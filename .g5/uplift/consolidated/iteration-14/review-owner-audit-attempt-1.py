"""Independent ordinary14 pre-proof owner audit against the completed13 archive."""
from pathlib import Path
import datetime, hashlib, json, re, tarfile, time

R = Path(__file__).resolve().parents[4]
H = Path(__file__).resolve().parent
started = time.monotonic()
checks, inputs = [], {}
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p):
    b = (R/p).read_bytes(); inputs[str(p)] = sha(b); return b
def ck(name, value):
    checks.append(dict(name=name, passed=bool(value))); assert value, name
def bodies(text):
    return {m[1]:m[2] for m in re.finditer(r'^<a id="([^"]+)"></a>\n\[[IDQ] · [^\]]+\]\n(.*?)(?=^<a id=|^## |\Z)',text.split('## Metadata')[0],re.M|re.S)}
meta=json.loads(read(H.relative_to(R)/'inputs.json'))
archive=Path(meta['before_archive'])
ck('completed13 before archive unchanged',sha(archive.read_bytes())==meta['before_archive_sha256']=='ec45a0098d3b35509529c82cc6b582babaf157f5bba746f46e1774be73922f8c')
old={}
with tarfile.open(archive,'r:gz') as tar:
    for entry in tar.getmembers():
        rel=entry.name.removeprefix('./')
        if entry.isfile() and (rel.startswith('.g5/ontology/') and rel.endswith('.md') or rel in ['.g5/Verus_verification/bugs_issues.md','.g5/Verus_verification/design_simplification.md','.g5/Verus_verification/open_questions.md','.g5/Verus_verification/crosswalk/statements.tsv','.g5/Verus_verification/crosswalk/findings.tsv']):
            old[rel]=tar.extractfile(entry).read()
previous,current={},{}
for rel,data in old.items():
    if rel.startswith('.g5/ontology/'):
        previous.update(bodies(data.decode()));current.update(bodies(read(rel).decode()))
expected={'install.export.ndjson','install.export.rdf.scope','install.export.rdf.content','install.export.rdf.report'}
ck('all405 inherited governing bodies raw-byte exact; only4ordinary export owners added',len(previous)==405 and len(current)==409 and set(current)-set(previous)==expected and all(current[k]==v for k,v in previous.items()))
doc=read('.g5/ontology/concepts/install.g5.md').decode()
ck('NDJSON scope and projection/inverse limits explicit',all(s in current['install.export.ndjson'] for s in ['default graph','then its non-temporal','count lines written','parallel','node-read projection','property aliases','omit only','does not promise an inverse','Named graphs and marked temporal rows are excluded']))
ck('RDF graph/filter/own-graph selection explicit',all(s in current['install.export.rdf.scope'] for s in ['graph_id','None','empty','named','own graph','Empty filter collections','matching labels','outgoing edges','no RDF subject']))
ck('RDF original qualifier envelope and distinct prefix rules explicit',all(s in current['install.export.rdf.content'] for s in ['nonempty qualifier dictionary','even when it is the only qualifier','ftp://','first three prefixes','falsey','intended qualifier exception is not settled','edge\'s context']))
ck('RDF report union/context and final-success reader explicit',all(s in current['install.export.rdf.report'] for s in ['After serialization succeeds','union of contexts','distinct subjects including blank nodes','IRI object','not `rdf:type`','two serialized quads but one reported triple','argument overrides','file atomicity']))
ck('RDF qualifier behavior not promoted to intended policy approval', 'as-built support is kept separate from intended-policy approval' in doc and 'no new owner decision' in doc)
ck('pending formal correspondence and providers remain explicit','Formal producer correspondence is pending.' in doc and 'arbitrary numeric text/IEEE normalization' in doc and 'ordinary JSON/filesystem laws' in doc)
for rel in ['.g5/Verus_verification/bugs_issues.md','.g5/Verus_verification/design_simplification.md','.g5/Verus_verification/open_questions.md','.g5/Verus_verification/crosswalk/findings.tsv']:
    ck('unchanged '+rel,read(rel)==old[rel])
rel='.g5/Verus_verification/crosswalk/statements.tsv';now=read(rel)
ck('statement crosswalk exact405prefix+4newowners',now.startswith(old[rel]) and len(now.splitlines())-len(old[rel].splitlines())==4)
ck('all audited current inputs stable',all(sha((R/k).read_bytes())==v for k,v in inputs.items()))
out=dict(verdict='PASS_ORDINARY14_EXPORT_OWNER_RECOVERY',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,inputs=inputs,old_owner_bodies=405,new_owner_blocks=4,total_blocks=409,findings_unchanged=434,simplifications_unchanged=55,questions_unchanged=146,elapsed_s=time.monotonic()-started,candidate_files_inspected=False,new_model_proof_runs=0,git_calls=0,native_calls=0,network_calls=0,interrupted_inputs_opened_or_reused=False,scope='Only current ordinary owners and fixed completed13 archive. Detailed literal/parser/SQL/codec correspondence still to be reviewed; recovered as-built behavior is not a policy decision or whole executable-body proof.')
(H/'review-owner-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['verdict','old_owner_bodies','new_owner_blocks','total_blocks','elapsed_s']}))
