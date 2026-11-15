# Edge acceptance

Product `3eaa79cf`, as-built one-triple transcription, bundled vstd and the pinned
Verus toolchain in SOURCE-consolidated.json. No assume/admit/external_body. Seven
theorems pass; six controls fail their named theorems. The initial expected count
was mistakenly eight; the original UNEXPECTED receipt (six verified, zero errors)
is retained. Manifest correction changes no theorem or product behavior.

`run` derives insertion, ordinary duplicate, temporal adoption and refusal from
row presence, temporal marker, API and provider refusal; `count` is the SQL reader
projection. The new rule corrects a published wrong canonical prediction, not a
product defect. Historical H3-19 evidence and score are unchanged.

| Role | Production member | Formal target | Evidence |
|---|---|---|---|
| marker producer | nodes_edges.py::_qualifiers_json | theorem_caller_marker_retained | actual caller Boolean marker preservation; not general JSON equivalence |
| deciding caller/writer | nodes_edges.py::NodesEdgesMixin.create_edge | run | actual Python/SQLite agreement |
| competing writer | nodes_edges.py::NodesEdgesMixin.store_edge | run | actual Python/SQLite agreement |
| endpoint writer | nodes_edges.py::NodesEdgesMixin._ensure_edge_endpoints | theorem_new_edge_registers_endpoints | actual SQL, SQLite FKs |
| duplicate reader | nodes_edges.py::_swallow_duplicate | theorem_duplicate_returns_differ | real unique-error catch; LIST ERROR branch untested |
| adoption writer | nodes_edges.py::NodesEdgesMixin._adopt_temporal_row | theorem_temporal_adoption | real Python/SQLite read and update |
| final reader | nodes_edges.py::NodesEdgesMixin.edge_count | count | actual reader on persisted rows |
| shared reader | nodes_edges.py::NodesEdgesMixin._count_in_graph | count | actual default/named and other-graph count |

All source paths start `iris_vector_graph/_engine/`. See binding.py for replay.
Fifty-six cases vary both APIs, absent/ordinary/temporal rows, default/named graph,
indexed/manual adjacency, and a CHECK refusal after endpoint creation. Same-return
product mutant and changed final count are detected. Qualifier v/temporal projects
to the formal value/marker. Repetition preserves the original v. For the refusal
cases the primary row and endpoints remain absent after real WriteTxn orchestration
over adapted SQLite savepoints. Independent review caught the originally omitted
caller-supplied `temporal=True` qualifier. The extended model derives marker
retention from that input; repeated marked create reports True/True and replaces
the value while keeping one row. This strengthens inherited F-C0351, not a new
defect. The ontology preserves the intended unmarked-edge guarantee while naming
the as-built exception. Earlier limited proofs/receipts remain historical.

Premises: successful ledger admission, one fixed graph/triple, valid inputs, faithful
SQL uniqueness/atomic rollback, no competing process during a call. Indexed callback
and manual native adjacency are substituted; the model distinguishes their intended
effect, while binding only observes callback invocation. IRIS is not executed. A
cross-process duplicate race, LIST ERROR recheck, failure after native adjacency and
the real callback/global rollback remain unqualified. The transcription does not
prove Python bodies, SQL implementation, all qualifier content or multigraph keys.
