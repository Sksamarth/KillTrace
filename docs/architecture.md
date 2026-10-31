# Proposed architecture

**Design status:** conceptual only. No component, interface, storage engine, or deployment environment is implemented or selected.

## Expected data flow

```text
Security logs
    |
    v
Incremental ingestion -> Normalization -> Detection and labeling
                            |                     |
                            v                     v
                    Evidence storage <-> Event correlation
                                                  |
Asset / identity / permission / connectivity ------+
context                                           v
                                        Attack path analysis
                                                  |
                                                  v
                                     Interactive timelines and graphs
```

## Proposed responsibilities

| Component | Intended responsibility |
| --- | --- |
| Ingestion | Read authorized logs incrementally; retain source references. |
| Normalization | Represent timestamps and host, user, and IP entities consistently; retain original evidence. |
| Detection and labeling | Identify suspicious events and attach supported ATT&CK technique and kill chain stage labels. |
| Evidence storage | Persist normalized events, provenance, and intermediate results for later retrieval. |
| Correlation | Connect relevant events using entities, time, and supporting evidence. |
| Attack path analysis | Reconstruct observed progression and assess possible next paths using available environmental context. |
| Presentation | Explain evidence and uncertainty through timelines and host/user graphs. |

## Memory and scale goals

The design will investigate incremental reads, bounded working sets, partitioned correlation, and persisted intermediate state instead of requiring an entire dataset in memory. These are proposals to evaluate, not implemented performance optimizations.

Benchmarks are planned for 15 GB, 30 GB, and 50 GB datasets. Resource limits and deployment assumptions must be set before claiming those scales are supported.

## Evidence and uncertainty

Relationships should retain references to their supporting events. Proposed future paths additionally require asset, identity, permission, or connectivity context. Missing context must be disclosed; reachability must not be displayed as confirmed compromise.

## Open design decisions

All technology choices remain **TBD**, including language, parsing formats, event schema, detection strategy, correlation windows, persistence, graph representation, visualization, and deployment. No package manifests or application code are part of initialization.
