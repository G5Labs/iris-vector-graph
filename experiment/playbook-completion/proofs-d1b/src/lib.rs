//! Completion audit, PROOFS-D1B lane (proof debt D-1, playbook §3.3). See PROOFS.md.
//!
//! - `snap_l1`, `snap_l2`: module 18 (save_snapshot / replacing restore_snapshot against the revision ledger, the
//!   redaction and concurrent writers) as an L1 business contract and an L2 machine over the archive and ledger
//!   storage layout, with `Refines<L1>` for every L2 step and both levels' `SafeContract` invariants; `snap_runs`:
//!   generic save and restore runs of the L2 relation; `vq_runs`: the queue's concrete steps.
//! - `vidx_l1`, `vidx_l2`: module 06, the IVF index lifecycle against erasure and builds, over `^IVF`.
//! - `vq_l1`, `vq_l2`: module 06, the embed queue's requests and workers, over `^EmbedQueue` and the vector rows.
//! - `cx_*` (only with their control feature): proved counterexamples, a run of the L2 step relation (as the control
//!   changes it) from its initial state to a step that is not an L1 step.
//! - `witness_*` (only without their family's controls): non-vacuity runs of the reviewed L2 machines.
pub mod snap_l1;
pub mod snap_l2;
pub mod snap_runs;
pub mod vidx_l1;
pub mod vidx_l2;
pub mod vq_l1;
pub mod vq_l2;
pub mod vq_runs;
#[cfg(feature = "control_f1801_no_prefix_check")]
pub mod cx_f1801_history;
#[cfg(feature = "control_f1801_restore_unredacts")]
pub mod cx_f1801_unredact;
#[cfg(feature = "control_fc1304_receipt_omits_archives")]
pub mod cx_fc1304;
#[cfg(feature = "control_fc1801_dirty_export")]
pub mod cx_fc1801;
#[cfg(feature = "control_fc1802_swallowed_line")]
pub mod cx_fc1802;
#[cfg(feature = "control_fc1804_edge_routes_omitted")]
pub mod cx_fc1804;
#[cfg(feature = "control_f0606_erase_keeps_ivf")]
pub mod cx_f0606;
#[cfg(feature = "control_hd0602_inplace_build")]
pub mod cx_hd0602;
#[cfg(feature = "control_hd0604_two_consumers")]
pub mod cx_hd0604;
#[cfg(feature = "control_f0604_done_without_vector")]
pub mod cx_f0604;
#[cfg(feature = "control_fc0601_no_version_check")]
pub mod cx_fc0601;
#[cfg(not(any(feature = "control_f1801_no_prefix_check", feature = "control_f1801_restore_unredacts",
              feature = "control_fc1304_receipt_omits_archives", feature = "control_fc1801_dirty_export",
              feature = "control_fc1802_swallowed_line", feature = "control_fc1804_edge_routes_omitted")))]
pub mod witness_snap;
#[cfg(not(any(feature = "control_f0606_erase_keeps_ivf", feature = "control_hd0602_inplace_build")))]
pub mod witness_vidx;
#[cfg(not(any(feature = "control_hd0604_two_consumers", feature = "control_f0604_done_without_vector",
              feature = "control_fc0601_no_version_check")))]
pub mod witness_vq;
