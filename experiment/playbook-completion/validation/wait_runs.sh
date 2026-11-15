#!/usr/bin/env bash
# Wait (<= $2 seconds, default 570) until run <id> ($1) has an exit file, then print one line per finished run since
# the marker file, with its pytest summary. Read-only.
: "${RUN_DIR:?}"
target=$1; limit=${2:-570}
mark="$RUN_DIR/validation/.wait-mark"
[ -e "$mark" ] || touch -d '2000-01-01' "$mark"
for _ in $(seq 1 $((limit / 5))); do [ -e "$RUN_DIR/validation/$target/exit" ] && break; sleep 5; done
find "$RUN_DIR/validation" -maxdepth 2 -name exit -newer "$mark" | sort | while read -r f; do
  d=$(dirname "$f"); s=$(grep -E '^=+ .* in [0-9.]+s' "$d/run.log" 2>/dev/null | tail -1 | tr -d '=')
  echo "$(basename "$d") exit=$(cat "$f") ${s}"
done
touch "$mark"
date -u +%FT%TZ
