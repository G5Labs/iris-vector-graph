#!/usr/bin/env python3
"""F-1110 probe (no IRIS): the published wire contract vs what the pin's client sends and the server answers.

    python experiment/playbook-completion/live/breadth-b/11_schema_probe.py

Validates Changeset.to_wire() of the pin's builder against specs/213-graph-revision-ledger/contracts/
changeset.schema.json ($defs/Changeset) with jsonschema (Draft 2020-12, as the upstream unit test does), and compares
the CommitError.error enum with the error codes the server classes can answer (`Err("<code>"` in Ledger*.cls and
ErrLimit's too_large). Writes $RUN_DIR/breadth-b/live/11-schema-probe.json.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
import jsonschema  # noqa: E402

from iris_vector_graph.ledger.changeset import Changeset  # noqa: E402

schema = json.loads((REPO / "specs/213-graph-revision-ledger/contracts/changeset.schema.json").read_text())
defs = schema["$defs"]
v = jsonschema.Draft202012Validator({"$ref": "#/$defs/Changeset", "$defs": defs})


def errs(cs):
    return [e.message[:200] for e in v.iter_errors(cs.to_wire())]


out = {}
a = Changeset(actor="a", actor_type="service")
a.create_node("x")
out["plain"] = errs(a)
b = Changeset(actor="a", actor_type="service")
b.create_temporal_edge("x", "P", "y", ts=1700000000)
out["create_temporal_edge"] = errs(b)
c = Changeset(actor="a", actor_type="service")
c.create_node("x")
c.post_commit_properties = {"x": {"k": "v"}}
out["post_commit_properties"] = errs(c)
enum = defs["CommitError"]["properties"]["error"].get("enum", [])
codes = set()
for p in (REPO / "iris_src/src/Graph/KG").glob("Ledger*.cls"):
    codes |= set(re.findall(r'Err\("([a-z_]+)"', p.read_text()))
codes.add("too_large")
out["commit_error_enum"] = sorted(enum)
out["server_codes"] = sorted(codes)
out["server_codes_missing_from_enum"] = sorted(codes - set(enum))
rec_ops = defs["MutationRecord"]["properties"]["op"].get("enum", [])
rec_kinds = defs["MutationRecord"]["properties"]["entity_kind"].get("enum", [])
out["record_op_enum_has_create_temporal_edge"] = "create_temporal_edge" in rec_ops
out["record_entity_kind_enum_has_temporal_edge"] = "temporal_edge" in rec_kinds
api = (REPO / "specs/213-graph-revision-ledger/contracts/ledger-api.md").read_text().splitlines()
out["ledger_api_commit_line"] = next((f"ledger-api.md:{i}: {ln[:220]}" for i, ln in enumerate(api, 1) if "commit(" in ln and "LedgerTransactionOpenError" in ln), None)
out["reproduced"] = bool(out["create_temporal_edge"] and out["post_commit_properties"] and out["server_codes_missing_from_enum"])
p = Path(os.environ["RUN_DIR"]) / "breadth-b" / "live" / "11-schema-probe.json"
p.write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
