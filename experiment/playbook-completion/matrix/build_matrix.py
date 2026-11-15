#!/usr/bin/env python3
"""Build the machine-readable obligation matrix (matrix/obligations.json) and its summary (matrix/MATRIX.md).

    python build_matrix.py [--check]
    python build_matrix.py --import-census $RUN_DIR/followup/writer-census.json   # writes matrix-input/writer-census-obligations.json

Starting inventories (original submission 9c3719c1, read-only): 19 modules, cells, 61 decisions, 138 premises, 197
findings, 8 not-implemented behaviours, 83 writer obligations. Completion evidence: evidence/runs/*.json and every
lane's machine-readable output (modules/NN.json, findings/audit/NN.json, footprints/NN.json, intent/*.json,
models/*/RESULTS.json, proofs/RESULTS.json, validation/results.json, matrix/orchestrator_status.json,
matrix-input/*.json).

Every (gate, module) cell gets a status from the strongest available source, in this order: an explicit lane or
orchestrator status with evidence; otherwise `open` with "no evidence". Statuses: closed, failed (a product defect
violates the obligation), open, blocked (exact dependency), not-applicable (with a source reason). IDs, overlaps and
evidence grades are preserved: an original finding keeps its F-id and grade; the audit disposition is added beside it.

matrix-input/*.json may hold `cells` (they replace the cell they name), `supplements` (added to the cell they name:
`add_evidence`, `as_built_findings`, `add_remaining`, and `reopen` with a reason, which can only turn a closed cell
open) and `extra_cells` (cells beyond the gate x module catalog, e.g.
one per census obligation; they take findings only from their own `as_built_findings`).

Product obligation (separate from the verification status), review R2-01:
- `level` is normalised to method / model / product (the input's wording is kept in `level_detail`);
- `fails` when the cell has as-built evidence of a violation: a reproduced finding attached by gate (by module, or
  from any module for a product-scope cell), a finding the cell names in `as_built_findings`, a cited run with result
  `fail`, a cited as-built model check or located control (a control encoding the pin's behaviour of a finding) with
  result `expected-violation`, or a lane status `failed`; `product_basis` lists which;
- `intent-undecided` when the only such evidence belongs to findings whose disposition is intent-undecided (or to a
  located control of a decision only): the behaviour is observed, the intent is not settled (CONVENTIONS);
- `holds-live` / `holds-inspected` only for a census (invariant, writer) pair discharged at the pin by a lemma or guard
  (writesets/DISCHARGES.json), graded by that discharge's evidence;
- `holds-in-model-only` for a closed model-level cell with no such evidence; `unknown` otherwise; `n/a` when the
  cell is not applicable.

--check fails if the committed obligations.json differs from what this script would write, if any inventory count
differs from the stated starting inventory, if a cell's remaining/reason says "as-built fails", "as-built
reproduces" or "as-built violate(s)" beside a product label other than `fails`, if a level does not normalise, if an
`as_built_findings` id is not a reproduced or intent-undecided audit finding, or if the census input does not match
its registered run.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
UPLIFT = ROOT.parent / "playbook-uplift"
sys.path.insert(0, str(UPLIFT / "tools"))
from ontology_index import parse_module  # noqa: E402

EXPECTED = {"modules": 19, "cells": 904, "decisions": 61, "premises": 138, "findings": 197, "not_implemented": 8,
            "writer_obligations": 83}
STATUSES = ["closed", "failed", "open", "blocked", "not-applicable"]
LEVELS = ("method", "model", "product")
PO = ["fails", "intent-undecided", "holds-live", "holds-inspected", "holds-as-detection", "holds-in-model-only", "unknown", "n/a"]
REPRODUCED = ("reproduced-live", "reproduced-test", "reproduced-model", "confirmed-source", "product-defect")
UNDECIDED = ("intent-undecided",)
AS_BUILT_TEXT = re.compile(r"as-built (fails|reproduc\w*|violates?\b)", re.I)
FID = re.compile(r"\bF-C?\d{4}\b")
HDID = re.compile(r"\bHD-\d{4}\b")
LOCATED_CONTROL = re.compile(r"^control_\w+ \((F-C?\d{4}|HD-\d{4})")
RUN_PREFIXES = ("run:", "mc:", "live:", "trace:", "check:", "registry:")
CENSUS_INPUT = ROOT / "matrix-input" / "writer-census-obligations.json"
DISCHARGES = ROOT / "writesets" / "DISCHARGES.json"
CENSUS_RUN = "followup-writer-census"


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def ids_in(text: str, prefix: str) -> list:
    return sorted(set(re.findall(rf"^#+\s*({prefix}-\d{{4}})\b", text, re.M)))


def inventories() -> dict:
    errors: list = []
    mods = []
    stm = {}
    for p in sorted((UPLIFT / "ontology").glob("[0-9][0-9]-*.md")):
        m = parse_module(p, errors, len(stm) + len(mods))
        mods.append((p, m))
        stm.update((s.id, s) for s in m.statements)
    out = {"modules": [], "findings": [], "decisions": [], "premises": [], "not_implemented": [], "cells": []}
    for p, m in mods:
        nn = p.name[:2]
        text = p.read_text()
        scope = re.search(r"^Scope:\s*(.+?)(?:\n\n|\n##)", text, re.S | re.M)
        out["modules"].append({"nn": nn, "code": getattr(m, "code", None) or p.stem, "file": p.name,
                               "statements": len(m.statements), "scope": scope.group(1).strip() if scope else ""})
        for s in m.statements:
            if "not-implemented" in getattr(s, "evidence", ""):
                out["not_implemented"].append({"id": s.id, "module": nn, "text": s.text})
        for c in getattr(m, "cells", []):
            d = c if isinstance(c, dict) else c.__dict__
            out["cells"].append({"module": nn, **{k: d.get(k) for k in ("entity", "state", "command", "outcome",
                                                                          "statements", "decision")}})
    # findings / decisions / premises: per-module files and the module-12..14 files
    for kind, prefix, sub, top in (("findings", "F", "findings", "FINDINGS.md"), ("decisions", "HD", "decisions", "DECISIONS.md"),
                                   ("premises", "P", "trust", "TRUST.md")):
        seen = set()
        for f in sorted((UPLIFT / sub).glob("*.md")):
            for i in ids_in(f.read_text(), prefix):
                if i not in seen:
                    seen.add(i)
                    out[kind].append({"id": i, "module": f.stem, "source": f"{sub}/{f.name}"})
        for i in ids_in((UPLIFT / top).read_text(), prefix):
            if i not in seen:
                seen.add(i)
                out[kind].append({"id": i, "module": i.split("-")[1][:2], "source": top})
    ws = load(UPLIFT / "semantics" / "writesets.json", {})
    out["writer_obligations"] = [{"pair": k, **(v if isinstance(v, dict) else {"discharge": v})}
                                 for k, v in ws.get("coverage", {}).items()]
    out["parse_errors"] = errors
    return out


def level_of(gate: str) -> str:
    """What a gate's evidence is about: the verification method, a model, or the product."""
    if gate.startswith(("3.3-", "3.3a-")) or gate in ("3.7-explorers",):
        return "model"
    if gate.startswith(("3.1-", "3.2-", "3.8-", "5")) or gate in ("3.4-generator", "3.7-differential"):
        return "method"
    return "product"


