# Canonical security event contract v1.0.0

## Current source-specific extension: FireX 2.1.0

The historical v1 contract below remains unchanged. Canonical 2.1.0 and source
profile `firex-kv-1.0.0` now describe typed projections from the authorized FireX
key/value sample. Python definitions are in `backend/app/contracts/firex_v21.py`;
published event/validation schemas are under `schemas/v2.1/`. Source mappings and
observed sample coverage are documented in field-mappings.md and dataset-analysis.md.

This profile is distinct from generic key-value v2.0.0: it validates/promotes
endpoints, account name, category/type/action and recognized login outcome.
Original fields and decoded message stay intact, with raw evidence referenced by
file hash, byte span and record hash. All promoted fields support absence; invalid
addresses/ports produce partial outcomes, malformed framing/encoding rejects,
and timestamp uncertainty remains explicit. Observer identity is not promoted
to an affected host. Numeric-looking eventtime retains its original precision
without epoch-unit guessing. Source-supplied alerts remain source information.

Schema and transformation versions participate in normalization identity; source
occurrence identity remains independent of normalization version. Different byte
locations retain duplicate occurrences. The Arrow columns can represent this
schema without adding unbounded fields, but readers must explicitly dispatch
2.1.0 validation. Phase 3 owns storage/worker integration; this phase only defines
and validates the source contract. Existing completed jobs are not migrated.

## Scope and source evidence

This contract is derived from the actual local 1 GiB JSONL file generated at the user's request from their Mitigata SimEDR 1.0 script. It is a **synthetic-source contract**, not an assertion about undisclosed organizer production logs. See [dataset analysis](dataset-analysis.md) for measured coverage and [field mappings](field-mappings.md) for every observed path. The generator's alert and ATT&CK metadata are simulated source annotations; KillChain AI does not produce or verify detections in this chunk.

Python definitions: `backend/app/contracts/v1.py`. Versioned JSON Schema artifacts: [event](../schemas/v1/event.schema.json) and [validation result](../schemas/v1/validation.schema.json). Arrow definition: `backend/app/contracts/arrow_v1.py`; [readable schema](../schemas/v1/arrow-schema.txt). Python is the source of truth; tests detect stale generated artifacts.

## Structure

| Canonical field | Meaning and null behavior |
| --- | --- |
| `schema_version` | Literal `1.0.0`, materialized on output |
| `source_profile` | Literal `simedr-json-1.0.0`; never silently applied to other sources |
| `provenance` | Required artifact/record/batch/transformation metadata defined below |
| `source_record_id` | SHA-256 source-occurrence identity derived from provenance |
| `normalization_id` | SHA-256 source-occurrence + schema + transformation identity |
| `timestamp` | Required uncertainty object: original string, state and nullable UTC instant |
| `event` | Optional id/kind/category/type/action/severity/outcome/module/dataset; arrays stay arrays |
| `host` | Optional name/hostname, address array, OS type and full description |
| `user` | Optional account name/domain; no inferred SID, account ID, or host association |
| `process` | Optional PID/name/executable/command line/entity ID, parent PID/name and source hashes |
| `source`, `destination` | Optional IP/port/domain endpoints; missing endpoints stay null |
| `dns_resolved_ips` | Optional array from observed DNS resolved addresses |
| `source_fields` | Original parsed JSON object including all mapped, unpromoted and future source fields |

All observation fields are optional even where this generated file always contains them. Missing and explicit-null normalized values may both be null, but `source_fields` preserves the distinction. Empty strings and arrays are not turned into missing values. Unknown canonical keys fail validation; future source-specific keys remain in `source_fields`. No kill-chain stage, risk score, inferred process lineage, prediction or detection field is invented.

