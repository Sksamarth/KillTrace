# Project overview

**KillChain AI — Trace the Attack. Break the Chain.**

A Cyber Kill Chain and Attack Path Analysis Platform, planned for a cybersecurity hackathon.

## Vision

Reconstruct concealed attacks from security logs into a unified narrative, with evidence for observed actions and explicit assumptions for possible next steps.

## Three objectives

1. **Detect and Label:** identify suspicious events and associate relevant MITRE ATT&CK techniques and Cyber Kill Chain stages.
2. **Connect the Steps:** correlate events across hosts, users, IP addresses, and timestamps into unified paths without excessive memory consumption.
3. **Explain and Look Ahead:** provide interactive timelines and graphs, and show potentially reachable systems and resources.

## Interpretation model

The Cyber Kill Chain will provide broad stage context. MITRE ATT&CK will provide behavioral technique context. These labels serve different purposes and will not be treated as interchangeable.

Observed events, inferred correlations, and potential future paths should remain distinguishable. Unknown stages or missing evidence should remain visible as uncertainty.

## Current repository contents

The current [investigation extension](investigations.md) adds evidence-based
rules, ATT&CK hypotheses, candidate-incident correlation and timeline/entity-graph
views on completed SimEDR/key-value ingestion jobs. Source alerts remain separate.
Raw/server ingestion and FireX compatibility are implemented. Ground-truth attack
accuracy, full causal paths, next-target context and larger-tier scaling remain open.

Foundation history: FastAPI health service, React/TypeScript shell, disk-backed
DuckDB factory, resource configuration, tests, Docker Compose and architecture
documentation. User-provided/generated logs remain local under ignored data/.

## Decisions still open

The stack is selected in the root README. Supported log formats, dataset schema, detection methods, correlation contracts, context sources, evaluation datasets, and performance thresholds remain open.

The 15 GB, 30 GB, and 50 GB scales are future evaluation targets. See [requirements](requirements.md) and [roadmap](roadmap.md).

## Chunk 3 status

Bounded ingestion, partitioned Parquet, validation ledgers and job start/status/list/cancel/resume APIs/UI are now implemented for the approved synthetic JSONL profile. Detection and attack analysis remain future work. See [ingestion](ingestion.md) for resource and recovery guarantees and their limits.
