# Next vector continuation: raw read admission, IVF admission and cache

Product3eaa79cf; preparation only while root closes iteration10. The root's
next-vector-PAIRS.md precedes its new implementation inspection. This survey used
that frozen panel and only the expressly allowed published feedback-3.md. M14,
released IVF case H3-14 and cache case H3-15 are known inputs, not new blind claims.
No evaluator/private file was inspected. No model, product, shared, ontology,
Git or database/runtime state was changed. All SQL/DDL strings in probes were
consumed by local fakes; no SQL server or DDL engine was called. New formal credit0.

## Strongest remaining candidate

Implement the **raw route/query-width admission workflow**, then compose its route
resolver with a separate IVF-build admission action and a derived positive-row
cache. This is a material missing producer/reader relation. A mismatch boolean,
prepared parser answer or supplied selected table would erase exactly the decision
M14 needs. The minimal useful theorem must derive route/table, literal width,
comparison width and effect trace from raw carriers, showing comparable wrong-width
queries raise with both dimensions before any scoring or client-vector read.
Readable absent named pairs must return[] before literal/catalog work. Correct-width
and seed neighbors must remain reachable. IVF's no-route error is a distinct build
admission result, not a search empty result.

This source-first survey found no new adjudicated product bug. The inherited
possible cached-absence concern was a forecast **miss**: _read_route already caches
only decoded positive rows. An actual second engine's resolve_route/_create_route
over the in-memory FakeRegistry creates the row, and the first engine's next read
sees it. That reflection and probe remain visible; they are not silently dropped.
The remaining cache proof gap is time/key/read-count composition and bounded
positive-row staleness, not a newly discovered missing cache invalidation.

## Actual producer-to-reader chain

| Stage | Exact current source and decision |
|---|---|
| query/public carrier | VectorMixin.kg_KNN_VEC504-542 normalizes graphNone to'', resolves _route_for_read, returns[] on tableNone, chooses/uppercases dtype, then checks width; query JSON text is preserved for the SQL bind |
| route authority | EmbeddingsMixin._route_for_read652-679 derives offered normalized model key, consumes actual _read_route result, selects actual row table; readable no row gives None except undeclared default pair; registry-absent compatibility and garbled-provider rows are separate legacy branches |
| cache producer | _route_cache_key315-324 includes registry table, graph-or'', normalized model key and kind; _cached_route326-337 checks TTL; _cache_route339-344 stores a decoded row and monotonic timestamp; misses/unavailable registry never reach that call |
| raw registry reader | _read_route377-468 materializes tuples before close, distinguishes SQLCODE-30 from other failures, filters short rows, stably prefers legacy names, decodes dimension int and dtype default, then caches the route |
| literal gate | _assert_query_width455-502 checks only string carriers whose stripped text starts'['; route dimension first if truthy, otherwise _catalog_width; len(json.loads(...)) derives outer width; parse failure or no declared width returns; mismatch raises before search |
| raw catalog reader | _catalog_width410-423 calls GraphSchema.get_embedding_dimension2063-2141: actual class lookup/derived class, compiled LEN comma/control-byte forms, then two-case INFORMATION_SCHEMA lookup and its digit heuristics; exceptions may yieldNone |
| primary score/reader | kg_KNN_VEC557-626 looks up a seed in the same table/graph, binds literal unchanged or derived stored seed text, executes scoped cosine SQL and converts float(score); primary -257 uses _raise_width_mismatch before fallback |
| optimized fallback | _kg_KNN_VEC_python_optimized795-853 re-resolves route/checks width, tries embedded SQL then DB-API, then client; both exceptions are swallowed; embedded reader filters row[0]None, while DB-API reader does not |
| client fallback | _kg_KNN_VEC_client_side855-927 re-resolves/checks, parses query JSON, fetches scoped CSV vectors, drops per-row conversion/dot/norm errors, sorts accepted scores; outer errors raise |
| IVF build | ivf_build1880-2027 validates arguments/imports dependencies first, resolves route, refuses tableNone before table cursor/query; valid route selects node_id/emb with graph bind, distinguishes empty node_ids/no rows, then clusters and invokes Build/AddBatch/Finalize/Info |
| wrappers | IRISGraphOperators.kg_KNN_VEC is a thin delegate; search_nodes_by_vector validates nonstrings, uses native KNN when available, otherwise refuses scoped IVF fallback. Native SQL/PyOps, fusion and GraphQL are other consumers, not automatically covered by this Python slice |

