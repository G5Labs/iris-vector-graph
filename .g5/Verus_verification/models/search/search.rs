// IVG embeddings and search — Verus model (initial uplift B-search, 2026-11-13).
//
// Product baseline 3eaa79cf. This file is a model and a transcription; it does not verify the
// product's ObjectScript or Python bodies. Bindings to the product (L3) are in NOTES.md and in the
// comments that name a product operation (BM25Index.cls line numbers are at the pin).
//
// Obligations
//   O1  BM25 counters (spec 044 FR-015..FR-022, ADR-0007) and the common-term cutoff (FR-044-C1..C5)
//   O2  BM25 schema-1 -> schema-2 Upgrade lifecycle (FR-023)
//   O3  embedding identity and routing (ADR-0006 as amended by the 4.0.0 routing decision)
//   O5  erasure over search stores (ADR-0004, GraphStores inventory)
//
// Layers: L1 rules are the `cons*`, `one_row`, `read_table`, `no_erased_answer`, cutoff-contract
// predicates; L2 is the transcription of each operation; theorems prove that in-scope L2 steps keep
// L1, and `witness_*` lemmas are concrete traces (proved) where the as-built mechanism breaks it.
//
// Run:  $VERUS_BIN search.rs --crate-type=lib --num-threads 4 --triggers-mode silent
use vstd::prelude::*;

verus! {

// ============================================================================ sums over finite sets

pub open spec fn sumf<K>(f: spec_fn(K) -> int, s: Set<K>) -> int
    decreases s.len(),
{
    if s.len() == 0 {
        0
    } else {
        let x = s.choose();
        f(x) + sumf(f, s.remove(x))
    }
}

pub proof fn lemma_sumf_remove<K>(f: spec_fn(K) -> int, s: Set<K>, x: K)
    requires
        s.contains(x),
    ensures
        sumf(f, s) == f(x) + sumf(f, s.remove(x)),
    decreases s.len(),
{
    let y = s.choose();
    if y != x {
        lemma_sumf_remove(f, s.remove(y), x);
        lemma_sumf_remove(f, s.remove(x), y);
        assert(s.remove(y).remove(x) =~= s.remove(x).remove(y));
    }
}

pub proof fn lemma_sumf_insert<K>(f: spec_fn(K) -> int, s: Set<K>, x: K)
    requires
        !s.contains(x),
    ensures
        sumf(f, s.insert(x)) == f(x) + sumf(f, s),
{
    lemma_sumf_remove(f, s.insert(x), x);
    assert(s.insert(x).remove(x) =~= s);
}

pub proof fn lemma_sumf_ext<K>(f: spec_fn(K) -> int, g: spec_fn(K) -> int, s: Set<K>)
    requires
        forall|x: K| #[trigger] s.contains(x) ==> f(x) == g(x),
    ensures
        sumf(f, s) == sumf(g, s),
    decreases s.len(),
{
    if s.len() != 0 {
        let x = s.choose();
        lemma_sumf_ext(f, g, s.remove(x));
    }
}

pub proof fn lemma_two_elems_len<A>(s: Set<A>, a: A, b: A)
    requires
        s.contains(a),
        s.contains(b),
        a != b,
    ensures
        s.len() >= 2,
        s.remove(a).len() > 0,
{
    assert(s.remove(a).contains(b));
}

// ============================================================================ the index state (^BM25Idx(x, ...))

pub type Term = int;
pub type Doc = int;

pub struct Ix {
    /// ^BM25Idx(x,"tf",term,docId): term-first; a term node exists only while it has a child
    pub tf: Map<Term, Map<Doc, int>>,
    /// ^BM25Idx(x,"df",term) (absent at zero)
    pub df: Map<Term, int>,
    /// ^BM25Idx(x,"doc",docId): $ListBuild of the document's distinct tokens (premise P_distinct)
    pub doc: Map<Doc, Set<Term>>,
    /// ^BM25Idx(x,"len",docId)
    pub len: Map<Doc, int>,
    /// ^BM25Idx(x,"cfg","N"); None is $Data = 0 (no index)
    pub n: Option<int>,
    /// +$Get(^BM25Idx(x,"cfg","totalLen"), 0)
    pub total: int,
    /// +$Get(^BM25Idx(x,"cfg","vocab_size"), 0)
    pub vocab: int,
    /// ^BM25Idx(x,"cfg","schema"); None reads as schema 1
    pub schema: Option<int>,
    /// ^BM25Idx(x,"cfg","upgrading")
    pub upgrading: bool,
    /// the schema-1 ^BM25Idx(x,"idf") subtree and cfg "avgdl" exist
    pub idf: bool,
}

pub open spec fn tfv(ix: Ix, t: Term, d: Doc) -> int {
    if ix.tf.contains_key(t) && ix.tf[t].contains_key(d) { ix.tf[t][d] } else { 0 }
}

/// +$Get(^BM25Idx(x,"df",t), 0)
pub open spec fn dfv(ix: Ix, t: Term) -> int {
    if ix.df.contains_key(t) { ix.df[t] } else { 0 }
}

/// +$Get(^BM25Idx(x,"cfg","N"), 0)
pub open spec fn nval(ix: Ix) -> int {
    match ix.n { Some(v) => v, None => 0 }
}

/// +$Get(^BM25Idx(x,"len",d), 0)
pub open spec fn lenv(ix: Ix, d: Doc) -> int {
    if ix.len.contains_key(d) { ix.len[d] } else { 0 }
}

pub open spec fn schema_of(ix: Ix) -> int {
    match ix.schema { Some(v) => v, None => 1 }
}

pub open spec fn posting(ix: Ix, t: Term) -> Map<Doc, int> {
    if ix.tf.contains_key(t) { ix.tf[t] } else { Map::empty() }
}

pub open spec fn doc_len_of(ix: Ix, d: Doc) -> int {
    sumf(|t: Term| tfv(ix, t, d), ix.doc[d])
}

pub open spec fn total_of(len: Map<Doc, int>) -> int {
    sumf(|d: Doc| len[d], len.dom())
}

/// No index: Kill ^BM25Idx(x) (Build's first statement, Drop).
pub open spec fn absent_ix() -> Ix {
    Ix {
        tf: Map::empty(),
        df: Map::empty(),
        doc: Map::empty(),
        len: Map::empty(),
        n: None,
        total: 0,
        vocab: 0,
        schema: None,
        upgrading: false,
        idf: false,
    }
}

pub open spec fn is_absent(ix: Ix) -> bool {
    &&& ix.n is None
    &&& ix.tf == Map::<Term, Map<Doc, int>>::empty()
    &&& ix.df == Map::<Term, int>::empty()
    &&& ix.doc == Map::<Doc, Set<Term>>::empty()
    &&& ix.len == Map::<Doc, int>::empty()
    &&& ix.total == 0
    &&& ix.vocab == 0
}

// ---------------------------------------------------------------------------- L1 (FR-016, FR-018)

/// L1 counter consistency of a present index at a committed point (spec 044 FR-016/FR-018,
/// ADR-0007, CONTEXT.md "Document Frequency"): df(t) = |{d : tf(t,d)}| and absent at zero; the
/// token record of d is exactly the terms with a tf(t,d); N = |len|; totalLen = sum len;
/// vocab_size = |df|; len(d) = sum_t tf(t,d) > 0.
pub open spec fn cons_present(ix: Ix) -> bool {
    &&& forall|t: Term| #[trigger] ix.tf.contains_key(t) ==> ix.tf[t].dom().len() > 0
    &&& forall|t: Term, d: Doc| #[trigger] ix.tf.contains_key(t) && #[trigger] ix.tf[t].contains_key(d)
            ==> ix.tf[t][d] > 0 && ix.doc.contains_key(d) && ix.doc[d].contains(t)
    &&& forall|t: Term| #[trigger] ix.df.contains_key(t) == ix.tf.contains_key(t)
    &&& forall|t: Term| #[trigger] ix.df.contains_key(t) ==> ix.df[t] == ix.tf[t].dom().len()
    &&& ix.doc.dom() == ix.len.dom()
    &&& forall|d: Doc, t: Term| #[trigger] ix.doc.contains_key(d) && #[trigger] ix.doc[d].contains(t)
            ==> ix.tf.contains_key(t) && ix.tf[t].contains_key(d)
    &&& forall|d: Doc| #[trigger] ix.doc.contains_key(d) ==> ix.len[d] > 0 && ix.len[d] == doc_len_of(ix, d)
    &&& ix.n == Some(ix.len.dom().len() as int)
    &&& ix.total == total_of(ix.len)
    &&& ix.vocab == ix.df.dom().len()
}

pub open spec fn cons(ix: Ix) -> bool {
    is_absent(ix) || (ix.n is Some && cons_present(ix))
}

// ---------------------------------------------------------------------------- L2 (BM25Index.cls)

/// The tokenizer's output for one text: tfMap (Insert l.449-454, IndexDoc l.183-188) and docLen
/// ($LISTLENGTH(tokens)). Premise P_tok, established by Tokenize l.80-85 (empty tokens are dropped
/// before the list is built, so docLen counts exactly the tokens tfMap counts).
pub open spec fn tok_ok(bag: Map<Term, int>, dlen: int) -> bool {
    &&& forall|t: Term| #[trigger] bag.contains_key(t) ==> bag[t] >= 1
    &&& dlen == sumf(|t: Term| bag[t], bag.dom())
    &&& (dlen > 0 <==> bag.dom().len() > 0)
}

/// RemoveDoc's loop over the token record (l.421-431): Kill tf(tok,d); df(tok) := +$Get(df)-1, and
/// at <= 0 Kill df(tok) and vocab_size - 1. Each token of the record once (P_distinct), so the
/// loop's effect is the per-term effect on every token of `rec`.
pub open spec fn remove_postings(ix: Ix, d: Doc, rec: Set<Term>) -> Ix {
    let gone = rec.filter(|t: Term| dfv(ix, t) - 1 <= 0);
    Ix {
        tf: Map::new(
            ix.tf.dom().filter(|t: Term| !(rec.contains(t) && ix.tf[t].dom().remove(d).len() == 0)),
            |t: Term| if rec.contains(t) { ix.tf[t].remove(d) } else { ix.tf[t] },
        ),
        df: Map::new(
            ix.df.dom().filter(|t: Term| !gone.contains(t)),
            |t: Term| if rec.contains(t) { ix.df[t] - 1 } else { ix.df[t] },
        ),
        vocab: ix.vocab - gone.len(),
        ..ix
    }
}

/// RemoveDoc's presence test (l.418)
pub open spec fn present(ix: Ix, d: Doc) -> bool {
    ix.len.contains_key(d) || ix.doc.contains_key(d)
}

/// RemoveDoc l.420: $Get(^BM25Idx(x,"doc",d)), "" when absent
pub open spec fn rec_of(ix: Ix, d: Doc) -> Set<Term> {
    if ix.doc.contains_key(d) { ix.doc[d] } else { Set::empty() }
}

/// BM25Index.RemoveDoc (l.416-437).
pub open spec fn remove_doc(ix: Ix, d: Doc) -> Ix {
    if !present(ix, d) {
        ix
    } else {
        remove_tail(remove_postings(ix, d, rec_of(ix, d)), d, lenv(ix, d))
    }
}

/// RemoveDoc l.432-435: Kill doc(d), Kill len(d), N := +$Get(N)-1, totalLen := +$Get(totalLen)-oldLen,
/// where oldLen was read at l.419, before the loop.
pub open spec fn remove_tail(ix: Ix, d: Doc, old_len: int) -> Ix {
    Ix {
        doc: ix.doc.remove(d),
        len: ix.len.remove(d),
        n: Some(nval(ix) - 1),
        total: ix.total - old_len,
        ..ix
    }
}

/// The add loop shared by Insert (l.471-479) and IndexDoc (l.191-199): tf(tok,d) := tfMap(tok),
/// df(tok) := +$Get(df)+1, and a token whose df was 0 counts one more vocabulary entry.
pub open spec fn add_postings(ix: Ix, d: Doc, bag: Map<Term, int>) -> Ix {
    Ix {
        tf: Map::new(
            ix.tf.dom().union(bag.dom()),
            |t: Term| if bag.contains_key(t) { posting(ix, t).insert(d, bag[t]) } else { ix.tf[t] },
        ),
        df: Map::new(
            ix.df.dom().union(bag.dom()),
            |t: Term| if bag.contains_key(t) { dfv(ix, t) + 1 } else { ix.df[t] },
        ),
        ..ix
    }
}

pub open spec fn fresh_terms(ix: Ix, bag: Map<Term, int>) -> Set<Term> {
    bag.dom().filter(|t: Term| dfv(ix, t) == 0)
}

/// Insert l.471-481: the add loop (tf, df, vocab_size), then the token record and len.
pub open spec fn add_body(ix: Ix, d: Doc, bag: Map<Term, int>, dlen: int) -> Ix {
    let ix1 = add_postings(ix, d, bag);
    Ix {
        doc: ix1.doc.insert(d, bag.dom()),
        len: ix1.len.insert(d, dlen),
        vocab: ix.vocab + fresh_terms(ix, bag).len(),
        ..ix1
    }
}

/// Insert l.482-483: N + 1 and totalLen + docLen (read without $Get: an undefined N raises).
pub open spec fn add_counters(ix: Ix, dlen: int) -> Ix {
    Ix { n: Some(nval(ix) + 1), total: ix.total + dlen, ..ix }
}

/// Insert l.468-484 after RemoveDoc.
pub open spec fn add_doc(ix: Ix, d: Doc, bag: Map<Term, int>, dlen: int) -> Ix {
    add_counters(add_body(ix, d, bag, dlen), dlen)
}

/// RequireWritable (l.385-394): a name with no N is writable; otherwise not while "upgrading" and
/// not on schema 1.
pub open spec fn writable(ix: Ix) -> bool {
    ix.n is None || (!ix.upgrading && schema_of(ix) >= 2)
}

/// The body of Insert between TStart and TCommit (l.460-485), run under Lock +^BM25Idx(x,"lock").
pub open spec fn insert_body(ix: Ix, d: Doc, bag: Map<Term, int>, dlen: int) -> Ix {
    let ix1 = remove_doc(init_ix(ix), d);
    if dlen > 0 { add_doc(ix1, d, bag, dlen) } else { ix1 }
}

/// Insert l.461-466: a name with no N is created as an empty schema-2 index.
pub open spec fn init_ix(ix: Ix) -> Ix {
    if ix.n is None {
        Ix { n: Some(0), total: 0, vocab: 0, schema: Some(2), ..ix }
    } else {
        ix
    }
}

// ---------------------------------------------------------------------------- preservation (locked writers)

pub proof fn lemma_remove_doc_preserves(ix: Ix, d: Doc)
    requires
        ix.n is Some,
        cons_present(ix),
    ensures
        cons_present(remove_doc(ix, d)),
        remove_doc(ix, d).n is Some,
        !remove_doc(ix, d).len.contains_key(d),
        remove_doc(ix, d).schema == ix.schema,
        remove_doc(ix, d).upgrading == ix.upgrading,
{
    if !ix.len.contains_key(d) && !ix.doc.contains_key(d) {
        return;
    }
    assert(ix.doc.contains_key(d));
    let rec = ix.doc[d];
    let gone = rec.filter(|t: Term| dfv(ix, t) - 1 <= 0);
    let ix1 = remove_postings(ix, d, rec);
    let ix2 = remove_doc(ix, d);
    assert(ix2.tf == ix1.tf && ix2.df == ix1.df && ix2.vocab == ix1.vocab);
    // every token of the record has a posting for d and df >= 1
    assert forall|t: Term| #[trigger] rec.contains(t) implies ix.tf.contains_key(t) && ix.tf[t].contains_key(d)
        && ix.df.contains_key(t) && ix.df[t] == ix.tf[t].dom().len() && ix.tf[t].dom().remove(d).len() == ix.df[t] - 1 by {
        assert(ix.doc.contains_key(d) && ix.doc[d].contains(t));
        assert(ix.tf.contains_key(t) && ix.tf[t].contains_key(d));
        assert(ix.df.contains_key(t));
        assert(ix.tf[t].dom().contains(d));
    }
    // the domains of tf and df stay equal
    assert forall|t: Term| #[trigger] ix2.df.contains_key(t) == ix2.tf.contains_key(t) by {
        if ix.tf.contains_key(t) && rec.contains(t) {
            assert(gone.contains(t) == (ix.tf[t].dom().remove(d).len() == 0));
        }
    }
    assert forall|t: Term| #[trigger] ix2.tf.contains_key(t) implies ix2.tf[t].dom().len() > 0
        && ix2.df[t] == ix2.tf[t].dom().len() by {
        if rec.contains(t) {
            assert(ix2.tf[t] == ix.tf[t].remove(d));
            assert(ix2.tf[t].dom() == ix.tf[t].dom().remove(d));
        } else {
            assert(ix2.tf[t] == ix.tf[t]);
        }
    }
    assert forall|t: Term| #[trigger] ix2.df.contains_key(t) implies ix2.df[t] == ix2.tf[t].dom().len() by {
        assert(ix2.tf.contains_key(t));
    }
    // vocab
    assert(gone.subset_of(ix.df.dom()));
    assert(ix2.df.dom() =~= ix.df.dom().difference(gone));
    assert(ix.df.dom().intersect(gone) =~= gone);
    vstd::set_lib::lemma_set_difference_len(ix.df.dom(), gone);
    assert(ix2.vocab == ix2.df.dom().len());
    // postings point at recorded documents
    assert forall|t: Term, e: Doc| #[trigger] ix2.tf.contains_key(t) && #[trigger] ix2.tf[t].contains_key(e)
        implies ix2.tf[t][e] > 0 && ix2.doc.contains_key(e) && ix2.doc[e].contains(t) by {
        if rec.contains(t) {
            assert(ix2.tf[t] == ix.tf[t].remove(d));
            assert(e != d);
            assert(ix.tf[t].contains_key(e));
        } else {
            assert(ix2.tf[t] == ix.tf[t]);
            assert(ix.tf[t].contains_key(e));
            if e == d {
                assert(ix.doc[d].contains(t));
            }
        }
    }
    // records point at postings
    assert forall|e: Doc, t: Term| #[trigger] ix2.doc.contains_key(e) && #[trigger] ix2.doc[e].contains(t)
        implies ix2.tf.contains_key(t) && ix2.tf[t].contains_key(e) by {
        assert(e != d);
        assert(ix2.doc[e] == ix.doc[e]);
        assert(ix.tf.contains_key(t) && ix.tf[t].contains_key(e));
        if rec.contains(t) {
            lemma_two_elems_len(ix.tf[t].dom(), d, e);
            assert(ix2.tf[t] == ix.tf[t].remove(d));
        } else {
            assert(ix2.tf[t] == ix.tf[t]);
        }
    }
    // document lengths
    assert forall|e: Doc| #[trigger] ix2.doc.contains_key(e) implies ix2.len[e] > 0 && ix2.len[e] == doc_len_of(ix2, e) by {
        assert(e != d);
        assert(ix2.doc[e] == ix.doc[e]);
        assert(ix2.len[e] == ix.len[e]);
        assert forall|t: Term| #[trigger] ix.doc[e].contains(t) implies tfv(ix2, t, e) == tfv(ix, t, e) by {
            assert(ix.tf.contains_key(t) && ix.tf[t].contains_key(e));
            if rec.contains(t) {
                lemma_two_elems_len(ix.tf[t].dom(), d, e);
                assert(ix2.tf[t] == ix.tf[t].remove(d));
            } else {
                assert(ix2.tf[t] == ix.tf[t]);
            }
        }
        lemma_sumf_ext(|t: Term| tfv(ix2, t, e), |t: Term| tfv(ix, t, e), ix.doc[e]);
    }
    // N and totalLen
    assert(ix2.len.dom() == ix.len.dom().remove(d));
    assert(ix2.n == Some(ix2.len.dom().len() as int));
    lemma_sumf_remove(|e: Doc| ix.len[e], ix.len.dom(), d);
    lemma_sumf_ext(|e: Doc| ix.len[e], |e: Doc| ix2.len[e], ix.len.dom().remove(d));
    assert(ix2.total == total_of(ix2.len));
    assert(ix2.doc.dom() =~= ix2.len.dom());
}

