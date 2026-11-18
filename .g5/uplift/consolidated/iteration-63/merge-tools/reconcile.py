#!/usr/bin/env python3
"""Merge-time reconciliation of cross-fork restatements (iteration 63). usage: reconcile.py DIR (edits DIR in place)."""
import csv, sys
D = sys.argv[1]
B = ["block","page","kind","sha256","status","obligations","excluded","structural_zero","parent","children","owners_checked","iteration"]
O = ["id","block","locator","statement","cases","observation","model_locators","premises","grade","design_check","check_scope","design_receipts","as_built","parent_entailment","gap","grade_source","iteration"]
E = ["id","block","locator","kind","owner","reason","iteration"]
def rd(f, c):
    with open(f"{D}/{f}", encoding="utf-8", newline="") as h:
        r = csv.DictReader(h, delimiter="\t", quoting=csv.QUOTE_NONE); assert r.fieldnames == c; return list(r)
def wr(f, c, rows):
    with open(f"{D}/{f}", "w", encoding="utf-8", newline="") as h:
        h.write("\t".join(c) + "\n")
        for r in rows: h.write("\t".join(r[k] for k in c) + "\n")
bb, oo, ee = rd("blocks.tsv", B), rd("obligations.tsv", O), rd("excluded.tsv", E)
OWN = {
 "structure.adjacency.bulk#x01": "install.bulk_load.loader",
 "structure.rebuilt.token#x01": "algorithms.cache.token#o01",
 "temporal.structural#x01": "temporal.optout.effect#o01",
 "temporal.structural.ledger#x01": "temporal.ledger#o03",
 "algorithms.cache.token#x01": "structure.rebuilt.valid#o01",
 "algorithms.cache.pagerank#x02": "algorithms.op.pagerank#o06",
 "search.scope.indexes.upkeep#x01": "search.erasure.indexes#o01",
 "search.erasure.indexes#x02": "search.scope.indexes.upkeep#o02",
 "search.fusion.leg_index#x01": "search.ivf.metric#o03",
 "query.writes.adjacency#x01": "structure.adjacency.undeclared#o03",
 "query.conformance#x02": "structure.edge.single#o01",
 "query.functions.path_elements#x01": "structure.edge.single#o01",
 "query.functions.path_elements#x02": "structure.multigraph#o03",
 "fhir.sql_mapping#x01": "install.snapshot.scope#o04",
 "search.scope.indexes#x01": "search.fusion.leg_index#o01",
 "search.scope.indexes#x02": "search.fusion.leg_index#o01",
 "search.scope.indexes.ivf#x01": "search.scope.indexes.upkeep#o01",
 "install.migration#x01": "search.quarantine#o07",
 "temporal.write#x04": "temporal.structural#o01",
 "temporal.write#x06": "temporal.stats.writers#o05",
 "temporal.delete#x01": "temporal.stats.writers#o04",
 "temporal.delete#x04": "temporal.structural.end#o01",
 "temporal.purge#x01": "temporal.structural.end#o01",
 "temporal.purge#x04": "temporal.structural#o01",
 "query.functions.random#x01": "query.writes.computed_values#o02",
 "query.functions.slice#x01": "query.parameters#o06",
 "query.functions.coalesce#x01": "query.values.relationship_text#o05",
 "query.writes.retype#x02": "query.values.relationship_text#o01",
}
ids = {e["id"]: e for e in ee}
for k, v in OWN.items():
    e = ids[k]; assert e["kind"] == "restatement", k
    e["owner"] = v
    e["reason"] = e["reason"] + f" [owner narrowed to {v} at merge, iteration 63]"
# iteration-61 reasons that called the owner not yet enumerated
for e in ee:
    if e["iteration"] == "61":
        for s in ("(not yet enumerated)", "(not started)"):
            if s in e["reason"]:
                e["reason"] = e["reason"].replace(s, "(enumerated in iteration 63)")
# double count: query.conformance#o03 restates query.writes.computed_values#o06
drop = "query.conformance#o03"
row = next(o for o in oo if o["id"] == drop)
oo = [o for o in oo if o["id"] != drop]
ee.append({"id": "query.conformance#x10", "block": "query.conformance", "locator": row["locator"], "kind": "restatement",
           "owner": "query.writes.computed_values#o06",
           "reason": "the computed-value refusal between matched nodes is owned by query.writes.computed_values#o06 (graded there from cypher_exprs); conformance lists it as a known deviation. Withdrawn as obligation query.conformance#o03 at merge to avoid counting it twice (iteration 63); the id is retired",
           "iteration": "63"})
