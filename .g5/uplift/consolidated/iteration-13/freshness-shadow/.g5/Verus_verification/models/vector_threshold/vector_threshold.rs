// Ordinary cosine threshold contract. Scores/thresholds are exact scaled integers;
// finite float conversion, cosine computation and SQL dialect are provider premises.
use vstd::prelude::*;
verus! {
pub struct Plan {pub predicate:Option<int>,pub vector_binds:nat,pub threshold_binds:nat}
pub open spec fn build(t:Option<int>) -> Plan {
    Plan{predicate:t,vector_binds:if t.is_some(){2}else{1},threshold_binds:if t.is_some(){1}else{0}}
}
pub open spec fn admits(p:Plan,score:int) -> bool {p.predicate.is_none() || score>=p.predicate.unwrap()}
pub open spec fn eligible(scores:Seq<int>,t:Option<int>) -> Seq<int>
    decreases scores.len(),
{if scores.len()==0{seq![]}else{
    let rest=eligible(scores.drop_first(),t);
    if admits(build(t),scores[0]){seq![scores[0]]+rest}else{rest}}}
pub open spec fn search(scores:Seq<int>,t:Option<int>,k:nat) -> Seq<int> {
    let es=eligible(scores,t);es.take(if k<es.len(){k as int}else{es.len() as int})
}
pub proof fn theorem_no_threshold_keeps_all(scores:Seq<int>)
    ensures eligible(scores,None)==scores,
    decreases scores.len(),
{if scores.len()>0{theorem_no_threshold_keeps_all(scores.drop_first());assert(seq![scores[0]]+scores.drop_first() =~= scores);}}
pub proof fn theorem_threshold_decides(score:int,t:int)
    ensures admits(build(Some(t)),score)==(score>=t),
        build(Some(t)).vector_binds==2,build(Some(t)).threshold_binds==1,
{}
pub proof fn theorem_boundary_included(t:int)
    ensures search(seq![t,t-1],Some(t),2)==seq![t],search(seq![t,t-1],None,2)==seq![t,t-1],
{reveal_with_fuel(eligible,4);}
pub proof fn theorem_filter_precedes_limit()
    ensures search(seq![100,50,25],Some(50),3)==seq![100,50],
        search(seq![100,50,25],None,3)==seq![100,50,25],
        search(seq![100,50,25],Some(50),1)==seq![100],
{reveal_with_fuel(eligible,5);}
pub proof fn theorem_omitted_threshold_has_one_vector()
    ensures build(None).vector_binds==1,build(None).threshold_binds==0,
{}
}
