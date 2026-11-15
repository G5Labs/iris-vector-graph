//! Modules 03 and 05 (with module 12's prefix erase), L2: the structural-versus-temporal edge over the stored layout at
//! pin 3eaa79cf; refinement of `edge_l1` for every step, the invariant, and the controls F-0304, F-0505, F-0507,
//! F-C0501, HD-0302, F-C1203, F-C0301.
//!
//! State (production names; the adjacency index of spec 252 declared, `Adjacency.Indexed()`):
//! - `rows`  Graph_KG.rdf_edges (s, p, o_id, graph_id, qualifiers) at ekey 0, one per triple, with its qualifiers'
//!           kind: `Marked` = {"temporal": true} (AssertTemporalRow's marker, Adjacency.cls:590-595), `Plain` = an
//!           explicit writer's qualifiers, `TOne` = an explicit writer's qualifiers holding "temporal": 1 (or "1")
//! - `out`   ^KG("out", g, s, p, o) / ^KG("in", g, o, p, s), written and removed by the row's functional index
//! - `tout`  ^KG("tout", g, ts, s, p, o) (re-indexed by triple; the weight is `tagg_l2`'s), `tin` ^KG("tin", g, ts, o, p, s)
//! - `nodes` Graph_KG.nodes (node_id, graph_id)
//! - `reg`   ^IVG.TemporalStructural(gKey, p) = 0: the temporal-only predicates (TemporalPolicy.cls:31-39)
//! - `pend`  create_edge calls between their COMMIT and `_adopt_temporal_row` (as built only)
//!
//! **Reviewed design** (the findings' remedies and the working answers): store_edge adopts a marked row as create_edge
//! does (F-0304 remedy); one marker predicate for every deleter, JSON true only (F-0505 remedy); Purge retracts the
//! marked rows (F-0507 remedy); a refused temporal write writes nothing (F-C0501 remedy, its "assert the row first"
//! variant: the row and its endpoints inside a transaction before any temporal global, because $Increment, which
//! writes bucket and tagg, is not undone by a rollback, iris-contract E-INCR); a direct delete of a triple that keeps a
//! structural timestamp reverts its row to marked (HD-0302
//! working answer); a prefix erase selects the prefix's ids from the temporal index too (F-C1203 remedy); create_edge
//! adopts inside the guarded insert's transaction (F-C0301 remedy). Each control puts one as-built decision back.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::edge_l1::*;

