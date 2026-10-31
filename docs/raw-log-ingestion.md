# Raw and server log ingestion

## Typed FireX profile (master Phase 3)

Select `firex-kv-1.0.0` / **FireX typed security logs** for the supplied FireX
source. This sixth profile uses canonical 2.1.0 and transformation firex-kv/1.0.0,
validates/promotes IPs, ports, account and event descriptors, and retains all raw
fields/evidence. The generic key-value profile remains unchanged for unknown
sources. See field-mappings.md for the explicit observed-source contract.
CLI: `PYTHONPATH=backend python -m app.ingestion --source firex-10G.log --profile firex-kv-1.0.0`.
No JSONL conversion is required. Existing jobs are not migrated or overwritten.

Actual bounded-source check: the 1,000-record / 525,485-byte sample completed
with all rows accepted, no issues and schema 2.1.0 Parquet. Tests cover duplicate
occurrences, malformed framing, cancellation/resume and typed storage round trips.
This does not establish full-file throughput, attack accuracy or 15/30/50 GB support.

Five explicit profiles are now supported. Select the format in the UI, in API `source_profile`, or CLI `--profile`.

| Profile | Scope |
| --- | --- |
| `simedr-json-1.0.0` | Existing synthetic JSONL, unchanged canonical v1; synthetic flag must be true |
| `raw-text-1.0.0` | Any line-oriented UTF-8 application/server text; preserve message without guessing fields; canonical v2 |
| `web-combined-1.0.0` | Explicit standard Apache/Nginx combined access format; canonical v2 |

File extensions do not determine the parser. Supported names include .log, .txt, .jsonl, .ndjson, extensionless names such as access_log, and numbered .log/_log rotations. Hidden files, archives and compressed files are excluded. Input references remain restricted to the configured local input root; no arbitrary absolute file access or network upload is introduced.

API example:

```json
{"source":"access.log","source_profile":"web-combined-1.0.0","synthetic":false}
```

CLI:

```sh
PYTHONPATH=backend python -m app.ingestion --source server.log --profile raw-text-1.0.0
PYTHONPATH=backend python -m app.ingestion --source access.log --profile web-combined-1.0.0
```

Pass --synthetic for artificial raw/server test files; real text logs default to false. SimEDR remains explicitly synthetic. Resume retains the stored profile and source identity.

## Mapping and uncertainty

Raw text stores the decoded physical line at source_fields.message. No host, account or time is inferred. These records are partially accepted with unstructured_record/timestamp_missing issues and stored under date=unknown. This includes syslog/error/application logs whose specific formats have not yet been inspected. Multiline stack traces are preserved as individual physical records, not silently merged into fictional events.

Combined format follows the documented remote-host, ident, authenticated-user, bracketed timestamp, quoted request, status, response bytes, referer and user-agent layout. These values remain in source_fields along with the original message. A syntactically valid client IP is additionally projected to source.ip; hostnames are retained without DNS lookup. Server host, local destination and account domain are not fabricated. Request/status describe a web access event, never a security detection.

A timestamp with a valid explicit numeric offset is converted to UTC using an English month lookup independent of machine locale. Canonical v2 timestamp.raw contains the adapter's ISO timestamp representation for valid access times; source_fields.timestamp and message retain the original timestamp spelling. Invalid times remain uncertain/partially accepted. Bad line structure, impossible HTTP status or invalid response size is rejected with a reason. Custom Nginx log_format variants are not assumed to be combined format.

