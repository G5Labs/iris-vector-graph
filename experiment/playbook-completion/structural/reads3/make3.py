#!/usr/bin/env python3
"""Assemble reads3/{method.json, cells.json} from the registered runs' result files, groups.json and static.json.

    python make3.py $RUN_DIR/structural/reads3/final/r-04.json $RUN_DIR/structural/reads3/final/r-10.json

Per inventoried read/both entry point that structural/reads/cells.json left unchecked (its 'remaining' text, 04: 113,
10: 200, plus the two module-10 entries that cell counted by a short-name match without a matching case: cypher:ivg.ppr
and the undecided eng:IRISGraphEngine.random_walk): how it is covered (live key / group / static / not covered) and the
result. Writes no other file.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = {"04": "st-live-reads3-04", "10": "st-live-reads3-10"}
SELFTEST = "st-control-reads3-selftest"

FINDING_OF = [  # (regex on the key, finding)
    (r"^cls:Graph\.KG\.(NKGAccelCentrality|NKGAccel)\.(Closeness|Eigenvector|Betweenness)", "F-C1041"),
    (r"^cls:Graph\.KG\.Communities\.", "F-C1041"),
    (r"^cls:Graph\.KG\.(NKGAccelTraversal|NKGAccel)\.RandomWalkJson", "F-1002"),
    (r"^cls:Graph\.KG\.(NKGAccelTraversal|NKGAccel)\.(KHopNeighbors|KHopNeighborsSorted|KHopJson|ShortestPathNKG|CountDistinctKHop)$", "F-C1046"),
    (r"^cls:Graph\.KG\.PageRankEmbedded\.", "F-1013"),
    (r"^eng:IRISGraphEngine\.kg_GRAPH_PATH$", "F-0820"),
]


def finding_of(key):
    for rx, f in FINDING_OF:
        if re.search(rx, key):
            return f
    return "UNATTRIBUTED"


def norm(key):
    return re.sub(r" \(.*$", "", key).split("#")[0]


def remaining(module):
    d = json.loads((ROOT / "structural/reads/cells.json").read_text())
    for c in d["cells"]:
        if c["module"] == module:
            txt = c["remaining"].split(" | ")[0]
            m = re.match(r"(\d+) of (\d+) inventoried read/both entry points not checked: (.*)", txt)
            return [x.strip() for x in m.group(3).split(", ")], int(m.group(2))
    raise SystemExit(f"no cell for {module}")


def main() -> int:
    results = [json.loads(Path(p).read_text()) for p in sys.argv[1:3]]
    keys = {}  # entry -> [ {run, case, key, verdict, ...} ]
    case_count, key_count = {}, {}
    for res in results:
        for c in res["cases"]:
            m = c["module"]
            case_count[m] = case_count.get(m, 0) + 1
            for k, v in c["per_key"].items():
                key_count[m] = key_count.get(m, 0) + 1
                keys.setdefault(norm(k), []).append({
                    "run": RUNS[m], "case": c["id"], "key": k, "verdict": v["verdict"],
                    "changed_under": v["changed_under"], "inside_changed": v["inside_changed"],
                    "inside_declared_changed": v.get("inside_declared_changed"),
                    "outside_perturbations": sorted(c["outside"].keys()), "declared": c["declared"],
                    "vacuous": v.get("vacuous"), "refusal_is_the_answer": v.get("refusal_is_the_answer"),
                    "base_answer_excerpt": v.get("base_answer_excerpt")})
    groups = json.loads((HERE / "groups.json").read_text())["groups"]
    member_group = {}
    for g in groups:
        for mbr in g["members"]:
            if mbr.startswith(("cls:", "eng:", "py:")) and "*" not in mbr and " " not in mbr:
                member_group[mbr] = g
    static = json.loads((HERE / "static.json").read_text())
    static_of = {}
    for mod in ("04", "10"):
        for s in static[mod]:
            ent = s["entry"]
            if " / " in ent:   # "cls:X.A / B / C" -> each
                head, first = ent.split(" / ")[0].rsplit(".", 1)
                names = [first] + [x.split(" ")[0] for x in ent.split(" / ")[1:]]
                for n in names:
                    static_of[f"{head}.{n}"] = s
            else:
                static_of[ent.split(" (")[0]] = s

    # wrapper/target agreement (groups.json G10-delegations claims it)
    pairs = []
    for e in keys:
        for wrap, targets in (("cls:Graph.KG.Traversal.", ("TraversalBFS", "TraversalKHop", "TraversalPaths", "TraversalBuild")),
                              ("cls:Graph.KG.NKGAccel.", ("NKGAccelLoader", "NKGAccelAdjacency", "NKGAccelTraversal", "NKGAccelCentrality"))):
            if e.startswith(wrap):
                name = e[len(wrap):]
                for t in targets:
                    te = f"cls:Graph.KG.{t}.{name}"
                    if te in keys:
                        pairs.append((e, te, sorted({x["verdict"] for x in keys[e]}), sorted({x["verdict"] for x in keys[te]})))
    disagreements = [p for p in pairs if p[2] != p[3]]

    method = {"gate": "3.4-declared-reads", "sub_lane": "reads3", "modules": ["04", "10"],
              "oracle": "non-interference (reads3/ni_base.py, a copy of reads2/ni_base.py; reads3/ni3core.py adds keyed per-entry verdicts, "
                        "a prep step after the perturbation, vacuous/raising keys never holding, engines with native_cypher=False)",
              "self_test": SELFTEST, "runs": [SELFTEST, RUNS["04"], RUNS["10"]],
              "cases": case_count, "keyed_answers": key_count,
              "wrapper_target_pairs_checked": len(pairs), "wrapper_target_disagreements": disagreements,
              "per_module": {}}
    cells = []
    for mod in ("04", "10"):
        rem, inv_total = remaining(mod)
        extra = ["cypher:ivg.ppr", "eng:IRISGraphEngine.random_walk"] if mod == "10" else []
        rows = []
        for ent in rem + extra:
            row = {"entry": ent, "inherited_from_reads_cell": ent in extra}
            ks = keys.get(ent, [])
            st = static_of.get(ent)
            grp = member_group.get(ent)
            verdicts = sorted({k["verdict"] for k in ks})
            if ks and set(verdicts) <= {"holds", "violation"}:
                row["covered"] = "live"
                row["result"] = "violation" if "violation" in verdicts else "holds"
            elif ks and st and st["check"] in ("static-holds", "static-violation"):
                row["covered"] = "live (undecided) + static"
                row["result"] = "violation (inspected)" if st["check"] == "static-violation" else "holds (inspected)"
            elif grp and grp["id"] == "G10-random-walk":
                row["covered"] = "group"
                row["result"] = "violation (through its representative)"
            elif ks and st and st["check"] == "not-covered":
                row["covered"] = "not covered"
                row["result"] = "undecided: " + ("; ".join(sorted({k["vacuous"] or "error" for k in ks})))
            elif ks and "holds" in verdicts:
                row["covered"] = "live"
                row["result"] = "holds"
            elif grp:
                row["covered"] = "group"
                row["result"] = "violation" if grp["result"].startswith("violation") else "holds"
            elif st and st["check"] == "static":
                row["covered"] = "static"
                row["result"] = "holds (inspected)"
            else:
                row["covered"] = "NOT COVERED"
                row["result"] = "unknown"
            if ks:
                row["live"] = [{k2: v for k2, v in k.items() if k2 in ("run", "case", "key", "verdict", "changed_under", "inside_changed", "declared",
                                                                        "inside_declared_changed", "outside_perturbations", "vacuous", "refusal_is_the_answer")} for k in ks]
            if grp:
                row["group"] = {"id": grp["id"], "representative": grp["representative"], "citation": grp["citation"]}
            if st:
                row["static"] = st
            if "violation" in row["result"]:
                fs = sorted({finding_of(k["key"]) for k in ks if k["verdict"] == "violation"})
                if not fs and grp and grp["id"] == "G10-random-walk":
                    fs = ["F-1002"]
                if not fs and grp and grp["id"] == "G10-betweenness-worker":
                    fs = ["F-C1041"]
                if not fs and st and st["check"] == "static-violation":
                    fs = ["F-C1041"]
                row["findings"] = fs
            if ent == "eng:IRISGraphEngine.kg_MENTIONS":
                row["note"] = ("holds against ALG-B9.10's every-graph footprint (10-algorithms.md:157); under HD-0201's working assumption "
                               "(a Python read with no graph argument reads the default graph, decisions.md:35-37; USER_GUIDE.md:462-464) the "
                               "declared-inside perturbation 'same ids and edges in the named graphs' changed it: the pattern of F-0820; "
                               "intent-undecided (HD-0201 open), not filed")
            rows.append(row)
        cov = {}
        for r in rows:
            cov[r["covered"]] = cov.get(r["covered"], 0) + 1
        viol = [r for r in rows if "violation" in r["result"]]
        notcov = [r for r in rows if r["covered"] in ("not covered", "NOT COVERED")]
        insens = sorted({k["key"] for r in rows for k in r.get("live", []) if k["inside_changed"] is False and k["verdict"] == "holds"})
        fids = sorted({f for r in viol for f in r.get("findings", [])})
        method["per_module"][mod] = {"inventory_read_both": inv_total, "unchecked_before": len(rem), "entries": rows,
                                     "coverage": cov, "violating_entries": len(viol), "findings": fids,
                                     "inside_unchanged_keys": insens}
        ev = [f"run:{SELFTEST}", f"run:{RUNS[mod]}", "run:st-control-reads-selftest",
              "run:st-live-reads-a" if mod == "04" else "run:st-live-reads-b",
              "experiment/playbook-completion/structural/reads3/method.json", "experiment/playbook-completion/structural/reads3/groups.json",
              "experiment/playbook-completion/structural/reads3/static.json", "experiment/playbook-completion/structural/reads3/ni3.py",
              "experiment/playbook-completion/structural/reads3/ni3core.py", f"experiment/playbook-completion/structural/reads3/ni3_{mod}.py"]
        prior = inv_total - len(rem)
        if mod == "04":
            basis = (f"all {inv_total} inventoried read/both entry points covered: {prior} in st-live-reads-a; {cov.get('live', 0)} live in "
                     f"{RUNS['04']} ({case_count['04']} cases, {key_count['04']} keyed answers, all hold); {cov.get('group', 0)} Private/ByRef helpers "
                     f"through groups whose live representatives hold (groups.json G04-*); no violation seen")
            cells.append({"gate": "3.4-declared-reads", "module": "04", "status": "closed" if not notcov else "open", "evidence": ev,
                          "evidence_grade": "live", "level": "product", "product_obligation": "unknown", "product_basis": basis,
                          "as_built_findings": [],
                          "remaining": ("none uncovered. Limits: non-interference sees only reads that reach the answer, under the perturbations "
                                        "listed per key in reads3/method.json; the 32 helpers covered by a group were not run on their own; the "
                                        f"inside perturbation left {len(insens)} keys unchanged (sensitivity not shown): " + ", ".join(insens))})
        else:
            live_viol = sorted({k["key"] for r in viol for k in r.get("live", []) if k["verdict"] == "violation"})
            basis = (f"of {inv_total} inventoried read/both entry points, {prior - 2} hold in st-live-reads-b; the {len(rem)} it left unchecked plus "
                     f"cypher:ivg.ppr (counted there by a short-name match with engine.ppr) and random_walk (undecided there), {len(rem) + 2} in all: "
                     f"{cov.get('live', 0)} live in {RUNS['10']} ({case_count['10']} cases, {key_count['10']} keyed answers), "
                     f"{cov.get('group', 0)} through groups, {cov.get('static', 0)} static, {cov.get('live (undecided) + static', 0)} undecided live and "
                     f"bounded by inspection, {len(notcov)} not covered. Violations ({len(viol)} entry points): the ^NKG class methods called "
                     f"directly answer every graph merged (F-C1041 centrality/communities; F-C1046 k-hop, shortest path, distinct k-hop; "
                     f"F-1002 random walk), PageRankEmbedded reads every graph's rows (F-1013, live here), kg_GRAPH_PATH answers named-graph "
                     f"paths (F-0820)")
            cells.append({"gate": "3.4-declared-reads", "module": "10", "status": "closed" if not notcov else "open", "evidence": ev,
                          "evidence_grade": "live", "level": "product", "product_obligation": "fails", "product_basis": basis,
                          "as_built_findings": ["F-C1041"] + [f for f in fids if f != "F-C1041"],
                          "remaining": ("not covered (" + str(len(notcov)) + "): " + ", ".join(r["entry"] for r in notcov) +
                                        " -- in this namespace each refuses or answers an empty marker before any read (observed live); the read "
                                        "that matters is the arno-callout library's walk of USER's ^KG, whose source is not at the pin and whose "
                                        "binary is absent from this container (F-1001, blocked-access; USER is the validation lane's). Undecided live "
                                        "but bounded statically: build_kg_adjacency_chunked (raises without the library; its walk reads ^KG(out/in, 0) "
                                        "only), Communities.ClosenessJsonPy / LeidenJsonPy (PYUNAVAIL: igraph absent; inspected to read the merged "
                                        "^NKG, F-C1041). Group-only (not run on their own): PageRank.Run, VarLength.EndsInto / NamedEnds, "
                                        "BetweennessWorker x2, random_walk (its library path is NKGAccel.RandomWalkJson, F-1002). Intent note: "
                                        "kg_MENTIONS holds against ALG-B9.10's every-graph footprint but reads named graphs under HD-0201's working "
                                        "assumption (F-0820's pattern; intent-undecided). Limits: non-interference sees only reads that reach the "
                                        f"answer under the listed perturbations; the inside perturbation left {len(insens)} holding keys unchanged.")})
        print(mod, cov, "violations", len(viol), fids, "not covered", [r["entry"] for r in notcov])
    method["errata_to_registered_observes"] = {
        "st-live-reads3-04": "'Inside perturbation left 20 keys unchanged': precisely 19 keyed answers (16 distinct keys, the Adj reader keys "
                             "counted once per graph) were unchanged under the inside perturbation and 1 case (TraversalBuild.InitNKGSkeleton) "
                             "had no inside perturbation; per_module.04.inside_unchanged_keys lists them",
        "st-live-reads3-10": "'None changed under edgeless nodes / properties alone' holds for the violating keys of the case that applied that "
                             "perturbation (the ^NKG class methods); the PageRankEmbedded and kg_GRAPH_PATH keys were run only under 'same ids "
                             "and other edges in the other graphs'",
    }
    method["findings_reused"] = {
        "F-C1041": "re-observed live (st-live-reads3-10): NKGAccelCentrality and NKGAccel ClosenessGlobal, ClosenessGlobalMSBFS, EigenvectorGlobal, "
                   "BetweennessGlobal, BetweennessGlobalParallel (numJobs 1), BetweennessNeighborhood and Communities TriangleCountJson, KCoreJson, "
                   "SCCJson, LeidenJson, LeidenJsonAuto changed when named graphs' edges were merged into ^NKG by sync (e.g. LeidenJson community "
                   "size 3 -> 4 with node d of the named graphs; BetweennessGlobalParallel a 1, c 1 -> a 3, b 2); LeidenJson and LeidenJsonAuto were "
                   "not in F-C1041's inspected list",
        "F-1002": "re-observed live: NKGAccelTraversal.RandomWalkJson and NKGAccel.RandomWalkJson('a', 6, 20) visit node d of the named graphs; "
                  "engine.random_walk answers [] without the library (vacuous)",
        "F-1013": "every-graph part reproduced live in AUDITD (F-1013's live run failed on SQLUSER.NODES elsewhere): ComputePageRank('%') and "
                  "ComputePageRankWithMetrics answered num_nodes 3 / num_edges 4 for the default graph alone and 11 / 14 (every graph's rows) with "
                  "the same ids in stg1 and stg2, adding node d",
        "F-0820": "re-observed live: engine.kg_GRAPH_PATH('a','R','R') answers named-graph steps (a-R-c, a-R-d, b-R-d...) beside the default "
                  "graph's a-R-b, b-R-c",
        "F-1001": "the ArnoAccel library readers stay blocked-access: refused outside USER, library absent",
    }
    (HERE / "method.json").write_text(json.dumps(method, indent=1) + "\n")
    (HERE / "cells.json").write_text(json.dumps({"cells": cells}, indent=1) + "\n")
    print("wrapper/target pairs", len(pairs), "disagreements", disagreements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
