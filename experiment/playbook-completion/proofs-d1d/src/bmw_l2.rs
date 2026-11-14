//! Module 07, L2 part 1: one index of ^BM25Idx and its writers at pin 3eaa79cf, with the caller's transaction levels;
//! refinement of `bmw_l1` for every step, the invariant, and the controls F-C0702, F-0701 and F-0704.
//!
//! Layout (iris_src/src/Graph/KG/BM25Index.cls:6-18): the postings `tf(tok, doc)`, the token record `doc(doc)` and
//! `len(doc)` of each document (`docs`: document -> token record); the header counters `cfg N` and `cfg totalLen`
//! (`counted`: the set of documents they count, N its size and totalLen the sum of their lengths -- an abstraction of
//! the arithmetic, exact while the header is consistent); the header's presence (`hdr`: `cfg N` and `cfg schema` = 2);
//! the caller's rows; IRIS's transaction levels as the image each open level would roll back to (`caller`: the
//! caller's SQL START TRANSACTION, $TLEVEL 1); the write lock `^BM25Idx(name,"lock")` (held by a running build in the
//! reviewed design: `b is Some`); a running build (`b`: its corpus, the documents still to index, the documents it has
//! counted in its local N, and its shadow generation).
//!
//! Steps: the caller's `CBegin`/`CWrite`/`CCommit`/`CRollback`; `Ins`/`Del` (Insert :442-493, Delete :496-514: lock,
//! RequireWritable, TSTART, body, TCOMMIT, as one step; `fail` is an error inside the Try: <SUBSCRIPT> on a long id,
//! RequireWritable after an Upgrade began, <UNDEFINED> after a concurrent Drop); `BStart`, `BDoc` (IndexDoc :178-205),
//! `BHeader` (:160-170; `refused`: the index handle's IndexNotBuiltError for 0 rows, vector.py:299-310); `Drop`
//! (:587-591); `Search`.
//!
//! **Reviewed design** (findings' remedies, HD-0701 working answer): a failed Insert/Delete rolls back its own level
//! only, TROLLBACK 1 (F-C0702 remedy, as _write_txn does); Build takes the write lock for its run, writes a shadow
//! generation and publishes it with its header in one step (F-0701 remedy); a refused build publishes nothing (F-0704
//! remedy: refuse before replacing); Drop takes the lock. **As built**: `If $TLevel > 0 TRollback` (:487, :508) rolls
//! back every level; Build kills the live index (:99) and rewrites it in place, header last, with no lock and no
//! transaction, so writers and Drop do not wait for it; the handle refuses after Build has replaced the index.
//!
//! Premises: P-W1 an Insert/Delete is one step (it holds the lock; interleaving inside it is not modelled); P-W2 Build
//! and Drop run with no caller transaction open, and no caller transaction begins while a build runs; P-W3 the writer
//! runs in the caller's server process (as in b-07-fc0702-nested-rollback; otherwise its level is not nested and the
//! nesting rule is vacuous); P-W4 no Upgrade, no schema-1 index, no lock timeout (a timeout refuses before the Try and
//! changes nothing).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::bmw_l1::*;

