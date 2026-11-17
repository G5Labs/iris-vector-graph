// product 3eaa79cf: the graph SQL procedures of Graph.KG.SqlProcs (iteration 53, Part B).
//   SQL entry points (iris_src/src/Graph/KG/SqlProcs.cls): MatchEdges 145-149 and MatchEdgesAllGraphs 151-155
//     (RequireSelect(rdf_edges), then Graph.KG.EdgeScan), DijkstraPath 160-164 (RequireSelect(rdf_edges), then
//     Graph.KG.Traversal.DijkstraProc 11-14 -> TraversalPaths.DijkstraJson 256-346), backfilltemporalrows 194-198
//     (RequireWrite(nodes, rdf_edges, "i"), then TemporalIndex.BackfillStructuralRows 232-235 -> BackfillWalk ->
//     Adjacency.AssertTemporalRow with pTrustIndex 0), rebuildedgeindices 200-203 (Ledger.RebuildEdgeIndices 224-240).
//   Scan: EdgeScan.MatchEdges 46-62 ($Char(0) -> "", "" graph -> key 0; shard never read), MatchEdgesAllGraphs 70-86
//     (every graph subscript of ^KG("out")), ScanOneGraph 95-145 (empty source: every source; empty predicate: every
//     predicate; w = the ^KG leaf, 1.0 when it has none; g = the graph name, "" for key 0).
//   Privilege: SqlPrivilege.RequireSelect / RequireWrite (%All passes; otherwise SQLCODE -99 naming the table).
//   Translator: _trp_directed_edge_join 16467-16530 (IVG_EDGESCAN=1, a hop from a node named by id, no USE GRAPH ->
//     MatchEdgesAllGraphs; USE GRAPH '' -> MatchEdges; a named graph -> rdf_edges), _expr_propref_edge_alias
//     22266-22273 (a property of an edge-scan alias is the literal NULL).
// The search itself (cost order, hop states, weights <= 0 as 1, maxCost, maxHops, direction, predicates) is the
// weighted_paths model's DijkstraJson; this model owns the SQL entry in front of it, the scan, the backfill and the
// index rebuild.
use vstd::prelude::*;

