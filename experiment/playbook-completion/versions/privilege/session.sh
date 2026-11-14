#!/usr/bin/env bash
# Pipe one ObjectScript script into `iris session` on the audit container, under the IRIS lock.
#   bash session.sh <namespace> <script.os> <log>
# The reader's password, when a script needs it, travels only as the environment variable IVGAUDIT_PW, read from
# $RUN_DIR/versions/secrets/ivgaudit_ro.pw by this script and passed by name (`docker exec -e IVGAUDIT_PW`), so it is in
# no command line, script or log.
set -euo pipefail
: "${RUN_DIR:?source environment.sh first}"
ns="$1"; script="$2"; log="$3"
C=ivg-playbook-20261113-audit-iris
envarg=()
if grep -q IVGAUDIT_PW "$script"; then
  IVGAUDIT_PW="$(cat "$RUN_DIR/versions/secrets/ivgaudit_ro.pw")"; export IVGAUDIT_PW; envarg=(-e IVGAUDIT_PW)
fi
{ echo "== $(date -u +%FT%TZ) iris session -U $ns < $(basename "$script") (sha256 $(sha256sum "$script" | cut -c1-16))"
  if [ "${IVG_LOCK_HELD:-0}" = 1 ]; then  # the caller already holds tools/locks.sh iris (run-all.sh)
    timeout 300 docker exec -i "${envarg[@]}" "$C" iris session IRIS -U "$ns" < "$script"
  else
    bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris \
      timeout 300 docker exec -i "${envarg[@]}" "$C" iris session IRIS -U "$ns" < "$script"
  fi
  echo "== exit $? $(date -u +%FT%TZ)"; } >> "$log" 2>&1
