# Initial uplift with Verus

Use for an explicitly requested recovery of an existing product's governing contract, or a continuation of that recovery. Confirm the source set and scope from the request and prior decisions, including whether the frontend is included. The usual initial scope is backend behavior. A missing ontology alone does not start uplift. Use the existing plan or `.g5/uplift/<task>/uplift-plan.md`. Keep baseline revisions, assignments, evidence, open obligations and the review-round count there.

One orchestrator owns integration. Delegate intent recovery, modeling and independent review to isolated sessions with bounded questions and write ownership. When isolation is unavailable, do the useful serial work and record independent review pending and the uplift incomplete. Use the [shared execution and evidence guidance](../uplift-evidence.md) to budget expensive runs and resume from actual artifacts. Existing authorization governs product repairs, new runtime tests and any deferred execution.

## A. Recover intent and challenge ontology coverage

Follow [intent recovery](../uplift-intent-recovery.md) and the shared [ontology conventions](../ontology.md). Pin original requirements and decisions. Independently inventory operations from entry points through writers, commits, external effects and final readers. Reconcile the two inventories in one coverage map, including unmatched operations and partially covered clauses. Preserve valid prior commitments and separate observed behavior, open policy choices and proposed repairs. The root should let a reader find and reconstruct the major capabilities.

For a consequential lifecycle, compare commands in states where the required result changes. Identify one valid completion and a neighboring refusal or failure from the sources. Have a fresh reader reconstruct the behavior from the ontology, then compare it with the original evidence and correct unsupported or missing rules. Carry unresolved intent into the model as a visible condition.

## B. Model behavior and connect it to implementation

Follow [Verus verification](verification.md) for all important in-scope behavioral obligations. Establish the L1 rule, the as-built L2 transition or function, and its binding to actual L3 operations. Share models across related obligations and give structural clauses a reasoned disposition. Before expanding proofs, challenge decisive premises at their real producers and check that the model can represent the cases recovered in stage A. Check the actual provider and library contract where it supplies the guarantee.

For example, when one command changes two records, locate each commit. Where the commits are separate, compare a fault inside a transaction with a fault between them, and observe both records and the result of a retry. A proof that assumes one atomic write answers the question only if the product establishes that boundary. Record formal and native outcomes separately.

For each remaining clause inherited from an older foundation, name the current owner, the exact assertion and applicable evidence, and the part still uncovered. After a counterexample, inspect the complete production path and decide whether the error lies in the contract, model, binding or product. Reopen stage A when the source evidence changes the interpretation. Keep a proposed repair separate and state the behavior to preserve, affected writers and readers, and a case that would distinguish success. Run authorized checks on the reviewed artifacts.

## C. Independently review, fix and recheck

Use the [shared independent review and repair loop](../uplift-review.md). Each round challenges both coverage and fidelity against original sources and actual operations. Ask the reviewer to try a false premise, an erroneously permitted step or a faulty implementation and also establish that a valid outcome survives. Examine actual verdicts and the product binding. Repair the owning artifacts and validate the repairs. The default maximum is three rounds for the whole uplift, including resumptions. Stop early after a clean independent review and completion of feasible required work.

Compare the final ontology bodies with the baseline for lost conditions, exceptions and uncertainty, including statements that changed parents. Finish the [Verus foundation handoff](setup_foundation.md). Report incomplete required work, established and conditional claims, product defects and human decisions. A documented product defect can coexist with a completed uplift.