def norm_level(raw, gate: str, errors: list, where: str):
    """(level, level_detail): one of LEVELS, and the input's wording when it differed."""
    if raw is None or raw == "":
        return level_of(gate), None
    r = str(raw).strip().lower()
    if r in LEVELS:
        return r, None
    if r.startswith("as-built"):
        return "product", str(raw)
    if "model" in r:
        return "model", str(raw)
    errors.append(f"{where}: level {raw!r} does not normalise to {LEVELS}")
    return level_of(gate), str(raw)


def runs() -> dict:
    return {p.stem: load(p) for p in sorted((ROOT / "evidence" / "runs").glob("*.json"))}


def resolve(e, reg: dict):
    """The registry id an evidence item names, or None. Accepts 'id', 'run:id' (mc:, live:, trace:, check:), a
    dict {kind, ref}, 'id (annotation ...)', a path ending in the id, and the breadth-B short ids 'mNN-...' that
    were registered as 'b-mc-mNN-...'."""
    if isinstance(e, dict):
        e = e.get("ref", "")
    s = str(e).strip()
    if not s:
        return None
    for x in reg:
        if s == x or s == "run:" + x or s.endswith("/" + x) or s.endswith(x + ".json"):
            return x
    for p in RUN_PREFIXES:
        if s.startswith(p):
            s = s[len(p):].strip()
            break
    tok = s.split()[0].rstrip(".,;:)") if s.split() else ""
    if tok in reg:
        return tok
    if re.match(r"^m\d\d-", tok) and "b-mc-" + tok in reg:
        return "b-mc-" + tok
    return None


def evidence_file(e: str) -> bool:
    """A committed artifact named by an evidence item: a path relative to the completion directory or the repository,
    optionally prefixed by a grade ('inspected:') and followed by ':lines' or ' (annotation)'."""
    s = str(e).strip()
    for p in ("inspected:", "file:", "path:"):
        if s.startswith(p):
            s = s[len(p):].strip()
    s = s.split(" (")[0].split()[0] if s.split() else ""
    s = re.sub(r":[0-9][0-9,\-]*$", "", s)
    return bool(s) and ((ROOT / s).exists() or (ROOT.parent.parent / s).exists())


