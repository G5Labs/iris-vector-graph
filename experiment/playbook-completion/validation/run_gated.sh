#!/usr/bin/env bash
# run.sh with the e2e gate ON and the harness in scratch mode (pre-existing namespaces still refused). One validation-lane pytest run: fresh log, JUnit XML and harness meta under $RUN_DIR/validation/<id>/.
#
#   bash experiment/playbook-completion/validation/run.sh <id> <timeout-seconds> -- <pytest args...>
#
# Runs from the clean clone of the pin at $VALIDATION_CHECKOUT (default $RUN_DIR/validation/checkout; made by
# `git clone --shared --no-checkout` of the local repository, `checkout --detach 3eaa79cf`, submodule from the local
# module store). The audit worktree is mounted read-only for this lane, and upstream tests write into the checkout
# (FastHTML's .sesskey, scratch files), so the suites run from a writable clean build of the same tree.
# Every run holds tools/locks.sh iris for its whole duration (CONVENTIONS.md "Connection cap": the Community container
# allows 8 connections across all lanes; every IRIS-connecting command runs under the lock, chunked).
set -uo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
id=$1; to=$2; shift 2
lock=(bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris)
[ "${1:-}" = "--lock" ] && shift
[ "${1:-}" = "--" ] && shift
PIN=3eaa79cf77d3e0a879b2cced634cf2729d81499e
CO=${VALIDATION_CHECKOUT:-$RUN_DIR/validation/checkout}
out="$RUN_DIR/validation/$id"
mkdir -p "$out"
[ -e "$out/run.log" ] && { echo "run.sh: $out/run.log exists; use a new id" >&2; exit 2; }
head=$(git -C "$CO" rev-parse HEAD); tree=$(git -C "$CO" rev-parse 'HEAD^{tree}')
[ "$head" = "$PIN" ] || { echo "run.sh: $CO is at $head, not the pin" >&2; exit 2; }
git -C "$CO" diff --quiet HEAD -- || { echo "run.sh: $CO has tracked changes" >&2; exit 2; }
export IVG_GATE_NAMESPACES=1 VALIDATION_SCRATCH_NS=1 PYTHONPATH="$CO"  # gate on: operator ruling 2026-11-14 (pinned fixtures may make isolated scratch namespaces under the lock)
{
  echo "# id=$id start_utc=$(date -u +%FT%TZ) checkout=$CO head=$head tree=$tree audit_head=$(git -C "$WORK_DIR" rev-parse HEAD) timeout=$to lock=${#lock[@]}"
  echo "# cmd: (cd $CO && ${lock[*]} timeout $to python $WORK_DIR/experiment/playbook-completion/validation/run_suite.py --meta $out/meta.json -- $* --junitxml=$out/junit.xml -ra)"
  echo "# env: IVG_TEST_CONTAINER=$IVG_TEST_CONTAINER IVG_PORT=$IVG_PORT IVG_NAMESPACE=$IVG_NAMESPACE SKIP_IRIS_TESTS=$SKIP_IRIS_TESTS IVG_GATE_NAMESPACES=$IVG_GATE_NAMESPACES PYTHONPATH=$PYTHONPATH PYTEST_ADDOPTS=$PYTEST_ADDOPTS"
  echo "# untracked before: $(git -C "$CO" status --porcelain --untracked-files=all | wc -l)"
} > "$out/run.log"
start=$(date +%s)
echo "# waiting for the iris lock at $(date -u +%FT%TZ)" >> "$out/run.log"
(cd "$CO" && "${lock[@]}" timeout "$to" python "$WORK_DIR/experiment/playbook-completion/validation/run_suite.py" \
    --meta "$out/meta.json" -- "$@" --junitxml="$out/junit.xml" -ra) >> "$out/run.log" 2>&1
rc=$?
end=$(date +%s)
{
  echo "# tracked changes after: $(git -C "$CO" diff --name-only HEAD -- | wc -l) untracked after: $(git -C "$CO" status --porcelain --untracked-files=all | wc -l)"
  echo "# exit=$rc wall_seconds=$((end - start)) end_utc=$(date -u +%FT%TZ)"
} >> "$out/run.log"
echo "$rc" > "$out/exit"
if grep -q "Unable to allocate a license" "$out/run.log"; then echo "# LICENSE-ALLOCATION FAILURE SEEN: infrastructure, rerun" >> "$out/run.log"; echo "LICENSE FAILURE in $id"; fi
echo "$id exit=$rc wall=$((end - start))s log=$out/run.log"
grep -E "^(=+ .* in [0-9.]+s|\[run_suite\])" "$out/run.log" | tail -2
exit $rc
