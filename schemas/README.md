# Versioned security event schemas

The v1.0.0 contract is derived from the actual locally generated synthetic SimEDR JSONL file. It does not establish a schema for unprovided organizer sources.

- [Canonical event JSON Schema](v1/event.schema.json)
- [Validation outcome JSON Schema](v1/validation.schema.json)
- [Arrow/Parquet schema](v1/arrow-schema.txt)
- [Contract semantics](../docs/data-contract.md)
- [Source mappings](../docs/field-mappings.md)
- [Dataset inspection](../docs/dataset-analysis.md)

Python source of truth: `backend/app/contracts/v1.py` and `arrow_v1.py`. Regenerate artifacts from the repository root with `PYTHONPATH=backend python scripts/export_contract.py` (POSIX) or `$env:PYTHONPATH='backend'; .\.venv\Scripts\python scripts/export_contract.py` (PowerShell). Tests check artifact consistency and storage round trips. Unknown schema versions are rejected; source-specific extra fields are retained under `source_fields` rather than silently accepted as canonical columns.
