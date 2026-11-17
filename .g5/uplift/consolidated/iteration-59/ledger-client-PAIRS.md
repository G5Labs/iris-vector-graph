# Iteration 59 (W1, ledger client and changeset): frozen predictions

Frozen at 2026-11-17 ~09:05 UTC (start 08:56:43 UTC), before any deciding source was read: no line of
`iris_vector_graph/ledger/*.py`, `iris_src/src/Graph/KG/Ledger*.cls`, the ledger guard, or any crosswalk row quoting
them was opened. Member names come only from the assignment's census list and the docs.

Sources read (and nothing else): the iteration-59 common brief; `README.md` (feature row); `docs/USER_GUIDE.md`
section 9 (lines 1052-1125) and "Writes inside your transaction" (lines 270-310); `docs/API_REFERENCE.md` "Revision
ledger" (lines 2352-2364); `docs/ADMIN_GUIDE.md` ledger and `^NKG` maintenance passages (grep hits; lines 940-990,
1028-1050); `docs/KNOWN_ISSUES.md` "A value written through the ledger is stored as its text" (305-330);
`docs/ledger-prometheus-hook.md` (linked from ADMIN_GUIDE line 1320; source of the outcome names); `CHANGELOG.md`
ledger entries (30-40, 76-90, 698-712, 1140-1148, 2208-2230, 4860-4880, 4975-5000, 5278-5330, 6144-6158); owner
blocks `.g5/ontology/features/ledger.g5.md` (whole page, including metadata) and `.g5/ontology/concepts/access.g5.md`
`access.ledger_strict*`; model notes `models/ledger_redaction/NOTES.md`, `models/ledger_apply/NOTES.md`,
`models/retry_replay/NOTES.md` (temporal, not reused), a keyword grep of `models/ledger_content/NOTES.md`.

Marks: **doc** = user documentation, **owner** = owner block text (block ID given), **owner-Today** = an as-built
deviation the owner records (prediction checks the owner, not the intent), **guess** = no source settles it; the
prediction is my best reading and its miss is informative.

Fixture: namespace `I59LA` created from `%SYS`, schema deployed, ledger enabled only there. Prefix `i59a_`. Readers:
`engine.ledger.head()`, `history()`, `get_revision(...).records`, `verify()`, the raised exception (class and
attributes), `CommitResult` fields, `Changeset.canonical_json()` / `fingerprint()` (names as in CHANGELOG 213:
"canonical JSON, SHA-256 fingerprint over {actor, actor_type, ops}"), `engine.get_node`, a metrics hook registered
with `register_metrics_hook`, `engine.ledger.stats()`, `engine.status()` / `verify_sync()`.

## W1 Changeset validation and canonical fingerprint

| ID | Prediction A | Neighbor B (one input changed) | Reader and observable difference | Source |
|---|---|---|---|---|
| P1.1 idempotency key | Commit C1 = (actor `a`, actor_type `t`, ops O, key K). Then commit C2 = same actor, actor_type and ops O, key K, but a different `message` and `correlation_id` → `CommitResult.replayed is True`, `C2.revision.revision_id == C1.revision.revision_id`, head seq unchanged, history length unchanged, graph unchanged | C2' = same key K, same actor, ops O with one property value changed (`"v1"` → `"v2"`) → `IdempotencyConflictError`; head unchanged; the node keeps `"v1"`; a later commit with a fresh key gets seq head+1 (no gap) | `replayed` + equal revision ID vs raised class; `head().seq` equal in both | owner `ledger.idempotency` (fingerprint covers actor, actor_type, ops only; message/correlation do not count); doc USER_GUIDE "Retries" |
| P1.2 operation order | Two changesets built independently with the same actor/actor_type and the same ops in the same order (`set_property(n,'a','1')`, `set_property(n,'b','2')`) → byte-identical `canonical_json()` and identical `fingerprint()` (64 hex, SHA-256); the property-dict key order inside an op does not matter (`create_node(..., properties={'x':1,'y':2})` vs `{'y':2,'x':1}` → equal) | Same two ops in reversed order → different canonical JSON and different fingerprint; committing the reversed changeset under C1's key → `IdempotencyConflictError` (order is part of the operations, which apply in order). Changing only `actor_type` → different fingerprint; changing only `message` → same fingerprint | `fingerprint()` equality; conflict vs replay on commit | owner `ledger.changeset` ("in order", "same changeset → same JSON form and fingerprint"), `ledger.commit` (ops apply in order); dict-key insensitivity is **guess** (from "canonical") |

