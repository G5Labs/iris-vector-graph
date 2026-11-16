"""Reusable read-only preservation and evidence check for this concrete audit."""
from pathlib import Path
import collections,csv,datetime,hashlib,json,os,re,subprocess
H=Path(__file__).resolve().parent;R=H.parents[3];V=R/'.g5/Verus_verification';checks=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ck(name,value,detail=None):
 checks.append(dict(name=name,passed=bool(value),detail=detail));assert value,(name,detail)
def ids(p):return re.findall(r'^<a id="([^"]+)"></a>\n### ',p.read_text(),re.M)
I=json.loads((H/'starting-inventory.json').read_text());P=json.loads((H/'reconciliation.json').read_text());start=json.loads((H/'start.json').read_text());O=json.loads((H/'ontology-start.json').read_text());Q=json.loads((H/'question-review.json').read_text())
ck('Git remains requested iteration13 seal',subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='eceb147d37720658e34b07f279cc267870fd393c')
for n in ['bugs_issues','design_simplification','open_questions']:
 raw=subprocess.check_output(['git','show','eceb147d:.g5/Verus_verification/'+n+'.md'],cwd=R)
 ck('starting register exact sealed bytes: '+n,raw==(H/'start'/f'{n}.md').read_bytes())
live=ids(V/'bugs_issues.md');removed=ids(H/'bugs-review.md');expected={x['id']for x in I['bugs_issues']}
ck('434 bug IDs conserved without duplicates or active/archive overlap',len(live)==153 and len(removed)==281 and len(set(live))==153 and len(set(removed))==281 and not(set(live)&set(removed))and set(live)|set(removed)==expected)
ck('stable archived navigation for every old bug link',set(re.findall(r'<span id="([^"]+)"', (V/'bugs_issues.md').read_text()))==set(removed))
for name,number in [('design_simplification',55),('open_questions',146)]:
 found=ids(V/f'{name}.md');ck('IDs retained exactly: '+name,len(found)==number and set(found)=={x['id']for x in I[name]})
bugtext=(V/'bugs_issues.md').read_text();evidence=re.findall(r'^Reproduced by: \*\*([^*]+)\*\*',bugtext,re.M)
ck('reproduction levels exactly match reviewed source',collections.Counter(evidence)=={'e2e reproduced':42,'partial reproduced':4,'outside active reproduction scope':107})
ck('54 simplification claims withdrawn plus one retired; zero active decisions','Decision: Open'not in(V/'design_simplification.md').read_text())
ck('121 policy questions open; no inferred new human decisions',len(re.findall(r'^Severity: .*Decision: Open',(V/'open_questions.md').read_text(),re.M))==121 and sum(x['status']=='settled existing authority'for x in Q)==9)
reg=json.loads((H/'regressions.json').read_text());ck('41 final real-provider caller contrasts and passing neighbors',len(reg)==41 and all(x['verdict']=='REPRODUCED_WITH_PASSING_NEIGHBOR'and'neighbor'in x['observation']for x in reg))
ck('42 original IDs have final native evidence',set(i for x in reg for i in x['ids'])=={x['id']for x in P['bugs']if x['repro_level']=='e2e reproduced'})
comp=json.loads((H/'components.json').read_text());ck('4 narrower witnesses retain explicit missing gates',len(comp)==4 and all(x['level']=='partial reproduced'and x['remaining_gate']for x in comp))
ck('60 pinned upstream authority tests passed','60 passed'in(H/'upstream-authority-tests.log').read_text())
ck('every starting bug has a test-discovery record',len(json.loads((H/'test-search.json').read_text()))==434)
# Meaning and stable kinds survive; only link destinations may move to the archive.
now={};metadata={}
for p in(R/'.g5/ontology').rglob('*.md'):
 s=p.read_text()
 for m in re.finditer(r'^<a id="([^"]+)"></a>\n\[([IDQ]) · [^\]]+\]\n(.*?)(?=^<a id=|^## |\Z)',s.split('## Metadata')[0],re.M|re.S):now[m[1]]=dict(path=p,kind=m[2],body=m[3].strip())
 for m in re.finditer(r'^### ([^\n]+)\n(.*?)(?=^### |\Z)',s.split('## Metadata')[-1],re.M|re.S):metadata[m[1]]=m[2]
def prose(s):return re.sub(r'\]\([^)]+\)','](<destination>)',s)
changed_links=[]
for k,x in O.items():
 ck('existing commitment meaning and kind preserved: '+k,k in now and now[k]['kind']==x['kind']and prose(now[k]['body'])==prose(x['body']))
 if now[k]['body']!=x['body']:changed_links.append(k)
