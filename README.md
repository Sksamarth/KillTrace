# KillChain AI

A local cybersecurity platform being built in phases. **Chunk 3 delivers bounded ingestion and validation only.** Detection, MITRE ATT&CK mapping, correlation, graphs, predictions and Gemini remain future phases. No security outcome or large-tier benchmark is claimed.

Stack: Python 3.11+, FastAPI/Pydantic, DuckDB, PyArrow/Parquet; React/TypeScript/Vite/Tailwind. Planned analysis libraries remain reserved dependencies. Designed for a single local worker on an 8 GB CPU-only laptop.

## Start locally (PowerShell)

From the repository root, with Python 3.11+ and Node 22.12+:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
# Copy only if you do not already have a local .env.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --env-file .env
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

If the laptop's `npm` resolves to a broken older user installation, use the working Node installation explicitly, for example `& 'C:\Program Files\nodejs\npm.cmd' run dev` in the frontend directory.

Open http://localhost:5173. API docs: http://localhost:8000/docs. In the ingestion page, select a source format and local file, acknowledge authorization and start a job. For `firex-10G.log`, choose **Quoted key=value logs**. The worker runs in a separate local process; the UI shows accepted/rejected counts, validation issues, checkpoints, cancellation and resume.

The default source root is `data/`; override `KILLCHAIN_INGESTION_INPUT_DIR` for another authorized local directory. Input paths are relative to that root. Absolute paths, traversal and resolved paths outside it are rejected. No uploads or network log readers exist. Explicit profiles support raw UTF-8 text, quoted key=value logs (including the supplied FireX file), generic JSON objects, standard combined access logs and existing synthetic SimEDR JSONL. Select the format explicitly; unknown fields are preserved without guessed entity mappings. See docs/raw-log-ingestion.md.

If the existing generated sample is missing, the previously supplied generator can create it:

```powershell
.\.venv\Scripts\python scripts/generate_sample.py
```

It refuses to overwrite files and targets 1 GiB, completing the final whole record. All rows are synthetic, including baseline rows without labels. Existing simulated source annotations are preserved without interpreting them as KillChain detections. The logfile and manifests stay outside Git under ignored `data/`.

## Ingest from the CLI

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python -m app.ingestion --source simedr-1gib.jsonl
.\.venv\Scripts\python -m app.ingestion --source firex-10G.log --profile key-value-1.0.0
.\.venv\Scripts\python -m app.ingestion --resume JOB_ID
```

CLI reads the local `.env`; source references are relative to the configured input root. It uses the same single-writer lock and recovery as API jobs. Interrupted/failed/cancelled jobs can resume; completed jobs cannot. A changed original source is refused on resume. Checkpoint recovery retains committed records and rolls back unfinished batches, not original logs.

## Docker Compose

Docker Engine/Compose required; execution is not verified on this development machine.

```sh
docker compose up --build
```

Open http://localhost:8080. Host `data/` is mounted read-only at `/inputs`; job outputs persist in named `/data`. Ports bind to loopback. The backend remains non-root. API and worker share a 2 GB container cap, with the worker's own lower memory admission budget. Local and Compose output stores are separate.

## Resource defaults and output

`.env.example` exposes batch rows (4,096), payload estimate (8 MiB), row groups (1,024), worker RSS admission (768 MiB), temporary disk (64 MiB), free-space reserve (256 MiB), input root and existing DuckDB settings. Batches flush on the first row/byte limit. Worker DuckDB buffers are additionally clamped to half the admission budget; spill is clamped to leave room for a pending part. These are bounded working sets and cooperative checks, not a guarantee against every transient allocation or OS kill.

Each job stores `job.json`, a durable `checkpoint.json`, validation ledger, compact append-only DuckDB catalog and canonical parts under `data/jobs/JOB_ID/events/date=YYYY-MM-DD/`. Uncertain timestamps use `date=unknown`. SimEDR uses unchanged canonical v1; new profiles use v2 with the same Arrow columns. Original raw file references, byte spans, digests, source/batch/schema/transform versions remain intact. Identical raw content at distinct byte locations is retained as separate occurrences. No complete dataset is loaded into Pandas or Python lists.

See [ingestion workflow, settings, lifecycle and recovery](docs/ingestion.md) for exact limits, errors and filesystem caveats. Large-tier 15/30/50 GB support remains unverified; small tests and the local 1 GiB exercise do not establish that qualification.

## API

| Route | Purpose |
| --- | --- |
| `GET /api/health` | Process liveness |
| `GET /api/ingestion/sources` | Supported local source list/configuration |
| `POST /api/ingestion/jobs` | Start background ingestion (202) |
| `GET /api/ingestion/jobs` | List jobs |
| `GET /api/ingestion/jobs/{id}` | Status, counts, errors and checkpoint |
| `GET /api/ingestion/jobs/{id}/validation` | Bounded durable diagnostic pages |
| `POST /api/ingestion/jobs/{id}/cancel` | Request cooperative cancellation |
| `POST /api/ingestion/jobs/{id}/resume` | Resume recoverable work |

Start body: `{"source":"simedr-1gib.jsonl","source_profile":"simedr-json-1.0.0","synthetic":true}`. Add `source_id` to set a stable processing source identity. Unknown sources/jobs return 404, invalid bodies 422, unsafe paths 400, and worker/state conflicts 409. Normal requests do not wait for bulk processing.

## Checks

See [measured ingestion baseline and profiling instructions](docs/ingestion-performance.md)
for the FireX sample timings and recommended optimization experiments.

```powershell
.\.venv\Scripts\python -m pytest -c backend/pytest.ini backend/tests
.\.venv\Scripts\python -m pip check
npm --prefix frontend run build
```

Tests cover contract validation, streaming, multiple batches, resource failures, cancellation, crash rollback, resume integrity and API behavior using small explicitly synthetic fixtures. They do not prove larger-tier performance. CI checks Python 3.11/3.14 and Node 22. Backend ranges and the development lock snapshot are retained; the latter is not a cross-platform guarantee.

## Documentation and handling

[Architecture](docs/architecture.md) · [Ingestion](docs/ingestion.md) · [Data contract](docs/data-contract.md) · [Dataset analysis](docs/dataset-analysis.md) · [Mappings](docs/field-mappings.md) · [Roadmap](docs/roadmap.md)

Never commit `.env`, keys, passwords, bulk datasets or private logs. No key is required; AI calls remain absent. This is a loopback-only local tool with no authentication or remote deployment. The repository remains named KillTrace; the product is KillChain AI.

[MIT License](LICENSE).


See [raw-log ingestion and JSONL conversion](docs/raw-log-ingestion.md) for supported profiles, field mappings and limits.


For the supplied FireX file, select **Quoted key=value logs** and `firex-10G.log` in the UI. To export easy-to-query JSONL independently, use `PYTHONPATH=backend python -m app.convert_logs data/firex-10G.log data/firex-10G.converted.jsonl --profile key-value`. Original data and converted exports remain excluded from Git. This file is 6,543,120,032 bytes; its name is not a size measurement.
