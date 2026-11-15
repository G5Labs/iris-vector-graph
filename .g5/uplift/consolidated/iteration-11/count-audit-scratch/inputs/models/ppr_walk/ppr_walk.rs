// Exact mathematical PPR over stable closed raw tables. Graph IDs are equality
// atoms; node IDs are atoms equipped with an integer total order, not a proof of
// all IRIS string collation or graph-name normalization. Optional count is the
// stored nonnegative # scalar (absent =>1), not supplied degree/transition data.
// Completed ordinary native keyed leaves have positive counts and faithful
// in/out mirrors. Negative/malformed/partial/provider states are unassessed.
// Native normal-forward Adj.Degree must equal raw eligible multiplicity; neither
// its cache nor the algorithm score cache is proved by this model. The actual
// Python fallback/direct native exclusion-count paths recompute those divisors.
// Only empty/unqualified predicate-ID exclusions are formalized. Type.p prefix
// matching and exclusion parsing remain separately observed source providers.
// Closed endpoints, unique scoped node rows and stable reads are explicit in
// raw preparation; missing/unstable/unfaithful tables are not silently repaired.
// Native floats/$Normalize and arbitrary ID carriers remain finite binding
// evidence, separate from exact reals, rational recurrence and decimal buckets.
use vstd::prelude::*;
verus! {
pub struct Node {pub graph:int,pub id:int}
pub struct Edge {pub graph:int,pub src:int,pub pred:int,pub dst:int,pub count:Option<nat>}
pub struct Hop {pub dst:int,pub weight:real}
pub struct Context {pub nodes:Seq<int>,pub edges:Seq<Edge>,pub graph:int,pub seeds:Seq<int>,pub excluded:Seq<int>,pub reverse:bool,pub weight:real,pub alpha:real}
pub open spec fn scoped(raw:Seq<Node>,g:int)->Seq<int> decreases raw.len() {
 if raw.len()==0 {seq![]} else {let t=scoped(raw.drop_first(),g);if raw[0].graph==g {seq![raw[0].id]+t}else{t}}
}
pub open spec fn valid_seeds(raw:Seq<int>,ns:Seq<int>)->Seq<int> decreases raw.len() {
 if raw.len()==0 {seq![]} else {let t=valid_seeds(raw.drop_first(),ns);if ns.contains(raw[0]) && !t.contains(raw[0]) {seq![raw[0]]+t}else{t}}
}
pub open spec fn mult(e:Edge)->nat {e.count.unwrap_or(1)}
pub open spec fn copies(h:Hop,n:nat)->Seq<Hop> decreases n {if n==0{seq![]}else{seq![h]+copies(h,(n-1) as nat)}}
pub open spec fn hops(es:Seq<Edge>,g:int,u:int,ex:Seq<int>,rev:bool,w:real)->Seq<Hop> decreases es.len() {
 if es.len()==0 {seq![]} else {
  let e=es[0]; let tail=hops(es.drop_first(),g,u,ex,rev,w);
  let keep=e.graph==g && !ex.contains(e.pred);
  let f=if keep && e.src==u {copies(Hop{dst:e.dst,weight:1real},mult(e))}else{seq![]};
  let r=if keep && rev && w>0real && e.dst==u {copies(Hop{dst:e.src,weight:w},mult(e))}else{seq![]};
  f+r+tail
 }
}
pub open spec fn pos(ns:Seq<int>,id:int)->nat decreases ns.len() {if ns.len()==0{0}else if ns[0]==id{0}else{1+pos(ns.drop_first(),id)}}
pub open spec fn zeros(n:nat)->Seq<real> {Seq::new(n,|i:int|0real)}
pub open spec fn sum(v:Seq<real>)->real decreases v.len() {if v.len()==0{0real}else{v[0]+sum(v.drop_first())}}
pub open spec fn deposit(v:Seq<real>,i:nat,a:real)->Seq<real> {if i<v.len(){v.update(i as int,v[i as int]+a)}else{v}}
pub open spec fn seed_add(v:Seq<real>,ns:Seq<int>,ss:Seq<int>,a:real)->Seq<real> decreases ss.len() {
 if ss.len()==0{v}else{seed_add(deposit(v,pos(ns,ss[0]),a),ns,ss.drop_first(),a)}
}
pub open spec fn initial(c:Context)->Seq<real> {seed_add(zeros(c.nodes.len()),c.nodes,c.seeds,1real/(c.seeds.len() as real))}
pub open spec fn ship(v:Seq<real>,ns:Seq<int>,hs:Seq<Hop>,share:real)->Seq<real> decreases hs.len() {
 if hs.len()==0{v}else{ship(deposit(v,pos(ns,hs[0].dst),share*hs[0].weight),ns,hs.drop_first(),share)}
}
pub struct Sweep {pub values:Seq<real>,pub dangling:real}
pub open spec fn scatter(c:Context,old:Seq<real>,i:nat,out:Seq<real>,dang:real)->Sweep decreases c.nodes.len()-i {
 if i>=c.nodes.len(){Sweep{values:out,dangling:dang}}else{
  let hs=hops(c.edges,c.graph,c.nodes[i as int],c.excluded,c.reverse,c.weight);
  if hs.len()==0 {scatter(c,old,i+1,out,dang+old[i as int])}else{
   scatter(c,old,i+1,ship(out,c.nodes,hs,c.alpha*old[i as int]/(hs.len() as real)),dang)
  }
 }
}
pub open spec fn next(c:Context,old:Seq<real>)->Seq<real> {
 let s=scatter(c,old,0,zeros(c.nodes.len()),0real);
 let restart=((1real-c.alpha)+c.alpha*s.dangling)/(c.seeds.len() as real);
 seed_add(s.values,c.nodes,c.seeds,restart)
}
pub open spec fn closed(c:Context)->bool {
 c.nodes.no_duplicates() && c.seeds.len()>0 && c.seeds.no_duplicates()
 && (forall|i:int|0<=i<c.seeds.len() ==> c.nodes.contains(c.seeds[i]))
 && (forall|i:int,j:int|0<=i<c.nodes.len() && 0<=j<hops(c.edges,c.graph,c.nodes[i],c.excluded,c.reverse,c.weight).len() ==> #[trigger] c.nodes.contains(hops(c.edges,c.graph,c.nodes[i],c.excluded,c.reverse,c.weight)[j].dst))
}
pub open spec fn unit(c:Context)->bool {!c.reverse || c.weight<=0real || c.weight==1real}
pub proof fn lemma_pos(ns:Seq<int>,id:int) requires ns.contains(id), ensures pos(ns,id)<ns.len(),ns[pos(ns,id) as int]==id, decreases ns.len() {
 if ns[0]!=id {let k=choose|k:int|0<=k<ns.len() && ns[k]==id; assert(k>0);assert(ns.drop_first()[k-1]==id);lemma_pos(ns.drop_first(),id);}
}
pub proof fn lemma_sum_zeros(n:nat) ensures sum(zeros(n))==0real, decreases n {
 if n>0 {assert(zeros(n).drop_first()==zeros((n-1) as nat));lemma_sum_zeros((n-1) as nat);}
}
pub proof fn lemma_deposit(v:Seq<real>,i:nat,a:real) requires i<v.len(), ensures deposit(v,i,a).len()==v.len(),sum(deposit(v,i,a))==sum(v)+a, decreases v.len() {
 if i==0 {assert(deposit(v,i,a).drop_first()==v.drop_first());}else{
  assert(deposit(v,i,a).drop_first()==deposit(v.drop_first(),(i-1) as nat,a));
  lemma_deposit(v.drop_first(),(i-1) as nat,a);
 }
}
pub proof fn lemma_seed_add(v:Seq<real>,ns:Seq<int>,ss:Seq<int>,a:real)
 requires v.len()==ns.len(),forall|i:int|0<=i<ss.len() ==> ns.contains(ss[i]),
 ensures seed_add(v,ns,ss,a).len()==v.len(),sum(seed_add(v,ns,ss,a))==sum(v)+(ss.len() as real)*a,
 decreases ss.len(),
{
 if ss.len()>0 {
  lemma_pos(ns,ss[0]);lemma_deposit(v,pos(ns,ss[0]),a);
  assert forall|i:int|0<=i<ss.drop_first().len() implies ns.contains(ss.drop_first()[i]) by {assert(ss.drop_first()[i]==ss[i+1]);}
  lemma_seed_add(deposit(v,pos(ns,ss[0]),a),ns,ss.drop_first(),a);
  let n=ss.len() as real; let t=ss.drop_first().len() as real;
  assert(t==n-1real);
  assert(a+t*a==n*a) by(nonlinear_arith) requires t==n-1real;
  assert(sum(seed_add(v,ns,ss,a))==sum(v)+a+t*a);
 } else {assert((ss.len() as real)*a==0real) by(nonlinear_arith) requires ss.len()==0;
 }
}
pub proof fn theorem_initial_uniform_mass(c:Context) requires closed(c), ensures initial(c).len()==c.nodes.len(),sum(initial(c))==1real {
 lemma_sum_zeros(c.nodes.len());lemma_seed_add(zeros(c.nodes.len()),c.nodes,c.seeds,1real/(c.seeds.len() as real));
 assert((c.seeds.len() as real)>0real);
 let n=c.seeds.len() as real;
 assert(n*(1real/n)==1real) by(nonlinear_arith) requires n>0real;
}
pub proof fn lemma_copies(h:Hop,n:nat) ensures copies(h,n).len()==n,forall|i:int|0<=i<n ==> copies(h,n)[i]==h, decreases n {
 if n>0 {lemma_copies(h,(n-1) as nat);assert forall|i:int|0<=i<n implies copies(h,n)[i]==h by {if i>0 {assert(copies(h,n)[i]==copies(h,(n-1) as nat)[i-1]);}}}
}
pub proof fn lemma_hops_unit(es:Seq<Edge>,g:int,u:int,ex:Seq<int>,rev:bool,w:real)
 requires !rev || w<=0real || w==1real,
 ensures forall|j:int|0<=j<hops(es,g,u,ex,rev,w).len() ==> hops(es,g,u,ex,rev,w)[j].weight==1real,
 decreases es.len(),
{
 if es.len()>0 {
  let e=es[0];let keep=e.graph==g && !ex.contains(e.pred);
  let f=if keep && e.src==u {copies(Hop{dst:e.dst,weight:1real},mult(e))}else{seq![]};
  let r=if keep && rev && w>0real && e.dst==u {copies(Hop{dst:e.src,weight:w},mult(e))}else{seq![]};
  let t=hops(es.drop_first(),g,u,ex,rev,w);
  lemma_copies(Hop{dst:e.dst,weight:1real},mult(e));lemma_copies(Hop{dst:e.src,weight:w},mult(e));
  lemma_hops_unit(es.drop_first(),g,u,ex,rev,w);
  assert forall|j:int|0<=j<(f+r+t).len() implies (f+r+t)[j].weight==1real by {
   if j<f.len(){assert((f+r+t)[j]==f[j]);}else if j<f.len()+r.len(){assert((f+r+t)[j]==r[j-f.len()]);}else{assert((f+r+t)[j]==t[j-f.len()-r.len()]);}
  }
 }
}
pub proof fn lemma_ship(v:Seq<real>,ns:Seq<int>,hs:Seq<Hop>,share:real)
 requires v.len()==ns.len(),forall|i:int|0<=i<hs.len() ==> ns.contains(hs[i].dst) && hs[i].weight==1real,
 ensures ship(v,ns,hs,share).len()==v.len(),sum(ship(v,ns,hs,share))==sum(v)+(hs.len() as real)*share,
 decreases hs.len(),
{
 if hs.len()>0 {
  lemma_pos(ns,hs[0].dst);lemma_deposit(v,pos(ns,hs[0].dst),share*hs[0].weight);
  assert forall|i:int|0<=i<hs.drop_first().len() implies ns.contains(hs.drop_first()[i].dst) && hs.drop_first()[i].weight==1real by {assert(hs.drop_first()[i]==hs[i+1]);}
  lemma_ship(deposit(v,pos(ns,hs[0].dst),share*hs[0].weight),ns,hs.drop_first(),share);
  let n=hs.len() as real;let t=hs.drop_first().len() as real;assert(t==n-1real);
  assert(share+t*share==n*share) by(nonlinear_arith) requires t==n-1real;
  assert(sum(ship(v,ns,hs,share))==sum(v)+share+t*share);
 }else{assert((hs.len() as real)*share==0real) by(nonlinear_arith) requires hs.len()==0;}
}
pub proof fn lemma_scatter(c:Context,old:Seq<real>,i:nat,out:Seq<real>,dang:real)
 requires closed(c),unit(c),old.len()==c.nodes.len(),out.len()==c.nodes.len(),i<=c.nodes.len(),
 ensures scatter(c,old,i,out,dang).values.len()==out.len(),
  sum(scatter(c,old,i,out,dang).values)+c.alpha*scatter(c,old,i,out,dang).dangling
   ==sum(out)+c.alpha*dang+c.alpha*sum(old.subrange(i as int,old.len() as int)),
 decreases c.nodes.len()-i,
{
 if i<c.nodes.len(){
  let hs=hops(c.edges,c.graph,c.nodes[i as int],c.excluded,c.reverse,c.weight);
  let rest=old.subrange((i+1) as int,old.len() as int);let tail=old.subrange(i as int,old.len() as int);
  assert(tail.drop_first()==rest);assert(sum(tail)==old[i as int]+sum(rest));
  if hs.len()==0 {
   lemma_scatter(c,old,i+1,out,dang+old[i as int]);
  }else{
   lemma_hops_unit(c.edges,c.graph,c.nodes[i as int],c.excluded,c.reverse,c.weight);
   assert forall|j:int|0<=j<hs.len() implies c.nodes.contains(hs[j].dst) && hs[j].weight==1real by {}
   let share=c.alpha*old[i as int]/(hs.len() as real);
   lemma_ship(out,c.nodes,hs,share);
   let n=hs.len() as real;let a=c.alpha;let v=old[i as int];
   assert(n*share==a*v) by(nonlinear_arith) requires n>0real,share==a*v/n;
   lemma_scatter(c,old,i+1,ship(out,c.nodes,hs,share),dang);
  }
  let a=c.alpha;let d=dang;let v=old[i as int];let t=sum(rest);
  assert(a*(d+v)+a*t==a*d+a*(v+t)) by(nonlinear_arith);
  assert(a*v+a*t==a*(v+t)) by(nonlinear_arith);
 }
}
pub proof fn theorem_step_mass_from_raw_outgoing(c:Context,old:Seq<real>)
 requires closed(c),unit(c),old.len()==c.nodes.len(),
 ensures next(c,old).len()==c.nodes.len(),sum(next(c,old))==1real-c.alpha+c.alpha*sum(old),
{
 let z=zeros(c.nodes.len());lemma_sum_zeros(c.nodes.len());lemma_scatter(c,old,0,z,0real);
 let s=scatter(c,old,0,z,0real);assert(old.subrange(0,old.len() as int)==old);
 let restart=((1real-c.alpha)+c.alpha*s.dangling)/(c.seeds.len() as real);
 lemma_seed_add(s.values,c.nodes,c.seeds,restart);
 let n=c.seeds.len() as real;let a=c.alpha;let d=s.dangling;
 assert(n*restart==(1real-a)+a*d) by(nonlinear_arith) requires n>0real,restart==((1real-a)+a*d)/n;
}
pub open spec fn abs(x:real)->real {if x<0real{-x}else{x}}
pub open spec fn delta(a:Seq<real>,b:Seq<real>)->real decreases a.len() {if a.len()==0{0real}else{abs(a[0]-b[0])+delta(a.drop_first(),b.drop_first())}}
pub open spec fn held(a:Seq<real>)->nat decreases a.len() {if a.len()==0{0}else{(if a[0]!=0real{1nat}else{0nat})+held(a.drop_first())}}
pub struct Walk {pub ranks:Seq<real>,pub iterations:nat,pub change:real,pub holding:nat}
pub open spec fn iterate(c:Context,old:Seq<real>,left:nat,tol:real)->Walk decreases left {
 if left==0 {Walk{ranks:old,iterations:0,change:0real,holding:held(old)}}else{
  let nr=next(c,old);let d=delta(nr,old);let h=held(nr);
  if d<(h as real)*tol || left==1 {Walk{ranks:nr,iterations:1,change:d,holding:h}}else{
   let r=iterate(c,nr,(left-1) as nat,tol);Walk{iterations:1+r.iterations,..r}
  }
 }
}
pub proof fn theorem_iterated_mass(c:Context,old:Seq<real>,left:nat,tol:real)
 requires closed(c),unit(c),old.len()==c.nodes.len(),sum(old)==1real,
 ensures iterate(c,old,left,tol).ranks.len()==c.nodes.len(),sum(iterate(c,old,left,tol).ranks)==1real,
 decreases left,
{
 if left>0 {theorem_step_mass_from_raw_outgoing(c,old);assert(sum(next(c,old))==1real) by(nonlinear_arith) requires sum(next(c,old))==1real-c.alpha+c.alpha*sum(old),sum(old)==1real;
  if !(delta(next(c,old),old)<(held(next(c,old)) as real)*tol || left==1){theorem_iterated_mass(c,next(c,old),(left-1) as nat,tol);}
 }
}
pub proof fn theorem_iteration_cap(c:Context,old:Seq<real>,left:nat,tol:real)
 ensures iterate(c,old,left,tol).iterations<=left,left>0 ==> iterate(c,old,left,tol).iterations>0,
 decreases left,
{if left>1 && !(delta(next(c,old),old)<(held(next(c,old)) as real)*tol){theorem_iteration_cap(c,next(c,old),(left-1) as nat,tol);}}
pub proof fn lemma_prepend_contains<A>(x:A,t:Seq<A>,v:A)
 ensures (seq![x]+t).contains(v) <==> x==v || t.contains(v),
{
 let z=seq![x]+t;
 if z.contains(v){let k=choose|k:int|0<=k<z.len() && z[k]==v;if k>0{assert(t[k-1]==v);}}
 if x==v{assert(z[0]==v);}else if t.contains(v){let k=choose|k:int|0<=k<t.len() && t[k]==v;assert(z[k+1]==v);}
}
pub proof fn theorem_valid_seed_set(raw:Seq<int>,ns:Seq<int>,id:int)
 ensures valid_seeds(raw,ns).contains(id) <==> raw.contains(id) && ns.contains(id),valid_seeds(raw,ns).no_duplicates(),
 decreases raw.len(),
{
 if raw.len()>0 {
  let t=valid_seeds(raw.drop_first(),ns);theorem_valid_seed_set(raw.drop_first(),ns,id);theorem_valid_seed_set(raw.drop_first(),ns,raw[0]);
  assert(raw==seq![raw[0]]+raw.drop_first());lemma_prepend_contains(raw[0],raw.drop_first(),id);lemma_prepend_contains(raw[0],t,id);
  if ns.contains(raw[0]) && !t.contains(raw[0]) {
   assert((seq![raw[0]]+t).no_duplicates()) by {
    assert forall|i:int,j:int|0<=i<j<(seq![raw[0]]+t).len() implies (seq![raw[0]]+t)[i]!=(seq![raw[0]]+t)[j] by {
     if i==0 {assert(t.contains(t[j-1]));}else{assert(t[i-1]!=t[j-1]);}
    }
   }
  }
 }
}
pub open spec fn prepare(raw:Seq<Node>,es:Seq<Edge>,ss:Seq<int>,g:int,ex:Seq<int>,rev:bool,w:real,a:real)->Context {
 let ns=scoped(raw,g);Context{nodes:ns,edges:es,graph:g,seeds:valid_seeds(ss,ns),excluded:ex,reverse:rev,weight:w,alpha:a}
}
pub proof fn theorem_scoped_members(raw:Seq<Node>,g:int,id:int)
 ensures scoped(raw,g).contains(id) <==> exists|i:int|0<=i<raw.len() && raw[i].graph==g && raw[i].id==id,
 decreases raw.len(),
{
 if raw.len()>0 {theorem_scoped_members(raw.drop_first(),g,id);
  lemma_prepend_contains(raw[0].id,scoped(raw.drop_first(),g),id);
  if scoped(raw,g).contains(id) && !(raw[0].graph==g && raw[0].id==id){
   let i=choose|i:int|0<=i<raw.drop_first().len() && raw.drop_first()[i].graph==g && raw.drop_first()[i].id==id;
   assert(raw[i+1].graph==g && raw[i+1].id==id);
  }
  if exists|i:int|0<=i<raw.len() && raw[i].graph==g && raw[i].id==id {
   let i=choose|i:int|0<=i<raw.len() && raw[i].graph==g && raw[i].id==id;
   if i>0 {assert(raw.drop_first()[i-1].graph==g && raw.drop_first()[i-1].id==id);}
  }
 }
}
pub proof fn lemma_hops_closed(es:Seq<Edge>,g:int,u:int,ns:Seq<int>,ex:Seq<int>,rev:bool,w:real)
 requires forall|i:int|0<=i<es.len() && es[i].graph==g && !ex.contains(es[i].pred) ==> ns.contains(es[i].src) && ns.contains(es[i].dst),
 ensures forall|j:int|0<=j<hops(es,g,u,ex,rev,w).len() ==> ns.contains(hops(es,g,u,ex,rev,w)[j].dst),
 decreases es.len(),
{
 if es.len()>0 {
  let e=es[0];let keep=e.graph==g && !ex.contains(e.pred);
  let f=if keep && e.src==u {copies(Hop{dst:e.dst,weight:1real},mult(e))}else{seq![]};
  let r=if keep && rev && w>0real && e.dst==u {copies(Hop{dst:e.src,weight:w},mult(e))}else{seq![]};
  let t=hops(es.drop_first(),g,u,ex,rev,w);
  assert forall|i:int|0<=i<es.drop_first().len() && es.drop_first()[i].graph==g && !ex.contains(es.drop_first()[i].pred) implies ns.contains(es.drop_first()[i].src) && ns.contains(es.drop_first()[i].dst) by {assert(es.drop_first()[i]==es[i+1]);}
  lemma_hops_closed(es.drop_first(),g,u,ns,ex,rev,w);
  lemma_copies(Hop{dst:e.dst,weight:1real},mult(e));lemma_copies(Hop{dst:e.src,weight:w},mult(e));
  assert forall|j:int|0<=j<(f+r+t).len() implies ns.contains((f+r+t)[j].dst) by {
   if j<f.len(){assert((f+r+t)[j]==f[j]);}else if j<f.len()+r.len(){assert((f+r+t)[j]==r[j-f.len()]);}else{assert((f+r+t)[j]==t[j-f.len()-r.len()]);}
  }
 }
}
pub proof fn theorem_raw_preparation_closed(raw:Seq<Node>,es:Seq<Edge>,ss:Seq<int>,g:int,ex:Seq<int>,rev:bool,w:real,a:real)
 requires scoped(raw,g).no_duplicates(),valid_seeds(ss,scoped(raw,g)).len()>0,
  forall|i:int|0<=i<es.len() && es[i].graph==g && !ex.contains(es[i].pred) ==> scoped(raw,g).contains(es[i].src) && scoped(raw,g).contains(es[i].dst),
 ensures closed(prepare(raw,es,ss,g,ex,rev,w,a)),
{
 let c=prepare(raw,es,ss,g,ex,rev,w,a);theorem_valid_seed_set(ss,c.nodes,0);
 assert forall|i:int|0<=i<c.seeds.len() implies c.nodes.contains(c.seeds[i]) by {theorem_valid_seed_set(ss,c.nodes,c.seeds[i]);}
 assert forall|i:int,j:int|0<=i<c.nodes.len() && 0<=j<hops(c.edges,c.graph,c.nodes[i],c.excluded,c.reverse,c.weight).len() implies c.nodes.contains(hops(c.edges,c.graph,c.nodes[i],c.excluded,c.reverse,c.weight)[j].dst) by {lemma_hops_closed(es,g,c.nodes[i],c.nodes,ex,rev,w);}
}
pub proof fn theorem_raw_walk_mass(raw:Seq<Node>,es:Seq<Edge>,ss:Seq<int>,g:int,left:nat,tol:real,a:real)
 requires scoped(raw,g).no_duplicates(),valid_seeds(ss,scoped(raw,g)).len()>0,0real<a<1real,left>=1,
  forall|i:int|0<=i<es.len() && es[i].graph==g ==> scoped(raw,g).contains(es[i].src) && scoped(raw,g).contains(es[i].dst),
 ensures ({let c=prepare(raw,es,ss,g,seq![],false,1real,a);sum(iterate(c,initial(c),left,tol).ranks)==1real && iterate(c,initial(c),left,tol).iterations<=left}),
{
 let c=prepare(raw,es,ss,g,seq![],false,1real,a);
 theorem_raw_preparation_closed(raw,es,ss,g,seq![],false,1real,a);theorem_initial_uniform_mass(c);theorem_iterated_mass(c,initial(c),left,tol);theorem_iteration_cap(c,initial(c),left,tol);
}
// Ideal decimal key. Binary/native half-boundary correspondence is not proved.
pub open spec fn decimal12(x:real)->int {
 let y=x*1000000000000real;let f=y.floor();
 if y-(f as real)<0.5real{f}else if y-(f as real)>0.5real{f+1}else if f%2==0{f}else{f+1}
}
pub struct Row {pub id:int,pub score:real}
pub open spec fn before(a:Row,b:Row)->bool {decimal12(a.score)>decimal12(b.score) || (decimal12(a.score)==decimal12(b.score) && a.id<=b.id)}
pub open spec fn insert(r:Row,rs:Seq<Row>)->Seq<Row> decreases rs.len() {if rs.len()==0{seq![r]}else if before(r,rs[0]){seq![r]+rs}else{seq![rs[0]]+insert(r,rs.drop_first())}}
pub open spec fn rank(rs:Seq<Row>)->Seq<Row> decreases rs.len() {if rs.len()==0{rs}else{insert(rs[0],rank(rs.drop_first()))}}
pub open spec fn rows(ns:Seq<int>,scores:Seq<real>)->Seq<Row> decreases ns.len() {if ns.len()==0{seq![]}else{seq![Row{id:ns[0],score:scores[0]}]+rows(ns.drop_first(),scores.drop_first())}}
pub open spec fn sparse(rs:Seq<Row>)->Seq<Row> decreases rs.len() {if rs.len()==0{rs}else{let t=sparse(rs.drop_first());if rs[0].score!=0real{seq![rs[0]]+t}else{t}}}
pub open spec fn has(rs:Seq<Row>,id:int)->bool decreases rs.len() {rs.len()>0 && (rs[0].id==id || has(rs.drop_first(),id))}
pub open spec fn missing(ns:Seq<int>,rs:Seq<Row>)->Seq<Row> decreases ns.len() {if ns.len()==0{seq![]}else{let t=missing(ns.drop_first(),rs);if has(rs,ns[0]){t}else{seq![Row{id:ns[0],score:0real}]+t}}}
pub open spec fn cut(rs:Seq<Row>,limit:int)->Seq<Row> {if limit>0 && limit<rs.len(){rs.take(limit)}else{rs}}
pub open spec fn full_reader(ns:Seq<int>,scores:Seq<real>,top:int)->Seq<Row> {cut(rank(rows(ns,scores)),top)}
pub open spec fn effective_limit(top:int,cap:int)->int {if top>0{top}else{cap}}
pub open spec fn fast_reader(ns:Seq<int>,scores:Seq<real>,producer_cap:int,top:int,cap:int)->Seq<Row> {
 let scored=rank(cut(rank(sparse(rows(ns,scores))),producer_cap));let limit=effective_limit(top,cap);
 if scored.len()==0{seq![]}else{cut(scored+rank(missing(ns,scored)),limit)}
}
pub open spec fn ordered(rs:Seq<Row>)->bool {forall|i:int,j:int|0<=i<j<rs.len() ==> before(rs[i],rs[j])}
pub proof fn lemma_order_transitive(a:Row,b:Row,c:Row) requires before(a,b),before(b,c), ensures before(a,c), {}
pub proof fn lemma_insert_order(r:Row,rs:Seq<Row>) requires ordered(rs), ensures ordered(insert(r,rs)),insert(r,rs).len()==rs.len()+1, decreases rs.len() {
 if rs.len()>0 {
  if !before(r,rs[0]) {lemma_insert_order(r,rs.drop_first());}
  assert forall|i:int,j:int|0<=i<j<insert(r,rs).len() implies before(insert(r,rs)[i],insert(r,rs)[j]) by {
   if before(r,rs[0]) {
    if i==0 {if j>1{lemma_order_transitive(r,rs[0],rs[j-1]);}}else{assert(before(rs[i-1],rs[j-1]));}
   }else{
    if i==0 {if insert(r,rs.drop_first())[j-1]==r {assert(before(rs[0],r));}else{
     // Membership of the insertion is established below separately.
     let v=insert(r,rs.drop_first())[j-1];
     lemma_insert_member(r,rs.drop_first(),v);
     let k=choose|k:int|0<=k<rs.drop_first().len() && rs.drop_first()[k]==v;
     assert(before(rs[0],rs[k+1]));
    }}else{assert(before(insert(r,rs.drop_first())[i-1],insert(r,rs.drop_first())[j-1]));}
   }
  }
 }
}
pub proof fn lemma_insert_member(r:Row,rs:Seq<Row>,v:Row)
 ensures insert(r,rs).contains(v) <==> v==r || rs.contains(v), decreases rs.len(),
{lemma_prepend_contains(r,seq![],v);if rs.len()>0{lemma_insert_member(r,rs.drop_first(),v);
 assert(rs==seq![rs[0]]+rs.drop_first());lemma_prepend_contains(rs[0],rs.drop_first(),v);lemma_prepend_contains(r,rs,v);lemma_prepend_contains(rs[0],insert(r,rs.drop_first()),v);}}
pub proof fn theorem_rank_order(rs:Seq<Row>) ensures ordered(rank(rs)),rank(rs).len()==rs.len(), decreases rs.len() {
 if rs.len()>0 {theorem_rank_order(rs.drop_first());lemma_insert_order(rs[0],rank(rs.drop_first()));}
}
pub proof fn theorem_cap_is_actual_prefix(rs:Seq<Row>,limit:int)
 ensures limit>0 && limit<rs.len() ==> cut(rs,limit)==rs.take(limit),cut(rs,limit).len()<=rs.len(),
 {}
pub proof fn lemma_div_one(x:real) ensures x/1real==x, {assert(x/1real==x) by(nonlinear_arith);}
pub open spec fn tiny(a:real)->Context {prepare(seq![Node{graph:0,id:0},Node{graph:0,id:1},Node{graph:0,id:2}],seq![Edge{graph:0,src:1,pred:7,dst:2,count:None}],seq![1],0,seq![],false,1real,a)}
pub proof fn lemma_tiny_recurrence(a:real)
 ensures initial(tiny(a))==seq![0real,1real,0real],next(tiny(a),initial(tiny(a)))==seq![0real,1real-a,a],
{
 reveal_with_fuel(scoped,4);reveal_with_fuel(valid_seeds,3);reveal_with_fuel(seed_add,3);reveal_with_fuel(pos,4);reveal_with_fuel(hops,3);reveal_with_fuel(copies,3);reveal_with_fuel(scatter,5);reveal_with_fuel(ship,3);
 let c=tiny(a);assert(c.nodes==seq![0,1,2]);assert(c.nodes[1]==1);assert(c.nodes.contains(1));assert(c.seeds==seq![1]);
 assert(zeros(3)==seq![0real,0real,0real]);assert(pos(c.nodes,1)==1);
 let v=initial(c);
 lemma_div_one(1real);assert(1real/(c.seeds.len() as real)==1real);
 assert(deposit(zeros(3),1,1real)==seq![0real,1real,0real]);
 assert(seed_add(zeros(3),c.nodes,c.seeds,1real)==deposit(zeros(3),1,1real));
 assert(v==seq![0real,1real,0real]);
 lemma_div_one(a*0real);lemma_div_one(a*1real);lemma_div_one(1real-a);
 assert(next(tiny(a),v)==seq![0real,1real-a,a]);
}
pub proof fn lemma_rank_identity(rs:Seq<Row>) requires ordered(rs), ensures rank(rs)==rs, decreases rs.len(), {
 if rs.len()>0{lemma_rank_identity(rs.drop_first());assert(insert(rs[0],rs.drop_first())==rs);}
}
pub proof fn lemma_tiny_readers(a:real,b:real)
 requires a>0real,b>0real,decimal12(a)>0,decimal12(b)==0,
 ensures full_reader(seq![0,1,2],seq![0real,a,b],2)==seq![Row{id:1,score:a},Row{id:0,score:0real}],
  fast_reader(seq![0,1,2],seq![0real,a,b],1000,2,1000)==seq![Row{id:1,score:a},Row{id:2,score:b}],
{
 reveal_with_fuel(rows,5);reveal_with_fuel(sparse,5);reveal_with_fuel(rank,5);reveal_with_fuel(insert,5);reveal_with_fuel(missing,5);reveal_with_fuel(has,5);
 assert(decimal12(0real)==0);
}
pub proof fn theorem_recurrence_tiny_zero_cut_differs()
 ensures ({let c=tiny(0.0000000000001real);let r=iterate(c,initial(c),1,0real).ranks;
  full_reader(c.nodes,r,2)==seq![Row{id:1,score:0.9999999999999real},Row{id:0,score:0real}]
  && fast_reader(c.nodes,r,1000,2,1000)==seq![Row{id:1,score:0.9999999999999real},Row{id:2,score:0.0000000000001real}]}),
{
 lemma_tiny_recurrence(0.0000000000001real);reveal_with_fuel(scoped,4);
 assert(decimal12(0.9999999999999real)==1000000000000);assert(decimal12(0.0000000000001real)==0);
 lemma_tiny_readers(0.9999999999999real,0.0000000000001real);
 let c=tiny(0.0000000000001real);assert(c.nodes==seq![0,1,2]);
 assert(iterate(c,initial(c),1,0real).ranks==next(c,initial(c)));
 assert(next(c,initial(c))==seq![0real,0.9999999999999real,0.0000000000001real]);
}
pub proof fn lemma_positive_readers(a:real,b:real,top:int)
 requires a>0real,b>0real,decimal12(a)>=decimal12(b)>0,
 ensures full_reader(seq![0,1,2],seq![0real,a,b],top)==fast_reader(seq![0,1,2],seq![0real,a,b],1000,top,1000),
{
 let z=Row{id:0,score:0real};let x=Row{id:1,score:a};let y=Row{id:2,score:b};
 assert(decimal12(0real)==0);assert(ordered(seq![x,y]));lemma_rank_identity(seq![x,y]);
 reveal_with_fuel(rows,4);reveal_with_fuel(sparse,4);reveal_with_fuel(missing,4);reveal_with_fuel(has,4);
 assert(rows(seq![0,1,2],seq![0real,a,b])==seq![z,x,y]);assert(sparse(seq![z,x,y])==seq![x,y]);
 reveal_with_fuel(insert,4);reveal_with_fuel(rank,2);
 assert((seq![z,x,y]).drop_first()==seq![x,y]);
 assert(rank(seq![z,x,y])==insert(z,seq![x,y]));
 assert(!before(z,x) && !before(z,y));assert(insert(z,seq![y])==seq![y,z]);
 assert(insert(z,seq![x,y])==seq![x,y,z]);
 assert(rank(seq![z,x,y])==seq![x,y,z]);
 assert(cut(rank(seq![x,y]),1000)==seq![x,y]);lemma_rank_identity(seq![x,y]);
 assert(missing(seq![0,1,2],seq![x,y])==seq![z]);lemma_rank_identity(seq![z]);
}
pub proof fn theorem_positive_rank_and_zeros_read_together()
 ensures ({let c=tiny(0.5real);let r=next(c,initial(c));full_reader(c.nodes,r,3)==fast_reader(c.nodes,r,1000,3,1000)}),
{lemma_tiny_recurrence(0.5real);reveal_with_fuel(scoped,4);assert(decimal12(0.5real)==500000000000);lemma_positive_readers(0.5real,0.5real,3);assert(tiny(0.5real).nodes==seq![0,1,2]);}
pub proof fn theorem_strict_held_change_decides(c:Context,old:Seq<real>,left:nat,tol:real)
 requires left>0,delta(next(c,old),old)<(held(next(c,old)) as real)*tol,
 ensures iterate(c,old,left,tol).iterations==1,iterate(c,old,left,tol).ranks==next(c,old),
{}
pub proof fn theorem_zero_tolerance_does_not_stop_on_zero_change(c:Context,old:Seq<real>,left:nat)
 requires left>1,next(c,old)==old,
 ensures iterate(c,old,left,0real).iterations==left,
 decreases left,
{
 lemma_delta_self(old);assert((held(old) as real)*0real==0real) by(nonlinear_arith);reveal_with_fuel(iterate,2);if left>2{theorem_zero_tolerance_does_not_stop_on_zero_change(c,old,(left-1) as nat);}
}
pub proof fn lemma_delta_self(v:Seq<real>) ensures delta(v,v)==0real, decreases v.len(), {if v.len()>0{lemma_delta_self(v.drop_first());}}
pub open spec fn reverse_fixture(w:real)->Context {Context{nodes:seq![1,2],edges:seq![Edge{graph:0,src:1,pred:7,dst:2,count:None}],graph:0,seeds:seq![2],excluded:seq![],reverse:true,weight:w,alpha:0.5real}}
pub proof fn theorem_reverse_weight_scales_contribution_only(w:real)
 requires w>0real,
 ensures next(reverse_fixture(w),seq![0real,1real])==seq![0.5real*w,0.5real],sum(next(reverse_fixture(w),seq![0real,1real]))==0.5real*w+0.5real,
{
 reveal_with_fuel(hops,3);reveal_with_fuel(copies,3);reveal_with_fuel(scatter,4);reveal_with_fuel(ship,3);reveal_with_fuel(seed_add,3);reveal_with_fuel(pos,3);reveal_with_fuel(sum,3);
 assert(zeros(2)==seq![0real,0real]);
 let c=reverse_fixture(w);lemma_div_one(0real);lemma_div_one(0.5real);
 assert(hops(c.edges,0,1,seq![],true,w)==seq![Hop{dst:2,weight:1real}]);
 assert(hops(c.edges,0,2,seq![],true,w)==seq![Hop{dst:1,weight:w}]);
 assert(ship(zeros(2),c.nodes,hops(c.edges,0,1,seq![],true,w),0real)==zeros(2));
 assert(ship(zeros(2),c.nodes,hops(c.edges,0,2,seq![],true,w),0.5real)==seq![0.5real*w,0real]);
 assert(scatter(c,seq![0real,1real],0,zeros(2),0real)==Sweep{values:seq![0.5real*w,0real],dangling:0real});
}
pub proof fn theorem_reverse_zero_uses_dangling_restart()
 ensures next(reverse_fixture(0real),seq![0real,1real])==seq![0real,1real],
{
 reveal_with_fuel(hops,3);reveal_with_fuel(copies,3);reveal_with_fuel(scatter,4);reveal_with_fuel(ship,3);reveal_with_fuel(seed_add,3);reveal_with_fuel(pos,3);lemma_div_one(0real);lemma_div_one(1real);assert(zeros(2)==seq![0real,0real]);
 let c=reverse_fixture(0real);assert(pos(c.nodes,2)==1);
 assert(hops(c.edges,0,1,seq![],true,0real)==seq![Hop{dst:2,weight:1real}]);assert(hops(c.edges,0,2,seq![],true,0real)==seq![]);
 assert(ship(zeros(2),c.nodes,hops(c.edges,0,1,seq![],true,0real),0real)==zeros(2));
 assert(scatter(c,seq![0real,1real],1,zeros(2),0real)==Sweep{values:zeros(2),dangling:1real});
 assert(scatter(c,seq![0real,1real],0,zeros(2),0real)==Sweep{values:zeros(2),dangling:1real});
 assert(((1real-0.5real)+0.5real*1real)/1real==1real);
}
pub proof fn theorem_multiplicity_divisor_not_distinct_neighbors()
 ensures hops(seq![Edge{graph:0,src:1,pred:7,dst:2,count:Some(2)},Edge{graph:0,src:1,pred:8,dst:3,count:None}],0,1,seq![],false,1real).len()==3,
  hops(seq![Edge{graph:0,src:1,pred:7,dst:2,count:Some(2)},Edge{graph:0,src:1,pred:8,dst:3,count:None}],0,1,seq![7],false,1real).len()==1,
{assert(seq![7int][0]==7);assert(seq![7int].contains(7));reveal_with_fuel(hops,4);reveal_with_fuel(copies,4);}
pub proof fn theorem_other_graph_not_members_or_hops()
 ensures scoped(seq![Node{graph:0,id:1},Node{graph:9,id:2}],0)==seq![1],hops(seq![Edge{graph:9,src:1,pred:7,dst:2,count:Some(3)}],0,1,seq![],false,1real).len()==0,
{reveal_with_fuel(scoped,3);reveal_with_fuel(hops,3);}
pub proof fn theorem_empty_scores_do_not_invent_zero_nodes(ns:Seq<int>)
 ensures fast_reader(ns,zeros(ns.len()),1000,0,1000).len()==0,
{lemma_zero_rows_sparse(ns);}
pub proof fn lemma_zero_rows_sparse(ns:Seq<int>) ensures sparse(rows(ns,zeros(ns.len()))).len()==0, decreases ns.len(), {
 if ns.len()>0{assert(zeros(ns.len())[0]==0real);assert(zeros(ns.len()).drop_first()==zeros((ns.len()-1) as nat));lemma_zero_rows_sparse(ns.drop_first());
 let tail=rows(ns.drop_first(),zeros((ns.len()-1) as nat));
 assert(rows(ns,zeros(ns.len()))==seq![Row{id:ns[0],score:0real}]+tail);
 reveal_with_fuel(sparse,2);assert((seq![Row{id:ns[0],score:0real}]+tail).drop_first()==tail);
 assert(sparse(seq![Row{id:ns[0],score:0real}]+tail)==sparse(tail));
 }else{assert(rows(ns,zeros(ns.len()))==seq![]);assert(sparse(seq![]).len()==0);}
}
pub open spec fn isolated3()->Context {prepare(seq![Node{graph:0,id:1},Node{graph:0,id:2},Node{graph:0,id:3}],seq![],seq![1,2,3],0,seq![],false,1real,0.5real)}
pub proof fn lemma_isolated3_recurrence()
 ensures initial(isolated3())==seq![1real/3real,1real/3real,1real/3real],next(isolated3(),initial(isolated3()))==initial(isolated3()),
{
 let c=isolated3();let v=1real/3real;
 reveal_with_fuel(scoped,4);reveal_with_fuel(valid_seeds,4);reveal_with_fuel(seed_add,5);reveal_with_fuel(pos,4);reveal_with_fuel(scatter,5);
 assert(c.nodes==seq![1,2,3]);assert(c.nodes[0]==1 && c.nodes[1]==2 && c.nodes[2]==3);
 assert(c.nodes.contains(1) && c.nodes.contains(2) && c.nodes.contains(3));assert(c.seeds==seq![1,2,3]);
 assert(zeros(3)==seq![0real,0real,0real]);assert(initial(c)==seq![v,v,v]);
 assert(3real*v==1real) by(nonlinear_arith) requires v==1real/3real;
 assert(scatter(c,initial(c),0,zeros(3),0real)==Sweep{values:zeros(3),dangling:1real});
 assert(((1real-0.5real)+0.5real*1real)/3real==v) by(nonlinear_arith) requires v==1real/3real;
}
pub proof fn lemma_capped_positive_row_becomes_zero(v:real)
 requires v>0real,
 ensures fast_reader(seq![1,2,3],seq![v,v,v],2,3,2)==seq![Row{id:1,score:v},Row{id:2,score:v},Row{id:3,score:0real}],
{
 let x=Row{id:1,score:v};let y=Row{id:2,score:v};let z=Row{id:3,score:v};let zero=Row{id:3,score:0real};
 reveal_with_fuel(rows,4);reveal_with_fuel(sparse,4);reveal_with_fuel(missing,4);reveal_with_fuel(has,4);
 assert(ordered(seq![x,y,z]));lemma_rank_identity(seq![x,y,z]);assert(sparse(seq![x,y,z])==seq![x,y,z]);
 assert(cut(seq![x,y,z],2)==seq![x,y]);assert(ordered(seq![x,y]));lemma_rank_identity(seq![x,y]);
 assert(missing(seq![1,2,3],seq![x,y])==seq![zero]);lemma_rank_identity(seq![zero]);
}
pub proof fn theorem_recurrence_cap_fabricates_zero()
 ensures ({let c=isolated3();let r=iterate(c,initial(c),1,0real).ranks;
  r[2]==1real/3real && fast_reader(c.nodes,r,2,3,2)[2]==Row{id:3,score:0real}}),
{
 lemma_isolated3_recurrence();let v=1real/3real;assert(v>0real) by(nonlinear_arith) requires v==1real/3real;lemma_capped_positive_row_becomes_zero(v);reveal_with_fuel(scoped,4);
 let c=isolated3();assert(c.nodes==seq![1,2,3]);assert(iterate(c,initial(c),1,0real).ranks==seq![v,v,v]);
}
pub proof fn lemma_cut_order(rs:Seq<Row>,limit:int) requires ordered(rs), ensures ordered(cut(rs,limit)), {
 assert forall|i:int,j:int|0<=i<j<cut(rs,limit).len() implies before(cut(rs,limit)[i],cut(rs,limit)[j]) by {
  assert(cut(rs,limit)[i]==rs[i] && cut(rs,limit)[j]==rs[j]);
 }
}
pub proof fn theorem_full_reader_ordered(ns:Seq<int>,scores:Seq<real>,top:int)
 requires ns.len()==scores.len(),ensures ordered(full_reader(ns,scores,top)),
{theorem_rank_order(rows(ns,scores));lemma_cut_order(rank(rows(ns,scores)),top);}
pub struct Request {pub graph:int,pub seeds:Seq<int>,pub alpha:real,pub iterations:int,pub tolerance:real,pub reverse:bool,pub weight:real,pub excluded:Option<Seq<int>>,pub top:int}
pub enum Reader {Fast,Fallback}
pub enum Answer {Refused,Empty,Rows{values:Seq<Row>,iterations:nat}}
pub open spec fn source_limit(q:Request)->int {if q.excluded.is_some(){if q.top>0{q.top}else{0}}else{1000}}
pub open spec fn source_context(raw:Seq<Node>,es:Seq<Edge>,q:Request)->Context {prepare(raw,es,q.seeds,q.graph,q.excluded.unwrap_or(seq![]),q.reverse,q.weight,q.alpha)}
pub open spec fn public(raw:Seq<Node>,es:Seq<Edge>,q:Request,reader:Reader)->Answer {
 if q.alpha<=0real || q.alpha>=1real || q.iterations<1 || q.seeds.len()==0 || q.weight<0real {Answer::Refused}else{
  let c=source_context(raw,es,q);
  if c.seeds.len()==0 {Answer::Empty}else{
   let r=iterate(c,initial(c),q.iterations as nat,q.tolerance);
   Answer::Rows{values:match reader{Reader::Fallback=>full_reader(c.nodes,r.ranks,q.top),Reader::Fast=>fast_reader(c.nodes,r.ranks,source_limit(q),q.top,if q.excluded.is_none(){1000}else{0})},iterations:r.iterations}
  }
 }
}
pub proof fn theorem_producer_limit_is_derived(q:Request)
 ensures q.excluded.is_none() ==> source_limit(q)==1000,q.excluded.is_some() && q.top>0 ==> source_limit(q)==q.top,
 q.excluded.is_some() && q.top<=0 ==> source_limit(q)==0,q.top>0 ==> effective_limit(q.top,1000)==q.top,
{}
pub proof fn theorem_refusal_precedes_walk(raw:Seq<Node>,es:Seq<Edge>,q:Request,r:Reader)
 requires q.alpha<=0real || q.alpha>=1real || q.iterations<1 || q.seeds.len()==0 || q.weight<0real,
 ensures public(raw,es,q,r)==Answer::Refused,
{}
pub proof fn theorem_no_valid_seed_is_empty(raw:Seq<Node>,es:Seq<Edge>,q:Request,r:Reader)
 requires 0real<q.alpha<1real,q.iterations>=1,q.seeds.len()>0,q.weight>=0real,source_context(raw,es,q).seeds.len()==0,
 ensures public(raw,es,q,r)==Answer::Empty,
{}
pub proof fn theorem_walk_request_stays_within_iteration_budget(raw:Seq<Node>,es:Seq<Edge>,q:Request,r:Reader)
 requires 0real<q.alpha<1real,q.iterations>=1,q.seeds.len()>0,q.weight>=0real,source_context(raw,es,q).seeds.len()>0,
 ensures match public(raw,es,q,r){Answer::Rows{values,iterations}=>1<=iterations<=q.iterations,_=>false},
{let c=source_context(raw,es,q);theorem_iteration_cap(c,initial(c),q.iterations as nat,q.tolerance);}
pub proof fn theorem_request_tiny_readers_differ()
 ensures ({let q=Request{graph:0,seeds:seq![1],alpha:0.0000000000001real,iterations:1,tolerance:0real,reverse:false,weight:1real,excluded:None,top:2};
 let raw=seq![Node{graph:0,id:0},Node{graph:0,id:1},Node{graph:0,id:2}];let es=seq![Edge{graph:0,src:1,pred:7,dst:2,count:None}];
 public(raw,es,q,Reader::Fast)!=public(raw,es,q,Reader::Fallback)}),
{
 let a=0.0000000000001real;theorem_recurrence_tiny_zero_cut_differs();
 let q=Request{graph:0,seeds:seq![1],alpha:a,iterations:1,tolerance:0real,reverse:false,weight:1real,excluded:None,top:2};
 let raw=seq![Node{graph:0,id:0},Node{graph:0,id:1},Node{graph:0,id:2}];let es=seq![Edge{graph:0,src:1,pred:7,dst:2,count:None}];
 assert(source_context(raw,es,q)==tiny(a));reveal_with_fuel(scoped,4);reveal_with_fuel(valid_seeds,3);assert(scoped(raw,0)[1]==1);assert(scoped(raw,0).contains(1));
}
pub proof fn theorem_above_zero_bucket_readers_agree()
 ensures ({let c=tiny(0.00000000001real);let r=iterate(c,initial(c),1,0real).ranks;
 full_reader(c.nodes,r,2)==fast_reader(c.nodes,r,1000,2,1000)}),
{
 lemma_tiny_recurrence(0.00000000001real);let a=0.99999999999real;let b=0.00000000001real;
 assert(decimal12(a)==999999999990);assert(decimal12(b)==10);lemma_positive_readers(a,b,2);
 let c=tiny(b);reveal_with_fuel(scoped,4);assert(c.nodes==seq![0,1,2]);

}
pub proof fn lemma_second_tiny_step()
 ensures next(tiny(0.5real),seq![0real,0.5real,0.5real])==seq![0real,0.75real,0.25real],
{
 let c=tiny(0.5real);reveal_with_fuel(scoped,4);reveal_with_fuel(valid_seeds,3);reveal_with_fuel(seed_add,3);reveal_with_fuel(pos,4);reveal_with_fuel(hops,3);reveal_with_fuel(copies,3);reveal_with_fuel(scatter,5);reveal_with_fuel(ship,3);
 assert(c.nodes[1]==1);assert(c.nodes.contains(1));assert(c.seeds==seq![1]);assert(zeros(3)==seq![0real,0real,0real]);lemma_div_one(0real);lemma_div_one(0.25real);lemma_div_one(0.75real);
 assert(c.nodes==seq![0,1,2]);
 assert(hops(c.edges,0,0,seq![],false,1real)==seq![]);assert(hops(c.edges,0,1,seq![],false,1real)==seq![Hop{dst:2,weight:1real}]);assert(hops(c.edges,0,2,seq![],false,1real)==seq![]);
 assert(pos(c.nodes,2)==2);assert(ship(zeros(3),c.nodes,seq![Hop{dst:2,weight:1real}],0.25real)==seq![0real,0real,0.25real]);
 assert(scatter(c,seq![0real,0.5real,0.5real],0,zeros(3),0real)==Sweep{values:seq![0real,0real,0.25real],dangling:0.5real});
}
pub proof fn theorem_held_zero_node_does_not_inflate_stop_threshold()
 ensures iterate(tiny(0.5real),initial(tiny(0.5real)),5,0.4real).iterations==2,
{
 lemma_tiny_recurrence(0.5real);lemma_second_tiny_step();reveal_with_fuel(delta,5);reveal_with_fuel(held,5);reveal_with_fuel(iterate,2);
 assert(delta(seq![0real,0.5real,0.5real],seq![0real,1real,0real])==1real);assert(held(seq![0real,0.5real,0.5real])==2);
 assert(delta(seq![0real,0.75real,0.25real],seq![0real,0.5real,0.5real])==0.5real);assert(held(seq![0real,0.75real,0.25real])==2);
}
pub proof fn lemma_seed_add_monotone(v:Seq<real>,ns:Seq<int>,ss:Seq<int>,a:real,j:int)
 requires v.len()==ns.len(),0<=j<v.len(),a>=0real,forall|i:int|0<=i<ss.len() ==> ns.contains(ss[i]),
 ensures seed_add(v,ns,ss,a).len()==v.len(),seed_add(v,ns,ss,a)[j]>=v[j],
 decreases ss.len(),
{
 if ss.len()>0 {
  lemma_pos(ns,ss[0]);lemma_deposit(v,pos(ns,ss[0]),a);let v1=deposit(v,pos(ns,ss[0]),a);assert(v1[j]>=v[j]);
  assert forall|i:int|0<=i<ss.drop_first().len() implies ns.contains(ss.drop_first()[i]) by {assert(ss.drop_first()[i]==ss[i+1]);}
  lemma_seed_add_monotone(v1,ns,ss.drop_first(),a,j);
 }
}
pub proof fn lemma_seed_positive(v:Seq<real>,ns:Seq<int>,ss:Seq<int>,a:real,id:int)
 requires v.len()==ns.len(),a>0real,ss.contains(id),forall|i:int|0<=i<ss.len() ==> ns.contains(ss[i]),ns.contains(id),v[pos(ns,id) as int]>=0real,
 ensures seed_add(v,ns,ss,a)[pos(ns,id) as int]>0real,
 decreases ss.len(),
{
 lemma_pos(ns,id);lemma_pos(ns,ss[0]);lemma_deposit(v,pos(ns,ss[0]),a);let v1=deposit(v,pos(ns,ss[0]),a);let j=pos(ns,id) as int;
 assert forall|i:int|0<=i<ss.drop_first().len() implies ns.contains(ss.drop_first()[i]) by {assert(ss.drop_first()[i]==ss[i+1]);}
 if ss[0]==id {assert(v1[j]==v[j]+a);lemma_seed_add_monotone(v1,ns,ss.drop_first(),a,j);}else{
  assert(ss==seq![ss[0]]+ss.drop_first());lemma_prepend_contains(ss[0],ss.drop_first(),id);assert(v1[j]>=v[j]);
  lemma_seed_positive(v1,ns,ss.drop_first(),a,id);
 }
}
pub proof fn lemma_valid_seed_identity(ss:Seq<int>,ns:Seq<int>)
 requires ss.no_duplicates(),forall|i:int|0<=i<ss.len() ==> ns.contains(ss[i]),
 ensures valid_seeds(ss,ns)==ss,
 decreases ss.len(),
{
 if ss.len()>0 {
  assert forall|i:int|0<=i<ss.drop_first().len() implies ns.contains(ss.drop_first()[i]) by {assert(ss.drop_first()[i]==ss[i+1]);}
  lemma_valid_seed_identity(ss.drop_first(),ns);theorem_valid_seed_set(ss.drop_first(),ns,ss[0]);assert(!ss.drop_first().contains(ss[0]));assert(ss==seq![ss[0]]+ss.drop_first());
 }
}
pub proof fn lemma_scoped_map(ns:Seq<int>,g:int)
 ensures scoped(ns.map_values(|id:int|Node{graph:g,id}),g)==ns,
 decreases ns.len(),
{
 if ns.len()>0 {lemma_scoped_map(ns.drop_first(),g);assert(ns.map_values(|id:int|Node{graph:g,id}).drop_first()==ns.drop_first().map_values(|id:int|Node{graph:g,id}));assert(ns==seq![ns[0]]+ns.drop_first());}
}
pub proof fn lemma_empty_scatter(c:Context,old:Seq<real>,i:nat,out:Seq<real>,d:real)
 requires c.edges.len()==0,old.len()==c.nodes.len(),i<=old.len(),
 ensures scatter(c,old,i,out,d).values==out,scatter(c,old,i,out,d).dangling==d+sum(old.subrange(i as int,old.len() as int)),
 decreases old.len()-i,
{
 if i<old.len(){lemma_empty_scatter(c,old,i+1,out,d+old[i as int]);assert(old.subrange(i as int,old.len() as int).drop_first()==old.subrange((i+1) as int,old.len() as int));}
}
pub proof fn lemma_isolated_seed_scores_positive(ns:Seq<int>)
 requires ns.len()>0,ns.no_duplicates(),
 ensures ({let c=Context{nodes:ns,edges:seq![],graph:0,seeds:ns,excluded:seq![],reverse:false,weight:1real,alpha:0.5real};
 initial(c)==next(c,initial(c)) && initial(c).len()==ns.len() && forall|j:int|0<=j<ns.len() ==> initial(c)[j]>0real}),
{
 let c=Context{nodes:ns,edges:seq![],graph:0,seeds:ns,excluded:seq![],reverse:false,weight:1real,alpha:0.5real};
 assert forall|i:int|0<=i<ns.len() implies ns.contains(ns[i]) by {}
 assert(closed(c));theorem_initial_uniform_mass(c);let a=1real/(ns.len() as real);let n=ns.len() as real;
 assert(a>0real) by(nonlinear_arith) requires a==1real/n,n>0real;
 assert forall|j:int|0<=j<ns.len() implies initial(c)[j]>0real by {
  lemma_pos(ns,ns[j]);assert(pos(ns,ns[j])==j);assert(zeros(ns.len())[j]==0real);
  lemma_seed_positive(zeros(ns.len()),ns,ns,a,ns[j]);
 }
 lemma_empty_scatter(c,initial(c),0,zeros(ns.len()),0real);assert(initial(c).subrange(0,ns.len() as int)==initial(c));
 assert(((1real-0.5real)+0.5real*1real)/n==a) by(nonlinear_arith) requires a==1real/n,n>0real;
}
pub open spec fn ids(rs:Seq<Row>)->Seq<int> {rs.map_values(|r:Row|r.id)}
pub proof fn lemma_row_ids(rs:Seq<Row>,id:int)
 ensures ids(rs).len()==rs.len(),ids(rs).contains(id)<==>has(rs,id),
 decreases rs.len(),
{
 if rs.len()>0 {lemma_row_ids(rs.drop_first(),id);assert(ids(rs)==seq![rs[0].id]+ids(rs.drop_first()));lemma_prepend_contains(rs[0].id,ids(rs.drop_first()),id);}
}
pub proof fn lemma_has_prepend(r:Row,rs:Seq<Row>,id:int)
 ensures has(seq![r]+rs,id) <==> r.id==id || has(rs,id),
{assert((seq![r]+rs).drop_first()==rs);reveal_with_fuel(has,2);}
pub proof fn lemma_missing_has(ns:Seq<int>,rs:Seq<Row>,id:int)
 ensures has(missing(ns,rs),id) <==> ns.contains(id) && !(has(rs,id)),
 decreases ns.len(),
{
 if ns.len()>0 {lemma_missing_has(ns.drop_first(),rs,id);assert(ns==seq![ns[0]]+ns.drop_first());lemma_prepend_contains(ns[0],ns.drop_first(),id);
 let t=missing(ns.drop_first(),rs);
 if has(rs,ns[0]){if ns[0]==id{assert(has(rs,id));}}else{lemma_has_prepend(Row{id:ns[0],score:0real},t,id);}
 }
}
pub proof fn lemma_missing_rows(ns:Seq<int>,rs:Seq<Row>)
 ensures forall|j:int|0<=j<missing(ns,rs).len() ==> missing(ns,rs)[j].score==0real && ns.contains(missing(ns,rs)[j].id) && !(has(rs,missing(ns,rs)[j].id)),
 decreases ns.len(),
{
 if ns.len()>0 {lemma_missing_rows(ns.drop_first(),rs);let t=missing(ns.drop_first(),rs);assert(ns==seq![ns[0]]+ns.drop_first());
  assert forall|j:int|0<=j<missing(ns,rs).len() implies missing(ns,rs)[j].score==0real && ns.contains(missing(ns,rs)[j].id) && !(has(rs,missing(ns,rs)[j].id)) by {
   let r=missing(ns,rs)[j];
   if has(rs,ns[0]){assert(r==t[j]);}else if j==0{assert(r==Row{id:ns[0],score:0real});}else{assert(r==t[j-1]);}
   lemma_prepend_contains(ns[0],ns.drop_first(),r.id);
  }
 }
}
pub proof fn lemma_missing_nonempty(ns:Seq<int>,rs:Seq<Row>)
 requires ns.no_duplicates(),rs.len()<ns.len(),
 ensures missing(ns,rs).len()>0,
{
 ns.unique_seq_to_set();ids(rs).lemma_cardinality_of_set();ns.to_set_ensures();ids(rs).to_set_ensures();
 if forall|id:int|ns.contains(id) ==> has(rs,id) {
  assert(ns.to_set().subset_of(ids(rs).to_set())) by {
   assert forall|id:int|ns.to_set().contains(id) implies ids(rs).to_set().contains(id) by {lemma_row_ids(rs,id);}
  }
  vstd::set_lib::lemma_len_subset(ns.to_set(),ids(rs).to_set());assert(ids(rs).len()==rs.len());assert(false);
 }
 let id=choose|id:int|ns.contains(id) && !(has(rs,id));lemma_missing_has(ns,rs,id);
}
pub proof fn lemma_rank_member(rs:Seq<Row>,v:Row)
 ensures rank(rs).contains(v) <==> rs.contains(v),
 decreases rs.len(),
{
 if rs.len()>0 {lemma_rank_member(rs.drop_first(),v);lemma_insert_member(rs[0],rank(rs.drop_first()),v);assert(rs==seq![rs[0]]+rs.drop_first());lemma_prepend_contains(rs[0],rs.drop_first(),v);}
}
pub proof fn lemma_rows_properties(ns:Seq<int>,scores:Seq<real>)
 requires ns.len()==scores.len(),
 ensures rows(ns,scores).len()==ns.len(),forall|i:int|0<=i<ns.len() ==> rows(ns,scores)[i].id==ns[i] && rows(ns,scores)[i].score==scores[i],
 decreases ns.len(),
{
 if ns.len()>0 {lemma_rows_properties(ns.drop_first(),scores.drop_first());reveal_with_fuel(rows,2);assert forall|i:int|0<=i<ns.len() implies rows(ns,scores)[i].id==ns[i] && rows(ns,scores)[i].score==scores[i] by {if i>0{assert(rows(ns,scores)[i]==rows(ns.drop_first(),scores.drop_first())[i-1]);assert(ns.drop_first()[i-1]==ns[i]);assert(scores.drop_first()[i-1]==scores[i]);}}}
}
pub proof fn lemma_sparse_positive(rs:Seq<Row>)
 requires forall|i:int|0<=i<rs.len() ==> rs[i].score>0real,
 ensures sparse(rs)==rs,
 decreases rs.len(),
{
 if rs.len()>0 {assert forall|i:int|0<=i<rs.drop_first().len() implies rs.drop_first()[i].score>0real by {assert(rs.drop_first()[i]==rs[i+1]);}lemma_sparse_positive(rs.drop_first());assert(rs==seq![rs[0]]+rs.drop_first());}
}
pub proof fn theorem_positive_input_cap_gap(ns:Seq<int>,scores:Seq<real>,cap:int)
 requires ns.no_duplicates(),scores.len()==ns.len(),0<cap<ns.len(),forall|j:int|0<=j<ns.len() ==> scores[j]>0real,
 ensures exists|i:int,j:int|0<=i<fast_reader(ns,scores,cap,ns.len() as int,cap).len() && 0<=j<ns.len()
  && fast_reader(ns,scores,cap,ns.len() as int,cap)[i].id==ns[j] && fast_reader(ns,scores,cap,ns.len() as int,cap)[i].score==0real && scores[j]>0real,
{
 let rs=rows(ns,scores);lemma_rows_properties(ns,scores);assert forall|i:int|0<=i<rs.len() implies rs[i].score>0real by {assert(rs[i].score==scores[i]);assert(scores[i]>0real);}
 lemma_sparse_positive(rs);theorem_rank_order(rs);let p=cut(rank(rs),cap);assert(p.len()==cap);lemma_cut_order(rank(rs),cap);lemma_rank_identity(p);
 lemma_missing_nonempty(ns,p);let m=missing(ns,p);theorem_rank_order(m);let zeros=rank(m);let z=zeros[0];
 lemma_rank_member(m,z);let k=choose|k:int|0<=k<m.len() && m[k]==z;lemma_missing_rows(ns,p);assert(z.score==0real && ns.contains(z.id));
 let j=choose|j:int|0<=j<ns.len() && ns[j]==z.id;
 let out=fast_reader(ns,scores,cap,ns.len() as int,cap);assert(out==cut(p+zeros,ns.len() as int));assert(out.len()>cap);assert(out[cap]==z);
 assert(0<=cap<out.len() && 0<=j<ns.len() && out[cap].id==ns[j] && out[cap].score==0real && scores[j]>0real);
}
pub proof fn theorem_public_default_cap_gap_from_raw_seeds(ns:Seq<int>)
 requires ns.no_duplicates(),ns.len()>1000,
 ensures ({let raw=ns.map_values(|id:int|Node{graph:0,id});let q=Request{graph:0,seeds:ns,alpha:0.5real,iterations:1,tolerance:0real,reverse:false,weight:1real,excluded:None,top:ns.len() as int};
 match public(raw,seq![],q,Reader::Fast){Answer::Rows{values,iterations}=> iterations==1 && exists|i:int,j:int|0<=i<values.len() && 0<=j<ns.len() && values[i].id==ns[j] && values[i].score==0real && next(source_context(raw,seq![],q),initial(source_context(raw,seq![],q)))[j]>0real,_=>false}}),
{
 let raw=ns.map_values(|id:int|Node{graph:0,id});let q=Request{graph:0,seeds:ns,alpha:0.5real,iterations:1,tolerance:0real,reverse:false,weight:1real,excluded:None,top:ns.len() as int};
 lemma_scoped_map(ns,0);assert forall|i:int|0<=i<ns.len() implies ns.contains(ns[i]) by {}
 lemma_valid_seed_identity(ns,ns);let c=source_context(raw,seq![],q);assert(c.nodes==ns && c.seeds==ns);lemma_isolated_seed_scores_positive(ns);
 assert(next(c,initial(c))==initial(c));assert(iterate(c,initial(c),1,0real).ranks==initial(c));
 theorem_positive_input_cap_gap(ns,initial(c),1000);
 let out=fast_reader(ns,initial(c),1000,ns.len() as int,1000);
 assert(public(raw,seq![],q,Reader::Fast)==Answer::Rows{values:out,iterations:1});
 let (i,j)=choose|i:int,j:int|0<=i<out.len() && 0<=j<ns.len() && out[i].id==ns[j] && out[i].score==0real && initial(c)[j]>0real;
 assert(next(c,initial(c))[j]>0real);
 assert(0<=i<out.len() && 0<=j<ns.len() && out[i].id==ns[j] && out[i].score==0real);
 assert(exists|ii:int,jj:int|0<=ii<out.len() && 0<=jj<ns.len() && out[ii].id==ns[jj] && out[ii].score==0real && next(c,initial(c))[jj]>0real);
 match public(raw,seq![],q,Reader::Fast) {
  Answer::Rows{values,iterations}=>{
   assert(values==out && iterations==1);
   assert(0<=i<values.len() && 0<=j<ns.len() && values[i].id==ns[j] && values[i].score==0real && next(c,initial(c))[j]>0real);
   assert(exists|ii:int,jj:int|0<=ii<values.len() && 0<=jj<ns.len() && values[ii].id==ns[jj] && values[ii].score==0real && next(c,initial(c))[jj]>0real);
  },_=>{assert(false);}
 }

}
}
