//! Refinement audit of M2 against an executable L1 (the business machine of the original proofs/src/l1.rs, extended
//! with what M2 adds: incarnations, the statement map, per-target audit counts and erasure by graph).
//!
//! L1 actions are atomic: Commit(c, incarnation), Erase(graph), Begin(target) (tombstones every live record of the
//! target at once, clears Decision-2 metadata, moves retry keys to "redacted", remembers how many it tombstoned),
//! Finish(target, audit) (writes the audit with exactly that count). L1 invariants: Decision 2, retry keys, marker
//! (while redacting t no record of t is content), no tombstone of a live incarnation, statements = live edges.
//!
//! The abstraction maps an M2 state to L1 through the committed view (every open transaction's undo log applied, value-
//! based as IRIS does) and the implied tombstones of the marked target (as the original l2::abs): while the marker names
//! t, every live record of t is already a tombstone in L1. Labels: PEnd that commits -> Commit; E4 -> Erase; the step that
//! creates the marker -> Begin; the Final that removes it -> Finish; everything else must be a stutter (the abstract state
//! unchanged). `explorer::refinement::audit` keeps every concrete state, so a lossy abstraction cannot hide a step.
use crate::m2::{self, g_of, Design, Rec, Run, S, A, M2, NE};
use crate::{limits, summarize, Check, Expect, CAP};
use explorer::refinement::Binding;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum R1 { Live { e: u8, inc: u8, del: bool }, Tomb { e: u8, inc: u8, del: bool }, Audit { t: u8, n: u8 } }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Rev1 { pub recs: Vec<R1>, pub text: bool, pub key: u8 }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Ks { Unused, Bound(u8), Redacted }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct L1S {
    pub hist: Vec<Rev1>,
    /// live incarnation per edge (0: none)
    pub live: [u8; NE],
    /// edges with a live statement
    pub stmts: u8,
    pub keys: [Ks; 3],
    pub redacting: Option<u8>,
    pub due: u8,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum L1A { Commit(u8, u8), Erase(u8), Begin(u8), Finish(u8, bool) }

pub struct L1;

fn has_tomb(r: &Rev1) -> bool { r.recs.iter().any(|x| matches!(x, R1::Tomb { .. })) }
fn live_t(s: &L1S, t: u8) -> bool { (0..NE).any(|e| g_of(e) == t && s.live[e] != 0) }

impl Model for L1 {
    type State = L1S;
    type Action = L1A;
    fn init_states(&self) -> Vec<L1S> { vec![abs(&M2::new(m2::Cfg::new(Design::Reviewed)).init_states()[0])] }
    fn actions(&self, _: &L1S) -> Vec<L1A> { vec![] }
    fn next(&self, s: &L1S, a: &L1A) -> Option<L1S> {
        let mut u = s.clone();
        match *a {
            L1A::Commit(c, inc) => {
                if s.keys[c as usize + 1] != Ks::Unused || s.redacting == Some(0) { return None; }
                let e = if c == 0 { 1u8 } else { 0u8 };
                if c == 0 { if s.live[1] != 0 { return None; } u.live[1] = inc; u.stmts |= 1 << 1; }
                else { if s.live[0] != inc || inc == 0 || s.stmts & 1 == 0 { return None; } u.live[0] = 0; u.stmts &= !1; }
                u.hist.push(Rev1 { recs: vec![R1::Live { e, inc, del: c == 1 }], text: true, key: c + 2 });
                u.keys[c as usize + 1] = Ks::Bound(u.hist.len() as u8 - 1);
            }
            L1A::Erase(g) => {
                for e in 0..NE { if g_of(e) == g { u.live[e] = 0; u.stmts &= !(1 << e); } }
            }
            L1A::Begin(t) => {
                if s.redacting.is_some() || live_t(s, t) { return None; }
                let mut n = 0;
                for rev in u.hist.iter_mut() {
                    for x in rev.recs.iter_mut() {
                        if let R1::Live { e, inc, del } = *x { if g_of(e as usize) == t { *x = R1::Tomb { e, inc, del }; n += 1; } }
                    }
                    if has_tomb(rev) { rev.text = false; rev.key = 0; }
                }
                for k in 0..3 { if let Ks::Bound(i) = u.keys[k] { if has_tomb(&u.hist[i as usize]) { u.keys[k] = Ks::Redacted; } } }
                u.redacting = Some(t);
                u.due = n;
            }
            L1A::Finish(t, audit) => {
                if s.redacting != Some(t) || live_t(s, t) { return None; }
                if !audit && s.due > 0 { return None; }
                if audit { u.hist.push(Rev1 { recs: vec![R1::Audit { t, n: s.due }], text: true, key: 0 }); }
                u.redacting = None;
                u.due = 0;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<L1S>> {
        vec![
            invariant("L1 Decision 2: a revision with a tombstone has no free text and no retry key",
                |s: &L1S| s.hist.iter().all(|r| !has_tomb(r) || (!r.text && r.key == 0))),
            invariant("L1 retry keys: a bound key names its own revision with no tombstone", |s: &L1S| {
                (0..3).all(|k| match s.keys[k] {
                    Ks::Bound(i) => s.hist.get(i as usize).map_or(false, |r| !has_tomb(r) && r.key == k as u8 + 1),
                    _ => true,
                })
            }),
            invariant("L1 marker: while a redaction runs no record of its target is content", |s: &L1S| match s.redacting {
                Some(t) => s.hist.iter().all(|r| r.recs.iter().all(|x| !matches!(x, R1::Live { e, .. } if g_of(*e as usize) == t))),
                None => s.due == 0,
            }),
            invariant("L1 no tombstone of a live incarnation", |s: &L1S| {
                s.hist.iter().all(|r| r.recs.iter().all(|x| !matches!(*x, R1::Tomb { e, inc, .. } if s.live[e as usize] == inc)))
            }),
            invariant("L1 statements are exactly the live edges",
                |s: &L1S| (0..NE).all(|e| (s.stmts & (1 << e) != 0) == (s.live[e] != 0))),
        ]
    }
}

/// The committed view: every open transaction rolled back (value-based, as IRIS).
pub fn committed(s: &S) -> S {
    let mut c = s.clone();
    for log in [s.p_undo.clone(), s.e_undo.clone(), s.w_undo.clone()] {
        for u in log.iter().rev() { if get(&c, u.item) == u.after { set(&mut c, u.item, u.before); } }
    }
    c
}
fn get(s: &S, it: m2::Item) -> u8 {
    match it { m2::Item::Row(e) => s.row[e as usize], m2::Item::Adj(e) => (s.adj >> e) & 1, m2::Item::Stmt(i) => s.stmt[i as usize - 1],
               m2::Item::Tuple(e) => s.tuple[e as usize], m2::Item::Next => s.next }
}
fn set(s: &mut S, it: m2::Item, v: u8) {
    match it { m2::Item::Row(e) => s.row[e as usize] = v, m2::Item::Adj(e) => if v == 1 { s.adj |= 1 << e } else { s.adj &= !(1 << e) },
               m2::Item::Stmt(i) => s.stmt[i as usize - 1] = v, m2::Item::Tuple(e) => s.tuple[e as usize] = v, m2::Item::Next => s.next = v }
}

pub fn abs(s: &S) -> L1S {
    let c = committed(s);
    let implied = |x: &Rec| matches!((s.marker, x), (Some(t), Rec::Live { e, .. }) if g_of(*e as usize) == t);
    let mut n_implied = 0;
    let hist: Vec<Rev1> = s.revs.iter().map(|r| {
        let imp = r.recs.iter().any(|x| implied(x));
        Rev1 {
            recs: r.recs.iter().map(|x| match *x {
                Rec::Live { e, inc, del } => if implied(x) { n_implied += 1; R1::Tomb { e, inc, del } } else { R1::Live { e, inc, del } },
                Rec::Tomb { e, inc, del } => R1::Tomb { e, inc, del },
                Rec::Audit { t, n } => R1::Audit { t, n },
            }).collect(),
            text: r.text && !imp,
            key: if imp { 0 } else { r.key },
        }
    }).collect();
    let mut keys = [Ks::Unused; 3];
    for k in 0..3 {
        if s.idem[k] != 0 {
            let i = s.idem[k] - 1;
            keys[k] = if s.revs[i as usize].recs.iter().any(|x| implied(x)) { Ks::Redacted } else { Ks::Bound(i) };
        } else if s.idem_red & (1 << k) != 0 { keys[k] = Ks::Redacted; }
    }
    let mut live = [0u8; NE];
    let mut stmts = 0u8;
    for e in 0..NE {
        live[e] = c.row[e];
        let id = c.tuple[e];
        if id != 0 && c.stmt[id as usize - 1] == 1 + 2 * e as u8 { stmts |= 1 << e; }
    }
    // one counter is non-zero at a time: the shared one at the pin, the marked target's in the reviewed design
    let due = match s.marker { Some(_) => s.count[0] + s.count[1] + n_implied, None => 0 };
    L1S { hist, live, stmts, keys, redacting: s.marker, due }
}

pub struct Bind { pub concrete: M2, pub l1: L1 }

impl Binding for Bind {
    type Concrete = M2;
    type Abstract = L1;
    type Observation = ([u8; NE], Option<u8>);
    fn concrete(&self) -> &M2 { &self.concrete }
    fn abstract_model(&self) -> &L1 { &self.l1 }
    fn abstract_state(&self, s: &S) -> L1S { abs(s) }
    fn abstract_action(&self, _a: &A) -> Option<L1A> { None }
    fn abstract_action_at(&self, s: &S, a: &A, t: &S) -> Option<L1A> {
        match *a {
            A::PEnd => match s.p { m2::Pp::Open { c, ok: true, inc } => Some(L1A::Commit(c, inc)), _ => None },
            A::E4 => match s.e { m2::Ep::Open { g, .. } => Some(L1A::Erase(g)), _ => None },
            A::Read1(..) | A::Read2(_) | A::Batch(_) => match (s.marker, t.marker) { (None, Some(g)) => Some(L1A::Begin(g)), _ => None },
            A::Final(p) => match (s.marker, t.marker, s.runs[p as usize]) {
                (Some(g), None, Run::Scan { .. }) => Some(L1A::Finish(g, t.revs.len() > s.revs.len())),
                _ => None,
            },
            _ => None,
        }
    }
    fn observe_concrete(&self, s: &S) -> Self::Observation { (committed(s).row, s.marker) }
    fn observe_abstract(&self, s: &L1S) -> Self::Observation { (s.live, s.redacting) }
}

pub fn checks() -> Vec<Check> {
    let mut v = vec![];
    v.push(Check { id: "refine-m2-reviewed", machine: "refinement", design: "reviewed", expect: Expect::Pass,
        what: "every step of reviewed M2 (stops and rollbacks included) is an L1 step or a stutter; L1 invariants hold on every abstract state",
        run: Box::new(|| {
            let b = Bind { concrete: M2::new(m2::Cfg::new(Design::Reviewed)), l1: L1 };
            summarize(explorer::refinement::audit(b, limits(CAP)).expect("audit"), m2::show, CAP)
        }) });
    v.push(Check { id: "refine-m2-as-built", machine: "refinement", design: "as-built", expect: Expect::Violation(""),
        what: "the as-built M2 does not refine L1 (its first tombstone is L1's Begin, taken while the target may be live)",
        run: Box::new(|| {
            let mut c = m2::Cfg::new(Design::AsBuilt);
            c.estop = false; c.pstop = false;
            let b = Bind { concrete: M2::new(c), l1: L1 };
            summarize(explorer::refinement::audit(b, limits(CAP)).expect("audit"), m2::show, CAP)
        }) });
    v.push(Check { id: "refine-m2-control-unlocked-start", machine: "refinement", design: "control", expect: Expect::Violation(""),
        what: "control: reviewed M2 with the unlocked start does not refine L1",
        run: Box::new(|| {
            let mut c = m2::Cfg::new(Design::Reviewed);
            c.mutant = m2::Mutant::UnlockedStart;
            let b = Bind { concrete: M2::new(c), l1: L1 };
            summarize(explorer::refinement::audit(b, limits(CAP)).expect("audit"), m2::show, CAP)
        }) });
    v
}
