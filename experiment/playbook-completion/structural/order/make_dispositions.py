#!/usr/bin/env python3
"""Writes dispositions.json: one hand disposition per storage-order scan site that the statement text alone does not
decide, for the modules this lane gates (01 03 06 09 11 12 13 14 16 17 18) and the sites of other modules the
extended rules newly found. Each entry: class, module, reason, cite (path:lines at the pin), anchor (text that must
occur at or within 3 lines of the site, so a moved line fails the gate). Read at pin 3eaa79cf."""
import json
from pathlib import Path

D = {}


def d(file, line, rule, cls, module, reason, cite, anchor):
    D[f"{file}:{line}:{rule}"] = {"class": cls, "module": module, "reason": reason, "cite": cite, "anchor": anchor}


ES = "iris_vector_graph/_engine/schema.py"
SC = "iris_vector_graph/schema.py"
VE = "iris_vector_graph/_engine/vector.py"
EM = "iris_vector_graph/_engine/embeddings.py"
EN = "iris_vector_graph/engine.py"
Q = "iris_vector_graph/_engine/query.py"
LA = "iris_src/src/Graph/KG/LedgerApply.cls"
VIS = "get_schema_visualization documents a sample: 'Sampled, not exact: a label's properties are the first 20 keys " \
      "of one node carrying it, and a predicate's start and end labels are those of one edge's endpoints' (_engine/schema.py:2775-2777); which row is sampled is outside the contract. Its graph-blind joins are F-0106."

# ---------------------------------------------------------------- 01 install-schema
d(ES, 700, "first-row", "order-irrelevant", "01", "SELECT $USERNAME has no FROM: one row by construction", [f"{ES}:699-701"], "SELECT $USERNAME")
d(ES, 2084, "first-row", "unique-key", "06", "quarantine row by q_rowid, the table's IDENTITY primary key (_engine/schema.py:212-213); quarantine is module 06's (06 Scope)", [f"{ES}:2079-2084", f"{ES}:212-213"], "fetchone")
for ln, rule in ((2791, "prefix-literal"), (2794, "first-row"), (2825, "prefix-literal"), (2827, "first-row"),
                 (2833, "prefix-literal"), (2835, "first-row"), (2839, "prefix-literal"), (2841, "first-row")):
    d(ES, ln, rule, "documented-sample", "01", VIS, [f"{ES}:2772-2779", f"{ES}:{ln - 2}-{ln + 1}"], "TOP 1" if rule == "prefix-literal" else "fetchone")
d(SC, 883, "first-row", "order-irrelevant", "01", "SELECT Graph_KG.backfill_temporal_rows(): a function call with no FROM, one row", [f"{SC}:882-884"], "backfill_temporal_rows")
d(SC, 933, "prefix-literal", "set-valued", "01", "batch drain: UPDATE ... WHERE %ID IN (SELECT TOP n %ID ... WHERE val_key IS NULL AND val IS NOT NULL) repeats until a batch is short, so every qualifying row is updated whatever order batches take (schema.py:928-941); breadth-a 01.json", [f"{SC}:928-941"], "SELECT TOP")
d(SC, 1073, "first-row", "unique-key", "01", "INFORMATION_SCHEMA.COLUMNS by (TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME): one catalog row per column", [f"{SC}:1068-1073"], "fetchone")
d(SC, 1131, "first-row", "unique-key", "01", "INFORMATION_SCHEMA.COLUMNS by (TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME): one catalog row per column", [f"{SC}:1126-1131"], "fetchone")
d(SC, 1353, "first-row", "unique-key", "01", "INFORMATION_SCHEMA.COLUMNS by (TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME='graph_id'): one catalog row", [f"{SC}:1349-1353"], "fetchone")
d(SC, 1862, "first-row", "unique-key", "01", "%Dictionary.PropertyDefinition by (parent, Name): the definition's ID is parent||Name", [f"{SC}:1858-1862"], "fetchone")
d(SC, 1908, "prefix-literal", "existence-only", "01", "status[table] = True when the SELECT runs; the row is not read (schema.py:1905-1911)", [f"{SC}:1905-1911"], "SELECT TOP 1")
d(SC, 2053, "first-row", "unique-key", "01", "%Dictionary.CompiledClass by (SqlSchemaName, SqlTableName): one class projects one SQL table name in a namespace", [f"{SC}:2049-2053"], "fetchone")
d(SC, 2123, "first-row", "unique-key", "01", "INFORMATION_SCHEMA.COLUMNS by (TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME='emb') per candidate table; the loop stops at the first table that has the column (deterministic candidate order, schema.py:2100-2126)", [f"{SC}:2100-2126"], "fetchone")

