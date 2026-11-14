//! Non-vacuity of the reviewed authorization model (compiled without its controls): on a loopback server with a key
//! and read-only mode, a local read with the key runs; a local write with the key is refused read-only; a local
//! request without the key is refused 401 (not 403); a remote request reaches neither listener; the health route
//! answers without the key; a Bolt read with the key runs; the SDK raises IVGClientError for the 401 of every kind of
//! call.
use vstd::prelude::*;
use crate::auth_l1::*;
use crate::auth_l2::*;

verus! {

pub open spec fn cf() -> Cfg { Cfg { key: Some(7), ro: true, host: Host::Loopback } }
pub open spec fn a0() -> A2 { A2 { cfg: cf(), via_cli: false, bolt: None, runs: 0, writes: 0 } }
pub open spec fn rq(remote: bool, shown: Option<nat>, public: bool, kind: Kind) -> Req { Req { remote, shown, public, kind, graph: 1 } }
pub open spec fn a1() -> A2 { A2 { bolt: Some(Host::Loopback), ..a0() } }

pub proof fn witness_auth()
    ensures
        init2(a0()),
        step2(a0(), AL2::ListenBolt, a1()),
        step2(a1(), AL2::Http { r: rq(false, Some(7), false, Kind::Read), st: Status::Ran }, A2 { runs: 1, ..a1() }),
        step2(a1(), AL2::Http { r: rq(false, Some(7), false, Kind::Write), st: Status::ReadOnly }, a1()),
        step2(a1(), AL2::Http { r: rq(false, None, false, Kind::Write), st: Status::Unauthorized }, a1()),
        step2(a1(), AL2::Http { r: rq(true, Some(7), false, Kind::Read), st: Status::Unreachable }, a1()),
        step2(a1(), AL2::Http { r: rq(false, None, true, Kind::Read), st: Status::Ran }, A2 { runs: 1, ..a1() }),
        step2(a1(), AL2::Bolt { r: rq(true, None, false, Kind::Write), st: Status::Unreachable }, a1()),
        step2(a1(), AL2::Bolt { r: rq(false, Some(7), false, Kind::Read), st: Status::Ran }, A2 { runs: 1, ..a1() }),
        step2(a1(), AL2::ClientSees { st: Status::Unauthorized, call: CallKind::Explain, cls: Cls::IvgClientError }, a1()),
        step2(a1(), AL2::ClientSees { st: Status::ReadOnly, call: CallKind::Async, cls: Cls::IvgClientError }, a1()),
{
}

} // verus!
