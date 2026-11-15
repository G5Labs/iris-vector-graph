# Weighted-path proof draw before the candidate

Product3eaa79cf, foundation9e120916. The iteration8 source-first remaining-work
survey and known public M12 are inputs, not a private/blind evaluation draw.
Canonical algorithms.op.paths.weighted predicts minimum cost under graph/direction,
weight-property, cost and positive-hop bounds. Its metadata explicitly leaves both
native numerical searches unproved. Existing unweighted P result contracts do not
prove this queue/relaxation implementation.

- A1 positive graph s-a4,s-b1,b-a1,a-t1: unbounded or H3 cost3; H2 cost5.
  A node-only visited rule would miss the feasible cost5 bounded path. At H2 cap4
  no path; cap5 includes it. Source uses node+hops and fewer-hop dominance.
- A2 source==target immediately returns zero even for an admitted identifier absent
  from the persisted node table. No path returns empty; cost errors remain errors.
- A3 absent/nonpositive scalar weight is effective1. The theorem is about the
  actual stable adjacency scalar projection, not a minimum over all keyed rows.
  The indexed lowest-ekey producer and a direct scalar reweight are distinct writers.
- A4 stale higher-cost PQ entries survive dist decreases; skip behavior must come
  from raw seen minimum hops and ordered pop, not an invented stale-distance guard.
- A5 actual parent links are installed only from accepted predecessors and become
  immutable after their key is settled; backtracking must derive path/cost/hops.
- A6 two-sided DijkstraCost has a different termination proof and invokes the path
  search when its recorded cheapest meeting exceeds the hop bound. Start with a
  meaningful DijkstraJson proof; do not claim the cost route until actually modeled.

Exact initial mathematical fragment: finite stable raw out/in coordinate graph,
admitted nonempty ordered-atom identifiers, exact integer raw scalar weights,
nonnegative integer cap, nonnegative H (0 means unbounded), explicit graph/direction/
predicate selection. Effective weights are positive integers. Floating/native
roundoff, concurrent graph changes, arbitrary JSON/identifier collation and failed
adjacency writes remain named correspondence/provider boundaries. No native/runtime
connection, product/shared/Git edit is performed by this builder.
