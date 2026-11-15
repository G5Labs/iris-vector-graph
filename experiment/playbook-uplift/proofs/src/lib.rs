//! IVG erasure -> ledger redaction -> replay: the playbook §3.3 models and proofs.
//!
//! - `model`: records, replay, tombstoning and the replay theorems (spec 256 US2, FR-007).
//! - `l1`: the abstract business machine (one step per user-visible command) and its invariants.
//! - `l2`: the algorithmic machine over the stored layout (batched redaction with a marker, cursor and counters, the
//!   commit-time checks, process stops), its refinement of `l1`, and the broken-implementation controls.
//! - `progress`: a bound on the work a redaction run does.
pub mod model;
pub mod l1;
pub mod l2;
pub mod progress;
