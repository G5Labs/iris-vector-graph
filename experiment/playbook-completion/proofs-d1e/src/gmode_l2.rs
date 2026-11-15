//! Module 02, L2 part 2: multigraph mode of one triple of one graph over the stored layout and the writers'
//! statements at pin 3eaa79cf; refinement of `gmode_l1` for every step, the invariant, and controls F-0201, F-0208
//! and F-0207.
//!
//! Layout: `rows` the triple's rows in Graph_KG.rdf_edges by edge key (unique key (s, p, o_id, graph_id, ekey),
//! iris_vector_graph/schema.py:44); `gm` ^IVG.GraphMode(gKey) = "multi" (GraphMode.cls:30-33); `cache` each engine's
//! cached mode (is_multigraph, iris_vector_graph/_engine/admin.py:917-926; only that engine's own set_multigraph /
//! erase forgets it, :928-936); `cy` each engine's Cypher relationship CREATE in flight with the mode it read
//! (`_multigraph` asks once per statement, iris_vector_graph/cypher/translator.py:441-457); `excl` / `shared` the
//! reviewed design's mode lock; `counted` the engine running GraphMode.Set(g, 0) between its count and its kill.
//!
//! Steps (one SQL statement or one global operation each): `SetOn` Set(g, 1); `SetOffCount` Set(g, 0)'s
//! ParallelCount (one SQL query, GraphMode.cls:35-40, 48-61; `ok` false: refused, parallel_edges_present);
//! `SetOffKill` its Kill ^IVG.GraphMode (:41); `CyMode` the statement's mode read; `CyInsertPar` the keyed insert at
//! COALESCE(MAX(ekey) + 1, 0) (translator.py:10368-10388: a fresh key, any here); `CyInsertOne` the mode-off insert
//! at ekey 0, refused by the unique key when ekey 0 exists; `Single` create_edge's guarded insert `... WHERE NOT
//! EXISTS (... AND ekey = 0)` (_engine/nodes_edges.py:1214-1217 with `_ekey_guard`, :1257-1273) or store_edge's
//! plain insert at ekey 0 (duplicate swallowed, :2560-2581); `Delete` a Cypher per-edge DELETE.
//!
//! **Reviewed design** (the findings' remedies): the single-edge writers and the mode-off insert refuse when the
//! triple has any row (F-0201); the mode is read per statement (F-0208); Set(g, 0) holds the graph's mode lock
//! exclusively from its count to its kill, and each Cypher writer holds it shared from its mode read to its insert
//! (F-0207: "a lock the multigraph writers also take").
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::gmode_l1::*;

