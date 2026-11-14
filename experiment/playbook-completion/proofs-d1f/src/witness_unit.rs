//! Non-vacuity of the reviewed unit model (compiled without its controls): a Bolt unit whose second RUN fails is
//! rolled back (nothing visible) and the driver's retry commits it once, both writes visible together; an HTTP
//! tx/commit request whose second statement fails publishes nothing.
use vstd::prelude::*;
use crate::unit_l1::*;
use crate::unit_l2::*;
use crate::unit_runs::*;

verus! {

pub proof fn witness_unit()
    ensures
        init2(u0(Entry::Bolt)), init2(u0(Entry::Http)),
        step2(u0(Entry::Bolt), UL2::Begin, b1()),
        step2(b1(), UL2::Run1, b2()),
        step2(b2(), UL2::Run2 { ok: false, http: false }, b3()),
        step2(b3(), UL2::Rollback, b4()),
        step2(b4(), UL2::Read { a: 0, b: 0 }, b4()),
        step2(b4(), UL2::Retry, b5()),
        step2(b5(), UL2::Run1, b6()),
        step2(b6(), UL2::Run2 { ok: true, http: false }, b7()),
        step2(b7(), UL2::Read { a: 0, b: 0 }, b7()),
        step2(b7(), UL2::Commit, b8()),
        step2(b8(), UL2::Read { a: 1, b: 1 }, b8()),
        step2(u0(Entry::Http), UL2::Begin, h1()),
        step2(h1(), UL2::Run1, h2()),
        step2(h2(), UL2::Run2 { ok: false, http: true }, h3()),
        step2(h3(), UL2::Read { a: 0, b: 0 }, h3()),
{
}

} // verus!
