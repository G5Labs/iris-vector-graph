//! M1, targeting (sequential: every operation is one atomic step; no concurrency).
//!
//! The three redaction predicates of the pin, kept apart (the original machines used one predicate for all three):
//! - record match `Matches` (LedgerRedact.cls:89-112): the record's graph field (field 7) must equal the target graph;
//!   with no prefix every such record matches; node records match by id prefix; create_rel/delete_rel by the tuple's
//!   endpoints; qualifier records through ("redacting","stmt") entries, the PrePass map (116-141) or the live/closed
//!   ("stmt") row, else -1 = unattributed (counted, not tombstoned, 317-320);
//! - liveness `LiveRows` (149-178): a prefix target in the DEFAULT graph counts node rows with the prefix in EVERY graph
//!   and relationships with a prefixed end in the target graph only; an unprefixed target counts only the rows of the
//!   target graph; a named-graph prefix target counts the target graph's rows with the prefix;
//! - statement cleanup `DropStatements` (446-471): ("stmt") entries, live or closed, of the target graph with a
//!   prefixed endpoint, and the ("tuple") entry that points at each.
//! And the eraser's: `EraseGraph` (Eraser.cls:47-261: every row of the graph, then EraseLedgerFor 1117-1144: every
//! ("stmt") entry of the graph and its ("tuple") entry) and `EraseNodes` (322-351 + EraseIdSet 467-636: node rows of the
//! graph with the prefix, their incident edges in that graph, EraseEdgeRow 641-680 killing each edge's tuple and live
//! statement).
//!
//! Graph-blind provenance: ledger node records carry graph "" (LedgerApply.cls:215-251; genesis LedgerGenesis.cls:14-36
//! records every node row of every graph, one record per row) while node rows live in any graph (UNIQUE(graph_id,
//! node_id)); `NodeExists` is graph-blind (LedgerApply.cls:79-84); create_rel registers missing endpoints in the edge's
//! graph without a record (EnsureEndpoint, 97-110). Each node record keeps, as a ghost, the graph of the row it describes.
//!
//! World: default graph D and named graph G; node ids a|1 (tenant prefix a|), b|1 (prefix b|), n (unprefixed); edges
//! E0 = G:a|1->n, E1 = G:b|1->n, E2 = D:a|1->b|1 (spanning both tenants). Content written before enable() (genesis) and
//! by a ledger-bypassing writer after it; ledger commits (create_node, a spanning create of a|1 and b|1, create_rel,
//! delete_rel, set_qual); EraseGraph, EraseNodes; Redact(graph, prefix) as one call (liveness, PrePass, scan, Final).
//!
//! Designs: `AsBuilt`; `Reviewed` = the working assumptions of HD-1303 (an unprefixed default-graph target counts node
//! rows of every graph, i.e. it is refused unless no node lives in any graph) and HD-1304 (a graph-only target of a
//! named graph whose history still holds node records of erased ids it cannot attribute reports "incomplete").
use crate::util::Only;
use crate::{limits, summarize, Check, Expect, Res, CAP};
use explorer::*;

pub const ID: [&str; 3] = ["a|1", "b|1", "n"];
pub const GN: [&str; 2] = ["D", "G"];
/// (graph, source, target)
pub const EG: [(u8, u8, u8); 3] = [(1, 0, 2), (1, 1, 2), (0, 0, 1)];
pub const EN: [&str; 3] = ["E0 G:a|1->n", "E1 G:b|1->n", "E2 D:a|1->b|1"];
pub const PN: [&str; 3] = ["", "a|", "b|"];

