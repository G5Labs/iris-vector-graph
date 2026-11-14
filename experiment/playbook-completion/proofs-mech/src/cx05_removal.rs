//! M-05 counterexamples: for each departing variant and each law it breaks, a run from the initial state to a
//! violation (L1: write the missed store, erase, redact; L3: write the missed store; L2: both targets write, erase one).
use vstd::prelude::*;
use crate::exec::*;
use crate::m05_removal::*;
use crate::i05_removal::*;

verus! {

pub proof fn cx_bm25_l1()
    ensures ({
        let t = run::<RemovalM<Bm25AsBuilt>>(removal_s0(), seq![RmA::Write(0, 1), RmA::Erase(0), RmA::Redact(0)]);
        t is Some && !law_l1::<Bm25AsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let s0 = removal_s0();
    let s1 = removal_step::<Bm25AsBuilt>(s0, RmA::Write(0, 1))->0;
    assert(Bm25AsBuilt::cfg().paths[1].contains(1nat) && !s0.content[0].contains(1nat));
    assert(removal_step::<Bm25AsBuilt>(s0, RmA::Write(0, 1)) is Some);
    assert(s1.content[0].contains(1nat));
    let s2 = removal_step::<Bm25AsBuilt>(s1, RmA::Erase(0))->0;
    assert(s1.content[0].contains(1nat));
    assert(removal_step::<Bm25AsBuilt>(s1, RmA::Erase(0)) is Some);
    let s3 = removal_step::<Bm25AsBuilt>(s2, RmA::Redact(0))->0;
    assert(removal_step::<Bm25AsBuilt>(s2, RmA::Redact(0)) is Some);
    assert(s3.redacted[0] && s3.content[0].contains(1nat) && !Bm25AsBuilt::cfg().receipt.contains(1nat));
    assert(run::<RemovalM<Bm25AsBuilt>>(removal_s0(), seq![RmA::Write(0, 1), RmA::Erase(0), RmA::Redact(0)]) == Some(s3));
}

pub proof fn cx_bm25_l3()
    ensures ({
        let t = run::<RemovalM<Bm25AsBuilt>>(removal_s0(), seq![RmA::Write(0, 1)]);
        t is Some && !law_l3::<Bm25AsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let s0 = removal_s0();
    let s1 = removal_step::<Bm25AsBuilt>(s0, RmA::Write(0, 1))->0;
    assert(Bm25AsBuilt::cfg().paths[1].contains(1nat) && !s0.content[0].contains(1nat));
    assert(removal_step::<Bm25AsBuilt>(s0, RmA::Write(0, 1)) is Some);
    assert(s1.content[0].contains(1nat));
    assert(s1.content[0].contains(1nat) && !reached_by_removal::<Bm25AsBuilt>(1nat));
    assert(run::<RemovalM<Bm25AsBuilt>>(removal_s0(), seq![RmA::Write(0, 1)]) == Some(s1));
}

pub proof fn cx_vector_indexes_l1()
    ensures ({
        let t = run::<RemovalM<VectorIndexesAsBuilt>>(removal_s0(), seq![RmA::Write(0, 2), RmA::Erase(0), RmA::Redact(0)]);
        t is Some && !law_l1::<VectorIndexesAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let s0 = removal_s0();
    let s1 = removal_step::<VectorIndexesAsBuilt>(s0, RmA::Write(0, 2))->0;
    assert(VectorIndexesAsBuilt::cfg().paths[2].contains(2nat) && !s0.content[0].contains(2nat));
    assert(removal_step::<VectorIndexesAsBuilt>(s0, RmA::Write(0, 2)) is Some);
    assert(s1.content[0].contains(2nat));
    let s2 = removal_step::<VectorIndexesAsBuilt>(s1, RmA::Erase(0))->0;
    assert(s1.content[0].contains(2nat));
    assert(removal_step::<VectorIndexesAsBuilt>(s1, RmA::Erase(0)) is Some);
    let s3 = removal_step::<VectorIndexesAsBuilt>(s2, RmA::Redact(0))->0;
    assert(removal_step::<VectorIndexesAsBuilt>(s2, RmA::Redact(0)) is Some);
    assert(s3.redacted[0] && s3.content[0].contains(2nat) && !VectorIndexesAsBuilt::cfg().receipt.contains(2nat));
    assert(run::<RemovalM<VectorIndexesAsBuilt>>(removal_s0(), seq![RmA::Write(0, 2), RmA::Erase(0), RmA::Redact(0)]) == Some(s3));
}

pub proof fn cx_vector_indexes_l3()
    ensures ({
        let t = run::<RemovalM<VectorIndexesAsBuilt>>(removal_s0(), seq![RmA::Write(0, 2)]);
        t is Some && !law_l3::<VectorIndexesAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let s0 = removal_s0();
    let s1 = removal_step::<VectorIndexesAsBuilt>(s0, RmA::Write(0, 2))->0;
    assert(VectorIndexesAsBuilt::cfg().paths[2].contains(2nat) && !s0.content[0].contains(2nat));
    assert(removal_step::<VectorIndexesAsBuilt>(s0, RmA::Write(0, 2)) is Some);
    assert(s1.content[0].contains(2nat));
    assert(s1.content[0].contains(2nat) && !reached_by_removal::<VectorIndexesAsBuilt>(2nat));
    assert(run::<RemovalM<VectorIndexesAsBuilt>>(removal_s0(), seq![RmA::Write(0, 2)]) == Some(s1));
}

pub proof fn cx_quarantine_l1()
    ensures ({
        let t = run::<RemovalM<QuarantineAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1), RmA::Erase(0), RmA::Redact(0)]);
        t is Some && !law_l1::<QuarantineAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let s0 = removal_s0();
    let s1 = removal_step::<QuarantineAsBuilt>(s0, RmA::Write(0, 1))->0;
    assert(QuarantineAsBuilt::cfg().paths[1].contains(1nat) && !s0.content[0].contains(1nat));
    assert(removal_step::<QuarantineAsBuilt>(s0, RmA::Write(0, 1)) is Some);
    assert(s1.content[0].contains(1nat));
    let s2 = removal_step::<QuarantineAsBuilt>(s1, RmA::Erase(0))->0;
    assert(s1.content[0].contains(1nat));
    assert(removal_step::<QuarantineAsBuilt>(s1, RmA::Erase(0)) is Some);
    let s3 = removal_step::<QuarantineAsBuilt>(s2, RmA::Redact(0))->0;
    assert(removal_step::<QuarantineAsBuilt>(s2, RmA::Redact(0)) is Some);
    assert(s3.redacted[0] && s3.content[0].contains(1nat) && !QuarantineAsBuilt::cfg().receipt.contains(1nat));
    assert(run::<RemovalM<QuarantineAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1), RmA::Erase(0), RmA::Redact(0)]) == Some(s3));
}

