"""Narrow executable witnesses. These deliberately do not claim end-to-end reproduction."""
import asyncio
import importlib.util
import json
import logging
from pathlib import Path
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
logging.disable(logging.CRITICAL)
out = []


def load(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


# Reuse a real cursor scenario, including its scripted IRIS SQL provider.
p = rt.ROOT / ".g5/Verus_verification/models/embedded_no_data/binding.py"
m = load(p, "embedded_audit")
old = m.bc.write_receipt
captured = []
def capture(model, harness, body):
    captured.append(body)
    return rt.HERE / "embedded-component.json"
m.bc.write_receipt = capture
try:
    m.main()
finally:
    m.bc.write_receipt = old
body = captured[0]
assert body["verdict"] == "AGREES", body
assert body["observed_rerun"]["completed_row_runs"] == [0, 0, 1], body["observed_rerun"]
(rt.HERE / "embedded-component.json").write_text(json.dumps(body, indent=2, default=str) + "\n")
out.append(dict(ids=["bug-adp-001"], level="partial reproduced", scenario="real EmbeddedCursor.executemany", evidence="embedded-component.json",
                remaining_gate="IRIS must raise the unsupported-path error after a successful batch prefix; scripted iris.sql does not establish this native trigger"))

# Engine fusion arithmetic is real; list production and provider failure are substituted.
from iris_vector_graph._engine.vector import VectorMixin
class Fusion:
    kg_RRF_FUSE = VectorMixin.kg_RRF_FUSE
    def _fusion_leg_index(self, kinds, graph):
        return ("v", "ivf") if "ivf" in kinds else ("t", "bm25")
    def ivf_search(self, *a, **kw):
        return [("one", 1.0)]
    def bm25_search(self, *a, **kw):
        return []
f = Fusion()
got = f.kg_RRF_FUSE(2, 2, 2, 60, "[1]", "ordinary")
assert got[0][0] == "one" and abs(got[0][1] - (1/61 + 1/120)) < 1e-12, got
neighbor = f.kg_RRF_FUSE(2, 2, 2, 60, "[1]", "")
assert neighbor == got
out.append(dict(ids=["bug-srch-005"], level="partial reproduced", actual=got, expected=[["one",1/61]],
                neighbor="present-vector rank contributes 1/61; unused text leg still adds 1/120",
                remaining_gate="a real pair of vector/BM25 providers and final reader ranking contrast remain; absent-rank policy is still Q search.fusion.absent"))

# Execute only the ordinary as-built session cases; never run the old file's main or repair copies.
p = rt.ROOT / ".g5/uplift/consolidated/iteration-9/bolt-session-probe.py"
b = load(p, "bolt_audit")
neighbor = asyncio.run(b.case("ws", False, False, False, "none"))
assert neighbor["ordinary_result_preserved"], neighbor
for ident, fragmented, noop in [("bug-plt-101", True, False), ("bug-plt-102", False, True)]:
    got = asyncio.run(b.case("ws", fragmented, noop, False, "none"))
    assert not got["ordinary_result_preserved"], got
    out.append(dict(ids=[ident], level="partial reproduced", actual=got, neighbor=neighbor,
                    remaining_gate="actual WebSocket listener/socket and real database query provider; local transport and one-row engine adapter are substituted"))
(rt.HERE / "components.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
print(json.dumps(dict(partial_cases=len(out))))
