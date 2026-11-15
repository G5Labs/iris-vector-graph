# Independent remaining-work draw before implementation/model inspection

Product3eaa79cf; foundation9e6a876f plus current iteration8 candidates. Selected from
README features -> USER_GUIDE weighted-path documentation, API reference and named
unit/E2E tests, then README Bolt support -> ADMIN_API entry plus Bolt codec/session
and typed CALL result tests. Public M12 weighted shortest path is already a known
published gap, so this is not a new blind/private draw. Bolt result/transaction
behavior is independently selected from entry-point compatibility, outside the
recent temporal/FHIR/procedure/health panels. No evaluator-private material used.

Authorities read before existing models and algorithm/session implementation:
USER_GUIDE631-668, tests/unit/test_weighted_shortest_path.py (misnamed unit file
actually requires IRIS), tests/e2e/test_dijkstra_cost_e2e.py, tests/unit/
test_weighted_shortest_path_parameters.py; README Bolt compatibility, ADMIN_API14-30,
tests/unit/test_bolt_server.py and typed CALL Bolt replay in test_460_r314_call_yield_values.py.

- A1 documented positive-weight minimum: s->a cost4, s->b cost1, b->a cost1,
  a->t cost1. No hop bound admits cheapest cost3; maxHops2 must instead admit
  s,a,t cost5. A bound concerns relationships, not which intermediate node was
  first reached. This tests a numerical/algorithmic distinction, not cache admission.
- A2 source==target should give length0/cost0, unreachable gives empty, unsupported
  weightProp and invalid direction refuse; parameters bind actual IDs. Existing
  tests cover those wrapper neighbors. We will distinguish real numerical execution
  from a mocked DijkstraJson response.
- A3 weights0/negative are normalized to1 according to the cost-search E2E's stated
  domain; an independent reference comparison must use the same effective weights.
  The existing E2E compares DijkstraCost to DijkstraJson, which is agreement between
  two shipped algorithms, not by itself an external optimality oracle.
- B1 a RUN result is read by PULL. With rows[1,2,3], PULL n1 then PULL n1 should
  preserve the unpulled suffix rather than replay or discard it; n-1 consumes all.
  This is a compatibility-derived working expectation to verify against primary
  protocol documentation before judging it a requirement.
- B2 a result.error is a FAILURE, not empty successful rows. RESET should clear
  result/failure state before another RUN; plain typed list/map values should be
  delivered in record fields without converting JSON-looking text to objects.
- B3 BEGIN/RUN/ROLLBACK versus BEGIN/RUN/COMMIT should reach an actual transaction
  owner or explicitly refuse unsupported transactions. Success acknowledgements
  alone cannot establish database rollback/commit. Existing local docs do not yet
  settle supported explicit-transaction policy; keep that unconfirmed until source
  and canonical owners are inspected.

No native, network, listener, runtime, authentication or privilege scenario will be
executed. Bounded in-process source/unit probes use a socket-connect guard. Before
claiming convergence distinguish existing formal hits, missing raw producers,
tractable new models, expensive numerical/provider work and unassessed behavior.

## Later source-derived framing challenge, frozen before probe

B4 is added after tracing the real pending-message writer `_recv_message`, not
retroactively counted as an original blind case. The product encoder accepts
`max_chunk=1` as well as its default; stateless decode should recover identical
message bodies. A WebSocket receives complete chunk-encoded messages which can
use that permitted smaller chunking. `_recv_message` appears to compute consumed
bytes by re-encoding each decoded body with the default chunk size, rather than
using the actual incoming byte count. Predict that the first decoded body is
correct but leftover framing can make a following valid message appear empty or
corrupt. Contrast default encoding versus small-chunk encoding; no network/listener,
authentication, engine or database will be used. This is a source-derived candidate,
not an adjudicated new bug or an existing model result.