def audit_records() -> list:
    out = []
    skip = {s.strip() for s in os.environ.get("MATRIX_EXCLUDE", "").split(",") if s.strip()}
    for p in sorted((ROOT / "findings" / "audit").glob("*.json")):
        if str(p.relative_to(ROOT)) in skip:   # an in-progress lane's file (orchestrator snapshots only)
            continue
        recs = load(p, [])
        for r in (recs if isinstance(recs, list) else recs.get("findings", []) + recs.get("new_findings", [])):
            out.append((p.stem, r))
    return out


def gate_tokens(f: dict) -> set:
    return {str(g).split()[0] for g in (f.get("gates") or []) if str(g).strip()}


# ---------------------------------------------------------------------------------------------- census import

# Writer -> module, from the module scopes of the ontology ("Production files"); where a scope splits a file, the
# function's module. Reason recorded with each cell.
WRITER_MODULE = [
    (r"^<any SQL client>::INSERT INTO Graph_KG\.ledger_revisions$", "11", "module 11 owns the immutable revision table"),
    (r"Graph/KG/Adjacency\.cls::", "04", "Adjacency.cls is module 04's (scope: 'the one writer')"),
    (r"Graph/KG/EdgeScan\.cls::", "04", "EdgeScan.cls is module 04's (scope: 'the old write names')"),
    (r"Graph/KG/Eraser\.cls::", "12", "Eraser.cls is module 12's"),
    (r"Graph/KG/FHIRGraph\.cls::", "15", "FHIRGraph.cls is module 15's"),
    (r"Graph/KG/Snapshot\.cls::", "18", "Snapshot.cls is module 18's"),
    (r"Graph/KG/TemporalPolicy\.cls::", "05", "TemporalPolicy.cls is module 05's"),
    (r"_engine/legacy\.py::", "01", "legacy.py is module 01's (setup and upgrades)"),
    (r"_engine/nodes_edges\.py::(erase_graph|delete_nodes_by_prefix|drop_graph)$", "12",
     "module 12 owns erase_graph / delete_nodes_by_prefix / drop_graph"),
    (r"_engine/nodes_edges\.py::", "03", "module 03 owns nodes_edges.py except the erasure entry points"),
    (r"_engine/schema\.py::(reify_edge|get_reifications|delete_reification)$", "15",
     "module 15's scope names the reification methods"),
    (r"_engine/schema\.py::(materialize_inference|retract_inference)$", "01",
     "no module's scope names these functions; assigned to 01, the owner of _engine/schema.py (setup and helpers)"),
    (r"_engine/snapshot\.py::", "18", "snapshot.py is module 18's"),
    (r"_engine/temporal\.py::", "05", "temporal.py is module 05's"),
    (r"iris_vector_graph/bulk_loader\.py::", "03", "bulk loads are module 03's"),
    (r"^iris_vector_graph/schema\.py::", "01", "module 01 owns the DDL, the 3.2.0 rescue and the graph_id upgrade steps"),
    (r"stores/iris_sql_store\.py::", "17", "module 17 owns the SQL adapter (stores/iris_sql_store.py)"),
    (r"iris_vector_graph/dbapi_utils\.py::", "17", "module 17's scope names dbapi_utils.py"),
    (r"migrations/graph_scoped_embeddings\.py::", "06", "module 06 owns the embedding migrations"),
]
# (invariant, writer) pairs whose violation a reproduced finding already shows, with the reason.
CENSUS_FINDINGS = {
    ("INV-text", "iris_vector_graph/_engine/legacy.py::copy_ledger_history"): (
        ["F-C1306"], "F-C1306 (live): copy_ledger_history leaves the copied Graph_KG.ledger_revisions rows, and "
                     "redaction does not clear them (legacy.py:606-646)"),
}
GAP_FINDINGS = (["F-1801"], "F-1801 (live): a replacing restore lays the archive's ledger, tombstones and redaction "
                            "state over the live ones (c18-live-ledger-overlay; core-m3-as-built-F1801-keys)")


def writer_module(w: str):
    for pat, nn, why in WRITER_MODULE:
        if re.search(pat, w):
            return nn, why
    return None, None


