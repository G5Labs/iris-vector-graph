#!/usr/bin/env bash
# Run one E-1 round (the pin's compiled embedded SQL in AUDITCORE vs the contract's permitted sets).
#   bash run-e1.sh <round dir> <seed> [random K] [--journal]
# Chunks of 20 cases, one IRIS lock hold each (other lanes interleave).
set -euo pipefail
: "${RUN_DIR:?source environment.sh first}"
dir="$1"; seed="$2"; k="${3:-40}"; j="${4:-}"
C="$WORK_DIR/experiment/playbook-completion/contract-2/contract"
mkdir -p "$dir"
[ -f "$dir/cases.json" ] || python "$C/native/cases_e1.py" "$dir/cases.json" --seed "$seed" --random "$k"
python - "$dir" <<'PY'
import json, sys
d = sys.argv[1]
ids = [c["id"] for c in json.load(open(f"{d}/cases.json"))]
for i in range(0, len(ids), 20):
    open(f"{d}/chunk-{i // 20:02d}.ids", "w").write("\n".join(ids[i:i + 20]) + "\n")
PY
for f in "$dir"/chunk-*.ids; do
  g=$(basename "$f" .ids)
  [ -f "$dir/$g.done" ] && continue
  echo "== $g $(date -u +%H:%M:%S)" >> "$dir/driver.log"
  extra=()
  [ "$j" = "--journal" ] && extra=(--journal "$dir/journal.json")
  bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris timeout 1500 \
    python "$C/native/driver_e1.py" "$dir/cases.json" "$dir/observed.json" "${extra[@]}" --only $(cat "$f") >> "$dir/driver.log" 2>&1
  touch "$dir/$g.done"
done
echo "== all chunks done $(date -u +%H:%M:%S)" >> "$dir/driver.log"
