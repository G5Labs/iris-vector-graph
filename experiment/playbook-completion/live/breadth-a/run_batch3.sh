#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
python cleanup_j07.py
python probes_06.py p0616_selector_crosses_graphs_and_like
python probes_04.py pC0403_failed_rebuild_leaves_partial_adjacency
