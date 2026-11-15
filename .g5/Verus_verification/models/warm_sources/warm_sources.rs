// As-built WarmFill/WarmAll/AllWarm, Adj.cls:135-217 at 3eaa79cf; inspected, not run on IRIS.
// `sources` is the finite sequence visited by $Order(^KG("out",graph,...)); SQL has no role.
use vstd::prelude::*;
verus! {
pub struct Source { pub predicates: nat, pub probe: bool, pub no_lock: bool,
    pub gen_before: int, pub gen_store: int, pub gen_after: int }
pub open spec fn stores(s: Source) -> nat {
    if s.probe && !s.no_lock && s.gen_before==s.gen_store && s.gen_after==s.gen_before {
        1+s.predicates
    } else { 0 }
}
pub open spec fn filled(sources: Seq<Source>) -> nat
    decreases sources.len(),
{
    if sources.len()==0 { 0 } else {
        (if stores(sources[0])>0 { 1nat } else { 0nat }) + filled(sources.drop_first())
    }
}
pub open spec fn stamp(sources: Seq<Source>, before: int, after: int) -> Option<int> {
    if filled(sources)==sources.len() && before==after { Some(before) } else { None }
}
pub open spec fn all_warm(stamp: Option<int>, current: int) -> bool { stamp==Some(current) }
pub proof fn theorem_global_source_fills_without_sql(s: Source,v: int)
    requires s.probe,!s.no_lock,s.gen_before==s.gen_store,s.gen_after==s.gen_before,
    ensures filled(seq![s])==1, all_warm(stamp(seq![s],v,v),v),
{ reveal_with_fuel(filled,2); }
pub proof fn theorem_failed_probe_leaves_no_stamp(s: Source,v: int)
    requires !s.probe,
    ensures filled(seq![s])==0,stamp(seq![s],v,v)==None,
{ reveal_with_fuel(filled,2); }
pub proof fn theorem_generation_moves_discard_fill(s: Source)
    requires s.gen_before!=s.gen_store || s.gen_before!=s.gen_after || s.no_lock,
    ensures stores(s)==0,
{}
pub proof fn theorem_version_moves_invalidates(sources: Seq<Source>,a: int,b: int)
    requires a!=b,
    ensures stamp(sources,a,b)==None,!all_warm(Some(a),b),
{}
pub proof fn theorem_empty_globals_count_zero(v: int)
    ensures filled(seq![])==0,all_warm(stamp(seq![],v,v),v),
{}
pub proof fn theorem_count_sources_not_entries(s: Source)
    requires s.probe,!s.no_lock,s.gen_before==s.gen_store,s.gen_after==s.gen_before,s.predicates>0,
    ensures stores(s)>1,filled(seq![s])==1,
{ reveal_with_fuel(filled,2); }
}
