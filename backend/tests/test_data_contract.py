import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from app.contracts.arrow_v1 import ARROW_SCHEMA, from_arrow_row, to_arrow_row
from app.contracts.v1 import CanonicalEvent, EventTime, Provenance, RecordValidation, TRANSFORMATION_VERSION, identities, validate_json_record

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = json.loads((Path(__file__).parent / "fixtures/simedr_records.json").read_text())
BATCH = UUID("00000000-0000-4000-8000-000000000001")


def provenance(raw, record_number=1, byte_offset=0, **updates):
    fields = dict(original_file=FIXTURES["artifact_file"], artifact_sha256=FIXTURES["artifact_sha256"], source_id="user-simedr-local", source_format="jsonl", record_number=record_number, byte_offset=byte_offset, byte_length=len(raw), raw_sha256=hashlib.sha256(raw).hexdigest(), batch_id=BATCH, transformation_version=TRANSFORMATION_VERSION, synthetic=True)
    fields.update(updates)
    return Provenance(**fields)


def validate(payload):
    raw = (json.dumps(payload) + "\n").encode()
    return validate_json_record(raw, provenance(raw))


def payload():
    return json.loads(FIXTURES["records"][0]["raw"])


@pytest.mark.parametrize("fixture", FIXTURES["records"])
def test_actual_generated_records_validate(fixture):
    raw = fixture["raw"].encode()
    ref = provenance(raw, fixture["record_number"], fixture["byte_offset"])
    result = validate_json_record(raw, ref)
    assert result.status == "valid"
    assert result.event.source_fields == json.loads(raw)
    assert result.event.timestamp.utc.tzinfo == timezone.utc
    assert result.event.provenance.synthetic is True


def test_missing_and_null_are_preserved_without_invented_entities():
    absent = validate({})
    explicit_null = validate({"@timestamp": None, "host": None, "process": None})
    assert absent.status == explicit_null.status == "partial"
    assert absent.event.host is None
    assert absent.event.source_fields == {}
    assert explicit_null.event.source_fields["host"] is None
    assert "timestamp_explicit_null" in explicit_null.issues
    assert absent.event.timestamp.utc is None


@pytest.mark.parametrize("value,state", [("2026-02-30T12:00:00Z", "invalid"), ("not a timestamp", "invalid"), ("2026-10-31T12:00:00", "offset_unknown"), ("2026-10-31T12:00:00.1234567Z", "invalid"), ("2026-10-31T12:00:00+24:00", "invalid"), ("2026-10-31T12:00:00+05:99", "invalid")])
def test_timestamp_uncertainty(value, state):
    row = payload()
    row["@timestamp"] = value  # Deliberate validator mutation, not a dataset finding.
    result = validate(row)
    assert result.status == "partial"
    assert result.event.timestamp.state == state
    assert result.event.timestamp.raw == value
    assert result.event.timestamp.utc is None