verus! {

pub struct Img { pub docs: Map<int, Set<int>>, pub counted: Set<int>, pub hdr: bool, pub rows: Set<int> }
pub struct Bld { pub corpus: Map<int, Set<int>>, pub todo: Set<int>, pub loc: Set<int>, pub shadow: Map<int, Set<int>> }
pub struct BW2 { pub cur: Img, pub caller: Option<Img>, pub b: Option<Bld> }

pub enum BWL2 {
    CBegin,
    CWrite { r: int },
    CCommit,
    CRollback,
    Ins { d: int, toks: Set<int>, fail: bool },
    Del { d: int, fail: bool },
    BStart { corpus: Map<int, Set<int>> },
    BDoc { d: int },
    BHeader { corpus: Map<int, Set<int>>, refused: bool },
    Drop,
    Search { ans: Option<(Map<int, Set<int>>, Set<int>)> },
}

pub open spec fn fc0702() -> bool { cfg!(feature = "control_fc0702_bare_trollback") }
pub open spec fn f0701() -> bool { cfg!(feature = "control_f0701_build_in_place") }
pub open spec fn f0704() -> bool { cfg!(feature = "control_f0704_late_refusal") }

pub open spec fn killed(c: Img) -> Img { Img { docs: Map::empty(), counted: Set::empty(), hdr: false, rows: c.rows } }

/// Insert's body (BM25Index.cls:461-488): a header if none (N = 0, schema 2), RemoveDoc (:416-437), the new document.
pub open spec fn ins_body(c: Img, d: int, toks: Set<int>) -> Img {
    let c1 = if c.hdr { c } else { Img { hdr: true, counted: Set::empty(), ..c } };
    let c2 = Img { docs: c1.docs.remove(d), counted: c1.counted.remove(d), ..c1 };
    if ne(toks) { Img { docs: c2.docs.insert(d, toks), counted: c2.counted.insert(d), ..c2 } } else { c2 }
}
/// Delete's body (:498-506): nothing for an index with no header, else RemoveDoc.
pub open spec fn del_body(c: Img, d: int) -> Img {
    if c.hdr { Img { docs: c.docs.remove(d), counted: c.counted.remove(d), ..c } } else { c }
}
/// A failed Insert/Delete's Catch. Reviewed: TROLLBACK 1 of its own level, the state before the call. As built
/// (`If $TLevel > 0 TRollback`): every level, back to the caller's TSTART, which ends the caller's transaction too.
pub open spec fn failed(s: BW2) -> BW2 {
    if fc0702() {
        match s.caller { Some(img) => BW2 { cur: img, caller: None, ..s }, None => s }
    } else { s }
}
/// Whether the write lock keeps a writer or Drop out: in the reviewed design a running build holds it.
pub open spec fn free(s: BW2) -> bool { f0701() || s.b is None }

pub open spec fn bdoc(bb: Bld, d: int) -> Bld {
    Bld { todo: bb.todo.remove(d),
          loc: if ne(bb.corpus[d]) { bb.loc.insert(d) } else { bb.loc },
          shadow: if ne(bb.corpus[d]) { bb.shadow.insert(d, bb.corpus[d]) } else { bb.shadow }, ..bb }
}
pub open spec fn published(s: BW2, bb: Bld) -> Img { Img { docs: bb.shadow, counted: bb.loc, hdr: true, rows: s.cur.rows } }

pub open spec fn init2(s: BW2) -> bool {
    s.cur == (Img { docs: Map::empty(), counted: Set::empty(), hdr: false, rows: Set::empty() }) && s.caller is None && s.b is None
}

pub open spec fn step2(s: BW2, l: BWL2, t: BW2) -> bool {
    match l {
        BWL2::CBegin => s.caller is None && s.b is None && t == (BW2 { caller: Some(s.cur), ..s }),
        BWL2::CWrite { r } => s.caller is Some && t == (BW2 { cur: Img { rows: s.cur.rows.insert(r), ..s.cur }, ..s }),
        BWL2::CCommit => s.caller is Some && t == (BW2 { caller: None, ..s }),
        BWL2::CRollback => s.caller is Some && t == (BW2 { cur: s.caller->Some_0, caller: None, ..s }),
        BWL2::Ins { d, toks, fail } =>
            free(s) && t == (if fail { failed(s) } else { BW2 { cur: ins_body(s.cur, d, toks), ..s } }),
        BWL2::Del { d, fail } =>
            free(s) && t == (if fail { failed(s) } else { BW2 { cur: del_body(s.cur, d), ..s } }),
        BWL2::BStart { corpus } =>
            s.b is None && s.caller is None
                && t == (BW2 { cur: if f0701() { killed(s.cur) } else { s.cur },
                               b: Some(Bld { corpus, todo: corpus.dom(), loc: Set::empty(), shadow: Map::empty() }), ..s }),
        BWL2::BDoc { d } =>
            s.b is Some && s.b->Some_0.todo.contains(d)
                && t == (BW2 { cur: if f0701() && ne(s.b->Some_0.corpus[d]) { Img { docs: s.cur.docs.insert(d, s.b->Some_0.corpus[d]), ..s.cur } } else { s.cur },
                               b: Some(bdoc(s.b->Some_0, d)), ..s }),
        BWL2::BHeader { corpus, refused } =>
            s.b is Some && corpus == s.b->Some_0.corpus && s.b->Some_0.todo == Set::<int>::empty()
                && (refused ==> s.b->Some_0.loc == Set::<int>::empty())
                && t == (BW2 {
                    cur: if f0701() { Img { counted: s.b->Some_0.loc, hdr: true, ..s.cur } }
                         else if refused && !f0704() { s.cur } else { published(s, s.b->Some_0) },
                    b: None, ..s }),
        BWL2::Drop => free(s) && s.caller is None && t == (BW2 { cur: killed(s.cur), ..s }),
        BWL2::Search { ans } => t == s && ans == (if s.cur.hdr { Some((s.cur.docs, s.cur.counted)) } else { None }),
    }
}

pub open spec fn dbof(c: Img) -> Db { Db { idx: if c.hdr { Some(c.docs) } else { None }, rows: c.rows } }
pub open spec fn absw(s: BW2) -> BW1 {
    BW1 { db: dbof(s.cur), open: match s.caller { Some(c) => Some(dbof(c)), None => None } }
}
pub open spec fn labw(l: BWL2) -> Option<BWL1> {
    match l {
        BWL2::CBegin => Some(BWL1::CBegin),
        BWL2::CWrite { r } => Some(BWL1::CWrite { r }),
        BWL2::CCommit => Some(BWL1::CCommit),
        BWL2::CRollback => Some(BWL1::CRollback),
        BWL2::Ins { d, toks, fail } => Some(BWL1::Insert { d, toks, ok: !fail }),
        BWL2::Del { d, fail } => Some(BWL1::Delete { d, ok: !fail }),
        BWL2::BStart { corpus } => None,
        BWL2::BDoc { d } => None,
        BWL2::BHeader { corpus, refused } => Some(BWL1::Build { corpus, ok: !refused }),
        BWL2::Drop => Some(BWL1::Drop),
        BWL2::Search { ans } => Some(BWL1::Search { ans }),
    }
}
/// The header counts exactly the stored documents; no header, no documents; every document has a token.
pub open spec fn cons(c: Img) -> bool {
    &&& (c.hdr ==> c.counted == c.docs.dom())
    &&& (!c.hdr ==> c.docs == Map::<int, Set<int>>::empty() && c.counted == Set::<int>::empty())
    &&& tok_ok(c.docs)
}
/// A running build's shadow holds exactly the corpus's documents with a token it has indexed so far.
pub open spec fn bld_ok(bb: Bld) -> bool {
    &&& forall|d: int| #[trigger] bb.todo.contains(d) ==> bb.corpus.contains_key(d)
    &&& bb.loc == bb.shadow.dom()
    &&& forall|d: int| #[trigger] bb.shadow.contains_key(d) ==>
            bb.corpus.contains_key(d) && bb.shadow[d] == bb.corpus[d] && ne(bb.corpus[d]) && !bb.todo.contains(d)
    &&& forall|d: int| #[trigger] bb.corpus.contains_key(d) ==> bb.todo.contains(d) || !ne(bb.corpus[d]) || bb.shadow.contains_key(d)
}
pub open spec fn inv07w(s: BW2) -> bool {
    &&& cons(s.cur)
    &&& (match s.caller { Some(c) => cons(c), None => true })
    &&& (match s.b { Some(bb) => s.caller is None && bld_ok(bb), None => true })
}

pub struct BwL2;
impl Contract for BwL2 {
    type S = BW2;
    type L = BWL2;
    open spec fn init(s: BW2) -> bool { init2(s) }
    open spec fn next(s: BW2, l: BWL2, t: BW2) -> bool { inv07w(s) && step2(s, l, t) }
}
pub struct BwRaw;
impl Contract for BwRaw {
    type S = BW2;
    type L = BWL2;
    open spec fn init(s: BW2) -> bool { init2(s) }
    open spec fn next(s: BW2, l: BWL2, t: BW2) -> bool { step2(s, l, t) }
}

proof fn lemma_ins(s: BW2, d: int, toks: Set<int>, fail: bool, t: BW2)
    requires inv07w(s), step2(s, BWL2::Ins { d, toks, fail }, t),
    ensures inv07w(t), step_or_stutter::<BwL1>(absw(s), labw(BWL2::Ins { d, toks, fail }), absw(t)),
{
    if fail {
        // a failed Insert takes back its own level only (TROLLBACK 1): the caller's transaction and rows stay
        // (control F-C0702 fails here)
        assert(t == s);
    } else {
        let c = s.cur;
        let n = ins_body(c, d, toks);
        assert(n.docs =~= put(curm(dbof(c).idx), d, toks));
        assert(n.counted =~= n.docs.dom());
        assert forall|e: int| #[trigger] n.docs.contains_key(e) implies ne(n.docs[e]) by {
            if e != d { assert(c.docs.contains_key(e)); }
        }
    }
}

