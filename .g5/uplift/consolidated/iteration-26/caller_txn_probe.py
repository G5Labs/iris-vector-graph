"""W31: engine writes inside a caller's transaction, engine on the caller's connection (C) vs from_connect (F).

Run-isolated retest fixture only; fresh ids per run. Predictions frozen in caller-txn-PAIRS.md. Every reading is made
after the caller's transaction has ended, on a separate observer connection.
    cd $IVG_PIN_DIR && $RUN_DIR/venv/bin/python -B <repo>/.g5/uplift/consolidated/iteration-26/caller_txn_probe.py
"""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W31_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
TAG = RUN.replace("T", "").replace("Z", "")[-8:]
TS = 2_000_000_000


def engine_f():
    from iris_vector_graph.engine import IRISGraphEngine
    from tests import conftest as fx
    f = IRISGraphEngine.from_connect("127.0.0.1", runtime.PORT, "USER", "_SYSTEM", "SYS",
                                     embedding_dimension=768, native_cypher=False)
    if not fx.container_hostname_matches(fx.probe_instance_hostname(f.conn),
                                         fx.docker_container_hostname(runtime.NAME), fx.docker_container_id(runtime.NAME)):
        raise RuntimeError("from_connect reached another instance")
    return f


def main():
    import iris
    from iris_vector_graph.bulk_loader import BulkLoader
    c = runtime.connect(); C = runtime.engine(c)
    o = runtime.connect(); O = runtime.engine(o); nat = iris.createIRIS(o)
    F = engine_f()
    res = {"run": RUN, "fixture": runtime.NAME, "port": runtime.PORT, "product": runtime.PRODUCT, "cases": {}}

    def read(a, b, pred, ts=None):
        r = O.execute_cypher(f"MATCH (x {{id: $a}})-[r:{pred}]->(y) RETURN y.id", {"a": a})
        out = {"get_node_a": O.get_node(a) is not None, "get_node_b": O.get_node(b) is not None,
               "cypher_edge": [list(x) for x in (r.rows if hasattr(r, "rows") else r.get("rows", []))],
               "kg_out": bool(nat.isDefined("^KG", "out", 0, a, pred, b))}
        if ts is not None:
            w = O.get_edges_in_window(a, pred, 0, 2 ** 31)
            out["window"] = sorted((e["o"], e["ts"]) for e in w)
        return out

    def txn(eng, body, end):
        cur = eng.conn.cursor(); cur.execute("START TRANSACTION")
        info = {}
        try:
            info["body"] = body(eng)
        except Exception as x:
            info["raised"] = f"{type(x).__name__}: {str(x)[:200]}"
        cur.execute("SELECT $TLEVEL"); info["tlevel_before_end"] = int(cur.fetchone()[0])
        cur.execute(end); cur.close()
        return info

    def case(name, fn):
        try:
            res["cases"][name] = fn()
        except Exception:
            res["cases"][name] = {"exception": traceback.format_exc()[-1500:]}

    def ordinary(eng, label, end):
        a, b, p = f"w31{TAG}{label}a", f"w31{TAG}{label}b", f"W31{label.upper()}"
        def body(e):
            e.create_node(a, labels=["W31"]); e.create_node(b, labels=["W31"]); return e.create_edge(a, p, b)
        info = txn(eng, body, end)
        return {"txn": info, "read": read(a, b, p)}
    case("T1_C_ordinary_rollback", lambda: ordinary(C, "t1", "ROLLBACK"))
    case("T2_C_ordinary_commit", lambda: ordinary(C, "t2", "COMMIT"))
    case("T3_F_ordinary_rollback", lambda: ordinary(F, "t3", "ROLLBACK"))
    case("T3n_F_ordinary_commit", lambda: ordinary(F, "t3n", "COMMIT"))

    def temporal(eng, label, end):
        a, b, p = f"w31{TAG}{label}a", f"w31{TAG}{label}b", f"W31{label.upper()}"
        info = txn(eng, lambda e: e.create_edge_temporal(a, p, b, timestamp=TS, weight=2.0), end)
        return {"txn": info, "read": read(a, b, p, ts=True)}
    case("T4_C_temporal_rollback", lambda: temporal(C, "t4", "ROLLBACK"))
    case("T5_F_temporal_rollback", lambda: temporal(F, "t5", "ROLLBACK"))
    case("T6_F_temporal_commit", lambda: temporal(F, "t6", "COMMIT"))

    def loader_after_write():
        x, y = f"w31{TAG}t7x", f"w31{TAG}t7y"
        def body(e):
            e.create_node(x)
            try:
                BulkLoader(e.conn).load_nodes([(y, {"namespace": "W31"})], use_noindex=False)
                return "loaded"
            except Exception as err:
                return f"{type(err).__name__}: {str(err)[:200]}"
        info = txn(C, body, "ROLLBACK")
        return {"txn": info, "x": O.get_node(x) is not None, "y": O.get_node(y) is not None}
    case("T7_C_loader_after_write", loader_after_write)

    def loader_nothing_written():
        y = f"w31{TAG}t8y"
        info = txn(C, lambda e: (BulkLoader(e.conn).load_nodes([(y, {"namespace": "W31"})], use_noindex=False), "loaded")[1], "ROLLBACK")
        return {"txn": info, "y": O.get_node(y) is not None}
    case("T8_C_loader_nothing_written", loader_nothing_written)

    def purge(eng, label):
        a, b, p = f"w31{TAG}{label}a", f"w31{TAG}{label}b", f"W31{label.upper()}"
        O.create_edge_temporal(a, p, b, timestamp=1000, weight=1.0)          # committed beforehand
        before = read(a, b, p, ts=True)
        info = txn(eng, lambda e: e.purge_before(2000), "ROLLBACK")
        return {"before": before, "txn": info, "after": read(a, b, p, ts=True)}
    case("T9_C_purge_rollback", lambda: purge(C, "t9"))
    case("T10_F_purge_rollback", lambda: purge(F, "t10"))

    for x in (c, o, F.conn):
        try: x.close()
        except Exception: pass
    path = HERE / f"caller-txn-observed-{RUN}.json"
    path.write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(path)
    for k, v in res["cases"].items():
        print("==", k, json.dumps(v, default=str)[:700])


if __name__ == "__main__":
    main()
