"""Bounded format recognition for direct local-file scans, never conversion."""
import json
from app.convert_logs import parse_key_values
from app.log_formats import COMBINED
from app.contracts.v1 import unique_object, reject_constant


def probe_source(path):
    profiles=set(); examined=0; malformed=0; budget=256*1024
    with path.open('rb') as stream:
        for _ in range(32):
            raw=stream.readline(budget+1)
            if not raw: break
            if len(raw)>budget: break
            budget-=len(raw)
            if not raw.strip(): continue
            examined+=1
            try:
                message=raw.decode('utf-8').rstrip('\r\n')
                if message.lstrip().startswith('{'):
                    value=json.loads(message,object_pairs_hook=unique_object,parse_constant=reject_constant)
                    if not isinstance(value,dict): raise ValueError()
                    profile='simedr-json-1.0.0' if isinstance(value.get('observer'),dict) and value['observer'].get('product')=='SimEDR' else 'json-record-1.0.0'
                elif COMBINED.fullmatch(message): profile='web-combined-1.0.0'
                else:
                    values=parse_key_values(message)
                    known={'date','time','tz','type','subtype','action','logid'}<=values.keys() and bool(values.get('devid') or values.get('devname'))
                    profile='firex-kv-1.0.0' if known else 'key-value-1.0.0'
                profiles.add(profile)
            except (ValueError,UnicodeError,RecursionError): malformed+=1
            if budget<=0: break
    profile=next(iter(profiles)) if len(profiles)==1 else None
    return dict(source_profile=profile,synthetic=profile=='simedr-json-1.0.0',
                can_analyze=profile in {'firex-kv-1.0.0','simedr-json-1.0.0'},
                records_examined=examined,malformed_sample_records=malformed,
                message='Recognized from a bounded sample; every record is validated during the scan.' if profile else 'Format is unknown or mixed. Choose an inspected source adapter in advanced options.')
