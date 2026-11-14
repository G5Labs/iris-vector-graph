//! Proved counterexample for control `control_f1350_bypass_ignores_marker` (F-C1350, live: `ws-live-ins-store_node`
//! and eleven sibling runs), compiled only with that feature.
//!
//! As built no non-ledger writer reads `^IVG.Ledger("redacting")` (only BlocksCommit does, for ledger commits,
//! LedgerRedact.cls:258-269), and BatchInLock tombstones without re-checking liveness (LedgerRedact.cls:302-330). The
//! composed participant contracts (`system::sys_step`, as the control changes them) run, from the initial state: a
//! ledger commit of tenant A's edge; the erasure of A (rows, statement cleanup, commit); a redaction of A opens and
//! starts — nothing of A is live, so its entry check passes and it marks A; a ledger-bypassing writer writes A's row
//! again and commits (unrecorded content, live and committed); the first batch tombstones the edge's record while its
//! key holds that content; the run reaches its final step, which can only be **refused** ("became live again",
//! LedgerRedact.cls:409-416), and the marker stays (F-C1307). RED-B1.1/FR-005 read as the product's own checks read
//! them (any content row of the target is live) fail: the strengthened `theorem_no_tombstone_of_live` is violated,
//! and the business invariants fail from the bypass write on (C4).
use vstd::prelude::*;
use actors::protocol::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
use crate::writer::*;
use crate::protocol_rl::*;
use crate::biz::*;
use crate::system::*;
use crate::witness::*;

