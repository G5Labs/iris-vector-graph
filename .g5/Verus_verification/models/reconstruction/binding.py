"""Real Python named readers; SQL, revision IDs, meta and redaction guard substituted.
Expected count fold is a hand translation of reconstruction.rs, not a verified twin.
"""
import inspect,itertools,json,os,sys,tempfile,textwrap
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
import binding_common as bc
PIN_DIR=bc.import_pin()
import history_fixture as hf
from iris_vector_graph.ledger import replay as R


def rec(i,op,id="a",kind="node",value=None):
    return R.MutationRecord(i,1,op,kind,id,"k",None,value,None)


def expected(records,through,bound,stream):
    nodes={};rels={}
    for r in records:
        if not 1<=r.seq<=through:continue
        if r.op!="redacted" and r.entity_kind!="revision":
            target=nodes if r.entity_kind=="node" else rels
            if r.op in ("create_node","create_rel"):target[r.entity_id]={}
            elif r.op in ("delete_node","delete_rel"):target.pop(r.entity_id,None)
            elif r.op=="set_prop" and r.entity_id in nodes:nodes[r.entity_id][r.attr]=r.new or ""
        if not stream and bound is not None and len(nodes)+len(rels)>bound:return None
    return {"nodes":{k:dict(v) for k,v in nodes.items()},"rels":sorted(rels)}


def normalize(state):
    if isinstance(state,R.GraphState):return {"nodes":{id:n.props for id,n in state.nodes.items()},"rels":sorted(state.statements)}
    entities=list(state)
    return {"nodes":{id:n.props for kind,id,n in entities if kind=="node"},"rels":sorted(id for kind,id,n in entities if kind=="rel")}


def compare(fn=None,change=False):
    original=R.reconstruct
    if fn:R.reconstruct=fn
    mism=[];n=0
    choices=[("create_node","a","node",None),("create_node","b","node",None),
             ("delete_node","b","node",None),("set_prop","a","node","v"),
             ("create_rel","1","rel",'{"s":"a","p":"R","o":"b","graph":null}'),
             ("delete_rel","1","rel",None),("redacted","a","node",None),("redact","x","revision",None)]
    try:
        for size in range(4):
            for xs in itertools.product(choices,repeat=size):
                rs=[rec(i+1,*x) for i,x in enumerate(xs)]
                for through,b,stream in itertools.product([1,3],[0,1,2],[False,True]):
                    g=hf.ledger(rs,b)
                    try:got=normalize(g.reconstruct(str(through),stream=stream))
                    except R.ReconstructionTooLargeError:got=None
                    want=expected(rs,through,b or 250000,stream)
                    if change and n==0:got=None
                    if got!=want:mism.append({"xs":xs,"through":through,"b":b,"stream":stream,"got":got,"want":want})
                    n+=1
    finally:R.reconstruct=original
    return n,mism


def main():
    n,mism=compare()
    src=textwrap.dedent(inspect.getsource(R.reconstruct));scope=dict(vars(R))
    exec(src.replace("and not stream and", "and True and"),scope)
    _,mut=compare(scope["reconstruct"]);_,changed=compare(change=True)
    # Reachable committed history: first two nodes, then delete one. Peak is two;
    # final size is one. Export and stream agree on the surviving node.
    rs=[rec(1,"create_node","a"),rec(2,"create_node","b"),rec(3,"delete_node","b")]
    g=hf.ledger(rs,1)
    try:g.reconstruct("3");raise AssertionError("prefix limit missing")
    except R.ReconstructionTooLargeError as e:assert (e.bound,e.estimate)==(1,2)
    with tempfile.TemporaryDirectory(dir=os.environ["RUN_DIR"]) as d:
        p=Path(d)/"out.ndjson";summary=g.export_reconstruction("3",str(p));lines=[json.loads(x) for x in p.read_text().splitlines()]
    stream=normalize(g.reconstruct("3",stream=True))
    assert stream=={"nodes":{"a":{}},"rels":[]} and summary.nodes==1 and lines[0]["id"]=="a"
    # Eager fold: returning a stream has already consumed every record.
    consumed=[]
    def tracked():
        for r in rs:consumed.append(r.seq);yield r
    iterator=R.reconstruct(tracked(),1,True);assert consumed==[1,2,3]
    detection={"stream_guard_mutant":bool(mut),"changed_deciding_observation":bool(changed)}
    out=bc.write_receipt("reconstruction",Path(__file__),{"verdict":"AGREES" if not mism and all(detection.values()) else "DISAGREES",
        "comparisons":n,"mismatch_count":len(mism),"mismatches":mism[:5],"detection":detection,
        "pin":bc.pin_identity(PIN_DIR),"journey":{"ordinary_error":[1,2],"stream":stream,"export":lines,"eager_consumed":consumed},
        "domain":"all sequences length 0..3 from 8 record shapes; 2 named cutoffs x 3 raw bounds x 2 delivery modes; arbitrary pure-reader inputs, not all histories are ledger-producible",
        "substituted":"SQL record and revision/meta provider, redaction guard; actual Python selectors, paging, decoding, fold, stream and NDJSON writer execute"})
    data=json.loads(out.read_text());data['inputs'][str(Path(hf.__file__).relative_to(bc.REPO))]=bc.sha(Path(hf.__file__))
    data['inputs']['iris_vector_graph/ledger/export.py']=bc.sha(PIN_DIR/'iris_vector_graph/ledger/export.py')
    # Product input key uses a path whose bytes equal the exported immutable pin.
    assert data['inputs']['iris_vector_graph/ledger/export.py']==bc.sha(bc.REPO/'iris_vector_graph/ledger/export.py')
    out.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    print(f"reconstruction: {data['verdict']}; {n} comparisons, {len(mism)} mismatches; {detection}; {out}")
    return int(data['verdict']!='AGREES')
if __name__=='__main__':raise SystemExit(main())
