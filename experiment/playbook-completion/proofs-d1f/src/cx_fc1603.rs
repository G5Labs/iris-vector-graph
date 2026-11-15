//! Proved counterexample for control `control_fc1603_bolt_binds_every_interface` (F-C1603), compiled only with it.
//!
//! The live probe c16-s6-status-maps: `uvicorn iris_vector_graph.cypher_api:app --host 127.0.0.1` served HTTP on
//! 127.0.0.1 and the Bolt listener on 0.0.0.0. Here the operator names the loopback address and sets no key; the app's
//! lifespan binds Bolt on every interface (not the operator's address), and a write from another machine runs over
//! Bolt (not an L1 step: a loopback server answers no other machine).
use vstd::prelude::*;
use actors::protocol::*;
use crate::auth_l1::*;
use crate::auth_l2::*;

verus! {

pub open spec fn y0() -> A2 { A2 { cfg: Cfg { key: None, ro: false, host: Host::Loopback }, via_cli: false, bolt: None, runs: 0, writes: 0 } }
pub open spec fn y1() -> A2 { A2 { bolt: Some(Host::Any), ..y0() } }
pub open spec fn yr() -> Req { Req { remote: true, shown: None, public: false, kind: Kind::Write, graph: 0 } }
pub open spec fn y2() -> A2 { A2 { runs: 1, writes: 1, ..y1() } }

pub proof fn counterexample_fc1603()
    ensures
        init2(y0()),
        step2(y0(), AL2::ListenBolt, y1()),
        !inv16a(y1()),
        step2(y1(), AL2::Bolt { r: yr(), st: Status::Ran }, y2()),
        !step_or_stutter::<AuthL1>(absa(y1()), laba(AL2::Bolt { r: yr(), st: Status::Ran }), absa(y2())),
        decide(y1().cfg, yr()) is Unreachable,
{
}

} // verus!
