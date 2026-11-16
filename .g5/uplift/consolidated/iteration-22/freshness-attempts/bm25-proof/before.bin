// product 3eaa79cf: BM25 index count maintenance under incremental writes.
//   iris_src/src/Graph/KG/BM25Index.cls Insert :442-494, RemoveDoc :416-440, Delete :496-524.
// The ObjectScript loops visit a document's distinct terms once each (tfMap keys; the doc record), so their effect on
// df is the pointwise update below (inspected transcription). Tokenization is a provider: a document is its term set.
use vstd::prelude::*;
verus! {
pub type Doc=int;
pub type Term=int;
/// `df(t)` is the stored ^BM25Idx(name,"df",t); 0 means no entry (the writer kills the node at zero).
pub struct Index {pub docs:Map<Doc,Set<Term>>,pub df:spec_fn(Term)->nat,pub n:nat}
/// Number of documents holding term t.
pub open spec fn holders(docs:Map<Doc,Set<Term>>,t:Term)->Set<Doc> {docs.dom().filter(|d:Doc|docs[d].contains(t))}
pub open spec fn count(docs:Map<Doc,Set<Term>>,t:Term)->nat {holders(docs,t).len()}
/// The owner's invariant (search.bm25.counts): every term's df equals the documents holding it (so no entry exactly
/// when none holds it), and N equals the number of documents.
pub open spec fn consistent(ix:Index)->bool {
 ix.n==ix.docs.dom().len() && (forall|t:Term| #[trigger] (ix.df)(t)==count(ix.docs,t))
}
pub open spec fn one(ts:Set<Term>,t:Term)->nat {if ts.contains(t){1nat}else{0nat}}
/// RemoveDoc: a document not in the index changes nothing; otherwise each of its terms loses one, dropping at zero.
pub open spec fn remove(ix:Index,d:Doc)->Index {
 if !ix.docs.contains_key(d) {ix} else {
  let ts=ix.docs[d];
  Index{docs:ix.docs.remove(d),
   df:|t:Term| ((ix.df)(t)-one(ts,t)) as nat,
   n:(ix.n-1) as nat}
 }
}
/// Insert: remove the old record, then add the new one only if it has terms (a document with none is not indexed).
pub open spec fn insert(ix:Index,d:Doc,ts:Set<Term>)->Index {
 let r=remove(ix,d);
 if ts.len()==0 {r} else {
  Index{docs:r.docs.insert(d,ts),
   df:|t:Term| (r.df)(t)+one(ts,t),
   n:r.n+1}
 }
}

proof fn lemma_holders_remove(docs:Map<Doc,Set<Term>>,d:Doc,t:Term)
 requires docs.contains_key(d)
 ensures count(docs.remove(d),t)==count(docs,t)-(if docs[d].contains(t){1int}else{0int}),
{
 let h=holders(docs,t);let h2=holders(docs.remove(d),t);
 assert(h2=~=h.remove(d));
 docs.dom().lemma_len_filter(|x:Doc|docs[x].contains(t));
 if docs[d].contains(t) {assert(h.contains(d));} else {assert(!h.contains(d));assert(h.remove(d)=~=h);}
}
proof fn lemma_holders_insert(docs:Map<Doc,Set<Term>>,d:Doc,ts:Set<Term>,t:Term)
 requires !docs.contains_key(d)
 ensures count(docs.insert(d,ts),t)==count(docs,t)+(if ts.contains(t){1int}else{0int}),
{
 let h=holders(docs,t);let h2=holders(docs.insert(d,ts),t);
 docs.dom().lemma_len_filter(|x:Doc|docs[x].contains(t));
 assert(!h.contains(d));
 if ts.contains(t) {assert(h2=~=h.insert(d));} else {assert(h2=~=h);}
}
/// Removing a document keeps the counts consistent.
pub proof fn theorem_remove_consistent(ix:Index,d:Doc)
 requires consistent(ix) ensures consistent(remove(ix,d)),
{
 if ix.docs.contains_key(d) {
  let r=remove(ix,d);
  assert(r.docs.dom()=~=ix.docs.dom().remove(d));
  assert forall|t:Term| #[trigger] (r.df)(t)==count(r.docs,t) by {lemma_holders_remove(ix.docs,d,t);}
 }
}
/// Inserting (replacing) a document keeps the counts consistent.
pub proof fn theorem_insert_consistent(ix:Index,d:Doc,ts:Set<Term>)
 requires consistent(ix) ensures consistent(insert(ix,d,ts)),
{
 theorem_remove_consistent(ix,d);let r=remove(ix,d);
 assert(!r.docs.contains_key(d)) by {if ix.docs.contains_key(d) {assert(r.docs.dom()=~=ix.docs.dom().remove(d));}}
 if ts.len()>0 {
  let w=insert(ix,d,ts);
  assert(w.docs.dom()=~=r.docs.dom().insert(d));
  assert forall|t:Term| #[trigger] (w.df)(t)==count(w.docs,t) by {lemma_holders_insert(r.docs,d,ts,t);}
 }
}
/// A replacement with no indexable terms removes the document; deleting an absent document changes nothing.
pub proof fn theorem_empty_replacement_removes(ix:Index,d:Doc)
 requires consistent(ix),ix.docs.contains_key(d)
 ensures !insert(ix,d,Set::empty()).docs.contains_key(d),insert(ix,d,Set::empty()).n==ix.n-1,
{assert(Set::<Term>::empty().len()==0);}
pub proof fn theorem_absent_delete_is_noop(ix:Index,d:Doc)
 requires !ix.docs.contains_key(d) ensures remove(ix,d)==ix {}
/// A replacement leaves N unchanged and moves the frequencies from the old terms to the new ones.
pub proof fn theorem_replace_keeps_n(ix:Index,d:Doc,ts:Set<Term>)
 requires consistent(ix),ix.docs.contains_key(d),ts.len()>0
 ensures insert(ix,d,ts).n==ix.n,insert(ix,d,ts).docs[d]==ts,
{}
}
