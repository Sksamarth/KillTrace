"""Disk-backed, evidence-linked investigation over completed canonical jobs."""
import argparse
import hashlib
import ipaddress
import json
import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path

import networkx as nx
import pyarrow.parquet as pq
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

from app.job_store import atomic_json, now, read_json

RULE_FILE = Path(__file__).resolve().parents[1] / 'rules' / 'investigation.yaml'


class Rule(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(pattern=r'^[a-z0-9-]{1,64}$')
    kind: Literal['failed_logins', 'login_after_failures', 'port_probe', 'office_script']
    threshold: int = Field(ge=1, le=10000)
    window_seconds: int = Field(ge=1, le=3600)

    @model_validator(mode='after')
    def office_threshold(self):
        if self.kind == 'office_script' and self.threshold != 1:
            raise ValueError('office_script is a per-event rule; threshold must be 1')
        return self


MAPPINGS = {
    'failed_logins': ('T1110.001', 'Password Guessing', 'Credential Access', None),
    'login_after_failures': ('T1110.001', 'Password Guessing', 'Credential Access', None),
    'port_probe': ('T1046', 'Network Service Discovery', 'Discovery', None),
    'office_script': ('T1059.001', 'PowerShell', 'Execution', None),
}


def load_rules(path=RULE_FILE):
    raw = path.read_bytes()
    if len(raw) > 65536:
        raise ValueError('rule file too large')
    values = yaml.safe_load(raw)
    if not isinstance(values, list) or not 1 <= len(values) <= 32:
        raise ValueError('expected 1 to 32 rules')
    rules = [Rule.model_validate(value) for value in values]
    if len({rule.id for rule in rules}) != len(rules):
        raise ValueError('duplicate rule id')
    return rules, hashlib.sha256(raw).hexdigest()


def ip(value):
    try:
        return str(ipaddress.ip_address(value)) if isinstance(value, str) else None
    except ValueError:
        return None


def observation(row):
    """Explicit field interpretation; device is observer, never destination host."""
    fields = json.loads(row['source_fields_json'])
    profile = row['source_profile']
    stamp = row['timestamp']['utc']
    if profile in {'key-value-1.0.0','firex-kv-1.0.0'}:
        f = fields.get('fields', {})
        device = f.get('devid') or f.get('devname')
        actor, target, user = ip(f.get('srcip')), ip(f.get('dstip')), f.get('user')
        action, outcome = f.get('action'), f.get('status')
        kind = 'auth' if f.get('type') == 'event' and action == 'login' else 'network' if f.get('type') == 'traffic' else 'other'
        failed = kind == 'auth' and outcome == 'failed'
        success = kind == 'auth' and outcome == 'success'
        port = f.get('dstport', '')
        port = int(port) if port.isascii() and port.isdecimal() and len(port) <= 5 else None
        port = port if port is not None and 0 <= port <= 65535 else None
        vendor_alert = f.get('type') == 'utm' and f.get('subtype') in {'ips', 'virus'}
        office = False
    elif profile == 'simedr-json-1.0.0':
        event, host, account = row['event'] or {}, row['host'] or {}, row['user'] or {}
        device = host.get('name')
        actor, target, user = (row['source'] or {}).get('ip'), (row['destination'] or {}).get('ip'), account.get('name')
        kind = 'auth' if 'authentication' in (event.get('category') or []) else 'network' if 'network' in (event.get('category') or []) else 'other'
        failed, success = kind == 'auth' and event.get('outcome') == 'failure', kind == 'auth' and event.get('outcome') == 'success'
        port = (row['destination'] or {}).get('port')
        process = row['process'] or {}
        office = (process.get('name') or '').lower() == 'powershell.exe' and (process.get('parent_name') or '').lower() in {'winword.exe', 'excel.exe', 'outlook.exe'}
        vendor_alert = event.get('kind') == 'alert'
        # Local process telemetry is anchored to the reporting host, not an invented IP.
        if office:
            actor = 'host:' + device if device else None
    else:
        return None
    ref = row['provenance']
    scope = json.dumps([ref['source_id'], device], separators=(',', ':'))
    return (row['source_record_id'], stamp.timestamp() if stamp else None, scope, device,
            actor, target, user, port, kind, int(failed), int(success), int(office), int(vendor_alert),
            json.dumps(ref), ref['synthetic'])


@contextmanager
def writer_lock(root):
    with (root / '.analysis.lock').open('a+b') as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def analyze(work, rule_file=RULE_FILE):
    work = Path(work).resolve()
    state_file = work / 'analysis' / 'job.json'
    if state_file.exists() and read_json(state_file)['status'] == 'completed':
        raise ValueError('completed analysis is immutable')
    try:
        with writer_lock(work.parent):
            return _analyze(work, rule_file)
    except OSError as error:
        state = {'status':'failed','error':{'code':type(error).__name__,'message':'Analysis writer unavailable; only one analysis worker is allowed.'}}
        (work / 'analysis').mkdir(exist_ok=True)
        atomic_json(state_file, state)
        return state


def _analyze(work, rule_file):
    work = Path(work).resolve()
    source_job = read_json(work / 'job.json')
    from app.resources import check_resources
    from app.config import Settings
    settings = Settings.model_validate(source_job['settings'])
    if source_job['status'] != 'completed':
        raise ValueError('analysis requires completed immutable ingestion')
    output = work / 'analysis'
    output.mkdir(exist_ok=True)
    state = {'status': 'running', 'stage':'reading_events', 'version': '1.0.0', 'started_at': now(), 'records_scanned': 0,
             'synthetic':source_job['synthetic'], 'source_profile':source_job['source_profile']}
    atomic_json(output / 'job.json', state)
    atomic_json(output / 'launch.json', {'pid':os.getpid()})
    db = None
    preview = nx.MultiDiGraph()
    try:
        rules, digest = load_rules(rule_file)
        state['rules_sha256'] = digest
        state['rules'] = [rule.model_dump() for rule in rules]
        db = sqlite3.connect(output / 'investigation.sqlite')
        db.executescript('''
            PRAGMA cache_size=-32768; PRAGMA temp_store=FILE;
            CREATE TABLE observations(id TEXT PRIMARY KEY, ts REAL, scope TEXT, device TEXT,
              actor TEXT, target TEXT, user TEXT, port INTEGER, kind TEXT, failed INTEGER,
              success INTEGER, office INTEGER, vendor_alert INTEGER, evidence TEXT, synthetic INTEGER);
            CREATE TABLE incidents(id TEXT PRIMARY KEY, scope TEXT, actor TEXT, started REAL, ended REAL);
            CREATE INDEX incident_lookup ON incidents(scope,actor,ended);
            CREATE TABLE detections(id TEXT PRIMARY KEY, incident_id TEXT, rule_id TEXT,
              started REAL, ended REAL, actor TEXT, target TEXT, user TEXT, device TEXT,
              count INTEGER, detail TEXT);
            CREATE INDEX incident_detections ON detections(incident_id,started);
        ''')
        for part in sorted((work / 'events').rglob('*.parquet')):
            for batch in pq.ParquetFile(part).iter_batches(batch_size=64):
                check_resources(settings, output)
                rows = batch.to_pylist()
                values = [value for row in rows if (value := observation(row)) is not None]
                for value in values:
                    record,stamp,_,_,actor,target,_,_,kind,*_=value
                    if kind=='network' and actor and target and preview.number_of_edges()<50:
                        a,b='actor:'+actor,'target:'+target
                        preview.add_node(a,label=actor,kind='actor')
                        preview.add_node(b,label=target,kind='target')
                        preview.add_edge(a,b,id=record,record_id=record,relationship='logged_network_event',
                                         status='observed_log_association',timestamp=stamp)
                db.executemany('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', values)
                db.commit()
                state['records_scanned'] += len(rows)
            atomic_json(output / 'job.json', state)
        db.executescript('''
            CREATE INDEX auth_groups ON observations(scope,actor,user,ts);
            CREATE INDEX network_groups ON observations(scope,actor,target,ts);
            CREATE TABLE candidates(rule_id TEXT, kind TEXT, scope TEXT, actor TEXT, target TEXT,
              user TEXT, device TEXT, started REAL, ended REAL, count INTEGER, bucket INTEGER, window INTEGER);
        ''')
        state['stage']='evaluating_rules'
        atomic_json(output / 'job.json',state)
        for rule in rules:
            if rule.kind == 'failed_logins':
                query = '''SELECT scope,actor,NULL,user,device,min(ts),max(ts),count(*),cast(ts / ? AS INTEGER)
                  FROM observations WHERE failed=1 AND ts IS NOT NULL AND actor IS NOT NULL
                  AND user IS NOT NULL AND device IS NOT NULL
                  GROUP BY scope,actor,user,cast(ts / ? AS INTEGER) HAVING count(*)>=?'''
            elif rule.kind == 'login_after_failures':
                query = '''SELECT s.scope,s.actor,NULL,s.user,s.device,min(f.ts),s.ts,count(*)+1,cast(s.ts / ? AS INTEGER)
                  FROM observations s JOIN observations f
                  ON f.scope=s.scope AND f.actor=s.actor AND f.user=s.user
                  AND f.failed=1 AND f.ts>=s.ts-? AND f.ts<=s.ts
                  WHERE s.success=1 AND s.ts IS NOT NULL AND s.device IS NOT NULL
                  GROUP BY s.id HAVING count(*)>=?'''
            elif rule.kind == 'port_probe':
                query = '''SELECT scope,actor,target,NULL,device,min(ts),max(ts),count(*),cast(ts / ? AS INTEGER)
                  FROM observations WHERE kind='network' AND ts IS NOT NULL AND actor IS NOT NULL
                  AND target IS NOT NULL AND port IS NOT NULL AND device IS NOT NULL
                  GROUP BY scope,actor,target,cast(ts / ? AS INTEGER) HAVING count(DISTINCT port)>=?'''
            else:
                query = '''SELECT scope,actor,NULL,user,device,ts,ts,1,cast(ts / ? AS INTEGER)
                  FROM observations WHERE office=1 AND ts IS NOT NULL AND actor IS NOT NULL AND ? > 0 AND ? > 0'''
            # Fetch from SQLite incrementally; all sorting/grouping can spill to disk.
            for group in db.execute(query, (rule.window_seconds, rule.window_seconds, rule.threshold)):
                scope, actor, target, user, device, first, last, count, bucket = group
                db.execute('INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                           (rule.id, rule.kind, scope, actor, target, user, device, first, last, count, bucket, rule.window_seconds))
        db.commit()
        state['stage']='correlating_findings'
        atomic_json(output / 'job.json',state)
        for ordinal, candidate in enumerate(db.execute('SELECT * FROM candidates ORDER BY started,rule_id,actor,rowid')):
            rule_id, kind, scope, actor, target, user, device, first, last, count, bucket, window = candidate
            # Conservative correlation: exact observer/source + actor, 10 min gap,
            # max one hour from incident start. No universal shared-IP merging.
            existing = db.execute('SELECT id FROM incidents WHERE scope=? AND actor=? AND ended>=? AND started>=? ORDER BY ended DESC LIMIT 1', (scope, actor, first-600, last-3600)).fetchone()
            incident = existing[0] if existing else hashlib.sha256(json.dumps([scope, actor, first]).encode()).hexdigest()[:24]
            if not existing:
                db.execute('INSERT INTO incidents VALUES (?,?,?,?,?)', (incident, scope, actor, first, last))
            else:
                db.execute('UPDATE incidents SET ended=max(ended,?) WHERE id=?', (last, incident))
            if kind == 'login_after_failures':
                where, args = '(failed=1 OR success=1) AND scope=? AND actor=? AND user=?', [scope, actor, user]
            elif kind == 'failed_logins':
                where, args = 'failed=1 AND scope=? AND actor=? AND user=?', [scope, actor, user]
            elif kind == 'port_probe':
                where, args = "kind='network' AND scope=? AND actor=? AND target=? AND port IS NOT NULL", [scope, actor, target]
            else:
                where, args = 'office=1 AND scope=? AND actor=? AND ts=?', [scope, actor, first]
            args += [first if kind == 'login_after_failures' else bucket*window,
                     last + 0.000001 if kind == 'login_after_failures' else (bucket+1)*window]
            references = [json.loads(row[0]) for row in db.execute(f'SELECT evidence FROM observations WHERE {where} AND ts>=? AND ts<? ORDER BY ts,id LIMIT 50', args)]
            technique, name, tactic, stage = MAPPINGS[kind]
            detail = dict(kind=kind, technique=technique, technique_name=name, tactic=tactic,
                          kill_chain_stage=stage, mapping_status='hypothesis',
                          conclusion='Suspicious behavior requiring investigation; compromise is not established.',
                          evidence=references, evidence_sample_limit=50, window_seconds=window,
                          correlation_reason='Same source/observer and actor within 10 minutes, maximum one-hour incident span.')
            detection = hashlib.sha256(json.dumps([rule_id,scope,actor,target,user,first,last,ordinal]).encode()).hexdigest()[:24]
            db.execute('INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?,?,?)', (detection, incident, rule_id, first, last, actor, target, user, device, count, json.dumps(detail)))
        db.commit()
        atomic_json(output / 'observed-graph.json', {
            'nodes':[dict(id=node,**data) for node,data in preview.nodes(data=True)],
            'edges':[dict(source=a,target=b,**data) for a,b,data in preview.edges(data=True)],
            'sample_limit':50,'interpretation':'First 50 mapped network records only. Logged endpoints do not establish successful communication or compromise.'})
        state.update(status='completed', stage='completed', completed_at=now(), detections=db.execute('SELECT count(*) FROM detections').fetchone()[0],
                     incidents=db.execute('SELECT count(*) FROM incidents').fetchone()[0],
                     source_alerts=db.execute('SELECT count(*) FROM observations WHERE vendor_alert=1').fetchone()[0],
                     time_unknown=db.execute('SELECT count(*) FROM observations WHERE ts IS NULL').fetchone()[0],
                     supported_observations=db.execute('SELECT count(*) FROM observations').fetchone()[0],
                     next_targets={'status': 'unavailable', 'reason': 'No asset permission or connectivity topology supplied.'})
    except Exception as error:
        state.update(status='failed', error={'code': type(error).__name__, 'message': str(error)[:512]})
    finally:
        if db:
            db.close()
        atomic_json(output / 'job.json', state)
    return state


def incident_path(db, incident):
    if not db.execute('SELECT 1 FROM incidents WHERE id=?', (incident,)).fetchone():
        raise KeyError(incident)
    rows = db.execute('SELECT id,rule_id,started,ended,actor,target,user,device,count,detail FROM detections WHERE incident_id=? ORDER BY started,ended,id LIMIT 101', (incident,)).fetchall()
    graph = nx.MultiDiGraph()
    timeline = []
    for identifier, rule, start, end, actor, target, user, device, count, encoded in rows[:100]:
        detail = json.loads(encoded)
        timeline.append(dict(id=identifier, rule_id=rule, started=start, ended=end, actor=actor, target=target, user=user, device=device, count=count, **detail))
        # Entity types and observer relationships are explicit, never lateral-movement claims.
        source = 'actor:' + actor
        graph.add_node(source, label=actor, kind='actor')
        for role, value in [('target', target), ('account', user), ('observer', device)]:
            if value:
                node = role + ':' + value
                graph.add_node(node, label=value, kind=role)
                graph.add_edge(source, node, id=identifier+':'+role, detection_id=identifier,
                               relationship='reported_by' if role == 'observer' else 'involved_in',
                               status='observed_association')
    return dict(incident_id=incident, timeline=timeline, truncated=len(rows)>100,
                nodes=[dict(id=node, **data) for node, data in graph.nodes(data=True)],
                edges=[dict(source=a, target=b, **data) for a,b,data in graph.edges(data=True)],
                interpretation='Evidence associations and temporal ordering, not a confirmed causal attack path.',
                next_targets={'status':'unavailable','reason':'Asset permissions/connectivity required.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-dir', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.job_dir)
    print(json.dumps(result))
    raise SystemExit(0 if result['status']=='completed' else 1)
