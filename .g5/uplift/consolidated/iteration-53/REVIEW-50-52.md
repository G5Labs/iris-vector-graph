# Review 50-52 (independent review round 2), copied verbatim

Reviewer session `d548b72a` (Opus 5.5); reviewed commit `8d8d9ae4adda9060eb74f24660a5e59190a1cde8` on `consolidated_uplift`. Source: `$G5_RUN_STATE/reviews/review-50-52/REVIEW.md`; derivations, notes and probes beside it. Dispositions: [DISPOSITIONS.md](DISPOSITIONS.md).

---

# Review 50–52 (independent review round 2): repairs, temporal statistics readers, operator reports

**Commit reviewed:** `8d8d9ae4adda9060eb74f24660a5e59190a1cde8` on `consolidated_uplift`; product pin `3eaa79cf` (product diff
since c648d226 is empty outside `.g5/`). Reviewer session d548b72a, Opus 5.5. No STOP file existed during the run.

**Result:** conditional sign-off. Nothing blocking. Round-1 items 1–3 and 5–7 are repaired; item 4 is repaired in
substance, with one residual mislabel. The W57 and W58 models are substantive state machines whose answers come from
modeled writers, and their recorded counts, controls and the temporal binding reproduce. Three material items remain:
a new label-set defect, the unknown-vs-zero readers W58 set aside, and LedgerStatus having no owner.

## Reproduced (copied tree `/tmp/review-50-52/tree`, Verus 0.2026.10.04.426d8b0)

| Check | Result |
|---|---|
| `temporal_stats` prove / controls | PASS 51 verified; 16/16 EXPECTED_FAIL |
| `operator_reports` prove / controls | PASS 34 verified; 17/17 EXPECTED_FAIL |
| `cypher_exprs` / `cypher_fns` | PASS 22 / 16 verified; 22/22 and 13/13 EXPECTED_FAIL |
| `retrieval_compose` / `ivf_entries` | PASS 35 / 19 verified; 15/15 and 7/7 EXPECTED_FAIL |
| `temporal_stats` binding re-run (prefix rewritten to `rv52b_`) | AGREES 139; all 16 mutations and the tamper detected |
| `member_reach.py --revision HEAD` / `c648d226` | 563 / 503 active; +61 new, −1 lost (`_scalar_numeric_and_datetime`, the item-4 reclassification); matches master 505→537→563 |

The `operator_reports` binding was not re-run: it drops and re-creates IRIS namespace I52B from %SYS, which goes beyond
prefix-scoped queries. Instead, bug-plt-115 was reproduced read-only in USER.

Fixture probes (`ivg-cont-20261117-iris`, USER, prefixes `rv52_*`; outputs `probe/p5*-out.json`):

- **bug-tmp-103** (Medium), reproduced: 1 target → 11; 3 → 12; the same target ×5 → 11; 40 → 47; empty → 0. A window
  that cuts the bucket and excludes the only edge gives count 0 but distinct 11.
- **bug-plt-115** (Medium), reproduced read-only:
  - The registry holds `kg_emb_…` rows (344 routed node vectors). `SELECT DISTINCT` answers `KG_EMB_…`, so
    `is_routed_embedding_table` is False for every row and `_embedding_tables` = `['kg_NodeEmbeddings']`.
  - `status().tables.node_embeddings` = 145, the legacy rows only (it should be 489).
- **Inherited repairs from 50**, all reproduced:
  - bug-cyp-126: row, property and missing-property null index → `'1'`; literal list → null.
  - bug-cyp-127: `CASE n.s1 WHEN 1` → `num`; `CASE n.i1 WHEN '1'` → `str`; generic CASE → `other`; literal/literal → `other`.
  - Item 5: a relationship CREATE with `{k:$k, lit:1}` stores `keys(r) = ['lit']`.

## Validation of round-1 items

