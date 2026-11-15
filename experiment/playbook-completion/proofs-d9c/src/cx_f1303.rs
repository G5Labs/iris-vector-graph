//! Proved counterexample for control `control_f1303_other_marker` (F-1303, re-run in this crate), compiled only with
//! that feature.
//!
//! With Final running under whatever marker exists (FinalInLock re-checks only its own target's liveness and removes
//! whichever marker exists, LedgerRedact.cls:409-441), the composed participant contracts run, from the initial state:
//! tenant B's node is committed and erased; process 0 redacts A (nothing of A to tombstone) to its final step;
//! process 2 re-runs A and also reaches its final step; process 0 finishes A (no marker now); process 1 starts B
//! (B's marker) and tombstones B's record; then process 2's final step runs under **B's** marker: it writes an audit
//! revision naming A that counts B's tombstone, and removes B's marker while B's run is still in progress (so commits
//! into B are no longer refused). (`proofs/` `counterexample_f1303`; explorer `redaction-as-built-audit`; live
//! `live-native-rerun-1314`.)
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

pub open spec fn f1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![cb()], keys(seq![cb()]), None), r: w0().rl.r }, st: store_apply(w0().st, seq![cb()]), ..w0() }
}
pub open spec fn f2() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..f1().rl.l }, r: f1().rl.r }, st: store_erase_rows(f1().st, dom_b()), ..f1() }
}
pub open spec fn f3() -> BizS { BizS { st: store_erase_index(f2().st), ..f2() } }
pub open spec fn f4() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..f3().rl.l }, r: f3().rl.r }, st: store_erase_commit(f3().st),
           pend: f3().pend.insert(dom_b()), ..f3() }
}
pub open spec fn f5() -> BizS { BizS { rl: RLS { l: f4().rl.l, r: red_step(f4().rl.r, RedL::Open { p: 0, t: t_a() }) }, ..f4() } }
pub open spec fn f6() -> BizS {
    BizS { rl: RLS { l: ledger_mark(f5().rl.l, t_a()), r: red_step(f5().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: f5().pend.insert(dom_a()), ..f5() }
}
pub open spec fn f7() -> BizS {
    BizS { rl: RLS { l: ledger_batch(f6().rl.l, 0, 0, t_a(), false, 0, 1), r: red_step(f6().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..f6() }
}
pub open spec fn f8() -> BizS {
    BizS { rl: RLS { l: ledger_batch(f7().rl.l, 0, 1, t_a(), false, 1, 0), r: red_step(f7().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..f7() }
}
pub open spec fn f9() -> BizS { BizS { rl: RLS { l: f8().rl.l, r: red_step(f8().rl.r, RedL::ToFinal { p: 0 }) }, ..f8() } }
pub open spec fn f10() -> BizS { BizS { rl: RLS { l: f9().rl.l, r: red_step(f9().rl.r, RedL::Open { p: 2, t: t_a() }) }, ..f9() } }
pub open spec fn f11() -> BizS { BizS { rl: RLS { l: f10().rl.l, r: red_step(f10().rl.r, RedL::Attach { p: 2, i: 1, j: 0, end: 1 }) }, ..f10() } }
pub open spec fn f12() -> BizS { BizS { rl: RLS { l: f11().rl.l, r: red_step(f11().rl.r, RedL::ToFinal { p: 2 }) }, ..f11() } }
pub open spec fn f13() -> BizS {
    BizS { rl: RLS { l: ledger_audit(f12().rl.l, t_a()), r: red_step(f12().rl.r, RedL::Finish { p: 0 }) },
           st: store_drop(f12().st, t_a().sc), pend: f12().pend.filter(|d: Dom| !covers(t_a().rm, d)), wr: f12().wr }
}
pub open spec fn f14() -> BizS { BizS { rl: RLS { l: f13().rl.l, r: red_step(f13().rl.r, RedL::Open { p: 1, t: t_b() }) }, ..f13() } }
pub open spec fn f15() -> BizS {
    BizS { rl: RLS { l: ledger_mark(f14().rl.l, t_b()), r: red_step(f14().rl.r, RedL::Attach { p: 1, i: 0, j: 0, end: 1 }) },
           pend: f14().pend.insert(dom_b()), ..f14() }
}
pub open spec fn f16() -> BizS {
    BizS { rl: RLS { l: ledger_batch(f15().rl.l, 0, 0, t_b(), true, 0, 1), r: red_step(f15().rl.r, RedL::Advance { p: 1, row_end: false }) }, ..f15() }
}
pub open spec fn f17() -> BizS {
    BizS { rl: RLS { l: ledger_audit(f16().rl.l, t_a()), r: red_step(f16().rl.r, RedL::Finish { p: 2 }) },
           st: store_drop(f16().st, t_a().sc), pend: f16().pend.filter(|d: Dom| !covers(t_a().rm, d)), wr: f16().wr }
}

pub proof fn counterexample_f1303()
    ensures
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![cb()], named: keys(seq![cb()]), key: None }, f1()),
        sys_step(f1(), BizL::EraseRows { e: dom_b() }, f2()),
        sys_step(f2(), BizL::EraseIndex, f3()),
        sys_step(f3(), BizL::EraseCommit, f4()),
        sys_step(f4(), BizL::Open { p: 0, t: t_a() }, f5()),
        sys_step(f5(), BizL::Start { p: 0, fresh: true }, f6()),
        sys_step(f6(), BizL::Scan { p: 0 }, f7()),
        sys_step(f7(), BizL::Scan { p: 0 }, f8()),
        sys_step(f8(), BizL::ToFinal { p: 0 }, f9()),
        sys_step(f9(), BizL::Open { p: 2, t: t_a() }, f10()),
        sys_step(f10(), BizL::Start { p: 2, fresh: false }, f11()),
        sys_step(f11(), BizL::ToFinal { p: 2 }, f12()),
        sys_step(f12(), BizL::Final { p: 0, ok: true }, f13()),
        sys_step(f13(), BizL::Open { p: 1, t: t_b() }, f14()),
        sys_step(f14(), BizL::Start { p: 1, fresh: true }, f15()),
        sys_step(f15(), BizL::Scan { p: 1 }, f16()),
        sys_step(f16(), BizL::Final { p: 2, ok: true }, f17()),
        // process 2 (target A) runs its final step under B's marker ...
        t_a() != t_b() && tgt_of(f16().rl.r, 2) == t_a() && f16().rl.l.marker == Some(t_b()),
        // ... its audit names A and counts the one tombstone of the tally, a record of B ...
        f16().rl.l.tally == seq![cb()] && member(t_b().rm, cb().k) && !member(t_a().rm, cb().k),
        f17().rl.l.hist == f16().rl.l.hist.push(seq![Rec::Audit { t: t_a(), n: 1 }]),
        // ... and it removes B's marker while B's run is in progress.
        f17().rl.l.marker is None && has_phase(f17().rl.r, 1, Phase::Batches) && tgt_of(f17().rl.r, 1) == t_b()
            && f17().pend.contains(dom_b()),
{
    assert(!member(t_a().rm, kb()) && member(t_b().rm, kb()));
    assert(t_a() != t_b());
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, cb());
    assert(f1().st.rows =~= Map::<Key, int>::empty().insert(kb(), 7));
    assert(sys_step(w0(), BizL::Commit { cs: seq![cb()], named: keys(seq![cb()]), key: None }, f1()));
    assert(sys_step(f1(), BizL::EraseRows { e: dom_b() }, f2()));
    assert(f2().st.rows =~= Map::<Key, int>::empty()) by {
        assert forall|k: Key| !#[trigger] f2().st.rows.contains_key(k) by {
            if f2().st.rows.contains_key(k) { assert(f1().st.rows.contains_key(k)); assert(k == kb()); }
        }
    }
    assert(sys_step(f2(), BizL::EraseIndex, f3()));
    assert(sys_step(f3(), BizL::EraseCommit, f4()));
    assert(sys_step(f4(), BizL::Open { p: 0, t: t_a() }, f5()));
    assert(f5().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(f5().st.rows, t_a().lv));
    assert(tgt_of(f5().rl.r, 0) == t_a());
    assert(aligned(t_a()) && aligned(t_b()));
    assert(f5().rl.l.hist.len() == 1);
    assert(sys_step(f5(), BizL::Start { p: 0, fresh: true }, f6()));
    assert(f6().rl.l.hist[0] == lives(seq![cb()]));
    assert(f6().rl.l.hist[0][0] == Rec::Live(cb()));
    assert(!hit(f6().rl.l, pcur(f6().rl.r, 0)));
    assert(sys_step(f6(), BizL::Scan { p: 0 }, f7()));
    assert(row_end(f7().rl.l, pcur(f7().rl.r, 0)));
    assert(sys_step(f7(), BizL::Scan { p: 0 }, f8()));
    assert(sys_step(f8(), BizL::ToFinal { p: 0 }, f9()));
    assert(sys_step(f9(), BizL::Open { p: 2, t: t_a() }, f10()));
    assert(tgt_of(f10().rl.r, 2) == t_a());
    assert(f10().st.rows =~= Map::<Key, int>::empty());
    assert(sys_step(f10(), BizL::Start { p: 2, fresh: false }, f11()));
    assert(sys_step(f11(), BizL::ToFinal { p: 2 }, f12()));
    assert(tgt_of(f12().rl.r, 0) == t_a());
    assert(f12().st.rows =~= Map::<Key, int>::empty());
    assert(sys_step(f12(), BizL::Final { p: 0, ok: true }, f13()));
    assert(sys_step(f13(), BizL::Open { p: 1, t: t_b() }, f14()));
    assert(tgt_of(f14().rl.r, 1) == t_b());
    assert(f14().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(f14().st.rows, t_b().lv));
    assert(f14().rl.l.hist.len() == 1);
    assert(sys_step(f14(), BizL::Start { p: 1, fresh: true }, f15()));
    assert(f15().rl.l.hist[0] == lives(seq![cb()]));
    assert(hit(f15().rl.l, pcur(f15().rl.r, 1)));
    assert(sys_step(f15(), BizL::Scan { p: 1 }, f16()));
    assert(f16().rl.l.tally =~= seq![cb()]);
    assert(tgt_of(f16().rl.r, 2) == t_a());
    assert(f16().st.rows =~= Map::<Key, int>::empty());
    assert(sys_step(f16(), BizL::Final { p: 2, ok: true }, f17()));
    assert(!covers(t_a().rm, dom_b()));
    assert(f17().pend.contains(dom_b()));
}

} // verus!
