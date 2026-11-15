# PROOFS-SYS: the module-00 axioms over the composed mechanisms (D-14's remaining part)

Lane proofs-sys, steer 13. Product pin `3eaa79cf` (unchanged; `check-product-scope.sh` passes). Crate
`experiment/playbook-completion/proofs-sys` (`ivg-proofs-sys`), Verus `0.2026.10.04.426d8b0`, `vstd`
`0.0.0-2026-09-20-0158`, actors at `c03f9fa`; it depends on `proofs-mech` by path (unchanged; built and verified in
the same build, and included in the trust scan and the sources hash). Logs `$RUN_DIR/proofs-sys/run-*`, recheck
`$RUN_DIR/proofs-sys-recheck/run-*`, generator `$RUN_DIR/proofs-sys/gen/gen_sys.py`.

**Every result is about the semantics lane's composed module-00 model** (`models/semantics/src/sys00.rs` at its commit
`50911c4a`, SHA-256 `ca7c21e74f3d6e06663589bd7620fdb3951570e06f5c9b59bed89cb8bfddcd35`; axioms as
`semantics/axioms.json` states them, SHA-256 `95fe2736ea3492d3466e15d03c597df632dc5652f87d42a3984b8f59e14d67ed`),
not about the product. The pin's as-built composition stays failed: it is a located control whose broken axioms each
have a proved counterexample run.

<!--RESULT-SUMMARY-->
**Result** (run directory `$RUN_DIR/proofs-sys/run-20261114T234729Z`, sources SHA-256 `fc9757dc97b10479b3f8f5d25e14d0c93ca1156b9cc78c60c3ee4096945e09df` including proofs-mech, gate **pass**): baseline **256 verified, 0 errors** with `--no-cheating` (wall 8.13 s, SMT 14993 ms, rlimit 59998656); trust inventory empty; **all 12 axiom checks of module 00 (AX-02..AX-08, AX-10, AX-11 in two parts, AX-12, AX-14) are proved once over the composed design trait**, each from its own obligation, and the reviewed composition discharges every obligation; **12 of 12 located controls** (the pin's as-built composition and the semantics lane's 11 per-axiom mutants) fail exactly at the obligations of the axioms the explorer reports them violating, with refutations and proved counterexample runs. Independent recheck `proofs-sys-recheck` (`$RUN_DIR/proofs-sys-recheck/run-20261114T235149Z`): gate **pass**, 256 verified, 12/12 controls, same sources. Registry: `proofs-sys-baseline`, one `proofs-sys-<feature>` per control, `proofs-sys-recheck`.
<!--/RESULT-SUMMARY-->

## What is composed, and how

`src/sys.rs` restates sys00: four processes (W commits tenant A's content with a retry key and retries once; C commits
tenant B; E erases A; R redacts A) interleave their step programs, plus the operator's actions (stop the erasure between
its steps, re-run it, resume a parked redaction), over the stores the semantics lane's objects share: content,
properties and derived entries per tenant, the ledger's records per tenant, the retry binding with its effect and
post-commit counters, the head lock, the marker, the receipt. The six mechanisms it composes are visible as state
components and step kinds: M-01 (commit with record), M-02 (binding, replay, post-commit step), M-03 (head lock,
marker), M-04 (derived entry), M-05 (erasure and redaction reach, receipt), M-10 (all-or-none erasure, inert refusals).

