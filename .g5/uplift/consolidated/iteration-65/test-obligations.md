# Iteration 65: test-derived obligations for ERASURE

Repository: `iris-vector-graph` at branch `consolidated_uplift` (HEAD 763e09b9). This file was produced by reading only. No repository file was changed and no test was run.

Paths are relative to the repository root. `file:line` points at the test's `def` line, or at the assertion when that is more precise.

Abbreviations:
- **SRC**: the test reads source text (a grep or regex over `.cls` or `.py`), not behaviour.
- **MOCK-SQL**: the test inspects SQL strings sent to a fake cursor.
- **MOCK-CALL**: the test inspects the arguments of a faked `classMethodValue` or `_call_classmethod` call, or of a fake store.
- **SKIP**: `pytest.mark.skipif(SKIP_IRIS_TESTS=="true")`.
- **MC**: the `iris_master_cleanup` fixture (`EraseAll` before and after each test).

---

## 0. Environment, fixtures and conditions every live test inherits

| Item | What it does | Consequence for erasure obligations |
|---|---|---|
| `iris_test_container` (tests/conftest.py:540-611) | Attaches to `IVG_TEST_CONTAINER`, default `ivg-iris-enterprise` (tests/conftest.py:23). A **missing** container is `pytest.fail`, unless `SKIP_IRIS_TESTS=true` (then skip) or `IVG_AUTO_START_CONTAINER=1`, which starts a **Community** container (:577-583). A stopped container always fails (:589-598). | The default target is Enterprise. Community is only used through the auto-start path. |
| `iris_connection` (tests/conftest.py:615-) plus the **patched `createIRIS`** (tests/conftest.py:715-775) | `iris.createIRIS(session_conn)` is monkeypatched to return a `ReconnectingNative` on a **separate dedicated native connection**, opened lazily. The comment at :725-730 says: "Community Edition has a 5-connection limit"; see also :938. | **In every test that uses the session `iris_connection`, the Eraser runs on a different IRIS process from the engine's DB-API cursor.** In production, `_iris_obj()` is `createIRIS` on the same connection (iris_vector_graph/stores/iris_sql_store.py:1456-1458), so the Eraser nests under the caller's `$TLevel`. Session-fixture tests therefore cannot observe caller-transaction nesting. Only tests that open their own connections can (test_464, the 236 scratch tests). |
| MC (tests/conftest.py:1084-1146) | Runs `DELETE Graph_KG.docs`, then `Graph.KG.Eraser.EraseAll` before **and** after each test. A failure is raised, not suppressed. It skips only if `iris_connection.cursor()` raises (:1097-1101). | `EraseAll` runs implicitly hundreds of times per run, but only tests/integration/test_master_cleanup.py asserts its outcome. |
| `ledger_reset` (:1278-1324) | MC, plus `DELETE` of the ledger tables and `Graph.KG.Ledger.PurgeAll` (or `kill ^IVG.Ledger`) on a temporary connection. | Ledger tests start from an empty ledger. |
| `node_graph_reset` (:1327-) | Deletes named-graph rows with SQL. | Used by test_214_*. |
| `ivg_236_scratch` (:1449-1492), `Scratch236` (:1378-1432) | Skips unless `IVG_NS_IVG236` names a non-USER, non-`%` namespace (:1457-1461), and skips unless the container is running (:1462-1464). It creates the namespace with `scripts/tck/setup_namespace.sh --create` if needed, deploys classes, runs `initialize_schema` and sets a sentinel. **`Scratch236.native()` opens a NEW `iris.connect` on every call and keeps it in `_conns` until session end** (:1384-1395, :1428-1432). | Used by test_eraser_failures, test_edgescan_ledger_erase, test_236_token_write_paths and test_236_algo_cache. **Skipped by default, because there is no default namespace.** It accumulates connections (see §1). |
| Other scratch-namespace gates (from subagent reads) | `IVG_NAMESPACE` prefixed `IVG460FX`/`IVG460FY` (r268, r274, r286, r65 all_graphs_writes, sec_audit); `IVG_R464_TXN_NS` (test_464); `IVG_R463_PRIV_NS`; `IVG_R465_ROLE_NS`; `IVG_FHIRLESS_NAMESPACE`; `IVG_PAROS_NAMESPACE` (degree_cache_live); `IVG_NS_IVGFHIR` (231 FHIR); `IVG_NS_IVG262ALT`; `IVG_R470_WR_NS`; `alt.requires_namespace` / `rr.requires_namespace` / `ns463.requires_namespace`. | Each of these is **skipped unless its variable is set**. Many of the most specific erasure obligations (routes injection, caller transaction, privilege refusals, ^NKG algorithm routes, FHIR) live behind these gates. |
| `perf` marker | `pyproject.toml:266` runs with `-m "not perf"`. | tests/integration/test_256_ledger_redaction_perf.py is deselected by default. |
| Community licence notes | tests/conftest.py:220 (a 2-core limit breaks parallel compile), :725 and :938 (5-connection limit); docs/dev/TCK.md:24 ("Community limits connections"); docs/dev/notes/known-issues-history.md:464 ("Unable to allocate a license", Community). | See §1 for test_eraser_failures. |

---

## 1. tests/integration/test_eraser_failures.py in detail

Module docstring: "when one store refuses a delete, nothing at all is erased" (:1-6). Kind: integration, live IRIS, scratch namespace **IVG236 only**.

**Gating.** The `world` fixture (:32-45) depends on `ivg_236_scratch`. The whole file therefore **skips unless `IVG_NS_IVG236` is set** and `IVG_TEST_CONTAINER` (default `ivg-iris-enterprise`) is running. There is no `SKIP_IRIS_TESTS` marker of its own. The fixture runs `Eraser.EraseAll` before each test (:35) and after it, guarded by the sentinel (:43-45). Teardown best-effort drops every `ivg_block_<table>` trigger (:38-42).

**Seed** (`seed`, :48-60). Nodes `n1` and `n2` are created in graph `gx`, plus edge `n1-R->n2`, through the engine. This populates `nodes` and `rdf_edges`, `^KG` out/in, the degree cache and the ledger tuple if the ledger is on. The seed then raw-INSERTs one row for `gx` into each of: `rdf_labels`, `rdf_props`, `docs` (id `n1`), `kg_NodeEmbeddings` and `kg_NodeEmbeddings_optimized` (graph_id and node_id only, with a NULL vector), `kg_EdgeEmbeddings` (n1, R, n2), and `rdf_reifications` (`'r1'`, edge_id). Each insert is committed.

Not populated: temporal data, routed `kg_emb_*`/`kg_eemb_*` tables, registry rows, FHIR side tables, ledger statements, ^NKG, the multigraph mode, or a caller transaction.

**Fault injection** (`block`, :69-75). This is SQL DDL:

```
CREATE TRIGGER Graph_KG.ivg_block_<table> BEFORE DELETE ON Graph_KG.<table>
LANGUAGE OBJECTSCRIPT { Set %ok=0 Set %msg="blocked" }
```

- It is committed, then removed by `DROP TRIGGER` (`unblock`, :78-80).
- There are **no** GRANT/REVOKE statements, no user or role creation, no `%SYS.Security` API, no table lock, no `%NOCHECK`/`%NOINDEX`, and no Python mock or monkeypatch.
- Eraser.cls uses no `%NOTRIGGER`/`%NOCHECK` (checked with grep). So both the embedded `&sql(DELETE …)` statements and the `%ExecDirect` DELETEs fire the row trigger whenever a matching row exists.
- The DELETE then returns a negative SQLCODE for a failed BEFORE DELETE trigger. That is −134 in IRIS's numbering, but the test does not pin the code.
- The Eraser throws `SqlErr`, "erase failed on <table> with SQLCODE n; nothing was erased" (Eraser.cls:1356-1358). For statement DELETEs it does not pass `%msg` (e.g. :132), so the text "blocked" probably does not appear. The assertion at :99 accepts either string.
- The Native API surfaces this as `RuntimeError`.

**Tests**

| Test | What is called | Promise and reader |
|---|---|---|
| `test_a_refused_delete_erases_nothing` :90-101. Parametrized over 9 tables {rdf_labels, rdf_props, docs, kg_NodeEmbeddings, kg_NodeEmbeddings_optimized, kg_EdgeEmbeddings, rdf_reifications, rdf_edges, nodes} × 3 ops {graph=`EraseGraph(gx)`, nodes=`EraseNodes(gx,"n")`, ids=`EraseNodeIds(gx,["n1","n2"])`}, so 27 cases. | Native `classMethodValue` directly. The Python facade and `_eraser_txn` are bypassed. | The call raises `RuntimeError` whose text contains "erase failed on <table>" or "blocked". The handle is still in the scratch namespace (:98). After unblocking, `SELECT COUNT(*)` of **all 9 tables, unscoped**, equals the before-snapshot (:101). Reader: SQL counts only. **Not read: `^KG` out/in/gen/degc, `^KG` prop/label, temporal data, ledger, ^NKG, `^KG("__version")`, AlgoCache.** |
| `test_erase_all_stops_cleanly_when_one_store_refuses` :104-112 | `EraseAll` with `rdf_labels` blocked. | `RuntimeError`, and the 9 SQL counts are unchanged. Before `rdf_labels`, EraseAll has already deleted routes, the registry, FHIR rows and `rdf_reifications` (Eraser.cls:743-764), so the reification row being restored proves rollback of those deletes. Globals are not read. |
| `test_erase_edges_stops_cleanly_when_the_edge_table_refuses` :115-122 | `EraseEdges(gx,[{n1,R,n2}])` with `rdf_edges` blocked. | `RuntimeError`, and `rdf_edges` COUNT == 1. The reification and `kg_EdgeEmbeddings` rows, which `EraseEdgeRow` deletes **before** `rdf_edges` (Eraser.cls:647-652), are **not** re-counted. |
| `test_erase_edges_rejects_something_that_is_not_an_edge_list` :125-128 | `EraseEdges(gx,'{"s":"n1"}')` | `RuntimeError` containing "EraseEdges expects a JSON array" (matches Eraser.cls:402). No state assertion. |

**What the injection reaches and what it cannot**

- Position in the order matters. In `EraseGraph` the DELETE order is labels, props, docs, kg_NodeEmbeddings, `_optimized`, routes, FHIR, reifications, kg_EdgeEmbeddings, rdf_edges, nodes (Eraser.cls:130-224).
  - Blocking `rdf_labels` fails the **first** statement, which proves almost nothing about rollback.
  - Blocking `nodes` fails the last SQL statement. That proves the ten earlier deletes roll back, and also the per-row `^KG("out")` clearing done by the rdf_edges functional index, although that is not read.
