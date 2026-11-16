// One ordinary triple in one graph. SQL uniqueness, atomic rollback and the
// adjacency callback are provider premises; this is not executable Python.
use vstd::prelude::*;
verus! {
pub enum Api { Create, Store }
pub struct State { pub row:bool, pub temporal:bool, pub value:int, pub endpoints:bool, pub adjacency:bool }
pub struct Result { pub state:State, pub answer:Option<bool> }
pub open spec fn run(s:State, api:Api, value:int, marker:bool, indexed:bool, refused:bool) -> Result {
    if refused { Result{state:s,answer:None} }
    else if !s.row {
        Result{state:State{row:true,temporal:marker,value,endpoints:true,
            adjacency:indexed || matches!(api,Api::Create) || s.adjacency},answer:Some(true)}
    } else if matches!(api,Api::Create) && s.temporal {
        Result{state:State{temporal:marker,value,..s},answer:Some(true)}
    } else {
        Result{state:State{endpoints:true,..s},answer:Some(matches!(api,Api::Store))}
    }
}
pub open spec fn count(s:State) -> nat { if s.row {1} else {0} }
pub proof fn theorem_duplicate_returns_differ(s:State,value:int,indexed:bool)
    requires s.row,!s.temporal,s.endpoints,
    ensures run(s,Api::Create,value,false,indexed,false).answer==Some(false),
        run(s,Api::Store,value,false,indexed,false).answer==Some(true),
        run(s,Api::Create,value,false,indexed,false).state==s,
        run(s,Api::Store,value,false,indexed,false).state==s,
{}
pub proof fn theorem_repeat_counts_one(s:State,api:Api,v:int,w:int,indexed:bool)
    requires !s.row,
    ensures count(run(run(s,api,v,false,indexed,false).state,api,w,false,indexed,false).state)==1,
        run(run(s,api,v,false,indexed,false).state,api,w,false,indexed,false).state.value==v,
{}
pub proof fn theorem_new_edge_registers_endpoints(s:State,api:Api,v:int,indexed:bool)
    requires !s.row,
    ensures run(s,api,v,false,indexed,false).state.endpoints,
        run(s,api,v,false,indexed,false).answer==Some(true),count(run(s,api,v,false,indexed,false).state)==1,
{}
pub proof fn theorem_refusal_leaves_state(s:State,api:Api,v:int,indexed:bool)
    ensures run(s,api,v,false,indexed,true).answer==None,run(s,api,v,false,indexed,true).state==s,
{}
pub proof fn theorem_temporal_adoption(s:State,v:int,indexed:bool)
    requires s.row,s.temporal,
    ensures run(s,Api::Create,v,false,indexed,false).answer==Some(true),
        !run(s,Api::Create,v,false,indexed,false).state.temporal,
        run(s,Api::Create,v,false,indexed,false).state.value==v,
        count(run(s,Api::Create,v,false,indexed,false).state)==1,
        run(s,Api::Store,v,false,indexed,false).state.temporal,
        run(s,Api::Store,v,false,indexed,false).state.value==s.value,
{}
pub proof fn theorem_adjacency_distinction(s:State,v:int)
    requires !s.row,!s.adjacency,
    ensures run(s,Api::Create,v,false,false,false).state.adjacency,
        !run(s,Api::Store,v,false,false,false).state.adjacency,
        run(s,Api::Store,v,false,true,false).state.adjacency,
{}
pub proof fn theorem_caller_marker_retained(s:State,v:int,w:int,indexed:bool)
    requires !s.row,
    ensures run(s,Api::Create,v,true,indexed,false).state.temporal,
        run(run(s,Api::Create,v,true,indexed,false).state,Api::Create,w,true,indexed,false).answer==Some(true),
        run(run(s,Api::Create,v,true,indexed,false).state,Api::Create,w,true,indexed,false).state.temporal,
        run(run(s,Api::Create,v,true,indexed,false).state,Api::Create,w,true,indexed,false).state.value==w,
{}

}
