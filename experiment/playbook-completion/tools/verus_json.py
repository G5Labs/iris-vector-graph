#!/usr/bin/env python3
"""Read the root crate's result from `cargo verus verify ... --output-json` output (shared by the proof runners).

A cold build (an empty target directory, verify.sh --clean) first verifies the dependencies (vstd, actors), whose
text summaries ("verification results:: N verified, M errors") come before the root crate's JSON document in the same
stream (operator diagnosis, supervision/proof-runner-prefix-diagnosis.json). Readers that called json.loads on the
whole stream failed closed on a successful run.

parse_verus_json(raw) returns the LAST JSON object in the stream that carries "verification-results", provided only
whitespace follows it; otherwise None (fail closed: no object, a truncated object, trailing text, or an object
without verification results). It never infers success from the text lines.

    python tools/verus_json.py --self-test [SAVED_STREAM ...]   # seeded cases plus any saved streams given
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def parse_verus_json(raw: str):
    dec = json.JSONDecoder()
    found = None
    i = raw.find("{")
    while i != -1:
        try:
            obj, end = dec.raw_decode(raw, i)
        except json.JSONDecodeError:
            i = raw.find("{", i + 1)
            continue
        if isinstance(obj, dict) and "verification-results" in obj:
            found = (obj, end)
        i = raw.find("{", end)
    if not found:
        return None
    obj, end = found
    if raw[end:].strip():
        return None
    return obj


def self_test(saved: list[str]) -> int:
    root = {"verification-results": {"encountered-error": False, "encountered-vir-error": False, "success": True,
                                     "verified": 94, "errors": 0, "is-verifying-entire-crate": True},
            "times-ms": {"total": 1, "smt": {"smt-run": 1, "rlimit-run": 1}}}
    doc = json.dumps(root, indent=1)
    failing = json.loads(doc)
    failing["verification-results"].update(success=False, errors=2, verified=92)
    cases = {
        "dependency-free stream": (doc, 94),
        "cold-build prefix": ("verification results:: 2059 verified, 0 errors\nverification results:: 121 verified, 0 errors\n" + doc + "\n", 94),
        "prefix containing braces": ("note: {vstd} built\n" + doc, 94),
        "failing root kept as failing": (json.dumps(failing), 92),
        "no JSON at all": ("verification results:: 2059 verified, 0 errors\n", None),
        "truncated root JSON": (doc[: len(doc) // 2], None),
        "text after the root JSON": (doc + "\nerror: something after\n", None),
        "object without verification results": ('{"a": 1}', None),
        "empty stream": ("", None),
    }
    bad = 0
    for name, (raw, want) in cases.items():
        got = parse_verus_json(raw)
        v = None if got is None else got["verification-results"]["verified"]
        ok = v == want
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}: verified={v} (expected {want})")
        if name == "failing root kept as failing" and got is not None and got["verification-results"]["success"]:
            bad += 1
            print("FAIL failing root read as success")
    for p in saved:
        raw = Path(p).read_text(errors="replace")
        got = parse_verus_json(raw)
        if got is None:
            bad += 1
            print(f"FAIL saved stream {p}: no root result")
        else:
            vr = got["verification-results"]
            print(f"ok   saved stream {p}: verified={vr['verified']} errors={vr['errors']} success={vr['success']}")
    print("self-test", "pass" if not bad else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test([a for a in sys.argv[1:] if a != "--self-test"]))
    print(json.dumps(parse_verus_json(sys.stdin.read()), indent=1))
