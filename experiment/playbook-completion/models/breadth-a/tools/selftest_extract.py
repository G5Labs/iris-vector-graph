#!/usr/bin/env python3
"""Self-test of the static extractors (playbook §5: every structural check has a self-test).

Feeds srcindex fixed SQL texts and ObjectScript lines whose footprint is known and fails on any misclassification,
including injected cases the extractor must NOT count (a comparison in an If, a global inside a string, a commented
line, a DELETE's FROM counted as a read).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import srcindex as S  # noqa: E402

fails = []


def check(name, cond):
    if not cond:
        fails.append(name)


e = S.sql_effects("INSERT INTO Graph_KG.rdf_edges (s,p,o_id) SELECT ?,?,? WHERE NOT EXISTS (SELECT 1 FROM Graph_KG.rdf_edges)")
check("insert target", ("insert", "Graph_KG.rdf_edges") in e["writes"])
check("guard read", ("from", "Graph_KG.rdf_edges") in e["reads"])
e = S.sql_effects("DELETE FROM {?}.rdf_props WHERE s = ?")
check("delete target placeholder schema", ("delete", "Graph_KG.rdf_props") in e["writes"])
check("delete FROM not a read", not e["reads"])
e = S.sql_effects("SELECT s FROM %IGNOREINDEX Graph_KG.rdf_labels.idx_labels_label Graph_KG.rdf_labels WHERE x=1")
check("index hint skipped", e["reads"] == [("from", "Graph_KG.rdf_labels")])
e = S.sql_effects("INSERT %NOINDEX %NOCHECK INTO Graph_KG.nodes (node_id) VALUES (?)")
check("hinted insert", ("insert", "Graph_KG.nodes") in e["writes"] and "%NOINDEX" in e["hints"])
e = S.sql_effects("DROP INDEX idx_props_key_val")
check("unqualified drop index", ("ddl-drop-index", "index:idx_props_key_val") in e["writes"])
e = S.sql_effects("the value FROM the cache is used")  # prose, not SQL
check("prose ignored", not e["reads"] and not e["writes"])

m = S.ClsMethod("x.cls", "T.C", "M", "ClassMethod", 1, 1, "")
ci = S.ClsIndex([])
for i, line in enumerate([
    '\tSet ^KG("out", g, s) = 1, x = ^KG("gen", g, s)',
    '\tIf ^KG("deg", g) = 2 { Quit }',
    '\tKill ^KG("degc", g)',
    '\tSet tmp = $Increment(^KG("__version"))',
    '\tSet msg = "Set ^NOTAGLOBAL(1) = 2"',
    '\t// Set ^COMMENTED(1) = 1',
    '\tLock +^IVG.AdjW(g)#"S":5',
    '\tLock -^IVG.AdjW(g)#"S"',
    '\tTSTART',
    '\tIf $TLevel > 0 { TROLLBACK }',
    '\tMerge ^A("x") = ^B("y")',
], 1):
    ci._scan_line(m, line, i)
w = {g for _, g in m.writes}
r = {g for _, g in m.reads}
check("set target", '^KG("out")' in w)
check("set rhs read", '^KG("gen")' in r)
check("if comparison is a read", '^KG("deg")' in r and '^KG("deg")' not in w)
check("kill", '^KG("degc")' in w)
check("$increment", '^KG("__version")' in w)
check("global in string ignored", not any("NOTAGLOBAL" in g for g in w | r))
check("comment ignored", not any("COMMENTED" in g for g in w | r))
check("lock acquire", any("acquire ^IVG.AdjW(g) mode=S timeout=5" == l for _, l in m.locks))
check("lock release", any(l.startswith("release ^IVG.AdjW(g)") for _, l in m.locks))
check("tstart", any(t.upper() == "TSTART" for _, t in m.txn))
check("trollback no level", any(t.upper() == "TROLLBACK" for _, t in m.txn))
check("merge target/source", '^A("x")' in w and '^B("y")' in r)

print("selftest:", "PASS" if not fails else "FAIL " + ", ".join(fails))
sys.exit(1 if fails else 0)
