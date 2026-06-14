import html
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from config import CHROMA_PATH, CHUNK_OVERLAP, CHUNK_SIZE, EMBED_MODEL, MAX_VIDEOS, SUBTITLE_TMP_PATH
from style_profile import build_style_profile, delete_style_profile, save_style_profile


TIMESTAMP_RE = re.compile(
    r"^\s*(?:\d+\s*)?(?:\d{1,2}:)?\d{1,2}:\d{2}[\.,]\d{3}\s*-->\s*(?:\d{1,2}:)?\d{1,2}:\d{2}[\.,]\d{3}.*$"
)
INLINE_TIMESTAMP_RE = re.compile(r"<\d{1,2}:\d{2}:\d{2}\.\d{3}>|<\d{1,2}:\d{2}\.\d{3}>")
TAG_RE = re.compile(r"<[^>]+>")
NOISE_RE = re.compile(r"\[(?:music|applause|laughter|noise|silence|sound)\]", re.IGNORECASE)
COLLECTION_RE = re.compile(r"[^a-z0-9_-]+")


@dataclass(frozen=True)
class VideoTranscript:
    video_id: str
    title: str
    url: str
    published_date: str
    transcript: str


def collection_name_for_creator(creator_name: str) -> str:
    slug = COLLECTION_RE.sub("_", creator_name.strip().lower()).strip("_-")
    if not slug:
        slug = "creator"
    name = f"cc_{slug}"
    return name[:63].rstrip("_-") if len(name) > 63 else name


def clean_transcript(raw_text: str) -> str:
    seen_lines: set[str] = set()
    cleaned_lines: list[str] = []

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.upper() == "WEBVTT" or line.upper().startswith("NOTE"):
            continue
        if line.isdigit() or TIMESTAMP_RE.match(line):
            continue

        line = html.unescape(line)
        line = INLINE_TIMESTAMP_RE.sub("", line)
        line = TAG_RE.sub("", line)
        line = NOISE_RE.sub("", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue

        normalized = line.lower()
        if normalized in seen_lines:
            continue
        seen_lines.add(normalized)
        cleaned_lines.append(line)

    return " ".join(cleaned_lines).strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    if not words:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


def collection_exists(creator_name: str) -> bool:
    client = _chroma_client()
    return collection_name_for_creator(creator_name) in _list_collection_names(client)


def delete_creator_collection(creator_name: str) -> None:
    client = _chroma_client()
    name = collection_name_for_creator(creator_name)
    if name in _list_collection_names(client):
        client.delete_collection(name)
    delete_style_profile(creator_name)


def list_creators() -> list[dict[str, str]]:
    client = _chroma_client()
    creators: list[dict[str, str]] = []
    for collection in client.list_collections():
        name = collection.name if hasattr(collection, "name") else str(collection)
        if not name.startswith("cc_"):
            continue
        metadata = getattr(collection, "metadata", None) or {}
        creators.append(
            {
                "creator_name": str(metadata.get("creator_name") or name.removeprefix("cc_").replace("_", " ").title()),
                "collection_name": name,
            }
        )
    return sorted(creators, key=lambda item: item["creator_name"].lower())


ProgressCallback = Callable[[dict[str, Any]], None]


def ingest_creator(
    channel_url: str,
    creator_name: str,
    overwrite: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    _report_progress(progress_callback, "checking", "Checking existing creator data.", 3)
    collection_name = collection_name_for_creator(creator_name)
    client = _chroma_client()

    if collection_name in _list_collection_names(client):
        if not overwrite:
            return {
                "status": "exists",
                "creator_name": creator_name,
                "message": f"{creator_name} is already loaded. Re-ingest to refresh the stored transcripts.",
            }
        _report_progress(progress_callback, "resetting", "Replacing existing creator data.", 7)
        client.delete_collection(collection_name)
        delete_style_profile(creator_name)

    videos = _fetch_video_transcripts(channel_url, progress_callback=progress_callback)
    documents: list[str] = []
    ids: list[str] = []
    metadatas: list[dict[str, Any]] = []

    _report_progress(
        progress_callback,
        "chunking",
        f"Chunking transcripts from {len(videos)} videos.",
        72,
        videos_processed=len(videos),
    )
    for video in videos:
        for index, chunk in enumerate(chunk_text(video.transcript)):
            ids.append(f"{video.video_id}:{index}")
            documents.append(chunk)
            metadatas.append(
                {
                    "creator_name": creator_name,
                    "video_id": video.video_id,
                    "video_title": video.title,
                    "video_url": video.url,
                    "published_date": video.published_date,
                    "chunk_index": index,
                }
            )

    _report_progress(
        progress_callback,
        "style",
        "Building a style profile from loaded transcripts.",
        78,
        videos_processed=len(videos),
    )
    save_style_profile(creator_name, build_style_profile(creator_name, [video.transcript for video in videos]))

    _report_progress(
        progress_callback,
        "embedding",
        f"Embedding {len(documents)} transcript chunks locally.",
        82,
        videos_processed=len(videos),
        chunks_stored=0,
    )
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"creator_name": creator_name},
        embedding_function=_embedding_function(),
    )

    if documents:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)

    status = "warning" if len(videos) < 5 else "ok"
    _report_progress(
        progress_callback,
        "complete",
        "Creator loaded. Opening chat.",
        100,
        videos_processed=len(videos),
        chunks_stored=len(documents),
    )
    return {
        "status": status,
        "videos_processed": len(videos),
        "chunks_stored": len(documents),
        "creator_name": creator_name,
        "message": "Fewer than 5 videos had usable transcripts." if status == "warning" else "Creator loaded.",
    }


