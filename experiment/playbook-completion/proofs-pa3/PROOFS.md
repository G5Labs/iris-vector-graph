# PROOFS-PA3: modules 04 and 11 without premise P-A3 (proof debt D-13, playbook §3.3)

Crate `experiment/playbook-completion/proofs-pa3` (`ivg-pa3-proofs`), lane models-2. Verus 0.2026.10.04, vstd
0.0.0-2026-09-20-0158, `actors` at `c03f9fa`. It is a copy of the breadth crate `proofs-breadth` (D-1, registered as
`proofs-breadth-*`, not modified) with premise P-A3 removed. Evidence grade: **proved** (`--no-cheating`, no trusted
item in this crate), about **models**. Every theorem here is about an L1 contract or a reviewed L2 machine. None says
that the ObjectScript or Python at pin `3eaa79cf` has the property. The product's obligations stay where the as-built
evidence puts them (failed; see "Premises the pin violates").

Gate result: **pass** (`RESULTS.json`, sources SHA-256 `599e7da930d89d62...`). Baseline `cargo verus verify -- --no-cheating`:
**108 verified, 0 errors** (registry `proofs-pa3-baseline`). All 9 controls are rejected, each with every error in
its expected file and a verified counterexample. Independent recheck: `proofs-pa3-recheck` (section 6).

Rerun: `source experiment/playbook-completion/environment.sh; python experiment/playbook-completion/proofs-pa3/tools/run_proofs.py`
(each Verus run under `tools/locks.sh heavy timeout 3600` after `cargo clean -p`; `PROOFS_OUT_DIR=<dir>` writes logs and
RESULTS.json there; `--register` registers the decisive runs under lane models-2).

## 1. What P-A3 was, and what replaces it

In `proofs-breadth`, P-A3 ("an eraser of g overlaps no writer of g") was built into the step relation of module 04:
`ELock` required no writer of g and `WLock` no eraser of g. Module 11's L2 had no eraser at all ("erasure's own
statement cleanup ... core lane"). `proofs-breadth/PROOFS.md` justified P-A3 by the row locks: the eraser's row deletes
wait on writer row locks. That holds for rows that exist. It does not hold for a row a writer inserts after the eraser's
DELETE has passed. The pin violates P-A3: EraseGraph takes no lock before its DELETE (`Eraser.cls:47-261` contains no
`Lock` command), RemoveGraph's lock is shared (`Adjacency.cls:431`, `Lock +^IVG.AdjW(pGraph)#"S":5`) like the writers'
(`Adjacency.cls:63`), and EraseGraph never takes the ledger head lock. F-1201 shows a ledger commit into G landing between
the row DELETE and the statement cleanup (live 8/8, `live-f1201-reproduced`, journal order as oracle). F-C1202 shows the
adjacency kill dropping an edge committed after the row delete (core M2, `core-m2-as-built-F1201-adjacency`).

In this crate the eraser is modelled as the steps of `Graph.KG.Eraser.EraseGraph(g)`, interleaving with every writer of
the same graph under the locks the code takes:

