"""Synthetic fixtures verify direct-file scanning without converted inputs."""
import time
from fastapi.testclient import TestClient
from app.main import app
from app.source_probe import probe_source


def test_probe_reads_original_firewall_records_and_rejects_unknown(tmp_path):
    file=tmp_path/'input.log'
    file.write_text('date=2026-10-31 time=12:00:00 tz=+0000 devid=lab logid=1 type=event subtype=system action=login\n')
    result=probe_source(file)
    assert result['source_profile']=='firex-kv-1.0.0' and result['can_analyze']
    file.write_text('unknown custom message\n')
    assert probe_source(file)['source_profile'] is None
    file.write_text('{"custom":1}\n')
    assert probe_source(file)['source_profile']=='json-record-1.0.0'
    assert not probe_source(file)['can_analyze']
    file.write_bytes(b'x'*(256*1024+1))
    assert probe_source(file)['records_examined']==0


def test_direct_scan_runs_detection_and_graph_without_frontend(tmp_path,monkeypatch):
    inputs=tmp_path/'input';inputs.mkdir()
    source=inputs/'original.log'
    source.write_text('\n'.join(f'date=2026-10-31 time=12:00:{i:02} tz=+0000 devid=lab logid=1 type=event subtype=system action=login status=failed srcip=192.0.2.10 user=example' for i in range(10))+'\n')
    monkeypatch.setenv('KILLCHAIN_DATA_DIR',str(tmp_path/'out'))
    monkeypatch.setenv('KILLCHAIN_INGESTION_INPUT_DIR',str(inputs))
    with TestClient(app) as client:
        assert client.get('/api/ingestion/probe',params={'source':'original.log'}).json()['can_analyze']
        assert client.get('/api/ingestion/probe',params={'source':'../outside.log'}).status_code==400
        response=client.post('/api/ingestion/jobs',json={'source':'original.log','source_profile':'auto','synthetic':True,'analyze_after':True})
        assert response.status_code==202,response.text
        job=response.json()
        assert job['source_profile']=='firex-kv-1.0.0' and job['analysis_requested']
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            state=client.get(f"/api/investigations/{job['job_id']}").json()
            if state['status'] in {'completed','failed','interrupted'}:break
            time.sleep(0.05)
        assert state['status']=='completed',state
        assert state['detections']==1 and state['records_scanned']==10
        graph=client.get(f"/api/investigations/{job['job_id']}/observed-graph")
        assert graph.status_code==200
        assert list(inputs.iterdir())==[source]  # No intermediate JSON/JSONL copy.


def test_auto_scan_does_not_silently_use_raw_text(tmp_path,monkeypatch):
    (tmp_path/'custom.log').write_text('unrecognized source\n')
    monkeypatch.setenv('KILLCHAIN_DATA_DIR',str(tmp_path/'out'))
    monkeypatch.setenv('KILLCHAIN_INGESTION_INPUT_DIR',str(tmp_path))
    with TestClient(app) as client:
        response=client.post('/api/ingestion/jobs',json={'source':'custom.log','source_profile':'auto','synthetic':False})
        assert response.status_code==400
        (tmp_path/'synthetic.jsonl').write_text('{"observer":{"product":"SimEDR"}}\n')
        response=client.post('/api/ingestion/jobs',json={'source':'synthetic.jsonl','source_profile':'auto','synthetic':False})
        assert response.status_code==400
        assert 'synthetic-source confirmation' in response.json()['detail']
