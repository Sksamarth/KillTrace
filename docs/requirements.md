# Requirements

**Status:** all functional requirements below are planned and unimplemented. Validation criteria describe future work; foundation tests exist; no analysis benchmarks exist.

## A. Detect and Label

- Identify suspicious events in security logs.
- Map events to relevant MITRE ATT&CK techniques.
- Associate events with corresponding Cyber Kill Chain stages.
- Preserve supporting evidence and permit unmapped or uncertain labels.

Future validation: use an authorized, annotated dataset to compare detections and labels with expected outcomes; report false positives, missed events, mapping coverage, and the ATT&CK version used. Thresholds are TBD.

## B. Connect the Steps

- Correlate events across multiple hosts, users, IP addresses, and timestamps.
- Reconstruct individual events into a unified attack path.
- Retain evidence references for relationships and distinguish correlation from confirmed causation.
- Support large-scale processing without excessive memory consumption.

Future validation: evaluate reconstruction against annotated scenarios, including unrelated events and incomplete evidence. Measure peak memory and runtime while processing each target dataset size. Memory budgets, timestamp handling, and accuracy thresholds are TBD.

## C. Explain and Look Ahead

- Present reconstructed attacks through interactive timelines.
- Visualize host and user relationships in attack graphs.
- Identify potential future attack paths.
- Show which systems and resources an attacker could potentially reach next.
- Separate observed activity from potential paths and expose evidence, assumptions, and missing context.

Future validation: verify that an analyst can trace displayed actions to source evidence and inspect the context underlying each reachability hypothesis. Define suitable asset, identity, permission, and connectivity inputs before evaluating this functionality.

## Target processing scales

| Dataset size | Purpose | Present capability |
| --- | --- | --- |
| 15 GB | Planned evaluation target | Not implemented or benchmarked |
| 30 GB | Planned evaluation target | Not implemented or benchmarked |
| 50 GB | Planned evaluation target | Not implemented or benchmarked |

No throughput, completion time, hardware configuration, or memory ceiling is promised. Future measurements must record dataset format and provenance, event counts, hardware, runtime, peak memory, and output quality. Dataset size alone does not establish scalability.

## Chunk 1 boundaries

- Deliver a runnable backend/frontend foundation and architecture report using the selected stack.
- Do not assume log schemas, generate fake detections or implement analysis features.
- Keep credentials and datasets out of Git.
- Design for disk-backed processing and bounded memory on an 8 GB laptop.
- Treat analysis features and dataset-size goals as future work until validated.
