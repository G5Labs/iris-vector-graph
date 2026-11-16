# W24: variable-length path multiplicity — predictions frozen before observation

Frozen 2026-11-16 before any call on this workflow. Before image: seal 20 `1dcbf766`.
Exposure: the 4.7.0 changelog line "`SQLUser.CY_VLP_ENDS` reads `^KG` ... and for a lower bound of 0 or 1 takes each end
at its BFS distance instead of enumerating every trail ... same answers". I have not read `Graph.KG.VarLength` or the
translator's var-length paths. Owner: none states multiplicity (`query.paths` covers routing only).

Graph: `a→x→b`, `a→y→b`, `a→b` (relationship type R). openCypher returns one row per path (relationship-unique trail).

| Query from a | openCypher | Risk if ends are taken once at BFS distance |
|---|---|---|
| `-[:R*1..2]->(t) RETURN t.id` | b, x, y, b, b (5 rows) | b, x, y (3) |
| `RETURN count(*)` | 5 | 3 |
| `RETURN DISTINCT t.id` | b, x, y | same |
| `RETURN t.id, count(*)` | b 3, x 1, y 1 | b 1 |
| `*2..2` | b, b (2) | b (1) |
| `*0..1` | a, x, y, b (4) | same |

## W24 outcome ([SQL path](varlength-observed-20261116T172154Z.json), [default engine](varlength-default-engine-observed-20261116T172205Z.json))

Every cell held on both engines: one row per path (b three times), DISTINCT b/x/y, `*2..2` b twice, `*0..1` four rows.
No discrepancy; the BFS-distance end optimization preserves multiplicity here.

## W25: adjacency rebuild — frozen before observation

Owner basis: ADR-0009 ("the rebuild refills out/in from SQL only"), `structure.adjacency.*`. Setup: default-graph edge
a→b, named-graph (g21) edge a→c, temporal edge a→d (marked row), and a planted `^KG("out", 0, a, R, z)` with no row.
Reader: `^KG("out", graph key, s, p, o)` over the Native API, before and after `rebuild_kg()`.

| Entry | After rebuild (prediction) |
|---|---|
| a→b in key 0 | present |
| a→c in key "g21" | present |
| a→d (marked row) in key 0 | present |
| planted a→z (no row) | removed |

## W25 outcome ([observation](rebuild-observed-20261116T172252Z.json))

Held: after `rebuild_kg()` the default-graph, named-graph and temporal-marked entries remain and the planted entry with
no row is gone. No discrepancy.
