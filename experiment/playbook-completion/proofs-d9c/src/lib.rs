//! Completion audit, PROOFS-D9C lane (review-4 R4-01, R4-03): a copy of `proofs-d9b` with guard G-BM (bypass writers
//! honour the marker), the no-tombstone theorem for content of any provenance, and F-1306 re-encoded as the pin's
//! direct-SQL write. PROOFS-D9B (proof debts D-9, D-12) was itself a copy of `proofs-d9` (the erase -> redact -> replay
//! participant contracts under the pin's real premises — three target predicates, ledger-bypassing writers, erasure
//! rollback with dirty reads — composed in three `Protocol2` levels) extended with revision metadata and zero-record
//! revisions (F-CS01), the retry key's move to idemRedacted, the statement history, record readers racing a redaction
//! (`reader`, `protocol_rd`; F-1402), a progress-only control for the fixed scan bound (D-12), and the F-1302, F-1303,
//! F-1306 controls re-run here. Every result is about the models. See PROOFS.md.
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
pub mod witness_meta;
pub mod reader;
pub mod protocol_rd;
pub mod witness_rd;
#[cfg(any(feature = "control_f1402_reader_no_recheck", feature = "control_reader_marker_recheck_only"))]
pub mod cx_reader;
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
#[cfg(feature = "control_fcs01_noop_unrecorded")]
pub mod cx_fcs01;
#[cfg(feature = "control_f1302_unlocked_start")]
pub mod cx_f1302;
#[cfg(feature = "control_f1303_other_marker")]
pub mod cx_f1303;
#[cfg(feature = "control_f1306_replay_direct_sql")]
pub mod cx_f1306;
#[cfg(feature = "control_f1350_bypass_ignores_marker")]
pub mod cx_f1350;
#[cfg(feature = "control_sc_narrow")]
pub mod cx_sc_narrow;