verus! {

pub enum Q { Marked, Plain, TOne }
pub struct PA { pub k: K, pub q: Q }

pub struct ES2 {
    pub rows: Map<K, Q>,
    pub out: Set<K>,
    pub tout: Set<Ev>,
    pub tin: Set<Ev>,
    pub nodes: Set<NK>,
    pub reg: Set<GP>,
    pub pend: Map<nat, PA>,
}

pub enum EL2 {
    /// create_node (nodes_edges.py:968-...): a node row.
    CreateNode { nk: NK },
    /// create_edge (nodes_edges.py:1150-1252): one WriteTxn: endpoints, the guarded INSERT ... WHERE NOT EXISTS, and
    /// (reviewed) the adopt of a marked row; `res` None: the call has committed and not answered yet (as built).
    CInsert { c: nat, k: K, q: Q, res: Option<bool> },
    /// `_adopt_temporal_row` after the COMMIT (nodes_edges.py:1254-1304; as built only).
    CAdopt { c: nat, k: K, ans: bool },
    /// store_edge (nodes_edges.py:2532-2588): one WriteTxn: endpoints, INSERT, a duplicate swallowed.
    SStore { k: K, q: Q },
    /// delete_edge (nodes_edges.py:1382-1450).
    DDelete { k: K },
    /// create_edge_temporal -> InsertEdge -> WriteStores (TemporalIndex.cls:46-130) -> AssertTemporalRow
    /// (Adjacency.cls:575-621), mode insert.
    TInsert { k: K, ts: int },
    /// The same call when IRIS refuses the edge row's INSERT (SQLCODE -104/-415/-121: AssertTemporalRow throws).
    TRefuse { k: K, ts: int },
    /// delete_edge_temporal -> DeleteTemporalEdge (TemporalIndex.cls:325-346) -> RetractTemporalRow (Adjacency.cls:623-648).
    TDelete { k: K, ts: int },
    /// purge_raw_before -> PurgeRawBefore (TemporalIndex.cls:866-943) -> RetireExpired (944-1049) ->
    /// RetractTemporalRows (Adjacency.cls:650-692), pRetireNodes 0, tsStart 0.
    PurgeRaw { g: int, end: int },
    /// TemporalIndex.Purge (TemporalIndex.cls:808-811) -> EraseAll (381-392).
    TPurge,
    /// delete_nodes_by_prefix -> Eraser.EraseNodes (Eraser.cls:322-370) -> EraseIdSet (467-639) ->
    /// TemporalIndex.EraseNodes (TemporalIndex.cls:400-453), one transaction; `sel`: the ids the prefix selects.
    ENodes { g: int, sel: Set<int> },
}

pub open spec fn f0304() -> bool { cfg!(feature = "control_f0304_store_no_adopt") }
pub open spec fn f0505() -> bool { cfg!(feature = "control_f0505_marker_predicate") }
pub open spec fn f0507() -> bool { cfg!(feature = "control_f0507_purge_keeps_rows") }
pub open spec fn fc0501() -> bool { cfg!(feature = "control_fc0501_refused_write_partial") }
pub open spec fn hd0302() -> bool { cfg!(feature = "control_hd0302_delete_removes_row") }
pub open spec fn fc1203() -> bool { cfg!(feature = "control_fc1203_prefix_from_node_rows") }
pub open spec fn fc0301() -> bool { cfg!(feature = "control_fc0301_adopt_after_commit") }

/// The deleters' marker test. Reviewed: JSON true only, as the adopt (nodes_edges.py:1297) and LedgerGenesis read it.
/// As built (F-0505): IsTemporalMarked's `%Get("temporal") = 1` (Adjacency.cls:736-748) accepts 1 and "1" too.
pub open spec fn marked(q: Q) -> bool { q is Marked || (f0505() && q is TOne) }
/// What a row means: a marked row is derived (CONTEXT.md:72-73); any other row is an explicit assertion.
pub open spec fn prov(q: Q) -> Prov { if q is Marked { Prov::Derived } else { Prov::Explicit } }

/// RetireExpired's candidates that no surviving timestamp holds, structural (ADR-0015 skip), whose row is marked.
pub open spec fn retired(s: ES2, g: int, tout2: Set<Ev>, k: K) -> bool {
    k.g == g && has_ts(s.tout, k) && !has_ts(tout2, k) && structural(s.reg, k) && s.rows.contains_key(k) && marked(s.rows[k])
}
pub open spec fn purge_rows(s: ES2, g: int, tout2: Set<Ev>) -> Map<K, Q> {
    Map::new(s.rows.dom().filter(|k: K| !retired(s, g, tout2, k)), |k: K| s.rows[k])
}
pub open spec fn unmarked_rows(rows: Map<K, Q>) -> Map<K, Q> {
    Map::new(rows.dom().filter(|k: K| !marked(rows[k])), |k: K| rows[k])
}
/// n is an endpoint of a temporal edge of graph g.
pub open spec fn endpoint(tout: Set<Ev>, g: int, n: int) -> bool {
    exists|e: Ev| #[trigger] tout.contains(e) && e.k.g == g && (e.k.s == n || e.k.o == n)
}
/// The ids the prefix erase collects into ^||IVG.EraseIds. As built (F-C1203): the cursor over Graph_KG.nodes
/// (Eraser.cls:334-346). Reviewed: also the endpoints of the graph's temporal edges.
pub open spec fn ids_of(s: ES2, g: int, sel: Set<int>) -> Set<int> {
    if fc1203() { sel.filter(|n: int| s.nodes.contains(NK { g, n })) }
    else { sel.filter(|n: int| s.nodes.contains(NK { g, n }) || endpoint(s.tout, g, n)) }
}
pub open spec fn erase_rows(rows: Map<K, Q>, g: int, ids: Set<int>) -> Map<K, Q> {
    Map::new(rows.dom().filter(|k: K| !hit(g, ids, k)), |k: K| rows[k])
}

pub open spec fn init2(s: ES2) -> bool {
    &&& s.rows == Map::<K, Q>::empty() && s.out == Set::<K>::empty()
    &&& s.tout == Set::<Ev>::empty() && s.tin == Set::<Ev>::empty() && s.nodes == Set::<NK>::empty()
    &&& s.pend == Map::<nat, PA>::empty()
}

pub open spec fn step2(s: ES2, l: EL2, t: ES2) -> bool {
    match l {
        EL2::CreateNode { nk } => t == ES2 { nodes: s.nodes.insert(nk), ..s },
        EL2::CInsert { c, k, q, res } => {
            &&& !(q is Marked) && !s.pend.contains_key(c)
            &&& if !s.rows.contains_key(k) {
                    res == Some(true)
                        && t == ES2 { rows: s.rows.insert(k, q), out: s.out.insert(k), nodes: add_ends(s.nodes, k), ..s }
                } else if fc0301() {
                    // as built: txn.commit(), then _adopt_temporal_row as a statement of its own (nodes_edges.py:1236-1252)
                    res == None::<bool> && t == ES2 { nodes: add_ends(s.nodes, k), pend: s.pend.insert(c, PA { k, q }), ..s }
                } else if s.rows[k] is Marked {
                    res == Some(true) && t == ES2 { rows: s.rows.insert(k, q), nodes: add_ends(s.nodes, k), ..s }
                } else {
                    res == Some(false) && t == ES2 { nodes: add_ends(s.nodes, k), ..s }
                }
        },
        EL2::CAdopt { c, k, ans } => {
            &&& s.pend.contains_key(c) && s.pend[c].k == k
            &&& if s.rows.contains_key(k) && s.rows[k] is Marked {
                    ans && t == ES2 { rows: s.rows.insert(k, s.pend[c].q), pend: s.pend.remove(c), ..s }
                } else {
                    !ans && t == ES2 { pend: s.pend.remove(c), ..s }
                }
        },
        EL2::SStore { k, q } => {
            &&& !(q is Marked)
            &&& if !s.rows.contains_key(k) {
                    t == ES2 { rows: s.rows.insert(k, q), out: s.out.insert(k), nodes: add_ends(s.nodes, k), ..s }
                } else if !f0304() && s.rows[k] is Marked {
                    t == ES2 { rows: s.rows.insert(k, q), nodes: add_ends(s.nodes, k), ..s }
                } else {
                    t == ES2 { nodes: add_ends(s.nodes, k), ..s }
                }
        },
        EL2::DDelete { k } =>
            if !hd0302() && has_ts(s.tout, k) && structural(s.reg, k) {
                t == ES2 { rows: s.rows.insert(k, Q::Marked), out: s.out.insert(k), ..s }
            } else {
                t == ES2 { rows: s.rows.remove(k), out: s.out.remove(k), ..s }
            },
        EL2::TInsert { k, ts } =>
            if s.tout.contains(Ev { k, ts }) {
                t == s  // a collision changes no store (spec 254; TemporalIndex.cls:82-86)
            } else if structural(s.reg, k) && !s.out.contains(k) {
                t == ES2 { tout: s.tout.insert(Ev { k, ts }), tin: s.tin.insert(Ev { k, ts }), rows: s.rows.insert(k, Q::Marked),
                           out: s.out.insert(k), nodes: add_ends(s.nodes, k), ..s }
            } else {
                // a temporal-only predicate (IsStructuralKey, TemporalIndex.cls:104), or ^KG("out") already holds the
                // triple (pTrustIndex, Adjacency.cls:577-579)
                t == ES2 { tout: s.tout.insert(Ev { k, ts }), tin: s.tin.insert(Ev { k, ts }), ..s }
            },
        EL2::TRefuse { k, ts } => {
            &&& !s.tout.contains(Ev { k, ts }) && structural(s.reg, k) && !s.out.contains(k)
            &&& if fc0501() {
                    // as built: tout, tin (and bucket) are set before AssertTemporalRow, whose node INSERTs run before
                    // the refused edge INSERT; nothing takes them back (no TSTART in InsertEdge/WriteStores)
                    t == ES2 { tout: s.tout.insert(Ev { k, ts }), tin: s.tin.insert(Ev { k, ts }), nodes: add_ends(s.nodes, k), ..s }
                } else {
                    t == s
                }
        },
        EL2::TDelete { k, ts } => {
            &&& s.tout.contains(Ev { k, ts })
            &&& if !has_ts(s.tout.remove(Ev { k, ts }), k) && s.rows.contains_key(k) && marked(s.rows[k]) {
                    t == ES2 { tout: s.tout.remove(Ev { k, ts }), tin: s.tin.remove(Ev { k, ts }), rows: s.rows.remove(k),
                               out: s.out.remove(k), ..s }
                } else {
                    t == ES2 { tout: s.tout.remove(Ev { k, ts }), tin: s.tin.remove(Ev { k, ts }), ..s }
                }
        },
        EL2::PurgeRaw { g, end } =>
            t == ES2 { tout: purge_ts(s.tout, g, end), tin: purge_ts(s.tin, g, end),
                       rows: purge_rows(s, g, purge_ts(s.tout, g, end)),
                       out: s.out.filter(|k: K| !retired(s, g, purge_ts(s.tout, g, end), k)), ..s },
        EL2::TPurge =>
            t == ES2 { tout: Set::empty(), tin: Set::empty(),
                       rows: if f0507() { s.rows } else { unmarked_rows(s.rows) },
                       out: if f0507() { s.out } else { s.out.filter(|k: K| !(s.rows.contains_key(k) && marked(s.rows[k]))) }, ..s },
        EL2::ENodes { g, sel } =>
            t == ES2 { nodes: erase_nodes(s.nodes, g, ids_of(s, g, sel)), rows: erase_rows(s.rows, g, ids_of(s, g, sel)),
                       out: s.out.filter(|k: K| !hit(g, ids_of(s, g, sel), k)),
                       tout: erase_ts(s.tout, g, ids_of(s, g, sel)), tin: erase_ts(s.tin, g, ids_of(s, g, sel)), ..s },
    }
}

// ------------------------------------------------------------------------------------------------ the abstraction

pub open spec fn abs_edges(rows: Map<K, Q>) -> Map<K, Prov> { Map::new(rows.dom(), |k: K| prov(rows[k])) }
pub open spec fn abse(s: ES2) -> ES1 { ES1 { edges: abs_edges(s.rows), tev: s.tout, nodes: s.nodes, reg: s.reg } }

pub open spec fn labe(l: EL2) -> Option<EL1> {
    match l {
        EL2::CreateNode { nk } => Some(EL1::Node { nk }),
        EL2::CInsert { c, k, q, res } => match res { Some(b) => Some(EL1::Create { k, ans: b }), None => None },
        EL2::CAdopt { c, k, ans } => Some(EL1::Create { k, ans }),
        EL2::SStore { k, q } => Some(EL1::Store { k }),
        EL2::DDelete { k } => Some(EL1::Retract { k }),
        EL2::TInsert { k, ts } => Some(EL1::TWrite { k, ts, ok: true }),
        EL2::TRefuse { k, ts } => Some(EL1::TWrite { k, ts, ok: false }),
        EL2::TDelete { k, ts } => Some(EL1::TDelete { k, ts }),
        EL2::PurgeRaw { g, end } => Some(EL1::PurgeBefore { g, end }),
        EL2::TPurge => Some(EL1::Purge),
        EL2::ENodes { g, sel } => Some(EL1::EraseNodes { g, sel }),
    }
}

// ------------------------------------------------------------------------------------------------ invariant

/// The functional index: ^KG("out"/"in") holds exactly the rows' triples.
pub open spec fn inv_out(s: ES2) -> bool { forall|k: K| #[trigger] s.out.contains(k) <==> s.rows.contains_key(k) }
/// ^KG("tin") mirrors ^KG("tout") (no suppressReverseIndex).
pub open spec fn inv_tin(s: ES2) -> bool { s.tin == s.tout }
/// create_edge answers in the step of its guarded insert: no call is between its COMMIT and its adopt.
pub open spec fn inv_pend(s: ES2) -> bool { forall|c: nat| !(#[trigger] s.pend.contains_key(c)) }
pub open spec fn inv0305(s: ES2) -> bool { inv1(abse(s)) && inv_out(s) && inv_tin(s) && inv_pend(s) }

pub struct EdgeL2;

impl Contract for EdgeL2 {
    type S = ES2;
    type L = EL2;
    open spec fn init(s: ES2) -> bool { init2(s) }
    open spec fn next(s: ES2, l: EL2, t: ES2) -> bool { inv0305(s) && step2(s, l, t) }
}

pub struct EdgeRaw;

impl Contract for EdgeRaw {
    type S = ES2;
    type L = EL2;
    open spec fn init(s: ES2) -> bool { init2(s) }
    open spec fn next(s: ES2, l: EL2, t: ES2) -> bool { step2(s, l, t) }
}

// ------------------------------------------------------------------------------------------------ step lemmas

/// A row's triple has its endpoints (inv_fk through the abstraction).
proof fn lemma_row_ends(s: ES2, k: K)
    requires inv0305(s), s.rows.contains_key(k),
    ensures s.nodes.contains(NK { g: k.g, n: k.s }), s.nodes.contains(NK { g: k.g, n: k.o }), add_ends(s.nodes, k) == s.nodes,
{
    assert(abse(s).edges.contains_key(k));
    assert(add_ends(s.nodes, k) =~= s.nodes);
}

proof fn lemma_createnode(s: ES2, nk: NK, t: ES2)
    requires inv0305(s), step2(s, EL2::CreateNode { nk }, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::CreateNode { nk }), abse(t)),
{
    lemma_l1_safe(abse(s), EL1::Node { nk }, abse(t));
}

proof fn lemma_cinsert(s: ES2, c: nat, k: K, q: Q, res: Option<bool>, t: ES2)
    requires inv0305(s), step2(s, EL2::CInsert { c, k, q, res }, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::CInsert { c, k, q, res }), abse(t)),
{
    // create_edge answers in the step of its guarded insert: the adopt is in the same transaction
    // (control F-C0301 fails here)
    assert(res is Some);
    let b = res->Some_0;
    if !s.rows.contains_key(k) {
        assert(abs_edges(t.rows) =~= abs_edges(s.rows).insert(k, Prov::Explicit));
    } else {
        lemma_row_ends(s, k);
        assert(abs_edges(t.rows) =~= abs_edges(s.rows).insert(k, Prov::Explicit));
    }
    assert(EdgeL1::next(abse(s), EL1::Create { k, ans: b }, abse(t)));
    lemma_l1_safe(abse(s), EL1::Create { k, ans: b }, abse(t));
}

proof fn lemma_cadopt(s: ES2, c: nat, k: K, ans: bool, t: ES2)
    requires inv0305(s), step2(s, EL2::CAdopt { c, k, ans }, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::CAdopt { c, k, ans }), abse(t)),
{
    assert(s.pend.contains_key(c));  // never: inv_pend
}

proof fn lemma_sstore(s: ES2, k: K, q: Q, t: ES2)
    requires inv0305(s), step2(s, EL2::SStore { k, q }, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::SStore { k, q }), abse(t)),
{
    if !s.rows.contains_key(k) {
        assert(abs_edges(t.rows) =~= abs_edges(s.rows).insert(k, Prov::Explicit));
    } else {
        lemma_row_ends(s, k);
        if s.rows[k] is Marked {
            // store_edge adopts a marked row, as create_edge does (control F-0304 fails here)
            assert(t.rows == s.rows.insert(k, q));
        }
        assert(abs_edges(t.rows) =~= abs_edges(s.rows).insert(k, Prov::Explicit));
    }
    assert(EdgeL1::next(abse(s), EL1::Store { k }, abse(t)));
    lemma_l1_safe(abse(s), EL1::Store { k }, abse(t));
}

