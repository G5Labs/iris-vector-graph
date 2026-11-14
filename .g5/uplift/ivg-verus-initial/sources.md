# Source inventory — IVG initial Verus uplift

Product pin `3eaa79cf` (v4.7.0 + checklist). This inventory locates evidence; it is not a governing specification. Per-domain tables with exact inspected portions are in the stage-A notes linked in the last column. Authority: **H** human requirement or answered question (with how it is recorded), **D** accepted design decision, **O** observed implementation, **E** evidence (tests, runs).

All 2,671 commits carry one Git author name, so authorship cannot show independent agreement. Human authority is recognised only where a source records a human decision: spec 256 "Decisions (Tom, 2026-10-22)" (secondhand, via the consumer's agent), the CONTEXT.md glossary entries marked "Decided <date>", and spec Clarification sessions that quote the requester.

## Discovered and inspected

| Source group | Locator | Revision/date | Authority | Status | Detail |
|---|---|---|---|---|---|
| Product glossary | [CONTEXT.md](../../../CONTEXT.md) | pin | D; H for dated "Decided" entries | inspected whole | all notes |
| ADRs 0001–0016 | [docs/adr](../../../docs/adr) | 2026-09-14 … 2026-11 | D (no recorded human decider) | inspected per domain; ADR-0016 says "implementation pending" though merged | [platform](intent/platform.md), [ledger](intent/ledger-history.md) |
| Spec 256 tenant redaction | [specs/256-ledger-tenant-redaction](../../../specs/256-ledger-tenant-redaction) | a140ed78 (draft) → 42907b21 (decisions) → 2b8ea46d (plan) | H secondhand for Decisions 1–4; D for plan | inspected whole; spec text contradicts its decisions in FR-004, SC-004 and one edge case | [ledger](intent/ledger-history.md) |
| Spec 213 ledger contracts | [specs/213-graph-revision-ledger/contracts](../../../specs/213-graph-revision-ledger/contracts) | 04bf1c67 (4.1.1) | D | inspected; not updated for spec 256 | [ledger](intent/ledger-history.md) |
| Specs 204, 234, 239–255, 257–262, 044, 025, 201, 203, 229 | [specs](../../../specs) | various | D; several still say "Draft" or "not adopted" after release | inspected per domain | domain notes |
| OpsReview brief | [IVG-OPSREVIEW-BRIEF.md](../../../docs/dev/notes/for-opsreview/IVG-OPSREVIEW-BRIEF.md) | 2026-10-25 | IVG-side summary of the consumer (not consumer text) | inspected parts; its usage example line 125 is wrong | [ledger](intent/ledger-history.md) |
| Guides | [USER_GUIDE](../../../docs/USER_GUIDE.md), [API_REFERENCE](../../../docs/API_REFERENCE.md), [ADMIN_GUIDE](../../../docs/ADMIN_GUIDE.md), [ARCHITECTURE](../../../docs/architecture/ARCHITECTURE.md) | pin | D/O | inspected per domain | domain notes |
| Release record | [CHANGELOG.md](../../../CHANGELOG.md), [KNOWN_ISSUES.md](../../../docs/KNOWN_ISSUES.md), [PRE_RELEASE_CHECKLIST.md](../../../PRE_RELEASE_CHECKLIST.md) | 4.0 … 4.7.0 | O/D | grep-driven per domain | domain notes |
| History | `git log` / `git show` on the worked-example commits (a140ed78, 42907b21, 2b8ea46d, e4b5eef5, 9afe0822) and later fixes | 2025-09-24 … 2026-11-12 | O, with defect narratives | inspected for ledger, eraser, temporal, search, cypher | domain notes |
| Product code | `iris_vector_graph/`, `iris_src/src/Graph/KG/`, `api/`, `sql/` | pin | O | inspected by operation; independent operation inventory | [operations](intent/operations.md) |
| Tests | `tests/unit`, `tests/integration`, `tests/e2e`, `tests/contract` | pin | E (live-DB vs mocked/source-text noted) | read per domain; executed against this arm's IRIS (see runbook) | domain notes, [runbook](../../Verus_verification/runbook.md) |
| Dependencies | [pyproject.toml](../../../pyproject.toml), [uv.lock](../../../uv.lock), IRIS Community 2026.x in container `ivg-g5-verus-20261113-iris` | pin | external premises (IRIS transactions, locks, SQL isolation) | IRIS behaviour relied on is listed as premises in the coverage map | [coverage](../../Verus_verification/coverage.md) |
| Experiment seed | [experiment/g5-verus/index.md](../../../experiment/g5-verus/index.md) | staging commit 203fd4b8 | prior agent summary (a lead, not authority) | every seed row challenged; corrections recorded in the domain notes and [final report](final-report.md) | domain notes |

## Unavailable or absent (not reviewed)

| Source | Why it matters | Follow-up |
|---|---|---|
| Spec 213 `spec.md`, `research.md`, `data-model.md` | FR-023 (immutability) and FR-047 (revision iff mutations visible) are known only through citations in code, ADR-0013 and commit abf4e6eb | ask the maintainer for the originals |
| Spec 256 `research` / `decisions` files | do not exist; decisions live in spec.md | none |
| OpsReview specs 055/056, agent-bus messages | the consumer's own words and acceptance for redaction | ask OpsReview |
| Specs 226, 227, 230 | FR numbers for graph-scoped embeddings and the (graph_id, node_id) re-key are known only from code comments and CHANGELOG | ask the maintainer |
| Specs 195, 196 | origin of `/fhir-event` and the API key | low priority (`/fhir-event` deprecated for 5.0) |
| External opsreview BM25 request file | origin of spec 044's performance requirements | low priority |

## Superseded or contradicted material noted

- ADR-0016 "implementation pending" and its description of classes reading the schema record (superseded by the 4.6.0 implementation).
- Specs 240/241 "not adopted" although merged; specs 235/236 still "Draft".
- Spec 256 FR-004, SC-004 and the "revision count does not change" edge case predate Decisions 1–2.
- USER_GUIDE says retries replay automatically; replay requires an idempotency key.
