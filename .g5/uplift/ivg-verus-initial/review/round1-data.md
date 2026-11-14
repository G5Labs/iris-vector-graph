# Stage C review, round 1 — R2-data (graph structure, adjacency, degree cache, rebuilt stores, temporal)

Reviewer: R2-data. I did not read the other round-1 reviews. Product baseline 3eaa79cf, worktree
`experiment/iris-vector-graph-g5-verus-20261113`. The product was read-only. I ran no IRIS, probe or test. Scratch
work, model copies and raw Verus logs are in `$RUN_DIR/agents/R2-data/` (`$RUN_DIR` =
`/home/ziniu_wu_g5labs_ai/runs/iris-vector-graph-g5-verus-20261113`).

The orchestrator ran the native probes between 23:42 and 23:46Z. My task described them as not yet run, so their raw
observations in `$RUN_DIR/native/` are newer than the brief. I read them and use them below.

## Independent expectations

I wrote these from CONTEXT.md, ADR-0001/0002/0003/0008/0009/0010/0011/0012/0015, specs 204/234/239/245/246/252/254/255
and the code before opening any uplift artifact. The code I read: `GraphKey`, `Adjacency`, `Adj`, `AdjIndex`,
`TemporalIndex`, `TemporalPolicy`, `LedgerApply`, `Ledger.Commit`, `AlgoCache`, the `Eraser` callers,
`_engine/{nodes_edges,temporal}.py`, `freshness.py` and `algo_cache.py`.

### Graph scope and keys

- **E1 Key derivations.** `ForIndex(name)` maps `""` (or a name made only of NUL) to integer 0. Any other accepted
  name maps to itself with every `$Char(0)` removed. `ForLedger` maps `""` to `$Char(1)` and is otherwise the same.
  `ForName` returns the canonical name, `""` for the default graph.
- **E2 Refusal rule.** `Validate` judges the canonical name, after NUL is stripped. It refuses exactly `"0"`, and any
  name that `$ZStrip(..,"*C")` would change: the IRIS control class 0–31 and 127–159, minus NUL, which was already
  stripped. `"00"`, `"0.0"` and `"-0"` are accepted and distinct from the default graph. An embedded NUL makes
  `"a"_$C(0)_"b"` the same graph as `"ab"`. The rule creates that collision on purpose (NUL is a transport artifact),
  and a model must represent it rather than hide it.
- **E3 Key separation.** The default graph's key differs from every accepted name's key, in both trees. No function
  converts one form into the other. A key used on the wrong tree reads nothing, and a scoped lookup never falls
  through to the default graph.
- **E4 Graph key first.** The graph key is the first subscript of every graph-scoped store: `gen`, `degc`, `degw`,
  `tlast`, `^IVG.TemporalStructural(gKey,p)`, `^IVG.GraphMode(gKey)` and `^IVG.AlgoCache(gKey,..)`. `^NKG` and
  `^ArnoKG` are deliberately unscoped.

### Edges, multigraph, adjacency

- **E5 Single-edge graphs.** Writing the same `(s,p,o,g)` twice adds nothing: `create_edge` returns False, ledger
  `create_rel` returns `relationship_exists`, and an upsert merges qualifiers. The same triple in two graphs is two
  edges. Deleting one graph's edge leaves the other's adjacency and the shared `^NKG` entry (`HeldElsewhere`).
- **E6 Multigraph mode.** Opt-in per graph. Turning it off is refused with `parallel_edges_present` while any triple
  has more than one row.
  - Layout: the leaf holds the lowest live ekey's weight. Children and `"#"` exist only while a triple has two or more
    edges; going from 2 to 1 collapses to the exact single-edge form.
  - Degree counts live edges. An ekey is never renumbered.
  - Spec 234 FR-007 says `create_edge` must add an edge in a multigraph, and FR-013 says an ambiguous tuple ref must be
    refused. The spec's status line says this ledger work is not done. Code: `create_edge` guards on `ekey = 0`, and
    `FindEdge` takes the first row.
