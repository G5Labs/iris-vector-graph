# Ontology format

## Blocks and IDs

A block represents one coherent commitment or decision that we want to understand, reference and maintain as a unit. Prefer one or two concise sentences that state the complete commitment and its essential conditions in plain language; follow the [writing rules](ontology-examples.md#writing-rules). Use bullets to clarify one commitment, and use children when a rule, trigger or decision needs its own identity. Link the owning block when another statement already states the rule.

Use children for consequential details or decisions that benefit from separate human review. Keep the parent accurate when read alone; retain essential qualifications there when omitting them would make it misleading. Ontology depth does not prescribe a verification level.

Use a stable, nested ID with an anchor:

```markdown
<a id="account.example"></a>
[I · account.example]

Statement.
```

A child uses `account.example.child_topic`, with its own anchor and marker, and directly follows its parent or the parent's earlier children. Each ID level below the top-level name, such as `account.example`, needs its own block that defines its concept. Keep existing IDs stable; when an ID changes, keep the former ID as an extra anchor line directly above the current anchor.

- `I`: intended behavior or constraint.
- `D`: an important decision.
- `Q`: unresolved intent; identify any provisional answer.

## Metadata

End the file with a new section `## Metadata` and a `### block-ID` entry per block. Record sources and parent/children links; use `Expands: [parent](#parent-id)` for a child. Add reference link to verification evidence and/or external files as source of this block and/or bug/gaps/issues/design simplification items when available.

Put tags on the corresponding block in the metadata. Write each kind of tag on its own bullet, with tags only and no trailing period or note, so viewers recognize it.
- provenance tag: `human-provided` (stated or faithfully paraphrased), `human-verified` (inferred from attributable human sources or confirmed), or `agent`. Use at most one provenance tag. Add `uncertain` for unresolved meaning, including Q; it is not a provenance tag, and a block's kind is not a tag. Do not imply human review or verification that did not happen.
- persona tag: `user-facing-behavior` (for PM persona), `architecture-decision` (for architect persona), `security`, ... (can have few more).
- verification tag: `test-coverage` (block is tested or partially tested with existing test cases), `manual-check-review` (block is validated by human or review by agent), `design-verified` (TLA+/TLC or other model checking machinery + code linking exist), `implementation-verified` (the code is directly verified against this block using formal verification). Use at most one verification tag, on its own bullet. `design-verified` needs a linked state machine with recorded runs; the [foundation format checks](TLC/setup_foundation.md#format-checks) link the recorded model evidence. A model association identifies relevant evidence; it does not by itself establish complete verification.

At the end of the meta-data for each block, you may optionally include a few concise sentences on the source of this block, bug/gaps/issues/design simplification associated with it, and/or verification evidence.

## Ontology file structure

Start at `.g5/ontology/root.g5.md`, with a short system overview and links to its pages. Introductory prose need not be blocks.

- `concepts/` holds shared vocabulary and contracts. Possible pages include security, design principles, architecture, data policy, invariants, operations deployment, domain, roles, and more.
- `features/` holds user stories, important contracts, intent and consequential implementation decisions. Organize big feature per page.

These are reference points, not required folders or files. Organize pages and sections naturally and hierarchically; link shared rules instead of duplicating them.

Put necessary system-specific terms in a separate definitions section at the top of the page, before the statements that use them. Definitions explain vocabulary; they are not ontology blocks and must not hide behavioral commitments or trigger conditions. Prefer ordinary words to invented jargon. Order statements so readers meet the behavior before its conditions, outcomes and exceptions. When rewording, preserve meaning, stable IDs, links, dependencies and unresolved questions.

Keep each page under the platform's render size. When a page grows past it, split it into files that follow its abstractions or sub-components — for example a `<feature>/` folder with one page per sub-component — and keep the original as a short parent page that defines the top level and links its children. The checker warns past 1,048,576 UTF-16 code units (the browser's JavaScript string length), mirroring the Files-view preview threshold.

Optional structural check: `python3 <guidance-directory>/scripts/check_ontology.py <ontology-directory>`. It also prints writing warnings for long statements and bullets, more than ten bullets, issue references in statement prose, undefined ID levels and oversized files; these do not fail the check.
