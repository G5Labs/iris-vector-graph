---
name: ontology-planning
description: Plan consequential design requests with the governing ontology. Choose the minimal sufficient design and edit the owning commitments. Excludes routine fixes within existing intent and agent-harness tuning.
---

# Design the minimal sufficient change

## Establish what governs the change

Read the request and `.g5/ontology/root.g5.md`; follow the owning commitments and
material interactions. Name the governing blocks, including unchanged ones relied on,
and distinguish required outcomes from mechanisms the agent proposes. Inspect actual
operations and consumers when reuse or feasibility decides the design. If ontology is
absent, establish only the commitments needed for this task; do not start an uplift.

Resolve contradictions from available authority. Preserve essential conditions and
important unresolved assumptions; existing code does not justify weakening intent.
Link durable intent sources. Where none exists, record consequential chat decisions in
`.g5/chat_intent/<workspace-or-pr>/<name>.md`, separating instructions from interpretation.

## Choose owners and complete operations

Before adding an owner or lifecycle, identify existing operations with the same
semantic role, including those introduced by other features. Compare reuse, extension,
derivation or removal where credible. Name the actual guarantee or incompatibility
that requires a separate mechanism, under the same outcomes, concurrency, failure
behavior, compatibility and operating envelope. Do not manufacture alternatives for
settled choices or reward fewer records that lose an outcome.

Distinguish fact ownership, legal-transition authority and commit coordination. Sketch
the caller's semantic input and complete outcome at consequential boundaries: callers
should not reconstruct admission, lifecycle or failure protocols. Preserve cross-owner
atomicity without moving every concern into one owner. Extend a shared guarantee at
its owner; keep feature-specific policy outside the core. For duplicated state,
examine derivation or a rebuildable projection, including discovery and recovery costs.

For a disputed choice, walk a concrete extension or recovery through each feasible
candidate. Compare decisions and assumptions that callers or owners must coordinate,
not file counts or generic design adjectives. Keep the simpler candidate only when it
preserves the required behavior. Use the [broader reference](references/design-evaluation.md)
only for a broad assessment; routine work needs no scorecard or system-wide audit.

## Edit ontology and finish the design

Amend the owning commitments in their existing organization and format, preserving IDs,
ownership and essential conditions. Record consequential ownership choices, reasons and
assumptions in concise, independently understandable prose. Use the existing ontology
as the guide to organization and follow the [writing rules](../../../.agents/guidance/ontology-examples.md#writing-rules)
for new and changed statements. Routine amendments need no other supporting document.
Consult [meaning and selection](../../../.agents/guidance/ontology.md),
[format](../../../.agents/guidance/ontology-format.md) or
[examples](../../../.agents/guidance/ontology-examples.md) only as needed.

Continue the existing plan, or use
`.g5/pr_ontology_diff_design/<workspace-or-pr>/ontology-plan.md`. Link governing blocks
and make ontology changes reviewable through the actual diff. Explain consequential
choices, interactions and acceptance conditions; link evidence rather than duplicating
it. Omit routine implementation detail recoverable from code.

Self-review against the request, governing ontology and actual guarantees of relied-on
operations. Check both required behavior and the ownership choices the implementation
must preserve. Resolve contradictions in the same plan and present it for human reading.
Implement when authorized, maintaining those commitments through fixes and follow-ups
and using the completion check in agent instructions. Report invalidated assurance
claims as gaps. No extra approval is needed for already authorized implementation.
