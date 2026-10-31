"""Inspect an authorized bounded FireX sample without printing private values."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from app.contracts.firex_v21 import validate_firex, TRANSFORM
from app.contracts.v1 import Provenance
from app.ingestion import records


def inspect(source, limit=1000):
    digest=hashlib.sha256()
    with source.open('rb') as stream:
        while block:=stream.read(1024**2):
            digest.update(block)
    counts,fields,issues=Counter(),Counter(),Counter()
    seen=set(); duplicates=0; inspected=0
    with source.open('rb') as stream:
        for number,offset,length,raw_hash,raw in records(stream):
            if number>limit: break
            inspected=number
            duplicates+=raw_hash in seen; seen.add(raw_hash)
            if raw is None:
                counts['rejected']+=1; issues['record_too_large']+=1
                continue
            ref=Provenance(original_file=str(source),artifact_sha256=digest.hexdigest(),source_id='local-firex',
                source_format='key-value',record_number=number,byte_offset=offset,byte_length=length,
                raw_sha256=raw_hash,batch_id=uuid4(),transformation_version=TRANSFORM,synthetic=False)
            result=validate_firex(raw,ref)
            counts[result.status]+=1; issues.update(result.issues)
            if result.event: fields.update(result.event.source_fields['fields'].keys())
    return dict(source_bytes=source.stat().st_size,artifact_sha256=digest.hexdigest(),records_inspected=inspected,
                validation=dict(counts),issues=dict(issues),duplicate_raw_records=duplicates,field_presence=dict(fields))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--limit',type=int,default=1000)
    args=parser.parse_args()
    if not 1<=args.limit<=10000: parser.error('limit must be 1..10000; duplicate tracking is bounded by this cap')
    print(json.dumps(inspect(args.source,args.limit),indent=2))
