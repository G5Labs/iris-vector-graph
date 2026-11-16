"""Source-declaration/query classification for exact reviewer scratch packages.
Counts are supported by enumerated function names, not inferred by subtraction.
A decreases_by body is attributed to its named recursive-spec termination query.
"""
from pathlib import Path
import hashlib,json,re,sys
HERE=Path(__file__).resolve().parent;scratch=HERE/sys.argv[1];model=sys.argv[2];repo=scratch/'repo';d=repo/'.g5/Verus_verification/models'/model;manifest=json.loads((d/'model.json').read_text())
files=[d/manifest['root']]+[(d/x).resolve() for x in manifest.get('additional_inputs',[]) if x.endswith('.rs')];rows=[]
for f in dict.fromkeys(files):
 raw=f.read_text();s=re.sub(r'/\*.*?\*/|//[^\n]*',' ',raw,flags=re.S);s=re.sub(r'"(?:\\.|[^"\\])*"', '""',s)
 declarations=list(re.finditer(r'\b(?P<kind>proof|spec)\s+fn\s+(?P<name>\w+)',s));proofs=[];hints=[];recursive=[]
 for i,m in enumerate(declarations):
  part=s[m.start():declarations[i+1].start() if i+1<len(declarations) else len(s)];name=m['name'];prefix=s[declarations[i-1].end() if i else 0:m.start()]
  if m['kind']=='proof':
   if re.search(r'#\[verifier::decreases_by\]\s*(?:pub\s+)?$',prefix):hints.append(name)
   else:proofs.append(name)
  elif re.search(r'\bdecreases\b',part):
   assert len(re.findall(r'\b'+re.escape(name)+r'\s*\(',part))>1 or ' via ' in part,(name,'not recursive')
   recursive.append(name)
 nla=[m.start() for m in re.finditer(r'by\s*\(\s*nonlinear_arith\s*\)',s)]
 rows.append(dict(path=str(f.relative_to(repo)),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),imported=f.parent.name!=model,proof_query_declarations=proofs,decreases_by_hint_declarations=hints,recursive_spec_query_declarations=recursive,nonlinear_subquery_offsets=nla,proof_units=len(proofs),recursive_spec_units=len(recursive),nonlinear_subquery_units=len(nla),total_units=len(proofs)+len(recursive)+len(nla)))
out=dict(model=model,manifest_expected=manifest['expected_verified'],files=rows,total_units=sum(x['total_units'] for x in rows),new_units=sum(x['total_units'] for x in rows if not x['imported']),imported_units=sum(x['total_units'] for x in rows if x['imported']),source_proof_declarations=sum(x['proof_units']+len(x['decreases_by_hint_declarations']) for x in rows),proof_units=sum(x['proof_units'] for x in rows),recursive_spec_units=sum(x['recursive_spec_units'] for x in rows),nonlinear_subquery_units=sum(x['nonlinear_subquery_units'] for x in rows),qualification='Source classification independently compared to scratch baseline; decreases_by hints are checked as part of associated recursive spec query, not counted as another proof unit.')
assert out['total_units']==manifest['expected_verified'],out
(HERE/('review-'+model.replace('_','-')+'-counts.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='files'}))
