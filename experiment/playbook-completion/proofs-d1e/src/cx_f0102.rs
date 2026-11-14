//! Proved counterexample for control `control_f0102_failure_only_logged` (F-0102), compiled only with it.
//!
//! Source (_engine/schema.py:2508-2511) and the explorer family breadth-a-mc-ins_setup-as-built: a base DDL
//! statement fails for a reason other than "exists" or a privilege and is logged only; every later step succeeds; the
//! reply has no warning while a step failed, which is not an L1 step (INS-B1.12).
use vstd::prelude::*;
use actors::protocol::*;
use crate::inst_l1::*;
use crate::inst_l2::*;
use crate::inst_runs::*;

verus! {

pub open spec fn c0() -> IS2 { i0(false, Set::empty(), Set::empty(), Set::empty()) }
pub open spec fn c1() -> IS2 { p_begin(c0(), 1) }
pub open spec fn c2() -> IS2 { p_ddl(c1(), false) }
pub open spec fn c3() -> IS2 { p_funcs(c2()) }
pub open spec fn c4() -> IS2 { p_deploy(c3(), true, true) }
pub open spec fn c5() -> IS2 { p_kg(c4()) }
pub open spec fn c6() -> IS2 { p_record(c5()) }
pub open spec fn c7() -> IS2 { p_end(c6()) }

pub proof fn counterexample_f0102()
    ensures
        init2(c0()),
        step2(c0(), IL2::Begin { schema: 1 }, c1()),
        step2(c1(), IL2::Ddl { ok: false }, c2()),
        step2(c2(), IL2::Funcs, c3()),
        step2(c3(), IL2::Deploy { on: true, ok: true }, c4()),
        step2(c4(), IL2::Kg { ok: true }, c5()),
        step2(c5(), IL2::Record, c6()),
        c6().run->Some_0.failed,
        step2(c6(), IL2::Reply { warned: false, ready: true }, c7()),
        !step_or_stutter::<InstL1>(absi(c6()), labi(IL2::Reply { warned: false, ready: true }), absi(c7())),
{
    lemma_i_steps(c0(), 1, true, true, 0);
    lemma_i_steps(c1(), 1, false, true, 0);
    lemma_i_steps(c2(), 1, true, true, 0);
    lemma_i_steps(c3(), 1, true, true, 0);
    lemma_i_steps(c4(), 1, true, true, 0);
    lemma_i_steps(c5(), 1, true, true, 0);
    lemma_i_steps(c6(), 1, true, true, 0);
}

} // verus!
