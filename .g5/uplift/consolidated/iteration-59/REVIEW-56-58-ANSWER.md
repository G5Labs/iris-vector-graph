# Review 56–58 (independent review round 4): conditional sign-off

Nothing is blocking. One item is material: the HTTP `tx/commit` batch keeps partial writes and has no owner or register entry. One counting fix is needed: `OtherEdgeKeys` is counted as an active binding, which drops the count from 706 to 705. All required findings, proofs and controls reproduced.

**Commit reviewed:** `fdc19d52` on `consolidated_uplift`, product pin `3eaa79cf`. No STOP file existed during the review. Notes and probe outputs are in `/tmp/review-56-58/`; the summary is `REVIEW.md`.

## What I reproduced

All proofs and controls ran on a `git archive` copy at `/tmp/review-56-58/tree`.

| Check | Command | Result |
|---|---|---|
| Proofs, 7 new models | `run_verus.py prove` | All PASS at the recorded counts: bolt_tx 20, install_lifecycle 32, traversal_strategy 30, adjacency_maint 35, rebuild_reads 5, clause_combos 28, result_decoders 12 |
| One control per model | `CONTROL=… run_verus.py controls` | `begin-refused`, `row-read-materialized`, `length-in-reversed`, `fresh-ignores-stamp`, `rebuild-swaps`, `group-by-kind-column`, `with-coalesce-typed`: all EXPECTED_FAIL |
| Reach | `member_reach.py --revision HEAD` and `--revision fb1f806b`, output to `/tmp/review-56-58/reach*` | 706 vs 640 active bindings: 70 newly bound, 4 lost (the F5 relabels). This matches the master's 640 → 662 → 696 → 706. 212 crosswalk rows were added (84 proves, 66 models, 8 witnesses, 19 delegates, 35 cites) |

Fixture probes ran on `ivg-cont-20261117-iris` with prefixes `rv58_*`:
- **bug-plt-127, reproduced.** With the product's own TCP Bolt listener and the neo4j driver: BEGIN, CREATE, `tx.rollback()` leaves count 1, and commit leaves 1.
- **bug-str-115, reproduced.** The race was run alone, with nothing else reading the fixture. 467 of 6,413 reads during three `sync()` calls answered `khop = [s]` and length −1.
  - **New:** the native Cypher read `MATCH (s)-[*1..2]->(b) RETURN count(DISTINCT b)` also answered 0 during the rebuild. The register says this reader was "not exercised".
  - **Passing neighbour:** 40 `create_edge` calls made during `sync()` were all still in `^KG` and answered by `khop` afterwards.
- **bug-srch-116, reproduced.** A quarantine row inserted with the `rv58_` prefix gives `ProgrammingError … Cursor closed`, and the row stays. An unknown `q_rowid` gives the documented `ValueError`. I deleted the row afterwards.
- **W62 Medium findings, reproduced:**
  - bug-cyp-155: `WITH coalesce(n.v, n.s) AS x RETURN x` answers `'3'`, while `RETURN coalesce(...)` answers `3`; a float comes back as `'2.5'`.
  - bug-cyp-156: a CASE over a boolean answers `'true'`.
- **F2 / bug-cyp-146, reproduced.** A fixed-length unbound path answers `length(p)` 1 (2 for two hops) while `p IS NULL` is true; a variable-length path answers null.
- **Refuted challenge.** I tested whether a whole float (2.0) comes back as an integer, which would contradict `theorem_typed_roundtrip`. It comes back as the float 2.0, so the claim holds.

Every "Expected" I checked is grounded in a document, an owner or openCypher. These severities are justified:
- bug-plt-127 High: silent, persisted, on the driver's standard API, and docs promise neo4j-driver compatibility with nothing saying transactions are unsupported.
- bug-str-115 Medium: silent but transient.
- bug-srch-116 Medium: the operator's recovery path is broken, but no data is lost.
- bug-cyp-155 Medium: silent wrong types on every reader.

## Round-3 items

