//! Proved counterexample for control `control_f1302_unlocked_start` (F-1302), compiled only with that feature.
//!
//! With Start checking without the lock and writing no marker, the composed participant contracts run, from the
//! initial state: a commit of tenant A's content; the erasure of A; a redaction of A opens and starts (no marker); a
//! commit re-creates A's content (nothing refuses it); the redaction's first batch tombstones A's record and only now
//! writes the marker. The tombstoned record's key is live: "no tombstone of live content" fails; A is live while
//! marked, so the run can never finish and commits into A are refused until A is erased again (F-1302's impact).
//! (Explorer counterexample `redaction-as-built-live`; live scenario `commit_in_unmarked_window`.)
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

pub open spec fn ca2() -> Content { Content { k: ka(), eff: Eff::Put(6) } }

pub open spec fn e0() -> BizS { w0() }
pub open spec fn e1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(e0().rl.l, seq![ca()], None), r: e0().rl.r }, st: store_apply(e0().st, seq![ca()]), ..e0() }
}
pub open spec fn e2() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..e1().rl.l }, r: e1().rl.r }, st: store_erase_rows(e1().st, tenant_a()),
           pend: e1().pend.insert(tenant_a()) }
}
pub open spec fn e3() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..e2().rl.l }, r: e2().rl.r }, st: store_erase_index(e2().st, tenant_a()), ..e2() }
}
pub open spec fn e4() -> BizS { BizS { rl: RLS { l: e3().rl.l, r: red_step(e3().rl.r, RedL::Open { p: 0, t: tenant_a() }) }, ..e3() } }
/// The as-built start: the process attaches (first record to the head) and no marker is written.
pub open spec fn e5() -> BizS {
    BizS { rl: RLS { l: e4().rl.l, r: red_step(e4().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: e4().pend.insert(tenant_a()), ..e4() }
}
pub open spec fn e6() -> BizS {
    BizS { rl: RLS { l: ledger_commit(e5().rl.l, seq![ca2()], None), r: e5().rl.r }, st: store_apply(e5().st, seq![ca2()]), ..e5() }
}
/// The first batch: tombstone record (0, 0), which writes the marker.
pub open spec fn e7() -> BizS {
    BizS { rl: RLS { l: ledger_batch(e6().rl.l, 0, 0, tenant_a(), true, 0, 1), r: red_step(e6().rl.r, RedL::Advance { p: 0, row_end: false }) },
           ..e6() }
}

pub proof fn counterexample_f1302()
    ensures
        Biz::init(e0()),
        sys_step(e0(), BizL::Commit { cs: seq![ca()], key: None }, e1()),
        sys_step(e1(), BizL::EraseRows { t: tenant_a() }, e2()),
        sys_step(e2(), BizL::EraseIndex { t: tenant_a() }, e3()),
        sys_step(e3(), BizL::Open { p: 0, t: tenant_a() }, e4()),
        sys_step(e4(), BizL::Start { p: 0, fresh: true }, e5()),
        sys_step(e5(), BizL::Commit { cs: seq![ca2()], key: None }, e6()),
        sys_step(e6(), BizL::Scan { p: 0 }, e7()),
        // A record is turned into a tombstone while its key is live ...
        e6().rl.l.hist[0][0] == Rec::Live(ca()) && e7().rl.l.hist[0][0] == Rec::Tomb(ca()),
        e6().st.rows.contains_key(ca().k) && e7().st.rows.contains_key(ca().k),
        // ... and the marker is written by that tombstone while A is live.
        e6().rl.l.marker is None && e7().rl.l.marker == Some(tenant_a()) && live_in(e7().st.rows, tenant_a()),
        !biz_inv(e7()),
{
    let t = tenant_a();
    let rs = lives(seq![ca()]);
    assert(rs.drop_last() =~= Seq::<Rec>::empty());
    assert(rs.last() == Rec::Live(ca()));
    let rs2 = lives(seq![ca2()]);
    assert(rs2.drop_last() =~= Seq::<Rec>::empty());
    assert(rs2.last() == Rec::Live(ca2()));
    assert(sys_step(e0(), BizL::Commit { cs: seq![ca()], key: None }, e1()));
    assert(sys_step(e1(), BizL::EraseRows { t }, e2()));
    assert(sys_step(e2(), BizL::EraseIndex { t }, e3()));
    assert(sys_step(e3(), BizL::Open { p: 0, t }, e4()));
    lemma_outside_not_live(e1().st.rows, t, t);
    assert(tgt_of(e4().rl.r, 0) == t);
    assert(e4().rl.l.hist.len() == 1);
    assert(sys_step(e4(), BizL::Start { p: 0, fresh: true }, e5()));
    assert(sys_step(e5(), BizL::Commit { cs: seq![ca2()], key: None }, e6()));
    assert(e6().rl.l.hist[0] == rs);
    assert(e6().rl.l.hist[0][0] == Rec::Live(ca()));
    assert(member(t, ka()));
    assert(hit(e6().rl.l, pcur(e6().rl.r, 0)));
    assert(sys_step(e6(), BizL::Scan { p: 0 }, e7()));
    assert(e6().st.rows.contains_key(ka()));
    assert(!mark_ok(e7()));
}

} // verus!