proof fn lemma_del(s: BW2, d: int, fail: bool, t: BW2)
    requires inv07w(s), step2(s, BWL2::Del { d, fail }, t),
    ensures inv07w(t), step_or_stutter::<BwL1>(absw(s), labw(BWL2::Del { d, fail }), absw(t)),
{
    if fail {
        // the same Catch as Insert's (BM25Index.cls:508): its own level only (control F-C0702 fails here)
        assert(t == s);
    } else if s.cur.hdr {
        let n = del_body(s.cur, d);
        assert(n.counted =~= n.docs.dom());
        assert forall|e: int| #[trigger] n.docs.contains_key(e) implies ne(n.docs[e]) by { assert(s.cur.docs.contains_key(e)); }
    }
}

proof fn lemma_bstart(s: BW2, corpus: Map<int, Set<int>>, t: BW2)
    requires inv07w(s), step2(s, BWL2::BStart { corpus }, t),
    ensures inv07w(t), step_or_stutter::<BwL1>(absw(s), labw(BWL2::BStart { corpus }), absw(t)),
{
    // the build writes a shadow generation under the lock: searchers still see the old index
    // (control F-0701 fails here: Build kills the live index first, BM25Index.cls:99)
    assert(t.cur == s.cur);
    assert(Map::<int, Set<int>>::empty().dom() =~= Set::<int>::empty());
}

