# Data contract — design gate

Status: blocked on actual authorized samples. No canonical event schema version has been issued. This document defines requirements for the future contract; it is not a field schema and must not be used to normalize logs.

See [dataset analysis](dataset-analysis.md), [field mapping status](field-mappings.md), and [schema status](../schemas/README.md). Chunk 1 runtime behavior remains unchanged.

## Contract approval and versioning

First inspect each real source, then define a canonical v1 contract with explicit types, nullability, identifier semantics and mappings. Publish immutable versioned schema definitions, corresponding Pydantic validation and an explicit Arrow/Parquet representation together. Record the canonical schema version and transformation/adapter version for each output event and in each output artifact manifest. A transformation change must not silently reuse an old version.

Separate source schema versions from canonical schema versions. Reject unsupported canonical versions explicitly. Define compatibility and migration rules before release: incompatible changes require a new major contract; additions require explicit reader behavior and validated defaults/nullability. Do not silently accept misspelled canonical keys as extensions. Future extensions need a namespaced, typed and bounded representation whose contents are based on observed sources.

## Evidence and provenance requirements

These are processing metadata requirements, not claims about columns in the organizer dataset.

| Traceability requirement | Required behavior for the future design |
| --- | --- |
| Original file | Retain an immutable artifact reference, original name/path in a private manifest, size and cryptographic content digest. Paths alone cannot identify unchanged evidence. |
| Original record or line | Select a locator appropriate to the observed format: byte span, logical record index, native record ID, archive member, and/or line range. Define index base and byte-range boundaries. Never equate a logical record with a physical line without checking framing. |
| Source identifier | Use a documented organizer/collector identity when available; otherwise assign an ingestion-managed identity and mark its origin. Do not invent a host identity from a file name. |
| Ingestion batch | Assign a processing batch identifier and persist its manifest/checkpoint relationship. It is processing metadata, not an original event field. |
| Transformation version | Record adapter/ruleset identity and immutable version plus source and target contract versions. Retain timestamp and identifier conversion decisions. |
| Raw evidence | Preserve original bytes in restricted immutable storage and retain a retrievable locator and digest. A parsed/re-serialized object is not the original byte evidence. |

Compressed or container formats may require both original-container references and a derived immutable member artifact with its own digest and locator. Preserve their relationship. Raw bytes must remain recoverable for decode failures, malformed records and unknown event types. Do not repeatedly inline entire source files into every event. Evidence retention, access control and deletion must be coordinated so references cannot silently outlive the evidence.

Distinguish a source-record identity, an ingestion occurrence and a content fingerprint when the contract is designed. Identical content is not sufficient evidence that two occurrences are the same event. Replay identity should depend on stable source artifact/record references and the relevant transformation version, not batch identity alone. Deduplication must preserve occurrence provenance and must not silently discard evidence. Exact identity algorithms remain unapproved until record framing is known.

## Missing information and uncertainty

Do not require host, user, address, process or event-type fields merely because they are useful for analysis. Determine their existence and meaning per source. Preserve the distinction between absent, explicit null, empty, invalid and unrecognized input through a documented validation outcome. Never substitute invented identifiers or an epoch timestamp for missing information.

Preserve original timestamp evidence and parsing decisions. Normalize to UTC only when the source provides an offset or there is documented, versioned timezone context. Do not infer timezone from the developer laptop or file modification time. Offset-free values, daylight-saving ambiguity, impossible dates, conflicting timestamps, precision loss and clock uncertainty need explicit outcomes. Ingestion time must not replace occurrence time. Select Arrow timestamp units and precision rules only after examining samples; preserve evidence if conversion would lose precision.

Unknown source event types should retain their original vocabulary and provenance without receiving an invented security label. Invalid timestamps, invalid addresses and malformed records must retain raw evidence and a reasoned validation outcome. Do not decide whether a source field contains an IP address until its semantics are verified. Define reject/quarantine versus partial-normalization behavior per source before implementing adapters.

## Schema validation plan — not yet implemented

No executable event-schema tests are supplied because no source-derived event schema exists. Existing foundation tests do not validate organizer logs. Future sanitized fixtures must come from authorized observed records or be clearly labeled isolated validator inputs derived from the approved contract; never present test inputs as organizer observations.

| Case | Acceptance requirement once the contract exists |
| --- | --- |
| Valid events | Each approved source maps to the expected canonical values, provenance and transformation versions; validate Pydantic and Arrow/Parquet round trips. |
| Missing fields | Observed optional omissions survive; required processing metadata failures are explicit; no fabricated defaults. |
| Invalid timestamps | Preserve original value/evidence and an invalid outcome; do not coerce to a valid occurrence time. Test actual observed formats, offsets and ambiguity separately. |
| Invalid IP addresses | Test IPv4/IPv6 and invalid values only for source fields verified to represent addresses; preserve invalid originals and diagnostics. |
| Malformed records | Preserve evidence and locator with a framing/parse diagnostic; do not emit a fabricated successful event. |
| Unknown event types | Retain unknown raw type without fabricated detection/mapping; follow the approved unknown-type policy. |
| Duplicate records | Same-record replay is recognizable across batches; different source occurrences with identical content retain separate provenance; transformation-version changes remain distinguishable. |
| Versions and extensions | Unsupported versions fail explicitly; unknown canonical keys cannot bypass validation; supported extensions obey type and size limits. |

Do not add passing placeholder tests, blanket skips, or generic event models to imply that these checks are complete.

## 8 GB laptop and columnar-storage design

The contract must support one-record validation followed by bounded Arrow record batches and Parquet row groups. Preserve nullability and enforce byte as well as row limits; a row count alone cannot bound memory when individual records or extension payloads are large. Define maximum record, field and nested-payload sizes after sample inspection, including an evidence-preserving oversized-record outcome. Never build a complete Python record list or DataFrame.

Keep original evidence on disk and reference it from normalized rows. Future batch accounting must include decompression, parser buffers, variable-width Arrow arrays, dictionary cardinality and conversion copies. Flush or reject before exceeding the working-set budget. Bound distinct-value profiling and graph expansion separately. Partitioning, timestamp units, row-group sizing, compression and dictionary strategy remain decisions to validate against observed data; no hardcoded dataset columns are selected here.

Use the existing single-worker DuckDB/spill configuration as an initial resource setting, not proof of a process-wide memory limit. No Arrow conversion, Parquet writer, ingestion pipeline, resource enforcement or benchmark is delivered in this chunk.

## Completion gate

Chunk 2 data-dependent deliverables remain incomplete until authorized samples are supplied and inspected, observed source mappings are reviewed, immutable event schema versions are published, and the validation matrix above is implemented and passing. The current deliverable records that gap and the requirements for resolving it.
