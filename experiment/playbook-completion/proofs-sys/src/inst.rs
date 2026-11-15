//! The explorer's 13 designs of module 00 as instances of the design trait: one choice vector of the composed
//! mechanisms' instances each (the reviewed composition, the pin's as-built composition, one mutant per axiom).
//! The reviewed design discharges every obligation (its `SysObject` impl), so every axiom theorem applies to it; the
//! departing designs have their parameters only here: kept obligations proved (`keep_*`), broken ones refuted
//! (`refute_*`); their `SysObject` impl exists only under their control feature (src/ctl.rs).
use vstd::prelude::*;
use ivg_proofs_mech::exec::*;
use crate::sys::*;
use crate::theorem::*;

verus! {

pub open spec fn reviewed_cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false } }

/// The reviewed composition: the property written in the commit (residual question 6's alternative); the eraser under
/// the head lock maintaining the derived store; check, marker and tombstones in one locked section, the binding moved,
/// Final clears its own marker and writes the receipt.
pub struct SysReviewed;
impl SysDesign for SysReviewed { open spec fn cfg() -> SysCfg { reviewed_cfg() } }
impl SysObject for SysReviewed {
    proof fn discharge_ax02() {}
    proof fn discharge_ax03() {}
    proof fn discharge_ax04() {}
    proof fn discharge_ax05() {}
    proof fn discharge_ax06() {}
    proof fn discharge_ax07() {}
    proof fn discharge_ax08() {}
    proof fn discharge_ax10() {}
    proof fn discharge_ax11() {}
    proof fn discharge_ax11m() {}
    proof fn discharge_ax12() {}
    proof fn discharge_ax14() {}
}
/// The generic theorem, instantiated: the whole proof work of the reviewed composition.
pub proof fn laws_sys_reviewed(s0: SS, ls: Seq<SA>, t: SS) requires reached::<SysM<SysReviewed>>(s0, ls, t)
    ensures all_invariant_axioms(t), law_ax14::<SysReviewed>(t) { theorem_sys::<SysReviewed>(s0, ls, t); }

/// sys00_as_built (as-built): the pin's composition: post-commit properties by a separate step that also runs on a replay (client.py:418-487), the unlocked liveness check and global marker clear (LedgerRedact.cls:185-430), the eraser without the head lock that does not maintain the derived store (Eraser.cls:665-678; F-0702, F-0606 family).
pub struct SysAsBuilt;
impl SysDesign for SysAsBuilt { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::AsBuilt, m03_erase_locked: false, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false } } }
pub proof fn keep_sysasbuilt_ax02() ensures obl_ax02::<SysAsBuilt>() {}
pub proof fn keep_sysasbuilt_ax03() ensures obl_ax03::<SysAsBuilt>() {}
pub proof fn keep_sysasbuilt_ax04() ensures obl_ax04::<SysAsBuilt>() {}
pub proof fn keep_sysasbuilt_ax05() ensures obl_ax05::<SysAsBuilt>() {}
pub proof fn refute_sysasbuilt_ax06() ensures !obl_ax06::<SysAsBuilt>() {}
pub proof fn refute_sysasbuilt_ax07() ensures !obl_ax07::<SysAsBuilt>() {}
pub proof fn refute_sysasbuilt_ax08() ensures !obl_ax08::<SysAsBuilt>() {}
pub proof fn refute_sysasbuilt_ax10() ensures !obl_ax10::<SysAsBuilt>() {}
pub proof fn refute_sysasbuilt_ax11() ensures !obl_ax11::<SysAsBuilt>() {}
pub proof fn refute_sysasbuilt_ax11m() ensures !obl_ax11m::<SysAsBuilt>() {}
pub proof fn keep_sysasbuilt_ax12() ensures obl_ax12::<SysAsBuilt>() {}
pub proof fn keep_sysasbuilt_ax14() ensures obl_ax14::<SysAsBuilt>() {}

