#!/usr/bin/env python3
"""Unit-level binding of rel_prop_text.rs to the pin's iris_vector_graph/prop_values.py::parse_rel_prop_text and
iris_vector_graph/_engine/query.py::_decode_rel_prop_text_columns.

    $RUN_DIR/venv/bin/python -I .g5/Verus_verification/models/rel_prop_text/binding.py

Real: parse_rel_prop_text (with parse_prop_text, decode_json_list_map and the two patterns) and
_decode_rel_prop_text_columns, from the exported pin. Substituted: the SQL layer (the text JSON_VALUE returns is given
directly; a result object stands in for the engine's). Expected outcomes: a hand transcription of the model's
`as_built` (Python's re.match semantics written out by character class, not by calling re) and of the reviewed
`decode`. Enumerated: every text of length 0-3 over {0, 1, 2, -, +, ., e, space, line break, U+0662} (1,111) and
named cases. The receipt lists every text where the product departs from the reviewed rule (finding bug-cyp-101).
Detection: a changed observation, and a mutant decoder with the repaired pattern (re.ASCII and \\Z).
"""
from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import binding_common as bc  # noqa: E402

PIN_DIR = bc.import_pin()
import iris_vector_graph.prop_values as pv  # noqa: E402
from iris_vector_graph._engine.query import _decode_rel_prop_text_columns  # noqa: E402

ALPHA = ["0", "1", "2", "-", "+", ".", "e", " ", "\n", "\u0662"]
NAMED = ["true", "false", "True", "False", "1", "0", "-7", "1.50", "[1]", "[1, 2]", "{\"a\": 1}", "[x", "{}", "[]",
         "01", "+1", ".5", "1.", "1e5", "12\n", "1.5\n", "1\u0662", "\u0661", " 1", "1 ", "-0", "007", "0.0"]


def ascii_digit(c):
    return "0" <= c <= "9"


def py_digit(c):
    return ascii_digit(c) or "\u0660" <= c <= "\u0669" or "\u06F0" <= c <= "\u06F9" or "\u0966" <= c <= "\u096F" or "\uFF10" <= c <= "\uFF19"


def int_digits(s, dig):
    return len(s) >= 1 and ((len(s) == 1 and s[0] == "0") or ("1" <= s[0] <= "9" and all(dig(c) for c in s[1:])))


def unsigned(u):
    return u[1:] if u[:1] == "-" else u


def int_text(u, dig):
    return int_digits(unsigned(u), dig)


def float_text(u, dig):
    s = unsigned(u)
    return any(s[k] == "." and int_digits(s[:k], dig) and len(s[k + 1:]) >= 1 and all(dig(c) for c in s[k + 1:])
               for k in range(1, len(s) - 1))


def parses(t):
    try:
        return isinstance(json.loads(t), (list, dict))
    except Exception:
        return False


def shaped(t):
    return len(t) >= 2 and ((t[0] == "[" and t[-1] == "]") or (t[0] == "{" and t[-1] == "}"))


def classify(v, t):
    if isinstance(v, bool):
        return ("bool", v)
    if isinstance(v, int):
        return ("int",)
    if isinstance(v, float):
        return ("float",)
    if isinstance(v, (list, dict)):
        return ("container",)
    return ("str", v == t)


def spec(t, as_built):
    if t == "true":
        return ("bool", True)
    if t == "false":
        return ("bool", False)
    if shaped(t) and parses(t):
        return ("container",)
    if as_built:
        mi = int_text(t, py_digit) or (t.endswith("\n") and int_text(t[:-1], py_digit))
        mf = float_text(t, py_digit) or (t.endswith("\n") and float_text(t[:-1], py_digit))
    else:
        mi, mf = int_text(t, ascii_digit), float_text(t, ascii_digit)
    if mi:
        return ("int",)
    if mf:
        return ("float",)
    return ("str", True)


def texts():
    for n in range(0, 4):
        for p in itertools.product(ALPHA, repeat=n):
            yield "".join(p)
    yield from NAMED