def import_census(path: Path) -> int:
    rec = load(ROOT / "evidence" / "runs" / f"{CENSUS_RUN}.json")
    data = path.read_bytes()
    if rec is None or hashlib.sha256(data).hexdigest() != rec["log_sha256"]:
        print(f"{path}: not the registered log of {CENSUS_RUN}")
        return 1
    d = json.loads(data)
    cells = []

    def cell(kind, n, inv, writer, stores, extra):
        nn, why = writer_module(writer)
        if nn is None:
            raise SystemExit(f"no module for writer {writer}")
        c = {"gate": "3.3a-writesets", "module": nn, "obligation_id": f"{kind}-{n:03d}", "kind": kind,
             "invariant": inv, "writer": writer, "stores": stores, "module_basis": why, "status": "open",
             "evidence": [f"run:{CENSUS_RUN}"], **extra}
        return c

    for n, o in enumerate(sorted(d["new_obligations"], key=lambda o: (o["writer"], o["invariant"])), 1):
        extra = {"remaining": "census obligation: no preservation lemma, guard or recorded finding discharges this "
                              "(invariant, writer) pair; the writer is declared by no plan"}
        if (o["invariant"], o["writer"]) in CENSUS_FINDINGS:
            f, why = CENSUS_FINDINGS[(o["invariant"], o["writer"])]
            extra = {"remaining": "census obligation, violated as built: " + why, "as_built_findings": f}
        cells.append(cell("WS-OBL", n, o["invariant"], o["writer"], o["stores"], extra))
    for n, o in enumerate(sorted(d["conditional_obligations"], key=lambda o: (o["writer"], o["invariant"])), 1):
        cells.append(cell("WS-COND", n, o["invariant"], o["writer"], o["stores"],
                          {"remaining": "conditional census obligation: applies if the run-time table name is a "
                                        "content or ledger table (unresolved by the lexical census)"}))
    for n, o in enumerate(sorted(d["gap_obligations"], key=lambda o: o["invariant"]), 1):
        w = o["sites"][0].split()[0].rsplit(":", 1)[0] + "::" + o["sites"][0].split()[1]
        cells.append(cell("WS-GAP", n, o["invariant"], w, [o["undeclared_store"]],
                          {"plan": o["plan"], "sites": o["sites"], "as_built_findings": GAP_FINDINGS[0],
                           "remaining": f"write-set gap: plan {o['plan']} does not declare {o['undeclared_store']}, "
                                        f"which {o['sites'][0]} writes; violated as built: {GAP_FINDINGS[1]}"}))
    out = {"_doc": "Per-obligation cells of the corrected writer census (review R2-02), generated by "
                   "matrix/build_matrix.py --import-census from the registered log of followup-writer-census "
                   "($RUN_DIR/followup/writer-census.json). Each (invariant, writer) obligation, conditional "
                   "obligation and write-set gap is one open cell of gate 3.3a-writesets in the writer's module.",
           "source_run": CENSUS_RUN, "source_sha256": rec["log_sha256"],
           "declared": {"obligations": len(d["new_obligations"]), "conditional": len(d["conditional_obligations"]),
                        "write_set_gaps": len(d["gap_obligations"]),
                        "ledger_writers_outside_ledger_classes": d["ledger_writers_outside_ledger_classes"]},
           "extra_cells": cells}
    CENSUS_INPUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"wrote {CENSUS_INPUT.relative_to(ROOT)}: {len(cells)} cells", dict(Counter(c['kind'] for c in cells)))
    return 0


# ------------------------------------------------------------------------------------------------------ build