def _fetch_video_transcripts(
    channel_url: str,
    progress_callback: ProgressCallback | None = None,
) -> list[VideoTranscript]:
    from yt_dlp import YoutubeDL

    temp_root = Path(SUBTITLE_TMP_PATH)
    temp_root.mkdir(parents=True, exist_ok=True)

    playlist_opts = {
        "extract_flat": True,
        "playlistend": MAX_VIDEOS,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }

    _report_progress(progress_callback, "video_list", "Fetching the latest video list from YouTube.", 10)
    with YoutubeDL(playlist_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    with tempfile.TemporaryDirectory(prefix="ingest_", dir=temp_root) as run_dir:
        temp_dir = Path(run_dir)
        entries = [entry for entry in (info or {}).get("entries", []) if entry]
        transcripts: list[VideoTranscript] = []
        total = min(len(entries), MAX_VIDEOS)
        _report_progress(
            progress_callback,
            "captions",
            f"Found {total} videos. Downloading captions.",
            15,
            videos_total=total,
            videos_processed=0,
        )

        for position, entry in enumerate(entries[:MAX_VIDEOS], start=1):
            video_id = entry.get("id")
            webpage_url = entry.get("url") or entry.get("webpage_url")
            if not video_id:
                continue
            video_url = webpage_url if str(webpage_url).startswith("http") else f"https://www.youtube.com/watch?v={video_id}"
            title = entry.get("title") or video_id
            percent = 15 + int((position - 1) / max(total, 1) * 55)
            _report_progress(
                progress_callback,
                "captions",
                f"Downloading captions {position}/{total}: {title}",
                percent,
                videos_total=total,
                videos_processed=len(transcripts),
            )
            subtitle_path = _download_subtitle(video_url, video_id, temp_dir)
            if subtitle_path is None:
                print(f"No transcript found for {video_url}")
                continue

            cleaned = clean_transcript(subtitle_path.read_text(encoding="utf-8", errors="ignore"))
            if not cleaned:
                print(f"Transcript was empty after cleaning for {video_url}")
                continue

            transcripts.append(
                VideoTranscript(
                    video_id=video_id,
                    title=title,
                    url=video_url,
                    published_date=str(entry.get("upload_date") or entry.get("timestamp") or ""),
                    transcript=cleaned,
                )
            )
            _report_progress(
                progress_callback,
                "captions",
                f"Processed captions for {len(transcripts)}/{total} usable videos.",
                15 + int(position / max(total, 1) * 55),
                videos_total=total,
                videos_processed=len(transcripts),
            )

        return transcripts


def _download_subtitle(video_url: str, video_id: str, temp_dir: Path) -> Path | None:
    from yt_dlp import YoutubeDL

    before = set(temp_dir.glob(f"{video_id}*"))
    opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en.*"],
        "subtitlesformat": "vtt/srt/best",
        "outtmpl": {"default": str(temp_dir / "%(id)s.%(ext)s")},
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }

    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([video_url])
    except Exception as exc:
        print(f"Failed to download subtitles for {video_url}: {exc}")
        return None

    candidates = [path for path in temp_dir.glob(f"{video_id}*") if path.suffix.lower() in {".vtt", ".srt"}]
    new_candidates = [path for path in candidates if path not in before]
    return (new_candidates or candidates or [None])[0]


def _chroma_client():
    import chromadb

    return chromadb.PersistentClient(path=CHROMA_PATH)


def _embedding_function():
    from chromadb.utils import embedding_functions

    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)


def _list_collection_names(client: Any) -> set[str]:
    names: set[str] = set()
    for collection in client.list_collections():
        names.add(collection.name if hasattr(collection, "name") else str(collection))
    return names


def _report_progress(
    progress_callback: ProgressCallback | None,
    stage: str,
    message: str,
    percent: int,
    **extra: Any,
) -> None:
    if progress_callback is None:
        return
    progress_callback({"stage": stage, "message": message, "percent": max(0, min(percent, 100)), **extra})
