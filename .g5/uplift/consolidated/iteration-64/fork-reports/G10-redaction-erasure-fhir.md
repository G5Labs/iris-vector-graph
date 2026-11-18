# G10-redaction-erasure-fhir fork report (saved verbatim by the integrator)

Regraded G10 (redaction, erasure and fhir pages: 72 full and 118 absent rows) against the brief's checklist. The overlay exits 0: 190 rows reviewed, 0 problems naming them, 0 errors. I edited no repository file.

Output is `scratch/iteration-64/forks/G10-redaction-erasure-fhir/rows.tsv`. It has one row per id with a `reason`, and changed rows carry `iteration=64` and an `it64 regrade:` suffix. The deterministic generator is `gen.py` in the same directory.

**1. Counts**
- Full rows (72): 47 held full, 25 full→partial, 0 full→absent.
- Absent rows (118): 112 held absent, 4 absent→partial, 2 absent→full.
- check_scope: 14 rows moved from full to narrowed (11 still full, 3 now partial).
- Statements fixed: 0. I found no drift from the current block text.
- Other edits: 16 more rows keep their grade and scope but changed in other columns: a `requires-reviewed:` note in `premises`; gap text that was really evidence (a control name) moved to `premises`; a gap retagged as `outside-statement:`; added locators; one design check raised from none to proved (target.nodes#o02).
- Overlay summary: absent→absent 112, absent→full 2, absent→partial 4, full→full 47, full→partial 25, scope full→narrowed 14, scope n/a→narrowed 6.

**2. Changed grades and scopes** (letters are the failed checklist items)

| id | old → new | letters and reason |
|---|---|---|
| erasure.scope#o01 | full/none → partial | a: only the erased()/erased_in definition; no theorem |
| erasure.history#o01 | full/none → partial | a: the frame on records is only the step definition |
| erasure.prefix-match#o01 | full/none → partial | a: definition only |
| erasure.prefix-match#o02 | full → partial | a b: erase half is definitional; redaction half is one concrete lemma |
| erasure.prefix-match#o03 | full → partial | b: witnesses show only the event without node rows surviving. Added d1c `counterexample_fc1203` and its control receipt, which also lacks the with-node-row contrast |
| erasure.prefix-match#o04 | full → partial | b: one instance; the explicit-id erase is not modelled |
| redaction.purpose#o02 | full scope → narrowed | e: `theorem_step_frame` needs `inv` under serialised redactions |
| redaction.target#o01 | full/none → partial | a: matches definition and its twin only |
| redaction.target.nodes#o01 | full → partial | b: temporal-edge records have no entity, so the lemma excludes them |
| redaction.target.nodes#o02 | full none → full proved narrowed | proof found: `lemma_keep_iff_entity_not_target` + `lemma_frame_and_tombstone` |
| redaction.target.relationships#o01 | full → partial | a e: the iff is the matches definition; the `tuple_parses` premise removes the unknown case |
| redaction.target.relationships#o02 | full → partial | b d: knowledge is the constant input `K()`; resume across calls is not proved |
| redaction.call#o14, #o15 | full/none → partial | a: None-step convention or step definition |
| redaction.after-erasure#o02 | full/none → partial | a: None-step convention |
| redaction.after-erasure.default-graph#o01, #o03 | full/none → partial | a: checked definition only |
| redaction.after-erasure.default-graph#o02 | refuted, scope full → narrowed | single witness (W3) |
| redaction.refusals#o01, #o02 | full/none → partial | a: Start guard definition only |
| redaction.tombstone#o04 | full → partial, narrowed | a: being content-free is the `Rec::Tomb` type definition; no proof concludes it |
| redaction.metadata.exception#o04 | full/none → partial | a: the `redacted_rev` clause is only in `update_allowed` |
| redaction.idempotency#o03, #o04 | scope full → narrowed | e: `theorem_redacted_key_refused` requires `inv` (serialised) |
| redaction.batches#o02 | full → partial | b: the invariant covers started runs only; the window before the first tombstone is not distinguished (bug-led-006) |
| redaction.batches.commits#o01, #o02 | scope full → narrowed | e: the bridge lemma assumes the lock held, no expected_head and n ≤ max_ops |
| redaction.batches.commits#o03 | full/none → partial | a: definition only |
| redaction.batches.competing#o01 | refuted, scope full → narrowed | single witness (W1) |
| fhir.graph.lifecycle.tasks#o01 | scope full → narrowed | e: `allocation_frame` is a provider premise; added `theorem_existing_foreign_stutters` for the refusal case |
| fhir.graph.lifecycle.tasks#o08 | scope full → narrowed | e: point check at 0/59/60; added `theorem_effective_interval` |
| fhir.sql_mapping#o01, #o04 | full → partial | a c d: the `label_source` input bit stands in for Cypher rows; translation is not modelled |
| fhir.sql_mapping#o07 | full → partial, narrowed | a c d: point check on boolean inputs |
| fhir.sql_mapping#o08 | scope full → narrowed | point check |
| fhir.sql_mapping.relationships#o03 | scope full → narrowed | the requires pick one contrasting pair |
| fhir.sql_mapping.relationships#o04 | full → partial, narrowed | a d: the SQL error is stipulated by the outcome table |
| erasure.live-statements#o01 | absent → full refuted narrowed | g: d1c `cx_f0303.rs::counterexample_f0303`, control `control_f0303_direct_delete_keeps_stmt`. `delete_edge` leaves the live statement and tuple entry |
| erasure.entry-points.single-path#o01 | absent → full refuted narrowed | g: the same d1c counterexample, a path outside the Eraser that removes one store but not the statement store. Gap tagged `owner-contradicted:` |
| erasure.live-statements#o02 | absent → partial proved narrowed | d9b `theorem_erasure_clears_statement_history` (baseline receipt only) |
| erasure.atomic#o04 | absent → partial proved narrowed | d9b `witness_erasure_rollback` (baseline receipt only) |
| redaction.batches#o04 | absent → partial proved narrowed | d9b `theorem_final_clears_statement_history` (baseline receipt only) |
| erasure.scope#o08 | absent → partial, no design check | d1e `gid_l2.rs::step2` guards with `valid(g)`; definitional only |

The other held rows only gained notes or retagged gaps. Every row's `reason` column has its justification.

**3. Owner contradictions, duplicates and housekeeping**
- Owner contradiction: erasure.entry-points.single-path#o01. `delete_edge` runs its own `DELETE FROM rdf_edges` (`_engine/nodes_edges.py:1426-1440`); this is §6.1 item 19.
- Possible contradiction, not tagged: redaction.batches#o02. As built, the marker is set at the first tombstone, so "while a run is unfinished" fails before then (bug-led-006). This may be a product defect rather than wrong owner text.
- Duplicates or missing obligations: none found.
- Housekeeping (report only): `ledger_redaction/NOTES.md` names prove receipt `20261114T044401Z`; the latest is `20261116T160746Z`. The crosswalk row `remove_table_mapping → theorem_writer_reads_current` does not decide fhir.sql_mapping#o05 (already in §6.3). `sql_mapping` is a shallow decision table and can carry little beyond partial.

**4. Rows I was unsure about** (good targets for the reviewer)
- One-instance as-built claims: erasure.prefix-match#o03 and #o04 went to partial for a missing contrast. redaction.after-erasure#o05 has the same one-witness pattern but I held it full, because both of its cases are witnessed.
- Held full on thin evidence: redaction.call#o05 (the Start comparison itself is definitional); redaction.metadata#o01 (the `cleared` set stands in for the four emptied fields); fhir.graph.lifecycle.tasks#o03 (proved only for fixed list shapes); fhir.sql_mapping#o08 and fhir.sql_mapping.relationships#o03 (tiny transcriptions).
- Upgrades: the two d1c refutations follow the reviewed-design control convention; the d1c control receipt passes the census receipt check. The three d9b partial upgrades rest on a crate described as "about the model" with a baseline receipt only. erasure.scope#o08: `valid(g)` is assumed to equal "cannot be stored safely".
