# Iteration 64 regrade brief (identical for every fork)

You regrade one group of census obligations. Every fork receives this same brief and checklist.

Paths: REPO = /home/ziniu_wu_g5labs_ai/experiments/model-coverage-uplift-20261117/iris-vector-graph/iris-vector-graph
S = /home/ziniu_wu_g5labs_ai/experiments/model-coverage-uplift-20261117/iris-vector-graph/scratch/iteration-64
Your group directory: S/forks/<GROUP>/ ; your ids: S/forks/<GROUP>/ids.txt (every `full` and `absent` row of your pages).

## Hard constraints

- **Do not edit any file in REPO** (no census TSV, model, NOTES, coverage.md, ontology, tool). Write only inside your
  group directory. Run tools from REPO with `PYTHONDONTWRITEBYTECODE=1`.
- No Verus run, no binding run, no IRIS. Read-only inspection of models, NOTES, receipts, coverage.md, crosswalk,
  ontology and product source (product source is read-only; pin 3eaa79cf).
- No new obligations, no withdrawals, no renumbering. If you find a duplicate or a missing obligation, report it in
  your final message instead.
- Do not touch `erasure.kept#o03`, `erasure.kept#o05`, `erasure.atomic#o01` (the integrator handles them).
- If `/home/ziniu_wu_g5labs_ai/experiments/model-coverage-uplift-20261117/iris-vector-graph/STOP` exists, write what
  you have and return.

## Tools (scratch, read-only on REPO)

- `python3 S/tools/show.py ID [ID ...]` (from REPO): the start row, the block's governing text + metadata, each cited
  proof fn's params/requires/ensures header (POINT CHECK flagged), and each cited model's latest PASS prove receipt.
- `python3 S/tools/overlay.py S/forks/<GROUP>/work S/forks/<GROUP>/rows.tsv` (from REPO): overlays your rows on the
  start census in a working dir, runs the census tool **with the new strict-grade lint**, prints every problem naming
  one of your ids, and a change summary. **It must exit 0 before you finish.**
