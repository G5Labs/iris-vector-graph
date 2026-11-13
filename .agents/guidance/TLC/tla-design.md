# Design with ontology and TLA+/TLC

Use this workflow when the user explicitly requests design with TLA+/TLC, continues
that design, or requests an initial downlift that has reached its design phase.
The same design pass covers the governing ontology, its edits and the checked models.
Treat a supplied design as a candidate to preserve and challenge.

The deliverable is a minimal sufficient design whose behavior has been checked and
whose ownership makes subsequent correct changes cheaper. Establish the design before
dependent production implementation, allowing focused feasibility inspection or spikes.
When implementation is also authorized, continue through implementation and validation.
Design-only work ends with the checked design, ontology diff and implementation handoff.
Model checks, controls and candidate comparisons below are part of this workflow;
separate production proofs or broad benchmark/mutation campaigns are not implied.

## 1. Establish governing intent and the change boundary

Pin the supplied requirements, accepted decisions, product baseline and verification
foundation. Respect any experiment input restrictions. Continue one plan, or use
`.g5/pr_ontology_diff_design/<workspace-or-pr>/ontology-plan.md`. Keep the initial
candidate and ontology revision recoverable before refinement; retain material revisions
so a later result can distinguish a discovered improvement from an initial choice.

Start at `.g5/ontology/root.g5.md` and identify the blocks that govern the change,
including unchanged commitments whose guarantees it relies on. Read original requirements
and accepted clarifications as well: omissions in existing ontology remain in scope.
Separate required outcomes, agent design choices, inherited behavior and unresolved intent.
Resolve conflicts from available authority; do not select the easiest-to-model interpretation
or promote a documented assumption into a requirement. Keep unresolved choices and their
conditional consequences visible while continuing independent work.

Inspect the actual integration surface before choosing a new owner or protocol. Follow
inputs through entry points, preparation, authorization, transitions, persistence and
final consumers/effects; include alternate callers and competing writers. Identify
existing operations with the same semantic role, even under another feature's name.
For each proposed reuse, identify the operation, the guarantees it supplies, its caller
premises and any missing guarantee. A class name, passing suite or proof of a neighboring
operation does not establish that contract.

Dependency investigation does not authorize baseline repair. Report defects already present
in the pinned pre-change product without repairing them unless separately authorized, even
when relevant to this design. Keep their origin, consequences for the new feature and repair
authority explicit. Defects introduced or worsened by the proposed change remain in scope;
repairing that regression does not authorize broader baseline cleanup.

Edit the owning ontology now to express the required outcomes, essential conditions and
initial consequential design choices. Preserve IDs and existing organization. If ontology
is absent, establish the in-scope commitments without starting a repository-wide uplift.
Use [ontology guidance](../ontology.md), [format](../ontology-format.md) and
[examples](../ontology-examples.md) only as needed. Keep the bodies human-readable; model
mechanics and detailed derivations belong in linked evidence. Record consequential chat
decisions without another durable source under `.g5/chat_intent/<workspace-or-pr>/`,
distinguishing human instructions from interpretation.

## 2. Derive comprehensive coverage independently of the models

Before model construction, derive an obligation inventory from the requirements,
governing ontology and inspected operations. Account for every material in-scope feature
behavior and affected inherited guarantee, including unchanged consumers newly exposed
to different inputs or timing. The existing model catalog is evidence, not the denominator.
Check both directions: obligations missing operations/evidence, and operations or effects
missing governing commitments. Expand the inventory when later investigation finds a path.

Within each concern, examine state × operation outcomes, meaningful input/identity
distinctions, successful completion, refusal, interruption and recovery. Include batch
membership and partial completion where applicable. Do not hide behavior under labels
such as UI, adapter or stateless: use behavioral models where meaningful and appropriate
source/runtime evidence for visual, structural or platform-specific obligations.

Keep one coverage map in the existing plan/evidence, linking obligation and authority to
owner/operations, property or other check, assumptions, result and gap. Shared models can
cover many obligations; one checked property cannot stand for an entire feature. Account
for inherited guarantees as reusable, affected, invalidated or a baseline gap, with a reason
and the gap's relevance to this change. A relevant baseline defect can remain reported
without repair while limiting the design's guarantees. Missing coverage for a requested
feature is not an inherited exception. If the current implementation lacks a field, API or
display path, first check whether authorized changes can supply the behavior or
preserve/recover the needed facts before calling it an external blocker. Do not invent
unavailable historical facts or turn impact analysis into unauthorized baseline repairs.

