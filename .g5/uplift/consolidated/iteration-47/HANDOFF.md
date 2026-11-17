# Iteration 47: the stopped W53 draft, Cypher built-in functions at run time (W54), and the Txn SQL entry points

Before image: `4eb9ea30` (seal 46 plus the question-card commit, whose `open_questions.md` refinements are untouched
here). Product `3eaa79cf` unchanged (`check_consolidated.py` PASS: product paths equal the pin in HEAD and working tree).
Native evidence only from `ivg-cont-20261117-iris`, fresh prefixes per run (`sq…`, `co…`, `ie…`, `i47_…`, `i47b_…`,
`I47H…`, `cf…`). Guidance: `Verus/uplift-iteration.md` sha256 `7c5f718a88badf0202d91cd1d557ff2dd2f2bab8bc25178dccf852143e913b12`
(changed from `d31f5890`).

## Result

**Part A (the stopped draft; evaluated, then finished).** W53's frozen predictions S1-S3 (SQL `kg_IVF` / `kg_BM25`
against `ivf_search` / `bm25_search`) re-run fresh: 3 of 3 held ([PAIRS](sqlprocs-PAIRS.md)). The draft's IVF cosine
observation reproduced fresh. Accepted: the finding, renumbered as **bug-srch-109** (Medium, new). Rejected: the
draft's `theorem_cosine_is_dot_product`, which only proved an arithmetic fact about two hand-picked numbers and whose
control replaced the score with `dot / 2` only for length 10. Replaced by a transcription of `IVFIndex.Search`'s scoring
branches over integer vectors (`entry_score`, `ivf_above`) with `theorem_cosine_ranks_as_dot` over **every** query and
vector pair, a misranking witness, and an equal-length neighbor; the control `cosine-normalized` installs the
repaired order and leaves the neighbor verified. Rejected as well: binding `kg_BM25` (no formal model decides BM25
scoring; it would cite a claim that does not constrain the reader). New owner block `search.ivf.metric`; `search.ivf`
gains the `kg_IVF` bullet.

