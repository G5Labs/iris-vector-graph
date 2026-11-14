//! M-12 instances: one type per object variant of mechanisms.json (family `catalog`, models/semantics/src/catalog.rs).
//!
//! Canonical and reviewed instances discharge every obligation (`CatalogObject`) and get `theorem_catalog` with no
//! proof work of their own. As-built variants that depart and the generic mutants have parameters only here; their
//! kept obligations are proved (`keep_*`), their broken ones refuted (`refute_*`), and their `CatalogObject` impl
//! exists only under their control feature (src/ctl_catalog.rs).
use vstd::prelude::*;
use crate::exec::*;
use crate::m12_catalog::*;

verus! {

pub open spec fn canon_cfg() -> CatCfg { CatCfg { naming: Naming::Full, records: true, read_checked: true, fail_open: false } }

// ---------------------------------------------------------------- canonical and reviewed instances (baseline)

/// canonical: 06/route, 15/table-mapping, 10/native-route (vector.py:164-226: the registry row names the table).
pub struct CatalogCanonical;
impl CatalogPolicy for CatalogCanonical { open spec fn cfg() -> CatCfg { canon_cfg() } }
impl CatalogObject for CatalogCanonical {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// bm25-index-graph-unchecked, reviewed: 07/bm25-index, 17/index-handle; the index records its graph and every read
/// checks it.
pub struct Bm25IndexGraphUncheckedReviewed;
impl CatalogPolicy for Bm25IndexGraphUncheckedReviewed { open spec fn cfg() -> CatCfg { canon_cfg() } }
impl CatalogObject for Bm25IndexGraphUncheckedReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// ivf-index-graph-unchecked, reviewed: 06/ivf-index; the fused search checks the index's graph.
pub struct IvfIndexGraphUncheckedReviewed;
impl CatalogPolicy for IvfIndexGraphUncheckedReviewed { open spec fn cfg() -> CatCfg { canon_cfg() } }
impl CatalogObject for IvfIndexGraphUncheckedReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// identity-fail-open, reviewed: 06/registry-row; a failed registry read refuses the write.
pub struct IdentityFailOpenReviewed;
impl CatalogPolicy for IdentityFailOpenReviewed { open spec fn cfg() -> CatCfg { canon_cfg() } }
impl CatalogObject for IdentityFailOpenReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// short-hash-name, reviewed: 09/compiled-shape; the plan name is a function of the full shape.
pub struct ShortHashNameReviewed;
impl CatalogPolicy for ShortHashNameReviewed { open spec fn cfg() -> CatCfg { canon_cfg() } }
impl CatalogObject for ShortHashNameReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// The generic theorem, instantiated: each line is the whole proof work of one instance.
pub proof fn laws_catalog_canonical(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CatalogM<CatalogCanonical>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_catalog::<CatalogCanonical>(s0, ls, t, a); }
pub proof fn laws_bm25_index_graph_unchecked_reviewed(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CatalogM<Bm25IndexGraphUncheckedReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_catalog::<Bm25IndexGraphUncheckedReviewed>(s0, ls, t, a); }
pub proof fn laws_ivf_index_graph_unchecked_reviewed(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CatalogM<IvfIndexGraphUncheckedReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_catalog::<IvfIndexGraphUncheckedReviewed>(s0, ls, t, a); }
pub proof fn laws_identity_fail_open_reviewed(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CatalogM<IdentityFailOpenReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_catalog::<IdentityFailOpenReviewed>(s0, ls, t, a); }
pub proof fn laws_short_hash_name_reviewed(s0: CS, ls: Seq<CA>, t: CS, a: CA) requires reached::<CatalogM<ShortHashNameReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_catalog::<ShortHashNameReviewed>(s0, ls, t, a); }

// ---------------------------------------------------------------- as-built variants that depart (parameters only)

/// bm25-index-graph-unchecked as built (F-0707): 07/bm25-index; read under USE GRAPH without checking the graph the
/// index was built for (translator.py:3133-3134, 3283-3292).
pub struct Bm25IndexGraphUncheckedAsBuilt;
impl CatalogPolicy for Bm25IndexGraphUncheckedAsBuilt { open spec fn cfg() -> CatCfg { CatCfg { read_checked: false, ..canon_cfg() } } }
pub proof fn keep_bm25_index_graph_unchecked_l1() ensures obl_l1::<Bm25IndexGraphUncheckedAsBuilt>() {}
pub proof fn refute_bm25_index_graph_unchecked_l2() ensures !obl_l2::<Bm25IndexGraphUncheckedAsBuilt>() {}
pub proof fn keep_bm25_index_graph_unchecked_l3() ensures obl_l3::<Bm25IndexGraphUncheckedAsBuilt>() {}

/// bm25-index-graph-unchecked as built (F-0705): 07/bm25-index, 17/index-handle; the index records no graph and is read
/// as the default graph's (BM25Index.cls:608-612).
pub struct Bm25IndexNoRecordAsBuilt;
impl CatalogPolicy for Bm25IndexNoRecordAsBuilt { open spec fn cfg() -> CatCfg { CatCfg { records: false, ..canon_cfg() } } }
pub proof fn refute_bm25_index_no_record_l1() ensures !obl_l1::<Bm25IndexNoRecordAsBuilt>() {}
pub proof fn refute_bm25_index_no_record_l2() ensures !obl_l2::<Bm25IndexNoRecordAsBuilt>() {}
pub proof fn keep_bm25_index_no_record_l3() ensures obl_l3::<Bm25IndexNoRecordAsBuilt>() {}

/// ivf-index-graph-unchecked as built (F-0609): 06/ivf-index; the fused search may read an IVF index built for another
/// graph (vector.py:194-225).
pub struct IvfIndexGraphUncheckedAsBuilt;
impl CatalogPolicy for IvfIndexGraphUncheckedAsBuilt { open spec fn cfg() -> CatCfg { CatCfg { read_checked: false, ..canon_cfg() } } }
pub proof fn keep_ivf_index_graph_unchecked_l1() ensures obl_l1::<IvfIndexGraphUncheckedAsBuilt>() {}
pub proof fn refute_ivf_index_graph_unchecked_l2() ensures !obl_l2::<IvfIndexGraphUncheckedAsBuilt>() {}
pub proof fn keep_ivf_index_graph_unchecked_l3() ensures obl_l3::<IvfIndexGraphUncheckedAsBuilt>() {}

/// identity-fail-open as built (F-0601, F-0602, F-0603, F-0613): 06/registry-row; a failed registry read lets the
/// write through unchecked (schema.py:1033-1061, embeddings.py:157-197, 2033-2049).
pub struct IdentityFailOpenAsBuilt;
impl CatalogPolicy for IdentityFailOpenAsBuilt { open spec fn cfg() -> CatCfg { CatCfg { fail_open: true, ..canon_cfg() } } }
pub proof fn keep_identity_fail_open_l1() ensures obl_l1::<IdentityFailOpenAsBuilt>() {}
pub proof fn refute_identity_fail_open_l2() ensures !obl_l2::<IdentityFailOpenAsBuilt>() {}
pub proof fn keep_identity_fail_open_l3() ensures obl_l3::<IdentityFailOpenAsBuilt>() {}

/// short-hash-name as built (F-0901, F-C0901): 09/compiled-shape; two plan shapes share one 32-bit checksum name
/// (Gen.cls:69-80).
pub struct ShortHashNameAsBuilt;
impl CatalogPolicy for ShortHashNameAsBuilt { open spec fn cfg() -> CatCfg { CatCfg { naming: Naming::ShortHash, ..canon_cfg() } } }
pub proof fn keep_short_hash_name_l1() ensures obl_l1::<ShortHashNameAsBuilt>() {}
pub proof fn keep_short_hash_name_l2() ensures obl_l2::<ShortHashNameAsBuilt>() {}
pub proof fn refute_short_hash_name_l3() ensures !obl_l3::<ShortHashNameAsBuilt>() {}

// ---------------------------------------------------------------- generic mutants of the canonical instance

/// catalog-control-C1-unchecked-read: a read uses an artifact without checking its binding.
pub struct CtlUncheckedRead;
impl CatalogPolicy for CtlUncheckedRead { open spec fn cfg() -> CatCfg { CatCfg { read_checked: false, ..canon_cfg() } } }
pub proof fn keep_ctl_unchecked_read_l1() ensures obl_l1::<CtlUncheckedRead>() {}
pub proof fn refute_ctl_unchecked_read_l2() ensures !obl_l2::<CtlUncheckedRead>() {}
pub proof fn keep_ctl_unchecked_read_l3() ensures obl_l3::<CtlUncheckedRead>() {}

/// catalog-control-C2-short-hash: two pairs share a name.
pub struct CtlShortHash;
impl CatalogPolicy for CtlShortHash { open spec fn cfg() -> CatCfg { CatCfg { naming: Naming::ShortHash, ..canon_cfg() } } }
pub proof fn keep_ctl_short_hash_l1() ensures obl_l1::<CtlShortHash>() {}
pub proof fn keep_ctl_short_hash_l2() ensures obl_l2::<CtlShortHash>() {}
pub proof fn refute_ctl_short_hash_l3() ensures !obl_l3::<CtlShortHash>() {}

/// catalog-control-C3-no-record: an artifact records no binding.
pub struct CtlNoRecord;
impl CatalogPolicy for CtlNoRecord { open spec fn cfg() -> CatCfg { CatCfg { records: false, ..canon_cfg() } } }
pub proof fn refute_ctl_no_record_l1() ensures !obl_l1::<CtlNoRecord>() {}
pub proof fn refute_ctl_no_record_l2() ensures !obl_l2::<CtlNoRecord>() {}
pub proof fn keep_ctl_no_record_l3() ensures obl_l3::<CtlNoRecord>() {}

/// catalog-control-C4-fail-open: a failed check lets the write through.
pub struct CtlFailOpen;
impl CatalogPolicy for CtlFailOpen { open spec fn cfg() -> CatCfg { CatCfg { fail_open: true, ..canon_cfg() } } }
pub proof fn keep_ctl_fail_open_l1() ensures obl_l1::<CtlFailOpen>() {}
pub proof fn refute_ctl_fail_open_l2() ensures !obl_l2::<CtlFailOpen>() {}
pub proof fn keep_ctl_fail_open_l3() ensures obl_l3::<CtlFailOpen>() {}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witness)

/// catalog-sharp-three-artifacts: the canonical design binds all three pairs' artifacts.
pub proof fn sharp_three_artifacts()
    ensures ({
        let t = run::<CatalogM<CatalogCanonical>>(catalog_s0(), seq![CA::Create(0), CA::Create(1), CA::Create(2)]);
        t is Some && t->0.slots[0] is Some && t->0.slots[1] is Some && t->0.slots[2] is Some
    })
{
    reveal_with_fuel(run, 4);
}

} // verus!
