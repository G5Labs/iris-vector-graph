# Independent DijkstraCost source and invariant review

This source review follows [frozen expectations](cost-review-expectations.md).
The new candidate was first inspected as a142-line initial scaffold. This is an
architecture assessment; final proof/control/binding replay remains pending.

## What the source actually computes

`TraversalPaths.DijkstraCost378-448` has two per-node distance/hop maps and two
queues with exact decrease-key, unlike JSON's retained stale entries. Both roots
start at0. The cheaper queue minimum is settled, forward on a tie; completed nodes
are skipped on later relaxation. An admissible arrival checks the opposite label
even if it fails to improve its own label. Best and BestHops change only when the
meeting sum strictly improves. A later equal-cost lower-hop meeting is ignored.

Each tentative label can carry a ghost walk derived by extending its accepted
predecessor. That walk explains the actual Hop map. At strict Best update, retain
an immutable forward walk plus reversed backward walk and their length. These
ghosts never decide the search. Correctness does not require a mutable live
meeting vertex or the least hop count among cheapest walks. The initial candidate
does this faithfully; its Best<=every current dual-label sum plus historical
feasible walk is sufficient. No supplied optimum or terminal trace is necessary.

The raw graph must have equal-effective-weight reverse coordinates for selected
arcs. The actual ordinary adjacency writer writes these, but a stable graph alone
does not imply them. Inherited mirror4's20/none and20/11 counterneighbors refute
silently transferring the one-sided theorem to arbitrary raw state. The initial
candidate's explicit `frame` requires the appropriate out/in transpose after
direction and predicate selection. Effective equality suffices; raw scalar
identity is stronger than needed. Children-only/missing scalar at a present
coordinate still has effective1, distinct from an absent coordinate.

## Sufficient crossing argument

Let P be any selected s->t walk with cost D<=cap, and assume Best absent or D<Best.
Positive effective weights make every prefix/suffix cost<=cap. Per-side closure
and accepted optimality must already have been derived from actual transitions.
Let i be the first vertex of P not forward-Done and j the last not backward-Done.

- If i does not exist, forward-Done at t has cost<=D and backward root t has0;
  the meeting invariant contradicts Best absent or D<Best. The symmetric case
  handles nonexistent j.
- If i>j+1, a vertex between the boundaries is Done on both sides. Its settled
  prefix/suffix minima and meeting invariant give Best<=D.
- If i=j+1, the crossing edge goes from a forward-Done vertex to a backward-Done
  vertex. Forward closure across that edge gives a forward label no dearer than
  its prefix, while the backward settled label costs no more than its suffix.
  Their meeting again gives Best<=D. If the neighbor was skipped as Done on the
  relaxing side, accepted optimality against the predecessor witness plus edge
  already supplies that closure inequality.
- Thus i<=j. The first-unsettled prefix and last-unsettled reversed suffix give
  queued labels. Their minima sum<=prefix(i)+suffix(j)<=D. An empty frontier is
  impossible; a frontsum>=Best contradicts D<Best.

This handles walks with repeated vertices and uses no preselected shortest walk,
global optimum, minimum-hop optimum or simple-path-only premise. Finite oracle
enumeration is useful for sensitivity but cannot substitute for this lemma.
Cap-equal labels remain admitted; a settled cost>=cap cannot have an admissible
positive outgoing extension, so skipped expansion preserves closure vacuously.

## Completion and wrapper obligations

Each Continue settles a previously unaccepted (side,node); exact queue and Done
skip prevent reinsertion. A finite source+target+raw-endpoints universe gives a
strictly decreasing remaining-side-node rank. The final package must derive an
actual finite terminal trace and terminal correctness, then combine them.

If Best is admitted and historical BestHops fits H (or H0), its constructed walk
proves bounded feasibility at the unbounded minimum. If positive H excludes that
snapshot, the source calls actual JSON on the unchanged raw graph/cap/H/direction/
predicate selection. An imported terminating JSON trace must decide the fallback,
with its existing theorem establishing the result afterwards. A choice filtered
by optimality would be circular; a choice filtered only by actual terminal-trace
relation, whose existence is proved, is legitimate mathematical determinism.
No unbounded admitted path implies no bounded admitted path, so absence needs no
fallback. Distinct endpoint core and nonempty self special0 must remain separate;
the source's empty endpoint refusal and public coercion/refusal are separate
carrier correspondence, not consequences of ordered integer node atoms.

No source defect or new inherited finding is asserted by this architecture review.
q-iter-007 remains open. Integer arithmetic, stable graph, reverse-provider frame,
raw argument coercion, floating summation and JSON formatting limits must stay
explicit in final NOTES/canonical wording. Final acceptance awaits the complete
derived proof, named altered-rule controls and executing-port/Python evidence.

## Equivalent simpler frontier proof and native supplement

The builder proposed a simpler formulation, independently checked here. Follow
P's forward-Done prefix and derive forward dist<=prefix by closure. At its first
forward-unsettled x, the exact queue contains that forward label. If x is backward
Done, accepted backward optimality on the reversed suffix plus the dual-label
bound already contradicts Best absent/too dear. Otherwise the per-side backward
frontier lemma on that reversed suffix supplies a queued cost<=suffix. Summing
the two queue minima gives<=D. If all P is forward-Done, use the dual label at
dst/rootBackward. This subsumes the indexed crossing cases above without assuming
a shortest path. Either formulation discharges the same material obligation.

Root's [Cost15 receipt](root-cost-native.json) now records15/15 agreeing actual
native Cost/JSON and public cost-only results across A1, equal-cost-hop tie,
frontsum and first-meeting cap/H neighbors. All20 fixture triples have observed
equal out/in points, seven selected product blob pin/export/current identities
match, and setup5 compiled-class provenance is reused explicitly. I inspected the
receipt without runtime calls. It does not instrument BestHops or prove which
fallback branch ran; those source/internal claims remain formal/port obligations.
"Native9" in the assignment meant iteration9 evidence (9000pairs/14public,
18boundary neighbors and mirror4), not a separate nine-case Cost receipt.

## Retained correspondence correction before acceptance

The first complete candidate passed81 and binding20,736 in my scratch copy, but
the builder identified a scan-order mismatch before final freeze. A single shared
filtered Arc sequence did not encode native `both`'s primary-orientation then
secondary scan with opposite primary orientation for the backward side. The
minimum-cost theorem permits arbitrary scan order, but a source-shaped BestHop/
trace relation must retain this distinction. Binding already used the actual
side-specific order; its independent Python transcription was therefore ahead of
that formal detail. Prior replay remains explicitly superseded, not final credit.

The correction adds `primary_tag(c,b)` and concatenates selected primary arcs
before secondary arcs. I checked Out/In/Both and both sides against the native
`tFwd/tBack/tK` relation. Membership/closure and finite-rank reasoning are unchanged;
the final proof/control/binding run must still be refreshed on these new bytes.