pub proof fn lemma_add_doc_preserves(ix: Ix, d: Doc, bag: Map<Term, int>, dlen: int)
    requires
        ix.n is Some,
        cons_present(ix),
        !ix.len.contains_key(d),
        tok_ok(bag, dlen),
        dlen > 0,
    ensures
        cons_present(add_doc(ix, d, bag, dlen)),
        add_doc(ix, d, bag, dlen).n is Some,
        add_doc(ix, d, bag, dlen).schema == ix.schema,
        add_doc(ix, d, bag, dlen).upgrading == ix.upgrading,
{
    let ix2 = add_doc(ix, d, bag, dlen);
    let fresh = fresh_terms(ix, bag);
    assert(!ix.doc.contains_key(d));
    // no posting names d yet
    assert forall|t: Term| #[trigger] ix.tf.contains_key(t) implies !ix.tf[t].contains_key(d) by {
        if ix.tf[t].contains_key(d) {
            assert(ix.doc.contains_key(d));
        }
    }
    assert forall|t: Term| #[trigger] ix2.df.contains_key(t) == ix2.tf.contains_key(t) by {}
    assert forall|t: Term| #[trigger] ix2.tf.contains_key(t) implies ix2.tf[t].dom().len() > 0
        && ix2.df[t] == ix2.tf[t].dom().len() by {
        if bag.contains_key(t) {
            assert(ix2.tf[t] == posting(ix, t).insert(d, bag[t]));
            assert(ix2.tf[t].dom() == posting(ix, t).dom().insert(d));
            assert(!posting(ix, t).dom().contains(d));
            if ix.tf.contains_key(t) {
                assert(ix.df.contains_key(t));
            } else {
                assert(!ix.df.contains_key(t));
                assert(posting(ix, t).dom() =~= Set::<Doc>::empty());
            }
        } else {
            assert(ix2.tf[t] == ix.tf[t]);
            assert(ix.df.contains_key(t));
        }
    }
    assert forall|t: Term| #[trigger] ix2.df.contains_key(t) implies ix2.df[t] == ix2.tf[t].dom().len() by {
        assert(ix2.tf.contains_key(t));
    }
    // vocab
    assert(ix2.df.dom() =~= ix.df.dom().union(fresh));
    assert(ix.df.dom().disjoint(fresh));
    vstd::set_lib::lemma_set_disjoint_lens(ix.df.dom(), fresh);
    assert(ix2.vocab == ix2.df.dom().len());
    // postings point at recorded documents
    assert forall|t: Term, e: Doc| #[trigger] ix2.tf.contains_key(t) && #[trigger] ix2.tf[t].contains_key(e)
        implies ix2.tf[t][e] > 0 && ix2.doc.contains_key(e) && ix2.doc[e].contains(t) by {
        if bag.contains_key(t) {
            assert(ix2.tf[t] == posting(ix, t).insert(d, bag[t]));
            if e == d {
                assert(ix2.doc[d] == bag.dom());
            } else {
                assert(ix.tf.contains_key(t) && ix.tf[t].contains_key(e));
                assert(ix2.doc[e] == ix.doc[e]);
            }
        } else {
            assert(ix2.tf[t] == ix.tf[t]);
            assert(ix.tf[t].contains_key(e));
            assert(e != d);
            assert(ix2.doc[e] == ix.doc[e]);
        }
    }
    // records point at postings
    assert forall|e: Doc, t: Term| #[trigger] ix2.doc.contains_key(e) && #[trigger] ix2.doc[e].contains(t)
        implies ix2.tf.contains_key(t) && ix2.tf[t].contains_key(e) by {
        if e == d {
            assert(bag.contains_key(t));
            assert(ix2.tf[t] == posting(ix, t).insert(d, bag[t]));
        } else {
            assert(ix2.doc[e] == ix.doc[e]);
            assert(ix.tf.contains_key(t) && ix.tf[t].contains_key(e));
            if bag.contains_key(t) {
                assert(ix2.tf[t] == posting(ix, t).insert(d, bag[t]));
            } else {
                assert(ix2.tf[t] == ix.tf[t]);
            }
        }
    }
    // document lengths
    assert forall|e: Doc| #[trigger] ix2.doc.contains_key(e) implies ix2.len[e] > 0 && ix2.len[e] == doc_len_of(ix2, e) by {
        if e == d {
            assert forall|t: Term| #[trigger] bag.dom().contains(t) implies tfv(ix2, t, d) == bag[t] by {
                assert(ix2.tf[t] == posting(ix, t).insert(d, bag[t]));
            }
            lemma_sumf_ext(|t: Term| tfv(ix2, t, d), |t: Term| bag[t], bag.dom());
        } else {
            assert(ix2.doc[e] == ix.doc[e]);
            assert(ix2.len[e] == ix.len[e]);
            assert forall|t: Term| #[trigger] ix.doc[e].contains(t) implies tfv(ix2, t, e) == tfv(ix, t, e) by {
                assert(ix.tf.contains_key(t) && ix.tf[t].contains_key(e));
                if bag.contains_key(t) {
                    assert(ix2.tf[t] == posting(ix, t).insert(d, bag[t]));
                } else {
                    assert(ix2.tf[t] == ix.tf[t]);
                }
            }
            lemma_sumf_ext(|t: Term| tfv(ix2, t, e), |t: Term| tfv(ix, t, e), ix.doc[e]);
        }
    }
    // N and totalLen
    assert(ix2.len.dom() == ix.len.dom().insert(d));
    assert(ix2.n == Some(ix2.len.dom().len() as int));
    lemma_sumf_insert(|e: Doc| ix2.len[e], ix.len.dom(), d);
    lemma_sumf_ext(|e: Doc| ix.len[e], |e: Doc| ix2.len[e], ix.len.dom());
    assert(ix2.total == total_of(ix2.len));
    assert(ix2.doc.dom() =~= ix2.len.dom());
}

pub proof fn lemma_absent_init_cons(ix: Ix)
    requires
        is_absent(ix),
    ensures
        cons_present(Ix { n: Some(0), total: 0, vocab: 0, schema: Some(2), ..ix }),
{
    let ix0 = Ix { n: Some(0), total: 0, vocab: 0, schema: Some(2), ..ix };
    assert(ix0.len.dom() =~= Set::<Doc>::empty());
    assert(ix0.df.dom() =~= Set::<Term>::empty());
    assert(ix0.doc.dom() =~= Set::<Doc>::empty());
}

/// O1 for Insert (FR-016, FR-018, FR-019, FR-020): a committed Insert on a consistent, writable
/// index leaves it consistent — including replace, replace with empty text and the first insert
/// into an absent index — and leaves the schema at 2 and the upgrade flag unchanged.
pub proof fn theorem_insert_preserves_counters(ix: Ix, d: Doc, bag: Map<Term, int>, dlen: int)
    requires
        cons(ix),
        writable(ix),
        tok_ok(bag, dlen),
    ensures
        cons(insert_body(ix, d, bag, dlen)),
        insert_body(ix, d, bag, dlen).n is Some,
        dlen > 0 ==> insert_body(ix, d, bag, dlen).len.contains_key(d),
        dlen <= 0 ==> !insert_body(ix, d, bag, dlen).len.contains_key(d),
        schema_of(insert_body(ix, d, bag, dlen)) >= 2,
        insert_body(ix, d, bag, dlen).upgrading == ix.upgrading,
{
    let ix0 = if ix.n is None { Ix { n: Some(0), total: 0, vocab: 0, schema: Some(2), ..ix } } else { ix };
    if ix.n is None {
        lemma_absent_init_cons(ix);
    }
    lemma_remove_doc_preserves(ix0, d);
    let ix1 = remove_doc(ix0, d);
    if dlen > 0 {
        lemma_add_doc_preserves(ix1, d, bag, dlen);
    }
}

/// O1 for Delete (FR-021): Delete on a present, writable, consistent index keeps it consistent.
pub proof fn theorem_delete_preserves_counters(ix: Ix, d: Doc)
    requires
        cons(ix),
        ix.n is Some,
        writable(ix),
    ensures
        cons(remove_doc(ix, d)),
        !remove_doc(ix, d).len.contains_key(d),
        remove_doc(ix, d).schema == ix.schema,
        remove_doc(ix, d).upgrading == ix.upgrading,
{
    lemma_remove_doc_preserves(ix, d);
}

// ---------------------------------------------------------------------------- writers, Build and Drop

/// Build's process-local counters (l.133-135) and the documents its scan has flushed so far.
pub struct BuildRun {
    pub bn: int,
    pub btotal: int,
    pub bvocab: int,
    pub seen: Set<Doc>,
}

/// One Insert or Delete transaction in flight: it holds Lock ^BM25Idx(x,"lock") from LockWrite to the
/// unlock after TCommit, so at most one exists. `pre` is the index at its TStart; `present`, `old_len`
/// and `rec` are what RemoveDoc read at l.418-420 (after Insert's new-index init, l.461-466).
pub enum Phase {
    /// TStart, init, RemoveDoc's loop over the record (l.460-431)
    Removed,
    /// RemoveDoc's tail: Kill doc and len, N - 1, totalLen - oldLen (l.432-435)
    Tailed,
    /// the add loop, the token record and len (l.471-481)
    Added,
}

pub struct WRun {
    pub pre: Ix,
    pub d: Doc,
    pub bag: Map<Term, int>,
    pub dlen: int,
    pub present: bool,
    pub old_len: int,
    pub rec: Set<Term>,
    pub phase: Phase,
}

pub struct WSys {
    pub ix: Ix,
    pub build: Option<BuildRun>,
    pub run: Option<WRun>,
    /// ghost: documents whose Delete (or empty-text replace) has returned and that no later write has
    /// put back (an Insert of the document, or a Build that scans it after the delete)
    pub gone: Set<Doc>,
}

pub enum WAct {
    /// Insert l.444-467 up to the end of RemoveDoc's loop: RequireWritable, Tokenize, LockWrite,
    /// RequireWritable, TStart, new-index init, RemoveDoc's presence test, oldLen, record and loop
    InsBegin { d: Doc, bag: Map<Term, int>, dlen: int },
    /// Delete l.496-505 up to the end of RemoveDoc's loop (no N: returns 0 without locking)
    DelBegin { d: Doc },
    /// the rest of RemoveDoc (l.432-435)
    WTail,
    /// Insert l.468-481 (nothing for a Delete or an empty text)
    WAdd,
    /// Insert l.482-485 / Delete l.506: N + 1 and totalLen + docLen (an Insert with tokens), TCommit,
    /// unlock. With N undefined the Insert raises <UNDEFINED> and rolls back: that path is not in the
    /// step relation (see W-O1d for the rollback premise P_undo).
    WCommit,
    /// a writer refused before TStart (RequireWritable, lock timeout): no change
    WriteFails,
    /// Build l.99: Kill ^BM25Idx(name), no lock
    BuildKill,
    /// Build l.146/156 -> IndexDoc l.178-204 for one scanned document, no lock
    BuildDoc { d: Doc, bag: Map<Term, int>, dlen: int },
    /// Build l.160-170: cfg N, totalLen, k1, b, vocab_size, graph and finally schema = 2
    BuildFinish,
    /// Drop l.587-591: Kill ^BM25Idx(name), no lock
    Drop,
}

/// `build_locked`: the proposed repair in which Build and Drop hold the index write lock for their
/// whole run (as-built: false). `delete_under_lock`: the second half of the repair (review R2-1):
/// Delete takes the lock before it tests for cfg N, so it waits for a Build instead of answering
/// "not in the index" while the Build has not yet published N.
pub struct WVariant {
    pub build_locked: bool,
    pub delete_under_lock: bool,
}

pub open spec fn as_built_writers() -> WVariant { WVariant { build_locked: false, delete_under_lock: false } }
pub open spec fn locked_build() -> WVariant { WVariant { build_locked: true, delete_under_lock: true } }
/// the round-1 repair alone (Build and Drop locked, Delete still tests N before the lock)
pub open spec fn round1_repair() -> WVariant { WVariant { build_locked: true, delete_under_lock: false } }

/// IndexDoc: postings, record and length go to the global; N, totalLen and vocab stay in Build's locals.
pub open spec fn index_doc(ix: Ix, d: Doc, bag: Map<Term, int>, dlen: int) -> Ix {
    let ix1 = add_postings(ix, d, bag);
    Ix { doc: ix1.doc.insert(d, bag.dom()), len: ix1.len.insert(d, dlen), ..ix1 }
}

/// What BuildFinish will publish.
pub open spec fn publish(ix: Ix, b: BuildRun) -> Ix {
    Ix { n: Some(b.bn), total: b.btotal, vocab: b.bvocab, schema: Some(2), ..ix }
}

/// TStart, init and RemoveDoc's loop, from the index as the writer finds it under the lock.
pub open spec fn begin_run(ix: Ix, d: Doc, bag: Map<Term, int>, dlen: int) -> (Ix, WRun) {
    let ix0 = init_ix(ix);
    let run = WRun {
        pre: ix, d, bag, dlen,
        present: present(ix0, d),
        old_len: lenv(ix0, d),
        rec: rec_of(ix0, d),
        phase: Phase::Removed,
    };
    (if present(ix0, d) { remove_postings(ix0, d, rec_of(ix0, d)) } else { ix0 }, run)
}

pub open spec fn wstep(s: WSys, a: WAct, v: WVariant) -> Option<WSys> {
    match a {
        WAct::InsBegin { d, bag, dlen } =>
            if !tok_ok(bag, dlen) || s.run is Some || (v.build_locked && s.build is Some) || !writable(s.ix) {
                None
            } else {
                let b = begin_run(s.ix, d, bag, dlen);
                Some(WSys { ix: b.0, run: Some(b.1), ..s })
            },
        WAct::DelBegin { d } =>
            if v.delete_under_lock && (s.run is Some || (v.build_locked && s.build is Some)) {
                None  // the repair: LockWrite before the existence test, so it waits
            } else if s.ix.n is None {
                Some(WSys { gone: s.gone.insert(d), ..s })  // returns 0 without locking (l.498)
            } else if s.run is Some || (v.build_locked && s.build is Some) || !writable(s.ix) {
                None
            } else {
                let b = begin_run(s.ix, d, Map::empty(), 0);
                Some(WSys { ix: b.0, run: Some(b.1), ..s })
            },
        WAct::WTail =>
            match s.run {
                Some(r) => if r.phase != Phase::Removed { None } else {
                    Some(WSys {
                        ix: if r.present { remove_tail(s.ix, r.d, r.old_len) } else { s.ix },
                        run: Some(WRun { phase: Phase::Tailed, ..r }),
                        ..s
                    })
                },
                None => None,
            },
        WAct::WAdd =>
            match s.run {
                Some(r) => if r.phase != Phase::Tailed { None } else {
                    Some(WSys {
                        ix: if r.dlen > 0 { add_body(s.ix, r.d, r.bag, r.dlen) } else { s.ix },
                        run: Some(WRun { phase: Phase::Added, ..r }),
                        ..s
                    })
                },
                None => None,
            },
        WAct::WCommit =>
            match s.run {
                Some(r) => if r.phase != Phase::Added || (r.dlen > 0 && s.ix.n is None) { None } else {
                    Some(WSys {
                        ix: if r.dlen > 0 { add_counters(s.ix, r.dlen) } else { s.ix },
                        run: None,
                        gone: if r.dlen > 0 { s.gone.remove(r.d) } else { s.gone.insert(r.d) },
                        ..s
                    })
                },
                None => None,
            },
        WAct::WriteFails => Some(s),
        WAct::BuildKill =>
            if s.build is Some || (v.build_locked && s.run is Some) {
                None  // one Build of a name at a time (modelling bound, see NOTES)
            } else {
                Some(WSys { ix: absent_ix(), build: Some(BuildRun { bn: 0, btotal: 0, bvocab: 0, seen: Set::empty() }), ..s })
            },
        WAct::BuildDoc { d, bag, dlen } =>
            match s.build {
                Some(b) =>
                    if !tok_ok(bag, dlen) || dlen <= 0 || b.seen.contains(d) {
                        None  // the scan flushes each node once (ORDER BY node_id); docLen 0 is skipped
                    } else {
                        Some(WSys {
                            ix: index_doc(s.ix, d, bag, dlen),
                            build: Some(BuildRun {
                                bn: b.bn + 1,
                                btotal: b.btotal + dlen,
                                bvocab: b.bvocab + fresh_terms(s.ix, bag).len(),
                                seen: b.seen.insert(d),
                            }),
                            gone: s.gone.remove(d),
                            ..s
                        })
                    },
                None => None,
            },
        WAct::BuildFinish =>
            match s.build {
                Some(b) => Some(WSys { ix: publish(s.ix, b), build: None, ..s }),
                None => None,
            },
        WAct::Drop =>
            if v.build_locked && (s.build is Some || s.run is Some) {
                None
            } else {
                Some(WSys { ix: absent_ix(), ..s })
            },
    }
}

