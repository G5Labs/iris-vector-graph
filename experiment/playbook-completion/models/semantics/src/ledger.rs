//! M-01 Ledger commit with record (axioms AX-05, AX-07, AX-04). Generic machine over `LedgerObject`.
//!
//! Abstract state of one governed item (the content one object holds in the store) and the ledger's records for it:
//! `content` (0 = absent, 1..2 a value), `records` (each the value it sets, 0 = a delete), `head`, `strict`, an
//! engine's cached copy of the strict flag (`cache`, refreshed by `Refresh`, the 5 s TTL of
//! iris_vector_graph/ledger/guard.py:20-59), and `unrecorded` (a write outside the ledger was allowed while not
//! strict: verify classifies such writes; it is not a defect of L2). `replay(records)` is the last record's value.
//!
//! Write paths (an object declares which it has; the canonical commit is Ledger.Commit, one TSTART..TCOMMIT under the
//! head lock that applies the ops and writes records, revision row and head together, iris_src/src/Graph/KG/Ledger.cls:397-528):
//! - `Commit`: atomic; refuses a stale expected head (`CommitStale`, Ledger.cls:478-488) with no change;
//! - `InsertIfAbsent{record_on_collision}`: a temporal insert-mode op; as built it is recorded even when it
//!   collides and changed nothing (F-0511);
//! - `DeleteAbsent{record_anyway}`: a graph-blind delete of an id the scoped store does not hold; as built the
//!   record is written although nothing was removed (F-1105);
//! - `Bypass(guard)`: a write outside the ledger: `Server` refuses while strict, `CachedClient` checks the engine's
//!   cached flag (F-0302, F-0801), `NoGuard` checks nothing (F-0301, F-0504, F-1108, F-0503).
//! Control mutants (never at the pin): `CommitTwoStep` (record in a second step, a stop between), `CommitOverwrite`
//! (an update rewrites the last record), `CommitIgnoreHead` (applies a stale expected head).
//!
//! Laws: M01-L1 (action) records are a prefix-preserving append and the head never falls; M01-L2 (invariant) no
//! commit in flight => content = replay(records) or an allowed unrecorded write is flagged; M01-L3 (action) a stale
//! expected head changes nothing; M01-L4 (action) while strict, no bypass changes the content.
//! Bounds: at most 2 records, 3 write attempts.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Guard { Server, CachedClient, NoGuard }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Path {
    Commit,
    InsertIfAbsent { record_on_collision: bool },
    DeleteAbsent { record_anyway: bool },
    Bypass(Guard),
    CommitTwoStep,
    CommitOverwrite,
    CommitIgnoreHead,
}

pub trait LedgerObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn as_built(&self) -> Vec<Path>;
    fn reviewed(&self) -> Vec<Path>;
    /// the law the as-built paths depart from ("" when the as-built keeps every law) and its findings
    fn departs(&self) -> (&'static str, &'static [&'static str]);
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub content: u8,
    pub records: Vec<u8>,
    pub head: u8,
    pub strict: bool,
    pub cache: bool,
    pub unrecorded: bool,
    pub mid: Option<u8>,
    pub attempts: u8,
    pub refusals: u8,
}

#[derive(Clone, Debug)]
pub enum A { Write(usize, u8), CommitStale(usize, u8), Finish, Stop, SetStrict(bool), Refresh }

pub struct Machine<'a, O: LedgerObject> { pub o: &'a O, pub paths: Vec<Path> }

pub const L1: &str = "M01-L1 history only grows";
pub const L2: &str = "M01-L2 content equals replay of records";
pub const L3: &str = "M01-L3 stale expected head changes nothing";
pub const L4: &str = "M01-L4 strict: no unrecorded change";

fn replay(r: &[u8]) -> u8 { r.last().copied().unwrap_or(0) }