pub proof fn cx_quarantine_l3()
    ensures ({
        let t = run::<RemovalM<QuarantineAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1)]);
        t is Some && !law_l3::<QuarantineAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let s0 = removal_s0();
    let s1 = removal_step::<QuarantineAsBuilt>(s0, RmA::Write(0, 1))->0;
    assert(QuarantineAsBuilt::cfg().paths[1].contains(1nat) && !s0.content[0].contains(1nat));
    assert(removal_step::<QuarantineAsBuilt>(s0, RmA::Write(0, 1)) is Some);
    assert(s1.content[0].contains(1nat));
    assert(s1.content[0].contains(1nat) && !reached_by_removal::<QuarantineAsBuilt>(1nat));
    assert(run::<RemovalM<QuarantineAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1)]) == Some(s1));
}

pub proof fn cx_snapshot_archives_l1()
    ensures ({
        let t = run::<RemovalM<SnapshotArchivesAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1), RmA::Erase(0), RmA::Redact(0)]);
        t is Some && !law_l1::<SnapshotArchivesAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let s0 = removal_s0();
    let s1 = removal_step::<SnapshotArchivesAsBuilt>(s0, RmA::Write(0, 1))->0;
    assert(SnapshotArchivesAsBuilt::cfg().paths[1].contains(2nat) && !s0.content[0].contains(2nat));
    assert(removal_step::<SnapshotArchivesAsBuilt>(s0, RmA::Write(0, 1)) is Some);
    assert(s1.content[0].contains(2nat));
    let s2 = removal_step::<SnapshotArchivesAsBuilt>(s1, RmA::Erase(0))->0;
    assert(s1.content[0].contains(2nat));
    assert(removal_step::<SnapshotArchivesAsBuilt>(s1, RmA::Erase(0)) is Some);
    let s3 = removal_step::<SnapshotArchivesAsBuilt>(s2, RmA::Redact(0))->0;
    assert(removal_step::<SnapshotArchivesAsBuilt>(s2, RmA::Redact(0)) is Some);
    assert(s3.redacted[0] && s3.content[0].contains(2nat) && !SnapshotArchivesAsBuilt::cfg().receipt.contains(2nat));
    assert(run::<RemovalM<SnapshotArchivesAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1), RmA::Erase(0), RmA::Redact(0)]) == Some(s3));
}

