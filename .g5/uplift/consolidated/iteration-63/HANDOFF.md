# Iteration 63 handoff — obligation census, tranche 2 (whole foundation enumerated)

Builder: Opus 5.5 (high). Assignment: [ASSIGNMENT.txt](ASSIGNMENT.txt). Start commit `e309b116` (after iteration 62's
integration); product pin `3eaa79cf`, no product file touched. No ontology wording, model, binding, receipt,
coverage.md, NOTES or findings file was edited. Nothing was run except the census tool, the gates and read-only
checks: no Verus, binding or IRIS run. Every grade comes from current models, NOTES, coverage.md, the crosswalk and
receipts, and the census tool checks every cited receipt is the latest fresh one of its kind.

## 1. What was done

- **Pre-check.** blocks.tsv held 287 not-started blocks on 14 pages, matching the iteration-61 list exactly (cypher 50,
  temporal 29, search 27, setup-and-upgrade 26, adjacency 26, algorithms 22, graph-structure 20, fhir 18,
  search-storage 18, algorithm-execution 13, status-and-repair 13, data-interchange 11, snapshots-and-bulk-load 11,
  search-indexes 3).
- **Enumeration.** Twelve forks of this session each took one page group and worked only in scratch, under one brief
  ([fork-reports/BRIEF.md](fork-reports/BRIEF.md)) that restates the iteration-61 rules unchanged. Each wrote fragment
  TSVs and validated them merged onto the repo census (`census.py --dir`, PASS). The harness did not let forks write
  report files, so I saved each fork's final report as [fork-reports/](fork-reports/)`<fork>.md`.

  | fork | pages / blocks |
  |---|---|
  | C1 | cypher: query.paths.varlength … query.system-procedures.results (20) |
  | C2 | cypher: query.aggregation … query.values.conditions (18) |
  | C3 | cypher: query.functions* (12) |
  | T | features/temporal (29) |
  | S1 | features/search (27) + operations/search-indexes (3) |
  | S2 | architecture/search-storage-and-indexes (18) + features/data-interchange (11) |
  | G | features/graph-structure (20) + operations/snapshots-and-bulk-load (11) |
  | A | architecture/adjacency-and-derived-data (26) |
  | AL | features/algorithms (22) |
  | AE | architecture/algorithm-execution (13) + operations/status-and-repair (13) |
  | F | features/fhir (18) |
  | U | operations/setup-and-upgrade (26) |

- **Merge** ([merge-tools/](merge-tools/)). `merge.py` refuses any change to a block's identity columns, a fragment
  touching an already-graded block, duplicate ids and malformed cells. `reconcile.py` holds every merge-time decision
  as code (§4). `xrefs.py` lists mutual restatement pairs and every cross-page block-owned restatement with the owner's
  obligations, for the reviewer.
- **Instrument** (backwards compatible). census.py gains one **Whole foundation** line, printed only when every block
  is complete (README "Reporting" updated). No rule, column, enum or check changed. The output for an incomplete
  census is byte-identical to before: re-running on the start TSVs reproduced `gates/census.before.txt`.
- **Independent spot-check.** A fresh (non-fork) reviewer re-graded a deterministic sample of 25 full and 10 absent
  new rows. 17 of the 35 verdicts disagreed, and all 17 corrections are applied and replayable in `reconcile.py` (§7).

## 2. Census command and output

```sh
cd <repo root> && PYTHONDONTWRITEBYTECODE=1 python3 .g5/Verus_verification/tools/census.py   # exit 0, PASS
```

Blocks 406: complete 406, partial 0, not started 0. **enumeration complete.** Full text in
[gates/census.txt](gates/census.txt) and [summary.md](../../../Verus_verification/census/summary.md), which holds
per-block rows for all 406 blocks; regenerating gives identical bytes.

**Whole foundation (all 406 blocks enumerated; after the spot-check corrections of §7):**

| | value |
|---|---|
| obligations | 2097 |
| full / partial / absent / unassessed | 966 / 403 / 728 / 0 |
| full/total as recorded | 46.1% (lower = upper by the tool: nothing is graded unassessed) |
| passing design checks over full stated scope (proved, full scope) | 322 |
| proved, including narrowed | 1083 |
| bounded | 0 |
| refuted (modelled as-built counterexamples) | 129 |
| unchecked | 0 |
| N/A blocks (empty denominator, structural zero) | 2 (query.native.sql-first; fhir.event.access) |

> **Read 46.1% as an upper-biased figure, not a measurement.** The independent spot-check in §7 re-graded a systematic
> sample of 25 new full grades. Only 13 of them held as full (52%; Wilson 95% interval 33–70%). Ten should have been
> partial, one absent and one was a restated duplicate; the sampled rows are corrected here. Extrapolated to the 720
> tranche-2 full grades, about 374 would hold (interval 241–504).
>
> If the 246 tranche-1 full grades hold, the whole-foundation full share is about **30%** (interval about 23–36%), not
> 46%. Tranche 1 has had no independent review either. The "proved, full scope" count is overstated in the same way:
> 5 of the 25 sampled full rows claimed full scope wrongly.
>
> A mechanical warning sign: 343 of the 720 new full rows (and 94 of the 223 iteration-61 full rows) carry a non-empty
> `gap` column. A full grade with a stated gap is the pattern the reviewer found.

**Per page** (`pr-full`: proved over full stated scope):