proof fn lemma_ddelete(s: ES2, k: K, t: ES2)
    requires inv0305(s), step2(s, EL2::DDelete { k }, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::DDelete { k }), abse(t)),
{
    if has_ts(s.tout, k) && structural(s.reg, k) {
        // the row of a triple that keeps a structural timestamp stays, reverted to marked (control HD-0302 fails here)
        assert(t.rows == s.rows.insert(k, Q::Marked));
        let w = choose|x: int| s.tout.contains(Ev { k, ts: x });
        assert(abse(s).tev.contains(Ev { k, ts: w }));
        assert(s.rows.contains_key(k));
        assert(abs_edges(t.rows) =~= abs_edges(s.rows).insert(k, Prov::Derived));
    } else {
        assert(abs_edges(t.rows) =~= abs_edges(s.rows).remove(k));
    }
    assert(EdgeL1::next(abse(s), EL1::Retract { k }, abse(t)));
    lemma_l1_safe(abse(s), EL1::Retract { k }, abse(t));
}

proof fn lemma_tinsert(s: ES2, k: K, ts: int, t: ES2)
    requires inv0305(s), step2(s, EL2::TInsert { k, ts }, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::TInsert { k, ts }), abse(t)),
{
    if s.tout.contains(Ev { k, ts }) {
    } else if structural(s.reg, k) && !s.out.contains(k) {
        assert(!s.rows.contains_key(k));
        assert(abs_edges(t.rows) =~= abs_edges(s.rows).insert(k, Prov::Derived));
    } else {
        assert(abs_edges(t.rows) =~= abs_edges(s.rows));
    }
    assert(EdgeL1::next(abse(s), EL1::TWrite { k, ts, ok: true }, abse(t)));
    lemma_l1_safe(abse(s), EL1::TWrite { k, ts, ok: true }, abse(t));
}

