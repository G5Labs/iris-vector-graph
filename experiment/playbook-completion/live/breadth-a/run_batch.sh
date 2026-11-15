#!/usr/bin/env bash
# One IRIS lock hold for breadth lane A's remaining live work (connection cap: at most 3 connections at once here).
set -u
cd "$(dirname "$0")"
python probes_01.py
python probes_05.py pC0501_refused_temporal_write_is_partial
python probes_06.py p0614_embed_nodes_refusal_counted p0616_selector_crosses_graphs_and_like
python probes_ledger.py
python journal_validate.py "$@"
