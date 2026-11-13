//! Machine 2, the refinement audit: an executable twin of L1 (proofs/src/l1.rs) and the binding from the redaction
//! core (machine 1) to it, the executable twin of `l2::abs` and `l2::lab` (proofs/src/l2.rs).
//!
//! `explorer::refinement::audit` explores every concrete state, keeps it (so a lossy abstraction cannot hide a
//! counterexample), and checks on each step that the abstract state either stays the same (an internal step) or
//! moves by exactly the L1 step the binding names, and that L1's invariants hold on every abstract state.
//! The reviewed design must pass exhaustively; the as-built design must fail (its first tombstone is L1's Begin,
//! taken while the target may be live: F-1302).
use crate::redaction::{self, member, A, Design, Rec, S};
use explorer::refinement::Binding;
use explorer::*;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum R1 { Live(u8), Tomb(u8), Audit }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Rev1 { pub recs: Vec<R1>, pub text: bool, pub key: Option<u8> }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Ks { Bound(u8), Redacted }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct L1S {
    pub hist: Vec<Rev1>,
    pub live: BTreeSet<u8>,
    pub keys: BTreeMap<u8, Ks>,
    pub redacting: Option<u8>,
    pub audit_due: bool,
}

#[derive(Clone, Debug)]
pub enum L1A { Commit(u8), Erase(u8), Bypass, Begin(u8), Finish(u8) }

pub struct L1;

fn has_tomb(r: &Rev1) -> bool { r.recs.iter().any(|x| matches!(x, R1::Tomb(_))) }