impl<'a, O: LedgerObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { content: 0, records: vec![], head: 0, strict: false, cache: false, unrecorded: false, mid: None, attempts: 0, refusals: 0 }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![A::Finish, A::Stop, A::SetStrict(true), A::SetStrict(false), A::Refresh];
        for i in 0..self.paths.len() {
            for x in 0..=2u8 { v.push(A::Write(i, x)); }
            v.push(A::CommitStale(i, 1));
        }
        v
    }
    fn within_bounds(&self, s: &S) -> bool { s.attempts < 3 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let full = s.records.len() >= 2;
        match *a {
            A::SetStrict(b) => { if s.strict == b || s.mid.is_some() { return None; } u.strict = b; }
            A::Refresh => { if s.cache == s.strict { return None; } u.cache = s.strict; }
            A::Finish => { let v = s.mid?; u.records.push(v); u.head += 1; u.mid = None; }
            A::Stop => { s.mid?; u.mid = None; } // the second step never runs; the content step already committed
            A::CommitStale(i, v) => {
                if s.mid.is_some() || full || s.head == 0 { return None; }
                u.attempts += 1;
                match self.paths[i] {
                    Path::CommitIgnoreHead => { u.content = v; u.records.push(v); u.head += 1; }
                    Path::Commit | Path::CommitTwoStep | Path::CommitOverwrite => { u.refusals += 1; }
                    _ => return None,
                }
            }
            A::Write(i, v) => {
                if s.mid.is_some() || full { return None; }
                u.attempts += 1;
                match self.paths[i] {
                    Path::Commit | Path::CommitIgnoreHead => {
                        if v == 0 && s.content == 0 { return None; }
                        u.content = v; u.records.push(v); u.head += 1;
                    }
                    Path::CommitTwoStep => { if v == 0 && s.content == 0 { return None; } u.content = v; u.mid = Some(v); }
                    Path::CommitOverwrite => {
                        if v == 0 { return None; }
                        u.content = v;
                        if s.records.is_empty() { u.records.push(v); u.head += 1; } else { *u.records.last_mut().unwrap() = v; }
                    }
                    Path::InsertIfAbsent { record_on_collision } => {
                        if v == 0 { return None; }
                        if s.content == 0 { u.content = v; u.records.push(v); u.head += 1; }
                        else if record_on_collision { u.records.push(v); u.head += 1; }
                        else { u.refusals += 0; } // a counted collision, no record (the reviewed contract)
                    }
                    Path::DeleteAbsent { record_anyway } => {
                        // a delete aimed at another scope: the store's item stays; graph-blind record of a delete
                        if v != 0 || s.content == 0 { return None; }
                        if record_anyway { u.records.push(0); u.head += 1; }
                    }
                    Path::Bypass(g) => {
                        if v == 0 && s.content == 0 { return None; }
                        let refuse = match g { Guard::Server => s.strict, Guard::CachedClient => s.cache, Guard::NoGuard => false };
                        if refuse { u.refusals += 1; } else { u.content = v; u.unrecorded = true; }
                    }
                }
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(L2, |s: &S| s.mid.is_some() || s.unrecorded || s.content == replay(&s.records))]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        let paths = self.paths.clone();
        vec![
            action_property(L1, |o: &S, _: &A, n: &S| n.records.len() >= o.records.len() && n.records[..o.records.len()] == o.records[..] && n.head >= o.head),
            action_property(L3, |o: &S, a: &A, n: &S| !matches!(a, A::CommitStale(..)) || (n.content == o.content && n.records == o.records)),
            action_property(L4, move |o: &S, a: &A, n: &S| {
                // a bypass step while strict must not change the content
                match a { A::Write(i, _) if matches!(paths[*i], Path::Bypass(_)) => !(o.strict && n.content != o.content), _ => true }
            }),
        ]
    }
}

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], [$($ab:expr),*], [$($rv:expr),*], $law:expr, [$($f:expr),*]) => {
        pub struct $t;
        impl LedgerObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn as_built(&self) -> Vec<Path> { vec![$($ab),*] }
            fn reviewed(&self) -> Vec<Path> { vec![$($rv),*] }
            fn departs(&self) -> (&'static str, &'static [&'static str]) { ($law, &[$($f),*]) }
        }
    };
}

object!(CommitCore, "commit-core", ["11/ledger", "11/edge-statement", "14/ledger-view"],
        [Path::Commit], [Path::Commit], "", []);
