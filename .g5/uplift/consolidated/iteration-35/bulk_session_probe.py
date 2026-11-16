"""W41: bulk_load_session outside and inside a caller's transaction (run-isolated retest fixture only)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W41_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def main():
    import iris
    c = runtime.connect(); e = runtime.engine(c); o = runtime.connect(); O = runtime.engine(o); nat = iris.createIRIS(o)
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    def pend():
        st = O.status(); return {"pending_sync": getattr(st, "pending_sync", None)}
    def read(pfx, pred):
        r = O.execute_cypher(f"MATCH (a)-[r:{pred}]->(b) RETURN count(r)")
        return {"node": O.get_node(f"{pfx}a") is not None, "edges": (r.rows if hasattr(r, "rows") else r["rows"])[0][0],
                "kg": bool(nat.isDefined("^KG", "out", 0, f"{pfx}a", pred, f"{pfx}b")), **pend()}
    def session(pfx, pred):
        with e.bulk_load_session() as s:
            s.add_nodes([{"id": f"{pfx}{x}", "labels": ["BS"], "properties": {"p": 1}} for x in "abc"])
            s.add_edges([(f"{pfx}a", f"{pfx}b", pred), (f"{pfx}b", f"{pfx}c", pred)])
    def case(k, fn):
        try: out["cases"][k] = fn()
        except Exception: out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:300]
    out["cases"]["start"] = pend()
    def s1():
        p = f"bs{TAG}1"; session(p, "BS1R"); return read(p, "BS1R")
    case("S1_no_caller_txn", s1)
    def s2():
        p = f"bs{TAG}2"; cur = c.cursor(); cur.execute("START TRANSACTION"); session(p, "BS2R"); cur.execute("COMMIT")
        after = read(p, "BS2R"); e.sync(); return {"after_commit": after, "after_sync": pend()}
    case("S2_caller_txn_commit", s2)
    def s3():
        p = f"bs{TAG}3"; cur = c.cursor(); cur.execute("START TRANSACTION"); session(p, "BS3R"); cur.execute("ROLLBACK"); return read(p, "BS3R")
    case("S3_caller_txn_rollback", s3)
    case("S3_then_sync", lambda: (e.sync(), pend())[1])
    for x in (c, o): x.close()
    path = HERE / f"bulk-session-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, v in out["cases"].items(): print("==", k, json.dumps(v, default=str)[:500])
if __name__ == "__main__":
    main()