| # | Verdict | Notes |
|---|---|---|
| 1 bug-plt-113 | **Repaired** | Owner states the documented cap plus "the edges among them"; two "Today" bullets; Arno-reader scope stated. Wrong-repair control withdrawn; `edges-among-answered`, `seeds-capped` added. |
| 2 bug-cyp-111 | **Repaired** (minor residual m6) | Narrowed to property lists and parameter indexes; `Src`/`IdxKind` in model; binding 9×7. |
| 3 bug-cyp-112 | **Repaired** | `ArgKind`, list-known flag and `Rev::ListAsJsonText`; owner widened. |
| 4 premise constants | **Partly repaired** | See below. |
| 5 relationship `$param` | **Repaired** | `RelValue::Param`; reproduced; simp-cyp-102 corrected. |
| 6 null index | **Repaired** | bug-cyp-126 Medium; modeled; reproduced. |
| 7 simple CASE | **Repaired** | bug-cyp-127; modeled. My probe adds a parameter test (`CASE $t WHEN 1`, t='1' → `num`), which closes their "parameter test not probed" residual and agrees with `kind_known(Param)=false`. |

**Item 4 in detail:**

- **Repaired:**
  - `iris_accepts_scalar_condition`: the bound member `_translate_boolean_expression` has its choice (`condition_sql(syn)`)
    modeled from syntax. Swapping RowVar→Predicate breaks `theorem_row_boolean_condition_fails` and the binding
    (mutation `row_condition_compared`). The active binding is legitimate.
  - `filer_writes_same_text`: `SetVal` is modeled from old and new kinds (`setval`), and `setval_skips_retype` is
    detected. Legitimate.
  - `_prop_set_deployed`: a real constraint. `prop_set_deployed(cached, check)` transcribes engine.py:1762-1781. The
    binding drives Absent through a non-existent schema prefix and Unreadable through a closed connection, both
    product-reachable, without overriding the cache. Mutation `unreadable_taken_as_absent` is detected.
  - Parser lookahead: `identifier_branch_parses(next, after)` is a real constraint on `Parser.parse_primary_expression`.
    But `tokens_after_lower` is a constant lexer table ("as observed") that the binding never observes (m5).
  - IVF: `insert_cell` is modeled from the metric branch, a real constraint. `build_cell` is a named k-means premise.
    `Build` (crosswalk row 642) is effectively a delegate for centroid storage.
- **Residual (m4), `driver_accepts_ast`:** `_fold_constant` (`folds`) is legitimately active. But
  `_create_resolve_prop_value` is labeled "decision: … returned as its AST", and its choice has no model term distinct
  from the driver premise. Controls `create-value-translated` and the premise flip produce the same model change. If
  the member refused unfolded values cleanly instead of returning the AST, the outcome (`RefusedNothingWritten`) and
  the binding would be unchanged.

## Findings

### Material

**M1. New product finding (suggest Medium): a nested map or list label-set value breaks "equal sets share one hash" and idempotence.**
- *Coverage gap.* Probe p51b:
  - `intern_label_set({"rv52": {"b": 1}})` twice gives two hashes (`39c028ff…`, `d9592d3d…`), and resolve gives
    `{"rv52":"10@%Library.DynamicObject"}`.
  - The same happens for `[1, 2]`.
- Source: `TemporalIndex.cls:1376-1378`, where the else branch embeds `val`, an oref.
- Contradicted:
  - the docstring (`TemporalIndex.cls:1336-1338`: "Idempotent", "Returns "" on invalid JSON"; `%FromJSON` actually
    throws);
  - the owner `temporal.labelset` ("equal sets share one hash");
  - type fidelity.
- Each call appends a new entry to an append-only global.
- The `temporal_stats` `canon` domain covers string pairs only and does not say so.
- **Repair:** add an owner bullet, a register entry and a binding case; extend the model domain or state the
  exclusion.

**M2. Coverage gap: the unknown-vs-zero distinction across the operator readers.** W58 set it aside.
- ADMIN_GUIDE:950-958 (R050) says a failed or skipped probe must read "unknown", not 0, "in sync" or "absent".
- `status()` keeps `unknown`, but:
  - `/server` (cypher_api.py:498-524) drops `unknown`;
  - `/metrics` (527-554) drops both `unknown` and `errors`, so a refused namespace or failed census emits
    `ivg_nodes_total 0`;
  - the readiness properties (status.py:192-214) read False on a failed probe with nothing distinguishing them;
  - a failed labels, props or edge-embedding count adds no unknown part (admin.py:472-476).
