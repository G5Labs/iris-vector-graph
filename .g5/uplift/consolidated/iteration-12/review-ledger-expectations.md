# Independent ledger-content expectations before candidate inspection

Product3eaa79cf77d3e0a879b2cced634cf2729d81499e; sealed11
9de67a2841e6250d322f73bdd951bbe121867340. Before12 archive digest
8dc3d2901ad993fd0200e9aab82cf3ca87b2f63d586970aad08162276869c594.
No new ledger_content candidate was inspected before this panel. Frozen11 PAIRS,
plan,23 source observations and7 independent premise probes are disclosed starting
evidence. Selection follows ledger.readers/.bound/.diff/.diff.order and actual
writer/reader source, not evaluator-only cases. Public guidance8442346f applies;
private evaluator artifacts are uninspected. q-con-002 and related bound/order
policy questions remain open; bug-led-101 is already known, not a new discovery.

## Frozen producer-to-reader neighbors

| ID | Material neighboring observation and necessary derivation |
|---|---|
| L1 | Fresh node with labels/props emits create_node(new empty string) followed by separate actual add_label/set_prop records; existing upsert emits no create and preserves unrelated content. Identical label/value writes succeed with no record. Derive lists and actual priors from current state, not a full preapplied create snapshot. |
| L2 | New relationship emits tuple-only create_rel then ordered qualifier records, with allocated statement identity; existing live-tuple upsert merges qualifiers without reset/new create. Actual tuple lookup/allocation and emitted priors must decide, not a supplied final relationship. |
| L3 | SQL null flag versus empty string versus literal text null remains distinct through from_row; from_wire is another carrier. The actual set_prop/set_qual fold maps newNone to empty text. A reader-only None/None record may therefore create empty content with an empty diff, but ordinary Enc(value) histories need not produce it. |
| L4 | Nested JSON-looking strings, numbers/bools represented as text and empty values survive exact property/qualifier maps/export as strings. Equality of opaque strings is not recursive JSON typing or a universal native coercion/encoding theorem. Label presence records use empty-string new/prior markers, not a supplied boolean/"1" value. |
| L5 | create_rel.new tuple graph versus disagreeing record.graph: the parsed tuple is deciding. None/empty/NUL default graph normalize alike; named tuple stays named. Typed TupleJson/parser correspondence may be explicit; malformed/nonobject JSON and arbitrary ID coercion must remain separate/error/unassessed. |
| L6 | Raw create resets existing node/statement state regardless of r.new contents; attribute set on absent entity is ignored, remove is idempotent. These general GraphState behaviors differ from ordinary writer refusals and cannot all be called reachable ApplyAll operations. |
| L7 | Reserved node keys id/__graph, missing entities/nonempty keys and removing missing values refuse at actual producer checks. Deleted-node/deleted-statement guards forbid same-changeset reuse; recreate across later revisions is a different neighbor. Qualifier admission differs from node reserved keys. |
| L8 | Deletion prior is serialized from actual current labels/properties or tuple/qualifiers before removal. A complete simple delete passes; mutating a supplied snapshot flag/map is insufficient. Snapshot captures need complete successful SQL/provider reads, not just a final empty reconstruction. |
| L9 | GraphState.delete_node does no implicit statement cascade. Actual detach producer emits default-graph incident relationship deletions first; strict mode may refuse. Named relationships survive default-node deletion, so replay can retain a statement with a bare endpoint absent from replay.nodes. |
| L10 | A surviving named node registration versus absent bare replay node after default deletion: graph-blind native NodeExists can still refuse later create_node(same ID) as node_exists. Ordinary producer correspondence needs separate physical memberships or a default-only frame; replay.nodes membership cannot substitute for NodeExists. |
| L11 | Genesis two physical rows of one normalized tuple allocate two statement IDs. GraphState statement map/export can retain both, tuple reverseindex/as_comparable collapse or lose lookup after deleting the earlier ID. One-live-statement-per-tuple must be proved for the admitted producer set or explicitly qualified; ordinary create admission does not establish it for Genesis. |
| L12 | Genesis scans node/label/property SQL rows without graph filters while replay node keys are bare IDs. Named/default copies can reset/collapse/merge in that projection. State actual projection or single-bare-ID/default frame; do not call it a full graph-scoped node reconstruction by assumption. |
| L13 | Adopt accepts record-shaped changes, allocates/reuses statement IDs and writes records without ordinary canonical mutations/admission. It must remain represented or an explicit separate provider boundary. ApplyAll reachability claims do not silently cover Genesis/Adopt or arbitrary raw reader histories. |
| L14 | Across a continuously live entity, labels/props/quals changed then restored yield no net entry; other changes use actual first prior and last new matching two named reconstructed endpoints. Derive both endpoint states from emitted records and all full maps; do not provide endpoint operands or an expected delta to the proof. |
| L15 | Existing k1/L →k2/L,M →delete→recreate k3 retains deletion-time snapshot k2/L,M rather than range-start k1/L. Preserve richer known bug-led-101 witness and simple-delete passing neighbor; inversion/equal-revision algebra does not resolve q-con-002 or authorize executable scripts. |
| L16 | Later records beyond named cutoff cannot change nested content or intermediate size refusal for that cutoff. Bound compares nodes+statements after every folded record; transient over-bound then later deletion still refuses ordinary reconstruction. Property bytes are not counted. |
| L17 | stream=True ignores that refusal but folds eagerly before returning its iterator. Export folds unbounded, emits actual complete labels/props/tuple/quals/statement IDs, and GraphState export ordering differs from passing an arbitrary iterator. Structured projection is not a byte-string/native JSON or bounded-memory theorem. |
| L18 | Named equal revisions produce empty diff; reversed endpoints select same actual lo+1..hi records then invert/sort. Unknown revision/redaction guards and seq/ordinal page selection must be actual reader roles or explicit existing contracts, not supplied cutoff/history lists pretending to prove the producer. |
| L19 | Tombstones/revision audit do not change GraphState; tombstones are separately listed by diff. Unknown/temporal operations are not automatically full structural content. A continuous endpoint theorem must name its recognized operation frame, not quietly project away a real writer and claim complete temporal reconstruction. |
| L20 | Successful complete snapshot/record queries versus quiet partial/failed provider reads: successful final fold or entity counts do not validate prior snapshot truth. Decoder/pager/provider contracts and native transaction/writer closure remain separate unless actually represented/corroborated. |

