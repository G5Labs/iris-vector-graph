//! Module 00: the universal axioms model-checked over the composed mechanisms (3.3-model-check for module 00).
//!
//! One machine composes M-01 (ledger commit with record), M-02 (retry binding), M-03 (head lock and redaction
//! marker), M-04 (a derived store kept in step with the content), M-05 (erasure and redaction reach), M-10 (refusals)
//! over two tenants, A (0) and B (1). Four processes, interleaved in every order:
//! - W: a client committing tenant A's content with a retry key, then retrying the same request once; as built its
//!   post-commit properties are a separate unlocked step after each ok answer, replays included
//!   (ledger/client.py:418-487); reviewed: the property is written in the commit (residual question 6's alternative).
//! - C: a commit of tenant B's content (no key).
//! - E: erasure of tenant A (content and property rows, and the derived store). As built: no head lock
//!   (Eraser.cls:665-678) and the derived store is not reached (F-0702, F-0606 family); reviewed: under the head lock,
//!   maintaining the derived store.
//! - R: redaction of tenant A. As built: unlocked liveness check, marker in the first locked batch, Final clears any
//!   marker (LedgerRedact.cls:185-430); reviewed: check, marker and tombstones in one locked section, Final clears its
//!   own marker. A Final that finds the target live parks the run (RED-B8.2); the operator may re-erase (E again) and
//!   resume (premises: operator re-runs, TRUST.md).
//! Axioms checked (each with its own check, `Keep`): AX-02 (a step on one tenant leaves the other's content, property,
//! derived entry and records), AX-03 (a refusing step changes nothing but its process), AX-04 (erasure is all or none:
//! no stop leaves one of its stores changed and not the other), AX-05 (records only append or become tombstones),
//! AX-06 (one effect and one post-commit write per key), AX-07 (live governed content has a live record), AX-08 (the
//! derived store equals the content), AX-10 (after a receipt with no fresh commit into A since it, tenant A holds nothing and its
//! key is not bound; no replayed answer's post-commit write re-creates erased content), AX-11 (no tombstone of live content; a marked target is not
//! live), AX-12 (a receipt is written only when no live record of the target remains), AX-14 (AG EF: every process
//! can finish and the marker be released). AX-01, AX-09 and AX-13 are not in this composition; their laws are checked
//! by the generic machines M-12/M-01 (AX-01), M-08 (AX-09) and M-11 (AX-13).
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Step {
    Lock, Unlock,
    CheckMarker(u8), CheckMarkerBad(u8), CheckNotLive(u8), CheckNotLiveFinal(u8, u8),
    SetMarker(u8), ClearOwn, ClearAny,
    Apply(u8, bool), ApplyProp(u8, bool), ApplyUnrecorded(u8), Post(u8),
    EraseBoth(u8, bool), EraseContent(u8), EraseProp(u8),
    TombAll(u8), TombAllAny, DeleteRecords(u8), MoveBinding, Receipt,
}
use Step::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Pc { At(u8), Done, Refused, Parked(u8) }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Bind { Free, Bound, Redacted }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Reply { NoReply, First, Replay, Refused }

#[derive(Clone, Debug)]
pub struct Design { pub name: &'static str, pub progs: [Vec<Step>; 4], pub post_always: bool, pub stoppable_e: bool }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub pc: [Pc; 4],
    pub lock: Option<u8>,
    pub marker: Option<(u8, u8)>,
    pub content: [bool; 2],
    pub prop: [bool; 2],
    pub der: [bool; 2],
    pub recs: Vec<(u8, bool)>,
    pub bind: Bind,
    pub effects: u8,
    pub posts: u8,
    pub reply: Reply,
    pub receipt: bool,
    pub partial: bool,
    pub e_done: bool,
    pub fresh_a: bool,
    /// a fresh commit into tenant A after the receipt (re-onboarding)
    pub after_receipt: bool,
    /// a replayed answer's post-commit write re-created erased content (no fresh commit since the erasure)
    pub revived: bool,
}

#[derive(Clone, Debug)]
pub enum A { Run(u8, Step), StopE, ReErase, Resume }

