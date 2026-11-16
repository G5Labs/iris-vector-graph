"""W36: BulkLoader in namespace W37 whose IVG Schema is Kg2 (bug-plt-012); neighbor in USER. Run-isolated fixture only."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W36_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def connect(ns):
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=ns, username="_SYSTEM", password="SYS")
    assert fx.container_hostname_matches(fx.probe_instance_hostname(c), fx.docker_container_hostname(runtime.NAME), fx.docker_container_id(runtime.NAME))
    return c
def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.bulk_loader import BulkLoader
    out = {"run": RUN, "fixture": runtime.NAME, "steps": {}}
    def step(k, fn):
        try: out["steps"][k] = fn()
        except Exception: out["steps"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]
    c = connect("W37")
    def setup():
        e0 = IRISGraphEngine(c, embedding_dimension=768, schema_prefix="Kg2", native_cypher=False)
        st = e0.initialize_schema()
        return {k: st.get(k) for k in ("schema", "objectscript_failed", "warnings")}
    step("setup", setup)
    e = IRISGraphEngine(c, embedding_dimension=768, schema_prefix="Kg2", native_cypher=False)
    def tables():
        cur = c.cursor(); cur.execute("SELECT TABLE_SCHEMA, COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA IN ('Graph_KG','Kg2') GROUP BY TABLE_SCHEMA"); r = cur.fetchall(); cur.close(); return [list(x) for x in r]
    step("tables", tables)
    def read(n):
        x = e.get_node(n); return None if x is None else {"labels": x.get("labels"), "p": x.get("p")}
    rows = lambda p: [(f"w36{TAG}{p}a", {"namespace": "W36", "p": 1})]
    step("S1_load_default_schema", lambda: BulkLoader(c).load_nodes(rows("s1"), use_noindex=False))
    step("S1_read", lambda: read(f"w36{TAG}s1a"))
    step("S2_load_kg2_indexed", lambda: BulkLoader(c, schema="Kg2").load_nodes(rows("s2"), use_noindex=False))
    step("S2_read", lambda: read(f"w36{TAG}s2a"))
    step("S3_load_kg2_noindex", lambda: BulkLoader(c, schema="Kg2").load_nodes(rows("s3")))
    step("S3_read_before_rebuild", lambda: read(f"w36{TAG}s3a"))
    step("S3_rebuild", lambda: BulkLoader(c, schema="Kg2").rebuild_all_indices())
    step("S3_read_after_rebuild", lambda: read(f"w36{TAG}s3a"))
    def kg2_rebuild_via_engine():
        r = e.execute_cypher("MATCH (n:W36) RETURN count(n)"); return (r.rows if hasattr(r, "rows") else r["rows"])
    step("S3_cypher_count", kg2_rebuild_via_engine)
    c.close()
    u = runtime.connect(); eu = runtime.engine(u)
    step("S4_user_load_noindex", lambda: BulkLoader(u).load_nodes([(f"w36{TAG}s4a", {"namespace": "W36", "p": 1})]))
    step("S4_rebuild", lambda: BulkLoader(u).rebuild_all_indices())
    step("S4_read", lambda: (lambda x: None if x is None else {"labels": x.get("labels"), "p": x.get("p")})(eu.get_node(f"w36{TAG}s4a")))
    u.close()
    path = HERE / f"schema-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, v in out["steps"].items(): print("==", k, json.dumps(v, default=str)[:400])
if __name__ == "__main__":
    main()
