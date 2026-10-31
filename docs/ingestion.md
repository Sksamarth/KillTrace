# Chunk 3 - bounded security log ingestion

## Supported source and phase boundary

The original v1 profile is **simedr-json-1.0.0**. Explicit v2 raw-text, key-value, generic JSON and combined access-log profiles are now available; see [current profile matrix](raw-log-ingestion.md). `.jsonl` and `.ndjson` are filename aliases for the same format. Every physical line is one logical record; the final record may omit a newline. CSV/CEF/syslog-specific field mappings, compressed archives, binary decoding and automatic schema inference are not implemented. UTF-8 syslog/application messages can be preserved using raw-text mode. The source-specific [v1 contract](data-contract.md) and [observed mappings](field-mappings.md) are unchanged.

This phase ingests and validates only. It adds no detections, ATT&CK mappings, incident correlation, graph visualization or AI calls. Source-supplied simulated annotations are preserved as source JSON without interpretation. The broader PRD remains the roadmap for later chunks.

## Start and inspect a job

Run the existing backend/API and frontend as described in the root README. The page lists up to 100 direct JSONL files from the configured input directory and accepts a relative path for nested files. The default input directory is `KILLCHAIN_DATA_DIR` (normally `data/`); `KILLCHAIN_INGESTION_INPUT_DIR` can provide a separate read-only source root. Absolute paths, parent traversal and resolved paths outside that root are rejected. Source selection requires acknowledgement of the approved synthetic profile. There are no uploads, arbitrary SQL, network sinks or remote log readers.

API conventions:

| Method and route | Response |
| --- | --- |
| GET `/api/ingestion/sources` | Bounded source list, supported profile and ingestion settings |
| POST `/api/ingestion/jobs` | 202: queued job; separate local worker process starts |
| GET `/api/ingestion/jobs?limit=20&offset=0` | Bounded job list (limit 1-100, offset 0-1000) |
| GET `/api/ingestion/jobs/{id}` | Status, attempt counts, outcomes, error and durable checkpoint |
| GET `/api/ingestion/jobs/{id}/validation?limit=50&cursor=0` | Bounded pages of durable validation entries; next byte cursor returned |
| POST `/api/ingestion/jobs/{id}/cancel` | 202: cooperative cancellation request |
| POST `/api/ingestion/jobs/{id}/resume` | 202: recover a failed, cancelled or interrupted job |

Start body:

```json
{"source":"simedr-1gib.jsonl","source_id":"local-simedr","source_profile":"simedr-json-1.0.0","synthetic":true}
```

These are processing metadata, not invented log columns. Invalid bodies return 422; unsupported/unsafe references return 400; absent jobs/sources return 404; an occupied worker or invalid state transition returns 409. `source_path`, private configuration paths and worker PID are excluded from API responses. The local loopback API remains unauthenticated; no remote deployment is added.

CLI from the repository root (`PYTHONPATH=backend`):

```sh
python -m app.ingestion --source simedr-1gib.jsonl
python -m app.ingestion --resume JOB_ID
```

The source argument is relative to the configured input directory, not the shell directory. CLI execution uses the same single-writer lock and checkpoints as API jobs. CLI exits zero only on completed jobs; cancelled/failed results exit nonzero and retain their state. API requests never wait for bulk hashing or normalization.

## Configuration and resource policy

All variables use the `KILLCHAIN_` prefix. They can be set through the environment; Uvicorn loads the root `.env` with the README's `--env-file` command. Source and output paths are separate in Compose (`/inputs` read-only, named `/data` output volume). The API snapshots configuration for each job; resume takes current application settings so resource limits can be adjusted after a failure.

| Setting suffix | Default | Meaning |
| --- | --- | --- |
| DATA_DIR | `data` | Local job/output root |
| INGESTION_INPUT_DIR | Unset | Input root; defaults to DATA_DIR |
| INGESTION_BATCH_ROWS | 4096 | Maximum accepted rows buffered per batch; also bounds rejection-only checkpoint intervals |
| INGESTION_BATCH_BYTES | 8388608 | Estimated raw + serialized source JSON + 4096-byte-per-row allowance |
| INGESTION_ROW_GROUP_ROWS | 1024 | Maximum Parquet row-group rows; clamped to batch row cap |
| INGESTION_MEMORY_MB | 768 | Soft current-process RSS admission budget in MiB |
| INGESTION_TEMP_BYTES | 67108864 | Spill plus pending temporary-output budget in bytes |
| INGESTION_DISK_RESERVE_BYTES | 268435456 | Required free space beyond pending output |
| DUCKDB_MEMORY_LIMIT | 1GB | Worker additionally clamps buffers to half the RSS admission budget, leaving Python/Arrow headroom; not an allocator-wide cap |
| DUCKDB_THREADS | 2 | Existing worker database thread limit |
| DUCKDB_MAX_TEMP_SIZE | 10GB | Existing spill ceiling; worker additionally clamps it to the smaller ingestion temporary budget |