Every material obligation needs a disposition. Unsupported or partially checked behavior
remains a gap and prevents an unqualified claim of complete design coverage.

## 3. Compare mechanisms before committing to their structure

At consequential choices, compare credible candidates under the same outcomes,
permissions, concurrency, failures, compatibility and operating envelope. Start by
examining reuse or extension of an existing contract, derivation of state and removal
of redundant coordination before adding another owner or lifecycle. Do not fabricate
alternatives for a settled choice. Keep behavioral repairs distinct from simplifications.
Do not merge independently governed policy contracts solely because their current
configurations yield the same results.

For each disputed boundary, make the alternatives concrete enough to compare:

- Which facts are authoritative, which are derived, and who owns legal transitions?
- Which complete operation does the caller invoke, and who coordinates the commit?
- Which policy must otherwise be reimplemented or kept synchronized across callers,
  projections, adapters or models? Where do compatibility and recovery add real costs?
- What missing guarantee or incompatible semantics requires a separate mechanism?
  Does an adapter preserve meaning, or disguise a second domain with accumulating exceptions?

Walk a plausible next change, drawn from the actual responsibilities or differences
between candidates, through each design. Identify semantic decisions that must change
together, caller premises that must be reconstructed, and contracts/evidence that must
be revisited. Include migration and operating costs. These are comparative observations,
not a universal score or a count of files. Fewer models, records or lines do not establish
lower cost; absent behavior and absent assurance are not savings.

Where modeling can distinguish candidates, name the uncertainty it must resolve and what
result would change the choice. If two candidates have equivalent modeled behavior,
keep the structural comparison explicit rather than inventing a property that favors one.

## 4. Build contracts, candidate machines and their interactions

