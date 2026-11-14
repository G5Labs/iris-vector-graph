//! M3a, retry / post-commit properties / erasure / redaction / interrupted operations / restore of an older archive.
//!
//! World: tenant A's node a|1 in the default graph, created by changeset C with retry key k and a post-commit property
//! p on a|1; tenant B's changeset U (key u) moves the ledger on. Facts used (each read at the pin):
//! - post-commit properties are a separate direct write after the commit, outside the revision, with no foreign key on
//!   nodes (client.py:430-435, 445-487: DELETE then INSERT on rdf_props of the default graph);
//! - a retry with a bound key and the same fingerprint is answered as a replay (Ledger.cls:457-462) BEFORE the
//!   redaction's commit check (514-518), and the client applies post-commit properties after a replay too (no
//!   `replayed` test, client.py:430-435); a key moved to idemRedacted is refused (466-473);
//! - EraseNodes(D, a|) selects ids from Graph_KG.nodes (Eraser.cls:331-350), so a property row whose node row is gone
//!   is not erased (the live observation of F-1306);
//! - LiveRows of the default-graph prefix target counts rdf_props rows with the prefix in every graph (149-178);
//! - a replacing restore (snapshot.py:1139-1152, 1554-1588, 1679; Eraser.cls:806-812) keeps the live ^IVG.Ledger
//!   except ("stmt")/("tuple") and sets the archive's nodes over it: archived records overwrite tombstones, archived
//!   ("idem") bindings come back, live idemRedacted/redactedRev entries stay, the store becomes the archive's (F-1801).
//! The redaction here follows the reviewed marker protocol (marker set at a locked start) so that F-1302/F-1303 do not
//! mask the effects studied here; a run may be stopped and resumed (resume restarts the scan).
//!
//! Designs: `AsBuilt`; `Reviewed` = HD-1305 (a retry must not recreate an erased tenant's properties; a genuinely
//! incomplete first attempt keeps a recovery path: the property write is one conditional statement "only while the
//! node row exists", and its completion is recorded with it, so a replay applies it only when the first attempt did
//! not) and HD-1801 (a restore whose archive's ledger is not the live ledger is refused before anything changes).
use crate::util::Only;
use crate::{limits, summarize, Check, Expect, Res, CAP};
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Mutant {
    None,
    /// control: a replay applies the post-commit properties unconditionally (the pin's client)
    ReplayAppliesPcp,
    /// control: ClearRevision leaves the retry key bound
    KeepRetryKey,
    /// control: a restore overlays the archive's ledger (the pin's restore)
    RestoreOverlay,
    /// progress-only: a replay never applies post-commit properties, and there is no other recovery path
    NoPcpRecovery,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Rev { pub tenant_a: bool, pub tomb: bool, pub text: bool, pub key: u8 }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Ledger { pub revs: Vec<Rev>, pub idem: [u8; 2], pub idem_red: u8, pub red_rev: u8,
    /// reviewed: completion of C's post-commit properties, recorded with them (part of the ledger, so a restore sees it)
    pub pcp_done: bool }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Arch { pub led: Ledger, pub node: bool, pub prop: bool, pub b: bool }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub node: bool,
    pub prop: bool,
    /// tenant B's node row
    pub b: bool,
    pub led: Ledger,
    /// the client of C's first attempt still has to apply its post-commit properties
    pub client_pending: bool,
    pub marker: bool,
    /// None: no run; Some(i): the run's cursor
    pub run: Option<u8>,
    pub archive: Option<Arch>,
    // ghosts
    pub erased: bool,
    pub pending: bool,
    pub redacted_ever: u8,
    pub restores: u8,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum A { Commit, Pcp, Crash, Retry, CommitU, Erase, Start, Batch, Final, Stop, Save, Restore }

pub struct M3 { pub design: Design, pub mutant: Mutant, pub split_pcp: bool, pub restore: bool, pub retry: bool,
    /// erasure available (switched off to ask whether a crashed first attempt can be completed by retrying alone)
    pub erase: bool }

impl M3 {
    pub fn new(design: Design) -> M3 { M3 { design, mutant: Mutant::None, split_pcp: true, restore: true, retry: true, erase: true } }
    fn reviewed(&self) -> bool { self.design == Design::Reviewed }
    fn live(s: &S) -> bool { s.node || s.prop }
    /// The client's post-commit property write.
    fn pcp(&self, u: &mut S) {
        if self.reviewed() && self.mutant != Mutant::ReplayAppliesPcp {
            if u.node && !u.led.pcp_done { u.prop = true; u.led.pcp_done = true; }
        } else {
            u.prop = true; // DELETE + INSERT on rdf_props, no foreign key
        }
    }
}

impl Model for M3 {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { node: false, prop: false, b: false, led: Ledger { revs: vec![], idem: [0, 0], idem_red: 0, red_rev: 0, pcp_done: false },
                 client_pending: false, marker: false, run: None, archive: None, erased: false,
                 pending: false, redacted_ever: 0, restores: 0 }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![A::Commit, A::Retry, A::CommitU, A::Erase, A::Start, A::Batch, A::Final, A::Stop];
        if self.split_pcp { v.extend([A::Pcp, A::Crash]); }
        if self.restore { v.extend([A::Save, A::Restore]); }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        match a {
            A::Commit => {
                if s.led.idem[0] != 0 || s.led.idem_red & 1 != 0 || s.led.revs.iter().any(|r| r.tenant_a) { return None; }
                if s.node || s.marker { return None; } // node_exists / BlocksCommit
                u.node = true;
                u.led.revs.push(Rev { tenant_a: true, tomb: false, text: true, key: 1 });
                u.led.idem[0] = u.led.revs.len() as u8;
                u.erased = false;
                if self.split_pcp { u.client_pending = true; } else { self.pcp(&mut u); }
            }
            A::Pcp => {
                if !s.client_pending { return None; }
                u.client_pending = false;
                self.pcp(&mut u);
            }
            A::Crash => {
                if !s.client_pending { return None; }
                u.client_pending = false;
            }
            A::Retry => {
                // a retry of C: replayed while its key is bound (before the redaction's commit check)
                if !self.retry || s.led.idem[0] == 0 || s.client_pending { return None; }
                if self.mutant != Mutant::NoPcpRecovery { self.pcp(&mut u); }
            }
            A::CommitU => {
                if s.led.idem[1] != 0 || s.led.idem_red & 2 != 0 || s.b { return None; }
                u.b = true;
                u.led.revs.push(Rev { tenant_a: false, tomb: false, text: true, key: 2 });
                u.led.idem[1] = u.led.revs.len() as u8;
            }
            A::Erase => {
                // EraseNodes(D, a|): the ids come from the nodes table
                if !self.erase || !s.node { return None; }
                u.node = false;
                u.prop = false;
                u.erased = true;
                u.pending = true;
            }
            A::Start => {
                if s.run.is_some() || Self::live(s) { return None; } // target_live
                u.marker = true;
                u.run = Some(0);
            }
            A::Batch => {
                let i = s.run? as usize;
                if i >= s.led.revs.len() || !s.marker { return None; }
                let r = s.led.revs[i];
                if r.tenant_a && !r.tomb {
                    u.led.revs[i].tomb = true;
                    u.redacted_ever |= 1 << i;
                    if s.led.red_rev & (1 << i) == 0 {
                        u.led.revs[i].text = false;
                        if r.key != 0 && self.mutant != Mutant::KeepRetryKey {
                            u.led.idem[r.key as usize - 1] = 0;
                            u.led.idem_red |= 1 << (r.key - 1);
                            u.led.revs[i].key = 0;
                        }
                        u.led.red_rev |= 1 << i;
                    }
                }
                u.run = Some(i as u8 + 1);
            }
            A::Final => {
                let i = s.run? as usize;
                if i < s.led.revs.len() || !s.marker { return None; }
                u.run = None;
                if Self::live(s) { return Some(u); } // target_live: the marker stays
                u.marker = false;
                u.pending = false;
            }
            A::Stop => { s.run?; u.run = None; }
            A::Save => {
                if s.archive.is_some() || s.marker || s.client_pending { return None; }
                u.archive = Some(Arch { led: s.led.clone(), node: s.node, prop: s.prop, b: s.b });
            }
            A::Restore => {
                let ar = s.archive.clone()?;
                if s.restores >= 1 || s.marker || s.run.is_some() || s.client_pending { return None; }
                u.restores += 1;
                let overlay = !self.reviewed() || self.mutant == Mutant::RestoreOverlay;
                if !overlay && ar.led != s.led { return Some(u); } // refused before anything changes
                if overlay {
                    for (i, r) in ar.led.revs.iter().enumerate() { u.led.revs[i] = *r; }
                    for k in 0..2 { if ar.led.idem[k] != 0 { u.led.idem[k] = ar.led.idem[k]; } }
                    u.led.idem_red |= ar.led.idem_red;
                    u.led.red_rev |= ar.led.red_rev;
                }
                u.node = ar.node;
                u.prop = ar.prop;
                u.b = ar.b;
                u.erased = false; // an authorized restore may bring content back
                if Self::live(&u) { u.pending = false; }
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant("RPL-X: after an erasure only a recorded commit or an authorized restore makes the tenant's content live again",
                |s: &S| !(s.erased && (s.node || s.prop))),
            invariant("RED-B2/HD-1801: a redacted record never regains its content", |s: &S| {
                (0..s.led.revs.len()).all(|i| s.redacted_ever & (1 << i) == 0 || s.led.revs[i].tomb)
            }),
            invariant("INV-text: a revision with a tombstone keeps no free text and no retry key; redactedRev marks only such revisions",
                |s: &S| s.led.revs.iter().enumerate().all(|(i, r)| (!r.tomb || (!r.text && r.key == 0))
                    && (s.led.red_rev & (1 << i) == 0 || r.tomb))),
            invariant("INV-retry: a bound key names a revision with no tombstone; a redacted key is unbound", |s: &S| {
                (0..2).all(|k| { let r = s.led.idem[k];
                    (r == 0 || !s.led.revs[r as usize - 1].tomb) && (s.led.idem_red & (1 << k) == 0 || r == 0) })
            }),
            invariant("RPL-B3: once settled, replay equals the store (node identity, as read_canonical)", |s: &S| {
                if s.marker || s.run.is_some() || s.client_pending || s.pending { return true; }
                let replay_a = s.led.revs.iter().any(|r| r.tenant_a && !r.tomb);
                let replay_b = s.led.revs.iter().any(|r| !r.tenant_a && !r.tomb);
                replay_a == (s.node || s.prop) && replay_b == s.b
            }),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![
            invariant("the tenant's erasure can always be finished without touching tenant B (no marker, nothing pending)",
                |s: &S| !s.marker && s.run.is_none() && !s.pending),
            invariant("a live committed node can always get its post-commit property (HD-1305 recovery path)",
                |s: &S| !s.client_pending && (!s.node || s.prop)),
        ]
    }
}

pub fn show(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    for (i, (a, s)) in c.steps.iter().enumerate() {
        let recs: Vec<String> = s.led.revs.iter().enumerate().map(|(n, r)| format!("r{n}[{}{}]{}{}", if r.tomb { "~" } else { "" },
            if r.tenant_a { "a|1" } else { "b|1" }, if r.text { "" } else { "*" }, if r.key != 0 { format!(" key{}", ["k", "u"][r.key as usize - 1]) } else { String::new() })).collect();
        out += &format!("  {:>2}. {:<8} node a|1={} prop p={} b|1={} recs={} idem={:?} idemRedacted={:02b} marker={} run={:?} client_pending={} archive={}\n",
            i + 1, format!("{:?}", a), s.node, s.prop, s.b, recs.join(" "), s.led.idem, s.led.idem_red, s.marker, s.run,
            s.client_pending, s.archive.is_some());
    }
    out
}

fn run<M: Model<State = S, Action = A>>(m: M) -> Res { summarize(explore(&m, limits(CAP)), show, CAP) }

pub fn checks() -> Vec<Check> {
    let r1 = "RPL-X: after an erasure only a recorded commit or an authorized restore makes the tenant's content live again";
    let r2 = "RED-B2/HD-1801: a redacted record never regains its content";
    let r3 = "INV-text: a revision with a tombstone keeps no free text and no retry key; redactedRev marks only such revisions";
    let r4 = "INV-retry: a bound key names a revision with no tombstone; a redacted key is unbound";
    let r5 = "RPL-B3: once settled, replay equals the store (node identity, as read_canonical)";
    let ef1 = "the tenant's erasure can always be finished without touching tenant B (no marker, nothing pending)";
    let ef2 = "a live committed node can always get its post-commit property (HD-1305 recovery path)";
    let ab = |split: bool, restore: bool| { let mut m = M3::new(Design::AsBuilt); m.split_pcp = split; m.restore = restore; m };
    let mut v = vec![];
    v.push(Check { id: "m3-as-built-F1306", machine: "M3-retry", design: "as-built", expect: Expect::Violation(r1),
        what: "F-1306: a replayed retry re-applies post-commit properties after the erasure (first attempt atomic)",
        run: Box::new(move || run(Only::keep(ab(false, false), &[r1]))) });
    v.push(Check { id: "m3-as-built-pcp-race", machine: "M3-retry", design: "as-built", expect: Expect::Violation(r1),
        what: "same root cause (F-1101/F-1306): the first attempt's own post-commit write lands after an erasure of its node",
        run: Box::new(move || { let mut m = ab(true, false); m.retry = false; run(Only::keep(m, &[r1])) }) });
    v.push(Check { id: "m3-as-built-F1306-stuck", machine: "M3-retry", design: "as-built", expect: Expect::Violation(ef1),
        what: "F-1306 impact: the revived property outlives EraseNodes; the redaction is refused forever (short of erasing the default graph)",
        run: Box::new(move || run(Only::keep(ab(false, false), &[ef1]))) });
    v.push(Check { id: "m3-as-built-F1801", machine: "M3-retry", design: "as-built", expect: Expect::Violation(r2),
        what: "F-1801: restoring an archive older than a redaction puts the redacted record back",
        run: Box::new(move || run(Only::keep(ab(false, true), &[r2]))) });
    v.push(Check { id: "m3-as-built-F1801-marks", machine: "M3-retry", design: "as-built", expect: Expect::Violation(r3),
        what: "F-1801: after the restore redactedRev marks a revision with no tombstone (and its text and key are back)",
        run: Box::new(move || run(Only::keep(ab(false, true), &[r3]))) });
    v.push(Check { id: "m3-as-built-F1801-keys", machine: "M3-retry", design: "as-built", expect: Expect::Violation(r4),
        what: "F-1801: after the restore the retry key is both bound and in idemRedacted",
        run: Box::new(move || run(Only::keep(ab(false, true), &[r4]))) });
    v.push(Check { id: "m3-reviewed", machine: "M3-retry", design: "reviewed", expect: Expect::Pass,
        what: "HD-1305 + HD-1801 working answers: every property and both AG EF goals",
        run: Box::new(move || run(M3::new(Design::Reviewed))) });
    for (id, mu, prop, what) in [
        ("m3-control-replay-applies-pcp", Mutant::ReplayAppliesPcp, r1, "a replay applies post-commit properties unconditionally"),
        ("m3-control-keep-retry-key", Mutant::KeepRetryKey, r4, "ClearRevision leaves the retry key bound"),
        ("m3-control-restore-overlay", Mutant::RestoreOverlay, r2, "a restore overlays the archive's ledger"),
    ] {
        v.push(Check { id, machine: "M3-retry", design: "control", expect: Expect::Violation(prop), what,
            run: Box::new(move || { let mut m = M3::new(Design::Reviewed); m.mutant = mu; run(Only::keep(m, &[prop])) }) });
    }
    v.push(Check { id: "m3-progress-no-pcp-recovery-progress", machine: "M3-retry", design: "progress-mutant", expect: Expect::Violation(ef2),
        what: "the naive HD-1305 fix (a replay never applies post-commit properties): a crashed first attempt is never completed (erasure off)",
        run: Box::new(move || { let mut m = M3::new(Design::Reviewed); m.mutant = Mutant::NoPcpRecovery; m.erase = false; run(Only::keep(m, &[ef2])) }) });
    v.push(Check { id: "m3-reviewed-recovery", machine: "M3-retry", design: "reviewed", expect: Expect::Pass,
        what: "HD-1305 recovery path, with erasure switched off (it would otherwise reach the goal by removing the node)",
        run: Box::new(move || { let mut m = M3::new(Design::Reviewed); m.erase = false; run(m) }) });
    v.push(Check { id: "m3-progress-no-pcp-recovery-safety", machine: "M3-retry", design: "progress-mutant", expect: Expect::Pass,
        what: "the same mutant keeps every safety property and the erasure goal",
        run: Box::new(move || { let mut m = M3::new(Design::Reviewed); m.mutant = Mutant::NoPcpRecovery; run(Only::keep(m, &[r1, r2, r3, r4, r5, ef1])) }) });
    v.push(Check { id: "m3-sharp-restore-refused", machine: "M3-retry", design: "sharpness", expect: Expect::Violation("reach: a restore is refused after a redaction"),
        what: "witness (reviewed): a restore of an archive older than a redaction is refused",
        run: Box::new(move || run(Only::reach_step(M3::new(Design::Reviewed), "reach: a restore is refused after a redaction",
            |s, a, t| matches!(a, A::Restore) && t.led == s.led && s.led.red_rev != 0 && t.node == s.node))) });
    v.push(Check { id: "m3-sharp-retry-refused", machine: "M3-retry", design: "sharpness", expect: Expect::Violation("reach: the redacted key is in idemRedacted and the tenant is erased and redacted"),
        what: "witness (reviewed): erase, redact, the key moved to idemRedacted",
        run: Box::new(move || run(Only::reach_state(M3::new(Design::Reviewed), "reach: the redacted key is in idemRedacted and the tenant is erased and redacted",
            |s| s.led.idem_red & 1 != 0 && !s.pending && !s.marker && !s.node && !s.prop))) });
    v.push(Check { id: "m3-sharp-crash-recovered", machine: "M3-retry", design: "sharpness", expect: Expect::Violation("reach: a retry completes a crashed first attempt's property"),
        what: "witness (reviewed): a retry completes the property of a first attempt that crashed before writing it",
        run: Box::new(move || run(Only::reach_step(M3::new(Design::Reviewed), "reach: a retry completes a crashed first attempt's property",
            |s, a, t| matches!(a, A::Retry) && !s.prop && t.prop))) });
    v
}
