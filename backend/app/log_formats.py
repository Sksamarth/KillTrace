"""Explicit line-oriented raw/server profiles; no format or timezone guessing."""
import hashlib
import ipaddress
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import Field, model_validator

from app.contracts.v1 import CanonicalEvent, ContractModel, EventFields, Endpoint, EventTime, Provenance, event_time, identities, MAX_RECORD_BYTES

PROFILES = {"simedr-json-1.0.0": ("jsonl", "simedr-json/1.0.0"), "raw-text-1.0.0": ("text", "raw-text/1.0.0"), "web-combined-1.0.0": ("web-combined", "web-combined/1.0.0"), "key-value-1.0.0": ("key-value", "key-value/1.0.0"), "json-record-1.0.0": ("jsonl", "json-record/1.0.0")}
PROFILES['firex-kv-1.0.0'] = ('key-value', 'firex-kv/1.0.0')


class CanonicalLogEvent(CanonicalEvent):
    schema_version: Literal["2.0.0"] = "2.0.0"
    source_profile: Literal["raw-text-1.0.0", "web-combined-1.0.0", "key-value-1.0.0", "json-record-1.0.0"]

    @model_validator(mode="after")
    def identities_match(self):
        profile = PROFILES[self.source_profile]
        if (self.provenance.source_format, self.provenance.transformation_version) != profile:
            raise ValueError("source provenance disagrees with parser profile")
        record_id = identities(self.provenance)[0]
        normalized = hashlib.sha256(f"{record_id}:2.0.0:{profile[1]}".encode()).hexdigest()
        if self.source_record_id != record_id or self.normalization_id != normalized:
            raise ValueError("identity does not match provenance")
        if len(json.dumps(self.source_fields, ensure_ascii=True, allow_nan=False).encode()) > 2 * MAX_RECORD_BYTES:
            raise ValueError("source payload exceeds contract bound")
        return self


class LogValidation(ContractModel):
    provenance: Provenance
    status: Literal["valid", "partial", "rejected"]
    issues: list[str] = Field(default_factory=list, max_length=32)
    event: CanonicalLogEvent | None = None

    @model_validator(mode="after")
    def consistent(self):
        if self.status == 'rejected':
            if self.event is not None or not self.issues:
                raise ValueError("rejection needs issues and no event")
        elif self.event is None or self.event.provenance != self.provenance:
            raise ValueError("accepted event needs matching provenance")
        elif (self.status == 'valid') == bool(self.issues):
            raise ValueError("valid/partial outcomes must agree with issues")
        return self


QUOTED = r'"((?:[^"\\]|\\.)*)"'
COMBINED = re.compile(r'^(\S+) (\S+) (\S+) \[([^\]]+)\] ' + QUOTED + r' ([0-9]{3}) ([0-9]+|-) ' + QUOTED + ' ' + QUOTED + '$')
MONTHS = {name: index for index, name in enumerate(('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'), 1)}


def access_time(value):
    match = re.fullmatch(r'(\d{2})/([A-Za-z]{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2}) ([+-])(\d{2})(\d{2})', value)
    if not match:
        return EventTime(raw=value, state="invalid")
    day, month, year, hour, minute, second, sign, zh, zm = match.groups()
    try:
        if int(zh) > 23 or int(zm) > 59:
            raise ValueError("invalid offset")
        zone = timezone(timedelta(minutes=(1 if sign == '+' else -1) * (int(zh)*60+int(zm))))
        instant = datetime(int(year), MONTHS[month], int(day), int(hour), int(minute), int(second), tzinfo=zone)
        # Canonical EventTime requires its raw representation to be ISO. Preserve
        # the original access-log timestamp separately in source_fields.
        return event_time(instant.isoformat())
    except (ValueError, KeyError):
        return EventTime(raw=value, state="invalid")


def validate_log_record(raw: bytes, provenance: Provenance, profile: str):
    if profile == 'firex-kv-1.0.0':
        from app.contracts.firex_v21 import validate_firex
        return validate_firex(raw, provenance)
    def reject(code):
        return LogValidation(status="rejected", provenance=provenance, issues=[code])
    if len(raw) > MAX_RECORD_BYTES:
        return reject("record_too_large")
    if len(raw) != provenance.byte_length or hashlib.sha256(raw).hexdigest() != provenance.raw_sha256:
        return reject("evidence_mismatch")
    try:
        message = raw.decode('utf-8', errors='strict').removesuffix('\n').removesuffix('\r')
    except UnicodeDecodeError:
        return reject("invalid_utf8")
    fields = {"message": message}
    stamp = event_time(None)
    event = source = None
    issues = ["unstructured_record", "timestamp_missing"]
    if profile == "web-combined-1.0.0":
        match = COMBINED.fullmatch(message)
        if not match:
            return reject("invalid_combined_log")
        client, ident, user, timestamp, request, status, size, referer, agent = match.groups()
        if len(timestamp) > 65536:
            return reject("invalid_timestamp_field")
        if len(size) > 19 or (size != '-' and int(size) > 2**63 - 1):
            return reject("invalid_response_size")
        if not 100 <= int(status) <= 599:
            return reject("invalid_http_status")
        fields.update(client=client, ident=ident, authenticated_user=user, timestamp=timestamp, request=request, status=int(status), response_bytes=None if size == '-' else int(size), referer=referer, user_agent=agent)
        stamp = access_time(timestamp)
        event = EventFields(category=["web"], type=["access"], action="http_request")
        try:
            source = Endpoint(ip=ipaddress.ip_address(client))
        except ValueError:
            pass  # Apache %h can be a hostname; never resolve or invent an IP.
        issues = [] if stamp.state == 'known' else ['timestamp_invalid']
    elif profile in {"key-value-1.0.0", "json-record-1.0.0"}:
        try:
            if profile == "key-value-1.0.0":
                from app.convert_logs import parse_key_values
                fields["fields"] = parse_key_values(message)
            else:
                from app.contracts.v1 import unique_object, reject_constant
                fields["fields"] = json.loads(message, object_pairs_hook=unique_object, parse_constant=reject_constant)
                if not isinstance(fields["fields"], dict):
                    return reject("record_not_object")
            issues = ["timestamp_missing"]
            if profile == "key-value-1.0.0":
                values = fields["fields"]
                if all(key in values for key in ("date", "time", "tz")):
                    zone = values["tz"]
                    if re.fullmatch(r'[+-]\d{4}', zone):
                        zone = zone[:3] + ':' + zone[3:]
                    stamp = event_time(f"{values['date']}T{values['time']}{zone}")
                    issues = [] if stamp.state == 'known' else ['timestamp_invalid']
        except (ValueError, RecursionError):
            return reject("invalid_structured_record")
    elif profile != "raw-text-1.0.0":
        return reject("unsupported_source_profile")
    try:
        record_id = identities(provenance)[0]
        normalized = hashlib.sha256(f"{record_id}:2.0.0:{provenance.transformation_version}".encode()).hexdigest()
        result = CanonicalLogEvent(source_profile=profile, provenance=provenance, source_record_id=record_id, normalization_id=normalized, timestamp=stamp, event=event, source=source, source_fields=fields)
        return LogValidation(status="partial" if issues else "valid", provenance=provenance, issues=issues, event=result)
    except ValueError:
        return reject("invalid_source_fields")
