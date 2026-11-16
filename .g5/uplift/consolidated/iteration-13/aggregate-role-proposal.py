"""Conservative source-role proposals; no central metadata mutation."""
from pathlib import Path
import json,re,hashlib
R=Path(__file__).resolve().parents[4];O=Path(__file__).resolve().parent;M=R/'.g5/Verus_verification/models/aggregate_results/aggregate_results.rs'
census=json.loads((O/'before-reach/census.json').read_text());before=json.loads((O/'before-reach/bindings.json').read_text());formal={}
for i,line in enumerate(M.read_text().splitlines(),1):
 m=re.search(r'pub proof fn (\w+)',line)
 if m:formal[m[1]]=i
T='iris_vector_graph/cypher/translator.py';Q='iris_vector_graph/_engine/query.py';N='iris_src/src/Graph/KG/Cypher/Exec.cls';P='iris_vector_graph/prop_values.py';S='iris_vector_graph/stores/iris_sql_store.py'
active=[
(T,'_expr_aggregation','theorem_raw_group_SUM_reaches_typed_scalar_reader','Admitted property-SUM AST derives NULL/DISTINCT/raw-float decisions and exact numeric storage to scalar reader.','SQL aggregate/equality/CY_IS_FLOAT/CAST/spelling are provider relations; exact integer/half-unit fragment, no backend/body proof.'),
(N,'Group','theorem_native_entity_count_is_raw_identity_set','Raw graph+ID distinct insertion and increment.','pW=1, stable normal nonnull bound IDs whose entity graph is the row graph; compressed/parallel/missing bindings outside.'),
(N,'GroupOf','theorem_key_enumeration_complete_unique','Derived exact-key group allocation is complete and unique.','Admitted key equality/projection only; raw-list/cache/hash/long-key/native collation providers excluded.'),
(N,'EmitGroups','theorem_full_output_before_page','Complete derived aggregates precede final order/page; empty global distinct from grouped.','Complete unique ORDER permutation premise; sort/trim/count-bound/parallel/native JSON outside.'),
(Q,'_drop_internal_columns','theorem_reader_projection_keeps_exact_public_cells','Raw generated ASCII __sort digits with optional _n/_s select scalar index projection.','Combined model has an earlier __rn filter, separately attributed to store. Equal-width generated scalar rows; Unicode regex/Bolt metadata excluded.'),
(P,'decode_typed_text','theorem_raw_group_SUM_reaches_typed_scalar_reader','Derived SUM numeric storage reaches existing N/D scalar relation.','Imported scalar kernel already credited; numeric spelling/payload parse and half-unit identity are providers, not new import gain.'),
]
observed=[(T,'_zero_if_null'),(T,'_numeric_static_type'),(T,'_json_text_list_agg'),(T,'_null_row_aggregate'),(Q,'QueryMixin._execute_parsed_sql'),(S,'IRISGraphStore.execute_sql'),(Q,'_finish_sql_result'),(Q,'_decode_typed_value_columns'),(Q,'_decode_numeric_expr_columns'),(Q,'_decode_json_value_columns'),(Q,'_fill_empty_columns'),(N,'KeysJSON'),(N,'GroupRow'),(N,'KeyValues')]
rows=[]
for path,symbol,item,claim,qual in active+[(p,n,None,'Actual ordinary producer/caller/reader or inspected native serializer correspondence.','No formal whole-function/body/metadata/codec/error theorem; OPTIONAL remains partial with bug-agg-001, native serializers only inspected.') for p,n in observed]:
 sid=path+'::'+symbol;assert sid in census,sid;assert item is None or item in formal,item
 native=path.endswith('.cls');role='bounded-active' if item else 'observation-only'
 rows.append(dict(source_id=sid,path=path,symbol=symbol,line_start=census[sid]['lines'][0],census_lines=census[sid]['lines'],sha256=hashlib.sha256((R/path).read_bytes()).hexdigest(),owner='query.aggregation',role=role,formal_item=str(M.relative_to(R))+'::'+item if item else None,formal_line=formal[item] if item else None,already_bound_before=bool(before.get(sid)),before_bindings=before.get(sid,[]),claim=claim,qualifier=qual,evidence_tier='Inspected (typed transcription only; no relevant native execution)' if native else 'Observed (actual Python/local executing provider; root finite native SQL separately)'))
body=dict(principal_owner='query.aggregation',roles=rows,recommendations_only=True,direct_executable_body_verified=0,active_count=sum(x['role']=='bounded-active' for x in rows),active_newly_unbound_before=sum(x['role']=='bounded-active' and not x['already_bound_before'] for x in rows),before='231/4130 sealed12; exact before-reach IDs/line starts used',scope='No census growth from observation-only rows. All three ObjectScript active roles are inspected typed transcriptions, not root SQL-native execution. Shared scalar reader imports/domain extensions remain already-bound.')
(O/'aggregate-source-roles.json').write_text(json.dumps(body,indent=2)+'\n');print(json.dumps({k:body[k] for k in ['active_count','active_newly_unbound_before']}))
