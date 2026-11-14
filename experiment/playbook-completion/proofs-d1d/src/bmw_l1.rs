//! Module 07, L1 part 1: one BM25 index and its writers, with the caller's transaction around them.
//!
//! Sources: spec 044 FR-016/FR-018 (specs/044-bm25-index/spec.md:162-164: N, totalLen and df consistent with the
//! documents "at every committed point"), FR-019 (:165: writers are exclusive and atomic), ADR-0007:5 (every write under
//! the index lock in a transaction), decisions.md HD-0701 working answer (intent/HD-0701.md: a Build publishes a complete
//! generation), TXT-X2 / SYS-I3 (a refused command leaves every store as it was), and the nesting rule of 4.6.4
//! (iris_vector_graph/_write_txn.py:1-30: an IVG write nested in a caller's transaction undoes only its own level).
//!
//! Abstraction (explicit): one index name; a document's indexable tokens are given as a set (tokenisation and its
//! stopwords are the namespace model's concern, `bmn_l1`); ranking is not modelled: a search answers the documents it
//! scores and the documents its counters count (N and totalLen are functions of that set), which is what BM25's
//! IDF and length normalisation read. The caller's own work is a set of rows (Graph_KG.docs rows, live check
//! b-07-fc0702-nested-rollback).
//!
//! State: what searchers and the caller see (`db`: the index, `None` when there is none, and the caller's rows) and the
//! caller's open transaction (`open`: what `db` was when it began). Labels: the caller's `CBegin`, `CWrite`, `CCommit`,
//! `CRollback`; `Build` (bm25_build / the index handle), `Insert`, `Delete`, `Drop`, `Search`.
//!
//! Business rules: **a failed write changes nothing** (the index, the caller's rows and the caller's open transaction
//! stay as they were); **a write nested in the caller's transaction goes with the caller's rollback**; **a build
//! replaces the index whole or not at all**; **a search's counters count exactly the documents it scores** (TXT-I2).
//! `inv1` (proved inductive): every stored document has at least one token (IndexDoc returns for an empty one,
//! BM25Index.cls:182; Insert of a text with no token removes the document, :467-468).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct Db { pub idx: Option<Map<int, Set<int>>>, pub rows: Set<int> }
pub struct BW1 { pub db: Db, pub open: Option<Db> }

pub enum BWL1 {
    CBegin,
    CWrite { r: int },
    CCommit,
    CRollback,
    Build { corpus: Map<int, Set<int>>, ok: bool },
    Insert { d: int, toks: Set<int>, ok: bool },
    Delete { d: int, ok: bool },
    Drop,
    Search { ans: Option<(Map<int, Set<int>>, Set<int>)> },
}

pub open spec fn ne(x: Set<int>) -> bool { x != Set::<int>::empty() }

/// What a build over `corpus` (document -> tokens) indexes: the documents with a token.
pub open spec fn indexed(corpus: Map<int, Set<int>>) -> Map<int, Set<int>> {
    Map::new(corpus.dom().filter(|d: int| ne(corpus[d])), |d: int| corpus[d])
}
pub open spec fn curm(idx: Option<Map<int, Set<int>>>) -> Map<int, Set<int>> {
    match idx { Some(m) => m, None => Map::<int, Set<int>>::empty() }
}
/// Insert's effect on the documents: replace `d`, or remove it when its text has no token (BM25Index.cls:467-484).
pub open spec fn put(m: Map<int, Set<int>>, d: int, toks: Set<int>) -> Map<int, Set<int>> {
    if ne(toks) { m.insert(d, toks) } else { m.remove(d) }
}
pub open spec fn del(idx: Option<Map<int, Set<int>>>, d: int) -> Option<Map<int, Set<int>>> {
    match idx { Some(m) => Some(m.remove(d)), None => None }
}
/// What a search scores from: the documents and the set its counters count.
pub open spec fn view(idx: Option<Map<int, Set<int>>>) -> Option<(Map<int, Set<int>>, Set<int>)> {
    match idx { Some(m) => Some((m, m.dom())), None => None }
}

pub struct BwL1;

impl Contract for BwL1 {
    type S = BW1;
    type L = BWL1;

    open spec fn init(s: BW1) -> bool { s.db.idx is None && s.db.rows == Set::<int>::empty() && s.open is None }

