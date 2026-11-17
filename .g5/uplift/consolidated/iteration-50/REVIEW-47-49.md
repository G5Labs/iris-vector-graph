# Review 47–49 (copied verbatim)

Reviewer: fresh read-only session `e431ba47`. Reviewed commit: `c648d226361f218e7cb77cd24290505bc37af324` on `consolidated_uplift` (product pin `3eaa79cf`). Source: `$G5_RUN_STATE/reviews/review-47-49/REVIEW.md` (sha256 58de6b259093bfb6cf2d65717251bd43bd1eaefc87c29d6fca3ff60965829df9); the reviewer's notes, derivations and probe scripts stay beside it outside the repository. Dispositions: [DISPOSITIONS.md](DISPOSITIONS.md).

---

# Review 47–49: specs, findings and bindings for W53–W56

**Result:** sign-off withheld until seven material items are fixed; nothing blocking. The recorded counts and controls hold, and the representative findings reproduce. But I found three new product defects, one wrong repair proposal (bug-plt-113), and several ontology bullets that claim more or less than the product does.

**Commit reviewed:** `c648d226361f218e7cb77cd24290505bc37af324` on `consolidated_uplift`, product pin `3eaa79cf`. The product source is identical to the pin. No STOP file existed during the run.

## What I reproduced

- **Proofs and controls** (run on a `git archive` copy in `/tmp/review-47-49/tree`, Verus 0.2026.10.04.426d8b0):
  - `cypher_fns`: PASS, 11 verified; 8 of 8 controls EXPECTED_FAIL.
  - `cypher_exprs`: PASS, 17 verified; 17 of 17 controls EXPECTED_FAIL.
  - `retrieval_compose`: PASS, 28 verified; 12 of 12 controls EXPECTED_FAIL.
  - These match the recorded results. All four binding receipts are AGREES, and their recorded input hashes match the current files.
- **Binding count:** `member_reach.py --revision HEAD` gives 503 against 448 at `4eb9ea30`: 55 new, none lost, matching the master's 15 + 17 + 23. The repo's git status was identical before and after the run.
- **Findings on the fixture** (prefixes `rv49_*`, outputs in `/tmp/review-47-49/probe/`):

| Finding | Severity | Result |
|---|---|---|
| bug-cyp-120 | High | Reproduced. A relationship created between new nodes with `w: 1 + 1, u: toUpper('x'), lit: 5` stores only `lit`; `keys(r)` is `['lit']`. |
| bug-cyp-111, 112, 113, 114, 117, 118, 121, 122 | Medium | All reproduced. |
| bug-plt-113 | High | Reproduced exactly: with `ppr_top_k` of 3 or 7 the only edge is a1→a2; with 50, all 7 edges appear. |

- **Independent derivation:** before reading the builders' work, I wrote my own expectations (`notes.md`). Two read-only helpers derived W55 and W56/W53 from product source only (`w55-derivation.md`, `w56-derivation.md`). I probed every derived case used below.

## Findings

### Material: fidelity errors and expectations the evidence does not support

1. **bug-plt-113's expected result and repair contradict documented intent.**
   - The docstring (`iris_vector_graph/_engine/algorithms.py:956-957`) says the result is "capped at `min(max_nodes, ppr_top_k)` nodes". The design note calls `top_k` a "hard node cap" (`docs/dev/notes/enhancements/001-ppr-guided-subgraph.md:41,144,169`).
   - Yet the bullet in `algorithms.op.subgraph.guided` presents the cap as a defect ("Today the subgraph's cap is `ppr_top_k`"). The repair proposal says to pass `max_nodes` instead, and control `guided-cap-max-nodes` encodes that repair.
   - The real defect is that edges among the returned nodes are missing. A second case I reproduced: three seeds with `ppr_top_k=1` return 3 nodes (over the cap) and no edges.
   - High severity still stands for the missing edges.
   - **Repair:** keep the documented cap, and model and control "the edges among the answered nodes are listed". Also state that the finding applies only to the ObjectScript `SubgraphJson` path; with Arno loaded and no `edge_types`, `iris_sql_store.py:2528-2533` takes `SubgraphNativeJson` instead.
   - **Owners:** `algorithms.g5.md`, bugs_issues `bug-plt-113`, the `retrieval_compose` control.

2. **bug-cyp-111 claims too much.**
   - `WITH [1,2,3] AS l UNWIND [-1] AS i RETURN l[i]` correctly answers the integer 3, and non-negative run-time indexes come back typed.
   - The ontology bullet ("An index known only at run time fails … answers the element as text") is wrong for a list held in a WITH from a literal. In the model, `IdxKind` lacks the list's source, and `translated_index(RowValue)` always goes through `json_arrayget` (`cypher_fns.rs`).
   - **Repair:** add the list source to the model and binding, and narrow the bullet to lists that come from a property.