Severity is the source's integer 0–10, not a calibrated probability or detection confidence. Event kinds/categories/types/actions/outcomes are bounded strings, not a closed vocabulary; new source types are retained. PIDs are nonnegative signed-64-bit values; ports are 0–65535; IP validation accepts IPv4 and IPv6 even though this file contains only IPv4. Synthetic hashes are carried as source strings, never treated as file-content verification.

## Evidence and provenance

Every validation result, including rejection, contains:

| Metadata | Contract |
| --- | --- |
| `original_file` | Required original file reference (1–2048 characters); production manifests must resolve it to immutable, access-controlled evidence |
| `artifact_sha256` | Lowercase SHA-256 of complete original file bytes |
| `source_id` | Stable assigned source identity (1–256 characters); current source is user-supplied SimEDR synthetic telemetry, not a machine inferred from a filename |
| `source_format` | Bounded format name; envelope can carry other formats, but this adapter accepts only `jsonl` |
| `record_number` | One-based physical line/logical record for this JSONL source (signed-64-bit positive integer) |
| `byte_offset` | Zero-based offset in the original uncompressed byte stream |
| `byte_length` | Exact byte count including LF/CRLF delimiter when present; 1–1,048,576 |
| `raw_sha256` | SHA-256 of that exact byte span, including delimiter |
| `batch_id` | Processing UUID, not an original event ID |
| `transformation_version` | Literal adapter identity `simedr-json/1.0.0` for this profile |
| `synthetic` | Required true for this profile; all rows are synthetic, including baseline rows without source labels |

`validate_json_record` checks record length and digest against the supplied reference. The caller must verify the complete artifact hash and record locator against a trusted manifest; this function does not reread/hash a 1 GiB file per event or verify file ownership. A fabricated caller-supplied digest is not an authenticity guarantee. Preserve original bytes on disk. Parsed JSON or its Parquet serialization cannot reconstruct original whitespace, key ordering, escaping, BOMs or newlines.

For compressed/container sources, future profiles must specify original container/member references and byte-coordinate semantics. Do not apply this JSONL locator to CSV multiline or binary formats. No CEF adapter is implemented; the generic provenance envelope preserves references for unsupported formats, and validation returns `unsupported_source_profile` rather than guessing.

## Duplicate and replay semantics

`source_record_id = SHA256(compact JSON [source_id, artifact_sha256, byte_offset, byte_length, raw_sha256])`, encoded as UTF-8. `normalization_id = SHA256(source_record_id + ':' + schema_version + ':' + transformation_version)`.

Replaying the same source occurrence in another batch yields the same identities. A separate byte occurrence containing identical content yields a different source-record ID. Transformation changes alter normalization identity but preserve source identity. Raw digest detects exact-byte equality; event IDs remain source values and are not trusted as global identity. No automatic deduplication/drop policy is implemented. The profiling tool checks exact byte-record digests and repeated source event IDs on disk; it does not establish semantic duplicate equivalence.

## Timestamp uncertainty

Original timestamp strings remain available in `timestamp.raw` and `source_fields`. `known` requires a valid ISO timestamp with seconds, explicit `Z` or numeric offset and at most six fractional digits; UTC must agree exactly with the original instant. The observed generator uses three fractional digits and `Z`. UTC uses Arrow `timestamp[us, UTC]`, preserving the observed millisecond precision while allowing microseconds without truncation.

`missing` has no raw/UTC value. Explicit source null additionally records `timestamp_explicit_null`. `invalid` preserves the original string and has no UTC instant. `offset_unknown` preserves a valid offset-free timestamp without assuming the laptop's timezone. Date-only strings, numeric epochs, impossible dates/offsets, and precision beyond microseconds are not guessed or truncated. Non-string/non-null timestamps reject the normalized event. No ingestion time substitutes for event time. The observed timestamps represent generation time; they do not establish a historical attack timeline or clock synchronization.

## Validation outcomes

`RecordValidation` v1.0.0 returns `valid`, `partial` or `rejected`, with provenance and bounded issue codes. A valid event has no issues; partial events have timestamp uncertainty issues; rejected records have issues and no fabricated normalized event.