pub struct Sys { pub d: Design }

pub const AX02: &str = "AX-02 graph and tenant scope";
pub const AX03: &str = "AX-03 explicit, inert refusals";
pub const AX04: &str = "AX-04 all or none across stores";
pub const AX05: &str = "AX-05 history only grows";
pub const AX06: &str = "AX-06 at most once per retry key";
pub const AX07: &str = "AX-07 a governed change is recorded with it";
pub const AX08: &str = "AX-08 derived stores match or say they are stale";
pub const AX10: &str = "AX-10 removal reaches every store";
pub const AX11: &str = "AX-11 conflicting commands serialize";
pub const AX11M: &str = "AX-11 a marked target is not live";
pub const AX12: &str = "AX-12 truthful outcomes";
pub const AX14: &str = "AX-14 accepted work progresses";

const W: usize = 0;
const C: usize = 1;
const E: usize = 2;
const R: usize = 3;

fn proj(s: &S, t: usize) -> (bool, bool, bool, Vec<bool>) {
    (s.content[t], s.prop[t], s.der[t], s.recs.iter().filter(|r| r.0 as usize == t).map(|r| r.1).collect())
}
fn shared(s: &S) -> (Option<(u8, u8)>, [bool; 2], [bool; 2], [bool; 2], Vec<(u8, bool)>, Bind, u8, u8, bool, bool, bool) {
    (s.marker, s.content, s.prop, s.der, s.recs.clone(), s.bind, s.effects, s.posts, s.receipt, s.partial, s.e_done)
}

impl Sys {
    fn finish(u: &mut S, i: usize, pc: Pc) { u.pc[i] = pc; if u.lock == Some(i as u8) { u.lock = None; } }
}

