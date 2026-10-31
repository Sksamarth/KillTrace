# Direct original-file scan

Choose the original authorized local log and click **Start log scan**. No JSON
or JSONL conversion is needed. Automatic recognition inspects at most 32 physical
records / 256 KiB, then the existing worker reads the original file incrementally
and validates every record. FireX's observed key/value signature selects the typed
2.1.0 adapter. Formats are recognized from content, not filenames alone.

The worker writes the normal bounded Parquet/index artifacts needed for queries
and recovery. These internal stores are distinct from a separate conversion copy;
there is no required intermediate JSON/JSONL file. The earlier export utility
remains optional and is not invoked by Scan.

Detection and graph preparation are requested with the scan and run in the worker
after successful ingestion. The request is persisted with the job, so closing or
refreshing the interface does not prevent that processing. No automatic analysis
is retroactively added to existing jobs. Raw-text work already running is left
unchanged. Original evidence and checkpoints are preserved.

Unknown/mixed samples require an explicit inspected adapter. Recognized generic
JSON/key-value formats can preserve fields but may have no semantic detection
mapping; the interface says so. Synthetic SimEDR provenance requires explicit
confirmation. Format recognition is not a statement that the whole file is valid
or that any event represents an attack. The advanced override remains available
for deliberate message-preservation workflows; it is no longer the default.

The read-only scan console shows the actual parser, byte offsets, records,
accepted/partial/rejected counts, elapsed time and durable checkpoint. The bar
advances at worker checkpoints; rule evaluation/correlation show separate stages.
Average rate is that job's counters divided by elapsed time, not a performance
qualification or an ETA guarantee.

Cytoscape provides bounded graph pan/zoom, fit, node dragging and selection, with
evidence drilldown for incident edges. A scan without findings can show the first
50 mapped network records as a separate observed-log graph. Logged endpoints do
not establish successful connections, access rights or compromise. No synthetic
graph is substituted for empty results. Incident source annotations remain
separate from deterministic findings; full attack accuracy remains unverified.

Current runtime is the Tauri development shell or local web workflow. A complete
packaged backend/Windows installer remains future work, as recorded in
desktop-architecture.md. This change does not claim completion of all desktop
master-prompt phases. The earlier investigation draft is now part of this initial
direct scanning workflow; broader rule/catalog/incident contracts remain partial.

Checks: full backend suite, frontend build and scan-progress/proxy security tests;
a real background-worker fixture proves original-file ingestion automatically
continues into detection and graphs without a frontend-triggered second step.
Live console/graph rendering and graph selection were checked on existing local
jobs. All bulk logs, outputs and screenshots remain excluded from Git.
