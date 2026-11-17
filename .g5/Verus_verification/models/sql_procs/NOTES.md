# sql_procs — notes (iteration 53, Part B)

Scope: the graph SQL procedures of `Graph.KG.SqlProcs` left unbound after iteration 47 (its HANDOFF "Part C"):
`MatchEdges`, `MatchEdgesAllGraphs`, `DijkstraPath`, `backfill_temporal_rows`, `rebuild_edge_indices`. Predictions were
frozen first ([sqlprocs-PAIRS.md](../../../uplift/consolidated/iteration-53/sqlprocs-PAIRS.md), commit `ff7d3528`); the
raw probe is [sqlprocs-observed-20261117T050743Z.json](../../../uplift/consolidated/iteration-53/sqlprocs/sqlprocs-observed-20261117T050743Z.json)
(namespace `I53P`).

## What the model owns and what it delegates

| Entry | Model terms | Decision from inputs |
|---|---|---|
| `MatchEdges(src, pred, shard, graph)` | `scan_hit`, `match_edges`, `graph_key`, `scan_w`; since iteration 56 `GArg`, `after_nul`, `after_empty`, `subscript_of`, `graph_arg_key`, `match_edges_arg` | graph '' / NULL / 0 / omitted → key 0 (the default graph only); empty source → every source; empty predicate → every predicate; `shard` never read; `w` is the leaf, 1.0 when none |
| `MatchEdgesAllGraphs(src, pred, shard)` | `all_hit`, `match_all` | every graph key, each edge with its graph (a triple in two graphs answers twice) |
| privilege | `gate`; since iteration 56 `require`, `first_missing`, `first_act`, `holds_priv`, `any_role`, `check_priv`, `select_ok`, `insert_ok`, `match_edges_sql` | `RequireSelect(rdf_edges)` for the three readers, `RequireWrite(nodes, rdf_edges, "i")` for the backfill; the verdict is derived from the caller's grants: `%All` passes first; otherwise the login or any role in `$Roles` must hold the privilege on the table or its schema (column privileges do not count, premise P-CHECKPRIV); the first missing table and privilege is named |
| the Cypher hop, `IVG_EDGESCAN=1` | `plan`, `rel_weight`, `hop_targets` | no `USE GRAPH` / `USE GRAPH ''` → the scan; a named graph → rows; a scan alias's relationship property is `NULL` |
| `DijkstraPath` | `dijkstra_json`, `dijkstra_path`, `sql_end` | weight property and direction checked in ObjectScript (raise); "" endpoint → no path; equal endpoints → the empty path; SQL '' arrives as `$Char(0)`; the search itself is **delegated** to the `weighted_paths` model (DijkstraJson) |
| `backfill_temporal_rows()` | `Bf`, `structural`, `backfill_rows`, `backfill_count`, `rows_written` | a structural temporal triple with no row gets a marked row; an existing row (marked or explicit) is left alone; temporal-only predicates are skipped; the answer is the number of triples walked |
| `rebuild_edge_indices(schema)` | `rebuild` | identifier check first; `BUILD INDEX` on four tables; refusal or a missing table raises naming the table; success answers 4 |

## Theorems (16 verified, vstd only; no `assume`, `admit` or `external_body`)

- Scan: `theorem_empty_predicate_every_predicate` (general over every adjacency list, source, shard and graph),
  `theorem_shard_ignored`, `theorem_graph_scoped_vs_all`, `theorem_shared_triple_once_per_graph` (witness of the
  all-graphs shape for any two arcs).
- Privilege: `theorem_entries_gated`.
- IVG_EDGESCAN: `theorem_edgescan_reads_null_property` (**bug-cyp-133**), neighbor `theorem_unweighted_and_named_agree`.
- DijkstraPath: `theorem_sql_entry_refuses_bad_arguments`, `theorem_sql_empty_endpoints_zero_path` (**bug-str-112**),
  neighbors `theorem_dijkstra_endpoint_neighbors`.
- Backfill: `theorem_backfill_writes_missing_only`, `theorem_backfill_idempotent_same_count`,
  `theorem_backfill_count_overstates` (**bug-tmp-107**), neighbor `theorem_backfill_count_exact_when_all_missing`.
- Rebuild: `theorem_rebuild_answers_four_or_raises`.

Controls (12, all EXPECTED_FAIL in their named functions, first run): `shard-partitions`, `default-reads-every-graph`,
`empty-predicate-matches-none`, `all-graphs-default-only`, `no-select-check`, `scan-exposes-weight`,
`sql-entry-unchecked`, `nul-read-as-empty`, `count-written-rows`, `optout-backfilled`, `backfill-marks-existing`,
`rebuild-refusal-answers-zero`. Receipts: [prove](../../results/sql_procs/20261117T051149Z-prove/receipt.json),
`results/sql_procs/20261117T0511*-control-*`.

## Binding

