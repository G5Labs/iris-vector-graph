# Iteration 3 seal

Input: clean `consolidated_uplift` at **0af2a61d1ab593f52f88c1343a0b4f11a858d878**.
Implementation checkpoint: **6f32b507aa5c9b16c8aedf68bef1f8619347b7b9**.
Product remains **3eaa79cf77d3e0a879b2cced634cf2729d81499e**. The final seal is the
clean tip with subject **Seal iteration 3 with corrected snapshot evidence and handoff**;
`git log -1 --format=%H` gives its full hash, also supplied in the completion.
A commit cannot contain its own hash.

All changes are under `.g5/`. Both imported playbook trees, `.agents/`,
`experiment/g5-verus/`, the five inherited G roots/manifests/twin and every product
path remain unchanged. No push, issue/comment, publication, delegated agent,
other session, container/service change or security reproduction occurred.
The [input manifest](inputs.json) freezes hashes and discloses an initial overly
broad filename listing; no evaluator contents or hidden cases were read or used.
Independent review and grading remain pending.

## What actually ran

| New as-built family | Verified / named controls | Actual comparison and limit |
|---|---:|---|
| [history_diff](../../../Verus_verification/models/history_diff/NOTES.md) | **12 / 6** | **9481** real named Python diff pairs, including **8113** continuous endpoint comparisons; SQL/revision/snapshot writers are fixtures |
| [pagerank_admission](../../../Verus_verification/models/pagerank_admission/NOTES.md) | **9 / 6** | **16** engine/store/cache journeys, three calls each, plus isolate/self-loop and empty-census cases; actual IRIS cache/algorithm providers substituted |
| [aql_frontend](../../../Verus_verification/models/aql_frontend/NOTES.md) | **6 / 4** | **100** real lexer/parser/typed AST/translator/public-adapter journeys; Cypher consumer recorder, no query-result proof |
| [vector_threshold](../../../Verus_verification/models/vector_threshold/NOTES.md) | **6 / 3** | **32** actual Python node/edge SQL-builder/result cases on adapted SQLite with real cosine calculations; no IRIS preparation/result observation |

All **33 obligations** pass and **19 controls** fail in their named claims.
[Validation](validation.json) records the exact latest proof/control/binding
receipts and their hashes; their raw Verus logs are committed beside receipts.
The models use pinned bundled vstd, no actors and no assume/admit/external_body.
These are specification/transcription proofs. Expected native calculations are
unverified Python, and no product executable body is verified.

Selected product suites: **164 passed**, ten files, no skips, one AQL warning.
Exact cwd/command/environment: [upstream-unit.json](upstream-unit.json),
[raw output](upstream-unit.log). Consolidated gate **PASS**, zero ontology issues
or writing warnings: [gate.log](gate.log). A changed history proof input with its
old evidence is rejected, then exact original bytes restored:
[freshness control](freshness-control.json), [raw output](freshness-control.log).
Captured raw solver logs retain their original trailing blank lines intentionally;
whitespace checks exclude those immutable logs.

The inherited five G families/128 controls, local playbook reruns (**105** pairs),
**40** native IRIS observations and iteration 1/2 suites were checked applicable by
unchanged hashed inputs, **not rerun** here. No new ObjectScript/IRIS execution.
[Unsuccessful attempts](attempts.md) retain type/mode/count failures, structural
gate repairs and the corrected historical inference; no failed run is a pass.

## Controlled predictions and producer challenges

[PAIRS.md](PAIRS.md) retains all five initially sampled questions, the initial
predictions, actual differences, deferral and additional producer review. These
are judgmental builder questions, exposed to public feedback, with no independent
holdout denominator or repository-wide estimate.

- **Diff:** equal endpoints return no entries; reverse swaps before/after for
  `(lo,hi]`. For an uninterrupted life, arbitrary raw attribute histories preserve
  first prior and last value, dropping net zero. The model now relates those
  values to endpoint states; global full-content/sorting refinement remains open.
- **Corrected lifecycle finding:** actual `DeleteNodeRows` calls
  `NodeSnapshotJson`, which stores labels/properties. Simple delete/recreate
  retains old k=1 in inverse existence.after. The inherited empty-prior fixture
  cannot establish its broad missing-property claim; that inference is withdrawn
  without deleting its original artifacts. A stronger reachable history
  `initial1 -> set2 -> delete(snapshot2) -> recreate -> set3` loses range-prior1
  when the life closes. This strengthens **bug-led-101**, not a new bug count.
  `ledger.readers.diff.order` owns the still-unratified alternatives: displayed
  lifecycle entries with deletion-moment snapshots (working default), or a complete
  endpoint delta/applicable script with range-start values and defined tie order.
- **PageRank:** unchanged COUNT:MAX, parameters and adjacency token hit without
  loner census; adding an isolate changes the key and recomputes, including its
  fixture score row. Failed census is unknown and uses the legacy list, while a
  successful empty table is known `0:0`. Independently discovered **I3-PR2** follows
  raw has-self-loop through `_edgeless.edgeless`: a self-loop-only loner permits a
  native eligibility probe; a true isolate forces Owner. This is not unconditional
  Native routing. Actual numerical normalization and snapshot concurrency remain
  unproved, and the Owner's existing **F-1003** 10,000-row cap remains explicit.
