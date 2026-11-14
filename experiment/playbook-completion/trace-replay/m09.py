"""Module 09 (native executor): trace replay through the gate machine (models/breadth-b/src/m09.rs:460-516).

The compiled-plan machine `planc` is not driven: its steps compile generated classes (IVGC.P<h>) into the
namespace in job or sync mode, which this lane does not do. Every native read here runs with the process compile
mode "off" (Graph.KG.Cypher.Gen.Mode, process-private), so Gen.For builds nothing (Gen.cls:64) and the
interpreter answers.

Scenario gate (default graph; tr09n -[:TRR]-> tr09m set up before the capture): a native read of the labelled hop
(no label yet), Cypher SET n:TRL on the SQL path, the read again, REMOVE n:TRL, the read again. Each read runs the
same query on a native engine (counting `_native_answers`) and on a SQL-path engine.
"""
from __future__ import annotations

import time

import trlib
from common import engine, gkey, reset
from families_b import Gate
from families_09 import Mode, Planc, lines_digest

DESIGNS = ["as-built", "reviewed"]
N, M, LBL = "tr09n", "tr09m", "TRL"
# a shape the native planner plans (family A, a tallied hop: native_plan.plan_query); a row-returning hop read is
# not planned at the pin, so its answer would be the SQL path's whatever the gate says
Q_READ = f"MATCH (a:{LBL})-[:TRR]->(b) RETURN count(*) AS c"


def _facts(c):
    eng = engine(c)
    edge = bool(eng._adjacency_indexed)
    rows = c.sql("SELECT Name, Type, TypeClass FROM %Dictionary.CompiledIndex WHERE parent = 'Graph.KG.rdflabels'")
    lab = [r for r in rows if str(r[2]) == "Graph.KG.LabelIndex"]
    return {"edge_idx": edge, "label_idx": bool(lab), "label_index_rows": [list(map(str, r)) for r in rows]}


def s_gate(cap: trlib.Capture):
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    eng = engine(c, native_cypher=False)
    eng.create_node(N)
    eng.create_node(M)
    eng.create_edge(N, "TRR", M)
    cap.meta["index_facts"] = _facts(c)
    c.close()
    cap.meta["gkey"] = gkey("")
    cap.begin()
    G = dict(family="gate")

    def read(c):
        from iris_vector_graph.cypher import native_plan
        c.call("Graph.KG.Cypher.Gen", "Mode", "off")
        nat = engine(c)
        n0 = int(getattr(nat, "_native_answers", 0))
        r1 = nat.execute_cypher(Q_READ)
        native_answered = int(getattr(nat, "_native_answers", 0)) > n0
        r2 = engine(c, native_cypher=False).execute_cypher(Q_READ)
        cnt = lambda r: int(r.rows[0][0]) if r.rows else 0  # noqa: E731
        return {"native_answered": native_answered, "native_count": cnt(r1), "sql_count": cnt(r2),
                "gate_reason": native_plan.native_gate(nat), "mode": str(c.call("Graph.KG.Cypher.Gen", "Effective"))}

    def cy(q):
        def f(c):
            r = engine(c, native_cypher=False).execute_cypher(q)
            if getattr(r, "error", None):
                raise RuntimeError(r.error)
            return "ok"
        return f
    cap.step("read", read, **G)
    cap.step("add-label", cy(f"MATCH (n {{id:'{N}'}}) SET n:{LBL}"), **G)
    cap.step("read", read, **G)
    cap.step("remove-label", cy(f"MATCH (n {{id:'{N}'}}) REMOVE n:{LBL}"), **G)
    cap.step("read", read, **G)


# ------------------------------------------------------------------------------------------------ compiled plans
# Orchestrator scope decision (follow-up): the native executor compiling its own generated plan classes (IVGC.P<h>)
# at run time is the product's normal operation; these scenarios run in AUDITC (TR_NAMESPACE=AUDITC), in the
# product's own modes (job, the default; sync, selected per process through Graph.KG.Cypher.Gen.Mode), and record
# every generated class the product compiled (a read-only %Dictionary query before and after each step).

SHAPES = {0: "T9A", 1: "T9B"}
MODE_LABELS = ["T9M1", "T9M2", "T9M3", "T9M4", "T9M5"]


def q_of(label):
    return f"MATCH (a:{label})-[:T9R]->(b) RETURN count(*) AS c"


def ivgc(c):
    """{generated class: digest of its Walk1 text} for every class of package IVGC (read only)."""
    out = {}
    for (name,) in c.sql("SELECT Name FROM %Dictionary.CompiledClass WHERE Name %STARTSWITH 'IVGC.'"):
        text = ""
        try:
            m = c.o.classMethodObject("%Dictionary.MethodDefinition", "%OpenId", f"{name}||Walk1")
            stream = m.get("Implementation")
            while not stream.get("AtEnd"):
                text += str(stream.invoke("Read", 30000))
        except Exception as ex:  # noqa: BLE001
            text = f"<unreadable {type(ex).__name__}>"
        out[str(name)] = lines_digest(text.replace("\r", "").split("\n"))
    return out


