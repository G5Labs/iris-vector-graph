# Iteration 35: bulk_load_session, and the retest's convergence judgment

Before image: seal 34 `9c668218`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-retest-20261116-iris`.

## W41

Step 5's outside-family workflow: the engine's own bulk path, `bulk_load_session`, with and without a caller's
transaction ([bulk-session-PAIRS.md](bulk-session-PAIRS.md)). Every prediction held once the reader was the loading
engine (the first probe read an observer engine; `pending_sync` is an in-process flag, corrected before the second
observation and kept on record). No finding. `structure.adjacency.bulk` now states the session's `^NKG` and
`pending_sync` behavior, including that another engine does not see the flag. Probe-only (no formal contract).

The full judgment is in the top-level [handoff](../HANDOFF.md#retest-convergence-2026-11-16).
