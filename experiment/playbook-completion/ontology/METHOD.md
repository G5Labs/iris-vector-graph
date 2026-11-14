# Ontology lane: literal term scope, strengthened checker, repaired modules

Input: the 19 module files of the original submission (`experiment/playbook-uplift/ontology/NN-*.md`, `9c3719c1`,
read-only). Output: the repaired modules in this directory, `INDEX.md` (generated), `repairs.json`, and the tools in
`tools/`. Product pin `3eaa79cf`. Logs: `$RUN_DIR/ontology/`.

## The rule

Playbook §3.1 ("Definitions first") read literally, as decided in [HD-0001](../decisions.md): a statement may use
a term of **its module's glossary** only when one of these defines it (kind D):

1. the statement itself;
2. an ancestor (the parent chain);
3. an earlier statement with the **same parent**.

The submitted checker also accepted an earlier sibling of any ancestor (an "aunt"). That extension is removed.
Matching is per module glossary, as the §3.1 gate says ("every term in the module glossary that the statement uses")
and as `../check-literal-scope.py` does.

## Checker changes (`tools/ontology_check.py`, derived from `experiment/playbook-uplift/tools/ontology_index.py`)

Kept: parent resolves and comes earlier, roots, ids, kinds, no code in statements, FK grade at most 8 on the
statement text, Source paths at the pin, every evidence form against the pin and the original registry
(`experiment/playbook-uplift/evidence/runs.json`, original `proofs/` with the Verus source hash, `TRUST.md`,
`DECISIONS.md`, `FINDINGS.md`), cells defined or assigned to the human, `INDEX.md` regenerates byte-identically
(`--check` fails when stale). Every message now carries a rule tag (`[scope]`, `[order]`, ...).

Changed or added:

| Rule tag | What it rejects |
|---|---|
| `[scope]` | A module glossary term used with no definer (primary or restatement) in literal scope. |
| `[order]` | A term used before its primary definition in document order. |
| `[definer-kind]` | A glossary definer or restatement that is missing or not kind D. |
| `[definer-text]` | A definer or restatement whose text does not contain the term. |
| `[cross-module]` | A glossary row whose definer or restatement is in another module (the format does not allow it). |
| `[foreign-term]` | A statement outside SYS that uses a term of another (non-SYS) module's glossary that its own glossary lacks. This keeps the submitted tool's global check of such terms. |
| `[glossary-duplicate]` | Two rows for one term, or one definer listed twice. |
| `[restatement]` | A restatement whose Notes lack "Same meaning as <primary>", whose text or evidence differs from the primary's, that comes before the primary, or a D row citing a same-module "Same meaning as" that the glossary does not list. |
| `[model-only]` | A `proved:` or `mc:` item (original or `C-`) without the `[model-only]` qualifier on a statement that cites a finding whose audit disposition is reproduced-live, reproduced-test or confirmed-source (review R-05), or intent-undecided with a live, run or trace evidence item (behaviour observed on the product, intent open; review R2-08). |
| `[uncited-finding]` | A statement that a reproduced finding's `intended` field names (disposition reproduced-live, -test, -model or confirmed-source), that carries a `proved:` item and does not cite that finding (review R2-03: the `[model-only]` rule fires only on cited findings, so it could not catch a missing citation). |
| `[parent]` | Also: a parent in another module. |
| `[evidence]` | Also: completion references (below); a hand-written `ran:` (derived only); `trace:` without `C-`; an `F-C` finding not in `../findings/audit/*.json`; a qualifier other than `[model-only]`, or one on a kind other than `proved:`/`mc:`. |

**Matcher.** Case-insensitive whole words with plural s/es and space/hyphen variants, exactly as
`check-literal-scope.py`, plus: a hyphen inside a term also matches a space ("out degree"), and a final consonant+y
also matches "ies" ("registries"). It is a superset of the script's pattern (checked on the original corpus below).
There is no stoplist; a verb use ("commits", "routes") counts as a use.

**Glossary format.** `| Term | Defined by | Restated by |`. "Defined by" is the primary definition. "Restated by"
lists local restatements: kind D, same module, after the primary, identical text, Notes "Same meaning as
<primary>". A restatement repeats a primary, so it is listed for every term that primary defines.

**Completion evidence** (resolves against `experiment/playbook-completion/evidence/runs/<id>.json`, written by
`tools/register_run.py`): `mc:C-<id>`, `live:C-<id>`, `trace:C-<id>`, `run:C-<id>` need a record with that id, the
same kind (`mc`/`live`/`trace`/`run`), `result` = `pass` and `product_pin` = the pin. `proved:C-<fn>` needs a
`proof fn <fn>` under `experiment/playbook-completion/proofs` and a record of kind `proof`, result `pass`, whose
`proof_fns` lists `<fn>` and whose `sources_sha256` equals the current proof sources (`ontology_check.py
--proof-hash`; register with `--extra proof_fns=a,b sources_sha256=<hash>`). Any other result (`fail`,
`expected-violation`, ...) or a missing record is rejected. Ids without `C-` resolve against the original registry.