`binding.py` drops and re-creates namespace `I53Q` (from `%SYS`, container `ivg-cont-20261117-iris` only), writes one
history through the public API and calls each SQL entry as `_SYSTEM` and as three users `i53q_*` (deleted afterwards).
Expected answers come from a Python port of these spec functions applied to the written history; the search's
expected path is a port of the documented rule (cheapest path within `maxCost` and a positive `maxHops`, weights
`<= 0` or none as 1, direction, predicates, graph), never the product's answer. **AGREES 224 cases**, all 12
mutations and the tampered observation (`hop_nograph_1`) detected
([receipt](../../results/sql_procs/20261117T051429Z-binding/receipt.json)).

## Premises and limits

- P-INDEX: the adjacency index is declared, so `^KG` and the rows agree (the scan and the rows plan read the same edges).
- P-SEEN: fewer distinct temporal triples per graph than the backfill's seen limit (100,000); past it a triple is walked,
  and counted, again.
- The search (cost order, hop states, ties) is `weighted_paths`' claim; this model binds the SQL entry in front of it.
  The binding's search port has no ties in its fixture.
- Multigraph: `create_edge` of a parallel edge answered False on a multigraph-enabled graph (the keyed writers were not
  driven), so the scan's one-leaf answer for parallel edges is not observed.
- The rebuild's effect on `^KG` (BUILD INDEX recreates the functional adjacency index from rows) is observed only as
  "rows and scan unchanged"; a `^KG` entry without a row was not constructed.
- `shard` has no documented meaning; the owner states it is not read.

## Iteration 56: repairs for independent review round 3 (review-53-55 F4 and a minor)

**F4 (the privilege verdict was an input).** Until iteration 53 `gate(holds, t)` took whether the privilege holds as
given, so `theorem_entries_gated` was true by definition and two products (column SELECT accepted, or refused) both
satisfied it. Now `require(c, sch, ts, acts)` derives the verdict from what IRIS records for the caller (`Caller`:
`%All`, the login's table / schema / column privileges, the roles in `$Roles`), transcribing `SqlPrivilege`
`RequireSelect` 18-29, `RequireWrite` 37-55 and `Holds` 106-121. The one provider fact is P-CHECKPRIV:
`$SYSTEM.SQL.Security.CheckPrivilege(grantee, 1, table, a)` counts a table or schema privilege and not a column
privilege (ADMIN_GUIDE 576 states the same intent), observed by the binding. New theorems: `theorem_all_passes`,
`theorem_single_check_iff_holds` (general, one table and action), `theorem_column_only_select_refused`,
`theorem_table_schema_role_select_pass` (any role index), `theorem_write_names_first_missing` (table order, and
`backfill_sql(insert_ok(c, sch), st)` follows it). Controls: `column-grant-counts`, `schema-grant-ignored`,
`roles-ignored`, `all-not-shortcut`, `first-table-only` (its first receipt is ERROR, `reveal_with_fuel` on a function
the mutation made non-recursive; the control now keeps the recursion; receipt kept).
`theorem_entries_gated` stays as the entries' delegation (what each entry does with a verdict).

**MatchEdges' graph argument (minor).** `graph_key` was the identity, so the normalization of `''`, `$Char(0)`, 0 and
`'0'` was encoded by representation. Now `GArg` is the raw argument and `graph_arg_key` applies the body's two steps
(line 52 `$Char(0)` → `""`, lines 55-57 `""` → 0) and the subscript collation (`"0"` is the number 0, provider).
`theorem_default_graph_spellings`; controls `nul-not-normalized`, `empty-not-default`, `zero-text-is-a-name`.

`theorem_readers_check_rdf_edges` makes the three reading entries' own choice of table (rdf_edges) a modeled decision
(`match_edges_sql`, `match_all_sql`, `dijkstra_sql`; control `readers-check-nodes`).

Results: [prove](../../results/sql_procs/20261117T070359Z-prove/receipt.json) **27 verified** (was 16); **21/21
controls EXPECTED_FAIL** (9 new; `results/sql_procs/20261117T0704*-control-*`); binding **AGREES 273** (was 224) in the re-created namespace `I56Q` (was `I53Q`): eight users `i56q_*` whose expected verdict
is computed from their grants by the port of `require` (no grant, schema SELECT, schema write, table SELECT,
column-only SELECT, a role `i56q_r` holding table SELECT, schema SELECT + INSERT on nodes only, `%All`), compared on
the verdict and on the table and privilege the refusal names (`priv_*_me_name`, `priv_*_bf_name`); and eight graph
spellings `me_spell_*` (SQL `''`, `CHAR(0)`, a bound `''`, 0, `'0'`, a bound `'0'`, NULL, a name). All 21 mutations
and the tamper detected. Users and the role are dropped after the run.

Limits: `RequireWrite` with "u"/"d" and its unknown-letter refusal are transcribed but not exercised; a role granted
`%All` indirectly, and grants made through `Security.Roles` rather than SQL, were not tried; `kg_BM25` and `kg_IVF`
share `RequireSelect` (their tables differ) and are bound by their own models only.
