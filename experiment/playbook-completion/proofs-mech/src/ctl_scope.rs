//! M-09 located controls (see src/ctl_ledger.rs for the form).
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m09_scope::*;
#[allow(unused_imports)]
use crate::i09_scope::*;

verus! {

// CONTROL scope_name_check_missing_as_built mech=M-09 check=scope-name-check-missing-as-built kind=as-built objects=02/graph-name findings=F-0202,F-0203 violates=M09-L1 refute=i09_scope::refute_name_check_missing_l1 cx=cx09_scope::cx_name_check_missing_l1
#[cfg(feature = "scope_name_check_missing_as_built")]
impl ScopeObject for NameCheckMissingAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE scope_name_check_missing_as_built M09-L1
    }
    proof fn discharge_l2() { keep_name_check_missing_l2(); }
    proof fn discharge_l3() { keep_name_check_missing_l3(); }
    proof fn discharge_l4() { keep_name_check_missing_l4(); }
}

// CONTROL scope_all_graphs_walk_as_built mech=M-09 check=scope-all-graphs-walk-as-built kind=as-built objects=08/graph-scope findings=F-0818,F-0819,F-0820 violates=M09-L2 refute=i09_scope::refute_all_graphs_walk_l2 cx=cx09_scope::cx_all_graphs_walk_l2
#[cfg(feature = "scope_all_graphs_walk_as_built")]
impl ScopeObject for AllGraphsWalkAsBuilt {
    proof fn discharge_l1() { keep_all_graphs_walk_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE scope_all_graphs_walk_as_built M09-L2
    }
    proof fn discharge_l3() { keep_all_graphs_walk_l3(); }
    proof fn discharge_l4() { keep_all_graphs_walk_l4(); }
}

// CONTROL scope_unscoped_read_as_built mech=M-09 check=scope-unscoped-read-as-built kind=as-built objects=10/default-graph-algorithm-call,16/graph-a-caller-names,17/link,07/fused-search,06/route,10/native-route,07/older-text-search,15/fhir-bridge,16/generated-graphql-call findings=F-1002,F-1006,F-1008,F-1013,F-1001,F-1603,F-1604,F-1701,F-0609,F-0711,F-0605,F-0616,F-1507 violates=M09-L2 refute=i09_scope::refute_unscoped_read_l2 cx=cx09_scope::cx_unscoped_read_l2
#[cfg(feature = "scope_unscoped_read_as_built")]
impl ScopeObject for UnscopedReadAsBuilt {
    proof fn discharge_l1() { keep_unscoped_read_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE scope_unscoped_read_as_built M09-L2
    }
    proof fn discharge_l3() { keep_unscoped_read_l3(); }
    proof fn discharge_l4() { keep_unscoped_read_l4(); }
}

// CONTROL scope_interned_no_graph_dimension_as_built mech=M-09 check=scope-interned-no-graph-dimension-as-built kind=exception objects=10/interned-snapshot findings= violates=M09-L2 refute=i09_scope::refute_interned_no_graph_dimension_l2 cx=cx09_scope::cx_interned_no_graph_dimension_l2
#[cfg(feature = "scope_interned_no_graph_dimension_as_built")]
impl ScopeObject for InternedNoGraphDimensionAsBuilt {
    proof fn discharge_l1() { keep_interned_no_graph_dimension_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE scope_interned_no_graph_dimension_as_built M09-L2
    }
    proof fn discharge_l3() { keep_interned_no_graph_dimension_l3(); }
    proof fn discharge_l4() { keep_interned_no_graph_dimension_l4(); }
}

// CONTROL scope_delete_every_graph_as_built mech=M-09 check=scope-delete-every-graph-as-built kind=as-built objects=15/reifier findings=F-1503 violates=M09-L3 refute=i09_scope::refute_delete_every_graph_l3 cx=cx09_scope::cx_delete_every_graph_l3
#[cfg(feature = "scope_delete_every_graph_as_built")]
impl ScopeObject for DeleteEveryGraphAsBuilt {
    proof fn discharge_l1() { keep_delete_every_graph_l1(); }
    proof fn discharge_l2() { keep_delete_every_graph_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE scope_delete_every_graph_as_built M09-L3
    }
    proof fn discharge_l4() { keep_delete_every_graph_l4(); }
}

