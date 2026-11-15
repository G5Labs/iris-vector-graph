//! Counterexamples: for each departing design and each axiom it breaks, a run of the composed machine with that
//! design's parameters, from the initial state, to a violation (the explorer's counterexample, restated). Each is
//! stated on the generic machine (`run::<SysM<Design>>`, `sys_step::<Design>`) and proved by evaluating the run for the
//! design's parameters (`lemma_run_cfg`, then `compute` on `run_cfg`).
use vstd::prelude::*;
use ivg_proofs_mech::exec::*;
use crate::sys::*;
use crate::base::*;
use crate::inst::*;
use crate::progress::*;

verus! {

pub proof fn cx_sysasbuilt_ax06()
    ensures ({
        let r = run::<SysM<SysAsBuilt>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0)]);
        r is Some && !law_ax06(r->0)
    })
{
    lemma_run_cfg::<SysAsBuilt>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::AsBuilt, m03_erase_locked: false, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0)]);
        r is Some && !law_ax06(r->0)
    }) by (compute);
}

pub proof fn cx_sysasbuilt_ax07()
    ensures ({
        let r = run::<SysM<SysAsBuilt>>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax07(r->0)
    })
{
    lemma_run_cfg::<SysAsBuilt>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::AsBuilt, m03_erase_locked: false, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && (r->0).content[0] && no_live((r->0).recs[0])
    }) by (compute);
    let t = run::<SysM<SysAsBuilt>>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3), SA::Run(3)])->0;
    lemma_no_live(t.recs[0]);
}

pub proof fn cx_sysasbuilt_ax08()
    ensures ({
        let r = run::<SysM<SysAsBuilt>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2)]);
        r is Some && !law_ax08(r->0)
    })
{
    lemma_run_cfg::<SysAsBuilt>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::AsBuilt, m03_erase_locked: false, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2)]);
        r is Some && !law_ax08(r->0)
    }) by (compute);
}

pub proof fn cx_sysasbuilt_ax10()
    ensures ({
        let r = run::<SysM<SysAsBuilt>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(0)]);
        r is Some && !law_ax10(r->0)
    })
{
    lemma_run_cfg::<SysAsBuilt>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::AsBuilt, m03_erase_locked: false, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(0)]);
        r is Some && !law_ax10(r->0)
    }) by (compute);
}

pub proof fn cx_sysasbuilt_ax11()
    ensures ({
        let r = run::<SysM<SysAsBuilt>>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
        r is Some && sys_step::<SysAsBuilt>(r->0, SA::Run(3)) is Some && !law_ax11::<SysAsBuilt>(r->0, 3)
    })
{
    lemma_run_cfg::<SysAsBuilt>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::AsBuilt, m03_erase_locked: false, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
        r is Some && step_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::AsBuilt, m03_erase_locked: false, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, r->0, SA::Run(3)) is Some && !law_ax11_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::AsBuilt, m03_erase_locked: false, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, r->0, 3)
    }) by (compute);
}

pub proof fn cx_sysasbuilt_ax11m()
    ensures ({
        let r = run::<SysM<SysAsBuilt>>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax11m(r->0)
    })
{
    lemma_run_cfg::<SysAsBuilt>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::AsBuilt, m03_erase_locked: false, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax11m(r->0)
    }) by (compute);
}

pub proof fn cx_ctltombbothtenants_ax02()
    ensures ({
        let r = run::<SysM<CtlTombBothTenants>>(sys_s0(), seq![SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && sys_step::<CtlTombBothTenants>(r->0, SA::Run(3)) is Some && !law_ax02(r->0, SA::Run(3), sys_step::<CtlTombBothTenants>(r->0, SA::Run(3))->0)
    })
{
    lemma_run_cfg::<CtlTombBothTenants>(sys_s0(), seq![SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Any, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && step_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Any, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, r->0, SA::Run(3)) is Some && !law_ax02(r->0, SA::Run(3), step_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Any, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, r->0, SA::Run(3))->0)
    }) by (compute);
}

pub proof fn cx_ctltombbothtenants_ax07()
    ensures ({
        let r = run::<SysM<CtlTombBothTenants>>(sys_s0(), seq![SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax07(r->0)
    })
{
    lemma_run_cfg::<CtlTombBothTenants>(sys_s0(), seq![SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Any, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && (r->0).content[1] && no_live((r->0).recs[1])
    }) by (compute);
    let t = run::<SysM<CtlTombBothTenants>>(sys_s0(), seq![SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)])->0;
    lemma_no_live(t.recs[1]);
}

pub proof fn cx_ctlrefusalwrites_ax03()
    ensures ({
        let r = run::<SysM<CtlRefusalWrites>>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0)]);
        r is Some && sys_step::<CtlRefusalWrites>(r->0, SA::Run(0)) is Some && !law_ax03(r->0, SA::Run(0), sys_step::<CtlRefusalWrites>(r->0, SA::Run(0))->0)
    })
{
    lemma_run_cfg::<CtlRefusalWrites>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Writes, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0)]);
        r is Some && step_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Writes, m10_erase_split: false }, r->0, SA::Run(0)) is Some && !law_ax03(r->0, SA::Run(0), step_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Writes, m10_erase_split: false }, r->0, SA::Run(0))->0)
    }) by (compute);
}

