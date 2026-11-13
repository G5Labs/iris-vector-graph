# Model checks and trajectory tests

Shared mechanics for [TLA+/TLC design](tla-design.md), [initial uplift](uplift.md)
and [initial downlift](downlift.md). The invoking workflow supplies scope and
authorization; this reference does not start model work for ordinary changes.

## Select the right scope

| Workflow | Model checking | New or extended trajectory tests |
|---|---|---|
| Initial uplift | Develop ontology and models together after source/scope confirmation. Check all important in-scope behavioral obligations, sharing concern models; audit coverage before finalization. Structural items need reasoned dispositions. | Suggest concrete cases; create and run them only when authorized. Existing authorization counts. |
| Initial downlift | Cover every core feature from the original requirements with TLA+/TLC, sharing concern models where appropriate. | Required during authorized implementation; prepare the cases during design. |
| Explicit TLA+/TLC design | Follow the complete design workflow; cover material in-scope behavior and affected inherited guarantees, sharing concern models. | Required during authorized implementation of that design; design-only work prepares cases without running the implementation phase. |
| Scoped model review or PR reverification | Preserve the explicitly requested scope; a request to review a model does not start a new design workflow. | As authorized by that review; otherwise retain proposed cases and use existing evidence. |

## Human decisions in the run report

For every TLA+ verification or reverification, include **Human decisions** in the run’s final report, even if the run is blocked. Use the existing report or handoff. If the workflow has none, save a short report with the run evidence.

List each human decision the run used, its source and the behavior it settles. For each open question, state what the owner needs to decide, the assumption you used, why it fits the accepted decisions and ontology, and which result depends on the answer. Keep that result conditional. If there are no decisions or questions, say so.

Continue to the completion gate on the most reasonable supported assumption. Ask the owner only when a missing decision or dependency blocks required work and no reasonable assumption lets it proceed. Finish independent work and report the blocker.

## Connect the contract, implementation model and running code

Keep three roles explicit:

| Role | Meaning | Connection |
|---|---|---|
| Abstract contract (L1) | Governing ontology's required behavior. | Statement IDs, properties and essential conditions. |
| Implementation-shaped model (L2) | Actual representations, guards, effects and interruption boundaries. | Map its states and actions to the abstract contract. |
| Runtime implementation (L3) | Production operations and dependencies. | Inspect their correspondence and exercise trajectories when authorized. |

These are roles, not mandatory files or ontology levels. One machine can cover several
statements; link each to its properties. For uplift, bind every as-built action to inspected
code, including input producers, lifecycle entry points, alternate writers, event handlers,
commit/failure boundaries and consumers. For downlift, do not claim correspondence before
code exists. Keep intended, as-built and repair variants distinct. Untraced boundaries
leave conditional conclusions; revise bindings when discoveries change the path.

Name authoritative and derived state, identities, preconditions, effects and frames.
Represent relevant stale inputs, concurrent actors, retries, partial failures and recovery.
Split transitions where a real actor or failure can intervene; do not invent interference
excluded by the implementation. A batch model must preserve member identity, filtering,
empty/mixed inputs and partial commits: checking one item cannot establish the batch contract.

Where earlier actions change an operation's required outcome, consider contrasting relevant
histories in the model and selected runtime trajectories. Keep unresolved earlier effects
represented until evidence settles them; a later response establishes only what its operation
and contract establish. Select histories that change a governing outcome, not every possible
combination or an additional mandatory campaign.

