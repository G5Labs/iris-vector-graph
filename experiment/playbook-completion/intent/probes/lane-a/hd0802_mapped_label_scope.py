"""HD-0802 probe: does a label mapped to a SQL table answer under every USE GRAPH scope?

Sources: CONTEXT.md:27-32 (graphs "are isolation units"; "Every node ... belongs to exactly one graph");
USER_GUIDE.md:401-402 ("`USE GRAPH` scopes a query to one graph"); map_sql_table (iris_vector_graph/_engine/fhir.py:88-105,
docs/API_REFERENCE.md:2449-2455) takes no graph and says nothing about graphs. No source settles the mapped case.

Steps: scratch table IVGAudit.Mapped0802 (2 rows), mapped to label IaMapped0802; an ordinary node of label IaOrd0802 in
graph ia-0802-a (control). Queries: count of mapped label with no USE GRAPH, under USE GRAPH 'ia-0802-a' (a graph with
content), under USE GRAPH 'ia-0802-none' (a graph with nothing), and the control label under 'ia-0802-none'.
Oracle (which reading each outcome supports):
  mapped count == 2 under both named scopes  -> reading (a): a mapping is namespace-wide, every scope sees its rows
  mapped count == 0 under a named scope      -> reading (b)/(c) (graph-owned mapping or refusal)
  an error under a named scope               -> reading (c)
  control: ordinary label under 'ia-0802-none' == 0 (graph scoping works for graph tables)
No stated contract is violated by either outcome (none exists for mapped labels): result `pass` records the as-built
reading; the decision stays open.
Cleanup: remove_table_mapping, DROP TABLE, erase the probe graph.
"""
from __future__ import annotations

import _common as C

TABLE = "IVGAudit.Mapped0802"
LABEL = "IaMapped0802"
GA, GN = "ia-0802-a", "ia-0802-none"


def count(e, q):
    try:
        r = e.execute_cypher(q)
        return {"rows": [list(x) for x in r.rows], "error": getattr(r, "error", None)}
    except Exception as ex:  # noqa: BLE001
        return {"raised": f"{type(ex).__name__}: {str(ex)[:200]}"}


def main():
    c = C.conn()
    e = C.engine(c)
    verdict = ("incomplete", "did not finish")
    try:
        c.sql(f"CREATE TABLE {TABLE} (pid VARCHAR(64) PRIMARY KEY, name VARCHAR(64))")
        c.sql(f"INSERT INTO {TABLE} (pid, name) VALUES ('ia0802:m1', 'one')")
        c.sql(f"INSERT INTO {TABLE} (pid, name) VALUES ('ia0802:m2', 'two')")
        C.obs(step="map", result=e.map_sql_table(TABLE, "pid", LABEL, property_columns=["name"]))
        e.create_node("ia0802:o1", labels=["IaOrd0802"], graph=GA)
        res = {
            "mapped_all_graphs": count(e, f"MATCH (n:{LABEL}) RETURN count(n) AS k"),
            "mapped_use_graph_a": count(e, f"USE GRAPH '{GA}' MATCH (n:{LABEL}) RETURN count(n) AS k"),
            "mapped_use_graph_none": count(e, f"USE GRAPH '{GN}' MATCH (n:{LABEL}) RETURN count(n) AS k"),
            "mapped_use_graph_none_props": count(e, f"USE GRAPH '{GN}' MATCH (n:{LABEL}) RETURN n.name AS name ORDER BY name"),
            "control_ordinary_use_graph_none": count(e, f"USE GRAPH '{GN}' MATCH (n:IaOrd0802) RETURN count(n) AS k"),
            "control_ordinary_use_graph_a": count(e, f"USE GRAPH '{GA}' MATCH (n:IaOrd0802) RETURN count(n) AS k"),
        }
        for k, v in res.items():
            C.obs(query=k, **v)
        C.obs(native_answers=e.__dict__.get("_native_answers", 0),
              note="mapped labels are declined by the native planner (_names_mapped_label): SQL path")

        def k(name):
            v = res[name]
            return v.get("rows", [[None]])[0][0] if v.get("rows") else None

        if k("control_ordinary_use_graph_none") != 0 or k("control_ordinary_use_graph_a") != 1:
            verdict = ("incomplete", f"control failed: {res['control_ordinary_use_graph_none']} / {res['control_ordinary_use_graph_a']}")
        elif k("mapped_use_graph_none") == 2 and k("mapped_use_graph_a") == 2:
            verdict = ("pass", "as built = reading (a): the mapped label answers its 2 table rows under USE GRAPH of a "
                               "graph with content and of a graph with no content at all; the ordinary-label control is "
                               "scoped (0 / 1). No contract settles the mapped case.")
        else:
            verdict = ("pass", f"as built scopes or refuses mapped labels: {res}")
    finally:
        try:
            e.remove_table_mapping(LABEL)
        except Exception as ex:  # noqa: BLE001
            C.obs(cleanup_error=f"remove_table_mapping: {ex}")
        try:
            c.sql(f"DROP TABLE {TABLE}")
        except Exception as ex:  # noqa: BLE001
            C.obs(cleanup_error=f"drop table: {ex}")
        C.obs(step="erase", removed=e.erase_graph(GA), mappings_after=e.list_table_mappings())
        c.close()
    C.verdict(*verdict)


if __name__ == "__main__":
    main()