/// sys00_control_ax02_tomb_both_tenants (mutant): the redaction tombstones every tenant's records.
pub struct CtlTombBothTenants;
impl SysDesign for CtlTombBothTenants { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Any, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false } } }
pub proof fn refute_ctltombbothtenants_ax02() ensures !obl_ax02::<CtlTombBothTenants>() {}
pub proof fn keep_ctltombbothtenants_ax03() ensures obl_ax03::<CtlTombBothTenants>() {}
pub proof fn keep_ctltombbothtenants_ax04() ensures obl_ax04::<CtlTombBothTenants>() {}
pub proof fn keep_ctltombbothtenants_ax05() ensures obl_ax05::<CtlTombBothTenants>() {}
pub proof fn keep_ctltombbothtenants_ax06() ensures obl_ax06::<CtlTombBothTenants>() {}
pub proof fn refute_ctltombbothtenants_ax07() ensures !obl_ax07::<CtlTombBothTenants>() {}
pub proof fn keep_ctltombbothtenants_ax08() ensures obl_ax08::<CtlTombBothTenants>() {}
pub proof fn keep_ctltombbothtenants_ax10() ensures obl_ax10::<CtlTombBothTenants>() {}
pub proof fn keep_ctltombbothtenants_ax11() ensures obl_ax11::<CtlTombBothTenants>() {}
pub proof fn keep_ctltombbothtenants_ax11m() ensures obl_ax11m::<CtlTombBothTenants>() {}
pub proof fn keep_ctltombbothtenants_ax12() ensures obl_ax12::<CtlTombBothTenants>() {}
pub proof fn keep_ctltombbothtenants_ax14() ensures obl_ax14::<CtlTombBothTenants>() {}

/// sys00_control_ax03_refusal_writes (mutant): the writer's refused marker check writes content.
pub struct CtlRefusalWrites;
impl SysDesign for CtlRefusalWrites { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Writes, m10_erase_split: false } } }
pub proof fn keep_ctlrefusalwrites_ax02() ensures obl_ax02::<CtlRefusalWrites>() {}
pub proof fn refute_ctlrefusalwrites_ax03() ensures !obl_ax03::<CtlRefusalWrites>() {}
pub proof fn keep_ctlrefusalwrites_ax04() ensures obl_ax04::<CtlRefusalWrites>() {}
pub proof fn keep_ctlrefusalwrites_ax05() ensures obl_ax05::<CtlRefusalWrites>() {}
pub proof fn keep_ctlrefusalwrites_ax06() ensures obl_ax06::<CtlRefusalWrites>() {}
pub proof fn refute_ctlrefusalwrites_ax07() ensures !obl_ax07::<CtlRefusalWrites>() {}
pub proof fn refute_ctlrefusalwrites_ax08() ensures !obl_ax08::<CtlRefusalWrites>() {}
pub proof fn keep_ctlrefusalwrites_ax10() ensures obl_ax10::<CtlRefusalWrites>() {}
pub proof fn keep_ctlrefusalwrites_ax11() ensures obl_ax11::<CtlRefusalWrites>() {}
pub proof fn refute_ctlrefusalwrites_ax11m() ensures !obl_ax11m::<CtlRefusalWrites>() {}
pub proof fn keep_ctlrefusalwrites_ax12() ensures obl_ax12::<CtlRefusalWrites>() {}
pub proof fn keep_ctlrefusalwrites_ax14() ensures obl_ax14::<CtlRefusalWrites>() {}

/// sys00_control_ax04_erase_split (mutant): the erasure is two steps and may be stopped between them.
pub struct CtlEraseSplit;
impl SysDesign for CtlEraseSplit { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: true } } }
pub proof fn keep_ctlerasesplit_ax02() ensures obl_ax02::<CtlEraseSplit>() {}
pub proof fn keep_ctlerasesplit_ax03() ensures obl_ax03::<CtlEraseSplit>() {}
pub proof fn refute_ctlerasesplit_ax04() ensures !obl_ax04::<CtlEraseSplit>() {}
pub proof fn keep_ctlerasesplit_ax05() ensures obl_ax05::<CtlEraseSplit>() {}
pub proof fn keep_ctlerasesplit_ax06() ensures obl_ax06::<CtlEraseSplit>() {}
pub proof fn keep_ctlerasesplit_ax07() ensures obl_ax07::<CtlEraseSplit>() {}
pub proof fn keep_ctlerasesplit_ax08() ensures obl_ax08::<CtlEraseSplit>() {}
pub proof fn keep_ctlerasesplit_ax10() ensures obl_ax10::<CtlEraseSplit>() {}
pub proof fn keep_ctlerasesplit_ax11() ensures obl_ax11::<CtlEraseSplit>() {}
pub proof fn keep_ctlerasesplit_ax11m() ensures obl_ax11m::<CtlEraseSplit>() {}
pub proof fn keep_ctlerasesplit_ax12() ensures obl_ax12::<CtlEraseSplit>() {}
pub proof fn keep_ctlerasesplit_ax14() ensures obl_ax14::<CtlEraseSplit>() {}

