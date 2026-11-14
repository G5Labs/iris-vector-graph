#!/usr/bin/env bash
# Review 4 (fork d9b-pa3-m2p): rerun the small checks of models/core-partition with my own build and output dir.
# Not using run_partition.py because it writes RESULTS.json into the crate and logs into $RUN_DIR/models-2.
set -u
source /home/ziniu_wu_g5labs_ai/experiments/iris-vector-graph-playbook-uplift-20261113/iris-vector-graph-audit/experiment/playbook-completion/environment.sh >/dev/null
O=$RUN_DIR/review-4/core-partition/small; mkdir -p $O
B=$RUN_DIR/review-4/core-partition/target/release/ivg-core-partition
run() { tag=$1; shift; /usr/bin/time -v timeout 1200 $B "$@" > $O/$tag.log 2>&1; echo "$tag rc=$?"; }
run coverage-keys --coverage 2 2
run coverage-keys-control --coverage 2 2 --broken-key
run union-a-reviewed --union 1 2 reviewed
run union-b-reviewed --union 2 1 reviewed
run union-b-as-built --union 2 1 as-built
run union-c-reviewed --union 0 3 reviewed
run union-control --union 2 1 reviewed --broken-key
run fidelity --only fidelity-m1-reviewed-a fidelity-m1-reviewed-b fidelity-m1-reviewed-c fidelity-m1-as-built-isolation-stmt-a fidelity-m1-as-built-isolation-stmt-b fidelity-m1-as-built-isolation-stmt-c
run family-as-built-F1304 --family as-built-F1304 2 2 --out $O/family-as-built-F1304.json
run family-control-liveness-collapsed --family control-liveness-collapsed 2 2 --out $O/family-control-liveness-collapsed.json
run family-control-dropstatements-all-graphs --family control-dropstatements-all-graphs 2 2 --out $O/family-control-dropstatements-all-graphs.json
echo SMALLDONE
