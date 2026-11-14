#!/usr/bin/env python3
"""Build reflection/root_causes.json and reflection/ROOT-CAUSES.md (gate 5c-root-causes).

    python build_root_causes.py

The assignment below is this lane's analysis (method level): every finding of the corpus (check_root_causes.py,
`load_corpus`) gets exactly one primary root cause RC-NN, optional secondary causes, or is excluded because its
disposition is refuted / not-reproduced. A root cause is a missing or violated shared rule or mechanism, named by the
original ontology's universal axioms SYS-I1..SYS-I10 (experiment/playbook-uplift/ontology/00-system.md) where one
applies, otherwise by the playbook principle or the product document it violates. Severities, dispositions and
counts are copied from the corpus, never typed here. Nothing here is a new product finding.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_root_causes import (CONDITIONAL_DISPOSITIONS, EXCLUDED_DISPOSITIONS, LANE, MAP, MD, ROOT, SEV_ORDER,  # noqa: E402
                               load_corpus, top10)

PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"

# id, title, axioms (SYS-I*), other rule violated, statement, remedy, primary members
RCS = [
    ("Graph scope is added by hand to each statement",
     ["SYS-I2"], "SYS-D3/SYS-D4 (each datum belongs to one graph; a call that names no graph uses the default graph); CONTEXT.md:38-43 (an all-graphs read is the union of each graph's own answer)",
     "Graph isolation is a column or first subscript that every query, join, walk, procedure and writer must add for "
     "itself; there is no graph-scoped access layer. Readers and writers that omit the predicate (all-graphs walks, "
     "joins by id across graphs, schema procedures under USE GRAPH, the SQL adapter, sample servers, native readers, "
     "reifier deletion) answer with, or change, another graph's content.",
     "Route every read and write through one graph-scoped access layer whose statements always bind graph_id (default "
     "'') and join on (graph_id, id); refuse unscoped calls; give every reader's tests a two-graph fixture with one id "
     "held by both graphs.",
     "F-0106 F-0206 F-0616 F-0707 F-0711 F-0816 F-0818 F-0819 F-0820 F-1001 F-1002 F-1006 F-1008 F-1009 F-1013 "
     "F-1503 F-1507 F-1603 F-1604 F-1701"),
    ("Stored facts whose key omits the graph",
     ["SYS-I2"], "SYS-D3 (each piece of data belongs to one graph); ADR-0013/plan.md:9-10 (node records are graph-blind by design)",
     "Several stores key a fact without its graph: ledger node records (genesis and LedgerApply record nodes "
     "graph-blind), reifier nodes (always the default graph), BM25 and IVF indexes with no recorded graph, edge vectors "
     "in a snapshot. Ownership checks built on them (redaction's targets, liveness, verify(), node-delete existence, "
     "index use under a graph) cannot attribute the fact, so they attribute it to the default graph or to every graph.",
     "Make the graph part of every stored key: record each node record's graph, create reifiers in the edge's graph, "
     "record the graph of every derived index and archive row; treat an absent graph as unknown (refuse or report "
     "incomplete), never as the default graph.",
     "F-0609 F-0705 F-1105 F-1304 F-1305 F-1401 F-1502 F-1803"),
    ("Removal reach is not derived from a declared store inventory",
     ["SYS-I4"], "SYS-D26 (erasure removes content from every store); ADR-0004; spec 256 US1/SC-001 and FR-008 (the receipt names what it does not reach)",
     "Erasure, redaction's liveness and reach, snapshot export and the redaction receipt each list by hand the stores "
     "and fields they cover. Stores and fields outside those lists keep an erased or redacted tenant's content and the "
     "receipt does not name them: IVF/tree/PLAID and BM25 indexes, temporal-only edges, routed vectors, "
     "embedding_quarantine, legacy Graph_KG ledger rows after an upgrade, IVG's own snapshot archives, the metadata of "
     "a revision that recorded nothing, and the audit's target digest.",
     "Declare one store inventory (each store and field with its owning graph/tenant key and its erase, redact, export "
     "and liveness hooks) and generate erasure, LiveRows/Matches, the snapshot plan and the receipt's out_of_reach "
     "list from it; check mechanically that every writer's target store is in the inventory.",
     "F-0606 F-0618 F-0702 F-C1203 F-C1304 F-C1305 F-C1306 F-C1308 F-C1309 F-C1804 F-CS01"),
    ("Erase, ledger commits and redaction start are not serialized on the ledger head lock",
     ["SYS-I1", "SYS-I3"], "LED-B4.14.4 (only the head-lock holder changes the statement maps); RED-B1.1 (never tombstone live content); premises P-1311, P-C01, P-A3 (false at the pin)",
     "The eraser deletes rows and kills statement-map entries without ^IVG.Ledger(\"head\"); redaction reads its "
     "'another run?' check and its liveness check unlocked and READ UNCOMMITTED and sets its marker only with the "
     "first tombstone; adoption and the first enable read the state they decide on before taking the lock. Each is a "
     "check-then-act on ledger-owned facts that a concurrent commit, erasure, rollback or second run invalidates.",
     "Serialize erase, ledger commits, adoption, enable and redaction start on the head lock (HD-1201 and HD-1301 "
     "working answers): take the lock before reading what a step decides on, check liveness against committed state "
     "and set the per-target marker in the same locked step, run the eraser's row deletes and statement cleanup under "
     "the same lock, and let Final act only when its scan reached the head it holds.",
     "F-1103 F-1104 F-1114 F-1201 F-1302 F-1303 F-C1201 F-C1202 F-C1301 F-C1302"),
    ("Unlocked read-modify-write of shared facts outside the ledger",
     ["SYS-I1"], "playbook §1 principle 3 (concurrency control lives in the database; lock plans are proved per handler)",
     "Outside the ledger, writers of shared facts read, decide and write with no lock, or under a lock mode that "
     "excludes nothing: multigraph mode off vs a parallel-edge write, BM25 Build/Drop, adjacency rebuilds (shared "
     "^IVG.AdjW), native-plan DropAll vs Build, embed-queue claims, ledger_stats counters (%OpenId/%Save), snapshot "
     "file names.",
     "Give every handler a lock plan: each read-modify-write of a shared fact holds the owner's exclusive lock across "
     "the read and the write, or uses an atomic primitive ($Increment, unique names, a version-checked write); one "
     "two-process interleaving test per handler.",
     "F-0207 F-0701 F-0905 F-1102 F-1807 F-C0402 F-C0601 F-C1101"),
    ("Derived stores and caches have no reliable staleness signal",
     ["SYS-I8"], "CONTEXT.md:109-120 (graph-version token); ADR-0012; AlgoCache.cls:5-7 ('never wrongly fresh')",
     "Caches and rebuilt stores (degree cache, algorithm cache, BM25 indexes, the interned snapshot ^NKG, temporal "
     "bucket aggregates, an engine's multigraph-mode cache) are kept current by a token or generation that is stepped "
     "after the write, killed and restarted, not stepped on every path (weights, node-only writes, temporal writes), "
     "survives a rollback ($Increment), or is not consulted at all, so a derived answer stays 'current' after its "
     "source changed or rolled back.",
     "One staleness mechanism for every derived store: a monotonic per-graph epoch stepped before every source write on "
     "every path and never killed, recorded at build and compared at read; mark the derived store stale on rollback, "
     "or store a computed answer only when the writer lock was free and the epoch did not move.",
     "F-0208 F-0401 F-0402 F-0405 F-0406 F-0501 F-0703 F-1004 F-1005 F-C0401 F-C0801"),
    ("Multi-call readers have no consistency protocol",
     ["SYS-I8"], "HD-1401 (a reader returns a consistent view or the documented in-progress result); HD-1802 (a consistent snapshot needs quiet writers or an epoch); IRIS contract E-VIS",
     "Readers that span several calls check the redaction marker once before reading, and save_snapshot reads every "
     "store READ UNCOMMITTED with no epoch, so a reader can return a partially redacted view and an archive can hold "
     "writes that never commit.",
     "Validate every multi-call read against an epoch (bumped by each redaction batch and Final and by writers) after "
     "the read and retry or refuse on change; for exports, an export gate that writers respect or a refusal while "
     "transactions are open.",
     "F-1402 F-C1801"),
    ("The ledger is not the single writer of governed content",
     ["SYS-I1", "SYS-I7"], "spec 213 FR-047; premises P-C02 and P-L6 (false at the pin); HD-1103 (strict mode is client-side)",
     "Ledger-governed content has many writers besides the ledger (bulk loader, purges and row drops, direct edge "
     "deletes, GraphQL mutations, bulk_delete_adjacency, temporal writes, server writers, raw SQL), and strict mode is "
     "a per-engine cached client check (5 s TTL, fail-open). So writes reach governed content unrecorded, leave live "
     "statement entries for removed rows, and are not refused by a redaction's marker.",
     "Enforce ownership in the server: one write gate (Txn_Begin or the content tables' row hooks) that every content "
     "writer passes, which refuses ungoverned writes under strict mode and writes into a marked target, decided per "
     "write and fail-closed; the writer census becomes its test list.",
     "F-0301 F-0302 F-0303 F-0503 F-0504 F-0801 F-1108 F-C1307"),
    ("Retries re-execute effects the idempotency record does not cover",
     ["SYS-I6"], "spec 213 ledger-api.md:26 (a replay returns the original outcome); HD-1305, HD-1603, HD-1702",
     "Idempotency covers only the revision: post-commit properties are a separate write that a replay applies again, a "
     "replay rebuilds its answer without statement ids, and the HTTP client and the Cypher server resend a write after "
     "an ambiguous outcome. A retry can therefore save twice or revive erased content.",
     "Put the whole effect under the idempotency record (post-commit properties recorded with the revision and skipped "
     "on replay; the stored first answer returned) and retry only reads or writes known not to have started; answer "
     "'outcome unknown' otherwise.",
     "F-1101 F-1106 F-1306 F-C1604 F-C1703"),
    ("A command's writes are not one validated, all-or-nothing unit",
     ["SYS-I3", "SYS-I4"], "USER_GUIDE.md:238-241 (each bulk write is a transaction); Neo4j commit-route and Bolt transaction semantics (P-1612)",
     "Multi-step and multi-store commands run in several transactions or autocommit statements (bulk loader chunks, "
     "the FHIR event route, the Neo4j commit route, FHIR Register and Schedule, reifier cleanup, temporal-index "
     "writes), and some refusals are detected after the first write (index-handle build, store_embeddings routes, a "
     "refused temporal write), so a failure or refusal leaves part of the command applied.",
     "One write-transaction wrapper used by every entry point: validate the whole request first, then perform every "
     "write of the command in one transaction (nesting with TROLLBACK 1), never committing inside it; a failure test "
     "per entry that asserts no store changed.",
     "F-0305 F-0615 F-0704 F-1511 F-1609 F-1610 F-C0501 F-C1501 F-C1502"),
    ("IVG ObjectScript writers roll back their caller's transaction",
     ["SYS-I3"], "CHANGELOG 4.6.4 and _write_txn.py:1-30 (an IVG write nested in a caller's transaction undoes only its own level); IRIS contract E-PARTIAL",
     "Some ObjectScript writers (adjacency sync/rebuild, BM25 Insert/Delete) handle a failure with TROLLBACK, which "
     "ends every level, instead of the nesting discipline the Python path follows; a failing IVG call inside a "
     "caller's transaction discards the caller's own work.",
     "One Txn helper for every ObjectScript writer that rolls back only the level it opened (TROLLBACK 1, and only when "
     "it started one); a nested-failure test per writer.",
     "F-0409 F-C0702"),
    ("Environment premises are asserted, not validated",
     [], "playbook §1 principle 2 (model the environment's freedom; state each narrower premise and test it); SYS-P1..SYS-P4 are stated premises",
     "The product relies on engine, edition, driver and optional-library behaviour it neither probes at run time nor "
     "tests on the configurations it supports: SQL COMMIT/ROLLBACK ending every level (true only as 'measured on "
     "2026.3'), durability of an acknowledged commit with SynchCommit=0, the uv.lock driver 5.3.2 (Decimal scores, "
     "<LIST ERROR> duplicate reports, closed cursors), VECTOR_L2 on Community, %AI classes in the test deploy, rdflib's "
     "API, the Arno library's presence and build, IRIS's default schema for unqualified names.",
     "An executable environment contract for every supported (engine, edition, driver, optional library) cell, run in "
     "CI, plus run-time capability probes that refuse with a named reason instead of assuming; a driver floor in "
     "pyproject.toml with a refreshed uv.lock.",
     "F-1012 F-1504 F-C0502 F-C1001 F-C1102 F-C1110 F-C1704 F-C1705 F-C1706"),
    ("The IVG Schema name is not resolved from one source",
     ["SYS-I10"], "ADR-0016 (the schema chosen at install is followed by everything); spec 262 FR-001/FR-006a/FR-007",
     "The namespace's schema record is the intended single source of the IVG Schema name, but legacy SQL files, the "
     "4.0.0 upgrade, the bulk loader's index rebuild, setup's DROP INDEX and the sample API hard-code Graph_KG or "
     "unqualified names, and the first-use check accepts a namespace with no record.",
     "Derive every SQL name through one qualifier from the deploy record (engine._ivg_schema); refuse a namespace with "
     "no record; retire or regenerate the legacy SQL files; run the suites on a non-default-schema namespace.",
     "F-0103 F-0105 F-0107 F-0109 F-0309 F-1605"),
    ("Failures are swallowed into empty, default or success answers",
     ["SYS-I9"], "CHANGELOG 4.6.0 rule 'a failed read raises'; 4.7.0 row 14 (every bulk writer raises for a refused row); 4.6.0 R265 (no silent empty answer)",
     "Handlers catch failures and answer as if nothing happened: [] for a failed read, False ('exists') for a refused "
     "write, DONE for a failed embedding, success with failed rows, 'healthy' with no database, zero vectors for a "
     "failed lookup, a fused search without its failed leg, a restore that drops a line it cannot write. The outcome "
     "is not computed from the operation's result.",
     "Enforce the 4.6.0 rule mechanically: no handler returns an empty/default answer from an except clause; every "
     "outcome (removed, DONE, restored counts, health, legs used) is computed from the operation's own result; a lint "
     "over except clauses plus a fault-injection test per reader.",
     "F-0101 F-0102 F-0209 F-0306 F-0307 F-0511 F-0604 F-0614 F-0709 F-1508 F-1509 F-1611 F-1615 F-C1802"),
    ("Refusals are not mapped to one typed error hierarchy at the boundary",
     ["SYS-I9"], "errors.py:1-17 (one catchable root IVGError); USER_GUIDE.md:313-318 (CypherParseError, GraphWriteError)",
     "Each layer raises its own exception types and messages: lexer SyntaxError, ValueError from the translator, "
     "connection failures reported as client syntax errors, node_not_found decoded as a relationship failure, "
     "wrong reasons in messages, SDK calls that skip the 401/403 map, the metrics hook missing Python-side refusals.",
     "One error mapping per boundary (parser, write path, HTTP status, SDK, wire decoder): every refusal is a subclass "
     "of IVGError carrying the server's reason code, transport failures are transient errors; a test that enumerates "
     "every exported exception class and server code.",
     "F-0804 F-0806 F-0807 F-1506 F-1704 F-1714 F-C1109 F-C1602"),
    ("The Cypher and AQL translators have no reference semantics",
     [], "openCypher semantics and the TCK (docs/dev/TCK.md); CYP-B6.x; KNOWN_ISSUES.md",
     "The translators rewrite each clause shape into SQL locally, with no reference evaluator to compare against; "
     "shapes outside the tested ones (literal-endpoint CREATE, FOREACH over a parameter, MERGE ON SET shapes, "
     "UNWIND..WITH, empty aggregates, null SET, '//' in strings, inline relationship properties, per-row MERGE SET, "
     "shortcut texts matched by substring) give wrong answers or errors.",
     "Drive the translators from a reference semantics: the typed openCypher TCK at the pin on every supported engine, "
     "a differential oracle per clause shape against a reference evaluator, and a refusal for every shape outside the "
     "covered set.",
     "F-0802 F-0805 F-0808 F-0809 F-0810 F-0822 F-0823 F-0824 F-C0101 F-C0803"),
    ("Stored values carry no type",
     [], "playbook §1 principle 7 (typed ids and values); spec 255 (a value comes back with the type it was written with); spec 204 FR-012",
     "Property and qualifier values are stored as JSON text or native subscripts with no type tag and no single "
     "serializer, so numbers and strings compare as each other, floats come back as integers, NaN is stored as "
     "JSON no reader accepts, canonical label forms are not JSON, native index values return as text, and a filter "
     "matches stored JSON text.",
     "A typed value encoding shared by every writer and reader (the planned typed storage), one JSON serializer "
     "(allow_nan=False) for qualifiers and label sets, and the TCK typed runs on mixed data.",
     "F-0308 F-0509 F-0811 F-0812 F-0813 F-1113 F-1804"),
    ("Domain codes, units and metrics are untyped",
     [], "playbook §1 principle 7 (enums, not codes; typed values); NAT-X12; LED-B4.9.2",
     "Kinds, modes, time units, metric names and fusion weights are raw strings or numbers: any revision kind is "
     "accepted, any compile-mode value acts as sync, 'now' is computed in seconds for a millisecond index, a missing "
     "time becomes 0, 'cosine' is an unnormalised dot product, an L2 distance is ranked as a similarity, default "
     "weights go to legs by position.",
     "Enums for kinds and modes that refuse unknown values, a unit carried by each temporal index, metric objects "
     "that carry normalisation and sort direction, weights keyed by leg kind; one unit test per value of each enum.",
     "F-0502 F-0510 F-0607 F-0710 F-0903 F-1107 F-1705"),
    ("Query text is built by pasting values",
     [], "CYP-I9.4 (a name in a query reaches SQL only as a bound value or a checked name); CYP-I8.6 (read-only changes nothing)",
     "The AQL translator pastes literals into Cypher text and a dotted function name is pasted into SQL, so caller "
     "text rewrites the query (and execute_aql has no read-only switch).",
     "Bind every literal as a parameter, validate identifiers against a grammar or an allow-list, and apply read_only "
     "at every query entry including execute_aql.",
     "F-0814 F-0815"),
    ("No server-side authorization or exposure boundary",
     [], "no SYS-I axiom covers it (an ontology gap); HD-1601 (the namespace is the authorization boundary); ADMIN_GUIDE.md:450-473 (least-privilege reading role); deploy/README.md:86",
     "Protection rests on documentation, client flags or the start-up path: file and global helpers are callable by a "
     "reading role, ImportGlobals skips the allow-list, Bolt binds every interface unless started by the CLI, the CLI "
     "binds 0.0.0.0 with no key, demo write routes need no key, the executor checks no privilege, the installer creates "
     "no least-privilege user.",
     "Decide the boundary (HD-1601) and enforce it in the server: no file or global helpers reachable by reading "
     "roles, loopback default bind and a refusal of unauthenticated external binds in the app itself, the key "
     "middleware on every server, a privilege check in the executor (or a documented resource boundary), an installer "
     "that creates the least-privilege user.",
     "F-0908 F-1614 F-1709 F-1806 F-C1603 F-C1803"),
    ("Edge identity for parallel edges is not one rule",
     [], "spec 234 FR-002/FR-007/FR-012/FR-013, SC-005; CONTEXT.md:103-108 (parallel edges each count)",
     "Multigraph support (spec 234) was implemented on some paths only: single-edge writers guard the triple only when "
     "ekey is 0, verify_graph and the graph check compare rows to keyed counts per triple wrongly, Bolt and the ledger "
     "identify an edge by its triple, in-degree collapses parallel edges that out-degree counts.",
     "One edge identity (s, p, o, ekey) used by rows, adjacency counts, the ledger, Bolt ids, degree and verify, with "
     "spec 234's ambiguous-tuple refusal where only a triple is given; a multigraph fixture in each reader's tests.",
     "F-0201 F-0204 F-0205 F-0403 F-1007 F-1712"),
    ("The temporal mark has no single predicate and adoption step",
     [], "ADR-0009 and its amendment; HD-0302; ADR-0015",
     "Whether an edge row is temporal-backed (marked) is decided by different predicates in the deleters, the ledger "
     "and the Python mirror, and the adopt/retract step runs on some writers only (store_edge does not adopt; Purge "
     "leaves marked rows; create_edge adopts after its commit).",
     "One shared mark predicate (JSON boolean true) and one adopt/retract step called by every writer and deleter "
     "inside its own transaction.",
     "F-0304 F-0505 F-0506 F-0507 F-C0301"),
    ("Results depend on storage order or join multiplicity",
     [], "playbook §1 principle 5 (never depend on storage or insertion order, only on keys and explicit orderings); gate 3.4-storage-order",
     "Result prefixes (TOP n) without a total ORDER BY, TOP 1 over several qualifying rows, statement-id allocation in "
     "scan order, schema procedures sampling one element, tie handling in shadow mode, and label joins that repeat a "
     "node make answers a function of storage order or join shape.",
     "Order every result prefix and every allocation by a total key, use EXISTS for filters, and close the "
     "storage-order scan's candidate list (order or document each).",
     "F-0907 F-C0302 F-C0602 F-C0603 F-C0604 F-C0703 F-C0802 F-C1108"),
    ("Identity by a non-injective checksum",
     [], "ADR-0014:19 (a compiled class answers exactly as the interpreter does); NAT-B1.11; NAT-I3",
     "Compiled plan classes and the interpreter's used-relationship set are keyed by a 32-bit $ZCRC, so two shapes "
     "share one class and two relationships count as one; a build then marks whatever entry the hash holds.",
     "Key plans and relationships by an exact key or a collision-resistant digest (the SHA-256 already computed), and "
     "keep the shape check under the entry's lock.",
     "F-0901 F-0902 F-C0901"),
    ("Restore writes stores directly instead of through their owners",
     ["SYS-I1", "SYS-I5"], "spec 213 FR-043 (the ledger survives a snapshot); ADR-0011 (one adjacency writer); SNP-B4.x (merge by the row's own key)",
     "save_snapshot/restore_snapshot copy rows and globals wholesale: a replacing restore lays an archive's ledger "
     "over the live one, a merge guards plain tables on their first column only and overwrites temporal aggregates, "
     "and the adjacency index is written outside its one writer. The stores' own invariants are not maintained.",
     "Restore through the owners: refuse an archive whose ledger history does not extend the live one before any "
     "mutation, rebuild derived stores (adjacency, aggregates) from restored rows, and guard each merged table on its "
     "primary or unique key.",
     "F-0404 F-1801 F-1802 F-1805"),
    ("Vector identity is enforced per seam and fails open",
     [], "ADR-0006 (every seam that writes vectors consults the registry); spec 226 FR-014 (enforcement is not opt-in); spec 227",
     "Each vector-writing seam (engine writes, Python embedder fallback, the IRIS queue worker, VectorOptimizer, "
     "enqueue, upgrade placement, kg_KNN_VEC's route guard) implements its own identity and route check, some none, "
     "and a failed registry read turns the check off.",
     "One vector-write gate in the server that every seam calls: it resolves the (graph, model, kind) route, compares "
     "identity and width, and fails closed when the registry cannot be read.",
     "F-0601 F-0602 F-0603 F-0605 F-0610 F-0611 F-0613"),
    ("Input validation is per entry point, not at the shared write boundary",
     ["SYS-I3"], "ADR-0003:119-121 (the validator rejects '0'); CHANGELOG.md:4618-4620 (the Python mirror refuses what the server refuses); changeset.schema.json limits",
     "Each entry point validates its own input, so graph names, timestamps and weights, vector widths and duplicates, "
     "the reserved stopword name and the wire schema's length limits are checked on some paths and not others.",
     "One validator per input kind at the shared write boundary (the server), the Python mirror generated from it, and "
     "a refusal with a validation code before the transaction starts.",
     "F-0202 F-0203 F-0513 F-0608 F-0706 F-C0701 F-C1107"),
    ("Resource bounds are not declared",
     [], "playbook §3.6 (capacity condition); SC budgets in specs 227 and 236",
     "Limits exist but are neither declared nor checked at the boundary: a combined key length for (s, p, o, graph), "
     "the subscript limit for a prefix, a ~35k-edge window cap under a migration, Python memory for an export claimed "
     "bounded, a Bolt session's IRIS connection, a latency budget.",
     "Declare every bound (key lengths, prefix length, row caps, memory, connections, latency) in the contract, check "
     "it at the boundary with a named refusal, and test each at the limit.",
     "F-0514 F-1510 F-C0606 F-C1106 F-C1204 F-C1601"),
    ("Parallel implementations of one operation diverge",
     [], "ALG-I1 (IVG answers the same without the library); ADR-0014:19; API-B5.8; spec 236 FR-014a",
     "One operation has several implementations (owner vs native PageRank, Arno vs fallback Leiden, the engine vs the "
     "sample API's Cypher entries, node vs edge/table vector search, the native gate vs the SQL path) with no "
     "differential test, and they answer differently.",
     "One implementation per operation, or a differential test that runs every route on the same fixtures and "
     "compares answers.",
     "F-0612 F-0906 F-1003 F-1607 F-C1002"),
    ("Progress is not designed for resumable or queued work",
     [], "LedgerRedact.cls:178-180 (running the same target again resumes it); progress premises PF-1..PF-4; HD-0604",
     "A bounded redaction re-scans from the first record on every call, and the embed queue serves PENDING entries in "
     "node-id order, so repeated work need not finish.",
     "Persist the scan cursor with the marker so a resume continues, serve queues in arrival order, and add a "
     "progress test (a bounded run finishes in finitely many calls).",
     "F-C0605 F-C1303"),
    ("Descriptions are written by hand and not checked against the code",
     [], "playbook §3.1 and §3.8 (every requirement carries evidence); docs/dev/TESTING_POLICY.md",
     "Specs, ADRs, guides, docstrings and self-describing outputs (wire schema, SHOW CONSTRAINTS, STATUS_PARTS, TCK "
     "figures) are maintained by hand; they lag the code or state behaviour it does not have, and nothing fails "
     "when they drift.",
     "Generate or test every description: execute documentation examples (tests/docs), check spec and ADR status lines "
     "in CI, generate the wire schema, constraint lists and status parts from the code, and keep evidence claims tied "
     "to commits of this repository.",
     "F-0104 F-0110 F-0407 F-0408 F-0617 F-0708 F-0821 F-0909 F-1011 F-1109 F-1110 F-1301 F-1501 F-1707 F-1711 F-1713"),
    ("Test, packaging and deploy tooling diverges from the product",
     [], "docs/ADMIN_GUIDE.md:353 (Community is supported); deploy/README.md; pyproject.toml console scripts",
     "The product's own fixtures, installers and entry points are not exercised as shipped: the test deploy compiles "
     "every class (unlike setup), two e2e fixtures read a meta key that does not exist, the bolt-on installer and the "
     "docker recipe do not do what the README says, declared console scripts cannot run.",
     "CI that installs from the built package, runs the deploy recipes and console scripts on Community, and fixtures "
     "that call the product's own setup and read its real keys.",
     "F-0108 F-1112 F-1708 F-1710 F-C1701"),
    ("Stated refusals, options and protocol verbs are accepted and ignored",
     ["SYS-I9"], "playbook §5 lesson 'a refusal written in the spec is not a refusal'; CYP-X3.8, CYP-X10.2, CYP-X12.x; Bolt protocol (P-1612)",
     "Interfaces accept inputs whose documented meaning they do not implement, instead of refusing them: a WHERE after "
     "RETURN, an unknown procedure, an untranslatable expression (NULL), a burst predicate, Leiden's max_levels/tol, "
     "suppress_reverse, a route timeout and cache flag, Bolt BEGIN/COMMIT/ROLLBACK and PULL {n}, transaction verbs on "
     "the embedded cursor, IVG_STRICT_NAMESPACE, --workers N, FHIR pagination, ACORN first, the metrics hook for every "
     "outcome, the MCP query text.",
     "Audit every documented refusal, parameter and protocol verb mechanically (a list generated from the docs and "
     "specs), implement it or refuse it with a named error, and test each.",
     "F-0508 F-0512 F-0803 F-0817 F-0825 F-1010 F-1111 F-1505 F-1601 F-1602 F-1606 F-1613 F-1702 F-1703 F-1706 F-C1702"),
]

# secondary causes: finding -> [RC numbers]
SECONDARY = {
    "F-0802": [1], "F-1002": [12, 29], "F-1001": [29], "F-0209": [1, 28], "F-0616": [19], "F-1502": [3],
    "F-1503": [27], "F-1013": [13], "F-0606": [2], "F-0507": [1, 3], "F-C1307": [4, 30], "F-1304": [29],
    "F-1305": [3, 29], "F-1401": [29], "F-1306": [8], "F-0301": [31], "F-0302": [6], "F-0801": [6], "F-0404": [8],
    "F-0613": [10, 14], "F-0610": [14], "F-1615": [13], "F-1504": [13], "F-0409": [10], "F-C0702": [10],
    "F-C1705": [31], "F-C1102": [31], "F-1709": [33], "F-0908": [31], "F-1708": [20], "F-C1309": [20],
    "F-C1301": [8], "F-0207": [21], "F-0208": [21], "F-1007": [29], "F-1712": [29], "F-0505": [29],
    "F-C0301": [10], "F-1803": [3], "F-C1804": [14], "F-0618": [29], "F-1805": [6], "F-1802": [14],
    "F-C1802": [25], "F-0307": [27], "F-0308": [27], "F-0306": [15], "F-C1107": [15, 28], "F-C1106": [27],
    "F-0614": [26], "F-0612": [26, 14], "F-0609": [26], "F-0611": [2], "F-0615": [26], "F-0601": [14],
    "F-C0603": [26, 29], "F-C0604": [26], "F-0608": [26], "F-0705": [1], "F-0707": [2], "F-0711": [13],
    "F-0701": [10], "F-0806": [31], "F-0814": [20], "F-0815": [1], "F-C0901": [5], "F-1003": [14, 28],
    "F-C1002": [12], "F-C1101": [10], "F-1105": [1], "F-1510": [31], "F-C1502": [3], "F-1601": [10],
    "F-1702": [10], "F-C1108": [8], "F-C1204": [27], "F-C1306": [13], "F-0103": [33], "F-0105": [31],
    "F-0108": [12], "F-0203": [29], "F-0205": [31], "F-0407": [5], "F-0506": [8], "F-0511": [10], "F-0617": [26],
    "F-1505": [31], "F-1111": [31], "F-1706": [31], "F-1703": [31], "F-1602": [14],
}

# Tentative cross-reference to the semantics lane's DRAFT ids (semantics/src/axioms_src.json AX-NN,
# mechanisms_src.json M-NN, read 2026-11-14 ~11:35 UTC). Not final: semantics_xref stays empty until the lane's
# axioms.json / mechanisms.json exist; then semantics_xref() fills it with the ids below that the final files contain.
TENTATIVE_XREF = {
    1: (["AX-02"], ["M-09"]), 2: (["AX-02"], ["M-09", "M-12"]), 3: (["AX-10"], ["M-05"]), 4: (["AX-11", "AX-01"], ["M-03"]),
    5: (["AX-11", "AX-01"], ["M-03"]), 6: (["AX-08"], ["M-04"]), 7: (["AX-12"], ["M-13"]), 8: (["AX-01", "AX-07"], ["M-01"]),
    9: (["AX-06"], ["M-02"]), 10: (["AX-04", "AX-03"], ["M-10"]), 11: (["AX-04"], ["M-10"]), 12: (["AX-09"], ["M-08"]),
    13: (["AX-09"], ["M-08"]), 14: (["AX-12"], []), 15: (["AX-03"], []), 16: ([], []), 17: ([], []), 18: ([], []),
    19: ([], []), 20: (["AX-13"], ["M-11"]), 21: (["AX-01"], []), 22: (["AX-01"], []), 23: ([], []), 24: ([], []),
    25: (["AX-05", "AX-01"], ["M-06"]), 26: (["AX-01"], ["M-12"]), 27: (["AX-03"], ["M-10"]), 28: ([], []), 29: ([], []),
    30: (["AX-14"], ["M-07"]), 31: ([], []), 32: ([], []), 33: (["AX-03"], []),
}

EXCLUDED_REASONS = {
    "F-1612": "refuted on IRIS 2026.1 Community: its premise P-1607 (Read() with no length returns at most 32,000 characters) does not hold for the CSP request stream classes (c16-s5-fraud-sql-stream, c16-s8-followup; findings/audit/16.json); the end-to-end web check is blocked-access",
    "F-0904": "not reproduced (b-09-f0904-sync-failed-build): a sync-mode failed build compiled in the reader's process, but the process still answered and prepared SQL on Community 2026.1; the harsher effect is a 2026.3 premise (P-0903); the compile-cost mechanism is source-confirmed (findings/audit/09.json)",
    "F-1608": "not reproduced (c16-s3-graphql-sample-api): two threads and one query thread on the shared connection gave 0 wrong answers in 12 s on 2026.1 with driver 5.3.2; the missing lock is source-confirmed and the premise stays open (findings/audit/16.json)",
    "F-C0403": "candidate, not reproduced: a sync() that failed on a row with graph '0' left all 400 sources in ^KG and verify_graph ok (findings/audit/04.json)",
}


def semantics_xref() -> dict:
    sem = ROOT / "semantics"
    paths = {k: sem / f"{k}.json" for k in ("axioms", "mechanisms")}
    present = {k: p.exists() for k, p in paths.items()}
    out = {"checked_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "paths": {k: str(p.relative_to(ROOT.parent.parent)) for k, p in paths.items()}, "present": present}
    out["status"] = "available" if all(present.values()) else (
        "pending: the semantics lane's axioms.json / mechanisms.json did not exist when this map was built; each root "
        "cause's semantics_xref is left empty for the orchestrator to fill once they exist")
    return out


def final_xref(n: int) -> dict:
    """Ids of the semantics lane's FINAL files (empty while they do not exist)."""
    out = {"axioms": [], "mechanisms": []}
    for kind, fname, ids in (("axioms", "axioms.json", TENTATIVE_XREF[n][0]),
                             ("mechanisms", "mechanisms.json", TENTATIVE_XREF[n][1])):
        p = ROOT / "semantics" / fname
        if p.exists():
            text = p.read_text()
            out[kind] = [i for i in ids if f'"{i}"' in text]
    return out