impl Model for Sys {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { pc: [Pc::At(0); 4], lock: None, marker: None, content: [false; 2], prop: [false; 2], der: [false; 2], recs: vec![], bind: Bind::Free,
                 effects: 0, posts: 0, reply: Reply::NoReply, receipt: false, partial: false, e_done: false, fresh_a: false, after_receipt: false, revived: false }]
    }
    fn actions(&self, s: &S) -> Vec<A> {
        let mut v = vec![A::StopE, A::ReErase, A::Resume];
        for i in 0..4 { if let Pc::At(k) = s.pc[i] { v.push(A::Run(i as u8, self.d.progs[i][k as usize])); } }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        match *a {
            A::StopE => {
                if !self.d.stoppable_e { return None; }
                let Pc::At(k) = s.pc[E] else { return None };
                if !matches!(self.d.progs[E][k as usize], EraseProp(_)) { return None; }
                u.partial = true; Self::finish(&mut u, E, Pc::Done); return Some(u);
            }
            A::ReErase => {
                if s.pc[E] != Pc::Done || !(s.content[0] || s.prop[0]) { return None; }
                u.pc[E] = Pc::At(0); return Some(u);
            }
            A::Resume => { let Pc::Parked(k) = s.pc[R] else { return None }; u.pc[R] = Pc::At(k); return Some(u); }
            A::Run(i, step) => {
                let i = i as usize;
                let Pc::At(k) = s.pc[i] else { return None };
                let me = i as u8;
                let mut next = Pc::At(k + 1);
                match step {
                    Lock => { if s.lock.is_some() && s.lock != Some(me) { return None; } u.lock = Some(me); }
                    Unlock => { if u.lock == Some(me) { u.lock = None; } }
                    CheckMarker(t) => { if matches!(s.marker, Some((m, o)) if m == t && o != me) { next = Pc::Refused; u.reply = if i == W { Reply::Refused } else { u.reply }; } }
                    CheckMarkerBad(t) => { if matches!(s.marker, Some((m, o)) if m == t && o != me) { next = Pc::Refused; u.content[t as usize] = true; } }
                    CheckNotLive(t) => { if s.content[t as usize] || s.prop[t as usize] { next = Pc::Refused; } }
                    CheckNotLiveFinal(t, back) => { if s.content[t as usize] || s.prop[t as usize] { next = Pc::Parked(back); } }
                    SetMarker(t) => { if s.marker.is_none() { u.marker = Some((t, me)); } }
                    ClearOwn => { if matches!(s.marker, Some((_, o)) if o == me) { u.marker = None; } }
                    ClearAny => { u.marker = None; }
                    Apply(t, keyed) | ApplyProp(t, keyed) => {
                        let with_prop = matches!(step, ApplyProp(..));
                        if keyed && s.bind == Bind::Bound { u.reply = Reply::Replay; }
                        else if keyed && s.bind == Bind::Redacted { u.reply = Reply::Refused; }
                        else {
                            let tt = t as usize;
                            u.content[tt] = true; u.der[tt] = true; u.recs.push((t, true));
                            if with_prop { u.prop[tt] = true; u.posts += 1; }
                            if keyed { u.bind = Bind::Bound; u.effects += 1; }
                            u.reply = Reply::First;
                            if tt == 0 { u.fresh_a = true; if s.receipt { u.after_receipt = true; } }
                        }
                    }
                    ApplyUnrecorded(t) => { let tt = t as usize; u.content[tt] = true; u.der[tt] = true; u.prop[tt] = true; if tt == 0 { u.fresh_a = true; if s.receipt { u.after_receipt = true; } } }
                    Post(t) => {
                        let runs = s.reply == Reply::First || (s.reply == Reply::Replay && self.d.post_always);
                        if runs { u.prop[t as usize] = true; u.posts += 1; if s.reply == Reply::Replay && s.e_done && !s.fresh_a { u.revived = true; } }
                    }
                    EraseBoth(t, maint) => { let tt = t as usize; u.content[tt] = false; u.prop[tt] = false; if maint { u.der[tt] = false; } u.e_done = true; if tt == 0 { u.fresh_a = false; } }
                    EraseContent(t) => { let tt = t as usize; u.content[tt] = false; u.der[tt] = false; }
                    EraseProp(t) => { let tt = t as usize; u.prop[tt] = false; u.e_done = true; if tt == 0 { u.fresh_a = false; } }
                    TombAll(t) => { for r in u.recs.iter_mut() { if r.0 == t { r.1 = false; } } }
                    TombAllAny => { for r in u.recs.iter_mut() { r.1 = false; } }
                    DeleteRecords(t) => { u.recs.retain(|r| r.0 != t); }
                    MoveBinding => { if s.bind == Bind::Bound { u.bind = Bind::Redacted; } }
                    Receipt => { u.receipt = true; u.after_receipt = false; }
                }
                match next {
                    Pc::At(n) if n as usize >= self.d.progs[i].len() => Self::finish(&mut u, i, Pc::Done),
                    Pc::At(n) => u.pc[i] = Pc::At(n),
                    other => Self::finish(&mut u, i, other),
                }
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(AX04, |s: &S| !s.partial),
            invariant(AX06, |s: &S| s.effects <= 1 && s.posts <= 1),
            invariant(AX07, |s: &S| (0..2u8).all(|t| !s.content[t as usize] || s.recs.contains(&(t, true)))),
            invariant(AX08, |s: &S| s.der == s.content),
            invariant(AX10, |s: &S| {
                let complete = !s.receipt || s.after_receipt || (!s.content[0] && !s.prop[0] && !s.der[0] && s.bind != Bind::Bound);
                complete && !s.revived
            }),
            invariant(AX11M, |s: &S| match s.marker { Some((t, _)) => !s.content[t as usize] && !s.prop[t as usize], None => true }),
        ]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![
            action_property(AX02, |o: &S, a: &A, n: &S| match a {
                A::Run(i, _) if *i as usize == C => proj(o, 0) == proj(n, 0),
                A::Run(_, _) | A::ReErase | A::StopE | A::Resume => proj(o, 1) == proj(n, 1),
            }),
            action_property(AX03, |o: &S, a: &A, n: &S| match a {
                A::Run(i, _) => {
                    let i = *i as usize;
                    let refused = matches!(n.pc[i], Pc::Refused | Pc::Parked(_)) && !matches!(o.pc[i], Pc::Refused | Pc::Parked(_));
                    !refused || shared(o) == shared(n)
                }
                _ => true,
            }),
            action_property(AX05, |o: &S, _a: &A, n: &S| n.recs.len() >= o.recs.len()
                && (0..o.recs.len()).all(|k| n.recs[k].0 == o.recs[k].0 && (n.recs[k].1 == o.recs[k].1 || !n.recs[k].1))),
            action_property(AX11, |o: &S, a: &A, _n: &S| match a {
                A::Run(_, TombAll(t)) => !o.content[*t as usize],
                _ => true,
            }),
            action_property(AX12, |o: &S, a: &A, _n: &S| !matches!(a, A::Run(_, Receipt)) || !o.recs.contains(&(0, true))),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant(AX14, |s: &S| s.marker.is_none() && s.pc.iter().all(|p| matches!(p, Pc::Done | Pc::Refused)))]
    }
}