A batch flushes before the first of row/estimated-byte limits is exceeded. A single otherwise valid record that cannot fit the configured batch budget is explicitly rejected as `record_exceeds_batch_budget`; increase the budget and start a new job if it must be reconsidered. The approved raw-record maximum remains 1 MiB. Oversized physical lines are drained in bounded chunks and recorded as `record_too_large` with their full byte length/digest/reference. They are not truncated into accepted events.

The byte estimate is not an exact Python heap limit. Parsing a bounded raw record, Arrow conversion and allocator overhead add memory. Current RSS is checked periodically and at batch boundaries; exceeding admission raises a recorded `MemoryError`. It cannot prevent every transient allocation or OS kill. Compose provides an additional 2 GB hard container cap shared by API and worker. Windows/VM/browser memory is separate. Unsupported current-RSS platforms conservatively use process peak RSS. No universal under-8-GB or full-tier guarantee is claimed.

The worker checks free disk and observed temporary files before writes, reserves metadata overhead and configures DuckDB spill below the overall temporary allowance. Parquet is written one temporary part at a time, fsynced, and renamed. Finished Parquet, the durable DuckDB database/WAL, ledgers and source logs are persistent data rather than temporary spill; they need sufficient permanent disk space. Disk-full, temporary-budget and memory errors produce a failed job and leave its last checkpoint recoverable. A hard filesystem failure can prevent even error-state persistence; the API then identifies an interrupted worker and local `worker.log` is the diagnostic fallback.

## Output layout and provenance

```text
data/jobs/JOB_ID/
  job.json
  checkpoint.json
  dispatch.json
  worker.log
  validation.jsonl
  killchain.duckdb
  spill/
  events/date=2026-10-31/part-00000000.parquet
  events/date=unknown/part-00000001.parquet
```

Only the needed date partitions exist. Partition date derives from the approved normalized UTC timestamp, never the laptop timezone. Missing/invalid/offset-free timestamps use `date=unknown` and retain their contract uncertainty. This directory key is storage metadata, not a new canonical field. Read individual parts with `pyarrow.parquet.ParquetFile` and bounded `iter_batches`; dataset readers must not pass an inferred partition column into the strict canonical event model.

Canonical Arrow/Parquet schema remains v1. Every accepted row preserves original file reference, full-file SHA-256, one-based record number, zero-based byte offset, byte length including any delimiter, raw-span SHA-256, source ID, schema/transform versions and a batch UUID corresponding to the job ID. Unknown source event types remain intact; optional absent fields are not invented. Raw evidence remains at the immutable original path. Parsed/re-serialized JSON is not a replacement for the source bytes.

The compact DuckDB catalog indexes source-record and normalization identities, locator, validation status and Parquet part. Exact repeated raw content at different byte locations is retained as separate source occurrences, as approved in v1. Resume does not append duplicates for already committed occurrences.

`records_accepted` includes partial records. `records_partial` is a subset, not an additional disjoint count. At a durable checkpoint, accepted + rejected = processed. The compact diagnostic ledger has `ledger_version=1.0.0` and `validator_version=1.0.0`; it is a job ledger, not the standalone canonical RecordValidation JSON shape. Every rejected or partial record gets a validation-ledger entry with issue codes, artifact/record locator, source/job/transform identity and raw digest. The ledger covers malformed JSON/encoding, wrong mapped types/IPs, timestamp uncertainty, oversized rows and budget rejections. Generic validator issues avoid echoing sensitive field values; see the original raw span for investigation. The UI shows the latest issue and counts; it does not claim semantic validity for unpromoted source fields.

## Job lifecycle and recovery

States: queued -> hashing -> running -> completed. Active jobs may become cancelling -> cancelled; failures become failed. If a known active PID no longer exists, status retrieval marks the job interrupted. Failed/cancelled/interrupted jobs can resume; completed jobs cannot. Job metadata records input identity, status, processed/accepted/partial/rejected counts, bytes, first/last start, completion, attempt number, accumulated elapsed time, last error and checkpoint.

One ownership-checked worker lock covers API and CLI dispatch. A short OS-backed management lock serializes cross-process metadata/lock transitions, while DuckDB has one writer. API threads read small manifests and remain responsive during normalization. Workers use a per-launch token handshake, including on Windows where a virtual-environment launcher PID may differ from the Python worker PID. The worker persists its actual PID once started. An unverifiable live/stale lock is treated conservatively rather than risking a second writer.

Checkpoint commit order:

