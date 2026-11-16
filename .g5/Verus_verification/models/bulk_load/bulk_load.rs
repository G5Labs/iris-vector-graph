// product 3eaa79cf: the standalone BulkLoader and the index-based readers that observe its rows.
//   iris_vector_graph/bulk_loader.py: _known_nodes_sql :182-199 (skip scan, %NOINDEX hint, graph-scoped),
//   load_nodes :252-378 (phase 1 nodes, phase 2 labels, phase 3 properties; only new ids reach phases 2-3; per-batch
//   commit :115-116; a failed phase rolls back its own batch :119-120 and raises), _executemany_batched :83-154,
//   rebuild_all_indices :484-510 (%BuildIndices on the four classes). Reader: get_node -> get_nodes (index equality
//   reads, graph-scoped), observed natively to return nothing for a %NOINDEX row until the rebuild.
//   Schema (iteration 31): SCHEMA = "Graph_KG" :41 is the default, and rebuild_all_indices names Graph.KG.* classes :495
//   whatever schema the loader was given.
// Domain: one batch per phase (batch_size >= input), distinct input ids, skip_existing=True (the default). The SQL
// engine's index behavior is a provider premise observed on the fixture, not derived here.
use vstd::prelude::*;
verus! {
pub type Node=int;
pub type Graph=int;
pub type Lbl=int;
pub type Key=int;
/// The property key the loader always writes (`props = {"id": nid}` :338).
pub open spec fn id_key()->Key {0}
/// One node id's rows in one graph. `*_ix` says whether those rows are in their table's index: a `%NOINDEX` insert
/// leaves them out until `%BuildIndices`.
pub struct Rec {pub node_ix:bool,pub labels:Set<Lbl>,pub labels_ix:bool,pub props:Set<Key>,pub props_ix:bool}
/// The store: (graph, node id) -> rows. Absent means no node row.
pub type Db=Map<(Graph,Node),Rec>;
/// One validated input row: its labels and property keys (other than `id`).
pub struct Row {pub labels:Set<Lbl>,pub props:Set<Key>}
pub type Input=Map<Node,Row>;
/// How a call ends: completed, or failed while inserting labels (phase 2) or properties (phase 3).
pub enum Stop {Done,FailLabels,FailProps}
pub struct Call {pub graph:Graph,pub noindex:bool,pub stop:Stop}

/// The skip scan sees every node row of the loader's own graph, `%NOINDEX` rows included.
pub open spec fn exists_in(db:Db,g:Graph,n:Node)->bool {db.contains_key((g,n))}
/// Phases 2 and 3 run only for ids the scan did not see (`nodes_to_process = new_nodes` :314).
pub open spec fn is_new(db0:Db,c:Call,n:Node)->bool {!exists_in(db0,c.graph,n)}
pub open spec fn targets(db0:Db,c:Call,inp:Input,k:(Graph,Node))->bool {k.0==c.graph && inp.contains_key(k.1) && is_new(db0,c,k.1)}

pub open spec fn phase_nodes(db0:Db,c:Call,inp:Input)->Db {
 Map::new(db0.dom().union(inp.dom().map(|n:Node| (c.graph,n))),
  |k:(Graph,Node)| if targets(db0,c,inp,k) {Rec{node_ix:!c.noindex,labels:Set::empty(),labels_ix:true,props:Set::empty(),props_ix:true}} else {db0[k]})
}
pub open spec fn phase_labels(db0:Db,db1:Db,c:Call,inp:Input)->Db {
 Map::new(db1.dom(),
  |k:(Graph,Node)| if targets(db0,c,inp,k) {Rec{node_ix:db1[k].node_ix,labels:inp[k.1].labels,labels_ix:!c.noindex,props:db1[k].props,props_ix:db1[k].props_ix}} else {db1[k]})
}
pub open spec fn phase_props(db0:Db,db2:Db,c:Call,inp:Input)->Db {
 Map::new(db2.dom(),
  |k:(Graph,Node)| if targets(db0,c,inp,k) {Rec{node_ix:db2[k].node_ix,labels:db2[k].labels,labels_ix:db2[k].labels_ix,props:inp[k.1].props.insert(id_key()),props_ix:!c.noindex}} else {db2[k]})
}
/// `load_nodes`: phase 1 commits per batch; a failed later phase rolls back only its own batch and raises.
pub open spec fn load(db0:Db,c:Call,inp:Input)->Db {
 let d1=phase_nodes(db0,c,inp);
 match c.stop {
  Stop::FailLabels=>d1,
  Stop::FailProps=>phase_labels(db0,d1,c,inp),
  Stop::Done=>phase_props(db0,phase_labels(db0,d1,c,inp),c,inp),
 }
}
/// `rebuild_all_indices`: every row of the four tables is indexed afterwards.
pub open spec fn rebuild(db:Db)->Db {
 Map::new(db.dom(),
  |k:(Graph,Node)| Rec{node_ix:true,labels:db[k].labels,labels_ix:true,props:db[k].props,props_ix:true})
}
/// The reader (`get_node(n, graph=g)`): an index read of the node, then its indexed labels and properties.
pub open spec fn visible(db:Db,g:Graph,n:Node)->bool {db.contains_key((g,n)) && db[(g,n)].node_ix}
pub open spec fn seen_labels(db:Db,g:Graph,n:Node)->Set<Lbl> {if visible(db,g,n) && db[(g,n)].labels_ix {db[(g,n)].labels} else {Set::empty()}}
pub open spec fn seen_props(db:Db,g:Graph,n:Node)->Set<Key> {if visible(db,g,n) && db[(g,n)].props_ix {db[(g,n)].props} else {Set::empty()}}
/// The owner's outcome for a fresh node: readable with exactly its input labels and properties (plus `id`).
pub open spec fn readable_as_input(db:Db,g:Graph,inp:Input,n:Node)->bool {
 visible(db,g,n) && seen_labels(db,g,n)==inp[n].labels && seen_props(db,g,n)==inp[n].props.insert(id_key())
}
pub open spec fn fresh(db:Db,g:Graph,inp:Input)->bool {forall|n:Node| inp.contains_key(n) ==> !db.contains_key((g,n))}

/// A completed load followed by `rebuild_all_indices` makes every fresh input node readable as given.
pub proof fn theorem_done_then_rebuild_reads_input(db:Db,c:Call,inp:Input,n:Node)
 requires c.stop==Stop::Done,fresh(db,c.graph,inp),inp.contains_key(n)
 ensures readable_as_input(rebuild(load(db,c,inp)),c.graph,inp,n),
{}
/// An indexed load (`use_noindex=False`) is readable as soon as it returns.
pub proof fn theorem_indexed_load_reads_now(db:Db,c:Call,inp:Input,n:Node)
 requires c.stop==Stop::Done,!c.noindex,fresh(db,c.graph,inp),inp.contains_key(n)
 ensures readable_as_input(load(db,c,inp),c.graph,inp,n),
{}
/// A `%NOINDEX` load (the default) is invisible to the reader until the indices are rebuilt, even though it completed.
pub proof fn theorem_noindex_invisible_until_rebuild(db:Db,c:Call,inp:Input,n:Node)
 requires c.noindex,fresh(db,c.graph,inp),inp.contains_key(n)
 ensures load(db,c,inp).contains_key((c.graph,n)),!visible(load(db,c,inp),c.graph,n),
{}
/// Re-running a completed load with the same input writes nothing (B2), whatever its index mode.
pub proof fn theorem_complete_rerun_is_noop(db:Db,c:Call,c2:Call,inp:Input)
 requires c.stop==Stop::Done,c2.stop==Stop::Done,c2.graph==c.graph
 ensures load(load(db,c,inp),c2,inp)=~=load(db,c,inp),
{
 let d=load(db,c,inp);
 assert forall|k:(Graph,Node)| !targets(d,c2,inp,k) by {}
 assert(phase_nodes(d,c2,inp)=~=d);
 assert(phase_labels(d,phase_nodes(d,c2,inp),c2,inp)=~=d);
}
/// bug-plt-011, as built: after a load that failed in phase 2, no completed re-run of the same input (any index mode),
/// even followed by a rebuild, gives a node its labels or properties; the re-run reports nothing written.
pub proof fn theorem_interrupted_load_is_never_completed(db:Db,c:Call,c2:Call,inp:Input,n:Node)
 requires c.stop==Stop::FailLabels,c2.stop==Stop::Done,c2.graph==c.graph,fresh(db,c.graph,inp),inp.contains_key(n)
 ensures
  load(db,c,inp).contains_key((c.graph,n)),
  !is_new(load(db,c,inp),c2,n),
  seen_labels(rebuild(load(load(db,c,inp),c2,inp)),c.graph,n)=~=Set::<Lbl>::empty(),
  seen_props(rebuild(load(load(db,c,inp),c2,inp)),c.graph,n)=~=Set::<Key>::empty(),
{
 let d=load(db,c,inp);
 assert forall|k:(Graph,Node)| !targets(d,c2,inp,k) by {}
 assert(phase_nodes(d,c2,inp)=~=d);
}
/// The same history with a label: the stranded node is readable but its label is missing, so it fails the owner's outcome.
pub proof fn witness_interrupted_rerun_strands(db:Db,c:Call,c2:Call,inp:Input,n:Node,l:Lbl)
 requires c.stop==Stop::FailLabels,c2.stop==Stop::Done,c2.graph==c.graph,fresh(db,c.graph,inp),inp.contains_key(n),
  inp[n].labels.contains(l)
 ensures visible(rebuild(load(load(db,c,inp),c2,inp)),c.graph,n),
  !readable_as_input(rebuild(load(load(db,c,inp),c2,inp)),c.graph,inp,n),
{
 let d=load(db,c,inp);
 assert forall|k:(Graph,Node)| !targets(d,c2,inp,k) by {}
 assert(phase_nodes(d,c2,inp)=~=d);
 let r=rebuild(load(d,c2,inp));
 assert(!seen_labels(r,c.graph,n).contains(l));
}
/// One loader loads one graph: rows of every other graph are untouched.
pub proof fn theorem_other_graphs_untouched(db:Db,c:Call,inp:Input,k:(Graph,Node))
 requires k.0!=c.graph
 ensures load(db,c,inp).contains_key(k)==db.contains_key(k),db.contains_key(k) ==> load(db,c,inp)[k]==db[k],
{}
/// The same id already in another graph does not make the loader skip it (C1).
pub proof fn theorem_same_id_other_graph_is_written(db:Db,c:Call,inp:Input,n:Node,h:Graph)
 requires c.stop==Stop::Done,!c.noindex,h!=c.graph,db.contains_key((h,n)),fresh(db,c.graph,inp),inp.contains_key(n)
 ensures readable_as_input(load(db,c,inp),c.graph,inp,n),load(db,c,inp)[(h,n)]==db[(h,n)],
{}

/// bug-plt-012: a loader whose schema has no tables in the namespace fails at its first statement and writes nothing.
pub open spec fn load_in(db0:Db,c:Call,inp:Input,tables_exist:bool)->Db {if tables_exist {load(db0,c,inp)} else {db0}}
/// bug-plt-012: rebuild_all_indices names the Graph.KG classes; where the namespace's IVG Schema is another, they do not
/// exist and nothing is rebuilt.
pub open spec fn rebuild_as_built(db:Db,ns_is_graph_kg:bool)->Db {if ns_is_graph_kg {rebuild(db)} else {db}}
/// S1: a loader left at the default schema in a namespace with another IVG Schema writes nothing.
pub proof fn theorem_loader_without_schema_writes_nothing(db0:Db,c:Call,inp:Input)
 ensures load_in(db0,c,inp,false)==db0,
{}
/// S3: given the right schema, a %NOINDEX load is written but stays unreadable after the loader's own rebuild.
pub proof fn theorem_rebuild_in_other_schema_leaves_rows_unreadable(db:Db,c:Call,inp:Input,n:Node)
 requires c.noindex,fresh(db,c.graph,inp),inp.contains_key(n)
 ensures load_in(db,c,inp,true).contains_key((c.graph,n)),!visible(rebuild_as_built(load_in(db,c,inp,true),false),c.graph,n),
{}
}
