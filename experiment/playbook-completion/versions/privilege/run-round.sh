#!/usr/bin/env bash
# One round of the live probe (grantor-aware revoke), one hold of tools/locks.sh iris: bash run-round.sh <round> [probe args]
# enable the user, probe with --revoke-as irisowner,_SYSTEM (grant.os granted as the terminal user irisowner; r1's
# restore granted SELECT again as _SYSTEM), list the privileges, disable the user, check the login, final listing.
set -euo pipefail
: "${RUN_DIR:?source environment.sh first}"
if [ "${IVG_LOCK_HELD:-0}" != 1 ]; then
  exec bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris env IVG_LOCK_HELD=1 bash "$0" "$@"
fi
P="$WORK_DIR/experiment/playbook-completion/versions/privilege"; round="$1"; shift; L="$RUN_DIR/versions/privilege/$round"; mkdir -p "$L"
log="$L/run-$round.log"
echo "== run-$round start $(date -u +%FT%TZ) (lock held)" >> "$log"
bash "$P/session.sh" %SYS "$P/privileges.os" "$L/privileges-before.log"
bash "$P/session.sh" %SYS "$P/enable.os" "$L/enable.log"
timeout 600 python "$P/privilege_probe.py" "$L/probe.json" --revoke-as irisowner,_SYSTEM "$@" > "$L/probe.log" 2> "$L/probe.stderr" \
  || echo "probe exit $?" >> "$log"
bash "$P/session.sh" %SYS "$P/privileges.os" "$L/privileges-after.log"
bash "$P/session.sh" %SYS "$P/disable.os" "$L/disable.log"
python "$P/login_check.py" > "$L/login-after-disable.log" 2>&1
bash "$P/session.sh" %SYS "$P/privileges.os" "$L/privileges-final.log"
echo "== run-$round end $(date -u +%FT%TZ)" >> "$log"
