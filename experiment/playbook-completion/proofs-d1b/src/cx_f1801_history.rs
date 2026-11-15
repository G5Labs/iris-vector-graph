//! Proved counterexample for control `control_f1801_no_prefix_check` (F-1801 history half, HD-1801), compiled only
//! with it.
//!
//! The live trace c18-live-ledger-overlay / ib-HD1801-merge-restore: revision 1 is committed, archive 0 is saved at
//! head 1, revision 2 is committed, then a replacing restore of archive 0 runs (the pin checks layout, strict mode and
//! a caller transaction only, snapshot.py:1095-1129) and sets the archive's ledger nodes over the live ones
//! (snapshot.py:1654-1692): head goes back to 1 while revision 2's id, record and LedgerRevisionD row survive. The
//! restore's answer is not an L1 step (no prefix), L1's invariant fails (one history), and the next commit is refused
//! by the IdKey on LedgerRevision.Seq: the ledger is wedged.
use vstd::prelude::*;
use actors::protocol::*;
use crate::snap_l1::*;
use crate::snap_l2::*;
use crate::snap_runs::*;

verus! {

pub open spec fn none() -> Set<Item> { Set::empty() }
pub open spec fn h1() -> SS2 { c_commit(c0(), none(), 1) }
pub open spec fn h2() -> SS2 { sve(h1(), 0) }
pub open spec fn h3() -> SS2 { c_commit(h2(), none(), 2) }
pub open spec fn h_end() -> SS2 { re(h3(), 0, none()) }

pub proof fn counterexample_f1801_history()
    ensures
        init2(c0()),
        step2(c0(), SL2::Commit { items: none(), id: 1 }, h1()),
        step2(h1(), SL2::XStart { id: 0 }, sv(h1(), 0, 0)),
        step2(sv(h1(), 0, 0), SL2::XRead, sv(h1(), 0, 1)),
        step2(sv(h1(), 0, 1), SL2::XRead, sv(h1(), 0, 2)),
        step2(sv(h1(), 0, 2), SL2::XRead, sv(h1(), 0, 3)),
        step2(sv(h1(), 0, 3), SL2::XRead, sv(h1(), 0, 4)),
        step2(sv(h1(), 0, 4), SL2::XLedger, svl(h1(), 0)),
        step2(svl(h1(), 0), SL2::XEnd { id: 0, lines: read_upto(h1().cur, 4), g: h1().g }, h2()),
        step2(h2(), SL2::Commit { items: none(), id: 2 }, h3()),
        step2(h3(), SL2::RBegin { id: 0 }, rb(h3(), 0)),
        step2(rb(h3(), 0), SL2::RLoad { bad: none() }, rl(h3(), 0, none())),
        step2(rl(h3(), 0, none()), SL2::RLedger, rg(h3(), 0, none())),
        step2(rg(h3(), 0, none()), SL2::REnd { id: 0, failed: none() }, h_end()),
        // the restore's answer is not an L1 step: the live history (head 2) is not a prefix of the archive's (head 1)
        !step_or_stutter::<SnapL1>(abs18(rg(h3(), 0, none())), lab18(SL2::REnd { id: 0, failed: none() }), abs18(h_end())),
        h3().g.led.head == 2 && h_end().g.led.head == 1 && h_end().g.led.ids.contains_key(2) && h_end().g.rev.contains(2),
        !inv1(abs18(h_end())),
        // the wedge: the next commit's revision row exists, so it is refused (and so is every later one)
        step2(h_end(), SL2::CommitRefused { items: none(), id: 3 }, h_end()),
{
    lemma_c0();
    lemma_commit_run(c0(), none(), 1);
    lemma_save_run(h1(), 0);
    assert(!h2().g.rev.contains(2));
    lemma_commit_run(h2(), none(), 2);
    assert(h3().files.contains_key(0));
    assert(h3().files[0].g == h1().g);
    lemma_restore_run(h3(), 0, none());
    let a1 = abs18(rg(h3(), 0, none()));
    assert(a1.archives.contains_key(0) && a1.archives[0].led.head == 1);
    assert(a1.led.head == 2);
    assert(!prefix(a1.led, a1.archives[0].led));
    assert(h_end().g.led.ids.contains_key(2));
    assert(!wf(abs18(h_end()).led));
}

} // verus!
