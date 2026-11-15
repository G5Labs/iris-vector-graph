//! Non-vacuity of the reviewed module 01 model (compiled without its controls): a setup whose class deploy fails
//! binds the namespace, says so, admits an engine of its schema whose feature call is a named failure, and refuses
//! another schema's engine and setup (HD-0102, FR-006); a setup that stopped after its marker admits no engine
//! (F-0103 remedy); a failed DDL statement is in the warnings (F-0102 remedy); the upgrade migrates the bound
//! schema's tables and refuses another schema; legacy removal reports a failed drop as not removed (F-0101 remedy).
use vstd::prelude::*;
use crate::inst_l1::*;
use crate::inst_l2::*;
use crate::inst_runs::*;

verus! {

pub open spec fn w0() -> IS2 { i0(false, Set::empty().insert(0int), Set::empty().insert(5int), Set::empty().insert(7int)) }
pub open spec fn w1() -> IS2 { p_begin(w0(), 1) }
pub open spec fn w2() -> IS2 { p_ddl(w1(), true) }
pub open spec fn w3() -> IS2 { p_funcs(w2()) }
pub open spec fn w4() -> IS2 { p_deploy(w3(), true, false) }
pub open spec fn w5() -> IS2 { p_kg(w4()) }
pub open spec fn w6() -> IS2 { p_record(w5()) }
pub open spec fn w7() -> IS2 { p_end(w6()) }
pub open spec fn h4() -> IS2 { p_end(w3()) }
pub open spec fn f2() -> IS2 { p_ddl(w1(), false) }
pub open spec fn r1() -> IS2 { p_rmview(w0(), 5, false) }
pub open spec fn r2() -> IS2 { p_rmfirst(r1(), 7, true) }

pub proof fn witness_inst()
    ensures
        init2(w0()),
        step2(w0(), IL2::Begin { schema: 1 }, w1()),
        step2(w1(), IL2::Ddl { ok: true }, w2()),
        step2(w2(), IL2::Funcs, w3()),
        step2(w3(), IL2::Deploy { on: true, ok: false }, w4()),
        step2(w4(), IL2::Kg { ok: true }, w5()),
        step2(w5(), IL2::Record, w6()),
        step2(w6(), IL2::Reply { warned: true, ready: false }, w7()),
        w7().rec == Some(1int) && !w7().cls,
        step2(w7(), IL2::Access { schema: 1, adm: Adm::Accepted }, w7()),
        step2(w7(), IL2::Feature { rdy: Ready::NotDeployed }, w7()),
        step2(w7(), IL2::Access { schema: 2, adm: Adm::Refused }, w7()),
        step2(w7(), IL2::Refuse { schema: 2 }, w7()),
        step2(w7(), IL2::Upgrade { arg: 0 }, w7()),
        step2(w3(), IL2::Stop, h4()),
        h4().funcs.contains(1) && h4().rec is None,
        step2(h4(), IL2::Access { schema: 1, adm: Adm::Refused }, h4()),
        step2(w1(), IL2::Ddl { ok: false }, f2()),
        f2().run->Some_0.failed && f2().run->Some_0.warnings,
        step2(w0(), IL2::RmView { v: 5, ok: false, reported: false }, r1()),
        r1().views.contains(5),
        step2(r1(), IL2::RmFirst { c: 7, ok: true, reported: true }, r2()),
        step2(r2(), IL2::RmLater { c: 7, reported: true }, r2()),
        !r2().lcls.contains(7),
{
    lemma_i_steps(w0(), 1, true, true, 5);
    lemma_i_steps(w1(), 1, true, true, 0);
    lemma_i_steps(w1(), 1, false, true, 0);
    lemma_i_steps(w2(), 1, true, true, 0);
    lemma_i_steps(w3(), 1, false, true, 0);
    lemma_i_steps(w4(), 1, true, true, 0);
    lemma_i_steps(w5(), 1, true, true, 0);
    lemma_i_steps(w6(), 1, true, true, 0);
    lemma_i_steps(w7(), 1, true, true, 0);
    lemma_i_steps(w7(), 2, true, true, 0);
    assert(p_upgrade(w7(), 0) == w7());
    lemma_i_steps(h4(), 1, true, true, 0);
    lemma_i_steps(w0(), 1, false, true, 5);
    lemma_i_steps(r1(), 1, true, true, 7);
    lemma_i_steps(r2(), 1, true, true, 7);
}

} // verus!
