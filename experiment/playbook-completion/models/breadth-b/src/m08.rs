//! Module 08 (Cypher on the SQL path) models at pin 3eaa79cf.
//!
//! Three small machines over the abstracted real state. Every check states its design and expectation; see
//! `checks()` for the list and the statements / findings each one covers.
//!
//! 1. `txn` — one Cypher write query as IVG's own transaction level (`_execute_cypher_write`,
//!    iris_vector_graph/_engine/query.py:1946-1966; `write_txn`, iris_vector_graph/_write_txn.py; Graph.KG.Txn
//!    Begin/End/Undo = TSTART / TCOMMIT / TROLLBACK 1, iris_src/src/Graph/KG/Txn.cls:19-58), nested in an optional
//!    caller transaction. Abstract rows: the caller's own earlier row `W`, the query's node row `C` and its edge row
//!    `E` between literal endpoints (translator.py:10212-10248 emits `INSERT ... VALUES` with no NOT EXISTS guard; the
//!    matched-endpoint path at 10306-10365 is guarded); `E` may already exist (environment freedom). A stepped write
//!    (count-only CREATE pipeline, query.py:1969-1990) runs a read step after a write step; the read step may fail with
//!    a SQL error (live: `1/0` in a MATCH map, SQLCODE -149), and `_raise_if_step_failed(res, wrote=True)`
//!    (query.py:1692-1705) words the error "the rows of the steps before it are written".
//!    Invariants: CYP-I6.4 / CYP-X6.5 (a failed query leaves none of its rows), CYP-I6.3 (a failed query keeps the
//!    caller's earlier work), F-0806 (the error text's claim matches the outcome), CYP-B6.7.6/7 + KNOWN_ISSUES.md:25-31
//!    (creating an existing edge between literal endpoints adds nothing and does not fail the query, F-0805).
//!    AG EF: the transaction level can always return to the caller's (progress of the write).
//! 2. `scope` — graph scope of reads over three graphs (default D, named A and B) sharing node ids x, m, l, with five
//!    candidate edges toggled by writes. Each read route computes its answer as built, and the per-graph truth; the
//!    invariant is SYS-I2 / CYP-I5.5 / CYP-I5.6 / CYP-I4.14: an answer about graph g holds only g's data. Routes:
//!    VLP with a WITH-carried start (`gall = 1`, translator.py:15404-15431, F-0818), HLL approx_count_distinct over the
//!    graph-blind ^NKG (query.py:4361-4421, F-0819), the count-UNION text shortcut (query.py:1841-1856, F-0802), db.labels
//!    (engine.py:1313-1318, F-0816), kg_GRAPH_PATH with no graph (algorithms.py:679-697, F-0820), a dotted function name
//!    pasting SQL (parser.py:1627-1640, translator.py:29563-29578, F-0815) and a mapped label (HD-0802, translator.py:404,
//!    719-779; reviewed contract assumed: graph-aware mapping provenance).
//! 3. `readonly` — read-only mode (execute_cypher(read_only=True), query.py:1794-1800 judges `writes_cypher` on the
//!    text; execute_aql has no read_only, query.py:1730-1745). Invariant CYP-I8.6: a call made in read-only mode
//!    changes no data and opens no transaction level. As built, a dotted function can call Graph_KG.Txn_Begin (live:
//!    $TLEVEL 0 -> 1 under read_only=True) and an AQL collection name can carry a SET (live: rows written) (F-0815,
//!    F-0814).
use breadth_b::*;
use explorer::*;

const M: &str = "08";

// ------------------------------------------------------------------------------------------------ 1. txn
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum TxnDesign { AsBuilt, Reviewed, RollbackAll, CommitPerStep, LeakLevel }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Variant { LiteralEdge, Stepped }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Pc { Idle, Running { v: Variant, step: u8 }, DoneOk(Variant), DoneErr { v: Variant, dup: bool, claims_kept: bool } }

/// Row presence: 0 absent, 1 written at IVG's open level, 2 committed, 3 pending in the caller's open transaction.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct TxnS {
    pub caller_open: bool,
    pub w: u8,
    pub c: u8,
    pub e: u8,
    /// IVG's open transaction levels ($TLEVEL above the caller's)
    pub ivg_level: u8,
    pub pc: Pc,
    /// ghost: rows this query wrote (bit 0 c, bit 1 e) and whether a caller transaction was open when it started
    pub q_rows: u8,
    pub q_caller: bool,
    pub queries: u8,
}

