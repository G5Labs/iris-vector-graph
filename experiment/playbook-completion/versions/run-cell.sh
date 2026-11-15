#!/usr/bin/env bash
# One engine x driver cell of the version lane: the contract's SQL/driver transaction-verb cases on one engine with one
# intersystems-irispython build, in chunks, then `iris-contract check`.
#   bash run-cell.sh <cell> <5.3.2|5.4.0> <container> <port> <namespace> <iris|none>
# lock "iris" = the shared audit container (tools/locks.sh iris, one hold per chunk); "none" = this lane's own container.
# Cases: $RUN_DIR/versions/cases-versions-20261114.json (cases.py --seed 20261114, filtered: every named case that uses a
# SQL or driver transaction verb or is a txn-* case, plus the rand-txn and rand-stmt families).
set -euo pipefail
: "${RUN_DIR:?source environment.sh first}"
cell="$1"; drv="$2"; ctr="$3"; port="$4"; ns="$5"; lock="$6"
V="$RUN_DIR/versions"; D="$V/$cell"; HERE="$WORK_DIR/experiment/playbook-completion/versions"
mkdir -p "$D"
main_sp=$("$VIRTUAL_ENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')
case "$drv" in
  5.4.0) pp="$RUN_DIR/availability/driver-5.4.0-venv/lib/python3.11/site-packages:$main_sp:$WORK_DIR" ;;
  5.3.2) pp="$WORK_DIR" ;;
  *) echo "unknown driver $drv" >&2; exit 2 ;;
esac
# CASES (optional) names another cases file, e.g. the unfiltered cases-all-20261114.json for a full-contract cell
[ -f "$D/cases.json" ] || cp "${CASES:-$V/cases-versions-20261114.json}" "$D/cases.json"
python3 - "$D" <<'EOF'
import json, sys
d = sys.argv[1]
groups = {}
for c in json.load(open(f"{d}/cases.json")):
    cid = c["id"]
    g = "-".join(cid.split("-")[:2]) if cid.startswith("rand-") else "named"
    groups.setdefault(g, []).append(cid)
for g, ids in groups.items():
    open(f"{d}/chunk-{g}.ids", "w").write("\n".join(ids) + "\n")
print(" ".join(f"{g}:{len(v)}" for g, v in groups.items()))
EOF
{ echo "== cell $cell driver $drv container $ctr port $port namespace $ns lock $lock $(date -u +%FT%TZ)"
  echo "PYTHONPATH=$pp"; } >> "$D/driver.log"
for f in "$D"/chunk-*.ids; do
  g=$(basename "$f" .ids)
  [ -f "$D/$g.done" ] && continue
  echo "== $g $(date -u +%H:%M:%S)" >> "$D/driver.log"
  cmd=(env PYTHONPATH="$pp" IVG_TEST_CONTAINER="$ctr" IVG_PORT="$port" IVG_CONTRACT_NS="$ns"
       timeout 1500 python "$HERE/run_driver.py" "$V/contract-snapshot/native" "$D/cases.json" "$D/observed.json"
       --only $(cat "$f"))
  if [ "$lock" = iris ]; then
    bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris "${cmd[@]}" >> "$D/driver.log" 2>&1
  else
    "${cmd[@]}" >> "$D/driver.log" 2>&1
  fi
  touch "$D/$g.done"
done
echo "== all chunks done $(date -u +%H:%M:%S)" >> "$D/driver.log"
set +e
"$V/bin/iris-contract" check "$D/cases.json" "$D/observed.json" --out "$D/report.json" > "$D/check.out" 2>&1
echo "check exit $?" >> "$D/check.out"
cat "$D/check.out"
