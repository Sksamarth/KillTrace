# Dataset analysis

## FireX source audit (master Phase 2)

The user supplied `data/firex-10G.log`, actually 6,543,120,032 bytes. It is
line-oriented quoted key=value text, not a JSON schema. The existing full JSONL
conversion preserved 12,398,551 records without parsing issues; that is not a
complete semantic validation. A bounded prefix sample of 1,000 records, 525,485
bytes, was separately checked against canonical 2.1.0: **1,000 valid**, no partial
or rejected records, and no identical raw-record hashes within the sample.
Sample SHA-256: `872d9d2be7a87977058b0bd66049afca5f0e1c634ead97f25f9e849ede619f97`.

All 1,000 decoded strictly as UTF-8 and supplied date/time/explicit tz, eventtime,
devname/devid, logid, type/subtype, level, vd and action. The observed timestamp
syntax includes `2026-10-23 08:48:26 +0530`; eventtime is preserved as a string
without assuming its epoch unit. Source and destination IPs appeared in 940
records; ports in 778; user in 151; hostname in 95; source attack annotations in
27 and virus in 13. Missing fields are source-family differences, not invented
empty entities. Process/PID/parent information was not available in this sample.
Device names identify the reporting observer; hostname may describe a requested
network destination, so neither is automatically declared an affected host.
logid is preserved as a source event code, not assumed globally unique.

The observed fields also include interfaces/roles, sessionid, proto, policyid,
service, countries, app/appcat/apprisk, duration, byte/packet counters, logdesc,
ui/method/status/reason/msg, url/catdesc, attack/attackid/severity and virus.
These unpromoted fields retain original strings. Source annotations do not become
verified attacks. No planted sequence or access-permission topology was provided.

Reproduce aggregate inspection without printing private field values:
`PYTHONPATH=backend python scripts/inspect_firex_contract.py data/firex-ingestion-sample.log`.
The script streams hashing/records and caps duplicate tracking at 10,000 inspected
records. No full-file duplicate or field-distribution claim follows from this
bounded prefix. The validator and schema tests include deliberately malformed
synthetic records; zero malformed real sample rows does not eliminate that case.

## Historical synthetic SimEDR inspection

## Source and scope

The user supplied a Python **synthetic** Mitigata SimEDR 1.0 generator and explicitly requested a 1 GB test log. We used a local-file adaptation to create **1 GiB (1,073,741,824-byte target)**, finishing the last whole record rather than cutting JSON. No organizer production dataset has been supplied. Findings below describe the actual generated file, not an assumed external schema or real attack corpus.

The adaptation retains the supplied baseline families/weights and five simulated alert templates. It adds a byte target, exclusive file creation, a SHA-256 manifest and progress reporting; it uses no network sinks or delay. Plain domains were restored from Markdown links introduced in the pasted text. All records are synthetic, even though only alert records carry `labels.synthetic` in the source. RNG seed 42 controls random choices but not UUIDs or wall-clock timestamps, so regeneration does not produce identical file bytes.

## Artifact and inspection coverage

| Property | Measured value |
| --- | --- |
| Local file (ignored by Git) | `data/simedr-1gib.jsonl` |
| Actual bytes | 1,073,742,861 |
| Whole-record overshoot beyond 1 GiB | 1,037 bytes |
| Physical lines / JSON objects | 1,284,111 / 1,284,111 |
| Format | Uncompressed JSON Lines, one nested object per line; not a JSON array |
| Encoding | Strict UTF-8 decode passed for every record; no BOM observed |
| Newlines | 1,284,111 LF; 0 CRLF |
| Largest record including delimiter | 1,305 bytes |
| File SHA-256 | `4561fe59115b4dc73c1d4795f46f8bb26e8bc7761e9d6b7af7b7cb6939b9bba1` |
| Generated simulated alerts | 64,216; source annotations only |
| Distinct host names / account names | 28 / 12 |
| Windows / Linux records | 1,196,184 / 87,927 |

`scripts/profile_sample.py` scanned the **entire file**, independently recomputed its SHA-256, inventoried all 91 observed object paths, counted missing/null/empty values, checked timestamp syntax and known IP fields, and used a disk-backed SQLite index for raw-record digest and event-ID repetitions. Its cache is configured to 8 MiB; line reads are capped at 1 MiB, field inventory at 512 paths and categorical counters at 128 values. There is no complete-dataset Python list, set or Pandas DataFrame. Full private profile/manifest artifacts remain under ignored `data/`; the disposable duplicate index was removed after successful inspection. No throughput, RSS or scalability benchmark was measured.

## Timestamps and identifiers

Every `@timestamp` is an explicit UTC ISO timestamp in `YYYY-MM-DDTHH:MM:SS.sssZ` form. Earliest: `2026-10-31T08:35:17.918000+00:00`; latest: `2026-10-31T08:36:02.473000+00:00`. These are generator wall-clock instants, not a historical multi-stage incident. Local timezone is not inferred. No absent, invalid or offset-free timestamp was observed; future such cases still have explicit contract outcomes.