def entries(c):
    """{hash: (class, shape, status)} of ^IVG.CypherCompiled (read only)."""
    out = {}
    h = c.o.nextSubscript(False, "^IVG.CypherCompiled", None)
    while h is not None:
        try:
            v = trlib._decode_raw(c.o.getBytes("^IVG.CypherCompiled", h)) if int(c.o.isDefined("^IVG.CypherCompiled", h)) % 10 == 1 else None
        except Exception:  # noqa: BLE001
            v = None
        if isinstance(v, tuple):
            out[str(h)] = (str(v[0]) if len(v) > 0 else None, str(v[1]) if len(v) > 1 and v[1] is not None else None,
                           str(v[3]) if len(v) > 3 else None)
        else:
            out[str(h)] = (None, None, None)
        h = c.o.nextSubscript(False, "^IVG.CypherCompiled", h)
    return out


def _data(labels):
    from iris_conn import Conn
    c = Conn(trlib.NS)
    try:
        e = engine(c)
        for lab in labels:
            e.create_node(f"tr09{lab.lower()}a", labels=[lab], properties={"name": lab})
            e.create_node(f"tr09{lab.lower()}b")
            e.create_edge(f"tr09{lab.lower()}a", "T9R", f"tr09{lab.lower()}b")
        c.call("Graph.KG.Cypher.Gen", "DropAll")
        before = ivgc(c)
    finally:
        c.close()
    return before


def _gen_pids(obs_c, me):
    """Processes other than `me` holding an ^IVG.CypherCompiled lock or running Graph.KG.Cypher.Gen (the build job)."""
    pids = set()
    for r in obs_c.sql("SELECT Owner, LockString FROM %SYS.LockQuery_List()"):
        if "CypherCompiled" in str(r[1] or "") and str(r[0]) != me:
            pids.add(str(r[0]))
    for (pid, rou) in obs_c.sql("SELECT Pid, Routine FROM %SYS.ProcessQuery WHERE NameSpace = ?", trlib.NS):
        if "Cypher.Gen" in str(rou or "") and str(pid) != me:
            pids.add(str(pid))
    return pids


def reader(cap, label, mode, shape_index=None, pre_mode=True):
    """A native read of `label`'s shape in `mode` ("job", "sync", or None = leave the process mode as it is). In job
    mode the step waits until no entry is pending (the build job finished) and names the job's process."""
    def f(c):
        if mode is not None:
            c.call("Graph.KG.Cypher.Gen", "Mode", mode)
        eff = str(c.call("Graph.KG.Cypher.Gen", "Effective"))
        before = entries(c)
        m_read = trlib.journal.mark()
        eng = engine(c)
        n0 = int(getattr(eng, "_native_answers", 0))
        r = eng.execute_cypher(q_of(label))
        native = int(getattr(eng, "_native_answers", 0)) > n0
        jobs = set()
        from iris_conn import Conn
        obs = Conn(trlib.NS)
        try:
            t0 = time.time()
            while time.time() - t0 < 90:
                jobs |= _gen_pids(obs, c.pid)
                ents = entries(c)
                if not any(st == "pending" for (_, _, st) in ents.values()):
                    break
                time.sleep(0.02)
        finally:
            obs.close()
        after = entries(c)
        changed = [h for h in after if after[h] != before.get(h)]
        # the build job: Gen.For starts it with Job (Gen.cls:96) and it exits when its build is done, usually before
        # the lock or process tables can be read; it is the process other than the reader that wrote this read's
        # entry in the journal window of this call (its records are then checked like the reader's)
        refs = tuple(f"^IVG.CypherCompiled({h}" for h in changed)
        for rec in trlib.journal.records_since(m_read, dbs={trlib.DB}):
            if rec["g"] and rec["p"] != c.pid and refs and rec["g"].startswith(refs):
                jobs.add(rec["p"])
        if shape_index is not None and changed:
            cap.meta.setdefault("slots", {})[str(shape_index)] = changed[0]
            cap.meta.setdefault("shape_text", {})[str(shape_index)] = after[changed[0]][1]
        reply = {"rows": [list(x) for x in (r.rows or [])], "native_answered": native, "effective": eff,
                 "entries": {h: list(v) for h, v in after.items()}, "changed": changed, "classes": ivgc(c),
                 "job_pids": sorted(jobs)}
        return (reply, sorted(jobs)) if jobs else reply
    return f


def dropall(c):
    st = str(c.call("Graph.KG.Cypher.Gen", "DropAll"))
    return {"status": st, "classes": ivgc(c), "entries": {h: list(v) for h, v in entries(c).items()}}


