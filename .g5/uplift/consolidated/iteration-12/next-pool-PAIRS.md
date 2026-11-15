# Alternate underserved draw: generated GraphQL connection lifetime

Frozen before opening pooling/resolver implementation bodies. Selected from37
unlinked `iris_vector_graph/gql` members and the production entrypoint census,
independently of the known communities/ledger queue. The imported interfaces
owner distinguishes the sample API from the generated GraphQL app; do not apply
one app's shared-connection or lifetime rule to the other by analogy.

Prospective source-informed hypotheses, not adopted owner decisions:

1. If the generated server uses AsyncConnectionPool for requests, two overlapping
   borrowers cannot use the same connection simultaneously. A returned connection
   becomes available to the next borrower without creating an extra live link.
2. Raising or cancellation inside an acquired context returns its borrowed link;
   cancellation while waiting does not consume a nonexistent permit or connection.
3. Pool size controls the number of live links only if all actual request writers
   and borrowers use that pool. An unused pool class is not end-to-end coverage.
4. Startup introspection, per-request resolvers and shutdown may own different
   links. Trace those real consumers and final cleanup before claiming that a
   successful acquire proves server connection lifetime or request isolation.

Known sample/Bolt connection lifetime and concurrency findings remain separate.
No network server, security/auth scenario, native call, source patch or new model.
Inspect actual entrypoint→context→resolver→release next. Set aside an unconnected
helper rather than inventing a product guarantee for it. Record any uncovered
owner question without treating this forecast as human intent.
