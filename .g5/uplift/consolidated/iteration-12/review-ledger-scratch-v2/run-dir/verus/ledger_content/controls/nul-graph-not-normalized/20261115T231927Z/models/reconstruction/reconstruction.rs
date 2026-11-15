// 3eaa79cf: structural entity/count projection of the real Python history reader.
// Map key (is_relationship,id); payload is an abstract property/tuple identity.
// SQL provides ordered records; selection is represented, database paging is not.
use vstd::prelude::*;
verus! {
pub type State = Map<(bool,int),int>;
pub enum Op { Create(bool,int,int), Delete(bool,int), Update(bool,int,int), Other }
pub struct Record { pub seq:nat, pub op:Op, pub redacted:bool, pub audit:bool }
pub open spec fn effective(raw:Option<nat>) -> nat {
    match raw { Some(n) => if n==0 {250000} else {n}, None => 250000 }
}
pub open spec fn selected(r:Record, through:nat) -> bool { 1 <= r.seq <= through }
pub open spec fn apply(s:State,r:Record) -> State {
    if r.redacted || r.audit {s} else { match r.op {
        Op::Create(rel,id,v) => s.insert((rel,id),v),
        Op::Delete(rel,id) => s.remove((rel,id)),
        Op::Update(rel,id,v) => if s.contains_key((rel,id)) {s.insert((rel,id),v)} else {s},
        Op::Other => s,
    } }
}
pub open spec fn next(s:State,r:Record,through:nat) -> State {
    if selected(r,through) {apply(s,r)} else {s}
}
pub open spec fn fold(s:State,rs:Seq<Record>,through:nat) -> State
    decreases rs.len(),
{
    if rs.len()==0 {s} else {fold(next(s,rs[0],through),rs.drop_first(),through)}
}
pub open spec fn run(s:State,rs:Seq<Record>,through:nat,bound:Option<nat>,stream:bool) -> Option<State>
    decreases rs.len(),
{
    if rs.len()==0 {Some(s)} else {
        let n=next(s,rs[0],through);
        if selected(rs[0],through) && bound.is_some() && !stream && n.len()>bound.unwrap() {None}
        else {run(n,rs.drop_first(),through,bound,stream)}
    }
}
pub open spec fn prefixes_fit(s:State,rs:Seq<Record>,through:nat,b:nat) -> bool
    decreases rs.len(),
{
    if rs.len()==0 {true} else {
        let n=next(s,rs[0],through);
        (!selected(rs[0],through) || n.len()<=b) && prefixes_fit(n,rs.drop_first(),through,b)
    }
}
pub proof fn theorem_stream_and_export_fold(s:State,rs:Seq<Record>,through:nat,b:Option<nat>)
    ensures run(s,rs,through,b,true)==Some(fold(s,rs,through)),
        run(s,rs,through,None,false)==Some(fold(s,rs,through)),
    decreases rs.len(),
{
    if rs.len()>0 {theorem_stream_and_export_fold(next(s,rs[0],through),rs.drop_first(),through,b);}
}
pub proof fn theorem_bound_exactly_prefixes(s:State,rs:Seq<Record>,through:nat,b:nat)
    ensures run(s,rs,through,Some(b),false).is_some()==prefixes_fit(s,rs,through,b),
        prefixes_fit(s,rs,through,b) ==> run(s,rs,through,Some(b),false)==Some(fold(s,rs,through)),
    decreases rs.len(),
{
    if rs.len()>0 {theorem_bound_exactly_prefixes(next(s,rs[0],through),rs.drop_first(),through,b);}
}
pub open spec fn record(seq:nat,op:Op) -> Record {Record {seq,op,redacted:false,audit:false}}
pub proof fn theorem_transient_oversize_refuses()
    ensures ({let rs=seq![record(1,Op::Create(false,0,0)),record(2,Op::Create(false,1,0)),record(3,Op::Delete(false,1))];
        fold(Map::empty(),rs,3)==map![(false,0)=>0]
        && run(Map::empty(),rs,3,Some(1),false)==None
        && run(Map::empty(),rs,3,Some(1),true)==Some(map![(false,0)=>0])}),
{reveal_with_fuel(fold,5);reveal_with_fuel(run,5);}
pub proof fn theorem_at_bound_succeeds()
    ensures run(Map::empty(),seq![record(1,Op::Create(false,0,0))],1,Some(1),false)==Some(map![(false,0)=>0]),
{reveal_with_fuel(run,3);}
pub proof fn theorem_named_revision_ignores_later()
    ensures run(Map::empty(),seq![record(1,Op::Create(false,0,0)),record(2,Op::Create(false,1,0))],1,Some(1),false)
        ==Some(map![(false,0)=>0]),
{reveal_with_fuel(run,4);}
pub proof fn theorem_zero_uses_default()
    ensures effective(Some(0))==250000, effective(None)==250000,effective(Some(1))==1,
{}
pub proof fn theorem_tombstone_and_audit_ignore(s:State,r:Record)
    requires r.redacted || r.audit,
    ensures apply(s,r)==s,
{}
pub proof fn theorem_missing_update_does_not_create(s:State,rel:bool,id:int,v:int)
    requires !s.contains_key((rel,id)),
    ensures apply(s,record(1,Op::Update(rel,id,v)))==s,
{}
}