# edge.single#o01 covers every writer of an ordinary edge, including Cypher CREATE (restated by conformance#x02, path_elements#x01)
es = next(o for o in oo if o["id"] == "structure.edge.single#o01")
es["statement"] = "Outside multigraph mode a graph holds at most one ordinary edge per triple: repeated creates through any writer (create_edge, store_edge, Cypher CREATE) leave one row"
es["cases"] = es["cases"] + "; Cypher CREATE of an existing triple outside multigraph mode (adds nothing)"
es["gap"] = (es["gap"] + "; " if es["gap"] and es["gap"] != "none" else "") + "the Cypher CREATE writer is not in the edge_acceptance model (restated here by query.conformance#x02 and query.functions.path_elements#x01; merge widening, iteration 63)"
order = {b["block"]: i for i, b in enumerate(bb)}
ee.sort(key=lambda r: (0 if r["iteration"] != "63" else 1, order[r["block"]] if r["iteration"] == "63" else 0, r["id"]) if False else 0)
# keep file order, but place the new exclusion after its block's other rows
ee = [e for e in ee if e["id"] != "query.conformance#x10"]
pos = max(i for i, e in enumerate(ee) if e["block"] == "query.conformance") + 1
ee.insert(pos, {"id": "query.conformance#x10", "block": "query.conformance", "locator": row["locator"], "kind": "restatement",
                "owner": "query.writes.computed_values#o06",
                "reason": "the computed-value refusal between matched nodes is owned by query.writes.computed_values#o06 (graded there from cypher_exprs); conformance lists it as a known deviation. Withdrawn as obligation query.conformance#o03 at merge to avoid counting it twice (iteration 63); the id is retired",
                "iteration": "63"})
for b in bb:
    if b["block"] == "query.conformance":
        b["obligations"] = str(int(b["obligations"]) - 1); b["excluded"] = str(int(b["excluded"]) + 1)
        b["owners_checked"] += "; conformance#x10 -> query.writes.computed_values#o06 (merge)"

# ---- corrections from the independent spot-check (35-row deterministic sample; see HANDOFF section 7) ----
SC = "changed at merge after the iteration-63 independent spot-check: "
def fix(oid, why, **kw):
    r = next(o for o in oo if o["id"] == oid)
    for k, v in kw.items():
        r[k] = v
    if r["design_check"] in ("proved", "refuted") and r["grade"] != "full":
        r["check_scope"] = "narrowed"
    r["grade_source"] = r["grade_source"] + "; " + SC + why
    r["gap"] = (r["gap"] + "; " if r["gap"] and r["gap"] != "none" else "") + why
