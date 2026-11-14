#!/usr/bin/env bash
# Run one iris-contract round in chunks (one IRIS lock hold per chunk, so other lanes interleave).
#   bash run-round.sh <round dir> <seed>
set -euo pipefail
: "${RUN_DIR:?source environment.sh first}"
dir="$1"; seed="$2"
C="$WORK_DIR/experiment/playbook-completion/iris-contract"
mkdir -p "$dir"
[ -f "$dir/cases.json" ] || python "$C/native/cases.py" "$dir/cases.json" --seed "$seed" --random-per-family 60 --ext-per-family 30
python - "$dir" <<'EOF'
import json, sys, collections
d = sys.argv[1]
cases = json.load(open(f"{d}/cases.json"))
groups = collections.OrderedDict()
for c in cases:
    cid = c["id"]
    g = "-".join(cid.split("-")[:2]) if cid.startswith("rand-") else ("named-ext" if c["clause"] and any(
        cid.startswith(p) for p in ("fx-", "noindex-", "nocheck-", "build-", "ddl-", "select-star", "alter-", "enc-",
                                    "stmt-", "autocommit-off-failed", "sql-tlevel", "vec-", "zstrip-", "order-")) else "named")
    groups.setdefault(g, []).append(cid)
for g, ids in groups.items():
    open(f"{d}/chunk-{g}.ids", "w").write("\n".join(ids) + "\n")
print(" ".join(f"{g}:{len(v)}" for g, v in groups.items()))
EOF
for f in "$dir"/chunk-*.ids; do
  g=$(basename "$f" .ids)
  if [ -f "$dir/$g.done" ]; then continue; fi
  echo "== $g $(date -u +%H:%M:%S)" >> "$dir/driver.log"
  bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris timeout 1500 \
    python "$C/native/driver.py" "$dir/cases.json" "$dir/observed.json" --only $(cat "$f") >> "$dir/driver.log" 2>&1
  touch "$dir/$g.done"
done
echo "== all chunks done $(date -u +%H:%M:%S)" >> "$dir/driver.log"
