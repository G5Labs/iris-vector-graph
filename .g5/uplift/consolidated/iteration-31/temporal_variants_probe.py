"""W37: bulk_create_edges_temporal and delete_edge_temporal with the caller's autocommit off, then rollback; neighbors
with START TRANSACTION. Run-isolated retest fixture only."""
import json, os, sys, time, inspect
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W37_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
TS = 1_900_000_000
def main():
    import iris
    c = runtime.connect(); C = runtime.engine(c); o = runtime.connect(); O = runtime.engine(o); nat = iris.createIRIS(o)
    out = {"run": RUN, "fixture": runtime.NAME, "bulk_signature": str(inspect.signature(C.bulk_create_edges_temporal)),
           "delete_signature": str(inspect.signature(C.delete_edge_temporal)), "cases": {}}
    def read(a, p, b):
        r = O.execute_cypher(f"MATCH (x)-[r:{p}]->(y) RETURN count(r)")
        return {"window": len(O.get_edges_in_window(a, p, 0, 2 ** 31)), "cypher": (r.rows if hasattr(r, "rows") else r["rows"])[0][0],
                "kg_out": bool(nat.isDefined("^KG", "out", 0, a, p, b)), "node_a": O.get_node(a) is not None}
    def txn(mode, fn):
        cur = c.cursor()
        if mode == "off": c.setAutoCommit(False)
        else: cur.execute("START TRANSACTION")
        cur.execute("SELECT $TLEVEL"); t0 = int(cur.fetchone()[0])
        err = None
        try: fn()
        except Exception as x: err = f"{type(x).__name__}: {str(x)[:200]}"
        cur.execute("SELECT $TLEVEL"); t1 = int(cur.fetchone()[0])
        if mode == "off": c.rollback(); c.setAutoCommit(True)
        else: cur.execute("ROLLBACK")
        return {"tlevel_before": t0, "tlevel_after_call": t1, "error": err}
    for mode in ("off", "sql"):
        a, b, p = f"tv{TAG}{mode}a", f"tv{TAG}{mode}b", f"TV{TAG}{mode.upper()}"
        edges = [{"source": a, "predicate": p, "target": b, "timestamp": TS, "weight": 1.0},
                 {"source": a, "predicate": p, "target": b + "2", "timestamp": TS, "weight": 1.0}]
        t = txn(mode, lambda: C.bulk_create_edges_temporal(edges))
        out["cases"][f"V1_bulk_{mode}"] = {"txn": t, "read": read(a, p, b)}
        a2, b2, p2 = f"tv{TAG}{mode}da", f"tv{TAG}{mode}db", f"TVD{TAG}{mode.upper()}"
        O.create_edge_temporal(a2, p2, b2, timestamp=TS, weight=1.0)       # committed beforehand
        before = read(a2, p2, b2)
        t = txn(mode, lambda: C.delete_edge_temporal(a2, p2, b2, TS))
        out["cases"][f"V2_delete_{mode}"] = {"before": before, "txn": t, "read": read(a2, p2, b2)}
    for x in (c, o): x.close()
    path = HERE / f"temporal-variants-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    print(out["bulk_signature"]); print(out["delete_signature"])
    for k, v in out["cases"].items(): print("==", k, json.dumps(v))
if __name__ == "__main__":
    main()
