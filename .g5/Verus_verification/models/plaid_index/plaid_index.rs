// product 3eaa79cf: PLAID multi-vector index (iris_src/src/Graph/KG/PLAIDSearch.cls; _engine/vector.py plaid_*).
//   Insert :204-232 (overwrite docPacked/docNTok, add centroid memberships, nDocs + 1, totalTokens + nTok; no width
//   check), Info :234-242, Search :99-202 (candidates from the nprobe nearest centroids, ranked by MaxSim over the stored
//   docPacked). Python plaid_build refuses a token of another width before writing (R089); plaid_insert checks nothing.
// Provider premises: the MaxSim score of a document is a function of the query and the document's stored tokens
// (uninterpreted here; its arithmetic, truncation at the shorter vector included, is checked by the binding).
use vstd::prelude::*;
verus! {
pub type D=int;
pub type Tok=Seq<int>;
pub struct Ix {pub tokens:Map<D,Seq<Tok>>,pub n_docs:int,pub total:int,pub dim:nat}
pub uninterp spec fn maxsim(q:Seq<Tok>,t:Seq<Tok>)->int;
pub open spec fn widths_ok(ts:Seq<Tok>,dim:nat)->bool {forall|i:int| 0<=i<ts.len() ==> #[trigger] ts[i].len()==dim}
/// plaid_build refuses a document list with a token of another width; nothing is written (None).
pub open spec fn build(docs:Map<D,Seq<Tok>>,dim:nat)->Option<Ix> {
 if forall|d:D| #[trigger] docs.contains_key(d) ==> widths_ok(docs[d],dim) {Some(Ix{tokens:docs,n_docs:docs.dom().len() as int,total:0,dim:dim})} else {None}
}
/// Insert: overwrite the document's tokens; count one more document and its tokens, whatever was there.
pub open spec fn insert(ix:Ix,d:D,ts:Seq<Tok>)->Ix {Ix{tokens:ix.tokens.insert(d,ts),n_docs:ix.n_docs+1,total:ix.total+ts.len(),dim:ix.dim}}
/// The score a search gives a candidate document: MaxSim over its stored tokens.
pub open spec fn score(ix:Ix,q:Seq<Tok>,d:D)->int {maxsim(q,ix.tokens[d])}

/// P1: a token of another width makes the build refuse.
pub proof fn theorem_build_refuses_other_width(docs:Map<D,Seq<Tok>>,dim:nat,d:D,i:int)
 requires docs.contains_key(d),0<=i<docs[d].len(),docs[d][i].len()!=dim
 ensures build(docs,dim).is_none(),
{assert(!widths_ok(docs[d],dim));}
/// P3, as built (F-0608 PLAID branch): re-inserting a stored document counts it again and adds its tokens to the total.
pub proof fn theorem_reinsert_inflates_counts(ix:Ix,d:D,ts:Seq<Tok>)
 requires ix.tokens.contains_key(d)
 ensures insert(ix,d,ts).tokens.dom()=~=ix.tokens.dom(),insert(ix,d,ts).n_docs==ix.n_docs+1,
  insert(ix,d,ts).total==ix.total+ts.len(),
{}
/// P3: after a re-insert the document is scored on its new tokens only (unlike IVF's stale cell).
pub proof fn theorem_reinsert_scored_on_new_tokens(ix:Ix,d:D,ts:Seq<Tok>,q:Seq<Tok>)
 ensures score(insert(ix,d,ts),q,d)==maxsim(q,ts),
{}
/// P4, as built: an insert of another width is accepted and the recorded width is unchanged.
pub proof fn theorem_insert_accepts_other_width(ix:Ix,d:D,ts:Seq<Tok>)
 requires ts.len()>0,ts[0].len()!=ix.dim
 ensures insert(ix,d,ts).tokens[d]==ts,insert(ix,d,ts).dim==ix.dim,
{}
/// P2 neighbor: a new document is counted once with its tokens.
pub proof fn theorem_new_doc_counted_once(ix:Ix,d:D,ts:Seq<Tok>)
 requires !ix.tokens.contains_key(d),ix.n_docs==ix.tokens.dom().len(),ix.tokens.dom().finite()
 ensures insert(ix,d,ts).n_docs==insert(ix,d,ts).tokens.dom().len(),
{assert(insert(ix,d,ts).tokens.dom()=~=ix.tokens.dom().insert(d));}
}