proof fn lemma_bdoc(s: BW2, d: int, t: BW2)
    requires inv07w(s), step2(s, BWL2::BDoc { d }, t),
    ensures inv07w(t), step_or_stutter::<BwL1>(absw(s), labw(BWL2::BDoc { d }), absw(t)),
{
    // IndexDoc writes the shadow, not the live index (control F-0701 fails here)
    assert(t.cur == s.cur);
    let bb = s.b->Some_0;
    let nb = bdoc(bb, d);
    assert(nb.loc =~= nb.shadow.dom());
}

proof fn lemma_bheader(s: BW2, corpus: Map<int, Set<int>>, refused: bool, t: BW2)
    requires inv07w(s), step2(s, BWL2::BHeader { corpus, refused }, t),
    ensures inv07w(t), step_or_stutter::<BwL1>(absw(s), labw(BWL2::BHeader { corpus, refused }), absw(t)),
{
    let bb = s.b->Some_0;
    if refused {
        // a refused build publishes nothing (control F-0704 fails here; control F-0701 too: the live index is gone)
        assert(t.cur == s.cur);
    } else {
        // the shadow is the corpus's indexed documents, published with its header in one step
        // (control F-0701 fails here: the header counts the build's local N, not the stored documents)
        assert(bb.shadow =~= indexed(bb.corpus)) by {
            assert forall|e: int| #[trigger] indexed(bb.corpus).contains_key(e) implies bb.shadow.contains_key(e) by {
                assert(!bb.todo.contains(e));
            }
        }
        assert(t.cur == published(s, bb));
    }
}