| Item | Verdict | Notes |
|---|---|---|
| F1 (Bolt transactions) | **Repaired for Bolt** | New owner `access.bolt.transactions`, model `bolt_tx` (whose step comes from the message kind, not the decision), controls for both repairs, binding cases, and bug-plt-127 at High. The owner's wording matches `bolt_server.py:500-510`, with one imprecision (m1). Not done: the sibling HTTP surface (G1), and the stale working assumption in the open question (m1). |
| F2 | Repaired | Reproduced above. |
| F3 | Repaired | The narrowing appears consistently in the aggregate_results NOTES, `coverage.md:697` and the parent metadata. |
| F4 | Repaired | Grants are now derived (`check_priv`, `any_role`, `holds_priv`) and the binding has 8 users with computed verdicts. I read the model; I did not re-run its binding. |
| F5 | Repaired | The 4 rows dropped out of reach (confirmed). The RequireSelect and RequireWrite rows are now derived. |
| m2 challenge | Repaired | bug-tmp-108 Low, with a refusal rule, model and control. |
| Minors: percentile type, null p, MatchEdges graph argument, kg_BM25 k, BM25 tie order, keys wording | Repaired | bug-cyp-147, bug-cyp-148, bug-srch-113, controls and owner text are all in place. The keys wording needs one qualification (m3). |

## Findings

### Coverage gaps

**G1 (material). The HTTP `/db/neo4j/tx/commit` batch keeps partial writes.**
- **Probe:** CREATE, then a failing UNION, then CREATE, in one request. The answer is 400, and both CREATEs persist (count 2); the third statement still ran after the failure.
- **Cause:** `cypher_api.py:379-404` runs each statement on its own and continues after an exception.
- **Current state:** the open question `access.transactions` mentions the fact in one bullet. There is no owner block, no register entry and no binding case. The F1 repair covered Bolt only.
- **Expected:** the endpoint's own name (`tx/commit`) and the Neo4j HTTP transactional contract, under which a failed statement rolls the transaction back. My fetch of the Neo4j docs was denied, so the builder must quote them.
- **Repair:** add an owner for the HTTP batch (or widen `access.bolt.transactions` to all Neo4j-compatible surfaces), register it (Medium suggested), and add a binding case that counts after a failing middle statement.

**G2 (minor). A `CALL {}` subquery that imports an UNWIND variable fails on both engines.**
- `UNWIND [1,2] AS i CALL { WITH i RETURN i*2 AS d } RETURN i, d` gives SQLCODE −29 (`Field 'U0.NODE_ID' not found`).
- `… CALL { WITH i UNWIND range(1,i) AS j RETURN count(j) AS c }` gives "Undefined variable: j".
- W62's C5 case only tested MATCH-anchored imports. Not registered; Low, because the failure is loud.

**G3 (minor). ORDER BY over a list the query holds puts booleans among the numbers (both engines).**
- `UNWIND [2,'a',null,1.5,true] AS x RETURN x ORDER BY x` gives `1.5, true, 2, 'a', null`. openCypher gives `'a', true, 1.5, 2, null`.
- `[2,true,0.5,false]` gives `0.5, false, true, 2`.
- `query.values.sorting` and C9 cover stored property values only. Not registered; Low.

**G4 (minor). Install-lifecycle commitments left unmodeled or unprobed:**
- `install.schema.concurrency` (bug-plt-003 is still "suspected"). Iteration 56 could already recreate namespaces and did not probe two concurrent setups.
- The fail-open "unchecked" outcome for an unreadable record, which the owner's own working assumption asks to model.
- The pending first-access check that re-runs on every access until it passes (`engine.py:1847-1858`).
- The routine fingerprint `^IVG.Deploy("routines")`, which ADMIN_GUIDE documents under "Running setup again".

### Fidelity errors (minor)

- **m1:** In `access.bolt.transactions`, "BEGIN, COMMIT and ROLLBACK … change nothing" is imprecise: ROLLBACK clears the pending rows and COMMIT resets the state (`bolt_server.py:503-510`). Separately, `open_questions.md:6043` still has the working assumption "Assume per-statement commits on Bolt", which contradicts the owner's new rule.
- **m2:** The new bullet in `query.values` states the mechanism as the contract: "Any other column reaches the reader as the IRIS driver hands it". Read as governing text, it permits bug-cyp-155 and bug-cyp-156. State the rule instead (a returned value keeps its Cypher type at every reader and driver) and move `CY_TYPED` and the decoder lists to metadata.
- **m3:** In `query.aggregation.keys`, "RETURN DISTINCT keeps them apart" holds for stored properties only. Over a list the query holds, `UNWIND [1, 1.0] … RETURN DISTINCT x` gives one row `[1]`, and `RETURN 1 UNION RETURN 1.0` also gives one row.
- **m4:** The WITH * finding (bug-cyp-150) was placed as a "Today" bullet in `query.conformance`. That D block lists documented TCK deviations, and WITH * is not in KNOWN_ISSUES. It also pushed the block to 11 bullets, which is the only new `check_ontology` warning (17 → 18). Move it to the WITH clause's owner.

