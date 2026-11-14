//! Module 07, L2 part 2: the global ^BM25Idx of a namespace at pin 3eaa79cf (every index's subtree and the stopword
//! node), the readers' graph check and the eraser; refinement of `bmn_l1` for every step, the invariant, and the
//! controls F-C0701, F-0705, F-0707 and F-0702.
//!
//! Layout: `gl` (each name's subtree ^BM25Idx(name): its documents and `cfg graph`, present when Build wrote it,
//! BM25Index.cls:164-168, absent for an index a first Insert created, :461-466); `stop` (the first-level children of
//! ^BM25Idx("__stop__"), Tokenize's stopword test `$Data(^BM25Idx("__stop__", tok))`, :83). Every Tokenize first runs
//! InitStopwords (:41-50): when "the" is not a child it sets all 77 (`eff`), and that write stays.
//!
//! Steps: `Build` (:97-175, with BM25BuildInput's validation, _validate.py:163-179), `Insert` (:442-493), `Drop`
//! (:587-591), `Search` on a surface (`UseGraph`: Cypher ivg.bm25.search / ivg.retrieve under USE GRAPH,
//! translator.py:3133-3134, 3283-3292; `Engine`: the engine's fusion legs and an unscoped Cypher call, which read the
//! index's graph through Info and `_index_graph`, vector.py:164-226, translator.py:3125-3142), `Erase` (the graph
//! eraser's transaction, Eraser.cls; GraphStores.Inventory, GraphStores.cls:26-133).
//!
//! **Reviewed design** (remedies): "__stop__" is refused by the writers (HD-0704, F-0706/F-C0701 remedy); a reader reads
//! an absent `cfg graph` as unknown and answers a scoped search only from an index recorded for that graph (F-0705
//! remedy: Info answers null; F-0707 remedy: compare under USE GRAPH); the eraser drops every index recorded for the
//! erased graph (F-0702 remedy). **As built**: the name is accepted, and Build writes `cfg`, `tf`, `df`, `doc`, `len`
//! beside the stopwords (each then a stopword in every index; Drop deletes the list); Info answers "" for an absent
//! graph, the default graph's name; USE GRAPH searches compare nothing; the eraser does not touch ^BM25Idx.
//!
//! Abstraction of the "__stop__" build (as built only): modelled by its end state, the 77 words and the five
//! structure subscripts (`structw`); its own documents are tokenised with the 77 words. Premises: P-N1 each call is one
//! step; P-N2 no Upgrade and no schema-1 index; P-N3 an index's documents are the nodes of its recorded graph (Build
//! reads only that graph's nodes, :111-130); an index with no recorded graph is not dropped by an erasure (its scoped
//! searches are refused instead).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::bmw_l1::{ne, put};
use crate::bmn_l1::*;