proof fn lemma_step(s: BW2, l: BWL2, t: BW2)
    requires inv07w(s), step2(s, l, t),
    ensures inv07w(t), step_or_stutter::<BwL1>(absw(s), labw(l), absw(t)),
{
    match l {
        BWL2::Ins { d, toks, fail } => lemma_ins(s, d, toks, fail, t),
        BWL2::Del { d, fail } => lemma_del(s, d, fail, t),
        BWL2::BStart { corpus } => lemma_bstart(s, corpus, t),
        BWL2::BDoc { d } => lemma_bdoc(s, d, t),
        BWL2::BHeader { corpus, refused } => lemma_bheader(s, corpus, refused, t),
        BWL2::Drop => { assert(Map::<int, Set<int>>::empty().dom() =~= Set::<int>::empty()); }
        _ => {}
    }
}

impl Refines<BwL1> for BwL2 {
    open spec fn abs(s: BW2) -> BW1 { absw(s) }
    open spec fn lab(l: BWL2) -> Option<BWL1> { labw(l) }
    proof fn init_refines(s: BW2) {}
    proof fn step_refines(s: BW2, l: BWL2, t: BW2) { lemma_step(s, l, t); }
}

impl SafeContract for BwL2 {
    open spec fn inv(s: BW2) -> bool { inv07w(s) }
    proof fn init_safe(s: BW2) { assert(Map::<int, Set<int>>::empty().dom() =~= Set::<int>::empty()); }
    proof fn step_safe(s: BW2, l: BWL2, t: BW2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<BW2>, labels: Seq<BWL2>, k: int)
    requires execution::<BwRaw>(states, labels), 0 <= k < states.len(),
    ensures inv07w(states[k]),
    decreases k,
{
    if k == 0 { assert(Map::<int, Set<int>>::empty().dom() =~= Set::<int>::empty()); }
    else {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution.
pub proof fn theorem_raw_executions_refine(states: Seq<BW2>, labels: Seq<BWL2>)
    requires execution::<BwRaw>(states, labels),
    ensures
        execution::<BwL2>(states, labels),
        abstract_execution::<BwL1>(Seq::new(states.len(), |i: int| absw(states[i])),
                                   Seq::new(labels.len(), |i: int| labw(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv07w(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv07w(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<BwL2>(states, labels));
    trace_refines::<BwL2, BwL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absw(states[i])) =~= Seq::new(states.len(), |i: int| <BwL2 as Refines<BwL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labw(labels[i])) =~= Seq::new(labels.len(), |i: int| <BwL2 as Refines<BwL1>>::lab(labels[i])));
}

/// TXT-I2 on the layout (FR-016/FR-018): at every point the header's N and totalLen are those of the stored documents.
pub proof fn theorem_header_counts_the_stored_documents(s: BW2)
    requires inv07w(s), s.cur.hdr,
    ensures s.cur.counted == s.cur.docs.dom(),
{
}

/// HD-0701: no step of a running build before its header changes what a searcher sees.
pub proof fn theorem_build_invisible_until_published(s: BW2, l: BWL2, t: BW2)
    requires inv07w(s), step2(s, l, t), l is BStart || l is BDoc,
    ensures absw(t) == absw(s),
{
    lemma_step(s, l, t);
}

} // verus!
