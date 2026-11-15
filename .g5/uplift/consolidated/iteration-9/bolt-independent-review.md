# Independent Bolt stream review

Product3eaa79cf; foundation input9e1209165d5076039d2ee315cc5cf67e4aa00856.
Reviewed the frozen source/model/binding/NOTES, root's36 local full-session cases,
retained overbroad packet oracle and revised canonical owners/issues. This is an
independent source review and isolated replay, not held-out grading. No product,
shared foundation, model, native/runtime/network or Git mutation was made.

**Verdict: accept the declared framing/plain-result fragment.** Independent
43-unit baseline and all19 named controls reproduce; each named control has an
explicit failed assertion/postcondition with no named resource limit. The actual
Python binding agrees on its full finite panel with zero socket calls. No change
to the candidate is requested. This does not verify arbitrary PackStream, a real
listener/driver, database transactions, authentication, partial sends or cancellation.

## Expectations and source chain

Read iteration8 remaining/framing PAIRS, survey/probes and iteration9 predictions
before the candidate. Kept the following distinctions: valid alternate chunking
must preserve the stream; incomplete input must not become a complete body;
coalesced complete bodies can pass while residue remains; partial PULL should
retain its suffix by intent but currently drops it (known F-1602); RESET, DISCARD,
ROLLBACK, COMMIT and failed RUN are different pending-state writers. The old P Unit
transaction model remains a separate substantive hit, not new stream coverage.
The observations are builder-visible and source-informed, not fresh hidden cases.

The active decoder is `_decode_messages_stateless`, assigned to decode_messages
after the obsolete earlier definition. The model correctly follows that active
alias. `scan` derives uint16 header sizes, actual payload slices, accumulation and
last complete boundary from raw bytes. The generic encoder-prefix lemma handles
every legal positive chunk limit<=65535, arbitrary body bytes and arbitrary suffix.
Neither decoded bodies nor consumed byte count is supplied as a decision input.

`receive` then separately transcribes the actual wrong cut: sum each decoded body's
default re-encoding length, slice the original buffer there, retain the other
decoded bodies and return queued data before another receive. `advance` composes
that raw extraction with the WebSocket falsey-body loop and tag dispatch. The
generic raw RUN/PULL chain reaches pending rows and final records, rather than
beginning with a predecoded command or final prefix/has_more answer. Out-of-frame
commands return unassessed None, not a fabricated refusal.

Source state details checked against the model:

- Scalar RUN preserves `_pending_columns`; it installs rows/default scalar types.
  An empty error string succeeds, a nonempty error/throw fails. Failed RUN clears
  rows but preserves columns/types, then FAILED gates ordinary dispatch before
  decoding fields or consulting the engine.
- Positive PULL emits a selected prefix, then clears every row, columns and types
  and omits has_more. Nonpositive handler n emits all as built; raw tiny-integer
  and empty-map wire cases derive their count, including signed-1.
- None pending preserves metadata, while Some(empty rows) takes the clearing path.
  RESET/ROLLBACK clear rows/columns/types; DISCARD retains types; COMMIT preserves
  pending rows. Graph-column metadata is explicitly outside this projection.
- Plain provider frame is at most two string columns/default scalar types, avoiding
  the source's node-triplet/relationship branches. Opaque Cell kind/payload equality
  proves symbolic record identity; general value-to-PackStream correctness is not
  obtained from declaring a Cell. Finite independent typed byte checks supply the
  observed codec correspondence only.

The decoder/advance program's NeedMore is an internal receive-step abstraction;
actual `_recv_message` loops for more bytes. Full handshake/EOF scheduling and
exception/cancellation transitions are not proved. The initialized no-configured-
key/read-only-refusal frame is explicit; no authentication scenario was tested.
Named engine results/throws are provider inputs. The fixed RETURNv proof body
does not verify Cypher query semantics or an actual database result.

## Independent full-session matrix and corrected oracle

I replayed root's actual session/handshake/receive/dispatch/RUN/PULL probe with
local WS objects and TCP StreamReader/writer, a one-row engine adapter and zero
socket connections. All36 expected cases reproduce. Localized copies change only
receive's byte cut, only run's EOF test, or both; no product file is changed.