ck('36 canonical owners added, no original commitment removed',len(now)==len(O)+36 and set(O)<=set(now))
ck('unfinished root navigation preserved byte-for-byte',(R/'.g5/ontology/root.g5.md').read_bytes()==(H/'start/ontology/root.g5.md').read_bytes())
for x in P['bugs']:
 if x['status'].startswith('active'):
  ck('active ordinary owner/evidence backlink: '+x['id'],bool(x['owners'])and all(x['id']in metadata.get(k,'')and'register-20261115/'in metadata.get(k,'')for k in x['owners']))
for x in Q:
 if x['status']in ['settled existing authority','open owner decision']and x['id']!='HD-0001':ck('canonical question source and assumption: '+x['id'],bool(x['owners'])and all(k in now and x['id']in metadata.get(k,'')for k in x['owners']))
# Preserve exact unfinished files except ontology metadata under this audit's authority.
kept=0
for rel,expected_sha in start['unfinished_hashes'].items():
 if rel.startswith(str(H.relative_to(R))):continue
 if rel.startswith('.g5/ontology/')and rel!='.g5/ontology/root.g5.md':continue
 p=R/rel;ck('unfinished file exact bytes: '+rel,p.is_file()and sha(p)==expected_sha);kept+=1
for rel,expected_sha in json.loads((H/'frozen-hashes.json').read_text()).items():ck('frozen archive/seal unchanged: '+Path(rel).name,sha(Path(rel))==expected_sha)
# Existing model/proof receipt bytes remain the seal's bytes; iteration14 additions are separately hash-protected above.
for prefix in ['iris_vector_graph','iris_src','api','tests','pyproject.toml','uv.lock','.g5/Verus_verification/models','.g5/Verus_verification/results','.g5/uplift/consolidated/iteration-13']:
 base='3eaa79cf'if not prefix.startswith('.g5/')else'eceb147d'
 cmd=['git','diff','--quiet',base,'--',prefix];p=subprocess.run(cmd,cwd=R);ck('unchanged tracked product/model/sealed evidence: '+prefix,p.returncode==0)
# Crosswalks conserve original source IDs and resolve their declared current canonical destinations.
for name in ['findings','questions','simplifications']:
 old=list(csv.DictReader((H/'start/crosswalk'/f'{name}.tsv').open(),delimiter='\t'));new=list(csv.DictReader((V/'crosswalk'/f'{name}.tsv').open(),delimiter='\t'))
 ck('source crosswalk IDs preserved: '+name,[(x['source_arm'],x['source_id'],x['canonical_id'])for x in old]==[(x['source_arm'],x['source_id'],x['canonical_id'])for x in new])
 for x in new:
  p=R/x['canonical_path'];ck('canonical crosswalk destination: '+name+':'+x['source_id'],p.is_file()and x['canonical_id']in ids(p))
# Check newly generated human-facing links, leaving exact-byte source snapshots and inherited historical links alone.
owned=[H/n for n in ['README.md','bugs-review.md','question-review.md','simplification-review.md']]
missing=[]
for p in owned:
 for dest in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  if '://'in dest or dest.startswith('#'):continue
  path,_,anchor=dest.partition('#');target=(p.parent/path).resolve()
  if not target.exists() and target != H/'verify.json':missing.append(dict(file=p.name,link=dest))
ck('audit report local link targets exist',not missing,missing)
# Reused receipt hashes are checked without executing a new proof campaign.
bindings=[]
for x in json.loads((H/'simplification-review.json').read_text()):
 for rec in x['existing_receipts']:
  p=R/rec['path'];j=json.loads(p.read_text())
  for rel,digest in j.get('inputs',{}).items():
   target=R/rel;bindings.append(dict(receipt=rec['path'],input=rel,current=target.is_file()and sha(target)==digest))
(H/'reused-proof-bindings.json').write_text(json.dumps(bindings,indent=2)+'\n')
# These receipts are historical, and reduction claims were withdrawn regardless; disclose any stale binding.
result=dict(verdict='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,check_count=len(checks),unfinished_files_exact=kept,preexisting_commitments=len(O),new_canonical_owners=36,body_link_destinations_changed=changed_links,historical_proof_inputs_checked=len(bindings),historical_proof_inputs_stale=[x for x in bindings if not x['current']],evidence_hashes={str(p.relative_to(R)):sha(p)for p in [H/'runtime.py',H/'runtime.json',H/'regressions.py',H/'regressions.json',H/'regressions-final.log',H/'components.py',H/'components.json',H/'embedded-component.json',H/'reconciliation.json']})
(H/'verify.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k]for k in ['verdict','check_count','unfinished_files_exact','preexisting_commitments','new_canonical_owners','body_link_destinations_changed','historical_proof_inputs_checked','historical_proof_inputs_stale']}))
