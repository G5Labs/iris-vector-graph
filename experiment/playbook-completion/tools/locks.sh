#!/usr/bin/env bash
# Shared resource locks for the completion audit (playbook §5 resource hygiene).
#
#   bash tools/locks.sh iris  <command...>   # any use of the dedicated IRIS container that resets the namespace,
#                                            # runs product suites, or measures timing
#   bash tools/locks.sh heavy <command...>   # any job expected to use > 4 GB or > 5 minutes (explorer, Verus)
#
# Every wait has a timeout (LOCK_WAIT_SECONDS, default 3 h). The lock is released when the command exits.
# Every hold is logged, one JSON object per line, to $RUN_DIR/locks/holds.jsonl (tools/locks_rec.py), and checked by
# tools/hygiene_check.py:
#   request   this script's pid, parent pid, the command, free disk (GB), the disk floor and the wait cap
#   refused   free disk below LOCK_DISK_FLOOR_GB (default 20): the command does not run, exit 3
#   acquired  seconds waited, and the pid and process group of the command itself (the holder: stop it by this pid)
#   released  the command's exit code
#   timeout   the wait timed out (exit 1, as before)
set -uo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
kind="${1:?iris|heavy}"; shift
case "$kind" in iris|heavy) ;; *) echo "unknown lock $kind" >&2; exit 2;; esac
mkdir -p "$RUN_DIR/locks"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LOCKS_REC="$here/locks_rec.py" LOCKS_LOG="$RUN_DIR/locks/holds.jsonl" LOCKS_KIND="$kind"
export LOCKS_HOLD="$(date -u +%Y%m%dT%H%M%S%N)-$$"
floor="${LOCK_DISK_FLOOR_GB:-20}"
wait="${LOCK_WAIT_SECONDS:-10800}"
avail="$(df --output=avail -BG "$RUN_DIR" 2>/dev/null | tail -1 | tr -dc 0-9)"
cmd_json="$(python3 -c 'import json, sys; print(json.dumps(sys.argv[1:])[:2000])' "$@")"
python3 "$LOCKS_REC" request "pid=$$" "ppid=$PPID" "cmd=$cmd_json" "disk_gb=${avail:-null}" "floor_gb=$floor" \
  "wait_cap_s=$wait"
if [[ -n "$avail" && "$avail" -lt "$floor" ]]; then
  echo "locks.sh: free disk ${avail} GB is below the floor ${floor} GB; not running" >&2
  python3 "$LOCKS_REC" refused "disk_gb=$avail"
  exit 3
fi
export LOCKS_T0="$(date +%s.%N)"
# the inner shell records the acquisition with its own pid, then becomes the command (exec keeps the pid)
flock -E 75 -w "$wait" "$RUN_DIR/locks/$kind.lock" \
  bash -c 'python3 "$LOCKS_REC" acquired "pid=$$"; exec "$@"' locks-holder "$@"
rc=$?
if [[ "$rc" == 75 ]] && ! grep -qF "\"hold\": \"$LOCKS_HOLD\", \"lock\": \"$kind\", \"event\": \"acquired\"" "$LOCKS_LOG"; then
  python3 "$LOCKS_REC" timeout "wait_cap_s=$wait"
  exit 1
fi
python3 "$LOCKS_REC" released "rc=$rc"
exit "$rc"
