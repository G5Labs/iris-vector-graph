# BREADTH-PROOFS: Verus L1/L2 refinement for modules 11 (ledger) and 04 (adjacency) (proof debt D-1, playbook §3.3)

Crate `experiment/playbook-completion/proofs-breadth` (`ivg-breadth-proofs`), Verus 0.2026.10.04, vstd
0.0.0-2026-09-20-0158, `actors` at `c03f9fa`. Evidence grade: **proved** (`--no-cheating`, no trusted item in this
crate), about **models**. Every theorem here is a statement about an L1 contract or a reviewed L2 machine. None
says that the ObjectScript or Python at pin `3eaa79cf` has the property. The product's obligations stay as the
as-built evidence leaves them (failed or open, see `findings/audit/11.json` and `04.json`).

| Gate item (§3.3) | Module 11 (ledger) | Module 04 (adjacency) |
|---|---|---|
| L1 contract with the business invariants (`Contract` + `SafeContract`) | `src/ledger_l1.rs` | `src/adj_l1.rs` |
| L2 machine over the stored layout, reviewed design | `src/ledger_l2.rs` (`^IVG.Ledger` head/rec/idBySeq/revById/idem/stmt/tuple/stmtNext, meta, revision row, stats row, guard cache) | `src/adj_l2.rs` (`^KG("out"/"gen"/"degc")`, `^IVG.AdjW` holders, `^IVG.AdjNoLock`, edge rows) |
| `Refines<L1>` for **every** L2 step | 11 labels, each mapped and proved (`lemma_step_refines`) | 25 labels, each mapped and proved (`lemma_step`) |
| L2 invariant inductive (`SafeContract`) | `inv2` | `inv04` (12 conjuncts) |
| Every raw L2 execution refines L1 and keeps both invariants | `theorem_raw_executions_refine` | `theorem_raw_executions_refine` |
| Broken-implementation controls rejected in the expected file | 4 of 4, all errors in `src/ledger_l2.rs` | 3 of 3, all errors in `src/adj_l2.rs` |
| Each control's counterexample proved reachable | 4 (`src/cx_f0801_ttl.rs`, `cx_f0801_failopen.rs`, `cx_f1108.rs`, `cx_fc1101.rs`) | 3 (`src/cx_fc0401.rs`, `cx_hd0401_erase.rs`, `cx_hd0401_rebuild.rs`) |
| Non-vacuity (the reviewed L2 does real work) | `src/witness_ledger.rs` | `src/witness_adj.rs` |
| Trust inventory | empty (this crate and `actors`) | same |

Baseline: `cargo verus verify -- --no-cheating`: **94 verified, 0 errors** (module 11: 53, module 04: 41); Verus 6.3 s,
SMT 7.1 s, 18.5 M rlimit, wall 6.8 s, 0.59 GB peak (registry `proofs-breadth-baseline`). Gate: **pass**
(`RESULTS.json`, sources SHA-256 `71aa2c81aaa38624...`). Rerun:
`source experiment/playbook-completion/environment.sh; python experiment/playbook-completion/proofs-breadth/tools/run_proofs.py`
(each Verus run under `tools/locks.sh heavy timeout 3600` after `cargo clean -p`; `PROOFS_OUT_DIR=<dir>` writes logs and
RESULTS.json there so a re-check never overwrites the registered logs; `--register` registers the decisive runs).

## 1. Module 11: ledger

### L1 contract (`ledger_l1.rs`)

