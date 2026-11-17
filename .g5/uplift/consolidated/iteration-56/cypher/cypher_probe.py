"""Iteration 56 (W2) probe: review 53-55 F2 (length of an unbound OPTIONAL path) and the percentile minors (answer type, the
p argument). Fixture ivg-cont-20261117-iris, USER, prefix i56c_<tag>_. Both engines: native_cypher off (SQL path) and on.
    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-56/cypher/cypher_probe.py)
"""
import json, logging, os, sys, time
logging.disable(logging.WARNING)
REPO=os.environ["IVG_REPO"]; sys.path.insert(0, REPO+"/.g5/uplift/consolidated/iteration-36")
import runtime
from iris_vector_graph.engine import IRISGraphEngine
c=runtime.connect(); e=runtime.engine(c); en=IRISGraphEngine(c, embedding_dimension=768, native_cypher=True)
T=time.strftime("%H%M%S"); P=f"i56c_{T}_"; A=f"I56CA{T}"; K=f"I56CK{T}"
for n in ("a1","a2","a3"): e.create_node(P+n, labels=[A], properties={"name":n})
e.create_edge(P+"a1",K,P+"a2"); e.create_edge(P+"a2",K,P+"a3")
def q(t,p=None,eng=e):
    try:
        r=eng.execute_cypher(t,p or {})
        if getattr(r,"error",None): return "err:"+str(r.error)[:150]
        return [[ (type(v).__name__, v) for v in row] for row in r.rows]
    except Exception as x: return f"exc:{type(x).__name__}:{str(x)[:150]}"
Q={
"fix1_un": f"MATCH (a:{A} {{name:'a3'}}) OPTIONAL MATCH p=(a)-[:{K}]->(b) RETURN length(p), p IS NULL, nodes(p), relationships(p)",
"fix1_m": f"MATCH (a:{A} {{name:'a1'}}) OPTIONAL MATCH p=(a)-[:{K}]->(b) RETURN length(p), p IS NULL, size(nodes(p)), size(relationships(p))",
"fix2_un": f"MATCH (a:{A} {{name:'a2'}}) OPTIONAL MATCH p=(a)-[:{K}]->(b)-[:{K}]->(c) RETURN length(p), p IS NULL",
"fix2_m": f"MATCH (a:{A} {{name:'a1'}}) OPTIONAL MATCH p=(a)-[:{K}]->(b)-[:{K}]->(c) RETURN length(p), p IS NULL",
"var_un": f"MATCH (a:{A} {{name:'a3'}}) OPTIONAL MATCH p=(a)-[:{K}*1..2]->(b) RETURN length(p)",
"var_m": f"MATCH (a:{A} {{name:'a1'}}) OPTIONAL MATCH p=(a)-[:{K}*1..2]->(b) RETURN length(p) ORDER BY length(p)",
"anchor_null": f"OPTIONAL MATCH (a:{A} {{name:'zz'}}) OPTIONAL MATCH p=(a)-[:{K}]->(b) RETURN length(p)",
"with_null": f"WITH null AS a OPTIONAL MATCH p=(a)-[:{K}]->(b) RETURN length(p)",
"lit_null": "RETURN length(null)",
"match_fixed": f"MATCH p=(a:{A} {{name:'a1'}})-[:{K}]->(b) RETURN length(p)",
"pct_int": "UNWIND [10,20,30,40] AS x RETURN percentileDisc(x,0.5), percentileCont(x,0.5)",
"pct_flt": "UNWIND [1.5,2.5] AS x RETURN percentileDisc(x,0.5), percentileCont(x,0.5)",
"min_int": "UNWIND [10,20] AS x RETURN min(x), max(x)",
}
out={k:{"sql":q(v),"native_on":q(v,eng=en)} for k,v in Q.items()}
out["pct_p_null"]=q("UNWIND [10,20,30] AS x RETURN percentileDisc(x,$p)",{"p":None})
out["pct_p_null_cont"]=q("UNWIND [10,20,30] AS x RETURN percentileCont(x,$p)",{"p":None})
out["pct_p_str"]=q("UNWIND [10,20,30] AS x RETURN percentileDisc(x,$p)",{"p":"0.5"})
out["pct_p_strx"]=q("UNWIND [10,20,30] AS x RETURN percentileDisc(x,$p)",{"p":"x"})
out["pct_p_num"]=q("UNWIND [10,20,30] AS x RETURN percentileDisc(x,$p)",{"p":0.5})
out["pct_p_bool"]=q("UNWIND [10,20,30] AS x RETURN percentileDisc(x,$p)",{"p":True})
out["pct_p_missing"]=q("UNWIND [10,20,30] AS x RETURN percentileDisc(x,$p)",{})
out["pct_lit_null"]=q("UNWIND [10,20,30] AS x RETURN percentileDisc(x,null)")
RUN=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); out["_run"]=RUN; out["_prefix"]=P; out["_queries"]=Q
from pathlib import Path
Path(REPO, ".g5/uplift/consolidated/iteration-56/cypher", f"cypher-observed-{RUN}.json").write_text(json.dumps(out, indent=1, default=str)+"\n")
for k,v in out.items(): print(k, str(v)[:200])
