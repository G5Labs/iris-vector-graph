//! M3b, record readers and verify() against ledger writes, erasure and a redaction (F-1401, F-1402, HD-1401).
//!
//! World: node ids x, y. Ledger commits CX/CY create_node x/y (default graph, records with graph ""), CR create_rel
//! x->y in named graph G (create_rel + set_qual records with graph G; EnsureEndpoint registers x and y in G without a
//! record, LedgerApply.cls:97-110, 485-488), DX delete_node x mode=detach (LedgerApply.cls:374-416: the default graph's
//! node row and its default-graph incident edges only; G's row of x and G's edge stay; one delete_node record). A
//! ledger-bypassing write puts an unrecorded node z in the default graph. EraseGraph(G); a redaction of (G, -) in the
//! reviewed marker protocol (Start sets the marker and bumps an epoch; Batch tombstones one record; Final clears the
//! marker). Two readers that take no lock (P-1401): a record reader R (get_revision/diff/reconstruct/export:
//! client.py:687-739) and verify() V (replay.py:806-835): each checks the marker, then reads (V reads records and the
//! canonical tables as one cut, which is stronger than the pin; the race studied is the marker check).
//!
//! verify() at the pin compares nodes graph-blind (read_canonical, replay.py:588-606: every node row of every graph,
//! collapsed by id) while ledger node operations govern the default graph's row (R290). Reviewed (HD-1401 working
//! answer): compare the node identity the ledger operation governs (default-graph node rows; endpoint rows in named
//! graphs are implied by their edges), and readers re-check the marker and the redaction epoch after reading.
use crate::util::Only;
use crate::{limits, summarize, Check, Expect, Res, CAP};
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Mutant { None, /// control: the reviewed verify ignores nodes altogether
    VerifyIgnoresNodes, /// control: the reviewed reader re-checks the marker but not the epoch
    NoEpoch, /// progress-only: a reviewed reader whose redaction moved waits for the old epoch instead of refusing
    WaitForEpoch }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum K { NodeC(u8), NodeD(u8), Rel, Qual }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Rec { pub k: K, pub tomb: bool }

/// What a reader read: records (as tomb flags of the G records) and, for verify, its verdict.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Rd { Idle, Checked { epoch: u8 }, Read { epoch: u8, half: bool, verdict: Option<bool> } }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    /// default-graph node rows (bits x, y, z) and G's node rows (bits x, y)
    pub d_nodes: u8,
    pub g_nodes: u8,
    pub g_edge: bool,
    pub recs: Vec<Rec>,
    pub committed: u8,
    pub bypass: bool,
    pub marker: bool,
    pub epoch: u8,
    pub run: Option<u8>,
    pub r: Rd,
    pub v: Rd,
    /// ghost: G erased and not yet completely redacted
    pub pending: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum A { CX, CY, CR, DX, Bypass, EraseG, Start, Batch, Final, R1, R2, R3, V1, V2, V3 }

pub struct M { pub design: Design, pub mutant: Mutant }