def s_planc(cap: trlib.Capture):
    """Compiled-plan cache in the product's own modes: shape A read in sync mode (built in the reader), read again
    (compiled), shape B read in job mode (the default; a background job builds), read again, Gen.DropAll (what a deploy
    runs), shape A read in sync mode again (built anew)."""
    reset()
    cap.meta["classes_before"] = _data(list(SHAPES.values()))
    cap.begin()
    P = dict(family="planc")
    cap.step("read", reader(cap, SHAPES[0], "sync", 0), planc="Read", shape_index=0, mode="sync", **P)
    cap.step("read", reader(cap, SHAPES[0], "sync", 0), planc="Read", shape_index=0, mode="sync", **P)
    cap.step("read", reader(cap, SHAPES[1], "job", 1), planc="Read", shape_index=1, mode="job", **P)
    cap.step("read", reader(cap, SHAPES[1], "job", 1), planc="Read", shape_index=1, mode="job", **P)
    cap.step("Gen.DropAll", dropall, planc="DropAll", **P)
    cap.step("read", reader(cap, SHAPES[0], "sync", 0), planc="Read", shape_index=0, mode="sync", **P)
    from iris_conn import Conn
    c = Conn(trlib.NS)
    try:
        cap.meta["classes_after"] = ivgc(c)
    finally:
        c.close()


def s_mode(cap: trlib.Capture):
    """F-0903: which mode a read builds in. One reader process R (its process mode is process-private). Namespace
    mode ^IVG.CypherGen("mode") set to "OFF" (a value Gen.Mode would refuse; the namespace value is a plain global
    Set, docs/ADMIN_GUIDE.md:774-779, here through the Native API as an operator would), "off", killed; process mode
    "sync" through Gen.Mode, then "OFF" (refused). Each read is a new shape, so a build is due whenever one runs."""
    reset()
    cap.meta["classes_before"] = _data(MODE_LABELS)
    from iris_conn import Conn
    c = Conn(trlib.NS)
    try:
        c.o.kill("^IVG.CypherGen", "mode")
    finally:
        c.close()
    cap.begin()
    M = dict(family="mode")

    def set_ns(v):
        def f(c):
            if v is None:
                c.o.kill("^IVG.CypherGen", "mode")
            else:
                c.o.set(v, "^IVG.CypherGen", "mode")
            return {"namespace_mode": v}
        return f

    def set_proc(v):
        def f(c):
            return {"effective": str(c.call("Graph.KG.Cypher.Gen", "Mode", v))}
        return f
    cap.step("clear-process-mode", set_proc(""), who="R", mode_op="ClearProc", **M)
    cap.step("set-namespace-mode", set_ns("OFF"), mode_op="SetNs", value="OFF", **M)
    cap.step("read", reader(cap, MODE_LABELS[0], None), who="R", mode_op="Read", **M)
    cap.step("set-namespace-mode", set_ns("off"), mode_op="SetNs", value="off", **M)
    cap.step("read", reader(cap, MODE_LABELS[1], None), who="R", mode_op="Read", **M)
    cap.step("set-namespace-mode", set_ns(None), mode_op="SetNs", value=None, **M)
    cap.step("read", reader(cap, MODE_LABELS[2], None), who="R", mode_op="Read", **M)
    cap.step("Gen.Mode", set_proc("sync"), who="R", mode_op="SetProc", value="sync", **M)
    cap.step("read", reader(cap, MODE_LABELS[3], None), who="R", mode_op="Read", **M)
    cap.step("Gen.Mode", set_proc("OFF"), who="R", mode_op="SetProc", value="OFF", **M)
    cap.step("read", reader(cap, MODE_LABELS[4], None), who="R", mode_op="Read", **M)

    def after():
        c = Conn(trlib.NS)
        try:
            c.o.kill("^IVG.CypherGen", "mode")
            cap.meta["classes_after"] = ivgc(c)
        finally:
            c.close()
    after()


SCENARIOS = {"gate": s_gate, "planc": s_planc, "mode": s_mode}

# The first SET of a plan entry (For's "pending") is overwritten by its build within the same step, and outside a
# transaction the journal keeps no old value: dropping it changes nothing any oracle can see. The dropped-record
# control of planc therefore drops a line of a plan (^IVG.CypherCompiled(h, "src", i)), whose loss must show.
CONTROL_PAIRS = {"planc": {"dropped-record": '"src",'}}

EXPECT = {"gate": [], "planc": [], "mode": [("mode[as-built]", Mode.M_X12, "F-0903")]}


def families(trace, design):
    name = trace["name"].split("-", 1)[1]
    if name == "planc":
        return [Planc(design)]
    if name == "mode":
        return [Mode(design)]
    return [Gate(N, LBL, trace["meta"]["gkey"], design)]


def footprint(trace):
    cy = trlib.declared("08", ["eng:IRISGraphEngine.execute_cypher"])
    rd = trlib.declared("09", ["eng:IRISGraphEngine.execute_cypher[native]", "cls:Graph.KG.Cypher.Exec.Run",
                               "cls:Graph.KG.Cypher.Gen.For"])
    gen = trlib.declared("09", ["cls:Graph.KG.Cypher.Gen.For", "cls:Graph.KG.Cypher.Gen.Build",
                                "job:Graph.KG.Cypher.Gen.Build[job]"])
    return {"read": rd | gen | trlib.declared("08", ["eng:IRISGraphEngine.execute_cypher"]),
            "add-label": cy, "remove-label": cy,
            "Gen.DropAll": trlib.declared("09", ["cls:Graph.KG.Cypher.Gen.DropAll"]),
            "clear-process-mode": set(), "Gen.Mode": set(),
            "set-namespace-mode": {"global:^IVG.CypherGen"}}
