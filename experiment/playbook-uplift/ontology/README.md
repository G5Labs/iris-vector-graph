# Ontology format (playbook §3.1)

Every module file is `NN-name.md`. `tools/ontology_index.py` parses every module, checks the gate and
writes `INDEX.md`. Never edit `INDEX.md` by hand; run `python experiment/playbook-uplift/tools/ontology_index.py`.
`--check` fails when the gate fails or when `INDEX.md` is not what the script would write.

The product pin is `3eaa79cf`. Every path below is relative to the repository root and must exist at the pin.

## File layout

```markdown
# NN Module title

Module: ABC
Root: ABC-0
Scope: one paragraph naming the production files this module owns.

## Glossary

| Term | Defined by |
|---|---|
| retry key | ABC-D1 |

## Statements

| Id | Parent | Kind | Statement | Evidence | Source | Notes |
|---|---|---|---|---|---|---|
| ABC-0 | SYS-0 | R | ... | ... | ... | ... |

## Cells

Entity tenant target: states live, erased, redacting, redacted; commands erase, redact, commit-into
Entity ...: states ...; commands ...

| Entity | State | Command | Outcome | Statements | Decision |
|---|---|---|---|---|---|
| tenant target | live | redact | refused | RED-X1 | |
```

Each section heading is literal. Tables must keep these exact columns. A `|` inside a cell is written `\|`.

## Statements

- **Id**: `<MODULE>-<suffix>`, unique across the ontology. `<MODULE>-0` is the module root. Suggested suffixes:
  `D1…` definitions, `B1…` business rules, `T1…` technical rules, `I1…` invariants, `X1…` refusals,
  `P1…` premises, `Q1…` open questions. Children may extend the parent's id (`RED-B2.1`).
- **Parent**: the id of an earlier statement. The module root's parent is `SYS-0`. `SYS-0`'s parent is `-`.
- **Kind**: one of
  - `R` module root (one per module);
  - `D` definition of a glossary term ("A tombstone is ...");
  - `B` business rule (what a user, tenant or operator can rely on);
  - `T` technical rule (how the product does it);
  - `I` invariant (always true between commands);
  - `X` refusal (a command the product refuses, and when);
  - `P` premise about the environment (IRIS, the driver, the operator);
  - `Q` open question (must also name a decision in `DECISIONS.md` in Evidence as `open:HD-NN`).
- **Statement**: one behaviour, plain English, Flesch-Kincaid grade at most 8 (checked). No backticks, code
  names, SQLSTATEs or global names: those go in Source and Notes. Use only glossary terms that are defined by an
  ancestor, by an earlier sibling, or by an earlier sibling of an ancestor (lexical scope, see below).
- **Evidence**: `; `-separated items. Every kind that applies, with its conditions in Notes.
  - `inspected:<path>:<line>[-<line>]` production code read at the pin (lines must exist).
  - `tested:<path>::<name>` an upstream test asserts it (`def <name>` or `class <name>` must exist). Not run here.
  - `run:<id>` a test set executed in this uplift (registry `evidence/runs.json`, result `pass`).
  - `live:<id>` observed on live IRIS Community in this uplift (registry, result `pass`).
  - `mc:<id>` model-checked by an explorer run in this uplift (registry, result `pass`).
  - `proved:<fn>` a Verus `proof fn` in `experiment/playbook-uplift/proofs`, covered by a registry Verus run
    whose source hash matches the current proof sources and that reported 0 errors.
  - `assumed:<P-id>` a premise in `TRUST.md`.
  - `open:<HD-id>` a decision assigned to the human in `DECISIONS.md`.
  - `finding:<F-id>` the code disagrees with the statement; recorded in `FINDINGS.md`.
  - `not-implemented` the intent source states it and no code does it (Source must cite the intent).
- **Source**: where the intent comes from: repo paths (`docs/adr/0013-...md`, `CONTEXT.md:120`), `commit:<sha>`,
  or URLs. Every repo path written in Source must exist at the pin.
- **Notes**: precise detail (code names, globals, SQLSTATEs, version differences, conditions of the evidence).

## Scope of a term

A statement may use a glossary term only when one of these defines it (kind `D`):

1. the statement itself (it is the definition);
2. an ancestor (the parent chain up to `SYS-0`);
3. an earlier sibling of the statement or of any ancestor (same parent, earlier in document order).

Module roots are children of `SYS-0`; `00-system.md` comes first, so the system definitions are earlier siblings of
every module root and are in scope everywhere. A term defined inside another module is not in scope: define it at
`SYS` level or define it again locally. Matching is case-insensitive on whole words, with a plural `s`/`es`.

This is the playbook's "ancestors or earlier same-level statements" rule read as lexical scope; the reading is
recorded as decision HD-01 in `DECISIONS.md`.

## Cells (entity state x command)

`Entity` lines declare the states and commands of each entity the module owns. The tool requires one row for every
(state, command) pair. Outcome is one of:

- `ok` the command performs its change;
- `no-op` the command is accepted and changes nothing;
- `refused` an explicit error and no change;
- `n/a` the command cannot be issued in that state (say why in the cited statement);
- `open` undecided: Decision must name an `HD-NN` in `DECISIONS.md` assigned to the human.

Every row other than `open` cites at least one statement id that resolves anywhere in the ontology.

## Readability check

Flesch-Kincaid grade = 0.39 x (words / sentences) + 11.8 x (syllables / words) - 15.59, on the Statement text only.
Syllables use the counter in `tools/ontology_index.py` (vowel groups with the usual silent-e and -es/-ed
corrections); it is deterministic, so a statement either passes or fails the same way on every machine.
