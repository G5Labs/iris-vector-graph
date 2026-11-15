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
pub enum JEvent {Continue(JState),Returned{state:JState,entry:JEntry},Empty(JState)}
pub open spec fn jstep(c:Config,s:JState)->JEvent {
    if s.queue.len()==0{JEvent::Empty(s)}else{
        let e=jminimum(s.queue);
        if jskipped(s,e){JEvent::Continue(jpop(s,e))}else{
            let t=jaccept(s,e);
            if e.1==c.dst{JEvent::Returned{state:t,entry:e}}
            else if e.0>=ratio(c.cap) || (c.bound>0 && e.2>=c.bound){JEvent::Continue(t)}
            else{JEvent::Continue(jexpand(c,t,e,c.arcs.filter(|a:Arc|selected(c,a) && a.2==e.1)))}}}
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
}
