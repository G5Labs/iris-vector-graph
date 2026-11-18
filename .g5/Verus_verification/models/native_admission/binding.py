#!/usr/bin/env python3
"""native_admission binding (iteration 62): the real engine from the pin, on the run's own IRIS fixture, against a
hand transcription of native_admission.rs (resolve_native, plan, gate + caches, try_native, warn/key, compare,
shadow_out, exec_parsed, reader).

Run from the pin tree through run_binding.py (installs the fixture runtime as `runtime`). It drops and re-creates the
namespaces I62B (admission, privileges, mapping, shadow) and I62C (executor version / missing class) from %SYS in the
run's container only (docker exec), creates users i62_all / i62_part / i62_rev with roles i62r_* and deletes them after.

Model inputs are observed or set by the harness, never read from the deciding code: the parsed query's clause flags
(parser output), the grants the harness made, the executor class the harness deployed, the labels it mapped, the
process environment, and each path's own answer (the SQL path from a native_cypher=False engine of the same user, the
native answer from a non-shadow native engine). The transcription derives the path, the raise, the warnings and the
comparison; the observation is what execute_cypher returned or raised, `_native_answers`, and the WARNING log.
Disclosed substitutions: a NativeRoute held on SQL is built by the real NativeRoute from synthetic timings (as the
route_recheck binding) and placed in the engine's route table; the executor's plan version is changed by compiling
the pin's Exec.cls with PLANVERSION 2 (a namespace deployed by another package version), and the class is deleted (a
partial deploy); both are reachable in production (spec 253's 2026-10-21 incident; any process may run
initialize_schema of another version while an engine runs). The comparator and planner domains are unit-level calls
of the real functions; F-0907's SQL tie order is a SQL freedom supplied as a permutation.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import binding_common as bc  # noqa: E402

PIN_DIR = bc.import_pin()
import runtime  # noqa: E402  (installed by run_binding.py)
from iris_vector_graph.cypher import ast, native_plan, native_shadow  # noqa: E402
from iris_vector_graph.cypher.native_route import NativeRoute  # noqa: E402
from iris_vector_graph.cypher.native_shadow import NativeMismatch  # noqa: E402
from iris_vector_graph.cypher.parser import parse_query  # noqa: E402
from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402

NSB, NSC = "I62B", "I62C"
PW = "I62pass-x9"
OK_TAIL = 'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!'
TABLES = ("nodes", "rdf_labels", "rdf_props", "rdf_edges")
RES = "%DB_%DEFAULT:RW,%DB_IRISLIB:R,%DB_IRISSYS:R,%Service_SQL:U,%Native_ClassExecution:U,%Native_GlobalAccess:U"
USERS = {"i62_all": TABLES, "i62_part": TABLES[:3], "i62_rev": TABLES}
PRODUCT_FILES = ["iris_vector_graph/_engine/query.py", "iris_vector_graph/cypher/native_plan.py",
                 "iris_vector_graph/cypher/native_shadow.py", "iris_vector_graph/engine.py",
                 "iris_vector_graph/_engine/nodes_edges.py", "iris_vector_graph/_engine/fhir.py",
                 "iris_vector_graph/cypher/native_route.py", "iris_src/src/Graph/KG/Cypher/Exec.cls"]


# ====================================================================== transcription of native_admission.rs
def resolve_native(arg, env):
    return arg if arg is not None else env != "0"


def features(q, shape_ok=True, covers=False, anchor="props"):
    p = parse_query(q) if isinstance(q, str) else q
    sub = any(isinstance(c, ast.SubqueryCall) for part in p.query_parts for c in part.clauses)
    agg = bool(p.return_clause) and any(isinstance(i.expression, ast.AggregationFunction) for i in p.return_clause.items)
    return {"mutation": p.is_mutation, "union": bool(p.union_queries), "procedure": p.procedure_call is not None,
            "chained": bool(p.subsequent_queries), "subquery": sub, "skip": p.skip is not None, "shape_ok": shape_ok,
            "aggregate": agg, "order_by": p.order_by_clause is not None, "covers": covers, "limit": p.limit is not None,
            "parts": len(p.subsequent_queries) + 1, "anchor": anchor,
            "hidden": bool(p.return_clause) and any((i.alias or "").startswith("__") for i in p.return_clause.items)}


def plan_t(f):
    if f["mutation"] or f["procedure"] or f["union"] or f["chained"]:
        return None
    if f["skip"] or f["subquery"] or not f["shape_ok"]:
        return None
    return {"ordered": (f["order_by"] and f["covers"]) if f["aggregate"] else f["order_by"], "limited": f["limit"]}


class EngineT:
    """The model's Engine: switch, bulk flag, the three caches, the warned set and its log."""

    def __init__(self, arg=None, env="unset"):
        self.native_cypher = resolve_native(arg, env)
        self.in_bulk = False
        self.idx = self.priv = self.exec = None
        self.warned, self.log, self.version_warnings, self.native_answers = set(), [], 0, 0

    def setup(self):
        self.idx = self.exec = None  # never the privilege answer


def gate_t(e, w):
    if not e.native_cypher:
        return "Off"
    if e.idx is None:
        e.idx = w["index"]
    if not e.idx:
        return "NoIndex"
    if e.in_bulk:
        return "InBulk"
    if e.priv is None:
        e.priv = all(w["select"][t] for t in TABLES)
    if not e.priv:
        return "NoSelect"
    if e.exec is None:
        if w.get("transient"):
            return "NotCurrent"
        e.exec = w["deployed"] == native_plan.PLAN_VERSION
        if not e.exec:
            e.version_warnings += 1
    return None if e.exec else "NotCurrent"