- In `EraseIdSet` (the ids and nodes ops), `Adjacency.RemoveNode` runs **before** the node's `rdf_labels` delete (Eraser.cls:547-553). Blocking `rdf_labels` therefore does exercise a `^KG` rollback, but the test never reads `^KG`.
- No injection is possible in:
  - global kills after the last SQL statement (`Adjacency.RemoveGraph`, `TemporalIndex.EraseGraph`, the `^KG` prop/label/deg2p kills, `^IVG.GraphMode`, `InvalidateDerived`, `EraseLedgerFor`; Eraser.cls:234-256);
  - `CollectOrphanRoutes` (which runs before `TSTART` in EraseEdges and EraseIdSet);
  - the post-commit `DROP TABLE` and registry delete (Eraser.cls:282-299, 828-842);
  - routed-table DELETEs, since no route is seeded;
  - FHIR side tables (not seeded).

**Production reachability.** A customer-defined BEFORE DELETE trigger is unlikely. The trigger is a stand-in for "statement k of the erase fails". The production causes of that are covered elsewhere:
- privilege refusal −99 (tests/e2e/test_465_stale_error_text_e2e.py:82 through a reading role; tests/e2e/test_463_refused_reads_e2e.py:82);
- FK −124 from an orphan route (test_227_orphan_route_erase docstring :3-9);
- lock timeouts, `<PROTECT>`, and an over-long subscript `<THROW>` (tests/e2e/test_463_refused_reads_e2e.py:95).

**Community edition**

- **Injection features.** `CREATE TRIGGER … LANGUAGE OBJECTSCRIPT` is core IRIS SQL and is available on Community. The test needs only DDL privilege; the fixture connects as `_SYSTEM`/`SYS` (tests/conftest.py:1387, :1421-1424). No users, roles, GRANT/REVOKE or security APIs are used.
- **Fixture features.** The fixture can **create a database and namespace** through `scripts/tck/setup_namespace.sh --create` → `scripts/dev/tcp_setup.py make` (tests/conftest.py:1468-1474; scripts/tck/setup_namespace.sh:1-35). That needs %SYS-level rights, which `_SYSTEM` has, and is permitted on Community.
- **Connections (likely blocker, inferred from code, not run).**
  - `Scratch236.native()` and `.dbapi()` open a fresh connection on every call and keep it open until session teardown.
  - Per parametrized case: fixture `w.native()` 1, `engine()` → `scratch.native()` + `dbapi()` 2, the test's two `world.native()` calls 2, teardown `ivg_236_scratch.native()` 1. That is about 6 connections.
  - Over the file: 27×6 + 6 + 5 + 3 ≈ **176 connections held open at once**, on top of whatever the other IVG236 tests in the same session opened.
  - The repository's own notes say Community allows 5 connections (tests/conftest.py:725, :938; docs/dev/TCK.md:24). **On Community this file would very likely fail from connection or licence exhaustion.** In practice it needs the Enterprise container named by the default `IVG_TEST_CONTAINER`, and even there the licence-unit behaviour of about 180 same-user connections from one IP was not verified.
- **Default behaviour.** With `IVG_NS_IVG236` unset, the whole file **skips**.

---

## 2. The named core files (read directly)

### 2a. tests/integration/test_erase_graph.py

Integration, SKIP (:29-31), fixture `engine` = MC + `IRISGraphEngine(dim=4)` (:40-44). Seed (`_seed`, :69-83) per graph: a node `n_<g>` with label Person and prop k=v in g; `create_edge a-KNOWS->b` in g; `create_edge_temporal a-SAW->b` at TS in g. That gives 2 `rdf_edges` rows, `^KG` out/in, the degree cache, and tout/tin/bucket/tagg. Readers: `_kg` = `Graph.KG.Meta.GetKG` through the session-patched native connection (:47-52), and `_sql_count` with a COALESCE graph predicate (:55-61). No mocks.

| file::test | Cond. | Entry and setup | Promise and reader | Rule |
|---|---|---|---|---|
| `::test_erase_removes_the_sql_rows` :91 | SKIP, MC | `erase_graph(GRAPH)` after `_seed` | rdf_edges count for g goes 2 → 0 (SQL) | Graph erase removes the graph's edge rows. |
| `::test_erase_removes_the_structural_adjacency` :100 | same | same | `^KG("out",g,a,KNOWS,b)` and `^KG("in",g,b,KNOWS,a)` become "" (GetKG). The `^KG` subscript is the graph **name** passed to GetKG | Graph erase removes the graph's out/in adjacency. |
| `::test_erase_removes_the_degree_cache` :113 | same | same | `^KG("gen",g,a)` and `^KG("degc",g,a,\x01)` become ""; `Adj.Degree(ForIndex(g),a)` == 0 | Graph erase removes gen/degc. |
| `::test_erase_removes_the_temporal_index` :129 | same | same | tout, tin, bucket and tagg(count) for g become "". **edgeprop and tlast are not read** | Graph erase removes the graph's temporal subtrees. |
| `::test_erase_removes_the_nodes_and_their_labels_and_props` :148 | same | same | `rdf_labels` and `rdf_props` WHERE `s = node` (**unscoped by graph**) == 0; nodes for g == 0 | Graph erase removes the node, labels and props. The docstring (:149-155) is stale; see §5. |
| `::test_erasing_one_graph_leaves_another_untouched` :174 | same | `_seed` g and OTHER with identical coordinates; `erase_graph(g)` | OTHER keeps `^KG` out, gen, tout and bucket, and its rdf_edges count is 2. **OTHER's tin, tagg, edgeprop, tlast, labels, props, node row and degc are not read** | A graph erase leaves another graph with the same ids untouched (partially checked). |
| `::test_erasing_the_default_graph_reaches_both_of_its_spellings` :188 | **Conditional skip** at :206-213 if `graph_id` already rejects NULL (on a fresh schema it is `NOT NULL DEFAULT ''`) | `create_edge d1→d2` (''), raw INSERT of `d3→d4` with graph_id NULL; `erase_graph("")` | rdf_edges WHERE s IN (d1,d3) == 0 | The default graph's erase covers NULL and ''. On a fresh database this is **usually skipped**. |
| `::test_erasing_the_default_graph_leaves_named_graphs_alone` :223 | SKIP, MC | default edge + `_seed(g)`; `erase_graph("")` | g's `^KG` out survives and g's rdf_edges count is 2 | A default-graph erase (key 0) is not a wildcard. |
| `::test_erase_leaves_no_drift_for_the_oracle_to_find` :239 | same | `erase_graph(g)`; `verify_graph(g)` | `ok == 1`, outEdges 0, cacheEntries 0 | Erasure is checked by the independent oracle. |
| `::test_erasing_a_graph_with_no_content_returns_zero` :255 | same | `erase_graph("erase_never_existed")` | Return value == 0 | A count of 0 means nothing matched; it is not an error. |
| `::test_a_rejected_graph_name_raises_before_anything_is_deleted` :260 | same | default edge; `erase_graph("0")` | Some exception is raised (`pytest.raises(Exception)`, broad), and the default graph's `^KG("out",0,d1,…)` survives | An invalid name is refused with no deletion. The rejection comes from the Python `validate_graph_name` (iris_vector_graph/_validate.py:38-40) before the Eraser is reached; see §5. |
| `::test_drop_graph_is_the_eraser_now` :276 | same | `drop_graph(g)` | `^KG` out and tout for g become "" | `drop_graph` is an alias of the Eraser path. |
| `::test_erase_all_empties_every_graph` :295 | same | `_seed` g, OTHER, and a default edge; `erase_all()` | rdf_edges count 0 for all three; `^KG` out gone for all three | EraseAll empties every graph. |
| `::test_erase_all_empties_the_stores_that_cannot_be_erased_per_graph` :309 | same | `_seed(g)`; `erase_all()` | `rdf_labels`, `rdf_props` and `rdf_reifications` have total count 0. **No reification was seeded**, so that third count is vacuous | EraseAll empties labels, props and reifications. |
| `::test_erase_all_leaves_the_interning_index_unbuilt_rather_than_stale` :326 | same | `_seed`, `sync()` (builds ^NKG); `erase_all()` | `^NKG("$meta","nodeCount")` was present before and is None after | EraseAll leaves ^NKG absent, not stale. Consistent with `DropNKG` (GraphIndex.cls:22-27) via `InvalidateDerived(1,0)`. |

### 2b. tests/integration/test_227_orphan_route_erase.py

Integration, SKIP (:30-33), `iris_connection` only, with **no MC**. The `orphan_route` fixture (:59-76) creates `Graph_KG.kg_emb_0bad0c0de7e57c0d`, which has the route shape (`IsRouteName`, Eraser.cls:1058-1061). The table has an FK on (graph_id, node_id) to nodes and **no registry row**. This is the state a rollback after a durable CREATE TABLE leaves behind; it is reachable in production (Eraser.cls:100-113). Each test calls `initialize_schema(rewidth=True)` at dimension 8, which has a **side effect** on the session namespace (USER by default).

| Test | Setup | Promise and reader | Rule |
|---|---|---|---|
| `::test_erase_graph_succeeds_with_an_orphan_routed_table` :79 | Raw INSERT of a node in `orphan-route-graph` plus a vector row in the orphan table | `erase_graph` does not raise. Orphan rows for the graph == 0; nodes for the graph == 0 (SQL) | An unclaimed route is **emptied** of the graph's rows, so its FK cannot block the nodes delete (−124). |
| `::test_an_unregistered_route_is_emptied_but_not_dropped` :107 | Node only | The orphan table still exists (INFORMATION_SCHEMA count == 1) | Only registry-claimed routes are dropped (FR-011). |

Not covered here: an orphan holding **another** graph's rows (are they kept?), an orphan `kg_eemb_*`, the orphan path for `EraseNodeIds`/`EraseEdges`/`EraseAll`, and an orphan with a non-hex name.

### 2c. tests/integration/test_edgescan_ledger_erase.py

Integration, `ivg_236_scratch` (**skips unless `IVG_NS_IVG236`**). The fixture runs EraseAll before and after (:21-29). Only the last test concerns erasure. The rest test EdgeScan match and ingest, so they are out of scope.

| Test | Setup | Promise and reader | Rule |
|---|---|---|---|
| `::test_erasing_a_graph_removes_its_ledger_statements_and_leaves_other_graphs` :113 | `ledger.enable()`; Changeset `l1-R->l2` in `gl` and `l3-R->l4` in the default graph, `auto_stub_missing_nodes`; commit | Before: a `^IVG.Ledger("tuple",l1,R,l2,<gl or ForLedger(gl)>)` exists. After `erase_graph("gl")`: that tuple is undefined under both spellings; the default graph's tuple (`ForLedger("")`) is still defined. Reader: native `isDefined`. **`^IVG.Ledger("stmt")` is not read, `("rec")` is not read, and `verify()` is not called** | Graph erase removes that graph's live ledger tuples and keeps other graphs' tuples. |

### 2d. tests/unit/test_eraser_inventory_coverage.py

Unit, SRC: it reads `GraphStores.cls` and `Eraser.cls` as text and needs no container (:1-13).

