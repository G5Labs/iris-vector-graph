# Iteration 60: grading of the frozen ledger predictions (native, local fixture)

All observations ran on the local fixture `ivg-uplift-next-20261115` (127.0.0.1:35975, IRIS Community 2026.1 Build 234U,
instance hostname `1a97b1515453` checked against the container before each run) in task-owned namespaces created
additively from `%SYS` with SQL `CREATE DATABASE` and deployed with `initialize_schema()` from the unchanged pin:
`I60LA` (W1 client/admission, lock, large), `I60LB` (W2 readers), `I60LC` (never enabled, then `max_ops=2`,
`recon_bound=1`), `I60LD` (`recon_bound=2`). IDs start with `i60`. Nothing was written in `USER`. Raw observations:
`probes/observed-20261117T194107Z-c.json`, `observed-20261117T194119Z-w1.json`, `observed-20261117T194244Z-w1-props.json`
(property re-read: the first run's helper read `get_node` with the wrong key shape), `observed-20261117T194249Z-w2-lock-large.json`,
`observed-20261117T194511Z-large-node.json` (same helper fix). Probe: `probes/ledger_probe.py`.

Provenance. Rows P*/S* (W1) and H*/D*/R*/V*/C* (W2) are the **adopted** iteration-59 tables
(`../iteration-59/ledger-client-PAIRS.md`, `ledger-replay-PAIRS.md`), frozen by a different session for the cloud fixture
(`I59LA`/`I59LB`, `ivg-cont-20261117-iris`); only the fixture names changed here (`I59LA`→`I60LA`, `I59LB`→`I60LB`, prefixes
`i59a_`/`i59r_`→`i60_`/`i60r_`). They are graded unedited (digests in `freeze-digests.txt`). Rows N1-N10 are **new**,
frozen in `PREDICTIONS-new.md` (commit `ebb8a679d`) before any ledger test or deciding source was read. None of these
rows is test-informed. Grades: **held** (every stated observation matched), **partial** (core held, a stated detail
missed), **missed**.

## Adopted W1 (client, changeset, admission, lifecycle, post-commit)

| ID | Grade | Observation |
|---|---|---|
| P1.1 | held | Retry with new message/correlation → `replayed=True`, same revision ID, head and history unchanged; same key with `v2` → `IdempotencyConflictError`, head unchanged, node keeps `v1`; fresh key → seq head+1. |
| P1.2 | held | Equal canonical JSON and 64-hex fingerprint; property-dict key order does not matter (the guess held: `sort_keys`); reversed ops → different fingerprint and `IdempotencyConflictError` under the first key; `actor_type` changes it; `message` does not. |
| S1.3 | partial | Reserved `id`/`__graph` refused at the builder, no server call, `idx` accepted; both relationship names → `ValueError`; one name accepted. Missed: the reserved-name class is `ChangesetOperationError` (with `op_index`), not a `ValueError`-like class. |
| S1.4 | held | `30` and `"30"` give one fingerprint; canonical JSON holds `"30"`. |
| P2.1 | held | Fresh `expected_head` commits with that parent; stale → `StaleHeadError` with `current_head` = Y's ID (attribute and message), head stays Y, node absent, next commit n+2. |
| P2.2 | held | Keyed retry with a stale `expected_head` replays; fresh key → `StaleHeadError`; unknown 32-hex → `UnknownRevisionError` (distinct class). |
| S2.3 | held | Empty changeset → `EmptyChangesetError` with a stale or current `expected_head` (client-side check; no counter moved, no hook event). |
| P3.1 | partial | A held: `NodeNotFoundError(missing_node='i60_missing', op_index=2)`, nothing applied, head unchanged, hook `failed_op`. B: commits and stubs the node, but the statement ID is keyed at op position **3**, not 2 (the builder inserts `upsert_node` before the relationship; the returned `OpRef.index` is 3 too). |
| P3.2 | held | Never enabled → `LedgerNotEnabledError`, hook `not_enabled`, nothing written; disabled → `LedgerDisabledError`, hook `disabled`, `rej_disabled` 0→1. |
| S3.3 | held | Every listed class subclasses `LedgerError`; an unknown wire code becomes a plain `LedgerError` carrying `"weird_code: why"`. |
| S3.4 | held | A raising hook leaves the result unchanged; event fields as documented; `enable()` emits no event (WARNING log line not captured). |
| S3.5 | held | `max_ops=2`: two ops commit; three → `ChangesetTooLargeError(limit=2)`, hook `too_large`, `rej_size_limit` 1. |
| P4.1 | held | Non-strict write succeeds and verify diverges; strict refuses `create_node` and Cypher `CREATE` (node absent), ledger commit still works, read-only Cypher allowed; `set_strict(False)` takes effect at once on the same engine. |
| P4.2 | held | Disable twice without error; unrecorded write while disabled, no revision; `enable()` → adoption revision (actor `system:ledger-verify`) recording it, strict now off; `enable(strict=True)` on an enabled ledger → head, no revision, strict stays off; after `disable()`, `enable(strict=True)` → adoption and strict on. |
| S4.3 | held | With `$TLEVEL` 1: `enable()` → `LedgerTransactionOpenError`; `disable()` not refused and joined the caller's transaction (state `disabled` inside, `enabled` after rollback). `set_strict` in the transaction not exercised. |
| S4.4 | partial | `meta()` shape held (state, strict, `max_ops` 50000, `recon_bound` 250000, plus head fields). Missed: `head()` before the first enable raises `LedgerNotEnabledError`, not `None` (the spec contract says so; N6 predicted it). |
| S4.5 | held | A second engine was refused 5.07 s after `set_strict(True)` (known F-0801 window). |
| P5.1 | held | `$REVISION_ID` substituted, `post_commit_applied=True`, no record, verify names `prop:last_rev`; without it no property; keyed replay re-applies over `'x'` (bug-led-003); strict does not stop it (bug-led-009). |
| P5.2 | held | Ghost target: property row with no node row and `get_node` answers a property-only node; inside a caller transaction rolled back: no revision, no property, head unchanged, next seq without a gap. |
| S5.3 | missed | No commit set the dirty flag (`_nkg_dirty` stayed False after a relationship create; `status().pending_sync` False). Cause found after grading: on this driver the Native API answers `None` for an absent `^NKG("$meta","nodeCount")`, and `str(None)` is not `""`, so `_mark_nkg_dirty_if_needed` never marks (kept as a candidate, see HANDOFF). |

## Adopted W2 (readers)

| ID | Grade | Observation |
|---|---|---|
| H1 | held | 5 revisions: `[1,2]`→2, `[3,4]`→4, `[5]`→None; 4 revisions: `[3,4]`→4 then `[]`→None (one extra read); `limit=0` → empty, no cursor; kinds and parent chain as predicted. |
| H2 | held | Newest first from integer 0: `[5,4]`→4, `[3,2]`→2; text `"0"` → empty page; `actor='a'` → `[2,4]`, `'A'` → `[2,4]`, `''` → `[]`. |
| D1 | held | One `prop:p` entry `'1'→'3'`; reverse swaps and equals `inverse()`; `inverse().inverse()` equal; equal endpoints empty; restored value → no entry; node entries before rel entries. |
| D2 | held | Deletion entry carries labels and properties in its snapshot; a life created and deleted inside the range contributes nothing; bug-led-101 history: separate deletion and creation entries, snapshot holds `q='2'`; reverse equals inverse. |
| R1 | held | Named revision vs head vs genesis as predicted; export lines are exactly the reconstruction's 10 nodes and 1 relationship; unrecorded node absent from `reconstruct(head)`, present after adoption and absent from the old head. |
| R2 | held | Detach delete (the row named detach): records `delete_rel` before `delete_node`, both gone at r3. Bound 1: head refused with `ReconstructionTooLargeError(bound=1, estimate=2)`, stream and export return `{a}`, the revision that created `a` reconstructs; bound 2 (`I60LD`) succeeds. Note: the default `delete_node` mode is `strict` and refuses a node with a relationship (`node_has_relationships`). |
| V1 | held | Clean verify equal twice, head unchanged; unrecorded node diverges, adopt appends one `adoption` revision, then equal; strict refuses and verify stays equal; SQL `UPDATE`/`DELETE` of `ledger_revisions` refused by the triggers (SQLCODE -132/-134), head and history unchanged. |
| V2 | held | Unrecorded `create_edge` → one relationship difference keyed by (s,p,o,graph); direct temporal write between recorded nodes → equal; Cypher `SET n.p = 30` over `'30'` → equal; temporal write to two new IDs → diverges naming both (bug-tmp-004). |
| C1 | held | Marked row: verify equal, not in `reconstruct(head)`, one-hop Cypher returns its row; explicit `create_edge` adopts it → diverges with exactly that relationship; adoption records `create_rel`; then equal and reconstructed. |
| C2 | held | One adoption revision with exactly: `set_prop cn p '2'→'9'`, `delete_node cz`, `create_node x`, `add_label x X`, `set_prop x k`; diff equals it; then equal. Ledger temporal op with upserts → equal and a `temporal_edge` diff kind; without upserts it commits and verify names `a3`,`b3` (bug-tmp-004; one of the two allowed outcomes). |

## New rows (N1-N10)

| ID | Grade | Observation |
|---|---|---|
| N1 | held | B's commit raised `LedgerLockTimeoutError` 40.0 s after the call while A's transaction held the head; after A's rollback head was h again and B's retry got seq h+1, parent h. Neighbor: A commits first → B succeeds at once, parent A's revision. |
| N2 | held | A key used inside a rolled-back caller transaction, and a key used only by a stale-head refusal, are both free for other operations; a kept key → `IdempotencyConflictError`. |
| N3 | held | Duplicate create → `ChangesetOperationError(op_index=1, 'relationship_exists: ...')`, `a.x` unset, head unchanged. Upsert → one edge, records `set_prop` + `set_qual w '2'`, no `create_rel`, `stmt_ids[1]` = the existing statement. |
| N4 | held | `create_node` with a label and a property → records `create_node`, `add_label`, `set_prop` (ordinals 1-3); mixed no-op → only `set_prop q`; all no-op → a revision with `op_count` 0 and no records (guess held). |
| N5 | held | `get_revision`, `diff`, `reconstruct`, `export_reconstruction` on unknown IDs (and `"xyz"`) → `UnknownRevisionError`; export wrote no file; head reads back; equal endpoints empty. |
| N6 | held | Never enabled: `head()`/`verify()`/`set_strict()` → `LedgerNotEnabledError`, history empty, status `never-enabled`, `stats()` returns without raising (`commits_ok` 0; `rejections` is an empty dict, not zeros). Disabled: head and history still read, status `disabled`, commit `LedgerDisabledError`. |
| N7 | held | Tuple-addressed `set_qualifier` records on statement S; `delete_relationship(stmt_id=S)` records `delete_rel` with the tuple JSON as prior; reconstruct lacks it; diff has one deletion; unknown statement → `op_index 0`; both names → `ValueError`. |
| N8 | held | Commit: `commits_ok` +1, status head = head; replay: no `commits_ok` or rejection change (`replays_idem` +1), hook `replayed`; stale: `rej_stale_head` +1; empty: nothing moves; strict refusal: `rej_strict_block` 0→1 (guess held). |
| N9 | held | Clean `verify(adopt=True)` writes nothing; after an unrecorded node one `adoption` revision by `system:ledger-verify`, parent the old head; the second adds nothing. |
| N10 | held | 2,000 ops of 2,500-character values (5,116,138 JSON chars, staged in chunks) committed as one revision: 2,000 records, every value 2,500 long, node holds all 2,000; 2,000 relationship creates → 2,000 statement IDs. |

## Totals

Adopted (20 rows): 16 held, 3 partial (S1.3, P3.1, S4.4), 1 missed (S5.3). New (10 rows): 10 held. The new rows were
written from the owner, the spec contract, docs and the models before tests or source; that they all held says those
sources predict this surface well, and it also means they were less risky than the guesses that missed. Material
predictions gained: N1/N2 (caller transaction holds the head lock; a rollback frees the key and the seq), N3, N4 and
N10 bind behavior that no model represented; S5.3's miss exposed a dirty-flag marker that never fires on this driver.