def main() -> int:
    if "--import-census" in sys.argv:
        return import_census(Path(sys.argv[sys.argv.index("--import-census") + 1]))
    inv = inventories()
    counts = {k: len(inv[k]) for k in ("modules", "findings", "decisions", "premises", "not_implemented", "cells",
                                         "writer_obligations")}
    gates = load(HERE / "gates.json")["gates"]
    reg = runs()
    lane_modules = {p.stem: load(p, {}) for p in sorted((ROOT / "modules").glob("*.json"))}
    records = audit_records()
    orch = load(HERE / "orchestrator_status.json", {"cells": []})
    problems: list = []

    cells = []
    nns = [m["nn"] for m in inv["modules"]]
    explicit = {(c["gate"], c.get("module", "product")): c for c in orch.get("cells", [])}
    supplements = defaultdict(list)
    extra = []
    census_inputs = {}
    # lane inputs (e.g. matrix-input/correspondence_status.json) take precedence for the cells they state
    for f in sorted((ROOT / "matrix-input").glob("*.json")):
        data = load(f, [])
        for c in (data if isinstance(data, list) else data.get("cells", [])):
            explicit[(c["gate"], c.get("module", "product"))] = {**c, "source": f"matrix-input/{f.name}"}
        if isinstance(data, dict):
            for s in data.get("supplements", []):
                supplements[(s["gate"], s.get("module", "product"))].append({**s, "source": f"matrix-input/{f.name}"})
            for c in data.get("extra_cells", []):
                extra.append({**c, "source": f"matrix-input/{f.name}"})
            if data.get("source_run") == CENSUS_RUN:
                census_inputs[f.name] = data
    disp = {}
    for _, r in records:
        disp[r["id"]] = r.get("disposition")
    audits_by_mod = defaultdict(list)
    for stem, r in records:
        audits_by_mod[str(r.get("module") or stem)[:2]].append(r)
    # which findings each registered run evidences: the findings that cite it, and the F-ids its record names
    run_findings = defaultdict(set)
    for _, r in records:
        for e in r.get("evidence") or []:
            rid = resolve(e, reg)
            if rid:
                run_findings[rid].add(r["id"])
    for rid, rec in reg.items():
        run_findings[rid] |= set(FID.findall(str((rec or {}).get("observes", ""))))

    def as_built_run(rid: str, rec: dict) -> bool:
        if rec.get("result") != "expected-violation":
            return False
        if rec.get("design") == "as-built" or "as-built" in rid:
            return True
        return rec.get("kind") == "control" and bool(LOCATED_CONTROL.match(str(rec.get("observes", ""))))

    def derive(c: dict, nn: str, gid: str, per_obligation: bool) -> None:
        """Set product_obligation, findings, findings_undecided and product_basis on a finished cell."""
        where = f"{gid}/{nn}" + (f"/{c.get('obligation_id')}" if c.get("obligation_id") else "")
        basis, undecided = [], []
        hits, hits_u = [], []
        if not per_obligation:
            pool = [r for _, r in records] if nn == "product" else audits_by_mod.get(nn, [])
            for f in pool:
                if gid in gate_tokens(f):
                    if f.get("disposition") in REPRODUCED:
                        hits.append(f["id"])
                    elif f.get("disposition") in UNDECIDED:
                        hits_u.append(f["id"])
        for fid in c.get("as_built_findings", []):
            if disp.get(fid) in REPRODUCED:
                hits.append(fid)
            elif disp.get(fid) in UNDECIDED:
                hits_u.append(fid)
            else:
                problems.append(f"{where}: as_built_findings {fid} is not a reproduced or intent-undecided finding "
                                f"(disposition {disp.get(fid)})")
        hits, hits_u = sorted(set(hits)), sorted(set(hits_u))
        basis += [f"finding {f}" for f in hits]
        undecided += [f"finding {f}" for f in hits_u]
        if c.get("_lane_failed"):
            basis.append(f"lane status failed ({c.get('source') or 'orchestrator'})")
        if c.get("_explicit_po") == "fails":
            basis.append(f"stated fails by {c.get('source') or 'orchestrator'}")
        # a lemma/guard discharge of one write-set pair may cite a run that failed on ANOTHER pair; only runs the
        # discharge names in failed_runs_other_pairs (with a reason; writesets/RUN-PAIRS.json) are ignored here
        # (review R4-02): any other failed run still makes the cell fail
        other = set(c.get("failed_runs_other_pairs") or [])
        if c["level"] != "method":
            for rid in c["cited_runs"]:
                if rid in other:
                    continue
                rec = reg.get(rid) or {}
                if not (rec.get("result") == "fail" or as_built_run(rid, rec)):
                    continue
                tied = run_findings.get(rid, set())
                rep = {f for f in tied if disp.get(f) in REPRODUCED}
                und = {f for f in tied if disp.get(f) in UNDECIDED}
                hd_only = not tied and HDID.search(str(rec.get("observes", "")))
                label = f"run {rid} ({rec.get('result')})"
                if rep or (not tied and not hd_only):
                    basis.append(label)
                elif und or hd_only:
                    undecided.append(label + " of " + (", ".join(sorted(und)) or "a decision only"))
        if hits:
            c["findings"] = hits
        if hits_u:
            c["findings_undecided"] = hits_u
        if basis:                     # a reproduced failure is shown even on a not-applicable cell
            po = "fails"
        elif undecided:
            po = "intent-undecided"
        elif c["status"] == "not-applicable":
            po = "n/a"
        elif c["level"] == "model" and c["status"] == "closed":
            po = "holds-in-model-only"
        else:
            po = c.get("_explicit_po") or "unknown"
        c["product_obligation"] = po
        if basis or undecided:
            c["product_basis"] = {"fails": basis, "intent_undecided": undecided}
        c.pop("_lane_failed", None)
        c.pop("_explicit_po", None)

    def finish(c: dict, gid: str, nn: str, per_obligation: bool = False) -> dict:
        c = dict(c)
        where = f"{gid}/{nn}"
        sups = [] if per_obligation else supplements.get((gid, nn), [])
        for s in sups:
            c["evidence"] = list(c.get("evidence", [])) + [e for e in s.get("add_evidence", [])
                                                           if e not in c.get("evidence", [])]
            c["as_built_findings"] = sorted(set(c.get("as_built_findings", [])) | set(s.get("as_built_findings", [])))
        lvl, detail = norm_level(c.get("level"), gid, problems, where)
        c["level"] = lvl
        if detail and "level_detail" not in c:
            c["level_detail"] = detail
        if "product_obligation" in c:
            c["_explicit_po"] = c.pop("product_obligation")
        ev = c.get("evidence", [])
        ids = sorted({x for x in (resolve(e, reg) for e in ev) if x})
        # decisive: the run settled something (a pass, an expected violation, or a product failure)
        passing = [i for i in ids if (reg[i] or {}).get("result") in ("pass", "expected-violation", "fail")]
        nonpass = [i for i in ids if i not in passing]
        files = [e for e in map(str, ev) if evidence_file(e)]
        st = c.get("status", "open")
        if st == "failed":            # lanes' "failed" = a product defect: the verification itself is done
            st = "closed"
            c["_lane_failed"] = True
        lifted = [s for s in sups if s.get("reopen") and s.get("lift") == "census-discharged"
                  and nn in census_any and census_open.get(nn, 0) == 0]
        reopen = [s["reopen"] for s in sups if s.get("reopen") and s not in lifted]
        if lifted:
            c["remaining"] = " ".join([x for x in [str(c.get("remaining") or "").strip()] if x]
                                      + ["Census reopen lifted: every census cell of this module is discharged "
                                         "(writesets/DISCHARGES.json)."])
        if reopen and st == "closed":  # a supplement may only reopen a cell, never close one
            st = "open"
            c["remaining"] = " ".join([x for x in [str(c.get("remaining") or "").strip()] if x]
                                      + ["Reopened: " + r for r in reopen])
        if gid == "3.8-findings-disposed" and st == "closed":
            st = "open"
            c["remaining"] = ("every finding is recorded with evidence and a disposition; a fix or a maintainer "
                              "decision per finding is outside this observation-only audit")
        if st == "closed":
            if passing:
                c["evidence_grade"] = "registered-run"
            elif files:
                c["evidence_grade"] = "inspected"
            else:
                st = "open"
                c["remaining"] = "closed claim cites no registered run or committed artifact"
            if nonpass and not passing:
                st = "open"
                c["remaining"] = f"closed claim cites only non-decisive runs {nonpass}"
        c["status"] = st
        c["cited_runs"] = ids
        added = [s["add_remaining"] for s in sups if s.get("add_remaining")]
        if added:
            c["remaining"] = " ".join([x for x in [c.get("remaining", "").strip()] if x] + added)
        if sups:
            c["supplemented_by"] = sorted({s["source"] for s in sups})
        derive(c, nn, gid, per_obligation)
        if not c.get("as_built_findings"):
            c.pop("as_built_findings", None)
        return c

    # write-set discharges (writesets lane, queue Q17c): one entry per census obligation id
    dis = load(DISCHARGES, {}) if DISCHARGES.exists() and not os.environ.get("MATRIX_SKIP_DISCHARGES") else {}
    dis = {k: v for k, v in dis.items() if not str(k).startswith("_")}
    applied = set()
    for i, c in enumerate(extra):
        d = dis.get(c.get("obligation_id")) if c["gate"] == "3.3a-writesets" else None
        if not d:
            continue
        applied.add(c["obligation_id"])
        kind = d.get("discharge")
        c = {**c, "discharge": kind, "discharge_grade": d.get("grade"), "discharge_source": "writesets/DISCHARGES.json"}
        for k in ("failed_runs_other_pairs", "failed_runs_other_pairs_reason", "holds_as", "depends_on", "context_runs"):
            if d.get(k):
                c[k] = d[k]
        refs = [str(e) for e in d.get("evidence", [])]
        for r in refs:
            if resolve(r, reg) is None:
                f = r.split(":")[0] if not r.startswith("run:") else r
                if not ((ROOT / f).exists() or (ROOT.parent.parent / f).exists()):
                    problems.append(f"{c['obligation_id']}: discharge evidence {r} is neither a registered run nor a file")
        # the census run defines the obligation; the discharge's own evidence decides it
        c["obligation_source"] = [e for e in c.get("evidence", [])]
        c["evidence"] = [r.split(":")[0] if resolve(r, reg) is None and not r.startswith("run:") else r for r in refs]
        c["discharge_evidence"] = refs
        # runs that did not decide anything (e.g. a blocked live attempt) are context, not discharge evidence
        ctx = [r for r in refs if resolve(r, reg) and (reg[resolve(r, reg)] or {}).get("result")
               not in ("pass", "fail", "expected-violation")]
        ctx += [r for r in refs if str(r).replace("run:", "") in set(d.get("context_runs") or [])]
        if ctx and d.get("grade") == "inspected":
            c["evidence"] = [e for e in c["evidence"] if e not in ctx]
            c["context_runs"] = ctx
        if kind in ("lemma", "guard"):
            # a per-pair discharge about the pin's own writer code: product level, graded by its evidence
            c["level"] = "product"
            c["product_obligation"] = ("holds-as-detection" if d.get("holds_as") == "detection"
                                       else "holds-live" if d.get("grade") == "live" else "holds-inspected")
        if kind in ("lemma", "guard", "finding"):
            c["status"] = "closed"
            if kind == "finding":
                c["as_built_findings"] = sorted(set(c.get("as_built_findings", [])) | set(d.get("findings", [])))
            how = f", holds as {d['holds_as']}" if d.get("holds_as") else ""
            dep = (f"; its evidence uses fixture setup authorized by operator clarification "
                   f"{', '.join(d['depends_on'])} (incidents/O-1-FIXTURES.md)") if d.get("depends_on") else ""
            c["remaining"] = f"discharged by {kind} ({d.get('grade')}{how}{dep}): {d.get('reason', '')}".strip()
        elif kind == "open":
            c["remaining"] = "open after the writesets lane: " + str(d.get("reason", ""))
        else:
            problems.append(f"{c['obligation_id']}: unknown discharge kind {kind!r}")
        extra[i] = c
    for k in sorted(set(dis) - applied):
        if not str(k).startswith("module:"):
            problems.append(f"writesets/DISCHARGES.json names {k}, which is no census obligation")
    census_open = defaultdict(int)     # per module: census cells still open after the discharges
    census_any = set()
    for c in extra:
        if c["gate"] == "3.3a-writesets" and c.get("obligation_id"):
            census_any.add(c.get("module"))
            if c.get("status", "open") != "closed":
                census_open[c.get("module")] += 1

    for g in gates:
        targets = ["product"] if g["scope"] == "product" else nns
        for nn in targets:
            c = explicit.get((g["id"], nn))
            if c is None and nn != "product":
                lm = lane_modules.get(nn, {})
                gs = lm.get("gates_by_id", {}) if isinstance(lm, dict) else {}
                if g["id"] in gs:
                    c = {"gate": g["id"], "module": nn, **gs[g["id"]], "source": f"modules/{nn}.json"}
            if c is None and g.get("na_reason"):
                c = {"gate": g["id"], "module": nn, "status": "not-applicable", "reason": g["na_reason"]}
            if c is None:
                c = {"gate": g["id"], "module": nn, "status": "open", "evidence": [], "remaining": "no evidence recorded"}
            cells.append(finish(c, g["id"], nn))
    gate_ids = {g["id"] for g in gates}
    for c in extra:
        if c["gate"] not in gate_ids or c.get("module", "product") not in nns + ["product"]:
            problems.append(f"extra cell {c.get('obligation_id')}: unknown gate or module")
            continue
        cells.append(finish(c, c["gate"], c.get("module", "product"), per_obligation=True))
    used = {k for k in supplements}
    for k in used:
        if not any((c["gate"], c["module"]) == k for c in cells):
            problems.append(f"supplement for {k} names no cell")

    # --check rules on the finished cells (review R2-01)
    for c in cells:
        text = " ".join(str(c.get(k) or "") for k in ("remaining", "reason"))
        if AS_BUILT_TEXT.search(text) and c["product_obligation"] != "fails":
            m = AS_BUILT_TEXT.search(text)
            problems.append(f"{c['gate']}/{c['module']}{'/' + c['obligation_id'] if c.get('obligation_id') else ''}: "
                            f"text says '{m.group(0)}' beside product label {c['product_obligation']}")
        if c["level"] not in LEVELS:
            problems.append(f"{c['gate']}/{c['module']}: level {c['level']}")
    census = {}
    for name, data in census_inputs.items():
        rec = reg.get(CENSUS_RUN) or {}
        mine = [c for c in cells if c.get("source") == f"matrix-input/{name}"]
        kinds = Counter(c.get("kind") for c in mine)
        decl = data.get("declared", {})
        if data.get("source_sha256") != rec.get("log_sha256"):
            problems.append(f"{name}: source_sha256 differs from the registered {CENSUS_RUN} log")
        if (kinds.get("WS-OBL"), kinds.get("WS-COND"), kinds.get("WS-GAP")) != (
                decl.get("obligations"), decl.get("conditional"), decl.get("write_set_gaps")):
            problems.append(f"{name}: cells {dict(kinds)} differ from the declared counts {decl}")
        census = {"source_run": CENSUS_RUN, "input": f"matrix-input/{name}", "declared": decl,
                  "cells_by_kind": dict(kinds), "cells_by_module": dict(sorted(Counter(c["module"] for c in mine).items())),
                  "product": dict(Counter(c["product_obligation"] for c in mine))}

    audited = {}
    for _, r in records:
        audited[r["id"]] = {k: r.get(k) for k in ("disposition", "severity", "confidence", "gates", "evidence")}
    findings = [{**f, "audit": audited.get(f["id"])} for f in inv["findings"]]
    new_findings = [{"id": i, **v} for i, v in audited.items() if not any(f["id"] == i for f in inv["findings"])]

    obligations = {"pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e", "submission": "9c3719c1",
                   "starting_inventory": counts, "expected_inventory": EXPECTED,
                   "inventory_matches": {k: counts[k] == EXPECTED[k] for k in EXPECTED},
                   "gates": gates, "cells": cells,
                   "status_counts": dict(Counter(c["status"] for c in cells)),
                   "product_counts": dict(Counter(c["product_obligation"] for c in cells)),
                   "modules": inv["modules"], "findings": findings, "new_findings": new_findings,
                   "decisions": inv["decisions"], "premises": inv["premises"], "not_implemented": inv["not_implemented"],
                   "writer_obligations": inv["writer_obligations"],
                   "writer_obligations_note": "starting inventory: the original hand manifest (9c3719c1, 83 pairs); "
                                              "the source-derived census is census_obligations",
                   "census_obligations": census, "registry_runs": len(reg)}
    text = json.dumps(obligations, indent=1, sort_keys=True, default=str) + "\n"
    target = HERE / "obligations.json"
    if "--check" in sys.argv:
        current = target.exists() and target.read_text() == text
        ok = current and all(obligations["inventory_matches"].values()) and not problems
        print("matrix", "current" if current else "STALE", obligations["inventory_matches"],
              f"{len(problems)} problem(s)")
        for p in problems:
            print("  ", p)
        return 0 if ok else 1
    target.write_text(text)
    by_gate = defaultdict(Counter)
    prod = defaultdict(Counter)
    for c in cells:
        by_gate[c["gate"]][c["status"]] += 1
        prod[c["gate"]][c.get("product_obligation")] += 1
    lines = ["# Obligation matrix (generated by build_matrix.py; do not edit)", "",
             f"Starting inventory: {counts} (expected {EXPECTED}).", "",
             "Two separate questions per cell. **Status**: was the verification step done with adequate evidence "
             "(closed needs a registered passing run, or is graded `inspected` when it rests on a committed analysis). "
             "**Product obligation**: does the product at the pin meet it — `fails` (as-built evidence of a violation: "
             "a reproduced finding attached by gate or named by the cell, a failed run, or an as-built model check or "
             "located control with its expected violation; `product_basis` in obligations.json says which), "
             "`intent-undecided` (the behaviour is observed but only findings whose intent is undecided show it), "
             "`holds-live` / `holds-inspected` (only for single write-set pairs the writesets lane discharged at the pin "
             "by a preservation lemma or guard, observed live or read in the pin's code; the weakest product grades), "
             "`holds-as-detection` (such a pair whose writer breaks the invariant's premise but verify() reports the "
             "effect: detected, not prevented; review R4-07), "
             "`holds-in-model-only` (only a model result supports it; the code correspondence is not discharged), "
             "`unknown`. **Level**: what the evidence is about (method, model, product; the input's wording is kept "
             "as `level_detail`). Rows count every cell, including the per-obligation census and reach cells below.", "",
             "| Gate | Level | " + " | ".join(STATUSES) + " | " + " | ".join("product " + p for p in PO) + " |",
             "|---|---|" + "---:|" * (len(STATUSES) + len(PO))]
    for g in gates:
        lines.append(f"| {g['id']} | {level_of(g['id'])} | " + " | ".join(str(by_gate[g['id']].get(s, 0)) for s in STATUSES)
                     + " | " + " | ".join(str(prod[g['id']].get(p, 0)) for p in PO) + " |")
    lines += ["", f"Totals: {dict(Counter(c['status'] for c in cells))}; evidence grade of closed cells: "
              f"{dict(Counter(c.get('evidence_grade') for c in cells if c['status'] == 'closed'))}; product: "
              f"{dict(Counter(c.get('product_obligation') for c in cells))}"]
    if census:
        lines += ["", "## Writer census obligations (review R2-02)", "",
                  f"From `{CENSUS_RUN}` via `{census['input']}`: declared {census['declared']['obligations']} "
                  f"(invariant, writer) obligations, {census['declared']['conditional']} conditional obligations and "
                  f"{census['declared']['write_set_gaps']} write-set gaps; one open cell of gate 3.3a-writesets each, "
                  f"in the writer's module. Cells by kind {census['cells_by_kind']}; by module "
                  f"{census['cells_by_module']}; product {census['product']}. The starting inventory's 83 writer "
                  f"obligations are the original hand manifest and stay as they were."]
    reach = [c for c in cells if c.get("kind") == "reach-obligation"]
    if reach:
        lines += ["", "## Reach obligations (review R2-10)", "",
                  "| Cell | Store | Status | Product |", "|---|---|---|---|"]
        lines += [f"| {c['gate']}/{c['module']}/{c['obligation_id']} | {c['store'].replace('|', chr(92) + '|')} | {c['status']} | "
                  f"{c['product_obligation']} |" for c in reach]
    (HERE / "MATRIX.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"inventory_matches": all(obligations["inventory_matches"].values()),
                      "status_counts": obligations["status_counts"],
                      "closed_grades": dict(Counter(c.get("evidence_grade") for c in cells if c["status"] == "closed")),
                      "product": dict(Counter(c.get("product_obligation") for c in cells)),
                      "problems": problems}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
