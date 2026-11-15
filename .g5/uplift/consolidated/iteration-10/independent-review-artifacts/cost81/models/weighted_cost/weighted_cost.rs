// DijkstraCost actual two queues/decrease-key and hop fallback. Integer raw graph.
use vstd::prelude::*;
use vstd::seq_lib::*;
#[path="../weighted_paths/weighted_paths.rs"] pub mod json;
verus! {
pub type Arc=json::Arc;
pub type Entry=(nat,int);
pub struct Side {pub queue:Set<Entry>,pub dist:Map<int,nat>,pub hop:Map<int,nat>,pub done:Set<int>,pub witness:Map<int,Seq<Arc>>}
pub struct State {pub forward:Side,pub backward:Side,pub best:Option<nat>,pub best_hops:nat,pub best_path:Seq<Arc>}
pub open spec fn side(s:State,b:bool)->Side {if b{s.backward}else{s.forward}}
pub open spec fn put(s:State,b:bool,z:Side)->State {if b{State{backward:z,..s}}else{State{forward:z,..s}}}
pub open spec fn root(c:json::Config,b:bool)->int {if b{c.dst}else{c.src}}
pub open spec fn reverse(a:Arc)->Arc {((1-a.0) as nat,a.1,a.4,a.3,a.2)}
pub open spec fn select(c:json::Config,b:bool,a:Arc)->bool {
    c.raw.contains_key(a) && a.1==c.graph && (match c.direction {
        json::Dir::Out=>a.0==(if b{1nat}else{0nat}),
        json::Dir::In=>a.0==(if b{0nat}else{1nat}),json::Dir::Both=>a.0<=1})
    && (c.predicates.len()==0 || c.predicates.contains(a.3))
}
pub open spec fn frame(c:json::Config)->bool {
    json::graph_frame(c) && forall|b:bool,a:Arc|#[trigger] select(c,b,a) ==> select(c,!b,reverse(a)) && json::weight(c,a)==json::weight(c,reverse(a))
}
pub open spec fn walk(c:json::Config,b:bool,from:int,to:int,p:Seq<Arc>)->bool
    decreases p.len(),
{if p.len()==0{from==to}else{select(c,b,p[0]) && p[0].2==from && walk(c,b,p[0].4,to,p.drop_first())}}
pub open spec fn reverse_path(p:Seq<Arc>)->Seq<Arc>
    decreases p.len(),
{if p.len()==0{seq![]}else{reverse_path(p.drop_first()).push(reverse(p[0]))}}
pub open spec fn neighbors(c:json::Config,b:bool,u:int)->Seq<Arc> {c.arcs.filter(|a:Arc|select(c,b,a) && a.2==u)}
pub open spec fn order()->spec_fn(Entry,Entry)->bool {|a:Entry,b:Entry|a.0<b.0 || (a.0==b.0 && a.1<=b.1)}
pub open spec fn minimum(q:Set<Entry>)->Entry {q.to_seq().sort_by(order())[0]}
pub open spec fn initial_side(c:json::Config,b:bool)->Side {
    let r=root(c,b);Side{queue:set![(0nat,r)],dist:map![r=>0nat],hop:map![r=>0nat],done:Set::empty(),witness:map![r=>seq![]]}
}
pub open spec fn initial(c:json::Config)->State {State{forward:initial_side(c,false),backward:initial_side(c,true),best:None,best_hops:0,best_path:seq![]}}
pub open spec fn accept(z:Side,e:Entry)->Side {Side{queue:z.queue.remove(e),done:z.done.insert(e.1),..z}}
pub open spec fn admitted(c:json::Config,b:bool,z:Side,e:Entry,a:Arc)->bool {
    select(c,b,a) && a.2==e.1 && !z.done.contains(a.4) && e.0+json::weight(c,a)<=c.cap
}
pub open spec fn decrease(c:json::Config,b:bool,z:Side,e:Entry,a:Arc)->Side {
    let v=a.4;let n=e.0+json::weight(c,a);
    if !admitted(c,b,z,e,a) || (z.dist.contains_key(v) && z.dist[v]<=n){z}
    else{let q=if z.dist.contains_key(v){z.queue.remove((z.dist[v],v))}else{z.queue};
        Side{queue:q.insert((n,v)),dist:z.dist.insert(v,n),hop:z.hop.insert(v,z.hop[e.1]+1),
            witness:z.witness.insert(v,z.witness[e.1].push(a)),..z}}
}
pub open spec fn relax(c:json::Config,s:State,b:bool,e:Entry,a:Arc)->State {
    let z=side(s,b);let t=put(s,b,decrease(c,b,z,e,a));let v=a.4;
    if !admitted(c,b,z,e,a) || !side(t,!b).dist.contains_key(v){t}
    else{let n=side(t,b).dist[v]+side(t,!b).dist[v];
        if s.best.is_some() && s.best.unwrap()<=n{t}else{
            State{best:Some(n),best_hops:side(t,false).hop[v]+side(t,true).hop[v],
                best_path:side(t,false).witness[v]+reverse_path(side(t,true).witness[v]),..t}}}
}
pub open spec fn expand(c:json::Config,s:State,b:bool,e:Entry,arcs:Seq<Arc>)->State
    decreases arcs.len(),
{if arcs.len()==0{s}else{expand(c,relax(c,s,b,e,arcs[0]),b,e,arcs.drop_first())}}
pub enum Reason {Empty,FrontSum}
pub enum Event {Continue(State),Halt(Reason)}
pub open spec fn step(c:json::Config,s:State)->Event {
    if s.forward.queue.len()==0 || s.backward.queue.len()==0{Event::Halt(Reason::Empty)}else{
        let f=minimum(s.forward.queue);let r=minimum(s.backward.queue);
        if s.best.is_some() && f.0+r.0>=s.best.unwrap(){Event::Halt(Reason::FrontSum)}else{
            let b=r.0<f.0;let e=if b{r}else{f};let t=put(s,b,accept(side(s,b),e));
            if e.0>=c.cap{Event::Continue(t)}else{Event::Continue(expand(c,t,b,e,neighbors(c,b,e.1)))}}}
}
pub open spec fn nodes(c:json::Config)->Set<int> {json::nodes(c).to_set().insert(c.dst)}
#[verifier::opaque]
pub open spec fn base(c:json::Config,b:bool,z:Side)->bool {
    &&& z.dist.contains_key(root(c,b)) && z.dist[root(c,b)]==0
    &&& z.hop.dom()==z.dist.dom() && z.witness.dom()==z.dist.dom()
    &&& forall|v:int|z.dist.contains_key(v) ==> z.dist[v]<=c.cap && nodes(c).contains(v)
        && walk(c,b,root(c,b),v,z.witness[v]) && json::cost(c,z.witness[v])==z.dist[v] && z.witness[v].len()==z.hop[v]
    &&& forall|v:int|z.done.contains(v) ==> z.dist.contains_key(v)
    &&& forall|q:Entry|z.queue.contains(q) <==> z.dist.contains_key(q.1) && !z.done.contains(q.1) && z.dist[q.1]==q.0
}
#[verifier::opaque]
pub open spec fn optimal(c:json::Config,b:bool,z:Side)->bool {
    forall|v:int,p:Seq<Arc>|z.done.contains(v) && walk(c,b,root(c,b),v,p) && json::cost(c,p)<=c.cap ==> z.dist[v]<=json::cost(c,p)
}
pub open spec fn closed_for(c:json::Config,b:bool,z:Side,closed:Set<int>)->bool {
    forall|u:int,a:Arc|closed.contains(u) && select(c,b,a) && a.2==u && z.dist[u]+json::weight(c,a)<=c.cap
        ==> z.dist.contains_key(a.4) && z.dist[a.4]<=z.dist[u]+json::weight(c,a)
}
pub open spec fn side_inv(c:json::Config,b:bool,z:Side)->bool {base(c,b,z) && optimal(c,b,z) && closed_for(c,b,z,z.done)}
#[verifier::opaque]
pub open spec fn best_inv(c:json::Config,s:State)->bool {
    (forall|v:int|s.forward.dist.contains_key(v) && s.backward.dist.contains_key(v) ==> s.best.is_some() && s.best.unwrap()<=s.forward.dist[v]+s.backward.dist[v])
    && (s.best.is_some() ==> walk(c,false,c.src,c.dst,s.best_path) && json::cost(c,s.best_path)==s.best.unwrap() && s.best_path.len()==s.best_hops)
}
pub open spec fn inv(c:json::Config,s:State)->bool {side_inv(c,false,s.forward) && side_inv(c,true,s.backward) && best_inv(c,s)}
pub proof fn lemma_order()
    ensures vstd::relations::total_ordering(order()),
{}
pub proof fn lemma_minimum(q:Set<Entry>)
    requires q.len()>0,
    ensures q.contains(minimum(q)),forall|e:Entry|q.contains(e) ==> minimum(q).0<=e.0,
{
    lemma_order();q.lemma_to_seq_to_set_id();q.lemma_to_seq_len();let seq=q.to_seq();seq.lemma_sort_by_ensures(order());
    seq.to_multiset_ensures();seq.sort_by(order()).to_multiset_ensures();assert(seq.sort_by(order()).len()==seq.len());
    seq.sort_by(order()).to_set_ensures();seq.to_set_ensures();
    assert(q.contains(minimum(q))) by {let sorted=seq.sort_by(order());assert(sorted.contains(sorted[0]));to_multiset_contains(sorted,sorted[0]);to_multiset_contains(seq,sorted[0]);}
    assert forall|e:Entry|q.contains(e) implies minimum(q).0<=e.0 by {
        let sorted=seq.sort_by(order());assert(seq.contains(e));to_multiset_contains(seq,e);to_multiset_contains(sorted,e);
        let i=choose|i:int|0<=i<sorted.len() && sorted[i]==e;assert(order()(sorted[0],sorted[i]));
    }
}
pub proof fn lemma_walk_push(c:json::Config,b:bool,from:int,via:int,to:int,p:Seq<Arc>,a:Arc)
    requires walk(c,b,from,via,p),select(c,b,a),a.2==via,a.4==to,
    ensures walk(c,b,from,to,p.push(a)),json::cost(c,p.push(a))==json::cost(c,p)+json::weight(c,a),
    decreases p.len(),
{
    if p.len()>0{lemma_walk_push(c,b,p[0].4,via,to,p.drop_first(),a);assert(p.push(a).drop_first() =~= p.drop_first().push(a));}
    else{assert(p =~= Seq::<Arc>::empty());assert(p.push(a) =~= seq![a]);assert(p.push(a).drop_first() =~= Seq::<Arc>::empty());}
    reveal_with_fuel(walk,2);reveal_with_fuel(json::cost,2);
}
pub proof fn lemma_reverse_walk(c:json::Config,b:bool,from:int,to:int,p:Seq<Arc>)
    requires frame(c),walk(c,b,from,to,p),
    ensures walk(c,!b,to,from,reverse_path(p)),json::cost(c,reverse_path(p))==json::cost(c,p),reverse_path(p).len()==p.len(),
    decreases p.len(),
{
    if p.len()>0{let a=p[0];assert(select(c,!b,reverse(a)));assert(json::weight(c,reverse(a))==json::weight(c,a));
        lemma_reverse_walk(c,b,a.4,to,p.drop_first());lemma_walk_push(c,!b,to,a.4,from,reverse_path(p.drop_first()),reverse(a));}
}
pub proof fn lemma_walk_concat(c:json::Config,b:bool,from:int,via:int,to:int,p:Seq<Arc>,q:Seq<Arc>)
    requires walk(c,b,from,via,p),walk(c,b,via,to,q),
    ensures walk(c,b,from,to,p+q),json::cost(c,p+q)==json::cost(c,p)+json::cost(c,q),
    decreases p.len(),
{
    if p.len()>0{lemma_walk_concat(c,b,p[0].4,via,to,p.drop_first(),q);assert((p+q).drop_first() =~= p.drop_first()+q);}
    else{assert(p =~= Seq::<Arc>::empty());assert(p+q =~= q);}
    reveal_with_fuel(walk,2);reveal_with_fuel(json::cost,2);
}
pub proof fn theorem_initial(c:json::Config)
    requires c.src!=c.dst,
    ensures inv(c,initial(c)),
{
    reveal(base);reveal(optimal);reveal(best_inv);
    assert(json::nodes(c).len()==c.arcs.len()+1);assert(json::nodes(c)[c.arcs.len() as int]==c.src);assert(json::nodes(c).contains(c.src));
    json::nodes(c).to_set_ensures();
}
pub open spec fn refines(z:Side,t:Side)->bool {
    z.done==t.done
    && (forall|v:int|z.dist.contains_key(v) ==> t.dist.contains_key(v) && t.dist[v]<=z.dist[v])
    && (forall|v:int|z.done.contains(v) ==> t.dist[v]==z.dist[v])
}
pub proof fn lemma_neighbor_node(c:json::Config,b:bool,a:Arc)
    requires frame(c),select(c,b,a),
    ensures nodes(c).contains(a.4),
{
    assert(c.arcs.contains(a));let i=choose|i:int|0<=i<c.arcs.len() && c.arcs[i]==a;
    assert(json::nodes(c).len()==c.arcs.len()+1);assert(json::nodes(c)[i]==a.4);assert(json::nodes(c).contains(a.4));
    json::nodes(c).to_set_ensures();
}
pub proof fn lemma_decrease_refines(c:json::Config,b:bool,z:Side,e:Entry,a:Arc)
    ensures refines(z,decrease(c,b,z,e,a)),
{}
pub proof fn lemma_decrease_base(c:json::Config,b:bool,z:Side,e:Entry,a:Arc)
    requires frame(c),base(c,b,z),z.done.contains(e.1),z.dist[e.1]==e.0,
    ensures base(c,b,decrease(c,b,z,e,a)),
{
    let t=decrease(c,b,z,e,a);let v=a.4;let n=e.0+json::weight(c,a);
    if t!=z{
        assert(t.witness[v]==z.witness[e.1].push(a));
        reveal(base);assert(z.dist.contains_key(e.1));
        assert(walk(c,b,root(c,b),e.1,z.witness[e.1]));lemma_walk_push(c,b,root(c,b),e.1,v,z.witness[e.1],a);
        lemma_neighbor_node(c,b,a);assert(n>0);assert(v!=root(c,b));
        assert(t.dist.contains_key(root(c,b)));assert(t.dist[root(c,b)]==0);
        assert(t.hop.dom()==t.dist.dom());assert(t.witness.dom()==t.dist.dom());
        assert forall|u:int|t.done.contains(u) implies t.dist.contains_key(u) by {assert(z.done.contains(u));assert(z.dist.contains_key(u));}
        assert forall|u:int|t.dist.contains_key(u) implies t.dist[u]<=c.cap && nodes(c).contains(u)
            && walk(c,b,root(c,b),u,t.witness[u]) && json::cost(c,t.witness[u])==t.dist[u] && t.witness[u].len()==t.hop[u] by {
            if u!=v{assert(z.dist.contains_key(u));}
        }
        assert forall|q:Entry|t.queue.contains(q) <==> t.dist.contains_key(q.1) && !t.done.contains(q.1) && t.dist[q.1]==q.0 by {
            if q.1==v{if q!=(n,v){assert(!t.queue.contains(q));}}
            else{assert(t.queue.contains(q)==z.queue.contains(q));}
        }
    }
}
pub proof fn lemma_optimal_refines(c:json::Config,b:bool,z:Side,t:Side)
    requires optimal(c,b,z),refines(z,t),
    ensures optimal(c,b,t),
{reveal(optimal);}
pub proof fn lemma_closed_refines(c:json::Config,b:bool,z:Side,t:Side,closed:Set<int>)
    requires base(c,b,z),refines(z,t),closed.subset_of(z.done),closed_for(c,b,z,closed),
    ensures closed_for(c,b,t,closed),
{
    assert forall|u:int,a:Arc|closed.contains(u) && select(c,b,a) && a.2==u && t.dist[u]+json::weight(c,a)<=c.cap implies
        t.dist.contains_key(a.4) && t.dist[a.4]<=t.dist[u]+json::weight(c,a) by {
        assert(z.done.contains(u));assert(z.dist[u]==t.dist[u]);
        assert(z.dist.contains_key(a.4));assert(t.dist.contains_key(a.4));
    }
}
pub proof fn lemma_frontier(c:json::Config,b:bool,z:Side,from:int,to:int,before:nat,p:Seq<Arc>)
    requires base(c,b,z),closed_for(c,b,z,z.done),walk(c,b,from,to,p),!z.done.contains(to),
        z.dist.contains_key(from),z.dist[from]<=before,before+json::cost(c,p)<=c.cap,
    ensures exists|q:Entry|z.queue.contains(q) && q.0<=before+json::cost(c,p),
    decreases p.len(),
{
    reveal(base);
    if !z.done.contains(from){assert(z.queue.contains((z.dist[from],from)));}
    else{
        if p.len()==0{assert(from==to);assert(false);}
        else{let a=p[0];assert(select(c,b,a));assert(z.dist[from]+json::weight(c,a)<=c.cap);
            assert(z.dist.contains_key(a.4));assert(z.dist[a.4]<=before+json::weight(c,a));
            lemma_frontier(c,b,z,a.4,to,before+json::weight(c,a),p.drop_first());
            let q=choose|q:Entry|z.queue.contains(q) && q.0<=before+json::weight(c,a)+json::cost(c,p.drop_first());
        }
    }
}
pub proof fn lemma_accept_base(c:json::Config,b:bool,z:Side,e:Entry)
    requires base(c,b,z),z.queue.contains(e),
    ensures base(c,b,accept(z,e)),!z.done.contains(e.1),z.dist[e.1]==e.0,
{
    reveal(base);let t=accept(z,e);
    assert(z.dist.contains_key(e.1));assert(z.dist[e.1]==e.0);assert(!z.done.contains(e.1));
    assert(t.dist.contains_key(root(c,b)));assert(t.dist[root(c,b)]==0);
    assert(t.hop.dom()==t.dist.dom());assert(t.witness.dom()==t.dist.dom());
    assert forall|v:int|t.dist.contains_key(v) implies t.dist[v]<=c.cap && nodes(c).contains(v)
        && walk(c,b,root(c,b),v,t.witness[v]) && json::cost(c,t.witness[v])==t.dist[v] && t.witness[v].len()==t.hop[v] by {
        assert(z.dist.contains_key(v));assert(t.witness[v]==z.witness[v]);
    }
    assert forall|v:int|t.done.contains(v) implies t.dist.contains_key(v) by {if v!=e.1{assert(z.done.contains(v));}}
    assert forall|q:Entry|t.queue.contains(q) <==> t.dist.contains_key(q.1) && !t.done.contains(q.1) && t.dist[q.1]==q.0 by {
        if q.1==e.1{assert(!t.queue.contains(q));}
    }
}
pub proof fn lemma_accept_optimal(c:json::Config,b:bool,z:Side,e:Entry)
    requires side_inv(c,b,z),z.queue.contains(e),forall|q:Entry|z.queue.contains(q) ==> e.0<=q.0,
    ensures optimal(c,b,accept(z,e)),
{
    reveal(base);assert(!z.done.contains(e.1));
    reveal(optimal);
    assert forall|v:int,p:Seq<Arc>|accept(z,e).done.contains(v) && walk(c,b,root(c,b),v,p) && json::cost(c,p)<=c.cap
        implies accept(z,e).dist[v]<=json::cost(c,p) by {
        if v==e.1{lemma_frontier(c,b,z,root(c,b),v,0,p);
            let q=choose|q:Entry|z.queue.contains(q) && q.0<=json::cost(c,p);assert(e.0<=q.0);}
    }
}
pub proof fn lemma_decrease_covers(c:json::Config,b:bool,z:Side,e:Entry,a:Arc)
    requires base(c,b,z),optimal(c,b,z),z.done.contains(e.1),z.dist[e.1]==e.0,
        select(c,b,a),a.2==e.1,e.0+json::weight(c,a)<=c.cap,
    ensures decrease(c,b,z,e,a).dist.contains_key(a.4),decrease(c,b,z,e,a).dist[a.4]<=e.0+json::weight(c,a),
{
    let t=decrease(c,b,z,e,a);let v=a.4;
    if z.done.contains(v){
        reveal(base);reveal(optimal);lemma_walk_push(c,b,root(c,b),e.1,v,z.witness[e.1],a);
        let p=z.witness[e.1].push(a);assert(walk(c,b,root(c,b),v,p));assert(json::cost(c,p)==e.0+json::weight(c,a));
        assert(z.dist[v]<=json::cost(c,p));
    }
}

pub proof fn lemma_relax_projection(c:json::Config,s:State,b:bool,e:Entry,a:Arc)
    ensures side(relax(c,s,b,e,a),b)==decrease(c,b,side(s,b),e,a),side(relax(c,s,b,e,a),!b)==side(s,!b),
{}
pub proof fn lemma_relax_best(c:json::Config,s:State,b:bool,e:Entry,a:Arc)
    requires frame(c),base(c,false,s.forward),base(c,true,s.backward),best_inv(c,s),
        side(s,b).done.contains(e.1),side(s,b).dist[e.1]==e.0,
    ensures best_inv(c,relax(c,s,b,e,a)),base(c,false,relax(c,s,b,e,a).forward),base(c,true,relax(c,s,b,e,a).backward),
{
    let z=side(s,b);let t=relax(c,s,b,e,a);let d=decrease(c,b,z,e,a);let v=a.4;
    lemma_relax_projection(c,s,b,e,a);lemma_decrease_base(c,b,z,e,a);
    assert(base(c,false,t.forward));assert(base(c,true,t.backward));
    if admitted(c,b,z,e,a) && side(s,!b).dist.contains_key(v){
        assert(d.dist.contains_key(v));let n=d.dist[v]+side(s,!b).dist[v];
        assert(n==t.forward.dist[v]+t.backward.dist[v]);
        if s.best.is_none() || n<s.best.unwrap(){
            reveal(base);
            let p=t.forward.witness[v];let q=t.backward.witness[v];
            lemma_reverse_walk(c,true,c.dst,v,q);
            lemma_walk_concat(c,false,c.src,v,c.dst,p,reverse_path(q));
            assert(t.best==Some(n));assert(t.best_path==p+reverse_path(q));
            assert(t.best_path.len()==t.best_hops);
        }
    }
    reveal(best_inv);
    assert(s.best.is_some() ==> t.best.is_some() && t.best.unwrap()<=s.best.unwrap());
    assert forall|u:int|t.forward.dist.contains_key(u) && t.backward.dist.contains_key(u) implies t.best.is_some() && t.best.unwrap()<=t.forward.dist[u]+t.backward.dist[u] by {
        if u==v && admitted(c,b,z,e,a){
            assert(side(s,!b).dist.contains_key(v));let n=t.forward.dist[v]+t.backward.dist[v];assert(t.best.is_some());assert(t.best.unwrap()<=n);
        }else{
            assert(s.forward.dist.contains_key(u));assert(s.backward.dist.contains_key(u));
            assert(t.forward.dist[u]==s.forward.dist[u]);assert(t.backward.dist[u]==s.backward.dist[u]);
        }
    }
}
pub open spec fn stage(c:json::Config,s:State,b:bool,closed:Set<int>)->bool {
    base(c,false,s.forward) && base(c,true,s.backward) && optimal(c,false,s.forward) && optimal(c,true,s.backward)
    && closed.subset_of(side(s,b).done) && closed_for(c,b,side(s,b),closed)
    && closed_for(c,!b,side(s,!b),side(s,!b).done) && best_inv(c,s)
}
pub proof fn lemma_relax_stage(c:json::Config,s:State,b:bool,closed:Set<int>,e:Entry,a:Arc)
    requires frame(c),stage(c,s,b,closed),side(s,b).done.contains(e.1),side(s,b).dist[e.1]==e.0,
    ensures stage(c,relax(c,s,b,e,a),b,closed),refines(side(s,b),side(relax(c,s,b,e,a),b)),
{
    let z=side(s,b);let t=relax(c,s,b,e,a);let d=decrease(c,b,z,e,a);
    lemma_relax_projection(c,s,b,e,a);lemma_decrease_refines(c,b,z,e,a);
    lemma_relax_best(c,s,b,e,a);lemma_optimal_refines(c,b,z,d);lemma_closed_refines(c,b,z,d,closed);
}
pub proof fn lemma_refines_transitive(z:Side,t:Side,u:Side)
    requires refines(z,t),refines(t,u),
    ensures refines(z,u),
{}
pub proof fn lemma_expand_stage(c:json::Config,s:State,b:bool,closed:Set<int>,e:Entry,arcs:Seq<Arc>)
    requires frame(c),stage(c,s,b,closed),side(s,b).done.contains(e.1),side(s,b).dist[e.1]==e.0,
    ensures stage(c,expand(c,s,b,e,arcs),b,closed),refines(side(s,b),side(expand(c,s,b,e,arcs),b)),
        side(expand(c,s,b,e,arcs),!b)==side(s,!b),
        forall|a:Arc|arcs.contains(a) && select(c,b,a) && a.2==e.1 && e.0+json::weight(c,a)<=c.cap
            ==> side(expand(c,s,b,e,arcs),b).dist.contains_key(a.4) && side(expand(c,s,b,e,arcs),b).dist[a.4]<=e.0+json::weight(c,a),
    decreases arcs.len(),
{
    if arcs.len()>0{
        let t=relax(c,s,b,e,arcs[0]);let u=expand(c,t,b,e,arcs.drop_first());
        lemma_relax_stage(c,s,b,closed,e,arcs[0]);lemma_relax_projection(c,s,b,e,arcs[0]);
        assert(side(t,b).done.contains(e.1));assert(side(t,b).dist[e.1]==e.0);
        lemma_expand_stage(c,t,b,closed,e,arcs.drop_first());lemma_refines_transitive(side(s,b),side(t,b),side(u,b));
        assert forall|a:Arc|arcs.contains(a) && select(c,b,a) && a.2==e.1 && e.0+json::weight(c,a)<=c.cap implies
            side(u,b).dist.contains_key(a.4) && side(u,b).dist[a.4]<=e.0+json::weight(c,a) by {
            if a==arcs[0]{lemma_decrease_covers(c,b,side(s,b),e,a);assert(side(t,b).dist.contains_key(a.4));}
            else{let i=choose|i:int|0<=i<arcs.len() && arcs[i]==a;assert(i>0);assert(arcs.drop_first()[i-1]==a);assert(arcs.drop_first().contains(a));}
        }
    }
}
pub proof fn theorem_continue_preserves(c:json::Config,s:State,t:State)
    requires frame(c),inv(c,s),step(c,s)==Event::Continue(t),
    ensures inv(c,t),
{
    assert(s.forward.queue.len()>0 && s.backward.queue.len()>0);let f=minimum(s.forward.queue);let r=minimum(s.backward.queue);
    lemma_minimum(s.forward.queue);lemma_minimum(s.backward.queue);let b=r.0<f.0;let e=if b{r}else{f};let z=side(s,b);
    assert(z.queue.contains(e));assert(forall|q:Entry|z.queue.contains(q) ==> e.0<=q.0);
    lemma_accept_base(c,b,z,e);lemma_accept_optimal(c,b,z,e);
    let accepted=put(s,b,accept(z,e));
    assert(best_inv(c,accepted)) by {reveal(best_inv);}
    assert(stage(c,accepted,b,z.done));
    assert(side(accepted,b).done.contains(e.1));assert(side(accepted,b).dist[e.1]==e.0);
    if e.0<c.cap{lemma_expand_stage(c,accepted,b,z.done,e,neighbors(c,b,e.1));}
    assert(stage(c,t,b,z.done));assert(side(t,b).done==z.done.insert(e.1));
    assert forall|u:int,a:Arc|side(t,b).done.contains(u) && select(c,b,a) && a.2==u && side(t,b).dist[u]+json::weight(c,a)<=c.cap implies
        side(t,b).dist.contains_key(a.4) && side(t,b).dist[a.4]<=side(t,b).dist[u]+json::weight(c,a) by {
        if u==e.1{
            assert(side(t,b).dist[u]==e.0);assert(json::weight(c,a)>0);assert(e.0<c.cap);
            assert(c.arcs.contains(a));let i=choose|i:int|0<=i<c.arcs.len() && c.arcs[i]==a;
            c.arcs.lemma_filter_contains(|a:Arc|select(c,b,a) && a.2==e.1,i);
            assert(neighbors(c,b,e.1).contains(a));
        }else{assert(z.done.contains(u));}
    }
    assert(side_inv(c,b,side(t,b)));assert(side_inv(c,!b,side(t,!b)));
}
// Follow the forward settled prefix to derive both queued frontier witnesses.
pub proof fn lemma_two_frontiers(c:json::Config,s:State,from:int,before:nat,p:Seq<Arc>)
    requires frame(c),inv(c,s),walk(c,false,from,c.dst,p),s.forward.dist.contains_key(from),s.forward.dist[from]<=before,
        before+json::cost(c,p)<=c.cap,s.best.is_none() || before+json::cost(c,p)<s.best.unwrap(),
    ensures exists|f:Entry,r:Entry|s.forward.queue.contains(f) && s.backward.queue.contains(r) && f.0+r.0<=before+json::cost(c,p),
    decreases p.len(),
{
    reveal(base);reveal(best_inv);
    if s.forward.done.contains(from){
        if p.len()==0{assert(from==c.dst);assert(s.backward.dist.contains_key(from));assert(s.backward.dist[from]==0);assert(s.best.is_some());assert(false);}
        else{let a=p[0];assert(s.forward.dist[from]+json::weight(c,a)<=c.cap);
            assert(s.forward.dist.contains_key(a.4));assert(s.forward.dist[a.4]<=before+json::weight(c,a));
            lemma_two_frontiers(c,s,a.4,before+json::weight(c,a),p.drop_first());
            let pair=choose|pair:(Entry,Entry)|s.forward.queue.contains(pair.0) && s.backward.queue.contains(pair.1) && pair.0.0+pair.1.0<=before+json::weight(c,a)+json::cost(c,p.drop_first());
        }
    }else{
        let f=(s.forward.dist[from],from);assert(s.forward.queue.contains(f));
        lemma_reverse_walk(c,false,from,c.dst,p);let rev=reverse_path(p);
        if s.backward.done.contains(from){
            reveal(optimal);assert(s.backward.dist[from]<=json::cost(c,rev));assert(s.best.is_some());
            assert(s.best.unwrap()<=s.forward.dist[from]+s.backward.dist[from]);assert(false);
        }else{
            lemma_frontier(c,true,s.backward,c.dst,from,0,rev);
            let r=choose|q:Entry|s.backward.queue.contains(q) && q.0<=json::cost(c,rev);
            assert(f.0+r.0<=before+json::cost(c,p));
        }
    }
}
pub open spec fn unbounded_feasible(c:json::Config,p:Seq<Arc>)->bool {walk(c,false,c.src,c.dst,p) && json::cost(c,p)<=c.cap}
pub proof fn theorem_terminal_minimum(c:json::Config,s:State,p:Seq<Arc>)
    requires frame(c),inv(c,s),!(step(c,s) is Continue),unbounded_feasible(c,p),
    ensures s.best.is_some(),s.best.unwrap()<=json::cost(c,p),
{
    assert(s.forward.dist.contains_key(c.src) && s.forward.dist[c.src]==0) by {reveal(base);}
    if s.best.is_none() || json::cost(c,p)<s.best.unwrap(){
        lemma_two_frontiers(c,s,c.src,0,p);
        let pair=choose|pair:(Entry,Entry)|s.forward.queue.contains(pair.0) && s.backward.queue.contains(pair.1) && pair.0.0+pair.1.0<=json::cost(c,p);
        assert(s.forward.queue.len()>0 && s.backward.queue.len()>0);
        lemma_minimum(s.forward.queue);lemma_minimum(s.backward.queue);
        let f=minimum(s.forward.queue);let r=minimum(s.backward.queue);
        assert(f.0<=pair.0.0);assert(r.0<=pair.1.0);assert(false);
    }
}
pub proof fn theorem_terminal_no_best_means_no_path(c:json::Config,s:State,p:Seq<Arc>)
    requires frame(c),inv(c,s),!(step(c,s) is Continue),s.best.is_none() || s.best.unwrap()>c.cap,
    ensures !unbounded_feasible(c,p),
{if unbounded_feasible(c,p){theorem_terminal_minimum(c,s,p);}}
pub open spec fn rank(c:json::Config,s:State)->nat {
    nodes(c).difference(s.forward.done).len()+nodes(c).difference(s.backward.done).len()
}
pub proof fn theorem_continue_rank(c:json::Config,s:State,t:State)
    requires frame(c),inv(c,s),step(c,s)==Event::Continue(t),
    ensures rank(c,t)<rank(c,s),
{
    assert(s.forward.queue.len()>0 && s.backward.queue.len()>0);let f=minimum(s.forward.queue);let r=minimum(s.backward.queue);
    lemma_minimum(s.forward.queue);lemma_minimum(s.backward.queue);let b=r.0<f.0;let e=if b{r}else{f};let z=side(s,b);
    reveal(base);assert(z.queue.contains(e));assert(z.dist.contains_key(e.1));assert(!z.done.contains(e.1));assert(nodes(c).contains(e.1));
    let accepted=put(s,b,accept(z,e));assert(side(accepted,b).done==z.done.insert(e.1));
    if e.0<c.cap{
        lemma_accept_base(c,b,z,e);lemma_accept_optimal(c,b,z,e);
        assert(best_inv(c,accepted)) by {reveal(best_inv);}
        assert(stage(c,accepted,b,z.done));lemma_expand_stage(c,accepted,b,z.done,e,neighbors(c,b,e.1));
    }
    assert(side(t,b).done==z.done.insert(e.1));assert(side(t,!b).done==side(s,!b).done);
    nodes(c).lemma_set_insert_diff_decreases(z.done,e.1);
}
pub open spec fn terminal_trace(c:json::Config,start:State,tr:Seq<State>)->bool {
    tr.len()>0 && tr[0]==start && !(step(c,tr.last()) is Continue)
    && forall|i:int|0<=i<tr.len()-1 ==> step(c,tr[i])==Event::Continue(tr[i+1])
}
pub proof fn theorem_search_terminates(c:json::Config,s:State)
    requires frame(c),inv(c,s),
    ensures exists|tr:Seq<State>|terminal_trace(c,s,tr) && inv(c,tr.last()) && tr.len()<=rank(c,s)+1,
    decreases rank(c,s),
{
    match step(c,s){
        Event::Continue(t)=>{
            theorem_continue_preserves(c,s,t);theorem_continue_rank(c,s,t);theorem_search_terminates(c,t);
            let tail=choose|tr:Seq<State>|terminal_trace(c,t,tr) && inv(c,tr.last()) && tr.len()<=rank(c,t)+1;let tr=seq![s]+tail;
            assert(tr.last()==tail.last());
            assert forall|i:int|0<=i<tr.len()-1 implies step(c,tr[i])==Event::Continue(tr[i+1]) by {
                if i==0{assert(tr[i+1]==tail[0]);}else{assert(tr[i]==tail[i-1]);assert(tr[i+1]==tail[i]);}
            }
            assert(terminal_trace(c,s,tr));
        },
        _=>{let tr=seq![s];assert(terminal_trace(c,s,tr));}
    }
}
pub proof fn theorem_initial_search_terminates(c:json::Config)
    requires frame(c),c.src!=c.dst,
    ensures exists|tr:Seq<State>|terminal_trace(c,initial(c),tr) && inv(c,tr.last()) && tr.len()<=2*nodes(c).len()+1,
{
    theorem_initial(c);theorem_search_terminates(c,initial(c));
    assert(nodes(c).difference(Set::empty()) =~= nodes(c));assert(rank(c,initial(c))==2*nodes(c).len());
}// Choice predicates contain actual transition traces only, never an optimality
// condition, correct answer, or supplied successful state.
pub open spec fn actual_json_trace(c:json::Config)->Seq<json::Search> {
    choose|tr:Seq<json::Search>|json::terminal_trace(c,json::initial(c),tr)
}
pub open spec fn actual_json_cost(c:json::Config)->Option<nat> {
    let tr=actual_json_trace(c);
    match json::step(c,tr.last()) {json::Event::Returned{state:_,entry:e}=>Some(e.0),_=>None}
}
pub open spec fn finish(c:json::Config,s:State)->Option<nat> {
    if s.best.is_none() || s.best.unwrap()>c.cap{None}
    else if c.bound>0 && s.best_hops>c.bound{actual_json_cost(c)}
    else{s.best}
}
pub open spec fn correct_result(c:json::Config,result:Option<nat>)->bool {
    match result {
        Some(n)=>(exists|p:Seq<Arc>|json::feasible(c,p) && json::cost(c,p)==n)
            && (forall|p:Seq<Arc>|json::feasible(c,p) ==> n<=json::cost(c,p)),
        None=>forall|p:Seq<Arc>|!json::feasible(c,p),
    }
}
pub proof fn lemma_forward_is_json(c:json::Config,from:int,to:int,p:Seq<Arc>)
    ensures walk(c,false,from,to,p) <==> json::walk(c,from,to,p),
    decreases p.len(),
{
    if p.len()>0{lemma_forward_is_json(c,p[0].4,to,p.drop_first());}
    reveal_with_fuel(walk,2);reveal_with_fuel(json::walk,2);
}
pub proof fn lemma_json_trace_inv(c:json::Config,tr:Seq<json::Search>,i:nat)
    requires json::graph_frame(c),json::terminal_trace(c,json::initial(c),tr),i<tr.len(),
    ensures json::inv(c,tr[i as int]),json::no_target(c,tr[i as int]),
    decreases i,
{
    if i==0{json::theorem_initial_invariant(c);assert(tr[0]==json::initial(c));assert(json::no_target(c,json::initial(c)));}
    else{lemma_json_trace_inv(c,tr,(i-1) as nat);assert(json::step(c,tr[(i-1) as int])==json::Event::Continue(tr[i as int]));
        json::theorem_actual_continue_preserves(c,tr[(i-1) as int],tr[i as int]);}
}
pub proof fn theorem_actual_json_fallback_correct(c:json::Config)
    requires json::graph_frame(c),c.src!=c.dst,
    ensures json::terminal_trace(c,json::initial(c),actual_json_trace(c)),correct_result(c,actual_json_cost(c)),
{
    json::theorem_complete_terminating_search(c);
    assert(exists|tr:Seq<json::Search>|json::terminal_trace(c,json::initial(c),tr));
    let tr=actual_json_trace(c);assert(json::terminal_trace(c,json::initial(c),tr));
    lemma_json_trace_inv(c,tr,(tr.len()-1) as nat);assert(json::terminal(c,tr.last()));json::theorem_terminal_correct(c,tr.last());
    match json::step(c,tr.last()){
        json::Event::Returned{state:t,entry:e}=>{
            assert(actual_json_cost(c)==Some(e.0));
            let p=json::backtrack(t,c.src,json::key(e),e.0+1);assert(json::feasible(c,p));assert(json::cost(c,p)==e.0);
        },
        _=>{},
    }
}
pub proof fn theorem_finish_correct(c:json::Config,s:State)
    requires frame(c),inv(c,s),!(step(c,s) is Continue),c.src!=c.dst,
    ensures correct_result(c,finish(c,s)),
{
    if s.best.is_none() || s.best.unwrap()>c.cap{
        assert forall|p:Seq<Arc>|!json::feasible(c,p) by {
            lemma_forward_is_json(c,c.src,c.dst,p);theorem_terminal_no_best_means_no_path(c,s,p);
        }
    }else if c.bound>0 && s.best_hops>c.bound{
        assert(finish(c,s)==actual_json_cost(c));theorem_actual_json_fallback_correct(c);
    }
    else{
        reveal(best_inv);let p=s.best_path;let n=s.best.unwrap();lemma_forward_is_json(c,c.src,c.dst,p);
        assert(json::feasible(c,p));assert(json::cost(c,p)==n);
        assert forall|p:Seq<Arc>|json::feasible(c,p) implies n<=json::cost(c,p) by {
            lemma_forward_is_json(c,c.src,c.dst,p);theorem_terminal_minimum(c,s,p);
        }
    }
}
pub open spec fn actual_cost_trace(c:json::Config)->Seq<State> {
    choose|tr:Seq<State>|terminal_trace(c,initial(c),tr)
}
pub open spec fn answer(c:json::Config)->Option<nat> {
    if c.src==c.dst{Some(0)}else{finish(c,actual_cost_trace(c).last())}
}
pub proof fn lemma_cost_trace_inv(c:json::Config,tr:Seq<State>,i:nat)
    requires frame(c),c.src!=c.dst,terminal_trace(c,initial(c),tr),i<tr.len(),
    ensures inv(c,tr[i as int]),
    decreases i,
{
    if i==0{theorem_initial(c);assert(tr[0]==initial(c));}
    else{lemma_cost_trace_inv(c,tr,(i-1) as nat);assert(step(c,tr[(i-1) as int])==Event::Continue(tr[i as int]));
        theorem_continue_preserves(c,tr[(i-1) as int],tr[i as int]);}
}
pub proof fn theorem_actual_dijkstra_cost_complete(c:json::Config)
    requires frame(c),
    ensures correct_result(c,answer(c)),
        c.src!=c.dst ==> terminal_trace(c,initial(c),actual_cost_trace(c)),
{
    if c.src==c.dst{
        json::theorem_admitted_self_is_zero(c);let p=Seq::<Arc>::empty();assert(json::feasible(c,p));assert(json::cost(c,p)==0);
    }else{
        theorem_initial_search_terminates(c);assert(exists|tr:Seq<State>|terminal_trace(c,initial(c),tr));
        let tr=actual_cost_trace(c);assert(terminal_trace(c,initial(c),tr));lemma_cost_trace_inv(c,tr,(tr.len()-1) as nat);
        theorem_finish_correct(c,tr.last());
    }
}
}
