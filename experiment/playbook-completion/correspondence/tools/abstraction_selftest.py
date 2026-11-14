#!/usr/bin/env python3
"""Negative controls for abstraction.py: traces the product never produced, each of which must be rejected.

    python abstraction_selftest.py TRACE.json [EXT_TRACE.json]

Controls on a ledger trace (conformance.py's five mutations, plus three of this lane):
- conformance.mutate(...) x5 (tombstone outside the target, commit rewriting history, erasure touching records,
  frame excursion (not an abstraction property: expected not caught here), live statement without tuple);
- tombstone-wrong-digest: one tombstone's digest replaced;
- audit-count-off: the redaction revision's count raised by one;
- marker-other-target: a batch's marker SET rewritten to another digest.
With an ext trace (row snapshots): store-apply-mismatch (a commit's rows_after loses one row) and
erase-leaves-row (an erasure's rows_after keeps one target row).
"""
from __future__ import annotations

import base64
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abstraction  # noqa: E402
from common import conformance  # noqa: E402
import iris  # noqa: E402


def lb(*vals) -> str:
    lst = iris.IRISList()
    for v in vals:
        lst.add(v)
    return base64.b64encode(lst.getBuffer()).decode()


def caught(trace) -> list:
    r = abstraction.check(trace)
    return r["violations"] + [n for n in r["invariant_notes"] if not n.split(": ", 1)[-1].startswith(("abstraction:", "inv_replay"))]


def main() -> int:
    t0 = json.loads(Path(sys.argv[1]).read_text())
    ok = True
    base = caught(t0)
    print("unmutated:", "clean" if not base else base[:3])
    ok &= not base
    controls = {}
    for k in conformance.CONTROLS:
        controls[k] = conformance.mutate(t0, k)
    t = copy.deepcopy(t0)
    redact_pid = [o["pid"] for o in t["ops"] if o["op"] == "redact"]
    r = next(r for r in t["journal"] if r["p"] in redact_pid and r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET"
             and conformance.decode_value(r["n"])[0] == "redacted")
    v = conformance.decode_value(r["n"])
    r["n"] = lb("redacted", "0" * 64, v[2], v[3], v[4])
    controls["tombstone-wrong-digest"] = t
    t = copy.deepcopy(t0)
    r = next(r for r in t["journal"] if r["p"] in redact_pid and r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET"
             and conformance.decode_value(r["n"])[0] == "redact")
    v = list(conformance.decode_value(r["n"]))
    v[5] = "S" + str(int(str(v[5])[1:]) + 1)
    r["n"] = lb(*v)
    controls["audit-count-off"] = t
    t = copy.deepcopy(t0)
    for r in t["journal"]:
        if r["p"] in redact_pid and r["g"] == '^IVG.Ledger("redacting")' and r["t"] == "SET":
            v = list(conformance.decode_value(r["n"]))
            v[0] = "f" * 64
            r["n"] = lb(*v)
    controls["marker-other-target"] = t
    if len(sys.argv) > 2:
        e0 = json.loads(Path(sys.argv[2]).read_text())
        base = caught(e0)
        print("ext unmutated:", "clean" if not base else base[:3])
        t = copy.deepcopy(e0)
        o = next(o for o in t["ops"] if o.get("label") == "commit-create")
        o["rows_after"]["labels"] = o["rows_after"]["labels"][1:]
        controls["store-apply-mismatch"] = t
        t = copy.deepcopy(e0)
        o = next(o for o in t["ops"] if o.get("label") == "erase-nodes")
        o["rows_after"]["nodes"] = o["rows_after"]["nodes"] + [r for r in o["rows_before"]["nodes"] if r[0].startswith("x|")][:1]
        controls["erase-leaves-row"] = t
    expect_not = {"frame-violation"}
    for k, t in controls.items():
        hits = caught(t)
        good = bool(hits) != (k in expect_not)
        ok &= good
        print(f"control {k}: {'REJECTED' if hits else 'not caught'}{' (expected: a frame property)' if k in expect_not else ''}"
              f" {hits[:1]}")
    print("abstraction self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
