# Iteration 61 handoff — replayable obligation census, first tranche

Builder: Opus 5.5 (high). Assignment: [ASSIGNMENT.txt](ASSIGNMENT.txt). Start commit `16c5aa61` (imported
ontology-refinement snapshot); product pin `3eaa79cf`, product paths unchanged (check_consolidated item 1: ok).
No ontology wording, model, binding, receipt, coverage.md or findings file was edited. No Verus, binding or IRIS run:
every grade is read from the current models, NOTES, coverage.md, crosswalk and receipts, and every cited receipt is
checked by the census tool to be the latest fresh receipt of its kind.

## 1. What was built

- [`tools/census.py`](../../../Verus_verification/tools/census.py): deterministic, standard library. It parses
  `.g5/ontology`, hashes each block's governing text, and validates `census/*.tsv`. It fails on:
  - a block missing from `blocks.tsv`, an unknown block, or a moved page/kind;
  - a graded block whose hash changed (**STALE**);
  - an obligation or exclusion on an unknown or not-started block;
  - count mismatches and bad enum values;
  - a model locator whose file or `fn`/item does not resolve;
  - a cited receipt that is missing, not the latest of its kind and label, has the wrong verdict, or whose recorded
    inputs changed (proof, control, binding, playbook rerun with its git tree, native `_probe_inputs`);
  - unknown child obligations in a parent entailment, and an unresolved restatement owner.

  It writes [`census/summary.md`](../../../Verus_verification/census/summary.md). Running it twice gives identical
  bytes (checked with `cmp`).
- [`census/README.md`](../../../Verus_verification/census/README.md): the counting rules and commands.
- [`census/blocks.tsv`](../../../Verus_verification/census/blocks.tsv): all 406 blocks. Its block/page/kind set
  equals `$G5_RUN_STATE/starting-owners.json` exactly (checked).
- [`census/obligations.tsv`](../../../Verus_verification/census/obligations.tsv): 535 rows.
- [`census/excluded.tsv`](../../../Verus_verification/census/excluded.tsv): 177 rows.
- Self-tests in scratch confirmed that the tool reports a wrong item, a superseded receipt, an unknown child id and a
  changed hash (STALE).
- Enumeration was split across six forks of this session, one per page group, writing only in scratch. Their reports
  are kept in [fork-reports/](fork-reports/).
- I merged the fragments, checked that no block was graded twice and that the identity columns were untouched, and
  reviewed cross-page restatements:
  - No two blocks exclude a statement as each other's restatement.
  - Eight restatement owners were narrowed from a block to its single owning obligation.
  - One grade was corrected (§3).

## 2. Census command and output

```sh
cd <repo root> && PYTHONDONTWRITEBYTECODE=1 python3 .g5/Verus_verification/tools/census.py   # exit 0
```

Output (full text in [gates/census.txt](gates/census.txt)): Blocks in the ontology 406. Complete 119, partial 0,
not started 287. **enumeration incomplete: whole-foundation percentage unmeasured** (enumerated 119 complete + 0
partial of 406 blocks; not-started blocks count zero obligations, not N/A).

Column key for the tables below: `pr-full` is the number of obligations proved over their full stated scope; `proved`
also includes proofs over a narrowed scope; `bnd` is bounded, `ref` refuted, `unch` unchecked.

| scope | blocks | full | partial | absent | unassessed | total | lower full/total | upper (full+unassessed)/total | pr-full | proved | bnd | ref | unch |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pooled, enumerated scope | 119 | 224 | 123 | 188 | 0 | 535 | 41.9% | 41.9% | 101 | 265 | 0 | 38 | 0 |
| architecture/adapters | 2 | 10 | 3 | 1 | 0 | 14 | 71.4% | 71.4% | 8 | 9 | 0 | 1 | 0 |
| architecture/query-execution | 17 | 15 | 24 | 31 | 0 | 70 | 21.4% | 21.4% | 6 | 17 | 0 | 9 | 0 |
| concepts/access | 13 | 12 | 5 | 27 | 0 | 44 | 27.3% | 27.3% | 0 | 11 | 0 | 6 | 0 |
| concepts/graph-scope | 14 | 8 | 12 | 19 | 0 | 39 | 20.5% | 20.5% | 2 | 15 | 0 | 2 | 0 |
| features/client-interfaces | 10 | 34 | 9 | 8 | 0 | 51 | 66.7% | 66.7% | 20 | 29 | 0 | 13 | 0 |
| features/erasure | 10 | 6 | 8 | 33 | 0 | 47 | 12.8% | 12.8% | 0 | 9 | 0 | 0 | 0 |
| features/ledger | 19 | 73 | 33 | 17 | 0 | 123 | 59.3% | 59.3% | 31 | 102 | 0 | 3 | 0 |
| features/redaction | 28 | 44 | 21 | 46 | 0 | 111 | 39.6% | 39.6% | 21 | 45 | 0 | 2 | 0 |
| operations/ledger | 6 | 22 | 8 | 6 | 0 | 36 | 61.1% | 61.1% | 13 | 28 | 0 | 2 | 0 |

