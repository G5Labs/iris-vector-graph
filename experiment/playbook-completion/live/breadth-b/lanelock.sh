#!/usr/bin/env bash
# Run a command holding the lane-B AUDITB lock (the same flock file blive.lane_lock uses), with a wait timeout.
#   bash experiment/playbook-completion/live/breadth-b/lanelock.sh <command...>
set -euo pipefail
: "${RUN_DIR:?source experiment/playbook-completion/environment.sh first}"
mkdir -p "$RUN_DIR/breadth-b"
exec flock -w "${LANE_LOCK_WAIT_SECONDS:-3600}" "$RUN_DIR/breadth-b/auditb.lock" "$@"