Route-cache TTL is strict: elapsed==30 is a hit, elapsed>30 evicts; TTL0 disables
lookup, but _cache_route can still store rows. Local invalidation removes the
matching graph/model/kind entries (None arguments are wildcards). Positive cached
rows can survive another engine's changed/dropped row until expiry. Do not assert
immediate authoritative freshness for every positive hit, or import PageRank's
different cache admission theorem.

## Existing substantive formal hits and exact gaps

G `search` is a56-unit family. Its O3 functions conflicts/read_route/read_table,
store and the associated proofs genuinely cover typed identity conflicts,
readable-registry absent/default selection, routed writes/readback under one_row,
name and column-width premises. The cached-store input is an earlier supplied row;
TTL/read count/raw query/catalog preflight are not derived. The G notes explicitly
exclude IVF/SQL KNN and cache TTL. This remains a substantive hit; it is not a raw
literal-width producer or build admission proof. When relating a new raw row
sequence to old read_route, retain its one-row premise: G arbitrarily chooses a
nonlegacy member, whereas source stable-sort chooses the first tied provider row.

C `vector_threshold` genuinely proves optional inclusive>= filtering before k,
SQL predicate/vector-bind count and actual generic/edge readers over an adapted
SQLite cosine provider (6units/3controls,32comparisons). Its ranked scaled-integer
score premise is explicit. It fixes route lookup to one table and deliberately
removes TO_VECTOR dtype/width syntax in the adapter. It proves neither this raw
width admission nor cache/IVF build. Retain its numerical/provider scope and success.
The published feedback also identifies P vector-route/IVF kernels as partial on
this producer boundary; no new P proof or broader P completeness is claimed here.

Missing roles are the actual raw route/metadata/query producer, admission/error
ordering, cache row/time derivation, and effect-sensitive actual reader composition.
A lookup returningSome(table), an already-counted vector length or generic score
predicate is insufficient. No label is treated as a substitute for those roles.

## Guarded observations and important deferred boundaries

The final probe executes96 actual pinned-function cases;23 existing zero-fixture
unit functions pass as written. All have0socket connects. Three copied actual
method mutations are detected: remove width mismatch refusal, override route-width
precedence with catalog width, and omit graph from cache key. Raw SQL, metadata,
score rows and Native Build/Info port results are local fixtures, not IRIS evidence.
The populated IVF neighbor does execute one-vector local sklearn clustering and
actual Python Build/AddBatch/Finalize/Info carriers over the fake port; it does not
execute or prove native IVF clustering/search/storage.

The census keeps unsupported and typed neighbors:

- nested arrays are parsed and counted by outer length (2), so route4 refuses;
  [true,false,null,"x"] has outer length4 and can reach the score provider. Width
  validity is not numeric element validity. NaN/Infinity spelling is also retained.
- list/tuple/None/numeric direct carriers skip the literal guard; the fake SQL
  provider may accept them, while direct client json.loads can raise TypeError.
  Native binder acceptance is unassessed, not inferred from fake success.
- route dimensionNone/empty/0/False uses catalog; True decodes1; string'4' decodes4;
  malformed recorded dimension raises during actual route decoding. Invalid dtype
  types may error before width; do not assume dtype is normalized after a failure.
- compiled LEN comma/control-byte and VECTOR catalog forms derive4. All-catalog
  failures yieldNone, without inventing a width. A supplied INFO_SCHEMA
  VARCHAR(4000) string is parsed as4000 by source's generic heuristic. That is an
  unsupported metadata/provider boundary, not a proven physical column width or
  a newly established ordinary-native bug.
- non-30 registry read error propagates; -30 uses compatibility; short provider
  rows use the source's degraded legacy path, tableNone can answer[], and typed
  bad dtype can error. These differ from readable absent normal rows.
- text-numeric/int/bool scores convert through Python float. A None score causes
  generic fallback; the last client neighbor computes1/sqrt(30) on supplied CSV.
  This is an actual reader/fallback observation, not a native cosine proof.

The requested public mixed-failure contrast is retained with the same raw
route.dimensionNone, catalog failures, query3 and stored CSV4. Immediate primary
-257 raises ValueError after1SQL score attempt. A first primary non-257 availability
fault, then optimized -257, leads to per-row client mismatch and **public[]** after
2SQL attempts. The direct optimized case has the same empty boundary. This is
provider-adapter evidence, not an actual native outage or a newly counted issue;
root retains it as deferred source behavior pending native/intent work. A new model
must not falsely prove that every width-provider failure anywhere always raises.