| Module | Eraser steps (L2 labels) | Writers that interleave | Locks modelled |
|---|---|---|---|
| 04 `adj_l2.rs` | `ELock` (TSTART), `ERows` (rdf_edges DELETE of g's rows, `Eraser.cls:217-219`), RemoveGraph (`EStep`+`EKill` reviewed, `EKillOut`+`EKill` as built, `Adjacency.cls:428-445`), `ECommit{g, del}`, `EAbort` (any phase) | adjacency writers (`WLock..WCommit/WAbort`: Put/Remove of one edge from the row hook or a caller, with or without `^IVG.AdjW(g)#"S"`) | P-1201 row locks: the DELETE waits for every open writer of g (each holds its row's lock, inserted or existing); a writer of a row the DELETE removed waits. Nothing blocks a writer that inserts a NEW row of g after the DELETE. |
| 11 `ledger_l2.rs` | `EStart{gr}` (TSTART after the strict-mode guard, `nodes_edges.py:1513`), `ERows` (the DELETEs of gr's rows, `Eraser.cls:217-224`), `EClean` (EraseLedgerFor, `Eraser.cls:1117-1144`: every `("stmt")` entry of gr and its `("tuple")` entry), `ECommit{del}`, `EAbort` (any phase; restores rows and the killed statement nodes) | ledger commits (`Commit`, `CommitNested` + `CallerEnd`), re-enable, governed engine writes (`EngineWrite`, including bulk_delete_adjacency) | P-1201 row locks: the DELETE waits for rows of gr an open nested commit holds; an engine write or an applied commit of a row the DELETE removed waits. A commit or engine write of a NEW row of gr is not blocked. |

The **reviewed design** adds one guard per module. Neither exists at the pin.

| Id | Element | Module | Source | At the pin |
|---|---|---|---|---|
| R11-7 | EraseGraph takes the ledger head lock before its row DELETE and holds it to its commit or rollback. Every commit, nested commit, re-enable and EraseEdges (R11-5) waits for it, and an erasure does not start while a nested commit holds it. | 11 | HD-1201 working answer (serialize erase with commits) | no: Eraser.cls takes no lock; F-1201 |
| R04-5 | EraseGraph takes `^IVG.AdjW(g)` **exclusively** before its row DELETE and holds it to its commit or rollback, so it waits for writers of g that hold the shared lock. A writer of g waits for it instead of writing without the lock (`WriterLock`'s 5 s fallback, `Adjacency.cls:61-73`, is not taken against an eraser). | 04 | HD-1201 working answer, applied to the adjacency writers (ledger-bypassing writers write adjacency too, so the head lock alone does not cover module 04) | no: RemoveGraph's lock is shared, taken after the DELETE; F-C1202 |

Under these guards, P-A3 holds in the reviewed model as a **proved invariant**, not a premise.
`theorem_pa3_from_guard` (module 04): a writer and an eraser of one graph are open together only while the eraser has
not passed TSTART and the writer is a lock-less one already in flight. Its row then blocks the eraser's DELETE, and the
witness `witness_overlap` shows such a run. Module 11: `er_ok` (part of the inductive invariant) says that while an
erasure is open no nested commit is open and no ledger commit has run since it started. A ledger-bypassing engine write
of a new row of gr may land in the middle (witness `witness_erase`); it is an unrecorded write (`drift`).

### Changes to the L1 contracts (reason: a row inserted after the DELETE may legitimately survive)

- Module 04, `adj_l1.rs`: `EraseGraph{g, del}` removes the edge rows its DELETE removed (`del`, all in g). In the breadth
  crate it removed every row of g. With writers interleaving, a serializable outcome may order a write inserted after the
  DELETE after the erase, and then its row survives. That is not a business violation. The violation is the row
  surviving without its adjacency (or statement) entry. Whether a reviewed erase leaves g empty is now the L2 theorem
  `theorem_guarded_erase_removes_graph`: when it commits, no committed row of g is left.
- Module 11, `ledger_l1.rs`: new label `Erase{del}`, with rows := rows minus del and drift := drift ∪ del. The history is
  never touched (`Eraser.cls:25-32`), so erased keys stop following the replay. Keys gain a graph field (`K.gr`). L1 puts
  no strict-mode condition on `Erase`: the guard checks the erasure at its start, and `SetStrict` takes no lock
  (`Ledger.cls:360-383`), so a strict switch is not ordered against an open erasure. Accordingly
  `theorem_strict_refuses_governed_writes` now ensures `!(l is GovWrite)` and `l is Erase || t.drift == s.drift` (the
  breadth version: `t.drift == s.drift`). `theorem_statements_match_records` now requires that no erasure is open.
- Module 11's L2 invariant now contains L1's invariant on the abstraction (`inv2 = inv2c && inv1(abs11(s))`). The
  erasure's DELETE needs the rows to agree with the replay outside drift. `lemma_step_inv` gets it from the L1 step
  (`L1::step_safe`).

## 2. Results

| Item | Module 11 (ledger) | Module 04 (adjacency) |
|---|---|---|
| `Refines<L1>` for every L2 step | 16 labels (11 + 5 erasure labels), `lemma_step_refines`, `lemma_erase_refines` | 26 labels (25 + `ERows`), `lemma_step` |
| L2 invariant inductive | `inv2` (`layout` over the erasure-undone globals `eg(s)`, stats, nested commit, `er_ok`, `inv1(abs11)`) | `inv04` (13 conjuncts: + `inv_del`; `inv_procs` with the guard conjunct) |
| Every raw L2 execution refines L1 and keeps both invariants | `theorem_raw_executions_refine` | `theorem_raw_executions_refine` |
| New theorems | `theorem_strict_refuses_governed_writes` (restated), `theorem_statements_match_records` (no erasure open) | `theorem_pa3_from_guard`, `theorem_guarded_erase_removes_graph` |
| Non-vacuity | `witness_ledger`, `witness_erase` (erasure under the head lock with a bypass insert of a new row of the same graph between its DELETE and its commit) | `witness_adj` (with `ERows`), `witness_overlap` (a lock-less writer of g in flight when the eraser locks; the DELETE then removes its committed row) |
| Controls rejected in the expected file, counterexample proved | 5 of 5 (4 copied + F-1201) | 4 of 4 (3 copied + F-C1202) |

## 3. Broken-implementation controls (located lines, run ids)

Every error is in the expected file, every failing function is in that file's module, and every function of every
other module verifies (`RESULTS.json`, `failing_outside_expected_module` empty). Each counterexample (compiled only with
its feature) is a proved run of the L2 step relation from its initial state.

| Control (finding) | Module | Rejected at (file:line) | Failing functions | Verified / errors | Proved counterexample | Registry |
|---|---|---|---|---|---|---|
| `control_f0801_ttl_cache` (F-0801) | 11 | `src/ledger_l2.rs:1000` | `ledger_l2::lemma_engine_write_refines` | 107 / 1 | cx_f0801_ttl (4 steps, as in proofs-breadth) | `proofs-pa3-f0801-ttl-cache` |
| `control_f0801_fail_open` (F-0801 (LED-B11.3)) | 11 | `src/ledger_l2.rs:1000` | `ledger_l2::lemma_engine_write_refines` | 107 / 1 | cx_f0801_failopen (3 steps) | `proofs-pa3-f0801-fail-open` |
| `control_f1108_unguarded_bulk_delete` (F-1108) | 11 | `src/ledger_l2.rs:1000` | `ledger_l2::lemma_engine_write_refines` | 107 / 1 | cx_f1108 (2 steps) | `proofs-pa3-f1108-unguarded-bulk-delete` |
| `control_fc1101_stats_whole_row` (F-C1101) | 11 | `src/ledger_l2.rs:1190`, `src/ledger_l2.rs:1224` | `ledger_l2::lemma_step_inv`, `ledger_l2::lemma_step_refines` | 106 / 2 | cx_fc1101 (5 steps; `!inv2`) | `proofs-pa3-fc1101-stats-whole-row` |
| `control_f1201_erase_no_head_lock` (F-1201; new control) | 11 | `src/ledger_l2.rs:1070` | `ledger_l2::lemma_head_lock` | 107 / 1 | cx_f1201 (6 steps; committed recorded edge with no statement entry; `!inv2`) | `proofs-pa3-f1201-erase-no-head-lock` |
| `control_fc0401_write_before_gen` (F-C0401) | 04 | `src/adj_l2.rs:811`, `src/adj_l2.rs:822` | `adj_l2::lemma_wout` | 108 / 1 | cx_fc0401 (10 steps; `!inv1`) | `proofs-pa3-fc0401-write-before-gen` |
| `control_hd0401_erase_kills_gen` (F-0401 / HD-0401 (erase)) | 04 | `src/adj_l2.rs:1604`, `src/adj_l2.rs:1612`, `src/adj_l2.rs:1619`, `src/adj_l2.rs:1622`, `src/adj_l2.rs:1863`, `src/adj_l2.rs:1866` | `adj_l2::lemma_eabort`, `adj_l2::lemma_ekill`, `adj_l2::lemma_ekillout` | 106 / 3 | cx_hd0401_erase (12 steps, `ERows` added; `!inv1`) | `proofs-pa3-hd0401-erase-kills-gen` |
| `control_hd0401_rebuild_kills_gen` (HD-0401 (rebuild)) | 04 | `src/adj_l2.rs:2035`, `src/adj_l2.rs:2038`, `src/adj_l2.rs:2097` | `adj_l2::lemma_babort`, `adj_l2::lemma_bkill` | 107 / 2 | cx_hd0401_rebuild (16 steps; `!inv1`) | `proofs-pa3-hd0401-rebuild-kills-gen` |
| `control_fc1202_erase_unguarded` (F-C1202; new control) | 04 | `src/adj_l2.rs:572` | `adj_l2::lemma_erase_guard` | 108 / 1 | cx_fc1202 (17 steps; committed edge with no adjacency entry, RStore not an L1 step, `!inv1`) | `proofs-pa3-fc1202-erase-unguarded` |

**The two new controls (P-A3 removed):**

- `control_f1201_erase_no_head_lock` (module 11, F-1201): EraseGraph takes no head lock. The proof fails at one line,
  `lemma_head_lock` (`ledger_l2.rs:1070`), which needs "no step that takes the head lock runs while an
  erasure is open, and no erasure starts under a nested commit's lock". Counterexample `cx_f1201::counterexample_f1201`
  (6 steps, the live trace's shape: graph 7 empty, as in `live-f1201-reproduced`): genesis; EraseGraph(7) starts; its
  DELETE removes nothing; a ledger commit of a new edge e of graph 7 applies (row, revision 2, `("stmt",1)`,
  `("tuple",e)`); EraseLedgerFor kills every statement entry of graph 7, the new one included; the erasure commits.
  Proved final state: no erasure or transaction open, e's row live (`rows[e] == 1`), e recorded
  (`head == 2`, `("rec",2,1) = create e`), e not an unrecorded write, and e has no `("tuple")` entry. That is a
  **committed recorded edge with no statement entry** (ERS-I3, the conclusion of `theorem_statements_match_records`), and
  `!inv2`.
- `control_fc1202_erase_unguarded` (module 04, F-C1202): EraseGraph takes no lock before its DELETE, and RemoveGraph's
  lock is shared. The proof fails at one line, `lemma_erase_guard` (`adj_l2.rs:572`), which needs "a writer
  of g does not start while an eraser of g is open, and the eraser's lock waits for writers of g holding the shared
  lock". Counterexample `cx_fc1202::counterexample_fc1202` (17 steps; R04-1 and R04-2 kept, so only the guard is
  removed): graph 0 empty; EraseGraph(0) starts and its DELETE removes nothing; a writer inserts the new edge x1 of
  graph 0 (no row lock stops it), steps the generation before and after its write and commits; RemoveGraph steps the
  generation, kills out and degc, and the erase commits. Proved: **the committed edge x1 has no adjacency entry**
  (`rows ∋ x1`, `out ∌ x1`, nothing open). A Degree call then reads generation 3, misses, has its probe granted, counts 0,
  passes its check and stores (3, 0). That store is not an L1 step (a current entry must hold the committed degree, 1).
  After the re-check, with nothing open, `degc[(0,0)] = (3, 0)` is current while the committed degree is 1: `!inv1`
  (ADJ-I5.9).

The seven copied controls are rejected at the same functions as in `proofs-breadth` (their line numbers moved with the
new code). Their counterexamples were kept; `cx_hd0401_erase` gained the `ERows` step.

## 4. The open case "inserts of new rows"

`proofs-breadth/PROOFS.md` (P-A3 row) and TRUST.md record that P-A3 was "not established for inserts of new rows". Here
that case is **modelled, not assumed away**. In the as-built step relations, a writer of g (module 04: `WLock` with
`row_free`; module 11: `Commit`/`EngineWrite` of a key not in the erasure's `del`) may start after the eraser's
DELETE, because a row that did not exist when the DELETE ran has no lock the writer must wait for. Both new
counterexamples are exactly that case: a new edge inserted after the DELETE. Existing rows are covered by the row-lock
conditions: the DELETE (`ERows`) waits for every open writer of g, and a writer or commit of a row in `del` waits. The
DELETE is one step. A real DELETE scans rows one by one, but each row is serialized by its lock, so an insert during the
scan is equivalent to an insert before the DELETE (if the scan reaches it and waits) or after it (premise P-E2). In the
reviewed designs, the guard makes inserts of new rows after the DELETE wait for the erasure's end. Module 11 is the
exception: there, ledger-bypassing engine writes are not blocked. Their keys are unrecorded writes, so the statement
index does not cover them.

## 5. Premises (named; none is an assumption inside a proof)

| Id | Premise | Status |
|---|---|---|
| P-L1..P-L3, P-L5 | as in `proofs-breadth/PROOFS.md` (fresh ids, genesis records the rows, steps are transactions under the code's locks, governed writes wait for a nested commit's row locks) | unchanged |
| P-L4 | Disable waits while a nested commit holds the head lock | **violated** (unchanged) |
| P-L6 | strict mode covers every governed writer | **violated** (unchanged) |
| P-A1, P-A2, P-A5, P-A6 | as in `proofs-breadth/PROOFS.md` | unchanged |
| **P-A3** | an eraser of g overlaps no writer of g | **removed as a premise.** Reviewed: a proved consequence of R04-5 (`theorem_pa3_from_guard`) and R11-7 (`er_ok`). As built: false at the pin (F-1201 live; both new controls) |
| P-A4 | a rebuild overlaps no writer, eraser or second rebuild | **violated** (unchanged; F-C0402) |
| P-E1 | at most one open erasure per graph (module 04) and at most one at a time (module 11) | reviewed: a consequence of the guards (the exclusive lock and the head lock exclude a second eraser); as built: a restriction of the control models only (fewer behaviours, so their counterexamples stand) |
| P-E2 | an erasure's DELETE of a graph's rows is one step | the row DELETEs serialize with each writer through row locks (P-1201), so an insert during the scan is equivalent to one before or after it; not checked against IRIS's scan order |
| P-E3 | module 04: the DELETE's own adjacency effect (the functional index removing `^KG("out")` row by row) is not modelled, because RemoveGraph kills all of g's adjacency in the same transaction. Module 11: EraseLedgerFor's kill of the tuple entries is modelled by graph (with `sidx_ok` every tuple entry of gr is named by a statement of gr). Readers' probe exclusion counts erasers in every phase, which in the as-built control over-restricts readers before RemoveGraph | modelling choices, stated |

## 6. Cost and recheck (measured, `RESULTS.json`)

Baseline (`proofs-pa3-baseline`): Verus 7.4 s, SMT 9.8 s, 25.3 M rlimit over 108 functions, wall 7.9 s, 0.62 GB peak. Each control run took 6.81-8.4 s of wall time. For comparison, `proofs-breadth` took 94 functions, 7.1 s SMT and 18.5 M rlimit.

| Module proof | Functions | SMT ms | rlimit | Largest function |
|---|---|---|---|---|
| 11 ledger (`ledger_l1`, `ledger_l2`, `witness_ledger`) | 61 | 3,929 | 8.63 M | `ledger_l2::lemma_step_inv` 1.88 M (it now also discharges L1's invariant via `L1::step_safe`); `witness_ledger::witness_erase` 1.44 M |
| 04 adjacency (`adj_l1`, `adj_l2`, `witness_adj`) | 47 | 5,822 | 16.68 M | `witness_adj::witness_adj` 3.38 M (concrete witness); `witness_adj::witness_overlap` 1.36 M; largest proof lemma `adj_l2::lemma_reader_step` 1.02 M |

No rlimit was raised and no per-object opaque layout was needed: each step keeps its own lemma over named invariant
conjuncts. Removing P-A3 cost 14 more functions, 2.7 s more SMT time and 6.8 M more rlimit. The added interleavings
are local to the eraser and guard lemmas.

Independent recheck `proofs-pa3-recheck` (`PROOFS_OUT_DIR=$RUN_DIR/proofs-pa3-recheck`, no registration of its parts,
fresh `cargo clean -p` per run): 108 verified, 0 errors, Verus 6.9 s, the same sources SHA-256 (`599e7da930d8`), and all 9 controls rejected at the same file:line locations and functions as the registered runs, each with its counterexample verified (log `$RUN_DIR/proofs-pa3-recheck/run.log`, results `$RUN_DIR/proofs-pa3-recheck/RESULTS.json`).

## 7. Trust inventory

This crate has no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp`
(`--no-cheating` also enforces the first two). The scan of `actors` (`c03f9fa`) finds none either. vstd is Verus's
trusted base. The gate status is **declared empty** (`RESULTS.json` `trust_inventory`).

## 8. What is NOT proved (open obligations)

- **No proof connects the ObjectScript or Python to these L2 machines** (D-2, D-3). Neither guard R11-7 nor R04-5
  exists at the pin.
- The two modules are separate L2 machines of the same EraseGraph. No single machine composes the ledger's statement
  index with the adjacency (the core lane's M2 explorer model does: `core-m2-as-built-F1201-*`).
- Module 11 erasure: one erasure at a time (P-E1). An erasure in a caller's open transaction, EraseNodes / EraseIdSet /
  EraseEdges (bulk_delete_adjacency is the existing engine-write step), and EraseAll are not modelled. A strict-mode
  switch during an open erasure is admitted by L1 (section 1). Statement history beyond the live index is not modelled.
- Module 04 erasure: one eraser per graph (P-E1). The F-1201 live run's other outcome (an FK error that rolls the erase
  back, `live-erase-vs-commit-fk`) is not modelled, because node rows are not in the module 04 L2. The reviewed guard
  R04-5 makes erasers and writers of g wait for each other, and progress (no deadlock between the exclusive lock and a
  writer's row lock) is not modelled.
- Everything listed in `proofs-breadth/PROOFS.md` section 7 still applies.
- F-C1202 is still not reproduced live: in the 8 native F-1201 trials the writer's adjacency write landed after the
  kill (`kg_out_G_defined`). Its evidence is the core model run and this crate's proved counterexample, both about
  models.

## Premises the pin violates

These premises or design elements of the models are false at pin `3eaa79cf`, by this audit's own evidence:

- **P-A3** (an eraser of g overlaps no writer of g). It is no longer a premise here, and the pin violates it.
  EraseGraph takes no lock before its row DELETE and never takes the ledger head lock (`Eraser.cls:47-261`), and
  RemoveGraph's `^IVG.AdjW(g)` lock is shared (`Adjacency.cls:431`). A ledger commit into G lands between the DELETE and
  EraseLedgerFor (F-1201, live 8/8, `live-f1201-reproduced`). Control `proofs-pa3-f1201-erase-no-head-lock` proves the
  consequence over the module 11 model: a committed recorded edge with no statement entry. Control
  `proofs-pa3-fc1202-erase-unguarded` proves the module 04 consequence over the model: a committed edge with no adjacency
  entry, and a current cached degree 0 against committed degree 1 (F-C1202, model only).
- **P-L4** (Disable takes no head lock), **P-L6** (governed content has writers outside the guard), **P-A4** (rebuilds
  overlap writers, erasers and each other): unchanged from `proofs-breadth`.
- Every reviewed-design element (R11-1..R11-7, R04-1..R04-5) is absent at the pin, and each control shows the
  corresponding as-built decision violating the model's contract.

So no safety result here transfers to the product. What transfers is the negative: each as-built decision in section 3
breaks the contract on a reachable run of the model, and for F-1201 the same interleaving is observed live.
