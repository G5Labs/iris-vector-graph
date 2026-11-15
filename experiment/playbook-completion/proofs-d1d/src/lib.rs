//! Completion audit, PROOFS-D1D lane (proof debt D-1, playbook §3.3). See PROOFS.md.
//!
//! - `bmw_l1`, `bmw_l2`: module 07, one BM25 index's writers (Build, Insert, Delete, Drop) and searches, with the
//!   caller's transaction levels, over ^BM25Idx(name) (postings, token records, the header's counters).
//! - `bmn_l1`, `bmn_l2`: module 07, the namespace's BM25 indexes: the "__stop__" node, tokens, the graph each index
//!   covers and the readers' check, the graph eraser.
//! - `cyw_l1`, `cyw_l2`: module 08, Cypher write queries on the SQL path (three shapes) under the ledger's strict
//!   guard, over nodes, rdf_edges qualifiers, rdf_props and ^IVG.Ledger("meta").
//! - `cys_l1`, `cys_l2`: module 08, graph scope of three read routes over the stored rows.
//! - `planc_l1`, `planc_l2`: module 09, the compiled-plan cache ^IVG.CypherCompiled, its build jobs and its readers.
//! - `nread_l1`, `nread_l2`: module 09, a native read against the SQL path: relationship identity, the executor's
//!   privilege check, the label gate, shadow mode, and another writer's open transaction.
//! - `*_runs`: each L2 machine's steps as functions (valid under every feature).
//! - `cx_*` (only with their control feature): proved counterexamples, a run of the L2 step relation (as the control
//!   changes it) from its initial state to a step that is not an L1 step.
//! - `witness_*` (only without their family's controls): non-vacuity runs of the reviewed L2 machines.
pub mod bmw_l1;
pub mod bmw_l2;
pub mod bmw_runs;
#[cfg(feature = "control_fc0702_bare_trollback")]
pub mod cx_fc0702;
#[cfg(feature = "control_f0701_build_in_place")]
pub mod cx_f0701;
#[cfg(feature = "control_f0704_late_refusal")]
pub mod cx_f0704;
#[cfg(not(any(feature = "control_fc0702_bare_trollback", feature = "control_f0701_build_in_place",
              feature = "control_f0704_late_refusal")))]
pub mod witness_bmw;
pub mod bmn_l1;
pub mod bmn_l2;
pub mod bmn_runs;
#[cfg(feature = "control_fc0701_stop_name_accepted")]
pub mod cx_fc0701;
#[cfg(feature = "control_f0705_absent_graph_is_default")]
pub mod cx_f0705;
#[cfg(feature = "control_f0707_no_scope_check")]
pub mod cx_f0707;
#[cfg(feature = "control_f0702_erase_keeps_index")]
pub mod cx_f0702;
#[cfg(not(any(feature = "control_fc0701_stop_name_accepted", feature = "control_f0705_absent_graph_is_default",
              feature = "control_f0707_no_scope_check", feature = "control_f0702_erase_keeps_index")))]
pub mod witness_bmn;
pub mod cyw_l1;
pub mod cyw_l2;
pub mod cyw_runs;
#[cfg(feature = "control_f0801_ttl_window")]
pub mod cx_f0801_ttl;
#[cfg(feature = "control_f0801_fail_open")]
pub mod cx_f0801_failopen;
#[cfg(feature = "control_f0805_literal_insert_unguarded")]
pub mod cx_f0805;
#[cfg(feature = "control_fc0803_top1_copy")]
pub mod cx_fc0803;
#[cfg(feature = "control_f0810_null_keeps_key")]
pub mod cx_f0810;
#[cfg(not(any(feature = "control_f0801_ttl_window", feature = "control_f0801_fail_open",
              feature = "control_f0805_literal_insert_unguarded", feature = "control_fc0803_top1_copy",
              feature = "control_f0810_null_keeps_key")))]
pub mod witness_cyw;
pub mod cys_l1;
pub mod cys_l2;
#[cfg(feature = "control_f0802_shortcut_unscoped")]
pub mod cx_f0802;
#[cfg(feature = "control_f0816_dblabels_unscoped")]
pub mod cx_f0816;
#[cfg(feature = "control_f0818_vlp_crosses_graphs")]
pub mod cx_f0818;
#[cfg(not(any(feature = "control_f0802_shortcut_unscoped", feature = "control_f0816_dblabels_unscoped",
              feature = "control_f0818_vlp_crosses_graphs")))]
pub mod witness_cys;
pub mod planc_l1;
pub mod planc_l2;
pub mod planc_runs;
#[cfg(feature = "control_f0901_shared_class_name")]
pub mod cx_f0901;
#[cfg(feature = "control_fc0901_mark_any_entry")]
pub mod cx_fc0901;
#[cfg(not(any(feature = "control_f0901_shared_class_name", feature = "control_fc0901_mark_any_entry")))]
pub mod witness_planc;
pub mod nread_l1;
pub mod nread_l2;
pub mod nread_runs;
#[cfg(feature = "control_f0902_crc_identity")]
pub mod cx_f0902;
#[cfg(feature = "control_f0908_run_unchecked")]
pub mod cx_f0908;
#[cfg(feature = "control_hd0902_shadow_swallows_native_error")]
pub mod cx_hd0902;
#[cfg(feature = "control_f0906_gate_edge_index_only")]
pub mod cx_f0906;
#[cfg(not(any(feature = "control_f0902_crc_identity", feature = "control_f0908_run_unchecked",
              feature = "control_hd0902_shadow_swallows_native_error", feature = "control_f0906_gate_edge_index_only")))]
pub mod witness_nread;
