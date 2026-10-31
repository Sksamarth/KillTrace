"""Small JSON job manifests and an ownership-checked single-worker lock."""
import heapq
import json
import os
import re
import time
import threading
from contextlib import contextmanager
from functools import wraps
from datetime import datetime, timezone
from pathlib import Path

ACTIVE = {"queued", "hashing", "running", "cancelling"}
_mutex = threading.RLock()
_held = threading.local()


@contextmanager
def management_guard(root):
    """Serialize short metadata/lock transitions across threads AND processes."""
    key = str(root.resolve())
    with _mutex:
        roots = getattr(_held, "roots", set())
        if key in roots:
            yield
            return
        with (root / ".management.lock").open("a+b") as stream:
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            for attempt in range(100):
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if attempt == 99:
                        raise RuntimeError("job management is busy; retry shortly")
                    time.sleep(0.05)
            _held.roots = roots | {key}
            try:
                yield
            finally:
                _held.roots = roots
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def guarded(root_argument):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with management_guard(root_argument(args[0])):
                return function(*args, **kwargs)
        return wrapped
    return decorate


def now():
    return datetime.now(timezone.utc).isoformat()


def sync_directory(path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def atomic_json(path, value):
    from uuid import uuid4
    temporary = path.with_suffix(f".{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(40):
        try:
            os.replace(temporary, path)
            sync_directory(path.parent)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.05)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def jobs_root(settings):
    root = settings.data_dir.resolve() / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def job_dir(settings, job_id):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise ValueError("invalid job ID")
    root = jobs_root(settings)
    path = (root / job_id).resolve()
    if path.parent != root or not (path / "job.json").is_file():
        raise FileNotFoundError("job not found")
    return path


def process_alive(pid):
    if not isinstance(pid, int) or pid < 1:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied: conservatively busy.
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@guarded(lambda root: root)
def release(root, job_id):
    path = root / ".worker.lock"
    if path.exists() and read_json(path).get("job_id") == job_id:
        path.unlink()


@guarded(lambda path: path.parent)
def reconcile(path):
    job = read_json(path / "job.json")
    if job["status"] in ACTIVE:
        lock_path = path.parent / ".worker.lock"
        lock = read_json(lock_path) if lock_path.exists() else {}
        dispatched = read_json(path / "dispatch.json").get("pid") if (path / "dispatch.json").exists() else None
        pid = job.get("worker_pid") or dispatched or (lock.get("owner_pid") if lock.get("job_id") == job["job_id"] else None)
        if not process_alive(pid):
            job.update(status="interrupted", completed_at=now(), error={"code": "worker_interrupted", "message": "Worker is no longer running. Resume from the last durable checkpoint."})
            atomic_json(path / "job.json", job)
            release(path.parent, job["job_id"])
    return job


@guarded(lambda root: root)
def claim(root, job_id):
    path = root / ".worker.lock"
    for attempt in range(2):
        try:
            with path.open("x", encoding="utf-8") as stream:
                json.dump({"job_id": job_id, "owner_pid": os.getpid()}, stream)
            return
        except FileExistsError:
            # Only remove an owned stale lock after proving its worker is absent.
            try:
                lock = read_json(path)
                other = root / lock["job_id"]
                if not re.fullmatch(r"[0-9a-f]{32}", lock["job_id"]):
                    raise RuntimeError("invalid worker lock; manual inspection required")
                reconcile(other)
            except (KeyError, FileNotFoundError, json.JSONDecodeError):
                raise RuntimeError("worker lock cannot be verified; manual inspection required")
            if path.exists() or attempt:
                raise RuntimeError("another ingestion worker owns this output directory")


def list_jobs(settings, limit=20, offset=0):
    root = jobs_root(settings)
    # Heap bounds memory even when the directory contains many historical jobs.
    entries = (entry for entry in root.iterdir() if re.fullmatch(r"[0-9a-f]{32}", entry.name) and (entry / "job.json").is_file())
    selected = heapq.nlargest(limit + offset, entries, key=lambda entry: (entry / "job.json").stat().st_mtime_ns)
    return [public_job(reconcile(path)) for path in selected[offset:]]


def public_job(job):
    return {key: value for key, value in job.items() if key not in {"source_path", "settings", "worker_pid"}}


def resolve_source(settings, reference):
    root = (settings.ingestion_input_dir or settings.data_dir).resolve()
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() not in {".jsonl", ".ndjson"}:
        raise ValueError("provide a relative JSONL filename under the configured input directory")
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("source is outside the input directory or is not a file")
    return path


def sources(settings):
    root = (settings.ingestion_input_dir or settings.data_dir).resolve()
    if not root.is_dir():
        return []
    result = []
    with os.scandir(root) as entries:
        for entry in entries:
            if entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in {".jsonl", ".ndjson"}:
                result.append({"reference": entry.name, "bytes": entry.stat().st_size})
                if len(result) == 100:
                    break
    return sorted(result, key=lambda item: item["reference"])
