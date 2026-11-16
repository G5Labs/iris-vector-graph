# W41: bulk_load_session with and without a caller's transaction — predictions frozen before observation

Frozen 2026-11-16, iteration 35. Before image: seal 34 `9c668218`. Product `3eaa79cf`. Fixture `ivg-retest-20261116-iris`.

Why this workflow: step 5. `bulk_load_session` is the engine's own bulk path, named by the owner
`structure.adjacency.bulk` ("must rebuild the indexes before it returns, whether it succeeds or fails") and unbound; its
caller-transaction branch has a distinct reader (`status().pending_sync`). Sources: owner bodies
`structure.adjacency.bulk`, `structure.write`; API_REFERENCE `bulk_load_session`; USER_GUIDE lines 279-281; ADMIN_GUIDE
lines 945 and 1032-1048. The session's code was not read. Verus determines none of these.

| Case | History | Reader | Prediction |
|---|---|---|---|
| S1 | no caller transaction: session `add_nodes` (3) and `add_edges` (2), exit | `get_node`; Cypher edge count; `^KG("out")`; `status().pending_sync` | rows readable; edges counted; `^KG` present (functional index); `pending_sync`: unknown (a bulk load leaves `^NKG` stale; the session may sync on exit) |
| S2 | `START TRANSACTION`; the same session; `COMMIT` | same | rows readable; `^KG` present; `pending_sync` True until `sync()` (USER_GUIDE) |
| S2s | then `engine.sync()` | `pending_sync` | False |
| S3 | `START TRANSACTION`; the same session; `ROLLBACK` | same | nothing written; `^KG` absent; `pending_sync` unknown |

### Correction before the second observation

The first probe read `status()` on a separate observer engine. `status.py:81` says `pending_sync` "reflects the
in-process `_nkg_dirty` flag", so the prediction concerns the **loading** engine. Second probe: the same S2/S3 histories,
reading `status().pending_sync` on the loading engine and on an observer engine.

## Outcome ([first](bulk-session-observed-20261116T222856Z.json), [second](bulk-session-observed2-20261116T222926Z.json))

S1 held: readable, edges counted, `^KG` present, nothing pending. S2 held on the loading engine: `pending_sync` True
inside the transaction and after the commit, False after `sync()`; an observer engine reports False throughout (the flag
is in-process, as `status.py` says). S3 held: nothing written, `^KG` absent; the loading engine's flag stays True until
`sync()` (resolved). The first probe's S2 "miss" was the wrong reader, corrected before the second observation. No
finding. The owner `structure.adjacency.bulk` now states the session's `^NKG` and `pending_sync` behavior, including
that another engine does not see the flag. No formal contract (probe-only).
