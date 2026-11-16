// DijkstraJson's raw stale-entry queue, dist/parent and minimum-seen-hop policy.
// Mathematical integer/stable projected-adjacency fragment, not executable bodies.
use vstd::prelude::*;
use vstd::seq_lib::*;
verus! {
// tag(out0/in1), graph, current node, predicate, neighbor. IDs are ordered atoms.
pub type Arc=(nat,int,int,int,int);
pub type Key=(int,nat);
pub type Entry=(nat,int,nat); // cost,node,hops; old higher-cost entries are retained
pub type Parent=(Key,Arc);
pub enum Dir {Out, In, Both}
pub struct Config {pub arcs:Seq<Arc>,pub raw:Map<Arc,Option<int>>,pub graph:int,pub src:int,pub dst:int,
    pub direction:Dir,pub predicates:Set<int>,pub cap:nat,pub bound:nat}
pub struct Search {pub queue:Set<Entry>,pub dist:Map<Key,nat>,pub parent:Map<Key,Parent>,
    pub seen:Map<int,nat>,pub done:Map<Key,nat>,pub removed:Set<Entry>}
pub open spec fn root(c:Config)->Key {(c.src,0)}
pub open spec fn key(e:Entry)->Key {(e.1,e.2)}
pub open spec fn effective(v:Option<int>)->nat {if v.is_some() && v.unwrap()>0{v.unwrap() as nat}else{1}}
pub open spec fn weight(c:Config,a:Arc)->nat {effective(c.raw[a])}
pub open spec fn selected(c:Config,a:Arc)->bool {
    c.raw.contains_key(a) && a.1==c.graph && (match c.direction{Dir::Out=>a.0==0,Dir::In=>a.0==1,Dir::Both=>a.0<=1})
    && (c.predicates.len()==0 || c.predicates.contains(a.3))
}
pub open spec fn graph_frame(c:Config)->bool {
    c.arcs.no_duplicates() && forall|a:Arc| c.raw.contains_key(a) <==> c.arcs.contains(a)
}
pub open spec fn hop_ok(c:Config,h:nat)->bool {if c.bound==0{h==0}else{h<=c.bound}}
pub open spec fn next_hop(c:Config,h:nat)->nat {if c.bound==0{0}else{h+1}}
pub open spec fn neighbors(c:Config,u:int)->Seq<Arc> {c.arcs.filter(|a:Arc|selected(c,a) && a.2==u)}
pub open spec fn entry_order()->spec_fn(Entry,Entry)->bool {|a:Entry,b:Entry|
    a.0<b.0 || (a.0==b.0 && (a.1<b.1 || (a.1==b.1 && a.2<=b.2)))}
pub open spec fn minimum(q:Set<Entry>)->Entry {q.to_seq().sort_by(entry_order())[0]}
pub open spec fn initial(c:Config)->Search {
    Search{queue:set![(0nat,c.src,0nat)],dist:map![root(c)=>0nat],parent:Map::empty(),seen:Map::empty(),done:Map::empty(),removed:Set::empty()}
}
pub open spec fn skipped(s:Search,e:Entry)->bool {s.seen.contains_key(e.1) && s.seen[e.1]<=e.2}
pub open spec fn pop_only(s:Search,e:Entry)->Search {Search{queue:s.queue.remove(e),removed:s.removed.insert(e),..s}}
pub open spec fn accept(s:Search,e:Entry)->Search {
    Search{seen:s.seen.insert(e.1,e.2),done:s.done.insert(key(e),e.0),..pop_only(s,e)}
}
pub open spec fn relax(c:Config,s:Search,from:Entry,a:Arc)->Search {
    let h=next_hop(c,from.2);let n=from.0+weight(c,a);let k=(a.4,h);
    if !selected(c,a) || a.2!=from.1 || !hop_ok(c,h) || n>c.cap ||
        (s.seen.contains_key(a.4) && s.seen[a.4]<=h) || (s.dist.contains_key(k) && s.dist[k]<=n) {s}
    else {Search{queue:s.queue.insert((n,a.4,h)),dist:s.dist.insert(k,n),parent:s.parent.insert(k,(key(from),a)),..s}}
}
pub open spec fn expand(c:Config,s:Search,from:Entry,arcs:Seq<Arc>)->Search
    decreases arcs.len(),
{if arcs.len()==0{s}else{expand(c,relax(c,s,from,arcs[0]),from,arcs.drop_first())}}
pub enum Event {Continue(Search), Returned{state:Search,entry:Entry}, Empty(Search)}
pub open spec fn step(c:Config,s:Search)->Event {
    if s.queue.len()==0 {Event::Empty(s)} else {
        let e=minimum(s.queue);
        if skipped(s,e){Event::Continue(pop_only(s,e))}else{
            let next=accept(s,e);
            if e.1==c.dst{Event::Returned{state:next,entry:e}}
            else if e.0>=c.cap || (c.bound>0 && e.2>=c.bound){Event::Continue(next)}
            else{Event::Continue(expand(c,next,e,neighbors(c,e.1)))}}}
}
pub open spec fn covered(s:Search,v:int,h:nat,cost:nat)->bool {
    (exists|e:Entry|s.queue.contains(e) && e.1==v && e.2<=h && e.0<=cost)
    || (exists|k:Key|s.done.contains_key(k) && k.0==v && k.1<=h && s.done[k]<=cost)
}
#[verifier::opaque]
pub open spec fn parent_inv(c:Config,dist:Map<Key,nat>,done:Map<Key,nat>,parent:Map<Key,Parent>)->bool {
    forall|k:Key|dist.contains_key(k) && k!=root(c) ==> {
        parent.contains_key(k) && done.contains_key(parent[k].0)
        && selected(c,parent[k].1) && parent[k].1.2==parent[k].0.0 && parent[k].1.4==k.0
        && next_hop(c,parent[k].0.1)==k.1
        && dist[k]==done[parent[k].0]+weight(c,parent[k].1)
    }
}
#[verifier::opaque]
pub open spec fn base_inv(c:Config,s:Search)->bool {
    &&& s.dist.contains_key(root(c)) && s.dist[root(c)]==0
    &&& forall|k:Key|s.dist.contains_key(k) ==> hop_ok(c,k.1) && s.dist[k]<=c.cap
        && (k.0==c.src ==> k==root(c)) && covered(s,k.0,k.1,s.dist[k])
    &&& forall|e:Entry|s.queue.contains(e) ==> s.dist.contains_key(key(e)) && s.dist[key(e)]<=e.0 && e.0<=c.cap
    &&& forall|k:Key|s.done.contains_key(k) ==> s.dist.contains_key(k) && s.dist[k]==s.done[k]
        && s.seen.contains_key(k.0) && s.seen[k.0]<=k.1
    &&& forall|v:int|s.seen.contains_key(v) ==> s.done.contains_key((v,s.seen[v]))
    &&& forall|k:Key,e:Entry|s.done.contains_key(k) && s.queue.contains(e) ==> s.done[k]<=e.0
    &&& (s.done.len()>0 ==> s.done.contains_key(root(c)))
    &&& parent_inv(c,s.dist,s.done,s.parent)
}
pub open spec fn closed_for(c:Config,s:Search,closed:Map<Key,nat>)->bool {
    forall|k:Key,a:Arc|closed.contains_key(k) && selected(c,a) && a.2==k.0
        && hop_ok(c,next_hop(c,k.1)) && closed[k]+weight(c,a)<=c.cap
        ==> covered(s,a.4,next_hop(c,k.1),closed[k]+weight(c,a))
}
#[verifier::opaque]
pub open spec fn closure(c:Config,s:Search)->bool {closed_for(c,s,s.done)}
pub open spec fn inv(c:Config,s:Search)->bool {base_inv(c,s) && closure(c,s)}
pub proof fn lemma_entry_order()
    ensures vstd::relations::total_ordering(entry_order()),
{}
pub proof fn lemma_minimum(q:Set<Entry>)
    requires q.len()>0,
    ensures q.contains(minimum(q)),forall|e:Entry|q.contains(e) ==> minimum(q).0<=e.0,
{
    lemma_entry_order();q.lemma_to_seq_to_set_id();q.lemma_to_seq_len();
    let seq=q.to_seq();seq.lemma_sort_by_ensures(entry_order());
    seq.to_multiset_ensures();seq.sort_by(entry_order()).to_multiset_ensures();
    assert(seq.sort_by(entry_order()).len()==seq.len());
    seq.sort_by(entry_order()).to_set_ensures();seq.to_set_ensures();
    assert(q.contains(minimum(q))) by {
        let sorted=seq.sort_by(entry_order());assert(sorted.contains(sorted[0]));
        to_multiset_contains(sorted,sorted[0]);to_multiset_contains(seq,sorted[0]);
    }
    assert forall|e:Entry|q.contains(e) implies minimum(q).0<=e.0 by {
        let sorted=seq.sort_by(entry_order());
        assert(seq.contains(e));to_multiset_contains(seq,e);to_multiset_contains(sorted,e);
        let i=choose|i:int|0<=i<sorted.len() && sorted[i]==e;
        assert(entry_order()(sorted[0],sorted[i]));
    }
}
pub proof fn theorem_initial_invariant(c:Config)
    ensures inv(c,initial(c)),
{
    reveal(base_inv);
    let s=initial(c);let r=root(c);
    assert(s.queue.contains((0nat,c.src,0nat)));
    assert(covered(s,c.src,0,0));
    assert forall|k:Key|s.dist.contains_key(k) implies hop_ok(c,k.1) && s.dist[k]<=c.cap && (k.0==c.src ==> k==root(c)) && covered(s,k.0,k.1,s.dist[k]) by {assert(k==r);}
    reveal(parent_inv);reveal(closure);
}
pub proof fn theorem_non_skipped_pop_uses_current_distance(c:Config,s:Search,e:Entry)
    requires base_inv(c,s),s.queue.contains(e),!skipped(s,e),
        forall|q:Entry|s.queue.contains(q) ==> e.0<=q.0,
    ensures s.dist[key(e)]==e.0,!s.done.contains_key(key(e)),
{
    reveal(base_inv);
    let k=key(e);assert(covered(s,k.0,k.1,s.dist[k]));
    if s.done.contains_key(k){assert(s.seen[k.0]<=k.1);}
    if exists|j:Key|s.done.contains_key(j) && j.0==k.0 && j.1<=k.1 && s.done[j]<=s.dist[k] {
        let j=choose|j:Key|s.done.contains_key(j) && j.0==k.0 && j.1<=k.1 && s.done[j]<=s.dist[k];
        assert(s.seen[k.0]<=j.1);assert(false);
    }
    let q=choose|q:Entry|s.queue.contains(q) && q.1==k.0 && q.2<=k.1 && q.0<=s.dist[k];
    assert(e.0<=q.0);
}
pub open spec fn refines_cover(s:Search,t:Search)->bool {
    (forall|e:Entry|s.queue.contains(e) ==> covered(t,e.1,e.2,e.0))
    && (forall|k:Key|#[trigger] s.done.contains_key(k) ==> t.done.contains_key(k) && t.done[k]==s.done[k])
}
pub proof fn lemma_cover_weaken(s:Search,v:int,h:nat,cost:nat,larger_h:nat,larger_cost:nat)
    requires covered(s,v,h,cost),h<=larger_h,cost<=larger_cost,
    ensures covered(s,v,larger_h,larger_cost),
{}
pub proof fn lemma_cover_monotone(s:Search,t:Search,v:int,h:nat,cost:nat)
    requires refines_cover(s,t),covered(s,v,h,cost),
    ensures covered(t,v,h,cost),
{
    if exists|e:Entry|s.queue.contains(e) && e.1==v && e.2<=h && e.0<=cost {
        let e=choose|e:Entry|s.queue.contains(e) && e.1==v && e.2<=h && e.0<=cost;
        lemma_cover_weaken(t,v,e.2,e.0,h,cost);
    } else {let k=choose|k:Key|s.done.contains_key(k) && k.0==v && k.1<=h && s.done[k]<=cost;
        assert(t.done.contains_key(k));}
}
pub proof fn lemma_pop_skip_refines(c:Config,s:Search,e:Entry)
    requires base_inv(c,s),s.queue.contains(e),skipped(s,e),
    ensures refines_cover(s,pop_only(s,e)),
{
    reveal(base_inv);
    let t=pop_only(s,e);let k=(e.1,s.seen[e.1]);
    assert(s.done.contains_key(k));assert(s.done[k]<=e.0);
    assert(t.done.contains_key(k));assert(k.1<=e.2);
    assert(exists|j:Key|t.done.contains_key(j) && j.0==e.1 && j.1<=e.2 && t.done[j]<=e.0);
    assert(covered(t,e.1,e.2,e.0));
    assert forall|q:Entry|s.queue.contains(q) implies covered(t,q.1,q.2,q.0) by {
        if q!=e{assert(t.queue.contains(q));}
    }
}
pub proof fn lemma_accept_refines(c:Config,s:Search,e:Entry)
    requires base_inv(c,s),s.queue.contains(e),!skipped(s,e),
        forall|q:Entry|s.queue.contains(q) ==> e.0<=q.0,
    ensures refines_cover(s,accept(s,e)),
{
    theorem_non_skipped_pop_uses_current_distance(c,s,e);
    let t=accept(s,e);assert(!s.done.contains_key(key(e)));assert(t.done.contains_key(key(e)));
    assert(covered(t,e.1,e.2,e.0));
    assert forall|q:Entry|s.queue.contains(q) implies covered(t,q.1,q.2,q.0) by {if q!=e{assert(t.queue.contains(q));}}
}
pub proof fn theorem_skip_preserves_base(c:Config,s:Search,e:Entry)
    requires base_inv(c,s),s.queue.contains(e),skipped(s,e),
    ensures base_inv(c,pop_only(s,e)),
{
    reveal(base_inv);
    lemma_pop_skip_refines(c,s,e);let t=pop_only(s,e);
    assert forall|k:Key|s.dist.contains_key(k) implies covered(t,k.0,k.1,s.dist[k]) by {lemma_cover_monotone(s,t,k.0,k.1,s.dist[k]);}
}
pub proof fn theorem_accept_preserves_base(c:Config,s:Search,e:Entry)
    requires base_inv(c,s),s.queue.contains(e),!skipped(s,e),
        forall|q:Entry|s.queue.contains(q) ==> e.0<=q.0,
    ensures base_inv(c,accept(s,e)),
{
    reveal(base_inv);
    theorem_non_skipped_pop_uses_current_distance(c,s,e);lemma_accept_refines(c,s,e);let t=accept(s,e);let k=key(e);
    assert forall|j:Key|s.dist.contains_key(j) implies covered(t,j.0,j.1,s.dist[j]) by {lemma_cover_monotone(s,t,j.0,j.1,s.dist[j]);}
    assert forall|j:Key|t.done.contains_key(j) implies t.dist.contains_key(j) && t.dist[j]==t.done[j] && t.seen.contains_key(j.0) && t.seen[j.0]<=j.1 by {
        if j!=k && j.0==e.1 {assert(s.seen.contains_key(e.1));assert(e.2<s.seen[e.1]);}
    }
    assert forall|v:int|t.seen.contains_key(v) implies t.done.contains_key((v,t.seen[v])) by {
        if v!=e.1 {assert(s.seen.contains_key(v));assert((v,t.seen[v])!=k);}
    }
    if s.done.len()==0 && k!=root(c){reveal(parent_inv);assert(s.dist.contains_key(k));assert(s.parent.contains_key(k));assert(s.done.contains_key(s.parent[k].0));assert(false);}
    assert(parent_inv(c,t.dist,t.done,t.parent)) by {
        reveal(parent_inv);
    assert forall|j:Key|s.dist.contains_key(j) && j!=root(c) implies {
        t.parent.contains_key(j) && t.done.contains_key(t.parent[j].0)
        && selected(c,t.parent[j].1) && t.parent[j].1.2==t.parent[j].0.0 && t.parent[j].1.4==j.0
        && next_hop(c,t.parent[j].0.1)==j.1
        && t.dist[j]==t.done[t.parent[j].0]+weight(c,t.parent[j].1)
    } by {assert(s.done.contains_key(s.parent[j].0));assert(s.parent[j].0!=k);}
    }
}

pub open spec fn done_upper(s:Search,cost:nat)->bool {forall|k:Key|s.done.contains_key(k) ==> s.done[k]<=cost}
pub proof fn lemma_accept_bounds_done(c:Config,s:Search,e:Entry)
    requires base_inv(c,s),s.queue.contains(e),!skipped(s,e),
        forall|q:Entry|s.queue.contains(q) ==> e.0<=q.0,
    ensures done_upper(accept(s,e),e.0),
{
    reveal(base_inv);}
pub proof fn lemma_relax_refines(c:Config,s:Search,e:Entry,a:Arc)
    ensures refines_cover(s,relax(c,s,e,a)),
{
    let t=relax(c,s,e,a);
    assert forall|q:Entry|s.queue.contains(q) implies covered(t,q.1,q.2,q.0) by {assert(t.queue.contains(q));}
}
pub proof fn theorem_relax_preserves_base(c:Config,s:Search,e:Entry,a:Arc)
    requires base_inv(c,s),s.done.contains_key(key(e)),s.done[key(e)]==e.0,done_upper(s,e.0),
    ensures base_inv(c,relax(c,s,e,a)),done_upper(relax(c,s,e,a),e.0),
{
    let t=relax(c,s,e,a);let h=next_hop(c,e.2);let n=e.0+weight(c,a);let k=(a.4,h);
    if t!=s {assert(t.parent[k]==(key(e),a));}
    reveal(base_inv);
    if t!=s {
        assert(!s.done.contains_key(k)) by {if s.done.contains_key(k){assert(s.seen.contains_key(k.0));assert(s.seen[k.0]<=h);}}
        assert(s.done.len()>0);assert(s.done.contains_key(root(c)));assert(s.seen[c.src]==0);
        assert(k.0!=c.src);
        lemma_relax_refines(c,s,e,a);
        assert(t.queue.contains((n,a.4,h)));assert(covered(t,k.0,k.1,n));
        assert forall|j:Key|t.dist.contains_key(j) implies hop_ok(c,j.1) && t.dist[j]<=c.cap && (j.0==c.src ==> j==root(c)) && covered(t,j.0,j.1,t.dist[j]) by {
            if j!=k{lemma_cover_monotone(s,t,j.0,j.1,s.dist[j]);}
        }
        assert forall|q:Entry|t.queue.contains(q) implies t.dist.contains_key(key(q)) && t.dist[key(q)]<=q.0 && q.0<=c.cap by {
            if q!=(n,a.4,h){assert(s.queue.contains(q));if key(q)==k{assert(s.dist.contains_key(k));assert(n<s.dist[k]);}}
        }
        reveal(parent_inv);
        assert forall|j:Key|t.dist.contains_key(j) && j!=root(c) implies {
            t.parent.contains_key(j) && t.done.contains_key(t.parent[j].0)
            && selected(c,t.parent[j].1) && t.parent[j].1.2==t.parent[j].0.0 && t.parent[j].1.4==j.0
            && next_hop(c,t.parent[j].0.1)==j.1
            && t.dist[j]==t.done[t.parent[j].0]+weight(c,t.parent[j].1)
        } by {
            if j==k{assert(t.parent[j]==(key(e),a));assert(s.dist[key(e)]==e.0);}
            else{assert(s.parent.contains_key(j));assert(s.done.contains_key(s.parent[j].0));assert(s.parent[j].0!=k);}
        }
        assert forall|j:Key|t.done.contains_key(j) implies t.dist.contains_key(j) && t.dist[j]==t.done[j] && t.seen.contains_key(j.0) && t.seen[j.0]<=j.1 by {assert(j!=k);}
        assert forall|j:Key,q:Entry|t.done.contains_key(j) && t.queue.contains(q) implies t.done[j]<=q.0 by {
            if q==(n,a.4,h){assert(s.done[j]<=e.0);}
        }
    }
}
pub proof fn theorem_relax_covers_neighbor(c:Config,s:Search,e:Entry,a:Arc)
    requires base_inv(c,s),s.done.contains_key(key(e)),s.done[key(e)]==e.0,done_upper(s,e.0),
        selected(c,a),a.2==e.1,hop_ok(c,next_hop(c,e.2)),e.0+weight(c,a)<=c.cap,
    ensures covered(relax(c,s,e,a),a.4,next_hop(c,e.2),e.0+weight(c,a)),
{
    reveal(base_inv);
    let h=next_hop(c,e.2);let n=e.0+weight(c,a);let k=(a.4,h);let t=relax(c,s,e,a);
    if s.seen.contains_key(a.4) && s.seen[a.4]<=h {
        let j=(a.4,s.seen[a.4]);assert(s.done.contains_key(j));assert(s.done[j]<=e.0);
        assert(t==s);assert(exists|j:Key|t.done.contains_key(j) && j.0==a.4 && j.1<=h && t.done[j]<=n);
    } else if s.dist.contains_key(k) && s.dist[k]<=n {lemma_cover_weaken(s,a.4,h,s.dist[k],h,n);}
    else{assert(t.queue.contains((n,a.4,h)));}
}

pub proof fn lemma_refines_transitive(s:Search,t:Search,u:Search)
    requires refines_cover(s,t),refines_cover(t,u),
    ensures refines_cover(s,u),
{
    assert forall|k:Key|s.done.contains_key(k) implies u.done.contains_key(k) && u.done[k]==s.done[k] by {assert(t.done.contains_key(k));}
    assert forall|q:Entry|s.queue.contains(q) implies covered(u,q.1,q.2,q.0) by {lemma_cover_monotone(t,u,q.1,q.2,q.0);}
}
pub proof fn lemma_expand_preserves_and_covers(c:Config,s:Search,e:Entry,arcs:Seq<Arc>)
    requires base_inv(c,s),s.done.contains_key(key(e)),s.done[key(e)]==e.0,done_upper(s,e.0),
    ensures base_inv(c,expand(c,s,e,arcs)),done_upper(expand(c,s,e,arcs),e.0),
        refines_cover(s,expand(c,s,e,arcs)),expand(c,s,e,arcs).done==s.done,expand(c,s,e,arcs).seen==s.seen,
        forall|a:Arc|arcs.contains(a) && selected(c,a) && a.2==e.1 && hop_ok(c,next_hop(c,e.2)) && e.0+weight(c,a)<=c.cap
            ==> covered(expand(c,s,e,arcs),a.4,next_hop(c,e.2),e.0+weight(c,a)),
    decreases arcs.len(),
{
    if arcs.len()==0 {
        assert forall|q:Entry|s.queue.contains(q) implies covered(s,q.1,q.2,q.0) by {}
    } else {
        let t=relax(c,s,e,arcs[0]);let u=expand(c,t,e,arcs.drop_first());
        theorem_relax_preserves_base(c,s,e,arcs[0]);lemma_relax_refines(c,s,e,arcs[0]);
        lemma_expand_preserves_and_covers(c,t,e,arcs.drop_first());lemma_refines_transitive(s,t,u);
        assert forall|a:Arc|arcs.contains(a) && selected(c,a) && a.2==e.1 && hop_ok(c,next_hop(c,e.2)) && e.0+weight(c,a)<=c.cap
            implies covered(u,a.4,next_hop(c,e.2),e.0+weight(c,a)) by {
            if a==arcs[0]{theorem_relax_covers_neighbor(c,s,e,a);lemma_cover_monotone(t,u,a.4,next_hop(c,e.2),e.0+weight(c,a));}
            else {let i=choose|i:int|0<=i<arcs.len() && arcs[i]==a;assert(i>0);assert(arcs.drop_first()[i-1]==a);assert(arcs.drop_first().contains(a));}
        }
    }
}
pub proof fn lemma_closed_for_monotone(c:Config,s:Search,t:Search,closed:Map<Key,nat>)
    requires refines_cover(s,t),closed_for(c,s,closed),
    ensures closed_for(c,t,closed),
{
    assert forall|k:Key,a:Arc|closed.contains_key(k) && selected(c,a) && a.2==k.0
        && hop_ok(c,next_hop(c,k.1)) && closed[k]+weight(c,a)<=c.cap
        implies covered(t,a.4,next_hop(c,k.1),closed[k]+weight(c,a)) by {
        lemma_cover_monotone(s,t,a.4,next_hop(c,k.1),closed[k]+weight(c,a));
    }
}
pub proof fn theorem_skip_preserves_invariant(c:Config,s:Search,e:Entry)
    requires inv(c,s),s.queue.contains(e),skipped(s,e),
    ensures inv(c,pop_only(s,e)),
{
    theorem_skip_preserves_base(c,s,e);lemma_pop_skip_refines(c,s,e);reveal(closure);
    lemma_closed_for_monotone(c,s,pop_only(s,e),s.done);
}
pub proof fn theorem_expand_preserves_invariant(c:Config,s:Search,e:Entry)
    requires graph_frame(c),inv(c,s),s.queue.contains(e),!skipped(s,e),
        forall|q:Entry|s.queue.contains(q) ==> e.0<=q.0,
    ensures ({let t=accept(s,e);let u=if e.0>=c.cap || (c.bound>0 && e.2>=c.bound){t}else{expand(c,t,e,neighbors(c,e.1))};inv(c,u) && u.done==t.done}),
{
    theorem_accept_preserves_base(c,s,e);lemma_accept_refines(c,s,e);lemma_accept_bounds_done(c,s,e);
    let t=accept(s,e);let stopped=e.0>=c.cap || (c.bound>0 && e.2>=c.bound);
    let u=if stopped{t}else{expand(c,t,e,neighbors(c,e.1))};
    if !stopped{lemma_expand_preserves_and_covers(c,t,e,neighbors(c,e.1));lemma_refines_transitive(s,t,u);}
    reveal(closure);lemma_closed_for_monotone(c,s,u,s.done);
    assert forall|k:Key,a:Arc|u.done.contains_key(k) && selected(c,a) && a.2==k.0
        && hop_ok(c,next_hop(c,k.1)) && u.done[k]+weight(c,a)<=c.cap
        implies covered(u,a.4,next_hop(c,k.1),u.done[k]+weight(c,a)) by {
        if k==key(e) {
            assert(u.done[k]==e.0);
            if stopped{assert(weight(c,a)>0);assert(false);}
            else {
                assert(c.arcs.contains(a));let i=choose|i:int|0<=i<c.arcs.len() && c.arcs[i]==a;
                c.arcs.lemma_filter_contains(|a:Arc|selected(c,a) && a.2==e.1,i);
                assert(neighbors(c,e.1).contains(a));
            }
        } else {assert(s.done.contains_key(k));}
    }
}
pub open spec fn no_target(c:Config,s:Search)->bool {forall|k:Key|s.done.contains_key(k) ==> k.0!=c.dst}
pub proof fn theorem_actual_continue_preserves(c:Config,s:Search,t:Search)
    requires graph_frame(c),inv(c,s),no_target(c,s),step(c,s)==Event::Continue(t),
    ensures inv(c,t),no_target(c,t),
{
    assert(s.queue.len()>0);let e=minimum(s.queue);lemma_minimum(s.queue);
    if skipped(s,e){theorem_skip_preserves_invariant(c,s,e);}
    else{assert(e.1!=c.dst);theorem_expand_preserves_invariant(c,s,e);}
    assert forall|k:Key|t.done.contains_key(k) implies k.0!=c.dst by {
        if !skipped(s,e) && k==key(e){assert(e.1!=c.dst);}else{assert(s.done.contains_key(k));}
    }
}

pub open spec fn walk(c:Config,from:int,to:int,p:Seq<Arc>)->bool
    decreases p.len(),
{if p.len()==0{from==to}else{selected(c,p[0]) && p[0].2==from && walk(c,p[0].4,to,p.drop_first())}}
pub open spec fn cost(c:Config,p:Seq<Arc>)->nat
    decreases p.len(),
{if p.len()==0{0}else{weight(c,p[0])+cost(c,p.drop_first())}}
pub open spec fn feasible(c:Config,p:Seq<Arc>)->bool {
    walk(c,c.src,c.dst,p) && (c.bound==0 || p.len()<=c.bound) && cost(c,p)<=c.cap
}
pub proof fn lemma_path_frontier(c:Config,s:Search,from:int,h:nat,before:nat,p:Seq<Arc>)
    requires inv(c,s),no_target(c,s),walk(c,from,c.dst,p),covered(s,from,h,before),hop_ok(c,h),
        c.bound==0 || h+p.len()<=c.bound,before+cost(c,p)<=c.cap,
    ensures exists|q:Entry|s.queue.contains(q) && q.0<=before+cost(c,p),
    decreases p.len(),
{
    if exists|q:Entry|s.queue.contains(q) && q.1==from && q.2<=h && q.0<=before {
        let q=choose|q:Entry|s.queue.contains(q) && q.1==from && q.2<=h && q.0<=before;
        assert(q.0<=before+cost(c,p));
    } else {
        let k=choose|k:Key|s.done.contains_key(k) && k.0==from && k.1<=h && s.done[k]<=before;
        if p.len()==0{assert(from==c.dst);assert(false);}
        else {
            let a=p[0];let next=next_hop(c,k.1);let prefix=s.done[k]+weight(c,a);
            reveal(base_inv);reveal(closure);
            assert(hop_ok(c,k.1));assert(hop_ok(c,next));assert(prefix<=c.cap);
            assert(covered(s,a.4,next,prefix));
            lemma_path_frontier(c,s,a.4,next,prefix,p.drop_first());
            let q=choose|q:Entry|s.queue.contains(q) && q.0<=prefix+cost(c,p.drop_first());
            assert(q.0<=before+cost(c,p));
        }
    }
}
pub proof fn theorem_ordered_target_pop_is_minimum(c:Config,s:Search,t:Search,e:Entry,p:Seq<Arc>)
    requires graph_frame(c),inv(c,s),no_target(c,s),step(c,s)==(Event::Returned{state:t,entry:e}),feasible(c,p),
    ensures e.1==c.dst,e.0<=cost(c,p),e.0<=c.cap,base_inv(c,t),t.dist[key(e)]==e.0,
{
    assert(s.queue.len()>0);assert(e==minimum(s.queue));lemma_minimum(s.queue);
    assert(!skipped(s,e));theorem_non_skipped_pop_uses_current_distance(c,s,e);theorem_accept_preserves_base(c,s,e);
    reveal(base_inv);assert(covered(s,c.src,0,0));
    lemma_path_frontier(c,s,c.src,0,0,p);
    let q=choose|q:Entry|s.queue.contains(q) && q.0<=cost(c,p);assert(e.0<=q.0);
}
pub proof fn theorem_empty_queue_is_no_feasible_path(c:Config,s:Search,p:Seq<Arc>)
    requires inv(c,s),no_target(c,s),s.queue.len()==0,
    ensures !feasible(c,p),
{
    if feasible(c,p){reveal(base_inv);lemma_path_frontier(c,s,c.src,0,0,p);
        let q=choose|q:Entry|s.queue.contains(q) && q.0<=cost(c,p);assert(false);}
}
pub open spec fn backtrack(s:Search,src:int,k:Key,fuel:nat)->Seq<Arc>
    decreases fuel,
{
    if fuel==0 || k.0==src || !s.parent.contains_key(k){seq![]}
    else{backtrack(s,src,s.parent[k].0,(fuel-1) as nat).push(s.parent[k].1)}
}
pub proof fn lemma_walk_push(c:Config,src:int,via:int,to:int,p:Seq<Arc>,a:Arc)
    requires walk(c,src,via,p),selected(c,a),a.2==via,a.4==to,
    ensures walk(c,src,to,p.push(a)),cost(c,p.push(a))==cost(c,p)+weight(c,a),
    decreases p.len(),
{
    if p.len()>0{
        lemma_walk_push(c,p[0].4,via,to,p.drop_first(),a);
        assert(p.push(a).drop_first() =~= p.drop_first().push(a));
    } else{assert(p =~= Seq::<Arc>::empty());assert(p.push(a) =~= seq![a]);assert(p.push(a).drop_first() =~= Seq::<Arc>::empty());}
    reveal_with_fuel(walk,2);reveal_with_fuel(cost,2);
}
pub proof fn theorem_backtrack_derives_path_and_cost(c:Config,s:Search,k:Key,fuel:nat)
    requires base_inv(c,s),s.dist.contains_key(k),fuel>s.dist[k],
    ensures walk(c,c.src,k.0,backtrack(s,c.src,k,fuel)),cost(c,backtrack(s,c.src,k,fuel))==s.dist[k],
        (c.bound>0 ==> backtrack(s,c.src,k,fuel).len()==k.1),
    decreases fuel,
{
    reveal(base_inv);reveal(parent_inv);
    if k.0==c.src{assert(k==root(c));}
    else {
        let prev=s.parent[k].0;let a=s.parent[k].1;
        assert(weight(c,a)>0);assert(s.dist.contains_key(prev));assert(s.dist[prev]==s.done[prev]);
        assert(s.dist[prev]<s.dist[k]);
        theorem_backtrack_derives_path_and_cost(c,s,prev,(fuel-1) as nat);
        lemma_walk_push(c,c.src,prev.0,k.0,backtrack(s,c.src,prev,(fuel-1) as nat),a);
    }
}
pub proof fn theorem_actual_returned_path_is_optimal(c:Config,s:Search,t:Search,e:Entry,p:Seq<Arc>)
    requires graph_frame(c),inv(c,s),no_target(c,s),step(c,s)==(Event::Returned{state:t,entry:e}),
    ensures feasible(c,backtrack(t,c.src,key(e),e.0+1)),
        cost(c,backtrack(t,c.src,key(e),e.0+1))==e.0,
        (feasible(c,p) ==> cost(c,backtrack(t,c.src,key(e),e.0+1))<=cost(c,p)),
{
    assert(s.queue.len()>0);assert(e==minimum(s.queue));lemma_minimum(s.queue);
    assert(!skipped(s,e));theorem_non_skipped_pop_uses_current_distance(c,s,e);theorem_accept_preserves_base(c,s,e);
    assert(t==accept(s,e));assert(base_inv(c,t));reveal(base_inv);
    theorem_backtrack_derives_path_and_cost(c,t,key(e),e.0+1);
    assert(hop_ok(c,e.2));assert(e.0<=c.cap);
    if feasible(c,p){theorem_ordered_target_pop_is_minimum(c,s,t,e,p);}
}

// Ghost history records popped queue entries. It changes no search decision.
pub open spec fn nodes(c:Config)->Seq<int> {c.arcs.map_values(|a:Arc|a.4).push(c.src)}
pub open spec fn hop_max(c:Config)->nat {c.bound}
pub open spec fn entries_at_cost(node:int,n:nat,hmax:nat)->Set<Entry> {
    Set::<nat>::range(0,hmax+1).map(|h:nat|(n,node,h))
}
pub open spec fn entries_for_node(node:int,n:nat,hmax:nat)->Set<Entry>
    decreases n,
{if n==0{entries_at_cost(node,0,hmax)}else{entries_for_node(node,(n-1) as nat,hmax).union(entries_at_cost(node,n,hmax))}}
pub open spec fn finite_entries(ns:Seq<int>,cap:nat,hmax:nat)->Set<Entry>
    decreases ns.len(),
{if ns.len()==0{Set::empty()}else{entries_for_node(ns[0],cap,hmax).union(finite_entries(ns.drop_first(),cap,hmax))}}
pub open spec fn universe(c:Config)->Set<Entry> {finite_entries(nodes(c),c.cap,hop_max(c))}
pub open spec fn rank(c:Config,s:Search)->nat {universe(c).difference(s.removed).len()}
#[verifier::opaque]
pub open spec fn termination_inv(c:Config,s:Search)->bool {
    &&& (forall|k:Key|s.dist.contains_key(k) ==> nodes(c).contains(k.0))
    &&& (forall|e:Entry|s.removed.contains(e) ==> s.dist.contains_key(key(e)) && s.dist[key(e)]<=e.0
        && e.0<=c.cap && hop_ok(c,e.2) && nodes(c).contains(e.1))
    &&& (forall|e:Entry|s.queue.contains(e) ==> !s.removed.contains(e))
}
pub proof fn lemma_entries_at_cost(node:int,n:nat,hmax:nat,h:nat)
    requires h<=hmax,
    ensures entries_at_cost(node,n,hmax).contains((n,node,h)),
{
    vstd::set_lib::range_set_properties::<nat>(0,hmax+1);
    let hs=Set::<nat>::range(0,hmax+1);assert(hs.contains(h));
    hs.lemma_map_contains(|h:nat|(n,node,h),(n,node,h));
}
pub proof fn lemma_entries_for_node(node:int,n:nat,hmax:nat,e:Entry)
    requires e.1==node,e.0<=n,e.2<=hmax,
    ensures entries_for_node(node,n,hmax).contains(e),
    decreases n,
{
    if e.0==n{lemma_entries_at_cost(node,n,hmax,e.2);}
    else{assert(n>0);lemma_entries_for_node(node,(n-1) as nat,hmax,e);}
}
pub proof fn lemma_finite_entries(ns:Seq<int>,cap:nat,hmax:nat,e:Entry)
    requires ns.contains(e.1),e.0<=cap,e.2<=hmax,
    ensures finite_entries(ns,cap,hmax).contains(e),
    decreases ns.len(),
{
    assert(ns.len()>0);
    if ns[0]==e.1{lemma_entries_for_node(e.1,cap,hmax,e);}
    else{let i=choose|i:int|0<=i<ns.len() && ns[i]==e.1;assert(i>0);assert(ns.drop_first()[i-1]==e.1);assert(ns.drop_first().contains(e.1));lemma_finite_entries(ns.drop_first(),cap,hmax,e);}
}
pub proof fn theorem_initial_termination_inv(c:Config)
    ensures termination_inv(c,initial(c)),
{reveal(termination_inv);assert(nodes(c).len()==c.arcs.len()+1);assert(nodes(c)[c.arcs.len() as int]==c.src);assert(nodes(c).contains(c.src));}
pub proof fn lemma_neighbor_in_nodes(c:Config,a:Arc)
    requires graph_frame(c),selected(c,a),
    ensures nodes(c).contains(a.4),
{
    assert(c.arcs.contains(a));let i=choose|i:int|0<=i<c.arcs.len() && c.arcs[i]==a;
    assert(nodes(c).len()==c.arcs.len()+1);assert(nodes(c)[i]==a.4);assert(nodes(c).contains(a.4));
}
pub proof fn theorem_pop_preserves_termination(c:Config,s:Search,e:Entry)
    requires base_inv(c,s),termination_inv(c,s),s.queue.contains(e),
    ensures termination_inv(c,pop_only(s,e)),termination_inv(c,accept(s,e)),
        pop_only(s,e).removed==s.removed.insert(e),!s.removed.contains(e),
{
    reveal(base_inv);reveal(termination_inv);
    assert(hop_ok(c,e.2));assert(nodes(c).contains(e.1));
}
pub proof fn theorem_relax_preserves_termination(c:Config,s:Search,e:Entry,a:Arc)
    requires graph_frame(c),termination_inv(c,s),
    ensures termination_inv(c,relax(c,s,e,a)),relax(c,s,e,a).removed==s.removed,
{
    reveal(termination_inv);let t=relax(c,s,e,a);let k=(a.4,next_hop(c,e.2));let n=e.0+weight(c,a);
    if t!=s {
        lemma_neighbor_in_nodes(c,a);
        assert(!s.removed.contains((n,a.4,k.1))) by {if s.removed.contains((n,a.4,k.1)){assert(s.dist.contains_key(k));assert(s.dist[k]<=n);}}
        assert forall|j:Key|t.dist.contains_key(j) implies nodes(c).contains(j.0) by {if j!=k{assert(s.dist.contains_key(j));}}
        assert forall|q:Entry|s.removed.contains(q) implies t.dist.contains_key(key(q)) && t.dist[key(q)]<=q.0
            && q.0<=c.cap && hop_ok(c,q.2) && nodes(c).contains(q.1) by {
            if key(q)==k{assert(s.dist.contains_key(k));assert(n<s.dist[k]);}
        }
        assert forall|q:Entry|t.queue.contains(q) implies !t.removed.contains(q) by {if q!=(n,a.4,k.1){assert(s.queue.contains(q));}}
    }
}
pub proof fn lemma_expand_preserves_termination(c:Config,s:Search,e:Entry,arcs:Seq<Arc>)
    requires graph_frame(c),base_inv(c,s),termination_inv(c,s),s.done.contains_key(key(e)),s.done[key(e)]==e.0,done_upper(s,e.0),
    ensures termination_inv(c,expand(c,s,e,arcs)),expand(c,s,e,arcs).removed==s.removed,
    decreases arcs.len(),
{
    if arcs.len()>0 {
        let t=relax(c,s,e,arcs[0]);theorem_relax_preserves_base(c,s,e,arcs[0]);theorem_relax_preserves_termination(c,s,e,arcs[0]);
        lemma_expand_preserves_termination(c,t,e,arcs.drop_first());
    }
}
pub proof fn theorem_continue_strictly_decreases(c:Config,s:Search,t:Search)
    requires graph_frame(c),inv(c,s),termination_inv(c,s),step(c,s)==Event::Continue(t),
    ensures termination_inv(c,t),rank(c,t)<rank(c,s),
{
    assert(s.queue.len()>0);let e=minimum(s.queue);lemma_minimum(s.queue);
    theorem_pop_preserves_termination(c,s,e);
    if !skipped(s,e){
        theorem_accept_preserves_base(c,s,e);lemma_accept_bounds_done(c,s,e);
        if e.0<c.cap && (c.bound==0 || e.2<c.bound){lemma_expand_preserves_termination(c,accept(s,e),e,neighbors(c,e.1));}
    }
    assert(t.removed==s.removed.insert(e));
    reveal(base_inv);reveal(termination_inv);
    assert(s.dist.contains_key(key(e)));assert(nodes(c).contains(e.1));assert(hop_ok(c,e.2));
    lemma_finite_entries(nodes(c),c.cap,hop_max(c),e);
    universe(c).lemma_set_insert_diff_decreases(s.removed,e);
}

// The finite trace is derived from the actual deterministic Continue transition.
// It is not an assumed terminating run or an added runtime search budget.
pub open spec fn terminal(c:Config,s:Search)->bool {
    match step(c,s){Event::Continue(_)=>false,_=>true}
}
pub open spec fn terminal_trace(c:Config,start:Search,tr:Seq<Search>)->bool {
    tr.len()>0 && tr[0]==start && terminal(c,tr.last())
    && forall|i:int|0<=i<tr.len()-1 ==> step(c,tr[i])==Event::Continue(tr[i+1])
}
pub proof fn theorem_actual_search_terminates(c:Config,s:Search)
    requires graph_frame(c),inv(c,s),no_target(c,s),termination_inv(c,s),
    ensures exists|tr:Seq<Search>|terminal_trace(c,s,tr) && tr.len()<=rank(c,s)+1
        && inv(c,tr.last()) && no_target(c,tr.last()),
    decreases rank(c,s),
{
    match step(c,s) {
        Event::Continue(t)=>{
            theorem_actual_continue_preserves(c,s,t);
            theorem_continue_strictly_decreases(c,s,t);
            theorem_actual_search_terminates(c,t);
            let tail=choose|tr:Seq<Search>|terminal_trace(c,t,tr) && tr.len()<=rank(c,t)+1
                && inv(c,tr.last()) && no_target(c,tr.last());
            let tr=seq![s]+tail;
            assert(tr.last()==tail.last());
            assert forall|i:int|0<=i<tr.len()-1 implies step(c,tr[i])==Event::Continue(tr[i+1]) by {
                if i==0{assert(tr[i+1]==tail[0]);}
                else{assert(tr[i]==tail[i-1]);assert(tr[i+1]==tail[i]);}
            }
            assert(terminal_trace(c,s,tr));
        },
        _=>{let tr=seq![s];assert(terminal_trace(c,s,tr));}
    }
}
pub open spec fn terminal_correct(c:Config,s:Search)->bool {
    match step(c,s) {
        Event::Returned{state:t,entry:e}=>{
            let path=backtrack(t,c.src,key(e),e.0+1);
            feasible(c,path) && cost(c,path)==e.0
            && forall|p:Seq<Arc>|feasible(c,p) ==> e.0<=cost(c,p)
        },
        Event::Empty(_)=>forall|p:Seq<Arc>|!feasible(c,p),
        Event::Continue(_)=>false,
    }
}
pub proof fn theorem_terminal_correct(c:Config,s:Search)
    requires graph_frame(c),inv(c,s),no_target(c,s),terminal(c,s),
    ensures terminal_correct(c,s),
{
    match step(c,s) {
        Event::Returned{state:t,entry:e}=>{
            theorem_actual_returned_path_is_optimal(c,s,t,e,seq![]);
            assert forall|p:Seq<Arc>|feasible(c,p) implies e.0<=cost(c,p) by {
                theorem_actual_returned_path_is_optimal(c,s,t,e,p);
            }
        },
        Event::Empty(_)=>{
            assert(s.queue.len()==0);
            assert forall|p:Seq<Arc>|!feasible(c,p) by {theorem_empty_queue_is_no_feasible_path(c,s,p);}
        },
        _=>{},
    }
}
pub proof fn theorem_complete_terminating_search(c:Config)
    requires graph_frame(c),c.src!=c.dst,
    ensures exists|tr:Seq<Search>|terminal_trace(c,initial(c),tr) && tr.len()<=rank(c,initial(c))+1
        && terminal_correct(c,tr.last()),
{
    theorem_initial_invariant(c);theorem_initial_termination_inv(c);
    assert(no_target(c,initial(c)));
    theorem_actual_search_terminates(c,initial(c));
    let tr=choose|tr:Seq<Search>|terminal_trace(c,initial(c),tr) && tr.len()<=rank(c,initial(c))+1
        && inv(c,tr.last()) && no_target(c,tr.last());
    theorem_terminal_correct(c,tr.last());
}
pub proof fn theorem_admitted_self_is_zero(c:Config)
    requires c.src==c.dst,
    ensures walk(c,c.src,c.dst,seq![]),cost(c,seq![])==0,feasible(c,seq![]),
        forall|p:Seq<Arc>|feasible(c,p) ==> cost(c,seq![])<=cost(c,p),
{}

}
