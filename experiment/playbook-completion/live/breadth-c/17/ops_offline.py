#!/usr/bin/env python3
"""Module 17 checks that need no IRIS: error hierarchy (F-1704), IVGResult fields (F-1711), STATUS_PARTS (F-1713),
console scripts declared in pyproject.toml (F-C1701), EmbeddedCursor transaction statements (F-1702, through the
cursor itself with a stub `iris.sql`). Output: $RUN_DIR/breadth-c/17/offline.json and live/breadth-c/17/offline.json.
"""
from __future__ import annotations

import importlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
OUT = Path(os.environ["RUN_DIR"]) / "breadth-c" / "17"
OUT.mkdir(parents=True, exist_ok=True)


def errors_hierarchy():
    from iris_vector_graph.errors import IVGError
    names = {
        "iris_vector_graph.schema_name": ["IVGSchemaError"],
        "iris_vector_graph.exceptions": ["BulkLoadError", "TemporalWindowError", "FHIRGraphError",
                                         "ClassesUnreadable", "EmbeddingIdentityConflict",
                                         "NamespaceConsistencyError"],
        "iris_vector_graph.host": ["HostError"],
        "iris_vector_graph.embedded": ["EmbeddedUnavailableError"],
    }
    out = {}
    for mod, cls in names.items():
        m = importlib.import_module(mod)
        for c in cls:
            k = getattr(m, c, None)
            out[f"{mod}.{c}"] = None if k is None else {
                "is_IVGError": issubclass(k, IVGError), "mro": [x.__name__ for x in k.__mro__][:6]}
    # every exception class the package defines, mechanically
    every = {}
    for p in sorted((REPO / "iris_vector_graph").rglob("*.py")):
        mod = ".".join(p.relative_to(REPO).with_suffix("").parts)
        if "browser_static" in mod or mod.endswith("__main__"):
            continue
        try:
            m = importlib.import_module(mod)
        except Exception:
            continue
        for n, k in vars(m).items():
            if inspect.isclass(k) and issubclass(k, BaseException) and k.__module__ == mod:
                every[f"{mod}.{n}"] = issubclass(k, IVGError)
    doc = (REPO / "iris_vector_graph/errors.py").read_text().split('"""')[1][:400]
    return {"named_in_finding": out, "every_package_exception": every,
            "not_under_IVGError": sorted(k for k, v in every.items() if not v), "errors_py_docstring": doc}


def ivgresult():
    from iris_vector_graph.result import IVGResult
    r = IVGResult(columns=["node_id"], rows=[["a"]])
    try:
        recs = r.records
        got = repr(recs)[:200]
    except Exception as ex:
        got = f"{type(ex).__name__}: {ex}"[:200]
    readme = (REPO / "deploy/README.md").read_text().splitlines()
    return {"fields": sorted(type(r).model_fields) if hasattr(type(r), "model_fields") else None,
            "result.records": got, "deploy_README_73_79": readme[72:79]}


def status_parts():
    from iris_vector_graph.status import STATUS_PARTS
    src = (REPO / "iris_vector_graph/_engine/admin.py").read_text().splitlines()
    appended = [f"admin.py:{i+1}: {ln.strip()}" for i, ln in enumerate(src)
                if "unknown.append(" in ln or ("unknown" in ln and '"adjacency"' in ln) or ('"routines"' in ln and "unknown" in ln)]
    return {"STATUS_PARTS": list(STATUS_PARTS), "unknown_appends_in_admin_py": appended[:20],
            "names_outside_STATUS_PARTS": sorted({"adjacency", "routines"} - set(STATUS_PARTS))}


def console_scripts():
    import tomllib
    py = tomllib.loads((REPO / "pyproject.toml").read_text())
    scripts = py["project"]["scripts"]
    wheel = py["tool"]["hatch"]["build"]["targets"]["wheel"]
    tracked = subprocess.run(["git", "ls-tree", "-r", "--name-only", "3eaa79cf", "scripts"], cwd=REPO,
                             capture_output=True, text=True).stdout.split()
    res = {"declared": scripts, "wheel_packages": wheel.get("packages"), "wheel_force_include": wheel.get("force-include"),
           "scripts/test.py tracked at pin": "scripts/test.py" in tracked,
           "scripts/ingest/networkx_loader.py tracked at pin": "scripts/ingest/networkx_loader.py" in tracked}
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)}
    runs = {}
    with tempfile.TemporaryDirectory() as d:
        for name in ("run-tests", "networkx-loader"):
            exe = Path(sys.executable).parent / name
            try:
                p = subprocess.run([str(exe), "--help"], cwd=d, env=env, capture_output=True, text=True, timeout=60)
                runs[name] = {"exit": p.returncode, "stderr_tail": p.stderr.strip().splitlines()[-2:]}
            except Exception as ex:
                runs[name] = {"error": str(ex)[:200]}
    # where the venv resolves `scripts` from (an editable install of the checkout puts the repo root on sys.path)
    res["runs_outside_repo_without_PYTHONPATH"] = runs
    p = subprocess.run([sys.executable, "-c", "import iris_vector_graph, sys; print(iris_vector_graph.__file__)"],
                       cwd="/tmp", env=env, capture_output=True, text=True)
    res["installed_package_path"] = p.stdout.strip()
    return res


def embedded_cursor():
    """F-1702: through EmbeddedCursor.execute with a recording stand-in for embedded `iris.sql`."""
    import iris_vector_graph.embedded as emb
    calls = []

    class Stmt:
        def execute(self, *a):
            calls.append(("execute", a))
            return iter([])

    class FakeSql:
        def prepare(self, sql):
            calls.append(("prepare", sql))
            return Stmt()

        def exec(self, sql, *a):
            calls.append(("exec", sql))
            return iter([])

    out = {}
    try:
        cur = emb.EmbeddedCursor.__new__(emb.EmbeddedCursor)
        for attr, val in (("_sql", FakeSql()), ("_iris_sql", FakeSql()), ("description", None), ("_rows", []),
                          ("rowcount", -1), ("_conn", None)):
            try:
                setattr(cur, attr, val)
            except Exception:
                pass
        for stmt in ("START TRANSACTION", "BEGIN", "COMMIT", "ROLLBACK"):
            n = len(calls)
            try:
                cur.execute(stmt)
                out[stmt] = {"sent_to_iris": calls[n:] != [], "calls": [str(c)[:80] for c in calls[n:]]}
            except Exception as ex:
                out[stmt] = {"error": f"{type(ex).__name__}: {ex}"[:200]}
    except Exception as ex:
        out["setup_error"] = f"{type(ex).__name__}: {ex}"[:300]
    src = (REPO / "iris_vector_graph/embedded.py").read_text().splitlines()
    out["source_312_321"] = src[311:321]
    return out


def main():
    res = {}
    for name, fn in (("F-1704", errors_hierarchy), ("F-1711", ivgresult), ("F-1713", status_parts),
                     ("F-C1701", console_scripts), ("F-1702", embedded_cursor)):
        try:
            res[name] = fn()
        except Exception as ex:
            res[name] = {"exception": f"{type(ex).__name__}: {ex}"[:500]}
    txt = json.dumps(res, indent=1, sort_keys=True, default=str)
    (OUT / "offline.json").write_text(txt + "\n")
    (HERE / "offline.json").write_text(txt + "\n")
    print(txt[:6000])


if __name__ == "__main__":
    main()
