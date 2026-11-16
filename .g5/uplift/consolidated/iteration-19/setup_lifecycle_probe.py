"""W21: dry run / real run / dry run / real run of initialize_schema on the fresh namespace W21 of the run-isolated fixture.

Snapshot after each step: Graph_KG tables with row counts, Graph_KG routines, compiled Graph.KG.* classes, and
^IVG.Deploy("schema"). The connection is identity-checked against the fixture container as in iteration-15/runtime.py.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402  (pin on sys.path, fixture name/port)

RUN = os.environ.get("W21_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
NS = "W21"


def connect():
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=NS, username="_SYSTEM", password="SYS")
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c), fx.docker_container_hostname(runtime.NAME),
                                         fx.docker_container_id(runtime.NAME)):
        c.close()
        raise RuntimeError("fixture identity mismatch")
    return c


def snapshot(c):
    import iris
    cur = c.cursor()
    cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'Graph_KG' ORDER BY TABLE_NAME")
    tables = [r[0] for r in cur.fetchall()]
    counts = {}
    for t in tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM Graph_KG."{t}"')
            counts[t] = cur.fetchone()[0]
        except Exception as x:
            counts[t] = f"ERROR {type(x).__name__}"
    cur.execute("SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA = 'Graph_KG' ORDER BY ROUTINE_NAME")
    routines = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT COUNT(*) FROM %Dictionary.CompiledClass WHERE Name %STARTSWITH 'Graph.KG.'")
    classes = cur.fetchone()[0]
    cur.close()
    native = iris.createIRIS(c)
    record = native.get("^IVG.Deploy", "schema") if native.isDefined("^IVG.Deploy", "schema") else None
    return {"tables": counts, "routines": routines, "compiled_graph_kg_classes": classes, "schema_record": record}


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    out = {"run": RUN, "fixture": runtime.NAME, "namespace": NS, "steps": []}
    c = connect()
    out["steps"].append({"step": "0 before", "snapshot": snapshot(c)})
    steps = [] if os.environ.get("W21_RESUME") == "1" else [("1 dry run", True), ("2 real run", False), ("3 dry run again", True), ("4 real run again", False)]
    for label, dry in steps:
        e = IRISGraphEngine(c, embedding_dimension=768)
        t0 = time.monotonic()
        try:
            report = e.initialize_schema(dry_run=dry)
            err = None
        except Exception as x:
            report, err = None, f"{type(x).__name__}: {x}"
        out["steps"].append({"step": label, "dry_run": dry, "elapsed_s": time.monotonic() - t0, "error": err,
                             "report": report, "snapshot": snapshot(c)})
    if os.environ.get("W21_RESUME") == "1":
        import iris
        iris.createIRIS(c).kill("^IVG.Deploy", "schema")
        out["steps"].append({"step": "5a record removed", "snapshot": snapshot(c)})
        for label, dry in [("5 dry run after removal", True), ("6 real run after removal", False)]:
            e = IRISGraphEngine(c, embedding_dimension=768)
            try:
                report, err = e.initialize_schema(dry_run=dry), None
            except Exception as x:
                report, err = None, f"{type(x).__name__}: {x}"
            out["steps"].append({"step": label, "dry_run": dry, "error": err, "report": report, "snapshot": snapshot(c)})
        try:
            e = IRISGraphEngine(c, embedding_dimension=768, schema_prefix="W21Other")
            report, err = e.initialize_schema(), None
        except Exception as x:
            report, err = None, f"{type(x).__name__}: {x}"
        out["steps"].append({"step": "7 other schema engine", "error": err, "report": report, "snapshot": snapshot(c)})
    c.close()
    path = HERE / f"setup-lifecycle-observed-{RUN}.json"
    path.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(path)
    prev = None
    for s in out["steps"]:
        snap = s["snapshot"]
        rep = s.get("report") or {}
        print(s["step"], "| tables", len(snap["tables"]), "rows", sum(v for v in snap["tables"].values() if isinstance(v, int)),
              "| routines", len(snap["routines"]), "| classes", snap["compiled_graph_kg_classes"], "| record", snap["schema_record"],
              "| report schema_recorded", rep.get("schema_recorded"), "| error", s.get("error"),
              "| same as previous" if prev == snap else "")
        prev = snap


if __name__ == "__main__":
    main()
