# Review round 3 — R3-reader repairs (ontology)

The round-3 repair fork applied these corrections to `.g5/ontology/` only. It changed no register, coverage, plan or product file. Each claim was checked against the cited product source, read-only, before it was written. Scratch, the pre-repair snapshot and the full diff are in `$RUN_DIR/agents/R3-repair-ontology/` (`ontology-before/`, `ontology.diff`).

**Checks after the repair:**
- `check_ontology.py .g5/ontology`: 13 files, 358 blocks (348 before), 0 issues, 0 writing warnings.
- `check_findings.py .g5/Verus_verification .g5/ontology`: no problems found.
- Every ontology→register link label equals the entry's title (a scratch label check found 0 mismatches).
- All 63 Q blocks state a provisional answer or say there is none.

**New blocks:**
- `ledger.commit.post-commit` (D) and `ledger.commit.post-commit.recorded` (Q, linked to q-010);
- `ledger.lifecycle.disable-during-redaction` (Q, linked to q-led-003);
- `install.schema.speed` and `install.import`;
- `redaction.batches.speed`;
- `temporal.structural.explicit-delete` (Q, linked to q-tmp-006);
- `structure.write.engine-connection` (Q, linked to q-plt-006);
- `graph.names.report` (D);
- `search.erasure.indexes.graphless` (Q).

No block was renamed. `access.retries` keeps its ID and changes from D to Q.

