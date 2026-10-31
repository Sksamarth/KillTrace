# Requirements

**Status:** all functional requirements below are planned and unimplemented. Validation criteria describe future work; no tests or benchmark results exist.

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

## Initialization constraints

- Document the project and create only the agreed directory scaffolding.
- Do not implement frontend, backend, ingestion, detection, or analysis code.
- Do not select a technology stack or install dependencies.
- Do not generate placeholder application code or fake sample logs.
- Do not describe planned functionality as delivered.
