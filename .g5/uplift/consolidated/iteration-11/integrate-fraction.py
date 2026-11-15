"""Integrate independently replayed rational fragment; no product-body claim."""
import ast,csv,json,re
from pathlib import Path
R=Path.cwd();V=R/'.g5/Verus_verification';O=R/'.g5/uplift/consolidated/iteration-11';family='C-weighted_fraction';F='.g5/Verus_verification/models/weighted_fraction/weighted_fraction.rs::';owner='algorithms.op.paths.weighted'
p=R/'.g5/ontology/features/algorithms.g5.md';s=p.read_text();anchor='- Children: [Parallel-edge policy](#algorithms.op.paths.weighted.parallel)';assert s.count(anchor)==1
s=s.replace(anchor,'''- Verus (exact rational extension): [weighted_fraction.rs](../../Verus_verification/models/weighted_fraction/weighted_fraction.rs), `theorem_raw_signed_rational_json`, `theorem_raw_signed_rational_cost`, `theorem_backtrack_reaches_source` and `theorem_json_reader_raw_fields`; [domains, controls and source roles](../../Verus_verification/models/weighted_fraction/NOTES.md). Raw signed ratios with positive denominators derive the common grid, default1/cap scaling and independent real-state transitions, parent costs, historical BestHop and unchanged-config actual JSON fallback. Complete-step coupling derives minimum/no-path, structured path sums and finite termination; negative caps and early self0 use separate actual source branches. This extends the mathematical numerical domain of the existing searches, not their raw Python/IRIS text coercion, native rounding/JSON/collation, writer/mirror maintenance or unresolved parallel-edge policy. [22 ordinary dyadic native cases](../../uplift/consolidated/iteration-11/root-fraction-native.json) and20,522 actual Python handler/source-port worlds are finite correspondence evidence, not native executable-body proof. The independent tag2 helper miss is retained and corrected; formal source and imported kernels were unchanged.
'''+anchor);p.write_text(s)
p=V/'families.tsv';rows=list(csv.reader(p.open(),delimiter='\t'));assert not any(r[0]==family for r in rows)
with p.open('a',newline='') as f:csv.writer(f,delimiter='\t',lineterminator='\n').writerow([family,'consolidated','.g5/Verus_verification/models/weighted_fraction','verus','as-built exact-rational transcription','derived grid/default/cap normalization; independent real JSON/Cost transitions, parent/history/fallback/terminal relation; native numeric and scalar mirror/writer providers explicit','active','iteration11:181 total =93new(65proof+9recursive+19NLA)+88 unchanged imports;13controls(9source-facing/4encoding)','independent scratch181/all13/20522binding/83upstream PASS; V1 tag2 helper miss fixed, retained; no formal or product defect','.g5/Verus_verification/models/weighted_fraction/NOTES.md'])
def loc(path,symbol):
 p=R/path
 if path.endswith('.py'):
  hits=[]
  def visit(ns,prefix=''):
   for n in ns:
    if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
     name=prefix+n.name
     if name==symbol:hits.append(f'{n.lineno}-{n.end_lineno}')
     if isinstance(n,ast.ClassDef):visit(n.body,name+'.')
  visit(ast.parse(p.read_text()).body)
 else:hits=[str(i) for i,x in enumerate(p.read_text().splitlines(),1) if re.match(r'\s*(?:ClassMethod|Method|Query)\s+'+re.escape(symbol)+r'\s*\(',x)]
 assert len(hits)==1,(path,symbol,hits)
 return hits[0]
C='iris_src/src/Graph/KG/TraversalPaths.cls';items=[
('rational search transition',C,'DijkstraJson','theorem_raw_signed_rational_json',True,'finite stable typed rational raw scalar/cap; exact real queue/seen/parent; source signed-cap branch; native arithmetic/coercion external'),
('rational stored-parent reader',C,'DijkstraBacktrack','theorem_backtrack_reaches_source',True,'reachable parent chain and recorded real edge costs; proof fuel cannot truncate; native JSON bytes outside'),
('rational bidirectional search and fallback',C,'DijkstraCost','theorem_raw_signed_rational_cost',True,'real decrease-key/history/stop; effective transposes for nonnegative distinct search; actual unchanged-config JSON fallback'),
('public typed caller context','iris_vector_graph/engine.py','IRISGraphEngine._proc_ivg_shortestpath_weighted','theorem_raw_signed_rational_cost',False,'actual handler forwarding/readers executed; arbitrary raw-to-Config/YIELD/float carriers unproved'),
('structured JSON provider',C,'PathJson','theorem_json_reader_raw_fields',False,'formal structured arc/cost fields only; generic JSON string/node-array byte producer external'),
('native float provider',C,'JsonFloat','theorem_json_reader_raw_fields',False,'native scalar formatting/rounding remains finite observation'),
('scalar projection producer','iris_src/src/Graph/KG/Adjacency.cls','SetLeafFromLowest','weight',False,'inherited scalar projection/writer relation; no new maintenance or all-keyed minimum proof')]
model=(R/F.split('::')[0]).read_text();rows=[];audit=[]
for role,path,sym,fn,active,limit in items:
 assert len(re.findall(r'\bfn\s+'+re.escape(fn)+r'\b',model))==1,fn
 relation='models' if active else 'observes';grade='Observed (dyadic native + actual Python/source ports); exact-math fragment' if active else 'Observed (qualified context)'
 rows.append([owner,role,path,sym,loc(path,sym),family,F+fn,relation,'as-built exact rational fragment' if active else 'provider/caller context',grade]);audit.append(dict(block=owner,role=role,path=path,symbol=sym,formal_item=F+fn,relation=relation,grade=grade,limit=limit,checked=True))
p=V/'crosswalk/decision-links.tsv';old=list(csv.reader(p.open(),delimiter='\t'));assert not any(x[5]==family for x in old[1:])
with p.open('a',newline='') as f:csv.writer(f,delimiter='\t',lineterminator='\n').writerows(rows)
(O/'fraction-role-integration.json').write_text(json.dumps(dict(rows=audit,active_rows=3,observations=4,new_rows=7,unique_new_members_expected=0,direct_body_verified=0,scope='Three strengthened roles were already census-active. Final combined source-member delta is measured separately. Qualified mathematical domain extension; no whole-method/native executable claim.'),indent=2)+'\n');print('Integrated rational family:3 strengthened active roles/4 observations; expected0 new unique members.')
