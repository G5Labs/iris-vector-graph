# Independent remaining-work survey: weighted numerics and Bolt results

The [retained draw](next-survey-remaining-PAIRS.md) records selection and expectations
before algorithm/session implementation and current formal inspection. Product3eaa79cf,
foundation9e6a876f, no private holdout. README/documented entry points selected the
known-public M12 weighted path plus a different ordinary Bolt result/transaction
workflow. These are purposive source-first questions, not independent grading or a
repository prevalence draw. Only next-survey-* artifacts were written by this survey;
no model/shared foundation/product/Git/native runtime changed.

## What the existing foundation already answers

`algorithms.op.paths.weighted` accurately states the intended cheapest path, effective
weight1 for absent/nonpositive weights, direction/property refusal, cost/hop bounds,
per-graph scope and decimal result shape. Its metadata explicitly says that neither
DijkstraJson nor DijkstraCost has a formal optimality contract. The inherited P
`atrav_l1/l2` covers **unweighted result contracts**, not search implementation: an
`ans` is constrained to satisfy `shortest` over the read graph. No weighted queue,
relaxation, hop-state dominance or path-backtrack proof is hidden in those declarations.
The current C cache/procedure contracts also do not establish numerical optimality.
Thus missing M12 proof is an honest existing gap, not a rediscovered product failure.

`access.transactions` keeps the unanswered policy—real explicit transactions or
refusal—and states the as-built per-RUN commit behavior. Imported P `unit_l2` has a
substantive reviewed transaction model plus `control_f1601_bolt_run_commits` and its
counterexample. That models the visible unit/rollback failure; it must be retained
as an existing formal hit, not called absent because the C/G member census has no
Bolt declaration links. It does not represent pending result rows, PULL sizes,
wire framing, record emission, remaining suffix or `has_more`.

## Weighted producer, writers and final reader

Actual path: parser -> `_proc_ivg_shortestpath_weighted` -> parameter/property/direction/
number validation -> graph census or explicit graph -> DijkstraJson versus DijkstraCost
selected by YIELD -> native traversal -> backtrack/PathJson -> decoded path/cost ->
RETURN projection/public execute_cypher. The handler forwards graph and maxHops to
**both** routes. A cost0 is retained, empty/no-path is no row, and provider/search or
JSON errors are not silently accepted as no path. Selected existing mock units
already distinguish those boundaries; no new wrapper defect was found.

The frozen A1 graph (s-a4,s-b1,b-a1,a-t1) needs cost3 unbounded but cost5 at maxHops2.
The actual ObjectScript has the necessary branch: distance/parent/priority queue are
keyed by node and hops under a bound; an already settled node is expanded again when
reached in fewer hops. The cost route invokes DijkstraJson when its cheapest meeting
exceeds the hop bound. A clearly labeled **unverified source-shaped Python sanity
transcription** gives3/5 and a node-only-state mutant gives no bounded path. This
supports why a real proof needs hop state; it is **not actual ObjectScript execution**,
a new Verus theorem or native optimality evidence. A3 nonpositive-weight behavior
was inspected (`edgeW<=0` becomes1), not freshly executed in native search here.

The numerical input is produced by persisted weighted adjacency: row/index writes
and `Adjacency.Put/PutShadow/PutKeyed`, legacy EdgeScan forwarding and rebuilds can
alter the read out/in leaves. PutKeyed's multigraph scalar leaf uses the lowest
ekey's weight, not an assumed minimum parallel-edge weight; a weighted proof must
state whether its input graph is this projection and bind that deciding writer.
Temporal structural writes and restores are further existing writers. They are not
all newly audited or made harmless by a wrapper test. The search reads shared ^KG
while its queue/parents are process-private, so stable graph/read semantics and
ObjectScript numeric/collation behavior remain correspondence premises to settle.
No numerical or concurrent safety was inferred from the existing cache token models.

Actual [guarded probe](next-survey-remaining-probe.py) executes **36** parser/handler/
route/public-result cases with named algorithm-port responses, varying graph,0/2/3
hops, cost-only versus path result and all three directions. It checks exact endpoint/
hop/graph forwarding and decoded result projection. The native algorithm result is
substituted. Calling these36 numerical searches would be false. Their source hashes
and equality to the exported pin are retained in the JSON.

## Bolt final records and competing state writers

Actual path: local framed bytes -> `_recv_message`/queue -> `_dispatch` -> RUN's real
engine-result/error reader -> pending rows/columns/type writers -> PULL record encoding
-> PackStream/chunked response bytes. `_get_engine` lazily retains the per-session
engine. RUN replaces the pending result; a failed RUN clears it and enters FAILED;
RESET clears result/type state; DISCARD and ROLLBACK clear rows; COMMIT changes READY
but leaves pending rows. PULL clears the result after sending its selected rows.
The FAILED dispatch gate ignores PULL and ROLLBACK until RESET (or GOODBYE). This
message-level state is finer than the existing unit-visibility model.

**21** actual in-process session/codec traces use typed IVGResult providers and an
AsyncMock WebSocket transport with a socket-connect guard, including:

- rows1/2/3 and PULL -1/0/1/2/3/4 followed by PULL1: positive n emits its prefix,
  then drops the suffix and omits has_more. This corroborates **known F-1602**, not
  a new bug. n0's all-row outcome is kept as an additional as-built observation,
  without adjudicating an invalid-n protocol requirement here;
