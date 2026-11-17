"""bolt_tx binding (iteration 56, review 53-55 F1): the product's real TCP Bolt listener (start_tcp_bolt_server, a real
engine on its own connection) against a port of bolt_tx.rs. Fixture ivg-cont-20261117-iris, USER, fresh prefix i56b_.

R cases: an independent raw Bolt 4.4 client sends one message at a time (HELLO, then the case's BEGIN / RUN / PULL /
COMMIT / ROLLBACK / RESET / GOODBYE) and records each summary answer (SUCCESS, FAILURE, IGNORED); a second engine
connection then counts the case's nodes (the final reader). D cases: the neo4j Python driver 6.4.1 (tx.rollback(),
a failure then rollback, an aborted execute_write, commit, auto-commit, a session closed with an open transaction);
the observation is the count and the exception classes the driver raised. The port predicts the answers and the count
from the message sequence; each port mutation mirrors a control of model.json and must be detected (rule-rollback-keeps
changes only the rule, so it has no product observation); one tampered count must be detected. The rule's count
(`intended`) is recorded beside each case."""
import asyncio, json, os, socket, struct, sys, threading, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/Verus_verification/tools")); sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import binding_common as bc  # noqa: E402
PIN = bc.import_pin()
import runtime  # noqa: E402

MUTS = ["begin-refused", "atomic-tx", "rollback-answers-failure", "run-not-committed", "failed-run-writes", "failure-not-sticky",
        "http-batch-atomic", "http-stop-at-failure", "http-failure-writes", "http-read-only-runs-reads", "http-status-ok-on-error",
        "read-only-first-only"]
BOLT_MUTS = MUTS[:6]; HTTP_MUTS = MUTS[6:]


# ------------------------------------------------------------------ port of bolt_tx.rs (m = active mutation)
# messages: ("Begin",) ("Run", w, fails) ("Pull",) ("Commit",) ("Rollback",) ("Reset",) ("Close",)
def step(s, msg, m):
    store, failed, tx = s
    k = msg[0]
    if failed and m != "failure-not-sticky":
        return ((store, False, None), "S") if k == "Reset" else (s, "I")
    if m == "atomic-tx":
        if k == "Begin": return (store, False, 0), "S"
        if k == "Run":
            if msg[2]: return (store, True, tx), "F"
            return ((store, False, tx + msg[1]) if tx is not None else (store + msg[1], False, None)), "S"
        if k == "Commit": return ((store + tx, False, None) if tx is not None else s), "S"
        if k in ("Rollback", "Reset", "Close"): return (store, False, None), "S"
        return s, "S"
    if k == "Begin":
        return ((store, True, None), "F") if m == "begin-refused" else (s, "S")
    if k == "Run":
        w, fails = msg[1], msg[2]
        if fails: return (store + (w if m == "failed-run-writes" else 0), True, tx), "F"
        return (store + (0 if m == "run-not-committed" else w), False, tx), "S"
    if k == "Rollback" and m == "rollback-answers-failure": return s, "F"
    if k == "Reset": return (store, False, tx), "S"
    return s, "S"


def exec_(msgs, m):
    s, ans = (0, False, None), []
    for x in msgs:
        s, a = step(s, x, m)
        if x[0] != "Close": ans.append(a)
    return {"answers": ans, "count": s[0]}


def neo(msgs):  # the rule (client ledger), recorded only
    store, tx, failed = 0, None, False
    for x in msgs:
        k = x[0]
        if failed:
            if k in ("Reset", "Close"): tx, failed = None, False
            continue
        if k == "Begin": tx = 0
        elif k == "Run":
            if x[2]: failed = True
            elif tx is not None: tx += x[1]
            else: store += x[1]
        elif k == "Commit" and tx is not None: store, tx = store + tx, None
        elif k in ("Rollback", "Reset", "Close"): tx = None
    return store


