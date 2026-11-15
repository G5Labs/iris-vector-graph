"""Disposable exact-file copies; no product/active input mutation."""
import hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
TOOL=REPO/'.g5/Verus_verification/tools/correspondence_gate.py'
STAMP=HERE/'correspondence-inputs.json'
def main():
    subprocess.run([sys.executable,str(TOOL),'capture',str(STAMP)],cwd=REPO,check=True)
    old=json.loads(STAMP.read_text());scratch=Path(tempfile.mkdtemp(prefix='ivg-iter8-freshness-'));results=[]
    for section in ['product','formal']:
        for rel in old[section]:
            if rel.startswith('external:'):continue
            p=scratch/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/rel,p)
    def run(label,rel=None,find=None,replace=None,added=None,formal=False):
        p=scratch/rel if rel else None;saved=p.read_bytes() if p and p.exists() else None
        if find is not None:
            s=p.read_text();assert s.count(find)==1,(label,s.count(find));p.write_text(s.replace(find,replace))
        if added is not None:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(added)
        r=subprocess.run([sys.executable,str(TOOL),'check',str(STAMP),'--root',str(scratch)],cwd=REPO,text=True,capture_output=True)
        (HERE/(label+'.log')).write_text(r.stdout+r.stderr);v=json.loads(r.stdout)
        expected=('STALE_ALL' if formal else 'REUSABLE_INPUTS','STALE_ALL' if rel else 'REUSABLE_INPUTS')
        assert (v['proof'],v['correspondence'])==expected,(label,v,expected)
        assert r.returncode==int(bool(rel));results.append({'label':label,'exit':r.returncode,**v})
        if p:
            if saved is None:p.unlink()
            else:p.write_bytes(saved)
    run('fresh-inputs')
    run('product-only-task-owner','iris_src/src/Graph/KG/FHIRGraph.cls',"If pTask.TaskClass '= \"Graph.KG.FHIRGraphSyncTask\" {",'If 0 {')
    run('product-only-fallback-tail','iris_vector_graph/stores/iris_sql_store.py','            for edge in edges:\n                # Keyword form','            for edge in edges[1:]:\n                # Keyword form')
    run('formal-task-setting-changed','.g5/Verus_verification/models/fhir_tasks/fhir_tasks.rs','Some(if xs.len()>1{xs[1]}else{seq![]})','Some(if xs.len()>1{xs[1]}else{graph_key()})',formal=True)
    run('formal-import-changed','.g5/Verus_verification/models/temporal_restore/temporal_restore.rs','Number(n)=>Scalar::NumericText(n)','Number(n)=>Scalar::NumericText(n+1)',formal=True)
    run('binding-only-reassigned','.g5/Verus_verification/crosswalk/decision-links.tsv','fhir_tasks.rs::ownership','fhir_tasks.rs::caller_interval')
    run('newly-registered-writer','iris_vector_graph/new_task_registry_writer.py',added='def registry_writer(conn, graph, task):\n    return conn.cursor().execute("UPDATE Graph_KG.fhir_graphs SET task_id=? WHERE graph_id=?", [task, graph])\nWRITERS = {"task_registry": registry_writer}\n')
    (HERE/'freshness-controls.json').write_text(json.dumps({'scratch':str(scratch),'controls':results,'actual_product_mutated':False},indent=2)+'\n')
    print(json.dumps({'controls':len(results),'all_expected':True,'scratch':str(scratch)}))
if __name__=='__main__':main()
