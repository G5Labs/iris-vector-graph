#!/usr/bin/env python3
"""FETCH FIRST on IRIS 2026.1 Community with the locked driver (AUDITENV, scratch table IVGAudit.T): each statement
runs in its own child process (a SIGSEGV is uncatchable in-process), with TOP and LIMIT as controls run the same way.
Prints one JSON object; exit 0 when every control answered (the observation itself is recorded, not judged)."""
import json
import os
import subprocess
import sys
from pathlib import Path

TOOLS = str(Path(__file__).resolve().parents[2] / "tools")
sys.path.insert(0, TOOLS)
from iris_conn import Conn  # noqa: E402

STMTS = [
    ("control-top", "SELECT TOP 2 k FROM IVGAudit.T ORDER BY k", True),
    ("control-limit", "SELECT k FROM IVGAudit.T ORDER BY k LIMIT 2", True),
    ("control-plain", "SELECT k FROM IVGAudit.T", True),
    ("fetch-first-0-unordered", "SELECT k FROM IVGAudit.T FETCH FIRST 0 ROWS ONLY", False),
    ("fetch-first-2-unordered", "SELECT k FROM IVGAudit.T FETCH FIRST 2 ROWS ONLY", False),
    ("fetch-first-2-ordered", "SELECT k FROM IVGAudit.T ORDER BY k FETCH FIRST 2 ROWS ONLY", False),
    ("offset-fetch-next", "SELECT k FROM IVGAudit.T ORDER BY k OFFSET 1 ROWS FETCH NEXT 2 ROWS ONLY", False),
]
CHILD = ("import sys; sys.path.insert(0, %r)\nfrom iris_conn import Conn\nc = Conn('AUDITENV')\ncur = c.conn.cursor()\n"
         "cur.execute(%r)\nprint('ROWS', [r[0] for r in cur.fetchall()], flush=True)\nc.close()\n")


def main():
    ctl = Conn("AUDITENV")
    try:
        ctl.sql("DELETE FROM IVGAudit.T")
        for k in ("1", "2", "3"):
            ctl.sql("INSERT INTO IVGAudit.T (k, v) VALUES (?, ?)", k, "v")
        out = {"engine": str(ctl.call("%SYSTEM.Version", "GetVersion")), "results": []}
        import iris
        import importlib.metadata as _m
        out["driver"] = _m.version("intersystems-irispython") + " " + iris.__file__
        for name, q, control in STMTS:
            try:
                r = subprocess.run([sys.executable, "-c", CHILD % (TOOLS, q)], capture_output=True, text=True,
                                   timeout=60, env=os.environ)
                rows = [ln for ln in r.stdout.splitlines() if ln.startswith("ROWS")]
                out["results"].append({"name": name, "sql": q, "control": control, "returncode": r.returncode,
                                       "rows": rows[0][5:] if rows else None,
                                       "stderr_tail": [ln for ln in r.stderr.splitlines() if "WARNING" not in ln][-3:]})
            except subprocess.TimeoutExpired:
                out["results"].append({"name": name, "sql": q, "control": control, "returncode": "timeout"})
        ok = all(x["returncode"] == 0 for x in out["results"] if x["control"])
        out["controls_answered"] = ok
        out["fetch_first_crashed"] = [x["name"] for x in out["results"] if not x["control"] and x["returncode"] in (-11, 139)]
        print(json.dumps(out, indent=1))
        return 0 if ok else 1
    finally:
        ctl.sql("DELETE FROM IVGAudit.T")
        ctl.close()


if __name__ == "__main__":
    raise SystemExit(main())