The tranche (a–d) is complete: 66 blocks with 265 obligations. The continuation pages (redaction and both ledger pages,
53 blocks with 270 obligations) are also complete. Nothing is unassessed, so the lower and upper bounds coincide.
Per-block counts are in summary.md.

How the 224 full obligations break down:

| design check | count |
|---|---:|
| proved over the full stated scope | 101 |
| proved over a narrowed scope | 72 |
| refuted (modelled as-built witness), full scope | 21 |
| refuted, narrowed scope | 15 |
| no design check: holds by a model step's definition | 15 (listed in §6) |

Of the 123 partial obligations, 92 are proved over a narrowed scope, 2 are refuted, and 29 have no check.

As-built correspondence entries over all 535 obligations:

| kind | entries |
|---|---:|
| binding | 213 |
| native | 95 |
| upstream-test | 93 |
| inspection | 74 |
| none | 60 |

Exclusions (177 in total):

| kind | count |
|---|---:|
| restatement | 95 |
| undecided-alternative | 50 |
| rationale | 19 |
| cross-reference | 7 |
| navigation | 4 |
| definition | 1 |
| evidence-annotation | 1 |

Grade sources: 287 reused, 29 changed from coverage.md, 219 new.

## 3. Reused grades, changed grades, parents

Reuse was allowed only when the theorem or witness still exists, its latest receipt is fresh, and the coverage.md
wording matches the current block. Moved blocks kept their IDs; links in the old locations still resolve through the
redirect pages. The main reuse sources are:
- coverage.md's ledger/erasure/redaction rows, platform rows (compiled plans, strict mode) and graph-key rows.
- The NOTES of route_recheck, embedded_no_data, sql_procs, bolt_stream, bolt_tx, bolt_answers, http_rows,
  routine_reporting, ledger_client, ledger_verify, ledger_apply, ledger_content, history_paging, history_diff and
  reconstruction.
- Iteration 60's test-obligation dispositions.

The details are in each fork report.

**Grades changed from coverage.md (reason):**

*Query execution*
- query.compiled.never-stale #o01 and #o02, and query.compiled.integrity #o01: "Proved (conditional) / Suspected
  violation" becomes **full, refuted**. Rule 3: the collision and straggler witnesses are modelled as-built
  counterexamples that reach the observation.
- query.compiled.fallback#o01 (a shape that is not compiled yet): becomes **partial, not proved**. The cited
  `lemma_for_interprets_otherwise` requires an existing entry.
- Coverage.md's "native executor and shadow mode … not modelled" is superseded. sort_key, cypher_clauses and the
  proofs-d1d nread crate model parts of it, including refutations.

*Erasure*
- erasure.scope: coverage.md's block-wide "Proved (model)" is split. Only the other-graph frame over rows,
  temporal-only events, adjacency and labels is proved. Removing g's rows is full by the `erased()` definition. Both
  default-graph spellings, the invalid-name refusal, and reification/FHIR rows are absent.
- erasure.prefix-match: "Violated" becomes **full**. The current text states the node-row limitation as today's
  behaviour, and the W5/W6 witnesses confirm it, narrowed to the witness instance. The every-store violation stays with
  bug-led-007 and bug-led-010.

*Graph scope*
- graph.no_fallthrough: the cross-store key claim moves to graph.key.derive#o04. "An unknown key reads nothing" is
  **partial** (only MatchEdges and the BFS walks are represented).
- graph.names#o04 (refused on every writer path before anything is written): **partial**. The model has no write
  order, and `create_node` does not check the name.
- graph.key.two_forms#o03 (SQL '' and NULL): **partial**.

*Access*
- read_only and Bolt/HTTP transactions: graded from bolt_tx (iterations 56 and 59), not "upstream only / unmodelled".

*Redaction*
- redaction.metadata.exception: "not modelled" becomes **full, proved** (`ledger_client::theorem_revision_rows_immutable`,
  iteration 60).