def compare(fn, mutate_first=False):
    mism, dep, n = [], [], 0
    for t in texts():
        got = classify(fn(t), t)
        want = spec(t, as_built=True)
        if mutate_first and n == 0:
            got = ("int",)
        n += 1
        if got != want:
            mism.append({"text": t, "expected_as_built": want, "observed": got})
        if got != spec(t, as_built=False):
            dep.append({"text": t, "observed": got, "reviewed_rule": spec(t, as_built=False)})
    return n, mism, dep


_INT = re.compile(r"-?(0|[1-9][0-9]*)\Z", re.ASCII)
_FLOAT = re.compile(r"-?(0|[1-9][0-9]*)\.[0-9]+\Z", re.ASCII)


def repaired(text):
    parsed = pv.decode_json_list_map(pv.parse_prop_text(text))
    if not isinstance(parsed, str):
        return parsed
    if _INT.match(parsed):
        return int(parsed)
    if _FLOAT.match(parsed):
        return float(parsed)
    return parsed


class Result:
    def __init__(self, columns, rows):
        self.columns, self.rows = columns, rows


class Q:
    def __init__(self, cols, arity):
        self.rel_prop_text_columns, self.return_arity = cols, arity


def arity_cases():
    out = []
    for cols, arity, columns in (([1], 2, ["a", "r.p"]), ([1], 3, ["a", "r.p"]), ([], 2, ["a", "r.p"]), ([0, 1], 2, ["r.q", "r.p"])):
        r = Result(columns, [["7", "7"], ["true", "x"]])
        _decode_rel_prop_text_columns(r, Q(cols, arity))
        decoded = len(columns) == arity
        want = [[(pv.parse_rel_prop_text(v) if (decoded and i in cols) else v) for i, v in enumerate(row)] for row in [["7", "7"], ["true", "x"]]]
        out.append({"cols": cols, "arity": arity, "columns": columns, "agrees": r.rows == want, "decoded": decoded})
    return out


def main():
    ident = bc.pin_identity(PIN_DIR)
    n, mism, dep = compare(pv.parse_rel_prop_text)
    _, d_obs, _ = compare(pv.parse_rel_prop_text, mutate_first=True)
    _, d_mut, _ = compare(repaired)
    ar = arity_cases()
    detected = {"changed_observation": bool(d_obs), "mutant_repaired_pattern": bool(d_mut)}
    expected_departures = all(("\n" in d["text"]) or ("\u0662" in d["text"]) for d in dep)
    verdict = "AGREES" if not mism and all(a["agrees"] for a in ar) and all(detected.values()) and ident["all_equal"] else "DISAGREES"
    body = {"verdict": verdict, "comparisons": n, "mismatch_count": len(mism), "mismatches": mism[:20], "detection": detected,
            "departures_from_reviewed_rule": {"count": len(dep), "all_are_newline_or_non_ascii_digit": expected_departures,
                                              "examples": dep[:12]},
            "arity_guard": ar,
            "real": ["iris_vector_graph/prop_values.py::parse_rel_prop_text", "::parse_prop_text", "::decode_json_list_map",
                     "::_CANONICAL_INT_RE", "::_CANONICAL_FLOAT_RE", "iris_vector_graph/_engine/query.py::_decode_rel_prop_text_columns"],
            "substituted": "the SQL layer: the JSON_VALUE text is given directly",
            "expected_from": "hand transcription of the model's as_built and decode by character class (this file)", "pin": ident}
    out = bc.write_receipt("rel_prop_text", Path(__file__).resolve(), body)
    print(f"rel_prop_text binding: {verdict} ({n} texts, {len(mism)} mismatches with as-built; {len(dep)} departures from the "
          f"reviewed rule, all newline/non-ASCII digit: {expected_departures}; detection {detected}) -> {out.relative_to(bc.REPO)}")
    return 0 if verdict == "AGREES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