pub proof fn cx_snapshot_archives_l3()
    ensures ({
        let t = run::<RemovalM<SnapshotArchivesAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1)]);
        t is Some && !law_l3::<SnapshotArchivesAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let s0 = removal_s0();
    let s1 = removal_step::<SnapshotArchivesAsBuilt>(s0, RmA::Write(0, 1))->0;
    assert(SnapshotArchivesAsBuilt::cfg().paths[1].contains(2nat) && !s0.content[0].contains(2nat));
    assert(removal_step::<SnapshotArchivesAsBuilt>(s0, RmA::Write(0, 1)) is Some);
    assert(s1.content[0].contains(2nat));
    assert(s1.content[0].contains(2nat) && !reached_by_removal::<SnapshotArchivesAsBuilt>(2nat));
    assert(run::<RemovalM<SnapshotArchivesAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1)]) == Some(s1));
}

pub proof fn cx_reifier_default_graph_l1()
    ensures ({
        let t = run::<RemovalM<ReifierDefaultGraphAsBuilt>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Erase(0), RmA::Redact(0)]);
        t is Some && !law_l1::<ReifierDefaultGraphAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let s0 = removal_s0();
    let s1 = removal_step::<ReifierDefaultGraphAsBuilt>(s0, RmA::Write(0, 0))->0;
    assert(ReifierDefaultGraphAsBuilt::cfg().paths[0].contains(1nat) && !s0.content[0].contains(1nat));
    assert(removal_step::<ReifierDefaultGraphAsBuilt>(s0, RmA::Write(0, 0)) is Some);
    assert(s1.content[0].contains(1nat));
    let s2 = removal_step::<ReifierDefaultGraphAsBuilt>(s1, RmA::Erase(0))->0;
    assert(s1.content[0].contains(1nat));
    assert(removal_step::<ReifierDefaultGraphAsBuilt>(s1, RmA::Erase(0)) is Some);
    let s3 = removal_step::<ReifierDefaultGraphAsBuilt>(s2, RmA::Redact(0))->0;
    assert(removal_step::<ReifierDefaultGraphAsBuilt>(s2, RmA::Redact(0)) is Some);
    assert(s3.redacted[0] && s3.content[0].contains(1nat) && !ReifierDefaultGraphAsBuilt::cfg().receipt.contains(1nat));
    assert(run::<RemovalM<ReifierDefaultGraphAsBuilt>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Erase(0), RmA::Redact(0)]) == Some(s3));
}

pub proof fn cx_reifier_default_graph_l3()
    ensures ({
        let t = run::<RemovalM<ReifierDefaultGraphAsBuilt>>(removal_s0(), seq![RmA::Write(0, 0)]);
        t is Some && !law_l3::<ReifierDefaultGraphAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let s0 = removal_s0();
    let s1 = removal_step::<ReifierDefaultGraphAsBuilt>(s0, RmA::Write(0, 0))->0;
    assert(ReifierDefaultGraphAsBuilt::cfg().paths[0].contains(1nat) && !s0.content[0].contains(1nat));
    assert(removal_step::<ReifierDefaultGraphAsBuilt>(s0, RmA::Write(0, 0)) is Some);
    assert(s1.content[0].contains(1nat));
    assert(s1.content[0].contains(1nat) && !reached_by_removal::<ReifierDefaultGraphAsBuilt>(1nat));
    assert(run::<RemovalM<ReifierDefaultGraphAsBuilt>>(removal_s0(), seq![RmA::Write(0, 0)]) == Some(s1));
}

pub proof fn cx_temporal_only_prefix_l1()
    ensures ({
        let t = run::<RemovalM<TemporalOnlyPrefixAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1), RmA::Erase(0), RmA::Redact(0)]);
        t is Some && !law_l1::<TemporalOnlyPrefixAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let s0 = removal_s0();
    let s1 = removal_step::<TemporalOnlyPrefixAsBuilt>(s0, RmA::Write(0, 1))->0;
    assert(TemporalOnlyPrefixAsBuilt::cfg().paths[1].contains(2nat) && !s0.content[0].contains(2nat));
    assert(removal_step::<TemporalOnlyPrefixAsBuilt>(s0, RmA::Write(0, 1)) is Some);
    assert(s1.content[0].contains(2nat));
    let s2 = removal_step::<TemporalOnlyPrefixAsBuilt>(s1, RmA::Erase(0))->0;
    assert(s1.content[0].contains(2nat));
    assert(removal_step::<TemporalOnlyPrefixAsBuilt>(s1, RmA::Erase(0)) is Some);
    let s3 = removal_step::<TemporalOnlyPrefixAsBuilt>(s2, RmA::Redact(0))->0;
    assert(removal_step::<TemporalOnlyPrefixAsBuilt>(s2, RmA::Redact(0)) is Some);
    assert(s3.redacted[0] && s3.content[0].contains(2nat) && !TemporalOnlyPrefixAsBuilt::cfg().receipt.contains(2nat));
    assert(run::<RemovalM<TemporalOnlyPrefixAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1), RmA::Erase(0), RmA::Redact(0)]) == Some(s3));
}

