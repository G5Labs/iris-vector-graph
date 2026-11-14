#!/usr/bin/env bash
# One lock hold for the module 16 batch (each script starts and stops its own servers by PID):
#   bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 bash run_batch.sh s3 s4 s5
set -u
cd "$(dirname "$0")"
for s in "$@"; do
  f=$(ls ${s}_*.py | head -1)
  echo "=== $f $(date -u +%FT%TZ)"
  timeout 600 python "$f" > "$RUN_DIR/breadth-c/16/${f%.py}.stdout.log" 2>&1
  echo "=== $f exit $? $(date -u +%FT%TZ)"
done
