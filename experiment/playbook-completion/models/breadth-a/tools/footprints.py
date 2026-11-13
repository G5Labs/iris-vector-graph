#!/usr/bin/env python3
"""Static read/write footprints of the reader and writer entry points of modules 01-06 (playbook §3.4 declared
reads, §3.5 lock plans, §3.3a write sets).

    python experiment/playbook-completion/models/breadth-a/tools/footprints.py

Input: models/breadth-a/inventory/NN.json (run inventory.py first) and footprint_reviews.json (hand reviews).
Output: experiment/playbook-completion/footprints/NN.json.

Method (static; nothing is run): for each entry point, the call closure (srcindex.Resolver, at most DEPTH hops and
NODE_CAP functions) is walked and every reached function contributes
  - SQL effects of its SQL text: INSERT/UPDATE/DELETE/TRUNCATE/DDL targets are writes, FROM/JOIN are reads, with the
    hints %NOLOCK/%NOINDEX/%NOCHECK/FOR UPDATE and SQL transaction statements;
  - ObjectScript global references classified by command (Set target, Kill, $Increment, Merge target = write;
    otherwise read), LOCK commands with mode and timeout, TSTART/TCOMMIT/TROLLBACK (with or without a level), $TLevel;
  - Python Native API global access and WriteTxn / commit / rollback markers;
  - implicit server hooks the SQL filer runs for a write: the functional indexes idx_edges_adj (Graph.KG.AdjIndex ->
    Graph.KG.Adjacency) on Graph_KG.rdf_edges and idx_labels_adj (Graph.KG.LabelIndex) on Graph_KG.rdf_labels
    (iris_vector_graph/schema.py:774-780), and the iFind index on rdf_props.val / docs.text (schema.py:482, 566).
Every item keeps up to MAX_AT source locations with the function it came from. Records carry
`confidence: "extracted"`; entries listed in footprint_reviews.json are merged with the reviewer's corrections and
marked `confidence: "reviewed"`. `journal` stays null here: the lane fills it from the journal oracle.
Known limits: string-built SQL whose table name is a runtime value is reported as Graph_KG.<dynamic:...>; dynamic
dispatch (getattr, callbacks) is not followed; a Set whose target is computed by indirection is caught only through
$Name; Python helpers reached through a variable are missed. The reviewed subset corrects what was checked by hand.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import srcindex as S  # noqa: E402
from modules import NAMES  # noqa: E402

REPO = S.REPO
HERE = Path(__file__).resolve().parent
INV = HERE.parent / "inventory"
OUT = REPO / "experiment/playbook-completion/footprints"
REVIEWS = HERE / "footprint_reviews.json"
DEPTH = 6
NODE_CAP = 600
MAX_AT = 4
SCRATCH = ("^||", "^mtemp", "^CacheTemp", "^IRIS.Temp", "^ISC.Temp", "^%")

HOOKS = {
    ("Graph_KG.rdf_edges", "insert"): ["cls:Graph.KG.AdjIndex.InsertIndex"],
    ("Graph_KG.rdf_edges", "update"): ["cls:Graph.KG.AdjIndex.UpdateIndex"],
    ("Graph_KG.rdf_edges", "delete"): ["cls:Graph.KG.AdjIndex.DeleteIndex"],
    ("Graph_KG.rdf_labels", "insert"): ["cls:Graph.KG.LabelIndex.InsertIndex"],
    ("Graph_KG.rdf_labels", "update"): ["cls:Graph.KG.LabelIndex.UpdateIndex"],
    ("Graph_KG.rdf_labels", "delete"): ["cls:Graph.KG.LabelIndex.DeleteIndex"],
}
HOOK_SRC = {"Graph_KG.rdf_edges": "iris_vector_graph/schema.py:774 (idx_edges_adj AS Graph.KG.AdjIndex)",
            "Graph_KG.rdf_labels": "iris_vector_graph/schema.py:780 (idx_labels_adj AS Graph.KG.LabelIndex)"}
IFIND = {"Graph_KG.rdf_props": "iris_vector_graph/schema.py:566 (idx_props_val_ifind AS %iFind.Index.Basic)",
         "Graph_KG.docs": "iris_vector_graph/schema.py:482 (idx_docs_text_ifind AS %iFind.Index.Basic)"}
BUILD_INDICES = {"Graph.KG.rdfedges": "Graph_KG.rdf_edges", "Graph.KG.rdflabels": "Graph_KG.rdf_labels",
                 "Graph.KG.rdfprops": "Graph_KG.rdf_props", "Graph.KG.nodes": "Graph_KG.nodes"}


def gstore(name: str) -> str:
    name = name.split(" (")[0]
    return "global:" + name


class Acc:
    def __init__(self):
        self.reads: Dict[str, List[str]] = defaultdict(list)
        self.writes: Dict[str, List[str]] = defaultdict(list)
        self.write_ops: Dict[str, set] = defaultdict(set)
        self.txn: List[dict] = []
        self.locks: List[dict] = []
        self.hints: Dict[str, List[str]] = defaultdict(list)
        self.calls: Dict[str, str] = {}

    def add(self, d: Dict[str, List[str]], store: str, at: str):
        if len(d[store]) < MAX_AT and at not in d[store]:
            d[store].append(at)


def short(key: str) -> str:
    if key.startswith("cls:"):
        return key[4:]
    return key.split("::", 1)[-1]


def walk(R: S.Resolver, key: str, acc: Acc) -> dict:
    seen: Dict[str, Tuple[int, str]] = {key: (0, "")}
    frontier = [key]
    hook_edges: List[Tuple[str, str]] = []
    truncated = False
    d = 0
    while frontier and d <= DEPTH:
        nxt = []
        for k in frontier:
            extra = contribute(R, k, acc, seen[k][0])
            for h, why in extra:
                if h not in seen:
                    seen[h] = (seen[k][0] + 1, why)
                    nxt.append(h)
                    hook_edges.append((h, why))
            if seen[k][0] >= DEPTH:
                continue
            for c, ln in R.callees(k):
                if c in seen:
                    continue
                if len(seen) >= NODE_CAP:
                    truncated = True
                    break
                seen[c] = (seen[k][0] + 1, f"{short(k)}@{ln}")
                nxt.append(c)
        frontier = nxt
        d += 1
    return {"functions_followed": len(seen), "max_depth": DEPTH, "truncated_at_cap": truncated,
            "implicit_hooks": sorted({f"{short(h)} <- {w}" for h, w in hook_edges})}


def contribute(R: S.Resolver, key: str, acc: Acc, depth: int) -> List[Tuple[str, str]]:
    extra: List[Tuple[str, str]] = []
    if key.startswith("cls:"):
        m = R.cl.methods.get(key[4:])
        if not m:
            return extra
        loc = lambda ln: f"{m.file}:{ln} ({m.cls.split('.')[-1]}.{m.name})"  # noqa: E731
        for ln, g in m.writes:
            if g.startswith(SCRATCH):
                acc.add(acc.writes, gstore(g) + " [process-private/scratch]", loc(ln))
            else:
                acc.add(acc.writes, gstore(g), loc(ln))
        for ln, g in m.reads:
            acc.add(acc.reads, gstore(g), loc(ln))
        for ln, t in m.txn:
            acc.txn.append({"marker": t, "at": loc(ln), "depth": depth})
        for ln, t in m.locks:
            acc.locks.append({"lock": t, "at": loc(ln), "depth": depth})
        for ln, text in m.sql:
            sql_into(acc, text, loc(ln), extra)
        for c, meth, ln in m.calls:
            if meth == "%BuildIndices" and c in BUILD_INDICES:
                tbl = BUILD_INDICES[c]
                acc.add(acc.writes, "sql:" + tbl + " [indices]", loc(ln))
                acc.write_ops["sql:" + tbl + " [indices]"].add("%BuildIndices")
                for h in ("cls:Graph.KG.AdjIndex.PurgeIndex", "cls:Graph.KG.AdjIndex.InsertIndex") if tbl.endswith("rdf_edges") else (
                        ("cls:Graph.KG.LabelIndex.PurgeIndex", "cls:Graph.KG.LabelIndex.InsertIndex") if tbl.endswith("rdf_labels") else ()):
                    extra.append((h, f"%BuildIndices {c} at {loc(ln)}"))
        if m.cls.startswith(("Graph.KG", "IVG")) and depth > 0:
            acc.calls.setdefault(key[4:], f"depth {depth}")
        return extra
    fn = R.py.funcs.get(key)
    if not fn:
        return extra
    loc = lambda ln: f"{fn.file}:{ln} ({fn.qual.split('.<locals>.')[-1]})"  # noqa: E731
    for ln, text in fn.sql:
        sql_into(acc, text, loc(ln), extra)
    for ln, op, g in fn.native_globals:
        (acc.add(acc.writes, gstore(g) + " [native API]", loc(ln)) if op == "write"
         else acc.add(acc.reads, gstore(g) + " [native API]", loc(ln)))
    for ln, t in fn.txn:
        acc.txn.append({"marker": t, "at": loc(ln), "depth": depth})
    for ln, t in fn.locks:
        acc.locks.append({"lock": t, "at": loc(ln), "depth": depth})
    for c in fn.calls:
        if c[0] == "cls":
            if c[2] == "%BuildIndices" and c[1] in BUILD_INDICES:
                tbl = BUILD_INDICES[c[1]]
                acc.add(acc.writes, "sql:" + tbl + " [indices]", loc(c[3]))
                acc.write_ops["sql:" + tbl + " [indices]"].add("%BuildIndices")
                if tbl.endswith("rdf_edges"):
                    extra.append(("cls:Graph.KG.AdjIndex.PurgeIndex", f"%BuildIndices at {loc(c[3])}"))
                    extra.append(("cls:Graph.KG.AdjIndex.InsertIndex", f"%BuildIndices at {loc(c[3])}"))
            k = R.cls_key(c[1], c[2])
            acc.calls.setdefault(k or f"{c[1]}.{c[2]}", f"native call at {fn.file}:{c[3]}" + ("" if k else " (unresolved)"))
    return extra


def sql_into(acc: Acc, text: str, at: str, extra: List[Tuple[str, str]]) -> None:
    eff = S.sql_effects(text)
    for op, t in eff["writes"]:
        store = ("sql:" + t) if not t.startswith(("routine:", "view:", "index:", "catalog:", "unqualified:")) else t
        acc.add(acc.writes, store, at)
        acc.write_ops[store].add(op)
        base = t
        noindex = any(h.startswith("%NOINDEX") for h in eff["hints"])
        for (tbl, hop), hooks in HOOKS.items():
            if base == tbl and op == hop:
                if noindex:
                    # %NOINDEX skips every index of the statement, the functional ones included: no hook runs
                    acc.add(acc.writes, f"[no row hook: %NOINDEX {op} of {tbl}; ^KG is written only by a later "
                                        f"%BuildIndices]", at)
                    continue
                for h in hooks:
                    extra.append((h, f"SQL {op} {tbl} at {at} via {HOOK_SRC[tbl]}"))
        if base in IFIND and op in ("insert", "update", "delete"):
            acc.add(acc.writes, "global:^IRIS.IF.* [iFind index of " + base + "]", at + " via " + IFIND[base])
    for op, t in eff["reads"]:
        acc.add(acc.reads, ("sql:" + t) if not t.startswith(("catalog:", "unqualified:")) else t, at)
    for h in eff["hints"]:
        if len(acc.hints[h]) < MAX_AT:
            acc.hints[h].append(at)
    for t in eff["txn"]:
        acc.txn.append({"marker": "SQL " + t, "at": at, "depth": -1})


def summarize_txn(acc: Acc) -> List[dict]:
    out, seen = [], set()
    for t in sorted(acc.txn, key=lambda x: x["depth"]):
        k = (t["marker"], t["at"])
        if k in seen:
            continue
        seen.add(k)
        m = t["marker"]
        if re.fullmatch(r"(?i)TRollback|TRO", m):
            m += "  [no level: rolls back every level, P-0409]"
        out.append({"marker": m, "at": t["at"]})
    return out[:40]


def summarize_locks(acc: Acc) -> List[dict]:
    out, seen = [], set()
    for l in acc.locks:
        k = (l["lock"], l["at"])
        if k in seen:
            continue
        seen.add(k)
        out.append({"lock": l["lock"], "at": l["at"]})
    for h, ats in acc.hints.items():
        out.append({"lock": "SQL hint " + h, "at": "; ".join(ats)})
    return out[:40]


def footprint(R: S.Resolver, key: str) -> dict:
    acc = Acc()
    meta = walk(R, key, acc)
    writes = [{"store": s, "ops": sorted(acc.write_ops.get(s, [])) or None, "at": at}
              for s, at in sorted(acc.writes.items())]
    reads = [{"store": s, "at": at} for s, at in sorted(acc.reads.items())]
    real_writes = [w for w in writes if "[process-private/scratch]" not in w["store"]]
    role = "both" if real_writes and reads else ("writer" if real_writes else ("reader" if reads else "none"))
    return {"role": role, "reads": reads, "writes": writes, "transactions": summarize_txn(acc),
            "locks": summarize_locks(acc), "calls": sorted(acc.calls)[:60], "extraction": meta}


def entry_key(py: S.PyIndex, e: dict) -> Optional[str]:
    if e["id"].startswith("cls:"):
        return e["id"]
    if e["id"].startswith(("py:", "export:")):
        return next((k for k, f in py.funcs.items() if f.file == e["file"] and f.qual == e["qual"]), None)
    if e["kind"] in ("rest", "cli"):
        f = next((k for k, f in py.funcs.items() if f.file == e["file"] and f.qual == e["qual"]), None)
        return f
    return None


def main() -> int:
    py, cl = S.load()
    R = S.Resolver(py, cl)
    reviews = json.loads(REVIEWS.read_text()) if REVIEWS.exists() else {"reviews": {}}
    OUT.mkdir(parents=True, exist_ok=True)
    totals = {}
    for nn in ("01", "02", "03", "04", "05", "06"):
        inv = json.loads((INV / f"{nn}.json").read_text())
        recs = []
        for e in inv["entry_points"]:
            key = entry_key(py, e)
            if not key:
                continue
            fp = footprint(R, key)
            if fp["role"] == "none":
                continue
            rec = {"id": e["id"], "kind": e["kind"], "source": e["source"], **fp,
                   "confidence": "extracted", "atomicity_claim": None, "notes": [], "journal": None}
            rv = reviews["reviews"].get(e["id"])
            if rv:
                rec["confidence"] = "reviewed"
                rec["review"] = {k: v for k, v in rv.items() if k not in ("atomicity_claim", "notes")}
                rec["atomicity_claim"] = rv.get("atomicity_claim")
                rec["notes"] = rv.get("notes", [])
            recs.append(rec)
        # reviewed records first, then writers, then readers
        order = {"reviewed": 0, "extracted": 1}
        recs.sort(key=lambda r: (order[r["confidence"]], {"writer": 0, "both": 0, "reader": 1}[r["role"]], r["id"]))
        doc = {
            "module": nn, "name": NAMES[nn], "pin": S.PIN,
            "generated_by": "experiment/playbook-completion/models/breadth-a/tools/footprints.py",
            "inputs": [f"experiment/playbook-completion/models/breadth-a/inventory/{nn}.json",
                       "experiment/playbook-completion/models/breadth-a/tools/footprint_reviews.json"],
            "method": __doc__.split("Method (static; nothing is run):", 1)[1].strip(),
            "counts": {"entry_points": len(recs), "writers": sum(r["role"] in ("writer", "both") for r in recs),
                       "readers": sum(r["role"] == "reader" for r in recs),
                       "reviewed": sum(r["confidence"] == "reviewed" for r in recs),
                       "journal_validated": 0},
            "entry_points": recs,
            "journal_validation": [],
        }
        old = OUT / f"{nn}.json"
        if old.exists():
            try:
                prev = json.loads(old.read_text())
                # keep journal results the lane has filled in
                doc["journal_validation"] = prev.get("journal_validation", [])
                pj = {r["id"]: r.get("journal") for r in prev.get("entry_points", []) if r.get("journal")}
                for r in recs:
                    if r["id"] in pj:
                        r["journal"] = pj[r["id"]]
                doc["counts"]["journal_validated"] = sum(1 for r in recs if r.get("journal"))
            except json.JSONDecodeError:
                pass
        old.write_text(json.dumps(doc, indent=1) + "\n")
        totals[nn] = doc["counts"]
    unreviewed = sorted(set(reviews["reviews"]) - {r for nn in totals for r in []})
    print(json.dumps(totals, indent=1))
    missing = []
    allids = set()
    for nn in totals:
        allids |= {r["id"] for r in json.loads((OUT / f"{nn}.json").read_text())["entry_points"]}
    for rid in reviews["reviews"]:
        if rid not in allids:
            missing.append(rid)
    if missing:
        print("reviews naming no footprint record:", missing)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
