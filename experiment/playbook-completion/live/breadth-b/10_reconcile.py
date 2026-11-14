#!/usr/bin/env python3
"""Module 10 entry-point reconciliation (gate 3.1-coverage): classify every entry point no ALG statement covers.

    python3 experiment/playbook-completion/live/breadth-b/10_reconcile.py   (no IRIS; reads source + inventory/10.json)

Classes (mechanical):
- reached-from-covered: an ObjectScript method in the call closure (##class/..M/$ClassMethod) of a covered entry point,
  or named in a covered Python entry point's classMethodValue calls; its behaviour is stated through that caller.
- product-caller: called from product Python (a literal "Graph.KG.Cls", "Method" pair or a %SQL/procedure call) whose
  caller is not itself a covered module-10 entry point -> listed with the call sites (an omission unless the caller is
  another module's).
- direct-surface-only: no product caller at all: reachable only by a direct class-method/SQL call -> genuine omission.
- other-module: owned by another module per its Scope line (module 04 builder, module 08 Cypher procedure parsing,
  other modules' writers listed for cells).
Writes $RUN_DIR/breadth-b/inventory/10-reconcile.json and prints a summary.
"""
import json, os, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "experiment/playbook-completion/models/breadth-b/tools"))
import inventory as inv  # noqa: E402

d = json.loads((REPO / "experiment/playbook-completion/models/breadth-b/inventory/10.json").read_text())
eps = {e["id"]: e for e in d["entry_points"]}
covered = {i for i, e in eps.items() if e["covered_by"]}
classes = inv.all_classes()
# closure of covered entry points
reach = set()
for i in covered:
    e = eps[i]
    if e["kind"] == "cls":
        for c in e.get("callees", []):
            reach.add("cls:" + c)
    if e["kind"] == "engine":
        for cm in e["hint"].get("classmethod_calls", []):
            c, _, n = cm.rpartition(".")
            reach.add("cls:" + cm)
            if c in classes and n in classes[c]["methods"]:
                for cc, nn in inv.cls_closure(c, n, classes):
                    reach.add(f"cls:{cc}.{nn}")
    if e["kind"] == "py":
        body = "\n".join((REPO / e["path"]).read_text().splitlines()[e["start"] - 1:e["end"]])
        for cm in inv.py_hints(body)["classmethod_calls"]:
            c, _, n = cm.rpartition(".")
            reach.add("cls:" + cm)
            if c in classes and n in classes[c]["methods"]:
                for cc, nn in inv.cls_closure(c, n, classes):
                    reach.add(f"cls:{cc}.{nn}")
# python call sites of class methods across the product
pyfiles = [p for p in (REPO / "iris_vector_graph").rglob("*.py")] + [p for p in (REPO / "api").rglob("*.py")]
callsites = {}
for p in pyfiles:
    txt = p.read_text(errors="replace")
    for m in re.finditer(r"[\"'](Graph\.KG\.[\w.]+)[\"']\s*,\s*[\"'](\w+)[\"']", txt):
        line = txt.count("\n", 0, m.start()) + 1
        callsites.setdefault(f"cls:{m.group(1)}.{m.group(2)}", []).append(f"{p.relative_to(REPO)}:{line}")
# ObjectScript callers anywhere in iris_src
cls_callers = {}
for cname, c in classes.items():
    for mname, m in c["methods"].items():
        for callee in inv.cls_callees(cname, m, classes):
            cls_callers.setdefault(f"cls:{callee[0]}.{callee[1]}", set()).add(f"{cname}.{mname}")
OTHER = {
    "cypher:": "08 (Cypher procedure parsing/dispatch; module 10 states only the ^NKG procedure refusals ALG-B7)",
    "ext:": "other module's writer, listed only to map cache/snapshot cells",
}
BUILDER = re.compile(r"^cls:Graph\.KG\.Traversal\.(BuildKG|BuildNKG|InitNKGSkeleton|BackfillDegp|Build2HopStats|Build2HopExactStats|NKGPopulated|NKGEdgeCount|NKGNodeCount|NKGLiveNodeCount|KGEdgeCount)$")
out = {}
for i in d["omissions"]:
    e = eps[i]
    if any(i.startswith(k) for k in OTHER):
        k = next(k for k in OTHER if i.startswith(k))
        out[i] = {"class": "other-module", "why": OTHER[k]}
    elif BUILDER.match(i):
        out[i] = {"class": "other-module", "why": "04 adjacency/snapshot builder (Traversal delegates to TraversalBuild; module 10 Scope: readers only)"}
    elif i in reach:
        out[i] = {"class": "reached-from-covered", "why": "in the call closure of a covered entry point"}
    elif i in callsites:
        out[i] = {"class": "product-caller", "why": "called from product Python", "sites": callsites[i][:6]}
    elif i in cls_callers:
        callers = sorted(cls_callers[i])
        out[i] = {"class": "reached-from-covered" if any(("cls:" + c) in covered or ("cls:" + c) in reach for c in callers) else "objectscript-caller-only",
                  "why": "called by ObjectScript", "callers": callers[:6]}
    elif e["kind"] == "py":
        # python function: any reference in product code?
        name = i.split(":")[-1].split(".")[-1]
        refs = []
        for p in pyfiles:
            if str(p.relative_to(REPO)) == e["path"]:
                continue
            t = p.read_text(errors="replace")
            for m in re.finditer(r"\b" + re.escape(name) + r"\b", t):
                refs.append(f"{p.relative_to(REPO)}:{t.count(chr(10), 0, m.start()) + 1}")
        out[i] = {"class": "product-caller" if refs else "direct-surface-only", "why": "python references", "sites": refs[:6]}
    else:
        out[i] = {"class": "direct-surface-only", "why": "no product caller found (Native API / SQL direct call only)"}
# Fixpoint: a site inside a covered (or reached) entry point's span, or an ObjectScript caller that is covered or
# reached, makes the omission reached-from-covered.
spans = [(eps[i]["path"], eps[i]["start"], eps[i]["end"], i) for i in eps]
def inside(site):
    f, _, ln = site.rpartition(":")
    return [i for (pth, a, b, i) in spans if pth == f and a <= int(ln) <= b]
changed = True
while changed:
    changed = False
    ok = covered | {k for k, v in out.items() if v["class"] == "reached-from-covered"}
    for k, v in out.items():
        if v["class"] not in ("product-caller", "objectscript-caller-only"):
            continue
        via = []
        for site in v.get("sites", []):
            via += [i for i in inside(site) if i in ok]
        for c in v.get("callers", []):
            if ("cls:" + c) in ok:
                via.append("cls:" + c)
        if via:
            v["class"] = "reached-from-covered"
            v["via"] = sorted(set(via))[:4]
            changed = True
summary = {}
for v in out.values():
    summary[v["class"]] = summary.get(v["class"], 0) + 1
res = {"module": "10", "omissions": len(d["omissions"]), "summary": summary, "classified": out}
dst = Path(os.environ.get("RUN_DIR", "/tmp")) / "breadth-b" / "inventory" / "10-reconcile.json"
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(res, indent=1) + "\n")
print(json.dumps(summary))
for k, v in out.items():
    if v["class"] in ("direct-surface-only", "product-caller", "objectscript-caller-only"):
        print(v["class"], k, v.get("sites", v.get("callers", ""))[:3])
