//! Proved counterexample for control `control_f1306_replay_reapplies` (F-1306), compiled only with that feature.
//!
//! With a replayed retry re-applying its post-commit properties, the composed participant contracts run, from the
//! initial state: a commit of tenant A's content with retry key 9; the erasure of A; a redaction of A opens and marks
//! A; the client retries with key 9 and the replay writes A's content again. A is live while marked: no tombstone of
//! A can be written safely, the run's final step can only be refused (target_live), and the business invariants fail.
//! (Explorer counterexample `retry-as-built`; live scenario `retry_between_erase_and_redact` in the original
//! submission.)
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

pub open spec fn d0() -> BizS { w0() }
pub open spec fn d1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(d0().rl.l, seq![ca()], Some(9)), r: d0().rl.r }, st: store_apply(d0().st, seq![ca()]), ..d0() }
}
pub open spec fn d2() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..d1().rl.l }, r: d1().rl.r }, st: store_erase_rows(d1().st, tenant_a()),
           pend: d1().pend.insert(tenant_a()) }
}
pub open spec fn d3() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..d2().rl.l }, r: d2().rl.r }, st: store_erase_index(d2().st, tenant_a()), ..d2() }
}
pub open spec fn d4() -> BizS { BizS { rl: RLS { l: d3().rl.l, r: red_step(d3().rl.r, RedL::Open { p: 0, t: tenant_a() }) }, ..d3() } }
pub open spec fn d5() -> BizS {
    BizS {
        rl: RLS { l: ledger_mark(d4().rl.l, tenant_a()), r: red_step(d4().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
        pend: d4().pend.insert(tenant_a()), ..d4()
    }
}
pub open spec fn d6() -> BizS { BizS { st: store_apply(d5().st, seq![ca()]), ..d5() } }

pub proof fn counterexample_f1306()
    ensures
        Biz::init(d0()),
        sys_step(d0(), BizL::Commit { cs: seq![ca()], key: Some(9) }, d1()),
        sys_step(d1(), BizL::EraseRows { t: tenant_a() }, d2()),
        sys_step(d2(), BizL::EraseIndex { t: tenant_a() }, d3()),
        sys_step(d3(), BizL::Open { p: 0, t: tenant_a() }, d4()),
        sys_step(d4(), BizL::Start { p: 0, fresh: true }, d5()),
        sys_step(d5(), BizL::Replay { key: 9, props: seq![ca()] }, d6()),
        d6().rl.l.marker == Some(tenant_a()) && live_in(d6().st.rows, tenant_a()),
        !biz_inv(d6()),
{
    let t = tenant_a();
    let rs = lives(seq![ca()]);
    assert(rs.drop_last() =~= Seq::<Rec>::empty());
    assert(rs.last() == Rec::Live(ca()));
    assert(sys_step(d0(), BizL::Commit { cs: seq![ca()], key: Some(9) }, d1()));
    assert(d1().rl.l.idem.contains_key(9));
    assert(sys_step(d1(), BizL::EraseRows { t }, d2()));
    assert(sys_step(d2(), BizL::EraseIndex { t }, d3()));
    assert(sys_step(d3(), BizL::Open { p: 0, t }, d4()));
    lemma_outside_not_live(d1().st.rows, t, t);
    assert(tgt_of(d4().rl.r, 0) == t);
    assert(d4().rl.l.hist.len() == 1);
    assert(sys_step(d4(), BizL::Start { p: 0, fresh: true }, d5()));
    assert(sys_step(d5(), BizL::Replay { key: 9, props: seq![ca()] }, d6()));
    assert(d6().st.rows.contains_key(ka()) && member(t, ka()));
    assert(!mark_ok(d6()));
}

} // verus!
