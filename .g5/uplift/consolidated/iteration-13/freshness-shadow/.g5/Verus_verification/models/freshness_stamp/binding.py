#!/usr/bin/env python3
"""Unit-level binding of freshness_stamp.rs to the pin's iris_vector_graph/freshness.py::Freshness.

    $RUN_DIR/venv/bin/python -I .g5/Verus_verification/models/freshness_stamp/binding.py

Real: Freshness.token, built_from, is_current, stale_stores (and _read_int) from the exported pin. Substituted: the
host (iris_vector_graph.host.Host) by a dict with IRIS $Data semantics (1 = value, 10 = children only, 11 = both).
Not run: TraversalKHop.Fresh (ObjectScript; Inspected). Expected outcomes: a hand transcription of the model's
read_int, token, built_from, is_current and stale_stores. Enumerated: every stamp and token state from
{unset, children only, "", 0, 1, 2, "0", "2"} (64 pairs) and, for tokens unset, 0 and 2, every ordered list of 0, 2 or 3 stores over those
stamps (1,731 lists). Detection: one changed observation and a product mutant reading an unset stamp as 0.
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import binding_common as bc  # noqa: E402

PIN_DIR = bc.import_pin()
from iris_vector_graph.freshness import Freshness  # noqa: E402

UNSET, CHILDREN = object(), object()
STATES = [UNSET, CHILDREN, "", 0, 1, 2, "0", "2"]


def spec_read(v):
    if v is UNSET or v is CHILDREN or v == "":
        return None
    return int(v)


def spec_token(t):
    r = spec_read(t)
    return 0 if r is None else r


def spec_current(s, t):
    return spec_read(s) == spec_token(t)


class Host:
    def __init__(self, token, stamps):
        self.d = {}
        self.children = set()
        for key, v in [(("^KG", "__version"), token)] + [(("^IVG.BuiltFrom", f"s{i}"), v) for i, v in enumerate(stamps)]:
            if v is CHILDREN:
                self.children.add(key)
            elif v is not UNSET:
                self.d[key] = v

    def is_defined(self, name, *subs):
        k = (name, *subs)
        return (1 if k in self.d else 0) + (10 if k in self.children else 0)

    def get(self, name, *subs):
        return self.d.get((name, *subs))

    def set(self, value, name, *subs):
        self.d[(name, *subs)] = value


def observe(cls, token, stamps):
    f = cls(Host(token, stamps))
    return {"token": f.token(), "built_from": [f.built_from(f"s{i}") for i in range(len(stamps))],
            "current": [f.is_current(f"s{i}") for i in range(len(stamps))],
            "stale": f.stale_stores([f"s{i}" for i in range(len(stamps))])}


def expect(token, stamps):
    return {"token": spec_token(token), "built_from": [spec_read(s) for s in stamps],
            "current": [spec_current(s, token) for s in stamps],
            "stale": [f"s{i}" for i, s in enumerate(stamps) if not spec_current(s, token)]}


def name(v):
    return "unset" if v is UNSET else "children-only" if v is CHILDREN else repr(v)


def compare(cls, mutate_first=False):
    mism, n = [], 0
    cases = [(t, [s]) for t, s in itertools.product(STATES, STATES)]
    cases += [(t, list(ss)) for t in (UNSET, 0, 2) for k in (0, 2, 3) for ss in itertools.product(STATES, repeat=k)]
    for t, ss in cases:
        got, want = observe(cls, t, ss), expect(t, ss)
        if mutate_first and n == 0:
            got = dict(got, current=[not c for c in got["current"]])
        n += 1
        if got != want:
            mism.append({"token": name(t), "stamps": [name(s) for s in ss], "expected": want, "observed": got})
    return n, mism


class UnsetIsZero(Freshness):
    def built_from(self, store):
        v = super().built_from(store)
        return 0 if v is None else v


def main():
    ident = bc.pin_identity(PIN_DIR)
    n, mism = compare(Freshness)
    _, d_obs = compare(Freshness, mutate_first=True)
    _, d_mut = compare(UnsetIsZero)
    detected = {"changed_current_in_one_observation": bool(d_obs), "mutant_unset_stamp_reads_zero": bool(d_mut)}
    verdict = "AGREES" if not mism and all(detected.values()) and ident["all_equal"] else "DISAGREES"
    body = {"verdict": verdict, "comparisons": n, "mismatch_count": len(mism), "mismatches": mism[:20], "detection": detected,
            "real": ["iris_vector_graph/freshness.py::Freshness._read_int", "::Freshness.token", "::Freshness.built_from",
                     "::Freshness.is_current", "::Freshness.stale_stores"],
            "substituted": "the host (a dict with $Data semantics)", "not_run": "TraversalKHop.Fresh (ObjectScript)",
            "expected_from": "hand transcription of the model's spec functions (this file)", "pin": ident}
    out = bc.write_receipt("freshness_stamp", Path(__file__).resolve(), body)
    print(f"freshness_stamp binding: {verdict} ({n} comparisons, {len(mism)} mismatches; detection {detected}) -> {out.relative_to(bc.REPO)}")
    return 0 if verdict == "AGREES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