verus! {

pub open spec fn c1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![ca()], keys(seq![ca()]), None), r: w0().rl.r }, st: store_apply(w0().st, seq![ca()]), ..w0() }
}
pub open spec fn c2() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..c1().rl.l }, r: c1().rl.r }, st: store_erase_rows(c1().st, dom_a()), ..c1() }
}
pub open spec fn c3() -> BizS { BizS { st: store_erase_index(c2().st), ..c2() } }
pub open spec fn c4() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..c3().rl.l }, r: c3().rl.r }, st: store_erase_commit(c3().st),
           pend: c3().pend.insert(dom_a()), ..c3() }
}
pub open spec fn c5() -> BizS { BizS { rl: RLS { l: c4().rl.l, r: red_step(c4().rl.r, RedL::Open { p: 0, t: t_a() }) }, ..c4() } }
pub open spec fn c6() -> BizS {
    BizS { rl: RLS { l: ledger_mark(c5().rl.l, t_a()), r: red_step(c5().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: c5().pend.insert(dom_a()), ..c5() }
}
/// The bypass writer re-creates A's row (it reads no marker).
pub open spec fn c7() -> BizS {
    BizS { st: store_write(c6().st, ka(), Some(9)), wr: WrS { open: c6().wr.open.insert(ka(), BTx { before: None, was: false }) }, ..c6() }
}
pub open spec fn c8() -> BizS { BizS { wr: WrS { open: c7().wr.open.remove(ka()) }, ..c7() } }
pub open spec fn c9() -> BizS {
    BizS { rl: RLS { l: ledger_batch(c8().rl.l, 0, 0, t_a(), true, 0, 1), r: red_step(c8().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..c8() }
}
pub open spec fn c10() -> BizS {
    BizS { rl: RLS { l: ledger_batch(c9().rl.l, 0, 1, t_a(), false, 1, 0), r: red_step(c9().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..c9() }
}
pub open spec fn c11() -> BizS { BizS { rl: RLS { l: c10().rl.l, r: red_step(c10().rl.r, RedL::ToFinal { p: 0 }) }, ..c10() } }
/// The final step is refused: the target is live again; the marker stays.
pub open spec fn c12() -> BizS { BizS { rl: RLS { l: c11().rl.l, r: red_step(c11().rl.r, RedL::Finish { p: 0 }) }, ..c11() } }

pub proof fn counterexample_f1350()
    ensures
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None }, c1()),
        sys_step(c1(), BizL::EraseRows { e: dom_a() }, c2()),
        sys_step(c2(), BizL::EraseIndex, c3()),
        sys_step(c3(), BizL::EraseCommit, c4()),
        sys_step(c4(), BizL::Open { p: 0, t: t_a() }, c5()),
        sys_step(c5(), BizL::Start { p: 0, fresh: true }, c6()),
        sys_step(c6(), BizL::BBegin { k: ka(), v: Some(9) }, c7()),
        sys_step(c7(), BizL::BCommit { k: ka() }, c8()),
        sys_step(c8(), BizL::Scan { p: 0 }, c9()),
        sys_step(c9(), BizL::Scan { p: 0 }, c10()),
        sys_step(c10(), BizL::ToFinal { p: 0 }, c11()),
        sys_step(c11(), BizL::Final { p: 0, ok: false }, c12()),
        // the entry check saw A empty and marked it; the writer then made A's row live and committed, unrecorded ...
        !live_in(c5().st.rows, t_a().lv) && c6().rl.l.marker == Some(t_a()),
        c8().st.rows.contains_key(ka()) && c8().st.unrec.contains(ka()) && no_open(c8().wr),
        // ... the batch tombstones the record of a key that holds content (the strengthened theorem fails) ...
        c8().rl.l.hist[0][0] == Rec::Live(ca()) && c9().rl.l.hist[0][0] == Rec::Tomb(ca()),
        any_content(c8(), ka()) && any_content(c9(), ka()),
        // ... and the run cannot finish: its final step can only be refused, and the marker stays (F-C1307).
        forall|y: BizS| !#[trigger] sys_step(c11(), BizL::Final { p: 0, ok: true }, y),
        c12().rl.l.marker == Some(t_a()),
        !biz_inv(c7()), !biz_inv(c9()),
{
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, ca());
    assert(c1().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5));
    assert(sys_step(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None }, c1()));
    assert(sys_step(c1(), BizL::EraseRows { e: dom_a() }, c2()));
    assert(c2().st.rows =~= Map::<Key, int>::empty()) by {
        assert forall|k: Key| !#[trigger] c2().st.rows.contains_key(k) by {
            if c2().st.rows.contains_key(k) { assert(c1().st.rows.contains_key(k)); assert(k == ka()); }
        }
    }
    assert(sys_step(c2(), BizL::EraseIndex, c3()));
    assert(sys_step(c3(), BizL::EraseCommit, c4()));
    assert(sys_step(c4(), BizL::Open { p: 0, t: t_a() }, c5()));
    assert(c5().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(c5().st.rows, t_a().lv));
    assert(tgt_of(c5().rl.r, 0) == t_a());
    assert(aligned(t_a()));
    assert(c5().rl.l.hist.len() == 1);
    assert(sys_step(c5(), BizL::Start { p: 0, fresh: true }, c6()));
    assert(oget(c6().st.rows, ka()) is None && !c6().st.unrec.contains(ka()));
    assert(sys_step(c6(), BizL::BBegin { k: ka(), v: Some(9) }, c7()));
    assert(sys_step(c7(), BizL::BCommit { k: ka() }, c8()));
    assert(c8().wr.open =~= Map::<Key, BTx>::empty());
    let c8c = pcur(c8().rl.r, 0);
    assert(c8c == Cur { t: dom_a(), i: 0, j: 0, end: 1 });
    assert(c8().rl.l.hist[0] == lives(seq![ca()]));
    assert(c8().rl.l.hist[0][0] == Rec::Live(ca()));
    assert(hit(c8().rl.l, c8c));
    assert(sys_step(c8(), BizL::Scan { p: 0 }, c9()));
    assert(row_end(c9().rl.l, pcur(c9().rl.r, 0)));
    assert(sys_step(c9(), BizL::Scan { p: 0 }, c10()));
    assert(sys_step(c10(), BizL::ToFinal { p: 0 }, c11()));
    assert(tgt_of(c11().rl.r, 0) == t_a());
    assert(c11().st.rows.contains_key(ka()) && member(t_a().lv, ka()));
    assert(live_in(c11().st.rows, t_a().lv));
    assert(sys_step(c11(), BizL::Final { p: 0, ok: false }, c12()));
    assert forall|y: BizS| !#[trigger] sys_step(c11(), BizL::Final { p: 0, ok: true }, y) by {}
    assert(c7().rl.l.marker == Some(t_a()) && member(t_a().rm, ka()) && c7().st.rows.contains_key(ka()));
    assert(!mark_key_all(c7(), ka()));
    assert(!key_ok(c7(), ka()));
    assert(!mark_key_all(c9(), ka()));
    assert(!key_ok(c9(), ka()));
}

} // verus!
