# Review 53-55 (independent review round 3), copied verbatim

Reviewer session `c68a5c59` (c68a5c59-cf74-4e9f-b94c-0fc845f92774); reviewed commit `fb1f806b` (fb1f806b26bc4d3008392085b47d208ec8683642) on `consolidated_uplift`, product pin `3eaa79cf`. Source: `$G5_RUN_STATE/reviews/review-53-55/REVIEW.md` (below, verbatim) and its full report `ANSWER.md` (appended after it, verbatim).

---

# Review 53-55 (independent review round 3), reviewer session c68a5c59

Commit reviewed: fb1f806b26bc4d3008392085b47d208ec8683642 (consolidated_uplift), product pin 3eaa79cf.
Scratch: /tmp/review-53-55 (tree/ = git archive copy; probes/; run/; reach/, reach-base/; bind/).

Reproduced:
- Proofs (copy, Verus 0.2026.10.04): sql_procs 16, bm25_scoring 32, percentile 26, cypher_clauses 26, bolt_answers 27, temporal_stats 58, operator_reports 48, aggregate_results 75: all PASS at recorded counts.
- Controls: full suites sql_procs 12/12, bm25_scoring 9/9, percentile 4/4, cypher_clauses 25/25, bolt_answers 19/19 EXPECTED_FAIL; temporal_stats nested-serialized-as-json, operator_reports metrics-marks-unknown and ledger-read-reported EXPECTED_FAIL.
- Binding: percentile binding rerun from the copy (prefix rv55p_): AGREES 156, 4/4 mutations, tamper detected.
- Freshness: latest prove+binding receipts of the 8 models above are FRESH.
- member_reach HEAD 640 / 8d8d9ae4 563: +77 new, 0 lost.
- Fixture probes rv55_ (probes/rv55-observed-20261117T064229Z.json) and rv55b_ (probes/rv55b-observed-20261117T064330Z.json).

See the final answer for the full findings; this file holds the same content in summary.

---

## ANSWER.md (verbatim)

# Review 53–55 (independent review round 3)

**Result: conditional sign-off.** Nothing is blocking. Five material items need repair:
- F1: Bolt transactions are reproducible but not owned or registered as such.
- F2: a new product defect, `length(p)` of a null path answers 1.
- F3: the aggregate_results narrowed claim is stated inconsistently.
- F4 and F5: some new bindings take their decision as an input or are locators, but are counted as active.

All proofs, controls and the required findings reproduced.

**Commit reviewed:** `fb1f806b` on `consolidated_uplift`, product pin `3eaa79cf`. No STOP file existed during the run.

## What I reproduced

All runs used a `git archive` copy at `/tmp/review-53-55/tree`.

| Check | Result |
|---|---|
| Proofs | All PASS at the recorded counts: sql_procs 16, bm25_scoring 32, percentile 26, cypher_clauses 26, bolt_answers 27, temporal_stats 58, operator_reports 48, aggregate_results 75 |
| Controls for the 5 new models | 69 of 69 EXPECTED_FAIL (12 + 9 + 4 + 25 + 19) |
| Round-2 repair controls | `nested-serialized-as-json`, `metrics-marks-unknown`, `ledger-read-reported` all EXPECTED_FAIL |
| Receipt freshness | The latest prove and binding receipts of all 8 models are FRESH |
| Percentile binding, re-run from the copy (prefix `rv55p_`) | AGREES 156; 4 of 4 mutations and the tamper detected |
| `member_reach.py` at HEAD vs `8d8d9ae4` | 640 vs 563 active bindings: 77 new, none lost. This matches the master's 619 → 640 for iteration 55 |

The temporal_stats and operator_reports bindings were not re-run; the operator_reports binding re-creates a namespace.

Fixture probes ran on `ivg-cont-20261117-iris`, USER, with outputs in `/tmp/review-53-55/probes/rv55*-observed-*.json`:
- **bug-cyp-135:** reproduced. Groups `[1,3],[1.5,1]`; `RETURN DISTINCT` gives 1, `'1'`, 1.5; `count(DISTINCT)` is 2.
- **bug-cyp-136:** reproduced. The SQL path gives 2 groups; the native-on engine gives 4.
- **bug-cyp-138:** reproduced. A UNION returns `'\x01N1'` and `'\x01D2.5'`.
- **bug-cyp-134:** reproduced. p 0.9 answers 30.0 and p 0.6 answers 20.0.
- **W60 Medium findings:**
  - bug-plt-123 reproduced: `RETURN b, r, a` reports the start as b, and `RETURN r` alone has no endpoints.
  - bug-cyp-145 reproduced: `n.v = '1'` matches a stored 1.
  - F-1602 reproduced: with `fetch_size=2` the driver gets 2 of 5 rows.
  - bug-cyp-139 reproduced: `LIMIT '2'` is used as 2.