proof fn lemma_trefuse(s: ES2, k: K, ts: int, t: ES2)
    requires inv0305(s), step2(s, EL2::TRefuse { k, ts }, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::TRefuse { k, ts }), abse(t)),
{
    // a refused temporal write writes nothing: the row is asserted before any temporal global (control F-C0501 fails here)
    assert(t == s);
}

proof fn lemma_tdelete(s: ES2, k: K, ts: int, t: ES2)
    requires inv0305(s), step2(s, EL2::TDelete { k, ts }, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::TDelete { k, ts }), abse(t)),
{
    let e = Ev { k, ts };
    let tout2 = s.tout.remove(e);
    if !has_ts(tout2, k) && s.rows.contains_key(k) {
        // the last temporal delete retracts a marked row only: one marker predicate, JSON true (control F-0505 fails here)
        assert(marked(s.rows[k]) == (s.rows[k] is Marked));
    }
    let es = abs_edges(s.rows);
    assert forall|x: K| #[trigger] es.contains_key(x) && x != k && es[x] is Derived implies has_ts(tout2, x) by {
        assert(supported(abse(s), x));
        lemma_has_sub(s.tout, tout2, x);
    }
    assert(abs_edges(t.rows) =~= keep_supported(es, tout2));
    assert(EdgeL1::next(abse(s), EL1::TDelete { k, ts }, abse(t)));
    lemma_l1_safe(abse(s), EL1::TDelete { k, ts }, abse(t));
}

