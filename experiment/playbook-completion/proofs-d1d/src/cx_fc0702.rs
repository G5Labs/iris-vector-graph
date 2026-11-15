//! Proved counterexample for control `control_fc0702_bare_trollback` (F-C0702), compiled only with it.
//!
//! The live check b-07-fc0702-nested-rollback: SQL START TRANSACTION and a caller INSERT ($TLEVEL 1); a bm25_insert
//! that fails inside Insert's Try (a 604-character id, <SUBSCRIPT>) leaves $TLEVEL 0 and the caller's row gone. Here:
//! the caller begins, writes row 1, and a failing Insert's `If $TLevel > 0 TRollback` (BM25Index.cls:487) ends the
//! caller's transaction and takes its row: the failed write is not an L1 step (L1: a failed write changes nothing).
use vstd::prelude::*;
use actors::protocol::*;
use crate::bmw_l1::*;
use crate::bmw_l2::*;
use crate::bmw_runs::*;

verus! {

pub open spec fn t1() -> Set<int> { Set::empty().insert(7int) }
pub open spec fn c1() -> BW2 { p_cbegin(w0()) }
pub open spec fn c2() -> BW2 { p_cwrite(c1(), 1) }
pub open spec fn c3() -> BW2 { p_ins(c2(), 5, t1(), true) }

pub proof fn counterexample_fc0702()
    ensures
        init2(w0()),
        step2(w0(), BWL2::CBegin, c1()),
        step2(c1(), BWL2::CWrite { r: 1 }, c2()),
        step2(c2(), BWL2::Ins { d: 5, toks: t1(), fail: true }, c3()),
        !step_or_stutter::<BwL1>(absw(c2()), labw(BWL2::Ins { d: 5, toks: t1(), fail: true }), absw(c3())),
        c2().caller is Some && c2().cur.rows.contains(1),
        c3().caller is None && !c3().cur.rows.contains(1),
{
    lemma_w_steps(w0(), 1, 5, t1(), true, Map::empty(), false);
    lemma_w_steps(c1(), 1, 5, t1(), true, Map::empty(), false);
    lemma_w_steps(c2(), 1, 5, t1(), true, Map::empty(), false);
    assert(c2().cur.rows.contains(1));
    assert(!c3().cur.rows.contains(1));
    assert(absw(c3()).db.rows != absw(c2()).db.rows);
}

} // verus!
