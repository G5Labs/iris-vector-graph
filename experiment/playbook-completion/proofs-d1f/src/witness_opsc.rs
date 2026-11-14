//! Non-vacuity of the reviewed operations-claims model (compiled without its controls): capability 3 deployed and
//! claimed available, capability 4 claimed supported by the catalogue but not available, and its routed call raises;
//! a locked install of 5.4.0; a duplicate row skipped; a report marking adjacency and routines unknown.
use vstd::prelude::*;
use crate::opsc_l1::*;
use crate::opsc_l2::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

pub open spec fn o0() -> O2 { O2 { deployed: Set::empty(), drv: None, rows: 0 } }
pub open spec fn o1() -> O2 { O2 { deployed: o0().deployed.insert(3), ..o0() } }
pub open spec fn o2() -> O2 { O2 { drv: Some(540), ..o1() } }
pub open spec fn u89() -> Set<nat> { Set::<nat>::empty().insert(8).insert(9) }

pub proof fn witness_opsc()
    ensures
        init2(o0()),
        step2(o0(), OL2::Deploy { cap: 3 }, o1()),
        step2(o1(), OL2::Claim { cap: 3, avail: true }, o1()),
        step2(o1(), OL2::Claim { cap: 4, avail: false }, o1()),
        step2(o1(), OL2::Catalogue { cap: 4, supported: true }, o1()),
        step2(o1(), OL2::Route { cap: 4, via_store: true, ok: false }, o1()),
        step2(o1(), OL2::Install { v: 540, locked: true }, o2()),
        step2(o2(), OL2::WriteNodes { dup: true, ok: true }, o2()),
        step2(o2(), OL2::WriteNodes { dup: false, ok: true }, O2 { rows: 1, ..o2() }),
        step2(o2(), OL2::Report { failed: u89(), unknown: u89(), parts: Set::<nat>::range(0, 10) }, o2()),
{
    assert(o1().deployed.contains(3));
    assert(!o1().deployed.contains(4));
    assert(u89().subset_of(all_parts()));
}

} // verus!
