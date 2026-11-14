//! Proved counterexample for control `control_fc0301_adopt_after_commit` (F-C0301), compiled only with it.
//!
//! The source reading of F-C0301 (nodes_edges.py:1236-1252): create_edge over a temporal edge's marked row finds the
//! triple, commits, and only then runs `_adopt_temporal_row`; a last temporal delete in between retracts the marked
//! row, the adopt finds no row and the call answers False (a duplicate) with no edge at all. The answer is not an L1
//! step. (Confirmed in source at the audit; this run makes it reproduced in the model.)
use vstd::prelude::*;
use actors::protocol::*;
use crate::edge_l1::*;
use crate::edge_l2::*;
use crate::edge_runs::*;

verus! {

pub open spec fn e10() -> Ev { Ev { k: k1(), ts: 10 } }
pub open spec fn x0() -> ES2 { e0(Set::empty()) }
pub open spec fn x1() -> ES2 { p_tinsert(x0(), k1(), 10) }
pub open spec fn x2() -> ES2 { p_cinsert(x1(), 0, k1(), Q::Plain) }
pub open spec fn x3() -> ES2 { p_tdelete(x2(), k1(), 10) }
pub open spec fn x4() -> ES2 { p_cadopt(x3(), 0) }

pub proof fn counterexample_fc0301()
    ensures
        init2(x0()),
        step2(x0(), EL2::TInsert { k: k1(), ts: 10 }, x1()),
        step2(x1(), EL2::CInsert { c: 0, k: k1(), q: Q::Plain, res: None }, x2()),
        step2(x2(), EL2::TDelete { k: k1(), ts: 10 }, x3()),
        step2(x3(), EL2::CAdopt { c: 0, k: k1(), ans: false }, x4()),
        !step_or_stutter::<EdgeL1>(abse(x3()), labe(EL2::CAdopt { c: 0, k: k1(), ans: false }), abse(x4())),
        !x4().rows.contains_key(k1()) && !x4().out.contains(k1()),
{
    lemma_p_tinsert(x0(), k1(), 10);
    assert(x1().rows.contains_key(k1()) && x1().rows[k1()] is Marked);
    assert(r_cinsert(x1(), k1()) == None::<bool>);
    lemma_p_cinsert(x1(), 0, k1(), Q::Plain);
    assert(x2().tout.contains(e10()));
    lemma_p_tdelete(x2(), k1(), 10);
    assert(x2().tout.remove(e10()) =~= Set::<Ev>::empty());
    assert(!has_ts(x2().tout.remove(e10()), k1()));
    assert(!x3().rows.contains_key(k1()));
    assert(x3().pend.contains_key(0) && x3().pend[0].k == k1());
    lemma_p_cadopt(x3(), 0);
    assert(!a_cadopt(x3(), 0));
    assert(!abse(x3()).edges.contains_key(k1()));
    assert(!abse(x4()).edges.contains_key(k1()));
}

} // verus!
