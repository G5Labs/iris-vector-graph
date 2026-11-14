# Trace replay through the breadth machines, and lock logs against the lock plans (playbook §3.7)

Lane: trace-replay (steer 7, Q17h). Namespace AUDITE only (deployed by the pin's own `initialize_schema`, 11:17 UTC).
Product pin `3eaa79cf`, unchanged; nothing compiled into IRIS by the lane (the only writes are the product's own,
through its public API or deployed `Graph.KG` class methods, plus the lane's resets and the two harness steps named
below). Raw traces, reports and logs: `$RUN_DIR/trace-replay/`.

Gates: `3.7-trace-replay` ("trace replay of real runs through the machines") and `3.7-lock-log` ("database
statement/lock log checked against the lock plan"). Evidence grade of every replay result: **trace** (a real
execution's journal replayed through a machine). Lock logs: **live**. Neither is a proof, and neither says anything
about inputs, interleavings or paths the traces did not exercise.

## 1. Method

**Capture** (`trlib.py`, `run.py capture NN`): a scenario is a list of steps; each step runs one product entry point
on its own IRIS connection (or a named persistent one, for an open caller transaction), and a journal mark
(`traces/journal.py`, read server-side, nothing compiled) is taken after it, so the journal records between two marks
are exactly what that step's processes wrote; the Work Queue Manager's worker jobs (bitmap/index maintenance on behalf
of the step) are recognised by their routine (`%SYS.WorkQueueMgr`). Before the first step every non-system global of
AUDITE is snapshotted with the Native API, and again after the last (the engine's own final state).

**Replay** (`trlib.check`, offline, `run.py check NN`), per step:
1. apply the step's journal records to the replayed store in journal order; *continuity*: each record's journaled old
   value must equal the replayed value of its node;
2. *frame*: every store the step wrote is in the step's declared write footprint (loaded from `footprints/NN.json`
   for the named entry points, `trlib.declared`); *foreign-process*: every writing process is one of the step's;
3. *model*: the module's machines map the step (its records, its reply) to actions of the transcribed explorer family,
   check each action is enabled (`next` defined) and that the machine's observable projection equals the abstraction
   `alpha` of the replayed store (and, where a step holds several transactions, at each transaction's end: `trlib.At`).
   A step with model-relevant net writes and no action is *unmapped-transaction*. Invariants and action properties of
   the as-built machine are evaluated on every replayed state: a violation is a product finding reproduced by the
   trace (listed per module; it is not a replay failure);
4. *faithfulness*: the replayed final store equals the engine's final snapshot.

Each machine is replayed twice: as built (must match every step: that is the replay result) and in the family's
reviewed design (expected to diverge where the finding is; the first divergence is reported). Machines are
transcriptions of `models/breadth-a/src/*.rs`, `models/breadth-b/src/m07.rs`..`m11.rs` and
`models/breadth-c/src/*.rs` into `families_a.py`, `families_11.py`, `families_b.py`, `families_c.py` (each class
cites the Rust lines); the model crates are not modified and not linked. The explorers' exploration bounds
(operation counts) are not guards of a real step and are not applied in the replay.

**Controls** (`trlib.mutate`, three per scenario, each must be flagged by one of its expected rules): *dropped record*
(the first model-relevant SET removed: model-post-state, continuity or faithfulness), *reordered transaction* (the
records of two model-relevant steps swapped, or, in a one-step trace, two of its transactions or two writes of one
node: model-post-state, model-not-enabled or continuity), *foreign write* (a copy of a model-relevant record
attributed to process 999999: foreign-process). A scenario may name the reorder pair (`CONTROL_PAIRS`, used only by
08/readonly, where the default pair is two identical machine actions); every other scenario uses the default choice.
The oracle itself has a self-test on the lane's scratch global
`^IVGAuditE` (plain SET, transactional SET/KILL/$Increment, nested level rolled back, full rollback, subtree KILL):
replay equals the engine, and each control is caught (`selftest_oracle.py`, `tr-oracle-selftest`).

**Lock logs** (`locklog.py`, `lockrun.py NN`, `lockcheck.py NN`): IRIS has no lock event log, so (a) a server-side
loop polls the planned lock names in `^$LOCK` (17,800-49,000 polls/s here) while one process runs the module's writers
in a loop, and a second loop scans the whole lock table every 50 ms for any other IVG/^KG/table lock the writer
holds; (b) block probes: a probe process holds one planned lock and the writer's state (`%SYS.ProcessQuery` State,
CurrentLineAndRoutine) and its own lock rows are sampled while it waits; journal marks split what it wrote before and
after the release. The plan is the `locks` entries of `footprints/NN.json` and the source lines they cite.

### Limits (apply to every module)
- One scenario per family; sequential steps (plus the open-caller-transaction interleavings named per module). A
  replay pass says the as-built machine matched these traces, not that the handler performs its step on every input.
- Bitmap index chunks (`BitSET` records: the journal reader reports the bit's value, not its position) and the SQL
  class dictionary (`^odd*`, written by the product's own DDL for routed tables) are not replayed; every other node of
  AUDITE is.
- Values the Native API cannot read as bytes (`$vector`) are compared by presence only.
- Lock polling sees a lock held at least one poll period (20-60 µs); shorter holds (Degree's exclusive probe, the
  release between two redaction batches) are not seen; the block probes cover those cases where it matters.

## 2. Results per module

Run ids: `tr-replay-NN` (the replay of all the module's scenarios, as built and reviewed), `tr-controls-NN`,
`tr-locklog-NN`. "Steps / records / actions" are captured steps, journal records replayed, and machine actions applied.

### 01 install-schema — `ins_setup` (breadth-a/src/ins_setup.rs:42-109)
- Scenario `firstuse`: harness removes the schema record `^IVG.Deploy("schema")` (as breadth probe p0103 did in AUDITA;
  restored in the same capture), the product's first-use check `schema_name.check_first_access` (the function an
  engine runs on first access, engine.py:1850-1866) accepts, the record is put back, a second check accepts. 4 steps,
  3 records, 6 actions. The two harness steps are environment steps mapped to machine restarts at reachable states
  (marker without record = Ok, Ok, Stop; record restored = five Ok steps), documented in the class.
- Result: as built matches every step; replay equals engine. **F-0103 reproduced** (INS-I3.4 at step 1: accepted with
  no record because the marker class exists). Reviewed design diverges at step 1 (it refuses). Controls: 3/3 caught.
- Scenario `setup` (follow-up, `tr-replay-01-r2`): harness removes the schema record, the pin's own
  `initialize_schema()` runs on AUDITE (its classes are unchanged, so nothing is compiled and the journal stays small:
  41 records), the first-use check accepts on the record setup wrote. 3 steps, 41 records, 8 actions (class
  `InsSetupRun`): the setup call is `NewRun` (the machine's step reset to Tables keeping the store's marker and record,
  an initial-state generalisation: the explorer models one setup on a fresh namespace) then one Ok/Fail per step,
  chosen from the reply and the WARNING records the call logged (captured by the scenario): Tables fails on a logged
  "Schema setup warning", Classes on a non-empty `objectscript_failed`, Kg on a logged "^KG bootstrap failed"
  (`kg_built` false alone means this run did not need to build ^KG). This run: no warning logged, `warnings` [],
  `objectscript_failed` {}, so five Ok; the Record step is the journaled `^IVG.Deploy("schema")` write. Matches as
  built, replay equals engine, no invariant violated (INS-B1.12 holds on this success path); reviewed design does
  not diverge. Controls 3/3 (`tr-controls-01-r2`; the reorder caught by model-post-state).
- Gap: setup replayed only on an already set-up namespace and only on its success path (no table created, no class
  compiled, ^KG not rebuilt; the failure paths of F-0102 not exercised). `ins_legacy` not replayed (no legacy objects
  exist in AUDITE and creating some would compile classes).
- Lock log: one `initialize_schema()` (3.2 s, no recompile) held only the parent `^IVG.AdjW` shared (its ^KG rebuild),
  within the declared plan; no ledger head lock. The plan's `^IVG.AdjW(g)` E:0 and `^IVG.NKGBuild` X were not exercised.

### 02 graph identity — `gid_mode` (breadth-a/src/gid_mode.rs:36-136)
- `offlone`: multigraph on, two Cypher CREATEs (edge keys 0, 1), Cypher DELETE of key 0, mode off (accepted), create_edge.
  6 steps, 96 records, 9 actions. **F-0201 reproduced** at step 5 (GID-I4.10: mode off, rows {0, 1}).
- `cache`: engine E1 sets on and CREATEs (caches "on"), engine E0 sets off, E1 CREATEs again. 4 steps, 44 records,
  7 actions. **F-0208 reproduced** at step 3.
- Both match as built; replay equals engine; controls 3/3 each. Reviewed diverges at the mode-off step (its Set is one
  locked step). Not exercised: the concurrent count/kill race of F-0207 (no interleaving inside `GraphMode.Set`).
- Lock log: 5,048 `set_multigraph` on/off calls held no polled lock and no IVG lock in the scans, and Set(off) did not
  wait while `^IVG.AdjW(g)` was held exclusively: matches the plan (no lock; the premise of F-0207). Holds.

### 03 direct writes — `wrt_ledger_stmt`, `wrt_bulk_atomic`, `tmp_mark` (breadth-a)
- `stmt`: ledger create of a-[TR]->b, direct delete_edge, direct create_edge, ledger set_qualifier by tuple, ledger
  delete by tuple, ledger re-create, delete_node. 7 steps, 250 records, 7 actions. **F-0303 reproduced**: INV-stmt at
  step 1 (the live statement outlives its row), WRT-B1.9 at step 3 (the update joins a second edge lifetime to the
  statement). Reviewed diverges at step 1.
- `bulk`: bulk_create_nodes of 2,000 nodes on a from_connect engine (two loader chunks on the engine's own Native API
  process), the last node's property wider than `rdf_props.val`. 2 steps, 92,056 records, 4 actions with two
  transaction-end checkpoints. The loader committed chunk 1 in its own transaction, rolled chunk 2 back, the SQL
  fallback rolled back, the call raised "nothing written", 1,000 nodes stayed committed. **F-0305 reproduced** (WRT-B3.19
  in state Raised with committed = (true, false)); new finding **F-C0330** (the reply says nothing was written).
- `mark`: over a temporal edge's marked row, store_edge then the last temporal delete; the same with create_edge (the
  adopting control). 6 steps, 125 records, 6 actions. **F-0304 reproduced** (ADR-0009 explicit-survives violated by the
  temporal delete after store_edge); the create_edge triple keeps its row (no violation).
- All match as built, replay equals engine, controls 3/3 each. Frame gap (footprint file, not the product):
  `footprints/03.json` `py:IRISGraphEngine.delete_node` omits `^IVG.Ledger` and `^NKG`, which the journal shows it
  writing (Eraser.EraseNodeIds' per-edge statement/tuple kill).
- Lock log: 781 create_edge+delete_edge pairs held `^IVG.AdjW("g")` shared only (plus SQL row locks of their rows);
  690 create_node held no adjacency lock; with `^IVG.AdjW(g)` held exclusively a create_edge waited 5.0 s at
  WriterLock (`+629^Graph.KG.Adjacency.1`, Adjacency.cls:60-64) holding its row locks (node rows, edge row, unique
  index entry: taken before the writer lock), then wrote `^IVG.AdjNoLock(g)` and the adjacency without the lock (the
  plan's fail-open). Holds.

### 04 adjacency — `adj_degree`, `adj_rebuild_txn` (Caller), `adj_token` (breadth-a)
- `degree`: Degree reads (miss, hit) around a committed Put, a Remove inside a caller transaction that rolls back (the
  journal shows its generation $Increment outside the transaction: the generation stays moved, P-0401), a committed
  Remove, EraseGraph, each read's answer checked against the machine. 11 steps, 170 records, 49 actions. No finding
  expected (F-0401/F-C0401 need a reader in flight across a rollback, not produced). HD-0401 design diverges at the
  erase (it steps the generation, the pin kills it).
- `rebuild`: engine.sync() inside a caller transaction on the caller's process, first failing on a poisoned row
  (graph_id '0', the upstream fixture's method; removed by a harness step), then succeeding. 9 steps, 140 records,
  10 actions. **F-0409 reproduced** (ADJ-B8.9 at the failing sync: $TLevel 0 and the caller's node gone).
- `token`: W opens a transaction and creates x-R->y (token stepped, not undone), kg_WCC computes and caches under the
  token, W rolls back, a fresh engine is served the cached answer (`cache_stats {'hit': 1}`, x and y joined). 4 steps,
  34 records, 7 actions. **F-0402 reproduced** (ADJ-I11.2 after the rollback).
- All match as built; controls 3/3 each.
- Lock log: Degree (+ a write every 5th call) held only the writes' `^IVG.AdjW(g)` S; Degree's own exclusive probe
  (`#"E":0`, Adj.cls:66-70) is too short to be polled, and with `^IVG.AdjW(g)` held shared Degree did not wait and
  answered (no degree-cache store: no record). sync (86 calls) held the parent `^IVG.AdjW` S (BeginRebuild,
  Adjacency.cls:812-819) and `^IVG.NKGBuild` X, mostly disjoint (2 of 209 intervals nested each way, no consistent
  order between the two; no conflict follows since the parent lock is shared); with `^IVG.AdjW` held exclusively sync
  waited 5 s at BeginRebuild (`+64^Graph.KG.Adjacency.1`) and failed "writer lock was not granted in 5 seconds",
  having written only `^KG("__version")` before the wait. Holds.

### 05 temporal — `tmp_bucket`, `tmp_mark` (breadth-a)
- `bucket`: insert (w 1), update at the same coordinate (w 2), skip-mode write, insert at a second coordinate, delete
  of the first. 5 steps, 62 records, 5 actions. **F-0501 reproduced** at the update (count 2, sum 3 for one edge).
- `mark`: explicit create_edge with `{"temporal": 1}`, temporal insert, last temporal delete (**F-0505 reproduced**:
  the explicit row is retracted); a temporal insert then `TemporalIndex.Purge()` (**F-0507 reproduced**: the marked row
  outlives every timestamp), then purge_before. 8 steps, 153 records, 6 actions.
- Both match as built; controls 3/3 each; reviewed diverges at the finding steps.
- Lock log: 2,927 temporal insert+delete pairs held `^IVG.AdjW(g)` S only; with it held exclusively a temporal insert
  wrote tout/tin/tlast/bucket first, then waited 5 s at WriterLock (AssertTemporalRow's row hook) and proceeded
  fail-open. Holds (the temporal stores are outside the writer lock by design).

### 06 vectors — `vec_ivf`, `vec_route_batch` (breadth-a)
- `ivf`: an IVF index over graph g with two cells (built before the capture), ivf_insert a and b, ivf_insert a again
  with the other cell's vector, ivf_delete a, erase_graph(g). 5 steps, 124 records, 8 actions. **F-0608 reproduced**
  (a listed in two cells; indexed 3 for 2 ids) and **F-0606 reproduced** (after the erase the index lists ids with no
  live vector; the vectors were in the graph's routed table, which the erase dropped).
- `route`: store_embeddings under a model key with no route: [a, missing m] width 2 (refused after the route was
  created and committed), [a] width 2 (stored), [a] width 3 (refused by the route's identity). 3 steps, 106 records,
  3 actions. **F-0615 reproduced** (VEC-X3.9 at step 0).
- Both match as built; controls 3/3 each. `vec_queue` (F-0604) and `vec_build_publish` not replayed.
- Lock log: 691 store_embedding+ivf_insert pairs held no IVG lock (the scan saw only the routed table's row locks and
  the class-dictionary lock of the route's DDL), and store_embedding did not wait for `^IVG.Ledger("head")` or
  `^IVG.AdjW(g)`. Holds (plan: no locks).

### 07-10 — see section 3

### 11 ledger core — `enable`, `commit`, `retry`, `guard`, `adopt` (breadth-b/src/m11.rs)
- `enable`: first enable (genesis), second enable (fast path). 2 steps, 28 records, 5 actions; matches; no finding
  (F-1104 needs two concurrent first enables).
- `commit`: P1 commits inside a caller transaction, the caller rolls back, P2 commits. 3 steps, 67 records, 6 actions;
  matches (the chain stays 1..head; the control design that unlocks at once is not distinguishable on this sequential
  trace).
- `retry`: commit with post-commit property V1 and key K, governed set to V2, retry of the first changeset. 3 steps,
  119 records, 3 actions. **F-1101 reproduced** (LED-B10.5 and the governed-value invariant: the replay writes V1 over
  the recorded V2) and **F-1106 reproduced** (the replay answers no statement ids).
- `guard`: E1 writes (caches not strict), E2 sets strict, E1 writes within the 5 s cache (lands: **F-0801**), the cache
  expires, E1's guarded write is refused, E1's bulk_delete_adjacency lands in strict mode (**F-1108**), E1 commits
  through the ledger. 7 steps, 122 records, 7 actions; SG violated from step 2. Frame gap: the refused create_node
  wrote `Graph_KG.ledger_stats` (the refusal counter), absent from `footprints/03.json` create_node.
- `adopt`: genesis, disable, an unrecorded node (before the capture); enable (adopts it: one adoption revision); a
  ledger commit of an edge from it. 2 steps, 79 records, 4 actions; matches (no F-1103: that needs a commit between the
  adoption's read and its commit).
- All match as built; controls 3/3 each. Not replayed: `stats` (F-1102 needs a Bump blocked by an open caller
  transaction).
- Lock log: closed before this lane (`corr-lockplan`).

### 13 redaction (lock log only)
- `Redact` with batch 1 over 4 target revisions (10 batches + Final in the receipt): the redaction pid held only
  `^IVG.Ledger("head")` exclusively (no other IVG lock in the scans); the releases between batches are shorter than the
  poll period (one episode seen).
- Final's head lock isolated: with the head lock held from the start the redaction waits at Batch's lock
  (`+11^Graph.KG.LedgerRedact.1`, LedgerRedact.cls:282) having written nothing; with a probe session that waits for
  the redaction marker (set by the first Batch inside its transaction) and then queues for the head lock behind the
  only Batch (batch 1000), the redaction waits at a second line (`+119^Graph.KG.LedgerRedact.1`) after writing its 8
  tombstones and clearing revisions 2-5, and writes its redaction revision (row 6) and the head only after the probe
  releases (receipt: 2 batches, complete). This is Final's lock (LedgerRedact.cls:390). Holds.

### 15 integrations — no machine can be driven
- `reify` `FHIRGraph.Register` refuses at FHIRGraph.cls:179-181 ("no FHIR repository", 0 records);
  reify_edge (61 records) and delete_reification (54 records) match no breadth-c family. FHIR machines (fhir.rs,
  register.rs): **blocked-access** (HS.FHIRServer / HS_FHIRServer absent on IRIS Community 2026.1); reification:
  **unrepresentable** in the breadth-c machines (no family covers it). Lock log: blocked (the sync lock is taken only
  on a registered FHIR graph).

### 16 interfaces — `unit` (breadth-c/src/unit.rs:20-140)
- `bolt`: in-process BoltSession._dispatch (harness transport overrides `_send_message` only): a fault-free unit, then
  BEGIN, RUN w1, failing RUN, RESET, the driver's retry. 12 steps, 182 records, 12 actions. **F-1601 reproduced** (unit
  atomicity at the RESET: w1 kept; at most once at the retry: w1 twice).
- `http`: POST /db/neo4j/tx/commit [w1, bad] through FastAPI TestClient (400, w1 committed), then the resend.
  2 steps, 111 records, 6 actions. **F-1610 reproduced**. Controls 3/3 each. Not exercised: TCP/WebSocket transports.

### 17 operations — `retry` (breadth-c/src/retry.rs:22-170)
- IVGClient against the in-process app through a harness transport that drops the first reply after a 200: the client
  resends; a second call gets every reply. 2 steps, 111 records, 9 actions. **F-C1703 reproduced** (at most once: the
  node created twice). Controls 3/3. Not exercised: the server-side re-run after an exception (F-C1604).

### 18 snapshots — `restore` (breadth-c/src/restore.rs:28-150), `snapcut` (snapcut.rs:26-160)
- `restore`: commit A (seq 2), save_snapshot, commit B (keyed, seq 3), erase and redact tenant A (seq 4), replacing
  restore, a commit after it. 7 steps, 367 records, 7 actions. **F-1801 reproduced**: one history, a redacted record
  holds no content, and the ledger only grows all violated at the restore (head back to 2, revisions 3-4 and the key
  binding survive, seq 2's tombstones overwritten); the next commit is refused (revision row 3 exists). Model gaps
  recorded: the pin's redaction writes its own revision (mapped as Redact + an unkeyed Commit); genesis is taken from
  the abstraction; the erase step touches nothing the machine reads.
- `snapcut`: a writer's open transaction creates node b and edge a->b; save_snapshot; rollback. 4 steps, 78 records,
  6 actions. **F-C1801 reproduced** (the archive holds a state that never committed).
- Controls 3/3 each.
- Lock log: 58 replacing restores held only the parent `^IVG.AdjW` S (from its `erase_all`: Eraser.EraseAll ->
  Adjacency.RemoveAll, Adjacency.cls:451-457) and never the ledger head lock; with the head lock held exclusively a
  restore did not wait (121 records written while it was held). The declared plan ("none: the ledger head lock is not
  taken") holds for the head lock and omits the inherited `^IVG.AdjW` S (plan gap, not a defect).

## 3. Modules 07-10 (breadth-b machines `models/breadth-b/src/m07.rs`..`m10.rs`, transcribed in `families_b.py`)

### 07 text search — `bm25` (m07.rs:62-391), `leg` (m07.rs:406-537)
- `bm25`: bm25_build over graph tr07g, bm25_insert, bm25_delete, the empty index-handle build
  (`index(name).build(properties=[nonexistent])`), bm25_search, bm25_drop. 6 steps, 121 records, 11 actions.
  **F-0704 reproduced** at step 3 (TXT-X2: the build raised IndexNotBuiltError after replacing the index with N=0).
  The journal shows bm25_build's 94 records and bm25_drop's KILL outside any transaction, insert and delete in one
  committed transaction each (F-0701's premise; the concurrent I5 race was not driven). Reviewed diverges at step 3.
- `leg`: an index built over graph A, two indexes created by a first bm25_insert (no recorded graph), USE GRAPH-scoped
  and unscoped `ivg.bm25.search`, a drop. 8 steps, 46 records, 8 actions. **F-0707** (TXT-I7) and **F-0705**
  (TXT-B8.3) reproduced at the asks. Fusion and Retrieve not driven (Retrieve needs an embedder; fusion's registry
  also lists the `__stop__` pseudo-index, F-0706, which the machine lacks).
- Both match as built; controls 3/3 each. Lock log: closed before this lane (`b-07-*`).

### 08 Cypher on SQL — `txn` (m08.rs:37-196), `readonly` (m08.rs:346-389)
- `txn`: the F-0805 CREATE with the literal edge present; a caller TSTART and create_node; the same CREATE inside the
  caller's transaction; a stepped write failing on 1/0; caller TCOMMIT; a stepped write that succeeds. 6 steps, 292
  records, 19 actions over three machine instances. **F-0805** (steps 0 and 2) and **F-0806** (step 3: the error says
  earlier steps are written, none is) reproduced; ATOMIC and CALLER held.
- `readonly`: a read, a CREATE (refused), two AQL writes carrying a SET in the collection name, a dotted
  `GRAPH_KG.TXN_BEGIN`, with read-only requested. 5 steps, 64 records, 5 actions. **F-0814** (an AQL write in read-only
  use changed data) and **F-0815** ($TLEVEL 0 to 1 under read_only) reproduced.
- Both match as built. Controls: 3/3 in `txn`; in `readonly` the reorder control swapped the two AQL writes, which are
  the same machine action, so no model rule can see their order: it was flagged only by faithfulness and
  foreign-process, which `run.py` does not count (`tr-controls-08` registered **fail** for that reason, kept as
  recorded). Follow-up `tr-controls-08-r2` (pass): every journaled transaction of `readonly` is an AqlWrite (the other
  calls write nothing), so `m08.CONTROL_PAIRS` names the pair (1, 2): the first AQL write's transaction is moved one
  call earlier onto the refused read-only CREATE (`Call(WriteClause)`), and model-post-state flags step 1 (the machine
  has a refused call change no data; the replayed store shows data changed). `txn` controls unchanged.
- Lock log: 284 Cypher CREATE+DELETE pairs held `^IVG.AdjW(g)` S only (row hook) plus SQL row locks; with it held
  exclusively a CREATE waited 5.0 s at WriterLock holding its node, label, property, edge and unique-index row locks,
  then completed. Holds.

### 09 native executor — `gate` (m09.rs:460-516)
- `gate`: native count read (process compile mode "off") compared with the SQL path, SET n:TRL, read, REMOVE n:TRL,
  read. 5 steps, 29 records, 5 actions; matches; no finding expected (both indexes declared, so F-0906's edge-only
  state is not reached without DDL). Controls 3/3.
- `planc`, `mode`, `used` not driven: in job/sync mode the executor compiles generated classes (IVGC.P<h>) into the
  namespace at run time, which this lane does not trigger. For the same reason the lock log (`^IVG.CypherCompiled(h)`
  X:0, Gen.cls:166-167) was not taken.

### 10 algorithms — `cache` (m10.rs:99-303), `degree` (m10.rs:653-697)
- `cache`: PPR from tr10x before the node exists, create_node with no edge, PPR, delete_node, PPR, delete_edge, PPR.
  7 steps, 84 records, 17 actions. **F-1004 reproduced** at step 2 (the entry cached before the node existed is served
  with the token unchanged; the fresh answer is the machine's own computation). Token abstracted by rank (an edgeless
  delete moved `^KG("__version")` by 2). Frame gap: delete_node wrote `^IVG.AlgoCache` and `^NKG`, absent from
  `footprints/03.json`.
- `degree`: in a multigraph, a->b twice by Cypher and c->b once, each followed by degree_centrality. 7 steps, 72
  records, 7 actions. **F-1007 reproduced** (in-degrees sum to 1 for 2 parallel edges; the reply equals the as-built
  machine's sums).
- Both match as built; controls 3/3 each. Not driven: nkg, routes, walk.
- Lock log: 2,863 rebuild_nkg calls held `^IVG.NKGBuild` X only; with it held by a probe rebuild_nkg waited at
  `+325^Graph.KG.TraversalBuild.1` and finished 0.14 s after the release. Holds.

<a id="gaps"></a>
## 4. Gaps and remaining obligations (exact)

- 01: setup replayed only on an already set-up namespace and its success path (fresh-namespace setup and the F-0102
  failure paths not exercised); `ins_legacy` not replayed; lock-plan entries `^IVG.AdjW(g)` E:0 and `^IVG.NKGBuild` X
  not exercised by the one setup run.
- 02: F-0207's interleaving (count and kill of `GraphMode.Set` against a concurrent writer) not produced.
- 04: F-0401/F-C0401 (reader in flight across a writer rollback or erase) not produced; `adj_rebuild_txn` part 2 (two
  concurrent rebuilds, F-C0402) not produced.
- 06: `vec_queue` (F-0604, needs the IRIS worker ProcessBatch) and `vec_build_publish` not replayed.
- 11: `stats` (F-1102) and the concurrent cases of enable (F-1104) and adopt (F-1103) not produced.
- 15: blocked-access (FHIR server classes) and unrepresentable (reification has no machine).
- 16: TCP/WebSocket Bolt transports; 17: the server-side re-run (F-C1604); 18: snapcut's commit and delete paths.
- 07: bm25 Upgrade/Crash and the I5 race (F-0701); Leg Fusion/Retrieve. 08: Txn CallerRollback; a model-detectable
  reorder control for 08/readonly. 10: nkg, routes, walk; concurrent cache interleavings.
- 09: `planc`/`mode`/`used` replay and the lock log of `^IVG.CypherCompiled(h)` X:0: both need the native executor's
  job/sync mode, which compiles generated classes at run time (not triggered by this lane); F-0906's edge-only state
  needs DDL.
- Every replay: sequential traces of one scenario per family.
- Footprint-file gaps found by the frame check (files, not product): `footprints/03.json` delete_node omits
  `^IVG.Ledger`, `^NKG`, `^IVG.AlgoCache`; create_node omits `Graph_KG.ledger_stats` (a strict-mode refusal's counter);
  `footprints/18.json`'s lock plan omits the parent `^IVG.AdjW` S its erase_all takes.
- Erratum: `tr-locklog-13`'s observes text also describes the Final-isolation probe; that check's log is
  `tr-locklog-13b`'s.

## 5. Registered runs

`tr-oracle-selftest` (check, pass); `tr-replay-01..11, 15..18` (trace; pass, 15 blocked); `tr-controls-01..11, 16..18`
(control; pass, 08 fail as above); `tr-locklog-01, 02, 03, 04, 05, 06, 08, 10, 13, 13b, 18` (live, pass).
Follow-up (after commit e8a3ab67): `tr-replay-01-r2` (trace, pass), `tr-controls-01-r2` (control, pass),
`tr-controls-08-r2` (control, pass; supersedes `tr-controls-08`, which stays as recorded).
New finding: F-C0330 (`findings/audit/zz-trace-replay.json`).

## 6. Files

`trlib.py` (capture, replay, controls, footprint loader), `run.py` (capture/check runner), `common.py`,
`selftest_oracle.py`, `families_a.py`, `families_11.py`, `families_b.py`, `families_c.py` (transcribed machines),
`m01.py`..`m18.py` (scenarios, families, footprints, expected findings), `locklog.py`, `lockrun.py`, `lockcheck.py`
(lock logs), `summarize.py`, `make_logs.py`, `MATRIX-INPUT.json`. Raw: `$RUN_DIR/trace-replay/NN/<scenario>/`
(`trace.json`, `report.json`), `$RUN_DIR/trace-replay/locklog/*.json`, `$RUN_DIR/trace-replay/logs/`.
