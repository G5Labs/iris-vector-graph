# Hand off a Verus foundation

Use the project's existing verification tree, commands and evidence formats. If it has no location, put a runbook and coverage map under `.g5/Verus_verification/` beside the shared ontology. Link existing Cargo crates, test projects or native fixtures in place. Link Verus evidence from the relevant ontology metadata using ordinary Markdown. G5's TLC state-machine viewer expects its own manifests and receipts. Preserve existing TLC evidence and use the [ontology format](../ontology-format.md) for any verification tag. Tag a statement `implementation-verified` only when the product's own executable body is verified against it. A proof over a model or a transcription does not qualify.

## What the next reviewer needs

In the runbook give the product and model revisions, toolchain and library pins, working directory, dependencies, and copyable commands for one real obligation. Show how to run its proof or exploration, exercise its faulty control, compare the product observation if available and find the raw verdict. State the expected result for each command. For a design-only handoff, identify the observations that become possible once code exists.

Maintain one coverage map from governing clause to model property, product operations, evidence and remaining work. For each material claim record:

| Question | Record |
| --- | --- |
| What is required? | Source and scope, owner, observable outcome, accepted decision or open question. |
| What has formal support? | Exact theorem and domain, or finite model, property, configuration and exploration limits. Identify trusted items, external premises and unproved obligations. |
| What connects it to the product? | Verified executable body, source-bound transcription with native observations, inspection, tests, or missing binding. Identify the final reader and unchecked layers. |
| What may another change rely on? | Supported within scope, conditional on a named premise, confirmed violation, unresolved authority, or unestablished. Cite the receipt and the next action for any blocked reliance. |

## Execution evidence and reuse

Keep each run's actual inputs, exact command, tool versions, selected targets, raw log, expected and observed substantive verdict, and any witness or counterexample. Capture the inputs that determine applicability, including the governing clause, proof and imported definitions, trust boundary, product bindings, environment and configuration. Compare these with the current candidate before citing an earlier result. Decide separately whether the theorem still follows from the same formal inputs and whether its binding still applies to this product. A new implementation can reuse an unchanged theorem while requiring fresh correspondence evidence. A changed replay adapter or expected-result calculation reopens the observations that use it. Record reuse and its justification separately from fresh execution. A new caller, writer or provider guarantee can change applicability even when the theorem text is identical.

During development rerun affected units and controls. On the final candidate, run the complete affected proof targets and native suites, verify their selected tests and expected verdicts, and apply the project's required integration checks. Distinguish exhaustive finite exploration from a search cut short. Preserve unsuccessful runs. A zero-test result, missing target, stale log, timeout or resource-limit result leaves the claim open. If using a freshness gate, exercise it on a changed proof input with the old receipt and require rejection. Preserve reviewed additions when regenerating artifacts using the [shared evidence rules](../uplift-evidence.md#preserve-reviewed-work-during-regeneration).

At an initial foundation handoff, have a reviewer use the runbook to reproduce a representative result and its distinguishing control. Report changed, newly established and inherited guarantees, human decisions and their sources, unresolved intent and what a consumer must still establish. Keep a confirmed product defect visible even when the check that reproduces it succeeds.
