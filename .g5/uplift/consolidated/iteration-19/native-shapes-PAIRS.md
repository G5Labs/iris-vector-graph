# W20: ordinary anchored reads, native executor vs SQL path — predictions frozen before observation

Frozen 2026-11-16 before running this panel. Before image: seal 18 `42620fb4`.
Exposure: iteration 18 found one equal-answers failure (empty string under ORDER BY); `native_plan` declines non-string
equality values; native plans need an anchor with a string id. I have not read `Graph.KG.Cypher.Exec` beyond `SortKey`.

Data: anchor A; six targets with `p` = "s", 7, 2.5, true, ["x", 1], missing, plus labels L/M; edges A-[:R {w: 0.5}]->t,
one reverse edge t3-[:R]->A, one second hop t1-[:R]->t2.

| Query shape (anchored on A) | Owner prediction | Source-informed risk |
|---|---|---|
| out-neighbours, `RETURN b.id, b.p` | equal | typed values (bool, float, list) decoded differently by the two paths |
| in-neighbours, undirected | equal | undirected duplicates/self |
| relationship property `r.w` | equal | number spelling (.5 vs 0.5) |
| target label filter, string property filter | equal | — |
| `count(b)`, `count(*)`, `DISTINCT b.p` | equal | list or bool distinctness |
| two hops | equal | — |
| `ORDER BY b.p` with `LIMIT`/`SKIP` over these values (no empty string) | equal | list rank |
| `RETURN b` (node value), `labels(b)`, `keys(b)` | equal | node JSON shape |

## Outcome of the panel ([observation](native-shapes-observed-20261116T171004Z.json))

Only four of sixteen shapes plan natively (`count`, `DISTINCT b.p`, `ORDER BY b.p` with `LIMIT`, `ORDER BY b.p DESC`);
all four give equal answers over string, integer, float, boolean, list and missing values. The other twelve take the
SQL path (two-column returns, label and property filters on the target, in/undirected, relationship variables, two
hops, `SKIP`, node values). Owner prediction held wherever the native path answers.

## W20b: the empty string in the other planned shapes — frozen before observation

Targets' `p`: `""`, `"s"`, missing. Queries: `RETURN count(b.p)`, `RETURN DISTINCT b.p`, `RETURN b.p` (unordered).
Owner: equal. Risk from bug-cyp-104: the native path treats `""` as null, so `count(b.p)` is 1 natively and 2 on SQL,
and `DISTINCT` returns `""` and null as one row.
