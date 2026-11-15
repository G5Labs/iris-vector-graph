//! Proved counterexample for control `control_f0901_shared_class_name` (F-0901), compiled only with it.
//!
//! The live check b-09-f0901-collision: two plan shapes with one $ZCRC (shapes 0 and 1 on hash 7 here). Shape 0 is
//! built and marked (class IVGC.P7); a reader of shape 0 runs it for its first anchor; a reader of shape 1 overwrites the
//! entry and its build recompiles IVGC.P7 from shape 1's lines; the first reader's second anchor runs the recompiled
//! class and answers shape 1's answer (not an L1 step: NAT-I3).
use vstd::prelude::*;
use actors::protocol::*;
use crate::planc_l1::*;
use crate::planc_l2::*;
use crate::planc_runs::*;

verus! {

pub open spec fn p1() -> PC2 { for2(q0(), 1, 0, 0, false) }
pub open spec fn p2() -> PC2 { compile2(p1(), 0) }
pub open spec fn p3() -> PC2 { mark2(p2(), 0) }
pub open spec fn p4() -> PC2 { for2(p3(), 2, 0, 1, false) }
pub open spec fn p5() -> PC2 { walk2(p4(), 2) }
pub open spec fn p6() -> PC2 { for2(p5(), 3, 1, 2, false) }
pub open spec fn p7() -> PC2 { compile2(p6(), 2) }
pub open spec fn p8() -> PC2 { walk2(p7(), 2) }

pub proof fn counterexample_f0901()
    ensures
        init2(q0()),
        step2(q0(), PCL2::For { r: 1, shape: 0, j: 0, restart: false }, p1()),
        step2(p1(), PCL2::BCompile { j: 0 }, p2()),
        step2(p2(), PCL2::BMark { j: 0 }, p3()),
        step2(p3(), PCL2::For { r: 2, shape: 0, j: 1, restart: false }, p4()),
        step2(p4(), PCL2::Walk { r: 2, shape: 0, a: interp(0, 0) }, p5()),
        step2(p5(), PCL2::For { r: 3, shape: 1, j: 2, restart: false }, p6()),
        step2(p6(), PCL2::BCompile { j: 2 }, p7()),
        step2(p7(), PCL2::Walk { r: 2, shape: 0, a: interp(1, 0) }, p8()),
        !step_or_stutter::<PcL1>(absp(p7()), labp(PCL2::Walk { r: 2, shape: 0, a: interp(1, 0) }), absp(p8())),
{
    lemma_p_steps(q0(), 1, 0, 0, false);
    assert(hof(q0(), 0) == 7);
    assert(p1().jobs.contains_key(0) && p1().jobs[0].h == 7 && p1().ent[7].shape == 0);
    lemma_p_steps(p1(), 1, 0, 0, false);
    assert(p2().cls[7] == 0 && p2().jobs[0].ph is Compiled);
    lemma_p_steps(p2(), 1, 0, 0, false);
    assert(marks(p2(), 0));
    assert(p3().ent[7] == (Ent { shape: 0, st: St::Ok, cls: Some(7) }));
    assert(!p3().jobs.contains_key(1) && !p3().rd.contains_key(2));
    lemma_p_steps(p3(), 2, 0, 1, false);
    assert(hit(p3(), 0));
    assert(p4().rd[2] == (Rd { s: 0, run: Some(7), left: 2 }));
    lemma_p_steps(p4(), 2, 0, 1, false);
    assert(answer(p4(), p4().rd[2]) == interp(0, 0));
    assert(p5().rd[2].left == 1);
    assert(!p5().jobs.contains_key(2) && !p5().rd.contains_key(3));
    lemma_p_steps(p5(), 3, 1, 2, false);
    assert(hof(p5(), 1) == 7 && !hit(p5(), 1));
    assert(p6().ent[7].shape == 1 && p6().src[7] == 1 && p6().jobs[2].dig == 1);
    assert(!p6().locks.contains(7));
    lemma_p_steps(p6(), 3, 1, 2, false);
    assert(p7().cls[7] == 1);
    assert(p7().rd[2] == (Rd { s: 0, run: Some(7), left: 1 }));
    lemma_p_steps(p7(), 2, 0, 2, false);
    assert(answer(p7(), p7().rd[2]) == interp(1, 0));
}

} // verus!
