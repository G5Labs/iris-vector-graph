# W52: the IVF named index after its build (insert, delete, search, info, drop)

Selected from the product-wide inventory after iteration 45: `ivf_build` is bound (`vector_admission`), but
`ivf_search`, `ivf_insert`, `ivf_delete`, `ivf_info` and `ivf_drop` are not, and no owner states their cases; the
VecIndex counterpart produced bug-srch-101/102. Sources for the predictions: the API reference and
`search.scope.indexes.upkeep`, `search.embedding.width`.

## Predictions, frozen before reading the source

Five 4-wide vectors stored for nodes of a named graph under a new model key; `ivf_build(name, nlist=2, ...)`.

| ID | Case | Reader | Predicted |
|---|---|---|---|
| V1 | the build | its answer; `ivf_info` | `indexed` 5, `nlist` 2, `type` "ivf" |
| V2 | search with one stored vector exactly, `nprobe` = nlist | `ivf_search` | that node first |
| V3 | `ivf_insert` of a new node's vector | `ivf_search`; `ivf_info.indexed` | found; `indexed` 6 |
| V4 | `ivf_insert` of the same node again with another vector | search for the new vector; `indexed` | one entry for the node (replaced); `indexed` 6 |
| V5 | `ivf_delete` of a node, and of a node not there | answers; search; `indexed` | True then False; the deleted node no longer found; `indexed` 5 |
| V6 | `ivf_search` and `ivf_info` on a name never built | answers | `[]` and `{}` |
| V7 | `ivf_insert` into a name never built | | `ValueError` |
| V8 | a query of another width | `ivf_search` | raises (`search.embedding.width`: never padded or cut) |
| V9 | `ivf_build` again under the same name | search for V3's inserted node | gone: the rebuild replaces the index with the route's vectors |
| V10 | `ivf_drop` | `ivf_info`, `ivf_search` | `{}` and `[]` |

## Outcome (observed after the freeze)

Observations: [1](ivf-observed-20261117T011444Z.json), [2](ivf-observed2-20261117T011512Z.json) (a re-insert into another cell), then the
[binding](../../../Verus_verification/results/ivf_entries/20261117T011629Z-binding/receipt.json) (AGREES with `ivf_entries.rs`).

| ID | Held? | What happened |
|---|---|---|
| V1 | yes | indexed 5, nlist 2, type ivf |
| V2 | yes | the exact vector's node first |
| V3 | yes | found; indexed 6 |
| V4 | **no** | same cell: replaced but indexed 7; another cell (observation 2): both copies stay, one delete leaves the node found (new Medium bug-srch-107) |
| V5 | yes | True, False; not found; size down by one |
| V6 | yes | [] and {} |
| V7 | yes | ValueError |
| V8 | **no** | a 3-wide query on a 4-wide index answered with scores (new Low bug-srch-108) |
| V9 | yes | the rebuild dropped the inserted node and restored the deleted one |
| V10 | yes | {} and [] |

Material prediction gained: the new owner `search.ivf` predicts all ten.
