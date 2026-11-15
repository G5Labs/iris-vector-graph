# Core models: erase -> redact -> replay (modules 12 ERS, 13 RED, 14 RPL)

Lane core-models of the completion audit. Explorer machines (G5Labs/actors `explorer` at `c03f9fa`) for the product at pin
`3eaa79cf`, closing the §3.3 / §3.3a model-fidelity gaps of the original submission (`experiment/playbook-uplift/MODELS.md`,
`baseline-audit.md` row "§3.3 — model fidelity"). Evidence grade: `mc` (bounded; every result below is exhaustive within
its declared bounds unless it says truncated, and none is). Nothing here is a proof, and nothing here is about the
ObjectScript itself: each machine is an executable reading of the cited source lines, checked against a stated property.

- Crate: `models/core` (`src/m1.rs`, `m2.rs`, `m3_retry.rs`, `m3_readers.rs`, `refine.rs`, `util.rs`, `main.rs`).
- Run: `bash tools/locks.sh heavy bash experiment/playbook-completion/models/core/tools/run_all.sh` (one process and one
  log per check under `$RUN_DIR/core-models/final/`, then `tools/merge_results.py` writes `RESULTS.json`; with `--register`
  it registers every check as `core-<id>`). One check: `ivg-core-models --only <id>`; `--list` lists them.
- Results: `RESULTS.json` (per check: id, machine, design, expectation, met, result, states, transitions, depth,
  exhaustive|truncated, seconds, violated property, counterexample trace, peak RSS, log).

## What the original collapsed, and where it is now represented