- redaction.audit, receipt and refusals ("Proved (audit, refusals)"):
  - audit #o01 and #o04 are partial and #o02 and #o03 absent, because `audit_rec` is a constant;
  - receipt #o01–#o08 are absent;
  - refusals: the caller-transaction refusal is partial; the invalid graph name and empty separator refusals are absent.
- redaction.verify ("Proved under premises"): **partial**. The replay theorem is not composed with ledger_verify's
  reader, and bug-led-013 contradicts "equal again" under the block's own conditions.

*Ledger*
- ledger.commit.serial: **partial**. Coverage.md's "Proved (admission order)" is a different obligation; many-writer
  serialization is proved only in the playbook pa3 reviewed design.
- ledger.immutability#o01: **full** (iteration 60 theorem).
- ledger.lifecycle and lifecycle.genesis#o01: now modelled (`theorem_enable_lifecycle`,
  `alternate.rs::theorem_genesis_full_content_from_raw_rows`).
- ledger.strict bullets 1, 2, 4, 5 and 7: **partial**. The guarded classes rest on a source-reading premise
  (`OtherGuarded`).
- ledger.commit#o01: graded full by the fork; **partial at merge review**. ledger_apply takes the admission decision
  as an input, and the end-to-end composition is the residual.

**Parent entailments claimed:**
- erasure.entry-points#o01, through single-path#o01. That child is the stronger promise, so the parent inherits the
  child's grade, absent.
- redaction.target (children refine membership per record kind) and redaction.metadata (the parent's own two
  obligations; its children only bound what may change).
- redaction.after-erasure#o01: default-graph targets are delegated to the child, whose no-prefix case is refuted.
- ledger.verify#o01: verify.scope#o01–#o05 define the two views, and `theorem_equal_iff_views_agree` composes them.
- access.bolt#o01 in part (framing#o03 and results#o01 give in-order answers inside the admitted fragment).

**Parents left open (the case where every child holds and the parent fails):**

| parent | open case |
|---|---|
| query.native#o01–#o03 | Own configuration promises; every child holds while the default resolves to off. |
| query.compiled#o02 | Every child holds while no class is ever used (a stale build job marks a fresh entry refused, bug-cyp-009). |
| erasure.atomic#o01 | Every routes child holds while a list erase without a caller transaction commits its first 500-entry chunk and then fails (bug-led-011). |
| adapters.embedded#o01 | Every no_data obligation holds while the written-in path renders a value differently from a bound parameter. |
| graph.key#o01, #o02 | A store's graph key is not the first subscript, or clearing one graph scans the others. |
| access.surfaces#o01 | A route runs its own SQL or truncates rows while every child holds. |
| access.api_key#o01, #o02 | The children cover only the key-set case. |
| access.read_only#o01 | No child states that reads still run. |
| redaction.batches#o02 | The readers, commits and competing children apply only while the marker exists; a run that has only scanned has no marker (bug-led-006). |
| redaction.tombstone#o03 | Its children (canonical form, digest) are absent. |
| ledger.revision#o01, #o02 | Adoption (`LedgerGenesis.Adopt`) and redaction audit (`LedgerRedact.FinalInLock`) write revisions that no model steps. |
| ledger.commit#o01 | Admission, apply and the post-apply field check are proved separately and never composed. |
| ledger.readers#o01 | Server-side reader effects: the records procedure, chunk staging, the export file write and verify's stats save. |

Structural zero: query.native.sql-first (a process rule plus two restatements, whose owners are
query.native.equal-answers, query.values and query.conformance).

## 4. Ranked uncovered material obligations (step 4; for iteration 62+)

Each entry gives the obligation ids, the missing distinction and the candidate source roles to bind.

