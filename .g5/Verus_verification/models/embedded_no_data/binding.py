#!/usr/bin/env python3
"""Unit-level binding of embedded_no_data.rs to the pin's iris_vector_graph/embedded.py.

    $RUN_DIR/venv/bin/python -I .g5/Verus_verification/models/embedded_no_data/binding.py

Real: EmbeddedCursor.execute and .executemany, _is_no_data, _no_data_ok, _is_ddtab_error, _exec_inline,
_inline_params and _sql_statement_execute from the exported pin. Substituted: IRIS's in-process `iris.sql` module (a
scripted object whose prepare/execute/exec answer by path and row) and the `iris` module that _sql_statement_execute
imports (a stub serving %SQL.Statement). Expected outcomes: a hand transcription of the model's execute, chain,
first_pass_row, pass1, fallback and executemany. Enumerated: execute over 5 verbs x 2 parameter forms x 5 x 5 x 5 path
outcomes (1,250); executemany over every batch of one or two rows with each row's form and its first-pass, fallback
exec and fallback %SQL.Statement outcomes (2 x 5 x 5 x 5 per row: 250 + 62,500). Detection: one changed row count,
a mutant that folds every error, and a mutant whose fallback resumes at the failed row.
"""
from __future__ import annotations

import itertools
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import binding_common as bc  # noqa: E402

PIN_DIR = bc.import_pin()
import iris_vector_graph.embedded as emb  # noqa: E402

OUT = ("rs", "c100", "cause100", "ddtab", "other")


class SQLError(Exception):
    def __init__(self, msg, sqlcode):
        super().__init__(msg)
        self.sqlcode = sqlcode


def raise_for(kind):
    if kind == "c100":
        raise SQLError("", 100)
    if kind == "cause100":
        try:
            raise SQLError("", 100)
        except SQLError as inner:
            raise SQLError("wrapped", -1) from inner
    if kind == "ddtab":
        raise SQLError("<UNIMPLEMENTED> ddtab", -400)
    if kind == "other":
        raise SQLError("refused", -104)


class RS:
    def columnCount(self):
        return 1

    def columnName(self, i):
        return "c"

    def _GetProperty(self, name):
        return 1


class Script:
    """Answers each call by (path, row id) and logs it. Paths: stmt (iris.sql.prepare(...).execute), exec
    (iris.sql.exec), sqlstmt (%SQL.Statement)."""

    def __init__(self, table):
        self.table, self.log = table, []

    def answer(self, path, row):
        kind = self.table[(path, row)]
        self.log.append((path, row, kind))
        if kind == "rs":
            return RS()
        raise_for(kind)


def row_of(text_or_params):
    s = " ".join(map(str, text_or_params)) if isinstance(text_or_params, (list, tuple)) else str(text_or_params)
    for tok in s.replace("'", " ").split():
        if tok.startswith("r") and tok[1:].isdigit():
            return int(tok[1:])
    raise AssertionError(f"no row id in {s!r}")


def make_sql(script):
    class Stmt:
        def execute(self, *params):
            return script.answer("stmt", row_of(params))

    sql = types.SimpleNamespace()
    sql.prepare = lambda q: Stmt()
    sql.exec = lambda text: script.answer("exec", row_of(text))
    return sql


def install_iris_stub(script):
    class SqlStatement:
        def _Prepare(self, q):
            return 1

        def _Execute(self, *params):
            return script.answer("sqlstmt", row_of(params))

    stub = types.ModuleType("iris")
    stub.cls = lambda name: types.SimpleNamespace(_New=lambda: SqlStatement())
    sys.modules["iris"] = stub


# ------------------------------------------------------------------ the model's spec, transcribed

def spec_execute(verb, inline, first, second, third):
    if verb == "START TRANSACTION":
        return ("skipped", None, -1)

    def err(k):
        return {"c100": (True, False, False), "cause100": (False, True, False), "ddtab": (False, False, True),
                "other": (False, False, False)}[k]
    if inline:
        c1 = ("got", True) if first == "rs" else ("got", False) if err(first)[0] else ("fail", err(first))
    else:
        c1 = ("got", True) if first == "rs" else ("fail", err(first))
    if c1[0] == "fail" and c1[1][2]:
        if second == "rs":
            c1 = ("got", True)
        elif not err(second)[2]:
            c1 = ("fail", err(second))
        elif third == "rs":
            c1 = ("got", True)
        else:
            c1 = ("fail", (False, err(third)[0], False))
    if c1[0] == "fail":
        e = c1[1]
        return ("done", False, 0) if (e[0] or e[1]) else ("raised", None, None)
    rs = c1[1]
    no_data = (not rs) and verb.split()[0] in ("UPDATE", "DELETE", "INSERT")
    return ("done", rs, 0 if no_data else -1)


