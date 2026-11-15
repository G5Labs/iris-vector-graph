"""HD-0902 probe: in shadow mode, what does a caller see when the native executor raises?

Sources: spec 253 US1 ("a shadow mode runs both paths for each query and fails on any difference"), FR-006 ("raise on
any difference"), FR-007 ("Any exception in the native executor MUST fall back to the SQL path and log a warning once
per reason per engine"); docs/dev/TCK.md:261-270 ("every natively planned query also runs on the SQL path ... A
difference therefore surfaces in the run as a raised NativeMismatch"); query.py:2069-2077, 2146-2152, 2226-2231 (pin).
Fault injection, in this probe's process only (no product file or class changes): the engine's _run_native_plan is
wrapped (a) to raise, (b) to return the real native answer plus one extra row.
Steps (graph ia-0902, a-[:R]->b), engine.cypher_shadow = True, compiled plans off (interpreter):
  0. baseline: native answers (the _native_answers counter rises), no NativeMismatch.
  1. injected native exception, twice: does execute_cypher raise, which rows come back, how many WARNINGs?
  2. control: injected wrong native answer -> NativeMismatch expected.
Oracle (readings of HD-0902):
  step 1 raises                          -> option (b) (shadow fails on native error)
  step 1 answers SQL rows, warns once     -> option (a), as built; a shadow run cannot see the fault but in a log line
  step 2 raises NativeMismatch           -> shadow does catch differences (control)
Contract under test is FR-007 (fallback, warn once per reason): pass when step 1 falls back and warns once; the record
says the shadow run did not count the native failure.
"""
from __future__ import annotations

import logging

import _common as C

G = "ia-0902"
Q = f"USE GRAPH '{G}' MATCH (a {{node_id: 'ia0902:a'}})-[:R]->(b) RETURN b.node_id AS b"


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


def main():
    c = C.conn()
    e = C.engine(c)
    cap = Capture()
    logging.getLogger("iris_vector_graph").addHandler(cap)
    verdict = ("incomplete", "did not finish")
    try:
        e.create_node("ia0902:a", labels=["IaN0902"], graph=G)
        e.create_node("ia0902:b", labels=["IaN0902"], graph=G)
        e.create_edge("ia0902:a", "R", "ia0902:b", graph=G)
        e.cypher_shadow = True
        n0 = e.__dict__.get("_native_answers", 0)
        try:
            r0 = e.execute_cypher(Q)
            base = {"rows": [list(x) for x in r0.rows], "native_answered": e.__dict__.get("_native_answers", 0) - n0}
        except Exception as ex:  # noqa: BLE001
            base = {"raised": f"{type(ex).__name__}: {ex}"}
        C.obs(step="baseline_shadow", **base)

        real = e._run_native_plan

        def boom(plan, parameters):
            raise RuntimeError("ia0902 injected native executor fault")

        e._run_native_plan = boom
        cap.records.clear()
        n1 = e.__dict__.get("_native_answers", 0)
        step1 = []
        for i in range(2):
            try:
                r = e.execute_cypher(Q)
                step1.append({"try": i, "rows": [list(x) for x in r.rows], "error": getattr(r, "error", None)})
            except Exception as ex:  # noqa: BLE001
                step1.append({"try": i, "raised": f"{type(ex).__name__}: {str(ex)[:200]}"})
        warns = [m for m in cap.records if "native Cypher fell back" in m]
        C.obs(step="injected_exception_shadow", results=step1, warnings=warns,
              native_answered=e.__dict__.get("_native_answers", 0) - n1)

        def wrong(plan, parameters):
            r = real(plan, parameters)
            r.rows = list(r.rows) + [["ia0902:phantom"]]
            return r

        e._run_native_plan = wrong
        try:
            r2 = e.execute_cypher(Q)
            ctrl = {"rows": [list(x) for x in r2.rows]}
        except Exception as ex:  # noqa: BLE001
            ctrl = {"raised": f"{type(ex).__name__}: {str(ex)[:200]}"}
        C.obs(step="control_wrong_answer_shadow", **ctrl)
        e._run_native_plan = real

        fell_back = all("raised" not in s and s["rows"] == [["ia0902:b"]] for s in step1)
        ctrl_caught = "NativeMismatch" in ctrl.get("raised", "")
        if base.get("native_answered") != 1:
            verdict = ("incomplete", f"baseline did not run natively: {base}")
        elif fell_back and len(warns) == 1 and ctrl_caught:
            verdict = ("pass", "shadow mode: an injected native exception did not raise; both calls answered the SQL "
                               "rows and one WARNING was logged (FR-007 holds; option a as built), while an injected "
                               "wrong native answer raised NativeMismatch (control). A shadow run therefore reports a "
                               "native difference but not a native failure.")
        else:
            verdict = ("fail" if not fell_back else "incomplete",
                       f"step1 {step1}, warnings {len(warns)}, control {ctrl}")
    finally:
        logging.getLogger("iris_vector_graph").removeHandler(cap)
        e.cypher_shadow = False
        C.obs(step="erase", removed=e.erase_graph(G))
        c.close()
    C.verdict(*verdict)


if __name__ == "__main__":
    main()
