# Initial uplift: recover and check the governing contract

Read only for an explicitly requested initial uplift of an existing codebase, or continuation of that recovery. Missing ontology and ordinary maintenance do not trigger this process. Uplift produces ontology, source and coverage evidence, TLA+/TLC checks, findings and repair proposals. Application repairs, new runtime tests and subsequent downlift retain their own authorization; existing authorization counts.

## One orchestrator, three delegated stages

One main agent owns the plan, integration and completion decision. Delegate **A. intent recovery**, **B. models and implementation correspondence**, and **C. independent gap closure** to isolated sessions or sub-agents with bounded context. Parallelize by coherent domain when useful, with disjoint write ownership. No particular provider, programming language or number of workers is required. If isolation is unavailable, complete useful work serially, then report **independent review pending** and the uplift incomplete. Repeating same-context self-review does not satisfy independence or justify consuming review rounds; resume at the saved round when an independent reviewer becomes available.

Continue the existing plan, or use `.g5/uplift/<task>/uplift-plan.md`. Persist scope and revisions, assignments, artifact locations, open obligations and the C round counter. Each handoff includes its question, source/ontology/model inputs, accepted decisions, write scope, permitted execution and required evidence. Do not rely on inherited conversation; the orchestrator checks returned artifacts and resolves conflicts before integration.

Establish the source set, authority and scope with the human, reusing confirmation already in the conversation. Identify unavailable sources and whether the frontend is included; the default scope is backend behavior. Resolve material scope changes, not each new source link. Honor an explicit decision to defer model execution, and report that limitation. Use [execution and evidence guidance](../uplift-evidence.md) for bounded resources, resumptions and result integrity.

## A. Recover intent and challenge ontology coverage

Follow [intent recovery and the source inventory](../uplift-intent-recovery.md). Discover relevant original conversations, requirements, decisions, issues, diagrams, repository guidance, history, code, tests, configuration, schemas and operational evidence. Keep sources and their inspection status discoverable throughout A, B and C; a source inventory is a living input, not a one-time checklist.

Build capabilities from both source intent and an independent investigation of implementation operations. Trace important behavior through producers, entry points, guards, alternate writers, effects, consumers, failures and recovery. When an older uplift exists, reconcile both foundations against the current sources and implementation; preserve valid commitments and identify corrected, superseded, upstream-fixed and future-only material.

Write concise governing ontology using [meaning and selection](../ontology.md), [format](../ontology-format.md) and [examples](../ontology-examples.md). Distinguish human intent, agent decisions, observed behavior and proposed repairs. Keep genuinely unresolved intent in Q with the best-supported production-ready option, its reason, material alternatives and conditional conclusions; the strictest policy is not automatically best. If no coherent provisional option is supported, ask the specific unresolved question and continue independent work. Do not add a requirement merely because it would make the feature more complete; include supported implications of governing intent. Detailed derivations belong in linked evidence unless they add independently useful governing precision.

Treat the ontology root (`.g5/ontology/root.g5.md`, or the project's existing equivalent) as a human landing page. Explain the system's purpose, major parts and how they fit together at a glance. Link to its child pages with short descriptions of what readers will find there, so they know where to go next. Keep this overview and navigation as ordinary Markdown outside ontology blocks. The root may also contain the highest-level human intent and other system-wide governing commitments as ontology blocks, with detailed contracts owned by the linked children.

Before declaring A ready, independently try to reconstruct the major functionality from the ontology and compare it with the source and operation inventory. Find omissions inside already-linked features, not just missing links. Every important capability needs an owner or reasoned disposition, and uncertainties must remain reachable. Later findings reopen the affected portion of A.

## B. Model behavior and connect it to implementation

Develop ontology and concern models together using the shared [model-checking mechanics](model-checking.md). Save TLA+/TLC artifacts under `.g5/TLA_verification/` following the [artifact layout](setup_foundation.md#artifact-paths). Check all important in-scope behavioral obligations with TLA+/TLC. Connect the abstract contract, implementation-shaped model and actual runtime operations using this approach; there is no Verus or production-code-generation phase.

Maintain one coverage map: source/capability → ontology obligations → model properties and cases → implementation operations/boundaries → results and gaps. Include material conditions and exceptions; one property or link does not cover a whole feature. Identify implementation functions/operations with unambiguous symbols and source locators, not just file or class links. For each important behavior, distinguish what is checked, partially checked, assumed or unmodeled; an implementation link alone establishes no model coverage. Structural obligations receive reasoned dispositions; missing behavioral checks remain gaps.

When reusing or consolidating a prior foundation, reconcile each material remaining clause in that same map with its current owner and the exact assertion, case or other evidence that addresses it. Record the reviewed revisions, covered part, assumptions and residual work; follow renamed or split owners by meaning. An owner link cannot close a gap or give related clauses coverage. Keep verification status, product defects and unresolved policy choices distinct: checking a defect does not repair it, and checking alternatives does not choose a policy.

Before expanding a model campaign, apply the shared [premise and abstraction checks](model-checking.md#connect-the-contract-implementation-model-and-running-code).

Keep intended, as-built and proposed variants distinct. Execute checks, investigate counterexamples through complete relevant code paths, and reconcile intent errors, model/binding errors, implementation defects and uncertain boundaries. Update the owning ontology bodies, correspondence and findings together. Suggest discriminating runtime cases; create and run new cases only within authorization. A successful command or a large count of models is not completion evidence.

For generated models, bindings and coverage artifacts, follow [regeneration preservation](../uplift-evidence.md#preserve-reviewed-work-during-regeneration) before replacing reviewed outputs.

For each material repair proposal, identify the governing obligation, owner/protocol to change, affected writers and consumers, behavior to preserve, and discriminating validation. Include recovery, compatibility, migration and operating consequences when material; identify unresolved choices instead of presenting a diagnosis or “add a guard” as a complete proposal. Scale detail to the finding and keep proposals separate from adopted requirements and implementation authorization.

## C. Independently review, fix and recheck

Follow [the independent review and repair loop](../uplift-review.md). Use fresh reviewers to challenge intent coverage, model semantics, implementation correspondence, evidence and simplification claims, then delegate repairs and validate them. A round may use several reviewers and repair agents. The default maximum is **three rounds for the uplift as a whole**, persisted across resumptions; three rounds are not mandatory.

Stop early only after a clean independent review and completion of feasible required work. At the cap, retain unresolved gaps and report incomplete work rather than silently starting another round. Finish with a human-readable semantic pass over the actual ontology bodies, then structural and link checks. After rewriting or reorganizing ontology, compare the final bodies with the governing baseline and relevant earlier revisions for lost conditions, exceptions, uncertainty and implementation-gap disclosures, following moved children by meaning. Stable IDs and links do not establish preserved meaning; retain valid commitments in readable prose and record reasons for substantive corrections.

Before the final report, complete the [verification foundation handoff](setup_foundation.md). Report scope, executed and reused evidence, findings, simplifications, decisions and limitations. Known product defects can coexist with a completed uplift; missing required investigation or checks cannot. Do not automatically begin implementation or another full campaign.
