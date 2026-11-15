// Python batch orchestration at 3eaa79cf; one explicit graph, positive batch size.
// Providers either refuse before node removal or fail during later reifier cleanup.
// Trigger sets script those external failures; the actual catch/count policy and
// order of primary deletion then cleanup are represented, not assumed atomic.
use vstd::prelude::*;
verus! {
pub enum Input { Missing, Empty, Id(int) }
pub struct Answer {pub live:Map<int,()>,pub deleted:nat,pub failed:nat}
pub open spec fn normalize(xs:Seq<Input>,seen:Set<int>) -> Seq<int>
    decreases xs.len(),
{
    if xs.len()==0 {seq![]} else {match xs[0] {
        Input::Missing | Input::Empty => normalize(xs.drop_first(),seen),
        Input::Id(id) => if seen.contains(id) {normalize(xs.drop_first(),seen)}
            else {seq![id]+normalize(xs.drop_first(),seen.insert(id))},
    }}
}
pub open spec fn remove(live:Map<int,()>,ids:Seq<int>) -> Map<int,()>
    decreases ids.len(),
{
    if ids.len()==0 {live} else {remove(live.remove(ids[0]),ids.drop_first())}
}
pub open spec fn blocked(ids:Seq<int>,reject:Set<int>) -> bool
    decreases ids.len(),
{
    ids.len()>0 && (reject.contains(ids[0]) || blocked(ids.drop_first(),reject))
}
pub open spec fn batches(live:Map<int,()>,ids:Seq<int>,size:nat,reject:Set<int>,cleanup:Set<int>) -> Answer
    recommends size>0,
    decreases ids.len(),
{
    if ids.len()==0 || size==0 {Answer {live,deleted:0,failed:0}} else {
        let n=if size<ids.len() {size} else {ids.len()};
        let batch=ids.take(n as int);
        let refused=blocked(batch,reject);
        let after=if refused {live} else {remove(live,batch)};
        let caught=refused || blocked(batch,cleanup);
        let rest=batches(after,ids.skip(n as int),size,reject,cleanup);
        Answer {live:rest.live,deleted:(if caught {0} else {(live.len()-after.len()) as nat})+rest.deleted,
            failed:rest.failed+if caught {batch.len()} else {0}}
    }
}
pub open spec fn run(live:Map<int,()>,xs:Seq<Input>,size:nat,reject:Set<int>) -> Answer {
    batches(live,normalize(xs,Set::empty()),size,reject,Set::empty())
}
pub open spec fn as_int(r:Answer) -> nat {r.deleted}
pub open spec fn as_bool(r:Answer) -> bool {r.deleted>0}
pub proof fn theorem_raw_ids_filtered_and_deduplicated()
    ensures normalize(seq![Input::Missing,Input::Empty,Input::Id(1),Input::Id(1),Input::Id(2)],Set::empty())==seq![1,2],
{reveal_with_fuel(normalize,7);}
pub proof fn theorem_later_batch_runs_after_failure()
    ensures ({let r=run(map![1=>(),2=>()],seq![Input::Id(1),Input::Id(2)],1,set![1]);
        r.live==map![1=>()] && r.deleted==1 && r.failed==1 && as_int(r)==1 && as_bool(r)}),
{reveal_with_fuel(normalize,4);reveal_with_fuel(batches,4);reveal_with_fuel(remove,4);reveal_with_fuel(blocked,4);}
pub proof fn theorem_legitimate_neighbor_deletes_both()
    ensures ({let r=run(map![1=>(),2=>()],seq![Input::Id(1),Input::Id(2)],1,Set::empty());
        r.live==Map::<int,()>::empty() && r.deleted==2 && r.failed==0}),
{reveal_with_fuel(normalize,4);reveal_with_fuel(batches,4);reveal_with_fuel(remove,4);reveal_with_fuel(blocked,4);}
pub proof fn theorem_failed_counts_requested_not_existing()
    ensures ({let r=run(map![1=>()],seq![Input::Id(1),Input::Id(2)],2,set![1]);
        r.live==map![1=>()] && r.deleted==0 && r.failed==2 && !as_bool(r)}),
{reveal_with_fuel(normalize,4);reveal_with_fuel(batches,4);reveal_with_fuel(blocked,4);}
pub proof fn theorem_cleanup_failure_is_not_rollback()
    ensures ({let r=batches(map![1=>(),2=>()],seq![1,2],2,Set::empty(),set![1]);
        r.live==Map::<int,()>::empty() && r.deleted==0 && r.failed==2 && !as_bool(r)}),
{reveal_with_fuel(batches,4);reveal_with_fuel(remove,4);reveal_with_fuel(blocked,4);}
pub proof fn theorem_empty_does_not_call_provider(live:Map<int,()>,size:nat,reject:Set<int>)
    ensures run(live,seq![],size,reject).live==live,run(live,seq![],size,reject).deleted==0,
        run(live,seq![],size,reject).failed==0,
{}
}
