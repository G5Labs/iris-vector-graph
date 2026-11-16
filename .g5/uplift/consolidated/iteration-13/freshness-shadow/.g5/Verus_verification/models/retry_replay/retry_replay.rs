// Counts may complete a prefix before its exception reaches the Python catch.
// Prefix effects are derived by the actual clock/writer fold, never supplied state.
#[path="../temporal_clock/temporal_clock.rs"]
pub mod clock;
use vstd::prelude::*;
verus! {
pub enum Fault {None, ErrorAfter(nat)}
pub struct Attempt {pub outcome:clock::Outcome,pub error:bool,pub completed:nat}
pub struct Result {pub outcome:clock::Outcome,pub fell_back:bool,pub completed:nat}
pub open spec fn prefix_len(n:nat,len:nat)->nat {if n<len{n}else{len}}
pub open spec fn counts(s:clock::stores::Global,es:Seq<clock::Request>,clocks:Seq<int>,f:Fault)->Attempt {
    match f {
        Fault::None=>Attempt{outcome:clock::fold(s,es,true,clocks),error:false,completed:es.len()},
        Fault::ErrorAfter(n)=>{let k=prefix_len(n,es.len());
            Attempt{outcome:clock::fold(s,es.take(k as int),true,clocks),error:true,completed:k}}
    }
}
pub open spec fn run(s:clock::stores::Global,es:Seq<clock::Request>,clocks:Seq<int>,fault:Fault)->Result {
    if es.len()==0 {Result{outcome:clock::fold(s,es,false,clocks),fell_back:false,completed:0}}
    else if !clock::batch_valid(es) {Result{outcome:clock::refused(s),fell_back:false,completed:0}}
    else {let normal=counts(s,es,clocks,fault);
        if normal.error {let fallback=clock::fold(normal.outcome.state,es,false,clocks);
            Result{outcome:fallback,fell_back:true,completed:normal.completed}}
        else {Result{outcome:normal.outcome,fell_back:false,completed:normal.completed}}}
}
pub open spec fn request(e:clock::stores::Edge,n:int,w:int,reverse:bool)->clock::Request {
    clock::Request{edge:e,short:clock::Raw::Number(n),long:clock::Raw::Missing,shape_ok:true,w,reverse}
}
pub open spec fn single(s:clock::stores::Global,e:clock::stores::Edge,n:int,w:int,reverse:bool,now:int,f:Fault)->Result {
    run(s,seq![request(e,n,w,reverse)],seq![now],f)
}
pub open spec fn read(r:Result,e:clock::stores::Edge,t:int,reverse:bool)->Option<int> {
    clock::observe(r.outcome,e,t,e.0,t,t,reverse,clock::stores::paging::plain(None))
}
pub proof fn lemma_one(s:clock::stores::Global,e:clock::stores::Edge,n:int,w:int,reverse:bool,now:int)
    ensures clock::batch_valid(seq![request(e,n,w,reverse)]),
        clock::fold(s,seq![request(e,n,w,reverse)],true,seq![now]).state==clock::write(s,e,n,clock::Route::Counts,now,true,w,reverse).state,
        clock::fold(s,seq![request(e,n,w,reverse)],false,seq![now]).state==clock::write(s,e,n,clock::Route::PrewriteFallback,now,true,w,reverse).state,
        clock::fold(s,seq![request(e,n,w,reverse)],false,seq![now]).count==1,
        clock::fold(s,seq![request(e,n,w,reverse)],false,seq![now]).collisions==0,
{
    assert(clock::batch_valid(seq![request(e,n,w,reverse)])) by {assert forall|i:int|0<=i<(seq![request(e,n,w,reverse)]).len() implies clock::bulk_payload((seq![request(e,n,w,reverse)])[i].short,(seq![request(e,n,w,reverse)])[i].long,true).is_some() by {assert(i==0);}}
    assert((seq![request(e,n,w,reverse)]).drop_first() =~= Seq::<clock::Request>::empty());
    reveal_with_fuel(clock::fold,2);
}
pub proof fn theorem_validation_precedes_counts_and_fallback(s:clock::stores::Global,es:Seq<clock::Request>,clocks:Seq<int>,f:Fault,i:int)
    requires 0<=i<es.len(),clock::bulk_payload(es[i].short,es[i].long,es[i].shape_ok).is_none(),
    ensures run(s,es,clocks,f).outcome.state==s,!run(s,es,clocks,f).outcome.accepted,!run(s,es,clocks,f).fell_back,
{}
pub proof fn theorem_empty_has_no_counts_or_fallback(s:clock::stores::Global,clocks:Seq<int>,f:Fault)
    ensures run(s,seq![],clocks,f).outcome.state==s,run(s,seq![],clocks,f).outcome.count==0,
        run(s,seq![],clocks,f).outcome.accepted,!run(s,seq![],clocks,f).fell_back,
{}
pub proof fn theorem_success_is_normal_writer(s:clock::stores::Global,es:Seq<clock::Request>,clocks:Seq<int>)
    requires es.len()>0,clock::batch_valid(es),
    ensures run(s,es,clocks,Fault::None).outcome==clock::fold(s,es,true,clocks),
        !run(s,es,clocks,Fault::None).fell_back,
{}
pub proof fn theorem_cutoff_derives_completed_prefix(s:clock::stores::Global,es:Seq<clock::Request>,clocks:Seq<int>,n:nat)
    ensures counts(s,es,clocks,Fault::ErrorAfter(n)).outcome.state==clock::fold(s,es.take(prefix_len(n,es.len()) as int),true,clocks).state,
        counts(s,es,clocks,Fault::ErrorAfter(n)).completed==prefix_len(n,es.len()),
{}
pub proof fn theorem_fault_replays_entire_batch(s:clock::stores::Global,es:Seq<clock::Request>,clocks:Seq<int>,n:nat)
    requires es.len()>0,clock::batch_valid(es),
    ensures run(s,es,clocks,Fault::ErrorAfter(n)).outcome==clock::fold(
        clock::fold(s,es.take(prefix_len(n,es.len()) as int),true,clocks).state,es,false,clocks),
        run(s,es,clocks,Fault::ErrorAfter(n)).fell_back,
{}
pub proof fn theorem_zero_lost_reply_retains_two_events(e:clock::stores::Edge,now:int,w:int)
    requires now>0,
    ensures read(single(Map::empty(),e,0,w,true,now,Fault::ErrorAfter(1)),e,0,false)==Some(w),
        read(single(Map::empty(),e,0,w,true,now,Fault::ErrorAfter(1)),e,now,false)==Some(w),
        read(single(Map::empty(),e,0,w,true,now,Fault::ErrorAfter(1)),e,0,true)==Some(w),
        read(single(Map::empty(),e,0,w,true,now,Fault::ErrorAfter(1)),e,now,true)==Some(w),
        single(Map::empty(),e,0,w,true,now,Fault::ErrorAfter(1)).outcome.count==1,
        single(Map::empty(),e,0,w,true,now,Fault::ErrorAfter(1)).outcome.collisions==0,
{
    lemma_one(Map::empty(),e,0,w,true,now);
    let first=clock::write(Map::empty(),e,0,clock::Route::Counts,now,true,w,true).state;
    lemma_one(first,e,0,w,true,now);
    assert((seq![request(e,0,w,true)]).take(1) =~= seq![request(e,0,w,true)]);
}
pub proof fn theorem_prewrite_zero_has_only_epoch(e:clock::stores::Edge,now:int,w:int)
    requires now>0,
    ensures read(single(Map::empty(),e,0,w,true,now,Fault::ErrorAfter(0)),e,0,false)==Some(w),
        read(single(Map::empty(),e,0,w,true,now,Fault::ErrorAfter(0)),e,now,false)==None,
        single(Map::empty(),e,0,w,true,now,Fault::ErrorAfter(0)).completed==0,
{lemma_one(Map::empty(),e,0,w,true,now);reveal_with_fuel(clock::fold,2);}
pub proof fn theorem_positive_lost_reply_collides(e:clock::stores::Edge,n:int,now:int,w:int)
    requires n>0,
    ensures single(Map::empty(),e,n,w,true,now,Fault::ErrorAfter(1)).outcome.state==single(Map::empty(),e,n,w,true,now,Fault::None).outcome.state,
        read(single(Map::empty(),e,n,w,true,now,Fault::ErrorAfter(1)),e,n,false)==Some(w),
        single(Map::empty(),e,n,w,true,now,Fault::ErrorAfter(1)).outcome.count==1,
        single(Map::empty(),e,n,w,true,now,Fault::ErrorAfter(1)).outcome.collisions==0,
{lemma_one(Map::empty(),e,n,w,true,now);let first=clock::write(Map::empty(),e,n,clock::Route::Counts,now,true,w,true).state;lemma_one(first,e,n,w,true,now);assert((seq![request(e,n,w,true)]).take(1) =~= seq![request(e,n,w,true)]);}
pub proof fn theorem_preexisting_collision_still_reports_one(s:clock::stores::Global,e:clock::stores::Edge,n:int,now:int,w:int)
    requires n>0,s.contains_key(clock::stores::out(clock::at(e,n))),
    ensures single(s,e,n,w,true,now,Fault::ErrorAfter(1)).outcome.state==s,
        single(s,e,n,w,true,now,Fault::ErrorAfter(1)).outcome.count==1,
        single(s,e,n,w,true,now,Fault::ErrorAfter(1)).outcome.collisions==0,
{lemma_one(s,e,n,w,true,now);assert((seq![request(e,n,w,true)]).take(1) =~= seq![request(e,n,w,true)]);}
pub proof fn theorem_normal_zero_has_only_current(e:clock::stores::Edge,now:int,w:int)
    requires now>0,
    ensures read(single(Map::empty(),e,0,w,true,now,Fault::None),e,now,false)==Some(w),
        read(single(Map::empty(),e,0,w,true,now,Fault::None),e,0,false)==None,
        !single(Map::empty(),e,0,w,true,now,Fault::None).fell_back,
{lemma_one(Map::empty(),e,0,w,true,now);reveal_with_fuel(clock::fold,2);}
pub proof fn theorem_zero_clock_overlaps(e:clock::stores::Edge,w:int)
    ensures single(Map::empty(),e,0,w,true,0,Fault::ErrorAfter(1)).outcome.state==single(Map::empty(),e,0,w,true,0,Fault::None).outcome.state,
        read(single(Map::empty(),e,0,w,true,0,Fault::ErrorAfter(1)),e,0,false)==Some(w),
{lemma_one(Map::empty(),e,0,w,true,0);let first=clock::write(Map::empty(),e,0,clock::Route::Counts,0,true,w,true).state;lemma_one(first,e,0,w,true,0);assert((seq![request(e,0,w,true)]).take(1) =~= seq![request(e,0,w,true)]);}
pub proof fn theorem_suppressed_reverse_stays_absent(e:clock::stores::Edge,now:int,w:int)
    requires now>0,
    ensures read(single(Map::empty(),e,0,w,false,now,Fault::ErrorAfter(1)),e,0,true)==None,
        read(single(Map::empty(),e,0,w,false,now,Fault::ErrorAfter(1)),e,now,true)==None,
{lemma_one(Map::empty(),e,0,w,false,now);let first=clock::write(Map::empty(),e,0,clock::Route::Counts,now,true,w,false).state;lemma_one(first,e,0,w,false,now);assert((seq![request(e,0,w,false)]).take(1) =~= seq![request(e,0,w,false)]);}
pub proof fn theorem_mixed_prefix_replay_reaches_three_points(a:clock::stores::Edge,b:clock::stores::Edge,now:int,n:int,wa:int,wb:int,k:nat)
    requires a.2!=b.2,now>0,n>0,1<=k<=2,
    ensures ({let es=seq![request(a,0,wa,true),request(b,n,wb,true)];let r=run(Map::empty(),es,seq![now,now],Fault::ErrorAfter(k));
        read(r,a,0,false)==Some(wa) && read(r,a,now,false)==Some(wa) && read(r,b,n,false)==Some(wb)
        && r.outcome.count==2 && r.outcome.collisions==0}),
{
    let es=seq![request(a,0,wa,true),request(b,n,wb,true)];
    assert(clock::batch_valid(es)) by {
        assert forall|i:int|0<=i<es.len() implies clock::bulk_payload(es[i].short,es[i].long,es[i].shape_ok).is_some() by {assert(i==0 || i==1);}
    }
    assert(es.drop_first() =~= seq![request(b,n,wb,true)]);
    assert(es.drop_first().drop_first() =~= Seq::<clock::Request>::empty());
    if k==1 {assert(es.take(1) =~= seq![request(a,0,wa,true)]);} else {assert(k==2);assert(es.take(2) =~= es);}
    reveal_with_fuel(clock::fold,3);
}

}
