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
        lemma_nat_real_mul(a,(b-1) as nat);
        assert(a*b==a*((b-1) as nat)+a) by(nonlinear_arith);
        assert(((a*b) as real)==((a*((b-1) as nat)) as real)+(a as real));
        assert(((b-1) as nat) as real==(b as real)-1real);
        assert((a as real)*((b as real)-1real)+(a as real)==(a as real)*(b as real)) by(nonlinear_arith);
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
}
