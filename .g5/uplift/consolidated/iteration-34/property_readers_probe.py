"""W40: Python property readers over API-written typed values (run-isolated retest fixture only)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W40_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def main():
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    key = f"pk{TAG}"; L = f"PL{TAG}"; g = f"prg{TAG}"; gn = f"prgn{TAG}"
    vals = {"i": 7, "f": 7.5, "s": "7", "b": True}
    for k, v in vals.items(): e.create_node(f"pr{TAG}{k}", labels=[L], properties={key: v})
    e.create_node(f"pr{TAG}g", labels=[L], properties={key: 7}, graph=g)
    e.create_node(f"pr{TAG}h", graph=gn)                                   # a named graph with nodes only
    def case(k, fn):
        try: out["cases"][k] = fn()
        except Exception: out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:300]
    ids = lambda xs: sorted(x if isinstance(x, str) else x.get("id") for x in xs)
    case("R1_nodes_by_property_7", lambda: ids(e.get_nodes_by_property(key, "7")))
    case("R1b_nodes_by_property_int7", lambda: ids(e.get_nodes_by_property(key, 7)))
    case("R1c_nodes_by_property_true", lambda: {v: ids(e.get_nodes_by_property(key, v)) for v in ("true", "True", "1")})
    case("R1d_nodes_by_property_7.5", lambda: ids(e.get_nodes_by_property(key, "7.5")))
    case("R2_ids_by_property_7", lambda: sorted(e.get_node_ids_by_property(key, "7")))
    case("R3_property_values", lambda: sorted([[type(v).__name__, v] for v in e.get_property_values(key)], key=str))
    case("R4_property_pairs", lambda: sorted([[s, type(v).__name__, v] for s, v in e.get_property_pairs(key)], key=str))
    case("R5_node_properties_vs_get_node", lambda: {k: {"props": e.get_node_properties(f"pr{TAG}{k}"), "get_node": e.get_node(f"pr{TAG}{k}")} for k in vals})
    case("R6_nodes_by_label", lambda: sorted([[n.get("id"), type(n.get(key, n.get("properties", {}).get(key) if isinstance(n.get("properties"), dict) else None)).__name__] for n in e.get_nodes_by_label(L)], key=str))
    case("R6_raw_first", lambda: e.get_nodes_by_label(L)[:1])
    case("R7_scope", lambda: ids(e.get_nodes_by_property(key)))
    case("R8_nodes_exist", lambda: sorted(e.nodes_exist([f"pr{TAG}i", f"pr{TAG}g", f"pr{TAG}h", f"pr{TAG}none"])))
    case("R9_list_graphs", lambda: {"g_listed": g in e.list_graphs(), "gn_listed": gn in e.list_graphs()})
    c.close(); path = HERE / f"property-readers-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, v in out["cases"].items(): print("==", k, json.dumps(v, default=str)[:600])
if __name__ == "__main__":
    main()