# ---------------------------------------------------------------- 03 writes
d("iris_vector_graph/_engine/nodes_edges.py", 828, "prefix-split", "finding:F-C0302", "03", "get_node_ids_by_property: TOP n built in a separate f-string (:820) with no ORDER BY: with a limit the caller gets the first n subjects in scan order; confirmed live st-live-so-03", ["iris_vector_graph/_engine/nodes_edges.py:801-832"], "cursor.execute(sql, params)")
d("iris_vector_graph/_engine/nodes_edges.py", 911, "prefix-split", "finding:F-C0302", "03", "get_property_pairs_like: as :828 (TOP built at :904)", ["iris_vector_graph/_engine/nodes_edges.py:892-915"], "cursor.execute(sql, [key, like])")
d("iris_vector_graph/_engine/nodes_edges.py", 605, "first-row", "finding:F-0206", "03", "_filter_edges_by_properties reads the qualifiers of the first rdf_edges row of (s, p, o_id) in any graph (no graph_id, no ekey): with the triple in two graphs, or parallel edges in a multigraph, the filter tests whichever row comes first in storage order. F-0206's remedy names this function ('give _filter_edges_by_properties ... a graph'); confirmed live st-live-so-03", ["iris_vector_graph/_engine/nodes_edges.py:584-618"], "row = cursor.fetchone()")
for ln, what in ((77, "SELECT $TLEVEL"), (134, "SELECT <schema>.Txn_<name>(?)"), (142, "SELECT $TLEVEL")):
    d("iris_vector_graph/_write_txn.py", ln, "first-row", "order-irrelevant", "03", f"{what}: no FROM, one row by construction", [f"iris_vector_graph/_write_txn.py:{ln - 3}-{ln}"], "fetchone")

# ---------------------------------------------------------------- 06 vectors
d(EM, 163, "first-row", "order-irrelevant", "06", "SELECT EMBEDDING(?, ?): no FROM, one row", [f"{EM}:161-163"], "fetchone")
d(EM, 1734, "first-row", "unique-key", "06", "route row by (node_id, graph_id): uq_emb_graph_node UNIQUE (graph_id, node_id) on every route (schema.py:430-436, _engine/schema.py routed_table_ddl)", [f"{EM}:1729-1734", f"{SC}:430-436"], "fetchone")
d(EM, 1888, "first-row", "unique-key", "06", "%Embedding.Config by Name, the configuration's key", [f"{EM}:1887-1888"], "fetchone")
d("iris_src/src/Graph/KG/EmbedQueue.cls", 250, "os-first-row", "unique-key", "06", "registry by (table_name, graph_id) (pk_embedding_registry, _engine/schema.py:143-158); COALESCE folds NULL and '' graph ids, which only an upgraded install can hold both of", ["iris_src/src/Graph/KG/EmbedQueue.cls:243-254", f"{ES}:143-158"], "%Next()")
d(ES, 1049, "first-row", "unique-key", "06", "registry row by (table_name, graph_id), its primary key pk_embedding_registry (_engine/schema.py:158)", [f"{ES}:1044-1049", f"{ES}:158"], "fetchone")
for ln, rule in ((60, "prefix-literal"), (62, "first-row"), (71, "prefix-split"), (72, "prefix-literal"), (75, "first-row")):
    d(VE, ln, rule, "existence-only", "06", "one stored vector to probe the column's element type, declared per table, so any row answers the same; the LIMIT 1 cast probe only tests that the statement runs (vector.py:56-84; breadth-a 06.json)", [f"{VE}:56-84"], "TOP 1" if ln < 70 else "LIMIT 1" if rule != "first-row" else "fetchone")
for ln, rule in ((435, "prefix-literal"), (437, "first-row")):
    d(VE, ln, rule, "existence-only", "06", "one stored vector's width for an error message; a route's emb column declares one width (vector.py:425-446)", [f"{VE}:425-446"], "TOP 1" if rule == "prefix-literal" else "fetchone")
