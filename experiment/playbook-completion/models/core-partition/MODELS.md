# Core M1 in the (2 pre-enable writes, 2 commits) profile, by a partition of its state space (proof debt D-10)

Lane models-2 of the completion audit. Evidence grade: `mc` (explorer at `c03f9fa`, bounded). Every statement here is
about the M1 model (`models/core/MODELS.md`, "M1 targeting"), never about the ObjectScript at pin `3eaa79cf`. The
product's obligations stay as the as-built evidence leaves them: F-1304 and F-1305 are reproduced live
(`live-native-rerun-1314`), and the as-built M1 violates RED-B1.1/RED-X2 and RED-B12/SC-001 here too.

## What was open

`models/core` ran M1's exhaustive checks in three bound profiles (pre-enable writes, ledger commits) a = (1, 2),
b = (2, 1), c = (0, 3); (2, 2) "exceeded 8 million states without finishing and is not claimed" (`models/core/MODELS.md`,
Remaining gaps; `PROOF-DEBT.md` D-10).

## Crate

`models/core-partition` (`ivg-core-partition`): `src/m1.rs` is a copy of `models/core/src/m1.rs` (sha256
`5490e14e9b23a629...`) whose machine is unchanged; added are a piece mode, `key_of` and the invariant `PART` (diff: the
header comment, the `piece` field and its two guards, `init_states`, `invariants`; nothing in a transition or a
property changed). `src/util.rs` is copied unchanged. `src/main.rs` is new (coverage checks and per-piece families).
Run: `python experiment/playbook-completion/models/core-partition/tools/run_partition.py [--register]` (it takes the
heavy lock itself; do not wrap it). Results: `RESULTS.json`; per-piece rows in each family's JSON under the run's
`out_dir`.

## Method: partition by pre-enable world

A pre-enable world W is a reachable state of the full (2, 2) model with `enabled = false`, i.e. the content written
before `enable()`. Piece W is M1 started in W with the pre-enable writes disabled. Facts the partition rests on, each
checked mechanically:

1. **Structure before enable()** (checked by `--coverage 2 2` over every reachable pre-enable state, with the full
   model's own `next`): the only enabled actions are pre-enable writes, whose successors have `enabled = false`, and
   `Enable`, whose successor has `enabled = true`. There are 43 such states (75 pre-enable write transitions): 1 with no
   write, 9 with one, 33 with two.
2. **Closure after enable()** (checked by the invariant `PART` at every state of every piece run): at every enabled
   state the full (2, 2) model (no piece mode, same bounds) has exactly the piece's successors (all 24 action kinds
   compared), so piece mode removes no transition there and a piece is closed under the full model's successors.
3. **Disjointness** (also `PART`): every enabled state of piece W has `key_of(s) = W`, where `key_of` reads only the
   state (its write count and its genesis revision, which records every node row with its ghost graph and every edge
   row, and whose records are never removed). Since a pre-enable state is determined by (writes, node rows, edge rows),
   distinct pieces have distinct keys and their enabled parts are disjoint.

Hence the reachable set of the full (2, 2) model is the disjoint union of the 43 pieces' reachable sets (each piece
contributes its own W and its enabled states): every path of the full model is a run of pre-enable writes to some W,
then `Enable`, then actions of piece W; conversely every piece path is a path of the full model from a reachable W.
Each property is checked on every piece, so it holds on the full space iff it holds on every piece.

