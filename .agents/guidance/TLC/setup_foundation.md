# Set up and hand off a verification foundation

At the end of an initial uplift or downlift, check that a fresh reviewer can use the project's models and evidence. During modeling, use the [artifact paths](#artifact-paths) and [receipt rules](#execution-evidence-and-reuse) as needed. For design-only work or deferred execution, identify the outstanding checks and how to run them. When asked to prepare existing material for G5's viewer, follow the [viewer instructions](#prepare-material-for-the-viewer).

## Project runbook

Put the run instructions in the verification root's `README.md`, or link from it to the existing project runbook. Give the product and verification revisions, working directory, tool prerequisites and one runnable example using a real concern and run label. Reuse project commands and add a small helper only where there is a gap. PairSoft illustrates three jobs that can be implemented together or separately.

| Job | What the next reviewer needs | PairSoft example |
| --- | --- | --- |
| Validate saved evidence | Check whether a named receipt still supports its declared result. Report stale, missing or incomplete evidence and why. | `validate_campaign.py` |
| Execute an affected check | Select a model and configuration, reuse a justified result or run TLC, and show where the receipt, log and trace were saved. Distinguish an expected control failure from an incomplete run. | `campaign.py` |
| Review applicability | When code, governing intent or a binding changes, prepare a pending review tied to the receipt and current inputs. The reviewer inspects the affected operation and records the reason for reuse or the follow-up needed. | `prepare_applicability_review.py` |

## Artifact paths

The verification root is `.g5/TLA_verification/`, beside `.g5/ontology/`. In a checkout rooted at `.g5`, use `TLA_verification/` and `ontology/` directly. Paths below are relative to the verification root. Keep the project's existing organization where it works. Use the listed manifest, bindings, index, receipt and findings paths for material the G5 viewer reads.

| Path | Contents |
| --- | --- |
| `models/<concern>/` | TLA+ modules (`.tla`) and TLC configurations (`.cfg`). `BINDINGS.md` explains how model actions correspond to implementation operations or the proposed design, with assumptions and limits. |
| `models/<concern>/manifest.json` | The checked `question`, governing `ontology_ids`, optional display `title` and declared `runs`. Each run has a `label` and, where known, `spec`, `cfg`, `kind`, `variant` and `expect`. The variant identifies the as-built, intended, repair or simplified model. |
| `results/<concern>/<run_id>/` | One directory per execution. Keep `receipt.json` with the recorded outcome, input revisions and state counts, alongside the executed inputs, raw log and any trace. |
| `results/index.jsonl` | One JSON object per execution with `concern` (the model folder name), `label`, `outcome` and `run_id`. Start the run ID with the UTC time as `YYYYMMDDTHHMMSSZ`. Include `kind`, `variant`, `expect`, `distinct_states`, `states_generated` and `depth` when known. The concern and label connect a result to its declared check. |
| `bugs_issues.md` and `design_simplification.md` | The viewer's two [findings files](#findings), for unresolved bugs or issues and proposed simplifications respectively. |
| `runner/` and `tools/` | Optional locations for reusable project commands and checker tools kept in the repository. |

## Execution evidence and reuse

Record the command, tool and adapter versions, fingerprints of the executed model, configuration and transitive dependencies, property and expectation, bounds, assumptions, governing ontology, code bindings and implementation revisions. Preserve unsuccessful runs and original receipts. Distinguish safety checks, as-built divergences, deliberately broken controls and reachability witnesses.

Read TLC's completion status, reported property and trace. Test the adapter with real output for success, the specific expected violation or witness, a malformed configuration, a different failing property, incomplete exploration and resource failure. A witness can stop at its target. Check that the validator accepts current evidence and rejects stale inputs. A successful process exit alone cannot establish either result.

Rerun affected checks when formal inputs change their meaning. Reuse requires a complete execution with matching formal inputs and recorded provenance. If code, governing intent or a binding changes, establish correspondence at the new revision and save the applicability decision separately. A changed expectation needs fresh adjudication and matching evidence. Report reused results as saved executions. A valid receipt covers the modeled claim under its recorded assumptions. For a proposed simplification, record the as-built and proposal runs using the [comparison rules](#simplification-comparisons).

## Check the handoff against real evidence

Follow one representative claim from its ontology statement to its property, configuration, bound operation or design, and saved result. Try the documented command and confirm that the current result can be identified. In the existing coverage map, link each checked claim to its selected receipt and any applicability decision. Reconcile totals with declared configurations and actual executions. Count a control detection once even when it supports several claims. Keep superseded attempts accessible as history. Record missing checks, open decisions and the conclusions they limit.

## Prepare material for the viewer

For a viewer handoff, check the [artifact paths and fields](#artifact-paths) and fill missing manifest or index fields from the saved evidence. For a formatting-only request, update formats, locations, links and findings. Preserve ontology meaning and recorded outcomes. G5 displays the saved model and results directly. A model link in the governing statement's metadata, a manifest and an indexed run make the evidence discoverable.

G5 shows `PASS` for an expected pass and `EXPECTED_<result>` for a detected expected violation or deadlock as matching their expectation. It marks `ERROR`, `TIMEOUT` and `RESOURCE` incomplete and shows other mismatches as unexpected. Report what you could establish from the original records and any gaps.

### Findings

Start with the [pre-edit snapshot](#format-checks) so the checks include the owner’s uncommitted decisions. G5 lists the files in the Core Ontology panel, where the owner can turn an entry into a tracker issue. Keep them in the verification root and link entries from the affected statements' metadata.

Use a stable, unique anchor immediately followed by a `###` heading that describes the problem or proposed change in one plain sentence. Use `####` or lower for headings inside the entry. This example shows the paragraph breaks the viewer reads.

```markdown
<a id="bug-001"></a>
### Duplicate order lines bypass the receiving limit

Severity: High · Decision: Open

Run: Uplift 2026-10-24

Found by: [asbuilt-dup](results/receipt-submit/20261024T120000Z-asbuilt-duplicates-a1b2c3/receipt.json)

Reproduced by: [QuantityLimitTests](../../src/Receipts.Tests/QuantityLimitTests.cs#L40) failed with two lines for one PO item.

Explain the consequence, the proposed repair and the governing statements and code.
```

- **Severity.** Use `Critical` for a security breach, data loss or a halt for many users. Use `High` for wrong business results, an authorization bypass or work completing without required review. Use `Medium` for visible misbehavior or an issue an administrator can repair, and `Low` for cosmetic issues, misleading text or documentation drift. Lower severity one level for an unconfirmed trigger, keeping Low at Low. Use `Unranked` when the evidence states no consequence.
- **Decisions and order.** Defects worth fixing, open product questions and recommended or conditional simplifications end their status line with ` · Decision: Open`. Put actionable entries first, highest severity first and Unranked last. Put observations, documentation drift, accepted exceptions and merged, rejected, retired or withdrawn proposals afterward under their own `##` heading, with severity alone on the status line.
- **Later runs.** Extend the existing files. Keep stable IDs and use fresh IDs for new entries. The separate `Run:` paragraph names the run that first recorded the entry. Use the run's supplied label, or `Uplift YYYY-MM-DD` for uplift. Keep it on carried entries and leave older entries without a run line as they are. Open entries can be updated or removed. An owner decision of `Need fix`, `Defer` or `Irrelevant` protects the whole entry, including uncommitted edits. Move a decided entry only to keep the order.
- **Bug evidence.** On separate paragraphs after `Run:`, use `Found by:` for receipts showing the issue or checking its repair, or explain another source such as `source review`. Use `Reproduced by:` for the test, result or runtime probe that demonstrated the behavior in code and say what it showed. Use `Reproduced by: none` when there is no runtime reproduction. Cite the direct evidence and omit a `Sources:` line listing earlier registers.
- **Ontology links.** End the metadata of every named statement outside the ontology root with a `Findings:` line linking back to the entry. Use the entry title and a path relative to the statement's file, for example `[Duplicate order lines bypass the receiving limit](../../TLA_verification/bugs_issues.md#bug-001)` from a feature page. Replace links to superseded registers. Keep the findings files out of Project Docs and the ontology root's navigation.

### Simplification comparisons

Say what makes the current design complicated, what would change and which behavior is preserved. Use `Comparison: [As-built](<receipt>) → [Proposed simplification](<receipt>)`. Find both runs in the evidence using the model variant and matching configuration, including when only the proposal was named in the entry. Identify a repair or intended variant accurately when it supplies the proposed model. Report both state counts and their ratio or percentage change when available. Counts measure explored model states. If specs, bounds, constraints, properties, behavior or completion differ, start the explanation after the second link with `Scope qualification:` and explain the difference. Keep available scores visible, including for a counterexample or incomplete run.

Use `→ none` only when no proposal run is recorded. Use `Comparison: none` with the reason when both runs are absent. If a run's role is unclear, inspect its configuration and bindings. In an authorized verification campaign, execute missing sides of actionable Critical or High comparisons and retain their receipts and counts. For a formatting-only request, report a missing execution as a gap.

### Format checks

From the repository root, save the working copies **before** changing the findings. In a checkout rooted at `.g5`, set `g5_dir=.` instead. In the G5 runtime, use the installed guidance directory shown here. In the harness source checkout, set `guidance_dir=.agents/guidance`.

```sh
g5_dir=.g5
guidance_dir="$HOME/.agents/guidance"
previous_findings=$(mktemp -d)
for file in bugs_issues.md design_simplification.md; do
  if [ -f "$g5_dir/TLA_verification/$file" ]; then
    cp "$g5_dir/TLA_verification/$file" "$previous_findings/"
  fi
done
```

After preparing the material, run all three checks from the same directory and shell.

```sh
python3 "$guidance_dir/scripts/link_verification.py" "$g5_dir/ontology"
python3 "$guidance_dir/scripts/check_ontology.py" "$g5_dir/ontology"
python3 "$guidance_dir/scripts/check_findings.py" "$g5_dir/TLA_verification" "$g5_dir/ontology" --previous "$previous_findings"
```

Resolve the model IDs reported by the linker. Preserve a renamed ID as an alias anchor directly above the current anchor. Use one metadata tag kind per bullet, with tags only and no trailing punctuation. Encode spaces in link destinations as `%20`. Follow the [ontology format](../ontology-format.md) for statement syntax. Fix reported format errors and list anything still unresolved in the handoff.
