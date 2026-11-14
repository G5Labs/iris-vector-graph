#!/usr/bin/env python3
"""Read-only inspection of AUDITCORE for the E-1 lane: which pin classes are compiled, the tables' indexes and
triggers, and what the E-1 probes' prefix holds (must be empty before and after)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from iris_conn import Conn, version

c = Conn("AUDITCORE")
out = {"engine": version(c), "pid": c.pid}
out["classes"] = [r[0] for r in c.sql("SELECT Name FROM %Dictionary.CompiledClass WHERE Name %STARTSWITH 'Graph.KG.' ORDER BY Name")]
for cls in ("Graph.KG.EdgeScan", "Graph.KG.Adjacency", "Graph.KG.GraphStores", "Graph.KG.GraphVerify", "Graph.KG.Eraser"):
    out.setdefault("methods", {})[cls] = [r[0] for r in c.sql("SELECT Name FROM %Dictionary.CompiledMethod WHERE parent = ? AND Name IN ('RegisterDefaultNode','AssertTemporalRow','RetractTemporalRows','VectorRouteGuard','VerifyGraph','EraseGraph')", cls)]
for t in ("nodes", "rdf_edges", "embedding_registry"):
    cls = "Graph.KG." + t
    out.setdefault("indexes", {})[t] = [list(map(str, r)) for r in c.sql("SELECT Name, Properties, TypeClass, _Unique FROM %Dictionary.CompiledIndex WHERE parent = ?", cls)]
    out.setdefault("triggers", {})[t] = [list(map(str, r)) for r in c.sql("SELECT Name, Event, Foreach FROM %Dictionary.CompiledTrigger WHERE parent = ?", cls)]
    out.setdefault("columns", {})[t] = [list(map(str, r)) for r in c.sql("SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='Graph_KG' AND TABLE_NAME=? ORDER BY ORDINAL_POSITION", t)]
    out.setdefault("rows", {})[t] = c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t}")[0][0]
out["prefix_rows"] = {
    "nodes": c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'env2'")[0][0],
    "edges": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'env2'")[0][0],
    "registry": c.sql("SELECT COUNT(*) FROM Graph_KG.embedding_registry WHERE graph_id %STARTSWITH 'env2'")[0][0],
}
out["indexed"] = str(c.call("Graph.KG.Adjacency", "Indexed"))
out["tlevel"] = int(c.o.getTLevel())
out["kg_default_out_env2"] = int(c.o.isDefined("^KG", "out", 0, "env2e1-e-s1"))
print(json.dumps(out, indent=1, default=str))
c.close()
