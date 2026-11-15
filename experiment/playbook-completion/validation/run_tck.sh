#!/usr/bin/env bash
# The vendored openCypher TCK (behave), the pin's own runner scripts/tck/run_all.sh, area groups one iris-lock hold
# each (CONVENTIONS.md "Connection cap"), then the pin's scripts/tck/summarize.py over the whole run.
#
#   bash experiment/playbook-completion/validation/run_tck.sh <run-id> [groups=6]
#
# TCK_LOCK=0: run_all.sh's own /tmp flock is replaced by tools/locks.sh iris held around each group.
set -uo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
rid=$1; groups=${2:-8}
# at most 8 lock holds: the lock is contended by ~14 queued processes, and each area group is a few minutes
[ "$groups" -gt 8 ] && groups=8
CO=${VALIDATION_CHECKOUT:-$RUN_DIR/validation/checkout}
out="$RUN_DIR/validation/$rid"
[ -e "$out/driver.log" ] && { echo "exists: $out" >&2; exit 2; }
mkdir -p "$out"
export PYTHONPATH="$CO" PYTHON="$(command -v python)" TCK_LOCK=0 TCK_TIMEOUT=1500 IVG_TCK_NAMESPACE="${IVG_NAMESPACE:-USER}"
mapfile -t areas < <(cd "$CO" && for d in tests/tck/features/*/*/; do basename "$d"; done)
n=${#areas[@]}; per=$(( (n + groups - 1) / groups ))
{
  echo "# id=$rid start_utc=$(date -u +%FT%TZ) checkout=$CO head=$(git -C "$CO" rev-parse HEAD) areas=$n groups=$groups"
  echo "# env: IVG_TEST_CONTAINER=$IVG_TEST_CONTAINER IVG_PORT=$IVG_PORT IVG_TCK_NAMESPACE=$IVG_TCK_NAMESPACE TCK_TIMEOUT=$TCK_TIMEOUT"
} > "$out/driver.log"
start=$(date +%s)
for ((i = 0; i < n; i += per)); do
  g=("${areas[@]:i:per}")
  echo "# group $((i / per)): ${g[*]} waiting $(date -u +%FT%TZ)" >> "$out/driver.log"
  t0=$(date +%s)
  (cd "$CO" && bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris \
      bash scripts/tck/run_all.sh "$out/areas" "${g[@]}") >> "$out/driver.log" 2>&1
  echo "# group $((i / per)) exit=$? seconds=$(( $(date +%s) - t0 ))" >> "$out/driver.log"
done
(cd "$CO" && python scripts/tck/summarize.py "$out/areas" "$out/results.tsv" --features "$CO/tests/tck/features") \
    > "$out/summary.txt" 2>&1
echo "# summarize exit=$? wall_seconds=$(( $(date +%s) - start )) end_utc=$(date -u +%FT%TZ)" >> "$out/driver.log"
grep -l "Unable to allocate a license" "$out"/areas/*.log 2>/dev/null | sed 's/^/LICENSE FAILURE: /' | tee -a "$out/driver.log"
cat "$out/summary.txt" | tail -15
