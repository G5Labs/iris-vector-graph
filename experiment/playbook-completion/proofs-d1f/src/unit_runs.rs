//! The unit L2 machine's runs used by the witness and the counterexamples (valid under every feature): a Bolt unit
//! whose second RUN fails, is rolled back and retried by the driver, then commits; an HTTP tx/commit request whose
//! second statement fails.
use vstd::prelude::*;
use crate::unit_l2::*;

verus! {

pub open spec fn u0(e: Entry) -> U2 {
    U2 { entry: e, ph: Ph::Idle, w1: 0, w2: 0, b1: false, b2: false, last_failed: false, attempts: 0, units: 0 }
}
pub open spec fn b1() -> U2 { U2 { ph: Ph::Open, attempts: 1, ..u0(Entry::Bolt) } }
pub open spec fn b2() -> U2 { run1(b1()) }
pub open spec fn b3() -> U2 { run2_fail(b2()) }
pub open spec fn b4() -> U2 { rollback(b3()) }
pub open spec fn b5() -> U2 { retry(b4()) }
pub open spec fn b6() -> U2 { run1(b5()) }
pub open spec fn b7() -> U2 { run2_ok(b6()) }
pub open spec fn b8() -> U2 { commit(b7()) }
pub open spec fn h1() -> U2 { U2 { ph: Ph::Open, attempts: 1, ..u0(Entry::Http) } }
pub open spec fn h2() -> U2 { run1(h1()) }
pub open spec fn h3() -> U2 { run2_fail(h2()) }

} // verus!