def spec_executemany(rows):
    """rows: [(inline, first, fexec, fstmt)] -> (log, count, raised)"""
    def no_data(k):
        return k in ("c100", "cause100")
    log, count = [], 0
    failed = None
    for i, (inline, first, fexec, fstmt) in enumerate(rows):
        ok = first == "rs" or no_data(first)
        if not ok:
            failed = first
            break
        log.append(i)
        count += 1
    if failed is None:
        return (log, count, False)
    if failed != "ddtab":
        return (log, count, True)
    count = 0
    for i, (inline, first, fexec, fstmt) in enumerate(rows):
        ok = fexec == "rs" or no_data(fexec) or (fexec == "ddtab" and (fstmt == "rs" or no_data(fstmt)))
        if not ok:
            return (log, count, True)
        log.append(i)
        count += 1
    return (log, count, False)


# ------------------------------------------------------------------ the product

def run_execute(cursor_cls, verb, inline, first, second, third):
    table = {}
    params = ["", "r0"] if inline else ["x", "r0"]
    if inline:
        table[("exec", 0)] = first
        # the second path is iris.sql.exec again: answer it with `second` on its second call
    else:
        table[("stmt", 0)] = first
        table[("exec", 0)] = second
    table[("sqlstmt", 0)] = third
    script = Script(table)
    if inline:
        calls = {"n": 0}

        def ex(text):
            calls["n"] += 1
            kind = first if calls["n"] == 1 else second
            script.log.append(("exec", 0, kind))
            if kind == "rs":
                return RS()
            raise_for(kind)
        sql = make_sql(script)
        sql.exec = ex
    else:
        sql = make_sql(script)
    install_iris_stub(script)
    cur = cursor_cls(iris_sql=sql)
    try:
        cur.execute(f"{verb} t SET a = ? WHERE b = ?" if verb != "START TRANSACTION" else verb, params)
    except Exception:
        return ("raised", None, None)
    if verb == "START TRANSACTION":
        return ("skipped", None, cur.rowcount)
    return ("done", cur._rs is not None, cur.rowcount)


def run_executemany(cursor_cls, rows):
    table = {}
    seq = []
    for i, (inline, first, fexec, fstmt) in enumerate(rows):
        seq.append(["", f"r{i}"] if inline else ["x", f"r{i}"])
    script = Script(table)
    pass1 = {i: r[1] for i, r in enumerate(rows)}
    fall = {i: r[2] for i, r in enumerate(rows)}
    stmt_t = {i: r[3] for i, r in enumerate(rows)}
    seen_exec = {}

    class Stmt:
        def execute(self, *params):
            i = row_of(params)
            k = pass1[i]
            script.log.append(("stmt", i, k))
            if k == "rs":
                return RS()
            raise_for(k)

    def ex(text):
        i = row_of(text)
        # an inline row's first-pass call is exec; any later exec of that row is the fallback's
        n = seen_exec.get(i, 0)
        seen_exec[i] = n + 1
        k = pass1[i] if (rows[i][0] and n == 0 and not fallback_started["v"]) else fall[i]
        script.log.append(("exec", i, k))
        if k == "rs":
            return RS()
        raise_for(k)

    fallback_started = {"v": False}
    orig_ddtab = emb._is_ddtab_error

    def watch(exc):
        r = orig_ddtab(exc)
        if r:
            fallback_started["v"] = True
        return r
    emb._is_ddtab_error = watch

    class SqlStatement:
        def _Prepare(self, q):
            return 1

        def _Execute(self, *params):
            i = row_of(params)
            k = stmt_t[i]
            script.log.append(("sqlstmt", i, k))
            if k == "rs":
                return RS()
            raise_for(k)
    stub = types.ModuleType("iris")
    stub.cls = lambda name: types.SimpleNamespace(_New=lambda: SqlStatement())
    sys.modules["iris"] = stub
    sql = types.SimpleNamespace(prepare=lambda q: Stmt(), exec=ex)
    cur = cursor_cls(iris_sql=sql)
    raised = False
    try:
        cur.executemany("UPDATE t SET a = ? WHERE b = ?", seq)
    except Exception:
        raised = True
    finally:
        emb._is_ddtab_error = orig_ddtab
    completed = [i for (path, i, k) in script.log if k in ("rs", "c100", "cause100")]
    # a fallback exec that raised ddtab then completed through %SQL.Statement counts once (its sqlstmt entry)
    return (completed, None if raised else cur.rowcount, raised)


