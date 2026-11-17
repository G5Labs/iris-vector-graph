# traversal strategy

Traversal answers by strategy derived from one edge state: ObjectScript BFS rows equal the SQL fallback's on every edge set; the source is never a BFS row while the trail walk can end there; the cap keeps the nearest prefix; named graphs scope every walk but khop, which has none; shortest_path_length reads 'in' as 'out' (bug-str-113); an unknown direction text is walked undirected (bug-str-114)

Evidence status: active. Variant: as-built bounded transcription.

Verified and errors count obligations reported by the verifier. A control is judged against its named expected failure. Native observations have their recorded scope.

[Formal source](traversal_strategy.rs)

[Formal claims, product bindings and limitations](NOTES.md)

[Premises](NOTES.md)

[Product and declaration crosswalk](../../crosswalk/decision-links.tsv)

Binding: [binding.py](binding.py) on the run-isolated continuation fixture (ivg-cont-20261117-iris, USER, prefix
`i57a_<tag>_`, graphs `i57ag<tag>{n,m,k}`), receipt `results/traversal_strategy/20261117T074632Z-binding/receipt.json`:
73 cases AGREES (BFS out/in/both x {any, R} x hops 1-3 by the selected strategy and by the forced SQL adapter, raw SQL
walk, named graph, caps 0/2/3, multigraph, four direction texts, write-then-delete; 6 variable-length ends; 7
shortest-path pairs; 5 khop; real and injected strategy selection; 2 knn), 19 of 19 mutations detected, tamper detected.
