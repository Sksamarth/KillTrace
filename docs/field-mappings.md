# SimEDR JSONL → canonical v1.0.0 field mappings

## Additional FireX mapping: canonical 2.1.0

Profile `firex-kv-1.0.0`, transformation `firex-kv/1.0.0` is independently defined
in `backend/app/contracts/firex_v21.py`; it does not reinterpret existing v1/v2 jobs.

| Source field | Canonical projection |
| --- | --- |
| date + time + tz | timestamp.raw adapter ISO representation; timestamp.utc only with validated explicit offset; originals retained |
| srcip / dstip | source.ip / destination.ip after strict IP validation |
| srcport / dstport | source.port / destination.port after decimal/range validation |
| user | user.name; no account domain inferred |
| type / subtype / action | event.category / event.type / event.action; unknown strings preserved |
| status for type=event, action=login | failed → failure; success → success; other values leave event.outcome unset |
| devid / devname | source_fields.fields observer identifiers; not host identity |
| eventtime / logid / sessionid / hostname and all others | source_fields.fields with original spelling and string precision |

Every original field remains in source_fields.fields and the decoded line remains
in source_fields.message. Missing fields remain absent there; typed projections
are null. Invalid IP/port fields are retained but omitted from typed endpoints and
listed as validation issues. Invalid/uncertain timestamps retain their state.
Malformed encoding/framing or evidence mismatches reject with an explicit reason.
Original bytes are authoritative via file/hash/record/span. Repeated identical
bytes at different source offsets retain distinct occurrence identities. The
reporting observer is not equated with the source IP, destination host or user.

## Scope and rules

Source profile `simedr-json-1.0.0`, transformation `simedr-json/1.0.0`, canonical `1.0.0`. These mappings derive from the fully inspected local synthetic JSONL artifact documented in [dataset analysis](dataset-analysis.md), plus 21 real synthetic record byte excerpts in `backend/tests/fixtures/simedr_records.json`. No external organizer schema is assumed.

Every original parsed field, including mapped fields, remains at the same path under `source_fields`. The table marks additional typed projections where implemented. Original raw bytes remain in the referenced artifact and are not reconstructed from JSON. Omission/null/empty source distinctions remain in `source_fields`; normalized observations may be null. Strict types, optionality and uncertainty rules are defined by the [contract](data-contract.md) and versioned schema, not by the frequency with which a field occurs in this sample.

IP/port projections validate syntax/range without inventing absent endpoints. Category/type arrays remain arrays. OS and parent-process fields flatten as listed. All unpromoted sections (including agent, observer, network, DNS details, file, registry and winlog) retain exact source JSON values without claiming semantic validation. Unknown future source keys also remain under `source_fields`; unknown canonical keys are rejected.

## Every observed source path

