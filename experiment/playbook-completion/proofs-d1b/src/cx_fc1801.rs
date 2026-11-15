//! Proved counterexample for control `control_fc1801_dirty_export` (F-C1801, HD-1802), compiled only with it.
//!
//! The live trace c18-live-dirty-export: another connection opens a transaction and creates a row; save_snapshot
//! runs (no lock, uncommitted reads, snapshot.py:864-1034) and archives it; the writer rolls back. The archive holds
//! a row the namespace never committed: the save is not an L1 step.
use vstd::prelude::*;
use actors::protocol::*;
use crate::snap_l1::*;
use crate::snap_l2::*;
use crate::snap_runs::*;

verus! {

pub open spec fn ghost_row() -> Item { (0, 0, 1) }
pub open spec fn d1() -> SS2 { SS2 { cur: c0().cur.union(set![ghost_row()]), w: Some(set![ghost_row()]), ..c0() } }
pub open spec fn d2() -> SS2 { sve(d1(), 0) }
pub open spec fn d_end() -> SS2 { SS2 { rows: d2().rows, cur: d2().cur.difference(set![ghost_row()]), w: None, ..d2() } }

pub proof fn counterexample_fc1801()
    ensures
        init2(c0()),
        step2(c0(), SL2::WOpen { items: set![ghost_row()] }, d1()),
        step2(d1(), SL2::XStart { id: 0 }, sv(d1(), 0, 0)),
        step2(sv(d1(), 0, 0), SL2::XRead, sv(d1(), 0, 1)),
        step2(sv(d1(), 0, 1), SL2::XRead, sv(d1(), 0, 2)),
        step2(sv(d1(), 0, 2), SL2::XRead, sv(d1(), 0, 3)),
        step2(sv(d1(), 0, 3), SL2::XRead, sv(d1(), 0, 4)),
        step2(sv(d1(), 0, 4), SL2::XLedger, svl(d1(), 0)),
        step2(svl(d1(), 0), SL2::XEnd { id: 0, lines: read_upto(d1().cur, 4), g: d1().g }, d2()),
        // the save is not an L1 step: the archive is not the committed state
        !step_or_stutter::<SnapL1>(abs18(svl(d1(), 0)),
            lab18(SL2::XEnd { id: 0, lines: read_upto(d1().cur, 4), g: d1().g }), abs18(d2())),
        step2(d2(), SL2::WEnd { commit: false, items: set![ghost_row()] }, d_end()),
        d_end().rows == Set::<Item>::empty() && d_end().files[0].lines.contains(ghost_row()),
{
    lemma_c0();
    assert(step2(c0(), SL2::WOpen { items: set![ghost_row()] }, d1()));
    lemma_save_run(d1(), 0);
    assert(d1().cur =~= set![ghost_row()]);
    assert(read_upto(d1().cur, 4) =~= set![ghost_row()]) by { assert(planned(0)); }
    let a1 = abs18(svl(d1(), 0));
    assert(a1.content == Set::<Item>::empty());
    assert(!set![ghost_row()].subset_of(Set::<Item>::empty())) by { assert(set![ghost_row()].contains(ghost_row())); }
    assert(d_end().files[0].lines == set![ghost_row()]);
}

} // verus!
