# Iteration 59 (W2): frozen predictions, ledger replay and readers

Frozen at 2026-11-17 08:59 UTC by worker W2, before any deciding source was opened. Not opened: anything under
`iris_vector_graph/ledger/`, `iris_vector_graph/_engine/ledger.py`, `iris_src/src/Graph/KG/Ledger*.cls`, any crosswalk
row, any model `.rs`/`binding.py`, `specs/213-*`, the ledger tests.

Sources read (and only these): `/tmp/i59-common-brief.md`; `README.md` (feature table line 144); `docs/USER_GUIDE.md`
section 9 "The revision ledger" (lines 1052-1131) and the transaction paragraphs naming the ledger (262-307);
`docs/API_REFERENCE.md` "Revision ledger" (2352-2363, only the `ledger` property is documented there);
`docs/ADMIN_GUIDE.md` lines naming the ledger (tables, `^IVG.Ledger`, restore guidance 975-982);
`CHANGELOG.md` ledger entries (lines 80-85, 2210-2228, 2767-2769, 3040-3047, 4795-4803, 4976-4979, 5279-5330);
`docs/KNOWN_ISSUES.md` "A value written through the ledger is stored as its text" (305-330);
`.g5/ontology/features/ledger.g5.md` blocks ledger.revision, ledger.lifecycle(.genesis), ledger.node-scope,
ledger.immutability, ledger.unrecorded, ledger.strict, ledger.readers, ledger.readers.history, ledger.readers.bound,
ledger.readers.diff, ledger.verify, ledger.verify.meaning, ledger.verify.scope and their metadata sections;
`NOTES.md` of models history_paging, history_diff, reconstruction, ledger_content, ledger_apply.

Source tags: **UG** USER_GUIDE section 9; **CL** CHANGELOG; **KI** KNOWN_ISSUES; owner block IDs as written;
**owner-Today** marks a prediction that is the as-built behavior an owner block or inherited finding already records
(it checks the owner, not the intent); **NOTES:<model>** marks a behavior an existing model's NOTES records.

Fixture (all predictions): container `ivg-cont-20261117-iris`, a namespace `I59LB` created from `%SYS` for this
iteration, schema deployed, ledger enabled only there (non-strict unless stated). Data are API-written with prefix
`i59r_`; changesets have actor `w2`. Readers are the public client `engine.ledger.{history,get_revision,diff,
reconstruct,export_reconstruction,verify}` plus, as a second reader where named, a Cypher/SQL read of the tables.
Where a parameter name is not documented (history direction, enable's reconstruction bound, verify's difference
fields) the prediction names the behavior and phase 2 reads the name; that reading does not change the prediction.

Each row is one prediction (A) and its reachable neighbor (B): a one-step change of input or history, the same
reader, and the observable difference expected between them.

## 1. History paging (ledger.readers, ledger.readers.history, ledger.revision)

| ID | Prediction A | Neighbor B | Source |
|---|---|---|---|
| H1 continuation and final page | History of 5 revisions (genesis seq 1, four changesets seq 2..5). Default order is oldest first. `history(limit=2)` → seqs `[1,2]`, next cursor 2; with cursor 2 → `[3,4]`, cursor 4; with cursor 4 → `[5]`, **no** cursor (short page). Kinds `['genesis','changeset',...]`; each revision's parent is the previous revision's ID, seqs contiguous. | Same calls on a history of 4 revisions: page 2 `[3,4]` is exactly full and **still returns cursor 4**; the third read returns `[]` and no cursor (one extra empty read). `history(limit=0)` → empty page, no cursor, in both histories. | UG ("history(limit=10)" oldest first); ledger.readers.history (owner-Today: full page always returns a cursor); ledger.revision; NOTES:history_paging |
| H2 newest-first and cursor zero; filter before limit | Newest-first order on the 5-revision history, integer cursor `0`, limit 2 → `[5,4]`, cursor 4; cursor 4 → `[3,2]` (cursor seq and everything newer excluded). | Same first call with the cursor given as **text** `"0"` → empty page (owner-Today: text "0" is truthy, selects seq < 0). Separate filter neighbor: with actors `a,b,a,b` on seqs 2..5, `history(actor='a', limit=2)` → `[2,4]` (filter applied before the limit, not one row); `actor='A'` also → `[2,4]` (database comparison accepts ASCII case changes, owner-Today); `actor=''` → `[]` (empty text is a supplied filter). | ledger.readers.history; NOTES:history_paging |

