#!/usr/bin/env bash
# Run sql_fallback_priv.py under the IRIS lock with the reader's password as the environment variable IVGAUDIT_PW
# (passed by name from $RUN_DIR/versions/secrets/ivgaudit_ro.pw, never on a command line or in a log).
#   SFP_TAG=r1 bash run_sql_fallback.sh   -> $RUN_DIR/writesets/sql-fallback/{results-r1.json,run-r1.out}
set -uo pipefail
: "${RUN_DIR:?source environment.sh first}"
TAG="${SFP_TAG:-r1}"; export SFP_TAG="$TAG"
d="$RUN_DIR/writesets/sql-fallback"; out="$d/run-$TAG.out"
mkdir -p "$d"
test ! -e "$out" || { echo "$out exists: use a new SFP_TAG"; exit 2; }
IVGAUDIT_PW="$(cat "$RUN_DIR/versions/secrets/ivgaudit_ro.pw")"; export IVGAUDIT_PW
rc=0
( cd "$WORK_DIR" && LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-3600}" bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris \
  timeout 900 python "$WORK_DIR/experiment/playbook-completion/writesets/live/sql_fallback_priv.py" ) > "$out" 2>&1 || rc=$?
unset IVGAUDIT_PW
if grep -rqF -f "$RUN_DIR/versions/secrets/ivgaudit_ro.pw" "$d/" 2>/dev/null; then
  echo "PASSWORD FOUND IN A LOG" >> "$out"
else
  echo "password scan: not found in $d/" >> "$out"
fi
echo "EXIT $rc" >> "$out"