proof fn lemma_purgeraw(s: ES2, g: int, end: int, t: ES2)
    requires inv0305(s), step2(s, EL2::PurgeRaw { g, end }, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::PurgeRaw { g, end }), abse(t)),
{
    let tout2 = purge_ts(s.tout, g, end);
    let es = abs_edges(s.rows);
    // the purge's retraction (RetractTemporalRows, then RetractTemporalRow's IsTemporalMarked) takes marked rows only:
    // one marker predicate, JSON true (control F-0505 fails here)
    assert forall|x: K| #[trigger] s.rows.contains_key(x) implies marked(s.rows[x]) == (s.rows[x] is Marked) by {}
    assert forall|x: K| #[trigger] es.contains_key(x) && es[x] is Derived && x.g != g implies has_ts(tout2, x) by {
        assert(supported(abse(s), x));
        lemma_has_sub(s.tout, tout2, x);
    }
    assert forall|x: K| #[trigger] es.contains_key(x) && es[x] is Derived implies has_ts(s.tout, x) && structural(s.reg, x) by {
        assert(supported(abse(s), x));
    }
    assert(abs_edges(t.rows) =~= keep_supported(es, tout2));
    assert(EdgeL1::next(abse(s), EL1::PurgeBefore { g, end }, abse(t)));
    lemma_l1_safe(abse(s), EL1::PurgeBefore { g, end }, abse(t));
}