| Test | Promise | Rule and caveat |
|---|---|---|
| `::test_the_inventory_parses` :38 | At least 17 `..Entry(` entries; includes rdf_edges, `^KG("out")` and `^IVG.Ledger("tuple")` | Guard for the regex. |
| `::test_every_graph_scoped_store_is_named_in_the_eraser` :56 (parametrized over scoped entries) | Each scoped store's name appears **somewhere** in Eraser.cls text, comments included. Adjacency stores must appear in Adjacency.cls and the Eraser must call `Adjacency).RemoveGraph(`. Temporal stores must appear in TemporalIndex.cls and the Eraser must call `TemporalIndex).EraseGraph(` | "Every graph-scoped store is reached by graph erase", checked by **substring only**. Example: `^IVG.TemporalStructural` is inventory scoped=1 (GraphStores.cls:110) but deliberately **not** killed by EraseGraph (Eraser.cls:245-247). The test passes because the name appears in a comment and in EraseAll. Likewise `Graph_KG.embedding_registry` (scoped, GraphStores.cls:54) is deleted by EraseGraph only for claimed route rows (Eraser.cls:292-293), not for a legacy-table identity row of that graph. |
| `::test_every_unscoped_store_is_named_in_the_eraser` :85 | Each unscoped store's name (rdf_reifications, ^NKG, deg2p_exact_merged, labelset, ^ArnoKG) appears in Eraser.cls | "EraseAll empties the unscoped stores" (textual). |
| `::test_erase_all_empties_the_adjacency_stores_through_adjacency` :100 | The Eraser calls `Adjacency).RemoveAll(`, and the RemoveAll body names out/in/gen/degc/degw | EraseAll empties adjacency through its owner class. |
| `::test_the_eraser_preserves_the_operation_records` :110 | Eraser.cls never contains `Kill ^IVG.Ledger("rec"` but does mention `^IVG.Ledger("rec"` | Erasure removes content, not history. |

### 2e. tests/integration/test_256_ledger_redaction_e2e.py ("256 ledger redaction e2e")

Integration, live: SKIP + `requires_database` + `integration` markers (:38-42). The `world` fixture is `ledger_reset` (so MC as well) plus `make_engine(dim=4)` (tests/integration/_ledger_helpers.py:18-20).

`build_world` (:192-229), all through the ledger:
- Tenant A: nodes `tenantA|n1` (label, prop) and `tenantA|n2` in the **default graph**; relationships in graph `gTenantA` with qualifiers.
- Tenant B: the same shape, with relationships in `gTenantB`.
- One spanning revision.
- A node `tenantA|n3` that is created and then detach-deleted, plus a qualifier set.

`erase_tenant_a` = `erase_graph("gTenantA")` + `delete_nodes_by_prefix("tenantA|")` with the default graph (:232-234). Erasure is the precondition. The subject is `ledger.redact`. The obligations about erasure are listed below; the redaction-only tests (:285-383, :436-473, :505-541) use erasure only as setup.

| Test | Erasure-relevant promise | Rule |
|---|---|---|
| `TestUS1RedactTenant::test_the_scan_sees_tenant_a_after_the_erase_alone` :262 | After the erase **alone**, `^IVG.Ledger` and the ledger tables still contain tenant A strings, and the history/diff/reconstruct/export readers still show "tenantA". Reader: a full Native walk of `^IVG.Ledger` plus ledger tables | Erasure keeps ledger history (`rec`, revisions). |
| `TestUS1::test_nothing_in_the_ledger_or_its_readers_holds_tenant_a` :267 | Erase, then redact: **no** tenant A string anywhere in `^IVG.Ledger` (stmt, tuple and rec included) or in the ledger tables, while tenant B is still found | Combined with redaction, the erase leaves no live statement or tuple that redaction could not clear. Indirect evidence that the erase removed GA's stmt/tuple entries. |
| `TestUS1::test_tenant_b_records_are_byte_identical` :276 | B's canonical records and revision rows are byte-identical after erase + redact | Erasing tenant A does not alter B's history. |
| `TestDefaultGraphTenantByPrefix` :385-420 (`acme` fixture: default-graph nodes `acme\|x`, `acme\|z`, `acme-health\|y`, `acme-health\|w`, with relationships) | `delete_nodes_by_prefix("acme\|")`, then redact by prefix: tombstones == 5; `acme-health\|*` are still live (`get_node` is not None, :420) and still in the ledger; `verify()` is "equal" | Prefix erase is literal (`acme\|` does not match `acme-health\|`) and keeps non-matching nodes. |
| `TestUS2Verifiable::test_verify_diverges_after_the_erase_alone_and_is_equal_after_the_redaction` :429 | `ledger.verify().result == "diverges"` after the erase alone; "equal" with no differences after redaction | Erasing changes the store and the ledger's reconstruction diverges: erase is a non-ledgered write. |
| `TestUS3Refusals::test_live_default_graph_nodes_refuse_the_prefix_and_nothing_changes` :488 | After `erase_graph(GA)` **only**, `redact(None, prefix="tenantA")` raises `RedactionTargetLiveError` and the full snapshot (`^IVG.Ledger`, `^KG`, ledger and content tables) is unchanged | `erase_graph(GA)` does not remove default-graph nodes with tenant A ids (graph isolation). |
| `TestUS3::test_a_live_tenant_graph_is_refused_…` :482 | No erase, so redact is refused | (redaction) |
| Others (:285, :295, :310, :320, :336, :359, :374, :436, :452, :460, :467, :495, :505) | Erasure as precondition only | (redaction) |

No mocks. Every check is on live globals and tables.

---

## 3. Other erasure tests (rows condensed from three subagent reads, with citations kept)

### 3a. Integration (live IRIS)

All rows below are SKIP plus `iris_connection`, unless a gate is named.

