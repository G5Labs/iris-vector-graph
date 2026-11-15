#!/usr/bin/env bash
# A whole suite directory in chunks, one iris-lock hold per chunk (CONVENTIONS.md "Connection cap").
#
#   bash experiment/playbook-completion/validation/run_chunks.sh <run-id> <chunks> <timeout-per-chunk> <dir> [-- extra pytest args]
#
# Every test_*.py file under <dir> (sorted, from the clean pin checkout) goes into exactly one of <chunks> contiguous
# chunks; each chunk is one run.sh run with id <run-id>-cNN. The file lists are kept in $RUN_DIR/validation/<run-id>/.
set -uo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
rid=$1; n=$2; to=$3; dir=$4; shift 4
[ "${1:-}" = "--" ] && shift
CO=${VALIDATION_CHECKOUT:-$RUN_DIR/validation/checkout}
mkdir -p "$RUN_DIR/validation/$rid"
if [ -e "$RUN_DIR/validation/$rid/files.txt" ]; then  # resume: same file list and chunks, skip chunks already started
  for f in "$RUN_DIR/validation/$rid"/chunk-*; do
    c=${f##*chunk-}
    [ -e "$RUN_DIR/validation/$rid-c$c/run.log" ] && { echo "skip $rid-c$c (already started)"; continue; }
    mapfile -t files < "$f"
    bash "$WORK_DIR/experiment/playbook-completion/validation/run.sh" "$rid-c$c" "$to" -- "${files[@]}" "$@"
  done
  exit 0
fi
(cd "$CO" && find "$dir" -name 'test_*.py' -type f | LC_ALL=C sort) > "$RUN_DIR/validation/$rid/files.txt"
total=$(wc -l < "$RUN_DIR/validation/$rid/files.txt")
per=$(( (total + n - 1) / n ))
split -d -a 2 -l "$per" "$RUN_DIR/validation/$rid/files.txt" "$RUN_DIR/validation/$rid/chunk-"
echo "$rid: $total files in $(ls "$RUN_DIR/validation/$rid"/chunk-* | wc -l) chunks of <= $per"
for f in "$RUN_DIR/validation/$rid"/chunk-*; do
  c=${f##*chunk-}
  mapfile -t files < "$f"
  bash "$WORK_DIR/experiment/playbook-completion/validation/run.sh" "$rid-c$c" "$to" -- "${files[@]}" "$@"
done