proof fn lemma_tpurge(s: ES2, t: ES2)
    requires inv0305(s), step2(s, EL2::TPurge, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::TPurge), abse(t)),
{
    let es = abs_edges(s.rows);
    // Purge retracts the marked rows its timestamps held up (control F-0507 fails here) ...
    assert forall|x: K| #[trigger] s.rows.contains_key(x) && s.rows[x] is Marked implies !t.rows.contains_key(x) by {}
    // ... and only those: one marker predicate, JSON true (control F-0505 fails here)
    assert forall|x: K| #[trigger] s.rows.contains_key(x) && !(s.rows[x] is Marked) implies
        t.rows.contains_key(x) && t.rows[x] == s.rows[x] by {}
    assert(abs_edges(t.rows) =~= keep_supported(es, Set::<Ev>::empty()));
    assert(EdgeL1::next(abse(s), EL1::Purge, abse(t)));
    lemma_l1_safe(abse(s), EL1::Purge, abse(t));
}

proof fn lemma_enodes(s: ES2, g: int, sel: Set<int>, t: ES2)
    requires inv0305(s), step2(s, EL2::ENodes { g, sel }, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(EL2::ENodes { g, sel }), abse(t)),
{
    let ids = ids_of(s, g, sel);
    assert forall|n: int| #[trigger] ids.contains(n) implies sel.contains(n) by {}
    assert forall|nk: NK| #[trigger] s.nodes.contains(nk) && nk.g == g && sel.contains(nk.n) implies ids.contains(nk.n) by {
        assert(nk == NK { g, n: nk.n });
    }
    assert(erase_nodes(s.nodes, g, ids) =~= erase_nodes(s.nodes, g, sel));
    assert forall|k: K| #[trigger] s.rows.contains_key(k) && hit(g, sel, k) implies hit(g, ids, k) by {
        assert(abse(s).edges.contains_key(k));
        assert(s.nodes.contains(NK { g: k.g, n: k.s }));
        assert(s.nodes.contains(NK { g: k.g, n: k.o }));
    }
    assert(abs_edges(t.rows) =~= erase_edges(abs_edges(s.rows), g, sel));
    // the prefix erase selects the prefix's ids from the temporal index too (control F-C1203 fails here)
    assert forall|e: Ev| #[trigger] s.tout.contains(e) && hit(g, sel, e.k) implies hit(g, ids, e.k) by {
        if sel.contains(e.k.s) { assert(endpoint(s.tout, g, e.k.s)); } else { assert(endpoint(s.tout, g, e.k.o)); }
    }
    assert(erase_ts(s.tout, g, ids) =~= erase_ts(s.tout, g, sel));
    assert(EdgeL1::next(abse(s), EL1::EraseNodes { g, sel }, abse(t)));
    lemma_l1_safe(abse(s), EL1::EraseNodes { g, sel }, abse(t));
}