Use the shared [model-checking mechanics](model-checking.md) for construction, refinement,
controls and trajectory tests. Save models and raw results under `.g5/TLA_verification/`
using the [artifact guidance](setup_foundation.md#artifact-paths). Build reusable concern models, not one
isolated model per acceptance criterion or a single machine that hides ownership.

Maintain three roles:

| Role | Required connection |
|---|---|
| Abstract contract (L1) | Governing behavior, allowed outcomes and progress, independent of the chosen mechanism |
| Candidate mechanism (L2) | Concrete state, guards, effects, frames and real interruption boundaries; an abstraction mapping to L1 |
| Implementation (L3) | Intended operation bindings during design; inspected source bindings and runtime evidence once implemented |

For each owner, model its externally meaningful contract. Model cross-owner protocols
over those contracts and check composition where an invariant or progress condition
crosses owners; isolated local checks cannot establish it. Expose who establishes each
shared premise and keeps it valid through use. Identify write authority and the operations
that enforce it; a coordinator's name does not settle participants' transition rules.

Reuse qualified environment contracts for the actual database, queue, provider and
framework behavior. Inspect their supported versions, assumptions and evidence. Extend
a shared contract when a generally needed guarantee is missing; keep feature policy in
its owner. Allow relevant environment behavior, including stale reads, duplicated or
reordered messages, lost responses, rollback and late effects. An uncertain guarantee
deciding the design is a verification target, not a convenient environment assumption.
If no suitable contract exists, model the dependency behavior needed by this design and
keep generally useful semantics reusable. Qualify new or changed environment assumptions
against the actual system, using existing evidence or targeted contract/differential checks
within task authorization. Where validation is unavailable, retain the conditional claim
and the exact independent check needed; an executable environment model is not evidence
that the real dependency obeys it.

Cover each material operation and branch at the chosen abstraction, including refusal
and failure. Where representation or atomicity differs, check L2 initialization and
transitions against L1 through an explicit mapping; account for justified stutters and
preserved progress. A phase variable must not supply serialization or atomicity that
the proposed operations cannot enforce. State finite bounds and reductions; model-checking
bounds are not product capacity limits. TLC establishes bounded results, not an unbounded
refinement theorem or a proof of production code.

## 5. Execute, challenge and simplify

Run the relevant TLC configurations for candidates and required properties. Check safety,
deadlocks, legitimate completion and required progress under named fairness/recovery
assumptions. Distinguish a reachable completion from eventual completion. A rejection or
permanent stutter that avoids every unsafe action may still violate the requested operation.

For each consequential guarantee, execute a relevant broken control and inspect the
failure: it must violate the intended assertion, while the unmodified control completes
as expected. Check witnesses that reach the real trigger and traverse recovery when that
is the claim. Parse errors, timeouts, unreachable premises and unrelated failures do not
establish sensitivity. Read formulas and configurations, not only green totals.

Use the results to challenge necessity, not only correctness. Remove or replace a disputed
mechanism under the same obligations and examine the resulting behavior. A guard that
protects only state introduced by that mechanism does not justify retaining the mechanism.
When a simpler candidate fails, trace the failure to a real required guarantee and its
enforcing owner before adding complexity. Preserve legitimate outcomes and supported
inputs; do not improve results by narrowing scope, concurrency or failure behavior.

Classify each finding before changing the design: intent ambiguity, model/binding error,
implementation defect, evidence gap, or supported simplification. Reconcile counterexamples
with actual operations and environment guarantees so abstraction errors do not invent bugs.
Amend the same ontology and plan for consequential discoveries, preserving essential
conditions and obligations outside the model, then rerun affected configurations and controls.

Record whether each material comparison led to a simplification, required a repair or
retained mechanism, confirmed the original choice, or remained inconclusive. Keep the
next-change comparison alongside the behavioral result. Model equivalence cannot establish
encapsulation, and reduced state-space size cannot establish architectural minimality.

## 6. Close the design and hand its commitments to implementation

Re-read the governing sources and inspect the integration surface independently of the
coverage map; reconcile omissions before claiming completion. Review the full resulting
design, including unmodeled behavior, compatibility, performance/capacity and recovery.
Check that the selected operations actually provide the guarantees their callers rely on.

Do not claim design readiness while relying on a known-false or unsupported dependency
guarantee. Choose a valid in-scope design where possible; otherwise retain the conditional
design, affected obligations and prerequisite repair, evidence or decision in the same plan
and handoff. Reporting a baseline defect does not establish that premise or its dependent
guarantees. Continue independent authorized design and implementation work.

Keep the ontology diff and one human-readable plan as the design of record. Explain the
chosen owners and complete operations, consequential alternatives and their disposition,
essential premises, unresolved choices and evidence limits. Preserve structural acceptance
conditions: which semantic rule has one owner, which existing operation is reused, and
which caller obligations the boundary must encapsulate. Record consequential ownership
decisions in the owning ontology's D statements; use existing metadata to link their
comparisons and source bindings. Do not copy the model into the ontology or require
production types to mirror model variables.

The design handoff links governing ontology → properties/configurations → results and
controls → intended operations → required implementation checks. Include selected failing
and successful trajectories, affected inherited guarantees and outstanding correspondence
work. Use the [execution evidence and reuse rules](setup_foundation.md#execution-evidence-and-reuse)
to distinguish fresh checks, applicable saved results and missing evidence.

When implementation is authorized, implement the accepted design using native methods;
no new approval is needed. Keep governing commitments and open assumptions in active
context and handoffs. If actual APIs cannot enforce a relied-on guarantee, reopen that
decision before dependent code spreads the protocol among callers.

Inspect implementation correspondence through input preparation, all relevant entry points,
competing writers, commit/failure boundaries and final consumers. Add or extend the
[TLC-derived trajectory tests](model-checking.md#turn-the-model-into-discriminating-tests)
through real operations and persistence where those supply the guarantee; use independent
oracles and controls that detect removal of the protection. Put lasting regression checks
in the normal test path where feasible. Also test requirements absent from the models.
For behavior that benefits from a reusable comparison across many cases, consider
[automated model-to-production replay](model-checking.md#optional-automated-model-to-production-replay)
under the same testing scope.
For implementation review, follow the affected statements' metadata to the ownership
decisions, comparisons and current source bindings. If delegating this check, pass those
references to the reviewer. Inspect whether actual production operations preserve those
decisions; reopen the comparison when they do not. Passing behavior tests can coexist
with renewed duplication. Recheck affected models,
bindings, controls and proportionate system/regression tests on the final relevant inputs;
carry forward only guarantees whose premises still hold.

Finish by stating whether authorized design work and implementation, when requested, are
complete, and separately which design/runtime guarantees are established, conditional or
unestablished. Report baseline findings without treating their unauthorized repairs as
unfinished work or their affected guarantees as established. Missing required investigation,
checks or in-scope repairs still means incomplete work. Do not stop at a green model while
independent authorized work remains. Preserve a continuation checkpoint if external input,
authority or an execution limit prevents progress. Report which decisions modeling changed,
which structural choices rested on other evidence, and the remaining prerequisites and limits.