- **E7 Declared index.** With the functional index declared, each row's transaction also changes `out`/`in`. A
  rollback restores both. There is no adjacency without a row and no row without adjacency. Three cases change the
  outcome:
  - (a) A caller that also calls `Adjacency.Remove` after its row write. `LedgerApply.DeleteRelInternal:689` does this
    whenever the leaf still exists. After a multigraph 2→1 collapse, that leaf is the survivor's, so the survivor's
    adjacency is killed while its row stays.
  - (b) A writer refused the lock, which writes anyway and sets `^IVG.AdjNoLock`.
  - (c) `RowUpdate`: a changed triple is a remove plus a put; a changed weight on the same triple is a reweight.
- **E8 Undeclared index (legacy).** The non-indexed branch of `DeleteTemporalEdge` calls `Adjacency.Remove` without
  checking for a row. The purge's `RetractTemporalShadows` keeps a triple that has a row. So the non-indexed delete
  removes the adjacency of an explicitly created edge on the same triple.

### Degree cache (ADR-0010/0012)

- **E9 Rule.** A served degree equals a recount, with `#` multiplicity.
- **E10 The generation is not monotone in production.** It can return to an earlier value:
  - `RemoveSource`, `RemoveGraph` and `RemoveAll` kill `gen`.
  - `BuildKG`'s `FillEdge` does not bump it.
  - That gives an ABA on the reader's pre-store check and post-store re-read.
- **E11 Rollback.** A rolled-back write over-bumps the generation, which only invalidates.
- **E12 Whole-graph stamp.** `AllWarm` is valid only while `degw == __version`.

### Rebuilt stores and algorithm cache

- **E13 Token.** `__version` only moves by `$Increment` and is never killed. A store's stamp must be taken before its
  build.
- **E14 Uncommitted read.** A token bumped inside an uncommitted writer, a reader that caches under it, and a rollback
  that does not take the bump back together leave a poisoned cache. The degree cache has the lock probe against this;
  `AlgoCache` and `Freshness` do not.
- **E15 `^NKG`.** It is right for the default graph only while no named graph has an edge.

### Temporal

- **E16 Write modes.**
  - Insert at occupied coordinates is a collision and changes nothing; skip does the same.
  - Update overwrites `tout`/`tin`/`edgeprop` and also `$Increment`s bucket, count and sum. An update of an existing
    edge therefore counts twice, against the docs.
  - The ledger's temporal op defaults to update.
- **E17 Write order.**
  - Order: tout, tlast, tin, `$Increment(bucket)`, then the structural row (which can throw), then
    `$Increment(count/sum)`, min/max/HLL `Set`s and edgeprop.
  - A direct write runs with no transaction. Inside a transaction, a rollback leaves the `$Increment`s.
  - The delete is the mirror image: `$Increment(bucket,-1)` and its Kill-at-0 survive a rollback.
- **E18 Forward implication and a race.** ADR-0009 says a timestamp of a structural predicate implies a row. A
  write/purge race on one triple breaks this: the writer trusts `^KG("out")`, then the purge retracts the row.
- **E19 Purges.** `PurgeRawBefore` covers `[start,end)` and keeps aggregates. `PurgeBefore` acts on the default graph
  only.
- **E20 Registry.** Absent means structural. A change takes effect for the next write.
- **E21 Ledger collision.** A ledger "insert" collision is still recorded as `create_temporal_edge`.

## Coverage findings

- **The forward implication is not an L1 property (R1-7).** `temporal.rs` `rows_ok` checks only marked row ⇒
  timestamp, the spec 254 amendment. ADR-0009's primary decision is the other direction: a timestamp of a structural
  predicate ⇒ a row, which `temporal.structural` states as "visible ... while any of its timestamps exist". It is
  stated nowhere.
  - The write/purge race (and the write/`DeleteTemporalEdge` race) is left out as "not claimed". Spec 254 lists it as
    an open defect (`tasks.md:80-81`), not as a design choice.
  - `Action::DeleteEdge` lets an explicit `delete_edge` remove a marked row while timestamps remain, without comment.
    No source decides that case.
