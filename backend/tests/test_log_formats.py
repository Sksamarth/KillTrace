import hashlib
import json
from uuid import uuid4

import pyarrow.parquet as pq
import pytest
from app.config import Settings
from app.contracts.v1 import Provenance
from app.contracts.arrow_v1 import from_arrow_row
from app.log_formats import validate_log_record, PROFILES
from app.jobs import create_job, prepare_resume, cancel
from app.ingestion import run_job

ACCESS = b'127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "-" "Test client"\n'

def check(raw, profile):
    fmt, version = PROFILES[profile]
    ref=Provenance(original_file='test.log',artifact_sha256=hashlib.sha256(raw).hexdigest(),source_id='test',source_format=fmt,record_number=1,byte_offset=0,byte_length=len(raw),raw_sha256=hashlib.sha256(raw).hexdigest(),batch_id=uuid4(),transformation_version=version,synthetic=False)
    return validate_log_record(raw,ref,profile)

def test_combined_fields_and_explicit_timezone():
    result=check(ACCESS,'web-combined-1.0.0')
    assert result.status=='valid'
    assert result.event.schema_version=='2.0.0'
    assert not result.event.provenance.synthetic
    assert result.event.timestamp.utc.hour==20
    assert str(result.event.source.ip)=='127.0.0.1'
    assert result.event.source_fields['response_bytes']==2326
    assert result.event.source_fields['authenticated_user']=='frank'
    assert result.event.host is None

@pytest.mark.parametrize('raw',[b'not an access log\n',ACCESS.replace(b'200 2326',b'999 2326'),ACCESS.replace(b'2326',b'9'*100)])
def test_bad_combined_records_are_rejected(raw):
    assert check(raw,'web-combined-1.0.0').status=='rejected'

def test_bad_time_preserves_original_and_uncertainty():
    result=check(ACCESS.replace(b'10/Oct',b'99/Oct'),'web-combined-1.0.0')
    assert result.status=='partial' and result.event.timestamp.utc is None
    assert result.event.source_fields['timestamp'].startswith('99/Oct')

def test_raw_text_is_preserved_without_guessing_entities():
    result=check(b'Oct 31 server app: failed connection\r\n','raw-text-1.0.0')
    assert result.status=='partial'
    assert result.event.host is None and result.event.user is None
    assert result.event.source_fields['message']=='Oct 31 server app: failed connection'
    assert check(b'\xff','raw-text-1.0.0').status=='rejected'

@pytest.mark.parametrize('profile,raw',[('raw-text-1.0.0',b'plain server message\n'),('web-combined-1.0.0',ACCESS)])
def test_job_roundtrip_cancel_resume_and_duplicates(tmp_path,profile,raw):
    inputs=tmp_path/'input';inputs.mkdir()
    (inputs/'server.log').write_bytes(raw+raw)
    settings=Settings(data_dir=tmp_path/'output',ingestion_input_dir=inputs,ingestion_batch_rows=1,ingestion_memory_mb=1024)
    work=create_job(settings,'server.log',source_profile=profile,synthetic=False)
    cancel(settings,work.name)
    assert run_job(work)['status']=='cancelled'
    result=run_job(prepare_resume(settings,work.name))
    assert result['status']=='completed' and result['records_accepted']==2
    events=[]
    for part in (work/'events').rglob('*.parquet'):
        table=pq.ParquetFile(part).read()
        assert table.schema.metadata[b'killchain.schema_version']==b'2.0.0'
        events.extend(from_arrow_row(row) for row in table.to_pylist())
    assert len({event.source_record_id for event in events})==2
    assert all(event.source_profile==profile and not event.provenance.synthetic for event in events)


def test_api_accepts_non_synthetic_log_profile(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.job_store import supported_name
    (tmp_path/'server.log').write_text('server message\n')
    monkeypatch.setenv('KILLCHAIN_DATA_DIR',str(tmp_path/'out'))
    monkeypatch.setenv('KILLCHAIN_INGESTION_INPUT_DIR',str(tmp_path))
    monkeypatch.setattr('app.ingestion_routes.launch',lambda work:None)
    with TestClient(app) as client:
        result=client.post('/api/ingestion/jobs',json={'source':'server.log','source_profile':'raw-text-1.0.0','synthetic':False})
        assert result.status_code==202 and result.json()['synthetic'] is False
    assert supported_name('access_log') and supported_name('access.log.1')
    assert not supported_name('.env') and not supported_name('server.log.gz')


def test_key_value_strings_and_converter_evidence(tmp_path):
    from app.convert_logs import convert, parse_key_values
    raw=b'date=2026-10-23 time=08:48:26 tz="+0530" eventtime=1792745306000000000 msg="two words"\n'
    fields=parse_key_values(raw.decode())
    assert fields['eventtime']=='1792745306000000000' and fields['msg']=='two words'
    source=tmp_path/'firewall.log';source.write_bytes(raw+b'broken record\n')
    output=tmp_path/'converted.jsonl'
    result=convert(source,output)
    assert result['records']==2 and result['records_with_issues']==1
    lines=[json.loads(line) for line in output.read_text().splitlines()]
    assert lines[0]['fields']==fields
    assert lines[0]['raw_sha256']==hashlib.sha256(raw).hexdigest()
    assert lines[1]['message']=='broken record'
    event=check(raw,'key-value-1.0.0').event
    assert event.source_fields['fields']==fields
    assert event.timestamp.utc.hour==3 and event.timestamp.utc.minute==18
    with pytest.raises(FileExistsError): convert(source,output)
    with pytest.raises(ValueError): parse_key_values('key=one key=two')


def test_generic_json_does_not_guess_source_entities():
    result=check(b'{"custom":42,"hostname":"not-an-approved-host-map"}\n','json-record-1.0.0')
    assert result.status=='partial' and result.event.host is None
    assert result.event.source_fields['fields']['custom']==42
    assert check(b'{"a":1,"a":2}\n','json-record-1.0.0').status=='rejected'


def test_key_value_rejects_long_unstructured_and_bad_separators():
    from app.convert_logs import parse_key_values
    with pytest.raises(ValueError): parse_key_values('x'*100000)
    with pytest.raises(ValueError): parse_key_values('a="one"b=two')
    assert parse_key_values('a="one word" b=two')['a']=='one word'


def test_oversized_timestamp_is_a_record_rejection():
    raw = ACCESS.replace(b'10/Oct/2000:13:55:36 -0700', b'x' * 70000)
    assert check(raw, 'web-combined-1.0.0').issues == ['invalid_timestamp_field']


def test_converter_contains_malformed_json_and_keeps_valid_suffix(tmp_path):
    from app.convert_logs import convert
    source = tmp_path / 'input.jsonl'
    source.write_bytes(b'{"n":1e999}\n' + b'[' * 2000 + b'0' + b']' * 2000 + b'\n{"ok":true}\n')
    output = tmp_path / 'output.jsonl'
    result = convert(source, output, 'jsonl')
    assert result['records'] == 3 and result['records_with_issues'] == 2
    with output.open() as stream:
        assert 'issues' in json.loads(next(stream))
        assert 'issues' in json.loads(next(stream))
        assert json.loads(next(stream))['fields'] == {'ok': True}


def test_v2_schema_artifacts_match_models():
    from pathlib import Path
    from app.log_formats import CanonicalLogEvent, LogValidation
    root = Path(__file__).resolve().parents[2] / 'schemas' / 'v2'
    for name, model in [('event.schema.json', CanonicalLogEvent), ('validation.schema.json', LogValidation)]:
        assert json.loads((root / name).read_text(encoding='utf-8')) == model.model_json_schema()
