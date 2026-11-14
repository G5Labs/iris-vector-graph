#!/usr/bin/env bash
# Performance runs (announced long iris-lock holds, validation/SUITES.md), after the functional queue finishes.
#
#   setsid nohup bash experiment/playbook-completion/validation/perf_queue.sh > $RUN_DIR/validation/perf-queue.log 2>&1 &
#
# Order alternates the redaction measurements with the other baselines, so repeated runs of the same measurement are
# separated in time (A/B style: rep 1, other work, rep 2).
set -uo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
V="$WORK_DIR/experiment/playbook-completion/validation"
CO=$RUN_DIR/validation/checkout
PERF=$V/perf/test_256_sc003_commit_blocking.py
for _ in $(seq 1 8640); do grep -q "^queue done" "$RUN_DIR/validation/queue-1.log" 2>/dev/null && break; sleep 10; done
echo "perf queue start $(date -u +%FT%TZ)"
up256() {  # upstream spec 256 SC-002 / SC-003 (tests/integration/test_256_ledger_redaction_perf.py, -m perf)
  bash "$V/run.sh" "perf-sc256-upstream-$1" 2400 -- tests/integration/test_256_ledger_redaction_perf.py -m perf -s
}
committer() {  # <id> <committers> <cycles>: independent committer-side SC-003 measurement (validation/perf)
  IVG_AUDIT_RECORDS=100000 IVG_AUDIT_COMMITTERS=$2 IVG_AUDIT_CYCLES=$3 IVG_AUDIT_WINDOW_S=8 \
  IVG_AUDIT_OUT="$RUN_DIR/validation/$1.jsonl" \
    bash "$V/run.sh" "$1" 3600 -- -p tests.conftest --rootdir="$CO" -c "$CO/pyproject.toml" "$PERF" -s
}
bench() {  # Spec 093 traversal benchmark (tests/benchmarks/bench.py), datasets S and M, OS path (no Arno on Community)
  local out="$RUN_DIR/validation/bench-$1"; mkdir -p "$out"
  { echo "# id=bench-$1 start_utc=$(date -u +%FT%TZ) head=$(git -C "$CO" rev-parse HEAD)"
    echo "# cmd: (cd $CO && locks.sh iris timeout 1800 env IRIS_HOST=127.0.0.1 IRIS_PORT=$IVG_PORT IRIS_NAMESPACE=$IVG_NAMESPACE python tests/benchmarks/bench.py --datasets S M --runs 10 --warmup 3 --seed 42 --outdir $out)"
  } > "$out/run.log"
  local t0; t0=$(date +%s)
  (cd "$CO" && PYTHONPATH="$CO" bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris timeout 1800 \
     env IRIS_HOST=127.0.0.1 IRIS_PORT="$IVG_PORT" IRIS_NAMESPACE="$IVG_NAMESPACE" \
     python tests/benchmarks/bench.py --datasets S M --runs 10 --warmup 3 --seed 42 --outdir "$out") >> "$out/run.log" 2>&1
  local rc=$?; echo "$rc" > "$out/exit"
  echo "# exit=$rc wall_seconds=$(( $(date +%s) - t0 )) end_utc=$(date -u +%FT%TZ)" >> "$out/run.log"
  echo "bench-$1 exit=$rc"
}
baselines() {  # the perf/performance-marked upstream sets, one module group per hold
  local r=$1
  bash "$V/run.sh" "perf-ledger-$r" 2400 -- tests/integration/test_ledger_perf.py -m perf -s \
    --deselect "tests/integration/test_ledger_perf.py::TestSoak::test_sc002_soak_ten_repetitions"
  bash "$V/run.sh" "perf-nodepk-$r" 2400 -- tests/integration/test_nodepk_performance.py \
    tests/integration/test_nodepk_graph_analytics.py tests/integration/test_nodepk_advanced_benchmarks.py \
    tests/integration/test_nodepk_production_scale.py -m "perf or performance" -s \
    --deselect "tests/integration/test_nodepk_advanced_benchmarks.py::TestAdvancedQueryPatterns::test_concurrent_query_throughput"
  bash "$V/run.sh" "perf-algos-$r" 2400 -- tests/e2e/test_communities_perf.py tests/unit/test_cypher_benchmark.py \
    tests/perf -m "perf or performance" -s
  IRIS_HOST=127.0.0.1 IRIS_PORT="$IVG_PORT" bash "$V/run.sh" "perf-performance-$r" 2400 -- tests/performance -s
}
up256 1
committer perf-committer-n1-1 1 3
baselines 1
bench 1
committer perf-committer-n3-1 3 2
up256 2
committer perf-committer-n1-2 1 3
bench 2
echo "perf queue done $(date -u +%FT%TZ)"