fix("structure.degree.cache.warm#o02", "warm_sources has no SQL role, so the SQL-rows-without-globals case is not stated; sources is an input tied to ^KG(out) only by a comment (spot-check row 2)", grade="partial")
fix("temporal.structural.mark.readers#o05", "the RDF/Cypher theorems cover only the marked row and the bulk-adopted quals None row, not explicit adoption with the write's own qualifiers; Row has no weight field (row 3)", grade="partial")
fix("query.paging#o08", "the 'x' ValueError case exists only in the as_built_page definition, not in the theorem; numeric-ness is an input (row 9)", grade="partial")
fix("query.functions.list_index#o05", "the literal theorem covers only Some(i) and the type rule only a RETURN column; native decline is a fixture observation (row 10)", check_scope="narrowed")
fix("query.functions.slice#o01", "only a row-variable lower bound is proved; l[a..b] does not parse (bug-cyp-122) and $l[$s..$e] fails (bug-cyp-125) (row 11)", grade="partial")
fix("install.inference#o07", "theorem_domain_type_not_lifted proves only the domain case in one 3-row world; range is not proved (row 12)", grade="partial")
fix("install.export.rdf.content#o11", "the theorem proves only the envelope's two blank subjects; the four triples exist only in the envelope definition and nothing reaches the parsed file (row 13)", grade="partial")
fix("search.embedding.check_on_write#o04", "the block covers every vector-writing path; the model covers store_embedding only (row 16)", grade="partial")
fix("search.fusion.rest#o02", "only /vectorSearch is modelled, by a single width-4 witness; the other REST body is not (row 18)", grade="partial")
fix("temporal.stats.distinct#o05", "the theorem requires a window inside one bucket and a single event and does not prove the untouched-bucket contrast (row 20)", check_scope="narrowed")
fix("temporal.labelset#o04", "no resolve function is modelled: canon only builds text and the store is a Set of texts; ResolveLabelSet is named only in a header comment (row 21)", grade="absent", model_locators="", design_check="none", check_scope="n/a")
fix("install.schema.not_ready#o04", "first_access maps the input booleans legacy/traces to the reasons, so the deciding detection is an input; the theorem also requires no record and no marker (row 22)", grade="partial")
fix("install.status.readiness#o02", "'the operation would answer' is a proxy (route_rows>0, ready_for_bfs); no search or traversal answer is modelled, so the witness stops before the reader (row 24)", grade="partial")
fix("search.scope.indexes#o03", "search.rs models Bm25.graph as set by build (BM25Index.cls:168); the fusion reader is reached only in playbook proofs-d1d bmn_l2.rs, not an active link (row 33)", grade="partial", model_locators=".g5/Verus_verification/models/search/search.rs::Bm25; .g5/Verus_verification/models/search/search.rs::build")
fix("temporal.labelset#o07", "val_text passes LVal::Num text through verbatim, so the '.5' spelling is a represented provider input with no theorem (row 34)", grade="partial", model_locators=".g5/Verus_verification/models/temporal_stats/temporal_stats.rs::val_text")
fe = next(o for o in oo if o["id"] == "fhir.event#o01")
fe["statement"] = "The /fhir-event route is deprecated and is removed in 5.0"
fe["grade_source"] += "; " + SC + "statement restored to the block text (it had imported 'since 4.1.0' and 'when called' from product code) (row 32)"
# search.fusion.python#o05 restated search.fusion.failed_leg#o02-#o04 while leaving out the raising text leg (row 5)
fp = next(o for o in oo if o["id"] == "search.fusion.python#o05")
oo = [o for o in oo if o["id"] != "search.fusion.python#o05"]
xs = [e for e in ee if e["block"] == "search.fusion.python"]
nx = max(int(e["id"].split("#x")[1]) for e in xs) + 1 if xs else 1
newx = {"id": f"search.fusion.python#x{nx:02d}", "block": "search.fusion.python", "locator": fp["locator"], "kind": "restatement",
        "owner": "search.fusion.failed_leg",
        "reason": "which legs multi_modal_search fuses is owned by search.fusion.failed_leg#o02-#o04 (text failure raises; vector/graph failure dropped; empty success kept); withdrawn as obligation search.fusion.python#o05 after the iteration-63 spot-check (row 5), id retired",
        "iteration": "63"}
pos = max(i for i, e in enumerate(ee) if e["block"] == "search.fusion.python") + 1 if xs else len(ee)
ee.insert(pos, newx)
for b in bb:
    if b["block"] == "search.fusion.python":
        b["obligations"] = str(int(b["obligations"]) - 1); b["excluded"] = str(int(b["excluded"]) + 1)
        b["owners_checked"] += f"; {newx['id']} -> search.fusion.failed_leg (spot-check)"
for r in oo:
    if r["id"] == "temporal.stats#o01":
        r["parent_entailment"] = r["parent_entailment"].replace("(temporal.stats.writers, not yet enumerated)", "(temporal.stats.writers#o01 to temporal.stats.writers#o06, enumerated in iteration 63 on the adjacency page)")
for r in bb:
    if r["iteration"] == "63":
        r["owners_checked"] = r["owners_checked"].replace("structure.edge.single (cross-page, not yet enumerated)", "structure.edge.single#o01 (cross-page; narrowed at merge)").replace("(cross-fork, not yet enumerated)", "(cross-fork; enumerated in iteration 63)")
wr("blocks.tsv", B, bb); wr("obligations.tsv", O, oo); wr("excluded.tsv", E, ee)
print("reconciled:", len(OWN), "owners narrowed; 1 obligation withdrawn as restatement; edge.single#o01 widened")
