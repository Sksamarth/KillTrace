# Ingestion baseline: 31 October 2026

Measured the existing canonical key-value ingestion worker, without production
code changes or an intermediate JSONL conversion. The source was the first
50,000 physical records of the supplied local FireX file: 26,410,619 bytes
(25.19 MiB). This contiguous prefix is not a random or full-corpus sample.

## End-to-end results

| Run | Worker wall time | Records/second | Source MiB/second |
| --- | ---: | ---: | ---: |
| Baseline 1 | 64.34 s | 777 | 0.391 |
| Baseline 2 | 55.63 s | 899 | 0.453 |
| cProfile run | 50.37 s | 993 | 0.500 |

All three runs accepted 50,000 records with zero partial/rejected records and
35 Parquet parts. Process-lifetime peak RSS was 118,140,928 bytes (112.7 MiB).
Outputs occupied approximately 19.7–21.3 MB per job, including the catalog.

Default settings: 4,096-row/8 MiB estimated batch caps, 1,024-row Parquet groups,
Zstandard compression, two DuckDB threads, 768 MiB worker admission; effective
DuckDB buffers 402 MB and spill limit 57 MB. Byte caps caused flushes before the
row cap. Runs used the same interpreter/process and Windows filesystem on this
development laptop (Python 3.14.3, Windows 11 build 26200). OS caches were warm;
peak RSS is not isolated per run.
Baseline 1 overlapped the test suite. The profiled run being faster demonstrates
cache/system-load variability, not a benefit from profiling. Profiler overhead
is not measured separately. Do not extrapolate full-tier qualification or a
precise full-file completion time from these results.

## Where the profiled run spends time

These are **cumulative function times**; nested rows overlap and must not be
summed. Percentages use the 50.37-second profiled wall time.

| Operation | Calls | Cumulative time | Wall-time share |
| --- | ---: | ---: | ---: |
| Source parsing and normalized-event validation | 50,000 | 27.80 s | 55.2% |
| Key-value parser (inside validation) | 50,000 | 13.57 s | 26.9% |
| Pydantic core validation (across callers) | 250,002 | 10.38 s | 20.6% |
| Batch flush, catalog and durable checkpoints | 35 | 10.22 s | 20.3% |
| Event-to-Arrow-row serialization | 50,000 | 4.40 s | 8.7% |
| fsync (inside several operations) | 144 | 4.26 s | 8.5% |
| Cancellation-file checks | 50,053 | 4.15 s | 8.2% |
| DuckDB execute (includes commits) | 110 | 2.12 s | 4.2% |
| Parquet write wrapper (inside flush) | 35 | 1.88 s | 3.7% |
| Physical-line reading and record hashing | 50,001 | 0.43 s | 0.9% |
| Whole-source verification (two passes) | 2 | 0.09 s | 0.2% |

Repeated work is visible: 300,000 JSON dumps, 150,000 identity calculations and
100,000 canonical identity-validator calls for 50,000 events. These are useful
optimization candidates, not authorization to remove integrity checks blindly.
Function timings include their callees and do not isolate physical disk latency
from compression or operating-system cache effects. This baseline does not show
graph storage or database replacement to be necessary.

## Recommended next experiments

1. Cache the cancellation path and poll at a bounded time/record interval rather
   than touching the filesystem for every event. Preserve documented stop latency.
2. Reduce repeated identity hashing, JSON serialization and nested model
   revalidation while retaining equivalent schema and evidence checks.
3. Optimize quoted-field parsing, preserving escape and duplicate-key behavior;
   compare against the current parser on valid and malformed fixtures.
4. Measure larger bounded batches/checkpoint intervals. Keep the fsync ordering
   and crash recovery guarantees; do not simply disable durability.
5. Consider bounded parser parallelism only after remeasuring the simpler changes.

For each change, use the same input, verify counts and evidence equivalence,
repeat unprofiled runs, and compare elapsed time, memory and recovery behavior.
Expand to samples from other file regions before the full-file qualification.

## Reproduce

Run from the repository root; select a fresh ignored destination each time:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python scripts/measure_ingestion.py data/firex-10G.log data/measurement-next --rows 50000 --repeats 2
```

The script preserves the original source, copies only a bounded prefix, runs two
unprofiled jobs followed by one cProfile job, and writes measurements.json and
ingestion.prof into that destination. Import/startup time, sample extraction and
job creation are excluded from the worker timer; final worker cleanup is included.
The harness uses its own output store, but avoid simultaneous production ingestion
for meaningful comparisons. Raw samples, catalogs and profiler files remain local
under ignored data/. No source records or private log values are checked in.

Validation: all 95 existing backend tests pass. The three real-source runs serve
as an end-to-end smoke check of the measurement harness. Frontend and production
ingestion behavior were not modified.
