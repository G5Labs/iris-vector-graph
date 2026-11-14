#!/usr/bin/env bash
# The venv's python with intersystems-irispython 5.4.0 first on the path (operator ruling 2026-11-14 03:16Z).
export PYTHONPATH="/home/ziniu_wu_g5labs_ai/runs/iris-vector-graph-playbook-uplift-20261113/completion-audit/availability/driver-5.4.0-venv/lib/python3.11/site-packages${PYTHONPATH:+:$PYTHONPATH}"
exec "/home/ziniu_wu_g5labs_ai/runs/iris-vector-graph-playbook-uplift-20261113/playbook/venv/bin/python" "$@"
