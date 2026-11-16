"""W30: the standalone BulkLoader through engine and Cypher readers (run-isolated retest fixture only).

Every case uses fresh ids and labels stamped with the run id, so no earlier state is read. Predictions are frozen in
bulk-loader-PAIRS.md. Run from the pin directory with the pinned venv:
    $RUN_DIR/venv/bin/python -B .g5/uplift/consolidated/iteration-25/bulk_loader_probe.py
"""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime  # noqa: E402  (iteration-25 retest fixture)
RUN = os.environ.get("W30_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
TAG = RUN.replace("T", "").replace("Z", "")[-8:]


class FailLabels:
    """Connection wrapper: the first executemany into rdf_labels raises a non-duplicate error (injected fault)."""
    def __init__(self, conn):
        self._c, self.fired = conn, False
    def __getattr__(self, k):
        return getattr(self._c, k)
    def cursor(self):
        cur, outer = self._c.cursor(), self
        class Cur:
            def __getattr__(self, k):
                return getattr(cur, k)
            def executemany(self, sql, rows):
                if "rdf_labels" in sql and not outer.fired:
                    outer.fired = True
                    raise RuntimeError("injected: connection lost during label insert")
                return cur.executemany(sql, rows)
        return Cur()


def readers(e, a, b, label, graph=None):
    out = {}
    try:
        n = e.get_node(a, graph=graph) if graph is not None else e.get_node(a)
        out["get_node"] = None if n is None else {"labels": sorted(n.get("labels", [])), "props": {k: v for k, v in n.get("properties", n).items() if k != "labels"} if isinstance(n, dict) else n}
    except Exception as x:
        out["get_node"] = f"ERROR {type(x).__name__}: {str(x)[:160]}"
    for name, q, p in (("edge", "MATCH (x {id: $a})-[r]->(y) RETURN y.id", {"a": a}),
                       ("label_count", f"MATCH (x:{label}) RETURN count(x)", {}),
                       ("label_ids", f"MATCH (x:{label}) RETURN x.id ORDER BY x.id", {})):
        try:
            r = e.execute_cypher(q, p)
            out[name] = r.get("rows") if isinstance(r, dict) else r
        except Exception as x:
            out[name] = f"ERROR {type(x).__name__}: {str(x)[:160]}"
    return out


def main():
    from iris_vector_graph.bulk_loader import BulkLoader
    c = runtime.connect(); e = runtime.engine(c)
    res = {"run": RUN, "fixture": runtime.NAME, "port": runtime.PORT, "product": runtime.PRODUCT, "cases": {}}

    def case(name, fn):
        try:
            res["cases"][name] = fn()
        except Exception:
            res["cases"][name] = {"exception": traceback.format_exc()[-1500:]}

    def load(prefix, label, noindex, rebuild=False):
        a, b = f"w30{TAG}{prefix}a", f"w30{TAG}{prefix}b"
        L = BulkLoader(c)
        sn = L.load_nodes([(a, {"namespace": label, "p": 7}), (b, {"namespace": label, "p": 8})], use_noindex=noindex)
        se = L.load_edges([(a, "W30R", b, {"w": 1})], use_noindex=noindex)
        rb = L.rebuild_all_indices() if rebuild else None
        return {"stats_nodes": sn, "stats_edges": se, "rebuild": rb, "read": readers(e, a, b, label)}

    case("A1_noindex_no_rebuild", lambda: load("a1", f"W30A1{TAG}", True))
    case("A2_indexed", lambda: load("a2", f"W30A2{TAG}", False))
    case("A3_noindex_then_rebuild", lambda: load("a3", f"W30A3{TAG}", True, rebuild=True))
    # A1's ids re-read after A3's rebuild_all_indices rebuilt every index (a later rebuild repairs earlier loads)
    case("A1_after_A3_rebuild", lambda: readers(e, f"w30{TAG}a1a", f"w30{TAG}a1b", f"W30A1{TAG}"))

    def a7():
        import networkx as nx
        a, b, label = f"w30{TAG}a7a", f"w30{TAG}a7b", f"W30A7{TAG}"
        G = nx.DiGraph(); G.add_node(a, namespace=label, p=7); G.add_node(b, namespace=label, p=8); G.add_edge(a, b, predicate="W30R")
        st = BulkLoader(c).load_networkx(G)
        return {"stats": st, "read": readers(e, a, b, label)}
    case("A7_load_networkx", a7)

    def b1():
        a, b, label = f"w30{TAG}b1a", f"w30{TAG}b1b", f"W30B1{TAG}"
        rows = [(a, {"namespace": label, "p": 7}), (b, {"namespace": label, "p": 8})]
        fc = FailLabels(c); first = None
        try:
            BulkLoader(fc).load_nodes(rows, use_noindex=False)
        except Exception as x:
            first = f"{type(x).__name__}: {str(x)[:200]}"
        after_first = readers(e, a, b, label)
        second = BulkLoader(c).load_nodes(rows, use_noindex=False)
        return {"fault_fired": fc.fired, "first": first, "after_first": after_first, "second": second,
                "after_second": readers(e, a, b, label)}
    case("B1_interrupted_then_rerun", b1)

    def b2():
        a, b, label = f"w30{TAG}b2a", f"w30{TAG}b2b", f"W30B2{TAG}"
        rows = [(a, {"namespace": label, "p": 7}), (b, {"namespace": label, "p": 8})]
        first = BulkLoader(c).load_nodes(rows, use_noindex=False)
        second = BulkLoader(c).load_nodes(rows, use_noindex=False)
        return {"first": first, "second": second, "read": readers(e, a, b, label)}
    case("B2_complete_then_rerun", b2)

    def c1():
        x, label = f"w30{TAG}c1x", f"W30C1{TAG}"
        e.create_node(x, labels=[label], properties={"p": "default"})
        st = BulkLoader(c, graph="w30g").load_nodes([(x, {"namespace": label, "p": "w30g"})], use_noindex=False)
        return {"stats": st, "default": readers(e, x, x, label), "w30g": readers(e, x, x, label, graph="w30g")}
    case("C1_other_graph", c1)

    c.close()
    path = HERE / f"bulk-loader-observed-{RUN}.json"
    path.write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(path)
    for k, v in res["cases"].items():
        print("==", k); print(json.dumps(v, default=str)[:1200])


if __name__ == "__main__":
    main()