## 2. Diff and inverse (ledger.readers, ledger.readers.diff)

| ID | Prediction A | Neighbor B | Source |
|---|---|---|---|
| D1 continuous attribute, inverse | Node `n` with `p='1'` at revision r1 (changeset), `set_property(n,p,2)` at r2, `set_property(n,p,3)` at r3. `diff(r1,r3)` → exactly one property entry for (`n`,`p`) before `'1'` after `'3'` (first prior, last new; values as text per KI). `diff(r3,r1)` → the same entry with before/after swapped, and it equals `diff(r1,r3).inverse()` (same entries, same order); `inverse().inverse()` equals the original. `diff(r1,r1)` → no entries. | Change r3 to `set_property(n,p,1)` (value restored): `diff(r1,r3)` → **no** entry for `p` (net zero), while `diff(r1,r2)` still has `'1'→'2'`. Adding a relationship in r2 makes the diff list node entries before rel entries, each sorted by entity ID then attribute (`entity_kind` values `node`, `rel`). | ledger.readers; ledger.readers.diff; UG; NOTES:history_diff |
| D2 lifecycle, inverse applied | Node `d` (label `L`, `q='x'`) exists at r1; r2 deletes it. `diff(r1,r2)` has a deletion entry for `d` carrying its labels and properties in its JSON snapshot; applying `diff(r1,r2).inverse()` to `reconstruct(r2)` (re-create `d` from the snapshot) gives `reconstruct(r1)`. A node created at r2 and deleted at r3 contributes **no** entry to `diff(r1,r3)`. | bug-led-101 history: `d` has `q='1'` at r1; r2 sets `q='2'`; r3 deletes `d`; r4 recreates `d`; r5 sets `q='3'`. `diff(r1,r5)` has separate deletion and creation entries; the deletion snapshot holds `q='2'`, not `'1'` (owner-Today: the range prior is lost), so applying the inverse to `reconstruct(r5)` gives `q='2'`, **not** `reconstruct(r1)`'s `q='1'`. `diff(r5,r1)` still equals `diff(r1,r5).inverse()`. | ledger.readers.diff (owner-Today, bug-led-101); NOTES:history_diff, ledger_content |

## 3. Reconstruct at a revision (ledger.readers, ledger.readers.bound)

| ID | Prediction A | Neighbor B | Source |
|---|---|---|---|
| R1 named revision vs head | Node `n` created with `p='1'` at r2, `p='2'` at r3, relationship `n-K->m` at r4. `reconstruct(r2)` → `n` with `p='1'`, no relationship; `reconstruct(head)` → `n` with `p='2'` and the relationship; `reconstruct(genesis)` → the pre-enable graph without `n`. A later revision (r5) does not change `reconstruct(r2)`. `export_reconstruction(r2, path)` writes NDJSON lines (`type: node|rel`) for exactly the same entities. | Same reads after an **unrecorded** `create_node('i59r_u')`: `reconstruct(head)` does **not** contain `u` (only the history), while the tables do; after `verify(adopt=True)` `reconstruct(new head)` contains `u` and `reconstruct(old head)` still does not. | ledger.readers; ledger.readers.bound; UG; ledger.unrecorded |
| R2 deleted entities and the bound | Node `d` with relationship `d-K->m` at r2, `delete_node(d)` (detach) at r3. `reconstruct(r2)` → contains `d` and the relationship; `reconstruct(r3)` → neither (the relationship's deletion is recorded before the node's). | Fresh empty namespace, ledger enabled with a reconstruction bound of 1 entity: create `a`, then `b`, then delete `b` (three changesets). `reconstruct(head)` **refuses** with `ReconstructionTooLargeError` although the final graph has 1 entity (the prefix after `b` held 2; owner-Today: the check runs after each record), while the stream mode and `export_reconstruction` return the final graph `{a}`; `reconstruct` of the revision that created `a` succeeds. With bound 2 the head read succeeds. | ledger.readers.bound (owner-Today); NOTES:reconstruction, ledger_content |

