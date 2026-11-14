# PROOFS-MECH: the 13 shared mechanisms proved once over a trait (proof debt D-14)

Lane proofs-mech, steer 7. Product pin `3eaa79cf` (unchanged; `check-product-scope.sh` passes). Crate
`experiment/playbook-completion/proofs-mech` (`ivg-proofs-mech`), Verus `0.2026.10.04.426d8b0`, `vstd`
`0.0.0-2026-09-20-0158`, actors at `c03f9fa` (dependency line as in `proofs/Cargo.toml`). Build target
`$RUN_DIR/target/proofs-mech`, logs `$RUN_DIR/proofs-mech/run-*`, recheck `$RUN_DIR/proofs-mech-recheck/run-*`.

**Every result here is about the semantics lane's mechanism models** (`models/semantics/src/*.rs`, the twins of the
cited code), not about the product. The pin's variants that depart from a law stay failed: each is a located control
whose obligation does not verify and whose law is broken by a proved run of the machine.

Playbook §3.3a item 2 asks for "shared mechanisms ... each with its state, operations, ... L1 laws, generic lemmas
proved once over a trait, and generic controls", and "proved once over a trait and instantiated per object, so adding
an object adds no new proof work" (verification-playbook.txt:281-284, 642-644). This crate does that for the 13
mechanisms and 45 laws of `semantics/MECHANISMS.md`.