| file::test | Cond. | Entry and essential setup | Promise and reader | Mocks / fault | Rule |
|---|---|---|---|---|---|
| test_214_drop_graph.py::removes_nodes :19, ::removes_edges :32, ::leaves_default_graph_untouched :48, ::nonexistent_returns_zero :60 | SKIP, MC, `node_graph_reset` | `drop_graph("g_drop")`; 2 nodes (+1 edge) in g; a default node | Return ≥2; SQL nodes/edges for g == 0; default node == 1; unknown graph → 0 | none | Graph erase removes rows, returns a count, isolates the default graph. |
| test_default_graph_spelling.py::test_delete_edge_removes_a_row_written_without_a_graph_id :108; ::test_drop_graph_removes_rows_written_without_a_graph_id :120; ::test_verify_graph_agrees… :130; ::test_delete_edge_all_graphs_removes_adjacency_in_every_graph :145 | SKIP | Raw INSERT with graph_id NULL; `delete_edge`; `drop_graph("")`; the same edge in default and a named graph with `all_graphs=True` | SQL count 0; `verify_graph("")` sqlEdges 1→0; per-graph `verify_graph` ok, outEdges 0 | none | NULL and '' are one default graph for drop_graph and delete_edge; `all_graphs` reaches every graph. |
| test_delete_nodes_graph_scoped.py::test_delete_in_one_graph_leaves_the_other_intact :85 | SKIP; in-fixture skip if `EraseNodeIds` is not deployed (:36); cleanup `erase_graph(A,B)` | store `delete_nodes(["x"], graph=A)`; the same ids, labels, props and edges in A and B | `rows==[[1]]`; in A: SQL nodes/labels/props/edges 0, `EdgeScan.MatchEdges` without x, `^KG` in/prop/label empty (`Meta.GetKG`), `Adj.Degree(hub)` 0; B intact; `^KG("__version")` increased | none | ID-list erase is graph-scoped across rows, adjacency, indexes and degree, and bumps the version. |
| …::test_returned_count_is_rows_removed :118; ::test_delete_of_2500_ids_succeeds :125 | same | x, y, never-existed; 2500 raw nodes in A plus id[0] in B | `[[2]]` and then `[[0]]` on repeat; `[[2500]]`; B row kept | none | Count = node rows removed; chunking above 2000 ids stays scoped. |
| …::test_delete_edges_is_graph_scoped :144 | same | store `delete_edges([(hub,R,x)], graph=A)` | `[[1]]`; A's neighbours lack x; B kept; node x kept | none | Relationship-list erase is scoped and keeps nodes. |
| …::test_prefix_erase_removes_only_matching_nodes_in_that_graph :155 | same | `delete_nodes_by_prefix("tmp:", graph=A)`; labels, props, 3 edges and embeddings in A and B | ==2; A's tmp nodes 0 and keep:1 kept; A rdf_edges 0 (incl. edges to keep); `^KG` out/in empty; `get_embedding(tmp:1,A)` None; B intact; version up | none | Prefix erase removes matching nodes, incident edges, adjacency and vectors in one graph. |
| …::test_prefix_erase_is_exact_not_case_folded :191; ::test_empty_prefix_is_refused :199 | same | `TMP:upper` vs `tmp:lower`; prefix "" | ==1; empty prefix: Python `ValueError` matching "erase_graph" **and** native `Eraser.EraseNodes(A,"")` raises matching "empty prefix"; node kept | none | Prefix match is case-exact; an empty prefix is refused at both layers. |
| …::test_ppr_and_neighbours_stop_seeing_deleted_nodes :210 | same | chain s→m→t; `delete_nodes(["m"],A)` | `kg_PERSONALIZED_PAGERANK` == {s:1.0, t:0.0}; neighbours of s empty | none | Readers stop seeing erased nodes. |
| …::test_default_graph_delete_leaves_named_graph :230 | same | d1 in default and A; `delete_nodes(["d1"])` | `[[1]]`; default 0; A 1 | none | Omitted graph = default only. |
| …::test_sql_fallback_is_scoped_and_chunked_on_live_iris :242 | same | **monkeypatch** `_eraser_methods={EraseNodeIds:False, EraseEdges:False}`; 2401 ids | Same scoping and counts by the SQL path | Forces the no-Eraser path. Reachable when the classes are not deployed | The fallback matches the Eraser's scoping and counts. |
| test_delete_adjacency.py :75, :94, :103, :116, :130, :158-:192, :213 | SKIP, MC | `create_edge` then `delete_edge` in named/default graphs; the same triple in 2 graphs (:130 also `BuildNKG`) | `verify_graph` ok, sqlEdges/outEdges; the other graph keeps outEdges 1; `Adj.Degree` decrements; no stray `^KG(gen\|degc\|deg\|degp,"a")` | none | `delete_edge` (a bypass of the Eraser) keeps adjacency exact and graph-scoped. |
| …::test_bulk_delete_adjacency_clears_a_nodes_inbound_and_outbound_edges :226 | same | `bulk_delete_adjacency(["hub"])` | Returns 1; hub degree None; neighbours fixed; unrelated edge kept | none | Node-scoped adjacency delete (all graphs). |
| test_delete_node_named_graph.py :85, :92, :100, :116, :120, :159, :167, :181, :186, :191 | `iris_connection` (no module SKIP); cleanup `erase_graph(uuid)` | `delete_node`/`bulk_delete_nodes`; node with label, prop, edge and **embedding dim 768 including a registry-routed `kg_emb_*`** in a named graph; a shared id in default + named | True; SQL nodes/labels/props/edges, `kg_NodeEmbeddings` and the routed row all 0; the other graph kept; missing → False; `DeleteResult(n,0)`; shared id without a graph → `ValueError` naming both graphs and nothing deleted (bulk too); `graph=None` → default only | none | `delete_node` erases every row of one node in one graph, including the routed vector; ambiguity is refused before any delete. |
| test_214_delete_edge_scoped.py :31, :40, :49, :58 | SKIP, MC, `node_graph_reset` | The same triple in umls/go/default | Per-graph SQL counts; `^KG("out",g,…)` | none | `delete_edge` scope: named / default-only / `all_graphs`. |
| test_nodes_edges_deep.py::TestDeleteEdge :217, :226, :239; ::test_drop_graph_nonexistent :254; TestDeleteNode :399, :406, :428, :437; TestBulkDeleteNodes :447, :457, :462 | MC | various | Mostly `isinstance(bool)` or int ≥0 (weak). :226 **patches `_iris_obj`** so `classMethodVoid` raises and still expects True; :428 patches `conn.cursor` to raise and expects `RuntimeError`; bulk returns (5,0)/(0,0)/(1,0) | see column | Weak; :226 is misleading (see §5). |
| test_236_token_write_paths.py :77, :81, :207, :211, :215, :224, :228, :233, :436, :518 | `ivg_236_scratch` (**skips unless `IVG_NS_IVG236`**) | world = EraseAll + a→b→c→d default + x→y in g1; each erase entry point | PageRank/WCC/CDLP/PPR answers change and `^KG("__version")` rises (never falls); `erase_graph("nothing-here")` still bumps the token | none | Every erase that can change an answer bumps the version token, even an empty erase. |
| test_233_arno_cache_stamp.py::test_write_and_delete_bump_the_stamp :39 | `iris_connection` | `delete_edge` (None and named) | `^KG("__version")` rises | none | `delete_edge` bumps the stamp. |
| test_236_algo_cache.py :157 (delete_edge, delete_node, `erase_graph(None)`, erase_all), :169, :184 | `ivg_236_scratch` | Cache filled first | Cached answer == recomputation; erased id absent from every `^IVG.AlgoCache` payload; `erase_all` → no entries | `monkeypatch.delenv` only | Erase purges the algorithm cache. |
| test_snapshot_inventory.py :58, :71 | SKIP | `GraphStores.InventoryJSON` vs `snapshot.STORE_PLAN` | Set equality | none | The Eraser's inventory equals the snapshot plan. |
| …::test_a_temporal_edge_survives_a_round_trip :89 (:102); ::two_hop_counts :192 (:211) | SKIP | A temporal edge / deg2p in a named graph; `erase_all` | `^KG("tout",G,…)` == "" and `^KG("deg2p",G,…)` == "" after the erase | none | EraseAll empties temporal and deg2p. |
| test_snapshot_routed_embeddings.py::test_a_routed_installation_survives… :115 | SKIP, MC | 2 graphs × 2 models, routed tables + registry; `erase_all` | `resolve_route(A/B)` None after the erase | none | EraseAll removes routes (registry). Whether tables are dropped is not read. |
| test_master_cleanup.py :49-:59 | SKIP | The MC EraseAll | `^KG("out",PROBE,…)` None; gen/degc empty; Degree 0; rdf_edges 0 | none | EraseAll empties ^KG and rows, named graphs included. |
| test_411_nkg_version_monotonic.py :38, :48 | MC | `erase_all` then a new chain; `erase_graph(named)`, `erase_all` | Betweenness only over the new prefix; `^NKG("$meta","version")` strictly increasing | none | No stale centrality; the ^NKG version is monotonic across erases. |
| test_ledger_us05_compat.py::TestNeverEnabled :67; ::TestDefaultMode :80; ::TestStrictMode :98 | SKIP, `ledger_reset` | `delete_edge`; Cypher `DETACH DELETE`; strict: `delete_edge`, `delete_node`, `bulk_delete_nodes`, `drop_graph("g")`, `delete_reification`, store `delete_nodes`/`delete_edges` | No ledger data when never enabled; default mode: verify diverges as `unrecorded_writes`; strict: `LedgerStrictModeError` with tables unchanged | none | In strict mode the listed erase paths are refused. `erase_graph`, `erase_all`, prefix, `erase_bare_nodes` and `bulk_delete_adjacency` are **not in the list**. |
| test_verify_graph.py :186-:289; :316, :364 | SKIP | Raw `DELETE %NOINDEX` on rdf_edges (a deliberate bypass); `InventoryJSON` | verify_graph ok 0 with orphan out/in drift seen only by `verify_graph`; each SQL store's graphScoped claim matches its `graph_id` column; the unscoped SQL set == {rdf_reifications} | Raw SQL bypass | The inventory's scope claims match the schema; bypass deletes are detectable. |
| test_engine_critical_fixes_e2e.py :106, :138; test_temporal_engine_polish_e2e.py :55, :145, :164; test_nodes_edges_and_algo_paths.py :152-:198; test_api_completeness.py :141; test_index_consistency_e2e.py :166 | class SKIP / MC | `bulk_delete_nodes`, `bulk_delete_adjacency` (DeprecationWarning), `drop_graph` | Edges removed in and out, unrelated edges kept; `DeleteResult` counts; `[]`→0; `drop_graph` leaves `_nkg_dirty` False and `^KG("out",g,…)` None | none | Bulk deletes count and clean edges; graph erase leaves no deferred staleness. |
| test_256_ledger_redaction_perf.py sc002 :45, sc003 :95 | SKIP + **`perf` (deselected)** | 10k revisions over 10 tenants; erase + prefix + redact | `verify()` equal; other tenants byte-identical; timing | none | As 2e, at scale. |
| test_ledger_us10/us02/ops_branches | SKIP, `ledger_reset` | Changeset `delete_node`/`delete_relationship` (LedgerApply, **not the Eraser**) | Cascade order; strict refusal; failing changeset leaves tables, `^KG` and stmtNext unchanged | none | Ledger delete semantics (a separate path). |