State: `st` (never-enabled / enabled / disabled), `strict`, `hist` (revision seq i+1 = `hist[i]`, each with its id, its
records and its retry key), `idem` (key -> (seq, fingerprint)), `rows` (governed content), `drift` (ghost: keys written
outside the ledger), `ok` (the stats row's commit counter). Labels, one per user-visible operation, answer included:
`Enable{strict,id,recs,busy}`, `Disable`, `SetStrict{on}`, `Commit{recs,key,fp,exp,id,out}` with
`out = Applied(seq) | Replayed(seq) | Refused(reason)`, `GovWrite{k,v}` (a governed engine write that lands),
`GovRefused`. The answer `out1` follows the pin's precedence state -> idempotency -> expected_head -> size -> apply
(Ledger.cls:13-14). Business rules and `inv1` (proved inductive):

- **a revision exists iff its mutations are recorded**: a commit appends the revision and applies its records in one
  step. `inv1` includes `agree(rows, replay(hist), drift)`. `theorem_revision_iff_recorded`: with no write outside the
  ledger, `rows == replay(hist)`;
- **an idempotency key binds one fingerprint and replays its revision**: `idem_ok` binds each key both ways to the
  revision carrying it. `theorem_replay_returns_bound_revision`: a `Replayed(seq)` answer changes nothing and names
  the revision bound to that key with that fingerprint. `theorem_key_binds_one_fingerprint`: any other fingerprint is
  refused (`IdemConflict`, or busy) and changes nothing;
- **expected-head refusal**: `theorem_expected_head_refusal`. An expected head that is not the head is refused
  (`UnknownHead` / `StaleHead`, or busy) unless the key replays. `theorem_applied_appends`: an applied commit appends
  exactly one revision on top of the given head and binds its key;
- **strict mode refuses governed writes**: `GovWrite` requires `!(enabled && strict)`.
  `theorem_strict_refuses_governed_writes`: while strict-enabled, no step lands a governed write and `drift` cannot grow;
- stats count the kept revisions: `theorem_stats_count_kept_revisions` (`ok == hist.len()`); revision ids are unique.

### L2 machine (`ledger_l2.rs`) and refinement

Layout: `meta`; `g.head`; `g.rec[(seq,ord)]`; `g.revrow[seq]` (RevisionId, OpCount, IdempotencyKey); `g.id_by_seq`;
`g.rev_by_id`; `g.idem[key] = (seq, fp)`; `g.sx` = `stmt[id] = (key, created, deleted)`, `tuple[key] = id`, `stmtNext`.
The statement index is maintained record by record, like create_rel/delete_rel (LedgerApply.cls:160-171). The state
also holds `stats` (CommitsOk and one refusal counter), `rows`, `txn` (a commit nested in a caller's open transaction
with its before-images: 4.7.0 nesting, head lock held to the caller's end), the guard's `gcache` and `probe_fails`,
and Bump's opened `copies`. `out2` is CommitInTxn's check on the layout: `("idem", key)`, `("revById", exp)`,
`("idBySeq", head)`. The abstraction reads the history back from the layout (`lay_hist`). While a nested commit is
open, the abstraction uses its before-images, so L1 sees the commit when the caller commits it.

| L2 step | L1 step | Proof |
|---|---|---|
| `Enable` never-enabled / disabled / enabled / busy | genesis / re-enable (strict := argument, HD-1104) / no-op / busy | `lemma_genesis`, `lemma_step_refines` |
| `Disable`, `SetStrict` | same | `lemma_step_refines` |
| `Commit` refused, replayed, busy | `Commit` with the same answer, no change | `lemma_out_matches` (layout checks = L1 rules) |
| `Commit` applied | `Commit Applied(head+1)` | `lemma_commit_refines`, `lemma_commit_layout` |
| `CommitNested` (in a caller transaction) | stutter | `lemma_nested_refines` |
| `CallerEnd` keep / rollback | `Commit Applied(seq)` / stutter | `lemma_caller_end_refines` |
| `GuardProbe`, `ProbeFails`, `BumpRead`, `BumpSave` | stutter | `lemma_step_refines` |
| `EngineWrite` landed / refused | `GovWrite` / `GovRefused` | `lemma_engine_write_refines` |

`inv2` (inductive, `lemma_step_inv`): `layout` (`lay_meta`, `lay_dom`: revision row, id maps and records
`("rec", seq, 1..OpCount)` exist exactly for seq 1..head; `lay_ids`; `lay_idem`; `sidx_ok`; `live_ok`: outside
`drift`, an edge has a tuple entry iff it is live in the replay of the recorded history), `stats.ok == head`, and
`txn_ok` for an open nested commit. L2 theorems: `theorem_layout_revision_iff_records` (FR-047 on the layout) and
`theorem_statements_match_records`.

Reviewed design (the working answers), and its status at the pin:

| Id | Element | Source | At the pin |
|---|---|---|---|
| R11-1 | governed writes read strict mode at write time (no TTL cache) | HD-0801 alternative (b) | no: F-0801 (guard.py:38-41) |
| R11-2 | a guard probe that cannot run refuses (fail closed) | HD-0801 (b), HD-1103 (c) | no: F-0801 / LED-B11.3 (guard.py:55-56) |
| R11-3 | every engine writer is guarded, bulk_delete_adjacency included | F-1108 remedy | no: F-1108 |
| R11-4 | each stats counter is one atomic increment of its own field; the commit counter is in the commit's transaction | F-1102 remedy | no: F-1102, F-C1101 |
| R11-5 | EraseEdges (behind bulk_delete_adjacency) holds the head lock | HD-1201 | no: F-1114 |
| R11-6 | Enable reads the state under the head lock (atomic) | F-1104 remedy | no: F-1104 |
| as built | commit precedence, replay, expected head, nesting with deferred unlock | Ledger.cls:388-528 | yes (pin's design) |

## 2. Module 04: adjacency

### L1 contract (`adj_l1.rs`)

State: the committed adjacency `adj` (entries `(graph, source, entry)`), one generation per source `ep`, the cache
`cache[(g, s)] = (generation, count)`. Labels: `Commit{x,add}`, `EraseGraph{g}`, `Advance` (generations move forward),
`Cache` (entries stored, killed or restored), `Hit{k,n}`. Rules: a committed write or erase needs no current entry for
its sources. `Advance` only raises generations, and no step lowers one. A stored or restored entry that carries the
current generation must hold the committed degree. A hit needs a current entry. `inv1`: every entry is no newer than its
generation, and a current entry holds the committed degree (ADJ-I5.9).

- **a cached degree is valid only for its source generation**: `theorem_hit_answers_committed_degree`,
  `theorem_current_entry_is_committed_degree`;
- **no stale degree becomes valid again after erase/rebuild**: `theorem_generations_monotone` and
  `theorem_stale_never_valid_again`. Along any execution, a generation behind a source's generation stays behind, so an
  entry carrying it is never current again, whatever erase, rebuild or restore happens in between.

### L2 machine (`adj_l2.rs`) and refinement

Layout: `out` (dirty: uncommitted entries visible), `gen` (absent reads 0; `$Increment` survives rollback), `degc`,
`nolock` (`^IVG.AdjNoLock(g)`), and the committed edge `rows`. Processes:
- writers `w`: Put / Remove of one edge, holding `^IVG.AdjW(g)#"S"` to their end, or without it with the AdjNoLock mark;
- readers `r`: Degree's steps (read gen, look up, exclusive no-wait probe, count, check, store, re-check;
  Adj.cls:52-91);
- erasers `e`: RemoveGraph in Eraser.EraseGraph's transaction;
- one rebuild `b`: BeginRebuild, RemoveAll, fill, commit or rollback.

A rollback restores the before-image of every node its transaction set or killed (the reader's later degc store
included, when that node was killed). Abstraction: `adj = rows`, `ep = gen`, `cache = degc`.

| L2 step | L1 step |
|---|---|
| `WLock`, `WOut`, `WAbort`; `RStart`, `RLookup` miss or moved generation, `RProbe`, `RCount`, `RCheck`; `ELock`; `EKillOut` (as built only); `BBegin`, `BFill`, `BCommit` | stutter |
| `WPre`, `WPost`, `EStep`, `BStep` | `Advance` |
| `WCommit{x,add}` | `Commit{x,add}` |
| `ECommit{g}` | `EraseGraph{g}` |
| `RLookup` hit with the current generation | `Hit{k,n}` |
| `RStore`, `RRecheck`, `EKill`, `EAbort`, `BKill`, `BAbort` | `Cache` |

`inv04` (inductive, one lemma per step):
- `inv_design`: the reviewed design never reaches the as-built eraser phase;
- `inv_procs`: the modelling premises P-A2..P-A4;
- `inv_lockless`: a writer without the lock has marked AdjNoLock;
- `inv_wrote`, `inv_claimed`, `inv_e_out`, `inv_b_out`: the visible adjacency differs from the committed rows only
  where an open transaction wrote, and the before-images match the rows;
- `inv_gen`: readers' and entries' generations are not ahead;
- `inv_re`, `inv_rw`: a reader whose probe was granted, or whose check passed, while its generation is still current
  has no eraser, rebuild or writer of its source past its lock (with no AdjNoLock mark), and its count is the committed
  degree;
- `inv_cur`: a writer, eraser or rebuild past its lock leaves no current entry of its sources;
- `inv_pre`: entries a rollback would restore are stale.

L2 theorem `theorem_quiescent_cache_is_committed_degree`: with nothing open, a `degc` entry carrying the current `gen`
holds the committed degree, which equals the count of `out`.

| Id | Element | Source | At the pin |
|---|---|---|---|
| R04-1 | a writer steps the generation before it changes out (and after, as built) | F-C0401 remedy; Adjacency.cls:27-30 rationale | no: Put/Remove write out first (Adjacency.cls:87-89, 151-156) |
| R04-2 | RemoveGraph steps every source's generation of the graph before killing out, degc and AdjNoLock; never kills gen | HD-0401 working answer (B/C) | no: kills gen after out (Adjacency.cls:434-439) |
| R04-3 | a rebuild steps every generation before RemoveAll's kills; never kills gen | HD-0401 | no: RemoveAll kills gen, FillEdge does not step (Adjacency.cls:452-462, 824-830) |
| R04-4 | one rebuild at a time, not overlapping writers or erasers | HD-0402 working answer | no: shared lock (F-C0402) |
| as built | Degree's four steps + re-check; shared writer lock; AdjNoLock fallback | Adj.cls:52-91, Adjacency.cls:61-73 | yes |

The reviewed generation step of a whole graph (R04-2) or of every graph (R04-3) is one atomic step over every source.
The code would realize it as HD-0401 option C (a graph epoch folded into each source's generation) or by stepping every
source that has a node. That realization is not modelled.

## 3. Broken-implementation controls

Each feature puts back one as-built decision. Every error is in the expected file, every failing function is in that
file's module, and every function of every other module verifies (`RESULTS.json`, `failing_outside_expected_module`
empty). Each control's counterexample (compiled only with it) is a proved run of the L2 step relation from its initial
state to a step that is not an L1 step. The module 04 counterexamples continue to a quiescent state where L1's
invariant fails.

| Control (finding) | Rejected at (function) | Proved counterexample | Registry |
|---|---|---|---|
| `control_f0801_ttl_cache` (F-0801) | `ledger_l2.rs:814` `assert(!strict_on(s.meta))` (`lemma_engine_write_refines`: a landed write must be an L1 `GovWrite`) | 4 steps: genesis, E1's guard caches "not strict", E2 turns strict on, E1's create_node lands while strict | `proofs-breadth-f0801-ttl-cache` |
| `control_f0801_fail_open` (F-0801, LED-B11.3) | `ledger_l2.rs:814` (same) | 3 steps: genesis strict, the probe fails, create_node lands while strict | `proofs-breadth-f0801-fail-open` |
| `control_f1108_unguarded_bulk_delete` (F-1108) | `ledger_l2.rs:814` (same) | 2 steps: genesis strict, bulk_delete_adjacency erases an edge row and its tuple entry | `proofs-breadth-f1108-unguarded-bulk-delete` |
| `control_fc1101_stats_whole_row` (F-C1101; F-1102 root cause) | `ledger_l2.rs:895` (`lemma_step_refines`: BumpSave must leave L1 unchanged), `:925` (`lemma_step_inv`: `stats.ok == head`) | 5 steps, the live trace b-11-live-f1102-txn: nested commit, B's Bump opens the dirty row, the caller rolls back, B saves its copy: CommitsOk 2 at head 1; `!inv2` | `proofs-breadth-fc1101-stats-whole-row` |
| `control_fc0401_write_before_gen` (F-C0401) | `adj_l2.rs:737` (`inv_rw`: a writer of a current reader's source left its lock phase), `:748` (`inv_cur`) in `lemma_wout` | 10 steps: reader at gen 0 probes, writer locks and writes x1, reader counts 2, checks, stores (0,2), writer rolled back: entry current with 2, committed degree 1; `!inv1` | `proofs-breadth-fc0401-write-before-gen` |
| `control_hd0401_erase_kills_gen` (F-0401 / HD-0401) | `adj_l2.rs:1433` (`inv_re`), `:1441` (`inv_cur`) in `lemma_ekillout` (out killed before any generation step); `:1448/:1451` `lemma_ekill` and `:1673/:1676` `lemma_eabort` (`t.gen == s.gen`: an L1 `Cache` step keeps every generation) | 11 steps, the finding's trace: gen 0, reader probes, RemoveGraph kills out, reader counts 0, stores (0,0), RemoveGraph kills gen and degc, erase rolls back and restores the reader's entry: (0,0) current, committed degree 1; `!inv1` | `proofs-breadth-hd0401-erase-kills-gen` |
| `control_hd0401_rebuild_kills_gen` (HD-0401, rebuild) | `adj_l2.rs:1837/:1840` `lemma_bkill`, `:1899` `lemma_babort` (a kill or restore of `^KG("gen")` is not an L1 step) | 16 steps: reader reads gen 2 and probes, RemoveAll kills out and gen, reader counts 0, fill and commit, a Put steps gen back to 2, reader's check passes and stores (2,0): a stale count valid again, committed degree 2; also `BKill` lowers a generation; `!inv1` | `proofs-breadth-hd0401-rebuild-kills-gen` |

Counts (verified / errors, each including its verified counterexample functions):
- F-0801 TTL 94/1; F-0801 fail-open 94/1; F-1108 94/1; F-C1101 93/2;
- F-C0401 95/1; HD-0401 erase 93/3; HD-0401 rebuild 94/2.

Each control run took 5.8-6.5 s of wall time. These counterexamples are proved over the models. The same defects were
found by the explorer models (`m11-guard-as-built-*`, `m11-stats-as-built-caller-txn`, `adj_degree-as-built*`) and, for
F-0801, F-1108 and F-C1101, reproduced live by breadth lane B.

## 4. Premises (named; none is an assumption inside a proof)

| Id | Premise | The pin |
|---|---|---|
| P-L1 | a new revision id is fresh (CreateGUID) | assumed (step guard) |
| P-L2 | the genesis records exactly the governed rows (LedgerGenesis.Capture) | assumed |
| P-L3 | every L2 step is one transaction under the locks the code takes (IRIS contract: Nesting, Locks deferral, Process stop, Visibility = dirty reads) | IRIS contract, validated differentially (`env-contract-r2`) |
| P-L4 | Disable waits while a nested commit holds the head lock | **violated**: Disable takes no head lock (Ledger.cls:331-358); a disable can land between a nested commit's decision and its caller's commit |
| P-L5 | a governed write waits for the row locks of an open nested commit | IRIS row locks (not checked here) |
| P-L6 | strict mode covers the engine's governed writers; nothing else writes the content outside the ledger | **violated**: writer census (25+ undeclared writer methods), GraphQL mutations (F-1108), server writers; raw SQL and BulkLoader are outside by contract (HD-0301/HD-1103) |
| P-A1 | one edge per writer transaction; readers run outside writers' transactions | the row hook writes one edge per row; caller transactions with several edges and a reader inside its writer's transaction (Adj.cls:41-46) are not modelled |
| P-A2 | no two open writers on one edge | row lock on the edge row |
| P-A3 | an eraser of g overlaps no writer of g | explorer restriction (the eraser's row deletes wait on writer row locks); not established for inserts of new rows |
| P-A4 | a rebuild overlaps no writer, eraser or second rebuild | **violated**: BeginRebuild takes `^IVG.AdjW#"S"` (Adjacency.cls:814-822), which excludes none of them (F-C0402) |
| P-A5 | the whole-graph / all-graph generation step and the rebuild's fill are single steps | reviewed design elements; no such step exists at the pin |
| P-A6 | rollback restores before-images of nodes the transaction set or killed; `$Increment` is not undone | IRIS contract P-0408, P-0401 (journal-confirmed by lane A) |

## 5. Cost (measured, `RESULTS.json`)

Baseline: Verus 6.3 s, SMT 7.1 s, 18.5 M rlimit over 94 functions, wall 6.8 s, 0.59 GB.

| Module proof | Functions | SMT ms | rlimit | Largest function |
|---|---|---|---|---|
| 11 ledger (`ledger_l1`, `ledger_l2`, `witness_ledger`) | 53 | 2,201 | 4.33 M | `ledger_l2::lemma_step_refines` 0.76 M |
| 04 adjacency (`adj_l1`, `adj_l2`, `witness_adj`) | 41 | 4,862 | 14.17 M | `witness_adj::witness_adj` 4.03 M (1.7 s); largest proof lemma `adj_l2::lemma_wpost` 0.85 M |

The largest proof lemma takes 0.85 M rlimit, against Verus's default per-function limit, and no rlimit was raised. The
per-object opaque layout was therefore **not** applied: each L2 step has its own lemma over named invariant conjuncts,
and the cost stays per step. The only large item is the concrete 21-step witness.

## 6. Trust inventory

This crate has no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp`
(`--no-cheating` also enforces the first two). The scan of `actors` (`c03f9fa`) finds none either. vstd is Verus's
trusted base (`Set::len`, `Map::new` and its axioms included). The gate status is **declared empty**
(`RESULTS.json` `trust_inventory`).

## 7. What is NOT proved (open obligations)

- **No proof connects the ObjectScript or Python to these L2 machines** (D-2, D-3). The L2 step relations and
  `theorem_raw_executions_refine` are the plug-in points for trace conformance.
- Module 11 items not modelled:
  - adoption against the verified head (F-1103) and the concurrent-enable race (F-1104): Enable is atomic here;
  - failed operations, revision kinds (F-1107), graph-blind node existence (F-1105);
  - a replay's statement ids (F-1106) and post-commit properties (F-1101): the same mechanism is the core lane's F-1306
    control;
  - statement history beyond the live index;
  - Disable and SetStrict inside a caller transaction (HD-1102);
  - erasure's own statement cleanup (F-1114/F-1201, core lane).
  F-1102's lost updates are rejected by the same control as F-C1101, but no separate counterexample is proved.
- Module 04 items not modelled:
  - token-stamped builds (F-0402), verify drift (F-0403), snapshot restore (F-0404), reweight (F-0405, F-0407),
    `^KG("degw")` (F-0406), a rebuild inside a caller transaction (F-0409);
  - two concurrent rebuilds (F-C0402): the L2 admits one rebuild by design, so this is not a control here (explorer
    `adj_rebuild_txn-concurrent-*` covers it);
  - `^KG("in")`, `^NKG`, per-predicate degc keys and parallel-edge counts.
  A hit whose generation moved between the reader's two reads is a stutter: no claim is made about its answer.
- No progress or liveness property, for either module.
- The L1s are new contracts written for this lane. Their correspondence to the ontology statements (LED-*, ADJ-*) and to
  the explorer models' invariants is by inspection.
- The reviewed designs rest on working answers: HD-0401, HD-0402, HD-0801, HD-1103 and HD-1201 are assumptions or
  supported readings, not maintainer decisions.

## Premises the pin violates

Three premises of these models are false at pin `3eaa79cf`, by this audit's own evidence: P-L4 (Disable takes no head
lock), P-L6 (governed content has writers outside the guard), P-A4 (rebuilds overlap writers, erasers and each other).
Every reviewed-design element R11-1..R11-6 and R04-1..R04-4 is also absent at the pin (sections 1, 2), and each control
shows the corresponding as-built decision violating the model's contract. So no safety result here transfers to the
product. What transfers is the negative: each as-built decision listed in section 3 breaks the contract, on a
reachable run of the model.
