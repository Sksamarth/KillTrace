# Detection rules (planned)

YAML will be the rule authoring format. No rules ship in this phase.
Before implementation, define a versioned rule schema, safe YAML loading,
supported fields, evidence requirements, ATT&CK version, false-positive tests,
and separate kill-chain mappings. Never evaluate rule text as Python or SQL.
