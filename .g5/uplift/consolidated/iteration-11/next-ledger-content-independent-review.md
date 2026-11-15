# Independent bounded ledger-content plan review

The frozen23-case preparation supports a useful next full-content continuation.
Its explicit distinction between semantic admitted record histories and native
writer reachability is necessary. I recommend proceeding after the next before
archive, with the premises below retained. This review creates no model, issue,
product change or policy answer. q-con-002 remains undecided; bug-led-101's richer
prior-loss witness is the existing finding. The complete simple-delete snapshot
is a passing neighbor, and the earlier simple missing-snapshot forecast stays
withdrawn.

Read frozen PAIRS/plan/probe/validation first, then actual writers and readers.
Seven small pinned Python reader checks pass with0 sockets/native calls in
[next-ledger-content-independent-probe.json](next-ledger-content-independent-probe.json).
They test candidate premises, not broad new product correctness.

## Reachable producer actions need their actual record expansion

[LedgerApply.OpCreateNode](../../../../iris_src/src/Graph/KG/LedgerApply.cls#L215)
rejects an existing create, while upsert of an existing node emits no create and
preserves existing labels/properties. A new node emits `create_node` with empty
new text, followed by separate `add_label` and `set_prop` records. AddLabel skips an
existing label; SetProp skips identical values and captures the actual previous
string. A create record cannot be defined to carry a pre-applied full node map.
The reader deliberately resets NodeState on create and does not unpack r.new.
Likewise [OpCreateRel](../../../../iris_src/src/Graph/KG/LedgerApply.cls#L450)
emits tuple-only create_rel plus separately ordered set_qual records; upsert of a
live tuple merges qualifiers without resetting the relationship. Derive these
record sequences from input operations and current maps, including no-op writes.

Normal setters require live nodes/references and nonempty keys; removal of a
missing property/label/qualifier refuses instead of emitting an idempotent remove.
GraphState's absent-entity ignore and idempotent remove are still actual reader
behaviors, but arbitrary reader iterables exhibiting them are not automatically
ordinary ApplyAll traces. Within a changeset, deletedNode/deletedStmt guards also
forbid reusing a deleted identity. Delete/recreate witnesses are reachable across
revisions, not necessarily within one ApplyAll call.

[IsReserved](../../../../iris_src/src/Graph/KG/LedgerApply.cls#L68) rejects exactly
node-property id/__graph; creation validates all reserved keys before its first
write. Genesis and canonical read omit those properties. GraphState itself accepts
such raw records. Qualifiers have a different admission rule: no node reserved-key
ban, but nonempty key and numeric weight checks. Keep the reader theorem general
enough for admitted raw records and separately characterize ordinary producer
reachability. Adoption is another real record writer: LedgerGenesis.Adopt largely
copies record-shaped prior/new fields and does not replay ordinary admission or
canonical SQL writes. A native-reach claim confined to ApplyAll must say so rather
than quietly omitting Genesis/Adopt.

## Strings/nulls/tuples are a typed boundary, not arbitrary JSON semantics

[LedgerApply.Enc/EncNull](../../../../iris_src/src/Graph/KG/LedgerApply.cls#L52),
[Ledger.RecordsFetch](../../../../iris_src/src/Graph/KG/Ledger.cls#L621), and
[MutationRecord.from_row](../../../../iris_vector_graph/ledger/replay.py#L54)
compose the N/S encoding with explicit null flags. Empty text, absent optional
value and literal text `null` remain distinguishable in a record. GraphState's
set_prop/set_qual **then maps None to empty text**. A raw set record with both
prior/new None yields an empty stored property but an empty attribute diff;
ordinary ApplyAll SetProp emits Enc(value), so that raw reader-only example must
not refute a correctly framed ordinary producer theorem.

Ledger.MetaGet maps JSON null/missing to a default. Node values use native string
coercion. ParseQuals skips JSON nulls, spells boolean true/false explicitly and
serializes nested containers as text; other create/merge paths also use native
`"" _ value`. Treat values as strings after the applicable producer conversion,
or explicitly model each conversion. Opaque string equality preserves nested
text **as text**, not recursively typed JSON values or a universal native encoding
roundtrip. `from_wire` is more permissive than from_row and does not enforce these
nominal string types; don't merge their contracts.

TupleJson gives default graph null, while replay._parse_tuple normalizes None,
empty and NUL to None and reads s/p/o from the new JSON object. For create_rel,
the tuple's graph is deciding; r.graph is not a substitute. An explicit typed
TupleJson/parser relation can settle normal objects without modeling a general
JSON parser. Invalid JSON, arrays/nonobjects or arbitrary numeric ID coercion
must remain separate reader error/carrier behavior, not silently accepted tuples.

## Tuple identity is the strongest necessary qualification

The plan correctly warns against a tuple-index bijection. Normal OpCreateRel's
FindEdge/refusal/upsert logic selects one live tuple, but that is insufficient to
establish uniqueness for all native-produced histories.
[Genesis.Capture](../../../../iris_src/src/Graph/KG/LedgerGenesis.cls#L14) scans
every non-temporal physical rdf_edges row, allocates a new statement for **each**,
and emits create_rel/set_qual. AllocStmt overwrites the tuple->ID index. Enable
calls Capture without a GraphMode or duplicate-tuple guard. Thus two physical
keyed rows for the same tuple provide a source-supported genesis route to two
statement IDs; this route has not been executed natively in this review.

Actual GraphState keeps both IDs, but `_stmt_by_tuple` retains the last. Its
as_comparable dict keyed by tuple collapses to one. Deleting the earlier ID
unconditionally pops that tuple index while leaving the later statement alive.
The bounded check observes2 statement maps/1 comparable tuple before deletion,
and remaining ID2 with no tuple lookup afterward. NDJSON entity export iterates
statement IDs and can retain both. A proof of full content can faithfully model
all these projections, or require **one live statement per normalized tuple** for
an endpoint-comparison theorem; do not infer that premise from ordinary create
admission alone. No new issue or multigraph policy decision is made here.

## Deletion closure and snapshot policy stay separate

GraphState.delete_node only removes the node map. Actual
[OpDeleteNode](../../../../iris_src/src/Graph/KG/LedgerApply.cls#L374) checks or
cascades **default-graph** incidents and emits DeleteRelInternal records before
DeleteNodeRows. Named-graph relationships are explicitly left alone. EnsureEndpoint
can register the same bare node ID in a named graph, while replay nodes are keyed
only by bare ID. A default profile deletion with a named relationship therefore
leaves a relationship whose bare endpoint is absent from replay.nodes. Full
endpoint closure needs a default-only graph frame or an explicit projection that
admits this state. It is not an implicit GraphState cascade theorem.

Deletion snapshots must be **derived before deletion**, as source does:
NodeSnapshotJson reads sorted labels/nonreserved default-graph props;
DeleteRelInternal snapshots tuple+quals; reifier cascades can emit further node
deletions before the relationship record. The node snapshot helper does not
propagate a negative query SQLCODE: its loops simply stop. A theorem that the
snapshot equals the current full map must name successful/complete SQL reads (or
represent that failure outcome), rather than assume a supplied snapshot-truth
flag. Folding a delete discards the entity regardless of snapshot contents, so a
correct final empty fold cannot validate snapshot truth.

Continuous-life endpoint diff is tractable if actual first priors/new values are
derived from current maps and create/label/property/qualifier expansions. Across
set-before-delete, compute_diff replaces existence_prior with the **deletion-time**
snapshot and discards that lifecycle's earlier attribute priors. Root's rich
k1/L -> k2/L,M -> delete -> recreate k3 example preserves exactly the known
bug-led-101 distinction. Equal/reverse algebra and stable entry order still do
not prove endpoint reconstruction or executable inverse scripts. Keep q-con-002's
range-start versus deletion-time decision open.

## Minimal next proof and bounded native follow-up

A finite typed semantic writer state with actual node/statement maps, actual
identity allocation, separate no-op/error outcomes and emitted record sequences
is enough for the next model. Derive snapshots and priors, then prove exact
GraphState fold per step and compose existing cutoff/bound selection via a count
projection. Prove stream/export entity contents without byte-string/native JSON
or memory-bound claims. The entity bound counts nodes/statements, not property
bytes; streaming still folds eagerly. Preserve temporal/redaction/audit/unknown
record handling explicitly: create_temporal_edge is a real emitted operation but
GraphState does not turn it into a governed statement. Don't call a structural
projection a complete temporal graph reconstruction.

If root later adds native evidence, a small owned-state panel should contrast
new versus existing upsert, no-op setter versus changed setter, null/empty/`null`
text, simple complete deletion versus changed-before-delete, named relationship
survival across default-node deletion, and pre-enable keyed-parallel genesis.
The last2 settle reachability/provider premises; they need no broad harness or
new issue adjudication. Provider transaction/SQL/JSON behavior remains conditional
unless that exact native setup is exercised. No iteration12 model is authorized
by this review.