1. Write bounded partition parts, fsync and rename them.
2. Commit compact index rows in one DuckDB transaction.
3. Flush/fsync validation ledger.
4. Atomically replace the checkpoint, then update job progress.

Checkpoint records include byte offset, physical-record number, accepted/partial/rejected totals, next part index, ledger length and source hash. Source hashing is streamed before ingest and again before completion. Only completed jobs are consumable datasets; failed/cancelled outputs are recovery artifacts. Resume rehashes the full original source and checks its size/mtime; changed input is refused. Use a new job for changed input.

Recovery rolls the index back to the last checkpoint, removes only uncheckpointed generated part files, truncates the validation ledger to its saved byte length, verifies existing Parquet footers/counts against the index/checkpoint, seeks to the saved offset and continues. Missing/truncated durable output causes explicit failure rather than silent success. This handles practical process interruption and the crash window after DB commit but before checkpoint publication. Original sources are never rewritten or deleted. Storage hardware/filesystem guarantees still apply; Windows has no equivalent portable directory-fsync guarantee.

Cancellation is cooperative, checked during hashing and between records. A pending bounded batch checkpoints before stopping. No force-kill or concurrent database write is used. A cancelled job with no checkpoint restarts its hashing phase. Failed-attempt UI counters can include uncommitted work; `checkpoint`/`resume_from` shows the durable position actually used during recovery.

## Tested behavior and limits

Automated tests use small existing synthetic excerpts and explicit validator mutations: valid/missing/unknown data, malformed timestamps/JSON/IPs, raw duplicates, multiple batches/row groups/date partitions, bounded oversized framing, memory/disk/temp failures, crash recovery, cancellation/resume, changed-source refusal, missing durable output, cross-thread reconciliation, worker token dispatch and API input/state boundaries. These assertions do not prove 15/30/50 GB capability.

A manual browser/API test uses the existing local 1 GiB file to exercise actual background start, cancellation and checkpoint resume. Its verified final result is recorded below; earlier out-of-phase prototype measurements are not Chunk 3 acceptance evidence. Docker execution is unverified because Docker is unavailable locally. Source formats, large-tier qualification, broad job scheduling, multiple simultaneous workers, uploads, detection, graph analysis and AI remain outside this phase.

## Local integration verification (2026-10-31)

The existing 1,073,742,861-byte source was started through the browser/API, interrupted by the initial Windows launcher handshake bug, recovered, cooperatively cancelled after 176,373 accepted records, and resumed to completion. Final checks found 1,284,111 processed/accepted records, zero partial/rejected records, exactly 1,284,111 distinct source-record IDs and catalog record numbers, and 1,284,111 Parquet rows across 884 parts. Row groups stayed at or below 1,024 rows. Nine sampled original byte spans matched both their digests and stored source JSON; the full source SHA-256 was rechecked unchanged. The worker lock was released. A local verification report is retained under ignored data/.

These are development ingestion/recovery checks on the local synthetic 1 GiB file, not full-tier benchmarks. Small-fixture tests additionally cover the final append-only catalog/buffer clamp, resource failures and corruption cases. No detection, attack-label accuracy or 15/30/50 GB qualification is claimed.

## Implementation file map

| Files | Change |
| --- | --- |
| `backend/app/ingestion.py` | Streaming framing, canonical validation, partition writes, durable checkpoints and recovery |
| `backend/app/job_store.py`, `backend/app/jobs.py` | Job manifests, guarded single-writer ownership, background dispatch and lifecycle |
| `backend/app/ingestion_routes.py`, `backend/app/main.py` | Source/job/validation APIs and integration with the existing health service |
| `backend/app/resources.py`, `backend/app/config.py`, `backend/app/storage.py` | Resource admission/measurement, configurable limits and existing disk-factory documentation |
| `backend/tests/test_ingestion.py` | Ingestion, failure, concurrency, recovery and API regression tests |
| `frontend/src/main.tsx`, `frontend/src/styles.css` | Source selection, progress, diagnostics, cancel/resume UI |
| `.env.example`, `compose.yaml` | Documented settings and read-only source mount |
| `README.md`, `docs/ingestion.md` | Startup, supported-source, storage/recovery workflow and verification |
| `docs/architecture.md`, `docs/data-contract.md`, `docs/problem-statement.md`, `docs/project-overview.md`, `docs/requirements.md`, `docs/roadmap.md` | Current phase/status and implementation boundaries |

The existing canonical Python models, versioned event/validation/Arrow schema artifacts, source fixtures, generator and frontend dependency manifest are unchanged.


Current raw/server extension: see [raw-log ingestion](raw-log-ingestion.md). The earlier synthetic-only statements describe the original v1 ingestion scope; explicit raw-text and combined-access profiles now use canonical v2.
