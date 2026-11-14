# Correspondence of modules 11-14 (ledger, erasure, redaction, replay) to the models (playbook §§3.4-3.6)

Lane: correspondence. Pin `3eaa79cf` (tree `b098a6f4`), IRIS 2026.1 Community (Build 234U), namespace `AUDITC` (the
pin's classes as deployed by `initialize_schema`; the INT text read from `^ROUTINE` aligns line for line with the
pinned `.cls` files, see §2). Observation only: nothing compiled, no product file changed. Evidence grades follow
`CONVENTIONS.md`; a result about a model is reported as such.

**Headline.** There is no verifier for ObjectScript or Python, so no handler is *proved* to implement its model step
(§3.5-handlers and §3.4-statements stay **open**). The strongest correspondence implemented here is a
**trace refinement check**: an executable abstraction function α from the stored state (`^IVG.Ledger` subscripts and
`Graph_KG` rows) to the states of the participant contracts the proofs use (`proofs/src/ledger.rs`, `store.rs`), applied
to IRIS journal traces of real executions, requiring every operation to be the contract step its label names (or a
stutter), plus the checkable conjuncts of `biz_inv` after every operation. It is run together with the orchestrator's
spec-level step rules and frame check (`traces/conformance.py`, unchanged, namespace patched), under the IRIS line-by-line
monitor, so the exact source lines that no checked trace executed are listed (§3). Those lines, and every executed line
for inputs other than the traced ones, are what remains unchecked.

Results at a glance (registered runs in §8):
- 15 actions mapped (§2b); 13 trace-checked on the pin (commit, replay, genesis, re-enable/adoption, disable/strict,
  three erasure entry points, redaction batch/final/pause-resume, verify, readers), the redaction *start* only as
  built (the reviewed atomic locked Start has no counterpart), post-commit properties as a premise instance.
- Checked traces: 0 spec-rule violations, 0 frame excursions, faithful replay, 0 α contract-step violations
  (10/10 negative controls rejected); F-1201 reproduced 2/2 as a non-serializable pair of individually valid steps.
- Unchecked lines: 281 of 1,760 executable ObjectScript handler lines, 181 of 690 Python handler lines (§3).
- §3.6: frame holds on every execution (store granularity; 15 write statements never executed); keys hold on every
  trace (F-1801 restore breaks them); FK closed; integrity (stmt/tuple bijection, tombstone digests) holds except
  F-1201; capacity: 3 new findings, no corrupting outcome; row permutation: 1 intent-undecided finding.
- Lock plans: 18 probes, production behaviour matches the source plans everywhere (deferred release observed as lock
  count `1D`); the defects are the source plans' departures from the reviewed design (F-1114, F-1201, F-1302, F-1104).
- New findings: F-C1106, F-C1107, F-C1108, F-C1109, F-C1204 (§6).

## 1. Method