/// sys00_control_ax05_delete_records (mutant): the redaction deletes the target's records instead of tombstoning them.
pub struct CtlDeleteRecords;
impl SysDesign for CtlDeleteRecords { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Delete, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false } } }
pub proof fn keep_ctldeleterecords_ax02() ensures obl_ax02::<CtlDeleteRecords>() {}
pub proof fn keep_ctldeleterecords_ax03() ensures obl_ax03::<CtlDeleteRecords>() {}
pub proof fn keep_ctldeleterecords_ax04() ensures obl_ax04::<CtlDeleteRecords>() {}
pub proof fn refute_ctldeleterecords_ax05() ensures !obl_ax05::<CtlDeleteRecords>() {}
pub proof fn keep_ctldeleterecords_ax06() ensures obl_ax06::<CtlDeleteRecords>() {}
pub proof fn keep_ctldeleterecords_ax07() ensures obl_ax07::<CtlDeleteRecords>() {}
pub proof fn keep_ctldeleterecords_ax08() ensures obl_ax08::<CtlDeleteRecords>() {}
pub proof fn keep_ctldeleterecords_ax10() ensures obl_ax10::<CtlDeleteRecords>() {}
pub proof fn keep_ctldeleterecords_ax11() ensures obl_ax11::<CtlDeleteRecords>() {}
pub proof fn keep_ctldeleterecords_ax11m() ensures obl_ax11m::<CtlDeleteRecords>() {}
pub proof fn keep_ctldeleterecords_ax12() ensures obl_ax12::<CtlDeleteRecords>() {}
pub proof fn keep_ctldeleterecords_ax14() ensures obl_ax14::<CtlDeleteRecords>() {}

/// sys00_control_ax06_post_on_replay (mutant): post-commit properties by a separate step that also runs on a replay.
pub struct CtlPostOnReplay;
impl SysDesign for CtlPostOnReplay { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::SeparateAlways, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false } } }
pub proof fn keep_ctlpostonreplay_ax02() ensures obl_ax02::<CtlPostOnReplay>() {}
pub proof fn keep_ctlpostonreplay_ax03() ensures obl_ax03::<CtlPostOnReplay>() {}
pub proof fn keep_ctlpostonreplay_ax04() ensures obl_ax04::<CtlPostOnReplay>() {}
pub proof fn keep_ctlpostonreplay_ax05() ensures obl_ax05::<CtlPostOnReplay>() {}
pub proof fn refute_ctlpostonreplay_ax06() ensures !obl_ax06::<CtlPostOnReplay>() {}
pub proof fn keep_ctlpostonreplay_ax07() ensures obl_ax07::<CtlPostOnReplay>() {}
pub proof fn keep_ctlpostonreplay_ax08() ensures obl_ax08::<CtlPostOnReplay>() {}
pub proof fn refute_ctlpostonreplay_ax10() ensures !obl_ax10::<CtlPostOnReplay>() {}
pub proof fn keep_ctlpostonreplay_ax11() ensures obl_ax11::<CtlPostOnReplay>() {}
pub proof fn refute_ctlpostonreplay_ax11m() ensures !obl_ax11m::<CtlPostOnReplay>() {}
pub proof fn keep_ctlpostonreplay_ax12() ensures obl_ax12::<CtlPostOnReplay>() {}
pub proof fn keep_ctlpostonreplay_ax14() ensures obl_ax14::<CtlPostOnReplay>() {}

