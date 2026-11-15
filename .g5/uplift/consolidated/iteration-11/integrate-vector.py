"""Integrate independently accepted V2 node-vector admission fragments."""
import ast,csv,json,re
from pathlib import Path
R=Path.cwd();V=R/'.g5/Verus_verification';O=R/'.g5/uplift/consolidated/iteration-11';family='C-vector_admission';root='.g5/Verus_verification/models/vector_admission/vector_admission.rs';cat='.g5/Verus_verification/models/vector_admission/catalog.rs'
p=R/'.g5/ontology/features/search.g5.md';s=p.read_text()
def add(bid,line,replace=None):
 global s
 m=re.search(r'^### '+re.escape(bid)+r'\n(.*?)(?=^### |\Z)',s,re.M|re.S);assert m,bid;b=m.group(0)
 if replace:
  assert replace in b,(bid,'missing old metadata');b=b.replace(replace,line)
 else:
  lines=b.splitlines();index=next((i for i,x in enumerate(lines) if x.startswith('- Expands:')),2);lines.insert(index,line);b='\n'.join(lines)+'\n\n'
 s=s[:m.start()]+b+s[m.end():]
old='- Verus: `search` (as-built) `read_route`/`read_table` model route absence, not the query-width preflight; the playbook\'s `vec_route_batch` explorer and `proofs-d1b` `vq_l2` (reviewed) do not either. No formal contract for the order "route, then width, then search".'
add('search.embedding.width','- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `width_check`, `theorem_direct_guard_no_score` and `theorem_whole_raw_row_four_query_three_no_scoring` derive route-before-width-before-score from raw rows, query characters and catalog cells for the three node KNN entry points. Nested JSON/strings/non-numeric elements are counted by the modeled outer-array lexer; syntax does not establish vector-element validity. JSON/library correspondence is finite observation, catalog output is a heuristic rather than physical-width truth, and numeric kernels/raw identifier carriers remain providers. Existing G search and P route kernels remain substantive typed routing hits; this does not establish every vector/edge/store/protocol surface.',old)
add('search.routes.no_fallback','- Verus (raw workflow extension): [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `resolve` and `theorem_whole_missing_raw_pair_returns_quiet_empty` derive scoped raw row selection, decoding, default/compatibility exceptions and named absence before any seed/vector/scoring effect. Stable provider row order and already-normalized identifier keys are explicit; no new route DDL/transaction or identity-codec theorem is inferred.')
add('search.routes.cache','- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `key`, `cached`, `evict`, `resolve`, `invalidate` and `theorem_all_search_phases_keep_original_scope` derive cache key isolation, separate store/lookup timestamps, strict expiry, no negative insertion and read counts. V2 fixes registry/graph/model/node-kind/TTL from the original stable engine request across fallbacks; only provider replies and clock samples vary. Integer clock ticks preserve comparisons; arbitrary native float-clock refinement, concurrent DDL/writer correctness and universal invalidation are unproved. TTL0 bypasses lookup without clearing old entries.')
add('search.knn','- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `theorem_primary_generic_failure_really_calls_optimized`, `theorem_optimized_double_failure_really_calls_client`, typed score readers and raw CSV shape/effect relations cover the primary/optimized/client node-search chain. The source model retains both the seed-identity-loss counterexample and the unknown-width mixed-error empty answer. SQL/NumPy numeric replies are provider inputs, with finite actual readers and predicates executed in735 binding comparisons; no cosine/ANN/numerical or native-body theorem follows. Nonstring/raw numeric carriers, connection/cursor allocation and exact exception text remain qualified.')
add('search.scope','- Verus (node KNN slice): [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `theorem_all_search_phases_keep_original_scope` keeps original registry, normalized graph/model and TTL across every phase, with node kind fixed. Raw row filters and actual SQLite table/graph/label predicates corroborate that selected slice; fusion, other index dispatch, GraphQL and native SQL procedure scope are not transferred from it.')
add('search.scope.indexes.ivf','- Verus: [vector_admission](../../Verus_verification/models/vector_admission/NOTES.md) `theorem_no_route_refuses_before_vector_read`, `theorem_empty_ids_after_cursor_before_select`, `theorem_malformed_info_after_build_keeps_local_maps` and `theorem_valid_info_publishes_after_native_prefix` derive the separate build admission/effect order from raw arguments, route rows and provider replies. The ordinary explicit text/metric/positive-int rule is modeled; generic Pydantic coercion is not. External Build/AddBatch/Finalize/Info effects can survive a later error; only local publication waits for syntax-valid Info. Opaque decoded Info content, base64/float32/clustering/native index correctness and rollback are outside this contract.')
p.write_text(s)
p=V/'families.tsv';existing=list(csv.reader(p.open(),delimiter='\t'));assert not any(x[0]==family for x in existing)
with p.open('a',newline='') as f:csv.writer(f,delimiter='\t',lineterminator='\n').writerow([family,'consolidated','.g5/Verus_verification/models/vector_admission','verus','as-built ordinary provider transcription','raw scoped rows/cache/JSON+catalog -> three node search phases/readers/effects and separate IVF admission; numerical/native/codec providers explicit','active','iteration11:77new=51proof(45theorem/6helper)+26recursive;0imports/NLA;8controls','independent V2 77/all8/735binding+3constructorchecks/23upstream PASS; V1 scope-TTL overapprox retained corrected; extra reviewer TTL mutation ordinary failure','.g5/Verus_verification/models/vector_admission/NOTES.md'])
def loc(path,symbol):
 tree=ast.parse((R/path).read_text());hits=[]
 def visit(ns,prefix=''):
  for n in ns:
   if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
    name=prefix+n.name
    if name==symbol:hits.append(f'{n.lineno}-{n.end_lineno}')
    if isinstance(n,ast.ClassDef):visit(n.body,name+'.')
 visit(tree.body);assert len(hits)==1,(path,symbol,hits);return hits[0]