pub proof fn cx_temporal_only_prefix_l3()
    ensures ({
        let t = run::<RemovalM<TemporalOnlyPrefixAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1)]);
        t is Some && !law_l3::<TemporalOnlyPrefixAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let s0 = removal_s0();
    let s1 = removal_step::<TemporalOnlyPrefixAsBuilt>(s0, RmA::Write(0, 1))->0;
    assert(TemporalOnlyPrefixAsBuilt::cfg().paths[1].contains(2nat) && !s0.content[0].contains(2nat));
    assert(removal_step::<TemporalOnlyPrefixAsBuilt>(s0, RmA::Write(0, 1)) is Some);
    assert(s1.content[0].contains(2nat));
    assert(s1.content[0].contains(2nat) && !reached_by_removal::<TemporalOnlyPrefixAsBuilt>(2nat));
    assert(run::<RemovalM<TemporalOnlyPrefixAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1)]) == Some(s1));
}

pub proof fn cx_history_text_l1()
    ensures ({
        let t = run::<RemovalM<HistoryTextAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1), RmA::Erase(0), RmA::Redact(0)]);
        t is Some && !law_l1::<HistoryTextAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let s0 = removal_s0();
    let s1 = removal_step::<HistoryTextAsBuilt>(s0, RmA::Write(0, 1))->0;
    assert(HistoryTextAsBuilt::cfg().paths[1].contains(3nat) && !s0.content[0].contains(3nat));
    assert(removal_step::<HistoryTextAsBuilt>(s0, RmA::Write(0, 1)) is Some);
    assert(s1.content[0].contains(3nat));
    let s2 = removal_step::<HistoryTextAsBuilt>(s1, RmA::Erase(0))->0;
    assert(s1.content[0].contains(3nat));
    assert(removal_step::<HistoryTextAsBuilt>(s1, RmA::Erase(0)) is Some);
    let s3 = removal_step::<HistoryTextAsBuilt>(s2, RmA::Redact(0))->0;
    assert(removal_step::<HistoryTextAsBuilt>(s2, RmA::Redact(0)) is Some);
    assert(s3.redacted[0] && s3.content[0].contains(3nat) && !HistoryTextAsBuilt::cfg().receipt.contains(3nat));
    assert(run::<RemovalM<HistoryTextAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1), RmA::Erase(0), RmA::Redact(0)]) == Some(s3));
}

pub proof fn cx_history_text_l3()
    ensures ({
        let t = run::<RemovalM<HistoryTextAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1)]);
        t is Some && !law_l3::<HistoryTextAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let s0 = removal_s0();
    let s1 = removal_step::<HistoryTextAsBuilt>(s0, RmA::Write(0, 1))->0;
    assert(HistoryTextAsBuilt::cfg().paths[1].contains(3nat) && !s0.content[0].contains(3nat));
    assert(removal_step::<HistoryTextAsBuilt>(s0, RmA::Write(0, 1)) is Some);
    assert(s1.content[0].contains(3nat));
    assert(s1.content[0].contains(3nat) && !reached_by_removal::<HistoryTextAsBuilt>(3nat));
    assert(run::<RemovalM<HistoryTextAsBuilt>>(removal_s0(), seq![RmA::Write(0, 1)]) == Some(s1));
}

