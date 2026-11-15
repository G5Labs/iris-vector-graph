//! Non-vacuity of the reviewed planc model (compiled without its controls), on the F-C0901 schedule: shapes 1 and 0
//! collide on hash 7; shape 1's build compiles class 0 while shape 0's read rewrites the entry; the build does not mark
//! it (another shape's entry); shape 0's build compiles class 1 and marks the entry; a read of shape 0 runs class 1 and
//! answers its own answer.
use vstd::prelude::*;
use crate::planc_l1::*;
use crate::planc_l2::*;
use crate::planc_runs::*;

verus! {

pub open spec fn p1() -> PC2 { for2(q0(), 1, 1, 0, false) }
pub open spec fn p2() -> PC2 { compile2(p1(), 0) }
pub open spec fn p3() -> PC2 { for2(p2(), 2, 0, 1, false) }
pub open spec fn p4() -> PC2 { mark2(p3(), 0) }
pub open spec fn p5() -> PC2 { compile2(p4(), 1) }
pub open spec fn p6() -> PC2 { mark2(p5(), 1) }
pub open spec fn p7() -> PC2 { for2(p6(), 3, 0, 2, false) }
pub open spec fn p8() -> PC2 { walk2(p7(), 3) }

pub proof fn witness_planc()
    ensures
        init2(q0()),
        step2(q0(), PCL2::For { r: 1, shape: 1, j: 0, restart: false }, p1()),
        step2(p1(), PCL2::BCompile { j: 0 }, p2()),
        step2(p2(), PCL2::For { r: 2, shape: 0, j: 1, restart: false }, p3()),
        step2(p3(), PCL2::BMark { j: 0 }, p4()),
        p4().ent[7].st is Pending,
        step2(p4(), PCL2::BCompile { j: 1 }, p5()),
        step2(p5(), PCL2::BMark { j: 1 }, p6()),
        p6().ent[7] == (Ent { shape: 0, st: St::Ok, cls: Some(1) }),
        step2(p6(), PCL2::For { r: 3, shape: 0, j: 2, restart: false }, p7()),
        p7().rd[3].run == Some(1int),
        step2(p7(), PCL2::Walk { r: 3, shape: 0, a: interp(0, 0) }, p8()),
{
    lemma_p_steps(q0(), 1, 1, 0, false);
    assert(hof(q0(), 1) == 7);
    assert(p1().jobs[0].h == 7 && p1().ent[7].shape == 1 && p1().src[7] == 1);
    lemma_p_steps(p1(), 1, 1, 0, false);
    assert(p2().jobs[0].ph == (Ph::Compiled { c: 0, from: 1 }));
    assert(!p2().rd.contains_key(2) && !p2().jobs.contains_key(1));
    lemma_p_steps(p2(), 2, 0, 1, false);
    assert(hof(p2(), 0) == 7 && !hit(p2(), 0));
    assert(p3().ent[7].shape == 0 && p3().jobs[0].ph is Compiled);
    lemma_p_steps(p3(), 2, 0, 0, false);
    assert(!marks(p3(), 0));
    assert(p4().ent[7].st is Pending && !p4().locks.contains(7));
    assert(p4().jobs[1] == (Job { h: 7, dig: 0, ph: Ph::Started }) && p4().src[7] == 0);
    lemma_p_steps(p4(), 2, 0, 1, false);
    assert(p5().cls[1] == 0 && p5().jobs[1].ph == (Ph::Compiled { c: 1, from: 0 }));
    lemma_p_steps(p5(), 2, 0, 1, false);
    assert(marks(p5(), 1));
    assert(!p6().rd.contains_key(3) && !p6().jobs.contains_key(2));
    lemma_p_steps(p6(), 3, 0, 2, false);
    assert(hit(p6(), 0));
    lemma_p_steps(p7(), 3, 0, 2, false);
    assert(answer(p7(), p7().rd[3]) == interp(0, 0));
}

} // verus!
