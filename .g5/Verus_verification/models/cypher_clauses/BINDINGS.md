# cypher clauses

Cypher clauses over API-written data: SQL grouping keys and count(DISTINCT) compare stored text while RETURN DISTINCT and the native executor compare type (bug-cyp-135, -136); arithmetic over property aggregates is an int column rounded half to even (bug-cyp-137); a UNION keeps only common boolean decoders and dedups raw values (bug-cyp-138); SKIP/LIMIT parameters of other kinds are used as counts (bug-cyp-139); a label-count UNION branch fails Prepare (bug-cyp-140); startNode/endNode of a relationships(p) element read a missing column (bug-cyp-141); DELETE refusal for any incident edge holds

Evidence status: active. Variant: as-built bounded transcription.

Verified and errors count obligations reported by the verifier. A control is judged against its named expected failure. Native observations have their recorded scope.

[Formal source](cypher_clauses.rs)

[Formal claims, product bindings and limitations](NOTES.md)

[Premises](NOTES.md)

[Product and declaration crosswalk](../../crosswalk/decision-links.tsv)