d(VE, 562, "first-row", "unique-key", "06", "the query node's own vector by (node_id, graph) on its route: uq_emb_graph_node", [f"{VE}:557-562", f"{SC}:430-436"], "fetchone")
for ln, rule in ((1146, "prefix-literal"), (1147, "first-row")):
    d(VE, ln, rule, "existence-only", "06", "validate_vector_table: documented as 'the length of one sampled vector' and a VECTOR column declares one width (breadth-a 06.json)", [f"{VE}:1130-1150"], "TOP 1" if rule == "prefix-literal" else "fetchone")
d(VE, 1521, "py-slice-cut", "documented-sample", "06", "kg_VECTOR_GRAPH_SEARCH keeps k of list(set(...)) - Python set order (hash order of str, randomized per process), not storage order; the docstring documents 'keeps k of that set in no particular order' (vector.py:1463-1468). The reviewed contract HD-0603 (best k, defined ties) is an assumption, intent-undecided (intent/HD-0603.md:37-41)", [f"{VE}:1463-1468", f"{VE}:1515-1521"], "all_entities[:k]")
d("iris_vector_graph/migrations/graph_scoped_embeddings.py", 1273, "prefix-literal", "finding:F-C0604", "06", "_measured_width sizes the route from one stored vector with no ORDER BY when neither the table nor the registry declares a width (breadth-a 06.json)", ["iris_vector_graph/migrations/graph_scoped_embeddings.py:1265-1280"], "SELECT TOP 1 emb")
d("iris_vector_graph/vector_utils.py", 352, "prefix-literal", "order-irrelevant", "06", "benchmark: any 100 rows serve the timing; the result holds only timings and min(len, k) (vector_utils.py:345-370)", ["iris_vector_graph/vector_utils.py:345-370"], "SELECT TOP 100")
for ln, rule in ((455, "prefix-literal"), (456, "first-row")):
    d("iris_vector_graph/vector_utils.py", ln, rule, "existence-only", "06", "one row's vector for 'vector_dimension'; the column declares one width", ["iris_vector_graph/vector_utils.py:450-460"], "TOP 1" if rule == "prefix-literal" else "fetchone")
for ln, rule in ((308, "os-first-row"), (308, "prefix-literal")):
    d("iris_src/src/Graph/KG/GraphStores.cls", ln, rule, "finding:F-C0603", "06", "VectorRouteGuard selects TOP 1 table_name over registry rows keyed (table_name, graph_id): two node routes for one graph with no model key answer in scan order, where Python applies _route_preference (breadth-a 06.json; the guard serves kg_KNN_VEC, module 06's route rule, though the class is in 12's inventory)", ["iris_src/src/Graph/KG/GraphStores.cls:300-312"], "SELECT TOP 1 table_name")

# ---------------------------------------------------------------- 09 native executor
for ln in (867, 900):
    d("iris_src/src/Graph/KG/Cypher/Exec.cls", ln, "os-cursor-alloc", "set-valued", "09", "Anchors numbers anchor candidates in cursor order (^||IVG.CypherRun('cand', $Increment(tN))); the numbering only enumerates the candidate set: an unordered Cypher answer's row order is unspecified (openCypher), and ordered/limited plans sort before cutting (NAT-T8.4; F-0907 shows the shadow comparison, not the executor, holds row order)", ["iris_src/src/Graph/KG/Cypher/Exec.cls:847-901"], "$Increment(tN)")
d("iris_src/src/Graph/KG/Cypher/Exec.cls", 1101, "prefix-literal", "order-irrelevant", "09", "NamedEnds: TOP 1001 is a count probe; with more than 1000 rows the method answers 0 and the general walk runs (:1117), with at most 1000 every row is read, so which 1001 rows come first never changes the answer", ["iris_src/src/Graph/KG/Cypher/Exec.cls:1095-1122"], "SELECT TOP 1001")
d("iris_src/src/Graph/KG/Cypher/Exec.cls", 1117, "os-cutoff", "order-irrelevant", "09", "as Exec.cls:1101: the cut-off falls back to the general walk", ["iris_src/src/Graph/KG/Cypher/Exec.cls:1110-1118"], "Quit:tN>1000")

