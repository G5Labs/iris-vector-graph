# Temporal snapshot to actual window readers

Product3eaa79cf, input seal47236c82. As-built transcription; no assume/admit/
external_body, no executable product-body proof. Pinned Verus/vstd unchanged.
**31 verified units =15 new units (13 named proofs,2 termination checks) plus16
unchanged paging units rechecked as an imported dependency.** Seven controls fail
their named claims. Do not count the imported16 as new theorems or new coverage.

## Producer, format and observation

`insert` derives outgoing weight, optional reverse-index weight and attributes
from a fresh event; an existing outgoing event makes an insert collision stutter.
Global keys retain graph, timestamp, source, predicate and target. The critical
snapshot subtrees are outgoing, inbound and attributes. `export_temporal` derives
its keys from the source finite map's domain and the actual critical-store plan;
it does not take the desired query key as an input. Under the Native API's complete
leaf-enumeration contract, any enumeration order works. The recursive Python
nextSubscript walk itself is inspected and sampled, not executable-body verified.
The zero-start control loses default graph0/epoch0; the actual empty-string start
preserves them. Other subtrees/aggregation/whole-archive composition are not proved.

`Scalar::Number(n)` denotes supported integer numeric values. NumericText(n)
denotes their canonical text; Text(atom) denotes the other sampled plain text.
The scalar export applies str(value), so Number becomes NumericText. Import sets
that text. The weight reader coerces numeric text to a JSON number; the attribute
reader preserves its stored string type. This distinguishes two real histories
that display the same digits but require different typed results. Native initial
receipt170720 DISAGREES and its original type-preserving expectation are retained.
The final model records the as-built conversion and refutes intended type
preservation, matching inherited F-1804 rather than inventing a new bug.

`apply`/`import` skip malformed or refused lines, counting only successful writes.
`restore` compares the actual optional layout text with graph-scoped and refuses
another layout before erasure, otherwise replaces or merges the
global map. Its report has no per-line failure count: a mixed good/refused import
can report successful globals while dropping an event. Native <SUBSCRIPT> refusal
and the real restore reproduce inherited F-C1802. The intended failure-reporting
obligation stays unmet; it is not weakened to permit silent data loss.

`weight` projects the actual global query's graph, inclusive time and source
filter; inbound uses its own reverse entry. `attrs` joins the stored original
coordinates. The imported paging module supplies window_spec/server_admits and
retains its separately proved cursor lifecycle. **There is no new theorem
constructing the full ordered page sequence from restored global keys.** Native
one-call/paged comparisons establish that stronger connection only for this
fixture. Arbitrary ordering/collation, predicate-tail selection, full paging
composition, huge responses and concurrent changes remain separate obligations.

## Domain and trust

The positive complete-source/writer-to-window theorems assume a compatible layout,
successful outer restore/housekeeping, legal nonempty native-address components,
faithful global get/set and complete finite key enumeration. Named graph integers
abstract distinct canonical graph keys; default is0. The corpus uses nonempty
plain text IDs, integer weights and int/plain-text attrs. General JSON/Unicode/
Decimal/nonfinite payloads, native numeric formatting and arbitrary graph-name
normalization are not proved here. Weight conversion and attribute type are
distinct; no all-value codec identity is assumed. Missing/refused lines are modeled
as failed writes, not silently included in positive premises.

Rejected writes in this slice mean malformed input or a refusal before writing,
such as the reproduced bad-subscript error. Lost acknowledgements and errors
after an effect are not established. Raw omitted/None/bulk timestamp resolution
is a separate uncovered producer (bug-tmp-007/F-0502); this slice starts with the
explicit integer timestamp, not a claim that all write APIs choose the same time.

Old per-key lemmas retain explicit key/store membership premises. The final
export_temporal and actual_writer_restore_window theorems derive those premises
from the source map and fixed critical stores. Fidelity of that finite enumeration
abstraction to the recursive platform walk is a named provider/code boundary,
challenged by actual zero/default/epoch cases and the altered exporter.

## Implementation roles

