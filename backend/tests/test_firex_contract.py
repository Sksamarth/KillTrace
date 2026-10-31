"""Synthetic records express observed field syntax, not planted attacks."""
import hashlib
from uuid import uuid4
from pathlib import Path
import json

from app.contracts.firex_v21 import FirexEvent, FirexValidation, validate_firex, TRANSFORM
from app.contracts.v1 import Provenance


def validate(raw, offset=0):
    ref=Provenance(original_file='synthetic-test.log',artifact_sha256='a'*64,
        source_id='test',source_format='key-value',record_number=1,byte_offset=offset,
        byte_length=len(raw),raw_sha256=hashlib.sha256(raw).hexdigest(),batch_id=uuid4(),
        transformation_version=TRANSFORM,synthetic=True)
    return validate_firex(raw,ref)


def test_typed_fields_preserve_observer_and_original_precision():
    result=validate(b'date=2026-10-23 time=08:48:26 tz=+0530 devid=observer user=test srcip=192.0.2.1 dstip=198.51.100.2 dstport=443 type=traffic subtype=forward action=deny eventtime=1792745306000000000\n')
    assert result.status=='valid'
    event=result.event
    assert event.host is None and event.process is None
    assert event.user.name=='test' and str(event.source.ip)=='192.0.2.1'
    assert event.destination.port==443 and event.timestamp.utc.hour==3
    assert event.source_fields['fields']['eventtime']=='1792745306000000000'
    assert event.source_fields['fields']['devid']=='observer'


def test_missing_and_bad_fields_preserve_uncertainty():
    result=validate(b'srcip=not-an-ip dstport=99999 action=unknown-new-action\n')
    assert result.status=='partial'
    assert set(result.issues)=={'timestamp_missing','srcip_invalid','dstport_invalid'}
    assert result.event.source is None and result.event.destination is None
    assert result.event.event.action=='unknown-new-action'
    assert validate(b'date=invalid time=no tz=+0530').event.timestamp.state=='invalid'
    assert validate(b'broken record').status=='rejected'
    assert validate(b'key=a key=b').status=='rejected'
    assert validate(b'\xff').status=='rejected'


def test_duplicate_content_has_distinct_occurrence_identity():
    raw=b'action=login\n'
    assert validate(raw).event.source_record_id!=validate(raw,10).event.source_record_id


def test_published_schema_matches_models():
    directory=Path(__file__).resolve().parents[2]/'schemas'/'v2.1'
    for name,model in [('event.schema.json',FirexEvent),('validation.schema.json',FirexValidation)]:
        assert json.loads((directory/name).read_text())==model.model_json_schema()


def test_ingestion_checkpoint_and_storage_roundtrip(tmp_path):
    from app.config import Settings
    from app.jobs import create_job, cancel, prepare_resume
    from app.ingestion import run_job
    from app.contracts.arrow_v1 import from_arrow_row
    import pyarrow.parquet as pq
    inputs=tmp_path/'input';inputs.mkdir()
    raw=b'date=2026-10-23 time=08:48:26 tz=+0530 srcip=192.0.2.1 dstport=443 user=test type=traffic\n'
    (inputs/'sample.log').write_bytes(raw+raw+b'bad framing\n')
    settings=Settings(data_dir=tmp_path/'out',ingestion_input_dir=inputs)
    work=create_job(settings,'sample.log',source_profile='firex-kv-1.0.0',synthetic=True)
    cancel(settings,work.name)
    assert run_job(work)['status']=='cancelled'
    result=run_job(prepare_resume(settings,work.name))
    assert result['status']=='completed' and result['records_accepted']==2 and result['records_rejected']==1
    events=[]
    for part in (work/'events').rglob('*.parquet'):
        table=pq.ParquetFile(part).read()
        assert table.schema.metadata[b'killchain.schema_version']==b'2.1.0'
        events.extend(from_arrow_row(row) for row in table.to_pylist())
    assert all(str(event.source.ip)=='192.0.2.1' for event in events)
    assert len({event.source_record_id for event in events})==2