3. **bug-cyp-112 is wider than stated, and the model predicts one case wrongly.**
   - These also reverse the JSON text:
     - `reverse(l[0..2])` gives `']2,1['`.
     - `reverse(coalesce(n.l, []))` gives `']3 ,2 ,1['`.
     - `reverse(l[0])` of a nested list gives text.
   - `WITH n.l AS l RETURN reverse(l)` gives the *string* `'[3,2,1]'`, but `reverse_result(Variable, List)` says it gives a list.
   - **Repair:** extend `ArgKind` (slice, subscript, functions that are not list-valued), add the result's type to `Rev`, add binding cases, and widen the ontology bullet. That bullet currently says "held in a stored property" only.

4. **Several decisions are modelled as fixed premises, so the theorems prove nothing about the code.**
   - Each of these is a constant: `evaluated_per_row()` (bug-cyp-114), `driver_accepts_ast()`, `iris_accepts_scalar_condition()`, `filer_writes_same_text()`, `identifier_branch_looks_ahead()`, `truncate_first()`. The theorems are arithmetic on the constant, and the controls just flip it.
   - That is acceptable as recorded observed premises. Under `uplift-scoring.md` it is not model coverage of the producer's rule.
   - Specifically:
     - `_scalar_numeric_and_datetime` (311 lines) is bound as the "decision" for rand/randomUUID, but no model term constrains it.
     - The model takes `_prop_set_deployed` as an input `deployed`. The binding forces `_prop_set_ok=False`, so the member's own logic (dictionary check; an exception counts as deployed) never runs.
   - **Repair:** classify these bindings as locator-only in the coverage records, or model the emitter's choice itself.

### Material: coverage gaps, including new product findings

5. **A plain parameter on a relationship CREATE between new nodes is silently dropped.**
   - `CREATE (a {id:…})-[r {k: $k}]->(b {id:…})` stores the relationship with `r.k` null. In `translator.py:10213-10226` an `ast.Parameter` is neither a `Literal` nor a `Variable`, so it becomes `None` and is filtered out.
   - This is the ordinary pattern drivers send, so bug-cyp-120's reach is wider than recorded. Iteration 48 never probed it (only `toUpper($s)`).
   - The model's `RelValue` has no `Param` case. `simp-cyp-102` exempts "a literal or a parameter" from the fix, so as written it would keep this drop, against its own "refusal instead of a silent drop" rule.
   - **Owners:** the `query.writes.computed_values` bullet, the `cypher_exprs` model and binding, bug-cyp-120, simp-cyp-102.

6. **New finding (Medium): a null run-time list index returns the first element.**
   - `WITH [1,2,3] AS l UNWIND [null] AS i RETURN l[i]` gives `'1'`; so do `n.l[null]` and `n.l[n.nope]`. The literal-list form `[1,2,3][null]` correctly gives null.
   - openCypher (TCK `List1`) says a null index gives null. `rule_index` and the binding have no null case.
   - `simp-cyp-101` lists "null for a null bound" as behavior to preserve without noting that the product already gets it wrong.
   - **Owners:** `query.functions.list_index`, `cypher_fns`, the register.

7. **New finding (Medium): a simple CASE compares with SQL's type coercion.**
   - With `n.s1 = '1'`: `CASE n.s1 WHEN 1 THEN 'num' WHEN '1' THEN 'str' END` gives `'num'`, and `UNWIND ['1'] AS s RETURN CASE s WHEN 1 …` also gives `'num'`.
   - But `n.s1 = 1` is false, and the generic `CASE WHEN n.s1 = 1` gives `'other'`. openCypher and `query.values.equality` both say `'1'` does not equal 1.
   - `query.values.conditions` claims simple CASE "give[s] the openCypher answer". Iteration 48's C1 never tried mixed types.
   - **Owners:** `query.values.conditions`, `cypher_exprs`, the register.

### Minor

