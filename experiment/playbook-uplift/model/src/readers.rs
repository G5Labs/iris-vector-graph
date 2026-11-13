//! Machine 4: a record reader (verify(), reconstruct(), diff(), export_reconstruction()) racing a redaction.
//!
//! Tenant A is erased; its ledger records a1, a2 are still content; b1 belongs to tenant B. A redaction of A runs in
//! the reviewed design (Start sets the marker, Scan tombstones one record per step, Final clears the marker), and
//! may run more than once (a second Start after a Final is a no-op run). The reader takes no lock:
//! - `as-built` (iris_vector_graph/ledger/client.py:687-693, replay.py:806-823): R1 reads the marker and gives up
//!   if it exists; R2 reads the records. Nothing ties R2 to what R1 saw.
//! - `reviewed`: R1 also reads a redaction epoch (one more per Start); after R2, R3 re-reads marker and epoch and
//!   accepts the view only if both are unchanged.
//!
//! Property: an accepted view never shows a redaction half done (some but not all of A's records tombstoned).
//! Spec 256 Decision 3 / ADR-0013: "Record readers raise RedactionInProgressError" exists to prevent exactly that.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Rd { Idle, Checked { epoch: u8 }, Read { epoch: u8, tombs: u8 }, Accepted { tombs: u8 }, Refused }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S4 {
    pub tombs: u8,
    pub marker: bool,
    pub epoch: u8,
    pub reader: Rd,
}

#[derive(Clone, Debug)]
pub enum A4 { Start, Scan, Final, R1, R2, R3 }

pub struct M4 { pub design: Design }

const A_RECORDS: u8 = 2;

impl Model for M4 {
    type State = S4;
    type Action = A4;
    fn init_states(&self) -> Vec<S4> { vec![S4 { tombs: 0, marker: false, epoch: 0, reader: Rd::Idle }] }
    fn actions(&self, _: &S4) -> Vec<A4> { vec![A4::Start, A4::Scan, A4::Final, A4::R1, A4::R2, A4::R3] }
    fn next(&self, s: &S4, a: &A4) -> Option<S4> {
        let mut u = s.clone();
        match a {
            A4::Start => { if s.marker || s.epoch >= 2 { return None; } u.marker = true; u.epoch += 1; }
            A4::Scan => { if !s.marker || s.tombs >= A_RECORDS { return None; } u.tombs += 1; }
            A4::Final => { if !s.marker || s.tombs < A_RECORDS { return None; } u.marker = false; }
            A4::R1 => {
                if s.reader != Rd::Idle { return None; }
                u.reader = if s.marker { Rd::Refused } else { Rd::Checked { epoch: s.epoch } };
            }
            A4::R2 => {
                let Rd::Checked { epoch } = s.reader else { return None };
                u.reader = match self.design {
                    Design::AsBuilt => Rd::Accepted { tombs: s.tombs },
                    Design::Reviewed => Rd::Read { epoch, tombs: s.tombs },
                };
            }
            A4::R3 => {
                let Rd::Read { epoch, tombs } = s.reader else { return None };
                u.reader = if s.marker || s.epoch != epoch { Rd::Refused } else { Rd::Accepted { tombs } };
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S4>> {
        vec![invariant("an accepted view never shows a redaction half done", |s: &S4| match s.reader {
            Rd::Accepted { tombs } => tombs == 0 || tombs == A_RECORDS,
            _ => true,
        })]
    }
    fn always_possibly(&self) -> Vec<Invariant<S4>> {
        vec![invariant("the reader can finish", |s: &S4| matches!(s.reader, Rd::Accepted { .. } | Rd::Refused))]
    }
}

pub fn show(c: &Counterexample<S4, A4>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<6} marker={} tombstones of A={}/{} reader={:?}\n", i + 1, format!("{:?}", a),
                        s.marker, s.tombs, A_RECORDS, s.reader);
    }
    out
}