# ------------------------------------------------------------------ port of the HTTP batch section (iteration 59, G1)
# statements: ("W", 1) a CREATE of one node, ("B",) a statement that fails in translation (names CREATE), ("R",) a read
def http_port(ro, stmts, m):
    named = lambda x: x[0] in ("W", "B")
    refused = (named(stmts[0]) if stmts else False) if m == "read-only-first-only" else any(named(x) for x in stmts)
    if ro and refused:
        if m == "http-read-only-runs-reads":
            return {"status": 403, "results": sum(1 for x in stmts if not named(x)), "errors": 1, "count": 0}
        return {"status": 403, "results": 0, "errors": 1, "count": 0}
    store, results, errors = 0, 0, 0
    for x in stmts:
        if x[0] == "B":
            errors += 1
            if m == "http-failure-writes": store += 1
            if m == "http-stop-at-failure": break
        else:
            results += 1
            if x[0] == "W": store += x[1]
    if m == "http-batch-atomic" and errors: store = 0
    status = 200 if (errors == 0 or m == "http-status-ok-on-error") else 400
    return {"status": status, "results": results, "errors": errors, "count": store}


def http_rule(ro, stmts):  # rule_batch: refused, failed or committed whole (recorded only)
    if ro and any(x[0] in ("W", "B") for x in stmts): return 0
    if any(x[0] == "B" for x in stmts): return 0
    return sum(x[1] for x in stmts if x[0] == "W")


# ------------------------------------------------------------------ independent raw Bolt 4.4 client
def rpack(v):
    if v is None: return b"\xc0"
    if isinstance(v, bool): return b"\xc3" if v else b"\xc2"
    if isinstance(v, int):
        if -16 <= v < 128: return struct.pack(">b", v)
        return b"\xca" + struct.pack(">i", v)
    if isinstance(v, str):
        b = v.encode(); n = len(b)
        return (bytes([0x80 | n]) if n < 16 else (b"\xd0" + bytes([n]) if n < 256 else b"\xd1" + struct.pack(">H", n))) + b
    if isinstance(v, dict): return bytes([0xA0 | len(v)]) + b"".join(rpack(k) + rpack(x) for k, x in v.items())
    raise TypeError(v)


class Raw:
    TAGS = {"Begin": 0x11, "Run": 0x10, "Pull": 0x3F, "Commit": 0x12, "Rollback": 0x13, "Reset": 0x0F, "Close": 0x02}

    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=20)
        self.s.sendall(b"\x60\x60\xb0\x17" + struct.pack(">IIII", 0x0404, 0, 0, 0))
        assert self._n(4) == struct.pack(">I", 0x0404)
        self.send(0x01, {"user_agent": "i56b-raw/1", "scheme": "basic", "principal": "neo4j", "credentials": "x"})
        assert self.summary() == "S"

    def _n(self, n):
        b = b""
        while len(b) < n:
            x = self.s.recv(n - len(b))
            if not x: raise ConnectionError("closed")
            b += x
        return b

    def send(self, tag, *fields):
        body = bytes([0xB0 | len(fields), tag]) + b"".join(rpack(f) for f in fields)
        self.s.sendall(struct.pack(">H", len(body)) + body + b"\x00\x00")

    def message(self):
        out = b""
        while True:
            n = struct.unpack(">H", self._n(2))[0]
            if n == 0:
                if out: return out
                continue
            out += self._n(n)

    def summary(self):
        while True:
            t = self.message()[1]
            if t == 0x71: continue
            return {0x70: "S", 0x7F: "F", 0x7E: "I"}.get(t, hex(t))

    def do(self, msg, text=None):
        k = msg[0]
        if k == "Close":
            self.send(0x02); self.s.close(); return None
        if k == "Run": self.send(0x10, text, {}, {})
        elif k == "Begin": self.send(0x11, {})
        elif k == "Pull": self.send(0x3F, {"n": -1})
        else: self.send(self.TAGS[k])
        return self.summary()