pub proof fn cx_ctlrefusalwrites_ax07()
    ensures ({
        let r = run::<SysM<CtlRefusalWrites>>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
        r is Some && !law_ax07(r->0)
    })
{
    lemma_run_cfg::<CtlRefusalWrites>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Writes, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
        r is Some && (r->0).content[0] && no_live((r->0).recs[0])
    }) by (compute);
    let t = run::<SysM<CtlRefusalWrites>>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)])->0;
    lemma_no_live(t.recs[0]);
}

pub proof fn cx_ctlrefusalwrites_ax08()
    ensures ({
        let r = run::<SysM<CtlRefusalWrites>>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
        r is Some && !law_ax08(r->0)
    })
{
    lemma_run_cfg::<CtlRefusalWrites>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Writes, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
        r is Some && !law_ax08(r->0)
    }) by (compute);
}

pub proof fn cx_ctlrefusalwrites_ax11m()
    ensures ({
        let r = run::<SysM<CtlRefusalWrites>>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
        r is Some && !law_ax11m(r->0)
    })
{
    lemma_run_cfg::<CtlRefusalWrites>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Writes, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
        r is Some && !law_ax11m(r->0)
    }) by (compute);
}

pub proof fn cx_ctlerasesplit_ax04()
    ensures ({
        let r = run::<SysM<CtlEraseSplit>>(sys_s0(), seq![SA::Run(2), SA::Run(2), SA::StopE]);
        r is Some && !law_ax04(r->0)
    })
{
    lemma_run_cfg::<CtlEraseSplit>(sys_s0(), seq![SA::Run(2), SA::Run(2), SA::StopE]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: true }, sys_s0(), seq![SA::Run(2), SA::Run(2), SA::StopE]);
        r is Some && !law_ax04(r->0)
    }) by (compute);
}

pub proof fn cx_ctldeleterecords_ax05()
    ensures ({
        let r = run::<SysM<CtlDeleteRecords>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && sys_step::<CtlDeleteRecords>(r->0, SA::Run(3)) is Some && !law_ax05(r->0, sys_step::<CtlDeleteRecords>(r->0, SA::Run(3))->0)
    })
{
    lemma_run_cfg::<CtlDeleteRecords>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Delete, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && step_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Delete, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, r->0, SA::Run(3)) is Some && (step_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Delete, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, r->0, SA::Run(3))->0).recs[0].len() < (r->0).recs[0].len()
    }) by (compute);
}

pub proof fn cx_ctlpostonreplay_ax06()
    ensures ({
        let r = run::<SysM<CtlPostOnReplay>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0)]);
        r is Some && !law_ax06(r->0)
    })
{
    lemma_run_cfg::<CtlPostOnReplay>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0)]);
        r is Some && !law_ax06(r->0)
    }) by (compute);
}

pub proof fn cx_ctlpostonreplay_ax10()
    ensures ({
        let r = run::<SysM<CtlPostOnReplay>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(0)]);
        r is Some && !law_ax10(r->0)
    })
{
    lemma_run_cfg::<CtlPostOnReplay>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(0)]);
        r is Some && !law_ax10(r->0)
    }) by (compute);
}

pub proof fn cx_ctlpostonreplay_ax11m()
    ensures ({
        let r = run::<SysM<CtlPostOnReplay>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0)]);
        r is Some && !law_ax11m(r->0)
    })
{
    lemma_run_cfg::<CtlPostOnReplay>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0)]);
        r is Some && !law_ax11m(r->0)
    }) by (compute);
}

pub proof fn cx_ctlunrecordedapply_ax07()
    ensures ({
        let r = run::<SysM<CtlUnrecordedApply>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0)]);
        r is Some && !law_ax07(r->0)
    })
{
    lemma_run_cfg::<CtlUnrecordedApply>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: false, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0)]);
        r is Some && (r->0).content[0] && no_live((r->0).recs[0])
    }) by (compute);
    let t = run::<SysM<CtlUnrecordedApply>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0)])->0;
    lemma_no_live(t.recs[0]);
}

pub proof fn cx_ctleraseskipsderived_ax08()
    ensures ({
        let r = run::<SysM<CtlEraseSkipsDerived>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2)]);
        r is Some && !law_ax08(r->0)
    })
{
    lemma_run_cfg::<CtlEraseSkipsDerived>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2)]);
        r is Some && !law_ax08(r->0)
    }) by (compute);
}

pub proof fn cx_ctleraseskipsderived_ax10()
    ensures ({
        let r = run::<SysM<CtlEraseSkipsDerived>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax10(r->0)
    })
{
    lemma_run_cfg::<CtlEraseSkipsDerived>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax10(r->0)
    }) by (compute);
}

pub proof fn cx_ctlbindingkept_ax10()
    ensures ({
        let r = run::<SysM<CtlBindingKept>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax10(r->0)
    })
{
    lemma_run_cfg::<CtlBindingKept>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: false, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax10(r->0)
    }) by (compute);
}

