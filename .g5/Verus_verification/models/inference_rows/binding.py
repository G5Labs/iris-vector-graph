"""inference_rows binding: the W44 shapes in a fresh named graph on the run-isolated continuation fixture
(ivg-cont-20261117-iris), through the actual create_edge, materialize_inference and retract_inference, read back from
rdf_edges (row and marker) and ^KG; compared with a port of inference_rows.rs. Mutations mirror the controls."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("IR_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
SUB = "http://www.w3.org/2000/01/rdf-schema#subClassOf"; SUBP = "http://www.w3.org/2000/01/rdf-schema#subPropertyOf"
TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"; DOM = "http://www.w3.org/2000/01/rdf-schema#domain"
RNG = "http://www.w3.org/2000/01/rdf-schema#range"
RES = {SUB, SUBP, TYPE, DOM, RNG}
MUTS = ["create_marks_asserted", "derive_rdfs7", "derive_lifts_domain", "retract_everything", "materialize_overwrites"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---- port of inference_rows.rs; rows: {(s, p, o): inferred?} ----
def derives(rows, m):
    a = {t for t, inf in rows.items() if not inf}
    rel = lambda p: {(s, o) for s, q, o in a if q == p}  # noqa: E731
    def tc(r):
        return r | {(x, y) for x, b in r for b2, y in r if b == b2 and x != y}
    sc, sp = tc(rel(SUB)), tc(rel(SUBP))
    out = {(x, SUB, y) for x, y in sc} | {(x, SUBP, y) for x, y in sp}
    out |= {(x, TYPE, b) for x, q, c in a if q == TYPE for c2, b in sc if c2 == c}
    edges = [(s, q, o) for s, q, o in a if q not in RES]
    dom_types = {(s, TYPE, d) for p, q, d in a if q == DOM for s, q2, o in edges if q2 == p}
    out |= dom_types | {(o, TYPE, r) for p, q, r in a if q == RNG for s, q2, o in edges if q2 == p}
    if m.get("derive_rdfs7"):
        out |= {(x, q, y) for p, k, q in a if k == SUBP for x, q2, y in edges if q2 == p}
    if m.get("derive_lifts_domain"):
        out |= {(x, TYPE, f) for x, _, d in dom_types for d2, f in sc if d2 == d}
    return out


def materialize(rows, m):
    new = dict(rows)
    for t in derives(rows, m):
        if t not in rows or m.get("materialize_overwrites"):
            new[t] = True
    return new


def create_edge(rows, t, m):
    if t in rows and not m.get("create_marks_asserted"):
        return rows
    new = dict(rows); new[t] = False
    return new


def retract(rows, m):
    return {} if m.get("retract_everything") else {t: False for t, inf in rows.items() if not inf}


def main():
    import iris
    from iris_vector_graph._validate import graph_index_key
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c); nat = iris.createIRIS(c)
    G = f"irg{TAG}"; q = f"ir{TAG}_"
    N = lambda x: x if x in RES else q + x  # noqa: E731
    shapes = [("A", SUB, "B"), ("B", SUB, "C"), ("x", TYPE, "A"),          # I1 chain
              ("A3", SUB, "B3"), ("x3", TYPE, "A3"), ("x3", TYPE, "B3"),   # I3 asserted first
              ("A4", SUB, "B4"), ("x4", TYPE, "A4"),                       # I4 asserted after
              ("p", SUBP, "pq"), ("x7", "p", "y7"), ("p", DOM, "D"), ("p", RNG, "R"), ("D", SUB, "E")]  # I7, I8, I10
    later = ("x4", TYPE, "B4")
    for s, p, o in shapes + [later]:
        for n in (s, o):
            if not e.node_exists(N(n), graph=G):
                e.create_node(N(n), graph=G)
    for s, p, o in shapes:
        e.create_edge(N(s), N(p), N(o), graph=G)

    def observe():
        cur = c.cursor()
        cur.execute(f"SELECT s, p, o_id, qualifiers FROM {e._ivg_schema}.rdf_edges WHERE graph_id = ?", [G])
        rows = {(s, p, o): bool(qu and '"inferred"' in qu) for s, p, o, qu in cur.fetchall()}
        cur.close()
        gk = graph_index_key(G)
        kg = {t: bool(nat.isDefined("^KG", "out", gk, *t)) for t in rows}
        return rows, kg

    trace = {}
    a1 = e.materialize_inference(graph=G)["inferred"]; trace["after_materialize"] = observe()
    a2 = e.materialize_inference(graph=G)["inferred"]; trace["after_rerun"] = observe()
    created = e.create_edge(N(later[0]), N(later[1]), N(later[2]), graph=G); trace["after_assert"] = observe()
    a3 = e.retract_inference(graph=G); trace["after_retract"] = observe()
    gone = [t for t in trace["after_assert"][0] if t not in trace["after_retract"][0]]
    gk = graph_index_key(G)
    kg_gone = not any(nat.isDefined("^KG", "out", gk, *t) for t in gone)
    c.close()

    def predict(m):
        r0 = {(N(s), N(p), N(o)): False for s, p, o in shapes}
        r1 = materialize(r0, m); r2 = materialize(r1, m); r3 = create_edge(r2, (N(later[0]), N(later[1]), N(later[2])), m)
        r4 = retract(r3, m)
        return {"counts": [len(r1) - len(r0), len(r2) - len(r1), len(r3) - len(r4)],
                "created": (N(later[0]), N(later[1]), N(later[2])) not in r2 or bool(m.get("create_marks_asserted")),
                "after_materialize": r1, "after_rerun": r2, "after_assert": r3, "after_retract": r4}

    obs = {"counts": [a1, a2, a3], "created": created, **{k: v[0] for k, v in trace.items()}}
    kg_ok = all(trace[k][1][t] for k in trace for t in trace[k][0])  # every row's ^KG entry present

    def norm(d):
        return {k: (sorted([list(t) + [v] for t, v in d[k].items()]) if isinstance(d[k], dict) else d[k]) for k in d}

    want = norm(predict({})); got = norm(obs)
    mism = [{"case": k, "observed": got[k], "expected": want[k]} for k in want if got[k] != want[k]]
    sens = {}
    for mm in MUTS:
        pm = norm(predict({mm: True}))
        sens[mm] = sum(1 for k in pm if pm[k] != got[k])
    body = {"kind": "binding", "model": "inference_rows", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": RUN, "graph": G,
            "verdict": "AGREES" if not mism and kg_ok and kg_gone else "DISAGREES", "kg_entries_gone_for_retracted_rows": kg_gone, "cases": len(want), "mismatches": mism,
            "observed": got, "kg_entries_for_every_row": kg_ok, "rows_removed_by_retract": [list(t) for t in gone],
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "inference_rows.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/_engine/schema.py", "iris_vector_graph/_engine/nodes_edges.py"]}},
            "scope": "Actual create_edge, materialize_inference(graph=G) and retract_inference(graph=G) on IRIS 2026.1 (pin 3eaa79cf), "
                     "multigraph off, one fresh named graph per run, read back from rdf_edges (row and inferred marker) and ^KG. "
                     "Subclass chains of two links. OWL rules, the default graph (W44 observed it), multigraph mode and the ledger are not exercised."}
    d = REPO / ".g5/Verus_verification/results/inference_rows" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "kg_entries_for_every_row", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str)[:600])


if __name__ == "__main__":
    main()
