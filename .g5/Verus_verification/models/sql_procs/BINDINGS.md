# sql procs

Graph SQL procedures: the MatchEdges and MatchEdgesAllGraphs scans (source, predicate, shard and graph arguments) and the Cypher hop on the IVG_EDGESCAN plan, the DijkstraPath SQL entry in front of DijkstraJson, backfill_temporal_rows and rebuild_edge_indices, each behind its privilege check

Evidence status: active. Variant: as-built bounded transcription.

Verified and errors count obligations reported by the verifier. A control is judged against its named expected failure. Native observations have their recorded scope.

[Formal source](sql_procs.rs)

[Formal claims, product bindings and limitations](NOTES.md)

[Premises](NOTES.md)

[Product and declaration crosswalk](../../crosswalk/decision-links.tsv)