/// sys00_control_ax07_unrecorded_apply (mutant): the first commit changes content without a record.
pub struct CtlUnrecordedApply;
impl SysDesign for CtlUnrecordedApply { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: false, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false } } }
pub proof fn keep_ctlunrecordedapply_ax02() ensures obl_ax02::<CtlUnrecordedApply>() {}
pub proof fn keep_ctlunrecordedapply_ax03() ensures obl_ax03::<CtlUnrecordedApply>() {}
pub proof fn keep_ctlunrecordedapply_ax04() ensures obl_ax04::<CtlUnrecordedApply>() {}
pub proof fn keep_ctlunrecordedapply_ax05() ensures obl_ax05::<CtlUnrecordedApply>() {}
pub proof fn keep_ctlunrecordedapply_ax06() ensures obl_ax06::<CtlUnrecordedApply>() {}
pub proof fn refute_ctlunrecordedapply_ax07() ensures !obl_ax07::<CtlUnrecordedApply>() {}
pub proof fn keep_ctlunrecordedapply_ax08() ensures obl_ax08::<CtlUnrecordedApply>() {}
pub proof fn keep_ctlunrecordedapply_ax10() ensures obl_ax10::<CtlUnrecordedApply>() {}
pub proof fn keep_ctlunrecordedapply_ax11() ensures obl_ax11::<CtlUnrecordedApply>() {}
pub proof fn keep_ctlunrecordedapply_ax11m() ensures obl_ax11m::<CtlUnrecordedApply>() {}
pub proof fn keep_ctlunrecordedapply_ax12() ensures obl_ax12::<CtlUnrecordedApply>() {}
pub proof fn keep_ctlunrecordedapply_ax14() ensures obl_ax14::<CtlUnrecordedApply>() {}

/// sys00_control_ax08_erase_skips_derived (mutant): the locked erasure does not maintain the derived store.
pub struct CtlEraseSkipsDerived;
impl SysDesign for CtlEraseSkipsDerived { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: false, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false } } }
pub proof fn keep_ctleraseskipsderived_ax02() ensures obl_ax02::<CtlEraseSkipsDerived>() {}
pub proof fn keep_ctleraseskipsderived_ax03() ensures obl_ax03::<CtlEraseSkipsDerived>() {}
pub proof fn keep_ctleraseskipsderived_ax04() ensures obl_ax04::<CtlEraseSkipsDerived>() {}
pub proof fn keep_ctleraseskipsderived_ax05() ensures obl_ax05::<CtlEraseSkipsDerived>() {}
pub proof fn keep_ctleraseskipsderived_ax06() ensures obl_ax06::<CtlEraseSkipsDerived>() {}
pub proof fn keep_ctleraseskipsderived_ax07() ensures obl_ax07::<CtlEraseSkipsDerived>() {}
pub proof fn refute_ctleraseskipsderived_ax08() ensures !obl_ax08::<CtlEraseSkipsDerived>() {}
pub proof fn refute_ctleraseskipsderived_ax10() ensures !obl_ax10::<CtlEraseSkipsDerived>() {}
pub proof fn keep_ctleraseskipsderived_ax11() ensures obl_ax11::<CtlEraseSkipsDerived>() {}
pub proof fn keep_ctleraseskipsderived_ax11m() ensures obl_ax11m::<CtlEraseSkipsDerived>() {}
pub proof fn keep_ctleraseskipsderived_ax12() ensures obl_ax12::<CtlEraseSkipsDerived>() {}
pub proof fn keep_ctleraseskipsderived_ax14() ensures obl_ax14::<CtlEraseSkipsDerived>() {}

/// sys00_control_ax10_binding_kept (mutant): the redaction does not move the retry binding.
pub struct CtlBindingKept;
impl SysDesign for CtlBindingKept { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: false, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false } } }
pub proof fn keep_ctlbindingkept_ax02() ensures obl_ax02::<CtlBindingKept>() {}
pub proof fn keep_ctlbindingkept_ax03() ensures obl_ax03::<CtlBindingKept>() {}
pub proof fn keep_ctlbindingkept_ax04() ensures obl_ax04::<CtlBindingKept>() {}
pub proof fn keep_ctlbindingkept_ax05() ensures obl_ax05::<CtlBindingKept>() {}
pub proof fn keep_ctlbindingkept_ax06() ensures obl_ax06::<CtlBindingKept>() {}
pub proof fn keep_ctlbindingkept_ax07() ensures obl_ax07::<CtlBindingKept>() {}
pub proof fn keep_ctlbindingkept_ax08() ensures obl_ax08::<CtlBindingKept>() {}
pub proof fn refute_ctlbindingkept_ax10() ensures !obl_ax10::<CtlBindingKept>() {}
pub proof fn keep_ctlbindingkept_ax11() ensures obl_ax11::<CtlBindingKept>() {}
pub proof fn keep_ctlbindingkept_ax11m() ensures obl_ax11m::<CtlBindingKept>() {}
pub proof fn keep_ctlbindingkept_ax12() ensures obl_ax12::<CtlBindingKept>() {}
pub proof fn keep_ctlbindingkept_ax14() ensures obl_ax14::<CtlBindingKept>() {}

