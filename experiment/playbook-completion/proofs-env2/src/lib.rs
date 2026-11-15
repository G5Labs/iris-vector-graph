//! Lane proofs-env (proof debt D-7): the IRIS environment contract as a Verus specification linked to the audit's
//! proof crates' participant contracts. See PROOFS.md.
//!
//! - `spec`: the contract's clauses the proof crates rely on, as a step function with its permitted-outcome structure
//!   (`outcomes`: two outcomes exactly at the contract's Freedom), and a case's runs (`run`, `permitted`);
//! - `wf`: every operation keeps the state well formed;
//! - `exec`: the executable model (`e_step`, `e_run`), verified equal to `spec` (the differential harness runs it);
//! - `effects`: the footprint of every operation (frame, cells written or rolled back, log growth, lock acquisition only
//!   without conflict);
//! - `headlock`: a transaction under an exclusive lock is one atomic step on the cells the lock protects (inductive
//!   invariant over every operation of every process; holder theorem; readers under the lock);
//! - `clauses`: the validated contract (`contract_sem`), what the premises are stated over (`validated`), the controls;
//! - `gen`: generic consequences of the clauses, each with its clause as a precondition;
//! - `premises`: the proof crates' premises (crate and premise id), each proved, shown false or shown not implied;
//! - `cx`: one counterexample per control (the clause is necessary).
pub mod spec;
pub mod ext;
pub mod wf;
pub mod exec;
pub mod ext_exec;
pub mod effects;
pub mod ext_lemmas;
pub mod headlock;
pub mod clauses;
pub mod gen;
pub mod premises;
pub mod cx;
