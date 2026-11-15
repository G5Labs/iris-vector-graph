//! Proved counterexample for control `control_f1302_unlocked_start` (F-1302, re-run in this crate), compiled only
//! with that feature.
//!
//! With Start checking without the head lock and writing no marker (LedgerRedact.cls:202-211), and a batch running with
//! no marker whose first tombstone writes it (cls:322-324), the composed participant contracts run, from the initial
//! state: a commit of tenant A's edge; the erasure of A (rows, statement cleanup, commit); a redaction of A opens and
//! starts — nothing of A is live — but writes no marker; a commit re-creates A's edge (nothing refuses it); the first
//! batch tombstones the edge's first record while its key holds recorded content, and only now writes the marker.
//! "No tombstone of live content" fails, and so do the business invariants (marked target holding recorded content).
//! (`proofs/` `counterexample_f1302`; explorer `redaction-as-built-live`; live `commit_in_unmarked_window`.)
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

pub open spec fn e1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![ca()], keys(seq![ca()]), None), r: w0().rl.r }, st: store_apply(w0().st, seq![ca()]), ..w0() }
}
pub open spec fn e2() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..e1().rl.l }, r: e1().rl.r }, st: store_erase_rows(e1().st, dom_a()), ..e1() }
}
pub open spec fn e3() -> BizS { BizS { st: store_erase_index(e2().st), ..e2() } }
pub open spec fn e4() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..e3().rl.l }, r: e3().rl.r }, st: store_erase_commit(e3().st),
           pend: e3().pend.insert(dom_a()), ..e3() }
}
pub open spec fn e5() -> BizS { BizS { rl: RLS { l: e4().rl.l, r: red_step(e4().rl.r, RedL::Open { p: 0, t: t_a() }) }, ..e4() } }
/// The as-built start: the process attaches (first record to the head); no marker is written.
pub open spec fn e6() -> BizS {
    BizS { rl: RLS { l: e5().rl.l, r: red_step(e5().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: e5().pend.insert(dom_a()), ..e5() }
}
pub open spec fn e7() -> BizS {
    BizS { rl: RLS { l: ledger_commit(e6().rl.l, seq![ca2()], keys(seq![ca2()]), None), r: e6().rl.r },
           st: store_apply(e6().st, seq![ca2()]), ..e6() }
}
/// The first batch: tombstone record (0, 0), which writes the marker.
pub open spec fn e8() -> BizS {
    BizS { rl: RLS { l: ledger_batch(e7().rl.l, 0, 0, t_a(), true, 0, 1), r: red_step(e7().rl.r, RedL::Advance { p: 0, row_end: false }) },
           ..e7() }
}

pub proof fn counterexample_f1302()
    ensures
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None }, e1()),
        sys_step(e1(), BizL::EraseRows { e: dom_a() }, e2()),
        sys_step(e2(), BizL::EraseIndex, e3()),
        sys_step(e3(), BizL::EraseCommit, e4()),
        sys_step(e4(), BizL::Open { p: 0, t: t_a() }, e5()),
        sys_step(e5(), BizL::Start { p: 0, fresh: true }, e6()),
        sys_step(e6(), BizL::Commit { cs: seq![ca2()], named: keys(seq![ca2()]), key: None }, e7()),
        sys_step(e7(), BizL::Scan { p: 0 }, e8()),
        // the start wrote no marker, so the re-creating commit was not refused ...
        e6().rl.l.marker is None && e7().st.rows.contains_key(ka()) && !e7().st.unrec.contains(ka()),
        // ... and the batch tombstones A's record while its key holds recorded content, writing the marker only now.
        e7().rl.l.hist[0][0] == Rec::Live(ca()) && e8().rl.l.hist[0][0] == Rec::Tomb(ca()) && rec_content(e7(), ka()),
        e8().rl.l.marker == Some(t_a()) && live_in(e8().st.rows, t_a().lv),
        !biz_inv(e8()),
{
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, ca());
    assert(e1().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5));
    assert(sys_step(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None }, e1()));
    assert(sys_step(e1(), BizL::EraseRows { e: dom_a() }, e2()));
    assert(e2().st.rows =~= Map::<Key, int>::empty()) by {
        assert forall|k: Key| !#[trigger] e2().st.rows.contains_key(k) by {
            if e2().st.rows.contains_key(k) { assert(e1().st.rows.contains_key(k)); assert(k == ka()); }
        }
    }
    assert(sys_step(e2(), BizL::EraseIndex, e3()));
    assert(sys_step(e3(), BizL::EraseCommit, e4()));
    assert(sys_step(e4(), BizL::Open { p: 0, t: t_a() }, e5()));
    assert(e5().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(e5().st.rows, t_a().lv));
    assert(tgt_of(e5().rl.r, 0) == t_a());
    assert(aligned(t_a()));
    assert(e5().rl.l.hist.len() == 1);
    assert(sys_step(e5(), BizL::Start { p: 0, fresh: true }, e6()));
    lemma_one(e6().st.rows, e6().st.stmts, e6().st.unrec, ca2());
    assert(!touches(seq![ca2()], t_a().rm) || e6().rl.l.marker is None);
    assert(sys_step(e6(), BizL::Commit { cs: seq![ca2()], named: keys(seq![ca2()]), key: None }, e7()));
    assert(e7().rl.l.hist[0] == lives(seq![ca()]));
    assert(e7().rl.l.hist[0][0] == Rec::Live(ca()));
    let c7 = pcur(e7().rl.r, 0);
    assert(c7 == Cur { t: dom_a(), i: 0, j: 0, end: 1 });
    assert(hit(e7().rl.l, c7));
    assert(sys_step(e7(), BizL::Scan { p: 0 }, e8()));
    assert(e7().st.rows.contains_key(ka()) && e7().st.rows[ka()] == 6);
    assert(!e7().st.unrec.contains(ka()));
    assert(member(t_a().lv, ka()));
    assert(crow(e8(), ka()) == Some(6int));
    assert(!mark_key_ok(e8(), ka()));
    assert(!key_ok(e8(), ka()));
}

} // verus!