Where representation or atomicity differs, check an explicit abstraction mapping:
implementation-model initialization must satisfy abstract initialization, and each relevant
transition must realize an allowed abstract transition or justified stutter. Retain the
mapping, configurations and finite bounds. This is **bounded refinement checking**, not
an unbounded proof or verification of running code. The [TLA+ refinement guide](https://github.com/tlaplus/vscode-tlaplus/blob/master/resources/knowledgebase/tla-refinement.md)
describes checking an instantiated abstract specification as a TLC property.

Before expanding a model campaign, inspect how the pinned producer or callee establishes
decisive shared premises for each relevant caller; otherwise keep conclusions conditional.
If a Boolean or preset outcome hides a decisive rule, derive it from representative inputs.
Check whether reachable cases merged by the abstraction require different outcomes;
exercise a distinguishing case and a valid completion. Apply this at material boundaries,
not every helper call.

Add an interaction model when local checks miss a consequential protocol; passing local
models do not establish composition. Independently inspect relied-on database, framework,
provider and service guarantees. Never assume the guarantee under test, omit a real writer
or let a test double supply the protection. Names, links and finite refinement alone do
not establish runtime correspondence.

## Review existing models for meaning, correctness and useful alternatives

Interpret each governing statement together with its relevant children. Identify
outcome-changing choices introduced during formalization, such as which identity counts,
when an event qualifies, or which failures preserve state. Resolve them from accepted
sources; where consequential meaning remains unresolved, expose it in the owning ontology
using the existing I/D/Q conventions and keep dependent conclusions conditional. Keep
model-only bookkeeping in verification evidence.

Apply these checks to new and retained models, including passing ones. Read the actual
formula, machine and configuration together. In existing coverage evidence, state the
claim, relevant code operations, bad behavior excluded and legitimate behavior preserved.
Challenge:

- **Vacuity:** unreachable triggers, empty input sets, false premises or refusal/stuttering
  that avoids the obligation. Inspect witnesses for the actual trigger and required
  completion. A retry/recovery witness must traverse that path, not just reach the same
  final state by another route. Check deadlocks and required liveness with explicit
  fairness and recovery assumptions.
- **Weak meaning:** typing, tautologies or idealized assignments that miss relevant broken
  behavior. Keep useful generic checks, but claim only what their formulas distinguish.
- **Wrong statements or correspondence:** omitted identities, inputs, writers, effects or
  failures, misplaced assumptions and impossible schedules. Reconcile with governing
  sources and complete relevant code paths before calling a trace a defect.

For each consequential guarantee, challenge a relevant bad alternative. The unmodified
control must complete as expected; the broken alternative must fail the intended assertion.
Parse errors, timeouts and unrelated failures are inconclusive. Investigate surviving
variants: weak checks, equivalent behavior, unreachable code and out-of-scope behavior need
different dispositions. Do not invent requirements to kill a mutant or claim an unrelated
kill as coverage.

Repair misleading claims and bindings; retain useful scoped checks and explain replacements
or retirements. Removing a property does not close its coverage gap. TLC cannot reveal
requirements or actions omitted from the model. For uplift, use the independent source and
operation inventory from [intent recovery](../uplift-intent-recovery.md#build-coverage-in-both-directions),
not the model list, as the coverage baseline. A Q option remains conditional, not evidence
that code enforces it.

## Build and check a faithful model

1. Name the decision the model can inform and what result would change it. For validation
   of a settled design, say so; do not invent alternatives. Preserve the starting candidate.
2. Pin source/model revisions, ontology IDs and properties. Save artifacts under
   `.g5/TLA_verification/` using the [storage reference](setup_foundation.md#artifact-paths).
   Keep one coverage map from obligations through properties to results and gaps.
3. Build the state and transitions using the correspondence rules above; record environment
   assumptions, abstraction limits and finite bounds. Apply the model review checks above
   to permitted, forbidden and failure cases.
4. Execute TLC and investigate unexpected results. Distinguish intent gaps, code defects,
   model/binding errors and uncertainty. Refine the same contract and evidence below,
   then recheck affected configurations, controls and legitimate completions.

## Compare useful alternatives

Compare credible candidates under the same required outcomes, permissions, environment,
failures and bounds. Label representation improvements, behavioral repairs and deliberately
broken controls separately; none requires a quota. If fidelity needs different assumptions
or bounds, explain why results are not directly comparable. Check newly exposed behavior
and preserved legitimate outcomes. A passing final model alone does not establish that
modeling discovered a simplification.

Start with removal, derivation or reuse of an owner/protocol versus added independent
state. Test apparent redundancy by removing a mechanism under the same obligations; a
guard protecting only its own mechanism's state does not establish necessity. Investigate
added state and recovery coupling even without a large state-count increase. For unexplained
state-space growth, separate changed bounds, history, monitors and abstraction from actual
production lifecycles before proposing a simplification. Counts are quantitative evidence
when scope and bounds are comparable, not a standalone minimality test or failure threshold.
Never hide required concurrency
or shrink bounds to improve the count; report a missing comparable baseline.

An uncertain guarantee deciding the choice is a verification target, not an environment
assumption. Check how its owner establishes it across entry points, retries, recovery and
late effects. Do not assume atomicity, serialization, completeness or authority through a
convenient phase variable. If enforcement is outside the model, name the boundary and
independent check still needed.

Report whether executed evidence supports a simpler candidate, requires a repair or retained
mechanism, reinforces the original choice under named premises, or adds no useful evidence.
Distinguish discoveries from deliberate controls. Do not silently adopt changed product
behavior, weaken intent or call bounded checks a minimality proof.

## Design decisions outside the model

Equivalent modeled behavior can hide different ownership, mutable interfaces, caller
obligations or extension costs. Inspect owner operations and callers: which invariants
must callers reconstruct, what is authoritative or derived, and what other actions must
change? Include omitted recovery, compatibility and operating costs. A module name is not
an encapsulation property.

When source bindings map one checked complete contract to independently maintained
production bodies, compare a shared implementation. Identify which implementation and
correspondence obligations would become shared, which remain caller-specific, and any
semantic differences or coupling costs that justify separation. Sharing a model action
alone does not establish that the production contracts are the same.

Fewer states do not justify broader mutable access, weakened progress, hidden provider
promises or unsupported capacity limits. If the model cannot distinguish the disputed
choice, say so and decide on the relevant unmodeled grounds. Retain consequential conclusions
in the existing design, not a second checklist. Design-only work stops before implementation
and runtime testing.

## Execution evidence and reuse

Use [result integrity and reuse](setup_foundation.md#execution-evidence-and-reuse)
for completed executions, input fingerprints, expected outcomes and current applicability.
Select affected properties and shared assumptions
before broad reruns; report fresh executions, applicable saved results and missing checks
separately. For initial uplift, follow the [compute limits and resumption guidance](../uplift-evidence.md#bound-execution-and-make-handoffs-resumable).

## Refine the ontology from model findings

Correct model/binding mistakes as such. Record violations of valid intent as code gaps
and repair only when authorized. Amend the owning ontology and accepted design for
consequential discoveries before dependent work; do not weaken intent to fit code.
Keep executable mechanics in evidence. A property does not require a new block; use a
child only for independently useful precision, with the [nested ID format](../ontology-format.md#blocks-and-ids).

Preserve essential conditions, open Q choices and unmodeled obligations. Finite bounds and
convenient model assumptions do not become product limits or guarantees. Link the affected
property and scoped result in metadata, carry the finding into proposed or authorized
runtime tests, and recheck affected properties. A passing child does not verify its whole
parent or implementation.

## Turn the model into discriminating tests

Apply this section when trajectory tests are authorized or required by the invoking
workflow; otherwise retain concrete proposed cases without claiming runtime evidence.
Trajectories supplement tests derived from the governing ontology and requirements;
obligations absent from the model still need coverage.

Map selected counterexamples, valid completions and alternative schedules to real
public operations and observable state. Control relevant ordering, duplicates,
crashes, stale identities and commit/response loss deterministically. Exercise real
persistence and workers where those boundaries supply the guarantee; simulate only
external dependencies and label their assumptions. Use independent persisted-state
oracles and external-effect journals, not the production function as its own oracle.

When two interpretations of a rule fit the existing tests, choose two cases that differ
in one relevant fact. State whether the required outcome should change or stay the same.
Exercise the production path that supplies that fact and observe the outcome at the
consumer named by the requirement.

Check test doubles and schedules against reachable production behavior before accepting
a reproduction: a helper may swallow an error, select different authority or serialize
work. Do not copy the algorithm or remove its real protection to manufacture a defect.
Report the narrow observation and missing boundaries; a partial path is not full E2E proof.

Check that the repair prevents forbidden effects while preserving permitted completion
and required correction or retry. Refusal is appropriate only where the governing contract
permits it; check its required state preservation and valid continuation. A repair may
instead change the transition or commit boundary. Do not replay a counterexample's later
steps when the repaired execution can no longer reach them.
Include a control demonstrating that the assertion detects removal of the protection.
Reuse existing tests when they already cover the obligation; add missing schedules
or boundaries rather than duplicate them. Required trajectory tests must pass after
the final relevant changes. Fix in-scope defects when authorized, and record
blocked/unexecuted cases as incomplete with the available evidence.

Maintain the link `ontology → property/trace → code action → test → result` in the
existing design/review evidence. Map each new modeled property to a named runtime test
and independent assertion. For protection supplied outside the model, record a runtime
control or explicit sensitivity gap; a broken model alone does not show that the test
detects the implementation defect. A reviewed binding and a finite executed trajectory
suite are not formal refinement proofs. Update scoped metadata using the
[storage format](../ontology-format.md#metadata).

### Optional automated model-to-production replay

Where many relevant cases can share a reference model, consider automated model-to-production
replay: execute corresponding operations and compare observed state, results and effects
through an explicit mapping. Check that observations form an allowed model execution,
including nondeterministic choices. If using a separate executable reference, establish its
correspondence to the checked model. Apply the existing independent-oracle, control and
evidence rules; retain targeted tests and requirement-based assertions because model and
code can share the same mistake.