- DISCARD/ROLLBACK/RESET versus COMMIT before PULL, folded error->FAILURE, ignored
  messages under FAILED and RESET recovery;
- eight null/bool/number/list/map/plain-text values, including JSON-looking text,
  preserved in actual PackStream records rather than decoded as another type;
- BEGIN/RUN/ROLLBACK versus COMMIT: no transaction command reaches the named spy
  connection port. This is real Bolt forwarding behavior with a substituted engine,
  **not** a fresh live database rollback experiment. Known F-1601 and its existing
  formal visible-unit counterexample remain the stronger inherited evidence.

Removing the actual PULL slice in a method copy changes the as-built first-record
oracle and is detected; the probe does not credit mere edited!=original inequality.
The existing transaction, error and typed-value observations are retained hits.
The missing pending-suffix/result-reader contract is material even though its defect
is already cataloged: no active formal specification found distinguishes the rows
that a second PULL can observe or maps them back to the producer's full result.

## New source-derived framing challenge

This later B4 challenge is separately frozen in PAIRS before its executable probe.
`BoltSession._recv_message` computes consumed bytes by **re-encoding** each decoded
body with default chunk sizes. That can differ from the actual incoming framing.
The product encoder/stateless decoder accept the same RESET body split into one-byte
chunks; the stateful WebSocket reader decodes RESET correctly, retains its terminator,
then returns **empty bytes for the following valid RUN**. With the default chunk size,
or chunks2/3 for this two-byte first body, the following RUN is preserved.
[next-survey-framing-probe.json](next-survey-framing-probe.json) retains every raw
frame/body/buffer for the four contrasts. Actual session run treats empty bytes as
end of input, so this can close the ordinary WebSocket session before that query.
No socket, listener, engine, authentication or database is involved.

The primary [Bolt message specification](https://neo4j.com/docs/bolt/current/bolt/message/)
permits arbitrary chunk sizes up to the16-bit maximum; one-byte chunks are valid.
It also documents keepalive NOOP chunks from Bolt4.1. The WebSocket `if not msg` end
check versus TCP's None-only check suggests a separate NOOP neighbor; it was **not
executed** by this survey and remains explicitly unassessed. No protocol conformance
claim beyond the tested bytes follows. The framing case was not located as an
existing finding in the inspected register; it remains a **new candidate for root
adjudication**, not a child-opened defect or an increased register count.

## Scope, counts, costs and next decision

[Sealed-iteration7 census extract](next-survey-remaining-census.json) lists53 Bolt
members, three native Dijkstra declarations and the weighted handler without valid
named declaration links under that instrument. This is not zero formal behavior:
P Unit/authorization/unweighted contracts remain, and no denominator is narrowed.
Exact unlinked identities are in that artifact; broader production distribution
stays in the parent reach report.

Selected existing guarded units: **112 passed in2.07s**, total command2.83s,0 socket
calls. They cover weighted argument/route/refusal/GDS and ordinary Bolt codec/chunk/
handshake/graph encoding; authentication tests and the misnamed weighted unit file
that needs actual IRIS were excluded explicitly. The main57 actual source traces
(36 wrapper+21 Bolt) take0.462s; the separate four framing contrasts are recorded
with their own elapsed time. These sets are not added to a population score. The
three A1 sanity outcomes are separate unverified transcription evidence. Tokens,
cache, currency and solver cost are unavailable; no new Verus run was requested.

**Strongest tractable next package:** Bolt buffer/message extraction plus pending
result lifecycle. Start from raw chunk headers/payload lengths, actual consumed
bytes and queue/buffer state, then RUN rows -> PULL/DISCARD/RESET/ROLLBACK/COMMIT ->
records/remainder/has_more. Preserve the as-built framing failure and F-1602 alongside
intended compatible behavior. A model that takes a parsed message list, supplied
consumed length or arbitrary has_more flag would miss the deciding producer. Keep
engine/PackStream/custom graph objects and network scheduling conditional unless
actually represented. Existing P transaction policy/model should remain distinct.
Estimated bounded builder cost roughly45–120 minutes plus review; that is a planning
estimate, not a task budget or measured promise. A passing default-chunk/all-row
neighbor and failing small-chunk/partial-PULL controls would establish useful closure.
No native database is needed to settle those ordinary buffer/result decisions.

The expensive remaining weighted minimum claim is also material. A faithful proof
needs ordered queue selection, relaxation, positive effective costs, bounded-hop
state dominance, parent/path relation and both-sided cost termination/fallback,
then real adjacency writer/read/provider correspondence. A rational/integer fragment
and bounded native oracle could be a starting phase; arbitrary floating costs and
live graph interference require further evidence. This is **not blocked because
it is hard**, and Community IRIS should be sufficient for sampled weighted paths;
this child simply did not access root's native runtime. A credible initial numerical
proof/correspondence package is likely several hours rather than the current tiny
wrapper probes; exact cost is unresolved until the proof/API inventory is chosen.

This independent draw finds existing supported hits and concrete material missing
formal distinctions. It **does not support convergence or diminishing returns**.
Root should continue from the real buffer/suffix candidate rather than claim that
old known defects,112 passing tests or current temporal/FHIR panels saturate the
foundation. Unexamined wire states, generic numerical algorithms, full graph
transactions and physical provider behavior remain honest residuals.
