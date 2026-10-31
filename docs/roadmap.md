# Delivery roadmap

1. **Foundation (Chunk 1):** health API, React shell, disk-backed connection factory, resource settings, tests and Compose. No analysis capability.
2. **Data contract:** inspect real authorized samples; document schemas, timestamps, provenance and validation before building adapters.
3. **Ingestion:** bounded Arrow/Parquet pipeline, checkpoints and measured memory/disk failure behavior.
4. **Detection:** validated YAML rules with evidence and false-positive tests; versioned ATT&CK and separate kill-chain mapping.
5. **Correlation and graphs:** time/entity windows, provenance edges, paginated APIs, capped NetworkX/Cytoscape slices.
6. **Reachability and AI:** contextual next-target hypotheses and optional server-side Gemini evidence summaries.
7. **Hardening and evaluation:** access controls, retention, recovery and measured 15/30/50 GB benchmarks. No scale claim before measurement.