Cleanup only (no erasure assertion): test_mcp_tools, test_buildkg_atomicity (its `_unpoison` docstring :105 notes that EraseAll's indexed DELETE trips −106 on extent drift), test_namespace_isolation, test_remaining_paths :469, the snapshot `erase_all` setup calls, and the 236 `finally` blocks.

### 3b. E2E (live IRIS)

| file::test | Cond. | Entry and essential setup | Promise and reader | Mocks / fault | Rule |
|---|---|---|---|---|---|
| test_erase_graph_nkg_e2e.py :138, :159, :174, :188, :204 | MC; fails rather than skips on a missing IRIS | `erase_graph(erased)`; two graphs share ids b, c; labels, props, row-backed edges; `BuildNKG`; ^NKG sentinel | :174 returns **5** (3 nodes + 2 edges; labels and props not counted); sentinel and `$meta nodeCount` gone; `^NKG $meta version` up. :188 the survivor's `^KG` out == {a→b, b→c} exactly, and a standing ^NKG == ^KG. :138/:159/:204 HLL / `approx_count_distinct` / reach equal a rebuild's. :138 passes **vacuously** when ^NKG was dropped | planted sentinel | A graph erase drops ^NKG when any edge or node might be in it, and never leaves ^NKG stale or lossy for the survivor. |
| …:220, :238, :268, :287, :301 | same | Adjacency-only edges (`WriteAdjacency`, no row); a graph written before the ^NKG skeleton; `Eraser.EraseEdges` direct; default graph | :220 ^NKG dropped (**`^KG("out",g)` not checked**); :238 returns 5 and ^NKG kept byte-identical apart from version; :268 EraseEdges returns **0** for an adjacency-only edge, `^KG("out",g,x)` gone, ^NKG dropped; :287 returns 1; :301 `erase_graph(None)` drops ^NKG (**default rows not asserted gone**) | adjacency with no row (reachable on legacy installs) | The ^NKG keep/drop rule; EraseEdges counts rows but invalidates on adjacency. |
| test_erase_nkg_kept_e2e.py :221, :248, :265, :277, :299, :324, :359 | MC, fail-not-skip | `Eraser.EraseNodeIds("", ids)` / `EraseNodes("", prefix)` / `erase_graph`; nodes, labels, props, edges; interned vs not | Returns 3/1/2/1/3; ^NKG kept iff no erased id is interned; BFS unchanged when kept; SQL nodes/labels/props/edges for the ids 0; ^NKG ⊆ ^KG; :324 rows and ^KG are identical whether ^NKG is kept or dropped | none | The ^NKG decision never changes what is erased; prefix erase shares the rule. |
| test_230_erase_residue.py::test_erase_one_graph_spares_the_other :238; ::…two_hop_reader… :279; ::test_erase_all_leaves_no_node_data :310 | fail-not-skip, own `_wipe` | `erase_graph(A)`; A and B share 3 ids; `rebuild_kg` + `Build2HopStats`; `erase_all` ×2 | `^KG` prop/label/deg2p for B byte-identical and for A empty; default `KHop2CountFast` unchanged; EraseAll: 1st ≥0, **2nd == 0**, every first-level `^KG` subscript except an allowlist (`__version`) empty | none | Per-graph `^KG` stores are erased by key only; EraseAll empties all of `^KG` except the version stamp. |
| test_227_erase_isolation.py :97, :122, :141, :160, :179, :193, :209 | `ivg227_env` fail-not-skip; :209 `requires_clean_isolation` | One node id in A and B; models a and b at widths 384/768; routed tables; `erase_graph(A)`, `erase_graph("")`, `erase_all` | A nodes 0 / B 1; `kg_KNN_VEC` on B still returns the node; A labels 0 / B ≥1 (**props not asserted**); A's routes gone or empty; A's registry rows gone and B's tuple-identical (incl. `set_at`); B's tables exist; `kg_NodeEmbeddings` table exists after the default erase (**rows not asserted**); EraseAll: registry `kg_emb_*` 0, routed tables dropped, nodes 0, `kg_NodeEmbeddings` 0 | none | Routes and the registry are graph-scoped; claimed routes are dropped; legacy tables are never dropped. |
| test_227_scale.py :337, :346 | slow, module fixture | 50 graphs × 2 models = 100 routes (45 graphs with routes only); `erase_graph` each | None of the 100 tables remains (INFORMATION_SCHEMA); under 90 s | none | A graph erase drops all its claimed routes, including empty ones. |
| test_temporal_erase_owner.py :60, :73, :87, :100 | SKIP, **no MC**; :87 `requires_clean_isolation` | `create_edge_temporal x→y` in A and B; `erase_graph(A)`; `erase_all`; `delete_node(x, graph=A)` | `get_edges_in_window` empty for A and non-empty for B; A's `get_temporal_aggregate` falsy; EraseAll → both empty; node erase removes in and out temporal edges in A only | none | Temporal erase is graph-scoped (only B's window read is checked; B's aggregate is not). |
| test_254_purge_e2e.py :304, :314, :322 | SKIP, MC | `delete_nodes_by_prefix("action:",g)`; `erase_graph(g)`; `delete_edge` on a temporal edge | A later purge deletes 1/0/1, which shows the timestamps were removed for prefix and graph erase but **left by `delete_edge`**; `adjacency_recount` clean | none | Erase removes temporal timestamps; the `delete_edge` bypass does not. |
| test_234_multigraph_storage_e2e.py :266, :278 | MC, fail-not-skip | Mode set on 2 graphs with **no data**; `erase_graph(G_MODE)`; `erase_all` | `is_multigraph(G_MODE)` False (also on a fresh engine); G_SINGLE kept; `$Data(^IVG.GraphMode)` 0 | none | Multigraph mode is **cleared** with its own graph only. |
| test_temporal_structural_optout_e2e.py :348, :361, :222 | SKIP, MC | Opt-out of SPAN in g; temporal-only writes; `erase_graph(g)` then `erase_all`; snapshot restore; `erase_bare_nodes` | After `erase_graph` the setting is kept (a re-ingest writes no rows); after `erase_all` it is reset; the snapshot restores it; sweep erases 9 | none | Temporal-only settings are kept by graph erase and removed by EraseAll. |
| test_temporal_bare_nodes_e2e.py :181, :254, :268, :282, :291, :300, :310, :331, :348, :365, :528 | SKIP, MC | `erase_bare_nodes`; 205 bare inserts with kept dependants; a 2nd connection with an uncommitted edge; a racing writer thread; `delete_node` after a dry run | Batched counts erased/bare/kept/batches; dry run leaves `GraphStores.Digest` and `^KG("__version")` unchanged; age floor honoured; graph-scoped; a routed embedding keeps its node; an uncommitted dependant blocks deletion; raw DELETE refused by FK −124; no lost acknowledged edge; :528 `delete_node` removes a later-written edge **silently** | real concurrency (reachable) | The bare sweep is guarded and batch-atomic; ID erase is unconditional. |
| test_eraser_without_fhir_tables_e2e.py :57 | SKIP + **`IVG_FHIRLESS_NAMESPACE`**; fails if the namespace has FHIR tables | `erase_graph` with nodes, labels, props and an edge | No exception; SQL counts 0. The docstring says it passes even without the fix on 2026.3.0AI | missing tables (reachable) | A missing FHIR table never fails an erase. |
| test_460_r268_erase_nkg_routes_e2e.py :252, :257 | Namespace `IVG460FX*/FY*` + container | `removed` fixture: default and named triangles, `sync()`, optional `delete_edge` first, then `erase_graph` / `delete_node`×3 / `bulk_delete_nodes` | Leiden/SCC/k-core/triangles/betweenness/closeness equal the default-graph values with no `sync()`; the next read rebuilds ^NKG to exactly the 6 default nodes and 7 edges | none | After erase, ^NKG readers answer for survivors only and rebuild on demand. |
| test_460_r274_nkg_leftovers_e2e.py :59; test_460_r286_nkg_kept_dictionary_e2e.py :103, :109 | same NS gate; :109 skips if an Arno library is configured | **Cypher** `USE GRAPH … MATCH ()-[r]->() DELETE r` | SCC/closeness/eigenvector answer only the default graph; a kept dictionary does not leak | missing library (reachable) | Bypass: Cypher DELETE leftovers in ^NKG do not leak. |
| test_degree_cache_live.py :300, :314, :325 | **`IVG_PAROS_NAMESPACE`** | Native `Eraser.EraseGraph/EraseNodeIds/EraseAll` on **adjacency-only** state with a warmed cache | `$Data ^KG(out\|in\|gen\|degc, G)` 0, Degree 0; the node's gen/degc gone and the inbound neighbour's degree 0; EraseAll clears every graph | adjacency without rows | The Eraser clears adjacency and degree cache even with no rows. |
| test_252_writer_paths_e2e.py :50, :59, :93, :100, :172 | SKIP (**runs `erase_all` in the session namespace, USER by default**) | `delete_edge`, `erase_graph(g)`, `erase_all`, `delete_node`, `bulk_delete_adjacency([a])` | Adjacency recount `differences()` == []; `bulk_delete_adjacency` warns, returns 1 (number of ids), removes incident rows in every graph and keeps nodes | none | Erasure leaves `^KG` equal to the rows. |
| test_464_caller_txn_e2e.py::test_a :328, ::test_b :343, ::test_c :358, ::test_d :380, for writes `delete_node` (:192/:309), `delete_edge` (:204/:310), `cypher_delete` (:294/:317) | **`IVG_R464_TXN_NS`** + container; txn = SQL `START TRANSACTION` or driver `setAutoCommit(False)`; **own connections (unpatched createIRIS)** | Caller txn + own INSERT; node n (label, prop) with an edge | (a) After the caller's rollback, node, label, edge row, `^KG(out,0,…)` and the caller row are all restored. (b) Commit keeps both. (c) A failed Cypher DELETE keeps the caller's work and `$TLEVEL` 1. (d) With no caller txn, `$TLEVEL` 0 and the change is visible from a 2nd connection. Each write leaves `$TLEVEL` == 1 inside the caller txn | real refusal (c) | The Eraser (`EraseNodeIds` via `delete_node` → `_eraser_txn`) nests under the caller's transaction and never commits or rolls it back. **`erase_graph`, `erase_all`, prefix, store `delete_edges` and `erase_bare_nodes` are not in the write list** (grep). |
| test_465_stale_error_text_e2e.py :82, :97, :106 | **`IVG_R465_ROLE_NS`** | A reading role (SELECT+EXECUTE, DB at R) calls `delete_node("bob")` | `GraphWriteError` containing "erase failed on rdf_edges"; later errors carry no stale `$ZERROR` | real privilege refusal | A failed Eraser delete surfaces as `GraphWriteError`. |
| test_463_refused_reads_e2e.py :82, :95 | **`IVG_R463_PRIV_NS`** | User without SELECT; `delete_node("x"*900)` | "delete_node failed (SQLCODE -99), nothing written", node kept; an over-long id → `GraphWriteError` with a cause | real refusal / `<THROW>` | A refused lookup raises before any erase; an Eraser throw becomes `GraphWriteError`. |
| test_460_r203_refused_writes_e2e.py :63, :77 | `rr.requires_namespace` | Reader role: `delete_edge`, `delete_reification` | `GraphWriteError` −99 "nothing written", `rr.state` unchanged; owner `delete_edge` of a missing edge → **True** | real refusal | — |
| test_460_sec_audit_e2e.py::test_erase_graph_reaches_only_its_own_routes :118 | `IVG_NAMESPACE` starts IVG460FX | secA route with a vector; a **planted** registry row for secB whose table_name is `"<secA table> WHERE 1=1 OR ? IS NULL --"`; `erase_graph("secB")` | secA's route still holds `sec:a` | planted registry row (reachable by any schema writer) | The registry's table_name is never pasted into DDL/DML unless it has the route shape (`IsRouteName`). |
| test_231_fhir_graph_sync_e2e.py::test_erase_keeps_registration_and_resets_watermarks :290; ::test_erase_clears_canonical_bookkeeping :310 | FHIR namespace (`IVG_NS_IVGFHIR`) | `erase_graph(FHIR GRAPH)` with `fhir_unresolved`, `fhir_definitions` and `fhir_canonical_refs` rows in GRAPH and another graph | nodes 0; `fhir_unresolved` 0; `fhir_graphs` watermarks (0,0) and the row kept; a rebuild re-projects; the other graph's rows kept | none | FHIR graph erase clears side rows by graph, resets watermarks and keeps the registration. |
| test_reification_e2e.py :70, :89 | SKIP | `delete_reification`; `delete_node(A)` with a reified edge | Reification 0 and edge kept; the node erase removes reification and reifier node | none | Node erase cascades to reifications of incident edges. |
| test_460_r313_pagerank_loners_cache_e2e.py :43, :54, :105 | `alt.requires_namespace` | `delete_node`, `delete_nodes_by_prefix`, Cypher `DETACH DELETE`, Cypher `DELETE r` | `kg_PAGERANK` no longer includes the node; `DELETE r` keeps both nodes | none | Every node-removal path invalidates the algorithm cache. |
| test_460_r310_long_id_lists_e2e.py :50, :56, :62, :75 | SKIP | 1200 nodes; a 1199-edge chain; a hub with 1200 spokes | bulk delete → 0 nodes; prefix **returns 1200**; Cypher `DELETE r` → 0 rels, nodes kept; hub `delete_node` → True, 0 spokes | none | Erasure works above 500 ids. |
| test_460_all_graphs_writes_e2e.py :229 (cases :151-:153) | `IVG460FX` + container | Cypher `DELETE r` / `DETACH DELETE n` / `DELETE n` across default, r65a and r65x | Only matched graphs change; under USE GRAPH only r65a (SQL on 4 tables; edges read only by `s IN ids`) | none | Cypher DELETE is per-graph. |
| test_delete_graph_scope_e2e.py :91, :101, :111, :118 | `iris_connection` (fails if None) | Cypher USE GRAPH / graph-less DETACH DELETE; A and B hold x; C holds an orphan prop | USE GRAPH removes A only; a graph-less delete removes bound rows only (C's orphan prop kept); non-DETACH refused ("DETACH") | none | Cypher DELETE scoping. |
| test_470_silent_writers_e2e.py :166, :189, :205 | `IVG_R470_WR_NS` | Cypher DETACH DELETE of an endpoint or reifier, named vs default | Reification row, reifier node and props 0; deleting a reifier keeps the edge; a named delete leaves the default graph's | none | Cypher DETACH DELETE cascades to reifications by graph. |
| test_460_r221_refused_delete_e2e.py :37, :48; test_252_cypher_read_after_write_e2e.py :66, :76; test_460_set_pinned_bindings / r208 / 470_rels_and_paths / 470_unwind / r310_unwind / 234_multigraph_cypher / 262_alt_schema_paths :269-:284 / r311 injection :134 | various gates | Cypher DELETE variants; `erase_graph("alt_g")` and `_store.delete_nodes` under schema IVGALT | A non-DETACH delete of a connected node is refused and nothing is written; ^KG updated with no sync; exact bindings deleted; a non-default schema is honoured; an injected name is refused | none | Cypher DELETE semantics (not the Eraser). |
| test_named_graphs.py::test_drop_graph_removes_all_paths :201 (under tests/unit/ but **live**) | SKIP | Nodes, an edge and a temporal edge in g; `drop_graph` | Cypher `USE GRAPH g … count(r)` == 0 | none | `drop_graph` removes structural and temporal edges. |

Cleanup only: test_227_inventory (whole file), test_227_graph_scoped_knn, test_227_recall (:68 deletes registry rows itself after `erase_graph`), test_embedded_wgproto_e2e, test_460_r281, test_470_orphan_props, test_create_edge_atomic, test_470_python_writers, test_464_api_typed_props (see §5), test_235_patient_ranking, test_460_kg_webapp_least_privilege, test_untested_methods, test_460_status_index_inventory, test_arno_namespace_kept, and the test_460_kg_webapp_reset fixture (it asserts no `kg_emb_<16hex>` route remains after `erase_all` under schema RAG, :161-:168).

### 3c. Unit tests (no IRIS unless noted)

Most unit "erasure" tests are SRC or MOCK. That is roughly 60% of them, per the subagent's count.

| file::test | Kind | What is checked | Mocks / fault (reachable?) | Rule |
|---|---|---|---|---|
| test_delete_nodes_graph_scope.py :67, :84, :100, :115, :131, :142 | MOCK-SQL (Eraser marked absent → SQL fallback) | Chunks of ≤500 ids; no `OR o_id IN`; every statement has `COALESCE(graph_id,'')=COALESCE(?,'')` with "A" or "" bound (None and "" are equal); count = summed rowcount; ids de-duplicated | `_RecordingCursor` (fallback reachable) | Fallback scoping, chunking and counting. |
| …:149, :309, :155, :162 | unit | `graph` is keyword-only; invalid graph "0" → `ValueError` with no statements; `[]` → `[[0]]` with no statements | — | Refusal before I/O; the empty list is a no-op. |
| …:193, :208, :214, :219, :232 | MOCK-CALL | 5 × `EraseNodeIds(graph, ≤500-id JSON)`, no data SQL; default → ""; returns the Eraser's count; an Eraser error ("SQLCODE -124") propagates as `RuntimeError` with **no SQL fallback**; the ledger guard runs first | faked `_call_classmethod` (reachable) | The Eraser path is authoritative. |
| …:245, :262 | MOCK-SQL / MOCK-CALL | `delete_edges` fallback scoped and counting real rows; Eraser path = 3 × `EraseEdges("B", JSON)` | — | Relationship-list erase. |
| …:277, :285, :291, :297 | unit | `delete_nodes_by_prefix("")`/`None` → `ValueError` matching "erase_graph", no calls; exactly one `EraseNodes(graph, prefix)`; no fallback (RuntimeError "EraseNodes"); the engine delegates | — | Prefix rules. |
| test_460_r276_except_audit.py::test_a_refused_transaction_before_the_eraser_raises_and_erases_nothing :84 (`delete_nodes`, `delete_nodes_by_prefix`, `delete_edges`, `erase_bare_nodes`) | unit | The cursor raises on `START TRANSACTION` → `GraphWriteError` "SQLCODE -110"; the Eraser is never called | fault: refused START or lock (reachable) | `_eraser_txn` fails closed before the Eraser. |
| test_store_protocol.py :453, :458, :609, :616 | MOCK-SQL | Empty → `[[0]]`; the SQL path issues `cursor.execute("COMMIT")`, never `conn.commit()` | — | The fallback commits on the cursor. |
| test_delete_node_delegation.py TestDeleteNode :61-:93; TestReifiersGoWithTheirEdges :108-:129; TestBulkDeleteNodes :136-:166 | MOCK-CALL (`FakeStore`) | Graph pass-through; None → ""; single-graph resolution; an ambiguous id → `ValueError` naming both; missing → False; failure raises; invalid name refused before I/O; reifier nodes deleted after the node (other graph too) and not counted; bulk per-graph and per-batch, a failed batch gives (1,1) with the others still run | `fail_for` (reachable) | `delete_node`/`bulk_delete_nodes` semantics. |
| test_463_refused_pagerank_delete_node.py :76, :86, :96, :103 | unit | −99/−415 → `GraphWriteError` "nothing written"; a shared id stays `ValueError`; a reifier failure says "the node is deleted; the reifier nodes … are not" | patched store (reachable) | **The node and its reifiers are not atomic.** |
| test_214_named_graphs.py::TestEraseGraphExtended :146, :163, :169, :186, :207; TestDeleteEdgeScoping :297-:314 | MOCK-CALL / SRC | `erase_graph("umls")` emits no SQL and calls `EraseGraph("umls")` exactly once; returns 0; Eraser.cls deletes dependants before parents (first occurrence); every `graph_id … =` line has 2 × COALESCE; every DELETE between EraseGraph and EraseAll has a WHERE; `delete_edge` SQL scoped unless `all_graphs` | MagicMock native | Facade delegation; FK order; default spellings (SRC). |
| test_nodes_edges_unit.py TestEraseGraph :464-:512; TestDeleteEdge :198-:212; :231 | MOCK-CALL | Returns the Eraser's count (10/7); None → ""; `drop_graph` → EraseGraph; erase_all → EraseAll; a failure raises; `_nkg_dirty` False; `delete_edge` ROLLBACK without COMMIT when the ^KG delete fails (unindexed) | faults (reachable) | — |
| test_engine_mocked.py :252, :487, :243, :247, :425; test_engine_coverage_v8.py :1142-:1195, :511; test_engine_deep.py :981 | MOCK-CALL | `drop_graph` → `EraseGraph`; `drop_graph("")` → "" (the default graph, not refused); restore(merge=False) clears via `EraseAll` | — | — |
| test_snapshot_coverage.py :332, :365 | MOCK | Restore clears via `EraseAll`; if EraseAll raises, no INSERT follows | fault | — |
| test_227_erase_plan.py :66, :81, :96, :105, :122, :140, :145, :155, :169, :178, :216, :243, :250 | SRC (+AST :216) | Child rows deleted by their own `graph_id` (not via a nodes subquery); legacy embeddings by graph_id; COALESCE on both sides; routes read from the registry, `DROP TABLE`, their registry rows deleted; legacy tables never dropped; **the quarantine is not named in EraseGraph or EraseAll, and no Python statement deletes it outside `place_quarantined`**; EraseAll empties the registry and drops routes | none | Graph-erase frame (textual). |
| test_227_orphan_route.py :48, :68 | MOCK | The route registry row is committed immediately; a failed insert does not commit | patched helpers | Prevents orphans (the erase side is not tested). |
| test_graph_stores_inventory.py :35-:103; test_227_objectscript_surface.py :61, :114, :146, :160; test_230_kg_subscript_layout.py :111, :155, :178, :195 | SRC | One inventory, its entries, scoped stores with locators, unscoped stores with reasons; ^KG prop/label/deg2p lead with the graph key; `deg2p_exact_merged` unscoped | none | The inventory is the frame. |
| test_erase_nkg_kept.py :54-:154; test_460_r268_erase_nkg_invalidation.py :34-:75; test_460_r274_nkg_leftovers.py :39 | SRC | ^NKG writers are limited; the interning check; `GraphEdgesInNKG \|\| GraphNodesInNKG` is decided before the DELETE; EraseEdges/EraseAll always invalidate; the version bump and AlgoCache purge are unconditional; "cannot tell" → interned; EraseAll does not mark "invalidated" | none | ^NKG rule (textual). |
| test_temporal_single_owner.py :134, :162-:214 | SRC | `TemporalIndex.EraseGraph` kills tout/tin/bucket/tagg/edgeprop/tlast at `ForIndex(graph)`; EraseAll kills all six; `EraseNodes` checks both ends and does no `DeleteAdjacency`; the Eraser delegates | none | Temporal frame (textual). |
| test_temporal_structural_optout_architecture.py :57, :70, :79 | SRC | EraseGraph has no `Kill ^IVG.TemporalStructural`; EraseAll does; the store is in the inventory as scoped | none | Kept store: temporal-only settings. |
| test_234_multigraph_sql.py :215, :220 | SRC | `Kill ^IVG.GraphMode(tKey)` in EraseGraph; `Kill ^IVG.GraphMode` in EraseAll | none | The multigraph mode is cleared, not kept. |
| test_temporal_bare_nodes_unit.py :56, :64, :71 | MOCK-CALL | `EraseBareNodes("g",500,1,60)` argument order; not deployed → RuntimeError; invalid name → ValueError | — | — |
| test_252_writers_leave_adjacency_to_the_index.py :90, :112-:141; test_temporal_engine_polish.py :46-:177 | MOCK-CALL | `bulk_delete_adjacency` warns and calls `EraseEdges` once per graph with de-duplicated triples (indexed) or `BulkDeleteAdjacency` (unindexed); `[]` → nothing | — | Deprecated alias. |
| test_adjacency_single_writer.py :129, :210; test_adjacency_counter_ownership.py :58-:159; test_degree_cache_writers.py :128, :305, :415, :421 | SRC | The Eraser writes out/in only through Adjacency.Remove*; legacy deg/degp killed only in RemoveSource/RemoveGraph/RemoveAll; `Remove` checks other graphs before `DeleteIndex` | none | Adjacency ownership. |
| test_463_kg_write_failures_raise.py :126, :135; test_460_r203_refused_writes.py :71, :81, :162; test_unified_edge_store.py :59 (+ live :244, :266) | unit / live | `delete_edge` → `GraphWriteError` with ROLLBACK and no COMMIT when the ^KG delete fails or is refused; a missing row → True | faults (reachable) | Bypass path `delete_edge`. |
| test_dictionary_probe.py :44, :51; test_460_r206_reader_capabilities.py :124, :132 | unit | Eraser presence probed through `%Dictionary.CompiledMethod` / `IDKEYExists`; a dead connection raises | fake conn | Selects the Eraser vs fallback path. |
| test_230_native_conn_reconnect.py :66-:131 | harness | `<UNDEFINED>zEraseAll` is not treated as a dead connection | fakes | Harness only. |

---

## 4. Rules the tests express

For each rule: the supporting tests, then the essential conditions no test checks. "SRC" means only textual support.

### 4.1 Graph erase: the stores and the frame

**Supported by:**
- SQL rows: test_erase_graph :91, :148; test_214_drop_graph :19, :32.
- `^KG` out/in: test_erase_graph :100.
- gen/degc/Degree: test_erase_graph :113; test_degree_cache_live :300 (adjacency only).
- Temporal tout/tin/bucket/tagg: test_erase_graph :129; test_temporal_erase_owner :60, :73; test_254 :314.
- `^KG` prop/label/deg2p: test_230_erase_residue :238, :279.
- Routes: test_227_erase_isolation :141, :160, :179; test_227_scale :337.
- FHIR rows: test_231 :290, :310.
- Ledger tuples: test_edgescan_ledger_erase :113.
- ^NKG: test_erase_graph_nkg_e2e; test_erase_nkg_kept_e2e :299.
- AlgoCache and version: test_236_algo_cache :157; test_236_token :215-:228; test_411 :48.
- Oracle: test_erase_graph :239.
- Isolation of another graph: test_erase_graph :174; test_230 :238; test_227_erase_isolation :97-:179; test_temporal_erase_owner :60; test_214 :48; test_erase_graph :223.
- Textual frame: test_227_erase_plan, test_eraser_inventory_coverage, test_graph_stores_inventory, test_temporal_single_owner, test_214_named_graphs :169/:207.

**Untested:**
- **No test reads h's temporal subtree after erasing g** at the global level. test_erase_graph :181-184 reads OTHER's tout and bucket only, not tin, tagg, edgeprop or tlast. test_temporal_erase_owner reads B through the window API only, not B's aggregate.
- **tlast and edgeprop of the erased graph** are never read after an erase.
- The erased graph's **docs/BM25 rows**, **kg_EdgeEmbeddings**, **kg_eemb_\* edge routes**, **rdf_reifications of its edges** and **kg_NodeEmbeddings rows** are never counted after `erase_graph`. The only exception is the trigger-failure test, which checks that they are *restored* after a failed erase, never that they are *gone* after a successful one. `docs` appears only in that test.
- Another graph's labels, props, node row, degc, docs and vectors are not all read after erasing g. Labels and vectors are read in test_227 :97/:122; props are named but not asserted.
- `^KG("degw")` and legacy `deg`/`degp` are not read after a graph erase.
- `^IVG.Ledger("stmt")` is never read after a graph erase, only `("tuple")`.

### 4.2 Default-graph spellings (None, "", NULL)

**Supported by:** test_erase_graph :188 (NULL and ''; **usually skipped** on a fresh schema, :206-213); test_default_graph_spelling :120, :130 (`drop_graph("")` with NULL rows); test_erase_graph :223 (key 0 is not a wildcard); test_236_token :224 (`erase_graph(None)`); test_erase_graph_nkg_e2e :301 (^NKG only); test_227_erase_isolation :193 (`graph=""`, table survives); test_delete_nodes_graph_scoped :230; test_delete_node_named_graph :181; unit test_delete_nodes_graph_scope :100/:208, test_nodes_edges_unit :476, test_engine_deep :981; SRC test_227_erase_plan :105 and test_214_named_graphs :186.

**Untested:**
- That `erase_graph(None)` and `erase_graph("")` have identical effects.
- NULL-spelled rows in labels, props, docs, embeddings or FHIR tables under a default erase.
- Prefix or ID erase over NULL-spelled rows.
- Whether default rows are actually gone after `erase_graph(None)` (test_erase_graph_nkg_e2e :301 checks ^NKG only).

### 4.3 Invalid graph name refusal

**Supported by:** test_erase_graph :260 (`"0"`, broad `Exception`, default graph intact); unit test_delete_nodes_graph_scope :155 ("0", no statements); test_delete_node_delegation :93; test_temporal_bare_nodes_unit :71.

**Untested:**
- The **Eraser-side** refusal (`GraphKey.ForIndex` before `TSTART`, Eraser.cls:49-51). In every test, Python's `validate_graph_name` refuses first (iris_vector_graph/_validate.py:38-40; nodes_edges.py:1514). No native call passes "0" or an unrepresentable name to `EraseGraph`/`EraseNodes`/`EraseNodeIds`/`EraseEdges`/`EraseBareNodes`.
- Over-long names, control characters (only in units), and non-string names at the engine `erase_graph` level.

### 4.4 Prefix erase (including the empty prefix)

**Supported by:**
- test_delete_nodes_graph_scoped :155 (matching nodes, incident edges, adjacency and vectors in one graph), :191 (case-exact), :199 (empty prefix refused in Python **and** natively, node kept).
- test_erase_nkg_kept_e2e :359 (count and ^NKG rule).
- test_254 :304 (temporal timestamps removed).
- test_460_r310 :56 (returns 1200).
- test_256 :385-420 (`acme|` does not match `acme-health|`, which survives).
- test_eraser_failures `nodes` op (rollback).
- test_236_token :211 (version bump).
- unit test_delete_nodes_graph_scope :277-:297.
- test_460_r276 :84.

**Untested:**
- `%`/`_`/`[` metacharacters. Eraser.cls uses `%STARTSWITH` plus a `$Extract` re-check; no test puts a LIKE wildcard in a prefix.
- A prefix that matches in two graphs where only one is erased. test_delete_nodes_graph_scoped :155 has B with the same ids, so this is partly covered.
- Prefix erase of nodes with docs, reifications, `kg_eemb_*` edge routes, or FHIR rows.
- `delete_nodes_by_prefix(None)` at engine level. Only the store level is unit-tested.

### 4.5 ID-list erase

**Supported by:**
- test_delete_nodes_graph_scoped :85, :118, :125, :210, :230, :242.
- test_delete_node_named_graph (all, including routed vectors and ambiguity refusal).
- test_erase_nkg_kept_e2e :221-:324.
- test_temporal_erase_owner :100.
- test_degree_cache_live :314.
- test_reification_e2e :89.
- test_460_r310 :50, :75.
- test_252_writer_paths :100.
- test_eraser_failures `ids` op.
- test_temporal_bare_nodes :528 (unconditional).
- test_464 `delete_node`.
- unit test_delete_nodes_graph_scope, test_delete_node_delegation, test_463_refused_pagerank_delete_node.

**Untested:**
- Duplicate ids at the live level (unit only).
- Ids present in `^KG` but with no row (EraseNodeIds sweeps `^KG` for absent ids, Eraser.cls:361-363). test_degree_cache_live :314 is the only adjacency-only case.
- `kg_eemb_*` rows for incident edges.
- Docs for the erased id.
- FHIR node rows (`EraseFHIRNodeRows`).
- Ledger stmt/tuple for incident edges.
- A self-loop.
- An id that would raise `<SUBSCRIPT>` in ^NKG (`NodeInterned` "cannot tell").

### 4.6 Relationship-list erase (EraseEdges / store.delete_edges / bulk_delete_adjacency)

**Supported by:** test_delete_nodes_graph_scoped :144, :242; test_erase_graph_nkg_e2e :268 (an adjacency-only edge returns 0 but is removed), :287; test_eraser_failures :115 (rollback, rdf_edges only), :125 (non-array refused); test_252_writer_paths :172 and test_delete_adjacency :226 (`bulk_delete_adjacency`); unit test_delete_nodes_graph_scope :245, :262; test_252_writers_leave_adjacency :112-:141.

**Untested:**
- A missing triple → 0 at the live level.
- A default-graph triple.
- Multigraph parallel edges (EraseEdges deletes every row with that s,p,o).
- Reification, `kg_EdgeEmbeddings` and `kg_eemb_*` rows actually gone.
- The ledger statement killed (`EraseEdgeRow`, Eraser.cls:667-678).
- Temporal timestamps of the erased edge.
- The ignored status of `Adjacency.Remove` (Eraser.cls:450, :668 use `Do`, not `$$$ThrowOnError`).
- Rollback of the reifications and edge embeddings when the rdf_edges delete fails. test_eraser_failures :122 counts rdf_edges only.

### 4.7 Erase-all

**Supported by:**
- test_erase_graph :295, :309, :326.
- test_230_erase_residue :310 (every `^KG` subscript but `__version`; the 2nd call returns 0).
- test_227_erase_isolation :209 (registry, routed tables, nodes, kg_NodeEmbeddings).
- test_temporal_erase_owner :87.
- test_234 :278 (GraphMode).
- test_temporal_structural_optout :348, :361.
- test_snapshot_inventory :89, :192.
- test_snapshot_routed_embeddings :115.
- test_master_cleanup :59.
- test_236_algo_cache :184.
- test_411 :38, :48.
- test_degree_cache_live :325.
- test_252 :93.
- test_eraser_failures :104 (rollback).
- SRC: test_227_erase_plan :178, :243, :250; test_eraser_inventory_coverage :85, :100.

**Untested:**
- The exact first-call return value (only ≥0).
- `docs` emptied.
- FHIR rows deleted and watermarks reset by EraseAll.
- `^IVG.Ledger` stmt/tuple killed while `rec` survives (live).
- `^ArnoKG` killed.
- `^KG("labelset")` and `deg2p_exact_merged` emptied (only through the test_230 allowlist walk).
- Orphan routes emptied but not dropped by EraseAll.
- `rdf_reifications` actually non-empty before EraseAll in test_erase_graph :309.

### 4.8 Kept stores

| Store | Expected after `erase_graph` / `erase_all` | Tests | Untested |
|---|---|---|---|
| `embedding_quarantine` | kept / kept | **SRC only**: test_227_erase_plan :169, :178, :216 | No live test puts a row in the quarantine and erases. |
| Temporal-only settings `^IVG.TemporalStructural` | kept / removed | test_temporal_structural_optout_e2e :348 (live), :361; SRC test_temporal_structural_optout_architecture :70 | A setting of **another** graph across `erase_all`; the inventory lists it as scoped, so the coverage test is satisfied only textually (§2d). |
| FHIR registration `fhir_graphs` and watermarks | row kept, watermarks reset to 0 / same for all | test_231 :290, :310 (gated) | EraseAll's FHIR handling; `interp_version` reset to NULL (Eraser.cls:1163); the −29 retry path. |
| Multigraph mode `^IVG.GraphMode` | **cleared** for its graph only / cleared | test_234 :266, :278; SRC test_234_multigraph_sql :220 | A graph holding parallel edges; `erase_graph(None)` on the default graph's mode. |
| `^KG("labelset")` | kept / removed | only the test_230 :310 allowlist walk (EraseAll) | No test shows labelset **surviving** a graph erase. |
| Registry (`embedding_registry`) | the graph's claimed route rows deleted after the DROP; another graph's rows untouched / all deleted | test_227_erase_isolation :160 (B byte-identical), :209; test_227_scale :337; test_460_sec_audit :118 (a malformed row is ignored) | A registry row for a **legacy** table (`kg_NodeEmbeddings`) of the erased graph. EraseGraph does not delete it (Eraser.cls:292-293 runs only for claimed routes). The registry row kept after a **failed DROP** (Eraser.cls:294-298). |
| `^IVG.Ledger("rec")` and revisions | kept / kept | test_256 :262, :429; SRC test_eraser_inventory_coverage :110 | `rec` after `erase_all` (live). |
| ^NKG | kept when nothing interned is touched, otherwise dropped and marked "invalidated" / dropped, not marked | test_erase_nkg_kept_e2e, test_erase_graph_nkg_e2e, test_460_r268; SRC test_460_r268_erase_nkg_invalidation :51 | `^NKG("$meta","invalidated")` absent after EraseAll (live). |

### 4.9 Ledger statements

**Supported by:**
- Graph erase removes that graph's `^IVG.Ledger("tuple")` and keeps the default graph's (test_edgescan_ledger_erase :113).
- Erase alone keeps history and makes `verify()` diverge; erase + redact leaves no tenant A trace and is "equal" (test_256 :262, :267, :429).
- Strict mode refuses `delete_edge`/`delete_node`/`bulk_delete_nodes`/`drop_graph`/store deletes (test_ledger_us05 :98).
- The ledger guard runs before the store erase (unit test_delete_nodes_graph_scope :232).

**Untested:**
- `^IVG.Ledger("stmt", id)` removed by `EraseLedgerFor` (read directly).
- Statements of **another named graph** kept (only the default graph is checked).
- Per-edge ledger kills in EraseNodeIds/EraseEdges (`EraseEdgeRow`).
- The EraseAll ledger kills.
- Strict-mode refusal of `erase_graph`, `erase_all`, `delete_nodes_by_prefix`, `erase_bare_nodes` and `bulk_delete_adjacency`. `_ledger_check` exists at nodes_edges.py:1513/:1553/:1581 but is not in the us05 list.
- Rollback of ledger kills after a failure.

### 4.10 Routes (claimed, orphan, drop after commit, failed drop)

**Supported by:**
- Claimed routes are dropped: test_227_erase_isolation :141, :179 (B kept); test_227_scale :337.
- Registry rows for A go and B's stay: :160.
- Legacy tables are never dropped: :193; SRC test_227_erase_plan :155.
- EraseAll drops all claimed routes: :209; test_snapshot_routed_embeddings :115.
- An orphan `kg_emb_` is emptied of the graph's rows and the erase succeeds: test_227_orphan_route_erase :79.
- An orphan is not dropped: :107.
- A malformed registry `table_name` is never pasted into SQL: test_460_sec_audit :118.
- Routed vectors are removed by node erase: test_delete_node_named_graph :85, :120.
- Prevention of orphans: unit test_227_orphan_route :48, :68.

**Untested:**
- **Drop-after-commit ordering.** No test observes that the content is committed before the DROP, or that an erase inside a caller's transaction runs the DROP (DDL) while the caller's transaction is still open.
- **A failed DROP.** That case keeps the registry row and the table, now empty (Eraser.cls:287-298, :833-841). No injection exists.
- An orphan holding **another** graph's rows (must survive).
- Orphan or claimed **`kg_eemb_*` edge routes** in any erase.
- The registry naming a table that is already gone (−30 tolerated, Eraser.cls:173-177, :289).
- The engine's route-cache invalidation after erase (nodes_edges.py:1524) in a live write-after-erase.

### 4.11 Count and return value

**Supported by:**
- `erase_graph` = nodes + edges: 5 (test_erase_graph_nkg_e2e :174, :238); ≥2 (test_214 :19); 0 for an empty graph (test_erase_graph :255; test_214 :60).
- `erase_all`: 2nd call 0 (test_230 :310).
- `EraseEdges` = rdf_edges rows (0 for an adjacency-only edge, 1 otherwise; test_erase_graph_nkg_e2e :268, :287).
- `EraseNodeIds`/`EraseNodes` = nodes rows (test_erase_nkg_kept_e2e).
- Store `delete_nodes` = rows actually removed, missing → 0 (test_delete_nodes_graph_scoped :118).
- Prefix: 2 (:155), 1200 (r310 :56).
- `delete_node` True/False.
- `bulk_delete_nodes` `DeleteResult`.
- `bulk_delete_adjacency` = number of ids.
- `delete_edge` of a missing edge = True (r203 :77).
- `erase_bare_nodes` JSON fields.
- Units: test_delete_nodes_graph_scope :115-:214; test_nodes_edges_unit :464-:512.

**Untested:**
- The `erase_graph` count when edges are temporal (each `create_edge_temporal` adds a row).
- Whether the count includes NULL-spelled rows.
- The exact first `erase_all` count.
- The count under a failed post-commit DROP (it should still report the removed rows).

### 4.12 Atomicity, rollback and the caller's transaction

**Supported by:**
- A refused SQL delete at any of 9 tables × 3 ops leaves all 9 SQL tables unchanged (test_eraser_failures :92). The same holds for EraseAll (:104) and EraseEdges (:115).
- A refusal surfaces as `GraphWriteError` with nothing written (test_465 :82; test_463 :82, :95; r203).
- `_eraser_txn` fails closed on a refused START (unit r276 :84).
- An Eraser failure is not followed by an SQL fallback (unit :219).
- **The Eraser nests in a caller's transaction and never commits or rolls it back**, for `delete_node` (EraseNodeIds), `delete_edge` and Cypher DELETE (test_464 a-d).
- Node and reifier are deliberately **not** atomic (unit test_463_refused_pagerank_delete_node :103).
- Bare sweep: earlier batches stay committed (Eraser.cls:1207, test_temporal_bare_nodes).

**Untested:**
- **Global state after a failed erase.** `^KG` out/in/gen/degc, `^KG` prop/label, temporal data, `^IVG.Ledger`, ^NKG, `^KG("__version")` and AlgoCache are never read after an injected failure. test_eraser_failures reads SQL counts only (:94, :101).
- A failure **after** the last SQL statement (in RemoveGraph, the TemporalIndex kills or the ledger kills).
- A failure inside routed-table DELETEs or FHIR rows.
- `erase_graph`, `erase_all`, `delete_nodes_by_prefix`, store `delete_edges` and `erase_bare_nodes` **inside a caller's transaction**. test_464's write list has no erase entry point other than `delete_node`.
- A caller rollback after `erase_graph` that dropped a route table (DDL is not rolled back).
- **Every session-fixture test runs the Eraser on a separate native connection** (tests/conftest.py:715-775), so the "same connection" nesting that `_eraser_txn` relies on (iris_sql_store.py:1451-1472) is exercised only by test_464 and the scratch tests.

### 4.13 Search indexes after erase (BM25, IVF, PLAID, VecIdx/HNSW)

**Supported by:**
- Another graph's vector still answers `kg_KNN_VEC` (test_227_erase_isolation :97).
- `get_embedding` is None for an erased node (test_delete_nodes_graph_scoped :155).
- A FHIR sync delete removes the node from `kg_KNN_VEC` (test_231 :121; not the Eraser).
- PPR and neighbours stop seeing erased nodes (test_delete_nodes_graph_scoped :210).
- Traversal, PageRank, WCC, CDLP and ^NKG algorithms (236 token, 236 algo_cache, r268, r313).

**Untested:**
- **BM25 (`docs`/`kg_TXT`) results after an erase.**
- IVF, PLAID and VecIdx contents or results after an erase.
- The erased graph's vector being absent from `kg_KNN_VEC`.
- The HNSW/ANN index going with a dropped route.
- `test_460_status_index_inventory` uses `bm25`/`ivf`/`plaid_drop` only as cleanup.

### 4.14 Bypass paths (delete_edge, Cypher DELETE, raw SQL)

**Supported by:**
- **`delete_edge`** (plain SQL DELETE + ^KG, not the Eraser):
  - graph scope and NULL spelling (test_214_delete_edge_scoped; test_default_graph_spelling :108, :145; unit test_214_named_graphs :297-:314);
  - adjacency exactness (test_delete_adjacency; test_252 :50);
  - **leaves temporal timestamps** (test_254 :322);
  - refusal → `GraphWriteError` and rollback (r203, test_463_kg_write_failures_raise, test_nodes_edges_unit);
  - a missing edge → True;
  - nests in the caller's transaction (test_464).
- **Cypher DELETE**:
  - per-graph (r65 all_graphs :229, test_delete_graph_scope_e2e);
  - DETACH cascades to reifications (test_470_silent_writers);
  - refusal of a non-DETACH delete (r221);
  - ^KG updated with no sync (test_252_cypher_read_after_write);
  - ^NKG leftovers do not leak (r274, r286);
  - cache invalidation (r313);
  - detected as `unrecorded_writes` by the ledger (us05 :80).
- **Raw `%NOINDEX` delete**: detected only by `verify_graph` (test_verify_graph :186-:289).

**Untested:**
- `delete_edge` and Cypher DELETE effects on `kg_EdgeEmbeddings`/`kg_eemb_*`, ledger stmt/tuple, docs, routed node vectors, temporal subtrees and `^NKG` HLL/edgeCount.
- Cypher `DETACH DELETE` of a node that has a vector or doc.
- `delete_edge` in multigraph mode.

---

## 5. Assertions or texts that contradict Eraser.cls or the code today (brief)

No live assertion was found that directly contradicts Eraser.cls behaviour. These are the tensions found:

1. **Stale docstrings in tests/integration/test_erase_graph.py.**
   - :149-155 says `rdf_labels`/`rdf_props` "have no graph column — the inventory records that as a hole".
   - :310-315 says rdf_labels, rdf_props and rdf_reifications are the inventory's `graphScoped: 0` entries.
   - Today GraphStores.cls:39-40 declares labels and props scoped by `graph_id`, and Eraser.cls:130-136 deletes them by their own `graph_id`.
   - The assertions (:162-166, :321-323) still pass. The same stale claim appears in the product docstring at iris_vector_graph/_engine/nodes_edges.py:1568-1569.
2. **tests/integration/test_erase_graph.py:260-265.** The docstring says the "0" rejection must "survive the trip through the Eraser rather than being re-implemented at the facade". In fact `erase_graph` calls `validate_graph_name` first (nodes_edges.py:1514; _validate.py:38-40), so the test cannot detect whether `EraseGraph`'s own `ForIndex` refusal (Eraser.cls:49-51) works.
3. **tests/unit/test_eraser_inventory_coverage.py:56-82.** Its premise is "a graph-scoped store the Eraser does not name is content that outlives erasure". It accepts `^IVG.TemporalStructural`, which is scoped=1 at GraphStores.cls:110 yet deliberately kept by EraseGraph (Eraser.cls:245-247), because the name appears in a comment. The test cannot distinguish "erased per graph" from "mentioned".
4. **tests/integration/test_nodes_edges_deep.py:226.** `test_delete_edge_adjacency_warning_swallowed` expects `delete_edge` to return True when the patched `classMethodVoid` raises. tests/unit/test_463_kg_write_failures_raise.py:126 expects `GraphWriteError` and a rollback when the ^KG delete fails. The integration test likely passes only because, after `sync()`, the adjacency is index-maintained and `classMethodVoid` is never reached. Its name and comment describe behaviour the code no longer has. This concerns the Python `delete_edge`, not Eraser.cls.
5. **tests/e2e/test_464_api_typed_props_e2e.py:104-106.** A comment says Cypher DETACH DELETE leaves the `rdf_reifications` row ("open 4.6.3 defect"), while tests/e2e/test_470_silent_writers_e2e.py:166-205 asserts the row is removed. This concerns the Cypher path, not Eraser.cls.
6. **tests/integration/test_erase_graph.py:309-323.** `rdf_reifications` is asserted empty after `erase_all`, but `_seed` writes no reification, so that third check is vacuous rather than wrong.