pub proof fn cx_default_routed_vectors_l1()
    ensures ({
        let t = run::<RemovalM<DefaultRoutedVectorsAsBuilt>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Erase(0), RmA::Redact(0)]);
        t is Some && !law_l1::<DefaultRoutedVectorsAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let s0 = removal_s0();
    let s1 = removal_step::<DefaultRoutedVectorsAsBuilt>(s0, RmA::Write(0, 0))->0;
    assert(DefaultRoutedVectorsAsBuilt::cfg().paths[0].contains(2nat) && !s0.content[0].contains(2nat));
    assert(removal_step::<DefaultRoutedVectorsAsBuilt>(s0, RmA::Write(0, 0)) is Some);
    assert(s1.content[0].contains(2nat));
    let s2 = removal_step::<DefaultRoutedVectorsAsBuilt>(s1, RmA::Erase(0))->0;
    assert(s1.content[0].contains(2nat));
    assert(removal_step::<DefaultRoutedVectorsAsBuilt>(s1, RmA::Erase(0)) is Some);
    let s3 = removal_step::<DefaultRoutedVectorsAsBuilt>(s2, RmA::Redact(0))->0;
    assert(removal_step::<DefaultRoutedVectorsAsBuilt>(s2, RmA::Redact(0)) is Some);
    assert(s3.redacted[0] && s3.content[0].contains(2nat) && !DefaultRoutedVectorsAsBuilt::cfg().receipt.contains(2nat));
    assert(run::<RemovalM<DefaultRoutedVectorsAsBuilt>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Erase(0), RmA::Redact(0)]) == Some(s3));
}

pub proof fn cx_default_routed_vectors_l3()
    ensures ({
        let t = run::<RemovalM<DefaultRoutedVectorsAsBuilt>>(removal_s0(), seq![RmA::Write(0, 0)]);
        t is Some && !law_l3::<DefaultRoutedVectorsAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let s0 = removal_s0();
    let s1 = removal_step::<DefaultRoutedVectorsAsBuilt>(s0, RmA::Write(0, 0))->0;
    assert(DefaultRoutedVectorsAsBuilt::cfg().paths[0].contains(2nat) && !s0.content[0].contains(2nat));
    assert(removal_step::<DefaultRoutedVectorsAsBuilt>(s0, RmA::Write(0, 0)) is Some);
    assert(s1.content[0].contains(2nat));
    assert(s1.content[0].contains(2nat) && !reached_by_removal::<DefaultRoutedVectorsAsBuilt>(2nat));
    assert(run::<RemovalM<DefaultRoutedVectorsAsBuilt>>(removal_s0(), seq![RmA::Write(0, 0)]) == Some(s1));
}

pub proof fn cx_temporal_purge_all_graphs_l2()
    ensures ({
        let s = run::<RemovalM<TemporalPurgeAllGraphsAsBuilt>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Write(1, 0)]);
        let a = RmA::Erase(0);
        s is Some && removal_step::<TemporalPurgeAllGraphsAsBuilt>(s->0, a) is Some && !law_l2(s->0, a, removal_step::<TemporalPurgeAllGraphsAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 3);
    let s0 = removal_s0();
    let s1 = removal_step::<TemporalPurgeAllGraphsAsBuilt>(s0, RmA::Write(0, 0))->0;
    assert(TemporalPurgeAllGraphsAsBuilt::cfg().paths[0].contains(0nat) && !s0.content[0].contains(0nat));
    assert(removal_step::<TemporalPurgeAllGraphsAsBuilt>(s0, RmA::Write(0, 0)) is Some);
    assert(s1.content[0].contains(0nat));
    let s2 = removal_step::<TemporalPurgeAllGraphsAsBuilt>(s1, RmA::Write(1, 0))->0;
    assert(TemporalPurgeAllGraphsAsBuilt::cfg().paths[0].contains(1nat) && !s1.content[1].contains(1nat));
    assert(removal_step::<TemporalPurgeAllGraphsAsBuilt>(s1, RmA::Write(1, 0)) is Some);
    assert(s2.content[1].contains(1nat));
    assert(run::<RemovalM<TemporalPurgeAllGraphsAsBuilt>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Write(1, 0)]) == Some(s2));
    assert(s2.content[0].contains(0nat));
    let t = removal_step::<TemporalPurgeAllGraphsAsBuilt>(s2, RmA::Erase(0))->0;
    assert(removal_step::<TemporalPurgeAllGraphsAsBuilt>(s2, RmA::Erase(0)) is Some);
    assert(s2.content[1].contains(1nat) && !t.content[1].contains(1nat));
}

