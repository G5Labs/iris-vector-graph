#!/usr/bin/env python3
"""Unit-level binding of temporal_window_reader.rs to the real Python half at the pin.

    $RUN_DIR/venv/bin/python -I .g5/Verus_verification/models/temporal_window_reader/binding.py

What is real: iris_vector_graph/_engine/temporal_window.py (window_spec, TemporalWindowCursor) from the exported pin.
What is substituted: the server (Graph.KG.TemporalWindow) by a scripted native object that answers Open and Next from a
list of responses and records Close calls. The server's own filter and page producer are not run here (Inspected).

Expected outcomes come from a hand transcription of the model's spec functions (open, step, close, window_spec,
named_count), not from the product. Enumerated inputs: every script whose answers before the last are successful
pages that are not done (0-2 rows) and whose last answer is done (0-2 rows) or a failure, up to 4 answers (160
scripts), under four uses (iterate to the end; one event then close twice then next; a with block; abandon and
collect); and every combination of source, sources and source_prefix from a small set (45). Detection checks: one
observation with a changed Close count, a cursor mutant that ends the read on an empty page, and a window_spec mutant
that drops an empty list must each be reported as a mismatch.
"""
from __future__ import annotations

import gc
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import binding_common as bc  # noqa: E402

PIN_DIR = bc.import_pin()
import iris_vector_graph._engine.temporal_window as tw  # noqa: E402  (the pin's module)
from iris_vector_graph.exceptions import TemporalWindowError  # noqa: E402

# ------------------------------------------------------------------ the model's spec, transcribed


def spec_open(script):
    r = script[0]
    if r["fail"]:
        return dict(buf=[], closed=True, srv_open=False, closes=0, calls=1, pos=1, out=[], stopped=False, raised=True)
    return dict(buf=list(r["rows"]), closed=r["done"], srv_open=not r["done"], closes=0, calls=1, pos=1, out=[],
                stopped=False, raised=False)


def spec_close(c):
    c = dict(c, buf=[])
    if c["closed"]:
        return c
    return dict(c, closed=True, srv_open=False, closes=c["closes"] + 1)


def spec_step(c, script):
    if c["stopped"] or c["raised"]:
        return c
    if c["buf"]:
        return dict(c, buf=c["buf"][1:], out=c["out"] + [c["buf"][0]])
    if c["closed"] or c["pos"] >= len(script):
        return dict(c, stopped=True)
    r = script[c["pos"]]
    c1 = dict(c, calls=c["calls"] + 1, pos=c["pos"] + 1)
    if r["fail"]:
        return dict(spec_close(c1), raised=True)
    return dict(c1, closed=r["done"], srv_open=c1["srv_open"] and not r["done"], buf=c1["buf"] + list(r["rows"]))


def spec_next(c, script):
    """A __next__ call: steps until an emit, a stop or a raise."""
    n = len(c["out"])
    while True:
        c = spec_step(c, script)
        if c["stopped"] or c["raised"] or len(c["out"]) > n:
            return c


def spec_scenario(script, use):
    c = spec_open(script)
    if c["raised"]:
        return {"raised_at_open": True, "out": [], "closes": 0, "calls": 1, "raised": True}
    if use == "drain":
        while not (c["stopped"] or c["raised"]):
            c = spec_next(c, script)
    elif use in ("one_close_twice", "with_block", "abandon"):
        c = spec_next(c, script)
        if not c["raised"]:
            c = spec_close(c)
            if use == "one_close_twice":
                c = spec_close(c)
                c = spec_next(c, script)  # must stop without a call
    return {"raised_at_open": False, "out": c["out"], "closes": c["closes"], "calls": c["calls"], "raised": c["raised"]}


def spec_window(source, sources, prefix):
    named = (1 if source else 0) + (1 if sources is not None else 0) + (1 if prefix else 0)
    if named > 1:
        return "refused"
    return {"source": source or None, "sources": sources, "prefix": prefix or None}


# ------------------------------------------------------------------ the product, driven with a scripted server


class ScriptedNative:
    def __init__(self, script):
        self.script, self.i, self.calls, self.closes = script, 0, 0, 0

    def classMethodValue(self, cls, method, *args):
        assert cls == tw.WINDOW_CLASS and method in ("Open", "Next"), (cls, method)
        self.calls += 1
        r = self.script[self.i]
        self.i += 1
        if r["fail"]:
            raise RuntimeError("<scripted failure>")
        return json.dumps({"h": 7, "rows": [{"s": "s", "p": "p", "o": f"o{x}", "ts": x, "w": 1} for x in r["rows"]],
                           "done": 1 if r["done"] else 0})

    def classMethodVoid(self, cls, method, *args):
        assert method == "Close" and args == (7,), (method, args)
        self.closes += 1