Host fields are `host.name`, `host.hostname`, `host.ip` (array), `host.os.type` and `host.os.full`. Names follow the generator's workstation/server inventory; `agent.id` is derived from host-name text, not a hardware identity. Account fields are `user.name` and `user.domain`; there is no SID or account UUID. Account and host choices do not establish a verified ownership or authorization relationship.

`source.ip` and optional `source.port` describe a source endpoint where supplied. `destination.ip`, `destination.port`, and `destination.domain` occur in network connections. `dns.resolved_ip` is an address array, not a destination socket. Full inspection validated 2,273,204 IPv4 address occurrences across host/source/destination/DNS fields; no IPv6 or invalid value was observed. This is syntactic validation, not network ownership, reachability or reputation validation. The generator contains some real-looking public IP/domain strings but makes no DNS, HTTP or socket calls in the local adaptation.

## Event families

| `event.action` | Records |
| --- | --- |
| `process_created` | 379,163 |
| `dns_query` | 243,696 |
| `registry_value_set` | 69,420 |
| `network_connection` | 317,532 |
| `user_logon` | 110,333 |
| `file_modified` | 151,028 |
| `file_rename` | 12,939 |

Categories observed: process, network, registry, authentication and file. Types observed: start, protocol, change, connection and creation. Kinds: 1,219,895 `event`, 64,216 `alert`. Severity values: 0, 5, 8 and 10. Authentication outcomes: 90,819 success and 19,514 failure. These vocabularies are source values, not a universal taxonomy.

## Process and security fields

`process.pid` and `process.name` occur in 1,173,778 rows; authentication rows lack process data. Executable, command line, hashes, parent PID/name and entity ID occur only in process-created events (379,163 rows). PIDs, parent PIDs and entity UUIDs are independently generated; do not infer verified lineage by joining random identifiers. The generator hashes executable **path strings**, not executable file bytes.

Additional fields include network transport/direction/protocol/byte counts, DNS question/response/address data, file path/name/size/extension, registry path/string values, and winlog event ID/logon type. Alert-only `threat`, `rule`, `labels` and `labels_extra` contain preattached simulated techniques, rule descriptions and synthetic aggregate counts. No Cyber Kill Chain stage field exists. The source does not identify an ATT&CK catalog version. None of these annotations is evidence of an independently executed or validated detection.

## Missing values, malformed records and duplicates

All present inventoried fields had **zero explicit null and zero empty-string/list/object values**. Omitted source fields are common and meaningful:

| Field | Missing records |
| --- | --- |
| `process.name` | 110,333 |
| `process.command_line` | 904,948 |
| `source.ip` | 856,246 |
| `destination.ip` | 966,579 |
| `dns.resolved_ip` | 1,040,415 |
| `event.outcome` | 1,173,778 |
| `labels` / `threat` | 1,219,895 each |

Full scan found zero malformed JSON/non-object rows, UTF-8 decode failures, invalid timestamps and invalid addresses in the inspected fields. It found zero repeated raw-record SHA-256 digests and zero repeated `event.id` values. This does not establish absence of semantic duplicates. Schema tests deliberately introduce invalid/missing/duplicate variants to verify handling; those mutations are not dataset findings.

The data has known synthetic limitations: generated public addresses are not sampled from actual flows; HTTPS metadata can coexist with port 80; Windows logon metadata can be attached to a Linux host by the supplied generator; process hashes and lineage are artificial; aggregates such as failed-count and mass-renames are template values rather than recomputed windows. Do not silently repair these semantics or use the file as ground truth for attack-path accuracy.

## Complete observed path inventory

`present` and `missing` count records, not array elements. Paths include both object containers and leaves. Types below are observed JSON-decoded Python types; source mappings are documented separately.