- The lint (in REPO `.g5/Verus_verification/tools/census.py`, function `lint`):
  - LINT-1: grade full with a non-empty gap ('none'/'-'/'n/a' count as empty) fails unless every ` || `-separated
    gap segment begins with `outside-statement:` (it names something the obligation's own statement does not require)
    or `owner-contradicted:` (the governing text is contradicted by source or by its own metadata; evidence follows).
  - LINT-2a: check_scope full fails when any cited proof fn has a `requires` clause, unless `premises` contains
    `requires-reviewed: <why every conjunct is a condition the statement itself states, or a model well-formedness
    fact every product input satisfies>`. If any conjunct narrows the statement's domain, record `narrowed` instead;
    if the narrowing removes a case the statement requires, the grade is partial.
  - LINT-2b: check_scope full fails when every cited proof fn is a point check (name `witness*` or no parameters).
    Record `narrowed`.
  - LINT-3: grade full fails when no model locator names a `proof fn`; a spec fn / definition / NOTES / model.json
    alone cannot carry full.

## Output

`S/forks/<GROUP>/rows.tsv`: tab-separated, header = the 17 obligations.tsv columns then `reason`:
`id block locator statement cases observation model_locators premises grade design_check check_scope design_receipts
as_built parent_entailment gap grade_source iteration reason`. **One row for every id in ids.txt**, in that order,
starting from the start row (copy from S/before/obligations.tsv) and changing only what the regrade requires. No tabs
or newlines inside cells. Write it with a Python script (csv with delimiter '\t', quoting=csv.QUOTE_NONE, or plain
'\t'.join), never by hand-editing a giant file.

For each row:
- `reason`: unchanged rows: `held: <one clause naming the proof and why a-g pass>` (full) or `held absent: <what you
  searched>` (absent). Changed rows: `<old> -> <new>: <checklist letters that failed> <specific reason>`, e.g.
  `full -> partial: b one entry point (execute_cypher) of three (Bolt, HTTP) proved`.
- Changed rows: set `iteration` to `64` and append `; it64 regrade: <short reason>` to `grade_source`.
- Downgraded rows: put the shortfall in `gap` as plain text (no tag needed for partial/absent).
- Full rows that keep a gap: rewrite each segment as `outside-statement: ...` only if it truly names something the
  statement does not require; otherwise the gap is a shortfall and the row is partial. Several segments are joined by
  ` || `.
- `check_scope full` kept: add the `requires-reviewed:` note to `premises` when a cited proof has `requires`.
- A partial row keeps a design check only over what it covers: `proved`/`refuted` with `check_scope narrowed`, or
  `none` with `n/a`. `full` scope is never right on a partial row.
- Every receipt you cite must be the latest of its kind for the model (overlay checks this). For a newly cited model
  use its latest PASS prove receipt (show.py prints it).

## Grade rules (README rule 2/3, unchanged) and the iteration-64 checklist

**full**: the formal rule distinguishes the required cases through the stated observation, directly or by documented
composition. A model label, code locator, native observation, binding AGREES count, test pass or successful proof
without the necessary property does not make an obligation full. **partial**: the model represents some of the cases,
or stops before the reader, or takes the decision as an input. **absent**: no formal rule represents it.

Regrade **every full row** against every item; any failure leaves the row non-full (record the letters):

- **a.** The cited property is a proof (theorem / lemma / witness) whose conclusion speaks to this obligation, not a
  definition, a label or an AGREES count. Read its `ensures` (show.py), not only its name.
- **b.** Its cases cover every condition, entry point and outcome the statement names (one entry point of several →
  partial). Check the `cases` column against what the proof actually distinguishes.
- **c.** Its observation is the stated reader, or a documented composition to it (cite where the composition is
  documented: NOTES, a lemma). A proxy, such as a row count standing for a reader, → partial.
- **d.** Decisive inputs are derived inside the model, not supplied as parameters (the decision as an input →
  partial). E.g. a boolean `refused` / `is_stale` parameter that the theorem merely threads through is an input.
- **e.** Premises/requires do not narrow the statement beyond its declared scope; otherwise check_scope narrowed; if
  the narrowing removes a required case → partial.
- **f.** The statement still matches the block's current text (show.py prints it). Fix drift: restore dropped
  refuting cases, remove imported product detail. Record `statement fixed: ...` in `reason`. Then grade the fixed
  statement.
- **g.** For a refuted obligation: the witness reaches the stated observation and the trace is permitted by the
  model's actual inputs (not a state the product cannot produce); otherwise partial. A single witness is
  `check_scope narrowed`.

**full → absent** only when nothing cited (or found) represents the obligation at all.

**Absent rows**: for each, search models **by behaviour, not only by block id**: `REPO/.g5/Verus_verification/models/*/`
`{*.rs,NOTES.md,manifest.json,model.json}`, `.g5/Verus_verification/coverage.md`,
`.g5/Verus_verification/crosswalk/decision-links.tsv`, and the playbook-proofs crates
(`REPO/experiment/playbook-completion/proofs-*/src/*.rs` and `.g5/Verus_verification/models/playbook-*`). Grep the
deciding function / reader / outcome words from the statement and the product names in the block metadata. Upgrade
to partial or full only under the same checklist; give the locator(s) (`path::proof_fn_or_spec_fn`, one of them a
proof fn for full), the design check and the latest receipt. Note on reviewed-design crates (proofs-d1d/d1e/d1f):
their as-built refutations count only where a control restoring the as-built rule has a fresh receipt; proofs-d1f
has only a baseline receipt, so nothing from it is above partial.

Owner contradictions: if source or the block's own metadata contradicts the governing statement, add a gap segment
`owner-contradicted: <file:line or metadata evidence>` (keep the grade the evidence supports) and list it in your final
message. Do not reword ontology text.

Be skeptical and specific. The iteration-63 spot-check held only 13 of 25 sampled full grades; typical failures were
full grades resting on a model definition (`envelope`, `canon`, `apply_props`), a proxy (`route_rows>0`), one entry
point of several, `check_scope full` on single-point witnesses or narrowing requires, and absent rows whose behaviour
was modelled under another block's name. Equally, do not downgrade a row whose proof genuinely decides it: a theorem
with a `requires` that only restates the statement's own condition ("when the graph is named …") is fine.

## Final message (your return value; the integrator saves it)

1. Counts: full held / full→partial / full→absent; absent held / absent→partial / absent→full; check_scope full→
   narrowed; statements fixed; overlay result (must be exit 0, paste its summary lines).
2. A table of every changed row: id, old → new, letters, one-line reason (the same as `reason`).
3. Owner contradictions found (id, evidence). Duplicates/missing obligations noticed. Housekeeping items noticed
   (stale coverage.md rows, NOTES receipt names, crosswalk rows) — report only.
4. Rows where you were unsure (id + why), so the reviewer can target them.
