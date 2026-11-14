//! Non-vacuity of the readers' protocol (D-9b), concrete executions of RdOuter from its initial state, each step
//! checked against `rd_next` and keeping `rd_inv`:
//! - `witness_reader_accepts`: a commit; a reader begins, reads the revision and returns it (Accept is reachable);
//! - `witness_reader_refuses`: two commits of tenant A; a reader begins and reads revision 0; a whole redaction of A
//!   runs (open, start, four scan steps, final) — the marker is absent again when the reader reads revision 1 —; the
//!   reviewed reader **refuses** because the epoch moved (sharpness: core `m3-readers-sharp-epoch-refusal`).
//! The states are shared with the readers' counterexample (`cx_reader`).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::redactor::*;
use crate::reader::*;
use crate::protocol_rl::*;
use crate::protocol_rd::*;
use crate::witness::*;

verus! {

pub open spec fn ka2() -> Key { Key { g: 1, id: 2, edge: false } }
pub open spec fn ca3() -> Content { Content { k: ka2(), eff: Eff::Put(8) } }

pub open spec fn r0() -> RdS { RdS { rl: w0().rl, rd: ReaderS { rd: Map::empty() } } }
pub open spec fn r1() -> RdS { RdS { rl: RLS { l: ledger_commit(r0().rl.l, seq![ca()], keys(seq![ca()]), None), r: r0().rl.r }, ..r0() } }
pub open spec fn r2() -> RdS { RdS { rl: RLS { l: ledger_commit(r1().rl.l, seq![ca3()], keys(seq![ca3()]), None), r: r1().rl.r }, ..r1() } }
pub open spec fn r3() -> RdS { RdS { rd: reader_step(r2().rd, ReaderL::Begin { q: 0, e0: r2().rl.l.epoch }), ..r2() } }
pub open spec fn r4() -> RdS { RdS { rd: reader_step(r3().rd, ReaderL::Page { q: 0, rs: r3().rl.l.hist[0] }), ..r3() } }
pub open spec fn r5() -> RdS { RdS { rl: RLS { l: r4().rl.l, r: red_step(r4().rl.r, RedL::Open { p: 0, t: t_a() }) }, ..r4() } }
pub open spec fn r6() -> RdS {
    RdS { rl: RLS { l: ledger_mark(r5().rl.l, t_a()), r: red_step(r5().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 2 }) }, ..r5() }
}
pub open spec fn r7() -> RdS {
    RdS { rl: RLS { l: ledger_batch(r6().rl.l, 0, 0, t_a(), true, 0, 1), r: red_step(r6().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..r6() }
}
pub open spec fn r8() -> RdS {
    RdS { rl: RLS { l: ledger_batch(r7().rl.l, 0, 1, t_a(), false, 1, 0), r: red_step(r7().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..r7() }
}
pub open spec fn r9() -> RdS {
    RdS { rl: RLS { l: ledger_batch(r8().rl.l, 1, 0, t_a(), true, 1, 1), r: red_step(r8().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..r8() }
}
pub open spec fn r10() -> RdS {
    RdS { rl: RLS { l: ledger_batch(r9().rl.l, 1, 1, t_a(), false, 2, 0), r: red_step(r9().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..r9() }
}
pub open spec fn r11() -> RdS { RdS { rl: RLS { l: r10().rl.l, r: red_step(r10().rl.r, RedL::ToFinal { p: 0 }) }, ..r10() } }
pub open spec fn r12() -> RdS { RdS { rl: RLS { l: ledger_audit(r11().rl.l, t_a()), r: red_step(r11().rl.r, RedL::Finish { p: 0 }) }, ..r11() } }
pub open spec fn r13() -> RdS { RdS { rd: reader_step(r12().rd, ReaderL::Page { q: 0, rs: r12().rl.l.hist[1] }), ..r12() } }
pub open spec fn r14() -> RdS { RdS { rd: reader_step(r13().rd, ReaderL::Refuse { q: 0 }), ..r13() } }

/// The reviewed steps of the redaction-inside-a-read run (r0 to r13).
pub proof fn lemma_rd_run()
    ensures
        RdOuter::init(r0()),
        rd_next(r0(), RdL::Ledger { x: RLL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None } }, r1()),
        rd_next(r1(), RdL::Ledger { x: RLL::Commit { cs: seq![ca3()], named: keys(seq![ca3()]), key: None } }, r2()),
        rd_next(r2(), RdL::Begin { q: 0 }, r3()),
        rd_next(r3(), RdL::Page { q: 0 }, r4()),
        rd_next(r4(), RdL::Ledger { x: RLL::Open { p: 0, t: t_a() } }, r5()),
        rd_next(r5(), RdL::Ledger { x: RLL::Start { p: 0, fresh: true } }, r6()),
        rd_next(r6(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r7()),
        rd_next(r7(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r8()),
        rd_next(r8(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r9()),
        rd_next(r9(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r10()),
        rd_next(r10(), RdL::Ledger { x: RLL::ToFinal { p: 0 } }, r11()),
        rd_next(r11(), RdL::Ledger { x: RLL::Final { p: 0, ok: true } }, r12()),
        rd_next(r12(), RdL::Page { q: 0 }, r13()),
        // the reader saw no marker when it began and sees none now; a whole redaction ran in between
        r3().rl.l.marker is None && r13().rl.l.marker is None && r3().rd.rd[0].e0 == 0 && r13().rl.l.epoch == 2,
        r13().rd.rd[0].e0 == 0 && r13().rd.rd[0].view.len() == 2,
        // its view: revision 0 as before the redaction, revision 1 as after it
        r13().rd.rd[0].view[0] == r3().rl.l.hist[0] && r13().rd.rd[0].view[0] == seq![Rec::Live(ca())],
        r13().rl.l.hist[0] == seq![Rec::Tomb(ca())],
        r13().rd.rd[0].view[1] == r13().rl.l.hist[1] && r13().rd.rd[0].view[1] == seq![Rec::Tomb(ca3())],
        r3().rl.l.hist[1] == seq![Rec::Live(ca3())],
{
    lemma_keys(seq![ca()]);
    lemma_keys(seq![ca3()]);
    let h1 = lives(seq![ca()]);
    let h2 = lives(seq![ca3()]);
    assert(h1 =~= seq![Rec::Live(ca())]);
    assert(h2 =~= seq![Rec::Live(ca3())]);
    assert(rd_next(r0(), RdL::Ledger { x: RLL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None } }, r1()));
    assert(rd_next(r1(), RdL::Ledger { x: RLL::Commit { cs: seq![ca3()], named: keys(seq![ca3()]), key: None } }, r2()));
    assert(r2().rl.l.hist =~= seq![h1, h2]);
    assert(rd_next(r2(), RdL::Begin { q: 0 }, r3()));
    assert(r3().rd.rd[0].view.len() == 0);
    assert(rd_next(r3(), RdL::Page { q: 0 }, r4()));
    assert(rd_next(r4(), RdL::Ledger { x: RLL::Open { p: 0, t: t_a() } }, r5()));
    assert(tgt_of(r5().rl.r, 0) == t_a());
    assert(r5().rl.l.hist.len() == 2);
    assert(rd_next(r5(), RdL::Ledger { x: RLL::Start { p: 0, fresh: true } }, r6()));
    let c6 = pcur(r6().rl.r, 0);
    assert(c6 == Cur { t: dom_a(), i: 0, j: 0, end: 2 });
    assert(r6().rl.l.hist[0][0] == Rec::Live(ca()));
    assert(hit(r6().rl.l, c6));
    assert(rd_next(r6(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r7()));
    assert(row_end(r7().rl.l, pcur(r7().rl.r, 0)));
    assert(rd_next(r7(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r8()));
    let c8 = pcur(r8().rl.r, 0);
    assert(c8 == Cur { t: dom_a(), i: 1, j: 0, end: 2 });
    assert(r8().rl.l.hist[1] == h2);
    assert(r8().rl.l.hist[1][0] == Rec::Live(ca3()));
    assert(hit(r8().rl.l, c8));
    assert(rd_next(r8(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r9()));
    assert(row_end(r9().rl.l, pcur(r9().rl.r, 0)));
    assert(rd_next(r9(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r10()));
    assert(rd_next(r10(), RdL::Ledger { x: RLL::ToFinal { p: 0 } }, r11()));
    assert(tgt_of(r11().rl.r, 0) == t_a());
    assert(rd_next(r11(), RdL::Ledger { x: RLL::Final { p: 0, ok: true } }, r12()));
    assert(r12().rd == r4().rd);
    assert(r12().rd.rd[0].view.len() == 1);
    assert(r12().rl.l.hist.len() == 3);
    assert(rd_next(r12(), RdL::Page { q: 0 }, r13()));
    assert(r7().rl.l.hist[0] =~= seq![Rec::Tomb(ca())]);
    assert(r9().rl.l.hist[1] =~= seq![Rec::Tomb(ca3())]);
    assert(r12().rl.l.hist[0] == r7().rl.l.hist[0]);
    assert(r12().rl.l.hist[1] == r9().rl.l.hist[1]);
    assert(r13().rd.rd[0].view =~= seq![h1, r12().rl.l.hist[1]]);
}

/// **The reviewed reader refuses** a view a whole redaction ran inside (the epoch moved; the marker is absent).
pub proof fn witness_reader_refuses()
    ensures
        rd_next(r13(), RdL::Refuse { q: 0 }, r14()),
        !accept_ok(r13().rl.l, r13().rd, 0),
        forall|x: RdS| !rd_next(r13(), RdL::Accept { q: 0 }, x),
        rd_inv(r13()) && rd_inv(r14()),
{
    lemma_rd_run();
    <RdOuter as SafeContract>::init_safe(r0());
    lemma_rd_safe(r0(), RdL::Ledger { x: RLL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None } }, r1());
    lemma_rd_safe(r1(), RdL::Ledger { x: RLL::Commit { cs: seq![ca3()], named: keys(seq![ca3()]), key: None } }, r2());
    lemma_rd_safe(r2(), RdL::Begin { q: 0 }, r3());
    lemma_rd_safe(r3(), RdL::Page { q: 0 }, r4());
    lemma_rd_safe(r4(), RdL::Ledger { x: RLL::Open { p: 0, t: t_a() } }, r5());
    lemma_rd_safe(r5(), RdL::Ledger { x: RLL::Start { p: 0, fresh: true } }, r6());
    lemma_rd_safe(r6(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r7());
    lemma_rd_safe(r7(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r8());
    lemma_rd_safe(r8(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r9());
    lemma_rd_safe(r9(), RdL::Ledger { x: RLL::Scan { p: 0 } }, r10());
    lemma_rd_safe(r10(), RdL::Ledger { x: RLL::ToFinal { p: 0 } }, r11());
    lemma_rd_safe(r11(), RdL::Ledger { x: RLL::Final { p: 0, ok: true } }, r12());
    lemma_rd_safe(r12(), RdL::Page { q: 0 }, r13());
    assert(rd_next(r13(), RdL::Refuse { q: 0 }, r14()));
    lemma_rd_safe(r13(), RdL::Refuse { q: 0 }, r14());
}

pub open spec fn a3() -> RdS { RdS { rd: reader_step(r1().rd, ReaderL::Begin { q: 0, e0: r1().rl.l.epoch }), ..r1() } }
pub open spec fn a4() -> RdS { RdS { rd: reader_step(a3().rd, ReaderL::Page { q: 0, rs: a3().rl.l.hist[0] }), ..a3() } }
pub open spec fn a5() -> RdS { RdS { rd: reader_step(a4().rd, ReaderL::Accept { q: 0 }), ..a4() } }

/// A reader with no redaction during its read returns its view, which is the history.
pub proof fn witness_reader_accepts()
    ensures
        rd_next(r1(), RdL::Begin { q: 0 }, a3()),
        rd_next(a3(), RdL::Page { q: 0 }, a4()),
        rd_next(a4(), RdL::Accept { q: 0 }, a5()),
        a4().rd.rd[0].view =~= a4().rl.l.hist,
{
    lemma_rd_run();
    assert(rd_next(r1(), RdL::Begin { q: 0 }, a3()));
    assert(rd_next(a3(), RdL::Page { q: 0 }, a4()));
    assert(rd_next(a4(), RdL::Accept { q: 0 }, a5()));
    assert(a4().rl.l.hist.len() == 1);
}

} // verus!