fn reviewed() -> Design {
    Design {
        name: "reviewed",
        progs: [
            vec![Lock, CheckMarker(0), ApplyProp(0, true), Unlock, Lock, CheckMarker(0), ApplyProp(0, true), Unlock],
            vec![Lock, CheckMarker(1), Apply(1, false), Unlock],
            vec![Lock, EraseBoth(0, true), Unlock],
            vec![Lock, CheckNotLive(0), SetMarker(0), TombAll(0), MoveBinding, Unlock, Lock, CheckNotLiveFinal(0, 6), ClearOwn, Receipt, Unlock],
        ],
        post_always: false, stoppable_e: false,
    }
}

fn as_built() -> Design {
    Design {
        name: "as-built",
        progs: [
            vec![Lock, CheckMarker(0), Apply(0, true), Unlock, Post(0), Lock, CheckMarker(0), Apply(0, true), Unlock, Post(0)],
            vec![Lock, CheckMarker(1), Apply(1, false), Unlock],
            vec![EraseBoth(0, false)],
            vec![CheckNotLive(0), Lock, SetMarker(0), TombAll(0), MoveBinding, Unlock, Lock, CheckNotLiveFinal(0, 6), ClearAny, Receipt, Unlock],
        ],
        post_always: true, stoppable_e: false,
    }
}