| Piece | What it does | Where |
|---|---|---|
| Scenario runner | runs operations one IRIS process each in AUDITC (emptied with `Eraser.EraseAll` + `Ledger.PurgeAll` first), takes a journal mark, row snapshots before/after each operation, the `^IVG.Ledger` snapshot before and after, the journal records since the mark and the storage map | `tools/scenarios.py` |
| `conf` | the exact scenario of `traces/conformance.py` (its `run()`, `NS`/`DB` patched to AUDITC; the file is not edited) | `scenarios.py conf` |
| `ext` | 32 operations reaching what `conf` does not (erasures and redactions through the public Python API): genesis over pre-enable rows, every changeset op kind, replay and every commit refusal, post-commit properties, a temporal edge, strict on/off, disable, a commit while disabled, a ledger-bypassing write and its adoption, `EraseEdges`, `EraseGraph`, a graph-target redaction, refusals of redact (`target_live`, another target's marker), a bounded run, a commit refused by `BlocksCommit`, readers and verify while marked, the resumed run, readers and verify after, `EraseAll` | `scenarios.py ext` |
| `f1201-1`, `f1201-2` | F-1201 world of `traces/f1201_native.py` ("other" seed: 4,000 statements in H; a probe holds `^IVG.AdjW("G")`; `EraseGraph(G)` races a commit into G), recorded as conformance traces | `scenarios.py f1201` |
| `lostack` | the lost-acknowledgement world of `traces/lost_ack.py` (client SIGKILLed at 0.3/0.8/3.0 s, retried with the same key) | `scenarios.py lostack` |
| Spec step rules + frame | `conformance.check_trace` (orchestrator's oracle); footprints for the extra operation kinds declared from source (`check_all.EXTRA_FOOTPRINT`); existing footprints unchanged | `tools/check_all.py` |
| Abstraction check | α and the per-operation contract-step check (per transaction, plus a serializability test, when operations overlap); invariants; negative controls (8 on `conf`, 2 more on `ext`) | `tools/abstraction.py`, `tools/abstraction_selftest.py` |
| Fast equivalent of the oracle | `conformance.check_trace` with its two quadratic loops indexed, for the 4,000-statement traces; identical reports on 16 trace/control variants | `tools/conformance_fast.py` |
| Keys / FK | journal-order checks of `head`, `stmtNext`, statement-id creation; `ledger_revisions` seq uniqueness and `idBySeq`/`revById` agreement; FK closure of final rows | `tools/check_all.py` |
| Line coverage | `%Monitor.System.LineByLine` (instance monitor, metric `RtnLine`, all processes, only while this lane holds the IRIS lock; counters cleared at each scenario's journal mark so setup is not counted) around each scenario; INT counts mapped to `.cls` lines. Python handlers: a stdlib line tracer over `iris_vector_graph/ledger/`, `_write_txn.py`, the erase entry points, same reset | `tools/monitor.py`, `tools/coverage.py`, `tools/cls_lines.py`, `tools/pycoverage.py` |
| Lock plans | 18 probes: a probe process holds the head lock or `^IVG.AdjW(key)`; the operation's process state (`%SYS.ProcessQuery`) and the lock table (`%SYS.LockQuery_List()`) are read while it is held; a journal mark at the release instant separates what the operation wrote before and after | `tools/lockplan.py` |
| Capacity | reference-length limits (read-only), 22 cases through commit / erase / redact / verify / genesis, and a row-permutation probe | `tools/capacity.py` |

## 2. The abstraction function α (stored state -> participant-contract state)

Defined at quiescent points (no transaction open: operation boundaries of the sequential traces).

| Model component (`proofs/src`) | Stored state at the pin | Notes |
|---|---|---|
| `LedgerS.hist[i][j]` | `^IVG.Ledger("rec", i+1, j+1)` for seq 1..`("head")` | content record `$LB(op, kind, id, attr, prior, new, graph, flags)` -> `Live(content)`; `$LB("redacted", digest, flags, op, kind)` -> `Tomb(c)` where `c` is the replaced record, identified by `digest = SHA-256(CanonicalRecord(c))` (checked); a revision of kind `redaction` (records `$LB("redact","revision",seq,"","N","S"_n,"","redaction")`) -> `[Audit{t: source.target_sha256, n: Σn}]` |
| `content(rec)` (vocab `Content{k, eff}`) | key and effect of the record | `create_node`/`delete_node` -> node key (graph "": the ledger's node records are graph-blind, LedgerApply.cls:232, :369); `add/remove_label` -> (label, id, L); `set/remove_prop` -> (prop, id, k); `create_rel`/`delete_rel` -> edge (g, s, p, o) from the tuple JSON; `set/remove_qual` -> (qual, g, s, p, o, k) through the statement id; `delete_node` also removes the node's labels and properties (DeleteNodeRows, LedgerApply.cls:354-371); `create_temporal_edge` -> no content (as `replay.py`) |
| `LedgerS.idem` | `^IVG.Ledger("idem", key) = $LB(seq, fingerprint)` | |
| `LedgerS.locked` | false at every quiescent point | the pin never holds `^IVG.Ledger("head")` across transactions; in the reviewed design the eraser would (HD-1201) |
| `LedgerS.enabled` | `("meta","state") = "enabled"` | |
| `LedgerS.marker` | `("redacting") = $LB(digest, graph, match, ms, actor)` -> target (graph, match) | |
| `LedgerS.mi, mj, mend` | **not represented** | the pin keeps the cursor in the call's locals (`tSeq`, `tOrd`, LedgerRedact.cls:214) and has no scan bound; reviewed design D-1/D-2 only |
| `LedgerS.count`, `tally` | `("redacting","n","records")`; per-revision counts `("redacting","revs",seq)` | the tally's contents are not stored; "every tallied record is of t" is checked per tombstone in the trace |
| `StoreS.rows` | governed rows: default-graph `nodes`, `rdf_labels`, `rdf_props` (reserved `id`, `__graph` excluded); `rdf_edges` of every graph and their qualifiers (temporal-marked rows excluded) | named-graph node rows written by `EnsureEndpoint` (LedgerApply.cls:97-110) have no record and are outside α (reported); this is the governed identity of HD-1401, not the product's graph-blind `verify()` (F-1401) |
| `StoreS.stmts` | `^IVG.Ledger("tuple", s, p, o, graphKey)` | `graphKey` `$c(1)` = default graph (GraphKey.ForLedger) |
| `StoreS.erasing` | an eraser transaction between its first row DELETE and its TCOMMIT | None at quiescent points |
| `RedS.procs[p]` | the frames of a running `LedgerRedact.Redact` call | process-local; not in storage |
| `^IVG.Ledger("stmt", id)` closed entries, `("redacting","stmt")`, `("redactedRev")`, `("idemRedacted")`, `ledger_revisions` free text | not in the proofs crate (PROOFS.md §11); the original L2 (`playbook-uplift/proofs/src/l2.rs`) has `meta`, `idem_red`, `red_rev` | checked here as trace properties: Decision 2 clearing, key movement to `idemRedacted` |

Contract steps required per operation (`abstraction.step`): commit = `Ledger.Commit` (`hist ++ [lives(records)]`, head+1,
key bound to the new seq, pre: enabled, key free, not `blocks_commit`) **and** `Store.Apply` (rows after = the new
records folded onto the rows before; for a genesis: rows unchanged and `replay(hist) = α(rows)`; for an adoption: rows
unchanged and `replay(hist) = α(rows)` after); replay and every refusal = stutter of both; erase = `Store.EraseRows` +
`EraseIndex` (rows after = `outside(rows, t)` for the eraser's own target predicate, tuple entries of `t` removed,
history unchanged); redaction batch = `Ledger.Batch` per tombstone (`Live(c) -> Tomb(c)`, digest, op/kind kept, `c` a
record of the target, not live, count and marker); Final = `Ledger.Audit` (one revision of `redact` records whose
counts sum to the run's count, marker removed, target digest, live tuple entries unchanged); SetEnabled; verify/readers
= stutter; a ledger-bypassing write = `Store.Apply` outside the ledger (premise P-C02, reported, not a Biz step).
Invariants after every operation: `ledger_inv`, stmt/tuple bijection (both directions), `stmts_ok`, `inv_stmts`
(ERS-I3), `inv_mark`, and `inv_replay` (differences reported and classified: pending targets, unrecorded writes).

## 2b. Per-action correspondence (handlers, reads/writes, transactions, locks, status path, α, grade)

Grades: **trace-checked** = a registered journal trace of the pin ran the action and both the spec step rules
(`conformance.py`) and the α contract-step check accepted it (or, where stated, found the known defect);
**source-inspected only** = read at the pin, no checked trace; **not represented** = the model has the action and the pin
has no counterpart (or the converse). Line counts are of the action's handler methods (a method shared by several
actions is counted in each); "unchecked" lines are executable lines no checked trace executed.

<!-- BEGIN ACTIONS (generated by tools/build.py) -->
### commit

- **Model**: L2 Commit{cs,key}; Ledger.Commit + Store.Apply (protocol_sys: one Biz commit step)
- **Handlers**: iris_vector_graph/ledger/client.py:381-400 commit; iris_vector_graph/ledger/client.py:402-443 _commit; iris_vector_graph/ledger/client.py:322-379 _send_changeset; iris_src/src/Graph/KG/Ledger.cls:397-415 Commit; iris_src/src/Graph/KG/Ledger.cls:419-528 CommitInTxn; iris_src/src/Graph/KG/Ledger.cls:532-567 WriteRevision; iris_src/src/Graph/KG/LedgerApply.cls:18-48 ApplyAll and the op handlers iris_src/src/Graph/KG/LedgerApply.cls:215-693; iris_src/src/Graph/KG/LedgerRedact.cls:258-269 BlocksCommit; iris_src/src/Graph/KG/LedgerStats.cls:65-88 Bump; iris_vector_graph/_write_txn.py:102-277 WriteTxn/write_txn (caller transaction open); iris_src/src/Graph/KG/Txn.cls:19-58
- **Reads**: globals ^||IVG.LedgerStage(token) (staged payload, process-private), ^IVG.Ledger("meta","state"|"maxOps"), ^IVG.Ledger("head"), ^IVG.Ledger("idBySeq"), ^IVG.Ledger("revById"), ^IVG.Ledger("idem"), ^IVG.Ledger("idemRedacted"), ^IVG.Ledger("redacting") (BlocksCommit), ^IVG.Ledger("stmt"), ^IVG.Ledger("tuple"), ^IVG.Ledger("stmtNext"), ^IVG.Ledger("redacting","stmt") and ^||IVG.RedactStmt via Matches, ^KG("out") (when the functional index is absent); tables nodes (NodeExists, graph-blind), rdf_labels, rdf_props, rdf_edges (FindEdge), rdf_reifications, ledger_revisions (RevisionObj), ledger_stats
- **Writes** (validated (conformance FOOTPRINT['commit']; frame check over every trace)): globals ^IVG.Ledger("rec",seq,ord), ("head"), ("revById"), ("idBySeq"), ("idem"), ("stmtNext"), ("stmt",id), ("tuple",s,p,o,gk), ^KG out/in/gen/__version via Adjacency (functional index RowPut/RowRemove or Put/Remove/Reweight), ^IVG.AdjNoLock(g) ($Increment, survives rollback) when AdjW is not granted, ^NKG (Put interns when built), ^KG temporal subtrees (create_temporal_edge); tables nodes, rdf_labels, rdf_props, rdf_edges, rdf_reifications (delete cascade), kg_NodeEmbeddings(_optimized) (DeleteNodeRows), ledger_revisions (+ ^Graph.KG.LedgerRevisionD/I), ledger_stats (WriteRevision; Bump after the transaction)
- **Transaction**: TSTART Ledger.cls:402 opens one level (nested under the caller's when $TLEVEL>0: client.py:395-400 write_txn -> Txn.Begin Txn.cls:19-31 opens IVG's level first); CommitInTxn runs inside it; :405 TCOMMIT when pOk else TROLLBACK 1 (a refusal after partial apply takes back only this level); catch :406-411 rolls back every level above entry; Bump :413 in its own transaction after (LedgerStats.cls:72-83); post-commit properties (client.py:445-487) in a further WriteTxn level, after the commit's transaction
- **Locks**: ^IVG.Ledger("head") exclusive, 30 s (Ledger.cls:21 LOCKTIMEOUT); taken Ledger.cls:440, after TSTART :402 and the payload parse :422-438; released Lock - Ledger.cls:404 before TCOMMIT/TROLLBACK :405 -> deferred to the outermost transaction end (contract Locks: deferral; doc :390-396); ^IVG.AdjW(graphKey) shared #"S", 5 s; a row writer then writes without it and SETs ^IVG.AdjNoLock(graphKey) (Adjacency.cls:61-73); taken per edge add/remove inside the transaction: Adjacency.Put :86, Remove :150, RowUpdate :523 (functional index Graph.KG.AdjIndex); released Lock - :93/:158 inside the transaction -> deferred to its end
- **Status / decoder**: CommitInTxn answers Err JSON (Ledger.cls:61-70): lock_timeout :443, not_enabled :446, disabled :449, idempotency_conflict :464, idempotency_redacted :471, unknown_head :480, stale_head :484, empty :492, too_large :496 (ErrLimit), failed_op (ApplyAll :26/:45, op_index), redaction_in_progress (BlocksCommit LedgerRedact.cls:265), inconsistent (WriteRevision :555/:564, catch :409); client.py:405-416 -> errors.py:175-199 from_commit_error -> _WIRE_MAP :156-172 (failed_op with reason "node_not_found: '" -> NodeNotFoundError); transport exceptions -> inconsistent (client.py:352-357); decoder map checked by tools/decoder_map_check.py
- **α**: hist' = hist ++ [lives(new records)], head+1, idem' = idem + {key: seq}; Store.Apply: rows' = fold(rows, new records), stmts' = stmt_recs(stmts, records)
- **Grade**: **trace-checked** — spec step rules + frame + alpha (Ledger.Commit and Store.Apply: rows after = records folded onto rows before) on every committed commit of the traces (run:corr-trace-conf, run:corr-trace-ext, run:corr-trace-lostack, run:trace-conformance-ledger)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 612/685 executable lines exercised by the checked traces; unchecked lines: 73 (listed per method in correspondence.json)

### replay

- **Model**: Ledger.Replay{key} (protocol_sys: a replay changes nothing, HD-1305); L2 retry rule
- **Handlers**: iris_src/src/Graph/KG/Ledger.cls:455-465 idempotency branch of CommitInTxn; iris_src/src/Graph/KG/Ledger.cls:468-473 idemRedacted refusal; iris_vector_graph/ledger/client.py:418-443 (a replayed result still applies post-commit properties :430-435, F-1306)
- **Reads**: globals ^IVG.Ledger("idem",key), ("idemRedacted", sha256(key)); tables ledger_revisions
- **Writes** (validated (lostack, ext commit-replay)): globals -; tables ledger_stats (Bump replays_idem), rdf_props (post-commit properties of the changeset, again)
- **Transaction**: the commit's level; pOk stays 0 so :405 TROLLBACK 1 of an empty level
- **Locks**: ^IVG.Ledger("head") exclusive, 30 s (Ledger.cls:21 LOCKTIMEOUT); taken Ledger.cls:440 (the replay is answered under the head lock); released as commit
- **Status / decoder**: replayed=true in the revision response (Ledger.cls:110-120) -> CommitResult.replayed; a different fingerprint -> idempotency_conflict -> IdempotencyConflictError; a redacted key -> IdempotencyRedactedError
- **α**: stutter of Ledger and Store (except post-commit properties: Store.Apply outside the ledger)
- **Grade**: **trace-checked** — Ledger.Replay is a stutter of ledger and store; F-1306 (replay re-applies post-commit properties) is outside these traces (live/model evidence in findings/audit/13.json) (run:corr-trace-ext, run:corr-trace-lostack)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 68/83 executable lines exercised by the checked traces; unchecked lines: 15 (listed per method in correspondence.json)

### enable-genesis

- **Model**: L2 SetEnabled{true} from never-enabled + the genesis Commit (seq 1); Ledger.SetEnabled + Commit
- **Handlers**: iris_vector_graph/ledger/client.py:281-297 enable; iris_src/src/Graph/KG/Ledger.cls:252-329 Enable; iris_src/src/Graph/KG/LedgerGenesis.cls:14-60 Capture; iris_src/src/Graph/KG/Ledger.cls:532-567 WriteRevision
- **Reads**: globals ^IVG.Ledger("meta","state") (unlocked, :254); tables nodes, rdf_labels, rdf_props, rdf_edges (ORDER BY)
- **Writes** (validated (ext enable-genesis)): globals ^IVG.Ledger("meta",*), ("head")=0 then 1, ("stmtNext")=1, ("stmt"), ("tuple"), ("rec",1,*), ("revById"), ("idBySeq"); tables ledger_revisions, ledger_stats
- **Transaction**: refuses $TLEVEL>0 (:261); TSTART :265; TCOMMIT :319 / TROLLBACK 1 :268/:301/:307/:315; catch :323-327
- **Locks**: ^IVG.Ledger("head") exclusive, 30 s (Ledger.cls:21 LOCKTIMEOUT); taken Ledger.cls:266 after the unlocked state read :254 (F-1104); released Lock - :318 (:300/:306/:314 on errors) before TCOMMIT -> at TCOMMIT
- **Status / decoder**: Err JSON lock_timeout :269, transaction_open :261, inconsistent; client raises from_commit_error
- **α**: enabled' = true; hist' = [lives(genesis records)] with replay(hist') = alpha(rows); rows unchanged
- **Grade**: **trace-checked** — genesis over pre-enable rows: rows unchanged and replay(hist) = alpha(rows) (run:corr-trace-ext)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 110/132 executable lines exercised by the checked traces; unchecked lines: 22 (listed per method in correspondence.json)

### reenable-adoption

- **Model**: L2 SetEnabled{true} from disabled, then an adoption Commit of the unrecorded divergence
- **Handlers**: iris_src/src/Graph/KG/Ledger.cls:271-287 Enable (disabled branch); iris_vector_graph/ledger/client.py:292-296 verify(adopt=True); iris_vector_graph/ledger/replay.py:806-859 verify; iris_src/src/Graph/KG/LedgerGenesis.cls:82-129 Adopt (CommitInTxn :505-506)
- **Reads**: globals ^IVG.Ledger("tuple"), ("stmt"); tables the content tables (read_canonical)
- **Writes** (validated (ext reenable, verify-adopt)): globals ^IVG.Ledger("meta","state"), adoption revision as commit; tables ledger_stats, ledger_revisions
- **Transaction**: Enable's own; the adoption is a separate commit transaction (F-1103: not tied to the compared head)
- **Locks**: ^IVG.Ledger("head") exclusive, 30 s (Ledger.cls:21 LOCKTIMEOUT); taken Enable :266; the adoption commit :440; released as commit
- **Status / decoder**: as commit
- **α**: SetEnabled; then Commit whose records make replay(hist) = alpha(rows)
- **Grade**: **trace-checked** — adoption: rows unchanged, replay(hist) = alpha(rows) after; the race F-1103 is not in the trace (run:corr-trace-ext)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 129/177 executable lines exercised by the checked traces; unchecked lines: 48 (listed per method in correspondence.json)

### disable-strict

- **Model**: L2 SetEnabled{false}; Ledger.SetEnabled (strict: not in the model)
- **Handlers**: iris_vector_graph/ledger/client.py:299-309; iris_src/src/Graph/KG/Ledger.cls:331-358 Disable; iris_src/src/Graph/KG/Ledger.cls:360-383 SetStrict
- **Reads**: globals ^IVG.Ledger("meta","state"); tables -
- **Writes** (validated (ext strict-on/off, disable)): globals ^IVG.Ledger("meta","state"|"strict"); tables ledger_stats
- **Transaction**: own TSTART :342/:365, TCOMMIT :351/:374; nested in the caller's level when one is open
- **Locks**: none: no head lock: a commit that already passed its state check (:445-450) commits after a concurrent Disable
- **Status / decoder**: Err inconsistent -> LedgerInconsistencyError
- **α**: enabled' = false; nothing else
- **Grade**: **trace-checked** — SetEnabled only; strict mode is not in the model (run:corr-trace-ext)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 27/37 executable lines exercised by the checked traces; unchecked lines: 10 (listed per method in correspondence.json)

### erase-graph

- **Model**: Store.EraseRows{t} + Store.EraseIndex{t} in one transaction (L2 Erase{t}); reviewed protocol: RL::Lock .. RL::Unlock around them (HD-1201)
- **Handlers**: iris_vector_graph/_engine/nodes_edges.py:1473-1527 erase_graph; iris_src/src/Graph/KG/Eraser.cls:47-305 EraseGraph; iris_src/src/Graph/KG/Eraser.cls:1117-1144 EraseLedgerFor; iris_src/src/Graph/KG/Adjacency.cls:428-447 RemoveGraph; iris_src/src/Graph/KG/Eraser.cls:1038-1053 InvalidateDerived
- **Reads**: globals ^IVG.Ledger("stmt") (every entry, dirty, :1121-1131), ^KG("out",g) (GraphEdgesInNKG), ^NKG("$NI"); tables embedding_registry, INFORMATION_SCHEMA.TABLES, rdf_edges, nodes
- **Writes** (validated (conformance FOOTPRINT['erase'])): globals ^IVG.Ledger("stmt",id), ("tuple",...) of the graph, ^KG out/in/gen/degc/degw/prop/label/deg2p*, ^IVG.GraphMode(g), ^IVG.AlgoCache, ^NKG (DropNKG), ^IVG.AdjNoLock(g) (killed), temporal subtrees (TemporalIndex.EraseGraph); tables rdf_labels, rdf_props, docs, kg_NodeEmbeddings(_optimized), routed kg_emb_*/kg_eemb_*, FHIR side tables, rdf_reifications, kg_EdgeEmbeddings, rdf_edges, nodes, (after commit) DROP TABLE routes, embedding_registry rows
- **Transaction**: TSTART :56; TCOMMIT :258; catch :259-261 rolls back every level above entry and rethrows; DDL after the commit :282-299
- **Locks**: ^IVG.Ledger("head"): NOT taken (as built; F-1114, F-1201); the reviewed design holds it from the row deletes to EraseLedgerFor; ^IVG.AdjW(graphKey) shared #"S", 5 s; a row writer then writes without it and SETs ^IVG.AdjNoLock(graphKey) (Adjacency.cls:61-73); taken rdf_edges DELETE :217 (functional index RowRemove -> Remove -> WriterLock) and RemoveGraph :431 (Adjacency.cls:431, refuses after 5 s -> $$$ThrowOnError :235); released Lock - Adjacency.cls:445 inside the transaction -> at TCOMMIT :258
- **Status / decoder**: throws (SqlErr, Eraser.cls:1356-1359) -> Native API exception -> Python raises (nodes_edges.py:1514-1516)
- **α**: rows' = outside(rows, graph g); stmts' = stmts minus g's; hist unchanged
- **Grade**: **trace-checked** — sequential: Store.EraseRows+EraseIndex; concurrent (corr-trace-f1201): not a step of the reviewed protocol (F-1201) (run:corr-trace-ext)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 132/195 executable lines exercised by the checked traces; unchecked lines: 63 (listed per method in correspondence.json)

### erase-nodes

- **Model**: Store.EraseRows + EraseIndex for a prefix target (graph g, ids starting prefix)
- **Handlers**: iris_vector_graph/_engine/nodes_edges.py:1529-1563 delete_nodes_by_prefix; iris_vector_graph/stores/iris_sql_store.py:1420-1450; iris_src/src/Graph/KG/Eraser.cls:322-351 EraseNodes; iris_src/src/Graph/KG/Eraser.cls:467-636 EraseIdSet; iris_src/src/Graph/KG/Eraser.cls:641-680 EraseEdgeRow; iris_src/src/Graph/KG/Adjacency.cls:396-426 RemoveNode; iris_src/src/Graph/KG/Eraser.cls:372-388 EraseNodeIds (same body)
- **Reads**: globals ^IVG.Ledger("tuple",s,p,o,gk) (EraseEdgeRow :673), ^KG("out"/"in", g, id), ^NKG("$NI"); tables nodes (prefix cursor, outside the transaction :333-348), rdf_edges (both directions)
- **Writes** (validated (conf2, conf, ext)): globals ^IVG.Ledger("stmt",id), ("tuple",...) per erased edge (:672-677), ^KG adjacency/prop/label, ^||IVG.EraseIds (process-private), ^NKG, ^IVG.AlgoCache, version (InvalidateDerived); tables rdf_reifications, kg_EdgeEmbeddings, edge routes, rdf_edges, rdf_labels, rdf_props, docs, kg_NodeEmbeddings(_optimized), node routes, FHIR node rows, nodes
- **Transaction**: ids collected before the transaction (EraseNodes :331-348); EraseIdSet TSTART :484, TCOMMIT :628, catch :629-633
- **Locks**: ^IVG.Ledger("head"): NOT taken (F-1114); ^IVG.AdjW(graphKey) shared #"S", 5 s; a row writer then writes without it and SETs ^IVG.AdjNoLock(graphKey) (Adjacency.cls:61-73); taken EraseEdgeRow's DELETE :663 (functional index) and Adjacency.Remove :668; RemoveNode -> RemoveSource :354; released deferred to TCOMMIT :628
- **Status / decoder**: throws; EraseNodes refuses an empty prefix :324-326
- **α**: rows' = outside(rows, prefix target)
- **Grade**: **trace-checked** (run:corr-trace-conf, run:corr-trace-ext, run:trace-conformance-ledger)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 195/256 executable lines exercised by the checked traces; unchecked lines: 61 (listed per method in correspondence.json)

### erase-edges-all

- **Model**: Store.EraseRows/EraseIndex for an edge set (EraseEdges) or for everything (EraseAll)
- **Handlers**: iris_src/src/Graph/KG/Eraser.cls:395-463 EraseEdges; iris_src/src/Graph/KG/Eraser.cls:709-845 EraseAll; iris_src/src/Graph/KG/Adjacency.cls:452-472 RemoveAll
- **Reads**: globals ^KG("out"); tables rdf_edges, embedding_registry
- **Writes** (validated (ext erase-edges, erase-all)): globals ^IVG.Ledger("stmt"), ("tuple") (EraseAll kills both subtrees :810-811), ^KG, ^NKG, ^ArnoKG, ^IVG.GraphMode, ^IVG.TemporalStructural, ^IVG.AlgoCache; tables every content table
- **Transaction**: TSTART :414 / :714; TCOMMIT :457 / :814
- **Locks**: ^IVG.Ledger("head"): NOT taken; ^IVG.AdjW(graphKey) shared #"S", 5 s; a row writer then writes without it and SETs ^IVG.AdjNoLock(graphKey) (Adjacency.cls:61-73); taken Remove / RemoveAll :455 (parent ^IVG.AdjW#S); released deferred to TCOMMIT
- **Status / decoder**: throws
- **α**: rows' = outside(rows, t)
- **Grade**: **trace-checked** (run:corr-trace-ext)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 118/132 executable lines exercised by the checked traces; unchecked lines: 14 (listed per method in correspondence.json)

### redact-start

- **Model**: L2 Start{p,t,fresh}; reviewed RL Start = Redactor.Open/Attach + Ledger.Mark in one locked step (HD-1301)
- **Handlers**: iris_vector_graph/ledger/client.py:633-680 redact; iris_src/src/Graph/KG/LedgerRedact.cls:185-214 Redact opening (state :188-190, marker :202-205, LiveRows :206-210, PrePass :212, cursor :214); iris_src/src/Graph/KG/LedgerRedact.cls:149-178 LiveRows; iris_src/src/Graph/KG/LedgerRedact.cls:116-141 PrePass; iris_src/src/Graph/KG/LedgerRedact.cls:322-324 BatchInLock writes the marker with the first tombstone
- **Reads**: globals ^IVG.Ledger("meta","state"), ("redacting"), ("rec") (PrePass); tables nodes, rdf_labels, rdf_props, rdf_edges (COUNT, READ UNCOMMITTED)
- **Writes** (validated: no journaled write before the first batch): globals ^||IVG.RedactStmt (process-private, not journaled); tables -
- **Transaction**: none: the opening checks run outside any transaction and without the lock
- **Locks**: none: the pin has no Start transaction: the opening reads are unlocked and the marker is written by the first tombstoning batch (F-1302, F-1303); not the reviewed design's atomic Mark
- **Status / decoder**: Err JSON transaction_open :187, not_enabled :189, disabled :190, invalid_target :191/:195, redaction_in_progress :204, inconsistent :207, target_live :209 -> client.py:678-679 from_commit_error -> RedactionTargetLiveError, RedactionInProgressError, InvalidRedactionTargetError
- **α**: Redactor.Open + Attach{i=0,j=0} (cursor at the first record, :214); no Ledger step until the first tombstone, which also performs Mark (as-built Ledger.Batch sets the marker if none)
- **Grade**: **trace-checked (as built; the reviewed atomic Start is not represented)** — the pin has no Start transaction: unlocked opening reads (no journaled write) and the marker written by the first batch; the reviewed design's locked Mark has no counterpart (F-1302, F-1303) (run:corr-trace-conf, run:corr-trace-ext)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 86/90 executable lines exercised by the checked traces; unchecked lines: 4 (listed per method in correspondence.json)

### redact-batch

- **Model**: L2 Scan{p} (one record); Ledger.Batch{i,j,t,tomb,ni,nj} (+ Redactor.Advance)
- **Handlers**: iris_src/src/Graph/KG/LedgerRedact.cls:216-226 the batch loop; iris_src/src/Graph/KG/LedgerRedact.cls:275-300 Batch; iris_src/src/Graph/KG/LedgerRedact.cls:302-330 BatchInLock; iris_src/src/Graph/KG/LedgerRedact.cls:333-347 Tombstone; iris_src/src/Graph/KG/LedgerRedact.cls:353-378 ClearRevision; iris_src/src/Graph/KG/LedgerRedact.cls:89-112 Matches; iris_src/src/Graph/KG/LedgerRevision.cls:87-101 RejectUpdate trigger exemption; iris_src/src/Graph/KG/Ledger.cls:572-605 CanonicalRecord
- **Reads**: globals ^IVG.Ledger("rec"), ("redacting"), ("redacting","stmt"), ^||IVG.RedactStmt, ("stmt"), ("redactedRev"); tables ledger_revisions (idempotency_key)
- **Writes** (validated (conformance FOOTPRINT['redact'])): globals ^IVG.Ledger("rec",seq,ord) := $LB("redacted",digest,flags,op,kind), ("redacting") (first), ("redacting","stmt",id), ("redacting","revs",seq), ("redacting","n",*), ("redactedRev",seq), ("idem",key) killed, ("idemRedacted",sha256(key)); tables ledger_revisions (message, source, correlation_id, idempotency_key := NULL)
- **Transaction**: TSTART :281; TCOMMIT :288 or TROLLBACK 1 :284/:288; catch :291-296 (one level)
- **Locks**: ^IVG.Ledger("head") exclusive, 30 s (Ledger.cls:21 LOCKTIMEOUT); taken LedgerRedact.cls:282 after TSTART; released Lock - :289 AFTER TCOMMIT :288 (Redact refuses $TLEVEL>0, so the unlock is immediate)
- **Status / decoder**: Err lock_timeout :285, disabled :305, inconsistent (:295, ClearRevision :356/:357/:375) -> Redact :228 returns it -> from_commit_error
- **α**: per tombstone Live(c) -> Tomb(c), c a record of t and not live, digest = SHA-256(CanonicalRecord); count += 1, tally += c, marker := marker or t
- **Grade**: **trace-checked** — every tombstone's digest recomputed = SHA-256(CanonicalRecord) of the record it replaced (run:corr-trace-conf, run:corr-trace-ext, run:trace-conformance-ledger)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 102/126 executable lines exercised by the checked traces; unchecked lines: 24 (listed per method in correspondence.json)

### redact-final

- **Model**: L2 Final{p,t,ok}; Ledger.Audit{t} + Redactor.Finish (reviewed: under its own marker, after a re-check)
- **Handlers**: iris_src/src/Graph/KG/LedgerRedact.cls:230-234 Redact; iris_src/src/Graph/KG/LedgerRedact.cls:384-407 Final; iris_src/src/Graph/KG/LedgerRedact.cls:409-442 FinalInLock; iris_src/src/Graph/KG/LedgerRedact.cls:446-471 DropStatements; iris_src/src/Graph/KG/LedgerRedact.cls:473-480 ReadCounts; iris_src/src/Graph/KG/LedgerRedact.cls:482-511 Receipt; iris_src/src/Graph/KG/Ledger.cls:532-567 WriteRevision (kind redaction)
- **Reads**: globals ^IVG.Ledger("redacting",*), ("stmt"), ("tuple"), ("head"), ("idBySeq"); tables content tables (LiveRows re-check under the lock)
- **Writes** (validated): globals ^IVG.Ledger("stmt",id) and ("tuple") of the target killed, redaction revision ("rec",head+1,*) ("head") ("revById") ("idBySeq"), ("redacting") killed; tables ledger_revisions, ledger_stats
- **Transaction**: TSTART :389; TCOMMIT :396 or TROLLBACK 1; catch :399-403
- **Locks**: ^IVG.Ledger("head") exclusive, 30 s (Ledger.cls:21 LOCKTIMEOUT); taken LedgerRedact.cls:390; released Lock - :397 after TCOMMIT (immediate)
- **Status / decoder**: target_live :415, disabled :411, inconsistent :414, lock_timeout :393
- **α**: hist' = hist ++ [Audit{t, n=count}] when marker and count>0; marker None; count 0; stmts unchanged (an erased target has no live tuple entry left); FinalInLock removes whichever marker exists (:439, F-1303)
- **Grade**: **trace-checked** (run:corr-trace-conf, run:corr-trace-ext)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 155/164 executable lines exercised by the checked traces; unchecked lines: 9 (listed per method in correspondence.json)

### redact-stop-resume

- **Model**: Redactor.Stop / Open again; reviewed: resume at the marker's cursor (D-1)
- **Handlers**: iris_src/src/Graph/KG/LedgerRedact.cls:217 max_batches exit; iris_src/src/Graph/KG/LedgerRedact.cls:236 ReadCounts for a paused run; iris_src/src/Graph/KG/LedgerRedact.cls:202-205 own marker passes; iris_src/src/Graph/KG/LedgerRedact.cls:214 the cursor restarts at the first record (F-C1303)
- **Reads**: globals ^IVG.Ledger("redacting"); tables -
- **Writes** (n/a): globals -; tables -
- **Transaction**: a stop between batches loses only the process's cursor; a killed process's open batch is rolled back by IRIS (contract: Process stop)
- **Locks**: head lock of the interrupted batch: released by process stop (contract)
- **Status / decoder**: receipt complete=false
- **α**: Redactor.Stop; Ledger unchanged; resume = Open + Attach{0,0} at the pin (rewind; progress-only control in proofs)
- **Grade**: **trace-checked (pause and resume); process-kill stop not represented here** — a killed batch is the IRIS contract's Process stop clause (env-contract-r2); the rescanning resume is F-C1303 (run:corr-trace-conf, run:corr-trace-ext)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 71/72 executable lines exercised by the checked traces; unchecked lines: 1 (listed per method in correspondence.json)

### verify

- **Model**: Reader step (stutter); the verify verdict of M3-readers
- **Handlers**: iris_vector_graph/ledger/client.py:741-744; iris_vector_graph/ledger/replay.py:806-859 verify; iris_vector_graph/ledger/replay.py:588-642 read_canonical; iris_vector_graph/ledger/replay.py:645-698 compare; iris_src/src/Graph/KG/Ledger.cls:158-164 Head; iris_src/src/Graph/KG/LedgerRedact.cls:242-254 InProgress; iris_src/src/Graph/KG/Ledger.cls:176-179 StmtForTuple; iris_src/src/Graph/KG/Ledger.cls:613-652 Records* (SQL ledger_records); iris_src/src/Graph/KG/Ledger.cls:192-210 RecordVerify
- **Reads**: globals ^IVG.Ledger("rec"), ("head"), ("redacting"), ("tuple"); tables nodes, rdf_labels, rdf_props, rdf_edges (graph-blind, F-1401), ledger_revisions
- **Writes** (validated (conformance FOOTPRINT['verify'])): globals -; tables ledger_stats (RecordVerify, own transaction :197-204)
- **Transaction**: no transaction around the reads (records and tables are read at different moments, P-1401); RecordVerify TSTART :197 / TCOMMIT :204
- **Locks**: none: the marker is checked once before reading (F-1402)
- **Status / decoder**: VerificationReport.result equal | diverges | redaction_in_progress
- **α**: stutter
- **Grade**: **trace-checked (stutter and frame)** — the verdict itself is graph-blind (F-1401); verify racing commits (P-1401) not represented (run:corr-trace-conf, run:corr-trace-ext, run:corr-trace-lostack)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 83/85 executable lines exercised by the checked traces; unchecked lines: 2 (listed per method in correspondence.json)

### readers

- **Model**: Reader steps (get_revision, diff, reconstruct, export, history): stutter; RPL-I1
- **Handlers**: iris_vector_graph/ledger/client.py:687-739; iris_vector_graph/ledger/client.py:585-629 history; iris_vector_graph/ledger/replay.py:252-269 iter_records_sql; iris_vector_graph/ledger/replay.py:544-566 reconstruct; iris_src/src/Graph/KG/Ledger.cls:613-652 RecordsExecute/Fetch/Close; iris_src/src/Graph/KG/Ledger.cls:166-174 SeqOf
- **Reads**: globals ^IVG.Ledger("rec"), ("revById"), ("redacting"); tables ledger_revisions
- **Writes** (validated: no writes (ext readers ops)): globals -; tables -
- **Transaction**: none
- **Locks**: none: history() does not refuse while a run is in progress
- **Status / decoder**: RedactionInProgressError while marked (client.py:687-693); UnknownRevisionError; ReconstructionTooLargeError (replay.py:557)
- **α**: stutter
- **Grade**: **trace-checked (stutter; refusal while marked)** — the check-once race F-1402 needs concurrency and is not represented in these traces (run:corr-trace-ext)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 63/72 executable lines exercised by the checked traces; unchecked lines: 9 (listed per method in correspondence.json)

### post-commit-properties

- **Model**: outside the ledger: Store.Apply of direct writes (premise P-C02); M3-retry's separate property write
- **Handlers**: iris_vector_graph/ledger/client.py:430-435; iris_vector_graph/ledger/client.py:445-487 _apply_post_commit_properties; iris_vector_graph/_write_txn.py:102-272 WriteTxn
- **Reads**: globals -; tables -
- **Writes** (validated (ext commit-post-commit-property)): globals -; tables rdf_props (DELETE + INSERT, default graph)
- **Transaction**: its own WriteTxn level after the commit's transaction (Txn_Begin/End/Undo)
- **Locks**: none: no head lock; not serialized with erasure (F-1306 race m3-as-built-pcp-race)
- **Status / decoder**: CommitResult.post_commit_applied / post_commit_error (never raised)
- **α**: Store.Apply outside the ledger: not a Biz step (P-C02)
- **Grade**: **trace-checked as a premise instance (not a Biz step)** — a Store.Apply outside the ledger: premise P-C02 is violated by design (F-1101) (run:corr-trace-ext)
- **Lines** (ObjectScript handler methods; Python handler lines in §3): 8/15 executable lines exercised by the checked traces; unchecked lines: 7 (listed per method in correspondence.json)

<!-- END ACTIONS -->

## 3. Line coverage: the unchecked lines (deliverable 2)

The IRIS line-by-line monitor **was usable** (`%Monitor.System.LineByLine.Start(rtns, $lb("RtnLine"), "")`, all
processes, `Clear()` at each journal mark, `Stop()` after collection; it is an instance monitor, nothing compiled).
Counts are per INT line of the class routine; `tools/coverage.py` maps them to the pinned `.cls` (all 2,274 executable
lines of the 11 classes map: `corr-int-alignment`). A line is **exercised** when a checked trace (`corr-trace-conf`,
`corr-trace-ext`, `corr-trace-f1201` (2 trials), `corr-trace-lostack`) executed it inside its journal window; every
operation of those windows went through the spec step rules, the frame check and the α contract-step check.

Totals over the handler methods of §2b (each method once): **ObjectScript 112 methods, 1,760 executable lines,
1,479 exercised, 281 unchecked**; **Python handler functions 690 executable lines, 509 exercised, 181 unchecked**
(`corr-line-coverage`). Per action (a shared method counts in each action that uses it):

| Action | Executable | Exercised | Unchecked |
|---|---|---|---|
| commit | 685 | 612 | 73 |
| replay | 83 | 68 | 15 |
| enable-genesis | 132 | 110 | 22 |
| reenable-adoption | 177 | 129 | 48 |
| disable-strict | 37 | 27 | 10 |
| erase-graph | 195 | 132 | 63 |
| erase-nodes | 256 | 195 | 61 |
| erase-edges-all | 132 | 118 | 14 |
| redact-start | 90 | 86 | 4 |
| redact-batch | 126 | 102 | 24 |
| redact-final | 164 | 155 | 9 |
| redact-stop-resume | 72 | 71 | 1 |
| verify | 85 | 83 | 2 |
| readers | 72 | 63 | 9 |
| post-commit-properties (ObjectScript part: Txn) | 15 | 8 | 7 |

What the unchecked lines are (kinds, from the list below): lock-timeout and catch/rollback branches of every
transaction (Commit :407-410, CommitInTxn :442-443, Enable, Disable, SetStrict, Batch, Final, RecordVerify, Bump,
Txn.Undo); the staged (>1,000,000-character) payload path (CommitInTxn :427-435) and `LargeOut`; `too_large`
(ErrLimit) and `idempotency_redacted` (:469-471) refusals; the redacted-tombstone branch of CanonicalRecord
(:579-587, reached only when a reader canonicalizes a tombstone); reification cascades (DeleteRelInternal :663-668);
statements referenced by `stmt_id` and tuple refs to unrecorded edges (ResolveRef); the adoption's delete_rel and
qualifier-by-tuple branches (Adopt :108-123); named-graph prefix targets (LiveRows :164); unattributed qualifier
records (BatchInLock :318-319, Matches :106-107); DropStatements' tuple kill (:465, never needed after a correct
erasure); routed embedding tables, FHIR side tables and ^NKG-built paths of the Eraser; `EraseNodeIds` (the
`delete_nodes` entry point, not traced); the AdjNoLock fallback of `WriterLock` (:67-72, exercised only by the lock
probes, which are not trace-checked); in Python, the chunked transport, the nested-transaction path of
`WriteTxn.native/commit/rollback`, `export_reconstruction`, history filters and parts of `compare`/`_adoption_items`.

| Handler (ObjectScript) | Lines | Exec. lines | Exercised | Unchecked lines (pinned .cls line numbers) |
|---|---|---|---|---|
| Adjacency.Remove | 148-167 | 13 | 12 | 163 |
| Adjacency.RemoveAll | 453-472 | 15 | 14 | 457 |
| Adjacency.RemoveGraph | 429-447 | 15 | 14 | 433 |
| Adjacency.RemoveNode | 397-423 | 20 | 10 | 400, 408, 409, 410, 411, 412, 413, 417, 418, 419 |
| Adjacency.RemoveSource | 349-391 | 31 | 20 | 352, 362, 363, 364, 365, 366, 367, 368, 369, 385, 386 |
| Adjacency.WriterLock | 62-73 | 8 | 3 | 67, 68, 69, 70, 72 |
| Eraser.CollectOrphanRoutes | 1086-1105 | 12 | 8 | 1099, 1100, 1101, 1102 |
| Eraser.EraseAll | 710-845 | 73 | 63 | 734, 747, 748, 749, 816, 817, 832, 834, 835, 836 |
| Eraser.EraseEdgeRow | 642-680 | 26 | 22 | 657, 658, 659, 660 |
| Eraser.EraseEdges | 396-463 | 44 | 41 | 402, 459, 460 |
| Eraser.EraseFHIRGraphRows | 1152-1180 | 16 | 5 | 1160, 1163, 1165, 1167, 1168, 1169, 1171, 1173, 1174, 1176, 1177 |
| Eraser.EraseFHIRNodeRows | 686-697 | 8 | 7 | 694 |
| Eraser.EraseGraph | 48-305 | 71 | 59 | 96, 171, 172, 175, 176, 260, 261, 286, 288, 289, 290, 292 |
| Eraser.EraseIdSet | 468-636 | 90 | 81 | 533, 545, 570, 571, 572, 573, 630, 631, 632 |
| Eraser.EraseNodeIds | 373-388 | 11 | 0 | 374, 375, 377, 378, 379, 381, 382, 383, 384, 385, 387 |
| Eraser.EraseNodes | 323-351 | 17 | 16 | 325 |
| Eraser.GraphEdgesInNKG | 869-919 | 31 | 15 | 876, 877, 879, 880, 881, 882, 883, 884, 885, 886, 887, 888, 906, 912, 913, 914 |
| Eraser.GraphNodesInNKG | 930-956 | 16 | 2 | 934, 935, 940, 941, 943, 945, 946, 947, 948, 949, 950, 951, 954, 955 |
| Eraser.InvalidateDerived | 1039-1053 | 7 | 6 | 1044 |
| Eraser.IsRouteName | 1059-1061 | 1 | 0 | 1060 |
| Eraser.NKGMayHoldAny | 976-986 | 7 | 6 | 982 |
| Eraser.NodeInterned | 995-1006 | 6 | 4 | 997, 1003 |
| Eraser.SqlErr | 1357-1359 | 1 | 0 | 1358 |
| Ledger.CanonicalRecord | 573-605 | 29 | 20 | 579, 580, 581, 582, 583, 584, 585, 586, 587 |
| Ledger.Commit | 398-415 | 13 | 9 | 407, 408, 409, 410 |
| Ledger.CommitInTxn | 420-528 | 75 | 60 | 427, 428, 429, 430, 431, 432, 433, 435, 442, 443, 469, 470, 471, 495, 496 |
| Ledger.Disable | 332-358 | 20 | 14 | 337, 338, 348, 349, 353, 354 |
| Ledger.Enable | 253-329 | 64 | 43 | 256, 257, 258, 259, 268, 269, 278, 279, 280, 300, 301, 302, 306, 307, 308, 314, 315, 316, 324, 325, 326 |
| Ledger.ErrLimit | 73-82 | 8 | 0 | 74, 75, 76, 77, 78, 79, 80, 81 |
| Ledger.LargeOut | 124-134 | 8 | 1 | 126, 127, 128, 129, 130, 131, 133 |
| Ledger.RecordVerify | 193-210 | 12 | 10 | 206, 207 |
| Ledger.SetStrict | 361-383 | 17 | 13 | 371, 372, 376, 377 |
| LedgerApply.ApplyAll | 19-48 | 27 | 26 | 44 |
| LedgerApply.DeleteRelInternal | 653-693 | 28 | 22 | 663, 664, 665, 666, 667, 668 |
| LedgerApply.NodeSnapshotJson | 338-351 | 11 | 10 | 345 |
| LedgerApply.OpCreateRel | 451-528 | 54 | 50 | 490, 510, 511, 513 |
| LedgerApply.OpDeleteNode | 375-416 | 32 | 30 | 395, 396 |
| LedgerApply.OpQual | 568-611 | 38 | 34 | 602, 603, 604, 605 |
| LedgerApply.ParseQuals | 124-141 | 12 | 10 | 134, 138 |
| LedgerApply.ResolveRef | 174-211 | 32 | 27 | 183, 184, 194, 195, 200 |
| LedgerGenesis.Adopt | 83-129 | 38 | 26 | 108, 109, 110, 111, 113, 114, 118, 119, 120, 121, 122, 123 |
| LedgerGenesis.TemporalMarked | 66-76 | 5 | 4 | 74 |
| LedgerRedact.Batch | 276-300 | 18 | 12 | 284, 285, 292, 293, 294, 295 |
| LedgerRedact.BatchInLock | 303-330 | 21 | 19 | 318, 319 |
| LedgerRedact.BlocksCommit | 259-269 | 7 | 6 | 268 |
| LedgerRedact.ClearRevision | 354-378 | 17 | 15 | 371, 372 |
| LedgerRedact.DropStatements | 447-471 | 19 | 18 | 465 |
| LedgerRedact.Final | 385-407 | 16 | 11 | 392, 393, 400, 401, 402 |
| LedgerRedact.LiveRows | 150-178 | 21 | 18 | 164, 167, 168 |
| LedgerRedact.Matches | 90-112 | 18 | 16 | 106, 107 |
| LedgerRedact.Redact | 186-239 | 41 | 40 | 195 |
| LedgerRedact.TupleEnds | 76-85 | 5 | 4 | 81 |
| LedgerRevision.RejectUpdate | 88-101 | 8 | 6 | 98, 99 |
| LedgerStats.Bump | 66-88 | 15 | 12 | 79, 84, 85 |
| Txn.Begin | 20-31 | 5 | 4 | 27 |
| Txn.End | 37-45 | 5 | 4 | 39 |
| Txn.Undo | 50-58 | 5 | 0 | 51, 52, 54, 55, 57 |

Fully exercised (55 methods): Eraser.EraseLedgerFor, Ledger.Err, Ledger.GKey, Ledger.Head, Ledger.MetaGet, Ledger.NewId, Ledger.NowMs, Ledger.RecordsClose, Ledger.RecordsExecute, Ledger.RecordsFetch, Ledger.RevisionObj, Ledger.RevisionResponse, Ledger.SeqOf, Ledger.State, Ledger.StmtForTuple, Ledger.WriteRevision, LedgerApply.AddLabel, LedgerApply.AllocStmt, LedgerApply.DeleteNodeRows, LedgerApply.Enc, LedgerApply.EncNull, LedgerApply.EnsureEndpoint, LedgerApply.FindEdge, LedgerApply.IsNumeric, LedgerApply.IsReserved, LedgerApply.MergeQuals, LedgerApply.NodeExists, LedgerApply.OpAddLabel, LedgerApply.OpCreateNode, LedgerApply.OpCreateTemporalEdge, LedgerApply.OpDeleteRel, LedgerApply.OpRemoveLabel, LedgerApply.OpRemoveProp, LedgerApply.OpSetProp, LedgerApply.PersistQuals, LedgerApply.QualsJson, LedgerApply.Rec, LedgerApply.Run, LedgerApply.SetProp, LedgerApply.TupleJson, LedgerApply.WeightOf, LedgerGenesis.Capture, LedgerRedact.FinalInLock, LedgerRedact.HasPrefix, LedgerRedact.InProgress, LedgerRedact.MatchString, LedgerRedact.PrePass, LedgerRedact.ReadCounts, LedgerRedact.Receipt, LedgerRedact.Sha256Hex, LedgerRedact.TargetDigest, LedgerRedact.TargetText, LedgerRedact.Tombstone, LedgerStats.Ensure, LedgerStats.PropertyFor.

| Handler (Python) | Lines | Exec. lines | Exercised | Unchecked lines |
|---|---|---|---|---|
| client.py:GraphLedger._call | 239-252 | 9 | 4 | 246, 247, 248, 249, 250 |
| client.py:GraphLedger._call_json | 254-259 | 5 | 3 | 258, 259 |
| client.py:GraphLedger._refuse_in_caller_transaction | 268-279 | 5 | 3 | 276, 277 |
| client.py:GraphLedger.enable | 281-297 | 12 | 7 | 290, 293, 294, 295, 296 |
| client.py:GraphLedger.disable | 299-303 | 4 | 3 | 303 |
| client.py:GraphLedger.set_strict | 305-309 | 4 | 3 | 309 |
| client.py:GraphLedger.head | 314-318 | 4 | 3 | 317 |
| client.py:GraphLedger._send_changeset | 322-379 | 44 | 24 | 341, 343, 344, 345, 346, 347, 348, 350, 351, 352, 353, 354, 355, 356, 362, 364, 365, 366, 367, 368 |
| client.py:GraphLedger.commit | 381-400 | 6 | 4 | 399, 400 |
| client.py:GraphLedger._apply_post_commit_properties | 445-487 | 26 | 21 | 483, 484, 485, 486, 487 |
| client.py:GraphLedger._seq_of | 579-583 | 4 | 3 | 582 |
| client.py:GraphLedger.get_revision | 695-704 | 8 | 7 | 702 |
| client.py:GraphLedger.diff | 706-718 | 10 | 9 | 714 |
| client.py:GraphLedger.export_reconstruction | 730-739 | 7 | 0 | 731, 732, 734, 735, 736, 737, 739 |
| client.py:_class_value | 210-216 | 4 | 3 | 215 |
| replay.py:verify | 806-859 | 42 | 36 | 818, 819, 832, 833, 841, 842 |
| replay.py:read_canonical | 588-642 | 42 | 37 | 623, 629, 630, 634, 635 |
| replay.py:compare | 645-698 | 44 | 30 | 661, 664, 665, 667, 668, 669, 670, 671, 672, 673, 688, 691, 692, 696 |
| replay.py:reconstruct | 544-566 | 15 | 8 | 556, 560, 561, 562, 563, 564, 566 |
| replay.py:iter_records | 231-249 | 11 | 10 | 247 |
| replay.py:iter_records_sql | 252-269 | 11 | 10 | 256 |
| replay.py:_adoption_items | 701-789 | 71 | 49 | 763, 764, 765, 766, 767, 768, 769, 770, 771, 772, 775, 776, 777, 778, 779, 780, 781, 782, 783, 784, 785, 786 |
| replay.py:_drop_temporal_marked | 792-803 | 4 | 1 | 801, 802, 803 |
| replay.py:GraphState.apply | 170-209 | 36 | 35 | 182 |
| replay.py:fetch_history | 299-354 | 39 | 24 | 318, 319, 320, 325, 326, 328, 329, 331, 332, 334, 335, 337, 338, 340, 341 |
| errors.py:from_commit_error | 175-199 | 20 | 16 | 181, 195, 197, 198 |
| _write_txn.py:caller_transaction_level | 64-87 | 15 | 12 | 73, 83, 86 |
| _write_txn.py:WriteTxn.begin | 164-175 | 10 | 6 | 168, 169, 170, 171 |
| _write_txn.py:WriteTxn.commit | 212-232 | 16 | 7 | 217, 218, 220, 221, 222, 223, 229, 230, 231 |
| _write_txn.py:WriteTxn.rollback | 234-253 | 14 | 0 | 238, 239, 240, 241, 243, 244, 245, 246, 247, 248, 250, 251, 252, 253 |
| _write_txn.py:WriteTxn.native | 147-160 | 8 | 0 | 151, 152, 153, 155, 156, 157, 158, 160 |
| _write_txn.py:WriteTxn._call | 131-137 | 6 | 5 | 136 |
| _write_txn.py:WriteTxn.__enter__ | 262-265 | 3 | 2 | 264 |
| _write_txn.py:WriteTxn.__exit__ | 267-272 | 4 | 3 | 271 |
| nodes_edges.py:NodesEdgesMixin.delete_nodes_by_prefix | 1529-1563 | 8 | 6 | 1555, 1556 |
| iris_sql_store.py:IRISGraphStore.delete_nodes_by_prefix | 1420-1448 | 12 | 8 | 1437, 1438, 1443, 1444 |

## 4. The §3.6 conditions (deliverable 3)

### 4.1 Frame (each handler writes only its declared stores)

Every transaction of the five r2 traces (and of `conf2`) wrote only stores in its operation's declared footprint
(`conformance.FOOTPRINT`, unchanged, plus `setenabled`, `bypass`, `read`, `probe` declared from source in
`check_all.EXTRA_FOOTPRINT`): **0 excursions** (`corr-frame-keys-fk`, `corr-trace-*`). Granularity is the store
(global root / SQL table), not the subscript or row. Per statement shape (`tools/frame_shapes.py`): of the write
statements in each module's handlers, these were executed under the check — module 11: 43/46 (not: reification delete
LedgerApply.cls:664, Adopt's statement close :110-111); module 12: 86/97 (routed-table DELETE/DROP, FHIR side tables,
`^NKG("$meta","invalidated")`, `RemoveSource`'s in-kill, `WriterLock`'s AdjNoLock); module 13: 18/19 (DropStatements'
tuple kill :465); module 14: 2/2 (RecordVerify's stats save; the post-commit property's SQL is Python and was
executed and frame-checked in `ext`). **Status: holds on every observed execution; the per-shape obligation is not
proved and 15 write statements were never executed — open.**

### 4.2 Keys (row ids, head, stmtNext, ledger_revisions)

In journal order of committed transactions, `^IVG.Ledger("head")` and `("stmtNext")` advance by exactly one; no
statement id is created twice or after it was killed; `ledger_revisions` seqs are exactly 1..head and
`idBySeq`/`revById` agree with `revision_id` in every final state (`corr-frame-keys-fk`: 0 notes over 5 traces;
4,510 statement ids created and 9 killed within the windows, none reused). By construction every writer of these keys runs under the head
lock (WriteRevision Ledger.cls:556-558, AllocStmt LedgerApply.cls:162-163). **But a replacing restore (module 18)
puts head back while `ledger_revisions` keeps the newer rows: the next commit fails with "ID key not unique ...
LedgerRevisionD(3)" (F-1801, `c18-live-ledger-overlay`); stmtNext goes back the same way.** Module 11: failed (F-1801);
12-14: hold on every trace (erasure and redaction allocate no ids except the redaction revision, head+1).

### 4.3 Foreign keys

Final rows of every trace are FK-closed (each `rdf_edges` (graph_id, s) and (graph_id, o_id), each `rdf_labels`
(graph_id, s) has its `nodes` row) and every erasure transaction committed (`corr-frame-keys-fk`). IRIS enforces the
composite FKs at statement time, so a committed erasure deleted in an FK-safe order: EraseGraph deletes labels, props,
docs, embeddings, routes, FHIR rows, reifications, edge embeddings, edges, then nodes (Eraser.cls:130-225);
EraseIdSet per id: incident edges (EraseEdgeRow), then labels, props, docs, embeddings, routes, then the node
(:497-590). A commit racing an erasure makes the erasure's node DELETE fail with -124 and roll back whole
(`live-erase-vs-commit-fk`). The ledger's create_rel registers endpoints first (EnsureEndpoint :485-488); delete_node
removes or refuses incident edges first (:401-413). Redaction writes no content row (n/a). **Module 14: `rdf_props` has
no FK; a replayed post-commit property after an erasure writes a property row of a node that no longer exists
(F-1306; `ib-HD1305-retry-revives`).**

### 4.4 Row permutation / storage order

`$ORDER` scans in the handlers depend only on key order or are order-insensitive (inspected): CommitInTxn's staged
chunks (integer chunk index), RecordsFetch / PrePass / BatchInLock (the (seq, ordinal) cursor *is* the documented
order), QualsJson / MergeQuals / OpCreateRel's sorted local `tKeys`, Final's `("redacting","revs")` (seq order),
DropStatements and EraseLedgerFor (collect then kill: the result is a set), EraseIdSet's `^||IVG.EraseIds` and
`tEdge` (sets), GraphEdgesInNKG/GraphNodesInNKG (boolean any-of), LiveRows (COUNT). Genesis Capture orders every scan
(LedgerGenesis.cls:18-38). Two SQL cursors without ORDER BY whose result depends on row order: **OpDeleteNode** assigns
statement ids to unrecorded incident edges in cursor order — live: three insertion orders give three id assignments,
same content (F-C1108, `corr-row-permutation`); **FindEdge** (LedgerApply.cls:144-157) takes the first row of
(s, p, o, graph), which in a multigraph (several `ekey` rows) is one of several (inspected, not probed). Status:
module 11 open (intent-undecided), 12-14 open (inspected only; no permutation run).

### 4.5 Capacity (`corr-capacity`; lock-table capacity is outside the IRIS contract's subset and not probed)

| Case | Outcome |
|---|---|
| reference limits (read-only) | `^IVG.Ledger("tuple", s, p, o, gk)` holds s = o = 195, p = 97; `^KG("out", 0, s, p, o)` 199; `^KG("prop", 0, id)` 500 |
| node id 256 / 257 | ok / clean failure (`failed_op` "insert node failed ... validation") |
| edge s = o = 194, p = 97 (widest that commits) | ok; EraseNodes, EraseGraph, redaction, verify and a genesis over a bypass-written edge of that width: all ok |
| edge 195/97 and 256/128 (schema-valid) | clean failure: `<SUBSCRIPT>` in rdf_edges' unique index u_spo_graph_ekey (F-C1106) |
| bypass `create_edge` 195 | refused by the same index (SQLCODE -415), "nothing written" (the harness's own `create_node` calls before it are why the row is marked "partial") |
| qualifier value 1,000,000 | ok (staged payload) — but the schema says maxLength 4000 (F-C1107); its later redaction ok (SHA-256 of a ~1 MB CanonicalRecord) |
| qualifier value 4,000,000 | clean failure, reported as `inconsistent` (`<MAXSTRING>`) (F-C1107) |
| property value 64,000 / 64,001 | ok / clean failure (`failed_op` validation) |
| idempotency_key 256 / 257 / 600 | ok / clean failure `inconsistent` (#7201) / clean failure `inconsistent` (`<SUBSCRIPT>` at Ledger.cls:457) (F-C1107) |
| message 4,001 | clean failure `inconsistent` (#7201) (F-C1107) |
| redaction prefix 10,000 | ok (matches nothing) |
| EraseNodes prefix 10,000 | clean failure: SQLCODE -400 `<SUBSCRIPT>` in the prefix cursor (F-C1204) |
| graph name 300 | clean failure (`failed_op` "register endpoint ... validation") |

No case changed state on failure and no case corrupted state (no recorded edge without its tuple entry, no row without
adjacency). The ledger is never handed a tuple it cannot index, because the content table's index is one character
narrower than the ledger's. Status: 11 failed (F-C1106, F-C1107), 12 failed (F-C1204), 13 and 14 open (string and
subscript limits hold for the redaction and verify cases probed; lock-table capacity is unrepresentable in the
contract; readers over ~1 MB records not probed).

### 4.6 Integrity (stmt/tuple bijection, tombstone shape)

After every operation of every trace: every live `("stmt")` entry has the tuple entry pointing back at it and every
tuple entry names a live statement with the same (s, p, o, graph) (both directions, α invariants); every tuple entry
names a live edge row (`stmts_ok`); every tombstone is `$LB("redacted", 64-hex, flags, op, kind)` and its digest is
the SHA-256 of the CanonicalRecord of the record it replaced, recomputed independently (`tools/abstraction.py
canonical_record`; 10 + 29 tombstones in conf/ext; the first attempt showed that `entity_id` of relationship records
is a JSON number, as `%ToJSON` emits an integer `$LB` element). The one integrity failure observed is F-1201's (a live
recorded edge without its statement, `corr-trace-f1201`).

### 4.7 Closure and ownership (`corr-closure-scan`)

44 product write sites of the ledger state: all but one belong to a modelled action; `restore_snapshot`
(snapshot.py:403, module 18) overlays `^IVG.Ledger` and the ledger tables outside any modelled step (F-1801); PurgeAll is
an admin reset. Ownership: the statement maps `("stmt")`/`("tuple")` have four owner actions — commit, adoption,
erasure (no head lock: F-1114) and Final's DropStatements; `ledger_stats` is shared by commit (Bump) and verify
(RecordVerify) and loses counts under contention (F-1102); `rdf_props` is written by commits, the eraser, the
post-commit property (no record, F-1101) and the 25 census writers (`writer-census`).

## 5. Lock plans from production behaviour (deliverable 4; `corr-lockplan`)

Each probe: P holds the lock, X runs the operation; X's process state (`%SYS.ProcessQuery.CurrentLineAndRoutine`,
mapped through the INT to the `.cls`), the lock table (`%SYS.LockQuery_List()`), and X's journal records split at the
release instant.

| Probe (lock held by P) | Observed | Plan (source) |
|---|---|---|
| head-commit (head X, 2.5 s) | X `LOCKW` at **Ledger.cls:440** inside its transaction (`InTransaction` set), 0 journaled writes before the release; commits after | lock after TSTART :402, before any write: matches |
| head-commit-timeout (33 s) | `LedgerLockTimeoutError` after 30.0 s; only the `rej_lock_timeout` stats bump written; nothing held after | :441-443, 30 s: matches |
| head-redact | X passes the unlocked opening reads and waits at **LedgerRedact.cls:282** (Batch); 0 writes before | matches (and is F-1302's unlocked start) |
| head-erase-nodes / head-erase-graph | X finishes in 6-14 ms while the head lock is held, killing `^IVG.Ledger("stmt"/"tuple")` before the release | no head lock: matches the source; differs from the reviewed design (F-1114, F-1201) |
| head-enable (never-enabled) | X waits at **Ledger.cls:266** inside its transaction, after the state read :254 | matches (F-1104's window) |
| head-disable / head-verify | finish while held (Disable writes `meta state` and stats) | no lock: matches; the Ledger contract's SetEnabled has no lock precondition |
| deferred-nested-commit (X in its own transaction) | after `commit()` returns X still owns `^IVG.Ledger("head")` X and `^IVG.AdjW(0)` S with count **`1D`** (deferred release); both gone after X's COMMIT | Lock - :404 / Adjacency.cls:93 inside a transaction: deferred to the outermost end (contract *Locks: deferral*): matches |
| deferred-nested-erase | `^IVG.AdjW("NE")` S `1D` until X's COMMIT | matches |
| adjw-commit (AdjW(0) X) | X owns the head lock X and waits at **Adjacency.cls:63** during the edge INSERT; node rows already written | order head -> AdjW: matches |
| adjw-commit-timeout (7 s) | after 5.0 s X proceeds without the lock, SET `^IVG.AdjNoLock(0)`, commits | :61-73: matches |
| adjw-shared-compatible (AdjW(0) S) | no wait | shared/shared compatible: matches |
| adjw-erase-graph (2.5 s) | waits at Adjacency.cls:63 (row DELETE's functional index); completes | matches |
| adjw-erase-graph-timeout (12 s) | row writer gives up after 5 s (AdjNoLock), **RemoveGraph refuses at Adjacency.cls:431** after 5 s more; the erase throws, rolls back; the graph's rows are intact (net effect: bitmap-extent re-encoding only) | :234-235, :259-261: matches |
| adjw-erase-all | waits at :63 (row writer) | matches |
| adjw-erase-all-parent (no edge rows) | waits at **Adjacency.cls:455** for the parent `^IVG.AdjW#"S"` after its row deletes | matches |

Not observed directly: Final's head lock (LedgerRedact.cls:390) — the same code shape as Batch's and executed in every
completed redaction of the traces; the ledger_stats row lock of Bump (observed by breadth-b, F-1102). **No mismatch
between the source lock plans and production behaviour; the mismatches are between the as-built plans and the reviewed
design**: erasure without the head lock (F-1114, F-1201), the unlocked redaction start (F-1302, F-1303), Enable's
unlocked state read (F-1104). No new lock-plan finding.

## 6. New findings (`findings.json`, for the orchestrator to merge)

| Id | Module | Sev. | Title | Evidence |
|---|---|---|---|---|
| F-C1106 | 11 | S3 | Relationships the wire schema admits are refused above an undocumented key-length limit (s = o ≥ 195, p ≥ 97: `<SUBSCRIPT>` in rdf_edges' unique index) | `corr-capacity` |
| F-C1107 | 11 | S3 | The commit does not enforce the schema's length limits (1 MB qualifier accepted) and reports violations (key 257/600, message 4,001, 4 M qualifier) as `inconsistent` / LedgerInconsistencyError | `corr-capacity` |
| F-C1108 | 11 | S4 | A detach delete assigns statement ids to unrecorded incident edges in storage order (intent-undecided) | `corr-row-permutation` |
| F-C1109 | 11 | S4 | Every `node_not_found` refusal is decoded as "create_relationship failed ... set auto_stub_missing_nodes" | `corr-trace-ext` |
| F-C1204 | 12 | S4 | EraseNodes fails (SQLCODE -400) on a prefix longer than the subscript limit instead of erasing nothing | `corr-capacity` |

Corroborated with new evidence: F-1114, F-1104, F-1302 (`corr-lockplan`), F-1201 (`corr-trace-f1201`: per-transaction
steps pass, the pair is non-serializable), F-1101 (`corr-trace-ext`: post-commit property = store change outside the
ledger).

## 7. Gate status (matrix-input/correspondence_status.json) and what stays open

| Gate | 11 | 12 | 13 | 14 |
|---|---|---|---|---|
| 3.4-statements | open | open | open | open |
| 3.4-ownership | failed | failed | failed | failed |
| 3.4-declared-reads | open | open | open | open |
| 3.5-handlers | open | open | open | open |
| 3.5-lockplans | failed | failed | failed | failed |
| 3.6-frame | open | open | open | open |
| 3.6-keys | failed | closed | closed | closed |
| 3.6-fk | closed | closed | not-applicable | failed |
| 3.6-capacity | failed | failed | open | open |
| 3.6-row-permutation | open | open | open | open |
| 3.6-closure | failed | open | failed | failed |
| 3.7-lock-log | closed | closed | open | closed |

Stays open, and why:
- **3.4-statements / 3.5-handlers (all four)**: no verifier for ObjectScript or Python, so no statement or handler is
  proved to perform its model step. What is discharged is a trace refinement check on the traced inputs; the unchecked
  lines of §3 (281 ObjectScript, 181 Python) have no evidence at all, and the exercised lines only for the inputs the
  traces used. The proofs (`proofs/`) remain statements about models.
- **3.4-declared-reads**: the journal records writes only; no read oracle was built; read sets are listed per action
  (§2b) from source. The reads that matter for correctness (EraseLedgerFor's dirty scan, the unlocked LiveRows, the
  readers' once-only marker check) are modelled (F-1201, F-C1201, F-C1301, F-1402).
- **3.6-frame**: empirical at store granularity; 15 write statements never executed.
- **3.6-row-permutation**: F-C1108 intent-undecided; FindEdge in multigraphs inspected only.
- **3.6-capacity 13/14**: lock-table capacity outside the IRIS contract's subset (unrepresentable); readers over very
  large records not probed.
- **3.7-lock-log 13**: Final's head lock not observed by a probe.
- 3.6-closure is a product-scope gate in `matrix/gates.json`; the module cells are informational for the orchestrator.

## 8. Registered runs (this lane)

`corr-int-alignment`, `corr-trace-conf`, `corr-trace-ext`, `corr-trace-f1201` (fail: F-1201 reproduced),
`corr-trace-lostack`, `corr-abstraction-selftest`, `corr-conformance-fast-equivalence`, `corr-line-coverage`,
`corr-frame-keys-fk`, `corr-lockplan`, `corr-capacity` (fail: F-C1106, F-C1107, F-C1204), `corr-row-permutation`
(fail: F-C1108), `corr-closure-scan` (fail: F-1801's unmodelled writer). Logs under
`$RUN_DIR/correspondence/{checks,live}`. Superseded, not registered: the r1 traces (`live/traces/`, monitor counted
setup work; the first `conf` ran without the monitor because a terminal decode error disabled it), the first capacity
run (`capacity-r1-harness-error.log`, a setup assumption of the harness).

## 9. Reproduce

```bash
source experiment/playbook-completion/environment.sh
T=experiment/playbook-completion/correspondence/tools; O=$RUN_DIR/correspondence/live
bash experiment/playbook-completion/tools/locks.sh iris bash -c "for s in conf ext f1201 lostack; do python $T/scenarios.py $O/traces-r2 \$s --monitor; done; python $T/lockplan.py $O/lockplan; python $T/capacity.py $O/capacity"
python $T/check_all.py $O/traces-r2/{conf,ext,f1201-1,f1201-2,lostack} --json $RUN_DIR/correspondence/checks/checks-r2.json
python $T/coverage.py $RUN_DIR/correspondence/probe0 $O/traces-r2/* --json $O/coverage.json
python $T/pycoverage.py $O/traces-r2/* --json $O/pycoverage.json
python $T/abstraction_selftest.py $O/traces-r2/conf/trace.json $O/traces-r2/ext/trace.json
python $T/conformance_fast.py --equivalence $O/traces-r2/conf/trace.json $O/traces-r2/ext/trace.json
python $T/closure_scan.py --self-test; python $T/build.py
```
