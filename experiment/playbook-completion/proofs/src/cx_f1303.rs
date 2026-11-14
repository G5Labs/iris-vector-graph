//! Proved counterexample for control `control_f1303_other_marker` (F-1303), compiled only with that feature.
//!
//! With Final running under whatever marker exists, the composed participant contracts run, from the initial state:
//! tenant B's content is committed and erased; process 0 redacts A (nothing of A to tombstone) to its final step;
//! process 2 re-runs A and also reaches its final step; process 0 finishes A (no marker now); process 1 starts B
//! (B's marker) and tombstones B's record; then process 2's final step runs under **B's** marker: it writes an audit
//! revision naming A and counting B's tombstone, and removes B's marker while B's run is still in progress (so
//! commits into B are no longer refused). The audit is misattributed and the marker is not its owner's.
//! (Explorer counterexample `redaction-as-built-audit`; live scenario `two_targets_at_once`.)
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

pub open spec fn ta() -> Tgt { tenant_a() }
pub open spec fn tb() -> Tgt { tenant_b() }

pub open spec fn f0() -> BizS { w0() }
pub open spec fn f1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(f0().rl.l, seq![cb()], None), r: f0().rl.r }, st: store_apply(f0().st, seq![cb()]), ..f0() }
}
pub open spec fn f2() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..f1().rl.l }, r: f1().rl.r }, st: store_erase_rows(f1().st, tb()), pend: f1().pend.insert(tb()) }
}
pub open spec fn f3() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..f2().rl.l }, r: f2().rl.r }, st: store_erase_index(f2().st, tb()), ..f2() }
}
pub open spec fn f4() -> BizS { BizS { rl: RLS { l: f3().rl.l, r: red_step(f3().rl.r, RedL::Open { p: 0, t: ta() }) }, ..f3() } }
pub open spec fn f5() -> BizS {
    BizS { rl: RLS { l: ledger_mark(f4().rl.l, ta()), r: red_step(f4().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: f4().pend.insert(ta()), ..f4() }
}
pub open spec fn f6() -> BizS {
    BizS { rl: RLS { l: ledger_batch(f5().rl.l, 0, 0, ta(), false, 0, 1), r: red_step(f5().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..f5() }
}
pub open spec fn f7() -> BizS {
    BizS { rl: RLS { l: ledger_batch(f6().rl.l, 0, 1, ta(), false, 1, 0), r: red_step(f6().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..f6() }
}
pub open spec fn f8() -> BizS { BizS { rl: RLS { l: f7().rl.l, r: red_step(f7().rl.r, RedL::ToFinal { p: 0 }) }, ..f7() } }
pub open spec fn f9() -> BizS { BizS { rl: RLS { l: f8().rl.l, r: red_step(f8().rl.r, RedL::Open { p: 2, t: ta() }) }, ..f8() } }
pub open spec fn f10() -> BizS { BizS { rl: RLS { l: f9().rl.l, r: red_step(f9().rl.r, RedL::Attach { p: 2, i: 1, j: 0, end: 1 }) }, ..f9() } }
pub open spec fn f11() -> BizS { BizS { rl: RLS { l: f10().rl.l, r: red_step(f10().rl.r, RedL::ToFinal { p: 2 }) }, ..f10() } }
pub open spec fn f12() -> BizS {
    BizS { rl: RLS { l: ledger_audit(f11().rl.l, ta()), r: red_step(f11().rl.r, RedL::Finish { p: 0 }) }, st: f11().st, pend: f11().pend.remove(ta()) }
}
pub open spec fn f13() -> BizS { BizS { rl: RLS { l: f12().rl.l, r: red_step(f12().rl.r, RedL::Open { p: 1, t: tb() }) }, ..f12() } }
pub open spec fn f14() -> BizS {
    BizS { rl: RLS { l: ledger_mark(f13().rl.l, tb()), r: red_step(f13().rl.r, RedL::Attach { p: 1, i: 0, j: 0, end: 1 }) },
           pend: f13().pend.insert(tb()), ..f13() }
}
pub open spec fn f15() -> BizS {
    BizS { rl: RLS { l: ledger_batch(f14().rl.l, 0, 0, tb(), true, 0, 1), r: red_step(f14().rl.r, RedL::Advance { p: 1, row_end: false }) }, ..f14() }
}
pub open spec fn f16() -> BizS {
    BizS { rl: RLS { l: ledger_audit(f15().rl.l, ta()), r: red_step(f15().rl.r, RedL::Finish { p: 2 }) }, st: f15().st, pend: f15().pend.remove(ta()) }
}

pub proof fn counterexample_f1303()
    ensures
        Biz::init(f0()),
        sys_step(f0(), BizL::Commit { cs: seq![cb()], key: None }, f1()),
        sys_step(f1(), BizL::EraseRows { t: tb() }, f2()),
        sys_step(f2(), BizL::EraseIndex { t: tb() }, f3()),
        sys_step(f3(), BizL::Open { p: 0, t: ta() }, f4()),
        sys_step(f4(), BizL::Start { p: 0, fresh: true }, f5()),
        sys_step(f5(), BizL::Scan { p: 0 }, f6()),
        sys_step(f6(), BizL::Scan { p: 0 }, f7()),
        sys_step(f7(), BizL::ToFinal { p: 0 }, f8()),
        sys_step(f8(), BizL::Open { p: 2, t: ta() }, f9()),
        sys_step(f9(), BizL::Start { p: 2, fresh: false }, f10()),
        sys_step(f10(), BizL::ToFinal { p: 2 }, f11()),
        sys_step(f11(), BizL::Final { p: 0, ok: true }, f12()),
        sys_step(f12(), BizL::Open { p: 1, t: tb() }, f13()),
        sys_step(f13(), BizL::Start { p: 1, fresh: true }, f14()),
        sys_step(f14(), BizL::Scan { p: 1 }, f15()),
        sys_step(f15(), BizL::Final { p: 2, ok: true }, f16()),
        // process 2 (target A) runs its final step under B's marker ...
        ta() != tb() && tgt_of(f15().rl.r, 2) == ta() && f15().rl.l.marker == Some(tb()),
        // ... its audit names A and counts the one tombstone of the tally, a record of B ...
        f15().rl.l.tally == seq![cb()] && member(tb(), cb().k) && !member(ta(), cb().k),
        f16().rl.l.hist == f15().rl.l.hist.push(seq![Rec::Audit { t: ta(), n: 1 }]),
        // ... and it removes B's marker while B's run is in progress.
        f16().rl.l.marker is None && has_phase(f16().rl.r, 1, Phase::Batches) && tgt_of(f16().rl.r, 1) == tb()
            && f16().pend.contains(tb()),
{
    assert(ta()(kb()) != tb()(kb()));
    assert(ta() != tb());
    let rs = lives(seq![cb()]);
    assert(rs.drop_last() =~= Seq::<Rec>::empty());
    assert(rs.last() == Rec::Live(cb()));
    assert(sys_step(f0(), BizL::Commit { cs: seq![cb()], key: None }, f1()));
    assert(replay_recs(Map::<Key, int>::empty(), rs.drop_last()) == Map::<Key, int>::empty());
    assert(f1().st.rows =~= Map::<Key, int>::empty().insert(kb(), 7));
    assert(sys_step(f1(), BizL::EraseRows { t: tb() }, f2()));
    assert(f2().st.rows =~= Map::<Key, int>::empty()) by {
        assert forall|k: Key| !#[trigger] f2().st.rows.contains_key(k) by {
            if f2().st.rows.contains_key(k) { assert(f1().st.rows.contains_key(k)); assert(k == kb()); }
        }
    }
    assert(sys_step(f2(), BizL::EraseIndex { t: tb() }, f3()));
    assert(sys_step(f3(), BizL::Open { p: 0, t: ta() }, f4()));
    assert(tgt_of(f4().rl.r, 0) == ta());
    assert(f4().rl.l.hist.len() == 1);
    assert(sys_step(f4(), BizL::Start { p: 0, fresh: true }, f5()));
    assert(f5().rl.l.hist[0] == rs);
    assert(!member(ta(), kb()));
    assert(!hit(f5().rl.l, pcur(f5().rl.r, 0)));
    assert(sys_step(f5(), BizL::Scan { p: 0 }, f6()));
    assert(row_end(f6().rl.l, pcur(f6().rl.r, 0)));
    assert(sys_step(f6(), BizL::Scan { p: 0 }, f7()));
    assert(sys_step(f7(), BizL::ToFinal { p: 0 }, f8()));
    assert(sys_step(f8(), BizL::Open { p: 2, t: ta() }, f9()));
    assert(tgt_of(f9().rl.r, 2) == ta());
    assert(sys_step(f9(), BizL::Start { p: 2, fresh: false }, f10()));
    assert(sys_step(f10(), BizL::ToFinal { p: 2 }, f11()));
    assert(tgt_of(f11().rl.r, 0) == ta());
    assert(sys_step(f11(), BizL::Final { p: 0, ok: true }, f12()));
    assert(sys_step(f12(), BizL::Open { p: 1, t: tb() }, f13()));
    assert(tgt_of(f13().rl.r, 1) == tb());
    assert(sys_step(f13(), BizL::Start { p: 1, fresh: true }, f14()));
    assert(f14().rl.l.hist[0] == rs);
    assert(member(tb(), kb()));
    assert(hit(f14().rl.l, pcur(f14().rl.r, 1)));
    assert(sys_step(f14(), BizL::Scan { p: 1 }, f15()));
    assert(f15().rl.l.tally =~= seq![cb()]);
    assert(tgt_of(f15().rl.r, 2) == ta());
    assert(sys_step(f15(), BizL::Final { p: 2, ok: true }, f16()));
    assert(f16().pend.contains(tb()));
}

} // verus!
