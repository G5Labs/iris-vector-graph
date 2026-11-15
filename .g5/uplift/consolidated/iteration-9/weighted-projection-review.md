# Independent review of the weighted producer mismatch

Product3eaa79cf. Read-only source/evidence review; no native call, model, shared
file, register, product or Git edit. Reviewed the original retained failure
`weighted-attempts/mode-off-lowest-oracle.{py,json,log}` and root's later
`weighted-projection-state.json`, not merely a rewritten successful oracle.

**Conclusion:** this receipt does not demonstrate that PutKeyed mishandles ekey0.
The fixture never enabled multigraph mode. The actual mode-off callback route
overwrites the bare scalar with the later row's weight1. The original lowest-key
oracle assumed the wrong producer branch. The accepted second row in a mode-off
graph is already covered by existing mode-off multiplicity findings; no new
lowest-ekey defect or Dijkstra optimality failure is established here.

## Actual source and retained observation

The original script starts with `e.erase_all()`, creates edges with ordinary
`create_edge`, and directly inserts another same-triple row at ekey5/weight1.
There is no `set_multigraph`, GraphMode.Apply/Set or write of `^IVG.GraphMode` in
that script. Calling the graph `wp9:multi` has no mode semantics. Eraser.EraseAll
(`Eraser.cls`:807) explicitly kills the GraphMode global.

The row callback chain at the pin is:

1. Declared functional `idx_edges_adj` has arguments graph_id,s,p,o_id,qualifiers,
   ekey (`schema.py`:771-774; `AdjIndex.cls`:1-14).
2. `AdjIndex.InsertIndex` forwards all six fields to `Adjacency.RowPut`.
3. `RowPut` (`Adjacency.cls`:476-489) derives the graph index key and qualifier
   weight, then calls PutKeyed **only if** `$Get(^IVG.GraphMode(tG))="multi"`.
   Otherwise it calls plain Put, regardless of the row's nonzero ekey.
4. `Put` (`:83-95`) assigns both bare out and in leaves to `+pWeight`; it does
   not create child ekeys or `#`, and does not select a lowest representative.

Root's identity-checked follow-up directly observes IsMulti0, raw mode null,
out/in scalar1, and no child0, child5 or `#` under either direction. This confirms
the expected mode-off state and bare-leaf shape. The source route plus this shape
explains the mismatch without invoking a special ekey0 comparison or exception.
The exact callback was not instrumented; its source routing is independently
consistent with all retained state evidence.

The original native receipt remains DISAGREES:9,000 paired searches,75 total
reported mismatches. Its producer assertion expected scalar10 from the lowest
SQL key0, while the actual mode-off scalar is1. Downstream recorded cost1 answers
are therefore compared to the wrong graph oracle (the projected-lowest graph
would instead use its alternative route of cost4). These observations should be
retained as a valid mode-off neighbor and an invalid lowest-key oracle, not counted
as an algorithmic counterexample or hidden evaluator result.

## Premises for a faithful producer/model link

Numerical correctness over the actual raw adjacency graph is separate from the
SQL-row-to-leaf producer claim. The former can remain valid for the recorded
scalar1 graph. The latter must derive or condition on the real mode routing:

- In mode off, RowPut/Put uses the latest writing callback's scalar for a repeated
  triple. Multiple committed rows are possible despite intended mode-off rules.
  FillTriple's nonmulti rebuild likewise uses the last supplied row, not lowest
  ekey. Do not discard this source-supported state merely because it violates the
  intended one-row policy.
- In mode on with complete indexed producer transitions, PutKeyed/SetLeafFromLowest
  selects the lowest live ekey, including0. The derived graph is not the minimum
  over parallel-row weights. This particular failed receipt did not exercise that
  branch at all.
- Current mode alone is insufficient for a history-sensitive physical equality
  claim: turning mode on after bad/restore-produced leaves does not by itself
  rebuild them. Establish mode before the relevant keyed writes or a completed
  faithful rebuild, correct functional-index declaration/arguments and admitted
  competing writers. Ledger direct Reweight is a separately known exception.

A minimal producer model can take raw graph mode plus row/callback order and
derive the two branches, then feed the resulting scalar graph to the queue proof.
Alternatively keep raw-leaf search proof and a clearly conditional lowest-key
helper theorem. It must not silently assume "graph has parallel rows" implies
"graph's mode is enabled", or present a helper as generic physical equality.

## Existing register disposition

- **F-0201** already states that a mode-off graph can hold two rows of one triple,
  reproduced live by the playbook arm; its governing intent is GID-I4.10/spec234.
- **bug-str-008** explicitly identifies `u_spo_graph_ekey` admitting nonzero keys
  in mode-off graphs and the missing server-side refusal, with stale-cache/mode-
  switch/restore routes. Raw SQL here uses the same admitted state and RowPut
  mode-off routing; it is not a third independent root to count.
- **bug-str-007** describes the related restore ordering: erase clears modes,
  rows are inserted through mode-off callbacks, the mode arrives afterward and
  no rebuild follows. This is the same reason current mode cannot establish past
  producer routing, but the present trigger is a native harness, not restore.
