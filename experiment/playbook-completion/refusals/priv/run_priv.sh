#!/usr/bin/env bash
# Run live_priv.py under the IRIS lock with the reader's password as the environment variable IVGAUDIT_PW (passed by
# name from $RUN_DIR/versions/secrets/ivgaudit_ro.pw, never on a command line or in a log).
#   RX_PRIV_TAG=r1 bash run_priv.sh      -> $RUN_DIR/refusals/priv/{results,final-state}-r1.json, run-r1.out
set -uo pipefail
: "${RUN_DIR:?source environment.sh first}"
TAG="${RX_PRIV_TAG:-r1}"; export RX_PRIV_TAG="$TAG"
out="$RUN_DIR/refusals/priv/run-$TAG.out"
mkdir -p "$RUN_DIR/refusals/priv"
test ! -e "$out" || { echo "$out exists: use a new RX_PRIV_TAG"; exit 2; }
IVGAUDIT_PW="$(cat "$RUN_DIR/versions/secrets/ivgaudit_ro.pw")"; export IVGAUDIT_PW
rc=0
LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-10000}" bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris \
  timeout 1800 python "$WORK_DIR/experiment/playbook-completion/refusals/priv/live_priv.py" > "$out" 2>&1 || rc=$?
unset IVGAUDIT_PW
if grep -rqF -f "$RUN_DIR/versions/secrets/ivgaudit_ro.pw" "$RUN_DIR/refusals/priv/" 2>/dev/null; then
  echo "PASSWORD FOUND IN A LOG" >> "$out"
else
  echo "password scan: not found in $RUN_DIR/refusals/priv/" >> "$out"
fi
echo "EXIT $rc" >> "$out"
