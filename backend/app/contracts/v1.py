"""Canonical v1 derived from the inspected synthetic SimEDR JSONL sample."""
import hashlib
import json
import re
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, IPvAnyAddress, JsonValue, ValidationError, model_validator

SCHEMA_VERSION = "1.0.0"
TRANSFORMATION_VERSION = "simedr-json/1.0.0"
MAX_RECORD_BYTES = 1024 * 1024
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, Field(max_length=65536)]
Name = Annotated[str, Field(min_length=1, max_length=256)]
StringList = Annotated[list[Text], Field(max_length=256)]


def strict_ip(value):
    if not isinstance(value, (str, IPv4Address, IPv6Address)):
        raise ValueError("IP address must be text, not a coerced integer")
    return value


IPAddress = Annotated[IPvAnyAddress, BeforeValidator(strict_ip)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Provenance(ContractModel):
    original_file: Annotated[str, Field(min_length=1, max_length=2048)]
    artifact_sha256: Digest
    source_id: Name
    source_format: Annotated[str, Field(min_length=1, max_length=64)]
    record_number: Annotated[int, Field(ge=1, le=2**63 - 1)]
    byte_offset: Annotated[int, Field(ge=0, le=2**63 - 1)]
    byte_length: Annotated[int, Field(ge=1, le=MAX_RECORD_BYTES)]
    raw_sha256: Digest
    batch_id: UUID
    transformation_version: Name
    synthetic: bool


class EventTime(ContractModel):
    raw: Text | None = None
    state: Literal["known", "missing", "invalid", "offset_unknown"]
    utc: AwareDatetime | None = None

    @model_validator(mode="after")
    def consistent_time(self) -> Self:
        if self.state == "missing":
            if self.raw is not None or self.utc is not None:
                raise ValueError("missing timestamp cannot contain a value")
        elif self.raw is None:
            raise ValueError("non-missing timestamp needs its original string")
        if self.state == "known":
            parsed = parse_instant(self.raw)
            if parsed is None or parsed.tzinfo is None or self.utc is None:
                raise ValueError("known timestamp requires explicit offset and UTC instant")
            if self.utc.utcoffset().total_seconds() != 0 or self.utc != parsed:
                raise ValueError("UTC instant must agree with original timestamp")
        elif self.utc is not None:
            raise ValueError("uncertain timestamp must not claim a UTC instant")
        if self.state == "offset_unknown":
            parsed = parse_instant(self.raw)
            if parsed is None or parsed.tzinfo is not None:
                raise ValueError("offset_unknown requires a valid offset-free timestamp")
        if self.state == "invalid" and parse_instant(self.raw) is not None:
            raise ValueError("valid timestamp cannot be marked invalid")
        return self


def parse_instant(value: str | None) -> datetime | None:
    # No numeric epoch guess, date-only coercion, precision truncation or local timezone inference.
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?", value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def event_time(raw: str | None) -> EventTime:
    if raw is None:
        return EventTime(state="missing")
    instant = parse_instant(raw)
    if instant is None:
        return EventTime(raw=raw, state="invalid")
    if instant.tzinfo is None:
        return EventTime(raw=raw, state="offset_unknown")
    return EventTime(raw=raw, state="known", utc=instant.astimezone(timezone.utc))


class EventFields(ContractModel):
    id: Text | None = None
    kind: Text | None = None
    category: StringList | None = None
    type: StringList | None = None
    action: Text | None = None
    severity: Annotated[int, Field(ge=0, le=10)] | None = None
    outcome: Text | None = None
    module: Text | None = None
    dataset: Text | None = None


class Host(ContractModel):
    name: Text | None = None
    hostname: Text | None = None
    ip: Annotated[list[IPAddress], Field(max_length=256)] | None = None
    os_type: Text | None = None
    os_full: Text | None = None


class User(ContractModel):
    name: Text | None = None
    domain: Text | None = None


class Process(ContractModel):
    pid: Annotated[int, Field(ge=0, le=2**63 - 1)] | None = None
    name: Text | None = None
    executable: Text | None = None
    command_line: Text | None = None
    entity_id: Text | None = None
    parent_pid: Annotated[int, Field(ge=0, le=2**63 - 1)] | None = None
    parent_name: Text | None = None
    hashes: dict[str, Text] | None = None


class Endpoint(ContractModel):
    ip: IPAddress | None = None
    port: Annotated[int, Field(ge=0, le=65535)] | None = None
    domain: Text | None = None


class CanonicalEvent(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    source_profile: Literal["simedr-json-1.0.0"] = "simedr-json-1.0.0"
    provenance: Provenance
    source_record_id: Digest
    normalization_id: Digest
    timestamp: EventTime
    event: EventFields | None = None
    host: Host | None = None
    user: User | None = None
    process: Process | None = None
    source: Endpoint | None = None
    destination: Endpoint | None = None
    dns_resolved_ips: Annotated[list[IPAddress], Field(max_length=256)] | None = None
    # Lossless semantic copy of source JSON, including fields not promoted to typed columns.
    # Raw byte evidence remains in the referenced file, including absent/null distinctions.
    source_fields: dict[str, JsonValue]

    @model_validator(mode="after")
    def identities_match(self) -> Self:
        record_id, normalization_id = identities(self.provenance)
        if self.source_record_id != record_id or self.normalization_id != normalization_id:
            raise ValueError("identities disagree with provenance")
        if self.provenance.source_format != "jsonl" or self.provenance.transformation_version != TRANSFORMATION_VERSION:
            raise ValueError("source profile requires the SimEDR JSONL transformation")
        if not self.provenance.synthetic:
            raise ValueError("this source profile is synthetic")
        encoded = json.dumps(self.source_fields, ensure_ascii=True, allow_nan=False).encode("utf-8")
        if len(encoded) > 2 * MAX_RECORD_BYTES:
            raise ValueError("source field payload exceeds contract bound")
        return self


class RecordValidation(ContractModel):
    validation_version: Literal["1.0.0"] = "1.0.0"
    status: Literal["valid", "partial", "rejected"]
    provenance: Provenance
    issues: Annotated[list[Name], Field(max_length=32)] = Field(default_factory=list)
    event: CanonicalEvent | None = None

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        if self.status == "rejected":
            if self.event is not None or not self.issues:
                raise ValueError("rejected result requires issues and no normalized event")
        elif self.event is None or self.event.provenance != self.provenance:
            raise ValueError("accepted result needs matching event provenance")
        elif self.status == "valid" and self.issues:
            raise ValueError("valid result cannot contain validation issues")
        elif self.status == "partial" and not self.issues:
            raise ValueError("partial result requires issues")
        return self


def identities(provenance: Provenance) -> tuple[str, str]:
    locator = [provenance.source_id, provenance.artifact_sha256, provenance.byte_offset, provenance.byte_length, provenance.raw_sha256]
    source_record_id = hashlib.sha256(json.dumps(locator, separators=(",", ":")).encode()).hexdigest()
    normalization_id = hashlib.sha256(f"{source_record_id}:{SCHEMA_VERSION}:{provenance.transformation_version}".encode()).hexdigest()
    return source_record_id, normalization_id


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"non-JSON constant: {value}")


def validate_json_record(raw: bytes, provenance: Provenance) -> RecordValidation:
    """Validate one bounded record; no source discovery, batching, persistence or detection.

    The caller supplies a verified immutable artifact manifest and byte locator.
    Source byte length/digest are verified here; artifact hash is not recomputed per row.
    """
    def rejected(reason):
        return RecordValidation(status="rejected", provenance=provenance, issues=[reason])

    if len(raw) > MAX_RECORD_BYTES:
        return rejected("record_too_large")
    if len(raw) != provenance.byte_length or hashlib.sha256(raw).hexdigest() != provenance.raw_sha256:
        return rejected("evidence_mismatch")
    if provenance.source_format != "jsonl" or provenance.transformation_version != TRANSFORMATION_VERSION or not provenance.synthetic:
        return rejected("unsupported_source_profile")
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=unique_object, parse_constant=reject_constant)
        if not isinstance(payload, dict):
            return rejected("record_not_object")
    except (UnicodeDecodeError, ValueError, RecursionError):
        return rejected("malformed_json_or_encoding")

    try:
        stamp = event_time(payload.get("@timestamp"))
        event_source = payload.get("event")
        host_source = payload.get("host")
        user_source = payload.get("user")
        process_source = payload.get("process")
        # Mapped objects must be objects or null; never silently erase malformed input.
        for obj in (event_source, host_source, user_source, process_source, payload.get("source"), payload.get("destination"), payload.get("dns")):
            if obj is not None and not isinstance(obj, dict):
                return rejected("invalid_source_field_type")

        def selected(obj, keys):
            return {key: obj[key] for key in keys if key in obj}

        event = EventFields(**selected(event_source, EventFields.model_fields)) if event_source is not None else None
        host = None
        if host_source is not None:
            os_data = host_source.get("os")
            if os_data is not None and not isinstance(os_data, dict):
                return rejected("invalid_source_field_type")
            host = Host(**selected(host_source, ("name", "hostname", "ip")), os_type=(os_data or {}).get("type"), os_full=(os_data or {}).get("full"))
        user = User(**selected(user_source, User.model_fields)) if user_source is not None else None
        process = None
        if process_source is not None:
            parent = process_source.get("parent")
            if parent is not None and not isinstance(parent, dict):
                return rejected("invalid_source_field_type")
            process = Process(**selected(process_source, ("pid", "name", "executable", "command_line", "entity_id")), parent_pid=(parent or {}).get("pid"), parent_name=(parent or {}).get("name"), hashes=process_source.get("hash"))
        record_id, normalization_id = identities(provenance)
        result = CanonicalEvent(provenance=provenance, source_record_id=record_id, normalization_id=normalization_id, timestamp=stamp,
            event=event, host=host, user=user, process=process,
            source=Endpoint(**selected(payload["source"], Endpoint.model_fields)) if payload.get("source") is not None else None,
            destination=Endpoint(**selected(payload["destination"], Endpoint.model_fields)) if payload.get("destination") is not None else None,
            dns_resolved_ips=(payload.get("dns") or {}).get("resolved_ip"), source_fields=payload)
    except (ValidationError, ValueError, TypeError, AttributeError, RecursionError):
        return rejected("invalid_source_fields")
    issues = []
    if stamp.state != "known":
        issues.append(f"timestamp_{stamp.state}")
    if "@timestamp" in payload and payload["@timestamp"] is None:
        issues.append("timestamp_explicit_null")
    return RecordValidation(status="partial" if issues else "valid", provenance=provenance, issues=issues, event=result)
