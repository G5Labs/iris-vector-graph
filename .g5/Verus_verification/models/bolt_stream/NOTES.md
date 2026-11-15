# Bolt raw framing through final records

Product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`, foundation input
`9e1209165d5076039d2ee315cc5cf67e4aa00856`. Canonical owners are `access.bolt`,
`access.bolt.framing` and `access.bolt.results`. This is an as-built Verus
transcription, **not executable product-body verification**. Pinned bundled vstd
only, no assumes/admits/external bodies or imported product/proof trees. Final
expected count: **43 verifier units =39 proof declarations (32 theorems,7 helper
lemmas) +4 recursive spec termination obligations**, with19 named controls.
Source-first predictions are [retained](../../../uplift/consolidated/iteration-9/bolt-predictions.md).

## Raw deciding producer and buffer/queue

`scan` reads the unsigned big-endian header bytes, checks payload availability,
accumulates actual payload slices and emits a body only at a zero header. Its
`used` output is derived from those traversed bytes up to the last complete
message boundary. It is never supplied by the caller. All raw u8 buffers are
admitted, including partial headers/payloads, missing terminators and empty chunks.
The recursive encoder likewise derives each header/payload slice from the body
and legal chunk limit1..65535. Its API argument values outside that proof fragment
are unassessed, not claimed refused by the product.

`lemma_scan_encoded_prefix` proves the body and actual consumed boundary for any
admitted chunk limit and arbitrary body bytes, including bodies longer than65535,
with an arbitrary following raw suffix. `receive` independently reproduces the
as-built cut: it re-encodes **all decoded bodies at the default chunk limit**,
sums those lengths and slices the original raw buffer there. The queue contains
the remaining decoded bodies, and a queued body is returned before any receive.
Neither a predecoded message list nor a resolved consumed length is an input.

The two-byte RESET body split into one-byte chunks has8 received bytes but6
re-encoded bytes; the model derives the remaining terminator. A later RUN frame
then produces empty bytes with RUN queued, and WebSocket's falsey-byte end check
closes without consulting the engine. Default framing is a passing neighbor.
Coalescing small-chunk RESET and RUN is a different passing neighbor: RUN is already
queued, so it is delivered without another transport read despite buffer residue.
This is not a claim that all fragmented messages immediately close or suppress RUN.
Root's valid fragmented HELLO example instead executes RETURN1 but loses its PULL
records and remains STREAMING. The generic raw scanner permits such shifted outcomes.

An original empty NOOP chunk is a separate root: the raw decoder emits an empty
body even when the cut equals the true boundary; the WebSocket loop then closes.
Separate and coalesced NOOP witnesses preserve this distinction. The TCP loop uses
None-only EOF and is observed as a passing contrast with in-process StreamReader.
No socket/TCP listener is used or proved by that contrast.

The [primary message specification](https://neo4j.com/docs/bolt/current/bolt/message/)
permits arbitrary16-bit chunk payload lengths and describes NOOP support from4.1,
including both clients/servers, with4.3 allowing it across states. The root ordinary
session supplement negotiates4.4. Root has adjudicated the two functional roots as
[bug-plt-101](../../bugs_issues.md#bug-plt-101) and [bug-plt-102](../../bugs_issues.md#bug-plt-102),
Low/Suspected with in-process end-to-end evidence. This child opened no issue and
claims no live network/client/deployment reproduction.

## Pending producer, alternate writers and actual reader

The engine-result input retains raw optional error text alongside columns/rows,
plus the named thrown-query outcome. Nonempty text decides FAILURE/FAILED; None
and empty text remain successful. Scalar RUN installs the rows/type metadata and
preserves existing `_pending_columns`, matching the source's scalar branch.
The result constructor represents an admitted plain-provider fragment: at most
two string columns (there can be no node triplet), default scalar column types,
and builtin null/bool/int64/finite float/string/list/map record cells. Types and
encoded-value identity are retained as opaque `Cell` fields. General PackStream,
Decimal/custom values, graph objects and relationship encoders are external codec
fragments, not proved by declaring a cell. The binding tests independent typed
values and record byte encodings for its finite samples.

`dispatch` reads the actual body tag. Its raw PULL field decoder recognizes the
canonical tiny-integer map (including signed -1) and the empty map's as-built -1
default. Wider integer handler contracts are generic, but arbitrary PackStream
message schemas/coercions are not proved. Out-of-fragment RUN/PULL/authentication/
HELLO payloads return None in the model, meaning **unassessed**, not a product refusal.
The supported core starts after valid handshake/initialization with no configured
key/read-only refusal. It does not model an authentication or security scenario.

`pull` selects a positive prefix, emits its records and then clears the whole
pending result, columns and types, with absent has_more (protocol default false).
A second PULL therefore emits no records. `remainder` is computed from the original
rows/n, so the positive partial-PULL theorem exposes nonempty lost suffix rather
than taking has_more/remainder as an oracle input. This is inherited **F-1602**,
not a new defect. Nonpositive n emits all as-built; n0/other negative behavior is
retained without inventing a protocol-validity policy for it.

RESET and ROLLBACK clear result/columns/types. DISCARD clears result/columns but
retains types. COMMIT enters READY and keeps pending rows, so PULL still reads
them. A failed RUN clears only result and enters FAILED; columns/types remain.
FAILED ignores ordinary PULL/ROLLBACK/RUN before consulting the engine or parsing
fields, until RESET/GOODBYE. Graph-column metadata is outside the projection; RESET
also does not clear that source attribute, so no whole-metadata clearing is claimed.

`advance` connects the raw receive output to dispatch rather than inserting a
predecoded command. Its generic raw RUN/PULL theorem follows encoded bytes ->
actual scan -> queue/buffer -> pending result -> records -> cleared suffix and
empty second PULL. `record_rows` is the final symbolic record reader; actual Python
binding also reads emitted chunked PackStream bytes. Transport sends and named
engine results are faithful provider premises; partial-send, encoder failure,
cancellation, socket scheduling and database behavior are unproved.

Existing P Unit L2 already gives a substantive transaction/visibility model and
F-1601 control. This new package does not rediscover that gap or claim database
COMMIT/ROLLBACK from success acknowledgements. Named spy transaction ports receive
no calls in the new local binding; actual unit persistence remains inherited.

## Exact source roles, deliberately partial

| Pin declaration | Formal role / evidence |
|---|---|
| bolt_server.py::encode_message :256-269 | chunk_wire/encode, raw byte framing for legal chunk limits |
| _decode_messages_stateless :294-311 (the active decode_messages alias) | scan/decode, raw header/payload/body/actual-boundary producer; obsolete earlier decoder is not the active role |
| BoltSession._recv_message :439-456 | receive, default re-encoded cut, buffer and queue order |
| BoltSession.run :396-426 | ws_continues/advance falsey-body loop condition in admitted initialized session; handshake/auth/general error loop unproved |
| BoltSession._dispatch :459-531 | dispatch core tag/FAILED gate/pending commands; authentication payloads excluded |
| BoltSession._handle_run :567-622 | run, raw error text and scalar-result rows/type writer; graph/relationship paths excluded |
| BoltSession._handle_pull :624-660 | pull/selected/records/record_rows, integer prefix, actual pending loss and final records |
| BoltSession._handle_reset :662-667 | reset, projected rows/columns/types only |
| PackStream pack/unpack, bolt_message_bytes, _send_message | exercised codec/output context; fixed wire fragments/independent finite oracle, no generic codec body proof or whole-member reach requested |
| TcpBoltSession.run/_recv_message | actual local transport contrast, observed only; full TCP reader/EOF/network proof not requested |
| _get_engine and IVGResult | named provider/context, not a new cache/construction or whole-result implementation proof |

## Executed evidence and controls

Binding uses the pinned real encoder/decoder/session and AsyncMock/StreamReader
ports under a socket-connect guard. The reference independently scans headers,
constructs framing/typed PackStream samples, derives pending state from raw message
tags/fields and compares every state/record projection. It never substitutes the
consumed length, message queue, selected prefix or has_more decision.

Current finite panel:22 encoder comparisons;89 raw reader/decoder traces including
65535/65536 boundaries, incomplete and byte-split arrivals;188 actual dispatch/result
traces;12 full initialized WebSocket run journeys; a separate WS NOOP and TCP NOOP
contrast. Exact final counts are in the receipt. They are purposive overlapping
combinations, not independent population samples. Nine detections include eight
actual product method/decoder variants (counted raw cut, lost high header byte,
PULL slicing, suffix retention, COMMIT clearing, failed gate, RESET retaining rows,
folded error) and one altered final-record observation. The latter requires the
original to satisfy the unchanged input oracle and the altered value to fail it;
no edit-only inequality is credited.

Root's separate36-case [ordinary HELLO/session supplement](../../../uplift/consolidated/iteration-9/bolt-session-probe.json)
uses actual run/handshake/receive/dispatch/RUN/PULL and compares receiver-only,
loop-only and both method copies. It retains coalesced passing traffic and all4
TCP contrasts. These are proposed local repairs only; no product edit or socket
is involved. The binding stamps script/receipt/raw log and validates the expected
matrix. Root's initial overbroad coalesced-failure oracle is preserved/retracted;
that is a harness expectation miss, not another product defect.

Nineteen formal controls alter header, incomplete emission, payload accumulation,
cut/queue/loop, raw error, pending state/slice/remainder/has_more, metadata/reset,
FAILED gate and signed PULL rules. Every named target must show an actual failed
postcondition under isolated verification; resource/parse failure alone receives
no control credit. Some whole-control runs hit resource limits in other obligations;
the retained isolated named logs distinguish real target failures from those limits.

49 selected upstream pinned codec/chunk/handshake/graph-pack units pass in0.80s
pytest,1.33s guarded total,0 socket calls. Authentication tests are deliberately
not selected. Failed development proof logs/receipts remain; they exposed proof
fuel/sequence-extensionality needs, not new product issues. Initial binding passed
None into IVGResult's list-typed column metadata and used an async close for a sync
writer; a second attempt had a dedented method-copy anchor mismatch. Exact failed
sources/logs are retained under iteration9/bolt-attempts and not counted positive.

## Replay and costs

```sh
export RUN_DIR=/Users/ziniuw/runs/ivg-iteration9-bolt-20261115 VERUS_RUN_THREADS=4
export VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus
export IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin PYTHONDONTWRITEBYTECODE=1
unset CONTROL
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/bolt_stream
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/bolt_stream
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/bolt_stream/binding.py
```

Per-phase costs/latest freshness are in iteration9/bolt-validation.json. This work
improves one material framing/result contract; it is not a convergence claim.
No token/cache/currency or solver-only CPU measure is available. No product,
shared tooling/ontology/imported tree, Git staging/commit or runtime was changed.
