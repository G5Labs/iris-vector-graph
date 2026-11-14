#!/usr/bin/env bash
# The correspondence lane's live steps in ONE hold of the IRIS lock (fewer acquisitions while the queue is long):
#   bash experiment/playbook-completion/tools/locks.sh iris bash experiment/playbook-completion/correspondence/tools/run_locked.sh [step ...]
# Each step has its own timeout and log; the line monitor is stopped at the start of every scenario step.
set -uo pipefail
source "$(dirname "$0")/../../environment.sh" >/dev/null
T=experiment/playbook-completion/correspondence/tools
O=$RUN_DIR/correspondence/live
mkdir -p "$O"
steps=("$@"); [ ${#steps[@]} -eq 0 ] && steps=(ext conf f1201 lockplan capacity lostack)
for s in "${steps[@]}"; do
  case "$s" in
    conf|ext|f1201|lostack) cmd=(timeout 900 python "$T/scenarios.py" "$O/traces" "$s" --monitor);;
    lockplan) cmd=(timeout 600 python "$T/lockplan.py" "$O/lockplan");;
    capacity) cmd=(timeout 900 python "$T/capacity.py" "$O/capacity");;
    *) echo "unknown step $s"; continue;;
  esac
  echo "== $s $(date -u +%FT%TZ)" | tee -a "$O/run_live.log"
  "${cmd[@]}" > "$O/$s.log" 2>&1
  echo "== $s exit $? $(date -u +%FT%TZ)" | tee -a "$O/run_live.log"
done