Every "Expected" I checked is grounded in docs, an owner or openCypher. The severities are plausible.

## Validation of round-2 items

| Item | Verdict | Notes |
|---|---|---|
| M1 | Repaired | Owner `temporal.labelset`, model, control and binding case, bug-tmp-105. Non-JSON input is observed only. |
| M2 | Repaired | Owners readers and readiness, model, controls, binding (receipt fresh, not re-run), bug-plt-119. |
| M3 | Repaired | New block `install.status.ledger`, control, bug-plt-120, `GraphLedger.stats` bound. |
| m1 | Repaired | `theorem_ms_edge_in_seconds_whole_bucket`, control `ms-buckets-apart`, bug-tmp-106. I checked they exist; I did not re-run that control. |
| m2 | **Partly** | See below. |
| m3, m4, m5, m7, m9, m10 | Repaired | |
| m6 | Repaired | The new bullet has no finding link; the evidence sits in bug-cyp-126. |
| m8 | Partly | As the dispositions themselves record. |

**Challenge to "m2 owned as built, not registered":**
- No document promises an empty key as a wildcard, so the wildcard part is fine.
- But the owner now states a rule ("an aggregate read needs a source and a predicate") with a "Today" departure, and nothing is registered or modeled.
- Within that departure, the same invalid call answers **0** when the window only cuts buckets. That is a silent wrong answer, not a refusal.
- Repair: register it as Low and add a refusal branch, or restate the rule.

## Findings

### Coverage gaps

**F1 (material): Bolt explicit transactions do not roll back.**
- Probe `rv55b … bolt_tx`, neo4j driver 6.4.1 against the product's own listener. A CREATE persists after each of:
  - `tx.rollback()`;
  - a failure inside the transaction followed by rollback;
  - an aborted `execute_write`.
