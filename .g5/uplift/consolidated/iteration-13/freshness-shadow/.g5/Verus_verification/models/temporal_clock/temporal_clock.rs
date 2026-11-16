// Raw timestamp -> Python port -> selected server writer -> global -> final window.
// As-built transcription at 3eaa79cf; NOT a proof of Python/ObjectScript bodies.
#[path="../temporal_restore/temporal_restore.rs"]
pub mod stores;
use vstd::prelude::*;
verus! {
// Decoded Python values. Text(n) is a nonempty string whose int() is n.
// Coercible covers other successfully int-convertible inputs, retaining original
// truthiness (e.g. 0.5 is truthy but int(0.5)==0). Parsing itself is not verified.
pub enum Raw { Missing, Null, Empty, Number(int), Text(int), Coercible{value:int,truthy:bool}, Bad }
pub open spec fn present(r:Raw)->bool {r!=Raw::Missing}
pub open spec fn supplied(r:Raw)->bool {r!=Raw::Missing && r!=Raw::Null && r!=Raw::Empty}
pub open spec fn truthy(r:Raw)->bool {
    match r {Raw::Missing|Raw::Null|Raw::Empty=>false,Raw::Number(n)=>n!=0,
        Raw::Coercible{value:_,truthy:b}=>b,_=>true}
}
pub open spec fn integer(r:Raw)->Option<int> {
    match r {Raw::Number(n)|Raw::Text(n)=>Some(n),Raw::Coercible{value:n,truthy:_}=>Some(n),_=>None}
}
pub open spec fn single_payload(r:Raw)->Option<int> {
    if r==Raw::Missing || r==Raw::Null {Some(0)}
    else {let n=integer(r);if n.is_some() && n.unwrap()>=0 {n}else{None}}
}
// shape_ok retains all other required roles/unknown-key checks; it is not an
// assumed timestamp decision. Both raw aliases remain inputs to this producer.
pub open spec fn bulk_shape(short:Raw,long:Raw,shape_ok:bool)->bool {
    shape_ok && (supplied(short)||supplied(long))
}
pub open spec fn bulk_selected(short:Raw,long:Raw)->Raw {
    if truthy(short){short}else{if present(long){long}else{Raw::Number(0)}}
}
pub open spec fn bulk_payload(short:Raw,long:Raw,shape_ok:bool)->Option<int> {
    if bulk_shape(short,long,shape_ok){integer(bulk_selected(short,long))}else{None}
}
pub enum NativeTime { Empty, Number(int) }
pub open spec fn single_clock(t:NativeTime,now:int)->int {
    match t {NativeTime::Empty=>now,NativeTime::Number(n)=>n}
}
pub open spec fn bulk_clock(n:int,now:int)->int {if n==0{now}else{n}}
pub enum Route { Single, Counts, PrewriteFallback }
pub open spec fn coordinate(n:int,route:Route,now:int)->int {
    match route {Route::Counts=>bulk_clock(n,now),_=>single_clock(NativeTime::Number(n),now)}
}
pub open spec fn at(identity:stores::Edge,ts:int)->stores::Edge {(identity.0,ts,identity.2,identity.3,identity.4)}
pub struct Outcome {pub state:stores::Global,pub accepted:bool,pub count:nat,pub collisions:nat,pub time:Option<int>}
pub open spec fn refused(s:stores::Global)->Outcome {Outcome{state:s,accepted:false,count:0,collisions:0,time:None}}
// Default insert mode, provider success or refusal before any write. A Counts
// exception before effects selects fallback; partial-prefix failures are residual.
pub open spec fn write(s:stores::Global,identity:stores::Edge,n:int,route:Route,now:int,provider_ok:bool,w:int,reverse:bool)->Outcome {
    if !provider_ok {refused(s)} else {
        let ts=coordinate(n,route,now);let e=at(identity,ts);let exists=s.contains_key(stores::out(e));
        Outcome{state:stores::insert(s,e,w,Map::empty(),reverse),accepted:true,
            count:if route==Route::Counts && exists{0}else{1},
            collisions:if route==Route::Counts && exists{1}else{0},time:Some(ts)}
    }
}
pub open spec fn call_single(s:stores::Global,e:stores::Edge,r:Raw,now:int,ok:bool,w:int,reverse:bool)->Outcome {
    match single_payload(r){None=>refused(s),Some(n)=>write(s,e,n,Route::Single,now,ok,w,reverse)}
}
pub open spec fn call_bulk(s:stores::Global,e:stores::Edge,short:Raw,long:Raw,shape_ok:bool,available:bool,now:int,ok:bool,w:int,reverse:bool)->Outcome {
    match bulk_payload(short,long,shape_ok){None=>refused(s),Some(n)=>write(s,e,n,
        if available{Route::Counts}else{Route::PrewriteFallback},now,ok,w,reverse)}
}
pub open spec fn observe(r:Outcome,e:stores::Edge,ts:int,g:int,lo:int,hi:int,reverse:bool,args:stores::paging::Args)->Option<int> {
    stores::weight(r.state,at(e,ts),reverse,g,lo,hi,args)
}
pub struct Request {pub edge:stores::Edge,pub short:Raw,pub long:Raw,pub shape_ok:bool,pub w:int,pub reverse:bool}
pub open spec fn batch_valid(es:Seq<Request>)->bool {
    forall|i:int| 0<=i<es.len() ==> bulk_payload(es[i].short,es[i].long,es[i].shape_ok).is_some()
}
// clocks[i] is the clock reading at item i, if that item needs it. No shared,
// monotone or nonzero clock is assumed. Missing test-environment clock entries
// default to zero; correspondence requires one available reading per item.
pub open spec fn fold(s:stores::Global,es:Seq<Request>,available:bool,clocks:Seq<int>)->Outcome
    decreases es.len(),
{
    if es.len()==0 {Outcome{state:s,accepted:true,count:0,collisions:0,time:None}}
    else {
        let e=es[0];let now=if clocks.len()>0{clocks[0]}else{0};
        let one=call_bulk(s,e.edge,e.short,e.long,e.shape_ok,available,now,true,e.w,e.reverse);
        let tail=fold(one.state,es.drop_first(),available,if clocks.len()>0{clocks.drop_first()}else{clocks});
        Outcome{state:tail.state,accepted:true,count:one.count+tail.count,collisions:one.collisions+tail.collisions,time:None}
    }
}
pub open spec fn call_batch(s:stores::Global,es:Seq<Request>,available:bool,clocks:Seq<int>,provider_ok:bool)->Outcome {
    if es.len()==0 {fold(s,es,available,clocks)}
    else if !batch_valid(es) || !provider_ok {refused(s)}
    else {fold(s,es,available,clocks)}
}
pub proof fn theorem_batch_validation_precedes_any_write(s:stores::Global,es:Seq<Request>,available:bool,clocks:Seq<int>,i:int)
    requires 0<=i<es.len(),bulk_payload(es[i].short,es[i].long,es[i].shape_ok).is_none(),
    ensures call_batch(s,es,available,clocks,true).state==s,
        !call_batch(s,es,available,clocks,true).accepted,call_batch(s,es,available,clocks,true).count==0,
{}
pub proof fn theorem_empty_batch_no_provider_dependency(s:stores::Global,available:bool,clocks:Seq<int>,ok:bool)
    ensures call_batch(s,seq![],available,clocks,ok).state==s,
        call_batch(s,seq![],available,clocks,ok).accepted,call_batch(s,seq![],available,clocks,ok).count==0,
{}
pub proof fn theorem_single_omission_and_epoch_share_carrier()
    ensures single_payload(Raw::Missing)==Some(0),single_payload(Raw::Null)==Some(0),
        single_payload(Raw::Number(0))==Some(0),single_payload(Raw::Text(0))==Some(0),
{}
pub proof fn theorem_single_validation(n:int)
    requires n<0,
    ensures single_payload(Raw::Number(n))==None,single_payload(Raw::Text(n))==None,
        single_payload(Raw::Empty)==None,single_payload(Raw::Bad)==None,
{}
pub proof fn theorem_bulk_missing_null_empty_refuse(shape:bool)
    ensures bulk_payload(Raw::Missing,Raw::Missing,shape)==None,
        bulk_payload(Raw::Null,Raw::Missing,shape)==None,
        bulk_payload(Raw::Empty,Raw::Missing,shape)==None,
        bulk_payload(Raw::Number(0),Raw::Missing,false)==None,
{}
pub proof fn theorem_alias_truthiness_changes_coordinate(n:int)
    requires n!=0,
    ensures bulk_payload(Raw::Number(0),Raw::Number(n),true)==Some(n),
        bulk_payload(Raw::Text(0),Raw::Number(n),true)==Some(0),
{}
pub proof fn theorem_present_null_is_not_missing()
    ensures bulk_payload(Raw::Number(0),Raw::Null,true)==None,
        bulk_payload(Raw::Number(0),Raw::Missing,true)==Some(0),
{}
pub proof fn theorem_bulk_keeps_negative(n:int)
    requires n<0,
    ensures bulk_payload(Raw::Number(n),Raw::Missing,true)==Some(n),
        single_payload(Raw::Number(n))==None,
{}
pub proof fn theorem_coercion_retains_preconversion_truthiness(n:int)
    ensures bulk_payload(Raw::Coercible{value:0,truthy:true},Raw::Number(n),true)==Some(0),
        bulk_payload(Raw::Coercible{value:0,truthy:false},Raw::Number(n),true)==Some(n),
{}
pub proof fn theorem_server_empty_and_zero_differ(now:int)
    requires now!=0,
    ensures single_clock(NativeTime::Empty,now)==now,single_clock(NativeTime::Number(0),now)==0,
        bulk_clock(0,now)==now,single_clock(NativeTime::Number(0),now)!=bulk_clock(0,now),
{}
pub proof fn theorem_positive_explicit_agrees(n:int,now:int)
    requires n>0,
    ensures coordinate(n,Route::Single,now)==n,coordinate(n,Route::Counts,now)==n,
        coordinate(n,Route::PrewriteFallback,now)==n,
{}
pub proof fn theorem_per_item_clock_is_not_batch_constant(now1:int,now2:int)
    requires now1!=now2,
    ensures coordinate(0,Route::Counts,now1)!=coordinate(0,Route::Counts,now2),
{}
pub proof fn theorem_bulk_zero_fallback_differs(e:stores::Edge,now:int)
    requires now!=0,
    ensures call_bulk(Map::empty(),e,Raw::Number(0),Raw::Missing,true,true,now,true,1,true).time==Some(now),
        call_bulk(Map::empty(),e,Raw::Number(0),Raw::Missing,true,false,now,true,1,true).time==Some(0),
{}
pub proof fn theorem_refusal_no_effect(s:stores::Global,e:stores::Edge,r:Raw,short:Raw,long:Raw,now:int)
    ensures call_single(s,e,r,now,false,1,true).state==s,
        call_bulk(s,e,short,long,true,true,now,false,1,true).state==s,
        !call_single(s,e,r,now,false,1,true).accepted,
{}
pub proof fn theorem_invalid_input_refuses_before_write(s:stores::Global,e:stores::Edge,now:int)
    ensures call_single(s,e,Raw::Bad,now,true,1,true).state==s,
        call_bulk(s,e,Raw::Missing,Raw::Missing,true,false,now,true,1,true).state==s,
        !call_bulk(s,e,Raw::Missing,Raw::Missing,true,false,now,true,1,true).accepted,
{}
pub proof fn theorem_actual_coordinate_reaches_window(s:stores::Global,e:stores::Edge,n:int,route:Route,now:int,w:int,reverse:bool,lo:int,hi:int)
    requires !s.contains_key(stores::out(at(e,coordinate(n,route,now)))),lo<=coordinate(n,route,now)<=hi,
    ensures observe(write(s,e,n,route,now,true,w,reverse),e,coordinate(n,route,now),e.0,lo,hi,false,stores::paging::plain(None))==Some(w),
        reverse ==> observe(write(s,e,n,route,now,true,w,reverse),e,coordinate(n,route,now),e.0,lo,hi,true,stores::paging::plain(None))==Some(w),
{}
// Producer-to-reader contracts quantify the raw caller values. The expected
// timestamp is independently derived here, never supplied as a resolved edge.
pub proof fn theorem_raw_single_to_reader(s:stores::Global,e:stores::Edge,r:Raw,now:int,w:int)
    requires single_payload(r).is_some(),
        !s.contains_key(stores::out(at(e,single_payload(r).unwrap()))),
    ensures observe(call_single(s,e,r,now,true,w,true),e,single_payload(r).unwrap(),e.0,
        single_payload(r).unwrap(),single_payload(r).unwrap(),false,stores::paging::plain(None))==Some(w),
        observe(call_single(s,e,r,now,true,w,true),e,single_payload(r).unwrap(),e.0,
        single_payload(r).unwrap(),single_payload(r).unwrap(),true,stores::paging::plain(None))==Some(w),
{}
pub open spec fn produced_bulk_time(short:Raw,long:Raw,shape_ok:bool,available:bool,now:int)->Option<int> {
    match bulk_payload(short,long,shape_ok) {None=>None,Some(n)=>Some(if !available{n}else{if n==0{now}else{n}})}
}
pub proof fn theorem_raw_bulk_to_reader(s:stores::Global,e:stores::Edge,short:Raw,long:Raw,shape_ok:bool,available:bool,now:int,w:int)
    requires produced_bulk_time(short,long,shape_ok,available,now).is_some(),
        !s.contains_key(stores::out(at(e,produced_bulk_time(short,long,shape_ok,available,now).unwrap()))),
    ensures observe(call_bulk(s,e,short,long,shape_ok,available,now,true,w,true),e,
        produced_bulk_time(short,long,shape_ok,available,now).unwrap(),e.0,
        produced_bulk_time(short,long,shape_ok,available,now).unwrap(),
        produced_bulk_time(short,long,shape_ok,available,now).unwrap(),false,stores::paging::plain(None))==Some(w),
{}
pub proof fn theorem_full_batch_one_item_to_reader(s:stores::Global,r:Request,available:bool,now:int)
    requires produced_bulk_time(r.short,r.long,r.shape_ok,available,now).is_some(),
        !s.contains_key(stores::out(at(r.edge,produced_bulk_time(r.short,r.long,r.shape_ok,available,now).unwrap()))),
    ensures observe(call_batch(s,seq![r],available,seq![now],true),r.edge,
        produced_bulk_time(r.short,r.long,r.shape_ok,available,now).unwrap(),r.edge.0,
        produced_bulk_time(r.short,r.long,r.shape_ok,available,now).unwrap(),
        produced_bulk_time(r.short,r.long,r.shape_ok,available,now).unwrap(),false,stores::paging::plain(None))==Some(r.w),
{
    assert(batch_valid(seq![r])) by {assert forall|i:int|0<=i<(seq![r]).len() implies bulk_payload((seq![r])[i].short,(seq![r])[i].long,(seq![r])[i].shape_ok).is_some() by {assert(i==0);}}
    assert((seq![r]).drop_first() =~= Seq::<Request>::empty());
    reveal_with_fuel(fold,2);
    theorem_raw_bulk_to_reader(s,r.edge,r.short,r.long,r.shape_ok,available,now,r.w);
}
pub proof fn theorem_final_window_excludes_wrong_graph_and_time(s:stores::Global,e:stores::Edge,n:int,route:Route,now:int,w:int,g:int,lo:int,hi:int)
    requires g!=e.0 || coordinate(n,route,now)<lo || coordinate(n,route,now)>hi,
    ensures observe(write(s,e,n,route,now,true,w,true),e,coordinate(n,route,now),g,lo,hi,false,stores::paging::plain(None))==None,
{}
pub proof fn theorem_raw_omission_misses_recent_window(e:stores::Edge,now:int)
    requires now>0,
    ensures observe(call_single(Map::empty(),e,Raw::Missing,now,true,7,true),e,0,e.0,0,0,false,stores::paging::plain(None))==Some(7),
        observe(call_single(Map::empty(),e,Raw::Missing,now,true,7,true),e,0,e.0,now,now,false,stores::paging::plain(None))==None,
{}
pub proof fn theorem_bulk_clock_and_fallback_final_windows(e:stores::Edge,now:int)
    requires now>0,
    ensures observe(call_bulk(Map::empty(),e,Raw::Number(0),Raw::Missing,true,true,now,true,7,true),e,now,e.0,now,now,false,stores::paging::plain(None))==Some(7),
        observe(call_bulk(Map::empty(),e,Raw::Number(0),Raw::Missing,true,false,now,true,7,true),e,0,e.0,now,now,false,stores::paging::plain(None))==None,
        observe(call_bulk(Map::empty(),e,Raw::Number(0),Raw::Missing,true,false,now,true,7,true),e,0,e.0,0,0,false,stores::paging::plain(None))==Some(7),
{}
pub proof fn theorem_duplicate_counts_differ(s:stores::Global,e:stores::Edge,n:int,now:int)
    requires n!=0,s.contains_key(stores::out(at(e,n))),
    ensures write(s,e,n,Route::Counts,now,true,7,true).state==s,
        write(s,e,n,Route::Counts,now,true,7,true).count==0,
        write(s,e,n,Route::Counts,now,true,7,true).collisions==1,
        write(s,e,n,Route::PrewriteFallback,now,true,7,true).state==s,
        write(s,e,n,Route::PrewriteFallback,now,true,7,true).count==1,
        write(s,e,n,Route::PrewriteFallback,now,true,7,true).collisions==0,
{}
pub proof fn theorem_zero_clock_is_legitimate_overlap(e:stores::Edge)
    ensures call_bulk(Map::empty(),e,Raw::Number(0),Raw::Missing,true,true,0,true,7,true).state
        ==call_bulk(Map::empty(),e,Raw::Number(0),Raw::Missing,true,false,0,true,7,true).state,
{}
}
