# Routed snapshot restoration through readers

As-built transcription at product3eaa79cf, pinned Verus0.2026.10.04.426d8b0,
bundled vstd only, no assume/admit/external_body. Fourteen obligations and ten
decisive controls. The product's Python/ObjectScript bodies remain unverified.

## Contract and boundary

`export` derives archived table identity and width from the source registry;
`install_registry` restores that identity. `prepare` selects archived width or the
restored-registry fallback, creates a missing physical declaration, retains an
existing declaration, and records the destination helper's index result only if
the registry write succeeds. `restore_one` skips insertion after an invalid width
and counts its one decoded archived row once. `load` enforces physical width and
parent presence for attempted inserts. An existing merge row is skipped BEFORE
those checks and still reports one restored row. `read` distinguishes no route,
no vector, a value and a registry pointing at a missing physical table.
`query_admitted` models the literal query's registered-width guard; it supplies no
general cosine, sorting or ANN result proof.

The source and destination in theorem_export_registry_restore_readback are
different states. Source registry width and actual source vector contents feed
the restored reader; the engine default is arbitrary. The destination must have
its parent node and no preexisting target table/row. Those premises hold in the
fresh replacing native case. `restore_parent` also represents the generic nodes
merge guard's actual first-column key: another graph's same node ID suppresses
the wanted parent. The resulting vector FK refusal and absent reader strengthen
the known bug-plt-004/F-1802 root, not a new bug. The original complete-archive
prediction and DISAGREES receipt164253 remain preserved. The corrected as-built
prediction does not settle or weaken the intended composite-key merge rule.

Domain: decoded node-route metadata, valid routed table identities abstracted as
distinct integers, unique registry route/table correspondence, current exported
node column order, a decoded nonempty vector and one archived row per load step.
Width::Falsy represents Python-falsey metadata (including numeric0); Present(0)
can represent truthy text"0"; Invalid represents caught TypeError/ValueError.
JSON parsing, integer conversion/uncaught overflow, malformed rows, invalid dtype,
duplicate/ambiguous registry rows and name validation are unproved boundaries.
No full archive loop/transaction/global composition is asserted. Other record
counts require composition of these steps; invalid-width prepare is not followed
by load. Successful SQL/DDL/commit and faithful FK/width enforcement are named
provider premises for positive theorems. Create-table exceptions and arbitrary
post-CREATE commit failures remain outside their guarantee.

Index `build` is the result of `_attempt_route_index`, NOT an independently proved
physical index state. The formal model proves helper-result recording and its
failed-record limitation. Native catalog observations confirm physical equality
in the successful fresh-table cases and injected-before-CREATE refusals only.
A failure after CREATE but during commit may leave an index despite a refused
helper result; general physical equality remains open. Local route-cache clearing
is observed; another process's cache/TTL and competing writers are not proved.

## Product roles

| Role | Production member | Formal declaration | Qualified evidence |
|---|---|---|---|
| archive producer | snapshot.py::routed_export_plan | export | actual saver metadata; valid unique node routes |
| archive writer | snapshot.py::SnapshotMixin.save_snapshot | export | actual ZIP registry, node/vector rows |
| deciding restore/writer | snapshot.py::SnapshotMixin.restore_snapshot | restore_one / restore_parent | actual registry/metadata/fallback, rows, counts and merge cases |
| declaration producer | schema.py::SchemaMixin.routed_table_ddl | prepare | actual VECTOR8/16 DDL and catalog |
| declaration writer | schema.py::SchemaMixin._create_routed_table | prepare | actual fresh/compatible/incompatible existing tables |
| index producer | schema.py::SchemaMixin._attempt_route_index | prepare | native success; injected-before-CREATE refusal; physical post-commit ambiguity open |
| registry writer | schema.py::SchemaMixin._record_route_index_state | prepare | actual UPDATE and injected refused UPDATE; stale claim retained |
| route reader | embeddings.py::EmbeddingsMixin._read_route | read | actual registry and cached route decoding |
| selecting reader | embeddings.py::EmbeddingsMixin._route_for_read | read | actual named graph/model miss versus route |
| final reader | embeddings.py::EmbeddingsMixin.get_embedding | read | actual persisted vector/value/error/absent outcomes |
| width guard | vector.py::VectorMixin._assert_query_width | query_admitted | actual literal query8/16 and wrong-width refusal |
| query consumer | vector.py::VectorMixin.kg_KNN_VEC | query_admitted | width/route only; native one-row result tested, numerics not proved |

Paths start `iris_vector_graph/_engine/`. Role links are specific behaviors, not
claims about entire members. Registry-row import is inside restore_snapshot and
is necessary even when a table full of vectors was recreated.

## Replay and retained misses

Use run_verus.py prove/controls on this directory. For binding, first provision
only the task's disposable hostname-checked runtime using iteration-5/native-setup.py,
then set IVG_SNAPSHOT_NATIVE=1, IVG_PIN_DIR to the exported pin and RUN_DIR to
/Users/ziniuw/runs/ivg-iteration5-snapshot-20261115 and run binding.py with the pinned
venv's Python -B -I. The container is ivg-uplift-next-20261115, port35975,
Community2026.1.0.234.1, image546fe52b9e68…, arm64, namespaceUSER. Existing sibling
containers are never touched. Initial password-change/setup refusal is preserved
in native-setup-initial.log; successful setup deployed66 classes and skipped3 MCP
classes needing unavailable %AI modules. Exact identity and full image digest are
in native-setup.json and native receipts.

Eleven final worlds agree: normal8/16, registry-width fallback, missing registry,
invalid width/missing table error, wrong archived width, existing incompatible
empty table, existing merge row, cross-graph parent collision, incompatible
existing merge row, plus two explicit index-provider fault injections. The first
nine use real IRIS SQL/DDL, ZIP save/restore and final reads; the last two run real
helpers with injected refusals. Catalog HNSW indexes are retained. Normal and
fallback worlds also perform actual one-row KNN searches, wrong-width refusals
and a new width16 write on an engine configured8. Creator-forces-default-width
and changed-final-vector controls are detected. No arbitrary cosine/ANN precision
or concurrent behavior is inferred. Before changing a world prediction, the
initial failed observation/oracle is retained and matched to its source cause.

The extra snapshot-merge-probe records the independently requested interaction:
an existing width8 row versus incoming width16 is a successful merge skip with
reported1/failed0, not a width refusal. That review changed load's ordering and
added its own generic theorem. The initial parent-complete premise was challenged
through actual generic node import, rather than trusted from the vector caller.

Independent reviewer reproduced proof/control packages on scratch copies and
inspected native receipts; no live runtime was shared concurrently. Builder and
review costs, inherited evidence and the next queue are in the iteration handoff.