pub proof fn lemma_step(s: ES2, l: EL2, t: ES2)
    requires inv0305(s), step2(s, l, t),
    ensures inv0305(t), step_or_stutter::<EdgeL1>(abse(s), labe(l), abse(t)),
{
    match l {
        EL2::CreateNode { nk } => lemma_createnode(s, nk, t),
        EL2::CInsert { c, k, q, res } => lemma_cinsert(s, c, k, q, res, t),
        EL2::CAdopt { c, k, ans } => lemma_cadopt(s, c, k, ans, t),
        EL2::SStore { k, q } => lemma_sstore(s, k, q, t),
        EL2::DDelete { k } => lemma_ddelete(s, k, t),
        EL2::TInsert { k, ts } => lemma_tinsert(s, k, ts, t),
        EL2::TRefuse { k, ts } => lemma_trefuse(s, k, ts, t),
        EL2::TDelete { k, ts } => lemma_tdelete(s, k, ts, t),
        EL2::PurgeRaw { g, end } => lemma_purgeraw(s, g, end, t),
        EL2::TPurge => lemma_tpurge(s, t),
        EL2::ENodes { g, sel } => lemma_enodes(s, g, sel, t),
    }
}

impl Refines<EdgeL1> for EdgeL2 {
    open spec fn abs(s: ES2) -> ES1 { abse(s) }
    open spec fn lab(l: EL2) -> Option<EL1> { labe(l) }
    proof fn init_refines(s: ES2) {
        assert(abs_edges(s.rows) =~= Map::<K, Prov>::empty());
    }
    proof fn step_refines(s: ES2, l: EL2, t: ES2) { lemma_step(s, l, t); }
}

