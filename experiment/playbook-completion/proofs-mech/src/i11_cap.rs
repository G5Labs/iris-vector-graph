//! M-11 instances: one type per object variant of mechanisms.json (family `cap`, models/semantics/src/cap.rs).
//!
//! An instance is its routes (`CapPolicy::routes`) and, when it keeps every law, its discharge of the obligations
//! (`CapObject`): the generic theorem `theorem_cap` then applies with no proof work of its own. As-built variants that
//! depart and the generic mutants (the semantics lane's negative controls) have parameters only here; their kept
//! obligations are proved (`keep_*`), their broken ones refuted (`refute_*`), and their `CapObject` impl exists only
//! under their control feature (src/ctl_cap.rs). 16/mcp-tool-set is not modelled (Community has no %AI, F-1613
//! blocked-access), as in the explorer.
use vstd::prelude::*;
use crate::exec::*;
use crate::m11_cap::*;

verus! {

// ---------------------------------------------------------------- canonical and reviewed instances (baseline)

/// http-server: 16/cypher-http-call, 16/bolt-session-with-a-key-set, 17/client-request, 17/namespace, 17/link (canonical; cypher_api.py, ADMIN_GUIDE.md:824-840): with IVG_API_KEY and IVG_READ_ONLY set every route checks both.
pub struct HttpServer;
impl CapPolicy for HttpServer { open spec fn routes() -> Seq<Route> { seq![r_read(), r_write()] } }
impl CapObject for HttpServer {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// demo-server, reviewed: 16/rest-web-app-path; the write routes check the key.
pub struct DemoServerReviewed;
impl CapPolicy for DemoServerReviewed { open spec fn routes() -> Seq<Route> { seq![r_read(), r_write()] } }
impl CapObject for DemoServerReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// aql, reviewed: 08/cypher-call; execute_aql checks read-only.
pub struct AqlReviewed;
impl CapPolicy for AqlReviewed { open spec fn routes() -> Seq<Route> { seq![r_read(), r_write()] } }
impl CapObject for AqlReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// aql-code-text, reviewed: 08/cypher-call; caller text is data, never code.
pub struct AqlCodeTextReviewed;
impl CapPolicy for AqlCodeTextReviewed { open spec fn routes() -> Seq<Route> { seq![r_read(), r_write()] } }
impl CapObject for AqlCodeTextReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// snapshot-file-helpers, reviewed: 18/snapshot-archive; no server-file route.
pub struct SnapshotFileHelpersReviewed;
impl CapPolicy for SnapshotFileHelpersReviewed { open spec fn routes() -> Seq<Route> { seq![r_read(), r_write()] } }
impl CapObject for SnapshotFileHelpersReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// privilege-in-engine-only, reviewed: 09/engine-native-path; the entry point checks the privilege.
pub struct PrivilegeInEngineOnlyReviewed;
impl CapPolicy for PrivilegeInEngineOnlyReviewed { open spec fn routes() -> Seq<Route> { seq![r_read(), r_write()] } }
impl CapObject for PrivilegeInEngineOnlyReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// The generic theorem, instantiated: each line is the whole proof work of one instance.
pub proof fn laws_http_server(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CapM<HttpServer>>(s0, ls, t)
    ensures cap_step::<HttpServer>(t, a) is Some ==> law_l1(t, a, cap_step::<HttpServer>(t, a)->0) && law_l2(t, a, cap_step::<HttpServer>(t, a)->0)
        && law_l3(t, a, cap_step::<HttpServer>(t, a)->0) { theorem_cap::<HttpServer>(s0, ls, t, a); }
pub proof fn laws_demo_server_reviewed(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CapM<DemoServerReviewed>>(s0, ls, t)
    ensures cap_step::<DemoServerReviewed>(t, a) is Some ==> law_l1(t, a, cap_step::<DemoServerReviewed>(t, a)->0) && law_l2(t, a, cap_step::<DemoServerReviewed>(t, a)->0)
        && law_l3(t, a, cap_step::<DemoServerReviewed>(t, a)->0) { theorem_cap::<DemoServerReviewed>(s0, ls, t, a); }
pub proof fn laws_aql_reviewed(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CapM<AqlReviewed>>(s0, ls, t)
    ensures cap_step::<AqlReviewed>(t, a) is Some ==> law_l1(t, a, cap_step::<AqlReviewed>(t, a)->0) && law_l2(t, a, cap_step::<AqlReviewed>(t, a)->0)
        && law_l3(t, a, cap_step::<AqlReviewed>(t, a)->0) { theorem_cap::<AqlReviewed>(s0, ls, t, a); }
pub proof fn laws_aql_code_text_reviewed(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CapM<AqlCodeTextReviewed>>(s0, ls, t)
    ensures cap_step::<AqlCodeTextReviewed>(t, a) is Some ==> law_l1(t, a, cap_step::<AqlCodeTextReviewed>(t, a)->0) && law_l2(t, a, cap_step::<AqlCodeTextReviewed>(t, a)->0)
        && law_l3(t, a, cap_step::<AqlCodeTextReviewed>(t, a)->0) { theorem_cap::<AqlCodeTextReviewed>(s0, ls, t, a); }
pub proof fn laws_snapshot_file_helpers_reviewed(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CapM<SnapshotFileHelpersReviewed>>(s0, ls, t)
    ensures cap_step::<SnapshotFileHelpersReviewed>(t, a) is Some ==> law_l1(t, a, cap_step::<SnapshotFileHelpersReviewed>(t, a)->0) && law_l2(t, a, cap_step::<SnapshotFileHelpersReviewed>(t, a)->0)
        && law_l3(t, a, cap_step::<SnapshotFileHelpersReviewed>(t, a)->0) { theorem_cap::<SnapshotFileHelpersReviewed>(s0, ls, t, a); }
pub proof fn laws_privilege_in_engine_only_reviewed(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CapM<PrivilegeInEngineOnlyReviewed>>(s0, ls, t)
    ensures cap_step::<PrivilegeInEngineOnlyReviewed>(t, a) is Some ==> law_l1(t, a, cap_step::<PrivilegeInEngineOnlyReviewed>(t, a)->0) && law_l2(t, a, cap_step::<PrivilegeInEngineOnlyReviewed>(t, a)->0)
        && law_l3(t, a, cap_step::<PrivilegeInEngineOnlyReviewed>(t, a)->0) { theorem_cap::<PrivilegeInEngineOnlyReviewed>(s0, ls, t, a); }

// ---------------------------------------------------------------- as-built variants that depart and generic mutants (parameters only)

/// demo-server as built: 16/rest-web-app-path (F-1614; src/iris_demo_server/app.py:1-22): the write routes need no key.
pub struct DemoServerAsBuilt;
impl CapPolicy for DemoServerAsBuilt { open spec fn routes() -> Seq<Route> { seq![r_read(), Route { kind: Kind::Write, key_check: false, ro_check: true }] } }
pub proof fn keep_demo_server_l1() ensures obl_l1::<DemoServerAsBuilt>() {}
pub proof fn refute_demo_server_l2() ensures !obl_l2::<DemoServerAsBuilt>() {
    assert(!route_checks_credential(DemoServerAsBuilt::routes()[1]));
}
pub proof fn keep_demo_server_l3() ensures obl_l3::<DemoServerAsBuilt>() {}

/// aql as built: 08/cypher-call (F-0814; aql/translator.py:50-58, 154-168): execute_aql ignores read-only.
pub struct AqlAsBuilt;
impl CapPolicy for AqlAsBuilt { open spec fn routes() -> Seq<Route> { seq![r_read(), Route { kind: Kind::Write, key_check: true, ro_check: false }] } }
pub proof fn refute_aql_l1() ensures !obl_l1::<AqlAsBuilt>() {
    assert(!route_checks_role(AqlAsBuilt::routes()[1]));
}
pub proof fn keep_aql_l2() ensures obl_l2::<AqlAsBuilt>() {}
pub proof fn keep_aql_l3() ensures obl_l3::<AqlAsBuilt>() {}

/// aql-code-text as built: 08/cypher-call (F-0815, F-0814): AQL text and a dotted function name pasted into Cypher / SQL text run caller text as code.
pub struct AqlCodeTextAsBuilt;
impl CapPolicy for AqlCodeTextAsBuilt { open spec fn routes() -> Seq<Route> { seq![r_read(), Route { kind: Kind::File, key_check: true, ro_check: true }] } }
pub proof fn keep_aql_code_text_l1() ensures obl_l1::<AqlCodeTextAsBuilt>() {}
pub proof fn keep_aql_code_text_l2() ensures obl_l2::<AqlCodeTextAsBuilt>() {}
pub proof fn refute_aql_code_text_l3() ensures !obl_l3::<AqlCodeTextAsBuilt>() {
    assert(!route_no_file(AqlCodeTextAsBuilt::routes()[1]));
}

/// snapshot-file-helpers as built: 18/snapshot-archive (F-C1803, F-1806; Snapshot.cls:4-73): file helpers reachable by any Native API caller.
pub struct SnapshotFileHelpersAsBuilt;
impl CapPolicy for SnapshotFileHelpersAsBuilt { open spec fn routes() -> Seq<Route> { seq![r_read(), Route { kind: Kind::File, key_check: false, ro_check: false }] } }
pub proof fn refute_snapshot_file_helpers_l1() ensures !obl_l1::<SnapshotFileHelpersAsBuilt>() {
    assert(!route_checks_role(SnapshotFileHelpersAsBuilt::routes()[1]));
}
pub proof fn refute_snapshot_file_helpers_l2() ensures !obl_l2::<SnapshotFileHelpersAsBuilt>() {
    assert(!route_checks_credential(SnapshotFileHelpersAsBuilt::routes()[1]));
}
pub proof fn refute_snapshot_file_helpers_l3() ensures !obl_l3::<SnapshotFileHelpersAsBuilt>() {
    assert(!route_no_file(SnapshotFileHelpersAsBuilt::routes()[1]));
}

/// privilege-in-engine-only as built: 09/engine-native-path (F-0908; Exec.cls:32-72): the privilege check lives in the engine only.
pub struct PrivilegeInEngineOnlyAsBuilt;
impl CapPolicy for PrivilegeInEngineOnlyAsBuilt { open spec fn routes() -> Seq<Route> { seq![r_read(), Route { kind: Kind::Read, key_check: false, ro_check: true }] } }
pub proof fn keep_privilege_in_engine_only_l1() ensures obl_l1::<PrivilegeInEngineOnlyAsBuilt>() {}
pub proof fn refute_privilege_in_engine_only_l2() ensures !obl_l2::<PrivilegeInEngineOnlyAsBuilt>() {
    assert(!route_checks_credential(PrivilegeInEngineOnlyAsBuilt::routes()[1]));
}
pub proof fn keep_privilege_in_engine_only_l3() ensures obl_l3::<PrivilegeInEngineOnlyAsBuilt>() {}

/// cap-control-C1-write-without-read-only-check: the write route does not check read-only.
pub struct CtlWriteWithoutReadOnlyCheck;
impl CapPolicy for CtlWriteWithoutReadOnlyCheck { open spec fn routes() -> Seq<Route> { seq![r_read(), Route { kind: Kind::Write, key_check: true, ro_check: false }] } }
pub proof fn refute_ctl_write_without_read_only_check_l1() ensures !obl_l1::<CtlWriteWithoutReadOnlyCheck>() {
    assert(!route_checks_role(CtlWriteWithoutReadOnlyCheck::routes()[1]));
}
pub proof fn keep_ctl_write_without_read_only_check_l2() ensures obl_l2::<CtlWriteWithoutReadOnlyCheck>() {}
pub proof fn keep_ctl_write_without_read_only_check_l3() ensures obl_l3::<CtlWriteWithoutReadOnlyCheck>() {}

/// cap-control-C2-route-without-key-check: the write route does not check the key.
pub struct CtlRouteWithoutKeyCheck;
impl CapPolicy for CtlRouteWithoutKeyCheck { open spec fn routes() -> Seq<Route> { seq![Route { kind: Kind::Write, key_check: false, ro_check: true }] } }
pub proof fn keep_ctl_route_without_key_check_l1() ensures obl_l1::<CtlRouteWithoutKeyCheck>() {}
pub proof fn refute_ctl_route_without_key_check_l2() ensures !obl_l2::<CtlRouteWithoutKeyCheck>() {
    assert(!route_checks_credential(CtlRouteWithoutKeyCheck::routes()[0]));
}
pub proof fn keep_ctl_route_without_key_check_l3() ensures obl_l3::<CtlRouteWithoutKeyCheck>() {}

/// cap-control-C3-file-route: a route reads or writes a server file.
pub struct CtlFileRoute;
impl CapPolicy for CtlFileRoute { open spec fn routes() -> Seq<Route> { seq![r_read(), Route { kind: Kind::File, key_check: true, ro_check: true }] } }
pub proof fn keep_ctl_file_route_l1() ensures obl_l1::<CtlFileRoute>() {}
pub proof fn keep_ctl_file_route_l2() ensures obl_l2::<CtlFileRoute>() {}
pub proof fn refute_ctl_file_route_l3() ensures !obl_l3::<CtlFileRoute>() {
    assert(!route_no_file(CtlFileRoute::routes()[1]));
}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witness)

/// cap-sharp-keyed-write: a keyed read-write caller writes through the reviewed gate.
pub proof fn sharp_keyed_write()
    ensures ({
        let t = run::<CapM<HttpServer>>(cap_s0(), seq![CA { key: 2, ro: false, route: 1 }]);
        t is Some && t->0.store != 0
    })
{
    reveal_with_fuel(run, 2);
}

} // verus!
