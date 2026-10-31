"""API/CLI job dispatch; CPU work executes in one separate local process."""
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from app.job_store import ACTIVE, atomic_json, claim, job_dir, jobs_root, now, process_alive, read_json, reconcile, release, resolve_source


def snapshot(settings):
    data = settings.model_dump(mode="json")
    data["data_dir"] = str(settings.data_dir.resolve())
    data["ingestion_input_dir"] = str((settings.ingestion_input_dir or settings.data_dir).resolve())
    return data


def create_job(settings, reference, source_id=None, source_profile="simedr-json-1.0.0", synthetic=True):
    from app.log_formats import PROFILES
    if source_profile not in PROFILES or (source_profile == "simedr-json-1.0.0" and not synthetic):
        raise ValueError("unsupported source profile or synthetic flag")
    source_id = source_id or ("local-simedr" if source_profile == "simedr-json-1.0.0" else "local-logs")
    source = resolve_source(settings, reference)
    root = jobs_root(settings)
    job_id = uuid4().hex
    work = root / job_id
    work.mkdir()
    job = {"job_id": job_id, "source_reference": reference, "source_path": str(source), "source_profile": source_profile, "source_id": source_id, "synthetic": synthetic,
        "source_size": source.stat().st_size, "source_mtime_ns": source.stat().st_mtime_ns, "schema_version": "1.0.0" if source_profile == "simedr-json-1.0.0" else "2.1.0" if source_profile == "firex-kv-1.0.0" else "2.0.0", "transformation_version": PROFILES[source_profile][1],
        "status": "queued", "created_at": now(), "started_at": None, "completed_at": None, "error": None, "checkpoint": None,
        "records_processed": 0, "records_accepted": 0, "records_partial": 0, "records_rejected": 0, "bytes_processed": 0, "attempt": 1,
        "elapsed_seconds": 0, "settings": snapshot(settings), "worker_pid": None}
    atomic_json(work / "job.json", job)
    try:
        claim(root, job_id)
    except Exception as error:
        job.update(status="failed", completed_at=now(), error={"code": "worker_busy", "message": str(error)})
        atomic_json(work / "job.json", job)
        raise
    return work


def prepare_resume(settings, job_id):
    work = job_dir(settings, job_id)
    job = reconcile(work)
    if job["status"] not in {"failed", "cancelled", "interrupted"}:
        raise RuntimeError("only failed, cancelled or interrupted jobs can be resumed")
    if (job.get("error") or {}).get("code") == "SourceChanged":
        raise ValueError("source changed; start a new job rather than reuse this checkpoint")
    if job.get("worker_pid") and job["worker_pid"] != os.getpid() and process_alive(job["worker_pid"]):
        raise RuntimeError("previous worker is still shutting down; retry resume shortly")
    source = resolve_source(settings, job["source_reference"])
    if str(source) != job["source_path"]:
        raise ValueError("source reference now resolves to a different location")
    claim(work.parent, job_id)
    try:
        (work / "cancel.request").unlink(missing_ok=True)
        (work / "dispatch.json").unlink(missing_ok=True)
        job.pop("last_validation_issue", None)
        job.update(status="queued", error=None, completed_at=None, worker_pid=None, attempt=job["attempt"] + 1,
            previous_elapsed_seconds=job["elapsed_seconds"], settings=snapshot(settings))
        atomic_json(work / "job.json", job)
    except BaseException:
        release(work.parent, job_id)
        raise
    return work


def launch(work):
    environment = os.environ.copy()
    backend = Path(__file__).resolve().parents[1]
    token = uuid4().hex
    environment["PYTHONPATH"] = str(backend) + os.pathsep + environment.get("PYTHONPATH", "")
    try:
        with (work / "worker.log").open("ab") as log:
            process = subprocess.Popen([sys.executable, "-m", "app.ingestion", "--job-dir", str(work), "--dispatch-token", token],
                cwd=backend.parent, env=environment, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        # Child waits for its PID handshake before opening DuckDB. The parent
        # never rewrites the lock after a child could have released it.
        atomic_json(work / "dispatch.json", {"pid": process.pid, "token": token})
    except BaseException as error:
        job = read_json(work / "job.json")
        job.update(status="failed", completed_at=now(), error={"code": "launch_failed", "message": str(error)[:2048]})
        atomic_json(work / "job.json", job)
        release(work.parent, work.name)
        raise


def cancel(settings, job_id):
    work = job_dir(settings, job_id)
    job = reconcile(work)
    if job["status"] not in ACTIVE:
        raise RuntimeError("job is not running")
    (work / "cancel.request").touch(exist_ok=True)
    return work
