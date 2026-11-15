use vstd::prelude::*;
use vstd::seq_lib::*;
use vstd::set_lib::*;
verus! {
pub type Node=nat; // ordered atoms; full IRIS collation/codec remains a provider
pub type Labels=Map<Node,Node>;
pub struct Coord {pub incoming:bool,pub graph:nat,pub owner:Node,pub predicate:nat,pub neighbor:Node}
pub open spec fn selected(a:Coord)->bool {a.graph==0}
pub open spec fn members(g:Seq<Coord>)->Set<Node> {g.filter(|a:Coord|selected(a)).map_values(|a:Coord|a.owner).to_set()}
pub open spec fn neighbor(g:Seq<Coord>,u:Node,v:Node)->bool {exists|i:int|0<=i<g.len() && selected(g[i]) && g[i].owner==u && g[i].neighbor==v}
pub open spec fn closed(g:Seq<Coord>)->bool {forall|u:Node,v:Node|#[trigger] neighbor(g,u,v) ==> members(g).contains(u) && members(g).contains(v)}
pub open spec fn mirrored(g:Seq<Coord>)->bool {forall|i:int|0<=i<g.len() && selected(g[i]) ==> exists|j:int|0<=j<g.len() && g[j]==Coord{incoming:!g[i].incoming,owner:g[i].neighbor,neighbor:g[i].owner,..g[i]}}
pub open spec fn get(l:Labels,u:Node)->Node {if l.contains_key(u){l[u]}else{u}}
pub open spec fn initial(g:Seq<Coord>)->Labels {Map::new(members(g),|u:Node|u)}
pub open spec fn min_fold(g:Seq<Coord>,u:Node,l:Labels,best:Node)->Node decreases g.len(),
{if g.len()==0{best}else{let a=g[0];let x=get(l,a.neighbor);min_fold(g.drop_first(),u,l,if selected(a) && a.owner==u && x<best{x}else{best})}}
pub open spec fn wround(g:Seq<Coord>,l:Labels)->Labels {Map::new(members(g),|u:Node|min_fold(g,u,l,get(l,u)))}
pub open spec fn changed(g:Seq<Coord>,a:Labels,b:Labels)->nat {members(g).filter(|u:Node|get(a,u)!=get(b,u)).len()}
pub open spec fn labels_at(g:Seq<Coord>,k:nat)->Labels decreases k,
{if k==0{initial(g)}else{wround(g,labels_at(g,(k-1) as nat))}}
pub open spec fn expand(g:Seq<Coord>,s:Set<Node>)->Set<Node> {members(g).filter(|v:Node|s.contains(v) || exists|u:Node|s.contains(u) && neighbor(g,u,v))}
pub open spec fn ball(g:Seq<Coord>,u:Node,k:nat)->Set<Node> decreases k,
{if k==0{Set::empty().insert(u)}else{expand(g,ball(g,u,(k-1) as nat))}}
pub open spec fn reachable(g:Seq<Coord>,u:Node,v:Node)->bool {exists|k:nat|#[trigger] ball(g,u,k).contains(v)}
pub open spec fn minimum_in(s:Set<Node>,x:Node)->bool {s.contains(x) && forall|v:Node|#[trigger] s.contains(v) ==> x<=v}
pub open spec fn component_min(g:Seq<Coord>,u:Node,x:Node)->bool {reachable(g,u,x) && forall|v:Node|#[trigger] reachable(g,u,v) ==> x<=v}
pub open spec fn round_inv(g:Seq<Coord>,k:nat,l:Labels)->bool {l.dom()==members(g) && forall|u:Node|members(g).contains(u) ==> minimum_in(ball(g,u,k),#[trigger] l[u])}
pub proof fn lemma_member_from_coordinate(g:Seq<Coord>,i:int)
    requires 0<=i<g.len(),selected(g[i]),
    ensures members(g).contains(g[i].owner),
{
    g.filter_lemma(|a:Coord|selected(a));let xs=g.filter(|a:Coord|selected(a));assert(xs.contains(g[i]));
    let j=choose|j:int|0<=j<xs.len() && xs[j]==g[i];assert(xs.map_values(|a:Coord|a.owner)[j]==g[i].owner);
}
pub proof fn theorem_mirror_closes_raw_neighbor_domain(g:Seq<Coord>)
    requires mirrored(g),
    ensures closed(g),forall|u:Node,v:Node|#[trigger] neighbor(g,u,v) ==> neighbor(g,v,u),
{
    assert forall|u:Node,v:Node|#[trigger] neighbor(g,u,v) implies members(g).contains(u) && members(g).contains(v) && neighbor(g,v,u) by {
        let i=choose|i:int|0<=i<g.len() && selected(g[i]) && g[i].owner==u && g[i].neighbor==v;
        let j=choose|j:int|0<=j<g.len() && g[j]==(Coord{incoming:!g[i].incoming,owner:g[i].neighbor,neighbor:g[i].owner,..g[i]});
        lemma_member_from_coordinate(g,i);lemma_member_from_coordinate(g,j);assert(exists|t:int|0<=t<g.len() && selected(g[t]) && g[t].owner==v && g[t].neighbor==u);
    }
}
pub proof fn lemma_ball_basic(g:Seq<Coord>,u:Node,k:nat)
    requires members(g).contains(u),
    ensures ball(g,u,k).contains(u),ball(g,u,k).subset_of(members(g)),ball(g,u,k).subset_of(ball(g,u,k+1)),
    decreases k,
{
    if k>0{lemma_ball_basic(g,u,(k-1) as nat);}
    assert forall|v:Node|#[trigger] ball(g,u,k).contains(v) implies members(g).contains(v) && ball(g,u,k+1).contains(v) by {};
}
pub proof fn lemma_ball_monotone(g:Seq<Coord>,u:Node,k:nat,t:nat)
    requires members(g).contains(u),k<=t,
    ensures ball(g,u,k).subset_of(ball(g,u,t)),
    decreases t-k,
{if k<t{lemma_ball_monotone(g,u,k,(t-1) as nat);lemma_ball_basic(g,u,(t-1) as nat);}}
pub proof fn lemma_ball_head(g:Seq<Coord>,u:Node,k:nat)
    requires closed(g),members(g).contains(u),
    ensures forall|v:Node|#[trigger] ball(g,u,k+1).contains(v) <==> v==u || exists|n:Node|neighbor(g,u,n) && ball(g,n,k).contains(v),
    decreases k,
{
    lemma_ball_basic(g,u,k);if k>0{lemma_ball_head(g,u,(k-1) as nat);}
    assert forall|v:Node|#[trigger] ball(g,u,k+1).contains(v) implies v==u || exists|n:Node|neighbor(g,u,n) && ball(g,n,k).contains(v) by {
        if k==0{if v!=u{assert(neighbor(g,u,v));lemma_ball_basic(g,v,0);}}
        else if ball(g,u,k).contains(v){
            if v!=u{let n=choose|n:Node|neighbor(g,u,n) && ball(g,n,(k-1) as nat).contains(v);lemma_ball_basic(g,n,(k-1) as nat);}
        }else{
            let w=choose|w:Node|ball(g,u,k).contains(w) && neighbor(g,w,v);
            if w==u{lemma_ball_basic(g,v,k);}else{
                let n=choose|n:Node|neighbor(g,u,n) && ball(g,n,(k-1) as nat).contains(w);lemma_ball_basic(g,n,(k-1) as nat);assert(ball(g,n,k).contains(v));
            }
        }
    }
    assert forall|v:Node|v==u || (exists|n:Node|neighbor(g,u,n) && ball(g,n,k).contains(v)) implies #[trigger] ball(g,u,k+1).contains(v) by {
        if v==u{}else{
            let n=choose|n:Node|neighbor(g,u,n) && ball(g,n,k).contains(v);lemma_ball_basic(g,n,k);
            if k==0{assert(v==n);assert(ball(g,u,k+1).contains(v));}
            else if ball(g,n,(k-1) as nat).contains(v){assert(ball(g,u,k).contains(v));}
            else{
                let w=choose|w:Node|ball(g,n,(k-1) as nat).contains(w) && neighbor(g,w,v);assert(ball(g,u,k).contains(w));assert(ball(g,u,k+1).contains(v));
            }
        }
    }
}
pub proof fn lemma_ball_strict_growth(g:Seq<Coord>,u:Node,k:nat)
    requires members(g).contains(u),ball(g,u,k)!=ball(g,u,k+1),
    ensures ball(g,u,k).len()>=k+1,
    decreases k,
{
    lemma_ball_basic(g,u,k);
    if k==0{assert(ball(g,u,0)==Set::empty().insert(u));}
    else{
        if ball(g,u,(k-1) as nat)==ball(g,u,k){assert(ball(g,u,k)==ball(g,u,k+1));}
        lemma_ball_strict_growth(g,u,(k-1) as nat);lemma_ball_basic(g,u,(k-1) as nat);
        let x=choose|x:Node|ball(g,u,k).contains(x) && !ball(g,u,(k-1) as nat).contains(x);
        ball(g,u,(k-1) as nat).lemma_subset_not_in_lt(ball(g,u,k),x);
    }
}
pub proof fn theorem_ball_stable_by_n_minus_one(g:Seq<Coord>,u:Node)
    requires members(g).contains(u),
    ensures members(g).len()>0,ball(g,u,(members(g).len()-1) as nat)==ball(g,u,members(g).len()),
{
    let n=members(g).len();assert(n>0);let k=(n-1) as nat;lemma_ball_basic(g,u,k);lemma_ball_basic(g,u,n);
    if ball(g,u,k)!=ball(g,u,n){lemma_ball_strict_growth(g,u,k);let x=choose|x:Node|ball(g,u,n).contains(x) && !ball(g,u,k).contains(x);ball(g,u,k).lemma_subset_not_in_lt(ball(g,u,n),x);lemma_len_subset(ball(g,u,n),members(g));}
}
pub proof fn lemma_ball_stable_future(g:Seq<Coord>,u:Node,k:nat,t:nat)
    requires ball(g,u,k)==ball(g,u,k+1),
    ensures ball(g,u,k+t)==ball(g,u,k),
    decreases t,
{if t>0{lemma_ball_stable_future(g,u,k,(t-1) as nat);}}
pub proof fn theorem_raw_reachability_bounded(g:Seq<Coord>,u:Node,v:Node)
    requires members(g).contains(u),
    ensures reachable(g,u,v) <==> ball(g,u,(members(g).len()-1) as nat).contains(v),
{
    theorem_ball_stable_by_n_minus_one(g,u);let n=(members(g).len()-1) as nat;
    if reachable(g,u,v){let k=choose|k:nat|ball(g,u,k).contains(v);if k>=n{lemma_ball_stable_future(g,u,n,(k-n) as nat);}else{lemma_ball_monotone(g,u,k,n);}}
    else if ball(g,u,n).contains(v){assert(exists|k:nat|ball(g,u,k).contains(v));}
}
pub open spec fn candidates(g:Seq<Coord>,u:Node,l:Labels,best:Node)->Set<Node> {g.filter(|a:Coord|selected(a) && a.owner==u).map_values(|a:Coord|get(l,a.neighbor)).to_set().insert(best)}
pub proof fn lemma_min_fold(g:Seq<Coord>,u:Node,l:Labels,best:Node)
    ensures minimum_in(candidates(g,u,l,best),min_fold(g,u,l,best)),
    decreases g.len(),
{
    if g.len()>0{
        let a=g[0];let x=get(l,a.neighbor);let b=if selected(a) && a.owner==u && x<best{x}else{best};lemma_min_fold(g.drop_first(),u,l,b);
        assert forall|v:Node|candidates(g,u,l,best).contains(v) implies min_fold(g,u,l,best)<=v by {
            if v!=best{let i=choose|i:int|0<=i<g.len() && selected(g[i]) && g[i].owner==u && v==get(l,g[i].neighbor);if i>0{assert(candidates(g.drop_first(),u,l,b).contains(v));}}
        }
        if min_fold(g,u,l,best)!=best{if min_fold(g,u,l,best)==b{assert(candidates(g,u,l,best).contains(b));}else{let i=choose|i:int|0<=i<g.drop_first().len() && selected(g.drop_first()[i]) && g.drop_first()[i].owner==u && min_fold(g,u,l,best)==get(l,g.drop_first()[i].neighbor);assert(candidates(g,u,l,best).contains(min_fold(g,u,l,best)));}}
    }
}
pub proof fn theorem_synchronous_round_extends_raw_radius(g:Seq<Coord>,k:nat,l:Labels)
    requires closed(g),round_inv(g,k,l),
    ensures round_inv(g,k+1,wround(g,l)),forall|u:Node|members(g).contains(u) ==> #[trigger] wround(g,l)[u]<=l[u],
{
    assert forall|u:Node|#[trigger] members(g).contains(u) implies minimum_in(ball(g,u,k+1),wround(g,l)[u]) && wround(g,l)[u]<=l[u] by {
        lemma_min_fold(g,u,l,l[u]);lemma_ball_head(g,u,k);lemma_ball_basic(g,u,k);let x=wround(g,l)[u];
        if x==l[u]{}else{let i=choose|i:int|0<=i<g.len() && selected(g[i]) && g[i].owner==u && x==get(l,g[i].neighbor);let n=g[i].neighbor;assert(neighbor(g,u,n));assert(ball(g,n,k).contains(x));}
        assert forall|v:Node|#[trigger] ball(g,u,k+1).contains(v) implies x<=v by {
            if v==u{assert(l[u]<=u);}else{let n=choose|n:Node|neighbor(g,u,n) && ball(g,n,k).contains(v);assert(candidates(g,u,l,l[u]).contains(l[n]));}
        }
    }
}
pub proof fn theorem_every_actual_round_is_raw_reachable_minimum(g:Seq<Coord>,k:nat)
    requires closed(g),
    ensures round_inv(g,k,labels_at(g,k)),
    decreases k,
{if k>0{theorem_every_actual_round_is_raw_reachable_minimum(g,(k-1) as nat);theorem_synchronous_round_extends_raw_radius(g,(k-1) as nat,labels_at(g,(k-1) as nat));}}
}
