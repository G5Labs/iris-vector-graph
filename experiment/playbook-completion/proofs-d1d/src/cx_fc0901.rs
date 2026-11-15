//! Proved counterexample for control `control_fc0901_mark_any_entry` (F-C0901), compiled only with it.
//!
//! The live check b-09-f0901-collision: a read of shape B (its build job compiling) then a read of shape A (one hash)
//! left one entry, status ok, and every later read of A answered B's answer, in every process. Here (shapes 1 = B and
//! 0 = A on hash 7, fresh class names): B's build compiles class 0; A's read rewrites the entry for A; B's build marks
//! the entry ok with class 0 (A's entry now names B's class); A's own job finds no pending entry and leaves; the next
//! read of A runs class 0 and answers B's answer (not an L1 step).
use vstd::prelude::*;
use actors::protocol::*;
use crate::planc_l1::*;
use crate::planc_l2::*;
use crate::planc_runs::*;

verus! {

pub open spec fn p1() -> PC2 { for2(q0(), 1, 1, 0, false) }
pub open spec fn p2() -> PC2 { compile2(p1(), 0) }
pub open spec fn p3() -> PC2 { for2(p2(), 2, 0, 1, false) }
pub open spec fn p4() -> PC2 { mark2(p3(), 0) }
pub open spec fn p5() -> PC2 { PC2 { jobs: p4().jobs.remove(1), ..p4() } }
pub open spec fn p6() -> PC2 { for2(p5(), 3, 0, 2, false) }
pub open spec fn p7() -> PC2 { walk2(p6(), 3) }

pub proof fn counterexample_fc0901()
    ensures
        init2(q0()),
        step2(q0(), PCL2::For { r: 1, shape: 1, j: 0, restart: false }, p1()),
        step2(p1(), PCL2::BCompile { j: 0 }, p2()),
        step2(p2(), PCL2::For { r: 2, shape: 0, j: 1, restart: false }, p3()),
        step2(p3(), PCL2::BMark { j: 0 }, p4()),
        p4().ent[7].shape == 0 && p4().ent[7].st is Ok && p4().ent[7].cls == Some(0int) && p4().cls[0] == 1,
        step2(p4(), PCL2::BLeave { j: 1 }, p5()),
        step2(p5(), PCL2::For { r: 3, shape: 0, j: 2, restart: false }, p6()),
        step2(p6(), PCL2::Walk { r: 3, shape: 0, a: interp(1, 0) }, p7()),
        !step_or_stutter::<PcL1>(absp(p6()), labp(PCL2::Walk { r: 3, shape: 0, a: interp(1, 0) }), absp(p7())),
{
    lemma_p_steps(q0(), 1, 1, 0, false);
    assert(hof(q0(), 1) == 7);
    assert(p1().jobs[0].h == 7 && p1().ent[7].shape == 1 && p1().src[7] == 1);
    lemma_p_steps(p1(), 1, 1, 0, false);
    assert(p2().cls[0] == 1 && p2().jobs[0].ph == (Ph::Compiled { c: 0, from: 1 }));
    assert(!p2().rd.contains_key(2) && !p2().jobs.contains_key(1));
    lemma_p_steps(p2(), 2, 0, 1, false);
    assert(hof(p2(), 0) == 7 && !hit(p2(), 0));
    assert(p3().ent[7].shape == 0 && p3().jobs[0].ph is Compiled);
    lemma_p_steps(p3(), 2, 0, 0, false);
    assert(marks(p3(), 0));
    assert(p4().ent[7] == (Ent { shape: 0, st: St::Ok, cls: Some(0) }));
    assert(p4().jobs.contains_key(1) && p4().jobs[1].ph is Started && !can_build(p4(), 1));
    lemma_p_steps(p4(), 2, 0, 1, false);
    assert(!p5().rd.contains_key(3) && !p5().jobs.contains_key(2));
    lemma_p_steps(p5(), 3, 0, 2, false);
    assert(hit(p5(), 0));
    assert(p6().rd[3] == (Rd { s: 0, run: Some(0), left: 2 }));
    lemma_p_steps(p6(), 3, 0, 2, false);
    assert(answer(p6(), p6().rd[3]) == interp(1, 0));
}

} // verus!
