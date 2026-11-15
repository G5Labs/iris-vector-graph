// As-built Python cache admission and COUNT:MAX producer, not PageRank numerics.
// Stable reads, non-reused SQL row IDs, faithful cache lookup/token and successful
// small payload storage are explicit premises; concurrent snapshots are not proved.
use vstd::prelude::*;
verus! {
pub struct Nodes {pub count:nat,pub max_id:nat}
pub struct Key {pub nodes:Option<Nodes>,pub loners:Seq<int>,pub damping:int,pub iterations:nat}
pub struct Entry {pub key:Key,pub adjacency:nat,pub rows:Seq<(int,int)>}
pub struct Reply {pub rows:Seq<(int,int)>,pub census:nat,pub computed:bool,pub native_candidate:bool}
// The loner reader includes self-loop-only nodes. PageRank passes only those
// with no edge at all to its edgeless argument; the others are in adjacency.
pub open spec fn edgeless(raw:Seq<(int,bool)>) -> Seq<int>
    decreases raw.len(),
{if raw.len()==0{seq![]}else{
    let rest=edgeless(raw.drop_first());
    if raw[0].1 {rest}else{seq![raw[0].0]+rest}}}
pub open spec fn token(count:Option<nat>,top:Option<nat>,failed:bool) -> Option<Nodes> {
    if failed {None}else{Some(Nodes{count:count.unwrap_or(0),max_id:top.unwrap_or(0)})}
}
pub open spec fn add_node(n:Nodes,new_id:nat) -> Nodes {Nodes{count:n.count+1,max_id:new_id}}
pub open spec fn key(n:Option<Nodes>,loners:Seq<int>,d:int,it:nat) -> Key {
    Key{nodes:n,loners:if n.is_some(){seq![]}else{loners},damping:d,iterations:it}
}
pub open spec fn call(n:Option<Nodes>,loners:Seq<int>,adj:nat,d:int,it:nat,e:Option<Entry>,fresh:Seq<(int,int)>) -> Reply {
    let k=key(n,loners,d,it);
    let hit=e.is_some() && e.unwrap().key==k && e.unwrap().adjacency==adj;
    Reply{rows:if hit{e.unwrap().rows}else{fresh},
        census:if n.is_some() && hit{0}else{1},computed:!hit,native_candidate:!hit && loners.len()==0}
}
pub proof fn theorem_count_max_producer()
    ensures token(None,None,false)==Some(Nodes{count:0,max_id:0}),token(Some(2),Some(8),true)==None,
{}
pub proof fn theorem_insert_moves_key(n:Nodes,id:nat,l:Seq<int>,d:int,it:nat)
    requires id>n.max_id,
    ensures key(Some(add_node(n,id)),l,d,it)!=key(Some(n),l,d,it),
{}
pub proof fn theorem_repeat_reads_no_loners(n:Nodes,l:Seq<int>,a:nat,d:int,it:nat,rows:Seq<(int,int)>,fresh:Seq<(int,int)>)
    ensures ({let e=Entry{key:key(Some(n),l,d,it),adjacency:a,rows};
        let r=call(Some(n),l,a,d,it,Some(e),fresh);r.rows==rows && r.census==0 && !r.computed}),
{}
pub proof fn theorem_added_isolate_recomputes(n:Nodes,id:nat,l:Seq<int>,a:nat,d:int,it:nat,rows:Seq<(int,int)>,fresh:Seq<(int,int)>)
    requires id>n.max_id,l.len()>0,
    ensures ({let e=Entry{key:key(Some(n),seq![],d,it),adjacency:a,rows};
        let r=call(Some(add_node(n,id)),l,a,d,it,Some(e),fresh);
        r.rows==fresh && r.computed && r.census==1 && !r.native_candidate}),
{theorem_insert_moves_key(n,id,l,d,it);}
pub proof fn theorem_adjacency_change_recomputes(n:Nodes,l:Seq<int>,a:nat,d:int,it:nat,rows:Seq<(int,int)>,fresh:Seq<(int,int)>)
    ensures call(Some(n),l,a+1,d,it,Some(Entry{key:key(Some(n),l,d,it),adjacency:a,rows}),fresh).computed,
{}
pub proof fn theorem_failed_token_uses_list(l:Seq<int>,d:int,it:nat)
    ensures key(None,l,d,it).loners==l,call(None,l,0,d,it,None,seq![]).census==1,
{}
pub proof fn theorem_parameters_decide(n:Nodes,l:Seq<int>,d:int,it:nat)
    ensures key(Some(n),l,d,it)!=key(Some(n),l,d+1,it),key(Some(n),l,d,it)!=key(Some(n),l,d,it+1),
{}
pub proof fn theorem_self_loop_and_isolate_differ(n:Nodes,id:int,d:int,it:nat)
    ensures call(Some(n),edgeless(seq![(id,true)]),0,d,it,None,seq![]).native_candidate,
        !call(Some(n),edgeless(seq![(id,false)]),0,d,it,None,seq![]).native_candidate,
{reveal_with_fuel(edgeless,3);}
// Row counts and normalized scores are not supplied as an expected answer to
// admission. They are independent server obligations, observed only in a fixture.
}
