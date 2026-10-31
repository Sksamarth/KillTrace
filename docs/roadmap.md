# Delivery roadmap

1. **Foundation (Chunk 1):** health API, React shell, disk-backed connection factory, resource settings, tests and Compose. No analysis capability.
2. **Data contract (synthetic source complete):** generated and fully inspected the user-requested 1 GiB SimEDR JSONL test file. [Canonical v1](data-contract.md), source mappings, provenance, Arrow/Parquet layout and validation tests cover this observed synthetic source. Real organizer/5 GB data remains a separate inspection gate.
3. **Ingestion:** bounded Arrow/Parquet pipeline, checkpoints and measured memory/disk failure behavior.
4. **Detection:** validated YAML rules with evidence and false-positive tests; versioned ATT&CK and separate kill-chain mapping.
5. **Correlation and graphs:** time/entity windows, provenance edges, paginated APIs, capped NetworkX/Cytoscape slices.
6. **Reachability and AI:** contextual next-target hypotheses and optional server-side Gemini evidence summaries.
7. **Hardening and evaluation:** access controls, retention, recovery and measured 15/30/50 GB benchmarks. No scale claim before measurement.