def main() -> int:
    corpus = load_corpus()
    recs = corpus["records"]
    ids = set(recs)
    rcs, assignments = [], {}
    prim_of = {}
    for n, (title, axioms, other, statement, remedy, members) in enumerate(RCS, 1):
        rid = f"RC-{n:02d}"
        prim = sorted(members.split())
        for f in prim:
            if f in prim_of:
                raise SystemExit(f"{f} is primary in {prim_of[f]} and {rid}")
            if f not in ids:
                raise SystemExit(f"{rid}: {f} not in corpus")
            prim_of[f] = rid
        sev = Counter(recs[f]["severity"] for f in prim)
        hi = min(sev, key=lambda s: SEV_ORDER[s])
        rcs.append({"id": rid, "title": title, "statement": statement,
                    "violates": {"axioms": axioms, "other": other},
                    "semantics_xref": final_xref(n),
                    "tentative_xref_from_drafts": {"axioms": TENTATIVE_XREF[n][0], "mechanisms": TENTATIVE_XREF[n][1]},
                    "primary": prim, "secondary": [],
                    "conditional": sorted(f for f in prim if recs[f]["disposition"] in CONDITIONAL_DISPOSITIONS),
                    "highest_severity": hi,
                    "severity_counts": {s: sev[s] for s in ("S1", "S2", "S3", "S4") if sev[s]},
                    "modules": sorted({str(recs[f].get("module") or "")[:2] for f in prim}),
                    "remedy": remedy})
    for f, nums in SECONDARY.items():
        for k in nums:
            rc = rcs[k - 1]
            if f in rc["primary"]:
                raise SystemExit(f"{f}: secondary {rc['id']} is its primary")
            rc["secondary"].append(f)
    for rc in rcs:
        rc["secondary"].sort()
    excluded = []
    for f in sorted(ids):
        d = recs[f]["disposition"]
        if d in EXCLUDED_DISPOSITIONS:
            excluded.append({"id": f, "disposition": d, "severity": recs[f]["severity"], "title": recs[f]["title"],
                             "reason": EXCLUDED_REASONS[f]})
        elif f not in prim_of:
            raise SystemExit(f"{f} ({d}) unassigned")
    for f in sorted(prim_of):
        r = recs[f]
        assignments[f] = {"primary": prim_of[f], "secondary": [rc["id"] for rc in rcs if f in rc["secondary"]],
                          "severity": r["severity"], "disposition": r["disposition"],
                          "module": str(r.get("module") or "")[:2], "title": r["title"]}
    disp = Counter(r.get("disposition") for r in recs.values())
    dups = {f: v for f, v in corpus["files"].items() if len(v) > 1}
    top = top10(rcs)
    out = {
        "lane": "reflection", "gate": "5c-root-causes", "level": "method", "pin": PIN,
        "generated_by": "experiment/playbook-completion/reflection/tools/build_root_causes.py",
        "checked_by": "experiment/playbook-completion/reflection/tools/check_root_causes.py",
        "corpus": {"sources": ["experiment/playbook-uplift/FINDINGS.md", "experiment/playbook-uplift/findings/*.md",
                               "experiment/playbook-completion/findings/audit/*.json"],
                   "rule": "one entry per finding id; an id recorded in several audit files takes the last file in "
                           "sorted order (as matrix/build_matrix.py)",
                   "unique_ids": len(ids), "original": len(corpus["original"]),
                   "new": len(ids - set(corpus["original"])),
                   "audit_records": sum(len(v) for v in corpus["files"].values()),
                   "duplicate_records": dups, "dispositions": dict(sorted(disp.items()))},
        "axioms_source": "experiment/playbook-uplift/ontology/00-system.md (SYS-I1..SYS-I10, universal axioms U1..U10)",
        "semantics_xref": semantics_xref(),
        "root_causes": rcs, "excluded": excluded, "assignments": assignments,
        "summary": {"root_causes": len(rcs), "assigned": len(prim_of), "excluded": len(excluded),
                    "conditional": sum(len(rc["conditional"]) for rc in rcs), "top10": top,
                    "top10_cover": sum(len(rcs[int(t[3:]) - 1]["primary"]) for t in top),
                    "no_sys_axiom": [rc["id"] for rc in rcs if not rc["violates"]["axioms"]]},
    }
    MAP.write_text(json.dumps(out, indent=1, sort_keys=False) + "\n")
    MD.write_text(render_md(out, recs))
    print(f"wrote {MAP.relative_to(ROOT)} ({len(rcs)} root causes, {len(prim_of)} assigned, {len(excluded)} excluded) "
          f"and {MD.relative_to(ROOT)}")
    return 0


