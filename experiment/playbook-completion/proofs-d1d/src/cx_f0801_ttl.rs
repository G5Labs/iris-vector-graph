//! Proved counterexample for control `control_f0801_ttl_window` (F-0801, the 5 s window), compiled only with it.
//!
//! The live check b-08-live-f0801: process A's engine wrote once (guard cached never-enabled); process B enabled the
//! ledger and set strict; 0.28 s later A's `CREATE (:B08G {id:'b08_g1'})` succeeded. Here: a write caches Meta
//! (disabled); another process enables strict mode; within the TTL the next write passes the guard from its cache and
//! commits (not an L1 step: in strict mode no write query commits).
use vstd::prelude::*;
use actors::protocol::*;
use crate::cyw_l1::*;
use crate::cyw_l2::*;
use crate::cyw_runs::*;

verus! {

pub open spec fn q1() -> Q { Q::CreateLit { ns: Set::empty().insert(1int), es: Set::empty() } }
pub open spec fn q2() -> Q { Q::CreateLit { ns: Set::empty().insert(2int), es: Set::empty() } }
pub open spec fn x1() -> CW2 { p_exec(c0(), q1(), true, (0, 0)) }
pub open spec fn x2() -> CW2 { p_meta(x1(), true, true) }
pub open spec fn x3() -> CW2 { p_exec(x2(), q2(), true, (0, 0)) }

pub proof fn counterexample_f0801_ttl()
    ensures
        init2(c0()),
        step2(c0(), CWL2::Exec { q: q1(), pok: true, top: (0, 0) }, x1()),
        step2(x1(), CWL2::Meta { en: true, strict: true }, x2()),
        step2(x2(), CWL2::Exec { q: q2(), pok: true, top: (0, 0) }, x3()),
        x3().nodes.contains(2),
        !step_or_stutter::<CwL1>(absc(x2()), labc(CWL2::Exec { q: q2(), pok: true, top: (0, 0) }), absc(x3())),
{
    lemma_c_steps(c0(), q1(), true, (0, 0), true, true, Why::Env);
    lemma_c_steps(x1(), q1(), true, (0, 0), true, true, Why::Env);
    assert(x2().cache == Some((false, false)) && x2().fresh);
    lemma_c_steps(x2(), q2(), true, (0, 0), true, true, Why::Env);
    assert(x3().nodes.contains(2));
}

} // verus!
