import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import Settings
from app.job_store import ACTIVE, job_dir, list_jobs, public_job, read_json, reconcile, sources
from app.jobs import cancel, create_job, launch, prepare_resume

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


class StartJob(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source: str = Field(min_length=1, max_length=1024)
    source_id: str | None = Field(default=None, min_length=1, max_length=256)
    source_profile: Literal["simedr-json-1.0.0", "raw-text-1.0.0", "web-combined-1.0.0", "key-value-1.0.0", "json-record-1.0.0"]
    synthetic: bool

    @model_validator(mode="after")
    def profile_flags(self):
        if self.source_profile == "simedr-json-1.0.0" and not self.synthetic:
            raise ValueError("SimEDR profile requires synthetic=true")
        return self


def status(settings, job_id):
    work = job_dir(settings, job_id)
    job = reconcile(work)
    if job["status"] in ACTIVE and (work / "cancel.request").exists():
        job["status"] = "cancelling"
    return public_job(job)


def http_error(error):
    if isinstance(error, (FileNotFoundError, NotADirectoryError)):
        raise HTTPException(404, "Local source or job not found")
    if isinstance(error, ValueError):
        raise HTTPException(400, str(error))
    if isinstance(error, RuntimeError):
        raise HTTPException(409, str(error))
    raise HTTPException(500, "Worker could not be started; inspect the local job log")


@router.get("/sources")
def input_sources():
    settings = Settings()
    from app.log_formats import PROFILES
    return {"items": sources(settings), "limit": 100, "source_profiles": list(PROFILES), "source_profile": "simedr-json-1.0.0", "configuration": {key: value for key, value in settings.model_dump(mode="json").items() if key.startswith("ingestion_") and key != "ingestion_input_dir"}}


@router.post("/jobs", status_code=202)
def start(body: StartJob):
    settings = Settings()
    try:
        work = create_job(settings, body.source, body.source_id, body.source_profile, body.synthetic)
        launch(work)
        return status(settings, work.name)
    except (OSError, ValueError, RuntimeError) as error:
        http_error(error)


@router.get("/jobs")
def job_list(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=1000)):
    return {"items": list_jobs(Settings(), limit, offset), "limit": limit, "offset": offset}


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    try:
        return status(Settings(), job_id)
    except (OSError, ValueError, RuntimeError) as error:
        http_error(error)


@router.get("/jobs/{job_id}/validation")
def validation_log(job_id: str, limit: int = Query(50, ge=1, le=100), cursor: int = Query(0, ge=0)):
    try:
        work = job_dir(Settings(), job_id)
        checkpoint_path = work / "checkpoint.json"
        end = read_json(checkpoint_path)["ledger_bytes"] if checkpoint_path.exists() else 0
        if cursor > end:
            raise ValueError("validation cursor exceeds the durable ledger")
        if not end:
            return {"items": [], "next_cursor": None}
        items = []
        with (work / "validation.jsonl").open("rb") as stream:
            if cursor:
                stream.seek(cursor - 1)
                if stream.read(1) != b"\n":
                    raise ValueError("validation cursor must be a record boundary")
            stream.seek(cursor)
            while stream.tell() < end and len(items) < limit:
                raw = stream.readline(min(65536, end - stream.tell()))
                if not raw or not raw.endswith(b"\n"):
                    raise ValueError("durable validation ledger is malformed")
                items.append(json.loads(raw))
            next_cursor = stream.tell() if stream.tell() < end else None
        return {"items": items, "next_cursor": next_cursor}
    except (OSError, ValueError, RuntimeError) as error:
        http_error(error)


@router.post("/jobs/{job_id}/cancel", status_code=202)
def cancel_job(job_id: str):
    settings = Settings()
    try:
        cancel(settings, job_id)
        return status(settings, job_id)
    except (OSError, ValueError, RuntimeError) as error:
        http_error(error)


@router.post("/jobs/{job_id}/resume", status_code=202)
def resume_job(job_id: str):
    settings = Settings()
    try:
        work = prepare_resume(settings, job_id)
        launch(work)
        return status(settings, job_id)
    except (OSError, ValueError, RuntimeError) as error:
        http_error(error)
