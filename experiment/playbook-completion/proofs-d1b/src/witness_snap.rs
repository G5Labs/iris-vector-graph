//! Non-vacuity of the module 18 reviewed model (compiled without module 18 controls): a concrete run of the L2 step
//! relation from its initial state in which tenant 7 commits a row, archive 0 is saved under the export gate, the
//! tenant is erased and redacted (the receipt names archive 0), archive 0 is restored with the redaction re-applied
//! (the row and its record stay out), the ledger commits on (no wedge), and a restore of the now older archive is
//! refused before any write. Every step is an L1 step or a stutter (`snap_l2::theorem_raw_executions_refine`).
use vstd::prelude::*;
use crate::snap_l1::*;
use crate::snap_l2::*;
use crate::snap_runs::*;

verus! {

pub open spec fn none() -> Set<Item> { Set::empty() }
pub open spec fn j8() -> Item { (0, 8, 1) }
pub open spec fn w4() -> SS2 {
    SS2 { g: G2 { led: Led { recs: redact_recs(t3().g.led.recs, 7), ..t3().g.led }, ..t3().g }, scope: t3().scope.insert(7), ..t3() }
}
pub open spec fn w5() -> SS2 { re(w4(), 0, none()) }
pub open spec fn w6() -> SS2 { c_commit(w5(), set![j8()], 2) }

pub proof fn witness_snap()
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
        t2().files[0].lines == set![i7()],
        step2(t2(), SL2::Erase { ten: 7 }, t3()),
        step2(t3(), SL2::Redact { ten: 7, oor: set![0nat] }, w4()),
        step2(w4(), SL2::RBegin { id: 0 }, rb(w4(), 0)),
        step2(rb(w4(), 0), SL2::RLoad { bad: none() }, rl(w4(), 0, none())),
        step2(rl(w4(), 0, none()), SL2::RLedger, rg(w4(), 0, none())),
        step2(rg(w4(), 0, none()), SL2::REnd { id: 0, failed: none() }, w5()),
        // the restore kept the live redaction: neither the row nor its record came back
        !w5().rows.contains(i7()) && w5().g.led.head == 1 && !w5().g.led.recs[1].contains(i7()),
        // the ledger commits on
        step2(w5(), SL2::Commit { items: set![j8()], id: 2 }, w6()),
        w6().g.led.head == 2 && w6().rows.contains(j8()),
        // a restore of the older archive is refused before any write
        step2(w6(), SL2::RRefuse { id: 0 }, w6()),
        forall|t: SS2| !step2(w6(), SL2::RBegin { id: 0 }, t),
{
    lemma_tenant_run();
    lemma_save_run(t1(), 0);
    assert(not_ten(t3().cur, 7) =~= t3().cur);
    assert(t3().files.dom() =~= set![0nat]);
    assert(step2(t3(), SL2::Redact { ten: 7, oor: set![0nat] }, w4()));
    assert(w4().files[0].g == g1_of(set![i7()]));
    assert(prefix(w4().g.led, w4().files[0].g.led));
    lemma_restore_run(w4(), 0, none());
    assert(set![i7()].difference(none()) =~= set![i7()]);
    assert(!scrub(set![i7()], set![7]).contains(i7()));
    assert(w5().g.led.recs.contains_key(1));
    assert(w5().g.led.recs[1] == scrub(set![i7()], w4().scope));
    assert(w5().rows =~= none()) by { assert(w4().scope == set![7]); }
    assert(w5().cur =~= none());
    assert(!w5().g.rev.contains(2));
    lemma_commit_run(w5(), set![j8()], 2);
    assert(w6().files.contains_key(0));
    assert(w6().files[0].g.led.head == 1);
    assert(!prefix(w6().g.led, w6().files[0].g.led));
}

} // verus!
