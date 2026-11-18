# Obligation census

The denominator of ontology obligations, per canonical block, under the harness rule
[uplift-scoring.md, "Census of ontology obligations"](../../../../harness/guidance/uplift-scoring.md) (frozen harness:
`$G5_HARNESS/guidance/uplift-scoring.md`) and uplift-review.md "Coverage through child blocks". Established in
iteration 61 ([handoff](../../uplift/consolidated/iteration-61/HANDOFF.md)).

```sh
python3 .g5/Verus_verification/tools/census.py            # from the repository root: validate, print, write summary.md
python3 .g5/Verus_verification/tools/census.py --init     # add new blocks as not-started; refresh not-started hashes
python3 .g5/Verus_verification/tools/census.py --dir D    # same checks on a working copy of the three TSVs in D
```

Exit 0 means every check passed. [summary.md](summary.md) is written by the same run; regenerating gives identical bytes.

## Files

- `blocks.tsv`: one row per canonical block (`[I · id]` / `[D · id]`) in `.g5/ontology`: page, kind, `sha256` of the
  block's own governing text, `status` (complete | partial | not-started), obligation and exclusion counts,
  `structural_zero` (reason when a complete block counts zero obligations; its percentage is then N/A), `parent` and
  `children` as declared by the block's `Expands:` / `Children:` metadata (block targets only; question links dropped),
  `owners_checked` (for each restatement or structural claim, the owner that was checked), `iteration`.
- `obligations.tsv`: one row per counted obligation, id `<block>#oNN`. Columns: `locator` (lead | bullet N | row N |
  exception N | working-assumption N, with a short quote prefix), `statement` (paraphrase keeping its conditions),
  `cases` (neighbouring inputs/histories that must give different results), `observation` (the reader), 
  `model_locators` (`path::item`, `; `-separated), `premises` (domain and premises), `grade`, `design_check`,
  `check_scope` (full | narrowed | n/a), `design_receipts`, `as_built` (`<kind> <verdict> <path>` entries, kind
  binding | native | upstream-test | inspection, or `none`), `parent_entailment` (child obligation ids and the
  argument, or `residual: <case where every child holds and the parent fails>`), `gap`, `grade_source`, `iteration`.
- `excluded.tsv`: id `<block>#xNN`, kind (rationale | undecided-alternative | navigation | evidence-annotation |
  restatement | definition | cross-reference), `owner` (for a restatement: the owning obligation id; the owning block id when the restatement spans several of its obligations or
  when that block is not yet enumerated), reason.

## Block hash

`sha256` of the lines from the block's `[K · id]` tag up to (not including) the next `<a id=…>` anchor or Markdown
heading, each line right-stripped and trailing blank lines dropped, joined with `\n`. The `### id` metadata section
(after `## Metadata`) is not part of it. A graded block (complete or partial) whose hash changes is reported STALE and
fails the check until it is regraded; a not-started block's hash is refreshed by `--init`.

## Counting rules (the master's published rules, applied exactly)

1. Read each block's own lead, bullets, prose, tables and exceptions. Split a claim when one outcome can fail while
   another still holds; keep conditions with the outcome they qualify. Count a restatement once at its owner and point
   aliases to it (`excluded.tsv`, kind `restatement`). Do not count Sources/Provenance/Findings metadata.
2. **full**: the formal rule distinguishes the required cases through the stated observation, directly or by documented
   composition. A model label, code locator, native observation, binding AGREES count, test pass or successful proof
   without the necessary property does not make an obligation full. **partial**: the model represents some of the
   cases, or stops before the reader, or takes the decision as an input. **absent**: no formal rule represents it.
   **unassessed**: not yet judged.
3. Design check is separate from representation: a modeled counterexample (witness) of an as-built violation is
   `refuted` with representation full when the witness reaches the stated observation; a proof over all sizes is
   `proved` (`check_scope` full only when it covers the obligation's whole stated scope without premises the product
   does not establish, otherwise narrowed); an explorer or finite-domain result is `bounded` with its domain; a
   failed or timed-out run is `unchecked`; no formal check is `none`.
4. Reuse an existing grade only when its statement, model, premises and evidence still apply: the cited theorem or
   witness still exists, its latest receipt is fresh (the tool checks that each cited receipt is the latest of its
   kind and label and that its recorded inputs are unchanged), and the coverage.md wording matches the current block
   text. Blocks moved by the reorganization keep their IDs; the crosswalk's "new" label on moved blocks is a
   relabelling artifact, not a new statement.
5. Parents: identify what the parent promises beyond its children. If it only restates them, record zero additional
   obligations after checking each owner (`structural_zero`, `owners_checked`). Otherwise list the child properties
   and either document why they jointly entail the parent obligation under compatible premises (inherited coverage)
   or keep the parent obligation open with the case where every child holds and the parent fails. An ordering,
   shared-state or completion guarantee across children can be missing while each child passes.
6. Check current models even when a block has no registered Verus link: search `models/*/manifest.json`
   `ontology_ids`, NOTES.md, coverage.md and `crosswalk/decision-links.tsv` for the block id and for the behaviour.
7. A stated working assumption about current behaviour is an assessable obligation within its scope; a working
   assumption that only states a preferred policy option is an undecided alternative (excluded with reason). Rationale,
   pure navigation and evidence annotations ("Iteration NN … observed") are excluded with reason.

## Reporting

Per block, per page and pooled over the enumerated scope (complete + partial blocks): the four grade counts,
`full/total` and, with unassessed entries, the lower bound `full/total` and upper bound `(full+unassessed)/total`; the
count of obligations proved over their full stated scope, with proved, bounded, refuted and unchecked counted
separately. A block with an empty denominator is N/A. Not-started blocks count zero obligations (not N/A). While any
block is not-started or partial the tool prints "enumeration incomplete: whole-foundation percentage unmeasured" with
the enumerated block count and never prints a whole-foundation percentage.
