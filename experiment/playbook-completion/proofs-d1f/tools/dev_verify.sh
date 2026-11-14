#!/usr/bin/env bash
# Development (unregistered) Verus run of this crate: tools/dev_verify.sh <tag> [features]
# Log: $RUN_DIR/proofs-d1f/scratch/<tag>.log. Never a decisive run (tools/run_proofs.py makes those).
set -euo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
here="$(cd "$(dirname "$0")/.." && pwd)"
tag="${1:?tag}"; feat="${2:-}"
mkdir -p "$RUN_DIR/proofs-d1f/scratch"
export CARGO_TARGET_DIR="$RUN_DIR/target/proofs-d1f"
cd "$here"
cargo clean -p ivg-d1f-proofs --offline >/dev/null 2>&1 || true
args=(cargo verus verify --offline --fwd-verus-args-to roots)
[ -n "$feat" ] && args+=(--features "$feat")
args+=(-- --no-cheating --triggers-mode silent)
bash "$here/../tools/locks.sh" heavy timeout 3600 "${args[@]}" > "$RUN_DIR/proofs-d1f/scratch/$tag.log" 2>&1 || true
grep -E '^(error|warning: unused)|verification results|-->' "$RUN_DIR/proofs-d1f/scratch/$tag.log" | grep -v 'actors/src' | head -80