verus! {

pub enum Surf { UseGraph, Engine }
pub struct BN2 { pub gl: Map<int, Ix>, pub stop: Set<int> }

pub enum BNL2 {
    Build { n: int, g: int, corpus: Map<int, Set<int>>, ok: bool },
    Insert { n: int, d: int, text: Set<int>, ok: bool },
    Drop { n: int, ok: bool },
    Search { n: int, g: int, q: Set<int>, ans: Option<Set<int>>, surf: Surf },
    Erase { g: int },
}

pub open spec fn fc0701() -> bool { cfg!(feature = "control_fc0701_stop_name_accepted") }
pub open spec fn f0705() -> bool { cfg!(feature = "control_f0705_absent_graph_is_default") }
pub open spec fn f0707() -> bool { cfg!(feature = "control_f0707_no_scope_check") }
pub open spec fn f0702() -> bool { cfg!(feature = "control_f0702_erase_keeps_index") }

/// "cfg", "tf", "df", "doc", "len"
pub open spec fn structw() -> Set<int> { Set::empty().insert(10int).insert(11int).insert(12int).insert(13int).insert(14int) }
/// InitStopwords: the stopwords in force at a Tokenize (and written by it).
pub open spec fn eff(stop: Set<int>) -> Set<int> { if stop.contains(the()) { stop } else { stop.union(sw()) } }
/// Whether a writer accepts the name.
pub open spec fn accepts(n: int) -> bool { fc0701() || n != stopn() }
/// The graph a reader takes an index to cover: reviewed, the recorded one or unknown; as built (Engine surface),
/// Info's "" for an absent subscript, which is the default graph's name.
pub open spec fn seen(ix: Ix, surf: Surf) -> Option<int> {
    if f0705() && surf is Engine { match ix.graph { Some(g) => Some(g), None => Some(dflt()) } } else { ix.graph }
}
pub open spec fn answers(s: BN2, n: int, g: int, surf: Surf) -> bool {
    s.gl.contains_key(n) && ((f0707() && surf is UseGraph) || seen(s.gl[n], surf) == Some(g))
}

pub open spec fn build2(s: BN2, n: int, g: int, corpus: Map<int, Set<int>>) -> BN2 {
    if n == stopn() { BN2 { gl: s.gl.insert(n, Ix { docs: tokenize(corpus, sw()), graph: Some(g) }), stop: sw().union(structw()) } }
    else { BN2 { gl: s.gl.insert(n, Ix { docs: tokenize(corpus, eff(s.stop)), graph: Some(g) }), stop: eff(s.stop) } }
}
pub open spec fn insert2(s: BN2, n: int, d: int, text: Set<int>) -> BN2 {
    BN2 { gl: s.gl.insert(n, Ix { docs: put(base(s.gl, n).docs, d, toks(text, eff(s.stop))), graph: base(s.gl, n).graph }),
          stop: if n == stopn() { eff(s.stop).union(structw()) } else { eff(s.stop) } }
}
pub open spec fn drop2(s: BN2, n: int) -> BN2 {
    if n == stopn() { BN2 { gl: s.gl.remove(n), stop: Set::empty() } } else { BN2 { gl: s.gl.remove(n), ..s } }
}

pub open spec fn init2(s: BN2) -> bool { s.gl == Map::<int, Ix>::empty() && s.stop == sw() }

pub open spec fn step2(s: BN2, l: BNL2, t: BN2) -> bool {
    match l {
        BNL2::Build { n, g, corpus, ok } => (ok ==> accepts(n)) && t == (if ok { build2(s, n, g, corpus) } else { s }),
        BNL2::Insert { n, d, text, ok } => (ok ==> accepts(n)) && t == (if ok { insert2(s, n, d, text) } else { s }),
        BNL2::Drop { n, ok } => (ok ==> accepts(n)) && t == (if ok { drop2(s, n) } else { s }),
        BNL2::Search { n, g, q, ans, surf } =>
            t == (BN2 { stop: eff(s.stop), ..s })
                && ans == (if answers(s, n, g, surf) { Some(hits(s.gl[n].docs, toks(q, eff(s.stop)))) } else { None }),
        BNL2::Erase { g } => t == (BN2 { gl: if f0702() { s.gl } else { erase(s.gl, g) }, ..s }),
    }
}

pub open spec fn absn(s: BN2) -> BN1 { BN1 { idx: s.gl } }
pub open spec fn labn(l: BNL2) -> Option<BNL1> {
    match l {
        BNL2::Build { n, g, corpus, ok } => Some(BNL1::Build { n, g, corpus, ok }),
        BNL2::Insert { n, d, text, ok } => Some(BNL1::Insert { n, d, text, ok }),
        BNL2::Drop { n, ok } => Some(BNL1::Drop { n, ok }),
        BNL2::Search { n, g, q, ans, surf } => Some(BNL1::Search { n, g, q, ans }),
        BNL2::Erase { g } => Some(BNL1::EraseGraph { g }),
    }
}

/// The stopword node holds exactly the 77 words, and no index is named "__stop__"; the L1 invariant of the indexes.
pub open spec fn inv07n(s: BN2) -> bool { s.stop == sw() && inv1(absn(s)) }

pub struct BnL2;
impl Contract for BnL2 {
    type S = BN2;
    type L = BNL2;
    open spec fn init(s: BN2) -> bool { init2(s) }
    open spec fn next(s: BN2, l: BNL2, t: BN2) -> bool { inv07n(s) && step2(s, l, t) }
}
pub struct BnRaw;
impl Contract for BnRaw {
    type S = BN2;
    type L = BNL2;
    open spec fn init(s: BN2) -> bool { init2(s) }
    open spec fn next(s: BN2, l: BNL2, t: BN2) -> bool { step2(s, l, t) }
}

proof fn lemma_eff(s: BN2)
    requires s.stop == sw(),
    ensures eff(s.stop) == sw(),
{
    assert(sw().contains(the()));
}

proof fn lemma_build(s: BN2, n: int, g: int, corpus: Map<int, Set<int>>, ok: bool, t: BN2)
    requires inv07n(s), step2(s, BNL2::Build { n, g, corpus, ok }, t),
    ensures inv07n(t), step_or_stutter::<BnL1>(absn(s), labn(BNL2::Build { n, g, corpus, ok }), absn(t)),
{
    // "__stop__" is refused before anything is written (HD-0704) (control F-C0701 fails here)
    assert(ok ==> n != stopn());
    lemma_eff(s);
    if ok {
        lemma_tokenize_ok(corpus);
        assert forall|k: int| #[trigger] t.gl.contains_key(k) implies docs_ok(t.gl[k].docs) by {
            if k != n { assert(s.gl.contains_key(k)); }
        }
    }
}

