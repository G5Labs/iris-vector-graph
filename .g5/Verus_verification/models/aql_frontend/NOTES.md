# Typed AQL depth and null translation

As-built frontend projection at 3eaa79cf, **6 verified / 4 controls**. Owner:
query.aql. Results/raw logs: `../../results/aql_frontend/`.

`decimal/lex` inspects the actual next two characters after a nonempty digit
prefix: '..' preserves an integer token; '.' followed by a non-dot (or end)
produces float. Digit accumulation is assumed, not proved. `depth/hops` preserves
integer single/range bounds and refuses float tokens before translation.
`resolve` distinguishes null from the string null and maps equality/inequality
to IsNull/IsNotNull; other comparison operators retain their form.

Four controls: treat '..' as decimal, discard upper bound, invert null inequality,
and treat string-null as null. Each fails its named theorem. Python binding runs
**100 journeys**: 96 depth/operator/literal combinations plus four decimal refusals.
Actual lexer, parser, typed AST, public translation and execute_aql adapter run;
Cypher execution is a recorder. Both the null consumer mutation and the numeric
lexer producer mutation are detected, plus a changed deciding observation.
No query execution, null truth table, bound-parameter null rewriting, graph
semantics, arbitrary text serialization or Cypher-to-SQL proof is claimed.

Trust: bundled pinned vstd only, no assume/admit/external_body or actors.
Syntactically valid surrounding traversal and digit-prefix accumulation are
premises. The output is an abstract predicate/bounds; exact text is observed in
Python. Expected Python calculation is unverified. Implementation-verified 0.
RC-16 gains narrowly scoped evidence; no translator simplification is implemented.