| Source path | Observed types | Present | Missing |
| --- | --- | --- | --- |
| `@timestamp` | str | 1,284,111 | 0 |
| `agent` | dict | 1,284,111 | 0 |
| `agent.id` | str | 1,284,111 | 0 |
| `agent.name` | str | 1,284,111 | 0 |
| `agent.type` | str | 1,284,111 | 0 |
| `agent.version` | str | 1,284,111 | 0 |
| `destination` | dict | 317,532 | 966,579 |
| `destination.domain` | str | 317,532 | 966,579 |
| `destination.ip` | str | 317,532 | 966,579 |
| `destination.port` | int | 317,532 | 966,579 |
| `dns` | dict | 243,696 | 1,040,415 |
| `dns.question` | dict | 243,696 | 1,040,415 |
| `dns.question.name` | str | 243,696 | 1,040,415 |
| `dns.question.type` | str | 243,696 | 1,040,415 |
| `dns.resolved_ip` | list | 243,696 | 1,040,415 |
| `dns.response_code` | str | 243,696 | 1,040,415 |
| `event` | dict | 1,284,111 | 0 |
| `event.action` | str | 1,284,111 | 0 |
| `event.category` | list | 1,284,111 | 0 |
| `event.dataset` | str | 1,284,111 | 0 |
| `event.id` | str | 1,284,111 | 0 |
| `event.kind` | str | 1,284,111 | 0 |
| `event.module` | str | 1,284,111 | 0 |
| `event.outcome` | str | 110,333 | 1,173,778 |
| `event.severity` | int | 1,284,111 | 0 |
| `event.type` | list | 1,284,111 | 0 |
| `file` | dict | 163,967 | 1,120,144 |
| `file.extension` | str | 12,939 | 1,271,172 |
| `file.name` | str | 151,028 | 1,133,083 |
| `file.path` | str | 163,967 | 1,120,144 |
| `file.size` | int | 151,028 | 1,133,083 |
| `host` | dict | 1,284,111 | 0 |
| `host.hostname` | str | 1,284,111 | 0 |
| `host.ip` | list | 1,284,111 | 0 |
| `host.name` | str | 1,284,111 | 0 |
| `host.os` | dict | 1,284,111 | 0 |
| `host.os.full` | str | 1,284,111 | 0 |
| `host.os.type` | str | 1,284,111 | 0 |
| `labels` | dict | 64,216 | 1,219,895 |
| `labels.simulated_detection` | str | 64,216 | 1,219,895 |
| `labels.synthetic` | str | 64,216 | 1,219,895 |
| `labels_extra` | dict | 25,536 | 1,258,575 |
| `labels_extra.failed_count_5min` | int | 12,597 | 1,271,514 |
| `labels_extra.files_renamed_60s` | int | 12,939 | 1,271,172 |
| `network` | dict | 317,532 | 966,579 |
| `network.bytes` | int | 317,532 | 966,579 |
| `network.direction` | str | 317,532 | 966,579 |
| `network.protocol` | str | 304,686 | 979,425 |
| `network.transport` | str | 317,532 | 966,579 |
| `observer` | dict | 1,284,111 | 0 |
| `observer.product` | str | 1,284,111 | 0 |
| `observer.vendor` | str | 1,284,111 | 0 |
| `observer.version` | str | 1,284,111 | 0 |
| `process` | dict | 1,173,778 | 110,333 |
| `process.command_line` | str | 379,163 | 904,948 |
| `process.entity_id` | str | 379,163 | 904,948 |
| `process.executable` | str | 379,163 | 904,948 |
| `process.hash` | dict | 379,163 | 904,948 |
| `process.hash.md5` | str | 379,163 | 904,948 |
| `process.hash.sha1` | str | 379,163 | 904,948 |
| `process.hash.sha256` | str | 379,163 | 904,948 |
| `process.name` | str | 1,173,778 | 110,333 |
| `process.parent` | dict | 379,163 | 904,948 |
| `process.parent.name` | str | 379,163 | 904,948 |
| `process.parent.pid` | int | 379,163 | 904,948 |
| `process.pid` | int | 1,173,778 | 110,333 |
| `registry` | dict | 69,420 | 1,214,691 |
| `registry.data` | dict | 69,420 | 1,214,691 |
| `registry.data.strings` | list | 69,420 | 1,214,691 |
| `registry.path` | str | 69,420 | 1,214,691 |
| `rule` | dict | 64,216 | 1,219,895 |
| `rule.id` | str | 64,216 | 1,219,895 |
| `rule.name` | str | 64,216 | 1,219,895 |
| `rule.severity` | str | 64,216 | 1,219,895 |
| `source` | dict | 427,865 | 856,246 |
| `source.ip` | str | 427,865 | 856,246 |
| `source.port` | int | 317,532 | 966,579 |
| `threat` | dict | 64,216 | 1,219,895 |
| `threat.framework` | str | 64,216 | 1,219,895 |
| `threat.tactic` | dict | 64,216 | 1,219,895 |
| `threat.tactic.name` | list | 64,216 | 1,219,895 |
| `threat.technique` | dict | 64,216 | 1,219,895 |
| `threat.technique.id` | list | 64,216 | 1,219,895 |
| `threat.technique.name` | list | 64,216 | 1,219,895 |
| `user` | dict | 1,284,111 | 0 |
| `user.domain` | str | 1,284,111 | 0 |
| `user.name` | str | 1,284,111 | 0 |
| `winlog` | dict | 110,333 | 1,173,778 |
| `winlog.event_id` | int | 110,333 | 1,173,778 |
| `winlog.logon` | dict | 110,333 | 1,173,778 |
| `winlog.logon.type` | str | 110,333 | 1,173,778 |

## Other formats and upcoming data

The pasted script includes optional CEF and syslog/HTTP renderers. No CEF, syslog, HTTP capture, CSV, Parquet or compressed source file was generated or inspected in this task. Source review alone is not empirical validation of those wire formats. The local adaptation emits only JSONL. The original CEF projection omits many JSON fields and would need separate format/escaping/framing tests.

The future 5 GB file needs its own authorization, artifact manifest, full format/schema/timezone checks and comparison to this profile. If it is an actual organizer dataset rather than a generated file, keep its provenance and conclusions distinct. The versioned contract supports this observed synthetic JSONL source only; no production schema or performance claim is made.
