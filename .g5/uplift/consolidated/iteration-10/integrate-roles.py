import ast,csv,json,re
from pathlib import Path
R=Path.cwd(); G=R/'.g5/Verus_verification'; O=R/'.g5/uplift/consolidated/iteration-10'
def loc(path,symbol):
 p=R/path
 if path.endswith('.py'):
  tree=ast.parse(p.read_text()); hits=[]
  def visit(nodes,prefix=''):
   for n in nodes:
    if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
     name=prefix+n.name
     if name==symbol:hits.append(f'{n.lineno}-{n.end_lineno}')
     if isinstance(n,ast.ClassDef):visit(n.body,name+'.')
  visit(tree.body)
 else:
  hits=[str(i) for i,s in enumerate(p.read_text().splitlines(),1) if re.match(r'\s*(?:ClassMethod|Method|Query)\s+'+re.escape(symbol)+r'\s*\(',s)]
 assert len(hits)==1,(path,symbol,hits)
 return hits[0]
P='iris_vector_graph/_engine/algorithms.py'; S='iris_vector_graph/stores/iris_sql_store.py'; C='iris_src/src/Graph/KG/PageRank.cls'; F='.g5/Verus_verification/models/ppr_walk/ppr_walk.rs::'; B='algorithms.op.ppr'; model=(R/F.split('::')[0]).read_text()
# A source role is active only for the mathematical fragment independently accepted.
active=[
(B,'recurrence writer',C,'Run','theorem_raw_walk_mass','exact recurrence; stable closed nodes, correct Degree provider, exact real arithmetic'),
(B,'multiplicity reader',C,'Multiplicity','mult','admitted absent-or-count scalar; native ordinary positive counters, not writer correctness'),
(B,'seed membership decision',C,'NodeSeeds','theorem_valid_seed_set','shared valid member-set projection only; not ordering/wire'),
(B+'.completion','positive producer rank and cut',C,'RunJson','cut','typed positive score projection, ideal decimal key/ID order and integer limit; generic codec external'),
(B+'.completion','zero completion reader',C,'WithUnscored','fast_reader','ranked input then missing-node zero fill and final cut; SQL enumeration provider'),
(B,'fallback recurrence writer',P,'AlgorithmsMixin._kg_PERSONALIZED_PAGERANK_python_fallback','theorem_raw_walk_mass','raw scoped members/physical multiplicities to exact recurrence and full reader; float/SQL providers'),
(B+'.completion','final public reader',P,'AlgorithmsMixin._ppr_every_node','fast_reader','capped positive input then zero fill; SQL TOP enumeration provider'),
(B+'.completion','typed request composition',P,'AlgorithmsMixin.kg_PERSONALIZED_PAGERANK','theorem_public_default_cap_gap_from_raw_seeds','ordinary typed request and faithful chosen owner/reader only; dynamic dispatch/cache/type carriers external')]
obs=[
(B+'.completion','wire limit context',P,'_runjson_tail','source_limit','combined numeric effect only; omitted tuple carrier unproved'),
(B+'.completion','store owner context',S,'IRISGraphStore._execute_ppr','source_limit','public composition effect only; direct-store limit carrier differs'),
(B+'.zero_ties','decimal key context','iris_vector_graph/_collation.py','rank_key','decimal12','finite actual key observations; ideal decimal theorem not all binary float'),
(B+'.zero_ties','ID collation context','iris_vector_graph/_collation.py','collation_key','rank','integer ordered atom idealization; arbitrary IRIS collation external'),
(B,'list wrapper context',P,'AlgorithmsMixin.ppr','full_reader','nine actual wrappers observed; distinct raw-score sort not formalized'),
(B,'argument guard context',P,'check_ppr_args','public','typed refusals observed; whole-number float range mismatch outside typed model'),
(B,'seed guard context',P,'_check_seeds','valid_seeds','typed raw parser not newly proved'),
(B,'exclusion guard context',P,'_check_exclusions','hops','prefix parser context only'),
(B,'exclusion matching context',P,'_exclude_matches','hops','bare predicate fragment modeled; Type.p parsing outside'),
(B,'native guard context',C,'CheckArgs','public','finite native/source checks; raw validation unproved'),
(B,'native exclusion parser',C,'ParseExclude','hops','bare predicate fragment modeled; generic parser unproved'),
(B,'native exclusion reader',C,'Excluded','hops','typed selected predicate fragment only'),
(B,'degree provider','iris_src/src/Graph/KG/Adj.cls','Degree','hops','Degree must equal recount; cache/global writers existing obligations'),
(B,'cached owner wrapper',S,'IRISGraphStore.execute_ppr','public','correct cached score map or fresh owner premise; no new cache writer reach')]
rows=[]; audit=[]
for isactive,items in [(True,active),(False,obs)]:
 for block,role,path,sym,fn,limit in items:
  assert re.search(r'\bfn\s+'+re.escape(fn)+r'\s*[(<]',model),(fn,'missing model item')
  relation='models' if isactive else 'observes'
  grade='Observed (bounded native + actual Python/source-port)' if isactive else 'Observed (qualified context)'
  rows.append([block,role,path,sym,loc(path,sym),'C-ppr_walk',F+fn,relation,'as-built exact-math fragment' if isactive else 'source/provider context',grade])
  audit.append(dict(block=block,role=role,path=path,symbol=sym,formal_item=F+fn,relation=relation,grade=grade,limit=limit,checked=True))
path=G/'crosswalk/decision-links.tsv'; existing=list(csv.reader(path.open(),delimiter='\t')); assert not any(r[5]=='C-ppr_walk' for r in existing[1:]),'already integrated'
with path.open('a',newline='') as f:csv.writer(f,delimiter='\t',lineterminator='\n').writerows(rows)
cost=dict(block='algorithms.op.paths.weighted',role='cost-only search transition',path='iris_src/src/Graph/KG/TraversalPaths.cls',symbol='DijkstraCost',formal_item='.g5/Verus_verification/models/weighted_cost/weighted_cost.rs::theorem_actual_dijkstra_cost_complete',relation='models',grade='Observed (bounded native + actual Python/source-port)',limit='exact integer selected mirrored scalar graph; historical BestHop/actual JSON fallback; writer/native numeric/codec unproved',checked=True)
(O/'role-audit.json').write_text(json.dumps(dict(rows=[cost]+audit,new_active_role_rows=9,new_observation_role_rows=14,new_rows=23,active_fragment_roles_checked=9,direct_body_verified=0,scope='Independent review accepted Cost1/PPR8 necessary deciding/producing/reading fragment roles. PPR wire/store carriers, raw parsers, cache/Degree writers and arbitrary native numerical/codec/collation providers remain observations or existing obligations. Inherited188 not exhaustively reaudited.'),indent=2)+'\n')
print(json.dumps({'new_ppr_rows':len(rows),'active':len(active),'observations':len(obs)}))
