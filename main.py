from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chat import answer_question
from ingest import collection_exists, delete_creator_collection, ingest_creator, list_creators
from retriever import retrieve_chunks


load_dotenv()

app = FastAPI(title="Creator Chat")
app.mount("/static", StaticFiles(directory="static"), name="static")

executor = ThreadPoolExecutor(max_workers=1)
ingest_jobs: dict[str, dict[str, Any]] = {}
ingest_jobs_lock = Lock()


class IngestRequest(BaseModel):
    channel_url: str
    creator_name: str
    overwrite: bool = False


class ChatRequest(BaseModel):
    question: str
    creator_name: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/style.css")
def root_style() -> FileResponse:
    return FileResponse("static/style.css")


@app.get("/app.js")
def root_script() -> FileResponse:
    return FileResponse("static/app.js")


@app.post("/ingest")
def ingest(request: IngestRequest) -> dict[str, Any]:
    if not request.channel_url.strip() or not request.creator_name.strip():
        raise HTTPException(status_code=400, detail="channel_url and creator_name are required")

    creator_name = request.creator_name.strip()
    if not request.overwrite and collection_exists(creator_name):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "exists",
                "creator_name": creator_name,
                "message": f"{creator_name} is already loaded. Re-ingest to refresh the stored transcripts.",
            },
        )

    job_id = uuid4().hex
    _update_job(
        job_id,
        status="queued",
        stage="queued",
        message="Queued ingestion job.",
        percent=0,
        creator_name=creator_name,
    )
    executor.submit(_run_ingest_job, job_id, request.channel_url.strip(), creator_name, request.overwrite)
    return {"status": "queued", "job_id": job_id, "creator_name": creator_name}


@app.get("/ingest/{job_id}")
def ingest_status(job_id: str) -> dict[str, Any]:
    with ingest_jobs_lock:
        job = ingest_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Ingestion job not found")
        return dict(job)


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    if not request.question.strip() or not request.creator_name.strip():
        raise HTTPException(status_code=400, detail="question and creator_name are required")
    try:
        chunks = retrieve_chunks(request.question.strip(), request.creator_name.strip())
        return answer_question(request.question.strip(), chunks, request.creator_name.strip())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/creators")
def creators() -> list[dict[str, str]]:
    return list_creators()


@app.delete("/creator/{creator_name}")
def delete_creator(creator_name: str) -> dict[str, str]:
    delete_creator_collection(creator_name)
    return {"status": "deleted", "creator_name": creator_name}


def _run_ingest_job(job_id: str, channel_url: str, creator_name: str, overwrite: bool) -> None:
    def progress(update: dict[str, Any]) -> None:
        _update_job(job_id, status="running", **update)

    try:
        result = ingest_creator(
            channel_url=channel_url,
            creator_name=creator_name,
            overwrite=overwrite,
            progress_callback=progress,
        )
        _update_job(
            job_id,
            status="complete",
            stage="complete",
            message=result.get("message", "Creator loaded."),
            percent=100,
            result=result,
            creator_name=result.get("creator_name", creator_name),
            videos_processed=result.get("videos_processed", 0),
            chunks_stored=result.get("chunks_stored", 0),
        )
    except Exception as exc:
        _update_job(job_id, status="error", stage="error", message=str(exc), error=str(exc), percent=100)


def _update_job(job_id: str, **updates: Any) -> None:
    with ingest_jobs_lock:
        current = ingest_jobs.setdefault(job_id, {"job_id": job_id})
        current.update(updates)


def _completed_job(result: dict[str, Any]) -> str:
    job_id = uuid4().hex
    _update_job(
        job_id,
        status="complete",
        stage="complete",
        message=result.get("message", "Creator loaded."),
        percent=100,
        result=result,
        creator_name=result.get("creator_name", ""),
        videos_processed=result.get("videos_processed", 0),
        chunks_stored=result.get("chunks_stored", 0),
    )
    return job_id
