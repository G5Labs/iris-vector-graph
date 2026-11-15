# Bolt stream handoff

Input seal9e120916, product3eaa79cf unchanged. New bolt_stream derives raw chunk
headers/payload/body/actual consumed boundary, as-built default re-encoded cut,
buffer/queue, then raw RUN/PULL fragment -> pending rows -> final records/remainder.
Expected43 units (39 proof declarations,4 termination) and19 named deciding-effect
controls. Actual local byte/session binding and root36 supplement are separately
qualified in NOTES. Parent owns issue/canonical/crosswalk integration; no new issue
was opened by this builder. Existing F-1601 Unit model is a substantive inherited
hit; F-1602 suffix loss is inherited. Root's new bug-plt-101/102 remain Low/Suspected.

## Canonical text recommendations

Keep access.bolt the overview and use its existing minimal children, access.bolt.framing
and access.bolt.results. Suggested as-built text, preserving intended protocol rules:

> WebSocket Bolt reads chunk headers and payloads into messages and queues complete
> messages in order. Today it advances the raw buffer by default re-encoded message
> lengths, so valid smaller chunks can leave old bytes and disrupt a later request
> or result; coalescing the whole exchange can still succeed because messages were
> already queued. An empty NOOP body also ends its WebSocket loop, while the local
> TCP reader continues. These are separate suspected roots, not a general failure
> of every fragmented exchange.

> A successful plain RUN replaces pending rows; a nonempty error enters FAILED.
> As built, positive PULL emits its prefix then clears all pending rows and omits
> has_more, losing the suffix (F-1602). RESET/ROLLBACK clear pending rows; DISCARD
> clears them while COMMIT keeps them. FAILED ignores ordinary requests until
> RESET/GOODBYE. These result rules do not establish database transaction atomicity.

The primary Bolt link and actual4.4 initialized-session evidence belong beside the
framing statements. Do not turn source/adapter observations into a deployed-network
claim or approved repair. General auth/handshake/codec/graph result/transport failure
paths remain outside this new proof; preserve existing owners and transaction model.

Formal metadata should link the stable bolt_stream.rs plus NOTES. Active proposed
source roles are encode_message, active _decode_messages_stateless, BoltSession
_recv_message/run/_dispatch/_handle_run/_handle_pull/_handle_reset in the qualified
fragments. PackStream, bolt_message_bytes/_send_message, TCP reader and engine
cache/result constructors are observation/context only, not generic new formal reach.

## Misses and validation

Predictions precede candidate/model construction. The original RESET small-chunk
witness loses later RUN; root's ordinary HELLO witness executes RUN but loses the
record/PULL. Coalesced queues are a retained passing neighbor. The root's initial
coalesced-failure expectation was withdrawn, with its raw failed artifact retained.
Builder failures were an invalid Pydantic fixture and a method-copy indentation
anchor, plus early proof fuel/sequence obligations; none are product defects or
controls. Final receipts/raw commands/costs/freshness are in bolt-validation.json.
Independent review is requested separately before parent sealing; no held-out
benchmark grade or new simplification is inferred from this package.
