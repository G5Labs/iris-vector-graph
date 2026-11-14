//! Proved counterexample for control `control_fc1804_edge_routes_omitted` (F-C1804), compiled only with it.
//!
//! The live traces c18-live-edge-vectors / c18-live-edge-routes: an edge vector is committed into a `kg_eemb_*` route;
//! save_snapshot's routed plan keeps node routes only (snapshot.py:299-344; security.py:58-68), so the archive lacks
//! it: the save is not an L1 step. A replacing restore of that archive then answers failed_rows = {} with the edge
//! vector gone.
use vstd::prelude::*;
use actors::protocol::*;
use crate::snap_l1::*;
use crate::snap_l2::*;
use crate::snap_runs::*;

verus! {

pub open spec fn e() -> Item { (2, 0, 1) }
pub open spec fn none() -> Set<Item> { Set::empty() }
pub open spec fn e1() -> SS2 { c_commit(c0(), set![e()], 1) }
pub open spec fn e2() -> SS2 { sve(e1(), 0) }
pub open spec fn e_end() -> SS2 { re(e2(), 0, none()) }

pub proof fn counterexample_fc1804()
    ensures
        init2(c0()),
        step2(c0(), SL2::Commit { items: set![e()], id: 1 }, e1()),
        step2(e1(), SL2::XStart { id: 0 }, sv(e1(), 0, 0)),
        step2(sv(e1(), 0, 0), SL2::XRead, sv(e1(), 0, 1)),
        step2(sv(e1(), 0, 1), SL2::XRead, sv(e1(), 0, 2)),
        step2(sv(e1(), 0, 2), SL2::XRead, sv(e1(), 0, 3)),
        step2(sv(e1(), 0, 3), SL2::XRead, sv(e1(), 0, 4)),
        step2(sv(e1(), 0, 4), SL2::XLedger, svl(e1(), 0)),
        step2(svl(e1(), 0), SL2::XEnd { id: 0, lines: read_upto(e1().cur, 4), g: e1().g }, e2()),
        // the save is not an L1 step: the archive lacks the committed edge vector
        !step_or_stutter::<SnapL1>(abs18(svl(e1(), 0)),
            lab18(SL2::XEnd { id: 0, lines: read_upto(e1().cur, 4), g: e1().g }), abs18(e2())),
        step2(e2(), SL2::RBegin { id: 0 }, rb(e2(), 0)),
        step2(rb(e2(), 0), SL2::RLoad { bad: none() }, rl(e2(), 0, none())),
        step2(rl(e2(), 0, none()), SL2::RLedger, rg(e2(), 0, none())),
        step2(rg(e2(), 0, none()), SL2::REnd { id: 0, failed: none() }, e_end()),
        // the restore answers failed_rows = {} and the edge vector is gone
        e1().rows.contains(e()) && !e_end().rows.contains(e()) && fail_of(none()) == none(),
{
    lemma_c0();
    lemma_commit_run(c0(), set![e()], 1);
    assert(e1().cur =~= set![e()]);
    assert(read_upto(e1().cur, 4) =~= none()) by { assert(!planned(2)); }
    lemma_save_run(e1(), 0);
    let a1 = abs18(svl(e1(), 0));
    assert(a1.content.contains(e()));
    assert(prefix(e2().g.led, e2().files[0].g.led));
    lemma_restore_run(e2(), 0, none());
    assert(e2().files[0].lines == none());
    assert(e_end().rows =~= none());
}

} // verus!
