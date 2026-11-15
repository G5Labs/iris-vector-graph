//! M-12 located controls. Each block exists only under its feature and is the departing variant's attempt to
//! discharge the mechanism trait: the kept obligations are discharged by the baseline's `keep_*` lemmas, each broken
//! one is asserted on the line marked `LOCATE <feature> <law>` and must fail there (its negation is proved in the
//! baseline by `refute_*`, and the law itself is broken by the run in src/cx12_catalog.rs).
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m12_catalog::*;
#[allow(unused_imports)]
use crate::i12_catalog::*;

verus! {

// CONTROL catalog_bm25_index_graph_unchecked_as_built mech=M-12 check=catalog-bm25-index-graph-unchecked-as-built kind=as-built objects=07/bm25-index,17/index-handle findings=F-0707 violates=M12-L2 refute=i12_catalog::refute_bm25_index_graph_unchecked_l2 cx=cx12_catalog::cx_bm25_index_graph_unchecked_l2
#[cfg(feature = "catalog_bm25_index_graph_unchecked_as_built")]
impl CatalogObject for Bm25IndexGraphUncheckedAsBuilt {
    proof fn discharge_l1() { keep_bm25_index_graph_unchecked_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE catalog_bm25_index_graph_unchecked_as_built M12-L2
    }
    proof fn discharge_l3() { keep_bm25_index_graph_unchecked_l3(); }
}

// CONTROL catalog_bm25_index_graph_unchecked_as_built_m12_l1_f_0705 mech=M-12 check=catalog-bm25-index-graph-unchecked-as-built-M12-L1-F-0705,catalog-bm25-index-graph-unchecked-as-built-M12-L2-F-0705 kind=as-built objects=07/bm25-index,17/index-handle findings=F-0705 violates=M12-L1,M12-L2 refute=i12_catalog::refute_bm25_index_no_record_l1,i12_catalog::refute_bm25_index_no_record_l2 cx=cx12_catalog::cx_bm25_index_no_record_l1,cx12_catalog::cx_bm25_index_no_record_l2
#[cfg(feature = "catalog_bm25_index_graph_unchecked_as_built_m12_l1_f_0705")]
impl CatalogObject for Bm25IndexNoRecordAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE catalog_bm25_index_graph_unchecked_as_built_m12_l1_f_0705 M12-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE catalog_bm25_index_graph_unchecked_as_built_m12_l1_f_0705 M12-L2
    }
    proof fn discharge_l3() { keep_bm25_index_no_record_l3(); }
}

// CONTROL catalog_ivf_index_graph_unchecked_as_built mech=M-12 check=catalog-ivf-index-graph-unchecked-as-built kind=as-built objects=06/ivf-index findings=F-0609 violates=M12-L2 refute=i12_catalog::refute_ivf_index_graph_unchecked_l2 cx=cx12_catalog::cx_ivf_index_graph_unchecked_l2
#[cfg(feature = "catalog_ivf_index_graph_unchecked_as_built")]
impl CatalogObject for IvfIndexGraphUncheckedAsBuilt {
    proof fn discharge_l1() { keep_ivf_index_graph_unchecked_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE catalog_ivf_index_graph_unchecked_as_built M12-L2
    }
    proof fn discharge_l3() { keep_ivf_index_graph_unchecked_l3(); }
}

// CONTROL catalog_identity_fail_open_as_built mech=M-12 check=catalog-identity-fail-open-as-built kind=as-built objects=06/registry-row findings=F-0601,F-0602,F-0603,F-0613 violates=M12-L2 refute=i12_catalog::refute_identity_fail_open_l2 cx=cx12_catalog::cx_identity_fail_open_l2
#[cfg(feature = "catalog_identity_fail_open_as_built")]
impl CatalogObject for IdentityFailOpenAsBuilt {
    proof fn discharge_l1() { keep_identity_fail_open_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE catalog_identity_fail_open_as_built M12-L2
    }
    proof fn discharge_l3() { keep_identity_fail_open_l3(); }
}

// CONTROL catalog_short_hash_name_as_built mech=M-12 check=catalog-short-hash-name-as-built kind=as-built objects=09/compiled-shape findings=F-0901,F-C0901 violates=M12-L3 refute=i12_catalog::refute_short_hash_name_l3 cx=cx12_catalog::cx_short_hash_name_l3
#[cfg(feature = "catalog_short_hash_name_as_built")]
impl CatalogObject for ShortHashNameAsBuilt {
    proof fn discharge_l1() { keep_short_hash_name_l1(); }
    proof fn discharge_l2() { keep_short_hash_name_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE catalog_short_hash_name_as_built M12-L3
    }
}

// CONTROL catalog_control_c1_unchecked_read mech=M-12 check=catalog-control-C1-unchecked-read kind=mutant objects=06/route,15/table-mapping,10/native-route,15/code-crosswalk findings= violates=M12-L2 refute=i12_catalog::refute_ctl_unchecked_read_l2 cx=cx12_catalog::cx_ctl_unchecked_read_l2
#[cfg(feature = "catalog_control_c1_unchecked_read")]
impl CatalogObject for CtlUncheckedRead {
    proof fn discharge_l1() { keep_ctl_unchecked_read_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE catalog_control_c1_unchecked_read M12-L2
    }
    proof fn discharge_l3() { keep_ctl_unchecked_read_l3(); }
}

// CONTROL catalog_control_c2_short_hash mech=M-12 check=catalog-control-C2-short-hash kind=mutant objects=06/route,15/table-mapping,10/native-route,15/code-crosswalk findings= violates=M12-L3 refute=i12_catalog::refute_ctl_short_hash_l3 cx=cx12_catalog::cx_ctl_short_hash_l3
#[cfg(feature = "catalog_control_c2_short_hash")]
impl CatalogObject for CtlShortHash {
    proof fn discharge_l1() { keep_ctl_short_hash_l1(); }
    proof fn discharge_l2() { keep_ctl_short_hash_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE catalog_control_c2_short_hash M12-L3
    }
}

// CONTROL catalog_control_c3_no_record mech=M-12 check=catalog-control-C3-no-record kind=mutant objects=06/route,15/table-mapping,10/native-route,15/code-crosswalk findings= violates=M12-L1,M12-L2 refute=i12_catalog::refute_ctl_no_record_l1,i12_catalog::refute_ctl_no_record_l2 cx=cx12_catalog::cx_ctl_no_record_l1,cx12_catalog::cx_ctl_no_record_l2
#[cfg(feature = "catalog_control_c3_no_record")]
impl CatalogObject for CtlNoRecord {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE catalog_control_c3_no_record M12-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE catalog_control_c3_no_record M12-L2
    }
    proof fn discharge_l3() { keep_ctl_no_record_l3(); }
}

// CONTROL catalog_control_c4_fail_open mech=M-12 check=catalog-control-C4-fail-open kind=mutant objects=06/route,15/table-mapping,10/native-route,15/code-crosswalk findings= violates=M12-L2 refute=i12_catalog::refute_ctl_fail_open_l2 cx=cx12_catalog::cx_ctl_fail_open_l2
#[cfg(feature = "catalog_control_c4_fail_open")]
impl CatalogObject for CtlFailOpen {
    proof fn discharge_l1() { keep_ctl_fail_open_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE catalog_control_c4_fail_open M12-L2
    }
    proof fn discharge_l3() { keep_ctl_fail_open_l3(); }
}

} // verus!
