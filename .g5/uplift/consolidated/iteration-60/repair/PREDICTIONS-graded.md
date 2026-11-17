# Iteration 60 repair: prediction grades

Predictions: [PREDICTIONS.md](PREDICTIONS.md), committed at `00966ce88` (sha256 `df2b22fb…e1fc14`) and its addendum at
`91d574425`, both before any native run. They are **exposed** (informed by the published review and by my source
reading of the deciding members); these grades are repair confirmations, not independent discovery.

Observations (local fixture `ivg-uplift-next-20261115`, IRIS 2026.1 Build 234U, instance hostname `1a97b1515453`
checked on every connection; unchanged product `3eaa79cf`):
[setup](probes/observed-20261117T210719Z-setup.json), [fe1 fe2 fe5 c4](probes/observed-20261117T210756Z-fe1-fe2-fe5-c4.json),
[fe4 fe3](probes/observed-20261117T210820Z-fe4-fe3.json); bindings
[ledger_client](../../../../Verus_verification/results/ledger_client/20261117T212518Z-binding/receipt.json) and
[ledger_verify](../../../../Verus_verification/results/ledger_verify/20261117T212044Z-binding/receipt.json).

| ID | Grade | Observed |
|---|---|---|
| R1.a | held | `temporal="yes"` committed: verify `equal`, no entry |
| R1.b | held | row `{"temporal":"true","w":"1"}`; verify `diverges`/`unrecorded_writes` with existence, `qual:temporal`, `qual:w`; adoption seq 4 (create_rel + 2 set_qual); next verify the same three entries |
| R1.c | held | `True` stored as `{"temporal":"true"}`; same divergence; adoption seq 6; still diverging |
| R1.d | held | unrecorded `create_edge(..., {"temporal": "true"})`: existence + qualifier entries; adoption seq 7; still diverging |
| R1.e | held | unrecorded `create_edge(..., {"temporal": True})` stored `{"temporal": true}`: no entry before or after |
| R2 | held | orphan post-commit property (0 node rows, prop row `k=v`): entries node existence + `prop:k`; adoption then `equal` |
| R3.a | held | B waited 40.0 s, `LedgerLockTimeoutError`; `rej_lock_timeout` 0 while A open and after A's rollback; B then committed the next seq with the prior head as parent |
| R3.b | held (and the test note was wrong here) | the Native API `lock("", 2, "^IVG.Ledger", "head")` WAS seen by ObjectScript: B waited 30.0 s, `rej_lock_timeout` +1. (`tests/integration/_tcp.py` says a Native API lock is invisible to `Lock`; on this fixture it was not. Not registered: test-helper commentary only.) |
| R3.c | held | `Ledger.Count("rej_strict_block")` while A open: 10.0 s, error status from `%SaveData` on `Graph.KG.LedgerStats`, +0; after A ended: immediate, +1 |
| R3.d | held | A's nested 5,000-character-message commit: `LedgerInconsistencyError`; B waited 30.0 s, +1, kept after A's rollback |
| R4 | held | `RedactionInProgressError`; events `["redaction_in_progress"]`; every counter unchanged; head unchanged |
| R5 | held | during: all four readers `RedactionInProgressError` for an unknown ID, `head()` still read; after: all four `UnknownRevisionError`; no export file written |
| R6.a | held | message 4,000 committed, `commits_ok` +1 (and key 256 committed) |
| R6.b | held | message 5,000, key 300, correlation 300, actor 300, object source 4,100+: `LedgerInconsistencyError("revision row save failed: ... MAXLEN ...")`, event `inconsistent`, no counter, head unchanged, 0 node rows |
| R6.c | held | keyed retry with a 5,000-character message: `replayed=True`, same seq, `replays_idem` +1 |
| R7.a | held | escaped as `iris_vector_graph.ledger.errors.NodeNotFoundError`, `op_index` 1 |
| R7.b | held | caught by the ledger class, `IVGError` and `ChangesetOperationError`; `issubclass(ledger, root)` False |
| R7.c | held | `set_property`, `add_label`, `remove_property` on a missing ID: ledger `NodeNotFoundError`, `op_index` 1, message "create_relationship failed: node '...' does not exist ..." |
| R8 | held | the two-rule model proves `theorem_text_marker_never_equal`; the unconditional adoption theorem fails without `no_text_marker` (control `text-marker-premise-dropped`) |
| R9 | held | `theorem_caller_transaction_holds_the_head` proves with `o2.srv.cnt == o1.srv.cnt`; control `stats-row-not-held` (the iteration-60 lock + 1 model) fails it |

**20 rows: 20 held, 0 partial, 0 missed.** One expectation outside the table was wrong: my first client-binding
redaction setup (batch size 1) assumed one batch would reach the target; the batch scans only `batch_size x 20` records
from the start of the history, so with a longer history it tombstoned nothing and left no marker (run 1 crashed; log
kept in [probes](probes/ledger_client-binding-run1-crashed.log)). The probe's earlier redaction worked only because its
namespace history was short. This is a harness-setup miss, not a product finding (the batch scan cap is documented in
`LedgerRedact.cls`); redaction is an excluded area and was not investigated further.
