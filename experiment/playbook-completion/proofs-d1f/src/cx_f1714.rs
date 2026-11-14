//! Proved counterexample for control `control_f1714_unmapped_refusal` (F-1714), compiled only with it.
//!
//! The live trace c17-live-server (Cypher HTTP server with IVG_API_KEY set, a client with a wrong key):
//! IVGClient.explain and load_ndjson, and AsyncIVGClient.execute_cypher, raised httpx's HTTPStatusError for the 401,
//! where execute_cypher raised IVGClientError. Here the explain call's 401 reaches the caller as HTTPStatusError (not an
//! L1 step: a 401 or 403 is IVGClientError for every request).
use vstd::prelude::*;
use actors::protocol::*;
use crate::auth_l1::*;
use crate::auth_l2::*;

verus! {

pub open spec fn z0() -> A2 { A2 { cfg: Cfg { key: Some(7), ro: false, host: Host::Loopback }, via_cli: true, bolt: None, runs: 0, writes: 0 } }

pub proof fn counterexample_f1714()
    ensures
        init2(z0()),
        step2(z0(), AL2::ClientSees { st: Status::Unauthorized, call: CallKind::Explain, cls: Cls::HttpStatusError }, z0()),
        !step_or_stutter::<AuthL1>(absa(z0()),
            laba(AL2::ClientSees { st: Status::Unauthorized, call: CallKind::Explain, cls: Cls::HttpStatusError }), absa(z0())),
        step2(z0(), AL2::ClientSees { st: Status::Unauthorized, call: CallKind::Cypher, cls: Cls::IvgClientError }, z0()),
{
}

} // verus!
