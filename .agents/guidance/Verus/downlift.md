# Initial downlift with Verus

Use for an explicitly requested initial design from requirements, its authorized implementation or its continuation. Keep one plan, using `.g5/downlift/<task>/downlift-plan.md` if there is no existing plan. For a feature on an established product, use the [new feature PR guide](new-feature-pr.md).

## Design from the retained outcomes

Pin the requirements, mocks, accepted decisions and current [ontology](../ontology.md). For a replacement product or migration, identify the existing journeys, stored data, compatibility and rollback commitments. Mark each original core feature retained, changed or deferred with its source and observable acceptance condition. Develop a readable initial ontology and save the initial design before refinement. Record a provisional choice and its consequences when intent remains open.

Compare credible simpler designs under the same outcomes, permitted failures, concurrency and operating envelope. Use the installed ontology-planning skill's design-evaluation dimensions as in initial G5 downlift. Include consequential choices outside the models. For each retained core feature, map its obligations to actual properties, use cases and remaining checks. Share proofs across features when they implement the same rule.

## Refine the design before implementation

Use [Verus verification](verification.md) to formalize the governing behavior first. Establish the domain and invariant for a calculation, or the L1 business transition and proposed L2 representation for a stateful design. Identify the data owner, real or proposed synchronization and persistence boundaries, permitted failures, retries and required progress. Check the relevant reusable environment contracts against the intended deployment, leaving unestablished premises explicit.

Prove the relevant refinements and run controls that remove a required effect, admit an invalid action or exclude legitimate completion. For an interaction, exercise a distinguishing interleaving. Retain the original design, counterexample and revised design so a reviewer can see what the verification changed. Review the final design against all retained outcomes and the supported input domain. A design-only request ends with the checked ontology and design, model evidence, unresolved decisions and the exact implementation paths and runtime cases still to establish.

## Implement and hand off within scope

When implementation is authorized, bind the selected design to actual entry points, storage, jobs and final readers as they are built. Revise the owning commitments when implementation exposes a material assumption. Use body verification where supported and run native end-to-end journeys for required success, refusal and recovery, including discriminating trajectories derived from the model. Check compatibility with existing data where applicable. Recheck affected proofs, controls and product cases after the final relevant change.

Complete the [foundation handoff](setup_foundation.md) at the achieved stage. Identify the evidence for each retained feature, human decisions, conditional claims and blocked checks. Keep later incremental changes on this foundation.
