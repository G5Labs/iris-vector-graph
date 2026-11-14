//! Proved counterexample for control `control_sc_narrow` (D-9b: side-condition part `rm ⊆ sc` on edges dropped),
//! compiled only with that feature. Not a finding at the pin (Matches and DropStatements coincide on relationships):
//! it shows that the statement-history theorem needs the guard.
//!
//! A target whose statement cleanup misses an edge its record match owns (`t_n`: cleanup selects nothing). From the
//! initial state: tenant A's edge is created and then deleted (its statement entry is now closed, holding the edge's
//! endpoints and graph); the redaction of A opens, starts (nothing of A live), tombstones both records and completes;
//! its cleanup leaves the closed entry. A complete redaction leaves tenant data in the statement history (SC-001 for
//! `^IVG.Ledger("stmt")`), and the business invariants fail from the marking on (the marked target is not aligned).
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

pub open spec fn t_n() -> Tgt { Tgt { rm: dom_a(), lv: dom_a(), sc: |k: Key| false } }
pub open spec fn cd() -> Content { Content { k: ka(), eff: Eff::Del } }

pub open spec fn v1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![ca()], keys(seq![ca()]), None), r: w0().rl.r }, st: store_apply(w0().st, seq![ca()]), ..w0() }
}
pub open spec fn v2() -> BizS {
    BizS { rl: RLS { l: ledger_commit(v1().rl.l, seq![cd()], keys(seq![cd()]), None), r: v1().rl.r }, st: store_apply(v1().st, seq![cd()]), ..v1() }
}
pub open spec fn v3() -> BizS { BizS { rl: RLS { l: v2().rl.l, r: red_step(v2().rl.r, RedL::Open { p: 0, t: t_n() }) }, ..v2() } }
pub open spec fn v4() -> BizS {
    BizS { rl: RLS { l: ledger_mark(v3().rl.l, t_n()), r: red_step(v3().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 2 }) },
           pend: v3().pend.insert(dom_a()), ..v3() }
}
pub open spec fn v5() -> BizS {
    BizS { rl: RLS { l: ledger_batch(v4().rl.l, 0, 0, t_n(), true, 0, 1), r: red_step(v4().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..v4() }
}
pub open spec fn v6() -> BizS {
    BizS { rl: RLS { l: ledger_batch(v5().rl.l, 0, 1, t_n(), false, 1, 0), r: red_step(v5().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..v5() }
}
pub open spec fn v7() -> BizS {
    BizS { rl: RLS { l: ledger_batch(v6().rl.l, 1, 0, t_n(), true, 1, 1), r: red_step(v6().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..v6() }
}
pub open spec fn v8() -> BizS {
    BizS { rl: RLS { l: ledger_batch(v7().rl.l, 1, 1, t_n(), false, 2, 0), r: red_step(v7().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..v7() }
}
pub open spec fn v9() -> BizS { BizS { rl: RLS { l: v8().rl.l, r: red_step(v8().rl.r, RedL::ToFinal { p: 0 }) }, ..v8() } }
pub open spec fn v10() -> BizS {
    BizS {
        rl: RLS { l: ledger_audit(v9().rl.l, t_n()), r: red_step(v9().rl.r, RedL::Finish { p: 0 }) },
        st: store_drop(v9().st, t_n().sc),
        pend: v9().pend.filter(|d: Dom| !covers(t_n().rm, d)),
        wr: v9().wr,
    }
}

pub proof fn counterexample_sc_narrow()
    ensures
        rm_in_lv(t_n()) && sc_in_rm(t_n()) && !rm_in_sc(t_n()),
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None }, v1()),
        sys_step(v1(), BizL::Commit { cs: seq![cd()], named: keys(seq![cd()]), key: None }, v2()),
        sys_step(v2(), BizL::Open { p: 0, t: t_n() }, v3()),
        sys_step(v3(), BizL::Start { p: 0, fresh: true }, v4()),
        sys_step(v4(), BizL::Scan { p: 0 }, v5()),
        sys_step(v5(), BizL::Scan { p: 0 }, v6()),
        sys_step(v6(), BizL::Scan { p: 0 }, v7()),
        sys_step(v7(), BizL::Scan { p: 0 }, v8()),
        sys_step(v8(), BizL::ToFinal { p: 0 }, v9()),
        sys_step(v9(), BizL::Final { p: 0, ok: true }, v10()),
        // A's edge was deleted: its statement entry is closed, not live ...
        !v2().st.rows.contains_key(ka()) && !v2().st.stmts.contains(ka()) && v2().st.shist.contains(ka()),
        // ... the redaction completed with both records tombstoned, and the closed entry is still there.
        v10().rl.l.marker is None && v10().rl.l.hist[0][0] == Rec::Tomb(ca()) && v10().rl.l.hist[1][0] == Rec::Tomb(cd()),
        member(t_n().rm, ka()) && ka().edge && v10().st.shist.contains(ka()),
        !biz_inv(v4()),
{
    assert(member(t_n().rm, ka()) && ka().edge && !member(t_n().sc, ka()));
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, ca());
    lemma_one_sh(w0().st.shist, ca());
    assert(v1().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5));
    assert(v1().st.shist =~= Set::<Key>::empty().insert(ka()));
    assert(sys_step(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: None }, v1()));
    lemma_one(v1().st.rows, v1().st.stmts, v1().st.unrec, cd());
    lemma_one_sh(v1().st.shist, cd());
    assert(v2().st.rows =~= Map::<Key, int>::empty());
    assert(v2().st.shist =~= Set::<Key>::empty().insert(ka()));
    assert(!v2().st.stmts.contains(ka()));
    assert(sys_step(v1(), BizL::Commit { cs: seq![cd()], named: keys(seq![cd()]), key: None }, v2()));
    assert(sys_step(v2(), BizL::Open { p: 0, t: t_n() }, v3()));
    assert(!live_in(v3().st.rows, t_n().lv));
    assert(tgt_of(v3().rl.r, 0) == t_n());
    assert(v3().rl.l.hist.len() == 2);
    assert(sys_step(v3(), BizL::Start { p: 0, fresh: true }, v4()));
    assert(!aligned(t_n()));
    assert(!mark_ok(v4()));
    let c4 = pcur(v4().rl.r, 0);
    assert(c4 == Cur { t: dom_a(), i: 0, j: 0, end: 2 });
    assert(v4().rl.l.hist[0][0] == Rec::Live(ca()));
    assert(hit(v4().rl.l, c4));
    assert(sys_step(v4(), BizL::Scan { p: 0 }, v5()));
    assert(row_end(v5().rl.l, pcur(v5().rl.r, 0)));
    assert(sys_step(v5(), BizL::Scan { p: 0 }, v6()));
    let c6 = pcur(v6().rl.r, 0);
    assert(c6 == Cur { t: dom_a(), i: 1, j: 0, end: 2 });
    assert(v6().rl.l.hist[1] == lives(seq![cd()]));
    assert(v6().rl.l.hist[1][0] == Rec::Live(cd()));
    assert(hit(v6().rl.l, c6));
    assert(sys_step(v6(), BizL::Scan { p: 0 }, v7()));
    assert(row_end(v7().rl.l, pcur(v7().rl.r, 0)));
    assert(sys_step(v7(), BizL::Scan { p: 0 }, v8()));
    assert(sys_step(v8(), BizL::ToFinal { p: 0 }, v9()));
    assert(tgt_of(v9().rl.r, 0) == t_n());
    assert(!live_in(v9().st.rows, t_n().lv));
    assert(sys_step(v9(), BizL::Final { p: 0, ok: true }, v10()));
    assert(v10().st.shist.contains(ka()));
}

} // verus!