impl S {
    fn g_live(&self) -> bool { self.g_nodes != 0 || self.g_edge }
    /// some but not all of G's records are tombstones
    pub fn half(&self) -> bool {
        let g: Vec<bool> = self.recs.iter().filter(|r| matches!(r.k, K::Rel | K::Qual)).map(|r| r.tomb).collect();
        g.iter().any(|t| *t) && g.iter().any(|t| !*t)
    }
    pub fn replay(&self) -> (u8, bool) {
        let mut n = 0u8;
        let mut e = false;
        for r in &self.recs {
            if r.tomb { continue; }
            match r.k { K::NodeC(i) => n |= 1 << i, K::NodeD(i) => n &= !(1 << i), K::Rel => e = true, K::Qual => {} }
        }
        (n, e)
    }
    /// verify() as the pin computes it: node ids of every graph, collapsed
    pub fn verdict_pin(&self) -> bool { let (n, e) = self.replay(); n == (self.d_nodes | self.g_nodes) && e == self.g_edge }
    /// the intended verdict (HD-1401 working answer): the default graph's node rows, which the ledger governs
    pub fn verdict_intended(&self) -> bool { let (n, e) = self.replay(); n == self.d_nodes && e == self.g_edge }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { d_nodes: 0, g_nodes: 0, g_edge: false, recs: vec![], committed: 0, bypass: false, marker: false, epoch: 0,
                 run: None, r: Rd::Idle, v: Rd::Idle, pending: false }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        use A::*;
        let mut v = vec![CX, CY, CR, DX, Bypass, EraseG, Start, Batch, Final, R1, R2, V1, V2];
        if self.design == Design::Reviewed { v.extend([R3, V3]); }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let once = |u: &mut S, bit: u8| -> Option<()> { if s.committed & bit != 0 { return None; } u.committed |= bit; Some(()) };
        let reviewed = self.design == Design::Reviewed;
        match a {
            A::CX | A::CY => {
                let i = if *a == A::CX { 0 } else { 1 };
                if (s.d_nodes | s.g_nodes) & (1 << i) != 0 { return None; } // node_exists, graph-blind
                once(&mut u, 1 << i)?;
                u.d_nodes |= 1 << i;
                u.recs.push(Rec { k: K::NodeC(i), tomb: false });
            }
            A::CR => {
                if (s.d_nodes | s.g_nodes) & 0b11 != 0b11 || s.g_edge || s.marker { return None; } // endpoints known; BlocksCommit
                once(&mut u, 4)?;
                u.g_nodes |= 0b11;
                u.g_edge = true;
                u.recs.push(Rec { k: K::Rel, tomb: false });
                u.recs.push(Rec { k: K::Qual, tomb: false });
            }
            A::DX => {
                if (s.d_nodes | s.g_nodes) & 1 == 0 { return None; }
                once(&mut u, 8)?;
                u.d_nodes &= !1; // the default graph's row only
                u.recs.push(Rec { k: K::NodeD(0), tomb: false });
            }
            A::Bypass => { if s.bypass { return None; } u.bypass = true; u.d_nodes |= 4; }
            A::EraseG => { if !s.g_live() { return None; } u.g_nodes = 0; u.g_edge = false; u.pending = true; }
            A::Start => {
                if s.run.is_some() || s.marker || s.g_live() || s.epoch >= 2 { return None; }
                u.marker = true;
                u.epoch += 1;
                u.run = Some(0);
            }
            A::Batch => {
                let i = s.run? as usize;
                if i >= s.recs.len() { return None; }
                if matches!(s.recs[i].k, K::Rel | K::Qual) { u.recs[i].tomb = true; }
                u.run = Some(i as u8 + 1);
            }
            A::Final => {
                let i = s.run? as usize;
                if i < s.recs.len() { return None; }
                u.run = None;
                if s.g_live() { return Some(u); }
                u.marker = false;
                u.pending = false;
            }
            A::R1 | A::V1 => {
                let rd = if *a == A::R1 { s.r } else { s.v };
                if rd != Rd::Idle || s.marker { return None; } // a marker: RedactionInProgressError / redaction_in_progress
                let nr = Rd::Checked { epoch: s.epoch };
                if *a == A::R1 { u.r = nr } else { u.v = nr }
            }
            A::R2 | A::V2 => {
                let rd = if *a == A::R2 { s.r } else { s.v };
                let Rd::Checked { epoch } = rd else { return None };
                let verdict = if *a == A::V2 {
                    Some(if !reviewed { s.verdict_pin() }
                         else if self.mutant == Mutant::VerifyIgnoresNodes { s.replay().1 == s.g_edge }
                         else { s.verdict_intended() })
                } else { None };
                let nr = Rd::Read { epoch, half: s.half(), verdict };
                // as built the view is accepted here; reviewed it waits for the re-check
                let nr = if reviewed { nr } else { Rd::Idle };
                if *a == A::R2 { u.r = nr } else { u.v = nr }
            }
            A::R3 | A::V3 => {
                let rd = if *a == A::R3 { s.r } else { s.v };
                let Rd::Read { epoch, .. } = rd else { return None };
                if self.mutant == Mutant::WaitForEpoch && (s.marker || s.epoch != epoch) { return None; }
                if *a == A::R3 { u.r = Rd::Idle } else { u.v = Rd::Idle }
            }
        }
        Some(u)
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        let design = self.design;
        let mutant = self.mutant;
        // the reader's answer is accepted at R2/V2 as built, at R3/V3 (if the marker and epoch did not move) reviewed
        let accepted = move |s: &S, a: &A| -> Option<(bool, Option<bool>)> {
            match (design, a) {
                (Design::AsBuilt, A::R2) | (Design::AsBuilt, A::V2) => {
                    let ver = if *a == A::V2 { Some(s.verdict_pin()) } else { None };
                    Some((s.half(), ver))
                }
                (Design::Reviewed, A::R3) | (Design::Reviewed, A::V3) => {
                    let rd = if *a == A::R3 { s.r } else { s.v };
                    let Rd::Read { epoch, half, verdict } = rd else { return None };
                    let moved = s.marker || (mutant != Mutant::NoEpoch && s.epoch != epoch);
                    if moved { None } else { Some((half, verdict)) }
                }
                _ => None,
            }
        };
        let acc2 = accepted.clone();
        vec![
            action_property("RPL-I1: an accepted reader view never shows a redaction half done", move |s: &S, a: &A, _t: &S| {
                accepted(s, a).map_or(true, |(half, _)| !half)
            }),
            action_property("RPL-B7/HD-1401: an accepted verify verdict is the intended one (governed node identity)",
                move |s: &S, a: &A, _t: &S| {
                    let Some((half, Some(v))) = acc2(s, a) else { return true };
                    // as built the verdict is computed at the read step itself (s), reviewed at the read (kept in Rd);
                    // the intended verdict is evaluated on the same cut, which for reviewed is the read's: re-derive
                    half || match design {
                        Design::AsBuilt => v == s.verdict_intended(),
                        Design::Reviewed => true, // checked by the reviewed variant below
                    }
                }),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("the readers can always finish", |s: &S| s.r == Rd::Idle && s.v == Rd::Idle)]
    }
}