verus! {

pub struct MS2 {
    pub rows: Set<int>,
    pub gm: bool,
    pub cache: Map<int, bool>,
    pub cy: Map<int, bool>,
    pub excl: bool,
    pub shared: Set<int>,
    pub counted: Option<int>,
}

pub enum ML2 {
    SetOn { e: int },
    SetOffCount { e: int, ok: bool },
    SetOffKill { e: int },
    CyMode { e: int },
    CyInsertPar { e: int, k: int },
    CyInsertOne { e: int, added: bool },
    Single { e: int, added: bool },
    Delete { k: int },
}

pub open spec fn f0201() -> bool { cfg!(feature = "control_f0201_ekey0_guard") }
pub open spec fn f0208() -> bool { cfg!(feature = "control_f0208_mode_cached_forever") }
pub open spec fn f0207() -> bool { cfg!(feature = "control_f0207_set_off_unlocked") }
pub open spec fn locked() -> bool { !f0207() }

/// May a single-edge insert at ekey 0 go in? As built only ekey 0 stops it (F-0201); reviewed, any row of the triple.
pub open spec fn guard_ok(s: MS2) -> bool { if f0201() { !s.rows.contains(0) } else { s.rows == Set::<int>::empty() } }

/// The mode a statement reads: the engine's cache as built (F-0208), ^IVG.GraphMode reviewed.
pub open spec fn mode_read(s: MS2, e: int) -> bool {
    if f0208() && s.cache.contains_key(e) { s.cache[e] } else { s.gm }
}

pub open spec fn step2(s: MS2, l: ML2, t: MS2) -> bool {
    match l {
        ML2::SetOn { e } => t == (MS2 { gm: true, cache: s.cache.remove(e), ..s }),
        ML2::SetOffCount { e, ok } => s.counted is None && s.gm && (locked() ==> !s.excl && s.shared == Set::<int>::empty())
            && ok == (s.rows.len() <= 1)
            && t == (if ok { MS2 { counted: Some(e), excl: locked(), ..s } } else { s }),
        ML2::SetOffKill { e } => s.counted == Some(e)
            && t == (MS2 { gm: false, counted: None, excl: false, cache: s.cache.remove(e), ..s }),
        ML2::CyMode { e } => !s.cy.contains_key(e) && (locked() ==> !s.excl)
            && t == (MS2 { cy: s.cy.insert(e, mode_read(s, e)),
                           cache: if s.cache.contains_key(e) { s.cache } else { s.cache.insert(e, s.gm) },
                           shared: if locked() { s.shared.insert(e) } else { s.shared }, ..s }),
        ML2::CyInsertPar { e, k } => s.cy.contains_key(e) && s.cy[e] && !s.rows.contains(k)
            && t == (MS2 { rows: s.rows.insert(k), cy: s.cy.remove(e), shared: s.shared.remove(e), ..s }),
        ML2::CyInsertOne { e, added } => s.cy.contains_key(e) && !s.cy[e] && added == guard_ok(s)
            && t == (MS2 { rows: if added { s.rows.insert(0) } else { s.rows }, cy: s.cy.remove(e), shared: s.shared.remove(e), ..s }),
        ML2::Single { e, added } => added == guard_ok(s)
            && t == (MS2 { rows: if added { s.rows.insert(0) } else { s.rows }, ..s }),
        ML2::Delete { k } => s.rows.contains(k) && t == (MS2 { rows: s.rows.remove(k), ..s }),
    }
}

pub open spec fn init2(s: MS2) -> bool {
    s.rows == Set::<int>::empty() && !s.gm && s.cache == Map::<int, bool>::empty() && s.cy == Map::<int, bool>::empty()
        && !s.excl && s.shared == Set::<int>::empty() && s.counted is None
}

pub open spec fn absm(s: MS2) -> MS1 { MS1 { keys: s.rows, multi: s.gm } }

pub open spec fn labm(l: ML2) -> Option<ML1> {
    match l {
        ML2::SetOn { e } => Some(ML1::SetOn),
        ML2::SetOffCount { e, ok } => if ok { None } else { Some(ML1::SetOff { ok: false }) },
        ML2::SetOffKill { e } => Some(ML1::SetOff { ok: true }),
        ML2::CyMode { e } => None,
        ML2::CyInsertPar { e, k } => Some(ML1::Parallel { k }),
        ML2::CyInsertOne { e, added } => Some(ML1::Single { k: 0, added }),
        ML2::Single { e, added } => Some(ML1::Single { k: 0, added }),
        ML2::Delete { k } => Some(ML1::Delete { k }),
    }
}

/// L1's invariant on the rows; a counted Set(g, 0) holds the lock over a triple of at most one row, in multigraph
/// mode; the lock is exclusive; a statement in flight holds it shared, and one that read multigraph mode reads the
/// current mode.
pub open spec fn invm(s: MS2) -> bool {
    &&& inv1(absm(s))
    &&& (s.counted is Some ==> s.excl && s.gm && s.rows.len() <= 1)
    &&& (s.excl ==> s.counted is Some && s.shared == Set::<int>::empty())
    &&& forall|e: int| #[trigger] s.cy.contains_key(e) ==> s.shared.contains(e)
    &&& forall|e: int| #[trigger] s.cy.contains_key(e) && s.cy[e] ==> s.gm
}

pub struct ModeL2;

impl Contract for ModeL2 {
    type S = MS2;
    type L = ML2;
    open spec fn init(s: MS2) -> bool { init2(s) }
    open spec fn next(s: MS2, l: ML2, t: MS2) -> bool { invm(s) && step2(s, l, t) }
}

pub struct ModeRaw;

impl Contract for ModeRaw {
    type S = MS2;
    type L = ML2;
    open spec fn init(s: MS2) -> bool { init2(s) }
    open spec fn next(s: MS2, l: ML2, t: MS2) -> bool { step2(s, l, t) }
}

proof fn lemma_setoffcount(s: MS2, e: int, ok: bool, t: MS2)
    requires invm(s), step2(s, ML2::SetOffCount { e, ok }, t),
    ensures invm(t), step_or_stutter::<ModeL1>(absm(s), labm(ML2::SetOffCount { e, ok }), absm(t)),
{
    // the count takes the mode lock exclusively and keeps it to the kill (control F-0207 fails here)
    assert(t.counted is Some ==> t.excl);
    assert(forall|x: int| #[trigger] t.cy.contains_key(x) ==> t.shared.contains(x));
}

proof fn lemma_cymode(s: MS2, e: int, t: MS2)
    requires invm(s), step2(s, ML2::CyMode { e }, t),
    ensures invm(t), step_or_stutter::<ModeL1>(absm(s), labm(ML2::CyMode { e }), absm(t)),
{
    // the statement holds the lock shared from its mode read (control F-0207 fails here) ...
    assert(t.shared.contains(e));
    // ... and reads the current mode (control F-0208 fails here)
    assert(t.cy[e] ==> t.gm);
    assert forall|x: int| #[trigger] t.cy.contains_key(x) implies t.shared.contains(x) by { if x != e { assert(s.cy.contains_key(x)); } }
    assert forall|x: int| #[trigger] t.cy.contains_key(x) && t.cy[x] implies t.gm by { if x != e { assert(s.cy.contains_key(x)); } }
}

proof fn lemma_single(s: MS2, e: int, added: bool, t: MS2)
    requires invm(s), step2(s, ML2::Single { e, added }, t),
    ensures invm(t), step_or_stutter::<ModeL1>(absm(s), labm(ML2::Single { e, added }), absm(t)),
{
    // a single-edge writer adds an edge only to a triple with none (control F-0201 fails here)
    assert(added ==> s.rows == Set::<int>::empty());
}

proof fn lemma_cyinsertone(s: MS2, e: int, added: bool, t: MS2)
    requires invm(s), step2(s, ML2::CyInsertOne { e, added }, t),
    ensures invm(t), step_or_stutter::<ModeL1>(absm(s), labm(ML2::CyInsertOne { e, added }), absm(t)),
{
    // the mode-off Cypher insert adds an edge only to a triple with none (control F-0201 fails here)
    assert(added ==> s.rows == Set::<int>::empty());
    assert forall|x: int| #[trigger] t.cy.contains_key(x) implies t.shared.contains(x) by { assert(s.cy.contains_key(x)); }
    assert forall|x: int| #[trigger] t.cy.contains_key(x) && t.cy[x] implies t.gm by { assert(s.cy.contains_key(x)); }
}

proof fn lemma_cyinsertpar(s: MS2, e: int, k: int, t: MS2)
    requires invm(s), step2(s, ML2::CyInsertPar { e, k }, t),
    ensures invm(t), step_or_stutter::<ModeL1>(absm(s), labm(ML2::CyInsertPar { e, k }), absm(t)),
{
    assert(s.gm);
    assert(s.shared.contains(e));
    assert forall|x: int| #[trigger] t.cy.contains_key(x) implies t.shared.contains(x) by { assert(s.cy.contains_key(x)); }
    assert forall|x: int| #[trigger] t.cy.contains_key(x) && t.cy[x] implies t.gm by { assert(s.cy.contains_key(x)); }
}

proof fn lemma_step(s: MS2, l: ML2, t: MS2)
    requires invm(s), step2(s, l, t),
    ensures invm(t), step_or_stutter::<ModeL1>(absm(s), labm(l), absm(t)),
{
    match l {
        ML2::SetOffCount { e, ok } => lemma_setoffcount(s, e, ok, t),
        ML2::CyMode { e } => lemma_cymode(s, e, t),
        ML2::Single { e, added } => lemma_single(s, e, added, t),
        ML2::CyInsertOne { e, added } => lemma_cyinsertone(s, e, added, t),
        ML2::CyInsertPar { e, k } => lemma_cyinsertpar(s, e, k, t),
        ML2::SetOffKill { e } => {
            assert forall|x: int| #[trigger] t.cy.contains_key(x) && t.cy[x] implies t.gm by {
                assert(s.cy.contains_key(x) && s.shared.contains(x));
            }
        }
        _ => {}
    }
}

impl Refines<ModeL1> for ModeL2 {
    open spec fn abs(s: MS2) -> MS1 { absm(s) }
    open spec fn lab(l: ML2) -> Option<ML1> { labm(l) }
    proof fn init_refines(s: MS2) {}
    proof fn step_refines(s: MS2, l: ML2, t: MS2) { lemma_step(s, l, t); }
}

impl SafeContract for ModeL2 {
    open spec fn inv(s: MS2) -> bool { invm(s) }
    proof fn init_safe(s: MS2) {}
    proof fn step_safe(s: MS2, l: ML2, t: MS2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<MS2>, labels: Seq<ML2>, k: int)
    requires execution::<ModeRaw>(states, labels), 0 <= k < states.len(),
    ensures invm(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution.
pub proof fn theorem_raw_executions_refine(states: Seq<MS2>, labels: Seq<ML2>)
    requires execution::<ModeRaw>(states, labels),
    ensures
        execution::<ModeL2>(states, labels),
        abstract_execution::<ModeL1>(Seq::new(states.len(), |i: int| absm(states[i])),
                                     Seq::new(labels.len(), |i: int| labm(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> invm(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies invm(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<ModeL2>(states, labels));
    trace_refines::<ModeL2, ModeL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absm(states[i])) =~= Seq::new(states.len(), |i: int| <ModeL2 as Refines<ModeL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labm(labels[i])) =~= Seq::new(labels.len(), |i: int| <ModeL2 as Refines<ModeL1>>::lab(labels[i])));
}

/// On the layout: rdf_edges never holds two rows of the triple while ^IVG.GraphMode says the graph is off.
pub proof fn theorem_mode_off_rows(s: MS2)
    requires invm(s), !s.gm,
    ensures s.rows.len() <= 1,
{
}

} // verus!
