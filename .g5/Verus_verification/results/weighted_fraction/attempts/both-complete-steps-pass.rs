// Source-facing exact rational costs coupled to the unchanged integer searches.
// Exact arithmetic/stable scalar adjacency; native Double/JSON/collation separate.
use vstd::prelude::*;
use vstd::seq_lib::*;
#[path="../weighted_cost/weighted_cost.rs"] pub mod kernel;
use kernel::json;
verus! {
pub type Arc=json::Arc;
pub type Key=json::Key;
pub struct Scalar {pub num:int,pub den:nat}
pub struct Config {pub arcs:Seq<Arc>,pub raw:Map<Arc,Option<Scalar>>,pub graph:int,pub src:int,pub dst:int,
    pub direction:json::Dir,pub predicates:Set<int>,pub cap:Scalar,pub bound:nat}
pub open spec fn ratio(x:Scalar)->real {(x.num as real)/(x.den as real)}
pub open spec fn weight(c:Config,a:Arc)->real {
    if c.raw[a].is_some() && ratio(c.raw[a].unwrap())>0real{ratio(c.raw[a].unwrap())}else{1real}
}
pub open spec fn selected(c:Config,a:Arc)->bool {
    c.raw.contains_key(a) && a.1==c.graph && (match c.direction{json::Dir::Out=>a.0==0,json::Dir::In=>a.0==1,json::Dir::Both=>a.0<=1})
    && (c.predicates.len()==0 || c.predicates.contains(a.3))
}
pub open spec fn frame(c:Config)->bool {
    c.arcs.no_duplicates() && (forall|a:Arc|c.raw.contains_key(a)<==>c.arcs.contains(a))
    && c.cap.den>0 && c.cap.num>=0
    && forall|a:Arc|c.raw.contains_key(a) && c.raw[a].is_some() ==> c.raw[a].unwrap().den>0
}
pub open spec fn denominations(c:Config)->Seq<nat> {
    c.arcs.map_values(|a:Arc|if c.raw[a].is_some(){c.raw[a].unwrap().den}else{1nat}).push(c.cap.den)
}
pub open spec fn product(ds:Seq<nat>)->nat decreases ds.len() {
    if ds.len()==0{1}else{ds[0]*product(ds.drop_first())}
}
pub open spec fn omitted(ds:Seq<nat>,i:nat)->nat decreases ds.len() {
    if ds.len()==0{1}else if i==0{product(ds.drop_first())}else{ds[0]*omitted(ds.drop_first(),(i-1) as nat)}
}
pub open spec fn denominator(c:Config)->nat {product(denominations(c))}
pub open spec fn index(c:Config,a:Arc)->nat {
    choose|i:nat|i<c.arcs.len() && c.arcs[i as int]==a
}
pub open spec fn factor(c:Config,a:Arc)->nat {omitted(denominations(c),index(c,a))}
pub open spec fn numerator(c:Config,a:Arc)->nat {
    if c.raw[a].is_some() && c.raw[a].unwrap().num>0{(c.raw[a].unwrap().num as nat)*factor(c,a)}else{denominator(c)}
}
pub open spec fn cap_numerator(c:Config)->nat {(c.cap.num as nat)*omitted(denominations(c),c.arcs.len())}
pub open spec fn encoded(c:Config)->json::Config {
    json::Config{arcs:c.arcs,raw:Map::new(c.raw.dom(),|a:Arc|Some(numerator(c,a) as int)),graph:c.graph,src:c.src,dst:c.dst,
        direction:c.direction,predicates:c.predicates,cap:cap_numerator(c),bound:c.bound}
}
pub open spec fn decode(c:Config,n:nat)->real {(n as real)/(denominator(c) as real)}

pub proof fn lemma_product(ds:Seq<nat>,i:nat)
    requires forall|j:int|0<=j<ds.len() ==> ds[j]>0,
    ensures product(ds)>0,i<ds.len() ==> omitted(ds,i)>0 && product(ds)==ds[i as int]*omitted(ds,i),
    decreases ds.len(),
{
    if ds.len()>0{
        assert forall|j:int|0<=j<ds.drop_first().len() implies ds.drop_first()[j]>0 by {assert(ds.drop_first()[j]==ds[j+1]);}
        lemma_product(ds.drop_first(),if i==0{0}else{(i-1) as nat});
        assert(ds[0]*product(ds.drop_first())>0) by(nonlinear_arith) requires ds[0]>0,product(ds.drop_first())>0;
        if 0<i<ds.len(){
            let d=ds[0];let v=ds[i as int];let f=omitted(ds.drop_first(),(i-1) as nat);
            assert(product(ds.drop_first())==v*f);
            assert(d*(v*f)==v*(d*f)) by(nonlinear_arith);
            assert(d*f>0) by(nonlinear_arith) requires d>0,f>0;
        }
    }
}
pub proof fn theorem_common_denominator_derived(c:Config)
    requires frame(c),
    ensures denominator(c)>0,
        forall|j:int|0<=j<denominations(c).len() ==> denominations(c)[j]>0,
        denominator(c)==c.cap.den*omitted(denominations(c),c.arcs.len()),
        forall|a:Arc|c.raw.contains_key(a) ==> factor(c,a)>0 &&
            denominator(c)==(if c.raw[a].is_some(){c.raw[a].unwrap().den}else{1nat})*factor(c,a),
{
    let ds=denominations(c);
    assert forall|j:int|0<=j<ds.len() implies ds[j]>0 by {
        if j<c.arcs.len(){assert(c.arcs.contains(c.arcs[j]));assert(c.raw.contains_key(c.arcs[j]));}
    }
    lemma_product(ds,c.arcs.len());
    assert forall|a:Arc|c.raw.contains_key(a) implies factor(c,a)>0 && denominator(c)==(if c.raw[a].is_some(){c.raw[a].unwrap().den}else{1nat})*factor(c,a) by {
        assert(c.arcs.contains(a));let j=choose|j:int|0<=j<c.arcs.len() && c.arcs[j]==a;
        assert(exists|i:nat|i<c.arcs.len() && c.arcs[i as int]==a);
        let i=index(c,a);assert(i<c.arcs.len());assert(c.arcs[i as int]==a);
        lemma_product(ds,i);assert(ds[i as int]==(if c.raw[a].is_some(){c.raw[a].unwrap().den}else{1nat}));
    }
}
pub proof fn lemma_ratio(num:int,den:nat,f:nat)
    requires den>0,f>0,
    ensures ((num as real)*(f as real))/((den as real)*(f as real))==(num as real)/(den as real),
        ((num as real)/(den as real)>0real <==> num>0),
{
    assert(((num as real)*(f as real))/((den as real)*(f as real))==(num as real)/(den as real)) by(nonlinear_arith)
        requires den as real>0real,f as real>0real;
    assert((num as real)/(den as real)>0real <==> num>0) by(nonlinear_arith) requires den as real>0real;
}
pub proof fn lemma_nat_real_mul(a:nat,b:nat)
    ensures ((a*b) as real)==(a as real)*(b as real),
    decreases b,
{
    if b>0{
        let t=(b-1) as nat;assert(b==t+1);
        lemma_nat_real_mul(a,t);
        assert(a*b==a*t+a) by(nonlinear_arith) requires b==t+1;
        assert(((a*b) as real)==((a*((b-1) as nat)) as real)+(a as real));
        assert(((b-1) as nat) as real==(b as real)-1real);
        assert((a as real)*((b as real)-1real)+(a as real)==(a as real)*(b as real)) by(nonlinear_arith);
    }else{
        assert(a*b==0) by(nonlinear_arith) requires b==0;
        assert((a as real)*(b as real)==0real) by(nonlinear_arith) requires b==0;
    }
}
pub proof fn theorem_scalar_and_cap_decode(c:Config,a:Arc)
    requires frame(c),c.raw.contains_key(a),
    ensures numerator(c,a)>0,decode(c,numerator(c,a))==weight(c,a),
        json::weight(encoded(c),a)==numerator(c,a),decode(c,cap_numerator(c))==ratio(c.cap),
{
    theorem_common_denominator_derived(c);let d=denominator(c);
    if c.raw[a].is_some(){let x=c.raw[a].unwrap();let f=factor(c,a);lemma_ratio(x.num,x.den,f);
        if x.num>0{
            assert((x.num as nat)*f>0) by(nonlinear_arith) requires x.num>0,f>0;
            lemma_nat_real_mul(x.den,f);lemma_nat_real_mul(x.num as nat,f);
            assert((d as real)==(x.den as real)*(f as real));
            assert((numerator(c,a) as real)==(x.num as real)*(f as real));
        }else{assert((d as real)/(d as real)==1real) by(nonlinear_arith) requires d>0;}
    }else{assert((d as real)/(d as real)==1real) by(nonlinear_arith) requires d>0;}
    let f=omitted(denominations(c),c.arcs.len());lemma_product(denominations(c),c.arcs.len());lemma_ratio(c.cap.num,c.cap.den,f);
    lemma_nat_real_mul(c.cap.num as nat,f);lemma_nat_real_mul(c.cap.den,f);
    assert((cap_numerator(c) as real)==(c.cap.num as real)*(f as real));
    assert((d as real)==(c.cap.den as real)*(f as real));
}
pub proof fn theorem_decode_arithmetic(c:Config,a:nat,b:nat)
    requires denominator(c)>0,
    ensures decode(c,0)==0real,decode(c,a+b)==decode(c,a)+decode(c,b),
        (decode(c,a)<decode(c,b) <==> a<b),(decode(c,a)<=decode(c,b) <==> a<=b),
        (decode(c,a)==decode(c,b) <==> a==b),
{
    let d=denominator(c) as real;
    assert(0real/d==0real) by(nonlinear_arith) requires d>0real;
    assert((a as real+b as real)/d==(a as real)/d+(b as real)/d) by(nonlinear_arith) requires d>0real;
    assert(((a as real)/d<(b as real)/d)<==>a<b) by(nonlinear_arith) requires d>0real;
    assert(((a as real)/d<=(b as real)/d)<==>a<=b) by(nonlinear_arith) requires d>0real;
    assert(((a as real)/d==(b as real)/d)<==>a==b) by(nonlinear_arith) requires d>0real;
}
pub proof fn theorem_encoding_preserves_selection(c:Config,a:Arc)
    requires frame(c),
    ensures json::graph_frame(encoded(c)),selected(c,a)==json::selected(encoded(c),a),
{}

pub type JEntry=(real,int,nat);
pub type Parent=(Key,Arc,real);
pub struct JState {pub queue:Set<JEntry>,pub dist:Map<Key,real>,pub parent:Map<Key,Parent>,pub seen:Map<int,nat>}
pub open spec fn je(c:Config,e:json::Entry)->JEntry {(decode(c,e.0),e.1,e.2)}
pub open spec fn jf(c:Config)->spec_fn(json::Entry)->JEntry {|e:json::Entry|je(c,e)}
pub open spec fn jq(c:Config,q:Set<json::Entry>)->Set<JEntry> {q.map(jf(c))}
pub open spec fn dm<K>(c:Config,m:Map<K,nat>)->Map<K,real> {Map::new(m.dom(),|k:K|decode(c,m[k]))}
pub open spec fn pm(c:Config,m:Map<Key,json::Parent>)->Map<Key,Parent> {
    Map::new(m.dom(),|k:Key|(m[k].0,m[k].1,weight(c,m[k].1)))
}
pub open spec fn js(c:Config,s:json::Search)->JState {JState{queue:jq(c,s.queue),dist:dm(c,s.dist),parent:pm(c,s.parent),seen:s.seen}}
pub open spec fn jorder(a:JEntry,b:JEntry)->bool {
    a.0<b.0 || (a.0==b.0 && (a.1<b.1 || (a.1==b.1 && a.2<=b.2)))
}
pub open spec fn jminimum(q:Set<JEntry>)->JEntry {choose|e:JEntry|q.contains(e) && forall|f:JEntry|q.contains(f) ==> jorder(e,f)}
pub open spec fn jinitial(c:Config)->JState {JState{queue:set![(0real,c.src,0nat)],dist:map![(c.src,0nat)=>0real],parent:Map::empty(),seen:Map::empty()}}
pub open spec fn jskipped(s:JState,e:JEntry)->bool {s.seen.contains_key(e.1) && s.seen[e.1]<=e.2}
pub open spec fn jpop(s:JState,e:JEntry)->JState {JState{queue:s.queue.remove(e),..s}}
pub open spec fn jaccept(s:JState,e:JEntry)->JState {JState{seen:s.seen.insert(e.1,e.2),..jpop(s,e)}}
pub open spec fn jrelax(c:Config,s:JState,e:JEntry,a:Arc)->JState {
    let h=if c.bound==0{0nat}else{e.2+1};let n=e.0+weight(c,a);let k=(a.4,h);
    if !selected(c,a) || a.2!=e.1 || (c.bound>0 && h>c.bound) || n>ratio(c.cap)
        || (s.seen.contains_key(a.4) && s.seen[a.4]<=h) || (s.dist.contains_key(k) && s.dist[k]<=n){s}
    else{JState{queue:s.queue.insert((n,a.4,h)),dist:s.dist.insert(k,n),parent:s.parent.insert(k,((e.1,e.2),a,weight(c,a))),..s}}
}
pub open spec fn jexpand(c:Config,s:JState,e:JEntry,arcs:Seq<Arc>)->JState decreases arcs.len() {
    if arcs.len()==0{s}else{jexpand(c,jrelax(c,s,e,arcs[0]),e,arcs.drop_first())}
}
pub open spec fn jneighbors(c:Config,u:int)->Seq<Arc> {c.arcs.filter(|a:Arc|selected(c,a) && a.2==u)}
pub enum JEvent {Continue(JState),Returned{state:JState,entry:JEntry},Empty(JState)}
pub open spec fn jstep(c:Config,s:JState)->JEvent {
    if s.queue.len()==0{JEvent::Empty(s)}else{
        let e=jminimum(s.queue);
        if jskipped(s,e){JEvent::Continue(jpop(s,e))}else{
            let t=jaccept(s,e);
            if e.1==c.dst{JEvent::Returned{state:t,entry:e}}
            else if e.0>=ratio(c.cap) || (c.bound>0 && e.2>=c.bound){JEvent::Continue(t)}
            else{JEvent::Continue(jexpand(c,t,e,jneighbors(c,e.1)))}}}
}
pub open spec fn jimage_event(c:Config,e:json::Event)->JEvent {
    match e{json::Event::Continue(s)=>JEvent::Continue(js(c,s)),json::Event::Empty(s)=>JEvent::Empty(js(c,s)),
        json::Event::Returned{state:s,entry:e}=>JEvent::Returned{state:js(c,s),entry:je(c,e)}}
}
pub proof fn lemma_je_injective(c:Config,e:json::Entry,f:json::Entry)
    requires denominator(c)>0,
    ensures (je(c,e)==je(c,f) <==> e==f),jorder(je(c,e),je(c,f))==json::entry_order()(e,f),
{theorem_decode_arithmetic(c,e.0,f.0);}
pub proof fn lemma_jq_insert_remove(c:Config,q:Set<json::Entry>,e:json::Entry)
    requires denominator(c)>0,
    ensures jq(c,q.insert(e))==jq(c,q).insert(je(c,e)),jq(c,q.remove(e))==jq(c,q).remove(je(c,e)),
        (q.len()==0 <==> jq(c,q).len()==0),
{
    assert forall|r:JEntry|jq(c,q.insert(e)).contains(r) <==> jq(c,q).insert(je(c,e)).contains(r) by {
        q.insert(e).lemma_map_contains(jf(c),r);q.lemma_map_contains(jf(c),r);
        if jq(c,q.insert(e)).contains(r){
            let f=choose|f:json::Entry|q.insert(e).contains(f) && je(c,f)==r;
            if f!=e{assert(q.contains(f));assert(exists|f:json::Entry|q.contains(f) && je(c,f)==r);assert(jq(c,q).contains(r));}
            else{assert(r==je(c,e));}
        }
        else if jq(c,q).insert(je(c,e)).contains(r){
            if r!=je(c,e){let f=choose|f:json::Entry|q.contains(f) && je(c,f)==r;assert(q.insert(e).contains(f));
                assert(exists|f:json::Entry|q.insert(e).contains(f) && je(c,f)==r);}
            else{assert(q.insert(e).contains(e));assert(exists|f:json::Entry|q.insert(e).contains(f) && je(c,f)==r);}
            assert(jq(c,q.insert(e)).contains(r));
        }
    }
    assert forall|r:JEntry|jq(c,q.remove(e)).contains(r) <==> jq(c,q).remove(je(c,e)).contains(r) by {
        q.remove(e).lemma_map_contains(jf(c),r);q.lemma_map_contains(jf(c),r);
        if jq(c,q.remove(e)).contains(r){let f=choose|f:json::Entry|q.remove(e).contains(f) && je(c,f)==r;lemma_je_injective(c,e,f);
            assert(q.contains(f) && f!=e);assert(r!=je(c,e));assert(exists|f:json::Entry|q.contains(f) && je(c,f)==r);assert(jq(c,q).contains(r));}
        else if jq(c,q).remove(je(c,e)).contains(r){let f=choose|f:json::Entry|q.contains(f) && je(c,f)==r;lemma_je_injective(c,e,f);assert(f!=e);
            assert(q.remove(e).contains(f));assert(exists|f:json::Entry|q.remove(e).contains(f) && je(c,f)==r);assert(jq(c,q.remove(e)).contains(r));}
    }
    lemma_set_nonempty(q);lemma_set_nonempty(jq(c,q));
    if q.len()>0{let f=choose|f:json::Entry|q.contains(f);q.lemma_map_contains(jf(c),je(c,f));assert(jq(c,q).contains(je(c,f)));}
    if jq(c,q).len()>0{let r=choose|r:JEntry|jq(c,q).contains(r);q.lemma_map_contains(jf(c),r);let f=choose|f:json::Entry|q.contains(f) && je(c,f)==r;}
    assert(jq(c,q.insert(e)) =~= jq(c,q).insert(je(c,e)));
    assert(jq(c,q.remove(e)) =~= jq(c,q).remove(je(c,e)));
}
pub proof fn lemma_set_nonempty<A>(q:Set<A>)
    ensures q.len()>0 <==> exists|a:A|q.contains(a),
{
    q.lemma_to_seq_len();q.lemma_to_seq_to_set_id();let seq=q.to_seq();seq.to_set_ensures();
    if q.len()>0{assert(seq.contains(seq[0]));assert(q.contains(seq[0]));}
    else{assert(seq =~= Seq::<A>::empty());assert(q =~= Set::<A>::empty());}
}
pub proof fn lemma_dm_insert<K>(c:Config,m:Map<K,nat>,k:K,n:nat)
    ensures dm(c,m.insert(k,n))==dm(c,m).insert(k,decode(c,n)),dm(c,m).dom()==m.dom(),
{
    assert(dm(c,m.insert(k,n)) =~= dm(c,m).insert(k,decode(c,n)));
}
pub proof fn lemma_pm_insert(c:Config,m:Map<Key,json::Parent>,k:Key,p:json::Parent)
    ensures pm(c,m.insert(k,p))==pm(c,m).insert(k,(p.0,p.1,weight(c,p.1))),pm(c,m).dom()==m.dom(),
{assert(pm(c,m.insert(k,p)) =~= pm(c,m).insert(k,(p.0,p.1,weight(c,p.1))));}
pub proof fn lemma_kernel_json_lex(q:Set<json::Entry>)
    requires q.len()>0,
    ensures q.contains(json::minimum(q)),forall|f:json::Entry|q.contains(f) ==> json::entry_order()(json::minimum(q),f),
{
    json::lemma_minimum(q);json::lemma_entry_order();let seq=q.to_seq();seq.lemma_sort_by_ensures(json::entry_order());
    seq.to_multiset_ensures();seq.sort_by(json::entry_order()).to_multiset_ensures();q.lemma_to_seq_to_set_id();
    assert forall|f:json::Entry|q.contains(f) implies json::entry_order()(json::minimum(q),f) by {
        assert(seq.contains(f));to_multiset_contains(seq,f);to_multiset_contains(seq.sort_by(json::entry_order()),f);
        let i=choose|i:int|0<=i<seq.sort_by(json::entry_order()).len() && seq.sort_by(json::entry_order())[i]==f;
        assert(json::entry_order()(seq.sort_by(json::entry_order())[0],seq.sort_by(json::entry_order())[i]));
    }
}
pub proof fn theorem_json_minimum_commutes(c:Config,q:Set<json::Entry>)
    requires denominator(c)>0,q.len()>0,
    ensures jminimum(jq(c,q))==je(c,json::minimum(q)),
{
    lemma_kernel_json_lex(q);let e=json::minimum(q);assert(jq(c,q).contains(je(c,e)));
    assert forall|r:JEntry|jq(c,q).contains(r) implies jorder(je(c,e),r) by {
        q.lemma_map_contains(jf(c),r);let f=choose|f:json::Entry|q.contains(f) && je(c,f)==r;lemma_je_injective(c,e,f);
    }
    assert(exists|r:JEntry|jq(c,q).contains(r) && forall|f:JEntry|jq(c,q).contains(f) ==> jorder(r,f));
    let r=jminimum(jq(c,q));assert(jq(c,q).contains(r));q.lemma_map_contains(jf(c),r);let f=choose|f:json::Entry|q.contains(f) && je(c,f)==r;
    assert(jorder(je(c,e),r));assert(jorder(r,je(c,e)));assert(r==je(c,e));
}
pub proof fn theorem_cap_decode(c:Config)
    requires frame(c),
    ensures denominator(c)>0,decode(c,encoded(c).cap)==ratio(c.cap),
{
    theorem_common_denominator_derived(c);let ds=denominations(c);let f=omitted(ds,c.arcs.len());
    lemma_product(ds,c.arcs.len());lemma_ratio(c.cap.num,c.cap.den,f);
    lemma_nat_real_mul(c.cap.num as nat,f);lemma_nat_real_mul(c.cap.den,f);
    assert((denominator(c) as real)==(c.cap.den as real)*(f as real));
    assert((cap_numerator(c) as real)==(c.cap.num as real)*(f as real));
}
pub proof fn theorem_json_initial_commutes(c:Config)
    requires frame(c),
    ensures jinitial(c)==js(c,json::initial(encoded(c))),
{
    theorem_common_denominator_derived(c);theorem_decode_arithmetic(c,0,0);
    lemma_jq_insert_remove(c,Set::empty(),(0nat,c.src,0nat));
    assert(jq(c,Set::empty()) =~= Set::<JEntry>::empty());
    assert(dm(c,Map::<Key,nat>::empty()) =~= Map::<Key,real>::empty());
    assert(pm(c,Map::<Key,json::Parent>::empty()) =~= Map::<Key,Parent>::empty());
    lemma_dm_insert(c,Map::<Key,nat>::empty(),(c.src,0nat),0nat);
}
pub proof fn lemma_json_pop_accept(c:Config,s:json::Search,e:json::Entry)
    requires denominator(c)>0,
    ensures jpop(js(c,s),je(c,e))==js(c,json::pop_only(s,e)),jaccept(js(c,s),je(c,e))==js(c,json::accept(s,e)),
{lemma_jq_insert_remove(c,s.queue,e);}
pub proof fn theorem_json_relax_commutes(c:Config,s:json::Search,e:json::Entry,a:Arc)
    requires frame(c),
    ensures jrelax(c,js(c,s),je(c,e),a)==js(c,json::relax(encoded(c),s,e,a)),
{
    theorem_encoding_preserves_selection(c,a);theorem_cap_decode(c);
    let h=json::next_hop(encoded(c),e.2);let k=(a.4,h);let n=e.0+json::weight(encoded(c),a);
    assert(dm(c,s.dist).dom()==s.dist.dom());
    if selected(c,a){
        theorem_scalar_and_cap_decode(c,a);theorem_decode_arithmetic(c,e.0,json::weight(encoded(c),a));
        theorem_decode_arithmetic(c,n,encoded(c).cap);
        if s.dist.contains_key(k){theorem_decode_arithmetic(c,s.dist[k],n);}
        if a.2==e.1 && json::hop_ok(encoded(c),h) && n<=encoded(c).cap
            && !(s.seen.contains_key(a.4) && s.seen[a.4]<=h) && !(s.dist.contains_key(k) && s.dist[k]<=n){
            lemma_jq_insert_remove(c,s.queue,(n,a.4,h));lemma_dm_insert(c,s.dist,k,n);lemma_pm_insert(c,s.parent,k,((e.1,e.2),a));
        }
    }
}
pub proof fn theorem_json_fold_commutes(c:Config,s:json::Search,e:json::Entry,arcs:Seq<Arc>)
    requires frame(c),
    ensures jexpand(c,js(c,s),je(c,e),arcs)==js(c,json::expand(encoded(c),s,e,arcs)),
    decreases arcs.len(),
{
    if arcs.len()>0{theorem_json_relax_commutes(c,s,e,arcs[0]);theorem_json_fold_commutes(c,json::relax(encoded(c),s,e,arcs[0]),e,arcs.drop_first());}
}
pub proof fn lemma_json_neighbor_sequence(c:Config,u:int)
    requires frame(c),
    ensures json::neighbors(encoded(c),u)==jneighbors(c,u),
{
    broadcast use lemma_filter_ext;
    reveal(json::neighbors);reveal(jneighbors);let ck=encoded(c);
    assert forall|a:Arc|selected(c,a)==json::selected(encoded(c),a) by {theorem_encoding_preserves_selection(c,a);}
    let p=|a:Arc|selected(c,a) && a.2==u;let q=|a:Arc|json::selected(ck,a) && a.2==u;
    assert(ck.arcs==c.arcs);lemma_filter_ext(c.arcs,p,q);
    assert(jneighbors(c,u)==c.arcs.filter(p));
    assert(json::neighbors(ck,u)==ck.arcs.filter(q));
}
pub broadcast proof fn lemma_filter_ext<A>(s:Seq<A>,p:spec_fn(A)->bool,q:spec_fn(A)->bool)
    requires forall|a:A|#[trigger] p(a)==q(a),
    ensures #[trigger] s.filter(p)==#[trigger] s.filter(q),
    decreases s.len(),
{
    s.lemma_filter_eq_filter_alt(p);s.lemma_filter_eq_filter_alt(q);
    if s.len()>0{lemma_filter_ext(s.drop_first(),p,q);}
}
pub proof fn theorem_json_step_commutes(c:Config,s:json::Search)
    requires frame(c),
    ensures jstep(c,js(c,s))==jimage_event(c,json::step(encoded(c),s)),
{
    reveal(jstep);reveal(json::step);reveal(jimage_event);
    theorem_cap_decode(c);lemma_jq_insert_remove(c,s.queue,(0nat,c.src,0nat));
    if s.queue.len()>0{
        let e=json::minimum(s.queue);theorem_json_minimum_commutes(c,s.queue);lemma_json_pop_accept(c,s,e);
        theorem_decode_arithmetic(c,e.0,encoded(c).cap);
        if json::skipped(s,e){assert(jskipped(js(c,s),je(c,e)));}
        else{
            if e.1==c.dst{}
            else if e.0>=encoded(c).cap || (c.bound>0 && e.2>=c.bound){}
            else{
                lemma_json_neighbor_sequence(c,e.1);
                theorem_json_fold_commutes(c,json::accept(s,e),e,json::neighbors(encoded(c),e.1));
            }
        }
    }
}

pub type CEntry=(real,int);
pub struct Side {pub queue:Set<CEntry>,pub dist:Map<int,real>,pub hop:Map<int,nat>,pub done:Set<int>,pub witness:Map<int,Seq<Arc>>}
pub struct CState {pub forward:Side,pub backward:Side,pub best:Option<real>,pub best_hops:nat,pub best_path:Seq<Arc>}
pub open spec fn ce(c:Config,e:kernel::Entry)->CEntry {(decode(c,e.0),e.1)}
pub open spec fn cf(c:Config)->spec_fn(kernel::Entry)->CEntry {|e:kernel::Entry|ce(c,e)}
pub open spec fn cq(c:Config,q:Set<kernel::Entry>)->Set<CEntry> {q.map(cf(c))}
pub open spec fn side(s:CState,b:bool)->Side {if b{s.backward}else{s.forward}}
pub open spec fn put(s:CState,b:bool,z:Side)->CState {if b{CState{backward:z,..s}}else{CState{forward:z,..s}}}
pub open spec fn ds(c:Config,z:kernel::Side)->Side {Side{queue:cq(c,z.queue),dist:dm(c,z.dist),hop:z.hop,done:z.done,witness:z.witness}}
pub open spec fn option(c:Config,n:Option<nat>)->Option<real> {if n.is_some(){Some(decode(c,n.unwrap()))}else{None}}
pub open spec fn cs(c:Config,s:kernel::State)->CState {CState{forward:ds(c,s.forward),backward:ds(c,s.backward),best:option(c,s.best),best_hops:s.best_hops,best_path:s.best_path}}
pub open spec fn corder(a:CEntry,b:CEntry)->bool {a.0<b.0 || (a.0==b.0 && a.1<=b.1)}
pub open spec fn cminimum(q:Set<CEntry>)->CEntry {choose|e:CEntry|q.contains(e) && forall|f:CEntry|q.contains(f) ==> corder(e,f)}
pub open spec fn select(c:Config,b:bool,a:Arc)->bool {
    c.raw.contains_key(a) && a.1==c.graph && (match c.direction{json::Dir::Out=>a.0==(if b{1nat}else{0nat}),json::Dir::In=>a.0==(if b{0nat}else{1nat}),json::Dir::Both=>a.0<=1})
    && (c.predicates.len()==0 || c.predicates.contains(a.3))
}
pub open spec fn mirrored(c:Config)->bool {forall|b:bool,a:Arc|#[trigger] select(c,b,a) ==> select(c,!b,kernel::reverse(a)) && weight(c,a)==weight(c,kernel::reverse(a))}
pub open spec fn primary_tag(c:Config,b:bool)->nat {let f=match c.direction{json::Dir::In=>1nat,_=>0nat};if b{(1-f) as nat}else{f}}
pub open spec fn scan(c:Config,b:bool,u:int,first:bool)->spec_fn(Arc)->bool {|a:Arc|select(c,b,a) && a.2==u && ((a.0==primary_tag(c,b))==first)}
pub open spec fn cneighbors(c:Config,b:bool,u:int)->Seq<Arc> {c.arcs.filter(scan(c,b,u,true))+c.arcs.filter(scan(c,b,u,false))}
pub open spec fn cinitial_side(c:Config,b:bool)->Side {let r=if b{c.dst}else{c.src};Side{queue:set![(0real,r)],dist:map![r=>0real],hop:map![r=>0nat],done:Set::empty(),witness:map![r=>seq![]]}}
pub open spec fn cinitial(c:Config)->CState {CState{forward:cinitial_side(c,false),backward:cinitial_side(c,true),best:None,best_hops:0,best_path:seq![]}}
pub open spec fn caccept(z:Side,e:CEntry)->Side {Side{queue:z.queue.remove(e),done:z.done.insert(e.1),..z}}
pub open spec fn cadmitted(c:Config,b:bool,z:Side,e:CEntry,a:Arc)->bool {select(c,b,a) && a.2==e.1 && !z.done.contains(a.4) && e.0+weight(c,a)<=ratio(c.cap)}
pub open spec fn cdecrease(c:Config,b:bool,z:Side,e:CEntry,a:Arc)->Side {
    let v=a.4;let n=e.0+weight(c,a);
    if !cadmitted(c,b,z,e,a) || (z.dist.contains_key(v) && z.dist[v]<=n){z}else{
        let q=if z.dist.contains_key(v){z.queue.remove((z.dist[v],v))}else{z.queue};
        Side{queue:q.insert((n,v)),dist:z.dist.insert(v,n),hop:z.hop.insert(v,z.hop[e.1]+1),witness:z.witness.insert(v,z.witness[e.1].push(a)),..z}}
}
pub open spec fn crelax(c:Config,s:CState,b:bool,e:CEntry,a:Arc)->CState {
    let z=side(s,b);let t=put(s,b,cdecrease(c,b,z,e,a));let v=a.4;
    if !cadmitted(c,b,z,e,a) || !side(t,!b).dist.contains_key(v){t}else{
        let n=side(t,b).dist[v]+side(t,!b).dist[v];
        if s.best.is_some() && s.best.unwrap()<=n{t}else{CState{best:Some(n),best_hops:side(t,false).hop[v]+side(t,true).hop[v],best_path:side(t,false).witness[v]+kernel::reverse_path(side(t,true).witness[v]),..t}}}
}
pub open spec fn cexpand(c:Config,s:CState,b:bool,e:CEntry,arcs:Seq<Arc>)->CState decreases arcs.len() {
    if arcs.len()==0{s}else{cexpand(c,crelax(c,s,b,e,arcs[0]),b,e,arcs.drop_first())}
}
pub enum CEvent {Continue(CState),Halt(kernel::Reason)}
pub open spec fn cstep(c:Config,s:CState)->CEvent {
    if s.forward.queue.len()==0 || s.backward.queue.len()==0{CEvent::Halt(kernel::Reason::Empty)}else{
        let f=cminimum(s.forward.queue);let r=cminimum(s.backward.queue);
        if s.best.is_some() && f.0+r.0>=s.best.unwrap(){CEvent::Halt(kernel::Reason::FrontSum)}else{
            let b=r.0<f.0;let e=if b{r}else{f};let t=put(s,b,caccept(side(s,b),e));
            if e.0>=ratio(c.cap){CEvent::Continue(t)}else{CEvent::Continue(cexpand(c,t,b,e,cneighbors(c,b,e.1)))}}}
}
pub open spec fn cimage_event(c:Config,e:kernel::Event)->CEvent {match e{kernel::Event::Continue(s)=>CEvent::Continue(cs(c,s)),kernel::Event::Halt(r)=>CEvent::Halt(r)}}
pub proof fn lemma_ce_injective(c:Config,e:kernel::Entry,f:kernel::Entry)
    requires denominator(c)>0,
    ensures (ce(c,e)==ce(c,f) <==> e==f),corder(ce(c,e),ce(c,f))==kernel::order()(e,f),
{theorem_decode_arithmetic(c,e.0,f.0);}
pub proof fn lemma_kernel_cost_lex(q:Set<kernel::Entry>)
    requires q.len()>0,
    ensures q.contains(kernel::minimum(q)),forall|f:kernel::Entry|q.contains(f) ==> kernel::order()(kernel::minimum(q),f),
{
    kernel::lemma_minimum(q);kernel::lemma_order();let seq=q.to_seq();seq.lemma_sort_by_ensures(kernel::order());
    seq.to_multiset_ensures();seq.sort_by(kernel::order()).to_multiset_ensures();q.lemma_to_seq_to_set_id();
    assert forall|f:kernel::Entry|q.contains(f) implies kernel::order()(kernel::minimum(q),f) by {
        assert(seq.contains(f));to_multiset_contains(seq,f);to_multiset_contains(seq.sort_by(kernel::order()),f);
        let i=choose|i:int|0<=i<seq.sort_by(kernel::order()).len() && seq.sort_by(kernel::order())[i]==f;
        assert(kernel::order()(seq.sort_by(kernel::order())[0],seq.sort_by(kernel::order())[i]));
    }
}
pub proof fn theorem_cost_minimum_commutes(c:Config,q:Set<kernel::Entry>)
    requires denominator(c)>0,q.len()>0,
    ensures cminimum(cq(c,q))==ce(c,kernel::minimum(q)),
{
    lemma_kernel_cost_lex(q);let e=kernel::minimum(q);q.lemma_map_contains(cf(c),ce(c,e));assert(cq(c,q).contains(ce(c,e)));
    assert forall|r:CEntry|cq(c,q).contains(r) implies corder(ce(c,e),r) by {
        q.lemma_map_contains(cf(c),r);let f=choose|f:kernel::Entry|q.contains(f) && ce(c,f)==r;lemma_ce_injective(c,e,f);
    }
    assert(exists|r:CEntry|cq(c,q).contains(r) && forall|f:CEntry|cq(c,q).contains(f) ==> corder(r,f));
    let r=cminimum(cq(c,q));assert(cq(c,q).contains(r));q.lemma_map_contains(cf(c),r);let f=choose|f:kernel::Entry|q.contains(f) && ce(c,f)==r;
    assert(corder(ce(c,e),r));assert(corder(r,ce(c,e)));assert(r==ce(c,e));
}
pub proof fn theorem_cost_selection_and_frame(c:Config,b:bool,a:Arc)
    requires frame(c),
    ensures select(c,b,a)==kernel::select(encoded(c),b,a),mirrored(c) ==> kernel::frame(encoded(c)),
{
    theorem_encoding_preserves_selection(c,a);theorem_common_denominator_derived(c);
    if mirrored(c){
        assert forall|bb:bool,aa:Arc|#[trigger] kernel::select(encoded(c),bb,aa) implies kernel::select(encoded(c),!bb,kernel::reverse(aa)) && json::weight(encoded(c),aa)==json::weight(encoded(c),kernel::reverse(aa)) by {
            assert(select(c,bb,aa));let rev=kernel::reverse(aa);assert(select(c,!bb,rev));
            theorem_scalar_and_cap_decode(c,aa);theorem_scalar_and_cap_decode(c,rev);
            theorem_decode_arithmetic(c,json::weight(encoded(c),aa),json::weight(encoded(c),rev));
        }
    }
}
pub proof fn lemma_cq_insert_remove(c:Config,q:Set<kernel::Entry>,e:kernel::Entry)
    requires denominator(c)>0,
    ensures cq(c,q.insert(e))==cq(c,q).insert(ce(c,e)),cq(c,q.remove(e))==cq(c,q).remove(ce(c,e)),
        (q.len()==0 <==> cq(c,q).len()==0),
{
    assert forall|r:CEntry|cq(c,q.insert(e)).contains(r) <==> cq(c,q).insert(ce(c,e)).contains(r) by {
        q.insert(e).lemma_map_contains(cf(c),r);q.lemma_map_contains(cf(c),r);
        if cq(c,q.insert(e)).contains(r){
            let f=choose|f:kernel::Entry|q.insert(e).contains(f) && ce(c,f)==r;
            if f!=e{assert(q.contains(f));assert(exists|f:kernel::Entry|q.contains(f) && ce(c,f)==r);assert(cq(c,q).contains(r));}
            else{assert(r==ce(c,e));}
        }
        else if cq(c,q).insert(ce(c,e)).contains(r){
            if r!=ce(c,e){let f=choose|f:kernel::Entry|q.contains(f) && ce(c,f)==r;assert(q.insert(e).contains(f));
                assert(exists|f:kernel::Entry|q.insert(e).contains(f) && ce(c,f)==r);}
            else{assert(q.insert(e).contains(e));assert(exists|f:kernel::Entry|q.insert(e).contains(f) && ce(c,f)==r);}
            assert(cq(c,q.insert(e)).contains(r));
        }
    }
    assert forall|r:CEntry|cq(c,q.remove(e)).contains(r) <==> cq(c,q).remove(ce(c,e)).contains(r) by {
        q.remove(e).lemma_map_contains(cf(c),r);q.lemma_map_contains(cf(c),r);
        if cq(c,q.remove(e)).contains(r){let f=choose|f:kernel::Entry|q.remove(e).contains(f) && ce(c,f)==r;lemma_ce_injective(c,e,f);
            assert(q.contains(f) && f!=e);assert(r!=ce(c,e));assert(exists|f:kernel::Entry|q.contains(f) && ce(c,f)==r);assert(cq(c,q).contains(r));}
        else if cq(c,q).remove(ce(c,e)).contains(r){let f=choose|f:kernel::Entry|q.contains(f) && ce(c,f)==r;lemma_ce_injective(c,e,f);assert(f!=e);
            assert(q.remove(e).contains(f));assert(exists|f:kernel::Entry|q.remove(e).contains(f) && ce(c,f)==r);assert(cq(c,q.remove(e)).contains(r));}
    }
    lemma_set_nonempty(q);lemma_set_nonempty(cq(c,q));
    if q.len()>0{let f=choose|f:kernel::Entry|q.contains(f);q.lemma_map_contains(cf(c),ce(c,f));assert(cq(c,q).contains(ce(c,f)));}
    if cq(c,q).len()>0{let r=choose|r:CEntry|cq(c,q).contains(r);q.lemma_map_contains(cf(c),r);let f=choose|f:kernel::Entry|q.contains(f) && ce(c,f)==r;}
    assert(cq(c,q.insert(e)) =~= cq(c,q).insert(ce(c,e)));
    assert(cq(c,q.remove(e)) =~= cq(c,q).remove(ce(c,e)));
}
pub proof fn lemma_cost_projection(c:Config,s:kernel::State,b:bool,z:kernel::Side)
    ensures cs(c,kernel::put(s,b,z))==put(cs(c,s),b,ds(c,z)),side(cs(c,s),b)==ds(c,kernel::side(s,b)),
{}
pub proof fn theorem_cost_initial_commutes(c:Config)
    requires frame(c),
    ensures cinitial(c)==cs(c,kernel::initial(encoded(c))),
{
    theorem_cap_decode(c);theorem_decode_arithmetic(c,0,0);
    assert forall|b:bool|cinitial_side(c,b)==ds(c,kernel::initial_side(encoded(c),b)) by {
        let r=if b{c.dst}else{c.src};lemma_cq_insert_remove(c,Set::empty(),(0nat,r));lemma_dm_insert(c,Map::<int,nat>::empty(),r,0nat);
        assert(cq(c,Set::empty()) =~= Set::<CEntry>::empty());assert(dm(c,Map::<int,nat>::empty()) =~= Map::<int,real>::empty());
    }
}
pub proof fn lemma_cost_accept_commutes(c:Config,z:kernel::Side,e:kernel::Entry)
    requires denominator(c)>0,
    ensures caccept(ds(c,z),ce(c,e))==ds(c,kernel::accept(z,e)),
{lemma_cq_insert_remove(c,z.queue,e);}
pub proof fn theorem_cost_decrease_commutes(c:Config,b:bool,z:kernel::Side,e:kernel::Entry,a:Arc)
    requires frame(c),
    ensures cdecrease(c,b,ds(c,z),ce(c,e),a)==ds(c,kernel::decrease(encoded(c),b,z,e,a)),
        cadmitted(c,b,ds(c,z),ce(c,e),a)==kernel::admitted(encoded(c),b,z,e,a),
{
    theorem_cost_selection_and_frame(c,b,a);theorem_cap_decode(c);
    assert(dm(c,z.dist).dom()==z.dist.dom());
    let v=a.4;let n=e.0+json::weight(encoded(c),a);
    if select(c,b,a){
        theorem_scalar_and_cap_decode(c,a);theorem_decode_arithmetic(c,e.0,json::weight(encoded(c),a));
        theorem_decode_arithmetic(c,n,encoded(c).cap);
        if z.dist.contains_key(v){theorem_decode_arithmetic(c,z.dist[v],n);}
        if kernel::admitted(encoded(c),b,z,e,a) && !(z.dist.contains_key(v) && z.dist[v]<=n){
            let q=if z.dist.contains_key(v){z.queue.remove((z.dist[v],v))}else{z.queue};
            if z.dist.contains_key(v){lemma_cq_insert_remove(c,z.queue,(z.dist[v],v));}
            lemma_cq_insert_remove(c,q,(n,v));lemma_dm_insert(c,z.dist,v,n);
        }
    }
}
pub proof fn theorem_cost_relax_commutes(c:Config,s:kernel::State,b:bool,e:kernel::Entry,a:Arc)
    requires frame(c),
    ensures crelax(c,cs(c,s),b,ce(c,e),a)==cs(c,kernel::relax(encoded(c),s,b,e,a)),
{
    theorem_cap_decode(c);let z=kernel::side(s,b);theorem_cost_decrease_commutes(c,b,z,e,a);
    let dec=kernel::decrease(encoded(c),b,z,e,a);let t=kernel::put(s,b,dec);let v=a.4;
    lemma_cost_projection(c,s,b,z);lemma_cost_projection(c,s,b,dec);
    assert(side(cs(c,s),b)==ds(c,z));assert(put(cs(c,s),b,ds(c,dec))==cs(c,t));
    if kernel::admitted(encoded(c),b,z,e,a) && kernel::side(t,!b).dist.contains_key(v){
        assert(dec.dist.contains_key(v));assert(kernel::side(t,b).dist.contains_key(v));
        let n=kernel::side(t,b).dist[v]+kernel::side(t,!b).dist[v];
        theorem_decode_arithmetic(c,kernel::side(t,b).dist[v],kernel::side(t,!b).dist[v]);
        if s.best.is_some(){theorem_decode_arithmetic(c,s.best.unwrap(),n);}
    }
}
pub proof fn theorem_cost_fold_commutes(c:Config,s:kernel::State,b:bool,e:kernel::Entry,arcs:Seq<Arc>)
    requires frame(c),
    ensures cexpand(c,cs(c,s),b,ce(c,e),arcs)==cs(c,kernel::expand(encoded(c),s,b,e,arcs)),
    decreases arcs.len(),
{
    if arcs.len()>0{theorem_cost_relax_commutes(c,s,b,e,arcs[0]);theorem_cost_fold_commutes(c,kernel::relax(encoded(c),s,b,e,arcs[0]),b,e,arcs.drop_first());}
}
pub proof fn lemma_cost_neighbor_sequence(c:Config,b:bool,u:int)
    requires frame(c),
    ensures cneighbors(c,b,u)==kernel::neighbors(encoded(c),b,u),
{
    broadcast use lemma_filter_ext;
    let ck=encoded(c);
    assert forall|a:Arc|select(c,b,a)==kernel::select(ck,b,a) by {theorem_cost_selection_and_frame(c,b,a);}
    assert(primary_tag(c,b)==kernel::primary_tag(ck,b));
    lemma_filter_ext(c.arcs,scan(c,b,u,true),kernel::scan_pred(ck,b,u,true));
    lemma_filter_ext(c.arcs,scan(c,b,u,false),kernel::scan_pred(ck,b,u,false));
}
pub proof fn theorem_cost_step_commutes(c:Config,s:kernel::State)
    requires frame(c),
    ensures cstep(c,cs(c,s))==cimage_event(c,kernel::step(encoded(c),s)),
{
    theorem_cap_decode(c);lemma_cq_insert_remove(c,s.forward.queue,(0nat,c.src));lemma_cq_insert_remove(c,s.backward.queue,(0nat,c.dst));
    if s.forward.queue.len()>0 && s.backward.queue.len()>0{
        let f=kernel::minimum(s.forward.queue);let r=kernel::minimum(s.backward.queue);
        theorem_cost_minimum_commutes(c,s.forward.queue);theorem_cost_minimum_commutes(c,s.backward.queue);
        theorem_decode_arithmetic(c,f.0,r.0);theorem_decode_arithmetic(c,r.0,f.0);
        if s.best.is_some(){theorem_decode_arithmetic(c,f.0+r.0,s.best.unwrap());}
        if !(s.best.is_some() && f.0+r.0>=s.best.unwrap()){
            let b=r.0<f.0;let e=if b{r}else{f};let z=kernel::side(s,b);let accepted=kernel::accept(z,e);let t=kernel::put(s,b,accepted);
            lemma_cost_projection(c,s,b,accepted);lemma_cost_accept_commutes(c,z,e);theorem_decode_arithmetic(c,e.0,encoded(c).cap);
            if e.0<encoded(c).cap{lemma_cost_neighbor_sequence(c,b,e.1);theorem_cost_fold_commutes(c,t,b,e,kernel::neighbors(encoded(c),b,e.1));}
        }
    }
}
}
