//! Proved counterexample for control `control_f0805_literal_insert_unguarded` (F-0805), compiled only with it.
//!
//! The live check b-08-live-f0805: after `CREATE (a:B08D {id:'b08_d1'})-[:B08T]->(b:B08D {id:'b08_d2'})`, the query
//! `CREATE (c:B08D {id:'b08_d3'}), (a ...)-[:B08T]->(b ...)` raised SQLCODE -119 and node b08_d3 was rolled back.
//! Here: relationship 1->2 is created; a query creating node 3 and 1->2 again is refused for the duplicate (not an L1
//! step: such a query adds nothing for the existing relationship and does not fail), and node 3 is not written.
use vstd::prelude::*;
use actors::protocol::*;
use crate::cyw_l1::*;
use crate::cyw_l2::*;
use crate::cyw_runs::*;

verus! {

pub open spec fn e12() -> Set<(int, int)> { Set::empty().insert((1int, 2int)) }
pub open spec fn q1() -> Q { Q::CreateLit { ns: Set::empty().insert(1int).insert(2int), es: e12() } }
pub open spec fn q2() -> Q { Q::CreateLit { ns: Set::empty().insert(3int), es: e12() } }
pub open spec fn z1() -> CW2 { p_exec(c0(), q1(), true, (0, 0)) }
pub open spec fn z2() -> CW2 { guarded(z1(), true) }

pub proof fn counterexample_f0805()
    ensures
        init2(c0()),
        step2(c0(), CWL2::Exec { q: q1(), pok: true, top: (0, 0) }, z1()),
        step2(z1(), CWL2::Refuse { q: q2(), pok: true, why: Why::Dup }, z2()),
        !step_or_stutter::<CwL1>(absc(z1()), labc(CWL2::Refuse { q: q2(), pok: true, why: Why::Dup }), absc(z2())),
        !z2().nodes.contains(3),
{
    lemma_c_steps(c0(), q1(), true, (0, 0), false, false, Why::Dup);
    assert(e12().disjoint(c0().edges));
    assert(z1().edges.contains((1, 2)));
    assert(!e12().disjoint(z1().edges));
    lemma_c_steps(z1(), q2(), true, (0, 0), false, false, Why::Dup);
}

} // verus!
