//! Module 07, L1 part 2: the BM25 indexes of a namespace (names, tokens, the graph each covers, erasure).
//!
//! Sources: TXT-D1 and docs/USER_GUIDE.md:886-891 (exactly the 77 listed English words are stopwords, for documents
//! and queries alike); decisions.md HD-0704 (intent/HD-0704.md, status supported: `^BM25Idx("__stop__")` is the
//! stopword list, not an index, BM25Index.cls:626-631, R165); TXT-I7 and HD-0703 (with a graph in scope a BM25 call
//! answers only from an index built for that graph, never another graph's); TXT-B8.3 (an index whose graph is not known
//! is never taken as the default graph's own); CONTEXT.md:198-208 and GraphStores.cls:112-115 (erasure removes content
//! from every store that holds it: no answer outlives erased content), F-0702's remedy (drop the indexes built for the
//! erased graph inside the erase).
//!
//! Abstraction (explicit): words are integers; a text is the set of its words; tokenisation is set difference with the
//! stopwords (`sw()`: two words standing for the 77, word 1 standing for "the"); ranking is not modelled: a search
//! answers the documents that hold a query token (`hits`). Index names are integers and `stopn()` is "__stop__". A
//! graph is an integer and `dflt()` is the default graph ("").
//!
//! Labels: `Build` (bm25_build / the index handle, graph g recorded), `Insert` (bm25_insert: a first Insert creates an
//! index that records no graph, BM25Index.cls:461-466), `Drop`, `Search` (any BM25 search surface asked for graph g:
//! Cypher ivg.bm25.search / ivg.retrieve under USE GRAPH, engine fusion legs, kg_BM25), `EraseGraph` (the graph eraser).
//!
//! Business rules: **"__stop__" is not an index name** (Build, Insert and Drop of it are refusals that change
//! nothing); **a document's tokens are its words less the 77 stopwords, in every index**; **a search for graph g
//! answers only from an index recorded for g** (an index with no recorded graph answers no scoped search, the default
//! graph's included); **after a graph is erased no index built for it remains**. `inv1` (proved inductive): no index
//! is named "__stop__", and every stored document has a token and no stopword.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::bmw_l1::{ne, put};

verus! {

pub struct Ix { pub docs: Map<int, Set<int>>, pub graph: Option<int> }
pub struct BN1 { pub idx: Map<int, Ix> }

pub enum BNL1 {
    Build { n: int, g: int, corpus: Map<int, Set<int>>, ok: bool },
    Insert { n: int, d: int, text: Set<int>, ok: bool },
    Drop { n: int, ok: bool },
    Search { n: int, g: int, q: Set<int>, ans: Option<Set<int>> },
    EraseGraph { g: int },
}

/// "__stop__"
pub open spec fn stopn() -> int { 0 }
/// the default graph ("")
pub open spec fn dflt() -> int { 0 }
/// "the" (InitStopwords' marker word, BM25Index.cls:44)
pub open spec fn the() -> int { 1 }
/// the 77 stopwords
pub open spec fn sw() -> Set<int> { Set::empty().insert(the()).insert(2int) }
/// a document's tokens: its words less the stopwords in force
pub open spec fn toks(text: Set<int>, stop: Set<int>) -> Set<int> { text.difference(stop) }
pub open spec fn tokenize(corpus: Map<int, Set<int>>, stop: Set<int>) -> Map<int, Set<int>> {
    Map::new(corpus.dom().filter(|d: int| ne(corpus[d].difference(stop))), |d: int| corpus[d].difference(stop))
}
/// the documents a query's tokens find
pub open spec fn hits(docs: Map<int, Set<int>>, q: Set<int>) -> Set<int> { docs.dom().filter(|d: int| ne(docs[d].intersect(q))) }
pub open spec fn base(idx: Map<int, Ix>, n: int) -> Ix {
    if idx.contains_key(n) { idx[n] } else { Ix { docs: Map::empty(), graph: None } }
}
pub open spec fn scoped(idx: Map<int, Ix>, n: int, g: int) -> bool { idx.contains_key(n) && idx[n].graph == Some(g) }
pub open spec fn erase(idx: Map<int, Ix>, g: int) -> Map<int, Ix> {
    Map::new(idx.dom().filter(|n: int| idx[n].graph != Some(g)), |n: int| idx[n])
}

pub struct BnL1;

impl Contract for BnL1 {
    type S = BN1;
    type L = BNL1;

    open spec fn init(s: BN1) -> bool { s.idx == Map::<int, Ix>::empty() }

    open spec fn next(s: BN1, l: BNL1, t: BN1) -> bool {
        match l {
            BNL1::Build { n, g, corpus, ok } =>
                (n == stopn() ==> !ok)
                    && t == (if ok { BN1 { idx: s.idx.insert(n, Ix { docs: tokenize(corpus, sw()), graph: Some(g) }) } } else { s }),
            BNL1::Insert { n, d, text, ok } =>
                (n == stopn() ==> !ok)
                    && t == (if ok { BN1 { idx: s.idx.insert(n, Ix { docs: put(base(s.idx, n).docs, d, toks(text, sw())),
                                                                     graph: base(s.idx, n).graph }) } } else { s }),
            BNL1::Drop { n, ok } => (n == stopn() ==> !ok) && t == (if ok { BN1 { idx: s.idx.remove(n) } } else { s }),
            BNL1::Search { n, g, q, ans } =>
                t == s && ans == (if scoped(s.idx, n, g) { Some(hits(s.idx[n].docs, toks(q, sw()))) } else { None }),
            BNL1::EraseGraph { g } => t == (BN1 { idx: erase(s.idx, g) }),
        }
    }
}

pub open spec fn docs_ok(m: Map<int, Set<int>>) -> bool {
    forall|d: int| #[trigger] m.contains_key(d) ==> ne(m[d]) && m[d].disjoint(sw())
}
pub open spec fn inv1(s: BN1) -> bool {
    &&& !s.idx.contains_key(stopn())
    &&& forall|n: int| #[trigger] s.idx.contains_key(n) ==> docs_ok(s.idx[n].docs)
}

pub proof fn lemma_tokenize_ok(corpus: Map<int, Set<int>>)
    ensures docs_ok(tokenize(corpus, sw())),
{
    let m = tokenize(corpus, sw());
    assert forall|d: int| #[trigger] m.contains_key(d) implies ne(m[d]) && m[d].disjoint(sw()) by {
        assert(m[d] == corpus[d].difference(sw()));
    }
}

