// product 3eaa79cf: maintenance of the adjacency ^KG("out"/"in", graph, ...) from a history of row writes and deletes
// (structure.adjacency*, structure.multigraph*, structure.degree*, structure.rebuilt*, structure.rebuild,
// structure.edge.delete, structure.node.delete).
//   With the declared adjacency index (Graph.KG.AdjIndex, IndexKind "functional", the fixture's state) every
//   rdf_edges INSERT / DELETE / UPDATE calls Adjacency.RowPut / RowRemove / RowUpdate (Adjacency.cls:477-534):
//   Put / Remove for a graph not in multigraph mode, PutKeyed / RemoveKeyed (210-321) in multigraph mode.
//   Graph.KG.Eraser (store.delete_edges, store.delete_nodes, engine.delete_node, delete_nodes_by_prefix) erases every
//   row of each triple it touches (EraseEdgeRow) and then calls Adjacency.Remove on the triple (Eraser.cls:450, 668).
//   sync() = BuildKG: with the index, PurgeIndex then %BuildIndices, i.e. RowPut for every row, in some order, while
//   every row is visible to OtherEdgeKeys (TraversalBuild.cls:126-136).
// The adjacency state is never an input: rows_at / adj_at fold the modeled history; canon is the rebuild's answer.
// Weights are integers here (the product stores +weight; the binding uses integer weights).
use vstd::prelude::*;
use vstd::set_lib::*;
verus! {

pub struct Tr { pub g: int, pub s: int, pub p: int, pub o: int }

/// One ^KG("out", g, s, p, o) entry: the leaf value, and the keyed children (ekey -> weight) that exist only
/// while a multigraph triple has two or more edges (then "#" = their count).
pub struct Entry { pub leaf: int, pub kids: Map<int, int> }

#[verifier::opaque]
pub open spec fn empty_m(m: Map<int, int>) -> bool { forall|x: int| !m.dom().contains(x) }
#[verifier::opaque]
pub open spec fn single(m: Map<int, int>) -> bool {
    exists|k: int| m.dom().contains(k) && (forall|x: int| #[trigger] m.dom().contains(x) ==> x == k)
}
pub open spec fn the_w(m: Map<int, int>) -> int { let k = choose|k: int| m.dom().contains(k); m[k] }
/// SetLeafFromLowest: the weight of the lowest live ekey.
pub open spec fn lowest_w(m: Map<int, int>) -> int {
    let k = choose|k: int| m.dom().contains(k) && (forall|j: int| #[trigger] m.dom().contains(j) ==> k <= j);
    m[k]
}

/// The rebuild's answer for one triple from its rows (ekey -> weight) (FillTriple / %BuildIndices).
pub open spec fn canon(multi: bool, rows: Map<int, int>) -> Option<Entry> {
    if empty_m(rows) { None }
    else if multi && !single(rows) { Some(Entry { leaf: lowest_w(rows), kids: rows }) }
    else { Some(Entry { leaf: the_w(rows), kids: Map::empty() }) }
}

// ---- the writers (Adjacency.cls) ----
/// Put (80-109): a bare leaf with the weight.
pub open spec fn put(w: int) -> Option<Entry> { Some(Entry { leaf: w, kids: Map::empty() }) }

/// PutKeyed (210-269); `others` = OtherEdgeKeys: the triple's rows under another ekey, as the row's index sees them.
pub open spec fn put_keyed(e: Option<Entry>, others: Map<int, int>, k: int, w: int) -> Option<Entry> {
    match e {
        None => put(w),
        Some(en) => {
            if empty_m(en.kids) && empty_m(others) { put(w) }
            else {
                let base = if empty_m(en.kids) {
                    if single(others) { Map::new(others.dom(), |x: int| en.leaf) } else { others }
                } else { en.kids };
                let kids2 = base.insert(k, w);
                Some(Entry { leaf: lowest_w(kids2), kids: kids2 })
            }
        }
    }
}

/// RemoveKeyed (275-321).
pub open spec fn remove_keyed(e: Option<Entry>, others: Map<int, int>, k: int) -> Option<Entry> {
    match e {
        None => None,
        Some(en) => {
            if empty_m(en.kids) { if !empty_m(others) { e } else { None } }
            else if !en.kids.dom().contains(k) { e }
            else {
                let k2 = en.kids.remove(k);
                if !empty_m(k2) && !single(k2) { Some(Entry { leaf: lowest_w(k2), kids: k2 }) }
                else if single(k2) { Some(Entry { leaf: the_w(k2), kids: Map::empty() }) }
                else { Some(Entry { leaf: en.leaf, kids: Map::empty() }) }
            }
        }
    }
}

/// RowPut / RowRemove (477-501): the graph's mode picks the writer.
pub open spec fn row_put(multi: bool, e: Option<Entry>, others: Map<int, int>, k: int, w: int) -> Option<Entry> {
    if multi { put_keyed(e, others, k, w) } else { put(w) }
}
pub open spec fn row_remove(multi: bool, e: Option<Entry>, others: Map<int, int>, k: int) -> Option<Entry> {
    if multi { remove_keyed(e, others, k) } else { None }
}
/// RowUpdate with the same edge and new qualifiers (517-533): a keyed child, then the leaf from the lowest; else Reweight.
pub open spec fn row_update(e: Option<Entry>, k: int, w: int) -> Option<Entry> {
    match e {
        None => None,
        Some(en) => if en.kids.dom().contains(k) {
            let k2 = en.kids.insert(k, w);
            Some(Entry { leaf: lowest_w(k2), kids: k2 })
        } else { Some(Entry { leaf: w, kids: en.kids }) },
    }
}

/// %BuildIndices after the purge: RowPut for every row in `order`, every row already visible.
pub open spec fn rebuild(multi: bool, rows: Map<int, int>, order: Seq<int>) -> Option<Entry>
    decreases order.len(),
{
    if order.len() == 0 { None }
    else {
        let k = order.last();
        row_put(multi, rebuild(multi, rows, order.drop_last()), rows.remove(k), k, rows[k])
    }
}

pub open spec fn enumerates(order: Seq<int>, rows: Map<int, int>) -> bool {
    order.no_duplicates() && (forall|x: int| #[trigger] rows.dom().contains(x) <==> order.contains(x))
}

/// The order %BuildIndices visits one triple's rows (a premise: each row once).
pub uninterp spec fn build_order(t: Tr, rows: Map<int, int>) -> Seq<int>;

// ---- the history ----
pub enum Op {
    /// create_edge, store.write_edges, Cypher CREATE: one INSERT (fresh ekey).
    Create { t: Tr, k: int, w: int },
    /// one row DELETE: Cypher DELETE r (by edge_id); engine.delete_edge is one DelRow per row of the triple
    /// in the graph (all_graphs: in every graph).
    DelRow { t: Tr, k: int },
    /// set_edge_weight's UPDATE of one row (default graph; one Update per row of the triple).
    Update { t: Tr, k: int, w: int },
    /// Graph.KG.Eraser: store.delete_edges(graph) on one triple.
    EraseTriple { t: Tr },
    /// Graph.KG.Eraser: engine.delete_node / store.delete_nodes (one id), delete_nodes_by_prefix (the ids).
    EraseNodes { g: int, ids: Set<int> },
    /// sync() = BuildKG.
    Sync,
}

pub open spec fn erases(op: Op, t: Tr) -> bool {
    match op {
        Op::EraseTriple { t: u } => u == t,
        Op::EraseNodes { g, ids } => t.g == g && (ids.contains(t.s) || ids.contains(t.o)),
        _ => false,
    }
}

pub open spec fn rows_step(op: Op, t: Tr, rows: Map<int, int>) -> Map<int, int> {
    if erases(op, t) { Map::empty() }
    else {
        match op {
            Op::Create { t: u, k, w } => if u == t { rows.insert(k, w) } else { rows },
            Op::DelRow { t: u, k } => if u == t { rows.remove(k) } else { rows },
            Op::Update { t: u, k, w } => if u == t && rows.dom().contains(k) { rows.insert(k, w) } else { rows },
            _ => rows,
        }
    }
}

pub open spec fn adj_step(mm: Set<int>, op: Op, t: Tr, rows: Map<int, int>, e: Option<Entry>) -> Option<Entry> {
    let multi = mm.contains(t.g);
    if erases(op, t) { None }   // every row of the triple, then Adjacency.Remove of the triple
    else {
        match op {
            Op::Create { t: u, k, w } => if u == t { row_put(multi, e, rows, k, w) } else { e },
            Op::DelRow { t: u, k } => if u == t && rows.dom().contains(k) { row_remove(multi, e, rows.remove(k), k) } else { e },
            Op::Update { t: u, k, w } => if u == t && rows.dom().contains(k) { row_update(e, k, w) } else { e },
            Op::Sync => rebuild(multi, rows, build_order(t, rows)),
            _ => e,
        }
    }
}

pub open spec fn rows_at(h: Seq<Op>, t: Tr) -> Map<int, int>
    decreases h.len(),
{
    if h.len() == 0 { Map::empty() } else { rows_step(h.last(), t, rows_at(h.drop_last(), t)) }
}

pub open spec fn adj_at(mm: Set<int>, h: Seq<Op>, t: Tr) -> Option<Entry>
    decreases h.len(),
{
    if h.len() == 0 { None }
    else { adj_step(mm, h.last(), t, rows_at(h.drop_last(), t), adj_at(mm, h.drop_last(), t)) }
}

/// The domain: an INSERT takes a fresh ekey (unique key (s, p, o_id, graph_id, ekey)); a graph not in multigraph
/// mode holds one row per triple (create_edge's guard, write_edges' duplicate skip); %BuildIndices visits each row once.
pub open spec fn op_ok(mm: Set<int>, op: Op, prev: Seq<Op>) -> bool {
    match op {
        Op::Create { t, k, w } => !rows_at(prev, t).dom().contains(k) && (mm.contains(t.g) || empty_m(rows_at(prev, t))),
        Op::Sync => forall|t: Tr| enumerates(#[trigger] build_order(t, rows_at(prev, t)), rows_at(prev, t)),
        _ => true,
    }
}

pub open spec fn admissible(mm: Set<int>, h: Seq<Op>) -> bool
    decreases h.len(),
{
    h.len() == 0 || (admissible(mm, h.drop_last()) && op_ok(mm, h.last(), h.drop_last()))
}

pub open spec fn inv(multi: bool, rows: Map<int, int>, e: Option<Entry>) -> bool {
    e == canon(multi, rows) && (multi || empty_m(rows) || single(rows))
}

// ---- small lemmas (empty_m and single are opaque; these are their only unfoldings) ----
pub proof fn lemma_single_intro(m: Map<int, int>, k: int)
    requires m.dom().contains(k), forall|x: int| #[trigger] m.dom().contains(x) ==> x == k,
    ensures the_w(m) == m[k], single(m), !empty_m(m),
{
    reveal(single); reveal(empty_m);
    let j = choose|j: int| m.dom().contains(j);
    assert(m.dom().contains(j));
}

pub proof fn lemma_single_elim(m: Map<int, int>) -> (k: int)
    requires single(m),
    ensures m.dom().contains(k), forall|x: int| #[trigger] m.dom().contains(x) ==> x == k, the_w(m) == m[k], !empty_m(m),
{
    reveal(single);
    let k = choose|k: int| m.dom().contains(k) && (forall|x: int| #[trigger] m.dom().contains(x) ==> x == k);
    lemma_single_intro(m, k);
    k
}

pub proof fn lemma_empty_intro(m: Map<int, int>)
    requires forall|x: int| !(#[trigger] m.dom().contains(x)),
    ensures empty_m(m), !single(m),
{
    reveal(single); reveal(empty_m);
}

pub proof fn lemma_empty_elim(m: Map<int, int>, x: int)
    requires empty_m(m),
    ensures !m.dom().contains(x), !single(m),
{
    reveal(single); reveal(empty_m);
}

pub proof fn lemma_empty_map()
    ensures empty_m(Map::<int, int>::empty()), !single(Map::<int, int>::empty()),
{
    reveal(single); reveal(empty_m);
}

pub proof fn lemma_nonempty_witness(m: Map<int, int>) -> (a: int)
    requires !empty_m(m),
    ensures m.dom().contains(a),
{
    reveal(empty_m);
    choose|a: int| m.dom().contains(a)
}

pub proof fn lemma_two_not_single(m: Map<int, int>, a: int, b: int)
    requires m.dom().contains(a), m.dom().contains(b), a != b,
    ensures !single(m), !empty_m(m),
{
    reveal(empty_m);
    if single(m) {
        let k = lemma_single_elim(m);
        assert(a == k && b == k);
    }
}

pub proof fn lemma_two_witness(m: Map<int, int>) -> (r: (int, int))
    requires !empty_m(m), !single(m),
    ensures m.dom().contains(r.0), m.dom().contains(r.1), r.0 != r.1,
{
    let a = lemma_nonempty_witness(m);
    if forall|x: int| #[trigger] m.dom().contains(x) ==> x == a {
        lemma_single_intro(m, a);
    }
    let b = choose|b: int| m.dom().contains(b) && b != a;
    (a, b)
}

pub proof fn lemma_create(multi: bool, rows: Map<int, int>, e: Option<Entry>, k: int, w: int)
    requires inv(multi, rows, e), !rows.dom().contains(k), multi || empty_m(rows),
    ensures inv(multi, rows.insert(k, w), row_put(multi, e, rows, k, w)),
{
    let r2 = rows.insert(k, w);
    lemma_empty_map();
    if empty_m(rows) {
        assert forall|x: int| #[trigger] r2.dom().contains(x) implies x == k by { lemma_empty_elim(rows, x); }
        lemma_single_intro(r2, k);
    } else if single(rows) {
        let j = lemma_single_elim(rows);
        lemma_two_not_single(r2, j, k);
        let base = Map::new(rows.dom(), |x: int| rows[j]);
        assert(base =~= rows);
        lemma_two_not_single(r2, j, k);
    } else {
        let (a, b) = lemma_two_witness(rows);
        lemma_two_not_single(r2, a, b);
    }
}

pub proof fn lemma_delrow(multi: bool, rows: Map<int, int>, e: Option<Entry>, k: int)
    requires inv(multi, rows, e), rows.dom().contains(k),
    ensures inv(multi, rows.remove(k), row_remove(multi, e, rows.remove(k), k)),
{
    let o = rows.remove(k);
    lemma_empty_map();
    if empty_m(rows) { lemma_empty_elim(rows, k); }
    if single(rows) {
        let j = lemma_single_elim(rows);
        assert forall|x: int| !(#[trigger] o.dom().contains(x)) by {}
        lemma_empty_intro(o);
    } else {
        let (a, b) = lemma_two_witness(rows);
        let c = if a != k { a } else { b };
        assert(o.dom().contains(c));
        if empty_m(o) { lemma_empty_elim(o, c); }
        assert(multi);
        if single(o) {
            let z = lemma_single_elim(o);
        }
    }
}

pub proof fn lemma_update(multi: bool, rows: Map<int, int>, e: Option<Entry>, k: int, w: int)
    requires inv(multi, rows, e), rows.dom().contains(k),
    ensures inv(multi, rows.insert(k, w), row_update(e, k, w)),
{
    let r2 = rows.insert(k, w);
    lemma_empty_map();
    if empty_m(rows) { lemma_empty_elim(rows, k); }
    if single(rows) {
        let j = lemma_single_elim(rows);
        assert forall|x: int| #[trigger] r2.dom().contains(x) implies x == k by {}
        lemma_single_intro(r2, k);
    } else {
        let (a, b) = lemma_two_witness(rows);
        lemma_two_not_single(r2, a, b);
        assert(multi);
    }
}

/// The step preserves the invariant: incremental maintenance stays equal to the rebuild's answer.
pub proof fn lemma_step(mm: Set<int>, op: Op, t: Tr, rows: Map<int, int>, e: Option<Entry>, prev: Seq<Op>)
    requires inv(mm.contains(t.g), rows, e), rows == rows_at(prev, t), op_ok(mm, op, prev),
    ensures inv(mm.contains(t.g), rows_step(op, t, rows), adj_step(mm, op, t, rows, e)),
{
    let multi = mm.contains(t.g);
    lemma_empty_map();
    if erases(op, t) {
        return;
    }
    match op {
        Op::Create { t: u, k, w } => { if u == t { lemma_create(multi, rows, e, k, w); } }
        Op::DelRow { t: u, k } => {
            if u == t && rows.dom().contains(k) { lemma_delrow(multi, rows, e, k); }
            else if u == t { assert(rows.remove(k) =~= rows); }
        }
        Op::Update { t: u, k, w } => { if u == t && rows.dom().contains(k) { lemma_update(multi, rows, e, k, w); } }
        Op::Sync => {
            assert(enumerates(build_order(t, rows_at(prev, t)), rows_at(prev, t)));
            lemma_rebuild(multi, rows, build_order(t, rows));
        }
        _ => {}
    }
}

pub proof fn lemma_second(rows: Map<int, int>, j: int, k: int)
    requires rows.dom().contains(j), rows.dom().contains(k), j != k,
    ensures put_keyed(put(rows[j]), rows.remove(k), k, rows[k]) == Some(Entry { leaf: lowest_w(rows), kids: rows }),
{
    lemma_empty_map();
    let others = rows.remove(k);
    assert(others.dom().contains(j));
    if empty_m(others) { lemma_empty_elim(others, j); }
    if single(others) {
        let z = lemma_single_elim(others);
        let base = Map::new(others.dom(), |x: int| rows[j]);
        assert(base =~= others);
    }
    assert(others.insert(k, rows[k]) =~= rows);
}

pub proof fn lemma_third(rows: Map<int, int>, k: int)
    requires rows.dom().contains(k),
    ensures put_keyed(Some(Entry { leaf: lowest_w(rows), kids: rows }), rows.remove(k), k, rows[k]) == Some(Entry { leaf: lowest_w(rows), kids: rows }),
{
    if empty_m(rows) { lemma_empty_elim(rows, k); }
    assert(rows.insert(k, rows[k]) =~= rows);
}

/// The rebuild's prefix states (any visiting order).
pub proof fn lemma_rebuild_prefix(multi: bool, rows: Map<int, int>, order: Seq<int>, i: int)
    requires enumerates(order, rows), 1 <= i <= order.len(),
    ensures
        i == 1 ==> rebuild(multi, rows, order.take(i)) == put(rows[order[0]]),
        (i >= 2 && multi) ==> rebuild(multi, rows, order.take(i)) == Some(Entry { leaf: lowest_w(rows), kids: rows }),
        (i >= 2 && !multi) ==> rebuild(multi, rows, order.take(i)) == put(rows[order[i - 1]]),
    decreases i,
{
    let pre = order.take(i);
    let k = order[i - 1];
    assert(pre.drop_last() =~= order.take(i - 1));
    assert(pre.last() == k);
    let prev = rebuild(multi, rows, order.take(i - 1));
    assert(rebuild(multi, rows, pre) == row_put(multi, prev, rows.remove(k), k, rows[k]));
    if i == 1 {
        assert(order.take(0) =~= Seq::<int>::empty());
        assert(prev == None::<Entry>);
    } else {
        lemma_rebuild_prefix(multi, rows, order, i - 1);
        assert(order.contains(k));
        assert(order.contains(order[0]));
        if multi {
            if i == 2 {
                lemma_second(rows, order[0], k);
            } else {
                lemma_third(rows, k);
            }
        }
    }
}

pub proof fn lemma_rebuild(multi: bool, rows: Map<int, int>, order: Seq<int>)
    requires enumerates(order, rows), multi || empty_m(rows) || single(rows),
    ensures rebuild(multi, rows, order) == canon(multi, rows),
{
    assert(order.take(order.len() as int) =~= order);
    if order.len() == 0 {
        assert forall|x: int| !(#[trigger] rows.dom().contains(x)) by { if rows.dom().contains(x) { assert(order.contains(x)); } }
        lemma_empty_intro(rows);
    } else {
        lemma_rebuild_prefix(multi, rows, order, order.len() as int);
        assert(order.contains(order[0]));
        if order.len() == 1 {
            assert forall|x: int| #[trigger] rows.dom().contains(x) implies x == order[0] by {
                assert(order.contains(x));
                let i = choose|i: int| 0 <= i < order.len() && order[i] == x;
            }
            lemma_single_intro(rows, order[0]);
        } else {
            assert(order.contains(order[1]));
            assert(order[0] != order[1]);
            lemma_two_not_single(rows, order[0], order[1]);
        }
    }
}

/// (b) Rebuild from rows == incremental state, for every admissible history and every triple.
pub proof fn theorem_incremental_equals_rebuild(mm: Set<int>, h: Seq<Op>, t: Tr)
    requires admissible(mm, h),
    ensures inv(mm.contains(t.g), rows_at(h, t), adj_at(mm, h, t)),
        adj_at(mm, h, t) == canon(mm.contains(t.g), rows_at(h, t)),
    decreases h.len(),
{
    lemma_empty_map();
    if h.len() == 0 {
        assert(rows_at(h, t) =~= Map::<int, int>::empty());
    } else {
        theorem_incremental_equals_rebuild(mm, h.drop_last(), t);
        lemma_step(mm, h.last(), t, rows_at(h.drop_last(), t), adj_at(mm, h.drop_last(), t), h.drop_last());
    }
}

/// R1: a sync() leaves every triple's entry as it was (no drift).
pub proof fn theorem_sync_changes_nothing(mm: Set<int>, h: Seq<Op>, t: Tr)
    requires admissible(mm, h.push(Op::Sync)),
    ensures adj_at(mm, h.push(Op::Sync), t) == adj_at(mm, h, t),
{
    let h2 = h.push(Op::Sync);
    assert(h2.drop_last() =~= h);
    theorem_incremental_equals_rebuild(mm, h, t);
    theorem_incremental_equals_rebuild(mm, h2, t);
}

// ---- (a) per-writer effects ----
/// D2 / D1: a delete in graph g leaves a triple of another graph (the same s, p, o) as it was.
pub proof fn theorem_other_graph_untouched(mm: Set<int>, op: Op, t: Tr, rows: Map<int, int>, e: Option<Entry>, g: int)
    requires t.g != g,
        match op {
            Op::DelRow { t: u, k } => u.g == g,
            Op::EraseTriple { t: u } => u.g == g,
            Op::EraseNodes { g: gg, ids } => gg == g,
            Op::Update { t: u, k, w } => u.g == g,
            _ => false,
        },
    ensures rows_step(op, t, rows) == rows, adj_step(mm, op, t, rows, e) == e,
{}

/// D1 / D4 (edges): erasing ids in g takes every g triple with an erased end, rows and entry.
pub proof fn theorem_erase_nodes_takes_incident(mm: Set<int>, g: int, ids: Set<int>, t: Tr, rows: Map<int, int>, e: Option<Entry>)
    requires t.g == g, ids.contains(t.s) || ids.contains(t.o),
    ensures empty_m(rows_step(Op::EraseNodes { g, ids }, t, rows)), adj_step(mm, Op::EraseNodes { g, ids }, t, rows, e) == None::<Entry>,
{
    lemma_empty_map();
}

/// The degree contribution of one entry (Graph.KG.Adj.Count: a "#" counts its edges, a bare leaf one).
pub open spec fn contrib(e: Option<Entry>) -> int {
    match e { None => 0, Some(en) => if empty_m(en.kids) { 1 } else { en.kids.dom().len() as int } }
}

/// D3: Cypher DELETE r of one of two parallel edges of a multigraph triple leaves the other: the target is still
/// reached, the leaf carries the survivor's weight, the degree contribution drops from 2 to 1.
pub proof fn theorem_delete_one_parallel_keeps_other(k1: int, k2: int, w1: int, w2: int)
    requires k1 != k2,
    ensures ({
        let rows = Map::<int, int>::empty().insert(k1, w1).insert(k2, w2);
        let e = canon(true, rows);
        let e2 = row_remove(true, e, rows.remove(k1), k1);
        &&& contrib(e) == 2
        &&& e2 == put(w2)
        &&& contrib(e2) == 1
        &&& e2 == canon(true, rows.remove(k1))
    }),
{
    let rows = Map::<int, int>::empty().insert(k1, w1).insert(k2, w2);
    lemma_two_not_single(rows, k1, k2);
    assert(rows.dom() =~= set![k1, k2]);
    assert(set![k1, k2].len() == 2) by {
        assert(set![k1].len() == 1);
    }
    let r1 = rows.remove(k1);
    assert(r1.dom().contains(k2));
    assert forall|x: int| #[trigger] r1.dom().contains(x) implies x == k2 by {}
    lemma_single_intro(r1, k2);
    lemma_single_intro(Map::<int, int>::empty().insert(k1, w1), k1);
    assert forall|x: int| !(#[trigger] Map::<int, int>::empty().dom().contains(x)) by {}
    lemma_empty_intro(Map::<int, int>::empty());
    assert(r1.remove(k2) =~= Map::<int, int>::empty());
}

/// D3 contrast: the same delete through a graph not in multigraph mode (Remove) takes the whole triple.
pub proof fn theorem_plain_delete_takes_triple(e: Option<Entry>, others: Map<int, int>, k: int)
    ensures row_remove(false, e, others, k) == None::<Entry>,
{}

// ---- ^NKG (merged across graphs; built by BuildNKG during sync) ----
/// Adjacency.Remove (161): the ^NKG edge goes only when the ^KG entry was there, ^NKG is built, and no other
/// graph holds the triple (HeldElsewhere).
pub open spec fn nkg_edge_after_remove(before: bool, had: bool, built: bool, held_elsewhere: bool) -> bool {
    if had && built && !held_elsewhere { false } else { before }
}
/// MarkGraphGone (174-181).
pub open spec fn marks_stale(g: int, g_has_out_left: bool, built: bool, an_end_interned: bool) -> bool {
    g != 0 && !g_has_out_left && built && an_end_interned
}

pub proof fn theorem_nkg_held_elsewhere(before: bool, had: bool, built: bool)
    ensures nkg_edge_after_remove(before, had, built, true) == before,
        (had && built) ==> !nkg_edge_after_remove(before, had, built, false),
{}

pub proof fn theorem_mark_graph_gone(g: int, interned: bool)
    ensures !marks_stale(0, false, true, true), (g != 0 && interned) ==> marks_stale(g, false, true, interned),
        !marks_stale(g, true, true, interned),
{}

// ---- labels: ^KG("label", g, label, s) mirrors rdf_labels (PutLabel / RemoveLabel per row) ----
pub struct Lab { pub g: int, pub l: int, pub n: int }

/// After an EraseNodes of ids in g: every label row of an erased id in g goes (RemoveLabel per row).
pub open spec fn label_kept(x: Lab, g: int, ids: Set<int>) -> bool { !(x.g == g && ids.contains(x.n)) }

/// D4: another node with the same label keeps it; the same id in another graph keeps it; the erased node loses it.
pub proof fn theorem_label_delete_scoped(g: int, ids: Set<int>, l: int, n: int, m: int, h: int)
    requires ids.contains(n), !ids.contains(m), h != g,
    ensures !label_kept(Lab { g, l, n }, g, ids), label_kept(Lab { g, l, n: m }, g, ids), label_kept(Lab { g: h, l, n }, g, ids),
{}

// ---- two-hop counts (Build2HopStats, Build2HopExactStats, KHop2CountFast / Exact) ----
pub open spec fn uni(ts: Seq<Set<int>>) -> Set<int>
    decreases ts.len(),
{
    if ts.len() == 0 { Set::empty() } else { uni(ts.drop_last()).union(ts.last()) }
}
pub open spec fn sum_len(ts: Seq<Set<int>>) -> int
    decreases ts.len(),
{
    if ts.len() == 0 { 0 } else { sum_len(ts.drop_last()) + ts.last().len() }
}
/// The walk (KHop2Count) and the exact stats: distinct second-hop targets that are neither the source nor a first-hop node.
pub open spec fn walk_count(ts: Seq<Set<int>>, x: Set<int>) -> int { uni(ts).difference(x).len() as int }

/// The readers: a precomputed count only while its stamp equals ^KG("__version") (Fresh) and it is stored (> 0).
pub open spec fn fast_answer(fresh: bool, sum: int, walk: int) -> int { if fresh && sum > 0 { sum } else { walk } }
pub open spec fn exact_answer(fresh: bool, stored: int, walk: int) -> int { if fresh && stored > 0 { stored } else { walk } }
pub open spec fn fresh(built_at: int, version: int) -> bool { built_at == version }

pub proof fn lemma_uni_le_sum(ts: Seq<Set<int>>)
    ensures uni(ts).len() <= sum_len(ts),
    decreases ts.len(),
{
    if ts.len() > 0 {
        let r = ts.drop_last();
        lemma_uni_le_sum(r);
        assert(ts.last() == ts[ts.len() - 1]);
        lemma_len_union(uni(r), ts.last());
    }
}

/// R2: fast is an upper bound of exact; a stale count is never read; fresh, exact = the walk.
pub proof fn theorem_two_hop(ts: Seq<Set<int>>, x: Set<int>, built_at: int, version: int)
    ensures ({
        let w = walk_count(ts, x);
        let f = fresh(built_at, version);
        &&& w <= sum_len(ts)
        &&& exact_answer(f, w, w) == w
        &&& fast_answer(f, sum_len(ts), w) >= w
        &&& !f ==> fast_answer(f, sum_len(ts), w) == w
    }),
{
    lemma_uni_le_sum(ts);
    lemma_len_difference(uni(ts), x);
}

/// Every edge write bumps ^KG("__version"), so stats built before it are stale.
pub proof fn theorem_write_makes_stale(built_at: int)
    ensures !fresh(built_at, built_at + 1),
{}

/// R2 witness: a diamond s->a, s->b, a->x, b->x: fast 2, exact 1; a back edge s->a, a->s: fast 1, exact 0.
pub proof fn witness_fast_overcounts(s: int, a: int, b: int, x: int)
    requires s != a, s != b, a != b, x != s, x != a, x != b,
    ensures
        sum_len(seq![set![x], set![x]]) == 2, walk_count(seq![set![x], set![x]], set![s, a, b]) == 1,
        sum_len(seq![set![s]]) == 1, walk_count(seq![set![s]], set![s, a]) == 0,
{
    reveal_with_fuel(uni, 3);
    reveal_with_fuel(sum_len, 3);
    let d = seq![set![x], set![x]];
    assert(d.drop_last() =~= seq![set![x]]);
    assert(seq![set![x]].drop_last() =~= Seq::<Set<int>>::empty());
    assert(uni(d) =~= set![x]);
    assert(uni(d).difference(set![s, a, b]) =~= set![x]);
    let e = seq![set![s]];
    assert(e.drop_last() =~= Seq::<Set<int>>::empty());
    assert(uni(e) =~= set![s]);
    assert(uni(e).difference(set![s, a]) =~= Set::<int>::empty());
}

}