Empty[] therefore has at least two source histories: no selected route/no scoring,
or selected route/provider attempts/client rows all dropped. Result equality alone
misses that distinction. The next model/binding should count both SQL cosine calls
and client-vector reads/kernel attempts; VECTOR_COSINE text alone is not every
scoring effect. Embedded-success typed-row behavior was read in source but was not
executed in this panel (embedded availability is forced to fail); keep it unassessed
until its actual reader is included.

Cache observations derive [a,b,c,edge,a] with4registry reads and distinct keys.
The cross-engine miss/create/read uses4route SELECTs total: first miss1, writer's
pre-lock/under-lock reads2more, then reader's fresh read. Positive cache observes
old width4/table at0 and30, new width3/table at30.001; explicit invalidation rereads.
The raw positive-row replacement is a provider-state change, not evidence of an
ordinary cross-process writer race or a new freshness bug.

## Next model shape and meaningful controls

Start with raw registry response rows/fault code+message, per-engine cache maps and
clock readings, raw catalog cells/faults, graph/model/kind request carrier and raw
query text/type. Derive SQLCODE-30 classification, row arity/field decoding,
preference/selected route, key+TTL lookup and cache update. Do not take a supplied
readable flag, route table, parse answer or mismatch boolean. A legitimate external
provider event may supply raw rows or an exception, not a preselected consumer result.

Implement a raw-character JSON parser/counting fragment and its relation to source
json.loads, rather than an input length. Standard numeric arrays with whitespace,
signs/decimals/exponents and empty-array neighbors are the minimum useful start.
A complete width parser can use recursive JSON value grammar (array/object/string/
number/true/false/null), deriving only outer-array count without float mathematics.
Keep Python's NaN/Infinity extensions, unsupported syntax and non-string carriers
explicit. A narrower first theorem must name its language precondition and retain
all outside cases in the census; unsupported valid JSON must not be reclassified as
source parse failure or silently assigned an invented Unsupported API result.

Derive comparison width from raw route dimension int/truthiness, else actual raw
catalog parsing/fallback. Scope physical-width truth to inspected metadata/provider
forms, not the heuristic's output by fiat. Trace separate RouteRead/CatalogRead/
SeedRead/SqlScore/EmbeddedScore/ClientVectorRead/ClientKernel/Build/Return/Raise
steps. Prove absence-before-width, comparable mismatch-before-all-scoring, no
padding/truncation of the literal bind, correct-width/seed reachability, error
classification and actual final reader relations. Model the mixed-failure empty
history as-built; do not repair its catches merely to obtain a stronger theorem.

Use a separate Build action sharing route resolution. Retain validation/dependency
admission before routing, no-route ValueError before table read/Build, graph/table
selection and empty-node/no-vector neighbors. K-means arithmetic and native IVF
contents/search remain outside an admission theorem. Validation results are not
assigned back to source locals: do not assume Pydantic coercion rewrites the original
arguments. Admitted normal Python integer/string arguments are a credible initial
fragment; unsupported typed build arguments remain unassessed until represented.

Then derive cache key isolation/read counts, misses/unavailable registry not cached,
miss->other-create->fresh read, exact TTL boundary, TTL0 and local invalidation.
Any old G/C import must be reported separately as rechecked; do not inflate a new
claim with unrelated imported BM25 units. The raw producer/reader work is tractable;
hard parsing or composition is not a reason to call it blocked or stop at a label.

Meaningful next controls: width check removed; compare catalog before recorded
width; compare width before absent route early-return; fabricate a default width
on unknown metadata; truncate/pad the score bind; conflate registry error with
absence; omit graph/model/kind/schema from cache key; cache a miss; change strict TTL
boundary; remove IVF no-route guard; read another table/omit graph; alter actual
float/None reader. Attribute each to a concrete derived theorem and input-dependent
observation. Source-port/provider mocks and actual product-method mutants must
remain classified separately from native experiments.

## Retained attempts and observed costs

The first96-case mixed schedule attempt failed because engine construction consumed
the fault sequence during capability probes. The corrected panel installs that
sequence at request start. The initial94-case panel also used invalid fixture table
names, so ordinary table validation blocked positive/control paths; it is retained
with its failed checks/debug output. Legitimate routed-name syntax fixed the fixture
without bypassing validation. Both failed scripts/json/logs and the successful
94-case intermediate are preserved, alongside final96 and unit23. No failed or
unassessed observation was removed from the record. Final probe3.78s; units3.87s;
other attempt costs remain in their receipts/logs. Formal/native costs are0 here.
No repository-wide prevalence, new blind success or convergence inference follows.
