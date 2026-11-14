//! Proved counterexample for control `control_f0109_upgrade_default_schema` (F-0109), compiled only with it.
//!
//! Source (migrations/upgrade.py:58, :140; ^IVG.Deploy("schema") is never read): a namespace holds another schema's
//! (Graph_KG = 0) tables in the 3.2.0 shape; setup of schema 1 binds it to 1 and leaves schema 0's tables untouched
//! (as built, _engine/schema.py:2314-2318); upgrade_to_4_0_0 with its default schema then migrates schema 0's tables,
//! which is not an L1 step (the upgrade touches the bound schema only).
use vstd::prelude::*;
use actors::protocol::*;
use crate::inst_l1::*;
use crate::inst_l2::*;
use crate::inst_runs::*;

verus! {

pub open spec fn c0() -> IS2 { i0(false, Set::empty().insert(0int), Set::empty(), Set::empty()) }
pub open spec fn c1() -> IS2 { p_begin(c0(), 1) }
pub open spec fn c2() -> IS2 { p_ddl(c1(), true) }
pub open spec fn c3() -> IS2 { p_funcs(c2()) }
pub open spec fn c4() -> IS2 { p_deploy(c3(), true, true) }
pub open spec fn c5() -> IS2 { p_kg(c4()) }
pub open spec fn c6() -> IS2 { p_record(c5()) }
pub open spec fn c7() -> IS2 { p_end(c6()) }
pub open spec fn c8() -> IS2 { p_upgrade(c7(), 0) }

pub proof fn counterexample_f0109()
    ensures
        init2(c0()),
        step2(c0(), IL2::Begin { schema: 1 }, c1()),
        step2(c1(), IL2::Ddl { ok: true }, c2()),
        step2(c2(), IL2::Funcs, c3()),
        step2(c3(), IL2::Deploy { on: true, ok: true }, c4()),
        step2(c4(), IL2::Kg { ok: true }, c5()),
        step2(c5(), IL2::Record, c6()),
        step2(c6(), IL2::Reply { warned: false, ready: true }, c7()),
        c7().rec == Some(1int),
        step2(c7(), IL2::Upgrade { arg: 0 }, c8()),
        c8().shaped.contains(0) && !c7().shaped.contains(0),
        !step_or_stutter::<InstL1>(absi(c7()), labi(IL2::Upgrade { arg: 0 }), absi(c8())),
{
    lemma_i_steps(c0(), 1, true, true, 0);
    lemma_i_steps(c1(), 1, true, true, 0);
    lemma_i_steps(c2(), 1, true, true, 0);
    lemma_i_steps(c3(), 1, true, true, 0);
    lemma_i_steps(c4(), 1, true, true, 0);
    lemma_i_steps(c5(), 1, true, true, 0);
    lemma_i_steps(c6(), 1, true, true, 0);
    lemma_i_steps(c7(), 1, true, true, 0);
    assert(c7().shaped =~= Set::empty().insert(1int));
    assert(c8().shaped.contains(0));
    assert(up1(absi(c7())) =~= Set::empty().insert(1int));
    assert(!up1(absi(c7())).contains(0));
}

} // verus!