def compare_execute(cursor_cls, mutate_first=False):
    mism, n = [], 0
    for verb, inline, a, b, c in itertools.product(("UPDATE", "DELETE", "INSERT", "SELECT", "START TRANSACTION"),
                                                   (False, True), OUT, OUT, OUT):
        got = run_execute(cursor_cls, verb, inline, a, b, c)
        want = spec_execute(verb, inline, a, b, c)
        if mutate_first and n == 0:
            got = (got[0], got[1], 99)
        n += 1
        if got != want:
            mism.append({"verb": verb, "inline": inline, "paths": [a, b, c], "expected": want, "observed": got})
    return n, mism


def compare_executemany(cursor_cls, limit=None):
    mism, n = [], 0
    per_row = list(itertools.product((False, True), OUT, OUT, OUT))
    batches = [[r] for r in per_row] + [list(p) for p in itertools.product(per_row, repeat=2)]
    for rows in batches[:limit]:
        log, count, raised = spec_executemany(rows)
        want = (log, None if raised else count, raised)
        got = run_executemany(cursor_cls, rows)
        n += 1
        if got != want:
            mism.append({"rows": rows, "expected": want, "observed": got})
    return n, mism


class FoldEverything(emb.EmbeddedCursor):
    def execute(self, sql, params=None):
        try:
            return super().execute(sql, params)
        except Exception:
            self._rs, self.rowcount = None, 0


class ResumeFallback(emb.EmbeddedCursor):
    """Mutant: the batch fallback resumes at the row that failed (the repaired variant)."""

    def executemany(self, sql, seq):
        seq = list(seq)
        iris_sql = self._get_iris_sql()
        count, done = 0, 0
        try:
            stmt = iris_sql.prepare(sql)
            for params in seq:
                if any(isinstance(p, str) and p == "" for p in params):
                    emb._no_data_ok(emb._exec_inline, iris_sql, sql, params)
                else:
                    emb._no_data_ok(stmt.execute, *params)
                count += 1
                done += 1
        except Exception as exc:
            if not emb._is_ddtab_error(exc):
                raise
            for params in seq[done:]:
                try:
                    emb._no_data_ok(iris_sql.exec, emb._inline_params(sql, list(params)))
                except Exception as exc2:
                    if not emb._is_ddtab_error(exc2):
                        raise
                    emb._no_data_ok(emb._sql_statement_execute, sql, list(params))
                count += 1
        self.rowcount = count


def main():
    ident = bc.pin_identity(PIN_DIR)
    n1, m1 = compare_execute(emb.EmbeddedCursor)
    n2, m2 = compare_executemany(emb.EmbeddedCursor)
    _, d1 = compare_execute(emb.EmbeddedCursor, mutate_first=True)
    _, d2 = compare_execute(FoldEverything)
    _, d3 = compare_executemany(ResumeFallback, limit=3000)
    # the as-built rerun, observed on the real cursor: a batch whose second row's first pass raises an unsupported-path
    # error after the first row ran
    rerun_case = [(False, "rs", "rs", "rs"), (True, "ddtab", "rs", "rs")]
    rerun_obs = run_executemany(emb.EmbeddedCursor, rerun_case)
    detected = {"changed_rowcount_in_one_observation": bool(d1), "mutant_fold_every_error": bool(d2),
                "mutant_fallback_resumes_at_failed_row": bool(d3)}
    verdict = "AGREES" if not m1 and not m2 and all(detected.values()) and ident["all_equal"] else "DISAGREES"
    body = {"verdict": verdict, "comparisons": {"execute": n1, "executemany": n2}, "mismatch_count": len(m1) + len(m2),
            "mismatches": (m1 + m2)[:20], "detection": detected,
            "observed_rerun": {"rows": rerun_case, "completed_row_runs": rerun_obs[0], "rowcount": rerun_obs[1],
                               "note": "row 0 runs in the first pass and again in the fallback (bug-adp-001, suspected: "
                                       "whether IRIS raises an unsupported-path error after a successful prepare is not shown)"},
            "real": ["iris_vector_graph/embedded.py::EmbeddedCursor.execute", "::EmbeddedCursor.executemany", "::_is_no_data",
                     "::_no_data_ok", "::_is_ddtab_error", "::_exec_inline", "::_inline_params", "::_sql_statement_execute"],
            "substituted": "iris.sql (scripted prepare/execute/exec) and the iris module's %SQL.Statement",
            "expected_from": "hand transcription of the model's spec functions (this file)", "pin": ident}
    out = bc.write_receipt("embedded_no_data", Path(__file__).resolve(), body)
    print(f"embedded_no_data binding: {verdict} ({n1} execute + {n2} executemany comparisons, {len(m1) + len(m2)} mismatches; "
          f"detection {detected}; rerun observed {rerun_obs}) -> {out.relative_to(bc.REPO)}")
    return 0 if verdict == "AGREES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
