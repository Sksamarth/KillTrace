# Evidence-linked investigations

KillChain AI now has an initial investigation workflow after ingestion. It reads
completed canonical Parquet directly; no intermediate JSONL export is required.
The result is a set of rule findings, conservatively correlated candidate
incidents, chronological timelines and bounded entity graphs. This is not yet
ground-truth-qualified reconstruction of complete causal attack chains.

## Use it

Start the backend/frontend as described in README. The latest completed ingestion
job is selected automatically. Select another completed job under Recent jobs if
needed. New direct scans automatically continue into analysis; for older completed
jobs click **Evaluate rules & build graph**, then select
an incident to inspect its timeline, graph and original evidence. Synthetic input
is visibly identified. Empty results are valid and are never replaced by demo
findings. Analysis supports completed SimEDR and key-value jobs. Other profiles
report zero supported observations rather than guessing field semantics.

CLI alternative:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python -m app.analysis --job-dir data/jobs/JOB_ID
```

The analysis writes status, the applied rules/hash, observations, detections and
incidents under the job's ignored `analysis/` directory. A completed analysis is
immutable. Failed/interrupted API analyses require a new ingestion job for retry
in this first implementation; checkpointed analysis resume and cancellation are
not implemented. Ingestion recovery remains unchanged. Do not run heavy ingestion
and analysis concurrently when measuring performance.

## Supported evidence and rules

| Source | Observation mapping |
| --- | --- |
| FireX-style quoted key/value | `devid`/`devname` is the reporting device; `srcip`/`dstip` are validated endpoints; `dstport` is range checked; `user` is a source-local account; canonical explicit-offset time determines ordering |
| FireX login | Only `type=event`, `action=login`, `status=failed` or `success` enables authentication rules; SSL-login outcomes are not inferred |
| FireX traffic | `type=traffic`, validated endpoints and destination ports enable port-diversity rules; allow/deny is not proof of compromise |
| SimEDR | Canonical authentication outcome, network endpoints, reporting host and process/parent names; `threat`, `rule` and synthetic detection labels do not trigger our rules |

Source-local identities are scoped by source ID and reporting device. An observer
is never relabelled as the destination machine. Unknown fields, invalid IPs,
missing accounts/devices or uncertain timestamps cannot satisfy rules requiring
them. Source-provided IPS/virus/SimEDR alert annotations are counted separately,
not automatically promoted to independently verified findings.

Rules live in `backend/rules/investigation.yaml`. Safe YAML loading and a strict
Pydantic config allow IDs, supported rule kinds, thresholds and windows only.
There is no executable YAML, SQL or arbitrary Sigma interpreter. Adding a new
algorithm still requires code/tests; thresholds and existing rule instances can
be configured without code. The complete config snapshot and SHA-256 are recorded.

| Rule | Default condition | ATT&CK hypothesis |
| --- | --- | --- |
| Repeated login failures | At least 10 failures for one observer/source IP/account in a fixed UTC-aligned 300-second bucket | T1110.001 Password Guessing / Credential Access |
| Login success after failures | A success with at least 10 preceding failures for the same scoped IP/account within 300 seconds (rolling lookback) | T1110.001 / Credential Access |
| Multiple destination ports | At least 20 distinct destination ports for one source/destination pair on the same observer in a fixed 60-second bucket | T1046 Network Service Discovery / Discovery |
| Office-spawned PowerShell | Recorded PowerShell process with Word, Excel or Outlook as parent | T1059.001 PowerShell / Execution |

Fixed buckets can miss bursts split across their boundaries. Port probing may be
an authorized scanner, login failures may be mistakes, and Office automation can
be legitimate. No false-positive/recall claims are made. Rules produce hypotheses
requiring analyst review, not confirmed attacker actions. A successful login does
not prove the prior failures caused it or that the account was compromised.

ATT&CK tactics and the Cyber Kill Chain are separate classifications. These
patterns do not establish a specific Kill Chain stage; `kill_chain_stage=null`
is displayed as undetermined. No arbitrary one-to-one mapping is fabricated.
Technique references checked 31 October 2026:
[T1110.001](https://attack.mitre.org/techniques/T1110/001/),
[T1046](https://attack.mitre.org/techniques/T1046/),
[T1059.001](https://attack.mitre.org/techniques/T1059/001/).
These selected IDs/names are a local mapping, not a complete synchronized ATT&CK catalog.

## Correlation, graph and provenance

Findings correlate only when scoped reporting device/source and actor match,
with at most a ten-minute gap and one hour from incident start. Shared account
names or IPs alone across observers are not merged. NAT, missing topology and
shared devices still limit attribution. Matched-observation counts may overlap
between rules; their sum is not a deduplicated raw-alert reduction metric.

The timeline orders findings by start/end time. NetworkX builds only the first
100 findings' graph at request time. Nodes represent actors, involved target
addresses, source-local accounts and reporting devices. Edges are evidence
associations (`involved_in`/`reported_by`), explicitly not confirmed lateral
movement or causal edges. The Cytoscape view displays at most 100 entities and
300 edges with pan/zoom, node dragging and inspection. Graph rendering loads only
when needed. A separate first-50-network-record snapshot is available even without
detections; it is labelled as logged associations, not a confirmed attack path.

Each finding includes up to 50 original evidence locators, full matched count,
rule/version hash at the analysis level, original source hash/record/byte span,
transformation version and synthetic flag. The original-evidence endpoint reads
only a bounded span from the stored job's source path and verifies its SHA-256
before showing it. Missing/changed evidence returns a conflict. It does not permit
the caller to choose arbitrary filesystem paths. Complete observations remain
in the local analysis database; the first 50 locators are an explicit sample.

Next-target analysis returns unavailable because no permissions or connectivity
topology was supplied. It does not equate observed communication with access
rights. Gemini is not used in this implementation.

## Storage and resource decisions

Bulk normalized events remain in Parquet/DuckDB. A separate on-disk SQLite
investigation index provides built-in indexed grouping and lookup without a new
service or extra dependency. This is an initial derived index, not a migration of
the bulk event store to SQLite or an in-memory graph of every log. Its observation
rows store only analysis fields and provenance, not entire copied raw messages.

Arrow reads batches of 64 records; SQLite uses a 32 MiB page-cache budget and
file-backed temporary operations. Source ingestion resource checks run between
batches. An OS-backed writer lock permits one analysis worker per job store and
releases after a crash. Requests launch a separate process and poll small status
files; completed API reads use read-only database connections and bounded pages.
Indexes/SQL temporary operations and Python/Arrow allocations still need full-tier
disk/memory measurement. The SQLite cache is not a hard process memory cap, and
long SQL phases do not have cooperative cancellation yet.

## API

| Route | Purpose |
| --- | --- |
| `POST /api/investigations/{job_id}` | Launch analysis of a completed ingestion job |
| `GET /api/investigations/{job_id}` | Status, applied rules and counts |
| `GET /api/investigations/{job_id}/incidents?limit=20&offset=0` | Page candidate incidents (maximum 100) |
| `GET /api/investigations/{job_id}/incidents/{incident_id}/path` | Bounded chronological findings and graph |
| `GET /api/investigations/{job_id}/detections/{detection_id}/evidence/{index}` | Hash-verified original evidence (index 0–49) |

## Local checks

On 31 October 2026, 10,000 existing synthetic SimEDR records produced 105
telemetry-based findings in 24 candidate incidents; 503 source annotations were
counted separately. On 50,000 actual supplied FireX records, the four rules found
zero matches and counted 2,308 source-reported alerts. This is compatibility
evidence for those subsets, not planted-attack accuracy or a full-dataset result.
No findings were fabricated to populate the UI.

Tests exercise explicit synthetic failed-login/success sequences, port diversity,
negative source annotations, missing time, distinct observers, duplicate content,
process-parent conditions, unsafe configuration, immutable results, verified raw
evidence/tampering, paging and a real background API worker. Large-tier throughput,
precision/recall, full causal paths and next-target predictions remain unqualified.
