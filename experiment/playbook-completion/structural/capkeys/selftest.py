#!/usr/bin/env python3
"""Self-tests of the structural lane's capacity, key and FK oracles (seeded violations must be caught).

    python selftest.py OUT.json              # pure: synthetic states, no IRIS
    locks.sh iris python selftest.py OUT.json --live   # adds the live reader checks on AUDITD scratch globals

Pure part: eval_keys and eval_fk on a clean synthetic state report nothing; each seeded state (one violation of one
condition) must be reported with exactly that condition's code and no other. classify (value-size outcomes) on
synthetic (error, residue, read-back) triples must give each outcome. is_counter / benign must keep row data out of
the counter set. Live part: kg_leaves reads seeded ^IVGAuditDKeys leaves exactly (then kills them); scan_from sees
the namespace's rows; a clean product-written graph gives no key and no FK violation.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "live"))
sys.path.insert(0, str(HERE))


def clean_key_state():
    return {"rows": {"nodes": [("", "a"), ("", "b"), ("g", "a")],
                     "rdf_labels": [("", "a", "L"), ("g", "a", "L")],
                     "rdf_props": [("", "a", "p")],
                     "rdf_edges": [("a", "R", "b", "", "0")],
                     "kg_NodeEmbeddings": [], "rdf_reifications": []},
            "edges": [("a", "R", "b", "", "0", "1")],
            "kg": {"out": [("0", "a", "R", "b")], "in": [("0", "b", "R", "a")],
                   "label": [("0", "L", "a"), ("g", "L", "a")]}}


def key_seeds():
    s = []
    x = clean_key_state(); x["rows"]["nodes"].append(("", "a")); s.append(("duplicate node row", x, "K1"))
    x = clean_key_state(); x["rows"]["rdf_edges"].append(("a", "R", "b", "", "0")); s.append(("duplicate edge key", x, "K1"))
    x = clean_key_state(); x["rows"]["rdf_props"].append(("", "a", "p")); s.append(("duplicate prop key", x, "K1"))
    x = clean_key_state(); x["kg"]["out"] = []; s.append(("row without out leaf", x, "K2"))
    x = clean_key_state(); x["kg"]["in"].append(("0", "z", "R", "a")); s.append(("in leaf without row", x, "K2"))
    x = clean_key_state(); x["kg"]["label"].append(("0", "L", "zz")); s.append(("label index without row", x, "K2"))
    x = clean_key_state(); x["edges"].append(("b", "R", "a", "", "0", "1")); x["kg"]["out"].append(("0", "b", "R", "a"))
    x["kg"]["in"].append(("0", "a", "R", "b")); s.append(("repeated edge id", x, "K3"))
    return s


def clean_fk_state():
    return {"nodes": [("a", ""), ("b", ""), ("a", "g")], "edges": [("a", "b", "", 1)],
            "labels": [("a", "L", ""), ("a", "L", "g")], "props": [("a", "p", "")], "emb": [("a", "")],
            "kg_out": [("0", "a", "R", "b")], "kg_in": [("0", "b", "R", "a")], "kg_label": [("0", "L", "a")],
            "kg_tout": [("0", "17", "a", "T", "b")], "reif": [("a", 1)]}


def fk_seeds():
    s = []
    mk = clean_fk_state
    x = mk(); x["edges"].append(("a", "q", "", 2)); s.append(("edge to missing node", x, "F1"))
    x = mk(); x["labels"].append(("q", "L", "")); s.append(("label of missing node", x, "F2"))
    x = mk(); x["props"].append(("b", "p", "g")); s.append(("prop of node missing in its graph", x, "F3"))
    x = mk(); x["emb"].append(("q", "")); s.append(("embedding of missing node", x, "F4"))
    x = mk(); x["kg_out"].append(("g", "a", "R", "b")); s.append(("adjacency endpoint missing in graph", x, "F5"))
    x = mk(); x["kg_label"].append(("g", "L", "b")); s.append(("label index of missing node", x, "F5"))
    x = mk(); x["kg_tout"].append(("0", "18", "a", "T", "q")); s.append(("temporal edge to missing node", x, "F6"))
    x = mk(); x["reif"].append(("b", 99)); s.append(("reification of missing edge", x, "F7"))
    x = mk(); x["reif"].append(("zz", 1)); s.append(("reifier node missing", x, "F7"))
    return s


def codes(viol):
    return sorted({v.split(" ")[0] for v in viol})


def pure():
    import keys
    import fk
    import cap_values
    import cap_width
    out = {"keys": [], "fk": [], "classify": [], "counter": []}
    ok = True
    r = keys.eval_keys(clean_key_state())
    out["keys"].append({"seed": "clean", "violations": r["violations"], "pass": not r["violations"]})
    ok &= not r["violations"]
    for name, st, code in key_seeds():
        r = keys.eval_keys(st)
        passed = codes(r["violations"]) == [code]
        out["keys"].append({"seed": name, "expect": code, "got": codes(r["violations"]), "pass": passed})
        ok &= passed
    r = fk.eval_fk(clean_fk_state())
    out["fk"].append({"seed": "clean", "violations": r["violations"], "pass": not r["violations"]})
    ok &= not r["violations"]
    for name, st, code in fk_seeds():
        r = fk.eval_fk(st)
        passed = codes(r["violations"]) == [code]
        out["fk"].append({"seed": name, "expect": code, "got": codes(r["violations"]), "pass": passed})
        ok &= passed
    for args, want in (((None, [], "abc", None, "abc"), "exact"), ((None, [], "ab", None, "abc"), "silent-truncation"),
                       ((None, [], None, None, "abc"), "silent-loss"), ((None, [], "xyz", None, "abc"), "silent-change"),
                       (("err", [], None, None, "abc"), "clean-refusal"), (("err", ["^KG(\"tout\",0,1)"], None, None, "abc"), "partial"),
                       ((None, [], None, "boom", "abc"), "reader-failure")):
        got = cap_values.classify(*args)
        out["classify"].append({"args": str(args)[:80], "want": want, "got": got, "pass": got == want})
        ok &= got == want
    for node, want in (('^t52S.XCFT.1', True), ('^KG("__version",0)', True), ('^KG("gen",0,"a")', True),
                       ('^KG("out",0,"a","R","b")', False), ('^t52S.XCFT.1("a")', False), ('^KG("tout",0,1,"a","R","b")', False)):
        got = cap_width.is_counter(node) or cap_values.benign(node)
        passed = bool(got) == want
        out["counter"].append({"node": node, "counter": bool(got), "pass": passed})
        ok &= passed
    return ok, out


def live():
    import lib
    import keys
    import fk
    out = {}
    c = lib.conn()
    ok = True
    try:
        c.o.kill("^IVGAuditDKeys")
        seeded = {("0", "a", "R", "b"), ("g", "x", "S", "y")}
        for G, a, p, b in seeded:
            c.o.set(1, "^IVGAuditDKeys", "out", 0 if G == "0" else G, a, p, b)
        got = keys.kg_leaves(c, "out", "^IVGAuditDKeys")
        out["kg_leaves_seeded"] = {"seeded": sorted(seeded), "read": sorted(got), "pass": got == seeded}
        ok &= got == seeded
        c.o.kill("^IVGAuditDKeys")
        out["scratch_removed"] = not int(c.o.isDefined("^IVGAuditDKeys"))
        lib.reset(c)
        e = lib.engine(c)
        e.create_node("st:a", labels=["L"], properties={"p": "1"})
        e.create_node("st:b", labels=["L"])
        e.create_edge("st:a", "R", "st:b")
        e.create_node("st:a", labels=["L"], graph="stg")
        c.conn.commit()
        kr = keys.keys_check(c)
        fr = fk.fk_check(c)
        out["clean_product_graph"] = {"key_violations": kr["violations"], "fk_violations": fr["violations"],
                                      "scan_from": keys.scan_from(c, "Graph_KG.nodes"), "row_counts": kr.get("row_counts"),
                                      "pass": not kr["violations"] and not fr["violations"] and kr["row_counts"]["nodes"] == 3}
        ok &= out["clean_product_graph"]["pass"]
        lib.reset(c)
    finally:
        c.close()
    return ok, out


def main() -> int:
    outp = Path(sys.argv[1])
    ok, res = pure()
    res = {"pure": res, "pure_pass": ok}
    if "--live" in sys.argv:
        lok, lres = live()
        res["live"] = lres
        res["live_pass"] = lok
        ok &= lok
    res["pass"] = ok
    outp.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:4000])
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
