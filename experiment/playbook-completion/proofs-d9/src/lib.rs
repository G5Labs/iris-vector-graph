//! Completion audit, PROOFS-D9 lane (proof debt D-9): the erase -> redact -> replay participant contracts of
//! `proofs/` generalised to the pin's real premises — three target predicates, ledger-bypassing writers, erasure
//! rollback with dirty reads — composed in three `Protocol2` levels, with safety under named premises, progress under
//! productive fairness, and a control for each new guard. Every result is about the models. See PROOFS.md.
//!
//! - Participants (each a `Contract` + `SafeContract` over its own state): `ledger`, `redactor`, `store`, `writer`.
//! - Level 1 (`protocol_rl`): Ledger x Redactor -> `RL`. Level 2 (`protocol_sys`): RL x Store -> `Mid` (`mid`).
//!   Level 3 (`protocol_top`): Mid x Writer -> `Biz` (`biz`).
//! - `safety`: Biz's invariants are inductive; `theorems`: the business theorems; `system`: any implementations of the
//!   participants refine Biz and keep its invariants; `progress`: one run under productive fairness; `witness`:
//!   concrete executions; `cx_*`: proved counterexamples of each control (only with its feature).
pub mod vocab;
pub mod ledger;
pub mod store;
pub mod redactor;
pub mod writer;
pub mod compose;
pub mod protocol_rl;
pub mod mid;
pub mod protocol_sys;
pub mod biz;
pub mod safety;
pub mod theorems;
pub mod protocol_top;
pub mod system;
pub mod progress;
pub mod witness;
#[cfg(feature = "control_bypass_start")]
pub mod cx_bypass_start;
#[cfg(feature = "control_bypass_erase")]
pub mod cx_bypass_erase;
#[cfg(feature = "control_liveness_dirty")]
pub mod cx_liveness_dirty;
#[cfg(feature = "control_unaligned_rm")]
pub mod cx_unaligned_rm;
#[cfg(feature = "control_unaligned_sc")]
pub mod cx_unaligned_sc;
#[cfg(feature = "control_f1201_erase_unlocked")]
pub mod cx_f1201;
