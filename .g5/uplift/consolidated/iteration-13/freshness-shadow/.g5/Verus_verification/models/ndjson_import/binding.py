#!/usr/bin/env python3
"""Real importer -> real create_node -> real get_nodes, with storage/rowcount/CY_TYPED substituted.
Additional graph routing and temporal batch observations are not formal node-flow claims.
"""
from __future__ import annotations
import importlib.util
import inspect
import itertools
import json
import logging
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
import binding_common as bc
PIN_DIR=bc.import_pin()
spec=importlib.util.spec_from_file_location("node_binding",HERE.parent/"node_read/binding.py")
nr=importlib.util.module_from_spec(spec); spec.loader.exec_module(nr)
from iris_vector_graph._engine import snapshot
from iris_vector_graph.engine import IRISGraphEngine

class World:
    def __init__(self):
        self.eng,_=nr.writer({}); self.nodes={}; self.rows={}; self.calls=[]; self.batches=[]
        self.eng.create_node=self.create_node
        self.eng.create_edge=self.create_edge
        self.eng.bulk_create_edges_temporal=self.bulk_temporal
    def create_node(self,id,labels=None,properties=None,graph=None):
        self.calls.append(("node",id,graph))
        key=(graph or "",id); exists=key in self.nodes
        _,rows=nr.writer(properties or {},node_id=id,existing=exists,labels=labels,graph=graph)
        if not exists: self.nodes[key]=properties or {}; self.rows[key]=rows
        return not exists
    def create_edge(self,*args,**kw):
        self.calls.append(("edge",args,kw)); return False # legitimate duplicate response, still counted
    def bulk_temporal(self,batch):
        self.batches.append([dict(x) for x in batch]); return 0 # count is not the importer's count

def observe(lines,fn=None,**kw):
    world=World()
    with tempfile.NamedTemporaryFile(mode="w",suffix=".ndjson",dir=os.environ.get("RUN_DIR"),delete=False) as f:
        f.write("\n".join(lines)+"\n"); name=f.name
    try:
        try:
            answer=(fn or snapshot.SnapshotMixin.import_graph_ndjson)(world.eng,name,**kw); error=None
        except ValueError as ex: answer=None; error=type(ex).__name__
        return world,answer,error
    finally: os.unlink(name)

NODE=json.dumps({"kind":"node","id":"n","properties":{"v":29}})
SECOND=json.dumps({"type":"node","id":"n","props":{"v":"29"}})
UNKNOWN=json.dumps({"kind":"alien","type":"node","id":"x"})
WIDE=json.dumps({"kind":"node","id":"x"*257})
LINES=["", "{", "[]", UNKNOWN, '{"kind":"node"}',NODE,SECOND,WIDE]

def expected(lines):
    props={}; nodes=skipped=0; stopped=False
    for line in lines:
        if stopped: break
        if not line.strip(): continue
        if line in ("{","[]",UNKNOWN,'{"kind":"node"}'): skipped+=1; continue
        if line==WIDE: stopped=True; break
        value=29 if line==NODE else "29"
        props.setdefault("n",value); nodes+=1
    return props,None if stopped else {"nodes":nodes,"edges":0,"temporal_edges":0,"skipped":skipped},"ValueError" if stopped else None

def compare(fn=None, mutate_observation=False):
    mism=[]; n=0
    for size in range(3):
        for lines in itertools.product(LINES,repeat=size):
            w,ans,error=observe(lines,fn)
            if mutate_observation and n==0: ans={**ans,"skipped":ans["skipped"]+1}
            props,want,err=expected(lines)
            got={id:p.get("v") for (g,id),p in w.nodes.items()}
            n+=1
            if nr.typed(got)!=nr.typed(props) or ans!=want or error!=err:
                mism.append({"lines":lines,"answer":ans,"expected":want,"error":error,"want_error":err,"props":got})
    return n,mism

def main():
    n,mism=compare()
    src=textwrap.dedent(inspect.getsource(snapshot.SnapshotMixin.import_graph_ndjson))
    needle='if not kind and etype == "node":'
    assert src.count(needle)==1
    scope=dict(vars(snapshot)); exec(src.replace(needle,'if etype == "node":'),scope)
    _,mut=compare(scope["import_graph_ndjson"])
    # Cross-call journey: a duplicate line counts but cannot turn the first numeric value into text.
    w,answer,error=observe([UNKNOWN,NODE,SECOND])
    eng=w.eng
    got,_=nr.read(eng,w.rows[("","n")])
    assert nr.typed(got[0]["v"])==["int",29] and answer["nodes"]==2 and answer["skipped"]==1
    # Supplemental scope observations, no live graph/database execution.
    edge=json.dumps({"type":"rel","s":"a","p":"R","o":"b","graph":"line"})
    w,a,_=observe([edge],graph="")
    assert a["edges"]==1 and w.calls[-1][2]["graph"]==""
    temporal=json.dumps({"kind":"temporal_edge","source":"a","predicate":"R","target":"b","attrs":{"b":True}})
    w,a,_=observe([temporal]*3,batch_size=2,graph="named")
    assert a["temporal_edges"]==3 and [len(b) for b in w.batches]==[2,1]
    assert all(c[2] is None for c in w.calls) and w.batches[0][0]["attrs"]["b"]=="True"
    extras=["iris_vector_graph/_engine/snapshot.py"]
    pin=bc.pin_identity(PIN_DIR)
    for p in extras:
        want=subprocess.check_output(["git","-C",str(bc.REPO),"rev-parse",f"{bc.PIN}:{p}"],text=True).strip()
        have=subprocess.check_output(["git","hash-object",str(PIN_DIR/p)],text=True).strip()
        pin["files_equal_pin_blobs"][p]=have==want; pin["all_equal"] &= have==want
    _,changed=compare(mutate_observation=True)
    detection={"explicit_kind_ignored_mutant":bool(mut),"changed_counter":bool(changed)}
    verdict="AGREES" if not mism and all(detection.values()) and pin["all_equal"] else "DISAGREES"
    out=bc.write_receipt("ndjson_import",Path(__file__),{"verdict":verdict,"comparisons":n,"mismatches":mism[:20],
        "mismatch_count":len(mism),"detection":detection,"journey":got,"pin":pin,
        "substituted":"IRIS storage, transactions, rowcount responses and CY_TYPED; actual importer, writer and reader execute",
        "supplemental_only":["edge explicit default graph override","temporal default endpoints, 2+1 flush, attrs stringification"]})
    d=json.loads(out.read_text())
    for p in [nr.HERE/"binding.py"]+[bc.REPO/p for p in extras]: d["inputs"][str(p.relative_to(bc.REPO))]=bc.sha(p)
    out.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(f"ndjson_import: {verdict}, {n} sequences, {len(mism)} mismatches, controls {detection}; {out}")
    return 0 if verdict=="AGREES" else 1
if __name__=="__main__": raise SystemExit(main())
