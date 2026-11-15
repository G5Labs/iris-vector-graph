//! Proved counterexample for control `control_f1801_restore_unredacts` (F-1801 redaction half, F-C1304 restore),
//! compiled only with it.
//!
//! The live traces c18-live-ledger-overlay (redaction half) and fu-r01a-snapshot-copies: tenant 7 commits a row
//! (revision 1), archive 0 is saved, the tenant is erased and redacted (its record loses the content), then a
//! replacing restore of archive 0 runs. The histories agree (same head, same revision id), so even the reviewed
//! prefix check lets it through; the pin writes the archive's rows and records with no live redaction re-applied:
//! the tenant's row and its record are back. The answer is not an L1 step and L1's invariant fails.
use vstd::prelude::*;
use actors::protocol::*;
use crate::snap_l1::*;
use crate::snap_l2::*;
use crate::snap_runs::*;

verus! {

pub open spec fn none() -> Set<Item> { Set::empty() }
pub open spec fn u4() -> SS2 {
    SS2 { g: G2 { led: Led { recs: redact_recs(t3().g.led.recs, 7), ..t3().g.led }, ..t3().g }, scope: t3().scope.insert(7), ..t3() }
}
pub open spec fn u_end() -> SS2 { re(u4(), 0, none()) }

pub proof fn counterexample_f1801_unredact()
    ensures
        init2(c0()),
        step2(c0(), SL2::Commit { items: set![i7()], id: 1 }, t1()),
        step2(t1(), SL2::XStart { id: 0 }, sv(t1(), 0, 0)),
        step2(sv(t1(), 0, 0), SL2::XRead, sv(t1(), 0, 1)),
        step2(sv(t1(), 0, 1), SL2::XRead, sv(t1(), 0, 2)),
        step2(sv(t1(), 0, 2), SL2::XRead, sv(t1(), 0, 3)),
        step2(sv(t1(), 0, 3), SL2::XRead, sv(t1(), 0, 4)),
        step2(sv(t1(), 0, 4), SL2::XLedger, svl(t1(), 0)),
        step2(svl(t1(), 0), SL2::XEnd { id: 0, lines: read_upto(t1().cur, 4), g: t1().g }, t2()),
        step2(t2(), SL2::Erase { ten: 7 }, t3()),
        step2(t3(), SL2::Redact { ten: 7, oor: set![0nat] }, u4()),
        step2(u4(), SL2::RBegin { id: 0 }, rb(u4(), 0)),
        step2(rb(u4(), 0), SL2::RLoad { bad: none() }, rl(u4(), 0, none())),
        step2(rl(u4(), 0, none()), SL2::RLedger, rg(u4(), 0, none())),
        step2(rg(u4(), 0, none()), SL2::REnd { id: 0, failed: none() }, u_end()),
        // the restore's answer is not an L1 step: it brings back content a live redaction removed
        !step_or_stutter::<SnapL1>(abs18(rg(u4(), 0, none())), lab18(SL2::REnd { id: 0, failed: none() }), abs18(u_end())),
        u_end().rows.contains(i7()) && u_end().g.led.recs[1].contains(i7()) && u_end().scope.contains(7),
        !inv1(abs18(u_end())),
{
    lemma_tenant_run();
    lemma_save_run(t1(), 0);
    assert(not_ten(t3().cur, 7) =~= t3().cur);
    assert(t3().files.dom() =~= set![0nat]);
    assert(step2(t3(), SL2::Redact { ten: 7, oor: set![0nat] }, u4()));
    assert(u4().files[0].g == g1_of(set![i7()]));
    assert(u4().g.led.ids == g1_of(set![i7()]).led.ids);
    assert(prefix(u4().g.led, u4().files[0].g.led));
    lemma_restore_run(u4(), 0, none());
    assert(set![i7()].difference(none()) =~= set![i7()]);
    assert(u_end().rows.contains(i7()));
    let a1 = abs18(rg(u4(), 0, none()));
    assert(a1.red.contains(7));
    assert(!scrub(a1.archives[0].content.difference(none()), a1.red).contains(i7()));
    assert(abs18(u_end()).content.contains(i7()));
    assert(u_end().g.led.recs.contains_key(1) && u_end().g.led.recs[1] == set![i7()]);
}

} // verus!
