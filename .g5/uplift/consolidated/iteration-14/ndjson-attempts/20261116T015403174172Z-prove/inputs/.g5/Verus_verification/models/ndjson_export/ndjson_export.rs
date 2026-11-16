// product3eaa79cf: raw normalized SQL rows -> hydrated maps -> default NDJSON records.
use vstd::prelude::*;
#[path="../node_read/node_read.rs"] pub mod nr;
#[path="../bulk_children/bulk_children.rs"] pub mod bc;
pub mod qualifier;
pub mod order;
verus! {
pub type Id=int; // ordinary nonempty ASCII identity/order atoms; not Python numeric ID arguments
pub struct Parent{pub graph:int,pub id:Id}
pub struct Label{pub graph:int,pub id:Id,pub label:int}
pub struct Prop{pub graph:int,pub id:Id,pub key:int,pub stored:nr::Stored}
pub struct Record{pub id:Id,pub labels:Seq<int>,pub props:Map<int,nr::Value>}
pub open spec fn graph(g:Option<int>)->int{if g.is_some(){g.unwrap()}else{0}}
pub open spec fn alias(k:int)->int{if k==0{2}else if k==1{3}else{k}}
pub open spec fn value(p:Prop)->nr::Value{nr::read(nr::cy_typed(p.stored))}
pub open spec fn ids(xs:Seq<Id>)->Set<Id> decreases xs.len(){if xs.len()==0{Set::empty()}else{ids(xs.drop_last()).insert(xs.last())}}
pub open spec fn init(xs:Seq<Id>)->Map<Id,Record>{Map::new(ids(xs),|id:Id|Record{id,labels:seq![],props:Map::empty()})}
pub open spec fn label_step(m:Map<Id,Record>,r:Label,g:int)->Map<Id,Record>{if r.graph==g&&m.contains_key(r.id){let old=m[r.id];m.insert(r.id,Record{labels:old.labels.push(r.label),..old})}else{m}}
pub open spec fn label_fold(m:Map<Id,Record>,rs:Seq<Label>,g:int)->Map<Id,Record> decreases rs.len(){if rs.len()==0{m}else{label_step(label_fold(m,rs.drop_last(),g),rs.last(),g)}}
pub open spec fn prop_step(m:Map<Id,Record>,r:Prop,g:int)->Map<Id,Record>{if r.graph==g&&m.contains_key(r.id){let old=m[r.id];m.insert(r.id,Record{props:old.props.insert(alias(r.key),value(r)),..old})}else{m}}
pub open spec fn prop_fold(m:Map<Id,Record>,rs:Seq<Prop>,g:int)->Map<Id,Record> decreases rs.len(){if rs.len()==0{m}else{prop_step(prop_fold(m,rs.drop_last(),g),rs.last(),g)}}
pub open spec fn labels(rs:Seq<Label>,g:int,id:Id)->Seq<int> decreases rs.len(){if rs.len()==0{seq![]}else{let r=rs.last();let out=labels(rs.drop_last(),g,id);if r.graph==g&&r.id==id{out.push(r.label)}else{out}}}
pub open spec fn prop_keys(rs:Seq<Prop>,g:int,id:Id)->Seq<int> decreases rs.len(){if rs.len()==0{seq![]}else{let r=rs.last();let out=prop_keys(rs.drop_last(),g,id);if r.graph==g&&r.id==id{out.push(r.key)}else{out}}}
pub open spec fn aliases(rs:Seq<Prop>,g:int,id:Id)->Set<int> decreases rs.len(){if rs.len()==0{Set::empty()}else{let r=rs.last();let out=aliases(rs.drop_last(),g,id);if r.graph==g&&r.id==id{out.insert(alias(r.key))}else{out}}}
pub open spec fn last_value(rs:Seq<Prop>,g:int,id:Id,k:int)->Option<nr::Value> decreases rs.len(){if rs.len()==0{None}else{let r=rs.last();if r.graph==g&&r.id==id&&alias(r.key)==k{Some(value(r))}else{last_value(rs.drop_last(),g,id,k)}}}
pub open spec fn expected_props(rs:Seq<Prop>,g:int,id:Id)->Map<int,nr::Value>{Map::new(aliases(rs,g,id),|k:int|last_value(rs,g,id,k).unwrap())}
pub open spec fn hydrated(xs:Seq<Id>,ls:Seq<Label>,ps:Seq<Prop>,g:int)->Map<Id,Record>{prop_fold(label_fold(init(xs),ls,g),ps,g)}
pub open spec fn parent_has(ns:Seq<Parent>,g:int,id:Id)->bool{exists|i:int|0<=i<ns.len()&&ns[i].graph==g&&ns[i].id==id}
pub open spec fn included(r:Record,ns:Seq<Parent>,g:int)->bool{r.labels.len()>0||r.props.dom().len()>0||parent_has(ns,g,r.id)}
pub open spec fn return_rows(xs:Seq<Id>,m:Map<Id,Record>,ns:Seq<Parent>,g:int)->Seq<Record>
 recommends ids(xs).subset_of(m.dom()),
 decreases xs.len(),
 {if xs.len()==0{seq![]}else{let out=return_rows(xs.drop_first(),m,ns,g);if included(m[xs[0]],ns,g){seq![m[xs[0]]]+out}else{out}}}
pub open spec fn get_nodes(xs:Seq<Id>,ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,g:Option<int>)->Seq<Record>{return_rows(xs,hydrated(xs,ls,ps,graph(g)),ns,graph(g))}
pub open spec fn get_node(id:Id,ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,g:Option<int>)->Option<Record>{let out=get_nodes(seq![id],ns,ls,ps,g);if out.len()>0{Some(out[0])}else{None}}
pub proof fn lemma_ids_member(xs:Seq<Id>,id:Id) ensures ids(xs).contains(id)<==>xs.contains(id),decreases xs.len(){if xs.len()>0{let p=xs.drop_last();lemma_ids_member(p,id);assert(xs==p.push(xs.last()));vstd::seq_lib::lemma_seq_contains_after_push(p,xs.last(),id);}}
pub proof fn lemma_label_fold(m:Map<Id,Record>,ls:Seq<Label>,g:int,id:Id)
 requires m.contains_key(id),
 ensures label_fold(m,ls,g).dom()==m.dom(),label_fold(m,ls,g)[id].id==m[id].id,label_fold(m,ls,g)[id].props==m[id].props,label_fold(m,ls,g)[id].labels==m[id].labels+labels(ls,g,id),
 decreases ls.len(),
 {if ls.len()>0{let p=ls.drop_last();lemma_label_fold(m,p,g,id);let r=ls.last();if r.graph==g&&r.id==id{assert((m[id].labels+labels(p,g,id)).push(r.label)=~=m[id].labels+labels(p,g,id).push(r.label));}}else{assert(m[id].labels+Seq::empty()=~=m[id].labels);}}
pub proof fn lemma_alias_last_defined(ps:Seq<Prop>,g:int,id:Id,k:int)
 ensures aliases(ps,g,id).contains(k)<==>last_value(ps,g,id,k).is_some(),
 decreases ps.len(),
 {if ps.len()>0{lemma_alias_last_defined(ps.drop_last(),g,id,k);}}
pub proof fn lemma_expected_props_step(ps:Seq<Prop>,r:Prop,g:int,id:Id)
 ensures expected_props(ps.push(r),g,id)==if r.graph==g&&r.id==id{expected_props(ps,g,id).insert(alias(r.key),value(r))}else{expected_props(ps,g,id)},
 {assert(ps.push(r).drop_last()=~=ps);assert(ps.push(r).last()==r);assert(expected_props(ps.push(r),g,id)=~=if r.graph==g&&r.id==id{expected_props(ps,g,id).insert(alias(r.key),value(r))}else{expected_props(ps,g,id)});}
pub proof fn lemma_prop_fold(m:Map<Id,Record>,ps:Seq<Prop>,g:int,id:Id)
 requires m.contains_key(id),m[id].props==Map::<int,nr::Value>::empty(),
 ensures prop_fold(m,ps,g).dom()==m.dom(),prop_fold(m,ps,g)[id].id==m[id].id,prop_fold(m,ps,g)[id].labels==m[id].labels,prop_fold(m,ps,g)[id].props==expected_props(ps,g,id),
 decreases ps.len(),
 {if ps.len()>0{let p=ps.drop_last();let r=ps.last();lemma_prop_fold(m,p,g,id);lemma_expected_props_step(p,r,g,id);assert(ps==p.push(r));}else{assert(expected_props(ps,g,id)=~=Map::empty());}}
pub proof fn theorem_raw_hydration_fields(xs:Seq<Id>,ls:Seq<Label>,ps:Seq<Prop>,g:int,id:Id)
 requires ids(xs).contains(id),
 ensures hydrated(xs,ls,ps,g).dom()==ids(xs),hydrated(xs,ls,ps,g)[id].id==id,hydrated(xs,ls,ps,g)[id].labels==labels(ls,g,id),hydrated(xs,ls,ps,g)[id].props==expected_props(ps,g,id),
 {lemma_label_fold(init(xs),ls,g,id);lemma_prop_fold(label_fold(init(xs),ls,g),ps,g,id);assert(Seq::<int>::empty()+labels(ls,g,id)=~=labels(ls,g,id));}
pub proof fn theorem_hydration_map_domain(xs:Seq<Id>,ls:Seq<Label>,ps:Seq<Prop>,g:int)
 ensures hydrated(xs,ls,ps,g).dom()==ids(xs),
 {if xs.len()>0{theorem_raw_hydration_fields(xs,ls,ps,g,xs.last());}else{assert(init(xs)=~=Map::empty());lemma_empty_map_label_fold(ls,g);lemma_empty_map_prop_fold(ps,g);}}
pub proof fn lemma_empty_map_label_fold(ls:Seq<Label>,g:int) ensures label_fold(Map::empty(),ls,g)==Map::<Id,Record>::empty(),decreases ls.len(){if ls.len()>0{lemma_empty_map_label_fold(ls.drop_last(),g);}}
pub proof fn lemma_empty_map_prop_fold(ps:Seq<Prop>,g:int) ensures prop_fold(Map::empty(),ps,g)==Map::<Id,Record>::empty(),decreases ps.len(){if ps.len()>0{lemma_empty_map_prop_fold(ps.drop_last(),g);}}
pub proof fn theorem_alias_value_provenance(xs:Seq<Id>,ls:Seq<Label>,ps:Seq<Prop>,g:int,id:Id,k:int)
 requires ids(xs).contains(id),
 ensures hydrated(xs,ls,ps,g)[id].props.contains_key(k)<==>aliases(ps,g,id).contains(k),aliases(ps,g,id).contains(k)==>hydrated(xs,ls,ps,g)[id].props[k]==last_value(ps,g,id,k).unwrap(),
 {theorem_raw_hydration_fields(xs,ls,ps,g,id);}
pub proof fn theorem_structural_alias_keys_protected(k:int)
 requires k>=0,
 ensures alias(k)!=0,alias(k)!=1,alias(k)==bc::alias(k),alias(k)==nr::alias(k),{}
pub proof fn theorem_raw_integer_and_double_scalar(p:Prop,n:int)
 ensures p.stored==(nr::Stored::Number{payload:n,double:false})==>value(p)==nr::Value::Integer(n),p.stored==(nr::Stored::Number{payload:n,double:true})==>value(p)==nr::Value::Double(n),{}
pub proof fn theorem_duplicate_request_initializes_once(xs:Seq<Id>,id:Id)
 ensures init(xs.push(id).push(id))==init(xs.push(id)),
 {lemma_ids_push(xs,id);lemma_ids_push(xs.push(id),id);assert(ids(xs.push(id)).insert(id)=~=ids(xs.push(id)));assert(init(xs.push(id).push(id))=~=init(xs.push(id)));}
pub proof fn theorem_return_duplicate_after_single_hydration(id:Id,ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,g:int)
 requires parent_has(ns,g,id),
 ensures get_nodes(seq![id,id],ns,ls,ps,Some(g)).len()==2,get_nodes(seq![id,id],ns,ls,ps,Some(g))[0]==get_nodes(seq![id,id],ns,ls,ps,Some(g))[1],
 {let xs=seq![id,id];lemma_ids_member(xs,id);theorem_raw_hydration_fields(xs,ls,ps,g,id);reveal_with_fuel(return_rows,3);}
pub proof fn theorem_empty_requests(ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,g:Option<int>) ensures get_nodes(seq![],ns,ls,ps,g)==Seq::<Record>::empty(),{}
pub proof fn lemma_ids_push(xs:Seq<Id>,id:Id) ensures ids(xs.push(id))==ids(xs).insert(id){assert(xs.push(id).drop_last()=~=xs);}

// Explicit refinement to the retained bulk_children integer reader: neither its map nor key order is input.
pub open spec fn raw_int(p:Prop)->int{match p.stored{nr::Stored::Number{payload,double:_}=>payload,_=>0}}
pub open spec fn int_props(ps:Seq<Prop>)->Map<bc::Child,int> decreases ps.len(){if ps.len()==0{Map::empty()}else{let r=ps.last();int_props(ps.drop_last()).insert(((r.graph,r.id),r.key),raw_int(r))}}
pub open spec fn normal_props(ps:Seq<Prop>)->bool{forall|i:int,j:int|0<=i<j<ps.len()==>(#[trigger] ps[i].graph,ps[i].id,ps[i].key)!=(#[trigger] ps[j].graph,ps[j].id,ps[j].key)}
pub open spec fn integer_props(ps:Seq<Prop>,g:int,id:Id)->bool{forall|i:int|0<=i<ps.len()&&ps[i].graph==g&&ps[i].id==id==>#[trigger] ps[i].stored==nr::Stored::Number{payload:raw_int(ps[i]),double:false}}
pub open spec fn alias_unique(ps:Seq<Prop>,g:int,id:Id,k:int)->bool{forall|i:int|0<=i<ps.len()&&ps[i].graph==g&&ps[i].id==id&&alias(ps[i].key)==alias(k)==>#[trigger] ps[i].key==k}
pub proof fn lemma_raw_prop_keys(ps:Seq<Prop>,g:int,id:Id,k:int)
 ensures prop_keys(ps,g,id).contains(k)<==>int_props(ps).contains_key(((g,id),k)),
 decreases ps.len(),
 {if ps.len()>0{let p=ps.drop_last();let r=ps.last();lemma_raw_prop_keys(p,g,id,k);if r.graph==g&&r.id==id{vstd::seq_lib::lemma_seq_contains_after_push(prop_keys(p,g,id),r.key,k);}assert(ps==p.push(r));}}
pub proof fn lemma_prop_key_source(ps:Seq<Prop>,g:int,id:Id,k:int)
 ensures prop_keys(ps,g,id).contains(k)<==>(exists|i:int|0<=i<ps.len()&&ps[i].graph==g&&ps[i].id==id&&ps[i].key==k),
 decreases ps.len(),
 {if ps.len()>0{let p=ps.drop_last();let r=ps.last();lemma_prop_key_source(p,g,id,k);
 if prop_keys(p,g,id).contains(k){let i=choose|i:int|0<=i<p.len()&&p[i].graph==g&&p[i].id==id&&p[i].key==k;assert(p[i]==ps[i]);}
 if exists|i:int|0<=i<ps.len()&&ps[i].graph==g&&ps[i].id==id&&ps[i].key==k{let i=choose|i:int|0<=i<ps.len()&&ps[i].graph==g&&ps[i].id==id&&ps[i].key==k;if i<p.len(){assert(p[i]==ps[i]);}}
 if r.graph==g&&r.id==id{vstd::seq_lib::lemma_seq_contains_after_push(prop_keys(p,g,id),r.key,k);}}}
pub proof fn theorem_raw_key_order_satisfies_retained_reader(ps:Seq<Prop>,g:int,id:Id)
 requires normal_props(ps),
 ensures bc::reader_order(int_props(ps),(g,id),prop_keys(ps,g,id)),
 decreases ps.len(),
 {if ps.len()>0{let p=ps.drop_last();let r=ps.last();assert(normal_props(p));theorem_raw_key_order_satisfies_retained_reader(p,g,id);if r.graph==g&&r.id==id{
 lemma_prop_key_source(p,g,id,r.key);assert(!prop_keys(p,g,id).contains(r.key));assert(prop_keys(ps,g,id).no_duplicates());}}
 assert forall|k:int|prop_keys(ps,g,id).contains(k)<==>int_props(ps).contains_key(((g,id),k)) by {lemma_raw_prop_keys(ps,g,id,k);}}
pub proof fn lemma_integer_last_alias(ps:Seq<Prop>,g:int,id:Id,k:int)
 requires integer_props(ps,g,id),alias_unique(ps,g,id,k),
 ensures last_value(ps,g,id,alias(k))==if int_props(ps).contains_key(((g,id),k)){Some(nr::Value::Integer(int_props(ps)[((g,id),k)]))}else{None},
 decreases ps.len(),
 {if ps.len()>0{let p=ps.drop_last();let r=ps.last();assert(integer_props(p,g,id));assert(alias_unique(p,g,id,k));lemma_integer_last_alias(p,g,id,k);if r.graph==g&&r.id==id{assert(r.stored==nr::Stored::Number{payload:raw_int(r),double:false});if alias(r.key)==alias(k){assert(r.key==k);}}}}
pub proof fn theorem_raw_integer_property_refines_retained_reader(xs:Seq<Id>,ls:Seq<Label>,ps:Seq<Prop>,g:int,id:Id,k:int)
 requires ids(xs).contains(id),normal_props(ps),integer_props(ps,g,id),alias_unique(ps,g,id,k),prop_keys(ps,g,id).contains(k),
 ensures bc::reader_order(int_props(ps),(g,id),prop_keys(ps,g,id)),hydrated(xs,ls,ps,g)[id].props.contains_key(alias(k)),hydrated(xs,ls,ps,g)[id].props[alias(k)]==nr::Value::Integer(bc::read_props(int_props(ps),(g,id),prop_keys(ps,g,id))[bc::alias(k)]),
 {theorem_raw_key_order_satisfies_retained_reader(ps,g,id);lemma_raw_prop_keys(ps,g,id,k);lemma_integer_last_alias(ps,g,id,k);theorem_alias_value_provenance(xs,ls,ps,g,id,alias(k));lemma_alias_last_defined(ps,g,id,alias(k));
 assert forall|j:int|prop_keys(ps,g,id).contains(j)&&int_props(ps).contains_key(((g,id),j))&&bc::alias(j)==bc::alias(k) implies j==k by{
  lemma_prop_key_source(ps,g,id,j);let i=choose|i:int|0<=i<ps.len()&&ps[i].graph==g&&ps[i].id==id&&ps[i].key==j;assert(alias(ps[i].key)==alias(k));}
 bc::lemma_read_complete_key(int_props(ps),(g,id),prop_keys(ps,g,id),k);
 }

// Raw default parent census, independently derived from arbitrary get_nodes child inclusion.
pub open spec fn selected_ids(ns:Seq<Parent>)->Seq<Id> decreases ns.len(){if ns.len()==0{seq![]}else{let p=selected_ids(ns.drop_last());let r=ns.last();if r.graph==0{p.push(r.id)}else{p}}}
pub open spec fn census(ns:Seq<Parent>)->Seq<Id>{order::sort(selected_ids(ns),|id:Id|id)}
pub proof fn lemma_selected_parent_source(ns:Seq<Parent>,id:Id)
 ensures selected_ids(ns).contains(id)<==>parent_has(ns,0,id),decreases ns.len(),
 {if ns.len()>0{let p=ns.drop_last();let r=ns.last();lemma_selected_parent_source(p,id);
 if parent_has(p,0,id){let i=choose|i:int|0<=i<p.len()&&p[i].graph==0&&p[i].id==id;assert(p[i]==ns[i]);}
 if parent_has(ns,0,id){let i=choose|i:int|0<=i<ns.len()&&ns[i].graph==0&&ns[i].id==id;if i<p.len(){assert(p[i]==ns[i]);}}
 if r.graph==0{vstd::seq_lib::lemma_seq_contains_after_push(selected_ids(p),r.id,id);}}}
pub proof fn theorem_default_census_derived(ns:Seq<Parent>,id:Id)
 ensures census(ns).len()==selected_ids(ns).len(),order::ordered(census(ns),|id:Id|id),census(ns).contains(id)<==>parent_has(ns,0,id),order::count(census(ns),id)==order::count(selected_ids(ns),id),
 {order::theorem_sort_ordered_and_length(selected_ids(ns),|id:Id|id);order::theorem_sort_preserves_each_row(selected_ids(ns),id,|id:Id|id);order::lemma_count_positive_iff_member(census(ns),id);order::lemma_count_positive_iff_member(selected_ids(ns),id);lemma_selected_parent_source(ns,id);}
pub enum Field{Structural(Id),Labels(Seq<int>),Scalar(nr::Value)}
pub open spec fn flatten(r:Record)->Map<int,Field>{Map::new(r.props.dom().union(set![0int,1int]),|k:int|if k==0{Field::Structural(r.id)}else if k==1{Field::Labels(r.labels)}else{Field::Scalar(r.props[k])})}
pub open spec fn field_value(f:Field)->nr::Value{match f{Field::Scalar(v)=>v,_=>nr::Value::Text(seq![])}}
pub open spec fn field_labels(f:Field)->Seq<int>{match f{Field::Labels(ls)=>ls,_=>seq![]}}
pub open spec fn projected_props(flat:Map<int,Field>)->Map<int,nr::Value>{Map::new(flat.dom().filter(|k:int|k!=0&&k!=1),|k:int|field_value(flat[k]))}
pub open spec fn ordinary_keys(ps:Seq<Prop>)->bool{forall|i:int|0<=i<ps.len()==>#[trigger] ps[i].key>=0}
pub proof fn lemma_raw_aliases_not_structural(ps:Seq<Prop>,g:int,id:Id)
 requires ordinary_keys(ps),ensures !aliases(ps,g,id).contains(0),!aliases(ps,g,id).contains(1),decreases ps.len(),
 {if ps.len()>0{lemma_raw_aliases_not_structural(ps.drop_last(),g,id);theorem_structural_alias_keys_protected(ps.last().key);}}
pub proof fn theorem_full_flatten_projection_preserves_hydrated_props(r:Record)
 requires !r.props.contains_key(0),!r.props.contains_key(1),
 ensures flatten(r)[0]==Field::Structural(r.id),flatten(r)[1]==Field::Labels(r.labels),projected_props(flatten(r))==r.props,
 {assert(projected_props(flatten(r))=~=r.props);}
pub proof fn theorem_raw_get_node_present_and_fields(id:Id,ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,g:int)
 requires parent_has(ns,g,id),
 ensures get_node(id,ns,ls,ps,Some(g)).is_some(),get_node(id,ns,ls,ps,Some(g)).unwrap().id==id,get_node(id,ns,ls,ps,Some(g)).unwrap().labels==labels(ls,g,id),get_node(id,ns,ls,ps,Some(g)).unwrap().props==expected_props(ps,g,id),
 {let xs=seq![id];lemma_ids_member(xs,id);theorem_raw_hydration_fields(xs,ls,ps,g,id);reveal_with_fuel(return_rows,2);}
pub enum Event{Node{id:Id,labels:Seq<int>,props:Map<int,nr::Value>},Edge{source:Id,predicate:int,target:Id,qual:Option<nat>},Outside}
pub open spec fn node_event(id:Id,r:Record)->Event{let f=flatten(r);Event::Node{id,labels:field_labels(f[1]),props:projected_props(f)}}
pub proof fn theorem_raw_node_event_content(id:Id,ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>)
 requires parent_has(ns,0,id),ordinary_keys(ps),
 ensures node_event(id,get_node(id,ns,ls,ps,Some(0)).unwrap())==(Event::Node{id,labels:labels(ls,0,id),props:expected_props(ps,0,id)}),
 {theorem_raw_get_node_present_and_fields(id,ns,ls,ps,0);lemma_raw_aliases_not_structural(ps,0,id);theorem_full_flatten_projection_preserves_hydrated_props(get_node(id,ns,ls,ps,Some(0)).unwrap());}
pub struct EdgeRow{pub graph:int,pub serial:int,pub source:Id,pub predicate:int,pub target:Id,pub raw:Option<Seq<char>>}
pub open spec fn selected_edge(e:EdgeRow)->bool{e.graph==0&&!qualifier::marked(e.raw)}
pub open spec fn edge_rows(es:Seq<EdgeRow>)->Seq<EdgeRow> decreases es.len(){if es.len()==0{seq![]}else{let p=edge_rows(es.drop_last());if selected_edge(es.last()){p.push(es.last())}else{p}}}
pub open spec fn edge_census(es:Seq<EdgeRow>)->Seq<EdgeRow>{order::sort(edge_rows(es),|e:EdgeRow|e.serial)}
pub open spec fn admitted_edges(es:Seq<EdgeRow>)->bool{forall|i:int|0<=i<es.len()&&selected_edge(es[i])==>#[trigger] qualifier::decode(es[i].raw).is_some()}
pub open spec fn edge_event(e:EdgeRow)->Event{match qualifier::decode(e.raw){Some(qualifier::Qual::Omitted)=>Event::Edge{source:e.source,predicate:e.predicate,target:e.target,qual:None},Some(qualifier::Qual::Field(n))=>Event::Edge{source:e.source,predicate:e.predicate,target:e.target,qual:Some(n)},None=>Event::Outside}}
pub proof fn theorem_edge_qualifier_zero_not_omitted(g:int,serial:int,source:Id,predicate:int,target:Id)
 ensures edge_event(EdgeRow{graph:g,serial,source,predicate,target,raw:Some(seq!['{','"','q','"',':','0','}'])})==(Event::Edge{source,predicate,target,qual:Some(0)}),
 {qualifier::theorem_zero_is_nonempty_object();}
pub proof fn lemma_selected_edge_source(es:Seq<EdgeRow>,e:EdgeRow)
 ensures edge_rows(es).contains(e)<==>(es.contains(e)&&selected_edge(e)),decreases es.len(),
 {if es.len()>0{let p=es.drop_last();let r=es.last();lemma_selected_edge_source(p,e);assert(es==p.push(r));vstd::seq_lib::lemma_seq_contains_after_push(p,r,e);if selected_edge(r){vstd::seq_lib::lemma_seq_contains_after_push(edge_rows(p),r,e);}}}
pub proof fn theorem_edge_census_derived(es:Seq<EdgeRow>,e:EdgeRow)
 ensures edge_census(es).len()==edge_rows(es).len(),order::ordered(edge_census(es),|e:EdgeRow|e.serial),edge_census(es).contains(e)<==>(es.contains(e)&&selected_edge(e)),order::count(edge_census(es),e)==order::count(edge_rows(es),e),
 {order::theorem_sort_ordered_and_length(edge_rows(es),|e:EdgeRow|e.serial);order::theorem_sort_preserves_each_row(edge_rows(es),e,|e:EdgeRow|e.serial);order::lemma_count_positive_iff_member(edge_census(es),e);order::lemma_count_positive_iff_member(edge_rows(es),e);lemma_selected_edge_source(es,e);}

// A line denotes one successfully completed JSON-object+newline write in the admitted codec law.
// The bytes/third-party JSON implementation are providers, not supplied parsed-result inputs.
pub struct File{pub lines:Seq<Event>,pub nodes:nat,pub edges:nat}
pub open spec fn start()->File{File{lines:seq![],nodes:0,edges:0}}
pub open spec fn is_node(e:Event)->bool{match e{Event::Node{..}=>true,_=>false}}
pub open spec fn is_edge(e:Event)->bool{match e{Event::Edge{..}=>true,_=>false}}
pub open spec fn ncount(es:Seq<Event>)->nat decreases es.len(){if es.len()==0{0}else{ncount(es.drop_last())+if is_node(es.last()){1nat}else{0nat}}}
pub open spec fn ecount(es:Seq<Event>)->nat decreases es.len(){if es.len()==0{0}else{ecount(es.drop_last())+if is_edge(es.last()){1nat}else{0nat}}}
pub open spec fn append_node(f:File,e:Event)->File{File{lines:f.lines.push(e),nodes:f.nodes+1,..f}}
pub open spec fn append_edge(f:File,e:Event)->File{File{lines:f.lines.push(e),edges:f.edges+1,..f}}
pub open spec fn node_events(ids:Seq<Id>,ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>)->Seq<Event> decreases ids.len(){
 if ids.len()==0{seq![]}else{let r=get_node(ids[0],ns,ls,ps,Some(0));let tail=node_events(ids.drop_first(),ns,ls,ps);if r.is_some(){seq![node_event(ids[0],r.unwrap())]+tail}else{tail}}}
pub open spec fn node_pass(f:File,ids:Seq<Id>,ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>)->File decreases ids.len(){
 if ids.len()==0{f}else{let r=get_node(ids[0],ns,ls,ps,Some(0));let next=if r.is_some(){append_node(f,node_event(ids[0],r.unwrap()))}else{f};node_pass(next,ids.drop_first(),ns,ls,ps)}}
pub open spec fn edge_events(es:Seq<EdgeRow>)->Seq<Event>{es.map(|i:int,e:EdgeRow|edge_event(e))}
pub open spec fn edge_pass(f:File,es:Seq<EdgeRow>)->File decreases es.len(){if es.len()==0{f}else{edge_pass(append_edge(f,edge_event(es[0])),es.drop_first())}}
pub open spec fn export(ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,es:Seq<EdgeRow>)->File{edge_pass(node_pass(start(),census(ns),ns,ls,ps),edge_census(es))}
pub proof fn lemma_append_relation<T>(s:Seq<T>,x:T,t:Seq<T>) ensures s.push(x)+t==s+(seq![x]+t),{assert(s.push(x)+t=~=s+(seq![x]+t));}
pub proof fn theorem_node_pass_actual_append(f:File,ids:Seq<Id>,ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>)
 ensures node_pass(f,ids,ns,ls,ps).lines==f.lines+node_events(ids,ns,ls,ps),node_pass(f,ids,ns,ls,ps).nodes==f.nodes+node_events(ids,ns,ls,ps).len(),node_pass(f,ids,ns,ls,ps).edges==f.edges,
 decreases ids.len(),
 {if ids.len()>0{let r=get_node(ids[0],ns,ls,ps,Some(0));let next=if r.is_some(){append_node(f,node_event(ids[0],r.unwrap()))}else{f};theorem_node_pass_actual_append(next,ids.drop_first(),ns,ls,ps);if r.is_some(){lemma_append_relation(f.lines,node_event(ids[0],r.unwrap()),node_events(ids.drop_first(),ns,ls,ps));}}else{assert(f.lines+Seq::empty()=~=f.lines);}}
pub proof fn theorem_edge_pass_actual_append(f:File,es:Seq<EdgeRow>)
 ensures edge_pass(f,es).lines==f.lines+edge_events(es),edge_pass(f,es).nodes==f.nodes,edge_pass(f,es).edges==f.edges+es.len(),
 decreases es.len(),
 {if es.len()>0{let next=append_edge(f,edge_event(es[0]));theorem_edge_pass_actual_append(next,es.drop_first());assert(edge_events(es)=~=seq![edge_event(es[0])]+edge_events(es.drop_first()));lemma_append_relation(f.lines,edge_event(es[0]),edge_events(es.drop_first()));}else{assert(edge_events(es)=~=Seq::empty());assert(f.lines+Seq::empty()=~=f.lines);}}
pub proof fn lemma_node_event_sequence(ids:Seq<Id>,ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>)
 requires ordinary_keys(ps),forall|i:int|0<=i<ids.len()==>parent_has(ns,0,#[trigger] ids[i]),
 ensures node_events(ids,ns,ls,ps).len()==ids.len(),forall|i:int|0<=i<ids.len()==>node_events(ids,ns,ls,ps)[i]==(Event::Node{id:ids[i],labels:labels(ls,0,ids[i]),props:expected_props(ps,0,ids[i])}),
 decreases ids.len(),
 {if ids.len()>0{theorem_raw_get_node_present_and_fields(ids[0],ns,ls,ps,0);theorem_raw_node_event_content(ids[0],ns,ls,ps);
 assert forall|i:int|0<=i<ids.drop_first().len() implies parent_has(ns,0,#[trigger] ids.drop_first()[i]) by {assert(ids.drop_first()[i]==ids[i+1]);}
 lemma_node_event_sequence(ids.drop_first(),ns,ls,ps);
 assert forall|i:int|0<=i<ids.len() implies node_events(ids,ns,ls,ps)[i]==(Event::Node{id:ids[i],labels:labels(ls,0,ids[i]),props:expected_props(ps,0,ids[i])}) by {if i>0{assert(ids.drop_first()[i-1]==ids[i]);}}}}
pub proof fn theorem_full_node_events_from_raw(ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>)
 requires ordinary_keys(ps),
 ensures node_events(census(ns),ns,ls,ps).len()==selected_ids(ns).len(),forall|i:int|0<=i<census(ns).len()==>node_events(census(ns),ns,ls,ps)[i]==(Event::Node{id:census(ns)[i],labels:labels(ls,0,census(ns)[i]),props:expected_props(ps,0,census(ns)[i])}),
 {assert forall|i:int|0<=i<census(ns).len() implies parent_has(ns,0,#[trigger] census(ns)[i]) by {theorem_default_census_derived(ns,census(ns)[i]);assert(census(ns).contains(census(ns)[i]));}
 lemma_node_event_sequence(census(ns),ns,ls,ps);order::theorem_sort_ordered_and_length(selected_ids(ns),|id:Id|id);}
pub proof fn theorem_selected_edge_events_are_structural(es:Seq<EdgeRow>)
 requires admitted_edges(es),
 ensures forall|i:int|0<=i<edge_census(es).len()==>is_edge(#[trigger] edge_events(edge_census(es))[i]),
 {assert forall|i:int|0<=i<edge_census(es).len() implies is_edge(#[trigger] edge_events(edge_census(es))[i]) by{
 let e=edge_census(es)[i];theorem_edge_census_derived(es,e);assert(edge_census(es).contains(e));let j=choose|j:int|0<=j<es.len()&&es[j]==e;assert(qualifier::decode(es[j].raw).is_some());}}
pub proof fn lemma_kind_counts(es:Seq<Event>)
 requires forall|i:int|0<=i<es.len()==>is_node(#[trigger] es[i]),
 ensures ncount(es)==es.len(),ecount(es)==0,decreases es.len(),
 {if es.len()>0{assert forall|i:int|0<=i<es.drop_last().len() implies is_node(#[trigger] es.drop_last()[i]) by{assert(es.drop_last()[i]==es[i]);}lemma_kind_counts(es.drop_last());}}
pub proof fn lemma_edge_kind_counts(es:Seq<Event>)
 requires forall|i:int|0<=i<es.len()==>is_edge(#[trigger] es[i]),
 ensures ecount(es)==es.len(),ncount(es)==0,decreases es.len(),
 {if es.len()>0{assert forall|i:int|0<=i<es.drop_last().len() implies is_edge(#[trigger] es.drop_last()[i]) by{assert(es.drop_last()[i]==es[i]);}lemma_edge_kind_counts(es.drop_last());}}
pub proof fn lemma_kind_counts_concat(a:Seq<Event>,b:Seq<Event>)
 ensures ncount(a+b)==ncount(a)+ncount(b),ecount(a+b)==ecount(a)+ecount(b),decreases b.len(),
 {if b.len()>0{lemma_kind_counts_concat(a,b.drop_last());assert((a+b).drop_last()=~=a+b.drop_last());assert((a+b).last()==b.last());}else{assert(a+b=~=a);}}
pub proof fn theorem_complete_export_line_sequence_and_counts(ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,es:Seq<EdgeRow>)
 requires ordinary_keys(ps),admitted_edges(es),
 ensures export(ns,ls,ps,es).lines==node_events(census(ns),ns,ls,ps)+edge_events(edge_census(es)),export(ns,ls,ps,es).nodes==selected_ids(ns).len(),export(ns,ls,ps,es).edges==edge_rows(es).len(),export(ns,ls,ps,es).lines.len()==export(ns,ls,ps,es).nodes+export(ns,ls,ps,es).edges,ncount(export(ns,ls,ps,es).lines)==export(ns,ls,ps,es).nodes,ecount(export(ns,ls,ps,es).lines)==export(ns,ls,ps,es).edges,
 {theorem_node_pass_actual_append(start(),census(ns),ns,ls,ps);let nf=node_pass(start(),census(ns),ns,ls,ps);theorem_edge_pass_actual_append(nf,edge_census(es));theorem_full_node_events_from_raw(ns,ls,ps);theorem_selected_edge_events_are_structural(es);order::theorem_sort_ordered_and_length(selected_ids(ns),|id:Id|id);
 let ne=node_events(census(ns),ns,ls,ps);let ee=edge_events(edge_census(es));assert(Seq::<Event>::empty()+ne=~=ne);
 assert forall|i:int|0<=i<ne.len() implies is_node(#[trigger] ne[i]) by{assert(i<census(ns).len());}
 lemma_kind_counts(ne);lemma_edge_kind_counts(ee);lemma_kind_counts_concat(ne,ee);order::theorem_sort_ordered_and_length(edge_rows(es),|e:EdgeRow|e.serial);
 }
pub proof fn theorem_export_nodes_before_edges(ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,es:Seq<EdgeRow>,i:int)
 requires ordinary_keys(ps),admitted_edges(es),0<=i<export(ns,ls,ps,es).lines.len(),
 ensures i<export(ns,ls,ps,es).nodes==>is_node(export(ns,ls,ps,es).lines[i]),i>=export(ns,ls,ps,es).nodes==>is_edge(export(ns,ls,ps,es).lines[i]),
 {theorem_complete_export_line_sequence_and_counts(ns,ls,ps,es);theorem_full_node_events_from_raw(ns,ls,ps);theorem_selected_edge_events_are_structural(es);order::theorem_sort_ordered_and_length(selected_ids(ns),|id:Id|id);let ne=node_events(census(ns),ns,ls,ps);let ee=edge_events(edge_census(es));if i<ne.len(){assert(export(ns,ls,ps,es).lines[i]==ne[i]);}else{assert(export(ns,ls,ps,es).lines[i]==ee[i-ne.len()]);}}

// Generated-record import reader. Ordinary IDs/endpoints denote nonempty strings; writers are callbacks.
// No create/matched/rowcount flag is an input, and no persisted inverse is asserted.
pub enum Action{CreateNode{id:Id,labels:Seq<int>,props:Map<int,nr::Value>,graph:Option<int>},CreateEdge{source:Id,predicate:int,target:Id,qual:Option<nat>,graph:Option<int>,keywords:bool}}
pub open spec fn callback(e:Event,g:Option<int>)->Option<Action>{match e{
 Event::Node{id,labels,props}=>Some(Action::CreateNode{id,labels,props,graph:g}),
 Event::Edge{source,predicate,target,qual}=>Some(Action::CreateEdge{source,predicate,target,qual,graph:g,keywords:g.is_some()||qual.is_some()}),Event::Outside=>None}}
pub struct Import{pub calls:Seq<Action>,pub nodes:nat,pub edges:nat}
pub open spec fn import_start()->Import{Import{calls:seq![],nodes:0,edges:0}}
pub open spec fn consume(i:Import,e:Event,g:Option<int>)->Import{let a=callback(e,g);if a.is_none(){i}else{Import{calls:i.calls.push(a.unwrap()),nodes:i.nodes+if is_node(e){1nat}else{0nat},edges:i.edges+if is_edge(e){1nat}else{0nat}}}}
pub open spec fn import_lines(i:Import,es:Seq<Event>,g:Option<int>)->Import decreases es.len(){if es.len()==0{i}else{import_lines(consume(i,es[0],g),es.drop_first(),g)}}
pub open spec fn actions(es:Seq<Event>,g:Option<int>)->Seq<Action> decreases es.len(){if es.len()==0{seq![]}else{let a=callback(es[0],g);let tail=actions(es.drop_first(),g);if a.is_some(){seq![a.unwrap()]+tail}else{tail}}}
pub open spec fn valid_events(es:Seq<Event>)->bool{forall|i:int|0<=i<es.len()==>is_node(#[trigger] es[i])||is_edge(es[i])}
pub proof fn lemma_kind_counts_cons(e:Event,es:Seq<Event>)
 ensures ncount(seq![e]+es)==ncount(es)+if is_node(e){1nat}else{0nat},ecount(seq![e]+es)==ecount(es)+if is_edge(e){1nat}else{0nat},
 {lemma_kind_counts_concat(seq![e],es);reveal_with_fuel(ncount,2);reveal_with_fuel(ecount,2);}
pub proof fn theorem_import_callback_arguments_and_counts(i:Import,es:Seq<Event>,g:Option<int>)
 requires valid_events(es),
 ensures import_lines(i,es,g).calls==i.calls+actions(es,g),import_lines(i,es,g).nodes==i.nodes+ncount(es),import_lines(i,es,g).edges==i.edges+ecount(es),actions(es,g).len()==es.len(),forall|j:int|0<=j<es.len()==>Some(actions(es,g)[j])==callback(es[j],g),
 decreases es.len(),
 {if es.len()>0{assert(valid_events(es.drop_first()));assert(callback(es[0],g).is_some());assert(es=~=seq![es[0]]+es.drop_first());let next=consume(i,es[0],g);theorem_import_callback_arguments_and_counts(next,es.drop_first(),g);lemma_append_relation(i.calls,callback(es[0],g).unwrap(),actions(es.drop_first(),g));lemma_kind_counts_cons(es[0],es.drop_first());
 assert forall|j:int|0<=j<es.len() implies Some(actions(es,g)[j])==callback(es[j],g) by{if j>0{assert(es.drop_first()[j-1]==es[j]);}}}else{assert(i.calls+Seq::empty()=~=i.calls);}}
pub proof fn theorem_actual_generated_export_to_import_callbacks(ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,es:Seq<EdgeRow>,g:Option<int>)
 requires ordinary_keys(ps),admitted_edges(es),
 ensures import_lines(import_start(),export(ns,ls,ps,es).lines,g).nodes==export(ns,ls,ps,es).nodes,import_lines(import_start(),export(ns,ls,ps,es).lines,g).edges==export(ns,ls,ps,es).edges,import_lines(import_start(),export(ns,ls,ps,es).lines,g).calls.len()==export(ns,ls,ps,es).lines.len(),forall|i:int|0<=i<export(ns,ls,ps,es).lines.len()==>Some(import_lines(import_start(),export(ns,ls,ps,es).lines,g).calls[i])==callback(export(ns,ls,ps,es).lines[i],g),
 {theorem_complete_export_line_sequence_and_counts(ns,ls,ps,es);let lines=export(ns,ls,ps,es).lines;
 assert forall|i:int|0<=i<lines.len() implies is_node(#[trigger] lines[i])||is_edge(lines[i]) by{theorem_export_nodes_before_edges(ns,ls,ps,es,i);}
 theorem_import_callback_arguments_and_counts(import_start(),lines,g);assert(Seq::<Action>::empty()+actions(lines,g)=~=actions(lines,g));}
pub proof fn theorem_zero_qualifier_uses_keyword_call(source:Id,predicate:int,target:Id)
 ensures callback(Event::Edge{source,predicate,target,qual:Some(0)},None)==Some(Action::CreateEdge{source,predicate,target,qual:Some(0),graph:None,keywords:true}),{}
pub proof fn theorem_empty_named_graph_is_still_explicit(source:Id,predicate:int,target:Id)
 ensures callback(Event::Edge{source,predicate,target,qual:None},Some(0))==Some(Action::CreateEdge{source,predicate,target,qual:None,graph:Some(0),keywords:true}),callback(Event::Edge{source,predicate,target,qual:None},None)==Some(Action::CreateEdge{source,predicate,target,qual:None,graph:None,keywords:false}),{}

pub proof fn theorem_final_file_node_fields(ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,es:Seq<EdgeRow>,i:int)
 requires ordinary_keys(ps),admitted_edges(es),0<=i<export(ns,ls,ps,es).nodes,
 ensures export(ns,ls,ps,es).lines[i]==(Event::Node{id:census(ns)[i],labels:labels(ls,0,census(ns)[i]),props:expected_props(ps,0,census(ns)[i])}),
 {theorem_complete_export_line_sequence_and_counts(ns,ls,ps,es);theorem_full_node_events_from_raw(ns,ls,ps);order::theorem_sort_ordered_and_length(selected_ids(ns),|id:Id|id);}
pub proof fn theorem_final_file_edge_fields(ns:Seq<Parent>,ls:Seq<Label>,ps:Seq<Prop>,es:Seq<EdgeRow>,i:int)
 requires ordinary_keys(ps),admitted_edges(es),0<=i<export(ns,ls,ps,es).edges,
 ensures export(ns,ls,ps,es).lines[export(ns,ls,ps,es).nodes+i]==edge_event(edge_census(es)[i]),edge_census(es).contains(edge_census(es)[i]),es.contains(edge_census(es)[i]),selected_edge(edge_census(es)[i]),
 {theorem_complete_export_line_sequence_and_counts(ns,ls,ps,es);theorem_full_node_events_from_raw(ns,ls,ps);order::theorem_sort_ordered_and_length(edge_rows(es),|e:EdgeRow|e.serial);let e=edge_census(es)[i];theorem_edge_census_derived(es,e);assert(edge_census(es).contains(e));}

pub proof fn witness_bare_parent_still_writes_a_line() ensures export(seq![Parent{graph:0,id:0}],seq![],seq![],seq![]).nodes==1 && export(seq![Parent{graph:0,id:0}],seq![],seq![],seq![]).lines.len()==1, {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_named_parent_does_not_duplicate_default_id() ensures export(seq![Parent{graph:0,id:0},Parent{graph:7,id:0}],seq![],seq![],seq![]).nodes==1, {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_id_property_reaches_alias_in_file() ensures ({let f=export(seq![Parent{graph:0,id:0}],seq![],seq![Prop{graph:0,id:0,key:0,stored:nr::Stored::Number{payload:10,double:false}}],seq![]);match f.lines[0]{Event::Node{id,labels:_,props}=>id==0&&props.contains_key(2)&&props[2]==nr::Value::Integer(10),_=>false}}), {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_two_label_rows_survive_file() ensures ({let f=export(seq![Parent{graph:0,id:0}],seq![Label{graph:0,id:0,label:1},Label{graph:0,id:0,label:2}],seq![],seq![]);match f.lines[0]{Event::Node{id:_,labels,props:_}=>labels==seq![1,2],_=>false}}), {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_last_alias_row_wins_in_file() ensures ({let f=export(seq![Parent{graph:0,id:0}],seq![],seq![Prop{graph:0,id:0,key:0,stored:nr::Stored::Number{payload:10,double:false}},Prop{graph:0,id:0,key:2,stored:nr::Stored::Number{payload:20,double:false}}],seq![]);match f.lines[0]{Event::Node{id:_,labels:_,props}=>props[2]==nr::Value::Integer(20),_=>false}}), {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_named_property_does_not_enter_default_file() ensures ({let f=export(seq![Parent{graph:0,id:0}],seq![],seq![Prop{graph:0,id:0,key:4,stored:nr::Stored::Number{payload:10,double:false}},Prop{graph:7,id:0,key:4,stored:nr::Stored::Number{payload:20,double:false}}],seq![]);match f.lines[0]{Event::Node{id:_,labels:_,props}=>props[4]==nr::Value::Integer(10),_=>false}}), {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_nodes_counter_counts_written_lines() ensures export(seq![Parent{graph:0,id:0}],seq![],seq![],seq![]).nodes==export(seq![Parent{graph:0,id:0}],seq![],seq![],seq![]).lines.len(), {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_named_edge_not_written() ensures export(seq![Parent{graph:0,id:0}],seq![],seq![],seq![EdgeRow{graph:7,serial:0,source:0,predicate:0,target:0,raw:None}]).edges==0, {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_marked_edge_not_written() ensures export(seq![Parent{graph:0,id:0}],seq![],seq![],seq![EdgeRow{graph:0,serial:0,source:0,predicate:0,target:0,raw:Some(seq!['{','"','t','e','m','p','o','r','a','l','"',':','t','r','u','e','}'])}]).edges==0, {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_parallel_physical_rows_both_written() ensures export(seq![Parent{graph:0,id:0}],seq![],seq![],seq![EdgeRow{graph:0,serial:0,source:0,predicate:0,target:0,raw:None},EdgeRow{serial:1,..EdgeRow{graph:0,serial:0,source:0,predicate:0,target:0,raw:None}}]).edges==2, {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_zero_qualifier_kept_in_file() ensures ({let f=export(seq![],seq![],seq![],seq![EdgeRow{graph:0,serial:0,source:0,predicate:0,target:0,raw:Some(seq!['{','"','q','"',':','0','}'])}]);f.lines[0]==(Event::Edge{source:0,predicate:0,target:0,qual:Some(0)})}), {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

pub proof fn witness_node_line_precedes_edge_line() ensures ({let f=export(seq![Parent{graph:0,id:0}],seq![],seq![],seq![EdgeRow{graph:0,serial:0,source:0,predicate:0,target:0,raw:None}]);is_node(f.lines[0])&&is_edge(f.lines[1])}), {reveal_with_fuel(selected_ids,4);reveal_with_fuel(edge_rows,4);reveal_with_fuel(order::sort,4);reveal_with_fuel(order::insert,4);reveal_with_fuel(node_pass,4);reveal_with_fuel(edge_pass,4);reveal_with_fuel(return_rows,4);reveal_with_fuel(ids,4);reveal_with_fuel(label_fold,4);reveal_with_fuel(prop_fold,4);reveal_with_fuel(qualifier::digits,4);}

}