**Findings.** `finding:F-NNNN` resolves against the original `FINDINGS.md`/`findings/*.md`; `finding:F-C...`
against `experiment/playbook-completion/findings/audit/*.json`. The audit also gives every finding's disposition,
which drives the `[model-only]` rule.

**INDEX.md.** Restatements are counted in the module table (Restated column) and left out of the evidence tables
and listings, because they repeat their primary's evidence. The evidence table splits `proved` and `mc` from
`proved (model-only)` and `mc (model-only)`; a "Model evidence and product evidence" table counts statements with
product evidence (inspected, tested, ran, run, live, trace), with model evidence, with model-only evidence, and with
a product finding; a "Model-only proofs and model checks" listing names them.

## Self-test (`--self-test`, log `$RUN_DIR/ontology/r05/self-test.log`)

A fixture (SYS, one module with a restatement, a definition parent, "out degree"/"registries" spellings, all four
`C-` evidence forms, an F-C finding reproduced live beside a `[model-only]` proof, a model-reproduced finding beside
an unmarked model check, an intent-undecided finding with live evidence, and a second module) must pass with 0
violations; it does. Each of 42 negative controls must be rejected with its own rule tag; all 42 are. The two added
for the second review: a reproduced finding's `intended` names a statement with `proved:` that does not cite it
(`[uncited-finding]`); `mc:` beside an intent-undecided finding observed live, without `[model-only]`. The six added for R-05: `proved:` beside a live-reproduced
finding without `[model-only]`; `mc:` beside an original-id finding the audit marks reproduced-test; `[model-only]`
on `inspected:`; an unknown qualifier; an F-C finding missing from the audit; a restatement whose evidence differs.
The first 34: aunt (ancestor-sibling) definition, later definition (`[order]` and
`[scope]`), missing parent, parent in another module, grade above 8, non-D definer, definer text without the term,
definer in another module, foreign term, restatement without the note, with different text, before the primary,
not listed, duplicate glossary row, y/ies plural out of scope, hyphen written as a space out of scope, completion
evidence (missing record, result fail, kind mismatch, other pin, missing proof fn, proof sources changed after the
run, trace without `C-`), the submitted tool's controls (cell not defined, cell statement unresolved, open cell
without a human decision, inspected lines outside the file, code in a statement, unknown premise, unknown original
run id, duplicate id), hand-written `ran:`, and a hand-edited `INDEX.md` (`--check` reports it stale).

**Differential.** On the original modules, this tool's literal rule with the script's pattern gives exactly the
pairs `check-literal-scope.py --details` prints: 1,392 pairs in 1,002 statements, 0 only-here, 0 only-there. With the
gate's matcher it gives 1,403 pairs in 1,006 statements, a superset; the 11 extra pairs are y/ies plurals
("post-commit properties" x4, "plan entries" x2, "identities" x4, "orphan properties" x1).

## Repair (`tools/repair.py`, deterministic; `--out DIR` regenerates elsewhere for comparison)

The modules here are generated from the originals. Original rows are copied verbatim except the Parent cell of a
reparented row and the text of the one reworded row. Steps:

1. **Explicit repairs.** CYP-D13 reworded (the glossary named it the definer of "multigraph mode", but its text
   lacked the term). Before: "A multigraph is a graph set to let two nodes hold more than one edge of one type."
   After: the same sentence plus "That setting is called multigraph mode." Two new primary definitions copy another
   module's definition for a term used without a local definition: NAT-D22 "chained query" (copy of CYP-D21, before
   NAT-X1) and RED-D14 "statement entry" (copy of ERS-D3, before RED-B9).