| Role | Product member | Formal target | Qualified evidence |
|---|---|---|---|
| event writer | TemporalIndex.cls::WriteStores | insert | actual direct temporal producer, weight/attrs/reverse; fresh insert domain |
| public producer | temporal.py::TemporalMixin.create_edge_temporal | insert | actual pinned caller/store path; explicit integer timestamp |
| port argument producer | iris_sql_store.py::IRISGraphStore.write_temporal_edge | insert | actual explicit timestamp/weight/attrs Native API call; raw clock selection excluded |
| store-plan producer | snapshot.py::kg_export_subscripts | export_temporal | actual fixed critical subtrees selected from STORE_PLAN |
| archive writer | snapshot.py::SnapshotMixin._export_global_to_ndjson | export / encode_scalar | actual key walk, graph0/time0 and scalar conversion; enumeration premise explicit |
| archive caller | snapshot.py::SnapshotMixin.save_snapshot | export_temporal | actual ZIP/global plan dispatch |
| import writer | snapshot.py::SnapshotMixin._import_global_from_ndjson | apply / import | actual scalar set and caught Native API refusal |
| restore caller | snapshot.py::SnapshotMixin.restore_snapshot | restore | actual layout-before-erase and mixed good/refused import |
| query producer | TemporalIndex.cls::QueryWindow | weight | actual one-call outgoing query; source/time/graph projection |
| reverse query producer | TemporalIndex.cls::QueryWindowInbound | weight | actual reverse entry and original source/target projection |
| port query consumer | iris_sql_store.py::IRISGraphStore.execute_temporal_window_query | weight | actual method/direction/JSON-to-column projection and error propagation |
| row producer | TemporalWindow.cls::Row | attrs / weight_value | actual numeric-vs-string attrs and weight JSON rendering |
| final one-call reader | temporal.py::TemporalMixin.get_edges_in_window | weight | actual store/result-key aliases, finite fixture |
| paged caller | temporal.py::TemporalMixin.iter_edges_in_window | weight | source/filter projection plus native page traversal only |
| final event mapper | temporal_window.py::event | attrs | actual field/attrs aliases; no complete serializer theorem |

Engine modules are under iris_vector_graph/_engine; iris_sql_store is under
iris_vector_graph/stores, and class paths start iris_src/src/Graph/KG.
Bind only these specific behaviors. Native host/provider,
raw JSON parser and whole archive/SQL/ledger effects are not body proofs.

## Replay, losses and proposed simplification

Use run_verus.py prove/controls on this directory. model.json additional_inputs
stamps the imported paging source; changing it invalidates this proof and binding.
Runner control copies keep each import under its unique preserved control snapshot.
The runner delta changes metadata/dependency materialization, not verifier flags,
tool binaries or existing models' input sets. See iteration6 input-parity and
dependency-staleness evidence. Initial type/count/proof and FAIL_ELSEWHERE control
attempts remain; value loss fails the actual inductive lemma, while the zero-key
theorem now independently unfolds its concrete case. No unrelated failure counts.

Native binding requires IVG_TEMPORAL_NATIVE=1 and the same isolated checked runtime
as iteration5. RUN_DIR=/Users/ziniuw/runs/ivg-iteration6-temporal-20261115, pinned
venv Python -B -I, IVG_PIN_DIR set to the exported pin. Seven worlds/check groups
cover normal writer/read, erase, restore, wrong layout, zero-start exporter,
refused line and proposed raw-value variant. Each graph/direction also runs one-call
and page-size1 readers, attrs and empty sources. Both changed-output and exporter
controls execute real acceptance predicates; a literal edited-value inequality
was withdrawn as meaningful control credit. Native line refusal is explicitly
required by its oracle. Image/identity/setup remain iteration5's pinned runtime.

A method-copy proposal merely removing str(value) was tested and **retired as
insufficient**: actual native Decimal values under KG out cannot be serialized by
the standard JSON encoder, so save correctly raises SnapshotReadError and writes
no archive. No repair was implemented. The existing type-aware format/server
codec proposal still needs design and compatibility work; older text-only archives
cannot recover whether digit text was originally a number. The failed candidate
and original typed-roundtrip failure are retained, not turned into passing claims.