| Finding | Disposition | Blocks changed | Notes |
|---|---|---|---|
| H1 post-commit properties | Applied | `ledger.commit` (body exception, Children), new `ledger.commit.post-commit` + `.recorded`, `ledger.strict` (body), `access.ledger_strict.undecided` (bullet), `access.ledger_strict.bypasses` (excepts the undecided list), root "how capabilities fit" | Strict-mode and marker gaps are recorded as suspected (bug-led-009). The verify divergence is observed. |
| H2 temporal premise and spec 256 deferral | Applied | `redaction.after-erasure.temporal` (body rewritten, q-009 link, deferral), `redaction.tenant` (own-graph bullet, bug-led-007/010 links), `erasure.prefix-match`, `temporal.erase` (body + Metadata, bug-led-007) | The bug-led-007 severity reweigh is a register change (see the report). |
| H3 FR-009 explicit branch | Applied | `install.schema.existing` (body bullet; Metadata divergence; bug-plt-026), `install.schema.concurrency.leftover` (narrowed; Metadata claim corrected) | The Q keeps its ID and parent, per the stable-ID rule. Its Metadata explains the placement. |
| H4 embedding claim | Applied | `search.embedding.claim` (body; contradicting Note removed) | Checked against `_read_route` (model_key only) and setup's claim path |
| M1 readers | Applied | `redaction.batches.readers` (body; `uncertain`; Decision 3 narrowed by the plan; q-002) | |
| M2 disable during redaction | Applied | `ledger.lifecycle` (bullets), new Q `ledger.lifecycle.disable-during-redaction` | A Q child rather than tagging the whole lifecycle block `uncertain`. Observed in `redaction_interrupt_resume`. |
| M3 absolute promise | Applied | `redaction.purpose` (exceptions bullets), page intro | |
| M4 per-500 commits | Applied | `erasure.atomic` (body bullet, Metadata, bug-led-011) | Code reading only. The register entry already exists. |
| M5 engine connection | Applied | `structure.write` (bullet lists the calls), new Q `structure.write.engine-connection`, `search.bm25.write_lock` (bullet), `erasure.atomic.caller-transaction` (Metadata pointer) | |
| M6 BulkLoader rebuild | Applied | `install.bulk_load` (body defers to `structure.adjacency.bulk`; `load_nodes`/`load_edges`), `install.bulk_load.rebuild`, Metadata divergence | `structure.adjacency.bulk` already listed the bulk loader and the caller-transaction rule, so it was left as the owner. |
| M7 `erasure.kept` | Applied | `erasure.kept` | It also clears the multigraph mode and resets the FHIR watermarks, and the two open questions are linked |
| M8 graph-less indexes | Applied | `search.erasure.indexes` (body), new Q `.graphless`, `search.scope.indexes` (IVF records no graph) | |
| M9 adjacency-only delete | Applied | `erasure.entry-points.single-path` | |
| M10 legacy names | Applied | new D `graph.names.report` (human-verified, ADR-0003 Accepted); `graph.names.legacy` narrowed to the upgrade question | |
| M11 routing guards | Applied | `algorithms.routing` | Namespace guard, multigraph refusal (`ArnoAccel.cls:262`) and edgeless node were verified |
| M12 other model | Applied | `search.embedding.other_model` (bullet; `uncertain`) | |
| M13 strict bypasses | Applied | `access.ledger_strict.bypasses`, `.undecided` | |
| M14 retries | Applied | `access.retries` changed from D to Q, tagged `uncertain` | It keeps its bug-plt-019 link. No open-question register entry exists (see the report). |
| M15 Cypher writes and the ledger | Applied | `query.writes.ledger` ("Today"; `uncertain`; CONTEXT.md and F10 cited) | |
| M16 provenance | Applied | Six spec-253 blocks (`query.paths`, `query.native`, `.privileges`, `.reads-only`, `.equal-answers`, `.sql-first`) and `install.schema.concurrency` changed to `agent`. Under-claim: `temporal.latest.exact` changed to `human-verified` (spec 255 Decision 1). | `temporal.structural.upgrade` was left `agent`: its bounded-memory bullet is the implementation's, not ADR-0015's. |
| M17 non-indexed mirror; explicit delete | Applied | `temporal.structural` (bullet; Metadata), new Q `temporal.structural.explicit-delete` | |
| M18 overlapping writers | Applied | `temporal.write.concurrency`, `temporal.latest.exact` | |
| M19 direct write | Applied | `temporal.write` (bullet) | |
| M20 undeclared index | Applied | `structure.adjacency.undeclared`, `query.writes.adjacency` | No `EdgeScan` call in the Cypher or store write paths (code reading) |
| M21 Q provisional answers | Applied | All 24 listed Qs plus the 9 new or changed ones; `structure.rebuilt.rollback` and `structure.multigraph.ledger` gained "Today …, observed"; `ledger.strict.fail-open` changed to "Provisional answer: none; today the check allows the write" | Long Q statements were split into bullets to stay within the writing rules |
| M22 register links | Applied (ontology side) | Metadata links q-001…q-005, q-007…q-010; `fhir.sql_mapping.graph_scope` → q-plt-018; `search.fusion.text_leg` → q-srch-006; `redaction.idempotency.other-tenant` → q-001; `erasure.prefix-match` tagged `uncertain` with a separator bullet | The "Open statement:" lines in the register entries are register-side (see the report) |
| M23 coverage | Applied | New D `install.import`; root "Not covered" section declares the non-Cypher read API and the exports as gaps | "Running the import again resumes it" was not written: re-running an import was not checked |
| M24 install losses | Partly applied | `install.schema.name` (package clash), `install.upgrade.grants` (views), `install.snapshot.scope` (layout refusal), new `install.schema.speed` (human-provided clarification) | Not applied: "its IVG version is never checked" for archives. It was not verified. |
| M25 pre-4.0.0 BM25 index | Applied (partly verified) | `search.scope.indexes` | The `BM25Index.cls:607-611` comment was verified. The fusion's choice of it rests on the helper's reading, which the Metadata notes. |
| L1 stale notes | Applied | `redaction.audit`, `redaction.after-erasure.default-graph`, `redaction.unattributed`, `redaction.target.nodes`, `temporal.structural.ledger-nodes` (including the V4 op-order condition), `temporal.ledger.atomic`, `structure.rebuilt.rollback`, `structure.multigraph.ledger` | `redaction.batches.competing`, `erasure.concurrency` and `erasure.atomic.caller-transaction` had already been corrected by R3-1 |
| L2 link labels | Applied | redaction, erasure, install | Every register link label is now the entry title |
| L3 digest | Applied | `redaction.tombstone.digest` ("For now"; q-005) | |
| L4 shared IDs | Applied | `ledger.lifecycle.genesis.shared-ids` (CONTEXT.md decision cited) | |
| L5 SC-003 | Applied | `redaction.batches` (bullet), new agent child `redaction.batches.speed` with its condition | |
| L6 paging | Applied | `temporal.window.paging` (FR-009 wording) | |
| L7 control characters | Applied | `graph.names` (NUL stripped first; codes 1–31, 127–159) | |
| L8 health and labels | Applied | `access.health` (body; 4.6.3), `install.legacy.ownership` Sources label changed to v4.6.3 | |
| L9 useful links | Partly applied | Root links the coverage map and the findings register | Not applied: per-block links to coverage rows, which is a large mechanical pass. The coverage map links each block instead. |
| L10 direct temporal writes | Applied | `ledger.strict` (bullet), `temporal.structural.ledger` | |
| L11 wording losses | Applied | `query.compiled.fallback`, `search.bm25.upgrade`, `search.quarantine.placement`, `search.fusion.failed_leg` (Metadata), `temporal.delete`, `temporal.structural.adopt`, `structure.multigraph.off` (Metadata justification), `redaction.batches.commits`, `redaction.call`, `redaction.verify`, `install.legacy` | Each was spot-checked in code. The placement refusal on an existing vector is inferred from the INSERT-then-DELETE order. |
| R3-1 residual | Already applied | — | The resume claims, Final's re-check, competing targets and both erasure transports were all current |
| R3-8 token metadata | Applied | `structure.rebuilt.token` Metadata | It now matches the corrected bug-str-016: weight-independent cache, `^ArnoKG` readers not traced, suspected, non-indexed installs only |

Totals: 38 Applied, 3 Partly applied (M24, M25, L9), 0 Not applied. R3-1 needed no change.