pub fn pre(id: u8, p: u8) -> bool { (p == 1 && id == 0) || (p == 2 && id == 1) }
pub fn ends_have(e: u8, p: u8) -> bool { let (_, s, o) = EG[e as usize]; pre(s, p) || pre(o, p) }
pub fn tname(t: u8) -> String { format!("({}, {})", GN[(t / 3) as usize], if t % 3 == 0 { "-" } else { PN[(t % 3) as usize] }) }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Mutant {
    None,
    /// control: one liveness predicate for every target: a default-graph prefix target counts default-graph rows only
    LivenessCollapsed,
    /// control: a qualifier record of the target graph matches without resolving its statement's endpoints
    QualIgnoresEnds,
    /// control: unattributed records are not counted
    UnattributedUncounted,
    /// control: DropStatements ignores the graph
    DropStatementsAllGraphs,
    /// progress-only: a redaction never reports complete
    NeverComplete,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum K {
    /// graph field "" always; `origin` is the ghost graph of the row the record describes
    Node { id: u8, origin: u8 },
    Rel { e: u8, stmt: u8, del: bool },
    /// `e` is a ghost: the product resolves the statement id only
    Qual { e: u8, stmt: u8 },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct R { pub k: K, pub tomb: bool }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Receipt { pub t: u8, /// 0 refused (target_live), 1 complete, 2 incomplete
    pub outcome: u8, pub unattr: u32 }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S1 {
    pub enabled: bool,
    /// node rows, bit g*3+id
    pub nodes: u8,
    pub edges: u8,
    /// ("stmt", id) for id 1..=6: 0 absent, else 1 + 2*edge + closed
    pub stmt: [u8; 6],
    pub next: u8,
    pub tuple: [u8; 3],
    /// ghost: the live incarnation of the edge is saved by the ledger (it has a statement)
    pub saved: u8,
    pub revs: Vec<Vec<R>>,
    /// ghost: targets the documented procedure still has to redact
    pub pending: u8,
    pub bypass: bool,
    pub pre: u8,
    pub commits: u8,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum A1 {
    PreNode(u8, u8),
    PreEdge(u8),
    Enable,
    CNode(u8),
    CNodeAB,
    CRel(u8),
    CDel(u8),
    CQual(u8),
    Bypass(u8),
    EraseGraph(u8),
    EraseNodes(u8, u8),
    Redact(u8),
}

impl S1 {
    pub fn node(&self, g: u8, id: u8) -> bool { self.nodes & (1 << (g * 3 + id)) != 0 }
    pub fn id_live(&self, id: u8) -> bool { self.node(0, id) || self.node(1, id) }
    pub fn edge(&self, e: u8) -> bool { self.edges & (1 << e) != 0 }
    fn add_node(&mut self, g: u8, id: u8) { self.nodes |= 1 << (g * 3 + id); }
    pub fn stmt_of(v: u8) -> Option<(u8, bool)> { if v == 0 { None } else { Some(((v - 1) / 2, (v - 1) % 2 == 1)) } }
    /// the content a record describes is live (node records: the id in any graph, as verify() compares nodes)
    pub fn entity_live(&self, k: &K) -> bool {
        match *k { K::Node { id, .. } => self.id_live(id), K::Rel { e, .. } | K::Qual { e, .. } => self.edge(e) }
    }
    fn alloc(&mut self, e: u8) -> Option<u8> {
        if self.next > 6 { return None; }
        let id = self.next;
        self.next += 1;
        self.stmt[id as usize - 1] = 1 + 2 * e;
        self.tuple[e as usize] = id;
        Some(id)
    }
    /// the live statement of edge e through the tuple index, or a new one (ResolveRef's assigned_stmt path)
    fn stmt_for(&mut self, e: u8) -> Option<u8> {
        let id = self.tuple[e as usize];
        if id != 0 && self.stmt[id as usize - 1] == 1 + 2 * e { return Some(id); }
        self.alloc(e)
    }
    pub fn replay_nodes(&self) -> u8 {
        let mut m = 0;
        for r in self.revs.iter().flatten() { if let (K::Node { id, .. }, false) = (r.k, r.tomb) { m |= 1 << id; } }
        m
    }
    pub fn replay_edges(&self) -> u8 {
        let mut m = 0u8;
        for r in self.revs.iter().flatten() {
            if let (K::Rel { e, del, .. }, false) = (r.k, r.tomb) { if del { m &= !(1 << e) } else { m |= 1 << e } }
        }
        m
    }
    pub fn store_nodes(&self) -> u8 { (0..3u8).filter(|&i| self.id_live(i)).fold(0, |m, i| m | 1 << i) }
}

/// The documented reach of a target over records (ADR-0013, plan.md:9-10, client.py:651-656): relationship and qualifier
/// records of the target graph whose edge has a prefixed end (all of them with no prefix); node records only through
/// the default graph, by prefix (all node records for the unprefixed default-graph target).
pub fn in_reach(t: u8, k: &K) -> bool {
    let (g, p) = (t / 3, t % 3);
    match *k {
        K::Node { id, .. } => g == 0 && (p == 0 || pre(id, p)),
        K::Rel { e, .. } | K::Qual { e, .. } => EG[e as usize].0 == g && (p == 0 || ends_have(e, p)),
    }
}

/// The target's own content by provenance: what a complete redaction of it must leave no trace of (SC-001), for the
/// targets the documentation says reach it: relationship and qualifier records as `in_reach`; node records of a
/// default-graph prefix target by prefix (graph-blind, documented); node records of an unprefixed target whose row
/// lived in the target graph, for a named graph the unprefixed ids (spec 256: "tenant erasure is then EraseGraph plus
/// this redaction"); none for a named-graph prefix target (documented: its node records take the second target `redact(None, prefix)`).
pub fn in_scope(t: u8, k: &K) -> bool {
    let (g, p) = (t / 3, t % 3);
    match *k {
        // unprefixed target: the node rows that lived in its graph; for a named graph only unprefixed ids (a prefixed
        // tenant's node records take the documented second target redact(None, prefix))
        K::Node { id, origin } => if p == 0 { origin == g && (g == 0 || id == 2) } else { g == 0 && pre(id, p) },
        K::Rel { .. } | K::Qual { .. } => in_reach(t, k),
    }
}

/// Default bounds of M1 for the checks that expect a violation (breadth-first, they stop at the first one): content
/// written before enable() and ledger commits. Erasures and Redact calls are unbounded everywhere. Checks that must
/// explore everything run three profiles that partition the bound (PROFILES); (2 pre-writes, 2 commits) exceeded 8
/// million states without finishing and is not claimed.
pub const BOUND_PRE: u8 = 2;
pub const BOUND_COMMITS: u8 = 3;
pub const PROFILES: [(&str, u8, u8); 3] = [("a", 1, 2), ("b", 2, 1), ("c", 0, 3)];

pub struct M1 { pub design: Design, pub mutant: Mutant, pub max_pre: u8, pub max_commits: u8 }

impl M1 {
    pub fn new(design: Design) -> M1 { M1 { design, mutant: Mutant::None, max_pre: BOUND_PRE, max_commits: BOUND_COMMITS } }
    /// A bound profile (content written before enable(), ledger commits).
    pub fn prof(mut self, pre: u8, commits: u8) -> M1 { self.max_pre = pre; self.max_commits = commits; self }
    fn reviewed(&self) -> bool { self.design == Design::Reviewed }

    /// LiveRows (LedgerRedact.cls:149-178), and the reviewed variant.
    pub fn live_rows(&self, s: &S1, g: u8, p: u8) -> bool {
        let nodes_any_graph = (g == 0 && p != 0 && self.mutant != Mutant::LivenessCollapsed) || (g == 0 && p == 0 && self.reviewed());
        let node_live = (0..3u8).any(|id| (p == 0 || pre(id, p)) && if nodes_any_graph { s.id_live(id) } else { s.node(g, id) });
        let edge_live = (0..3u8).any(|e| s.edge(e) && EG[e as usize].0 == g && (p == 0 || ends_have(e, p)));
        node_live || edge_live
    }

    /// Matches (LedgerRedact.cls:89-112): 1, 0 or -1 (unattributed).
    fn matches(&self, s: &S1, r: &R, g: u8, p: u8, red: u8, pp: &[u8; 7]) -> i8 {
        if r.tomb { return 0; }
        let gf = match r.k { K::Node { .. } => 0, K::Rel { e, .. } | K::Qual { e, .. } => EG[e as usize].0 };
        if gf != g { return 0; }
        if p == 0 { return 1; }
        match r.k {
            K::Node { id, .. } => pre(id, p) as i8,
            K::Rel { e, .. } => ends_have(e, p) as i8,
            K::Qual { stmt, .. } => {
                if self.mutant == Mutant::QualIgnoresEnds { return 1; }
                if red & (1 << stmt) != 0 { return 1; }
                let ee = if pp[stmt as usize] != 0 { pp[stmt as usize] - 1 } else {
                    match S1::stmt_of(s.stmt[stmt as usize - 1]) { Some((e2, _)) => e2, None => return -1 }
                };
                ends_have(ee, p) as i8
            }
        }
    }

    /// One Redact call: the next state and its receipt (the receipt is not kept in the state; properties recompute it
    /// from the pre-state, which is exact since the call is deterministic).
    pub fn redact(&self, s: &S1, t: u8) -> (S1, Receipt) {
        let (g, p) = (t / 3, t % 3);
        let mut u = s.clone();
        if self.live_rows(s, g, p) {
            return (u, Receipt { t, outcome: 0, unattr: 0 });
        }
        // PrePass (prefix targets): statement endpoints from the create_rel/delete_rel records of the target graph
        let mut pp = [0u8; 7];
        if p != 0 {
            for r in s.revs.iter().flatten() {
                if let (K::Rel { e, stmt, .. }, false) = (r.k, r.tomb) { if EG[e as usize].0 == g { pp[stmt as usize] = e + 1; } }
            }
        }
        let mut red = 0u8;
        let mut unattr = 0u32;
        let mut pos = 0;
        for i in 0..u.revs.len() {
            for j in 0..u.revs[i].len() {
                let r = u.revs[i][j];
                match self.matches(&u, &r, g, p, red, &pp) {
                    x if x < 0 => { if self.mutant != Mutant::UnattributedUncounted { unattr |= 1 << pos; } }
                    0 => {}
                    _ => {
                        u.revs[i][j].tomb = true;
                        if let K::Rel { stmt, .. } = r.k { red |= 1 << stmt; }
                    }
                }
                pos += 1;
            }
        }
        // Final: the liveness re-check sees what the opening check saw (no concurrency here); DropStatements
        for id in 1..=6u8 {
            if let Some((e, _)) = S1::stmt_of(u.stmt[id as usize - 1]) {
                let graph_ok = EG[e as usize].0 == g || self.mutant == Mutant::DropStatementsAllGraphs;
                if graph_ok && (p == 0 || ends_have(e, p)) {
                    u.stmt[id as usize - 1] = 0;
                    if u.tuple[e as usize] == id { u.tuple[e as usize] = 0; }
                }
            }
        }
        let unowned_nodes = u.revs.iter().flatten().any(|r| matches!(r.k, K::Node { id, .. } if !r.tomb && !u.id_live(id)));
        let outcome = if self.mutant == Mutant::NeverComplete { 2 }
                      else if self.reviewed() && g == 1 && p == 0 && unowned_nodes { 2 } else { 1 };
        if outcome == 1 { u.pending &= !(1 << t); }
        (u, Receipt { t, outcome, unattr })
    }
}

impl Model for M1 {
    type State = S1;
    type Action = A1;

    fn init_states(&self) -> Vec<S1> {
        vec![S1 { enabled: false, nodes: 0, edges: 0, stmt: [0; 6], next: 1, tuple: [0; 3], saved: 0, revs: vec![],
                  pending: 0, bypass: false, pre: 0, commits: 0 }]
    }

    fn actions(&self, _: &S1) -> Vec<A1> {
        let mut v = vec![A1::Enable, A1::CNodeAB];
        for g in 0..2 { for id in 0..3 { v.push(A1::PreNode(g, id)); } }
        for e in 0..3 { v.extend([A1::PreEdge(e), A1::CRel(e), A1::CDel(e), A1::CQual(e), A1::Bypass(e)]); }
        for id in 0..3 { v.push(A1::CNode(id)); }
        for g in 0..2 { v.extend([A1::EraseGraph(g), A1::EraseNodes(g, 1), A1::EraseNodes(g, 2)]); }
        for t in 0..6 { v.push(A1::Redact(t)); }
        v
    }

    fn next(&self, s: &S1, a: &A1) -> Option<S1> {
        let mut u = s.clone();
        let commit = |u: &mut S1, recs: Vec<R>| { u.revs.push(recs); u.commits += 1; };
        match *a {
            A1::PreNode(g, id) => {
                if s.enabled || s.pre >= self.max_pre || s.node(g, id) { return None; }
                u.add_node(g, id);
                u.pre += 1;
            }
            A1::PreEdge(e) => {
                if s.enabled || s.pre >= self.max_pre || s.edge(e) { return None; }
                let (g, so, o) = EG[e as usize];
                u.add_node(g, so);
                u.add_node(g, o);
                u.edges |= 1 << e;
                u.pre += 1;
            }
            A1::Enable => {
                if s.enabled { return None; }
                u.enabled = true;
                let mut recs = vec![];
                for id in 0..3u8 { for g in 0..2u8 { if s.node(g, id) { recs.push(R { k: K::Node { id, origin: g }, tomb: false }); } } }
                for e in [2u8, 0, 1] { // ORDER BY s, p, o_id, graph_id: a|1->b|1 (D), a|1->n (G), b|1->n (G)
                    if s.edge(e) {
                        let id = u.alloc(e)?;
                        u.saved |= 1 << e;
                        recs.push(R { k: K::Rel { e, stmt: id, del: false }, tomb: false });
                    }
                }
                if !recs.is_empty() { u.revs.push(recs); }
            }
            A1::CNode(id) => {
                if !s.enabled || s.commits >= self.max_commits || s.id_live(id) { return None; } // node_exists (graph-blind)
                u.add_node(0, id);
                commit(&mut u, vec![R { k: K::Node { id, origin: 0 }, tomb: false }]);
            }
            A1::CNodeAB => {
                if !s.enabled || s.commits >= self.max_commits || s.id_live(0) || s.id_live(1) { return None; }
                u.add_node(0, 0);
                u.add_node(0, 1);
                commit(&mut u, vec![R { k: K::Node { id: 0, origin: 0 }, tomb: false }, R { k: K::Node { id: 1, origin: 0 }, tomb: false }]);
            }
            A1::CRel(e) => {
                let (g, so, o) = EG[e as usize];
                if !s.enabled || s.commits >= self.max_commits || s.edge(e) || !s.id_live(so) || !s.id_live(o) { return None; }
                u.add_node(g, so); // EnsureEndpoint: no record
                u.add_node(g, o);
                u.edges |= 1 << e;
                let id = u.alloc(e)?;
                u.saved |= 1 << e;
                commit(&mut u, vec![R { k: K::Rel { e, stmt: id, del: false }, tomb: false }]);
            }
            A1::CDel(e) => {
                if !s.enabled || s.commits >= self.max_commits || !s.edge(e) { return None; }
                let id = u.stmt_for(e)?;
                u.stmt[id as usize - 1] = 1 + 2 * e + 1;
                u.tuple[e as usize] = 0;
                u.edges &= !(1 << e);
                u.saved &= !(1 << e);
                commit(&mut u, vec![R { k: K::Rel { e, stmt: id, del: true }, tomb: false }]);
            }
            A1::CQual(e) => {
                if !s.enabled || s.commits >= self.max_commits || !s.edge(e) { return None; }
                let id = u.stmt_for(e)?;
                u.saved |= 1 << e;
                commit(&mut u, vec![R { k: K::Qual { e, stmt: id }, tomb: false }]);
            }
            A1::Bypass(e) => {
                if !s.enabled || s.bypass || s.edge(e) { return None; }
                let (g, so, o) = EG[e as usize];
                u.add_node(g, so);
                u.add_node(g, o);
                u.edges |= 1 << e;
                u.saved &= !(1 << e);
                u.bypass = true;
            }
            A1::EraseGraph(g) => {
                if !s.enabled { return None; }
                for id in 0..3u8 {
                    if s.node(g, id) && g == 1 && id < 2 { u.pending |= 1 << (id + 1); } // redact(None, prefix) as documented
                }
                u.nodes &= !(0b111 << (g * 3));
                for e in 0..3u8 { if EG[e as usize].0 == g { u.edges &= !(1 << e); u.saved &= !(1 << e); } }
                for id in 1..=6u8 {
                    if let Some((e, _)) = S1::stmt_of(s.stmt[id as usize - 1]) {
                        if EG[e as usize].0 == g { u.stmt[id as usize - 1] = 0; u.tuple[e as usize] = 0; }
                    }
                }
                u.pending |= 1 << (g * 3);
            }
            A1::EraseNodes(g, p) => {
                if !s.enabled { return None; }
                let ids: Vec<u8> = (0..3u8).filter(|&id| s.node(g, id) && pre(id, p)).collect();
                for e in 0..3u8 {
                    let (eg, so, o) = EG[e as usize];
                    if eg == g && s.edge(e) && (ids.contains(&so) || ids.contains(&o)) {
                        u.edges &= !(1 << e);
                        u.saved &= !(1 << e);
                        let id = u.tuple[e as usize];
                        if id != 0 { u.stmt[id as usize - 1] = 0; }
                        u.tuple[e as usize] = 0;
                    }
                }
                for id in ids { u.nodes &= !(1 << (g * 3 + id)); }
                u.pending |= 1 << (g * 3 + p);
                if g == 1 { u.pending |= 1 << p; }
            }
            A1::Redact(t) => {
                if !s.enabled { return None; }
                u = self.redact(s, t).0;
            }
        }
        Some(u)
    }

    fn invariants(&self) -> Vec<Invariant<S1>> {
        vec![
            invariant("RPL-B3: with no unrecorded write and every erased target redacted, replay equals the store", |s: &S1| {
                if !s.enabled || s.bypass || s.pending != 0 { return true; }
                s.replay_nodes() == s.store_nodes() && s.replay_edges() == s.edges
            }),
            invariant("ERS-I2/I3: live statement entries are exactly the live saved edges", |s: &S1| {
                let edges_ok = (0..3u8).all(|e| {
                    let id = s.tuple[e as usize];
                    let has = id != 0 && s.stmt[id as usize - 1] == 1 + 2 * e;
                    has == (s.edge(e) && s.saved & (1 << e) != 0)
                });
                let stmts_ok = (1..=6u8).all(|id| match S1::stmt_of(s.stmt[id as usize - 1]) {
                    Some((e, false)) => s.tuple[e as usize] == id && s.edge(e) && s.saved & (1 << e) != 0,
                    _ => true,
                });
                edges_ok && stmts_ok
            }),
        ]
    }

    fn action_properties(&self) -> Vec<ActionProperty<S1, A1>> {
        let me = M1 { design: self.design, mutant: self.mutant, max_pre: self.max_pre, max_commits: self.max_commits };
        fn changed(s: &S1, t: &S1) -> Vec<(R, R)> {
            s.revs.iter().flatten().zip(t.revs.iter().flatten()).filter(|(a, b)| a != b).map(|(a, b)| (*a, *b)).collect()
        }
        vec![
            action_property("RED-B1.1/RED-X2: no tombstone of content live in any graph", |s: &S1, a: &A1, t: &S1| {
                if !matches!(a, A1::Redact(_)) { return true; }
                changed(s, t).iter().all(|(x, _)| !s.entity_live(&x.k))
            }),
            action_property("RED-B12/SC-001: a complete redaction leaves no dead content of its target, except records it counts as unattributed",
                move |s: &S1, a: &A1, t: &S1| {
                    let A1::Redact(tg) = *a else { return true };
                    let rc = me.redact(s, tg).1;
                    if rc.outcome != 1 { return true; }
                    t.revs.iter().flatten().enumerate().all(|(pos, r)| {
                        r.tomb || !in_scope(tg, &r.k) || t.entity_live(&r.k) || rc.unattr & (1 << pos) != 0
                    })
                }),
            action_property("RED-I1/I2: only records in the target's documented reach change, each into its own tombstone",
                |s: &S1, a: &A1, t: &S1| {
                    let A1::Redact(tg) = *a else { return true };
                    t.revs.len() == s.revs.len()
                        && changed(s, t).iter().all(|(x, y)| in_reach(tg, &x.k) && !x.tomb && y.tomb && x.k == y.k)
                }),
        ]
    }

    fn always_possibly(&self) -> Vec<Invariant<S1>> {
        vec![invariant("every erased target can still be completely redacted", |s: &S1| s.pending == 0)]
    }
}

pub fn act(a: &A1) -> String {
    match *a {
        A1::PreNode(g, id) => format!("pre-enable write node {} in {}", ID[id as usize], GN[g as usize]),
        A1::PreEdge(e) => format!("pre-enable write edge {} (implicit endpoints)", EN[e as usize]),
        A1::Enable => "enable() (genesis)".into(),
        A1::CNode(id) => format!("commit create_node {}", ID[id as usize]),
        A1::CNodeAB => "commit create_node a|1 + b|1 (spanning)".into(),
        A1::CRel(e) => format!("commit create_rel {}", EN[e as usize]),
        A1::CDel(e) => format!("commit delete_rel {}", EN[e as usize]),
        A1::CQual(e) => format!("commit set_qual {}", EN[e as usize]),
        A1::Bypass(e) => format!("bypass write edge {}", EN[e as usize]),
        A1::EraseGraph(g) => format!("EraseGraph({})", GN[g as usize]),
        A1::EraseNodes(g, p) => format!("EraseNodes({}, {})", GN[g as usize], PN[p as usize]),
        A1::Redact(t) => format!("Redact{}", tname(t)),
    }
}

pub fn brief(s: &S1) -> String {
    let nodes: Vec<String> = (0..2u8).flat_map(|g| (0..3u8).filter(move |&id| s.node(g, id)).map(move |id| format!("{}:{}", GN[g as usize], ID[id as usize]))).collect();
    let edges: Vec<&str> = (0..3u8).filter(|&e| s.edge(e)).map(|e| EN[e as usize]).collect();
    let recs: Vec<String> = s.revs.iter().enumerate().map(|(n, r)| format!("r{n}[{}]", r.iter().map(|x| {
        let b = match x.k {
            K::Node { id, origin } => format!("node {} (row in {})", ID[id as usize], GN[origin as usize]),
            K::Rel { e, stmt, del } => format!("{}rel s{stmt} {}", if del { "delete_" } else { "create_" }, &EN[e as usize][..2]),
            K::Qual { e, stmt } => format!("qual s{stmt} ({})", &EN[e as usize][..2]),
        };
        if x.tomb { format!("~{b}") } else { b }
    }).collect::<Vec<_>>().join(", "))).collect();
    let stm: Vec<String> = (1..=6u8).filter_map(|id| S1::stmt_of(s.stmt[id as usize - 1]).map(|(e, c)| format!("s{id}:{}{}", &EN[e as usize][..2], if c { "(closed)" } else { "" }))).collect();
    format!("nodes={:?} edges={:?} stmt=[{}] recs={} pending={:?}", nodes, edges, stm.join(" "), recs.join(" "),
            (0..6u8).filter(|t| s.pending & (1 << t) != 0).map(tname).collect::<Vec<_>>())
}

thread_local! {
    /// The machine whose receipts a trace shows (set by `run` before exploring).
    pub static SHOWN: std::cell::Cell<(Design, Mutant)> = std::cell::Cell::new((Design::AsBuilt, Mutant::None));
}

pub fn show(c: &Counterexample<S1, A1>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    let (design, mutant) = SHOWN.with(|c| c.get());
    let m = M1 { design, mutant, max_pre: 0, max_commits: 0 };
    let mut prev = c.init.clone();
    for (i, (a, s)) in c.steps.iter().enumerate() {
        let rc = if let A1::Redact(t) = *a {
            let r = m.redact(&prev, t).1;
            format!(" receipt={}{}", ["refused target_live", "complete", "incomplete"][r.outcome as usize],
                    if r.unattr != 0 { format!(" unattributed={}", r.unattr.count_ones()) } else { String::new() })
        } else { String::new() };
        out += &format!("  {:>2}. {:<40} {}{}\n", i + 1, act(a), brief(s), rc);
        prev = s.clone();
    }
    out
}

fn run(m: Only<M1>) -> Res {
    SHOWN.with(|c| c.set((m.m.design, m.m.mutant)));
    summarize(explore(&m, limits(CAP)), show, CAP)
}
fn whole(m: M1) -> Only<M1> { Only::keep(m, &[]) }

pub fn checks() -> Vec<Check> {
    let p1 = "RED-B1.1/RED-X2: no tombstone of content live in any graph";
    let p2 = "RED-B12/SC-001: a complete redaction leaves no dead content of its target, except records it counts as unattributed";
    let p3 = "RED-I1/I2: only records in the target's documented reach change, each into its own tombstone";
    let p4 = "RPL-B3: with no unrecorded write and every erased target redacted, replay equals the store";
    let p5 = "ERS-I2/I3: live statement entries are exactly the live saved edges";
    let ef = "every erased target can still be completely redacted";
    let mut v = vec![];
    v.push(Check { id: "m1-as-built-F1304", machine: "M1", design: "as-built", expect: Expect::Violation(p1),
        what: "F-1304: the unprefixed default-graph target counts default-graph rows only but matches every node record",
        run: Box::new(move || run(Only::keep(M1::new(Design::AsBuilt), &[p1]))) });
    v.push(Check { id: "m1-as-built-F1305", machine: "M1", design: "as-built", expect: Expect::Violation(p2),
        what: "F-1305: a graph-only target cannot reach the graph-blind node records of its graph's rows, and reports complete",
        run: Box::new(move || run(Only::keep(M1::new(Design::AsBuilt), &[p2]))) });
    v.push(Check { id: "m1-as-built-replay", machine: "M1", design: "as-built", expect: Expect::Violation(p4),
        what: "RPL-B3 fails at the pin (F-1304 or F-1305: verify diverges after the documented procedure)",
        run: Box::new(move || run(Only::keep(M1::new(Design::AsBuilt), &[p4]))) });
    for (pf, pre, com) in PROFILES {
        v.push(Check { id: Box::leak(format!("m1-as-built-isolation-stmt-{pf}").into_boxed_str()), machine: "M1", design: "as-built", expect: Expect::Pass,
            what: Box::leak(format!("at the pin, sequentially: isolation (RED-I1/I2), the statement maps (ERS-I2/I3) and AG EF hold (profile {pf}: {pre} pre-enable writes, {com} commits)").into_boxed_str()),
            run: Box::new(move || run(Only::keep(M1::new(Design::AsBuilt).prof(pre, com), &[p3, p5, ef]))) });
        v.push(Check { id: Box::leak(format!("m1-reviewed-{pf}").into_boxed_str()), machine: "M1", design: "reviewed", expect: Expect::Pass,
            what: Box::leak(format!("HD-1303 + HD-1304 working assumptions: every property and AG EF (profile {pf}: {pre} pre-enable writes, {com} commits)").into_boxed_str()),
            run: Box::new(move || run(whole(M1::new(Design::Reviewed).prof(pre, com)))) });
    }
    v.push(Check { id: "m1-sc001-strict", machine: "M1", design: "as-built", expect: Expect::Violation("SC-001 strict: a complete redaction leaves no dead content of its target"),
        what: "documented exception: with the unattributed exception removed, SC-001's zero bar fails (qualifier records of unrecorded edges)",
        run: Box::new(move || run(Only::reach_step(M1::new(Design::Reviewed), "SC-001 strict: a complete redaction leaves no dead content of its target",
            |s, a, t| { let A1::Redact(tg) = *a else { return false };
                M1::new(Design::Reviewed).redact(s, tg).1.outcome == 1 && t.revs.iter().flatten().any(|r| !r.tomb && in_scope(tg, &r.k) && !t.entity_live(&r.k)) }))) });
    for (id, mu, prop, what) in [
        ("m1-control-liveness-collapsed", Mutant::LivenessCollapsed, p1, "one liveness predicate: a default-graph prefix target counts default-graph rows only"),
        ("m1-control-qual-ignores-ends", Mutant::QualIgnoresEnds, p3, "qualifier records match by graph without their statement's endpoints"),
        ("m1-control-unattributed-uncounted", Mutant::UnattributedUncounted, p2, "unattributed records are not counted"),
        ("m1-control-dropstatements-all-graphs", Mutant::DropStatementsAllGraphs, p5, "DropStatements ignores the graph"),
    ] {
        v.push(Check { id, machine: "M1", design: "control", expect: Expect::Violation(prop), what,
            run: Box::new(move || { let mut m = M1::new(Design::Reviewed); m.mutant = mu; run(Only::keep(m, &[prop])) }) });
    }
    v.push(Check { id: "m1-progress-never-complete-progress", machine: "M1", design: "progress-mutant", expect: Expect::Violation(ef),
        what: "a redaction never reports complete: AG EF fails (profile a)", run: Box::new(move || {
            let mut m = M1::new(Design::Reviewed).prof(1, 2); m.mutant = Mutant::NeverComplete; run(Only::keep(m, &[ef])) }) });
    v.push(Check { id: "m1-progress-never-complete-safety", machine: "M1", design: "progress-mutant", expect: Expect::Pass,
        what: "the same mutant keeps every safety property (profile a)", run: Box::new(move || {
            let mut m = M1::new(Design::Reviewed).prof(1, 2); m.mutant = Mutant::NeverComplete; run(Only::keep(m, &[p1, p2, p3, p4, p5])) }) });
    let rv = || M1::new(Design::Reviewed);
    v.push(Check { id: "m1-sharp-unattributed", machine: "M1", design: "sharpness", expect: Expect::Violation("reach: a complete redaction counts an unattributed record"),
        what: "witness: an unattributed qualifier record is counted",
        run: Box::new(move || run(Only::reach_step(rv(), "reach: a complete redaction counts an unattributed record",
            |s, a, _| matches!(*a, A1::Redact(t) if { let r = M1::new(Design::Reviewed).redact(s, t).1; r.outcome == 1 && r.unattr != 0 })))) });
    v.push(Check { id: "m1-sharp-incomplete", machine: "M1", design: "sharpness", expect: Expect::Violation("reach: a graph-only target reports incomplete"),
        what: "witness (reviewed): a graph-only target with graph-blind node history reports incomplete",
        run: Box::new(move || run(Only::reach_step(rv(), "reach: a graph-only target reports incomplete",
            |s, a, _| matches!(*a, A1::Redact(t) if M1::new(Design::Reviewed).redact(s, t).1.outcome == 2)))) });
    v.push(Check { id: "m1-sharp-refused-other-graph", machine: "M1", design: "sharpness", expect: Expect::Violation("reach: a default-graph target is refused for a node living only in G"),
        what: "witness (reviewed): Redact(D, -) refused because a node lives in G only",
        run: Box::new(move || run(Only::reach_step(rv(), "reach: a default-graph target is refused for a node living only in G",
            |s, a, _| matches!(*a, A1::Redact(0)) && M1::new(Design::Reviewed).redact(s, 0).1.outcome == 0
                && (0..3u8).any(|id| s.node(1, id)) && (0..3u8).all(|id| !s.node(0, id)) && s.edges & 0b100 == 0))) });
    v.push(Check { id: "m1-sharp-tenant-cycle", machine: "M1", design: "sharpness", expect: Expect::Violation("reach: a prefixed tenant with an edge in G is erased and redacted by its two targets"),
        what: "witness (reviewed): E0 and a|1 erased in G and D, then (G,a|) and (D,a|) complete with nothing pending",
        run: Box::new(move || run(Only::reach_state(rv(), "reach: a prefixed tenant with an edge in G is erased and redacted by its two targets",
            |s| s.pending == 0 && !s.id_live(0) && s.revs.iter().flatten().any(|r| matches!(r.k, K::Rel { e: 0, .. }) && r.tomb)
                && s.revs.iter().flatten().any(|r| matches!(r.k, K::Node { id: 0, .. }) && r.tomb)
                && s.revs.iter().flatten().any(|r| !r.tomb)))) });
    v
}
