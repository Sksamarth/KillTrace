"""Explicit synthetic fixtures test rule behavior, not organizer ground truth."""
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analysis import analyze, incident_path, load_rules
from app.analysis import observation, writer_lock
from app.config import Settings
from app.ingestion import run_job
from app.jobs import create_job
from app.main import app


def ingest(tmp_path, lines, profile='key-value-1.0.0'):
    inputs = tmp_path / 'input'; inputs.mkdir()
    (inputs / 'test.log').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    settings = Settings(data_dir=tmp_path/'out', ingestion_input_dir=inputs)
    work = create_job(settings, 'test.log', source_profile=profile, synthetic=True)
    assert run_job(work)['status'] == 'completed'
    return settings, work


def event(second, **fields):
    data = dict(date='2026-10-31', time=f'12:00:{second:02}', tz='+0000', devid='lab-observer',
                type='event', subtype='system', action='login', status='failed', user='test-user', srcip='192.0.2.10')
    data.update(fields)
    return ' '.join(f'{key}="{value}"' for key,value in data.items())


def test_auth_sequence_incident_graph_evidence_and_tampering(tmp_path, monkeypatch):
    settings, work = ingest(tmp_path, [event(i) for i in range(10)] + [event(15,status='success')])
    result = analyze(work)
    assert result['status']=='completed' and result['detections']==2 and result['incidents']==1
    assert result['next_targets']['status']=='unavailable'
    with sqlite3.connect(work/'analysis'/'investigation.sqlite') as db:
        incident = db.execute('SELECT id FROM incidents').fetchone()[0]
        path = incident_path(db, incident)
    assert len(path['timeline'])==2
    assert {node['kind'] for node in path['nodes']} == {'actor','account','observer'}
    assert all(edge['status']=='observed_association' for edge in path['edges'])
    assert all(step['kill_chain_stage'] is None for step in path['timeline'])
    monkeypatch.setenv('KILLCHAIN_DATA_DIR', str(settings.data_dir))
    with TestClient(app) as client:
        base=f'/api/investigations/{work.name}'
        assert len(client.get(base+'/incidents').json()['items'])==1
        assert client.get(base+f'/incidents/{incident}/path').status_code==200
        identifier=path['timeline'][0]['id']
        evidence=client.get(base+f'/detections/{identifier}/evidence/0')
        assert evidence.status_code==200 and evidence.json()['raw_hash_verified']
        assert evidence.json()['reference']['synthetic']
        (settings.ingestion_input_dir/'test.log').write_text('changed')
        assert client.get(base+f'/detections/{identifier}/evidence/0').status_code==409
        assert client.get(base+'/incidents/absent/path').status_code==404
        assert client.get(base+'/incidents?limit=101').status_code==422
        assert client.post(base).status_code==409
    with pytest.raises(ValueError):
        analyze(work)


def test_negative_cases_do_not_turn_source_alerts_into_detections(tmp_path):
    lines=[event(i,srcip=f'192.0.2.{i+1}') for i in range(10)]
    lines += [event(20,type='utm',subtype='ips',action='detected',attack='source annotation')]
    lines += [event(21,time='invalid')]
    _, work=ingest(tmp_path, lines)
    result=analyze(work)
    assert result['status']=='completed' and result['detections']==0
    assert result['source_alerts']==1 and result['time_unknown']==1


def test_port_diversity_is_required(tmp_path):
    _, work=ingest(tmp_path,[event(i,type='traffic',dstip='198.51.100.2',dstport=str(1000+i),action='deny') for i in range(20)])
    result=analyze(work)
    assert result['status']=='completed' and result['detections']==1
    with sqlite3.connect(work/'analysis'/'investigation.sqlite') as db:
        detail=json.loads(db.execute('SELECT detail FROM detections').fetchone()[0])
    assert detail['technique']=='T1046'
    assert detail['mapping_status']=='hypothesis'


