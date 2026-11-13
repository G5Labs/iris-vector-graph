#!/usr/bin/env python3
"""§3.5 decoder/status-map check for the ledger wire protocol (modules 11-14).

    python decoder_map_check.py [--self-test]

Every error code the ObjectScript ledger classes can put on the wire (Err("code", ...) and ErrLimit's "too_large")
must have a typed exception in the Python decoder iris_vector_graph/ledger/errors.py `_WIRE_MAP`; a code the decoder
maps but no server path emits is reported too (dead mapping). Codes are extracted from source text at the pin; the
self-test injects one unmapped server code and one dead mapping into copies and requires both to be reported.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CLS = sorted((REPO / "iris_src/src/Graph/KG").glob("Ledger*.cls"))
PY = REPO / "iris_vector_graph/ledger/errors.py"


def server_codes(texts) -> dict:
    codes: dict = {}
    for name, t in texts:
        for m in re.finditer(r'Err\("([a-z_]+)"', t):
            codes.setdefault(m.group(1), set()).add(name)
        for m in re.finditer(r'%Set\("error",\s*"([a-z_]+)"\)', t):
            codes.setdefault(m.group(1), set()).add(name)
    return codes


def decoder_codes(py_text: str) -> set:
    tree = ast.parse(py_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "_WIRE_MAP" for t in node.targets):
            return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    raise SystemExit("no _WIRE_MAP in decoder")


def check(texts, py_text) -> dict:
    s = server_codes(texts)
    d = decoder_codes(py_text)
    return {"server": sorted(s), "decoder": sorted(d), "unmapped": sorted(set(s) - d), "dead": sorted(d - set(s))}


def main() -> int:
    texts = [(p.name, p.read_text()) for p in CLS]
    py = PY.read_text()
    if "--self-test" in sys.argv:
        bad = check(texts + [("Injected.cls", 'Return ..Err("injected_code", "x")')],
                    py.replace('"invalid_target": InvalidRedactionTargetError,',
                               '"invalid_target": InvalidRedactionTargetError,\n    "never_sent": LedgerError,'))
        ok = bad["unmapped"] == ["injected_code"] and "never_sent" in bad["dead"]
        print("self-test", "PASS" if ok else "FAIL", bad["unmapped"], bad["dead"])
        return 0 if ok else 1
    r = check(texts, py)
    print(f"server codes {len(r['server'])}: {r['server']}")
    print(f"decoder codes {len(r['decoder'])}; unmapped {r['unmapped']}; dead {r['dead']}")
    return 0 if not r["unmapped"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