# ---------------------------------------------------------------- 11 ledger
d(LA, 153, "os-first-row", "finding:F-0205", "11", "FindEdge takes the first rdf_edges row of (s, p, o_id, graph) without ekey: in a multigraph the ledger's delete/qualifier ops act on whichever parallel edge comes first in storage order (F-0205 cites LedgerApply.cls:144-157); confirmed live st-live-so-11", [f"{LA}:144-157"], "%Next()")
d(LA, 258, "os-first-row", "existence-only", "11", "AddLabel: SELECT 1 ... If tRS.%Next(): existence of the label row", [f"{LA}:253-262"], "%Next()")
d(LA, 302, "os-first-row", "existence-only", "11", "OpRemoveLabel: SELECT 1 ... existence of the label row", [f"{LA}:295-307"], "%Next()")
d(LA, 272, "os-first-row", "unique-key", "11", "SetProp reads val by (s, key) in the default graph: pk_props PRIMARY KEY (graph_id, s, key) (schema.py:417); DEFAULTGRAPH folds NULL and '' graph ids (LedgerApply.cls:15), which only an upgraded install holds both of", [f"{LA}:265-283", f"{SC}:417", f"{LA}:15"], "%Next()")
d(LA, 328, "os-first-row", "unique-key", "11", "OpRemoveProp: as SetProp (pk_props)", [f"{LA}:321-335", f"{SC}:417"], "%Next()")
d(LA, 388, "os-cursor-alloc", "finding:F-C1108", "11", "OpDeleteNode detach allocates statement ids to unrecorded incident edges in the order of an unordered cursor (:385-397); reproduced live by corr-row-permutation (F-C1108, intent-undecided)", [f"{LA}:384-400"], "While tRS.%Next()")
d("iris_vector_graph/ledger/client.py", 557, "first-row", "unique-key", "11", "ledger_stats has IdKey LedgerName and only the 'default' row is written (LedgerStats.cls:48, 56)", ["iris_vector_graph/ledger/client.py:550-558", "iris_src/src/Graph/KG/LedgerStats.cls:48", "iris_src/src/Graph/KG/LedgerStats.cls:56"], "fetchone")

# ---------------------------------------------------------------- 13 redaction
d("iris_src/src/Graph/KG/LedgerRedact.cls", 309, "os-cutoff", "collation-ordered", "13", "BatchInLock walks ^IVG.Ledger('rec', seq, ordinal) in subscript (key) order and stops a batch at pBatch matches or pCap scanned; the next batch resumes from the saved (pSeq, pOrd) key (LedgerRedact.cls:303-320), so the batches partition the record keys whatever the content tables' row order. A restart from the first record after a stop is F-C1303 (progress), not storage order", ["iris_src/src/Graph/KG/LedgerRedact.cls:303-320"], "tMatched >= pBatch")

# ---------------------------------------------------------------- 16 interfaces
for ln in (207, 232, 248, 266):
    d("api/gql/core/resolvers.py", ln, "prefix-literal", "false-positive", "16", "the {order_clause} placeholder is always an ORDER BY: n.created_at by default, n.node_id or a property value (api/gql/core/resolvers.py:159-177); ties at the page cut (equal created_at) follow storage order, the same tie class as the top-k searches", ["api/gql/core/resolvers.py:159-177"], "query = \"\"\"")
d("api/gql/resolvers/query.py", 93, "first-row", "order-irrelevant", "16", "unreachable: the sample app's schema imports only api.gql.core.resolvers (api/gql/schema.py:16); this older resolver module is not imported anywhere at the pin", ["api/gql/schema.py:16", "api/gql/resolvers/query.py:76-94"], "fetchone")
d("api/main.py", 47, "first-row", "order-irrelevant", "16", "SELECT 1: no FROM, one row", ["api/main.py:44-48"], "fetchone")
d("iris_vector_graph/gql/engine.py", 40, "prefix-literal", "documented-sample", "16", "get_sampled_properties is documented as sampling ('Samples nodes of a given label', 'Using TOP clause for sampling as per SC-002/SC-003 and FR-002'): the discovered key set may depend on which sample_limit nodes come first only when a label has more than sample_limit (1000) nodes; its graph-blind join is F-1603", ["iris_vector_graph/gql/engine.py:32-50"], "sql = f\"\"\"")
d("iris_vector_graph/gql/resolvers.py", 40, "py-slice-cut", "finding:F-C1642", "16", "resolve_nodes pages all_ids[offset:offset+limit] of an unordered SELECT s FROM rdf_labels: page membership follows storage order; F-1603 is the cross-graph part (the page cut from every graph's ids); confirmed live st-live-so-16", ["iris_vector_graph/gql/resolvers.py:32-46"], "all_ids[offset : offset + limit]")

