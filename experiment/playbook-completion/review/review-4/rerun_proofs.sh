#!/usr/bin/env bash
# Review 4: independent recheck of each in-scope proof crate into $RUN_DIR/review-4/<crate>.
# The runners take the heavy lock per Verus run themselves; this script must NOT be wrapped in locks.sh heavy.
set -u
cd /home/ziniu_wu_g5labs_ai/experiments/iris-vector-graph-playbook-uplift-20261113/iris-vector-graph-audit
source experiment/playbook-completion/environment.sh >/dev/null
for c in proofs-d1c proofs-d1d proofs-d1e proofs-d1f proofs-d9b proofs-pa3; do
  mkdir -p "$RUN_DIR/review-4/$c"
  echo "== $c start $(date -u +%FT%TZ)"
  PROOFS_OUT_DIR="$RUN_DIR/review-4/$c" timeout 5400 python experiment/playbook-completion/$c/tools/run_proofs.py \
     > "$RUN_DIR/review-4/$c/runner.out" 2>&1
  echo "== $c exit $? $(date -u +%FT%TZ)"
  tail -3 "$RUN_DIR/review-4/$c/runner.out"
done
echo ALLDONE
