//! Non-vacuity witnesses: concrete executions of Biz from its initial state that use every new element of the model,
//! each step checked against `Biz::next` and keeping the invariants:
//! - `witness_erasure_rollback`: a commit of two tenants' content; an erasure of tenant A that rolls back (A's row is
//!   back exactly as it was); the erasure again, its statement cleanup, its commit.
//! - `witness_bypass_and_redaction`: a bypass write of tenant B that rolls back, the same write again and its commit;
//!   then the whole redaction of A with three **different** (aligned) predicates — liveness wider than record match,
//!   statement cleanup narrower — to a settled state whose replay equals the store at every key the bypass writer did
//!   not write (`witness_settled`).
//! Fixtures (keys, contents, targets) are shared with the counterexamples (`cx_*`).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
use crate::writer::*;
use crate::protocol_rl::*;
use crate::mid::*;
use crate::biz::*;
use crate::safety::*;
use crate::theorems::*;

verus! {

pub open spec fn dom_a() -> Dom { |k: Key| k.g == 1 }
/// Tenant A's target with three different predicates: liveness also looks at graph 3; cleanup only at A's edges.
pub open spec fn t_a() -> Tgt { Tgt { rm: dom_a(), lv: |k: Key| k.g == 1 || k.g == 3, sc: |k: Key| k.g == 1 && k.edge } }
pub open spec fn ka() -> Key { Key { g: 1, id: 1, edge: true } }
pub open spec fn kb() -> Key { Key { g: 2, id: 1, edge: false } }
pub open spec fn kb2() -> Key { Key { g: 2, id: 2, edge: false } }
pub open spec fn ca() -> Content { Content { k: ka(), eff: Eff::Put(5) } }
pub open spec fn cb() -> Content { Content { k: kb(), eff: Eff::Put(7) } }

pub open spec fn w0() -> BizS {
    BizS {
        rl: RLS {
            l: LedgerS { hist: Seq::empty(), idem: Map::empty(), locked: false, enabled: true, marker: None, mi: 0, mj: 0, mend: 0,
                         count: 0, tally: Seq::empty() },
            r: RedS { procs: Map::empty() },
        },
        st: StoreS { rows: Map::empty(), unrec: Set::empty(), stmts: Set::empty(), erasing: None },
        pend: Set::empty(),
        wr: WrS { open: Map::empty() },
    }
}

pub open spec fn cs2() -> Seq<Content> { seq![ca(), cb()] }

pub open spec fn x1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, cs2(), Some(9)), r: w0().rl.r }, st: store_apply(w0().st, cs2()), ..w0() }
}
pub open spec fn x2() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..x1().rl.l }, r: x1().rl.r }, st: store_erase_rows(x1().st, dom_a()), ..x1() }
}
pub open spec fn x3() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..x2().rl.l }, r: x2().rl.r }, st: store_erase_abort(x2().st), ..x2() }
}
pub open spec fn x4() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..x3().rl.l }, r: x3().rl.r }, st: store_erase_rows(x3().st, dom_a()), ..x3() }
}
pub open spec fn x5() -> BizS { BizS { st: store_erase_index(x4().st), ..x4() } }
pub open spec fn x6() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..x5().rl.l }, r: x5().rl.r }, st: store_erase_commit(x5().st),
           pend: x5().pend.insert(dom_a()), ..x5() }
}

proof fn lemma_cs2()
    ensures
        lives(cs2()).len() == 2, lives(cs2())[0] == Rec::Live(ca()), lives(cs2())[1] == Rec::Live(cb()),
        x1().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5).insert(kb(), 7),
        x1().st.stmts =~= Set::<Key>::empty().insert(ka()),
        x1().st.unrec =~= Set::<Key>::empty(),
{
    let rs = lives(cs2());
    let r1 = rs.drop_last();
    let r0 = r1.drop_last();
    assert(r0 =~= Seq::<Rec>::empty());
    assert(r1.last() == Rec::Live(ca()));
    assert(rs.last() == Rec::Live(cb()));
    let m0 = Map::<Key, int>::empty();
    let s0 = Set::<Key>::empty();
    assert(replay_recs(m0, r0) == m0);
    assert(replay_recs(m0, r1) == apply_rec(m0, Rec::Live(ca())));
    assert(replay_recs(m0, rs) == apply_rec(apply_rec(m0, Rec::Live(ca())), Rec::Live(cb())));
    assert(stmt_recs(s0, r0) == s0);
    assert(stmt_recs(s0, r1) == stmt_rec(s0, Rec::Live(ca())));
    assert(stmt_recs(s0, rs) == stmt_rec(stmt_rec(s0, Rec::Live(ca())), Rec::Live(cb())));
    assert(unrec_recs(s0, r0) == s0);
    assert(unrec_recs(s0, r1) == unrec_rec(s0, Rec::Live(ca())));
    assert(unrec_recs(s0, rs) == unrec_rec(unrec_rec(s0, Rec::Live(ca())), Rec::Live(cb())));
}

