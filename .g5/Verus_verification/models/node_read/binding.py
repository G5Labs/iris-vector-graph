#!/usr/bin/env python3
"""Real create_node/prop_value -> substituted IRIS CY_TYPED -> real get_nodes/read_node_value.

The producer's *actual bound values* feed the reader; expected values come from the input contract.
No database, transaction, native executor or SQL-function execution is claimed.
"""
from __future__ import annotations
import itertools
import json
import math
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
logging.disable(logging.CRITICAL)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import binding_common as bc
PIN_DIR = bc.import_pin()
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph import prop_values as pv
from iris_vector_graph._engine import nodes_edges as ne

VALUES = [0, -7, 29, -(2**63), 2**63-1, -(2**63)-1, 2**63, 2**70,
          0.5, 5.0, -0.25, True, False, "29", "5", "0.5", "", "true", "false",
          "\x01N29", "\x01D5", "\x01Sx", "\x01Jtrue", "a", "[1,2]", {"x":1}, [1,"a"],
          float("inf"), float("-inf"), float("nan")]

def typed(v):
    if isinstance(v, dict): return {k: typed(x) for k,x in v.items()}
    if isinstance(v, list): return [typed(x) for x in v]
    return [type(v).__name__, v]

def provider(v, lose_double=False):
    """CY_TYPED's inspected numeric-tag/escape branches. Numeric spelling is substituted."""
    if type(v) is int: return "\x01N" + str(v)
    if type(v) is float: return ("\x01N" + str(int(v))) if lose_double and v.is_integer() else "\x01D" + repr(v)
    if isinstance(v,str) and v.startswith("\x01"): return "\x01S" + v
    return v

def expected(v):
    if isinstance(v,bool): return v
    if isinstance(v,int): return v if -(2**63) <= v <= 2**63-1 else str(v)
    if isinstance(v,float): return v if math.isfinite(v) else str(v)
    if isinstance(v,(list,dict)): return v
    if v in ("true","false"): return v == "true"
    if isinstance(v,str) and v.startswith(("[","{")):
        try: return json.loads(v)
        except ValueError: pass
    return v

def writer(props, node_id="n", existing=False, labels=None, graph=None):
    conn, cur = MagicMock(), MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = (4,)
    cur.fetchall.return_value = []
    cur.description, cur.rowcount = [], (0 if existing else 1)
    eng = IRISGraphEngine(conn, embedding_dimension=4)
    cur.execute.reset_mock(); cur.executemany.reset_mock()
    assert eng.create_node(node_id, properties=props, labels=labels, graph=graph) is (not existing)
    rows=[]
    for call in cur.executemany.call_args_list:
        sql = str(call.args[0])
        if "INSERT" not in sql or "rdf_props" not in sql: continue
        cols=sql.split("(",1)[1].split(")",1)[0].replace('"',"").replace(" ","").split(",")
        for data in call.args[1]:
            rec=dict(zip(cols,data)); rows.append((rec["s"],rec["key"],rec["val"]))
    return eng, rows

class Cursor:
    def __init__(self, props=(), labels=(), exists=("n",), lose_double=False):
        self.props,self.labels,self.exists,self.lose_double=props,labels,exists,lose_double
        self.calls=[]; self.rows=[]
    def execute(self,sql,params):
        assert params[0] == "", "this observation is deliberately one graph only"
        self.calls.append((sql,list(params)))
        ids=params[1:]
        if "rdf_labels" in sql: self.rows=[r for r in self.labels if r[0] in ids]
        elif "rdf_props" in sql:
            assert "CY_TYPED(val)" in sql
            self.rows=[(n,k,provider(v,self.lose_double)) for n,k,v in self.props if n in ids]
        elif ".nodes" in sql: self.rows=[(n,) for n in self.exists if n in ids]
        else: raise AssertionError(sql)
    def fetchall(self): return self.rows

def read(eng, rows, ids=("n",), **kw):
    cur=Cursor(rows,**kw)
    eng.conn=MagicMock(); eng.conn.cursor.return_value=cur
    return eng.get_nodes(list(ids)),cur

def compare(mutant=False, lose_double=False, mutate_observation=False):
    mism=[]
    for v in VALUES:
        with patch.object(ne,"prop_value",pv.prop_text if mutant else pv.prop_value):
            eng,rows=writer({"v":v})
        got,_=read(eng,rows,lose_double=lose_double)
        if mutate_observation and v == 29 and type(v) is int: got[0]["v"]="29"
        want=[{"id":"n","labels":[],"v":expected(v),"p_id":"n"}]
        if typed(got)!=typed(want): mism.append({"input":repr(v),"expected":typed(want),"got":typed(got)})
    return mism

def main():
    mism=compare(); n=len(VALUES)
    eng,_=writer({})
    # Both bare-node neighbors, every request sequence through length three, including repeats and missing IDs.
    for exists in ((),("n",)):
        for size in range(4):
            for ids in itertools.product(("n","missing"),repeat=size):
                got,_=read(eng,[],ids,exists=exists)
                want=[{"id":i,"labels":[]} for i in ids if i in exists]
                n+=1
                if got!=want: mism.append({"ids":ids,"exists":exists,"got":got,"want":want})
    # Native unit witness for a newly noticed alias collision, with both permitted SQL row orders.
    eng,rows=writer({"id":"stored-id","p_id":"user-value"})
    a,_=read(eng,rows); b,_=read(eng,list(reversed(rows)))
    witness={"forward":a,"reverse":b,"different":a!=b}
    assert a[0]["id"]==b[0]["id"]=="n" and a[0]["p_id"]=="user-value" and b[0]["p_id"]=="stored-id"
    detection={"legacy_numeric_writer":bool(compare(mutant=True)),"lost_D_tag":bool(compare(lose_double=True)),
               "changed_reader_type":bool(compare(mutate_observation=True))}
    ident=bc.pin_identity(PIN_DIR)
    verdict="AGREES" if not mism and all(detection.values()) and ident["all_equal"] else "DISAGREES"
    out=bc.write_receipt("node_read",Path(__file__),{"verdict":verdict,"comparisons":n,"mismatches":mism,
        "detection":detection,"alias_collision":witness,"pin":ident,
        "real":["create_node","prop_value","get_nodes","read_node_value","decode_typed_text"],
        "substituted":["IRIS storage, transactions and CY_TYPED numeric spelling/tag producer"],
        "scope":"numeric/boolean/text model plus supplemental JSON and nonfinite unit regressions; single graph only"})
    print(f"node_read: {verdict}, {n} comparisons; alias collision {witness['different']}; {out}")
    return 0 if verdict=="AGREES" else 1
if __name__=="__main__": raise SystemExit(main())
