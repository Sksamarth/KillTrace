# Master development phase checklist

Updated 31 October 2026 after receiving the seven-phase master prompt.
This checklist distinguishes historical deliveries from completion under the new
gates. No seven-phase completion is claimed.

## Phase 1 — verification complete

- [x] Read architecture, problem statement, project overview, requirements and roadmap.
- [x] Inspect backend/frontend, APIs, dependencies, storage/configuration and Compose.
- [x] Existing local backend responds: `/api/health` reports `ok`.
- [x] OpenAPI JSON loads and `/docs` returns HTTP 200.
- [x] Local Vite frontend responds with HTTP 200.
- [x] TypeScript checking and Vite production build pass.
- [x] Full current backend suite: **104 passed**, one existing Starlette/httpx deprecation warning.
- [x] Tests exercise disk-backed DuckDB settings/persistence and invalid resource configuration.
- [x] `pip check`: no broken requirements.
- [x] Inspect Git: existing `origin` repository, branch `main`; no history rewrite or forced push.
- [x] Docker Desktop installed and the official hello-world container passed.
- [x] Compose images built and both services reached healthy state.
- [x] Backend health and frontend API proxy return `ok`; frontend and API docs return HTTP 200.
- [x] DuckDB connection and dependency checks inside the Linux backend container.

Docker Desktop 4.97.0, Engine 29.9.2 and Compose v5.6.1 use WSL 2.
Virtual disks were verified under `E:\DockerData`. The isolated verification
project is `killchain-foundation-check`, using loopback backend port 18000 and
frontend port 18080 to preserve existing local development servers. Generated
Compose configuration and installer artifacts remain ignored under data/.
An initial startup command timed out before the engine became ready; after a
later engine stop, Desktop was restarted and both services passed fresh HTTP
checks. This verifies startup, not long-running reliability or dataset scale.

The restricted environment initially reported approximately 144 MiB free on C:.
An unrestricted host check showed approximately 119 GiB free; the earlier reading
must not be treated as the host disk capacity. E: had approximately 70 GiB free. Tests used a fresh
ignored `data/` test directory on E: after the system temporary directory failed
the configured free-space reserve. No existing files were deleted. Docker's WSL
and image storage was explicitly placed on E: during per-user installation.

The Docker dependency gate is resolved by actual runtime verification. The Phase 1
verification report is committed/pushed separately from the preserved analysis
draft before the Phase 2 contract audit begins.

## Preserved work and subsequent gates

Previously pushed foundation/data-contract/ingestion work remains intact:

- Foundation history: `8aef048` and subsequent documentation changes.
- Synthetic source/contract: `a599d2e`.
- Bounded ingestion: `d84bdf4`.
- Raw/server profiles and JSONL utility: `c67953e`.
- Measurement harness/report: `c48464c` (last pushed implementation commit when
  this verification started).

The investigation code developed before the master prompt arrived is preserved
as an **uncommitted draft**, not claimed as a completed master-prompt phase. Its
tests/build pass, but the draft combines initial detection and correlation work
and needs to be reconciled with the newly required separate phase commits. Do not
delete it or commit it as Phase 1 foundation work. Local synthetic findings are
not organizer ground truth; no full causal attack reconstruction is established.

- [x] Phase 2: preserve v1/v2; add explicit FireX canonical 2.1.0 definitions,
  published schemas, field mappings, malformed/missing/duplicate tests and actual
  1,000-record sample validation. Full workspace regression: 108 passed. Ingestion
  wiring of the new profile belongs to Phase 3, not this contract change.
- [x] Phase 3: wire the explicit FireX profile into API/CLI, schema metadata and
  Arrow reading; preserve all existing profiles and checkpoint behavior. Full
  workspace suite: 109 passed. Actual 1,000-record sample accepted completely,
  schema 2.1.0 Parquet, zero validation issues (job 51abb13d55704144b60ad3a23406c081).
- [ ] Phase 4: complete full rule metadata, versioned ATT&CK catalog, mapping explanations,
  detection filters/dashboard and evaluation cases; commit before Phase 5.
- [ ] Phase 5: complete incident/edge contracts and interactive graph/timeline requirements;
  preserve observed/inferred distinctions and bounded responses; commit before Phase 6.
- [ ] Phase 6: implement contextual reachability only with actual context, plus optional
  bounded/redacted Gemini reports. No permissions, topology or credentials are fabricated.
- [ ] Phase 7: hardening, benchmark report and evaluation of actual supported capabilities.

15/30/50 GB tiers, real-world accuracy, causal paths, contextual next targets and
Gemini reports are not verified. The existing local sample measurements do not
satisfy those gates. No CI/CD pipeline was added.
