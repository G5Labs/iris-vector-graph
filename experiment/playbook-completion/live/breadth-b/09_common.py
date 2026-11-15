"""Module 09 live-check helpers (native Cypher executor) on AUDITB: scratch ids b09_*, labels B09*, graphs b09g*.

Run every script under `bash experiment/playbook-completion/tools/locks.sh iris python ...` (connection cap).

- `osession(script)`: runs ObjectScript lines in an `iris session` terminal in AUDITB (docker exec; nothing is
  compiled). Used only for product-free probes ($ZCRC, $LIST behaviour) and for reading entries whose $LIST is broken.
- `plan_state(c)`: the compiled-plan entries ^IVG.CypherCompiled and the IVGC classes, read without the product's
  Entries() (which raises on a broken entry).
- `cleanup(s)`: Gen.DropAll (the product's own drop), process mode cleared, every b09 row removed (default graph and
  b09g* graphs) with delete_nodes_by_prefix, label and edge-type leftovers removed by SQL.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import *  # noqa: F401,F403,E402

GRAPHS = ["b09gA", "b09gB"]


def osession(script: str, timeout: int = 300) -> str:
    container = os.environ["IVG_TEST_CONTAINER"]
    lines = [ln.strip() for ln in script.strip().splitlines() if ln.strip()]
    body = "\n".join(" " + ln for ln in lines) + '\n write !,$char(30),"END",! halt\n'
    r = subprocess.run(["docker", "exec", "-i", container, "iris", "session", "IRIS", "-U", "AUDITB"],
                       input=body, capture_output=True, text=True, timeout=timeout)
    if "\x1eEND" not in r.stdout:
        raise RuntimeError("iris session did not finish: " + r.stdout[-1500:] + r.stderr[-500:])
    return r.stdout


def marked(out: str, tag: str):
    """Values written as $char(30)_tag_"|"_value lines."""
    res = []
    for ln in out.replace("\r", "").split("\n"):
        if ln.startswith("\x1e" + tag + "|"):
            res.append(ln[len(tag) + 2:])
    return res


def plan_state(c) -> dict:
    """Entries of ^IVG.CypherCompiled read in an iris session with $ListData/$ListGet (the product's Entries() raises
    on an entry with an undefined element), and the IVGC classes from the class dictionary."""
    out = osession('''
 set h="",u=$char(31) for  { set h=$order(^IVG.CypherCompiled(h),1,e) quit:h=""  set d="" for i=1:1:5 { set d=d_$listdata(e,i) } write $char(30),"ENT|",h,u,$listlength(e),u,d,u,$listget(e,1),u,$translate($listget(e,4),$char(10,13,30,31),"    "),u,$length($listget(e,2)),u,$zcrc($listget(e,2),7),u,$order(^IVG.CypherCompiled(h,"src",""),-1),! }
''')
    entries = {}
    for v in marked(out, "ENT"):
        h, n, defined, cls, status, shape_len, crc, src_n = v.split("\x1f", 7)
        entries[h] = {"list_length": int(n), "elements_defined": defined, "class": cls, "status": status,
                      "shape_len": int(shape_len), "zcrc_of_shape": crc, "hash_matches_shape": crc == h,
                      "src_lines": src_n}
    classes = [r[0] for r in c.sql("SELECT Name FROM %Dictionary.ClassDefinition WHERE Name %STARTSWITH 'IVGC.'")]
    compiled = [r[0] for r in c.sql("SELECT Name FROM %Dictionary.CompiledClass WHERE Name %STARTSWITH 'IVGC.'")]
    return {"entries": entries, "class_definitions": classes, "compiled_classes": compiled}


def run(eng, q, params=None):
    t = time.time()
    try:
        r = eng.execute_cypher(q, parameters=params or {})
        return {"q": q, "rows": [list(x) for x in (r.rows or [])], "columns": list(r.columns or []),
                "error": getattr(r, "error", None), "exc": None, "ms": round((time.time() - t) * 1000, 1)}
    except BaseException as e:  # noqa: BLE001  (recorded, not hidden)
        return {"q": q, "rows": None, "exc": type(e).__name__, "msg": str(e)[:1500],
                "ms": round((time.time() - t) * 1000, 1)}


def native_count(eng) -> int:
    return int(getattr(eng, "_native_answers", 0))


def ppget(c, name: str):
    """A process-private global of the connection's server process, read with $Get through an iris-free path:
    not available over the Native API, so answered None (kept for symmetry)."""
    return None


def cleanup(s, extra_engines=()):
    res = {}
    for e in (s.eng,) + tuple(extra_engines):
        try:
            e._iris_obj().classMethodValue("Graph.KG.Cypher.Gen", "Mode", "")
        except Exception as ex:  # noqa: BLE001
            res.setdefault("mode_reset_errors", []).append(repr(ex))
    try:
        res["dropall"] = str(s.c.call("Graph.KG.Cypher.Gen", "DropAll"))
    except Exception as ex:  # noqa: BLE001
        res["dropall_error"] = repr(ex)
    try:
        s.c.o.kill("IVG.CypherGen", "mode")
    except Exception:
        pass
    for g in [None] + GRAPHS:
        try:
            res[f"deleted:{g}"] = s.eng.delete_nodes_by_prefix("b09_", graph=g)
        except Exception as ex:  # noqa: BLE001
            res[f"delete_error:{g}"] = repr(ex)
    left = {}
    for t, col in (("nodes", "node_id"), ("rdf_labels", "s"), ("rdf_props", "s"), ("rdf_edges", "s"),
                   ("rdf_edges", "o_id")):
        n = s.c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t} WHERE {col} %STARTSWITH 'b09'")[0][0]
        if n:
            s.c.sql(f"DELETE FROM Graph_KG.{t} WHERE {col} %STARTSWITH 'b09'")
        left[f"{t}.{col}"] = n
    res["leftover_rows_removed_by_sql"] = left
    res["after"] = plan_state(s.c)
    res["mode_global"] = gget(s.c, "mode", root="IVG.CypherGen")
    return res
