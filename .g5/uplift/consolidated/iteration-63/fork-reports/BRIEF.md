# Iteration 63 fork brief (census tranche 2)

You are a fork of the iteration-63 builder. You know the assignment, the census README rules, the tool, and the
iteration-61 conventions from the conversation so far. Enumerate ONLY your assigned blocks. Rules are unchanged from
iteration 61; follow README "Counting rules" exactly. Do not edit anything in the repository; write only in your
scratch directory `$G5_RUN_STATE/scratch/iteration-63/<NAME>/`. Do not run Verus, bindings or IRIS. If
`$G5_RUN_STATE/STOP` exists, write what you have (blocks you did not finish stay out of your blocks.tsv) and return.

## Output files (in your scratch dir, TSV, headers exactly as the census; no tabs/newlines inside cells)

- `blocks.tsv`: one row per block you completed, copied from the repo blocks.tsv row with `status` complete (or
  partial if you could not finish it), `obligations`/`excluded` counts, `structural_zero` (only for complete blocks
  with zero obligations), `owners_checked` (non-empty for every graded block: owners checked for restatements /
  "own text" when nothing is restated), `iteration` 63. Never change page/kind/sha256/parent/children.
- `obligations.tsv`: `<block>#oNN` rows, all 17 columns as in iteration 61 (see sample rows in the repo file).
  `grade_source`: `reused: <source>` | `changed: <source>: <reason>` | `new: inspected here`. `iteration` 63.
- `excluded.tsv`: `<block>#xNN` rows. A restatement's owner is an obligation id when it exists (repo or your own),
  otherwise the owning block id. If the owner is a block on another fork's page, use the block id and list it in your
  report's "cross-fork restatements" section with the quoted text so the merger can check the owner counts it.
  Never exclude something as a restatement of a block that might in turn exclude it back; when in doubt about the
  owner, count it at the block whose page the ontology designates as owner (metadata/links) and report it.
- `owner-updates.tsv` (optional, no header, `exclusion_id<TAB>new_owner`): narrow existing repo restatement owners
  that point to your blocks (e.g. `graph.default#x04  structure.edge.delete#o02`) to your owning obligation id. If
  the owner block does not actually state the restated claim, say so in the report instead.
- `report.md`: see below.

## Validation (must PASS before you return)

```sh
cd $G5_RUN_STATE/iris-vector-graph
python3 $G5_RUN_STATE/scratch/iteration-63/tools/merge.py .g5/Verus_verification/census \
  $G5_RUN_STATE/scratch/iteration-63/<NAME>/check $G5_RUN_STATE/scratch/iteration-63/<NAME>
PYTHONDONTWRITEBYTECODE=1 python3 .g5/Verus_verification/tools/census.py --dir $G5_RUN_STATE/scratch/iteration-63/<NAME>/check
```
The check must end in PASS (it will still say "enumeration incomplete" — expected). The tool checks every model
locator (`path::item`, Rust items must be fn/struct/enum/const/type) and that every cited receipt is the latest
fresh receipt of its kind and label with the right verdict; if a receipt you wanted to cite is not the latest/fresh,
cite the latest fresh one of the same kind for that model, or do not claim the check (design_check none/unchecked) and
say why.

## Grading discipline (the reviewer will challenge these)

- Read the block text itself (`.g5/ontology/<page>`), including its `### id` metadata (sources, findings, links) for
  context, but obligations come from governing text only.
- Before grading, search current models by block id AND by behaviour: `models/*/manifest.json` (`ontology_ids`),
  `models/*/NOTES.md`, `coverage.md`, `crosswalk/decision-links.tsv`, and the Rust model files themselves. Check the
  theorem/witness exists (grep the fn), the receipt is latest and fresh (the tool does this), and that the model
  premise/scope matches the current block wording. A label, locator, binding AGREES count or test pass without the
  property is not full. Proof over a narrowed domain = `proved` + `check_scope narrowed`. A theorem that takes the
  deciding value as an input makes the obligation at most partial.
- `design_check` and `as_built` are separate from `grade`. Use `as_built` entries `binding AGREES <receipt.json>`,
  `native <verdict> <path>`, `upstream-test <verdict> <path>`, `inspection <verdict> <path>`, or `none`.
- Parents: state what the parent adds beyond its children; credit only with a documented entailment
  (`parent_entailment` naming child obligation ids and the argument); otherwise `residual: <case where every child
  holds and the parent fails>`. Structural zero only after checking each owner.
- Exclusions: rationale, undecided alternatives (preferred policy options, proposals), navigation, evidence
  annotations ("Iteration NN observed …"), definitions, cross-references — each with a reason. A working assumption
  about current behaviour is assessable.
- When the ontology text is contradicted by product source you inspected (product pin 3eaa79cf, `iris_vector_graph/`,
  `iris_src/`), grade the obligation as written and record the contradiction in the report (do not reword ontology).

## report.md (concise, factual; the merger copies it into the handoff's fork-reports/)

1. Per block: status, f/p/a/u counts, exclusions, structural zero.
2. Page totals; proved (full scope / narrowed), refuted, bounded, unchecked.
3. Grades reused (source), changed (old -> new, reason), new.
4. Parents: entailments claimed (with argument) and parents left open (the open case).
5. Restatements: owner-updates made; cross-fork restatements (exclusion id, quoted text, owner block).
6. Grade-source errors: wrong/stale coverage.md rows, NOTES/manifest errors, ontology statements contradicted by
   source (file:line evidence).
7. Ranked uncovered material obligations on your pages (absent obligations in blocks with no applicable model first,
   then unsupported conditions/outcomes in partly covered blocks): block, obligation ids, missing distinction,
   deciding/writing/observing code to bind (file::symbol).
8. Mapping to the iteration-60 RUN-STOP residual queue (store/iris_sql_store, GQL/GraphQL, SDK/CLI/HTTP admin,
   translator residue, install residue, load_networkx/load_obo, migrations, temporal/operator/retrieval residues):
   which items correspond to census obligations on your pages (ids), and source behaviour you noticed with no owner
   in the ontology (source-discovered omissions, file::symbol).
9. Limitations and judgement calls.

Your final message: 10–20 lines — blocks done/partial, page f/p/a/u, proved/refuted counts, validation PASS line,
top 3 uncovered items, and any cross-fork restatement or owner issue the merger must resolve.
