# Master development phase checklist

Updated 31 October 2026 after receiving the seven-phase master prompt.
This checklist distinguishes historical deliveries from completion under the new
gates. No seven-phase completion is claimed.

## Phase 1 — verification in progress, blocked on Docker

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
- [ ] Docker Compose service startup: **blocked**. No `docker` command is available,
  and Docker Desktop/CLI are absent from their standard installation locations.
- [ ] Complete Phase 1 and verify its completion commit remotely before advancing.

Additional environment constraint: the system C: drive had approximately 144 MiB
free during verification. E: had approximately 70 GiB free. Tests used a fresh
ignored `data/` test directory on E: after the system temporary directory failed
the configured free-space reserve. No existing files were deleted. Docker's image,
WSL and temporary storage placement needs available disk space; do not blindly
install it onto the nearly full system drive.

The master prompt requires Compose startup verification and says to stop at
missing dependencies. Resume after Docker Engine/Compose is available and running,
or after an explicit user revision permitting local-only Phase 1 with Docker
verification deferred. Static Compose inspection is not a successful runtime test.

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

- [ ] Phase 2: audit existing v1/v2 artifacts and mappings against all new contract requirements.
- [ ] Phase 3: verify existing ingestion against the audited contract and commit its gate evidence.
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