- The owner `install.status.readers` says `/server` and `/metrics` carry the counts "unchanged" and is silent on the
  loss. The model `Status` has no probe-failure dimension.
- Source-derived only; I did not probe it.
- **Repair:** add an owner bullet per reader, a probe on a refused namespace (e.g. a namespace never set up), and a
  model `unknown` input with a `/metrics` contrast.

**M3. Coverage gap: LedgerStatus (W58 scope) has no owner or model term.**
- Prediction S7 "held", but nothing in `.g5/ontology` owns `status().ledger`.
- `GraphLedger.stats()` swallows a failed `ledger_stats` read (`ledger/client.py:549-563`). The report then shows
  "0 commits · 0 rejections" with no error and no unknown, against `_ledger_status`'s docstring ("a read that fails is
  reported", `_engine/ledger.py:41-42`).
- Source only.
- **Repair:** add an owner bullet under `install.status` and the S7 contrast plus the swallowed-read case.

### Minor

| # | Kind | Issue and evidence | Owner / closure |
|---|---|---|---|
| m1 | coverage (new, Low) | A ms edge written by `TemporalIndexMS.InsertEdge` at (T+50)·1000 is counted by the seconds readers' whole bucket: `get_temporal_aggregate` count 1, a groups row, velocity 1. Meanwhile `get_edges_in_window(T..T+299)` = [] and the cut window `T..T+298` = 0 (probe p51; bucket numbers coincide, 1.7e12/3e5 = 1.7e9/300). temporal.g5.md:457 says the stores are shared but not this consequence, which breaks "exactly the window". | `temporal.stats.window`; register Low |
| m2 | coverage | `get_temporal_aggregate` with an empty source or predicate, and `get_distinct_count(source, "")`, raise `RuntimeError <SUBSCRIPT>`, while `get_bucket_groups("")` means all predicates (probe p51b). The owner says "every source's when no source is named" but is silent on the empty predicate. | `temporal.stats.window`/`.distinct` |
| m3 | expected grounding | ADMIN_GUIDE:940 says `ready_for_vector_search` means "the default embedding table holds vectors", and :942 says `kg_edge_count` "equals the edges in rdf_edges" (code caps at 10000). bug-plt-115's Expected rests on spec 230 FR-006, which is right, but the doc conflict should be stated. `KGEdgeCount` is bound through the declared-index premise (kg = rows); its cap and multiplicity walk are unmodeled. | bug-plt-115; `install.status.readiness` |
| m4 | binding role | `_create_resolve_prop_value`: see item 4. Relabel it a delegate of `folds`, or observe the error class (`<LIST ERROR>` vs a clean refusal) so its own choice is distinguished. | crosswalk row 669 |
| m5 | premise | `tokens_after_lower` is unobserved; have the binding record the lexer's tokens for `a..3`, `a..b`, `a..]`. | cypher_exprs binding |
| m6 | owner precision | `query.functions.list_index`: a null *parameter* index fails with "Incorrect number of parameters" (probe p50), but the bullet says a null run-time index "gives the list's first element". | owner bullet |
| m7 | coverage | `ready_for_edge_search` (a readiness flag) is not in `install.status.readiness`. bug-plt-115's collation applies to edge routes too (`_embedding_tables(kind=edge)`); R11 was not run. | owner bullet, probe |
| m8 | coverage, source only | Unprobed: `/indexes` is all-or-nothing (500 on the first failing `List()`, schema.py:1950-1963) where status reports per kind; `SHOW INDEXES` says ONLINE for any BM25/IVF/PLAID global, including mid-build or empty; `ivg status` exits 0 with errors; `snapshot_info`'s other raw errors and lack of a layout check; heal after an indeterminate count; a partial heal failure leaves the engine dirty (schema.py:2893). | `install.status.readers`, `.verify_sync`, `install.snapshot.info` |
| m9 | coverage | In `TemporalIndexMS`, `GetVelocity`/`FindBursts` take `windowSec` in ms (it is subtracted from an ms now); the owner states only the seconds default now. | `temporal.stats.velocity` |
| m10 | model domain | `ready_for_multihop_bfs` omits `kg_predicates_consistent`; `bfs_path` has no Arno case; `detect()` fixes `os: true`. Each is a stated premise (index declared, Arno absent). Fine within scope, but the owner should name the predicate-consistency conjunct. | operator_reports NOTES |

