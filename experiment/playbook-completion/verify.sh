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
mode=fast; clean=0
for a in "$@"; do case "$a" in --clean) clean=1;; --fast|--full|--live|--merge) mode="${a#--}";; *) echo "unknown argument $a" >&2; exit 2;; esac; done
# --merge: the bounded merge gate (playbook "One gate = one build on one machine, at most 20 minutes"): one run under a
# hard 1200-second envelope; hitting it fails the gate. Spec and trust checks, Verus on changed crates only, a fixed
# native-IRIS canary set and the touched slices' trace replay; every crate's Verus with its controls and the full live
# rounds stay in the periodic full verification (--live --clean).
if [[ "$mode" == merge && -z "${VERIFY_ENVELOPED:-}" ]]; then
  exec timeout --kill-after=10 1200 env VERIFY_ENVELOPED=1 bash "$0" "$@"
fi
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$RUN_DIR/verify/$stamp"; mkdir -p "$out"
summary="$out/summary.jsonl"; : > "$summary"
T="$RUN_DIR/target"
# --clean: every build from empty target directories under this run (model crates: $out/target; proof runners: a
# private RUN_DIR whose locks/ is the shared lock directory, so the heavy lock still serializes them)
PRD="$RUN_DIR"; POUT="$out"
if [[ "$clean" == 1 ]]; then
  T="$out/target"; PRD="$out/cleanroot"; POUT="$out/cleanroot/proofs-out"
  mkdir -p "$PRD" "$POUT"; ln -sfn "$RUN_DIR/locks" "$PRD/locks"
  # recorded contract rounds read by proofs-env's differential (inputs, not build outputs)
  ln -sfn "$RUN_DIR/env" "$PRD/env"; ln -sfn "$RUN_DIR/contract-2" "$PRD/contract-2"
fi

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
  echo "mode $mode clean $clean"
  echo "worktree_status_lines $(git status --porcelain | wc -l)"
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
step ignored-files        60  python3 "$here/tools/ignored_check.py"
step ignored-selftest     60  python3 "$here/tools/ignored_check.py" --self-test
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
step intent-check         120 python3 "$here/tools/intent_check.py"
step intent-selftest      300 python3 "$here/tools/intent_check.py" --self-test
step status-numbers      120 python3 "$here/tools/status_numbers.py" --check
step status-numbers-selftest 300 python3 "$here/tools/status_numbers.py" --self-test
step coverage-reconcile   600 python3 "$here/ontology/tools/coverage_reconcile.py" --require-zero
step coverage-selftest    900 python3 "$here/ontology/tools/coverage_reconcile.py" --self-test
step writesets-check      300 python3 "$here/writesets/tools/check_discharges.py"
step writesets-selftest   600 python3 "$here/writesets/tools/check_discharges.py" --self-test
step semantics-check      300 python3 "$here/semantics/tools/check_semantics.py"
step semantics-selftest   600 python3 "$here/semantics/tools/check_semantics.py" --self-test
step root-causes-check    300 python3 "$here/reflection/tools/check_root_causes.py"
step root-causes-selftest 600 python3 "$here/reflection/tools/check_root_causes.py" --self-test
step premise-map-check    300 python3 "$here/reflection/tools/check_premise_map.py"
step premise-map-selftest 600 python3 "$here/reflection/tools/check_premise_map.py" --self-test
step closure-check       300 python3 "$here/reflection/tools/check_closure.py"
step closure-selftest    600 python3 "$here/reflection/tools/check_closure.py" --self-test
step ownership-selftest   600 python "$here/structural/ownership/ownership.py" --self-test
step crash-oracle-selftest 60 python "$here/traces/crash_world.py" --self-test-oracle
rm -rf "$out/disconnect-copy"; cp -r "$RUN_DIR/product-gates/disconnect-r1" "$out/disconnect-copy" 2>/dev/null
step disconnect-oracle-selftest 300 python "$here/product-gates/disconnect_world.py" --self-test-oracle "$out/disconnect-copy"
step contract-build       900 env CARGO_TARGET_DIR="$T/iris-contract" cargo build --release --offline --manifest-path "$here/iris-contract/Cargo.toml"
step contract-selftest    600 "$T/iris-contract/release/iris-contract" selftest
round="$(cat "$here/iris-contract/VALIDATED_ROUND" 2>/dev/null || echo r2)"   # the latest round that met the gate
step contract-recheck-round 600 "$T/iris-contract/release/iris-contract" check "$RUN_DIR/env/$round/cases.json" "$RUN_DIR/env/$round/observed.json"
step conformance-recheck  600 python "$here/traces/conformance.py" --check "$RUN_DIR/traces/conf2/trace.json"
step conformance-controls 600 python "$here/traces/conformance.py" --self-test "$RUN_DIR/traces/conf2/trace.json"
step lostack-oracle-selftest 60 python "$here/traces/lost_ack.py" --self-test-oracle
step verus-json-selftest  60 python3 "$here/tools/verus_json.py" --self-test

