// As-built Python fusion helper. Real arithmetic models mathematical RRF scores;
// Python rounding, provider relevance and equal-score iteration order are unproved.
use vstd::prelude::*;
verus! {
pub type Row = (int,int); // entity ID, provider score (ignored by RRF)
pub open spec fn rank(xs:Seq<Row>,id:int,offset:nat) -> Option<nat>
    decreases xs.len(),
{
    if xs.len()==0 {None} else if xs[0].0==id {Some(offset+1)}
    else {rank(xs.drop_first(),id,offset+1)}
}
pub open spec fn part(xs:Seq<Row>,id:int,c:nat) -> real {
    match rank(xs,id,0) { Some(r) => 1real / (c as real+r as real), None => 0real }
}
pub open spec fn score(lists:Seq<Seq<Row>>,id:int,c:nat) -> real
    decreases lists.len(),
{
    if lists.len()==0 {0real} else {part(lists[0],id,c)+score(lists.drop_first(),id,c)}
}
pub open spec fn same_ids(a:Seq<Row>,b:Seq<Row>) -> bool {
    a.len()==b.len() && forall|i:int| 0<=i<a.len() ==> a[i].0==b[i].0
}
pub proof fn theorem_rank_ignores_magnitude(a:Seq<Row>,b:Seq<Row>,id:int,offset:nat)
    requires same_ids(a,b),
    ensures rank(a,id,offset)==rank(b,id,offset),
    decreases a.len(),
{
    if a.len()>0 && a[0].0!=id {
        assert(same_ids(a.drop_first(),b.drop_first())) by {
            assert forall|i:int| 0<=i<a.drop_first().len() implies a.drop_first()[i].0==b.drop_first()[i].0 by {
                assert(a[i+1].0==b[i+1].0);
            }
        }
        theorem_rank_ignores_magnitude(a.drop_first(),b.drop_first(),id,offset+1);
    }
}
pub proof fn theorem_first_occurrence_wins(a:int,b:int,c:nat)
    ensures rank(seq![(0,a),(0,b)],0,0)==Some(1),part(seq![(0,a),(0,b)],0,c)==1real/(c as real+1real),
{reveal_with_fuel(rank,4);}
pub proof fn theorem_absent_contributes_zero(c:nat)
    ensures part(seq![(1,900)],0,c)==0real,
{reveal_with_fuel(rank,3);}
// Observed consumer sorts and takes k; strict pair winner is the specified slice.
pub open spec fn top_two(lists:Seq<Seq<Row>>) -> Option<int> {
    let a=score(lists,0,60);let b=score(lists,1,60);
    if a>b {Some(0)} else if b>a {Some(1)} else {None}
}
pub proof fn theorem_second_leg_changes_winner()
    ensures top_two(seq![seq![(0,1),(1,1000)]])==Some(0),
        top_two(seq![seq![(0,1),(1,1000)],seq![(1,-1000)]])==Some(1),
{
    reveal_with_fuel(score,4);reveal_with_fuel(rank,4);
    assert(1real/61real > 1real/62real) by(nonlinear_arith);
    assert(1real/62real + 1real/61real > 1real/61real) by(nonlinear_arith);
    assert(score(seq![seq![(0,1),(1,1000)]],0,60)==1real/61real);
    assert(score(seq![seq![(0,1),(1,1000)]],1,60)==1real/62real);
}
pub enum Provider { NotRequested, Rows(Seq<Row>), Raises }
pub struct Legs {pub lists:Seq<Seq<Row>>,pub modes:Seq<int>,pub error:bool}
// Provider results are scoped external inputs. Catch policy is derived here.
pub open spec fn add(p:Provider,mode:int,legs:Legs) -> Legs {
    match p {
        Provider::NotRequested => legs,
        Provider::Rows(xs) => Legs {lists:legs.lists.push(xs),modes:legs.modes.push(mode),..legs},
        Provider::Raises => if mode==1 {Legs {error:true,..legs}} else {legs},
    }
}
pub open spec fn collect(v:Provider,t:Provider) -> Legs {
    add(t,1,add(v,0,Legs {lists:seq![],modes:seq![],error:false}))
}
pub proof fn theorem_vector_failure_dropped_text_failure_raises(xs:Seq<Row>)
    ensures collect(Provider::Raises,Provider::Rows(xs)).error==false,
        collect(Provider::Raises,Provider::Rows(xs)).modes==seq![1],
        collect(Provider::Rows(xs),Provider::Raises).error==true,
{}
pub proof fn theorem_empty_success_is_a_retained_leg()
    ensures collect(Provider::Rows(seq![]),Provider::NotRequested).modes==seq![0],
        collect(Provider::Raises,Provider::NotRequested).modes==seq![],
{}
pub proof fn theorem_graph_failure_dropped(l:Legs)
    ensures add(Provider::Raises,2,l)==l,
{}
}