#[derive(Clone, Debug)]
pub enum TxnA { CallerBegin, CallerCommit, CallerRollback, Start(Variant), Step { fail: bool }, Reset }

pub struct Txn { pub d: TxnDesign }

impl Model for Txn {
    type State = TxnS;
    type Action = TxnA;
    fn init_states(&self) -> Vec<TxnS> {
        // environment freedom: the literal edge may already exist (committed) or not
        [0u8, 2u8].iter().map(|&e| TxnS { caller_open: false, w: 0, c: 0, e, ivg_level: 0, pc: Pc::Idle,
            q_rows: 0, q_caller: false, queries: 0 }).collect()
    }
    fn actions(&self, _: &TxnS) -> Vec<TxnA> {
        vec![TxnA::CallerBegin, TxnA::CallerCommit, TxnA::CallerRollback, TxnA::Start(Variant::LiteralEdge),
             TxnA::Start(Variant::Stepped), TxnA::Step { fail: false }, TxnA::Step { fail: true }, TxnA::Reset]
    }
    fn next(&self, s: &TxnS, a: &TxnA) -> Option<TxnS> {
        let mut t = s.clone();
        let quiet = matches!(s.pc, Pc::Idle | Pc::DoneOk(_) | Pc::DoneErr { .. });
        match a {
            TxnA::CallerBegin => {
                if s.caller_open || !quiet || s.w != 0 { return None; }
                t.caller_open = true;
                t.w = 3; // the caller's own earlier write, pending in its transaction
            }
            TxnA::CallerCommit | TxnA::CallerRollback => {
                if !s.caller_open || !quiet { return None; }
                let commit = matches!(a, TxnA::CallerCommit);
                t.caller_open = false;
                for r in [&mut t.w, &mut t.c, &mut t.e] {
                    if *r == 3 { *r = if commit { 2 } else { 0 }; }
                }
            }
            TxnA::Reset => {
                if !matches!(s.pc, Pc::DoneOk(_) | Pc::DoneErr { .. }) { return None; }
                t.pc = Pc::Idle;
            }
            TxnA::Start(v) => {
                if !matches!(s.pc, Pc::Idle) || s.queries >= 2 { return None; }
                t.queries += 1;
                t.ivg_level += 1; // Txn_Begin: TSTART
                t.q_rows = 0;
                t.q_caller = s.caller_open;
                t.pc = Pc::Running { v: *v, step: 0 };
            }
            TxnA::Step { fail } => {
                let Pc::Running { v, step } = s.pc else { return None };
                // where a step's write lands: IVG's level, or (pre-4.6.4 mutant) committed at once
                let landed = if self.d == TxnDesign::CommitPerStep { if s.caller_open { 3 } else { 2 } } else { 1 };
                match (v, step) {
                    // step 0 of both variants: a guarded node insert (NOT EXISTS), never fails
                    (_, 0) => {
                        if *fail { return None; }
                        if t.c == 0 { t.c = landed; t.q_rows |= 1; }
                        t.pc = Pc::Running { v, step: 1 };
                    }
                    // literal edge: as built an unguarded INSERT ... VALUES; a duplicate is SQLCODE -119
                    (Variant::LiteralEdge, 1) => {
                        if *fail { return None; } // its only failure is the duplicate, decided by the state
                        let exists = t.e != 0;
                        if exists && self.d != TxnDesign::Reviewed {
                            self.fail_query(&mut t, v, true, false);
                        } else {
                            if !exists { t.e = landed; t.q_rows |= 2; }
                            self.finish_ok(&mut t, v);
                        }
                    }
                    // stepped write: a read step after a write step; the environment may fail it (a SQL error)
                    (Variant::Stepped, 1) => {
                        if *fail {
                            let claims = self.d != TxnDesign::Reviewed; // _raise_if_step_failed(res, wrote=True)
                            self.fail_query(&mut t, v, false, claims);
                        } else {
                            self.finish_ok(&mut t, v);
                        }
                    }
                    _ => return None,
                }
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<TxnS>> {
        vec![
            invariant("a failed write query leaves none of its rows", |s: &TxnS| match s.pc {
                Pc::DoneErr { .. } => (s.q_rows & 1 == 0 || s.c == 0) && (s.q_rows & 2 == 0 || s.e == 0),
                _ => true,
            }),
            invariant("an error's text matches what stayed written", |s: &TxnS| match s.pc {
                Pc::DoneErr { claims_kept, .. } => !claims_kept || (s.q_rows & 1 != 0 && s.c != 0) || (s.q_rows & 2 != 0 && s.e != 0),
                _ => true,
            }),
            invariant("creating an existing edge between literal endpoints adds nothing and fails nothing", |s: &TxnS| {
                !matches!(s.pc, Pc::DoneErr { dup: true, .. })
            }),
        ]
    }
    fn action_properties(&self) -> Vec<ActionProperty<TxnS, TxnA>> {
        // checked on the failing step itself: the caller's open transaction and its row are as they were
        vec![action_property("a failed write query keeps the caller's earlier work", |s: &TxnS, _: &TxnA, t: &TxnS| {
            let fails = matches!(s.pc, Pc::Running { .. }) && matches!(t.pc, Pc::DoneErr { .. });
            !fails || (t.caller_open == s.caller_open && t.w == s.w)
        })]
    }
    fn always_possibly(&self) -> Vec<Invariant<TxnS>> {
        vec![invariant("the write's transaction level can always close", |s: &TxnS| s.ivg_level == 0)]
    }
}

impl Txn {
    fn fail_query(&self, t: &mut TxnS, v: Variant, dup: bool, claims_kept: bool) {
        match self.d {
            // SQL ROLLBACK ends every level (4.6.3's START TRANSACTION / ROLLBACK; _write_txn.py docstring)
            TxnDesign::RollbackAll => {
                for r in [&mut t.w, &mut t.c, &mut t.e] { if *r == 1 || *r == 3 { *r = 0; } }
                t.caller_open = false;
            }
            // earlier steps were already committed one by one (pre-4.6.4)
            TxnDesign::CommitPerStep => {}
            // Txn_Undo: TROLLBACK 1 takes back IVG's level alone; the caller's pending rows stay
            _ => for r in [&mut t.c, &mut t.e] { if *r == 1 { *r = 0; } },
        }
        // progress mutant: an exception escapes before Txn_Undo, so the level stays open
        if self.d != TxnDesign::LeakLevel { t.ivg_level -= 1; }
        t.pc = Pc::DoneErr { v, dup, claims_kept };
    }
    fn finish_ok(&self, t: &mut TxnS, v: Variant) {
        // Txn_End: TCOMMIT; under a caller transaction only $TLEVEL drops and the rows stay pending in it
        let to = if t.caller_open { 3 } else { 2 };
        for r in [&mut t.c, &mut t.e] { if *r == 1 { *r = to; } }
        t.ivg_level -= 1;
        t.pc = Pc::DoneOk(v);
    }
}

// ------------------------------------------------------------------------------------------------ 2. scope
/// Graphs: 0 default (D), 1 A, 2 B. Node ids: 0 x, 1 m, 2 l. Candidate edges (graph, src, dst).
const EDGES: [(u8, u8, u8); 5] = [(1, 0, 1), (2, 1, 2), (0, 0, 1), (0, 1, 2), (1, 1, 2)];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Route { VlpCarried, HllApprox, CountShortcut, DbLabels, GraphPath, DottedFn, MappedLabel }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum ScopeDesign { AsBuilt, Reviewed, ReviewedVlpUnscoped }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct ScopeS {
    pub edges: u8,
    pub last: Option<(Route, Option<u8>, u32, u32)>, // route, USE GRAPH g, answer, truth (encoded)
    pub leak: bool,
    pub ops: u8,
}

#[derive(Clone, Debug)]
pub enum ScopeA { Toggle(u8), Query(Route, Option<u8>) }

pub struct Scope { pub d: ScopeDesign, pub routes: Vec<Route> }

fn has(edges: u8, i: usize) -> bool { edges & (1 << i) != 0 }
fn exists(edges: u8, g: u8, n: u8) -> bool {
    (g == 1 && n == 0) || EDGES.iter().enumerate().any(|(i, &(eg, s, d))| has(edges, i) && eg == g && (s == n || d == n))
}
/// ids reachable from n in 1..=2 hops over the edges of graphs in `gs` (a bitmask of graphs), as an id bitmask
fn reach(edges: u8, gs: u8, n: u8) -> u8 {
    let step = |from: u8| -> u8 {
        let mut out = 0u8;
        for (i, &(g, s, d)) in EDGES.iter().enumerate() {
            if has(edges, i) && gs & (1 << g) != 0 && from & (1 << s) != 0 { out |= 1 << d; }
        }
        out
    };
    let h1 = step(1 << n);
    h1 | step(h1)
}
/// per-graph truth for an all-graphs walk from x: (graph, id) pairs reachable inside each graph x is in
fn per_graph_pairs(edges: u8, n: u8) -> u32 {
    let mut out = 0u32;
    for g in 0..3u8 {
        if exists(edges, g, n) {
            let r = reach(edges, 1 << g, n);
            out |= (r as u32) << (3 * g);
        }
    }
    out
}
fn ids_of_pairs(p: u32) -> u8 { ((p | (p >> 3) | (p >> 6)) & 0b111) as u8 }
fn popcount(x: u32) -> u32 { x.count_ones() }
fn nodes_in(edges: u8, g: u8) -> u32 { (0..3u8).filter(|&n| exists(edges, g, n)).count() as u32 }
fn edges_in(edges: u8, g: u8) -> u32 { EDGES.iter().enumerate().filter(|(i, e)| has(edges, *i) && e.0 == g).count() as u32 }
fn graphs_with_nodes(edges: u8) -> u32 { (0..3u8).filter(|&g| (0..3u8).any(|n| exists(edges, g, n))).fold(0, |a, g| a | (1 << g)) }

impl Scope {
    /// (answer, truth): equal (or answer within truth for sets) when the route respects graph scope
    fn answer(&self, edges: u8, r: Route, use_g: Option<u8>) -> Option<(u32, u32)> {
        let rev = self.d != ScopeDesign::AsBuilt;
        match r {
            Route::VlpCarried => {
                // all-graphs read from x with a WITH-carried start: answer ids
                if use_g.is_some() { return None; }
                let truth = ids_of_pairs(per_graph_pairs(edges, 0)) as u32;
                let scoped = rev && self.d != ScopeDesign::ReviewedVlpUnscoped;
                let ans = if scoped { truth } else { reach(edges, 0b111, 0) as u32 };
                Some((ans, truth))
            }
            Route::HllApprox => {
                if use_g.is_some() { return None; } // refused under USE GRAPH (query.py:4420)
                let truth = popcount(per_graph_pairs(edges, 0));
                let named_edges = EDGES.iter().enumerate().any(|(i, e)| has(edges, i) && e.0 != 0);
                let ans = if rev && named_edges { truth } else { popcount(reach(edges, 0b111, 0) as u32) };
                Some((ans, truth))
            }
            Route::CountShortcut => {
                let g = use_g?;
                let truth = nodes_in(edges, g) * 16 + edges_in(edges, g);
                let all = (0..3u8).map(|g| nodes_in(edges, g)).sum::<u32>() * 16 + EDGES.iter().enumerate().filter(|(i, _)| has(edges, *i)).count() as u32;
                Some((if rev { truth } else { all }, truth))
            }
            Route::DbLabels => {
                let g = use_g?;
                let truth = graphs_with_nodes(edges) & (1 << g); // one label per graph
                Some((if rev { truth } else { graphs_with_nodes(edges) }, truth))
            }
            Route::GraphPath => {
                // engine.kg_GRAPH_PATH(x, P1, P2): no graph argument means the default graph
                if use_g.is_some() { return None; }
                let truth = reach(edges, 1, 0) as u32;
                let any = (0..3u8).fold(0u32, |a, g| a | reach(edges, 1 << g, 0) as u32);
                Some((if rev { truth } else { any }, truth))
            }
            Route::DottedFn => {
                // `...`.f() pastes SQL text: it can read every graph's node ids
                let g = use_g?;
                let truth = (0..3u8).filter(|&n| exists(edges, g, n)).fold(0u32, |a, n| a | (1 << n));
                if rev { return Some((truth, truth)); } // refused (reviewed): nothing outside g answers
                let all = (0..3u8).filter(|&n| (0..3u8).any(|gg| exists(edges, gg, n))).fold(0u32, |a, n| a | (1 << n));
                Some((all, truth))
            }
            Route::MappedLabel => {
                // a label mapped to an outside table whose rows belong to graph B (provenance); queried under USE GRAPH g
                let g = use_g?;
                let truth = if g == 2 { 1 } else { 0 };
                Some((if rev { truth } else { 1 }, truth))
            }
        }
    }
}

impl Model for Scope {
    type State = ScopeS;
    type Action = ScopeA;
    fn init_states(&self) -> Vec<ScopeS> { vec![ScopeS { edges: 0, last: None, leak: false, ops: 0 }] }
    fn actions(&self, _: &ScopeS) -> Vec<ScopeA> {
        let mut v: Vec<ScopeA> = (0..EDGES.len() as u8).map(ScopeA::Toggle).collect();
        for &r in &self.routes {
            for g in [None, Some(0), Some(1), Some(2)] { v.push(ScopeA::Query(r, g)); }
        }
        v
    }
    fn within_bounds(&self, s: &ScopeS) -> bool { s.ops <= 7 }
    fn next(&self, s: &ScopeS, a: &ScopeA) -> Option<ScopeS> {
        if s.ops >= 7 { return None; }
        let mut t = s.clone();
        t.ops += 1;
        match a {
            ScopeA::Toggle(i) => { t.edges ^= 1 << i; t.last = None; t.leak = false; }
            ScopeA::Query(r, g) => {
                let (ans, truth) = self.answer(s.edges, *r, *g)?;
                let ok = match r {
                    Route::HllApprox | Route::CountShortcut => ans == truth,
                    _ => ans & !truth == 0,
                };
                t.last = Some((*r, *g, ans, truth));
                t.leak = !ok;
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<ScopeS>> {
        vec![invariant("an answer about graph g holds only g's data", |s: &ScopeS| !s.leak)]
    }
}

// ------------------------------------------------------------------------------------------------ 3. readonly
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Kind { Read, WriteClause, DottedTxnBegin, AqlWrite }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum RoDesign { AsBuilt, Reviewed, ReviewedNoTextCheck }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct RoS { pub data: u8, pub tlevel: u8, pub answered: u8, pub refused: u8, pub calls: u8 }

#[derive(Clone, Debug)]
pub enum RoA { Call(Kind) }

pub struct ReadOnly { pub d: RoDesign }

impl Model for ReadOnly {
    type State = RoS;
    type Action = RoA;
    fn init_states(&self) -> Vec<RoS> { vec![RoS { data: 0, tlevel: 0, answered: 0, refused: 0, calls: 0 }] }
    fn actions(&self, _: &RoS) -> Vec<RoA> {
        [Kind::Read, Kind::WriteClause, Kind::DottedTxnBegin, Kind::AqlWrite].into_iter().map(RoA::Call).collect()
    }
    fn next(&self, s: &RoS, a: &RoA) -> Option<RoS> {
        if s.calls >= 3 { return None; }
        let mut t = s.clone();
        t.calls += 1;
        let RoA::Call(k) = a;
        // every call here is made with read_only requested by the caller
        let text_check = self.d != RoDesign::ReviewedNoTextCheck;
        let reviewed = self.d != RoDesign::AsBuilt;
        match k {
            Kind::Read => t.answered += 1,
            Kind::WriteClause => if text_check { t.refused += 1 } else { t.data += 1 },
            // writes_cypher judges clauses only; the pasted SQL calls Graph_KG.Txn_Begin
            Kind::DottedTxnBegin => if reviewed { t.refused += 1 } else { t.tlevel += 1; t.answered += 1 },
            // execute_aql has no read_only: the translated SET runs
            Kind::AqlWrite => if reviewed && text_check { t.refused += 1 } else { t.data += 1 },
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<RoS>> {
        vec![invariant("a call in read-only mode changes no data and opens no transaction", |s: &RoS| s.data == 0 && s.tlevel == 0)]
    }
}

// ------------------------------------------------------------------------------------------------ checks
fn txn(d: TxnDesign) -> Txn { Txn { d } }
const ATOMIC: &str = "a failed write query leaves none of its rows";
const CALLER: &str = "a failed write query keeps the caller's earlier work";
const MSG: &str = "an error's text matches what stayed written";
const DUP: &str = "creating an existing edge between literal endpoints adds nothing and fails nothing";
const CLOSE: &str = "the write's transaction level can always close";
const SYSI2: &str = "an answer about graph g holds only g's data";
const RO: &str = "a call in read-only mode changes no data and opens no transaction";

fn scope_only(r: Route) -> Scope { Scope { d: ScopeDesign::AsBuilt, routes: vec![r] } }
const ALL_ROUTES: [Route; 7] = [Route::VlpCarried, Route::HllApprox, Route::CountShortcut, Route::DbLabels,
    Route::GraphPath, Route::DottedFn, Route::MappedLabel];

pub fn checks() -> Vec<(&'static str, Box<dyn Fn() -> Outcome>)> {
    let mut v = vec![
        // --- txn
        check("m08-txn-as-built-dup", || judge("m08-txn-as-built-dup", M, "txn", "as-built", Expect::Violation(DUP),
            "F-0805; CYP-B6.7.6, CYP-B6.7.7; KNOWN_ISSUES.md:25-31",
            explore(&Only::new(txn(TxnDesign::AsBuilt), &[DUP]), limits()), show_debug)),
        check("m08-txn-as-built-msg", || judge("m08-txn-as-built-msg", M, "txn", "as-built", Expect::Violation(MSG),
            "F-0806; query.py:1692-1705",
            explore(&Only::new(txn(TxnDesign::AsBuilt), &[MSG]), limits()), show_debug)),
        check("m08-txn-as-built-atomic", || judge("m08-txn-as-built-atomic", M, "txn", "as-built", Expect::Pass,
            "CYP-I6.3, CYP-I6.4, CYP-X6.5 hold as built (journal: live 08-footprints)",
            explore(&Only::new(txn(TxnDesign::AsBuilt), &[ATOMIC, CALLER, CLOSE]), limits()), show_debug)),
        check("m08-txn-reviewed", || judge("m08-txn-reviewed", M, "txn", "reviewed", Expect::Pass,
            "CYP-I6.3, CYP-I6.4, CYP-X6.5, CYP-B6.7.7, F-0805/F-0806 remedies; AG EF level closes",
            explore(&txn(TxnDesign::Reviewed), limits()), show_debug)),
        check("m08-txn-control-rollback-all", || judge("m08-txn-control-rollback-all", M, "txn", "control", Expect::Violation(CALLER),
            "mutant: failure ends every level (SQL ROLLBACK, 4.6.3) must break CYP-I6.3",
            explore(&Only::new(txn(TxnDesign::RollbackAll), &[CALLER]), limits()), show_debug)),
        check("m08-txn-control-commit-per-step", || judge("m08-txn-control-commit-per-step", M, "txn", "control", Expect::Violation(ATOMIC),
            "mutant: steps commit one by one (pre-4.6.4) must break CYP-I6.4",
            explore(&Only::new(txn(TxnDesign::CommitPerStep), &[ATOMIC]), limits()), show_debug)),
        check("m08-txn-control-leak-level", || judge("m08-txn-control-leak-level", M, "txn", "control", Expect::Violation(CLOSE),
            "progress mutant: a failure that skips Txn_Undo leaves IVG's level open; only the AG EF goal may fail",
            explore(&Only::new(txn(TxnDesign::LeakLevel), &[CLOSE]), limits()), show_debug)),
        check("m08-txn-control-leak-level-safety", || judge("m08-txn-control-leak-level-safety", M, "txn", "control", Expect::Pass,
            "the progress mutant keeps the safety properties (progress controls fail only the progress check)",
            explore(&Only::new(txn(TxnDesign::LeakLevel), &[ATOMIC, CALLER]), limits()), show_debug)),
        check("m08-txn-positive-caller-kept", || judge("m08-txn-positive-caller-kept", M, "txn", "positive",
            Expect::Violation("witness: a failed query inside a caller transaction"),
            "sharpness: a failure with the caller's row pending is reachable",
            explore(&Only::new(txn(TxnDesign::Reviewed), &[]).witness("witness: a failed query inside a caller transaction",
                |s: &TxnS| matches!(s.pc, Pc::DoneErr { .. }) && s.caller_open && s.w == 3), limits()), show_debug)),
        check("m08-txn-positive-commit", || judge("m08-txn-positive-commit", M, "txn", "positive",
            Expect::Violation("witness: a query's rows committed"),
            "sharpness: a successful query commits its node and edge",
            explore(&Only::new(txn(TxnDesign::Reviewed), &[]).witness("witness: a query's rows committed",
                |s: &TxnS| matches!(s.pc, Pc::DoneOk(Variant::LiteralEdge)) && s.c == 2 && s.e == 2 && s.q_rows == 3), limits()), show_debug)),
    ];
    // --- scope: one as-built check per route (one finding each), the reviewed design over every route, a control
    let per_route: [(&'static str, Route, &'static str); 7] = [
        ("m08-scope-as-built-vlp", Route::VlpCarried, "F-0818; CYP-I5.6"),
        ("m08-scope-as-built-hll", Route::HllApprox, "F-0819; CYP-I4.14"),
        ("m08-scope-as-built-shortcut", Route::CountShortcut, "F-0802"),
        ("m08-scope-as-built-dblabels", Route::DbLabels, "F-0816"),
        ("m08-scope-as-built-graphpath", Route::GraphPath, "F-0820"),
        ("m08-scope-as-built-dotted", Route::DottedFn, "F-0815; CYP-I9.4"),
        ("m08-scope-as-built-mapped", Route::MappedLabel, "HD-0802 (assumed reviewed contract); CYP-Q4.17"),
    ];
    for (id, r, covers) in per_route {
        v.push(check(id, move || judge(id, M, "scope", "as-built", Expect::Violation(SYSI2), covers,
            explore(&scope_only(r), limits()), show_debug)));
    }
    v.push(check("m08-scope-reviewed", || judge("m08-scope-reviewed", M, "scope", "reviewed", Expect::Pass,
        "SYS-I2, CYP-I5.5, CYP-I5.6, CYP-I4.14 over every read route (reviewed remedies of F-0802/0815/0816/0818/0819/0820, HD-0802)",
        explore(&Scope { d: ScopeDesign::Reviewed, routes: ALL_ROUTES.to_vec() }, limits()), show_debug)));
    v.push(check("m08-scope-control-vlp-unscoped", || judge("m08-scope-control-vlp-unscoped", M, "scope", "control",
        Expect::Violation(SYSI2), "mutant: reviewed design with the VLP graph test dropped must be caught",
        explore(&Scope { d: ScopeDesign::ReviewedVlpUnscoped, routes: ALL_ROUTES.to_vec() }, limits()), show_debug)));
    v.push(check("m08-scope-positive-walk", || judge("m08-scope-positive-walk", M, "scope", "positive",
        Expect::Violation("witness: a scoped walk answers a non-empty set"),
        "sharpness: the reviewed walk is not vacuous (answers ids)",
        explore(&Only::new(Scope { d: ScopeDesign::Reviewed, routes: vec![Route::VlpCarried] }, &[])
            .witness("witness: a scoped walk answers a non-empty set",
                |s: &ScopeS| matches!(s.last, Some((Route::VlpCarried, None, a, _)) if a != 0)), limits()), show_debug)));
    // --- readonly
    v.push(check("m08-readonly-as-built", || judge("m08-readonly-as-built", M, "readonly", "as-built", Expect::Violation(RO),
        "F-0815 (Txn_Begin under read_only), F-0814 (execute_aql has no read_only); CYP-I8.6",
        explore(&ReadOnly { d: RoDesign::AsBuilt }, limits()), show_debug)));
    v.push(check("m08-readonly-reviewed", || judge("m08-readonly-reviewed", M, "readonly", "reviewed", Expect::Pass,
        "CYP-I8.6 with dotted names refused under read_only and execute_aql(read_only)",
        explore(&ReadOnly { d: RoDesign::Reviewed }, limits()), show_debug)));
    v.push(check("m08-readonly-control-no-text-check", || judge("m08-readonly-control-no-text-check", M, "readonly", "control",
        Expect::Violation(RO), "mutant: writes_cypher check removed must be caught",
        explore(&ReadOnly { d: RoDesign::ReviewedNoTextCheck }, limits()), show_debug)));
    v.push(check("m08-readonly-positive-read", || judge("m08-readonly-positive-read", M, "readonly", "positive",
        Expect::Violation("witness: a read is answered in read-only mode"), "sharpness: reads still answer",
        explore(&Only::new(ReadOnly { d: RoDesign::Reviewed }, &[]).witness("witness: a read is answered in read-only mode",
            |s: &RoS| s.answered > 0), limits()), show_debug)));
    v
}
