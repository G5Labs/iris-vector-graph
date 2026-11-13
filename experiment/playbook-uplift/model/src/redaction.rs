//! Machine 1, the redaction core: executable twin of the L2 redaction machine (proofs/src/l2.rs).
//!
//! World: replay keys a1, a2 (tenant A) and b1 (tenant B); targets A = {a1, a2} and B = {b1}; two redacting
//! processes; changesets C0 (A only, key 0), C1 (B only, key 1), C2 (spanning A and B, key 2) and C3 (A again,
//! key 3); erasure of either target; one write that bypasses the ledger. Steps are the L2 transactions: Commit,
//! Erase, Bypass, Start, Scan (one record), Final, Stop (a stopped process; its open transaction is rolled back,
//! P-0001).
//!
//! Designs:
//! - `as-built` (LedgerRedact.cls at 3eaa79cf): Start checks the other-target marker and liveness without the
//!   head lock and sets no marker; the first tombstone sets the marker if none exists (lines 202-211, 322-324);
//!   a batch matches its own target whatever marker exists; the counters are shared under the one marker; Final
//!   re-checks its own target and writes the audit with the shared counts, then kills the marker (lines 409-441).
//! - `reviewed`: Start checks and sets the marker in one locked transaction; Scan and Final run only while the
//!   marker names their own target (the machine proved in Verus).
//!
//! Properties (each the executable twin of an L1 rule):
//! - action `no tombstone of live content` (L1 theorem_begin_spares_live; spec 256 FR-005);
//! - `each audit counts its own target` (Decision 1: the redaction revision records what it redacted);
//! - `Decision 2` and `retry keys` (L1 text_ok, keys_ok);
//! - `replay equals the store once settled` (L1 theorem_erase_then_redact; FR-007);
//! - always-possibly `settled`: from every state the ledger can reach no marker and no run (AG EF).
use explorer::*;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Design { AsBuilt, Reviewed }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Rec { Live(u8), Tomb(u8), Audit { t: u8, n: u8 } }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Rev { pub recs: Vec<Rec>, pub text: bool, pub key: Option<u8> }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Run { pub t: u8, pub i: u8, pub j: u8 }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub revs: Vec<Rev>,
    pub idem: BTreeMap<u8, u8>,
    pub idem_red: BTreeSet<u8>,
    pub red_rev: BTreeSet<u8>,
    pub marker: Option<u8>,
    pub count: u8,
    pub live: BTreeSet<u8>,
    pub runs: [Option<Run>; 2],
    // ghost
    pub tombs_of: [u8; 2],
    pub bypass: bool,
    pub pending: BTreeSet<u8>,
    /// revisions that existed at each target's last erasure (None: never erased)
    pub erased_at: [Option<u8>; 2],
    pub starts: u8,
    pub erases: u8,
}

#[derive(Clone, Debug)]
pub enum A { Commit(u8), Erase(u8), Bypass, Start(u8, u8), Scan(u8), Final(u8), Stop(u8) }

pub fn member(t: u8, k: u8) -> bool { if t == 0 { k <= 1 } else { k == 2 } }
pub fn name(k: u8) -> &'static str { ["a1", "a2", "b1"][k as usize] }
pub fn changeset(c: u8) -> (Vec<u8>, u8) {
    match c { 0 => (vec![0, 1], 0), 1 => (vec![2], 1), 2 => (vec![0, 2], 2), _ => (vec![0], 3) }
}

pub struct M { pub design: Design }

impl M {
    pub fn live_in(s: &S, t: u8) -> bool { s.live.iter().any(|&k| member(t, k)) }

    fn tombstone(&self, s: &mut S, p: usize, r: Run, k: u8) {
        let (i, j) = (r.i as usize, r.j as usize);
        s.revs[i].recs[j] = Rec::Tomb(k);
        if s.marker.is_none() { s.marker = Some(r.t); }
        if !s.red_rev.contains(&r.i) {
            s.revs[i].text = false;
            if let Some(key) = s.revs[i].key.take() {
                s.idem.remove(&key);
                s.idem_red.insert(key);
            }
        }
        s.red_rev.insert(r.i);
        s.count += 1;
        s.tombs_of[r.t as usize] += 1;
        s.runs[p] = Some(Run { j: r.j + 1, ..r });
    }