/// The index an undisturbed transaction has produced at its current phase.
pub open spec fn after_tail(r: WRun) -> Ix {
    let b = begin_run(r.pre, r.d, r.bag, r.dlen).0;
    if r.present { remove_tail(b, r.d, r.old_len) } else { b }
}

pub open spec fn after_add(r: WRun) -> Ix {
    if r.dlen > 0 { add_body(after_tail(r), r.d, r.bag, r.dlen) } else { after_tail(r) }
}

pub open spec fn stage(r: WRun) -> Ix {
    match r.phase {
        Phase::Removed => begin_run(r.pre, r.d, r.bag, r.dlen).0,
        Phase::Tailed => after_tail(r),
        Phase::Added => after_add(r),
    }
}

pub open spec fn run_ok(r: WRun) -> bool {
    &&& cons(r.pre)
    &&& writable(r.pre)
    &&& tok_ok(r.bag, r.dlen)
    &&& r.present == present(init_ix(r.pre), r.d)
    &&& r.old_len == lenv(init_ix(r.pre), r.d)
    &&& r.rec == rec_of(init_ix(r.pre), r.d)
}

/// Invariant (repair): nothing in flight -> the index is consistent (L1); a Build in flight -> what
/// it will publish is consistent and its scan has flushed exactly the documents the global holds; a
/// writer transaction in flight -> the global is exactly that transaction's partial state.
pub open spec fn winv(s: WSys) -> bool {
    match (s.build, s.run) {
        (None, None) => cons(s.ix),
        (Some(b), None) => cons_present(publish(s.ix, b)) && b.seen == s.ix.len.dom(),
        (None, Some(r)) => run_ok(r) && s.ix == stage(r),
        (Some(_), Some(_)) => false,
    }
}

pub proof fn lemma_tok_empty()
    ensures
        tok_ok(Map::<Term, int>::empty(), 0),
{
    assert(Map::<Term, int>::empty().dom() =~= Set::<Term>::empty());
}

/// O1 with the repair: when Build and Drop take the index write lock, every reachable state with no
/// transaction in flight is consistent, and a writer's transaction runs on its own partial state — so
/// neither a Build nor a Drop can land inside an Insert or Delete (the step relation splits Insert
/// and Delete at RemoveDoc's loop, its tail, the add loop and TCommit).
pub proof fn theorem_locked_build_preserves(s: WSys, a: WAct)
    requires
        winv(s),
        wstep(s, a, locked_build()) is Some,
    ensures
        winv(wstep(s, a, locked_build())->Some_0),
{
    let v = locked_build();
    let s2 = wstep(s, a, v)->Some_0;
    match a {
        WAct::InsBegin { d, bag, dlen } => {
            let r = s2.run->Some_0;
            assert(s2.ix == stage(r));
        },
        WAct::DelBegin { d } => {
            if s.ix.n is Some {
                lemma_tok_empty();
                let r = s2.run->Some_0;
                assert(s2.ix == stage(r));
            }
        },
        WAct::WTail => {
            let r = s.run->Some_0;
            let r2 = s2.run->Some_0;
            assert(s2.ix == stage(r2));
        },
        WAct::WAdd => {
            let r = s.run->Some_0;
            let r2 = s2.run->Some_0;
            assert(s2.ix == stage(r2));
        },
        WAct::WCommit => {
            let r = s.run->Some_0;
            theorem_insert_preserves_counters(r.pre, r.d, r.bag, r.dlen);
            assert(remove_doc(init_ix(r.pre), r.d) == after_tail(r));
            assert(s2.ix == insert_body(r.pre, r.d, r.bag, r.dlen));
        },
        WAct::WriteFails => {},
        WAct::BuildKill => {
            lemma_absent_init_cons(absent_ix());
            let b = s2.build->Some_0;
            assert(publish(s2.ix, b) == Ix { n: Some(0), total: 0, vocab: 0, schema: Some(2), ..absent_ix() });
            assert(s2.ix.len.dom() =~= Set::<Doc>::empty());
        },
        WAct::BuildDoc { d, bag, dlen } => {
            let b = s.build->Some_0;
            let p = publish(s.ix, b);
            lemma_add_doc_preserves(p, d, bag, dlen);
            let b2 = s2.build->Some_0;
            assert(fresh_terms(p, bag) == fresh_terms(s.ix, bag));
            assert(add_postings(p, d, bag).tf =~= add_postings(s.ix, d, bag).tf);
            assert(add_postings(p, d, bag).df =~= add_postings(s.ix, d, bag).df);
            assert(publish(s2.ix, b2) == add_doc(p, d, bag, dlen));
            assert(b2.seen =~= s2.ix.len.dom());
        },
        WAct::BuildFinish => {},
        WAct::Drop => {},
    }
}

pub proof fn lemma_init_winv()
    ensures
        winv(WSys { ix: absent_ix(), build: None, run: None, gone: Set::empty() }),
{
}

// ---------------------------------------------------------------------------- witnesses (Build and Drop without the lock)

pub open spec fn bag1(t: Term) -> Map<Term, int> { Map::empty().insert(t, 1int) }

pub proof fn lemma_bag1_tok(t: Term)
    ensures
        tok_ok(bag1(t), 1),
{
    let b = bag1(t);
    assert(b.dom() =~= Set::<Term>::empty().insert(t));
    lemma_sumf_insert(|u: Term| b[u], Set::<Term>::empty(), t);
    assert(b.dom().len() == 1);
}

/// One complete Insert transaction with nothing interleaved: InsBegin, WTail, WAdd, WCommit.
pub open spec fn insert_steps(s: WSys, d: Doc, bag: Map<Term, int>, dlen: int, v: WVariant) -> Option<WSys> {
    match wstep(s, WAct::InsBegin { d, bag, dlen }, v) {
        Some(s1) => match wstep(s1, WAct::WTail, v) {
            Some(s2) => match wstep(s2, WAct::WAdd, v) {
                Some(s3) => wstep(s3, WAct::WCommit, v),
                None => None,
            },
            None => None,
        },
        None => None,
    }
}

/// W-O1a (F2): Build's Kill, then an Insert of a document Build will not scan (another graph's
/// node, or one created after the scan), then Build indexes its document and publishes its own
/// local counts. With nothing in flight the committed index has N = 1 and two documents.
pub proof fn witness_build_insert_breaks_n() {
    let v = as_built_writers();
    let s0 = WSys { ix: absent_ix(), build: None, run: None, gone: Set::empty() };
    lemma_bag1_tok(7);
    let s1 = wstep(s0, WAct::BuildKill, v)->Some_0;
    assert(writable(s1.ix));
    assert(insert_steps(s1, 2, bag1(7), 1, v) is Some);
    let s2 = insert_steps(s1, 2, bag1(7), 1, v)->Some_0;
    assert(s2.ix.len.contains_key(2));
    assert(s2.run is None);
    assert(!s2.build->Some_0.seen.contains(1));
    let s3 = wstep(s2, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, v)->Some_0;
    assert(wstep(s2, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, v) is Some);
    let s4 = wstep(s3, WAct::BuildFinish, v)->Some_0;
    assert(s4.build is None && s4.run is None);
    assert(s4.ix.n == Some(1int));
    assert(s4.ix.len.contains_key(1) && s4.ix.len.contains_key(2));
    lemma_two_elems_len(s4.ix.len.dom(), 1, 2);
    assert(!cons(s4.ix));
    assert(!winv(s4));
}

/// W-O1b (F2): an Insert of the same document between Build's Kill and Build's IndexDoc counts it
/// twice in df (FR-016 violated at a committed point with nothing in flight); a later Delete of the
/// document leaves df(7) = 1 for a term no document contains.
pub proof fn witness_build_insert_double_df() {
    let v = as_built_writers();
    let s0 = WSys { ix: absent_ix(), build: None, run: None, gone: Set::empty() };
    lemma_bag1_tok(7);
    let s1 = wstep(s0, WAct::BuildKill, v)->Some_0;
    assert(insert_steps(s1, 1, bag1(7), 1, v) is Some);
    let s2 = insert_steps(s1, 1, bag1(7), 1, v)->Some_0;
    assert(s2.ix.df.contains_key(7) && s2.ix.df[7] == 1);
    let s3 = wstep(s2, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, v)->Some_0;
    assert(wstep(s2, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, v) is Some);
    let s4 = wstep(s3, WAct::BuildFinish, v)->Some_0;
    assert(s4.ix.df[7] == 2);
    assert(s4.ix.tf[7].dom() =~= Set::<Doc>::empty().insert(1));
    assert(s4.ix.tf[7].dom().len() == 1);
    assert(!cons(s4.ix));
    // the damage persists through the locked writers: Delete(1) is admitted and leaves a phantom df
    assert(writable(s4.ix));
    let s5 = wstep(s4, WAct::DelBegin { d: 1 }, v)->Some_0;
    assert(wstep(s4, WAct::DelBegin { d: 1 }, v) is Some);
    assert(s4.ix.doc[1] =~= Set::<Term>::empty().insert(7));
    assert(s4.ix.tf[7].dom().remove(1) =~= Set::<Doc>::empty());
    let s6 = wstep(s5, WAct::WTail, v)->Some_0;
    let s7 = wstep(s6, WAct::WAdd, v)->Some_0;
    let s8 = wstep(s7, WAct::WCommit, v)->Some_0;
    assert(wstep(s7, WAct::WCommit, v) is Some);
    assert(s8.run is None && s8.build is None);
    assert(!s8.ix.tf.contains_key(7));
    assert(s8.ix.df.contains_key(7) && s8.ix.df[7] == 1);
    assert(!cons(s8.ix));
}

/// W-O1c (F2, Drop): a trace of the step relation. Two Inserts build a consistent index {1: 7, 2: 8};
/// an Insert replacing document 1 runs RemoveDoc's loop; Drop's Kill (no lock) lands; the Insert's
/// remaining statements all succeed (RemoveDoc reads N and totalLen with +$Get, then N exists again
/// for l.482) and it commits: the dropped index exists again with N = 0, one document and no schema
/// (so writers are then refused as "schema 1"). Needs no rollback premise.
pub proof fn witness_drop_inside_insert() {
    let v = as_built_writers();
    lemma_bag1_tok(7);
    lemma_bag1_tok(8);
    lemma_bag1_tok(9);
    let s0 = WSys { ix: absent_ix(), build: None, run: None, gone: Set::empty() };
    assert(insert_steps(s0, 1, bag1(7), 1, v) is Some);
    let sa = insert_steps(s0, 1, bag1(7), 1, v)->Some_0;
    theorem_insert_preserves_counters(s0.ix, 1, bag1(7), 1);
    assert(sa.ix == insert_body(s0.ix, 1, bag1(7), 1));
    assert(insert_steps(sa, 2, bag1(8), 1, v) is Some);
    let sb = insert_steps(sa, 2, bag1(8), 1, v)->Some_0;
    theorem_insert_preserves_counters(sa.ix, 2, bag1(8), 1);
    assert(sb.ix == insert_body(sa.ix, 2, bag1(8), 1));
    assert(cons(sb.ix) && sb.run is None && sb.build is None);
    assert(sb.ix.len.contains_key(1) && sb.ix.len[1] == 1);
    // Insert(1, "nine") under the lock: TStart and RemoveDoc's loop over the record {7}
    let s1 = wstep(sb, WAct::InsBegin { d: 1, bag: bag1(9), dlen: 1 }, v)->Some_0;
    assert(wstep(sb, WAct::InsBegin { d: 1, bag: bag1(9), dlen: 1 }, v) is Some);
    assert(s1.run->Some_0.present && s1.run->Some_0.old_len == 1);
    // Drop in another process
    let s2 = wstep(s1, WAct::Drop, v)->Some_0;
    assert(wstep(s1, WAct::Drop, v) is Some);
    assert(s2.ix == absent_ix());
    // the rest of the Insert
    let s3 = wstep(s2, WAct::WTail, v)->Some_0;
    let s4 = wstep(s3, WAct::WAdd, v)->Some_0;
    assert(s4.ix.n == Some(-1int));
    assert(wstep(s4, WAct::WCommit, v) is Some);
    let s5 = wstep(s4, WAct::WCommit, v)->Some_0;
    assert(s5.run is None && s5.build is None);
    assert(s5.ix.n == Some(0int));
    assert(s5.ix.len.dom() =~= Set::<Doc>::empty().insert(1));
    assert(s5.ix.len.dom().len() == 1);
    assert(!is_absent(s5.ix));
    assert(!cons(s5.ix));
    assert(schema_of(s5.ix) == 1);
    assert(!winv(s5));
}

// ---------------------------------------------------------------------------- a returned Delete takes effect (review R2-1)

/// L1 (spec 044 FR-019/FR-021 — Delete is atomic and exclusive like Insert; `bm25_delete` "Returns True
/// if it was in the index, False if it was not or the index does not exist"): once a Delete of d has
/// returned, d is not in the index until a later write puts it back (an Insert of d, or a Build that
/// scans d after the delete). The only exception is an Insert of d whose add loop has run and whose
/// TCommit has not yet (it will take d out of `gone`).
pub open spec fn gone_ok(s: WSys) -> bool {
    forall|d: Doc| #[trigger] s.gone.contains(d) ==> !s.ix.len.contains_key(d)
        || (s.run is Some && s.run->Some_0.d == d && s.run->Some_0.dlen > 0 && s.run->Some_0.phase == Phase::Added)
}

/// With the full repair (Build and Drop take the lock; Delete takes it before testing cfg N), a
/// Delete that has returned stays in effect: no Build publishes the deleted document unless it
/// scanned it after the delete.
pub proof fn theorem_repair_delete_takes_effect(s: WSys, a: WAct)
    requires
        winv(s),
        gone_ok(s),
        wstep(s, a, locked_build()) is Some,
    ensures
        gone_ok(wstep(s, a, locked_build())->Some_0),
{
    let v = locked_build();
    let s2 = wstep(s, a, v)->Some_0;
    match a {
        WAct::InsBegin { d, bag, dlen } => {
            assert forall|e: Doc| #[trigger] s2.gone.contains(e) implies !s2.ix.len.contains_key(e) by {
                assert(s.gone.contains(e));
                assert(s2.ix.len == init_ix(s.ix).len);
            }
        },
        WAct::DelBegin { d } => {
            if s.ix.n is None {
                assert(s.run is None && s.build is None);
                assert(is_absent(s.ix));
                assert forall|e: Doc| #[trigger] s2.gone.contains(e) implies !s2.ix.len.contains_key(e) by {
                    assert(s.ix.len.dom() =~= Set::<Doc>::empty());
                }
            } else {
                assert forall|e: Doc| #[trigger] s2.gone.contains(e) implies !s2.ix.len.contains_key(e) by {
                    assert(s.gone.contains(e));
                    assert(s2.ix.len == s.ix.len);
                }
            }
        },
        WAct::WTail => {
            let r = s.run->Some_0;
            assert forall|e: Doc| #[trigger] s2.gone.contains(e) implies !s2.ix.len.contains_key(e) by {
                assert(s.gone.contains(e));
            }
        },
        WAct::WAdd => {
            let r = s.run->Some_0;
            assert forall|e: Doc| #[trigger] s2.gone.contains(e) implies !s2.ix.len.contains_key(e)
                || (s2.run is Some && s2.run->Some_0.d == e && s2.run->Some_0.dlen > 0 && s2.run->Some_0.phase == Phase::Added) by {
                assert(s.gone.contains(e));
                if r.dlen > 0 && e != r.d {
                    assert(s2.ix.len == s.ix.len.insert(r.d, r.dlen));
                }
            }
        },
        WAct::WCommit => {
            let r = s.run->Some_0;
            assert(s.ix == after_add(r));
            assert forall|e: Doc| #[trigger] s2.gone.contains(e) implies !s2.ix.len.contains_key(e) by {
                if r.dlen > 0 {
                    assert(e != r.d);
                    assert(s.gone.contains(e));
                    assert(s2.ix.len == s.ix.len);
                } else if e == r.d {
                    assert(s.ix == after_tail(r));
                    if r.present {
                        assert(!s.ix.len.contains_key(r.d));
                    } else {
                        assert(!present(init_ix(r.pre), r.d));
                        assert(s.ix.len == init_ix(r.pre).len);
                    }
                } else {
                    assert(s.gone.contains(e));
                }
            }
        },
        WAct::WriteFails => {},
        WAct::BuildKill => {
            assert forall|e: Doc| #[trigger] s2.gone.contains(e) implies !s2.ix.len.contains_key(e) by {
                assert(s2.ix.len.dom() =~= Set::<Doc>::empty());
            }
        },
        WAct::BuildDoc { d, bag, dlen } => {
            assert forall|e: Doc| #[trigger] s2.gone.contains(e) implies !s2.ix.len.contains_key(e) by {
                assert(e != d);
                assert(s.gone.contains(e));
            }
        },
        WAct::BuildFinish => {
            assert forall|e: Doc| #[trigger] s2.gone.contains(e) implies !s2.ix.len.contains_key(e) by {
                assert(s.gone.contains(e));
            }
        },
        WAct::Drop => {
            assert forall|e: Doc| #[trigger] s2.gone.contains(e) implies !s2.ix.len.contains_key(e) by {
                assert(s2.ix.len.dom() =~= Set::<Doc>::empty());
            }
        },
    }
}

pub proof fn lemma_init_gone_ok()
    ensures
        gone_ok(WSys { ix: absent_ix(), build: None, run: None, gone: Set::empty() }),
{
}