verus! {

// =============================================================== the edge scan
/// One adjacency entry ^KG("out", g, s, p, o) = w. Graph key 0 is the default graph; ids are positive, 0 stands for
/// SQL's '' (and NULL, and an omitted argument), which reach the body as $Char(0) or "" and are both read as "".
pub struct Arc { pub g: int, pub s: int, pub p: int, pub o: int, pub w: Option<int> }

/// A graph key as ScanOneGraph reads it (already normalized: 0 is the default graph, a name its own key).
pub open spec fn graph_key(graph: int) -> int { graph }

/// MatchEdges' raw graph argument as its body receives it (iteration 56, review 53-55 minor): SQL '' arrives as
/// $Char(0); NULL, an omitted argument and a bound '' arrive as ""; 0 and '0'; a graph name (Name(n), n > 0).
pub enum GArg { Char0, Empty, Zero, ZeroText, Name(int) }
/// EdgeScan.MatchEdges 52: `Set:graph=$Char(0) graph = ""`.
pub open spec fn after_nul(g: GArg) -> GArg { if g == GArg::Char0 { GArg::Empty } else { g } }
/// EdgeScan.MatchEdges 55-57: `If graph = "" { Set graph = 0 }`.
pub open spec fn after_empty(g: GArg) -> GArg { if g == GArg::Empty { GArg::Zero } else { g } }
/// The ^KG("out", graph, ...) subscript ScanOneGraph reads (provider: IRIS subscript collation, under which the text
/// "0" is the canonical number 0). A "" left in place would be a graph nobody writes (-1); a $Char(0) left in place a
/// graph named $Char(0) that nobody writes (-2).
pub open spec fn subscript_of(g: GArg) -> int {
    match g { GArg::Zero => 0, GArg::ZeroText => 0, GArg::Name(n) => n, GArg::Empty => -1, GArg::Char0 => -2 }
}
pub open spec fn graph_arg_key(g: GArg) -> int { subscript_of(after_empty(after_nul(g))) }
/// The scan MatchEdges answers for a raw graph argument.
pub open spec fn match_edges_arg(adj: Seq<Arc>, src: int, pred: int, shard: int, g: GArg) -> Seq<Arc> {
    match_edges(adj, src, pred, shard, graph_arg_key(g))
}
/// The weight the scan reports: the leaf's value, 1.0 when the leaf has none.
pub open spec fn scan_w(a: Arc) -> int { match a.w { Some(w) => w, None => 1 } }
/// ScanOneGraph's test for one graph key: source and predicate each match, or are '' (every one).
pub open spec fn scan_hit(a: Arc, key: int, src: int, pred: int, shard: int) -> bool {
    a.g == key && (src == 0 || a.s == src) && (pred == 0 || a.p == pred)
}
pub open spec fn match_edges(adj: Seq<Arc>, src: int, pred: int, shard: int, graph: int) -> Seq<Arc> {
    adj.filter(|a: Arc| scan_hit(a, graph_key(graph), src, pred, shard))
}
/// MatchEdgesAllGraphs: ScanOneGraph for every graph key ^KG("out") holds.
pub open spec fn all_hit(a: Arc, src: int, pred: int, shard: int) -> bool {
    (src == 0 || a.s == src) && (pred == 0 || a.p == pred)
}
pub open spec fn match_all(adj: Seq<Arc>, src: int, pred: int, shard: int) -> Seq<Arc> {
    adj.filter(|a: Arc| all_hit(a, src, pred, shard))
}

// =============================================================== the privilege gate
pub enum Ans<T> { Refused, Ok(T) }
/// What an entry does with RequireSelect / RequireWrite's verdict (`holds`: the call returned $$$OK).
pub open spec fn gate<T>(holds: bool, t: T) -> Ans<T> { if holds { Ans::Ok(t) } else { Ans::Refused } }

// --------------------------------------------------------------- the verdict, derived from the caller's grants
// (iteration 56, review 53-55 F4: the verdict was an input; now it is computed from what IRIS records for the caller.)
pub enum Act { S, I, U, D }
/// What one grantee (the user, or one of its roles) holds as IRIS records it: privileges on a table, on a schema, and
/// column privileges (on some columns of a table).
pub struct Grantee { pub table: Set<(int, Act)>, pub schema: Set<(int, Act)>, pub column: Set<(int, Act)> }
/// The caller: $Username's own grants, the roles in $Roles, and whether %All is among them.
pub struct Caller { pub all: bool, pub user: Grantee, pub roles: Seq<Grantee> }
/// Provider premise P-CHECKPRIV: $SYSTEM.SQL.Security.CheckPrivilege(grantee, 1, table, a) is true when the grantee
/// holds a on the table or on the table's schema; a column privilege does not count (ADMIN_GUIDE 574-576; observed by
/// the binding's users).
pub open spec fn check_priv(gr: Grantee, sch: int, t: int, a: Act) -> bool {
    gr.table.contains((t, a)) || gr.schema.contains((sch, a))
}
/// SqlPrivilege.Holds 106-121: the user, or else the first role in $Roles that holds it.
pub open spec fn any_role(roles: Seq<Grantee>, sch: int, t: int, a: Act) -> bool decreases roles.len() {
    if roles.len() == 0 { false } else { check_priv(roles.last(), sch, t, a) || any_role(roles.drop_last(), sch, t, a) }
}
pub open spec fn holds_priv(c: Caller, sch: int, t: int, a: Act) -> bool {
    check_priv(c.user, sch, t, a) || any_role(c.roles, sch, t, a)
}
pub enum Gate { Pass, Refused(int, Act) }
/// The inner loop of RequireWrite (49-53): the first action of acts not held on t.
pub open spec fn first_act(c: Caller, sch: int, t: int, acts: Seq<Act>) -> Option<Act> decreases acts.len() {
    if acts.len() == 0 { None }
    else if !holds_priv(c, sch, t, acts[0]) { Some(acts[0]) }
    else { first_act(c, sch, t, acts.subrange(1, acts.len() as int)) }
}
/// The outer loop of RequireSelect (24-28) / RequireWrite (44-54): the first table, then action, not held.
pub open spec fn first_missing(c: Caller, sch: int, ts: Seq<int>, acts: Seq<Act>) -> Option<(int, Act)> decreases ts.len() {
    if ts.len() == 0 { None }
    else { match first_act(c, sch, ts[0], acts) {
        Some(a) => Some((ts[0], a)),
        None => first_missing(c, sch, ts.subrange(1, ts.len() as int), acts),
    } }
}
/// RequireSelect(ts) is require(c, sch, ts, [S]); RequireWrite(ts, "i") is require(c, sch, ts, [I]). %All passes
/// before any check (lines 22 and 41); otherwise SQLCODE -99 naming the first missing privilege and table.
pub open spec fn require(c: Caller, sch: int, ts: Seq<int>, acts: Seq<Act>) -> Gate {
    if c.all { Gate::Pass }
    else { match first_missing(c, sch, ts, acts) { None => Gate::Pass, Some(x) => Gate::Refused(x.0, x.1) } }
}
/// The tables the entries name, in the IVG Schema sch.
pub open spec fn t_nodes() -> int { 1 }
pub open spec fn t_edges() -> int { 2 }
pub open spec fn select_ok(c: Caller, sch: int) -> bool { require(c, sch, seq![t_edges()], seq![Act::S]) == Gate::Pass }
pub open spec fn insert_ok(c: Caller, sch: int) -> bool {
    require(c, sch, seq![t_nodes(), t_edges()], seq![Act::I]) == Gate::Pass
}
/// SqlProcs.MatchEdges 145-149 for a caller: RequireSelect(rdf_edges), then the scan.
pub open spec fn match_edges_sql(c: Caller, sch: int, adj: Seq<Arc>, src: int, pred: int, shard: int, g: GArg) -> Ans<Seq<Arc>> {
    gate(select_ok(c, sch), match_edges_arg(adj, src, pred, shard, g))
}
/// SqlProcs.MatchEdgesAllGraphs 151-155: RequireSelect(rdf_edges), then every graph's scan.
pub open spec fn match_all_sql(c: Caller, sch: int, adj: Seq<Arc>, src: int, pred: int, shard: int) -> Ans<Seq<Arc>> {
    gate(select_ok(c, sch), match_all(adj, src, pred, shard))
}
/// SqlProcs.DijkstraPath 160-164: RequireSelect(rdf_edges), then DijkstraProc -> DijkstraJson.
pub open spec fn dijkstra_sql(c: Caller, sch: int, src: End, dst: End, wp: WProp, dir: Dir) -> Ans<PathAns> {
    dijkstra_path(select_ok(c, sch), src, dst, wp, dir)
}

// =============================================================== the Cypher hop on the two SQL plans
pub enum Plan { Rows, Scan }
/// Which plan a directed hop from a node named by id takes (no inline relationship properties, no USE GRAPH of a
/// named graph): IVG_EDGESCAN=1 takes the scan, otherwise the rdf_edges join.
pub open spec fn plan(edgescan_env: bool, named_graph: bool) -> Plan {
    if edgescan_env && !named_graph { Plan::Scan } else { Plan::Rows }
}
/// `r.weight` of the hop: the rows plan reads the row's qualifiers (the weight given to the write, null when none);
/// the scan alias is the literal NULL for every relationship property.
pub open spec fn rel_weight(pl: Plan, a: Arc) -> Option<int> {
    match pl { Plan::Rows => a.w, Plan::Scan => None }
}
/// The hop's targets: both plans read the same edges (the declared index keeps ^KG and the rows in step).
pub open spec fn hop_targets(pl: Plan, adj: Seq<Arc>, src: int, pred: int) -> Seq<Arc> { match_all(adj, src, pred, 0) }

// =============================================================== DijkstraPath: the SQL entry in front of DijkstraJson
pub enum Dir { Out, In, Both, Other }
pub enum WProp { Empty, Weight, Other }
/// An endpoint argument as DijkstraJson sees it: Missing is "", Nul is SQL's '' ($Char(0)), Id a node id.
pub enum End { Missing, Nul, Id(int) }
/// SQL hands '' to a procedure body as $Char(0); the Python CALL refuses an empty endpoint before SQL.
pub open spec fn sql_end(empty: bool, id: int) -> End { if empty { End::Nul } else { End::Id(id) } }
pub enum PathAns { Raises, NoPath, ZeroPath(End), Search }
/// DijkstraJson 256-285: CheckWeightProp, CheckDirection, then "" endpoints -> "{}", equal endpoints -> the empty
/// path at cost 0 (before any cost cap or node check), otherwise the search (weighted_paths).
pub open spec fn dijkstra_json(src: End, dst: End, wp: WProp, dir: Dir) -> PathAns {
    if wp == WProp::Other { PathAns::Raises }
    else if dir == Dir::Other { PathAns::Raises }
    else if src == End::Missing || dst == End::Missing { PathAns::NoPath }
    else if src == dst { PathAns::ZeroPath(src) }
    else { PathAns::Search }
}
pub open spec fn dijkstra_path(select: bool, src: End, dst: End, wp: WProp, dir: Dir) -> Ans<PathAns> {
    gate(select, dijkstra_json(src, dst, wp, dir))
}
/// The owner's rule for an empty endpoint: no path (algorithms.op.paths.weighted).
pub open spec fn rule_empty_endpoint() -> PathAns { PathAns::NoPath }

// =============================================================== backfill_temporal_rows
pub type Tri = (int, int, int, int); // (graph key, s, p, o)
/// The stores the backfill reads and writes: the distinct triples ^KG("tout") holds, the temporal-only registrations
/// (graph key, predicate), and the structural rows with their temporal mark.
pub struct Bf { pub tout: Set<Tri>, pub optout: Set<(int, int)>, pub rows: Map<Tri, bool> }
pub open spec fn structural(st: Bf) -> Set<Tri> { st.tout.filter(|t: Tri| !st.optout.contains((t.0, t.2))) }
/// AssertTemporalRow with pTrustIndex 0: a triple with no row gets a marked row (and its endpoint nodes); a row
/// already there, marked or not, is left as it is.
pub open spec fn backfill_rows(st: Bf) -> Map<Tri, bool> {
    Map::new(st.rows.dom().union(structural(st)), |t: Tri| if st.rows.contains_key(t) { st.rows[t] } else { true })
}
pub open spec fn backfill(st: Bf) -> Bf { Bf { rows: backfill_rows(st), ..st } }
/// The answer: BackfillWalk's `asserted`, one per structural triple walked (premise P-SEEN: fewer distinct triples
/// per graph than the seen limit, 100000, so none is walked twice).
pub open spec fn backfill_count(st: Bf) -> nat { structural(st).len() }
/// What ADMIN_GUIDE:413 says setup's temporal_rows_backfilled is: "the temporal edges it gave rows first".
pub open spec fn rows_written(st: Bf) -> nat { structural(st).filter(|t: Tri| !st.rows.contains_key(t)).len() }
pub open spec fn backfill_sql(insert_priv: bool, st: Bf) -> Ans<(Bf, nat)> { gate(insert_priv, (backfill(st), backfill_count(st))) }

// =============================================================== rebuild_edge_indices
pub enum Schema { NotIdentifier, Missing, Present }
pub enum RbAns { RaisesNotIdentifier, RaisesNamingTable, Ok(nat) }
/// RebuildEdgeIndices 224-240: refuse a schema that is not an SQL identifier before any statement; then BUILD INDEX on
/// nodes, rdf_labels, rdf_props and rdf_edges in turn; a refused (no %BUILD_INDEX) or failed (no such table)
/// statement raises naming the table (4.6.0: it answered 0); four statements answer 4.
pub open spec fn rebuild(schema: Schema, build_priv: bool) -> RbAns {
    match schema {
        Schema::NotIdentifier => RbAns::RaisesNotIdentifier,
        Schema::Missing => RbAns::RaisesNamingTable,
        Schema::Present => if build_priv { RbAns::Ok(4) } else { RbAns::RaisesNamingTable },
    }
}

// =============================================================== theorems: the scan
/// ME1: an empty predicate answers every predicate of the source in that graph; a named one answers only its own.
pub proof fn theorem_empty_predicate_every_predicate(adj: Seq<Arc>, src: int, shard: int, graph: int, a: Arc, p: int)
    requires adj.contains(a), a.g == graph, a.s == src, p != 0, p != a.p,
    ensures
        match_edges(adj, src, 0, shard, graph).contains(a),
        match_edges(adj, src, a.p, shard, graph).contains(a),
        !match_edges(adj, src, p, shard, graph).contains(a),
{
    let f0 = |b: Arc| scan_hit(b, graph_key(graph), src, 0, shard);
    let fp = |b: Arc| scan_hit(b, graph_key(graph), src, a.p, shard);
    let fq = |b: Arc| scan_hit(b, graph_key(graph), src, p, shard);
    adj.lemma_filter_contains_rev(f0, a);
    adj.lemma_filter_contains_rev(fp, a);
    if adj.filter(fq).contains(a) {
        let i = choose|i: int| 0 <= i < adj.filter(fq).len() && adj.filter(fq)[i] == a;
        adj.lemma_filter_pred(fq, i);
    }
}

/// ME5: the shard argument is never read: every shard answers the same edges.
pub proof fn theorem_shard_ignored(adj: Seq<Arc>, src: int, pred: int, graph: int, sh1: int, sh2: int)
    ensures
        match_edges(adj, src, pred, sh1, graph) == match_edges(adj, src, pred, sh2, graph),
        match_all(adj, src, pred, sh1) == match_all(adj, src, pred, sh2),
{
    let f1 = |a: Arc| scan_hit(a, graph_key(graph), src, pred, sh1);
    let f2 = |a: Arc| scan_hit(a, graph_key(graph), src, pred, sh2);
    let g1 = |a: Arc| all_hit(a, src, pred, sh1);
    let g2 = |a: Arc| all_hit(a, src, pred, sh2);
    assert(f1 =~= f2);
    assert(g1 =~= g2);
}

/// ME2: one graph's scan never answers another graph's edge (the default graph included), while the all-graphs scan
/// answers it with its own graph.
pub proof fn theorem_graph_scoped_vs_all(adj: Seq<Arc>, src: int, pred: int, shard: int, graph: int, a: Arc)
    requires adj.contains(a), a.g != graph, src == 0 || a.s == src, pred == 0 || a.p == pred,
    ensures
        !match_edges(adj, src, pred, shard, graph).contains(a),
        match_all(adj, src, pred, shard).contains(a),
        match_edges(adj, src, pred, shard, a.g).contains(a),
{
    let f = |b: Arc| scan_hit(b, graph_key(graph), src, pred, shard);
    let fa = |b: Arc| all_hit(b, src, pred, shard);
    let fg = |b: Arc| scan_hit(b, graph_key(a.g), src, pred, shard);
    adj.lemma_filter_contains_rev(fa, a);
    adj.lemma_filter_contains_rev(fg, a);
    if adj.filter(f).contains(a) {
        let i = choose|i: int| 0 <= i < adj.filter(f).len() && adj.filter(f)[i] == a;
        adj.lemma_filter_pred(f, i);
    }
}

/// The same triple in two graphs is answered twice by the all-graphs scan, once per graph, each with its weight.
pub proof fn theorem_shared_triple_once_per_graph(a: Arc, b: Arc)
    requires a.g != b.g, a.s == b.s, a.p == b.p, a.o == b.o,
    ensures ({
        let adj = seq![a, b];
        match_all(adj, a.s, a.p, 0) == adj && match_edges(adj, a.s, a.p, 0, a.g) == seq![a]
    }),
{
    let adj = seq![a, b];
    reveal_with_fuel(Seq::filter, 3);
    assert(adj.drop_last() =~= seq![a]);
    assert(seq![a].drop_last() =~= Seq::<Arc>::empty());
    assert(match_all(adj, a.s, a.p, 0) =~= adj);
    assert(match_edges(adj, a.s, a.p, 0, a.g) =~= seq![a]);
}

// =============================================================== theorems: privilege
/// ME3, DJ9, BF4: without the privilege each SQL entry fails before reading or writing; with it, it answers.
pub proof fn theorem_entries_gated(adj: Seq<Arc>, src: int, pred: int, graph: int, st: Bf, s2: End, d2: End)
    ensures
        gate(false, match_edges(adj, src, pred, 0, graph)) == Ans::<Seq<Arc>>::Refused,
        gate(false, match_all(adj, src, pred, 0)) == Ans::<Seq<Arc>>::Refused,
        dijkstra_path(false, s2, d2, WProp::Empty, Dir::Out) == Ans::<PathAns>::Refused,
        backfill_sql(false, st) == Ans::<(Bf, nat)>::Refused,
        gate(true, match_edges(adj, src, pred, 0, graph)) == Ans::Ok(match_edges(adj, src, pred, 0, graph)),
        backfill_sql(true, st) == Ans::Ok((backfill(st), backfill_count(st))),
{}

// =============================================================== theorems: the privilege verdict (iteration 56, F4)
/// %All passes every check before any grant is read (RequireSelect 22, RequireWrite 41).
pub proof fn theorem_all_passes(c: Caller, sch: int, ts: Seq<int>, acts: Seq<Act>)
    requires c.all,
    ensures require(c, sch, ts, acts) == Gate::Pass,
{}

/// General, one table and one action: a caller without %All passes exactly when it, or one of its roles, holds the
/// privilege on the table or on its schema; otherwise the refusal names that table and privilege.
pub proof fn theorem_single_check_iff_holds(c: Caller, sch: int, t: int, a: Act)
    requires !c.all,
    ensures require(c, sch, seq![t], seq![a]) == (if holds_priv(c, sch, t, a) { Gate::Pass } else { Gate::Refused(t, a) }),
{
    reveal_with_fuel(first_missing, 2);
    reveal_with_fuel(first_act, 2);
    assert(seq![t].subrange(1, 1) =~= Seq::<int>::empty());
    assert(seq![a].subrange(1, 1) =~= Seq::<Act>::empty());
}

proof fn lemma_any_role(roles: Seq<Grantee>, sch: int, t: int, a: Act, i: int)
    requires 0 <= i < roles.len(), check_priv(roles[i], sch, t, a),
    ensures any_role(roles, sch, t, a),
    decreases roles.len(),
{
    if i < roles.len() - 1 {
        assert(roles.drop_last()[i] == roles[i]);
        lemma_any_role(roles.drop_last(), sch, t, a, i);
    }
}

/// ADMIN_GUIDE 576 "SELECT on some of its columns does not [count]": a caller whose only SELECT on rdf_edges is a
/// column privilege is refused naming rdf_edges, and MatchEdges answers nothing.
pub proof fn theorem_column_only_select_refused(c: Caller, sch: int, adj: Seq<Arc>, src: int, pred: int, shard: int, g: GArg)
    requires
        !c.all, c.roles.len() == 0,
        c.user.column.contains((t_edges(), Act::S)),
        !c.user.table.contains((t_edges(), Act::S)), !c.user.schema.contains((sch, Act::S)),
    ensures
        require(c, sch, seq![t_edges()], seq![Act::S]) == Gate::Refused(t_edges(), Act::S),
        match_edges_sql(c, sch, adj, src, pred, shard, g) == Ans::<Seq<Arc>>::Refused,
{
    theorem_single_check_iff_holds(c, sch, t_edges(), Act::S);
}

/// Neighbors: SELECT on the table, on its schema, or held by any role in $Roles each pass, and MatchEdges answers
/// the scan.
pub proof fn theorem_table_schema_role_select_pass(c: Caller, sch: int, adj: Seq<Arc>, src: int, pred: int, shard: int, g: GArg, i: int)
    requires
        !c.all,
        c.user.table.contains((t_edges(), Act::S)) || c.user.schema.contains((sch, Act::S))
            || (0 <= i < c.roles.len() && c.roles[i].table.contains((t_edges(), Act::S))),
    ensures
        require(c, sch, seq![t_edges()], seq![Act::S]) == Gate::Pass,
        match_edges_sql(c, sch, adj, src, pred, shard, g) == Ans::Ok(match_edges_arg(adj, src, pred, shard, g)),
{
    if !(c.user.table.contains((t_edges(), Act::S)) || c.user.schema.contains((sch, Act::S))) {
        lemma_any_role(c.roles, sch, t_edges(), Act::S, i);
    }
    theorem_single_check_iff_holds(c, sch, t_edges(), Act::S);
}

/// RequireWrite(nodes, rdf_edges, "i") names the first missing pair in table order: no INSERT on nodes names nodes;
/// INSERT on nodes but not on rdf_edges names rdf_edges; both pass. backfill_temporal_rows follows the verdict.
pub proof fn theorem_write_names_first_missing(c: Caller, sch: int, st: Bf)
    requires !c.all,
    ensures
        !holds_priv(c, sch, t_nodes(), Act::I) ==> require(c, sch, seq![t_nodes(), t_edges()], seq![Act::I]) == Gate::Refused(t_nodes(), Act::I),
        holds_priv(c, sch, t_nodes(), Act::I) && !holds_priv(c, sch, t_edges(), Act::I)
            ==> require(c, sch, seq![t_nodes(), t_edges()], seq![Act::I]) == Gate::Refused(t_edges(), Act::I),
        holds_priv(c, sch, t_nodes(), Act::I) && holds_priv(c, sch, t_edges(), Act::I)
            ==> backfill_sql(insert_ok(c, sch), st) == Ans::Ok((backfill(st), backfill_count(st))),
        !holds_priv(c, sch, t_nodes(), Act::I) ==> backfill_sql(insert_ok(c, sch), st) == Ans::<(Bf, nat)>::Refused,
{
    reveal_with_fuel(first_missing, 3);
    reveal_with_fuel(first_act, 2);
    assert(seq![Act::I].subrange(1, 1) =~= Seq::<Act>::empty());
    assert(seq![t_nodes(), t_edges()].subrange(1, 2) =~= seq![t_edges()]);
    assert(seq![t_edges()].subrange(1, 1) =~= Seq::<int>::empty());
}

/// The three reading entries check SELECT on rdf_edges, the table ^KG stands for: a caller holding SELECT on nodes
/// only is refused by all three, and one holding it on rdf_edges answered by all three (the table is the entries'
/// own choice; ADMIN_GUIDE 572-574).
pub proof fn theorem_readers_check_rdf_edges(c: Caller, sch: int, adj: Seq<Arc>, src: int, pred: int, g: GArg, s2: End, d2: End)
    requires !c.all, c.roles.len() == 0, !c.user.schema.contains((sch, Act::S)),
    ensures
        c.user.table.contains((t_nodes(), Act::S)) && !c.user.table.contains((t_edges(), Act::S)) ==> {
            &&& match_edges_sql(c, sch, adj, src, pred, 0, g) == Ans::<Seq<Arc>>::Refused
            &&& match_all_sql(c, sch, adj, src, pred, 0) == Ans::<Seq<Arc>>::Refused
            &&& dijkstra_sql(c, sch, s2, d2, WProp::Empty, Dir::Out) == Ans::<PathAns>::Refused
        },
        c.user.table.contains((t_edges(), Act::S)) ==> {
            &&& match_edges_sql(c, sch, adj, src, pred, 0, g) == Ans::Ok(match_edges_arg(adj, src, pred, 0, g))
            &&& match_all_sql(c, sch, adj, src, pred, 0) == Ans::Ok(match_all(adj, src, pred, 0))
            &&& dijkstra_sql(c, sch, s2, d2, WProp::Empty, Dir::Out) == Ans::Ok(dijkstra_json(s2, d2, WProp::Empty, Dir::Out))
        },
{
    theorem_single_check_iff_holds(c, sch, t_edges(), Act::S);
}

// =============================================================== theorems: MatchEdges' graph argument
/// SQL '' (arriving as $Char(0)), "" (NULL, an omitted argument, a bound ''), 0 and '0' all read the default
/// graph's key 0; a name reads its own graph (and theorem_graph_scoped_vs_all keeps the graphs apart).
pub proof fn theorem_default_graph_spellings(adj: Seq<Arc>, src: int, pred: int, shard: int, n: int)
    requires n > 0,
    ensures
        graph_arg_key(GArg::Char0) == 0, graph_arg_key(GArg::Empty) == 0,
        graph_arg_key(GArg::Zero) == 0, graph_arg_key(GArg::ZeroText) == 0,
        graph_arg_key(GArg::Name(n)) == n,
        match_edges_arg(adj, src, pred, shard, GArg::Char0) == match_edges(adj, src, pred, shard, 0),
        match_edges_arg(adj, src, pred, shard, GArg::Empty) == match_edges(adj, src, pred, shard, 0),
        match_edges_arg(adj, src, pred, shard, GArg::ZeroText) == match_edges(adj, src, pred, shard, 0),
{}

// =============================================================== theorems: the IVG_EDGESCAN plan
/// bug-cyp-133: with IVG_EDGESCAN=1 a hop from a node named by id reads the same edges, but every relationship
/// property, `r.weight` included, reads null where the rows plan reads the stored value.
pub proof fn theorem_edgescan_reads_null_property(adj: Seq<Arc>, src: int, pred: int, a: Arc, w: int)
    requires a.w == Some(w),
    ensures
        plan(true, false) == Plan::Scan, plan(false, false) == Plan::Rows, plan(true, true) == Plan::Rows,
        hop_targets(Plan::Scan, adj, src, pred) == hop_targets(Plan::Rows, adj, src, pred),
        rel_weight(Plan::Rows, a) == Some(w),
        rel_weight(Plan::Scan, a) == Option::<int>::None,
        rel_weight(plan(true, false), a) != rel_weight(plan(false, false), a),
{}
/// Neighbor: an edge written without a weight reads null on both plans, and a named graph never takes the scan.
pub proof fn theorem_unweighted_and_named_agree(a: Arc, env: bool)
    requires a.w == Option::<int>::None,
    ensures rel_weight(plan(env, false), a) == rel_weight(plan(false, false), a),
            rel_weight(plan(env, true), a) == rel_weight(Plan::Rows, a),
{}

// =============================================================== theorems: DijkstraPath
/// DJ6: the SQL entry refuses a direction or weight property the procedure refuses (the checks are in DijkstraJson,
/// not only in Python), for every endpoint pair.
pub proof fn theorem_sql_entry_refuses_bad_arguments(s: End, d: End, wp: WProp, dir: Dir)
    requires wp == WProp::Other || dir == Dir::Other,
    ensures dijkstra_path(true, s, d, wp, dir) == Ans::Ok(PathAns::Raises),
{}
/// bug-str-112: SQL's '' for both endpoints is $Char(0) in the body, which the empty test misses and the equal test
/// takes: a zero-length path through a node named $Char(0), where the rule answers no path.
pub proof fn theorem_sql_empty_endpoints_zero_path(wp: WProp, dir: Dir)
    requires wp != WProp::Other, dir != Dir::Other,
    ensures
        dijkstra_path(true, sql_end(true, 0), sql_end(true, 0), wp, dir) == Ans::Ok(PathAns::ZeroPath(End::Nul)),
        dijkstra_json(sql_end(true, 0), sql_end(true, 0), wp, dir) != rule_empty_endpoint(),
{}
/// Neighbors: an equal pair of ids answers the empty path; one '' endpoint and one id searches from $Char(0), which
/// has no edges (no path, through weighted_paths); a "" endpoint from ObjectScript answers no path.
pub proof fn theorem_dijkstra_endpoint_neighbors(x: int, y: int, wp: WProp, dir: Dir)
    requires wp != WProp::Other, dir != Dir::Other, x != y,
    ensures
        dijkstra_json(End::Id(x), End::Id(x), wp, dir) == PathAns::ZeroPath(End::Id(x)),
        dijkstra_json(sql_end(true, 0), End::Id(y), wp, dir) == PathAns::Search,
        dijkstra_json(End::Missing, End::Id(y), wp, dir) == rule_empty_endpoint(),
        dijkstra_json(End::Id(x), End::Id(y), wp, dir) == PathAns::Search,
{}

// =============================================================== theorems: the backfill
proof fn lemma_subset_len_lt(a: Set<Tri>, b: Set<Tri>, t: Tri)
    requires a.subset_of(b), b.contains(t), !a.contains(t),
    ensures a.len() < b.len(),
{
    vstd::set_lib::lemma_len_subset(a, b.remove(t));
}
/// BF1/BF5: every structural triple has a row afterwards, a missing one marked; a row already there keeps its mark,
/// so an explicit (unmarked) edge stays unmarked; a temporal-only triple gets none.
pub proof fn theorem_backfill_writes_missing_only(st: Bf, t: Tri)
    ensures
        structural(st).contains(t) ==> backfill(st).rows.contains_key(t),
        structural(st).contains(t) && !st.rows.contains_key(t) ==> backfill(st).rows[t] == true,
        st.rows.contains_key(t) ==> backfill(st).rows[t] == st.rows[t],
        st.optout.contains((t.0, t.2)) && !st.rows.contains_key(t) ==> !backfill(st).rows.contains_key(t),
{}
/// BF2: a second run writes nothing new and answers the same count again (not 0).
pub proof fn theorem_backfill_idempotent_same_count(st: Bf)
    ensures
        backfill(backfill(st)).rows == backfill(st).rows,
        backfill_count(backfill(st)) == backfill_count(st),
{
    assert(backfill(backfill(st)).rows =~= backfill(st).rows);
}
/// bug-tmp-107: the count is every structural triple walked; once one of them already has a row it exceeds the rows
/// written, which is what setup's `temporal_rows_backfilled` is documented to report.
pub proof fn theorem_backfill_count_overstates(st: Bf, t: Tri)
    requires structural(st).contains(t), st.rows.contains_key(t),
    ensures rows_written(st) < backfill_count(st),
{
    let s = structural(st);
    let m = s.filter(|u: Tri| !st.rows.contains_key(u));
    assert(m.subset_of(s));
    lemma_subset_len_lt(m, s, t);
}
/// Neighbor: when no structural triple has a row yet (the upgrade case the setup report describes), the count is the
/// rows written.
pub proof fn theorem_backfill_count_exact_when_all_missing(st: Bf)
    requires forall|t: Tri| structural(st).contains(t) ==> !st.rows.contains_key(t),
    ensures rows_written(st) == backfill_count(st),
{
    assert(structural(st).filter(|u: Tri| !st.rows.contains_key(u)) =~= structural(st));
}

// =============================================================== theorems: the index rebuild
/// RB1-RB4: four statements answer 4; a schema that is not an identifier is refused before any statement, and a
/// missing %BUILD_INDEX or a missing table raises (never 0).
pub proof fn theorem_rebuild_answers_four_or_raises(schema: Schema, priv_: bool)
    ensures
        rebuild(Schema::Present, true) == RbAns::Ok(4),
        rebuild(Schema::NotIdentifier, priv_) == RbAns::RaisesNotIdentifier,
        rebuild(Schema::Present, false) == RbAns::RaisesNamingTable,
        rebuild(Schema::Missing, priv_) == RbAns::RaisesNamingTable,
        rebuild(schema, priv_) != RbAns::Ok(0),
{}

} // verus!