// CONTROL scope_three_predicates_as_built mech=M-09 check=scope-three-predicates-as-built kind=as-built objects=13/redaction-target,11/node-id findings=F-1304,F-1305,F-1105,F-1401 violates=M09-L4 refute=i09_scope::refute_three_predicates_l4 cx=cx09_scope::cx_three_predicates_l4
#[cfg(feature = "scope_three_predicates_as_built")]
impl ScopeObject for ThreePredicatesAsBuilt {
    proof fn discharge_l1() { keep_three_predicates_l1(); }
    proof fn discharge_l2() { keep_three_predicates_l2(); }
    proof fn discharge_l3() { keep_three_predicates_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE scope_three_predicates_as_built M09-L4
    }
}

// CONTROL scope_control_c1_key_ignores_name mech=M-09 check=scope-control-C1-key-ignores-name kind=mutant objects=03/node-in-one-graph,03/edge-in-one-graph,05/temporal-coordinates,08/cypher-node,08/cypher-edge,12/graph-content,07/docs-table-search findings= violates=M09-L1 refute=i09_scope::refute_ctl_key_ignores_name_l1 cx=cx09_scope::cx_ctl_key_ignores_name_l1
#[cfg(feature = "scope_control_c1_key_ignores_name")]
impl ScopeObject for CtlKeyIgnoresName {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE scope_control_c1_key_ignores_name M09-L1
    }
    proof fn discharge_l2() { keep_ctl_key_ignores_name_l2(); }
    proof fn discharge_l3() { keep_ctl_key_ignores_name_l3(); }
    proof fn discharge_l4() { keep_ctl_key_ignores_name_l4(); }
}

// CONTROL scope_control_c2_join_across_graphs mech=M-09 check=scope-control-C2-join-across-graphs kind=mutant objects=03/node-in-one-graph,03/edge-in-one-graph,05/temporal-coordinates,08/cypher-node,08/cypher-edge,12/graph-content,07/docs-table-search findings= violates=M09-L2 refute=i09_scope::refute_ctl_join_across_graphs_l2 cx=cx09_scope::cx_ctl_join_across_graphs_l2
#[cfg(feature = "scope_control_c2_join_across_graphs")]
impl ScopeObject for CtlJoinAcrossGraphs {
    proof fn discharge_l1() { keep_ctl_join_across_graphs_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE scope_control_c2_join_across_graphs M09-L2
    }
    proof fn discharge_l3() { keep_ctl_join_across_graphs_l3(); }
    proof fn discharge_l4() { keep_ctl_join_across_graphs_l4(); }
}

// CONTROL scope_control_c3_delete_every_graph mech=M-09 check=scope-control-C3-delete-every-graph kind=mutant objects=03/node-in-one-graph,03/edge-in-one-graph,05/temporal-coordinates,08/cypher-node,08/cypher-edge,12/graph-content,07/docs-table-search findings= violates=M09-L3 refute=i09_scope::refute_ctl_delete_every_graph_l3 cx=cx09_scope::cx_ctl_delete_every_graph_l3
#[cfg(feature = "scope_control_c3_delete_every_graph")]
impl ScopeObject for CtlDeleteEveryGraph {
    proof fn discharge_l1() { keep_ctl_delete_every_graph_l1(); }
    proof fn discharge_l2() { keep_ctl_delete_every_graph_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE scope_control_c3_delete_every_graph M09-L3
    }
    proof fn discharge_l4() { keep_ctl_delete_every_graph_l4(); }
}

// CONTROL scope_control_c4_graph_blind_match mech=M-09 check=scope-control-C4-graph-blind-match kind=mutant objects=03/node-in-one-graph,03/edge-in-one-graph,05/temporal-coordinates,08/cypher-node,08/cypher-edge,12/graph-content,07/docs-table-search findings= violates=M09-L4 refute=i09_scope::refute_ctl_graph_blind_match_l4 cx=cx09_scope::cx_ctl_graph_blind_match_l4
#[cfg(feature = "scope_control_c4_graph_blind_match")]
impl ScopeObject for CtlGraphBlindMatch {
    proof fn discharge_l1() { keep_ctl_graph_blind_match_l1(); }
    proof fn discharge_l2() { keep_ctl_graph_blind_match_l2(); }
    proof fn discharge_l3() { keep_ctl_graph_blind_match_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE scope_control_c4_graph_blind_match M09-L4
    }
}

} // verus!
