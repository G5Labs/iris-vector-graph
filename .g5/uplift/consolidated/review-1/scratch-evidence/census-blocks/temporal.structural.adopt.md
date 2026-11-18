# temporal.structural.adopt (review-1 fork A)
Independent enumeration: lead mark-cleared+qualifiers (general, incl. store_edge per F-0304); per entry point: create_edge, bulk, Cypher CREATE, Cypher MERGE, ledger create_rel; after adoption no delete/purge removes; adopt True vs dup False; explicit-first never marked (restatement); caller temporal=True exception (3 outcomes). ~9-10 vs recorded 8/1.
Split: o04 merges Cypher CREATE and MERGE (observed MERGE variants keep mark while CREATE adopts) -> minor under-split (both absent).
Exclusion x01 -> temporal.structural.mark.readers#o07 carries it (theorem_explicit_first_stays_unmarked). OK.
Grades: all 8 agree. o01 refuted via edge_acceptance.rs:46-47 (Store keeps mark). o02 :40-45. o03 temporal_marker.rs:167-170 (bulk_write takes no qualifiers). o05 partial: temporal.rs:654-665 apply_op definition only. o06 temporal.rs:2394 lemma (single step; sequence by trivial induction). o07 :20-26,:40-45. o08 :55-61.
Minor: bulk "adopts with empty qualifiers" (metadata observed divergence) is a second refuting case of lead "qualifiers apply" not in o01 cases.
Fidelity: nodes_edges.py:1250-1254 + 1275-1304 matches run() Create branch; len(rows)!=1 -> False matches one-row premise. Adoption UPDATE does not rewrite ^KG adjacency weight (not checked further).
