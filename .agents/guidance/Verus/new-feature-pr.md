# Develop a new feature PR on a Verus foundation

Use when the task adds a feature to a product that has a Verus foundation. Start from its actual pre-feature revision and project runbook. Continue one plan through design, implementation and final verification within the request's authority. For review of an already implemented feature, use [incremental re-verification](incremental-reverification.md).

## Establish the feature boundary

Read the full authorized feature packet, including acceptance conditions and later owner decisions. Pin the pre-PR product, ontology, toolchain, foundation and available evidence, and note where that evidence was produced on a different revision. Record what earlier guarantees the feature will rely on, any inherited limitations and which dependencies the change can invalidate. Keep a single obligation map from required outcomes to changed or unchanged operations, model properties and evidence. Inventory the whole feature even when implementation will proceed in slices.

Before the first slice, design the rules whose meaning can change an outcome. Name the business identity, units, owner, legal transitions, refusal, side effects and permitted default for each relevant consumer. For facts a rule depends on, find each writer and final reader from schemas, registrations, calls and queries. A new caller or event consumer can change an existing invariant without changing its source file. When the feature adds a state or status, check which existing commands can receive it and what affected readers must show or do. Capture a concrete pair of cases when two interpretations produce different outcomes. Update the owning ontology and record remaining choices in the plan.

## Build in verified slices

For each coherent slice establish the required contract, implement the change and apply [Verus verification](verification.md). Reuse existing proofs only after checking their domains, caller premises, trust and environment. Extend an existing state machine when it can distinguish the new behavior. Where it cannot, change its representation and recheck what relied on it. For storage and protocol changes, include compatibility with prior records, actual transaction boundaries, redelivery or interruption, and the consumer-visible result.

Connect each proof or bounded result to the implemented path and its final reader. Include a valid use and a control that breaks the relevant rule. Exercise the distinction in the actual product where the binding depends on unverified code. Measure affected performance or capacity when it is a requirement or the design changes the operating envelope. Record baseline defects and their effect on reliance. If a premise is unestablished, keep the dependent claim conditional. If the premise is known to be false on this path, establish the feature’s guarantee another way or report it as unsupported. Keep any broader repair within its authorization.

## Qualify the final candidate

Reconcile the full diff, including late edits and deletions, with the feature packet. Derive expected results from the original sources before comparing them with the author’s evidence. Use a fresh reviewer when available. Review all affected inherited obligations, callers and consumers. Classify existing evidence as still applicable, rechecked, invalidated or missing. Run the complete affected proof targets, controls and native suites on the frozen candidate, with fresh receipts for changed inputs. Include the existing integration, migration or end-to-end checks that supply required behavior.

Hand off the ontology delta, changed guarantees, decision sources, raw results and exact remaining limits under the [foundation receipt rules](setup_foundation.md). Completion requires evidence for the whole requested feature, including preserved legitimate behavior. State which accepted obligation remains unmet if the feature is incomplete.
