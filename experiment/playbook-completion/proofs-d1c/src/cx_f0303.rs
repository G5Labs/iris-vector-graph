//! Proved counterexample for control `control_f0303_direct_delete_keeps_stmt` (F-0303), compiled only with it.
//!
//! The live trace breadth-a-live-ledger-stmt (p0303b): a ledger create of the triple allocates statement 0 and the tuple
//! entry; engine.delete_edge deletes the row and leaves both live (not an L1 step; L1's invariant fails: a live
//! statement whose edge is gone); engine.create_edge re-creates the edge (a new row), and an op by tuple then acts on
//! statement 0, allocated for the deleted edge (not an L1 step: the history joins two edges into one statement).
use vstd::prelude::*;
use actors::protocol::*;
use crate::stmt_l1::*;
use crate::stmt_l2::*;
use crate::stmt_runs::*;

verus! {

pub open spec fn z1() -> SS2 { p_lcreate(s0(), 5) }
pub open spec fn z2() -> SS2 { p_ddelete(z1(), 5) }
pub open spec fn z3() -> SS2 { p_dcreate(z2(), 5) }
pub open spec fn z4() -> SS2 { p_lupdate(z3(), 5) }

pub proof fn counterexample_f0303()
    ensures
        init2(s0()),
        step2(s0(), SL2::LCreate { k: 5, id: 0 }, z1()),
        step2(z1(), SL2::DDelete { k: 5 }, z2()),
        !step_or_stutter::<StmtL1>(abss(z1()), labs(SL2::DDelete { k: 5 }), abss(z2())),
        !inv1(abss(z2())),
        step2(z2(), SL2::DCreate { k: 5 }, z3()),
        step2(z3(), SL2::LUpdate { k: 5, id: 0 }, z4()),
        !step_or_stutter::<StmtL1>(abss(z3()), labs(SL2::LUpdate { k: 5, id: 0 }), abss(z4())),
        z4().tuple[5] == 0 && z4().stmt[0].life == 0 && z4().rows[5] == 1,
{
    lemma_s_steps(s0(), 5);
    lemma_s_steps(z1(), 5);
    assert(live_stmts(z2().stmt).contains_key(0));
    assert(!drop_stmts_of(live_stmts(z1().stmt), 5).contains_key(0)) by {
        assert(live_stmts(z1().stmt)[0].k == 5);
    }
    assert(abss(z2()).stmts.contains_key(0) && !abss(z2()).row.contains_key(abss(z2()).stmts[0].k));
    lemma_s_steps(z2(), 5);
    lemma_s_steps(z3(), 5);
    assert(i_lupdate(z3(), 5) == 0);
    assert(abss(z3()).stmts.contains_key(0) && abss(z3()).stmts[0] == (St { k: 5, life: 0 }));
    assert(abss(z3()).row[5] == 1);
    assert(!unnamed(abss(z3()), 5));
    assert(!names(abss(z3()), 0, 5));
}

} // verus!
