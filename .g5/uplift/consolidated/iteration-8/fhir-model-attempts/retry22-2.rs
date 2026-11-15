// As-built task workflow at 3eaa79cf; spec transcription, not product-body proof.
use vstd::prelude::*;
verus! {
pub type Str=Seq<char>;
pub open spec fn sync_class()->Str {seq!['G','r','a','p','h','.','K','G','.','F','H','I','R','G','r','a','p','h','S','y','n','c','T','a','s','k']}
pub open spec fn graph_key()->Str {seq!['G','r','a','p','h','I','d']}
pub open spec fn error_status()->Str {seq!['e','r','r','o','r']}
pub open spec fn pairs_tail(xs:Seq<Str>)->Seq<Str> {if xs.len()>2{xs.subrange(2,xs.len() as int)}else{seq![]}}
// Valid decoded native list, NOT a prefiltered map. Odd last GraphId uses
// $LISTGET's empty default. Later matching key replaces earlier, even with empty.
pub open spec fn graph_setting(xs:Seq<Str>)->Option<Str>
    decreases xs.len(),
{if xs.len()==0{None}else{
    let tail=graph_setting(pairs_tail(xs));
    if tail.is_some(){tail}else{if xs[0]==graph_key(){Some(if xs.len()>1{xs[1]}else{seq![]})}else{None}}
}}
pub open spec fn saved_graph(xs:Seq<Str>)->Str {match graph_setting(xs){None=>seq![],Some(g)=>g}}
pub struct Task {pub class:Str,pub namespace:Str,pub settings:Seq<Str>,pub minutes:int}
pub struct Row {pub task_id:Str,pub interval:int,pub version:Option<int>}
pub struct State {pub rows:Map<Str,Row>,pub tasks:Map<Str,Task>}
pub enum Owner {Own,Class,Namespace,Graph}
pub open spec fn ownership(t:Task,g:Str,ns:Str)->Owner {
    if t.class!=sync_class(){Owner::Class}else if t.namespace!=ns{Owner::Namespace}
    else if saved_graph(t.settings)!=g{Owner::Graph}else{Owner::Own}
}
pub open spec fn object_exists(s:State,id:Str)->bool {id.len()>0 && s.tasks.contains_key(id)}
pub enum Interval {Omitted,Integer(int),Other}
pub open spec fn caller_interval(raw:Interval)->Option<int> {
    match raw {Interval::Omitted=>Some(0),Interval::Integer(n)=>if n>=60{Some(n)}else{None},_=>None}
}
pub open spec fn effective(sent:int,registered:int)->int {if sent>0{sent}else{registered}}
pub open spec fn minutes(n:int)->int {n/60+if n%60>0{1int}else{0int}}
pub enum Fault {None,Assign,Save,Delete,Sql}
pub enum Op {Assign,Save,Delete,Sql}
pub enum Reason {Caller,Unregistered,Interval,Class,Namespace,Graph,Assign,Save,Delete,Sql}
pub enum Reply {Error(Reason),Scheduled{id:Str,seconds:int,minutes:int},Unscheduled{old_id:Str,removed:bool}}
pub struct Outcome {pub state:State,pub reply:Reply,pub ops:Seq<Op>}
pub open spec fn fail(s:State,reason:Reason,ops:Seq<Op>)->Outcome {Outcome{state:s,reply:Reply::Error(reason),ops}}
pub open spec fn owner_reason(o:Owner)->Reason {match o {Owner::Class=>Reason::Class,Owner::Namespace=>Reason::Namespace,_=>Reason::Graph}}
pub open spec fn scheduled_task(g:Str,ns:Str,n:int)->Task {
    Task{class:sync_class(),namespace:ns,settings:seq![graph_key(),g],minutes:minutes(n)}
}
// Native port input is the numeric caller carrier, not a supplied ownership bit.
// Fresh allocation is a provider premise when no object is reused (fresh must be
// a nonempty unused ID); arbitrary raw stored IDs and all task rows remain inputs.
pub open spec fn schedule(s:State,g:Str,ns:Str,sent:int,fresh:Str,fault:Fault)->Outcome {
    if !s.rows.contains_key(g){fail(s,Reason::Unregistered,seq![])}else{
        let row=s.rows[g];let n=effective(sent,row.interval);
        if n<60{fail(s,Reason::Interval,seq![])}else{
            let has=object_exists(s,row.task_id);
            if has && ownership(s.tasks[row.task_id],g,ns)!=Owner::Own {
                fail(s,owner_reason(ownership(s.tasks[row.task_id],g,ns)),seq![])
            }else if fault==Fault::Assign {fail(s,Reason::Assign,seq![Op::Assign])}
            else if fault==Fault::Save {fail(s,Reason::Save,seq![Op::Assign,Op::Save])}
            else {
                let id=if has{row.task_id}else{fresh};
                let saved=State{tasks:s.tasks.insert(id,scheduled_task(g,ns,n)),..s};
                if fault==Fault::Sql {fail(saved,Reason::Sql,seq![Op::Assign,Op::Save,Op::Sql])}
                else {Outcome{state:State{rows:saved.rows.insert(g,Row{task_id:id,interval:n,..row}),..saved},
                    reply:Reply::Scheduled{id,seconds:n,minutes:minutes(n)},ops:seq![Op::Assign,Op::Save,Op::Sql]}}
            }
        }
    }
}
pub open spec fn public_schedule(s:State,g:Str,ns:Str,raw:Interval,fresh:Str,fault:Fault)->Outcome {
    match caller_interval(raw){None=>fail(s,Reason::Caller,seq![]),Some(n)=>schedule(s,g,ns,n,fresh,fault)}
}
pub open spec fn unschedule(s:State,g:Str,ns:Str,fault:Fault)->Outcome {
    if !s.rows.contains_key(g){fail(s,Reason::Unregistered,seq![])}else{
        let row=s.rows[g];let has=object_exists(s,row.task_id);
        if has && ownership(s.tasks[row.task_id],g,ns)!=Owner::Own {
            fail(s,owner_reason(ownership(s.tasks[row.task_id],g,ns)),seq![])
        }else if has && fault==Fault::Delete {fail(s,Reason::Delete,seq![Op::Delete])}
        else {
            let deleted=State{tasks:if has{s.tasks.remove(row.task_id)}else{s.tasks},..s};
            let ops=if has{seq![Op::Delete,Op::Sql]}else{seq![Op::Sql]};
            if fault==Fault::Sql {fail(deleted,Reason::Sql,ops)}
            else{Outcome{state:State{rows:deleted.rows.insert(g,Row{task_id:seq![],..row}),..deleted},
                reply:Reply::Unscheduled{old_id:row.task_id,removed:has},ops}}
        }
    }
}
// Final Status point projection: actual status also reads resource/count metadata.
// Missing/Future version and provider refusal raise rather than fabricating an ID.
pub enum Status {Error,Value{task_id:Str,interval:int,version:Option<int>,stale:bool}}
pub open spec fn status(s:State,g:Str,current:int,provider_read:bool)->Status {
    if !provider_read || !s.rows.contains_key(g){Status::Error}else{
        let row=s.rows[g];
        if row.version.is_some() && row.version.unwrap()>current {Status::Error}
        else{Status::Value{task_id:row.task_id,interval:row.interval,version:row.version,
            stale:row.version.is_none() || row.version.unwrap()<current}}
    }
}
pub enum SyncReply {Thrown,Malformed,Parsed(Str)}
pub struct Invocation {pub namespace:Str,pub graph:Str,pub success:bool}
pub open spec fn on_task(graph:Str,ns:Str,reply:SyncReply)->Invocation {
    Invocation{namespace:ns,graph,success:match reply{SyncReply::Parsed(st)=>st!=error_status(),_=>false}}
}
// TaskManager loader assumption is explicit: canonical AssignSettings [GraphId,g]
// loads definition.GraphId=g. Duplicate raw lists are modeled for CheckOwnTask;
// arbitrary loader behavior is not proved. This is the specified loader fragment.
pub open spec fn tick(s:State,id:Str,reply:SyncReply)->Option<Invocation> {
    if s.tasks.contains_key(id) && s.tasks[id].class==sync_class() {
        Some(on_task(saved_graph(s.tasks[id].settings),s.tasks[id].namespace,reply))
    }else{None}
}
pub proof fn theorem_settings_last_key_wins(g:Str,other:Str)
    ensures saved_graph(seq![graph_key(),g,graph_key(),other])==other,
        saved_graph(seq![graph_key(),other,graph_key(),g])==g,
{reveal_with_fuel(graph_setting,3);}
pub proof fn theorem_odd_or_missing_graph_key(g:Str,other:Str)
    requires other!=graph_key(),
    ensures saved_graph(seq![graph_key()])==seq![],saved_graph(seq![other,g])==seq![],
        saved_graph(seq![graph_key(),g,graph_key()])==seq![],
{reveal_with_fuel(graph_setting,3);}
pub proof fn theorem_wrong_field_refuses(t:Task,g:Str,ns:Str)
    ensures t.class!=sync_class() ==> ownership(t,g,ns)==Owner::Class,
        t.class==sync_class() && t.namespace!=ns ==> ownership(t,g,ns)==Owner::Namespace,
        t.class==sync_class() && t.namespace==ns && saved_graph(t.settings)!=g ==> ownership(t,g,ns)==Owner::Graph,
{}
pub proof fn theorem_caller_none_and_explicit_zero()
    ensures caller_interval(Interval::Omitted)==Some(0),caller_interval(Interval::Integer(0))==None,
        caller_interval(Interval::Integer(59))==None,caller_interval(Interval::Integer(60))==Some(60),caller_interval(Interval::Other)==None,
{}
pub proof fn theorem_rounding_bounds(n:int)
    requires n>=60,
    ensures minutes(n)>=1,minutes(n)*60>=n,(minutes(n)-1)*60<n,
{}
pub proof fn theorem_effective_interval(raw:int,registered:int)
    ensures raw<=0 ==> effective(raw,registered)==registered,
        raw>0 ==> effective(raw,registered)==raw,minutes(60)==1,minutes(61)==2,
{}
pub proof fn theorem_existing_foreign_stutters(s:State,g:Str,ns:Str,sent:int,fresh:Str,fault:Fault)
    requires s.rows.contains_key(g),object_exists(s,s.rows[g].task_id),ownership(s.tasks[s.rows[g].task_id],g,ns)!=Owner::Own,
    ensures schedule(s,g,ns,sent,fresh,fault).state==s,unschedule(s,g,ns,fault).state==s,
        schedule(s,g,ns,sent,fresh,fault).ops==seq![],unschedule(s,g,ns,fault).ops==seq![],
{}
pub proof fn theorem_stale_id_creates_and_status_reads(s:State,g:Str,ns:Str,fresh:Str,current:int)
    requires s.rows.contains_key(g),s.rows[g].interval>=60,!object_exists(s,s.rows[g].task_id),fresh.len()>0,!s.tasks.contains_key(fresh),
        s.rows[g].version.is_none() || s.rows[g].version.unwrap()<=current,
    ensures public_schedule(s,g,ns,Interval::Omitted,fresh,Fault::None).state.rows[g].task_id==fresh,
        public_schedule(s,g,ns,Interval::Omitted,fresh,Fault::None).state.tasks.contains_key(fresh),
        status(public_schedule(s,g,ns,Interval::Omitted,fresh,Fault::None).state,g,current,true)
            ==(Status::Value{task_id:fresh,interval:s.rows[g].interval,version:s.rows[g].version,
                stale:s.rows[g].version.is_none() || s.rows[g].version.unwrap()<current}),
{}
pub proof fn theorem_existing_own_reuses_id(s:State,g:Str,ns:Str,fresh:Str,n:int)
    requires s.rows.contains_key(g),object_exists(s,s.rows[g].task_id),ownership(s.tasks[s.rows[g].task_id],g,ns)==Owner::Own,n>=60,
    ensures public_schedule(s,g,ns,Interval::Integer(n),fresh,Fault::None).state.rows[g].task_id==s.rows[g].task_id,
        public_schedule(s,g,ns,Interval::Integer(n),fresh,Fault::None).state.tasks[s.rows[g].task_id].minutes==minutes(n),
{}
pub proof fn theorem_assign_or_save_failure_precedes_sql(s:State,g:Str,ns:Str,fresh:Str,n:int,fault:Fault)
    requires s.rows.contains_key(g),n>=60,(!object_exists(s,s.rows[g].task_id) || ownership(s.tasks[s.rows[g].task_id],g,ns)==Owner::Own),
        fault==Fault::Assign || fault==Fault::Save,
    ensures schedule(s,g,ns,n,fresh,fault).state==s,!schedule(s,g,ns,n,fresh,fault).ops.contains(Op::Sql),
{}
pub proof fn theorem_sql_failure_preserves_saved_orphan(s:State,g:Str,ns:Str,fresh:Str,n:int)
    requires s.rows.contains_key(g),n>=60,!object_exists(s,s.rows[g].task_id),fresh.len()>0,!s.tasks.contains_key(fresh),
    ensures schedule(s,g,ns,n,fresh,Fault::Sql).reply==Reply::Error(Reason::Sql),
        schedule(s,g,ns,n,fresh,Fault::Sql).state.rows==s.rows,
        schedule(s,g,ns,n,fresh,Fault::Sql).state.tasks.contains_key(fresh),
        schedule(s,g,ns,n,fresh,Fault::Sql).state.tasks[fresh]==scheduled_task(g,ns,n),
{}
pub proof fn theorem_unschedule_stale_clears_only_registry(s:State,g:Str,ns:Str)
    requires s.rows.contains_key(g),!object_exists(s,s.rows[g].task_id),
    ensures unschedule(s,g,ns,Fault::None).state.tasks==s.tasks,
        unschedule(s,g,ns,Fault::None).state.rows[g].task_id==seq![],
        unschedule(s,g,ns,Fault::None).reply==(Reply::Unscheduled{old_id:s.rows[g].task_id,removed:false}),
{}
pub proof fn theorem_unschedule_own_deletes_and_reports_old_id(s:State,g:Str,ns:Str)
    requires s.rows.contains_key(g),object_exists(s,s.rows[g].task_id),ownership(s.tasks[s.rows[g].task_id],g,ns)==Owner::Own,
    ensures !unschedule(s,g,ns,Fault::None).state.tasks.contains_key(s.rows[g].task_id),
        unschedule(s,g,ns,Fault::None).state.rows[g].task_id==seq![],
        unschedule(s,g,ns,Fault::None).reply==(Reply::Unscheduled{old_id:s.rows[g].task_id,removed:true}),
{}
pub proof fn theorem_delete_failure_precedes_sql(s:State,g:Str,ns:Str)
    requires s.rows.contains_key(g),object_exists(s,s.rows[g].task_id),ownership(s.tasks[s.rows[g].task_id],g,ns)==Owner::Own,
    ensures unschedule(s,g,ns,Fault::Delete).state==s,unschedule(s,g,ns,Fault::Delete).ops==seq![Op::Delete],
{}
pub proof fn theorem_sql_failure_keeps_deleted_task_and_stale_id(s:State,g:Str,ns:Str)
    requires s.rows.contains_key(g),object_exists(s,s.rows[g].task_id),ownership(s.tasks[s.rows[g].task_id],g,ns)==Owner::Own,
    ensures unschedule(s,g,ns,Fault::Sql).reply==Reply::Error(Reason::Sql),unschedule(s,g,ns,Fault::Sql).state.rows==s.rows,
        !unschedule(s,g,ns,Fault::Sql).state.tasks.contains_key(s.rows[g].task_id),
{}
pub proof fn theorem_orphan_survives_unschedule_and_can_tick(s:State,g:Str,ns:Str,fresh:Str,n:int,reply:SyncReply)
    requires s.rows.contains_key(g),n>=60,!object_exists(s,s.rows[g].task_id),fresh.len()>0,!s.tasks.contains_key(fresh),
    ensures ({let saved=schedule(s,g,ns,n,fresh,Fault::Sql).state;let removed=unschedule(saved,g,ns,Fault::None);
        removed.reply==(Reply::Unscheduled{old_id:s.rows[g].task_id,removed:false}) && removed.state.rows[g].task_id==seq![]
        && tick(removed.state,fresh,reply)==Some(on_task(g,ns,reply))}),
{reveal_with_fuel(graph_setting,2);}
pub proof fn theorem_schedule_retry_can_leave_two_tasks(s:State,g:Str,ns:Str,first:Str,second:Str,n:int)
    requires s.rows.contains_key(g),n>=60,!object_exists(s,s.rows[g].task_id),first.len()>0,second.len()>0,
        first!=second,!s.tasks.contains_key(first),!s.tasks.contains_key(second),
    ensures ({let saved=schedule(s,g,ns,n,first,Fault::Sql).state;let retried=schedule(saved,g,ns,n,second,Fault::None).state;
        retried.rows[g].task_id==second && retried.tasks.contains_key(first) && retried.tasks.contains_key(second)}),
{}
pub proof fn theorem_delete_sql_failure_retry_is_stale(s:State,g:Str,ns:Str)
    requires s.rows.contains_key(g),object_exists(s,s.rows[g].task_id),ownership(s.tasks[s.rows[g].task_id],g,ns)==Owner::Own,
    ensures ({let partial=unschedule(s,g,ns,Fault::Sql).state;let retried=unschedule(partial,g,ns,Fault::None);
        retried.reply==(Reply::Unscheduled{old_id:s.rows[g].task_id,removed:false}) && retried.state.rows[g].task_id==seq![]}),
{}
pub proof fn theorem_final_status_does_not_validate_task(s:State,g:Str,current:int)
    requires s.rows.contains_key(g),s.rows[g].version.is_none() || s.rows[g].version.unwrap()<=current,
    ensures status(s,g,current,true)==status(State{tasks:Map::empty(),..s},g,current,true),
        status(s,g,current,false)==Status::Error,
{}
pub proof fn theorem_future_version_status_refuses(s:State,g:Str,current:int)
    requires s.rows.contains_key(g),s.rows[g].version.is_some(),s.rows[g].version.unwrap()>current,
    ensures status(s,g,current,true)==Status::Error,
{}
pub proof fn theorem_successful_schedule_derives_tick_target(s:State,g:Str,ns:Str,fresh:Str,n:int,reply:SyncReply)
    requires s.rows.contains_key(g),n>=60,(!object_exists(s,s.rows[g].task_id) || ownership(s.tasks[s.rows[g].task_id],g,ns)==Owner::Own),
    ensures ({let done=public_schedule(s,g,ns,Interval::Integer(n),fresh,Fault::None);
        tick(done.state,done.state.rows[g].task_id,reply)==Some(on_task(g,ns,reply))}),
{reveal_with_fuel(graph_setting,2);}
pub proof fn theorem_busy_is_success_error_and_parse_failures_fail(g:Str,ns:Str)
    ensures on_task(g,ns,SyncReply::Parsed(seq!['b','u','s','y'])).success,
        on_task(g,ns,SyncReply::Parsed(seq!['o','k'])).success,
        !on_task(g,ns,SyncReply::Parsed(error_status())).success,
        !on_task(g,ns,SyncReply::Thrown).success,!on_task(g,ns,SyncReply::Malformed).success,
{}
pub proof fn theorem_other_graph_registry_and_task_frame(s:State,g:Str,other:Str,ns:Str,n:int,fresh:Str,id:Str)
    requires s.rows.contains_key(other),other!=g,s.tasks.contains_key(id),id!=fresh,
        s.rows.contains_key(g) ==> id!=s.rows[g].task_id,
    ensures schedule(s,g,ns,n,fresh,Fault::None).state.rows[other]==s.rows[other],
        schedule(s,g,ns,n,fresh,Fault::None).state.tasks[id]==s.tasks[id],
        unschedule(s,g,ns,Fault::None).state.rows[other]==s.rows[other],
        unschedule(s,g,ns,Fault::None).state.tasks[id]==s.tasks[id],
{}
}
