# Design simplifications — IVG initial Verus uplift

Proposals only; nothing here is implemented. Each says what makes the current design complicated, what would change, the behavior that must survive and a case that would show a safe change. Index: [findings register](findings.md).

<a id="simp-001"></a>
### Claim the redaction marker for one run, under the head lock, before the first batch

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/ledger_redaction/20261114T044401Z-prove/receipt.json) → [Proposed simplification](results/ledger_redaction/20261114T044401Z-prove/receipt.json)

Scope qualification: both sides are the same Verus model ([redaction.rs](models/ledger_redaction/redaction.rs)); the as-built side is `witness_concurrent_targets_break_the_marker` under `Variant { serial: false, repaired: false }`, the proposal is `witness_repair_refuses_the_interleaving` under `repaired: true`. These are finite witnesses, not state counts; the serialised invariant (`lemma_step_preserves_inv`) is proved for the as-built design only.

What is complicated now: `LedgerRedact.Redact` checks the marker and liveness outside the head lock; the marker is written lazily by the first batch that finds a match; `BatchInLock` and `FinalInLock` never compare the marker with their own target; counters and the redacted-revision list live under the marker and are shared by any run. Correctness therefore depends on callers never running two redactions at once, and readers, commits and receipts all derive their view from a marker no run owns.

Proposal: in the first batch's transaction, under the head lock, re-run the liveness check and write the marker with the run's target digest and a run token; refuse a batch or final step whose token is not the marker's; let a later call of the same target take over a stale token. The "started" state and the separate entry check disappear.

Behavior to preserve: resuming the same target after a pause, error or process death; refusing a different target while one is unfinished; a re-run of a finished target writes nothing and leaves no marker; readers and target commits refused only while a run is unfinished; batches still release the head lock between transactions.

Distinguishing case: the schedule of `redaction_concurrent_targets` (two targets started while a long commit holds the head lock) — the second run must be refused with `redaction_in_progress`, and each completed target must have its own redaction revision.

<a id="simp-cyp-001"></a>
### Name each compiled Cypher class by its code's digest instead of the shape's CRC-32

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/platform/20261114T002651Z-prove/receipt.json) → none

Scope qualification: the as-built side is the witnesses `witness_collision_swaps_the_class_mid_run`, `witness_collision_leaves_another_shapes_code_under_an_ok_entry`, `witness_straggler_recompiles_for_an_old_layout` and `witness_readback_trusts_the_entrys_class` in [platform.rs](models/platform/platform.rs), finite traces rather than state counts; no proposal variant was run. Review R3-platform's scratch check Adv-2 showed that a shape check in `Build` alone closes W-O2b but not W-O2a.

What is complicated now: the class name `IVGC.P<$ZCRC(shape,7)>` (`Gen.cls:69, 183`) is shared by colliding shapes, so `For` must compare the stored shape (`:71`), rebuild the same class for each colliding shape in turn (thrash), check the class name (`:73`) and the lines' SHA-256 digest (R311), and still cannot stop a class changing under a run ([bug-cyp-001](bugs_issues.md#bug-cyp-001), [bug-cyp-007](bugs_issues.md#bug-cyp-007), [bug-cyp-008](bugs_issues.md#bug-cyp-008)).

Proposal: name the class by the SHA-256 already computed for its lines (or by a per-entry sequence) and record it in the entry; have `Build` require the entry's shape and stamp to match the lines it compiles; optionally store shape and stamp as class parameters and compare them in `RunA`.

Behavior to preserve: one class per shape and layout; interpreted until built; R311's digest check; a deploy and `Gen.DropAll()` still discard every class.

Distinguishing case: two shapes forced to one CRC-32 by a test hook, run alternately in job and sync mode; each run executes only its own shape's code and no rebuild thrash occurs. Governing statement: [query.compiled.integrity](../ontology/features/cypher.g5.md#query.compiled.integrity).

