"""W52: the IVF named index after its build (run-isolated continuation fixture; ordinary data)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W52_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def main():
    c = runtime.connect(); e = runtime.engine(c)
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    G, K, NAME = f"ivg{TAG}", f"ivf-k-{TAG}", f"ivf{TAG}"; p = f"iv{TAG}_"
    vecs = {"a": [1, 0, 0, 0], "b": [0, 1, 0, 0], "c": [0, 0, 1, 0], "d": [0, 0, 0, 1], "e": [1, 1, 0, 0]}

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    def top(q, k=3, name=NAME, nprobe=2):
        return [(n[len(p):] if n.startswith(p) else n, round(float(s), 3)) for n, s in e.ivf_search(name, q, k=k, nprobe=nprobe)]

    for n, v in vecs.items():
        e.create_node(p + n, graph=G); e.store_embedding(p + n, [float(x) for x in v], graph=G, model_key=K)
    case("V1_build", lambda: {"answer": e.ivf_build(NAME, nlist=2, graph=G, model_key=K), "info": e.ivf_info(NAME)})
    case("V2_exact", lambda: top([0, 0, 1, 0]))
    case("V3_insert", lambda: {"cell": e.ivf_insert(NAME, p + "f", [0.0, 0.0, 0.7, 0.7]), "top": top([0, 0, 0.7, 0.7]), "indexed": e.ivf_info(NAME).get("indexed")})
    case("V4_reinsert_same_node", lambda: {"cell": e.ivf_insert(NAME, p + "f", [0.7, 0.0, 0.0, 0.7]), "top_new": top([0.7, 0, 0, 0.7]), "top_old": top([0, 0, 0.7, 0.7]), "indexed": e.ivf_info(NAME).get("indexed")})
    case("V5_delete", lambda: {"existing": e.ivf_delete(NAME, p + "c"), "missing": e.ivf_delete(NAME, p + "zz"), "top": top([0, 0, 1, 0]), "indexed": e.ivf_info(NAME).get("indexed")})
    case("V6_never_built", lambda: {"search": e.ivf_search(f"nope{TAG}", [1, 0, 0, 0]), "info": e.ivf_info(f"nope{TAG}")})
    case("V7_insert_never_built", lambda: e.ivf_insert(f"nope{TAG}", p + "x", [1, 0, 0, 0]))
    case("V8_other_width", lambda: top([1, 0, 0]))
    case("V9_rebuild", lambda: {"answer": e.ivf_build(NAME, nlist=2, graph=G, model_key=K), "f_found": any(n == "f" for n, _ in top([0.7, 0, 0, 0.7], k=6)),
                                "c_found": any(n == "c" for n, _ in top([0, 0, 1, 0], k=6)), "indexed": e.ivf_info(NAME).get("indexed")})
    case("V10_drop", lambda: (e.ivf_drop(NAME), {"info": e.ivf_info(NAME), "search": e.ivf_search(NAME, [1, 0, 0, 0])})[1])
    dest = HERE / f"ivf-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