**AG EF per piece** ("every erased target can still be completely redacted") is sound: an enabled state's successors
in the full model are its successors in the piece (fact 2), so the set of states reachable from it, and whether a goal
state is among them, is the same in both; a pre-enable state has `pending = 0`, so it is itself a goal state. No piece
run is truncated (state cap 60 M; the explorer's frontier rule never applies because M1 has no `within_bounds` cut).

Independent confirmations of the argument:

- **Keys** (`m2p-coverage-keys`): the 43 piece keys equal an enumeration written independently of `m1.rs`'s `next`
  (every sequence of at most two writes, each adding an absent node row, or an absent edge row with its endpoint rows in
  the edge's graph). Control (`m2p-coverage-keys-control`): dropping one key makes the check fail.
- **Union** on the profiles that fit unpartitioned (`m2p-union-a-reviewed`, `-b-reviewed`, `-b-as-built`,
  `-c-reviewed`): an explorer-free breadth-first enumeration of the full reachable set equals the union of the pieces'
  sets exactly (no piece state outside it, no state in two pieces, no full state in no piece; sums 2,849,806,
  1,469,036, 1,720,016, 1,369,721, which are also the registered unpartitioned explorer counts of `core-m1-reviewed-a`,
  `-b`, `core-m1-as-built-isolation-stmt-b`, `core-m1-reviewed-c`). Control (`m2p-union-control`): dropping one piece
  leaves 103,011 full states uncovered and the check fails.
- **Fidelity of the copy** (`m2p-fidelity`): with piece mode off, the copy reproduces the state counts of the six
  registered profile checks `core-m1-reviewed-{a,b,c}` and `core-m1-as-built-isolation-stmt-{a,b,c}` exactly.
- **The unpartitioned (2, 2) runs** (`m2p-full-reviewed-22`, `m2p-full-as-built-isolation-stmt-22`): see Results.

## Expectations per piece (stated in `src/main.rs` `families()` before the decisive runs)

| Family (keep) | Design | Expectation in piece W | Why |
|---|---|---|---|
| `reviewed` (every property: RED-B1.1/RED-X2, RED-B12/SC-001, RED-I1/I2, RPL-B3, ERS-I2/I3, AG EF; PART) | reviewed (HD-1303 + HD-1304) | pass, exhaustive | as profiles a-c |
| `as-built-isolation-stmt` (RED-I1/I2, ERS-I2/I3, AG EF; PART) | as built | pass, exhaustive | as profiles a-c |
| `as-built-F1304` (RED-B1.1/RED-X2; PART) | as built | violation in every piece | from any W: erase both graphs, commit a node a\|1 in D, a bypass write of E0 puts a\|1 in G, EraseGraph(D), Redact(D, -) counts D's rows only and tombstones a\|1's record (F-1304) |
| `as-built-F1305` (RED-B12/SC-001; PART) | as built | violation iff W has a node row of n in G; else pass, exhaustive | a node record whose ghost graph is G arises only from genesis; (G, -) cannot match the graph-blind record and reports complete (F-1305); in every other respect as-built and reviewed agree on SC-001 |
| `control-liveness-collapsed` (RED-B1.1/RED-X2; PART) | reviewed with one liveness predicate | violation in every piece | negative control: the F-1304 path with Redact(D, a\|) |
| `control-dropstatements-all-graphs` (ERS-I2/I3; PART) | reviewed with DropStatements ignoring the graph | violation in every piece | negative control: a redaction of an empty graph drops another graph's live statement |

A violation run is breadth-first and stops at the first violation (shortest trace in its piece); it is a witness, not
an exhaustive exploration. A pass run is exhaustive within the piece's bounds.

## Results (run `$RUN_DIR/models-2/final-20261114T113041Z`)

| Registry id | Check | Result | States | Transitions | Time | Peak RSS |
|---|---|---|---|---|---|---|
| `m2p-reviewed-22` | reviewed, every property + AG EF + PART, 43 pieces | pass in 43/43, exhaustive | 21,355,762 (largest piece 1,558,548) | 266,808,918 | 427 s (wall 436 s) | 1.08 GB |
| `m2p-as-built-isolation-stmt-22` | as built, RED-I1/I2 + ERS-I2/I3 + AG EF + PART, 43 pieces | pass in 43/43, exhaustive | 25,117,999 (largest piece 1,912,607) | 314,278,010 | 483 s (wall 494 s) | 1.38 GB |
| `m2p-as-built-F1304-22` | as built, RED-B1.1/RED-X2 (F-1304), 43 pieces | expected violation in 43/43 (first violation, shortest) | 3,901 (largest piece 706) | 7,454 | 0 s (wall 0 s) | 3 MB |
| `m2p-as-built-F1305-22` | as built, RED-B12/SC-001 (F-1305), 43 pieces | expected violation in 22/43 (first violation, shortest), pass exhaustive in 21/43 | 6,893,103 (largest piece 740,891) | 85,937,065 | 116 s (wall 118 s) | 253 MB |
| `m2p-control-liveness-collapsed-22` | control: one liveness predicate, 43 pieces | expected violation in 43/43 (first violation, shortest) | 5,382 (largest piece 706) | 12,111 | 0 s (wall 0 s) | 3 MB |
| `m2p-control-dropstatements-all-graphs-22` | control: DropStatements ignores the graph, 43 pieces | expected violation in 43/43 (first violation, shortest) | 8,563 (largest piece 512) | 19,102 | 0 s (wall 0 s) | 3 MB |
| `m2p-full-reviewed-22` | unpartitioned (2, 2), reviewed, every property + AG EF | pass, exhaustive; states equal the partition's sum 21,355,762 | 21,355,762 | 266,808,993 | wall 263 s | 14.68 GB |
| `m2p-full-as-built-isolation-stmt-22` | unpartitioned (2, 2), as built, RED-I1/I2 + ERS-I2/I3 + AG EF | pass, exhaustive; states equal the partition's sum 25,117,999 | 25,117,999 | 314,278,085 | wall 290 s | 17.07 GB |
| `m2p-coverage-keys` | 43 piece keys: structure before enable(), equal to the independent enumeration | pass | - | - | wall 0 s | 2 MB |
| `m2p-coverage-keys-control` | control: one key dropped | fails as it must | - | - | wall 0 s | 2 MB |
| `m2p-union-a-reviewed` | union = full set, profile a (1, 2) reviewed | pass | - | - | wall 61 s | 967 MB |
| `m2p-union-b-reviewed` | union = full set, profile b (2, 1) reviewed | pass | - | - | wall 27 s | 361 MB |
| `m2p-union-b-as-built` | union = full set, profile b (2, 1) as built | pass | - | - | wall 33 s | 406 MB |
| `m2p-union-c-reviewed` | union = full set, profile c (0, 3) reviewed | pass | - | - | wall 27 s | 766 MB |
| `m2p-union-control` | control: one piece dropped (profile b) | fails as it must | - | - | wall 26 s | 360 MB |
| `m2p-fidelity` | copy reproduces core-m1-reviewed-a/b/c, core-m1-as-built-isolation-stmt-a/b/c | pass | - | - | wall 129 s | 2.23 GB |

Transitions: each family's sum plus the 75 pre-enable write transitions (which piece mode does not take; they lead from one world to another) equals the unpartitioned count (266,808,918 + 75 = 266,808,993; 314,278,010 + 75 = 314,278,085). The F-1305 violations are exactly the 22 worlds with a node row of n in G (`family-as-built-F1305.json`); every F-1304 and control piece has a shortest trace of 2 to 5 steps (e.g. empty world: enable, commit a|1 + b|1, bypass write of E0, EraseGraph(D), Redact(D, -) complete with a|1's record tombstoned while a|1 lives in G). Per-piece rows (state counts, depths, traces): `$RUN_DIR/models-2/final-20261114T113041Z/family-*.json` and `.log`.

The unpartitioned (2, 2) runs fit in memory here (14.7 GB and 17.1 GB peak under the heavy lock); the earlier probe "exceeded 8 million states without finishing" (models/core/MODELS.md, which also mentions an abandoned M1 probe at an 8 M cap); the space has 21,355,762 (reviewed) and 25,117,999 (as built) states. The partition is the primary method (1.1-1.4 GB per family run) and the unpartitioned runs confirm it: same state counts, same verdicts.

## What is claimed, and what is not

- Claimed: within M1's bounds (at most 2 pre-enable writes, at most 2 ledger commits, at most 1 ledger-bypassing write;
  erasures and Redact calls unbounded), the reviewed M1 (HD-1303 + HD-1304 working assumptions) satisfies every M1
  property and AG EF on the whole (2, 2) space, exhaustively; the as-built M1 keeps RED-I1/I2, ERS-I2/I3 and AG EF on
  the whole space and violates RED-B1.1/RED-X2 (F-1304) from every pre-enable world and RED-B12/SC-001 (F-1305) from
  exactly the 22 worlds with a node row of n in G. Together with profile c (0, 3), M1 is now exhaustive for every
  profile with at most 2 pre-enable writes and at most 2 commits, and for (0, 3).
- Not claimed: (2, 3), (1, 3) or larger profiles (the default violation bound (2, 3) is used only by violation checks);
  anything outside M1's world (three ids, two graphs, three edges, no temporal edges, labels and properties folded into
  node rows; `models/core/MODELS.md`, Remaining gaps); anything about the product's code (no correspondence proof,
  PROOF-DEBT D-2/D-3). The reviewed design is a model; no reviewed element exists at the pin.
- Trust: the explorer is executable and unproved (TRUST.md); the coverage argument's three facts are checked by code in
  this crate (`--coverage`, `PART`) and cross-checked by an explorer-free enumeration on four smaller profiles and by the
  unpartitioned (2, 2) counts.