pub proof fn cx_ctlcheckbeforelock_ax07()
    ensures ({
        let r = run::<SysM<CtlCheckBeforeLock>>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax07(r->0)
    })
{
    lemma_run_cfg::<CtlCheckBeforeLock>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::CheckBeforeLock, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && (r->0).content[0] && no_live((r->0).recs[0])
    }) by (compute);
    let t = run::<SysM<CtlCheckBeforeLock>>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3), SA::Run(3)])->0;
    lemma_no_live(t.recs[0]);
}

pub proof fn cx_ctlcheckbeforelock_ax11()
    ensures ({
        let r = run::<SysM<CtlCheckBeforeLock>>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
        r is Some && sys_step::<CtlCheckBeforeLock>(r->0, SA::Run(3)) is Some && !law_ax11::<CtlCheckBeforeLock>(r->0, 3)
    })
{
    lemma_run_cfg::<CtlCheckBeforeLock>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::CheckBeforeLock, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
        r is Some && step_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::CheckBeforeLock, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, r->0, SA::Run(3)) is Some && !law_ax11_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::CheckBeforeLock, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, r->0, 3)
    }) by (compute);
}

pub proof fn cx_ctlcheckbeforelock_ax11m()
    ensures ({
        let r = run::<SysM<CtlCheckBeforeLock>>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax11m(r->0)
    })
{
    lemma_run_cfg::<CtlCheckBeforeLock>(sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::CheckBeforeLock, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax11m(r->0)
    }) by (compute);
}

pub proof fn cx_ctlreceiptearly_ax10()
    ensures ({
        let r = run::<SysM<CtlReceiptEarly>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax10(r->0)
    })
{
    lemma_run_cfg::<CtlReceiptEarly>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Early, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax10(r->0)
    }) by (compute);
}

pub proof fn cx_ctlreceiptearly_ax12()
    ensures ({
        let r = run::<SysM<CtlReceiptEarly>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && sys_step::<CtlReceiptEarly>(r->0, SA::Run(3)) is Some && !law_ax12::<CtlReceiptEarly>(r->0, 3)
    })
{
    lemma_run_cfg::<CtlReceiptEarly>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Early, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && step_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Early, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, r->0, SA::Run(3)) is Some && cur_step_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Early, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, r->0, 3) == Some(Step::Receipt) && (r->0).recs[0].len() > 0 && (r->0).recs[0][0]
    }) by (compute);
}

/// The redaction runs to Done; the marker it set is never cleared, so from there no run is final (AG EF fails).
pub proof fn cx_ctlmarkernevercleared_ax14()
    ensures ({
        let r = run::<SysM<CtlMarkerNeverCleared>>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && !law_ax14::<CtlMarkerNeverCleared>(r->0)
    })
{
    lemma_run_cfg::<CtlMarkerNeverCleared>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::NeverCleared, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && (r->0).pc[3] is Done
    }) by (compute);
    let t = run::<SysM<CtlMarkerNeverCleared>>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)])->0;
    theorem_base::<CtlMarkerNeverCleared>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)], t);
    lemma_never_cleared(t);
}

/// No live record (quantifier-free, so `compute` decides it on a concrete list).
pub open spec fn no_live(r: Seq<bool>) -> bool
    decreases r.len(),
{
    if r.len() == 0 { true } else { !r.last() && no_live(r.drop_last()) }
}

pub proof fn lemma_no_live(r: Seq<bool>)
    requires no_live(r),
    ensures !has_live_record(r),
    decreases r.len(),
{
    if r.len() > 0 {
        lemma_no_live(r.drop_last());
        assert forall|k: int| 0 <= k < r.len() implies !r[k] by {
            if k < r.len() - 1 { assert(r.drop_last()[k] == r[k]); }
        }
    }
}

/// With the marker never cleared, a redaction that is Done keeps the marker forever: no run from such a state reaches
/// a final state (AG EF fails).
pub proof fn lemma_never_cleared(t: SS)
    requires inv_base::<CtlMarkerNeverCleared>(t), t.pc[3] is Done,
    ensures !law_ax14::<CtlMarkerNeverCleared>(t),
{
    let inv = |x: SS| inv_base::<CtlMarkerNeverCleared>(x) && x.pc[3] is Done;
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SysM::<CtlMarkerNeverCleared>::step(x, a)) is Some
        implies inv(SysM::<CtlMarkerNeverCleared>::step(x, a)->0) by {
        lemma_base_step::<CtlMarkerNeverCleared>(x, a);
        if let SA::Run(i) = a {
            let c = CtlMarkerNeverCleared::cfg();
            lemma_after(c, x, i, pc_k(x.pc[i as int]), step_at(c, i, pc_k(x.pc[i as int])));
        }
    }
    assert forall|ls: Seq<SA>| #[trigger] run::<SysM<CtlMarkerNeverCleared>>(t, ls) is Some
        implies !final_state(run::<SysM<CtlMarkerNeverCleared>>(t, ls)->0) by {
        lemma_run_inv::<SysM<CtlMarkerNeverCleared>>(inv, t, ls);
    }
}

} // verus!
