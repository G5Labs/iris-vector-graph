#!/usr/bin/env bash
# Live steps of the correspondence lane, each under its own hold of the IRIS lock (AUDITC only).
#   bash experiment/playbook-completion/correspondence/tools/run_live.sh [step ...]
set -uo pipefail
source "$(dirname "$0")/../../environment.sh" >/dev/null
T=experiment/playbook-completion/correspondence/tools
L=experiment/playbook-completion/tools/locks.sh
O=$RUN_DIR/correspondence/live
mkdir -p "$O"
steps=("$@"); [ ${#steps[@]} -eq 0 ] && steps=(conf ext f1201 lostack lockplan capacity)
for s in "${steps[@]}"; do
  case "$s" in
    conf|ext|f1201|lostack) cmd=(timeout 1200 python "$T/scenarios.py" "$O/traces" "$s" --monitor);;
    lockplan) cmd=(timeout 1200 python "$T/lockplan.py" "$O/lockplan");;
    capacity) cmd=(timeout 1200 python "$T/capacity.py" "$O/capacity");;
    *) echo "unknown step $s"; continue;;
  esac
  echo "== $s $(date -u +%FT%TZ)" | tee -a "$O/run_live.log"
  bash "$L" iris "${cmd[@]}" > "$O/$s.log" 2>&1
  echo "== $s exit $? $(date -u +%FT%TZ)" | tee -a "$O/run_live.log"
done
