#!/usr/bin/env python3
"""§3.4 declared reads, modules 04 and 10: the non-interference oracle (reads3/ni_base.py, a copy of reads2/ni_base.py,
extended by reads3/ni3core.py) over the read/both entry points structural/reads/cells.json left unchecked.

    locks.sh iris timeout 900 python ni3.py --self-test --out FILE           # the copied self-test (ni_base.main)
    locks.sh iris timeout 900 python ni3.py --modules 04 --out FILE [--only TEXT] [--part i/n]
    python ni3.py --list                                                       # the cases and their keys, no IRIS

Cases are in ni3_04.py and ni3_10.py; per case: base state, the action twice (stable), each perturbation OUTSIDE the
declared footprint (answer must not change), an INSIDE perturbation (should change), perturbations declared inside
(reported, expected to change). A keyed case evaluates several entry points on the same states; each key has its
own verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ni3core as K  # noqa: E402
import lib  # noqa: E402


def all_cases():
    import ni3_04
    import ni3_10
    return ni3_04.cases() + ni3_10.cases()


def selftest_ext():
    """A keyed case with two seeded readers before and after a prep step (sync): one graph-blind (must be flagged),
    one scoped to G1 (must hold), a vacuous key and a raising key (both undecided, never holding)."""
    G1 = K.G1

    def blind(e, c):
        return sorted(map(list, c.sql('SELECT "key", val FROM Graph_KG.rdf_props WHERE s = ?', "a")))

    def scoped(e, c):
        return sorted(map(list, c.sql('SELECT "key", val FROM Graph_KG.rdf_props WHERE s = ? AND graph_id = ?', "a", G1)))

    def blind_kg(e, c):
        return sorted({str(g) for g, _ in c.o.iterator("^KG", "out").items() if int(c.o.isDefined("^KG", "out", g, "a"))})

    def scoped_kg(e, c):
        return K.walk(c, "^KG", "out", G1, "a")

    def boom(e, c):
        raise RuntimeError("seeded failure")
    return K.C3("selftest", "SEEDED keyed case (reads3 extension)", K.multi([
        ("SEEDED blind", blind), ("SEEDED scoped", scoped), ("SEEDED blind after prep", blind_kg),
        ("SEEDED scoped after prep", scoped_kg), ("SEEDED vacuous", lambda e, c: "PYUNAVAIL"), ("SEEDED error", boom)]),
        K.NI.base_in(G1), "G1's rows and ^KG(out, G1) of a", {"same ids in other graphs": K.NI.other_graphs(G1)},
        inside=K.NI.inside_nodes(G1), prep=lambda e, c: e.sync(),
        vacuous={"SEEDED vacuous": lambda v: "seeded vacuous answer" if v == "PYUNAVAIL" else None})


def main() -> int:
    if "--list" in sys.argv:
        for x in all_cases():
            print(x["module"], "|", x["id"])
        return 0
    out_p = Path(sys.argv[sys.argv.index("--out") + 1])
    if "--self-test" in sys.argv:
        # 1. the copied oracle's own self-test (ni_base.main: seeded graph-blind / scoped / undeclared-table readers)
        part1 = out_p.with_name(out_p.stem + "-ni_base.json")
        sys.argv = [sys.argv[0], "--self-test", "--out", str(part1)]
        rc1 = K.NI.main()
        # 2. the reads3 extension (keyed verdicts, prep after the perturbation, vacuous / error keys)
        ext = selftest_ext()
        res = K.run_case3(ext)
        pk = res["per_key"]
        ok3 = (pk["SEEDED blind"]["verdict"] == "violation" and pk["SEEDED scoped"]["verdict"] == "holds"
               and pk["SEEDED blind after prep"]["verdict"] == "violation" and pk["SEEDED scoped after prep"]["verdict"] == "holds"
               and pk["SEEDED vacuous"]["verdict"] == "undecided-vacuous" and pk["SEEDED error"]["verdict"] == "undecided-error"
               and pk["SEEDED blind"]["inside_changed"] and pk["SEEDED scoped"]["inside_changed"])
        first = json.loads(part1.read_text())
        summary = {**first["summary"], "self_test_reads3_extension": "PASS" if ok3 else "FAIL"}
        lib.dump(out_p, {"summary": summary, "ni_base_selftest": first, "extension_case": res})
        print(json.dumps(summary))
        return 0 if (rc1 == 0 and ok3) else 1
    c = lib.conn()
    info = {"engine": lib.version(c), "namespace": lib.NS, "argv": sys.argv[1:]}
    c.close()
    mods = sys.argv[sys.argv.index("--modules") + 1].split(",")
    sel = [x for x in all_cases() if x["module"] in mods]
    if "--only" in sys.argv:
        pats = sys.argv[sys.argv.index("--only") + 1].split("||")
        sel = [x for x in sel if any(p in x["id"] for p in pats)]
    if "--part" in sys.argv:
        i, n = map(int, sys.argv[sys.argv.index("--part") + 1].split("/"))
        sel = [x for j, x in enumerate(sel) if j % n == i - 1]
    info["cases"] = [x["id"] for x in sel]
    K.run_all(sel, out_p, info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