    pub fn replay(s: &S) -> BTreeSet<u8> {
        let mut m = BTreeSet::new();
        for rev in &s.revs {
            for r in &rev.recs {
                if let Rec::Live(k) = r { m.insert(*k); }
            }
        }
        m
    }
}

impl Model for M {
    type State = S;
    type Action = A;

    fn init_states(&self) -> Vec<S> {
        vec![S {
            revs: vec![], idem: BTreeMap::new(), idem_red: BTreeSet::new(), red_rev: BTreeSet::new(),
            marker: None, count: 0, live: BTreeSet::new(), runs: [None, None], tombs_of: [0, 0], bypass: false,
            pending: BTreeSet::new(), erased_at: [None, None], starts: 0, erases: 0,
        }]
    }

    fn actions(&self, _s: &S) -> Vec<A> {
        let mut v: Vec<A> = (0..4).map(A::Commit).collect();
        v.extend([A::Erase(0), A::Erase(1), A::Bypass]);
        for p in 0..2 {
            v.extend([A::Start(p, 0), A::Start(p, 1), A::Scan(p), A::Final(p), A::Stop(p)]);
        }
        v
    }

    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        match *a {
            A::Commit(c) => {
                let (keys, key) = changeset(c);
                if s.idem.contains_key(&key) || s.idem_red.contains(&key) { return None; }
                if let Some(t) = s.marker { if keys.iter().any(|&k| member(t, k)) { return None; } }
                u.revs.push(Rev { recs: keys.iter().map(|&k| Rec::Live(k)).collect(), text: true, key: Some(key) });
                u.idem.insert(key, s.revs.len() as u8);
                for k in keys { u.live.insert(k); }
            }
            A::Erase(t) => {
                if !Self::live_in(s, t) { return None; }
                u.live.retain(|&k| !member(t, k));
                u.pending.insert(t);
                u.erased_at[t as usize] = Some(s.revs.len() as u8);
                u.erases += 1;
            }
            A::Bypass => {
                if s.bypass { return None; }
                u.live.insert(0);
                u.bypass = true;
            }
            A::Start(p, t) => {
                let p = p as usize;
                if s.runs[p].is_some() || Self::live_in(s, t) { return None; }
                if let Some(m) = s.marker { if m != t { return None; } }
                u.runs[p] = Some(Run { t, i: 0, j: 0 });
                u.starts += 1;
                if self.design == Design::Reviewed && s.marker.is_none() { u.marker = Some(t); }
            }
            A::Scan(p) => {
                let pi = p as usize;
                let r = s.runs[pi]?;
                if (r.i as usize) >= s.revs.len() { return None; }
                if self.design == Design::Reviewed && s.marker != Some(r.t) { return None; }
                let row = &s.revs[r.i as usize].recs;
                if (r.j as usize) >= row.len() {
                    u.runs[pi] = Some(Run { i: r.i + 1, j: 0, ..r });
                } else {
                    match row[r.j as usize] {
                        Rec::Live(k) if member(r.t, k) => self.tombstone(&mut u, pi, r, k),
                        _ => u.runs[pi] = Some(Run { j: r.j + 1, ..r }),
                    }
                }
            }
            A::Final(p) => {
                let pi = p as usize;
                let r = s.runs[pi]?;
                if (r.i as usize) < s.revs.len() { return None; }
                u.runs[pi] = None;
                match s.marker {
                    None => { u.pending.remove(&r.t); } // nothing was redacted: no audit (LedgerRedact.cls:418)
                    Some(m) => {
                        if self.design == Design::Reviewed && m != r.t { return None; }
                        if Self::live_in(s, r.t) { return Some(u); } // target_live: the marker stays
                        if s.count > 0 {
                            u.revs.push(Rev { recs: vec![Rec::Audit { t: r.t, n: s.count }], text: false, key: None });
                        }
                        u.marker = None;
                        u.count = 0;
                        u.pending.remove(&r.t);
                    }
                }
            }
            A::Stop(p) => {
                if s.runs[p as usize].is_none() { return None; }
                u.runs[p as usize] = None;
            }
        }
        Some(u)
    }

    fn within_bounds(&self, s: &S) -> bool { s.revs.len() <= 6 && s.starts <= 3 && s.erases <= 3 }

    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant("Decision 2: a revision with a tombstone keeps no free text and no retry key", |s: &S| {
                s.revs.iter().all(|r| !r.recs.iter().any(|x| matches!(x, Rec::Tomb(_))) || (!r.text && r.key.is_none()))
            }),
            invariant("retry keys: a bound key names a revision with no tombstone", |s: &S| {
                s.idem.values().all(|&i| !s.revs[i as usize].recs.iter().any(|x| matches!(x, Rec::Tomb(_))))
            }),
            invariant("replay equals the store once settled", |s: &S| {
                if s.bypass || !s.pending.is_empty() || s.marker.is_some() || s.runs.iter().any(|r| r.is_some()) {
                    return true;
                }
                M::replay(s) == s.live
            }),
        ]
    }

    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![
            // L1's rule at record granularity: redaction removes only history that an erasure already took out of
            // the store. A record committed after its target's last erasure (or with no erasure at all) holds
            // content that is still live in this world (it has no deletes), so tombstoning it is the defect.
            action_property("no tombstone of live content", |s: &S, a: &A, t: &S| {
                if let A::Scan(p) = a {
                    if let Some(r) = s.runs[*p as usize] {
                        let (i, j) = (r.i as usize, r.j as usize);
                        if i < s.revs.len() && j < s.revs[i].recs.len() {
                            if let (Rec::Live(_), Rec::Tomb(_)) = (&s.revs[i].recs[j], &t.revs[i].recs[j]) {
                                return matches!(s.erased_at[r.t as usize], Some(e) if (i as u8) < e);
                            }
                        }
                    }
                }
                true
            }),
            action_property("each audit counts exactly its own target's tombstones", |s: &S, a: &A, t: &S| {
                if let A::Final(_) = a {
                    if let Some(rev) = t.revs.last() {
                        if t.revs.len() > s.revs.len() {
                            if let Rec::Audit { t: tg, n } = rev.recs[0] {
                                let own = t.tombs_of[tg as usize] - audited_before(s, tg);
                                return own == n;
                            }
                        }
                    }
                }
                true
            }),
        ]
    }

    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("settled: no marker and no run", |s: &S| s.marker.is_none() && s.runs.iter().all(|r| r.is_none()))]
    }
}