| page | blocks | full | partial | absent | total | full/total | pr-full | proved | refuted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| architecture/adapters | 2 | 10 | 3 | 1 | 14 | 71.4% | 8 | 9 | 1 |
| architecture/adjacency-and-derived-data | 26 | 82 | 23 | 26 | 131 | 62.6% | 18 | 80 | 6 |
| architecture/algorithm-execution | 13 | 9 | 3 | 29 | 41 | 22.0% | 0 | 10 | 2 |
| architecture/query-execution | 17 | 37 | 19 | 14 | 70 | 52.9% | 21 | 30 | 15 |
| architecture/search-storage-and-indexes | 18 | 29 | 23 | 35 | 87 | 33.3% | 16 | 30 | 4 |
| concepts/access | 13 | 12 | 6 | 26 | 44 | 27.3% | 0 | 12 | 6 |
| concepts/graph-scope | 14 | 8 | 12 | 19 | 39 | 20.5% | 2 | 15 | 2 |
| features/algorithms | 22 | 55 | 22 | 60 | 137 | 40.1% | 0 | 64 | 6 |
| features/client-interfaces | 10 | 34 | 9 | 8 | 51 | 66.7% | 20 | 29 | 13 |
| features/cypher | 50 | 135 | 60 | 127 | 322 | 41.9% | 38 | 154 | 27 |
| features/data-interchange | 11 | 59 | 8 | 22 | 89 | 66.3% | 17 | 59 | 4 |
| features/erasure | 10 | 6 | 8 | 33 | 47 | 12.8% | 0 | 9 | 0 |
| features/fhir | 18 | 22 | 18 | 41 | 81 | 27.2% | 13 | 33 | 1 |
| features/graph-structure | 20 | 42 | 14 | 43 | 99 | 42.4% | 8 | 53 | 0 |
| features/ledger | 19 | 73 | 33 | 17 | 123 | 59.3% | 31 | 102 | 3 |
| features/redaction | 28 | 44 | 21 | 46 | 111 | 39.6% | 21 | 45 | 2 |
| features/search | 27 | 72 | 33 | 27 | 132 | 54.5% | 29 | 78 | 10 |
| features/temporal | 29 | 92 | 30 | 47 | 169 | 54.4% | 48 | 102 | 6 |
| operations/ledger | 6 | 22 | 8 | 6 | 36 | 61.1% | 13 | 28 | 2 |
| operations/search-indexes | 3 | 12 | 2 | 2 | 16 | 75.0% | 2 | 10 | 3 |
| operations/setup-and-upgrade | 26 | 26 | 21 | 59 | 106 | 24.5% | 17 | 36 | 7 |
| operations/snapshots-and-bulk-load | 11 | 23 | 14 | 19 | 56 | 41.1% | 0 | 32 | 4 |
| operations/status-and-repair | 13 | 62 | 13 | 21 | 96 | 64.6% | 0 | 63 | 5 |
| **whole foundation** | **406** | **966** | **403** | **728** | **2097** | **46.1%** | **322** | **1083** | **129** |

Concepts/adapters, concepts/install and root hold no canonical blocks.

**Change in scope versus change on retained obligations.** The iteration-62 census (119 blocks) stood at
246/119/170 of 535, 46.0%. Its 535 rows are unchanged here: no grade, statement or receipt was edited. Only 11
iteration-61 exclusions changed, in owner or reason text (§4). The new tranche (287 blocks) adds 1562 obligations (1564 enumerated, 2 withdrawn at merge as restatements),
graded 720/284/558 (46.1%) after the spot-check corrections, with 206 proved over full scope, 804 proved and 85
refuted. So the move from 46.0% to 46.1% is entirely a change of scope, not a repair, and §7 shows that both tranches'
full shares are likely overstated.

## 3. Grades reused, new and changed (tranche 2)

| source | count |
|---|---:|
| reused (theorem/witness found, latest receipt fresh per tool, wording matches current block) | 805 |
| new (inspected here; mostly absent obligations and the first grades for new behaviour) | 717 |
| changed from an existing grade source (24 by the forks, 16 more after the spot-check, §7) | 40 |

Per page, as the forks graded them before the §7 corrections (reused / new / changed):

| page | reused | new | changed |
|---|---:|---:|---:|
| adjacency-and-derived-data | 66 | 60 | 5 |
| algorithm-execution | 9 | 29 | 3 |
| search-storage-and-indexes | 34 | 53 | 1 |
| algorithms | 74 | 62 | 1 |
| cypher | 160 | 159 | 3 |
| data-interchange | 60 | 29 | 0 |
| fhir | 27 | 53 | 1 |
| graph-structure | 39 | 60 | 0 |
| search | 76 | 54 | 2 |
| temporal | 124 | 44 | 1 |
| search-indexes | 14 | 2 | 0 |
| setup-and-upgrade | 40 | 60 | 6 |
| snapshots-and-bulk-load | 21 | 35 | 0 |
| status-and-repair | 75 | 20 | 1 |

### Changed grades

**Overstatements that become refutations (rule 3).** "Proved / Suspected / Violated" becomes full + refuted where a
modelled as-built counterexample reaches the observation:
- install.schema.not_ready#o02 (bug-plt-133);
- install.schema.existing#o04 (bug-plt-026);
- install.schema.concurrency#o01–#o04;
- algorithms.cache#o03 and cache.token#o01 (PPR, F-1004);
- install.status#o03 (bug-plt-115);
- degree.cache.erase#o02;
- temporal.structural#o01, .end#o01, .adopt#o01;
- temporal.edge#o03 (epoch 0).

**Became partial.**
- undeclared#o03: the witness covers a raw SQL delete only.
- algorithms.cache.concurrency#o01: coverage.md grades text that is no longer in the block.
- query.values.relationship_text#o04: proved at the decoder, not at the Cypher reader.
- search.embedding.queue#o01: the witnesses assume a write the embed_queue binding refutes on IRIS.

**Absent despite a crosswalk link.** fhir.sql_mapping#o05: the linked theorem does not decide relationship removal.

**Newly modelled since coverage.md** (full, proved narrowed):
- search.embedding.other_model#o02 (install_lifecycle);
- search.routes.no_fallback#o01 (vector_admission);
- algorithms.op.paths.weighted#o01 (weighted_paths optimality, iteration 9).

**Graded absent where the ontology says "observed only":** computed_values#o07, retype#o05, query.writes.ledger#o01.

**Reclassified, not counted as changed:** search.embedding.check_on_write#o01 merges three coverage.md rows into one
full + refuted obligation.

### Judgement conventions (same as iteration 61; reviewers should challenge them)

- A "Today …" sentence about current behaviour is assessable. When an as-built witness confirms it, it is full + proved
  (narrowed), and the intended rule it contradicts is full + refuted.
- Refutations inside reviewed-design crates (proofs-d1d/d1e/d1f) count only where a control restores the as-built rule
  and has a fresh receipt. proofs-d1f has only a baseline receipt, so its as-built counterexamples (HD-1503, F-C1501,
  F-1511) are **not** counted as refutations; every fhir grade from it is held at partial.
- Proofs over a model with provider premises are `check_scope narrowed`. Algorithms, algorithm-execution, status and
  snapshots therefore have no full-scope proof.
- 17 full obligations have no design check, because they hold by a model step's definition. They are listed in each
  fork report §2.

## 4. Merge reconciliation (all in `merge-tools/reconcile.py`)

1. **Double count removed.** C1 counted `query.writes.computed_values#o06` (a relationship CREATE between matched nodes
   stores a literal or parameter and refuses a computed value). C2 counted the same claim at `query.conformance`
   bullet 5.
   - The conformance obligation is withdrawn and becomes `query.conformance#x10`, a restatement of
     computed_values#o06. Its id `#o03` is retired, leaving a numbering gap.
   - Reason: conformance's other deviation bullets are likewise excluded as restatements of their feature owners.
   - Net effect: −1 full.
