# History pages through the actual result reader

As-built transcription at product `3eaa79cf`, foundation input iteration5
`47236c829a48215db58c1677637b3fc41cc85310`. Pinned Verus
`0.2026.10.04.426d8b0`, bundled vstd only, four threads. Twenty verified obligations,
thirteen decisive named controls. No assume/admit/external_body in this model;
no product executable body is verified.

## What the model represents

`Table` contains every revision row once, keyed by unique sequence; `frame`
requires the enumerated IDs and row map to agree. `admitted` derives cursor and
all actor/type/time/correlation/source predicates from those persisted fields.
`ordered` sorts admitted sequence keys in the requested direction; it reuses
vstd `Seq::sort_by` and its proved total-order/multiset law, rather than taking
ordered output as an input. `prefix` then limits the rows. Generic theorems prove
the raw predicates, derived order, preserved selected count and final decoded
sequence identities. A distinguishing three-row theorem retains both late
matches; a filter-after-limit control fails it.

`finish` supplies the last sequence whenever a nonempty page has exactly the
requested size. It has no extra-row lookahead: an exactly full final page supplies
a cursor too, and the subsequent empty page supplies None. Time bounds include
equality. Zero limit returns an empty page; negative TOP is refused by the pinned
IRIS provider before a result page. `attempt` distinguishes failed cursor open,
query execute/fetch and final decode from a successful empty page; after acquiring
a cursor the code attempts close exactly once. It does not prove server resource
release if close itself fails.

Descending cursor selection depends on the original argument's truthiness BEFORE
integer conversion. `cursor_input` represents integers and successfully converted,
nonempty integer text: integer0 starts from newest, while text"0" adds `seq < 0`
and returns no positive revision. Both source primitive branches and a changed
product condition are checked. General arbitrary Python-object coercion and failed
integer parsing remain outside this decoded input projection; no new API validation
or rejection rule is inferred.

`decode` is a projection of the actual RevisionInfo reader: sequence/time/count
are integers; optional empty parent/message/correlation/key become None; a present
SQL NULL in a stringified field becomes text"None". The ghost `wire` retains raw
comparison fields, so a source JSON filter is evaluated before the reader changes
its representation. The model does not implement a general JSON parser or claim
that RevisionInfo.source is always a dict. Twelve explicit actual decoder cases
observe object/list/scalar/invalid-text and falsey JSON behavior separately.

## Provider comparison is consequential

The first source probe used case-preserving test values without case challenges.
Source inspection found `%String` columns without an exact-collation override.
Root's fresh native commits and actual history calls establish that actor,
actor_type, correlation_id and raw JSON-source filters accept ASCII case changes.
They also accept trailing spaces and TABs; leading spaces do not match. The final
model's SqlUpperAscii mode therefore uppercases ASCII letters and removes trailing
space/TAB. Its Binary mode is an alternate-provider comparison, not the product
claim. Dedicated altered rules lose uppercase or trailing-whitespace agreement.

This is an explicit provider fragment. General Unicode/locale collation, other
control characters, deployed schema drift, text truncation/coercion and arbitrary
provider versions are not proved. Native provider observations are linked and
hashed in the binding receipt; a changed provider/configuration requires rechecking
them even if the source and theorem inputs are unchanged. A successful-query
theorem assumes the SQL engine faithfully evaluates this comparison/order/limit
over the table snapshot; positive provider failures are represented by `attempt`.
The implementation is ObjectScript/Python, not verified SQL/IRIS bodies.

Source filtering compares stored serialized text under that collation, not
semantic JSON values. `Ledger.CommitInTxn` serializes an object source using
`%ToJSON` and omits non-object source; its whole serialization, commit and
redaction protocols are not modeled by this reader package. Actual native
object-source commits ground the sampled source rows. `ClearRevision` is a
competing writer: it sets the four metadata fields to SQL NULL, so a later page's
filter population can differ. Each invocation reads the then-current table; the
fixed-table pagination reasoning is not a stable multi-call snapshot or a proof
under concurrent commit/redaction. Correlation-index initialization and faithful
SQL index contents are also provider/setup premises, not discharged here.

## Product roles and limits of each link

| Role | Production member | Formal declaration | Evidence |
|---|---|---|---|
| public argument producer/caller | `iris_vector_graph/ledger/client.py::GraphLedger.history` | `history` / `cursor_input` | actual wrapper forwards all parameters; Python/SQLite agreement |
| deciding query producer and page consumer | `iris_vector_graph/ledger/replay.py::fetch_history` | `admitted` / `ordered` / `selected` / `finish` / `attempt` | real SQL executes through adapter; native TOP/collation boundaries supplied by root |
| row-field producer for final object | `iris_vector_graph/ledger/replay.py::_rev_from_row` | `decode` | actual named-column zip and RevisionInfo construction, full numeric/optional projection |
| final typed reader | `iris_vector_graph/ledger/client.py::RevisionInfo.from_wire` | `decode` | projection proved; JSON-source cases observed only |

The query source, deciding parameters, persisted SQL values and final caller-visible
page all participate. These four links cover the named reader behaviors, not the
entire methods or the prior commit/redaction writers. Relevant but unbound provider
roles include the `%String` collation and SQL engine, `LedgerRevision.BuildCorrelationIndex`,
`Ledger.CommitInTxn`/`WriteRevision`/genesis and `LedgerRedact.ClearRevision`.
Those residual roles must not be credited as complete writer-to-reader verification.

## Replay and evidence

From the repository root:

```sh
export RUN_DIR=/Users/ziniuw/runs/ivg-iteration6-history-20261115
export VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus
export VERUS_RUN_THREADS=4 PYTHONDONTWRITEBYTECODE=1
export IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/history_paging
CONTROL=limit-before-filter python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/history_paging
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/history_paging/binding.py
```

Omit CONTROL to run all thirteen. The final **6080** actual Python/SQLite journeys vary both
directions, zero/negative/positive limits, cursor positions, every filter family,
empty table, omitted/empty filter and case/space/TAB/JSON-text neighbors. Full
RevisionInfo sequence/time/count/parent/source/actor/kind/message/correlation/key
payloads are checked. Deliberately non-monotone insertion order cannot supply the
expected order by fixture construction. Exact-full final pages and final empty
calls are retained, along with execute/fetch/decode/open fault cases and twelve
explicit decoder cases. Five product/observation controls detect changes to
cursor inclusivity, full-page cursor, actor filtering, converted cursor truthiness
and final revision identity.

SQLite adapts only TOP to LIMIT and installs the observed collation fragment.
It deliberately rejects negative TOP according to root's native IRIS evidence;
SQLite's negative LIMIT would otherwise mean unlimited. Root's separately run
`history-top-native`, `history-collation-native` and
`history-collation-spaces-native`, `history-collation-interior-native` and
`history-continuation-native` scripts/JSON are receipt inputs. The native interior
spacing neighbor confirms that formatting a JSON source differently can change
selection even when decoding would give the same object. Actual limit1 forward
and reverse native continuation pages end with the extra empty request and retain
full RevisionInfo payloads. This builder
did not use the root-owned live runtime. The native image/provider version and
hostname check are recorded with those observations and iteration5 setup.

All failed proof/type/count attempts and the two initial control-anchor ERRORs
remain preserved. They are not violations or control successes. The final model
and control receipts supersede them. Binding expected rows use independent
selection/sort/count calculations and explicit source decoder expectations; the
adapter/expectation transcription is unverified Python. No independent grading
or repository-wide rate follows from this purposive source panel.