def render_md(m: dict, recs: dict) -> str:
    rcs = m["root_causes"]
    s = m["summary"]
    c = m["corpus"]
    L = []
    w = L.append
    w("# Findings grouped by root cause (gate 5c-root-causes)\n")
    w("Lane reflection of the completion audit, product pin `3eaa79cf`. Level: **method** (an analysis of the "
      "findings; no new product finding, no product claim). Machine-readable twin: `root_causes.json`, generated by "
      "`tools/build_root_causes.py`, checked by `tools/check_root_causes.py` (registered as `rf-root-causes-check`, "
      "self-test `rf-root-causes-selftest`). Playbook lesson (verification-playbook.txt §5, 'Count root causes, not "
      "findings'): findings fall to a handful of shared mechanisms once grouped by the rule they break.\n")
    w("## Corpus and rule\n")
    w(f"- Findings: every id in the original submission (`experiment/playbook-uplift/FINDINGS.md`, `findings/*.md`: "
      f"{c['original']} ids) and every audit record in `findings/audit/*.json` ({c['audit_records']} records, "
      f"{c['unique_ids']} distinct ids: {c['original']} original, {c['new']} new). Ids recorded twice take the later "
      f"file's record, as the matrix does: " + ", ".join(f"{k} ({' then '.join(v)})" for k, v in sorted(c['duplicate_records'].items())) + ".")
    w("- Dispositions in the corpus: " + ", ".join(f"{k} {v}" for k, v in c["dispositions"].items()) + ".")
    w(f"- Each finding has exactly one **primary** root cause; **secondary** causes are listed where another rule is "
      f"also broken. Refuted and not-reproduced findings are listed separately and count to no root cause "
      f"({s['excluded']}). Intent-undecided and blocked-access findings are assigned but marked *conditional* "
      f"({s['conditional']}): the behaviour is observed or confirmed in source, the intent or the live reproduction "
      f"is not settled.")
    w("- A root cause is a missing or violated shared rule or mechanism. 'Violates' names the original ontology's "
      "universal axioms SYS-I1..SYS-I10 (`experiment/playbook-uplift/ontology/00-system.md`) where one applies, and "
      "otherwise the playbook principle or product document it breaks.")
    xs = m["semantics_xref"]
    w(f"- Cross-reference to the semantics lane (`semantics/axioms.json`, `semantics/mechanisms.json`): "
      f"{xs['status']} (checked {xs['checked_utc']}). The lane's drafts (`semantics/src/axioms_src.json` AX-01..AX-14, "
      f"`mechanisms_src.json` M-01..M-13) were read for a tentative mapping, recorded per root cause as "
      f"`tentative_xref_from_drafts` and shown below as 'tentative'; it is not a cross-reference to final ids.\n")
    w(f"**Result: {c['unique_ids']} findings -> {s['assigned']} assigned to {s['root_causes']} root causes, "
      f"{s['excluded']} excluded.** The ten largest root causes cover {s['top10_cover']} of the {s['assigned']} "
      f"assigned findings ({100 * s['top10_cover'] / s['assigned']:.0f}%).\n")
    w("## Root causes (ordered by findings covered, then S1 count)\n")
    w("| Rank | Id | Root cause | Violates | Findings | S1 | S2 | S3 | S4 | Highest | Conditional | Secondary |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|")
    order = sorted(rcs, key=lambda r: (-len(r["primary"]), -r["severity_counts"].get("S1", 0),
                                       -r["severity_counts"].get("S2", 0), r["id"]))
    for k, rc in enumerate(order, 1):
        sc = rc["severity_counts"]
        w(f"| {k} | {rc['id']} | {rc['title']} | {', '.join(rc['violates']['axioms']) or '(none of SYS-I1..I10)'} | "
          f"{len(rc['primary'])} | {sc.get('S1', 0)} | {sc.get('S2', 0)} | {sc.get('S3', 0)} | {sc.get('S4', 0)} | "
          f"{rc['highest_severity']} | {len(rc['conditional'])} | {len(rc['secondary'])} |")
    w("")
    w("## Top 10 (findings covered, then severity)\n")
    for k, rid in enumerate(s["top10"], 1):
        rc = rcs[int(rid[3:]) - 1]
        sc = rc["severity_counts"]
        w(f"{k}. **{rid} {rc['title']}** — {len(rc['primary'])} findings ({', '.join(f'{v} {x}' for x, v in sc.items())}), "
          f"highest {rc['highest_severity']}. Remedy: {rc['remedy']}")
    w("")
    w("## Observations\n")
    s1 = Counter()
    for rc in rcs:
        s1[rc["id"]] = rc["severity_counts"].get("S1", 0)
    tot_s1 = sum(s1.values())
    cons = ", ".join(f"{r} {n}" for r, n in s1.most_common() if n)
    w(f"- S1 findings ({tot_s1} assigned) concentrate in few causes: {cons}.")
    w(f"- {len(s['no_sys_axiom'])} of {s['root_causes']} root causes break no SYS-I axiom of the original ontology "
      f"({', '.join(s['no_sys_axiom'])}): environment premises, translation semantics, typed values and units, query "
      f"construction, authorization, edge identity, the temporal mark, ordering, identity digests, vector identity, "
      f"capacity, divergent implementations, progress, documentation, tooling. The original's ten universal axioms "
      f"do not state these rules; they are candidates for the semantics lane's axiom and mechanism lists.")
    w("- Shared-mechanism view (playbook: '12 shared mechanisms closed 90%'): one graph-scoped access layer (RC-01, "
      "RC-02), one store inventory (RC-03), one ledger head-lock protocol and server-side write gate (RC-04, RC-08), "
      "one staleness epoch (RC-06, RC-07), one write-transaction wrapper (RC-10, RC-11), one outcome/error rule "
      "(RC-14, RC-15, RC-33) and an executable environment contract (RC-12) would address the root causes of "
      + str(sum(len(rcs[i - 1]['primary']) for i in (1, 2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15, 33))) +
      f" of the {s['assigned']} assigned findings. This is a statement about the grouping, not a claim that the remedies "
      "are correct or sufficient: each remedy is prose, nothing was implemented or tested here.")
    w("")
    w("## Root-cause details\n")
    for rc in rcs:
        w(f"### {rc['id']} {rc['title']}\n")
        w(f"- Statement: {rc['statement']}")
        w(f"- Violates: {', '.join(rc['violates']['axioms']) or 'none of SYS-I1..SYS-I10'}; {rc['violates']['other']}.")
        w(f"- Highest severity {rc['highest_severity']}; modules {', '.join(rc['modules'])}.")
        t = rc["tentative_xref_from_drafts"]
        w(f"- Semantics lane ids: final {rc['semantics_xref']['axioms'] + rc['semantics_xref']['mechanisms'] or 'pending'}; "
          f"tentative from drafts {', '.join(t['axioms'] + t['mechanisms']) or 'none'}.")
        w(f"- Remedy (prose only): {rc['remedy']}")
        w(f"- Findings ({len(rc['primary'])}):")
        for f in rc["primary"]:
            r = recs[f]
            cond = " *(conditional: " + r["disposition"] + ")*" if f in rc["conditional"] else ""
            w(f"  - {f} [{r['severity']}, {r['disposition']}] {r['title']}{cond}")
        if rc["secondary"]:
            w(f"- Also a secondary cause of: {', '.join(rc['secondary'])}")
        w("")
    w("## Excluded (refuted or not reproduced; no root cause)\n")
    w("| Id | Disposition | Severity | Title | Reason |")
    w("|---|---|---|---|---|")
    for e in m["excluded"]:
        w(f"| {e['id']} | {e['disposition']} | {e['severity']} | {e['title']} | {e['reason']} |")
    w("")
    w("## Limits\n")
    w("- The assignment is a judgement over the findings' recorded intended/observed/remedy text; another reader could "
      "place a borderline finding under a neighbouring cause (most such alternatives are recorded as secondary "
      "causes). The checker verifies coverage, existence and arithmetic, not the judgement.")
    w("- The corpus is read when the check runs: a finding any lane adds later fails `check_root_causes.py` until it "
      "is assigned (ratchet).")
    w("- Root causes are about the product's rules; whether the product's intent requires each rule is settled only "
      "where the findings' intent is (the conditional members are not).")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
