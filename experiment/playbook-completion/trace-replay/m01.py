"""Module 01 (install, schema): trace replay through ins_setup (first use).

Scenario firstuse (AUDITE was set up by the pin's own initialize_schema at 11:17 UTC): the harness removes the schema
record ^IVG.Deploy("schema") (as breadth probe p0103 did in AUDITA; restored byte for byte in the same capture), the
product's first-use check runs (schema_name.check_first_access, the function engine.py:1850-1866 runs on an engine's
first access) and accepts (F-0103: no record, marker class present); the record is restored; a second first-use check
on the restored namespace accepts.
"""
from __future__ import annotations

import trlib
from families_a import InsSetup, InsSetupRun

DESIGNS = ["as-built", "reviewed"]


def s_firstuse(cap: trlib.Capture):
    from iris_conn import Conn
    c = Conn(trlib.NS)
    try:
        saved = (c.o.get("^IVG.Deploy", "schema"), c.o.get("^IVG.Deploy", "schema", "recorded"))
        from iris_vector_graph.schema_name import marker_class
        cap.meta["marker_class"] = marker_class("Graph_KG")
        marker = bool(int(c.o.isDefined("^oddDEF", marker_class("Graph_KG")) or 0))
    finally:
        c.close()
    cap.meta["saved_record"] = [str(x) for x in saved]
    cap.meta["marker_class_present"] = marker

    def restore():
        c = Conn(trlib.NS)
        try:
            if c.o.get("^IVG.Deploy", "schema") is None and saved[0] is not None:
                c.o.set(saved[0], "^IVG.Deploy", "schema")
                c.o.set(saved[1], "^IVG.Deploy", "schema", "recorded")
        finally:
            c.close()
    cap.after = [restore]
    cap.begin()

    def remove(c):
        c.o.kill("^IVG.Deploy", "schema")
        return "record removed"
    cap.step("harness-remove-record", remove, env="record-removed", marker=marker)

    def first_use(c):
        from iris_vector_graph.schema_name import check_first_access
        check_first_access(c.o, "Graph_KG")
        return "accepted"
    cap.step("check_first_access", first_use, first_use=1, marker=marker)

    def put_back(c):
        c.o.set(saved[0], "^IVG.Deploy", "schema")
        c.o.set(saved[1], "^IVG.Deploy", "schema", "recorded")
        return "record restored"
    cap.step("harness-restore-record", put_back, env="record-restored", marker=marker)
    cap.step("check_first_access", first_use, first_use=2, marker=marker)


def s_setup(cap: trlib.Capture):
    """initialize_schema() replayed through ins_setup: the harness removes the schema record (as in firstuse), the
    pin's own initialize_schema() runs on the lane's namespace (classes unchanged: nothing recompiles; it re-records
    the schema, rebuilds ^KG, tunes the tables), then the product's first-use check accepts on the record it wrote.
    A few edges are written before the capture so the ^KG rebuild has rows to read."""
    from iris_conn import Conn
    from common import engine, reset
    reset()
    c = Conn(trlib.NS)
    try:
        e = engine(c)
        for i in range(5):
            e.create_edge(f"tr01s{i}", "R", f"tr01s{(i + 1) % 5}")
        saved = (c.o.get("^IVG.Deploy", "schema"), c.o.get("^IVG.Deploy", "schema", "recorded"))
        from iris_vector_graph.schema_name import marker_class
        cap.meta["marker_class"] = marker_class("Graph_KG")
        marker = bool(int(c.o.isDefined("^oddDEF", marker_class("Graph_KG")) or 0))
    finally:
        c.close()
    cap.meta["saved_record"] = [str(x) for x in saved]
    cap.meta["marker_class_present"] = marker

    def restore():
        c = Conn(trlib.NS)
        try:
            if c.o.get("^IVG.Deploy", "schema") is None and saved[0] is not None:
                c.o.set(saved[0], "^IVG.Deploy", "schema")
                c.o.set(saved[1], "^IVG.Deploy", "schema", "recorded")
        finally:
            c.close()
    cap.after = [restore]
    cap.begin()

    def remove(c):
        c.o.kill("^IVG.Deploy", "schema")
        return "record removed"
    cap.step("harness-remove-record", remove, env="record-removed", marker=marker)

    def setup(c):
        # the WARNING records setup logs while it runs: a failed DDL statement ("Schema setup warning", Tables) and a
        # failed ^KG bootstrap ("^KG bootstrap failed", Kg) are logged only (schema.py:2509-2511, 2680-2681; F-0102),
        # so the reply alone cannot say whether those steps failed
        import logging
        seen = []

        class H(logging.Handler):
            def emit(self, rec):
                seen.append(rec.getMessage()[:300])
        h = H(level=logging.WARNING)
        lg = logging.getLogger("iris_vector_graph")
        lg.addHandler(h)
        try:
            info = engine(c).initialize_schema()
        finally:
            lg.removeHandler(h)
        out = {k: (sorted(v) if isinstance(v, (set, frozenset)) else v) for k, v in dict(info).items()}
        out["log_warnings"] = seen
        return out
    cap.step("initialize_schema", setup, setup_run=1, marker=marker)

    def first_use(c):
        from iris_vector_graph.schema_name import check_first_access
        check_first_access(c.o, "Graph_KG")
        return "accepted"
    cap.step("check_first_access", first_use, first_use=1, marker=marker)


SCENARIOS = {"firstuse": s_firstuse, "setup": s_setup}
EXPECT = {"firstuse": [("ins_setup[as-built]1", InsSetup.I34, "F-0103")], "setup": []}


def families(trace, design):
    if trace["name"].endswith("-setup"):
        return [InsSetupRun(1, design)]
    return [InsSetup(1, design), InsSetup(2, design)]


def footprint(trace):
    return {"harness-remove-record": {"global:^IVG.Deploy"}, "harness-restore-record": {"global:^IVG.Deploy"},
            "check_first_access": set(),
            "initialize_schema": trlib.declared("01", ["py:IRISGraphEngine.initialize_schema"])}
