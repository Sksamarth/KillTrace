"""Single-writer, checkpointed SimEDR JSONL to canonical Parquet ingestion."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from app.config import Settings
from app.contracts.arrow_v1 import ARROW_SCHEMA, to_arrow_row
from app.contracts.v1 import MAX_RECORD_BYTES, Provenance, TRANSFORMATION_VERSION, validate_json_record
from app.job_store import atomic_json, now, process_alive, read_json, release, resolve_source, sync_directory
from app.resources import check_resources, memory_bytes
from app.storage import open_database

INDEX_SCHEMA = pa.schema([(name, pa.int64() if name in {"record_number", "byte_offset", "byte_length"} else pa.string()) for name in
    ("source_record_id", "normalization_id", "record_number", "byte_offset", "byte_length", "raw_sha256", "validation_status", "parquet_part")])


class Cancelled(Exception):
    pass


class SourceChanged(ValueError):
    pass


def records(stream, start_number=0, start_offset=0):
    """Drain oversized physical lines with at most 1 MiB+1 bytes buffered."""
    number, offset = start_number, start_offset
    while raw := stream.readline(MAX_RECORD_BYTES + 1):
        number += 1
        length = len(raw)
        digest = hashlib.sha256(raw)
        if length > MAX_RECORD_BYTES:
            while not raw.endswith(b"\n"):
                raw = stream.readline(MAX_RECORD_BYTES + 1)
                if not raw:
                    break
                length += len(raw)
                digest.update(raw)
            raw = None
        yield number, offset, length, digest.hexdigest(), raw
        offset += length


def source_hash(source, cancelled):
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            if cancelled():
                raise Cancelled()
            digest.update(chunk)
    return digest.hexdigest()


def recover_outputs(work, db, checkpoint):
    """Rollback the at-most-one uncheckpointed batch after a process crash."""
    db.execute("DELETE FROM events WHERE record_number > ?", [checkpoint["records_processed"]])
    for path in (work / "events").rglob("part-*"):
        if not path.is_file():
            continue
        # Only known generated files under this owned job directory are touched.
        if path.suffix == ".tmp" or int(path.stem.split("-")[1]) >= checkpoint["parquet_parts"]:
            path.unlink()
    ledger = work / "validation.jsonl"
    if ledger.stat().st_size < checkpoint["ledger_bytes"]:
        raise ValueError("validation ledger is shorter than the durable checkpoint")
    with ledger.open("r+b") as stream:
        stream.truncate(checkpoint["ledger_bytes"])
    part_count = row_count = 0
    for part in (work / "events").rglob("*.parquet"):
        part_count += 1
        row_count += pq.ParquetFile(part).metadata.num_rows
    catalog_count = db.execute("SELECT count(*) FROM events").fetchone()[0]
    if part_count != checkpoint["parquet_parts"] or row_count != checkpoint["records_accepted"] or catalog_count != row_count:
        raise ValueError("durable checkpoint outputs are missing or inconsistent; restore them or start a new job")


def run_job(work: Path):
    job = read_json(work / "job.json")
    settings = Settings.model_validate(job["settings"])
    lock = read_json(work.parent / ".worker.lock")
    if lock["job_id"] != job["job_id"]:
        raise RuntimeError("job does not own the single-writer lock")
    if job.get("worker_pid") and job["worker_pid"] != os.getpid() and process_alive(job["worker_pid"]):
        raise RuntimeError("a different live process already owns this job")
    if job["status"] not in {"queued", "hashing", "running", "cancelling"}:
        raise ValueError("job is not queued for execution")
    source = Path(job["source_path"])
    job.update(status="hashing", worker_pid=os.getpid(), started_at=job.get("started_at") or now(), last_started_at=now(), completed_at=None, error=None)
    start = time.monotonic()
    db = None
    ledger = None
    checkpoint = None
    batch, estimated = [], 0

    def cancelled():
        return (work / "cancel.request").exists()

    def save():
        job["elapsed_seconds"] = round(job.get("previous_elapsed_seconds", 0) + time.monotonic() - start, 3)
        try:
            atomic_json(work / "job.json", job)
        except PermissionError:
            # Advisory progress may be temporarily locked by a Windows reader.
            # Checkpoint and final status writes below remain mandatory.
            pass

    def memory_guard():
        current, peak = memory_bytes()
        job["peak_worker_rss_bytes"] = max(job.get("peak_worker_rss_bytes", 0), peak)
        if current > settings.ingestion_memory_mb * 1024**2:
            raise MemoryError("configured memory admission budget exceeded")

    def flush():
        nonlocal batch, estimated, checkpoint
        memory_guard()
        check_resources(settings, work, estimated + 1024**2)
        part = checkpoint["parquet_parts"]
        index_rows = []
        # Partition only this bounded batch; no global date/event aggregation.
        groups = {}
        for row, status in batch:
            instant = row["timestamp"]["utc"]
            date = instant.date().isoformat() if instant else "unknown"
            groups.setdefault(date, []).append((row, status))
        for date, entries in groups.items():
            directory = work / "events" / f"date={date}"
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"part-{part:08d}.parquet"
            temporary = target.with_suffix(".tmp")
            pq.write_table(pa.Table.from_pylist([row for row, _ in entries], schema=ARROW_SCHEMA), temporary, compression="zstd", row_group_size=settings.ingestion_row_group_rows)
            with temporary.open("r+b") as part_stream:
                os.fsync(part_stream.fileno())
            if temporary.stat().st_size > settings.ingestion_temp_bytes:
                raise OSError("temporary Parquet output exceeds configured disk budget")
            os.replace(temporary, target)
            sync_directory(directory)
            sync_directory(directory.parent)
            relative = target.relative_to(work).as_posix()
            for row, status in entries:
                ref = row["provenance"]
                index_rows.append((row["source_record_id"], row["normalization_id"], ref["record_number"], ref["byte_offset"], ref["byte_length"], ref["raw_sha256"], status, relative))
            part += 1
        if index_rows:
            table = pa.table({field.name: [row[index] for row in index_rows] for index, field in enumerate(INDEX_SCHEMA)}, schema=INDEX_SCHEMA)
            db.register("ingestion_index", table)
            db.execute("BEGIN TRANSACTION")
            try:
                db.execute("INSERT INTO events SELECT * FROM ingestion_index")
                db.execute("COMMIT")
            except BaseException:
                try:
                    db.execute("ROLLBACK")
                except Exception:
                    pass  # Preserve the original commit/write failure for reporting.
                raise
            finally:
                db.unregister("ingestion_index")
        ledger.flush()
        os.fsync(ledger.fileno())
        # DB WAL COMMIT + fsynced ledger + complete Parquet precede the checkpoint.
        checkpoint = {**{key: job[key] for key in ("records_processed", "records_accepted", "records_partial", "records_rejected", "bytes_processed")}, "parquet_parts": part, "ledger_bytes": ledger.tell(), "artifact_sha256": job["artifact_sha256"], "created_at": now()}
        atomic_json(work / "checkpoint.json", checkpoint)
        job["checkpoint"] = checkpoint
        batch, estimated = [], 0
        save()

    try:
        save()
        check_resources(settings, work)
        if resolve_source(settings, job["source_reference"]) != source:
            raise SourceChanged("source reference resolves to a different location")
        stat = source.stat()
        if stat.st_size != job["source_size"] or stat.st_mtime_ns != job["source_mtime_ns"]:
            raise SourceChanged("source metadata changed since job selection; start a new job")
        digest = source_hash(source, cancelled)
        if job.get("artifact_sha256") and (job["artifact_sha256"] != digest or job["source_size"] != stat.st_size or job["source_mtime_ns"] != stat.st_mtime_ns):
            raise SourceChanged("source changed since this job was created; resume refused")
        job.update(artifact_sha256=digest, source_size=stat.st_size, source_mtime_ns=stat.st_mtime_ns)
        # Reserve room for a pending Parquet part while clamping DuckDB spill.
        configured = int(settings.duckdb_max_temp_size[:-2]) * (1000**3 if settings.duckdb_max_temp_size.endswith("GB") else 1000**2)
        spill_bytes = min(configured, settings.ingestion_temp_bytes - settings.ingestion_batch_bytes - 1024**2)
        declared_memory = int(settings.duckdb_memory_limit[:-2]) * (1000**3 if settings.duckdb_memory_limit.endswith("GB") else 1000**2)
        job["effective_duckdb_memory_limit"] = f"{max(1, min(declared_memory, settings.ingestion_memory_mb * 1024**2 // 2) // 1000000)}MB"
        job["effective_duckdb_temp_limit"] = f"{max(1, spill_bytes // 1000000)}MB"
        db = open_database(settings.model_copy(update={"data_dir": work, "duckdb_max_temp_size": job["effective_duckdb_temp_limit"], "duckdb_memory_limit": job["effective_duckdb_memory_limit"]}))
        # Append-only columnar catalog: avoid a global in-memory ART/unique index.
        # Sequential byte locators + rollback to the checkpoint enforce replay safety.
        db.execute("CREATE TABLE IF NOT EXISTS events (source_record_id VARCHAR, normalization_id VARCHAR, record_number BIGINT, byte_offset BIGINT, byte_length BIGINT, raw_sha256 VARCHAR, validation_status VARCHAR, parquet_part VARCHAR)")
        (work / "events").mkdir(exist_ok=True)
        ledger_path = work / "validation.jsonl"
        ledger_path.touch(exist_ok=True)
        if (work / "checkpoint.json").exists():
            checkpoint = read_json(work / "checkpoint.json")
            if checkpoint["artifact_sha256"] != digest:
                raise SourceChanged("checkpoint source digest does not match")
            recover_outputs(work, db, checkpoint)
        else:
            checkpoint = {"records_processed": 0, "records_accepted": 0, "records_partial": 0, "records_rejected": 0, "bytes_processed": 0, "parquet_parts": 0, "ledger_bytes": 0, "artifact_sha256": digest, "created_at": now()}
            recover_outputs(work, db, checkpoint)
            atomic_json(work / "checkpoint.json", checkpoint)
        for key in ("records_processed", "records_accepted", "records_partial", "records_rejected", "bytes_processed"):
            job[key] = checkpoint[key]
        job.update(status="running", checkpoint=checkpoint)
        save()
        ledger = ledger_path.open("ab")
        since_checkpoint = 0
        with source.open("rb") as stream:
            stream.seek(checkpoint["bytes_processed"])
            for number, offset, length, raw_hash, raw in records(stream, checkpoint["records_processed"], checkpoint["bytes_processed"]):
                if cancelled():
                    flush()
                    raise Cancelled()
                if number % 128 == 0:
                    memory_guard()
                if raw is None:
                    row, status, issues = None, "rejected", ["record_too_large"]
                else:
                    ref = Provenance(original_file=str(source), artifact_sha256=digest, source_id=job["source_id"], source_format="jsonl", record_number=number, byte_offset=offset, byte_length=length, raw_sha256=raw_hash, batch_id=UUID(job["job_id"]), transformation_version=TRANSFORMATION_VERSION, synthetic=True)
                    result = validate_json_record(raw, ref)
                    row = to_arrow_row(result.event) if result.event else None
                    status, issues = result.status, result.issues
                cost = length + len(row["source_fields_json"].encode("utf-8")) + 4096 if row else 0
                if batch and (len(batch) >= settings.ingestion_batch_rows or estimated + cost > settings.ingestion_batch_bytes):
                    flush()
                    since_checkpoint = 0
                if row and cost > settings.ingestion_batch_bytes:
                    row, status, issues = None, "rejected", ["record_exceeds_batch_budget"]
                job["records_processed"] = number
                job["bytes_processed"] = offset + length
                if row:
                    batch.append((row, status))
                    estimated += cost
                    job["records_accepted"] += 1
                    job["records_partial"] += status == "partial"
                else:
                    job["records_rejected"] += 1
                if status != "valid":
                    diagnostic = {"ledger_version": "1.0.0", "validator_version": "1.0.0", "status": status, "issues": issues, "artifact_sha256": digest, "source_id": job["source_id"], "job_id": job["job_id"], "transformation_version": TRANSFORMATION_VERSION, "record_number": number, "byte_offset": offset, "byte_length": length, "raw_sha256": raw_hash}
                    ledger.write((json.dumps(diagnostic) + "\n").encode("utf-8"))
                    job["last_validation_issue"] = diagnostic
                since_checkpoint += 1
                if since_checkpoint >= settings.ingestion_batch_rows:
                    flush()
                    since_checkpoint = 0
        flush()
        if source_hash(source, cancelled) != digest or source.stat().st_size != stat.st_size or source.stat().st_mtime_ns != stat.st_mtime_ns:
            raise SourceChanged("source changed during ingestion; completion refused")
        if cancelled():
            raise Cancelled()
        db.execute("CHECKPOINT")
        job.update(status="completed", completed_at=now())
    except Cancelled:
        job.update(status="cancelled", completed_at=now(), error=None)
    except BaseException as error:
        job.update(status="cancelled" if isinstance(error, KeyboardInterrupt) else "failed", completed_at=now(), error={"code": type(error).__name__, "message": str(error)[:2048]})
    finally:
        for resource in (ledger, db):
            if resource is not None:
                try:
                    resource.close()
                except Exception as error:
                    job.update(status="failed", completed_at=now())
                    job["error"] = job.get("error") or {"code": "cleanup_failed", "message": str(error)[:2048]}
        try:
            _, peak = memory_bytes()
            job["peak_worker_rss_bytes"] = max(job.get("peak_worker_rss_bytes", 0), peak)
        except (OSError, MemoryError):
            pass
        job["elapsed_seconds"] = round(job.get("previous_elapsed_seconds", 0) + time.monotonic() - start, 3)
        job["resume_from"] = job.get("checkpoint")
        try:
            atomic_json(work / "job.json", job)
        finally:
            release(work.parent, job["job_id"])
    return job


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", type=Path)
    parser.add_argument("--source")
    parser.add_argument("--resume")
    parser.add_argument("--dispatch-token")
    args = parser.parse_args()
    if args.job_dir:
        if args.dispatch_token:
            for _ in range(1000):
                ready = args.job_dir / "dispatch.json"
                if ready.exists() and read_json(ready).get("token") == args.dispatch_token:
                    break
                time.sleep(0.01)
            else:
                raise RuntimeError("dispatcher handshake did not complete")
        result = run_job(args.job_dir.resolve())
    else:
        from app.jobs import create_job, prepare_resume
        settings = Settings(_env_file=".env")
        work = prepare_resume(settings, args.resume) if args.resume else create_job(settings, args.source)
        result = run_job(work)
    print(json.dumps({key: value for key, value in result.items() if key not in {"settings", "source_path"}}, indent=2))
    raise SystemExit(0 if result["status"] == "completed" else 1)
