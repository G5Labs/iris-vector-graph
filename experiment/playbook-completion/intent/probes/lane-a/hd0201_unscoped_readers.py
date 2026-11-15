"""HD-0201 probe: what does a Python read with no graph argument read?

Contract under test: docs/USER_GUIDE.md:462-463 (blame 9b313a2c, 2026-11-03): "Python methods that write or read take
`graph=`; omitted, they mean the default graph, never every graph." (also the rule maintainer commits R219 99903e9c and
R249 1b439ea0 apply to the counters). CONTEXT.md:27-30: the default graph is "the graph a write or read gets when it
names none".

Fixture (probe-private ids iaNNNN:*, named graph ia-0201):
  default graph : ia0201:y  label IA0201D
  graph ia-0201 : ia0201:y  label IA0201L ; ia0201:x label IA0201L
Oracle per reader, called with no graph argument:
  default-graph reading (USER_GUIDE)  -> nothing labelled IA0201L exists; x does not exist.
  all-graphs reading (docstrings "in all graphs" / "not graph-scoped")  -> x and y.
  get_nodes_by_label: a returned node must carry the label asked for (any reading); hydrating ids of every graph from
  the default graph violates every reading (finding F-0206).
Verdict: pass only if every reader follows the USER_GUIDE rule; fail records which readers do not.
"""
from __future__ import annotations

import _common as C

G = "ia-0201"
L, D = "IA0201L", "IA0201D"


def main() -> None:
    c = C.conn()
    e = C.engine(c)
    try:
        e.erase_graph(G)
        e.delete_node("ia0201:y", graph="")
        assert e.create_node("ia0201:y", labels=[D])
        assert e.create_node("ia0201:y", labels=[L], graph=G)
        assert e.create_node("ia0201:x", labels=[L], graph=G)

        r = {}
        r["get_node_ids_by_label"] = sorted(e.get_node_ids_by_label(L))
        r["get_nodes_by_label"] = sorted(((n["id"], sorted(n.get("labels", []))) for n in e.get_nodes_by_label(L)))
        r["get_node_ids_by_property(id)"] = sorted(i for i in e.get_node_ids_by_property("id") if i.startswith("ia0201:"))
        r["nodes_exist([x])"] = sorted(e.nodes_exist(["ia0201:x"]))
        r["get_node(x)"] = e.get_node("ia0201:x")
        r["get_nodes([x])"] = e.get_nodes(["ia0201:x"])
        r["count_nodes(label=L)"] = e.count_nodes(label=L) if hasattr(e, "count_nodes") else "n/a"
        for k, v in r.items():
            C.obs(reader=k, answer=v)

        violations = []
        if r["get_node_ids_by_label"]:
            violations.append("get_node_ids_by_label reads every graph")
        if r["nodes_exist([x])"]:
            violations.append("nodes_exist reads every graph")
        if r["get_node_ids_by_property(id)"] != ["ia0201:y"]:
            violations.append("get_node_ids_by_property reads every graph")
        bad_hydration = [i for i, labels in r["get_nodes_by_label"] if L not in labels]
        if bad_hydration:
            violations.append(f"get_nodes_by_label returned {bad_hydration} without label {L} (ids of every graph "
                              "hydrated from the default graph, F-0206)")
        scoped_ok = r["get_node(x)"] is None and r["count_nodes(label=L)"] in (0, "n/a")
        C.obs(scoped_readers_follow_default_graph=scoped_ok)
        C.obs(violations=violations)
        if violations:
            C.verdict("fail", "; ".join(violations))
        else:
            C.verdict("pass", "every unscoped reader read only the default graph")
    finally:
        e.erase_graph(G)
        e.delete_node("ia0201:y", graph="")
        C.obs(cleanup_left=c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'ia0201:'"))
        c.close()


if __name__ == "__main__":
    main()
