# Procedure results: retained before-model predictions

Foundation709a497f/product3eaa79cf. Source-frozen P1/P2 and alias discoveries were
already observed in iteration6/breadth-survey.md; these are builder-visible cases,
not a newly blind sample. Before building the model, current query.system-procedures
states allowed/refused tails but not alias mapping or empty-data validation. Imported
cys_l2 models graph scope of labels, not the consuming rows/columns. No current
formal claim answers these pairs; no private evidence is consulted.

- P1: persisted A/B, YIELD label AS l WHERE l=$wanted RETURN l: A returns A under
  column l; C returns empty under l. Ontology partial; formal unanswered.
- P2: WITH label WHERE label='B' RETURN label filters B; MATCH after YIELD refuses
  naming MATCH. Ontology supported; formal unanswered.
- P3 (known source discovery): bare alias filters successfully but physical column
  label remains; explicit RETURN l projects column l. ORDER BY l on the bare alias
  refuses; RETURN l ORDER BY l succeeds. Ontology unanswered; formal unanswered.
- P4 (new question to check): unsupported WHERE with no producer rows versus a
  nonempty producer may distinguish validation from evaluation. No outcome is
  predicted by the current owner/model; both unanswered. Retain any exception to
  a broad refusal claim rather than assume validation occurs eagerly.

Intended alias convention from tests and ordinary YIELD semantics is separate from
as-built standalone columns; no owner decision or product defect is assumed. The
existing unscoped db.labels finding F-0816 stays inherited. Provider dialect,
collation and concurrent mutations remain explicit boundaries.
