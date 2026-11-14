//! Non-vacuity of the reviewed cyw model (compiled without its controls): relationship 1->2 is created; creating it
//! again with node 3 commits and adds node 3 only; node properties are set; the MERGE copies each row's node; a null SET
//! removes the key; another process sets strict mode: a write is refused (Strict), and one whose probe cannot run is
//! refused (Unavailable).
use vstd::prelude::*;
use crate::cyw_l1::*;
use crate::cyw_l2::*;
use crate::cyw_runs::*;

verus! {

pub open spec fn e12() -> Set<(int, int)> { Set::empty().insert((1int, 2int)) }
pub open spec fn q1() -> Q { Q::CreateLit { ns: Set::empty().insert(1int).insert(2int).insert(9int), es: e12() } }
pub open spec fn q2() -> Q { Q::CreateLit { ns: Set::empty().insert(3int), es: e12() } }
pub open spec fn qa() -> Q { Q::SetProp { n: 1, k: 7, v: Some(1) } }
pub open spec fn qb() -> Q { Q::SetProp { n: 2, k: 7, v: Some(2) } }
pub open spec fn rows() -> Set<(int, int)> { Set::empty().insert((1int, 9int)).insert((2int, 9int)) }
pub open spec fn qm() -> Q { Q::MergeCopy { rows: rows() } }
pub open spec fn qn() -> Q { Q::SetProp { n: 1, k: 7, v: None } }
pub open spec fn g1() -> CW2 { p_exec(c0(), q1(), true, (0, 0)) }
pub open spec fn g2() -> CW2 { p_exec(g1(), q2(), true, (0, 0)) }
pub open spec fn g3() -> CW2 { p_exec(g2(), qa(), true, (0, 0)) }
pub open spec fn g4() -> CW2 { p_exec(g3(), qb(), true, (0, 0)) }
pub open spec fn g5() -> CW2 { p_exec(g4(), qm(), true, (1, 9)) }
pub open spec fn g6() -> CW2 { p_exec(g5(), qn(), true, (0, 0)) }
pub open spec fn g7() -> CW2 { p_meta(g6(), true, true) }

pub proof fn witness_cyw()
    ensures
        init2(c0()),
        step2(c0(), CWL2::Exec { q: q1(), pok: true, top: (0, 0) }, g1()),
        step2(g1(), CWL2::Exec { q: q2(), pok: true, top: (0, 0) }, g2()),
        g2().edges == g1().edges && g2().nodes.contains(3),
        step2(g2(), CWL2::Exec { q: qa(), pok: true, top: (0, 0) }, g3()),
        step2(g3(), CWL2::Exec { q: qb(), pok: true, top: (0, 0) }, g4()),
        step2(g4(), CWL2::Exec { q: qm(), pok: true, top: (1, 9) }, g5()),
        g5().qual[(2, 9)] == pm(g4().props, 2) && g5().qual[(1, 9)] == pm(g4().props, 1),
        step2(g5(), CWL2::Exec { q: qn(), pok: true, top: (0, 0) }, g6()),
        !g6().props[1].contains_key(7),
        step2(g6(), CWL2::Meta { en: true, strict: true }, g7()),
        step2(g7(), CWL2::Refuse { q: q2(), pok: true, why: Why::Strict }, g7()),
        step2(g7(), CWL2::Refuse { q: q2(), pok: false, why: Why::Unavailable }, g7()),
{
    lemma_c_steps(c0(), q1(), true, (0, 0), false, false, Why::Env);
    assert(g1().edges.contains((1, 2)));
    lemma_c_steps(g1(), q2(), true, (0, 0), false, false, Why::Env);
    assert(g2().edges =~= g1().edges);
    assert(g2().nodes.contains(3));
    lemma_c_steps(g2(), qa(), true, (0, 0), false, false, Why::Env);
    assert(g2().nodes.contains(1) && g2().nodes.contains(2));
    lemma_c_steps(g3(), qb(), true, (0, 0), false, false, Why::Env);
    assert(g4().edges =~= e12());
    assert(rows().disjoint(g4().edges));
    lemma_c_steps(g4(), qm(), true, (1, 9), false, false, Why::Env);
    assert(g5().nodes.contains(1));
    lemma_c_steps(g5(), qn(), true, (0, 0), false, false, Why::Env);
    lemma_c_steps(g6(), qn(), true, (0, 0), true, true, Why::Env);
    lemma_c_steps(g7(), q2(), true, (0, 0), true, true, Why::Strict);
    lemma_c_steps(g7(), q2(), false, (0, 0), true, true, Why::Unavailable);
}

} // verus!
