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
| `[restatement]` | A restatement whose Notes lack "Same meaning as <primary>", whose text differs from the primary's text, that comes before the primary, or a D row citing a same-module "Same meaning as" that the glossary does not list. |
| `[parent]` | Also: a parent in another module. |
| `[evidence]` | Also: completion references (below); a hand-written `ran:` (derived only); `trace:` without `C-`. |

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

**INDEX.md.** Restatements are counted in the module table (Restated column) and left out of the evidence tables
and listings, because they repeat their primary's evidence.

## Self-test (`--self-test`, log `$RUN_DIR/ontology/self-test.log`)

A fixture (SYS, one module with a restatement, a definition parent, "out degree"/"registries" spellings and all four
`C-` evidence forms, and a second module) must pass with 0 violations; it does. Each of 34 negative controls must be
rejected with its own rule tag; all 34 are: aunt (ancestor-sibling) definition, later definition (`[order]` and
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
- `check-literal-scope.py` reads only the "Defined by" column, so it cannot judge the repaired modules. The
  differential and `independent_recheck.py` cover that.

## Reproduce

```bash
source experiment/playbook-completion/environment.sh
T=experiment/playbook-completion/ontology/tools
python3 $T/ontology_check.py --ontology experiment/playbook-uplift/ontology   # before: 1,406 violations
python3 $T/repair.py --out /tmp/ontology-regen && for f in /tmp/ontology-regen/*; do cmp "$f" experiment/playbook-completion/ontology/$(basename "$f"); done
python3 $T/ontology_check.py --check      # after: 0 violations, index current
python3 $T/ontology_check.py --self-test  # positive control, 34 negative controls, differential
python3 $T/independent_recheck.py
```
