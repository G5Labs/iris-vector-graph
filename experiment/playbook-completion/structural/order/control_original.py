#!/usr/bin/env python3
"""Control: the original check (tools/storage_order_check.py, unchanged) over the planted cases of the extended
scanner's self-test. Expected: the original flags only the one-literal prefix (t_lit.py:1) and misses the split
prefix, the first-row read, the slice cut and the ObjectScript first-row/alloc/cutoff sites the extension finds; the
extended scanner on the product finds those original 109 sites plus the new rules' sites.

    python control_original.py
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("orig", HERE.parents[1] / "tools" / "storage_order_check.py")
orig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orig)
import storage_order_scan as ext  # noqa: E402

src = (HERE / "storage_order_scan.py").read_text()
# the planted files of the extended self-test, re-read from its source text
ns = {}
start = src.index("    seeded = [")
end = src.index("    r = scan(seeded)")
exec("from pathlib import Path\n" + "\n".join(l[4:] for l in src[start:end].splitlines()), ns)
seeded = ns["seeded"]
o = orig.scan(seeded)
e = ext.scan(seeded)
orig_found = sorted({(Path(x["file"]).name, x["line"]) for x in o})
ext_cands = sorted({(Path(x["file"]).name, x["line"], x["rule"]) for x in e if x["auto"] == "candidate"})
ok = orig_found == [("t_lit.py", 1)] and len(ext_cands) >= 7
print("control", "PASS" if ok else "FAIL", json.dumps({"original_flags": orig_found, "extended_candidates": ext_cands}))
sys.exit(0 if ok else 1)
