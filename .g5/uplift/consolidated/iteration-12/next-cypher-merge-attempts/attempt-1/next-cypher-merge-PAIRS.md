# Next Cypher write draw, before implementation inspection

Builder-selected from the iteration12 before census (980 unlinked Cypher
members), canonical query.writes/.atomic/.create-existing/.conformance and node
typed-read intent, plus pinned history/test names for MERGE SET. This is a large
underserved subsystem, independently of the communities and ledger gap queue.
The recent fixes and their regression tests are known inputs, not discoveries or
private evaluation. No new model starts before a later iteration before image.

Prospective neighboring outcomes:

1. A new MERGE identity runs ON CREATE assignments and leaves ON MATCH assignments
   untouched; a matched identity runs only ON MATCH. Existing node CREATE keeps
   prior property values, while explicit SET changes them.
2. Computed number, boolean and text assignments are actual expression results,
   never AST spellings. Node writes preserve their stored type through a later
   MATCH filter and result reader. Relationship qualifiers keep their documented
   text-decoder limitations rather than acquiring node-type fidelity by analogy.
3. An assignment reading another MATCH-bound node sees that row's typed value.
   An assignment reading the merged node or relationship sees the correct live
   entity. A parameter with number2 and text"2" must not silently use one prepared
   supplied result. Numeric-looking text arithmetic still has the documented
   coercion qualification; equality/type tests distinguish stored types.
4. Every stage of a stepped MERGE uses the matched row frame captured for the
   write. Later branch writes cannot change which original rows receive other
   assignments. A refusal rolls back this write, including earlier steps, while
   preserving the caller's earlier work.
5. The read result, a subsequent independent query and raw stored type/value agree
   on the selected new/matched branch. Checking SQL text alone does not settle
   persistence, decoding, graph scope, or transaction behavior.

Inspect parser/AST, typed expression translation, row capture, branch gating,
native SQL effect and final node/relationship readers next. Restrict any finite
native probe to fresh task-prefix identities and the owned instance. Preserve
known deviations and all unsuccessful forecasts; no security cases or repairs.
