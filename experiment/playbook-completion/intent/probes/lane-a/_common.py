"""Shared helpers for intent lane A probes (namespace AUDITIA only).

Every probe:
- connects through tools/iris_conn.Conn("AUDITIA") (identity-checked against the dedicated container);
- builds engines on the pin's public API without calling initialize_schema (no class is ever compiled);
- turns compiled native plans off for its own process (Graph.KG.Cypher.Gen.Mode("off") is process-private), so
  native Cypher is interpreted and no plan class is generated;
- names its data with a per-probe prefix ("ia<HD>_...") and removes only that data;
- prints one JSON line per observation, then a final "VERDICT <pass|fail|expected-violation> <text>" line.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

from iris_conn import Conn  # noqa: E402

NS = "AUDITIA"


def conn() -> Conn:
    c = Conn(NS)
    assert c.namespace == NS
    c.call("Graph.KG.Cypher.Gen", "Mode", "off")
    return c


def engine(c: Conn, **kw):
    from iris_vector_graph.engine import IRISGraphEngine
    kw.setdefault("namespace", NS)
    return IRISGraphEngine(c.conn, **kw)


def obs(**kw) -> None:
    print(json.dumps(kw, default=str, sort_keys=True), flush=True)


def verdict(result: str, text: str) -> None:
    assert result in ("pass", "fail", "expected-violation", "incomplete", "blocked")
    print(f"VERDICT {result} {text}", flush=True)


def cleanup_graph(c: Conn, graph: str | None, id_prefix: str) -> None:
    """Remove probe rows by id prefix from the four graph tables (SQL), in every graph or one graph."""
    g = "" if graph is None else " AND graph_id = ?"
    args = () if graph is None else (graph,)
    for table, col in (("Graph_KG.rdf_edges", "s"), ("Graph_KG.rdf_edges", "o_id"), ("Graph_KG.rdf_props", "s"),
                       ("Graph_KG.rdf_labels", "s"), ("Graph_KG.nodes", "node_id")):
        try:
            c.sql(f"DELETE FROM {table} WHERE {col} %STARTSWITH ?{g}", id_prefix, *args)
        except Exception as e:  # noqa: BLE001
            obs(cleanup_error=f"{table}.{col}: {e}")


def dump_global(c: Conn, gname: str, *subs, _limit: int = 200000) -> dict:
    """Every defined node under gname(subs...) as {tuple(relative subscripts): value} (Native API $Order walk)."""
    out: dict = {}

    def walk(prefix: tuple) -> None:
        d = c.o.isDefined(gname, *subs, *prefix)
        if d in (1, 11):
            out[prefix] = c.o.get(gname, *subs, *prefix)
        if d in (10, 11):
            s = ""
            while True:
                s = c.o.nextSubscript(False, gname, *subs, *prefix, s)
                if s is None or s == "":
                    break
                walk(prefix + (s,))
                if len(out) > _limit:
                    raise RuntimeError("global too large to dump")

    walk(())
    return out


def restore_global(c: Conn, gname: str, saved: dict, *subs) -> None:
    """Kill gname(subs...) and write back exactly the nodes in saved (from dump_global)."""
    c.o.kill(gname, *subs)
    for rel, val in saved.items():
        c.o.set(val, gname, *subs, *rel)