def test_rule_schema_rejects_unsafe_or_duplicate_config(tmp_path):
    rules=tmp_path/'rules.yaml'
    rules.write_text('- !!python/object:bad {}')
    with pytest.raises(Exception): load_rules(rules)
    rules.write_text('- {id: a, kind: failed_logins, threshold: 0, window_seconds: 300}')
    with pytest.raises(ValueError): load_rules(rules)
    rules.write_text('- {id: a, kind: failed_logins, threshold: 10, window_seconds: 300, sql: unsafe}')
    with pytest.raises(ValueError): load_rules(rules)


def test_same_actor_different_observers_stays_separate(tmp_path):
    _,work=ingest(tmp_path,[event(i,devid=device) for device in ['observer-a','observer-b'] for i in range(10)])
    result=analyze(work)
    assert result['status']=='completed' and result['incidents']==2


def test_process_rule_uses_telemetry_not_supplied_attack_labels():
    from datetime import datetime, timezone
    row=dict(source_record_id='example',source_profile='simedr-json-1.0.0',
             timestamp={'utc':datetime(2026,10,31,tzinfo=timezone.utc)},
             provenance={'source_id':'lab','synthetic':True}, source_fields_json='{"threat":{"technique":"ignored"}}',
             event={'kind':'alert'},host={'name':'lab-host'},user={'name':'lab-user'},
             source=None,destination=None,process={'name':'powershell.exe','parent_name':'WINWORD.EXE'})
    value=observation(row)
    assert value[11]==1 and value[12]==1
    row['process']['parent_name']='explorer.exe'
    assert observation(row)[11]==0


def test_duplicate_content_and_fixed_bucket_boundary(tmp_path):
    lines=[event(0)]*10
    lines += [event(0,time='12:10:00',status='success')]
    _,work=ingest(tmp_path,lines)
    result=analyze(work)
    assert result['status']=='completed' and result['detections']==1
    with sqlite3.connect(work/'analysis'/'investigation.sqlite') as db:
        count, detail=db.execute('SELECT count,detail FROM detections').fetchone()
    assert count==10 and len(json.loads(detail)['evidence'])==10


def test_analysis_requires_completed_ingestion_and_single_writer(tmp_path):
    from app.job_store import atomic_json
    _,work=ingest(tmp_path,[event(0)])
    with writer_lock(work.parent):
        assert analyze(work)['status']=='failed'
    job=json.loads((work/'job.json').read_text()); job['status']='running'
    atomic_json(work/'job.json',job)
    with pytest.raises(ValueError): analyze(work)


def test_api_launches_real_background_analysis_worker(tmp_path, monkeypatch):
    import time
    settings,work=ingest(tmp_path,[event(i) for i in range(10)])
    monkeypatch.setenv('KILLCHAIN_DATA_DIR',str(settings.data_dir))
    with TestClient(app) as client:
        base=f'/api/investigations/{work.name}'
        assert client.get(base).json()['status']=='not_started'
        assert client.post(base).status_code==202
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            result=client.get(base).json()
            if result['status'] not in {'queued','running'}:
                break
            time.sleep(0.05)
        assert result['status']=='completed',result
        assert result['detections']==1


def test_typed_firex_reports_real_analysis_stages(tmp_path,monkeypatch):
    import app.analysis as analysis_module
    _,work=ingest(tmp_path,[event(i) for i in range(10)],profile='firex-kv-1.0.0')
    stages=[]
    original=analysis_module.atomic_json
    def observe(path,value):
        stages.append(value.get('stage'))
        return original(path,value)
    monkeypatch.setattr(analysis_module,'atomic_json',observe)
    result=analyze(work)
    assert result['status']=='completed' and result['detections']==1
    assert result['supported_observations']==10
    assert {'reading_events','evaluating_rules','correlating_findings','completed'} <= set(stages)


def test_many_connections_to_one_port_are_not_port_probing(tmp_path):
    _,work=ingest(tmp_path,[event(i,type='traffic',dstip='198.51.100.2',dstport='443',action='accept') for i in range(20)])
    result=analyze(work)
    assert result['status']=='completed' and result['detections']==0
    graph=json.loads((work/'analysis'/'observed-graph.json').read_text())
    assert len(graph['nodes'])==2 and len(graph['edges'])==20
    assert all(edge['relationship']=='logged_network_event' for edge in graph['edges'])
