# Retry replay package for root integration

Input9e6a876f/product3eaa79cf. Only new retry_replay model/results and retry-* evidence
were edited. No product/Git/shared tool/ontology/runtime changes; no native connection.

Final70 verified =14 new (13 behavior proof bodies +1 unfolding lemma) +56 reused
clock/restore/window units rechecked. All9 named controls EXPECTED_FAIL. Actual
Python/store/catch/ported-prefix/paged-reader binding AGREES872 cases/6976 nested
window observations,0 mismatches,4 genuine rejections + untouched success neighbor,
0 socket connections. Root native4 is stamped/audited, not rerun or inflated into
native prefix1 evidence. NOTES enumerates exact source roles and provider limits.

## Canonical recommendation

Retain temporal.write and temporal.edge.clock intent. Under the existing
`temporal.write.partial-failure` metadata, or a child `temporal.write.retry`, add:

> A Counts error does not undo completed items. The Python store retries every
> normalized item with the single writer and reports only accepted fallback calls.
> After a completed zero-timestamp item, this can leave both a current-time event
> and an epoch0 event while reporting one write; a positive timestamp collides at
> its original coordinate, and can report one even when nothing new was inserted.

Preserve the prewrite neighbor and completed-prefix provider boundary: failure
inside one WriteStores, fallback item errors, actual TCP loss and other modes are
not covered. The native4 full-success-then-error fixture is an injected lost reply,
not a real transport failure. Fixed-coordinate repeatability remains conditional on
identical resolved times. Do not relabel intended event-time/count guarantees as
satisfied or infer an owner policy/repair approval.

Stable formal link should target models/retry_replay/retry_replay.rs in owning G5
metadata, with NOTES for source roles. Generic composition items: `counts`, `run`,
`read`, `theorem_fault_replays_entire_batch`; point consequences:
`theorem_zero_lost_reply_retains_two_events`, `theorem_prewrite_zero_has_only_epoch`,
`theorem_positive_lost_reply_collides`, `theorem_preexisting_collision_still_reports_one`,
`theorem_mixed_prefix_replay_reaches_three_points`. Imported roles remain inherited.

Match known bug-tmp-001 and F-0502 rather than count a new product bug. No question,
accepted simplification or repair is claimed. The first69 baseline and initial
mutation-indent assertion remain historical attempts. This package also caught
inherited temporal_clock's edit-only changed-coordinate sensitivity; root withdrew
that credit and refreshed its helper separately before this binding stamped it.

No source-role rows were added by the child; source table in NOTES is ready for
root semantic integration. Earlier model-to-code links must remain scoped to the
represented raw/prefix/catch/window projection. Root should independently review
the fault cutoff, whole-batch versus suffix replay, prefix count disposal and actual
oracle controls before sealing. Full material retry/provider/concurrency unknowns
remain, and this package supplies no convergence evidence by itself.
