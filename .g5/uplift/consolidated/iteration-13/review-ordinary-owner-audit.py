"""Read-only ordinary-owner preservation audit against the sealed12 before image; no Git."""
from pathlib import Path
import json,hashlib,tarfile,re,datetime,time
R=Path(__file__).resolve().parents[4];H=Path(__file__).resolve().parent;meta=json.loads((H/'inputs.json').read_text());checks=[];inputs={};start=time.monotonic()
def sha(x):return hashlib.sha256(x).hexdigest()
def ck(n,v):checks.append({'name':n,'passed':bool(v)});assert v,n
def read(rel):v=(R/rel).read_bytes();inputs[rel]=sha(v);return v.decode()
def bodies(s):return {m[1]:m[2].strip() for m in re.finditer(r'^<a id="([^"]+)"></a>\n\[[IDQ] · [^\]]+\]\n(.*?)(?=^<a id=|^## |\Z)',s.split('## Metadata')[0],re.M|re.S)}
archive=Path(meta['before_archive']);ck('unchanged sealed12 before archive',sha(archive.read_bytes())==meta['before_archive_sha256']);old={}
with tarfile.open(archive,'r:gz') as t:
 for m in t.getmembers():
  rel=m.name.removeprefix('./')
  if rel.startswith('.g5/ontology/') and rel.endswith('.md') and m.isfile():old[rel]=t.extractfile(m).read().decode()
 for rel in ['.g5/Verus_verification/bugs_issues.md','.g5/Verus_verification/design_simplification.md','.g5/Verus_verification/open_questions.md','.g5/Verus_verification/crosswalk/statements.tsv','.g5/Verus_verification/crosswalk/findings.tsv']:
  names=[n for n in t.getnames() if n.removeprefix('./')==rel];assert len(names)==1;old[rel]=t.extractfile(names[0]).read().decode()
a={};z={}
for rel,text in old.items():
 if rel.startswith('.g5/ontology/'):a.update(bodies(text));z.update(bodies(read(rel)))
ck('403 inherited owners retained plus two ordinary owners',len(a)==403 and len(z)==405 and set(z)-set(a)=={'install.status','query.aggregation'})
ck('all403 inherited governing bodies exact unchanged',all(z[k]==v for k,v in a.items()))
status=z['install.status'];agg=z['query.aggregation'];ck('status scope and partial errors explicit',all(s in status for s in ['every graph','ordinary count methods','distinct legacy or registered table','without a registry','unknown','completed counts']))
ck('aggregate producer and core neighbors explicit',all(s in agg for s in ['rows reaching its query stage','COUNT(*)','COUNT(value)','DISTINCT','Empty grouped input','one aggregate row','WITH','collection','ordering, skipping and limiting','declared return columns']))
for rel in ['.g5/Verus_verification/bugs_issues.md','.g5/Verus_verification/design_simplification.md','.g5/Verus_verification/open_questions.md','.g5/Verus_verification/crosswalk/findings.tsv']:ck('unchanged '+rel,old[rel]==read(rel))
rel='.g5/Verus_verification/crosswalk/statements.tsv';s=read(rel);ck('statement crosswalk prior exact prefix plus2ordinary rows',s.startswith(old[rel]) and len(s.splitlines())-len(old[rel].splitlines())==2)
for rel in ['docs/USER_GUIDE.md','docs/ADMIN_GUIDE.md','tests/unit/test_230_status_counts.py','tests/unit/test_460_r050_status_unknown.py','tests/unit/test_sum_column_typing.py','tests/unit/test_460_r308_collect_typed.py','tests/unit/test_empty_result_columns.py','tests/unit/test_order_limit_aggregate_scope.py']:read(rel)
out={'verdict':'PASS_ORDINARY_OWNER_PRESERVATION','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'inputs':inputs,'baseline':meta['last_verified_seal'],'elapsed_s':time.monotonic()-start,'scope':'Only fresh ordinary owner recovery. All inherited governing bodies/findings unchanged; no quarantined content opened/read/assessed/reused, no Git/native/network or shared writes. Formal metadata/roles remain pending frozen packages.'};(H/'review-ordinary-owner-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'verdict':out['verdict'],'checks':len(checks),'elapsed_s':out['elapsed_s']}))
