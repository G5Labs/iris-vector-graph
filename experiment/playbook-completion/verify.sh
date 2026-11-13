#!/usr/bin/env bash
# One verification entry point for the completion audit of IVG pin 3eaa79cf.
#
#   bash experiment/playbook-completion/verify.sh            # fast offline gate (target < 20 min)
#   bash experiment/playbook-completion/verify.sh --full     # + every model crate, every proof and control
#   bash experiment/playbook-completion/verify.sh --live     # + native IRIS rounds on the dedicated container
#
# Logs go to $RUN_DIR/verify/<UTC stamp>/ with summary.json (each step: command, exit, seconds, log SHA-256),
# versions.txt (toolchain and engine) and inputs.txt (candidate commit, product tree, experiment tree hashes).
# A step's result is its exit code; nothing is marked passed unless it ran and exited 0. Inconclusive steps
# (resource limit, lock wait timeout, missing dependency) are recorded as such, never as a pass.
set -uo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
cd "$repo"
mode="${1:-fast}"; mode="${mode#--}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$RUN_DIR/verify/$stamp"; mkdir -p "$out"
summary="$out/summary.jsonl"; : > "$summary"
T="$RUN_DIR/target"

step() {  # step <id> <timeout-seconds> <command...>
  local id="$1" secs="$2"; shift 2
  local log="$out/$id.log" t0=$SECONDS
  timeout "$secs" "$@" > "$log" 2>&1; local rc=$?
  local sha; sha="$(sha256sum "$log" | cut -c1-64)"
  printf '{"step":"%s","exit":%d,"seconds":%d,"log":"%s","log_sha256":"%s","command":%s}\n' \
    "$id" "$rc" "$((SECONDS - t0))" "${log#$RUN_DIR/}" "$sha" "$(printf '%s' "$*" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')" >> "$summary"
  printf '%-34s exit %-3d %5ds\n' "$id" "$rc" "$((SECONDS - t0))"
}
have() { [[ -e "$1" ]]; }

{
  echo "candidate_commit $(git rev-parse HEAD)"
  echo "product_pin 3eaa79cf77d3e0a879b2cced634cf2729d81499e"
  echo "product_tree_at_pin $(git rev-parse 3eaa79cf^{tree})"
  echo "experiment_tree $(git rev-parse HEAD:experiment/playbook-completion)"
  echo "original_submission_tree $(git rev-parse HEAD:experiment/playbook-uplift)"
} > "$out/inputs.txt"
{
  rustc --version; cargo --version; python --version 2>&1
  "${VERUS_BIN:-verus}" --version 2>/dev/null | head -2 || echo "verus: not on PATH"
  python -c "import importlib.metadata as m;print('intersystems_irispython', m.version('intersystems_irispython'))"
  echo "actors/explorer: $(git -C "$IVG_EXPERIMENT/playbook-reference-actors" rev-parse HEAD 2>/dev/null)"
} > "$out/versions.txt" 2>&1

# ---------------------------------------------------------------- fast offline gate
step product-scope        60  bash "$here/check-product-scope.sh"
step registry             300 python3 "$here/tools/check_registry.py"
step registry-selftest    60  python3 "$here/tools/check_registry.py" --self-test
step ontology-gate        600 python3 "$here/ontology/tools/ontology_check.py" --check
step ontology-selftest    600 python3 "$here/ontology/tools/ontology_check.py" --self-test
step ontology-recheck     600 python3 "$here/ontology/tools/independent_recheck.py"
step matrix               300 python3 "$here/matrix/build_matrix.py" --check
step decoder-map          60  python3 "$here/tools/decoder_map_check.py"
step decoder-map-selftest 60  python3 "$here/tools/decoder_map_check.py" --self-test
step storage-order-selftest 60 python3 "$here/tools/storage_order_check.py" --self-test
step writer-census-selftest 120 python3 "$here/tools/writer_census.py" --self-test
step contract-build       900 env CARGO_TARGET_DIR="$T/iris-contract" cargo build --release --offline --manifest-path "$here/iris-contract/Cargo.toml"
step contract-selftest    600 "$T/iris-contract/release/iris-contract" selftest
step contract-recheck-r2  600 "$T/iris-contract/release/iris-contract" check "$RUN_DIR/env/r2/cases.json" "$RUN_DIR/env/r2/observed.json"
step conformance-recheck  600 python "$here/traces/conformance.py" --check "$RUN_DIR/traces/conf2/trace.json"
step conformance-controls 600 python "$here/traces/conformance.py" --self-test "$RUN_DIR/traces/conf2/trace.json"
step lostack-oracle-selftest 60 python "$here/traces/lost_ack.py" --self-test-oracle

# ---------------------------------------------------------------- full: every model crate, proofs and controls
if [[ "$mode" == full || "$mode" == live ]]; then
  for crate in core breadth-a breadth-b breadth-c; do
    if have "$here/models/$crate/run_all.sh"; then
      step "models-$crate" 7200 bash "$here/tools/locks.sh" heavy bash "$here/models/$crate/run_all.sh" "$out/models-$crate"
    fi
  done
  if have "$here/proofs/tools/run_proofs.py"; then
    step proofs 7200 bash "$here/tools/locks.sh" heavy python "$here/proofs/tools/run_proofs.py" --out "$out/proofs"
  fi
fi

# ---------------------------------------------------------------- live: native rounds on the dedicated engine
if [[ "$mode" == live ]]; then
  L="bash $here/tools/locks.sh iris"
  step contract-live 5400 $L bash -c "python '$here/iris-contract/native/cases.py' '$out/cases.json' --seed $((RANDOM)) --random-per-family 60 && python '$here/iris-contract/native/driver.py' '$out/cases.json' '$out/observed.json' && '$T/iris-contract/release/iris-contract' check '$out/cases.json' '$out/observed.json'"
  step conformance-live 3600 $L python "$here/traces/conformance.py" "$out/conformance" --batch 1
  step f1201-live       3600 $L python "$here/traces/f1201_native.py" "$out/f1201" --trials 4 --seed other
  step lost-ack-live    5400 $L python "$here/traces/lost_ack.py" "$out/lost-ack"
fi

step product-scope-final 60 bash "$here/check-product-scope.sh"
python3 - "$summary" <<'EOF'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
bad = [r["step"] for r in rows if r["exit"] != 0]
print(f"{len(rows)} steps; {len(rows) - len(bad)} exit 0; nonzero: {bad}")
EOF
echo "logs: $out"