/// The build-delete-publish history shared by the two witnesses below: a consistent index holding
/// document 1, a Build's Kill, the Build's scan flushing document 1, then a Delete of document 1.
pub proof fn lemma_delete_during_build_trace(v: WVariant)
    requires
        !v.delete_under_lock,
    ensures ({
        let s0 = WSys { ix: absent_ix(), build: None, run: None, gone: Set::empty() };
        let sa = insert_steps(s0, 1, bag1(7), 1, v);
        &&& sa is Some
        &&& wstep(sa->Some_0, WAct::BuildKill, v) is Some
        &&& wstep(wstep(sa->Some_0, WAct::BuildKill, v)->Some_0, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, v) is Some
    }),
{
    lemma_bag1_tok(7);
    let s0 = WSys { ix: absent_ix(), build: None, run: None, gone: Set::empty() };
    assert(insert_steps(s0, 1, bag1(7), 1, v) is Some);
}

/// W-O1e (R2-1, as built): a Delete issued while a Build is in flight answers 0 ("not in the index")
/// without taking the lock, because Build sets cfg N only after its scan (l.160) and Delete tests N
/// first (l.498). The Build's scan had already flushed the document, and BuildFinish publishes it:
/// with nothing in flight, the deleted document is in the index.
pub proof fn witness_delete_during_build_lost() {
    let v = as_built_writers();
    lemma_delete_during_build_trace(v);
    lemma_bag1_tok(7);
    let s0 = WSys { ix: absent_ix(), build: None, run: None, gone: Set::empty() };
    let sa = insert_steps(s0, 1, bag1(7), 1, v)->Some_0;
    let s1 = wstep(sa, WAct::BuildKill, v)->Some_0;
    let s2 = wstep(s1, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, v)->Some_0;
    assert(s2.ix.n is None);
    let s3 = wstep(s2, WAct::DelBegin { d: 1 }, v)->Some_0;
    assert(wstep(s2, WAct::DelBegin { d: 1 }, v) is Some);
    assert(s3.ix == s2.ix && s3.run is None && s3.gone.contains(1));
    let s4 = wstep(s3, WAct::BuildFinish, v)->Some_0;
    assert(s4.build is None && s4.run is None);
    assert(s4.ix.len.contains_key(1));
    assert(s4.gone.contains(1) && s4.run is None);
    assert(!gone_ok(s4));
}

/// The same history under the round-1 repair alone (Build and Drop take the lock): Delete still
/// tests N before the lock, so the delete is still lost — while the counter invariant `winv` holds
/// throughout. The counter repair does not make a returned delete take effect.
pub proof fn witness_round1_repair_loses_delete() {
    let v = round1_repair();
    lemma_delete_during_build_trace(v);
    lemma_bag1_tok(7);
    let s0 = WSys { ix: absent_ix(), build: None, run: None, gone: Set::empty() };
    let sa = insert_steps(s0, 1, bag1(7), 1, v)->Some_0;
    let s1 = wstep(sa, WAct::BuildKill, v)->Some_0;
    let s2 = wstep(s1, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, v)->Some_0;
    let s3 = wstep(s2, WAct::DelBegin { d: 1 }, v)->Some_0;
    assert(wstep(s2, WAct::DelBegin { d: 1 }, v) is Some);
    assert(s3.gone.contains(1));
    let s4 = wstep(s3, WAct::BuildFinish, v)->Some_0;
    assert(s4.ix.len.contains_key(1));
    assert(s4.gone.contains(1) && s4.run is None);
    assert(!gone_ok(s4));
    // the counters stay consistent throughout (winv): the counter repair is silent on this
    let l = locked_build();
    lemma_init_winv();
    let i1 = wstep(s0, WAct::InsBegin { d: 1, bag: bag1(7), dlen: 1 }, v)->Some_0;
    assert(wstep(s0, WAct::InsBegin { d: 1, bag: bag1(7), dlen: 1 }, l) == wstep(s0, WAct::InsBegin { d: 1, bag: bag1(7), dlen: 1 }, v));
    theorem_locked_build_preserves(s0, WAct::InsBegin { d: 1, bag: bag1(7), dlen: 1 });
    let i2 = wstep(i1, WAct::WTail, v)->Some_0;
    assert(wstep(i1, WAct::WTail, l) == wstep(i1, WAct::WTail, v));
    theorem_locked_build_preserves(i1, WAct::WTail);
    let i3 = wstep(i2, WAct::WAdd, v)->Some_0;
    assert(wstep(i2, WAct::WAdd, l) == wstep(i2, WAct::WAdd, v));
    theorem_locked_build_preserves(i2, WAct::WAdd);
    assert(wstep(i3, WAct::WCommit, l) == wstep(i3, WAct::WCommit, v));
    theorem_locked_build_preserves(i3, WAct::WCommit);
    assert(sa == wstep(i3, WAct::WCommit, v)->Some_0);
    assert(wstep(sa, WAct::BuildKill, l) == wstep(sa, WAct::BuildKill, v));
    theorem_locked_build_preserves(sa, WAct::BuildKill);
    assert(wstep(s1, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, l) == wstep(s1, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, v));
    theorem_locked_build_preserves(s1, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 });
    assert(winv(s2));
    assert(winv(s3));
    assert(wstep(s3, WAct::BuildFinish, l) == wstep(s3, WAct::BuildFinish, v));
    theorem_locked_build_preserves(s3, WAct::BuildFinish);
    assert(winv(s4) && cons(s4.ix));
}

/// Valid outcome survives the full repair: on the same history the Delete waits for the Build
/// (not enabled while it runs), then removes the published document.
pub proof fn witness_repair_delete_after_build() {
    let v = locked_build();
    lemma_bag1_tok(7);
    let s0 = WSys { ix: absent_ix(), build: None, run: None, gone: Set::empty() };
    assert(insert_steps(s0, 1, bag1(7), 1, v) is Some);
    let sa = insert_steps(s0, 1, bag1(7), 1, v)->Some_0;
    let s1 = wstep(sa, WAct::BuildKill, v)->Some_0;
    assert(wstep(sa, WAct::BuildKill, v) is Some);
    let s2 = wstep(s1, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, v)->Some_0;
    assert(wstep(s1, WAct::BuildDoc { d: 1, bag: bag1(7), dlen: 1 }, v) is Some);
    assert(wstep(s2, WAct::DelBegin { d: 1 }, v) is None);
    let s3 = wstep(s2, WAct::BuildFinish, v)->Some_0;
    assert(writable(s3.ix));
    let s4 = wstep(s3, WAct::DelBegin { d: 1 }, v)->Some_0;
    assert(wstep(s3, WAct::DelBegin { d: 1 }, v) is Some);
    let s5 = wstep(s4, WAct::WTail, v)->Some_0;
    let s6 = wstep(s5, WAct::WAdd, v)->Some_0;
    assert(wstep(s6, WAct::WCommit, v) is Some);
    let s7 = wstep(s6, WAct::WCommit, v)->Some_0;
    assert(s7.run is None && s7.build is None);
    assert(!s7.ix.len.contains_key(1));
    assert(s7.gone.contains(1));
}

/// TRollback (premise P_undo, IRIS journal semantics): each node the rolled-back transaction wrote
/// gets back the value it had when that transaction first wrote it, whatever another process wrote
/// there since. An Insert of d writes tf(t,d) and df(t) for t in `terms`, doc(d), len(d) and cfg N,
/// totalLen and vocab_size.
pub open spec fn restored_post(cur: Ix, pre: Ix, d: Doc, t: Term) -> Map<Doc, int> {
    if pre.tf.contains_key(t) && pre.tf[t].contains_key(d) {
        posting(cur, t).insert(d, pre.tf[t][d])
    } else {
        posting(cur, t).remove(d)
    }
}

pub open spec fn undo(cur: Ix, pre: Ix, d: Doc, terms: Set<Term>) -> Ix {
    Ix {
        tf: Map::new(
            cur.tf.dom().union(terms).filter(|t: Term| !terms.contains(t) || restored_post(cur, pre, d, t).dom().len() > 0),
            |t: Term| if terms.contains(t) { restored_post(cur, pre, d, t) } else { cur.tf[t] },
        ),
        df: Map::new(
            cur.df.dom().union(terms).filter(|t: Term| !terms.contains(t) || pre.df.contains_key(t)),
            |t: Term| if terms.contains(t) { pre.df[t] } else { cur.df[t] },
        ),
        doc: if pre.doc.contains_key(d) { cur.doc.insert(d, pre.doc[d]) } else { cur.doc.remove(d) },
        len: if pre.len.contains_key(d) { cur.len.insert(d, pre.len[d]) } else { cur.len.remove(d) },
        n: pre.n,
        total: pre.total,
        vocab: pre.vocab,
        ..cur
    }
}

/// W-O1d (F3, conditional; NOT a trace of `wstep`, which has no caller transactions): the model's
/// functions composed as an Insert inside a caller's transaction whose `Lock -` releases the lock at
/// the inner TCommit (premise P_unlock_in_txn), a second writer committing on top, and the caller's
/// rollback (P_undo). The result would have a posting for term 7 and no df(7). Native probe
/// search_bm25_caller_txn_lock observed that IRIS keeps the lock until the caller's transaction ends,
/// so P_unlock_in_txn is false and this branch is not reachable.
pub proof fn witness_caller_txn_rollback() {
    lemma_bag1_tok(7);
    let s0 = Ix { n: Some(0), total: 0, vocab: 0, schema: Some(2), ..absent_ix() };
    lemma_absent_init_cons(absent_ix());
    assert(cons(s0) && writable(s0));
    let s1 = insert_body(s0, 1, bag1(7), 1);
    theorem_insert_preserves_counters(s0, 1, bag1(7), 1);
    assert(writable(s1));
    let s2 = insert_body(s1, 2, bag1(7), 1);
    theorem_insert_preserves_counters(s1, 2, bag1(7), 1);
    let terms = Set::<Term>::empty().insert(7);
    let s3 = undo(s2, s0, 1, terms);
    assert(s2.tf.contains_key(7) && s2.tf[7].contains_key(2));
    assert(restored_post(s2, s0, 1, 7).contains_key(2));
    assert(s3.tf.contains_key(7));
    assert(!s3.df.contains_key(7));
    assert(!cons(s3));
}

// ============================================================================ O2: schema-1 -> schema-2 upgrade

pub open spec fn has_posting(ix: Ix, d: Doc) -> bool {
    exists|t: Term| #[trigger] ix.tf.contains_key(t) && ix.tf[t].contains_key(d)
}

pub open spec fn terms_of(ix: Ix, d: Doc) -> Set<Term> {
    ix.tf.dom().filter(|t: Term| ix.tf[t].contains_key(d))
}

/// Premise P_s1 (what schema-1 Build/Insert left, and what every later writer keeps): tf and len
/// agree. It is what Upgrade reads; df, doc, N, totalLen and vocab_size are not trusted.
pub open spec fn s1ok(ix: Ix) -> bool {
    &&& forall|t: Term| #[trigger] ix.tf.contains_key(t) ==> ix.tf[t].dom().len() > 0
    &&& forall|t: Term, d: Doc| #[trigger] ix.tf.contains_key(t) && #[trigger] ix.tf[t].contains_key(d)
            ==> ix.tf[t][d] > 0 && ix.len.contains_key(d)
    &&& forall|d: Doc| #[trigger] ix.len.contains_key(d) ==> ix.len[d] > 0 && has_posting(ix, d)
            && ix.len[d] == sumf(|t: Term| tfv(ix, t, d), terms_of(ix, d))
}

/// Upgrade l.542-558: Kill df and doc, then one walk of tf rebuilds both.
pub open spec fn rebuilt(ix: Ix) -> Ix {
    Ix {
        df: Map::new(ix.tf.dom(), |t: Term| ix.tf[t].dom().len() as int),
        doc: Map::new(ix.len.dom().filter(|d: Doc| has_posting(ix, d)), |d: Doc| terms_of(ix, d)),
        ..ix
    }
}

/// Upgrade l.559-568: N and totalLen from a walk of len; vocab_size from the tf walk.
pub open spec fn counted(ix: Ix) -> Ix {
    Ix { n: Some(ix.len.dom().len() as int), total: total_of(ix.len), vocab: ix.df.dom().len() as int, ..ix }
}

pub proof fn lemma_cons_gives_s1ok(ix: Ix)
    requires
        cons(ix),
    ensures
        s1ok(ix),
{
    if is_absent(ix) {
        assert(ix.len.dom() =~= Set::<Doc>::empty());
        assert(ix.tf.dom() =~= Set::<Term>::empty());
        return;
    }
    assert forall|d: Doc| #[trigger] ix.len.contains_key(d) implies ix.len[d] > 0 && has_posting(ix, d)
        && ix.len[d] == sumf(|t: Term| tfv(ix, t, d), terms_of(ix, d)) by {
        assert(ix.doc.contains_key(d));
        assert(terms_of(ix, d) =~= ix.doc[d]);
        if ix.doc[d].len() == 0 {
            assert(sumf(|t: Term| tfv(ix, t, d), ix.doc[d]) == 0);
        }
        let t = ix.doc[d].choose();
        assert(ix.doc[d].contains(t));
        assert(ix.tf.contains_key(t) && ix.tf[t].contains_key(d));
    }
}

pub proof fn lemma_s1ok_frame(a: Ix, b: Ix)
    requires
        s1ok(a),
        a.tf == b.tf,
        a.len == b.len,
    ensures
        s1ok(b),
{
    assert forall|d: Doc| #[trigger] b.len.contains_key(d) implies b.len[d] > 0 && has_posting(b, d)
        && b.len[d] == sumf(|t: Term| tfv(b, t, d), terms_of(b, d)) by {
        assert(terms_of(a, d) =~= terms_of(b, d));
        lemma_sumf_ext(|t: Term| tfv(a, t, d), |t: Term| tfv(b, t, d), terms_of(a, d));
        let t = choose|t: Term| #[trigger] a.tf.contains_key(t) && a.tf[t].contains_key(d);
        assert(b.tf.contains_key(t) && b.tf[t].contains_key(d));
    }
}

/// cons and cons_present read tf, df, doc, len, N, totalLen and vocab_size only.
pub proof fn lemma_cons_frame(a: Ix, b: Ix)
    requires
        a.tf == b.tf,
        a.df == b.df,
        a.doc == b.doc,
        a.len == b.len,
        a.n == b.n,
        a.total == b.total,
        a.vocab == b.vocab,
    ensures
        cons_present(a) ==> cons_present(b),
        cons(a) ==> cons(b),
{
    if cons_present(a) {
        assert forall|d: Doc| #[trigger] b.doc.contains_key(d) implies b.len[d] > 0 && b.len[d] == doc_len_of(b, d) by {
            lemma_sumf_ext(|t: Term| tfv(a, t, d), |t: Term| tfv(b, t, d), a.doc[d]);
        }
    }
}

pub proof fn lemma_rebuild_count_cons(ix: Ix)
    requires
        s1ok(ix),
    ensures
        cons_present(counted(rebuilt(ix))),
        counted(rebuilt(ix)).tf == ix.tf,
        counted(rebuilt(ix)).len == ix.len,
{
    let r = rebuilt(ix);
    let c = counted(r);
    assert(c.df.dom() == ix.tf.dom());
    assert(c.doc.dom() =~= ix.len.dom());
    assert forall|t: Term, d: Doc| #[trigger] c.tf.contains_key(t) && #[trigger] c.tf[t].contains_key(d)
        implies c.tf[t][d] > 0 && c.doc.contains_key(d) && c.doc[d].contains(t) by {
        assert(ix.len.contains_key(d));
        assert(has_posting(ix, d));
        assert(c.doc[d] == terms_of(ix, d));
    }
    assert forall|d: Doc, t: Term| #[trigger] c.doc.contains_key(d) && #[trigger] c.doc[d].contains(t)
        implies c.tf.contains_key(t) && c.tf[t].contains_key(d) by {
        assert(c.doc[d] == terms_of(ix, d));
    }
    assert forall|d: Doc| #[trigger] c.doc.contains_key(d) implies c.len[d] > 0 && c.len[d] == doc_len_of(c, d) by {
        assert(c.doc[d] == terms_of(ix, d));
        lemma_sumf_ext(|t: Term| tfv(c, t, d), |t: Term| tfv(ix, t, d), terms_of(ix, d));
    }
    assert forall|t: Term| #[trigger] c.df.contains_key(t) implies c.df[t] == c.tf[t].dom().len() by {}
}

pub enum UpPc {
    /// l.533: "upgrading" set, waiting for the lock
    Flagged,
    /// l.535-542: holds the lock; df and doc killed
    Killed,
    /// l.543-558: df and doc rebuilt
    Rebuilt,
    /// l.566-568: N, totalLen, vocab_size written
    Counted,
    /// l.570: schema = 2
    Flipped,
    /// l.571-572: idf and avgdl killed
    Cleaned,
}

pub struct USys {
    pub ix: Ix,
    /// Lock ^BM25Idx(x,"lock") holder (writers acquire and release it inside their atomic step)
    pub lock: Option<nat>,
    /// Upgrade calls in flight, by process
    pub ups: Map<nat, UpPc>,
}

pub enum UAct {
    Start { p: nat },
    LockKill { p: nat },
    Timeout { p: nat },
    Rebuild { p: nat },
    Count { p: nat },
    Flip { p: nat },
    Clean { p: nat },
    Done { p: nat },
    /// an error inside the Try (l.573-576): Kill upgrading, unlock, rethrow
    Fail { p: nat },
    /// the process dies (halt, kill, shutdown): IRIS releases its locks; no Catch runs
    Crash { p: nat },
    Insert { d: Doc, bag: Map<Term, int>, dlen: int },
    Delete { d: Doc },
}

/// `recheck`: the proposed repair (re-read schema under the lock and skip the rebuild of a schema-2
/// index); `serial`: premise that an Upgrade starts only when no other Upgrade of the index is in
/// flight; `crash_after_flip`: whether a process may die between the flip and clearing the flag.
pub struct UVariant {
    pub recheck: bool,
    pub serial: bool,
    pub crash_after_flip: bool,
}

pub open spec fn upgrade_as_built() -> UVariant { UVariant { recheck: false, serial: true, crash_after_flip: false } }
pub open spec fn upgrade_concurrent() -> UVariant { UVariant { recheck: false, serial: false, crash_after_flip: false } }
pub open spec fn upgrade_crash_rerun() -> UVariant { UVariant { recheck: false, serial: true, crash_after_flip: true } }
pub open spec fn upgrade_repaired() -> UVariant { UVariant { recheck: true, serial: false, crash_after_flip: true } }

pub open spec fn holds_lock(pc: UpPc) -> bool { pc != UpPc::Flagged }