2. **Reparenting under a definition.** A candidate is a non-D statement whose only module terms are those of an
   earlier same-parent definition, whose subtree uses that term out of scope, and whose text does not open with a
   pronoun. The move cannot lose scope for the statement and only adds scope below it. The tool found 51; each was
   reviewed. 35 are accepted, where the statement is a rule about the defined thing (e.g. LED-B4 "A commit saves all
   of a changeset as one revision" under LED-D4 "A commit is ..."). 16 are rejected, where the term is incidental
   (reasons in `repairs.json` summary, e.g. OPS-B3 is about admin helpers, not drift). The tool stops on an
   unreviewed candidate.
3. **Local restatements.** For each remaining (parent, primary) with a use out of scope, one restatement with the
   primary's exact text, evidence and Source goes under that parent immediately before its first child that uses the
   term, repeated to a fixpoint (a restatement's own terms get restatements before it). Ids are the primary's id plus
   a letter suffix in document order (`LED-D4a`, ...). No definition chains are built.

| Repair | Count |
|---|---:|
| Reparented (reviewed) | 35 |
| Reparenting candidates rejected | 16 |
| Added restatements | 860 |
| Added primary definitions (foreign terms) | 2 |
| Reworded | 1 (CYP-D13) |
| Deleted statements, changed ids, kinds, evidence, Source or Notes | 0 |

Out-of-scope pairs (gate matcher): 1,403 before, 1,255 after reparenting, 0 after restatements. Statements: 3,015 to
3,877. Cells unchanged (904; 29 open, each assigned to a human decision).

## Results

| | Original modules (`--ontology experiment/playbook-uplift/ontology`) | Repaired modules (`--check`) |
|---|---|---|
| Violations | 1,406: scope 1,403, foreign-term 2, definer-text 1 (and INDEX.md stale) | 0, INDEX.md current |

`tools/independent_recheck.py` shares no code with the checker or the repair tool. On the raw markdown it finds 0
pairs out of literal scope (script pattern and superset pattern) and 0 malformed restatements. All 3,015 original
rows keep their id, kind, evidence, Source and Notes and their relative order; parent and text changes are exactly
those in `repairs.json`; text outside the two tables, the cells included, is unchanged. Mutating one restatement or
one parent in a scratch copy makes it fail.

## Completion evidence and model-level evidence (review R-05, `tools/add_evidence.py`)

The review found product statements carrying the original `proved:`/`mc:` tags while the audit's own findings show
the pin violates them. `tools/add_evidence.py` (idempotent; log `evidence-additions.json`) runs after `repair.py`:

1. **Finding tags.** Candidates come from each reproduced finding's `intended` text (the statement ids it names as
   the violated contract), minus statements the original already tagged with it. Criterion: the observed behaviour
   contradicts the statement's text in some reachable execution. Each candidate is reviewed into `FINDING_TAGS` or
   `FINDING_REJECT` (reason recorded); the tool stops on an unreviewed one (it caught F-C1001, added to the audit
   during this work). Intent-undecided findings are not tagged. Two tags come from the review, not from `intended`:
   F-C1303 on RED-B8.1 and F-1304 on RPL-B1.1. Universal axioms (SYS-I2, SYS-I3, ...) take findings: one
   counterexample refutes them.
2. **Run tags.** A passing `live`/`mc`/`trace` record is tagged only on statements its `observes` text names (lists
   such as "RED-I1/I2" or "(ALG-B1.5, B2.2, ...)" are expanded); every named id is reviewed into `RUN_TAGS` or
   `RUN_REJECT`. Confirming runs are not put on SYS axioms; SNP-B3.7 is rejected because it describes the as-built
   behaviour the reviewed model forbids; runs that say the F-1201 window was not reached are not put on ERS-I3.
   Conditions go into Notes (sequential profiles only; indexed configuration only; reviewed design, not the pin).
   No `proved:C-` tag: no completion proof record names a statement or lists proof functions.
3. **Model-only.** Every `proved:`/`mc:` item of a statement citing a product-disposition finding gets `[model-only]`.
4. **Restatements** take their primary's new evidence.

| Added | Count |
|---|---:|
| `finding:` tags | 51 (on 35 statements); 40 on 27 after R-05, 11 more after the second review (below) |
| `live:C-` tags | 48 |
| `mc:C-` tags | 25 (13 after R-05; 12 as-built passes of breadth B after the second review) |
| `trace:C-`, `proved:C-` tags | 0 |
| Statements with `[model-only]` items | 14 (24 items): CYP-I6.4, CYP-X6.5, ERS-I3, RED-B1.1, RED-B4, RED-B4.3, RED-B6.1, RED-B7.1, RED-B8, RED-B8.1, RPL-B1.1, RPL-B3, RPL-I1, SNP-I3.6 |
| Notes extended with conditions | 18 |
| Restatements updated | 2 (TXT-D1's) |
| Reproduced findings left untagged | 34 (each with its reason in `evidence-additions.json`) |

Before (`r05/check-before.log`): 14 `[model-only]` violations in 7 statements, the review's cases. After: 0.

## Left open (none fail the gate)

- **System terms outside SYS are not gated.** The gate checks each statement against its own module's glossary
  (§3.1 wording, `check-literal-scope.py`). Under the literal rule, the SYS definitions are earlier siblings of each
  module root, so they are never in scope there. `ontology_check.py --system-terms` reports 4,619 statement/term
  pairs in 2,605 statements outside SYS that use a SYS term ("graph" 849, "edge" 732, "node" 541, ...). If the
  rule is meant to cover system terms too, each module needs local definitions of the SYS terms it uses. That
  question goes to the orchestrator; this lane did not change it.
- **Word sense.** The matcher cannot tell a noun from a verb. Verb uses ("the erasure commits", "routes") get a
  restatement of the noun definition, which is harmless but reads oddly in places (e.g. ERS-D4a before ERS-T1).
- **Reading order.** A restatement can sit between siblings that open with "It" (e.g. ERS-D3a before ERS-B1.2).
  The Parent column still names the referent.
- **Untagged findings.** 34 reproduced findings tag no statement (listed with reasons in `evidence-additions.json`).
  Mapping them would need a judgment the finding record does not make. Of the validation findings, F-C1002 (Leiden
  partition quality) and F-C0606 (SC-010 latency) contradict no statement: none states a partition quality or a
  latency budget.
- **Moving inputs.** The audit and registry are still growing. `add_evidence.py` stops on any new unreviewed
  candidate, so a rerun after other lanes add findings or runs fails until they are reviewed.
- `check-literal-scope.py` reads only the "Defined by" column, so it cannot judge the repaired modules. The
  differential and `independent_recheck.py` cover that.

## Reproduce

```bash
source experiment/playbook-completion/environment.sh
T=experiment/playbook-completion/ontology/tools
python3 $T/ontology_check.py --ontology experiment/playbook-uplift/ontology   # before: 1,406 violations
python3 $T/repair.py --out /tmp/ontology-regen && python3 $T/add_evidence.py --ontology /tmp/ontology-regen \
  && for f in /tmp/ontology-regen/*; do cmp "$f" experiment/playbook-completion/ontology/$(basename "$f"); done
python3 $T/ontology_check.py --check      # after: 0 violations, index current
python3 $T/ontology_check.py --self-test  # positive control, 40 negative controls, differential
python3 $T/independent_recheck.py
```

## Second review (review/REVIEW-2.md R2-03, R2-08; review-response lane)

The R-05 re-tag preceded the follow-up, so no follow-up finding was cited. Now (`tools/add_evidence.py`, reviewed
tags in `FINDING_TAGS`, each with its reason; "manual" = the finding's `intended` does not name the statement):

| Finding | Statement | |
|---|---|---|
| F-C1308 | RED-B1.1 (from `intended`), RED-B1 (manual) | temporal-only edge live while its record is tombstoned |
| F-C1309 | RED-B7 (manual) | the audit revision's target digest is the guessable name's SHA-256 |
| F-C1306 | RED-B12 (manual) | legacy Graph_KG.ledger_revisions keeps the tenant's text after erase and redaction |
| F-1801 | RED-B4 (manual; its `proved:theorem_retry_refused` is now `[model-only]`) | a replacing restore binds a redacted retry key again |
| F-C1304, F-C1305 | RED-B10 (manual) | the receipt's out-of-reach list omits snapshot archives and the embedding quarantine |
| F-C1307 | RED-B8 (manual) | a writer outside the ledger keeps the run from ever finishing |
| F-C1203 | ERS-B2 (manual) | a prefix erasure leaves the tenant's temporal-only edge |
| F-C1706 | OPS-B5.4 | under the locked driver a duplicate raises instead of being skipped |
| F-C0502 | TMP-B2.13 | under the locked driver the flag's marked-row write fails |

F-C1102 is not tagged: it is now intent-undecided (review R2-08), and intent-undecided findings are not tagged.
F-C0803's candidate CYP-B6.8 is rejected with its reason. The 52 run candidates of the breadth-B checks registered
after R-05 are reviewed: 12 candidates of 6 as-built passes are tagged (`mc:C-b-mc-*`, Notes "checks the as-built
model ... within its bounds (model-level; no code correspondence)"); the 37 reviewed-design candidates, and 3 as-built
candidates whose run excludes the case a finding shows, are rejected with reasons (`RUN_REJECT`). The `[model-only]` rule now also fires for an
intent-undecided finding with live, run or trace evidence (F-1201 on ERS-I3 keeps its marks after F-1201 became
intent-undecided), and `[uncited-finding]` is new. `independent_recheck.py` re-derives both rules without shared code.
Before the tags, `[uncited-finding]` reported exactly F-C1308 on RED-B1.1 (and F-0503 on RPL-B3, a reviewed rejection,
before F-0503 became intent-undecided); after, 0. Registry: `rr2-ontology-check`, `rr2-ontology-self-test`,
`rr2-ontology-independent-recheck` (lane review-response).
