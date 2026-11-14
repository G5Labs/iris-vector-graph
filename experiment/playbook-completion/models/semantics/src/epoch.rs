//! M-13 Read epoch: consistent multi-step read (axiom AX-12). Generic machine over `EpochObject`.
//!
//! Abstract state: a multi-step change of two parts (a redaction over two batches, or a writer's transaction over two
//! tables) that sets a marker and moves an epoch when it starts, changes part 1 then part 2, then clears the marker
//! and moves the epoch again; and a reader that reads part 1 and part 2 in two steps (record readers page by page,
//! save_snapshot table by table). Readers: `NoCheck` (save_snapshot reads uncommitted rows with no barrier,
//! snapshot.py:864-1034, F-C1801), `CheckStart` (record readers check the redaction marker before reading only,
//! F-1402), `CheckStartEnd` (the working answer of HD-1401: an epoch compared before and after; a change seen means
//! the read reports itself interrupted).
//!
//! Law M13-L1 (invariant): a finished, uninterrupted read returns both parts from one state.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Reader { NoCheck, CheckStart, CheckStartEnd }

pub trait EpochObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn as_built(&self) -> Reader;
    fn departs(&self) -> (&'static str, &'static [&'static str]);
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Rd { Idle, Begun(u8), Read1(u8, u8), Read2(u8, u8, u8), Done { consistent: bool, interrupted: bool } }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S { pub wpc: u8, pub marker: bool, pub epoch: u8, pub parts: [u8; 2], pub r: Rd }

#[derive(Clone, Copy, Debug)]
pub enum A { Start, Change1, Change2, Finish, RBegin, RRead1, RRead2, REnd }

pub struct Machine<'a, O: EpochObject> { pub o: &'a O, pub reader: Reader }

pub const L1: &str = "M13-L1 a finished read shows one state";

impl<'a, O: EpochObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { vec![S { wpc: 0, marker: false, epoch: 0, parts: [0, 0], r: Rd::Idle }] }
    fn actions(&self, _: &S) -> Vec<A> { vec![A::Start, A::Change1, A::Change2, A::Finish, A::RBegin, A::RRead1, A::RRead2, A::REnd] }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        match (*a, s.wpc, s.r) {
            (A::Start, 0, _) => { u.wpc = 1; u.marker = true; u.epoch += 1; }
            (A::Change1, 1, _) => { u.wpc = 2; u.parts[0] = 1; }
            (A::Change2, 2, _) => { u.wpc = 3; u.parts[1] = 1; }
            (A::Finish, 3, _) => { u.wpc = 4; u.marker = false; u.epoch += 1; }
            (A::RBegin, _, Rd::Idle) => {
                if self.reader != Reader::NoCheck && s.marker { u.r = Rd::Done { consistent: true, interrupted: true }; } else { u.r = Rd::Begun(s.epoch); }
            }
            (A::RRead1, _, Rd::Begun(e)) => { u.r = Rd::Read1(e, s.parts[0]); }
            (A::RRead2, _, Rd::Read1(e, v1)) => { u.r = Rd::Read2(e, v1, s.parts[1]); }
            (A::REnd, _, Rd::Read2(e, v1, v2)) => {
                let interrupted = self.reader == Reader::CheckStartEnd && (s.epoch != e || s.marker);
                u.r = Rd::Done { consistent: v1 == v2, interrupted };
            }
            _ => return None,
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(L1, |s: &S| !matches!(s.r, Rd::Done { consistent: false, interrupted: false }))]
    }
}

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], $ab:expr, $law:expr, [$($f:expr),*]) => {
        pub struct $t;
        impl EpochObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn as_built(&self) -> Reader { $ab }
            fn departs(&self) -> (&'static str, &'static [&'static str]) { ($law, &[$($f),*]) }
        }
    };
}

object!(CheckAtStart, "check-at-start", ["14/ledger-view"], Reader::CheckStart, L1, ["F-1402"]);
object!(NoCheckReader, "no-check", ["18/snapshot-archive"], Reader::NoCheck, L1, ["F-C1801"]);

fn instance_checks<O: EpochObject>(o: &O) -> Vec<Outcome> {
    let (law, f) = o.departs();
    let n = o.name();
    vec![
        check(&format!("epoch-{n}-as-built"), meta("M-13", "epoch", n, o.objects(), "as-built", "safety", law, f, ""), Expect::Violation(law),
              &Keep::only(&Machine { o, reader: o.as_built() }, &[law])),
        check(&format!("epoch-{n}-reviewed"), meta("M-13", "epoch", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass,
              &Keep::safety(&Machine { o, reader: Reader::CheckStartEnd })),
    ]
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&CheckAtStart));
    out.extend(instance_checks(&NoCheckReader));
    let o = &CheckAtStart;
    out.push(check("epoch-control-C1-no-end-check", meta("M-13", "epoch", "check-at-start", o.objects(), "control", "safety", L1, &[], ""), Expect::Violation(L1),
                   &Keep::only(&Machine { o, reader: Reader::CheckStart }, &[L1])));
    let rv = Machine { o, reader: Reader::CheckStartEnd };
    let sm = || meta("M-13", "epoch", "check-at-start", CheckAtStart.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("epoch-sharp-interrupted", sm(), &rv, "never: a read reports itself interrupted", |s: &S| matches!(s.r, Rd::Done { interrupted: true, .. })));
    out.push(reach("epoch-sharp-new-state-read", sm(), &rv, "never: a consistent read of the changed state",
                   |s: &S| matches!(s.r, Rd::Done { consistent: true, interrupted: false }) && s.parts == [1, 1]));
    out
}
