//! Completion audit, PROOFS-D1C lane (proof debt D-1, playbook §3.3). See PROOFS.md.
//!
//! - `edge_l1`, `edge_l2`: modules 03 and 05 (with module 12's prefix erase), the structural-versus-temporal edge
//!   (ADR-0009, ADR-0015) as an L1 business contract and an L2 machine over rdf_edges, ^KG("out"/"in"),
//!   ^KG("tout"/"tin"), Graph_KG.nodes and ^IVG.TemporalStructural, with `Refines<L1>` for every L2 step and both
//!   levels' `SafeContract` invariants; `edge_runs`: the L2 steps as functions.
//! - `stmt_l1`, `stmt_l2`: module 03, the ledger's statement link of a directly written edge, over rdf_edges and
//!   ^IVG.Ledger("stmt"/"tuple").
//! - `bulk_l1`, `bulk_l2`: module 03, a bulk write's atomicity over the committed rows and the loader's chunks.
//! - `tagg_l1`, `tagg_l2`: module 05, the bucket aggregates over ^KG("tout"/"bucket"/"tagg").
//! - `cx_*` (only with their control feature): proved counterexamples, a run of the L2 step relation (as the control
//!   changes it) from its initial state to a step that is not an L1 step.
//! - `witness_*` (only without their family's controls): non-vacuity runs of the reviewed L2 machines.
pub mod edge_l1;
pub mod edge_l2;
pub mod edge_runs;
#[cfg(feature = "control_f0304_store_no_adopt")]
pub mod cx_f0304;
#[cfg(feature = "control_f0505_marker_predicate")]
pub mod cx_f0505;
#[cfg(feature = "control_f0507_purge_keeps_rows")]
pub mod cx_f0507;
#[cfg(feature = "control_fc0501_refused_write_partial")]
pub mod cx_fc0501;
#[cfg(feature = "control_hd0302_delete_removes_row")]
pub mod cx_hd0302;
#[cfg(feature = "control_fc1203_prefix_from_node_rows")]
pub mod cx_fc1203;
#[cfg(feature = "control_fc0301_adopt_after_commit")]
pub mod cx_fc0301;
#[cfg(not(any(feature = "control_f0304_store_no_adopt", feature = "control_f0505_marker_predicate",
              feature = "control_f0507_purge_keeps_rows", feature = "control_fc0501_refused_write_partial",
              feature = "control_hd0302_delete_removes_row", feature = "control_fc1203_prefix_from_node_rows",
              feature = "control_fc0301_adopt_after_commit")))]
pub mod witness_edge;
pub mod stmt_l1;
pub mod stmt_l2;
pub mod stmt_runs;
#[cfg(feature = "control_f0303_direct_delete_keeps_stmt")]
pub mod cx_f0303;
#[cfg(not(feature = "control_f0303_direct_delete_keeps_stmt"))]
pub mod witness_stmt;
pub mod bulk_l1;
pub mod bulk_l2;
pub mod bulk_runs;
#[cfg(feature = "control_f0305_chunks_commit_alone")]
pub mod cx_f0305;
#[cfg(not(feature = "control_f0305_chunks_commit_alone"))]
pub mod witness_bulk;
pub mod tagg_l1;
pub mod tagg_l2;
pub mod tagg_runs;
#[cfg(feature = "control_f0501_update_counted_again")]
pub mod cx_f0501;
#[cfg(not(feature = "control_f0501_update_counted_again"))]
pub mod witness_tagg;
