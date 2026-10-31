# KillTrace

**Trace the Attack. Break the Chain.**

A Cyber Kill Chain and Attack Path Analysis Platform.

> **Status: planning and repository initialization.** This repository contains documentation and directory scaffolding only. No application, detection engine, visualization, or processing capability is implemented.

## Problem statement

Security logs contain large volumes of isolated signals. Concealed attacks can span hosts, users, IP addresses, and long periods, making it difficult to connect individual alerts into a coherent incident.

KillTrace aims to reconstruct a unified attack narrative that explains where an attack began, what the attacker did, how it progressed across systems, which hosts and users were affected, and which systems or resources could be reachable next.

### Motivating use case: INC-01 — 2013 Retail Data Breach

A stolen third-party vendor credential, followed by weeks of ignored security alerts, contributed to a major retail breach affecting up to 110 million customers.

This motivating incident illustrates why analysts need correlated evidence, visibility across attack stages, and early detection. It is context for the project, not a claim that KillTrace could have prevented the incident. No incident dataset is included.

## Proposed solution and objectives

The proposed platform will turn security events into evidence-linked timelines and attack graphs. Its three core functional requirements are:

| Objective | Planned behavior |
| --- | --- |
| **A. Detect and Label** | Identify suspicious log events, map relevant MITRE ATT&CK techniques, and associate Cyber Kill Chain stages. |
| **B. Connect the Steps** | Correlate hosts, users, IP addresses, and timestamps into unified attack paths, while keeping memory consumption bounded during large-scale processing. |
| **C. Explain and Look Ahead** | Provide interactive timelines and host/user attack graphs, and identify potential future paths and reachable resources. |

All three objectives are planned. See [requirements](docs/requirements.md) for scope and future validation criteria.

## Target data scales

| Dataset size | Status |
| --- | --- |
| 15 GB | Future processing goal; unimplemented and unbenchmarked |
| 30 GB | Future processing goal; unimplemented and unbenchmarked |
| 50 GB | Future processing goal; unimplemented and unbenchmarked |

These are dataset-size targets, not memory budgets, throughput guarantees, or demonstrated capabilities. Hardware, formats, execution time, and peak memory will need to be defined and measured.

## Cyber Kill Chain overview

The [Lockheed Martin Cyber Kill Chain](https://www.lockheedmartin.com/en-us/capabilities/cyber/cyber-kill-chain.html) describes seven stages: Reconnaissance, Weaponization, Delivery, Exploitation, Installation, Command and Control, and Actions on Objectives.

KillTrace plans to use these stages to organize an attack narrative. Evidence may cover only some stages; missing stages will remain unknown rather than being inferred as confirmed activity.

## MITRE ATT&CK integration

[MITRE ATT&CK](https://attack.mitre.org/resources/) describes observed adversary behaviors. Planned event enrichment will attach relevant technique identifiers and supporting evidence. ATT&CK technique mappings and kill chain stage labels will be maintained separately; they do not imply a universal one-to-one mapping. Coverage, mapping rules, and the ATT&CK version remain to be defined.

## Attack path analysis

Observed paths will connect related events through entities and time, preserving the underlying evidence. Potential future paths will depend on available asset, identity, permission, and connectivity context. They will be labeled as hypotheses with assumptions, distinct from observed attacker actions; reachability alone does not prove compromise.

## Expected system architecture

The following is a conceptual proposal; components and interfaces are not implemented.

```text
Security logs -> Incremental ingestion -> Normalization -> Detection and labeling
                                              |                    |
                                              v                    v
                                      Evidence storage <-> Event correlation
                                                                  |
Asset / identity / connectivity context ----------------> Attack path analysis
                                                                  |
                                                       Timelines and graphs
```

Incremental processing, bounded working sets, and persisted intermediate results are proposed approaches to managing memory. Storage, execution model, and deployment remain TBD. See [architecture](docs/architecture.md).

## Planned features

- Suspicious-event detection with evidence references.
- ATT&CK technique enrichment and kill chain stage labeling.
- Correlation across hosts, users, addresses, and timestamps.
- Unified attack narratives and interactive timelines.
- Attack graphs showing relationships between hosts and users.
- Potential next-step paths and reachable systems/resources with explicit assumptions.
- Evaluation at 15 GB, 30 GB, and 50 GB with measured memory and runtime.

## Technology stack

**TBD.** Languages, frameworks, databases, visualization libraries, infrastructure, and deployment tools have not been selected. No dependencies are installed or specified.

## Project roadmap

1. **Repository foundation (current):** establish documentation, MIT license, and directory structure.
2. **Scope and design (planned):** finalize log formats, event schema, evaluation criteria, architecture, and technology choices.
3. **Detection and correlation (planned):** implement ingestion, labeling, and evidence-linked reconstruction.
4. **Explanation and reachability (planned):** implement timelines, graphs, and contextual future-path analysis.
5. **Evaluation and presentation (planned):** benchmark target dataset sizes and document limits for a hackathon demonstration.

See the [roadmap](docs/roadmap.md) for milestone exit criteria. No application milestone is complete.

## Installation

Implementation is not yet available. There is no application to install or run and no build, dependency installation, or test command at this stage.

To browse the documentation locally:

```sh
git clone https://github.com/Sksamarth/KillTrace.git
cd KillTrace
```

## Repository structure

```text
KillTrace/
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── problem-statement.md
│   ├── project-overview.md
│   ├── requirements.md
│   ├── architecture.md
│   └── roadmap.md
├── src/
│   └── .gitkeep
├── tests/
│   └── .gitkeep
├── assets/
│   └── .gitkeep
└── sample-data/
    └── README.md
```

## Documentation

- [Problem statement](docs/problem-statement.md)
- [Project overview](docs/project-overview.md)
- [Requirements](docs/requirements.md)
- [Proposed architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Sample-data policy](sample-data/README.md)

## License

Released under the [MIT License](LICENSE).