<a id="simp-002"></a>
### Put a relationship's endpoints in every relationship record so redaction never has to look them up

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/ledger_redaction/20261114T044401Z-prove/receipt.json) → none

Scope qualification: the as-built side is `witness_unattributed_qualifier_survives` and `lemma_complete_run_removes_every_target_record` (which needs premise P_ends); no proposal model was run.

What is complicated now: qualifier records (`set_qual`, `remove_qual`) carry only a statement id. `LedgerRedact.Matches` reconstructs the endpoints from a pre-pass over create/delete records (process-private `^||IVG.RedactStmt`), the live statement map, and the statements tombstoned by the run (`("redacting","stmt")`). When none of these knows the statement — a statement assigned to an edge written outside the ledger and erased since — the record is left in place and counted as `unattributed_records`.

Proposal: when the ledger assigns a statement (`assigned_stmt`) or writes any qualifier record, include the tuple (source, target, graph) in the record (or always write a `create_rel` record when a statement is first assigned). Matching then reads only the record itself; the pre-pass, the private global and the redacting-statement set can go.

Behavior to preserve: the canonical form and digest of every existing record (old records keep their layout; the reader must accept both); replay and diff results; the record count of a commit if the create-on-assign variant is chosen must be documented.

Distinguishing case: `redaction_unattributed_qualifier` — the qualifier record must become a tombstone and `unattributed_records` must be 0.

<a id="simp-003"></a>
### Derive redaction's liveness check from the eraser's store inventory

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/ledger_redaction/20261114T044401Z-prove/receipt.json) → [Proposed simplification](results/ledger_redaction/20261114T044401Z-prove/receipt.json)

Scope qualification: the as-built side is `lemma_checked_implies_content` with witnesses W2 (temporal-only) and W3 (whole default graph); the proposal side is `witness_full_check_refuses_the_gaps` under `full_check: true`, in the same model.

What is complicated now: `LedgerRedact.LiveRows` keeps its own list of four tables and its own graph-blindness rule (only with a prefix), separate from `Graph.KG.GraphStores`, the inventory the eraser derives its work from. The two lists already disagree: the temporal index and a whole-default-graph target's named-graph node rows are content to the eraser but not to the liveness check.

Proposal: answer "is the target live?" from the same inventory the eraser uses, with one graph-blindness rule for every default-graph target (prefix or not), as spec 256 plan.md states.

Behavior to preserve: the separator boundary (`acme` is not blocked by live `acme-health|` rows); the refusal message naming the stores that are live; a target whose content was erased is not refused.