- F-1601 still reads "inconclusive, not reproduced" in the register-20261115 audit record.
- No owner states the intended behavior; `access.bolt` only has a working assumption of per-statement commits.
- The governing text of `access.bolt.results` states the intended PULL behavior, with F-1601 and F-1602 only in metadata.
- `bolt_stream`'s `theorem_commit_preserves_but_rollback_discards` concerns pending rows, not writes, which is easy to misread.
- W60's scope included the Bolt state machine.
- **Repair:**
  - Add an owner block (rollback discards the transaction's writes, or BEGIN is refused) with "Today" bullets.
  - Promote F-1601 to E2E reproduced at Medium or higher; the driver reports success while the writes stay.
  - Add a binding case: BEGIN, CREATE, ROLLBACK, then count.

**F2 (material; new product finding, suggest Medium): `length(p)` of a null OPTIONAL path answers 1.**
- `OPTIONAL MATCH p = (a)-[:K]->(b)` with no match: `length(p)` is 1 while `p IS NULL` is true, on both engines.
- A variable-length path and the literal `length(null)` correctly give null.
- Cause: `translator.py:28797-28802` returns `len(pattern.relationships)` as a constant.
- This contradicts `query.optional` ("later expressions read them as null") and openCypher.
- **Repair:** register it, add an owner bullet, and add a cypher_clauses case plus a binding case.

### Fidelity errors

**F3 (material): the aggregate_results narrowed claim is stated inconsistently.**
- The narrowing appears only in `query.aggregation.keys` metadata (`cypher.g5.md:1086`) and cypher_clauses NOTES.
- The aggregate_results NOTES and its `coverage.md:697` row are unchanged since `8d8d9ae4`.
- The parent `query.aggregation` still cites `theorem_key_enumeration_complete_unique` with no qualifier.
- aggregate_results proves `theorem_numeric_distinct_normalizes_int_and_whole_double` (rs:110): `count(DISTINCT)` over 1 and 1.0 counts one value. The product agrees (my probe: `count(DISTINCT)` = 1, group `[1,2]`, while `RETURN DISTINCT` gives 2 rows).
- But the owner's working assumption is "two values". So that theorem certifies as correct an outcome the owner treats as a departure.
- **Repair:** mark the theorem as conditional on `query.aggregation.keys.numbers`, and state the narrowing in the model's NOTES, the coverage row and the parent's metadata.

### Binding errors

**F4 (material): the sql_procs privilege gate takes its decision as an input.**
- `gate(holds, t)` takes whether the privilege holds as a given, so `theorem_entries_gated` is true by definition.
- The RequireSelect and RequireWrite rows claim the decision "%All or SELECT on the table or schema; column privileges do not count".
- The binding hand-labels three users; it has no table-only, column-only or %All user.
- Two outcomes satisfy the formal guarantee equally: column-level SELECT accepted, or refused.
- **Repair:** model the grants and add those users, or relabel the two rows as delegates or locators.

**F5 (material for counting): locator-only members are counted as active bindings.**
- `start_tcp_bolt_server` (its row says "no decision of its own").
- `BoltSession._do_handshake` on WebSocket (its row says "not exercised").
- `BM25Index.Build` and `bm25_build` (their formal item `used_arg` takes the statistics as inputs).
- RequireSelect and RequireWrite (F4).
- **Repair:** reclassify these 6 and recount; 640 drops by at least 6.

### Minor
- **Percentile result type:** `percentileDisc` over integers answers a float. This is owned as a "Today" bullet but has no register entry. Neo4j returns the input's type, and the model's `Ans::Value(int)` cannot tell the two apart.
- **Null percentile parameter:** `percentileDisc(x, $p)` with a null p raises a raw Python `TypeError` from `float(None)`.
- **MatchEdges graph argument:** the normalization of `''`, `$Char(0)`, 0 and `'0'` to the default graph is encoded by representation (`graph_key` is the identity) and has no control.
- **kg_BM25 vs bm25_search:** `kg_BM25` with k ≤ 0 answers `[]`, while `bm25_search` refuses k < 1. No owner covers the difference.
- **BM25 tie order:** the owner says "node-ID order". As built it is equality to 12 decimals, then IRIS subscript collation (observed d10, d9, dB, da).
- **`query.aggregation.keys` wording:** its governing sentence ("of the same type") reads as settled intent while the question is open and openCypher compares numbers by value.

### Unsupported findings and evidence
- **Unsupported findings:** none.
- **Missing evidence:** F-1601 is now reproducible E2E (F1).
- **Stale evidence:** none.

## Binding sample (20 newly bound members)

| Member | Classification |
|---|---|
| `EdgeScan::ScanOneGraph` | Directly constrained |
| `EdgeScan::MatchEdges` | Partial: the graph normalization is encoded by representation |
| `TemporalIndex::BackfillWalk` | Directly constrained |
| `Ledger::RebuildEdgeIndices` | Directly constrained (coarse) |
| `BM25Index::SearchCore` | Directly constrained |
| `IVG/Percentile::PDISC` | Directly constrained; the result type is unmodeled |
| `translate_return_clause` | Directly constrained (`key_of`) |
| `_tts_union_branches` | Directly constrained |
| `translate_delete_clause` | Directly constrained |
| `negotiate_version` | Directly constrained |
| `_recompose_graph_row` | Directly constrained |
| `GraphLedger.stats` | Directly constrained |
| `_unwind_by_index_retry` | Partial: inspected transcription only |
| `SqlProcs::MatchEdges` (SQL entry) | Justified delegate, bound to a definitional theorem |
| `_scalar_statistical` | Justified delegate: the null-drop is a premise; the null-p error is unmodeled |
| `SqlPrivilege::RequireSelect` | Locator only: decision is an input |
| `BM25Index::Build` | Locator only |
| `bm25_build` | Locator only |
| `start_tcp_bolt_server` | Locator only |
| `BoltSession._do_handshake` (WebSocket) | Locator only |

That is 11 directly constrained, 2 partial, 2 justified delegates and 5 locator-only.

## Sign-off conditions
- F1 and F2 owned and registered, each with a binding case.
- F3's statement made consistent across the owner, model NOTES and coverage row.
- F4 and F5 reclassified and recounted.

This is the third and last review round in the budget, so these repairs need validation within it.

## Limitations
- I did not re-run the temporal_stats, operator_reports, cypher_clauses, bm25_scoring, sql_procs or bolt_answers bindings, only the percentile one.
- I did not try the WebSocket Bolt path or other drivers.
- Fixture nodes remain in USER under the prefixes `rv55_`, `rv55b_` and `rv55p_`.

## Repository state
HEAD is still `fb1f806b`. `git status --porcelain --ignored` is identical before and after; the one pre-existing ignored `__pycache__` file was already there. There are no worktrees. `member_reach.py` wrote only to `/tmp/review-53-55/reach*`.

Notes and probe outputs are in `/tmp/review-53-55/`; the summary file is `REVIEW.md`.