- **Rolled-back deletes and erasures are hidden (R1-9).** `step()` turns `Delete`/`Purge` inside a transaction into a
  no-op (`if s.txn.len() == 0 {..} else { s }`). The case is reachable: `delete_edge_temporal` or `delete_node`
  (→ `TemporalIndex.EraseNodes`) inside a caller's transaction (4.6.4 nesting), then `ROLLBACK`.
  `RemoveTemporalRow`'s `$Increment(bucket,-1)` survives, and its Kill-at-0 is restored as 0, so the event counter
  under-counts. This is the mirror of F3. It contradicts `temporal.erase` ("Node erasure keeps the remaining statistics
  ... exact") and erasure's all-or-nothing rule.
- **Degree-cache routes and the warm stamp (R1-10).** The model and notes give delete_node and non-indexed sync/restore
  as the ABA routes. Missing routes:
  - the Python purge's default `retire_bare_nodes=True` (`Eraser.ForgetNodes` → `RemoveSource`, Eraser.cls:1320-1327),
    common under opsreview-style retention;
  - `erase_graph` (`RemoveGraph`);
  - `%BuildIndices` `PurgeIndex` (`RemoveAll`).

  `WarmFill`/`AllWarm`/`degw` are not modeled. I read them and found them safe, because `__version` is never killed;
  that is not a finding.
- **Graph keys across stores (R1-4).** No L1 statement says that every store spells a graph with the same canonical
  name: SQL `graph_id` = `ForName(name)` for every writer. The model has only a witness (Q5). See Check A.
- **The legacy non-indexed branch (R1-13).** `temporal.structural.end` ("An unmarked structural edge stays") does not
  say it applies only with the index declared. E8 violates it in an undeclared namespace.
- **The register and the coverage map omit this scope (R1-1).** See the register check below.

## Fidelity findings

Answers to the four specific challenges:

1. **The degree-cache ABA is real; the abstraction did not invent it.**
   - `Adjacency.RemoveSource` kills `^KG("gen",g,s)` (Adjacency.cls:376). `RemoveGraph` (437) and `RemoveAll` (461)
     kill the whole subtree. The next `$Increment` restarts at 1.
   - The reader's store test and re-read compare only for equality (Adj.cls:75-80). The `Adj.Degree` comment
     (46-48) acknowledges the restart, but the re-read only covers a restart after the store.
   - The model's `KillCommitted` (`gen: 0`) matches the code. Check B: with kills that move gen forward, the as-built
     protocol is proved sound with no P-QUIET and no epoch. So the ABA comes from the restart alone.
   - The tGen = 0 route that NOTES claims had no witness. Check B2 adds one (58 verified, 0 errors). It needs gen
     absent, which happens after a non-indexed `BuildKG`; an indexed rebuild goes through `%BuildIndices` → `Put` and
     bumps gen.
   - The window is narrow. The stress probe ran 3383 rounds with verdict INCONCLUSIVE
     (`graph_structure_degree_aba-20261113T234512Z.json`). For a 2-entry node the count takes microseconds, while the
     three committed writer transactions take milliseconds, so the race can only be hit by preemption. The product
     status should stay SUSPECTED, labeled "not natively reproducible without a stall hook".
2. **The parallel-edge delete defect (LedgerApply.cls:689) is confirmed from the code and natively.**
   - `DeleteRelInternal` deletes the row (678); the index's `RowRemove` → `RemoveKeyed` collapses the triple to the
     survivor's bare leaf (Adjacency.cls:300-311); then 689 sees `$Data` and calls `Remove`, which kills the leaf.
   - Raw evidence: `graph_structure_parallel_delete_rel-20261113T234255Z.json`, default and named graph, index
     `functional`. Before: 2 rows, children [0,1], `#` = 2, degree 2. After: 1 row, no leaf, degree 0 and recount 0,
     while Cypher `MATCH` still returns the neighbour through the SQL rows.
   - The model's `delete_rel_as_built` is a faithful transcription.
3. **Temporal F1 and F3 premises are faithful.**
   - F1 (update): `WriteStores` has no early return for update (TemporalIndex.cls:82-86), so bucket (102) and
     count/sum (117-118) are incremented again. `raw_part`/`agg_part` transcribe this in order, and F1 does not
     depend on P-INCR.
   - F3: the order raw → bucket `$Increment` → row (may throw) → count/sum `$Increment` matches the code.
     `Ledger.Commit` runs `ApplyAll` inside TSTART and `TROLLBACK 1` on refusal (Ledger.cls:402-407).
   - P-INCR ("`$Increment` is not undone by TROLLBACK") is supported by the repo's own measurements (ADR-0010
     Context; USER_GUIDE "Writes inside your transaction") and by IRIS documentation. It is correctly carried as a
     premise.
   - Native evidence is incomplete, though (R1-6). The update case and all four rollback cases crashed on R1-5. Only
     `bulk_fallback_update` corroborates F1: bucket 4 against 2 raw edges, and tagg count 2 / sum 2.0 against a raw
     sum of 6.0.
