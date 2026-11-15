//! Proved counterexample for control `control_f0810_null_keeps_key` (F-0810), compiled only with it.
//!
//! The live check b-08-live-f0810: after SET n.z = null on b08_s, keys(n) = [id, z, name] and properties(n).z = ''.
//! Here: node 1 gets property 7 = 3; `SET n.7 = null` leaves key 7 with the empty value (not an L1 step: the key goes).
use vstd::prelude::*;
use actors::protocol::*;
use crate::cyw_l1::*;
use crate::cyw_l2::*;
use crate::cyw_runs::*;

verus! {

pub open spec fn q0() -> Q { Q::CreateLit { ns: Set::empty().insert(1int), es: Set::empty() } }
pub open spec fn qs() -> Q { Q::SetProp { n: 1, k: 7, v: Some(3) } }
pub open spec fn qn() -> Q { Q::SetProp { n: 1, k: 7, v: None } }
pub open spec fn n1() -> CW2 { p_exec(c0(), q0(), true, (0, 0)) }
pub open spec fn n2() -> CW2 { p_exec(n1(), qs(), true, (0, 0)) }
pub open spec fn n3() -> CW2 { p_exec(n2(), qn(), true, (0, 0)) }

pub proof fn counterexample_f0810()
    ensures
        init2(c0()),
        step2(c0(), CWL2::Exec { q: q0(), pok: true, top: (0, 0) }, n1()),
        step2(n1(), CWL2::Exec { q: qs(), pok: true, top: (0, 0) }, n2()),
        step2(n2(), CWL2::Exec { q: qn(), pok: true, top: (0, 0) }, n3()),
        n3().props[1].contains_key(7) && n3().props[1][7] == Val::Empty,
        !step_or_stutter::<CwL1>(absc(n2()), labc(CWL2::Exec { q: qn(), pok: true, top: (0, 0) }), absc(n3())),
{
    lemma_c_steps(c0(), q0(), true, (0, 0), false, false, Why::Env);
    lemma_c_steps(n1(), qs(), true, (0, 0), false, false, Why::Env);
    assert(n1().nodes.contains(1));
    lemma_c_steps(n2(), qn(), true, (0, 0), false, false, Why::Env);
    assert(n3().props[1].contains_key(7));
    assert(!apply(absc(n2()), qn()).props[1].contains_key(7));
}

} // verus!
