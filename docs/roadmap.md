# Delivery roadmap

1. **Foundation (Chunk 1):** health API, React shell, disk-backed connection factory, resource settings, tests and Compose. No analysis capability.
2. **Data contract (synthetic source complete):** generated and fully inspected the user-requested 1 GiB SimEDR JSONL test file. [Canonical v1](data-contract.md), source mappings, provenance, Arrow/Parquet layout and validation tests cover this observed synthetic source. Real organizer/5 GB data remains a separate inspection gate.
3. **Ingestion (Chunk 3 implemented):** bounded canonical Arrow batches, date-partitioned Parquet, single-worker job APIs/UI, resource checks, validation ledgers, cooperative cancellation and checkpoint rollback/resume. Small-fixture and local 1 GiB checks are separate from unverified 15/30/50 GB qualification. See [ingestion](ingestion.md).
4. **Detection (initial implementation):** four tested rule kinds with configurable YAML thresholds, provenance, explicit ATT&CK hypotheses and unknown Kill Chain stages when evidence is insufficient. Ground-truth accuracy and broader coverage remain open.
5. **Correlation and graphs (initial implementation):** bounded scoped actor/time correlation, paginated incident APIs, NetworkX association slices and an SVG timeline/graph UI. Complete causal/cross-host reconstruction and Cytoscape interactions remain open. See [investigations](investigations.md).
6. **Reachability and AI:** contextual next-target hypotheses and optional server-side Gemini evidence summaries.
7. **Hardening and evaluation:** access controls, retention, recovery and measured 15/30/50 GB benchmarks. No scale claim before measurement.
