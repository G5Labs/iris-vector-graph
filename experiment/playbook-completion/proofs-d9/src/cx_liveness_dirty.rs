//! Proved counterexample for control `control_liveness_dirty` (F-C1201), compiled only with that feature.
//!
//! With the liveness check made when the redaction is called, without the head lock, on the rows other processes see
//! (as the pin's LiveRows, LedgerRedact.cls:206-210), the composed participant contracts run, from the initial state:
//! a ledger commit of tenant A's edge; an erasure of A deletes A's rows and holds the head lock (its transaction open,
//! e.g. erase_graph inside a caller transaction); a redaction of A is called and its check sees A empty; the erasure
//! rolls back (A's edge is back) and releases the lock; the redaction's locked Start marks A — A holds recorded
//! content while marked — and its first batch tombstones the edge's record while the edge is live. (Live on the pin:
//! `ib-HD1201-open-erasure`; core model `m2-as-built-P1311-erase-rollback`.)
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

pub open spec fn d1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![ca()], None), r: w0().rl.r }, st: store_apply(w0().st, seq![ca()]), ..w0() }
}
pub open spec fn d2() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..d1().rl.l }, r: d1().rl.r }, st: store_erase_rows(d1().st, dom_a()), ..d1() }
}
pub open spec fn d3() -> BizS { BizS { rl: RLS { l: d2().rl.l, r: red_step(d2().rl.r, RedL::Open { p: 0, t: t_a() }) }, ..d2() } }
pub open spec fn d4() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..d3().rl.l }, r: d3().rl.r }, st: store_erase_abort(d3().st), ..d3() }
}
pub open spec fn d5() -> BizS {
    BizS { rl: RLS { l: ledger_mark(d4().rl.l, t_a()), r: red_step(d4().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: d4().pend.insert(dom_a()), ..d4() }
}
pub open spec fn d6() -> BizS {
    BizS { rl: RLS { l: ledger_batch(d5().rl.l, 0, 0, t_a(), true, 0, 1), r: red_step(d5().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..d5() }
}

pub proof fn counterexample_liveness_dirty()
    ensures
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![ca()], key: None }, d1()),
        sys_step(d1(), BizL::EraseRows { e: dom_a() }, d2()),
        sys_step(d2(), BizL::Open { p: 0, t: t_a() }, d3()),
        sys_step(d3(), BizL::EraseAbort, d4()),
        sys_step(d4(), BizL::Start { p: 0, fresh: true }, d5()),
        sys_step(d5(), BizL::Scan { p: 0 }, d6()),
        // the check saw an open erasure's uncommitted deletes ...
        d2().st.erasing is Some && !live_in(d2().st.rows, t_a().lv),
        // ... which rolled back: A's edge is recorded content again when A is marked ...
        d5().rl.l.marker == Some(t_a()) && d5().st.rows.contains_key(ka()) && !d5().st.unrec.contains(ka()),
        // ... and the batch tombstones its record while it is live.
        d5().rl.l.hist[0][0] == Rec::Live(ca()) && d6().rl.l.hist[0][0] == Rec::Tomb(ca()),
        rec_content(d5(), ka()) && rec_content(d6(), ka()) && d6().st.erasing is None,
        !biz_inv(d5()), !biz_inv(d6()),
{
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, ca());
    assert(d1().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5));
    assert(sys_step(w0(), BizL::Commit { cs: seq![ca()], key: None }, d1()));
    assert(sys_step(d1(), BizL::EraseRows { e: dom_a() }, d2()));
    assert(d2().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(d2().st.rows, t_a().lv));
    assert(sys_step(d2(), BizL::Open { p: 0, t: t_a() }, d3()));
    assert(sys_step(d3(), BizL::EraseAbort, d4()));
    assert(d4().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5));
    assert(tgt_of(d4().rl.r, 0) == t_a());
    assert(d4().rl.l.hist.len() == 1);
    assert(sys_step(d4(), BizL::Start { p: 0, fresh: true }, d5()));
    let c5 = pcur(d5().rl.r, 0);
    assert(c5 == Cur { t: dom_a(), i: 0, j: 0, end: 1 });
    assert(d5().rl.l.hist[0][0] == Rec::Live(ca()));
    assert(hit(d5().rl.l, c5));
    assert(sys_step(d5(), BizL::Scan { p: 0 }, d6()));
    assert(d6().rl.l.hist[0][0] == Rec::Tomb(ca()));
    assert(member(t_a().rm, ka()));
    assert(crow(d5(), ka()) == Some(5int));
    assert(!mark_key_ok(d5(), ka()));
    assert(!key_ok(d5(), ka()));
    assert(crow(d6(), ka()) == Some(5int));
    assert(!mark_key_ok(d6(), ka()));
    assert(!key_ok(d6(), ka()));
}

} // verus!
