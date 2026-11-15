use vstd::prelude::*;
#[path="../reconstruction/reconstruction.rs"] pub mod old;
verus! {
pub type Text=Seq<char>;
pub type Tuple=(int,Text,int,Option<Text>);
pub struct Node {pub labels:Set<Text>,pub props:Map<Text,Text>}
pub struct Stmt {pub tuple:Tuple,pub quals:Map<Text,Text>}
pub struct State {pub nodes:Map<int,Node>,pub rels:Map<int,Stmt>,pub by_tuple:Map<Tuple,int>}
pub open spec fn empty_node()->Node {Node{labels:Set::empty(),props:Map::empty()}}
pub open spec fn empty()->State {State{nodes:Map::empty(),rels:Map::empty(),by_tuple:Map::empty()}}
pub open spec fn graph(g:Option<Text>)->Option<Text> {if g.is_none() || g.unwrap().len()==0 || g==Some(seq!['\0']){None}else{g}}
pub open spec fn tuple(s:int,p:Text,o:int,g:Option<Text>)->Tuple {(s,p,o,graph(g))}
pub open spec fn reserved(k:Text)->bool {k==seq!['i','d'] || k==seq!['_','_','g','r','a','p','h']}
pub open spec fn text(v:Option<Text>)->Text {if v.is_some(){v.unwrap()}else{seq![]}}
pub open spec fn value<K>(m:Map<K,Text>,k:K)->Option<Text> {if m.contains_key(k){Some(m[k])}else{None}}
pub enum Action {
 CreateNode(int),DeleteNode{ id:int,snapshot:Node },AddLabel(int,Text),RemoveLabel(int,Text),
 SetProp{ id:int,key:Text,prior:Option<Text>,new:Option<Text> },RemoveProp{ id:int,key:Text,prior:Text },
 CreateRel(int,Tuple),DeleteRel{ id:int,snapshot:Stmt },
 SetQual{ id:int,key:Text,prior:Option<Text>,new:Option<Text> },RemoveQual{ id:int,key:Text,prior:Text },
 Temporal,Other,
}
pub struct Record {pub seq:nat,pub ordinal:nat,pub action:Action,pub redacted:bool,pub audit:bool}
pub open spec fn rec(a:Action)->Record {Record{seq:1,ordinal:1,action:a,redacted:false,audit:false}}
pub open spec fn put_node(s:State,id:int,n:Node)->State {State{nodes:s.nodes.insert(id,n),..s}}
pub open spec fn put_rel(s:State,id:int,r:Stmt)->State {State{rels:s.rels.insert(id,r),..s}}
pub open spec fn apply(s:State,r:Record)->State {
 if r.redacted || r.audit{s}else{match r.action {
  Action::CreateNode(id)=>put_node(s,id,empty_node()),
  Action::DeleteNode{id,..}=>State{nodes:s.nodes.remove(id),..s},
  Action::AddLabel(id,k)=>if s.nodes.contains_key(id){put_node(s,id,Node{labels:s.nodes[id].labels.insert(k),..s.nodes[id]})}else{s},
  Action::RemoveLabel(id,k)=>if s.nodes.contains_key(id){put_node(s,id,Node{labels:s.nodes[id].labels.remove(k),..s.nodes[id]})}else{s},
  Action::SetProp{id,key,new,..}=>if s.nodes.contains_key(id){put_node(s,id,Node{props:s.nodes[id].props.insert(key,text(new)),..s.nodes[id]})}else{s},
  Action::RemoveProp{id,key,..}=>if s.nodes.contains_key(id){put_node(s,id,Node{props:s.nodes[id].props.remove(key),..s.nodes[id]})}else{s},
  Action::CreateRel(id,t)=>State{rels:s.rels.insert(id,Stmt{tuple:t,quals:Map::empty()}),by_tuple:s.by_tuple.insert(t,id),..s},
  Action::DeleteRel{id,..}=>if s.rels.contains_key(id){State{rels:s.rels.remove(id),by_tuple:s.by_tuple.remove(s.rels[id].tuple),..s}}else{s},
  Action::SetQual{id,key,new,..}=>if s.rels.contains_key(id){put_rel(s,id,Stmt{quals:s.rels[id].quals.insert(key,text(new)),..s.rels[id]})}else{s},
  Action::RemoveQual{id,key,..}=>if s.rels.contains_key(id){put_rel(s,id,Stmt{quals:s.rels[id].quals.remove(key),..s.rels[id]})}else{s},
  _=>s,
 }}
}
pub open spec fn fold(s:State,rs:Seq<Record>)->State decreases rs.len() {
 if rs.len()==0{s}else{fold(apply(s,rs[0]),rs.drop_first())}
}
pub enum NumberState {Start,Sign,Int,DotBare,DotTail,Frac,Exp,ExpSign,ExpDigits}
pub open spec fn digit(c:char)->bool {'0'<=c<='9'}
pub open spec fn number_next(st:NumberState,c:char)->Option<NumberState> {match st {
 NumberState::Start|NumberState::Sign=>if digit(c){Some(NumberState::Int)}else if c=='.'{Some(NumberState::DotBare)}else if matches!(st,NumberState::Start) && (c=='+' || c=='-'){Some(NumberState::Sign)}else{None},
 NumberState::Int=>if digit(c){Some(NumberState::Int)}else if c=='.'{Some(NumberState::DotTail)}else if c=='e' || c=='E'{Some(NumberState::Exp)}else{None},
 NumberState::DotBare=>if digit(c){Some(NumberState::Frac)}else{None},
 NumberState::DotTail|NumberState::Frac=>if digit(c){Some(NumberState::Frac)}else if c=='e' || c=='E'{Some(NumberState::Exp)}else{None},
 NumberState::Exp|NumberState::ExpSign=>if digit(c){Some(NumberState::ExpDigits)}else if matches!(st,NumberState::Exp) && (c=='+' || c=='-'){Some(NumberState::ExpSign)}else{None},
 NumberState::ExpDigits=>if digit(c){Some(NumberState::ExpDigits)}else{None},
}}
pub open spec fn number_scan(t:Text,st:NumberState)->Option<NumberState> decreases t.len() {
 if t.len()==0{Some(st)}else{let n=number_next(st,t[0]);if n.is_none(){None}else{number_scan(t.drop_first(),n.unwrap())}}
}
pub open spec fn numeric(t:Text)->bool {let n=number_scan(t,NumberState::Start);n.is_some() && matches!(n.unwrap(),NumberState::Int|NumberState::DotTail|NumberState::Frac|NumberState::ExpDigits)}
pub open spec fn weight_key(k:Text)->bool {k==seq!['w','e','i','g','h','t']}
pub enum Op {CreateNode(int,bool),AddLabel(int,Text),RemoveLabel(int,Text),SetProp(int,Text,Text),RemoveProp(int,Text),
 CreateRel(int,Tuple,bool),DeleteRel(int),SetQual(int,Text,Text),RemoveQual(int,Text),DeleteNode(int)}
pub enum Error {Exists,Missing,Reserved,EmptyKey,MissingAttribute,Incident,Numeric}
pub struct Reply {pub state:State,pub records:Seq<Record>,pub error:Option<Error>}
pub open spec fn fail(s:State,e:Error)->Reply {Reply{state:s,records:seq![],error:Some(e)}}
pub open spec fn done(s:State,rs:Seq<Record>)->Reply {Reply{state:s,records:rs,error:None}}
// This primitive is the ordinary successful-SQL/default-profile projection.
// Full batch create/upsert expands to these operations, not a supplied node map.
pub open spec fn produce(s:State,o:Op)->Reply {match o {
 Op::CreateNode(id,upsert)=>if s.nodes.contains_key(id){if upsert{done(s,seq![])}else{fail(s,Error::Exists)}}
  else{done(put_node(s,id,empty_node()),seq![rec(Action::CreateNode(id))])},
 Op::AddLabel(id,k)=>if !s.nodes.contains_key(id){fail(s,Error::Missing)}else if k.len()==0{fail(s,Error::EmptyKey)}
  else if s.nodes[id].labels.contains(k){done(s,seq![])}else{done(put_node(s,id,Node{labels:s.nodes[id].labels.insert(k),..s.nodes[id]}),seq![rec(Action::AddLabel(id,k))])},
 Op::RemoveLabel(id,k)=>if !s.nodes.contains_key(id){fail(s,Error::Missing)}else if !s.nodes[id].labels.contains(k){fail(s,Error::MissingAttribute)}
  else{done(put_node(s,id,Node{labels:s.nodes[id].labels.remove(k),..s.nodes[id]}),seq![rec(Action::RemoveLabel(id,k))])},
 Op::SetProp(id,k,v)=>if reserved(k){fail(s,Error::Reserved)}else if !s.nodes.contains_key(id){fail(s,Error::Missing)}else if k.len()==0{fail(s,Error::EmptyKey)}
  else if value(s.nodes[id].props,k)==Some(v){done(s,seq![])}
  else{done(put_node(s,id,Node{props:s.nodes[id].props.insert(k,v),..s.nodes[id]}),seq![rec(Action::SetProp{id,key:k,prior:value(s.nodes[id].props,k),new:Some(v)})])},
 Op::RemoveProp(id,k)=>if reserved(k){fail(s,Error::Reserved)}else if !s.nodes.contains_key(id){fail(s,Error::Missing)}else if !s.nodes[id].props.contains_key(k){fail(s,Error::MissingAttribute)}
  else{done(put_node(s,id,Node{props:s.nodes[id].props.remove(k),..s.nodes[id]}),seq![rec(Action::RemoveProp{id,key:k,prior:s.nodes[id].props[k]})])},
 Op::CreateRel(id,t,upsert)=>if !s.nodes.contains_key(t.0) || !s.nodes.contains_key(t.2){fail(s,Error::Missing)}
  else if t.1.len()==0{fail(s,Error::EmptyKey)}else if s.by_tuple.contains_key(t){if upsert{done(s,seq![])}else{fail(s,Error::Exists)}}
  else{done(State{rels:s.rels.insert(id,Stmt{tuple:t,quals:Map::empty()}),by_tuple:s.by_tuple.insert(t,id),..s},seq![rec(Action::CreateRel(id,t))])},
 Op::DeleteRel(id)=>if !s.rels.contains_key(id){fail(s,Error::Missing)}else{done(State{rels:s.rels.remove(id),by_tuple:s.by_tuple.remove(s.rels[id].tuple),..s},seq![rec(Action::DeleteRel{id,snapshot:s.rels[id]})])},
 Op::SetQual(id,k,v)=>if !s.rels.contains_key(id){fail(s,Error::Missing)}else if k.len()==0{fail(s,Error::EmptyKey)}else if weight_key(k) && !numeric(v){fail(s,Error::Numeric)}else if value(s.rels[id].quals,k)==Some(v){done(s,seq![])}
  else{done(put_rel(s,id,Stmt{quals:s.rels[id].quals.insert(k,v),..s.rels[id]}),seq![rec(Action::SetQual{id,key:k,prior:value(s.rels[id].quals,k),new:Some(v)})])},
 Op::RemoveQual(id,k)=>if !s.rels.contains_key(id){fail(s,Error::Missing)}else if k.len()==0{fail(s,Error::EmptyKey)}else if !s.rels[id].quals.contains_key(k){fail(s,Error::MissingAttribute)}
  else{done(put_rel(s,id,Stmt{quals:s.rels[id].quals.remove(k),..s.rels[id]}),seq![rec(Action::RemoveQual{id,key:k,prior:s.rels[id].quals[k]})])},
 Op::DeleteNode(id)=>if !s.nodes.contains_key(id){fail(s,Error::Missing)}else if exists|rid:int|s.rels.contains_key(rid) && s.rels[rid].tuple.3.is_none() && (s.rels[rid].tuple.0==id || s.rels[rid].tuple.2==id){fail(s,Error::Incident)}
  else{done(State{nodes:s.nodes.remove(id),..s},seq![rec(Action::DeleteNode{id,snapshot:s.nodes[id]})])},
}}
pub proof fn theorem_primitive_records_replay_full_content(s:State,o:Op)
 ensures fold(s,produce(s,o).records)==produce(s,o).state,
         produce(s,o).error.is_some() ==> produce(s,o).state==s && produce(s,o).records.len()==0,
{reveal_with_fuel(fold,2);}
pub proof fn theorem_current_prior_is_derived(s:State,id:int,k:Text,v:Text)
 requires s.nodes.contains_key(id),!reserved(k),k.len()>0,value(s.nodes[id].props,k)!=Some(v),
 ensures produce(s,Op::SetProp(id,k,v)).records==seq![rec(Action::SetProp{id,key:k,prior:value(s.nodes[id].props,k),new:Some(v)})],
{}
pub proof fn theorem_simple_snapshot_is_complete(s:State,id:int)
 requires s.nodes.contains_key(id),!(exists|rid:int|s.rels.contains_key(rid) && s.rels[rid].tuple.3.is_none() && (s.rels[rid].tuple.0==id || s.rels[rid].tuple.2==id)),
 ensures produce(s,Op::DeleteNode(id)).records==seq![rec(Action::DeleteNode{id,snapshot:s.nodes[id]})],
{}
pub proof fn theorem_labels_and_quals_are_not_reset_by_existing_upsert(s:State,id:int)
 requires s.nodes.contains_key(id),
 ensures produce(s,Op::CreateNode(id,true)).state==s,produce(s,Op::CreateNode(id,true)).records.len()==0,
{}
pub proof fn theorem_reader_null_empty_text(s:State,id:int,k:Text)
 requires s.nodes.contains_key(id),
 ensures apply(s,rec(Action::SetProp{id,key:k,prior:None,new:None})).nodes[id].props[k]==seq![],
         apply(s,rec(Action::SetProp{id,key:k,prior:None,new:Some(seq![])})).nodes[id].props[k]==seq![],
         apply(s,rec(Action::SetProp{id,key:k,prior:None,new:Some(seq!['n','u','l','l'])})).nodes[id].props[k]==seq!['n','u','l','l'],
{}
pub proof fn theorem_delete_node_is_not_relationship_cascade(s:State,id:int)
 ensures apply(s,rec(Action::DeleteNode{id,snapshot:empty_node()})).rels==s.rels,
{}
pub proof fn theorem_tombstone_audit_temporal_ignored(s:State,r:Record)
 requires r.redacted || r.audit || matches!(r.action,Action::Temporal|Action::Other),
 ensures apply(s,r)==s,
{}
pub proof fn lemma_fold_concat(s:State,a:Seq<Record>,b:Seq<Record>)
 ensures fold(s,a+b)==fold(fold(s,a),b),
 decreases a.len(),
{
 if a.len()>0{lemma_fold_concat(apply(s,a[0]),a.drop_first(),b);assert((a+b).drop_first() =~= a.drop_first()+b);}
}
pub open spec fn execute(s:State,ops:Seq<Op>)->Reply decreases ops.len() {
 if ops.len()==0{done(s,seq![])}else{
  let first=produce(s,ops[0]);if first.error.is_some(){fail(s,first.error.unwrap())}else{
   let rest=execute(first.state,ops.drop_first());if rest.error.is_some(){fail(s,rest.error.unwrap())}
   else{done(rest.state,first.records+rest.records)}}}
}
pub proof fn theorem_transaction_records_replay_full_content(s:State,ops:Seq<Op>)
 ensures fold(s,execute(s,ops).records)==execute(s,ops).state,
         execute(s,ops).error.is_some() ==> execute(s,ops).state==s && execute(s,ops).records.len()==0,
 decreases ops.len(),
{
 if ops.len()>0{
  let first=produce(s,ops[0]);theorem_primitive_records_replay_full_content(s,ops[0]);
  if first.error.is_none(){theorem_transaction_records_replay_full_content(first.state,ops.drop_first());lemma_fold_concat(s,first.records,execute(first.state,ops.drop_first()).records);}
 }
}
pub enum Request {
 Node{ id:int,upsert:bool,labels:Seq<Text>,props:Seq<(Text,Text)> },
 Rel{ s:int,p:Text,o:int,raw_graph:Option<Text>,upsert:bool,quals:Seq<(Text,Text)> },
 Primitive(Op),
}
pub struct Store {pub state:State,pub next:nat}
pub struct Output {pub store:Store,pub records:Seq<Record>,pub error:Option<Error>}
pub open spec fn node_ops(id:int,labels:Seq<Text>,props:Seq<(Text,Text)>)->Seq<Op> {
 labels.map_values(|k:Text|Op::AddLabel(id,k))+props.map_values(|kv:(Text,Text)|Op::SetProp(id,kv.0,kv.1))
}
pub open spec fn request_ops(g:Store,q:Request)->Seq<Op> {match q {
 Request::Node{id,upsert,labels,props}=>seq![Op::CreateNode(id,upsert)]+node_ops(id,labels,props),
 Request::Rel{s,p,o,raw_graph,upsert,quals}=>{
  let t=tuple(s,p,o,raw_graph);let id=if g.state.by_tuple.contains_key(t){g.state.by_tuple[t]}else{g.next as int};
  seq![Op::CreateRel(id,t,upsert)]+quals.filter(|kv:(Text,Text)|kv.0.len()>0).map_values(|kv:(Text,Text)|Op::SetQual(id,kv.0,kv.1))},
 Request::Primitive(o)=>seq![o],
}}
pub open spec fn pre_error(g:Store,q:Request)->Option<Error> {match q {
 Request::Node{id,upsert,props,..}=>if g.state.nodes.contains_key(id) && !upsert{Some(Error::Exists)}
  else if exists|i:int|0<=i<props.len() && reserved(props[i].0){Some(Error::Reserved)}else{None},
 Request::Rel{s,p,o,quals,..}=>if !g.state.nodes.contains_key(s) || !g.state.nodes.contains_key(o){Some(Error::Missing)}else if p.len()==0{Some(Error::EmptyKey)}
  else if exists|i:int|0<=i<quals.len() && weight_key(quals[i].0) && !numeric(quals[i].1){Some(Error::Numeric)}else{None},
 _=>None,
}}
pub open spec fn allocating(g:Store,q:Request)->bool {match q {
 Request::Rel{s,p,o,raw_graph,..}=>!g.state.by_tuple.contains_key(tuple(s,p,o,raw_graph)),_=>false,
}}
pub open spec fn request(g:Store,q:Request)->Output {
 if pre_error(g,q).is_some(){Output{store:g,records:seq![],error:pre_error(g,q)}}else{
  let out=execute(g.state,request_ops(g,q));
  Output{store:Store{state:out.state,next:if out.error.is_none() && allocating(g,q){g.next+1}else{g.next}},records:out.records,error:out.error}}
}
pub proof fn theorem_raw_request_full_content(g:Store,q:Request)
 ensures fold(g.state,request(g,q).records)==request(g,q).store.state,
         request(g,q).error.is_some() ==> request(g,q).store.state==g.state && request(g,q).store.next==g.next && request(g,q).records.len()==0,
{theorem_transaction_records_replay_full_content(g.state,request_ops(g,q));}
pub proof fn theorem_new_node_emits_separate_content(g:Store,id:int,k:Text,v:Text,l:Text)
 requires !g.state.nodes.contains_key(id),!reserved(k),k.len()>0,l.len()>0,
 ensures ({let q=Request::Node{id,upsert:false,labels:seq![l],props:seq![(k,v)]};let out=request(g,q);
  out.error.is_none() && out.store.state.nodes[id].labels==set![l] && out.store.state.nodes[id].props==map![k=>v]
  && out.records==seq![rec(Action::CreateNode(id)),rec(Action::AddLabel(id,l)),rec(Action::SetProp{id,key:k,prior:None,new:Some(v)})]}),
{reveal_with_fuel(execute,5);}
pub proof fn theorem_same_value_and_label_are_noop(s:State,id:int,k:Text,v:Text,l:Text)
 requires s.nodes.contains_key(id),!reserved(k),k.len()>0,l.len()>0,s.nodes[id].props.contains_key(k),s.nodes[id].props[k]==v,s.nodes[id].labels.contains(l),
 ensures execute(s,seq![Op::AddLabel(id,l),Op::SetProp(id,k,v)]).records.len()==0,
{reveal_with_fuel(execute,4);}
pub proof fn theorem_reserved_create_has_no_committed_prefix(g:Store,id:int,l:Text)
 ensures request(g,Request::Node{id,upsert:true,labels:seq![l],props:seq![(seq!['i','d'],seq!['x'])]}).store.state==g.state,
         request(g,Request::Node{id,upsert:true,labels:seq![l],props:seq![(seq!['i','d'],seq!['x'])]}).records.len()==0,
{let ps=seq![(seq!['i','d'],seq!['x'])];assert(reserved(ps[0].0));assert(0<=0<ps.len() && reserved(ps[0].0));assert(exists|i:int|0<=i<ps.len() && reserved(ps[i].0));}
pub proof fn theorem_raw_graph_tuple_normalization(s:int,p:Text,o:int,named:Text)
 requires named.len()>0,named!=seq!['\0'],
 ensures tuple(s,p,o,None)==tuple(s,p,o,Some(seq![])),tuple(s,p,o,Some(seq!['\0']))==tuple(s,p,o,None),
         tuple(s,p,o,Some(named)).3==Some(named),
{}

pub open spec fn node_key()->spec_fn(int)->(bool,int) {|id:int|(false,id)}
pub open spec fn rel_key()->spec_fn(int)->(bool,int) {|id:int|(true,id)}
pub open spec fn project(s:State)->old::State {
 Map::new(s.nodes.dom().map(node_key()).union(s.rels.dom().map(rel_key())),|k:(bool,int)|0int)
}
pub open spec fn structural(r:Record)->old::Record {old::Record{seq:r.seq,redacted:r.redacted,audit:r.audit,op:match r.action {
 Action::CreateNode(id)=>old::Op::Create(false,id,0),Action::DeleteNode{id,..}=>old::Op::Delete(false,id),
 Action::AddLabel(id,_)|Action::RemoveLabel(id,_)|Action::SetProp{id,..}|Action::RemoveProp{id,..}=>old::Op::Update(false,id,0),
 Action::CreateRel(id,_)=>old::Op::Create(true,id,0),Action::DeleteRel{id,..}=>old::Op::Delete(true,id),
 Action::SetQual{id,..}|Action::RemoveQual{id,..}=>old::Op::Update(true,id,0),_=>old::Op::Other,
}}}
pub proof fn lemma_project_membership(s:State,k:(bool,int))
 ensures project(s).contains_key(k)==(if k.0{s.rels.contains_key(k.1)}else{s.nodes.contains_key(k.1)}),
         project(s).contains_key(k) ==> project(s)[k]==0,
{
 let ns=s.nodes.dom();let rs=s.rels.dom();ns.lemma_map_contains(node_key(),k);rs.lemma_map_contains(rel_key(),k);
 if k.0 && rs.contains(k.1){assert(rel_key()(k.1)==k);assert(exists|id:int|rs.contains(id) && rel_key()(id)==k);}
 if !k.0 && ns.contains(k.1){assert(node_key()(k.1)==k);assert(exists|id:int|ns.contains(id) && node_key()(id)==k);}
}
pub proof fn theorem_full_content_structural_step(s:State,r:Record)
 ensures project(apply(s,r))==old::apply(project(s),structural(r)),
{
 let n=apply(s,r);let out=old::apply(project(s),structural(r));
 assert forall|k:(bool,int)|project(n).contains_key(k)==out.contains_key(k) && (project(n).contains_key(k) ==> project(n)[k]==out[k]) by {
  lemma_project_membership(s,k);lemma_project_membership(n,k);
 }
 assert(project(n) =~= out);
}
pub proof fn theorem_entity_count_projection(s:State)
 ensures project(s).len()==s.nodes.len()+s.rels.len(),
 decreases s.nodes.len()+s.rels.len(),
{
 if s.nodes.len()>0{
  let ns=s.nodes.dom().to_seq();s.nodes.dom().lemma_to_seq_len();s.nodes.dom().lemma_to_seq_to_set_id();assert(ns.len()==s.nodes.len());let id=ns[0];assert(s.nodes.contains_key(id));
  let t=State{nodes:s.nodes.remove(id),..s};theorem_entity_count_projection(t);
  assert forall|k:(bool,int)|project(s).contains_key(k)==project(t).insert((false,id),0).contains_key(k) by {lemma_project_membership(s,k);lemma_project_membership(t,k);}
  assert(project(s) =~= project(t).insert((false,id),0));
 }else if s.rels.len()>0{
  let rs=s.rels.dom().to_seq();s.rels.dom().lemma_to_seq_len();s.rels.dom().lemma_to_seq_to_set_id();assert(rs.len()==s.rels.len());let id=rs[0];assert(s.rels.contains_key(id));
  let t=State{rels:s.rels.remove(id),..s};theorem_entity_count_projection(t);
  assert forall|k:(bool,int)|project(s).contains_key(k)==project(t).insert((true,id),0).contains_key(k) by {lemma_project_membership(s,k);lemma_project_membership(t,k);}
  assert(project(s) =~= project(t).insert((true,id),0));
 }else{assert(s.nodes =~= Map::<int,Node>::empty());assert(s.rels =~= Map::<int,Stmt>::empty());assert(project(s) =~= Map::<(bool,int),int>::empty());}
}
pub open spec fn selected(r:Record,through:nat)->bool {1<=r.seq<=through}
pub open spec fn next(s:State,r:Record,through:nat)->State {if selected(r,through){apply(s,r)}else{s}}
pub open spec fn named_fold(s:State,rs:Seq<Record>,through:nat)->State decreases rs.len() {
 if rs.len()==0{s}else{named_fold(next(s,rs[0],through),rs.drop_first(),through)}
}
pub open spec fn entity_count(s:State)->nat {s.nodes.len()+s.rels.len()}
pub open spec fn run(s:State,rs:Seq<Record>,through:nat,bound:Option<nat>,stream:bool)->Option<State> decreases rs.len() {
 if rs.len()==0{Some(s)}else{let n=next(s,rs[0],through);
  if selected(rs[0],through) && bound.is_some() && !stream && entity_count(n)>bound.unwrap(){None}
  else{run(n,rs.drop_first(),through,bound,stream)}}
}
pub proof fn theorem_named_full_fold_projects(s:State,rs:Seq<Record>,through:nat)
 ensures project(named_fold(s,rs,through))==old::fold(project(s),rs.map_values(|r:Record|structural(r)),through),
 decreases rs.len(),
{
 if rs.len()>0{
  theorem_full_content_structural_step(s,rs[0]);theorem_named_full_fold_projects(next(s,rs[0],through),rs.drop_first(),through);
  assert(rs.map_values(|r:Record|structural(r)).drop_first() =~= rs.drop_first().map_values(|r:Record|structural(r)));
 }
}
pub proof fn theorem_named_bound_result_projects(s:State,rs:Seq<Record>,through:nat,b:Option<nat>,stream:bool)
 ensures run(s,rs,through,b,stream).is_some()==old::run(project(s),rs.map_values(|r:Record|structural(r)),through,b,stream).is_some(),
         run(s,rs,through,b,stream).is_some() ==> project(run(s,rs,through,b,stream).unwrap())==old::run(project(s),rs.map_values(|r:Record|structural(r)),through,b,stream).unwrap(),
 decreases rs.len(),
{
 if rs.len()>0{
  let n=next(s,rs[0],through);theorem_entity_count_projection(n);theorem_full_content_structural_step(s,rs[0]);
  theorem_named_bound_result_projects(n,rs.drop_first(),through,b,stream);
  assert(rs.map_values(|r:Record|structural(r)).drop_first() =~= rs.drop_first().map_values(|r:Record|structural(r)));
 }
}
pub proof fn theorem_full_stream_and_export_fold(s:State,rs:Seq<Record>,through:nat,b:Option<nat>)
 ensures run(s,rs,through,b,true)==Some(named_fold(s,rs,through)),run(s,rs,through,None,false)==Some(named_fold(s,rs,through)),
 decreases rs.len(),
{if rs.len()>0{theorem_full_stream_and_export_fold(next(s,rs[0],through),rs.drop_first(),through,b);}}
pub proof fn theorem_later_records_cannot_change_full_content(s:State,a:Seq<Record>,later:Seq<Record>,through:nat,b:Option<nat>,stream:bool)
 requires forall|i:int|0<=i<later.len() ==> later[i].seq>through,
 ensures named_fold(s,a+later,through)==named_fold(s,a,through),run(s,a+later,through,b,stream)==run(s,a,through,b,stream),
 decreases a.len()+later.len(),
{
 if a.len()>0{
  theorem_later_records_cannot_change_full_content(next(s,a[0],through),a.drop_first(),later,through,b,stream);
  assert((a+later).drop_first() =~= a.drop_first()+later);
 }else if later.len()>0{
  assert forall|i:int|0<=i<later.drop_first().len() implies later.drop_first()[i].seq>through by {assert(later.drop_first()[i]==later[i+1]);}
  theorem_later_records_cannot_change_full_content(s,seq![],later.drop_first(),through,b,stream);
 }
}
pub open spec fn stamp(rs:Seq<Record>,seq:nat,start:nat)->Seq<Record> {Seq::new(rs.len(),|i:int|Record{seq,ordinal:start+(i as nat),..rs[i]})}
pub proof fn theorem_stamping_preserves_full_content(s:State,rs:Seq<Record>,seq:nat,start:nat)
 ensures fold(s,stamp(rs,seq,start))==fold(s,rs),
 decreases rs.len(),
{
 if rs.len()>0{
  assert(stamp(rs,seq,start).drop_first() =~= stamp(rs.drop_first(),seq,start+1));
  theorem_stamping_preserves_full_content(apply(s,rs[0]),rs.drop_first(),seq,start+1);
 }
}

pub proof fn theorem_batch_empty_qual_is_skipped(g:Store,s:int,p:Text,o:int,rg:Option<Text>,upsert:bool,k:Text,v:Text,x:Text)
 requires k.len()>0,!weight_key(k),
 ensures request(g,Request::Rel{s,p,o,raw_graph:rg,upsert,quals:seq![(seq![],x),(k,v)]})
          ==request(g,Request::Rel{s,p,o,raw_graph:rg,upsert,quals:seq![(k,v)]}),
{
 let a=seq![(seq![],x),(k,v)];let b=seq![(k,v)];let pred=|kv:(Text,Text)|kv.0.len()>0;
 a.lemma_filter_eq_filter_alt(pred);b.lemma_filter_eq_filter_alt(pred);
 assert(a.filter(pred)==b);assert(b.filter(pred)==b);
 assert forall|i:int|0<=i<a.len() implies !weight_key(a[i].0) by {if i==0{}else{assert(i==1);}}
 assert forall|i:int|0<=i<b.len() implies !weight_key(b[i].0) by {assert(i==0);}
}

}