/// The reviewed verify's verdict is fixed at its read; this wrapper checks it there against the intended one on that
/// same cut (an accepted verdict then needs only the unchanged-marker/epoch check above).
pub struct VerdictAtRead(pub M);
impl Model for VerdictAtRead {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { self.0.init_states() }
    fn actions(&self, s: &S) -> Vec<A> { self.0.actions(s) }
    fn next(&self, s: &S, a: &A) -> Option<S> { self.0.next(s, a) }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![action_property("RPL-B7/HD-1401: an accepted verify verdict is the intended one (governed node identity)",
            |s: &S, a: &A, t: &S| {
                if *a != A::V2 { return true; }
                match t.v { Rd::Read { half: false, verdict: Some(v), .. } => v == s.verdict_intended(), _ => true }
            })]
    }
}

pub fn show(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    let ids = ["x", "y", "z"];
    for (i, (a, s)) in c.steps.iter().enumerate() {
        let d: Vec<&str> = (0..3).filter(|b| s.d_nodes & (1 << b) != 0).map(|b| ids[b]).collect();
        let g: Vec<&str> = (0..2).filter(|b| s.g_nodes & (1 << b) != 0).map(|b| ids[b]).collect();
        let recs: Vec<String> = s.recs.iter().map(|r| format!("{}{}", if r.tomb { "~" } else { "" }, match r.k {
            K::NodeC(n) => format!("create_node {}", ids[n as usize]), K::NodeD(n) => format!("delete_node {}", ids[n as usize]),
            K::Rel => "create_rel G:x->y".into(), K::Qual => "set_qual G:x->y".into() })).collect();
        let (rn, re) = s.replay();
        out += &format!("  {:>2}. {:<6} D nodes={:?} G nodes={:?} G edge={} recs=[{}] marker={} epoch={} R={:?} V={:?} | replay nodes={:03b} edge={} verify(pin)={} verify(intended)={}\n",
            i + 1, format!("{:?}", a), d, g, s.g_edge, recs.join(", "), s.marker, s.epoch, s.r, s.v, rn, re,
            if s.verdict_pin() { "equal" } else { "diverges" }, if s.verdict_intended() { "equal" } else { "diverges" });
    }
    out
}