pub proof fn lemma_put_ok(m: Map<int, Set<int>>, d: int, text: Set<int>)
    requires docs_ok(m),
    ensures docs_ok(put(m, d, toks(text, sw()))),
{
    let p = put(m, d, toks(text, sw()));
    assert forall|e: int| #[trigger] p.contains_key(e) implies ne(p[e]) && p[e].disjoint(sw()) by {
        if e != d { assert(m.contains_key(e)); }
    }
}

proof fn lemma_l1_safe(s: BN1, l: BNL1, t: BN1)
    requires inv1(s), BnL1::next(s, l, t),
    ensures inv1(t),
{
    match l {
        BNL1::Build { n, g, corpus, ok } => {
            if ok {
                lemma_tokenize_ok(corpus);
                assert forall|k: int| #[trigger] t.idx.contains_key(k) implies docs_ok(t.idx[k].docs) by {
                    if k != n { assert(s.idx.contains_key(k)); }
                }
            }
        }
        BNL1::Insert { n, d, text, ok } => {
            if ok {
                assert(docs_ok(base(s.idx, n).docs)) by {
                    if !s.idx.contains_key(n) { assert(docs_ok(Map::<int, Set<int>>::empty())); }
                }
                lemma_put_ok(base(s.idx, n).docs, d, text);
                assert forall|k: int| #[trigger] t.idx.contains_key(k) implies docs_ok(t.idx[k].docs) by {
                    if k != n { assert(s.idx.contains_key(k)); }
                }
            }
        }
        BNL1::Drop { n, ok } => {
            if ok {
                assert forall|k: int| #[trigger] t.idx.contains_key(k) implies docs_ok(t.idx[k].docs) by { assert(s.idx.contains_key(k)); }
            }
        }
        BNL1::EraseGraph { g } => {
            assert forall|k: int| #[trigger] t.idx.contains_key(k) implies docs_ok(t.idx[k].docs) by { assert(s.idx.contains_key(k)); }
        }
        _ => {}
    }
}

impl SafeContract for BnL1 {
    open spec fn inv(s: BN1) -> bool { inv1(s) }
    proof fn init_safe(s: BN1) {}
    proof fn step_safe(s: BN1, l: BNL1, t: BN1) { lemma_l1_safe(s, l, t); }
}

/// HD-0704: Build, Insert and Drop of "__stop__" are refusals that change nothing.
pub proof fn theorem_stop_name_is_not_an_index(s: BN1, l: BNL1, t: BN1)
    requires BnL1::next(s, l, t),
        (l matches BNL1::Build { n, .. } && n == stopn()) || (l matches BNL1::Insert { n, .. } && n == stopn())
            || (l matches BNL1::Drop { n, .. } && n == stopn()),
    ensures t == s,
{
}

/// TXT-D1: a built index's documents are their words less exactly the 77 stopwords.
pub proof fn theorem_tokens_are_words_less_the_stopwords(s: BN1, n: int, g: int, corpus: Map<int, Set<int>>, t: BN1, d: int)
    requires BnL1::next(s, BNL1::Build { n, g, corpus, ok: true }, t), corpus.contains_key(d), ne(corpus[d].difference(sw())),
    ensures t.idx[n].docs.contains_key(d), t.idx[n].docs[d] == corpus[d].difference(sw()),
{
}

/// TXT-I7 / HD-0703 / TXT-B8.3: a search for graph g that answers read an index recorded for g.
pub proof fn theorem_scoped_search_reads_its_graphs_index(s: BN1, n: int, g: int, q: Set<int>, a: Set<int>, t: BN1)
    requires BnL1::next(s, BNL1::Search { n, g, q, ans: Some(a) }, t),
    ensures s.idx.contains_key(n) && s.idx[n].graph == Some(g),
{
}

/// CONTEXT.md:198-208 (F-0702): after graph g is erased, no index built for g remains and no search for g answers.
pub proof fn theorem_erase_leaves_no_index_of_the_graph(s: BN1, g: int, t: BN1, n: int, q: Set<int>, a: Set<int>, u: BN1)
    requires BnL1::next(s, BNL1::EraseGraph { g }, t),
    ensures
        forall|k: int| #[trigger] t.idx.contains_key(k) ==> t.idx[k].graph != Some(g),
        !BnL1::next(t, BNL1::Search { n, g, q, ans: Some(a) }, u),
{
}

} // verus!