object!(NodeDeleteNamedOnly, "node-delete-named-only", ["11/node-id"],
        [Path::Commit, Path::DeleteAbsent { record_anyway: true }], [Path::Commit, Path::DeleteAbsent { record_anyway: false }],
        L2, ["F-1105"]);
object!(TemporalInsertCollision, "temporal-insert-collision", ["05/temporal-coordinates"],
        [Path::Commit, Path::InsertIfAbsent { record_on_collision: true }], [Path::Commit, Path::InsertIfAbsent { record_on_collision: false }],
        L2, ["F-0511"]);
object!(StrictCachedGuard, "strict-cached-guard", ["03/ledger-state", "08/cypher-node", "08/cypher-edge", "08/cypher-call"],
        [Path::Commit, Path::Bypass(Guard::CachedClient)], [Path::Commit, Path::Bypass(Guard::Server)],
        L4, ["F-0302", "F-0801"]);
object!(BypassUnchecked, "bypass-unchecked", ["03/node-in-one-graph", "03/edge-in-one-graph"],
        [Path::Commit, Path::Bypass(Guard::NoGuard)], [Path::Commit, Path::Bypass(Guard::Server)],
        L4, ["F-0301", "F-0504", "F-1108", "F-0503"]);

fn instance_checks<O: LedgerObject>(o: &O) -> Vec<Outcome> {
    let (law, f) = o.departs();
    let ab = Machine { o, paths: o.as_built() };
    let rv = Machine { o, paths: o.reviewed() };
    let n = o.name();
    let mut out = vec![];
    if law.is_empty() {
        out.push(check_keep(&format!("ledger-{n}-as-built"), meta("M-01", "ledger", n, o.objects(), "as-built", "safety", "all", f, ""), Expect::Pass, &Keep::safety(&ab)));
    } else {
        out.push(check_keep(&format!("ledger-{n}-as-built"), meta("M-01", "ledger", n, o.objects(), "as-built", "safety", law, f, ""), Expect::Violation(law), &Keep::only(&ab, &[law])));
    }
    out.push(check_keep(&format!("ledger-{n}-reviewed"), meta("M-01", "ledger", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)));
    out
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&CommitCore));
    out.extend(instance_checks(&NodeDeleteNamedOnly));
    out.extend(instance_checks(&TemporalInsertCollision));
    out.extend(instance_checks(&StrictCachedGuard));
    out.extend(instance_checks(&BypassUnchecked));
    // generic controls: mutants of the canonical instance, one per law
    let o = &CommitCore;
    let ctl = |id: &str, law: &'static str, paths: Vec<Path>| {
        let m = Machine { o, paths };
        check_keep(id, meta("M-01", "ledger", "commit-core", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    out.push(ctl("ledger-control-C1-two-step-record", L2, vec![Path::CommitTwoStep]));
    out.push(ctl("ledger-control-C2-overwrite-record", L1, vec![Path::Commit, Path::CommitOverwrite]));
    out.push(ctl("ledger-control-C3-ignore-head", L3, vec![Path::CommitIgnoreHead]));
    out.push(ctl("ledger-control-C4-unguarded-bypass", L4, vec![Path::Commit, Path::Bypass(Guard::NoGuard)]));
    // sharpness on the reviewed bypass-guarded design: two records with content live; a strict refusal
    let rv = Machine { o: &StrictCachedGuard, paths: StrictCachedGuard.reviewed() };
    out.push(reach("ledger-sharp-two-records", meta("M-01", "ledger", "strict-cached-guard", StrictCachedGuard.objects(), "reviewed", "sharpness", "", &[], ""),
                   &rv, "never: two records and live content", |s: &S| s.records.len() == 2 && s.content != 0));
    out.push(reach("ledger-sharp-strict-refusal", meta("M-01", "ledger", "strict-cached-guard", StrictCachedGuard.objects(), "reviewed", "sharpness", "", &[], ""),
                   &rv, "never: a write refused while strict", |s: &S| s.refusals > 0 && s.strict));
    out
}
