//! Proved counterexample for control `control_fc1304_receipt_omits_archives` (F-C1304, receipt), compiled only with
//! it.
//!
//! The live trace fu-r01a-snapshot-copies: tenant 7 commits a row, archive 0 is saved, the tenant is erased and then
//! redacted. The receipt's out_of_reach names exports, journals and backups only (LedgerRedact.cls:504-509), while
//! archive 0 still holds the tenant's row and record. The redaction is not an L1 step.
use vstd::prelude::*;
use actors::protocol::*;
use crate::snap_l1::*;
use crate::snap_l2::*;
use crate::snap_runs::*;

verus! {

pub open spec fn v4() -> SS2 {
    SS2 { g: G2 { led: Led { recs: redact_recs(t3().g.led.recs, 7), ..t3().g.led }, ..t3().g }, scope: t3().scope.insert(7), ..t3() }
}

pub proof fn counterexample_fc1304()
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
        step2(t3(), SL2::Redact { ten: 7, oor: Set::empty() }, v4()),
        holds(abs18(t3()).archives[0], 7),
        !step_or_stutter::<SnapL1>(abs18(t3()), lab18(SL2::Redact { ten: 7, oor: Set::empty() }), abs18(v4())),
{
    lemma_tenant_run();
    lemma_save_run(t1(), 0);
    assert(not_ten(t3().cur, 7) =~= t3().cur);
    assert(step2(t3(), SL2::Redact { ten: 7, oor: Set::empty() }, v4()));
    let a1 = abs18(t3());
    assert(a1.archives.contains_key(0) && a1.archives[0].content == set![i7()]);
    assert(a1.archives[0].content.contains(i7()));
    assert(holds(a1.archives[0], 7));
}

} // verus!
