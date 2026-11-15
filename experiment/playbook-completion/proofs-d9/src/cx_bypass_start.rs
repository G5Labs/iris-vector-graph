//! Proved counterexample for control `control_bypass_start` (F-C1301), compiled only with that feature.
//!
//! With Start not waiting for open ledger-bypassing transactions (as at the pin: no writer takes a lock the redaction
//! takes), the composed participant contracts (`system::sys_step`) run, from the initial state: a ledger commit of
//! tenant A's edge; a bypass transaction deletes that row (open, visible at once: E-VIS); a redaction of A opens and
//! starts — its liveness check sees A empty — and marks A; its first batch tombstones the edge's record; the bypass
//! transaction rolls back (E-ROLLBACK-OTHER / E-STOP) and the edge is live again with its history tombstoned. The
//! tombstoned record's key held recorded content in the committed view when the batch ran: "no tombstone of live
//! content" fails, and so do the business invariants. (Core model `m2-reviewed-bypass-nonserializing`, 4 steps.)
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

pub open spec fn b1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![ca()], None), r: w0().rl.r }, st: store_apply(w0().st, seq![ca()]), ..w0() }
}
pub open spec fn b2() -> BizS {
    BizS { st: store_write(b1().st, ka(), None), wr: WrS { open: b1().wr.open.insert(ka(), BTx { before: Some(5), was: false }) }, ..b1() }
}
pub open spec fn b3() -> BizS { BizS { rl: RLS { l: b2().rl.l, r: red_step(b2().rl.r, RedL::Open { p: 0, t: t_a() }) }, ..b2() } }
pub open spec fn b4() -> BizS {
    BizS { rl: RLS { l: ledger_mark(b3().rl.l, t_a()), r: red_step(b3().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: b3().pend.insert(dom_a()), ..b3() }
}
pub open spec fn b5() -> BizS {
    BizS { rl: RLS { l: ledger_batch(b4().rl.l, 0, 0, t_a(), true, 0, 1), r: red_step(b4().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..b4() }
}
pub open spec fn b6() -> BizS {
    BizS { st: store_undo(b5().st, ka(), Some(5), false), wr: WrS { open: b5().wr.open.remove(ka()) }, ..b5() }
}

pub proof fn counterexample_bypass_start()
    ensures
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![ca()], key: None }, b1()),
        sys_step(b1(), BizL::BBegin { k: ka(), v: None }, b2()),
        sys_step(b2(), BizL::Open { p: 0, t: t_a() }, b3()),
        sys_step(b3(), BizL::Start { p: 0, fresh: true }, b4()),
        sys_step(b4(), BizL::Scan { p: 0 }, b5()),
        sys_step(b5(), BizL::BAbort { k: ka() }, b6()),
        // Start ran while the bypass delete was open, and marked A while A's edge was committed content ...
        b3().wr.open.contains_key(ka()) && b4().rl.l.marker == Some(t_a()) && crow(b4(), ka()) == Some(5int) && !cunrec(b4(), ka()),
        // ... the batch tombstoned its record while the key held recorded content ...
        b4().rl.l.hist[0][0] == Rec::Live(ca()) && b5().rl.l.hist[0][0] == Rec::Tomb(ca()) && rec_content(b4(), ka()),
        // ... and after the rollback the content is live, recorded, with its history tombstoned.
        b6().st.rows.contains_key(ka()) && !b6().st.unrec.contains(ka()) && b6().rl.l.hist[0][0] == Rec::Tomb(ca()),
        no_open(b6().wr) && b6().st.erasing is None,
        !biz_inv(b4()), !biz_inv(b6()),
{
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, ca());
    lemma_one(Map::<Key, int>::empty(), Set::<Key>::empty(), Set::<Key>::empty(), ca());
    assert(b1().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5));
    assert(sys_step(w0(), BizL::Commit { cs: seq![ca()], key: None }, b1()));
    assert(oget(b1().st.rows, ka()) == Some(5int));
    assert(!b1().st.unrec.contains(ka()));
    assert(sys_step(b1(), BizL::BBegin { k: ka(), v: None }, b2()));
    assert(sys_step(b2(), BizL::Open { p: 0, t: t_a() }, b3()));
    assert(b3().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(b3().st.rows, t_a().lv));
    assert(tgt_of(b3().rl.r, 0) == t_a());
    assert(b3().rl.l.hist.len() == 1);
    assert(sys_step(b3(), BizL::Start { p: 0, fresh: true }, b4()));
    let c4 = pcur(b4().rl.r, 0);
    assert(c4 == Cur { t: dom_a(), i: 0, j: 0, end: 1 });
    assert(b4().rl.l.hist[0][0] == Rec::Live(ca()));
    assert(hit(b4().rl.l, c4));
    assert(sys_step(b4(), BizL::Scan { p: 0 }, b5()));
    assert(b5().wr.open[ka()] == BTx { before: Some(5), was: false });
    assert(sys_step(b5(), BizL::BAbort { k: ka() }, b6()));
    assert(b5().rl.l.hist[0][0] == Rec::Tomb(ca()));
    assert(member(t_a().rm, ka()));
    assert(!mark_key_ok(b4(), ka()));
    assert(!key_ok(b4(), ka()));
    assert(b6().wr.open =~= Map::<Key, BTx>::empty());
    assert(crow(b6(), ka()) == Some(5int));
    assert(!mark_key_ok(b6(), ka()));
    assert(!key_ok(b6(), ka()));
}

} // verus!
