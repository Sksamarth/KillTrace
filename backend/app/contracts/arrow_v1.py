"""Explicit v1 Arrow/Parquet representation; caller owns bounded batching."""
import json

import pyarrow as pa

from app.contracts.v1 import CanonicalEvent


def struct(fields):
    return pa.struct([pa.field(name, dtype) for name, dtype in fields])


TEXT = pa.string()
STRINGS = pa.list_(TEXT)
ENDPOINT = struct([("ip", TEXT), ("port", pa.int32()), ("domain", TEXT)])
ARROW_SCHEMA = pa.schema([
    pa.field("schema_version", TEXT, nullable=False),
    pa.field("source_profile", TEXT, nullable=False),
    pa.field("provenance", struct([
        ("original_file", TEXT), ("artifact_sha256", TEXT), ("source_id", TEXT), ("source_format", TEXT),
        ("record_number", pa.int64()), ("byte_offset", pa.int64()), ("byte_length", pa.int64()),
        ("raw_sha256", TEXT), ("batch_id", TEXT), ("transformation_version", TEXT), ("synthetic", pa.bool_()),
    ]), nullable=False),
    pa.field("source_record_id", TEXT, nullable=False),
    pa.field("normalization_id", TEXT, nullable=False),
    pa.field("timestamp", struct([("raw", TEXT), ("state", TEXT), ("utc", pa.timestamp("us", tz="UTC"))]), nullable=False),
    pa.field("event", struct([(name, STRINGS if name in ("category", "type") else pa.int32() if name == "severity" else TEXT)
                             for name in ("id", "kind", "category", "type", "action", "severity", "outcome", "module", "dataset")])),
    pa.field("host", struct([("name", TEXT), ("hostname", TEXT), ("ip", STRINGS), ("os_type", TEXT), ("os_full", TEXT)])),
    pa.field("user", struct([("name", TEXT), ("domain", TEXT)])),
    pa.field("process", struct([("pid", pa.int64()), ("name", TEXT), ("executable", TEXT), ("command_line", TEXT),
                               ("entity_id", TEXT), ("parent_pid", pa.int64()), ("parent_name", TEXT), ("hashes", pa.map_(TEXT, TEXT))])),
    pa.field("source", ENDPOINT),
    pa.field("destination", ENDPOINT),
    pa.field("dns_resolved_ips", STRINGS),
    pa.field("source_fields_json", pa.large_string(), nullable=False),
], metadata={b"killchain.schema_version": b"1.0.0", b"killchain.source_profile": b"simedr-json-1.0.0", b"killchain.evidence": b"synthetic; raw bytes referenced, not reconstructed"})


def to_arrow_row(event: CanonicalEvent) -> dict:
    row = event.model_dump(mode="json")
    row["timestamp"]["utc"] = event.timestamp.utc
    row["source_fields_json"] = json.dumps(row.pop("source_fields"), separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return row


def from_arrow_row(row: dict) -> CanonicalEvent:
    row = dict(row)
    row["source_fields"] = json.loads(row.pop("source_fields_json"))
    if row.get("process") is not None and row["process"].get("hashes") is not None:
        row["process"] = {**row["process"], "hashes": dict(row["process"]["hashes"])}
    # JSON mode preserves strict UUID/IP/datetime decoding rules across storage.
    model = CanonicalEvent
    if row.get('schema_version') == '2.1.0':
        from app.contracts.firex_v21 import FirexEvent
        model = FirexEvent
    if row.get("schema_version") == "2.0.0":
        from app.log_formats import CanonicalLogEvent
        model = CanonicalLogEvent
    return model.model_validate_json(json.dumps(row, default=lambda value: value.isoformat()))
