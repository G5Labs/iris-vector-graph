#!/usr/bin/env python3
"""Unit-level binding of index_declaration.rs to the pin's GraphSchema.ensure_adjacency_index.

    $RUN_DIR/venv/bin/python -I .g5/Verus_verification/models/index_declaration/binding.py

Real: iris_vector_graph/schema.py::GraphSchema.ensure_adjacency_index and ::GraphSchema.adjacency_index_kind from the
exported pin. Substituted: the database, by a scripted cursor that answers the catalog queries from an enumerated
catalog state and records each statement that changes something (DROP INDEX, the temporal backfill, CREATE INDEX),
as tests/unit/test_252_index_declaration.py does. Expected outcomes: a hand transcription of the model's plan.
Enumerated: callback classes (0, 1 or 2 compiled) x procedures class x ekey column x graph columns (1 or 2) x each
index functional, plain or absent (216 states), plus a second run on every state after applying the first run's
actions. Detection: a changed observation and a mutant that takes a plain index for the adjacency index.
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import binding_common as bc  # noqa: E402

PIN_DIR = bc.import_pin()
from iris_vector_graph.schema import GraphSchema  # noqa: E402

KINDS = ("functional", "plain", "absent")


class Cursor:
    def __init__(self, st):
        self.st, self.pending, self.ddl = dict(st), None, []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        st = self.st
        if "Name IN ('Graph.KG.AdjIndex', 'Graph.KG.LabelIndex')" in s:
            self.pending = [(st["callbacks"],)]
        elif "Name = 'Graph.KG.SqlProcs'" in s:
            self.pending = [(1 if st["procs"] else 0,)]
        elif "COLUMN_NAME = 'ekey'" in s:
            self.pending = [(1,)] if st["ekey"] else []
        elif "COLUMN_NAME = 'graph_id'" in s:
            self.pending = [(st["graph_cols"],)]
        elif "%Dictionary.CompiledIndex" in s:
            k = st["edges" if params[0] == "idx_edges_adj" else "labels"]
            self.pending = [] if k == "absent" else [("",)] if k == "plain" else [("Graph.KG.AdjIndex",)]
        elif s.startswith("DROP INDEX"):
            name = s.split()[2]
            self.ddl.append(("drop", name))
            self.st["edges" if name == "idx_edges_adj" else "labels"] = "absent"
        elif "backfill_temporal_rows" in s:
            self.ddl.append(("backfill",))
            self.pending = [(0,)]
        elif s.startswith("SELECT TOP 1 1 FROM"):
            self.pending = []
        elif s.startswith("CREATE INDEX"):
            name = s.split()[2]
            self.ddl.append(("create", name))
            self.st["edges" if name == "idx_edges_adj" else "labels"] = "functional"
        else:
            raise AssertionError(f"unexpected statement {s[:80]}")

    def fetchone(self):
        return self.pending[0] if self.pending else None

    def fetchall(self):
        return list(self.pending or [])


def spec_plan(st):
    if not (st["callbacks"] == 2 and st["procs"] and st["ekey"] and st["graph_cols"] == 2):
        return []
    out = []
    for idx, key in (("idx_edges_adj", "edges"), ("idx_labels_adj", "labels")):
        k = st[key]
        if k == "functional":
            continue
        if k == "plain":
            out.append(("drop", idx))
        if idx == "idx_edges_adj":
            out.append(("backfill",))
        out.append(("create", idx))
    return out


def states():
    for cb, pr, ek, gc, ke, kl in itertools.product((0, 1, 2), (False, True), (False, True), (1, 2), KINDS, KINDS):
        yield {"callbacks": cb, "procs": pr, "ekey": ek, "graph_cols": gc, "edges": ke, "labels": kl}


def compare(fn, mutate_first=False):
    mism, n = [], 0
    for st in states():
        cur = Cursor(st)
        fn(cur)
        got1, after = cur.ddl, cur.st
        cur2 = Cursor(after)
        fn(cur2)
        got = (got1, cur2.ddl)
        want_after = dict(st)
        for a in spec_plan(st):
            if a[0] == "create":
                want_after["edges" if a[1] == "idx_edges_adj" else "labels"] = "functional"
        want = (spec_plan(st), spec_plan(want_after))
        if mutate_first and n == 0:
            got = (got[0] + [("create", "idx_edges_adj")], got[1])
        n += 1
        if got != want:
            mism.append({"state": st, "expected": want, "observed": got})
    return n, mism


def plain_as_declared(cursor):
    orig = GraphSchema.adjacency_index_kind

    def kind(*a, **k):
        r = orig(*a, **k)
        return "functional" if r == "plain" else r
    GraphSchema.adjacency_index_kind = staticmethod(kind)
    try:
        return GraphSchema.ensure_adjacency_index(cursor)
    finally:
        GraphSchema.adjacency_index_kind = staticmethod(orig)


def main():
    ident = bc.pin_identity(PIN_DIR)
    n, mism = compare(GraphSchema.ensure_adjacency_index)
    _, d_obs = compare(GraphSchema.ensure_adjacency_index, mutate_first=True)
    _, d_mut = compare(plain_as_declared)
    detected = {"changed_observation": bool(d_obs), "mutant_plain_taken_as_declared": bool(d_mut)}
    verdict = "AGREES" if not mism and all(detected.values()) and ident["all_equal"] else "DISAGREES"
    body = {"verdict": verdict, "comparisons": n, "mismatch_count": len(mism), "mismatches": mism[:20], "detection": detected,
            "real": ["iris_vector_graph/schema.py::GraphSchema.ensure_adjacency_index", "::GraphSchema.adjacency_index_kind"],
            "substituted": "the database (a scripted cursor answering the catalog queries and recording DDL)",
            "expected_from": "hand transcription of the model's plan and apply (this file)", "pin": ident}
    out = bc.write_receipt("index_declaration", Path(__file__).resolve(), body)
    print(f"index_declaration binding: {verdict} ({n} catalog states, each run twice; {len(mism)} mismatches; detection {detected}) -> {out.relative_to(bc.REPO)}")
    return 0 if verdict == "AGREES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