Reference: [Apache combined format](https://httpd.apache.org/docs/2.4/logs.html). Parser fixtures are illustrative specification-based tests, not observations of an unprovided organizer dataset. The supplied FireX sample uses the separate key-value profile described below.

## Storage and compatibility

The existing canonical v1 models and schema artifacts remain unchanged. Canonical v2 reuses the typed observation structure with explicit raw/server profiles and real/synthetic provenance. Definition: backend/app/log_formats.py; schema: schemas/v2/event.schema.json. The Arrow column layout stays compatible; file metadata records the actual schema/profile, and the Arrow reader dispatches validation by schema version. Original-file hashes, byte locators, record identities, resource limits, validation ledgers and checkpoint recovery apply to all profiles. Raw-byte evidence remains in the original file.

No new detector, graph, ATT&CK mapping or AI service is introduced. Existing limits still apply: strict UTF-8, 1 MiB per physical record, bounded Arrow batches, soft RSS admission, temporary-space/free-disk checks and one local writer. Compression, binary Windows EVTX, multiline-event reconstruction, custom formats and non-UTF-8 codecs require separate inspected adapters; they are not silently guessed. No 15/30/50 GB or new-format throughput benchmark is claimed.

## Actual supplied FireX file and JSONL conversion

The user supplied `data/firex-10G.log`. Its actual size is **6,543,120,032 bytes**, not 10 GB. Initial bounded inspection found UTF-8 quoted key=value records with date/time/tz, nanosecond-looking eventtime strings, device identifiers, type/subtype, addresses, ports, interfaces and action fields. This is an initial format observation, not a complete distribution/schema analysis or a verified product/vendor identification.

Use `key-value-1.0.0` in the ingestion UI/API to retain a named field dictionary under source_fields.fields. Values stay strings, preserving leading zeros and large timestamp precision. Generic JSON objects can use `json-record-1.0.0` without the SimEDR synthetic assumption. Both use v2 and retain the message without guessing host/account/IP mappings. The key-value profile explicitly recognizes ISO date + time + numeric tz fields, as observed in the supplied file; it converts their combined instant to UTC only when all three validate. Original values remain intact, eventtime stays a string, and other timestamp representations are not guessed. Generic JSON timestamps remain unpromoted. Duplicate keys or malformed quoted framing are rejected explicitly rather than silently overwritten.

A separate bounded export command converts the original raw file directly into easy-to-query JSONL:

```sh
PYTHONPATH=backend python -m app.convert_logs data/firex-10G.log data/firex-10G.converted.jsonl --profile key-value
```

Converter profiles: key-value, text, jsonl. Each output record carries a field dictionary (or unstructured message), source record number, byte span and raw SHA-256. The sidecar manifest identifies the original file/hash, profile and counts. Invalid input records produce issue entries; they are not silently discarded. No automatic numeric coercion or epoch-unit guessing occurs. Original files remain authoritative evidence. Conversion output is a generic JSONL envelope, not a synthetic SimEDR event; select the generic JSON profile when ingesting it.

The converter uses bounded physical lines, refuses overwrite, retains partial output after cancellation/failure, supports a cooperative --cancel-file flag, and does not claim resumable converter output. The main canonical ingester still provides checkpoint resume for all supported profiles. Conversion is currently strict UTF-8 and line-oriented; it cannot universally infer arbitrary binary, compressed, multiline or vendor-specific formats. Those need explicit inspected adapters. All logs, JSONL exports and manifests stay under ignored data/.

Actual-source integration: the first 1,000 physical records (525,485 bytes) were copied locally to an ignored bounded test sample and ingested with the key-value profile. All 1,000 were accepted with validated explicit-offset timestamps, zero partial/rejected records, and canonical v2 Parquet output. This is source compatibility evidence for that sample only, not a full-corpus semantic validation or scale benchmark.

Full local conversion completed on 31 October 2026: **12,398,551 physical records**, **zero conversion issue records**, from 6,543,120,032 source bytes into `data/firex-10G.converted.jsonl` (9,580,728,702 bytes). The larger export includes explicit JSON keys, provenance locators and per-record hashes. Its sidecar is `data/firex-10G.converted.jsonl.manifest.json`. These are local ignored artifacts, not repository deliverables. Successful parsing does not establish detection accuracy, ground truth or complete semantic mappings.

Independent bounded verification recounted all output newlines, rehashed the entire source against the manifest, checked the final byte span reaches source EOF, and compared field values/raw hashes at records 1, 6,202,914 and 12,398,551 with the original source bytes. All checks passed. The local verification report is `data/firex-conversion-verification.json`. Every field in every exported record was not independently re-parsed a second time.

Validation for this extension: 95 backend tests pass, the TypeScript/Vite production build passes, and pip reports no broken requirements. Tests cover original v1 compatibility, v2 schema artifacts, malformed input containment, preserved values/evidence, timezone handling and job lifecycle behavior. Docker and larger-tier performance were not requalified.