fn m00(design: &'static str, kind: &'static str, law: &'static str, f: &[&'static str]) -> Meta {
    meta("SYS", "sys00", "composed-axioms", &["00/system"], design, kind, law, f, "")
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    let rv = Sys { d: reviewed() };
    let ab = Sys { d: as_built() };
    out.push(check("sys00-reviewed-all-axioms", m00("reviewed", "safety", "all", &[]), Expect::Pass, &Keep::safety(&rv)));
    out.push(check("sys00-reviewed-progress", m00("reviewed", "progress", AX14, &[]), Expect::Pass, &Keep::progress(&rv)));
    // as built: each axiom alone
    let expect_ab: [(&str, &[&str], bool); 12] = [
        (AX02, &[], false), (AX03, &[], false), (AX04, &[], false), (AX05, &[], false),
        (AX06, &["F-1101", "F-1306"], true), (AX07, &["F-1302"], true), (AX08, &["F-0702", "F-0606"], true),
        (AX10, &["F-1306", "F-0702"], true), (AX11, &["F-1302"], true), (AX11M, &["F-1302", "F-1306"], true), (AX12, &[], false), (AX14, &[], false),
    ];
    for (law, f, viol) in expect_ab.iter() {
        let id = format!("sys00-as-built-{}", law.split(' ').next().unwrap().to_lowercase() + if *law == AX11M { "-marker" } else { "" });
        if *law == AX14 {
            out.push(check(&id, m00("as-built", "progress", law, f), Expect::Pass, &Keep::progress(&ab)));
        } else if *viol {
            out.push(check(&id, m00("as-built", "safety", law, f), Expect::Violation(law), &Keep::only(&ab, &[law])));
        } else {
            out.push(check(&id, m00("as-built", "safety", law, f), Expect::Pass, &Keep::only(&ab, &[law])));
        }
    }
    // controls: one mutant of the reviewed composition per axiom
    let mut ctl = |id: &str, law: &'static str, d: Design| {
        let m = Sys { d };
        if law == AX14 {
            out.push(check(id, m00("control", "progress", law, &[]), Expect::Violation(law), &Keep::progress(&m)));
        } else {
            out.push(check(id, m00("control", "safety", law, &[]), Expect::Violation(law), &Keep::only(&m, &[law])));
        }
    };
    let mut d = reviewed(); d.progs[R][3] = TombAllAny; ctl("sys00-control-ax02-tomb-both-tenants", AX02, d);
    let mut d = reviewed(); d.progs[W][1] = CheckMarkerBad(0); ctl("sys00-control-ax03-refusal-writes", AX03, d);
    let mut d = reviewed(); d.progs[E] = vec![Lock, EraseContent(0), EraseProp(0), Unlock]; d.stoppable_e = true; ctl("sys00-control-ax04-erase-split", AX04, d);
    let mut d = reviewed(); d.progs[R][3] = DeleteRecords(0); ctl("sys00-control-ax05-delete-records", AX05, d);
    let mut d = reviewed(); d.progs[W] = as_built().progs[W].clone(); d.post_always = true; ctl("sys00-control-ax06-post-on-replay", AX06, d);
    let mut d = reviewed(); d.progs[W][2] = ApplyUnrecorded(0); ctl("sys00-control-ax07-unrecorded-apply", AX07, d);
    let mut d = reviewed(); d.progs[E][1] = EraseBoth(0, false); ctl("sys00-control-ax08-erase-skips-derived", AX08, d);
    let mut d = reviewed(); d.progs[R] = vec![Lock, CheckNotLive(0), SetMarker(0), TombAll(0), Unlock, Lock, CheckNotLiveFinal(0, 5), ClearOwn, Receipt, Unlock];
    ctl("sys00-control-ax10-binding-kept", AX10, d);
    let mut d = reviewed(); d.progs[R] = vec![CheckNotLive(0), Lock, SetMarker(0), TombAll(0), MoveBinding, Unlock, Lock, CheckNotLiveFinal(0, 6), ClearOwn, Receipt, Unlock];
    ctl("sys00-control-ax11-check-before-lock", AX11, d);
    let mut d = reviewed(); d.progs[R] = vec![Lock, CheckNotLive(0), SetMarker(0), Receipt, TombAll(0), MoveBinding, Unlock, Lock, CheckNotLiveFinal(0, 7), ClearOwn, Unlock];
    ctl("sys00-control-ax12-receipt-early", AX12, d);
    let mut d = reviewed(); d.progs[R] = vec![Lock, CheckNotLive(0), SetMarker(0), TombAll(0), MoveBinding, Unlock, Lock, CheckNotLiveFinal(0, 6), Receipt, Unlock];
    ctl("sys00-control-ax14-marker-never-cleared", AX14, d);
    // sharpness on the reviewed composition
    out.push(reach("sys00-sharp-redaction-completes", m00("reviewed", "sharpness", "", &[]), &rv, "never: tenant A redacted with a receipt while B is live",
                   |s: &S| s.receipt && s.content[1] && !s.content[0] && s.bind == Bind::Redacted));
    out.push(reach("sys00-sharp-retry-refused-after-redaction", m00("reviewed", "sharpness", "", &[]), &rv, "never: the retry refused after redaction",
                   |s: &S| s.reply == Reply::Refused && s.bind == Bind::Redacted));
    out.push(reach("sys00-sharp-replay", m00("reviewed", "sharpness", "", &[]), &rv, "never: a replayed answer", |s: &S| s.reply == Reply::Replay));
    out.push(reach("sys00-sharp-commit-blocked-by-marker", m00("reviewed", "sharpness", "", &[]), &rv, "never: the writer refused by the marker",
                   |s: &S| s.pc[W] == Pc::Refused && s.marker.is_some()));
    out
}
