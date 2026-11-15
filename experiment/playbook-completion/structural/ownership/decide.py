#!/usr/bin/env python3
"""Turn the registered ownership check (st-check-own-census) into matrix cells, proposed findings and the method record.

    python decide.py OWNERSHIP_JSON

Writes structural/ownership/cells.json, findings-proposed.json and method.json. Reads only the check's output and the
finding map below (each mapping cites the finding it reuses or the new record it proposes).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = ["run:st-check-own-census", "run:st-check-own-controls", "run:st-control-own-selftest"]
MODULES = ["01", "02", "03", "04", "05", "06", "08", "09", "10", "15", "16", "18"]

# (writer module, store) -> finding covering that second write. Reused ids keep their original records.
REUSE = {
    ("18", 'global:^KG("__version")'): "F-0404", ("18", 'global:^KG("degc")'): "F-0404",
    ("18", 'global:^KG("degw")'): "F-0404", ("18", 'global:^KG("gen")'): "F-0404",
    ("11", "sql:Graph_KG.kg_NodeEmbeddings"): "F-0618", ("11", "sql:Graph_KG.kg_NodeEmbeddings_optimized"): "F-0618",
    ("16", "sql:Graph_KG.rdf_props"): "F-1604",
}
NEW = {
    ("04", 'global:^KG("prop")'): "F-C0440",
    ("06", 'global:^NKG("q")'): "F-C0640",
    ("08", "sql:Graph_KG.kg_NodeEmbeddings"): "F-C0840", ("08", "sql:Graph_KG.rdf_reifications"): "F-C0840",
    ("10", 'global:^KG("__version")'): "F-C1040",
    ("12", "global:^ArnoKG"): "F-C1240",
    ("15", 'global:^KG("label")'): "F-C1540", ("15", "sql:Graph_KG.docs"): "F-C1540",
    ("15", "sql:Graph_KG.kg_EdgeEmbeddings"): "F-C1540", ("15", "sql:Graph_KG.kg_NodeEmbeddings"): "F-C1540",
    ("15", "sql:Graph_KG.kg_NodeEmbeddings_optimized"): "F-C1540", ("15", "sql:kg_emb_*"): "F-C1540",
    ("15", "sql:kg_eemb_*"): "F-C1540",
    ("17", "sql:Graph_KG.docs"): "F-C1740", ("17", "sql:Graph_KG.rdf_reifications"): "F-C1740",
}
UNOWNED_00 = "modules/00.json reconciliation (unowned product entry points import_rdf, materialize_inference / retract_inference; open under 3.1-coverage)"
# declared co-writes whose consequence an existing finding records (listed with the cell, not as an ownership defect)
DECLARED_WITH_FINDINGS = {
    ("12", 'global:^IVG.Ledger("stmt")'): "F-1114", ("12", 'global:^IVG.Ledger("tuple")'): "F-1114",
    ("18", 'global:^IVG.Ledger'): "F-1801", ("05", "sql:Graph_KG.nodes"): "F-0503",
    ("15", "sql:Graph_KG.nodes"): "F-1502", ("15", "sql:Graph_KG.rdf_labels"): "F-1503",
}
for _sub in ("rec", "stmt", "tuple", "idem", "idemRedacted", "redactedRev", "redacting", "head", "stmtNext", "idBySeq",
             "revById", "meta"):
    DECLARED_WITH_FINDINGS[("18", f'global:^IVG.Ledger("{_sub}")')] = "F-1801"
DECLARED_WITH_FINDINGS[("18", "sql:Graph_KG.ledger_revisions")] = "F-1801"
DECLARED_WITH_FINDINGS[("18", "sql:Graph_KG.ledger_stats")] = "F-1801"
ADR_FINDING = {"ADR-0011": ["F-0404", "F-1806"], "ADR-0002": ["F-1805", "F-1806"]}
CONDITIONAL_FINDING = ["F-1806"]


def finding_for(m, st):
    return REUSE.get((m, st)) or NEW.get((m, st)) or (UNOWNED_00 if m == "00" else None)


def main() -> int:
    d = json.loads(Path(sys.argv[1]).read_text())
    rep, pm = d["report"], d["per_module"]
    cells, method_rows = [], {}
    for m in MODULES:
        p = pm.get(m, {"writes_others": [], "others_write_own": [], "own_single": [], "adr": []})
        writes_und = [w for w in p["writes_others"] if w["class"] == "undeclared"]
        writes_dec = [w for w in p["writes_others"] if w["class"] == "declared"]
        writes_cond = [w for w in p["writes_others"] if w["class"] == "undeclared-conditional"]
        own_written = []
        findings = set()
        for o in p["others_write_own"]:
            st = o["store"]
            for wm, cls_ in o["writers"].items():
                f = finding_for(wm, st) if cls_ == "undeclared" else (CONDITIONAL_FINDING[0] if cls_ == "undeclared-conditional" else None)
                own_written.append({"store": st, "writer": wm, "class": cls_,
                                    "declared_by": rep[st]["writers"][wm]["declared_by"], "finding": f})
                if f and f.startswith("F-"):
                    findings.add(f)
                g = DECLARED_WITH_FINDINGS.get((wm, st))
                if g:
                    findings.add(g)
        for w in writes_und:
            f = finding_for(m, w["store"])
            w["finding"] = f
            if f and f.startswith("F-"):
                findings.add(f)
        for w in writes_dec:
            g = DECLARED_WITH_FINDINGS.get((m, w["store"]))
            if g:
                findings.add(g)
        if writes_cond:
            findings |= set(CONDITIONAL_FINDING)
        adr = p["adr"]
        for a in adr:
            findings |= set(ADR_FINDING.get(a["adr"], []))
        # conditional writes INTO this module's stores (any-global loaders) are F-1806 too
        if any(o["class"] == "undeclared-conditional" for o in own_written):
            findings.add("F-1806")
        fails = bool(writes_und or writes_dec or writes_cond or own_written or adr)
        own_stores = sorted({st for st, r in rep.items() if r["owner"] == m})
        dec_by = defaultdict(set)
        for w in writes_dec:
            dec_by[w["declared_by"]].add(w["store"])
        for o in own_written:
            if o["class"] == "declared":
                dec_by["into own: " + o["declared_by"]].add(f"{o['store']}<-{o['writer']}")
        basis = []
        if own_stores:
            basis.append(f"owns {len(own_stores)} stores; {len({o['store'] for o in own_written})} of them have another writer module")
        if writes_und:
            basis.append("undeclared writes into other modules' stores: " + "; ".join(
                f"{w['store']} (owner {w['owner']}, {w['n_sites']} site(s), e.g. {w['sites'][0]})" for w in writes_und))
        und_in = [o for o in own_written if o["class"] == "undeclared"]
        if und_in:
            basis.append("undeclared writers of its stores: " + "; ".join(f"{o['writer']} -> {o['store']}" for o in und_in))
        if writes_dec or any(o["class"] == "declared" for o in own_written):
            basis.append("declared co-writers (single ownership fails by design): " + "; ".join(
                f"{k}: {len(v)}" for k, v in sorted(dec_by.items())))
        if writes_cond or any(o["class"] == "undeclared-conditional" for o in own_written):
            basis.append("conditional: run-time-named writers (Graph.KG.Snapshot.ImportGlobals / SetNodeJSON load any global; restore's allow-listed roots)")
        if adr:
            basis.append(f"{len(adr)} ADR class violations ({', '.join(sorted({a['adr'] for a in adr}))})")
        cell = {"gate": "3.4-ownership", "module": m, "status": "closed",
                "evidence": RUNS + ["experiment/playbook-completion/structural/ownership/method.json",
                                    "experiment/playbook-completion/structural/ownership/ownership.py",
                                    "experiment/playbook-completion/structural/ownership/census_all.py"],
                "evidence_grade": "inspected (mechanical source census, registered check with self-test; census completeness and journal controls)",
                "level": "product", "product_obligation": "fails" if fails else "holds",
                "product_basis": ". ".join(basis) if basis else "every store it writes is its own and no other module writes them",
                "as_built_findings": sorted(f for f in findings if f.startswith("F-")),
                "remaining": ("source-level census: run-time names rest on the cited resolution hints in census_all.py/ownership.py "
                              "(TABLE_HINTS, LINE_HINTS, TEMPLATE_USERS); a write form the scanner does not recognise is covered only "
                              "as far as the registered census (268/268) and the 393 journal-observed pairs reach. Whether declared "
                              "shared ownership is accepted is a maintainer decision (§3.8).")}
        if m == "03":
            cell["remaining"] += " Unowned writers of content tables: " + UNOWNED_00 + "."
        if m == "01":
            cell["remaining"] += " DDL (162 schema objects) is reported in ownership.json 'ddl', not decided here; F-0107 (unqualified DROP INDEX) is the open DDL ownership finding."
        cells.append(cell)
        method_rows[m] = {"decision": f"closed, product {'fails' if fails else 'holds'}",
                          "reason": cell["product_basis"],
                          "writes_others_undeclared": writes_und, "writes_others_declared": writes_dec,
                          "writes_others_conditional": [{"store": w["store"], "owner": w["owner"], "sites": w["conditional_sites"]} for w in writes_cond][:40],
                          "own_stores": own_stores, "own_written_by_others": own_written, "adr": adr,
                          "findings": sorted(f for f in findings if f.startswith("F-"))}
    (HERE / "cells.json").write_text(json.dumps({"cells": cells}, indent=1) + "\n")
    second_writer_table = []
    for st, r in sorted(rep.items()):
        for wm, w in sorted(r["writers"].items()):
            if w["class"] in ("owner", "sole-writer", "not-ivg"):
                continue
            second_writer_table.append({"store": st, "owner": r["owner"], "writer": wm, "class": w["class"],
                                        "declared_by": w["declared_by"], "basis": w["basis"],
                                        "finding": finding_for(wm, st) if w["class"] == "undeclared" else
                                        ("F-1806" if w["class"] == "undeclared-conditional" else DECLARED_WITH_FINDINGS.get((wm, st))),
                                        "sites": (w["sites"] or w["conditional_sites"] or w["delegate_sites"] or w["unserved_sites"])[:6]})
    method = {
        "gate": "3.4-ownership", "pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e",
        "runs": {"st-check-own-census": "check fail (the product has no single write owner for 98 of 101 stores)",
                 "st-check-own-controls": "check pass (completeness 268/268 vs followup-writer-census; product guard agrees; 393 journal pairs explained, 0 gaps)",
                 "st-control-own-selftest": "control pass (8/8 seeded cases)"},
        "method": [
            "Census (census_all.py): a generalised copy of tools/writer_census.py over every durable store of the pin. ObjectScript: Set/Merge targets (multi-target Set, $Piece/$List/$Extract), Kill/ZKill, $Increment/$I/$Sequence, indirection resolved from the method's Set/For lines, returned $Name of a ..Method, or same-class callers' arguments; %Save/%KillExtent/%DeleteId of the persistent classes; SQL DML/DDL text (embedded &sql, literals, concatenation across continuation lines). Python: SQL text literals and rendered f-string/+/%/format text with run-time names resolved in the function, module, callers, a same-name function's return value, or a cited hint; Native API set/kill/increment with literal or resolved names and first subscripts. SQL files. Process-private ^|| and IRIS system globals excluded.",
            "Stores: sql:Graph_KG.<table> whatever schema the text names (the IVG Schema is run-time), sql:kg_emb_* / sql:kg_eemb_* for routes, global:^Root, and for ^KG/^NKG/^IVG.Ledger the first subscript; a whole-root Kill writes every sub-store; a run-time sub-store or an any-global loader is a conditional write of every store it can reach.",
            "Site -> module: models/breadth-c/inventory.json (Class.Method entries; innermost Python entry; entries with no owner are module 00), then same-file callers for private helpers, the breadth-A function lists, and file owners; cited overrides for SQL templates executed elsewhere (migrations/statements.py, GraphSchema.get_bulk_insert_sql) and the example resolver the sample API serves.",
            "Declared owner per store (ownership.py DECLARED, each with its citation: ontology Root/Scope lines, ADR-0011, ADR-0002, GraphStores.Inventory, snapshot.py STORE_PLAN). A writer module other than the owner is: declared (named by the owner's ontology, by the writer's ontology, or by a product store plan), delegate (a method the owner's Scope names as its writer), unserved (code no product path reaches), undeclared, or undeclared-conditional. Every non-owner writer breaks the single-owner rule; only undeclared ones are ownership defects in the product's own terms (findings). ADR class lists are checked per site.",
            "Controls: completeness against the registered census (every one of its 268 product sites found, store-compatible); the product's own source guard tests/unit/test_adjacency_single_writer.py agrees on the .cls writers of ^KG out/in; the 393 journal-observed (entry, store) pairs of footprints/NN.json are each explained by a census site reached from the entry (or a census writer in a reached module, a routed table created in the action, caller SQL, or a cited reading).",
            "Self-test: seeded files assigned to module 16 (a multi-target Set of ^KG(\"out\"), a delegating Adjacency.Put call, an indirection Kill of $Name(^BM25Idx(...)), an f-string DELETE on rdf_reifications, a Native API kill with a variable global name) and to module 04 (its own write): all 8 expectations met.",
        ],
        "counts": {k: d[k] for k in ("files", "sites", "stores", "multi_writer_stores", "undeclared_pairs", "declared_pairs",
                                     "conditional_pairs", "adr_violations")},
        "per_module": method_rows,
        "second_writer_table": second_writer_table,
        "not_decided_here": {"ddl": "162 schema objects and their DDL writer modules are listed in ownership.json 'ddl' (setup's DDL, routes created by VEC, FHIR tables by INT, compiled-plan classes by NAT); DDL ownership is not part of these cells",
                             "modules_07_11_12_13_14_17": "their 3.4-ownership cells were already closed by other lanes; this run's data for them is in per_module of ownership.json (11: PurgeAll kills RED's marker sub-stores (admin reset, declared by writer); 12: F-C1240; 17: F-C1740)"},
    }
    (HERE / "method.json").write_text(json.dumps(method, indent=1) + "\n")
    print(json.dumps([{k: c[k] for k in ("module", "status", "product_obligation", "as_built_findings")} for c in cells], indent=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
