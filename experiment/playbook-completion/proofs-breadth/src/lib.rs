//! Completion audit, BREADTH-PROOFS lane (proof debt D-1, playbook §3.3). See PROOFS.md.
//!
//! - `ledger_l1`, `ledger_l2`: module 11 (ledger commit with retry keys and expected head, enable / disable / strict,
//!   the strict-mode guard, the stats row) as an L1 business contract and an L2 machine over `^IVG.Ledger`, with
//!   `Refines<L1>` for every L2 step and both levels' `SafeContract` invariants.
//! - `adj_l1`, `adj_l2`: module 04 (adjacency writer lock, generation-validated degree cache, erase, rebuild) likewise
//!   over `^KG("out"/"gen"/"degc")`, `^IVG.AdjW` and `^IVG.AdjNoLock`.
//! - `cx_*` (only with their control feature): proved counterexamples, a run of the L2 step relation (as the control
//!   changes it) from its initial state to a step that is not an L1 step.
pub mod ledger_l1;
pub mod ledger_l2;
pub mod adj_l1;
pub mod adj_l2;
#[cfg(any(feature = "control_f0801_ttl_cache", feature = "control_f0801_fail_open",
          feature = "control_f1108_unguarded_bulk_delete", feature = "control_fc1101_stats_whole_row"))]
pub mod cx_ledger_common;
#[cfg(feature = "control_f0801_ttl_cache")]
pub mod cx_f0801_ttl;
#[cfg(feature = "control_f0801_fail_open")]
pub mod cx_f0801_failopen;
#[cfg(feature = "control_f1108_unguarded_bulk_delete")]
pub mod cx_f1108;
#[cfg(feature = "control_fc1101_stats_whole_row")]
pub mod cx_fc1101;
#[cfg(any(feature = "control_fc0401_write_before_gen", feature = "control_hd0401_erase_kills_gen",
          feature = "control_hd0401_rebuild_kills_gen"))]
pub mod cx_adj_common;
#[cfg(feature = "control_fc0401_write_before_gen")]
pub mod cx_fc0401;
#[cfg(feature = "control_hd0401_erase_kills_gen")]
pub mod cx_hd0401_erase;
#[cfg(feature = "control_hd0401_rebuild_kills_gen")]
pub mod cx_hd0401_rebuild;
#[cfg(not(any(feature = "control_f0801_ttl_cache", feature = "control_f0801_fail_open",
              feature = "control_f1108_unguarded_bulk_delete", feature = "control_fc1101_stats_whole_row")))]
pub mod witness_ledger;
#[cfg(not(any(feature = "control_fc0401_write_before_gen", feature = "control_hd0401_erase_kills_gen",
              feature = "control_hd0401_rebuild_kills_gen")))]
pub mod witness_adj;
