# KillChain AI

Trace the attack. Break the chain.

A cybersecurity platform foundation for evidence-backed log analysis, MITRE ATT&CK and Cyber Kill Chain mapping, incident correlation, attack reconstruction, and contextual next-target assessment.

**Chunk 1 status:** runnable health API and React shell, resource configuration, disk-backed storage factory, tests, and Docker Compose. Log ingestion, detections, mappings, correlation, graphs, predictions, and Gemini calls are not implemented. No dataset schema or synthetic detections are supplied.

## Stack

Python 3.11+, FastAPI, Pydantic; DuckDB, PyArrow and Parquet; Python/YAML rules; NetworkX; React, TypeScript, Vite, Tailwind CSS, Cytoscape.js and Recharts; Google Gemini API; Docker Compose. Analysis and AI libraries are dependencies reserved for later phases.

## Run locally

Use Python 3.11+ and Node 22.12+ (Node 22 LTS recommended). From the repository root, create a virtual environment and install backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --env-file .env
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8000. API docs: http://localhost:8000/docs. The health endpoint reports process liveness only. Gemini credentials are optional and unused; never put credentials in frontend variables.

## Docker Compose

```sh
docker compose up --build
```

Open http://localhost:8080. Ports bind to loopback. The backend runs as a non-root user with one API process. A named volume persists analysis storage; it is currently empty because the API does not open a database. Compose reads optional resource overrides from `.env`. The Gemini key is deliberately not passed to containers until integration exists. Container execution requires a Docker Engine/Compose installation and has not been verified in the current development environment.

## Checks

```powershell
.\.venv\Scripts\python -m pytest -c backend/pytest.ini backend/tests
cd frontend
npm run build
```

Backend dependency ranges are declared in requirements files; `backend/requirements.lock.txt` captures the versions tested on the development Python interpreter. Re-resolve for the target platform/Python before deployment. Frontend versions are pinned transitively by `package-lock.json`.

## Structure

- `backend/app/`: health API, validated configuration, schema-free DuckDB factory.
- `backend/tests/`: API and storage configuration/persistence checks.
- `frontend/`: responsive UI shell, same-origin API requests, build configuration.
- `rules/`: rule design policy; no detection content.
- `docs/architecture.md`: architecture report, memory budgets, risks and phase boundaries.
- `docs/roadmap.md`: incremental delivery gates.
- `sample-data/`: data policy only. Runtime data belongs in ignored `data/`.

The historical `src/`, `tests/`, and `assets/` directories are reserved scaffolding. The GitHub repository remains named KillTrace; the product is KillChain AI. Historical planning documents describe intent, not implemented capabilities; this README and architecture report define current status.

## Data and security

Do not commit real logs, datasets, `.env`, API keys, or private configuration. No upload, authentication, or remote deployment interface exists yet. Keep this foundation local until authorization, tenant isolation, upload limits, and audit controls are implemented. AI will summarize evidence only after explicit data handling controls are designed; it must never invent detections or treat untrusted log text as instructions.

## License

[MIT](LICENSE).

## Chunk 2 - synthetic dataset and data contract

A 1 GiB JSONL test file was generated locally from the user-supplied Mitigata SimEDR script and fully inspected. All rows are synthetic; supplied alert and ATT&CK tags are simulated source metadata, not detections produced by KillChain AI. The logfile, generation manifest and full profiling report are under ignored `data/` and are not committed. Only 21 small explicitly synthetic test excerpts are versioned.

- [Dataset analysis](docs/dataset-analysis.md): full-file findings, field inventory and limitations.
- [Canonical v1 contract](docs/data-contract.md): provenance, uncertainty, validation and memory limits.
- [Source mappings](docs/field-mappings.md): all observed paths, including unpromoted source fields.
- [Versioned schema artifacts](schemas/README.md): JSON Schema and explicit Arrow/Parquet layout.

The Python contract validates one bounded record and supports fixture-scale Parquet round trips. No bulk ingestion pipeline or detection engine is implemented. Optional CEF/syslog/HTTP output from the pasted script was not generated or validated. A future organizer/5 GB sample needs independent inspection before reuse of this profile.

To create another local 1 GiB synthetic file (the generator refuses to overwrite existing files):

```powershell
.\.venv\Scripts\python scripts/generate_sample.py --output data/another-simedr-1gib.jsonl
.\.venv\Scripts\python scripts/profile_sample.py data/another-simedr-1gib.jsonl --report data/another-simedr-1gib.profile.json
```

The byte target is 1,073,741,824; generation finishes the last complete record, so actual size can exceed it slightly. The seed controls random choices, not UUIDs/timestamps. Inspection uses capped per-record reads and disk-backed duplicate indexes. Run the existing backend test command above; see the contract for schema-artifact export instructions.
