// product3eaa79cf: raw normalized SQL rows -> hydrated maps -> default NDJSON records.
use vstd::prelude::*;
#[path="../node_read/node_read.rs"] pub mod nr;
#[path="../bulk_children/bulk_children.rs"] pub mod bc;
pub mod qualifier;
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

}
