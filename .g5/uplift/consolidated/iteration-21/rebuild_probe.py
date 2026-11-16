"""W25: rebuild_kg against the edge rows, read from ^KG directly (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W25_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
def main():
    import iris
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768); nat = iris.createIRIS(c)
    n = {k: f"rb{RUN}{k}" for k in "abcdz"}; R = f"RBR{RUN}"
    for k in "abdz": e.create_node(n[k], labels=["RB"])
    e.create_node(n["a"], labels=["RB"], graph="g21"); e.create_node(n["c"], labels=["RB"], graph="g21")
    e.create_edge(n["a"], R, n["b"]); e.create_edge(n["a"], R, n["c"], graph="g21")
    e.create_edge_temporal(n["a"], R, n["d"], timestamp=1700000000, weight=1.0)
    nat.set(1, "^KG", "out", 0, n["a"], R, n["z"])  # planted entry with no row
    entries = {"a->b key0": (0, "b"), "a->c key g21": ("g21", "c"), "a->d key0 (marked)": (0, "d"), "planted a->z key0": (0, "z")}
    def read(): return {k: bool(nat.isDefined("^KG", "out", g, n["a"], R, n[t])) for k, (g, t) in entries.items()}
    before = read(); t0 = time.monotonic(); ok = e.rebuild_kg(); el = time.monotonic() - t0; after = read()
    c.close()
    out = {"run": RUN, "fixture": runtime.NAME, "before": before, "rebuild_returned": ok, "rebuild_s": el, "after": after}
    path = HERE / f"rebuild-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    print("before", before); print("rebuild", ok, round(el, 1), "s"); print("after ", after)
if __name__ == "__main__":
    main()
