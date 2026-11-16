# W37: bug-tmp-102's rule on the batch writer and the temporal delete — predictions frozen before observation

Frozen 2026-11-16, iteration 31. Same fixture. Caller: driver autocommit off, nothing written, then `conn.rollback()`.
Source of predictions: the `temporal.write` statement as updated in iteration 27 ("When the caller turned the driver's
autocommit off and has written nothing yet, its rollback removes the structural edge and its end nodes but keeps the
temporal edge") and the `write_routing` call-shape rule (global writes at `$TLEVEL` 0 are durable; the first SQL write
opens the caller's level). `bulk_create_edges_temporal` and `delete_edge_temporal` were **not** read.

| Case | Call inside the caller's transaction | Prediction after rollback |
|---|---|---|
| V1 | `bulk_create_edges_temporal` of two new edges | as bug-tmp-102: window keeps both; structural rows and nodes gone |
| V2 | `delete_edge_temporal` of a committed temporal edge (with its marked structural row) | unknown order; if the stores are killed before the SQL delete: the window loses the edge, the structural row stays |
| V3 | neighbor: the same calls after SQL `START TRANSACTION` | everything restored / nothing left (joins) |

## Outcome ([observation](temporal-variants-observed-20261116T221350Z.json); `write_routing` binding, 52 histories)

V1 held: after an autocommit-off rollback the batch's temporal entries remain (window 1), its structural rows, `^KG("out")`
and nodes are gone. V2: the stores are killed before the SQL removal, as the conditional prediction said: the temporal
edge stays deleted (window 0) while the structural row and `^KG("out")` entry are back. V3 held: both undone after
`START TRANSACTION`. Unexplained detail: the two-edge batch's window read returned 1 edge, not 2 (not investigated; the
binding uses one-edge batches). bug-tmp-102 widened; same rule, not a new entry.
