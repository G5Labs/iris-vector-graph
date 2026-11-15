# Canonical-only reader self-check

Self-check, not independent review. Answers below use the statement bodies in
`.g5/ontology` only. New ontology remains proposed intent until owner acceptance.

| Question | Answer from the canonical owner |
|---|---|
| Does equal revision diff read any range? What does reverse mean? | ledger.readers.diff: equal returns no entries; the earlier endpoint is excluded, later included; reverse swaps before/after. Within a continuous life first prior/last new survives and net-zero disappears |
| Does reverse prop:k after=None prove old k was absent after delete/recreate? | No. ledger.readers.diff says the reverse existence entry carries a deletion snapshot. Simple delete/recreate retains the old property there; a preceding property change can instead lose the range-start prior. The net requirement stays in place |
| Can the inverse be applied in displayed order to reconstruct the earlier graph? | ledger.readers.diff.order leaves that unresolved. Default is a displayed set of lifecycle entries; an applicable script requires defined tie order and snapshot semantics. The maintainer owns ratification |
| Does repeated global PageRank scan loners? What changes on an isolate insert? | algorithms.cache.pagerank: same node COUNT:MAX/adjacency/params hits without census; adding an isolate changes the node key and recomputes. Failed token falls back to the list; empty table token is0:0 |
| Does a self-loop-only loner force Owner? | algorithms.cache.pagerank: the adapter removes self-loop-only nodes from the edgeless list. True isolates force Owner; loops alone permit the native eligibility probe, subject to algorithms.routing |
| Do fresh PageRank cache keys establish all-node normalized scores? | No. algorithms.op.pagerank keeps that requirement and states the Owner's 10000-row departure. algorithms.cache.pagerank separates numerical and concurrency premises; PPR freshness is separately owned |
| Does AQL 1..2 mean a decimal? What about 1.5 depth? | query.aql:1..2 keeps both integer bounds; decimal depth raises AQLParseError before execution. Literal null and string-null keep different predicates; null inequality becomes IS NOT NULL |
| Does the AQL contract promise query-result equivalence? | query.aql ends at Cypher text and bindings; traversal execution and SQL semantics remain unproved |
| Does a cosine score equal to threshold survive? What if omitted? | search.knn.threshold: equal survives, below is removed, omission keeps all scores eligible before top-k. This rule owns only generic vector_search and edge_vector_search |

Unchanged commitments relied on: ledger.readers (net requirement and read-only
readers), ledger.commit (record order/transaction intent), algorithms.routing
(Native eligibility), query.paths (Cypher consumer), search.knn (ranked search),
graph.default (default graph identity), and structure.node.read (downstream node
reader). algorithms.op.pagerank's requirement is preserved while its known
departure is made explicit. No accepted condition was weakened to fit code.

Independent reviewer attacks: replay the snapshot control and stronger Python
history; challenge changed-at-delete versus range-start values; test whether
native-candidate or normalized fixtures are mistaken for an actual numerical
guarantee. Then inspect the adapted SQLite boundary without treating it as IRIS.