| # | Issue | Evidence |
|---|---|---|
| m1 | Slicing a null list gives `[]`, not null. | `MATCH (n) RETURN n.missing[0..2]` |
| m2 | Slicing a parameter list fails "Incorrect number of parameters"; the WITH form works. Possibly a parameter-order fault (helper read `translator.py:23778-23789`), possibly bug-cyp-125's driver premise. Needs triage. | `$l[$s..$e]`, `$l[$s..]`; `WITH $l AS l RETURN l[$s..$e]` |
| m3 | Unrecorded: a SET of a list built from properties raises a raw Python error. | `SET n.l = [n.a, 1]` → `TypeError: PropertyReference is not JSON serializable` |
| m4 | `trim` does not strip tabs or newlines, though `query.functions.strings` claims the openCypher answer. | `trim('\t a \n')` is unchanged (size 5) |
| m5 | A key from a WITH column fails rather than reading null; this is in bug-cyp-113's text but not its ontology bullet or `KeyArg`. | `WITH n, 'num' AS k RETURN n[k]` → "Non-integer index type" |
| m6 | `range()` accepts a non-integer step. | `range(1,3,1.5)` → `[1, 2.5]` |
| m7 | Five `query.functions` children cite `translator.py#L23500-L23656` for three functions, but the range covers only `_expr_subscript`. Reverse (24495), rand (26919) and range (29114) fall outside, and the strings range (`L24475-L24494`) ends just before reverse. | `cypher.g5.md` Sources lines |
| m8 | IVF build clusters with Euclidean k-means whatever the metric, while Insert picks a cell by dot product; "when it picks cells" holds for Search and Insert only. The model has no cell assignment. | `vector.py:1989`; `IVFIndex.cls:200-205` |
| m9 | Some theorems only check one worked example: `theorem_equal_lengths_agree` (provable in general), the bug-plt-113 star-graph theorems, and `theorem_guided_cap_is_ppr_top_k` / `theorem_hybrid_c_zero_becomes_60` (arithmetic on constants). | `ivf_entries.rs`, `retrieval_compose.rs` |
| m10 | Retype covers node properties only. On a relationship, `SET r.age = toInteger(r.age)` is refused with a self-contradictory error ("can read only its own `age`"). | fixture probe |
| m11 | W56 cases found by source reading only, not probed: Cypher `ivg.retrieve` is another fusion entry point (`translator.py:3343`); a `c` equal to minus a rank divides by zero; `/hybridSearch` turns k=0 into 50; the fusion IVF leg fixes `nprobe` at 8; the PPR walk ignores `edge_types`. | already in the master's residual queue |

**Not reproduced by me:** bug-srch-109, 110, 111, 112, bug-plt-114, and bug-cyp-115, 116, 119, 123, 124, 125. Apart from bug-plt-113, every expected result I checked is supported by openCypher or the docs.

## Binding sample (16 members across the three iterations)

| Member | Classification |
|---|---|
| `translator.py::_scalar_numeric_and_datetime` | **Locator only / unsupported** (the decision is a premise constant) |
| `engine.py::IRISGraphEngine._prop_set_deployed` | **Locator only** (decision taken as input; binding overrides its cache) |
| `IVFIndex.cls::Build` | **Locator only** for the metric (no cell assignment in the model) |
| `translator.py::_expr_subscript` | Directly constrained, partial (no list source, null index or WITH-key failure) |
| `translator.py::_scalar_string` | Directly constrained, partial (missing argument kinds; Variable case mispredicted) |
| `translator.py::_create_clause_relationship_entry` | Directly constrained, partial (no `Param` case) |
| `algorithms.py::kg_PPR_GUIDED_SUBGRAPH` | Directly constrained, but its "departure" is documented intent (item 1) |
| `CypherFn.cls::IVGLISTGET` | Directly constrained (SQL callers only; stated) |
| `Subgraph.cls::SubgraphJson` | Directly constrained (transcription; one-example theorems; binding port is richer) |
| `vector.py::_fusion_leg_index` | Directly constrained |
| `PyOps.cls::getDefaultDimension` | Directly constrained (a constant) |
| `SqlProcs.cls::CypherFnIVGLISTGET` | Justified shared delegate (forwarder) |
| `_engine/query.py::_execute_parsed_sql` | Justified shared delegate (generic reader) |
| `SqlProcs.cls::TxnBegin` / `TxnEnd` / `TxnUndo` | Justified delegates (forwarders; I did not re-run `write_routing`) |
| `translator.py::_create_node_literal` | Justified delegate (the refusal comes from the driver premise) |
| `IVFIndex.cls::AddBatch` | Justified delegate (stores the raw vectors the model assumes) |

That is 8 directly constrained (4 of them partial), 5 justified delegates and 3 locator-only. Every new row has a stated role.

## Readability of the new owner blocks

The bodies are generally plain and short. Present-day departures sit in "Today …" bullets linked to their findings, which works well. The problems are those above: three bodies claim more than the product does (`list_index`, `reverse`, `values.conditions`), one presents documented intent as a defect (`subgraph.guided`), and the shared Sources ranges are misleading (m7).

## Sign-off

For W53–W56 the specs largely match intent and the ontology, and the recorded High and Medium findings are real and correctly ranked. Sign-off is conditional on:

- correcting bug-plt-113's expected result, repair and control (item 1);
- extending bug-cyp-120, `RelValue`, the binding and simp-cyp-102 to parameter values (item 5);
- recording the null-index and simple-CASE findings (items 6–7);
- narrowing or broadening the bug-cyp-111 and bug-cyp-112 claims, and their models, to what the product does (items 2–3);
- marking the premise-constant bindings as locator-only in the counts (item 4).

## Repository state

HEAD is still `c648d226`. `git status` is clean, and `--ignored` shows only one ignored `__pycache__` file from 2026-11-16, which predates this review. Nothing was written to the repo. All scratch files, probe outputs and notes are under `/tmp/review-47-49/`.
