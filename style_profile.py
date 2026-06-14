import json
import re
from pathlib import Path
from typing import Any

from config import STYLE_PROFILE_PATH


KEY_RE = re.compile(r"[^a-z0-9_-]+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
PHRASE_RE = re.compile(r"\b(?:you need to|the way to|what I would do|here's the thing|the point is|think about it)\b", re.IGNORECASE)


def style_key(creator_name: str) -> str:
    key = KEY_RE.sub("_", creator_name.strip().lower()).strip("_-")
    return key or "creator"


def build_style_profile(creator_name: str, transcripts: list[str]) -> dict[str, Any]:
    text = " ".join(transcripts)
    words = text.split()
    sentences = [sentence.strip() for sentence in SENTENCE_RE.split(text) if sentence.strip()]
    phrase_counts: dict[str, int] = {}

    for match in PHRASE_RE.finditer(text):
        phrase = match.group(0).lower()
        phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

    common_phrases = [
        phrase for phrase, _count in sorted(phrase_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]
    avg_sentence_words = round(len(words) / max(len(sentences), 1), 1) if words else 0

    return {
        "creator_name": creator_name,
        "avg_sentence_words": avg_sentence_words,
        "common_phrases": common_phrases,
        "style_note": (
            "Use the creator's directness, pacing, and explanation structure when those traits are visible "
            "in the retrieved chunks. Do not infer facts from this style profile."
        ),
    }


def save_style_profile(creator_name: str, profile: dict[str, Any]) -> None:
    path = Path(STYLE_PROFILE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    profiles = _read_profiles(path)
    profiles[style_key(creator_name)] = profile
    path.write_text(json.dumps(profiles, indent=2, sort_keys=True), encoding="utf-8")


def load_style_profile(creator_name: str) -> dict[str, Any] | None:
    path = Path(STYLE_PROFILE_PATH)
    profiles = _read_profiles(path)
    profile = profiles.get(style_key(creator_name))
    return profile if isinstance(profile, dict) else None


def delete_style_profile(creator_name: str) -> None:
    path = Path(STYLE_PROFILE_PATH)
    profiles = _read_profiles(path)
    profiles.pop(style_key(creator_name), None)
    if profiles:
        path.write_text(json.dumps(profiles, indent=2, sort_keys=True), encoding="utf-8")
    elif path.exists():
        path.unlink()


def format_style_profile(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "No separate style profile is available. Use only the style visible in the retrieved chunks."

    phrases = profile.get("common_phrases") or []
    phrase_text = ", ".join(phrases) if phrases else "No repeated phrases detected."
    return (
        f"Average sentence length: {profile.get('avg_sentence_words', 0)} words. "
        f"Common phrasing signals: {phrase_text}. "
        f"{profile.get('style_note', '')}"
    ).strip()


def _read_profiles(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