def run_t(w, f):
    if w["deployed"] is None:
        return ("raise", "missing")
    if w["deployed"] != native_plan.PLAN_VERSION:
        return ("raise", f"version{w['deployed']}")
    if f["anchor"] == "props" and not w["select"]["rdf_props"]:
        return ("raise", "anchor_props_99")
    if f["anchor"] == "id_nolabel" and not w["select"]["nodes"]:
        return ("raise", "anchor_nodes_99")
    return ("rows",)


def warn_t(e, reason):
    if reason not in e.warned:
        e.warned.add(reason)
        e.log.append(reason)


def try_native_t(e, w, f, mapped):
    p = plan_t(f)
    if p is None:
        return None
    if gate_t(e, w) is not None or mapped or f.get("hidden"):
        return None
    r = run_t(w, f)
    if r[0] == "raise":
        warn_t(e, r[1])
        return None
    e.native_answers += 1
    return p


def key_t(v):
    return (type(v).__name__, v)


def compare_t(sc, sr, nc, nr, ordered, limited, unl):
    """native_shadow.compare as transcribed: Pass, or (what, named row)."""
    if list(sc) != list(nc):
        return ("columns", None)
    if limited and not ordered:
        if len(sr) != len(nr):
            return ("row count", None)
        budget = list(unl if unl is not None else sr)
        for row in nr:
            k = [key_t(v) for v in row]
            hit = next((i for i, b in enumerate(budget) if [key_t(v) for v in b] == k), None)
            if hit is None:
                return ("a row the query cannot return", list(row))
            budget.pop(hit)
        return "pass"
    if ordered:
        for i, (s, n) in enumerate(zip(sr, nr)):
            if [key_t(v) for v in s] != [key_t(v) for v in n]:
                return (f"row {i}", list(n))
        if len(sr) != len(nr):
            m = min(len(sr), len(nr))
            return (f"row count {len(sr)} vs {len(nr)}", list((nr if len(nr) > len(sr) else sr)[m]))
        return "pass"
    cs = Counter(tuple(key_t(v) for v in r) for r in sr)
    cn = Counter(tuple(key_t(v) for v in r) for r in nr)
    if cs == cn:
        return "pass"
    return ("missing from native", None) if cs - cn else ("extra in native", None)


def exec_parsed_t(e, w, f, mapped, shadow, route_sql, sql_obs, nat_obs, unl_obs):
    """Expected (outcome, path) at execute_cypher. sql_obs / nat_obs: each path's own observed answer."""
    if not shadow and route_sql:
        return ("answer", "routed_sql") if sql_obs["kind"] == "rows" else ("error_result", None)
    p = try_native_t(e, w, f, mapped)
    if p is None:
        return ("answer", "sql") if sql_obs["kind"] == "rows" else ("error_result", None)
    if not shadow:
        return ("answer", "native")
    if sql_obs["kind"] == "error":
        return ("raise", "NativeMismatch:SqlFailed")
    unl = unl_obs["rows"] if p["limited"] and not p["ordered"] else None
    c = compare_t(sql_obs["cols"], sql_obs["rows"], nat_obs["cols"], nat_obs["rows"], p["ordered"], p["limited"], unl)
    return ("answer", "native") if c == "pass" else ("raise", "NativeMismatch:" + c[0].split(" ")[0])


# ====================================================================== the fixture
def iris(script, ns="%SYS"):
    return subprocess.run(["docker", "exec", "-i", runtime.NAME, "iris", "session", "IRIS", "-U", ns],
                          input=script + "\nHalt\n", capture_output=True, text=True, timeout=300).stdout


def recreate(ns):
    assert ns.startswith("I62")
    out = iris(f'Set ns="{ns}", dir="/usr/irissys/mgr/{ns.lower()}/"\n'
               'If ##class(Config.Namespaces).Exists(ns) { Set sc=##class(Config.Namespaces).Delete(ns) }\n'
               'If ##class(Config.Databases).Exists(ns) { Set sc=##class(Config.Databases).Delete(ns) }\n'
               'If ##class(%File).Exists(dir_"IRIS.DAT") { Set sc=##class(SYS.Database).DeleteDatabase(dir) }\n'
               'Set ok=##class(%File).CreateDirectoryChain(dir) Set sc=##class(SYS.Database).CreateDatabase(dir) '
               'If $System.Status.IsOK(sc) { Set pdb("Directory")=dir, sc=##class(Config.Databases).Create(ns,.pdb) } '
               'If $System.Status.IsOK(sc) { Set pns("Globals")=ns, pns("Routines")=ns, sc=##class(Config.Namespaces).Create(ns,.pns) } '
               + OK_TAIL)
    assert "RESULT OK" in out, out


def connect(ns, user="_SYSTEM", pw="SYS"):
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=ns, username=user, password=pw)
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c), fx.docker_container_hostname(runtime.NAME),
                                         fx.docker_container_id(runtime.NAME)):
        c.close()
        raise RuntimeError("fixture identity mismatch")
    return c