4. **The graph-key proofs use the real rule, and the control class is now observed.**
   - `is_ctrl` = 0–31 ∪ 127–159, with NUL stripped first and `"0"` refused. That is `Validate` exactly.
   - P-CTRL was observed natively through `GraphKey.ForName` (keys probe, `p_ctrl`): 0x01, 0x1F, 0x7F, 0x80, 0x85 and
     0x9F refused; 0xA0 accepted. The ontology still says "not checked live" (R1-14).
   - Weakness (Check A): the injectivity theorems are relative to `canonical`. A variant that strips every control
     character instead of refusing it (ADR-0003's table wording) keeps all five injectivity/cross-store theorems
     green. Only `theorem_refusals` and the Q4 witness fail. The theorems therefore cannot see a canonicalization that
     merges names the other stores keep apart, which is the K4 drift (R1-4).

Other fidelity points:

- **Correct reductions.** §3 `put_keyed`/`remove_keyed` match Adjacency.cls:210-321. §4 `Add` (content then token)
  is a safe reduction, because the token bump follows the content change and the reader reads the token first.
- **WCC's isolated nodes are not a token hole.** WCC's edgeless nodes are added outside the cache (`complete_labels`,
  algorithms.py:814), so node-only writes do not poison it. That closes intent Q8 for WCC; I did not check CDLP's
  equivalent.
- **The `as-built-without-quiet-premise` control is detected by a proof-structure assertion.** It fails at
  `assert(v.epoch_stamp)` in `lemma_killcommitted`, not at a semantic property. The ABA witness under `dv_product`
  supplies the semantic counterexample, so the control is acceptable. I reproduced it at 54 verified, 2 errors, at
  lines 1003 and 1325.

## Adversarial checks

Each check ran on a scratch copy with
`$VERUS_BIN <file>.rs --crate-type=lib --num-threads 4 --triggers-mode silent`, Verus 0.2026.10.04.426d8b0. Logs are
in `$RUN_DIR/agents/R2-data/logs/`.

| # | Kind | What changed | Verdict | Log |
|---|---|---|---|---|
| 0 | Reproduction | Unmodified models | graph_structure 56 verified, 0 errors; temporal 75 verified, 0 errors. Both match the receipts. | `base_graph_structure.log`, `base_temporal.log` |
| 0b | Reproduction | Uplift controls `as-built-without-quiet-premise` and `as-built-delete-rel-without-line-689` applied by hand from model.json | 54v/2e and 53v/3e, at the expected functions | `ctl-*.log` |
| A | (b) Faulty implementation | `checkA/checkA.diff`: `canonical` strips every control character (ADR-0003 table `$ZStrip(..,"*C")`), so the refusal never fires | 54v/2e. Only `theorem_refusals` (lines 241-242) and the Q4 witness fail; all injectivity/cross-store theorems still verify. The first attempt (52v/4e) also dropped the `!contains_ctrl` conjunct. Its two extra failures were proof engineering (no lemma that canonical has no control character). Restoring the now-vacuous conjunct fixed them. That log was overwritten. | `checkA.log` |
| B | (a) Premise test | `checkB/checkB.diff`: `KillCommitted` moves gen forward (`s.gen + 1`); `covered()` no longer requires P-QUIET or the epoch; adds `theorem_monotone_kill_cache_sound` and a fill-and-hit witness | 56v/2e. The new theorem and witness verify. The only failures are the two ABA trace asserts that expect `gen == 0` (lines 1270, 1308). | `checkB.log` |
| B2 | (a) Erroneously permitted step | `checkB2/checkB2.diff`: `witness_gen0_erase_alone_serves_stale_degree` (as-built: read gen 0, count 2, erase, store, serve 2 over 0 entries) and `witness_gen0_repair_refuses` | 58v/0e. The defect trace is permitted as built and refused under the epoch repair. | `checkB2.log` |
| C | (a) Erroneously permitted interleaving + (c) valid outcome | `checkC/checkC.diff`: adds `fwd_ok` (ADR-0009 forward direction); `purge_stale` (decision on the pre-write state, effects after a committed write); `witness_purge_write_race_drops_row`; and two sequential-order witnesses | 78v/0e. The race ends with a live timestamp of a structural predicate and no row: `!fwd_ok`, while the uplift's `rows_ok` still holds. Purge→write and write→purge both keep `fwd_ok` (valid outcomes survive). | `checkC.log` |
| D | (b) Faulty implementation | `checkD/checkD.diff`: `DeleteTemporalEdge`'s survivor test ignores the graph (`has_ts_any_graph`), plus a concrete two-graph witness | 75v/1e. `lemma_delete_rows` fails (line 1729), and `witness_graph_blind_delete_keeps_dead_row` shows `!rows_ok`: a marked row of graph 0 survives because graph 7 holds the triple. Detected. | `checkD.log`, `checkD2.log` |

## Evidence findings

- **Receipts are current.** The latest receipts' input hashes equal the current files: graph_structure prove
  232246Z plus 17 controls, temporal prove 232106Z plus 25 controls. Every control is EXPECTED_FAIL with no
  timeout or resource limit. The superseded FAIL_ELSEWHERE runs are kept and explained, and the equivalence logs exist
  in `agents/B-structure/equiv/`.
- **The native observations have not been integrated.** They exist in `$RUN_DIR/native/` but not in
  `.g5/Verus_verification/receipts/native/`. NOTES and ontology still say "SUSPECTED until probe runs" for results
  that are now observed:
  - OBSERVED: F3 parallel delete, F1 algorithm cache (WCC, `eng3` hit = 1, token 8341 unchanged by the rollback), K4
    NUL split, P-CTRL, temporal F2b bulk fallback, temporal F4 endpoint nodes, F8 stranded row.
  - INCONCLUSIVE: degree ABA, temporal F1 single-edge, F2 retry, F3 R1–R4.
- **A probe crash hides the temporal F1/F2/F3 evidence (R1-6).** The crash is product defect R1-5. The update case also
  loses its pre-crash views because `case_update` records only on return.
- **The scope's tests were not run here (R1-11).** The ontology "Live coverage" links for this scope point at tests
  this uplift did not run. `tests/integration-per-file/summary.txt` covers ledger and erasure only, and the coverage
  map's "Native suites" section is unfilled.
- **Probe design (R1-12).** The probes drive public entry points, compute expectations from the raw window or the L1
  layout, and self-check their verdict functions. Gaps:
  - `parallel_delete_rel` does not require `layout_before == layout(2)`. This run met it anyway.
  - `keys` K3 ignores `p_ctrl`, so it would call a correct outcome a defect if 0x85 were not a control.
  - `write_modes` partial_write treats "nothing written" as OBSERVED_AS_EXPECTED even when the failure happened before
    `WriteStores`. It should check that the error names `AssertTemporalRow`.
  - `algo_cache_rollback` does not use its own hit statistics, and has no `IVG_DISABLE_ALGO_CACHE=1` arm to separate
    an `^ArnoKG`/`^NKG` cause.
  - `rollback_counters` R1 does not confirm the temporal op ran before the refusal.
  - `degree_aba` cannot open the window (above).

## Findings-register check

- **Missing entirely.** `bugs_issues.md`, `open_questions.md` and `design_simplification.md` contain only redaction
  items. `findings.md`, linked from `bugs_issues.md` line 3, does not exist. Nothing from graph structure or temporal
  is recorded.
  - Missing bugs, with natively confirmed ones in bold: **F3 parallel delete**, **algorithm-cache rollback**, **K4 NUL
    split** (invisible to `verify_graph`: `verify_graph("g5k")` answers `ok` with `sqlEdges 0` while the orphaned
    `"g5k\x00"` row exists), **R1-5 empty-window aggregate**, **temporal F2b bulk fallback**, **F4 endpoint nodes**,
    **F8 stranded row**.
  - Missing suspected bugs: degree ABA F2 (Medium), temporal F1 (Medium, partly corroborated), temporal F3 (Medium,
    conditional on P-INCR), F2 partial write, the write/purge race (a known open defect, spec 254), R1-9 delete
    rollback residue, and intent F4–F11 (concurrent keyed writers, restore multiplicity, mode-off ekey, `verify_graph`
    false drift on parallel edges, partial indexed rebuild, `^NKG` interning in the callback, swallowed callback
    statuses, PersistQuals reweight).
  - Missing simplifications: S4 (`Indexed()` guard at line 689, proved), the epoch repair (proved), bumping the token
    after rollback (proved for the model), the temporal S2/S3, and the alternative from Check B (`$Increment` gen in
    `RemoveSource` instead of Kill). That alternative leaves one residue node per erased source, and RemoveGraph and
    RemoveAll still need the epoch.
  - Missing questions: Q1 (update aggregates), Q4 (Python vs IRIS control set), Q5 (canonical SQL `graph_id`),
    multigraph FR-007/FR-013, `structure.rebuilt.rollback`, explicit delete of a marked row.
- **Wrong classification.** These are recorded as questions or "suspected" but are confirmed product defects:
  - Graph-scope Q5/K4.
  - The `structure.multigraph.ledger` observation.
  - The `structure.rebuilt.rollback` observation. The (a)/(b) policy choice stays open.
  - The write/purge race, which `temporal.write.concurrency` lists as a question. It violates decided ADR-0009 and is
    a known product defect.
- **Unsupported claims.**
  - Ontology "Live coverage" for unrun tests (R1-11).
  - `graph.names` "not checked live" is now stale in the opposite direction.
  - The NOTES statuses that predate the probe runs.

## Summary of material findings

Findings from R2-data. "Native" means observed in `$RUN_DIR/native/` or the probe traces there.

| ID | Sev | Category | Finding | Owning artifact | Proposed correction |
|---|---|---|---|---|---|
| R1-1 | High | missing or stale evidence | The findings register, coverage map and runbook carry nothing from graph structure or temporal; `findings.md` link broken; native results not integrated | `.g5/Verus_verification/{bugs_issues,open_questions,design_simplification,coverage}.md`, both model NOTES | Add the entries listed above with severity and raw-observation links; add coverage rows per clause; update NOTES/ontology statuses from the 2342–2346Z observations |
| R1-2 | High | product defect | Ledger `delete_rel` on a multigraph triple kills the survivor's adjacency (LedgerApply.cls:689); confirmed in code and natively in both graphs | register; `structure.multigraph.ledger` | Bug entry; S4 plus keyed repair as the proposal; Cypher MATCH vs traversal disagree afterwards |
| R1-3 | Medium | product defect | Algorithm cache serves an answer over a rolled-back write; native WCC hit at an unchanged token | register; `structure.rebuilt.rollback` | Bug plus open policy (a)/(b); evidence → Observed |
| R1-4 | Medium | product defect + model error | NUL-padded name: two SQL graphs share one index graph; orphan row without adjacency is invisible to `verify_graph` (native K4). Key L1 is injective only modulo `canonical` (Check A) | register; `graph.names`/`graph.key.derive`; model §1 | Bug; add an L1 obligation "every writer's SQL `graph_id` = `ForName(name)`" and model `create_edge`'s raw binding against it |
| R1-5 | Medium | product defect (new) | `get_temporal_aggregate(min/max/avg)` over an empty window raises `ValueError` (`str(None)` = 'None', iris_sql_store.py:2987), though documented "0 or 0.0, never None"; seen in 6 probe traces | register; `temporal.stats` | Bug; add the empty-window rule as an `I` statement with the observed divergence |
| R1-6 | Medium | missing or stale evidence | Temporal F1 single-edge, F2 retry and F3 R1–R4 are INCONCLUSIVE (probe crash on R1-5); update case lost data; only bulk_fallback_update corroborates F1 | temporal probes; temporal NOTES | Read only count/sum or catch per metric, record incrementally, rerun; keep F3 SUSPECTED, conditional on P-INCR |
| R1-7 | Medium | model error / missing intent | Temporal L1 lacks ADR-0009's forward implication; model cannot represent the write/purge (or delete) race, a known open defect (spec 254 tasks.md:80-81); explicit `delete_edge` of a marked row permitted silently | `temporal.rs`; `temporal.structural`, `temporal.write.concurrency` | Add `fwd_ok` with enumerated exceptions and a split purge action (Check C); register the race as a bug; add a question on explicit deletion of a marked row |
| R1-8 | Medium | product defect (suspected) | Degree-cache ABA: confirmed from code and model (Checks B, B2); natively unreachable by stress | register; graph_structure NOTES; `structure.degree.cache.erase` | Bug, SUSPECTED, Medium; add the retire_bare_nodes, erase_graph and %BuildIndices routes; record the Check B alternative repair |
| R1-9 | Medium | missing intent / product defect (suspected) | A rolled-back temporal delete or node erasure leaves the event counter decremented (`$Increment(-1)`, Kill-at-0 restored as 0); model encodes in-transaction Delete/Purge as no-ops | `temporal.rs` step(); `temporal.delete`, `temporal.erase`; register | Represent it or exclude it with a reason; register as the mirror of F3; probe with START TRANSACTION, `delete_edge_temporal`, ROLLBACK |
| R1-10 | Low | correspondence error | tGen = 0 ABA route claimed without a witness; extra kill routes not listed | graph_structure NOTES/model | Adopt the Check B2 witness; list the routes |
| R1-11 | Medium | missing or stale evidence | "Live coverage" links for this scope point at tests not run in this uplift | ontology metadata; `coverage.md` "Native suites" | Run the cited e2e and integration files at baseline, or label them "exists, not run here" |
| R1-12 | Low | missing or stale evidence | Probe discrimination gaps (preconditions, P-CTRL conditioning, failure-site check, cache-hit attribution, op-executed check) | probes | Tighten each judge as listed in Evidence findings |
| R1-13 | Low | incorrect intent (scope) | `temporal.structural.end` is unqualified; the non-indexed `DeleteTemporalEdge` removes an explicit edge's adjacency (no row check) | `temporal.g5.md` | Qualify "with the adjacency index declared" and record the legacy divergence |
| R1-14 | Low | missing or stale evidence | `graph.names` says the control class is not checked live; it now is (0x80–0x9F refused, 0xA0 accepted); K3 refusal surfaces as SQLCODE -400 | `graph-scope.g5.md` metadata; Q4 | Update evidence; note the error class for Q4 |