impl Model for L1 {
    type State = L1S;
    type Action = L1A;
    fn init_states(&self) -> Vec<L1S> {
        vec![L1S { hist: vec![], live: BTreeSet::new(), keys: BTreeMap::new(), redacting: None, audit_due: false }]
    }
    fn actions(&self, _: &L1S) -> Vec<L1A> {
        let mut v: Vec<L1A> = (0..4).map(L1A::Commit).collect();
        v.extend([L1A::Erase(0), L1A::Erase(1), L1A::Bypass, L1A::Begin(0), L1A::Begin(1), L1A::Finish(0), L1A::Finish(1)]);
        v
    }
    fn next(&self, s: &L1S, a: &L1A) -> Option<L1S> {
        let mut u = s.clone();
        let live_in = |t: u8| s.live.iter().any(|&k| member(t, k));
        match *a {
            L1A::Commit(c) => {
                let (keys, key) = redaction::changeset(c);
                if s.keys.contains_key(&key) { return None; }
                if let Some(t) = s.redacting { if keys.iter().any(|&k| member(t, k)) { return None; } }
                u.hist.push(Rev1 { recs: keys.iter().map(|&k| R1::Live(k)).collect(), text: true, key: Some(key) });
                u.keys.insert(key, Ks::Bound(s.hist.len() as u8));
                u.live.extend(keys);
            }
            L1A::Erase(t) => { u.live.retain(|&k| !member(t, k)); }
            L1A::Bypass => { u.live.insert(0); }
            L1A::Begin(t) => {
                if s.redacting.is_some() || live_in(t) { return None; }
                let mut any = false;
                for rev in u.hist.iter_mut() {
                    for x in rev.recs.iter_mut() {
                        if let R1::Live(k) = *x { if member(t, k) { *x = R1::Tomb(k); any = true; } }
                    }
                    if has_tomb(rev) { rev.text = false; rev.key = None; }
                }
                for (_, ks) in u.keys.iter_mut() {
                    if let Ks::Bound(i) = *ks { if has_tomb(&u.hist[i as usize]) { *ks = Ks::Redacted; } }
                }
                u.redacting = Some(t);
                u.audit_due = any;
            }
            L1A::Finish(t) => {
                if s.redacting != Some(t) || live_in(t) { return None; }
                if s.audit_due { u.hist.push(Rev1 { recs: vec![R1::Audit], text: false, key: None }); }
                u.redacting = None;
                u.audit_due = false;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<L1S>> {
        vec![
            invariant("L1 Decision 2: a revision with a tombstone has no free text and no retry key",
                |s: &L1S| s.hist.iter().all(|r| !has_tomb(r) || (!r.text && r.key.is_none()))),
            invariant("L1 retry keys: a bound key names its own untouched revision", |s: &L1S| {
                s.keys.iter().all(|(k, ks)| match ks {
                    Ks::Bound(i) => s.hist.get(*i as usize).map_or(false, |r| !has_tomb(r) && r.key == Some(*k)),
                    Ks::Redacted => true,
                })
            }),
            invariant("L1 marker: while a redaction runs no live record of its target remains", |s: &L1S| {
                match s.redacting {
                    Some(t) => s.hist.iter().all(|r| r.recs.iter().all(|x| !matches!(x, R1::Live(k) if member(t, *k)))),
                    None => !s.audit_due,
                }
            }),
        ]
    }
}

/// `l2::abs`, executably.
pub fn abs(s: &S) -> L1S {
    let implied = |recs: &Vec<Rec>| match s.marker {
        Some(t) => recs.iter().any(|x| matches!(x, Rec::Live(k) if member(t, *k))),
        None => false,
    };
    let hist: Vec<Rev1> = s.revs.iter().map(|r| {
        let imp = implied(&r.recs);
        Rev1 {
            recs: r.recs.iter().map(|x| match *x {
                Rec::Live(k) => match s.marker { Some(t) if member(t, k) => R1::Tomb(k), _ => R1::Live(k) },
                Rec::Tomb(k) => R1::Tomb(k),
                Rec::Audit { .. } => R1::Audit,
            }).collect(),
            text: r.text && !imp,
            key: if imp { None } else { r.key },
        }
    }).collect();
    let mut keys = BTreeMap::new();
    for (&k, &i) in &s.idem {
        keys.insert(k, if implied(&s.revs[i as usize].recs) { Ks::Redacted } else { Ks::Bound(i) });
    }
    for &k in &s.idem_red { keys.insert(k, Ks::Redacted); }
    let some_member = match s.marker {
        Some(t) => s.revs.iter().any(|r| r.recs.iter().any(|x| matches!(x, Rec::Live(k) if member(t, *k)))),
        None => false,
    };
    L1S { hist, live: s.live.clone(), keys, redacting: s.marker, audit_due: s.count > 0 || some_member }
}

pub struct Bind { pub concrete: redaction::M, pub l1: L1 }

impl Binding for Bind {
    type Concrete = redaction::M;
    type Abstract = L1;
    type Observation = (BTreeSet<u8>, Option<u8>);
    fn concrete(&self) -> &redaction::M { &self.concrete }
    fn abstract_model(&self) -> &L1 { &self.l1 }
    fn abstract_state(&self, s: &S) -> L1S { abs(s) }
    fn abstract_action(&self, _a: &A) -> Option<L1A> { None }
    /// `l2::lab`, with the outcome read from the step (the Verus labels carry it as `fresh` and `ok`).
    fn abstract_action_at(&self, s: &S, a: &A, t: &S) -> Option<L1A> {
        match *a {
            A::Commit(c) => Some(L1A::Commit(c)),
            A::Erase(g) => Some(L1A::Erase(g)),
            A::Bypass => Some(L1A::Bypass),
            A::Start(..) | A::Scan(_) => match (s.marker, t.marker) {
                (None, Some(g)) => Some(L1A::Begin(g)),
                _ => None,
            },
            A::Final(_) => match (s.marker, t.marker) {
                (Some(g), None) => Some(L1A::Finish(g)),
                _ => None,
            },
            A::Stop(_) => None,
        }
    }
    fn observe_concrete(&self, s: &S) -> Self::Observation { (s.live.clone(), s.marker) }
    fn observe_abstract(&self, s: &L1S) -> Self::Observation { (s.live.clone(), s.redacting) }
}

pub fn binding(design: Design) -> Bind { Bind { concrete: redaction::M { design }, l1: L1 } }

