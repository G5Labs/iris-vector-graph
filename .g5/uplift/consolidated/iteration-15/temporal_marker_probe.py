"""W15-A native probe: one triple written unmarked, marked (temporal) or adopted, read by every export/Cypher reader.

Run-isolated fixture ivg-cloud-20261116-iris only (identity-checked by runtime.connect). Ordinary data only.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime  # noqa: E402

RUN = os.environ.get("W15_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))


def rows(c, sql, params=()):
    cur = c.cursor()
    try:
        cur.execute(sql, list(params))
        return [list(r) for r in cur.fetchall()]
    finally:
        cur.close()


def world(e, c, name, writes, graph=None):
    a, b = f"w15{RUN}{name}a", f"w15{RUN}{name}b"
    e.create_node(a, labels=["Person"], graph=graph)
    e.create_node(b, labels=["Person"], graph=graph)
    for w in writes:
        if w == "plain":
            e.create_edge(a, "KNOWS", b, graph=graph)
        elif w == "plain5":
            e.create_edge(a, "KNOWS", b, weight=5.0, graph=graph)
        elif w == "bulk":
            e.bulk_create_edges([{"source_id": a, "predicate": "KNOWS", "target_id": b}], graph=graph)
        elif w == "temporal":
            e.create_edge_temporal(a, "KNOWS", b, timestamp=1700000000, weight=1.5, graph=graph)
        elif w == "temporal1":
            e.create_edge_temporal(a, "KNOWS", b, timestamp=1700000000, weight=1.0, graph=graph)
        elif w == "temporal3":
            e.create_edge_temporal(a, "KNOWS", b, timestamp=1700000100, weight=3.0, graph=graph)
    raw = rows(c, "SELECT s, p, o_id, qualifiers, graph_id FROM Graph_KG.rdf_edges WHERE s = ?", [a])
    out = {"ids": [a, b], "graph": graph, "writes": writes, "raw_rows": raw}
    with tempfile.TemporaryDirectory() as d:
        nq = Path(d) / "x.nq"
        rep = e.export_rdf(str(nq), format="nquads", graph_id=None, node_ids=[a, b])
        out["rdf_report"] = {k: rep[k] for k in ("triples", "nodes", "edges")}
        out["rdf_lines"] = sorted(l for l in nq.read_text().splitlines() if l.strip())
        nd = Path(d) / "x.ndjson"
        counts = e.export_graph_ndjson(str(nd))
        mine = [json.loads(l) for l in nd.read_text().splitlines() if a in l or b in l]
        out["ndjson_lines"] = mine
        out["ndjson_edge_lines"] = sum(1 for m in mine if m["kind"] == "edge")
        out["ndjson_counts_total"] = counts
    gclause = f" WHERE a.id = '{a}'"
    q = f"MATCH (a)-[r:KNOWS]->(b){gclause} RETURN count(r) AS n"
    try:
        out["cypher_count"] = e.execute_cypher(q)["rows"]
    except Exception as x:  # record, do not hide
        out["cypher_count"] = f"ERROR {type(x).__name__}: {x}"
    q = f"MATCH (a)-[r:KNOWS]->(b){gclause} RETURN properties(r) AS p, r.temporal AS t, r.weight AS w"
    try:
        out["cypher_props"] = e.execute_cypher(q)["rows"]
    except Exception as x:
        out["cypher_props"] = f"ERROR {type(x).__name__}: {x}"
    return out


def main():
    c = runtime.connect()
    e = runtime.engine(c)
    res = {"run": RUN, "fixture": runtime.NAME, "port": runtime.PORT, "worlds": {}}
    for name, writes, graph in [("plain", ["plain"], None), ("marked", ["temporal"], None),
                                ("adopted", ["temporal", "plain"], None), ("named", ["temporal"], "g15"),
                                ("weight1", ["temporal1"], None), ("second", ["temporal", "temporal3"], None),
                                ("adopt5", ["temporal", "plain5"], None), ("adoptbulk", ["temporal", "bulk"], None),
                                ("plainfirst", ["plain5", "temporal"], None)]:
        try:
            res["worlds"][name] = world(e, c, name, writes, graph)
        except Exception as x:
            res["worlds"][name] = {"error": f"{type(x).__name__}: {x}"}
    c.close()
    out = Path(os.environ.get("W15_OUT", str(HERE))) / f"temporal-marker-observed-{RUN}.json"
    out.write_text(json.dumps(res, indent=2, default=str) + "\n")
    print(out)
    for k, w in res["worlds"].items():
        if "error" in w:
            print(k, w["error"]); continue
        print(k, "raw", [r[3] for r in w["raw_rows"]], "rdf", w["rdf_report"], "nd_edges", w["ndjson_edge_lines"],
              "cy", w["cypher_count"], w["cypher_props"])


if __name__ == "__main__":
    main()