def engine(c, ns, arg=True, **kw):
    return IRISGraphEngine(c, embedding_dimension=8, namespace=ns, native_cypher=arg, **kw)


def deploy_exec(ns, version):
    """Compile the pin's Exec.cls into `ns` with PLANVERSION `version`; None deletes the class."""
    if version is None:
        out = iris('Set sc=$System.OBJ.Delete("Graph.KG.Cypher.Exec","-d")\n' + OK_TAIL, ns)
    else:
        src = (PIN_DIR / "iris_src/src/Graph/KG/Cypher/Exec.cls").read_text()
        src = src.replace("Parameter PLANVERSION = 3;", f"Parameter PLANVERSION = {version};")
        tmp = f"/tmp/i62exec_{version}.cls"
        subprocess.run(["docker", "exec", "-i", runtime.NAME, "sh", "-c", f"cat > {tmp}"], input=src, text=True, check=True)
        out = iris(f'Set sc=$System.OBJ.Load("{tmp}","ck-d")\n' + OK_TAIL, ns)
    assert "RESULT OK" in out, out


class Log(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.fell, self.version = [], []

    def emit(self, r):
        m = r.getMessage()
        if "native Cypher fell back to SQL" in m:
            self.fell.append(m)
        elif "native Cypher off" in m:
            self.version.append(m)


LOG = Log()
logging.getLogger("iris_vector_graph").addHandler(LOG)
logging.getLogger("iris_vector_graph").setLevel(logging.WARNING)


def tv(rows):
    return [[[type(v).__name__, v] for v in r] for r in rows or []]


def observe(e, q, p=None):
    """What execute_cypher gave: outcome, path, columns, typed rows, warnings."""
    before, f0, v0 = getattr(e, "_native_answers", 0), len(LOG.fell), len(LOG.version)
    obs = {}
    try:
        r = e.execute_cypher(q, p or {})
        obs = {"outcome": "error_result" if r.error else "answer", "cols": list(r.columns or []), "rows": tv(r.rows),
               "error": (r.error or "")[:200] or None}
    except Exception as x:  # noqa: BLE001
        msg = str(x)
        what = None
        if isinstance(x, NativeMismatch):
            what = "SqlFailed" if "SQL path failed" in msg else msg.split("(", 1)[1].split(")", 1)[0].split(" ")[0]
        obs = {"outcome": "raise", "type": type(x).__name__, "what": what, "msg": msg[:400],
               "names_plan": "'family': 'A'" in msg, "names_cypher": q[:30] in msg, "names_params": repr(p or {}) in msg}
    n = getattr(e, "_native_answers", 0) - before
    obs["native_runs"] = n
    obs["fell_back_warnings"] = len(LOG.fell) - f0
    obs["version_warnings"] = len(LOG.version) - v0
    return obs


def path_of(obs, routed=False):
    if obs["outcome"] == "raise":
        return ("raise", f"{obs['type']}:{obs['what']}" if obs["type"] == "NativeMismatch" else obs["type"])
    if obs["outcome"] == "error_result":
        return ("error_result", None)
    return ("answer", "native" if obs["native_runs"] else ("routed_sql" if routed else "sql"))


def provider(obs):
    """Each path's own answer, as the model's input."""
    if obs["outcome"] == "answer":
        return {"kind": "rows", "cols": obs["cols"], "rows": [[v for _, v in r] for r in obs["rows"]]}
    return {"kind": "error"}


CASES = []


def record(name, expected, obs, extra=None, routed=False, warn_expected=None):
    got = path_of(obs, routed)
    row = {"case": name, "expected": list(expected), "observed": list(got), "obs": obs}
    if warn_expected is not None:
        row["expected_warnings"] = warn_expected
        row["agrees"] = list(expected) == list(got) and warn_expected == obs["fell_back_warnings"]
    else:
        row["agrees"] = list(expected) == list(got)
    if extra:
        row.update(extra)
    CASES.append(row)
    return row


# ====================================================================== live cases
def live():
    for ns in (NSB, NSC):
        recreate(ns)
    admin = connect(NSB)
    a = engine(admin, NSB, None)
    a.initialize_schema()
    T = "i62" + os.urandom(2).hex()
    L, LM, LX = "P" + T, "Q" + T, "Ext" + T
    for i, (s, v, t) in enumerate([("", 1, "same"), ("b", "1", "same"), (None, 2, "other"), ("a", "2", "same")]):
        props = {"k": f"{T}_{i}", "v": v, "t": t, "g": "g"}
        if s is not None:
            props["s"] = s
        a.create_node(f"{T}_{i}", labels=[L], properties=props)
    a.create_node(f"{T}_m", labels=[LM], properties={"k": f"{T}_m", "g": "g"})
    world = {"index": True, "select": {t: True for t in TABLES}, "deployed": native_plan.PLAN_VERSION}
    sqlonly = engine(admin, NSB, False)

    R = (f"MATCH (n:{L}) WHERE n.k = $k RETURN n.k AS k, n.v AS v", {"k": f"{T}_1"})
    RS = (f"MATCH (n:{L}) RETURN n.k AS k", {})

    def case(name, eng, et, q, p=None, f=None, mapped=False, shadow=None, route_sql=False, w=None, sql_eng=None,
             nat_eng=None, warn=None, nat_given=None):
        f = f or features(q)
        w = w or world
        shadow = bool(getattr(eng, "cypher_shadow", False)) or os.environ.get("IVG_CYPHER_SHADOW") == "1" if shadow is None else shadow
        sql_obs = provider(observe(sql_eng or sqlonly, q, p))
        nat_obs = nat_given or (provider(observe(nat_eng, q, p)) if nat_eng is not None else {"kind": "rows", "cols": [], "rows": []})
        unl_obs = {"rows": []}
        if f["limit"]:
            unl_q = q.rsplit(" LIMIT ", 1)[0]
            unl_obs = provider(observe(sql_eng or sqlonly, unl_q, p))
        exp = exec_parsed_t(et, w, f, mapped, shadow, route_sql, sql_obs, nat_obs, unl_obs)
        obs = observe(eng, q, p)
        return record(name, exp, obs, {"query": q, "params": p, "features": f, "sql_provider": sql_obs},
                      routed=route_sql, warn_expected=warn)

    # ---- switch resolution (query.native#o01-#o03, gates#o01)
    for arg, env in ((None, "unset"), (False, "unset"), (None, "0"), (True, "0"), (None, "1")):
        if env == "unset":
            os.environ.pop("IVG_NATIVE_CYPHER", None)
        else:
            os.environ["IVG_NATIVE_CYPHER"] = env
        e = engine(admin, NSB, arg)
        case(f"switch_arg{arg}_env{env}", e, EngineT(arg, env), *R)
    os.environ.pop("IVG_NATIVE_CYPHER", None)

    # ---- bulk-load session (gates#o03)
    e, et = engine(admin, NSB, None), EngineT()
    case("bulk_before", e, et, *R)
    with e.bulk_load_session(rebuild_indexes=False, incremental=False):
        et.in_bulk = True
        case("bulk_inside", e, et, *R)
    et.in_bulk = False
    case("bulk_after", e, et, *R)

    # ---- reads only (reads-only#o01-#o05)
    e, et = engine(admin, NSB, None), EngineT()
    for name, q, p, ok in [
        ("read", *R, True),
        ("write_set", f"MATCH (n:{L}) WHERE n.k = $k SET n.z = 'z' RETURN n.k AS k", {"k": f"{T}_1"}, True),
        ("union", f"MATCH (n:{L}) RETURN n.k AS k UNION MATCH (n:{L}) RETURN n.k AS k", {}, True),
        ("call", "CALL db.labels() YIELD label RETURN label", {}, True),
        ("skip", f"MATCH (n:{L}) RETURN n.k AS k SKIP 1", {}, True),
    ]:
        case(name, e, et, q, p, f=features(q, ok))
    # chained: parent declined, each part (chain emptied) planned on its own; two supported parts -> two native runs
    qc = f"MATCH (n:{L}) WHERE n.k = $k RETURN n.k AS k MATCH (m:{L}) WHERE m.k = $k RETURN m.k AS k2"
    fc = features(qc)
    before = getattr(e, "_native_answers", 0)
    r = e.execute_cypher(qc, {"k": f"{T}_1"})
    parts_planned = sum(1 for _ in range(fc["parts"]) if plan_t(dict(fc, chained=False)) is not None and try_native_t(et, world, dict(fc, chained=False), False) is not None)
    CASES.append({"case": "chained_parts", "expected": ["parent_declined", plan_t(fc) is None, "native_parts", parts_planned],
                  "observed": ["parent_declined", native_plan.plan_query(parse_query(qc), {"k": "x"}) is None, "native_parts",
                               getattr(e, "_native_answers", 0) - before],
                  "rows": tv(r.rows), "agrees": None})
    CASES[-1]["agrees"] = CASES[-1]["expected"] == CASES[-1]["observed"]
    # a write's read step: count_create's count and merge_rows' prefix (the real producers) return an internal alias
    from iris_vector_graph.cypher.count_create import plan_count_create
    from iris_vector_graph.cypher.merge_rows import plan_row_merge
    for name, q, check, make in [
        ("count_create_step", f"MATCH (n:{L} {{g: 'g'}}) CREATE (:C{T})", f"MATCH (c:C{T}) RETURN count(*) AS c",
         lambda pq: plan_count_create(pq, {})[0][1]),
        ("row_merge_prefix", f"MATCH (n:{L} {{t: 'other'}}) MERGE (m:M{T} {{x: n.k}})", f"MATCH (m:M{T}) RETURN m.x AS x",
         lambda pq: plan_row_merge(pq, {}).prefix),
    ]:
        f = features(q)
        step = features(make(parse_query(q)))
        before = getattr(e, "_native_answers", 0)
        e.execute_cypher(q, {})
        after = getattr(e, "_native_answers", 0)
        effect = sqlonly.execute_cypher(check, {}).rows
        exp_native = 1 if try_native_t(et, world, step, False) is not None else 0
        CASES.append({"case": name, "expected": ["whole_declined", plan_t(f) is None, "step_hidden_alias", True,
                                                 "read_step_native", exp_native],
                      "observed": ["whole_declined", native_plan.plan_query(parse_query(q), {}) is None, "step_hidden_alias",
                                   step["hidden"], "read_step_native", after - before],
                      "write_effect": tv(effect)})
        CASES[-1]["agrees"] = CASES[-1]["expected"] == CASES[-1]["observed"]
    # a read statement chained after a write statement: its own part, admitted, inside the write's transaction; it
    # reads the row the uncommitted SET just changed
    qw = (f"MATCH (m:{L}) WHERE m.k = $k SET m.z = 'zz{T}' RETURN m.k AS k "
          f"MATCH (n:{L}) WHERE n.z = 'zz{T}' RETURN n.k AS k2")
    fw = features(qw)
    pq = parse_query(qw)
    read_part = features(pq.subsequent_queries[0]) if pq.subsequent_queries else None
    write_part = dict(features(qw), chained=False)
    before = getattr(e, "_native_answers", 0)
    r = e.execute_cypher(qw, {"k": f"{T}_3"})
    exp = (plan_t(fw) is None, try_native_t(et, world, write_part, False) is None,
           1 if read_part and try_native_t(et, world, read_part, False) is not None else 0)
    CASES.append({"case": "chained_write_then_read", "expected": ["whole_declined", exp[0], "write_part_sql", exp[1],
                  "read_part_native", exp[2], "reads_uncommitted", [[["str", f"{T}_3"]]]],
                  "observed": ["whole_declined", native_plan.plan_query(pq, {"k": "x"}) is None, "write_part_sql", True,
                               "read_part_native", getattr(e, "_native_answers", 0) - before, "reads_uncommitted", tv(r.rows)]})
    CASES[-1]["agrees"] = CASES[-1]["expected"] == CASES[-1]["observed"]

    # ---- mapped label (gates#o05)
    cur = admin.cursor()
    cur.execute(f"CREATE TABLE I62Ext.{LX} (PatientID VARCHAR(50), Name VARCHAR(50))")
    cur.execute(f"INSERT INTO I62Ext.{LX} (PatientID, Name) VALUES ('p1', 'Ann')")
    admin.commit()
    e, et = engine(admin, NSB, None), EngineT()
    e.map_sql_table(f"I62Ext.{LX}", "PatientID", LX)
    sqlmap = engine(admin, NSB, False)
    sqlmap.map_sql_table(f"I62Ext.{LX}", "PatientID", LX)
    case("mapped_label", e, et, f"MATCH (p:{LX}) WHERE p.Name = $n RETURN p.Name AS n", {"n": "Ann"}, mapped=True, sql_eng=sqlmap)
    case("unmapped_label_same_engine", e, et, *R)

    # ---- shadow (query.shadow#o01-#o05, route#o03, equal-answers runtime sample)
    nat = engine(admin, NSB, None, native_route_ms=0)  # the native provider never routes to SQL
    QS = {
        "eq_read": R,
        "order_empty_string": (f"MATCH (n:{L}) RETURN n.s AS s ORDER BY n.s", {}),
        "group_mixed_types": (f"MATCH (n:{L}) RETURN n.v AS v, count(*) AS c", {}),
        "limit_unordered": (f"MATCH (n:{L}) RETURN n.k AS k LIMIT 2", {}),
        "order_ties": (f"MATCH (n:{L}) WHERE n.t = 'same' RETURN n.k AS k ORDER BY n.t", {}),
    }
    e, et = engine(admin, NSB, None), EngineT()
    e.cypher_shadow = True
    for name, (q, p) in QS.items():
        case("shadow_" + name, e, et, q, p, nat_eng=nat, shadow=True)
    # the environment switch, set after the engine was built and read on each call
    e2, et2 = engine(admin, NSB, None), EngineT()
    ng = provider(observe(nat, *QS["order_empty_string"]))  # before the variable is set: it reaches every engine
    os.environ["IVG_CYPHER_SHADOW"] = "1"
    case("shadow_env_on", e2, et2, *QS["order_empty_string"], nat_given=ng, shadow=True)
    os.environ.pop("IVG_CYPHER_SHADOW", None)
    case("shadow_env_off", e2, et2, *QS["order_empty_string"], nat_eng=nat, shadow=False)
    # runtime sample of equal answers (columns, values, value types) on admitted reads, native vs SQL path
    sample = []
    for name, (q, p) in QS.items():
        n_o, s_o = observe(nat, q, p), observe(sqlonly, q, p)
        same_rows = n_o["rows"] == s_o["rows"]
        bag = sorted(map(json.dumps, n_o["rows"])) == sorted(map(json.dumps, s_o["rows"]))
        assert n_o["native_runs"] == 1 and s_o["native_runs"] == 0, (name, n_o, s_o)
        sample.append({"query": name, "native_runs": n_o["native_runs"], "columns_equal": n_o["cols"] == s_o["cols"],
                       "rows_and_types_equal_in_order": same_rows, "rows_and_types_equal_as_bag": bag,
                       "native": n_o["rows"], "sql": s_o["rows"]})
    # route held on SQL: consulted without shadow, bypassed (and not recorded) with it
    q, p = R
    held = NativeRoute(50.0, drift=None)  # the default IVG_NATIVE_ROUTE_MS
    for _ in range(40):
        pth = held.next_path()
        held.record(pth, 1.0 if pth == "native" else 0.2)
        if held.choice is not None:
            break
    e, et = engine(admin, NSB, None), EngineT()
    key = e._native_key(parse_query(q), p)
    e.__dict__.setdefault("_native_routes", {})[key] = held
    case("route_held_sql_no_shadow", e, et, q, p, route_sql=True, shadow=False)
    e.cypher_shadow = True
    case("route_held_sql_shadow", e, et, q, p, nat_eng=nat, route_sql=True, shadow=True)
    CASES.append({"case": "route_held_choice", "expected": ["sql"], "observed": [held.choice], "agrees": held.choice == "sql"})
    e3, et3 = engine(admin, NSB, None), EngineT()
    e3.cypher_shadow = True
    observe(e3, q, p)
    CASES.append({"case": "shadow_records_no_route", "expected": [0], "observed": [len(getattr(e3, "_native_routes", {}))],
                  "agrees": len(getattr(e3, "_native_routes", {})) == 0})

    # ---- privileges (privileges#o01, #o03; shadow#o03 through a real SQL failure)
    made = {}
    try:
        for u, tables in USERS.items():
            role = u.replace("i62_", "i62r_")
            out = iris(f'If ##class(Security.Users).Exists("{u}") {{ Set sc=##class(Security.Users).Delete("{u}") }}\n'
                       f'If ##class(Security.Roles).Exists("{role}") {{ Set sc=##class(Security.Roles).Delete("{role}") }}\n'
                       f'Set sc=##class(Security.Roles).Create("{role}","i62 binding","{RES}")\n'
                       f'Set sc=##class(Security.Users).Create("{u}","{role}","{PW}","i62 binding user","{NSB}")\n' + OK_TAIL)
            assert "RESULT OK" in out, out
            made[u] = role
            for t in tables:
                cur.execute(f"GRANT SELECT ON Graph_KG.{t} TO {role}")
            cur.execute(f"GRANT EXECUTE ON SCHEMA Graph_KG TO {role}")
        admin.commit()
        conns = {}
        for u, tables in USERS.items():
            conns[u] = connect(NSB, u, PW)
            w = dict(world, select={t: t in tables for t in TABLES})
            eu, etu = engine(conns[u], NSB, None), EngineT()
            su = engine(conns[u], NSB, False)
            case(f"priv_{u}", eu, etu, *R, w=w, sql_eng=su)
            if u == "i62_rev":
                cur.execute("REVOKE SELECT ON Graph_KG.rdf_props FROM i62r_rev")
                admin.commit()
                w2 = dict(world, select=dict(w["select"], rdf_props=False))
                c2 = connect(NSB, u, PW)
                su2 = engine(c2, NSB, False)
                case("priv_rev_running_engine_props_anchor", eu, etu, *R, w=w2, sql_eng=su, warn=1)
                case("priv_rev_running_engine_props_anchor_again", eu, etu, *R, w=w2, sql_eng=su, warn=0)
                running = case("priv_rev_running_engine_label_scan", eu, etu, *RS, w=w2, sql_eng=su,
                               f=features(RS[0], anchor="scan"), warn=0)
                eu.cypher_shadow = True
                case("priv_rev_running_engine_shadow_scan", eu, etu, *RS, w=w2, sql_eng=su, shadow=True,
                     nat_given=provider(running["obs"]), f=features(RS[0], anchor="scan"), warn=0)
                case("priv_rev_running_engine_shadow_props", eu, etu, *R, w=w2, sql_eng=su, shadow=True, warn=0)
                eu.cypher_shadow = False
                case("priv_rev_new_engine", engine(c2, NSB, None), EngineT(), *R, w=w2, sql_eng=su2)
                c2.close()
        for c in conns.values():
            c.close()
    finally:
        for u, role in made.items():
            iris(f'Set sc=##class(Security.Users).Delete("{u}")\nSet sc=##class(Security.Roles).Delete("{role}")\n' + OK_TAIL)
    cur.close()
    admin.close()

    # ---- executor version / missing class / failure after admission (gates#o04, fallback#o01-#o02, shadow#o05)
    cc = connect(NSC)
    s = engine(cc, NSC, None)
    s.initialize_schema()
    for i in range(3):
        s.create_node(f"{T}_c{i}", labels=[L], properties={"k": f"{T}_c{i}"})
    RC = (f"MATCH (n:{L}) WHERE n.k = $k RETURN n.k AS k", {"k": f"{T}_c1"})
    sqlc = engine(cc, NSC, False)
    wc = dict(world)
    e, et = engine(cc, NSC, None), EngineT()
    case("exec_current_admitted", e, et, *RC, w=wc, sql_eng=sqlc, warn=0)
    es, ets = engine(cc, NSC, None), EngineT()
    es.cypher_shadow = True
    case("exec_current_shadow", es, ets, *RC, w=wc, sql_eng=sqlc, nat_eng=e, shadow=True, warn=0)
    deploy_exec(NSC, 2)
    wc = dict(world, deployed=2)
    case("exec_v2_running_engine_falls_back", e, et, *RC, w=wc, sql_eng=sqlc, warn=1)
    case("exec_v2_same_reason_again", e, et, *RC, w=wc, sql_eng=sqlc, warn=0)
    case("exec_v2_shadow_native_failure", es, ets, *RC, w=wc, sql_eng=sqlc, shadow=True, warn=1)
    deploy_exec(NSC, None)
    wc = dict(world, deployed=None)
    case("exec_missing_running_engine_new_reason", e, et, *RC, w=wc, sql_eng=sqlc, warn=1)
    e4, et4 = engine(cc, NSC, None), EngineT()
    case("exec_missing_new_engine_gate", e4, et4, *RC, w=wc, sql_eng=sqlc, warn=0)
    CASES[-1]["version_warning_expected"] = et4.version_warnings
    CASES[-1]["agrees"] = CASES[-1]["agrees"] and CASES[-1]["obs"]["version_warnings"] == et4.version_warnings
    deploy_exec(NSC, 2)
    wc = dict(world, deployed=2)
    e5, et5 = engine(cc, NSC, None), EngineT()
    case("exec_v2_new_engine_gate", e5, et5, *RC, w=wc, sql_eng=sqlc, warn=0)
    CASES[-1]["version_warning_expected"] = et5.version_warnings
    CASES[-1]["agrees"] = CASES[-1]["agrees"] and CASES[-1]["obs"]["version_warnings"] == et5.version_warnings
    deploy_exec(NSC, 3)
    wc = dict(world)
    case("exec_restored_cached_engine_stays_sql", e5, et5, *RC, w=wc, sql_eng=sqlc, warn=0)
    case("exec_restored_new_engine", engine(cc, NSC, None), EngineT(), *RC, w=wc, sql_eng=sqlc, warn=0)
    e5.initialize_schema()
    et5.setup()
    case("exec_restored_after_setup", e5, et5, *RC, w=wc, sql_eng=sqlc, warn=0)
    cc.close()
    return sample


# ====================================================================== unit domains: the real planner and comparator
PLANNER = [
    ("MATCH (n:P) WHERE n.k = $k RETURN n.k AS k", True, False),
    ("MATCH (n:P) RETURN n.k AS k ORDER BY n.k", True, False),
    ("MATCH (n:P) RETURN n.k AS k ORDER BY n.t LIMIT 2", True, False),
    ("MATCH (n:P) RETURN n.k AS k LIMIT 2", True, False),
    ("MATCH (n:P) RETURN n.k AS k SKIP 1", True, False),
    ("MATCH (n:P) RETURN n.v AS v, count(*) AS c ORDER BY v", True, True),
    ("MATCH (n:P) RETURN n.v AS v, n.w AS w, count(*) AS c ORDER BY v", True, False),
    ("MATCH (n:P) SET n.x = 1", True, False),
    ("MATCH (n:P) DETACH DELETE n", True, False),
    ("MERGE (n:P {id: 'x'})", True, False),
    ("CREATE (n:P)", True, False),
    ("CALL db.labels()", True, False),
    ("MATCH (n:P) RETURN n.k AS k UNION MATCH (m:P) RETURN m.k AS k", True, False),
    ("MATCH (n:P) RETURN n.k AS k MATCH (m:P) RETURN m.k AS k2", True, False),
    ("MATCH (n:P) RETURN someUnknownFunction(n)", False, False),
    ("MATCH (n:P) WITH n.k AS k RETURN k", False, False),
]


def planner_domain():
    rows = []
    for q, ok, covers in PLANNER:
        f = features(q, ok, covers)
        want = plan_t(f)
        got = native_plan.plan_query(parse_query(q), {"k": "x"})
        got = None if got is None else {"ordered": bool(got["ordered"]), "limited": bool(got["limited"])}
        rows.append({"query": q, "want": want, "got": got, "agrees": want == got})
    return rows


VALS = [1, "1", 1.0, True, None, "a"]


def comparator_domain(cmp=None):
    cmp = cmp or native_shadow.compare
    rows, n = [], 0
    lists = [[]] + [[[v]] for v in VALS] + [[[a], [b]] for a, b in itertools.product(VALS[:4], repeat=2)]
    for sr, nr in itertools.product(lists, repeat=2):
        for ordered, limited in ((True, False), (False, False), (False, True), (True, True)):
            unl = (sr + [["a"]]) if limited and not ordered else None
            want = compare_t(["c"], sr, ["c"], nr, ordered, limited, unl)
            try:
                cmp("q", {}, ["c"], sr, ["c"], nr, ordered=ordered, limited=limited, sql_unlimited_rows=unl)
                got = "pass"
            except NativeMismatch as x:
                msg = str(x)
                what = msg.split("(", 1)[1].split(") for", 1)[0]
                got = (what, None)
            n += 1
            ok = (want == "pass") == (got == "pass") and (want == "pass" or want[0].split()[:2] == got[0].split()[:2])
            if not ok:
                rows.append({"sql": sr, "native": nr, "ordered": ordered, "limited": limited, "want": want, "got": got})
    # columns first
    try:
        cmp("q", {}, ["a"], [[1]], ["b"], [[1]], ordered=False)
        rows.append({"columns": "not raised"})
    except NativeMismatch as x:
        if "columns" not in str(x):
            rows.append({"columns": str(x)})
    return n, rows


def f0907():
    """The planner marks ORDER BY over a tied key ordered; SQL may return ties in another order (a SQL freedom)."""
    q = "MATCH (n:P) WHERE n.t = 'same' RETURN n.k AS k ORDER BY n.t"
    p = native_plan.plan_query(parse_query(q), {})
    native, sql = [["k0"], ["k1"]], [["k1"], ["k0"]]
    out = {}
    for lim in (False, True):
        ql = q + (" LIMIT 1" if lim else "")
        pl = native_plan.plan_query(parse_query(ql), {})
        nr, sr = (native[:1], sql[:1]) if lim else (native, sql)
        want = compare_t(["k"], sr, ["k"], nr, bool(pl["ordered"]), bool(pl["limited"]), sql if lim else None)
        try:
            native_shadow.compare(ql, {}, ["k"], sr, ["k"], nr, ordered=bool(pl["ordered"]), limited=bool(pl["limited"]),
                                  sql_unlimited_rows=sql if lim else None)
            got = "pass"
        except NativeMismatch as x:
            got = str(x).split("(", 1)[1].split(")", 1)[0]
        owner_ok = sorted(nr) == sorted(sr) if not lim else all(r in sql for r in nr)
        out["limit" if lim else "nolimit"] = {"plan_ordered": bool(pl["ordered"]), "want": want if want == "pass" else want[0],
                                              "got": got, "owner_rule_admits": owner_ok}
    out["agrees"] = all(v["want"] == v["got"] or (v["want"] != "pass" and v["got"] != "pass")
                        for k, v in out.items() if isinstance(v, dict))
    return out


def warned_set_unit(mutant=False):
    """The real _try_native's warned set on a stub engine whose executor raises (unit level)."""
    from unittest.mock import MagicMock
    e = IRISGraphEngine(MagicMock(), native_cypher=True)
    e._adjacency_indexed_cached, e._in_bulk_load, e._native_executor_cached = True, False, True
    e._native_privileges = lambda: True
    e._table_mapping_cache = {}
    msgs = iter(["plan version 3, executor 2", "plan version 3, executor 2", "x" * 160 + "A", "x" * 160 + "B", "other"])
    e._run_native_plan = lambda plan, params: (_ for _ in ()).throw(RuntimeError(next(msgs)))
    f0 = len(LOG.fell)
    seen = []
    for _ in range(5):
        if mutant:
            e.__dict__.pop("_native_warned", None)
        e._try_native(parse_query("MATCH (n:P) WHERE n.k = $k RETURN n.k AS k"), {"k": "a"})
        seen.append(len(LOG.fell) - f0)
    et = EngineT()
    want = []
    for m in ["plan version 3, executor 2", "plan version 3, executor 2", "x" * 160 + "A", "x" * 160 + "B", "other"]:
        warn_t(et, ("RuntimeError", m[:160]))
        want.append(len(et.log))
    return {"want": want, "got": seen, "agrees": want == seen}


# ====================================================================== main
def main():
    started = time.time()
    sample = live()
    planner = planner_domain()
    ncmp, cmp_bad = comparator_domain()
    tie = f0907()
    warned = warned_set_unit()
    # detection: (a) a changed decisive observed field; (b) product mutants
    flip = json.loads(json.dumps(CASES))
    tgt = next(c for c in flip if c["case"] == "bulk_inside")
    tgt["observed"] = ["answer", "native"]
    detected_obs = any(list(c["expected"]) != list(c["observed"]) for c in flip if c["case"] == "bulk_inside")
    orig_key = native_shadow._key
    native_shadow._key = lambda row: tuple(("v", v) for v in row)  # the comparator without value types
    try:
        _, mutant_bad = comparator_domain()
    finally:
        native_shadow._key = orig_key
    mutant_warn = warned_set_unit(mutant=True)
    detection = {"changed_observed_path": detected_obs, "comparator_without_types": bool(mutant_bad),
                 "warned_set_dropped": not mutant_warn["agrees"]}
    mism = [c for c in CASES if not c["agrees"]]
    pin = bc.pin_identity(PIN_DIR)
    for p in PRODUCT_FILES:
        want = subprocess.check_output(["git", "-C", str(bc.REPO), "rev-parse", f"{bc.PIN}:{p}"], text=True).strip()
        have = subprocess.check_output(["git", "hash-object", str(PIN_DIR / p)], text=True).strip()
        pin["files_equal_pin_blobs"][p] = want == have
        pin["all_equal"] &= want == have
    agrees = (not mism and all(r["agrees"] for r in planner) and not cmp_bad and tie["agrees"] and warned["agrees"]
              and all(detection.values()) and pin["all_equal"])
    verdict = "AGREES" if agrees else "DISAGREES"
    out = bc.write_receipt("native_admission", Path(__file__), {
        "verdict": verdict, "fixture": runtime.FIXTURE, "namespaces": [NSB, NSC], "seconds": round(time.time() - started, 1),
        "live_cases": CASES, "live_mismatches": [c["case"] for c in mism], "equal_answers_sample": sample,
        "planner_domain": planner, "comparator_domain": {"comparisons": ncmp, "mismatches": cmp_bad[:20]},
        "f0907_tie_order": tie, "warned_set_unit": warned, "detection": detection, "pin": pin,
        "real": "execute_cypher/_execute_parsed/_try_native/_shadow_compare/native_gate/_native_privileges/"
                "_native_executor_current/bulk_load_session/map_sql_table on IRIS; plan_query, native_shadow.compare",
        "scope": "one engine process; label/property reads; disclosed: synthetic NativeRoute timings, Exec recompiled "
                 "at PLANVERSION 2 or deleted in I62C, SQL tie permutation for F-0907 at unit level"})
    d = json.loads(out.read_text())
    for p in PRODUCT_FILES:
        d["inputs"][p] = bc.sha(bc.REPO / p)
    out.write_text(json.dumps(d, indent=2, sort_keys=True, default=str) + "\n")
    print(f"native_admission: {verdict}, {len(CASES)} live cases ({len(mism)} disagree), planner {len(planner)}, "
          f"comparator {ncmp}, detection {detection}; {out}")
    for c in mism:
        print(json.dumps(c, default=str)[:600])
    return 0 if verdict == "AGREES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
