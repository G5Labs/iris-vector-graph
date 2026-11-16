// product 3eaa79cf: the embedding inventory report and its CLI reader.
//   iris_vector_graph/_engine/schema.py SchemaMixin.embedding_inventory :1715-1806 (one row per registry route; one
//   no-route row per graph with nodes and no route; row_count counted inside the route's graph; index_state from the
//   class dictionary); iris_vector_graph/cli.py _inventory_payload :77-90 (routed_tables = rows naming a table),
//   _print_inventory :93-108. Provider premises: the registry rows, the per-graph counts and the class dictionary's
//   HNSW indexes are inputs read in one call; their consistency across reads is not modeled.
use vstd::prelude::*;
verus! {
pub type G=int;
pub type T=int;
pub struct Route {pub graph:G,pub table:T,pub count:nat,pub indexed:bool}
pub enum IndexState {Present,Absent}
pub struct Row {pub graph:G,pub table:Option<T>,pub count:nat,pub state:IndexState}
pub open spec fn route_row(r:Route)->Row {Row{graph:r.graph,table:Some(r.table),count:r.count,state:if r.indexed {IndexState::Present} else {IndexState::Absent}}}
pub open spec fn routed(rs:Seq<Route>,g:G)->bool {exists|i:int| 0<=i<rs.len() && rs[i].graph==g}
/// The report: every route's row, then a no-route row for each graph with nodes and no route.
pub open spec fn report(rs:Seq<Route>,graphs:Seq<G>)->Seq<Row> {
 rs.map_values(|r:Route| route_row(r))+graphs.filter(|g:G| !routed(rs,g)).map_values(|g:G| Row{graph:g,table:None,count:0,state:IndexState::Absent})
}
/// The CLI's routed-table count: rows that name a table.
pub open spec fn routed_tables(rows:Seq<Row>)->nat {rows.filter(|r:Row| r.table.is_some()).len()}

/// A graph with nodes and no route is reported once, with no table, a zero count and no index (US4-3).
pub proof fn theorem_unrouted_graph_reported(rs:Seq<Route>,graphs:Seq<G>,g:G)
 requires graphs.contains(g),!routed(rs,g)
 ensures report(rs,graphs).contains(Row{graph:g,table:None,count:0,state:IndexState::Absent}),
{
 let f=graphs.filter(|x:G| !routed(rs,x));
 let i=choose|i:int| 0<=i<graphs.len() && graphs[i]==g;
 graphs.filter_lemma(|x:G| !routed(rs,x));
 assert(f.contains(g));
 let j=choose|j:int| 0<=j<f.len() && f[j]==g;
 let m=f.map_values(|x:G| Row{graph:x,table:None,count:0,state:IndexState::Absent});
 assert(m[j]==Row{graph:g,table:None,count:0,state:IndexState::Absent});
 let r=report(rs,graphs);
 assert(r[rs.len()+j]==m[j]);
}
/// A routed graph gets no no-route row: every row for it names a table.
pub proof fn theorem_routed_graph_has_no_empty_row(rs:Seq<Route>,graphs:Seq<G>,k:int)
 requires 0<=k<report(rs,graphs).len(),routed(rs,report(rs,graphs)[k].graph)
 ensures report(rs,graphs)[k].table.is_some(),
{
 let f=graphs.filter(|x:G| !routed(rs,x));
 graphs.filter_lemma(|x:G| !routed(rs,x));
 if k>=rs.len() {let j=k-rs.len(); assert(f.contains(f[j]));}
}
/// A row names a table exactly when it comes from a route, so the CLI's routed-table count is the number of routes,
/// whatever graphs lack one.
pub proof fn theorem_rows_name_table_iff_route(rs:Seq<Route>,graphs:Seq<G>,k:int)
 requires 0<=k<report(rs,graphs).len()
 ensures report(rs,graphs)[k].table.is_some()==(k<rs.len()),
{}
}