pub open spec fn ustep(s: USys, a: UAct, v: UVariant) -> Option<USys> {
    match a {
        UAct::Start { p } =>
            if s.ups.contains_key(p) || (v.serial && s.ups.dom().len() > 0) {
                None
            } else if s.ix.n is None {
                Some(s)  // {"upgraded":0,"missing":1}
            } else if schema_of(s.ix) >= 2 && !s.ix.upgrading {
                Some(s)  // {"upgraded":0,"already":1}
            } else {
                Some(USys { ix: Ix { upgrading: true, ..s.ix }, ups: s.ups.insert(p, UpPc::Flagged), ..s })
            },
        UAct::LockKill { p } =>
            if !s.ups.contains_key(p) || s.ups[p] != UpPc::Flagged || s.lock is Some {
                None
            } else if v.recheck && schema_of(s.ix) >= 2 {
                Some(USys { lock: Some(p), ups: s.ups.insert(p, UpPc::Flipped), ..s })
            } else {
                Some(USys {
                    ix: Ix { df: Map::empty(), doc: Map::empty(), ..s.ix },
                    lock: Some(p),
                    ups: s.ups.insert(p, UpPc::Killed),
                })
            },
        UAct::Timeout { p } =>
            if !s.ups.contains_key(p) || s.ups[p] != UpPc::Flagged || s.lock is None {
                None
            } else {
                Some(USys { ix: Ix { upgrading: false, ..s.ix }, ups: s.ups.remove(p), ..s })
            },
        UAct::Rebuild { p } =>
            if !s.ups.contains_key(p) || s.ups[p] != UpPc::Killed { None } else {
                Some(USys { ix: rebuilt(s.ix), ups: s.ups.insert(p, UpPc::Rebuilt), ..s })
            },
        UAct::Count { p } =>
            if !s.ups.contains_key(p) || s.ups[p] != UpPc::Rebuilt { None } else {
                Some(USys { ix: counted(s.ix), ups: s.ups.insert(p, UpPc::Counted), ..s })
            },
        UAct::Flip { p } =>
            if !s.ups.contains_key(p) || s.ups[p] != UpPc::Counted { None } else {
                Some(USys { ix: Ix { schema: Some(2), ..s.ix }, ups: s.ups.insert(p, UpPc::Flipped), ..s })
            },
        UAct::Clean { p } =>
            if !s.ups.contains_key(p) || s.ups[p] != UpPc::Flipped { None } else {
                Some(USys { ix: Ix { idf: false, ..s.ix }, ups: s.ups.insert(p, UpPc::Cleaned), ..s })
            },
        UAct::Done { p } =>
            if !s.ups.contains_key(p) || s.ups[p] != UpPc::Cleaned { None } else {
                Some(USys { ix: Ix { upgrading: false, ..s.ix }, lock: None, ups: s.ups.remove(p) })
            },
        UAct::Fail { p } =>
            if !s.ups.contains_key(p) || s.ups[p] == UpPc::Flagged { None } else {
                Some(USys { ix: Ix { upgrading: false, ..s.ix }, lock: None, ups: s.ups.remove(p) })
            },
        UAct::Crash { p } =>
            if !s.ups.contains_key(p) || (!v.crash_after_flip && (s.ups[p] == UpPc::Flipped || s.ups[p] == UpPc::Cleaned)) {
                None
            } else {
                Some(USys { lock: if s.lock == Some(p) { None } else { s.lock }, ups: s.ups.remove(p), ..s })
            },
        UAct::Insert { d, bag, dlen } =>
            if !tok_ok(bag, dlen) || s.lock is Some || !writable(s.ix) { None } else {
                Some(USys { ix: insert_body(s.ix, d, bag, dlen), ..s })
            },
        UAct::Delete { d } =>
            if s.ix.n is None { Some(s) } else if s.lock is Some || !writable(s.ix) { None } else {
                Some(USys { ix: remove_doc(s.ix, d), ..s })
            },
    }
}

pub open spec fn rebuilding(pc: UpPc) -> bool {
    pc == UpPc::Killed || pc == UpPc::Rebuilt || pc == UpPc::Counted
}

/// Shared part of the invariant (as-built under its premises, and the repair without them).
pub open spec fn uinv_core(s: USys) -> bool {
    &&& s1ok(s.ix)
    // FR-023 for readers: a Search that reads schema 2 reads a consistent index
    &&& (schema_of(s.ix) >= 2 ==> cons(s.ix))
    // the lock is held exactly by the upgrades past LockKill
    &&& forall|p: nat| #[trigger] s.ups.contains_key(p) ==> (holds_lock(s.ups[p]) <==> s.lock == Some(p))
    &&& (s.lock is Some ==> s.ups.contains_key(s.lock->Some_0) && holds_lock(s.ups[s.lock->Some_0]))
    // a rebuild runs on a schema-1 index
    &&& forall|p: nat| #[trigger] s.ups.contains_key(p) && rebuilding(s.ups[p]) ==> schema_of(s.ix) < 2
    &&& forall|p: nat| #[trigger] s.ups.contains_key(p) && s.ups[p] == UpPc::Rebuilt ==>
            s.ix.df == rebuilt(s.ix).df && s.ix.doc == rebuilt(s.ix).doc
    &&& forall|p: nat| #[trigger] s.ups.contains_key(p) && (s.ups[p] == UpPc::Counted || s.ups[p] == UpPc::Flipped
            || s.ups[p] == UpPc::Cleaned) ==> s.ix.n is Some && cons_present(s.ix)
    &&& (s.ups.dom().len() > 0 ==> s.ix.n is Some)
    &&& (s.ix.n is None ==> is_absent(s.ix) && !s.ix.upgrading)
}

/// As-built invariant (premises: serial Upgrades, no death between the flip and the flag's clear).
pub open spec fn uinv(s: USys) -> bool {
    &&& uinv_core(s)
    &&& forall|p: nat, q: nat| #[trigger] s.ups.contains_key(p) && #[trigger] s.ups.contains_key(q) ==> p == q
    // writers are refused from flag-set to flag-clear (FR-023)
    &&& (s.ups.dom().len() > 0 ==> s.ix.upgrading)
    &&& forall|p: nat| #[trigger] s.ups.contains_key(p) && s.ups[p] == UpPc::Flagged ==> schema_of(s.ix) < 2
    // a stale flag is only ever left on a schema-1 index
    &&& (s.ix.upgrading ==> schema_of(s.ix) < 2 || exists|p: nat| #[trigger] s.ups.contains_key(p)
            && (s.ups[p] == UpPc::Flipped || s.ups[p] == UpPc::Cleaned))
}

pub proof fn lemma_dom_nonempty<K, V>(m: Map<K, V>, k: K)
    requires
        m.contains_key(k),
    ensures
        m.dom().len() > 0,
{
    assert(m.dom().contains(k));
}

