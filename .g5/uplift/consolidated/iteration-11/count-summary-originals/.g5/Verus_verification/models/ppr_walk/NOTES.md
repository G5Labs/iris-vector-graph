# PPR walk, producer limit and final readers

Product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`; iteration9 foundation
`e56c8592b040abb08eafefed65ae17e2f56bd673`. This is an exact mathematical
source model plus finite actual-Python correspondence, not a native body or
floating-point refinement proof. Canonical owners are `algorithms.op.ppr`,
`algorithms.op.ppr.completion`, and the open `algorithms.op.ppr.zero_ties`.
The existing P cache/row models, `pagerank_admission`, and `graph_structure`
cache/degree contracts remain substantive hits; this package adds walk arithmetic
and the capped producer through its final readers, not fresh cache correctness.

Current baseline: **103 verifier units = 68 proof declarations (30 named
theorems, 38 helpers) + 35 recursive-spec termination checks**, all new, no
imports. All **24 named controls** fail decisively in their isolated ordinary post/assert
checks. One whole mutant (`producer-cap-ignored`) also reaches a collateral
resource limit elsewhere; its isolated capped-row helper fails cleanly and no
resource failure is used as control credit. Latest **26 proof/control/binding
receipts** are fresh and expected in the iteration10 validation.
Nothing is implementation-verified. No unchecked declarations, `assume`,
external proof, crate, product edit, native connection or network operation was
added. The pinned verifier uses four threads and its bundled vstd only.

## Producer and deciding state

`scoped` derives this graph's node list from raw `(graph,id)` rows;
`valid_seeds` intersects the raw seed IDs with those nodes and deduplicates the
set used for the uniform share. It merges native `NodeSeeds` membership and
`Run` set construction mathematically, not their full ordering/JSON/SQL APIs.
Scoped uniqueness is the node-table key premise. Graph normalization and seed
wire types remain providers. `theorem_scoped_members` and
`theorem_valid_seed_set` establish actual membership; no supplied membership bit,
normalized transition matrix, rank map or convergence Boolean decides the walk.

Each raw edge has graph/source/predicate/target plus an optional stored `#`
count. Absent count means one; otherwise `copies` expands the raw count into
individual slots. `hops` derives eligible forward and enabled reverse slots
from those rows. The divisor is their **number**, never their sum of weights.
Exclusions remove the same edge from transfer and divisor. Only empty and bare
predicate-ID exclusions have a new formal claim; `Type.p` prefix parsing/matching
is observed through actual Python cases and remains outside that claim.

`initial` deposits `1/distinct_valid_seed_count`. `scatter/ship` derive each
outgoing transfer and dangling score; `next` distributes `(1-alpha +
alpha*dangling)/seed_count` to seeds. Generic finite-sum proofs give
`sum(next)=1-alpha+alpha*sum(old)` for forward or unit-reverse traversal, hence
initial and every repeated step have mass one in the stable closed graph domain.
The raw preparation theorem derives hop endpoint closure from raw edge endpoints
and the selected node rows. `deposit`'s out-of-range totalization is not a claim
about malformed/orphan/unstable native adjacency; those states are unassessed.

`iterate` installs the new scores before testing the actual summed absolute
change against **nonzero holders times tolerance**, strictly `<`, or the
iteration cap. Disappearing score coordinates contribute to that change. Zero
and negative tolerances remain admitted; zero change does not pass zero
strict tolerance. This proves finite recurrence/termination and its cap, not
stationary-distribution convergence, an accuracy bound or arbitrary native
roundoff behavior.

For bidirectional weight `w>0`, the two-node witness derives `(w/2,1/2)` and
mass `(w+1)/2`; weight zero disables reverse and uses dangling restart instead.
Nonunit mass is the documented as-built extension, not a new defect or policy.

## Native and cache boundary

Normal forward `Run` calls `Graph.KG.Adj.Degree`; it may read a cache, rather
than recomputing `hops.len()`. Native correspondence therefore requires that
answer equal the raw eligible multiplicity. Stable closed rows alone do not
prove it. Direct Python and native exclusion counting have their own recount
paths. **No new producer reach is claimed for `Adj.Degree`, `Count`, cache
writers, `_cached_algorithm` or the score-cache protocol.** Degree ABA/generation/
interrupted-writer risks and algorithm-cache history remain their existing
owners; ordinary rollback is not asserted to poison Degree.