fn run<X: Model<State = S, Action = A>>(m: X) -> Res { summarize(explore(&m, limits(CAP)), show, CAP) }

pub fn checks() -> Vec<Check> {
    let half = "RPL-I1: an accepted reader view never shows a redaction half done";
    let verdict = "RPL-B7/HD-1401: an accepted verify verdict is the intended one (governed node identity)";
    let ef = "the readers can always finish";
    let mk = |design, mutant| M { design, mutant };
    let mut v = vec![];
    v.push(Check { id: "m3-readers-as-built-F1402", machine: "M3-readers", design: "as-built", expect: Expect::Violation(half),
        what: "F-1402: a reader checks the marker once, before reading; a redaction starts in between",
        run: Box::new(move || run(Only::keep(mk(Design::AsBuilt, Mutant::None), &[half]))) });
    v.push(Check { id: "m3-readers-as-built-F1401", machine: "M3-readers", design: "as-built", expect: Expect::Violation(verdict),
        what: "F-1401: verify compares node ids across graphs; a detach delete leaves G's row of the node",
        run: Box::new(move || run(Only::keep(mk(Design::AsBuilt, Mutant::None), &[verdict]))) });
    v.push(Check { id: "m3-readers-reviewed", machine: "M3-readers", design: "reviewed", expect: Expect::Pass,
        what: "HD-1401 working answer: re-check marker and epoch after reading; AG EF the readers finish",
        run: Box::new(move || run(Only::keep(mk(Design::Reviewed, Mutant::None), &[half, ef]))) });
    v.push(Check { id: "m3-readers-reviewed-verdict", machine: "M3-readers", design: "reviewed", expect: Expect::Pass,
        what: "HD-1401 working answer: verify compares the governed (default-graph) node identity",
        run: Box::new(move || run(VerdictAtRead(mk(Design::Reviewed, Mutant::None)))) });
    v.push(Check { id: "m3-readers-control-verify-ignores-nodes", machine: "M3-readers", design: "control", expect: Expect::Violation(verdict),
        what: "a verify that ignores nodes misses an unrecorded node write",
        run: Box::new(move || run(VerdictAtRead(mk(Design::Reviewed, Mutant::VerifyIgnoresNodes)))) });
    v.push(Check { id: "m3-readers-progress-wait-for-epoch-progress", machine: "M3-readers", design: "progress-mutant", expect: Expect::Violation(ef),
        what: "a reader that waits for its old epoch instead of refusing never finishes once a redaction starts",
        run: Box::new(move || run(Only::keep(mk(Design::Reviewed, Mutant::WaitForEpoch), &[ef]))) });
    v.push(Check { id: "m3-readers-progress-wait-for-epoch-safety", machine: "M3-readers", design: "progress-mutant", expect: Expect::Pass,
        what: "the same mutant keeps the reader safety property",
        run: Box::new(move || run(Only::keep(mk(Design::Reviewed, Mutant::WaitForEpoch), &[half]))) });
    v.push(Check { id: "m3-readers-sharp-epoch-refusal", machine: "M3-readers", design: "sharpness", expect: Expect::Violation("reach: a reviewed reader refuses because a whole redaction run passed"),
        what: "witness (reviewed): no marker at the re-check, but the epoch moved, so the view is refused",
        run: Box::new(move || run(Only::reach_step(mk(Design::Reviewed, Mutant::None), "reach: a reviewed reader refuses because a whole redaction run passed",
            |s, a, _| *a == A::R3 && !s.marker && matches!(s.r, Rd::Read { epoch, half: true, .. } if epoch != s.epoch)))) });
    v.push(Check { id: "m3-readers-control-no-epoch", machine: "M3-readers", design: "control", expect: Expect::Violation(half),
        what: "a reader that re-checks the marker but not the epoch accepts a view across a whole redaction run",
        run: Box::new(move || run(Only::keep(mk(Design::Reviewed, Mutant::NoEpoch), &[half]))) });
    v
}
