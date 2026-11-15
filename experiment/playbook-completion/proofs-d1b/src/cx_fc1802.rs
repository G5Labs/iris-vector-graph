//! Proved counterexample for control `control_fc1802_swallowed_line` (F-C1802), compiled only with it.
//!
//! The live trace c18-live-swallowed-lines: a native-global line is committed and archived; on restore IRIS refuses
//! it (<SUBSCRIPT>); _import_global_from_ndjson logs it at debug and goes on (snapshot.py:1665-1684). The answer says
//! nothing failed while the line is missing: not an L1 step.
use vstd::prelude::*;
use actors::protocol::*;
use crate::snap_l1::*;
use crate::snap_l2::*;
use crate::snap_runs::*;

verus! {

pub open spec fn y() -> Item { (3, 0, 1) }
pub open spec fn none() -> Set<Item> { Set::empty() }
pub open spec fn f1() -> SS2 { c_commit(c0(), set![y()], 1) }
pub open spec fn f2() -> SS2 { sve(f1(), 0) }
pub open spec fn f_end() -> SS2 { re(f2(), 0, set![y()]) }

pub proof fn counterexample_fc1802()
    ensures
        init2(c0()),
        step2(c0(), SL2::Commit { items: set![y()], id: 1 }, f1()),
        step2(f1(), SL2::XStart { id: 0 }, sv(f1(), 0, 0)),
        step2(sv(f1(), 0, 0), SL2::XRead, sv(f1(), 0, 1)),
        step2(sv(f1(), 0, 1), SL2::XRead, sv(f1(), 0, 2)),
        step2(sv(f1(), 0, 2), SL2::XRead, sv(f1(), 0, 3)),
        step2(sv(f1(), 0, 3), SL2::XRead, sv(f1(), 0, 4)),
        step2(sv(f1(), 0, 4), SL2::XLedger, svl(f1(), 0)),
        step2(svl(f1(), 0), SL2::XEnd { id: 0, lines: read_upto(f1().cur, 4), g: f1().g }, f2()),
        step2(f2(), SL2::RBegin { id: 0 }, rb(f2(), 0)),
        step2(rb(f2(), 0), SL2::RLoad { bad: set![y()] }, rl(f2(), 0, set![y()])),
        step2(rl(f2(), 0, set![y()]), SL2::RLedger, rg(f2(), 0, set![y()])),
        step2(rg(f2(), 0, set![y()]), SL2::REnd { id: 0, failed: none() }, f_end()),
        // the answer is not an L1 step: failed_rows is empty while the line is not restored
        !step_or_stutter::<SnapL1>(abs18(rg(f2(), 0, set![y()])), lab18(SL2::REnd { id: 0, failed: none() }), abs18(f_end())),
        !f_end().rows.contains(y()),
{
    lemma_c0();
    lemma_commit_run(c0(), set![y()], 1);
    assert(f1().cur =~= set![y()]);
    assert(read_upto(f1().cur, 4) =~= set![y()]) by { assert(planned(3)); }
    lemma_save_run(f1(), 0);
    assert(f2().files[0].lines == set![y()]);
    assert(store_of(set![y()], 3) =~= set![y()]);
    assert(prefix(f2().g.led, f2().files[0].g.led));
    lemma_restore_run(f2(), 0, set![y()]);
    assert(set![y()].difference(set![y()]) =~= none());
    assert(f_end().rows =~= none());
    let a1 = abs18(rg(f2(), 0, set![y()]));
    assert(scrub(a1.archives[0].content.difference(none()), a1.red).contains(y()));
}

} // verus!
