"""Module 10 live helpers (lane B, AUDITB). Run every script under `tools/locks.sh iris`."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import *  # noqa: F401,F403

def state(s):
    """Namespace facts module 10 depends on."""
    c = s.c
    out = {
        "ledger": str(c.call("Graph.KG.Ledger", "Meta")),
        "graphs_nodes": c.sql("SELECT graph_id, COUNT(*) FROM Graph_KG.nodes GROUP BY graph_id"),
        "graphs_edges": c.sql("SELECT graph_id, COUNT(*) FROM Graph_KG.rdf_edges GROUP BY graph_id"),
        "kg_version": gget(c, "__version", root="KG"),
        "nkg_meta": {k: gget(c, "$meta", k, root="NKG") for k in ("version", "builtFrom", "invalidated", "stale", "edgeCount")},
        "nkg_ni_first": None,
        "algocache_graphs": gsubs(c, "IVG.AlgoCache"),
    }
    try:
        it = c.o.iterator("NKG", "$NI")
        for k in it.subscripts():
            out["nkg_ni_first"] = k
            break
    except Exception as e:
        out["nkg_ni_first"] = repr(e)
    return out

def cleanup_b10(s, graphs=()):
    """Delete every b10_ node/edge in the default graph through the pin's API, erase own named graphs."""
    eng = s.eng
    ids = [r[0] for r in s.c.sql("SELECT node_id FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'b10_' AND graph_id = ''")]
    errs = []
    for g in graphs:
        try:
            eng.erase_graph(g) if hasattr(eng, "erase_graph") else s.c.call("Graph.KG.Eraser", "EraseGraph", g)
        except Exception as e:
            errs.append(f"erase {g}: {e}")
    for i in ids:
        try:
            eng.delete_node(i)
        except Exception as e:
            errs.append(f"delete {i}: {e}")
    left = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'b10_'")[0][0]
    lefte = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'b10_' OR o_id %STARTSWITH 'b10_'")[0][0]
    return {"deleted": len(ids), "errors": errs, "left_nodes": left, "left_edges": lefte}
