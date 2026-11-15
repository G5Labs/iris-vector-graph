//! Proved counterexample for control `control_unaligned_rm` (F-1304; also the shape of F-C1308), compiled only with
//! that feature.
//!
//! The target is the pin's `redact(None)` with no prefix: record match = every node record (they carry graph "",
//! LedgerGenesis.cls:14-20, and Matches returns 1 for them, LedgerRedact.cls:93-94) and the default graph's
//! relationship records; liveness = rows of the default graph only (LiveRows, cls:157-158); statement cleanup = the
//! default graph's statements. Record match is not inside liveness. From the initial state: a node of named graph 1 is
//! committed (its record describes that row); the redaction of the target opens and starts — nothing of the default
//! graph is live — and its first batch tombstones the node's record while the node is live in graph 1.
//! (Live on the pin: `live-native-rerun-1314`, `ib-HD1303-nopfx-default`; core model `m1-as-built-F1304`. F-C1308 is
//! the same shape with temporal-only edges: Matches matches their records, LiveRows does not count them.)
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

pub open spec fn t_d() -> Tgt {
    Tgt { rm: |k: Key| !k.edge || k.g == 0, lv: |k: Key| k.g == 0, sc: |k: Key| k.g == 0 }
}
pub open spec fn kn() -> Key { Key { g: 1, id: 1, edge: false } }
pub open spec fn cn() -> Content { Content { k: kn(), eff: Eff::Put(5) } }

pub open spec fn u1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![cn()], keys(seq![cn()]), None), r: w0().rl.r }, st: store_apply(w0().st, seq![cn()]), ..w0() }
}
pub open spec fn u2() -> BizS { BizS { rl: RLS { l: u1().rl.l, r: red_step(u1().rl.r, RedL::Open { p: 0, t: t_d() }) }, ..u1() } }
pub open spec fn u3() -> BizS {
    BizS { rl: RLS { l: ledger_mark(u2().rl.l, t_d()), r: red_step(u2().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 1 }) },
           pend: u2().pend.insert(t_d().rm), ..u2() }
}
pub open spec fn u4() -> BizS {
    BizS { rl: RLS { l: ledger_batch(u3().rl.l, 0, 0, t_d(), true, 0, 1), r: red_step(u3().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..u3() }
}

pub proof fn counterexample_unaligned_rm()
    ensures
        !rm_in_lv(t_d()) && sc_in_rm(t_d()),
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![cn()], named: keys(seq![cn()]), key: None }, u1()),
        sys_step(u1(), BizL::Open { p: 0, t: t_d() }, u2()),
        sys_step(u2(), BizL::Start { p: 0, fresh: true }, u3()),
        sys_step(u3(), BizL::Scan { p: 0 }, u4()),
        u3().rl.l.hist[0][0] == Rec::Live(cn()) && u4().rl.l.hist[0][0] == Rec::Tomb(cn()),
        u3().st.rows.contains_key(kn()) && !u3().st.unrec.contains(kn()) && u4().st.rows.contains_key(kn()),
        rec_content(u3(), kn()) && rec_content(u4(), kn()),
        !biz_inv(u3()), !biz_inv(u4()),
{
    assert(member(t_d().rm, kn()) && !member(t_d().lv, kn()));
    assert forall|k: Key| #[trigger] member(t_d().sc, k) && k.edge implies member(t_d().rm, k) by {}
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, cn());
    assert(u1().st.rows =~= Map::<Key, int>::empty().insert(kn(), 5));
    assert(sys_step(w0(), BizL::Commit { cs: seq![cn()], named: keys(seq![cn()]), key: None }, u1()));
    assert(sys_step(u1(), BizL::Open { p: 0, t: t_d() }, u2()));
    if live_in(u2().st.rows, t_d().lv) {
        let k = choose|k: Key| #[trigger] u2().st.rows.contains_key(k) && member(t_d().lv, k);
        assert(k == kn());
    }
    assert(tgt_of(u2().rl.r, 0) == t_d());
    assert(u2().rl.l.hist.len() == 1);
    assert(sys_step(u2(), BizL::Start { p: 0, fresh: true }, u3()));
    let c3 = pcur(u3().rl.r, 0);
    assert(c3 == Cur { t: t_d().rm, i: 0, j: 0, end: 1 });
    assert(u3().rl.l.hist[0][0] == Rec::Live(cn()));
    assert(hit(u3().rl.l, c3));
    assert(sys_step(u3(), BizL::Scan { p: 0 }, u4()));
    assert(u4().rl.l.hist[0][0] == Rec::Tomb(cn()));
    assert(crow(u3(), kn()) == Some(5int));
    assert(!mark_key_ok(u3(), kn()));
    assert(!key_ok(u3(), kn()));
    assert(crow(u4(), kn()) == Some(5int));
    assert(!mark_key_ok(u4(), kn()));
    assert(!key_ok(u4(), kn()));
}

} // verus!
