//! Proved counterexample for control `control_fc0803_top1_copy` (F-C0803), compiled only with it.
//!
//! The live check b-08-live-storage-order: `MATCH (a:B08PP), (t:B08TT {id:'b08_tt'}) MERGE (a)-[r:B08MR3]->(t) ON
//! CREATE SET r = a` with a = b08_p1 {pop: 1} and b08_p2 {pop: 2} gave both relationships b08_p1's properties. Here:
//! nodes 1, 2, 9; node 1 has property 7 = 1 and node 2 has 7 = 2; the MERGE over rows (1, 9) and (2, 9), with TOP 1
//! returning row (1, 9), gives relationship 2->9 node 1's properties (not an L1 step).
use vstd::prelude::*;
use actors::protocol::*;
use crate::cyw_l1::*;
use crate::cyw_l2::*;
use crate::cyw_runs::*;

verus! {

pub open spec fn q0() -> Q { Q::CreateLit { ns: Set::empty().insert(1int).insert(2int).insert(9int), es: Set::empty() } }
pub open spec fn qa() -> Q { Q::SetProp { n: 1, k: 7, v: Some(1) } }
pub open spec fn qb() -> Q { Q::SetProp { n: 2, k: 7, v: Some(2) } }
pub open spec fn rows() -> Set<(int, int)> { Set::empty().insert((1int, 9int)).insert((2int, 9int)) }
pub open spec fn qm() -> Q { Q::MergeCopy { rows: rows() } }
pub open spec fn m1() -> CW2 { p_exec(c0(), q0(), true, (0, 0)) }
pub open spec fn m2() -> CW2 { p_exec(m1(), qa(), true, (0, 0)) }
pub open spec fn m3() -> CW2 { p_exec(m2(), qb(), true, (0, 0)) }
pub open spec fn m4() -> CW2 { p_exec(m3(), qm(), true, (1, 9)) }

pub proof fn counterexample_fc0803()
    ensures
        init2(c0()),
        step2(c0(), CWL2::Exec { q: q0(), pok: true, top: (0, 0) }, m1()),
        step2(m1(), CWL2::Exec { q: qa(), pok: true, top: (0, 0) }, m2()),
        step2(m2(), CWL2::Exec { q: qb(), pok: true, top: (0, 0) }, m3()),
        step2(m3(), CWL2::Exec { q: qm(), pok: true, top: (1, 9) }, m4()),
        m4().qual[(2, 9)] == pm(m3().props, 1) && pm(m3().props, 1) != pm(m3().props, 2),
        !step_or_stutter::<CwL1>(absc(m3()), labc(CWL2::Exec { q: qm(), pok: true, top: (1, 9) }), absc(m4())),
{
    lemma_c_steps(c0(), q0(), true, (0, 0), false, false, Why::Env);
    lemma_c_steps(m1(), qa(), true, (0, 0), false, false, Why::Env);
    assert(m1().nodes.contains(1) && m1().nodes.contains(2));
    lemma_c_steps(m2(), qb(), true, (0, 0), false, false, Why::Env);
    assert(m3().edges =~= Set::<(int, int)>::empty());
    assert(rows().disjoint(m3().edges));
    lemma_c_steps(m3(), qm(), true, (1, 9), false, false, Why::Env);
    assert(pm(m3().props, 1)[7] == Val::Int(1));
    assert(pm(m3().props, 2)[7] == Val::Int(2));
    assert(m4().qual[(2, 9)] == pm(m3().props, 1));
    assert(apply(absc(m3()), qm()).qual[(2, 9)] == pm(m3().props, 2));
}

} // verus!