## 4. Verify after an unrecorded write vs a clean ledger (ledger.verify, .meaning, .scope, ledger.unrecorded, ledger.revision, ledger.immutability)

| ID | Prediction A | Neighbor B | Source |
|---|---|---|---|
| V1 clean vs unrecorded | Clean ledger (genesis + changesets): `verify().result == 'equal'`; calling it twice does not move the head. | After `engine.create_node('i59r_u')` (non-strict): `verify().result == 'diverges'`, the differences name `i59r_u` as an unrecorded write; head unchanged by verify. `verify(adopt=True)` appends one revision of kind `adoption` (seq head+1, parent the old head) recording it; the next `verify()` → `'equal'`. Under strict mode the same `create_node` raises `LedgerStrictModeError`, writes nothing, and `verify()` stays `'equal'`. A raw SQL `UPDATE` (or `DELETE`) of a `ledger_revisions` row is refused (immutability), and the head and `history()` are unchanged. | UG; ledger.verify; ledger.unrecorded; ledger.strict; ledger.revision; ledger.immutability |
| V2 scope: what verify compares | Unrecorded `create_edge(a,K,b)` between two ledger-recorded nodes → `'diverges'` with one relationship difference keyed by (source, predicate, target, graph). | Direct temporal write `create_edge_temporal(a,K2,b,...)` between the same recorded nodes → `'equal'` (its plain marked row is outside verify on both sides; the temporal index is not compared). Second neighbor: a Cypher `SET n.p = 30` over a ledger-written `p='30'` (same text, different stored type) → `'equal'` (verify compares the value's text, which the ledger treats as identical). A direct temporal write to two **new** endpoint IDs → `'diverges'` naming the endpoint nodes (owner-Today, bug-tmp-004). | ledger.verify.scope; UG; CL 3046; KI 305; bug-tmp-004 |

## 5. Canonical read and compare, adoption items, temporal-marked rows (ledger.verify.scope, ledger.unrecorded)

| ID | Prediction A | Neighbor B | Source |
|---|---|---|---|
| C1 temporal-marked rows | After the direct temporal write of V2-B (marked row for `a-K2->b`), `verify()` is `'equal'` and `reconstruct(head)` has no `a-K2->b`, though a one-hop Cypher read sees it. | Then an explicit `create_edge(a,K2,b)`: the row is adopted and its mark cleared, so the same row is now canonical but unrecorded → `verify()` `'diverges'` with exactly that relationship; `verify(adopt=True)` records a relationship create for (`a`,`K2`,`b`) in the adoption revision; next `verify()` `'equal'` and `reconstruct(head)` now has `a-K2->b`. | CL 3040-3047; ledger.verify.scope; ledger.unrecorded |
| C2 adoption items across kinds | Unrecorded, in one step: `create_node('i59r_x')` with label `X` and property `k`; a non-ledger property change on recorded node `n` (`p` from `'2'` to `'9'`, via `store_node`/Cypher SET); `delete_node` of recorded node `z`. `verify()` → `'diverges'` naming all three; `verify(adopt=True)` → one adoption revision whose records cover: node create + label + property for `x`, a property set on `n` with prior `'2'` new `'9'`, a node delete for `z`; `diff(old head, adoption)` shows exactly those net changes; `reconstruct(adoption)` equals the tables; next `verify()` `'equal'`. | Ledger's own temporal operation: a changeset `upsert_node(a2)`, `upsert_node(b2)`, `create_temporal_edge(a2,T,b2,ts=...)` → `verify()` `'equal'` and `diff` over that revision contains an entry with `entity_kind='temporal_edge'`; the same changeset **without** the two upserts (endpoints missing) → `verify()` `'diverges'` with `a2`,`b2` as unrecorded nodes (owner-Today, bug-tmp-004) or the commit refuses with `NodeNotFoundError`; either outcome is recorded, `'equal'` would be the miss. | ledger.unrecorded; ledger.verify; CL 4802; bug-tmp-004 |

## Count

Ten prediction rows (two per workflow), each with its neighbor: 20 observable outcomes (more where a row lists a
second neighbor). Supplementary checks folded into V1: strict refusal and `ledger_revisions` immutability.
