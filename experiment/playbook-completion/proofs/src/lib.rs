//! Completion audit, CORE-PROOFS lane (playbook §3.3): participant contracts for erase -> redact -> replay, composed in
//! two levels with `actors::protocol::Protocol2`, an outer business contract with its safety invariants, progress
//! under named fairness, and the broken-implementation controls. See PROOFS.md.
//!
//! - Participants (each a `Contract` + `SafeContract` over its own state): `ledger`, `store`, `redactor`.
//! - Level 1 (`protocol_rl`): Ledger x Redactor -> `RL`. Level 2 (`protocol_sys`): RL x Store -> `Biz`.
//! - `biz`: the outer business contract and its invariants. `compose`, `system`: any implementations of the
//!   participants refine `Biz` (`theorem_compose`, `theorem_trans`) and keep its invariants.
//! - `progress`: `FairWork` for a redaction run; `witness`: a concrete erase -> redact -> settled execution.
//! - `cx_*` (only with their control feature): proved counterexamples of the pin's coordination.
pub mod vocab;
pub mod ledger;
pub mod store;
pub mod redactor;
pub mod compose;
pub mod protocol_rl;
pub mod biz;
pub mod protocol_sys;
pub mod system;
pub mod progress;
pub mod witness;
#[cfg(feature = "control_f1302_unlocked_start")]
pub mod cx_f1302;
#[cfg(feature = "control_f1303_other_marker")]
pub mod cx_f1303;
#[cfg(feature = "control_f1201_erase_unlocked")]
pub mod cx_f1201;
#[cfg(feature = "control_f1306_replay_reapplies")]
pub mod cx_f1306;