| Baseline/repair neighbor | Actual retained outcome |
|---|---|
| default HELLO, no NOOP | query1, record1, final DEFUNCT |
| one-byte-chunk HELLO, separate later frames | query1, **records0**, STREAMING, buffer residue |
| same fragmented HELLO, all coalesced | query1, record1, DEFUNCT, residue remains |
| canonical HELLO plus NOOP, separate or coalesced | WS query0/record0, READY when loop closes |
| receiver-only copy | fixes fragmented/separate case, NOOP still fails |
| loop-only copy | fixes canonical NOOP, fragmented/separate HELLO still loses records |
| both copies | expected scalar record for every WS packetization case |
| all4 actual TCP contrasts | expected record, including NOOP, with no TCP socket |

The initial root oracle expected fragmented HELLO to fail even when all messages
were coalesced. The passing coalesced trace disproves that claim; it remains
preserved under bolt-attempts/overbroad-packet-oracle. The current corrected matrix
is faithful. Also, the HELLO trace loses **PULL output after RUN**, whereas the
two-byte RESET witness can close before queued RUN. Root's wording erratum and
revised canonical/issues preserve this phase distinction. Neither failure should
be generalized to every fragmented body or every packetization.

## Intent, issue roots and claim scope

Reviewed current IDs `access.bolt`, `access.bolt.framing`, `access.bolt.results`.
They preserve protocol intent separately from the as-built failures and existing
transaction owner. The shipped Bolt compatibility commitment plus root's primary
protocol adjudication supports arbitrary legal chunking and Bolt4.4 NOOP. This
review inspected local sources/evidence and did not independently fetch the web
specification under its no-network scope.

bug-plt-101 is the raw byte-count/re-encoding root; bug-plt-102 is the empty-message
WebSocket loop root. Receiver-only/loop-only contrasts show they are independent.
Neither duplicates F-1602's suffix discard or F-1601/P Unit's database transaction
root. Low/Suspected end-to-end with actual local Python transports is appropriately
qualified: an actual listener, real WebSocket/TCP client or deployment route was
not exercised. The metadata says so. No new security classification, owner repair
approval or native network reproduction is inferred. The as-built theorems that
expose these failures do not weaken the intended framing/PULL rules.

Eight binding sensitivities modify actual product function/decoder copies. The
ninth is a weaker **oracle-sensitivity** check: the original actual record must
satisfy the unchanged input-derived oracle before a deliberately altered typed
record is rejected. It is labeled as an observation check, not a ninth product
implementation mutation or a new behavior. All19 formal controls separately change
deciding effects and require isolated named false postconditions/assertions.

## Isolated replay and identities

Scratch: `/Users/ziniuw/.cache/g5-verification/ivg-iter9-bolt-review-wgpxj2qk`.
Copied only the runner, binding_common, frozen Bolt package and root session
supplement. Exported product pin is the shared read-only pin; Git object identity
lookup is read-only against the real repository. RUN_DIR is scratch/run, four
Verus threads, no source/native mutation. Exact frozen hashes:

- Model `e33a117863fb22d2c012748e0eff64341096153e1ed0a5e3a49458b2681d82b5`.
- Manifest `d88b622ff5ad38a33d02315012f8f65eaea1b557efdea313c96593280d386194`.
- Binding `58d4f258f71ff905588053d1a905446e27e7c6ce0145239c36c1a9b25fe31b72`.
- NOTES `ac7e6870f5f1829d2260719830b51a5e41468ffeee56ce20fdbd8506f70bd229`.

Baseline43 verified/0 errors in2.491s. All19 controls EXPECTED_FAIL in79.230s.
Three whole-mutant runs have resource limits in other obligations:
decoded-queue-dropped, queue-waits-for-new-frame and empty-message-keeps-ws-open.
Their isolated named targets show ordinary explicit failures without resource
limits, as do all other named targets. No resource-only failure receives credit.
The scratch independent-control-audit.json records every target and raw log.

Binding AGREES:22 encoder,89 raw framing,188 dispatch/result,12 full initialized
WS journeys and2 NOOP contrasts; zero mismatch/socket calls; nine sensitivities
split as above. Binding internal time1.006s. The separate independent full-session
rerun records36 cases/zero socket calls in independent-session-probe.json/log;
probe0.045s (first command0.668s), preserved refreshed command also succeeds.
The49 upstream unit results were inspected builder evidence, not independently
rerun or counted again here.

All copied frozen inputs equal the current builder files at review. Scratch
logs/receipts, frozen-inputs.json and verifier cost JSON are retained. The finite
panel is purposive and overlapping, not a repository prevalence estimate. Exact
token/cache/currency or solver-only CPU cost is unavailable. No whole-member body,
arbitrary codec/protocol, actual network, database/transaction or convergence claim
follows from this accepted fragment.
