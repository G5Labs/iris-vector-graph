// As-built per-attribute lifecycle projection of 3eaa79cf replay.py.
// Values and relationship tuples are opaque integer tokens. Ordered SQL records,
// admitted operations and stable ledger history are provider premises.
use vstd::prelude::*;
verus! {
pub enum Op { Create, Delete, Set(int), Remove }
pub struct Record { pub seq:nat, pub op:Op, pub prior:Option<int>, pub new:Option<int> }
pub struct Entity { pub exists:bool, pub value:Option<int> }
pub struct Life { pub seen:bool, pub created:bool, pub before:Option<int>, pub after:Option<int> }
pub enum Payload {Value(int),Snapshot(Option<int>)}
pub open spec fn val(v:Option<int>) -> Option<Payload> {match v {Some(x)=>Some(Payload::Value(x)),None=>None}}
pub struct Entry { pub attr:bool, pub before:Option<Payload>, pub after:Option<Payload> }
pub struct Delta { pub closed:Seq<Entry>, pub life:Option<Life> }
pub open spec fn writer(s:Entity,seq:nat,op:Op) -> (Entity,Record) {
    let n=match op {Op::Set(v)=>Some(v), _=>None};
    let next=match op {Op::Create=>Entity{exists:true,value:None},Op::Delete=>Entity{exists:false,value:None},
        _=>Entity{value:n,..s}};
    (next,Record{seq,op,prior:s.value,new:n})
}
pub open spec fn track(d:Delta,r:Record) -> Delta {
    match r.op {
        Op::Create=>Delta{life:Some(Life{seen:false,created:true,before:None,after:None}),..d},
        Op::Delete=>Delta{closed: if d.life.is_none() || !d.life.unwrap().created {
            d.closed.push(Entry{attr:false,before:Some(Payload::Snapshot(r.prior)),after:None})} else {d.closed}, life:None},
        _=>{let l=if d.life.is_some(){d.life.unwrap()}else{Life{seen:false,created:false,before:None,after:None}};
            Delta{life:Some(Life{seen:true,created:l.created,
                before:if l.seen {l.before}else{if l.created {None}else{r.prior}},after:r.new}),..d}}
    }
}
pub open spec fn finish(d:Delta) -> Seq<Entry> {
    if d.life.is_none(){d.closed}else{
        let l=d.life.unwrap();
        let e=if l.created {d.closed.push(Entry{attr:false,before:None,after:Some(Payload::Snapshot(None))})}else{d.closed};
        if l.seen && (if l.created {l.after.is_some()}else{l.before!=l.after}) {
            e.push(Entry{attr:true,before:val(l.before),after:val(l.after)})}else{e}
    }
}
pub open spec fn inverse(es:Seq<Entry>) -> Seq<Entry> {
    Seq::new(es.len(),|i:int| Entry{before:es[i].after,after:es[i].before,..es[i]})
}
pub open spec fn selected(r:Record,a:nat,b:nat) -> bool { a < r.seq <= b }
pub open spec fn read(d:Delta,rs:Seq<Record>,a:nat,b:nat) -> Delta
    decreases rs.len(),
{if rs.len()==0 {d}else{read(if selected(rs[0],a,b){track(d,rs[0])}else{d},rs.drop_first(),a,b)}}
pub open spec fn empty() -> Delta {Delta{closed:seq![],life:None}}
pub open spec fn diff(rs:Seq<Record>,a:nat,b:nat) -> Seq<Entry> {
    if a==b {seq![]} else if a<b {finish(read(empty(),rs,a,b))} else {inverse(finish(read(empty(),rs,b,a)))}
}
// A continuous life: first prior and final new are derived from raw writes.
pub open spec fn continuous(s:Entity,d:Delta,ops:Seq<Op>) -> (Entity,Delta)
    decreases ops.len(),
{if ops.len()==0 {(s,d)}else{let (n,r)=writer(s,1,ops[0]);continuous(n,track(d,r),ops.drop_first())}}
pub open spec fn attr_op(o:Op) -> bool {match o {Op::Set(_)|Op::Remove=>true,_=>false}}
pub open spec fn attrs_only(ops:Seq<Op>) -> bool {
    forall|i:int| 0<=i<ops.len() ==> attr_op(ops[i])
}
pub open spec fn aligned(s:Entity,d:Delta,original:Option<int>) -> bool {
    s.exists && d.closed.len()==0 && d.life.is_some() && !d.life.unwrap().created
    && d.life.unwrap().seen && d.life.unwrap().before==original && d.life.unwrap().after==s.value
}
pub proof fn theorem_continuous_endpoint_relation(s:Entity,d:Delta,ops:Seq<Op>,original:Option<int>)
    requires attrs_only(ops),aligned(s,d,original),
    ensures aligned(continuous(s,d,ops).0,continuous(s,d,ops).1,original),
    decreases ops.len(),
{
    if ops.len()>0 {
        let (n,r)=writer(s,1,ops[0]);
        assert(attrs_only(ops.drop_first())) by {
            assert forall|i:int| 0<=i<ops.drop_first().len() implies
                attr_op(ops.drop_first()[i]) by {assert(ops.drop_first()[i]==ops[i+1]);}
        }
        theorem_continuous_endpoint_relation(n,track(d,r),ops.drop_first(),original);
    }
}
pub proof fn theorem_inverse_involution(es:Seq<Entry>)
    ensures inverse(inverse(es))==es,
{assert(inverse(inverse(es)) =~= es);}
pub proof fn theorem_raw_history_endpoints(s:Entity,ops:Seq<Op>)
    requires s.exists,attrs_only(ops),ops.len()>0,
    ensures ({let out=continuous(s,empty(),ops);let es=finish(out.1);
        if s.value==out.0.value {es.len()==0}
        else {es==seq![Entry{attr:true,before:val(s.value),after:val(out.0.value)}]}}),
{
    let (n,r)=writer(s,1,ops[0]);
    assert(attrs_only(ops.drop_first())) by {
        assert forall|i:int| 0<=i<ops.drop_first().len() implies attr_op(ops.drop_first()[i]) by {
            assert(ops.drop_first()[i]==ops[i+1]);
        }
    }
    theorem_continuous_endpoint_relation(n,track(empty(),r),ops.drop_first(),s.value);
}
pub proof fn theorem_named_reverse_and_equal(rs:Seq<Record>,a:nat,b:nat)
    requires a<b,
    ensures diff(rs,b,a)==inverse(diff(rs,a,b)),diff(rs,a,a)==seq![],
{}
pub proof fn theorem_range_lower_exclusive(r:Record,a:nat,b:nat)
    requires r.seq==a,a<=b,
    ensures !selected(r,a,b),
{}
pub proof fn theorem_continuous_net_zero(v:int)
    ensures ({let s=Entity{exists:true,value:Some(v)};let (_,r)=writer(s,1,Op::Set(v));
        finish(track(empty(),r)).len()==0}),
{}
pub proof fn theorem_first_prior_survives()
    ensures ({let s=Entity{exists:true,value:Some(1)};let (s1,r1)=writer(s,1,Op::Set(2));
        let (_,r2)=writer(s1,2,Op::Set(3));let d=finish(track(track(empty(),r1),r2));
        d==seq![Entry{attr:true,before:Some(Payload::Value(1)),after:Some(Payload::Value(3))}]}),
{}
pub proof fn theorem_simple_delete_preserves_snapshot()
    ensures ({let s=Entity{exists:true,value:Some(1)};let (s1,r1)=writer(s,2,Op::Delete);
        let (s2,r2)=writer(s1,3,Op::Create);let (s3,r3)=writer(s2,3,Op::Set(2));
        let es=finish(track(track(track(empty(),r1),r2),r3));
        s.value==Some(1) && s3.value==Some(2) && es.len()==3
        && inverse(es)[0].after==Some(Payload::Snapshot(Some(1)))
        && inverse(es)[2].before==Some(Payload::Value(2)) && inverse(es)[2].after==None}),
{}
// The stronger legitimate challenge: change k before deleting. The deletion
// snapshot preserves the changed value, while closing drops its earlier prior.
pub proof fn theorem_change_then_delete_loses_range_prior()
    ensures ({let s=Entity{exists:true,value:Some(1)};let (s1,r1)=writer(s,2,Op::Set(2));
        let (s2,r2)=writer(s1,3,Op::Delete);let (s3,r3)=writer(s2,4,Op::Create);
        let (_,r4)=writer(s3,4,Op::Set(3));let es=finish(track(track(track(track(empty(),r1),r2),r3),r4));
        es.len()==3 && inverse(es)[0].after==Some(Payload::Snapshot(Some(2)))
        && inverse(es)[2].after==None && s.value==Some(1)}),
{}
pub proof fn theorem_created_then_deleted_cancels()
    ensures ({let s=Entity{exists:false,value:None};let (s1,r1)=writer(s,1,Op::Create);
        let (_,r2)=writer(s1,2,Op::Delete);finish(track(track(empty(),r1),r2)).len()==0}),
{}
}
