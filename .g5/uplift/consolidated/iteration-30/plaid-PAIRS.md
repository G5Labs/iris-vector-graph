# W35: F-0608's PLAID branch — predictions frozen before observation

Frozen 2026-11-16, iteration 30. Before image: seal 29 `6a4ca6e4`. Product `3eaa79cf`. Fixture `ivg-retest-20261116-iris`.

Why this workflow: the strongest remaining candidate at the step-5 check. F-0608 ("Vector index stores do not check width
or duplicates") was reproduced on IVF by the playbook audit and on VecIndex in iteration 27; its notes say "VecIndex and
PLAID branches of the finding were not run". PLAID (`Graph.KG.PLAIDSearch`) is otherwise unexamined.

Sources: API_REFERENCE `plaid_*` (lines 1083-1121), the `plaid_build` docstring note (R089: "A token of another width
raises `ValueError` before anything is written"), and F-0608's claim. `PLAIDSearch.cls` and the `plaid_insert` wrapper
were not read. Verus determines none of these.

| Case | History | Reader | Prediction |
|---|---|---|---|
| P1 | `plaid_build` with one token of another width | the call; `plaid_info` | `ValueError`, nothing written (`{}`) |
| P2 | build 4 docs (3-wide tokens); `plaid_insert` a new doc | `plaid_info`; `plaid_search` with its tokens | `indexed` +1, `totalTokens` + its tokens; it ranks first |
| P3 | `plaid_insert` an existing doc ID with tokens pointing elsewhere | `plaid_info`; search in the old direction | F-0608: `indexed` +1 although no document was added; the old tokens still make it answer the old direction |
| P4 | `plaid_insert` a doc with 2-wide tokens | the call; `plaid_info`; a search | F-0608: accepted, no error; scores for it unknown |
| P5 | `plaid_search`/`plaid_info` on a name never built | the calls | `[]` and `{}` |

### Added after reading the source, before any observation (exposed: source-informed)

`PLAIDSearch.Insert` (:204-232) overwrites `docPacked(docId)` and `docNTok(docId)`, adds the document to the centroid
list of each new token's nearest centroid without removing old memberships, and adds 1 to `nDocs` and `nTok` to
`totalTokens` unconditionally; it checks no width. Search ranks candidates by MaxSim over the stored `docPacked`.
Expectations: P3 — `indexed` +1 and `totalTokens` + the new count (both inflated), but the document is scored on its
**new** tokens, so the old direction no longer ranks it high (unlike IVF's stale cell); P4 — accepted, `dim` unchanged,
scored on the shared components.

## Outcome ([observation](plaid-observed-20261116T220723Z.json); binding in `results/plaid_index/`)

| Case | Outcome |
|---|---|
| P1 | held: `ValueError` naming the token, `plaid_info` `{}` |
| P2 | held: indexed 4 → 5, totalTokens 6 → 8, the new document first (0.98) |
| P3 | **partly held**: indexed 5 → 6 and totalTokens 8 → 9 for a stored ID (F-0608 confirmed); but the F-0608-derived expectation that old tokens still answer **missed** — the document scores 0.0 in the old direction and 1.0 in the new one (the source-based expectation held) |
| P4 | held (accepted); and the 2-wide document takes first rank (1.0) over a 0.5 match: scored on shared components |
| P5 | held: `[]`, `{}` |

Material prediction gained: no owner stated PLAID results; `search.plaid` now does, and F-0608's PLAID branch is
reproduced with its difference from IVF. Repair of a known finding, not a new discovery.
