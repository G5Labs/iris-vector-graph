//! Proved counterexample for control `control_f1201_erase_unlocked` (F-1201, regression of an original guard in the
//! generalised model), compiled only with that feature.
//!
//! With the eraser taking no head lock, the composed participant contracts run, from the initial state: the erasure
//! of tenant A deletes A's rows (its transaction open); a ledger commit creates an edge of A (the lock is free); the
//! erasure's statement cleanup kills the new edge's statement entry; the erasure commits. No erasure is open, the
//! edge is live with recorded content, and it has no statement entry. (Original `proofs/src/cx_f1201.rs`; explorer
//! `erasure-as-built`; core model `m2-as-built-F1201-stmt`.)
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

pub open spec fn f1() -> BizS { BizS { st: store_erase_rows(w0().st, dom_a()), ..w0() } }
pub open spec fn f2() -> BizS {
    BizS { rl: RLS { l: ledger_commit(f1().rl.l, seq![ca()], None), r: f1().rl.r }, st: store_apply(f1().st, seq![ca()]), ..f1() }
}
pub open spec fn f3() -> BizS { BizS { st: store_erase_index(f2().st), ..f2() } }
pub open spec fn f4() -> BizS { BizS { st: store_erase_commit(f3().st), pend: f3().pend.insert(dom_a()), ..f3() } }

pub proof fn counterexample_f1201()
    ensures
        Biz::init(w0()),
        sys_step(w0(), BizL::EraseRows { e: dom_a() }, f1()),
        sys_step(f1(), BizL::Commit { cs: seq![ca()], key: None }, f2()),
        sys_step(f2(), BizL::EraseIndex, f3()),
        sys_step(f3(), BizL::EraseCommit, f4()),
        ka().edge && f4().st.rows.contains_key(ka()) && !f4().st.stmts.contains(ka()) && !f4().st.unrec.contains(ka()),
        f4().st.erasing is None,
        !biz_inv(f4()),
{
    lemma_one(f1().st.rows, f1().st.stmts, f1().st.unrec, ca());
    assert(sys_step(w0(), BizL::EraseRows { e: dom_a() }, f1()));
    assert(sys_step(f1(), BizL::Commit { cs: seq![ca()], key: None }, f2()));
    assert(f2().st.rows.contains_key(ka()));
    assert(f2().st.stmts.contains(ka()));
    assert(sys_step(f2(), BizL::EraseIndex, f3()));
    assert(sys_step(f3(), BizL::EraseCommit, f4()));
    assert(!f4().st.stmts.contains(ka()));
    assert(!c_stmt_ok(f4(), ka()));
    assert(!key_ok(f4(), ka()));
}

} // verus!
