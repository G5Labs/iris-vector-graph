//! Proved counterexample for control `control_f1614_app_without_key_gate` (F-1614), compiled only with it.
//!
//! The live trace c16-s8-followup: the demo server started with IVG_API_KEY set; without the key, POST
//! /api/fhir/live/add reached the route's validation (400, not 401). Here a write from another machine without the
//! key runs route code (not an L1 step: with a key set, no route code runs without it).
use vstd::prelude::*;
use actors::protocol::*;
use crate::auth_l1::*;
use crate::auth_l2::*;

verus! {

pub open spec fn x0() -> A2 { A2 { cfg: Cfg { key: Some(7), ro: false, host: Host::Any }, via_cli: false, bolt: None, runs: 0, writes: 0 } }
pub open spec fn xr() -> Req { Req { remote: true, shown: None, public: false, kind: Kind::Write, graph: 0 } }
pub open spec fn x1() -> A2 { A2 { runs: 1, writes: 1, ..x0() } }

pub proof fn counterexample_f1614()
    ensures
        init2(x0()),
        step2(x0(), AL2::Http { r: xr(), st: Status::Ran }, x1()),
        !step_or_stutter::<AuthL1>(absa(x0()), laba(AL2::Http { r: xr(), st: Status::Ran }), absa(x1())),
        decide(x0().cfg, xr()) is Unauthorized,
{
}

} // verus!
