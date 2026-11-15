#!/usr/bin/env bash
# Several files, one pytest session each, inside ONE tools/locks.sh iris hold (CONVENTIONS.md "Connection cap").
#
#   bash experiment/playbook-completion/validation/run_files_one_hold.sh <id> <timeout-per-file> <file...>
#
# For fixtures that keep connections open for their whole session (tests/conftest.py Scratch236 keeps every
# connection it opens until session end), so one session per file keeps the container under its 8 licence units.
# Each file gets $RUN_DIR/validation/<id>-fNN/{run.log,junit.xml,meta.json,exit}, as run.sh writes them.
# Environment is passed through (VALIDATION_SCRATCH_NS, IVG_NS_IVG236, ...).
set -uo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
id=$1; to=$2; shift 2
CO=${VALIDATION_CHECKOUT:-$RUN_DIR/validation/checkout}
PIN=3eaa79cf77d3e0a879b2cced634cf2729d81499e
[ "$(git -C "$CO" rev-parse HEAD)" = "$PIN" ] || { echo "checkout not at pin" >&2; exit 2; }
git -C "$CO" diff --quiet HEAD -- || { echo "checkout has tracked changes" >&2; exit 2; }
export IVG_GATE_NAMESPACES=${IVG_GATE_NAMESPACES:-0} PYTHONPATH="$CO"
inner=$(mktemp "$RUN_DIR/validation/.one-hold-XXXX.sh")
{
  echo 'set -uo pipefail'
  i=0
  for f in "$@"; do
    d="$RUN_DIR/validation/$id-f$(printf %02d $i)"
    echo "mkdir -p '$d'"
    echo "{ echo '# id=$(basename "$d") start_utc='\$(date -u +%FT%TZ)' checkout=$CO head=$PIN one-hold=$id'; echo '# cmd: (cd $CO && timeout $to python $WORK_DIR/experiment/playbook-completion/validation/run_suite.py --meta $d/meta.json -- $f --junitxml=$d/junit.xml -ra)'; echo '# env: VALIDATION_SCRATCH_NS='\${VALIDATION_SCRATCH_NS:-} 'IVG_NS_IVG236='\${IVG_NS_IVG236:-} 'IVG_GATE_NAMESPACES='\$IVG_GATE_NAMESPACES; } > '$d/run.log'"
    echo "s=\$(date +%s); (cd '$CO' && timeout $to python '$WORK_DIR/experiment/playbook-completion/validation/run_suite.py' --meta '$d/meta.json' -- '$f' --junitxml='$d/junit.xml' -ra) >> '$d/run.log' 2>&1; rc=\$?"
    echo "echo \"# exit=\$rc wall_seconds=\$((\$(date +%s) - s)) end_utc=\$(date -u +%FT%TZ)\" >> '$d/run.log'; echo \$rc > '$d/exit'; echo \"$(basename "$d") $f exit=\$rc\""
    i=$((i + 1))
  done
} > "$inner"
bash "$WORK_DIR/experiment/playbook-completion/tools/locks.sh" iris bash "$inner"
rm -f "$inner"