**The design trait.** The explorer fixes 13 designs (reviewed, as built, one mutant per axiom). Here a design is
`SysDesign::cfg() -> SysCfg`, the choice of one instance per composed mechanism: M-01 whether the first commit records
its change; M-02 post-commit properties in the commit or by a separate step that also runs on a replay; M-03 the
redaction section (reviewed, as built, check-before-lock, never-cleared) and whether the eraser takes the head lock;
M-04 whether erasure maintains the derived store; M-05 which records redaction tombstones (own, every tenant's,
delete), whether it moves the binding, when it writes the receipt; M-10 whether a refusal writes, whether the erasure
is two stoppable steps. The four programs are computed from the choices (`w_step`, `e_step`, `r_step`), and each
explorer design is exactly one choice vector (src/inst.rs; the generator asserts that each design's broken
obligations are the explorer's `violates` list). There are 3,072 choice vectors; every theorem below holds for all of
them that meet its obligation.

**Axioms** (the explorer's checks, word for word): AX-02 (action: a step of the B committer leaves A, every other step
leaves B), AX-03 (action: a refusing or parking step changes no shared store), AX-04 (no half-done erasure), AX-05
(action: each tenant's records only grow or turn into tombstones), AX-06 (one effect and one post-commit write per key),
AX-07 (live content has a live record), AX-08 (derived store equals content), AX-10 (after a receipt with no fresh
commit since, A holds nothing and its key is not bound; no replay re-creates erased content), AX-11 (action: no
tombstone of live content), AX-11M (a marked target is not live), AX-12 (action: a receipt only when no live record of
A remains), AX-14 (AG EF: every process can finish and the marker be released). AX-01, AX-09 and AX-13 are not in
the composition (as in the explorer); their laws are proofs-mech's M-12/M-01, M-08 and M-11 theorems.

**Obligations** (one per axiom, on the choices; `obl_axNN`, discharged by `SysObject::discharge_axNN`): AX-02 no
tombstoning of every tenant; AX-03 inert refusals; AX-04 one-step erasure; AX-05 no deletion of records; AX-06
post-commit properties in the commit; AX-07 the first commit records, inert refusals, no tombstoning of every tenant,
liveness checked inside the lock; AX-08 erasure maintains the derived store, inert refusals; AX-10 erasure maintains
the derived store, properties in the commit, the binding moved, the receipt at Final, and (inert refusals or a marker
that is cleared); AX-11 liveness checked inside the lock; AX-11M the same, inert refusals, properties in the commit;
AX-12 the receipt at Final; AX-14 the marker is cleared.

## Generic proofs (once over the design trait)

- `base.rs` `inv_base` (every design, no obligation): shapes; program counters in range; the head lock is held
  exactly by the process inside a locked section of its program; the marker is set exactly while the redaction is in its
  marked phase (only the redaction sets or clears it); the receipt is written exactly once the redaction passed its
  receipt step; a commit about to apply has seen no marker. `lemma_positions` states every program's facts by
  position, decided by the solver over all choice vectors.
- `facts.rs` `inv_facts` (every design): what the redaction has checked or done still holds while it holds the head
  lock or its marker: A has no content (and no properties, with properties in the commit) inside its first section
  after a check inside the lock, and inside its final section after the final check; A's key is not bound from its
  MoveBinding to its receipt; A has no live record from its tombstones to its receipt. The argument: only W writes A's
  content, properties, records or binding, only at positions where it holds the lock, and for its apply steps only
  having seen no marker.
- `axioms.rs`: `theorem_ax02`, `_ax03`, `_ax05`, `_ax11`, `_ax12` (per step), `theorem_ax04`, `_ax06`, `_ax07`,
  `_ax08`, `_ax10`, `_ax11m` (invariants), each requiring only its own obligation. The step's effect is opaque; its
  closed forms (`lemma_frame`, `lemma_effect_data`, `lemma_effect_binding`) keep each proof to the fields it reads.
- `progress.rs` `theorem_ax14`: constructive. `lemma_ef` returns the schedule that finishes: drain the lock holder,
  then each process alone (`lemma_drain`: every step of a process running alone is enabled); if the redaction is then
  parked on live content, the operator re-runs the erasure (`lemma_drain_e`: A not live after it) and resumes the
  redaction, whose final section then passes (`lemma_drain_r_final`).
- `theorem.rs` `theorem_sys<O: SysObject>`: every axiom for every design that discharges the trait; `inst.rs`
  `laws_sys_reviewed` instantiates it for the reviewed composition (its whole proof work).

## Reuse of the per-mechanism theorems (src/bridge.rs)

For the composed choices that have an exact mechanism instance in proofs-mech, the design's component *is* that
instance (a type generic in the design) and the system obligation is proved **equal** to the component's mechanism
obligation(s), using proofs-mech's own discharge, keep, refute and rule lemmas; proofs-mech's generic theorems are then
instantiated at the component (`component_m02`, `_m03`, `_m04`, `_m05`, `_m10`):

| Composed choice | proofs-mech instance(s) | Proved equality |
|---|---|---|
| M-02 post-commit, binding move | `RetryOf<O>` = LedgerKeyReviewed / LedgerKeyAsBuilt / ZeroRecordRevisionAsBuilt (ledger_rv with the design's post and redact policy) | `obl_ax06 == M02 obl_l1 && obl_l2`; `m05_move_binding == M02 obl_l4` |
| M-03 redaction section; eraser lock | `ExclOf<O>` = RedactionMarkerReviewed / RedactionMarkerAsBuilt / CtlCheckBeforeLock / never-cleared programs; `EraserOf<O>` = EraserNoHeadLockReviewed / AsBuilt | `obl_ax11 == M03 obl_l3 && obl_l5`; `m03_erase_locked == M03 obl_l2` |
| M-04 erasure maintenance | `DerivedOf<O>` = AdjacencyFunctional / IvfEraseF0606 | `erase_maintains == M04 obl_l1 && obl_l2` |
| M-05 tombstone reach | `RemovalOf<O>` = RowsAdjacencyTemporal / CtlCrossTarget | `obl_ax02 == M05 obl_l2` |
| M-10 erasure as a unit | `UnitOf<O>` = Canonical / PerStatementCommitAsBuilt | `obl_ax04 == M10 obl_l1` |

The axioms themselves are proved on the composed machine: sys00 abstracts each mechanism differently from its own
machine (one global reply, applies as single steps, a parked redaction that resumes), so no refinement from sys00 to
the mechanism machines is claimed (open obligation 2). M-01's choice (an unrecorded first commit) has no exact
proofs-mech instance and is not bridged.

**Observation (not a product finding).** The eraser's head lock (M03-L2, F-1201) is not covered by any module-00 axiom
check of sys00: the as-built composition (eraser without the head lock) keeps every sys00 axiom on that dimension,
while its eraser component breaks M03-L2 (`bridge_m03`, proofs-mech's eraser-no-head-lock control). sys00's AX-11
checks only tombstones of live content and the marker; F-1201's lost statement entry is outside its state.

<!--CONTROL-TABLE-->
## Located controls

| Feature | Design (kind) | Explorer check(s) | Axioms broken (= explorer) | Located at | Result |
|---|---|---|---|---|---|
| `sys00_as_built` | SysAsBuilt (as-built) | sys00-as-built-ax-06, sys00-as-built-ax-07, sys00-as-built-ax-08, sys00-as-built-ax-10, sys00-as-built-ax-11, sys00-as-built-ax-11-marker | AX-06, AX-07, AX-08, AX-10, AX-11, AX-11M | src/ctl_sys.rs:20, src/ctl_sys.rs:23, src/ctl_sys.rs:26, src/ctl_sys.rs:29, src/ctl_sys.rs:32, src/ctl_sys.rs:35 | rejected at its obligation |
| `sys00_control_ax02_tomb_both_tenants` | CtlTombBothTenants (mutant) | sys00-control-ax02-tomb-both-tenants | AX-02, AX-07 | src/ctl_sys.rs:45, src/ctl_sys.rs:52 | rejected at its obligation |
| `sys00_control_ax03_refusal_writes` | CtlRefusalWrites (mutant) | sys00-control-ax03-refusal-writes | AX-03, AX-07, AX-08, AX-11M | src/ctl_sys.rs:67, src/ctl_sys.rs:73, src/ctl_sys.rs:76, src/ctl_sys.rs:81 | rejected at its obligation |
| `sys00_control_ax04_erase_split` | CtlEraseSplit (mutant) | sys00-control-ax04-erase-split | AX-04 | src/ctl_sys.rs:93 | rejected at its obligation |
| `sys00_control_ax05_delete_records` | CtlDeleteRecords (mutant) | sys00-control-ax05-delete-records | AX-05 | src/ctl_sys.rs:113 | rejected at its obligation |
| `sys00_control_ax06_post_on_replay` | CtlPostOnReplay (mutant) | sys00-control-ax06-post-on-replay | AX-06, AX-10, AX-11M | src/ctl_sys.rs:133, src/ctl_sys.rs:138, src/ctl_sys.rs:142 | rejected at its obligation |
| `sys00_control_ax07_unrecorded_apply` | CtlUnrecordedApply (mutant) | sys00-control-ax07-unrecorded-apply | AX-07 | src/ctl_sys.rs:157 | rejected at its obligation |
| `sys00_control_ax08_erase_skips_derived` | CtlEraseSkipsDerived (mutant) | sys00-control-ax08-erase-skips-derived | AX-08, AX-10 | src/ctl_sys.rs:177, src/ctl_sys.rs:180 | rejected at its obligation |
| `sys00_control_ax10_binding_kept` | CtlBindingKept (mutant) | sys00-control-ax10-binding-kept | AX-10 | src/ctl_sys.rs:199 | rejected at its obligation |
| `sys00_control_ax11_check_before_lock` | CtlCheckBeforeLock (mutant) | sys00-control-ax11-check-before-lock | AX-07, AX-11, AX-11M | src/ctl_sys.rs:216, src/ctl_sys.rs:221, src/ctl_sys.rs:224 | rejected at its obligation |
| `sys00_control_ax12_receipt_early` | CtlReceiptEarly (mutant) | sys00-control-ax12-receipt-early | AX-10, AX-12 | src/ctl_sys.rs:241, src/ctl_sys.rs:246 | rejected at its obligation |
| `sys00_control_ax14_marker_never_cleared` | CtlMarkerNeverCleared (mutant) | sys00-control-ax14-marker-never-cleared | AX-14 | src/ctl_sys.rs:266 | rejected at its obligation |

Each broken axiom's counterexample is `cx::cx_<design>_<axiom>`, a run of the composed machine from the initial state; each refutation `inst::refute_<design>_<axiom>`.
<!--/CONTROL-TABLE-->

## Premises

| Id | Premise | Status |
|---|---|---|
| PS-1 | The composed machine is the semantics lane's sys00 abstraction: two tenants with one item each, one retry key retried once, one erasure, one redaction run, and every Run step atomic (one transaction, P-0001) | modelling restriction, as in the explorer; not discharged against the product |
| PS-2 | The operator re-runs the erasure of a target found live and resumes a parked redaction (actions ReErase, Resume) | used only by AX-14's schedule; TRUST.md's operator-re-run progress premise; assumed |
| PS-3 | AX-14 is AG EF ("can finish"): the theorem exhibits a schedule that finishes; a scheduler that runs it (fairness) is not modelled | named; a fairness version is open |
| PS-4 | AX-01, AX-09 and AX-13 are outside the composition; their laws are proofs-mech's M-12/M-01, M-08 and M-11 theorems | scope of the explorer check, kept |

No premise is an assumption inside a proof: PS-1 is the model, PS-2 is part of the model (its actions), PS-3 states
what AX-14 means, PS-4 states the scope.

## Differences from the explorer machine (none weakens an axiom)

- Records are kept per tenant (`recs[t]`) instead of one list of (tenant, live) pairs: every operation acts on one
  tenant's records and every law reads one tenant's, so AX-05's global form and its per-tenant form agree.
- The 13 designs are 13 points of the 3,072 choice vectors; the theorems cover all choice vectors meeting each
  obligation, and each obligation is exact for the 13 designs (the located laws equal the explorer's `violates`).
- Counterexamples are stated on the generic machine and proved by evaluating the run for the design's parameters
  (`lemma_run_cfg`, then `compute`); for AX-05, AX-07 and AX-12 the computed facts are concrete (lengths, entries) and
  the solver derives the violation.

## Open obligations (exact)

1. Code correspondence: no proof connects the product's code to sys00 or to the mechanism machines (D-2, D-3).
2. No refinement from sys00 to the proofs-mech machines (they abstract the mechanisms differently); the reuse is the
   proved equality of obligations and the instantiated mechanism theorems (bridge), not a composition theorem over
   the mechanism machines themselves.
3. M-07 (queue) and M-13 (read epoch) are not in sys00's composition; AX-14 here is the composed AG EF, M07-L4's
   fair-service and resume theorems are proofs-mech's.
4. sys00's fixed small world (PS-1) and its axiom checks' scope (the observation above: no check covers M03-L2).
5. AX-14 under fair scheduling (PS-3) instead of AG EF.

## Trust inventory

No trusted item in this crate or in proofs-mech (scanned: no `assume`, `admit`, `external_body`, `external`, `axiom`,
`uninterp`, `assume_specification`; actors scanned too; `RESULTS.json` `trust_inventory`). `vstd` is Verus's trusted
base. `by (compute)` decides concrete runs and M-03's rules on literal programs.

## Premises the pin violates

The as-built composition (post-commit properties re-applied on a replay, F-1101/F-1306; the unlocked liveness check
and global marker clear, F-1302/F-1303; the eraser without the head lock that does not maintain the derived store,
F-1201, F-0702/F-0606 family) breaks AX-06, AX-07, AX-08, AX-10, AX-11 and AX-11M, each with a proved counterexample
run; its obligations fail exactly there. Every theorem here is about the reviewed composition (and about any choice
vector meeting an axiom's obligation); no result transfers to the product, and no new product finding was made.

<!--COST-TABLE-->
## Cost

Whole-crate Verus run 8.13 s wall (proofs-mech dependency cached); per module (SMT ms, rlimit):

| Module | SMT ms | rlimit |
|---|---:|---:|
| axioms | 4488 | 19668673 |
| base | 5595 | 25030521 |
| bridge | 76 | 253278 |
| cx | 2023 | 7281619 |
| facts | 978 | 2756030 |
| inst | 635 | 2055931 |
| progress | 1172 | 2905898 |
| sys | 8 | 17023 |
| theorem | 14 | 29683 |
<!--/COST-TABLE-->

## Reproduce

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/proofs-sys/tools/run_proofs.py --register
    PROOFS_OUT_DIR=$RUN_DIR/proofs-sys-recheck python experiment/playbook-completion/proofs-sys/tools/run_proofs.py
    python experiment/playbook-completion/proofs-sys/tools/report.py     # PROOFS.md sections, RESULTS.json axioms, MATRIX-INPUT.json