fn audited_before(s: &S, tg: u8) -> u8 {
    s.revs.iter().flat_map(|r| r.recs.iter()).map(|x| match x { Rec::Audit { t, n } if *t == tg => *n, _ => 0 }).sum()
}

pub fn show(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    for (i, (a, s)) in c.steps.iter().enumerate() {
        let recs: Vec<String> = s.revs.iter().enumerate().map(|(n, r)| format!("r{n}[{}]{}", r.recs.iter().map(|x| match x {
            Rec::Live(k) => name(*k).to_string(), Rec::Tomb(k) => format!("~{}", name(*k)),
            Rec::Audit { t, n } => format!("audit({}:{n})", ["A", "B"][*t as usize]) }).collect::<Vec<_>>().join(","),
            if r.text { "" } else { "*" })).collect();
        let act = match a {
            A::Commit(c) => format!("Commit C{c}"), A::Erase(t) => format!("Erase {}", ["A", "B"][*t as usize]),
            A::Bypass => "Bypass write a1".into(), A::Start(p, t) => format!("p{p} Start {}", ["A", "B"][*t as usize]),
            A::Scan(p) => format!("p{p} Scan"), A::Final(p) => format!("p{p} Final"), A::Stop(p) => format!("p{p} Stop"),
        };
        out += &format!("  {:>2}. {:<16} live={:?} marker={:?} recs={}\n", i + 1, act,
            s.live.iter().map(|k| name(*k)).collect::<Vec<_>>(), s.marker.map(|t| ["A", "B"][t as usize]), recs.join(" "));
    }
    out
}

/// The same machine, checking one action property only (so a violation of one does not hide the others).
pub struct Only { pub m: M, pub keep: &'static str }

impl Model for Only {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { self.m.init_states() }
    fn actions(&self, s: &S) -> Vec<A> { self.m.actions(s) }
    fn next(&self, s: &S, a: &A) -> Option<S> { self.m.next(s, a) }
    fn within_bounds(&self, s: &S) -> bool { self.m.within_bounds(s) }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        self.m.action_properties().into_iter().filter(|p| p.name == self.keep).collect()
    }
}
