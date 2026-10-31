"""Bounded investigation APIs; heavy work runs outside API requests."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Query

from app.config import Settings
from app.job_store import atomic_json, job_dir, now, process_alive, read_json
from app.analysis import incident_path

router = APIRouter(prefix='/api/investigations', tags=['investigations'])


def work_dir(job_id):
    try:
        work = job_dir(Settings(), job_id)
        if not (work / 'job.json').is_file():
            raise FileNotFoundError()
        return work
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, 'Ingestion job not found')


def state_for(work):
    path = work / 'analysis' / 'job.json'
    if not path.exists():
        return {'status':'not_started'}
    state = read_json(path)
    # A finished artifact always wins over process liveness.
    launch = work / 'analysis' / 'launch.json'
    if state['status'] in {'running','queued'} and launch.exists():
        pid = read_json(launch)['pid']
        if not process_alive(pid):
            return {**state, 'status':'interrupted', 'error':{'message':'Analysis worker exited before publishing results.'}}
    return state


@router.post('/{job_id}', status_code=202)
def start(job_id: str):
    work = work_dir(job_id)
    if read_json(work / 'job.json')['status'] != 'completed':
        raise HTTPException(409, 'Complete ingestion before analysis')
    try:
        (work / 'analysis').mkdir()
    except FileExistsError:
        raise HTTPException(409, 'Analysis already exists; inspect its status. Use a new ingestion job for a fresh analysis.')
    state = {'status':'queued', 'created_at':now()}
    atomic_json(work / 'analysis' / 'job.json', state)
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
    try:
        with (work / 'analysis' / 'worker.log').open('ab') as log:
            child = subprocess.Popen([sys.executable, '-m', 'app.analysis', '--job-dir', str(work)], env=env,
                                     stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        atomic_json(work / 'analysis' / 'launch.json', {'pid':child.pid})
    except OSError as error:
        atomic_json(work / 'analysis' / 'job.json', {'status':'failed','error':{'message':str(error)}})
        raise HTTPException(500, 'Could not launch analysis worker')
    return state


@router.get('/{job_id}')
def status(job_id: str):
    return state_for(work_dir(job_id))


@router.get('/{job_id}/observed-graph')
def observed_graph(job_id: str):
    work=work_dir(job_id)
    if state_for(work)['status']!='completed':
        raise HTTPException(409,'Complete analysis before viewing graph')
    artifact=work/'analysis'/'observed-graph.json'
    if not artifact.exists():
        return {'nodes':[],'edges':[],'interpretation':'This older analysis has no graph snapshot; a new scan can generate one.'}
    return read_json(artifact)


@contextmanager
def database(work):
    if state_for(work)['status'] != 'completed':
        raise HTTPException(409, 'Analysis is not complete')
    db = sqlite3.connect((work / 'analysis' / 'investigation.sqlite').as_uri()+'?mode=ro', uri=True)
    try:
        yield db
    finally:
        db.close()


@router.get('/{job_id}/incidents')
def incidents(job_id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=1000000)):
    with database(work_dir(job_id)) as db:
        rows = db.execute('''SELECT i.id,i.actor,i.started,i.ended,count(d.id),sum(d.count)
            FROM incidents i JOIN detections d ON d.incident_id=i.id GROUP BY i.id
            ORDER BY i.started,i.id LIMIT ? OFFSET ?''', (limit, offset)).fetchall()
    return {'items':[dict(id=a,actor=b,started=c,ended=d,detections=e,matched_observations=f) for a,b,c,d,e,f in rows], 'limit':limit,'offset':offset}


@router.get('/{job_id}/incidents/{incident_id}/path')
def path(job_id: str, incident_id: str):
    with database(work_dir(job_id)) as db:
        try:
            return incident_path(db, incident_id)
        except KeyError:
            raise HTTPException(404, 'Incident not found')


@router.get('/{job_id}/detections/{detection_id}/evidence/{index}')
def evidence(job_id: str, detection_id: str, index: int):
    if not 0 <= index < 50:
        raise HTTPException(404, 'Evidence reference not found')
    work = work_dir(job_id)
    with database(work) as db:
        row = db.execute('SELECT detail FROM detections WHERE id=?', (detection_id,)).fetchone()
    refs = json.loads(row[0])['evidence'] if row else []
    if index >= len(refs):
        raise HTTPException(404, 'Evidence reference not found')
    ref = refs[index]
    job = read_json(work / 'job.json')
    try:
        with open(job['source_path'], 'rb') as source:
            source.seek(ref['byte_offset'])
            raw = source.read(ref['byte_length'])
        if hashlib.sha256(raw).hexdigest() != ref['raw_sha256']:
            raise HTTPException(409, 'Original evidence changed')
    except OSError:
        raise HTTPException(409, 'Original evidence unavailable')
    return {'reference':ref,'raw':raw.decode('utf-8',errors='replace'), 'raw_hash_verified':True}