2. **28 restatement owners narrowed from a block to its owning obligation**, each checked against the owner's text
   (the xrefs listing): for example install.migration#x01 → search.quarantine#o07, fhir.sql_mapping#x01 →
   install.snapshot.scope#o04, and the temporal → temporal.stats.writers / temporal.structural / .end exclusions.
   `structure.adjacency.bulk#x01` is re-pointed from install.bulk_load to **install.bulk_load.loader**, which owns the
   BulkLoader's duplicate and rebuild contract.
3. **Owner widened.** `structure.edge.single#o01` now states the per-triple invariant for every writer, including
   Cypher CREATE, because query.conformance#x02 and path_elements#x01 restate it. Grade stays partial; the gap names
   the unmodelled Cypher writer.
4. **Stale wording.**
   - temporal.stats#o01's entailment now names temporal.stats.writers#o01 to #o06.
   - iteration-61 reasons saying "(not yet enumerated)/(not started)" now say "(enumerated in iteration 63)".
5. **Owner updates from forks** (iteration-61 exclusions that pointed at then-unenumerated blocks):

   | exclusion | new owner |
   |---|---|
   | graph.default#x02 | install.export.rdf.scope#o01 |
   | graph.default#x03 | install.status#o01 |
   | graph.default#x04 | structure.edge.delete#o02 |
   | graph.default#x05 | structure.reification#o07 |
   | erasure.scope#x03 | search.erasure.indexes#o01 (`witness_erase_leaves_bm25` now counted there, full refuted) |
   | ledger.changeset#x01 | temporal.ledger#o01 |
   | ledger.strict#x04 | temporal.ledger#o03 |
   | ledger.strict#x03 | temporal.structural.ledger#o04 |

   - erasure.scope#x02 stays block-owned (search.erasure): it spans #o01, #o02 and erasure.atomic.routes.
   - query.native.sql-first#x03 stays block-owned (query.conformance): the limits it restates span several
     obligations.
6. **Cycle check.** Six mutual block pairs remain. Each pair excludes **different** statements, checked
   individually:
   - algorithms.cache.token ↔ structure.rebuilt.token;
   - search.erasure.indexes ↔ search.scope.indexes.upkeep;
   - structure.adjacency.declare ↔ temporal.structural.upgrade;
   - temporal.ledger ↔ temporal.structural.ledger;
   - the two redaction pairs from iteration 61.

   No statement is excluded at both ends.
7. **Known overlaps kept, both counted.** In each pair the claims can fail independently:
   - temporal.write.collision#o01 (no store changes) vs temporal.stats.writers#o02 (no statistic changes);
   - algorithms.graph_scope#o02 vs graph.unscoped_snapshot#o02 (adds the procedure list and message);
   - algorithms.cache.erasure#o01 (every erase path) vs erasure.scope#o05 (graph erase);
   - query.graph-scope#o01 vs graph.named#o02 (different deciders);
   - query.writes.ledger#o01 vs ledger.unrecorded#o01.

8. **Spot-check corrections:** 17 rows, listed in §7.

## 5. Parents

