"""Write findings/audit/{01..06}.json for breadth lane A: one record per original finding of modules 01-06, plus the
new findings (F-C<module><nn>). Records are data below; a record backed by a live probe takes its observation and its
reproduced flag from live/breadth-a/results/<probe>.json, so the files regenerate after a rerun and can never claim
a reproduction the probe file does not hold.

    python experiment/playbook-completion/live/breadth-a/make_audit.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RES = HERE / "results"
OUT = ROOT / "findings" / "audit"
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"


def probe(name):
    p = RES / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def E(kind, ref):
    return {"kind": kind, "ref": ref}


# (id, title, intended, observed-if-no-probe, severity, confidence, remedy, gates, evidence, probe, live_run, fallback
#  disposition, notes)
F = []


def f(id, title, intended, observed, sev, conf, remedy, gates, evidence, probe_name=None, live_run=None,
      disposition="confirmed-source", notes="", model=None):
    F.append(dict(id=id, title=title, intended=intended, observed=observed, severity=sev, confidence=conf,
                  remedy=remedy, gates=gates, evidence=evidence, probe=probe_name, live_run=live_run,
                  fallback=disposition, notes=notes, model=model))


ORIG = "experiment/playbook-uplift/findings/{m}.md"

# ------------------------------------------------------------------ 01 install, schema
f("F-0101", "Legacy removal reports objects removed that may still be there",
  "`removed` is whether the object was dropped (specs/262-ivg-owned-sql-schema/data-model.md:50-60).",
  "remove_legacy_objects sets removed=True after DROP VIEW without reading _drop's result and for every later item of a "
  "class once the class was handled (iris_vector_graph/_engine/legacy.py:666-686).",
  "S3", "high", "Set `removed` from _drop's result for views and from the class delete's result for every item of that "
  "class; a unit case where DROP VIEW raises.", ["3.5-decoders", "3.8-findings-disposed"],
  [E("probe", "breadth-a-probe-local-0101-0601"), E("mc", "breadth-a-mc-ins_legacy-as-built"),
   E("control", "breadth-a-control-ins_legacy"), E("inspected", "iris_vector_graph/_engine/legacy.py:666-698")],
  probe_name="local_f0101", disposition="reproduced-test",
  notes="Reproduced by running the pin's remove_legacy_objects against a fake connection whose DROP VIEW and class "
        "delete fail (no IRIS: a 4.5.x legacy object set cannot be produced in AUDITA without installing objects). "
        "Model ins_legacy (INS-I7.6) violates as built and passes reviewed.")
f("F-0102", "Some setup failures are only logged, not put in the reply's warnings",
  "ADMIN_GUIDE (docs/ADMIN_GUIDE.md:428): `warnings` lists what you must act on, each also logged at WARNING.",
  "A base DDL failure other than already-exists/privilege is a log line (iris_vector_graph/_engine/schema.py:2506-2511); "
  "a failed ALTER ... emb VECTOR goes to report['failed'] and a log line (1666-1671); a failed ^KG bootstrap is a log "
  "line (2680-2681). Re-read at the pin.",
  "S2", "high", "Append each of these to status['warnings']; a unit test that makes one CREATE TABLE fail with a "
  "non-tolerated error.", ["3.5-decoders", "3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/_engine/schema.py:2506-2511"), E("inspected", "iris_vector_graph/_engine/schema.py:1664-1671"),
   E("inspected", "iris_vector_graph/_engine/schema.py:2680-2681"), E("mc", "breadth-a-mc-ins_setup-as-built")],
  notes="Not provoked live: making a CREATE TABLE fail in AUDITA needs a privilege or catalog change on the shared "
        "container (forbidden). Model ins_setup check ins_setup-as-built-F0102 (INS-B1.12) violates as built.")
f("F-0103", "The first-use check accepts a namespace with no schema record",
  "Spec 262 FR-006a (specs/262-ivg-owned-sql-schema/spec.md:245): refuse when the namespace has no schema record or "
  "lacks the 4.6.0 objects; HD-0101 (supported) separates an unreadable record (warn) from a readable mismatch (refuse).",
  None, "S3", "high", "Refuse when no record exists whatever the marker says (setup exempt), or amend FR-006a and the "
  "ADMIN_GUIDE to say the marker alone is accepted.", ["3.3-model-check", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-01-install"), E("mc", "breadth-a-mc-ins_setup-as-built"),
   E("inspected", "iris_vector_graph/schema_name.py:220-235")],
  probe_name="p0103_no_record_marker_accepted", live_run="breadth-a-live-01-install",
  notes="docs/KNOWN_ISSUES.md:787-809 accepts the behaviour; the spec and the known issue conflict (S3).")
f("F-0104", "Spec 240 says its design was not adopted, but it ships",
  "A spec's status line describes the shipped code.",
  "specs/240-alt-migration-as-data/spec.md:6 'Status: Exploratory (alternative implementation; not adopted)'; "
  "iris_vector_graph/migrations/docs_and_edge_vectors.py:53 imports iris_vector_graph.migrations.statements.",
  "S3", "high", "Update the spec status or remove the module.", ["3.1-coverage", "3.8-findings-disposed"],
  [E("inspected", "specs/240-alt-migration-as-data/spec.md:6"), E("inspected", "iris_vector_graph/migrations/docs_and_edge_vectors.py:53")])
f("F-0105", "The SQL files under sql/ describe an old schema and put objects outside the IVG Schema",
  "Spec 262 FR-001/FR-002 (spec.md:231-233): IVG creates nothing outside the IVG Schema; HD-0103 (assumption): packaged "
  "SQL loaded by the legacy deployer is reachable.",
  "sql/schema.sql:4-7 creates Graph_KG.nodes keyed by node_id alone; scripts/deploy_production.py:65 still runs "
  "sql/schema.sql and sql/operators_fixed.sql.", "S3", "high",
  "Per HD-0103: bring the legacy deployer to parity or retire it; mark the historical files.",
  ["3.1-coverage", "3.8-findings-disposed"],
  [E("inspected", "sql/schema.sql:4-7"), E("inspected", "scripts/deploy_production.py:63-66")],
  notes="Not run: executing the legacy deployer would create objects outside the IVG Schema in a shared container.")
f("F-0106", "Property keys of a label mix graphs",
  "CONTEXT.md:38-43 / SYS-I2: an all-graphs read is the union of each graph's own answer; content of one graph never "
  "answers about another.", None, "S2", "high",
  "Join rdf_labels to rdf_props on (graph_id, s); a test with one id in two graphs.", ["3.4-declared-reads", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-01-install"), E("inspected", "iris_vector_graph/_engine/schema.py:500-515")],
  probe_name="p0106_property_keys_cross_graph", live_run="breadth-a-live-01-install",
  notes="The docstring now says 'Not graph-scoped'; the join by id alone still lists a key no node with the label holds.")
f("F-0107", "Every setup runs an unqualified DROP INDEX",
  "Spec 262 FR-007 (spec.md:246-248): IVG's SQL names only IVG Schema objects, fully qualified.",
  "iris_vector_graph/schema.py:657 ('DROP INDEX idx_props_key_val') in ensure_indexes; no schema token, so the SchemaCursor "
  "rewrite leaves it unqualified.", "S3", "medium",
  "Qualify it (DROP INDEX idx_props_key_val ON <schema>.rdf_props) or drop the step.", ["3.4-ownership", "3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/schema.py:655-658"), E("live", "breadth-a-live-01-install")],
  probe_name="p0107_unqualified_drop_index", live_run="breadth-a-live-01-install",
  notes="The live observation lists every index of that name in AUDITA and the process's default schema; whether IRIS "
        "would drop an application's SQLUser index of that name was not tried (it would need a SQLUser object).")
f("F-0108", "The upstream test deploy does not follow setup's skip rules",
  "docs/ADMIN_GUIDE.md:353: IRIS Community is supported; initialize_schema skips classes whose %AI dependencies are absent.",
  "tests/conftest.py:215-262 compiles every class under iris_src/src and raises on any failure; setup skipped "
  "Graph.KG.MCPService/MCPToolSet/MCPTools in AUDITA ($RUN_DIR/setup/deploy-AUDITA.json).", "S4", "high",
  "Have the fixture call initialize_schema() or apply select_classes; a CI job on Community.", ["3.7-mutation", "3.8-findings-disposed"],
  [E("inspected", "tests/conftest.py:215-262"), E("live", "$RUN_DIR/setup/deploy-AUDITA.json")],
  notes="Test-infrastructure finding; the completion audit uses the pin's initialize_schema for deployment.")
f("F-0109", "The 4.0.0 upgrade does not follow the namespace's schema",
  "ADR-0016 (docs/adr/0016-one-ivg-schema-per-namespace.md:10-12): the schema name chosen at install is followed by everything.",
  "iris_vector_graph/migrations/upgrade.py:58 DEFAULT_SCHEMA = 'Graph_KG' and :140 schema default; ^IVG.Deploy('schema') "
  "is never read.", "S3", "high", "Read the record (refuse a mismatch) or document Graph_KG-only.", ["3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/migrations/upgrade.py:55-59"), E("inspected", "iris_vector_graph/migrations/upgrade.py:138-141")],
  notes="A live upgrade needs a 3.x fixture namespace; not available (blocked-access for a live run: the orchestrator owns namespaces).")
f("F-0110", "ADR-0016 lags the shipped design",
  "A decision record states the shipped mechanism and API names.",
  "docs/adr/0016-one-ivg-schema-per-namespace.md:5 'implementation pending: spec 262'; :26 names "
  "remove_legacy_sql_objects while the method is remove_legacy_objects (iris_vector_graph/_engine/admin.py:378).",
  "S3", "high", "Amend the ADR's status and consequences.", ["3.8-findings-disposed"],
  [E("inspected", "docs/adr/0016-one-ivg-schema-per-namespace.md:5"), E("inspected", "docs/adr/0016-one-ivg-schema-per-namespace.md:26"),
   E("inspected", "iris_vector_graph/_engine/admin.py:378")])
f("F-C0101", "An inline relationship property in a Cypher pattern fails on an edge with no properties",
  "openCypher: MATCH (x)-[r:R {k: 0}]->(y) and MATCH (x)-[r:R]->(y) WHERE r.k = 0 are equivalent; a missing property "
  "makes the filter false, not an error. create_edge's docstring: omitted properties leave the property null.",
  None, "S2", "high",
  "Guard Graph_KG.JSON_VALUE against an empty/NULL document (as CY_REL_PROP does), or emit the guarded function in "
  "_merge_prop_preds; a Cypher test over an edge written by create_edge without properties.",
  ["3.4-statements", "3.5-decoders", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-02-mode-off"), E("inspected", "iris_vector_graph/schema.py:2185"),
   E("inspected", "iris_vector_graph/cypher/translator.py:11197-11216")],
  probe_name="pC0101_inline_rel_prop_null_qualifiers", live_run="breadth-a-live-02-mode-off",
  notes="New. Graph_KG.JSON_VALUE (DDL at iris_vector_graph/schema.py:2185, created by setup: module 01) calls "
        "%FromJSON on NULL and then %Get on a non-object: <INVALID OREF>, SQLCODE -149. Inline MATCH and inline DELETE "
        "fail; the WHERE form answers []. Any edge written without properties (create_edge, store_edge, bulk paths) "
        "is a trigger. The Cypher translation belongs to module 08; reported here because the failing object is setup's DDL.")

# ------------------------------------------------------------------ 02 graph identity
f("F-0201", "A graph whose mode is off can hold two edges of one triple",
  "Spec 234 FR-002: with the mode off a triple never gets a second edge; GID-I4.10.", None, "S2", "high",
  "Guard the single-edge writers on the triple whatever its ekey, or refuse mode off while an edge has a non-zero ekey "
  "(or renumber the lone edge to 0).", ["3.3-model-check", "3.3a-writesets", "3.6-keys", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-02-mode-off"), E("mc", "breadth-a-mc-gid_mode-as-built"), E("mc", "breadth-a-mc-gid_mode-reviewed"),
   E("control", "breadth-a-control-gid_mode")],
  probe_name="p0201_mode_off_lone_ekey1", live_run="breadth-a-live-02-mode-off",
  notes="Impact reproduced too: after a per-edge delete of the ekey-1 row the surviving ekey-0 row has no ^KG out leaf "
        "and verify_graph reports 1 missing out and 1 missing in entry.")
f("F-0202", "The name check is not run at every entry that takes a graph name",
  "ADR-0003 (docs/adr/0003-two-graph-key-derivations.md:119-121): the validator rejects the name '0'.", None, "S2", "high",
  "Call validate_graph_name at every entry (create_node, store_node, store_edge, bulk paths, BulkLoader, USE GRAPH) and "
  "write the canonical name.", ["3.5-decoders", "5c-refusals", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-02-identity"), E("inspected", "iris_vector_graph/_engine/nodes_edges.py:968-1015")],
  probe_name="p0202_reserved_name_writers", live_run="breadth-a-live-02-identity",
  notes="create_node and store_node wrote rows under graph '0'; node_count and delete_node then refuse the name (the rows "
        "cannot be read or removed through the API that wrote them); store_edge into '0' fails late with the server's "
        "ERROR #5001 inside a SQLCODE -400.")
f("F-0203", "The Python name check refuses fewer control characters than the server check",
  "CHANGELOG.md:4618-4620: the Python mirror exists to refuse what the server refuses, before the round trip.",
  None, "S4", "high", "Refuse unicodedata category Cc (0-31, 127-159) in _validate.validate_graph_name.",
  ["5c-refusals", "3.8-findings-disposed"], [E("live", "breadth-a-live-02-identity")],
  probe_name="p0203_c1_control_char", live_run="breadth-a-live-02-identity",
  notes="Also settles premise P-0202 live: $ZStrip(,'*C') covers U+0085.")
f("F-0204", "The graph check reports a multigraph's parallel edges as missing adjacency",
  "Spec 234 SC-005: zero drift on a multigraph after random creates and deletes.", None, "S2", "high",
  "Compare rows per (s,p,o) with the keyed '#' count.", ["3.5-decoders", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-02-identity")], probe_name="p0204_verify_parallel", live_run="breadth-a-live-02-identity",
  notes="Same defect as F-0403. Three parallel edges, keyed count 3: verify reports ok 0 with 2 missing out and in entries.")
f("F-0205", "Direct edge writes, the ledger and Bolt do not track parallel edges, and the user docs do not say so",
  "Spec 234 FR-007/FR-012/FR-013 (edge_id identity, ambiguous_tuple refusal); its status line says US4 not done.",
  "Bolt gives a relationship id hash(f'{s}-{type}-{o}') (iris_vector_graph/bolt_server.py:770); LedgerApply.FindEdge "
  "takes the first row of the triple (iris_src/src/Graph/KG/LedgerApply.cls:144-157). Re-read at the pin.",
  "S2", "medium", "Implement FR-007/012/013 or document each limit.", ["3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/bolt_server.py:770"), E("inspected", "iris_src/src/Graph/KG/LedgerApply.cls:144-157")],
  notes="Not reproduced live (Bolt server not started in the audit; ledger-on-multigraph left to the ledger lane).")
f("F-0206", "Some Python readers join one graph's ids with another graph's data",
  "USER_GUIDE.md:466-467 (graph= omitted means the default graph); HD-0201 (assumption): no join of ids from one scope "
  "to records of another.", None, "S2", "high",
  "Hydrate each id from its own graph; give _filter_edges_by_properties and set_edge_weight a graph.",
  ["3.4-declared-reads", "3.8-findings-disposed"], [E("live", "breadth-a-live-02-identity")],
  probe_name="p0206_cross_graph_hydration", live_run="breadth-a-live-02-identity",
  notes="get_nodes_by_label(L) answered the default graph's node (labels ['Other']) for an id labelled L only in a named graph.")
f("F-0207", "Turning the mode off races a write that adds a parallel edge",
  "Spec 234 FR-002 (the refusal exists to keep a mode-off graph single-edge).",
  "GraphMode.Set counts parallel triples with one SQL query then kills the setting, no lock, no transaction "
  "(iris_src/src/Graph/KG/GraphMode.cls:26-45).", "S2", "high",
  "Hold a lock the multigraph writers also take across the count and the kill.",
  ["3.3-model-check", "3.5-lockplans", "3.8-findings-disposed"],
  [E("mc", "breadth-a-mc-gid_mode-as-built"), E("mc", "breadth-a-mc-gid_mode-reviewed"), E("control", "breadth-a-control-gid_mode"),
   E("inspected", "iris_src/src/Graph/KG/GraphMode.cls:26-61")], disposition="reproduced-model",
  notes="Check gid_mode-as-built-F0207 (GID-I4.10) gives the race trace; the reviewed design with the shared lock passes "
        "exhaustively; control gid_mode-control-writers-unlocked is caught. Not provoked live: the window lies inside one "
        "class method.")
f("F-0208", "An engine keeps a graph's mode forever, so another engine's change is not seen",
  "Spec 234 FR-002; GID-I4.10.", None, "S2", "high",
  "Read the mode per statement, expire the cache, or refuse a keyed insert server-side in a mode-off graph.",
  ["3.3-model-check", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-02-identity"), E("mc", "breadth-a-mc-gid_mode-as-built")],
  probe_name="p0208_stale_mode_cache", live_run="breadth-a-live-02-identity")
f("F-0209", "An all-graphs walk can miss graphs",
  "An all-graphs read is the union over every graph (CONTEXT.md:38-43).",
  "_edge_graphs stops after 10,000 graphs and answers [] on any error (iris_vector_graph/_engine/query.py:2408-2420).",
  "S4", "high", "List without a cap and raise on failure.", ["3.6-capacity", "3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/_engine/query.py:2408-2420")],
  notes="Not run: needs 10,001 graphs with edges.")

# ------------------------------------------------------------------ 03 writes
f("F-0301", "The bulk loader writes while ledger strict mode is on",
  "HD-0301 (supported): spec 213's API contract excludes the bulk loader and raw SQL from strict mode; the USER_GUIDE "
  "(docs/USER_GUIDE.md:1107-1121) says strict refuses create_node, create_edge 'and the other methods'.", None, "S3", "high",
  "State the exclusion in the USER_GUIDE next to strict mode (the contract is supported as is).",
  ["3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-ledger"), E("inspected", "iris_vector_graph/bulk_loader.py:252-272")],
  probe_name="p0301_bulk_loader_under_strict", live_run="breadth-a-live-ledger",
  notes="Behaviour matches the supported contract (HD-0301); the defect is the USER_GUIDE wording. Severity lowered to S3 accordingly.")
f("F-0302", "Strict mode reaches another engine only after its five-second cache expires",
  "USER_GUIDE.md:1107-1121 states refusal without a window; HD-1103 (supported): strict mode is a client-side guard "
  "whose cache behaviour must be inventoried.", None, "S3", "high",
  "Document the window and the fail-open rule next to set_strict, or check on the server.",
  ["3.5-lockplans", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-ledger"), E("tested", "tests/unit/test_ledger_guard.py::test_cache_honours_ttl_and_refresh"),
   E("inspected", "iris_vector_graph/ledger/guard.py:20-59")],
  probe_name="p0302_strict_cache_window", live_run="breadth-a-live-ledger")
f("F-0303", "A direct edge delete leaves the ledger's live link for the edge",
  "CONTEXT.md:198-205 (no live statement outlives its content); INV-stmt (semantics/writesets.json).", None, "S2", "high",
  "Route delete_edge (and the Cypher relationship delete) through Eraser.EraseEdges.",
  ["3.3-model-check", "3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-ledger-stmt"), E("mc", "breadth-a-mc-wrt_ledger_stmt-as-built"), E("mc", "breadth-a-mc-wrt_ledger_stmt-reviewed"),
   E("control", "breadth-a-control-wrt_ledger_stmt")],
  probe_name="p0303b_direct_delete_keeps_stmt", live_run="breadth-a-live-ledger-stmt",
  notes="The first live attempt (breadth-a-live-ledger, p0303) read ^IVG.Ledger('tuple') with graph key 0 instead of "
        "GraphKey.ForLedger('') ($Char(1)) and decided nothing; p0303b corrects the key. A ledger create of the same "
        "triple after the direct delete allocated a new statement (p0303: 1 then 2), so the reuse happens through the "
        "tuple index for a directly re-created edge, as the finding says.")
f("F-0304", "Storing an edge over a marked edge does not take the edge over",
  "ADR-0009 (CONTEXT.md:66-73) and HD-0302 (supported): an explicit structural create clears the temporal mark; a "
  "temporal-backed row must not delete an explicitly written edge.", None, "S1", "high",
  "Run the adopt step after store_edge's swallowed duplicate.",
  ["3.3-model-check", "3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-05-temporal"), E("mc", "breadth-a-mc-tmp_mark-as-built"), E("mc", "breadth-a-mc-tmp_mark-reviewed"),
   E("control", "breadth-a-control-tmp_mark")],
  probe_name="p0304_store_edge_does_not_adopt", live_run="breadth-a-live-05-temporal",
  notes="Discriminating control in the same probe: over the same marked row, create_edge adopts (qualifiers NULL) and its "
        "edge survives the last temporal delete; store_edge keeps {\"temporal\":true} and its edge is deleted (data loss).")
f("F-0305", "A bulk write larger than one chunk is not one transaction on the server-loader path",
  "USER_GUIDE.md:238-241: each bulk write is a transaction of its own.", None, "S2", "high",
  "Run the loader on the cursor's own process inside the WriteTxn (txn.native()), or one loader call per transaction.",
  ["3.3-model-check", "3.7-trace-replay", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-03-bulk-atomicity"), E("trace", "breadth-a-live-03-bulk-atomicity"),
   E("live", "breadth-a-live-03-bulk-killed-client"), E("mc", "breadth-a-mc-wrt_bulk_atomic-as-built"),
   E("mc", "breadth-a-mc-wrt_bulk_atomic-reviewed"), E("control", "breadth-a-control-wrt_bulk_atomic")],
  probe_name="p0305_bulk_chunks_not_one_transaction", live_run="breadth-a-live-03-bulk-atomicity",
  notes="from_connect engine: 1,001 of 2,000 nodes committed and visible to a READ COMMITTED reader while the call was "
        "stalled in chunk 2; the journal shows two committed node transactions by the engine's Native API process, none "
        "by its cursor process. A client killed inside chunk 2 left exactly chunk 1 committed (breadth-a-live-03-bulk-killed-client).")
f("F-0306", "create_node answers False for a write IRIS refuses as invalid",
  "create_node docstring: False means the node already exists; 4.6.0 R203: a refusal is not 'already there'.", None,
  "S4", "high", "Drop the 'validation failed' match or width-check the graph name.", ["3.5-decoders", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-03-writes")], probe_name="p0306_long_graph_name_reads_as_duplicate", live_run="breadth-a-live-03-writes",
  notes="Also settles premise P-0307 live (a 300-character graph name).")
f("F-0307", "The server path of bulk_ingest_edges skips a refused edge without an error",
  "4.7.0 row 14: every bulk writer raises for a refused row; the SQL path of bulk_ingest_edges raises GraphWriteError.",
  None, "S2", "high", "Width-check in Python before sending; make the loader throw on a refused row.",
  ["5c-refusals", "3.8-findings-disposed"], [E("live", "breadth-a-live-03-writes")],
  probe_name="p0307_ingest_drops_refused_edge", live_run="breadth-a-live-03-writes")
f("F-0308", "The bulk loader stores a NaN or infinite edge property as JSON no reader accepts",
  "4.6.0 R307: create_edge and store_edge refuse NaN/Infinity because IRIS JSON functions then fail every relationship read.",
  None, "S2", "high", "Use _qualifiers_json (allow_nan=False) in the loader.", ["5c-refusals", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-03-writes")], probe_name="p0308_loader_nan_breaks_reads", live_run="breadth-a-live-03-writes",
  notes="create_edge refused the same value (ValueError); the Cypher read of the loaded graph failed with SQLCODE -149 in CY_REL_PROP.")
f("F-0309", "The bulk loader rebuilds the indexes of Graph_KG whatever schema it loaded",
  "ADR-0016 / CONTEXT.md:20-24: a namespace's IVG schema may be other than Graph_KG.",
  "rebuild_all_indices calls %BuildIndices on the fixed classes Graph.KG.rdfedges/rdflabels/rdfprops/nodes "
  "(iris_vector_graph/bulk_loader.py:495).", "S2", "high", "Derive the class names from the schema.",
  ["3.8-findings-disposed"], [E("inspected", "iris_vector_graph/bulk_loader.py:493-496")],
  notes="Live check blocked-access: needs a namespace whose IVG Schema is not Graph_KG (namespaces are the orchestrator's). "
        "Related observation (breadth-a-live-bulkloader-noindex): edges BulkLoader.load_edges wrote with its default "
        "%NOINDEX and no rebuild_all_indices were invisible to indexed reads (0 vs 2 rows) and survived erase_graph of "
        "their graph; reported to the erasure lane, not counted here (the loader's docstring requires the rebuild).")
f("F-C0301", "create_edge's adoption of a marked row runs after its transaction commits",
  "create_edge docstring/ADR-0009: an explicit create over a marked row adopts it in the same write.",
  "When the guarded insert finds the triple, txn.commit() runs first and _adopt_temporal_row's UPDATE runs afterwards as "
  "its own statement (iris_vector_graph/_engine/nodes_edges.py:1236-1252); a temporal delete in between removes the "
  "marked row and the call answers False (duplicate) with no edge.", "S4", "medium",
  "Adopt inside the same transaction as the guarded insert.", ["3.5-lockplans", "3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/_engine/nodes_edges.py:1236-1252")],
  notes="New, from the footprint sub-lane's static reading; confirmed in source, not provoked (a narrow interleaving).")

# ------------------------------------------------------------------ 04 adjacency
f("F-0401", "A killed source generation can let an in-flight reader store a wrong out-degree",
  "ADJ-I5.9 / ADJ-I5.9.1; HD-0401 (assumption): invalidation never makes an old degree-cache value valid again.",
  "Adj.Degree's four steps (iris_src/src/Graph/KG/Adj.cls:51-90) against RemoveSource/RemoveGraph/RemoveAll killing "
  "^KG('gen') (Adjacency.cls:376-377, 437-438, 461-462) and a rolled-back erase.", "S2", "high",
  "Per HD-0401: step the generation (or a graph epoch) and never kill it; the model also needs the step before the write "
  "(see F-C0401).", ["3.3-model-check", "3.3-refinement", "3.3a-writesets", "3.8-findings-disposed"],
  [E("mc", "breadth-a-mc-adj_degree-as-built"), E("mc", "breadth-a-mc-adj_degree-reviewed"), E("control", "breadth-a-control-adj_degree"),
   E("inspected", "iris_src/src/Graph/KG/Adj.cls:51-90")], disposition="reproduced-model",
  notes="adj_degree-as-built-F0401-erase gives the finding's trace; the refinement audit against L1 'degree = committed "
        "out count' fails as built and passes for the reviewed design. Live provocation is unrepresentable with the "
        "public surface: the window lies between the probe and the count inside one Adj.Degree call.")
f("F-0402", "A rebuilt store or cached answer can stay current after the write it read is rolled back",
  "AlgoCache.cls:5-7 ('never wrongly fresh'); ADR-0012:23-26 names the case unsafe; ADJ-I7.3 / ADJ-I11.2.", None, "S2", "high",
  "Probe the writer lock exclusively before computing and store only if the probe held and the token did not move, AND "
  "step the token before the adjacency write: the model shows the probe alone leaves a writer-stopped-mid-write window "
  "(adj_token-probe-writer-window).", ["3.3-model-check", "3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-04-adjacency"), E("mc", "breadth-a-mc-adj_token-as-built"), E("mc", "breadth-a-mc-adj_token-reviewed"),
   E("mc", "breadth-a-mc-adj_token-probe-writer-window"), E("control", "breadth-a-control-adj_token")],
  probe_name="p0402_rolled_back_edge_served_current", live_run="breadth-a-live-04-adjacency",
  notes="Live: token 114 -> 115 by the open write, WCC computed and cached under 115, writer rolled back (row and out "
        "entry gone), token stays 115, a fresh engine's kg_WCC was a cache hit joining the rolled-back edge's endpoints.")
f("F-0403", "verify_graph reports drift on a graph with parallel edges whose index matches its rows",
  "Spec 234 SC-005 and spec.md:78-80.", None, "S2", "high", "Count rows per triple against the '#' count.",
  ["3.5-decoders", "3.8-findings-disposed"], [E("live", "breadth-a-live-02-identity")],
  probe_name="p0204_verify_parallel", live_run="breadth-a-live-02-identity", notes="Same defect as F-0204.")
f("F-0404", "Snapshot restore writes the adjacency index outside the one writer where the row hook is not declared",
  "ADR-0011 (one writer); ADR-0008:46 and spec 252 FR-016 (ImportGlobals restores rows only).",
  "_import_global_from_ndjson sets ^KG out/in over the Native API when the namespace is not indexed "
  "(iris_vector_graph/_engine/snapshot.py:1656-1692).", "S3", "high",
  "Route the restore through Graph.KG.Adjacency or rebuild from rows; extend the single-writer guard to Python.",
  ["3.4-ownership", "3.8-findings-disposed"], [E("inspected", "iris_vector_graph/_engine/snapshot.py:1656-1692")],
  notes="AUDITA declares the row hook, so the path is unreachable there; a non-indexed namespace is not available.")
f("F-0405", "Some weight refreshes do not move the graph-version token",
  "CONTEXT.md:116-119: every write path able to change an algorithm's answer moves the token.", None, "S4", "high",
  "Step the token whenever a stored weight changes.", ["3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-04-adjacency")], probe_name="p0405_weight_refresh_token", live_run="breadth-a-live-04-adjacency")
f("F-0406", "Clearing the degree cache alone gives zeros while the warm stamp holds",
  "ADR-0012:17: the cache is derived; kill it and every answer is still right.", None, "S2", "high",
  "Make AllWarm require an entry, or document killing ^KG('degw') with ^KG('degc').", ["3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-04-adjacency")], probe_name="p0406_degc_kill_under_warm_stamp", live_run="breadth-a-live-04-adjacency")
f("F-0407", "Reweight takes no writer lock and moves no generation, against ADR-0012 and spec 252 FR-004",
  "ADR-0012:31 and spec 252 FR-004 as written.", None, "S3", "high",
  "Amend ADR-0012 and FR-004 to 'every write that changes the set of out entries'.", ["3.5-lockplans", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-04-adjacency"), E("tested", "tests/e2e/test_degree_cache_live.py::test_reweight_does_not_move_the_generation")],
  probe_name="p0407_reweight_generation", live_run="breadth-a-live-04-adjacency",
  notes="The behaviour is deliberate and harmless for counts; the documents over-state the rule.")
f("F-0408", "Comments and docs still describe adjacency behaviour that changed",
  "Comments and ADRs describe the shipped behaviour.",
  "EdgeScan.cls:149 'graph=\"\" = default graph'; admin.py:854-861 drop_graph text; ADR-0010 line 5 'implementation pending'.",
  "S4", "high", "Correct the four texts.", ["3.8-findings-disposed"],
  [E("inspected", "iris_src/src/Graph/KG/EdgeScan.cls:149"), E("inspected", "iris_vector_graph/_engine/admin.py:854-861")])
f("F-0409", "A failed adjacency rebuild inside a caller's transaction rolls back the caller's work",
  "CHANGELOG 4.6.4 (CHANGELOG.md:410-424): an IVG write never commits or rolls back a transaction its caller opened.",
  None, "S1", "high", "Roll back to the level found, or refuse sync() inside a caller transaction.",
  ["3.3-model-check", "3.5-lockplans", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-04-adjacency"), E("mc", "breadth-a-mc-adj_rebuild_txn-as-built"),
   E("mc", "breadth-a-mc-adj_rebuild_txn-reviewed"), E("control", "breadth-a-control-adj_rebuild_txn")],
  probe_name="p0409_failed_sync_rolls_back_caller", live_run="breadth-a-live-04-adjacency",
  notes="Precondition: the engine's Native API handle shares the caller's process (an engine built on the caller's DB-API "
        "connection, as here); on a from_connect engine BuildKG runs in another process.")
f("F-C0401", "A writer stopped between its adjacency write and its generation step lets a reader cache a count that includes the undone edge",
  "ADJ-I5.9 / ADR-0012: a cached degree carrying the current generation equals the committed count.",
  "Adjacency.Put writes ^KG('out')/('in') and only then $Increments ^KG('gen') (iris_src/src/Graph/KG/Adjacency.cls:87-89); "
  "Adj.Degree's probe can precede the writer's lock and its count can follow the out write "
  "(iris_src/src/Graph/KG/Adj.cls:68-80). A writer process stopped between the two (rolled back by IRIS, P-0001) leaves the "
  "generation unchanged, so the reader's store of the dirty count stays current.", "S2", "medium",
  "Step the generation before the out write (the reviewed adj_degree design), as well as never killing it (HD-0401).",
  ["3.3-model-check", "3.8-findings-disposed"],
  [E("mc", "breadth-a-mc-adj_degree-hd0401-writer-window"), E("inspected", "iris_src/src/Graph/KG/Adjacency.cls:80-93"),
   E("inspected", "iris_src/src/Graph/KG/Adj.cls:51-90")], disposition="reproduced-model",
  notes="New, from the model sub-lane. The same window exists as built (Put's order is unchanged in HD-0401's fix). Not "
        "provoked live: needs a process stopped between two statements of one class method.")
f("F-C0402", "Two adjacency rebuilds can run at once",
  "HD-0402 (assumption): at most one publishing rebuild per adjacency structure; the ADMIN_GUIDE names a single rebuild.",
  "Adjacency.BeginRebuild takes ^IVG.AdjW in shared mode (iris_src/src/Graph/KG/Adjacency.cls:814-822), which a second "
  "rebuild's shared request does not conflict with (P-0403).", "S2", "medium",
  "Take the rebuild lock exclusively (or a separate exclusive rebuild lock) and return busy to a second caller.",
  ["3.3-model-check", "3.5-lockplans", "3.8-findings-disposed"],
  [E("mc", "breadth-a-mc-adj_rebuild_txn-as-built"), E("mc", "breadth-a-mc-adj_rebuild_txn-reviewed"),
   E("inspected", "iris_src/src/Graph/KG/Adjacency.cls:809-822")], disposition="reproduced-model",
  notes="New. Check adj_rebuild_txn-concurrent-as-built-HD0402 violates ADJ-Q8.10; the reviewed exclusive design passes; "
        "control early-release is caught. Intent rests on HD-0402, an assumption.")

# ------------------------------------------------------------------ 05 temporal
f("F-0501", "An update-mode write counts its edge again in the bucket aggregate",
  "CONTEXT.md:173-177 (an upsert replaces the edge); the docstring says aggregates keep the original value.", None, "S2", "high",
  "Make update subtract the old weight and not count, or rebuild the bucket.", ["3.3-model-check", "3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-05-temporal"), E("mc", "breadth-a-mc-tmp_bucket-as-built"), E("mc", "breadth-a-mc-tmp_bucket-reviewed"),
   E("control", "breadth-a-control-tmp_bucket")], probe_name="p0501_update_double_counts_bucket", live_run="breadth-a-live-05-temporal",
  notes="Whole-bucket count 2 and sum 6.0 for one edge of weight 5.0; a window cutting the bucket answers 1; after the "
        "delete the bucket counter stays 1. Neither the docstring (original value kept) nor CONTEXT holds.")
f("F-0502", "A temporal write with no time lands at epoch 0, not at the current time",
  "InsertEdge's own rule: a missing time is now (TemporalIndex.cls:51).", None, "S2", "high",
  "Send '' for a missing timestamp; stop treating an explicit 0 as missing in BulkInsertCounts.", ["3.5-decoders", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-05-temporal")], probe_name="p0502_missing_time_is_epoch_zero", live_run="breadth-a-live-05-temporal")
f("F-0503", "A temporal write can create node rows that the ledger never records",
  "INV-replay / RPL-B3: with every write made through the ledger, replay equals the store; HD-0501 (assumption): implicitly "
  "created endpoints are real effects to record or give derived provenance.", None, "S2", "high",
  "Per HD-0501: record the endpoint rows a governed temporal op creates, or mark them derived and exclude them from verify.",
  ["3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-ledger"), E("inspected", "iris_src/src/Graph/KG/Adjacency.cls:575-603")],
  probe_name="p0503_changeset_temporal_endpoint", live_run="breadth-a-live-ledger")
f("F-0504", "Purges and the row drop delete node rows without the strict-mode check or a record",
  "USER_GUIDE.md:1107-1121 (strict refuses structural writes not made through the ledger); erase_bare_nodes calls the guard "
  "(iris_vector_graph/stores/iris_sql_store.py:2823-2825).", None, "S2", "high",
  "Guard node retirement as erase_bare_nodes is guarded, or skip ledger-known nodes.", ["3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-ledger"), E("inspected", "iris_vector_graph/_engine/temporal.py:623-641")],
  probe_name="p0504_purge_retires_nodes_under_strict", live_run="breadth-a-live-ledger")
f("F-0505", "The marker test differs between the deleters and the ledger",
  "ADR-0009 / HD-0302: an explicitly written edge (no JSON-true mark) survives the temporal side; LedgerGenesis treats "
  "temporal 1 as an ordinary qualifier (LedgerGenesis.cls:62-75).", None, "S1", "high",
  "One shared predicate (JSON boolean true).", ["3.3-model-check", "3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-05-temporal"), E("mc", "breadth-a-mc-tmp_mark-as-built"), E("mc", "breadth-a-mc-tmp_mark-reviewed")],
  probe_name="p0505_marker_predicate", live_run="breadth-a-live-05-temporal",
  notes="An explicit create_edge with qualifiers {\"temporal\": 1} was deleted by the last temporal delete on its triple (data loss).")
f("F-0506", "Without the adjacency index, the Python mirror writes an unmarked row for any predicate",
  "ADR-0015 (an opted-out predicate writes nothing else); ADR-0009 (the asserted row is marked).",
  "create_edge_temporal / bulk_create_edges_temporal insert an unmarked rdf_edges row when not _adjacency_indexed "
  "(iris_vector_graph/_engine/temporal.py:309-331, 453-475).", "S2", "high", "Write the marker and honour the opt-out registry, "
  "or drop the mirror.", ["3.3a-writesets", "3.8-findings-disposed"], [E("inspected", "iris_vector_graph/_engine/temporal.py:309-331")],
  notes="AUDITA declares the adjacency index, so the mirror path is unreachable there (a non-indexed namespace is not available).")
f("F-0507", "TemporalIndex.Purge wipes every graph's temporal index and leaves the marked rows",
  "ADR-0009 amendment: the marked row goes when the triple's last timestamp goes, in every graph; TMP-B9.13.", None, "S2", "high",
  "Retract marked rows in Purge (or remove it) and fix the create_edge_temporal docstring that advises calling it.",
  ["3.3-model-check", "3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-05-purge"), E("mc", "breadth-a-mc-tmp_mark-as-built"), E("mc", "breadth-a-mc-tmp_mark-reviewed")],
  probe_name="p0507_purge_wipes_all_graphs", live_run="breadth-a-live-05-purge",
  notes="Both graphs' tout gone; both marked rows and ^KG out stay; purge_before afterwards removes 0.")
f("F-0508", "find_burst_nodes accepts a predicate and ignores it",
  "Args docstring: 'predicate: Filter to edges with this predicate' (temporal.py find_burst_nodes).", None, "S3", "high",
  "Remove the argument or count per predicate; make the docstring agree (its first paragraph now says it filters nothing).",
  ["3.5-decoders", "3.8-findings-disposed"], [E("live", "breadth-a-live-05-temporal")],
  probe_name="p0508_burst_predicate_ignored", live_run="breadth-a-live-05-temporal")
f("F-0509", "InternLabelSet's canonical form is not valid JSON for some inputs",
  "Spec 204 FR-012: the canonical form is JSON.", None, "S3", "high", "Build the form with JSON escaping; catch the parse error.",
  ["3.5-decoders", "3.8-findings-disposed"], [E("live", "breadth-a-live-05-temporal")],
  probe_name="p0509_label_set_json", live_run="breadth-a-live-05-temporal")
f("F-0510", "The millisecond index computes 'now' in seconds",
  "TemporalIndexMS: TSUNIT='ms' (TemporalIndexMS.cls:7-9).", None, "S2", "high", "Scale now by 1000 when TSUNIT='ms'.",
  ["3.5-decoders", "3.8-findings-disposed"], [E("live", "breadth-a-live-05-temporal")],
  probe_name="p0510_ms_index_now_in_seconds", live_run="breadth-a-live-05-temporal")
f("F-0511", "A changeset's insert-mode temporal op is recorded even when it collides",
  "Changeset.create_temporal_edge docstring: insert fails if the key exists (iris_vector_graph/ledger/changeset.py:334-335).",
  None, "S3", "high", "Return the collision from WriteStores to LedgerApply; refuse or skip the record (HD-0502).",
  ["3.3a-writesets", "3.8-findings-disposed"], [E("live", "breadth-a-live-ledger")],
  probe_name="p0511_insert_collision_recorded", live_run="breadth-a-live-ledger")
f("F-0512", "The batch field that suppresses the reverse index is not the one spec 204 names",
  "Spec 204 FR-009 (specs/204-temporal-index-gaps/spec.md:185): suppress_reverse.", None, "S3", "high",
  "Accept both names or amend the spec.", ["3.5-decoders", "3.8-findings-disposed"], [E("live", "breadth-a-live-05-temporal")],
  probe_name="p0512_suppress_reverse_field", live_run="breadth-a-live-05-temporal")
f("F-0513", "Temporal writes validate their input on one path only",
  "TemporalEdgeInput (iris_vector_graph/_validate.py:207-227): timestamp >= 0, weight >= 0.", None, "S3", "high",
  "Validate every edge on every path.", ["5c-refusals", "3.8-findings-disposed"], [E("live", "breadth-a-live-05-purge")],
  probe_name="p0513_validation_paths", live_run="breadth-a-live-05-purge",
  notes="Weight -1 refused with a timestamp; stored without a timestamp and on the batch path.")
f("F-0514", "The Python structural-row migration cannot read a large graph",
  "The migration backfills every temporal triple of a graph.",
  "_temporal_triples reads with get_edges_in_window(start=0, end=_ALL_TIME_END) "
  "(iris_vector_graph/migrations/temporal_structural_rows.py:55-63), whose docstring states a ~35 k-edge cap that raises "
  "TemporalWindowError (iris_vector_graph/_engine/temporal.py:500-505).", "S2", "high",
  "Read with iter_edges_in_window, or call backfill_temporal_structural_rows.", ["3.6-capacity", "3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/migrations/temporal_structural_rows.py:55-63"), E("inspected", "iris_vector_graph/_engine/temporal.py:500-505")],
  notes="Not run live (36k temporal edges in AUDITA under the shared IRIS lock was not cheap); the cap is the product's own docstring.")
f("F-C0501", "A refused temporal write raises but leaves the edge in the temporal index",
  "create_edge_temporal docstring: 'A write IRIS refuses raises GraphWriteError and writes nothing'.", None, "S2", "high",
  "Open a transaction in InsertEdge/WriteStores (or assert the row first) so a refusal takes back tout/tin/bucket/tagg.",
  ["3.3a-writesets", "5c-refusals", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-05-partial"), E("inspected", "iris_src/src/Graph/KG/TemporalIndex.cls:80-111")],
  probe_name="pC0501_refused_temporal_write_is_partial", live_run="breadth-a-live-05-partial",
  notes="New, from the footprint sub-lane's static reading (WriteStores has no TSTART and writes the temporal stores before "
        "AssertTemporalRow); provoked with a 140-character predicate the structural row refuses.")

# ------------------------------------------------------------------ 06 vectors
f("F-0601", "A registry read that fails for any reason lets a vector write through unchecked",
  "ADR-0006 (refusable before it happens); FR-014 (enforcement is not opt-in).", None, "S2", "high",
  "Raise from get_embedding_identity (and the inventory/quarantine reads) unless the registry is absent.",
  ["3.5-decoders", "3.8-findings-disposed"],
  [E("probe", "breadth-a-probe-local-0101-0601"), E("inspected", "iris_vector_graph/_engine/schema.py:1033-1061")],
  probe_name="local_f0601", disposition="reproduced-test",
  notes="Pin code against a fake cursor raising SQLCODE -99 on the registry read: get_embedding_identity -> None and "
        "enforce_embedding_identity returns None (write proceeds). Not provoked live: revoking SELECT in AUDITA changes "
        "server security settings (forbidden).")
f("F-0602", "Vectors from one model can be stored under another model's identity",
  "ADR-0006: a vector's identity is the model that made it.",
  "embed_text falls back to a Python embedder when the IRIS EMBEDDING() call fails (iris_vector_graph/_engine/embeddings.py:"
  "157-197); _encode_batch never calls IRIS EMBEDDING() (2033-2049); the offered identity comes from embedding_config first "
  "(iris_vector_graph/_engine/schema.py:1013-1018).", "S2", "high",
  "Offer the identity of the model that produced the vector, or refuse cross-model fallback.", ["3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/_engine/embeddings.py:157-197"), E("inspected", "iris_vector_graph/_engine/embeddings.py:2033-2049"),
   E("inspected", "iris_vector_graph/_engine/schema.py:1013-1018")],
  notes="Live check blocked-access: IRIS EMBEDDING() configurations need %Embedding/AI Hub (P-0101), absent on Community 2026.1.")
f("F-0603", "The IRIS queue worker writes vectors with no identity check, and ignores the model for the default graph",
  "ADR-0006 / spec 226: every seam that writes vectors consults the registry.",
  "ProcessBatch targets Graph_KG.kg_NodeEmbeddings for every default-graph entry whatever its config "
  "(iris_src/src/Graph/KG/EmbedQueue.cls:280-286) and reads no registry row.", "S2", "high",
  "Route default-graph entries through the registry and compare the entry's model and width before writing.",
  ["3.3a-writesets", "3.8-findings-disposed"], [E("inspected", "iris_src/src/Graph/KG/EmbedQueue.cls:258-338")],
  notes="Live write path blocked-access: it needs a working EMBEDDING() config (absent on Community); without it the worker "
        "writes nothing at all (F-0604).")
f("F-0604", "The IRIS queue worker marks an entry DONE when no vector was made",
  "SetResult: DONE carries the result vector, ERROR the message; VEC-I7.18.", None, "S2", "high",
  "Set ERROR with the IRIS message on a failed Prepare, a negative SQLCODE or an empty result.",
  ["3.3-model-check", "3.5-decoders", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-06-vectors"), E("mc", "breadth-a-mc-vec_queue-as-built"), E("mc", "breadth-a-mc-vec_queue-reviewed"),
   E("control", "breadth-a-control-vec_queue")], probe_name="p0604_queue_done_without_vector", live_run="breadth-a-live-06-vectors")
f("F-0605", "enqueue_for_embedding checks the default table's row, not the target graph's route",
  "Spec 227: kg_NodeEmbeddings' registry row is the default pair's row and nobody else's (embeddings.py:1992-1998).",
  "enqueue_for_embedding always enforces against ('kg_NodeEmbeddings', graph '') (iris_vector_graph/_engine/embeddings.py:"
  "1839-1842 at the pin's numbering: the enforce call before _ensure_queue_route).", "S3", "high",
  "Resolve the target route (graph, config) and enforce against its row.", ["3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/_engine/embeddings.py:1803-1850")])
f("F-0606", "Erasure leaves IVF, tree and PLAID indexes holding an erased graph's ids and vectors",
  "HD-0601 (assumption): retained vector-index contents are observable after erasure unless purged; graph-owned indexes "
  "must be invalidated or deleted. docs/migration/v4.0.0.md:742-750 names IVF a gap.", None, "S1", "high",
  "Prune or invalidate graph-owned indexes in the erase; record the graph with the index.",
  ["3.3-model-check", "3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-06-vectors"), E("mc", "breadth-a-mc-vec_ivf-as-built"), E("mc", "breadth-a-mc-vec_ivf-reviewed"),
   E("control", "breadth-a-control-vec_ivf")], probe_name="p0606_erase_leaves_ivf", live_run="breadth-a-live-06-vectors",
  notes="After erase_graph removed the graph's 4 nodes, ivf_search answered the same 3 erased ids with the same scores and "
        "ivf_info still counts 4.")
f("F-0607", "The IVF index's 'cosine' metric is an unnormalised dot product",
  "metric='cosine' is cosine similarity (VecIndex.Cosine normalises, VecIndex.cls:83-90).", None, "S2", "high",
  "Normalise at build, insert and query time.", ["3.5-decoders", "3.8-findings-disposed"], [E("live", "breadth-a-live-06-vectors")],
  probe_name="p0607_ivf_cosine_is_dot", live_run="breadth-a-live-06-vectors",
  notes="Query [1,1,0,0]: long45 [10,0,0,0] scored 10.0 above short0 [0.1,0.1,0,0] scored 0.2; cosine orders them the other way.")
f("F-0608", "Vector index stores do not check width or duplicates",
  "VEC-B11.14: an id lives in at most one cell; indexed counts distinct ids.", None, "S2", "high",
  "Delete before insert across cells, count only new ids, refuse another width.", ["3.3-model-check", "3.6-keys", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-06-vectors"), E("mc", "breadth-a-mc-vec_ivf-as-built"), E("mc", "breadth-a-mc-vec_ivf-reviewed")],
  probe_name="p0608_ivf_insert_duplicates", live_run="breadth-a-live-06-vectors",
  notes="Re-inserting 'a' put it in cells 0 and 1, indexed 2 -> 3, and the stale vector still answered the old direction "
        "with score 1.0. VecIndex and PLAID branches of the finding were not run.")
f("F-0609", "The fused search may read an IVF index built for another graph",
  "FR-013 (a scoped lookup never widens); search_nodes_by_vector refuses the same case (vector.py:783-790).",
  "_fusion_leg_index falls back to an index whose graph is unknown, with a WARNING (iris_vector_graph/_engine/vector.py:208-225).",
  "S2", "high", "Refuse the IVF leg for an index of unknown or other graph; persist the graph with the index.",
  ["3.4-declared-reads", "3.8-findings-disposed"], [E("inspected", "iris_vector_graph/_engine/vector.py:194-225")])
f("F-0610", "The SQL kg_KNN_VEC answers no rows, without error, for a graph whose vectors are under a declared model",
  "docs/KNOWN_ISSUES.md:702-714 (such a call raises); 4.6.0 R265 (no silent empty answer).", None, "S2", "high",
  "Have VectorRouteGuard refuse when the graph has any node route other than kg_NodeEmbeddings.",
  ["3.5-decoders", "3.8-findings-disposed"], [E("live", "breadth-a-live-06-vectors")],
  probe_name="p0610_knn_vec_declared_model", live_run="breadth-a-live-06-vectors",
  notes="The engine's search_nodes_by_vector answers [('v1', 1.0)] for the same graph and model; SQL kg_KNN_VEC answers [].")
f("F-0611", "Edge vectors the upgrade places in a named graph are not found by edge search, and the edge and text quarantines have no API",
  "CONTEXT.md:159-161 (an operator places each quarantined vector); edge search resolves (graph, model, edge) routes.",
  "The edge step inserts into kg_EdgeEmbeddings with the edge's graph_id (iris_vector_graph/migrations/statements.py:203-240) "
  "and adopts kg_EdgeEmbeddings for graph '' only (iris_vector_graph/_engine/schema.py:1312-1315).", "S2", "high",
  "Route named-graph edge rows into kg_eemb_ tables or register kg_EdgeEmbeddings per graph; add list/place calls.",
  ["3.8-findings-disposed"], [E("inspected", "iris_vector_graph/migrations/statements.py:203-240"),
                              E("inspected", "iris_vector_graph/_engine/schema.py:1305-1315")],
  notes="Live check needs a 3.2.0 fixture namespace (blocked-access: namespaces belong to the orchestrator).")
f("F-0612", "The edge and table searches skip rules the node search keeps",
  "ADR-0005 forbids the lengthed TO_VECTOR form for a query vector; 4.6.0 R142 uses the route's dtype.",
  "edge_vector_search builds TO_VECTOR(?, engine dtype, comma-counted dim) and answers [] for errors containing '-30', "
  "'not found' or 'empty' (iris_vector_graph/_engine/vector.py:366-391).", "S3", "high",
  "Use the unlengthed form and the route's dtype; extend the routed-name refusal to kg_eemb_.", ["3.5-decoders", "3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/_engine/vector.py:366-391")])
f("F-0613", "VectorOptimizer.migrate_to_optimized writes vectors without the identity check and reports success with failures",
  "ADR-0006: every seam that writes vectors consults the registry.",
  "migrate_to_optimized inserts row by row with no enforce_embedding_identity and no transaction and returns success: True "
  "with a failed count (iris_vector_graph/vector_utils.py:151-280).", "S3", "high",
  "Enforce the identity, run as one transaction or report failure when failed > 0.", ["3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/vector_utils.py:151-280")])
f("F-0614", "embed_nodes and embed_edges count an identity refusal as an error and return normally",
  "ADR-0006: spec 226 requires it to raise.", None, "S3", "high", "Re-raise EmbeddingIdentityConflict.",
  ["3.5-decoders", "3.8-findings-disposed"], [E("live", "breadth-a-live-06-embed"), E("inspected", "iris_vector_graph/_engine/embeddings.py:1462-1480")],
  probe_name="p0614_embed_nodes_refusal_counted", live_run="breadth-a-live-06-embed")
f("F-0615", "A store_embeddings batch refused for a missing node can leave a new empty route behind",
  "SYS-I3: a refused write changes no store (VEC-X3.9).", None, "S2", "high", "Check every node before resolving the route.",
  ["3.3-model-check", "3.3a-writesets", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-06-vectors"), E("mc", "breadth-a-mc-vec_route_batch-as-built"), E("mc", "breadth-a-mc-vec_route_batch-reviewed"),
   E("control", "breadth-a-control-vec_route_batch")], probe_name="p0615_refused_batch_leaves_route", live_run="breadth-a-live-06-vectors",
  notes="Refused with 'Node does not exist', yet a 6-wide kg_emb_ route and its registry row exist afterwards.")
f("F-0616", "The embed selector's label filter crosses graphs, and its exclude pattern escapes without ESCAPE",
  "Spec 227: selection is graph-scoped (embed_nodes docstring); an exclude pattern skips the matching ids (P-0603).", None,
  "S2", "high", "Add the graph predicate to the label subqueries and ESCAPE '\\' to the LIKE.",
  ["3.4-declared-reads", "3.8-findings-disposed"], [E("live", "breadth-a-live-06-embed"), E("inspected", "iris_vector_graph/embed_selector.py:71-112")],
  probe_name="p0616_selector_crosses_graphs_and_like", live_run="breadth-a-live-06-selector",
  notes="Two earlier runs failed in the harness's fake model (breadth-a-live-06-vectors, breadth-a-live-06-embed) but "
        "already showed the selection: total 3 nodes selected in g for label X with exclude x_*, where only xy1 qualifies.")
f("F-0617", "The glossary and user guide say a second model's write is refused; the code routes it to its own table",
  "CONTEXT.md:154-157 and docs/USER_GUIDE.md:958-960.",
  "A write naming another model gets its own route (iris_vector_graph/_engine/embeddings.py:755-792); the upstream test "
  "test_same_width_different_model_gets_its_own_route asserts it.", "S3", "high", "Update CONTEXT.md and the USER_GUIDE.",
  ["3.8-findings-disposed"], [E("inspected", "CONTEXT.md:154-157"), E("inspected", "iris_vector_graph/_engine/embeddings.py:755-792"),
                              E("tested", "tests/integration/test_embedding_identity_refusal_e2e.py::test_same_width_different_model_gets_its_own_route")],
  notes="p0610/p0614 probes in AUDITA created model-keyed routes without refusal, consistent with the code.")
f("F-0618", "The ledger's node delete does not reach a default-graph node's routed vectors",
  "The engine's delete_node (Eraser.EraseNodeIds) reaches every route; a ledger delete of the same node should too.",
  None, "S2", "high", "Have LedgerApply.DeleteNodeRows delete from every node route the registry names for the default graph.",
  ["3.3a-writesets", "3.6-fk", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-ledger"), E("inspected", "iris_src/src/Graph/KG/LedgerApply.cls:353-370")],
  probe_name="p0618_ledger_delete_routed_vector", live_run="breadth-a-live-ledger")
f("F-C0601", "A node re-enqueued while a worker holds its old text is marked DONE with the old vector",
  "enqueue_for_embedding docstring: re-enqueue overwrites, one entry per node (the latest request is the one to honour).",
  "ClaimPendingBatch is a plain scan with no claim state (iris_src/src/Graph/KG/EmbedQueue.cls:105-133); Enqueue overwrites a "
  "PENDING entry of the same graph (EmbedQueue.cls:44-58); the worker then sets DONE for the entry id with the vector of "
  "the text it read before.", "S3", "medium",
  "Version each entry (a sequence stamped at enqueue) and set DONE only if the version is unchanged; or claim atomically.",
  ["3.3-model-check", "3.8-findings-disposed"],
  [E("mc", "breadth-a-mc-vec_queue-as-built"), E("inspected", "iris_src/src/Graph/KG/EmbedQueue.cls:35-60")],
  disposition="reproduced-model",
  notes="New, from the model sub-lane (check vec_queue-as-built-reenqueue). HD-0604 assumes a single active consumer; even "
        "with one worker the enqueue/work interleaving loses the newer text.")


f("F-C0403", "Candidate: with the adjacency index declared, a failed rebuild could leave part of the adjacency missing",
  "TraversalBuild.BuildKG's comment (iris_src/src/Graph/KG/TraversalBuild.cls:46-55): the kill sits inside the "
  "transaction so a row the rebuild cannot process leaves the adjacency as it was, never destroyed.", None, "S4", "low",
  "Build the new adjacency beside the old one and publish it atomically, or keep the indexed path's purge inside a "
  "transaction it can roll back (no parallel jobs), or validate every row's graph key before purging.",
  ["3.5-lockplans", "3.7-trace-replay", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-04-rebuild"), E("trace", "breadth-a-journal-footprints"),
   E("inspected", "iris_src/src/Graph/KG/TraversalBuild.cls:120-131")],
  probe_name="pC0403_failed_rebuild_leaves_partial_adjacency", live_run="breadth-a-live-04-rebuild",
  notes="Candidate from the journal (J12: ^KG out/in refilled outside any transaction by the caller's and two worker "
        "processes) against the method's comment: the indexed path purges and refills after TCommit with %BuildIndices "
        "in parallel jobs. Not reproduced: a sync() failed on a row with graph_id '0' left all 400 sources of a 400-edge "
        "graph in ^KG out and verify_graph ok. Readers during the refill can still see a partial adjacency (the method's "
        "own catch comment says so); that window was not measured. Not counted as a defect.")
f("F-C0302", "Property lookups with a limit return a storage-order subset",
  "A capped lookup answers a defined subset (no stated order at the pin; ADR/USER_GUIDE silent).",
  "get_node_ids_by_property and get_property_pairs_like build SELECT TOP n ... with no ORDER BY "
  "(iris_vector_graph/_engine/nodes_edges.py:820, 904): with a limit the caller gets the first n rows in scan order.",
  "S4", "medium", "ORDER BY the subject (and value) under a limit, or document the arbitrary subset.",
  ["3.4-storage-order", "3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/_engine/nodes_edges.py:801-832"), E("inspected", "iris_vector_graph/_engine/nodes_edges.py:892-915"),
   E("inspected", "experiment/playbook-completion/models/breadth-a/storage-order/03.json")],
  notes="New, from the storage-order disposition (the coordinator's scan missed both: TOP is built in a separate string).")
f("F-C0603", "kg_KNN_VEC's route guard picks an arbitrary registry row where Python applies a fixed preference",
  "Route resolution is one rule across surfaces (embeddings.py:107-118 orders the candidates).",
  "VectorRouteGuard selects TOP 1 table_name over registry rows keyed (table_name, graph_id), so two node rows for one "
  "graph with no model key answer in scan order (iris_src/src/Graph/KG/GraphStores.cls:300-312).", "S4", "low",
  "Apply the Python preference in the guard (ORDER BY it) or refuse when more than one row qualifies.",
  ["3.4-storage-order", "3.8-findings-disposed"],
  [E("inspected", "iris_src/src/Graph/KG/GraphStores.cls:300-312"), E("inspected", "experiment/playbook-completion/models/breadth-a/storage-order/06.json")],
  notes="New, from the storage-order disposition; reachability (two unkeyed node rows for one graph) not shown.")
f("F-C0604", "The 4.0.0 vector migration takes an undeclared legacy table's width from an arbitrary row",
  "Migration sizes a route from the data it moves; rows of several widths are a quarantine case.",
  "_Migrator._measured_width reads one stored vector with no ORDER BY when neither the table nor the registry declares a "
  "width (iris_vector_graph/migrations/graph_scoped_embeddings.py:1265-1280).", "S4", "low",
  "Measure every distinct width and refuse/quarantine a mixed table.", ["3.4-storage-order", "3.8-findings-disposed"],
  [E("inspected", "iris_vector_graph/migrations/graph_scoped_embeddings.py:1265-1280"),
   E("inspected", "experiment/playbook-completion/models/breadth-a/storage-order/06.json")],
  notes="New, from the storage-order disposition; a 3.x fixture with mixed widths would be needed to provoke it.")
f("F-C0605", "The embed queue serves PENDING entries in node-id order, so an entry can wait indefinitely",
  "A queue that is worked repeatedly eventually serves every entry (progress; HD-0604 single consumer).",
  "ClaimPendingBatch and ProcessBatch take the first batchSize PENDING entries in reqId (= node id) collation order "
  "(iris_src/src/Graph/KG/EmbedQueue.cls:112-133, 258-268); under steady enqueueing of low-collating ids a high id is "
  "never reached.", "S4", "low", "Serve in arrival order (a sequence subscript) or round-robin from the last reqId.",
  ["3.3-model-check", "3.8-findings-disposed"],
  [E("inspected", "iris_src/src/Graph/KG/EmbedQueue.cls:112-133"), E("inspected", "experiment/playbook-completion/models/breadth-a/storage-order/06.json")],
  notes="New, from the storage-order disposition (collation-ordered, not storage-ordered). A progress (AG EF) model with "
        "an unbounded arrival stream would show it; the bounded vec_queue model drains because arrivals are bounded.")
f("F-C0602", "SQL kg_KNN_VEC answers a node once per label, so a multi-label node takes several of the k places",
  "kg_KNN_VEC is a k-nearest-nodes search over the default route (schema.py:2437-2483); kg_RRF_FUSE's vector leg calls it "
  "with no label filter (schema.py:2558).", None, "S2", "high",
  "Use EXISTS for the label filter (no join when no filter is given), or SELECT DISTINCT node_id.",
  ["3.4-statements", "3.6-row-permutation", "3.8-findings-disposed"],
  [E("live", "breadth-a-live-06-embed"), E("inspected", "iris_vector_graph/schema.py:2468-2479")],
  probe_name="pC0602_knn_vec_label_rows", live_run="breadth-a-live-06-embed",
  notes="New, from the storage-order sub-lane's note; reproduced: a node with labels LA and LB filled both places of k=2 "
        "and pushed out the second-nearest node.")


MODULE_OF = lambda fid: fid[2:4] if fid.startswith("F-0") else fid[3:5]


def build():
    by = {}
    for r in F:
        rec = {k: r[k] for k in ("id", "title", "intended", "severity", "confidence", "remedy", "gates", "evidence", "notes")}
        rec["module"] = MODULE_OF(r["id"])
        p = probe(r["probe"]) if r["probe"] else None
        if p is not None:
            rec["observed"] = {"probe": r["probe"], "verdict": p.get("verdict"), "oracle": p.get("oracle"),
                               "values": p.get("observed"), "result_file": f"experiment/playbook-completion/live/breadth-a/results/{r['probe']}.json",
                               "log": p.get("log")}
            if r["observed"]:
                rec["observed"]["source"] = r["observed"]
            if p.get("reproduced") is True:
                rec["disposition"] = r["fallback"] if r["fallback"] == "reproduced-test" else "reproduced-live"
            elif p.get("reproduced") is False:
                rec["disposition"] = "not-reproduced"
            else:
                rec["disposition"] = r["fallback"] if r["fallback"] != "confirmed-source" or r["observed"] else "open"
                rec["observed"]["note"] = "the probe did not decide (crashed or observation only)"
        else:
            rec["observed"] = r["observed"] if r["observed"] else "live probe not yet run"
            rec["disposition"] = r["fallback"] if (r["observed"] or r["fallback"] != "confirmed-source") else "open"
        if rec["disposition"] == "reproduced-live" and r["live_run"]:
            if not any(e["ref"] == r["live_run"] for e in rec["evidence"]):
                rec["evidence"].insert(0, E("live", r["live_run"]))
        by.setdefault(rec["module"], []).append(rec)
    OUT.mkdir(parents=True, exist_ok=True)
    for m, recs in sorted(by.items()):
        orig = [x for x in recs if not x["id"].startswith("F-C")]
        doc = {"module": m, "pin": PIN, "lane": "breadth-a", "generated_by": "experiment/playbook-completion/live/breadth-a/make_audit.py",
               "source_findings": ORIG.format(m=m), "original_count": len(orig),
               "new_count": len(recs) - len(orig),
               "dispositions": {d: sum(1 for x in recs if x["disposition"] == d) for d in sorted({x["disposition"] for x in recs})},
               "findings": recs}
        (OUT / f"{m}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
        print(m, len(orig), "original +", len(recs) - len(orig), "new", doc["dispositions"])


if __name__ == "__main__":
    build()
