#!/usr/bin/env python3
"""Module 01 lock plans, live on AUDITD (gate 3.5-lockplans).

    locks.sh iris python setup_probes.py OUT_DIR

initialize_schema takes no lock of its own (draft $RUN_DIR/lockplans/drafts/01.md section 0(a); footprints/01.json
review "none: two concurrent setups are not serialized"). Its one-time adjacency bootstrap is gated by an unlocked
check-then-act on ^Graph.KG.Meta("kg_built") (iris_vector_graph/schema.py:3329-3357): IsSet, then BuildKG (which ends
in BuildNKG under ^IVG.NKGBuild, TraversalBuild.cls:150, 293), then Set. A probe holding ^IVG.NKGBuild parks the first
setup inside BuildNKG, before its Set, so a second setup reaches the gate meanwhile.

  B (LP-01-2a): two initialize_schema runs on a namespace with edges and no kg_built mark. Oracle INS-B1.10 "The
    first setup that finds edges in the edge table builds the adjacency index from them. It does this once."
    (docs/ADMIN_GUIDE.md:370-374; status["kg_built"] is True only for the run that built).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lpcommon as L  # noqa: E402
import holdprobe as H  # noqa: E402

G = "lpb"
KEYS = ("kg_built", "nkg_built", "schema", "schema_recorded", "tables_created", "objectscript_failed", "warnings")


def setup_b(sd):
    for i in range(20):
        sd.e.create_edge(f"lpb|{i}", "R", f"lpb|{(i + 1) % 20}", graph=G)
    sd.c.conn.commit()
    out = {"kg_built_before_delete": str(sd.o.classMethodValue("Graph.KG.Meta", "IsSet", "kg_built")),
           "nkg_built_before_delete": str(sd.o.classMethodValue("Graph.KG.Meta", "IsSet", "nkg_built"))}
    sd.o.classMethodValue("Graph.KG.Meta", "Delete", "kg_built")
    sd.o.classMethodValue("Graph.KG.Meta", "Delete", "nkg_built")
    out["kg_built_after_delete"] = str(sd.o.classMethodValue("Graph.KG.Meta", "IsSet", "kg_built"))
    out["edges"] = int(sd.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ?", G)[0][0])
    return out


def setup_run(sd):
    st = sd.e.initialize_schema()
    st = st if isinstance(st, dict) else {}
    return json.dumps({k: (st.get(k) if not isinstance(st.get(k), (list, dict)) else str(st.get(k))[:200]) for k in KEYS},
                      default=str)


def after_b(sd):
    out = {"kg_built": str(sd.o.classMethodValue("Graph.KG.Meta", "IsSet", "kg_built")),
           "nkg_built": str(sd.o.classMethodValue("Graph.KG.Meta", "IsSet", "nkg_built")),
           "schema_record": H.gget(sd, "^IVG.Deploy", "schema")}
    try:
        out["verify_graph"] = str(sd.e.verify_graph(G))[:400]
    except Exception as ex:  # noqa: BLE001
        out["verify_graph"] = f"<{type(ex).__name__}: {str(ex)[:200]}>"
    return out


def both_parked(obs, sides, done):
    if done:
        return True
    st = [L.proc_state(obs.c, s.c.pid) for s in sides.values()]
    return all("LOCK" in (x.get("state") or "").upper() for x in st)


def probes():
    return [dict(name="B-two-setups-kg-built-gate", lock=("^IVG.NKGBuild", ()), hold=6.0, max_hold=120.0,
                 release_when=both_parked, setup=setup_b,
                 ops=[("X1", 0.0, setup_run, False), ("X2", 3.0, setup_run, False)], after=after_b,
                 expect="as built: X1 parks in BuildNKG before its Set of kg_built; X2 passes the unlocked gate, rebuilds "
                        "^KG and parks too; after the release both statuses say kg_built True (INS-B1.10: once)")]


def main() -> int:
    out = Path(sys.argv[1])
    c = L.conn()
    print("engine:", L.version(c), "namespace", c.namespace, flush=True)
    c.close()
    results = []
    for p in probes():
        r = H.run(**p)
        results.append(r)
        L.dump(out / f"{p['name']}.json", r)
        print(json.dumps({"probe": r["probe"], "ops": r.get("ops"), "returned_before_release": r.get("returned_before_release"),
                          "released_at_s": r.get("released_at_s"), "state_last": (r.get("state_while_held") or [None])[-1],
                          "after": r.get("after"),
                          "journal": {k: {"records": v["records"], "roots": v["roots_total"]} for k, v in r.get("journal", {}).items()}},
                         default=str)[:3500], flush=True)
    L.dump(out / "setup_probes.json", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
