use vstd::prelude::*;
use vstd::seq_lib::*;
verus! {
pub type Text=Seq<int>;
pub enum Kind { Node, Edge }
pub struct Row { pub graph:Option<nat>, pub id:int, pub attr:Option<nat> }
pub struct Route { pub name:Text, pub kind:Option<Text> }
pub struct Catalog { pub tables:Map<Text,Seq<Row>>, pub refused:Map<Text,Text> }
pub struct Registry { pub rows:Seq<Route>, pub error:Option<Text> }
pub enum Diagnostic { Missing(Text), Provider(Text) }
pub struct Read { pub count:nat, pub error:Option<Diagnostic> }
pub enum Error { Registry(Text), Core(Diagnostic), Count(Text,Diagnostic) }
pub struct Total { pub count:nat, pub errors:Seq<Error> }
pub struct Census { pub nodes:nat,pub edges:nat,pub labels:nat,pub props:nat,pub nv:nat,pub ev:nat,
 pub graph_unknown:bool,pub vector_unknown:bool,pub errors:Seq<Error> }
pub enum GraphView { Unknown, Rows(nat,nat) }
pub enum VectorView { Unknown, Absent, Scan(nat), Indexed(nat) }
pub struct View { pub graph:GraphView,pub vector:VectorView,pub counts:Census }
pub enum Scalar { Count(nat), Error }
pub open spec fn nodes()->Text {seq![110,111,100,101,115]}
pub open spec fn edges()->Text {seq![114,100,102,95,101,100,103,101,115]}
pub open spec fn labels()->Text {seq![114,100,102,95,108,97,98,101,108,115]}
pub open spec fn props()->Text {seq![114,100,102,95,112,114,111,112,115]}
pub open spec fn legacy(k:Kind)->Text {match k {Kind::Node=>seq![107,103,95,78,111,100,101,69,109,98,101,100,100,105,110,103,115],Kind::Edge=>seq![107,103,95,69,100,103,101,69,109,98,101,100,100,105,110,103,115]}}
pub open spec fn lower(t:Text)->Text {t.map_values(|x:int|if 65<=x<=90{x+32}else{x})}
pub open spec fn hex(x:int)->bool {48<=x<=57 || 97<=x<=102}
pub open spec fn route_name(t:Text,k:Kind)->bool {
 let p=match k{Kind::Node=>seq![107,103,95,101,109,98,95],Kind::Edge=>seq![107,103,95,101,101,109,98,95]};
 (t.len()==p.len()+16 || (t.len()==p.len()+17 && t[t.len()-1]==10))
 && t.take(p.len() as int)==p && forall|i:int| p.len()<=i<p.len()+16 ==> hex(t[i])
}
pub open spec fn kind_word(k:Kind)->Text {match k {Kind::Node=>seq![110,111,100,101],Kind::Edge=>seq![101,100,103,101]}}
pub open spec fn registry_kind(r:Route)->Text {if r.kind.is_none() || r.kind.unwrap().len()==0 {kind_word(Kind::Node)}else{r.kind.unwrap()}}
pub open spec fn eligible(r:Route,k:Kind)->bool {registry_kind(r)==kind_word(k) && route_name(r.name,k)}
pub open spec fn select_routes(rs:Seq<Route>,k:Kind,held:Seq<Text>)->Seq<Text> decreases rs.len() {
 if rs.len()==0 {held}else{let r=rs[0];
 let next=if eligible(r,k) && !held.map_values(|x:Text|lower(x)).contains(lower(r.name)) {held.push(r.name)}else{held};
 select_routes(rs.skip(1),k,next)}
}
pub open spec fn tables(r:Registry,k:Kind)->Seq<Text> {
 if r.error.is_some(){seq![legacy(k)]}else{select_routes(r.rows,k,seq![legacy(k)])}
}
pub open spec fn contains_text(s:Text,n:Text)->bool {
 exists|i:int| 0<=i && i+n.len()<=s.len() && #[trigger] s.subrange(i,i+n.len() as int)==n
}
pub open spec fn missing_registry(e:Text)->bool {contains_text(e,seq![83,81,76,67,79,68,69,58,32,60,45,51,48,62])}
pub open spec fn registry_errors(r:Registry)->Seq<Error> {
 if r.error.is_some() && !missing_registry(r.error.unwrap()){seq![Error::Registry(r.error.unwrap())]}else{seq![]}
}
pub open spec fn read(c:Catalog,t:Text)->Read {
 if c.refused.contains_key(t){Read{count:0,error:Some(Diagnostic::Provider(c.refused[t]))}}
 else if !c.tables.contains_key(t){Read{count:0,error:Some(Diagnostic::Missing(t))}}
 else{Read{count:c.tables[t].len(),error:None}}
}
pub open spec fn sum(c:Catalog,ts:Seq<Text>)->Total decreases ts.len() {
 if ts.len()==0 {Total{count:0,errors:seq![]}}else{
 let h=read(c,ts[0]);let tail=sum(c,ts.skip(1));
 Total{count:tail.count,errors:(if h.error.is_some(){seq![Error::Count(ts[0],h.error.unwrap())]}else{seq![]})+tail.errors}}
}
pub open spec fn embeddings(c:Catalog,r:Registry,k:Kind)->Total {
 let s=sum(c,tables(r,k));Total{count:s.count,errors:registry_errors(r)+s.errors}
}
pub open spec fn one_errors(t:Text,r:Read)->Seq<Error> {if r.error.is_some(){seq![Error::Core(r.error.unwrap())]}else{seq![]}}
pub open spec fn dedup(es:Seq<Error>,held:Seq<Error>)->Seq<Error> decreases es.len() {
 if es.len()==0{held}else{dedup(es.skip(1),if held.contains(es[0]){held}else{held.push(es[0])})}
}
pub open spec fn census(c:Catalog,r:Registry)->Census {
 let n=read(c,nodes());let e=read(c,edges());let l=read(c,labels());let p=read(c,props());
 let nv=embeddings(c,r,Kind::Node);let ev=embeddings(c,r,Kind::Edge);
 Census{nodes:n.count,edges:e.count,labels:l.count,props:p.count,nv:nv.count,ev:ev.count,
 graph_unknown:n.error.is_some() || e.error.is_some(),vector_unknown:nv.errors.len()>0,
 errors:dedup(one_errors(nodes(),n)+one_errors(edges(),e)+one_errors(labels(),l)+one_errors(props(),p)+nv.errors+ev.errors,seq![])}
}
pub open spec fn report(s:Census,hnsw:bool)->View {
 View{graph:if s.graph_unknown{GraphView::Unknown}else{GraphView::Rows(s.nodes,s.edges)},
 vector:if s.vector_unknown{VectorView::Unknown}else{if s.nv==0{VectorView::Absent}else{if hnsw{VectorView::Indexed(s.nv)}else{VectorView::Scan(s.nv)}}},counts:s}
}
pub open spec fn gid(g:Option<nat>)->nat {g.unwrap_or(0)}
pub open spec fn matches(r:Row,g:Option<nat>,a:Option<nat>)->bool {
 gid(r.graph)==gid(g) && (a.is_none() || a==Some(0) || r.attr==a)
}
pub open spec fn scan(rs:Seq<Row>,g:Option<nat>,a:Option<nat>)->nat decreases rs.len() {
 if rs.len()==0{0}else{(if matches(rs[0],g,a){1nat}else{0nat})+scan(rs.skip(1),g,a)}
}
pub open spec fn scoped(c:Catalog,t:Text,g:Option<nat>,a:Option<nat>)->Scalar {
 if !c.tables.contains_key(t) || c.refused.contains_key(t){Scalar::Error}else{Scalar::Count(scan(c.tables[t],g,a))}
}
pub open spec fn node_query(c:Catalog,g:Option<nat>,label:Option<nat>)->Scalar {
 scoped(c,if label.is_some() && label!=Some(0){labels()}else{nodes()},g,label)
}
pub open spec fn distribution(rs:Seq<Row>,g:Option<nat>)->Map<Option<nat>,nat> decreases rs.len() {
 if rs.len()==0{Map::empty()}else{let tail=distribution(rs.skip(1),g);
 if gid(rs[0].graph)==gid(g){let k=rs[0].attr;tail.insert(k,if tail.contains_key(k){tail[k]+1}else{1})}else{tail}}
}
pub open spec fn no_dupes(ts:Seq<Text>)->bool {ts.map_values(|x:Text|lower(x)).no_duplicates()}
pub proof fn lemma_choose_unique(rs:Seq<Route>,k:Kind,held:Seq<Text>)
 requires no_dupes(held)
 ensures no_dupes(select_routes(rs,k,held))
 decreases rs.len(),
{
 if rs.len()>0 {let r=rs[0];let low=held.map_values(|x:Text|lower(x));
 if eligible(r,k) && !low.contains(lower(r.name)) {
 assert(held.push(r.name).map_values(|x:Text|lower(x)) =~= low.push(lower(r.name)));
 lemma_choose_unique(rs.skip(1),k,held.push(r.name));
 }else{lemma_choose_unique(rs.skip(1),k,held);}}
}
pub proof fn theorem_route_tables_never_double_count(r:Registry,k:Kind)
 ensures no_dupes(tables(r,k)), tables(r,k).len()>0, tables(r,k)[0]==legacy(k)
{
 if r.error.is_none(){lemma_choose_unique(r.rows,k,seq![legacy(k)]);lemma_choose_prefix(r.rows,k,seq![legacy(k)]);assert(tables(r,k).take(1)[0]==tables(r,k)[0]);}
}
pub proof fn lemma_choose_prefix(rs:Seq<Route>,k:Kind,held:Seq<Text>)
 ensures select_routes(rs,k,held).len()>=held.len(), select_routes(rs,k,held).take(held.len() as int)==held
 decreases rs.len(),
{
 if rs.len()>0{let r=rs[0];let next=if eligible(r,k)&&!held.map_values(|x:Text|lower(x)).contains(lower(r.name)){held.push(r.name)}else{held};
 lemma_choose_prefix(rs.skip(1),k,next);
 assert(select_routes(rs,k,held).take(held.len() as int) =~= held);}
}
pub proof fn lemma_chosen_members(rs:Seq<Route>,k:Kind,held:Seq<Text>)
 ensures forall|t:Text| select_routes(rs,k,held).contains(t) ==> held.contains(t) || exists|i:int|0<=i<rs.len() && rs[i].name==t && eligible(rs[i],k)
 decreases rs.len(),
{
 if rs.len()>0 {let r=rs[0];let next=if eligible(r,k)&&!held.map_values(|x:Text|lower(x)).contains(lower(r.name)){held.push(r.name)}else{held};
 lemma_chosen_members(rs.skip(1),k,next);
 assert forall|t:Text| select_routes(rs,k,held).contains(t) implies held.contains(t) || exists|i:int|0<=i<rs.len() && rs[i].name==t && eligible(rs[i],k) by {
 if !held.contains(t) {if next.contains(t){assert(t==r.name);assert(exists|i:int|0<=i<rs.len() && rs[i].name==t && eligible(rs[i],k)) by {assert(rs[0].name==t);};}
 else{let i=choose|i:int|0<=i<rs.skip(1).len() && rs.skip(1)[i].name==t && eligible(rs.skip(1)[i],k);assert(rs[i+1]==rs.skip(1)[i]);}}}
 }
}
pub proof fn theorem_registry_kind_and_shape_both_required(r:Registry,k:Kind,t:Text)
 requires tables(r,k).contains(t),t!=legacy(k)
 ensures r.error.is_none(),route_name(t,k),exists|i:int|0<=i<r.rows.len() && r.rows[i].name==t && registry_kind(r.rows[i])==kind_word(k)
{if r.error.is_none(){lemma_chosen_members(r.rows,k,seq![legacy(k)]);
 assert(!seq![legacy(k)].contains(t));
 let i=choose|i:int|0<=i<r.rows.len() && r.rows[i].name==t && eligible(r.rows[i],k);
 assert(route_name(r.rows[i].name,k));}}
pub proof fn lemma_choose_covers(rs:Seq<Route>,k:Kind,held:Seq<Text>,t:Text)
 requires held.map_values(|x:Text|lower(x)).contains(lower(t)) || exists|i:int|0<=i<rs.len() && eligible(rs[i],k) && lower(rs[i].name)==lower(t)
 ensures select_routes(rs,k,held).map_values(|x:Text|lower(x)).contains(lower(t))
 decreases rs.len(),
{
 if rs.len()>0 {let r=rs[0];let next=if eligible(r,k)&&!held.map_values(|x:Text|lower(x)).contains(lower(r.name)){held.push(r.name)}else{held};
 assert(held.map_values(|x:Text|lower(x)).contains(lower(t)) ==> next.map_values(|x:Text|lower(x)).contains(lower(t))) by {
  if held.map_values(|x:Text|lower(x)).contains(lower(t)){let j=choose|j:int|0<=j<held.len() && lower(held[j])==lower(t);assert(next[j]==held[j]);assert(next.map_values(|x:Text|lower(x))[j]==lower(t));}
 }
 if !next.map_values(|x:Text|lower(x)).contains(lower(t)) {
 assert(!held.map_values(|x:Text|lower(x)).contains(lower(t)));
 let i=choose|i:int|0<=i<rs.len() && eligible(rs[i],k)&&lower(rs[i].name)==lower(t);
 if i==0 {assert(next.map_values(|x:Text|lower(x)).contains(lower(r.name))) by {
 if held.map_values(|x:Text|lower(x)).contains(lower(r.name)){let j=choose|j:int|0<=j<held.len() && lower(held[j])==lower(r.name);assert(next[j]==held[j]);assert(next.map_values(|x:Text|lower(x))[j]==lower(r.name));}else{assert(next[held.len() as int]==r.name);assert(next.map_values(|x:Text|lower(x))[held.len() as int]==lower(r.name));}
 }}assert(i>0);assert(rs.skip(1)[i-1]==rs[i]);}
 lemma_choose_covers(rs.skip(1),k,next,t);}
}
pub proof fn theorem_registry_eligible_routes_are_not_omitted(r:Registry,k:Kind,i:int)
 requires r.error.is_none(),0<=i<r.rows.len(),eligible(r.rows[i],k)
 ensures tables(r,k).map_values(|x:Text|lower(x)).contains(lower(r.rows[i].name))
{lemma_choose_covers(r.rows,k,seq![legacy(k)],r.rows[i].name);}
pub proof fn theorem_missing_vs_unreadable_registry(c:Catalog,r:Registry,k:Kind)
 requires r.error.is_some()
 ensures tables(r,k)==seq![legacy(k)],
 embeddings(c,r,k).count==read(c,legacy(k)).count,
 missing_registry(r.error.unwrap()) ==> registry_errors(r).len()==0,
 !missing_registry(r.error.unwrap()) ==> registry_errors(r)==seq![Error::Registry(r.error.unwrap())]
{assert(seq![legacy(k)].skip(1) =~= Seq::<Text>::empty());reveal_with_fuel(sum,2);}
pub proof fn theorem_read_is_content_not_cache(c:Catalog,t:Text)
 requires c.tables.contains_key(t),!c.refused.contains_key(t)
 ensures read(c,t).count==c.tables[t].len(),read(c,t).error.is_none()
{}
pub proof fn lemma_sum_append(c:Catalog,a:Seq<Text>,b:Seq<Text>)
 ensures sum(c,a+b).count==sum(c,a).count+sum(c,b).count,
 sum(c,a+b).errors==sum(c,a).errors+sum(c,b).errors
 decreases a.len(),
{if a.len()>0{assert((a+b).skip(1) =~= a.skip(1)+b);lemma_sum_append(c,a.skip(1),b);}}
pub proof fn theorem_failed_table_keeps_other_counts(c:Catalog,a:Seq<Text>,b:Seq<Text>,bad:Text)
 requires !c.tables.contains_key(bad) || c.refused.contains_key(bad)
 ensures sum(c,a+seq![bad]+b).count==sum(c,a).count+sum(c,b).count,
 sum(c,a+seq![bad]+b).errors==sum(c,a).errors+seq![Error::Count(bad,read(c,bad).error.unwrap())]+sum(c,b).errors
{assert(a+seq![bad]+b =~= a+(seq![bad]+b));assert((seq![bad]+b).skip(1) =~= b);lemma_sum_append(c,a,seq![bad]+b);}
pub proof fn lemma_sum_readable(c:Catalog,ts:Seq<Text>)
 requires forall|i:int|0<=i<ts.len() ==> c.tables.contains_key(ts[i]) && !c.refused.contains_key(ts[i])
 ensures sum(c,ts).errors.len()==0
 decreases ts.len(),
{if ts.len()>0{lemma_sum_readable(c,ts.skip(1));}}
pub proof fn theorem_raw_catalog_to_final_report(c:Catalog,r:Registry,hnsw:bool)
 requires c.tables.contains_key(nodes()),c.tables.contains_key(edges()),!c.refused.contains_key(nodes()),!c.refused.contains_key(edges()),
 r.error.is_none(),forall|i:int|0<=i<tables(r,Kind::Node).len() ==> c.tables.contains_key(tables(r,Kind::Node)[i]) && !c.refused.contains_key(tables(r,Kind::Node)[i])
 ensures report(census(c,r),hnsw).graph==GraphView::Rows(c.tables[nodes()].len(),c.tables[edges()].len()),
 !census(c,r).vector_unknown,
 census(c,r).nv==sum(c,tables(r,Kind::Node)).count,
 census(c,r).ev==sum(c,tables(r,Kind::Edge)).count
{lemma_sum_readable(c,tables(r,Kind::Node));}
pub proof fn theorem_failure_is_unknown_not_empty(c:Catalog,r:Registry,hnsw:bool)
 requires !c.tables.contains_key(nodes()) || c.refused.contains_key(nodes()) || !c.tables.contains_key(edges()) || c.refused.contains_key(edges())
 ensures census(c,r).graph_unknown,report(census(c,r),hnsw).graph==GraphView::Unknown
{}
pub proof fn theorem_report_preserves_tables(c:Catalog,r:Registry,hnsw:bool)
 ensures report(census(c,r),hnsw).counts==census(c,r)
{}
pub proof fn theorem_graph_unknown_is_only_core_node_edge_errors(c:Catalog,r:Registry)
 ensures census(c,r).graph_unknown==(read(c,nodes()).error.is_some() || read(c,edges()).error.is_some()),
 census(c,r).vector_unknown==(embeddings(c,r,Kind::Node).errors.len()>0)
{}
pub proof fn theorem_empty_and_partial_vector_report(s:Census)
 ensures s.vector_unknown ==> report(s,false).vector==VectorView::Unknown,
 !s.vector_unknown && s.nv==0 ==> report(s,false).vector==VectorView::Absent,
 !s.vector_unknown && s.nv>0 ==> report(s,false).vector==VectorView::Scan(s.nv),
 !s.vector_unknown && s.nv>0 ==> report(s,true).vector==VectorView::Indexed(s.nv)
{}
pub proof fn lemma_scan_filter(rs:Seq<Row>,g:Option<nat>,a:Option<nat>)
 ensures scan(rs,g,a)==rs.filter(|r:Row|matches(r,g,a)).len()
 decreases rs.len(),
{if rs.len()>0{lemma_scan_filter(rs.skip(1),g,a);
 assert(rs =~= seq![rs[0]]+rs.skip(1));Seq::filter_distributes_over_add(seq![rs[0]],rs.skip(1),|r:Row|matches(r,g,a));reveal_with_fuel(Seq::filter,2);
 }else{reveal(Seq::filter);}}
pub proof fn theorem_scalar_is_raw_scoped_cardinality(c:Catalog,t:Text,g:Option<nat>,a:Option<nat>)
 requires c.tables.contains_key(t),!c.refused.contains_key(t)
 ensures scoped(c,t,g,a)==Scalar::Count(c.tables[t].filter(|r:Row|matches(r,g,a)).len())
{lemma_scan_filter(c.tables[t],g,a);}
pub proof fn theorem_scoped_failure_propagates(c:Catalog,t:Text,g:Option<nat>,a:Option<nat>)
 requires !c.tables.contains_key(t) || c.refused.contains_key(t)
 ensures scoped(c,t,g,a)==Scalar::Error
{}
pub proof fn theorem_default_null_empty_named(r:Row,a:Option<nat>)
 ensures matches(r,None,a)==matches(r,Some(0),a),
 r.graph.is_none() ==> gid(r.graph)==0,
 r.graph==Some(2) ==> !matches(r,None,a)
{}
pub proof fn lemma_empty_filter(rs:Seq<Row>,g:Option<nat>)
 ensures scan(rs,g,None)==scan(rs,g,Some(0))
 decreases rs.len(),
{if rs.len()>0{lemma_empty_filter(rs.skip(1),g);}}
pub proof fn theorem_empty_filter_is_unfiltered(c:Catalog,g:Option<nat>)
 ensures node_query(c,g,None)==node_query(c,g,Some(0)),node_query(c,g,Some(1))==scoped(c,labels(),g,Some(1))
{if c.tables.contains_key(nodes()){lemma_empty_filter(c.tables[nodes()],g);}}
pub proof fn theorem_appending_row_counts_physical_multiplicity(rs:Seq<Row>,r:Row,g:Option<nat>,a:Option<nat>)
 ensures scan(seq![r]+rs,g,a)==scan(rs,g,a)+(if matches(r,g,a){1nat}else{0nat})
{assert((seq![r]+rs).skip(1) =~= rs);}
pub proof fn lemma_distribution(rs:Seq<Row>,g:Option<nat>,k:Option<nat>)
 ensures distribution(rs,g).contains_key(k)==(rs.filter(|r:Row|gid(r.graph)==gid(g)&&r.attr==k).len()>0),
 distribution(rs,g).contains_key(k) ==> distribution(rs,g)[k]==rs.filter(|r:Row|gid(r.graph)==gid(g)&&r.attr==k).len()
 decreases rs.len(),
{if rs.len()>0{lemma_distribution(rs.skip(1),g,k);
 assert(rs =~= seq![rs[0]]+rs.skip(1));Seq::filter_distributes_over_add(seq![rs[0]],rs.skip(1),|r:Row|gid(r.graph)==gid(g)&&r.attr==k);reveal_with_fuel(Seq::filter,2);
 }else{reveal(Seq::filter);}}
pub proof fn theorem_distribution_uses_label_rows(rs:Seq<Row>,g:Option<nat>,k:Option<nat>)
 ensures distribution(rs,g).contains_key(k) ==> distribution(rs,g)[k]==rs.filter(|r:Row|gid(r.graph)==gid(g)&&r.attr==k).len()
{lemma_distribution(rs,g,k);}
pub proof fn lemma_dedup_members(es:Seq<Error>,held:Seq<Error>)
 ensures forall|e:Error|dedup(es,held).contains(e)==(held.contains(e)||es.contains(e))
 decreases es.len(),
{if es.len()>0{let next=if held.contains(es[0]){held}else{held.push(es[0])};lemma_dedup_members(es.skip(1),next);
 assert forall|e:Error| dedup(es,held).contains(e)==(held.contains(e)||es.contains(e)) by {
 if held.contains(es[0]) {assert(next==held);if e==es[0]{assert(held.contains(e));}}
 else {
 if held.contains(e){let j=choose|j:int|0<=j<held.len()&&held[j]==e;assert(next[j]==e);}
 if e==es[0]{assert(next[held.len() as int]==e);}
 if next.contains(e){let j=choose|j:int|0<=j<next.len()&&next[j]==e;if j<held.len(){assert(held[j]==e);}else{assert(e==es[0]);}}
 }
 assert(next.contains(e)==(held.contains(e)||e==es[0]));
 assert(dedup(es.skip(1),next).contains(e)==(next.contains(e)||es.skip(1).contains(e)));
 assert(es.contains(e)==(e==es[0]||es.skip(1).contains(e))) by {
 if es.contains(e){let i=choose|i:int|0<=i<es.len()&&es[i]==e;if i>0{assert(es.skip(1)[i-1]==e);}}
 else if es.skip(1).contains(e){let i=choose|i:int|0<=i<es.skip(1).len()&&es.skip(1)[i]==e;assert(es[i+1]==e);}
 }
 }
 }}
pub proof fn theorem_errors_are_retained_after_dedup(c:Catalog,r:Registry)
 ensures forall|e:Error| #[trigger] census(c,r).errors.contains(e) ==>
 (one_errors(nodes(),read(c,nodes()))+one_errors(edges(),read(c,edges()))+one_errors(labels(),read(c,labels()))+one_errors(props(),read(c,props()))+embeddings(c,r,Kind::Node).errors+embeddings(c,r,Kind::Edge).errors).contains(e)
{lemma_dedup_members(one_errors(nodes(),read(c,nodes()))+one_errors(edges(),read(c,edges()))+one_errors(labels(),read(c,labels()))+one_errors(props(),read(c,props()))+embeddings(c,r,Kind::Node).errors+embeddings(c,r,Kind::Edge).errors,seq![]);}
pub proof fn theorem_same_raw_message_core_failures_share_error(text:Text)
 ensures dedup(seq![Error::Core(Diagnostic::Provider(text)),Error::Core(Diagnostic::Provider(text))],seq![])==seq![Error::Core(Diagnostic::Provider(text))]
{let e=Error::Core(Diagnostic::Provider(text));assert(seq![e,e].skip(1) =~= seq![e]);assert(seq![e].skip(1) =~= Seq::<Error>::empty());assert(Seq::<Error>::empty().push(e) =~= seq![e]);reveal_with_fuel(dedup,3);}
pub proof fn theorem_all_graphs_not_distinct_ids()
 ensures scan(seq![Row{graph:None,id:1,attr:None},Row{graph:Some(2),id:1,attr:None}],None,None)==1,
 seq![Row{graph:None,id:1,attr:None},Row{graph:Some(2),id:1,attr:None}].len()==2
{reveal_with_fuel(scan,3);}

}
