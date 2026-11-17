"""prov_window binding: on the run-isolated continuation fixture (ivg-cont-20261117-iris), whose default graph holds
more temporal edges than one QueryWindow string can carry (iteration 44's W50 load), fresh small edges are exported and
looked up through the actual prov_export and prov_as_dict; outcome classes compared with a port of prov_window.rs.
Mutations mirror the controls. Ordinary data; files under $PROV_FILES or /tmp."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("PW_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
FILES = Path(os.environ.get("PROV_FILES", "/tmp")) / f"prov-binding-{RUN}"
MUTS = ["read_streams", "as_dict_bounded", "exclusive_end"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def outcome(fn):
    try:
        r = fn(); return ("Answer", r)
    except RuntimeError as ex:
        return ("Raised" if "MAXSTRING" in str(ex) else "Other", None)


def main():
    t0 = time.time(); FILES.mkdir(parents=True, exist_ok=True); c = runtime.connect(); e = runtime.engine(c)
    s, A, P = f"pw{TAG}:s", f"pw{TAG}:A", f"PW{TAG}"
    t = 2_000_000_000 + int(TAG)
    e.create_edge_temporal(s, P, A, timestamp=t, weight=1.0)
    e.create_edge_temporal(s, P, A, timestamp=t + 10, weight=1.0)
    got = {}
    k, r = outcome(lambda: e.prov_export(str(FILES / "exact.ttl"), ts_start=t, ts_end=t))
    got["small_window_exact_bounds"] = [k, r["activities"] if r else None]
    k, r = outcome(lambda: e.prov_export(str(FILES / "both.ttl"), ts_start=t, ts_end=t + 10))
    got["small_window_both_ends"] = [k, r["activities"] if r else None]
    got["as_dict_with_large_history"] = outcome(lambda: e.prov_as_dict(f"{s}|{P}|{A}|{t}"))[0]
    got["export_all_time"] = outcome(lambda: e.prov_export(str(FILES / "all.ttl")))[0]
    c.close()

    def predict(m):
        cap_ok = lambda big: (not big) or m.get("read_streams")  # noqa: E731
        return {"small_window_exact_bounds": ["Answer", 1],
                "small_window_both_ends": ["Answer", 1 if m.get("exclusive_end") else 2],
                "as_dict_with_large_history": "Answer" if (cap_ok(True) or m.get("as_dict_bounded")) else "Raised",
                "export_all_time": "Answer" if cap_ok(True) else "Raised"}

    want = predict({})
    mism = [{"case": k_, "observed": got[k_], "expected": want[k_]} for k_ in want if got[k_] != want[k_]]
    sens = {mm: sum(1 for k_, v in predict({mm: True}).items() if v != got[k_]) for mm in MUTS}
    body = {"kind": "binding", "model": "prov_window", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()), "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "prov_window.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/_engine/prov.py", "iris_src/src/Graph/KG/TemporalIndex.cls"]}},
            "scope": "Actual prov_export and prov_as_dict on IRIS 2026.1 (pin 3eaa79cf) with a default graph of more than 40,000 temporal edges "
                     "(premise for the Raised cases). prov_export_from_cypher shares prov_as_dict's whole-history read (inspected, observed in W50 P6 "
                     "only before the large load)."}
    d = REPO / ".g5/Verus_verification/results/prov_window" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k_: body[k_] for k_ in ("verdict", "cases", "observed", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
