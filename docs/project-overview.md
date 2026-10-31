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

FastAPI health service, React/TypeScript dashboard shell, a disk-backed DuckDB factory, resource configuration, tests, Docker Compose, and architecture documentation. No datasets or analysis features exist.

## Decisions still open

The stack is selected in the root README. Supported log formats, dataset schema, detection methods, correlation contracts, context sources, evaluation datasets, and performance thresholds remain open.

The 15 GB, 30 GB, and 50 GB scales are future evaluation targets. See [requirements](requirements.md) and [roadmap](roadmap.md).
