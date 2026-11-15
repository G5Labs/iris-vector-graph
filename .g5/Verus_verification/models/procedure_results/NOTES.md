# Handled procedure results

Product3eaa79cf, foundation709a497f, iteration7. Owner: query.system-procedures.
This is an **as-built transcription**, not executable product-body verification.
No assumes/admissions/external bodies; bundled vstd only.19 verified proof units,
including two sequence helper lemmas, and10 decisive named controls. Original failed
compile/proof attempts and the earlier17-unit model are retained in results/.

## Deciding chain and represented rules

Persisted rdf_labels -> `_proc_db_labels` SQL DISTINCT/ORDER -> dispatch -> parsed
YIELD physical/alias pair -> structural tail validation -> WHERE -> optional RETURN
projection -> ORDER/SKIP/LIMIT -> public execute_cypher columns/rows. `provider`
projects all records' label codes, deduplicates and sorts them; requested graph is
ignored, preserving inherited F-0816. The model proves complete membership and no
duplicates. SQL execution/collation is a provider relation, not a verified SQL body.

`Query.source/alias/return_name/order_name` retain actual parsed names rather than
pre-decided alias-match booleans. `Tail` represents None, passing WITH names, MATCH,
UNION and RETURN DISTINCT; `bad_tail` derives admission from those variants. The
full Cypher grammar/parser and all other tail forms remain inspected or excluded.
One scoped condition is All, Eq/Ne a typed scalar, IS NULL, Unsupported or absent
parameter. Only True passes; null equality and inequality both drop text label rows,
and text differs from boolean true. Composite/list/map/general WHERE evaluation is
not proved. Empty rows bypass expression/parameter validation; structural tail
refusal remains eager. A requested RETURN list already equal to the provider's physical columns takes
an early shortcut before source validation: YIELD absent AS label RETURN label
keeps actual label values, whereas alias l refuses on nonempty data. Otherwise
incorrect source columns refuse on nonempty projection; empty RETURN still carries
the requested name. Independent review found this omitted branch in the first
18-unit model; the original false correspondence claim and source are retained
under iteration7/procedure-attempts, with a dedicated final theorem/control.

Without RETURN a db.labels alias remains a filter name but does not replace the
physical result column label. With RETURN l, projection resolves l back to label
and names the result l. ORDER consumes actual result columns: bare alias ORDER BY l
refuses even on empty rows, while RETURN l ORDER BY l succeeds. This is an as-built
exception to the ordinary alias convention; no new owner policy or repair is inferred.
Filtering precedes cutting. Legal nonnegative SKIP/LIMIT values are modeled as nat;
parser/coercion, negative pagination, multiple result columns and arbitrary providers
are outside this contract. DESC implementation is represented by reverse on the
already sorted single-column provider; the main new proofs concern alias admission,
filtering and cut rather than general heterogeneous sorting.

## Product roles and writers

| Source declaration | Formal role / evidence |
|---|---|
| engine.py IRISGraphEngine._proc_db_labels | provider; real SQL against persisted labels |
| engine.py IRISGraphEngine._try_system_procedure | dispatcher to provider; db.labels branch only |
| cypher/parser.py Parser.parse_procedure_call | raw alias pair; actual parser in every binding case |
| cypher/row_where.py yield_names | source/alias relation |
| cypher/row_where.py handler_tail | Tail/RETURN scope admission; scoped AST variants |
| cypher/row_where.py _eq / row_passes | typed scalar eq/True admission; label-text subset |
| cypher/row_where.py where_rows | filtered, nonempty early validation boundary |
| _engine/query.py _project_onto_names | RETURN projection and empty source boundary |
| _engine/query.py _apply_handler_tail | actual result-column order/cut |
| _engine/query.py QueryMixin._execute_parsed / execute_cypher | composition/final reader; handled metadata branch |
| _engine/nodes_edges.py NodesEdgesMixin.create_node / bulk_create_nodes | real label-table setup writers; state-to-provider premise, not newly proved writer transactions |

Other real writers can alter rdf_labels: update_node label additions, delete_node,
graph/all erasure, SQL/compiled Cypher writes, snapshot SQL imports and native bulk
loader. The model's finite arbitrary record state admits their committed results;
it does not prove each writer or concurrent isolation. Existing node/bulk models
supply narrower inherited contracts. The full-product/name correspondence gate
reopens if any source or new writer changes. No claim depends on a cache of labels.

## Executed evidence and controls

binding.py uses real single and bulk Python writers with the inherited bulk_children
SQLite dialect/transaction adapter (entire helper hash stamped), real metadata SQL,
parser/dispatch/WHERE/projection/tail and public result reader. Five empty/nonempty/
duplicate/cross-graph worlds, two writers, aliases,9 condition forms, optional RETURN,
three ORDER names, SKIP0/1,LIMIT absent/0/1, WITH and wrong-source/MATCH neighbors.
Final comparison count is in the fresh receipt; these are purposive combinations,
not independent samples or repository prevalence. A/B/C labels relate integer model
codes to single-character ordered text; arbitrary Unicode/IRIS collation is not proved.
The native24-case supplement runs actual default single/named bulk writers and SQL
on the task-owned identity-checked IRIS, including empty/data-dependent refusals.

Three actual comparison controls must reject: removing WHERE consumer, a method copy
removing DISTINCT, and changing returned column. These evaluate the input-derived
oracle, not just edited!=original. Formal controls remove WHERE, alias projection,
bare-column retention, empty validation bypass, structural refusal, ORDER-column
check, filter-before-limit, unscoped provider, DISTINCT and the physical-column
projection shortcut. All fail named theorems.

Initial harness failure set a readonly capabilities property. A later harness imported
the SQL helper after product classes; helper's fresh-pin import split AST class
identities and caused false ORDER refusals. The original DISAGREES receipt/log remains
but is a harness error, not a product finding. Loading the helper before all product
classes fixes the identity split; actual native24 cases corroborate final behavior.
Product files never changed. Live SQL schema/driver/connection and transaction,
network/HTTP/Bolt response packaging, GDS/translated IVG procedure numerics, multi-
column results and arbitrary expression/provider faults remain outside this proof.
