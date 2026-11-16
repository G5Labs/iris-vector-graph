// Per-route restore stages; decoded widths and successful SQL/provider operations
// are the abstraction boundary. No IRIS/Python executable body is verified.
use vstd::prelude::*;
verus! {
pub enum Width { Falsy, Invalid, Present(int) }
pub struct Route { pub table:int,pub width:int,pub indexed:bool }
pub struct State {
    pub registry:Map<(int,int),Route>,pub widths:Map<int,int>,
    pub rows:Map<(int,int,int),Seq<int>>,pub parents:Set<(int,int)>,pub failed:nat
}
pub struct Load { pub state:State,pub reported:nat }
pub enum Read { Absent, Value(Seq<int>), MissingTable }
pub struct Archived { pub key:(int,int),pub table:int,pub width:int }
pub open spec fn export(s:State,key:(int,int)) -> Option<Archived> {
    if !s.registry.contains_key(key) || s.registry[key].width<=0 {None}
    else {Some(Archived{key,table:s.registry[key].table,width:s.registry[key].width})}
}
pub open spec fn install_registry(s:State,key:(int,int),route:Route) -> State {
    State{registry:s.registry.insert(key,route),..s}
}
pub open spec fn width(meta:Width,registry:Option<int>) -> int {
    match meta {Width::Falsy=>registry.unwrap_or(0),Width::Invalid=>0,Width::Present(w)=>w}
}
pub open spec fn prepare(s:State,key:(int,int),table:int,meta:Width,engine_width:int,build:bool,record:bool,archived_rows:nat) -> State {
    let fallback=if s.registry.contains_key(key) && s.registry[key].table==table {Some(s.registry[key].width)} else {None};
    let w=width(meta,fallback);
    if w<=0 {State{failed:s.failed+archived_rows,..s}} else {
        let declared=if s.widths.contains_key(table){s.widths}else{s.widths.insert(table,w)};
        let registry=if record && s.registry.contains_key(key) && s.registry[key].table==table {
            s.registry.insert(key,Route{indexed:build,..s.registry[key]})
        } else {s.registry};
        State{widths:declared,registry,..s}
    }
}
pub open spec fn load(s:State,table:int,g:int,n:int,v:Seq<int>,merge:bool) -> Load {
    let key=(table,g,n);
    if !s.widths.contains_key(table) {
        Load{state:State{failed:s.failed+1,..s},reported:0}
    } else if merge && s.rows.contains_key(key) {
        Load{state:s,reported:1}
    } else if s.widths[table]!=v.len() || !s.parents.contains((g,n)) || s.rows.contains_key(key) {
        Load{state:State{failed:s.failed+1,..s},reported:0}
    } else {
        Load{state:State{rows:s.rows.insert(key,v),..s},reported:1}
    }
}
// Invalid-width route skips its INSERT, so failure rows are counted once.
pub open spec fn restore_one(s:State,key:(int,int),t:int,meta:Width,engine:int,build:bool,record:bool,g:int,n:int,v:Seq<int>,merge:bool) -> Load {
    let fallback=if s.registry.contains_key(key) && s.registry[key].table==t {Some(s.registry[key].width)} else {None};
    let chosen=width(meta,fallback);let p=prepare(s,key,t,meta,engine,build,record,1);
    if chosen<=0 {Load{state:p,reported:0}} else {load(p,t,g,n,v,merge)}
}

pub open spec fn read(s:State,key:(int,int),node:int) -> Read {
    if !s.registry.contains_key(key){Read::Absent}
    else if !s.widths.contains_key(s.registry[key].table){Read::MissingTable}else{
        let row=(s.registry[key].table,key.0,node);
        if s.rows.contains_key(row){Read::Value(s.rows[row])}else{Read::Absent}
    }
}
pub open spec fn query_admitted(s:State,key:(int,int),offered:int) -> bool {
    s.registry.contains_key(key) && offered==s.registry[key].width
}
pub proof fn theorem_archived_width_not_engine(s:State,key:(int,int),t:int,w:int,engine:int,build:bool,record:bool)
    requires !s.widths.contains_key(t),w>0,
    ensures prepare(s,key,t,Width::Present(w),engine,build,record,1).widths[t]==w,
{}
pub proof fn theorem_fallback_and_invalid(s:State,key:(int,int),t:int,engine:int)
    requires s.registry.contains_key(key),s.registry[key].table==t,s.registry[key].width>0,!s.widths.contains_key(t),
    ensures prepare(s,key,t,Width::Falsy,engine,false,true,1).widths[t]==s.registry[key].width,
        prepare(s,key,t,Width::Invalid,engine,false,true,1).failed==s.failed+1,
        prepare(s,key,t,Width::Present(0),engine,false,true,1).failed==s.failed+1,
{}
pub proof fn theorem_restored_row_reaches_own_reader(s:State,key:(int,int),t:int,node:int,v:Seq<int>,engine:int,build:bool)
    requires s.registry.contains_key(key),s.registry[key].table==t,s.registry[key].width==v.len(),v.len()>0,
        !s.widths.contains_key(t),!s.rows.contains_key((t,key.0,node)),s.parents.contains((key.0,node)),
    ensures read(load(prepare(s,key,t,Width::Present(v.len() as int),engine,build,true,1),t,key.0,node,v,false).state,key,node)==Read::Value(v),
        query_admitted(load(prepare(s,key,t,Width::Present(v.len() as int),engine,build,true,1),t,key.0,node,v,false).state,key,v.len() as int),
{}
pub proof fn theorem_orphan_table_does_not_resolve(s:State,key:(int,int),t:int,node:int,v:Seq<int>,engine:int)
    requires !s.registry.contains_key(key),
    ensures read(load(prepare(s,key,t,Width::Present(v.len() as int),engine,true,true,1),t,key.0,node,v,false).state,key,node)==Read::Absent,
{}
pub proof fn theorem_existing_incompatible_width_is_not_redeclared(s:State,key:(int,int),t:int,g:int,n:int,v:Seq<int>,w:int,engine:int)
    requires s.widths.contains_key(t),s.widths[t]!=v.len(),w>0,!s.rows.contains_key((t,g,n)),
    ensures prepare(s,key,t,Width::Present(w),engine,true,true,1).widths[t]==s.widths[t],
        load(prepare(s,key,t,Width::Present(w),engine,true,true,1),t,g,n,v,true).reported==0,
        load(prepare(s,key,t,Width::Present(w),engine,true,true,1),t,g,n,v,true).state.rows==s.rows,
        load(prepare(s,key,t,Width::Present(w),engine,true,true,1),t,g,n,v,true).state.failed==s.failed+1,
{}
pub proof fn theorem_index_result_and_failed_record(s:State,key:(int,int),t:int,w:int,engine:int,build:bool)
    requires s.registry.contains_key(key),s.registry[key].table==t,w>0,
    ensures prepare(s,key,t,Width::Present(w),engine,build,true,1).registry[key].indexed==build,
        prepare(s,key,t,Width::Present(w),engine,build,false,1).registry[key].indexed==s.registry[key].indexed,
{}
pub proof fn theorem_merge_reports_without_overwrite(s:State,t:int,g:int,n:int,v:Seq<int>)
    requires s.widths.contains_key(t),s.widths[t]==v.len(),s.parents.contains((g,n)),s.rows.contains_key((t,g,n)),
    ensures load(s,t,g,n,v,true).reported==1,load(s,t,g,n,v,true).state.rows==s.rows,
        load(s,t,g,n,v,false).reported==0,load(s,t,g,n,v,false).state.failed==s.failed+1,
{}
pub proof fn theorem_other_graph_frame(s:State,t:int,g:int,n:int,v:Seq<int>,other:(int,int),node:int)
    requires other.0!=g,
    ensures read(load(s,t,g,n,v,true).state,other,node)==read(s,other,node),
{}
pub proof fn theorem_invalid_width_leaves_reader_error(s:State,key:(int,int),t:int,n:int,engine:int)
    requires s.registry.contains_key(key),s.registry[key].table==t,!s.widths.contains_key(t),
    ensures read(prepare(s,key,t,Width::Invalid,engine,true,true,1),key,n)==Read::MissingTable,
{}
pub proof fn theorem_export_uses_registry(s:State,key:(int,int))
    requires s.registry.contains_key(key),s.registry[key].width>0,
    ensures export(s,key).unwrap().key==key,export(s,key).unwrap().table==s.registry[key].table,
        export(s,key).unwrap().width==s.registry[key].width,
{}
pub proof fn theorem_export_registry_restore_readback(src:State,dst:State,key:(int,int),n:int,engine:int,build:bool)
    requires src.registry.contains_key(key),src.registry[key].width>0,
        src.rows.contains_key((src.registry[key].table,key.0,n)),
        src.rows[(src.registry[key].table,key.0,n)].len()==src.registry[key].width,
        !dst.widths.contains_key(src.registry[key].table),
        !dst.rows.contains_key((src.registry[key].table,key.0,n)),dst.parents.contains((key.0,n)),
    ensures ({let a=export(src,key).unwrap();
        let s=install_registry(dst,key,src.registry[key]);
        let p=prepare(s,key,a.table,Width::Present(a.width),engine,build,true,1);
        let v=src.rows[(a.table,key.0,n)];
        read(load(p,a.table,key.0,n,v,false).state,key,n)==Read::Value(v)}),
{
    let a=export(src,key).unwrap();let s=install_registry(dst,key,src.registry[key]);
    theorem_restored_row_reaches_own_reader(s,key,a.table,n,src.rows[(a.table,key.0,n)],engine,build);
}
// The generic nodes merge guard uses only the exported first column, node_id.
// A parent in another graph therefore suppresses insertion of the wanted parent.
pub open spec fn restore_parent(s:State,g:int,n:int,merge:bool) -> Load {
    if merge && (exists|other:int| s.parents.contains((other,n))) {Load{state:s,reported:1}}
    else {Load{state:State{parents:s.parents.insert((g,n)),..s},reported:1}}
}
pub proof fn theorem_existing_row_skips_width_check(s:State,t:int,g:int,n:int,v:Seq<int>)
    requires s.widths.contains_key(t),s.rows.contains_key((t,g,n)),
    ensures load(s,t,g,n,v,true).state==s,load(s,t,g,n,v,true).reported==1,
{}
pub proof fn theorem_merge_parent_collision_blocks_vector(s:State,key:(int,int),t:int,n:int,other:int,v:Seq<int>)
    requires s.registry.contains_key(key),s.registry[key].table==t,s.widths.contains_key(t),
        s.widths[t]==v.len(),s.parents.contains((other,n)),!s.parents.contains((key.0,n)),
        !s.rows.contains_key((t,key.0,n)),
    ensures restore_parent(s,key.0,n,true).state==s,restore_parent(s,key.0,n,true).reported==1,
        load(restore_parent(s,key.0,n,true).state,t,key.0,n,v,true).reported==0,
        load(restore_parent(s,key.0,n,true).state,t,key.0,n,v,true).state.failed==s.failed+1,
        read(load(restore_parent(s,key.0,n,true).state,t,key.0,n,v,true).state,key,n)==Read::Absent,
{assert(exists|o:int| s.parents.contains((o,n))) by {assert(s.parents.contains((other,n)));}}

pub proof fn theorem_invalid_route_skips_insert(s:State,key:(int,int),t:int,n:int,v:Seq<int>,engine:int)
    ensures restore_one(s,key,t,Width::Invalid,engine,true,true,key.0,n,v,false).reported==0,
        restore_one(s,key,t,Width::Invalid,engine,true,true,key.0,n,v,false).state.failed==s.failed+1,
        restore_one(s,key,t,Width::Invalid,engine,true,true,key.0,n,v,false).state.rows==s.rows,
{}

}
