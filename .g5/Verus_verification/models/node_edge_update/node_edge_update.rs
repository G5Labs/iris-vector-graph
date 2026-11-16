// product 3eaa79cf: node and edge updates and deletes (iris_vector_graph/_engine/nodes_edges.py).
//   store_node (properties replace one by one, None removes, labels added, id only when absent, True), delete_node
//   (labels, properties and incident edges of the node in its graph), set_edge_weight (default graph only; False and no
//   write when no edge), delete_edge (one graph unless all_graphs; success even when nothing matched). The SQL statements
//   and the adjacency callbacks that carry these effects are provider steps observed natively.
use vstd::prelude::*;
verus! {
pub type N=int; pub type K=int; pub type V=int; pub type L=int; pub type G=int; pub type P=int;
pub open spec fn ID_KEY()->K {0}
pub open spec fn DEFAULT()->G {0}
pub struct Node {pub props:Map<K,V>,pub labels:Set<L>}
pub struct Db {pub nodes:Map<(G,N),Node>,pub edges:Map<(G,N,P,N),V>}
/// One property update: Some(v) replaces, None removes.
pub open spec fn apply_props(m:Map<K,V>,upd:Map<K,Option<V>>)->Map<K,V> {
 Map::new(m.dom().union(upd.dom().filter(|k:K| upd[k].is_some())),
  |k:K| if upd.contains_key(k) && upd[k].is_some() {upd[k].unwrap()} else {m[k]})
  .remove_keys(upd.dom().filter(|k:K| upd[k].is_none()))
}
pub open spec fn store_node(db:Db,g:G,n:N,upd:Map<K,Option<V>>,labels:Set<L>,idv:V)->(Db,bool) {
 let old=if db.nodes.contains_key((g,n)) {db.nodes[(g,n)]} else {Node{props:Map::empty(),labels:Set::empty()}};
 let p=apply_props(old.props,upd);
 let p2=if p.contains_key(ID_KEY()) {p} else {p.insert(ID_KEY(),idv)};
 (Db{nodes:db.nodes.insert((g,n),Node{props:p2,labels:old.labels+labels}),edges:db.edges},true)
}
pub open spec fn incident(e:(G,N,P,N),g:G,n:N)->bool {e.0==g && (e.1==n || e.3==n)}
pub open spec fn delete_node(db:Db,g:G,n:N)->Db {
 Db{nodes:db.nodes.remove((g,n)),edges:db.edges.remove_keys(db.edges.dom().filter(|e:(G,N,P,N)| incident(e,g,n)))}
}
pub open spec fn set_edge_weight(db:Db,s:N,p:P,o:N,w:V)->(Db,bool) {
 if db.edges.contains_key((DEFAULT(),s,p,o)) {(Db{nodes:db.nodes,edges:db.edges.insert((DEFAULT(),s,p,o),w)},true)} else {(db,false)}
}
pub open spec fn delete_edge(db:Db,g:G,s:N,p:P,o:N)->(Db,bool) {(Db{nodes:db.nodes,edges:db.edges.remove((g,s,p,o))},true)}

/// U1: a given value replaces, None removes, other properties and labels stay, labels are added.
pub proof fn theorem_store_node_updates(db:Db,g:G,n:N,upd:Map<K,Option<V>>,labels:Set<L>,idv:V,k:K,j:K,l:L)
 requires db.nodes.contains_key((g,n)),upd.contains_key(k),upd[k].is_some(),upd.contains_key(j),upd[j].is_none(),j!=ID_KEY(),
  db.nodes[(g,n)].labels.contains(l)
 ensures ({let r=store_node(db,g,n,upd,labels,idv).0.nodes[(g,n)];
  r.props.contains_key(k) && (k==ID_KEY() || r.props[k]==upd[k].unwrap()) && !r.props.contains_key(j) && r.labels.contains(l) && r.labels.subset_of(db.nodes[(g,n)].labels+labels)}),
  store_node(db,g,n,upd,labels,idv).1,
{
 let old=db.nodes[(g,n)];let p=apply_props(old.props,upd);
 assert(upd.dom().filter(|x:K| upd[x].is_some()).contains(k));
 assert(upd.dom().filter(|x:K| upd[x].is_none()).contains(j));
 assert(!upd.dom().filter(|x:K| upd[x].is_none()).contains(k));
 assert(p.contains_key(k) && p[k]==upd[k].unwrap());
 assert(!p.contains_key(j));
}
/// U2: a new ID is created with its id property.
pub proof fn theorem_store_new_gets_id(db:Db,g:G,n:N,idv:V)
 requires !db.nodes.contains_key((g,n))
 ensures store_node(db,g,n,Map::empty(),Set::empty(),idv).0.nodes[(g,n)].props[ID_KEY()]==idv,
{
 let p=apply_props(Map::<K,V>::empty(),Map::<K,Option<V>>::empty());
 assert(!p.contains_key(ID_KEY()));
}
/// D1: deleting a node removes it and its incident edges in its graph; other nodes stay.
pub proof fn theorem_delete_node_removes_incident(db:Db,g:G,n:N,k:N,p:P)
 requires db.edges.contains_key((g,n,p,k)),db.nodes.contains_key((g,k)),k!=n
 ensures !delete_node(db,g,n).nodes.contains_key((g,n)),!delete_node(db,g,n).edges.contains_key((g,n,p,k)),
  delete_node(db,g,n).nodes.contains_key((g,k)),
{assert(db.edges.dom().filter(|e:(G,N,P,N)| incident(e,g,n)).contains((g,n,p,k)));}
/// W1-W3: the weight changes only for a default-graph edge; otherwise False and nothing written.
pub proof fn theorem_set_weight_default_graph_only(db:Db,s:N,p:P,o:N,w:V,h:G)
 ensures db.edges.contains_key((DEFAULT(),s,p,o)) ==> set_edge_weight(db,s,p,o,w).0.edges[(DEFAULT(),s,p,o)]==w && set_edge_weight(db,s,p,o,w).1,
  !db.edges.contains_key((DEFAULT(),s,p,o)) ==> set_edge_weight(db,s,p,o,w).0==db && !set_edge_weight(db,s,p,o,w).1,
  h!=DEFAULT() ==> (db.edges.contains_key((h,s,p,o)) ==> set_edge_weight(db,s,p,o,w).0.edges[(h,s,p,o)]==db.edges[(h,s,p,o)]),
{}
/// E1-E3: delete_edge removes the triple from one graph, reports success, and leaves other graphs.
pub proof fn theorem_delete_edge_one_graph(db:Db,g:G,h:G,s:N,p:P,o:N)
 requires g!=h,db.edges.contains_key((h,s,p,o))
 ensures !delete_edge(db,g,s,p,o).0.edges.contains_key((g,s,p,o)),delete_edge(db,g,s,p,o).1,
  delete_edge(db,g,s,p,o).0.edges[(h,s,p,o)]==db.edges[(h,s,p,o)],
{}
}
