use vstd::prelude::*;
use crate::*;
verus! {
pub enum Data {Text(Text),Node(Node),Rel(Stmt),Tuple(Tuple)}
pub struct Entry {pub rel:bool,pub id:int,pub attr:Option<(nat,Text)>,pub before:Option<Data>,pub after:Option<Data>}
pub struct Life {pub created:bool,pub existence_new:Option<Data>,pub attrs:Map<(nat,Text),(Option<Text>,Option<Text>)>}
pub struct Delta {pub closed:Seq<Entry>,pub live:Map<(bool,int),Life>}
pub open spec fn delta()->Delta {Delta{closed:seq![],live:Map::empty()}}
pub open spec fn create(d:Delta,rel:bool,id:int,new:Data)->Delta {
 Delta{live:d.live.insert((rel,id),Life{created:true,existence_new:Some(new),attrs:Map::empty()}),..d}
}
pub open spec fn remove(d:Delta,rel:bool,id:int,snapshot:Data)->Delta {
 let k=(rel,id);let created=d.live.contains_key(k) && d.live[k].created;
 Delta{closed:if created{d.closed}else{d.closed.push(Entry{rel,id,attr:None,before:Some(snapshot),after:None})},live:d.live.remove(k)}
}
pub open spec fn lifecycle(d:Delta,r:Record)->Delta {
 if r.redacted || r.audit{d}else{match r.action {
 Action::CreateNode(id)=>create(d,false,id,Data::Text(seq![])),Action::CreateRel(id,t)=>create(d,true,id,Data::Tuple(t)),
 Action::DeleteNode{id,snapshot}=>remove(d,false,id,Data::Node(snapshot)),Action::DeleteRel{id,snapshot}=>remove(d,true,id,Data::Rel(snapshot)),
 _=>{let a=attr_record(r);if a.is_none(){d}else{
  let (f,b,n)=a.unwrap();let k=(f.0==2,f.1);let ak=(f.0,f.2);
  let l=if d.live.contains_key(k){d.live[k]}else{Life{created:false,existence_new:None,attrs:Map::empty()}};
  let first=if l.attrs.contains_key(ak){l.attrs[ak].0}else if l.created{None}else{b};
  Delta{live:d.live.insert(k,Life{attrs:l.attrs.insert(ak,(first,n)),..l}),..d}}}
 }}
}
pub open spec fn lifecycles(d:Delta,rs:Seq<Record>)->Delta decreases rs.len() {
 if rs.len()==0{d}else{lifecycles(lifecycle(d,rs[0]),rs.drop_first())}
}
pub open spec fn inverse(es:Seq<Entry>)->Seq<Entry> {
 es.map_values(|e:Entry|Entry{before:e.after,after:e.before,..e})
}
pub proof fn theorem_simple_full_snapshot_survives_inverse(s:State,id:int)
 requires s.nodes.contains_key(id),!(exists|rid:int|s.rels.contains_key(rid) && s.rels[rid].tuple.3.is_none() && (s.rels[rid].tuple.0==id || s.rels[rid].tuple.2==id)),
 ensures ({let r=produce(s,Op::DeleteNode(id)).records[0];let d=lifecycle(delta(),r);
   inverse(d.closed)==seq![Entry{rel:false,id,attr:None,before:None,after:Some(Data::Node(s.nodes[id]))}]}),
{theorem_simple_snapshot_is_complete(s,id);}
pub proof fn lemma_lifecycles_concat(d:Delta,a:Seq<Record>,b:Seq<Record>)
 ensures lifecycles(d,a+b)==lifecycles(lifecycles(d,a),b),
 decreases a.len(),
{if a.len()>0{lemma_lifecycles_concat(lifecycle(d,a[0]),a.drop_first(),b);assert((a+b).drop_first() =~= a.drop_first()+b);}}
#[verifier::opaque]
pub open spec fn rich_base()->Output {request(initial_store(),Request::Node{id:0,upsert:false,labels:seq![seq!['L']],props:seq![(seq!['k'],seq!['1'])]})}
#[verifier::opaque]
pub open spec fn rich_changed()->Reply {execute(rich_base().store.state,seq![Op::SetProp(0,seq!['k'],seq!['2']),Op::AddLabel(0,seq!['M'])])}
#[verifier::opaque]
pub open spec fn rich_deleted()->Reply {produce(rich_changed().state,Op::DeleteNode(0))}
#[verifier::opaque]
pub open spec fn rich_recreated()->Reply {execute(rich_deleted().state,seq![Op::CreateNode(0,false),Op::SetProp(0,seq!['k'],seq!['3'])])}
pub proof fn lemma_rich_raw_states()
 ensures rich_base().store.state.nodes[0].props==map![seq!['k']=>seq!['1']],rich_base().store.state.nodes[0].labels==set![seq!['L']],
         rich_changed().state.nodes[0]==(Node{labels:set![seq!['L'],seq!['M']],props:map![seq!['k']=>seq!['2']]}),
         rich_changed().state.rels==Map::<int,Stmt>::empty(),
         rich_changed().records==seq![rec(Action::SetProp{id:0,key:seq!['k'],prior:Some(seq!['1']),new:Some(seq!['2'])}),rec(Action::AddLabel(0,seq!['M']))],
{
 reveal(rich_base);reveal(rich_changed);reveal_with_fuel(execute,5);
 theorem_new_node_emits_separate_content(initial_store(),0,seq!['k'],seq!['1'],seq!['L']);
}
pub proof fn lemma_rich_delete_and_recreate()
 ensures rich_deleted().records==seq![rec(Action::DeleteNode{id:0,snapshot:rich_changed().state.nodes[0]})],
         rich_recreated().state.nodes[0].props==map![seq!['k']=>seq!['3']],
         rich_recreated().records==seq![rec(Action::CreateNode(0)),rec(Action::SetProp{id:0,key:seq!['k'],prior:None,new:Some(seq!['3'])})],
{
 lemma_rich_raw_states();reveal(rich_deleted);reveal(rich_recreated);reveal_with_fuel(execute,4);
 theorem_simple_snapshot_is_complete(rich_changed().state,0);
}
pub proof fn theorem_rich_known_lifecycle_keeps_deletion_time_snapshot()
 ensures ({let d=lifecycles(delta(),rich_changed().records+rich_deleted().records+rich_recreated().records);
  rich_base().store.state.nodes[0].props[seq!['k']]==seq!['1'] && rich_base().store.state.nodes[0].labels==set![seq!['L']]
  && rich_recreated().state.nodes[0].props[seq!['k']]==seq!['3'] && d.closed.len()==1
  && inverse(d.closed)[0].after==Some(Data::Node(Node{labels:set![seq!['L'],seq!['M']],props:map![seq!['k']=>seq!['2']]}))
  && d.live[(false,0)].created && d.live[(false,0)].attrs[(1nat,seq!['k'])]==(None,Some(seq!['3']))}),
{
 lemma_rich_raw_states();lemma_rich_delete_and_recreate();
 reveal_with_fuel(lifecycles,3);
 lemma_lifecycles_concat(delta(),rich_changed().records,rich_deleted().records+rich_recreated().records);
 let d1=lifecycles(delta(),rich_changed().records);
 assert(d1.live.contains_key((false,0)));assert(!d1.live[(false,0)].created);
 lemma_lifecycles_concat(d1,rich_deleted().records,rich_recreated().records);
 let d2=lifecycles(d1,rich_deleted().records);
 assert(d2.closed.len()==1);assert(d2.closed[0].before==Some(Data::Node(rich_changed().state.nodes[0])));
 assert(!d2.live.contains_key((false,0)));
}

pub enum Row {Node(int),Label(int,Text),Prop(int,Text,Option<Text>),Edge{s:int,p:Text,o:int,raw_graph:Option<Text>,quals:Seq<(Text,InputValue)>}}
pub open spec fn parsed_pairs(qs:Seq<(Text,InputValue)>)->Seq<(Text,Text)> {
 qs.filter(|kv:(Text,InputValue)|parsed_qual(kv.1).is_some()).map_values(|kv:(Text,InputValue)|(kv.0,parsed_qual(kv.1).unwrap()))
}
pub open spec fn temporal_marked(qs:Seq<(Text,InputValue)>)->bool {
 exists|i:int|0<=i<qs.len() && qs[i].0==seq!['t','e','m','p','o','r','a','l'] && qs[i].1==InputValue::Boolean(true)
}
pub open spec fn quals_map(m:Map<Text,Text>,qs:Seq<(Text,Text)>)->Map<Text,Text> decreases qs.len() {
 if qs.len()==0{m}else{quals_map(m.insert(qs[0].0,qs[0].1),qs.drop_first())}
}
pub open spec fn qual_records(id:int,qs:Seq<(Text,Text)>)->Seq<Record> {
 qs.map_values(|kv:(Text,Text)|rec(Action::SetQual{id,key:kv.0,prior:None,new:Some(kv.1)}))
}
pub proof fn lemma_qual_record_fold(s:State,id:int,qs:Seq<(Text,Text)>)
 requires s.rels.contains_key(id),
 ensures fold(s,qual_records(id,qs))==put_rel(s,id,Stmt{quals:quals_map(s.rels[id].quals,qs),..s.rels[id]}),
 decreases qs.len(),
{
 if qs.len()>0{
  let n=put_rel(s,id,Stmt{quals:s.rels[id].quals.insert(qs[0].0,qs[0].1),..s.rels[id]});
  assert(qual_records(id,qs)[0]==rec(Action::SetQual{id,key:qs[0].0,prior:None,new:Some(qs[0].1)}));
  assert(apply(s,qual_records(id,qs)[0])==n);
  assert(qual_records(id,qs).drop_first() =~= qual_records(id,qs.drop_first()));lemma_qual_record_fold(n,id,qs.drop_first());
  let v=Stmt{quals:quals_map(s.rels[id].quals,qs),..s.rels[id]};
  assert(put_rel(n,id,v).rels =~= put_rel(s,id,v).rels);
  assert(fold(s,qual_records(id,qs))==put_rel(n,id,v));
 }else{
  assert(qual_records(id,qs) =~= seq![]);assert(s.rels.insert(id,s.rels[id]) =~= s.rels);
 }
}

pub open spec fn capture_step(g:Store,row:Row)->Output {match row {
 Row::Node(id)=>Output{store:Store{state:put_node(g.state,id,empty_node()),..g},records:seq![rec(Action::CreateNode(id))],error:None},
 Row::Label(id,k)=>Output{store:Store{state:if g.state.nodes.contains_key(id){put_node(g.state,id,Node{labels:g.state.nodes[id].labels.insert(k),..g.state.nodes[id]})}else{g.state},..g},records:seq![rec(Action::AddLabel(id,k))],error:None},
 Row::Prop(id,k,v)=>if reserved(k){Output{store:g,records:seq![],error:None}}else{
  Output{store:Store{state:if g.state.nodes.contains_key(id){put_node(g.state,id,Node{props:g.state.nodes[id].props.insert(k,text(v)),..g.state.nodes[id]})}else{g.state},..g},records:seq![rec(Action::SetProp{id,key:k,prior:None,new:Some(text(v))})],error:None}},
 Row::Edge{s,p,o,raw_graph,quals}=>if temporal_marked(quals){Output{store:g,records:seq![],error:None}}else{
  let qs=parsed_pairs(quals);if exists|i:int|0<=i<qs.len() && qs[i].0.len()==0{Output{store:g,records:seq![],error:Some(Error::KeyCarrier)}}else{
   let id=g.next as int;let t=tuple(s,p,o,raw_graph);
   Output{store:Store{state:State{rels:g.state.rels.insert(id,Stmt{tuple:t,quals:quals_map(Map::empty(),qs)}),by_tuple:g.state.by_tuple.insert(t,id),..g.state},next:g.next+1,..g},records:seq![rec(Action::CreateRel(id,t))]+qual_records(id,qs),error:None}}},
}}
pub proof fn theorem_capture_row_full_content(g:Store,row:Row)
 ensures fold(g.state,capture_step(g,row).records)==capture_step(g,row).store.state,
{
 match row {
  Row::Edge{s,p,o,raw_graph,quals}=>if !temporal_marked(quals){let qs=parsed_pairs(quals);if !(exists|i:int|0<=i<qs.len() && qs[i].0.len()==0){
   let id=g.next as int;let t=tuple(s,p,o,raw_graph);let n=State{rels:g.state.rels.insert(id,Stmt{tuple:t,quals:Map::empty()}),by_tuple:g.state.by_tuple.insert(t,id),..g.state};
   lemma_qual_record_fold(n,id,qs);lemma_fold_concat(g.state,seq![rec(Action::CreateRel(id,t))],qual_records(id,qs));reveal_with_fuel(fold,2);
  }},_=>{reveal_with_fuel(fold,2);},
 }
}
pub open spec fn capture(g:Store,rows:Seq<Row>)->Output decreases rows.len() {
 if rows.len()==0{Output{store:g,records:seq![],error:None}}else{
  let first=capture_step(g,rows[0]);if first.error.is_some(){Output{store:g,records:seq![],error:first.error}}else{
   let rest=capture(first.store,rows.drop_first());if rest.error.is_some(){Output{store:g,records:seq![],error:rest.error}}else{Output{records:first.records+rest.records,..rest}}}}
}
pub proof fn theorem_genesis_full_content_from_raw_rows(g:Store,rows:Seq<Row>)
 ensures fold(g.state,capture(g,rows).records)==capture(g,rows).store.state,
 decreases rows.len(),
{
 if rows.len()>0{let first=capture_step(g,rows[0]);theorem_capture_row_full_content(g,rows[0]);
  if first.error.is_none(){theorem_genesis_full_content_from_raw_rows(first.store,rows.drop_first());lemma_fold_concat(g.state,first.records,capture(first.store,rows.drop_first()).records);}}
}
pub proof fn theorem_temporal_boolean_marker_differs_from_string(g:Store,s:int,p:Text,o:int)
 ensures capture_step(g,Row::Edge{s,p,o,raw_graph:None,quals:seq![(seq!['t','e','m','p','o','r','a','l'],InputValue::Boolean(true))]}).records.len()==0,
         !temporal_marked(seq![(seq!['t','e','m','p','o','r','a','l'],InputValue::Text(seq!['t','r','u','e']))]),
{
 let q=seq![(seq!['t','e','m','p','o','r','a','l'],InputValue::Boolean(true))];assert(q[0].1==InputValue::Boolean(true));assert(exists|i:int|0<=i<q.len() && q[i].0==seq!['t','e','m','p','o','r','a','l'] && q[i].1==InputValue::Boolean(true));
}
}
verus! {
pub struct Identities {pub tuples:Map<Tuple,int>,pub statements:Map<int,Tuple>,pub next:nat}
pub struct Adopted {pub ids:Identities,pub record:Record}
// Native adoption accepts record-shaped input; it does not reapply ordinary SQL.
// The prior payload is copied, not claimed to be a validated store snapshot.
pub open spec fn adopt(ids:Identities,r:Record)->Adopted {match r.action {
 Action::CreateRel(_,t)=>{
  let exists=ids.tuples.contains_key(t);let id=if exists{ids.tuples[t]}else{ids.next as int};
  Adopted{ids:if exists{ids}else{Identities{tuples:ids.tuples.insert(t,id),statements:ids.statements.insert(id,t),next:ids.next+1}},record:Record{action:Action::CreateRel(id,t),..r}}},
 Action::DeleteRel{id,..}=>Adopted{ids:if ids.statements.contains_key(id){Identities{tuples:ids.tuples.remove(ids.statements[id]),..ids}}else{ids},record:r},
 _=>Adopted{ids,record:r},
}}
pub proof fn theorem_adoption_identity_is_derived(ids:Identities,r:Record,t:Tuple,supplied:int)
 requires r.action==Action::CreateRel(supplied,t),
 ensures adopt(ids,r).record.action==Action::CreateRel(if ids.tuples.contains_key(t){ids.tuples[t]}else{ids.next as int},t),
{}
pub proof fn theorem_adoption_attribute_payload_is_copied(ids:Identities,r:Record)
 requires attr_record(r).is_some(),
 ensures adopt(ids,r).record==r,adopt(ids,r).ids==ids,
{}
}
