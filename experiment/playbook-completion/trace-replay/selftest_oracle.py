#!/usr/bin/env python3
"""Self-test of the replay oracle (trlib) on the lane's scratch global ^IVGAuditE (created and removed here).

    python selftest_oracle.py OUT_DIR

Steps: a SET outside a transaction; a transaction with SET, a subtree KILL and $Increment; a nested level rolled back
with TROLLBACK 1 inside a committed outer transaction; a fully rolled-back transaction; the final KILL. The replay of
the journal over the before-snapshot must equal the engine's final state with no continuity break, and each seeded
defect must be flagged. A toy family (the value of ^IVGAuditE("n")) checks the model-step plumbing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trlib  # noqa: E402
from iris_conn import Conn  # noqa: E402

G = "^IVGAuditE"


class Toy(trlib.Family):
    name = "toy-counter"

    def init(self, store, trace):
        v = store.get(G, "n")
        return "absent" if v is None else str(v)

    def actions(self, step, seg, pre, post):
        return [a for a in step.get("model", [])]

    def next(self, S, a):
        if a[0] == "set":
            return str(a[1])
        if a[0] == "incr":
            return str((0 if S == "absent" else int(S)) + a[1])
        if a[0] == "kill":
            return "absent" if S != "absent" else None   # killing an absent counter is not a step of this toy
        return S

    def obs(self, S):
        return S

    def alpha(self, store, step):
        v = store.get(G, "n")
        return "absent" if v is None else str(v)

    def relevant(self, ref):
        return ref.startswith(G)


def scenario(cap: trlib.Capture):
    g = "IVGAuditE"

    def s1(c):
        c.o.set(5, g, "n")
        return "set n=5"
    cap.step("plain-set", s1, model=[("set", 5)])

    def s2(c):
        c.o.tStart()
        c.o.set("a", g, "t", 1)
        c.o.set("b", g, "t", 2)
        c.o.kill(g, "t")
        c.o.increment(3, g, "n")
        c.o.set("x", g, "keep")
        c.o.tCommit()
        return "txn"
    cap.step("txn", s2, model=[("incr", 3)])

    def s3(c):
        c.o.tStart()
        c.o.set("outer", g, "o")
        c.o.tStart()
        c.o.set("inner", g, "i")
        c.o.increment(1, g, "n")
        c.o.tRollbackOne()
        c.o.tCommit()
        return "nested"
    # the $Increment inside the rolled-back level is journaled outside the transaction and survives (P-0401)
    cap.step("nested-rollback-1", s3, model=[("incr", 1)])

    def s4(c):
        c.o.tStart()
        c.o.set(99, g, "n")
        c.o.tRollback()
        return "rolled back"
    cap.step("rollback", s4, model=[])

    def s5(c):
        c.o.kill(g)
        return "killed"
    cap.step("kill", s5, model=[("kill",)])


def main() -> int:
    out = Path(sys.argv[1])
    cap = trlib.Capture("selftest-oracle", lambda: Conn(trlib.NS))
    c = Conn(trlib.NS)
    c.o.kill("IVGAuditE")
    c.close()
    cap.begin(roots=[G])
    scenario(cap)
    trace = cap.end(out)
    fp = {"*": {"global:^IVGAuditE"}}
    rep = trlib.check(trace, [Toy()], fp)
    ctl = trlib.run_controls(trace, lambda: [Toy()], fp)
    types = sorted({r["t"] for r in trace["journal"]})
    res = {"record_types": types, "records": rep["records"], "violations": rep["violations"],
           "replay_matches_engine": rep["replay_matches_engine"], "model_steps": rep["model_steps"],
           "steps": rep["steps"], "controls": ctl,
           "journal": [{k: r[k] for k in ("a", "t", "p", "x", "g", "n", "o")} for r in trace["journal"]]}
    (out / "selftest.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("record_types", "records", "violations", "replay_matches_engine",
                                           "model_steps")}, indent=1))
    for r in res["journal"]:
        print("  ", r["a"], r["t"], r["p"], r["x"], r["g"], r["n"], r["o"])
    for k, v in ctl.items():
        print(f"control {k}: {'CAUGHT' if v['caught'] else 'NOT CAUGHT'} {v.get('mutation', v.get('detail'))} "
              f"rules={v.get('rules_fired')}")
    ok = not rep["violations"] and rep["replay_matches_engine"] and all(v["caught"] for v in ctl.values())
    print("self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
