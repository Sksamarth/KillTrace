# KillChain AI — architecture report

## Scope and implemented foundation

Current extension: [evidence-linked investigations](investigations.md) adds a
separate local analysis worker over completed Parquet, a derived disk-backed
SQLite observation/incident index, safe YAML rule parameters, bounded NetworkX
incident slices and investigation APIs/UI. Bulk events remain in Parquet/DuckDB.
The graph shows associations, not proven causal movement. Earlier Chunk 3 scope
statements below describe that delivery; complete attack reconstruction,
contextual reachability and AI remain future work.

The foundation exposed `GET /api/health`, OpenAPI and a React shell; Chunk 3 extends them with local ingestion job APIs and an ingestion interface. Pydantic validates storage resource settings. A tested factory opens an on-disk DuckDB database without creating any application tables. Docker Compose defines loopback-only frontend/backend services and persistent storage. Detection and analysis dependencies are installed but unused. Chunk 2 adds a versioned source-specific contract derived from an inspected synthetic SimEDR JSONL file; no undisclosed source schema is assumed.

## Proposed processing architecture

```text
Authorized sources -> adapter/schema discovery -> bounded Arrow batches
    -> partitioned Parquet + source provenance -> single DuckDB processing worker
    -> evidence-linked detections -> windowed correlation -> bounded graph slices
    -> paginated FastAPI responses -> Cytoscape.js / Recharts
                                      |
                        opt-in evidence summary via Gemini
```

Chunk 3 adds the single local ingestion worker, checkpoint/job metadata, canonical Parquet output and compact catalog to the foundation API/UI. Detection and other analysis stages remain future work. Start with a single local worker rather than distributed infrastructure on an 8 GB laptop. Keep expensive jobs outside API requests; later persist job states, checkpoints, cancellation and recovery. One process owns database writes. Do not let independent worker/API processes write the same DuckDB file. The API will read published immutable artifacts or communicate through the worker.

## Dataset contract and source adapters

Before ingestion, inspect authorized representative samples, formats, encodings, timestamp/timezone semantics, entity identifiers, data sensitivity, and source provenance. Define source-specific adapters and a versioned canonical contract from that evidence. Missing fields and ambiguous times must be recorded rather than invented. Preserve evidence references and transformation versions. Chunk 2 provides the synthetic SimEDR v1 contract; Chunk 3 adds bounded offline ingestion and local job APIs/UI. The raw-log extension adds v2 profiles for UTF-8 text, combined access logs, quoted key=value records and generic JSON objects, plus streaming JSONL conversion. The supplied FireX file was inspected as key=value text; unknown entity semantics remain unpromoted. See [current adapters and mappings](raw-log-ingestion.md), [data contract](data-contract.md) and [dataset analysis](dataset-analysis.md). Uploads and binary/compressed decoding remain future work.

## Resource strategy for Ryzen 5 / 8 GB / no GPU

- Start DuckDB at 1 GB buffer budget and two threads; spill to disk with a 10 GB temporary-space ceiling. The connection factory disables external access and insertion-order preservation. Trusted adapter code will own file I/O; SQL queries may not open arbitrary files.
- DuckDB's memory setting is not a process-wide RSS ceiling. Python, Arrow, query operators, and NetworkX require additional memory. Compose caps the backend at 2 GB; tune this after measurement. No dataset-size support or throughput is claimed.
- Chunk 3 ingestion iterates Arrow batches with both byte and row limits, caps individual record size and writes bounded partitioned Parquet row groups. Do not load full datasets into Pandas, Python lists, or a NetworkX graph.
- Correlation needs bounded time/entity windows, disk checkpoints, and explicit late-event handling. Persist global graph edges; load only limited incident subgraphs into NetworkX. Bound frontend nodes, edges, result pages and chart buckets before rendering.
- Proposed initial budgets: 1 GB DuckDB buffers, up to 512 MB worker Python/Arrow working set, up to 256 MB graph slice. These are design targets, not enforcement or measured results. Leave several GB for Windows, browser, editor and Docker overhead. Prefer local processes when Docker overhead is too high.
- Reject or pause work when disk space is insufficient. Quotas, admission controls, batch bounds, graph limits, and worker scheduling remain to be implemented and benchmarked. CPU-only operation needs no local model or GPU.

DuckDB documents both spill configuration and memory allocations outside its buffer manager: [configuration](https://duckdb.org/docs/stable/configuration/overview) and [out-of-memory guidance](https://duckdb.org/docs/stable/guides/performance/oom). Production memory behavior must be benchmarked under the intended query workload.

## Detection, mapping and graph integrity

Versioned YAML rules must use safe loading and a validated declarative schema. Every detection must reference source evidence and a tested condition. Define precision/false-positive evaluation before enabling any rule. ATT&CK technique IDs require a pinned catalog version; kill-chain stages remain a separate evidence-backed classification rather than a universal one-to-one mapping.

Correlation edges must retain reason, timestamps, confidence and evidence. Observed progression and hypothetical future reachability must have distinct representations. Next-target assessments require actual asset, identity, permission and connectivity context; reachability does not establish compromise. NetworkX is for bounded incident slices, not the complete dataset.

## AI boundary

The Google Gen AI SDK is reserved, with no client initialization or network calls. Future Gemini integration must run server-side, require an explicit model choice and data-sharing policy, redact sensitive evidence, bound prompt sizes, timeouts, retries and cost, and validate structured responses. Treat log content as untrusted input. AI output must cite supplied evidence and disclose uncertainty; deterministic detection remains independently testable. Never send raw bulk datasets or trust generated attack claims without evidence.

## Delivery and operational limits

Vite proxies API traffic locally; Nginx does the same in Compose. This avoids a permissive CORS policy. No authentication or multi-user access exists. Before remote use, add authentication, authorization, TLS, audit events, secure uploads, retention and deletion policy. Container base tags and backend dependency ranges need controlled updates and vulnerability review before deployment; the local lock snapshot is not a cross-platform guarantee.

## Next design gates

1. Profile actual authorized samples; approve a versioned event contract and provenance model.
2. Build a bounded, checkpointable adapter and measure memory/disk use.
3. Validate a small set of real detection rules and independent ATT&CK/kill-chain mappings.
4. Add correlation, bounded graph API, and evidence drill-down.
5. Add contextual reachability and optional Gemini summaries.
6. Benchmark 15/30/50 GB targets only after functional correctness; report peak RSS, disk/spill, runtime, hardware and failure recovery.

## Chunk 3 implementation

The [ingestion worker](ingestion.md) uses the unchanged canonical contract and one source record at a time. Bounded Arrow batches write UTC-date-partitioned Parquet plus an append-only compact DuckDB locator catalog. There is no global unique/ART index growing with all source records. A single writer lock and short OS-backed management lock coordinate API/CLI jobs; the API itself reads small status manifests and launches one separate local worker.

Checkpoints follow fsynced Parquet, DuckDB transaction commit and ledger fsync. Resume verifies the immutable source, rolls back unfinished output, validates the durable prefix and continues at the saved offset. Cooperative cancellation and resource failures preserve recoverable checkpoints. The UI shows status, counts, diagnostics and checkpoint scope. Actual configuration and filesystem limits are documented in ingestion.md.

Earlier sections describe the long-term analysis architecture. Detection, ATT&CK labeling, correlation, graphs, next-target analysis and Gemini are not implemented in Chunk 3. Larger-tier scalability remains unqualified.