**Entailment credited (1):** temporal.stats#o01.
- Composition: `theorem_stats_as_built_fragment` composes the per-step writer rules (temporal.stats.writers#o01–#o06)
  over serial histories. Graded full, proved, narrowed.
- Residual: a raw purge that cut a bucket, followed by a delete (q-tmp-002), and concurrent writers
  (`witness_concurrent_inserts_double_count`).

**Parents left open (42 obligations carry `residual:` text).** Each row gives the case where every child holds and the
parent fails; the full list is in the fork reports §4.

| parent | open case |
|---|---|
| query.functions#o01 | An unmodelled function answers a run-time argument differently from the same literal. list_index/reverse/slice already refute it over a narrowed scope. |
| query.graph-scope#o04 | Every child holds on the SQL path while the native plan passes another graph key to Exec.cls. |
| algorithms.op#o01 | A node with no edge is missing from degree, closeness, eigenvector, triangles, SCC, k-core or Leiden answers. |
| algorithms.routing#o01–#o07 | A non-listed algorithm, a named-graph call or a non-USER call is routed to a native reader. |
| algorithms.cache#o01, #o03 | The token does not move on rollback (bug-str-002) or on node creation for PPR (F-1004). Refuted as built. |
| structure.adjacency#o01 | The undeclared FillEdge rebuild disagrees with the rows. |
| structure.adjacency#o02–#o05 | Own text with no child: rebuild serialization, reader graph scoping, the interned snapshot's merged edge. |
| structure.degree.cache#o01, #o03 | The whole-graph stamp path; clearing entries while the stamp is current returns zeros (F-0406). |
| structure.rebuilt#o01–#o03 | ^NKG uses its own flags, not a token; ^ArnoKG has no child; the per-process flag lets another process treat a failed rebuild as fresh. |
| temporal.structural#o01 | A throwing structural step (bug-tmp-001) or a purge race leaves a timestamp with no row. |
| structure.multigraph#o01 | The engine's cached mode (F-0208) disagrees with ^IVG.GraphMode. |
| structure.degree#o01 | The children constrain cached hits only. |
| install.snapshot#o01 | A label, property or reification row, or a BM25/IVF global, fails to come back. |
| search.embedding#o02 | The IRIS queue worker writes with no identity check, or a failed registry read admits a conflict. Refuted. |
| search.erasure#o04 | A process cache or an uncleared IVF/VecIndex/PLAID index still answers erased content. |
| search.quarantine | The upgrade itself misplaces, defaults or drops a vector. |
| install.import | load_networkx/load_obo keeping earlier writes on failure; import_rdf per-batch commit. |
| fhir.graph.lifecycle#o02 | A failed registry update plus a retry leaves two tasks (F-C1501). Refuted. |
| fhir.sync | Batch/watermark atomicity is not entailed by the children. |
| install.namespace#o01 | Two schemas share ^KG/^NKG and the ledger globals. |
| install.schema#o01 | A creator outside setup (BulkLoader, legacy deployer). |
| install.setup#o01 | A case-variant redeploy (bug-plt-015). |
| install.deploy#o01, install.deploy.editions#o01 | The skip rule drops a class the server could run; a class that is not skipped fails to compile on one edition. |
| install.upgrade#o01 | A legacy function is redefined or dropped. |
| install.legacy#o03 | Removing a multi-procedure class fails part-way (bug-plt-014). |
| install.migration#o01 | A re-run duplicates rows. |

**Structural zero:**
- fhir.event.access: restates access.api_key.every_route#o01 and access.read_only#o07.
- query.native.sql-first: from iteration 61.

## 6. Grade-source errors and ontology statements contradicted by source (for the master; nothing reworded)

Evidence is file:line at the product pin. The forks verified the items marked *(src)* against source; the rest come
from the block's own metadata or the model NOTES.

### 6.1 Ontology statements contradicted by source or by their own metadata

| # | block | statement | evidence |
|---|---|---|---|
| 1 | query.graph-scope.names | USE GRAPH refuses a bad name before anything is read or written | No name validation in `cypher/parser.py:174-192`, `translator.py` or `_engine/query.py` (bug-cyp-006); no "Today" label *(src)* |
| 2 | query.browser-metadata | gives the fixed answers "to no other query" | `_engine/query.py:1830-1858` matches words anywhere in the text (bug-cyp-003) *(src)* |
| 3 | search.erasure.indexes bullets 1–2 | erasing every graph empties every named index | `Eraser.cls::EraseAll` (~705–815) kills none of ^BM25Idx, ^IVF, ^PLAID, ^VecIdx *(src)* |
| 4 | search.bm25.cutoff | bullet 3 says skipped terms are reported "in sorted order"; the working assumption says "token order" | Source sorts (`BM25Index.cls` SearchCore $Order, ~286–291) *(src)* |
| 5 | search.routes.create_on_write | table, index and registry row are "committed together" | `schema.py:884-933` commits them separately (bug-srch-015) *(src)* |
| 6 | search.embedding.queue lead | "checked against the table it will be written to" | `embeddings.py:1838-1842` always checks the default legacy table (bug-srch-006) *(src)* |
| 7 | search.bm25.query_time_idf | "never reflects an older index size" | Its own metadata: schema-1 indexes still score with the stored IDF |
| 8 | algorithms.owner, algorithms.op.walks | every algorithm has an Owner giving complete answers without Arno | `_engine/algorithms.py:658-678`: random_walk returns [] without Arno *(src)* |
| 9 | algorithms.op bullet 3 | an unknown direction is rejected with ValueError | Contradicts its child op.paths (no path) and execute_bfs (unknown text = both, bug-str-114); `TraversalPaths.cls:121` walks every non-"both" text outbound for ShortestLength *(src)* |
| 10 | algorithms.op bullet 4 | sampleSize "0 or more" | `_validate.py:249` caps it at 1,000,000 *(src)* |
| 11 | algorithms.graph_scope | the refusal names the Python method | `NKGAccel.cls:213-223` says only "Call the engine's method" *(src)* |
| 12 | algorithms.op.leiden | random_seed makes a run repeatable | Its metadata: the ObjectScript Louvain fallback ignores it |
| 13 | fhir.interpretation bullet 3 | PageRank skips compartment edges by default | Only fhir_concept_ppr does (`fhir_graph.py:409`); `personalized_pagerank` defaults `exclude_predicates=None` (`algorithms.py:227, :434`) *(src)* |
| 14 | fhir.graph.lifecycle lead | registration builds the graph | A first Register does not rebuild (`FHIRGraph.cls:262-272`) *(src)* |
| 15 | structure.node lead | a write IRIS refuses raises | `nodes_edges.py:1097-1104` returns False for "unique", "-119" or "validation failed" *(src)* |
| 16 | install.bulk_load.rebuild lead | a failed rebuild is named in a warning and reads scan | `BulkLoader.load_networkx` raises RuntimeError instead (`bulk_loader.py:586-598`) *(src)* |
| 17 | install.snapshot.derived | the restore moves the token | Only inside `if global_files:` (`snapshot.py:1555-1585`); an SQL-only archive does not *(src, other writers not traced)* |
| 18 | structure.reification bullets 1, 3 | (graph-scoped behaviour) | The guard and join match `s = reifier_id` with no graph (`_engine/schema.py:3318-3324, 3340-3345`): a cross-graph leak *(src)* |
| 19 | erasure.entry-points.single-path#o01 (iteration-61 block) | every delete goes through the Eraser | `delete_edge` runs its own `DELETE FROM rdf_edges` (`nodes_edges.py:1426-1440`) *(src)* |
| 20 | structure.adjacency.bulk bullet 4 | in-transaction bulk_load_session leaves ^NKG to sync() | operator_reports' DISAGREE binding `20261117T042222Z`: each row is interned via `Adjacency.RowPut` |
| 21 | structure.multigraph.layout bullet 5 | the losing writer retries once | Its metadata: no retry, uniqueness error |
| 22 | degree.cache.uncommitted bullet 3 | "until the next rebuild" | `RemoveGraph` (erase_graph) also clears AdjNoLock (`Adjacency.cls:440`) *(src)* |
| 23 | temporal.owner, structure.adjacency.one_writer | single-owner rules | Contradicted by their own metadata (window reader, snapshot restore) |
| 24 | structure.rebuilt lead | freshness is decided by a token | ^NKG uses its own flags; `freshness.py` has no caller in the product *(src)* |
| 25 | temporal.purge bullet 6 | the legacy purge removes statistics of buckets before the cutoff | `TemporalIndex.cls::PurgeBefore` (816–860) does so only inside its raw-timestamp loop *(src)* |
| 26 | install.setup bullet 1 | "not a partial install" | Its metadata: objects created before the failing statement stay |
| 27 | install.legacy | reports truthfully per object | bug-plt-014 |
| 28 | install.schema / classes_follow | (schema follows the namespace) | BulkLoader ignores the schema (bug-plt-012); deploy rewrites class sources with the engine's spelling (bug-plt-015) |
| 29 | ledger.strict bullet 5 | (list of refused loaders) | Omits load_obo, which is refused only through load_networkx's guard (`snapshot.py:1724`) *(src)* |
| 30 | access.defaults | (defaults of the server) | True for `ivg server start`; the sample `api/main.py` reads IRIS_USER and binds 0.0.0.0:8000 (`:155`) *(src)* |
| 31 | query.with metadata | C5 (CALL import) is modelled in clause_combos | `clause_combos/NOTES.md:85` says not modelled |
| 32 | query.optional metadata (`cypher.g5.md:890`) | cites `theorem_null_row_count_zero` | Does not exist; the real one is `theorem_null_row_counts` |
| 33 | query.values.equality metadata | "Parameters … were not checked" | Stale |
| 34 | query.writes metadata | Children: line | Includes structure.node.delete via a question link (parse artefact) |
| 35 | install.status metadata | Children line | Not written as `- Children:`, so the census sees no children |

### 6.2 coverage.md rows wrong or stale

| section / line | problem |
|---|---|
| Search section | Names prove receipt `20261114T035601Z` (latest `20261116T160846Z`) |
| Search section | other_model "refusal half Open" |
| Search section | Gap list calls these unmodelled though models exist: BM25 scoring (bm25_scoring), fusion (retrieval_compose, fusion_ranking), knn/scope/no_fallback (vector_admission), width setup and quarantine placement (install_lifecycle) |
| Search section | Queue row relies on W-O3a/b, which the iteration-36 binding contradicts |
| M18 relationship-text row | "Proved" holds at the decoder only |
| ~147 | "Nodes, edges, reifications CRUD … not modeled": stale for nodes and edges |
| 101 | Grades algorithms.cache.concurrency against text no longer in the block |
| 102 | "Proved (given the bump)" omits the PPR refutation |
| 103, 481 | Cache rows say Violated / reviewed design only (now full refuted) |
| 448, 502 | "FHIR: no model" (fhir_tasks and sql_mapping exist) |
| 451, 484, 502 | algorithms "not modelled" and weighted-path "Open (no optimality proof)" (weighted_paths, it. 9) |
| Temporal gap rows | "ts=0 not modelled" and "window reader not modelled" |
| Install gaps | Says install.schema.name, setup*, deploy* not modelled |
| Install: not_ready row | "no separate theorem" |
| Install: existing row | "Proved" despite the refuted explicit-name case |
| Platform "Latest evidence" | Superseded prove receipt `20261114T002651Z` |
| ~427 | Lists query.writes.atomic as not modelled |
| query.writes.ledger row | "Proved; Observed" covers only the strict refusal |
| Graph and temporal rows | undeclared, temporal.structural/.end/.adopt and degree.cache.erase use Proved/Suspected where rule 3 gives refuted |
| (missing) | No row at all for cypher_fns or cypher_exprs |

### 6.3 NOTES, manifests, tags and crosswalk

- **Stale "latest/final receipt" names in NOTES** (the census cites the true latest):

  | NOTES | names | latest |
  |---|---|---|
  | cypher_exprs | 033051Z / 033119Z | 044807Z / 044717Z |
  | clause_combos | — | 082830Z / 083139Z |
  | cypher_clauses | — | 072020Z |
  | result_decoders | — | 083143Z |
  | aggregate_results | — | 072021Z |
  | sort_key | — | 173229Z |
  | temporal_stats | — | 072022Z |
  | adjacency_maint | — | 20261118T013554Z |

- **Old-location owner links** (they resolve only through redirects) in the NOTES of install_lifecycle, setup_record,
  operator_reports, rebuild_reads, freshness_stamp, index_declaration, traversal_strategy, temporal_marker and
  temporal_stats.
- **install_lifecycle has no manifest.json**, so a manifest `ontology_ids` search misses it.
- **`design-verified` tags that overstate coverage:**

  | block | full |
  |---|---|
  | query.system-procedures | 0/9 |
  | query.parameters | 1/7 |
  | query.values | 6/11 |
  | query.aggregation | 10/13 |
  | percentile | one premise obligation not full |
  | install.setup | 0/3 |
  | install.setup.dry_run | 0/2 |
  | install.setup.resume | 1/4 |
  | algorithms.cache, cache.token, install.status | carry as-built refutations |
  | temporal.window.sources | server half inspected only |

- **Crosswalk rows citing a theorem that does not decide the claim:**
  - `remove_table_mapping` → `theorem_writer_reads_current`;
  - structure.multigraph.count → routine_reporting's census-count theorem.
- **Receipts left stale and undeclared.** Neither is cited by the census or flagged by check_evidence; both are
  housekeeping:
  - `results/native_admission/20261118T015505Z-control-read-step-keeps-write`: its control is not declared in the
    current model.json, and it has no NOTES mention;
  - `results/retrieval_compose/20261117T024538Z-control-guided-cap-max-nodes`: withdrawn in NOTES.
- **proofs-d1f has only a baseline receipt.** Running `control_hd1503_erase_ignores_sync_lock` would give the
  cheapest refutation on the fhir page.

### 6.4 Iteration-61 census grades that tranche 2 calls into question (not changed here; master to decide)

- **erasure.kept#o03, #o05 (absent, "no model").** proofs-d1f `fhir_l2.rs::erased` represents both on the same
  reviewed-design basis that makes fhir.erase#o01 partial. Align both to partial, or both to absent.
- **erasure.atomic#o01.** It does not cite temporal.rs `witness_rolled_back_delete_undercounts` or native
  `temporal_rollback_counters.json` R6, which are a modelled as-built counterexample for the temporal-counter part.
- **erasure.entry-points.single-path#o01.** Contradicted for `delete_edge` (§6.1 item 19).
- **query.native.sql-first#x02.** Its reason still says "SQL side by query.values"; the SQL side is query.values#o01.

## 7. Independent spot-check (non-fork reviewer)

**Sample and reviewer.**
- The sample is drawn deterministically from the merged new rows: every 30th full row (25 rows) and every 56th absent
  row (10 rows). It is kept in [review-sample.tsv](review-sample.tsv).
- The reviewer was a fresh general-purpose agent, not a fork. It received the README rules and the sample, but none
  of my conclusions, and was told to be skeptical.
- I re-checked four of its verdicts in source myself (rows 21, 22, 32, 33), and they hold.

**Results.**

| verdict | full rows (25) | absent rows (10) |
|---|---:|---:|
| agree | 11 (2 of them weak) | 7 |
| should be partial | 10 | 2 |
| scope should be narrowed (stays full) | 2 | 0 |
| should be absent | 1 | 0 |
| statement wrong | 1 (duplicate of failed_leg; withdrawn) | 1 (stays absent; statement fixed) |

**Corrections applied** (all in `merge-tools/reconcile.py`, "spot-check" section, with the reason appended to `gap`
and `grade_source`):

| row | change | reason |
|---|---|---|
| structure.degree.cache.warm#o02 | → partial | SQL role not modelled; sources is an input |
| temporal.structural.mark.readers#o05 | → partial | explicit adoption with own qualifiers and weight not modelled |
| query.paging#o08 | → partial | the ValueError case is only in a definition |
| query.functions.slice#o01 | → partial | only a row-variable lower bound is proved |
| install.inference#o07 | → partial | domain only |
| install.export.rdf.content#o11 | → partial | envelope subjects only; the parsed file is not reached |
| search.embedding.check_on_write#o04 | → partial | store_embedding only |
| search.fusion.rest#o02 | → partial | one endpoint, one width-4 witness |
| install.schema.not_ready#o04 | → partial | the detection booleans are inputs |
| install.status.readiness#o02 | → partial, refuted narrowed | a proxy, not the reader |
| query.functions.list_index#o05 | scope → narrowed | |
| temporal.stats.distinct#o05 | scope → narrowed | |
| temporal.labelset#o04 | full → absent | no resolve function modelled |
| search.scope.indexes#o03 | absent → partial | search.rs `Bm25.graph` and `build` |
| temporal.labelset#o07 | absent → partial | `val_text` passes the provider's text through |
| search.fusion.python#o05 | withdrawn → search.fusion.python#x04 | restatement of search.fusion.failed_leg#o02–#o04 that dropped the raising text leg |
| fhir.event#o01 | statement restored to the block text | |

**Net effect:** full 977 → 966; partial 391 → 403; absent 729 → 728; total 2098 → 2097; proved over full scope
327 → 322.

**Patterns the reviewer found.** These are systematic, so the unsampled rows almost certainly carry the same errors:
1. **Full grades resting on things rule 2 excludes.** Examples: a model *definition* (`envelope`, `canon`,
   `apply_props`, `as_built_page`), a *proxy* (`route_rows>0`), or one entry point where the statement covers several.
   The row's own `gap` often admits the shortfall while the grade stays full.
2. **`check_scope full` on narrowed proofs.** It is claimed for single-point witnesses and for theorems with narrowing
   `requires`.
3. **Absent searches that missed models.** They grepped block ids and obvious model names, and missed behaviour
   modelled under another block. Separately, statements sometimes drift from the block text, by dropping a refuting
   case or importing product detail.

**Consequence.** The unsampled 695 tranche-2 full grades were not re-graded; the estimate is in §2. The forks applied
the same reuse procedure as iteration 61, so the 246 tranche-1 full grades may be overstated in the same way.

## 8. Ranked uncovered material obligations, whole foundation

Each entry gives the obligation ids, the missing distinction, and the deciding / writing / observing code to bind.

### A. Absent obligations in blocks with no applicable model

1. **Erasure across stores, including search stores.** Privacy; still the lowest page (12.8%).
   - Obligations: erasure.scope#o02–#o07; live-statements#o01–#o03; atomic#o01–#o05; kept#o01–#o07;
     atomic.routes#o01–#o04; search.erasure#o01–#o04; search.erasure.indexes#o03–#o04 (contradicted by EraseAll);
     algorithms.cache.erasure#o01.
   - Missing: which stores each erase reaches, keyed per graph; failure mid-erase; erase-all of named indexes.
   - Deciding / writing: `Eraser.cls::EraseGraph`, `::EraseAll`, `::EraseIdSet`, `::CollectOrphanRoutes`;
     `nodes_edges.py::erase_graph`, `::erase_all`; `iris_sql_store.py::delete_nodes`, `::_eraser_txn`; the replacing
     restore in `snapshot.py`.
   - Readers: `kg_KNN_VEC`, `kg_TXT`, `bm25_search`, `ivf_search`, `vec_search`, `verify()`.
2. **Security surfaces with no model.**
   - access.api_key*: 15 absent (iteration 61, item 2): `api_auth.py`, `_api_key.py`, `bolt_server.py::_authenticate`,
     `::_handle_logon`, `::_handle_reset`.
   - access.webapp#o01–#o04: `Service.cls::CreateWebApp`, `::EnsureWebAppRole`, `::GrantWebAppSql`.
   - install.upgrade.grants#o01–#o05 and arno_revoke#o01–#o02 (EXECUTE only, never table privileges; the revoke set):
     `_engine/legacy.py::copy_grants`, the revoke step.
3. **Native-reader (Arno) routing and its evidence gate:** 22 absent.
   - Obligations: algorithms.routing#o01–#o07, routing.revision#o01–#o03, routing.reload#o01, routing.excluded#o01,
     routing.fallback#o01–#o03, proof#o01–#o03, proof.gate#o01–#o04.
   - Missing: which reader answers per algorithm, graph, namespace, revision and report state, and how a failed
     native answer is handled.
   - Bind: `arno_readers.py::route`, `::load_proof`, `::validate_proof`, `::parse_report`;
     `iris_sql_store.py::_arno_route`, `::_native_answer`; `ArnoAccel.cls`; `scripts/arno_reader_gate.py`.
4. **Upgrade, data migrations and legacy removal:** 28 absent.
   - Obligations: search.quarantine#o01–#o08; install.migration#o01–#o06, .steps#o01–#o03; install.legacy#o01–#o07,
     .manifest, .ownership; install.upgrade#o01–#o04, #o06.
   - Missing: conservation, re-run idempotence, an injected commit failure, per-object removal truth.
   - Bind: `migrations/graph_scoped_embeddings.py::_fate`, `migrations/upgrade.py::upgrade_to_4_0_0`,
     `migrations/_commit.py`, `_engine/admin.py::remove_legacy_objects`, `legacy_manifest.py`.
5. **Centrality and community answers:** 29 absent.
   - Obligations: degree, betweenness, closeness, eigenvector, leiden, triangles, scc, kcore.
   - Missing: the values themselves; betweenness's fixed SHA-1 sample of 200; Leiden's fallback order.
   - Bind: `_engine/algorithms.py` (each function), `NKGAccelCentrality.cls`, `execute_degree_centrality`.
6. **Newest-event temporal index:** temporal.latest#o01–#o08, latest.exact#o01–#o05 (13 absent).
   - Bind: `TemporalIndex.cls::NoteLatest`, `::Relatest`, `::RebuildLatest`; reader `TemporalWindow.cls::Latest`,
     `get_latest_edges`. The iteration-51 native predictions L1–L8 exist.
7. **FHIR resync, rebuild and compartment edges:** 19 absent.
   - Obligations: sync.idempotent#o01, #o03–#o06; rebuild#o01–#o04; behind#o01–#o02; interpretation#o01–#o08.
   - Bind: `FHIRGraph.cls::ResyncKey`, `DropNode`, `RunBatch`, `Rebuild`, `SyncOnce`.
8. **Cypher scoping and gates.**
   - query.with#o01–#o08, no model: `translator.py::translate_with_clause`, `::translate_subquery_call`.
   - USE GRAPH validation, query.graph-scope.names#o01–#o02 (contradicted): `parser.py`, `_validate.py::validate_graph_name`.
   - Write routing without USE GRAPH: graph.all_graphs_write#o01–#o04, query.graph-scope.write, query.graph-scope.read#o01–#o02.
   - Engine read-only gate: query.read-only#o01–#o04 and access.read_only.verdict#o01–#o03: `read_only.py::writes_cypher`.
9. **Reifications:** structure.reification#o01–#o07, plus the source-found cross-graph leak.
   - Bind: `_engine/schema.py::reify_edge`, `::get_reifications`, `::delete_reification`.
10. **Cypher string and list functions:** query.functions.strings (13 absent), query.functions#o02–#o13 (12 absent).
    - Bind: `translator.py::_scalar_string`, `::_expr_fn_list_ops`, and the `schema.py` CypherFn bodies.
11. **Smaller model-less groups:**
    - structure.verify#o01–#o04 (`GraphVerify.cls`; bug-str-004);
    - structure.node.read.properties#o01–#o08;
    - temporal.purge.bare-nodes#o01–#o05;
    - search.bm25.write_lock#o04–#o08 and incremental#o01–#o02;
    - search.routes.create_on_write#o02–#o04 and orphan#o02–#o03;
    - fhir.event#o01–#o04;
    - access.defaults#o01–#o03.

### B. Unsupported conditions and outcomes in partly covered blocks

12. **Bulk paths:**
    - structure.adjacency.bulk#o02–#o04 (rebuild before return; bug-str-009);
    - install.bulk_load.loader#o02, #o08, #o09;
    - install.bulk_load.rebuild#o01 (token and degree-cache freshness).
13. **Freshness:**
    - interned snapshot: structure.rebuilt#o01, #o03, stale_read#o02, #o03 (`EnsureNKG`, `MarkGraphGone`);
    - token per writer: structure.rebuilt.token#o02, #o03 (bug-str-016);
    - algorithm cache: algorithms.cache.token#o04 (namespace-wide token), cache#o04, cache.concurrency#o02.
14. **Multigraph switch and restore:** structure.multigraph.switch, .restore, multigraph#o03 (F-0208, bug-str-007/008).
    - Bind: `GraphMode.cls::Set`, `_engine/admin.py::set_multigraph`, `_ekey_guard`.
15. **Native-connection calls inside a caller transaction:** structure.write#o05–#o09 (bug-srch-002).
    - Bind: `engine.py::_iris_obj`, the index writers.
16. **Restore derived state and failure:** install.snapshot.derived#o01–#o03, failure#o01–#o02, scope#o04.
17. **Cypher write atomicity:** query.writes.atomic#o01, #o03, #o05.
    - Bind: `_execute_cypher_write`, `_write_txn.py::WriteTxn`; needs a no-caller-transaction start.
18. **Global PageRank:** algorithms.op.pagerank#o02–#o05, #o07, #o08 (default-graph scope, sum to 1, dangling spread).
19. **Changeset temporal operations:** temporal.ledger#o02, #o03.
    - Bind: `LedgerApply.cls::OpCreateTemporalEdge`, `Changeset.create_temporal_edge`.
20. **Carried from iteration 61:**
    - redaction's unmarked scan window (redaction.batches#o02; bug-led-006);
    - ledger post-commit (ledger.commit.post-commit#o01, #o02, #o04–#o06);
    - verify concurrent with a commit (ledger.verify#o07);
    - the revision invariant across all writers (ledger.revision#o01, #o02).

Native admission and parity, item 3 of iteration 61, was closed by iteration 62 (query-execution 15 → 37 full) and is
not repeated here.

## 9. Iteration-60 RUN-STOP residual queue against the census

| residual | census obligations (owner exists) | no owner in the ontology (source-discovered omissions) |
|---|---|---|
| store / `iris_sql_store` | Owned only through behaviours: graph-scope.write and query.writes.delete#o01, #o02 and atomic (`execute_transaction`); pagerank, subgraph, degree and paths (`execute_*`); algorithms.routing#o04–#o05, routing.fallback, cache#o01–#o03, capabilities#o07; search.knn#o05; structure.node.delete.bulk#o06; structure.write#o05; undeclared#o03 (`write_edges`); erasure (`delete_nodes`/`_eraser_txn`) | No block owns the store protocol as an interface (`store_protocol.py` is declaration-only) |
| GQL/GraphQL | search.scope#o01 and access.surfaces#o01 mention it in passing | **No block owns the GraphQL schema or resolvers** (37 members, none reached) |
| SDK/CLI/HTTP admin | access.defaults#o01–#o03, access.webapp#o01–#o04, install.status.readers#o01–#o12, fhir.event#o01–#o04, the `ivg fhir` CLI (fhir.graph.lifecycle#o01, fhir.sync), search.routes.inventory#o05, search.fusion.rest | Sample API binds 0.0.0.0:8000 (`api/main.py:155`); `ivg server start` has no --iris-username (`cli.py:420-427`); Bolt per-session connections never closed (metadata only); `IVG_SNAPSHOT_DIR` (metadata only) |
| Translator residue (review-59 G2/G3) | G2 → query.with#o01–#o08; G3 → query.values.sorting#o06; query.union#o02, #o03, #o08–#o10; query.conformance#o02, #o04–#o07; query.writes#o01, #o05, #o06; create-existing; computed_values#o07–#o11; query.functions*; algorithms.graph_scope#o02; algorithms.op.paths#o07; structure.multigraph.layout#o05, #o06; adopt#o04; scan#o10, #o11; stale_read#o03 | Pre-parse shortcuts `_execute_approx_count_distinct` / `_try_khop_fast_path` (when they answer, USE GRAPH); `_scope_statements` (later statements inherit the first USE GRAPH); `_execute_count_create` raise_on_error; `_null_row_aggregate` trigger; 13 CypherFn bodies reachable only from SQL; IVGRANGE positional UNWIND (`translator.py:9027`); F-0823 |
| Install residue (review-59 G4) | install.upgrade*, grants, arno_revoke, install.legacy*, install.deploy#o01–#o05, #o09, #o10, install.setup#o02, #o03, install.schema.speed, fhir.graph.install#o01–#o04, install.status.capabilities#o01–#o07, structure.drift#o02, declare#o06, temporal.structural.upgrade#o03, #o04, #o08, search.embedding.registry#o01, claim#o03, #o04, install.snapshot*, install.bulk_load* | Dry-run and report shapes of individual migrations |
| `load_networkx` / `load_obo` | install.import#o01, #o02, #o04; install.bulk_load#o02; install.bulk_load.rebuild#o02 | load_obo fetches URLs and decodes lossily; ledger.strict bullet 5 omits load_obo |
| Migrations | install.migration#o01–#o06, .steps#o01–#o03, install.upgrade#o01–#o06, search.quarantine#o01–#o08, claim#o01, fhir.interpretation.version#o01–#o04, temporal.latest#o08, temporal.purge#o05 | `TemporalIndex.cls::RebuildBucket` (migration-only statistics rebuild) |
| Temporal residue | temporal.latest*, bare-nodes, graph-scope#o02, temporal.ledger, window ordering and filters, opt-out operations, distinct/group reads, repeatable#o02, #o03, paging handles; temporal.structural#o03, #o04, .end#o04, .ledger#o01, #o05, #o06, temporal.owner#o01, mark.readers#o02; fhir.event#o03 | The millisecond class's readers over seconds-class edges; `get_edge_attrs` and `get_window_sources`; the `BulkInsert` wrapper returning only the first count |
| Operator residue | install.status.* readers, structure.rebuild#o09, #o10, #o12, #o13, structure.verify*, structure.adjacency.bulk#o05, #o06, stale_read, subgraph.guided#o09–#o11, neighbors#o03, walks#o06, fusion.leg_index#o02 | kg_GRAPH_WALK next-hop lookahead (`_engine/algorithms.py:707-709`); kg_GRAPH_WALK_TVF alias; kg_GRAPH_PATH path_id always 1; `bfs_vector_rerank`; gds.* shim option validation |
| Retrieval residue | search.fusion.same_graph#o01–#o02, surfaces#o03, multi_vector#o01, #o03, vector_graph#o02, #o06, rest#o03, scope.indexes#o03–#o05, fusion.python#o06–#o09, leg_index#o03, embedding.bulk#o02, #o05 | `TextSearchEngine.search_documents` ignores graphs (bug-srch-013); F-C0602 (kg_KNN_VEC answers a node once per label); F-0610; F-C0715 bm25_search ID rewriting; `set_embedding_identity(force=True)` overwrite |

**Other source-discovered omissions:**
- FHIR re-registration semantics: watermarks kept; denylist applies only at the next rebuild; json_links changes
  trigger an immediate rebuild or "rebuild pending". A refused Register keeps its settings (F-1511).
- The FHIR concept readers (`ResolveConcepts`, `CoverageReport`, `ConceptGaps`, `PatientConcepts`, `LinkReport`,
  `GroupPPR`) and `fhir_bridge_add` / `get_kg_anchors`.
- `_interp_stale`, which fhir_tasks models but no block owns.
- `BM25Index.Build` kills the old index before scanning (line 99).
- `EmbedQueue::ClearDone` and free-text queue entries.
- `bulk_ingest_edges`, which is missing from install.bulk_load's "three ways".
- The restore's `_register_endpoints` recovery for pre-4.0 archives.
- `keys(n)` listing `id`.
- PPR's own conditions for using the Owner (routing metadata only).
- bug-plt-018: status claims native PPR and WCC (metadata only).
- The writer lock's console WARNING (`Adjacency.cls:68-71`).

## 10. Limitations

- **The full count is overstated by an estimated ~45% on tranche 2 (§7).** Only the 35 sampled rows were re-graded.
  The census is otherwise the work of twelve forks of one builder session plus my merge review, and tranche 1 has had
  no independent review either.
- **No grade rests on a fresh run.** Freshness is the census receipt check plus check_evidence.
- **Split granularity is a judgement and drives the denominators.** Examples: strings 16, scan 11, quarantine 8,
  weighted paths 19, rdf.content 13, latest 8, and each "Today" bullet as its own obligation. C2 notes that excluding
  every "Today" bullet would remove about 20 mostly-full obligations on its pages alone.
- **Source reading was targeted.** Many absent grades rest on "no model exists", not on reading each implementation.
  Many contradictions are taken from block metadata or NOTES, not re-traced.
- **Some "full scope" proofs may be generous** (A: declare#o01–#o05, stamp#o01–#o06), because the bindings are
  unit-level. Conversely, every algorithms and status proof is marked narrowed.
- **Reviewed-design refutations are model-only.** proofs-d1d/d1e controls count as refutations under the iteration-61
  convention; none is reproduced live.
- **The fork generators are not committed.** They were scratch scripts, as in iteration 61. The committed record is
  the TSVs, the fork reports and `merge-tools/` (merge, reconcile, xrefs). The tranche can be replayed from the
  fragments only while scratch exists.

## 11. Remaining work (master's call)

- **Re-grade before using the percentage.** Re-grade every full grade (tranche 1 and 2) under rule 2 with an
  adversarial verifier. Start with the 437 full rows that carry a non-empty `gap`. Then re-check every
  `check_scope full` against the theorem's `requires`, and every absent grade with a by-behaviour model search. Until
  that is done, report the whole-foundation share as "46.1% recorded, about 30% estimated (23–36%)".
- **Independent review of the remaining judgement calls** in §3 and §10, and the 40 changed grades.
- **Owner pass** over the §6.1 ontology contradictions, §6.2 coverage.md rows, §6.3 NOTES and tags, and the §6.4
  iteration-61 grades.
- **Next modelling targets:** §8 A1–A3 (erasure across stores, security surfaces, native-reader routing), then A4
  (migrations).

## 12. Gates

Raw outputs are in [gates/](gates/); `*.before.txt` are runs at the start commit `e309b116`. All were run from the
repository root with `G5_GUIDE=$G5_HARNESS/guidance PYTHONDONTWRITEBYTECODE=1`.

| gate | start | end |
|---|---|---|
| `tools/census.py` | exit 0, PASS; enumeration incomplete (119 of 406) | **exit 0, PASS; enumeration complete (406 of 406)**; output deterministic (two runs compared byte for byte) |
| `tools/check_evidence.py` | FRESH | **FRESH** |
| `tools/check_consolidated.py` | PASS | **PASS** |
| `guidance/scripts/check_ontology.py .g5/ontology` | 0 issues, 17 warnings, 406 blocks | 0 issues, 17 warnings, 406 blocks |
| `guidance/scripts/check_findings.py .g5/Verus_verification .g5/ontology` | No problems found | No problems found |

Files changed by this batch:
- `census/blocks.tsv`, `obligations.tsv`, `excluded.tsv` and `summary.md`;
- `tools/census.py` (the whole-foundation line) and `census/README.md` (the Reporting note);
- this directory.

No product, ontology, model, receipt, coverage.md, NOTES or findings file changed.
