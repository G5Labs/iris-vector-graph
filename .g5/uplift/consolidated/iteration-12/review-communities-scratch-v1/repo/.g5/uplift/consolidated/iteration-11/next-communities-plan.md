# Communities continuation survey and next-model plan

Selection and predictions are in next-communities-PAIRS.md. This source-informed
survey is preparation only, not new formal or independent grading credit.

Actual Graph.KG.Algorithms.WCCJson/CDLPJson enumerate default-graph out/in node
subscripts, union them into initial self labels, then create newLabels from old
labels synchronously. WCC scans out/in neighbors to take a minimum, counts changed
labels, installs the entire new map and stops only after a no-change round. It
checks maxIter before starting the next round; a budget can therefore refuse even
if the last updated labels already happen to be the final component map but the
no-change round was not run. Empty adjacency returns{} before the loop. CDLP
counts neighbor labels across both directions/predicates, excludes self-loops,
chooses maximal count then first label in IRIS collation, installs synchronously
and stops on no change or the fixed budget. A two-node pair oscillates by parity;
there is no convergence promise for CDLP.

Both native kernels enumerate adjacency nodes, not a supplied SQL node set. Actual
public kg_WCC/kg_CDLP call complete_labels(core_result, list(_loners())) outside
the shared core cache. complete_labels preserves existing labels, adds absent
loners as self labels and sorts by collation. _loners first pages the actual native
Edgeless census, then uses SQL on failure. The store core cache is keyed by params
and adjacency token; explicit WCC limits bypass the native reader in favor of the
Owner. Strict membership readers and native-result refusal/fallback are already
substantive procedure_results/routing hits. Existing graph_structure models and
native WCC rollback evidence remain genuine cache-writer counterexamples; P
acache_l2's node version is a counterfactual input the pin does not generally have.
The PageRank COUNT:MAX producer applies to global score membership and is not
silently transferred to WCC/CDLP's differently placed live completion.

A useful correction to the initial broad cache concern: an isolate insertion
leaves the adjacency token unchanged, yet WCC/CDLP may safely reuse cached core
labels because every public call adds the fresh loners. No new node-token bug was
found here. Native18 preparations pass, including actual two-connection isolate
insert: both core cache hits increase while the public result contains the new
isolate. Ordinary isolate deletion also removes it from both public answers (that
writer does move the token and causes misses in this observation). This is not an
all-writer, rollback, race or ABA guarantee. A previous bare cache-key model misses
the consumer composition even if its abstract node-token rule is stronger.

Root native files retain18 prefix-projected checks: raw WCC fixed point and public
loner completion; raw/public too-small round refusal; raw/public CDLP rounds1..4
with odd/even swap, self-loop exclusion and two-predicate majority; warm cache;
two-connection isolate insert/delete. Fresh disjoint task-owned components coexist
with prior task fixtures; only their prefix is asserted. No global erase, security,
DDL, parallel-mode mutation or new formal/issue credit. Native numeric-ID collation,
malformed provider shapes and full native reader equivalence were not tested.

The physical-key multiplicity prediction remains conditional and unconfirmed.
CDLP's source adds1 for each (direction,predicate,neighbor) coordinate and never
reads #/key children. Different predicates give distinct votes, as the native
majority neighbor confirms. Repeated keyed rows of one triple are collapsed in
this source projection. The guide says each edge one vote, while the earlier
multigraph spec documents set semantics for PPR/PageRank/Arno and does not settle
CDLP here. Do not count a new defect or weaken the governing each-edge commitment
without a dedicated intent/projection comparison. Preserve that unresolved boundary
in any next paired ledger. WCC's partition is multiplicity-insensitive.

A substantive post-archive implementation should:

1. Start with raw selected scoped coordinates and node rows; derive neighbor
   lists, initial adjacency member union and the faithful mirror condition. Do not
   accept a component map, prepared vote count or converged flag. Ordered atom IDs
   can model IRIS order with full collation as an external correspondence boundary.
2. Model actual synchronous WCC scan/fold/changed/install/guard order. Prove every
   label originates in its reachable component, decreases monotonically, reaches
   the minimum by finite path-radius propagation and terminates with at most N
   rounds including the final unchanged round (empty separately). Derive component
   connectivity from raw edges; a supplied partition/shortest answer is inadequate.
   Establish success/no-change and explicit budget refusal, including the already-
   correct-but-not-yet-confirmed boundary. Require sufficient mirror symmetry for
   the ordinary undirected meaning; keep unfaithful providers outside that theorem.
3. Derive CDLP frequency bags from raw coordinate scans and old label state;
   prove majority/tie/self-loop and synchronous parity witnesses, finite budget
   termination and fixed-point stability. Never claim it must converge. Retain
   keyed-edge projection as a distinct qualified role rather than invent counts.
4. Derive live loners from raw SQL node/edge membership (including only-self-loop
   versus no-edge), apply actual complete_labels and demonstrate cache core reuse
   plus new isolate completion. Include successful empty versus failed census and
   explicit native/SQL paging/readers if claimed; arbitrary SQL snapshot/driver
   failures remain providers. Existing cache-write/rollback facts must not be erased.
5. Bind actual Python core-dispatch, store strict reader and public completion to
   functional raw graph answers with an independent BFS/label-vote oracle and actual
   source mutations. Controls should change direction/mirror use, WCC no-change/
   guard order, CDLP sync/self-loop/count/tie and cached-core-plus-live-completion
   separately. Refuted forecasts, unsupported carriers and failed runs stay visible.

No new model may start until the next iteration before archive. Existing public
feedback cases are known selection inputs, not fresh evaluation. Native/full-body
verification and repository-wide completeness remain0/unclaimed. The current
vector/rational builders continue independently; this plan does not replace them.