impl SafeContract for EdgeL2 {
    open spec fn inv(s: ES2) -> bool { inv0305(s) }
    proof fn init_safe(s: ES2) {
        assert(abs_edges(s.rows) =~= Map::<K, Prov>::empty());
    }
    proof fn step_safe(s: ES2, l: EL2, t: ES2) { lemma_step(s, l, t); }
}

// ------------------------------------------------------------------------------------------------ theorems

proof fn lemma_raw_inv_at(states: Seq<ES2>, labels: Seq<EL2>, k: int)
    requires execution::<EdgeRaw>(states, labels), 0 <= k < states.len(),
    ensures inv0305(states[k]),
    decreases k,
{
    if k == 0 {
        assert(abs_edges(states[0].rows) =~= Map::<K, Prov>::empty());
    } else {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution every state of which satisfies L1's business invariant.
pub proof fn theorem_raw_executions_refine(states: Seq<ES2>, labels: Seq<EL2>)
    requires execution::<EdgeRaw>(states, labels),
    ensures
        execution::<EdgeL2>(states, labels),
        abstract_execution::<EdgeL1>(Seq::new(states.len(), |i: int| abse(states[i])),
                                     Seq::new(labels.len(), |i: int| labe(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv0305(#[trigger] states[i]) && inv1(abse(states[i])),
{
    assert forall|i: int| 0 <= i < states.len() implies inv0305(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<EdgeL2>(states, labels));
    trace_refines::<EdgeL2, EdgeL1>(states, labels);
    refinement_preserves_safety::<EdgeL2, EdgeL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| abse(states[i])) =~= Seq::new(states.len(), |i: int| <EdgeL2 as Refines<EdgeL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labe(labels[i])) =~= Seq::new(labels.len(), |i: int| <EdgeL2 as Refines<EdgeL1>>::lab(labels[i])));
}

/// ADR-0009 on the layout: ^KG("out") (what MATCH, BFS and centrality read) holds every triple ^KG("tout") holds for a
/// structural predicate, through its row.
pub proof fn theorem_adjacency_holds_every_structural_temporal_edge(s: ES2, e: Ev)
    requires inv0305(s), s.tout.contains(e), structural(s.reg, e.k),
    ensures s.rows.contains_key(e.k), s.out.contains(e.k),
{
    assert(abse(s).tev.contains(e));
    assert(abse(s).edges.contains_key(e.k));
}

/// ADR-0009 amendment and ADR-0015 on the layout: a row carrying the marker has a timestamp in ^KG("tout") and a
/// structural predicate.
pub proof fn theorem_marked_row_has_time(s: ES2, k: K)
    requires inv0305(s), s.rows.contains_key(k), s.rows[k] is Marked,
    ensures has_ts(s.tout, k), structural(s.reg, k),
{
    assert(abse(s).edges.contains_key(k));
}

} // verus!