/// sys00_control_ax11_check_before_lock (mutant): the redaction checks liveness before taking the lock.
pub struct CtlCheckBeforeLock;
impl SysDesign for CtlCheckBeforeLock { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::CheckBeforeLock, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false } } }
pub proof fn keep_ctlcheckbeforelock_ax02() ensures obl_ax02::<CtlCheckBeforeLock>() {}
pub proof fn keep_ctlcheckbeforelock_ax03() ensures obl_ax03::<CtlCheckBeforeLock>() {}
pub proof fn keep_ctlcheckbeforelock_ax04() ensures obl_ax04::<CtlCheckBeforeLock>() {}
pub proof fn keep_ctlcheckbeforelock_ax05() ensures obl_ax05::<CtlCheckBeforeLock>() {}
pub proof fn keep_ctlcheckbeforelock_ax06() ensures obl_ax06::<CtlCheckBeforeLock>() {}
pub proof fn refute_ctlcheckbeforelock_ax07() ensures !obl_ax07::<CtlCheckBeforeLock>() {}
pub proof fn keep_ctlcheckbeforelock_ax08() ensures obl_ax08::<CtlCheckBeforeLock>() {}
pub proof fn keep_ctlcheckbeforelock_ax10() ensures obl_ax10::<CtlCheckBeforeLock>() {}
pub proof fn refute_ctlcheckbeforelock_ax11() ensures !obl_ax11::<CtlCheckBeforeLock>() {}
pub proof fn refute_ctlcheckbeforelock_ax11m() ensures !obl_ax11m::<CtlCheckBeforeLock>() {}
pub proof fn keep_ctlcheckbeforelock_ax12() ensures obl_ax12::<CtlCheckBeforeLock>() {}
pub proof fn keep_ctlcheckbeforelock_ax14() ensures obl_ax14::<CtlCheckBeforeLock>() {}

/// sys00_control_ax12_receipt_early (mutant): the receipt is written before the tombstones.
pub struct CtlReceiptEarly;
impl SysDesign for CtlReceiptEarly { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Early, m10_refusal: M10Refusal::Inert, m10_erase_split: false } } }
pub proof fn keep_ctlreceiptearly_ax02() ensures obl_ax02::<CtlReceiptEarly>() {}
pub proof fn keep_ctlreceiptearly_ax03() ensures obl_ax03::<CtlReceiptEarly>() {}
pub proof fn keep_ctlreceiptearly_ax04() ensures obl_ax04::<CtlReceiptEarly>() {}
pub proof fn keep_ctlreceiptearly_ax05() ensures obl_ax05::<CtlReceiptEarly>() {}
pub proof fn keep_ctlreceiptearly_ax06() ensures obl_ax06::<CtlReceiptEarly>() {}
pub proof fn keep_ctlreceiptearly_ax07() ensures obl_ax07::<CtlReceiptEarly>() {}
pub proof fn keep_ctlreceiptearly_ax08() ensures obl_ax08::<CtlReceiptEarly>() {}
pub proof fn refute_ctlreceiptearly_ax10() ensures !obl_ax10::<CtlReceiptEarly>() {}
pub proof fn keep_ctlreceiptearly_ax11() ensures obl_ax11::<CtlReceiptEarly>() {}
pub proof fn keep_ctlreceiptearly_ax11m() ensures obl_ax11m::<CtlReceiptEarly>() {}
pub proof fn refute_ctlreceiptearly_ax12() ensures !obl_ax12::<CtlReceiptEarly>() {}
pub proof fn keep_ctlreceiptearly_ax14() ensures obl_ax14::<CtlReceiptEarly>() {}

