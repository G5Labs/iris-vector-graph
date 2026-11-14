#!/usr/bin/env bash
# The privilege lane's IRIS steps in one hold of tools/locks.sh iris (audit container, AUDITB / %SYS / AUDITENV):
#   bash run-all.sh            (takes the lock itself)
# 1 create the role and user (%SYS), 2 SQL grants (AUDITB), 3 list the privileges, 4 the live probe, 5 list again,
# 6 disable the user, 7 login check, 8 final listing; then the 2026.1 driver probes (AUDITENV, ^IVGAudit* only).
set -euo pipefail
: "${RUN_DIR:?source environment.sh first}"
if [ "${IVG_LOCK_HELD:-0}" != 1 ]; then
  exec bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris env IVG_LOCK_HELD=1 bash "$0" "$@"
fi
P="$WORK_DIR/experiment/playbook-completion/versions/privilege"; V="$WORK_DIR/experiment/playbook-completion/versions"
L="$RUN_DIR/versions/privilege"; mkdir -p "$L"
log="$L/run-all.log"
echo "== run-all start $(date -u +%FT%TZ) (lock held)" >> "$log"
bash "$P/session.sh" %SYS "$P/create.os" "$L/create.log"
grep -q "<<USER::USER>>" "$L/create.log" || { echo "create failed" >> "$log"; exit 1; }
bash "$P/session.sh" AUDITB "$P/grant.os" "$L/grant.log"
bash "$P/session.sh" %SYS "$P/privileges.os" "$L/privileges-before.log"
timeout 600 python "$P/privilege_probe.py" "$L/probe.json" > "$L/probe.log" 2> "$L/probe.stderr" || echo "probe exit $?" >> "$log"
bash "$P/session.sh" %SYS "$P/privileges.os" "$L/privileges-after.log"
python "$P/login_check.py" > "$L/login-before-disable.log" 2>&1
bash "$P/session.sh" %SYS "$P/disable.os" "$L/disable.log"
python "$P/login_check.py" > "$L/login-after-disable.log" 2>&1
bash "$P/session.sh" %SYS "$P/privileges.os" "$L/privileges-final.log"
# 2026.1 driver probes (both builds)
main_sp=$("$VIRTUAL_ENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')
pp4="$RUN_DIR/availability/driver-5.4.0-venv/lib/python3.11/site-packages:$main_sp:$WORK_DIR"
for f in autocommit_probe sql_verbs_entry_probe; do
  out="$RUN_DIR/versions/logs/${f//_/-}-e261.log"
  { date -u +%FT%TZ; echo "## 2026.1 x 5.3.2"; timeout 120 python "$V/$f.py" AUDITENV 2>&1 | grep -v "^WARNING:root";
    echo "## 2026.1 x 5.4.0"; PYTHONPATH="$pp4" timeout 120 python "$V/$f.py" AUDITENV 2>&1 | grep -v "^WARNING:root"; } > "$out"
done
echo "== run-all end $(date -u +%FT%TZ)" >> "$log"
