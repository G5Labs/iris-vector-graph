# Verifier-unit classification correction

The iteration11 independent source/per-function audit corrected a label used in
iteration10 summaries. PPR still verifies103 units, with the same model, controls,
claims and receipts. Its actual decomposition is68 proof declarations (30 named
theorems,38 helpers),18 recursive-spec termination checks and17 internal nonlinear
arithmetic subqueries. The previous label '35 recursive-spec termination checks'
wrongly combined the18 recursion checks and17 arithmetic subqueries. An internal
subquery is not an additional independent theorem.

Iteration10's146 new units therefore comprise108 proof declarations,21 recursive
spec checks and17 arithmetic subqueries. The45 unchanged imported JSON-search
units remain separate;191 total units including imports is unchanged. No gain,
proof result, source binding, issue count or policy decision is added by this
classification correction. Fusion's existing11 total is already correct:7 proof
declarations,2 recursive specs and2 arithmetic subqueries; no explicit incorrect
subtype claim was located there.

The [independent audit report](count-audit-report.md) and results/logs preserve36
sequential scratch commands, full PPR103/fusion11 runs, each recursive spec's1-unit
run and each relevant proof's1-plus-subquery count. Stable source scan covered37
model files and excluded both mutable iteration11 candidates. PPR and fusion are
the only stable source files with explicit nonlinear_arith sites. The audit took
about45.23 verifier wall seconds; no source, model, manifest or solver flag changed.

The original10 commit cb02a64d and its external after archive, plus11's before
archive, are immutable. Original summary/document bytes before these current
working-tree annotations are additionally preserved in count-summary-originals
with a hash manifest. Historical raw receipts, process logs and independent-review
artifact copies are untouched. Current summary values and PPR NOTES are corrected;
historical review hash equalities describe their original frozen snapshot, not a
requirement that later documentation edits preserve that document hash. Source,
model, binding and control hashes are unchanged, so their proof/evidence freshness
does not depend on this prose correction.

All26 latest PPR proof/control/binding input hashes still match after this
documentation correction (count-correction-ppr-freshness.json). A global checker
run during iteration11 construction correctly reported only the two moving new
packages' unfinished expected-count metadata; that log is retained, not a final
consolidated pass. It found no PPR freshness problem.

The current validation display also fills its formerly null verified/error counts
from each unchanged raw receipt's observed object. This corrects a summary reader
that looked for a top-level verified field; no solver result is recomputed. Full
mutant resource flags are displayed separately from the independent ordinary
named-obligation failures.
