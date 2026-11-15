//! Module 03, L2 part 2: directly written edges and the ledger's statement entries over the stored layout at pin
//! 3eaa79cf; refinement of `stmt_l1` for every step, the invariant, and the control F-0303.
//!
//! State (production names; one graph, triples abstracted to `int`):
//! - `rows`   Graph_KG.rdf_edges: triple -> edge_id (the row's %ID; a row created again gets a new id)
//! - `next_id` the edge_id counter
//! - `stmt`   ^IVG.Ledger("stmt", id) = $LB(s, p, o, g, createdSeq, deletedSeq): `k` the tuple, `live` deletedSeq
//!            empty; `life` is ghost (the edge_id of the row the statement was allocated for; not stored)
//! - `next_stmt` ^IVG.Ledger("stmtNext")
//! - `tuple`  ^IVG.Ledger("tuple", s, p, o, gkey) = id
//!
//! **Reviewed design** (F-0303 remedy): delete_edge goes through Eraser.EraseEdges, whose EraseEdgeRow kills the
//! triple's statement and tuple entry with the row (Eraser.cls:641-683), as delete_node's per-edge step already does.
//! As built, delete_edge is a plain SQL DELETE (nodes_edges.py:1414-1433).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::stmt_l1::*;

verus! {

pub struct SR { pub k: int, pub life: nat, pub live: bool }

pub struct SS2 {
    pub rows: Map<int, nat>,
    pub next_id: nat,
    pub stmt: Map<nat, SR>,
    pub next_stmt: nat,
    pub tuple: Map<int, nat>,
}

pub enum SL2 {
    /// OpCreateRel's create path (LedgerApply.cls:455-497) with AllocStmt (159-168).
    LCreate { k: int, id: nat },
    /// An op naming the relationship by tuple: ResolveRef (LedgerApply.cls:185-204) or OpCreateRel's merge path
    /// (470-479); with no tuple entry the live edge is given a statement ("assigned_stmt").
    LUpdate { k: int, id: nat },
    /// The changeset delete by tuple (LedgerApply.cls:670-683): row, deletedSeq, tuple entry.
    LDelete { k: int, id: nat },
    /// engine.create_edge: the guarded INSERT (nodes_edges.py:1205-1219); nothing in the ledger.
    DCreate { k: int },
    /// engine.delete_edge (nodes_edges.py:1382-1450).
    DDelete { k: int },
    /// engine.delete_node -> Eraser.EraseNodeIds -> EraseEdgeRow for the node's edge (Eraser.cls:641-683).
    ENode { k: int },
}

pub open spec fn f0303() -> bool { cfg!(feature = "control_f0303_direct_delete_keeps_stmt") }

/// EraseEdgeRow: the row, the triple's statement and its tuple entry.
pub open spec fn unlink(s: SS2, k: int) -> SS2 {
    SS2 { rows: s.rows.remove(k), stmt: if s.tuple.contains_key(k) { s.stmt.remove(s.tuple[k]) } else { s.stmt },
          tuple: s.tuple.remove(k), ..s }
}

pub open spec fn init2(s: SS2) -> bool {
    s.rows == Map::<int, nat>::empty() && s.next_id == 0 && s.stmt == Map::<nat, SR>::empty() && s.next_stmt == 0
        && s.tuple == Map::<int, nat>::empty()
}

pub open spec fn step2(s: SS2, l: SL2, t: SS2) -> bool {
    match l {
        SL2::LCreate { k, id } =>
            !s.rows.contains_key(k) && id == s.next_stmt
                && t == (SS2 { rows: s.rows.insert(k, s.next_id), next_id: s.next_id + 1,
                               stmt: s.stmt.insert(id, SR { k, life: s.next_id, live: true }), next_stmt: s.next_stmt + 1,
                               tuple: s.tuple.insert(k, id) }),
        SL2::LUpdate { k, id } =>
            s.rows.contains_key(k) && if !s.tuple.contains_key(k) {
                id == s.next_stmt && t == (SS2 { stmt: s.stmt.insert(id, SR { k, life: s.rows[k], live: true }),
                                                 next_stmt: s.next_stmt + 1, tuple: s.tuple.insert(k, id), ..s })
            } else {
                // a killed or deleted statement is refused ("statement is unknown" / "was deleted")
                id == s.tuple[k] && s.stmt.contains_key(id) && s.stmt[id].live && t == s
            },
        SL2::LDelete { k, id } =>
            s.rows.contains_key(k) && s.tuple.contains_key(k) && s.tuple[k] == id && s.stmt.contains_key(id) && s.stmt[id].live
                && t == (SS2 { rows: s.rows.remove(k), stmt: s.stmt.insert(id, SR { live: false, ..s.stmt[id] }),
                               tuple: s.tuple.remove(k), ..s }),
        SL2::DCreate { k } =>
            !s.rows.contains_key(k) && t == (SS2 { rows: s.rows.insert(k, s.next_id), next_id: s.next_id + 1, ..s }),
        SL2::DDelete { k } =>
            s.rows.contains_key(k) && if f0303() { t == (SS2 { rows: s.rows.remove(k), ..s }) } else { t == unlink(s, k) },
        SL2::ENode { k } => s.rows.contains_key(k) && t == unlink(s, k),
    }
}

// ------------------------------------------------------------------------------------------------ the abstraction

pub open spec fn live_stmts(stmt: Map<nat, SR>) -> Map<nat, St> {
    Map::new(stmt.dom().filter(|j: nat| stmt[j].live), |j: nat| St { k: stmt[j].k, life: stmt[j].life })
}
pub open spec fn abss(s: SS2) -> SS1 { SS1 { row: s.rows, next_life: s.next_id, stmts: live_stmts(s.stmt), next_stmt: s.next_stmt } }

pub open spec fn labs(l: SL2) -> Option<SL1> {
    match l {
        SL2::LCreate { k, id } => Some(SL1::LCreate { k, id }),
        SL2::LUpdate { k, id } => Some(SL1::LUpdate { k, id }),
        SL2::LDelete { k, id } => Some(SL1::LDelete { k, id }),
        SL2::DCreate { k } => Some(SL1::DCreate { k }),
        SL2::DDelete { k } => Some(SL1::DDelete { k }),
        SL2::ENode { k } => Some(SL1::DDelete { k }),
    }
}

// ------------------------------------------------------------------------------------------------ invariant

/// The tuple index points at the triple's live statement ...
pub open spec fn inv_tuple(s: SS2) -> bool {
    forall|k: int| #[trigger] s.tuple.contains_key(k) ==>
        s.stmt.contains_key(s.tuple[k]) && s.stmt[s.tuple[k]].live && s.stmt[s.tuple[k]].k == k
}
/// ... and every live statement is the one its triple's tuple entry names.
pub open spec fn inv_back(s: SS2) -> bool {
    forall|j: nat| #[trigger] s.stmt.contains_key(j) && s.stmt[j].live ==> s.tuple.contains_key(s.stmt[j].k) && s.tuple[s.stmt[j].k] == j
}
pub open spec fn inv_ids(s: SS2) -> bool { forall|j: nat| #[trigger] s.stmt.contains_key(j) ==> j < s.next_stmt }
pub open spec fn inv03s(s: SS2) -> bool { inv1(abss(s)) && inv_tuple(s) && inv_back(s) && inv_ids(s) }

pub struct StmtL2;

impl Contract for StmtL2 {
    type S = SS2;
    type L = SL2;
    open spec fn init(s: SS2) -> bool { init2(s) }
    open spec fn next(s: SS2, l: SL2, t: SS2) -> bool { inv03s(s) && step2(s, l, t) }
}

pub struct StmtRaw;

impl Contract for StmtRaw {
    type S = SS2;
    type L = SL2;
    open spec fn init(s: SS2) -> bool { init2(s) }
    open spec fn next(s: SS2, l: SL2, t: SS2) -> bool { step2(s, l, t) }
}

// ------------------------------------------------------------------------------------------------ step lemmas

/// A live statement is in the abstraction and names its triple's current row (inv_named through the abstraction).
proof fn lemma_live_named(s: SS2, j: nat)
    requires inv03s(s), s.stmt.contains_key(j), s.stmt[j].live,
    ensures abss(s).stmts.contains_key(j), abss(s).stmts[j] == (St { k: s.stmt[j].k, life: s.stmt[j].life }),
            s.rows.contains_key(s.stmt[j].k), s.rows[s.stmt[j].k] == s.stmt[j].life,
{
    assert(s.stmt.dom().filter(|i: nat| s.stmt[i].live).contains(j));
    assert(live_stmts(s.stmt).contains_key(j));
    assert(abss(s).stmts.contains_key(j));
}

proof fn lemma_lcreate(s: SS2, k: int, id: nat, t: SS2)
    requires inv03s(s), step2(s, SL2::LCreate { k, id }, t),
    ensures inv03s(t), step_or_stutter::<StmtL1>(abss(s), labs(SL2::LCreate { k, id }), abss(t)),
{
    assert(!s.stmt.contains_key(id));
    assert(live_stmts(t.stmt) =~= live_stmts(s.stmt).insert(id, St { k, life: s.next_id }));
    assert(!s.tuple.contains_key(k)) by {
        if s.tuple.contains_key(k) {
            let j = s.tuple[k];
            lemma_live_named(s, j);
        }
    }
    lemma_l1_safe(abss(s), SL1::LCreate { k, id }, abss(t));
    assert forall|x: int| #[trigger] t.tuple.contains_key(x) implies
        t.stmt.contains_key(t.tuple[x]) && t.stmt[t.tuple[x]].live && t.stmt[t.tuple[x]].k == x by {
        if x != k { assert(s.tuple.contains_key(x)); assert(s.tuple[x] < s.next_stmt); }
    }
    assert forall|j: nat| #[trigger] t.stmt.contains_key(j) && t.stmt[j].live implies
        t.tuple.contains_key(t.stmt[j].k) && t.tuple[t.stmt[j].k] == j by {
        if j != id {
            assert(s.stmt.contains_key(j) && s.stmt[j].live);
            assert(live_stmts(s.stmt).contains_key(j));
            assert(s.stmt[j].k != k);
        }
    }
}

proof fn lemma_lupdate(s: SS2, k: int, id: nat, t: SS2)
    requires inv03s(s), step2(s, SL2::LUpdate { k, id }, t),
    ensures inv03s(t), step_or_stutter::<StmtL1>(abss(s), labs(SL2::LUpdate { k, id }), abss(t)),
{
    if !s.tuple.contains_key(k) {
        assert(unnamed(abss(s), k)) by {
            assert forall|j: nat| #[trigger] abss(s).stmts.contains_key(j) implies abss(s).stmts[j].k != k by {
                assert(s.stmt.contains_key(j) && s.stmt[j].live);
            }
        }
        assert(!s.stmt.contains_key(id));
        assert(live_stmts(t.stmt) =~= live_stmts(s.stmt).insert(id, St { k, life: s.rows[k] }));
        lemma_l1_safe(abss(s), SL1::LUpdate { k, id }, abss(t));
        assert forall|x: int| #[trigger] t.tuple.contains_key(x) implies
            t.stmt.contains_key(t.tuple[x]) && t.stmt[t.tuple[x]].live && t.stmt[t.tuple[x]].k == x by {
            if x != k { assert(s.tuple.contains_key(x)); assert(s.tuple[x] < s.next_stmt); }
        }
        assert forall|j: nat| #[trigger] t.stmt.contains_key(j) && t.stmt[j].live implies
            t.tuple.contains_key(t.stmt[j].k) && t.tuple[t.stmt[j].k] == j by {
            if j != id { assert(s.stmt.contains_key(j) && s.stmt[j].live); }
        }
    } else {
        // the tuple entry names the live statement of the current edge
        lemma_live_named(s, id);
        assert(abss(s).stmts.contains_key(id) && abss(s).stmts[id].k == k);
        assert(!unnamed(abss(s), k));
        assert(names(abss(s), id, k));
    }
}

proof fn lemma_ldelete(s: SS2, k: int, id: nat, t: SS2)
    requires inv03s(s), step2(s, SL2::LDelete { k, id }, t),
    ensures inv03s(t), step_or_stutter::<StmtL1>(abss(s), labs(SL2::LDelete { k, id }), abss(t)),
{
    assert(live_stmts(s.stmt).contains_key(id));
    assert(names(abss(s), id, k));
    assert(live_stmts(t.stmt) =~= live_stmts(s.stmt).remove(id));
    lemma_l1_safe(abss(s), SL1::LDelete { k, id }, abss(t));
    assert forall|x: int| #[trigger] t.tuple.contains_key(x) implies
        t.stmt.contains_key(t.tuple[x]) && t.stmt[t.tuple[x]].live && t.stmt[t.tuple[x]].k == x by {
        assert(s.tuple.contains_key(x));
    }
    assert forall|j: nat| #[trigger] t.stmt.contains_key(j) && t.stmt[j].live implies
        t.tuple.contains_key(t.stmt[j].k) && t.tuple[t.stmt[j].k] == j by {
        assert(s.stmt.contains_key(j) && s.stmt[j].live);
    }
}

proof fn lemma_dcreate(s: SS2, k: int, t: SS2)
    requires inv03s(s), step2(s, SL2::DCreate { k }, t),
    ensures inv03s(t), step_or_stutter::<StmtL1>(abss(s), labs(SL2::DCreate { k }), abss(t)),
{
    lemma_l1_safe(abss(s), SL1::DCreate { k }, abss(t));
}

/// The reviewed unlink ends exactly the triple's live statement.
proof fn lemma_unlink(s: SS2, k: int, t: SS2)
    requires inv03s(s), s.rows.contains_key(k), t == unlink(s, k),
    ensures inv03s(t), step_or_stutter::<StmtL1>(abss(s), Some(SL1::DDelete { k }), abss(t)),
{
    assert(live_stmts(t.stmt) =~= drop_stmts_of(live_stmts(s.stmt), k)) by {
        assert forall|j: nat| #[trigger] live_stmts(s.stmt).contains_key(j) && live_stmts(s.stmt)[j].k == k implies
            !live_stmts(t.stmt).contains_key(j) by {
            assert(s.stmt.contains_key(j) && s.stmt[j].live);
        }
        assert forall|j: nat| #[trigger] live_stmts(t.stmt).contains_key(j) implies
            live_stmts(s.stmt).contains_key(j) && live_stmts(s.stmt)[j].k != k by {
            assert(s.stmt.contains_key(j) && s.stmt[j].live);
            if s.stmt[j].k == k { assert(s.tuple.contains_key(k) && s.tuple[k] == j); }
        }
    }
    lemma_l1_safe(abss(s), SL1::DDelete { k }, abss(t));
    assert forall|x: int| #[trigger] t.tuple.contains_key(x) implies
        t.stmt.contains_key(t.tuple[x]) && t.stmt[t.tuple[x]].live && t.stmt[t.tuple[x]].k == x by {
        assert(s.tuple.contains_key(x));
        if s.tuple.contains_key(k) { assert(s.tuple[x] != s.tuple[k]); }
    }
    assert forall|j: nat| #[trigger] t.stmt.contains_key(j) && t.stmt[j].live implies
        t.tuple.contains_key(t.stmt[j].k) && t.tuple[t.stmt[j].k] == j by {
        assert(s.stmt.contains_key(j) && s.stmt[j].live);
    }
}

proof fn lemma_ddelete(s: SS2, k: int, t: SS2)
    requires inv03s(s), step2(s, SL2::DDelete { k }, t),
    ensures inv03s(t), step_or_stutter::<StmtL1>(abss(s), labs(SL2::DDelete { k }), abss(t)),
{
    // delete_edge goes through EraseEdgeRow: the triple's statement and tuple entry go with the row
    // (control F-0303 fails here)
    assert(t == unlink(s, k));
    lemma_unlink(s, k, t);
}

proof fn lemma_enode(s: SS2, k: int, t: SS2)
    requires inv03s(s), step2(s, SL2::ENode { k }, t),
    ensures inv03s(t), step_or_stutter::<StmtL1>(abss(s), labs(SL2::ENode { k }), abss(t)),
{
    lemma_unlink(s, k, t);
}

pub proof fn lemma_step(s: SS2, l: SL2, t: SS2)
    requires inv03s(s), step2(s, l, t),
    ensures inv03s(t), step_or_stutter::<StmtL1>(abss(s), labs(l), abss(t)),
{
    match l {
        SL2::LCreate { k, id } => lemma_lcreate(s, k, id, t),
        SL2::LUpdate { k, id } => lemma_lupdate(s, k, id, t),
        SL2::LDelete { k, id } => lemma_ldelete(s, k, id, t),
        SL2::DCreate { k } => lemma_dcreate(s, k, t),
        SL2::DDelete { k } => lemma_ddelete(s, k, t),
        SL2::ENode { k } => lemma_enode(s, k, t),
    }
}

impl Refines<StmtL1> for StmtL2 {
    open spec fn abs(s: SS2) -> SS1 { abss(s) }
    open spec fn lab(l: SL2) -> Option<SL1> { labs(l) }
    proof fn init_refines(s: SS2) { assert(live_stmts(s.stmt) =~= Map::<nat, St>::empty()); }
    proof fn step_refines(s: SS2, l: SL2, t: SS2) { lemma_step(s, l, t); }
}

impl SafeContract for StmtL2 {
    open spec fn inv(s: SS2) -> bool { inv03s(s) }
    proof fn init_safe(s: SS2) { assert(live_stmts(s.stmt) =~= Map::<nat, St>::empty()); }
    proof fn step_safe(s: SS2, l: SL2, t: SS2) { lemma_step(s, l, t); }
}

// ------------------------------------------------------------------------------------------------ theorems

proof fn lemma_raw_inv_at(states: Seq<SS2>, labels: Seq<SL2>, k: int)
    requires execution::<StmtRaw>(states, labels), 0 <= k < states.len(),
    ensures inv03s(states[k]),
    decreases k,
{
    if k == 0 {
        assert(live_stmts(states[0].stmt) =~= Map::<nat, St>::empty());
    } else {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution every state of which satisfies L1's business invariant.
pub proof fn theorem_raw_executions_refine(states: Seq<SS2>, labels: Seq<SL2>)
    requires execution::<StmtRaw>(states, labels),
    ensures
        execution::<StmtL2>(states, labels),
        abstract_execution::<StmtL1>(Seq::new(states.len(), |i: int| abss(states[i])),
                                     Seq::new(labels.len(), |i: int| labs(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv03s(#[trigger] states[i]) && inv1(abss(states[i])),
{
    assert forall|i: int| 0 <= i < states.len() implies inv03s(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<StmtL2>(states, labels));
    trace_refines::<StmtL2, StmtL1>(states, labels);
    refinement_preserves_safety::<StmtL2, StmtL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| abss(states[i])) =~= Seq::new(states.len(), |i: int| <StmtL2 as Refines<StmtL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labs(labels[i])) =~= Seq::new(labels.len(), |i: int| <StmtL2 as Refines<StmtL1>>::lab(labels[i])));
}

/// INV-stmt on the layout: a tuple entry names a live statement of the triple's current row (an op by tuple can only
/// reach the statement of the edge it finds).
pub proof fn theorem_tuple_entry_names_current_row(s: SS2, k: int)
    requires inv03s(s), s.tuple.contains_key(k),
    ensures s.rows.contains_key(k), s.stmt[s.tuple[k]].life == s.rows[k],
{
    lemma_live_named(s, s.tuple[k]);
}

} // verus!