| Collapsed in the original (baseline-audit §3.3 model fidelity) | Now represented | Machine |
|---|---|---|
| one target predicate for three rules (P-1310) | `Matches` (LedgerRedact.cls:89-112), `LiveRows` (149-178), `DropStatements` (446-471) kept apart, plus the eraser's `EraseGraph` (Eraser.cls:47-261, `EraseLedgerFor` 1117-1144) and `EraseNodes` (322-351, `EraseIdSet` 467-636, `EraseEdgeRow` 641-680) | M1 |
| graph-blind node provenance | node records carry graph "" with the ghost graph of the row they describe; genesis records every row of every graph (LedgerGenesis.cls:14-36); `NodeExists` graph-blind (LedgerApply.cls:79-84); implicit endpoints without a record (`EnsureEndpoint`, 97-110); overlapping ids in D and G | M1 |
| default/named graphs, preexisting data | graphs D and G; content written before `enable()` and by a ledger-bypassing writer after it | M1 |
| unattributed qualifier records | qualifier records resolved only through ("redacting","stmt"), the PrePass map, or the ("stmt") row; -1 counted (317-320) | M1 |
| statement/tuple maps and cleanup | ("stmt") entries (live/closed) and ("tuple") entries, written by commits, killed by both erasers and by `DropStatements` | M1, M2 |
| atomic erasure (P-1311) | EraseGraph as four steps of one open transaction (row DELETE with the index's adjacency entry; `RemoveGraph`; `EraseLedgerFor`; TCOMMIT) or a stop that rolls it back | M2 |
| the two opening reads as one step | marker check (202-205) and `LiveRows` (206-210) as separate unlocked steps | M2 |
| audit as a flag | shared counters under the one marker (342-344) at the pin, per-target counters in the reviewed design; every audit's count checked against the tombstones its own target made | M2 |
| Final only with its own marker | Final with own, absent (no audit when nothing dropped, 418) or other target's marker; Final after a scan that ended before newer records | M2 |
| isolation and rollback | IRIS contract (`iris-contract/CONTRACT.md`, validated): dirty reads of globals and rows, value-based rollback ("Rollback over another's write"), DELETE waits for another transaction's inserted row, stop rolls back and releases locks | M2 |
| idempotent post-commit replay (F-1306) | post-commit property as a separate write (client.py:430-487), replay before the commit check (Ledger.cls:457-462 before 514-518), no FK, EraseNodes selecting from `nodes` | M3-retry |
| restore of an older archive (HD-1801) | replacing restore that overlays the archive's ledger (F-1801) vs refusal of a divergent archive | M3-retry |
| readers and verify (F-1401, F-1402) | marker checked once before reading; verify's graph-blind node comparison vs the governed identity; detach delete with a named-graph edge | M3-readers |

## Machines, bounds, designs

**M1 targeting (`m1.rs`)**, sequential (each operation one atomic step). World: graphs D and G; ids `a|1`, `b|1`, `n`;
edges E0 = G:a|1->n, E1 = G:b|1->n, E2 = D:a|1->b|1 (spans both tenants). Actions: pre-enable writes of nodes and edges
(with implicit endpoints), `enable()` (genesis), commits create_node, a spanning create of a|1+b|1, create_rel (with
`EnsureEndpoint`), delete_rel, set_qual (assigning a statement to an unrecorded edge, `ResolveRef`), one ledger-bypassing
edge write, EraseGraph(D|G), EraseNodes(D|G, a||b|), Redact over all six targets (liveness, PrePass, scan, Final with
`DropStatements`). Bounds: erasures and Redact calls unbounded; pre-enable writes and commits bounded; exhaustive checks
run three profiles that partition the bound — a: 1 pre-write + 2 commits, b: 2 + 1, c: 0 + 3 ((2, 2) exceeded 8 million
states without finishing and is not claimed). Violation checks use (2, 3) and stop at the first violation (breadth-first,
so shortest). Reviewed = HD-1303 (an unprefixed default-graph target counts node rows of every graph: refused unless no
node lives anywhere) + HD-1304 (a named-graph target with no prefix reports `incomplete` while the history holds node
records of dead ids it cannot attribute). Properties: RED-B1.1/RED-X2 (no tombstone of content live in any graph; node
records: the id in any graph, as verify compares), RED-B12/SC-001 (a complete redaction leaves no dead content of its own
target except records it counts as unattributed; "own target" by provenance, with the documented second target
`redact(None, prefix)` for prefixed tenants), RED-I1/I2 (only records in the documented reach change, each into its own
tombstone), RPL-B3 (no unrecorded write and every target the documented procedure owes redacted => replay equals the
store), ERS-I2/I3 (live statement entries are exactly the live saved edges), AG EF "every erased target can still be
completely redacted".

**M2 concurrency (`m2.rs`)**. World: named graphs G1 (tenant A) and G2 (tenant B); targets A = (G1, -), B = (G2, -);
edges a0 (G1) and b0 (G2) committed by a revision spanning both tenants, a1 (G1) created by commit CA; commit DA deletes
a0. For relationship records and graph targets the three predicates coincide (Matches: record graph; LiveRows: rows of
the graph; DropStatements: statements of the graph); M1 is where they differ. Processes: two redacting processes (either
target), a ledger committer P (apply under the head lock, BlocksCommit, commit or rollback, or stop), an eraser E
(EraseGraph's four steps or stop), a ledger-bypassing writer W (insert or delete any edge row of either graph in its own
transaction, at any moment). Batches process one record (batch_size=1 is a legal configuration; larger batches are a
subset of these schedules). Value-based undo logs give the committed view and IRIS rollback. Bounds: ledger commits ≤ 2,
bypass writes ≤ 2 (guards); erasures, Redact calls (resumes) and stops unbounded, so the graph is finite and exact and AG
EF is decided with no state cut by a bound (the explorer counts cut states as able to reach the goal, which would let any
bounded action "rescue" a stuck state; the first version of these checks had exactly that weakness and was discarded).
Designs: as-built; reviewed = HD-1201 (the eraser holds the head lock from its DELETE to its commit) + HD-1301 (Start checks
marker and liveness and sets its marker in one step under the head lock; batches and Final run only under their own
target's marker; per-target counters) + one requirement found here (Final runs only when its scan has reached the current
end of the ledger — the original L2 machine had this guard, the pin does not; control `m2-control-final-trusts-old-scan`
shows the reviewed design fails without it). Properties (census names in brackets): INV-no-live-tombstone (no tombstone
describes a live incarnation whenever no transaction is open), INV-audit (each audit counts exactly its own target's
tombstones), INV-audit-settled, INV-marker-owner (a run tombstones and finishes only under its own target's marker),
INV-marker (while the marker names t no record of t is added), INV-stmt (live statement entries = live recorded edges,
no transaction open), INV-adj (adjacency = edge rows, no transaction open), INV-text (Decision 2), INV-retry, INV-replay;
AG EF "settled: no marker, no run, no open transaction, every erased target that is still erased redacted".

**M3-retry (`m3_retry.rs`)**. Tenant A's node a|1 (default graph) by changeset C with key k and a post-commit property;
tenant B's changeset U moves the ledger on; client crash between the commit and its property write; retries (replayed
while the key is bound, before the commit check); EraseNodes(D, a|); the redaction (D, a|) in the reviewed marker
protocol (start, batches, Final, stop/resume) so F-1302/F-1303 do not mask what is studied; one archive save and one
restore. Reviewed = HD-1305 (a retry must not recreate erased properties, and an incomplete first attempt keeps a
recovery path: the property write is one conditional statement "while the node row exists" and records its completion
in the ledger, so a replay applies it only for an incomplete first attempt) + HD-1801 (a restore whose archive's ledger
is not the live ledger is refused before anything changes). Properties: RPL-X (after an erasure only a recorded commit
or an authorized restore makes the tenant's content live again), RED-B2/HD-1801 (a redacted record never regains its
content), INV-text incl. redactedRev, INV-retry, RPL-B3 (node identity as `read_canonical`, which makes a node of a
property row); AG EF "the tenant's erasure can always be finished without touching tenant B" and "a live committed node
can always get its post-commit property".

**M3-readers (`m3_readers.rs`)**. Ledger create_node x, y (D), create_rel x->y in G (two records, implicit endpoints),
delete_node x detach (R290: D's row only), an unrecorded node z; EraseGraph(G); redaction of (G, -) with an epoch; a
record reader and verify(), each: marker check, read (verify reads records and tables as one cut — stronger than the
pin; the race studied is the marker check), and in the reviewed design a re-check of marker and epoch. Reviewed verify
compares the governed node identity (default-graph rows; HD-1401 working answer). Properties: RPL-I1 (an accepted view
never shows a redaction half done), RPL-B7/HD-1401 (an accepted verify verdict is the intended one), AG EF the readers
finish.

**Refinement (`refine.rs`)**. `explorer::refinement::audit` of reviewed M2 (every process stoppable, no bypass writer)
against an executable L1 (Commit, Erase, Begin, Finish, atomic; invariants Decision 2, retry keys, marker, no tombstone of
a live incarnation, statements = live edges) through the committed view and the original's implied-tombstone
abstraction. Every concrete step must be the labelled L1 step or a stutter; L1's invariants must hold on every abstract
state; observations (committed rows, marker) must agree.

## Results

82 checks, 82 met their expectation, 0 truncated (state cap 60,000,000); every result is exhaustive within its declared bounds. Largest: `m2-reviewed-bypass-serializing-w1c1` 8,075,032 states, 5.7 GB peak; the whole suite takes about 5 minutes (`$RUN_DIR/core-models/final/`, logs per check; registered as `core-<id>`). Step counts are the shortest traces (breadth-first); an AG EF violation's trace ends at a state from which the goal is unreachable.

| Check | Design | Expectation | Result | States | Depth | s |
|---|---|---|---|---|---|---|
| **M1** | | | | | | |
| `m1-as-built-F1304` | as-built | violation: RED-B1.1/RED-X2 | MET expected-violation (3 steps) | 231 | 2 | 0.0 |
| `m1-as-built-F1305` | as-built | violation: RED-B12/SC-001 | MET expected-violation (4 steps) | 1,740 | 3 | 0.0 |
| `m1-as-built-isolation-stmt-a` | as-built | pass | MET pass | 3,257,790 | 17 | 33.3 |
| `m1-as-built-isolation-stmt-b` | as-built | pass | MET pass | 1,720,016 | 17 | 15.3 |
| `m1-as-built-isolation-stmt-c` | as-built | pass | MET pass | 1,398,785 | 17 | 14.5 |
| `m1-as-built-replay` | as-built | violation: RPL-B3 | MET expected-violation (3 steps) | 231 | 2 | 0.0 |
| `m1-control-dropstatements-all-graphs` | control | violation: ERS-I2/I3 | MET expected-violation (3 steps) | 300 | 2 | 0.0 |
| `m1-control-liveness-collapsed` | control | violation: RED-B1.1/RED-X2 | MET expected-violation (3 steps) | 231 | 2 | 0.0 |
| `m1-control-qual-ignores-ends` | control | violation: RED-I1/I2 | MET expected-violation (4 steps) | 399 | 3 | 0.0 |
| `m1-control-unattributed-uncounted` | control | violation: RED-B12/SC-001 | MET expected-violation (5 steps) | 2,602 | 4 | 0.0 |
| `m1-progress-never-complete-progress` | progress-mutant | violation: every erased target can still be completely redacted | MET expected-violation (2 steps) | 1,049,375 | 16 | 9.1 |
| `m1-progress-never-complete-safety` | progress-mutant | pass | MET pass | 1,049,375 | 16 | 9.7 |
| `m1-reviewed-a` | reviewed | pass | MET pass | 2,849,806 | 17 | 31.6 |
| `m1-reviewed-b` | reviewed | pass | MET pass | 1,469,036 | 16 | 14.3 |
| `m1-reviewed-c` | reviewed | pass | MET pass | 1,369,721 | 17 | 15.1 |
| `m1-sc001-strict` | as-built | violation: SC-001 strict | MET expected-violation (5 steps) | 2,602 | 4 | 0.0 |
| `m1-sharp-incomplete` | sharpness | violation: witness: a graph-only target reports incomplete | MET expected-violation (4 steps) | 362 | 3 | 0.0 |
| `m1-sharp-refused-other-graph` | sharpness | violation: witness: a default-graph target is refused for a node living only in G | MET expected-violation (3 steps) | 87 | 2 | 0.0 |
| `m1-sharp-tenant-cycle` | sharpness | violation: witness: a prefixed tenant with an edge in G is erased and redacted by its two targets | MET expected-violation (5 steps) | 11,121 | 4 | 0.0 |
| `m1-sharp-unattributed` | sharpness | violation: witness: a complete redaction counts an unattributed record | MET expected-violation (5 steps) | 2,602 | 4 | 0.0 |
| **M2** | | | | | | |
| `m2-as-built-F1201-adjacency` | as-built | violation: INV-adj | MET expected-violation (6 steps) | 895 | 5 | 0.0 |
| `m2-as-built-F1201-stmt` | as-built | violation: INV-stmt | MET expected-violation (6 steps) | 893 | 5 | 0.0 |
| `m2-as-built-F1302-commit-after-check` | as-built | violation: INV-no-live-tombstone | MET expected-violation (10 steps) | 5,978 | 9 | 0.0 |
| `m2-as-built-F1303-audit` | as-built | violation: INV-audit | MET expected-violation (13 steps) | 2,391 | 12 | 0.0 |
| `m2-as-built-F1303-owner` | as-built | violation: INV-marker-owner | MET expected-violation (12 steps) | 1,721 | 11 | 0.0 |
| `m2-as-built-P1311-erase-rollback` | as-built | violation: INV-no-live-tombstone | MET expected-violation (5 steps) | 102 | 4 | 0.0 |
| `m2-as-built-bypass-rollback` | as-built | violation: INV-no-live-tombstone | MET expected-violation (5 steps) | 661 | 4 | 0.0 |
| `m2-as-built-commit-rollback` | as-built | violation: INV-no-live-tombstone | MET expected-violation (5 steps) | 457 | 4 | 0.0 |
| `m2-as-built-marker-holds` | as-built | pass | MET pass | 6,680,005 | 92 | 46.6 |
| `m2-as-built-paced-resume` | as-built | violation: settled | MET expected-violation (1 steps) | 936 | 18 | 0.0 |
| `m2-as-built-stale-final` | as-built | violation: INV-replay | MET expected-violation (20 steps) | 208,480 | 19 | 0.9 |
| `m2-as-built-unpaced-progress` | as-built | pass | MET pass | 165,746 | 57 | 0.8 |
| `m2-control-batch-under-other-marker` | control | violation: INV-marker-owner | MET expected-violation (20 steps) | 69,253 | 19 | 0.2 |
| `m2-control-counters-swapped` | control | violation: INV-audit | MET expected-violation (7 steps) | 338 | 6 | 0.0 |
| `m2-control-erase-no-head-lock` | control | violation: INV-stmt | MET expected-violation (6 steps) | 493 | 5 | 0.0 |
| `m2-control-final-trusts-old-scan` | control | violation: INV-replay | MET expected-violation (20 steps) | 70,492 | 19 | 0.2 |
| `m2-control-unlocked-start` | control | violation: INV-no-live-tombstone | MET expected-violation (5 steps) | 278 | 4 | 0.0 |
| `m2-progress-final-keeps-marker-progress` | progress-mutant | violation: settled | MET expected-violation (3 steps) | 182,756 | 37 | 0.9 |
| `m2-progress-final-keeps-marker-safety` | progress-mutant | pass | MET pass | 182,756 | 37 | 0.9 |
| `m2-progress-paced-restart-progress` | progress-mutant | violation: settled | MET expected-violation (3 steps) | 3,400 | 19 | 0.0 |
| `m2-progress-paced-restart-safety` | progress-mutant | pass | MET pass | 3,400 | 19 | 0.0 |
| `m2-reviewed` | reviewed | pass | MET pass | 2,448,115 | 68 | 16.2 |
| `m2-reviewed-bypass-nonserializing` | reviewed | violation: INV-no-live-tombstone | MET expected-violation (4 steps) | 124 | 3 | 0.0 |
| `m2-reviewed-bypass-serializing-w1c0` | reviewed | pass | MET pass | 558,374 | 46 | 3.7 |
| `m2-reviewed-bypass-serializing-w1c1` | reviewed | pass | MET pass | 8,075,032 | 66 | 56.1 |
| `m2-reviewed-bypass-serializing-w2c0` | reviewed | pass | MET pass | 3,064,642 | 48 | 19.4 |
| `m2-reviewed-bypass-stmt` | reviewed | violation: INV-stmt | MET expected-violation (2 steps) | 9 | 1 | 0.0 |
| `m2-sharp-both-audited` | sharpness | violation: witness: both targets audited | MET expected-violation (16 steps) | 20,686 | 15 | 0.1 |
| `m2-sharp-commit-refused` | sharpness | violation: witness: a commit into the marked target is refused | MET expected-violation (5 steps) | 103 | 4 | 0.0 |
| `m2-sharp-erase-rollback` | sharpness | violation: witness: an erasure is rolled back after its ledger cleanup | MET expected-violation (4 steps) | 31 | 3 | 0.0 |
| `m2-sharp-final-no-marker` | sharpness | violation: witness: a Final runs with no marker and drops statements | MET expected-violation (14 steps) | 19,957 | 13 | 0.1 |
| `m2-sharp-final-other-marker` | sharpness | violation: witness: a Final runs under another target's marker | MET expected-violation (13 steps) | 2,391 | 12 | 0.0 |
| `m2-sharp-paced-loop` | sharpness | violation: witness: a paused call left every record of A tombstoned, the marker set, and Final never ran | MET expected-violation (7 steps) | 189 | 6 | 0.0 |
| `m2-sharp-resume-completes` | sharpness | violation: witness: a stopped run is resumed and audited | MET expected-violation (10 steps) | 1,403 | 9 | 0.0 |
| **M3-retry** | | | | | | |
| `m3-as-built-F1306` | as-built | violation: RPL-X | MET expected-violation (3 steps) | 11 | 2 | 0.0 |
| `m3-as-built-F1306-stuck` | as-built | violation: the tenant's erasure can always be finished without touching tenant B (no marker, nothing pending) | MET expected-violation (3 steps) | 62 | 10 | 0.0 |
| `m3-as-built-F1801` | as-built | violation: RED-B2/HD-1801 | MET expected-violation (7 steps) | 322 | 6 | 0.0 |
| `m3-as-built-F1801-keys` | as-built | violation: INV-retry | MET expected-violation (7 steps) | 322 | 6 | 0.0 |
| `m3-as-built-F1801-marks` | as-built | violation: INV-text | MET expected-violation (7 steps) | 322 | 6 | 0.0 |
| `m3-as-built-pcp-race` | as-built | violation: RPL-X | MET expected-violation (3 steps) | 16 | 2 | 0.0 |
| `m3-control-keep-retry-key` | control | violation: INV-retry | MET expected-violation (4 steps) | 49 | 3 | 0.0 |
| `m3-control-replay-applies-pcp` | control | violation: RPL-X | MET expected-violation (3 steps) | 22 | 2 | 0.0 |
| `m3-control-restore-overlay` | control | violation: RED-B2/HD-1801 | MET expected-violation (8 steps) | 517 | 7 | 0.0 |
| `m3-progress-no-pcp-recovery-progress` | progress-mutant | violation: a live committed node can always get its post-commit property (HD-1305 recovery path) | MET expected-violation (2 steps) | 78 | 5 | 0.0 |
| `m3-progress-no-pcp-recovery-safety` | progress-mutant | pass | MET pass | 985 | 13 | 0.0 |
| `m3-reviewed` | reviewed | pass | MET pass | 1,087 | 14 | 0.0 |
| `m3-reviewed-recovery` | reviewed | pass | MET pass | 86 | 6 | 0.0 |
| `m3-sharp-crash-recovered` | sharpness | violation: witness: a retry completes a crashed first attempt's property | MET expected-violation (3 steps) | 25 | 2 | 0.0 |
| `m3-sharp-restore-refused` | sharpness | violation: witness: a restore is refused after a redaction | MET expected-violation (8 steps) | 414 | 7 | 0.0 |
| `m3-sharp-retry-refused` | sharpness | violation: witness: the redacted key is in idemRedacted and the tenant is erased and redacted | MET expected-violation (5 steps) | 103 | 4 | 0.0 |
| **M3-readers** | | | | | | |
| `m3-readers-as-built-F1401` | as-built | violation: RPL-B7/HD-1401 | MET expected-violation (6 steps) | 310 | 5 | 0.0 |
| `m3-readers-as-built-F1402` | as-built | violation: RPL-I1 | MET expected-violation (10 steps) | 1,504 | 9 | 0.0 |
| `m3-readers-control-no-epoch` | control | violation: RPL-I1 | MET expected-violation (13 steps) | 6,663 | 12 | 0.0 |
| `m3-readers-control-verify-ignores-nodes` | control | violation: RPL-B7/HD-1401 | MET expected-violation (3 steps) | 68 | 2 | 0.0 |
| `m3-readers-progress-wait-for-epoch-progress` | progress-mutant | violation: the readers can always finish | MET expected-violation (2 steps) | 12,006 | 22 | 0.0 |
| `m3-readers-progress-wait-for-epoch-safety` | progress-mutant | pass | MET pass | 12,006 | 22 | 0.0 |
| `m3-readers-reviewed` | reviewed | pass | MET pass | 12,006 | 22 | 0.0 |
| `m3-readers-reviewed-verdict` | reviewed | pass | MET pass | 12,006 | 22 | 0.0 |
| `m3-readers-sharp-epoch-refusal` | sharpness | violation: witness: a reviewed reader refuses because a whole redaction run passed | MET expected-violation (13 steps) | 6,663 | 12 | 0.0 |
| **refinement** | | | | | | |
| `refine-m2-as-built` | as-built | violation: a refinement violation | MET expected-violation (4 steps) | 129 | 3 | 0.0 |
| `refine-m2-control-unlocked-start` | control | violation: a refinement violation | MET expected-violation (5 steps) | 278 | 4 | 0.0 |
| `refine-m2-reviewed` | reviewed | pass | MET pass | 2,448,115 | 68 | 26.7 |

## Findings reproduced (as-built, shortest traces in RESULTS.json)

| Finding | Check (steps) | Shortest trace | Reviewed design |
|---|---|---|---|
| F-1201 | `m2-as-built-F1201-stmt` (6) | E deletes G1's rows; E RemoveGraph; P applies create a1 (row, statement 3, tuple); E's EraseLedgerFor kills statement 3 and its tuple; E commits; P commits: a1 live and recorded, no statement | passes with the eraser holding the head lock (`m2-reviewed`); control `m2-control-erase-no-head-lock` (5) |
| F-1302 | `m2-as-built-F1302-commit-after-check` (10) | marker check; a ledger delete of a0 (uncommitted) makes A look erased to the unlocked LiveRows; the delete commits; commit CA creates a1; the batches tombstone a1's record while a1 is live | passes with the locked Start; control `m2-control-unlocked-start` (4) |
| F-1303 | `m2-as-built-F1303-audit` (13), `m2-as-built-F1303-owner` (12) | both runs pass their marker check before either tombstones; A's first tombstone sets marker A; B tombstones b0 under A's marker; B's Final writes audit(B:2), counting A's tombstone, and removes A's marker while A still runs | passes; controls `m2-control-counters-swapped` (6), `m2-control-batch-under-other-marker` |
| F-1304 | `m1-as-built-F1304` (3) | a\|1 written in G before enable(); genesis records it graph-blind; Redact(D, -) counts D's rows only and tombstones a\|1's record while a\|1 lives in G (also RPL-B3, `m1-as-built-replay`, 3) | passes (HD-1303: refused while any node lives); control `m1-control-liveness-collapsed` (3) |
| F-1305 | `m1-as-built-F1305` (4) | n written in G before enable(); genesis; EraseGraph(G); Redact(G, -) reports complete; n's node record (graph "") stays and is not counted | passes (HD-1304: `incomplete`, witness `m1-sharp-incomplete`) |
| F-1306 | `m3-as-built-F1306` (3), `m3-as-built-F1306-stuck` (AG EF) | commit with a post-commit property; EraseNodes(D, a\|); a retry is replayed and writes the property again; EraseNodes no longer selects it (no node row) and LiveRows counts it, so the redaction is refused for ever short of EraseGraph(D) | passes (`m3-reviewed`); control `m3-control-replay-applies-pcp` |
| F-1401 | `m3-readers-as-built-F1401` (6) | create x, y; create_rel x->y in G (implicit endpoints); delete_node x detach; verify (graph-blind) diverges on x, whose G row stays | passes (governed identity); control `m3-readers-control-verify-ignores-nodes` (3) |
| F-1402 | `m3-readers-as-built-F1402` (10) | the reader checks the marker; a redaction of G starts and tombstones one of G's two records; the reader reads a half-done view and accepts it | passes (re-check marker and epoch); control `m3-readers-control-no-epoch` |
| F-1801 | `m3-as-built-F1801` (7), `-marks` (7), `-keys` (7) | commit; erase; save; redact; restore: the archive's record replaces the tombstone, its text and key come back, redactedRev still marks the revision, the key is bound and in idemRedacted | passes (refuse a divergent archive; witness `m3-sharp-restore-refused`); control `m3-control-restore-overlay` |
| F-C1201 (live, intent lane B) | `m2-as-built-P1311-erase-rollback` (5) | marker check; E deletes G1's rows; the unlocked LiveRows reads the uncommitted delete; a batch tombstones a0's record; E is stopped and rolls back: a0 live, its history tombstoned. Premise P-1311 of the original proof is false at the pin | passes with HD-1201 + HD-1301 (the eraser and Start both hold the head lock) |
| F-0303 class | `m2-reviewed-bypass-stmt` (2) | a ledger-bypassing delete of a0's row commits; statement 1 stays live (INV-stmt), in any design | not a redaction design question |

Not reproduced by a model: F-1301 (a documentation conflict; the models follow Decision 2, which INV-text checks).

## New findings (proposed; ids for the orchestrator to confirm)

Each is a candidate record for the findings audit (module 12/13), with its shortest model trace in `RESULTS.json`.
Model evidence only (`mc`); none is reproduced live by this lane.

**F-C1301 (proposed, module 13, S1, confidence medium) — the liveness check reads the uncommitted deletes of every
writer, not only of an erasure.** Intended: RED-B1.1, spec 256 FR-005, INV-no-live-tombstone. Observed (model): the
unlocked `LiveRows` (LedgerRedact.cls:206-210) counts rows READ UNCOMMITTED (contract "Visibility"), so an open
transaction that deleted the target's last live row makes it look erased; when that transaction rolls back, the run has
tombstoned live content. F-C1201 is the erasure case; the same holds for a ledger commit that is stopped
(`m2-as-built-commit-rollback`, 5 steps: marker check, P applies delete_rel a0, LiveRows passes, P stopped and rolled
back, a batch tombstones a0's record) and for any of the 25 ledger-bypassing writers (`m2-as-built-bypass-rollback`, 5
steps). The reviewed lock design (Start under the head lock, HD-1301; eraser under it, HD-1201) closes the ledger and
erasure cases but not the bypass writers, which take no head lock: `m2-reviewed-bypass-nonserializing` (4 steps: W
deletes a0 uncommitted; the locked Start passes; a batch tombstones; W rolls back). This contradicts the original
discharge "INV-no-live-tombstone × engine.direct_edge_delete: removes content only" (`playbook-uplift/semantics/
WRITESETS.md:62`). Premise: the contract's Visibility clause applied to an uncommitted DELETE (the decided case
`row-dirty-select` is an insert; F-C1201's live probe observed the delete case for an erasure). Remedy: every
same-target writer serializes with the redaction's check (HD-1201 extended), or the check must not observe uncommitted
deletes; `m2-reviewed-bypass-serializing-*` pass when the writer serializes.

**F-C1302 (proposed, module 13, S2, confidence medium, low likelihood) — Final trusts a scan that ended before it took
the lock.** Intended: RED-B12/SC-001 and RPL-B3 (a complete redaction leaves no content of its target; verify equal
after erase and redact). Observed (model, `m2-as-built-stale-final`, 20 steps): the call runs `Final` as soon as a batch
has passed the last record that existed then (LedgerRedact.cls:216-231); `FinalInLock` (409-442) re-checks liveness but
not that no record was appended since. Trace: two calls of target A (p0, p1); both scan to the end; p0's Final
completes and removes the marker; commit CA creates a1 in G1 (no marker, so not refused); EraseGraph(G1) removes it; p1's
Final now finds A not live, no marker and no statement, returns `complete` with no audit — a1's create record is still
content and verify diverges. The same happens to a single call whose run tombstoned nothing, if a commit and an erasure
of the target land between its last batch and its Final's lock. Remedy: under the lock, Final checks that the ledger head
is where its scan ended, or keeps scanning (the original L2 machine's Final had this guard; with it the reviewed design
passes, and the control `m2-control-final-trusts-old-scan` shows the reviewed design fails without it).

**F-C1303 (proposed, module 13, S3, confidence high) — a paced redaction never finishes.** Intended: `ledger.redact`
docstring (client.py:659-660: "max_batches > 0 stops early and leaves the run in progress; calling again with the same
target resumes it"); ADR-0013 ("Re-running the same redaction resumes it"); RED-B8. Observed: every call starts its scan
at the first record (LedgerRedact.cls:214) and a batch scans at most batch_size × SCANFACTOR (20) records
(213, 309); a call with max_batches = k therefore never examines records beyond k × batch_size × 20, already tombstoned
records included, so an operator who keeps resuming with the same max_batches never reaches Final on a ledger with more
records: the marker stays, readers refuse and commits into the target are refused for ever. Model:
`m2-as-built-paced-resume` (AG EF fails; with unpaced resumes `m2-as-built-unpaced-progress` passes) and the witness
`m2-sharp-paced-loop` (7 steps: every record of A tombstoned, marker set, Final unreachable). Remedy: keep the cursor
under the marker and resume from it, or let a resumed call skip tombstones without counting them against the cap.

**F-C1202 (proposed, module 12, S2, confidence medium) — EraseGraph's adjacency kill drops an edge committed after its
row DELETE.** Same root cause as F-1201 (no serialization between EraseGraph and writers of the graph). Observed (model,
`m2-as-built-F1201-adjacency`, 6 steps): E deletes G1's rows; P inserts a1 (its row's index entry writes ^KG); E's
`Adjacency.RemoveGraph` (Adjacency.cls:428-447, a shared writer lock that does not exclude writers) kills ^KG("out"/"in",
G1) including a1's entry; both commit: a1's row is live and traversals do not see it. HD-1201's head lock closes it for
ledger commits only; a non-ledger edge writer is not excluded by the head lock.

**F-1306 / F-1101, an additional trace (no new id).** `m3-as-built-pcp-race` (3 steps): the first attempt's own
post-commit write (client.py:430-435, a separate transaction after the commit) lands after an EraseNodes of its node and
revives the erased tenant's property, without any retry. "A replay applies no post-commit properties" (the naive HD-1305
remedy) does not close it; a property write that applies only while the node row exists does (`m3-reviewed`).

### What the reviewed designs needed (design feedback, not product findings)

- HD-1301: the locked Start must be complemented by a Final that checks its scan reached the current head (F-C1302;
  control `m2-control-final-trusts-old-scan`).
- HD-1201: "same-target writes serialize" must include the ledger-bypassing writers, or the liveness check must not see
  uncommitted deletes (F-C1301; `m2-reviewed-bypass-nonserializing`).
- HD-1305: suppressing replays alone removes the recovery path of a first attempt that crashed before its property write
  (`m3-progress-no-pcp-recovery-progress`); a conditional write with recorded completion keeps both (`m3-reviewed`,
  `m3-reviewed-recovery`).
- HD-1303 / HD-1304 working assumptions: no violation in any of the three M1 profiles.

## The ledger-bypassing writer and the 25 census writers

`$RUN_DIR/checks/writer-census.json` lists 25 product writers outside the original write plans that write content
tables and never consult the marker (EdgeScan.BulkIngestEdgesSQL/BulkIngestNodesSQL/RegisterDefaultNode,
Eraser.DeleteBareSet, FHIRGraph.EnsureNode/SyncProps/DeleteEdge/DropNode/ResyncKey, TemporalPolicy.DropRows,
Adjacency.RetractTemporalRow(s), the SQL store's write_nodes/write_edges/delete_edges/_delete_nodes_sql, nodes_edges
store_node/bulk_ingest_edges, schema inference and migrations), giving 100 (invariant, writer) obligations on INV-marker,
INV-no-live-tombstone, INV-stmt and INV-replay. M2's writer W stands for all of them: it inserts or deletes a content row
of either graph (either target) in its own transaction, at any moment (before, during and after any redaction phase:
between the opening reads, between batches, before Final), never reads the marker, and takes no head lock at the pin. The
grouping holds because, for the four invariants, what matters about a writer is only (1) which target's content it makes
live or not live, (2) whether its change is visible before it commits and can roll back, and (3) whether it writes ledger
globals — the census writers write content tables only. Node, label and property rows are subsumed by edge rows here
because `LiveRows` treats a live row of any content table of the target identically and graph targets match no node
record (node-record effects of bypass writes are M1's `bypass` and pre-enable actions). A writer that commits per
statement (autocommit) is the special case "W begins and commits with no step in between". Per invariant:

| Invariant | W at the pin (does not serialize) | W serializing like a ledger write (HD-1201 working assumption extended to all same-target writers) |
|---|---|---|
| INV-no-live-tombstone | **fails**: the liveness check reads W's uncommitted delete, the run tombstones, W rolls back (`m2-as-built-bypass-rollback`, 5 steps); the reviewed locked Start fails the same way (`m2-reviewed-bypass-nonserializing`) | holds (`m2-reviewed-bypass-serializing-*`); W's inserts during a run are new, unrecorded incarnations, so tombstoning older records is correct, and Final refuses `target_live` |
| INV-marker | holds: W adds no record (`m2-as-built-marker-holds`, `m2-reviewed-bypass-serializing-*`); W does write content into a marked target unrefused, which makes Final refuse until the target is erased again (AG EF still holds: erase again) | holds |
| INV-stmt | **fails** by W alone: a bypass delete of a recorded edge leaves its live statement (F-0303 class; `m2-reviewed-bypass-stmt`, 2 steps) | fails the same way (not a redaction property) |
| INV-replay | discharged by the invariant's premise "no unrecorded write" (verify classifies unrecorded writes, RPL-B7.1); the guard is a ghost set by W's commit | same |

## Progress: premises and progress-only mutants

AG EF ("from every reachable state some path reaches the goal") is checked on the exact finite graph (no bounded
action can rescue a state). The path it asserts encodes these premises, which are therefore assumptions, not results:
writers become quiet (the path adds no commit or bypass write), the operator resumes stopped or paused runs (calls are
unbounded), no process is stopped forever (the path contains no stop), and the operator may erase a target again when a
write made it live (erasures unbounded). AG EF is not "every fair schedule settles" (P-1306: a scan that follows the tail
finishes only if commits pause). Progress-only mutants (each violates AG EF and nothing else):

| Machine | Mutant | AG EF | Safety |
|---|---|---|---|
| M1 | a redaction never reports complete | fails | holds |
| M2 | Final writes the audit but never removes the marker | fails | holds |
| M2 | every resumed call restarts its scan and pauses after one record (the pin's paced resume) | fails | holds |
| M3-retry | a replay never applies post-commit properties (the naive HD-1305 fix) | the recovery goal fails | holds |
| M3-readers | a reader waits for its old epoch instead of refusing | fails | holds |

## Remaining gaps

- M1 is exhaustive in three bound profiles (1 pre-enable write + 2 commits; 2 + 1; 0 + 3); (2, 2) exceeded 8 million states
  without finishing and is not claimed. Three ids, two graphs and three edges: no transitive or multi-hop effects,
  labels and properties folded into node rows, no temporal edges.
- Temporal edges are not modelled. Inspected only, no claim: `Matches` matches `create_temporal_edge` records by their
  tuple (LedgerRedact.cls:97-98) while `LiveRows` counts nodes, labels, properties and edges only (149-178), and a
  predicate registered temporal-only writes no structural row (TemporalIndex.cls WriteStores, ADR-0015); whether a live
  temporal-only edge can have its history tombstoned is open.
- M2 uses graph-only targets on two named graphs, where the three predicates coincide; prefix targets under concurrency
  (the PrePass map read outside the lock, qualifier attribution through live statement rows read dirty) and node records
  under concurrency are not modelled. One eraser (EraseGraph only; EraseNodes/EraseEdges/EraseAll concurrency not
  modelled), batches of one record, lock timeouts modelled as waits, ledger disable/enable during a run not modelled.
- The bypass writer is checked with the committer off (1 or 2 writes) and with 1 write + 1 commit (committer and eraser
  not stopped in that partition); 1 write + 1 commit with every process stoppable exceeded 19 GB and is not claimed.
- Adjacency is one bit per edge with the functional index; the degree cache and generations (module 04) are not.
- M3-readers: verify reads records and tables as one cut (stronger than the pin), so verify racing commits (P-1401) is not
  covered; no genesis, so the governed identity of graph-blind genesis records of named-graph rows (HD-1101/1304) is
  not decided here. The reviewed verify equals the oracle by construction; the checks show the oracle discriminates
  (control) and that the pin's verify differs from it (F-1401).
- M3-retry: one node, one key; a retry with different post-commit properties under the same fingerprint, merge restores
  (F-1802) and restores during a run are not modelled.
- Refinement: reviewed M2 without the bypass writer against an executable L1; not a proof, not a `Protocol2` composition
  (queue Q4), and L1 is this lane's reading of the original l1.rs, extended.
- Explorer caveat (tool, not product): when a run stops at the state cap, a state expanded only partly keeps the
  successors found so far, so AG EF can report a false violation (seen once in an abandoned M1 probe at an 8 M cap);
  explorer/src/lib.rs treats only states with no recorded successor as cut. No reported result is truncated.
- IRIS semantics come from the validated contract (`iris-contract/CONTRACT.md`); the delete case of dirty reads is the
  general Visibility clause (decided case: inserts). Nothing here observes the product live.