pub proof fn lemma_dom_empty<K, V>(m: Map<K, V>)
    requires
        m.dom().len() == 0,
    ensures
        forall|k: K| !(#[trigger] m.contains_key(k)),
{
    assert forall|k: K| !(#[trigger] m.contains_key(k)) by {
        if m.contains_key(k) { lemma_dom_nonempty(m, k); }
    }
}

pub proof fn theorem_upgrade_step_preserves(s: USys, a: UAct)
    requires
        uinv(s),
        ustep(s, a, upgrade_as_built()) is Some,
    ensures
        uinv(ustep(s, a, upgrade_as_built())->Some_0),
{
    let v = upgrade_as_built();
    let s2 = ustep(s, a, v)->Some_0;
    match a {
        UAct::Start { p } => {
            if s2 != s {
                lemma_dom_empty(s.ups);
                assert(s.lock is None);
                assert(schema_of(s.ix) < 2);
                assert forall|q: nat| #[trigger] s2.ups.contains_key(q) implies q == p by {}
                lemma_dom_nonempty(s2.ups, p);
            }
            lemma_s1ok_frame(s.ix, s2.ix);
            lemma_cons_frame(s.ix, s2.ix);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::LockKill { p } => {
            assert(schema_of(s.ix) < 2);
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) implies q == p by {}
            lemma_s1ok_frame(s.ix, s2.ix);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::Timeout { p } => {
            // only lock holders are upgrades, and there is one upgrade: p, which does not hold it
            assert(false);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::Rebuild { p } => {
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) implies q == p by {}
            assert(rebuilding(s.ups[p]));
            lemma_s1ok_frame(s.ix, s2.ix);
            assert(schema_of(s.ix) < 2);
            assert(schema_of(s2.ix) < 2);
            assert(s2.ix.tf == s.ix.tf && s2.ix.len == s.ix.len);
            assert(s2.ix.df =~= rebuilt(s2.ix).df);
            assert forall|d: Doc| has_posting(s2.ix, d) == has_posting(s.ix, d) by {}
            assert forall|d: Doc| terms_of(s2.ix, d) == terms_of(s.ix, d) by {
                assert(terms_of(s2.ix, d) =~= terms_of(s.ix, d));
            }
            assert(s.ix.len.dom().filter(|d: Doc| has_posting(s.ix, d)) =~= s2.ix.len.dom().filter(|d: Doc| has_posting(s2.ix, d)));
            assert(s2.ix.doc =~= rebuilt(s2.ix).doc);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::Count { p } => {
            assert(s.ix.df == rebuilt(s.ix).df && s.ix.doc == rebuilt(s.ix).doc);
            assert(rebuilt(s.ix) == s.ix);
            lemma_rebuild_count_cons(s.ix);
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) implies q == p by {}
            lemma_s1ok_frame(s.ix, s2.ix);
            assert(schema_of(s2.ix) < 2);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::Flip { p } => {
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) implies q == p by {}
            lemma_s1ok_frame(s.ix, s2.ix);
            lemma_cons_frame(s.ix, s2.ix);
            assert(s2.ups.contains_key(p) && s2.ups[p] == UpPc::Flipped);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::Clean { p } => {
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) implies q == p by {}
            lemma_s1ok_frame(s.ix, s2.ix);
            lemma_cons_frame(s.ix, s2.ix);
            assert(s2.ups.contains_key(p) && s2.ups[p] == UpPc::Cleaned);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::Done { p } => {
            assert forall|q: nat| !(#[trigger] s2.ups.contains_key(q)) by {}
            assert(s2.ups.dom() =~= Set::<nat>::empty());
            lemma_s1ok_frame(s.ix, s2.ix);
            lemma_cons_frame(s.ix, s2.ix);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::Fail { p } => {
            assert forall|q: nat| !(#[trigger] s2.ups.contains_key(q)) by {}
            assert(s2.ups.dom() =~= Set::<nat>::empty());
            lemma_s1ok_frame(s.ix, s2.ix);
            lemma_cons_frame(s.ix, s2.ix);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::Crash { p } => {
            assert forall|q: nat| !(#[trigger] s2.ups.contains_key(q)) by {}
            assert(s2.ups.dom() =~= Set::<nat>::empty());
            assert(schema_of(s.ix) < 2);
            lemma_s1ok_frame(s.ix, s2.ix);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::Insert { d, bag, dlen } => {
            assert(!s.ix.upgrading || s.ix.n is None);
            if s.ups.dom().len() > 0 {
                assert(s.ix.upgrading);
            }
            assert(s.ups.dom().len() == 0);
            lemma_dom_empty(s.ups);
            assert(cons(s.ix));
            theorem_insert_preserves_counters(s.ix, d, bag, dlen);
            lemma_cons_gives_s1ok(s2.ix);
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
        UAct::Delete { d } => {
            if s.ix.n is Some {
                assert(s.ups.dom().len() == 0);
                lemma_dom_empty(s.ups);
                theorem_delete_preserves_counters(s.ix, d);
                lemma_cons_gives_s1ok(s2.ix);
            }
            assert(s2.ix.upgrading ==> schema_of(s2.ix) < 2 || exists|q: nat| #[trigger] s2.ups.contains_key(q) && (s2.ups[q] == UpPc::Flipped || s2.ups[q] == UpPc::Cleaned));
            assert(uinv_core(s2));
        },
    }
}

pub proof fn lemma_rebuilt_frame(a: Ix, b: Ix)
    requires
        a.tf == b.tf,
        a.len == b.len,
    ensures
        rebuilt(a).df == rebuilt(b).df,
        rebuilt(a).doc == rebuilt(b).doc,
        counted(rebuilt(a)).n == counted(rebuilt(b)).n,
        counted(rebuilt(a)).total == counted(rebuilt(b)).total,
        counted(rebuilt(a)).vocab == counted(rebuilt(b)).vocab,
{
    assert(rebuilt(a).df =~= rebuilt(b).df);
    assert forall|d: Doc| has_posting(a, d) == has_posting(b, d) by {}
    assert forall|d: Doc| terms_of(a, d) == terms_of(b, d) by {
        assert(terms_of(a, d) =~= terms_of(b, d));
    }
    assert(a.len.dom().filter(|d: Doc| has_posting(a, d)) =~= b.len.dom().filter(|d: Doc| has_posting(b, d)));
    assert(rebuilt(a).doc =~= rebuilt(b).doc);
}

/// FR-023 "refuse writers while it runs": with an Upgrade in flight, Insert and Delete are refused
/// (the flag, checked before and under the lock) and change nothing.
pub proof fn theorem_writers_refused_while_upgrading(s: USys, d: Doc, bag: Map<Term, int>, dlen: int)
    requires
        uinv(s),
        s.ups.dom().len() > 0,
    ensures
        ustep(s, UAct::Insert { d, bag, dlen }, upgrade_as_built()) is None,
        ustep(s, UAct::Delete { d }, upgrade_as_built()) is None,
{
}

/// The index an uninterrupted Upgrade leaves: a function of tf and len alone.
pub open spec fn canonical(ix: Ix) -> Ix {
    Ix { schema: Some(2), upgrading: false, idf: false, ..counted(rebuilt(ix)) }
}

pub proof fn lemma_canonical_depends_on_tf_len(a: Ix, b: Ix)
    requires
        a.tf == b.tf,
        a.len == b.len,
    ensures
        canonical(a) == canonical(b),
{
    lemma_rebuilt_frame(a, b);
}

pub open spec fn then(o: Option<USys>, a: UAct, v: UVariant) -> Option<USys> {
    match o { Some(s) => ustep(s, a, v), None => None }
}

/// One Upgrade call by process p, start to finish, with nothing interleaved.
pub open spec fn run_upgrade(s: USys, p: nat, v: UVariant) -> Option<USys> {
    then(then(then(then(then(then(ustep(s, UAct::Start { p }, v),
        UAct::LockKill { p }, v), UAct::Rebuild { p }, v), UAct::Count { p }, v), UAct::Flip { p }, v),
        UAct::Clean { p }, v), UAct::Done { p }, v)
}

/// FR-023 "converts in one pass": an Upgrade that runs to the end leaves the canonical schema-2 index
/// (consistent, flag cleared, idf removed, lock free) computed from tf and len alone.
pub proof fn theorem_upgrade_completes(s: USys, p: nat)
    requires
        uinv(s),
        s.ups.dom().len() == 0,
        s.ix.n is Some,
        schema_of(s.ix) < 2 || s.ix.upgrading,
    ensures
        run_upgrade(s, p, upgrade_as_built()) is Some,
        run_upgrade(s, p, upgrade_as_built())->Some_0.ix == canonical(s.ix),
        cons(canonical(s.ix)),
        run_upgrade(s, p, upgrade_as_built())->Some_0.ups.dom().len() == 0,
        run_upgrade(s, p, upgrade_as_built())->Some_0.lock is None,
{
    let v = upgrade_as_built();
    lemma_dom_empty(s.ups);
    assert(s.lock is None);
    assert(schema_of(s.ix) < 2);
    let s1 = ustep(s, UAct::Start { p }, v)->Some_0;
    let s2 = ustep(s1, UAct::LockKill { p }, v)->Some_0;
    let s3 = ustep(s2, UAct::Rebuild { p }, v)->Some_0;
    let s4 = ustep(s3, UAct::Count { p }, v)->Some_0;
    let s5 = ustep(s4, UAct::Flip { p }, v)->Some_0;
    let s6 = ustep(s5, UAct::Clean { p }, v)->Some_0;
    let s7 = ustep(s6, UAct::Done { p }, v)->Some_0;
    assert(s3.ix.tf == s.ix.tf && s3.ix.len == s.ix.len);
    lemma_rebuilt_frame(s.ix, s2.ix);
    assert(rebuilt(s2.ix) == Ix { df: rebuilt(s.ix).df, doc: rebuilt(s.ix).doc, ..s2.ix });
    assert(s7.ix == canonical(s.ix));
    lemma_rebuild_count_cons(s.ix);
    lemma_cons_frame(counted(rebuilt(s.ix)), canonical(s.ix));
    assert(s7.ups.dom() =~= Set::<nat>::empty());
}

/// Every step of an Upgrade call (including Timeout, Fail and Crash) leaves tf and len as they were.
pub proof fn lemma_upgrade_steps_keep_tf_len(s: USys, a: UAct, v: UVariant)
    requires
        ustep(s, a, v) is Some,
        !(a is Insert),
        !(a is Delete),
    ensures
        ustep(s, a, v)->Some_0.ix.tf == s.ix.tf,
        ustep(s, a, v)->Some_0.ix.len == s.ix.len,
{
}

/// FR-023 "safe to re-run after an interruption": wherever an earlier call stopped (Fail or Crash
/// before the flip, a lock Timeout), the state keeps the original tf and len (previous lemma), and
/// a re-run that goes to the end leaves exactly what an uninterrupted run from the original state
/// leaves.
pub proof fn theorem_rerun_converges(s: USys, mid: USys, p: nat)
    requires
        uinv(mid),
        mid.ups.dom().len() == 0,
        mid.ix.n is Some,
        schema_of(mid.ix) < 2 || mid.ix.upgrading,
        mid.ix.tf == s.ix.tf,
        mid.ix.len == s.ix.len,
    ensures
        run_upgrade(mid, p, upgrade_as_built()) is Some,
        run_upgrade(mid, p, upgrade_as_built())->Some_0.ix == canonical(s.ix),
{
    theorem_upgrade_completes(mid, p);
    lemma_canonical_depends_on_tf_len(mid.ix, s.ix);
}

/// A schema-1 index that satisfies P_s1, with no Upgrade in flight, satisfies the invariant.
pub proof fn lemma_schema1_init(ix: Ix)
    requires
        s1ok(ix),
        ix.n is Some,
        ix.schema is None,
        !ix.upgrading,
    ensures
        uinv(USys { ix, lock: None, ups: Map::empty() }),
{
    let s = USys { ix, lock: None, ups: Map::empty() };
    assert(s.ups.dom() =~= Set::<nat>::empty());
}

// ---------------------------------------------------------------------------- the repair: re-check under the lock

/// With the re-check, the reader guarantee and the rebuild's exclusivity hold with concurrent
/// Upgrades and with a process dying at any point, including after the flip.
pub proof fn theorem_repaired_upgrade_preserves(s: USys, a: UAct)
    requires
        uinv_core(s),
        ustep(s, a, upgrade_repaired()) is Some,
    ensures
        uinv_core(ustep(s, a, upgrade_repaired())->Some_0),
{
    let v = upgrade_repaired();
    let s2 = ustep(s, a, v)->Some_0;
    if !(a is Insert) && !(a is Delete) {
        lemma_upgrade_steps_keep_tf_len(s, a, v);
        lemma_rebuilt_frame(s.ix, s2.ix);
    }
    match a {
        UAct::Start { p } => {
            if s2 != s {
                lemma_s1ok_frame(s.ix, s2.ix);
                lemma_cons_frame(s.ix, s2.ix);
                lemma_dom_nonempty(s2.ups, p);
            }
        },
        UAct::LockKill { p } => {
            lemma_s1ok_frame(s.ix, s2.ix);
            lemma_dom_nonempty(s.ups, p);
            assert forall|q: nat| #[trigger] s.ups.contains_key(q) implies !holds_lock(s.ups[q]) by {}
            if schema_of(s.ix) >= 2 {
                assert(cons(s.ix));
                assert(cons_present(s2.ix));
            }
        },
        UAct::Timeout { p } => {
            lemma_s1ok_frame(s.ix, s2.ix);
            lemma_cons_frame(s.ix, s2.ix);
            if s2.ups.dom().len() > 0 {
                let q = s2.ups.dom().choose();
                assert(s.ups.contains_key(q));
                lemma_dom_nonempty(s.ups, q);
            }
        },
        UAct::Rebuild { p } => {
            assert(rebuilding(s.ups[p]));
            lemma_s1ok_frame(s.ix, s2.ix);
            assert(schema_of(s.ix) < 2);
            assert(s2.ix.df == rebuilt(s2.ix).df && s2.ix.doc == rebuilt(s2.ix).doc);
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) && q != p implies !holds_lock(s2.ups[q]) by {}
        },
        UAct::Count { p } => {
            assert(rebuilt(s.ix) == s.ix);
            lemma_rebuild_count_cons(s.ix);
            lemma_s1ok_frame(s.ix, s2.ix);
            assert(schema_of(s2.ix) < 2);
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) && q != p implies !holds_lock(s2.ups[q]) by {}
        },
        UAct::Flip { p } => {
            lemma_s1ok_frame(s.ix, s2.ix);
            lemma_cons_frame(s.ix, s2.ix);
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) && q != p implies !holds_lock(s2.ups[q]) by {}
        },
        UAct::Clean { p } => {
            lemma_s1ok_frame(s.ix, s2.ix);
            lemma_cons_frame(s.ix, s2.ix);
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) && q != p implies !holds_lock(s2.ups[q]) by {}
        },
        UAct::Done { p } => {
            lemma_cons_frame(s.ix, s2.ix);
            lemma_s1ok_frame(s.ix, s2.ix);
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) implies !holds_lock(s2.ups[q]) by {}
            if s2.ups.dom().len() > 0 {
                let q = s2.ups.dom().choose();
                assert(s.ups.contains_key(q));
            }
        },
        UAct::Fail { p } => {
            lemma_cons_frame(s.ix, s2.ix);
            lemma_s1ok_frame(s.ix, s2.ix);
            assert forall|q: nat| #[trigger] s2.ups.contains_key(q) implies !holds_lock(s2.ups[q]) by {}
            if s2.ups.dom().len() > 0 {
                let q = s2.ups.dom().choose();
                assert(s.ups.contains_key(q));
            }
        },
        UAct::Crash { p } => {
            if s2.ups.dom().len() > 0 {
                let q = s2.ups.dom().choose();
                assert(s.ups.contains_key(q));
                lemma_dom_nonempty(s.ups, q);
            }
        },
        UAct::Insert { d, bag, dlen } => {
            assert forall|q: nat| #[trigger] s.ups.contains_key(q) implies !holds_lock(s.ups[q]) by {}
            assert(cons(s.ix));
            theorem_insert_preserves_counters(s.ix, d, bag, dlen);
            lemma_cons_gives_s1ok(s2.ix);
        },
        UAct::Delete { d } => {
            if s.ix.n is Some {
                assert forall|q: nat| #[trigger] s.ups.contains_key(q) implies !holds_lock(s.ups[q]) by {}
                theorem_delete_preserves_counters(s.ix, d);
                lemma_cons_gives_s1ok(s2.ix);
            }
        },
    }
}

// ---------------------------------------------------------------------------- witnesses (O2)

/// A schema-1 index with one document {7} (stored idf, no df, no doc, no totalLen).
pub open spec fn s1_index() -> Ix {
    Ix {
        tf: Map::empty().insert(7int, Map::empty().insert(1int, 1int)),
        df: Map::empty(),
        doc: Map::empty(),
        len: Map::empty().insert(1int, 1int),
        n: Some(1),
        total: 0,
        vocab: 1,
        schema: None,
        upgrading: false,
        idf: true,
    }
}

pub proof fn lemma_s1_index_ok()
    ensures
        s1ok(s1_index()),
{
    let ix = s1_index();
    assert(ix.tf.dom() =~= Set::<Term>::empty().insert(7));
    assert(ix.len.dom() =~= Set::<Doc>::empty().insert(1));
    assert(ix.tf[7].dom() =~= Set::<Doc>::empty().insert(1));
    assert forall|t: Term, d: Doc| #[trigger] ix.tf.contains_key(t) && #[trigger] ix.tf[t].contains_key(d)
        implies ix.tf[t][d] > 0 && ix.len.contains_key(d) by {
        assert(t == 7);
        assert(d == 1);
    }
    assert(terms_of(ix, 1) =~= Set::<Term>::empty().insert(7));
    lemma_sumf_insert(|t: Term| tfv(ix, t, 1), Set::<Term>::empty(), 7);
    assert(ix.tf.contains_key(7) && ix.tf[7].contains_key(1));
    assert(has_posting(ix, 1));
}

/// W-O2a (F4): two Upgrade calls both pass the pre-lock check (the second sees schema 1, or the
/// flag). The first finishes and clears the flag while the second is still in flight, so a writer
/// is admitted during the second call (FR-023 "refuse writers while it runs"); the second then
/// kills df on a schema-2 index, and a Search reading schema 2 finds df(7) = 0 for a term that
/// has a posting (FR-023 "never observe schema 2 before the conversion is complete").
pub proof fn witness_concurrent_upgrades() {
    let v = upgrade_concurrent();
    lemma_s1_index_ok();
    lemma_bag1_tok(8);
    let s0 = USys { ix: s1_index(), lock: None, ups: Map::empty() };
    let s1 = ustep(s0, UAct::Start { p: 1 }, v)->Some_0;
    assert(s1.ups.contains_key(1) && s1.ix.upgrading);
    let s2 = ustep(s1, UAct::Start { p: 2 }, v)->Some_0;
    assert(s2.ups.contains_key(2) && s2.ups[2] == UpPc::Flagged);
    let s3 = ustep(s2, UAct::LockKill { p: 1 }, v)->Some_0;
    let s4 = ustep(s3, UAct::Rebuild { p: 1 }, v)->Some_0;
    let s5 = ustep(s4, UAct::Count { p: 1 }, v)->Some_0;
    let s6 = ustep(s5, UAct::Flip { p: 1 }, v)->Some_0;
    let s7 = ustep(s6, UAct::Clean { p: 1 }, v)->Some_0;
    let s8 = ustep(s7, UAct::Done { p: 1 }, v)->Some_0;
    assert(s8.ups.contains_key(2) && s8.ups[2] == UpPc::Flagged);
    assert(s8.lock is None && !s8.ix.upgrading && schema_of(s8.ix) == 2);
    // a writer is admitted while call 2 is in flight
    assert(ustep(s8, UAct::Insert { d: 2, bag: bag1(8), dlen: 1 }, v) is Some);
    let s9 = ustep(s8, UAct::Insert { d: 2, bag: bag1(8), dlen: 1 }, v)->Some_0;
    assert(s9.ups.contains_key(2));
    // call 2 takes the lock and kills df on a schema-2 index
    let s10 = ustep(s9, UAct::LockKill { p: 2 }, v)->Some_0;
    assert(ustep(s9, UAct::LockKill { p: 2 }, v) is Some);
    assert(schema_of(s10.ix) == 2);
    assert(s10.ix.tf.contains_key(7));
    assert(dfv(s10.ix, 7) == 0);
    assert(!cons(s10.ix));
}

/// W-O2b (F4): the process running Upgrade dies after the flip and before the flag is cleared
/// (during Kill ^BM25Idx(x,"idf"), which walks the whole schema-1 idf subtree). The stale flag
/// refuses writers; the operator re-runs Upgrade, whose pre-check proceeds because of the flag, and
/// it kills df on a schema-2 index that Searches are reading.
pub proof fn witness_crash_after_flip_rerun() {
    let v = upgrade_crash_rerun();
    lemma_s1_index_ok();
    lemma_bag1_tok(8);
    let s0 = USys { ix: s1_index(), lock: None, ups: Map::empty() };
    let s1 = ustep(s0, UAct::Start { p: 1 }, v)->Some_0;
    let s2 = ustep(s1, UAct::LockKill { p: 1 }, v)->Some_0;
    let s3 = ustep(s2, UAct::Rebuild { p: 1 }, v)->Some_0;
    let s4 = ustep(s3, UAct::Count { p: 1 }, v)->Some_0;
    let s5 = ustep(s4, UAct::Flip { p: 1 }, v)->Some_0;
    let s6 = ustep(s5, UAct::Crash { p: 1 }, v)->Some_0;
    assert(ustep(s5, UAct::Crash { p: 1 }, v) is Some);
    assert(s6.ups.dom() =~= Set::<nat>::empty());
    assert(s6.ix.upgrading && schema_of(s6.ix) == 2 && s6.lock is None);
    lemma_rebuild_count_cons(s1_index());
    // writers are refused by the stale flag ("being upgraded", not "re-run Upgrade")
    assert(ustep(s6, UAct::Insert { d: 2, bag: bag1(8), dlen: 1 }, v) is None);
    let s7 = ustep(s6, UAct::Start { p: 2 }, v)->Some_0;
    assert(s7.ups.contains_key(2));
    let s8 = ustep(s7, UAct::LockKill { p: 2 }, v)->Some_0;
    assert(schema_of(s8.ix) == 2);
    assert(s8.ix.tf.contains_key(7));
    assert(dfv(s8.ix, 7) == 0);
    assert(!cons(s8.ix));
}

/// Valid outcome survives the repair: on the same death-after-flip history the re-check skips the
/// rebuild, the index stays consistent throughout, and the re-run clears the flag.
pub proof fn witness_repair_rerun_keeps_index() {
    let v = upgrade_repaired();
    lemma_s1_index_ok();
    let s0 = USys { ix: s1_index(), lock: None, ups: Map::empty() };
    let s1 = ustep(s0, UAct::Start { p: 1 }, v)->Some_0;
    let s2 = ustep(s1, UAct::LockKill { p: 1 }, v)->Some_0;
    assert(s2.ups[1] == UpPc::Killed);
    let s3 = ustep(s2, UAct::Rebuild { p: 1 }, v)->Some_0;
    let s4 = ustep(s3, UAct::Count { p: 1 }, v)->Some_0;
    let s5 = ustep(s4, UAct::Flip { p: 1 }, v)->Some_0;
    let s6 = ustep(s5, UAct::Crash { p: 1 }, v)->Some_0;
    let s7 = ustep(s6, UAct::Start { p: 2 }, v)->Some_0;
    let s8 = ustep(s7, UAct::LockKill { p: 2 }, v)->Some_0;
    assert(s8.ups[2] == UpPc::Flipped);
    lemma_rebuild_count_cons(s1_index());
    lemma_rebuilt_frame(s1_index(), s2.ix);
    lemma_cons_frame(counted(rebuilt(s1_index())), s8.ix);
    assert(cons(s8.ix));
    let s9 = ustep(s8, UAct::Clean { p: 2 }, v)->Some_0;
    let s10 = ustep(s9, UAct::Done { p: 2 }, v)->Some_0;
    assert(ustep(s9, UAct::Done { p: 2 }, v) is Some);
    lemma_cons_frame(counted(rebuilt(s1_index())), s10.ix);
    assert(cons(s10.ix) && !s10.ix.upgrading && schema_of(s10.ix) == 2);
}

// ============================================================================ common-term cutoff (FR-044-C1..C5)

/// pMaxDfFraction as num/den (den > 0). The Python wrapper refuses a fraction outside 0..1.
pub struct Frac {
    pub num: int,
    pub den: int,
}

/// (tD / N) > pMaxDfFraction, for N > 0 (SearchCore returns [] at N = 0 before the cutoff, l.241)
pub open spec fn over(dfv: int, n: int, f: Frac) -> bool {
    dfv * f.den > f.num * n
}

/// (+pMaxDfFraction > 0) && (schema >= 2) (l.266)
pub open spec fn cut_on(f: Frac, schema: int) -> bool {
    f.num > 0 && schema >= 2
}

pub struct CutSt {
    /// tMinTok / tMinDf
    pub min: Option<(Term, int)>,
    /// the keys of tDf: known query terms
    pub known: Set<Term>,
    /// tSkip
    pub skip: Set<Term>,
}

/// SearchCore l.268-276: one pass over the query tokens in order.
pub open spec fn cut_scan(q: Seq<Term>, df: spec_fn(Term) -> int, n: int, f: Frac, i: int) -> CutSt
    decreases i,
{
    if i <= 0 {
        CutSt { min: None, known: Set::empty(), skip: Set::empty() }
    } else {
        let s = cut_scan(q, df, n, f, i - 1);
        let tok = q[i - 1];
        let d = df(tok);
        if d == 0 {
            s
        } else {
            CutSt {
                known: s.known.insert(tok),
                min: match s.min {
                    None => Some((tok, d)),
                    Some(m) => if d < m.1 { Some((tok, d)) } else { s.min },
                },
                skip: if over(d, n, f) { s.skip.insert(tok) } else { s.skip },
            }
        }
    }
}

pub struct CutOut {
    /// ^||bm25skip: what SearchReport lists (each once; ObjectScript collation order, see Q6)
    pub skip: Set<Term>,
    /// ^||bm25fallback
    pub fallback: bool,
}

/// SearchCore l.265-293.
pub open spec fn cutoff(q: Seq<Term>, df: spec_fn(Term) -> int, n: int, f: Frac, schema: int) -> CutOut {
    if !cut_on(f, schema) {
        CutOut { skip: Set::empty(), fallback: false }
    } else {
        let s = cut_scan(q, df, n, f, q.len() as int);
        if s.known.subset_of(s.skip) && s.min is Some {
            CutOut { skip: s.skip.remove(s.min->Some_0.0), fallback: true }
        } else {
            CutOut { skip: s.skip, fallback: false }
        }
    }
}

// ---------------------------------------------------------------------------- L1

/// The rarest known term, ties to the first in query order (FR-044-C2).
pub open spec fn rarest_upto(q: Seq<Term>, df: spec_fn(Term) -> int, m: int, i: int) -> bool {
    &&& 0 <= m < i <= q.len()
    &&& df(q[m]) > 0
    &&& forall|j: int| 0 <= j < i && #[trigger] df(q[j]) > 0 ==> df(q[j]) >= df(q[m])
    &&& forall|j: int| 0 <= j < m && #[trigger] df(q[j]) > 0 ==> df(q[j]) > df(q[m])
}

pub open spec fn known_at(q: Seq<Term>, df: spec_fn(Term) -> int, t: Term, i: int) -> bool {
    exists|j: int| 0 <= j < i && q[j] == t && #[trigger] df(q[j]) > 0
}

pub open spec fn any_known(q: Seq<Term>, df: spec_fn(Term) -> int) -> bool {
    exists|j: int| 0 <= j < q.len() && #[trigger] df(q[j]) > 0
}

pub open spec fn all_over(q: Seq<Term>, df: spec_fn(Term) -> int, n: int, f: Frac) -> bool {
    forall|j: int| 0 <= j < q.len() && #[trigger] df(q[j]) > 0 ==> over(df(q[j]), n, f)
}

pub proof fn lemma_known_step(q: Seq<Term>, df: spec_fn(Term) -> int, t: Term, i: int)
    requires
        0 < i <= q.len(),
    ensures
        known_at(q, df, t, i) == (known_at(q, df, t, i - 1) || (q[i - 1] == t && df(q[i - 1]) > 0)),
{
    if known_at(q, df, t, i) {
        let j = choose|j: int| 0 <= j < i && q[j] == t && #[trigger] df(q[j]) > 0;
        if j < i - 1 {
            assert(0 <= j < i - 1 && q[j] == t && df(q[j]) > 0);
        }
    }
    if known_at(q, df, t, i - 1) {
        let j = choose|j: int| 0 <= j < i - 1 && q[j] == t && #[trigger] df(q[j]) > 0;
        assert(0 <= j < i && q[j] == t && df(q[j]) > 0);
    }
    if q[i - 1] == t && df(q[i - 1]) > 0 {
        assert(0 <= i - 1 < i && q[i - 1] == t && df(q[i - 1]) > 0);
    }
}

pub proof fn lemma_cut_scan(q: Seq<Term>, df: spec_fn(Term) -> int, n: int, f: Frac, i: int)
    requires
        0 <= i <= q.len(),
        forall|t: Term| #[trigger] df(t) >= 0,
    ensures ({
        let s = cut_scan(q, df, n, f, i);
        &&& forall|t: Term| #[trigger] s.known.contains(t) <==> known_at(q, df, t, i)
        &&& forall|t: Term| #[trigger] s.skip.contains(t) <==> (known_at(q, df, t, i) && over(df(t), n, f))
        &&& (s.min is None <==> !(exists|j: int| 0 <= j < i && #[trigger] df(q[j]) > 0))
        &&& (s.min is Some ==> exists|m: int| rarest_upto(q, df, m, i) && q[m] == s.min->Some_0.0
                && s.min->Some_0.1 == df(q[m]))
    }),
    decreases i,
{
    if i > 0 {
        lemma_cut_scan(q, df, n, f, i - 1);
        let s0 = cut_scan(q, df, n, f, i - 1);
        let s = cut_scan(q, df, n, f, i);
        let tok = q[i - 1];
        if df(tok) == 0 {
            assert(s == s0);
        } else {
            assert(s.known == s0.known.insert(tok));
            assert(s.skip == (if over(df(tok), n, f) { s0.skip.insert(tok) } else { s0.skip }));
        }
        assert forall|t: Term| #[trigger] s.known.contains(t) <==> known_at(q, df, t, i) by {
            lemma_known_step(q, df, t, i);
            assert(s0.known.contains(t) <==> known_at(q, df, t, i - 1));
            if df(tok) == 0 {
                assert(s.known.contains(t) == s0.known.contains(t));
                assert(!(q[i - 1] == t && df(q[i - 1]) > 0));
            } else {
                assert(s.known.contains(t) == (s0.known.contains(t) || t == tok));
            }
        }
        assert forall|t: Term| #[trigger] s.skip.contains(t) <==> (known_at(q, df, t, i) && over(df(t), n, f)) by {
            lemma_known_step(q, df, t, i);
            assert(s0.skip.contains(t) <==> (known_at(q, df, t, i - 1) && over(df(t), n, f)));
            if df(tok) == 0 {
                assert(s.skip.contains(t) == s0.skip.contains(t));
                assert(!(q[i - 1] == t && df(q[i - 1]) > 0));
            } else if over(df(tok), n, f) {
                assert(s.skip.contains(t) == (s0.skip.contains(t) || t == tok));
            } else {
                assert(s.skip.contains(t) == s0.skip.contains(t));
            }
        }
        if df(tok) > 0 {
            assert(df(q[i - 1]) > 0);
            match s0.min {
                None => {
                    assert(rarest_upto(q, df, i - 1, i)) by {
                        assert forall|j: int| 0 <= j < i && #[trigger] df(q[j]) > 0 implies df(q[j]) >= df(q[i - 1]) by {
                            if j < i - 1 { assert(df(q[j]) > 0); }
                        }
                    }
                },
                Some(mm) => {
                    let m = choose|m: int| rarest_upto(q, df, m, i - 1) && q[m] == mm.0 && mm.1 == df(q[m]);
                    if df(tok) < mm.1 {
                        assert(rarest_upto(q, df, i - 1, i));
                    } else {
                        assert(rarest_upto(q, df, m, i));
                    }
                },
            }
        } else {
            assert forall|j: int| 0 <= j < i && #[trigger] df(q[j]) > 0 implies j < i - 1 by {}
            if s0.min is Some {
                let mm = s0.min->Some_0;
                let m = choose|m: int| rarest_upto(q, df, m, i - 1) && q[m] == mm.0 && mm.1 == df(q[m]);
                assert(rarest_upto(q, df, m, i));
            }
        }
    }
}

/// FR-044-C1..C5 as a contract of SearchCore's cutoff: off -> nothing skipped; otherwise exactly
/// the known terms over the bound are skipped, except that when every known term is over it the
/// rarest (first in query order on a tie) is kept and `fallback` is reported; a df = 0 term is
/// never skipped; and a query with a known term always scores at least one.
pub proof fn theorem_cutoff_contract(q: Seq<Term>, df: spec_fn(Term) -> int, n: int, f: Frac, schema: int)
    requires
        n > 0,
        f.den > 0,
        // df is a document count read from ^BM25Idx(x,"df",t) with +$Get (0 when absent)
        forall|t: Term| #[trigger] df(t) >= 0,
    ensures ({
        let out = cutoff(q, df, n, f, schema);
        &&& !cut_on(f, schema) ==> out.skip == Set::<Term>::empty() && !out.fallback
        &&& (cut_on(f, schema) && !(any_known(q, df) && all_over(q, df, n, f))) ==> !out.fallback
                && forall|t: Term| #[trigger] out.skip.contains(t) <==> (known_at(q, df, t, q.len() as int) && over(df(t), n, f))
        &&& (cut_on(f, schema) && any_known(q, df) && all_over(q, df, n, f)) ==> out.fallback
                && exists|m: int| rarest_upto(q, df, m, q.len() as int)
                    && forall|t: Term| #[trigger] out.skip.contains(t) <==> (known_at(q, df, t, q.len() as int) && t != q[m])
        &&& forall|t: Term| df(t) == 0 ==> !(#[trigger] out.skip.contains(t))
        &&& any_known(q, df) ==> exists|j: int| 0 <= j < q.len() && #[trigger] df(q[j]) > 0 && !out.skip.contains(q[j])
    }),
{
    let out = cutoff(q, df, n, f, schema);
    let len = q.len() as int;
    if cut_on(f, schema) {
        lemma_cut_scan(q, df, n, f, len);
        let s = cut_scan(q, df, n, f, len);
        assert forall|t: Term| df(t) == 0 implies !(#[trigger] out.skip.contains(t)) by {
            if s.skip.contains(t) {
                let j = choose|j: int| 0 <= j < len && q[j] == t && #[trigger] df(q[j]) > 0;
            }
        }
        if any_known(q, df) && all_over(q, df, n, f) {
            assert(s.min is Some);
            assert(s.known.subset_of(s.skip)) by {
                assert forall|t: Term| #[trigger] s.known.contains(t) implies s.skip.contains(t) by {
                    let j = choose|j: int| 0 <= j < len && q[j] == t && #[trigger] df(q[j]) > 0;
                }
            }
            let mm = s.min->Some_0;
            let m = choose|m: int| rarest_upto(q, df, m, len) && q[m] == mm.0 && mm.1 == df(q[m]);
            assert(rarest_upto(q, df, m, len));
            assert forall|t: Term| #[trigger] out.skip.contains(t) <==> (known_at(q, df, t, len) && t != q[m]) by {
                if known_at(q, df, t, len) {
                    let j = choose|j: int| 0 <= j < len && q[j] == t && #[trigger] df(q[j]) > 0;
                }
            }
            assert(0 <= m < len && df(q[m]) > 0 && !out.skip.contains(q[m]));
        } else {
            if s.known.subset_of(s.skip) && s.min is Some {
                // every known term is over the bound: contradiction with the branch
                assert(any_known(q, df)) by {
                    let mm = s.min->Some_0;
                    let m = choose|m: int| rarest_upto(q, df, m, len) && q[m] == mm.0 && mm.1 == df(q[m]);
                    assert(0 <= m < len && df(q[m]) > 0);
                }
                assert(all_over(q, df, n, f)) by {
                    assert forall|j: int| 0 <= j < len && #[trigger] df(q[j]) > 0 implies over(df(q[j]), n, f) by {
                        assert(known_at(q, df, q[j], len));
                        assert(s.known.contains(q[j]));
                        assert(s.skip.contains(q[j]));
                    }
                }
            }
            if any_known(q, df) {
                // some known term is not over the bound, and it is not skipped
                let j0 = choose|j: int| 0 <= j < len && #[trigger] df(q[j]) > 0 && !over(df(q[j]), n, f);
                assert(!out.skip.contains(q[j0]));
            }
        }
    } else {
        assert(out.skip == Set::<Term>::empty());
        if any_known(q, df) {
            let j0 = choose|j: int| 0 <= j < len && #[trigger] df(q[j]) > 0;
            assert(!out.skip.contains(q[j0]));
        }
    }
}

// ============================================================================ O3: embedding identity and routing

pub type Graph = int;
pub type Key = int;
pub type Tbl = int;
pub type Node = int;

/// graph_id '' (the default graph)
pub open spec fn default_graph() -> Graph { 0 }
/// Graph_KG.kg_NodeEmbeddings (the first of VECTOR_TABLE_NAMES; _route_preference ranks it first)
pub open spec fn legacy() -> Tbl { 0 }

/// kg_emb_<first 16 hex of sha256(graph + "\0" + (model or ""))> (route_table_name). Uninterpreted;
/// premise P_hash (names_ok) says the names are distinct from the legacy table and from each other.
pub uninterp spec fn route_name(g: Graph, m: Option<Key>) -> Tbl;

pub open spec fn names_ok() -> bool {
    &&& forall|g: Graph, m: Option<Key>| #[trigger] route_name(g, m) != legacy()
    &&& forall|g1: Graph, m1: Option<Key>, g2: Graph, m2: Option<Key>|
            #[trigger] route_name(g1, m1) == #[trigger] route_name(g2, m2) ==> g1 == g2 && m1 == m2
}

/// EmbeddingIdentity: model_key (normalized), mechanism, dimension, dtype. `model == None` is the
/// undeclared identity (recorded unknown / offered unknown).
pub struct Ident {
    pub model: Option<Key>,
    pub mech: Option<int>,
    pub width: Option<int>,
    pub dtype: int,
}

/// embedding_identity.conflicts (l.180-241): model, then mechanism (both only when both models are
/// known), then width (when both known), then dtype.
pub open spec fn conflicts(rec: Ident, off: Ident) -> bool {
    ||| (rec.model is Some && off.model is Some && rec.model != off.model)
    ||| (rec.model is Some && off.model is Some && rec.mech != off.mech)
    ||| (rec.width is Some && off.width is Some && rec.width != off.width)
    ||| rec.dtype != off.dtype
}

/// Graph_KG.embedding_registry, primary key (table_name, graph_id), node routes only.
pub type Reg = Map<(Tbl, Graph), Ident>;

pub open spec fn row_for(reg: Reg, t: Tbl, g: Graph, m: Option<Key>) -> bool {
    reg.contains_key((t, g)) && reg[(t, g)].model == m
}

/// _read_route (embeddings.py:377-468) on a readable registry: the rows for (graph, model, node),
/// the legacy table preferred (_route_preference).
pub open spec fn read_route(reg: Reg, g: Graph, m: Option<Key>) -> Option<Tbl> {
    if row_for(reg, legacy(), g, m) {
        Some(legacy())
    } else if exists|t: Tbl| #[trigger] row_for(reg, t, g, m) {
        Some(choose|t: Tbl| #[trigger] row_for(reg, t, g, m))
    } else {
        None
    }
}

/// _is_default_pair (embeddings.py:743-753)
pub open spec fn is_default_pair(g: Graph, m: Option<Key>) -> bool {
    g == default_graph() && m is None
}

/// What every reader of the pair reads (_route_for_read, embeddings.py:652-679, readable registry).
pub open spec fn read_table(reg: Reg, g: Graph, m: Option<Key>) -> Option<Tbl> {
    match read_route(reg, g, m) {
        Some(t) => Some(t),
        None => if is_default_pair(g, m) { Some(legacy()) } else { None },
    }
}

/// L1 (v4.0.0 routing, CHANGELOG "routed tables, one per (graph_id, model_key)"): one route per pair.
pub open spec fn one_row(reg: Reg) -> bool {
    forall|t1: Tbl, t2: Tbl, g: Graph, m: Option<Key>|
        #[trigger] row_for(reg, t1, g, m) && #[trigger] row_for(reg, t2, g, m) ==> t1 == t2
}

/// Premise P_routed_rows: a routed table's row names the pair its name was derived from
/// (no set_embedding_identity(force=True) on a routed table).
pub open spec fn routed_rows_ok(reg: Reg) -> bool {
    forall|t: Tbl, g: Graph| #[trigger] reg.contains_key((t, g)) && t != legacy() ==>
        t == route_name(g, reg[(t, g)].model)
}

pub enum Read {
    Ok,
    /// SQLCODE -30: no registry (pre-226 namespace)
    Absent,
    /// any other failure (permission, connection, timeout)
    Error,
}

pub struct ESys {
    pub reg: Reg,
    /// vector rows (table, graph_id, node_id) -> the identity of the writer that produced them
    pub vecs: Map<(Tbl, Graph, Node), Ident>,
    /// ^IVG.Ledger("meta","state") = "enabled"
    pub ledger_on: bool,
}

pub enum EOut {
    Refused,
    Wrote { s: ESys, table: Tbl },
}

/// store_embedding (embeddings.py:942-1025) for one node vector.
///   `cached`: a route served by _cached_route (30 s TTL) with the row it was read from
///   `rr`: the outcome of _read_route's registry SELECT when not cached
///   `ir`: the outcome of get_embedding_identity's SELECT (schema.py:1033-1084)
/// `fail_closed` is the proposed repair: get_embedding_identity's read failure raises.
pub open spec fn store(s: ESys, g: Graph, node: Node, off: Ident, cached: Option<(Tbl, Ident)>, rr: Read, ir: Read, fail_closed: bool) -> EOut {
    let key = off.model;
    let routed: Option<(bool, Option<(Tbl, Ident)>)> = match cached {
        Some(c) => Some((true, Some(c))),
        None => match rr {
            Read::Error => None,  // raises (4.6.0 R161)
            Read::Absent => Some((false, None)),
            Read::Ok => match read_route(s.reg, g, key) {
                Some(t) => Some((true, Some((t, s.reg[(t, g)])))),
                None => Some((true, None)),
            },
        },
    };
    match routed {
        None => EOut::Refused,
        Some(rt) => {
            let readable = rt.0;
            let route = rt.1;
            // _route_for_write (l.755-791)
            let created = readable && route is None && !is_default_pair(g, key);
            let table = if created { route_name(g, key) } else if route is Some { route->Some_0.0 } else { legacy() };
            let reg1 = if created { s.reg.insert((table, g), off) } else { s.reg };
            let route_g = if created || route is Some { g } else { default_graph() };
            // enforce_embedding_identity(table, graph_id=route.graph_id or "") (schema.py:1354-1396)
            let recorded: Option<Ident> = match ir {
                Read::Ok => if reg1.contains_key((table, route_g)) { Some(reg1[(table, route_g)]) } else { None },
                Read::Absent => None,
                Read::Error => None,  // get_embedding_identity: `except Exception: return None`
            };
            let id_refused = (fail_closed && ir is Error) || (recorded is Some && conflicts(recorded->Some_0, off));
            // _route_width + the length check (l.991-995): the route's recorded width
            let width_refused = route is Some && route->Some_0.1.width is Some && off.width is Some
                && route->Some_0.1.width != off.width;
            if id_refused || width_refused {
                EOut::Refused
            } else {
                EOut::Wrote { s: ESys { reg: reg1, vecs: s.vecs.insert((table, g, node), off), ..s }, table }
            }
        },
    }
}

/// get_embedding / kg_KNN_VEC for one pair (readable registry)
pub open spec fn get(s: ESys, g: Graph, m: Option<Key>, node: Node) -> Option<Ident> {
    match read_table(s.reg, g, m) {
        Some(t) => if s.vecs.contains_key((t, g, node)) { Some(s.vecs[(t, g, node)]) } else { None },
        None => None,
    }
}

/// L1 refusal rule, stated without the product's `conflicts` (ADR-0005/0006, spec 226 FR-010/FR-014,
/// 4.0.0 routing): a write into a pair whose recorded identity disagrees on width, dtype, or — both
/// sides naming a model — on model or mechanism, is refused. A different declared model is routed
/// to its own pair rather than refused.
pub open spec fn l1_must_refuse(rec: Ident, off: Ident) -> bool {
    ||| (rec.width is Some && off.width is Some && rec.width != off.width)
    ||| rec.dtype != off.dtype
    ||| (rec.model is Some && off.model is Some && (rec.model != off.model || rec.mech != off.mech))
}

/// The recorded identity a write of (g, key) is measured against: its route's row, or for the
/// default pair with no row of its own, kg_NodeEmbeddings' row.
pub open spec fn target_row(reg: Reg, g: Graph, key: Option<Key>) -> Option<Ident> {
    match read_route(reg, g, key) {
        Some(t) => Some(reg[(t, g)]),
        None => if is_default_pair(g, key) && reg.contains_key((legacy(), default_graph())) {
            Some(reg[(legacy(), default_graph())])
        } else {
            None
        },
    }
}

/// O3 (ADR-0006 as amended by 4.0.0): with fresh registry reads, store_embedding (a) is refused
/// exactly when the identity recorded for its pair disagrees with the writer's (L1 rule above), (b)
/// otherwise writes the vector where every reader of its (graph, model) pair reads it, and (c)
/// keeps one route per pair.
pub proof fn theorem_store_routes_and_refuses(s: ESys, g: Graph, node: Node, off: Ident)
    requires
        names_ok(),
        one_row(s.reg),
        routed_rows_ok(s.reg),
    ensures ({
        let out = store(s, g, node, off, None, Read::Ok, Read::Ok, false);
        let key = off.model;
        &&& (out is Refused <==> (target_row(s.reg, g, key) is Some
                && l1_must_refuse(target_row(s.reg, g, key)->Some_0, off)))
        &&& out is Wrote ==> read_table(out->s.reg, g, key) == Some(out->table)
                && get(out->s, g, key, node) == Some(off)
                && one_row(out->s.reg) && routed_rows_ok(out->s.reg)
    }),
{
    let key = off.model;
    let out = store(s, g, node, off, None, Read::Ok, Read::Ok, false);
    match read_route(s.reg, g, key) {
        Some(t) => {
            if row_for(s.reg, legacy(), g, key) {
                assert(t == legacy());
            } else {
                assert(row_for(s.reg, t, g, key));
            }
            assert(row_for(s.reg, t, g, key));
        },
        None => {
            if !is_default_pair(g, key) {
                let t = route_name(g, key);
                let reg1 = s.reg.insert((t, g), off);
                assert(!(exists|u: Tbl| #[trigger] row_for(s.reg, u, g, key)));
                assert(!s.reg.contains_key((t, g))) by {
                    if s.reg.contains_key((t, g)) {
                        assert(t != legacy());
                        assert(t == route_name(g, s.reg[(t, g)].model));
                        assert(s.reg[(t, g)].model == key);
                        assert(row_for(s.reg, t, g, key));
                    }
                }
                assert(row_for(reg1, t, g, key));
                assert forall|t1: Tbl, t2: Tbl, g2: Graph, m: Option<Key>|
                    #[trigger] row_for(reg1, t1, g2, m) && #[trigger] row_for(reg1, t2, g2, m) implies t1 == t2 by {
                    if (t1, g2) != (t, g) && (t2, g2) != (t, g) {
                        assert(row_for(s.reg, t1, g2, m) && row_for(s.reg, t2, g2, m));
                    } else if (t1, g2) == (t, g) && (t2, g2) != (t, g) {
                        assert(row_for(s.reg, t2, g, key));
                    } else if (t2, g2) == (t, g) && (t1, g2) != (t, g) {
                        assert(row_for(s.reg, t1, g, key));
                    }
                }
                if out is Wrote {
                    assert(!row_for(reg1, legacy(), g, key)) by {
                        assert(!row_for(s.reg, legacy(), g, key));
                        assert(t != legacy());
                    }
                    assert(read_route(reg1, g, key) == Some(t));
                }
                assert forall|t1: Tbl, g1: Graph| #[trigger] reg1.contains_key((t1, g1)) && t1 != legacy() implies
                    t1 == route_name(g1, reg1[(t1, g1)].model) by {
                    if (t1, g1) != (t, g) { assert(s.reg.contains_key((t1, g1))); }
                }
            }
        },
    }
}

/// The identity check reads nothing from the ledger: its outcome is the same with the ledger
/// enabled or disabled (ADR-0006 "including … one that has no history feature enabled").
pub proof fn theorem_identity_check_ignores_ledger(s: ESys, g: Graph, node: Node, off: Ident,
    cached: Option<(Tbl, Ident)>, rr: Read, ir: Read)
    ensures
        store(ESys { ledger_on: true, ..s }, g, node, off, cached, rr, ir, false) is Refused
            == store(ESys { ledger_on: false, ..s }, g, node, off, cached, rr, ir, false) is Refused,
{
}

// ---------------------------------------------------------------------------- the queue (F8)

/// Graph.KG.EmbedQueue.RouteTable (l.220-235): a kg_emb_ row of (graph, key(config)), or "".
pub open spec fn route_table(reg: Reg, g: Graph, c: Key) -> Option<Tbl> {
    if exists|t: Tbl| #[trigger] row_for(reg, t, g, Some(c)) && t != legacy() {
        Some(choose|t: Tbl| #[trigger] row_for(reg, t, g, Some(c)) && t != legacy())
    } else {
        None
    }
}

/// enqueue_for_embedding's check (embeddings.py:1838-1842): kg_NodeEmbeddings@'' against the
/// entry's config, no width offered.
pub open spec fn enqueue_admits(s: ESys, c: Key, mech: int, dtype: int) -> bool {
    let off = Ident { model: Some(c), mech: Some(mech), width: None, dtype };
    !(s.reg.contains_key((legacy(), default_graph())) && conflicts(s.reg[(legacy(), default_graph())], off))
}

/// EmbedQueue.ProcessBatch (l.258-337) for one entry of (graph, node, config): the default graph's
/// entries go to kg_NodeEmbeddings whatever their config; no identity check; IRIS refuses only a
/// vector whose width differs from the column's (modelled by the row's recorded width, P_col).
pub open spec fn process_entry(s: ESys, g: Graph, node: Node, c: Key, mech: int, width: int, dtype: int) -> EOut {
    let target = if g == default_graph() { Some(legacy()) } else { route_table(s.reg, g, c) };
    match target {
        None => EOut::Refused,
        Some(t) => {
            let col_refuses = s.reg.contains_key((t, g)) && s.reg[(t, g)].width is Some && s.reg[(t, g)].width != Some(width);
            if col_refuses { EOut::Refused } else {
                EOut::Wrote {
                    s: ESys { vecs: s.vecs.insert((t, g, node), Ident { model: Some(c), mech: Some(mech), width: Some(width), dtype }), ..s },
                    table: t,
                }
            }
        },
    }
}

/// set_embedding_identity's claim of an adopted row (schema.py:1177-1209): UPDATE ... WHERE
/// model_key IS NULL; also what initialize_schema does for an engine with embedding_config.
pub open spec fn claim(s: ESys, t: Tbl, g: Graph, off: Ident) -> ESys {
    if s.reg.contains_key((t, g)) && s.reg[(t, g)].model is None {
        ESys { reg: s.reg.insert((t, g), off), ..s }
    } else {
        s
    }
}

// ---------------------------------------------------------------------------- witnesses (O3)

pub open spec fn unknown_legacy_reg() -> Reg {
    Map::empty().insert((legacy(), default_graph()), Ident { model: None, mech: None, width: Some(4), dtype: 0 })
}

/// W-O3a (F8): an install whose kg_NodeEmbeddings row is adopted-unknown (what initialize_schema
/// writes for an engine with no embedding_config). A default-graph entry for model B passes the
/// enqueue check; the IRIS worker writes its B vector into kg_NodeEmbeddings. Readers of
/// ('', B) resolve no route and miss it; readers of the default pair ('', undeclared) get a B
/// vector. store_embedding for the same (graph, model) would have created and used B's route.
pub proof fn witness_queue_default_graph_misroutes()
    requires
        names_ok(),
{
    let b: Key = 2;
    let s0 = ESys { reg: unknown_legacy_reg(), vecs: Map::empty(), ledger_on: false };
    assert(enqueue_admits(s0, b, 1, 0));
    let out = process_entry(s0, default_graph(), 1, b, 1, 4, 0);
    assert(out is Wrote && out->table == legacy());
    let s1 = out->s;
    // the stored vector's pair resolves to no table, so its own readers miss it
    assert(!row_for(s1.reg, legacy(), default_graph(), Some(b)));
    assert forall|t: Tbl| !(#[trigger] row_for(s1.reg, t, default_graph(), Some(b))) by {}
    assert(read_table(s1.reg, default_graph(), Some(b)) is None);
    assert(get(s1, default_graph(), Some(b), 1) is None);
    // the undeclared default pair reads kg_NodeEmbeddings and gets model B's vector
    assert(row_for(s1.reg, legacy(), default_graph(), None));
    assert(get(s1, default_graph(), None, 1) == Some(Ident { model: Some(b), mech: Some(1), width: Some(4), dtype: 0 }));
    // the direct write path routes the same (graph, model) elsewhere
    let off = Ident { model: Some(b), mech: Some(1), width: Some(4), dtype: 0 };
    let w = store(s0, default_graph(), 1, off, None, Read::Ok, Read::Ok, false);
    assert(read_route(s0.reg, default_graph(), Some(b)) is None);
    assert(w is Wrote && w->table == route_name(default_graph(), Some(b)));
    assert(w->table != legacy());
}

/// W-O3b (F8, time of check vs time of use): the entry is queued while kg_NodeEmbeddings is
/// unclaimed, then an engine configured for model A claims it, then the IRIS worker writes model
/// B's vector into the table now recorded as A's — "mixed in" (CONTEXT.md, ADR-0006).
pub proof fn witness_queue_writes_into_claimed_table()
    requires
        names_ok(),
{
    let a: Key = 1;
    let b: Key = 2;
    let s0 = ESys { reg: unknown_legacy_reg(), vecs: Map::empty(), ledger_on: false };
    assert(enqueue_admits(s0, b, 1, 0));
    let ida = Ident { model: Some(a), mech: Some(1), width: Some(4), dtype: 0 };
    let s1 = claim(s0, legacy(), default_graph(), ida);
    assert(s1.reg[(legacy(), default_graph())].model == Some(a));
    // enqueue would now refuse B ...
    assert(!enqueue_admits(s1, b, 1, 0));
    // ... but the entry is already queued, and the worker does not check
    let out = process_entry(s1, default_graph(), 1, b, 1, 4, 0);
    assert(out is Wrote && out->table == legacy());
    let s2 = out->s;
    assert(read_table(s2.reg, default_graph(), Some(a)) == Some(legacy()));
    assert(get(s2, default_graph(), Some(a), 1) == Some(Ident { model: Some(b), mech: Some(1), width: Some(4), dtype: 0 }));
}

/// W-O3c (F9): a model-A engine writes to the default graph while kg_NodeEmbeddings is still
/// adopted-unknown, which creates A's own route; initialize_schema (or set_embedding_identity)
/// later claims kg_NodeEmbeddings for A. Two rows now answer ('', A); the preference picks
/// kg_NodeEmbeddings and the stored vector is no longer readable by its pair.
pub proof fn witness_claim_after_route_splits_pair()
    requires
        names_ok(),
{
    let a: Key = 1;
    let ida = Ident { model: Some(a), mech: Some(1), width: Some(4), dtype: 0 };
    let s0 = ESys { reg: unknown_legacy_reg(), vecs: Map::empty(), ledger_on: true };
    assert(read_route(s0.reg, default_graph(), Some(a)) is None);
    let w = store(s0, default_graph(), 1, ida, None, Read::Ok, Read::Ok, false);
    let r = route_name(default_graph(), Some(a));
    assert(w is Wrote && w->table == r);
    let s1 = w->s;
    assert(get(s1, default_graph(), Some(a), 1) == Some(ida)) by {
        assert(row_for(s1.reg, r, default_graph(), Some(a)));
        assert(!row_for(s1.reg, legacy(), default_graph(), Some(a)));
    }
    let s2 = claim(s1, legacy(), default_graph(), ida);
    assert(row_for(s2.reg, legacy(), default_graph(), Some(a)));
    assert(row_for(s2.reg, r, default_graph(), Some(a)));
    assert(!one_row(s2.reg));
    assert(read_table(s2.reg, default_graph(), Some(a)) == Some(legacy()));
    assert(!s2.vecs.contains_key((legacy(), default_graph(), 1)));
    assert(get(s2, default_graph(), Some(a), 1) is None);
    assert(s2.vecs.contains_key((r, default_graph(), 1)));
}

/// W-O3d (F11): a route served from the cache, then get_embedding_identity's SELECT fails; the
/// failure reads as "nothing recorded" and a writer whose mechanism disagrees with the row (same
/// model key, same width) is admitted into the table.
pub proof fn witness_identity_fail_open() {
    let a: Key = 1;
    let row = Ident { model: Some(a), mech: Some(1), width: Some(4), dtype: 0 };
    let off = Ident { model: Some(a), mech: Some(2), width: Some(4), dtype: 0 };
    let s0 = ESys { reg: Map::empty().insert((legacy(), default_graph()), row), vecs: Map::empty(), ledger_on: false };
    assert(conflicts(row, off));
    let out = store(s0, default_graph(), 1, off, Some((legacy(), row)), Read::Ok, Read::Error, false);
    assert(out is Wrote && out->table == legacy());
    // with the read failing closed the same write is refused
    assert(store(s0, default_graph(), 1, off, Some((legacy(), row)), Read::Ok, Read::Error, true) is Refused);
    // and with a fresh read it is refused as well
    assert(store(s0, default_graph(), 1, off, None, Read::Ok, Read::Ok, false) is Refused);
}

/// W-O3e (Q1, open question): an undeclared writer on the default graph is width-checked only and
/// writes into kg_NodeEmbeddings although that table is recorded as model A's; A's readers then
/// get a vector of unknown model. On a named graph the same writer gets its own route and A's
/// readers never see it.
pub proof fn witness_undeclared_default_vs_named()
    requires
        names_ok(),
{
    let a: Key = 1;
    let g: Graph = 5;
    let ida = Ident { model: Some(a), mech: Some(1), width: Some(4), dtype: 0 };
    let und = Ident { model: None, mech: None, width: Some(4), dtype: 0 };
    let ra = route_name(g, Some(a));
    let reg = Map::empty().insert((legacy(), default_graph()), ida).insert((ra, g), ida);
    let s0 = ESys { reg, vecs: Map::empty(), ledger_on: false };
    // default graph: mixed in
    assert(read_route(s0.reg, default_graph(), None) is None) by {
        assert forall|t: Tbl| !(#[trigger] row_for(s0.reg, t, default_graph(), None)) by {}
    }
    let w0 = store(s0, default_graph(), 1, und, None, Read::Ok, Read::Ok, false);
    assert(!conflicts(ida, und));
    assert(w0 is Wrote && w0->table == legacy());
    assert(get(w0->s, default_graph(), Some(a), 1) == Some(und));
    // named graph: isolated in its own route
    assert(ra != legacy());
    assert(read_route(s0.reg, g, None) is None) by {
        assert forall|t: Tbl| !(#[trigger] row_for(s0.reg, t, g, None)) by {}
    }
    let w1 = store(s0, g, 1, und, None, Read::Ok, Read::Ok, false);
    assert(w1 is Wrote && w1->table == route_name(g, None));
    assert(route_name(g, None) != ra);
    assert(read_table(w1->s.reg, g, Some(a)) == Some(ra)) by {
        assert(row_for(w1->s.reg, ra, g, Some(a)));
        assert(!row_for(w1->s.reg, legacy(), g, Some(a)));
    }
    assert(!(w1->s).vecs.contains_key((ra, g, 1)));
    assert(get(w1->s, g, Some(a), 1) is None);
}

// ============================================================================ O5: erasure over search stores

pub type IxName = int;

/// A BM25 index as Search reads it: the graph recorded at Build (cfg "graph", BM25Index.cls:168)
/// and each document's tokens (tf / doc).
pub struct Bm25 {
    pub graph: Graph,
    pub docs: Map<Node, Set<Term>>,
}

pub struct GSys {
    /// Graph_KG.nodes rows (graph_id, node_id), with each node's indexed text tokens (rdf_props)
    pub nodes: Map<(Graph, Node), Set<Term>>,
    /// ^BM25Idx
    pub bm25: Map<IxName, Bm25>,
}

pub open spec fn graph_rows(s: GSys, g: Graph) -> Set<(Graph, Node)> {
    s.nodes.dom().filter(|k: (Graph, Node)| k.0 == g && s.nodes[k].len() > 0)
}

pub open spec fn node_of(k: (Graph, Node)) -> Node { k.1 }

/// BM25Index.Build(name, props, pGraph): one document per node of the graph with indexable text
/// (Build's SQL scan is graph-scoped, l.123-131; docLen 0 is skipped, l.182).
pub open spec fn build(s: GSys, name: IxName, g: Graph) -> GSys {
    GSys {
        bm25: s.bm25.insert(name, Bm25 {
            graph: g,
            docs: Map::new(graph_rows(s, g).map(|k: (Graph, Node)| node_of(k)), |n: Node| s.nodes[(g, n)]),
        }),
        ..s
    }
}

/// Search(name, term) hits: the documents whose tokens contain the term.
pub open spec fn hit(s: GSys, name: IxName, t: Term, n: Node) -> bool {
    s.bm25.contains_key(name) && s.bm25[name].docs.contains_key(n) && s.bm25[name].docs[n].contains(t)
}

/// Eraser.EraseGraph (Eraser.cls:46-313): every SQL table and ^KG / ^IVG global of GraphStores'
/// inventory; ^BM25Idx is in neither the scoped nor the unscoped list. `repaired` drops the indexes
/// whose recorded graph is the erased one (proposal S2).
pub open spec fn erase_graph(s: GSys, g: Graph, repaired: bool) -> GSys {
    GSys {
        nodes: Map::new(s.nodes.dom().filter(|k: (Graph, Node)| k.0 != g), |k: (Graph, Node)| s.nodes[k]),
        bm25: if repaired {
            Map::new(s.bm25.dom().filter(|x: IxName| s.bm25[x].graph != g), |x: IxName| s.bm25[x])
        } else {
            s.bm25
        },
    }
}

/// engine.create_node(node_id, properties, graph)
pub open spec fn create_node(s: GSys, g: Graph, n: Node, text: Set<Term>) -> GSys {
    GSys { nodes: s.nodes.insert((g, n), text), ..s }
}

/// L1 (ADR-0004 "removes graph content from every store that holds it"; GraphStores.cls:113-116
/// "no answer outlives erased content"; Eraser.cls:138-144 on the BM25 corpus): after EraseGraph(g),
/// a search of an index that answers for g returns no node of g that was erased, and never scores
/// erased text for a node of g.
pub open spec fn no_erased_answer(before: GSys, after: GSys, g: Graph) -> bool {
    forall|name: IxName, t: Term, n: Node|
        #[trigger] hit(after, name, t, n) && after.bm25[name].graph == g ==> !before.nodes.contains_key((g, n))
}

/// The repair satisfies L1 and leaves every other graph's index as it was.
pub proof fn theorem_repaired_erase_removes_answers(s: GSys, g: Graph)
    ensures
        no_erased_answer(s, erase_graph(s, g, true), g),
        forall|name: IxName| #[trigger] s.bm25.contains_key(name) && s.bm25[name].graph != g ==>
            erase_graph(s, g, true).bm25.contains_key(name) && erase_graph(s, g, true).bm25[name] == s.bm25[name],
{
}

/// W-O5 (F1): build an index for graph 1 over node 5 ("seven"), erase graph 1, search: node 5 is
/// still answered. Re-create node 5 in graph 1 with other text: the erased text still scores for it.
pub proof fn witness_erase_leaves_bm25() {
    let g: Graph = 1;
    let seven: Set<Term> = Set::empty().insert(7);
    let eight: Set<Term> = Set::empty().insert(8);
    let s0 = GSys { nodes: Map::empty().insert((g, 5int), seven), bm25: Map::empty() };
    let s1 = build(s0, 0, g);
    assert(graph_rows(s0, g).contains((g, 5int))) by {
        assert(seven.contains(7));
    }
    assert(graph_rows(s0, g).map(|k: (Graph, Node)| node_of(k)).contains(5)) by {
        assert(graph_rows(s0, g).contains((g, 5int)) && 5 == node_of((g, 5int)));
    }
    assert(s1.bm25[0].docs.dom().contains(5));
    assert(s1.bm25[0].docs[5] == seven);
    assert(hit(s1, 0, 7, 5));
    let s2 = erase_graph(s1, g, false);
    assert(!s2.nodes.contains_key((g, 5)));
    assert(hit(s2, 0, 7, 5));
    assert(!no_erased_answer(s1, s2, g));
    // the same id comes back with other text, and the erased text answers for it
    let s3 = create_node(s2, g, 5, eight);
    assert(hit(s3, 0, 7, 5) && !s3.nodes[(g, 5)].contains(7));
    // the repair removes the answer
    let r2 = erase_graph(s1, g, true);
    assert(!hit(r2, 0, 7, 5));
}

} // verus!