**Part B (W54, Cypher built-in functions over values known only at run time).** Predictions frozen and committed
(`f0d0ac4b`) before the deciding source was read ([PAIRS](cypherfn-PAIRS.md)): **6 held, 2 partial, 4 missed**. Every
miss came from source the predictions could not see: the translator chooses a function's implementation by the
argument's syntax, and the run-time choices differ from the literal ones. New owner section
[query.functions](../../../ontology/features/cypher.g5.md#query.functions) (8 blocks). New model `cypher_fns`.
Structural result: Cypher reaches only 4 of the 17 `CypherFn` bodies (`IVGRANGE`, `IVGTYPEERROR`, `IVGJSONSET`,
`IVGJSONREMOVE`); the list, map, string and regex answers come from the translator and the setup SQL functions in
`GraphSchema.get_procedures_sql_list` ([query.functions.sql_helpers](../../../ontology/features/cypher.g5.md#query.functions.sql_helpers)).
The native executor declined every function shape probed (24 of 24), so one executor was compared.

**Part C (stretch, partial).** `Txn_Begin/End/Undo` bound as the SQL entry points `WriteTxn` calls, after re-running
the `write_routing` binding on this fixture (AGREES, 52 histories). The other Part C members: residuals below.

## Predictions held and missed

| Workflow | Held | Partial | Missed |
|---|---|---|---|
| W53 S1-S3 (SQL readers of the named indexes) | S1, S2, S3 | | |
| W54 L1-L12 (functions at run time) | L3, L4, L5, L8, L9, L10 | L6 (`keys(n)` also lists `id`), L11 (error has no `TypeError` name) | L1 (`reverse`), L2 (run-time index), L7 (`n[k]`, `m[k]`), L12 (`randomUUID`/`rand`) |

Not frozen (found after the source reading): bug-srch-109 (IVF cosine), the `CREATE` refusal with `randomUUID()`, the
"Incorrect number of parameters" failures of `n.l[$i]` and `m[$k]`, and the 4-of-17 reach of `CypherFn`.

## Findings

New (discovered here; each **E2E reproduced** on the fixture with a passing neighbor):

| ID | Severity | Trigger → observable | Formal claim |
|---|---|---|---|
| [bug-srch-109](../../../Verus_verification/bugs_issues.md#bug-srch-109) | Medium | IVF metric "cosine" over vectors of different lengths → `ivf_search` and `kg_IVF` rank by raw dot product | `ivf_entries` `theorem_cosine_ranks_as_dot`, `theorem_cosine_metric_misranks` |
| [bug-cyp-111](../../../Verus_verification/bugs_issues.md#bug-cyp-111) | Medium | negative list index known only at run time → the query fails `<RANGE>`; run-time element answered as text | `cypher_fns` `theorem_row_negative_index_fails` |
| [bug-cyp-112](../../../Verus_verification/bugs_issues.md#bug-cyp-112) | Medium | `reverse()` of a stored list → its JSON text reversed | `theorem_stored_list_reversed_as_text` |
| [bug-cyp-113](../../../Verus_verification/bugs_issues.md#bug-cyp-113) | Medium | `n[k]` with `k` from `UNWIND` → reads property "k"; `keys(n)`/`n[k]` idiom all null | `theorem_row_key_reads_variable_name` |
| [bug-cyp-114](../../../Verus_verification/bugs_issues.md#bug-cyp-114) | Medium | `randomUUID()`/`rand()` → one value per query; a `CREATE` using one is refused | `theorem_rows_share_one_value` (conditional on the observed IRIS premise) |
| [bug-cyp-115](../../../Verus_verification/bugs_issues.md#bug-cyp-115) | Low | `m[k]`, `m['a']` of a map built in the query → numbers and booleans as text | none (probe only, open in Verus) |
| [bug-cyp-116](../../../Verus_verification/bugs_issues.md#bug-cyp-116) | Low | `head()` of a number → error text without `TypeError` | none (probe only) |

Inherited and reproduced again: [F-C0841](../../../Verus_verification/bugs_issues.md#F-C0841) (run-time `range()` step
0 answers `[]`), now with a formal claim (`theorem_runtime_zero_step_empty`). Withdrawn: none. Questions opened or
resolved: none (openCypher settles every expected outcome used; percentileDisc's rounding is recorded as a decision
matching Neo4j, held on the fixture).

## Owners changed

New: `search.ivf.metric`; `query.functions` with `.list_index`, `.reverse`, `.dynamic_access`, `.range`,
`.percentile` (D), `.random`, `.sql_helpers` (D). Extended: `search.ivf` (the `kg_IVF` reader). IDs preserved;
`check_ontology.py` 365 blocks, 0 issues, 17 writing warnings (unchanged from the start).

## Models

| Model | Verified | Controls | Binding |
|---|---|---|---|
| `ivf_entries` (extended) | 9 (was 4) | 6 of 6 EXPECTED_FAIL (`cosine-normalized`, `cosine-takes-l2-branch` new) | AGREES 6 cases (4 + `cosine_ivf_search`, `cosine_kg_IVF`); 6 of 6 mutations and the tamper check detected ([receipt](../../../Verus_verification/results/ivf_entries/20261117T014907Z-binding/receipt.json)) |
| `cypher_fns` (new) | 11 | 8 of 8 EXPECTED_FAIL in the final run | AGREES 43 cases; 8 of 8 mutations and the tamper check detected ([receipt](../../../Verus_verification/results/cypher_fns/20261117T015955Z-binding/receipt.json)) |
| `write_routing` (binding re-run only) | unchanged | unchanged | AGREES 52 histories on this fixture ([receipt](../../../Verus_verification/results/write_routing/20261117T020529Z-binding/receipt.json)) |

Retained failures: `ivf_entries` prove `20261117T014824Z` (count 9 against an expected 7, before the expectation was
corrected); `cypher_fns` prove `20261117T015814Z` (count 11 against 12); `cypher_fns` control
`range-ignores-direction` **SURVIVED** at `20261117T015827Z` because the rule and IVGRANGE shared one count helper (fixed
by writing the rule's count separately; it now fails as expected); `cypher_fns` binding `20261117T015937Z` DISAGREED on
its own harness (IRIS refuses `?` arguments to `JSON_ARRAYGET`; the direct call now inlines literals). Trust inventory
of both models: empty (no `assume`, `admit`, `external_body`); `vstd` only; the binding ports are unverified Python.

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings **448 → 463**. Newly reached and bound: 15 (A: `IVFIndex.Build`, `.AddBatch`, `SqlProcs.kgIVF`;
B: `translator.py::_expr_subscript`, `_scalar_string`, `_expr_fn_list_ops`, `_scalar_numeric_and_datetime`,
`QueryMixin._execute_parsed_sql`, `CypherFn.IVGLISTGET`, `CypherFn.IVGRANGE`, `SqlProcs.CypherFnIVGLISTGET`,
`SqlProcs.CypherFnIVGRANGE`; C: `SqlProcs.TxnBegin`, `.TxnEnd`, `.TxnUndo`). Strengthened (a new claim on an
already bound member): 3 (`IVFIndex.Search`, `VectorMixin.ivf_build`, `GraphSchema.get_procedures_sql_list`).
Overlap 0; distinct additions 18; lost 0. Locator only: `IVFIndex.SearchProc` (`delegates`). New formal distinctions:
cosine vs dot ranking at the reader; run-time vs literal list index; property read vs list literal for `reverse`; row
variable vs parameter key; run-time step 0; per-statement evaluation. Correspondence confirmed at the reader for each
(binding cases above); none withdrawn.

Correspondence: [delta from 46](correspondence-delta-from-46.json) (proof and correspondence STALE_ALL by design: the
two models' formal inputs and the bindings, crosswalk and families changed; no product file changed); fresh
[stamp](correspondence-inputs.json). `check_evidence.py` FRESH; `check_findings.py` no problems; `check_consolidated.py`
PASS. `link_verification.py` reports `.g5/TLA_verification/models not found` (no TLA models in this foundation; not
applicable).

## Residual list

Part B, open:
- The 12 `CypherFn` bodies that Cypher does not reach and that stay unbound (13 are unreached; `IVGLISTGET` is bound through its direct SQL call) (`IVGREGEXMATCH`, `IVGJSONARRAYLENGTH`, `IVGJSONVALUE`, `IVGJSONKEYS`,
  `IVGLISTREVERSE`, `IVGSTRSPLIT`, `IVGNEWID`, `IVGRAND`, `IVGLISTHEAD`, `IVGLISTLAST`, `IVGLISTTAIL`, `IVGMAPGET`) and
  their SqlProcs forwarders: first missing step is a documented SQL workflow that calls them; by reading,
  `IVGREGEXMATCH` answers 0 (not null) for a null string, unlike Cypher's `=~`. `IVGTYPEERROR` is reached but its
  raise is not modeled; `IVGJSONSET`/`IVGJSONREMOVE` belong to relationship `SET`/`REMOVE` (not examined here).
- `PercentilePDISC`/`PercentilePCONT`: L9/L10 held; no formal contract (first missing: a model of `IVG.Percentile`).
- `keys(n)` listing `id` for a `create_node` node: whether `id` is a stored property or added by the reader (not read).
- The run-time element type (`'1'`), map value types (bug-cyp-115) and the error text (bug-cyp-116) are probe-only.
- The `CREATE` refusal with `randomUUID()`: not traced to its source; other functions inside a `CREATE` map unchecked.
- The native executor: declined every function shape; whether any function shape routes natively is unassessed.
- `vector_search`'s IVF fallback and `kg_RRF_FUSE`'s IVF leg read the cosine-as-dot `Search` but were not exercised
  (the fixture supports `VECTOR_COSINE`).
- `kg_BM25`: S2 held; unbound until a BM25 scoring model exists.

Part C, not reached in this iteration (first missing step for each):
- `MatchEdges`, `MatchEdgesAllGraphs`: reached from the translator and `_engine/temporal.py` (and SQL per ADMIN_GUIDE);
  no prediction or probe yet; the shard/graph scan decision is unmodeled.
- `DijkstraPath`: reached by `CALL ivg.shortestPath.weighted`; `Traversal.DijkstraProc` has no binding; the
  `weighted_paths`/`weighted_cost` models were not checked against this SQL entry.
- `PropSet` (`Prop_Set`): emitted by the translator for typed node property writes and by `engine.py`; no prediction.
- `backfilltemporalrows`: called from setup (`schema.py`); `rebuildedgeindices`: ADMIN_GUIDE only (operator SQL);
  neither predicted nor probed.

Set aside: none of the quarantined material was opened; no evaluator-private input was read.

## Cost

Builder wall clock about 25 minutes (01:46-02:07 UTC, from the first command to the seal); tokens and currency not
available to the builder. Each proof under 2 s, each control suite under 15 s, each binding under 4 s.

## Independent review

Not performed in this iteration (no separate reviewer was started). For a reviewer: reproduce `cypher_fns` prove,
`CONTROL=row-index-through-ivglistget`, and its binding (runbook "Continuation on Linux"); attack first whether the
binding ports match the spec functions they claim, and whether `theorem_rows_share_one_value` should be read as a
product property beyond the observed IRIS 2026.1 premise.