Precondition (review round 3 R3-3): the last property holds only once the prefix erase itself reaches every store the full check reads. Under the as-built `EraseNodes`, which selects IDs from node rows, a full check would refuse every prefix redaction of a tenant with temporal-only events whose endpoints have no node row ([bug-led-007](bugs_issues.md#bug-led-007)) or with property rows that have no node row ([bug-led-010](bugs_issues.md#bug-led-010)), until those are erased by ID. So this simplification depends on bug-led-007's erase repair (and bug-led-010's). Distinguishing cases a repair must pass: [erasure_prefix_temporal_only](receipts/native/erasure_prefix_temporal_only.json) (after the prefix erase, no event of the tenant is readable and the redaction completes) and [redaction_orphan_prop_blocks](receipts/native/redaction_orphan_prop_blocks.json) (after the prefix erase, the redaction completes without an explicit-id erase); in the model, W5 `witness_prefix_erase_leaves_temporal_only_content` and W6 `witness_orphan_prop_row_blocks_prefix_redaction` must stop holding.

Distinguishing cases: `redaction_temporal_only_live` and `redaction_default_graph_whole` must both be refused with `target_live`, and `test_live_acme_health_nodes_do_not_block_redacting_acme` must still pass.

<a id="simp-str-001"></a>
### Delete a relationship through one Eraser path, whatever the caller

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — no model run compares the as-built deletes with the proposal.

What is complicated now: four paths delete a relationship row: `delete_edge` (`nodes_edges.py:1382-1456`), Cypher `DELETE r` (`translator.py:10699-10712`), ledger `DeleteRelInternal` (`LedgerApply.cls:652-693`) and `Eraser.EraseEdgeRow` (`Eraser.cls:641-677`). Each removes a different set of satellites (reifications, edge embeddings, ledger tuple and statement entries, adjacency), and the ledger path adds its own adjacency call that breaks multigraph triples ([bug-str-001](bugs_issues.md#bug-str-001), [bug-str-013](bugs_issues.md#bug-str-013)).

Proposal: route `delete_edge`, Cypher relationship `DELETE` and the ledger's relationship delete through `Eraser.EraseEdgeRow` (by edge ID), so the satellites and the adjacency move in one transaction by one rule.

Behavior to preserve: `delete_edge`'s return value and graph scoping; the ledger's record of the delete in the same transaction; Cypher's per-graph correlation of the deleted rows; nesting in a caller's transaction.

Distinguishing case: delete one of two parallel edges that has a reification and an edge embedding through each path; afterwards the survivor keeps its adjacency, and the deleted edge's reification, vector and live statement are gone in every case. Governing statement: [erasure.entry-points.single-path](../ontology/features/erasure.g5.md#erasure.entry-points.single-path).

<a id="simp-srch-001"></a>
### One fusion function with an explicit absent-rank rule and per-leg failure reporting

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — no model run covers fusion.

What is complicated now: four RRF implementations rank the same inputs differently: the engine (`vector.py:1444-1446`, absent rank from the leg's length), the SQL procedure (`schema.py:2536-2537`, 1e9), `ivg.retrieve` (`translator.py:3342-3352`, 0) and `fusion.py:56-58` (0); one `try` turns a failed leg into an empty answer ([bug-srch-005](bugs_issues.md#bug-srch-005), [bug-srch-010](bugs_issues.md#bug-srch-010)).

Proposal: one function, called by the engine, the operators and `fusion.py`, with an absent item contributing 0 (or one documented constant) and a failed leg raised or reported by name; the SQL procedure and `ivg.retrieve` document the same rule.

Behavior to preserve: per-graph scoping of each leg; the empty-text skip; the default `c`.

Distinguishing case: A at vector rank 1 only and B at rank 50 in both legs of 200 (c=60): B must rank first on every entry point. Open part: [search.fusion.absent](../ontology/features/search.g5.md#search.fusion.absent). Governing statement: [search.fusion](../ontology/features/search.g5.md#search.fusion).

<a id="simp-plt-001"></a>
### Enforce strict ledger mode once, on the server, instead of in each Python engine

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/platform/20261114T002651Z-prove/receipt.json) → none

Scope qualification: the as-built side is `witness_ttl_window_admits_a_write_after_set_strict`, `witness_failed_probe_admits_a_write`, `witness_undocumented_bypasses_break_the_contract` and `witness_class_absent_cached_for_the_engines_lifetime` in [platform.rs](models/platform/platform.rs); controls `g-ttl-zero` and `g-fail-closed` show the first two depend on the cache and the fail-open path. No server-side gate variant was run.

What is complicated now: the strict check exists only in Python, as a per-engine probe cached for 5 s that fails open (`ledger/guard.py:20, 38-59`), called method by method; no ObjectScript writer reads `^IVG.Ledger("meta","strict")`. Paths without the call bypass it (`bulk_delete_adjacency` and the sample API's raw cursor, undocumented; FHIR sync and the MCP Cypher tool, undecided), an engine that first checked before the ledger classes existed never enforces it ([bug-plt-025](bugs_issues.md#bug-plt-025)), and another engine can write for up to 5 s after `set_strict(True)` ([bug-plt-005](bugs_issues.md#bug-plt-005), [bug-plt-006](bugs_issues.md#bug-plt-006), [q-plt-001](open_questions.md#q-plt-001)).

Proposal: read the strict flag in the ObjectScript writers' shared entry (or in the Eraser and the adjacency writers), so every path that changes structure checks it at write time.

Behavior to preserve: the documented exemptions (BulkLoader, raw SQL, the marked temporal row), the rejection counter, the ledger's own writes, and the error type `LedgerStrictModeError` at the Python surface.

Distinguishing cases: the TTL window (a second engine's `create_node` 1 ms after `set_strict(True)`), `bulk_delete_adjacency` and FHIR sync under strict. Governing statement: [ledger.strict](../ontology/features/ledger.g5.md#ledger.strict).

<a id="simp-cyp-002"></a>
### Carry each node binding's graph through Cypher translation instead of correlating graphs by regex afterwards

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — no model run covers the translator.

What is complicated now: the all-graphs rule is added after translation by regular expressions over join and sub-SELECT text (`translator.py:564-1035`); it took surface-by-surface fixes from 2026-10-20 to 2026-11-10 (`56de32f5`, R157, R158, R192, R226/R260 `c3a05900`, R308 `ecc07c57`, R310, R319, `b1af594e`, 4.7.0 row 11, the 4.6.1/4.6.2 shortestPath fixes), and correlation is skipped from a one-table probe ([bug-cyp-005](bugs_issues.md#bug-cyp-005)).

Proposal: make a node binding `(alias, graph_expr)` from the start; emit every join and sub-SELECT with the graph equality; treat `USE GRAPH` as binding `graph_expr` to a literal.

Behavior to preserve: the plans IRIS gets when only one graph exists (`translator.py:783-785`), the LEFT JOIN null-row placement (`:730-733`), and every row of the e2e write matrix.

Distinguishing case: a pattern comprehension or `EXISTS {}` over a node ID shared by two graphs, a spelling the regexes may miss. Governing statement: [query.graph-scope.read](../ontology/features/cypher.g5.md#query.graph-scope.read).

<a id="simp-str-002"></a>
### Give the inverse of a graph key one owner in GraphKey

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — the graph-key model proves the forward keys only.

What is complicated now: several sites turn an index key back into a SQL `graph_id` on their own (`Adjacency.cls:583, 627, 654, 698, 889`, `AssertTemporalRow`, `Retract*`, `OtherEdgeKeys`, Python `delete_edge`), an undeclared third derivation outside `GraphKey` that is right only while `ForIndex(g) = ForName(g)` for named graphs (ADR-0003); the ledger's redaction code spells record graphs with an inline `$Translate` too ([simp-led-001](#simp-led-001)).

Proposal: add `GraphKey.NameOf(indexKey)` (or pass names to those methods) and use it at every site.

Behavior to preserve: every SQL `COALESCE(graph_id,'')` predicate; default and named graph rows.

Distinguishing case: default- and named-graph rows deleted through each site. Governing statement: [graph.key.owner](../ontology/concepts/graph-scope.g5.md#graph.key.owner).

<a id="simp-str-003"></a>
### Bump the version token before ending a rebuild so the warm stamp survives it

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — the warm stamp is not represented in the model.

What is complicated now: `BuildKG` bumps the token after `EndRebuild(1)` (`TraversalBuild.cls:142-145`), so the whole-graph warm stamp written during the rebuild is stale at once and the O(1) bulk readers fall back after every `sync()`, against ADR-0012 and `Adj.cls:180-183`.

Proposal: bump the token before `EndRebuild(1)`.

Behavior to preserve: the token still moves on every rebuild; readers during the rebuild still see it as not current.

Distinguishing case: `AllWarm(g) = 1` right after `BuildKG` with no writer. Governing statement: [structure.degree.cache.warm](../ontology/features/graph-structure.g5.md#structure.degree.cache.warm).

<a id="simp-tmp-001"></a>
### Remove the unadopted spec-246 Python path for temporal structural rows

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — the Python legacy path is not represented in the temporal model.

What is complicated now: besides the server-side `AssertTemporalRow`/`RetractTemporalRow`, the engine keeps the `temporal_structural_rows` keyword, `_own_structural_row`, `_owned_structural_row`, `_triple_survives`, a flag branch of `delete_edge_temporal` and `migrations/temporal_structural_rows.py` (spec 246 "not adopted"); this path ignores the temporal-only registry ([bug-tmp-006](bugs_issues.md#bug-tmp-006)).

Proposal: remove the path, or make the migration delegate to `TemporalPolicy.BackfillRows`.

Behavior to preserve: an idempotent backfill with a read-only dry run.

Distinguishing case: flag on, predicate opted out, write: with the path removed no row appears. Governing statement: [temporal.structural](../ontology/features/temporal.g5.md#temporal.structural).

<a id="simp-srch-002"></a>
### Check embedding identity against the registry row the route lookup already read

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: [As-built](results/search/20261114T000543Z-prove/receipt.json) → [Proposed simplification](results/search/20261114T000543Z-prove/receipt.json)

Scope qualification: both sides are `witness_identity_fail_open` in [search.rs](models/search/search.rs): its as-built branch (a cached route plus a failed identity read) admits the mismatched writer, and its fail-closed branch, the one raise-on-error policy proposed here, refuses it; control `repair-fail-closed-off` shows the refusal depends on the repair. Finite witnesses, not state counts.

What is complicated now: a write reads the registry twice, once in `_read_route` (raises on error, R161) and again in `get_embedding_identity` (swallows every error, `schema.py:1054-1056`), and the second read decides the identity check ([bug-srch-012](bugs_issues.md#bug-srch-012)); the queue's enqueue check reads a third, wrong table ([bug-srch-006](bugs_issues.md#bug-srch-006)).

Proposal: let `enforce_embedding_identity` use the row `_read_route` returned, with one raise-on-error policy, and give `enqueue_for_embedding` the same route-based check.

Behavior to preserve: refusal before anything is queued or written; "no registry" (SQLCODE -30) still passes as documented.

Distinguishing case: a cached route plus a failing identity read must refuse a mismatched mechanism. Governing statement: [search.embedding.check_on_write](../ontology/features/search.g5.md#search.embedding.check_on_write).

<a id="simp-plt-002"></a>
### Make the engine's Owner fallback uniform across algorithms

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — no model covers algorithm routing.

What is complicated now: for PageRank, WCC and CDLP the engine re-calls the same Owner after the store's Owner failed (`_engine/algorithms.py:797-804, 823-828, 845-849`), while PPR raises (R127); `Proof.from_dict`'s IN_SCOPE filter is dead code given the all-or-nothing validation (A-platform F-A8).

Proposal: raise after the store's Owner fails for every algorithm, and remove the dead filter.

Behavior to preserve: a native failure still yields the Owner's answer.

Distinguishing case: a store whose Owner raises: every algorithm raises once, with no second Owner call. Governing statement: [algorithms.routing.fallback](../ontology/features/algorithms.g5.md#algorithms.routing.fallback).

<a id="simp-plt-003"></a>
### Write FHIR graph labels through the adjacency writer that owns the label index

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — FHIR is not modelled.

What is complicated now: `FHIRGraph` sets `^KG("label")` directly in `EnsureNode`, `SyncProps` and `DropNode` (`FHIRGraph.cls:2477-2616`), beside the `rdf_labels` functional index, with no version-token bump (A-platform F-B10; A-ops hazard (a)8).

Proposal: call `Adjacency.PutLabel`/`RemoveLabel`.

Behavior to preserve: the FHIR sync's output graph.

Distinguishing case: a sync followed by `verify_graph` and the token: same labels, and the token moves. Governing statement: [fhir.sync](../ontology/features/fhir.g5.md#fhir.sync).

<a id="simp-plt-004"></a>
### Rebuild adjacency once after load_networkx

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — bulk loading is not modelled.

What is complicated now: `load_networkx` runs `rebuild_all_indices` and then `BuildKG` in indexed mode, rebuilding adjacency twice (A-platform F-B11).

Proposal: run one rebuild.

Behavior to preserve: the resulting `^KG`.

Distinguishing case: compare `^KG` dumps and the token delta with one and with two rebuilds. Governing statement: [install.bulk_load.rebuild](../ontology/concepts/install.g5.md#install.bulk_load.rebuild).

<a id="simp-plt-005"></a>
### Retire the leftover schema-state helpers that are process-global or probe retired classes

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — not modelled.

What is complicated now: `IRISCapabilities.graphoperators_deployed` probes a class FR-015 retired (`capabilities.py:15`; `schema.py:2837`); `GraphSchema.last_deploy` is process-global (`schema.py:2908-2921`); `runs_in_ivg_schema` swaps `self.conn` on a shared engine (`schema_name.py:512-527`), unsafe when an engine is shared across threads, as `cypher_api` does under `_engine_lock` only (A-platform F-S11).

Proposal: drop the probe, keep the deploy result per engine, and use a per-call rewritten cursor.

Behavior to preserve: the schema rewrite seen by each call.

Distinguishing case: two threads on one engine, one inside `runs_in_ivg_schema`: the other keeps its own connection. Governing statement: [install.deploy](../ontology/concepts/install.g5.md#install.deploy).

<a id="simp-cyp-003"></a>
### Mark a compiled entry failed when its walk raises, so the interpreter answers next time

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — the compiled-plan model does not represent a raising walk.

What is complicated now: a compiled walk that raises falls to the SQL path, as the fallback rule allows, but the entry stays `ok`, so the shape pays a failed native run and a SQL run on every call until a deploy, warned once per engine (A-cypher F12).

Proposal: in `RunA`'s caller, mark the entry failed when `Walk1` raises.

Behavior to preserve: the SQL fallback for this call; a deploy or stamp change still allows a fresh build.

Distinguishing case: a shape whose compiled walk raises: the second call is answered by the interpreter, not SQL. Governing statement: [query.compiled.fallback](../ontology/features/cypher.g5.md#query.compiled.fallback).

<a id="simp-led-001"></a>
### Spell record graphs in redaction through GraphKey instead of an inline translate

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Comparison: none — the redaction model treats the graph spelling as given.

What is complicated now: `LedgerRedact.Matches`, `PrePass` and `DropStatements` turn record graphs into names with an inline `$Translate`, a fourth spelling of the graph-key rules that ADR-0003 asks to keep in `GraphKey`.

Proposal: call `GraphKey.ForName` (or the inverse in [simp-str-002](#simp-str-002)) at those sites.

Behavior to preserve: the redaction target digest and the matching of default-graph records.

Distinguishing case: redact a named graph and the default graph with a prefix; the same records are tombstoned before and after. Governing statement: [redaction.target](../ontology/features/redaction.g5.md#redaction.target).

## Observations and documentation drift

<a id="simp-str-005"></a>
### Drawing degree generations from the version token is not a repair

Severity: Unranked

Run: Uplift 2026-11-13

Comparison: [As-built](results/graph_structure/20261114T000451Z-prove/receipt.json) → [Proposed simplification](results/graph_structure/20261114T000451Z-prove/receipt.json)

Scope qualification: the as-built side is `witness_aba_delete_and_recreate_serves_stale_degree`; the proposal side is `witness_s1_set_generation_is_undone_by_rollback`, which shows the proposal reviving an old entry after a rollback. Finite witnesses, not state counts.

Rejected proposal (A-structure S1): `Set ^KG("gen",g,s) = $Increment(^KG("__version"))` in place of the two `$Increment`s. A `Set` is journaled, so a rollback restores the pre-image over a concurrent writer's committed generation and revives an old cache entry; the product's `$Increment` of `gen` is load-bearing (ADR-0012:23-24). The epoch stamp in [bug-str-003](bugs_issues.md#bug-str-003) is the proposed repair instead. Governing statement: [structure.degree.cache](../ontology/features/graph-structure.g5.md#structure.degree.cache).
