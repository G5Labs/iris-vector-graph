//! Proved counterexample for control `control_f1713_status_parts_short` (F-1713), compiled only with it.
//!
//! The check c17-offline: STATUS_PARTS is the eight names of status.py:11, and admin.py appends "adjacency" (:551)
//! and "routines" (:752-753) to unknown. Here the adjacency probe fails and the report marks part 8 unknown, which the
//! published list does not name (not an L1 step).
use vstd::prelude::*;
use actors::protocol::*;
use crate::opsc_l1::*;
use crate::opsc_l2::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

pub open spec fn v0() -> O2 { O2 { deployed: Set::empty(), drv: None, rows: 0 } }
pub open spec fn u8s() -> Set<nat> { Set::<nat>::empty().insert(8) }

pub proof fn counterexample_f1713()
    ensures
        init2(v0()),
        step2(v0(), OL2::Report { failed: u8s(), unknown: u8s(), parts: status_parts() }, v0()),
        !status_parts().contains(8),
        !step_or_stutter::<OpscL1>(abso(v0()), labo(OL2::Report { failed: u8s(), unknown: u8s(), parts: status_parts() }), abso(v0())),
{
    assert(u8s().subset_of(all_parts()));
    assert(u8s().contains(8));
}

} // verus!
