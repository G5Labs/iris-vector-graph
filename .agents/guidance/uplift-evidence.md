# Uplift execution and evidence

<a id="retain-evidence-for-the-actual-claim"></a>

Use the project runner for the selected uplift. For TLC follow the [artifact paths](TLC/setup_foundation.md#artifact-paths) and [execution evidence and reuse](TLC/setup_foundation.md#execution-evidence-and-reuse). For Verus follow the [foundation handoff and receipts](Verus/setup_foundation.md).

For a requested comparison of harness revisions, use [controlled evaluation](uplift-evaluation.md). Its benchmark inputs and held-out expectations are separate from ordinary uplift inputs; running an evaluation is not a prerequisite for each project uplift.

## Bound execution and make handoffs resumable

The orchestrator owns a shared compute budget for heavy checks across workers. Choose concurrency from available memory/CPU and observed model cost; parallel agents do not each receive an independent full-machine allowance. Keep semantic work parallel while queuing expensive runs. Retain finite bounds, time/resource limits, tool versions and the reason for any reduced exploration. A timeout or resource exhaustion is an incomplete check, never a pass or a reason to silently remove required behavior.

Use native session/sub-agent facilities and isolated write ownership or worktrees as available. Record the inputs, outputs, active runs and remaining obligations at handoff. On interruption, inspect artifacts and raw logs before deciding what completed; an agent's final message or process disappearance is not execution evidence. Resume useful work without repeating unchanged campaigns. Persist C's round counter so a resumed worker does not restart its review budget.

## Preserve reviewed work during regeneration

Generated verification artifacts must be reproducible from maintained inputs, or regeneration must stop before overwriting later reviewed work. Check regeneration in a disposable location for dropped assertions or configurations, lost bindings or coverage decisions, and changed formal inputs. Integrate reviewed additions into the generator or its maintained inputs; until then, guard against overwriting them and record the limitation. Preserve execution receipts and apply the foundation’s reuse rules to changed outputs; regeneration alone neither executes checks nor renews their applicability.
