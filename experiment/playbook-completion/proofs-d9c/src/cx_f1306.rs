//! Proved counterexample for control `control_f1306_replay_direct_sql` (F-1306, live `ib-HD1305-retry-revives`,
//! `live-native-rerun-1314`), compiled only with that feature. D-9c re-encoding (review R4-03): `proofs-d9b` modelled
//! the replayed post-commit properties as recorded content (a store Apply); the pin writes them **by direct SQL without
//! a ledger record** (client.py:445-481, after the ledger answered the replay at Ledger.cls:457-462, before its marker
//! check at 514-518), so here the replay is followed by a Writer step that reads no marker.
//!
//! From the initial state: a commit of tenant A's content with retry key 9; the erasure of A; a redaction of A opens
//! and marks A; the client retries with key 9, the ledger answers the replay and the client writes A's property row
//! again by direct SQL and commits (unrecorded content in the marked target); the first batch tombstones A's record
//! while its key holds that content. The run's final step can then only be refused (target live): the run is stuck
//! while the marker refuses ordinary commits (the live probe's "during a run" case). Between an erasure and the
//! redaction (no marker) the same write is a permitted unrecorded write in this model: Start is then refused
//! (target_live), which is a progress effect, not a safety violation here.
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
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![ca()], keys(seq![ca()]), Some(9)), r: w0().rl.r }, st: store_apply(w0().st, seq![ca()]), ..w0() }
}
pub open spec fn d2() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..d1().rl.l }, r: d1().rl.r }, st: store_erase_rows(d1().st, dom_a()), ..d1() }
}
pub open spec fn d3() -> BizS { BizS { st: store_erase_index(d2().st), ..d2() } }
pub open spec fn d4() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..d3().rl.l }, r: d3().rl.r }, st: store_erase_commit(d3().st),
           pend: d3().pend.insert(dom_a()), ..d3() }
}
pub open spec fn d5() -> BizS { BizS { rl: RLS { l: d4().rl.l, r: red_step(d4().rl.r, RedL::Open { p: 0, t: t_a() }) }, ..d4() } }
pub open spec fn d6() -> BizS {
    BizS { rl: RLS { l: ledger_mark(d5().rl.l, t_a()), r: red_step(d5().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: d5().pend.insert(dom_a()), ..d5() }
}
/// The replay of key 9: the ledger answers from the stored revision; the client writes the property row by direct SQL.
pub open spec fn d7() -> BizS {
    BizS { st: store_write(d6().st, ka(), Some(5)), wr: WrS { open: d6().wr.open.insert(ka(), BTx { before: None, was: false }) }, ..d6() }
}
/// ... and that write commits (its own transaction).
pub open spec fn d8() -> BizS { BizS { wr: WrS { open: d7().wr.open.remove(ka()) }, ..d7() } }
pub open spec fn d9() -> BizS {
    BizS { rl: RLS { l: ledger_batch(d8().rl.l, 0, 0, t_a(), true, 0, 1), r: red_step(d8().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..d8() }
}

pub proof fn counterexample_f1306()
    ensures
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: Some(9) }, d1()),
        sys_step(d1(), BizL::EraseRows { e: dom_a() }, d2()),
        sys_step(d2(), BizL::EraseIndex, d3()),
        sys_step(d3(), BizL::EraseCommit, d4()),
        sys_step(d4(), BizL::Open { p: 0, t: t_a() }, d5()),
        sys_step(d5(), BizL::Start { p: 0, fresh: true }, d6()),
        sys_step(d6(), BizL::Replay { key: 9, props: seq![ca()] }, d7()),
        sys_step(d7(), BizL::BCommit { k: ka() }, d8()),
        sys_step(d8(), BizL::Scan { p: 0 }, d9()),
        // the replay changed no ledger state but wrote A's row, unrecorded, into the marked target ...
        d7().rl == d6().rl && d6().rl.l.marker == Some(t_a()) && !live_in(d6().st.rows, t_a().lv),
        d8().st.rows.contains_key(ka()) && d8().st.unrec.contains(ka()) && live_in(d8().st.rows, t_a().lv),
        // ... and the batch tombstones A's record while its key holds that content.
        d8().rl.l.hist[0][0] == Rec::Live(ca()) && d9().rl.l.hist[0][0] == Rec::Tomb(ca()) && any_content(d8(), ka()),
        !biz_inv(d7()), !biz_inv(d8()),
{
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, ca());
    assert(d1().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5));
    assert(sys_step(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: Some(9) }, d1()));
    assert(d1().rl.l.idem.contains_key(9));
    assert(sys_step(d1(), BizL::EraseRows { e: dom_a() }, d2()));
    assert(d2().st.rows =~= Map::<Key, int>::empty()) by {
        assert forall|k: Key| !#[trigger] d2().st.rows.contains_key(k) by {
            if d2().st.rows.contains_key(k) { assert(d1().st.rows.contains_key(k)); assert(k == ka()); }
        }
    }
    assert(sys_step(d2(), BizL::EraseIndex, d3()));
    assert(sys_step(d3(), BizL::EraseCommit, d4()));
    assert(sys_step(d4(), BizL::Open { p: 0, t: t_a() }, d5()));
    assert(d5().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(d5().st.rows, t_a().lv));
    assert(tgt_of(d5().rl.r, 0) == t_a());
    assert(aligned(t_a()));
    assert(sys_step(d5(), BizL::Start { p: 0, fresh: true }, d6()));
    assert(d6().rl.l.idem.contains_key(9));
    assert(oget(d6().st.rows, ka()) is None && !d6().st.unrec.contains(ka()));
    assert(seq![ca()][0] == ca());
    assert(sys_step(d6(), BizL::Replay { key: 9, props: seq![ca()] }, d7()));
    assert(sys_step(d7(), BizL::BCommit { k: ka() }, d8()));
    assert(d8().wr.open =~= Map::<Key, BTx>::empty());
    assert(member(t_a().lv, ka()));
    let c8 = pcur(d8().rl.r, 0);
    assert(c8 == Cur { t: dom_a(), i: 0, j: 0, end: 1 });
    assert(d8().rl.l.hist[0] == lives(seq![ca()]));
    assert(d8().rl.l.hist[0][0] == Rec::Live(ca()));
    assert(hit(d8().rl.l, c8));
    assert(sys_step(d8(), BizL::Scan { p: 0 }, d9()));
    assert(!mark_key_all(d7(), ka()));
    assert(!key_ok(d7(), ka()));
    assert(!mark_key_all(d8(), ka()));
    assert(!key_ok(d8(), ka()));
}

} // verus!
