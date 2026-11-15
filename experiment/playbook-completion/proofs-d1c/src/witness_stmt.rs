//! Non-vacuity of the reviewed statement model (compiled without its control): a ledger create, an op by tuple on its
//! statement, a ledger delete; a direct create, an op by tuple that gives the unrecorded edge a statement, a direct
//! delete that ends it (through EraseEdgeRow); a direct re-create, whose op by tuple gets a new statement.
use vstd::prelude::*;
use crate::stmt_l2::*;
use crate::stmt_runs::*;

verus! {

pub open spec fn w1() -> SS2 { p_lcreate(s0(), 5) }
pub open spec fn w2() -> SS2 { p_lupdate(w1(), 5) }
pub open spec fn w3() -> SS2 { p_ldelete(w2(), 5) }
pub open spec fn w4() -> SS2 { p_dcreate(w3(), 5) }
pub open spec fn w5() -> SS2 { p_lupdate(w4(), 5) }
pub open spec fn w6() -> SS2 { p_ddelete(w5(), 5) }
pub open spec fn w7() -> SS2 { p_dcreate(w6(), 5) }
pub open spec fn w8() -> SS2 { p_lupdate(w7(), 5) }

pub proof fn witness_stmt()
    ensures
        init2(s0()),
        step2(s0(), SL2::LCreate { k: 5, id: 0 }, w1()),
        step2(w1(), SL2::LUpdate { k: 5, id: 0 }, w2()),
        step2(w2(), SL2::LDelete { k: 5, id: 0 }, w3()),
        !w3().stmt[0].live,
        step2(w3(), SL2::DCreate { k: 5 }, w4()),
        step2(w4(), SL2::LUpdate { k: 5, id: 1 }, w5()),
        w5().stmt[1].life == 1 && w5().rows[5] == 1,
        step2(w5(), SL2::DDelete { k: 5 }, w6()),
        !w6().stmt.contains_key(1) && !w6().tuple.contains_key(5),
        step2(w6(), SL2::DCreate { k: 5 }, w7()),
        step2(w7(), SL2::LUpdate { k: 5, id: 2 }, w8()),
        w8().tuple[5] == 2 && w8().stmt[2].life == 2 && w8().rows[5] == 2,
{
    lemma_s_steps(s0(), 5);
    lemma_s_steps(w1(), 5);
    assert(i_lupdate(w1(), 5) == 0);
    lemma_s_steps(w2(), 5);
    assert(w2().tuple[5] == 0);
    lemma_s_steps(w3(), 5);
    lemma_s_steps(w4(), 5);
    assert(i_lupdate(w4(), 5) == 1);
    lemma_s_steps(w5(), 5);
    lemma_s_steps(w6(), 5);
    assert(!w6().tuple.contains_key(5));
    lemma_s_steps(w7(), 5);
    assert(i_lupdate(w7(), 5) == 2);
}

} // verus!