1. **Erasure across stores** (the master's lead (ii): **confirmed**; 6 of 47 full, 33 absent).
   - Obligations: erasure.scope#o02–#o07; live-statements#o01–#o03; atomic#o01–#o05; entry-points.single-path#o01;
     kept#o01–#o07; atomic.routes#o01–#o04.
   - Missing distinction: which stores a graph, ID, prefix or edge erase reaches (reifications, FHIR side rows, temporal
     entries of structural edges, caches, statement-map entries), with the same IDs in another graph surviving; '' versus
     NULL; a failure mid-erase and the caller's transaction level (the per-500 commit); bypass deletes.
   - Statements are absent from every model; only native `redaction_binding` evidence exists. The prefix match is the
     one well-covered part.
   - Deciding/writing: `iris_src/src/Graph/KG/Eraser.cls::EraseGraph`, `::EraseNodes`, `::EraseIdSet`,
     `::EraseLedgerFor`, `::EraseAll`, `::CollectOrphanRoutes`; `GraphStores.cls::Scoped`/`Unscoped`;
     `stores/iris_sql_store.py::IRISGraphStore.delete_nodes`/`delete_edges`/`_eraser_txn`;
     `_engine/nodes_edges.py::erase_graph`, `::bulk_delete_nodes`, `::delete_edge`.
   - Observing: per-store reads, `LedgerRedact.cls::PrePass`/`LiveRows`, and `verify()`.
2. **API-key authentication gate, HTTP and Bolt** (15 absent; security; no model at all).
   - Obligations: access.api_key#o01, #o02; every_route#o01–#o06; headers#o01–#o03; bolt#o01–#o04.
   - Missing distinction: key unset/empty versus set; public routes matched on the exact path; every method; CORS
     preflight; 401 before any handler and before the read-only check; Bolt authentication state (a refused LOGON
     revokes it; RESET does not restore it).
   - Roles: `iris_vector_graph/api_auth.py`, `iris_vector_graph/_api_key.py`, `bolt_server.py::BoltSession._authenticate`,
     `::_handle_logon`, `::_handle_reset`, `::_refuse_unauthorized`.
   - Observing: the HTTP status and the Bolt RUN answer.
3. **Native Cypher admission versus SQL fallback, and answer parity** (the master's lead (i): **confirmed**).
   - Admission: 12 obligations; 1 full (a refutation inside the reviewed-design crate), 2 partial, 9 absent. Nothing
     transcribes the as-built `plan_query`/`native_gate`.
   - Parity: 10 obligations; 2 full (both refutations: bug-cyp-104, bug-cyp-136/002), 4 partial, 4 absent.
   - Obligations: query.native.gates#o01, #o03–#o05; reads-only#o01–#o04; fallback#o01, #o02;
     equal-answers#o01, #o02, #o05; shadow#o02, #o05.
   - Roles: `cypher/native_plan.py::plan_query`, `::native_gate`; `engine.py::_adjacency_indexed`,
     `::_native_privileges`, `::_native_executor_current`; `_engine/query.py::_names_mapped_label`, `::_try_native`,
     `::_shadow_compare`; `cypher/native_shadow.py::compare`; `Exec.cls::Run`, `::Neighbours`, `::GroupOf`,
     `::SortKey`.
   - Reader: `execute_cypher`.
4. **Read-only verdict and route refusals.**
   - Obligations: access.read_only.verdict#o01–#o03 and read_only#o02, #o03, #o05, #o07 are absent; read_only#o04 and
     #o06 are partial. The existing models take the verdict as an input.
   - Roles: `cypher/read_only.py::writes_cypher` (decider); the `api_auth.py` read-only middleware;
     `cypher_api.py::_cypher_writes_under_read_only`; `bolt_server.py::BoltSession._handle_run`; `api/gql/schema.py`.
5. **Writes and deletes without an explicit graph.**
   - Obligations: graph.all_graphs_write#o01–#o04 (absent); graph.default#o02–#o04 (absent);
     graph.all_graphs_read#o01–#o03.
   - Missing distinction: a Cypher write without USE GRAPH lands only in the bound row's graph; CREATE/MERGE act only in
     the default graph; a node delete without graph= removes the one holder, returns False for none, and refuses with
     several holders.
   - Roles: `cypher/translator.py`'s SET/DELETE/MERGE translation; `_engine/nodes_edges.py`'s holder lookup and
     `delete_node`/`bulk_delete_nodes`; `iris_sql_store.py::execute_transaction`.
6. **Redaction's unmarked scan window** (redaction.batches#o02, purpose#o03; bug-led-006). This is the cheapest
   refutation: the model represents it, but no witness exists, and `theorem_completion` assumes a started run.
   - Roles: `LedgerRedact.cls::Redact`, `::BatchInLock`, `::BlocksCommit`; `Ledger.cls::CommitInTxn`.
7. **Ledger post-commit properties and replay** (ledger.commit.post-commit#o01, #o02, #o04–#o06; F-1101).
   - Roles: `ledger/client.py::GraphLedger._commit`, `replay.py::verify`.
8. **Verify concurrent with a commit** (ledger.verify#o07, q-led-006). Also redaction.batches.readers#o06 (verify with
   adopt=True racing a redaction, bug-led-001).
   - Roles: `replay.py::verify`, `read_canonical`; `Ledger.cls::Commit`; `LedgerRedact.cls::InProgress`.
9. **Revision invariant across all writers** (ledger.revision#o01, #o02).
   - Roles: `Ledger.cls::WriteRevision`, `LedgerGenesis.cls::Adopt`, `LedgerRedact.cls::FinalInLock`.
10. **Further gaps:**
    - Redaction receipt fields (redaction.receipt#o01–#o08): `LedgerRedact.cls::Receipt`, `client.py::RedactionReceipt`.
    - Interned-snapshot refusal (graph.unscoped_snapshot#o01, #o02): `NKGAccel.RefuseMergedGraphs`,
      `stores/lazy_kg.py::named_graph_with_edges`.
    - The IRIS boundary beyond the three `rdf_edges` readers (access.iris_boundary#o01, #o04, #o05): kg_BM25, kg_IVF,
      and the Native API path.
    - Server-to-engine parity (access.surfaces#o01): GraphQL, MCP and `Service.cls`.
    - Compiled versus interpreted equality (query.compiled.equal-answers#o01, #o02).

## 5. Findings for the master (factual errors in existing grade sources; not repaired here)

1. **Ontology wording, erasure.atomic, working assumption 2** (verified by the builder). It says erasure, ledger commits
   and redaction share the ledger head lock, and that redaction checks liveness while holding it. As built,
   `Eraser.cls` takes no `^IVG.Ledger("head")` lock: the only takers are `Ledger.cls:266,440` and
   `LedgerRedact.cls:282,390`. `LedgerRedact.Redact`'s first liveness check runs outside the lock. Native
   `erasure_caller_transaction_redaction` shows a redaction completing during an uncommitted erase. This is the
   HD-1201 / q-004 proposal, not current behaviour; the census excludes it as an undecided alternative.
2. **Ontology wording, query.compiled.deploy-discards** (verified by the builder). "Nothing else removes them" is
   wrong: `Gen.cls:214` `$System.OBJ.Delete(tCls)` removes a class that failed to compile.
3. **query.native.gates bullet 2** says the index must be on both the edge and label tables. As built,
   `engine.py::_adjacency_indexed` reads only `idx_edges_adj` (F-0906, reproduced in the model only). The metadata names
   no finding.
4. **redaction.tombstone.canonical-form** says an empty graph is written as null. Its own metadata says genesis
   default-graph relationships store NUL (`"\u0000"`).
5. **coverage.md overstatements and stale rows:**
   - erasure.scope "Proved (model)";
   - redaction.verify/ledger.verify "Proved under premises" (bug-led-013);
   - redaction.audit/receipt/refusals "Proved (audit, refusals)";
   - ledger.commit.serial (admission order taken for serialization);
   - line 371: `lemma_for_interprets_otherwise` claimed for absent entries;
   - lines ~431–436, native executor and shadow "not modelled";
   - the ledger rows still saying "not modelled" after iterations 59–60;
   - the graph.no_fallthrough row reading only the cross-store claim;
   - the two_forms row citing a superseded prove receipt.
6. **Tags and links:**
   - `design-verified` on query.native.route (3 of 15 obligations full), and on graph.default and graph.key.two_forms
     (routine_reporting covers only the count readers).
   - Old-location links in the NOTES of embedded_no_data, result_decoders and bolt_answers (they still resolve through
     the redirects).
   - ledger_redaction/NOTES.md names a 20261114 receipt as latest; the latest is `20261116T160746Z`.
7. **Model fidelity and controls:**
   - ledger_redaction's final step with no marker appends nothing, but the product's `FinalInLock` writes a redaction
     revision when `DropStatements` removed entries.
   - `theorem_revision_rows_immutable` has no control for the `redacted_rev` condition.
8. **Evidence wording:** erasure.live-statements' metadata calls the statement left after `delete_edge` an "Observed
   divergence", while the bug-str-013 audit says "not reproduced in this audit".

## 6. Gates at the end (raw outputs in [gates/](gates/); `*.before.txt` are the start-commit runs)

Run with `G5_GUIDE=$G5_HARNESS/guidance PYTHONDONTWRITEBYTECODE=1` from the repository root.

| gate | start (16c5aa61) | end |
|---|---|---|
| `tools/census.py` | (new) | **exit 0**; PASS |
| `tools/check_evidence.py` | FRESH | **FRESH**, exit 0 |
| `guidance/scripts/check_ontology.py .g5/ontology` | 0 issues, 17 warnings, 406 blocks | 0 issues, 17 warnings, 406 blocks |
| `guidance/scripts/check_findings.py` | No problems found | No problems found |
| `tools/check_consolidated.py` | 1 failure: correspondence gate | 1 failure: the same correspondence gate |

**The correspondence gate fails at both start and end, for a reason this batch did not cause.**
- `correspondence_gate.py check iteration-60/correspondence-inputs.json` reports `STALE_ALL` with
  `changed_product: []`.
- Iteration 60 captured the Mac toolchain (`/Users/ziniuw/.cache/.../verus-arm64-macos/{verus,z3}`). This Linux host
  uses `$VERUS_BIN` (same version 0.2026.10.04.426d8b0, x86 binaries).
- I did not recapture. A new capture here would assert reusability on a binary that no receipt in that capture used.
- The master should decide between two options: rerun the affected proofs on this host's Verus and capture, or record
  the cross-platform toolchain identity explicitly.

All other check_consolidated items pass, including "no untracked file outside .g5/" and "product paths equal the pin".

## 7. Limitations and remaining census work

**Not started: 287 blocks** (zero obligations counted, not N/A).

| page | blocks |
|---|---:|
| features/cypher | 50 |
| features/temporal | 29 |
| features/search | 27 |
| operations/setup-and-upgrade | 26 |
| architecture/adjacency-and-derived-data | 26 |
| features/algorithms | 22 |
| features/graph-structure | 20 |
| architecture/search-storage-and-indexes | 18 |
| features/fhir | 18 |
| architecture/algorithm-execution | 13 |
| operations/status-and-repair | 13 |
| features/data-interchange | 11 |
| operations/snapshots-and-bulk-load | 11 |
| operations/search-indexes | 3 |

No block is partial.

**Restatements owned by not-started blocks.** These are counted when the owner's page is enumerated:

| owner | page |
|---|---|
| query.values, query.conformance | cypher |
| install.export.rdf.scope, install.status | setup and status |
| structure.edge.delete, structure.reification | graph-structure / adjacency |
| search.erasure, search.erasure.indexes | search |
| temporal.ledger, temporal.structural.ledger | temporal |

The BM25 refutation (`witness_erase_leaves_bm25`) belongs to search.erasure and is not yet counted.

**Judgement calls a reviewer should challenge:**
- **Split granularity**: 15 route obligations, 7 redaction error classes, 8 receipt fields, 4 reads-only decline
  classes, per-store erasure splits.
- **Full with no design check**: 15 obligations are graded full because the property holds by a model step's
  definition. They are erasure.scope#o01, erasure.history#o01, erasure.prefix-match#o01,
  ledger.idempotency.key-required#o01, redaction.target#o01, redaction.target.nodes#o02, redaction.call#o14, #o15,
  redaction.after-erasure#o02, redaction.after-erasure.default-graph#o01, #o03, redaction.refusals#o01, #o02,
  redaction.metadata.exception#o04 and redaction.batches.commits#o03.
- **Refutations inside the reviewed-design crate**: proofs-d1d's (cx_f0906, cx_f0908, cx_f0902) count as as-built
  refutations because each restores the as-built rule in a control. None is reproduced live.
- **Shared delegate**: redaction.batches.readers' full grades rely on the decision-links justified shared delegate
  (ledger_client's `redacting` flag stands for the marker).

**Evidence and independence:**
- The census was built by forks of one builder session; it has not had independent review.
- No grade rests on a fresh run. Freshness is the census receipt check plus check_evidence, and both pass.
- redaction.batches#o02 is graded full and proved, but narrowed to started runs. The as-built violation (bug-led-006)
  has no modelled witness; adding one is item 6 of §4.

**Reproducing the merge:** each fork's generator script was a scratch artifact, not committed. The TSVs are the
record, and census.py replays them.

## 8. Recommendation to the master

1. **Iteration 62:** erasure across stores (item 1). It has the lowest coverage (12.8%), is privacy-material, and its
   source roles are concentrated in one class (`Eraser.cls`) plus the store layer.
2. **Then** the API-key gate (item 2): a small, pure decision surface with no model and security consequence.
3. **Then** native admission and parity (item 3).
4. **Alongside:** continue the census on features/cypher, features/search and features/temporal. They are heavily
   modelled, so reuse is cheap, and they own most of the restatements that are currently pointed at not-started blocks.
5. **Decide:** whether to fix the two verified ontology wording errors (§5 items 1 and 2) in an owner pass.
