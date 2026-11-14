//! Non-vacuity of the D-9b metadata and retry-key results (reviewed design), concrete executions of Biz from its
//! initial state, each step checked against `Biz::next` and keeping `biz_inv`:
//! - `witness_noop_recorded`: the reviewed counterpart of `cx_fcs01` (the live minimal schedule of F-CS01): the no-op
//!   operation leaves a no-op record (R-1), so the redaction tombstones it, clears revision 1's metadata and moves
//!   key 2 to idemRedacted; a same-key retry is then refused;
//! - `witness_decision2_spanning`: Decision 2 on a revision spanning tenants A and B (`witness::x1`, key 9): after A's
//!   redaction, B's record is untouched, the revision's metadata is cleared and key 9 can be neither replayed nor
//!   bound again.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
use crate::protocol_rl::*;
use crate::mid::*;
use crate::biz::*;
use crate::safety::*;
use crate::theorems::*;
use crate::witness::*;

verus! {

/// The no-op operation's record (reviewed R-1): it names A's edge and changes nothing.
pub open spec fn cnop() -> Content { Content { k: ka(), eff: Eff::Nop } }

pub open spec fn y1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![ca()], keys(seq![ca()]), Some(1)), r: w0().rl.r }, st: store_apply(w0().st, seq![ca()]), ..w0() }
}
pub open spec fn y2() -> BizS {
    BizS { rl: RLS { l: ledger_commit(y1().rl.l, seq![cnop()], keys(seq![cnop()]), Some(2)), r: y1().rl.r }, st: store_apply(y1().st, seq![cnop()]), ..y1() }
}
pub open spec fn y3() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..y2().rl.l }, r: y2().rl.r }, st: store_erase_rows(y2().st, dom_a()), ..y2() }
}
pub open spec fn y4() -> BizS { BizS { st: store_erase_index(y3().st), ..y3() } }
pub open spec fn y5() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..y4().rl.l }, r: y4().rl.r }, st: store_erase_commit(y4().st),
           pend: y4().pend.insert(dom_a()), ..y4() }
}
pub open spec fn y6() -> BizS { BizS { rl: RLS { l: y5().rl.l, r: red_step(y5().rl.r, RedL::Open { p: 0, t: t_a() }) }, ..y5() } }
pub open spec fn y7() -> BizS {
    BizS { rl: RLS { l: ledger_mark(y6().rl.l, t_a()), r: red_step(y6().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 2 }) },
           pend: y6().pend.insert(dom_a()), ..y6() }
}
pub open spec fn y8() -> BizS {
    BizS { rl: RLS { l: ledger_batch(y7().rl.l, 0, 0, t_a(), true, 0, 1), r: red_step(y7().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..y7() }
}
pub open spec fn y9() -> BizS {
    BizS { rl: RLS { l: ledger_batch(y8().rl.l, 0, 1, t_a(), false, 1, 0), r: red_step(y8().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..y8() }
}
pub open spec fn y10() -> BizS {
    BizS { rl: RLS { l: ledger_batch(y9().rl.l, 1, 0, t_a(), true, 1, 1), r: red_step(y9().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..y9() }
}
pub open spec fn y11() -> BizS {
    BizS { rl: RLS { l: ledger_batch(y10().rl.l, 1, 1, t_a(), false, 2, 0), r: red_step(y10().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..y10() }
}
pub open spec fn y12() -> BizS { BizS { rl: RLS { l: y11().rl.l, r: red_step(y11().rl.r, RedL::ToFinal { p: 0 }) }, ..y11() } }
pub open spec fn y13() -> BizS {
    BizS {
        rl: RLS { l: ledger_audit(y12().rl.l, t_a()), r: red_step(y12().rl.r, RedL::Finish { p: 0 }) },
        st: store_drop(y12().st, t_a().sc),
        pend: y12().pend.filter(|d: Dom| !covers(t_a().rm, d)),
        wr: y12().wr,
    }
}

/// The reviewed design on F-CS01's schedule: both revisions end redacted, both keys in idemRedacted, retries refused.
pub proof fn witness_noop_recorded()
    ensures
        Biz::init(w0()),
        biz_next(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: Some(1) }, y1()),
        biz_next(y1(), BizL::Commit { cs: seq![cnop()], named: keys(seq![cnop()]), key: Some(2) }, y2()),
        biz_next(y2(), BizL::EraseRows { e: dom_a() }, y3()),
        biz_next(y3(), BizL::EraseIndex, y4()),
        biz_next(y4(), BizL::EraseCommit, y5()),
        biz_next(y5(), BizL::Open { p: 0, t: t_a() }, y6()),
        biz_next(y6(), BizL::Start { p: 0, fresh: true }, y7()),
        biz_next(y7(), BizL::Scan { p: 0 }, y8()),
        biz_next(y8(), BizL::Scan { p: 0 }, y9()),
        biz_next(y9(), BizL::Scan { p: 0 }, y10()),
        biz_next(y10(), BizL::Scan { p: 0 }, y11()),
        biz_next(y11(), BizL::ToFinal { p: 0 }, y12()),
        biz_next(y12(), BizL::Final { p: 0, ok: true }, y13()),
        biz_inv(y13()),
        y2().st.rows == y1().st.rows,
        y13().rl.l.hist[1][0] == Rec::Tomb(cnop()),
        meta_redacted(y13().rl.l, 0) && meta_redacted(y13().rl.l, 1),
        y13().rl.l.idemr.contains(1) && y13().rl.l.idemr.contains(2),
        forall|y: BizS, props: Seq<Content>| !biz_next(y13(), BizL::Replay { key: 2, props }, y),
{
    <Biz as SafeContract>::init_safe(w0());
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, ca());
    lemma_one(Map::<Key, int>::empty(), Set::<Key>::empty(), Set::<Key>::empty(), ca());
    assert(y1().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5));
    assert(biz_next(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: Some(1) }, y1()));
    lemma_biz_safe(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: Some(1) }, y1());

    lemma_one(y1().st.rows, y1().st.stmts, y1().st.unrec, cnop());
    assert(y2().st.rows =~= y1().st.rows);
    assert(y1().rl.l.idem =~= Map::<IKey, nat>::empty().insert(1, 0));
    assert(biz_next(y1(), BizL::Commit { cs: seq![cnop()], named: keys(seq![cnop()]), key: Some(2) }, y2()));
    lemma_biz_safe(y1(), BizL::Commit { cs: seq![cnop()], named: keys(seq![cnop()]), key: Some(2) }, y2());

    assert(biz_next(y2(), BizL::EraseRows { e: dom_a() }, y3()));
    lemma_biz_safe(y2(), BizL::EraseRows { e: dom_a() }, y3());
    assert(y3().st.rows =~= Map::<Key, int>::empty()) by {
        assert forall|k: Key| !#[trigger] y3().st.rows.contains_key(k) by {
            if y3().st.rows.contains_key(k) { assert(y2().st.rows.contains_key(k)); assert(k == ka()); }
        }
    }
    assert(biz_next(y3(), BizL::EraseIndex, y4()));
    lemma_biz_safe(y3(), BizL::EraseIndex, y4());
    assert(biz_next(y4(), BizL::EraseCommit, y5()));
    lemma_biz_safe(y4(), BizL::EraseCommit, y5());
    assert(biz_next(y5(), BizL::Open { p: 0, t: t_a() }, y6()));
    lemma_biz_safe(y5(), BizL::Open { p: 0, t: t_a() }, y6());
    assert(y6().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(y6().st.rows, t_a().lv));
    assert(tgt_of(y6().rl.r, 0) == t_a());
    assert(aligned(t_a()));
    assert(no_open(y6().wr));
    assert(biz_next(y6(), BizL::Start { p: 0, fresh: true }, y7()));
    lemma_biz_safe(y6(), BizL::Start { p: 0, fresh: true }, y7());

    let c7 = pcur(y7().rl.r, 0);
    assert(c7 == Cur { t: dom_a(), i: 0, j: 0, end: 2 });
    assert(y7().rl.l.hist[0][0] == Rec::Live(ca()));
    assert(hit(y7().rl.l, c7));
    assert(biz_next(y7(), BizL::Scan { p: 0 }, y8()));
    lemma_biz_safe(y7(), BizL::Scan { p: 0 }, y8());
    assert(row_end(y8().rl.l, pcur(y8().rl.r, 0)));
    assert(biz_next(y8(), BizL::Scan { p: 0 }, y9()));
    lemma_biz_safe(y8(), BizL::Scan { p: 0 }, y9());
    let c9 = pcur(y9().rl.r, 0);
    assert(c9 == Cur { t: dom_a(), i: 1, j: 0, end: 2 });
    assert(y9().rl.l.hist[1] == lives(seq![cnop()]));
    assert(y9().rl.l.hist[1][0] == Rec::Live(cnop()));
    assert(hit(y9().rl.l, c9));
    assert(biz_next(y9(), BizL::Scan { p: 0 }, y10()));
    lemma_biz_safe(y9(), BizL::Scan { p: 0 }, y10());
    assert(row_end(y10().rl.l, pcur(y10().rl.r, 0)));
    assert(biz_next(y10(), BizL::Scan { p: 0 }, y11()));
    lemma_biz_safe(y10(), BizL::Scan { p: 0 }, y11());
    assert(biz_next(y11(), BizL::ToFinal { p: 0 }, y12()));
    lemma_biz_safe(y11(), BizL::ToFinal { p: 0 }, y12());
    assert(tgt_of(y12().rl.r, 0) == t_a());
    assert(y12().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(y12().st.rows, t_a().lv));
    assert(biz_next(y12(), BizL::Final { p: 0, ok: true }, y13()));
    lemma_biz_safe(y12(), BizL::Final { p: 0, ok: true }, y13());

    assert(y13().rl.l.hist[0] == y8().rl.l.hist[0]);
    assert(y13().rl.l.hist[1] == y10().rl.l.hist[1]);
    assert(y13().rl.l.hist[0][0] is Tomb && y13().rl.l.hist[1][0] is Tomb);
    theorem_decision2_any(y13(), 0, 0);
    theorem_decision2_any(y13(), 1, 0);
    assert(y13().rl.l.meta[1].okey == Some(2int));
    assert(y13().rl.l.meta[0].okey == Some(1int));
    assert forall|y: BizS, props: Seq<Content>| !biz_next(y13(), BizL::Replay { key: 2, props }, y) by {
        if biz_next(y13(), BizL::Replay { key: 2, props }, y) { theorem_retry_refused(y13(), 2, BizL::Replay { key: 2, props }, y); }
    }
}

/// Decision 2 on a revision spanning tenants A and B: A's redaction clears its metadata and moves key 9; B's record
/// stays as it was; key 9 can be neither replayed nor bound again.
pub proof fn witness_decision2_spanning()
    ensures
        x17().rl.l.hist[0][0] == Rec::Tomb(ca()) && x17().rl.l.hist[0][1] == Rec::Live(cb()),
        meta_redacted(x17().rl.l, 0) && x17().rl.l.meta[0].okey == Some(9int) && x17().rl.l.idemr.contains(9),
        forall|y: BizS, props: Seq<Content>| !biz_next(x17(), BizL::Replay { key: 9, props }, y),
        forall|y: BizS, cs: Seq<Content>, named: Seq<Key>| !biz_next(x17(), BizL::Commit { cs, named, key: Some(9) }, y),
{
    witness_erasure_rollback();
    witness_bypass_and_redaction();
    theorem_decision2_any(x17(), 0, 0);
    assert(x17().rl.l.meta[0] == x13().rl.l.meta[0]);
    assert(x13().rl.l.meta[0] == cleared(x12().rl.l.meta[0]));
    assert(x12().rl.l.meta[0] == x1().rl.l.meta[0]);
    assert(x1().rl.l.meta[0] == commit_meta(keys(cs2()), Some(9)));
    assert forall|y: BizS, props: Seq<Content>| !biz_next(x17(), BizL::Replay { key: 9, props }, y) by {
        if biz_next(x17(), BizL::Replay { key: 9, props }, y) { theorem_retry_refused(x17(), 9, BizL::Replay { key: 9, props }, y); }
    }
    assert forall|y: BizS, cs: Seq<Content>, named: Seq<Key>| !biz_next(x17(), BizL::Commit { cs, named, key: Some(9) }, y) by {
        if biz_next(x17(), BizL::Commit { cs, named, key: Some(9) }, y) {
            theorem_retry_refused(x17(), 9, BizL::Commit { cs, named, key: Some(9) }, y);
        }
    }
}

} // verus!
