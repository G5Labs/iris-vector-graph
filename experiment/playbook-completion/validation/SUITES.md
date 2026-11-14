# Validation lane: upstream suites and performance baselines at the pin (in progress)

Status: runs in progress. This file is rewritten with the results when the queues finish.

## Announced long iris-lock holds (performance, after the functional suites)

Per the coordinator's fairness request, functional suites hold `tools/locks.sh iris` per chunk (target <= ~15 min).
The performance runs below start only after the functional queue (`queue-1.log`: unit, integration, e2e, small sets,
TCK, multi-process) has finished, and may hold the lock longer (each is one timing-sensitive measurement that must run
alone):

| Run id | What | Expected hold |
|---|---|---|
| `perf-sc256-upstream-1`, `-2` | `tests/integration/test_256_ledger_redaction_perf.py -m perf` (spec 256 SC-002, SC-003) | up to 40 min each |
| `perf-committer-n1-1`, `-2` | `validation/perf/test_256_sc003_commit_blocking.py`, 1 committer process, 3 cycles of 100,000 records | up to 60 min each |
| `perf-committer-n3-1` | same, 3 committer processes (multi-process variant), 2 cycles | up to 60 min |
| `perf-ledger-1`, `perf-nodepk-1`, `perf-algos-1`, `perf-performance-1` | upstream `-m perf` / `performance` sets | up to 40 min each |
| `bench-1`, `bench-2` | `tests/benchmarks/bench.py --datasets S M` (spec 093, ObjectScript path) | up to 30 min each |

Driver: `validation/perf_queue.sh` (log `$RUN_DIR/validation/perf-queue.log`).