### Binding errors

- **B1 (counting).** `Adjacency.cls::OtherEdgeKeys` has the role "input: the triple's other rows…" but relation `proves`. Under F5's own rule (a member whose output is a model input is `cites`), it should be relabelled. 706 → 705.
- **B2 (minor).** `Adjacency.cls::MarkGraphGone` is counted active, but its grade reads "Inspected (proof and controls only; not observed by the binding)". Either add an observation of the `^NKG` stale flag after a named graph's last edge is erased, or report it in the inspection-only subset.
- **B3 (agree with the builders' audit flags).** These rows are weak but defensible:
  - `place_quarantined`: on the real product only the "row stays" outcome is observed; the later checks are bound only under a harness substitution.
  - `_unwind_bool_flag`: its control replaces the route's result, not the flag function's body.
  - `_float_expr_value` and `_plan_vector_dimensions`: binding-detected only, through a shared decision.
  - `EndsByDistance`: the model holds the openCypher trail rule; the member's own optimisations are checked only by the binding's port.
  - `KHop2CountExact`: binding-detected only, but `exact_answer` is derived.
  - `set_edge_weight` was not newly bound in this window.

### Unsupported findings
None.

### Missing or stale evidence
- The bug-str-115 register entry and owner bullet should add the native Cypher var-length reader (count 0 during `sync()`) and the passing neighbour (writes during `sync()` are kept).
- bug-cyp-138 should note that literal lists in a UNION also come back as JSON text (`'[1, 2]'`), while `RETURN [1,2]` alone is a list.
- I did not run `check_consolidated.py`, because it needs a git checkout and I would not run it in the repository. Receipt freshness was not independently re-verified.

## Binding sample (20 members newly bound in 56–58)

| Member | Classification |
|---|---|
| `Adjacency::Remove`, `::PutKeyed` | Directly constrained |
| `Adjacency::OtherEdgeKeys` | **Locator only** (B1) |
| `Adjacency::MarkGraphGone` | Partial: constrained by theorem and control, inspection only |
| `TraversalBuild::BuildKG` | Directly constrained (race reproduced) |
| `TraversalBuild::Build2HopStats` | Directly constrained (general `sum_len` rule plus a witness) |
| `TraversalKHop::KHop2CountExact` | Directly constrained (binding-detected) |
| `VarLength::EndsByDistance` | Justified (binding-checked against the trail rule) |
| `TraversalPaths::ShortestLength` | Directly constrained for the direction; the length itself is taken as the answer (stated scope) |
| `execute_knn_vec` | Directly constrained, no-route branch only |
| `resolve_schema_name`, `check_first_access`, `upload_and_compile` | Directly constrained |
| `place_quarantined` | Partial: "row stays" only on the product |
| `_plan_vector_dimensions`, `_float_expr_value` | Justified shared delegate |
| `_unwind_bool_flag` | Partial |
| `labels_subquery`, `read_prop_value`, `SqlPrivilege::Holds` | Directly constrained |

Totals: 13 directly constrained, 3 justified, 3 partial, 1 locator only, 0 unsupported.

The two-outcome test produced these scope limits, none of them a wrong claim:
- `adjacency_maint` excludes concurrency, so whether a write during a rebuild is kept or lost is undecided by the model; the product kept all 40.
- `install_lifecycle`'s conservation theorem counts rows, not vector content.
- ShortestLength's bidirectional search is represented only by its answer.

## Sign-off
Conditional sign-off on iterations 56–58, on two conditions:
1. G1 is owned and registered, with a binding case.
2. B1 is relabelled and recounted (and B2 either bound or reported as inspection-only).

G2, G3, G4 and m1–m4 can go to the residual queue.

## Limitations
- I re-ran no model bindings; my own probes stood in for them.
- I did not try the 5.4.1 driver, WebSocket Bolt or embedded Python.
- Fixture data remains under the prefixes `rv58_`, `rv58r_`, `rv58w_` and `rv58p_` (labels `RV58*`).
- `sync()` ran three times; nothing else was reading the fixture then.

## Repository state
HEAD is still `fdc19d52`. `git status --porcelain --ignored` is identical before and after. I created no worktrees; `member_reach.py` wrote only to `/tmp/review-56-58/reach*`.