<!--RESULT-SUMMARY-->
**Result** (run directory `$RUN_DIR/proofs-mech/run-20261114T151136Z`, sources SHA-256 `3e168bab31757fd605c7d744a6a9485a4bda23def41d5b86a0b4d5524fd7ab71`, gate **pass**): baseline **1149 verified, 0 errors** with `--no-cheating` (wall 19.16 s, SMT 45540 ms, rlimit 102951701); trust inventory empty; **all 45 laws of the 13 mechanisms are proved generically** (one theorem per law over the mechanism's trait, plus one bundled theorem per mechanism; M07-L4 as two progress theorems); 78 canonical or reviewed instances discharge every obligation of their trait; **120 of 120 located controls** (72 as-built variants of the pin, 2 documented exceptions, 46 generic mutants) fail exactly at the obligation(s) of the law(s) the explorer reports them violating, with their refutations and proved counterexamples verified in the same build. Registry: `proofs-mech-baseline`, one `proofs-mech-<feature>` per control, recheck `proofs-mech-recheck`.
<!--/RESULT-SUMMARY-->

## Inputs read

| Input | Version read |
|---|---|
| `semantics/MECHANISMS.md`, `semantics/mechanisms.json`, `semantics/axioms.json` | first at commit `b0433157`; final mapping at the semantics lane's commit `50911c4a` (review-4 fixes R4-02, R4-06..R4-08), `mechanisms.json` SHA-256 `1f0c08be9f25b94987f1c06af73ba909becd3f3db900cccf10b104479a75face` |
| `models/semantics/src/*.rs` (the explorer machines) | `b0433157`, re-checked at `50911c4a`: between the two the machines' steps, laws and variants are unchanged; R4-08 changed the harness (`check_keep`, per-law complements), split `adjacency-no-lock-mark` (M-03), `result-cache-04` (M-04) and the catalog index variants (M-12) into their own instances, and added objects to existing variants |
| `models/semantics/RESULTS.json` | SHA-256 `205b95d9f5e9e3efaa07298640879e4e2cf84bccd412a105af05807a2d80b84a`: the `violates` list of every as-built and control check is the oracle each Verus control is compared with |

## Method (one pattern for every mechanism)

For mechanism `M-NN` (`src/mNN_<fam>.rs`):

1. **State and operations**: the explorer machine's state and actions, restated as a Verus spec step function
   `<fam>_step::<O>(s, a) -> Option<S>` (None: not enabled), generic over the instance `O`. `exec::Machine` and
   `exec::run`/`reached` give every machine the same run semantics; `exec::lemma_reached_inv` lifts an inductive
   predicate to every state reached from the initial state (the shape of `actors::hierarchy::invariant_at`).
2. **Trait with the instance parameters**: `<Fam>Policy` declares, as spec functions, what an object chooses: write
   paths (M-01), dedup/retry/post-commit/redaction policy (M-02), the processes' step programs (M-03), write paths,
   fill, clear, gate and rebuild policies (M-04), store lists, inventory, redaction reach, receipt (M-05), carried
   stores and restore policies (M-06), the mark/claim policy, the service order and the resume cursor (M-07), the
   install flags (M-08), key, read and delete policies and the record-match scope (M-09), commit, undo and reply
   policies (M-10), routes (M-11), naming, recording, read check and fail-open (M-12), the reader's checks (M-13).
3. **Laws** as spec predicates: invariant laws on states, action laws on steps (`law_lN`), word for word the
   explorer's invariant or action property.
4. **Obligations**: one spec predicate per law on the instance parameters (`obl_lN::<O>()`), each a design rule
   (stated in the file header). `<Fam>Object: <Fam>Policy` has one proof function per law,
   `proof fn discharge_lN() ensures obl_lN::<Self>();`, which every instance must prove: the obligations are proof
   obligations of the instance, never `assume`d or admitted.
5. **Generic lemmas, proved once**: per law, `lemma_lN_step::<O>` (`requires obl_lN::<O>()`, with an inductive
   invariant where the law is not inductive by itself) and `theorem_lN::<O>` over every reached state or every step
   from one; the bundled `theorem_<fam>::<O: <Fam>Object>` calls the instance's discharges and gives every law.
6. **Instances** (`src/iNN_<fam>.rs`): one type per object variant of `mechanisms.json` (the explorer's instance
   variants). Canonical and reviewed variants implement `<Fam>Object` in the baseline, usually with empty proof
   bodies (the solver evaluates the obligation on the parameters) or one `by (compute)` line (M-03); each has a
   `laws_*` line instantiating the generic theorem: that is the whole proof work of adding an object. Departing
   variants (the pin's as-built variants with their findings, and the semantics lane's generic mutants) have their
   parameters only; their kept obligations are proved (`keep_*`) and their broken ones refuted (`refute_*`, the
   negation of the obligation) in the baseline.
7. **Located controls** (`src/ctl_<fam>.rs`, one Cargo feature each): the departing variant's attempt to implement
   `<Fam>Object`: kept obligations are discharged by the `keep_*` lemmas; each broken obligation is asserted on a line
   marked `// LOCATE <feature> <law>`, which must be exactly where verification fails. Its counterexample
   (`src/cxNN_<fam>.rs`, always compiled) is a run of the generic machine with that variant's parameters, from the
   initial state, to a violation of the law (the explorer's counterexample, restated and proved).
8. **Exactness**: for every control, the set of broken obligations (LOCATE lines) equals the set of laws the
   explorer's check reports violated (`violates` in `models/semantics/RESULTS.json`, copied into the CONTROL line
   and compared by the runner; for the two liveness configurations of M-07, whose explorer checks record an empty
   `violates` list, it is their expectation `Violation(M07-L4)`). So no obligation is stronger than its law for any
   variant in the catalogue: an obligation fails exactly where its law fails, and each failure has a proved
   counterexample.

Gate runner `tools/run_proofs.py` (pattern of `proofs-d9b`/`proofs-d9c`): trust scan (no `assume`, `admit`,
`external_body`/`external`, `axiom`, `uninterp`, `assume_specification` in the crate or in actors); feature hygiene
(every `cfg(feature)` is one impl block in a `ctl_` file with a CONTROL line and LOCATE lines, and Cargo.toml declares
exactly these features); baseline with `--no-cheating`, 0 errors, every function verified, every named refutation and
counterexample among them; each control fails only at its LOCATE lines, its failing functions are exactly its own
`discharge_lN` of the broken laws, every other function verifies and the set of other functions equals the
baseline's, and its refutations and counterexamples verify in the same build. Every Verus run is
`bash experiment/playbook-completion/tools/locks.sh heavy timeout 3600 cargo verus verify ...` after
`cargo clean -p ivg-proofs-mech`, logged into a new `run-<UTC stamp>/` directory; each text log ends with a
`RUNNER SUMMARY` line carrying the verified and error counts and the SHA-256 of the JSON log.
`tools/law_coverage.py` derives the per-law coverage (below and `RESULTS.json` `law_coverage`) from the sources.

## Mechanisms, laws, obligations and generic proofs

| Mechanism | Trait (parameters) | Laws (kind) | Obligations (design rules) | Generic proof |
|---|---|---|---|---|
| M-01 Ledger commit with record | `LedgerPolicy::paths` | L1 history only grows (action), L2 record and change together (invariant), L3 stale head changes nothing (action), L4 strict: no unrecorded change (action) | L1 no path rewrites a record; L2 every path records exactly the change it makes (no two-step record, no record of a collided insert or of a delete that removed nothing); L3 every commit path checks the expected head; L4 every bypass path's guard reads the server's strict flag | L2 by the invariant `law_l2 && mid is None`; L1, L3, L4 per step |
| M-02 Retry and idempotency binding | `RetryPolicy::cfg` (dedup, client retry, post-commit, redaction, server re-run) | L1 at most one effect (invariant), L2 a replay changes nothing (action), L3 a conflicting payload changes nothing (action), L4 redaction removes the binding (invariant) | L1 binding atomic with the effect and post-commit only on the first answer, or the request is never repeated (no client retry, no re-run); L2 no post-commit step on a replay; L3 a conflicting payload is never applied; L4 redaction moves the binding | structural invariant (pending two-step binding, no binding without dedup, redacted key not free) plus a per-policy-shape invariant for L1 |
| M-03 Exclusive section: lock and marker | `ExclPolicy::progs`, `init_live` (the processes' step programs) | L1 mutual exclusion (invariant), L2 guarded effects hold the lock (action), L3 a marked target is not live (invariant), L4 only the owner clears the marker (action), L5 no tombstone of live content (action) | structural rules on the programs, decided by computation (`holds_all`): L1 no broken lock and no lock step inside a section; L2 every guarded effect inside a section; L3 a marker is set only in an X section that checked the target not live, content is made live only in an X section that checked no other marker, by a program that never sets a marker, and (if any program uses markers) the lock discipline; L4 no `ClearAny`; L5 (if any program tombstones) the lock discipline, every tombstone in an X section that checked the target not live, content made live only in X sections | Owicki-Gries style: `inv_held` (a process inside a section holds what its opening step took), `inv_disc` (under the discipline a holder is inside a matching section; mutual exclusion), `inv_nl`/`inv_nm` (the facts an X section checked still hold: target not live, no other marker), `inv_l3` (the marker's owner runs a marker-setting program) |
| M-04 Derived store with staleness | `DerivedPolicy::cfg` (write paths with lock/pre/post/sync/wrong/survives, fill, clear, gate, rebuild) | L1 current or stale (invariant), L2 every write path maintains or moves the token (action), L3 a rebuild is current and correct (action), L4 a gated read answers the source (action) | L1 rebuilds recompute; no clear keeps a current stamp; every path maintains the value correctly in its transaction or moves the token; fills are off, or every fill probes the writer lock after reading the token and every path takes the lock and moves the token before writing; L2 every path is sync or moves the token; L3 rebuilds recompute; L4 the gate checks the stamp and L1's rule holds | invariant `ind_l1`: L1 in every state (not only with no writer open), stamp never ahead of the token, an open bumped writer never sees a current stamp, the writer states' `dirty`/`sync_der` shape, a granted probe with a current token implies an idle or only-begun writer and a computed value equal to the committed source |
| M-05 Store inventory and removal | `RemovalPolicy::cfg` (write paths' stores, inventory, redaction reach, receipt, cross-target stores) | L1 removal reaches every store or the receipt names it (invariant), L2 removal leaves other targets (action), L3 the inventory is complete (invariant) | L1 and L3 (one rule) every store a write path reaches is in the inventory, the redaction's reach or the receipt; L2 no store a write path reaches is shared across targets | invariant: content only from write paths; an erased target holds nothing in the inventory and is never written again; a redacted target was erased and holds nothing in the redaction's reach |
| M-06 Snapshot save and restore | `SnapshotPolicy` (carried stores, head policy, aggregate policy) | L1 round trip on every store (invariant), L2 a restore never lowers the head (action), L3 a merge combines aggregates (action) | L1 the archive carries every store; L2 a replacing restore refuses when the live head is ahead; L3 a merge that carries the aggregates combines them | L1: the archive equals the saved state on carried stores; L3: the archive carries the aggregates exactly when the policy does |
| M-07 Background job and queue | three traits: `QueueEntryPolicy` (mark, cas, single consumer), `QueueOrderPolicy::pick` (service order), `ResumePolicy::resume_at` (cursor) | L1 done means done (invariant), L2 one worker per entry (invariant), L3 bounded overtaking (invariant), **L4 progress** (fair service; a resumed run can always finish) | L1 mark only what was made, from the current text, single consumer; L2 single consumer; L3 and L4 (service) serve the oldest pending entry; L4 (resume) resume at the persisted cursor | entry invariants; order: queue of distinct ids, overtakes + position of id 2 bounded; **progress**: see below |
| M-08 Install, settings and version gate | `InstallPolicy` (four as-built flags) | L1 one schema (invariant), L2 idempotent setup and enable (action), L3 setup touches only its schema (action), L4 an out-of-domain setting is refused (action) | L1 first use refuses an unrecorded namespace; L2 a lost first-enable race returns the genesis; L3 setup drops only qualified names; L4 out-of-domain settings are refused | L1: used schemas are the recorded one |
| M-09 Graph key and tenant scope | `ScopePolicy::cfg` (key, read, delete, record-match scope) | L1 distinct names, distinct keys (invariant), L2 a read answers its own graph (action), L3 a write changes only its graph (action), L4 the target predicates agree (invariant) | L1 every entry validates the name; L2 reads answer from their own graph only; L3 deletes address (graph, id); L4 the record match is scoped by graph | L1: an accepted name carries its entry's key |
| M-10 Unit of work | `UnitPolicy::cfg` (commit, undo, reply) | L1 all or none, L2 inert refusal, L3 the reply matches the outcome (invariants) | L1 one transaction and a rollback; L2 a refusal rolls back its own level only; L3 refusals reply with a code of the family | per-step invariant over the unit's program counter (both initial states: caller transaction open or not) |
| M-11 Capability gate | `CapPolicy::routes` | L1 a read-only caller changes nothing, L2 no valid credential no effect, L3 no server-file or code capability (actions) | L1 every route reads only or checks the read-only role; L2 every route checks the credential; L3 no file route | per step |
| M-12 Catalog binding | `CatalogPolicy::cfg` (naming, recording, read check, fail-open) | L1 every artifact records its binding (invariant), L2 use only the bound artifact (action), L3 distinct bindings distinct artifacts (invariant) | L1 artifacts record their binding; L2 artifacts record their binding, reads check it and a failed check refuses; L3 full naming | slot invariant: a slot's record is its creator's pair |
| M-13 Read epoch | `EpochPolicy::reader` | L1 a finished read shows one state (invariant) | L1 the reader compares the epoch and the marker after reading | reader-phase invariant over the writer's change |

### Progress (M07-L4), with its fairness premises explicit

- **Fair service** (`m07_queue::theorem_l4_order`): for every infinite execution `st`, `lb` of the order machine
  whose first state is reached from the initial state (`order_exec`: every step is a machine step, as
  `actors::fairness::infinite_execution`), in which **the worker is weakly fair** (`worker_fair`: whenever id 2 is
  pending at i, some k >= i is a Serve step) and with the obligation (serve the oldest pending entry), id 2 pending
  at i implies some k >= i at which it is no longer pending. Proved by a rank argument on id 2's position in the style
  of `actors::fairness::eventually_drained`. The fairness premise is a hypothesis of the theorem, never assumed.
- **Resumed run** (`m07_queue::theorem_l4_resume`): with the obligation (resume at the persisted cursor), from every
  reached state some run finishes the redaction (AG EF, `law_l4_resume`), and exactly `3 - cursor` further calls
  finish it: the premise is that the run is resumed that many more times.
- **Counterexamples**: the pin's node-id service order (MinId, F-C0605) and the LIFO mutant: a proved **fair lasso**,
  a 7-step prefix from the initial state to queue `[2]` with 3 overtakes, then the cycle Enqueue(0), Serve forever;
  the proof shows `order_exec` and `worker_fair` hold along it and id 2 is pending at every index (and the prefix
  breaks L3). The pin's restarting bounded redaction (F-C1303) and its mutant: an invariant of every run from the
  initial state (record 1 is never tombstoned) proves that no run finishes (`!law_l4_resume` at the initial state).

<!--LAW-TABLE-->
## Which instances discharge which laws

Every law is proved once over its mechanism's trait (column 2). Column 3: the canonical/reviewed instances that implement the mechanism's Object trait in the baseline (they discharge every obligation of their trait, so the generic theorem applies with no proof of their own); column 4: departing variants that still keep this law (their `keep_*` lemma discharges its obligation, so the per-law theorem applies to them); column 5: the variants that break it (each a located control with a refutation and a proved counterexample).

| Law | Generic theorem(s) | Discharged by (instances) | Kept by departing variants | Broken by (control) |
|---|---|---|---|---|
| M01-L1 action | `theorem_action_laws`, `theorem_ledger` | CommitCore, NodeDeleteNamedOnlyReviewed, TemporalInsertCollisionReviewed, StrictCachedGuardReviewed, BypassUncheckedReviewed | NodeDeleteNamedOnlyAsBuilt, TemporalInsertCollisionAsBuilt, StrictCachedGuardAsBuilt, BypassUncheckedAsBuilt, CtlTwoStepRecord, CtlIgnoreHead, CtlUnguardedBypass | CtlOverwriteRecord (mutant) |
| M01-L2 invariant | `theorem_l2`, `theorem_ledger` | CommitCore, NodeDeleteNamedOnlyReviewed, TemporalInsertCollisionReviewed, StrictCachedGuardReviewed, BypassUncheckedReviewed | StrictCachedGuardAsBuilt, BypassUncheckedAsBuilt, CtlOverwriteRecord, CtlIgnoreHead, CtlUnguardedBypass | NodeDeleteNamedOnlyAsBuilt (F-1105), TemporalInsertCollisionAsBuilt (F-0511), CtlTwoStepRecord (mutant) |
| M01-L3 action | `theorem_action_laws`, `theorem_ledger` | CommitCore, NodeDeleteNamedOnlyReviewed, TemporalInsertCollisionReviewed, StrictCachedGuardReviewed, BypassUncheckedReviewed | NodeDeleteNamedOnlyAsBuilt, TemporalInsertCollisionAsBuilt, StrictCachedGuardAsBuilt, BypassUncheckedAsBuilt, CtlTwoStepRecord, CtlOverwriteRecord, CtlUnguardedBypass | CtlIgnoreHead (mutant) |
| M01-L4 action | `theorem_action_laws`, `theorem_ledger` | CommitCore, NodeDeleteNamedOnlyReviewed, TemporalInsertCollisionReviewed, StrictCachedGuardReviewed, BypassUncheckedReviewed | NodeDeleteNamedOnlyAsBuilt, TemporalInsertCollisionAsBuilt, CtlTwoStepRecord, CtlOverwriteRecord, CtlIgnoreHead | StrictCachedGuardAsBuilt (F-0302,F-0801), BypassUncheckedAsBuilt (F-0301,F-0504,F-1108,F-0503), CtlUnguardedBypass (mutant) |
| M02-L1 invariant | `theorem_l1`, `theorem_retry` | IdempotentSetup, LedgerKeyReviewed, ZeroRecordRevisionReviewed, ClientResendReviewed, ServerRerunReviewed | ZeroRecordRevisionAsBuilt, CtlRedactionKeepsBinding | LedgerKeyAsBuilt (F-1101,F-1306), ClientResendAsBuilt (F-C1703), ServerRerunAsBuilt (F-C1604), CtlBindAfterEffect (mutant), CtlPostOnReplay (mutant), CtlApplyConflict (mutant) |
| M02-L2 action | `theorem_l2`, `theorem_retry` | IdempotentSetup, LedgerKeyReviewed, ZeroRecordRevisionReviewed, ClientResendReviewed, ServerRerunReviewed | ZeroRecordRevisionAsBuilt, ClientResendAsBuilt, ServerRerunAsBuilt, CtlBindAfterEffect, CtlApplyConflict, CtlRedactionKeepsBinding | LedgerKeyAsBuilt (F-1101,F-1306), CtlPostOnReplay (mutant) |
| M02-L3 action | `theorem_l3`, `theorem_retry` | IdempotentSetup, LedgerKeyReviewed, ZeroRecordRevisionReviewed, ClientResendReviewed, ServerRerunReviewed | LedgerKeyAsBuilt, ZeroRecordRevisionAsBuilt, ClientResendAsBuilt, ServerRerunAsBuilt, CtlBindAfterEffect, CtlPostOnReplay, CtlRedactionKeepsBinding | CtlApplyConflict (mutant) |
| M02-L4 invariant | `theorem_l4`, `theorem_retry` | IdempotentSetup, LedgerKeyReviewed, ZeroRecordRevisionReviewed, ClientResendReviewed, ServerRerunReviewed | LedgerKeyAsBuilt, ClientResendAsBuilt, ServerRerunAsBuilt, CtlBindAfterEffect, CtlPostOnReplay, CtlApplyConflict | ZeroRecordRevisionAsBuilt (F-CS01), CtlRedactionKeepsBinding (mutant) |
| M03-L1 invariant | `theorem_l1`, `theorem_excl` | HeadLockCommit, AdjacencyNoLockMark, RedactionMarkerReviewed, EraserNoHeadLockReviewed, AdjacencyWriterLockReviewed, Bm25WriteLockReviewed, PlanBuildLockReviewed, ModeSwitchReviewed | RedactionMarkerAsBuilt, EraserNoHeadLockAsBuilt, AdjacencyWriterLockAsBuilt, Bm25WriteLockAsBuilt, PlanBuildLockAsBuilt, ModeSwitchAsBuilt, CtlWriterWithoutLock, CtlCheckBeforeLock, CtlClearAny, CtlTombWithoutCheck | CtlLockAdmitsTwo (mutant) |
| M03-L2 action | `theorem_l2`, `theorem_excl` | HeadLockCommit, AdjacencyNoLockMark, RedactionMarkerReviewed, EraserNoHeadLockReviewed, AdjacencyWriterLockReviewed, Bm25WriteLockReviewed, PlanBuildLockReviewed, ModeSwitchReviewed | RedactionMarkerAsBuilt, CtlLockAdmitsTwo, CtlCheckBeforeLock, CtlClearAny, CtlTombWithoutCheck | EraserNoHeadLockAsBuilt (F-1201,F-1114,F-C1201), AdjacencyWriterLockAsBuilt (F-0407), Bm25WriteLockAsBuilt (F-0701), PlanBuildLockAsBuilt (F-0905), ModeSwitchAsBuilt (F-0207), CtlWriterWithoutLock (mutant) |
| M03-L3 invariant | `theorem_l3`, `theorem_excl` | HeadLockCommit, AdjacencyNoLockMark, RedactionMarkerReviewed, EraserNoHeadLockReviewed, AdjacencyWriterLockReviewed, Bm25WriteLockReviewed, PlanBuildLockReviewed, ModeSwitchReviewed | EraserNoHeadLockAsBuilt, AdjacencyWriterLockAsBuilt, Bm25WriteLockAsBuilt, PlanBuildLockAsBuilt, ModeSwitchAsBuilt, CtlLockAdmitsTwo, CtlClearAny | RedactionMarkerAsBuilt (F-1302,F-1303), CtlWriterWithoutLock (mutant), CtlCheckBeforeLock (mutant), CtlTombWithoutCheck (mutant) |
| M03-L4 action | `theorem_l4`, `theorem_excl` | HeadLockCommit, AdjacencyNoLockMark, RedactionMarkerReviewed, EraserNoHeadLockReviewed, AdjacencyWriterLockReviewed, Bm25WriteLockReviewed, PlanBuildLockReviewed, ModeSwitchReviewed | EraserNoHeadLockAsBuilt, AdjacencyWriterLockAsBuilt, Bm25WriteLockAsBuilt, PlanBuildLockAsBuilt, ModeSwitchAsBuilt, CtlLockAdmitsTwo, CtlWriterWithoutLock, CtlCheckBeforeLock, CtlTombWithoutCheck | RedactionMarkerAsBuilt (F-1302,F-1303), CtlClearAny (mutant) |
| M03-L5 action | `theorem_l5`, `theorem_excl` | HeadLockCommit, AdjacencyNoLockMark, RedactionMarkerReviewed, EraserNoHeadLockReviewed, AdjacencyWriterLockReviewed, Bm25WriteLockReviewed, PlanBuildLockReviewed, ModeSwitchReviewed | EraserNoHeadLockAsBuilt, AdjacencyWriterLockAsBuilt, Bm25WriteLockAsBuilt, PlanBuildLockAsBuilt, ModeSwitchAsBuilt, CtlLockAdmitsTwo, CtlClearAny | RedactionMarkerAsBuilt (F-1302,F-1303), CtlWriterWithoutLock (mutant), CtlCheckBeforeLock (mutant), CtlTombWithoutCheck (mutant) |
| M04-L1 invariant | `theorem_l1`, `theorem_derived` | AdjacencyFunctional, DegreeCacheReviewed, ResultCache04Reviewed, AlgoCacheEdgelessReviewed, InternedSnapshotReviewed, Bm25TextChangeReviewed, StatementMapDirectDeleteReviewed, BucketAggregateUpdateReviewed, EngineModeCacheReviewed, TtlCacheReviewed, NativeGateLabelIndexReviewed, IvfEraseReviewed | CtlUncheckedGate | DegreeCacheF0402 (F-0402), DegreeCacheFC0401 (F-C0401), DegreeCacheF0406 (F-0406), ResultCache04F0402 (F-0402), AlgoCacheEdgelessF1004 (F-1004), InternedSnapshotF1005 (F-1005), InternedSnapshotFC0801 (F-C0801), Bm25TextChangeF0703 (F-0703), StatementMapDirectDeleteF0303 (F-0303), BucketAggregateUpdateF0501 (F-0501), EngineModeCacheF0208 (F-0208), TtlCacheF0302 (F-0302), TtlCacheEXC05 (exception), NativeGateLabelIndexF0906 (F-0906), IvfEraseF0606 (F-0606), CtlUnmaintainedPath (mutant), CtlTokenAfterCompute (mutant), CtlRebuildStampOnly (mutant), CtlProbeLate (mutant) |
| M04-L2 action | `theorem_l2`, `theorem_derived` | AdjacencyFunctional, DegreeCacheReviewed, ResultCache04Reviewed, AlgoCacheEdgelessReviewed, InternedSnapshotReviewed, Bm25TextChangeReviewed, StatementMapDirectDeleteReviewed, BucketAggregateUpdateReviewed, EngineModeCacheReviewed, TtlCacheReviewed, NativeGateLabelIndexReviewed, IvfEraseReviewed | DegreeCacheF0402, DegreeCacheFC0401, DegreeCacheF0406, ResultCache04F0402, InternedSnapshotFC0801, BucketAggregateUpdateF0501, CtlTokenAfterCompute, CtlRebuildStampOnly, CtlUncheckedGate, CtlProbeLate | AlgoCacheEdgelessF1004 (F-1004), InternedSnapshotF1005 (F-1005), Bm25TextChangeF0703 (F-0703), StatementMapDirectDeleteF0303 (F-0303), EngineModeCacheF0208 (F-0208), TtlCacheF0302 (F-0302), TtlCacheEXC05 (exception), NativeGateLabelIndexF0906 (F-0906), IvfEraseF0606 (F-0606), CtlUnmaintainedPath (mutant) |
| M04-L3 invariant | `theorem_l3`, `theorem_derived` | AdjacencyFunctional, DegreeCacheReviewed, ResultCache04Reviewed, AlgoCacheEdgelessReviewed, InternedSnapshotReviewed, Bm25TextChangeReviewed, StatementMapDirectDeleteReviewed, BucketAggregateUpdateReviewed, EngineModeCacheReviewed, TtlCacheReviewed, NativeGateLabelIndexReviewed, IvfEraseReviewed | DegreeCacheF0402, DegreeCacheFC0401, DegreeCacheF0406, ResultCache04F0402, AlgoCacheEdgelessF1004, InternedSnapshotF1005, InternedSnapshotFC0801, Bm25TextChangeF0703, StatementMapDirectDeleteF0303, BucketAggregateUpdateF0501, EngineModeCacheF0208, TtlCacheF0302, TtlCacheEXC05, NativeGateLabelIndexF0906, IvfEraseF0606, CtlUnmaintainedPath, CtlTokenAfterCompute, CtlUncheckedGate, CtlProbeLate | CtlRebuildStampOnly (mutant) |
| M04-L4 action | `theorem_l4`, `theorem_derived` | AdjacencyFunctional, DegreeCacheReviewed, ResultCache04Reviewed, AlgoCacheEdgelessReviewed, InternedSnapshotReviewed, Bm25TextChangeReviewed, StatementMapDirectDeleteReviewed, BucketAggregateUpdateReviewed, EngineModeCacheReviewed, TtlCacheReviewed, NativeGateLabelIndexReviewed, IvfEraseReviewed | - | DegreeCacheF0402 (F-0402), DegreeCacheFC0401 (F-C0401), DegreeCacheF0406 (F-0406), ResultCache04F0402 (F-0402), AlgoCacheEdgelessF1004 (F-1004), InternedSnapshotF1005 (F-1005), InternedSnapshotFC0801 (F-C0801), Bm25TextChangeF0703 (F-0703), StatementMapDirectDeleteF0303 (F-0303), BucketAggregateUpdateF0501 (F-0501), EngineModeCacheF0208 (F-0208), TtlCacheF0302 (F-0302), TtlCacheEXC05 (exception), NativeGateLabelIndexF0906 (F-0906), IvfEraseF0606 (F-0606), CtlUnmaintainedPath (mutant), CtlTokenAfterCompute (mutant), CtlRebuildStampOnly (mutant), CtlUncheckedGate (mutant), CtlProbeLate (mutant) |
| M05-L1 invariant | `theorem_l1`, `theorem_removal` | RowsAdjacencyTemporal, Bm25Reviewed, VectorIndexesReviewed, QuarantineReviewed, SnapshotArchivesReviewed, ReifierDefaultGraphReviewed, TemporalOnlyPrefixReviewed, HistoryTextReviewed, DefaultRoutedVectorsReviewed, TemporalPurgeAllGraphsReviewed | TemporalPurgeAllGraphsAsBuilt, CtlCrossTarget | Bm25AsBuilt (F-0702), VectorIndexesAsBuilt (F-0606), QuarantineAsBuilt (F-C1305), SnapshotArchivesAsBuilt (F-C1304), ReifierDefaultGraphAsBuilt (F-1502), TemporalOnlyPrefixAsBuilt (F-C1203,F-C1308), HistoryTextAsBuilt (F-C1306,F-CS01,F-C1309), DefaultRoutedVectorsAsBuilt (F-0618), CtlStoreDropped (mutant) |
| M05-L2 action | `theorem_l2`, `theorem_removal` | RowsAdjacencyTemporal, Bm25Reviewed, VectorIndexesReviewed, QuarantineReviewed, SnapshotArchivesReviewed, ReifierDefaultGraphReviewed, TemporalOnlyPrefixReviewed, HistoryTextReviewed, DefaultRoutedVectorsReviewed, TemporalPurgeAllGraphsReviewed | Bm25AsBuilt, VectorIndexesAsBuilt, QuarantineAsBuilt, SnapshotArchivesAsBuilt, ReifierDefaultGraphAsBuilt, TemporalOnlyPrefixAsBuilt, HistoryTextAsBuilt, DefaultRoutedVectorsAsBuilt, CtlStoreDropped | TemporalPurgeAllGraphsAsBuilt (F-0507), CtlCrossTarget (mutant) |
| M05-L3 invariant | `theorem_l3`, `theorem_removal` | RowsAdjacencyTemporal, Bm25Reviewed, VectorIndexesReviewed, QuarantineReviewed, SnapshotArchivesReviewed, ReifierDefaultGraphReviewed, TemporalOnlyPrefixReviewed, HistoryTextReviewed, DefaultRoutedVectorsReviewed, TemporalPurgeAllGraphsReviewed | TemporalPurgeAllGraphsAsBuilt, CtlCrossTarget | Bm25AsBuilt (F-0702), VectorIndexesAsBuilt (F-0606), QuarantineAsBuilt (F-C1305), SnapshotArchivesAsBuilt (F-C1304), ReifierDefaultGraphAsBuilt (F-1502), TemporalOnlyPrefixAsBuilt (F-C1203,F-C1308), HistoryTextAsBuilt (F-C1306,F-CS01,F-C1309), DefaultRoutedVectorsAsBuilt (F-0618), CtlStoreDropped (mutant) |
| M06-L1 invariant | `theorem_l1`, `theorem_snapshot` | EdgeVectorsMissingReviewed, ReplacingRestoreReviewed, MergeAggregatesReviewed | ReplacingRestoreAsBuilt, MergeAggregatesAsBuilt, CtlHeadLaidOver, CtlAggregatesOverwritten | EdgeVectorsMissingAsBuilt (F-C1804,F-1803,F-1804), CtlStoreLeftOut (mutant) |
| M06-L2 action | `theorem_l2`, `theorem_snapshot` | EdgeVectorsMissingReviewed, ReplacingRestoreReviewed, MergeAggregatesReviewed | EdgeVectorsMissingAsBuilt, MergeAggregatesAsBuilt, CtlStoreLeftOut, CtlAggregatesOverwritten | ReplacingRestoreAsBuilt (F-1801), CtlHeadLaidOver (mutant) |
| M06-L3 action | `theorem_l3`, `theorem_snapshot` | EdgeVectorsMissingReviewed, ReplacingRestoreReviewed, MergeAggregatesReviewed | EdgeVectorsMissingAsBuilt, ReplacingRestoreAsBuilt, CtlStoreLeftOut, CtlHeadLaidOver | MergeAggregatesAsBuilt (F-1805), CtlAggregatesOverwritten (mutant) |
| M07-L1 invariant | `theorem_l1`, `theorem_entry` | EmbedQueueEntryReviewed | - | EmbedQueueF0604 (F-0604), EmbedQueueFC0601 (F-C0601), EmbedQueueHD0604 (F-C0670), CtlTwoConsumers (mutant), CtlMarkAlways (mutant) |
| M07-L2 invariant | `theorem_l2`, `theorem_entry` | EmbedQueueEntryReviewed | EmbedQueueF0604, EmbedQueueFC0601, CtlMarkAlways | EmbedQueueHD0604 (F-C0670), CtlTwoConsumers (mutant) |
| M07-L3 invariant | `theorem_l3`, `theorem_order` | EmbedQueueOrderReviewed | - | EmbedQueueOrderAsBuilt (F-C0605), CtlLifo (mutant) |
| M07-L4 progress | `theorem_l4_order`, `theorem_l4_resume`, `theorem_order`, `theorem_resume` | EmbedQueueOrderReviewed, BoundedRedactionResumeReviewed | - | EmbedQueueOrderAsBuilt (F-C0605), CtlLifo (mutant), BoundedRedactionResumeAsBuilt (F-C1303), CtlRestartScan (mutant) |
| M08-L1 invariant | `theorem_l1`, `theorem_install` | Canonical, FirstUseNoRecordReviewed, UnqualifiedDropReviewed, UncheckedSettingReviewed, ConcurrentFirstEnableReviewed | UnqualifiedDropAsBuilt, UncheckedSettingAsBuilt, ConcurrentFirstEnableAsBuilt, CtlUnqualifiedDrop, CtlSettingUnchecked, CtlEnableRaceErrors | FirstUseNoRecordAsBuilt (F-0103), CtlFirstUseAcceptsAny (mutant) |
| M08-L2 action | `theorem_action_laws`, `theorem_install` | Canonical, FirstUseNoRecordReviewed, UnqualifiedDropReviewed, UncheckedSettingReviewed, ConcurrentFirstEnableReviewed | FirstUseNoRecordAsBuilt, UnqualifiedDropAsBuilt, UncheckedSettingAsBuilt, CtlFirstUseAcceptsAny, CtlUnqualifiedDrop, CtlSettingUnchecked | ConcurrentFirstEnableAsBuilt (F-1104), CtlEnableRaceErrors (mutant) |
| M08-L3 action | `theorem_action_laws`, `theorem_install` | Canonical, FirstUseNoRecordReviewed, UnqualifiedDropReviewed, UncheckedSettingReviewed, ConcurrentFirstEnableReviewed | FirstUseNoRecordAsBuilt, UncheckedSettingAsBuilt, ConcurrentFirstEnableAsBuilt, CtlFirstUseAcceptsAny, CtlSettingUnchecked, CtlEnableRaceErrors | UnqualifiedDropAsBuilt (F-0107), CtlUnqualifiedDrop (mutant) |
| M08-L4 action | `theorem_action_laws`, `theorem_install` | Canonical, FirstUseNoRecordReviewed, UnqualifiedDropReviewed, UncheckedSettingReviewed, ConcurrentFirstEnableReviewed | FirstUseNoRecordAsBuilt, UnqualifiedDropAsBuilt, ConcurrentFirstEnableAsBuilt, CtlFirstUseAcceptsAny, CtlUnqualifiedDrop, CtlEnableRaceErrors | UncheckedSettingAsBuilt (F-0903,F-1506), CtlSettingUnchecked (mutant) |
| M09-L1 invariant | `theorem_l1`, `theorem_scope` | ScopeCanonical, NameCheckMissingReviewed, AllGraphsWalkReviewed, UnscopedReadReviewed, InternedNoGraphDimensionReviewed, DeleteEveryGraphReviewed, ThreePredicatesReviewed | AllGraphsWalkAsBuilt, UnscopedReadAsBuilt, InternedNoGraphDimensionAsBuilt, DeleteEveryGraphAsBuilt, ThreePredicatesAsBuilt, CtlJoinAcrossGraphs, CtlDeleteEveryGraph, CtlGraphBlindMatch | NameCheckMissingAsBuilt (F-0202,F-0203), CtlKeyIgnoresName (mutant) |
| M09-L2 invariant | `theorem_l2`, `theorem_scope` | ScopeCanonical, NameCheckMissingReviewed, AllGraphsWalkReviewed, UnscopedReadReviewed, InternedNoGraphDimensionReviewed, DeleteEveryGraphReviewed, ThreePredicatesReviewed | NameCheckMissingAsBuilt, DeleteEveryGraphAsBuilt, ThreePredicatesAsBuilt, CtlKeyIgnoresName, CtlDeleteEveryGraph, CtlGraphBlindMatch | AllGraphsWalkAsBuilt (F-0818,F-0819,F-0820), UnscopedReadAsBuilt (F-1002,F-1006,F-1008,F-1013,F-1001,F-1603,F-1604,F-1701,F-0609,F-0711,F-0605,F-0616,F-1507), InternedNoGraphDimensionAsBuilt (exception), CtlJoinAcrossGraphs (mutant) |
| M09-L3 action | `theorem_l3`, `theorem_scope` | ScopeCanonical, NameCheckMissingReviewed, AllGraphsWalkReviewed, UnscopedReadReviewed, InternedNoGraphDimensionReviewed, DeleteEveryGraphReviewed, ThreePredicatesReviewed | NameCheckMissingAsBuilt, AllGraphsWalkAsBuilt, UnscopedReadAsBuilt, InternedNoGraphDimensionAsBuilt, ThreePredicatesAsBuilt, CtlKeyIgnoresName, CtlJoinAcrossGraphs, CtlGraphBlindMatch | DeleteEveryGraphAsBuilt (F-1503), CtlDeleteEveryGraph (mutant) |
| M09-L4 invariant | `theorem_l4`, `theorem_scope` | ScopeCanonical, NameCheckMissingReviewed, AllGraphsWalkReviewed, UnscopedReadReviewed, InternedNoGraphDimensionReviewed, DeleteEveryGraphReviewed, ThreePredicatesReviewed | NameCheckMissingAsBuilt, AllGraphsWalkAsBuilt, UnscopedReadAsBuilt, InternedNoGraphDimensionAsBuilt, DeleteEveryGraphAsBuilt, CtlKeyIgnoresName, CtlJoinAcrossGraphs, CtlDeleteEveryGraph | ThreePredicatesAsBuilt (F-1304,F-1305,F-1105,F-1401), CtlGraphBlindMatch (mutant) |
| M10-L1 invariant | `theorem_l1`, `theorem_unit` | Canonical, PerChunkCommitReviewed, RollbackAllLevelsReviewed, PerStatementCommitReviewed, NoTransactionReviewed, WrongReplyReviewed, HiddenFailureReviewed | RollbackAllLevelsAsBuilt, WrongReplyAsBuilt, HiddenFailureAsBuilt, CtlRollbackAllLevels, CtlOkOnFailure | PerChunkCommitAsBuilt (F-0305), PerStatementCommitAsBuilt (F-1601,F-1610,F-1609,F-C1502), NoTransactionAsBuilt (F-1511,F-C1501,F-0615,F-C0501), CtlPerStatement (mutant) |
| M10-L2 invariant | `theorem_l2`, `theorem_unit` | Canonical, PerChunkCommitReviewed, RollbackAllLevelsReviewed, PerStatementCommitReviewed, NoTransactionReviewed, WrongReplyReviewed, HiddenFailureReviewed | PerChunkCommitAsBuilt, PerStatementCommitAsBuilt, NoTransactionAsBuilt, WrongReplyAsBuilt, HiddenFailureAsBuilt, CtlPerStatement, CtlOkOnFailure | RollbackAllLevelsAsBuilt (F-C0702,F-0704,F-0409), CtlRollbackAllLevels (mutant) |
| M10-L3 invariant | `theorem_l3`, `theorem_unit` | Canonical, PerChunkCommitReviewed, RollbackAllLevelsReviewed, PerStatementCommitReviewed, NoTransactionReviewed, WrongReplyReviewed, HiddenFailureReviewed | PerChunkCommitAsBuilt, RollbackAllLevelsAsBuilt, PerStatementCommitAsBuilt, NoTransactionAsBuilt, CtlPerStatement, CtlRollbackAllLevels | WrongReplyAsBuilt (F-0807,F-0804,F-0817), HiddenFailureAsBuilt (F-0306,F-0307,F-0709,F-1508,F-1615), CtlOkOnFailure (mutant) |
| M11-L1 action | `theorem_action_laws`, `theorem_cap` | HttpServer, DemoServerReviewed, AqlReviewed, AqlCodeTextReviewed, SnapshotFileHelpersReviewed, PrivilegeInEngineOnlyReviewed | DemoServerAsBuilt, AqlCodeTextAsBuilt, PrivilegeInEngineOnlyAsBuilt, CtlRouteWithoutKeyCheck, CtlFileRoute | AqlAsBuilt (F-0814), SnapshotFileHelpersAsBuilt (F-C1803,F-1806), CtlWriteWithoutReadOnlyCheck (mutant) |
| M11-L2 action | `theorem_action_laws`, `theorem_cap` | HttpServer, DemoServerReviewed, AqlReviewed, AqlCodeTextReviewed, SnapshotFileHelpersReviewed, PrivilegeInEngineOnlyReviewed | AqlAsBuilt, AqlCodeTextAsBuilt, CtlWriteWithoutReadOnlyCheck, CtlFileRoute | DemoServerAsBuilt (F-1614), SnapshotFileHelpersAsBuilt (F-C1803,F-1806), PrivilegeInEngineOnlyAsBuilt (F-0908), CtlRouteWithoutKeyCheck (mutant) |
| M11-L3 action | `theorem_action_laws`, `theorem_cap` | HttpServer, DemoServerReviewed, AqlReviewed, AqlCodeTextReviewed, SnapshotFileHelpersReviewed, PrivilegeInEngineOnlyReviewed | DemoServerAsBuilt, AqlAsBuilt, PrivilegeInEngineOnlyAsBuilt, CtlWriteWithoutReadOnlyCheck, CtlRouteWithoutKeyCheck | AqlCodeTextAsBuilt (F-0815,F-0814), SnapshotFileHelpersAsBuilt (F-C1803,F-1806), CtlFileRoute (mutant) |
| M12-L1 invariant | `theorem_l1`, `theorem_catalog` | CatalogCanonical, Bm25IndexGraphUncheckedReviewed, IvfIndexGraphUncheckedReviewed, IdentityFailOpenReviewed, ShortHashNameReviewed | Bm25IndexGraphUncheckedAsBuilt, IvfIndexGraphUncheckedAsBuilt, IdentityFailOpenAsBuilt, ShortHashNameAsBuilt, CtlUncheckedRead, CtlShortHash, CtlFailOpen | Bm25IndexNoRecordAsBuilt (F-0705), CtlNoRecord (mutant) |
| M12-L2 action | `theorem_l2`, `theorem_catalog` | CatalogCanonical, Bm25IndexGraphUncheckedReviewed, IvfIndexGraphUncheckedReviewed, IdentityFailOpenReviewed, ShortHashNameReviewed | ShortHashNameAsBuilt, CtlShortHash | Bm25IndexGraphUncheckedAsBuilt (F-0707), Bm25IndexNoRecordAsBuilt (F-0705), IvfIndexGraphUncheckedAsBuilt (F-0609), IdentityFailOpenAsBuilt (F-0601,F-0602,F-0603,F-0613), CtlUncheckedRead (mutant), CtlNoRecord (mutant), CtlFailOpen (mutant) |
| M12-L3 invariant | `theorem_l3`, `theorem_catalog` | CatalogCanonical, Bm25IndexGraphUncheckedReviewed, IvfIndexGraphUncheckedReviewed, IdentityFailOpenReviewed, ShortHashNameReviewed | Bm25IndexGraphUncheckedAsBuilt, Bm25IndexNoRecordAsBuilt, IvfIndexGraphUncheckedAsBuilt, IdentityFailOpenAsBuilt, CtlUncheckedRead, CtlNoRecord, CtlFailOpen | ShortHashNameAsBuilt (F-0901,F-C0901), CtlShortHash (mutant) |
| M13-L1 invariant | `theorem_l1`, `theorem_epoch` | CheckAtStartReviewed, NoCheckReviewed | - | CheckAtStartAsBuilt (F-1402), NoCheckAsBuilt (F-C1801), CtlNoEndCheck (mutant) |
<!--/LAW-TABLE-->

<!--CONTROL-TABLE-->
## Located controls

One Cargo feature each (`proofs-mech-<feature>` with `_` as `-`); result `expected-violation` when the control fails exactly at its LOCATE line(s) and nowhere else. Full records: `RESULTS.json` `controls`.

| Feature | Variant (kind) | Explorer check(s) | Findings | Laws broken | Located at | Result |
|---|---|---|---|---|---|---|
| `ledger_bypass_unchecked_as_built` | BypassUncheckedAsBuilt (as-built) | ledger-bypass-unchecked-as-built | F-0301, F-0504, F-1108, F-0503 | M01-L4 | src/ctl_ledger.rs:54 | rejected at its obligation |
| `ledger_control_c1_two_step_record` | CtlTwoStepRecord (mutant) | ledger-control-C1-two-step-record | - | M01-L2 | src/ctl_ledger.rs:63 | rejected at its obligation |
| `ledger_control_c2_overwrite_record` | CtlOverwriteRecord (mutant) | ledger-control-C2-overwrite-record | - | M01-L1 | src/ctl_ledger.rs:73 | rejected at its obligation |
| `ledger_control_c3_ignore_head` | CtlIgnoreHead (mutant) | ledger-control-C3-ignore-head | - | M01-L3 | src/ctl_ledger.rs:86 | rejected at its obligation |
| `ledger_control_c4_unguarded_bypass` | CtlUnguardedBypass (mutant) | ledger-control-C4-unguarded-bypass | - | M01-L4 | src/ctl_ledger.rs:98 | rejected at its obligation |
| `ledger_node_delete_named_only_as_built` | NodeDeleteNamedOnlyAsBuilt (as-built) | ledger-node-delete-named-only-as-built | F-1105 | M01-L2 | src/ctl_ledger.rs:19 | rejected at its obligation |
| `ledger_strict_cached_guard_as_built` | StrictCachedGuardAsBuilt (as-built) | ledger-strict-cached-guard-as-built | F-0302, F-0801 | M01-L4 | src/ctl_ledger.rs:43 | rejected at its obligation |
| `ledger_temporal_insert_collision_as_built` | TemporalInsertCollisionAsBuilt (as-built) | ledger-temporal-insert-collision-as-built | F-0511 | M01-L2 | src/ctl_ledger.rs:30 | rejected at its obligation |
| `retry_client_resend_as_built` | ClientResendAsBuilt (as-built) | retry-client-resend-as-built | F-C1703 | M02-L1 | src/ctl_retry.rs:40 | rejected at its obligation |
| `retry_control_c1_bind_after_effect` | CtlBindAfterEffect (mutant) | retry-control-C1-bind-after-effect | - | M02-L1 | src/ctl_retry.rs:62 | rejected at its obligation |
| `retry_control_c2_post_on_replay` | CtlPostOnReplay (mutant) | retry-control-C2-post-on-replay | - | M02-L1, M02-L2 | src/ctl_retry.rs:73, src/ctl_retry.rs:76 | rejected at its obligation |
| `retry_control_c3_apply_conflict` | CtlApplyConflict (mutant) | retry-control-C3-apply-conflict | - | M02-L1, M02-L3 | src/ctl_retry.rs:86, src/ctl_retry.rs:90 | rejected at its obligation |
| `retry_control_c4_redaction_keeps_binding` | CtlRedactionKeepsBinding (mutant) | retry-control-C4-redaction-keeps-binding | - | M02-L4 | src/ctl_retry.rs:102 | rejected at its obligation |
| `retry_ledger_key_as_built` | LedgerKeyAsBuilt (as-built) | retry-ledger-key-as-built | F-1101, F-1306 | M02-L1, M02-L2 | src/ctl_retry.rs:16, src/ctl_retry.rs:19 | rejected at its obligation |
| `retry_server_rerun_as_built` | ServerRerunAsBuilt (as-built) | retry-server-rerun-as-built | F-C1604 | M02-L1 | src/ctl_retry.rs:51 | rejected at its obligation |
| `retry_zero_record_revision_as_built` | ZeroRecordRevisionAsBuilt (as-built) | retry-zero-record-revision-as-built | F-CS01 | M02-L4 | src/ctl_retry.rs:32 | rejected at its obligation |
| `excl_adjacency_writer_lock_as_built` | AdjacencyWriterLockAsBuilt (as-built) | excl-adjacency-writer-lock-as-built | F-0407 | M03-L2 | src/ctl_excl.rs:44 | rejected at its obligation |
| `excl_bm25_write_lock_as_built` | Bm25WriteLockAsBuilt (as-built) | excl-bm25-write-lock-as-built | F-0701 | M03-L2 | src/ctl_excl.rs:56 | rejected at its obligation |
| `excl_control_c1_lock_admits_two` | CtlLockAdmitsTwo (mutant) | excl-control-C1-lock-admits-two | - | M03-L1 | src/ctl_excl.rs:91 | rejected at its obligation |
| `excl_control_c2_writer_without_lock` | CtlWriterWithoutLock (mutant) | excl-control-C2-writer-without-lock | - | M03-L2, M03-L3, M03-L5 | src/ctl_excl.rs:104, src/ctl_excl.rs:107, src/ctl_excl.rs:111 | rejected at its obligation |
| `excl_control_c3_check_before_lock` | CtlCheckBeforeLock (mutant) | excl-control-C3-check-before-lock | - | M03-L3, M03-L5 | src/ctl_excl.rs:121, src/ctl_excl.rs:125 | rejected at its obligation |
| `excl_control_c4_clear_any` | CtlClearAny (mutant) | excl-control-C4-clear-any | - | M03-L4 | src/ctl_excl.rs:136 | rejected at its obligation |
| `excl_control_c5_tomb_without_check` | CtlTombWithoutCheck (mutant) | excl-control-C5-tomb-without-check | - | M03-L3, M03-L5 | src/ctl_excl.rs:147, src/ctl_excl.rs:151 | rejected at its obligation |
| `excl_eraser_no_head_lock_as_built` | EraserNoHeadLockAsBuilt (as-built) | excl-eraser-no-head-lock-as-built | F-1201, F-1114, F-C1201 | M03-L2 | src/ctl_excl.rs:32 | rejected at its obligation |
| `excl_mode_switch_as_built` | ModeSwitchAsBuilt (as-built) | excl-mode-switch-as-built | F-0207 | M03-L2 | src/ctl_excl.rs:80 | rejected at its obligation |
| `excl_plan_build_lock_as_built` | PlanBuildLockAsBuilt (as-built) | excl-plan-build-lock-as-built | F-0905 | M03-L2 | src/ctl_excl.rs:68 | rejected at its obligation |
| `excl_redaction_marker_as_built` | RedactionMarkerAsBuilt (as-built) | excl-redaction-marker-as-built, excl-redaction-marker-as-built-F1302-marker, excl-redaction-marker-as-built-F1302-tomb-live | F-1302, F-1303 | M03-L3, M03-L4, M03-L5 | src/ctl_excl.rs:17, src/ctl_excl.rs:20, src/ctl_excl.rs:23 | rejected at its obligation |
| `derived_algo_cache_edgeless_as_built_f1004` | AlgoCacheEdgelessF1004 (as-built) | derived-algo-cache-edgeless-as-built-F1004 | F-1004 | M04-L1, M04-L2, M04-L4 | src/ctl_derived.rs:68, src/ctl_derived.rs:71, src/ctl_derived.rs:75 | rejected at its obligation |
| `derived_bm25_text_change_as_built_f0703` | Bm25TextChangeF0703 (as-built) | derived-bm25-text-change-as-built-F0703 | F-0703 | M04-L1, M04-L2, M04-L4 | src/ctl_derived.rs:111, src/ctl_derived.rs:114, src/ctl_derived.rs:118 | rejected at its obligation |
| `derived_bucket_aggregate_update_as_built_f0501` | BucketAggregateUpdateF0501 (as-built) | derived-bucket-aggregate-update-as-built-F0501 | F-0501 | M04-L1, M04-L4 | src/ctl_derived.rs:141, src/ctl_derived.rs:146 | rejected at its obligation |
| `derived_control_c1_unmaintained_path` | CtlUnmaintainedPath (mutant) | derived-control-C1-unmaintained-path | - | M04-L1, M04-L2, M04-L4 | src/ctl_derived.rs:229, src/ctl_derived.rs:232, src/ctl_derived.rs:236 | rejected at its obligation |
| `derived_control_c2_token_after_compute` | CtlTokenAfterCompute (mutant) | derived-control-C2-token-after-compute | - | M04-L1, M04-L4 | src/ctl_derived.rs:244, src/ctl_derived.rs:249 | rejected at its obligation |
| `derived_control_c3_rebuild_stamp_only` | CtlRebuildStampOnly (mutant) | derived-control-C3-rebuild-stamp-only | - | M04-L1, M04-L3, M04-L4 | src/ctl_derived.rs:257, src/ctl_derived.rs:261, src/ctl_derived.rs:264 | rejected at its obligation |
| `derived_control_c4_unchecked_gate` | CtlUncheckedGate (mutant) | derived-control-C4-unchecked-gate | - | M04-L4 | src/ctl_derived.rs:275 | rejected at its obligation |
| `derived_control_c5_probe_late` | CtlProbeLate (mutant) | derived-control-C5-probe-late | - | M04-L1, M04-L4 | src/ctl_derived.rs:283, src/ctl_derived.rs:288 | rejected at its obligation |
| `derived_degree_cache_as_built_f0402` | DegreeCacheF0402 (as-built) | derived-degree-cache-as-built-F0402 | F-0402 | M04-L1, M04-L4 | src/ctl_derived.rs:16, src/ctl_derived.rs:21 | rejected at its obligation |
| `derived_degree_cache_as_built_f0406` | DegreeCacheF0406 (as-built) | derived-degree-cache-as-built-F0406 | F-0406 | M04-L1, M04-L4 | src/ctl_derived.rs:42, src/ctl_derived.rs:47 | rejected at its obligation |
| `derived_degree_cache_as_built_fc0401` | DegreeCacheFC0401 (as-built) | derived-degree-cache-as-built-FC0401 | F-C0401 | M04-L1, M04-L4 | src/ctl_derived.rs:29, src/ctl_derived.rs:34 | rejected at its obligation |
| `derived_engine_mode_cache_as_built_f0208` | EngineModeCacheF0208 (as-built) | derived-engine-mode-cache-as-built-F0208 | F-0208 | M04-L1, M04-L2, M04-L4 | src/ctl_derived.rs:154, src/ctl_derived.rs:157, src/ctl_derived.rs:161 | rejected at its obligation |
| `derived_interned_snapshot_as_built_f1005` | InternedSnapshotF1005 (as-built) | derived-interned-snapshot-as-built-F1005 | F-1005 | M04-L1, M04-L2, M04-L4 | src/ctl_derived.rs:83, src/ctl_derived.rs:86, src/ctl_derived.rs:90 | rejected at its obligation |
| `derived_interned_snapshot_as_built_fc0801` | InternedSnapshotFC0801 (as-built) | derived-interned-snapshot-as-built-FC0801 | F-C0801 | M04-L1, M04-L4 | src/ctl_derived.rs:98, src/ctl_derived.rs:103 | rejected at its obligation |
| `derived_ivf_erase_as_built_f0606` | IvfEraseF0606 (as-built) | derived-ivf-erase-as-built-F0606 | F-0606 | M04-L1, M04-L2, M04-L4 | src/ctl_derived.rs:214, src/ctl_derived.rs:217, src/ctl_derived.rs:221 | rejected at its obligation |
| `derived_native_gate_label_index_as_built_f0906` | NativeGateLabelIndexF0906 (as-built) | derived-native-gate-label-index-as-built-F0906 | F-0906 | M04-L1, M04-L2, M04-L4 | src/ctl_derived.rs:199, src/ctl_derived.rs:202, src/ctl_derived.rs:206 | rejected at its obligation |
| `derived_result_cache_04_as_built_f0402` | ResultCache04F0402 (as-built) | derived-result-cache-04-as-built-F0402 | F-0402 | M04-L1, M04-L4 | src/ctl_derived.rs:55, src/ctl_derived.rs:60 | rejected at its obligation |
| `derived_statement_map_direct_delete_as_built_f0303` | StatementMapDirectDeleteF0303 (as-built) | derived-statement-map-direct-delete-as-built-F0303 | F-0303 | M04-L1, M04-L2, M04-L4 | src/ctl_derived.rs:126, src/ctl_derived.rs:129, src/ctl_derived.rs:133 | rejected at its obligation |
| `derived_ttl_cache_as_built_exc05` | TtlCacheEXC05 (exception) | derived-ttl-cache-as-built-EXC05 | - | M04-L1, M04-L2, M04-L4 | src/ctl_derived.rs:184, src/ctl_derived.rs:187, src/ctl_derived.rs:191 | rejected at its obligation |
| `derived_ttl_cache_as_built_f0302` | TtlCacheF0302 (as-built) | derived-ttl-cache-as-built-F0302 | F-0302 | M04-L1, M04-L2, M04-L4 | src/ctl_derived.rs:169, src/ctl_derived.rs:172, src/ctl_derived.rs:176 | rejected at its obligation |
| `removal_bm25_as_built` | Bm25AsBuilt (as-built) | removal-bm25-as-built, removal-bm25-as-built-M05-L3 | F-0702 | M05-L1, M05-L3 | src/ctl_removal.rs:15, src/ctl_removal.rs:19 | rejected at its obligation |
| `removal_control_c1_store_dropped` | CtlStoreDropped (mutant) | removal-control-C1-store-dropped, removal-control-C1b-store-dropped-inventory | - | M05-L1, M05-L3 | src/ctl_removal.rs:121, src/ctl_removal.rs:125 | rejected at its obligation |
| `removal_control_c2_cross_target` | CtlCrossTarget (mutant) | removal-control-C2-cross-target | - | M05-L2 | src/ctl_removal.rs:134 | rejected at its obligation |
| `removal_default_routed_vectors_as_built` | DefaultRoutedVectorsAsBuilt (as-built) | removal-default-routed-vectors-as-built | F-0618 | M05-L1, M05-L3 | src/ctl_removal.rs:99, src/ctl_removal.rs:103 | rejected at its obligation |
| `removal_history_text_as_built` | HistoryTextAsBuilt (as-built) | removal-history-text-as-built | F-C1306, F-CS01, F-C1309 | M05-L1, M05-L3 | src/ctl_removal.rs:87, src/ctl_removal.rs:91 | rejected at its obligation |
| `removal_quarantine_as_built` | QuarantineAsBuilt (as-built) | removal-quarantine-as-built | F-C1305 | M05-L1, M05-L3 | src/ctl_removal.rs:39, src/ctl_removal.rs:43 | rejected at its obligation |
| `removal_reifier_default_graph_as_built` | ReifierDefaultGraphAsBuilt (as-built) | removal-reifier-default-graph-as-built | F-1502 | M05-L1, M05-L3 | src/ctl_removal.rs:63, src/ctl_removal.rs:67 | rejected at its obligation |
| `removal_snapshot_archives_as_built` | SnapshotArchivesAsBuilt (as-built) | removal-snapshot-archives-as-built | F-C1304 | M05-L1, M05-L3 | src/ctl_removal.rs:51, src/ctl_removal.rs:55 | rejected at its obligation |
| `removal_temporal_only_prefix_as_built` | TemporalOnlyPrefixAsBuilt (as-built) | removal-temporal-only-prefix-as-built | F-C1203, F-C1308 | M05-L1, M05-L3 | src/ctl_removal.rs:75, src/ctl_removal.rs:79 | rejected at its obligation |
| `removal_temporal_purge_all_graphs_as_built` | TemporalPurgeAllGraphsAsBuilt (as-built) | removal-temporal-purge-all-graphs-as-built | F-0507 | M05-L2 | src/ctl_removal.rs:112 | rejected at its obligation |
| `removal_vector_indexes_as_built` | VectorIndexesAsBuilt (as-built) | removal-vector-indexes-as-built, removal-vector-indexes-as-built-M05-L3 | F-0606 | M05-L1, M05-L3 | src/ctl_removal.rs:27, src/ctl_removal.rs:31 | rejected at its obligation |
| `snapshot_control_c1_store_left_out` | CtlStoreLeftOut (mutant) | snapshot-control-C1-store-left-out | - | M06-L1 | src/ctl_snapshot.rs:48 | rejected at its obligation |
| `snapshot_control_c2_head_laid_over` | CtlHeadLaidOver (mutant) | snapshot-control-C2-head-laid-over | - | M06-L2 | src/ctl_snapshot.rs:59 | rejected at its obligation |
| `snapshot_control_c3_aggregates_overwritten` | CtlAggregatesOverwritten (mutant) | snapshot-control-C3-aggregates-overwritten | - | M06-L3 | src/ctl_snapshot.rs:70 | rejected at its obligation |
| `snapshot_edge_vectors_missing_as_built` | EdgeVectorsMissingAsBuilt (as-built) | snapshot-edge-vectors-missing-as-built | F-C1804, F-1803, F-1804 | M06-L1 | src/ctl_snapshot.rs:18 | rejected at its obligation |
| `snapshot_merge_aggregates_as_built` | MergeAggregatesAsBuilt (as-built) | snapshot-merge-aggregates-as-built | F-1805 | M06-L3 | src/ctl_snapshot.rs:40 | rejected at its obligation |
| `snapshot_replacing_restore_as_built` | ReplacingRestoreAsBuilt (as-built) | snapshot-replacing-restore-as-built | F-1801 | M06-L2 | src/ctl_snapshot.rs:29 | rejected at its obligation |
| `queue_bounded_redaction_resume_as_built` | BoundedRedactionResumeAsBuilt (as-built) | queue-bounded-redaction-resume-as-built | F-C1303 | M07-L4 | src/ctl_queue.rs:90 | rejected at its obligation |
| `queue_control_c1_lifo_overtaking` | CtlLifo (mutant) | queue-control-C1-lifo-overtaking, queue-control-C1b-lifo-fair-lasso | - | M07-L3, M07-L4 | src/ctl_queue.rs:79, src/ctl_queue.rs:82 | rejected at its obligation |
| `queue_control_c2_two_consumers` | CtlTwoConsumers (mutant) | queue-control-C2-two-consumers | - | M07-L1, M07-L2 | src/ctl_queue.rs:48, src/ctl_queue.rs:51 | rejected at its obligation |
| `queue_control_c3_mark_always` | CtlMarkAlways (mutant) | queue-control-C3-mark-always | - | M07-L1 | src/ctl_queue.rs:59 | rejected at its obligation |
| `queue_control_c4_restart_scan` | CtlRestartScan (mutant) | queue-control-C4-restart-scan | - | M07-L4 | src/ctl_queue.rs:98 | rejected at its obligation |
| `queue_embed_queue_as_built_f0604` | EmbedQueueF0604 (as-built) | queue-embed-queue-as-built-F0604 | F-0604 | M07-L1 | src/ctl_queue.rs:19 | rejected at its obligation |
| `queue_embed_queue_as_built_fc0601` | EmbedQueueFC0601 (as-built) | queue-embed-queue-as-built-FC0601 | F-C0601 | M07-L1 | src/ctl_queue.rs:28 | rejected at its obligation |
| `queue_embed_queue_as_built_fc0605_overtaking` | EmbedQueueOrderAsBuilt (as-built) | queue-embed-queue-as-built-FC0605-overtaking, queue-embed-queue-as-built-FC0605-fair-lasso | F-C0605 | M07-L3, M07-L4 | src/ctl_queue.rs:68, src/ctl_queue.rs:71 | rejected at its obligation |
| `queue_embed_queue_as_built_hd0604` | EmbedQueueHD0604 (as-built) | queue-embed-queue-as-built-HD0604 | F-C0670 | M07-L1, M07-L2 | src/ctl_queue.rs:37, src/ctl_queue.rs:40 | rejected at its obligation |
| `install_concurrent_first_enable_as_built` | ConcurrentFirstEnableAsBuilt (as-built) | install-concurrent-first-enable-as-built | F-1104 | M08-L2 | src/ctl_install.rs:54 | rejected at its obligation |
| `install_control_c1_first_use_accepts_any` | CtlFirstUseAcceptsAny (mutant) | install-control-C1-first-use-accepts-any | - | M08-L1 | src/ctl_install.rs:64 | rejected at its obligation |
| `install_control_c2_unqualified_drop` | CtlUnqualifiedDrop (mutant) | install-control-C2-unqualified-drop | - | M08-L3 | src/ctl_install.rs:77 | rejected at its obligation |
| `install_control_c3_setting_unchecked` | CtlSettingUnchecked (mutant) | install-control-C3-setting-unchecked | - | M08-L4 | src/ctl_install.rs:89 | rejected at its obligation |
| `install_control_c4_enable_race_errors` | CtlEnableRaceErrors (mutant) | install-control-C4-enable-race-errors | - | M08-L2 | src/ctl_install.rs:98 | rejected at its obligation |
| `install_first_use_no_record_as_built` | FirstUseNoRecordAsBuilt (as-built) | install-first-use-no-record-as-built | F-0103 | M08-L1 | src/ctl_install.rs:20 | rejected at its obligation |
| `install_unchecked_setting_as_built` | UncheckedSettingAsBuilt (as-built) | install-unchecked-setting-as-built | F-0903, F-1506 | M08-L4 | src/ctl_install.rs:45 | rejected at its obligation |
| `install_unqualified_drop_as_built` | UnqualifiedDropAsBuilt (as-built) | install-unqualified-drop-as-built | F-0107 | M08-L3 | src/ctl_install.rs:33 | rejected at its obligation |
| `scope_all_graphs_walk_as_built` | AllGraphsWalkAsBuilt (as-built) | scope-all-graphs-walk-as-built | F-0818, F-0819, F-0820 | M09-L2 | src/ctl_scope.rs:27 | rejected at its obligation |
| `scope_control_c1_key_ignores_name` | CtlKeyIgnoresName (mutant) | scope-control-C1-key-ignores-name | - | M09-L1 | src/ctl_scope.rs:81 | rejected at its obligation |
| `scope_control_c2_join_across_graphs` | CtlJoinAcrossGraphs (mutant) | scope-control-C2-join-across-graphs | - | M09-L2 | src/ctl_scope.rs:93 | rejected at its obligation |
| `scope_control_c3_delete_every_graph` | CtlDeleteEveryGraph (mutant) | scope-control-C3-delete-every-graph | - | M09-L3 | src/ctl_scope.rs:105 | rejected at its obligation |
| `scope_control_c4_graph_blind_match` | CtlGraphBlindMatch (mutant) | scope-control-C4-graph-blind-match | - | M09-L4 | src/ctl_scope.rs:117 | rejected at its obligation |
| `scope_delete_every_graph_as_built` | DeleteEveryGraphAsBuilt (as-built) | scope-delete-every-graph-as-built | F-1503 | M09-L3 | src/ctl_scope.rs:61 | rejected at its obligation |
| `scope_interned_no_graph_dimension_as_built` | InternedNoGraphDimensionAsBuilt (exception) | scope-interned-no-graph-dimension-as-built | - | M09-L2 | src/ctl_scope.rs:49 | rejected at its obligation |
| `scope_name_check_missing_as_built` | NameCheckMissingAsBuilt (as-built) | scope-name-check-missing-as-built | F-0202, F-0203 | M09-L1 | src/ctl_scope.rs:15 | rejected at its obligation |
| `scope_three_predicates_as_built` | ThreePredicatesAsBuilt (as-built) | scope-three-predicates-as-built | F-1304, F-1305, F-1105, F-1401 | M09-L4 | src/ctl_scope.rs:73 | rejected at its obligation |
| `scope_unscoped_read_as_built` | UnscopedReadAsBuilt (as-built) | scope-unscoped-read-as-built | F-1002, F-1006, F-1008, F-1013, F-1001, F-1603, F-1604, F-1701, F-0609, F-0711, F-0605, F-0616, F-1507 | M09-L2 | src/ctl_scope.rs:38 | rejected at its obligation |
| `unit_control_c1_per_statement` | CtlPerStatement (mutant) | unit-control-C1-per-statement | - | M10-L1 | src/ctl_unit.rs:78 | rejected at its obligation |
| `unit_control_c2_rollback_all_levels` | CtlRollbackAllLevels (mutant) | unit-control-C2-rollback-all-levels | - | M10-L2 | src/ctl_unit.rs:89 | rejected at its obligation |
| `unit_control_c3_ok_on_failure` | CtlOkOnFailure (mutant) | unit-control-C3-ok-on-failure | - | M10-L3 | src/ctl_unit.rs:100 | rejected at its obligation |
| `unit_hidden_failure_as_built` | HiddenFailureAsBuilt (as-built) | unit-hidden-failure-as-built | F-0306, F-0307, F-0709, F-1508, F-1615 | M10-L3 | src/ctl_unit.rs:70 | rejected at its obligation |
| `unit_no_transaction_as_built` | NoTransactionAsBuilt (as-built) | unit-no-transaction-as-built | F-1511, F-C1501, F-0615, F-C0501 | M10-L1 | src/ctl_unit.rs:48 | rejected at its obligation |
| `unit_per_chunk_commit_as_built` | PerChunkCommitAsBuilt (as-built) | unit-per-chunk-commit-as-built | F-0305 | M10-L1 | src/ctl_unit.rs:18 | rejected at its obligation |
| `unit_per_statement_commit_as_built` | PerStatementCommitAsBuilt (as-built) | unit-per-statement-commit-as-built | F-1601, F-1610, F-1609, F-C1502 | M10-L1 | src/ctl_unit.rs:38 | rejected at its obligation |
| `unit_rollback_all_levels_as_built` | RollbackAllLevelsAsBuilt (as-built) | unit-rollback-all-levels-as-built | F-C0702, F-0704, F-0409 | M10-L2 | src/ctl_unit.rs:29 | rejected at its obligation |
| `unit_wrong_reply_as_built` | WrongReplyAsBuilt (as-built) | unit-wrong-reply-as-built | F-0807, F-0804, F-0817 | M10-L3 | src/ctl_unit.rs:60 | rejected at its obligation |
| `cap_aql_as_built` | AqlAsBuilt (as-built) | cap-aql-as-built | F-0814 | M11-L1 | src/ctl_cap.rs:28 | rejected at its obligation |
| `cap_aql_code_text_as_built` | AqlCodeTextAsBuilt (as-built) | cap-aql-code-text-as-built | F-0815, F-0814 | M11-L3 | src/ctl_cap.rs:40 | rejected at its obligation |
| `cap_control_c1_write_without_read_only_check` | CtlWriteWithoutReadOnlyCheck (mutant) | cap-control-C1-write-without-read-only-check | - | M11-L1 | src/ctl_cap.rs:72 | rejected at its obligation |
| `cap_control_c2_route_without_key_check` | CtlRouteWithoutKeyCheck (mutant) | cap-control-C2-route-without-key-check | - | M11-L2 | src/ctl_cap.rs:83 | rejected at its obligation |
| `cap_control_c3_file_route` | CtlFileRoute (mutant) | cap-control-C3-file-route | - | M11-L3 | src/ctl_cap.rs:94 | rejected at its obligation |
| `cap_demo_server_as_built` | DemoServerAsBuilt (as-built) | cap-demo-server-as-built | F-1614 | M11-L2 | src/ctl_cap.rs:19 | rejected at its obligation |
| `cap_privilege_in_engine_only_as_built` | PrivilegeInEngineOnlyAsBuilt (as-built) | cap-privilege-in-engine-only-as-built | F-0908 | M11-L2 | src/ctl_cap.rs:63 | rejected at its obligation |
| `cap_snapshot_file_helpers_as_built` | SnapshotFileHelpersAsBuilt (as-built) | cap-snapshot-file-helpers-as-built | F-C1803, F-1806 | M11-L1, M11-L2, M11-L3 | src/ctl_cap.rs:48, src/ctl_cap.rs:51, src/ctl_cap.rs:54 | rejected at its obligation |
| `catalog_bm25_index_graph_unchecked_as_built` | Bm25IndexGraphUncheckedAsBuilt (as-built) | catalog-bm25-index-graph-unchecked-as-built | F-0707 | M12-L2 | src/ctl_catalog.rs:19 | rejected at its obligation |
| `catalog_bm25_index_graph_unchecked_as_built_m12_l1_f_0705` | Bm25IndexNoRecordAsBuilt (as-built) | catalog-bm25-index-graph-unchecked-as-built-M12-L1-F-0705, catalog-bm25-index-graph-unchecked-as-built-M12-L2-F-0705 | F-0705 | M12-L1, M12-L2 | src/ctl_catalog.rs:28, src/ctl_catalog.rs:31 | rejected at its obligation |
| `catalog_control_c1_unchecked_read` | CtlUncheckedRead (mutant) | catalog-control-C1-unchecked-read | - | M12-L2 | src/ctl_catalog.rs:71 | rejected at its obligation |
| `catalog_control_c2_short_hash` | CtlShortHash (mutant) | catalog-control-C2-short-hash | - | M12-L3 | src/ctl_catalog.rs:82 | rejected at its obligation |
| `catalog_control_c3_no_record` | CtlNoRecord (mutant) | catalog-control-C3-no-record | - | M12-L1, M12-L2 | src/ctl_catalog.rs:90, src/ctl_catalog.rs:93 | rejected at its obligation |
| `catalog_control_c4_fail_open` | CtlFailOpen (mutant) | catalog-control-C4-fail-open | - | M12-L2 | src/ctl_catalog.rs:103 | rejected at its obligation |
| `catalog_identity_fail_open_as_built` | IdentityFailOpenAsBuilt (as-built) | catalog-identity-fail-open-as-built | F-0601, F-0602, F-0603, F-0613 | M12-L2 | src/ctl_catalog.rs:51 | rejected at its obligation |
| `catalog_ivf_index_graph_unchecked_as_built` | IvfIndexGraphUncheckedAsBuilt (as-built) | catalog-ivf-index-graph-unchecked-as-built | F-0609 | M12-L2 | src/ctl_catalog.rs:41 | rejected at its obligation |
| `catalog_short_hash_name_as_built` | ShortHashNameAsBuilt (as-built) | catalog-short-hash-name-as-built | F-0901, F-C0901 | M12-L3 | src/ctl_catalog.rs:62 | rejected at its obligation |
| `epoch_check_at_start_as_built` | CheckAtStartAsBuilt (as-built) | epoch-check-at-start-as-built | F-1402 | M13-L1 | src/ctl_epoch.rs:18 | rejected at its obligation |
| `epoch_control_c1_no_end_check` | CtlNoEndCheck (mutant) | epoch-control-C1-no-end-check | - | M13-L1 | src/ctl_epoch.rs:34 | rejected at its obligation |
| `epoch_no_check_as_built` | NoCheckAsBuilt (as-built) | epoch-no-check-as-built | F-C1801 | M13-L1 | src/ctl_epoch.rs:26 | rejected at its obligation |
<!--/CONTROL-TABLE-->

## Differences from the explorer machines (none weakens a law)

- Finiteness bounds dropped wherever the laws hold without them (any number of records, writes, sends, fills,
  rebuilds, clears, answers, calls, setups, restores; nat tokens, heads and counters). The theorems therefore cover
  every run of the unbounded machine, and the explorer's bounded runs are among them.
- Sentinels replaced: M-04's invalidated stamp 255 is `None`; M-06's uncarried store 255 is `None`.
- Sets instead of bitmasks: M-03 lock holders, M-05 stores (store k = bit 2^k), M-08 used schemas.
- Generalised domains: M-01 values, M-02 payloads (the first request still carries payload 1), M-08 schema ids and
  setting values (every value above 2 is outside the domain).
- Kept as in the explorer (not generalised): two targets (M-03, M-05), two graphs, two ids and four names (M-09),
  three ids and saturation at 3 overtakes (M-07 order), three records (M-07 resume), the identity derivation and
  `v + 1` as the wrong one (M-04), `% 3` values and the aggregate cap 9 (M-06, M-11).
- M-03: a step naming a target other than 0 or 1 is disabled, and an empty program starts Done (the explorer has
  neither).
- Not ported: the explorer's sharpness checks are ported as `sharp_*` witnesses (non-vacuity) except M-07's
  AG-EF-blind check (as built, id 2 can always still be served); the system machine `sys00` (module 00) is not a
  mechanism and is not ported.

## Instances and objects

Each instance type maps to one explorer variant (`family/name` in `mechanisms.json`) and thereby to its objects; the
mapping is in `RESULTS.json` `law_coverage.laws.*.discharged_by_instances` and in each control's CONTROL line. Objects
that `mechanisms.json` lists with no model (not modelled by the semantics lane: M-01/M-04 `18/namespace`, shown in the
snapshot family; M-03 `15/fhir-graph`, `15/fhir-sync-task`; M-05 `15/fhir-graph`; M-07 `09/compiled-shape`,
`15/fhir-graph`, `15/fhir-sync-task`; M-10 `07/docs-table-search`, `15/concept-pipeline`; M-11 `16/mcp-tool-set`;
M-13 `05/reader-handle`) have no instance here either.

## Open obligations (exact)

1. **Code correspondence**: no proof connects the ObjectScript/Python code to these machines (D-2, D-3); each machine
   is the semantics lane's twin of the cited lines. A law proved here holds for the twin of every instance that
   discharges it; the product's obligation stays as its as-built evidence says.
2. **Mechanisms not composed**: each mechanism is proved alone over its own state; their composition (for example
   M-01 x M-03 x M-05 for erase -> redact) is the subject of `proofs-d9*`, not of this crate; the `sys00` system
   machine stays explorer-only.
3. **Unattached findings**: the axiom-breaking findings that `MECHANISMS.md` does not attach to a mechanism instance
   (its last section) have no instance here.
4. **Fixed small domains** listed above (two targets, two graphs, three ids, three records): the generic proofs are
   over arbitrary parameters within these domains, not over arbitrary numbers of targets, graphs or ids.
5. **M-07 AG-EF-blind fact** (as built, id 2 can always still be served) not ported (explorer-only).

## Trust inventory

No trusted item in the crate: no `assume`, `admit`, `external_body`, `external`, `axiom`, `uninterp`,
`assume_specification` (scanned by the runner, also in actors; `RESULTS.json` `trust_inventory`). `vstd` is Verus's
trusted base (listed, not scanned). `by (compute)` is used only to decide M-03's structural rules on literal programs.
The fairness premises of M07-L4 are hypotheses of the progress theorems.

## Premises the pin violates

Every result is about the reviewed mechanisms (the canonical and reviewed instances, and the laws each departing
variant still keeps). The pin's variants that depart stay failed: each as-built control above is the pin's variant
(with its findings) failing its obligation at the located line, with a proved run of its machine that breaks the law.
In particular the S1 departures: F-1302/F-1303/F-C1350 (M-03 L3, L4, L5: unlocked liveness check, late marker, global
marker clear), F-1201/F-1114/F-C1201 (M-03 L2: erasure without the head lock), F-1105 and F-0511 (M-01 L2), F-0302,
F-0801, F-0301, F-0504, F-1108, F-0503 (M-01 L4), F-1101/F-1306 (M-02 L1, L2), F-CS01 (M-02 L4; M-05 L1/L3),
F-0702, F-0606, F-C1305, F-C1304, F-1502, F-C1203/F-C1308, F-C1306/F-C1309, F-0618 (M-05 L1/L3), F-0507 (M-05 L2),
F-1304/F-1305/F-1105/F-1401 (M-09 L4), F-C1303 (M-07 L4), F-C0605 (M-07 L3, L4). No result here transfers to the
product, and no new product finding was made.

## Cost

<!--COST-TABLE-->
Baseline SMT time and rlimit per mechanism (its mNN, iNN and cxNN modules), from the baseline's Verus JSON; whole-crate wall time 19.16 s per Verus run (one run per control, the same order).

| Mechanism | SMT ms | rlimit | functions |
|---|---:|---:|---:|
| M-01 | 1281 | 2842183 | 74 |
| M-02 | 1173 | 1877103 | 82 |
| M-03 | 20755 | 50228579 | 173 |
| M-04 | 10907 | 22333745 | 205 |
| M-05 | 2088 | 4642260 | 104 |
| M-06 | 733 | 1462561 | 46 |
| M-07 | 5110 | 12331947 | 69 |
| M-08 | 607 | 1226720 | 75 |
| M-09 | 662 | 1416049 | 98 |
| M-10 | 393 | 773013 | 74 |
| M-11 | 781 | 1732768 | 64 |
| M-12 | 517 | 1165914 | 66 |
| M-13 | 501 | 886130 | 15 |
<!--/COST-TABLE-->

## Provenance of the sources

The mechanism files (`mNN_*`) are written by hand. Several instance, counterexample and control files were generated
from per-variant tables by one-off scripts kept with the raw logs (`$RUN_DIR/proofs-mech/gen/gen03.py`, `gen05.py`,
`gen09.py`; the helpers' `$RUN_DIR/proofs-mech/fork-*/gen*.py`); the generated `.rs` files in `src/` are the artifacts
and are verified as they stand. M-03's generator also computes each variant's rule values in Python; every value is
re-checked by Verus (`rules_*`, `by (compute)`). Development copies of the crate (`$RUN_DIR/proofs-mech/fork-*`) were
used to build M-04, M-06, M-07, M-08, M-10, M-11, M-12, M-13 in parallel; only the copies' source files were taken over,
and every registered result comes from this crate.

## Reproduce

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-mech/tools/run_proofs.py --register          # decisive (registered)
    PROOFS_OUT_DIR=$RUN_DIR/proofs-mech-recheck python experiment/playbook-completion/proofs-mech/tools/run_proofs.py
    python experiment/playbook-completion/proofs-mech/tools/law_coverage.py                   # adds law_coverage
