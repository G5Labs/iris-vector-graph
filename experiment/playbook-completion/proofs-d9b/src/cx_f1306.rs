//! Proved counterexample for control `control_f1306_replay_reapplies` (F-1306, re-run in this crate), compiled only
//! with that feature.
//!
//! With a replayed retry re-applying the post-commit properties its client sends (client.py:430-435; the ledger answers
//! the replay at Ledger.cls:457-462, before the marker check at 514-518), the composed participant contracts run, from
//! the initial state: a commit of tenant A's content with retry key 9; the erasure of A; a redaction of A opens and
//! marks A; the client retries with key 9 and the replay writes A's content again. A holds recorded content while
//! marked: no tombstone of A can be written safely, the run's final step can only be refused (target_live), and the
//! business invariants fail. (`proofs/` `counterexample_f1306`; explorer `retry-as-built`; live
//! `live-native-rerun-1314`, `ib-HD1305-retry-revives`.)
use vstd::prelude::*;
use actors::protocol::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
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
/// The replay of key 9 re-applies its post-commit content.
pub open spec fn d7() -> BizS { BizS { st: store_apply(d6().st, seq![ca()]), ..d6() } }

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
        d6().rl.l.marker == Some(t_a()) && !live_in(d6().st.rows, t_a().lv),
        d7().rl.l.marker == Some(t_a()) && live_in(d7().st.rows, t_a().lv) && rec_content(d7(), ka()),
        !biz_inv(d7()),
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
    assert(sys_step(d6(), BizL::Replay { key: 9, props: seq![ca()] }, d7()));
    lemma_one(d6().st.rows, d6().st.stmts, d6().st.unrec, ca());
    assert(d7().st.rows.contains_key(ka()) && !d7().st.unrec.contains(ka()));
    assert(member(t_a().lv, ka()));
    assert(crow(d7(), ka()) == Some(5int));
    assert(!mark_key_ok(d7(), ka()));
    assert(!key_ok(d7(), ka()));
}

} // verus!
