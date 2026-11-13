#!/usr/bin/env bash
# Reproduce every gate of the IVG playbook uplift from the experiment branch.
#
#   bash experiment/playbook-uplift/tools/check_all.sh            # offline gates (no IRIS): about 10 minutes
#   bash experiment/playbook-uplift/tools/check_all.sh --live     # also rerun the live scenarios and the upstream
#                                                                 # Community suite on $IVG_TEST_CONTAINER, register them
#
# Offline gates: the ontology index (--check), the write-set obligations (--check), the ontology checker's self-test,
# the model checks (all eleven must meet their stated expectation; needs about 10 GB of memory), and the Verus proof gate
# (baseline under --no-cheating plus six controls that must fail). Logs go to $RUN_DIR/final.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
uplift="$(dirname "$here")"
repo="$(cd "$uplift/../.." && pwd)"
: "${RUN_DIR:?source the experiment environment.sh first}"
mkdir -p "$RUN_DIR/final"
cd "$repo"
if [[ "${1:-}" == --live ]]; then
  python "$uplift/native/scenarios.py" --out "$RUN_DIR/final/native" > "$RUN_DIR/final/native.log" 2>&1
  python "$RUN_DIR/run-community-redaction.py" > "$RUN_DIR/final/upstream-community-redaction.log" 2>&1
fi
( cd "$uplift/model" && CARGO_TARGET_DIR="$RUN_DIR/mc/target" cargo build --release -q \
  && "$RUN_DIR/mc/target/release/ivg-redaction-model" --out "$RUN_DIR/final/mc-summary.json" > "$RUN_DIR/final/mc.log" 2>&1 )
tail -1 "$RUN_DIR/final/mc.log"
python "$here/run_verus.py" > "$RUN_DIR/final/verus.log" 2>&1
tail -1 "$RUN_DIR/final/verus.log"
python "$here/register_all.py"
python "$here/test_results.py"
python "$here/ontology_index.py" --self-test | tail -1
python "$here/writesets.py" --check
python "$here/ontology_index.py" --check
