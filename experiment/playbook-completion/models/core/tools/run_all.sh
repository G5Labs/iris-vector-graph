#!/usr/bin/env bash
# Run every core-models check in its own process with its own log, then merge RESULTS.json (tools/merge_results.py).
#   bash experiment/playbook-completion/models/core/tools/run_all.sh [ID|PREFIX* ...]
# Run it under `tools/locks.sh heavy`: the largest checks need about 2-3 GB and a minute each.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
source "$here/../../environment.sh" >/dev/null
cd "$here"
export CARGO_TARGET_DIR="$RUN_DIR/target/core-models"
cargo build --release 2>&1 | tail -1
bin="$CARGO_TARGET_DIR/release/ivg-core-models"
out="$RUN_DIR/core-models/final"
mkdir -p "$out/logs" "$out/json"
if [ "$#" -gt 0 ]; then ids=$("$bin" --list | awk '{print $1}' | while read -r i; do for p in "$@"; do
  case "$p" in *\*) [[ "$i" == "${p%\*}"* ]] && echo "$i";; *) [[ "$i" == "$p" ]] && echo "$i";; esac; done; done)
else ids=$("$bin" --list | awk '{print $1}'); fi
for id in $ids; do
  echo "== $id"
  timeout 3000 /usr/bin/time -v "$bin" --only "$id" --out "$out/json/$id.json" > "$out/logs/$id.log" 2>&1 || true
  grep -E 'MET|Maximum resident' "$out/logs/$id.log" | head -2
done
python3 "$here/tools/merge_results.py" "$out" "$here/RESULTS.json"
