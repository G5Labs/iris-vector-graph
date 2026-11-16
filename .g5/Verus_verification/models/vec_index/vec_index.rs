// product 3eaa79cf: the VecIndex random-projection-tree index (iris_src/src/Graph/KG/VecIndex.cls).
//   Create :42-52 (settings, count 0; vectors and trees kept), Drop :54-57, Insert :144-155 (store, dim := width,
//   count + 1, InsertIntoTree in every tree), InsertIntoTree :328-345, Build :157-170 (trees rebuilt over every stored
//   vector), Search :172-182 (trees when numTrees > 0, else brute force), SearchTree :347-371 (the primary child first),
//   RankCandidates :373-387, TopK :389-422 (ascending distance; score 1-d for cosine, -d for dot, d otherwise), Info
//   :460-468. Python wrappers: _engine/vector.py vec_create_index :1548, vec_insert :1578, vec_build :1598,
//   vec_search :1606, vec_info :1632, vec_drop :1641, vec_expand :1644 (no width or duplicate check).
// Provider premises: the metric arithmetic ($vectorop; element-wise operations stop at the shorter vector) is an
// uninterpreted distance; the planes are random, so the leaf a vector reaches is an uninterpreted function of the tree's
// planes and the vector, the same for InsertIntoTree and the primary descent of SearchTree (same `proj >= 0` test).
use vstd::prelude::*;
verus! {
pub type Id=int;
pub type V=Seq<int>;
pub type Planes=int;
pub type Leaf=int;
/// The leaf a vector reaches in a tree with the given planes.
pub uninterp spec fn reach(p:Planes,v:V)->Leaf;
pub struct Ix {pub vecs:Map<Id,V>,pub count:int,pub dim:nat,pub trees:nat,pub planes:Planes,pub leaves:Map<Leaf,Set<Id>>}
pub open spec fn members(ix:Ix,l:Leaf)->Set<Id> {if ix.leaves.contains_key(l) {ix.leaves[l]} else {Set::empty()}}
/// Create: settings and a zero count; vectors and trees are kept (only `cfg` and `meta.count` are set).
pub open spec fn create(ix:Ix,dim:nat,trees:nat)->Ix {
 Ix{vecs:ix.vecs,count:0,dim:dim,trees:trees,planes:ix.planes,leaves:ix.leaves}
}
/// Insert: store the vector, set dim to its width, count one more, and add the id to the leaf it reaches.
pub open spec fn insert(ix:Ix,id:Id,v:V)->Ix {
 let l=reach(ix.planes,v);
 Ix{vecs:ix.vecs.insert(id,v),count:ix.count+1,dim:v.len(),trees:ix.trees,planes:ix.planes,
    leaves:if ix.trees==0 {ix.leaves} else {ix.leaves.insert(l,members(ix,l).insert(id))}}
}
/// Build: new planes; every stored vector placed again; count and settings unchanged.
pub open spec fn build(ix:Ix,p:Planes)->Ix {
 Ix{vecs:ix.vecs,count:ix.count,dim:ix.dim,trees:ix.trees,planes:p,
    leaves:Map::new(ix.vecs.dom().map(|i:Id| reach(p,ix.vecs[i])),|l:Leaf| ix.vecs.dom().filter(|i:Id| reach(p,ix.vecs[i])==l))}
}
pub open spec fn drop()->Ix {Ix{vecs:Map::empty(),count:0,dim:0,trees:0,planes:0,leaves:Map::empty()}}
/// The candidates a search ranks: with trees, at least the leaf the query reaches; without, every stored vector.
pub open spec fn candidates(ix:Ix,q:V)->Set<Id> {if ix.trees==0 {ix.vecs.dom()} else {members(ix,reach(ix.planes,q))}}
pub enum Metric {Cosine,Dot,L2,L1,Chebyshev}
/// TopK's reported score for a distance d (Distance: 1-cos for cosine, -dot for dot, the distance otherwise).
pub open spec fn score(m:Metric,d:int)->int {match m {Metric::Cosine=>1-d,Metric::Dot=>-d,_=>d}}

/// V3: a vector inserted into an index that already has trees is a candidate for an identical query at once.
pub proof fn theorem_insert_found_by_identical_query(ix:Ix,id:Id,v:V)
 requires ix.trees>0
 ensures candidates(insert(ix,id,v),v).contains(id),
{}
/// After a build, every stored vector is a candidate for an identical query.
pub proof fn theorem_build_places_every_vector(ix:Ix,p:Planes,id:Id)
 requires ix.trees>0,ix.vecs.contains_key(id)
 ensures candidates(build(ix,p),ix.vecs[id]).contains(id),
{
 let b=build(ix,p);let l=reach(p,ix.vecs[id]);
 assert(ix.vecs.dom().map(|i:Id| reach(p,ix.vecs[i])).contains(l));
}
/// F-0608 (VecIndex branch), as built: re-inserting a stored id leaves the stored ids as they were but counts one more.
pub proof fn theorem_reinsert_inflates_count(ix:Ix,id:Id,v:V)
 requires ix.vecs.contains_key(id)
 ensures insert(ix,id,v).vecs.dom()=~=ix.vecs.dom(),insert(ix,id,v).count==ix.count+1,
{}
/// The ordinary neighbor: from a new index, inserting distinct ids counts exactly the stored vectors.
pub proof fn theorem_distinct_inserts_count_vectors(ix:Ix,a:Id,b:Id,va:V,vb:V,dim:nat,trees:nat)
 requires ix.vecs.dom().len()==0,ix.vecs.dom().finite(),a!=b
 ensures insert(insert(create(ix,dim,trees),a,va),b,vb).count==insert(insert(create(ix,dim,trees),a,va),b,vb).vecs.dom().len(),
{
 let r=insert(insert(create(ix,dim,trees),a,va),b,vb);
 assert(ix.vecs.dom()=~=Set::<Id>::empty()) by {if exists|i:Id| ix.vecs.dom().contains(i) {let i=choose|i:Id| ix.vecs.dom().contains(i); assert(ix.vecs.dom().len()>0) by {ix.vecs.dom().lemma_len0_is_empty();}}}
 assert(r.vecs.dom()=~=set![a,b]);
}
/// V10, as built: creating an index over an existing name reports a zero count while every stored vector stays searchable.
pub proof fn theorem_recreate_zero_count_keeps_vectors(ix:Ix,dim:nat,q:V)
 requires ix.trees==0
 ensures create(ix,dim,0).count==0,create(ix,dim,0).vecs==ix.vecs,candidates(create(ix,dim,0),q)==ix.vecs.dom(),
{}
/// V11, as built: an insert of another width is stored, and the index's recorded width becomes that width.
pub proof fn theorem_insert_overwrites_dim(ix:Ix,id:Id,v:V)
 requires v.len()!=ix.dim
 ensures insert(ix,id,v).vecs[id]==v,insert(ix,id,v).dim==v.len(),insert(ix,id,v).dim!=ix.dim,
{}
/// V12: after a drop nothing is a candidate.
pub proof fn theorem_drop_empties_search(q:V)
 ensures candidates(drop(),q)=~=Set::<Id>::empty(),drop().count==0,
{}
/// V5-V7: the reported score per metric; results come in ascending distance, so for dot the largest dot product first.
pub proof fn theorem_score_mapping(d1:int,d2:int)
 requires d1<d2
 ensures score(Metric::Cosine,d1)>score(Metric::Cosine,d2),score(Metric::Dot,d1)>score(Metric::Dot,d2),
  score(Metric::L2,d1)<score(Metric::L2,d2),score(Metric::Cosine,0)==1,
{}
}