The normal public/store correspondence also requires a freshly computed Owner
answer or a correct cached score map. `StoreProvider` executes the actual
`IRISGraphStore._execute_ppr` body while naming `_native_answer -> None`; it does
not execute `execute_ppr`'s `_cached_algorithm` wrapper. Thus an always-computing
port proves no cache-history validity. The root native fresh-graph cases avoid
that history, not all provider state.

The native input fragment has unique grouped `(graph,source,predicate,target)`
coordinates, complete faithful in/out mirrors, and completed ordinary keyed
coordinates with **positive** stored counts matching their keys. Native keyed
parallels share one grouped coordinate with its count; the SQLite fallback
expands them into physical rows. A raw sequence can mathematically repeat row
positions, but arbitrary duplicate coordinates are not claimed to be literal
native globals: that grouping/mirroring/count relation is a provider premise.
The mathematical count also admits zero; that is algebra, not universal native
map-presence correspondence. With a present `#0` and another positive outgoing
arc, native `Run` can create an explicit zero map entry. Store rows retain it;
the engine's direct class-fast branch filters `score>0`. Native underflow can
also affect zero presence. Those map-presence/numeric states are unassessed,
not new public refusals or ordinary-writer bugs. The binding's zero edge count
panel means an absent raw edge, not a malformed stored `#0` leaf.

## Final read projection and both counterexamples

`rows/sparse/rank/cut` derive sparse producer rows from the walk. `source_limit`
derives the real default **1000** from `excluded=None`; an explicit exclusion
list, including `[]`, forwards the positive top limit or unlimited semantics.
Nonpositive wire limits are represented by their common unlimited effect, not
claimed to be identical argument strings. A positive reader top takes precedence
over its default cap, even above 1000. No `top<=1000` restriction hides that case.

The full fallback reader sorts every node's score. The fast reader first ranks
and caps producer rows, then appends current absent IDs at zero in ID order and
cuts the result. It deliberately does not equate “missing from capped rows”
with “unreachable.” The raw-node projection represents the semantic reader
answer; SQL `TOP(limit+scored_count)`/index traversal and native enumeration
completeness are provider/finite-adapter correspondence, not a general SQL or
collation proof. Numeric IDs are abstract atoms equipped with an integer total
order. `decimal12` derives an ideal nearest decimal bucket (ties to even);
Python binary rounding, `$Normalize`, half boundaries and arbitrary IRIS ID
carriers are not universally proved equivalent to it.

