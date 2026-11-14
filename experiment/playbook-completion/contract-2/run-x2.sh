#!/usr/bin/env bash
# Run one contract-2 X2 round on AUDITENV (cases_x2.py, driver_x2.py), chunks of 40 cases, one IRIS lock hold each.
#   bash run-x2.sh <round dir> <seed> [random per family]
set -euo pipefail
: "${RUN_DIR:?source environment.sh first}"
dir="$1"; seed="$2"; k="${3:-25}"
C="$WORK_DIR/experiment/playbook-completion/contract-2/contract"
mkdir -p "$dir"
[ -f "$dir/cases.json" ] || python "$C/native/cases_x2.py" "$dir/cases.json" --seed "$seed" --random "$k"
python - "$dir" <<'PY'
import json, sys
d = sys.argv[1]
ids = [c["id"] for c in json.load(open(f"{d}/cases.json"))]
for i in range(0, len(ids), 40):
    open(f"{d}/chunk-{i // 40:02d}.ids", "w").write("\n".join(ids[i:i + 40]) + "\n")
PY
cd "$WORK_DIR"
for f in "$dir"/chunk-*.ids; do
  g=$(basename "$f" .ids)
  [ -f "$dir/$g.done" ] && continue
  echo "== $g $(date -u +%H:%M:%S)" >> "$dir/driver.log"
  bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 \
    python "$C/native/driver_x2.py" "$dir/cases.json" "$dir/observed.json" --only $(cat "$f") >> "$dir/driver.log" 2>&1
  touch "$dir/$g.done"
done
echo "== all chunks done $(date -u +%H:%M:%S)" >> "$dir/driver.log"