Strict UTF-8 and JSON parsing reject bad encodings, non-object records, duplicate JSON keys and nonstandard NaN/Infinity constants. Wrong mapped field types, invalid addresses, invalid ports or out-of-range severity reject the event while retaining the raw reference. There is no scalar-to-array or numeric-string coercion. Fields not promoted to typed observations are preserved as bounded JSON source fields; their semantic validity is not claimed. Generic rejection codes avoid echoing potentially sensitive values.

Tests use 21 actual synthetic record byte excerpts spanning action/type/outcome/source-rule/OS combinations found within the first 10,000 rows. Explicit test mutations cover missing fields, nulls, invalid timestamps, timezone uncertainty, IPv4/IPv6, malformed records, unknown types, duplicates/replays, provenance mismatch, unsupported profiles, versions, bounds and Parquet round trips. Mutations are validator inputs, not findings about the generated file.

## Bounded Arrow and Parquet storage

The explicit Arrow schema uses nullable structs/lists rather than inferring schema from each batch. UUIDs/IP addresses/digests are strings; byte locators and PIDs are signed 64-bit integers. `source_fields` is stored as `source_fields_json: large_string`, a semantic JSON copy, avoiding a dynamic wide Parquet schema. Known normalized fields remain typed/queryable. Reader helpers revalidate rows against v1. Parquet metadata records schema/source-profile versions and synthetic status. Validation-result JSON retains rejection/partial outcomes; the Chunk 3 writer persists those outcomes in a separate validation ledger.

Single-record input is capped at 1 MiB, normalized strings at 65,536 characters, normalized string/IP arrays at 256 entries, and serialized `source_fields` at 2 MiB. These are defensive initial limits, not observed dataset maxima or throughput claims. The Chunk 3 bounded reader enforces this before decoding and preserves oversized-record references in a separate rejection ledger; canonical Provenance still cannot represent a record larger than 1 MiB. Never truncate evidence to make it valid.

Future batching should flush at the first of a row cap or byte cap (initial design targets: 8,192 rows or 16 MiB of estimated payload), then measure real RSS including JSON, Arrow and conversion copies before tuning. Chunk 3 now implements a bounded batcher, partitioned Parquet writer, separate-process job APIs, cooperative cancellation and checkpoint recovery. Its defaults are 4,096 rows or 8 MiB estimated payload; the earlier 8,192/16 MiB proposal is not the active configuration. Resource checks are cooperative rather than allocator guarantees. See [ingestion](ingestion.md). Tiny bounded fixture tables in tests verify storage compatibility only. Keep full evidence on disk, retain the existing 1 GB DuckDB/two-thread initial settings, and leave memory for Windows/editor/browser. Full-dataset duplicate checks use an 8 MiB SQLite page cache and disk indexes instead of Python sets. No complete dataset is loaded into Pandas or Python lists.

## Version policy and next source

Versioned artifacts are published together with transformation and mapping definitions. Breaking field, type or semantic changes require a new major contract and explicit migration. A new additive minor version also requires reader/schema agreement; v1 readers reject unsupported version literals. Re-export artifacts with `$env:PYTHONPATH='backend'; .\.venv\Scripts\python scripts/export_contract.py` in PowerShell.

This release covers the generated JSONL profile only. The supplied script describes optional CEF and syslog/HTTP outputs, but none was generated or inspected. Its CEF formatter is lossy; it must have its own samples, mapping and parser tests before support is advertised. The organizer's future 5 GB sample must be profiled and compared against this source profile before reuse; no assumption of identical fields is permitted. No performance or detection benchmark is claimed.


Current raw/server extension: see [raw-log ingestion](raw-log-ingestion.md). The earlier synthetic-only statements describe the original v1 ingestion scope; explicit raw-text and combined-access profiles now use canonical v2.
