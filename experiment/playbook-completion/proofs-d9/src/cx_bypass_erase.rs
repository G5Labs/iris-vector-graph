//! Proved counterexample for control `control_bypass_erase`, compiled only with that feature.
//!
//! With the eraser not waiting for open bypass transactions on its target, the composed participant contracts run,
//! from the initial state: a ledger commit of tenant A's edge (row and statement entry); a bypass transaction deletes
//! the row (open); the erasure of A deletes A's rows (the bypass-deleted row is not visible to its DELETE, so its
//! undo log does not hold it), kills A's statement entries including the edge's, and commits; the bypass transaction
//! rolls back and the edge's row is back — recorded content — with no statement entry and no erasure open:
//! "statement entries match live edges" fails (ADR-0004: "no live statement outlives its content", here its converse).
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

pub open spec fn e1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![ca()], None), r: w0().rl.r }, st: store_apply(w0().st, seq![ca()]), ..w0() }
}
pub open spec fn e2() -> BizS {
    BizS { st: store_write(e1().st, ka(), None), wr: WrS { open: e1().wr.open.insert(ka(), BTx { before: Some(5), was: false }) }, ..e1() }
}
pub open spec fn e3() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..e2().rl.l }, r: e2().rl.r }, st: store_erase_rows(e2().st, dom_a()), ..e2() }
}
pub open spec fn e4() -> BizS { BizS { st: store_erase_index(e3().st), ..e3() } }
pub open spec fn e5() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..e4().rl.l }, r: e4().rl.r }, st: store_erase_commit(e4().st),
           pend: e4().pend.insert(dom_a()), ..e4() }
}
pub open spec fn e6() -> BizS {
    BizS { st: store_undo(e5().st, ka(), Some(5), false), wr: WrS { open: e5().wr.open.remove(ka()) }, ..e5() }
}

pub proof fn counterexample_bypass_erase()
    ensures
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![ca()], key: None }, e1()),
        sys_step(e1(), BizL::BBegin { k: ka(), v: None }, e2()),
        sys_step(e2(), BizL::EraseRows { e: dom_a() }, e3()),
        sys_step(e3(), BizL::EraseIndex, e4()),
        sys_step(e4(), BizL::EraseCommit, e5()),
        sys_step(e5(), BizL::BAbort { k: ka() }, e6()),
        // the erasure ran while the bypass transaction on its target's row was open
        e2().wr.open.contains_key(ka()) && member(dom_a(), ka()),
        // after the rollback: a live edge with recorded content and no statement entry, no erasure open
        ka().edge && e6().st.rows.contains_key(ka()) && !e6().st.stmts.contains(ka()) && !e6().st.unrec.contains(ka()),
        e6().st.erasing is None && no_open(e6().wr),
        !biz_inv(e5()), !biz_inv(e6()),
{
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, ca());
    assert(e1().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5));
    assert(e1().st.stmts =~= Set::<Key>::empty().insert(ka()));
    assert(sys_step(w0(), BizL::Commit { cs: seq![ca()], key: None }, e1()));
    assert(oget(e1().st.rows, ka()) == Some(5int));
    assert(!e1().st.unrec.contains(ka()));
    assert(sys_step(e1(), BizL::BBegin { k: ka(), v: None }, e2()));
    assert(sys_step(e2(), BizL::EraseRows { e: dom_a() }, e3()));
    assert(sys_step(e3(), BizL::EraseIndex, e4()));
    assert(!e4().st.stmts.contains(ka()));
    assert(sys_step(e4(), BizL::EraseCommit, e5()));
    assert(e5().wr.open[ka()] == BTx { before: Some(5), was: false });
    assert(sys_step(e5(), BizL::BAbort { k: ka() }, e6()));
    assert(!c_stmt_ok(e5(), ka()));
    assert(!key_ok(e5(), ka()));
    assert(e6().wr.open =~= Map::<Key, BTx>::empty());
    assert(!c_stmt_ok(e6(), ka()));
    assert(!key_ok(e6(), ka()));
}

} // verus!
