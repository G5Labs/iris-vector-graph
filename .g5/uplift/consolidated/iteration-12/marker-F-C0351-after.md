<a id="F-C0351"></a>
### Explicit edge writers store the temporal marker {"temporal": true} given as a caller qualifier: the row is a marked row with no timestamp, and verify() does not see the relationship

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-ba-marker-qualifier`; inspected `iris_vector_graph/ledger/replay.py:613-620`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-ba-marker-qualifier`

- Expected: docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md:38-42 (the marker distinguishes a temporal edge's derived row; a row an explicit write asserted is unmarked) and ADR-0009/TMP-B9.13 marked-needs-time (a marked row exists only while its triple has a timestamp); experiment/playbook-uplift/ontology/14-replay.md:51 (RPL-B7.1: verify names a change made outside the ledger an unrecorded write).
- Observed at the pin: Live in AUDITB (ws-live-ba-marker-qualifier), no temporal edge in the namespace: engine.store_edge, engine.create_edge and BulkLoader.load_edges (use_noindex False), each given qualifiers {'temporal': True}, wrote rows stored {"temporal": true}; their triples have no timestamp. verify() then reported diverges on the six endpoint nodes only: the three relationships are not among its differences, because read_canonical skips rows whose temporal qualifier is JSON true (iris_vector_graph/ledger/replay.py:617-620).
- Source severity S3, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Reserve the marker key: refuse (or strip) a caller qualifier named 'temporal' in every explicit writer, as the ledger reserves 'id' and '__graph', so the marker can only come from the temporal side.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 4 strengthening, not a new discovery: independent review of edge_acceptance found the caller marker input missing from its first transcription. The extended run/theorem_caller_marker_retained and 56 actual Python/SQLite cases now include temporal=True on insertion and repeated adoption: True/True, one row, final caller value and marker retained. The prior live verify omission remains inherited, not rerun. temporal.structural.adopt preserves ADR-0009's intended unmarked explicit edge and names this observed exception. No reserve/strip repair is implemented; the SQL/provider boundary remains conditional.

Iteration12 new reachable consequence of the same caller-controlled-marker root, not a new issue: ordinary `Changeset.create_relationship` with qualifier `temporal: "true"` stores that string without a temporal writer. A second ordinary create of the same tuple enters `LedgerApply.OpCreateRel`'s adoption branch, rewrites the one physical row and allocates a fresh statement without deleting the old one. Named reconstruction and NDJSON export then retain both complete statement maps, while tuple lookup selects the new ID. The `temporal: "false"` neighbor refuses `relationship_exists` without a revision. [Six native checks](../uplift/consolidated/iteration-12/root-ledger-marker-native.json) and [independent raw-record/content audit](../uplift/consolidated/iteration-12/review-ledger-marker-audit.json) retain all ten emitted records from four captured revisions. The native panel directly uses text true/false; public boolean-to-string normalization is source-inspected, not an extra native case. Existing [F-0505](#F-0505) and [F-C0450](#F-C0450) cover related inconsistent marker predicates. The complete ordinary producer proof is restricted to its declared no-marker/default profile; this valid API input remains a qualified boundary, never an invented refusal. No repair, severity change or policy decision is made.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