- **AQL:** raw `..` remains an integer-range token and both bounds reach the Cypher
  text; decimal depths refuse before execution. Literal null equality/inequality
  becomes IS NULL/IS NOT NULL; text `"null"` remains a value. Producer and consumer
  controls detect changes. The public adapter hands exact text and bindings to
  Cypher; no traversal or SQL result equivalence is claimed.
- **Vector helpers:** omitted threshold keeps all eligible rows, threshold0.5
  excludes score0.25 and includes equality; the predicate precedes limit and
  carries the repeated vector bind. Actual builders/readers and adapted SQL results
  agree. The relational/cosine provider, float domain and IRIS dialect remain
  explicit premises, separate from other KNN/fusion surfaces.

The additional underserved-area review was vector threshold/results after the
first three proof packages, followed by the raw self-loop producer challenge and
a bulk-node producer/consumer inspection. **I3-BULK** remains in the sample as
deferred: default/named node graph, labels/properties, guarded merge and readback
were inspected, but no server/SQL label-property equivalence proof was added.
The existing ID-only family does not close that gap. Further scalar additions or
links would not close the full transaction/content boundary; that is the concrete
next campaign, alongside the unresolved lifecycle policy.

## Registers, coverage and public predictions

All inherited anchors remain: **428 bugs/issues, 55 simplifications, 140 questions**.
Crosswalk source rows remain **443 / 56 / 141**; [breakdown](register-counts.json).
No new confirmed defect, simplification or owner decision is claimed. bug-led-101
has corrected premises and stronger model/unit evidence. F-1003 is retained;
F-1004 and bug-plt-017 are explicitly recognized as the same PPR creation trigger,
with the inherited deletion premise still refuted. They are not discoveries here.
RC-16/RC-28 gain scoped frontend/predicate evidence; no shared repair is implemented.
q-con-002 now has a canonical owner, both policies and the snapshot correction.
Imported long-tail entries not semantically compared remain marked as such.

[Coverage map](../../../Verus_verification/coverage.md#improvement-iteration-3-2026-11-15)
and `tools/inventory.py`: stable denominators **3077 Python definitions**, **972
ObjectScript members**, **14 SQL files**. Direct scoped source links **70/3077**
and **25/972**; indirect-only **6/0**; SQL **0/14**; **127** binding rows across
**30** blocks, **20** with producer/writer and reader/consumer. Two support constants
excluded, zero unresolved, implementation-verified **0**. Link counts do not measure
complete symbol semantics or behavioral percentages. No old denominator is rewritten.

[Known32 predictions](public-predictions.tsv) preserve identities/cohorts. Before
columns use public feedback-2, including its M03/M04/J03 promotions. The only new
public formal completion prediction is **M05's scheduled inverse/equal distinction**;
broader semantic lifecycle inversion stays open. M21/J04, full reconstruction/export
fields, restore-to-readers and other gaps stay scoped as before. No prediction or
grade is made for hidden cases or a fresh evaluator draw; builder-selected controls
are reported separately. Known case totals are not recomputed as self-grades.

## Replay, review and strongest remaining gap

[Runbook](../../../Verus_verification/runbook.md#improvement-iteration-3-on-this-mac)
contains copyable proof, snapshot control, Python binding and consolidated gate.
Verus: `~/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus`;
actors inherited at `~/.cache/g5-verification/ivg-actors-c03f9fa`, unused here.
Python3.11.8, exported pin/venv reused from `~/runs/ivg-consolidated-20261114`;
new scratch/logs in `~/runs/ivg-iteration3-20261115`. The imported trees are immutable.

**Strongest remaining gap:** full lifecycle diff/content correctness against both
named reconstructed states, including deletion snapshots and their application
policy. The per-attribute continuous-life theorem does not close it. Actual IRIS
ApplyAll/prior production and transaction rollback correspondence also remain
unexecuted. Other open areas: restore-to-width/window, bulk child-value equivalence,
algorithm numerics/output cap, WCC/CDLP consumers, route winner statistics, warm
content/concurrency, CALL row evaluation and broader FHIR/HTTP/Bolt/translator semantics.

Reviewer package: [canonical-only self-check](reader-check.md), [sample](PAIRS.md),
[runbook](../../../Verus_verification/runbook.md#improvement-iteration-3-on-this-mac),
latest receipts/logs in validation.json. Attack first: (1) whether full snapshot
priors change the stronger lifecycle witness and what the API promises there;
(2) whether node-token concurrency/nonreuse, native eligibility and fixture scores
are mistaken for a numerical/freshness proof; (3) whether AQL/SQLite provider
boundaries can be enlarged without new correspondence evidence. Independent review
is pending; no sub-agent or external reviewer was used.

No shared method instruction was changed. The demonstrated failure was trusting
a hand-built record premise: inspect the decisive writer, retain the valid neighbor
and compare the consuming reader before preserving a defect claim. Existing guidance
already requires that, so adding another instruction would be redundant.

Costs: first recorded work timestamp **2026-11-15 06:45:46 UTC**; final validation
at **2026-11-15 07:10:25 UTC**, **1479s** later. Earlier instruction/source reading is
unmeasured. Selected tests: **2.00s tool / 1.45s pytest**; recorded consolidated
gate **3.15s**. Solver CPU/total solver wall, per-package authoring cost, token/billing
and cache charges are unavailable. There was no evaluator execution in this chat.
