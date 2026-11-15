//! M-11 located controls. Each block exists only under its feature and is the departing variant's attempt to
//! discharge the mechanism trait: the kept obligations are discharged by the baseline's `keep_*` lemmas, each broken
//! one is asserted on the line marked `LOCATE <feature> <law>` and must fail there (its negation is proved in the
//! baseline by `refute_*`, and the law itself is broken by the call in src/cx11_cap.rs).
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m11_cap::*;
#[allow(unused_imports)]
use crate::i11_cap::*;

verus! {

// CONTROL cap_demo_server_as_built mech=M-11 check=cap-demo-server-as-built kind=as-built objects=16/rest-web-app-path,16/demo-server-call findings=F-1614 violates=M11-L2 refute=i11_cap::refute_demo_server_l2 cx=cx11_cap::cx_demo_server_l2
#[cfg(feature = "cap_demo_server_as_built")]
impl CapObject for DemoServerAsBuilt {
    proof fn discharge_l1() { keep_demo_server_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE cap_demo_server_as_built M11-L2
    }
    proof fn discharge_l3() { keep_demo_server_l3(); }
}

// CONTROL cap_aql_as_built mech=M-11 check=cap-aql-as-built kind=as-built objects=08/cypher-call findings=F-0814 violates=M11-L1 refute=i11_cap::refute_aql_l1 cx=cx11_cap::cx_aql_l1
#[cfg(feature = "cap_aql_as_built")]
impl CapObject for AqlAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE cap_aql_as_built M11-L1
    }
    proof fn discharge_l2() { keep_aql_l2(); }
    proof fn discharge_l3() { keep_aql_l3(); }
}

// CONTROL cap_aql_code_text_as_built mech=M-11 check=cap-aql-code-text-as-built kind=as-built objects=08/cypher-call findings=F-0815,F-0814 violates=M11-L3 refute=i11_cap::refute_aql_code_text_l3 cx=cx11_cap::cx_aql_code_text_l3
#[cfg(feature = "cap_aql_code_text_as_built")]
impl CapObject for AqlCodeTextAsBuilt {
    proof fn discharge_l1() { keep_aql_code_text_l1(); }
    proof fn discharge_l2() { keep_aql_code_text_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE cap_aql_code_text_as_built M11-L3
    }
}

// CONTROL cap_snapshot_file_helpers_as_built mech=M-11 check=cap-snapshot-file-helpers-as-built kind=as-built objects=18/snapshot-archive findings=F-C1803,F-1806 violates=M11-L1,M11-L2,M11-L3 refute=i11_cap::refute_snapshot_file_helpers_l1,i11_cap::refute_snapshot_file_helpers_l2,i11_cap::refute_snapshot_file_helpers_l3 cx=cx11_cap::cx_snapshot_file_helpers_l1,cx11_cap::cx_snapshot_file_helpers_l2,cx11_cap::cx_snapshot_file_helpers_l3
#[cfg(feature = "cap_snapshot_file_helpers_as_built")]
impl CapObject for SnapshotFileHelpersAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE cap_snapshot_file_helpers_as_built M11-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE cap_snapshot_file_helpers_as_built M11-L2
    }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE cap_snapshot_file_helpers_as_built M11-L3
    }
}

// CONTROL cap_privilege_in_engine_only_as_built mech=M-11 check=cap-privilege-in-engine-only-as-built kind=as-built objects=09/engine-native-path findings=F-0908 violates=M11-L2 refute=i11_cap::refute_privilege_in_engine_only_l2 cx=cx11_cap::cx_privilege_in_engine_only_l2
#[cfg(feature = "cap_privilege_in_engine_only_as_built")]
impl CapObject for PrivilegeInEngineOnlyAsBuilt {
    proof fn discharge_l1() { keep_privilege_in_engine_only_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE cap_privilege_in_engine_only_as_built M11-L2
    }
    proof fn discharge_l3() { keep_privilege_in_engine_only_l3(); }
}

// CONTROL cap_control_c1_write_without_read_only_check mech=M-11 check=cap-control-C1-write-without-read-only-check kind=mutant objects=16/cypher-http-call,16/bolt-session-with-a-key-set,17/client-request,17/namespace,17/link,16/generated-graphql-call,16/fraud-server-call findings= violates=M11-L1 refute=i11_cap::refute_ctl_write_without_read_only_check_l1 cx=cx11_cap::cx_ctl_write_without_read_only_check_l1
#[cfg(feature = "cap_control_c1_write_without_read_only_check")]
impl CapObject for CtlWriteWithoutReadOnlyCheck {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE cap_control_c1_write_without_read_only_check M11-L1
    }
    proof fn discharge_l2() { keep_ctl_write_without_read_only_check_l2(); }
    proof fn discharge_l3() { keep_ctl_write_without_read_only_check_l3(); }
}

// CONTROL cap_control_c2_route_without_key_check mech=M-11 check=cap-control-C2-route-without-key-check kind=mutant objects=16/cypher-http-call,16/bolt-session-with-a-key-set,17/client-request,17/namespace,17/link,16/generated-graphql-call,16/fraud-server-call findings= violates=M11-L2 refute=i11_cap::refute_ctl_route_without_key_check_l2 cx=cx11_cap::cx_ctl_route_without_key_check_l2
#[cfg(feature = "cap_control_c2_route_without_key_check")]
impl CapObject for CtlRouteWithoutKeyCheck {
    proof fn discharge_l1() { keep_ctl_route_without_key_check_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE cap_control_c2_route_without_key_check M11-L2
    }
    proof fn discharge_l3() { keep_ctl_route_without_key_check_l3(); }
}

// CONTROL cap_control_c3_file_route mech=M-11 check=cap-control-C3-file-route kind=mutant objects=16/cypher-http-call,16/bolt-session-with-a-key-set,17/client-request,17/namespace,17/link,16/generated-graphql-call,16/fraud-server-call findings= violates=M11-L3 refute=i11_cap::refute_ctl_file_route_l3 cx=cx11_cap::cx_ctl_file_route_l3
#[cfg(feature = "cap_control_c3_file_route")]
impl CapObject for CtlFileRoute {
    proof fn discharge_l1() { keep_ctl_file_route_l1(); }
    proof fn discharge_l2() { keep_ctl_file_route_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE cap_control_c3_file_route M11-L3
    }
}

} // verus!