proof fn lemma_insert(s: BN2, n: int, d: int, text: Set<int>, ok: bool, t: BN2)
    requires inv07n(s), step2(s, BNL2::Insert { n, d, text, ok }, t),
    ensures inv07n(t), step_or_stutter::<BnL1>(absn(s), labn(BNL2::Insert { n, d, text, ok }), absn(t)),
{
    // (control F-C0701 fails here)
    assert(ok ==> n != stopn());
    lemma_eff(s);
    if ok {
        assert(docs_ok(base(s.gl, n).docs)) by {
            if !s.gl.contains_key(n) { assert(docs_ok(Map::<int, Set<int>>::empty())); }
        }
        lemma_put_ok(base(s.gl, n).docs, d, text);
        assert forall|k: int| #[trigger] t.gl.contains_key(k) implies docs_ok(t.gl[k].docs) by {
            if k != n { assert(s.gl.contains_key(k)); }
        }
    }
}

proof fn lemma_drop(s: BN2, n: int, ok: bool, t: BN2)
    requires inv07n(s), step2(s, BNL2::Drop { n, ok }, t),
    ensures inv07n(t), step_or_stutter::<BnL1>(absn(s), labn(BNL2::Drop { n, ok }), absn(t)),
{
    // Drop of "__stop__" would delete the stopword list (control F-C0701 fails here)
    assert(ok ==> n != stopn());
    if ok {
        assert forall|k: int| #[trigger] t.gl.contains_key(k) implies docs_ok(t.gl[k].docs) by { assert(s.gl.contains_key(k)); }
    }
}

proof fn lemma_search(s: BN2, n: int, g: int, q: Set<int>, ans: Option<Set<int>>, surf: Surf, t: BN2)
    requires inv07n(s), step2(s, BNL2::Search { n, g, q, ans, surf }, t),
    ensures inv07n(t), step_or_stutter::<BnL1>(absn(s), labn(BNL2::Search { n, g, q, ans, surf }), absn(t)),
{
    lemma_eff(s);
    assert(t == s);
    // a search for graph g answers only from an index recorded for g (controls F-0705 and F-0707 fail here)
    assert(answers(s, n, g, surf) == scoped(s.gl, n, g));
}

proof fn lemma_erase(s: BN2, g: int, t: BN2)
    requires inv07n(s), step2(s, BNL2::Erase { g }, t),
    ensures inv07n(t), step_or_stutter::<BnL1>(absn(s), labn(BNL2::Erase { g }), absn(t)),
{
    // the eraser drops every index recorded for the erased graph (control F-0702 fails here)
    assert(t.gl == erase(s.gl, g));
    assert forall|k: int| #[trigger] t.gl.contains_key(k) implies docs_ok(t.gl[k].docs) by { assert(s.gl.contains_key(k)); }
}

proof fn lemma_step(s: BN2, l: BNL2, t: BN2)
    requires inv07n(s), step2(s, l, t),
    ensures inv07n(t), step_or_stutter::<BnL1>(absn(s), labn(l), absn(t)),
{
    match l {
        BNL2::Build { n, g, corpus, ok } => lemma_build(s, n, g, corpus, ok, t),
        BNL2::Insert { n, d, text, ok } => lemma_insert(s, n, d, text, ok, t),
        BNL2::Drop { n, ok } => lemma_drop(s, n, ok, t),
        BNL2::Search { n, g, q, ans, surf } => lemma_search(s, n, g, q, ans, surf, t),
        BNL2::Erase { g } => lemma_erase(s, g, t),
    }
}

impl Refines<BnL1> for BnL2 {
    open spec fn abs(s: BN2) -> BN1 { absn(s) }
    open spec fn lab(l: BNL2) -> Option<BNL1> { labn(l) }
    proof fn init_refines(s: BN2) {}
    proof fn step_refines(s: BN2, l: BNL2, t: BN2) { lemma_step(s, l, t); }
}

impl SafeContract for BnL2 {
    open spec fn inv(s: BN2) -> bool { inv07n(s) }
    proof fn init_safe(s: BN2) {}
    proof fn step_safe(s: BN2, l: BNL2, t: BN2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<BN2>, labels: Seq<BNL2>, k: int)
    requires execution::<BnRaw>(states, labels), 0 <= k < states.len(),
    ensures inv07n(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution.
pub proof fn theorem_raw_executions_refine(states: Seq<BN2>, labels: Seq<BNL2>)
    requires execution::<BnRaw>(states, labels),
    ensures
        execution::<BnL2>(states, labels),
        abstract_execution::<BnL1>(Seq::new(states.len(), |i: int| absn(states[i])),
                                   Seq::new(labels.len(), |i: int| labn(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv07n(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv07n(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<BnL2>(states, labels));
    trace_refines::<BnL2, BnL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absn(states[i])) =~= Seq::new(states.len(), |i: int| <BnL2 as Refines<BnL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labn(labels[i])) =~= Seq::new(labels.len(), |i: int| <BnL2 as Refines<BnL1>>::lab(labels[i])));
}

/// TXT-D1 on the layout: the stopword node never holds anything but the 77 words, so Tokenize drops exactly them.
pub proof fn theorem_stopword_node_is_the_77(s: BN2)
    requires inv07n(s),
    ensures eff(s.stop) == sw(), !s.gl.contains_key(stopn()),
{
    lemma_eff(s);
}

} // verus!
