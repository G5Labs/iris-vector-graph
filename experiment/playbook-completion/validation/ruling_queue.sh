#!/usr/bin/env bash
# Operator ruling 2026-11-14 03:16Z: convert feasible 'blocked' rows into runs, each under tools/locks.sh iris.
#   setsid nohup bash experiment/playbook-completion/validation/ruling_queue.sh <step...> > $RUN_DIR/validation/ruling-queue.log 2>&1 &
# Steps: driver540, docs, alt, gated1 (first 25 light primary-only gated e2e files).
set -uo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
V="$WORK_DIR/experiment/playbook-completion/validation"
CO=$RUN_DIR/validation/checkout
S540=$RUN_DIR/availability/driver-5.4.0-venv/lib/python3.11/site-packages
LOCK=(bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris)
echo "ruling queue pid $$ start $(date -u +%FT%TZ): $*"
for step in "$@"; do
  echo "== $step $(date -u +%FT%TZ)"
  case $step in
    driver540)
      VALIDATION_DRIVER_SITE=$S540 bash "$V/run.sh" driver540-1 1500 -- \
        tests/integration/test_algorithms_new_paths.py tests/integration/test_store_write_paths.py \
        tests/integration/test_sql_store_paths.py tests/e2e/test_460_proc_yield_alias_e2e.py \
        tests/e2e/test_460_r270_ppr_networkx_e2e.py tests/e2e/test_create_edge_atomic_e2e.py \
        tests/e2e/test_temporal_structural_row_live.py tests/e2e/test_communities_e2e.py
      VALIDATION_DRIVER_SITE=$S540 IVG_ORACLE_USER=1 bash "$V/run.sh" driver540-oracle-1 1200 -- "@$RUN_DIR/validation/oracle-1/chunk-00"
      o=$RUN_DIR/validation/driver540-tck-unwind-1; mkdir -p "$o"
      (cd "$CO" && PYTHONPATH=$CO PYTHON="$V/py540.sh" TCK_LOCK=0 TCK_TIMEOUT=600 IVG_TCK_NAMESPACE=USER \
        "${LOCK[@]}" bash scripts/tck/run_all.sh "$o/areas" unwind) > "$o/driver.log" 2>&1
      echo "driver540-tck-unwind-1 exit=$?"
      ;;
    docs)
      o=$RUN_DIR/validation/setup-ivg460doc; mkdir -p "$o"
      { echo "# cmd: (cd $CO && locks.sh iris timeout 900 python scripts/dev/make_scratch_namespace.py IVG460DOC) start $(date -u +%FT%TZ)"
        (cd "$CO" && PYTHONPATH=$CO "${LOCK[@]}" timeout 900 python scripts/dev/make_scratch_namespace.py IVG460DOC)
        echo "# exit=$? end $(date -u +%FT%TZ)"; } > "$o/run.log" 2>&1
      tail -3 "$o/run.log"
      VALIDATION_SCRATCH_NS=1 IVG_NAMESPACE=IVG460DOC bash "$V/run.sh" docs-run-1 1500 -- tests/docs/test_docs_run.py
      ;;
    alt)
      VALIDATION_SCRATCH_NS=1 IVG_NS_IVG262ALT=IVG262ALT bash "$V/run.sh" alt-1 1500 -- \
        tests/e2e/test_262_alt_schema_paths.py tests/integration/test_grant_copy.py tests/integration/test_cypher_advanced.py
      ;;
    gated1)
      mapfile -t files < <(head -25 "$RUN_DIR/validation/gated-primary-light.txt")
      bash "$V/run_gated.sh" gated-1 1500 -- "${files[@]}"
      ;;
    *) echo "unknown step $step" ;;
  esac
done
echo "ruling queue done $(date -u +%FT%TZ)"
