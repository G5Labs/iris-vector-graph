# Intent recovery and the source inventory

Use during stage A of initial uplift with [TLC](TLC/uplift.md) or [Verus](Verus/uplift.md), and revisit when modeling or review exposes missing intent. Recover governing meaning, not a transcription of every available artifact.

## Keep sources discoverable throughout the work

Reuse the project's source ledger, or keep `sources.md` (or a structured equivalent) beside the uplift plan. Anything relevant may supply intent or evidence: original requirements and conversations, answered questions, accepted decisions, issues and PRs, diagrams and screenshots, repository guidance, older ontology, history, code, tests, schemas, configuration, dependency contracts, operational records and observed behavior. This is a discovery space, not a requirement to search every service or the entire internet.

For each useful source or coherent source group, retain a stable locator, revision/date where available, origin, scope, authority, inspection status and follow-up. Distinguish discovered, inspected, unavailable and superseded material; record which portions were inspected when partial. Link consequential extracted claims to their passages and owning ontology or disposition. Group incidental files rather than cataloging every line. The inventory locates evidence; it must not become a second governing specification.

Refresh this inventory at stage handoffs and review rounds. B and C consult the original sources as well as A's conclusions, add newly discovered sources and revisit unresolved or conflicting claims. Do not silently discard inaccessible evidence or claim it was reviewed. Keep original records accessible through links; do not copy whole transcripts into ontology.

## Recover authority at statement level

Check governing documents, accepted decisions, human answers and relevant repository instructions beyond the most obvious requirements folder. Historical skills and prompts can explain an artifact's origin without becoming instructions for the current agent. Prefer original records over summaries, and distinguish explicit commitments and later corrections in the same scope from tentative or superseded statements. A newer timestamp or confident tone alone does not establish authority.

When reading conversations or exports, distinguish human-authored statements from quoted assistant suggestions, tool outputs and injected context. Resolve the question behind a short answer such as “yes”; read relevant attachments and diagrams. Deduplicate copied records without losing provenance. An agent's summary of human intent is a lead to verify, not fresh human authority.

Code and tests are valuable reverse-discovery sources, but a policy found there may be obsolete, accidental or contradicted by an accepted decision. Check its history and governing evidence before promoting it into intent. Separate supported human requirements, necessary implications, agent design choices, observed implementation and proposed improvements. Preserve valid intent when implementation diverges; do not turn every existing behavior into a requirement or every plausible improvement into human intent.

Prior agent findings can guide investigation without acquiring human authority. In an evaluated experiment, respect the declared allowed inputs and held-out evaluation boundary; do not feed hidden scorecards or evaluator findings to uplift workers. Normal source recovery and the uplift's own review findings remain legitimate inputs.

Check consequential provisional Q options together with the contracts and consumers that rely on them. Individually plausible answers may conflict when combined; keep the affected conclusions conditional until there is a coherent supported choice. When an answer or stronger source resolves a question, update its owner and dependent ontology, model assumptions, bindings and findings, removing superseded qualifications and rechecking affected evidence. A human answer establishes intent, not that the implementation already satisfies it. Reuse the existing plan and links; no separate question workflow is needed.

## Build coverage in both directions

Build capabilities from source intent and independently inventory production functions/operations. Trace each important behavior through its input producers, entry points, guards, writers, effects, consumers and failure/recovery paths. Neither the existing model list nor the current bug list defines the denominator. Group operations when they implement one behavior, while retaining the concrete functions behind that group.

For each consequential capability, record its source, governing owner, relevant operations and coverage or unresolved questions. Reverse the check: trace each governing commitment back to evidence and forward to implementation and verification. Inspect conditions within an already-linked statement; a whole-block link does not establish every clause. When reporting operation coverage, use inspected operation-to-contract/model links over the declared in-scope operation inventory, with exclusions and partial coverage visible; file counts and search hits are not substitutes.

Derive relevant cases from those contracts: for example absent versus empty inputs, zero or several participants, mixed batches, duplicate delivery, repeated actions, terminal state, interruption and recovery. Cover distinctions that can change a required outcome; do not invent business restrictions to fill a matrix. Keep detailed case tables and model mechanics in evidence. Only concise, useful governing statements and consequential choices belong in the human-facing ontology; a property does not require a new block.

Before investing in the full model campaign, have a fresh reader attempt to reconstruct the major functionality from the ontology alone, then compare with independently recovered expectations and operations. Could an implementation obey everything written yet omit important required behavior? Repair supported omissions in the owning statements. This early check does not replace C's independent review of the completed models, bindings and evidence.

## Reconcile an older foundation when present

Compare both foundations semantically against the selected implementation and current sources, preserving stable IDs and one owner per commitment where possible. Classify older material as retained, corrected, superseded, fixed upstream, conditional or future-only. An old defect may now be fixed; its valid contract may still matter. A later feature's extension contract must not silently become a claim about current implementation. Retain correction lineage and scoped evidence rather than duplicate competing owners. Saved model results require an applicability review, not automatic promotion to fresh evidence.
