# W36: the BulkLoader in a namespace whose IVG Schema is not Graph_KG (bug-plt-012) — predictions frozen before observation

Frozen 2026-11-16, iteration 31. Before image: seal 30 `1b4e3683`. Product `3eaa79cf`. Fixture `ivg-retest-20261116-iris`,
new namespace `W37` (database `W37DB`), set up with `initialize_schema()` on an engine made with `schema_prefix="Kg2"`.

Why this workflow: a consequential, tractable gap left open in iteration 25: bug-plt-012 is an "inconclusive regression
gap", and the owner's statement and its metadata disagree. Exposure: `bulk_loader.py` was read in iteration 25
(`SCHEMA = "Graph_KG"` default; `rebuild_all_indices` names `Graph.KG.*` classes). Verus (`bulk_load`) does not model
the schema.

| Case | History in W37 | Reader | Owner statement (`install.bulk_load.loader`: "It writes and rebuilds in the namespace's recorded IVG Schema, like every other IVG writer.") | Owner metadata / source |
|---|---|---|---|---|
| S1 | `BulkLoader(conn).load_nodes(rows, use_noindex=False)` (no schema given) | the call; Kg2 engine `get_node` | written into Kg2 and readable | the default `Graph_KG` names a table W37 does not have: the call fails (SQL table not found) and nothing is written |
| S2 | `BulkLoader(conn, schema="Kg2").load_nodes(rows, use_noindex=False)` | Kg2 engine `get_node` | readable | readable |
| S3 | `BulkLoader(conn, schema="Kg2").load_nodes(rows)` (default `%NOINDEX`), then `rebuild_all_indices()` | the rebuild's answer; `get_node` | rebuilt and readable | the rebuild names `Graph.KG.*` classes: it reports failure for each, and the rows stay unreadable |
| S4 | neighbor in `USER` (`Graph_KG`) | as S3 | readable | readable (iteration 25 A3) |

## Outcome ([observation](schema-observed-20261116T221059Z.json); `bulk_load` binding, three W37 histories)

S1 held for the metadata/source: "Table 'GRAPH_KG.NODES' not found", nothing written. S2 held. S3 held for the
metadata/source: the rebuild answers `false` for all four `Graph.KG.*` classes and the node stays unreadable. S4 held.
The owner statement's intended rule ("writes and rebuilds in the namespace's recorded IVG Schema") is the expectation the
product misses: bug-plt-012 E2E reproduced (repair of a known suspicion). The statement now carries a "Today" bullet.
