"""Measure real-source ingestion without changing the production worker.

Outputs stay in ignored data/. cProfile cumulative timings overlap: do not sum
them. Baseline runs exclude profiler overhead. No raw evidence is exported.
"""
import argparse
import cProfile
import json
import platform
import pstats
import time
from pathlib import Path

from app.config import Settings
from app.ingestion import run_job
from app.jobs import create_job


def measure(source, destination, rows, repeats, profile):
    destination.mkdir(parents=True, exist_ok=False)
    sample = destination / 'sample.log'
    copied = 0
    with source.open('rb') as reader, sample.open('xb') as writer:
        for _ in range(rows):
            line = reader.readline(1024 * 1024 + 1)
            if not line:
                break
            if len(line) > 1024 * 1024:
                raise ValueError('sample record exceeds 1 MiB')
            writer.write(line)
            copied += 1
    results = []
    for attempt in range(repeats + 1):
        settings = Settings(_env_file=None, data_dir=destination / f'run-{attempt}', ingestion_input_dir=destination)
        work = create_job(settings, sample.name, source_profile=profile, synthetic=False)
        profiler = cProfile.Profile() if attempt == repeats else None
        start = time.perf_counter()
        if profiler:
            profiler.enable()
        job = run_job(work)
        if profiler:
            profiler.disable()
        elapsed = time.perf_counter() - start
        if job['status'] != 'completed':
            raise RuntimeError(str(job.get('error')))
        result = dict(profiled=bool(profiler), seconds=elapsed, records=job['records_processed'],
                      records_per_second=job['records_processed'] / elapsed,
                      source_mib_per_second=sample.stat().st_size / 1024**2 / elapsed,
                      peak_process_rss_bytes=job['peak_worker_rss_bytes'],
                      accepted=job['records_accepted'], partial=job['records_partial'], rejected=job['records_rejected'],
                      parquet_parts=job['checkpoint']['parquet_parts'],
                      output_bytes=sum(p.stat().st_size for p in work.rglob('*') if p.is_file()))
        if profiler:
            profiler.dump_stats(str(destination / 'ingestion.prof'))
            stats = pstats.Stats(profiler)
            entries = []
            for (file, line, function), (primitive, calls, own, cumulative, _) in stats.stats.items():
                entries.append(dict(module=Path(file).name, function=function, calls=calls,
                                    self_seconds=own, cumulative_seconds=cumulative))
            result['top_cumulative'] = sorted(entries, key=lambda x: x['cumulative_seconds'], reverse=True)[:40]
            result['top_self'] = sorted(entries, key=lambda x: x['self_seconds'], reverse=True)[:30]
        results.append(result)
        print(json.dumps({k: v for k, v in result.items() if not isinstance(v, list)}), flush=True)
    report = dict(python=platform.python_version(), platform=platform.platform(),
                  source_bytes=sample.stat().st_size, source_records=copied,
                  settings=settings.model_dump(mode='json', exclude={'data_dir', 'ingestion_input_dir'}),
                  limitations='Contiguous source prefix; warm OS cache; same process across runs; RSS peak is process-lifetime, not isolated per run; profiler adds overhead; cumulative times overlap. Not full-tier qualification.',
                  runs=results)
    (destination / 'measurements.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--rows', type=int, default=50000)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--profile', default='key-value-1.0.0')
    args = parser.parse_args()
    if args.rows < 1 or args.repeats < 1:
        parser.error('rows and repeats must be positive')
    measure(args.source, args.destination, args.rows, args.repeats, args.profile)
