//! M-10 Unit of work: all or none, inert refusal (axioms AX-04, AX-03, AX-12). Generic machine over `UnitObject`.
//!
//! Abstract state: whether the caller has a transaction open with an earlier write W of its own; the unit's two
//! writes A and B (kept or not); the unit's program counter and its reply. The unit begins (a nested level when the
//! caller's transaction is open: Ledger.Commit, Ledger.cls:390-415; `_write_txn`), writes A, then writes B or fails.
//! Commit modes: `Txn` (one level), `PerStatement` (each write commits on its own: Bolt RUN, HTTP tx-commit,
//! bulk chunks), `NoTxn` (A is written before or outside the transaction: route creation, FHIR register's upsert).
//! Refusal handling: `OwnLevel` (TROLLBACK 1), `AllLevels` (the caller's transaction too: F-C0702, F-0409),
//! `NoRollback`. Replies: `Code`, `WrongClass` (a refusal outside the product's error family), `OkOnFailure`.
//!
//! Laws: M10-L1 (invariant) a finished unit kept both writes or neither; M10-L2 (invariant) a refused unit left the
//! caller's earlier write; M10-L3 (invariant) a refused unit replied refused with a code of its family, and an ok
//! reply means both writes are kept.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Commit { Txn, PerStatement, NoTxn }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Undo { OwnLevel, AllLevels, NoRollback }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Reply { Code, WrongClass, OkOnFailure }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Cfg { pub commit: Commit, pub undo: Undo, pub reply: Reply }

pub const CANON: Cfg = Cfg { commit: Commit::Txn, undo: Undo::OwnLevel, reply: Reply::Code };

pub trait UnitObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn as_built(&self) -> Cfg;
    fn departs(&self) -> (&'static str, &'static [&'static str]);
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum R { Pending, Ok, Refused(bool) }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S { pub caller_open: bool, pub w: bool, pub a: bool, pub a_committed: bool, pub b: bool, pub pc: u8, pub reply: R }

#[derive(Clone, Copy, Debug)]
pub enum A { Begin, WriteA, WriteB, Fail, End }

pub struct Machine<'a, O: UnitObject> { pub o: &'a O, pub c: Cfg }

pub const L1: &str = "M10-L1 all or none";
pub const L2: &str = "M10-L2 a refusal leaves the caller's writes";
pub const L3: &str = "M10-L3 the reply matches the outcome";

impl<'a, O: UnitObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        [false, true].iter().map(|&o| S { caller_open: o, w: o, a: false, a_committed: false, b: false, pc: 0, reply: R::Pending }).collect()
    }
    fn actions(&self, _: &S) -> Vec<A> { vec![A::Begin, A::WriteA, A::WriteB, A::Fail, A::End] }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let c = self.c;
        let mut u = s.clone();
        match (*a, s.pc) {
            (A::Begin, 0) => { u.pc = 1; }
            (A::WriteA, 1) => { u.a = true; u.a_committed = matches!(c.commit, Commit::PerStatement | Commit::NoTxn); u.pc = 2; }
            (A::WriteB, 2) => { u.b = true; u.pc = 3; }
            (A::End, 3) => { u.pc = 4; u.reply = R::Ok; }
            (A::Fail, 2) => {
                match c.undo {
                    Undo::OwnLevel => { if !s.a_committed { u.a = false; } }
                    Undo::AllLevels => { if !s.a_committed { u.a = false; } u.w = false; }
                    Undo::NoRollback => {}
                }
                u.reply = match c.reply { Reply::Code => R::Refused(true), Reply::WrongClass => R::Refused(false), Reply::OkOnFailure => R::Ok };
                u.pc = 4;
            }
            _ => return None,
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(L1, |s: &S| s.pc != 4 || s.a == s.b),
            invariant(L2, |s: &S| s.pc != 4 || s.b || s.w == s.caller_open),
            invariant(L3, |s: &S| s.pc != 4 || match s.reply { R::Refused(code) => code && !s.b, R::Ok => s.a && s.b, R::Pending => false }),
        ]
    }
}

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], $ab:expr, $law:expr, [$($f:expr),*]) => {
        pub struct $t;
        impl UnitObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn as_built(&self) -> Cfg { $ab }
            fn departs(&self) -> (&'static str, &'static [&'static str]) { ($law, &[$($f),*]) }
        }
    };
}