    open spec fn next(s: BW1, l: BWL1, t: BW1) -> bool {
        match l {
            BWL1::CBegin => s.open is None && t == (BW1 { db: s.db, open: Some(s.db) }),
            BWL1::CWrite { r } => s.open is Some && t == (BW1 { db: Db { rows: s.db.rows.insert(r), ..s.db }, ..s }),
            BWL1::CCommit => s.open is Some && t == (BW1 { db: s.db, open: None }),
            BWL1::CRollback => s.open is Some && t == (BW1 { db: s.open->Some_0, open: None }),
            BWL1::Build { corpus, ok } =>
                s.open is None && t == (if ok { BW1 { db: Db { idx: Some(indexed(corpus)), ..s.db }, ..s } } else { s }),
            BWL1::Insert { d, toks, ok } =>
                t == (if ok { BW1 { db: Db { idx: Some(put(curm(s.db.idx), d, toks)), ..s.db }, ..s } } else { s }),
            BWL1::Delete { d, ok } =>
                t == (if ok { BW1 { db: Db { idx: del(s.db.idx, d), ..s.db }, ..s } } else { s }),
            BWL1::Drop => s.open is None && t == (BW1 { db: Db { idx: None, ..s.db }, ..s }),
            BWL1::Search { ans } => t == s && ans == view(s.db.idx),
        }
    }
}

pub open spec fn tok_ok(m: Map<int, Set<int>>) -> bool { forall|d: int| #[trigger] m.contains_key(d) ==> ne(m[d]) }
pub open spec fn db_ok(db: Db) -> bool { match db.idx { Some(m) => tok_ok(m), None => true } }
pub open spec fn inv1(s: BW1) -> bool { db_ok(s.db) && match s.open { Some(o) => db_ok(o), None => true } }

proof fn lemma_l1_safe(s: BW1, l: BWL1, t: BW1)
    requires inv1(s), BwL1::next(s, l, t),
    ensures inv1(t),
{
    match l {
        BWL1::Build { corpus, ok } => {
            if ok { assert(tok_ok(indexed(corpus))); }
        }
        BWL1::Insert { d, toks, ok } => {
            if ok {
                let m = put(curm(s.db.idx), d, toks);
                assert forall|e: int| #[trigger] m.contains_key(e) implies ne(m[e]) by {
                    if e != d { assert(curm(s.db.idx).contains_key(e)); }
                }
            }
        }
        BWL1::Delete { d, ok } => {
            if ok && s.db.idx is Some {
                let m = s.db.idx->Some_0.remove(d);
                assert forall|e: int| #[trigger] m.contains_key(e) implies ne(m[e]) by { assert(s.db.idx->Some_0.contains_key(e)); }
            }
        }
        _ => {}
    }
}

impl SafeContract for BwL1 {
    open spec fn inv(s: BW1) -> bool { inv1(s) }
    proof fn init_safe(s: BW1) {}
    proof fn step_safe(s: BW1, l: BWL1, t: BW1) { lemma_l1_safe(s, l, t); }
}

/// SYS-I3 / TXT-X2 and the 4.6.4 nesting rule: a failed Insert or Delete changes nothing, so the caller's open
/// transaction and its uncommitted rows are still there.
pub proof fn theorem_failed_write_changes_nothing(s: BW1, l: BWL1, t: BW1)
    requires BwL1::next(s, l, t), (l matches BWL1::Insert { ok, .. } && !ok) || (l matches BWL1::Delete { ok, .. } && !ok),
    ensures t == s, t.open == s.open, t.db.rows == s.db.rows,
{
}

/// _write_txn.py:7-12: an IVG write nested in the caller's transaction is the caller's to keep or undo.
pub proof fn theorem_nested_write_goes_with_callers_rollback(s: BW1, d: int, toks: Set<int>, t: BW1, u: BW1)
    requires s.open is Some, BwL1::next(s, BWL1::Insert { d, toks, ok: true }, t), BwL1::next(t, BWL1::CRollback, u),
    ensures u.db == s.open->Some_0, u.open is None,
{
}

/// HD-0701 / FR-016: a build replaces the index with the corpus's documents, or (refused) changes nothing.
pub proof fn theorem_build_all_or_nothing(s: BW1, corpus: Map<int, Set<int>>, ok: bool, t: BW1)
    requires BwL1::next(s, BWL1::Build { corpus, ok }, t),
    ensures (ok && t.db.idx == Some(indexed(corpus)) && t.db.rows == s.db.rows) || (!ok && t == s),
{
}

/// TXT-I2 (FR-016/FR-018): N and totalLen are those of exactly the documents a search scores.
pub proof fn theorem_search_counts_its_documents(s: BW1, m: Map<int, Set<int>>, c: Set<int>, t: BW1)
    requires BwL1::next(s, BWL1::Search { ans: Some((m, c)) }, t),
    ensures c == m.dom(),
{
}

} // verus!
