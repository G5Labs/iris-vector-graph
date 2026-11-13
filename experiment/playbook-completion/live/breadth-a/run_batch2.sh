#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
python probes_06.py p0614_embed_nodes_refusal_counted p0616_selector_crosses_graphs_and_like pC0602_knn_vec_label_rows
python probes_ledger.py p_enable p0303b_direct_delete_keeps_stmt p_disable