object!(PerChunkCommit, "per-chunk-commit", ["03/caller-transaction"], Cfg { commit: Commit::PerStatement, ..CANON }, L1, ["F-0305"]);
object!(RollbackAllLevels, "rollback-all-levels", ["07/bm25-index", "04/adjacency-entry"], Cfg { undo: Undo::AllLevels, ..CANON }, L2, ["F-C0702", "F-0704", "F-0409"]);
object!(PerStatementCommit, "per-statement-commit", ["16/bolt-session-with-a-key-set", "16/cypher-http-call", "15/reifier"], Cfg { commit: Commit::PerStatement, ..CANON }, L1, ["F-1601", "F-1610", "F-1609", "F-C1502"]);
object!(NoTransaction, "no-transaction", ["15/fhir-graph", "06/route", "05/temporal-coordinates"], Cfg { commit: Commit::NoTxn, ..CANON }, L1, ["F-1511", "F-C1501", "F-0615", "F-C0501"]);
object!(WrongReply, "wrong-reply", ["08/cypher-call"], Cfg { reply: Reply::WrongClass, ..CANON }, L3, ["F-0807", "F-0804", "F-0817"]);
object!(HiddenFailure, "hidden-failure", ["03/node-in-one-graph", "07/fused-search"], Cfg { reply: Reply::OkOnFailure, ..CANON }, L3, ["F-0306", "F-0307", "F-0709"]);
object!(Canonical, "canonical", ["11/caller-transaction", "17/link"], CANON, "", []);

fn instance_checks<O: UnitObject>(o: &O) -> Vec<Outcome> {
    let (law, f) = o.departs();
    let n = o.name();
    let ab = Machine { o, c: o.as_built() };
    let rv = Machine { o, c: CANON };
    let mut out = vec![];
    if law.is_empty() {
        out.push(check(&format!("unit-{n}-as-built"), meta("M-10", "unit", n, o.objects(), "as-built", "safety", "all", f, ""), Expect::Pass, &Keep::safety(&ab)));
    } else {
        out.push(check(&format!("unit-{n}-as-built"), meta("M-10", "unit", n, o.objects(), "as-built", "safety", law, f, ""), Expect::Violation(law), &Keep::only(&ab, &[law])));
        out.push(check(&format!("unit-{n}-reviewed"), meta("M-10", "unit", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)));
    }
    out
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&PerChunkCommit));
    out.extend(instance_checks(&RollbackAllLevels));
    out.extend(instance_checks(&PerStatementCommit));
    out.extend(instance_checks(&NoTransaction));
    out.extend(instance_checks(&WrongReply));
    out.extend(instance_checks(&HiddenFailure));
    out.extend(instance_checks(&Canonical));
    let o = &Canonical;
    let ctl = |id: &str, law: &'static str, c: Cfg| {
        let m = Machine { o, c };
        check(id, meta("M-10", "unit", "canonical", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    out.push(ctl("unit-control-C1-per-statement", L1, Cfg { commit: Commit::PerStatement, ..CANON }));
    out.push(ctl("unit-control-C2-rollback-all-levels", L2, Cfg { undo: Undo::AllLevels, ..CANON }));
    out.push(ctl("unit-control-C3-ok-on-failure", L3, Cfg { reply: Reply::OkOnFailure, ..CANON }));
    let rv = Machine { o, c: CANON };
    let sm = || meta("M-10", "unit", "canonical", Canonical.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("unit-sharp-refused-inside-caller", sm(), &rv, "never: a refusal inside a caller transaction keeps the caller's write",
                   |s: &S| s.pc == 4 && s.caller_open && s.w && s.reply == R::Refused(true)));
    out.push(reach("unit-sharp-ok", sm(), &rv, "never: an ok unit with both writes", |s: &S| s.pc == 4 && s.a && s.b && s.reply == R::Ok));
    out
}