| Source path | Canonical destination | Handling |
| --- | --- | --- |
| `@timestamp` | `timestamp.raw + timestamp.state/utc` | Explicit offset → UTC; missing/invalid/offset-free values retain uncertainty; raw bytes referenced. |
| `agent` | `source_fields.agent` | Preserved source annotation; no security inference or semantic verification. |
| `agent.id` | `source_fields.agent.id` | Preserved source annotation; no security inference or semantic verification. |
| `agent.name` | `source_fields.agent.name` | Preserved source annotation; no security inference or semantic verification. |
| `agent.type` | `source_fields.agent.type` | Preserved source annotation; no security inference or semantic verification. |
| `agent.version` | `source_fields.agent.version` | Preserved source annotation; no security inference or semantic verification. |
| `destination` | `destination` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `destination.domain` | `destination.domain` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `destination.ip` | `destination.ip` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `destination.port` | `destination.port` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `dns` | `source_fields.dns` | Preserved source annotation; no security inference or semantic verification. |
| `dns.question` | `source_fields.dns.question` | Preserved source annotation; no security inference or semantic verification. |
| `dns.question.name` | `source_fields.dns.question.name` | Preserved source annotation; no security inference or semantic verification. |
| `dns.question.type` | `source_fields.dns.question.type` | Preserved source annotation; no security inference or semantic verification. |
| `dns.resolved_ip` | `dns_resolved_ips` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `dns.response_code` | `source_fields.dns.response_code` | Preserved source annotation; no security inference or semantic verification. |
| `event` | `event` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `event.action` | `event.action` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `event.category` | `event.category` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `event.dataset` | `event.dataset` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `event.id` | `event.id` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `event.kind` | `event.kind` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `event.module` | `event.module` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `event.outcome` | `event.outcome` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `event.severity` | `event.severity` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `event.type` | `event.type` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `file` | `source_fields.file` | Preserved source annotation; no security inference or semantic verification. |
| `file.extension` | `source_fields.file.extension` | Preserved source annotation; no security inference or semantic verification. |
| `file.name` | `source_fields.file.name` | Preserved source annotation; no security inference or semantic verification. |
| `file.path` | `source_fields.file.path` | Preserved source annotation; no security inference or semantic verification. |
| `file.size` | `source_fields.file.size` | Preserved source annotation; no security inference or semantic verification. |
| `host` | `host` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `host.hostname` | `host.hostname` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `host.ip` | `host.ip` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `host.name` | `host.name` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `host.os` | `host.os_type / host.os_full` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `host.os.full` | `host.os_full` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `host.os.type` | `host.os_type` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `labels` | `source_fields.labels` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `labels.simulated_detection` | `source_fields.labels.simulated_detection` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `labels.synthetic` | `source_fields.labels.synthetic` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `labels_extra` | `source_fields.labels_extra` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `labels_extra.failed_count_5min` | `source_fields.labels_extra.failed_count_5min` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `labels_extra.files_renamed_60s` | `source_fields.labels_extra.files_renamed_60s` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `network` | `source_fields.network` | Preserved source annotation; no security inference or semantic verification. |
| `network.bytes` | `source_fields.network.bytes` | Preserved source annotation; no security inference or semantic verification. |
| `network.direction` | `source_fields.network.direction` | Preserved source annotation; no security inference or semantic verification. |
| `network.protocol` | `source_fields.network.protocol` | Preserved source annotation; no security inference or semantic verification. |
| `network.transport` | `source_fields.network.transport` | Preserved source annotation; no security inference or semantic verification. |
| `observer` | `source_fields.observer` | Preserved source annotation; no security inference or semantic verification. |
| `observer.product` | `source_fields.observer.product` | Preserved source annotation; no security inference or semantic verification. |
| `observer.vendor` | `source_fields.observer.vendor` | Preserved source annotation; no security inference or semantic verification. |
| `observer.version` | `source_fields.observer.version` | Preserved source annotation; no security inference or semantic verification. |
| `process` | `process` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `process.command_line` | `process.command_line` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `process.entity_id` | `process.entity_id` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `process.executable` | `process.executable` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `process.hash` | `process.hashes` | Preserve synthetic path hash strings; not hashes of real executable bytes. |
| `process.hash.md5` | `process.hashes.md5` | Preserve synthetic path hash strings; not hashes of real executable bytes. |
| `process.hash.sha1` | `process.hashes.sha1` | Preserve synthetic path hash strings; not hashes of real executable bytes. |
| `process.hash.sha256` | `process.hashes.sha256` | Preserve synthetic path hash strings; not hashes of real executable bytes. |
| `process.name` | `process.name` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `process.parent` | `process.parent_pid / process.parent_name` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `process.parent.name` | `process.parent_name` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `process.parent.pid` | `process.parent_pid` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `process.pid` | `process.pid` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `registry` | `source_fields.registry` | Preserved source annotation; no security inference or semantic verification. |
| `registry.data` | `source_fields.registry.data` | Preserved source annotation; no security inference or semantic verification. |
| `registry.data.strings` | `source_fields.registry.data.strings` | Preserved source annotation; no security inference or semantic verification. |
| `registry.path` | `source_fields.registry.path` | Preserved source annotation; no security inference or semantic verification. |
| `rule` | `source_fields.rule` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `rule.id` | `source_fields.rule.id` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `rule.name` | `source_fields.rule.name` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `rule.severity` | `source_fields.rule.severity` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `source` | `source` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `source.ip` | `source.ip` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `source.port` | `source.port` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `threat` | `source_fields.threat` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `threat.framework` | `source_fields.threat.framework` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `threat.tactic` | `source_fields.threat.tactic` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `threat.tactic.name` | `source_fields.threat.tactic.name` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `threat.technique` | `source_fields.threat.technique` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `threat.technique.id` | `source_fields.threat.technique.id` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `threat.technique.name` | `source_fields.threat.technique.name` | Source-supplied simulated metadata; never a KillChain AI detection or ATT&CK validation. |
| `user` | `user` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `user.domain` | `user.domain` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `user.name` | `user.name` | Typed projection; also retained verbatim as parsed JSON under `source_fields`. |
| `winlog` | `source_fields.winlog` | Preserved source annotation; no security inference or semantic verification. |
| `winlog.event_id` | `source_fields.winlog.event_id` | Preserved source annotation; no security inference or semantic verification. |
| `winlog.logon` | `source_fields.winlog.logon` | Preserved source annotation; no security inference or semantic verification. |
| `winlog.logon.type` | `source_fields.winlog.logon.type` | Preserved source annotation; no security inference or semantic verification. |

## Processing metadata

The source JSON has no original-file checksum, byte offset, record number, ingestion batch, transformation version or canonical schema version. Those are assigned processing metadata from the private artifact manifest and record locator, never asserted to be source columns. The adapter requires verified caller-supplied provenance, checks each record's byte length/digest, and derives replay/normalization identities. `event.id` stays the original UUID string, separate from these identities.

All records have processing `provenance.synthetic=true`; absence of `labels.synthetic` on baseline rows does not make them real telemetry. `source_id` identifies this source, not a predicted host or account. A different real source must receive its own profile and reviewed mappings.

## CEF and other formats

No empirical mappings are published for formats not generated and inspected here. The pasted formatter suggests CEF `rt`, `dvchost`, `suser`, `cat`, `act`, `externalId` and selected process/address/technique extensions, but those are source-code observations only. They are not an approved CEF mapping and are not accepted by the JSONL adapter. Many JSON fields would be absent after CEF projection. Inspect actual records, escaping, extension boundaries and any syslog envelope before defining that profile; no source inherits another format's mappings automatically.
