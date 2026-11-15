//! Proved counterexample for control `control_unaligned_sc`, compiled only with that feature.
//!
//! The target's record match and liveness are tenant A's graph, but its statement cleanup selects every graph's
//! statements (the shape of core model control `m1-control-dropstatements-all-graphs`). From the initial state: a
//! ledger commit of tenant B's edge (row and statement entry); the redaction of A opens, starts (A not live), scans the
//! revision (B's record is not A's), reaches its final step and finishes — and its statement cleanup removes B's
//! statement entry while B's edge is live: "statement entries match live edges" fails for another tenant.
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

pub open spec fn t_x() -> Tgt { Tgt { rm: dom_a(), lv: dom_a(), sc: |k: Key| k.edge } }
pub open spec fn kbe() -> Key { Key { g: 2, id: 1, edge: true } }
pub open spec fn cbe() -> Content { Content { k: kbe(), eff: Eff::Put(7) } }

pub open spec fn v1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![cbe()], None), r: w0().rl.r }, st: store_apply(w0().st, seq![cbe()]), ..w0() }
}
pub open spec fn v2() -> BizS { BizS { rl: RLS { l: v1().rl.l, r: red_step(v1().rl.r, RedL::Open { p: 0, t: t_x() }) }, ..v1() } }
pub open spec fn v3() -> BizS {
    BizS { rl: RLS { l: ledger_mark(v2().rl.l, t_x()), r: red_step(v2().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: v2().pend.insert(dom_a()), ..v2() }
}
pub open spec fn v4() -> BizS {
    BizS { rl: RLS { l: ledger_batch(v3().rl.l, 0, 0, t_x(), false, 0, 1), r: red_step(v3().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..v3() }
}
pub open spec fn v5() -> BizS {
    BizS { rl: RLS { l: ledger_batch(v4().rl.l, 0, 1, t_x(), false, 1, 0), r: red_step(v4().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..v4() }
}
pub open spec fn v6() -> BizS { BizS { rl: RLS { l: v5().rl.l, r: red_step(v5().rl.r, RedL::ToFinal { p: 0 }) }, ..v5() } }
pub open spec fn v7() -> BizS {
    BizS {
        rl: RLS { l: ledger_audit(v6().rl.l, t_x()), r: red_step(v6().rl.r, RedL::Finish { p: 0 }) },
        st: store_drop(v6().st, t_x().sc),
        pend: v6().pend.filter(|d: Dom| !covers(t_x().rm, d)),
        wr: v6().wr,
    }
}

pub proof fn counterexample_unaligned_sc()
    ensures
        rm_in_lv(t_x()) && !sc_in_rm(t_x()),
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![cbe()], key: None }, v1()),
        sys_step(v1(), BizL::Open { p: 0, t: t_x() }, v2()),
        sys_step(v2(), BizL::Start { p: 0, fresh: true }, v3()),
        sys_step(v3(), BizL::Scan { p: 0 }, v4()),
        sys_step(v4(), BizL::Scan { p: 0 }, v5()),
        sys_step(v5(), BizL::ToFinal { p: 0 }, v6()),
        sys_step(v6(), BizL::Final { p: 0, ok: true }, v7()),
        v6().st.stmts.contains(kbe()),
        kbe().edge && v7().st.rows.contains_key(kbe()) && !v7().st.stmts.contains(kbe()) && !v7().st.unrec.contains(kbe()),
        v7().st.erasing is None,
        !biz_inv(v7()),
{
    assert(member(t_x().sc, kbe()) && kbe().edge && !member(t_x().rm, kbe()));
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, cbe());
    assert(v1().st.rows =~= Map::<Key, int>::empty().insert(kbe(), 7));
    assert(v1().st.stmts =~= Set::<Key>::empty().insert(kbe()));
    assert(sys_step(w0(), BizL::Commit { cs: seq![cbe()], key: None }, v1()));
    assert(sys_step(v1(), BizL::Open { p: 0, t: t_x() }, v2()));
    if live_in(v2().st.rows, t_x().lv) {
        let k = choose|k: Key| #[trigger] v2().st.rows.contains_key(k) && member(t_x().lv, k);
        assert(k == kbe());
    }
    assert(tgt_of(v2().rl.r, 0) == t_x());
    assert(v2().rl.l.hist.len() == 1);
    assert(sys_step(v2(), BizL::Start { p: 0, fresh: true }, v3()));
    let c3 = pcur(v3().rl.r, 0);
    assert(c3 == Cur { t: dom_a(), i: 0, j: 0, end: 1 });
    assert(v3().rl.l.hist[0][0] == Rec::Live(cbe()));
    assert(!hit(v3().rl.l, c3));
    assert(sys_step(v3(), BizL::Scan { p: 0 }, v4()));
    let c4 = pcur(v4().rl.r, 0);
    assert(c4 == Cur { t: dom_a(), i: 0, j: 1, end: 1 });
    assert(row_end(v4().rl.l, c4));
    assert(sys_step(v4(), BizL::Scan { p: 0 }, v5()));
    assert(sys_step(v5(), BizL::ToFinal { p: 0 }, v6()));
    assert(tgt_of(v6().rl.r, 0) == t_x());
    assert(!live_in(v6().st.rows, t_x().lv));
    assert(sys_step(v6(), BizL::Final { p: 0, ok: true }, v7()));
    assert(!v7().st.stmts.contains(kbe()));
    assert(!c_stmt_ok(v7(), kbe()));
    assert(!key_ok(v7(), kbe()));
}

} // verus!
