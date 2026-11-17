// product 3eaa79cf: composed retrieval (W56, iteration 49). Legs -> fusion / expansion / subgraph -> returned answer.
//   Engine fusion: iris_vector_graph/_engine/vector.py VectorMixin.kg_RRF_FUSE 1382-1451 (absent rank len+c, one try
//     around both legs), VectorMixin._fusion_leg_index 187-225 (own recorded index > hnsw > unknown-scope index),
//     _index_graph 164-185 and _index_graph_scopes 150-162 (an IVF scope is known only in the engine that built it,
//     ivf_build 2023-2025), AlgorithmsMixin.kg_RERANK (algorithms.py 1043-1050, c=60, k1=k2=2*top_n);
//     iris_vector_graph/operators.py IRISGraphOperators.__init__ (its own engine) and kg_RRF_FUSE (defaults).
//   SQL fusion: schema.py kg_RRF_FUSE procedure 2526-2560 (absent rank 10^9, docs text via kg_TXT); Graph.KG.PyOps
//     FuseRanks 351-368 (absent rank 10^9, first occurrence), HybridSearch 370-421 (c 0 -> 60; route or procedure),
//     VectorSearch 263-303 / RouteVectorRows 305-349 / vectorToJson 236-261 / getExpectedDimension 98-156.
//   kg_VECTOR_GRAPH_SEARCH: vector.py 1453-1548 (list(set(...))[:k] before the sort; in_graph_expansion is membership
//     in the expansion; vector_similarity from the vector leg only).
//   Subgraphs: algorithms.py kg_PPR_GUIDED_SUBGRAPH 947-985 (cap min(max_nodes, ppr_top_k), seeds + PPR top ids),
//     kg_SUBGRAPH 880-946 -> stores/iris_sql_store.py execute_subgraph 2500-2560 -> Graph.KG.Subgraph.SubgraphJson
//     (Subgraph.cls 6-100: seeds with edges, BFS over frontier in collation order, edge recorded before the cap test).
//   multi_vector_search: vector.py 1288-1381 (a failing source is skipped).
// Readers: the Python return values, the SQL procedure's rows, the PyOps class methods' %DynamicArray.
use vstd::prelude::*;
verus! {

// =============================================================== reciprocal-rank fusion: the absent contribution
/// Which fusion surface computes the score. The rule for an item a leg lacks is decided by the surface.
pub enum Surface { Engine, SqlProcedure, PyOpsFuseRanks, PythonRrf }

/// The place a missing item is given. Engine: `len(leg) + c` (vector.py 1444-1446); SQL procedure and FuseRanks:
/// 10^9; RRFFusion (and CALL ivg.retrieve): no contribution (None).
pub open spec fn absent_place(s: Surface, c: nat, leg_len: nat) -> Option<nat> {
    match s {
        Surface::Engine => Some(leg_len + c),
        Surface::SqlProcedure => Some(1000000000nat),
        Surface::PyOpsFuseRanks => Some(1000000000nat),
        Surface::PythonRrf => None,
    }
}
pub open spec fn part(s: Surface, c: nat, rank: Option<nat>, leg_len: nat) -> real {
    match rank {
        Some(r) => 1real / (c as real + r as real),
        None => match absent_place(s, c, leg_len) {
            Some(p) => 1real / (c as real + p as real),
            None => 0real,
        },
    }
}
/// A two-leg fused score: vector rank, vector leg length, text rank, text leg length.
pub open spec fn rrf(s: Surface, c: nat, rv: Option<nat>, lv: nat, rt: Option<nat>, lt: nat) -> real {
    part(s, c, rv, lv) + part(s, c, rt, lt)
}

/// W56 F1b (bug-srch-005, E2E): the fixture's legs (c = 60, vector leg 62 long, text leg 60 long). x is vector rank 1
/// and absent from text; n30 is vector rank 32 and text rank 31. The engine puts x above n30 (x answered 31st of
/// 62); FuseRanks and the SQL procedure put n30 above x (x answered 61st).
pub proof fn theorem_engine_absent_rank_reorders()
    ensures
        rrf(Surface::Engine, 60, Some(1), 62, None, 60) > rrf(Surface::Engine, 60, Some(32), 62, Some(31), 60),
        rrf(Surface::PyOpsFuseRanks, 60, Some(1), 62, None, 60) < rrf(Surface::PyOpsFuseRanks, 60, Some(32), 62, Some(31), 60),
        rrf(Surface::SqlProcedure, 60, Some(1), 62, None, 60) < rrf(Surface::SqlProcedure, 60, Some(32), 62, Some(31), 60),
{
    assert(1real / 61real + 1real / 180real > 1real / 92real + 1real / 91real) by (nonlinear_arith);
    assert(1real / 61real + 1real / 1000000060real < 1real / 92real + 1real / 91real) by (nonlinear_arith);
}
/// Neighbor (F1, held): an item at rank 10 in both legs beats an item at rank 1 of one leg on every surface.
pub proof fn theorem_both_legs_rank10_wins_everywhere(s: Surface)
    ensures rrf(s, 60, Some(10), 62, Some(10), 60) > rrf(s, 60, Some(1), 62, None, 60),
{
    assert(2real / 70real > 1real / 61real + 1real / 180real) by (nonlinear_arith);
    assert(1real / 70real + 1real / 70real == 2real / 70real) by (nonlinear_arith);
    assert(1real / 1000000060real < 1real / 180real) by (nonlinear_arith);
}
/// The engine's absent contribution depends on the other leg's length; RRFFusion's is zero.
pub proof fn theorem_engine_absent_depends_on_length()
    ensures
        part(Surface::Engine, 60, None, 0) != part(Surface::Engine, 60, None, 200),
        part(Surface::PythonRrf, 60, None, 0) == 0real,
        part(Surface::PythonRrf, 60, None, 200) == 0real,
{
    assert(1real / 120real != 1real / 320real) by (nonlinear_arith);
}
/// W56 F3/F4 (value departure): a skipped or empty leg adds 1/(2c) to every row the engine answers, so the reported
/// rrf of a vector rank-1 row is 1/61 + 1/120 (observed 0.024726776), not 1/61. Order is unchanged.
pub proof fn theorem_engine_skipped_leg_adds_constant(r: nat)
    ensures rrf(Surface::Engine, 60, Some(r), 62, None, 0) == 1real / (60real + r as real) + 1real / 120real,
{}

// =============================================================== engine fusion: a failed leg versus an empty one
pub enum Leg { Rows(nat), Fails }
pub enum FuseOut { Empty, VectorOnly, TextOnly, Both }
/// kg_RRF_FUSE runs the vector leg and then the text leg inside one try: a vector failure skips the text leg, and the
/// except clause leaves both lists as they were (empty), so the answer is []. A text failure keeps the vector rows.
pub open spec fn engine_fuse(v: Leg, text_requested: bool, t: Leg) -> FuseOut {
    match v {
        Leg::Fails => FuseOut::Empty,
        Leg::Rows(nv) => {
            let nt: nat = if !text_requested { 0 } else { match t { Leg::Fails => 0, Leg::Rows(n) => n } };
            if nv > 0 && nt > 0 { FuseOut::Both } else if nv > 0 { FuseOut::VectorOnly }
            else if nt > 0 { FuseOut::TextOnly } else { FuseOut::Empty }
        }
    }
}
/// W56 F4 (held; KNOWN_ISSUES): a failed vector leg answers [] although the text leg has rows; an empty successful
/// vector leg answers the text ranking. search.fusion.failed_leg requires the failure to be reported instead.
pub proof fn theorem_failed_vector_leg_reads_as_no_match()
    ensures
        engine_fuse(Leg::Fails, true, Leg::Rows(60)) == FuseOut::Empty,
        engine_fuse(Leg::Rows(0), true, Leg::Rows(3)) == FuseOut::TextOnly,
        engine_fuse(Leg::Rows(62), true, Leg::Fails) == FuseOut::VectorOnly,
{}

// =============================================================== which vector index the engine's fusion reads
pub enum Scope { Recorded(int), Unknown }
pub enum Choice { Ivf, Hnsw, NoLeg }
/// The scope an engine sees for an IVF index: only the engine instance that built it recorded the graph
/// (ivf_build -> _index_graph_scopes); any other engine, including the one IRISGraphOperators creates, sees Unknown.
pub open spec fn ivf_scope_seen(built_by_this_engine: bool, built_for: int) -> Scope {
    if built_by_this_engine { Scope::Recorded(built_for) } else { Scope::Unknown }
}
/// _fusion_leg_index over one IVF entry and the hnsw entry: an index recorded for the graph wins, then hnsw, then an
/// index of unknown scope (with a warning); none of them, no vector leg.
pub open spec fn leg_index(ivf: Option<Scope>, hnsw: bool, g: int) -> Choice {
    match ivf {
        Some(Scope::Recorded(h)) if h == g => Choice::Ivf,
        _ => if hnsw { Choice::Hnsw } else {
            match ivf { Some(Scope::Unknown) => Choice::Ivf, _ => Choice::NoLeg }
        },
    }
}
/// Vectors are integer pairs; the query is (1, 0). IVF "cosine" scores the dot product (bug-srch-109); the HNSW leg
/// (kg_KNN_VEC) scores the cosine. `above(ch, v1, v2)`: v1 is ranked above v2 in the vector leg.
pub open spec fn dotq(v: (int, int)) -> int { v.0 }
pub open spec fn len2(v: (int, int)) -> int { v.0 * v.0 + v.1 * v.1 }
pub open spec fn cos_above(v1: (int, int), v2: (int, int)) -> bool {
    // cos1 > cos2 for positive dots, compared without roots: dot1^2 * |v2|^2 > dot2^2 * |v1|^2
    dotq(v1) * dotq(v1) * len2(v2) > dotq(v2) * dotq(v2) * len2(v1)
}
pub open spec fn above(ch: Choice, v1: (int, int), v2: (int, int)) -> bool {
    match ch { Choice::Ivf => dotq(v1) > dotq(v2), Choice::Hnsw => cos_above(v1, v2), Choice::NoLeg => false }
}
/// W56 F7 (new, bug-srch-110): one graph, one cosine IVF index, the same call. The engine that built the index reads
/// it and ranks the long vector L = (10, 10) above the aligned A = (1, 0); a fresh engine (another process, or
/// IRISGraphOperators) cannot tell the index's graph, reads hnsw, and ranks A above L.
pub proof fn theorem_fused_leg_depends_on_building_engine(g: int)
    ensures
        leg_index(Some(ivf_scope_seen(true, g)), true, g) == Choice::Ivf,
        leg_index(Some(ivf_scope_seen(false, g)), true, g) == Choice::Hnsw,
        above(leg_index(Some(ivf_scope_seen(true, g)), true, g), (10, 10), (1, 0)),
        above(leg_index(Some(ivf_scope_seen(false, g)), true, g), (1, 0), (10, 10)),
{
    assert(1int * 1 * 200 > 10 * 10 * 1) by (nonlinear_arith);
}
/// Neighbor: another graph's recorded IVF is never read while hnsw exists; with no hnsw an unknown-scope IVF is.
pub proof fn theorem_other_graph_ivf_not_read(g: int, h: int)
    requires g != h,
    ensures
        leg_index(Some(Scope::Recorded(h)), true, g) == Choice::Hnsw,
        leg_index(Some(Scope::Recorded(h)), false, g) == Choice::NoLeg,
        leg_index(Some(Scope::Unknown), false, g) == Choice::Ivf,
{}

// =============================================================== PyOps (the /vectorSearch and /hybridSearch bodies)
/// HybridSearch's `c = int(c) if c else 60`.
pub open spec fn hybrid_c(c: nat) -> nat { if c == 0 { 60 } else { c } }
/// Transcription (m9: stated for every c): 0 becomes 60, any other c is kept.
pub proof fn theorem_hybrid_c_zero_becomes_60(c: nat)
    ensures hybrid_c(0) == 60, c > 0 ==> hybrid_c(c) == c,
{}
pub enum Search { Rows, NoRows, WidthRefused }
/// getExpectedDimension: the route's width, else (a named graph with no route) getDefaultDimension = 768; the default
/// pair reads its column width. vectorToJson refuses another width before any table is read.
pub open spec fn pyops_expected(route_width: Option<nat>, default_pair_width: nat, named: bool) -> nat {
    match route_width { Some(w) => w, None => if named { 768 } else { default_pair_width } }
}
pub open spec fn pyops_vector_search(route_width: Option<nat>, named: bool, qdim: nat) -> Search {
    if qdim != pyops_expected(route_width, 768, named) { Search::WidthRefused }
    else { match route_width { Some(_) => Search::Rows, None => Search::NoRows } }
}
/// The engine's kg_KNN_VEC looks the route up first: an unrouted pair answers nothing whatever the width
/// (search.routes.no_fallback).
pub open spec fn engine_knn(route_width: Option<nat>, qdim: nat) -> Search {
    match route_width { None => Search::NoRows, Some(w) => if qdim != w { Search::WidthRefused } else { Search::Rows } }
}
/// W56 Y1 (new, bug-srch-111): a named graph with no route and a 4-wide query: PyOps refuses on width 768, the engine
/// answers nothing. Neighbor: a 768-wide query gets no rows from both; a routed graph's own width gets rows from both.
pub proof fn theorem_unrouted_rest_search_refuses_width()
    ensures
        pyops_vector_search(None, true, 4) == Search::WidthRefused,
        engine_knn(None, 4) == Search::NoRows,
        pyops_vector_search(None, true, 768) == Search::NoRows,
        pyops_vector_search(Some(4), true, 4) == Search::Rows,
        engine_knn(Some(4), 4) == Search::Rows,
{}

// =============================================================== kg_VECTOR_GRAPH_SEARCH
/// The candidate set's iteration order (Python set order: arbitrary, varies with the hash seed) is `order`; the
/// method keeps its first k (`list(set(...))[:k]`, vector.py 1513) and only then sorts by vector similarity. A
/// candidate is answered iff it is kept. (Iteration 50: transcribed directly; the former premise constant
/// `truncate_first()` is gone, so the control changes the transcribed order of operations.)
pub open spec fn index_of(order: Seq<int>, x: int) -> int
    decreases order.len(),
{
    if order.len() == 0 { -1 } else if order[0] == x { 0 } else {
        let i = index_of(order.drop_first(), x); if i < 0 { -1 } else { i + 1 }
    }
}
/// `sim_rank(x)`: x's place by vector similarity (0 = best); the as-built method does not read it before truncating.
pub open spec fn answered(order: Seq<int>, sim_rank: spec_fn(int) -> int, k: int, x: int) -> bool { 0 <= index_of(order, x) < k }
/// HD-0603's ranked alternative (the repair): sort the candidates by similarity, then keep the k best.
pub open spec fn rule_answered(order: Seq<int>, sim_rank: spec_fn(int) -> int, k: int, x: int) -> bool {
    0 <= index_of(order, x) && sim_rank(x) < k
}
/// W56 V1 (held; HD-0603, E2E for 5 of 8 hash seeds): candidates a (best), b, p, r, n; with k = 2 and the observed
/// order p, r, a, b, n the best vector hit a is not answered.
pub proof fn theorem_best_hit_can_be_dropped()
    ensures !answered(seq![3int, 4, 1, 2, 5], |x: int| x - 1, 2, 1), rule_answered(seq![3int, 4, 1, 2, 5], |x: int| x - 1, 2, 1),
{
    reveal_with_fuel(index_of, 4);
}
/// Neighbor: when k covers the candidate set, every candidate (the best hit included) is answered, in any order.
pub proof fn theorem_k_covering_set_keeps_best(order: Seq<int>, x: int, k: int)
    requires 0 <= index_of(order, x), order.len() <= k,
    ensures answered(order, |y: int| 0int, k, x),
{
    lemma_index_bound(order, x);
}
pub proof fn lemma_index_bound(order: Seq<int>, x: int)
    ensures index_of(order, x) < order.len(),
    decreases order.len(),
{
    if order.len() > 0 && order[0] != x { lemma_index_bound(order.drop_first(), x); }
}
/// in_graph_expansion is membership in the expansion targets; vector_similarity comes from the vector leg only.
pub open spec fn in_graph_expansion(is_vector_hit: bool, is_expansion_target: bool) -> bool { is_expansion_target }
pub open spec fn vector_similarity(is_vector_hit: bool, cosine: int) -> int { if is_vector_hit { cosine } else { 0 } }
/// W56 V4 (missed) and V3 (held): b, a vector hit that a's edge also reaches, is flagged as an expansion; t, found
/// only by text, scores 0 although its stored vector's cosine is positive.
pub proof fn theorem_expansion_flag_and_text_only_zero()
    ensures in_graph_expansion(true, true), !in_graph_expansion(true, false), vector_similarity(false, 17) == 0,
        vector_similarity(true, 17) == 17,
{}

// =============================================================== kg_SUBGRAPH / kg_PPR_GUIDED_SUBGRAPH
// Scope: the ObjectScript Owner Graph.KG.Subgraph.SubgraphJson. IRISGraphStore.execute_subgraph (iris_sql_store.py
// 2526-2541) asks the Arno reader Graph.KG.ArnoAccel.SubgraphNativeJson first when no edge_types are given and routing
// says native; that path is not modeled (no Arno on the fixture). Every theorem below is about the Owner path.
pub struct St { pub seen: Set<int>, pub count: nat, pub edges: Seq<(int, int)> }
/// The cap kg_PPR_GUIDED_SUBGRAPH hands kg_SUBGRAPH: min(max_nodes, ppr_top_k) (algorithms.py 971-973). This is the
/// documented cap (docstring 956-957; the design note's top_k "hard node cap", "len(result.nodes) <= top_k always").
pub open spec fn guided_cap(max_nodes: nat, ppr_top_k: nat) -> nat { if max_nodes < ppr_top_k { max_nodes } else { ppr_top_k } }
pub open spec fn empty_st() -> St { St { seen: Set::empty(), count: 0, edges: seq![] } }
/// SubgraphJson's seed loop (Subgraph.cls 37-48): every seed with an edge either way enters the frontier and is
/// counted once; the cap is not consulted, so the seeds alone can exceed it.
pub open spec fn admit(seeds: Seq<int>, has_edge: spec_fn(int) -> bool, st: St, cap: nat) -> St
    decreases seeds.len(),
{
    if seeds.len() == 0 { st } else {
        let s = seeds[0];
        let st1 = if has_edge(s) && !st.seen.contains(s) { St { seen: st.seen.insert(s), count: st.count + 1, ..st } } else { st };
        admit(seeds.drop_first(), has_edge, st1, cap)
    }
}
/// SubgraphJson's inner loop over one node's out-neighbors: the edge is recorded first; an unseen neighbor is added
/// unless the count has reached the cap, which stops the whole expansion.
pub open spec fn expand_node(n: int, outs: Seq<int>, st: St, cap: nat) -> (St, bool)
    decreases outs.len(),
{
    if outs.len() == 0 { (st, false) } else {
        let o = outs[0];
        let st1 = St { edges: st.edges.push((n, o)), ..st };
        if st1.seen.contains(o) { expand_node(n, outs.drop_first(), st1, cap) }
        else if st1.count >= cap { (st1, true) }
        else { expand_node(n, outs.drop_first(), St { seen: st1.seen.insert(o), count: st1.count + 1, ..st1 }, cap) }
    }
}
/// One hop over the frontier in collation order; after each node the cap is tested again.
pub open spec fn expand_frontier(frontier: Seq<int>, adj: spec_fn(int) -> Seq<int>, st: St, cap: nat) -> St
    decreases frontier.len(),
{
    if frontier.len() == 0 { st } else {
        let r = expand_node(frontier[0], adj(frontier[0]), st, cap);
        if r.1 || r.0.count >= cap { r.0 } else { expand_frontier(frontier.drop_first(), adj, r.0, cap) }
    }
}
/// What the answer lists as an edge: SubgraphJson returns the edges it recorded (kg_SUBGRAPH and
/// kg_PPR_GUIDED_SUBGRAPH reshape them, adding and removing none).
pub open spec fn lists_edge(r: St, adj: spec_fn(int) -> Seq<int>, e: (int, int)) -> bool { r.edges.contains(e) }
/// The documented answer (algorithms.op.subgraph and .guided): the answered nodes, and every edge between two of them.
pub open spec fn rule_lists_edge(r: St, adj: spec_fn(int) -> Seq<int>, e: (int, int)) -> bool {
    r.seen.contains(e.0) && r.seen.contains(e.1) && adj(e.0).contains(e.1)
}
/// The documented size: at most the cap.
pub open spec fn rule_within_cap(r: St, cap: nat) -> bool { r.count <= cap }

// ---- general facts about the transcription (m9: stated for every input, not one example)
pub proof fn lemma_expand_node_count_grows(n: int, outs: Seq<int>, st: St, cap: nat)
    ensures expand_node(n, outs, st, cap).0.count >= st.count,
    decreases outs.len(),
{
    if outs.len() > 0 {
        let o = outs[0];
        let st1 = St { edges: st.edges.push((n, o)), ..st };
        if st1.seen.contains(o) { lemma_expand_node_count_grows(n, outs.drop_first(), st1, cap); }
        else if st1.count >= cap { }
        else { lemma_expand_node_count_grows(n, outs.drop_first(), St { seen: st1.seen.insert(o), count: st1.count + 1, ..st1 }, cap); }
    }
}
/// expand_node keeps the edges it was given and adds only edges that leave n.
pub proof fn lemma_expand_node_edges_leave_n(n: int, outs: Seq<int>, st: St, cap: nat)
    ensures ({ let r = expand_node(n, outs, st, cap).0;
               r.edges.len() >= st.edges.len()
               && (forall|i: int| 0 <= i < st.edges.len() ==> r.edges[i] == st.edges[i])
               && (forall|i: int| st.edges.len() <= i < r.edges.len() ==> r.edges[i].0 == n) }),
    decreases outs.len(),
{
    if outs.len() > 0 {
        let o = outs[0];
        let st1 = St { edges: st.edges.push((n, o)), ..st };
        if st1.seen.contains(o) { lemma_expand_node_edges_leave_n(n, outs.drop_first(), st1, cap); }
        else if st1.count >= cap { }
        else { lemma_expand_node_edges_leave_n(n, outs.drop_first(), St { seen: st1.seen.insert(o), count: st1.count + 1, ..st1 }, cap); }
    }
}
/// W56 S_star_cap3 generalized (bug-plt-114): whenever the count has reached the cap and a node's first out-neighbor
/// is unseen, that edge is listed while its far node is not, and expansion stops.
pub proof fn theorem_capped_subgraph_lists_edge_to_unlisted_node(n: int, adj: spec_fn(int) -> Seq<int>, st: St, cap: nat)
    requires adj(n).len() > 0, !st.seen.contains(adj(n)[0]), st.count >= cap,
    ensures ({ let r = expand_node(n, adj(n), st, cap);
               lists_edge(r.0, adj, (n, adj(n)[0])) && !r.0.seen.contains(adj(n)[0]) && r.1 }),
{
    let r = expand_node(n, adj(n), st, cap);
    assert(r.0.edges == st.edges.push((n, adj(n)[0])));
    assert(r.0.edges[st.edges.len() as int] == (n, adj(n)[0]));
}
/// bug-plt-113 generalized: once the admitted seeds fill the cap, only the first frontier node in collation order is
/// expanded, so every listed edge leaves that node, for every frontier, adjacency and cap.
pub proof fn theorem_filled_cap_expands_only_first_node(frontier: Seq<int>, adj: spec_fn(int) -> Seq<int>, st: St, cap: nat)
    requires frontier.len() > 0, st.count >= cap, st.edges.len() == 0,
    ensures ({ let r = expand_frontier(frontier, adj, st, cap);
               forall|e: (int, int)| #[trigger] lists_edge(r, adj, e) ==> e.0 == frontier[0] }),
{
    let r1 = expand_node(frontier[0], adj(frontier[0]), st, cap);
    lemma_expand_node_count_grows(frontier[0], adj(frontier[0]), st, cap);
    lemma_expand_node_edges_leave_n(frontier[0], adj(frontier[0]), st, cap);
    assert(expand_frontier(frontier, adj, st, cap) == r1.0);
    assert forall|e: (int, int)| #[trigger] lists_edge(r1.0, adj, e) implies e.0 == frontier[0] by {
        let i = choose|i: int| 0 <= i < r1.0.edges.len() && r1.0.edges[i] == e;
    }
}
/// bug-plt-113 (seeds over the cap) generalized: distinct seeds that all have an edge and are not yet seen are all
/// admitted whatever the cap, so more seeds than the cap give an answer larger than the cap (from the empty state:
/// `admit(seeds, has_edge, empty_st(), cap).count == seeds.len()`).
pub proof fn theorem_admitted_seeds_ignore_cap(seeds: Seq<int>, has_edge: spec_fn(int) -> bool, st: St, cap: nat)
    requires seeds.no_duplicates(), forall|i: int| 0 <= i < seeds.len() ==> has_edge(seeds[i]) && !st.seen.contains(seeds[i]),
    ensures admit(seeds, has_edge, st, cap).count == st.count + seeds.len(),
            st.count + seeds.len() > cap ==> !rule_within_cap(admit(seeds, has_edge, st, cap), cap),
    decreases seeds.len(),
{
    if seeds.len() > 0 {
        let s = seeds[0];
        let st1 = St { seen: st.seen.insert(s), count: st.count + 1, ..st };
        assert forall|j: int| 0 <= j < seeds.drop_first().len() implies has_edge(seeds.drop_first()[j]) && !st1.seen.contains(seeds.drop_first()[j]) by {
            assert(seeds.drop_first()[j] == seeds[j + 1]);
            assert(seeds[j + 1] != seeds[0]);
        }
        theorem_admitted_seeds_ignore_cap(seeds.drop_first(), has_edge, st1, cap);
    }
}
/// The cap rule for every input: min(max_nodes, ppr_top_k); ppr_top_k under the default max_nodes 5000.
pub proof fn theorem_guided_cap_is_ppr_top_k(max_nodes: nat, ppr_top_k: nat)
    ensures guided_cap(max_nodes, ppr_top_k) <= max_nodes, guided_cap(max_nodes, ppr_top_k) <= ppr_top_k,
            guided_cap(max_nodes, ppr_top_k) == max_nodes || guided_cap(max_nodes, ppr_top_k) == ppr_top_k,
            ppr_top_k <= max_nodes ==> guided_cap(max_nodes, ppr_top_k) == ppr_top_k,
{}

// ---- witnesses on the observed star (each mirrors a binding case; the general claims above carry the rule)
/// The star of follow-up 3: s = 9 -> a1..a6 = 1..6, and a1 -> a2. Collation puts a1..a6 before s.
pub open spec fn star(n: int) -> Seq<int> {
    if n == 9 { seq![1int, 2, 3, 4, 5, 6] } else if n == 1 { seq![2int] } else { seq![] }
}
pub open spec fn star_has_edge(n: int) -> bool { (1 <= n && n <= 6) || n == 9 }
pub open spec fn seeded(seeds: Set<int>, count: nat) -> St { St { seen: seeds, count: count, edges: seq![] } }
/// Witness (W56 P1; bug-plt-113): ppr_top_k = 3 gives the seeds s, a2, a1 and the cap 3, which they already fill;
/// only a1 is expanded. The answer lists a1->a2 and not s->a1 or s->a2, although s, a1 and a2 are all answered and
/// the rule lists those edges. Observed: nodes a1, a2, s; edges a1>a2.
pub proof fn theorem_guided_subgraph_drops_edges_among_top_nodes()
    ensures ({
        let st = admit(seq![9int, 2, 1], |n: int| star_has_edge(n), empty_st(), guided_cap(5000, 3));
        let r = expand_frontier(seq![1int, 2, 9], |n: int| star(n), st, guided_cap(5000, 3));
        r.edges == seq![(1int, 2int)] && !lists_edge(r, |n: int| star(n), (9int, 1int))
            && rule_lists_edge(r, |n: int| star(n), (9int, 1int)) && r.seen.contains(9) && r.seen.contains(1)
    }),
{
    reveal_with_fuel(admit, 4);
    reveal_with_fuel(expand_node, 3);
    reveal_with_fuel(expand_frontier, 3);
    let st = admit(seq![9int, 2, 1], |n: int| star_has_edge(n), empty_st(), 3);
    assert(seq![9int, 2, 1].drop_first() =~= seq![2int, 1]);
    assert(seq![2int, 1].drop_first() =~= seq![1int]);
    assert(seq![1int].drop_first() =~= seq![]);
    assert(st.seen =~= set![9int, 2, 1]);
    assert(st.count == 3);
    assert(st.edges =~= seq![]);
    let r1 = expand_node(1, seq![2int], st, 3);
    assert(seq![2int].drop_first() =~= seq![]);
    assert(r1.0.edges =~= seq![(1int, 2int)]);
    let r = expand_frontier(seq![1int, 2, 9], |n: int| star(n), st, guided_cap(5000, 3));
    assert(r.edges =~= seq![(1int, 2int)]);
    assert(!r.edges.contains((9int, 1int))) by {
        if r.edges.contains((9int, 1int)) { let i = choose|i: int| 0 <= i < r.edges.len() && r.edges[i] == (9int, 1int); assert(i == 0); }
    }
    assert(star(9)[0] == 1);
}
/// Witness (review 47-49, reproduced in iteration 50; bug-plt-113): seeds s, a3, a4 with ppr_top_k = 1 (top id a3)
/// give a cap of 1; all three seeds are admitted (3 nodes > 1) and the first frontier node a3 has no out-edge, so
/// the answer lists no edge, although the rule lists s->a3 and s->a4. Observed: nodes a3, a4, s; no edges.
pub proof fn theorem_guided_seeds_exceed_cap()
    ensures ({
        let st = admit(seq![9int, 3, 4], |n: int| star_has_edge(n), empty_st(), guided_cap(5000, 1));
        let r = expand_frontier(seq![3int, 4, 9], |n: int| star(n), st, guided_cap(5000, 1));
        r.count == 3 && !rule_within_cap(r, guided_cap(5000, 1)) && r.edges.len() == 0
            && !lists_edge(r, |n: int| star(n), (9int, 3int)) && rule_lists_edge(r, |n: int| star(n), (9int, 3int))
    }),
{
    reveal_with_fuel(admit, 4);
    reveal_with_fuel(expand_node, 2);
    reveal_with_fuel(expand_frontier, 2);
    let st = admit(seq![9int, 3, 4], |n: int| star_has_edge(n), empty_st(), 1);
    assert(seq![9int, 3, 4].drop_first() =~= seq![3int, 4]);
    assert(seq![3int, 4].drop_first() =~= seq![4int]);
    assert(seq![4int].drop_first() =~= seq![]);
    assert(st.seen =~= set![9int, 3, 4]);
    assert(st.count == 3);
    assert(st.edges =~= seq![]);
    assert(star(3) =~= seq![]);
    let r = expand_frontier(seq![3int, 4, 9], |n: int| star(n), st, guided_cap(5000, 1));
    assert(r == st);
    assert(star(9)[2] == 3);
    assert(star(9).contains(3));
}
/// Witness (W56 S_star_1hop; bug-plt-114): kg_SUBGRAPH([s], k_hops = 1) answers a1 and a2 but does not list a1->a2:
/// only the frontier's out-edges are recorded.
pub proof fn theorem_last_hop_edges_missing()
    ensures ({
        let r = expand_frontier(seq![9int], |n: int| star(n), seeded(set![9int], 1), 10000);
        r.seen.contains(1) && r.seen.contains(2) && !lists_edge(r, |n: int| star(n), (1int, 2int))
            && rule_lists_edge(r, |n: int| star(n), (1int, 2int)) && lists_edge(r, |n: int| star(n), (9int, 1int))
    }),
{
    reveal_with_fuel(expand_node, 8);
    reveal_with_fuel(expand_frontier, 2);
    let s0 = seeded(set![9int], 1);
    let r = expand_node(9, star(9), s0, 10000);
    assert(star(9).drop_first() =~= seq![2int, 3, 4, 5, 6]);
    assert(star(9).drop_first().drop_first() =~= seq![3int, 4, 5, 6]);
    assert(star(9).drop_first().drop_first().drop_first() =~= seq![4int, 5, 6]);
    assert(star(9).drop_first().drop_first().drop_first().drop_first() =~= seq![5int, 6]);
    assert(star(9).drop_first().drop_first().drop_first().drop_first().drop_first() =~= seq![6int]);
    assert(seq![6int].drop_first() =~= seq![]);
    let es = seq![(9int, 1int), (9int, 2int), (9int, 3int), (9int, 4int), (9int, 5int), (9int, 6int)];
    assert(r.0.edges =~= es);
    assert(!es.contains((1int, 2int))) by {
        if es.contains((1int, 2int)) { let i = choose|i: int| 0 <= i < es.len() && es[i] == (1int, 2int); }
    }
    assert(es[0] == (9int, 1int));
    assert(star(1)[0] == 2);
}
/// Neighbor witness (W56 PG_star_top50): ppr_top_k = 50 admits all seven reachable nodes under a cap of 50; every
/// edge among them is listed, as the rule requires.
pub proof fn theorem_guided_uncapped_lists_all_edges()
    ensures ({
        let st = admit(seq![9int, 2, 1, 3, 4, 5, 6], |n: int| star_has_edge(n), empty_st(), guided_cap(5000, 50));
        let r = expand_frontier(seq![1int, 2, 3, 4, 5, 6, 9], |n: int| star(n), st, guided_cap(5000, 50));
        rule_within_cap(r, guided_cap(5000, 50)) && r.count == 7
            && lists_edge(r, |n: int| star(n), (1int, 2int)) && lists_edge(r, |n: int| star(n), (9int, 1int))
            && lists_edge(r, |n: int| star(n), (9int, 6int))
    }),
{
    reveal_with_fuel(admit, 8);
    reveal_with_fuel(expand_node, 8);
    reveal_with_fuel(expand_frontier, 8);
    let seeds = seq![9int, 2, 1, 3, 4, 5, 6];
    assert(seeds.drop_first() =~= seq![2int, 1, 3, 4, 5, 6]);
    assert(seeds.drop_first().drop_first() =~= seq![1int, 3, 4, 5, 6]);
    assert(seeds.drop_first().drop_first().drop_first() =~= seq![3int, 4, 5, 6]);
    assert(seeds.drop_first().drop_first().drop_first().drop_first() =~= seq![4int, 5, 6]);
    assert(seeds.drop_first().drop_first().drop_first().drop_first().drop_first() =~= seq![5int, 6]);
    assert(seeds.drop_first().drop_first().drop_first().drop_first().drop_first().drop_first() =~= seq![6int]);
    assert(seq![6int].drop_first() =~= seq![]);
    let st = admit(seeds, |n: int| star_has_edge(n), empty_st(), 50);
    let all = set![9int, 2, 1, 3, 4, 5, 6];
    assert(st.seen =~= all);
    assert(st.count == 7);
    assert(st.edges =~= seq![]);
    let f = seq![1int, 2, 3, 4, 5, 6, 9];
    assert(f.drop_first() =~= seq![2int, 3, 4, 5, 6, 9]);
    assert(f.drop_first().drop_first() =~= seq![3int, 4, 5, 6, 9]);
    assert(f.drop_first().drop_first().drop_first() =~= seq![4int, 5, 6, 9]);
    assert(f.drop_first().drop_first().drop_first().drop_first() =~= seq![5int, 6, 9]);
    assert(f.drop_first().drop_first().drop_first().drop_first().drop_first() =~= seq![6int, 9]);
    assert(f.drop_first().drop_first().drop_first().drop_first().drop_first().drop_first() =~= seq![9int]);
    assert(seq![9int].drop_first() =~= seq![]);
    assert(seq![2int].drop_first() =~= seq![]);
    let s1 = expand_node(1, seq![2int], st, 50).0;
    assert(s1.edges =~= seq![(1int, 2int)]);
    assert(s1.seen == all && s1.count == 7);
    assert(star(2) =~= seq![]); assert(star(3) =~= seq![]); assert(star(4) =~= seq![]); assert(star(5) =~= seq![]); assert(star(6) =~= seq![]);
    assert(star(9).drop_first() =~= seq![2int, 3, 4, 5, 6]);
    assert(star(9).drop_first().drop_first() =~= seq![3int, 4, 5, 6]);
    assert(star(9).drop_first().drop_first().drop_first() =~= seq![4int, 5, 6]);
    assert(star(9).drop_first().drop_first().drop_first().drop_first() =~= seq![5int, 6]);
    assert(star(9).drop_first().drop_first().drop_first().drop_first().drop_first() =~= seq![6int]);
    let es = seq![(1int, 2int), (9int, 1int), (9int, 2int), (9int, 3int), (9int, 4int), (9int, 5int), (9int, 6int)];
    let s9 = expand_node(9, star(9), s1, 50).0;
    assert(s9.edges =~= es);
    let r = expand_frontier(f, |n: int| star(n), st, 50);
    assert(r == s9);
    assert(es[0] == (1int, 2int)); assert(es[1] == (9int, 1int)); assert(es[6] == (9int, 6int));
}

// =============================================================== multi_vector_search
pub enum Src { Rows(nat), Fails }
/// A failing source is logged and skipped; the answer is fused from the others, [] when none answered.
pub open spec fn mvs_rows(a: Src, b: Src) -> nat {
    (match a { Src::Rows(n) => n, Src::Fails => 0 }) + (match b { Src::Rows(n) => n, Src::Fails => 0 })
}
/// W56 M1 (held): a failing source contributes nothing and raises nothing; every source failing reads as no match.
pub proof fn theorem_failed_source_skipped()
    ensures mvs_rows(Src::Rows(6), Src::Fails) == mvs_rows(Src::Rows(6), Src::Rows(0)), mvs_rows(Src::Fails, Src::Fails) == 0,
{}

}
