//! Proved counterexample for controls `control_f1402_reader_no_recheck` (F-1402, as built: client.py:720-728, then a
//! lazy paged read, replay.py:231-269) and `control_reader_marker_recheck_only` (HD-1401 alternative (b1)), compiled
//! only with either feature.
//!
//! The composed participant contracts (`protocol_rd::rd_sys_step`, as either control changes them) run, from the
//! initial state: two commits of tenant A; a reader finds no marker and reads revision 0; a whole redaction of A runs
//! and finishes; the reader reads revision 1 — the marker is absent again — and returns its view. The view holds
//! revision 0 as before the redaction and revision 1 as after it: it is neither the history when the read began nor
//! the history when it ended (RPL-I1 fails: `theorem_accepted_view_consistent`'s conclusion is false at this Accept).
//! A post-read marker re-check passes (no marker at either end), so (b1) does not detect it; only the epoch does
//! (live `ib-HD1401-reader-full-race`; core `m3-readers-as-built-F1402`, `m3-readers-control-no-epoch`).
use vstd::prelude::*;
use actors::protocol::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::reader::*;
use crate::protocol_rl::*;
use crate::protocol_rd::*;
use crate::witness::*;
use crate::witness_rd::*;

verus! {

pub open spec fn r14a() -> RdS { RdS { rd: reader_step(r13().rd, ReaderL::Accept { q: 0 }), ..r13() } }

pub proof fn counterexample_reader_half_redacted()
    ensures
        RdOuter::init(r0()),
        rd_sys_step(r0(), RdL::Ledger { x: RLL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None } }, r1()),
        rd_sys_step(r1(), RdL::Ledger { x: RLL::Commit { cs: seq![ca3()], named: keys(seq![ca3()]), key: None } }, r2()),
        rd_sys_step(r2(), RdL::Begin { q: 0 }, r3()),
        rd_sys_step(r3(), RdL::Page { q: 0 }, r4()),
        rd_sys_step(r4(), RdL::Ledger { x: RLL::Open { p: 0, t: t_a() } }, r5()),
        rd_sys_step(r5(), RdL::Ledger { x: RLL::Start { p: 0, fresh: true } }, r6()),
        rd_sys_step(r6(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r7()),
        rd_sys_step(r7(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r8()),
        rd_sys_step(r8(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r9()),
        rd_sys_step(r9(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r10()),
        rd_sys_step(r10(), RdL::Ledger { x: RLL::ToFinal { p: 0 } }, r11()),
        rd_sys_step(r11(), RdL::Ledger { x: RLL::Final { p: 0, ok: true } }, r12()),
        rd_sys_step(r12(), RdL::Page { q: 0 }, r13()),
        rd_sys_step(r13(), RdL::Accept { q: 0 }, r14a()),
        // the returned view: revision 0 before the redaction, revision 1 after it ...
        r13().rd.rd[0].view[0] == r3().rl.l.hist[0] && r13().rd.rd[0].view[0] != r13().rl.l.hist[0],
        r13().rd.rd[0].view[1] == r13().rl.l.hist[1] && r13().rd.rd[0].view[1] != r3().rl.l.hist[1],
        // ... with no marker when the read began nor when it ended (a marker re-check passes); the epoch moved.
        r3().rl.l.marker is None && r13().rl.l.marker is None && r13().rl.l.epoch != r13().rd.rd[0].e0,
{
    lemma_rd_run();
    lemma_rd_enabled(r0().rl, r0().rd, RdL::Ledger { x: RLL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None } }, r1());
    lemma_rd_enabled(r1().rl, r1().rd, RdL::Ledger { x: RLL::Commit { cs: seq![ca3()], named: keys(seq![ca3()]), key: None } }, r2());
    lemma_rd_enabled(r2().rl, r2().rd, RdL::Begin { q: 0 }, r3());
    lemma_rd_enabled(r3().rl, r3().rd, RdL::Page { q: 0 }, r4());
    lemma_rd_enabled(r4().rl, r4().rd, RdL::Ledger { x: RLL::Open { p: 0, t: t_a() } }, r5());
    lemma_rd_enabled(r5().rl, r5().rd, RdL::Ledger { x: RLL::Start { p: 0, fresh: true } }, r6());
    lemma_rd_enabled(r6().rl, r6().rd, RdL::Ledger { x: RLL::Scan { p: 0 } }, r7());
    lemma_rd_enabled(r7().rl, r7().rd, RdL::Ledger { x: RLL::Scan { p: 0 } }, r8());
    lemma_rd_enabled(r8().rl, r8().rd, RdL::Ledger { x: RLL::Scan { p: 0 } }, r9());
    lemma_rd_enabled(r9().rl, r9().rd, RdL::Ledger { x: RLL::Scan { p: 0 } }, r10());
    lemma_rd_enabled(r10().rl, r10().rd, RdL::Ledger { x: RLL::ToFinal { p: 0 } }, r11());
    lemma_rd_enabled(r11().rl, r11().rd, RdL::Ledger { x: RLL::Final { p: 0, ok: true } }, r12());
    lemma_rd_enabled(r12().rl, r12().rd, RdL::Page { q: 0 }, r13());
    assert(r13().rd.rd.contains_key(0));
    assert(rd_sys_step(r13(), RdL::Accept { q: 0 }, r14a()));
    assert(seq![Rec::Live(ca())][0] != seq![Rec::Tomb(ca())][0]);
    assert(seq![Rec::Tomb(ca3())][0] != seq![Rec::Live(ca3())][0]);
}

} // verus!
