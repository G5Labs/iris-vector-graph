use vstd::prelude::*;
#[path="../reconstruction/reconstruction.rs"] pub mod old;
#[path="alternate.rs"] pub mod alternate;
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
 Temporal,Other,Redacted,Audit,
}
pub struct Record {pub seq:nat,pub ordinal:nat,pub action:Action}
pub open spec fn rec(a:Action)->Record {Record{seq:1,ordinal:1,action:a}}
pub open spec fn record_redacted(r:Record)->bool {matches!(r.action,Action::Redacted)}
pub open spec fn record_audit(r:Record)->bool {matches!(r.action,Action::Audit)}
pub open spec fn put_node(s:State,id:int,n:Node)->State {State{nodes:s.nodes.insert(id,n),..s}}
pub open spec fn put_rel(s:State,id:int,r:Stmt)->State {State{rels:s.rels.insert(id,r),..s}}
pub open spec fn apply(s:State,r:Record)->State {
 if record_redacted(r) || record_audit(r){s}else{match r.action {
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
pub enum Error {Exists,Missing,Reserved,EmptyKey,MissingAttribute,Incident,Numeric,KeyCarrier,Deleted}
pub struct Reply {pub state:State,pub records:Seq<Record>,pub error:Option<Error>}
pub open spec fn fail(s:State,e:Error)->Reply {Reply{state:s,records:seq![],error:Some(e)}}
pub open spec fn done(s:State,rs:Seq<Record>)->Reply {Reply{state:s,records:rs,error:None}}
// This primitive is the ordinary successful-SQL/default-profile projection.
// Full batch create/upsert expands to these operations, not a supplied node map.
pub open spec fn produce(s:State,o:Op)->Reply {match o {
 Op::CreateNode(id,upsert)=>if s.nodes.contains_key(id){if upsert{done(s,seq![])}else{fail(s,Error::Exists)}}
  else{done(put_node(s,id,empty_node()),seq![rec(Action::CreateNode(id))])},
 Op::AddLabel(id,k)=>if !s.nodes.contains_key(id){fail(s,Error::Missing)}else if k.len()==0{fail(s,Error::EmptyKey)}
  else if s.nodes[id].labels.contains(k){done(s,seq![rec(Action::AddLabel(id,k))])}else{done(put_node(s,id,Node{labels:s.nodes[id].labels.insert(k),..s.nodes[id]}),seq![rec(Action::AddLabel(id,k))])},
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
 requires record_redacted(r) || record_audit(r) || matches!(r.action,Action::Temporal|Action::Other),
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
 ReplaceQuals{ id:int,quals:Seq<(Text,Text)> },DeleteNode{ id:int,detach:bool },
 Primitive(Op),
}
pub struct Store {pub state:State,pub next:nat,pub dead_nodes:Set<int>,pub dead_rels:Set<int>}
pub struct Output {pub store:Store,pub records:Seq<Record>,pub error:Option<Error>}
pub open spec fn node_ops(id:int,labels:Seq<Text>,props:Seq<(Text,Text)>)->Seq<Op> {
 labels.map_values(|k:Text|Op::AddLabel(id,k))+props.map_values(|kv:(Text,Text)|Op::SetProp(id,kv.0,kv.1))
}
pub open spec fn request_ops(g:Store,q:Request)->Seq<Op> {match q {
 Request::Node{id,upsert,labels,props}=>seq![Op::CreateNode(id,upsert)]+node_ops(id,labels,props),
 Request::Rel{s,p,o,raw_graph,upsert,quals}=>{
  let t=tuple(s,p,o,raw_graph);let id=if g.state.by_tuple.contains_key(t){g.state.by_tuple[t]}else{g.next as int};
  seq![Op::CreateRel(id,t,upsert)]+quals.map_values(|kv:(Text,Text)|Op::SetQual(id,kv.0,kv.1))},
 Request::ReplaceQuals{id,quals}=>if !g.state.rels.contains_key(id){seq![Op::DeleteRel(id)]}else{
  let keys=quals.map_values(|kv:(Text,Text)|kv.0);
  let removed=g.state.rels[id].quals.dom().to_seq().filter(|k:Text|!keys.contains(k));
  removed.map_values(|k:Text|Op::RemoveQual(id,k))+quals.map_values(|kv:(Text,Text)|Op::SetQual(id,kv.0,kv.1))},
 Request::DeleteNode{id,detach}=>if detach{
  g.state.rels.dom().to_seq().sort_by(|a:int,b:int|a<=b).filter(|rid:int|g.state.rels[rid].tuple.3.is_none() && (g.state.rels[rid].tuple.0==id || g.state.rels[rid].tuple.2==id)).map_values(|rid:int|Op::DeleteRel(rid))+seq![Op::DeleteNode(id)]
 }else{seq![Op::DeleteNode(id)]},
 Request::Primitive(o)=>seq![o],
}}
pub open spec fn blocked_op(g:Store,o:Op)->bool {match o {
 Op::CreateNode(id,_)|Op::AddLabel(id,_)|Op::RemoveLabel(id,_)|Op::SetProp(id,_,_)|Op::RemoveProp(id,_)|Op::DeleteNode(id)=>g.dead_nodes.contains(id),
 Op::CreateRel(_,t,_)=>g.dead_nodes.contains(t.0) || g.dead_nodes.contains(t.2),
 Op::DeleteRel(id)|Op::SetQual(id,_,_)|Op::RemoveQual(id,_)=>g.dead_rels.contains(id),
}}
pub open spec fn blocked(g:Store,q:Request)->bool {match q {
 Request::Node{id,..}|Request::DeleteNode{id,..}=>g.dead_nodes.contains(id),Request::ReplaceQuals{id,..}=>g.dead_rels.contains(id),Request::Rel{s,o,..}=>g.dead_nodes.contains(s) || g.dead_nodes.contains(o),Request::Primitive(o)=>blocked_op(g,o),
}}
pub open spec fn pre_error(g:Store,q:Request)->Option<Error> {if matches!(q,Request::Rel{..}) && q->Rel_p.len()==0{Some(Error::EmptyKey)}else if blocked(g,q){Some(Error::Deleted)}else{match q {
 Request::Node{id,upsert,props,..}=>if g.state.nodes.contains_key(id) && !upsert{Some(Error::Exists)}
  else if exists|i:int|0<=i<props.len() && reserved(props[i].0){Some(Error::Reserved)}else{None},
 Request::Rel{s,p,o,raw_graph,upsert,quals}=>if !g.state.nodes.contains_key(s) || !g.state.nodes.contains_key(o){Some(Error::Missing)}else if p.len()==0{Some(Error::EmptyKey)}
  else if exists|i:int|0<=i<quals.len() && weight_key(quals[i].0) && !numeric(quals[i].1){Some(Error::Numeric)}
  else if g.state.by_tuple.contains_key(tuple(s,p,o,raw_graph)) && !upsert{Some(Error::Exists)}
  else if exists|i:int|0<=i<quals.len() && quals[i].0.len()==0{Some(Error::KeyCarrier)}else{None},
 Request::ReplaceQuals{id,quals}=>if !g.state.rels.contains_key(id){Some(Error::Missing)}
  else if exists|i:int|0<=i<quals.len() && weight_key(quals[i].0) && !numeric(quals[i].1){Some(Error::Numeric)}
  else if exists|i:int|0<=i<quals.len() && quals[i].0.len()==0{Some(Error::KeyCarrier)}else{None},
 _=>None,
}}}
pub open spec fn allocating(g:Store,q:Request)->bool {match q {
 Request::Rel{s,p,o,raw_graph,..}=>!g.state.by_tuple.contains_key(tuple(s,p,o,raw_graph)),_=>false,
}}
pub open spec fn deleted_nodes(g:Store,q:Request)->Set<int> {match q {Request::DeleteNode{id,..}|Request::Primitive(Op::DeleteNode(id))=>g.dead_nodes.insert(id),_=>g.dead_nodes}}
pub open spec fn deleted_rels(g:Store,q:Request)->Set<int> {match q {
 Request::Primitive(Op::DeleteRel(id))=>g.dead_rels.insert(id),
 Request::DeleteNode{id,detach}=>if detach{g.dead_rels.union(g.state.rels.dom().filter(|rid:int|g.state.rels[rid].tuple.3.is_none() && (g.state.rels[rid].tuple.0==id || g.state.rels[rid].tuple.2==id)))}else{g.dead_rels},_=>g.dead_rels,
}}
pub open spec fn request(g:Store,q:Request)->Output {
 if pre_error(g,q).is_some(){Output{store:g,records:seq![],error:pre_error(g,q)}}else{
  let out=execute(g.state,request_ops(g,q));
  Output{store:Store{state:out.state,next:if out.error.is_none() && allocating(g,q){g.next+1}else{g.next},
   dead_nodes:if out.error.is_none(){deleted_nodes(g,q)}else{g.dead_nodes},
   dead_rels:if out.error.is_none(){deleted_rels(g,q)}else{g.dead_rels}},records:out.records,error:out.error}}
}
pub proof fn theorem_raw_request_full_content(g:Store,q:Request)
 ensures fold(g.state,request(g,q).records)==request(g,q).store.state,
         request(g,q).error.is_some() ==> request(g,q).store.state==g.state && request(g,q).store.next==g.next && request(g,q).records.len()==0,
{theorem_transaction_records_replay_full_content(g.state,request_ops(g,q));}
pub proof fn theorem_new_node_emits_separate_content(g:Store,id:int,k:Text,v:Text,l:Text)
 requires !g.state.nodes.contains_key(id),!g.dead_nodes.contains(id),!reserved(k),k.len()>0,l.len()>0,
 ensures ({let q=Request::Node{id,upsert:false,labels:seq![l],props:seq![(k,v)]};let out=request(g,q);
  out.error.is_none() && out.store.state.nodes.contains_key(id) && out.store.state.rels==g.state.rels && out.store.state.nodes[id].labels==set![l] && out.store.state.nodes[id].props==map![k=>v]
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
pub open spec fn structural(r:Record)->old::Record {old::Record{seq:r.seq,redacted:record_redacted(r),audit:record_audit(r),op:match r.action {
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
 assert forall|k:(bool,int)|#[trigger] project(n).dom().contains(k) <==> out.dom().contains(k) by {
  lemma_project_membership(s,k);lemma_project_membership(n,k);
 }
 assert(project(n).dom() =~= out.dom());
 assert forall|k:(bool,int)|project(n).contains_key(k) implies #[trigger] project(n)[k]==out[k] by {
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

// Native local-array empty subscript rejects before $Order enumeration in the
// separately corroborated provider fragment; direct SetQual has EmptyKey refusal.
pub proof fn theorem_batch_empty_key_carrier_fault(g:Store,s:int,p:Text,o:int,rg:Option<Text>,v:Text)
 requires g.state.nodes.contains_key(s),g.state.nodes.contains_key(o),!g.dead_nodes.contains(s),!g.dead_nodes.contains(o),p.len()>0,
 ensures request(g,Request::Rel{s,p,o,raw_graph:rg,upsert:true,quals:seq![(seq![],v)]}).error==Some(Error::KeyCarrier),
         request(g,Request::Rel{s,p,o,raw_graph:rg,upsert:true,quals:seq![(seq![],v)]}).records.len()==0,
{
 let qs=seq![(seq![],v)];assert(qs[0].0.len()==0);assert(exists|i:int|0<=i<qs.len() && qs[i].0.len()==0);
 assert forall|i:int|0<=i<qs.len() implies !weight_key(qs[i].0) by {assert(i==0);}
}
pub open spec fn requests(g:Store,qs:Seq<Request>)->Output decreases qs.len() {
 if qs.len()==0{Output{store:g,records:seq![],error:None}}else{
  let first=request(g,qs[0]);if first.error.is_some(){Output{store:g,records:seq![],error:first.error}}else{
   let rest=requests(first.store,qs.drop_first());if rest.error.is_some(){Output{store:g,records:seq![],error:rest.error}}
   else{Output{records:first.records+rest.records,..rest}}}}
}
pub open spec fn clear_context(g:Store)->Store {Store{dead_nodes:Set::empty(),dead_rels:Set::empty(),..g}}
pub open spec fn commit(g:Store,qs:Seq<Request>,seq:nat)->Output {
 let w=requests(clear_context(g),qs);if w.error.is_some(){Output{store:g,records:seq![],error:w.error}}
 else{Output{store:clear_context(w.store),records:stamp(w.records,seq,1),error:None}}
}
pub proof fn theorem_requests_full_content(g:Store,qs:Seq<Request>)
 ensures fold(g.state,requests(g,qs).records)==requests(g,qs).store.state,
         requests(g,qs).error.is_some() ==> requests(g,qs).store==g && requests(g,qs).records.len()==0,
 decreases qs.len(),
{
 if qs.len()>0{
  let f=request(g,qs[0]);theorem_raw_request_full_content(g,qs[0]);
  if f.error.is_none(){theorem_requests_full_content(f.store,qs.drop_first());lemma_fold_concat(g.state,f.records,requests(f.store,qs.drop_first()).records);}
 }
}
pub proof fn theorem_committed_revision_full_content(g:Store,qs:Seq<Request>,seq:nat)
 ensures fold(g.state,commit(g,qs,seq).records)==commit(g,qs,seq).store.state,
         commit(g,qs,seq).error.is_some() ==> commit(g,qs,seq).store==g && commit(g,qs,seq).records.len()==0,
         forall|i:int|0<=i<commit(g,qs,seq).records.len() ==> commit(g,qs,seq).records[i].seq==seq && commit(g,qs,seq).records[i].ordinal==i+1,
{theorem_requests_full_content(clear_context(g),qs);theorem_stamping_preserves_full_content(g.state,requests(clear_context(g),qs).records,seq,1);}
pub proof fn theorem_deleted_context_precedes_reserved(g:Store,id:int,v:Text)
 requires g.dead_nodes.contains(id),
 ensures request(g,Request::Primitive(Op::SetProp(id,seq!['i','d'],v))).error==Some(Error::Deleted),
{}
pub proof fn theorem_new_revision_resets_deletion_context(g:Store,id:int)
 requires !g.state.nodes.contains_key(id),
 ensures commit(g,seq![Request::Node{id,upsert:false,labels:seq![],props:seq![]}],1).error.is_none(),
{reveal_with_fuel(requests,3);reveal_with_fuel(execute,3);}
pub open spec fn physical_exists(regs:Set<(Option<Text>,int)>,id:int)->bool {exists|g:Option<Text>|regs.contains((g,id))}
pub open spec fn physical_create_refused(regs:Set<(Option<Text>,int)>,id:int)->bool {physical_exists(regs,id)}
pub proof fn theorem_named_registration_refuses_create_after_default_delete(s:State,regs:Set<(Option<Text>,int)>,id:int,g:Text)
 requires regs.contains((Some(g),id)),
 ensures !apply(s,rec(Action::DeleteNode{id,snapshot:empty_node()})).nodes.contains_key(id),
         physical_create_refused(regs.remove((None,id)),id),
{assert(regs.remove((None,id)).contains((Some(g),id)));assert(exists|gg:Option<Text>|regs.remove((None,id)).contains((gg,id)));}

pub type Field=(nat,int,Text); // label / property / qualifier, then entity id/key
pub type AttrDelta=Map<Field,(Option<Text>,Option<Text>)>;
pub open spec fn field(s:State,f:Field)->Option<Text> {
 if f.0==0{if s.nodes.contains_key(f.1) && s.nodes[f.1].labels.contains(f.2){Some(seq![])}else{None}}
 else if f.0==1{if s.nodes.contains_key(f.1){value(s.nodes[f.1].props,f.2)}else{None}}
 else if f.0==2{if s.rels.contains_key(f.1){value(s.rels[f.1].quals,f.2)}else{None}}else{None}
}
pub open spec fn attr_record(r:Record)->Option<(Field,Option<Text>,Option<Text>)> {if record_redacted(r) || record_audit(r){None}else{match r.action {
 Action::AddLabel(id,k)=>Some(((0nat,id,k),None,Some(seq![]))),Action::RemoveLabel(id,k)=>Some(((0nat,id,k),Some(seq![]),None)),
 Action::SetProp{id,key,prior,new}=>Some(((1nat,id,key),prior,new)),Action::RemoveProp{id,key,prior}=>Some(((1nat,id,key),Some(prior),None)),
 Action::SetQual{id,key,prior,new}=>Some(((2nat,id,key),prior,new)),Action::RemoveQual{id,key,prior}=>Some(((2nat,id,key),Some(prior),None)),_=>None,
}}}
pub open spec fn attr_track(d:AttrDelta,r:Record)->AttrDelta {
 let a=attr_record(r);if a.is_none(){d}else{let (k,b,n)=a.unwrap();d.insert(k,(if d.contains_key(k){d[k].0}else{b},n))}
}
pub open spec fn attr_scan(d:AttrDelta,rs:Seq<Record>)->AttrDelta decreases rs.len() {
 if rs.len()==0{d}else{attr_scan(attr_track(d,rs[0]),rs.drop_first())}
}
pub open spec fn changed(d:AttrDelta)->AttrDelta {Map::new(d.dom().filter(|f:Field|d[f].0!=d[f].1),|f:Field|d[f])}
pub open spec fn aligned(initial:State,current:State,d:AttrDelta)->bool {
 forall|f:Field|if d.contains_key(f){d[f].0==field(initial,f) && d[f].1==field(current,f)}else{field(initial,f)==field(current,f)}
}
pub open spec fn valid_attr_step(s:State,r:Record)->bool {
 let a=attr_record(r);
 a.is_some() && field(s,a.unwrap().0)==a.unwrap().1 && field(apply(s,r),a.unwrap().0)==a.unwrap().2
 && forall|f:Field|f!=a.unwrap().0 ==> field(s,f)==field(apply(s,r),f)
}
pub open spec fn attr_op(o:Op)->bool {match o {Op::AddLabel(_,_)|Op::RemoveLabel(_,_)|Op::SetProp(_,_,_)|Op::RemoveProp(_,_)|Op::SetQual(_,_,_)|Op::RemoveQual(_,_)=>true,_=>false}}
pub proof fn theorem_attribute_producer_step(s:State,o:Op)
 requires attr_op(o),
 ensures produce(s,o).records.len()<=1,
         produce(s,o).records.len()==1 ==> valid_attr_step(s,produce(s,o).records[0]),
         produce(s,o).records.len()==0 ==> produce(s,o).state==s,
{
 let rs=produce(s,o).records;
 if rs.len()==1{
  let r=rs[0];let a=attr_record(r).unwrap();
  assert forall|f:Field|f!=a.0 implies field(s,f)==field(apply(s,r),f) by {}
 }
}
pub proof fn lemma_attribute_alignment_step(initial:State,current:State,d:AttrDelta,r:Record)
 requires aligned(initial,current,d),valid_attr_step(current,r),
 ensures aligned(initial,apply(current,r),attr_track(d,r)),
{
 let a=attr_record(r).unwrap();
 assert forall|f:Field|if attr_track(d,r).contains_key(f){attr_track(d,r)[f].0==field(initial,f) && attr_track(d,r)[f].1==field(apply(current,r),f)}else{field(initial,f)==field(apply(current,r),f)} by {
  if f==a.0{}else{}
 }
}
pub proof fn lemma_attr_scan_concat(d:AttrDelta,a:Seq<Record>,b:Seq<Record>)
 ensures attr_scan(d,a+b)==attr_scan(attr_scan(d,a),b),
 decreases a.len(),
{
 if a.len()>0{lemma_attr_scan_concat(attr_track(d,a[0]),a.drop_first(),b);assert((a+b).drop_first() =~= a.drop_first()+b);}
}
pub proof fn theorem_continuous_alignment(initial:State,current:State,d:AttrDelta,ops:Seq<Op>)
 requires aligned(initial,current,d),forall|i:int|0<=i<ops.len() ==> attr_op(ops[i]),execute(current,ops).error.is_none(),
 ensures aligned(initial,execute(current,ops).state,attr_scan(d,execute(current,ops).records)),
 decreases ops.len(),
{
 if ops.len()>0{
  let f=produce(current,ops[0]);let rest=ops.drop_first();theorem_attribute_producer_step(current,ops[0]);theorem_primitive_records_replay_full_content(current,ops[0]);
  assert forall|i:int|0<=i<rest.len() implies attr_op(rest[i]) by {assert(rest[i]==ops[i+1]);}
  if f.records.len()==1{
   lemma_attribute_alignment_step(initial,current,d,f.records[0]);
   assert(f.records =~= seq![f.records[0]]);reveal_with_fuel(fold,3);reveal_with_fuel(attr_scan,3);
  }else{assert(f.records =~= seq![]);}
  theorem_continuous_alignment(initial,f.state,attr_scan(d,f.records),rest);
  lemma_attr_scan_concat(d,f.records,execute(f.state,rest).records);
 }
}
pub proof fn theorem_continuous_full_content_endpoint_diff(s:State,ops:Seq<Op>)
 requires forall|i:int|0<=i<ops.len() ==> attr_op(ops[i]),
 ensures ({let out=execute(s,ops);let d=changed(attr_scan(Map::empty(),out.records));
  forall|f:Field|d.contains_key(f)==(field(s,f)!=field(out.state,f))
   && (d.contains_key(f) ==> d[f]==(field(s,f),field(out.state,f)))}),
{
 let out=execute(s,ops);let scan=attr_scan(Map::empty(),out.records);let d=changed(scan);
 assert(aligned(s,s,Map::empty()));
 if out.error.is_none(){theorem_continuous_alignment(s,s,Map::empty(),ops);}
 else{theorem_transaction_records_replay_full_content(s,ops);}
 assert forall|f:Field|d.contains_key(f)==(field(s,f)!=field(out.state,f)) && (d.contains_key(f) ==> d[f]==(field(s,f),field(out.state,f))) by {}
}

pub enum View {Node{id:int,labels:Set<Text>,props:Map<Text,Text>},Rel{id:int,tuple:Tuple,quals:Map<Text,Text>}}
pub open spec fn entities(s:State)->Map<(bool,int),View> {Map::new(project(s).dom(),|k:(bool,int)|if k.0{View::Rel{id:k.1,tuple:s.rels[k.1].tuple,quals:s.rels[k.1].quals}}else{View::Node{id:k.1,labels:s.nodes[k.1].labels,props:s.nodes[k.1].props}})}
pub open spec fn stream_entities(s:State)->Seq<((bool,int),View)> {
 let m=entities(s);m.dom().to_seq().map_values(|k:(bool,int)|(k,m[k]))
}
pub proof fn theorem_export_preserves_complete_fields(s:State,id:int)
 ensures s.nodes.contains_key(id) ==> entities(s)[(false,id)]==(View::Node{id,labels:s.nodes[id].labels,props:s.nodes[id].props}),
         s.rels.contains_key(id) ==> entities(s)[(true,id)]==(View::Rel{id,tuple:s.rels[id].tuple,quals:s.rels[id].quals}),
{lemma_project_membership(s,(false,id));lemma_project_membership(s,(true,id));}
pub proof fn theorem_stream_exact_entity_reader(s:State,k:(bool,int))
 ensures stream_entities(s).len()==entity_count(s),
         entities(s).contains_key(k) ==> stream_entities(s).contains((k,entities(s)[k])),
{
 theorem_entity_count_projection(s);let m=entities(s);let keys=m.dom().to_seq();m.dom().lemma_to_seq_len();m.dom().lemma_to_seq_to_set_id();
 if m.contains_key(k){assert(keys.contains(k));let i=choose|i:int|0<=i<keys.len() && keys[i]==k;
  assert(stream_entities(s)[i]==(k,m[k]));assert(stream_entities(s).contains((k,m[k])));}
}
pub open spec fn comparable(s:State,ids:Seq<int>,out:Map<Tuple,(int,Map<Text,Text>)>)->Map<Tuple,(int,Map<Text,Text>)> decreases ids.len() {
 if ids.len()==0{out}else{let id=ids[0];comparable(s,ids.drop_first(),if s.rels.contains_key(id){out.insert(s.rels[id].tuple,(id,s.rels[id].quals))}else{out})}
}
pub proof fn theorem_duplicate_tuple_views_remain_distinct(t:Tuple,a:int,b:int)
 requires a!=b,
 ensures ({let s=fold(empty(),seq![rec(Action::CreateRel(a,t)),rec(Action::CreateRel(b,t))]);
  s.rels.contains_key(a) && s.rels.contains_key(b) && s.by_tuple[t]==b
  && entities(s).contains_key((true,a)) && entities(s).contains_key((true,b))
  && comparable(s,seq![a,b],Map::empty())==map![t=>(b,Map::<Text,Text>::empty())]
  && ({let d=apply(s,rec(Action::DeleteRel{id:a,snapshot:s.rels[a]}));d.rels.contains_key(b) && !d.by_tuple.contains_key(t)
       && comparable(d,seq![b],Map::empty())==map![t=>(b,Map::<Text,Text>::empty())]})}),
{
 reveal_with_fuel(fold,4);reveal_with_fuel(comparable,4);
 let s=fold(empty(),seq![rec(Action::CreateRel(a,t)),rec(Action::CreateRel(b,t))]);
 lemma_project_membership(s,(true,a));lemma_project_membership(s,(true,b));
}
pub open spec fn decode_nullable(cell:Option<Text>,null_flag:bool)->Option<Text> {if null_flag{None}else{Some(text(cell))}}
pub enum InputValue {Null,Text(Text),Boolean(bool),NumberText(Text),NestedText(Text),Unsupported}
pub open spec fn public_value(v:InputValue)->Option<Text> {match v {InputValue::Text(t)|InputValue::NumberText(t)=>Some(t),InputValue::Boolean(b)=>Some(if b{seq!['t','r','u','e']}else{seq!['f','a','l','s','e']}),_=>None}}
pub open spec fn parsed_qual(v:InputValue)->Option<Text> {match v {InputValue::NestedText(t)=>Some(t),_=>public_value(v)}}
pub proof fn theorem_null_text_and_public_value_boundaries()
 ensures decode_nullable(None,false)==Some(seq![]),decode_nullable(Some(seq![]),true)==None,
         decode_nullable(Some(seq!['n','u','l','l']),false)==Some(seq!['n','u','l','l']),
         public_value(InputValue::Null)==None,public_value(InputValue::NestedText(seq!['{','}']))==None,
         parsed_qual(InputValue::Null)==None,parsed_qual(InputValue::NestedText(seq!['{','}']))==Some(seq!['{','}']),
{}
pub open spec fn allocation_frame(g:Store)->bool {g.next>0 && forall|id:int|g.state.rels.contains_key(id) ==> 0<id<g.next}
pub proof fn theorem_raw_new_rel_uses_own_fresh_counter(g:Store,a:int,p:Text,b:int,rg:Option<Text>)
 requires allocation_frame(g),g.state.nodes.contains_key(a),g.state.nodes.contains_key(b),!g.dead_nodes.contains(a),!g.dead_nodes.contains(b),p.len()>0,!g.state.by_tuple.contains_key(tuple(a,p,b,rg)),
 ensures ({let out=request(g,Request::Rel{s:a,p,o:b,raw_graph:rg,upsert:false,quals:seq![]});
   out.error.is_none() && out.store.next==g.next+1 && out.store.state.rels.contains_key(g.next as int)
   && out.records==seq![rec(Action::CreateRel(g.next as int,tuple(a,p,b,rg))) ]
   && !g.state.rels.contains_key(g.next as int)}),
{reveal_with_fuel(execute,3);}

pub open spec fn record_seq(r:Record)->nat {r.seq}
pub proof fn lemma_named_concat(s:State,a:Seq<Record>,b:Seq<Record>,through:nat)
 ensures named_fold(s,a+b,through)==named_fold(named_fold(s,a,through),b,through),
 decreases a.len(),
{if a.len()>0{lemma_named_concat(next(s,a[0],through),a.drop_first(),b,through);assert((a+b).drop_first() =~= a.drop_first()+b);}}
pub proof fn lemma_named_all(s:State,rs:Seq<Record>,through:nat)
 requires forall|i:int|0<=i<rs.len() ==> 1<=#[trigger] record_seq(rs[i])<=through,
 ensures named_fold(s,rs,through)==fold(s,rs),
 decreases rs.len(),
{
 if rs.len()>0{
  assert forall|i:int|0<=i<rs.drop_first().len() implies 1<=#[trigger] record_seq(rs.drop_first()[i])<=through by {assert(rs.drop_first()[i]==rs[i+1]);}
  assert(1<=record_seq(rs[0])<=through);assert(selected(rs[0],through));
  lemma_named_all(apply(s,rs[0]),rs.drop_first(),through);
 }
}
pub proof fn lemma_named_none(s:State,rs:Seq<Record>,through:nat)
 requires forall|i:int|0<=i<rs.len() ==> #[trigger] record_seq(rs[i])>through,
 ensures named_fold(s,rs,through)==s,
 decreases rs.len(),
{
 if rs.len()>0{
  assert forall|i:int|0<=i<rs.drop_first().len() implies #[trigger] record_seq(rs.drop_first()[i])>through by {assert(rs.drop_first()[i]==rs[i+1]);}
  assert(record_seq(rs[0])>through);assert(!selected(rs[0],through));
  lemma_named_none(s,rs.drop_first(),through);
 }
}
pub open spec fn range_attrs(d:AttrDelta,rs:Seq<Record>,lo:nat,hi:nat)->AttrDelta decreases rs.len() {
 if rs.len()==0{d}else{range_attrs(if lo<rs[0].seq<=hi{attr_track(d,rs[0])}else{d},rs.drop_first(),lo,hi)}
}
pub proof fn lemma_range_concat(d:AttrDelta,a:Seq<Record>,b:Seq<Record>,lo:nat,hi:nat)
 ensures range_attrs(d,a+b,lo,hi)==range_attrs(range_attrs(d,a,lo,hi),b,lo,hi),
 decreases a.len(),
{if a.len()>0{lemma_range_concat(if lo<a[0].seq<=hi{attr_track(d,a[0])}else{d},a.drop_first(),b,lo,hi);assert((a+b).drop_first() =~= a.drop_first()+b);}}
pub proof fn lemma_range_none(d:AttrDelta,rs:Seq<Record>,lo:nat,hi:nat)
 requires forall|i:int|0<=i<rs.len() ==> #[trigger] record_seq(rs[i])<=lo,
 ensures range_attrs(d,rs,lo,hi)==d,
 decreases rs.len(),
{
 if rs.len()>0{
  assert forall|i:int|0<=i<rs.drop_first().len() implies #[trigger] record_seq(rs.drop_first()[i])<=lo by {assert(rs.drop_first()[i]==rs[i+1]);}
  assert(record_seq(rs[0])<=lo);
  lemma_range_none(d,rs.drop_first(),lo,hi);
 }
}
pub proof fn lemma_range_stamped(d:AttrDelta,rs:Seq<Record>,lo:nat,hi:nat,start:nat)
 requires lo<hi,
 ensures range_attrs(d,stamp(rs,hi,start),lo,hi)==attr_scan(d,rs),
 decreases rs.len(),
{
 if rs.len()>0{
  assert(stamp(rs,hi,start).drop_first() =~= stamp(rs.drop_first(),hi,start+1));
  lemma_range_stamped(attr_track(d,rs[0]),rs.drop_first(),lo,hi,start+1);
 }
}
pub proof fn theorem_named_generated_full_content_endpoints(base:Seq<Record>,ops:Seq<Op>,lo:nat,hi:nat)
 requires lo<hi,forall|i:int|0<=i<base.len() ==> 1<=#[trigger] record_seq(base[i])<=lo,
          forall|i:int|0<=i<ops.len() ==> attr_op(ops[i]),
          execute(fold(empty(),base),ops).error.is_none(),
 ensures ({let before=fold(empty(),base);let out=execute(before,ops);let hist=base+stamp(out.records,hi,1);
  named_fold(empty(),hist,lo)==before && named_fold(empty(),hist,hi)==out.state
  && ({let d=changed(range_attrs(Map::empty(),hist,lo,hi));forall|f:Field|
   d.contains_key(f)==(field(named_fold(empty(),hist,lo),f)!=field(named_fold(empty(),hist,hi),f))
   && (d.contains_key(f) ==> d[f]==(field(named_fold(empty(),hist,lo),f),field(named_fold(empty(),hist,hi),f)))})}),
{
 let before=fold(empty(),base);let out=execute(before,ops);let generated=stamp(out.records,hi,1);let hist=base+generated;
 theorem_transaction_records_replay_full_content(before,ops);theorem_continuous_full_content_endpoint_diff(before,ops);
 lemma_named_concat(empty(),base,generated,lo);lemma_named_concat(empty(),base,generated,hi);lemma_named_all(empty(),base,lo);lemma_named_all(empty(),base,hi);
 assert forall|i:int|0<=i<generated.len() implies 1<=#[trigger] record_seq(generated[i])<=hi && record_seq(generated[i])>lo by {}
 lemma_named_none(before,generated,lo);lemma_named_all(before,generated,hi);theorem_stamping_preserves_full_content(before,out.records,hi,1);
 lemma_range_concat(Map::empty(),base,generated,lo,hi);lemma_range_none(Map::empty(),base,lo,hi);lemma_range_stamped(Map::empty(),out.records,lo,hi,1);
}

pub open spec fn default_request(q:Request)->bool {match q {
 Request::Rel{raw_graph,..}=>graph(raw_graph).is_none(),
 Request::Primitive(Op::CreateRel(_,_,_))=>false,_=>true,
}}
pub open spec fn default_batches(batches:Seq<Seq<Request>>)->bool {
 forall|i:int,j:int|0<=i<batches.len() && 0<=j<batches[i].len() ==> default_request(batches[i][j])
}
pub struct History {pub store:Store,pub log:Seq<Record>,pub next_seq:nat}
pub open spec fn history(g:Store,batches:Seq<Seq<Request>>,seq:nat)->History decreases batches.len() {
 if batches.len()==0{History{store:g,log:seq![],next_seq:seq}}else{
  let now=commit(g,batches[0],seq);let rest=history(now.store,batches.drop_first(),if now.error.is_none(){seq+1}else{seq});
  History{log:now.records+rest.log,..rest}}
}
pub proof fn theorem_history_full_content_from_its_records(g:Store,batches:Seq<Seq<Request>>,seq:nat)
 ensures fold(g.state,history(g,batches,seq).log)==history(g,batches,seq).store.state,
 decreases batches.len(),
{
 if batches.len()>0{
  let now=commit(g,batches[0],seq);let n=if now.error.is_none(){seq+1}else{seq};theorem_committed_revision_full_content(g,batches[0],seq);
  theorem_history_full_content_from_its_records(now.store,batches.drop_first(),n);
  lemma_fold_concat(g.state,now.records,history(now.store,batches.drop_first(),n).log);
 }
}
pub open spec fn initial_store()->Store {Store{state:empty(),next:1,dead_nodes:Set::empty(),dead_rels:Set::empty()}}
pub proof fn theorem_closed_default_ordinary_history(batches:Seq<Seq<Request>>)
 requires default_batches(batches),
 ensures fold(empty(),history(initial_store(),batches,2).log)==history(initial_store(),batches,2).store.state,
{theorem_history_full_content_from_its_records(initial_store(),batches,2);}

pub open spec fn coherent(s:State)->bool {
 (forall|id:int|s.rels.contains_key(id) ==> s.by_tuple.contains_key(s.rels[id].tuple) && s.by_tuple[s.rels[id].tuple]==id)
 && (forall|t:Tuple|s.by_tuple.contains_key(t) ==> s.rels.contains_key(s.by_tuple[t]) && s.rels[s.by_tuple[t]].tuple==t)
}
pub open spec fn ids_below(s:State,limit:nat)->bool {forall|id:int|s.rels.contains_key(id) ==> 0<id<limit}
pub open spec fn creation_below(o:Op,limit:nat)->bool {match o {Op::CreateRel(id,_,_)=>0<id<limit,_=>true}}
pub open spec fn fresh_creation(s:State,o:Op)->bool {match o {Op::CreateRel(id,t,_)=>s.by_tuple.contains_key(t) || !s.rels.contains_key(id),_=>true}}
pub proof fn lemma_primitive_id_bound(s:State,o:Op,limit:nat)
 requires ids_below(s,limit),creation_below(o,limit),
 ensures ids_below(produce(s,o).state,limit),
{
 assert forall|id:int|produce(s,o).state.rels.contains_key(id) implies 0<id<limit by {}
}
pub proof fn lemma_primitive_tuple_index(s:State,o:Op)
 requires coherent(s),fresh_creation(s,o),
 ensures coherent(produce(s,o).state),
{
 let n=produce(s,o).state;
 assert forall|id:int|n.rels.contains_key(id) implies n.by_tuple.contains_key(n.rels[id].tuple) && n.by_tuple[n.rels[id].tuple]==id by {}
 assert forall|t:Tuple|n.by_tuple.contains_key(t) implies n.rels.contains_key(n.by_tuple[t]) && n.rels[n.by_tuple[t]].tuple==t by {}
}
pub proof fn lemma_execute_id_bound(s:State,ops:Seq<Op>,limit:nat)
 requires ids_below(s,limit),forall|i:int|0<=i<ops.len() ==> creation_below(ops[i],limit),
 ensures ids_below(execute(s,ops).state,limit),
 decreases ops.len(),
{
 if ops.len()>0{
  let f=produce(s,ops[0]);lemma_primitive_id_bound(s,ops[0],limit);
  assert forall|i:int|0<=i<ops.drop_first().len() implies creation_below(ops.drop_first()[i],limit) by {assert(ops.drop_first()[i]==ops[i+1]);}
  if f.error.is_none(){lemma_execute_id_bound(f.state,ops.drop_first(),limit);}
 }
}
pub open spec fn noncreating(o:Op)->bool {!matches!(o,Op::CreateRel(_,_,_))}
pub proof fn lemma_noncreating_execute_index(s:State,ops:Seq<Op>)
 requires coherent(s),forall|i:int|0<=i<ops.len() ==> noncreating(ops[i]),
 ensures coherent(execute(s,ops).state),
 decreases ops.len(),
{
 if ops.len()>0{
  let f=produce(s,ops[0]);lemma_primitive_tuple_index(s,ops[0]);
  assert forall|i:int|0<=i<ops.drop_first().len() implies noncreating(ops.drop_first()[i]) by {assert(ops.drop_first()[i]==ops[i+1]);}
  if f.error.is_none(){lemma_noncreating_execute_index(f.state,ops.drop_first());}
 }
}
pub proof fn theorem_request_preserves_ordinary_identity_frame(g:Store,q:Request)
 requires coherent(g.state),allocation_frame(g),default_request(q),
 ensures coherent(request(g,q).store.state),allocation_frame(request(g,q).store),
{
 if pre_error(g,q).is_none(){
  let ops=request_ops(g,q);let limit=if allocating(g,q){g.next+1}else{g.next};
  assert(ids_below(g.state,limit));
  match q {
   Request::Rel{s,p,o,raw_graph,upsert,quals}=>{
    let t=tuple(s,p,o,raw_graph);let id=if g.state.by_tuple.contains_key(t){g.state.by_tuple[t]}else{g.next as int};
    assert(fresh_creation(g.state,Op::CreateRel(id,t,upsert)));let head=produce(g.state,Op::CreateRel(id,t,upsert));lemma_primitive_tuple_index(g.state,Op::CreateRel(id,t,upsert));
    assert forall|i:int|0<=i<ops.drop_first().len() implies noncreating(ops.drop_first()[i]) by {}
    if head.error.is_none(){lemma_noncreating_execute_index(head.state,ops.drop_first());}
   },_=>{
    assert forall|i:int|0<=i<ops.len() implies noncreating(ops[i]) by {}
    lemma_noncreating_execute_index(g.state,ops);
   },
  }
  assert forall|i:int|0<=i<ops.len() implies creation_below(ops[i],limit) by {}
  lemma_execute_id_bound(g.state,ops,limit);
 }
}

pub open spec fn default_state(s:State)->bool {forall|id:int|s.rels.contains_key(id) ==> s.rels[id].tuple.3.is_none()}
pub open spec fn default_creation(o:Op)->bool {match o {Op::CreateRel(_,t,_)=>t.3.is_none(),_=>true}}
pub proof fn lemma_default_primitive(s:State,o:Op)
 requires default_state(s),default_creation(o),
 ensures default_state(produce(s,o).state),
{assert forall|id:int|produce(s,o).state.rels.contains_key(id) implies produce(s,o).state.rels[id].tuple.3.is_none() by {}}
pub proof fn lemma_default_execute(s:State,ops:Seq<Op>)
 requires default_state(s),forall|i:int|0<=i<ops.len() ==> default_creation(ops[i]),
 ensures default_state(execute(s,ops).state),
 decreases ops.len(),
{
 if ops.len()>0{
  let f=produce(s,ops[0]);lemma_default_primitive(s,ops[0]);
  assert forall|i:int|0<=i<ops.drop_first().len() implies default_creation(ops.drop_first()[i]) by {assert(ops.drop_first()[i]==ops[i+1]);}
  if f.error.is_none(){lemma_default_execute(f.state,ops.drop_first());}
 }
}
pub open spec fn producer_frame(g:Store)->bool {coherent(g.state) && allocation_frame(g) && default_state(g.state)}
pub proof fn theorem_request_full_identity_default_frame(g:Store,q:Request)
 requires producer_frame(g),default_request(q),
 ensures producer_frame(request(g,q).store),
{
 theorem_request_preserves_ordinary_identity_frame(g,q);
 if pre_error(g,q).is_none(){
  assert forall|i:int|0<=i<request_ops(g,q).len() implies default_creation(request_ops(g,q)[i]) by {}
  lemma_default_execute(g.state,request_ops(g,q));
 }
}
pub proof fn theorem_revision_preserves_closed_frame(g:Store,qs:Seq<Request>)
 requires producer_frame(g),forall|i:int|0<=i<qs.len() ==> default_request(qs[i]),
 ensures producer_frame(requests(g,qs).store),
 decreases qs.len(),
{
 if qs.len()>0{
  theorem_request_full_identity_default_frame(g,qs[0]);
  assert forall|i:int|0<=i<qs.drop_first().len() implies default_request(qs.drop_first()[i]) by {assert(qs.drop_first()[i]==qs[i+1]);}
  theorem_revision_preserves_closed_frame(request(g,qs[0]).store,qs.drop_first());
 }
}
pub proof fn theorem_history_inductive_ordinary_frame(g:Store,batches:Seq<Seq<Request>>,seq:nat)
 requires producer_frame(g),default_batches(batches),
 ensures producer_frame(history(g,batches,seq).store),
 decreases batches.len(),
{
 if batches.len()>0{
  assert forall|j:int|0<=j<batches[0].len() implies default_request(batches[0][j]) by {}
  theorem_revision_preserves_closed_frame(clear_context(g),batches[0]);
  assert(producer_frame(commit(g,batches[0],seq).store));
  assert(default_batches(batches.drop_first())) by {
   assert forall|i:int,j:int|0<=i<batches.drop_first().len() && 0<=j<batches.drop_first()[i].len() implies default_request(batches.drop_first()[i][j]) by {assert(batches.drop_first()[i]==batches[i+1]);}
  }
  let now=commit(g,batches[0],seq);theorem_history_inductive_ordinary_frame(now.store,batches.drop_first(),if now.error.is_none(){seq+1}else{seq});
 }
}
pub proof fn theorem_closed_default_producer_reader(batches:Seq<Seq<Request>>)
 requires default_batches(batches),
 ensures producer_frame(history(initial_store(),batches,2).store),
         fold(empty(),history(initial_store(),batches,2).log)==history(initial_store(),batches,2).store.state,
{
 assert(producer_frame(initial_store()));theorem_history_inductive_ordinary_frame(initial_store(),batches,2);theorem_closed_default_ordinary_history(batches);
}

pub open spec fn node_shape(n:Node)->bool {
 (forall|k:Text|#[trigger] n.labels.contains(k) ==> k.len()>0) && (forall|k:Text|#[trigger] n.props.contains_key(k) ==> (k.len()>0 && !reserved(k)))
}
pub open spec fn rel_shape(r:Stmt)->bool {r.tuple.1.len()>0 && forall|k:Text|r.quals.contains_key(k) ==> k.len()>0}
pub open spec fn wellformed(s:State)->bool {
 (forall|id:int|s.nodes.contains_key(id) ==> node_shape(s.nodes[id]))
 && (forall|id:int|s.rels.contains_key(id) ==> rel_shape(s.rels[id]) && s.nodes.contains_key(s.rels[id].tuple.0) && s.nodes.contains_key(s.rels[id].tuple.2))
}
pub proof fn lemma_node_shape_field(n:Node,k:Text)
 requires node_shape(n),
 ensures n.labels.contains(k) ==> k.len()>0,n.props.contains_key(k) ==> (k.len()>0 && !reserved(k)),
{}
pub proof fn lemma_primitive_content_shape(s:State,o:Op)
 requires wellformed(s),default_state(s),default_creation(o),
 ensures wellformed(produce(s,o).state),
{
 let n=produce(s,o).state;
 assert forall|id:int|n.nodes.contains_key(id) implies node_shape(n.nodes[id]) by {
  assert forall|k:Text|n.nodes[id].labels.contains(k) implies k.len()>0 by {}
  assert forall|k:Text|n.nodes[id].props.contains_key(k) implies k.len()>0 && !reserved(k) by {if s.nodes.contains_key(id){lemma_node_shape_field(s.nodes[id],k);}}
 }
 assert forall|id:int|n.rels.contains_key(id) implies rel_shape(n.rels[id]) && n.nodes.contains_key(n.rels[id].tuple.0) && n.nodes.contains_key(n.rels[id].tuple.2) by {
  assert forall|k:Text|n.rels[id].quals.contains_key(k) implies k.len()>0 by {}
  match o {Op::DeleteNode(x)=>{
   if s.rels.contains_key(id) && (s.rels[id].tuple.0==x || s.rels[id].tuple.2==x){
    assert(exists|rid:int|s.rels.contains_key(rid) && s.rels[rid].tuple.3.is_none() && (s.rels[rid].tuple.0==x || s.rels[rid].tuple.2==x));
   }
  },_=>{}}
 }
}
pub proof fn lemma_execute_content_shape(s:State,ops:Seq<Op>)
 requires wellformed(s),default_state(s),forall|i:int|0<=i<ops.len() ==> default_creation(ops[i]),
 ensures wellformed(execute(s,ops).state),
 decreases ops.len(),
{
 if ops.len()>0{
  let f=produce(s,ops[0]);lemma_primitive_content_shape(s,ops[0]);lemma_default_primitive(s,ops[0]);
  assert forall|i:int|0<=i<ops.drop_first().len() implies default_creation(ops.drop_first()[i]) by {assert(ops.drop_first()[i]==ops[i+1]);}
  if f.error.is_none(){lemma_execute_content_shape(f.state,ops.drop_first());}
 }
}
pub proof fn theorem_request_preserves_full_content_frame(g:Store,q:Request)
 requires producer_frame(g),wellformed(g.state),default_request(q),
 ensures producer_frame(request(g,q).store),wellformed(request(g,q).store.state),
{
 theorem_request_full_identity_default_frame(g,q);
 if pre_error(g,q).is_none(){
  assert forall|i:int|0<=i<request_ops(g,q).len() implies default_creation(request_ops(g,q)[i]) by {}
  lemma_execute_content_shape(g.state,request_ops(g,q));
 }
}
pub proof fn theorem_revision_full_content_frame(g:Store,qs:Seq<Request>)
 requires producer_frame(g),wellformed(g.state),forall|i:int|0<=i<qs.len() ==> default_request(qs[i]),
 ensures producer_frame(requests(g,qs).store),wellformed(requests(g,qs).store.state),
 decreases qs.len(),
{
 if qs.len()>0{
  theorem_request_preserves_full_content_frame(g,qs[0]);
  assert forall|i:int|0<=i<qs.drop_first().len() implies default_request(qs.drop_first()[i]) by {assert(qs.drop_first()[i]==qs[i+1]);}
  theorem_revision_full_content_frame(request(g,qs[0]).store,qs.drop_first());
 }
}
pub proof fn theorem_history_full_inductive_frame(g:Store,batches:Seq<Seq<Request>>,seq:nat)
 requires producer_frame(g),wellformed(g.state),default_batches(batches),
 ensures producer_frame(history(g,batches,seq).store),wellformed(history(g,batches,seq).store.state),
 decreases batches.len(),
{
 if batches.len()>0{
  assert forall|j:int|0<=j<batches[0].len() implies default_request(batches[0][j]) by {}
  theorem_revision_full_content_frame(clear_context(g),batches[0]);
  assert(producer_frame(commit(g,batches[0],seq).store));assert(wellformed(commit(g,batches[0],seq).store.state));
  assert(default_batches(batches.drop_first())) by {
   assert forall|i:int,j:int|0<=i<batches.drop_first().len() && 0<=j<batches.drop_first()[i].len() implies default_request(batches.drop_first()[i][j]) by {assert(batches.drop_first()[i]==batches[i+1]);}
  }
  let now=commit(g,batches[0],seq);theorem_history_full_inductive_frame(now.store,batches.drop_first(),if now.error.is_none(){seq+1}else{seq});
 }
}
pub proof fn theorem_closed_default_full_workflow(batches:Seq<Seq<Request>>)
 requires default_batches(batches),
 ensures producer_frame(history(initial_store(),batches,2).store),wellformed(history(initial_store(),batches,2).store.state),
         fold(empty(),history(initial_store(),batches,2).log)==history(initial_store(),batches,2).store.state,
{
 assert(wellformed(empty()));assert(producer_frame(initial_store()));theorem_history_full_inductive_frame(initial_store(),batches,2);theorem_closed_default_ordinary_history(batches);
}

pub open spec fn temporal_key(k:Text)->bool {k==seq!['t','e','m','p','o','r','a','l']}
pub open spec fn safe_qual(k:Text,v:Text)->bool {!(temporal_key(k) && v==seq!['t','r','u','e'])}
pub open spec fn safe_pairs(ps:Seq<(Text,Text)>)->bool {forall|i:int|0<=i<ps.len() ==> safe_qual(ps[i].0,ps[i].1)}
pub open spec fn safe_op(o:Op)->bool {match o {Op::SetQual(_,k,v)=>safe_qual(k,v),_=>true}}
pub open spec fn ordinary_request(q:Request)->bool {default_request(q) && match q {
 Request::Rel{raw_graph,quals,..}=> (raw_graph.is_none() || raw_graph==Some(seq![])) && safe_pairs(quals),
 Request::ReplaceQuals{quals,..}=>safe_pairs(quals),Request::Primitive(o)=>safe_op(o),_=>true,
}}
pub open spec fn ordinary_batches(bs:Seq<Seq<Request>>)->bool {default_batches(bs) && forall|i:int,j:int|0<=i<bs.len() && 0<=j<bs[i].len() ==> ordinary_request(bs[i][j])}
pub open spec fn no_marker(s:State)->bool {forall|id:int|s.rels.contains_key(id) ==> value(s.rels[id].quals,seq!['t','e','m','p','o','r','a','l'])!=Some(seq!['t','r','u','e'])}
pub proof fn lemma_primitive_no_marker(s:State,o:Op)
 requires no_marker(s),safe_op(o),
 ensures no_marker(produce(s,o).state),
{assert forall|id:int|produce(s,o).state.rels.contains_key(id) implies value(produce(s,o).state.rels[id].quals,seq!['t','e','m','p','o','r','a','l'])!=Some(seq!['t','r','u','e']) by {}}
pub proof fn lemma_execute_no_marker(s:State,ops:Seq<Op>)
 requires no_marker(s),forall|i:int|0<=i<ops.len() ==> safe_op(ops[i]),
 ensures no_marker(execute(s,ops).state),
 decreases ops.len(),
{
 if ops.len()>0{
  let f=produce(s,ops[0]);lemma_primitive_no_marker(s,ops[0]);
  assert forall|i:int|0<=i<ops.drop_first().len() implies safe_op(ops.drop_first()[i]) by {assert(ops.drop_first()[i]==ops[i+1]);}
  if f.error.is_none(){lemma_execute_no_marker(f.state,ops.drop_first());}
 }
}
pub proof fn theorem_request_no_marker(g:Store,q:Request)
 requires no_marker(g.state),ordinary_request(q),
 ensures no_marker(request(g,q).store.state),
{
 if pre_error(g,q).is_none(){
  assert forall|i:int|0<=i<request_ops(g,q).len() implies safe_op(request_ops(g,q)[i]) by {}
  lemma_execute_no_marker(g.state,request_ops(g,q));
 }
}
pub proof fn theorem_revision_no_marker(g:Store,qs:Seq<Request>)
 requires no_marker(g.state),forall|i:int|0<=i<qs.len() ==> ordinary_request(qs[i]),
 ensures no_marker(requests(g,qs).store.state),
 decreases qs.len(),
{
 if qs.len()>0{
  theorem_request_no_marker(g,qs[0]);
  assert forall|i:int|0<=i<qs.drop_first().len() implies ordinary_request(qs.drop_first()[i]) by {assert(qs.drop_first()[i]==qs[i+1]);}
  theorem_revision_no_marker(request(g,qs[0]).store,qs.drop_first());
 }
}
pub proof fn theorem_history_no_marker(g:Store,bs:Seq<Seq<Request>>,seq:nat)
 requires no_marker(g.state),ordinary_batches(bs),
 ensures no_marker(history(g,bs,seq).store.state),
 decreases bs.len(),
{
 if bs.len()>0{
  assert forall|j:int|0<=j<bs[0].len() implies ordinary_request(bs[0][j]) by {}
  theorem_revision_no_marker(clear_context(g),bs[0]);assert(no_marker(commit(g,bs[0],seq).store.state));
  assert(ordinary_batches(bs.drop_first())) by {
   assert(default_batches(bs.drop_first())) by {assert forall|i:int,j:int|0<=i<bs.drop_first().len() && 0<=j<bs.drop_first()[i].len() implies default_request(bs.drop_first()[i][j]) by {assert(bs.drop_first()[i]==bs[i+1]);}}
   assert forall|i:int,j:int|0<=i<bs.drop_first().len() && 0<=j<bs.drop_first()[i].len() implies ordinary_request(bs.drop_first()[i][j]) by {assert(bs.drop_first()[i]==bs[i+1]);}
  }
  let now=commit(g,bs[0],seq);theorem_history_no_marker(now.store,bs.drop_first(),if now.error.is_none(){seq+1}else{seq});
 }
}
pub proof fn theorem_closed_ordinary_source_domain(bs:Seq<Seq<Request>>)
 requires ordinary_batches(bs),
 ensures producer_frame(history(initial_store(),bs,2).store),wellformed(history(initial_store(),bs,2).store.state),no_marker(history(initial_store(),bs,2).store.state),
         fold(empty(),history(initial_store(),bs,2).log)==history(initial_store(),bs,2).store.state,
{theorem_closed_default_full_workflow(bs);assert(no_marker(empty()));theorem_history_no_marker(initial_store(),bs,2);}

pub proof fn theorem_public_marker_is_not_an_api_refusal()
 ensures public_value(InputValue::Boolean(true))==Some(seq!['t','r','u','e']),
         !safe_qual(seq!['t','e','m','p','o','r','a','l'],seq!['t','r','u','e']),
{}

}