## Proof and binding architecture to challenge

Start with semantic operations, physical/logical memberships where necessary,
identity allocation and actual current maps. Derive all ordinary records, null
tags, first priors, snapshot maps and no-op/error outcomes; then actual GraphState
fold and count projection; then named cutoff/bound/stream/export and continuous-
life diff. Initial empty/genesis state may not be replaced by a prepared full
answer without an explicit existing provider contract. Prove map contents and
tuple identity, not merely cardinalities. A separate default-only ordinary writer
fragment can be useful, but named/Genesis/Adopt exclusions must remain visible.

Expected roles include LedgerApply create/upsert/label/property/relationship/
qualifier/delete helpers, Enc/EncNull/Rec/TupleJson, NodeExists/EnsureEndpoint,
snapshot/statement allocation; LedgerGenesis.Capture/Adopt; Ledger.RecordsFetch;
MutationRecord.from_row; contributes/_parse_tuple/_graph_key; GraphState.apply,
stmt_for_tuple/as_comparable; named GraphLedger reader/cutoff and iter_records;
reconstruct plus export_ndjson/_iter_entities; and actual lifecycle compute_diff.
These are expected deciding/writing/reader roles, not automatic whole-member
credit. Existing reconstruction/history_diff/paging remain substantive hits.

Controls should alter emitted expansion/prior/null/tuple/default graph, one actual
label/property/qualifier write, reset/ignore semantics, cutoff, intermediate bound,
snapshot prior or first-prior retention and reject changed final content against
unchanged input-derived expectations. Keep actual Python versus ObjectScript
source-port/helper versus observation sensitivity separate. No raw prepared map,
truth bit, DP answer or result-as-premise may decide the boundary it purports to
prove. Ordinary false claims earn control credit; syntax/type/resource/lookup
failures do not. Preserve exact pre-attempt bytes, misses and unsupported frames.

This reviewer runs no native calls. Root's controlled native evidence may settle
finite reachability/provider cases, not native body equivalence or a policy answer.
