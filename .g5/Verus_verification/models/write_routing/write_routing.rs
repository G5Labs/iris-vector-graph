// product 3eaa79cf: whether an engine write joins the caller's transaction.
//   iris_vector_graph/_write_txn.py: WriteTxn.begin :164-175 (Txn_Begin(hold) -> level, joined = level > 1),
//   commit :212-232 (Txn_End lowers to the caller's level), rollback :234-250 (Txn_Undo takes back IVG's level only),
//   caller_transaction_level :64-87 and refuse_in_caller_transaction :90-99 (refuse when $TLEVEL > 0).
//   Routing: ordinary writes run on the engine's SQL connection; IRISGraphStore._iris_obj (stores/iris_sql_store.py
//   :842-849) is createIRIS(store.conn), used by create_edge_temporal -> write_temporal_edge (:2655-2690);
//   engine._iris_obj (engine.py :1894-1943) opens a Native API connection of its own when the engine knows its
//   credentials (from_connect :487-511), used by purge_before (_engine/temporal.py :623-640) and
//   set_temporal_structural (:722-746).
//   Direct ObjectScript calls (no WriteTxn): TemporalIndex.InsertEdge sets ^KG("tout"/"tin") (WriteStores) before
//   its embedded SQL inserts the marked structural row and endpoint nodes; PurgeBefore runs RetireExpired (SQL) before
//   its kills; TemporalPolicy.Apply sets globals only.
// Provider premises (observed on the fixture, not derived): SQL START TRANSACTION sets $TLEVEL 1 at once; with the
// driver's autocommit off, $TLEVEL is 0 until the first SQL write, which opens level 1 implicitly; a global set at
// $TLEVEL 0 is durable at once; ObjectScript TSTART/TCOMMIT/TROLLBACK 1 nest; the caller ends its transaction at its
// own level 1 (on 2026.1 SQL COMMIT/ROLLBACK end one level, F-C1705, so no deeper level is modeled as ended by it);
// a second server process has its own transaction.
use vstd::prelude::*;
verus! {
pub type W=int;
/// The server process a call's writes run in.
pub enum Proc {Caller,Own}
pub enum Engine {OnCallerConn,FromConnect}
pub enum Op {Ordinary,TemporalEdge,Purge,Policy}
pub enum Start {Sql,AutocommitOff}
pub enum End {Commit,Rollback}
/// engine._iris_obj(): its own Native API connection when it knows the credentials, else createIRIS(engine.conn).
pub open spec fn native_proc(e:Engine)->Proc {match e {Engine::FromConnect=>Proc::Own,Engine::OnCallerConn=>Proc::Caller}}
pub open spec fn route(e:Engine,op:Op)->Proc {
 match op {
  Op::Ordinary=>Proc::Caller,
  Op::TemporalEdge=>Proc::Caller,
  Op::Purge=>native_proc(e),
  Op::Policy=>native_proc(e),
 }
}
/// The caller's process: its $TLEVEL, the writes not yet committed and what is durable.
pub struct St {pub tlevel:nat,pub hold:bool,pub pending:Seq<W>,pub durable:Set<W>}
pub open spec fn start(s:Start)->St {
 match s {
  Start::Sql=>St{tlevel:1,hold:false,pending:Seq::empty(),durable:Set::empty()},
  Start::AutocommitOff=>St{tlevel:0,hold:true,pending:Seq::empty(),durable:Set::empty()},
 }
}
/// The caller's own SQL write: with autocommit off it opens the caller's level first.
pub open spec fn caller_write(st:St,w:W)->St {
 St{tlevel:if st.tlevel==0 {1} else {st.tlevel},hold:st.hold,pending:st.pending.push(w),durable:st.durable}
}
/// WriteTxn.begin on the caller's process: Txn_Begin(hold) opens the caller's level first when held, then IVG's.
pub open spec fn begin(st:St)->(St,nat) {
 let base:nat=if st.hold && st.tlevel==0 {1} else {st.tlevel};
 (St{tlevel:base+1,hold:st.hold,pending:st.pending,durable:st.durable},base+1)
}
pub open spec fn ivg_put(st:St,w:W)->St {St{tlevel:st.tlevel,hold:st.hold,pending:st.pending.push(w),durable:st.durable}}
/// WriteTxn.commit: Txn_End lowers to level-1; at level 1 (no caller) that commits.
pub open spec fn ivg_commit(st:St,level:nat)->St {
 if level<=1 {St{tlevel:0,hold:st.hold,pending:Seq::empty(),durable:st.durable+st.pending.to_set()}}
 else {St{tlevel:(level-1) as nat,hold:st.hold,pending:st.pending,durable:st.durable}}
}
/// WriteTxn.rollback: Txn_Undo takes back the writes of IVG's level (those after `mark`) only.
pub open spec fn ivg_undo(st:St,level:nat,mark:nat)->St {
 St{tlevel:(level-1) as nat,hold:st.hold,pending:st.pending.subrange(0,mark as int),durable:st.durable}
}
/// How a call writes: through WriteTxn, or by calling ObjectScript directly; and the order of its global (G) and
/// SQL (S) writes. Step i of a call with id w writes effect 2*w+i.
pub enum Via {WriteTxn,Direct}
pub enum Step {G,S}
pub open spec fn via(op:Op)->Via {match op {Op::Ordinary=>Via::WriteTxn,_=>Via::Direct}}
pub open spec fn steps(op:Op)->Seq<Step> {
 match op {
  Op::Ordinary=>seq![Step::S],
  Op::TemporalEdge=>seq![Step::G,Step::S],
  Op::Purge=>seq![Step::S,Step::G],
  Op::Policy=>seq![Step::G],
 }
}
/// One write on the caller's process outside WriteTxn: at $TLEVEL 0 a global is durable at once, and an SQL write
/// opens level 1 implicitly when the driver's autocommit is off.
pub open spec fn step(st:St,k:Step,x:W)->St {
 if st.tlevel==0 {
  match k {
   Step::S=>if st.hold {St{tlevel:1,hold:st.hold,pending:st.pending.push(x),durable:st.durable}}
            else {St{tlevel:0,hold:st.hold,pending:st.pending,durable:st.durable.insert(x)}},
   Step::G=>St{tlevel:0,hold:st.hold,pending:st.pending,durable:st.durable.insert(x)},
  }
 } else {St{tlevel:st.tlevel,hold:st.hold,pending:st.pending.push(x),durable:st.durable}}
}
pub open spec fn direct(st:St,ks:Seq<Step>,w:W)->St {
 if ks.len()==1 {step(st,ks[0],2*w)} else {step(step(st,ks[0],2*w),ks[1],2*w+1)}
}
pub open spec fn put_all(st:St,n:nat,w:W)->St {if n==1 {ivg_put(st,2*w)} else {ivg_put(ivg_put(st,2*w),2*w+1)}}
/// One engine call with id `w`. On another process it is a transaction of its own there.
pub open spec fn call(st:St,e:Engine,op:Op,w:W)->St {
 match route(e,op) {
  Proc::Own=>St{tlevel:st.tlevel,hold:st.hold,pending:st.pending,
                durable:if steps(op).len()==1 {st.durable.insert(2*w)} else {st.durable.insert(2*w).insert(2*w+1)}},
  Proc::Caller=>match via(op) {
   Via::WriteTxn=>{let (b,l)=begin(st); ivg_commit(put_all(b,steps(op).len(),w),l)},
   Via::Direct=>direct(st,steps(op),w),
  },
 }
}
/// Effect i of call w is kept after the caller ends its transaction.
pub open spec fn kept(s:Start,e:Engine,op:Op,w:W,end:End,i:int)->bool {caller_end(call(start(s),e,op,w),end).durable.contains(2*w+i)}
pub open spec fn caller_end(st:St,end:End)->St {
 match end {
  End::Commit=>St{tlevel:0,hold:st.hold,pending:Seq::empty(),durable:st.durable+st.pending.to_set()},
  End::Rollback=>St{tlevel:0,hold:st.hold,pending:Seq::empty(),durable:st.durable},
 }
}
/// refuse_in_caller_transaction: refuse when $TLEVEL is above 0.
pub open spec fn refuses(st:St)->bool {st.tlevel>0}

/// T1-T3: a call through WriteTxn is kept exactly when the caller commits, however the caller opened its transaction.
pub proof fn theorem_writetxn_call_follows_caller_end(s:Start,e:Engine,w:W,end:End)
 ensures kept(s,e,Op::Ordinary,w,end,0)==(end==End::Commit),
{
 let c=call(start(s),e,Op::Ordinary,w);
 assert(c.pending=~=seq![2*w]);
 assert(c.durable=~=Set::<W>::empty());
 if end==End::Commit {assert(c.pending.to_set().contains(2*w)) by {assert(c.pending[0]==2*w);}}
}
/// T4, T5, T9 and the policy call: after SQL START TRANSACTION every effect of a call on the caller's process is kept
/// exactly when the caller commits.
pub proof fn theorem_start_transaction_direct_call_follows_caller_end(e:Engine,op:Op,w:W,end:End,i:int)
 requires (route(e,op)==Proc::Caller),(via(op)==Via::Direct),0<=i,i<steps(op).len()
 ensures kept(Start::Sql,e,op,w,end,i)==(end==End::Commit),
{
 let c=call(start(Start::Sql),e,op,w);
 if steps(op).len()==1 {assert(c.pending=~=seq![2*w]);} else {assert(c.pending=~=seq![2*w,2*w+1]);}
 assert(c.durable=~=Set::<W>::empty());
 if end==End::Commit {assert(c.pending.to_set().contains(2*w+i)) by {assert(c.pending[i]==2*w+i);}}
}
/// T11, T12 (as built): with the driver's autocommit off and nothing written, the caller's rollback of a
/// create_edge_temporal keeps its temporal stores (effect 0) and removes its structural row and nodes (effect 1).
pub proof fn theorem_autocommit_off_temporal_edge_splits(e:Engine,w:W)
 ensures kept(Start::AutocommitOff,e,Op::TemporalEdge,w,End::Rollback,0),
  !kept(Start::AutocommitOff,e,Op::TemporalEdge,w,End::Rollback,1),
  kept(Start::AutocommitOff,e,Op::TemporalEdge,w,End::Commit,1),
{
 let c=call(start(Start::AutocommitOff),e,Op::TemporalEdge,w);
 assert(c.durable=~=set![2*w]);
 assert(c.pending=~=seq![2*w+1]);
 assert(c.pending.to_set().contains(2*w+1)) by {assert(c.pending[0]==2*w+1);}
}
/// The same caller and a purge on the caller's process: its SQL comes first, so the whole purge follows the caller.
pub proof fn theorem_autocommit_off_purge_follows(w:W,end:End,i:int)
 requires 0<=i<2
 ensures kept(Start::AutocommitOff,Engine::OnCallerConn,Op::Purge,w,end,i)==(end==End::Commit),
{
 let c=call(start(Start::AutocommitOff),Engine::OnCallerConn,Op::Purge,w);
 assert(c.pending=~=seq![2*w,2*w+1]);
 assert(c.durable=~=Set::<W>::empty());
 if end==End::Commit {assert(c.pending.to_set().contains(2*w+i)) by {assert(c.pending[i]==2*w+i);}}
}
/// T10: a call routed to the engine's own connection is durable whatever the caller does.
pub proof fn theorem_own_process_write_survives_rollback(s:Start,e:Engine,op:Op,w:W,end:End)
 requires route(e,op)==Proc::Own
 ensures kept(s,e,op,w,end,0),
{}
/// T5: create_edge_temporal joins on both engines; T9/T10: the maintenance calls join only on the caller's connection.
pub proof fn theorem_routing(e:Engine)
 ensures route(e,Op::TemporalEdge)==Proc::Caller,route(e,Op::Ordinary)==Proc::Caller,
  route(Engine::FromConnect,Op::Purge)==Proc::Own,route(Engine::OnCallerConn,Op::Purge)==Proc::Caller,
  route(Engine::FromConnect,Op::Policy)==Proc::Own,
{}
/// A failed IVG write takes back its own level only: the caller's earlier write stays in the open transaction.
pub proof fn theorem_failed_write_keeps_caller_work(s:Start,w0:W,w1:W)
 requires w0!=w1
 ensures ({
  let a=caller_write(start(s),w0);let (b,l)=begin(a);let u=ivg_undo(ivg_put(b,w1),l,a.pending.len());
  u.pending=~=seq![w0] && u.tlevel==a.tlevel && caller_end(u,End::Commit).durable.contains(w0)
   && !caller_end(u,End::Commit).durable.contains(w1)
 }),
{
 let a=caller_write(start(s),w0);let (b,l)=begin(a);let u=ivg_undo(ivg_put(b,w1),l,a.pending.len());
 assert(u.pending=~=seq![w0]);
 assert(u.pending.to_set().contains(w0)) by {assert(u.pending[0]==w0);}
 assert(!u.pending.to_set().contains(w1)) by {if u.pending.to_set().contains(w1) {assert(u.pending.contains(w1)); let i=choose|i:int| 0<=i<u.pending.len() && u.pending[i]==w1; assert(i==0);} }
}
/// T7, T8: after SQL START TRANSACTION the loader refuses even before the caller writes; with autocommit off it
/// refuses once the caller has written, and runs before that.
pub proof fn theorem_loader_refusal(w:W)
 ensures refuses(start(Start::Sql)),refuses(caller_write(start(Start::Sql),w)),
  !refuses(start(Start::AutocommitOff)),refuses(caller_write(start(Start::AutocommitOff),w)),
{}
}