`theorem_request_tiny_readers_differ` derives one iteration from a raw
seed->tiny edge plus an early zero ID at alpha `1e-13`. Exact scores are
`1-alpha, alpha, 0`; the tiny value and zero share a twelve-decimal bucket.
Fast top2 selects seed/tiny; full fallback selects seed/zero. The alpha `1e-11`
neighbor agrees. This preserves the unresolved ordering choice
[q-iter-008](../../open_questions.md#q-iter-008); root owns
[bug-plt-103](../../bugs_issues.md#bug-plt-103). No preferred policy is assumed.

`theorem_public_default_cap_gap_from_raw_seeds` is **generic for every distinct
raw node list N>1000**, each node an isolated valid seed. It derives positive
initial/one-step scores, the actual public `excluded=None`, top=N, producer1000,
a missing ID by finite cardinality, and the final reader's literal zero for
that positive seed. No input rank map/cap or supplied missing-membership flag is
assumed. The earlier three-node/cap2 witness remains a structural control, not
the only closure of actual 1000. This matches root's fresh native1002 case and
[bug-plt-104](../../bugs_issues.md#bug-plt-104); an intentional top1000 cut losing
mass is a passing neighbor, not that defect. No repair is implemented.

## Actual Python binding and observations

`binding.py` imports the exact exported pin and checks its blobs, runs the
actual public `kg_PERSONALIZED_PAGERANK`, actual fallback, actual `_execute_ppr`,
`_ppr_every_node`, and nine `ppr()` list-wrapper cases. SQLite executes the raw
node/edge SELECTs; its adapter translates `TOP` and supplies a named IRIS-order
collation for the selected finite carriers. Physical keyed rows expand count,
so duplicate predicates/keys affect the actual fallback's divisor. An
independent Fraction gather recurrence reconstructs degree and transitions;
it does not call the source port or receive a score matrix.

The unchanged actual fallback is observed with `sys.settrace` at the installed
rank/change/held line. Its actual iteration count, change, holders and mass,
and the line-oriented sparse ObjectScript port's trace, are compared with the
Fraction oracle before final score/read order comparisons. The ObjectScript
port is a transcription, **not IRIS execution or native equivalence**. The
class-fast provider and uncached store-body provider compute from raw edges;
three public missing-method cases execute actual fallback dispatch. Internal
errors and store errors remain raised; selected relational failures close the
cursor. All calls run under a socket-connect guard.

Final carrier: **450 core journeys**, **6 error/missing-provider neighbors**,
**13 refused inputs**, **9 actual list-wrapper readers**. All baseline output
and trace comparisons agree. Ten sensitivity checks comprise **six actual
Python method changes**, **three explicitly labeled source-port changes**, and
**one changed final score rejected against the unchanged input-derived oracle**.
A separately supplied stale-degree port returns mass5/6, demonstrating the
Degree-equality premise; it is not an observed native writer failure or a new
issue. Full public routing/auth/provider/permission/numeric protocols are not
newly formalized by these finite observations.

The wrapper tests observe its raw-score stable sort after the kg-method cut;
the mathematical `public` reader models the kg method, not all `ppr()` wrapper
ordering. Typed Python integer iterations are the formal carrier. A later
four-case actual fallback probe retains the allowed whole-float `1.0/2.0`
validation -> `range` TypeError boundary in
[the carrier probe](../../../uplift/consolidated/iteration-10/ppr-carrier-source.json).
It was noticed after the original predictions and is deferred/outside this
formal carrier; no native coercion or new issue is inferred here.

Root-owned native evidence is read/hash-audited, not rerun: six tiny/zero cases,
four1002-cap cases, and five prior reverse-weight cases. Their actual facts,
helper/source provenance and original logs are mandatory stamped flat inputs.
The new native6/4 facts concern actual fresh public store paths plus direct
fallback calls over the DB. Physical unavailable-provider dispatch was not
observed natively; only the named in-process provider cases execute that public
branch. Compilation provenance reuses setup5 PageRank deployment, not a new
exported compiled-body equality proof. No native run is counted twice.

## Failures, validation and replay

Predictions precede current bodies/model in
[iteration10/ppr-predictions.md](../../../uplift/consolidated/iteration-10/ppr-predictions.md).
Intermediate proof logs retain missing sequence, real-division, quantifier and
reader-composition obligations, including resource-heavy unsplit draft helpers;
all final helpers use ordinary checks with the same pinned flags. Draft source
snapshots were not all materialized; logs retain their failing source excerpts.
The first binding had zero baseline mismatches but missed one mutated final
append branch because top2 returned early; its DISAGREES receipt/log remains.
The corrected actual mutation uses top3, where that line executes. A later
native-fact parser wrongly required `samples` on the fallback summary; its raw
KeyError is retained and no pass receipt was emitted for that attempt.

First control replay had19 expected failures and5 `FAIL_ELSEWHERE`: those five
wrong isolated caller targets trusted changed helper contracts. They are not
credited as controls. The final manifest targets the false deciding-effect
helper contracts directly; see final receipts and raw named verifier logs.
There are24 declared controls, covering membership, duplicate seeds,
multiplicity, exclusions, reverse/divisor/restart/dangling rules, strict held
stopping, decimal/ID ranking and both producer/reader limits.

Selected pinned upstream unit files: `test_460_r270_ppr_networkx`,
`test_460_r276_ppr_fast_path_errors`, `test_460_r050_ppr_seed_list`,
`test_231_ppr_graph`, `test_235_ppr_exclude`, and
`test_ppr_bidirectional_passthrough`: **87 passed, 2.14s pytest / 2.97s guarded
wall**, zero socket calls. NetworkX's pure Python reference executes there;
no native/e2e/database deployment result is claimed from those units.

Replay with the exact binaries/commands and final receipt selection in
[iteration10/ppr-handoff.md](../../../uplift/consolidated/iteration-10/ppr-handoff.md).
Proof/control/raw stdout, original failed attempts, costs and freshness audit
remain under `results/ppr_walk/` and iteration10 `ppr-*`. No product/shared
foundation/ontology/Git/live-target-runtime/native writes were performed by this builder.