def run_product(script, use, cursor_cls):
    nat = ScriptedNative(script)
    out, raised = [], False
    try:
        cur = cursor_cls(nat, "", {"start": 0, "end": 10, "dir": "out", "attrs": 0, "page": 2})
    except TemporalWindowError:
        return {"raised_at_open": True, "out": [], "closes": nat.closes, "calls": nat.calls, "raised": True}
    try:
        if use == "drain":
            for e in cur:
                out.append(e["ts"])
        elif use == "one_close_twice":
            try:
                out.append(next(cur)["ts"])
            except StopIteration:
                pass
            cur.close()
            cur.close()
            try:
                next(cur)
                out.append("UNEXPECTED")
            except StopIteration:
                pass
        elif use == "with_block":
            with cur as c2:
                try:
                    out.append(next(c2)["ts"])
                except StopIteration:
                    pass
        elif use == "abandon":
            try:
                out.append(next(cur)["ts"])
            except StopIteration:
                pass
            del cur
            gc.collect()
    except TemporalWindowError:
        raised = True
    return {"raised_at_open": False, "out": out, "closes": nat.closes, "calls": nat.calls, "raised": raised}


def scripts():
    ok = [{"fail": False, "rows": [], "done": False}, {"fail": False, "rows": [1], "done": False},
          {"fail": False, "rows": [1, 2], "done": False}]
    last = [{"fail": False, "rows": [], "done": True}, {"fail": False, "rows": [1], "done": True},
            {"fail": False, "rows": [1, 2], "done": True}, {"fail": True, "rows": [], "done": False}]
    for n in range(0, 4):
        for pre in itertools.product(ok, repeat=n):
            for end in last:
                s = [dict(p) for p in pre] + [dict(end)]
                k = 0
                for p in s:  # distinct row ids, in page order
                    p["rows"] = [k + i for i in range(len(p["rows"]))]
                    k += len(p["rows"])
                yield s


USES = ("drain", "one_close_twice", "with_block", "abandon")


def compare(cursor_cls, mutate_first=False):
    mism, n = [], 0
    for s in scripts():
        for use in USES:
            want, got = spec_scenario(s, use), run_product(s, use, cursor_cls)
            if mutate_first and n == 0:
                got = dict(got, closes=got["closes"] + 1)
            n += 1
            if want != got:
                mism.append({"script": s, "use": use, "expected": want, "observed": got})
    return n, mism


def compare_window(fn):
    vals_s = [None, "", "a"]
    vals_l = [None, [], [""], ["a"], ["a", "b"]]
    vals_p = [None, "", "t"]
    mism, n = [], 0
    for source, sources, prefix in itertools.product(vals_s, vals_l, vals_p):
        n += 1
        want = spec_window(source, sources, prefix)
        try:
            spec = fn(0, 10, source=source, sources=sources, source_prefix=prefix, predicates=None, direction="out",
                      attrs=True, page_size=10)
            got = {"source": spec.get("source"), "sources": spec.get("sources", None) if "sources" in spec else None,
                   "prefix": spec.get("prefix")}
            if "sources" not in spec:
                got["sources"] = None
        except ValueError:
            got = "refused"
        if want != got:
            mism.append({"args": [source, sources, prefix], "expected": want, "observed": got})
    return n, mism


class StopOnEmptyPage(tw.TemporalWindowCursor):
    """Product mutant: the read ends at an empty page (what test_an_empty_middle_page_does_not_end_the_read guards)."""

    def __next__(self):
        while not self._rows:
            if self.closed:
                raise StopIteration
            try:
                page = self._call("Next", self.handle, self._page)
            except TemporalWindowError:
                self.close()
                raise
            self.closed = bool(page.get("done")) or not page.get("rows")
            self._rows.extend(page.get("rows") or [])
        return tw.event(self._rows.popleft(), self._attrs)


def window_spec_drops_empty(start, end, **kw):
    if kw.get("sources") == []:
        kw["sources"] = None
    return tw.window_spec(start, end, **kw)


def main():
    ident = bc.pin_identity(PIN_DIR)
    n, mism = compare(tw.TemporalWindowCursor)
    nw, mism_w = compare_window(tw.window_spec)
    _, det_obs = compare(tw.TemporalWindowCursor, mutate_first=True)
    _, det_mut = compare(StopOnEmptyPage)
    _, det_win = compare_window(window_spec_drops_empty)
    detected = {"changed_close_count_in_one_observation": len(det_obs) > 0,
                "cursor_mutant_stop_on_empty_page": len(det_mut) > 0,
                "window_spec_mutant_drops_empty_list": len(det_win) > 0}
    verdict = "AGREES" if not mism and not mism_w and all(detected.values()) and ident["all_equal"] else "DISAGREES"
    body = {"verdict": verdict, "comparisons": {"cursor": n, "window_spec": nw},
            "mismatches": (mism + mism_w)[:20], "mismatch_count": len(mism) + len(mism_w),
            "detection": detected, "detected_counts": {"obs": len(det_obs), "cursor_mutant": len(det_mut), "window_mutant": len(det_win)},
            "real": ["iris_vector_graph/_engine/temporal_window.py::window_spec", "::TemporalWindowCursor (all methods)", "::_server_call", "::event"],
            "substituted": "the server Graph.KG.TemporalWindow (scripted Open/Next/Close answers)",
            "expected_from": "hand transcription of the model's spec functions open, step, close, window_spec (this file)",
            "pin": ident}
    out = bc.write_receipt("temporal_window_reader", Path(__file__).resolve(), body)
    print(f"temporal_window_reader binding: {verdict} ({n} cursor + {nw} window_spec comparisons, "
          f"{body['mismatch_count']} mismatches; detection {detected}) -> {out.relative_to(bc.REPO)}")
    return 0 if verdict == "AGREES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
