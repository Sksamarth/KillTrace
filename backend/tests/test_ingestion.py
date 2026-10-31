import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import duckdb
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.ingestion import records, run_job
from app.job_store import atomic_json, job_dir, read_json, reconcile
from app.jobs import cancel, create_job, prepare_resume
from app.main import app

FIXTURES = json.loads((Path(__file__).parent / "fixtures/simedr_records.json").read_text(encoding="utf-8"))


def settings(tmp_path, **updates):
    return Settings(data_dir=tmp_path / "output", ingestion_input_dir=tmp_path / "input", ingestion_batch_rows=3,
        ingestion_row_group_rows=2, ingestion_batch_bytes=65536, ingestion_memory_mb=1024, duckdb_memory_limit="128MB", **updates)


def source_file(config, rows=None):
    config.ingestion_input_dir.mkdir(exist_ok=True)
    source = config.ingestion_input_dir / "sample.jsonl"
    source.write_bytes(b"".join(row.encode() if isinstance(row, str) else row for row in (rows or [item["raw"] for item in FIXTURES["records"]])))
    return source


def stored_rows(work):
    for part in sorted((work / "events").rglob("*.parquet")):
        yield from pq.ParquetFile(part).read().to_pylist()


def test_valid_multiple_batches_and_provenance(tmp_path):
    config = settings(tmp_path)
    source = source_file(config)
    work = create_job(config, source.name)
    job = run_job(work)
    assert job["status"] == "completed"
    assert job["records_processed"] == job["records_accepted"] == len(FIXTURES["records"])
    assert job["records_rejected"] == 0
    assert int(job["effective_duckdb_memory_limit"][:-2]) <= 128
    assert job["checkpoint"]["parquet_parts"] > 1
    assert job["artifact_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    output = list(stored_rows(work))  # Only 21 small fixture records.
    assert len({row["source_record_id"] for row in output}) == len(output)
    for row in output:
        ref = row["provenance"]
        with source.open("rb") as stream:
            stream.seek(ref["byte_offset"])
            raw = stream.read(ref["byte_length"])
        assert hashlib.sha256(raw).hexdigest() == ref["raw_sha256"]
        assert json.loads(raw) == json.loads(row["source_fields_json"])
        assert UUID(ref["batch_id"]).hex == job["job_id"]
    assert any((work / "events").glob("date=*"))
    with duckdb.connect(str(work / "killchain.duckdb"), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM duckdb_constraints() WHERE table_name='events'").fetchone()[0] == 0
    for part in (work / "events").rglob("*.parquet"):
        metadata = pq.ParquetFile(part).metadata
        assert all(metadata.row_group(i).num_rows <= 2 for i in range(metadata.num_row_groups))


def test_invalid_partial_unknown_and_duplicate_records_are_not_discarded(tmp_path):
    config = settings(tmp_path)
    original = FIXTURES["records"][0]["raw"]
    changed = json.loads(original)
    changed["@timestamp"] = "bad-time"
    changed["event"]["type"] = ["unknown-source-type"]
    invalid_ip = json.loads(original)
    invalid_ip["source"] = {"ip": "bad-ip"}
    raw = [original, original, b'{"broken":\n', b'{}\n', (json.dumps(changed) + "\n").encode(), (json.dumps(invalid_ip) + "\n").encode()]
    source_file(config, raw)
    work = create_job(config, "sample.jsonl")
    job = run_job(work)
    assert job["status"] == "completed"
    assert job["records_processed"] == 6
    assert job["records_accepted"] == 4
    assert job["records_partial"] == job["records_rejected"] == 2
    output = list(stored_rows(work))
    assert len({row["source_record_id"] for row in output}) == 4
    assert sum(row["provenance"]["raw_sha256"] == hashlib.sha256(original.encode()).hexdigest() for row in output) == 2
    assert any(json.loads(row["source_fields_json"]).get("event", {}).get("type") == ["unknown-source-type"] for row in output)
    issues = [json.loads(line) for line in (work / "validation.jsonl").read_text().splitlines()]
    assert len(issues) == 4
    assert {item["status"] for item in issues} == {"partial", "rejected"}


def test_streaming_oversized_line_drains_without_losing_next_record():
    class Guarded(io.BytesIO):
        def read(self, *args):
            raise AssertionError("framer must not read whole input")
        def readline(self, size=-1):
            assert 0 < size <= 1024**2 + 1
            return super().readline(size)
    raw = b"x" * (2 * 1024**2) + b"\n{}\n"
    rows = list(records(Guarded(raw)))
    assert rows[0][-1] is None
    assert rows[0][2] == 2 * 1024**2 + 1
    assert rows[1][-1] == b"{}\n"
    assert rows[1][1] == rows[0][2]


def test_cancellation_checkpoint_resume_exactly_once(tmp_path, monkeypatch):
    config = settings(tmp_path)
    source_file(config)
    work = create_job(config, "sample.jsonl")
    original = pq.write_table
    calls = []
    def request_cancel(table, path, **kwargs):
        original(table, path, **kwargs)
        calls.append(path)
        if len(calls) == 1:
            (work / "cancel.request").touch()
    monkeypatch.setattr("app.ingestion.pq.write_table", request_cancel)
    stopped = run_job(work)
    assert stopped["status"] == "cancelled"
    assert 0 < stopped["checkpoint"]["records_processed"] < len(FIXTURES["records"])
    checkpoint_ids = {row["source_record_id"] for row in stored_rows(work)}
    monkeypatch.setattr("app.ingestion.pq.write_table", original)
    resumed = run_job(prepare_resume(config, work.name))
    assert resumed["status"] == "completed"
    output = list(stored_rows(work))
    assert len(output) == len(FIXTURES["records"])
    assert checkpoint_ids <= {row["source_record_id"] for row in output}
    assert len({row["source_record_id"] for row in output}) == len(output)


def test_crash_after_db_commit_before_checkpoint_is_rolled_back(tmp_path, monkeypatch):
    config = settings(tmp_path)
    source_file(config)
    work = create_job(config, "sample.jsonl")
    original = atomic_json
    calls = []
    def crash_before_checkpoint(path, value):
        if path.name == "checkpoint.json":
            calls.append(path)
            if len(calls) == 2:
                raise OSError("injected checkpoint failure after DB commit")
        return original(path, value)
    monkeypatch.setattr("app.ingestion.atomic_json", crash_before_checkpoint)
    failed = run_job(work)
    assert failed["status"] == "failed"
    assert read_json(work / "checkpoint.json")["records_processed"] == 0
    assert list((work / "events").rglob("*.parquet"))
    monkeypatch.setattr("app.ingestion.atomic_json", original)
    result = run_job(prepare_resume(config, work.name))
    assert result["status"] == "completed"
    assert len(list(stored_rows(work))) == len(FIXTURES["records"])
    with duckdb.connect(str(work / "killchain.duckdb"), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == len(FIXTURES["records"])


@pytest.mark.parametrize("resource", ["memory", "disk", "temporary"])
def test_resource_limits_fail_cleanly_and_can_recover(tmp_path, monkeypatch, resource):
    config = settings(tmp_path)
    source_file(config)
    work = create_job(config, "sample.jsonl")
    with monkeypatch.context() as patch:
        if resource == "memory":
            patch.setattr("app.resources.memory_bytes", lambda: (2 * 1024**3, 2 * 1024**3))
        elif resource == "disk":
            patch.setattr("app.resources.shutil.disk_usage", lambda path: SimpleNamespace(free=0))
        else:
            patch.setattr("app.resources.temporary_bytes", lambda path: config.ingestion_temp_bytes + 1)
        result = run_job(work)
    assert result["status"] == "failed"
    assert result["error"]["message"]
    assert not (work.parent / ".worker.lock").exists()
    assert run_job(prepare_resume(config, work.name))["status"] == "completed"


def test_changed_source_refuses_resume_and_live_lock_excludes_second_writer(tmp_path):
    config = settings(tmp_path)
    source = source_file(config)
    work = create_job(config, "sample.jsonl")
    with pytest.raises(RuntimeError):
        create_job(config, "sample.jsonl")
    cancel(config, work.name)
    assert run_job(work)["status"] == "cancelled"
    # Establish a hashed source then simulate a recoverable processing failure.
    result = run_job(prepare_resume(config, work.name))
    assert result["status"] == "completed"
    with pytest.raises(RuntimeError):
        prepare_resume(config, work.name)
    state = read_json(work / "job.json")
    state["status"] = "failed"  # Controlled crash fixture with a durable checkpoint.
    atomic_json(work / "job.json", state)
    source.write_bytes(source.read_bytes() + b'{}\n')
    result = run_job(prepare_resume(config, work.name))
    assert result["status"] == "failed"
    assert result["error"]["code"] == "SourceChanged"


def test_api_nonblocking_dispatch_status_cancel_resume_and_input_boundary(tmp_path, monkeypatch):
    config = settings(tmp_path)
    source = source_file(config)
    monkeypatch.setenv("KILLCHAIN_DATA_DIR", str(config.data_dir))
    monkeypatch.setenv("KILLCHAIN_INGESTION_INPUT_DIR", str(config.ingestion_input_dir))
    launched = []
    monkeypatch.setattr("app.ingestion_routes.launch", lambda work: launched.append(work))
    with TestClient(app) as client:
        assert client.get("/api/ingestion/sources").json()["items"][0]["reference"] == source.name
        body = {"source": source.name, "source_profile": "simedr-json-1.0.0", "synthetic": True}
        assert client.post("/api/ingestion/jobs", json={"source": source.name}).status_code == 422
        assert client.post("/api/ingestion/jobs", json={**body, "synthetic": False}).status_code == 422
        assert client.post("/api/ingestion/jobs", json={**body, "source": "../private.jsonl"}).status_code == 400
        assert client.post("/api/ingestion/jobs", json={**body, "source": str(source)}).status_code == 400
        response = client.post("/api/ingestion/jobs", json=body)
        assert response.status_code == 202
        job = response.json()
        assert job["status"] == "queued" and launched
        assert "source_path" not in job and "settings" not in job
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/ingestion/jobs", json=body).status_code == 409
        assert client.get("/api/ingestion/jobs?limit=1000").status_code == 422
        assert client.post(f"/api/ingestion/jobs/{job['job_id']}/cancel").json()["status"] == "cancelling"
        assert run_job(launched[-1])["status"] == "cancelled"
        assert client.post(f"/api/ingestion/jobs/{job['job_id']}/resume").status_code == 202
        assert run_job(launched[-1])["status"] == "completed"
        assert client.get(f"/api/ingestion/jobs/{job['job_id']}").json()["records_processed"] == len(FIXTURES["records"])
        assert client.post(f"/api/ingestion/jobs/{job['job_id']}/cancel").status_code == 409
        assert client.get("/api/ingestion/jobs/" + "0" * 32).status_code == 404


def test_interrupted_worker_is_detected_and_can_resume(tmp_path, monkeypatch):
    config = settings(tmp_path)
    source_file(config)
    work = create_job(config, "sample.jsonl")
    with monkeypatch.context() as patch:
        patch.setattr("app.job_store.process_alive", lambda pid: False)
        assert reconcile(work)["status"] == "interrupted"
    assert run_job(prepare_resume(config, work.name))["status"] == "completed"


def test_incompatible_budget_configuration_is_rejected():
    with pytest.raises(ValueError):
        Settings(ingestion_batch_bytes=8 * 1024**2, ingestion_temp_bytes=3 * 1024**2)


def test_dispatch_uses_a_token_independent_of_windows_launcher_pid(tmp_path, monkeypatch):
    from app.jobs import launch
    config = settings(tmp_path)
    source_file(config)
    work = create_job(config, "sample.jsonl")
    commands = []
    def fake_process(command, **options):
        commands.append(command)
        assert options["stdout"] is options["stderr"]
        return SimpleNamespace(pid=999999)
    monkeypatch.setattr("app.jobs.subprocess.Popen", fake_process)
    launch(work)
    dispatch = read_json(work / "dispatch.json")
    assert dispatch["pid"] == 999999
    assert dispatch["token"] == commands[0][commands[0].index("--dispatch-token") + 1]
    assert len(dispatch["token"]) == 32
    assert read_json(work.parent / ".worker.lock")["owner_pid"] == os.getpid()


def test_concurrent_status_reconciliation_has_no_shared_temporary_file_race(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    config = settings(tmp_path)
    source_file(config)
    work = create_job(config, "sample.jsonl")
    monkeypatch.setattr("app.job_store.process_alive", lambda pid: False)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: reconcile(work), range(16)))
    assert all(job["status"] == "interrupted" for job in results)
    assert not (work.parent / ".worker.lock").exists()


def test_record_larger_than_batch_budget_is_rejected_with_evidence(tmp_path):
    config = settings(tmp_path).model_copy(update={"ingestion_batch_bytes": 1024})
    source_file(config, [FIXTURES["records"][0]["raw"]])
    work = create_job(config, "sample.jsonl")
    job = run_job(work)
    assert job["status"] == "completed"
    assert job["records_processed"] == job["records_rejected"] == 1
    diagnostic = json.loads((work / "validation.jsonl").read_text())
    assert diagnostic["issues"] == ["record_exceeds_batch_budget"]
    assert diagnostic["byte_offset"] == 0 and diagnostic["raw_sha256"]


def test_oversized_physical_record_is_logged_and_next_record_is_ingested(tmp_path):
    config = settings(tmp_path)
    source_file(config, [b"x" * (1024**2 + 10) + b"\n", FIXTURES["records"][0]["raw"]])
    work = create_job(config, "sample.jsonl")
    job = run_job(work)
    assert job["status"] == "completed"
    assert job["records_processed"] == 2 and job["records_rejected"] == 1 and job["records_accepted"] == 1
    diagnostic = json.loads((work / "validation.jsonl").read_text())
    assert diagnostic["issues"] == ["record_too_large"]
    assert next(stored_rows(work))["provenance"]["record_number"] == 2


def test_validation_api_reads_only_bounded_durable_entries(tmp_path, monkeypatch):
    config = settings(tmp_path)
    source_file(config, [b'{broken}\n', b'{}\n', b'{}\n'])
    work = create_job(config, "sample.jsonl")
    assert run_job(work)["status"] == "completed"
    monkeypatch.setenv("KILLCHAIN_DATA_DIR", str(config.data_dir))
    with TestClient(app) as client:
        path = f"/api/ingestion/jobs/{work.name}/validation"
        first = client.get(path + "?limit=1").json()
        assert len(first["items"]) == 1
        assert first["items"][0]["issues"] == ["malformed_json_or_encoding"]
        second = client.get(path + f"?cursor={first['next_cursor']}&limit=100").json()
        assert len(second["items"]) == 2 and second["next_cursor"] is None
        assert client.get(path + "?cursor=1").status_code == 400
        assert client.get(path + "?limit=1000").status_code == 422


def test_memory_admission_failure_after_checkpoint_is_recoverable(tmp_path, monkeypatch):
    config = settings(tmp_path)
    source_file(config)
    work = create_job(config, "sample.jsonl")
    calls = []
    def increased_memory():
        calls.append(True)
        return (0, 0) if len(calls) == 1 else (2 * 1024**3, 2 * 1024**3)
    with monkeypatch.context() as patch:
        patch.setattr("app.ingestion.memory_bytes", increased_memory)
        failed = run_job(work)
    assert failed["status"] == "failed" and failed["error"]["code"] == "MemoryError"
    assert failed["checkpoint"]["records_processed"] == 3
    assert run_job(prepare_resume(config, work.name))["status"] == "completed"


def test_blank_input_root_environment_uses_safe_default(tmp_path, monkeypatch):
    monkeypatch.setenv("KILLCHAIN_INGESTION_INPUT_DIR", "")
    assert Settings(data_dir=tmp_path).ingestion_input_dir is None


def test_source_changed_before_worker_start_is_refused(tmp_path):
    config = settings(tmp_path)
    source = source_file(config)
    work = create_job(config, "sample.jsonl")
    source.write_bytes(source.read_bytes() + b'{}\n')
    job = run_job(work)
    assert job["status"] == "failed" and job["error"]["code"] == "SourceChanged"
    assert job["records_processed"] == 0
    with pytest.raises(ValueError, match="new job"):
        prepare_resume(config, work.name)


def test_atomic_manifest_retries_transient_windows_sharing(tmp_path, monkeypatch):
    original = os.replace
    calls = []
    def temporarily_locked(source, target):
        calls.append(target)
        if len(calls) < 3:
            raise PermissionError("simulated Windows sharing restriction")
        return original(source, target)
    monkeypatch.setattr("app.job_store.os.replace", temporarily_locked)
    monkeypatch.setattr("app.job_store.time.sleep", lambda seconds: None)
    target = tmp_path / "job.json"
    atomic_json(target, {"status": "completed"})
    assert read_json(target) == {"status": "completed"} and len(calls) == 3


def test_commit_failure_reports_original_error_even_if_rollback_fails(tmp_path, monkeypatch):
    from app.storage import open_database
    config = settings(tmp_path)
    source_file(config)
    work = create_job(config, "sample.jsonl")
    class BrokenCommit:
        def __init__(self, connection):
            self.connection = connection
        def __getattr__(self, name):
            return getattr(self.connection, name)
        def execute(self, sql, *parameters):
            if sql == "COMMIT":
                raise OSError("simulated disk-full commit failure")
            if sql == "ROLLBACK":
                raise RuntimeError("rollback could not run")
            return self.connection.execute(sql, *parameters)
    with monkeypatch.context() as patch:
        patch.setattr("app.ingestion.open_database", lambda options: BrokenCommit(open_database(options)))
        failed = run_job(work)
    assert failed["status"] == "failed"
    assert failed["error"] == {"code": "OSError", "message": "simulated disk-full commit failure"}
    assert run_job(prepare_resume(config, work.name))["status"] == "completed"


def test_missing_checkpoint_parquet_is_not_silently_accepted(tmp_path):
    config = settings(tmp_path)
    source_file(config)
    work = create_job(config, "sample.jsonl")
    assert run_job(work)["status"] == "completed"
    state = read_json(work / "job.json")
    state["status"] = "failed"  # Controlled interrupted job with a durable checkpoint.
    atomic_json(work / "job.json", state)
    next((work / "events").rglob("*.parquet")).unlink()
    result = run_job(prepare_resume(config, work.name))
    assert result["status"] == "failed"
    assert "missing or inconsistent" in result["error"]["message"]
