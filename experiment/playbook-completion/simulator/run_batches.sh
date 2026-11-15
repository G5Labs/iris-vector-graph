#!/usr/bin/env bash
# Runs the simulator in lock holds of at most MINUTES minutes each (lock fairness), with a pause between holds.
#   bash run_batches.sh OUT_DIR FIRST_SEED HOLDS SEEDS_PER_HOLD [MINUTES]
set -uo pipefail
cd "$(dirname "$0")/../../.."
source experiment/playbook-completion/environment.sh >/dev/null
out="$1"; seed="$2"; holds="$3"; per="$4"; minutes="${5:-9}"
mkdir -p "$out"
for h in $(seq 1 "$holds"); do
  end=$((seed + per))
  echo "=== hold $h seeds $seed:$end $(date -u +%FT%TZ)" | tee -a "$out/holds.log"
  timeout $(( ${minutes%.*} * 60 + 240 )) bash experiment/playbook-completion/tools/locks.sh iris \
    python experiment/playbook-completion/simulator/sim.py run "$out" --seeds "$seed:$end" --minutes "$minutes" \
    2>&1 | grep -v WARNING >> "$out/run.log"
  echo "=== hold $h done rc=$? $(date -u +%FT%TZ)" | tee -a "$out/holds.log"
  seed=$end
  sleep 30
done
