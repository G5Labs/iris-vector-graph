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
pub proof fn lemma_ball_head(g:Seq<Coord>,u:Node,k:nat,v:Node)
    requires closed(g),members(g).contains(u),
    ensures ball(g,u,k+1).contains(v) <==> v==u || exists|n:Node|neighbor(g,u,n) && ball(g,n,k).contains(v),
    decreases k,
{
    lemma_ball_basic(g,u,k);if k>0{lemma_ball_head(g,u,(k-1) as nat,v);}
    if ball(g,u,k+1).contains(v) {
        if k==0{if v!=u{assert(neighbor(g,u,v));lemma_ball_basic(g,v,0);}}
        else if ball(g,u,k).contains(v){
            if v!=u{let n=choose|n:Node|neighbor(g,u,n) && ball(g,n,(k-1) as nat).contains(v);lemma_ball_basic(g,n,(k-1) as nat);}
        }else{
            let w=choose|w:Node|ball(g,u,k).contains(w) && neighbor(g,w,v);
            if w==u{lemma_ball_basic(g,v,k);}else{
                lemma_ball_head(g,u,(k-1) as nat,w);
                let n=choose|n:Node|neighbor(g,u,n) && ball(g,n,(k-1) as nat).contains(w);lemma_ball_basic(g,n,(k-1) as nat);assert(ball(g,n,k).contains(v));
            }
        }
    }
    if v==u{}else if exists|n:Node|neighbor(g,u,n) && ball(g,n,k).contains(v){
        let n=choose|n:Node|neighbor(g,u,n) && ball(g,n,k).contains(v);lemma_ball_basic(g,n,k);
        if k==0{assert(v==n);assert(ball(g,u,k+1).contains(v));}
        else if ball(g,n,(k-1) as nat).contains(v){assert(ball(g,u,k).contains(v));}
        else{
            let w=choose|w:Node|ball(g,n,(k-1) as nat).contains(w) && neighbor(g,w,v);lemma_ball_head(g,u,(k-1) as nat,w);assert(ball(g,u,k).contains(w));assert(ball(g,u,k+1).contains(v));
        }
    }
}
pub proof fn lemma_proper_subset_witness(a:Set<Node>,b:Set<Node>)
    requires a.subset_of(b),a!=b,
    ensures exists|x:Node|b.contains(x) && !a.contains(x),
{if !(exists|x:Node|b.contains(x) && !a.contains(x)){assert(a =~= b);}}
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
        lemma_proper_subset_witness(ball(g,u,(k-1) as nat),ball(g,u,k));let x=choose|x:Node|ball(g,u,k).contains(x) && !ball(g,u,(k-1) as nat).contains(x);
        ball(g,u,(k-1) as nat).lemma_subset_not_in_lt(ball(g,u,k),x);
    }
}
pub proof fn theorem_ball_stable_by_n_minus_one(g:Seq<Coord>,u:Node)
    requires members(g).contains(u),
    ensures members(g).len()>0,ball(g,u,(members(g).len()-1) as nat)==ball(g,u,members(g).len()),
{
    let n=members(g).len();assert(n>0);let k=(n-1) as nat;lemma_ball_basic(g,u,k);lemma_ball_basic(g,u,n);
    if ball(g,u,k)!=ball(g,u,n){lemma_ball_strict_growth(g,u,k);lemma_proper_subset_witness(ball(g,u,k),ball(g,u,n));let x=choose|x:Node|ball(g,u,n).contains(x) && !ball(g,u,k).contains(x);ball(g,u,k).lemma_subset_not_in_lt(ball(g,u,n),x);lemma_len_subset(ball(g,u,n),members(g));}
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
pub proof fn lemma_min_fold(g:Seq<Coord>,u:Node,l:Labels,best:Node)
    ensures min_fold(g,u,l,best)<=best,
        forall|i:int|0<=i<g.len() && selected(g[i]) && g[i].owner==u ==> min_fold(g,u,l,best)<=get(l,g[i].neighbor),
        min_fold(g,u,l,best)==best || exists|i:int|0<=i<g.len() && selected(g[i]) && g[i].owner==u && min_fold(g,u,l,best)==get(l,g[i].neighbor),
    decreases g.len(),
{
    if g.len()>0{
        let a=g[0];let x=get(l,a.neighbor);let b=if selected(a) && a.owner==u && x<best{x}else{best};lemma_min_fold(g.drop_first(),u,l,b);
        assert forall|i:int|0<=i<g.len() && selected(g[i]) && g[i].owner==u implies min_fold(g,u,l,best)<=get(l,g[i].neighbor) by {if i>0{assert(g.drop_first()[i-1]==g[i]);}}
        if min_fold(g,u,l,best)!=best{
            if min_fold(g,u,l,best)==b{assert(selected(g[0]) && g[0].owner==u && min_fold(g,u,l,best)==get(l,g[0].neighbor));}
            else{let i=choose|i:int|0<=i<g.drop_first().len() && selected(g.drop_first()[i]) && g.drop_first()[i].owner==u && min_fold(g,u,l,best)==get(l,g.drop_first()[i].neighbor);assert(g[i+1]==g.drop_first()[i]);}
        }
    }
}
pub proof fn theorem_synchronous_round_extends_raw_radius(g:Seq<Coord>,k:nat,l:Labels)
    requires closed(g),round_inv(g,k,l),
    ensures round_inv(g,k+1,wround(g,l)),forall|u:Node|members(g).contains(u) ==> #[trigger] wround(g,l)[u]<=l[u],
{
    assert forall|u:Node|#[trigger] members(g).contains(u) implies minimum_in(ball(g,u,k+1),wround(g,l)[u]) && wround(g,l)[u]<=l[u] by {
        lemma_min_fold(g,u,l,l[u]);lemma_ball_basic(g,u,k);let x=wround(g,l)[u];
        if x==l[u]{}else{
            let i=choose|i:int|0<=i<g.len() && selected(g[i]) && g[i].owner==u && x==get(l,g[i].neighbor);let n=g[i].neighbor;
            assert(neighbor(g,u,n));assert(minimum_in(ball(g,n,k),l[n]));lemma_ball_head(g,u,k,x);
            assert(exists|n:Node|neighbor(g,u,n) && ball(g,n,k).contains(x));
        }
        assert forall|v:Node|#[trigger] ball(g,u,k+1).contains(v) implies x<=v by {
            lemma_ball_head(g,u,k,v);
            if v==u{assert(l[u]<=u);}else{
                let n=choose|n:Node|neighbor(g,u,n) && ball(g,n,k).contains(v);let i=choose|i:int|0<=i<g.len() && selected(g[i]) && g[i].owner==u && g[i].neighbor==n;
                assert(minimum_in(ball(g,n,k),l[n]));assert(x<=l[n]);assert(l[n]<=v);
            }
        }
    }
}
pub proof fn theorem_every_actual_round_is_raw_reachable_minimum(g:Seq<Coord>,k:nat)
    requires closed(g),
    ensures round_inv(g,k,labels_at(g,k)),
    decreases k,
{if k>0{theorem_every_actual_round_is_raw_reachable_minimum(g,(k-1) as nat);theorem_synchronous_round_extends_raw_radius(g,(k-1) as nat,labels_at(g,(k-1) as nat));}}
pub enum WEvent {Continue(Labels),Success{labels:Labels,rounds:nat},Refused}
pub open spec fn wstep(g:Seq<Coord>,limit:Option<int>,k:nat)->WEvent {
    if members(g).len()==0{WEvent::Success{labels:initial(g),rounds:0}}
    else if limit.is_some() && k as int>=limit.unwrap(){WEvent::Refused}
    else{let old=labels_at(g,k);let next=wround(g,old);if changed(g,old,next)==0{WEvent::Success{labels:next,rounds:k+1}}else{WEvent::Continue(next)}}
}
pub open spec fn stops(g:Seq<Coord>,limit:Option<int>,k:nat)->bool {!(wstep(g,limit,k) is Continue)}
pub open spec fn prefix(g:Seq<Coord>,limit:Option<int>,t:nat)->bool {forall|k:nat|k<t ==> !#[trigger] stops(g,limit,k)}
pub open spec fn first_stop(g:Seq<Coord>,limit:Option<int>)->nat {choose|t:nat|stops(g,limit,t) && prefix(g,limit,t)}
pub open spec fn wcc(g:Seq<Coord>,limit:Option<int>)->WEvent {wstep(g,limit,first_stop(g,limit))}
pub proof fn lemma_minimum_unique(s:Set<Node>,x:Node,y:Node)
    requires minimum_in(s,x),minimum_in(s,y),ensures x==y,
{}
pub proof fn lemma_changed_exactly_map_inequality(g:Seq<Coord>,a:Labels,b:Labels)
    requires a.dom()==members(g),b.dom()==members(g),
    ensures changed(g,a,b)==0 <==> a==b,
{
    let delta=members(g).filter(|u:Node|get(a,u)!=get(b,u));
    if changed(g,a,b)==0{delta.lemma_len0_is_empty();assert forall|u:Node|#[trigger] members(g).contains(u) implies a[u]==b[u] by {if a[u]!=b[u]{assert(delta.contains(u));}};assert(a =~= b);}
    else if a==b{assert(delta =~= Set::empty());}
}
pub proof fn theorem_confirmation_round_by_n(g:Seq<Coord>)
    requires closed(g),members(g).len()>0,
    ensures wround(g,labels_at(g,(members(g).len()-1) as nat))==labels_at(g,(members(g).len()-1) as nat),
{
    let n=members(g).len();let k=(n-1) as nat;theorem_every_actual_round_is_raw_reachable_minimum(g,k);theorem_every_actual_round_is_raw_reachable_minimum(g,n);
    assert forall|u:Node|#[trigger] members(g).contains(u) implies labels_at(g,n)[u]==labels_at(g,k)[u] by {
        theorem_ball_stable_by_n_minus_one(g,u);lemma_minimum_unique(ball(g,u,k),labels_at(g,k)[u],labels_at(g,n)[u]);
    }
    assert(labels_at(g,k) =~= labels_at(g,n));
}
pub proof fn lemma_earliest_stop_exists_before(g:Seq<Coord>,limit:Option<int>,end:nat)
    requires stops(g,limit,end),
    ensures exists|t:nat|t<=end && stops(g,limit,t) && prefix(g,limit,t),
    decreases end,
{
    if prefix(g,limit,end){assert(exists|t:nat|t<=end && stops(g,limit,t) && prefix(g,limit,t));}
    else{let k=choose|k:nat|k<end && stops(g,limit,k);lemma_earliest_stop_exists_before(g,limit,k);}
}
pub proof fn lemma_fixed_round_remains_fixed(g:Seq<Coord>,k:nat,t:nat)
    requires wround(g,labels_at(g,k))==labels_at(g,k),
    ensures labels_at(g,k+t)==labels_at(g,k),
    decreases t,
{if t>0{lemma_fixed_round_remains_fixed(g,k,(t-1) as nat);}}
pub proof fn theorem_actual_wcc_terminates_with_confirmation(g:Seq<Coord>,limit:Option<int>)
    requires closed(g),
    ensures stops(g,limit,first_stop(g,limit)),prefix(g,limit,first_stop(g,limit)),
        first_stop(g,limit)<=if members(g).len()==0{0nat}else{(members(g).len()-1) as nat},
        !(wcc(g,limit) is Continue),
        match wcc(g,limit){WEvent::Success{labels,rounds}=>labels.dom()==members(g) && rounds<=members(g).len() && (forall|u:Node|members(g).contains(u) ==> component_min(g,u,#[trigger] labels[u])),WEvent::Refused=>limit.is_some(),_=>false},
        (limit.is_none() || limit.unwrap()>=members(g).len() as int) ==> wcc(g,limit) is Success,
{
    let n=members(g).len();let end=if n==0{0nat}else{(n-1) as nat};
    if n>0{theorem_confirmation_round_by_n(g);theorem_every_actual_round_is_raw_reachable_minimum(g,end);theorem_every_actual_round_is_raw_reachable_minimum(g,end+1);lemma_changed_exactly_map_inequality(g,labels_at(g,end),wround(g,labels_at(g,end)));}
    assert(stops(g,limit,end));lemma_earliest_stop_exists_before(g,limit,end);
    let witness=choose|t:nat|t<=end && stops(g,limit,t) && prefix(g,limit,t);
    let t=first_stop(g,limit);
    if t>witness{assert(!stops(g,limit,witness));}
    if n>0 && wcc(g,limit) is Success{
        theorem_every_actual_round_is_raw_reachable_minimum(g,t);theorem_every_actual_round_is_raw_reachable_minimum(g,t+1);lemma_changed_exactly_map_inequality(g,labels_at(g,t),wround(g,labels_at(g,t)));
        lemma_fixed_round_remains_fixed(g,t,(end-t) as nat);theorem_every_actual_round_is_raw_reachable_minimum(g,end);
        assert forall|u:Node|#[trigger] members(g).contains(u) implies component_min(g,u,labels_at(g,end)[u]) by {
            theorem_raw_reachability_bounded(g,u,labels_at(g,end)[u]);
            assert forall|v:Node|#[trigger] reachable(g,u,v) implies labels_at(g,end)[u]<=v by {theorem_raw_reachability_bounded(g,u,v);}
        }
    }
}
pub open spec fn pair()->Seq<Coord> {seq![Coord{incoming:false,graph:0,owner:0,predicate:0,neighbor:1},Coord{incoming:true,graph:0,owner:1,predicate:0,neighbor:0}]}
pub proof fn theorem_already_correct_pair_still_needs_confirmation()
    ensures get(labels_at(pair(),1),0)==0,get(labels_at(pair(),1),1)==0,
        wstep(pair(),Some(1),0) is Continue,wstep(pair(),Some(1),1) is Refused,wstep(pair(),Some(2),1) is Success,
        wstep(seq![],Some(0),0)==(WEvent::Success{labels:Map::empty(),rounds:0}),wstep(pair(),Some(0),0) is Refused,
{
    let g=pair();reveal_with_fuel(Seq::filter,3);reveal_with_fuel(min_fold,3);reveal_with_fuel(labels_at,3);
    assert(g.filter(|a:Coord|selected(a)) =~= g);assert(g.map_values(|a:Coord|a.owner) =~= seq![0nat,1nat]);assert(members(g) =~= set![0nat,1nat]);
    assert(get(labels_at(g,1),0)==0);assert(get(labels_at(g,1),1)==0);
    assert(wround(g,labels_at(g,1)) =~= labels_at(g,1));lemma_changed_exactly_map_inequality(g,labels_at(g,1),wround(g,labels_at(g,1)));
    assert(changed(g,initial(g),wround(g,initial(g)))>0) by {lemma_changed_exactly_map_inequality(g,initial(g),wround(g,initial(g)));}
    assert(initial(seq![]) =~= Map::empty());
}

pub type Counts=Map<Node,nat>;
pub open spec fn count(c:Counts,x:Node)->nat {if c.contains_key(x){c[x]}else{0}}
pub open spec fn vote(a:Coord,u:Node)->bool {selected(a) && a.owner==u && a.neighbor!=u}
pub open spec fn frequency(g:Seq<Coord>,u:Node,l:Labels,x:Node)->nat decreases g.len(),
{if g.len()==0{0}else{(if vote(g[0],u) && get(l,g[0].neighbor)==x{1nat}else{0nat})+frequency(g.drop_first(),u,l,x)}}
pub open spec fn count_fold(g:Seq<Coord>,u:Node,l:Labels,c:Counts)->Counts decreases g.len(),
{if g.len()==0{c}else{let a=g[0];let x=get(l,a.neighbor);count_fold(g.drop_first(),u,l,if vote(a,u){c.insert(x,count(c,x)+1)}else{c})}}
pub open spec fn counts(g:Seq<Coord>,u:Node,l:Labels)->Counts {count_fold(g,u,l,Map::empty())}
pub open spec fn better(a:(Node,nat),b:(Node,nat))->bool {a.1>b.1 || (a.1==b.1 && a.0<=b.0)}
pub open spec fn best_fold(keys:Seq<Node>,c:Counts,b:(Node,nat))->(Node,nat) decreases keys.len(),
{if keys.len()==0{b}else{let x=keys[0];let n=count(c,x);best_fold(keys.drop_first(),c,if n>b.1 || (n==b.1 && x<b.0){(x,n)}else{b})}}
pub open spec fn keys(c:Counts)->Seq<Node> {c.dom().to_sorted_seq(|a:Node,b:Node|a<=b)}
pub open spec fn winner(g:Seq<Coord>,u:Node,l:Labels)->Node {let c=counts(g,u,l);best_fold(keys(c),c,(get(l,u),0)).0}
pub open spec fn cround(g:Seq<Coord>,l:Labels)->Labels {Map::new(members(g),|u:Node|winner(g,u,l))}
pub struct CResult {pub labels:Labels,pub rounds:nat}
pub open spec fn crun(g:Seq<Coord>,l:Labels,remaining:nat)->CResult decreases remaining,
{if members(g).len()==0 || remaining==0{CResult{labels:l,rounds:0}}else{let next=cround(g,l);if changed(g,l,next)==0{CResult{labels:next,rounds:1}}else{let r=crun(g,next,(remaining-1) as nat);CResult{rounds:r.rounds+1,..r}}}}
pub open spec fn cdlp(g:Seq<Coord>,limit:int)->CResult {crun(g,initial(g),if limit>0{limit as nat}else{0})}
pub proof fn theorem_raw_coordinate_counting(g:Seq<Coord>,u:Node,l:Labels,c:Counts)
    ensures forall|x:Node|#[trigger] count(count_fold(g,u,l,c),x)==count(c,x)+frequency(g,u,l,x),
        forall|x:Node|#[trigger] count_fold(g,u,l,c).contains_key(x) <==> c.contains_key(x) || frequency(g,u,l,x)>0,
    decreases g.len(),
{
    if g.len()>0{let a=g[0];let x=get(l,a.neighbor);theorem_raw_coordinate_counting(g.drop_first(),u,l,if vote(a,u){c.insert(x,count(c,x)+1)}else{c});}
}
pub proof fn lemma_frequency_witness(g:Seq<Coord>,u:Node,l:Labels,x:Node)
    ensures frequency(g,u,l,x)>0 <==> exists|i:int|0<=i<g.len() && vote(g[i],u) && get(l,g[i].neighbor)==x,
    decreases g.len(),
{if g.len()>0{lemma_frequency_witness(g.drop_first(),u,l,x);if frequency(g.drop_first(),u,l,x)>0{let i=choose|i:int|0<=i<g.drop_first().len() && vote(g.drop_first()[i],u) && get(l,g.drop_first()[i].neighbor)==x;assert(g[i+1]==g.drop_first()[i]);}}}
pub proof fn lemma_better_transitive(a:(Node,nat),b:(Node,nat),c:(Node,nat))
    requires better(a,b),better(b,c),ensures better(a,c),
{}
pub proof fn lemma_best_fold(keys:Seq<Node>,c:Counts,b:(Node,nat))
    ensures better(best_fold(keys,c,b),b),
        forall|x:Node|keys.contains(x) ==> #[trigger] better(best_fold(keys,c,b),(x,count(c,x))),
        best_fold(keys,c,b)==b || exists|i:int|0<=i<keys.len() && best_fold(keys,c,b)==(keys[i],count(c,keys[i])),
    decreases keys.len(),
{
    if keys.len()>0{
        let x=keys[0];let n=count(c,x);let next=if n>b.1 || (n==b.1 && x<b.0){(x,n)}else{b};lemma_best_fold(keys.drop_first(),c,next);
        lemma_better_transitive(best_fold(keys,c,b),next,b);lemma_better_transitive(best_fold(keys,c,b),next,(x,n));
        assert forall|v:Node|keys.contains(v) implies better(best_fold(keys,c,b),(v,count(c,v))) by {if v!=x{assert(keys.drop_first().contains(v));}}
        if best_fold(keys,c,b)!=b && best_fold(keys,c,b)!=next{let i=choose|i:int|0<=i<keys.drop_first().len() && best_fold(keys,c,b)==(keys.drop_first()[i],count(c,keys.drop_first()[i]));assert(keys[i+1]==keys.drop_first()[i]);}
    }
}
pub proof fn lemma_ordered_count_keys(c:Counts)
    ensures keys(c).to_set()==c.dom(),keys(c).len()==c.dom().len(),
{
    c.dom().lemma_to_seq_to_set_id();c.dom().lemma_to_seq_len();let q=c.dom().to_seq();q.lemma_sort_by_ensures(|a:Node,b:Node|a<=b);
}
pub proof fn theorem_cdlp_most_votes_then_least_label(g:Seq<Coord>,u:Node,l:Labels)
    ensures (counts(g,u,l).dom().len()==0 ==> winner(g,u,l)==get(l,u)),
        (counts(g,u,l).dom().len()>0 ==> counts(g,u,l).contains_key(winner(g,u,l)) && frequency(g,u,l,winner(g,u,l))>0),
        forall|x:Node|#[trigger] frequency(g,u,l,x)>0 ==> frequency(g,u,l,winner(g,u,l))>=frequency(g,u,l,x) && (frequency(g,u,l,winner(g,u,l))==frequency(g,u,l,x) ==> winner(g,u,l)<=x),
{
    theorem_raw_coordinate_counting(g,u,l,Map::empty());let c=counts(g,u,l);lemma_ordered_count_keys(c);lemma_best_fold(keys(c),c,(get(l,u),0));
    if c.dom().len()>0{let x=c.dom().choose();assert(keys(c).contains(x));assert(count(c,x)>0);assert(best_fold(keys(c),c,(get(l,u),0)).1>0);}
}
pub proof fn theorem_self_loop_is_no_vote(a:Coord,u:Node,l:Labels,c:Counts)
    requires a.owner==u,a.neighbor==u,
    ensures count_fold(seq![a],u,l,c)==c,
{reveal_with_fuel(count_fold,2);}
pub proof fn theorem_cdlp_finite_budget_and_fixed_stop(g:Seq<Coord>,l:Labels,r:nat)
    requires l.dom()==members(g),
    ensures crun(g,l,r).labels.dom()==members(g),crun(g,l,r).rounds<=r,
        r==0 ==> crun(g,l,r).labels==l && crun(g,l,r).rounds==0,
        (r>0 && members(g).len()>0 && cround(g,l)==l) ==> crun(g,l,r).labels==l && crun(g,l,r).rounds==1,
    decreases r,
{
    if r>0 && members(g).len()>0{
        lemma_changed_exactly_map_inequality(g,l,cround(g,l));if cround(g,l)!=l{theorem_cdlp_finite_budget_and_fixed_stop(g,cround(g,l),(r-1) as nat);}
    }
}
pub open spec fn swap(l:Labels)->Labels {Map::new(set![0nat,1nat],|u:Node|if u==0{l[1]}else{l[0]})}
pub proof fn lemma_pair_cdlp_swaps_old_labels(l:Labels)
    requires l.dom()==set![0nat,1nat],l[0]!=l[1],
    ensures cround(pair(),l)==swap(l),changed(pair(),l,cround(pair(),l))>0,
{
    let g=pair();reveal_with_fuel(Seq::filter,3);assert(g.filter(|a:Coord|selected(a)) =~= g);assert(g.map_values(|a:Coord|a.owner) =~= seq![0nat,1nat]);assert(members(g) =~= set![0nat,1nat]);
    reveal_with_fuel(count_fold,3);reveal_with_fuel(frequency,3);
    theorem_cdlp_most_votes_then_least_label(g,0,l);theorem_cdlp_most_votes_then_least_label(g,1,l);
    assert(counts(g,0,l).dom() =~= set![l[1]]);assert(counts(g,1,l).dom() =~= set![l[0]]);
    assert(cround(g,l) =~= swap(l));lemma_changed_exactly_map_inequality(g,l,cround(g,l));
}
pub proof fn theorem_two_node_oscillation_is_limit_parity(l:Labels,r:nat)
    requires l.dom()==set![0nat,1nat],l[0]!=l[1],
    ensures crun(pair(),l,r).rounds==r,crun(pair(),l,r).labels==if r%2==0{l}else{swap(l)},
    decreases r,
{
    if r>0{lemma_pair_cdlp_swaps_old_labels(l);theorem_two_node_oscillation_is_limit_parity(swap(l),(r-1) as nat);assert(swap(swap(l)) =~= l);}
}

}
