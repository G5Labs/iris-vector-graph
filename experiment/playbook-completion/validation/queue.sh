#!/usr/bin/env bash
# The validation lane's run queue, detached (setsid nohup) so it outlives one tool call. Each step waits for the
# previous step's chunks to finish; every IRIS hold goes through run.sh (tools/locks.sh iris, <= ~15 min per chunk).
#
#   setsid nohup bash experiment/playbook-completion/validation/queue.sh <step...> > $RUN_DIR/validation/queue.log 2>&1 &
set -uo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
V="$WORK_DIR/experiment/playbook-completion/validation"
CO=$RUN_DIR/validation/checkout
wait_done() {  # <prefix> <n>: until n chunk exit files exist (timeout 6 h)
  for _ in $(seq 1 4320); do [ "$(ls "$RUN_DIR"/validation/"$1"-c*/exit 2>/dev/null | wc -l)" -ge "$2" ] && return 0; sleep 5; done
  echo "timeout waiting for $1"; return 1
}
echo "queue pid $$ start $(date -u +%FT%TZ): $*"
for step in "$@"; do
  echo "== $step $(date -u +%FT%TZ)"
  case $step in
    wait-unit) wait_done unit-3 8 ;;
    unit-resume) bash "$V/run_chunks.sh" unit-3 8 1800 tests/unit; wait_done unit-3 8 ;;
    wait-integration) wait_done integration-1 6 ;;
    integration-resume) bash "$V/run_chunks.sh" integration-1 6 3600 tests/integration -- --deselect \
        "tests/integration/test_ledger_us03_concurrency.py::TestUS3Concurrency::test_eight_writers_fifty_commits_contiguous_single_parent_history"
      wait_done integration-1 6 ;;
    e2e) bash "$V/run_chunks.sh" e2e-1 22 1500 tests/e2e ;;
    small)
      bash "$V/run.sh" schema-contract-1 900 -- tests/test_schema_contract.py
      bash "$V/run.sh" contract-1 900 -- tests/contract
      IVG_RUN_CONTRACT=1 bash "$V/run.sh" contract-optin-1 900 -- tests/contract
      bash "$V/run.sh" python-1 900 -- tests/python
      bash "$V/run.sh" docs-2 900 -- tests/docs
      bash "$V/run.sh" regression-2 900 -- tests/regression
      bash "$V/run.sh" perf-default-1 900 -- tests/perf
      ;;
    tck) bash "$V/run_tck.sh" tck-1 37 ;;
    mp)
      for r in 1 2 3; do
        bash "$V/run.sh" mp-existing-$r 900 -- tests/integration/test_ledger_us03_concurrency.py \
          tests/integration/test_ledger_us04_idempotency.py tests/integration/test_ledger_us09_verify.py \
          --deselect "tests/integration/test_ledger_us03_concurrency.py::TestUS3Concurrency::test_eight_writers_fifty_commits_contiguous_single_parent_history"
      done
      ;;
    *) echo "unknown step $step" ;;
  esac
done
echo "queue done $(date -u +%FT%TZ)"
