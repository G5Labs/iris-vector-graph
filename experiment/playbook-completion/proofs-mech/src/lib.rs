//! Completion audit, PROOFS-MECH lane (proof debt D-14, playbook 3.3a item 2): the 13 shared mechanisms of
//! semantics/MECHANISMS.md proved once over a trait each. Per mechanism NN: `mNN_<fam>` (state, operations, the
//! policy trait with the instance parameters, the laws, the obligations and the `<Fam>Object` trait whose proof
//! functions discharge them, generic lemmas and theorems), `iNN_<fam>` (one type per object variant: parameters,
//! discharges, kept and refuted obligations, non-vacuity witnesses), `cxNN_<fam>` (proved counterexamples of the
//! departing variants) and `ctl_<fam>` (located controls, one feature each). `exec` holds the run semantics shared
//! by every machine. Every result is about the semantics lane's mechanism models; see PROOFS.md.
pub mod exec;
pub mod m01_ledger;
pub mod i01_ledger;
pub mod cx01_ledger;
pub mod ctl_ledger;
pub mod m02_retry;
pub mod i02_retry;
pub mod cx02_retry;
pub mod ctl_retry;
pub mod m03_excl;
pub mod i03_excl;
pub mod cx03_excl;
pub mod ctl_excl;
pub mod m04_derived;
pub mod i04_derived;
pub mod cx04_derived;
pub mod ctl_derived;
pub mod m05_removal;
pub mod i05_removal;
pub mod cx05_removal;
pub mod ctl_removal;
pub mod m06_snapshot;
pub mod i06_snapshot;
pub mod cx06_snapshot;
pub mod ctl_snapshot;
pub mod m07_queue;
pub mod i07_queue;
pub mod cx07_queue;
pub mod ctl_queue;
pub mod m08_install;
pub mod i08_install;
pub mod cx08_install;
pub mod ctl_install;
pub mod m09_scope;
pub mod i09_scope;
pub mod cx09_scope;
pub mod ctl_scope;
pub mod m10_unit;
pub mod i10_unit;
pub mod cx10_unit;
pub mod ctl_unit;
pub mod m11_cap;
pub mod i11_cap;
pub mod cx11_cap;
pub mod ctl_cap;
pub mod m12_catalog;
pub mod i12_catalog;
pub mod cx12_catalog;
pub mod ctl_catalog;
pub mod m13_epoch;
pub mod i13_epoch;
pub mod cx13_epoch;
pub mod ctl_epoch;
