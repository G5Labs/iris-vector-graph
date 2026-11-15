"""Independent stable-source verifier-unit accounting; excludes moving iteration11 models."""
import datetime,hashlib,json,re,shutil,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];MODELS=ROOT/'.g5/Verus_verification/models';SCRATCH=HERE/'count-audit-scratch';VERUS=Path('/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus')
SKIP={'vector_admission','weighted_fraction'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def masked(text):
 # Preserve offsets/lines while removing comments and literal contents. No AST/token
 # count is inferred from the final verifier total.
 a=list(text);i=0;n=len(text)
 def blank(x,y):
  for k in range(x,y):
   if a[k]!='\n':a[k]=' '
 while i<n:
  if text.startswith('//',i):
   j=text.find('\n',i);j=n if j<0 else j;blank(i,j);i=j;continue
  if text.startswith('/*',i):
   j=i+2;depth=1
   while j<n and depth:
    if text.startswith('/*',j):depth+=1;j+=2
    elif text.startswith('*/',j):depth-=1;j+=2
    else:j+=1
   blank(i,j);i=j;continue
  raw=re.match(r'(?:br|rb|r)(\#*)"',text[i:])
  if raw:
   close='"'+raw.group(1);j=text.find(close,i+raw.end());j=n if j<0 else j+len(close);blank(i,j);i=j;continue
  if text[i]=='"':
   j=i+1
   while j<n:
    if text[j]=='\\':j+=2
    elif text[j]=='"':j+=1;break
    else:j+=1
   blank(i,min(j,n));i=j;continue
  if text[i]=="'":
   ch=re.match(r"'(?:\\.|[^'\\])'",text[i:])
   if ch:blank(i,i+ch.end());i+=ch.end();continue
  i+=1
 return ''.join(a)
DECL=re.compile(r'\b(proof|spec|exec)\s+fn\s+([A-Za-z_]\w*)')
def outline(p):
 text=p.read_text();m=masked(text);found=list(DECL.finditer(m));out=[]
 for index,h in enumerate(found):
  end=found[index+1].start() if index+1<len(found) else len(m);segment=m[h.start():end];brace=segment.find('{');header=segment[:brace] if brace>=0 else segment;body=segment[brace:] if brace>=0 else ''
  nla=[text.count('\n',0,h.start()+q.start())+1 for q in re.finditer(r'\bby\s*\(\s*nonlinear_arith\s*\)',segment)]
  out.append({'mode':h.group(1),'name':h.group(2),'line':text.count('\n',0,h.start())+1,'decreases_in_spec_header':h.group(1)=='spec' and bool(re.search(r'\bdecreases\b',header)),'direct_self_call':bool(re.search(r'\b'+re.escape(h.group(2))+r'\s*\(',body)),'nonlinear_subquery_lines':nla})
 return out
inventory=[];files=[]
for d in sorted(MODELS.iterdir()):
 if not d.is_dir() or d.name in SKIP:continue
 for p in sorted(d.glob('*.rs')):
  funcs=outline(p);nla=[x for x in funcs if x['nonlinear_subquery_lines']]
  inventory.append({'file':str(p.relative_to(ROOT)),'sha256':sha(p),'proof_declarations':sum(x['mode']=='proof' for x in funcs),'decreasing_spec_declarations':[x['name'] for x in funcs if x['decreases_in_spec_header']],'explicit_nonlinear_subqueries':sum(len(x['nonlinear_subquery_lines']) for x in funcs),'nonlinear_functions':nla});files.append(p)
assert sorted((Path(x['file']).parent.name,x['explicit_nonlinear_subqueries']) for x in inventory if x['explicit_nonlinear_subqueries'])==[('fusion_ranking',2),('ppr_walk',17)]
selected={};commands=[];started=time.perf_counter()
for model in ['ppr_walk','fusion_ranking']:
 original=MODELS/model/(model+'.rs');dest=SCRATCH/'inputs/models'/model;dest.mkdir(parents=True,exist_ok=True)
 shutil.copy2(original,dest/original.name);shutil.copy2(MODELS/model/'model.json',dest/'model.json')
 funcs=outline(original);proofs=[x for x in funcs if x['mode']=='proof'];specs=[x for x in funcs if x['decreases_in_spec_header']];nlas=[x for x in funcs if x['nonlinear_subquery_lines']]
 assert all(x['direct_self_call'] for x in specs)
 expected=(68,18,17,103) if model=='ppr_walk' else (7,2,2,11)
 assert (len(proofs),len(specs),sum(len(x['nonlinear_subquery_lines']) for x in funcs))==expected[:3]
 manifest=json.loads((dest/'model.json').read_text());assert manifest['expected_verified']==expected[3]
 selected[model]={'source':str(original.relative_to(ROOT)),'source_sha256':sha(original),'scratch_source':str((dest/original.name).relative_to(ROOT)),'scratch_source_sha256':sha(dest/original.name),'proof_declarations':proofs,'recursive_specs':specs,'nonlinear_proof_functions':nlas,'totals':{'proof_declarations':expected[0],'recursive_spec_checks':expected[1],'nonlinear_arith_subqueries':expected[2],'verifier_total':expected[3]},'checks':[]}
 targets=[(None,expected[3])]+[(x['name'],1) for x in specs]+[(x['name'],1+len(x['nonlinear_subquery_lines'])) for x in nlas]
 targets += [('lemma_pos',1)] if model=='ppr_walk' else [('theorem_graph_failure_dropped',1)]
 for name,count in targets:
  label='full' if name is None else name;log=SCRATCH/'logs'/model/(label+'.log');log.parent.mkdir(parents=True,exist_ok=True)
  cmd=[str(VERUS),str(dest/original.name),'--crate-type=lib','--num-threads','4','--triggers-mode','silent']
  if name:cmd+=['--verify-root','--verify-function',name]
  t=time.perf_counter();p=subprocess.run(cmd,cwd=dest,capture_output=True,text=True,timeout=120);elapsed=time.perf_counter()-t;text=p.stdout+p.stderr;log.write_text(text)
  match=re.search(r'verification results:: (\d+) verified, (\d+) errors',text);observed=[int(x) for x in match.groups()] if match else None
  row={'function':name,'expected_units':count,'observed':observed,'exit_code':p.returncode,'seconds':elapsed,'command':cmd,'log':str(log.relative_to(ROOT)),'ordinary_clean':p.returncode==0 and observed==[count,0] and 'Resource limit' not in text and 'rlimit' not in text.lower()}
  selected[model]['checks'].append(row);commands.append(row)
  assert row['ordinary_clean'],row
 assert sha(original)==sha(dest/original.name)
result={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'COUNT_ATTRIBUTION_CONFIRMED','product':'3eaa79cf77d3e0a879b2cced634cf2729d81499e','stable_model_source_files_scanned':len(files),'excluded_moving_models':sorted(SKIP),'candidate_files_inspected':[],'inventory':inventory,'selected':selected,'verifier':{'path':str(VERUS),'version':subprocess.check_output([str(VERUS),'--version'],text=True),'threads':4,'scope':'Unchanged stable source copied byte-for-byte; full baseline plus every recursive-spec function and every nonlinear-containing proof isolated. One nonlinear-free proof per model confirms body-only count. No active mutable11 replay.'},'scratch_runs':len(commands),'elapsed_s':time.perf_counter()-started,'iteration10_corrected_new_units':{'proof_declarations':108,'recursive_spec_checks':21,'nonlinear_arith_subqueries':17,'total':146,'unchanged_imported_units':45,'including_imports':191},'findings':['PPR103 is68proof bodies+18recursive spec checks+17nonlinear subqueries, not68+35recursive checks.','Fusion current11 is7proof bodies+2recursive specs(rank,score)+2nonlinear subqueries, not10 and not7+4recursive. Its existing NOTES/manifest total11 are correct.','Only PPR/fusion stable model sources contain explicit nonlinear_arith; moving fraction/vector excluded. None of these subqueries is an additional independent behavioral theorem.','Proof/control totals, source/model/manifest bytes, sealed archives and historical raw receipts remain unchanged. Root owns dated current-document/ledger erratum.']}
(HERE/'count-audit-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'stable_files':len(files),'scratch_runs':len(commands),'ppr':selected['ppr_walk']['totals'],'fusion':selected['fusion_ranking']['totals'],'elapsed':result['elapsed_s']}))
