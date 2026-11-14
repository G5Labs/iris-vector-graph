//! Non-vacuity witness: one concrete execution of the outer contract from its initial state, through a commit of
//! two tenants' content, an erasure of tenant A, and the whole redaction of A (open, fresh start, a tombstone, a
//! skipped record of tenant B, a revision boundary, the final step), to a settled state whose replay equals the
//! store. Every step is checked against `Biz::next` and keeps the invariants, so neither the contract's steps nor
//! its invariants are vacuous on the path the upstream e2e test exercises (spec 256 US2).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
use crate::protocol_rl::*;
use crate::biz::*;

verus! {

pub open spec fn tenant_a() -> Tgt { |k: Key| k.g == 1 }
pub open spec fn tenant_b() -> Tgt { |k: Key| k.g == 2 }
pub open spec fn ka() -> Key { Key { g: 1, id: 1, edge: true } }
pub open spec fn kb() -> Key { Key { g: 2, id: 1, edge: false } }
pub open spec fn ca() -> Content { Content { k: ka(), eff: Eff::Put(5) } }
pub open spec fn cb() -> Content { Content { k: kb(), eff: Eff::Put(7) } }

pub open spec fn w0() -> BizS {
    BizS {
        rl: RLS {
            l: LedgerS { hist: Seq::empty(), idem: Map::empty(), locked: false, enabled: true, marker: None, mi: 0, mj: 0, mend: 0,
                         count: 0, tally: Seq::empty() },
            r: RedS { procs: Map::empty() },
        },
        st: StoreS { rows: Map::empty(), stmts: Set::empty(), erasing: None },
        pend: Set::empty(),
    }
}

pub proof fn witness_erase_then_redact()
    ensures ({
        let t = tenant_a();
        let cs = seq![ca(), cb()];
        let x0 = w0();
        let l1 = BizL::Commit { cs, key: Some(9) };
        let x1 = BizS { rl: RLS { l: ledger_commit(x0.rl.l, cs, Some(9)), r: x0.rl.r }, st: store_apply(x0.st, cs), pend: x0.pend };
        let l2 = BizL::EraseRows { t };
        let x2 = BizS { rl: RLS { l: LedgerS { locked: true, ..x1.rl.l }, r: x1.rl.r }, st: store_erase_rows(x1.st, t), pend: x1.pend.insert(t) };
        let l3 = BizL::EraseIndex { t };
        let x3 = BizS { rl: RLS { l: LedgerS { locked: false, ..x2.rl.l }, r: x2.rl.r }, st: store_erase_index(x2.st, t), pend: x2.pend };
        let l4 = BizL::Open { p: 0, t };
        let x4 = BizS { rl: RLS { l: x3.rl.l, r: red_step(x3.rl.r, RedL::Open { p: 0, t }) }, ..x3 };
        let l5 = BizL::Start { p: 0, fresh: true };
        let x5 = BizS {
            rl: RLS { l: ledger_mark(x4.rl.l, t), r: red_step(x4.rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: x4.rl.l.hist.len() }) },
            st: x4.st, pend: x4.pend.insert(t) };
        let l6 = BizL::Scan { p: 0 };
        let x6 = BizS { rl: RLS { l: ledger_batch(x5.rl.l, 0, 0, t, true, 0, 1), r: red_step(x5.rl.r, RedL::Advance { p: 0, row_end: false }) }, ..x5 };
        let x7 = BizS { rl: RLS { l: ledger_batch(x6.rl.l, 0, 1, t, false, 0, 2), r: red_step(x6.rl.r, RedL::Advance { p: 0, row_end: false }) }, ..x6 };
        let x8 = BizS { rl: RLS { l: ledger_batch(x7.rl.l, 0, 2, t, false, 1, 0), r: red_step(x7.rl.r, RedL::Advance { p: 0, row_end: true }) }, ..x7 };
        let l9 = BizL::ToFinal { p: 0 };
        let x9 = BizS { rl: RLS { l: x8.rl.l, r: red_step(x8.rl.r, RedL::ToFinal { p: 0 }) }, ..x8 };
        let l10 = BizL::Final { p: 0, ok: true };
        let x10 = BizS { rl: RLS { l: ledger_audit(x9.rl.l, t), r: red_step(x9.rl.r, RedL::Finish { p: 0 }) }, st: x9.st, pend: x9.pend.remove(t) };
        &&& Biz::init(x0)
        &&& biz_next(x0, l1, x1) && biz_next(x1, l2, x2) && biz_next(x2, l3, x3) && biz_next(x3, l4, x4)
        &&& biz_next(x4, l5, x5) && biz_next(x5, l6, x6) && biz_next(x6, l6, x7) && biz_next(x7, l6, x8)
        &&& biz_next(x8, l9, x9) && biz_next(x9, l10, x10)
        &&& biz_inv(x5) && biz_inv(x10)
        &&& x5.rl.l.marker == Some(t)
        &&& settled(x10)
        &&& replay(x10.rl.l.hist) =~= x10.st.rows
        &&& x10.st.rows.contains_key(kb()) && x10.st.rows[kb()] == 7 && !x10.st.rows.contains_key(ka())
        &&& x10.rl.l.hist.len() == 2
        &&& x10.rl.l.hist[0][0] == Rec::Tomb(ca()) && x10.rl.l.hist[0][1] == Rec::Live(cb())
        &&& x10.rl.l.hist[1] == seq![Rec::Audit { t, n: 1 }]
    }),
{
    let t = tenant_a();
    let cs = seq![ca(), cb()];
    let x0 = w0();
    <Biz as SafeContract>::init_safe(x0);

    let l1 = BizL::Commit { cs, key: Some(9) };
    let x1 = BizS { rl: RLS { l: ledger_commit(x0.rl.l, cs, Some(9)), r: x0.rl.r }, st: store_apply(x0.st, cs), pend: x0.pend };
    assert(lives(cs).len() == 2 && lives(cs)[0] == Rec::Live(ca()) && lives(cs)[1] == Rec::Live(cb()));
    assert(biz_next(x0, l1, x1));
    lemma_biz_safe(x0, l1, x1);
    assert(x1.rl.l.hist[0] == lives(cs));

    let l2 = BizL::EraseRows { t };
    let x2 = BizS { rl: RLS { l: LedgerS { locked: true, ..x1.rl.l }, r: x1.rl.r }, st: store_erase_rows(x1.st, t), pend: x1.pend.insert(t) };
    assert(biz_next(x1, l2, x2));
    lemma_biz_safe(x1, l2, x2);

    let l3 = BizL::EraseIndex { t };
    let x3 = BizS { rl: RLS { l: LedgerS { locked: false, ..x2.rl.l }, r: x2.rl.r }, st: store_erase_index(x2.st, t), pend: x2.pend };
    assert(biz_next(x2, l3, x3));
    lemma_biz_safe(x2, l3, x3);

    let l4 = BizL::Open { p: 0, t };
    let x4 = BizS { rl: RLS { l: x3.rl.l, r: red_step(x3.rl.r, RedL::Open { p: 0, t }) }, ..x3 };
    assert(biz_next(x3, l4, x4));
    lemma_biz_safe(x3, l4, x4);

    let l5 = BizL::Start { p: 0, fresh: true };
    let x5 = BizS {
        rl: RLS { l: ledger_mark(x4.rl.l, t), r: red_step(x4.rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: x4.rl.l.hist.len() }) },
        st: x4.st, pend: x4.pend.insert(t) };
    lemma_outside_not_live(x1.st.rows, t, t);
    assert(tgt_of(x4.rl.r, 0) == t);
    assert(biz_next(x4, l5, x5));
    lemma_biz_safe(x4, l5, x5);

    // Scan 1: record (0, 0) is tenant A's: tombstone it.
    let l6 = BizL::Scan { p: 0 };
    let c5 = pcur(x5.rl.r, 0);
    assert(c5 == Cur { t, i: 0, j: 0, end: 1 });
    assert(x5.rl.l.hist[0][0] == Rec::Live(ca()));
    assert(member(t, ka()));
    assert(hit(x5.rl.l, c5));
    let x6 = BizS { rl: RLS { l: ledger_batch(x5.rl.l, 0, 0, t, true, 0, 1), r: red_step(x5.rl.r, RedL::Advance { p: 0, row_end: false }) }, ..x5 };
    assert(biz_next(x5, l6, x6));
    lemma_biz_safe(x5, l6, x6);

    // Scan 2: record (0, 1) is tenant B's: skip it.
    let c6 = pcur(x6.rl.r, 0);
    assert(c6 == Cur { t, i: 0, j: 1, end: 1 });
    assert(x6.rl.l.hist[0][1] == Rec::Live(cb()));
    assert(!member(t, kb()));
    assert(!hit(x6.rl.l, c6));
    let x7 = BizS { rl: RLS { l: ledger_batch(x6.rl.l, 0, 1, t, false, 0, 2), r: red_step(x6.rl.r, RedL::Advance { p: 0, row_end: false }) }, ..x6 };
    assert(biz_next(x6, l6, x7));
    lemma_biz_safe(x6, l6, x7);

    // Scan 3: the end of revision 0.
    let c7 = pcur(x7.rl.r, 0);
    assert(c7 == Cur { t, i: 0, j: 2, end: 1 });
    assert(row_end(x7.rl.l, c7));
    let x8 = BizS { rl: RLS { l: ledger_batch(x7.rl.l, 0, 2, t, false, 1, 0), r: red_step(x7.rl.r, RedL::Advance { p: 0, row_end: true }) }, ..x7 };
    assert(biz_next(x7, l6, x8));
    lemma_biz_safe(x7, l6, x8);

    let l9 = BizL::ToFinal { p: 0 };
    let x9 = BizS { rl: RLS { l: x8.rl.l, r: red_step(x8.rl.r, RedL::ToFinal { p: 0 }) }, ..x8 };
    assert(biz_next(x8, l9, x9));
    lemma_biz_safe(x8, l9, x9);

    let l10 = BizL::Final { p: 0, ok: true };
    let x10 = BizS { rl: RLS { l: ledger_audit(x9.rl.l, t), r: red_step(x9.rl.r, RedL::Finish { p: 0 }) }, st: x9.st, pend: x9.pend.remove(t) };
    assert(biz_next(x9, l10, x10));
    lemma_biz_safe(x9, l10, x10);

    assert(x10.pend =~= Set::<Tgt>::empty());
    theorem_replay_settled(x10);
    assert(x10.st.rows == outside(store_apply(x0.st, cs).rows, t));
    assert(store_apply(x0.st, cs).rows.contains_key(kb()));
    assert(x10.rl.l.hist[0][0] == Rec::Tomb(ca()));
    assert(x10.rl.l.hist[0][1] == Rec::Live(cb()));
}

} // verus!