Supplementary (W1): S1.3 `set_property(n, 'id', ...)` and `set_property(n, '__graph', ...)` raise at the builder call
(a `ValueError`-like client exception, **guess** on class), no server call, head unchanged; neighbor `'idx'` is
accepted. A relationship op naming both a statement ID and a (s,p,o) tuple is refused at the builder; naming exactly
one is accepted (owner `ledger.changeset`, `ledger.commit.admission`). S1.4 a numeric property value `30` appears in
the canonical JSON and record as the text `"30"` (doc KNOWN_ISSUES), so `set_property(n,'p',30)` and
`set_property(n,'p','30')` give the same fingerprint (**guess** that the fingerprint is taken after stringification).

## W2 Expected head and stale head

| ID | Prediction A | Neighbor B | Reader and observable difference | Source |
|---|---|---|---|---|
| P2.1 stale head | Read `h = head()` (seq n). Commit X with `expected_head=h.revision_id` → succeeds, seq n+1, parent `h.revision_id` | Read `h` (seq n); another commit Y lands (seq n+1); then X with `expected_head=h.revision_id` → `StaleHeadError` that names the current head (Y's revision ID, attribute or message); head stays Y; X's node absent; no seq consumed (next commit gets n+2) | success+parent vs raised class + named head; `get_node` | owner `ledger.commit.expected-head`; doc USER_GUIDE "Concurrency" |
| P2.2 admission order | After Y, resend an earlier keyed commit K1 (same key, same fingerprint) with a now-stale `expected_head` → replays (`replayed=True`, K1's revision), no `StaleHeadError` | The same stale `expected_head` with a fresh key → `StaleHeadError`. And `expected_head` = 32 lowercase hex that is no revision → `UnknownRevisionError` (distinct class from `StaleHeadError`) | replay vs stale vs unknown class | owner `ledger.commit.admission` (key before expected head), `ledger.commit.expected-head` |

Supplementary (W2): S2.3 an empty changeset with a stale `expected_head`: server order puts size last, so if the
client sends it the answer is `StaleHeadError`; if the client checks emptiness first, `EmptyChangesetError`
(**guess**: I predict `EmptyChangesetError` from a client-side check, since the builder knows the op count; a miss
confirms the server order). Expected head equal to the current head with an empty changeset → `EmptyChangesetError`.

## W3 Error mapping from server codes to Python exceptions

| ID | Prediction A | Neighbor B | Reader and observable difference | Source |
|---|---|---|---|---|
| P3.1 failing operation | Changeset `[create_node(a), create_node(b), create_relationship(a,'R','i59a_missing')]` → `NodeNotFoundError` with `.missing_node == 'i59a_missing'` and the failing op position 2 (zero-based) in the exception; nothing applied (a, b absent), head unchanged, hook outcome `failed_op` | Same ops with `Changeset(auto_stub_missing_nodes=True)` → commits; `i59a_missing` exists; result's statement IDs give one entry at op position 2 | exception class/attributes vs success + statement-ID map | doc CHANGELOG spec 217; owner `ledger.commit` (zero-based position, statement IDs by op position) |
| P3.2 disabled vs never enabled | Fresh namespace (ledger never enabled): `commit(cs)` → `LedgerNotEnabledError`, hook outcome `not_enabled`, nothing written | After `enable()` then `disable()`: the same `commit(cs)` → `LedgerDisabledError`, hook outcome `disabled`, `stats().rejections['rej_disabled']` incremented by 1; nothing recorded | class + hook outcome + stats counter | owner `ledger.lifecycle`; doc ledger-prometheus-hook (outcome list, `rej_disabled`) |

Supplementary (W3): S3.3 every mapped class is a subclass of `LedgerError` (`StaleHeadError`, `UnknownRevisionError`,
`IdempotencyConflictError`, `NodeNotFoundError`, `ChangesetTooLargeError`, `EmptyChangesetError`,
`LedgerDisabledError`, `LedgerNotEnabledError`, `LedgerLockTimeoutError`, `LedgerStrictModeError`), and an
unrecognised server reason maps to a generic `LedgerError` (or op error) carrying the reason text rather than being
swallowed (**guess** on the fallback). S3.4 a hook that raises is logged at WARNING and the commit's result is
unchanged; the hook sees `op_count`, `actor`, `actor_type`, a float `duration_ms`, `revision_id`/`seq` only on
success/replay, and `reason` only on refusal (doc ledger-prometheus-hook). `enable()` does not call the hook.
S3.5 `ChangesetTooLargeError` when ops exceed `max_ops` given at enable (e.g. `enable(max_ops=2)` and a 3-op
changeset; 2 ops commit), hook outcome `too_large`.

## W4 Enable / disable / strict lifecycle effects on ordinary writes

| ID | Prediction A | Neighbor B | Reader and observable difference | Source |
|---|---|---|---|---|
| P4.1 strict toggle | Ledger enabled, not strict: `engine.create_node('i59a_free')` succeeds; `verify().result == 'diverges'` with the node among unrecorded writes; a ledger commit still works | After `set_strict(True)` on the same engine: `engine.create_node('i59a_blocked')` → `LedgerStrictModeError`, node absent; `execute_cypher("CREATE ...")` refused the same way; a ledger `commit` still succeeds; `set_strict(False)` → `create_node` works again (same engine, no 5 s wait) | `get_node` present vs exception + absent | doc USER_GUIDE strict example; owner `ledger.strict`, `ledger.unrecorded`, `access.ledger_strict` |
| P4.2 disable / re-enable | Strict ledger, then `disable()` (twice: no error the second time): `create_node('i59a_off')` succeeds (strict governs an enabled ledger only) and creates no revision; `enable()` again (default `strict`) → a new revision of kind `adoption` recording `i59a_off`; strict is now off (`create_node` succeeds); `verify()` equal apart from writes after the adoption | `enable(strict=True)` on an already-enabled non-strict ledger → returns the current head, writes no revision, and does NOT switch strict on (`create_node` still succeeds; "changes nothing"). Neighbor of the re-enable: `enable(strict=True)` after `disable()` → adoption revision and strict on | revision kinds in `history()`, `head()` equality, `create_node` outcome | owner `ledger.lifecycle` (+ working assumption: strict set on every re-enable, default False), `ledger.strict` (enabled ledger) |

Supplementary (W4): S4.3 `enable()` inside an open caller transaction → `LedgerTransactionOpenError`, nothing changes
(doc CHANGELOG 4.7.x); `disable()` and `set_strict()` inside the same open transaction are NOT refused (owner
HD-1102 is still open and the metadata says only enable/redact refuse) and their change joins the caller's
transaction: after the caller's rollback the ledger is enabled again (**owner-Today**, mechanism partly **guess**).
S4.4 `head()` before the first enable → `None` or `LedgerNotEnabledError` (**guess**: `None`); `meta()` (undocumented)
returns the enabled flag, strict flag, `max_ops` (default 50000) and `recon_bound` (default 250000) (**guess** on
shape). S4.5 a second engine on the same namespace sees `set_strict(True)` within about 5 s, not necessarily
immediately (owner `ledger.strict` working assumption, known F-0801; not a new finding).

## W5 Post-commit properties and NKG dirty marking

| ID | Prediction A | Neighbor B | Reader and observable difference | Source |
|---|---|---|---|---|
| P5.1 post-commit properties | Commit creating `i59a_p` with `post_commit_properties={'i59a_p': {'last_rev': '$REVISION_ID'}}` → `post_commit_applied is True`, `post_commit_error is None`; `get_node('i59a_p')` has `last_rev == result.revision.revision_id`; `get_revision(...).records` has no record for `last_rev`; `verify().result == 'diverges'` naming that property | The same changeset without `post_commit_properties` → no `last_rev`, `verify()` equal. Replay neighbor: change `last_rev` to `'x'` with a direct write, resend the keyed commit → `replayed=True` and `last_rev` is the revision ID again (re-applied; **owner-Today**, bug-led-003). Strict neighbor: under `set_strict(True)` the post-commit property is still written (**owner-Today**, bug-led-009) | node property + verify result | owner `ledger.commit.post-commit`, `ledger.idempotency` metadata; CHANGELOG spec 218 |
| P5.2 post-commit target and transaction | `post_commit_properties` naming an ID with no node (`i59a_ghost`) → `post_commit_applied is True` and a property row for `i59a_ghost` with no node row (`get_node` answers none or a property-only node, **guess**); verify diverges | Inside a caller transaction then rollback: neither the revision nor the post-commit property remains; head unchanged; no seq gap | property presence vs absence; `head()` | owner `ledger.commit.post-commit` metadata ("IDs need not exist"), `ledger.commit.caller-transaction`; doc USER_GUIDE txn section |

Supplementary (W5): S5.3 NKG dirty marking: a commit that creates or deletes a relationship leaves `^NKG` stale and
the engine reports it (`verify_sync().pending_sync` / the in-memory dirty flag set, or `status().pending_sync`
True) while a commit of node properties only leaves the flag clear (**guess**: CHANGELOG names "NKG dirty-marking"
as a commit concern and `^NKG` "is not kept from the rows"; which op kinds set it is not documented; my
prediction is "any relationship create/delete", not deletes only). A refused commit sets nothing.

## Counts

10 core predictions (2 per workflow) and 10 supplementary ones (S1.3, S1.4, S2.3, S3.3, S3.4, S3.5, S4.3, S4.4,
S4.5, S5.3; S1.3, S3.4 and S4.4 hold two observations each). Known findings these touch, which the observation
checks but does not count as new: bug-led-003 (replay re-applies post-commit, no statement IDs), bug-led-009
(post-commit bypasses strict), bug-doc-002 (retry needs a key), F-0801 (5 s strict cache), bug-plt-025 (guard cache).
