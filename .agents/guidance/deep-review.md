# Deep PR review

Review the current PR's implementation against the changed and relevant ontology and
all initial requirements, including accepted clarifications. Use these commitments
and what is reasonably inferable from them to decide what constitutes a defect and
how severe it is.

Use the native review and fix loop. In each round, review and fix confirmed defects
introduced or worsened by this PR: bugs, gaps, regressions, unnecessary design
complexity, duplicated code paths and other issues within those commitments.
Validate the fixes, then start a new review round against the full scope. Stop when
a round finds no issues or the user's budget is exhausted; default to at most
10 rounds when no budget is specified. Budget exhaustion is not a clean review.

Quality-of-life feature improvements whose behavior is neither required by the
ontology or initial requirements nor reasonably inferable from them are not defects
to fix. Do not expand requirements or weaken valid intent to justify a fix.

Finish with a concise report at
`.g5/pr_ontology_diff_design/<workspace-or-pr>/deep-review.md`: issues fixed,
ontology nodes vetted, checks and material remaining gaps, rounds completed and
why the loop stopped.