/// A one-record changeset (used by the counterexamples).
pub proof fn lemma_one(m: Map<Key, int>, st: Set<Key>, u: Set<Key>, c: Content)
    ensures
        lives(seq![c]).len() == 1, lives(seq![c])[0] == Rec::Live(c),
        replay_recs(m, lives(seq![c])) == apply_rec(m, Rec::Live(c)),
        stmt_recs(st, lives(seq![c])) == stmt_rec(st, Rec::Live(c)),
        unrec_recs(u, lives(seq![c])) == unrec_rec(u, Rec::Live(c)),
{
    let rs = lives(seq![c]);
    assert(rs.drop_last() =~= Seq::<Rec>::empty());
    assert(rs.last() == Rec::Live(c));
    assert(replay_recs(m, rs.drop_last()) == m);
    assert(stmt_recs(st, rs.drop_last()) == st);
    assert(unrec_recs(u, rs.drop_last()) == u);
}

/// An erasure that rolls back, then the erasure again to its commit.
pub proof fn witness_erasure_rollback()
    ensures
        Biz::init(w0()),
        biz_next(w0(), BizL::Commit { cs: cs2(), key: Some(9) }, x1()),
        biz_next(x1(), BizL::EraseRows { e: dom_a() }, x2()),
        biz_next(x2(), BizL::EraseAbort, x3()),
        biz_next(x3(), BizL::EraseRows { e: dom_a() }, x4()),
        biz_next(x4(), BizL::EraseIndex, x5()),
        biz_next(x5(), BizL::EraseCommit, x6()),
        biz_inv(x6()),
        // the rollback restored A's row and statement exactly; the committed erasure removed them
        !x2().st.rows.contains_key(ka()) && x3().st.rows =~= x1().st.rows && x3().st.stmts =~= x1().st.stmts,
        !x6().st.rows.contains_key(ka()) && !x6().st.stmts.contains(ka()) && x6().st.rows.contains_key(kb()),
        x6().pend.contains(dom_a()),
{
    <Biz as SafeContract>::init_safe(w0());
    lemma_cs2();
    assert(biz_next(w0(), BizL::Commit { cs: cs2(), key: Some(9) }, x1()));
    lemma_biz_safe(w0(), BizL::Commit { cs: cs2(), key: Some(9) }, x1());

    assert(biz_next(x1(), BizL::EraseRows { e: dom_a() }, x2()));
    lemma_biz_safe(x1(), BizL::EraseRows { e: dom_a() }, x2());

    assert(biz_next(x2(), BizL::EraseAbort, x3()));
    lemma_biz_safe(x2(), BizL::EraseAbort, x3());
    assert(x3().st.rows =~= x1().st.rows);
    assert(x3().st.stmts =~= x1().st.stmts);

    assert(biz_next(x3(), BizL::EraseRows { e: dom_a() }, x4()));
    lemma_biz_safe(x3(), BizL::EraseRows { e: dom_a() }, x4());

    assert(biz_next(x4(), BizL::EraseIndex, x5()));
    lemma_biz_safe(x4(), BizL::EraseIndex, x5());

    assert(biz_next(x5(), BizL::EraseCommit, x6()));
    lemma_biz_safe(x5(), BizL::EraseCommit, x6());
    assert(!x6().st.stmts.contains(ka()));
}

