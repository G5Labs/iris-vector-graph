# G07-structure-snapshots-access fork report (saved verbatim by the integrator)

I regraded all 165 rows of G07 (structure, snapshots and bulk load, access). `rows.tsv` has one row per id in `ids.txt`, and `overlay.py` exits 0. No repository file was edited, nothing was committed, and there was no STOP file.

## 1. Counts
- Full rows (77): 53 held, 24 full→partial, 0 full→absent.
- Absent rows (88): 74 held absent, 14 absent→partial, 0 absent→full.
- check_scope: 8 rows went full→narrowed. Held full: bypasses#o02, #o03, engine_cache#o01, structure.node.bulk#o07, #o08, structure.edge.delete#o03. Downgraded rows: bypasses#o04, #o05.
- Statements fixed: 0.
- Overlay summary: `rows reviewed: 165; problems naming them: 0; errors: 0`; absent->absent 74, absent->partial 14, full->full 53, full->partial 24, scope full->narrowed 8, scope n/a->narrowed 10.

Held full rows had their gaps cleared: premise and as-built text moved into `premises`. Two gaps became `outside-statement:` (structure.write#o03 and structure.multigraph.count#o07). structure.node.read#o06 carries a `requires-reviewed:` note.

## 2. Changed rows

Full → partial

| id | letters | reason |
|---|---|---|
| access.iris_boundary#o03 | b | Only the backfill's two-table INSERT order is proved. |
| access.read_only#o08 | b,d | Only the HTTP tx/commit batch is modelled; Bolt transactions are not, and the per-statement write verdict is an input. |
| access.ledger_strict.bypasses#o04 | b,g | The GraphQL Cypher field is folded into one ApiSample path with the REST route; not probed. Stays refuted, narrowed. |
| access.ledger_strict.bypasses#o05 | b,c,g | updateProtein's property writes are folded into the ApiSample node-write path. Stays refuted, narrowed. |
| structure.write#o10 | a | Holds only by `step`'s definition; no proof fn. |
| structure.write#o11 | b,c | Reifier nodes are not modelled; the cleanup failure is a single point check. |
| structure.node.update#o01 | a | The new row and the True return are definitional. |
| structure.node.update#o02 | a,b | "Others stay" holds only by `apply_props`' definition. |
| structure.node.update#o03 | b | Adding a new given label is not proved (subset only). |
| structure.node.update#o04 | b | A node that already has an id keeps it only by definition. |
| structure.node.update#o06 | a,c | The model has no raise branch; True is a constant. |
| structure.node.read#o02 | b | Only `result([id,id])` is proved; order across different IDs is not. |
| structure.node.delete.bulk#o01 | b | '1' vs 1 text conversion is not represented; single point check. |
| structure.node.delete.bulk#o02 | b | The log record is not modelled. |
| structure.edge#o02 | a,d,e | Refusal returns the prior state by definition, under an assumed rollback. |
| structure.edge.weight#o01 | b | The ledger qualifier update writer (bug-str-012) is not a modelled op. |
| structure.edge.delete#o01 | b,d | One DelRow per row is a caller-supplied history, not derived. |
| install.snapshot.scope#o06 | c | Only the temporal globals are modelled, not the SQL tables. |
| install.snapshot.temporal#o04 | b | The suppressed-reverse absence (the obligation itself) is not proved. |
| install.snapshot.info#o02 | a,e | `restore` is a one-line definitional copy of rows. |
| install.bulk_load.loader#o03 | b | `load_edges` is not modelled. |
| install.bulk_load.loader#o05 | b | The refusal is one generic `$TLEVEL` predicate; per-batch commits over several batches are not modelled. |
| install.bulk_load.loader#o06 | d | The schema mismatch is two boolean inputs. |
| install.bulk_load.loader#o07 | d | The schema mismatch is two boolean inputs. |

Absent → partial. Eleven upgrades come from `proofs-d1f` `auth_l1`/`auth_l2`. That crate has only a baseline receipt, so none of these can go above partial:
- access.graph_id#o01: `theorem_graph_is_not_authorization`.
- access.api_key#o01 and #o02: `http_decide` / `bolt_decide` (definition only).
- access.api_key.every_route#o01, #o02, #o04: `theorem_no_route_code_without_the_key`; the public-path bit is an input.
- access.api_key.every_route#o06: `theorem_read_only_after_the_key_gate`.
- access.api_key.bolt#o01: `bolt_decide`.
- access.api_key.bolt#o02: `theorem_raw_executions_refine` plus the no-key theorem.
- access.read_only#o02 and #o03: `theorem_read_only_after_the_key_gate`; write-ness is an input.

Three come from current models:
- structure.node.read.properties#o04: `node_read::write`. The model stops before the reader.
- structure.node.read.properties#o05: `node_read::theorem_boolean_precedes_integer`. Only the `get_node` half is covered.
- structure.multigraph.count#o06: `traversal_strategy::theorem_vl_parallel_edges_return`. Covers var-length trails only.

## 3. Owner contradictions, duplicates and housekeeping

Five gaps tagged `owner-contradicted:` (iteration-63 §6.1, checked against the cited evidence): structure.node#o02 (`nodes_edges.py:1097-1104` returns False, not an error); structure.reification#o03 (`_engine/schema.py:3318-3324`); structure.reification#o06 (`_engine/schema.py:3340-3345`); install.bulk_load.rebuild#o02 (`bulk_loader.py:586-598` raises RuntimeError); install.snapshot.derived#o02 (`snapshot.py:1555-1585`, bump only under `if global_files:`).

No new contradictions, duplicates or missing obligations found.

Housekeeping, report only:
- structure.node.update, structure.node.read and structure.node.delete.bulk carry `design-verified` tags or Verus lines that now overstate the coverage.
- `bulk_delete` assumes an atomic primary delete, which conflicts with bug-led-011's per-chunk commit. So it cannot represent structure.node.delete.bulk#o06.
- platform's `log` marks every committed structural write as unrecorded, so it cannot distinguish BulkLoader for install.bulk_load.ledger#o01.

## 4. Rows for the reviewer to target
- access.ledger_strict.bypasses#o04, #o05: downgraded because the GraphQL field and updateProtein are folded into one ApiSample path. They could arguably stay full refuted.
- structure.node.update#o01, #o06 and structure.edge#o02: strict calls where the outcome is literally the model's definition.
- structure.node.delete.bulk#o02: I counted the unmodelled "logged" outcome as a missing case; this is a judgement call.
- structure.edge.weight#o03: held full because the cost reader composes with `effective()`. It could be argued down to partial as definitional.
- The 14 absent→partial upgrades: especially the definition-only ones (access.api_key#o01, #o02, bolt#o01, structure.node.read.properties#o04).
- install.snapshot.scope#o06: downgraded because the refusal is shown only on the temporal store.

Files: `rows.tsv`; `build.py`, which replays every decision from `before/`; `work/`, the overlay copy.

## Recheck after the show.py stub fix (42 ids)
Five statements drifted and are fixed; no grade changed: install.snapshot#o04 (absent; imported "reads tables and globals one at a time" removed, restates the quiet-writers working assumption); install.snapshot.scope#o03 (full refuted narrowed; first-column guard detail belongs to install.snapshot.routes#o12; the witness still refutes the fixed statement); install.snapshot.failure#o01 (absent; exception name removed); install.snapshot.failure#o02 (absent; RuntimeError removed, "not atomic as a whole" kept); install.snapshot.derived#o01 (absent; restated as "a restore never brings back derived caches from the archive"). The other 37 ids match. Overlay exit 0.