- **bug-str-012** is a different root: LedgerApply.PersistQuals invokes direct
  Reweight after an indexed multigraph qualifier update and can override lowest
  ekey. That path is not present in this receipt.
- **bug-str-011** concerns swallowed keyed-writer statuses. No keyed route or
  failing callback is established here, so it should not be used as this cause.

These registers already distinguish the mode/admission and writer roots. No
register update was made by this reviewer. If root adds evidence, describe this
as the mode-off raw-SQL neighbor/oracle correction and preserve inherited IDs.

## Exact remaining evidence

The follow-up settled the largest missing fact: raw native mode is off and keyed
layout absent. To test the intended lowest-key branch, root is now rerunning with
explicit `set_multigraph(graph,True)` **before** the relevant writes; that corrected
run was pending when this review was written. It should record:

1. GraphKey, raw mode/IsMulti and successful mode-setting result around creation;
   the actual row keys/qualifier weights after commit.
2. Both scalar leaves plus children0/5 and `#` for this triple after each transition.
   Expected mode-on state is scalar10, children0=10/5=1, count2 in both directions.
3. Functional-index name/type class and argument order (or an already hash-stamped
   provider installation receipt) to tie raw SQL to the expected callback. The
   current mismatch/state receipts do not explicitly trace callback entry/args.
4. Native searches against that **derived** mode-on graph, plus the retained
   mode-off branch. The correction must not relabel the failed9,000 run as pass.

If those facts yield scalar1 while the actual callback is PutKeyed in mode on,
then investigate OtherEdgeKeys' query visibility/count, the child map, callback
argument values, compiled class/index version and any later writer before claiming
a zero-ekey or lowest-selection defect. Present evidence does not reach that case.
General concurrency, transaction rollback, native numeric/key collation and every
competing writer remain outside this one fixture conclusion.

## Evidence identities

- Original script SHA256 `d66b7704f41fa63d4cf5c7e092ef0857bfddbdafdf135f4a175c25c66e9e8aec`.
- Original JSON `69e80dfd64db1066f8f9ad2627996f4864b0b6e1d3b5ba143262aa9ee7063336`.
- Original log `7ec699c6e04ab90dbb8cf13d363da17744e0a21592079d93b78c8254da488c8c`.
- Follow-up state JSON `1fca473bbdab81aa27e9b23e2aae698c909a64968cd9e9ac7a87f12f7bc27be3`.

All are builder/root-owned native observations inspected by this independent
reader; no native replay was performed here. This correction supplies neither a
new weighted proof nor evidence of foundation convergence.

## Corrected mode-on native addendum

Root's subsequent frozen weighted-native.json now reports AGREES on9,000 paired
search cases, zero mismatches and14 public cases. I inspected it without replay.
The corrected fixture enables multigraph mode before writes, records IsMulti1,
and retains SQL rows key0/weight10 and key5/weight1. Out/in scalars are10; the
recorded children are0=10,5=1,#=2. The derived adjacency optimum is4 through the
two-edge alternative, while the all-parallel-row optimum would be1. This directly
corroborates the mode distinction and refutes the proposed special zero-key fault
on this sampled producer state. It supersedes the pending-run status above, not
the original retained failure/oracle diagnosis.

The corrected run stamps ten selected product pin/export/current blob identities
(all equal), helper inputs and current source hashes. It reuses the root's existing
exact-class runtime setup; the functional callback was not independently exported
or instrumented anew here. Therefore callback installation/compiled-body fidelity
remains a provider/setup correspondence condition, not an additional proof from
this file. No concrete mismatch remains in the corrected branch. General keyed
transitions, mode-history/restore and direct competing Reweight paths retain their
existing qualifications and findings.

Corrected script SHA256 `dde0f86d14bc002abcf6617f40537c7125b033d7208f4dc2ff953781eb9a46d8`;
corrected native JSON `ddf341b286f9297e526c8ffa704f392f72aa787d751fd35e84e0e8cc30e6c8c1`.
Observed native run time8.03s; review itself made no native/network calls.

## Intended weighted parallel-edge policy remains separate

The corrected native result does not itself decide whether weighted shortest
path **should** optimize every stored parallel relationship or the lowest-ekey
representative graph. USER_GUIDE631 promises cheapest-by-edge-weight. Spec234
FR004 mandates the scalar layout, but FR015 and its clarifications explicitly name
Arno/^NKG/PPR/BFS/PageRank collapse, not Dijkstra. The spec's user story also says
path-returning traversals report parallel edges. No inspected statement explicitly
authorizes weighted shortest path to ignore a cheaper nonlowest relationship.
Research R5's weighted-PPR discussion is not a Dijkstra policy decision, and later
PPR requirements cannot be inferred to settle the weighted-path contract.

I recommended an open question to root: which relationship set should weighted
shortest path optimize in a multigraph? Preserve the desired minimum-cost rule,
state the observed representative behavior as **today's** projection, and keep
the new numerical theorem scoped to the derived adjacency graph. A future all-
parallel-edge policy could change that reader's producer without changing FR004's
compatibility leaf or discarding the generic positive-weight queue proof. No new
weighted bug or provisional owner answer is inferred from the present ambiguity.
