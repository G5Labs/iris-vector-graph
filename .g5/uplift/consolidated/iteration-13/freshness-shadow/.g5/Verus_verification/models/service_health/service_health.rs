// Health wrapper lifecycle at product 3eaa79cf. Provider replies are raw query,
// namespace-read and construction outcomes; status is derived here, never supplied.
// Validated schema names use ASCII; Python's wider Unicode upper() stays a boundary.
use vstd::prelude::*;
verus! {
pub enum Error { Connection, Permission, Other }
pub enum Access { Ready, Raised(Error) }
pub enum Factory { Raised(Error), Engine{id:int,connection:Access} }
pub enum Scalar { Integer(int), Ratio(int,int), Boolean(bool), Text(Seq<char>), Null, Nonfinite }
pub enum Selected { Raised(Error), Missing, Row(Scalar) }
pub enum Record { Raised(Error), Missing, Value(Seq<char>) }
pub struct Probe {pub selected:Selected,pub iris:bool,pub record:Record,pub expected:Seq<char>}
pub enum Query { Raised(Error), Returned{error:Option<Seq<char>>} }
pub enum Reason { Startup, Select, RecordRead, RecordMissing, RecordMismatch }
pub enum Status { Ok, Unavailable }
pub struct Reply {pub status:Status,pub reason:Option<Reason>}
pub open spec fn upper_char(c:char) -> char {
    match c {
        'a'=>'A','b'=>'B','c'=>'C','d'=>'D','e'=>'E','f'=>'F','g'=>'G',
        'h'=>'H','i'=>'I','j'=>'J','k'=>'K','l'=>'L','m'=>'M','n'=>'N',
        'o'=>'O','p'=>'P','q'=>'Q','r'=>'R','s'=>'S','t'=>'T','u'=>'U',
        'v'=>'V','w'=>'W','x'=>'X','y'=>'Y','z'=>'Z',_=>c,
    }
}
pub open spec fn upper(s:Seq<char>) -> Seq<char> {Seq::new(s.len(),|i:int|upper_char(s[i]))}
pub open spec fn same_schema(a:Seq<char>,b:Seq<char>) -> bool {upper(a)==upper(b)}
pub open spec fn selected_one(x:Selected) -> bool {
    match x {
        Selected::Row(Scalar::Integer(n))=>n==1,
        Selected::Row(Scalar::Ratio(n,d))=>d!=0 && n==d,
        Selected::Row(Scalar::Boolean(b))=>b,
        _=>false,
    }
}
pub open spec fn problem(p:Probe) -> Option<Reason> {
    if !selected_one(p.selected) {Some(Reason::Select)}
    else if !p.iris {None}
    else {match p.record {
        Record::Raised(_)=>Some(Reason::RecordRead),
        Record::Missing=>Some(Reason::RecordMissing),
        Record::Value(name)=>if same_schema(name,p.expected) {None}else{Some(Reason::RecordMismatch)},
    }}
}
pub open spec fn reply(reason:Option<Reason>) -> Reply {
    Reply{status:if reason.is_some(){Status::Unavailable}else{Status::Ok},reason}
}
pub struct Main {pub engine:Option<int>,pub factory_calls:nat}
pub struct MainRequest {pub state:Main,pub response:Reply,pub selected:bool,pub record_read:bool}
pub open spec fn main_boot(f:Factory) -> Main {
    Main{engine:match f {Factory::Engine{id,connection:Access::Ready}=>Some(id),_=>None},factory_calls:1}
}
// Injected engines are accessed outside create_app's constructor exception catch.
pub open spec fn main_injected(id:int,connection:Access) -> Option<Main> {
    match connection {Access::Ready=>Some(Main{engine:Some(id),factory_calls:0}),_=>None}
}
pub open spec fn main_request(s:Main,p:Probe) -> MainRequest {
    MainRequest{state:s,response:reply(if s.engine.is_none(){Some(Reason::Startup)}else{problem(p)}),
        selected:s.engine.is_some(),record_read:s.engine.is_some() && selected_one(p.selected) && p.iris}
}
pub struct Cache {pub engine:Option<int>,pub factory_calls:nat,pub close_attempts:nat}
pub struct CacheRequest {pub state:Cache,pub response:Reply,pub used:Option<int>}
pub open spec fn query_ok(q:Query) -> bool {
    match q {Query::Raised(_)=>false,Query::Returned{error}=>error.is_none() || error.unwrap().len()==0}
}
pub open spec fn cache_request(s:Cache,f:Factory,q:Query) -> CacheRequest {
    let attempted=s.engine.is_none();
    let engine=if attempted {match f {Factory::Raised(_)=>None,Factory::Engine{id,..}=>Some(id)}} else {s.engine};
    let state=Cache{engine,factory_calls:s.factory_calls+if attempted{1nat}else{0nat},..s};
    CacheRequest{state,used:engine,response:Reply{status:if engine.is_some() && query_ok(q){Status::Ok}else{Status::Unavailable},reason:None}}
}
// closed means a successfully reported close, not absence of effects on a raised close.
pub struct Reset {pub state:Cache,pub closed:Option<int>}
pub open spec fn reset(s:Cache,close:Access) -> Reset {
    Reset{state:Cache{engine:None,close_attempts:s.close_attempts+if s.engine.is_some(){1nat}else{0nat},..s},
        closed:if s.engine.is_some() && matches!(close,Access::Ready){s.engine}else{None}}
}
pub open spec fn empty_cache() -> Cache {Cache{engine:None,factory_calls:0,close_attempts:0}}
pub open spec fn clean_query() -> Query {Query::Returned{error:None}}
pub open spec fn attempt_raised(s:Cache,f:Factory,q:Query) -> bool {
    (s.engine.is_none() && matches!(f,Factory::Raised(_))) || matches!(q,Query::Raised(_))
}
pub struct QueryRun {pub state:Cache,pub ok:bool,pub attempts:nat}
// _run_cypher is the current competing cache writer: one exception-triggered reset/retry.
// A folded result.error is examined AFTER the loop and does not trigger reset.
pub open spec fn run_query(s:Cache,first:Factory,q1:Query,next:Factory,q2:Query,close:Access) -> QueryRun {
    let a=cache_request(s,first,q1);
    if attempt_raised(s,first,q1) {
        let b=cache_request(reset(a.state,close).state,next,q2);
        QueryRun{state:b.state,ok:matches!(b.response.status,Status::Ok),attempts:2}
    } else {QueryRun{state:a.state,ok:matches!(a.response.status,Status::Ok),attempts:1}}
}

pub proof fn theorem_main_refuses_wrong_probe(s:Main,p:Probe)
    requires s.engine.is_some(),!selected_one(p.selected),
    ensures main_request(s,p).response.status==Status::Unavailable,
        main_request(s,p).response.reason==Some(Reason::Select),!main_request(s,p).record_read,
{}
pub proof fn theorem_main_checks_actual_namespace(s:Main,p:Probe)
    requires s.engine.is_some(),selected_one(p.selected),p.iris,
    ensures main_request(s,p).record_read,
        (p.record is Missing ==> main_request(s,p).response.reason==Some(Reason::RecordMissing)),
        (p.record is Raised ==> main_request(s,p).response.reason==Some(Reason::RecordRead)),
        (p.record matches Record::Value(name) ==> (
            main_request(s,p).response.status==Status::Ok <==> same_schema(name,p.expected))),
{}
pub proof fn theorem_standin_skips_namespace(s:Main,p:Probe)
    requires s.engine.is_some(),selected_one(p.selected),!p.iris,
    ensures main_request(s,p).response.status==Status::Ok,!main_request(s,p).record_read,
{}
pub proof fn lemma_upper_idempotent(c:char)
    ensures upper_char(upper_char(c))==upper_char(c),
{}
pub proof fn theorem_ascii_case_match(s:Main,p:Probe,name:Seq<char>)
    requires s.engine.is_some(),selected_one(p.selected),p.iris,
        p.record==Record::Value(name),p.expected==upper(name),
    ensures main_request(s,p).response.status==Status::Ok,
{
    assert(upper(upper(name)) =~= upper(name)) by {
        assert forall|i:int| 0<=i<name.len() implies upper(upper(name))[i]==upper(name)[i] by {
            lemma_upper_idempotent(name[i]);
        }
    }
}
pub proof fn theorem_sample_startup_absence_is_sticky(p:Probe,q:Probe,error:Error)
    ensures main_request(main_request(main_boot(Factory::Raised(error)),p).state,q).state.engine.is_none(),
        main_request(main_request(main_boot(Factory::Raised(error)),p).state,q).state.factory_calls==1,
        main_request(main_request(main_boot(Factory::Raised(error)),p).state,q).response.status==Status::Unavailable,
        !main_request(main_boot(Factory::Raised(error)),p).selected,
{}
pub proof fn theorem_constructor_and_injected_refusal_differ(id:int,error:Error)
    ensures main_boot(Factory::Engine{id,connection:Access::Raised(error)}).engine.is_none(),
        main_injected(id,Access::Raised(error)).is_none(),
        main_injected(id,Access::Ready).unwrap().engine==Some(id),
{}
pub proof fn theorem_bound_sample_can_recover(s:Main,bad:Probe,good:Probe)
    requires s.engine.is_some(),!selected_one(bad.selected),selected_one(good.selected),!good.iris,
    ensures main_request(s,bad).response.status==Status::Unavailable,
        main_request(main_request(s,bad).state,good).response.status==Status::Ok,
        main_request(main_request(s,bad).state,good).state.factory_calls==s.factory_calls,
{}
pub proof fn theorem_failed_construction_is_retried(error:Error,id:int)
    ensures ({let a=cache_request(empty_cache(),Factory::Raised(error),clean_query());
        let b=cache_request(a.state,Factory::Engine{id,connection:Access::Ready},clean_query());
        a.response.status==Status::Unavailable && a.state.engine.is_none() && a.state.factory_calls==1
        && b.response.status==Status::Ok && b.state.engine==Some(id) && b.state.factory_calls==2}),
{}
pub proof fn theorem_cached_query_failure_keeps_engine(s:Cache,f:Factory,error:Error)
    requires s.engine.is_some(),
    ensures cache_request(s,f,Query::Raised(error)).response.status==Status::Unavailable,
        cache_request(s,f,Query::Raised(error)).state.engine==s.engine,
        cache_request(s,f,Query::Raised(error)).state.factory_calls==s.factory_calls,
{}
pub proof fn theorem_folded_error_controls_status(s:Cache,f:Factory,msg:Seq<char>)
    requires s.engine.is_some(),msg.len()>0,
    ensures cache_request(s,f,Query::Returned{error:Some(msg)}).response.status==Status::Unavailable,
        cache_request(s,f,Query::Returned{error:None}).response.status==Status::Ok,
        cache_request(s,f,Query::Returned{error:Some(seq![])}).response.status==Status::Ok,
{}
pub proof fn theorem_cache_recovers_without_new_factory(s:Cache,f:Factory,error:Error)
    requires s.engine.is_some(),
    ensures cache_request(cache_request(s,f,Query::Raised(error)).state,f,clean_query()).response.status==Status::Ok,
        cache_request(cache_request(s,f,Query::Raised(error)).state,f,clean_query()).state.engine==s.engine,
        cache_request(cache_request(s,f,Query::Raised(error)).state,f,clean_query()).state.factory_calls==s.factory_calls,
{}
pub proof fn theorem_reset_clears_even_when_close_fails(s:Cache,error:Error)
    ensures reset(s,Access::Raised(error)).state.engine.is_none(),reset(s,Access::Raised(error)).closed.is_none(),
        reset(s,Access::Raised(error)).state.close_attempts==s.close_attempts+if s.engine.is_some(){1nat}else{0nat},
{}
pub proof fn theorem_reset_allows_replacement(s:Cache,id:int,close:Access)
    ensures cache_request(reset(s,close).state,Factory::Engine{id,connection:Access::Ready},clean_query()).state.engine==Some(id),
        cache_request(reset(s,close).state,Factory::Engine{id,connection:Access::Ready},clean_query()).state.factory_calls==s.factory_calls+1,
{}
pub proof fn theorem_success_is_probe_specific(s:Cache,f:Factory,p:Probe)
    requires s.engine.is_some(),!selected_one(p.selected),
    ensures cache_request(s,f,clean_query()).response.status==Status::Ok,
        problem(p)==Some(Reason::Select),
{}
pub proof fn theorem_query_exception_replaces_cache(s:Cache,f:Factory,id:int,error:Error,close:Access)
    requires s.engine.is_some(),
    ensures run_query(s,f,Query::Raised(error),Factory::Engine{id,connection:Access::Ready},clean_query(),close).state.engine==Some(id),
        run_query(s,f,Query::Raised(error),Factory::Engine{id,connection:Access::Ready},clean_query(),close).state.factory_calls==s.factory_calls+1,
        run_query(s,f,Query::Raised(error),Factory::Engine{id,connection:Access::Ready},clean_query(),close).attempts==2,
        run_query(s,f,Query::Raised(error),Factory::Engine{id,connection:Access::Ready},clean_query(),close).ok,
{}
pub proof fn theorem_folded_query_failure_does_not_reset(s:Cache,f:Factory,next:Factory,msg:Seq<char>,q2:Query,close:Access)
    requires s.engine.is_some(),msg.len()>0,
    ensures run_query(s,f,Query::Returned{error:Some(msg)},next,q2,close).state==s,
        run_query(s,f,Query::Returned{error:Some(msg)},next,q2,close).attempts==1,
        !run_query(s,f,Query::Returned{error:Some(msg)},next,q2,close).ok,
{}
pub proof fn theorem_second_query_exception_stops(s:Cache,f:Factory,id:int,a:Error,b:Error,close:Access)
    requires s.engine.is_some(),
    ensures run_query(s,f,Query::Raised(a),Factory::Engine{id,connection:Access::Ready},Query::Raised(b),close).attempts==2,
        !run_query(s,f,Query::Raised(a),Factory::Engine{id,connection:Access::Ready},Query::Raised(b),close).ok,
        run_query(s,f,Query::Raised(a),Factory::Engine{id,connection:Access::Ready},Query::Raised(b),close).state.engine==Some(id),
{}
}
