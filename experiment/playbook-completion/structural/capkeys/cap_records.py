#!/usr/bin/env python3
"""§3.6 capacity: ledger records near IRIS's long-string limit through every reader of modules 11, 13, 14 and 18
(AUDITD, live).

    locks.sh iris python cap_records.py OUT.json

For each payload (a relationship qualifier of n characters, plain or escape-expanding) the case commits one
changeset on a fresh ledger, then runs each module's reader on it: get_revision / history (11, 14), reconstruct,
export_reconstruction and verify (14), save_snapshot + replacing restore_snapshot + verify (18), and, after the
tenant's erasure, redact + get_revision (13). Oracle: the reader answers, and the value it returns for the
qualifier equals what was committed (length and SHA-256); an accepted commit whose record a reader cannot return is
a capacity defect (a committed revision that cannot be read, verified or restored).
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
import lib  # noqa: E402

from iris_vector_graph.ledger import Changeset  # noqa: E402

MAXSTR = 3_641_144


def h(s):
    if s is None:
        return None
    s = s if isinstance(s, str) else json.dumps(s, sort_keys=True)
    return {"len": len(s), "sha": hashlib.sha256(s.encode("utf-8", "surrogatepass")).hexdigest()[:16]}


def find_qual(obj, want_len):
    """The qualifier value of length want_len anywhere in a reader's answer (records, states, ndjson)."""
    stack = [obj]
    seen = 0
    while stack and seen < 200000:
        x = stack.pop()
        seen += 1
        if isinstance(x, str):
            if len(x) == want_len:
                return x
            if len(x) > want_len and x.startswith("{"):
                try:
                    stack.append(json.loads(x))
                except Exception:  # noqa: BLE001
                    pass
        elif isinstance(x, dict):
            stack.extend(x.values())
        elif isinstance(x, (list, tuple)):
            stack.extend(x)
        elif hasattr(x, "__dict__"):
            stack.extend(vars(x).values())
    return None


def step(name, f, out):
    t0 = time.time()
    try:
        v = f()
        out[name] = {"ok": True, "secs": round(time.time() - t0, 2)}
        return v
    except Exception as ex:  # noqa: BLE001
        out[name] = {"ok": False, "error": f"{type(ex).__name__}: {str(ex)[:400]}", "secs": round(time.time() - t0, 2)}
        return None


def case(label, value):
    c = lib.conn()
    r = {"case": label, "qualifier": h(value)}
    try:
        lib.reset(c)
        eng = lib.engine(c)
        led = eng.ledger
        led.enable()
        c.conn.commit()
        ch = Changeset(actor="audit:structural", actor_type="ingest", message="near-limit record")
        ch.create_node("rq|1")
        ch.create_node("rq|2")
        ch.create_relationship("rq|1", "R", "rq|2", qualifiers={"big": value})
        res = step("commit", lambda: led.commit(ch), r)
        c.conn.commit()
        if res is None:
            r["outcome"] = "commit-refused"
            return r
        rid = res.revision.revision_id
        r["seq"] = res.revision.seq
        rev = step("11/14:get_revision", lambda: led.get_revision(rid), r)
        if rev is not None:
            got = find_qual([vars(x) if hasattr(x, "__dict__") else x for x in rev.records], len(value))
            r["11/14:get_revision"]["value_equal"] = got == value
        step("11/14:history", lambda: led.history(limit=10), r)
        st = step("14:reconstruct", lambda: led.reconstruct(rid), r)
        if st is not None:
            got = find_qual(st, len(value))
            r["14:reconstruct"]["value_equal"] = got == value
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "exp.ndjson"
            step("14:export_reconstruction", lambda: led.export_reconstruction(rid, str(p)), r)
            if p.exists():
                txt = p.read_text()
                r["14:export_reconstruction"]["value_present"] = value in txt or json.dumps(value)[1:-1] in txt
        v = step("14:verify", lambda: led.verify(), r)
        if v is not None:
            r["14:verify"]["result"] = str(getattr(v, "result", v))[:200]
        with tempfile.TemporaryDirectory() as d:
            p = str(Path(d) / "snap.zip")
            step("18:save_snapshot", lambda: eng.save_snapshot(p), r)
            if r["18:save_snapshot"]["ok"]:
                lib.reset(c)
                rr = step("18:restore_snapshot", lambda: eng.restore_snapshot(p), r)
                c.conn.commit()
                if rr is not None:
                    eng2 = lib.engine(c)
                    rv2 = step("18:get_revision_after_restore", lambda: eng2.ledger.get_revision(rid), r)
                    if rv2 is not None:
                        got = find_qual([vars(x) if hasattr(x, "__dict__") else x for x in rv2.records], len(value))
                        r["18:get_revision_after_restore"]["value_equal"] = got == value
                    q = c.sql("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = 'rq|1'")
                    qv = None
                    if q and q[0][0] is not None:
                        try:
                            qv = json.loads(str(q[0][0])).get("big")
                        except Exception:  # noqa: BLE001
                            qv = None
                    r["18:edge_row_after_restore"] = {"present": bool(q), "value_equal": qv == value}
                    v2 = step("18:verify_after_restore", lambda: eng2.ledger.verify(), r)
                    if v2 is not None:
                        r["18:verify_after_restore"]["result"] = str(getattr(v2, "result", v2))[:200]
        # 13: erase the tenant, then redact it
        eng = lib.engine(c)
        step("12:erase_nodes", lambda: c.call("Graph.KG.Eraser", "EraseNodes", "", "rq|"), r)
        c.conn.commit()
        rc = step("13:redact", lambda: eng.ledger.redact(prefix="rq"), r)
        c.conn.commit()
        if rc is not None:
            r["13:redact"]["receipt"] = str(rc)[:300]
            rv3 = step("13:get_revision_after_redact", lambda: eng.ledger.get_revision(rid), r)
            if rv3 is not None:
                got = find_qual([vars(x) if hasattr(x, "__dict__") else x for x in rv3.records], len(value))
                r["13:get_revision_after_redact"]["value_still_present"] = got is not None
        fails = [k for k, v in r.items() if isinstance(v, dict) and v.get("ok") is False]
        wrong = [k for k, v in r.items() if isinstance(v, dict) and v.get("value_equal") is False]
        r["outcome"] = "all-readers-ok" if not fails and not wrong else "reader-defect"
        r["failed_steps"] = fails
        r["wrong_value_steps"] = wrong
    except Exception:  # noqa: BLE001
        r["outcome"] = "harness-error"
        r["trace"] = traceback.format_exc()[-1500:]
    finally:
        try:
            lib.reset(c)
        except Exception:  # noqa: BLE001
            pass
        c.close()
    print(json.dumps({k: v for k, v in r.items() if k != "trace"}, default=str)[:1800], flush=True)
    return r


def main() -> int:
    outp = Path(sys.argv[1])
    res = []
    for label, value in (("plain-1000000", "x" * 1_000_000),
                         ("plain-1800000", "x" * 1_800_000),
                         ("plain-3000000", "x" * 3_000_000),
                         ("plain-3600000", "x" * 3_600_000),
                         ("quotes-1000000", '"' * 1_000_000),
                         ("quotes-1900000", '"' * 1_900_000),
                         ("ctrl-700000", "\x01" * 700_000)):
        res.append(case(label, value))
        lib.dump(outp, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
