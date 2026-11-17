// product 3eaa79cf: traversal answers by strategy, derived from one modeled adjacency state.
//   iris_vector_graph/stores/iris_sql_store.py: IRISGraphStore._select_bfs_strategy / _only_default_graph /
//   execute_bfs / _bfs_rows / _run_objectscript_bfs / _sql_bfs_fallback / execute_vl_ends / shortest_path_length /
//   execute_shortest_path / execute_knn_vec; iris_vector_graph/_engine/algorithms.py khop / _khop_fallback;
//   iris_src/src/Graph/KG/TraversalBFS.cls BFSFast / BFSFastJsonSorted / ReachTypes; TraversalPaths.cls
//   ShortestPathJson / ShortestLength; VarLength.cls Ends.
// State: a finite edge sequence, each edge (graph, source, predicate, target, edge key). Every answer below is a
// function of that sequence and the query; no answer is an input.
use vstd::prelude::*;
verus! {

pub struct Edge { pub g: int, pub s: int, pub p: int, pub o: int, pub k: int }

pub enum Dir { Out, In, Both }

/// One traversal question: the graph walked (0 the default graph), the type filter (typed: only `preds`), direction.
pub struct Q { pub g: int, pub typed: bool, pub preds: Set<int>, pub dir: Dir }

pub open spec fn type_ok(q: Q, p: int) -> bool { !q.typed || q.preds.contains(p) }

/// Edge e carries a walk from u to v under q: e is in q's graph, of an allowed type, and points the walked way.
pub open spec fn edge_steps(q: Q, e: Edge, u: int, v: int) -> bool {
    e.g == q.g && type_ok(q, e.p) && match q.dir {
        Dir::Out => e.s == u && e.o == v,
        Dir::In => e.o == u && e.s == v,
        Dir::Both => (e.s == u && e.o == v) || (e.o == u && e.s == v),
    }
}

pub open spec fn step(es: Seq<Edge>, q: Q, u: int, v: int) -> bool {
    exists|i: int| 0 <= i < es.len() && edge_steps(q, #[trigger] es[i], u, v)
}

// ---------------------------------------------------------------- the SQL fallback (_sql_bfs_fallback)
/// visited[nbr] = hop for a neighbour of the frontier not yet visited; the next frontier is exactly those.
pub open spec fn sql_new(es: Seq<Edge>, q: Q, src: int, h: nat, v: int) -> bool
    decreases h, 0nat,
{
    if h == 0 { v == src }
    else { (exists|u: int| sql_new(es, q, src, (h - 1) as nat, u) && step(es, q, u, v)) && !sql_visited(es, q, src, (h - 1) as nat, v) }
}

pub open spec fn sql_visited(es: Seq<Edge>, q: Q, src: int, h: nat, v: int) -> bool
    decreases h, 1nat,
{
    if h == 0 { v == src } else { sql_visited(es, q, src, (h - 1) as nat, v) || sql_new(es, q, src, h, v) }
}

/// A row (v, d) of the SQL fallback's answer.
pub open spec fn sql_row(es: Seq<Edge>, q: Q, src: int, hops: nat, v: int, d: nat) -> bool {
    1 <= d <= hops && sql_new(es, q, src, d, v)
}

// ---------------------------------------------------------------- the ObjectScript walk (BFSFast, pAnyType = 1)
/// BFSFast's frontier: the source at hop 0; after a hop, the nodes it reached that `seen` (every earlier frontier)
/// does not hold.
pub open spec fn os_front(es: Seq<Edge>, q: Q, src: int, h: nat, v: int) -> bool
    decreases h, 0nat,
{
    if h == 0 { v == src }
    else { (exists|u: int| os_front(es, q, src, (h - 1) as nat, u) && step(es, q, u, v)) && !os_seen(es, q, src, (h - 1) as nat, v) }
}

pub open spec fn os_seen(es: Seq<Edge>, q: Q, src: int, h: nat, v: int) -> bool
    decreases h, 1nat,
{
    if h == 0 { v == src } else { os_seen(es, q, src, (h - 1) as nat, v) || os_front(es, q, src, h, v) }
}

/// BFSFast records one row per edge walked out of the frontier at hop h, whether or not its far node was seen
/// (the source and earlier nodes included): v is walked at h when some frontier node steps to it.
pub open spec fn os_walked(es: Seq<Edge>, q: Q, src: int, h: nat, v: int) -> bool {
    1 <= h && exists|u: int| os_front(es, q, src, (h - 1) as nat, u) && step(es, q, u, v)
}

/// _bfs_rows over the ObjectScript rows: each node other than the source once, at the least hop it was walked at.
pub open spec fn os_row(es: Seq<Edge>, q: Q, src: int, hops: nat, v: int, d: nat) -> bool {
    excl_source(v, src) && 1 <= d <= hops && os_walked(es, q, src, d, v)
        && forall|j: nat| 1 <= j < d ==> !#[trigger] os_walked(es, q, src, j, v)
}

/// _bfs_rows' `node != source_id`.
pub open spec fn excl_source(v: int, src: int) -> bool { v != src }

// ---------------------------------------------------------------- lemmas
pub proof fn lemma_front_eq_new(es: Seq<Edge>, q: Q, src: int, h: nat)
    ensures forall|v: int| os_front(es, q, src, h, v) == sql_new(es, q, src, h, v),
        forall|v: int| os_seen(es, q, src, h, v) == sql_visited(es, q, src, h, v),
    decreases h,
{
    if h > 0 {
        lemma_front_eq_new(es, q, src, (h - 1) as nat);
        assert forall|v: int| os_front(es, q, src, h, v) == sql_new(es, q, src, h, v) by {
            assert(os_seen(es, q, src, (h - 1) as nat, v) == sql_visited(es, q, src, (h - 1) as nat, v));
            if os_front(es, q, src, h, v) {
                let u = choose|u: int| os_front(es, q, src, (h - 1) as nat, u) && step(es, q, u, v);
                assert(sql_new(es, q, src, (h - 1) as nat, u));
            }
            if sql_new(es, q, src, h, v) {
                let u = choose|u: int| sql_new(es, q, src, (h - 1) as nat, u) && step(es, q, u, v);
                assert(os_front(es, q, src, (h - 1) as nat, u));
            }
        }
        assert forall|v: int| os_seen(es, q, src, h, v) == sql_visited(es, q, src, h, v) by {
            assert(os_seen(es, q, src, (h - 1) as nat, v) == sql_visited(es, q, src, (h - 1) as nat, v));
            assert(os_front(es, q, src, h, v) == sql_new(es, q, src, h, v));
        }
    }
}

pub proof fn lemma_visited_mono(es: Seq<Edge>, q: Q, src: int, i: nat, j: nat, v: int)
    requires i <= j, sql_visited(es, q, src, i, v),
    ensures sql_visited(es, q, src, j, v),
    decreases j - i,
{
    if i < j {
        lemma_visited_mono(es, q, src, i, (j - 1) as nat, v);
    }
}

pub proof fn lemma_visited_has_new(es: Seq<Edge>, q: Q, src: int, h: nat, v: int)
    requires sql_visited(es, q, src, h, v),
    ensures exists|j: nat| j <= h && #[trigger] sql_new(es, q, src, j, v),
    decreases h,
{
    if h == 0 {
        assert(sql_new(es, q, src, 0, v));
    } else if sql_new(es, q, src, h, v) {
    } else {
        lemma_visited_has_new(es, q, src, (h - 1) as nat, v);
    }
}

pub proof fn lemma_new_visited(es: Seq<Edge>, q: Q, src: int, h: nat, v: int)
    requires sql_new(es, q, src, h, v),
    ensures sql_visited(es, q, src, h, v),
{}

/// A node walked at hop j (>= 1) is visited by hop j.
pub proof fn lemma_walked_visited(es: Seq<Edge>, q: Q, src: int, j: nat, v: int)
    requires os_walked(es, q, src, j, v),
    ensures sql_visited(es, q, src, j, v),
{
    lemma_front_eq_new(es, q, src, (j - 1) as nat);
    let u = choose|u: int| os_front(es, q, src, (j - 1) as nat, u) && step(es, q, u, v);
    assert(sql_new(es, q, src, (j - 1) as nat, u));
    if !sql_visited(es, q, src, (j - 1) as nat, v) {
        assert(sql_new(es, q, src, j, v));
    }
}

/// B2: for every edge sequence, graph, type set, direction, source and hop bound, the ObjectScript walk's rows (after
/// _bfs_rows) are exactly the SQL fallback's rows. The pred column is ReachTypes' answer for the same depth map in both.
pub proof fn theorem_os_rows_eq_sql_rows(es: Seq<Edge>, q: Q, src: int, hops: nat, v: int, d: nat)
    ensures os_row(es, q, src, hops, v, d) <==> (excl_source(v, src) && sql_row(es, q, src, hops, v, d)),
{
    if 1 <= d {
        lemma_front_eq_new(es, q, src, (d - 1) as nat);
        lemma_front_eq_new(es, q, src, d);
    }
    if os_row(es, q, src, hops, v, d) {
        let u = choose|u: int| os_front(es, q, src, (d - 1) as nat, u) && step(es, q, u, v);
        assert(sql_new(es, q, src, (d - 1) as nat, u));
        if sql_visited(es, q, src, (d - 1) as nat, v) {
            lemma_visited_has_new(es, q, src, (d - 1) as nat, v);
            let j = choose|j: nat| j <= (d - 1) as nat && #[trigger] sql_new(es, q, src, j, v);
            assert(j >= 1);
            lemma_front_eq_new(es, q, src, (j - 1) as nat);
            let w = choose|w: int| sql_new(es, q, src, (j - 1) as nat, w) && step(es, q, w, v);
            assert(os_front(es, q, src, (j - 1) as nat, w));
            assert(os_walked(es, q, src, j, v));
            assert(false);
        }
        assert(sql_new(es, q, src, d, v));
    }
    if excl_source(v, src) && sql_row(es, q, src, hops, v, d) {
        let u = choose|u: int| sql_new(es, q, src, (d - 1) as nat, u) && step(es, q, u, v);
        assert(os_front(es, q, src, (d - 1) as nat, u));
        assert(os_walked(es, q, src, d, v));
        assert forall|j: nat| 1 <= j < d implies !#[trigger] os_walked(es, q, src, j, v) by {
            if os_walked(es, q, src, j, v) {
                lemma_walked_visited(es, q, src, j, v);
                lemma_visited_mono(es, q, src, j, (d - 1) as nat, v);
            }
        }
    }
}

/// B3: execute_bfs never lists the source, whatever cycles or self-loops reach it back.
pub proof fn theorem_bfs_never_lists_source(es: Seq<Edge>, q: Q, src: int, hops: nat, d: nat)
    ensures !os_row(es, q, src, hops, src, d),
{}

/// B3: one row per node: a node is listed at one depth only (parallel edges add rows to the walk, not to the answer).
pub proof fn theorem_one_row_per_node(es: Seq<Edge>, q: Q, src: int, hops: nat, v: int, d1: nat, d2: nat)
    requires os_row(es, q, src, hops, v, d1), os_row(es, q, src, hops, v, d2),
    ensures d1 == d2,
{
    if d1 < d2 { assert(!os_walked(es, q, src, d1, v)); }
    if d2 < d1 { assert(!os_walked(es, q, src, d2, v)); }
}

// ---------------------------------------------------------------- reach is a function of the step relation
pub proof fn lemma_new_ext(es1: Seq<Edge>, es2: Seq<Edge>, q1: Q, q2: Q, src: int, h: nat)
    requires forall|u: int, v: int| step(es1, q1, u, v) == step(es2, q2, u, v),
    ensures forall|v: int| sql_new(es1, q1, src, h, v) == sql_new(es2, q2, src, h, v),
        forall|v: int| sql_visited(es1, q1, src, h, v) == sql_visited(es2, q2, src, h, v),
    decreases h,
{
    if h > 0 {
        lemma_new_ext(es1, es2, q1, q2, src, (h - 1) as nat);
        assert forall|v: int| sql_new(es1, q1, src, h, v) == sql_new(es2, q2, src, h, v) by {
            assert(sql_visited(es1, q1, src, (h - 1) as nat, v) == sql_visited(es2, q2, src, (h - 1) as nat, v));
            if sql_new(es1, q1, src, h, v) {
                let u = choose|u: int| sql_new(es1, q1, src, (h - 1) as nat, u) && step(es1, q1, u, v);
                assert(sql_new(es2, q2, src, (h - 1) as nat, u) && step(es2, q2, u, v));
            }
            if sql_new(es2, q2, src, h, v) {
                let u = choose|u: int| sql_new(es2, q2, src, (h - 1) as nat, u) && step(es2, q2, u, v);
                assert(sql_new(es1, q1, src, (h - 1) as nat, u) && step(es1, q1, u, v));
            }
        }
        assert forall|v: int| sql_visited(es1, q1, src, h, v) == sql_visited(es2, q2, src, h, v) by {
            assert(sql_visited(es1, q1, src, (h - 1) as nat, v) == sql_visited(es2, q2, src, (h - 1) as nat, v));
            assert(sql_new(es1, q1, src, h, v) == sql_new(es2, q2, src, h, v));
        }
    }
}

/// B1 / S3 / named-graph scoping: edges of any other graph change no answer. `es` plus edges outside q's graph steps
/// exactly as `es`, so every walk (BFS rows, shortest length, khop) is unchanged.
pub proof fn theorem_other_graph_edges_invisible(es: Seq<Edge>, extra: Seq<Edge>, q: Q, src: int, h: nat)
    requires forall|i: int| 0 <= i < extra.len() ==> (#[trigger] extra[i]).g != q.g,
    ensures forall|v: int| sql_new(es + extra, q, src, h, v) == sql_new(es, q, src, h, v),
        forall|v: int| sql_visited(es + extra, q, src, h, v) == sql_visited(es, q, src, h, v),
{
    assert forall|u: int, v: int| step(es + extra, q, u, v) == step(es, q, u, v) by {
        if step(es + extra, q, u, v) {
            let i = choose|i: int| 0 <= i < (es + extra).len() && edge_steps(q, #[trigger] (es + extra)[i], u, v);
            if i >= es.len() { assert((es + extra)[i] == extra[i - es.len()]); }
            else { assert((es + extra)[i] == es[i]); }
        }
        if step(es, q, u, v) {
            let i = choose|i: int| 0 <= i < es.len() && edge_steps(q, #[trigger] es[i], u, v);
            assert((es + extra)[i] == es[i]);
        }
    }
    lemma_new_ext(es + extra, es, q, q, src, h);
}

/// B3 / S1: a parallel edge (same graph, source, type, target; another key) changes no walk.
pub proof fn theorem_parallel_edge_invisible(es: Seq<Edge>, i: int, key: int, q: Q, src: int, h: nat)
    requires 0 <= i < es.len(),
    ensures forall|v: int| sql_new(es.push(Edge { k: key, ..es[i] }), q, src, h, v) == sql_new(es, q, src, h, v),
        forall|v: int| sql_visited(es.push(Edge { k: key, ..es[i] }), q, src, h, v) == sql_visited(es, q, src, h, v),
{
    let es2 = es.push(Edge { k: key, ..es[i] });
    assert forall|u: int, v: int| step(es2, q, u, v) == step(es, q, u, v) by {
        if step(es2, q, u, v) {
            let j = choose|j: int| 0 <= j < es2.len() && edge_steps(q, #[trigger] es2[j], u, v);
            if j == es.len() { assert(edge_steps(q, es[i], u, v)); } else { assert(es2[j] == es[j]); }
        }
        if step(es, q, u, v) {
            let j = choose|j: int| 0 <= j < es.len() && edge_steps(q, #[trigger] es[j], u, v);
            assert(es2[j] == es[j]);
        }
    }
    lemma_new_ext(es2, es, q, q, src, h);
}

// ---------------------------------------------------------------- the cap (execute_bfs: run(..., 0, ...), then cut)
/// The cap execute_bfs hands an adapter: 0 (all), so an adapter's own cut (BFSFast counts walked edges) never decides.
pub open spec fn adapter_cap(max_results: nat) -> nat { 0 }

/// The answer's rows from the uncapped ordered rows: `rows[:max_results] if max_results else rows`.
pub open spec fn cut(rows: Seq<(int, nat)>, max_results: nat) -> Seq<(int, nat)> {
    if max_results > 0 && max_results < rows.len() { rows.take(max_results as int) } else { rows }
}

pub open spec fn ordered(rows: Seq<(int, nat)>) -> bool {
    forall|a: int, b: int| 0 <= a < b < rows.len() ==> (#[trigger] rows[a]).1 <= (#[trigger] rows[b]).1
}

/// B4: the adapter is asked for every row; the cut happens after the least-depth fold and the (depth, id) sort.
pub proof fn theorem_adapter_walks_uncapped(k: nat)
    ensures adapter_cap(k) == 0,
{}

/// B4: 0 answers every row; k answers the first k rows of the uncapped answer, none farther than a row it dropped.
pub proof fn theorem_cap_keeps_nearest_prefix(rows: Seq<(int, nat)>, k: nat)
    requires ordered(rows),
    ensures cut(rows, 0) == rows,
        cut(rows, k).len() <= rows.len(),
        forall|a: int| 0 <= a < cut(rows, k).len() ==> cut(rows, k)[a] == rows[a],
        forall|a: int, b: int| 0 <= a < cut(rows, k).len() <= b < rows.len() ==> (#[trigger] cut(rows, k)[a]).1 <= (#[trigger] rows[b]).1,
{}

// ---------------------------------------------------------------- strategy selection
pub enum Strategy { Arno, ObjectScript, SqlFallback }

pub struct Env { pub arno: bool, pub arno_bfs: bool, pub named_graph: bool, pub dir: Dir, pub other_graphs_have_edges: bool, pub kg_readable: bool }

/// _only_default_graph: ^KG("out")'s top level holds the default graph's key alone (or nothing); False when unreadable.
pub open spec fn only_default_graph(env: Env) -> bool { env.kg_readable && !env.other_graphs_have_edges }

/// _select_bfs_strategy.
pub open spec fn select(env: Env) -> Strategy {
    if !(env.dir is Out) { Strategy::ObjectScript }
    else if !env.named_graph && env.arno && env.arno_bfs && only_default_graph(env) { Strategy::Arno }
    else { Strategy::ObjectScript }
}

/// _run_objectscript_bfs: the SQL walk answers when the call raises or BFSFast walked no edge ("SORTED:0").
pub open spec fn falls_back(os_raised: bool, os_edges_walked: nat) -> bool { os_raised || os_edges_walked == 0 }

pub open spec fn answered_by(env: Env, os_raised: bool, os_edges_walked: nat) -> Strategy {
    let s = select(env);
    if s is ObjectScript && falls_back(os_raised, os_edges_walked) { Strategy::SqlFallback } else { s }
}

/// B1 / test_227: a named graph, or an inbound / undirected walk, never takes the Arno path; with the library absent
/// (the fixture) nothing does.
pub proof fn theorem_arno_only_default_outbound(env: Env)
    ensures (env.named_graph || !(env.dir is Out) || !env.arno || env.other_graphs_have_edges) ==> !(select(env) is Arno),
{}

/// The fixture: Arno absent, so a walk that records an edge is answered by the ObjectScript walk and a walk that
/// records none (the source has no adjacency entry in q's graph and direction) by the SQL fallback.
pub proof fn theorem_fixture_path(env: Env, walked: nat)
    requires !env.arno,
    ensures walked > 0 ==> answered_by(env, false, walked) is ObjectScript,
        answered_by(env, false, 0) is SqlFallback,
{}

/// Arno is reachable: the default graph, outbound, the library and its bfs capability, no other graph's edges.
pub proof fn theorem_arno_reachable(env: Env)
    requires env.arno, env.arno_bfs, !env.named_graph, env.dir is Out, !env.other_graphs_have_edges, env.kg_readable,
    ensures select(env) is Arno,
{}

// ---------------------------------------------------------------- the direction text execute_bfs is handed
/// "out", "OUT", "outbound", "in", "inbound", "both", anything else (e.g. "sideways").
pub enum DirText { Out, OutUpper, Outbound, In, Inbound, Both, Other }

/// BFSFast compares `direction = "out"` / "in" / "both" exactly: any other text walks no edge (SORTED:0).
pub open spec fn os_walks_text(t: DirText) -> bool { t is Out || t is In || t is Both }

/// _sql_bfs_fallback: `direction in ("out", "outbound")`, `in ("in", "inbound")`, and every other text the else
/// branch, which reads both columns.
pub open spec fn sql_dir_text(t: DirText) -> Dir {
    if t is Out || t is Outbound { Dir::Out } else if t is In || t is Inbound { Dir::In } else { Dir::Both }
}

/// _bfs_rows / ReachTypes: str(direction).lower(), outbound -> out, inbound -> in; "OUT" reads as "out".
pub open spec fn type_dir_text(t: DirText) -> Dir {
    if t is Out || t is OutUpper || t is Outbound { Dir::Out } else if t is In || t is Inbound { Dir::In } else { Dir::Both }
}

/// New finding: a direction text other than the three exact ones walks nothing in BFSFast, so the SQL fallback
/// answers; "OUT" and "sideways" are walked undirected there, while "OUT"'s types are read as outgoing.
pub proof fn theorem_unknown_direction_walks_both()
    ensures !os_walks_text(DirText::OutUpper), !os_walks_text(DirText::Other), !os_walks_text(DirText::Outbound),
        sql_dir_text(DirText::OutUpper) is Both, sql_dir_text(DirText::Other) is Both,
        sql_dir_text(DirText::Outbound) is Out, type_dir_text(DirText::OutUpper) is Out,
{}

// ---------------------------------------------------------------- variable-length ends (VarLength.Ends): trails
/// path is a sequence of edge indices and nodes the nodes it passes, from src to v, each edge stepping under q.
pub open spec fn chain(es: Seq<Edge>, q: Q, src: int, path: Seq<int>, nodes: Seq<int>, v: int) -> bool {
    nodes.len() == path.len() + 1 && nodes[0] == src && nodes[nodes.len() - 1] == v
        && forall|a: int| 0 <= a < path.len() ==> 0 <= #[trigger] path[a] < es.len() && edge_steps(q, es[path[a]], nodes[a], nodes[a + 1])
}

/// Relationship uniqueness: no edge (graph, source, type, target, key) twice.
pub open spec fn distinct(path: Seq<int>) -> bool {
    forall|a: int, b: int| 0 <= a < b < path.len() ==> path[a] != path[b]
}

pub open spec fn trail(es: Seq<Edge>, q: Q, src: int, path: Seq<int>, nodes: Seq<int>, v: int) -> bool {
    distinct(path) && chain(es, q, src, path, nodes, v)
}

pub open spec fn trail_len(es: Seq<Edge>, q: Q, src: int, l: nat, v: int) -> bool {
    exists|path: Seq<int>, nodes: Seq<int>| path.len() == l && #[trigger] trail(es, q, src, path, nodes, v)
}

/// An end (v, l): a trail of length l in minh..maxh reaches v, and none shorter in that range.
pub open spec fn vl_end(es: Seq<Edge>, q: Q, src: int, minh: nat, maxh: nat, v: int, l: nat) -> bool {
    minh <= l <= maxh && trail_len(es, q, src, l, v) && forall|j: nat| minh <= j < l ==> !#[trigger] trail_len(es, q, src, j, v)
}

pub open spec fn e(g: int, s: int, p: int, o: int, k: int) -> Edge { Edge { g, s, p, o, k } }

pub open spec fn q_out() -> Q { Q { g: 0, typed: false, preds: Set::empty(), dir: Dir::Out } }
pub open spec fn q_both() -> Q { Q { g: 0, typed: false, preds: Set::empty(), dir: Dir::Both } }

/// B6: a cycle back to the source at depth >= minh makes the source an end of the trail walk, while execute_bfs on
/// the same edges never lists it.
pub proof fn theorem_vl_ends_list_source_bfs_does_not()
    ensures vl_end(seq![e(0, 1, 7, 2, 0), e(0, 2, 7, 1, 0)], q_out(), 1, 1, 2, 1, 2),
        forall|d: nat| !os_row(seq![e(0, 1, 7, 2, 0), e(0, 2, 7, 1, 0)], q_out(), 1, 2, 1, d),
{
    let es = seq![e(0, 1, 7, 2, 0), e(0, 2, 7, 1, 0)];
    let q = q_out();
    let p = seq![0int, 1int];
    let ns = seq![1int, 2int, 1int];
    assert(edge_steps(q, es[p[0]], ns[0], ns[1]));
    assert(edge_steps(q, es[p[1]], ns[1], ns[2]));
    assert(chain(es, q, 1, p, ns, 1));
    assert(trail(es, q, 1, p, ns, 1));
    assert(trail_len(es, q, 1, 2, 1));
    assert forall|j: nat| 1 <= j < 2 implies !#[trigger] trail_len(es, q, 1, j, 1) by {
        if trail_len(es, q, 1, j, 1) {
            let (pp, nn) = choose|pp: Seq<int>, nn: Seq<int>| pp.len() == j && #[trigger] trail(es, q, 1, pp, nn, 1);
            assert(0 <= pp[0] < es.len() && edge_steps(q, es[pp[0]], nn[0], nn[1]));
            assert(pp[0] == 0 || pp[0] == 1);
        }
    }
}

/// B6, relationship uniqueness: over one edge a-b walked undirected, no trail of length 2 exists, so the walk does
/// not come back to a over the edge it arrived by.
pub proof fn theorem_vl_both_no_backtrack()
    ensures forall|v: int| !#[trigger] trail_len(seq![e(0, 1, 7, 2, 0)], q_both(), 1, 2, v),
{
    let es = seq![e(0, 1, 7, 2, 0)];
    assert forall|v: int| !#[trigger] trail_len(es, q_both(), 1, 2, v) by {
        if trail_len(es, q_both(), 1, 2, v) {
            let (pp, nn) = choose|pp: Seq<int>, nn: Seq<int>| pp.len() == 2 && #[trigger] trail(es, q_both(), 1, pp, nn, v);
            assert(0 <= pp[0] < 1);
            assert(0 <= pp[1] < 1);
            assert(pp[0] != pp[1]);
        }
    }
}

/// B6 / B3 on a multigraph: two parallel edges a->b (two keys) walked undirected are two relationships, so a is an
/// end at 2.
pub proof fn theorem_vl_parallel_edges_return()
    ensures trail_len(seq![e(0, 1, 7, 2, 0), e(0, 1, 7, 2, 1)], q_both(), 1, 2, 1),
{
    let es = seq![e(0, 1, 7, 2, 0), e(0, 1, 7, 2, 1)];
    let q = q_both();
    let p = seq![0int, 1int];
    let ns = seq![1int, 2int, 1int];
    assert(edge_steps(q, es[p[0]], ns[0], ns[1]));
    assert(edge_steps(q, es[p[1]], ns[1], ns[2]));
    assert(chain(es, q, 1, p, ns, 1));
    assert(trail(es, q, 1, p, ns, 1));
}

// ---------------------------------------------------------------- shortest paths
/// A shortest path from src to dst of length n under q (n the least hop count whose visited set holds dst).
pub open spec fn has_len(es: Seq<Edge>, q: Q, src: int, dst: int, n: nat) -> bool {
    sql_visited(es, q, src, n, dst) && (n == 0 || !sql_visited(es, q, src, (n - 1) as nat, dst))
}

pub open spec fn with_dir(q: Q, d: Dir) -> Q { Q { dir: d, ..q } }

/// ShortestPathJson walks "out" or "both"; execute_shortest_path reads "in" as the outgoing path from dst to src.
pub open spec fn esp_len(es: Seq<Edge>, q: Q, src: int, dst: int, n: nat) -> bool {
    if q.dir is In { has_len(es, with_dir(q, Dir::Out), dst, src, n) } else { has_len(es, q, src, dst, n) }
}

/// ShortestLength: tBoth = (direction = "both"); any other direction searches the source's out entries.
pub open spec fn spl_dir(d: Dir) -> Dir { if d is Both { Dir::Both } else { Dir::Out } }

pub open spec fn spl_len(es: Seq<Edge>, q: Q, src: int, dst: int, n: nat) -> bool {
    has_len(es, with_dir(q, spl_dir(q.dir)), src, dst, n)
}

/// S1: out and both, the two readers answer the same length on every edge set.
pub proof fn theorem_lengths_agree_out_both(es: Seq<Edge>, q: Q, src: int, dst: int, n: nat)
    requires !(q.dir is In),
    ensures spl_len(es, q, src, dst, n) == esp_len(es, q, src, dst, n),
{
    assert(with_dir(q, spl_dir(q.dir)) == q);
}

pub proof fn lemma_nothing_out_of_source(es: Seq<Edge>, q: Q, src: int, h: nat, v: int)
    requires forall|u: int, w: int| step(es, q, u, w) ==> u != src,
    ensures sql_visited(es, q, src, h, v) ==> v == src,
        h > 0 ==> !sql_new(es, q, src, h, v),
    decreases h,
{
    if h > 0 {
        lemma_nothing_out_of_source(es, q, src, (h - 1) as nat, v);
        if sql_new(es, q, src, h, v) {
            let u = choose|u: int| sql_new(es, q, src, (h - 1) as nat, u) && step(es, q, u, v);
            lemma_nothing_out_of_source(es, q, src, (h - 1) as nat, u);
            if h - 1 > 0 { assert(!sql_new(es, q, src, (h - 1) as nat, u)); }
            assert(u == src);
        }
    }
}

/// S2: on one edge b->a, execute_shortest_path(a, b, 'in') finds the incoming path of length 1, and
/// shortest_path_length(a, b, 'in') searches a's out entries and finds none within any bound.
pub proof fn theorem_in_length_differs(maxh: nat)
    requires maxh >= 1,
    ensures esp_len(seq![e(0, 2, 7, 1, 0)], with_dir(q_out(), Dir::In), 1, 2, 1),
        !sql_visited(seq![e(0, 2, 7, 1, 0)], with_dir(with_dir(q_out(), Dir::In), spl_dir(Dir::In)), 1, maxh, 2),
{
    let es = seq![e(0, 2, 7, 1, 0)];
    let qo = with_dir(q_out(), Dir::Out);
    assert(edge_steps(qo, es[0], 2, 1));
    assert(step(es, qo, 2, 1));
    assert(sql_new(es, qo, 2, 0, 2));
    assert(!sql_visited(es, qo, 2, 0, 1));
    assert(sql_new(es, qo, 2, 1, 1));
    let qs = with_dir(with_dir(q_out(), Dir::In), spl_dir(Dir::In));
    assert forall|u: int, w: int| step(es, qs, u, w) implies u != 1 by {
        let i = choose|i: int| 0 <= i < es.len() && edge_steps(qs, #[trigger] es[i], u, w);
        assert(i == 0);
    }
    lemma_nothing_out_of_source(es, qs, 1, maxh, 2);
}

// ---------------------------------------------------------------- khop and knn
/// khop (algorithms.py): BFSFastJson on the default graph, outbound, every type; nodes = the seed (when it has an
/// out-edge or is a node) and every node walked within hops. It has no graph argument.
pub open spec fn khop_node(es: Seq<Edge>, seed: int, hops: nat, seed_is_node: bool, v: int) -> bool {
    let q = khop_q();
    if v == seed { seed_is_node || exists|w: int| step(es, q, seed, w) }
    else { sql_visited(es, q, seed, hops, v) }
}

pub open spec fn khop_q() -> Q { Q { g: 0, typed: false, preds: Set::empty(), dir: Dir::Out } }

/// N2 / B7: khop's nodes other than the seed are execute_bfs's ids (default graph, out, no types) on every edge set.
pub proof fn theorem_khop_is_default_out_bfs(es: Seq<Edge>, seed: int, hops: nat, v: int, seed_is_node: bool)
    requires v != seed,
    ensures khop_node(es, seed, hops, seed_is_node, v) <==> exists|d: nat| #[trigger] os_row(es, q_out(), seed, hops, v, d),
{
    assert(khop_q() == q_out());
    if khop_node(es, seed, hops, seed_is_node, v) {
        lemma_visited_has_new(es, khop_q(), seed, hops, v);
        let d = choose|d: nat| d <= hops && #[trigger] sql_new(es, khop_q(), seed, d, v);
        assert(d >= 1);
        theorem_os_rows_eq_sql_rows(es, khop_q(), seed, hops, v, d);
        assert(os_row(es, khop_q(), seed, hops, v, d));
    }
    if exists|d: nat| #[trigger] os_row(es, khop_q(), seed, hops, v, d) {
        let d = choose|d: nat| #[trigger] os_row(es, khop_q(), seed, hops, v, d);
        theorem_os_rows_eq_sql_rows(es, khop_q(), seed, hops, v, d);
        lemma_new_visited(es, khop_q(), seed, d, v);
        lemma_visited_mono(es, khop_q(), seed, d, hops, v);
    }
}

/// N2: khop answers the default graph's walk whatever named graphs hold: edges only in a named graph add nothing.
pub proof fn theorem_khop_ignores_named_graphs(es: Seq<Edge>, named: Seq<Edge>, seed: int, hops: nat, v: int)
    requires forall|i: int| 0 <= i < named.len() ==> (#[trigger] named[i]).g != 0, v != seed,
    ensures khop_node(es + named, seed, hops, false, v) == khop_node(es, seed, hops, false, v),
{
    theorem_other_graph_edges_invisible(es, named, khop_q(), seed, hops);
}

/// execute_knn_vec: the route for (graph, model); None answers no neighbours, whatever vectors exist.
pub open spec fn knn_rows(routed: bool, nearest: nat) -> nat { if routed { nearest } else { 0 } }

/// N1.
pub proof fn theorem_knn_no_route_no_rows(nearest: nat)
    ensures knn_rows(false, nearest) == 0, knn_rows(true, nearest) == nearest,
{}

}
