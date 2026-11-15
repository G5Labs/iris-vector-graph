"""Disposable exact-file fixtures; production and active model inputs stay untouched."""
import hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
TOOL=REPO/'.g5/Verus_verification/tools/correspondence_gate.py';STAMP=HERE/'correspondence-inputs.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def main():
    old=json.loads(STAMP.read_text());scratch=Path(tempfile.mkdtemp(prefix='ivg-iter9-freshness-'));results=[]
    binding=sorted((REPO/'.g5/Verus_verification/results/weighted_paths').glob('*-binding/receipt.json'))[-1]
    package=json.loads(binding.read_text())['inputs']
    for rel in set(old['product'])|set(old['formal'])|set(package):
        if rel.startswith('external:'):continue
        p=scratch/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/rel,p)
    def run(label,rel=None,find=None,replace=None,added=None,formal=False,native=False):
        p=scratch/rel if rel else None;saved=p.read_bytes() if p and p.exists() else None
        if find is not None:
            s=p.read_text();assert s.count(find)==1,(label,s.count(find));p.write_text(s.replace(find,replace))
        if added is not None:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(added)
        r=subprocess.run([sys.executable,str(TOOL),'check',str(STAMP),'--root',str(scratch)],cwd=REPO,text=True,capture_output=True)
        v=json.loads(r.stdout);package_stale=[k for k,x in package.items() if sha(scratch/k)!=x]
        expected=('STALE_ALL' if formal else 'REUSABLE_INPUTS','STALE_ALL' if rel and not native else 'REUSABLE_INPUTS')
        assert (v['proof'],v['correspondence'])==expected,(label,v,expected)
        if native:assert package_stale==[rel],package_stale
        if rel is None:assert not package_stale
        results.append(dict(label=label,exit=r.returncode,**v,weighted_binding_stale_inputs=package_stale,
            evidence_scope='Global source/formal manifest and package evidence hashes are distinct; native fact file changes reopen its binding evidence even when source/solver inputs reuse.'))
        if p:
            if saved is None:p.unlink()
            else:p.write_bytes(saved)
    run('fresh')
    run('weighted-source','iris_src/src/Graph/KG/TraversalPaths.cls','Set tBound = (+maxHops > 0)','Set tBound = 0')
    run('bolt-source','iris_vector_graph/bolt_server.py','if not msg_bytes:','if msg_bytes is None:')
    run('weighted-formal','.g5/Verus_verification/models/weighted_paths/weighted_paths.rs','if skipped(s,e){Event::Continue','if false{Event::Continue',formal=True)
    run('bolt-formal','.g5/Verus_verification/models/bolt_stream/bolt_stream.rs','Read::Message(body)=>body.len()>0','Read::Message(body)=>true',formal=True)
    run('binding-code','.g5/Verus_verification/models/weighted_paths/binding.py','class SourcePort:','class AlteredPort:')
    run('binding-reassigned','.g5/Verus_verification/crosswalk/decision-links.tsv','weighted_paths.rs::theorem_backtrack_derives_path_and_cost','weighted_paths.rs::theorem_admitted_self_is_zero')
    run('new-writer','iris_vector_graph/new_weight_writer.py',added='def update_weight(conn, weight):\n    return conn.cursor().execute("UPDATE Graph_KG.rdf_edges SET qualifiers=?", [weight])\nWRITERS={"weight":update_weight}\n')
    run('native-evidence','.g5/uplift/consolidated/iteration-9/weighted-native.json','"verdict": "AGREES"','"verdict": "DISAGREES"',native=True)
    result=dict(scratch=str(scratch),controls=results,all_expected=True,active_inputs_mutated=False,
        weighted_binding_receipt=str(binding.relative_to(REPO)),source_manifest=str(STAMP.relative_to(REPO)))
    (HERE/'freshness-controls.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'controls':len(results),'all_expected':True,'scratch':str(scratch)}))
if __name__=='__main__':main()
