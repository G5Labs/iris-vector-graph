//! Located controls: each block exists only under its feature and is the departing design's attempt to discharge the
//! system trait: kept obligations by the baseline's `keep_*` lemmas, each broken one asserted on its LOCATE line.
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::sys::*;
#[allow(unused_imports)]
use crate::inst::*;

verus! {

// CONTROL sys00_as_built mech=SYS check=sys00-as-built-ax-06,sys00-as-built-ax-07,sys00-as-built-ax-08,sys00-as-built-ax-10,sys00-as-built-ax-11,sys00-as-built-ax-11-marker kind=as-built objects=00/system findings=F-1101,F-1306,F-1302,F-0702,F-0606 violates=AX-06,AX-07,AX-08,AX-10,AX-11,AX-11M refute=inst::refute_sysasbuilt_ax06,inst::refute_sysasbuilt_ax07,inst::refute_sysasbuilt_ax08,inst::refute_sysasbuilt_ax10,inst::refute_sysasbuilt_ax11,inst::refute_sysasbuilt_ax11m cx=cx::cx_sysasbuilt_ax06,cx::cx_sysasbuilt_ax07,cx::cx_sysasbuilt_ax08,cx::cx_sysasbuilt_ax10,cx::cx_sysasbuilt_ax11,cx::cx_sysasbuilt_ax11m
#[cfg(feature = "sys00_as_built")]
impl SysObject for SysAsBuilt {
    proof fn discharge_ax02() { keep_sysasbuilt_ax02(); }
    proof fn discharge_ax03() { keep_sysasbuilt_ax03(); }
    proof fn discharge_ax04() { keep_sysasbuilt_ax04(); }
    proof fn discharge_ax05() { keep_sysasbuilt_ax05(); }
    proof fn discharge_ax06() {
        assert(obl_ax06::<Self>()); // LOCATE sys00_as_built AX-06
    }
    proof fn discharge_ax07() {
        assert(obl_ax07::<Self>()); // LOCATE sys00_as_built AX-07
    }
    proof fn discharge_ax08() {
        assert(obl_ax08::<Self>()); // LOCATE sys00_as_built AX-08
    }
    proof fn discharge_ax10() {
        assert(obl_ax10::<Self>()); // LOCATE sys00_as_built AX-10
    }
    proof fn discharge_ax11() {
        assert(obl_ax11::<Self>()); // LOCATE sys00_as_built AX-11
    }
    proof fn discharge_ax11m() {
        assert(obl_ax11m::<Self>()); // LOCATE sys00_as_built AX-11M
    }
    proof fn discharge_ax12() { keep_sysasbuilt_ax12(); }
    proof fn discharge_ax14() { keep_sysasbuilt_ax14(); }
}

// CONTROL sys00_control_ax02_tomb_both_tenants mech=SYS check=sys00-control-ax02-tomb-both-tenants kind=mutant objects=00/system findings= violates=AX-02,AX-07 refute=inst::refute_ctltombbothtenants_ax02,inst::refute_ctltombbothtenants_ax07 cx=cx::cx_ctltombbothtenants_ax02,cx::cx_ctltombbothtenants_ax07
#[cfg(feature = "sys00_control_ax02_tomb_both_tenants")]
impl SysObject for CtlTombBothTenants {
    proof fn discharge_ax02() {
        assert(obl_ax02::<Self>()); // LOCATE sys00_control_ax02_tomb_both_tenants AX-02
    }
    proof fn discharge_ax03() { keep_ctltombbothtenants_ax03(); }
    proof fn discharge_ax04() { keep_ctltombbothtenants_ax04(); }
    proof fn discharge_ax05() { keep_ctltombbothtenants_ax05(); }
    proof fn discharge_ax06() { keep_ctltombbothtenants_ax06(); }
    proof fn discharge_ax07() {
        assert(obl_ax07::<Self>()); // LOCATE sys00_control_ax02_tomb_both_tenants AX-07
    }
    proof fn discharge_ax08() { keep_ctltombbothtenants_ax08(); }
    proof fn discharge_ax10() { keep_ctltombbothtenants_ax10(); }
    proof fn discharge_ax11() { keep_ctltombbothtenants_ax11(); }
    proof fn discharge_ax11m() { keep_ctltombbothtenants_ax11m(); }
    proof fn discharge_ax12() { keep_ctltombbothtenants_ax12(); }
    proof fn discharge_ax14() { keep_ctltombbothtenants_ax14(); }
}

// CONTROL sys00_control_ax03_refusal_writes mech=SYS check=sys00-control-ax03-refusal-writes kind=mutant objects=00/system findings= violates=AX-03,AX-07,AX-08,AX-11M refute=inst::refute_ctlrefusalwrites_ax03,inst::refute_ctlrefusalwrites_ax07,inst::refute_ctlrefusalwrites_ax08,inst::refute_ctlrefusalwrites_ax11m cx=cx::cx_ctlrefusalwrites_ax03,cx::cx_ctlrefusalwrites_ax07,cx::cx_ctlrefusalwrites_ax08,cx::cx_ctlrefusalwrites_ax11m
#[cfg(feature = "sys00_control_ax03_refusal_writes")]
impl SysObject for CtlRefusalWrites {
    proof fn discharge_ax02() { keep_ctlrefusalwrites_ax02(); }
    proof fn discharge_ax03() {
        assert(obl_ax03::<Self>()); // LOCATE sys00_control_ax03_refusal_writes AX-03
    }
    proof fn discharge_ax04() { keep_ctlrefusalwrites_ax04(); }
    proof fn discharge_ax05() { keep_ctlrefusalwrites_ax05(); }
    proof fn discharge_ax06() { keep_ctlrefusalwrites_ax06(); }
    proof fn discharge_ax07() {
        assert(obl_ax07::<Self>()); // LOCATE sys00_control_ax03_refusal_writes AX-07
    }
    proof fn discharge_ax08() {
        assert(obl_ax08::<Self>()); // LOCATE sys00_control_ax03_refusal_writes AX-08
    }
    proof fn discharge_ax10() { keep_ctlrefusalwrites_ax10(); }
    proof fn discharge_ax11() { keep_ctlrefusalwrites_ax11(); }
    proof fn discharge_ax11m() {
        assert(obl_ax11m::<Self>()); // LOCATE sys00_control_ax03_refusal_writes AX-11M
    }
    proof fn discharge_ax12() { keep_ctlrefusalwrites_ax12(); }
    proof fn discharge_ax14() { keep_ctlrefusalwrites_ax14(); }
}

// CONTROL sys00_control_ax04_erase_split mech=SYS check=sys00-control-ax04-erase-split kind=mutant objects=00/system findings= violates=AX-04 refute=inst::refute_ctlerasesplit_ax04 cx=cx::cx_ctlerasesplit_ax04
#[cfg(feature = "sys00_control_ax04_erase_split")]
impl SysObject for CtlEraseSplit {
    proof fn discharge_ax02() { keep_ctlerasesplit_ax02(); }
    proof fn discharge_ax03() { keep_ctlerasesplit_ax03(); }
    proof fn discharge_ax04() {
        assert(obl_ax04::<Self>()); // LOCATE sys00_control_ax04_erase_split AX-04
    }
    proof fn discharge_ax05() { keep_ctlerasesplit_ax05(); }
    proof fn discharge_ax06() { keep_ctlerasesplit_ax06(); }
    proof fn discharge_ax07() { keep_ctlerasesplit_ax07(); }
    proof fn discharge_ax08() { keep_ctlerasesplit_ax08(); }
    proof fn discharge_ax10() { keep_ctlerasesplit_ax10(); }
    proof fn discharge_ax11() { keep_ctlerasesplit_ax11(); }
    proof fn discharge_ax11m() { keep_ctlerasesplit_ax11m(); }
    proof fn discharge_ax12() { keep_ctlerasesplit_ax12(); }
    proof fn discharge_ax14() { keep_ctlerasesplit_ax14(); }
}

// CONTROL sys00_control_ax05_delete_records mech=SYS check=sys00-control-ax05-delete-records kind=mutant objects=00/system findings= violates=AX-05 refute=inst::refute_ctldeleterecords_ax05 cx=cx::cx_ctldeleterecords_ax05
#[cfg(feature = "sys00_control_ax05_delete_records")]
impl SysObject for CtlDeleteRecords {
    proof fn discharge_ax02() { keep_ctldeleterecords_ax02(); }
    proof fn discharge_ax03() { keep_ctldeleterecords_ax03(); }
    proof fn discharge_ax04() { keep_ctldeleterecords_ax04(); }
    proof fn discharge_ax05() {
        assert(obl_ax05::<Self>()); // LOCATE sys00_control_ax05_delete_records AX-05
    }
    proof fn discharge_ax06() { keep_ctldeleterecords_ax06(); }
    proof fn discharge_ax07() { keep_ctldeleterecords_ax07(); }
    proof fn discharge_ax08() { keep_ctldeleterecords_ax08(); }
    proof fn discharge_ax10() { keep_ctldeleterecords_ax10(); }
    proof fn discharge_ax11() { keep_ctldeleterecords_ax11(); }
    proof fn discharge_ax11m() { keep_ctldeleterecords_ax11m(); }
    proof fn discharge_ax12() { keep_ctldeleterecords_ax12(); }
    proof fn discharge_ax14() { keep_ctldeleterecords_ax14(); }
}

// CONTROL sys00_control_ax06_post_on_replay mech=SYS check=sys00-control-ax06-post-on-replay kind=mutant objects=00/system findings= violates=AX-06,AX-10,AX-11M refute=inst::refute_ctlpostonreplay_ax06,inst::refute_ctlpostonreplay_ax10,inst::refute_ctlpostonreplay_ax11m cx=cx::cx_ctlpostonreplay_ax06,cx::cx_ctlpostonreplay_ax10,cx::cx_ctlpostonreplay_ax11m
#[cfg(feature = "sys00_control_ax06_post_on_replay")]
impl SysObject for CtlPostOnReplay {
    proof fn discharge_ax02() { keep_ctlpostonreplay_ax02(); }
    proof fn discharge_ax03() { keep_ctlpostonreplay_ax03(); }
    proof fn discharge_ax04() { keep_ctlpostonreplay_ax04(); }
    proof fn discharge_ax05() { keep_ctlpostonreplay_ax05(); }
    proof fn discharge_ax06() {
        assert(obl_ax06::<Self>()); // LOCATE sys00_control_ax06_post_on_replay AX-06
    }
    proof fn discharge_ax07() { keep_ctlpostonreplay_ax07(); }
    proof fn discharge_ax08() { keep_ctlpostonreplay_ax08(); }
    proof fn discharge_ax10() {
        assert(obl_ax10::<Self>()); // LOCATE sys00_control_ax06_post_on_replay AX-10
    }
    proof fn discharge_ax11() { keep_ctlpostonreplay_ax11(); }
    proof fn discharge_ax11m() {
        assert(obl_ax11m::<Self>()); // LOCATE sys00_control_ax06_post_on_replay AX-11M
    }
    proof fn discharge_ax12() { keep_ctlpostonreplay_ax12(); }
    proof fn discharge_ax14() { keep_ctlpostonreplay_ax14(); }
}

// CONTROL sys00_control_ax07_unrecorded_apply mech=SYS check=sys00-control-ax07-unrecorded-apply kind=mutant objects=00/system findings= violates=AX-07 refute=inst::refute_ctlunrecordedapply_ax07 cx=cx::cx_ctlunrecordedapply_ax07
#[cfg(feature = "sys00_control_ax07_unrecorded_apply")]
impl SysObject for CtlUnrecordedApply {
    proof fn discharge_ax02() { keep_ctlunrecordedapply_ax02(); }
    proof fn discharge_ax03() { keep_ctlunrecordedapply_ax03(); }
    proof fn discharge_ax04() { keep_ctlunrecordedapply_ax04(); }
    proof fn discharge_ax05() { keep_ctlunrecordedapply_ax05(); }
    proof fn discharge_ax06() { keep_ctlunrecordedapply_ax06(); }
    proof fn discharge_ax07() {
        assert(obl_ax07::<Self>()); // LOCATE sys00_control_ax07_unrecorded_apply AX-07
    }
    proof fn discharge_ax08() { keep_ctlunrecordedapply_ax08(); }
    proof fn discharge_ax10() { keep_ctlunrecordedapply_ax10(); }
    proof fn discharge_ax11() { keep_ctlunrecordedapply_ax11(); }
    proof fn discharge_ax11m() { keep_ctlunrecordedapply_ax11m(); }
    proof fn discharge_ax12() { keep_ctlunrecordedapply_ax12(); }
    proof fn discharge_ax14() { keep_ctlunrecordedapply_ax14(); }
}

// CONTROL sys00_control_ax08_erase_skips_derived mech=SYS check=sys00-control-ax08-erase-skips-derived kind=mutant objects=00/system findings= violates=AX-08,AX-10 refute=inst::refute_ctleraseskipsderived_ax08,inst::refute_ctleraseskipsderived_ax10 cx=cx::cx_ctleraseskipsderived_ax08,cx::cx_ctleraseskipsderived_ax10
#[cfg(feature = "sys00_control_ax08_erase_skips_derived")]
impl SysObject for CtlEraseSkipsDerived {
    proof fn discharge_ax02() { keep_ctleraseskipsderived_ax02(); }
    proof fn discharge_ax03() { keep_ctleraseskipsderived_ax03(); }
    proof fn discharge_ax04() { keep_ctleraseskipsderived_ax04(); }
    proof fn discharge_ax05() { keep_ctleraseskipsderived_ax05(); }
    proof fn discharge_ax06() { keep_ctleraseskipsderived_ax06(); }
    proof fn discharge_ax07() { keep_ctleraseskipsderived_ax07(); }
    proof fn discharge_ax08() {
        assert(obl_ax08::<Self>()); // LOCATE sys00_control_ax08_erase_skips_derived AX-08
    }
    proof fn discharge_ax10() {
        assert(obl_ax10::<Self>()); // LOCATE sys00_control_ax08_erase_skips_derived AX-10
    }
    proof fn discharge_ax11() { keep_ctleraseskipsderived_ax11(); }
    proof fn discharge_ax11m() { keep_ctleraseskipsderived_ax11m(); }
    proof fn discharge_ax12() { keep_ctleraseskipsderived_ax12(); }
    proof fn discharge_ax14() { keep_ctleraseskipsderived_ax14(); }
}

// CONTROL sys00_control_ax10_binding_kept mech=SYS check=sys00-control-ax10-binding-kept kind=mutant objects=00/system findings= violates=AX-10 refute=inst::refute_ctlbindingkept_ax10 cx=cx::cx_ctlbindingkept_ax10
#[cfg(feature = "sys00_control_ax10_binding_kept")]
impl SysObject for CtlBindingKept {
    proof fn discharge_ax02() { keep_ctlbindingkept_ax02(); }
    proof fn discharge_ax03() { keep_ctlbindingkept_ax03(); }
    proof fn discharge_ax04() { keep_ctlbindingkept_ax04(); }
    proof fn discharge_ax05() { keep_ctlbindingkept_ax05(); }
    proof fn discharge_ax06() { keep_ctlbindingkept_ax06(); }
    proof fn discharge_ax07() { keep_ctlbindingkept_ax07(); }
    proof fn discharge_ax08() { keep_ctlbindingkept_ax08(); }
    proof fn discharge_ax10() {
        assert(obl_ax10::<Self>()); // LOCATE sys00_control_ax10_binding_kept AX-10
    }
    proof fn discharge_ax11() { keep_ctlbindingkept_ax11(); }
    proof fn discharge_ax11m() { keep_ctlbindingkept_ax11m(); }
    proof fn discharge_ax12() { keep_ctlbindingkept_ax12(); }
    proof fn discharge_ax14() { keep_ctlbindingkept_ax14(); }
}

// CONTROL sys00_control_ax11_check_before_lock mech=SYS check=sys00-control-ax11-check-before-lock kind=mutant objects=00/system findings= violates=AX-07,AX-11,AX-11M refute=inst::refute_ctlcheckbeforelock_ax07,inst::refute_ctlcheckbeforelock_ax11,inst::refute_ctlcheckbeforelock_ax11m cx=cx::cx_ctlcheckbeforelock_ax07,cx::cx_ctlcheckbeforelock_ax11,cx::cx_ctlcheckbeforelock_ax11m
#[cfg(feature = "sys00_control_ax11_check_before_lock")]
impl SysObject for CtlCheckBeforeLock {
    proof fn discharge_ax02() { keep_ctlcheckbeforelock_ax02(); }
    proof fn discharge_ax03() { keep_ctlcheckbeforelock_ax03(); }
    proof fn discharge_ax04() { keep_ctlcheckbeforelock_ax04(); }
    proof fn discharge_ax05() { keep_ctlcheckbeforelock_ax05(); }
    proof fn discharge_ax06() { keep_ctlcheckbeforelock_ax06(); }
    proof fn discharge_ax07() {
        assert(obl_ax07::<Self>()); // LOCATE sys00_control_ax11_check_before_lock AX-07
    }
    proof fn discharge_ax08() { keep_ctlcheckbeforelock_ax08(); }
    proof fn discharge_ax10() { keep_ctlcheckbeforelock_ax10(); }
    proof fn discharge_ax11() {
        assert(obl_ax11::<Self>()); // LOCATE sys00_control_ax11_check_before_lock AX-11
    }
    proof fn discharge_ax11m() {
        assert(obl_ax11m::<Self>()); // LOCATE sys00_control_ax11_check_before_lock AX-11M
    }
    proof fn discharge_ax12() { keep_ctlcheckbeforelock_ax12(); }
    proof fn discharge_ax14() { keep_ctlcheckbeforelock_ax14(); }
}

// CONTROL sys00_control_ax12_receipt_early mech=SYS check=sys00-control-ax12-receipt-early kind=mutant objects=00/system findings= violates=AX-10,AX-12 refute=inst::refute_ctlreceiptearly_ax10,inst::refute_ctlreceiptearly_ax12 cx=cx::cx_ctlreceiptearly_ax10,cx::cx_ctlreceiptearly_ax12
#[cfg(feature = "sys00_control_ax12_receipt_early")]
impl SysObject for CtlReceiptEarly {
    proof fn discharge_ax02() { keep_ctlreceiptearly_ax02(); }
    proof fn discharge_ax03() { keep_ctlreceiptearly_ax03(); }
    proof fn discharge_ax04() { keep_ctlreceiptearly_ax04(); }
    proof fn discharge_ax05() { keep_ctlreceiptearly_ax05(); }
    proof fn discharge_ax06() { keep_ctlreceiptearly_ax06(); }
    proof fn discharge_ax07() { keep_ctlreceiptearly_ax07(); }
    proof fn discharge_ax08() { keep_ctlreceiptearly_ax08(); }
    proof fn discharge_ax10() {
        assert(obl_ax10::<Self>()); // LOCATE sys00_control_ax12_receipt_early AX-10
    }
    proof fn discharge_ax11() { keep_ctlreceiptearly_ax11(); }
    proof fn discharge_ax11m() { keep_ctlreceiptearly_ax11m(); }
    proof fn discharge_ax12() {
        assert(obl_ax12::<Self>()); // LOCATE sys00_control_ax12_receipt_early AX-12
    }
    proof fn discharge_ax14() { keep_ctlreceiptearly_ax14(); }
}

// CONTROL sys00_control_ax14_marker_never_cleared mech=SYS check=sys00-control-ax14-marker-never-cleared kind=mutant objects=00/system findings= violates=AX-14 refute=inst::refute_ctlmarkernevercleared_ax14 cx=cx::cx_ctlmarkernevercleared_ax14
#[cfg(feature = "sys00_control_ax14_marker_never_cleared")]
impl SysObject for CtlMarkerNeverCleared {
    proof fn discharge_ax02() { keep_ctlmarkernevercleared_ax02(); }
    proof fn discharge_ax03() { keep_ctlmarkernevercleared_ax03(); }
    proof fn discharge_ax04() { keep_ctlmarkernevercleared_ax04(); }
    proof fn discharge_ax05() { keep_ctlmarkernevercleared_ax05(); }
    proof fn discharge_ax06() { keep_ctlmarkernevercleared_ax06(); }
    proof fn discharge_ax07() { keep_ctlmarkernevercleared_ax07(); }
    proof fn discharge_ax08() { keep_ctlmarkernevercleared_ax08(); }
    proof fn discharge_ax10() { keep_ctlmarkernevercleared_ax10(); }
    proof fn discharge_ax11() { keep_ctlmarkernevercleared_ax11(); }
    proof fn discharge_ax11m() { keep_ctlmarkernevercleared_ax11m(); }
    proof fn discharge_ax12() { keep_ctlmarkernevercleared_ax12(); }
    proof fn discharge_ax14() {
        assert(obl_ax14::<Self>()); // LOCATE sys00_control_ax14_marker_never_cleared AX-14
    }
}

} // verus!
