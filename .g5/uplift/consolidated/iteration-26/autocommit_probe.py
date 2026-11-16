"""W31 T11-T13: create_edge_temporal with the caller's driver autocommit off and nothing written, then rollback;
neighbor with SQL START TRANSACTION. Run-isolated retest fixture only; readers on a separate connection."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W31_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def main():
    import iris
    from iris_vector_graph.engine import IRISGraphEngine
    from tests import conftest as fx
    c = runtime.connect(); C = runtime.engine(c); o = runtime.connect(); O = runtime.engine(o); nat = iris.createIRIS(o)
    F = IRISGraphEngine.from_connect("127.0.0.1", runtime.PORT, "USER", "_SYSTEM", "SYS", embedding_dimension=768, native_cypher=False)
    assert fx.container_hostname_matches(fx.probe_instance_hostname(F.conn), fx.docker_container_hostname(runtime.NAME), fx.docker_container_id(runtime.NAME))
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    for name, eng, mode, end in [("T11_C_autocommit_off_rollback", C, "off", "rollback"), ("T12_F_autocommit_off_rollback", F, "off", "rollback"),
                                 ("T13_C_start_transaction_rollback", C, "sql", "rollback"), ("T11n_C_autocommit_off_commit", C, "off", "commit")]:
        a, b, p = f"ac{TAG}{name[:4]}a", f"ac{TAG}{name[:4]}b", f"AC{TAG}{name[:3]}"
        cur = eng.conn.cursor()
        if mode == "off": eng.conn.setAutoCommit(False)
        else: cur.execute("START TRANSACTION")
        cur.execute("SELECT $TLEVEL"); t0 = int(cur.fetchone()[0])
        eng.create_edge_temporal(a, p, b, timestamp=2_000_000_000, weight=2.0)
        cur.execute("SELECT $TLEVEL"); t1 = int(cur.fetchone()[0])
        if mode == "off": (eng.conn.rollback if end == "rollback" else eng.conn.commit)(); eng.conn.setAutoCommit(True)
        else: cur.execute("ROLLBACK")
        r = O.execute_cypher(f"MATCH (x)-[r:{p}]->(y) RETURN count(r)")
        out["cases"][name] = {"tlevel_before_call": t0, "tlevel_after_call": t1,
            "window": len(O.get_edges_in_window(a, p, 0, 2 ** 31)), "cypher_edges": (r.rows if hasattr(r, "rows") else r["rows"])[0][0],
            "kg_out": bool(nat.isDefined("^KG", "out", 0, a, p, b)), "kg_tout": bool(nat.isDefined("^KG", "tout", 0, 2_000_000_000, a, p, b)),
            "node_a": O.get_node(a) is not None, "node_b": O.get_node(b) is not None}
        print(name, out["cases"][name])
    path = HERE / f"autocommit-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1) + "\n"); print(path)
if __name__ == "__main__":
    main()