pub open spec fn x7() -> BizS {
    BizS { st: store_write(x6().st, kb2(), Some(3)), wr: WrS { open: x6().wr.open.insert(kb2(), BTx { before: None, was: false }) }, ..x6() }
}
pub open spec fn x8() -> BizS { BizS { st: store_undo(x7().st, kb2(), None, false), wr: WrS { open: x7().wr.open.remove(kb2()) }, ..x7() } }
pub open spec fn x9() -> BizS {
    BizS { st: store_write(x8().st, kb2(), Some(3)), wr: WrS { open: x8().wr.open.insert(kb2(), BTx { before: None, was: false }) }, ..x8() }
}
pub open spec fn x10() -> BizS { BizS { wr: WrS { open: x9().wr.open.remove(kb2()) }, ..x9() } }
pub open spec fn x11() -> BizS { BizS { rl: RLS { l: x10().rl.l, r: red_step(x10().rl.r, RedL::Open { p: 0, t: t_a() }) }, ..x10() } }
pub open spec fn x12() -> BizS {
    BizS { rl: RLS { l: ledger_mark(x11().rl.l, t_a()), r: red_step(x11().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: x11().pend.insert(dom_a()), ..x11() }
}
pub open spec fn x13() -> BizS {
    BizS { rl: RLS { l: ledger_batch(x12().rl.l, 0, 0, t_a(), true, 0, 1), r: red_step(x12().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..x12() }
}
pub open spec fn x14() -> BizS {
    BizS { rl: RLS { l: ledger_batch(x13().rl.l, 0, 1, t_a(), false, 0, 2), r: red_step(x13().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..x13() }
}
pub open spec fn x15() -> BizS {
    BizS { rl: RLS { l: ledger_batch(x14().rl.l, 0, 2, t_a(), false, 1, 0), r: red_step(x14().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..x14() }
}
pub open spec fn x16() -> BizS { BizS { rl: RLS { l: x15().rl.l, r: red_step(x15().rl.r, RedL::ToFinal { p: 0 }) }, ..x15() } }
pub open spec fn x17() -> BizS {
    BizS {
        rl: RLS { l: ledger_audit(x16().rl.l, t_a()), r: red_step(x16().rl.r, RedL::Finish { p: 0 }) },
        st: store_drop(x16().st, t_a().sc),
        pend: x16().pend.filter(|d: Dom| !covers(t_a().rm, d)),
        wr: x16().wr,
    }
}

/// A bypass write that rolls back, the same write committed, and the redaction of A to a settled state.
pub proof fn witness_bypass_and_redaction()
    requires biz_inv(x6()),
    ensures
        aligned(t_a()) && t_a().rm != t_a().lv && t_a().sc != t_a().rm,
        biz_next(x6(), BizL::BBegin { k: kb2(), v: Some(3) }, x7()),
        biz_next(x7(), BizL::BAbort { k: kb2() }, x8()),
        biz_next(x8(), BizL::BBegin { k: kb2(), v: Some(3) }, x9()),
        biz_next(x9(), BizL::BCommit { k: kb2() }, x10()),
        biz_next(x10(), BizL::Open { p: 0, t: t_a() }, x11()),
        biz_next(x11(), BizL::Start { p: 0, fresh: true }, x12()),
        biz_next(x12(), BizL::Scan { p: 0 }, x13()),
        biz_next(x13(), BizL::Scan { p: 0 }, x14()),
        biz_next(x14(), BizL::Scan { p: 0 }, x15()),
        biz_next(x15(), BizL::ToFinal { p: 0 }, x16()),
        biz_next(x16(), BizL::Final { p: 0, ok: true }, x17()),
        biz_inv(x12()) && x12().rl.l.marker == Some(t_a()),
        biz_inv(x17()),
        !x8().st.rows.contains_key(kb2()) && x10().st.rows.contains_key(kb2()) && x10().st.unrec.contains(kb2()),
        x17().rl.l.hist[0][0] == Rec::Tomb(ca()) && x17().rl.l.hist[0][1] == Rec::Live(cb()),
        x17().rl.l.hist[1] == seq![Rec::Audit { t: t_a(), n: 1 }],
{
    lemma_cs2();
    assert(member(t_a().lv, Key { g: 3, id: 0, edge: false }) && !member(t_a().rm, Key { g: 3, id: 0, edge: false }));
    assert(member(t_a().rm, Key { g: 1, id: 0, edge: false }) && !member(t_a().sc, Key { g: 1, id: 0, edge: false }));
    assert(oget(x6().st.rows, kb2()) is None);
    assert(!x6().st.unrec.contains(kb2()));
    assert(biz_next(x6(), BizL::BBegin { k: kb2(), v: Some(3) }, x7()));
    lemma_biz_safe(x6(), BizL::BBegin { k: kb2(), v: Some(3) }, x7());

    assert(x7().wr.open[kb2()] == BTx { before: None, was: false });
    assert(biz_next(x7(), BizL::BAbort { k: kb2() }, x8()));
    lemma_biz_safe(x7(), BizL::BAbort { k: kb2() }, x8());

    assert(x8().wr.open =~= Map::<Key, BTx>::empty());
    assert(oget(x8().st.rows, kb2()) is None);
    assert(!x8().st.unrec.contains(kb2()));
    assert(biz_next(x8(), BizL::BBegin { k: kb2(), v: Some(3) }, x9()));
    lemma_biz_safe(x8(), BizL::BBegin { k: kb2(), v: Some(3) }, x9());

    assert(biz_next(x9(), BizL::BCommit { k: kb2() }, x10()));
    lemma_biz_safe(x9(), BizL::BCommit { k: kb2() }, x10());
    assert(x10().wr.open =~= Map::<Key, BTx>::empty());

    assert(biz_next(x10(), BizL::Open { p: 0, t: t_a() }, x11()));
    lemma_biz_safe(x10(), BizL::Open { p: 0, t: t_a() }, x11());

    // Start: nothing the liveness predicate selects is live (A was erased; graph 3 is empty).
    assert(tgt_of(x11().rl.r, 0) == t_a());
    if live_in(x11().st.rows, t_a().lv) {
        let k = choose|k: Key| #[trigger] x11().st.rows.contains_key(k) && member(t_a().lv, k);
        assert(k == kb() || k == kb2());
    }
    assert(x11().rl.l.hist.len() == 1);
    assert(no_open(x11().wr));
    assert(biz_next(x11(), BizL::Start { p: 0, fresh: true }, x12()));
    lemma_biz_safe(x11(), BizL::Start { p: 0, fresh: true }, x12());

    // Scan 1: record (0, 0) is A's: tombstone it.
    let c12 = pcur(x12().rl.r, 0);
    assert(c12 == Cur { t: dom_a(), i: 0, j: 0, end: 1 });
    assert(x12().rl.l.hist[0][0] == Rec::Live(ca()));
    assert(hit(x12().rl.l, c12));
    assert(biz_next(x12(), BizL::Scan { p: 0 }, x13()));
    lemma_biz_safe(x12(), BizL::Scan { p: 0 }, x13());

    // Scan 2: record (0, 1) is B's: skip it.
    let c13 = pcur(x13().rl.r, 0);
    assert(c13 == Cur { t: dom_a(), i: 0, j: 1, end: 1 });
    assert(x13().rl.l.hist[0][1] == Rec::Live(cb()));
    assert(!hit(x13().rl.l, c13));
    assert(biz_next(x13(), BizL::Scan { p: 0 }, x14()));
    lemma_biz_safe(x13(), BizL::Scan { p: 0 }, x14());

    // Scan 3: the end of revision 0.
    let c14 = pcur(x14().rl.r, 0);
    assert(c14 == Cur { t: dom_a(), i: 0, j: 2, end: 1 });
    assert(row_end(x14().rl.l, c14));
    assert(biz_next(x14(), BizL::Scan { p: 0 }, x15()));
    lemma_biz_safe(x14(), BizL::Scan { p: 0 }, x15());

    assert(biz_next(x15(), BizL::ToFinal { p: 0 }, x16()));
    lemma_biz_safe(x15(), BizL::ToFinal { p: 0 }, x16());

    assert(tgt_of(x16().rl.r, 0) == t_a());
    assert(biz_next(x16(), BizL::Final { p: 0, ok: true }, x17()));
    lemma_biz_safe(x16(), BizL::Final { p: 0, ok: true }, x17());
    assert(x17().rl.l.hist[0][0] == Rec::Tomb(ca()));
    assert(x17().rl.l.hist[0][1] == Rec::Live(cb()));
}

/// The end of the redaction is settled: replay equals the store at every key the bypass writer did not write; the
/// bypass-written row of B stays (unrecorded, which `verify()` would report).
pub proof fn witness_settled()
    ensures
        settled(x17()),
        forall|k: Key| !x17().st.unrec.contains(k) ==> #[trigger] oget(replay(x17().rl.l.hist), k) == oget(x17().st.rows, k),
        x17().st.unrec =~= Set::<Key>::empty().insert(kb2()),
        x17().st.rows.contains_key(kb()) && x17().st.rows[kb()] == 7 && !x17().st.rows.contains_key(ka()),
        x17().st.rows.contains_key(kb2()),
{
    witness_erasure_rollback();
    witness_bypass_and_redaction();
    lemma_cs2();
    assert(covers(t_a().rm, dom_a()));
    assert(x17().pend =~= Set::<Dom>::empty()) by {
        assert forall|d: Dom| !#[trigger] x17().pend.contains(d) by {
            if x16().pend.contains(d) { assert(d == dom_a()); }
        }
    }
    assert(no_open(x17().wr));
    assert(settled(x17()));
    theorem_replay_settled(x17());
}

} // verus!
