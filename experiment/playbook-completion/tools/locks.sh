#!/usr/bin/env bash
# Shared resource locks for the completion audit (playbook §5 resource hygiene).
#
#   bash tools/locks.sh iris  <command...>   # any use of the dedicated IRIS container that resets the namespace,
#                                            # runs product suites, or measures timing
#   bash tools/locks.sh heavy <command...>   # any job expected to use > 4 GB or > 5 minutes (explorer, Verus)
#
# Every wait has a timeout (IRIS: 3 h, heavy: 3 h). The lock is released when the command exits.
set -euo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
kind="${1:?iris|heavy}"; shift
case "$kind" in iris|heavy) ;; *) echo "unknown lock $kind" >&2; exit 2;; esac
mkdir -p "$RUN_DIR/locks"
exec flock -w "${LOCK_WAIT_SECONDS:-10800}" "$RUN_DIR/locks/$kind.lock" "$@"