# ---------------------------------------------------------------- 17 operations
d("iris_vector_graph/_engine/admin.py", 104, "prefix-literal", "documented-sample", "17", "active_queries_sql: TOP n of CURRENT_STATEMENTS, a bounded diagnostic list (docstring admin.py:95-101; OPS-B3.4 'up to a limit'); no order is promised", ["iris_vector_graph/_engine/admin.py:95-107"], "SELECT TOP")
d("iris_vector_graph/stores/iris_sql_store.py", 1180, "prefix-split", "finding:F-C1742", "17", "query_nodes(limit=n) without a label: SELECT node_id FROM nodes FETCH FIRST n ROWS ONLY with no ORDER BY: the caller gets the first n node rows in storage order (store_protocol.py:10-11 promises no order); confirmed live st-live-so-17", ["iris_vector_graph/stores/iris_sql_store.py:1162-1182", "iris_vector_graph/store_protocol.py:10-11"], "cursor.execute")
d("iris_vector_graph/stores/iris_sql_store.py", 1192, "first-row", "finding:F-1701", "17", "query_nodes' property filter reads val by (s, key) with no graph: with the id in two graphs it tests whichever graph's row comes first; F-1701's remedy names query_nodes ('give get_nodes/get_node_labels/query_nodes a graph argument')", ["iris_vector_graph/stores/iris_sql_store.py:1184-1200"], "fetchone")

# ---------------------------------------------------------------- 18 snapshot
d("iris_vector_graph/_engine/snapshot.py", 1421, "first-row", "unique-key", "18", "only routed tables reach this read (is_routed_embedding_table, snapshot.py:1400-1404) and a route's name is derived from its graph and model (routing.py:32-78), so table_name selects one registry row (pk_embedding_registry (table_name, graph_id))", ["iris_vector_graph/_engine/snapshot.py:1398-1426", "iris_vector_graph/routing.py:32-78"], "fetchone")

# ---------------------------------------------------------------- sites of closed modules newly found by the extended rules
d(Q, 3120, "first-row", "unique-key", "08", "_vlp_qualifiers by (s, p, o_id, graph): unique outside a multigraph (u_spo_graph_ekey with ekey 0); a multigraph walk passes edge_id and reads the row by edge_id (query.py:3091-3104, 4.6.0 R294)", [f"{Q}:3091-3120", f"{SC}:44"], "fetchone")
for ln, rule in ((624, "prefix-literal"), (625, "first-row"), (634, "prefix-literal")):
    d(EN, ln, rule, "existence-only", "02", "_more_than_one_graph: any first row, then whether a graph above or below it exists (engine.py:615-638; breadth-a 02.json)", [f"{EN}:615-638"], "TOP 1 graph_id" if rule == "prefix-literal" else "fetchone")
d(EN, 852, "first-row", "order-irrelevant", "08", "SELECT $ZVERSION: no FROM, one row", [f"{EN}:850-853"], "fetchone")
for ln, rule in ((1340, "prefix-literal"), (1343, "first-row"), (1382, "prefix-literal"), (1385, "first-row")):
    d(EN, ln, rule, "finding:F-C0802", "08", "db.schema.nodeTypeProperties / relTypeProperties sample one node or edge per label/type in storage order (module 08's disposition, modules/08.json storage_order)", [f"{EN}:{ln - 3}-{ln + 3}"], "TOP 1" if rule == "prefix-literal" else "fetchone")
for ln in (1835, 1837):
    d(Q, ln, "prefix-literal", "finding:F-C0802", "08", "the text shortcuts answer the first 25 ids / types in storage order (modules/08.json storage_order)", [f"{Q}:1830-1840"], "TOP 25")

out = {"pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e", "dispositions": D}
Path(__file__).with_name("dispositions.json").write_text(json.dumps(out, indent=1, sort_keys=True))
print(len(D), "dispositions")