# ---------------------------------------------------------------- merge: the bounded merge gate (hard 1200 s)
if [[ "$mode" == merge ]]; then
  MG="python3 $here/tools/merge_gate.py"
  BASE="${MERGE_BASE:-$($MG base)}"; echo "merge_base $BASE" >> "$out/inputs.txt"
  echo "changed_crates $($MG changed-crates "$BASE")" >> "$out/inputs.txt"
  echo "touched_modules $($MG touched-modules "$BASE")" >> "$out/inputs.txt"
  step merge-selftest      60  $MG --self-test
  step merge-trust-scan    120 $MG trust-scan
  step merge-cache-check   300 $MG cache-check "$BASE"
  for crate in $($MG changed-crates "$BASE"); do
    step "merge-verus-$crate" 900 $MG verus "$crate" "$out/verus-$crate"
  done
  # fixed canary set on the dedicated IRIS (native counterparts of the playbook's real-database canaries)
  L="bash $here/tools/locks.sh iris"
  N="$here/iris-contract/native"
  step canary-contract-named 600 $L bash -c "python '$N/cases.py' '$out/canary-cases.json' --random-per-family 0 --ext-per-family 0 && python '$N/driver.py' '$out/canary-cases.json' '$out/canary-observed.json' && { '$T/iris-contract/release/iris-contract' check '$out/canary-cases.json' '$out/canary-observed.json' > '$out/canary-check.txt' 2>&1; $MG contract-outside '$out/canary-check.txt'; }"
  step canary-conformance  300 $L python "$here/traces/conformance.py" "$out/conformance" --batch 1
  step canary-f1201        300 $L python "$here/traces/f1201_native.py" "$out/f1201" --trials 2 --seed other
  # touched slices: each touched module's trace replay through its machines, captured into a private RUN_DIR so no
  # registered trace is overwritten (modules 12-14 are the ledger slice of the conformance and F-1201 canaries; 15 has
  # no FHIR server here)
  MRD="$out/mergeroot"; mkdir -p "$MRD"; ln -sfn "$RUN_DIR/locks" "$MRD/locks"
  for nn in $($MG touched-modules "$BASE"); do
    if [[ -f "$here/trace-replay/m$nn.py" ]] && ! $MG blocked-replay | grep -qw "$nn"; then
      step "slice-$nn" 600 $L env RUN_DIR="$MRD" TR_NAMESPACE=AUDITE bash -c "cd '$here/trace-replay' && python run.py capture $nn && python run.py check $nn"
    else
      echo "slice-$nn: no runnable trace-replay scenario (12-14: covered by the ledger canaries; blocked replay, e.g. 15: no FHIR server)" >> "$out/inputs.txt"
    fi
  done
fi

