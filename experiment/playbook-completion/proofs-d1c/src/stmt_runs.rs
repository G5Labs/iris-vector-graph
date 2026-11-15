//! The statement L2 machine's steps as functions (valid under every feature), used by the witness and the
//! counterexample. The triple is 5.
use vstd::prelude::*;
use crate::stmt_l2::*;

verus! {

pub open spec fn s0() -> SS2 { SS2 { rows: Map::empty(), next_id: 0, stmt: Map::empty(), next_stmt: 0, tuple: Map::empty() } }
pub open spec fn p_lcreate(s: SS2, k: int) -> SS2 {
    SS2 { rows: s.rows.insert(k, s.next_id), next_id: s.next_id + 1,
          stmt: s.stmt.insert(s.next_stmt, SR { k, life: s.next_id, live: true }), next_stmt: s.next_stmt + 1,
          tuple: s.tuple.insert(k, s.next_stmt) }
}
pub open spec fn i_lupdate(s: SS2, k: int) -> nat { if !s.tuple.contains_key(k) { s.next_stmt } else { s.tuple[k] } }
pub open spec fn p_lupdate(s: SS2, k: int) -> SS2 {
    if !s.tuple.contains_key(k) {
        SS2 { stmt: s.stmt.insert(s.next_stmt, SR { k, life: s.rows[k], live: true }), next_stmt: s.next_stmt + 1,
              tuple: s.tuple.insert(k, s.next_stmt), ..s }
    } else { s }
}
pub open spec fn p_ldelete(s: SS2, k: int) -> SS2 {
    SS2 { rows: s.rows.remove(k), stmt: s.stmt.insert(s.tuple[k], SR { live: false, ..s.stmt[s.tuple[k]] }), tuple: s.tuple.remove(k), ..s }
}
pub open spec fn p_dcreate(s: SS2, k: int) -> SS2 { SS2 { rows: s.rows.insert(k, s.next_id), next_id: s.next_id + 1, ..s } }
pub open spec fn p_ddelete(s: SS2, k: int) -> SS2 { if f0303() { SS2 { rows: s.rows.remove(k), ..s } } else { unlink(s, k) } }

pub proof fn lemma_s_steps(s: SS2, k: int)
    ensures
        !s.rows.contains_key(k) ==> step2(s, SL2::LCreate { k, id: s.next_stmt }, p_lcreate(s, k)),
        s.rows.contains_key(k) && (s.tuple.contains_key(k) ==> s.stmt.contains_key(s.tuple[k]) && s.stmt[s.tuple[k]].live)
            ==> step2(s, SL2::LUpdate { k, id: i_lupdate(s, k) }, p_lupdate(s, k)),
        s.rows.contains_key(k) && s.tuple.contains_key(k) && s.stmt.contains_key(s.tuple[k]) && s.stmt[s.tuple[k]].live
            ==> step2(s, SL2::LDelete { k, id: s.tuple[k] }, p_ldelete(s, k)),
        !s.rows.contains_key(k) ==> step2(s, SL2::DCreate { k }, p_dcreate(s, k)),
        s.rows.contains_key(k) ==> step2(s, SL2::DDelete { k }, p_ddelete(s, k)),
{
}

} // verus!
