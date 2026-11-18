# Iteration 65 predictions, graded

Two frozen sets, both written before the deciding code was read:
- the master's: `$G5_RUN_STATE/assignments/iteration-65-master-predictions.md`, sha256 `c6a1320b…f590784`, checked equal to the
  digest beside it;
- the builder's: [builder-predictions.md](builder-predictions.md), sha256 `7d50d02b…e94ad3e`, committed in `763e09b9`
  before `Eraser.cls` was opened.

The builder's set was written from the owner's metadata, which already discloses some behaviour (listed in its header).
Grades: **S** supported, **P** partly supported, **W** wrong, **U** unconfirmed. Evidence: the
[binding receipt](../../../Verus_verification/results/erasure_stores/20261118T043516Z-binding/receipt.json) cases and the
model's theorems.

## Master (13)

| id | grade | evidence |
|---|---|---|
| E1 | S | B1: every g1 store emptied; g2's `a`, `b` rows, labels, props, edge, adjacency, temporal, statements and routed vector unchanged. Not predicted: g2's derived `^NKG` and cached answers also go (bug-str-118). |
| E2 | P | The model and the code erase both spellings (`theorem_default_graph_both_spellings`). B0: NULL is not reachable at the pin, because every content table declares `graph_id` NOT NULL. Only `''` was observed (B3). |
| E3 | S | B4, B5, B6 (the Eraser's own refusal natively): all stores equal before and after. |
| E4 | S | B1 (stmt and tuple of g1 gone; g2's and the default graph's kept; Rec unchanged). |
| E5 | S | C1, C6 (stmt and tuple removed with the row); C7 `delete_edge` leaves them. |
| E6 | P | The empty prefix is refused (C2). The `acme` → `acme-health|x` half is in the model (`theorem_prefix_selects_node_rows`); live, only `acme|` was run, which kept `acme-health|1`. |
| E7 | S | B1: 7 = 3 node rows + 4 relationship rows. The zero count with content removed is `witness_zero_count_with_content_removed`; live, C3 returned 0 while removing a temporal event (an ID erase, not a graph erase). |
| E8 | S | `theorem_no_erase_touches_quarantine`; B1-B3 and D1. |
| E9 | S | B1: TemporalStructural kept, FHIR wm 7/9 → 0/0, registration kept, multigraph off (`is_multigraph` False). |
| E10 | S | D1: settings, `^NKG` and the registry emptied (label sets were not populated). |
| E11 | P | Holds for an engine on the caller's connection (E1, E2). On a `from_connect` engine the erase commits on its own connection and survives the caller's rollback (E6, q-plt-006). |
| E12 | S | B1: claimed route dropped, orphan emptied and kept. Not predicted: when joined, the drop runs inside the caller's transaction (bug-str-119). |
| E13 | S | E4: 500 erased and committed, the second chunk raised. |

Master: 10 S, 3 P, 0 W, 0 U.

## Builder (22 workflow predictions + 4 owner checks)

| id | grade | evidence |
|---|---|---|
| P1a | S | B1 frame and effect. The count differs from the figure written for a smaller fixture, but its rule (nodes + relationships) holds. |
| P1b | P | `None` and `''` are one erase (S). "NULL reachable through public writers" is **W** (B0: NOT NULL). |
| P1c | P | `"0"` and a control character are refused (S). "A very long name refused" is **W**: a 300-character name was accepted and returned 0 (probe explore3). |
| P1d | S | BM25 still answers after the graph erase (B1 reader); the graphless indexes are untouched (model; IVF and PLAID were not built). |
| P1e | S | B1. |
| P1f | S | B1. |
| P1g | S | B2. |
| P2a | P | The stores are right (C1). The return is **W**: prefix and ID erases return node rows only (q-007). |
| P2b | S | C2; zero without error (C3). |
| P2c | S | C4, C5, C1 (statement of the deleted relationship removed). |
| P2d | S | C6, C7. |
| P2e | S | C1 leaves the temporal-only event and the orphan property row; C3's explicit-ID erase removes them. |
| P3a | S | D1. |
| P3b | S | D1 (`^BM25Idx` and `^VecIdx` kept; bug-srch-117). |
| P3c | S | D1 (13). |
| P4a | P | Joined on the caller's connection (S); a `from_connect` engine is not joined (E6). |
| P4b | P | "Never commits the caller's level" is S (E1). "The drop is not run inside the caller's transaction" is **W** (bug-str-119). The temporal counter was not exercised (U). |
| P4c | S | E3. |
| P5a | S | B1. |
| P5b | W | The drop is not deferred: it runs inside the caller's transaction, and the caller's rollback restored the table (E1). |
| P6a | S | `witness_zero_count_with_content_removed`; C3. |
| P6b | P | `bulk_delete_nodes` reports its own `DeleteResult` (S). "Their edges are counted" is **W** (node rows only). |
| owner: erasure.atomic WA2 | W | Predicted 50/50 that EraseGraph takes the head lock. No erase path takes it (F-1114). |
| owner: single-path `delete_edge` | S | C7. |
| owner: search.erasure.indexes bullets 1-2 | S | D1. |
| owner: degree.cache.uncommitted bullet 3 | S | `Adjacency.RemoveGraph` kills `^IVG.AdjNoLock(g)` (B1). |

Builder: workflow predictions 15 S, 6 P, 1 W (P5b); owner checks 3 S, 1 W (the head lock). The partial rows contain 5 wrong sub-claims.

## Not predicted by either set (material)

- A single-graph erase drops the unscoped `^NKG` and every graph's cached algorithm answers (bug-str-118).
- The reifier node of a named graph's edge survives its graph's erase (F-1502, re-observed in the B1 reader).
- `GraphStores.Digest` (the empty-graph reader) still lists the kept temporal-only setting after an erase.
- EraseAll deletes the registry before its drops (bug-str-120, model only).
- An explicit-ID erase reaches what the prefix erase leaves (C3), which gives an operator route around bug-led-007/010.
