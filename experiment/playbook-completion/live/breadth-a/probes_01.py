"""Live checks of module 01 (install, schema) findings in AUDITA. See probe_lib for the rules."""
from __future__ import annotations

import sys

from probe_lib import Result, engine, erase, gname, run


def p0103_no_record_marker_accepted(r: Result):
    """F-0103: with the schema record ^IVG.Deploy("schema") absent and the 4.6.0 marker class present, the first-use
    check accepts the namespace. Spec 262 FR-006a (spec.md:245) requires a refusal when the namespace has no schema
    record. The record is saved and restored byte for byte around the check."""
    from iris_vector_graph.schema_name import check_first_access
    c, eng = engine()
    saved = (c.o.get("^IVG.Deploy", "schema"), c.o.get("^IVG.Deploy", "schema", "recorded"))
    r.obs("record_before", [str(x) for x in saved])
    try:
        c.o.kill("^IVG.Deploy", "schema")
        r.obs("record_during", str(c.o.get("^IVG.Deploy", "schema")))
        try:
            check_first_access(c.o, "Graph_KG")
            r.obs("check_first_access", "accepted")
        except Exception as e:
            r.obs("check_first_access", f"refused {type(e).__name__}: {str(e)[:200]}")
    finally:
        if saved[0] is not None:
            c.o.set(saved[0], "^IVG.Deploy", "schema")
        if saved[1] is not None:
            c.o.set(saved[1], "^IVG.Deploy", "schema", "recorded")
        r.obs("record_restored", [str(c.o.get("^IVG.Deploy", "schema")), str(c.o.get("^IVG.Deploy", "schema", "recorded"))])
        c.close()
    r["oracle"] = "FR-006a: an engine refuses a namespace with no schema record (setup exempt)"
    r["reproduced"] = r["observed"]["check_first_access"] == "accepted"
    r["verdict"] = "accepted with no record (marker class present)" if r["reproduced"] else "refused"


def p0106_property_keys_cross_graph(r: Result):
    """F-0106: get_property_keys(label) joins labels to properties by id alone, so a key held only by a same-id node of
    another graph is listed as the label's key. Oracle: CONTEXT.md:38-43 / SYS-I2."""
    c, eng = engine()
    ga, gb = gname("ka"), gname("kb")
    nid, label, key = gname("x"), gname("Lk"), gname("onlyB")
    try:
        eng.create_node(nid, labels=[label], properties={"own": 1}, graph=ga)
        eng.create_node(nid, properties={key: "b"}, graph=gb)
        keys = r.obs("get_property_keys", eng.get_property_keys(label))
        r["oracle"] = "every key listed for label L is held by a node with L in its own graph"
        r["reproduced"] = key in keys
        r["verdict"] = "graph B's key listed under graph A's label" if r["reproduced"] else "scoped"
    finally:
        erase(eng, ga, gb)
        c.close()


def p0107_unqualified_drop_index(r: Result):
    """F-0107 / P-0112 (observation only): which index does the unqualified `DROP INDEX idx_props_key_val` of
    ensure_indexes name? Checks whether the IVG Schema holds an index of that name and which schema an unqualified
    name resolves in for this process (the default schema)."""
    c, eng = engine()
    try:
        r.obs("indexes_named_idx_props_key_val", c.sql(
            "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.INDEXES WHERE INDEX_NAME = 'idx_props_key_val'"))
        try:
            r.obs("default_schema", str(c.o.classMethodValue("%SYSTEM.SQL.Schema", "Default")))
        except Exception as e:
            r.obs("default_schema", f"unavailable: {str(e)[:120]}")
        r["oracle"] = "spec 262 FR-007: IVG's SQL names only fully qualified objects in the IVG Schema"
        r["reproduced"] = None
        r["verdict"] = "observation"
    finally:
        c.close()


PROBES = {f.__name__: f for f in (p0103_no_record_marker_accepted, p0106_property_keys_cross_graph,
                                  p0107_unqualified_drop_index)}

if __name__ == "__main__":
    sys.exit(run("01", PROBES, sys.argv[1:]))