/// sys00_control_ax14_marker_never_cleared (mutant): the redaction never clears its marker.
pub struct CtlMarkerNeverCleared;
impl SysDesign for CtlMarkerNeverCleared { open spec fn cfg() -> SysCfg { SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::NeverCleared, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false } } }
pub proof fn keep_ctlmarkernevercleared_ax02() ensures obl_ax02::<CtlMarkerNeverCleared>() {}
pub proof fn keep_ctlmarkernevercleared_ax03() ensures obl_ax03::<CtlMarkerNeverCleared>() {}
pub proof fn keep_ctlmarkernevercleared_ax04() ensures obl_ax04::<CtlMarkerNeverCleared>() {}
pub proof fn keep_ctlmarkernevercleared_ax05() ensures obl_ax05::<CtlMarkerNeverCleared>() {}
pub proof fn keep_ctlmarkernevercleared_ax06() ensures obl_ax06::<CtlMarkerNeverCleared>() {}
pub proof fn keep_ctlmarkernevercleared_ax07() ensures obl_ax07::<CtlMarkerNeverCleared>() {}
pub proof fn keep_ctlmarkernevercleared_ax08() ensures obl_ax08::<CtlMarkerNeverCleared>() {}
pub proof fn keep_ctlmarkernevercleared_ax10() ensures obl_ax10::<CtlMarkerNeverCleared>() {}
pub proof fn keep_ctlmarkernevercleared_ax11() ensures obl_ax11::<CtlMarkerNeverCleared>() {}
pub proof fn keep_ctlmarkernevercleared_ax11m() ensures obl_ax11m::<CtlMarkerNeverCleared>() {}
pub proof fn keep_ctlmarkernevercleared_ax12() ensures obl_ax12::<CtlMarkerNeverCleared>() {}
pub proof fn refute_ctlmarkernevercleared_ax14() ensures !obl_ax14::<CtlMarkerNeverCleared>() {}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// sys00-sharp-redaction-completes: tenant A redacted with a receipt while B is live.
pub proof fn sharp_redaction_completes()
    ensures ({
        let r = run::<SysM<SysReviewed>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && ({ let t = r->0; t.receipt && t.content[1] && !t.content[0] && t.bind is Redacted })
    })
{
    crate::progress::lemma_run_cfg::<SysReviewed>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(1), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3)]);
        r is Some && ({ let t = r->0; t.receipt && t.content[1] && !t.content[0] && t.bind is Redacted })
    }) by (compute);
}

/// sys00-sharp-retry-refused-after-redaction: the retry refused after redaction.
pub proof fn sharp_retry_refused_after_redaction()
    ensures ({
        let r = run::<SysM<SysReviewed>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0)]);
        r is Some && ({ let t = r->0; t.reply is Refused && t.bind is Redacted })
    })
{
    crate::progress::lemma_run_cfg::<SysReviewed>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(2), SA::Run(2), SA::Run(2), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0), SA::Run(0)]);
        r is Some && ({ let t = r->0; t.reply is Refused && t.bind is Redacted })
    }) by (compute);
}

/// sys00-sharp-replay: a replayed answer.
pub proof fn sharp_replay()
    ensures ({
        let r = run::<SysM<SysReviewed>>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0)]);
        r is Some && ({ let t = r->0; t.reply is Replay })
    })
{
    crate::progress::lemma_run_cfg::<SysReviewed>(sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0), SA::Run(0)]);
        r is Some && ({ let t = r->0; t.reply is Replay })
    }) by (compute);
}

/// sys00-sharp-commit-blocked-by-marker: the writer refused by the marker.
pub proof fn sharp_commit_blocked_by_marker()
    ensures ({
        let r = run::<SysM<SysReviewed>>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
        r is Some && ({ let t = r->0; t.pc[0] is Refused && t.marker is Some })
    })
{
    crate::progress::lemma_run_cfg::<SysReviewed>(sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
    reveal(effect);
    assert({
        let r = run_cfg(SysCfg { m01_recorded: true, m02_post: M02Post::InCommit, m03_redact: M03Redact::Reviewed, m03_erase_locked: true, m04_erase_maintains: true, m05_tomb: M05Tomb::Own, m05_move_binding: true, m05_receipt: M05Receipt::Final, m10_refusal: M10Refusal::Inert, m10_erase_split: false }, sys_s0(), seq![SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(3), SA::Run(0), SA::Run(0)]);
        r is Some && ({ let t = r->0; t.pc[0] is Refused && t.marker is Some })
    }) by (compute);
}

} // verus!
