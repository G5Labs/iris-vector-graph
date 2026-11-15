//! Lane proofs-stmt (steer 14; proof debt D-2, gate 3.4-statements; D-3, gate 3.5-handlers; D-4, the head-lock plan):
//! the pin's Graph.KG.Eraser.EraseGraph statement program, hand-translated into the operation language of the IRIS
//! 2026.1 contract's Verus specification (crate ivg-proofs-env2, unchanged), and proved in that model to perform the
//! core Store contract's steps (crate ivg-core-proofs, unchanged) under an abstraction. See PROOFS.md.
//!
//! - `lay`: the layout of IVG's storage in a contract universe; `alpha` to `StoreS`; the statement-index invariant;
//! - `prog`: the statement language, its runs, the EraseGraph program (as built, reviewed, mutants);
//! - `oplem`: one contract operation's effect; `runs`: composition of runs and traces;
//! - `stmts`: the statement lemmas (3.4); `eg`: the handler theorems (3.5) and the discipline theorem (D-4);
//! - `cx`: counterexamples of the controls (always compiled); `exec`: exec counterparts verified equal to `prog`.
pub mod lay;
pub mod prog;
pub mod oplem;
pub mod runs;
pub mod stmts;
pub mod eg;
pub mod cx;