E='iris_vector_graph/_engine/embeddings.py';P='iris_vector_graph/_engine/vector.py';S='iris_vector_graph/schema.py';W='search.embedding.width';C='search.routes.cache';K='search.knn';B='search.scope.indexes.ivf';N='search.routes.no_fallback';scope='search.scope'
items=[
(C,'cache key producer',E,'EmbeddingsMixin._route_cache_key',root,'key',True,'normalized registry/graph/model/kind atoms only'),
(C,'positive cache selector',E,'EmbeddingsMixin._cached_route',root,'cached',True,'strict TTL comparison; clock ticks and stable config, no binary64 or drift proof'),
(C,'decoded row cache writer',E,'EmbeddingsMixin._cache_route',root,'resolve',True,'own write_at separate from lookup timestamp; no DDL/concurrent writer theorem'),
(C,'local cache invalidator',E,'EmbeddingsMixin.invalidate_route_cache',root,'invalidate',True,'exact scoped/wildcard deletion; universal call sites not proved'),
(N,'raw registry producer',E,'EmbeddingsMixin._read_route',root,'resolve',True,'scoped rows, stable preference, ordinary field decode/absent classification; provider formats explicit'),
(N,'route selector',E,'EmbeddingsMixin._route_for_read',root,'theorem_whole_missing_raw_pair_returns_quiet_empty',True,'derived readable absence vs default/compatibility; normalization external'),
(W,'raw query width guard',P,'VectorMixin._assert_query_width',root,'width_check',True,'modeled raw JSON outer count and route/catalog comparison; stdlib grammar correspondence finite'),
(W,'catalog adapter',P,'VectorMixin._catalog_width',cat,'read',True,'truthy/None output normalization; class lookup/driver interface external'),
(W,'raw metadata parser',S,'GraphSchema.get_embedding_dimension',cat,'raw',True,'ordinary ASCII LEN/control/INFO parsing and selection; not physical-width truth or arbitrary bytes'),
(K,'primary workflow and reader',P,'VectorMixin.kg_KNN_VEC',root,'theorem_primary_generic_failure_really_calls_optimized',True,'typed primary reader/seed expansion/width failure/fallback; controlled105 departure retained'),
(scope,'optimized workflow and reader',P,'VectorMixin._kg_KNN_VEC_python_optimized',root,'theorem_optimized_double_failure_really_calls_client',True,'per-entry guard, embedded/DBAPI readers and fallback; kernels/providers explicit'),
(scope,'client workflow and reader',P,'VectorMixin._kg_KNN_VEC_client_side',root,'theorem_client_shape_refusal_is_derived',True,'array-construction provider, numeric CSV shape, attempted kernels/drop/rank; no NumPy math proof'),
(W,'width diagnostic reader',P,'VectorMixin._raise_width_mismatch',root,'diagnostic',True,'raw array/list query count and first CSV comma count; arbitrary scalar/str/exact message excluded'),
(B,'ordinary argument gate','iris_vector_graph/_validate.py','IVFBuildInput',root,'valid',True,'explicit raw nonempty text/metric/positive-int gate; not generic Pydantic/coercion/resource proof'),
(B,'IVF admission and effect reader',P,'VectorMixin.ivf_build',root,'theorem_no_route_refuses_before_vector_read',True,'raw argument/route/selection -> native prefix/local publication; Info content/clustering/index/atomicity unproved'),
(C,'route publication context',E,'EmbeddingsMixin._create_route',root,'resolve',False,'later raw row publication observed via actual writer fakes/native neighbor; no new DDL/lock/commit proof'),
(W,'class lookup provider',S,'GraphSchema.resolve_table_class',cat,'raw',False,'actual cursor/class lookup observed, no new class/identifier selector theorem'),
(B,'other IVF dispatch context',P,'VectorMixin.search_nodes_by_vector',root,'theorem_no_route_refuses_before_vector_read',False,'different search dispatch is outside the build theorem; no transferred reach')]
rows=[];audit=[]
for block,role,path,sym,fp,fn,active,limit in items:
 assert len(re.findall(r'\bfn\s+'+re.escape(fn)+r'\b',(R/fp).read_text()))==1,(fp,fn)
 relation='models' if active else 'observes';grade='Observed (actual Python/SQLite + finite native); ordinary fragment' if active else 'Observed (qualified context)';rows.append([block,role,path,sym,loc(path,sym),family,fp+'::'+fn,relation,'as-built ordinary provider fragment' if active else 'provider/other-consumer context',grade]);audit.append(dict(block=block,role=role,path=path,symbol=sym,formal_item=fp+'::'+fn,relation=relation,grade=grade,limit=limit,checked=True))
p=V/'crosswalk/decision-links.tsv';old=list(csv.reader(p.open(),delimiter='\t'));assert not any(x[5]==family for x in old[1:])
with p.open('a',newline='') as f:csv.writer(f,delimiter='\t',lineterminator='\n').writerows(rows)
frac=json.loads((O/'fraction-role-integration.json').read_text());allrows=frac['rows']+audit;before=json.loads((O/'before-reach/bindings.json').read_text());new=sorted({x['path']+'::'+x['symbol'] for x in allrows if x['relation']=='models'}-set(before))
(O/'role-audit.json').write_text(json.dumps(dict(rows=allrows,new_active_role_rows=18,new_observation_role_rows=7,new_rows=25,active_fragment_roles_checked=18,new_unique_members_from_locators=new,unique_new_members=len(new),direct_body_verified=0,scope='All18 bounded necessary fragment roles independently reviewed;7 are strengthening roles already active. Counted members are locators, not whole bodies. Raw codecs/native numeric/catalog truth/provider/other surfaces remain qualified; inherited197 not exhaustively reaudited.'),indent=2)+'\n');print(json.dumps(dict(vector_active=15,vector_observations=3,total_active_rows=18,total_observations=7,new_unique_locators=len(new))))