def test_explicit_offset_is_normalized_without_assuming_local_zone():
    row = payload()
    row["@timestamp"] = "2026-10-31T12:00:00.123+05:30"
    event = validate(row).event
    assert event.timestamp.utc == datetime(2026, 10, 31, 6, 30, 0, 123000, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        EventTime(raw=row["@timestamp"], state="known", utc=datetime(2026, 10, 31, tzinfo=timezone.utc))


@pytest.mark.parametrize("field", ["host", "source", "destination", "dns"])
def test_invalid_ip_rejected_with_raw_provenance(field):
    row = payload()
    row[field] = {"ip": ["999.1.2.3"]} if field == "host" else {"resolved_ip": ["bad-ip"]} if field == "dns" else {"ip": "999.1.2.3"}
    result = validate(row)
    assert result.status == "rejected"
    assert result.event is None
    assert result.issues == ["invalid_source_fields"]
    assert result.provenance.raw_sha256


def test_ipv6_supported_by_contract_without_claiming_it_was_observed():
    row = payload()
    row["host"]["ip"] = ["2001:db8::1"]
    assert str(validate(row).event.host.ip[0]) == "2001:db8::1"


@pytest.mark.parametrize("raw", [b'{"broken":\n', b'[]\n', b'\xff\n', b'{"a":1,"a":2}\n', b'{"a":NaN}\n'])
def test_malformed_records_keep_evidence_reference(raw):
    ref = provenance(raw)
    result = validate_json_record(raw, ref)
    assert result.status == "rejected"
    assert result.provenance == ref
    assert result.event is None


@pytest.mark.parametrize("field,value", [("process", "wrong-type"), ("host", {"os": []}), ("event", {"severity": "8"}), ("source", {"port": 65536}), ("source", {"ip": 123}), ("@timestamp", 1700000000)])
def test_wrong_types_do_not_silently_coerce(field, value):
    row = payload()
    row[field] = value
    assert validate(row).status == "rejected"


def test_unknown_types_and_extensions_are_preserved():
    row = payload()
    row["event"]["type"] = ["future-source-type"]
    row["future_vendor_section"] = {"key": None}
    result = validate(row)
    assert result.status == "valid"
    assert result.event.event.type == ["future-source-type"]
    assert result.event.source_fields["future_vendor_section"] == {"key": None}
    assert "detection" not in type(result.event).model_fields


def test_source_record_replay_and_distinct_occurrences():
    raw = FIXTURES["records"][0]["raw"].encode()
    first = provenance(raw)
    other_batch = provenance(raw, batch_id=UUID("00000000-0000-4000-8000-000000000002"))
    second_occurrence = provenance(raw, record_number=2, byte_offset=len(raw))
    assert identities(first) == identities(other_batch)
    assert identities(first) != identities(second_occurrence)
    assert first.raw_sha256 == second_occurrence.raw_sha256
    changed_transform = provenance(raw, transformation_version="simedr-json/2.0.0")
    assert identities(first)[0] == identities(changed_transform)[0]
    assert identities(first)[1] != identities(changed_transform)[1]


def test_evidence_tampering_and_unsupported_format():
    raw = b'{}\n'
    assert validate_json_record(b'[]\n', provenance(raw)).issues == ["evidence_mismatch"]
    assert validate_json_record(raw, provenance(raw, source_format="cef")).issues == ["unsupported_source_profile"]
    assert validate_json_record(raw, provenance(raw, synthetic=False)).issues == ["unsupported_source_profile"]


def test_required_provenance_and_unknown_canonical_keys():
    with pytest.raises(ValidationError):
        Provenance.model_validate({})
    event = validate(payload()).event
    for change in ({"schema_version": "2.0.0"}, {"unexpected_key": True}, {"source_record_id": "0" * 64}):
        data = {**event.model_dump(mode="json"), **change}
        with pytest.raises(ValidationError):
            CanonicalEvent.model_validate_json(json.dumps(data))
    with pytest.raises(ValidationError):
        RecordValidation(status="valid", provenance=event.provenance)


def test_contract_bounds_reject_oversized_records_and_fields():
    raw = b'{}\n'
    assert validate_json_record(b' ' * (1024 * 1024 + 1), provenance(raw)).issues == ["record_too_large"]
    row = payload()
    row["user"]["name"] = "x" * 65537
    assert validate(row).status == "rejected"


def test_arrow_parquet_round_trip_of_real_fixtures(tmp_path):
    events = [validate(json.loads(fixture["raw"])).event for fixture in FIXTURES["records"]]
    events += [validate({}).event, validate({"@timestamp": None, "host": None}).event, validate({"@timestamp": "bad-time"}).event]
    table = pa.Table.from_pylist([to_arrow_row(event) for event in events], schema=ARROW_SCHEMA)
    target = tmp_path / "bounded-test.parquet"
    pq.write_table(table, target, row_group_size=8)
    restored = pq.read_table(target)
    assert restored.schema.metadata == ARROW_SCHEMA.metadata
    for expected, actual in zip(events, restored.to_pylist(), strict=True):
        assert from_arrow_row(actual) == expected


def test_versioned_artifacts_match_python_definitions():
    for name, model in (("event.schema.json", CanonicalEvent), ("validation.schema.json", RecordValidation)):
        assert json.loads((ROOT / "schemas/v1" / name).read_text()) == model.model_json_schema()
    assert (ROOT / "schemas/v1/arrow-schema.txt").read_text() == str(ARROW_SCHEMA) + "\n"


def test_local_generator_target_digest_and_overwrite_protection(tmp_path):
    spec = importlib.util.spec_from_file_location("generate_sample", ROOT / "scripts/generate_sample.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    target = tmp_path / "sample.jsonl"
    manifest = generator.generate(target, 4096, alert_ratio=1)
    raw = target.read_bytes()  # Tiny test fixture, not the 1 GiB dataset.
    assert 4096 <= len(raw) < 4096 + 4096
    assert manifest["sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(raw.splitlines()) == manifest["records"] == manifest["simulated_alerts"]
    assert all(json.loads(line)["labels"]["simulated_detection"] == "true" for line in raw.splitlines())
    with pytest.raises(FileExistsError):
        generator.generate(target, 4096)


def test_profiler_counts_duplicates_missing_and_invalid_values(tmp_path):
    spec = importlib.util.spec_from_file_location("profile_sample", ROOT / "scripts/profile_sample.py")
    profiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profiler)
    # Deliberately mutated tiny validator inputs, not claims about the 1 GiB file.
    original = FIXTURES["records"][0]["raw"].encode()
    changed = payload()
    changed["@timestamp"] = "bad-time"
    changed["host"]["ip"] = ["not-an-ip"]
    target = tmp_path / "profiling-input.jsonl"
    target.write_bytes(original + original + (json.dumps(changed) + "\n").encode() + b'{}\n{"broken":\n')
    report_path = tmp_path / "report.json"
    report = profiler.profile(target, report_path)
    assert report["counts"]["physical_lines"] == 5
    assert report["counts"]["duplicate_raw_records"] == 1
    assert report["counts"]["duplicate_event_ids"] == 2
    assert report["counts"]["malformed_records"] == 1
    assert report["counts"]["invalid_timestamp"] == report["counts"]["invalid_ip_values"] == 1
    assert report["fields"]["host.name"]["missing_records"] == 1
    assert not report_path.with_suffix(".sqlite").exists()
