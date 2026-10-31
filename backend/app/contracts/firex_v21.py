"""Observed local FireX key/value contract; not a vendor-format guarantee."""
import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from app.contracts.v1 import CanonicalEvent, ContractModel, Endpoint, EventFields, User, Provenance, MAX_RECORD_BYTES, event_time, identities
from app.convert_logs import parse_key_values

VERSION = '2.1.0'
PROFILE = 'firex-kv-1.0.0'
TRANSFORM = 'firex-kv/1.0.0'


class FirexEvent(CanonicalEvent):
    schema_version: Literal['2.1.0'] = VERSION
    source_profile: Literal['firex-kv-1.0.0'] = PROFILE

    @model_validator(mode='after')
    def identities_match(self):
        ref = self.provenance
        record = identities(ref)[0]
        normalized = hashlib.sha256(f'{record}:{VERSION}:{TRANSFORM}'.encode()).hexdigest()
        if ref.source_format != 'key-value' or ref.transformation_version != TRANSFORM:
            raise ValueError('incorrect FireX provenance')
        if self.source_record_id != record or self.normalization_id != normalized:
            raise ValueError('identity disagrees with evidence')
        if len(json.dumps(self.source_fields, ensure_ascii=True, allow_nan=False).encode()) > 2*MAX_RECORD_BYTES:
            raise ValueError('source payload exceeds bound')
        return self


class FirexValidation(ContractModel):
    status: Literal['valid','partial','rejected']
    provenance: Provenance
    issues: list[str] = Field(max_length=32)
    event: FirexEvent | None = None

    @model_validator(mode='after')
    def consistent(self):
        if self.status == 'rejected':
            if self.event is not None or not self.issues:
                raise ValueError('invalid rejection')
        elif self.event is None or self.event.provenance != self.provenance:
            raise ValueError('accepted result needs matching evidence')
        elif (self.status == 'valid') == bool(self.issues):
            raise ValueError('issues disagree with status')
        return self


def validate_firex(raw: bytes, ref: Provenance):
    def reject(issue):
        return FirexValidation(status='rejected',provenance=ref,issues=[issue])
    if len(raw)>MAX_RECORD_BYTES:
        return reject('record_too_large')
    if len(raw)!=ref.byte_length or hashlib.sha256(raw).hexdigest()!=ref.raw_sha256:
        return reject('evidence_mismatch')
    try:
        message=raw.decode('utf-8').removesuffix('\n').removesuffix('\r')
        fields=parse_key_values(message)
        stamp=event_time(None)
        if all(key in fields for key in ('date','time','tz')):
            zone=fields['tz']
            if len(zone)==5 and zone[0] in '+-' and zone[1:].isascii() and zone[1:].isdigit():
                zone=zone[:3]+':'+zone[3:]
            stamp=event_time(f"{fields['date']}T{fields['time']}{zone}")
        issues=[] if stamp.state=='known' else ['timestamp_'+stamp.state]
        def endpoint(prefix):
            mapped={}
            value=fields.get(prefix+'ip')
            if value:
                try:
                    mapped['ip']=Endpoint(ip=value).ip
                except ValueError:
                    issues.append(prefix+'ip_invalid')
            port=fields.get(prefix+'port')
            if port:
                if port.isascii() and port.isdecimal() and len(port)<=5 and 0<=int(port)<=65535:
                    mapped['port']=int(port)
                else:
                    issues.append(prefix+'port_invalid')
            return Endpoint(**mapped) if mapped else None
        source,destination=endpoint('src'),endpoint('dst')
        record=identities(ref)[0]
        result=FirexEvent(provenance=ref,source_record_id=record,
            normalization_id=hashlib.sha256(f'{record}:{VERSION}:{TRANSFORM}'.encode()).hexdigest(),
            timestamp=stamp,source=source,destination=destination,
            user=User(name=fields['user']) if fields.get('user') else None,
            event=EventFields(category=[fields['type']] if fields.get('type') else None,
                              type=[fields['subtype']] if fields.get('subtype') else None,
                              action=fields.get('action'),
                              outcome={'failed':'failure','success':'success'}.get(fields.get('status'))
                              if fields.get('type')=='event' and fields.get('action')=='login' else None),
            source_fields={'message':message,'fields':fields})
        return FirexValidation(status='partial' if issues else 'valid',provenance=ref,issues=issues,event=result)
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        return reject('malformed_or_invalid_source_fields')
