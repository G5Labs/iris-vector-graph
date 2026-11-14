//! Proved counterexample for control `control_f1201_erase_unlocked` (F-1201), compiled only with that feature.
//!
//! With the eraser not taking the head lock, the composed participant contracts (`system::sys_step`) run, from the
//! initial state: the erasure of tenant A deletes A's rows; a commit creates an edge of A (the ledger's lock is free);
//! the erasure's statement cleanup removes the new edge's statement entry. Then no erasure is open, the edge is live,
//! and it has no statement entry: "statement entries match live edges" fails, and so do the business invariants.
//! (Explorer counterexample `erasure-as-built`, 5 steps, in the original submission.)
use vstd::prelude::*;
use actors::protocol::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::protocol_rl::*;
use crate::biz::*;
use crate::system::*;
use crate::witness::*;

verus! {

pub open spec fn c0() -> BizS { w0() }
pub open spec fn c1() -> BizS { BizS { st: store_erase_rows(c0().st, tenant_a()), pend: c0().pend.insert(tenant_a()), ..c0() } }
pub open spec fn c2() -> BizS {
    BizS { rl: RLS { l: ledger_commit(c1().rl.l, seq![ca()], None), r: c1().rl.r }, st: store_apply(c1().st, seq![ca()]), ..c1() }
}
pub open spec fn c3() -> BizS { BizS { st: store_erase_index(c2().st, tenant_a()), ..c2() } }

pub proof fn counterexample_f1201()
    ensures
        Biz::init(c0()),
        sys_step(c0(), BizL::EraseRows { t: tenant_a() }, c1()),
        sys_step(c1(), BizL::Commit { cs: seq![ca()], key: None }, c2()),
        sys_step(c2(), BizL::EraseIndex { t: tenant_a() }, c3()),
        c3().st.erasing is None && ka().edge && c3().st.rows.contains_key(ka()) && !c3().st.stmts.contains(ka()),
        !biz_inv(c3()),
{
    let t = tenant_a();
    let rs = lives(seq![ca()]);
    assert(rs.drop_last() =~= Seq::<Rec>::empty());
    assert(rs.last() == Rec::Live(ca()));
    assert(sys_step(c0(), BizL::EraseRows { t }, c1()));
    assert(sys_step(c1(), BizL::Commit { cs: seq![ca()], key: None }, c2()));
    assert(c2().st.rows.contains_key(ka()));
    assert(sys_step(c2(), BizL::EraseIndex { t }, c3()));
    assert(member(t, ka()));
    assert(!c3().st.stmts.contains(ka()));
    assert(!in_erasing(c3().st.erasing)(ka()));
    assert(!inv_stmts(c3()));
}

} // verus!