def main():
    import importlib.metadata as md
    import neo4j
    from iris_vector_graph import bolt_server as bs
    from iris_vector_graph.engine import IRISGraphEngine
    t0 = time.time(); cases = []
    RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
    P = f"i56b_{TAG}_"
    c2 = runtime.connect(); e2 = IRISGraphEngine(c2, embedding_dimension=768)
    loop = asyncio.new_event_loop()
    threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True).start()
    s0 = socket.socket(); s0.bind(("127.0.0.1", 0)); port = s0.getsockname()[1]; s0.close()
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"): os.environ.pop(k, None)
    srv = asyncio.run_coroutine_threadsafe(bs.start_tcp_bolt_server(lambda: e2, host="127.0.0.1", port=port), loop).result(10)
    c3 = runtime.connect(); e3 = runtime.engine(c3)

    def label(name): return f"I56B{TAG}{name.replace('_', '')}"

    def count(name):
        r = e3.execute_cypher(f"MATCH (n:{label(name)}) RETURN count(n) AS c", {})
        return r.rows[0][0] if r.rows else None

    def create(name, i): return f"CREATE (:{label(name)} {{id: '{P}{name}_{i}'}})"
    def bad(name): return f"CREATE (:{label(name)} {{id: '{P}{name}_bad'}}) RETURN 1 AS a UNION RETURN 2 AS b"

    W, B = ("Run", 1, False), ("Run", 1, True)
    raw_cases = {
        "R_rollback": [("Begin",), W, ("Pull",), ("Rollback",)],
        "R_rollback_two": [("Begin",), W, ("Pull",), W, ("Pull",), ("Rollback",)],
        "R_fail_rollback_reset": [("Begin",), W, ("Pull",), B, ("Pull",), ("Rollback",), ("Reset",)],
        "R_reset_in_tx": [("Begin",), W, ("Pull",), ("Reset",)],
        "R_close_in_tx": [("Begin",), W, ("Pull",), ("Close",)],
        "R_commit": [("Begin",), W, ("Pull",), ("Commit",)],
        "R_autocommit": [W, ("Pull",)],
        "R_empty_rollback": [("Begin",), ("Rollback",)],
        "R_fail_autocommit": [B, ("Pull",), ("Reset",), W, ("Pull",)],
    }
    for name, msgs in raw_cases.items():
        cl = Raw(port); ans = []; i = 0
        for x in msgs:
            text = None
            if x[0] == "Run":
                text = bad(name) if x[2] else create(name, i); i += 1
            a = cl.do(x, text)
            if a is not None: ans.append(a)
        if msgs[-1][0] != "Close":
            cl.do(("Close",))
        time.sleep(0.2)
        obs = {"answers": ans, "count": count(name)}
        cases.append({"name": name, "section": "R", "msgs": msgs, "observed": obs, "intended": neo(msgs),
                      "predict": (lambda m, msgs=msgs: exec_(msgs, m if m in BOLT_MUTS else None))})

    # D: the neo4j driver
    def drv():
        return neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", "x"), connection_timeout=10)

    def d_rollback(d, name):
        with d.session() as s:
            tx = s.begin_transaction(); tx.run(create(name, 0)).consume(); tx.rollback()
        return []

    def d_rollback_two(d, name):
        with d.session() as s:
            tx = s.begin_transaction(); tx.run(create(name, 0)).consume(); tx.run(create(name, 1)).consume(); tx.rollback()
        return []

    def d_fail(d, name):
        errs = []
        with d.session() as s:
            tx = s.begin_transaction(); tx.run(create(name, 0)).consume()
            try: tx.run(bad(name)).consume()
            except Exception as x: errs.append(type(x).__name__)
            try: tx.rollback()
            except Exception as x: errs.append("rollback:" + type(x).__name__)
        return errs

    def d_execute_write_abort(d, name):
        def work(t):
            t.run(create(name, 0)).consume(); raise RuntimeError("client aborts the unit of work")
        with d.session() as s:
            try: s.execute_write(work)
            except Exception as x: return [type(x).__name__]
        return []

    def d_commit(d, name):
        with d.session() as s:
            tx = s.begin_transaction(); tx.run(create(name, 0)).consume(); tx.commit()
        return []

    def d_autocommit(d, name):
        with d.session() as s: s.run(create(name, 0)).consume()
        return []

    def d_execute_write_ok(d, name):
        with d.session() as s: s.execute_write(lambda t: t.run(create(name, 0)).consume())
        return []

    def d_close_open_tx(d, name):
        s = d.session(); tx = s.begin_transaction(); tx.run(create(name, 0)).consume(); s.close()
        return []

    d_cases = {
        "D_tx_rollback": (d_rollback, [("Begin",), W, ("Pull",), ("Rollback",)], []),
        "D_tx_rollback_two": (d_rollback_two, [("Begin",), W, ("Pull",), W, ("Pull",), ("Rollback",)], []),
        "D_fail_then_rollback": (d_fail, [("Begin",), W, ("Pull",), B, ("Pull",), ("Rollback",), ("Reset",)], ["CypherSyntaxError"]),
        "D_execute_write_abort": (d_execute_write_abort, [("Begin",), W, ("Pull",), ("Rollback",)], ["RuntimeError"]),
        "D_session_closed_open_tx": (d_close_open_tx, [("Begin",), W, ("Pull",), ("Rollback",)], []),
        "D_tx_commit": (d_commit, [("Begin",), W, ("Pull",), ("Commit",)], []),
        "D_execute_write_ok": (d_execute_write_ok, [("Begin",), W, ("Pull",), ("Commit",)], []),
        "D_autocommit": (d_autocommit, [W, ("Pull",)], []),
    }
    with drv() as d:
        for name, (fn, msgs, errs_expected) in d_cases.items():
            errs = fn(d, name)
            time.sleep(0.2)
            obs = {"errors": errs, "count": count(name)}
            cases.append({"name": name, "section": "D", "msgs": msgs, "observed": obs, "intended": neo(msgs),
                          "predict": (lambda m, msgs=msgs, ee=errs_expected: {"errors": ee, "count": exec_(msgs, m if m in BOLT_MUTS else None)["count"]})})
    loop.call_soon_threadsafe(srv.close); time.sleep(0.3); loop.call_soon_threadsafe(loop.stop)

    # H: the HTTP /db/neo4j/tx/commit batch (iteration 59, review 56-58 G1), in-process FastAPI app on USER
    os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE="USER", BOLT_ENABLED="0")
    os.environ.setdefault("IRIS_USERNAME", "_SYSTEM"); os.environ.setdefault("IRIS_PASSWORD", "SYS")
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api
    WH, BH, RH = ("W", 1), ("B",), ("R",)
    h_cases = {
        "H_fail_middle": (False, [WH, BH, WH]),
        "H_fail_first": (False, [BH, WH]),
        "H_fail_last": (False, [WH, BH]),
        "H_two_failures": (False, [WH, BH, WH, BH]),
        "H_all_ok": (False, [WH, WH]),
        "H_reads_around_failure": (False, [RH, BH, RH]),
        "H_read_only_write": (True, [WH, RH]),
        "H_read_only_reads": (True, [RH, RH]),
        "H_read_only_write_last": (True, [RH, WH]),
    }
    with TestClient(cypher_api.app) as client:
        for name, (ro, stmts) in h_cases.items():
            body_st = []
            for i, x in enumerate(stmts):
                q = create(name, i) if x[0] == "W" else (bad(name) if x[0] == "B" else f"MATCH (n:{label(name)}) RETURN count(n) AS c")
                body_st.append({"statement": q, "parameters": {}})
            if ro: os.environ["IVG_READ_ONLY"] = "true"
            try:
                r = client.post("/db/neo4j/tx/commit", json={"statements": body_st})
            finally:
                os.environ.pop("IVG_READ_ONLY", None)
            j = r.json()
            obs = {"status": r.status_code, "results": len(j.get("results", [])), "errors": len(j.get("errors", [])), "count": count(name)}
            cases.append({"name": name, "section": "H", "msgs": [list(x) for x in stmts], "read_only": ro, "observed": obs,
                          "error_codes": sorted({x.get("code") for x in j.get("errors", [])}),
                          "intended": http_rule(ro, stmts),
                          "predict": (lambda m, ro=ro, stmts=stmts: http_port(ro, stmts, m if m in HTTP_MUTS else None))})

    # ---------------- verdict, sensitivities, tamper
    mism = [x["name"] for x in cases if x["predict"](None) != x["observed"]]
    sens = {m: [x["name"] for x in cases if x["predict"](m) != x["observed"]] for m in MUTS}
    tc = next(x for x in cases if x["name"] == "R_rollback")
    tampered = dict(tc["observed"], count=0)
    tamper_detected = tc["predict"](None) != tampered
    th = next(x for x in cases if x["name"] == "H_fail_middle")
    tampered_h = dict(th["observed"], count=0)
    tamper_h_detected = th["predict"](None) != tampered_h
    body = {"verdict": "AGREES" if not mism else "DISAGREES", "cases": len(cases), "comparisons": len(cases), "mismatches": mism,
            "sensitivities_detected_cases": {m: len(v) for m, v in sens.items()}, "all_sensitivities_detected": all(sens.values()),
            "rule_only_controls": ["rule-rollback-keeps"],
            "tamper": {"case": tc["name"], "tampered_observation": tampered, "detected": tamper_detected},
            "tamper_http": {"case": th["name"], "tampered_observation": tampered_h, "detected": tamper_h_detected},
            "departures_from_rule": [x["name"] for x in cases if x["observed"]["count"] != x["intended"]],
            "rule_only_controls_http": ["rule-http-keeps-earlier"],
            "fixture": runtime.NAME, "port": runtime.PORT, "tag": TAG, "prefix": P, "neo4j_driver": md.version("neo4j"),
            "elapsed_s": round(time.time() - t0, 1),
            "pin": bc.pin_identity(PIN), "model_json_sha256": bc.sha(HERE / "model.json"),
            "product_files": {p: bc.sha(PIN / p) for p in ["iris_vector_graph/bolt_server.py", "iris_vector_graph/_engine/query.py", "iris_vector_graph/cypher_api.py"]},
            "cells": [{k: v for k, v in x.items() if k != "predict"} | {"expected": x["predict"](None)} for x in cases],
            "scope": "The product's TCP Bolt listener (BoltSession._dispatch, _handle_run, _handle_reset; TcpBoltSession) over a "
                     "real engine, read by an independent raw Bolt 4.4 client and the neo4j Python driver; the final reader is a "
                     "second engine connection's count. Not covered: WebSocket Bolt (same _dispatch), Bolt 5 drivers other "
                     "than the Python one, the read-only gate inside a Bolt transaction. Section H (iteration 59): the HTTP /db/neo4j/tx/commit "
                     "route (neo4j_tx_commit, _run_cypher) in-process through FastAPI's TestClient on a real engine, read by a second "
                     "engine connection's count; /db/{db}/query/v2 and a statement that fails after writing part of its effect are not covered."}
    c2.close(); c3.close()
    out = bc.write_receipt("bolt_tx", Path(__file__).resolve(), body)
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "all_sensitivities_detected", "sensitivities_detected_cases", "departures_from_rule")}
                     | {"tamper": tamper_detected, "tamper_http": tamper_h_detected, "receipt": str(out.relative_to(REPO))}))
    for x in mism: print("MISMATCH", x, json.dumps([y for y in cases if y["name"] == x][0]["observed"]))
    for m, v in sens.items():
        if not v: print("UNDETECTED", m)


if __name__ == "__main__":
    main()