# ---------------------------------------------------------------- full: every model crate, proofs and controls
if [[ "$mode" == full || "$mode" == live ]]; then
  # Model crates: build and run every check with output under this verify run only (never into a lane's
  # registered log directories), then compare met/expected counts with the committed RESULTS.json.
  H="bash $here/tools/locks.sh heavy"
  step models-core-build 1800 env CARGO_TARGET_DIR="$T/core-models" cargo build --release --offline --manifest-path "$here/models/core/Cargo.toml"
  step models-core 7200 $H "$T/core-models/release/ivg-core-models" --out "$out/models-core.json"
  for crate in breadth-a breadth-c; do
    step "models-$crate-build" 1800 env CARGO_TARGET_DIR="$T/$crate" cargo build --release --offline --manifest-path "$here/models/$crate/Cargo.toml"
    bin="$(find "$T/$crate/release" -maxdepth 1 -type f -perm -u+x ! -name '*.d' | head -1)"
    step "models-$crate" 7200 $H "$bin" --out "$out/models-$crate.json"
  done
  if have "$here/proofs-breadth/tools/run_proofs.py"; then mkdir -p "$POUT/proofs-breadth"
    step proofs-breadth 3600 env RUN_DIR="$PRD" PROOFS_OUT_DIR="$POUT/proofs-breadth" python "$here/proofs-breadth/tools/run_proofs.py"
  fi
  # breadth-b writes into its own crate directory (compile-time path): build and run a copy under this run
  rm -rf "$out/breadth-b-copy"; cp -r "$here/models/breadth-b" "$out/breadth-b-copy"; rm -rf "$out/breadth-b-copy/results"
  step models-breadth-b-build 1800 env CARGO_TARGET_DIR="$T/breadth-b-verify" cargo build --release --offline --manifest-path "$out/breadth-b-copy/Cargo.toml"
  step models-breadth-b 7200 $H "$T/breadth-b-verify/release/breadth-b"
  cp "$out/breadth-b-copy/RESULTS.json" "$out/models-breadth-b.json" 2>/dev/null || true
  if have "$here/proofs-d9/tools/run_proofs.py"; then mkdir -p "$POUT/proofs-d9"
    step proofs-d9 3600 env RUN_DIR="$PRD" PROOFS_OUT_DIR="$POUT/proofs-d9" python "$here/proofs-d9/tools/run_proofs.py"
  fi
  if have "$here/proofs-d1b/tools/run_proofs.py"; then mkdir -p "$POUT/proofs-d1b"
    step proofs-d1b 3600 env RUN_DIR="$PRD" PROOFS_OUT_DIR="$POUT/proofs-d1b" python "$here/proofs-d1b/tools/run_proofs.py"
  fi
  if have "$here/proofs-d1c/tools/run_proofs.py"; then mkdir -p "$POUT/proofs-d1c"
    step proofs-d1c 3600 env RUN_DIR="$PRD" PROOFS_OUT_DIR="$POUT/proofs-d1c" python "$here/proofs-d1c/tools/run_proofs.py"
  fi
  if have "$here/proofs-d1d/tools/run_proofs.py"; then mkdir -p "$POUT/proofs-d1d"
    step proofs-d1d 3600 env RUN_DIR="$PRD" PROOFS_OUT_DIR="$POUT/proofs-d1d" python "$here/proofs-d1d/tools/run_proofs.py"
  fi
  if have "$here/proofs-d1e/tools/run_proofs.py"; then mkdir -p "$POUT/proofs-d1e"
    step proofs-d1e 3600 env RUN_DIR="$PRD" PROOFS_OUT_DIR="$POUT/proofs-d1e" python "$here/proofs-d1e/tools/run_proofs.py"
  fi
  if have "$here/proofs-d1f/tools/run_proofs.py"; then mkdir -p "$POUT/proofs-d1f"
    step proofs-d1f 3600 env RUN_DIR="$PRD" PROOFS_OUT_DIR="$POUT/proofs-d1f" python "$here/proofs-d1f/tools/run_proofs.py"
  fi
  for crate in proofs-d9b proofs-d9c proofs-pa3 proofs-mech proofs-sys proofs-env; do
    if have "$here/$crate/tools/run_proofs.py"; then mkdir -p "$POUT/$crate"
      step "$crate" 3600 env RUN_DIR="$PRD" PROOFS_OUT_DIR="$POUT/$crate" python "$here/$crate/tools/run_proofs.py"
    fi
  done
  # §3.3a mechanisms (explorer over a trait) and the D-10 partition (pieces only; the two 15-17 GB unpartitioned
  # runs are registered as m2p-full-* and not repeated here)
  step models-semantics-build 1800 env CARGO_TARGET_DIR="$T/semantics" cargo build --release --offline --manifest-path "$here/models/semantics/Cargo.toml"
  step models-semantics 3600 $H "$T/semantics/release/ivg-semantics-models" --out "$out/models-semantics.json"
  step models-core-partition-build 1800 env CARGO_TARGET_DIR="$T/core-partition" cargo build --release --offline --manifest-path "$here/models/core-partition/Cargo.toml"
  CP="$T/core-partition/release/ivg-core-partition"
  step partition-coverage 3000 "$CP" --coverage 2 2
  for fam in reviewed as-built-isolation-stmt as-built-F1304 as-built-F1305 control-liveness-collapsed control-dropstatements-all-graphs; do
    step "partition-$fam" 3600 $H "$CP" --family "$fam" 2 2 --out "$out/partition-$fam.json"
  done
  step models-compare 120 python3 "$here/tools/compare_model_results.py" "$out"
  if have "$here/proofs/tools/run_proofs.py"; then mkdir -p "$POUT/proofs"
    step proofs 7200 env RUN_DIR="$PRD" PROOFS_OUT_DIR="$POUT/proofs" python "$here/proofs/tools/run_proofs.py"  # takes the heavy lock per Verus run itself; writes under $out
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
import os
debt = os.path.join(os.path.dirname(sys.argv[1]), "merge-debt.jsonl")
if os.path.exists(debt):
    for l in open(debt):
        print("INCONCLUSIVE (proof debt, not a pass):", l.strip())
sys.exit(1 if bad else 0)
EOF
rc=$?
echo "logs: $out"
exit $rc