Not reproduced by me: bug-tmp-104, the strengthened bug-tmp-002/003/009 (the temporal binding re-run covers their
contrasts), bug-plt-116/117/118 (no namespace re-creation), bug-cyp-128..132. Every Expected I checked (bug-tmp-103,
bug-plt-115, bug-plt-116) is grounded in docs or docstrings; the severities are reasonable.

No unsupported findings. Evidence is current: the receipt input hashes match the files I re-ran.

## Binding sample (17 members newly bound in 50–52)

| Member | Classification |
|---|---|
| `TemporalIndex.cls::GetAggregate` | Directly constrained (whole vs cut from modeled state) |
| `TemporalIndex.cls::FindBursts` | Directly constrained (predicate not read; threshold inclusive) |
| `TemporalIndex.cls::InternLabelSet` | Directly constrained, partial (nested values outside the domain, M1) |
| `TemporalIndex.cls::HLLEmpty` | Justified shared delegate (constant used by writer and rebuild) |
| `TemporalIndexMS.cls::GetBucketCount` | Directly constrained (counter reader) |
| `IRISGraphStore.get_temporal_aggregate` | Directly constrained (conversion; driver-None premise named) |
| `TemporalMixin.intern_label_set` | Justified delegate (json.dumps → store) |
| `AdminMixin.verify_sync` | Directly constrained (indeterminate branch unmodeled) |
| `TraversalBuild.cls::RewritePass` | Directly constrained (edgeCount = distinct merged triples) |
| `TraversalBuild.cls::KGEdgeCount` | Partial, close to locator: replaced by the premise "^KG = rows"; only every-graph scope is checked by the binding |
| `Adjacency.cls::Put` | Directly constrained (skeleton guard, new-triple count) |
| `Adjacency.cls::RowPut` | Justified delegate (forwards to Put) |
| `GraphSchema.bootstrap_kg_global` | Directly constrained (markers only with rows, marker unset) |
| `EngineStatus.ready_for_multihop_bfs` | Directly constrained, partial (m10) |
| `cypher_api.py::get_metrics` | Directly constrained, partial (unknown loss unmodeled, M2) |
| `translator.py::_static_value_kind` | Directly constrained, partial (arithmetic/map kinds outside the `Syntax` domain) |
| `translator.py::_create_resolve_prop_value` (strengthened in 50) | Justified delegate only; its stated decision is not distinguished (m4) |

That is 12 directly constrained (6 of them partial), 4 justified delegates and 1 close to locator-only. None is
unsupported. Every new crosswalk row states a role.

## Readability of the new owner blocks

`temporal.stats.*`, `temporal.labelset` and `install.status.*` read plainly. Each states the rule, then "Today …"
departures linked to findings, with open intent linked to questions. `install.status.readers`' "unchanged" overstates
fidelity for `/metrics` (M2). The `temporal.labelset` opening sentence overclaims for nested values (M1).

## Sign-off

Sign-off on iterations 50–52 is granted, conditional on:

- recording M1 (owner, register, binding case);
- adding owner coverage for M2 (the unknown-vs-zero readers) and M3 (LedgerStatus), at least as owned as-built
  departures with one probe each;
- relabeling `_create_resolve_prop_value`'s role (m4).

The minor items can go into the residual queue.

## Repository state

HEAD is still `8d8d9ae4`. `git status --porcelain --ignored` is identical before and after the review. Every run
used the `git archive` copy; `member_reach.py` wrote only to `/tmp/review-50-52/reach*`.
