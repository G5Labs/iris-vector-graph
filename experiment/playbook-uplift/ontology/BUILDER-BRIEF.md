# Builder brief: §3.1 breadth uplift of iris-vector-graph

You are a builder on the iris-vector-graph (IVG) verification uplift. You write one or two ontology module files
at playbook §3.1 breadth. The orchestrator owns everything else (the system module, the erasure → redaction →
replay modules, the index, the proofs and every live run).

## Where you are

- Checkout: `/home/ziniu_wu_g5labs_ai/experiments/iris-vector-graph-playbook-uplift-20261113/iris-vector-graph`,
  branch `experiment/iris-vector-graph-playbook-uplift-20261113`. Product pin `3eaa79cf`; everything outside
  `experiment/` is the product at the pin. Read it; never modify it.
- Use the repo's Python for the gate: `$RUN_DIR/venv/bin/python` where
  `RUN_DIR=/home/ziniu_wu_g5labs_ai/runs/iris-vector-graph-playbook-uplift-20261113/playbook` (plain `python3`
  also works: the gate script needs only the standard library and git).

## Rules (binding)

- Edit only your allow-listed files (your prompt names them). Never edit `INDEX.md`, `README.md`, `00-system.md`,
  `TRUST.md`, `DECISIONS.md`, `FINDINGS.md`, another builder's files, or anything outside `experiment/playbook-uplift/`.
- Do not run git commands that write (no commit, no stash, no checkout). Do not start, stop or connect to IRIS or
  Docker. Do not run test suites; you read tests, you do not run them. Do not kill processes you did not start.
- Never claim a check you did not run. Evidence you can give is `inspected`, `tested` (an upstream test that you opened
  and whose assertion matches the statement), `assumed`, `open`, `finding` and `not-implemented`. The orchestrator
  adds `run`, `live`, `mc` and `proved` later.

## Read first

1. `experiment/playbook-uplift/ontology/README.md`: the exact file format, evidence grammar, cells and the scope rule.
2. `experiment/playbook-uplift/ontology/00-system.md`: the system terms. Use them; do not redefine them.
3. `experiment/playbook-uplift/index.md`: the seed contracts. If a seed falls in your area, state it, check it
   against the code at the pin, and record any disagreement as a finding. "Extend and challenge" is the job:
   a seed is a claim, not a fact.
4. `CONTEXT.md` (glossary), the ADRs in `docs/adr` for your area, `docs/KNOWN_ISSUES.md` and `CHANGELOG.md` entries for
   your area (search by class or function name), the specs under `specs/` for your area, `docs/USER_GUIDE.md`,
   `docs/API_REFERENCE.md`, `docs/ADMIN_GUIDE.md` sections for your area.
5. The production code you own (listed in your prompt) and its tests (`tests/unit`, `tests/integration`,
   `tests/e2e`, `tests/contract`). Use `git log -S` / `git log --oneline -- <path>` when history explains a rule.

## What to produce

For each module file you own:

1. **Root (R)**: what the module owns (which facts, which stores), one sentence.
2. **Definitions (D)** before first use, for every term your statements need beyond the system terms. Add each to
   the module Glossary table. Keep the Glossary small and specific (multi-word terms are fine: "degree cache").
   Do not put everyday words in the Glossary.
3. **Statements at breadth**: one behaviour each, covering every public command of the module (engine methods,
   SQL procedures and functions, ObjectScript entry points, HTTP or CLI entry points it owns), its refusals (X),
   its invariants (I), its technical rules where a design decision lives (T), its premises about IRIS or other
   dependencies (P), and its open questions (Q). Aim for 80-200 statements per module, proportional to the code.
   Group them under a few parent statements (one per command or feature) so the tree reads top-down.
4. **Evidence** on every statement: at least one `inspected:<path>:<lines>` into production code at the pin, plus
   `tested:<path>::<test name>` for each upstream test you opened that asserts it. In Notes say whether the test needs
   live IRIS (integration/e2e) or only inspects source text or Python (unit), because those support different claims.
   Line numbers must be real (the gate checks they exist; check them with `sed -n` or `grep -n`).
5. **Intent sources** in Source: ADR, spec, doc path (with `:line` where useful), or `commit:<sha>`.
6. **Disagreements**: when code, docs, tests or the seed disagree, write the statement as the intended behaviour and
   add `finding:F-NNkk`; describe the finding in `findings/NN.md` (heading `### F-NNkk title`, then Evidence,
   Impact, and What would close it). When intent is genuinely undecided, write a `Q` statement with
   `open:HD-NNkk` and describe it in `decisions/NN.md` (heading `### HD-NNkk title`, a line `- Owner: human`, the
   question, the options, and the default the code applies today). Premises go in `trust/NN.md` (heading
   `### P-NNkk title`). `NN` is your module number; `kk` counts from 01.
7. **Cells**: declare the module's main entities with `Entity <name>: states a, b; commands x, y` lines (2-6 states,
   3-10 commands each, the ones a user can observe) and write one row per (state, command) pair. Every row cites
   statements; a pair whose outcome you cannot determine from code and docs is `open` with an HD id.
8. **Readability**: every Statement must read at Flesch-Kincaid grade 8 or below. Use short sentences and common
   words; put code names, globals, SQL, error codes and version notes in Notes. Check a sentence with
   `python experiment/playbook-uplift/tools/ontology_index.py --grade "your sentence"`.

## The gate

Run `python experiment/playbook-uplift/tools/ontology_index.py --only NN [MM]` (your module numbers). It parses every
module, checks yours and prints only your violations; it does not write `INDEX.md`. Iterate until it reports
0 violations for your files. Other builders are writing other files at the same time; ignore their violations.

## Final report (under 300 words)

Files written; statement counts by kind; cell count and open cells; the gate result for your files (paste the last
line); the 3-6 most important findings with one line of evidence each; open decisions; what you could not cover and
why. Never claim a check passed unless you ran it and saw the result.