pub proof fn cx_ctl_store_dropped_l1()
    ensures ({
        let t = run::<RemovalM<CtlStoreDropped>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Erase(0), RmA::Redact(0)]);
        t is Some && !law_l1::<CtlStoreDropped>(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let s0 = removal_s0();
    let s1 = removal_step::<CtlStoreDropped>(s0, RmA::Write(0, 0))->0;
    assert(CtlStoreDropped::cfg().paths[0].contains(1nat) && !s0.content[0].contains(1nat));
    assert(removal_step::<CtlStoreDropped>(s0, RmA::Write(0, 0)) is Some);
    assert(s1.content[0].contains(1nat));
    let s2 = removal_step::<CtlStoreDropped>(s1, RmA::Erase(0))->0;
    assert(s1.content[0].contains(1nat));
    assert(removal_step::<CtlStoreDropped>(s1, RmA::Erase(0)) is Some);
    let s3 = removal_step::<CtlStoreDropped>(s2, RmA::Redact(0))->0;
    assert(removal_step::<CtlStoreDropped>(s2, RmA::Redact(0)) is Some);
    assert(s3.redacted[0] && s3.content[0].contains(1nat) && !CtlStoreDropped::cfg().receipt.contains(1nat));
    assert(run::<RemovalM<CtlStoreDropped>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Erase(0), RmA::Redact(0)]) == Some(s3));
}

pub proof fn cx_ctl_store_dropped_l3()
    ensures ({
        let t = run::<RemovalM<CtlStoreDropped>>(removal_s0(), seq![RmA::Write(0, 0)]);
        t is Some && !law_l3::<CtlStoreDropped>(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let s0 = removal_s0();
    let s1 = removal_step::<CtlStoreDropped>(s0, RmA::Write(0, 0))->0;
    assert(CtlStoreDropped::cfg().paths[0].contains(1nat) && !s0.content[0].contains(1nat));
    assert(removal_step::<CtlStoreDropped>(s0, RmA::Write(0, 0)) is Some);
    assert(s1.content[0].contains(1nat));
    assert(s1.content[0].contains(1nat) && !reached_by_removal::<CtlStoreDropped>(1nat));
    assert(run::<RemovalM<CtlStoreDropped>>(removal_s0(), seq![RmA::Write(0, 0)]) == Some(s1));
}

pub proof fn cx_ctl_cross_target_l2()
    ensures ({
        let s = run::<RemovalM<CtlCrossTarget>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Write(1, 1)]);
        let a = RmA::Erase(0);
        s is Some && removal_step::<CtlCrossTarget>(s->0, a) is Some && !law_l2(s->0, a, removal_step::<CtlCrossTarget>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 3);
    let s0 = removal_s0();
    let s1 = removal_step::<CtlCrossTarget>(s0, RmA::Write(0, 0))->0;
    assert(CtlCrossTarget::cfg().paths[0].contains(0nat) && !s0.content[0].contains(0nat));
    assert(removal_step::<CtlCrossTarget>(s0, RmA::Write(0, 0)) is Some);
    assert(s1.content[0].contains(0nat));
    let s2 = removal_step::<CtlCrossTarget>(s1, RmA::Write(1, 1))->0;
    assert(CtlCrossTarget::cfg().paths[1].contains(2nat) && !s1.content[1].contains(2nat));
    assert(removal_step::<CtlCrossTarget>(s1, RmA::Write(1, 1)) is Some);
    assert(s2.content[1].contains(2nat));
    assert(run::<RemovalM<CtlCrossTarget>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Write(1, 1)]) == Some(s2));
    assert(s2.content[0].contains(0nat));
    let t = removal_step::<CtlCrossTarget>(s2, RmA::Erase(0))->0;
    assert(removal_step::<CtlCrossTarget>(s2, RmA::Erase(0)) is Some);
    assert(s2.content[1].contains(2nat) && !t.content[1].contains(2nat));
}

} // verus!
