//! M-04 counterexamples: for each departing variant and each law it breaks, a run of the generic machine with that
//! variant's parameters from the initial state to a violation (the explorer's counterexample shapes, restated).
use vstd::prelude::*;
use crate::exec::*;
use crate::m04_derived::*;
use crate::i04_derived::*;

verus! {

/// derived-degree-cache-as-built-F0402: M04-L1.
pub proof fn cx_degree_cache_f0402_l1()
    ensures ({
        let t = run::<DerivedM<DegreeCacheF0402>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::RToken, DA::RCompute, DA::RStore, DA::Rollback]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 7);
}

/// derived-degree-cache-as-built-F0402: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_degree_cache_f0402_l4()
    ensures ({
        let s = run::<DerivedM<DegreeCacheF0402>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::RToken, DA::RCompute, DA::RStore, DA::Rollback]);
        s is Some && derived_step::<DegreeCacheF0402>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<DegreeCacheF0402>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 7);
}

/// derived-degree-cache-as-built-FC0401: M04-L1.
pub proof fn cx_degree_cache_fc0401_l1()
    ensures ({
        let t = run::<DerivedM<DegreeCacheFC0401>>(derived_s0(), seq![DA::RToken, DA::RProbe, DA::Begin(0), DA::Write(2), DA::RCompute, DA::RStore, DA::Rollback]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 8);
}

/// derived-degree-cache-as-built-FC0401: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_degree_cache_fc0401_l4()
    ensures ({
        let s = run::<DerivedM<DegreeCacheFC0401>>(derived_s0(), seq![DA::RToken, DA::RProbe, DA::Begin(0), DA::Write(2), DA::RCompute, DA::RStore, DA::Rollback]);
        s is Some && derived_step::<DegreeCacheFC0401>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<DegreeCacheFC0401>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 8);
}

/// derived-degree-cache-as-built-F0406: M04-L1.
pub proof fn cx_degree_cache_f0406_l1()
    ensures ({
        let t = run::<DerivedM<DegreeCacheF0406>>(derived_s0(), seq![DA::Clear]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// derived-degree-cache-as-built-F0406: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_degree_cache_f0406_l4()
    ensures ({
        let s = run::<DerivedM<DegreeCacheF0406>>(derived_s0(), seq![DA::Clear]);
        s is Some && derived_step::<DegreeCacheF0406>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<DegreeCacheF0406>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// derived-result-cache-04-as-built-F0402: M04-L1.
pub proof fn cx_result_cache_04_f0402_l1()
    ensures ({
        let t = run::<DerivedM<ResultCache04F0402>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::RToken, DA::RCompute, DA::RStore, DA::Rollback]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 7);
}

/// derived-result-cache-04-as-built-F0402: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_result_cache_04_f0402_l4()
    ensures ({
        let s = run::<DerivedM<ResultCache04F0402>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::RToken, DA::RCompute, DA::RStore, DA::Rollback]);
        s is Some && derived_step::<ResultCache04F0402>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<ResultCache04F0402>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 7);
}

/// derived-algo-cache-edgeless-as-built-F1004: M04-L1.
pub proof fn cx_algo_cache_edgeless_f1004_l1()
    ensures ({
        let t = run::<DerivedM<AlgoCacheEdgelessF1004>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-algo-cache-edgeless-as-built-F1004: M04-L2 (a commit through the unmaintained path changes the source with no token move).
pub proof fn cx_algo_cache_edgeless_f1004_l2()
    ensures ({
        let s = run::<DerivedM<AlgoCacheEdgelessF1004>>(derived_s0(), seq![DA::Begin(1), DA::Write(2)]);
        s is Some && derived_step::<AlgoCacheEdgelessF1004>(s->0, DA::Commit) is Some
            && !law_l2::<AlgoCacheEdgelessF1004>(s->0, DA::Commit, derived_step::<AlgoCacheEdgelessF1004>(s->0, DA::Commit)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// derived-algo-cache-edgeless-as-built-F1004: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_algo_cache_edgeless_f1004_l4()
    ensures ({
        let s = run::<DerivedM<AlgoCacheEdgelessF1004>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<AlgoCacheEdgelessF1004>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<AlgoCacheEdgelessF1004>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-interned-snapshot-as-built-F1005: M04-L1.
pub proof fn cx_interned_snapshot_f1005_l1()
    ensures ({
        let t = run::<DerivedM<InternedSnapshotF1005>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-interned-snapshot-as-built-F1005: M04-L2 (a commit through the unmaintained path changes the source with no token move).
pub proof fn cx_interned_snapshot_f1005_l2()
    ensures ({
        let s = run::<DerivedM<InternedSnapshotF1005>>(derived_s0(), seq![DA::Begin(1), DA::Write(2)]);
        s is Some && derived_step::<InternedSnapshotF1005>(s->0, DA::Commit) is Some
            && !law_l2::<InternedSnapshotF1005>(s->0, DA::Commit, derived_step::<InternedSnapshotF1005>(s->0, DA::Commit)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// derived-interned-snapshot-as-built-F1005: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_interned_snapshot_f1005_l4()
    ensures ({
        let s = run::<DerivedM<InternedSnapshotF1005>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<InternedSnapshotF1005>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<InternedSnapshotF1005>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-interned-snapshot-as-built-FC0801: M04-L1.
pub proof fn cx_interned_snapshot_fc0801_l1()
    ensures ({
        let t = run::<DerivedM<InternedSnapshotFC0801>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Rollback]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-interned-snapshot-as-built-FC0801: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_interned_snapshot_fc0801_l4()
    ensures ({
        let s = run::<DerivedM<InternedSnapshotFC0801>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Rollback]);
        s is Some && derived_step::<InternedSnapshotFC0801>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<InternedSnapshotFC0801>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-bm25-text-change-as-built-F0703: M04-L1.
pub proof fn cx_bm25_text_change_f0703_l1()
    ensures ({
        let t = run::<DerivedM<Bm25TextChangeF0703>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-bm25-text-change-as-built-F0703: M04-L2 (a commit through the unmaintained path changes the source with no token move).
pub proof fn cx_bm25_text_change_f0703_l2()
    ensures ({
        let s = run::<DerivedM<Bm25TextChangeF0703>>(derived_s0(), seq![DA::Begin(1), DA::Write(2)]);
        s is Some && derived_step::<Bm25TextChangeF0703>(s->0, DA::Commit) is Some
            && !law_l2::<Bm25TextChangeF0703>(s->0, DA::Commit, derived_step::<Bm25TextChangeF0703>(s->0, DA::Commit)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// derived-bm25-text-change-as-built-F0703: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_bm25_text_change_f0703_l4()
    ensures ({
        let s = run::<DerivedM<Bm25TextChangeF0703>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<Bm25TextChangeF0703>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<Bm25TextChangeF0703>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-statement-map-direct-delete-as-built-F0303: M04-L1.
pub proof fn cx_statement_map_direct_delete_f0303_l1()
    ensures ({
        let t = run::<DerivedM<StatementMapDirectDeleteF0303>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-statement-map-direct-delete-as-built-F0303: M04-L2 (a commit through the unmaintained path changes the source with no token move).
pub proof fn cx_statement_map_direct_delete_f0303_l2()
    ensures ({
        let s = run::<DerivedM<StatementMapDirectDeleteF0303>>(derived_s0(), seq![DA::Begin(1), DA::Write(2)]);
        s is Some && derived_step::<StatementMapDirectDeleteF0303>(s->0, DA::Commit) is Some
            && !law_l2::<StatementMapDirectDeleteF0303>(s->0, DA::Commit, derived_step::<StatementMapDirectDeleteF0303>(s->0, DA::Commit)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// derived-statement-map-direct-delete-as-built-F0303: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_statement_map_direct_delete_f0303_l4()
    ensures ({
        let s = run::<DerivedM<StatementMapDirectDeleteF0303>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<StatementMapDirectDeleteF0303>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<StatementMapDirectDeleteF0303>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-bucket-aggregate-update-as-built-F0501: M04-L1.
pub proof fn cx_bucket_aggregate_update_f0501_l1()
    ensures ({
        let t = run::<DerivedM<BucketAggregateUpdateF0501>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-bucket-aggregate-update-as-built-F0501: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_bucket_aggregate_update_f0501_l4()
    ensures ({
        let s = run::<DerivedM<BucketAggregateUpdateF0501>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<BucketAggregateUpdateF0501>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<BucketAggregateUpdateF0501>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-engine-mode-cache-as-built-F0208: M04-L1.
pub proof fn cx_engine_mode_cache_f0208_l1()
    ensures ({
        let t = run::<DerivedM<EngineModeCacheF0208>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-engine-mode-cache-as-built-F0208: M04-L2 (a commit through the unmaintained path changes the source with no token move).
pub proof fn cx_engine_mode_cache_f0208_l2()
    ensures ({
        let s = run::<DerivedM<EngineModeCacheF0208>>(derived_s0(), seq![DA::Begin(0), DA::Write(2)]);
        s is Some && derived_step::<EngineModeCacheF0208>(s->0, DA::Commit) is Some
            && !law_l2::<EngineModeCacheF0208>(s->0, DA::Commit, derived_step::<EngineModeCacheF0208>(s->0, DA::Commit)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// derived-engine-mode-cache-as-built-F0208: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_engine_mode_cache_f0208_l4()
    ensures ({
        let s = run::<DerivedM<EngineModeCacheF0208>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<EngineModeCacheF0208>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<EngineModeCacheF0208>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-ttl-cache-as-built-F0302: M04-L1.
pub proof fn cx_ttl_cache_f0302_l1()
    ensures ({
        let t = run::<DerivedM<TtlCacheF0302>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-ttl-cache-as-built-F0302: M04-L2 (a commit through the unmaintained path changes the source with no token move).
pub proof fn cx_ttl_cache_f0302_l2()
    ensures ({
        let s = run::<DerivedM<TtlCacheF0302>>(derived_s0(), seq![DA::Begin(0), DA::Write(2)]);
        s is Some && derived_step::<TtlCacheF0302>(s->0, DA::Commit) is Some
            && !law_l2::<TtlCacheF0302>(s->0, DA::Commit, derived_step::<TtlCacheF0302>(s->0, DA::Commit)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// derived-ttl-cache-as-built-F0302: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_ttl_cache_f0302_l4()
    ensures ({
        let s = run::<DerivedM<TtlCacheF0302>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<TtlCacheF0302>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<TtlCacheF0302>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-ttl-cache-as-built-EXC05: M04-L1.
pub proof fn cx_ttl_cache_exc05_l1()
    ensures ({
        let t = run::<DerivedM<TtlCacheEXC05>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-ttl-cache-as-built-EXC05: M04-L2 (a commit through the unmaintained path changes the source with no token move).
pub proof fn cx_ttl_cache_exc05_l2()
    ensures ({
        let s = run::<DerivedM<TtlCacheEXC05>>(derived_s0(), seq![DA::Begin(0), DA::Write(2)]);
        s is Some && derived_step::<TtlCacheEXC05>(s->0, DA::Commit) is Some
            && !law_l2::<TtlCacheEXC05>(s->0, DA::Commit, derived_step::<TtlCacheEXC05>(s->0, DA::Commit)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// derived-ttl-cache-as-built-EXC05: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_ttl_cache_exc05_l4()
    ensures ({
        let s = run::<DerivedM<TtlCacheEXC05>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<TtlCacheEXC05>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<TtlCacheEXC05>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-native-gate-label-index-as-built-F0906: M04-L1.
pub proof fn cx_native_gate_label_index_f0906_l1()
    ensures ({
        let t = run::<DerivedM<NativeGateLabelIndexF0906>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-native-gate-label-index-as-built-F0906: M04-L2 (a commit through the unmaintained path changes the source with no token move).
pub proof fn cx_native_gate_label_index_f0906_l2()
    ensures ({
        let s = run::<DerivedM<NativeGateLabelIndexF0906>>(derived_s0(), seq![DA::Begin(0), DA::Write(2)]);
        s is Some && derived_step::<NativeGateLabelIndexF0906>(s->0, DA::Commit) is Some
            && !law_l2::<NativeGateLabelIndexF0906>(s->0, DA::Commit, derived_step::<NativeGateLabelIndexF0906>(s->0, DA::Commit)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// derived-native-gate-label-index-as-built-F0906: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_native_gate_label_index_f0906_l4()
    ensures ({
        let s = run::<DerivedM<NativeGateLabelIndexF0906>>(derived_s0(), seq![DA::Begin(0), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<NativeGateLabelIndexF0906>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<NativeGateLabelIndexF0906>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-ivf-erase-as-built-F0606: M04-L1.
pub proof fn cx_ivf_erase_f0606_l1()
    ensures ({
        let t = run::<DerivedM<IvfEraseF0606>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-ivf-erase-as-built-F0606: M04-L2 (a commit through the unmaintained path changes the source with no token move).
pub proof fn cx_ivf_erase_f0606_l2()
    ensures ({
        let s = run::<DerivedM<IvfEraseF0606>>(derived_s0(), seq![DA::Begin(1), DA::Write(2)]);
        s is Some && derived_step::<IvfEraseF0606>(s->0, DA::Commit) is Some
            && !law_l2::<IvfEraseF0606>(s->0, DA::Commit, derived_step::<IvfEraseF0606>(s->0, DA::Commit)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// derived-ivf-erase-as-built-F0606: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_ivf_erase_f0606_l4()
    ensures ({
        let s = run::<DerivedM<IvfEraseF0606>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<IvfEraseF0606>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<IvfEraseF0606>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-control-C1-unmaintained-path: M04-L1.
pub proof fn cx_ctl_unmaintained_path_l1()
    ensures ({
        let t = run::<DerivedM<CtlUnmaintainedPath>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-control-C1-unmaintained-path: M04-L2 (a commit through the unmaintained path changes the source with no token move).
pub proof fn cx_ctl_unmaintained_path_l2()
    ensures ({
        let s = run::<DerivedM<CtlUnmaintainedPath>>(derived_s0(), seq![DA::Begin(1), DA::Write(2)]);
        s is Some && derived_step::<CtlUnmaintainedPath>(s->0, DA::Commit) is Some
            && !law_l2::<CtlUnmaintainedPath>(s->0, DA::Commit, derived_step::<CtlUnmaintainedPath>(s->0, DA::Commit)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// derived-control-C1-unmaintained-path: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_ctl_unmaintained_path_l4()
    ensures ({
        let s = run::<DerivedM<CtlUnmaintainedPath>>(derived_s0(), seq![DA::Begin(1), DA::Write(2), DA::Commit]);
        s is Some && derived_step::<CtlUnmaintainedPath>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<CtlUnmaintainedPath>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// derived-control-C2-token-after-compute: M04-L1.
pub proof fn cx_ctl_token_after_compute_l1()
    ensures ({
        let t = run::<DerivedM<CtlTokenAfterCompute>>(derived_s0(), seq![DA::RCompute, DA::Begin(0), DA::PreBump, DA::Write(2), DA::PostBump, DA::Commit, DA::RToken, DA::RStore]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 9);
}

/// derived-control-C2-token-after-compute: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_ctl_token_after_compute_l4()
    ensures ({
        let s = run::<DerivedM<CtlTokenAfterCompute>>(derived_s0(), seq![DA::RCompute, DA::Begin(0), DA::PreBump, DA::Write(2), DA::PostBump, DA::Commit, DA::RToken, DA::RStore]);
        s is Some && derived_step::<CtlTokenAfterCompute>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<CtlTokenAfterCompute>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 9);
}

/// derived-control-C3-rebuild-stamp-only: M04-L1.
pub proof fn cx_ctl_rebuild_stamp_only_l1()
    ensures ({
        let t = run::<DerivedM<CtlRebuildStampOnly>>(derived_s0(), seq![DA::Begin(0), DA::PreBump, DA::Write(2), DA::PostBump, DA::Commit, DA::Rebuild]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 7);
}

/// derived-control-C3-rebuild-stamp-only: M04-L3 (after a committed write, the rebuild restamps the old value).
pub proof fn cx_ctl_rebuild_stamp_only_l3()
    ensures ({
        let s = run::<DerivedM<CtlRebuildStampOnly>>(derived_s0(), seq![DA::Begin(0), DA::PreBump, DA::Write(2), DA::PostBump, DA::Commit]);
        s is Some && derived_step::<CtlRebuildStampOnly>(s->0, DA::Rebuild) is Some && !law_l3(DA::Rebuild, derived_step::<CtlRebuildStampOnly>(s->0, DA::Rebuild)->0)
    })
{
    reveal_with_fuel(run, 6);
}

/// derived-control-C3-rebuild-stamp-only: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_ctl_rebuild_stamp_only_l4()
    ensures ({
        let s = run::<DerivedM<CtlRebuildStampOnly>>(derived_s0(), seq![DA::Begin(0), DA::PreBump, DA::Write(2), DA::PostBump, DA::Commit, DA::Rebuild]);
        s is Some && derived_step::<CtlRebuildStampOnly>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<CtlRebuildStampOnly>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 7);
}

/// derived-control-C4-unchecked-gate: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_ctl_unchecked_gate_l4()
    ensures ({
        let s = run::<DerivedM<CtlUncheckedGate>>(derived_s0(), seq![DA::Begin(0), DA::PreBump, DA::Write(2), DA::PostBump, DA::Commit]);
        s is Some && derived_step::<CtlUncheckedGate>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<CtlUncheckedGate>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 6);
}

/// derived-control-C5-probe-late: M04-L1.
pub proof fn cx_ctl_probe_late_l1()
    ensures ({
        let t = run::<DerivedM<CtlProbeLate>>(derived_s0(), seq![DA::Begin(0), DA::PreBump, DA::Write(2), DA::RToken, DA::RCompute, DA::Rollback, DA::RProbe, DA::RStore]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 9);
}

/// derived-control-C5-probe-late: M04-L4 (an answer through the gate differs from the source).
pub proof fn cx_ctl_probe_late_l4()
    ensures ({
        let s = run::<DerivedM<CtlProbeLate>>(derived_s0(), seq![DA::Begin(0), DA::PreBump, DA::Write(2), DA::RToken, DA::RCompute, DA::Rollback, DA::RProbe, DA::RStore]);
        s is Some && derived_step::<CtlProbeLate>(s->0, DA::Answer) is Some && !law_l4(DA::Answer, derived_step::<CtlProbeLate>(s->0, DA::Answer)->0)
    })
{
    reveal_with_fuel(run, 9);
}

} // verus!
