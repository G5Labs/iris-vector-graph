#!/usr/bin/env python3
# reads3: copy of structural/reads2/ni_base.py (itself a verbatim copy of structural/reads/noninterference.py); not edited
# there. Two changes only: the scratch global is ^IVGAuditDRd3Snap (reads3 scratch prefix) and scratch files go under
# $RUN_DIR/structural/reads3/tmp. The oracle (variant, same, run_case, the self-test) is unchanged.
"""§3.4 declared reads: a non-interference read oracle, with a self-test (structural lane, AUDITD, observation only).

    locks.sh iris timeout 1500 python noninterference.py --modules 03,04 --out FILE
    locks.sh iris timeout 600  python noninterference.py --self-test --out FILE

Oracle A (semantic, independent of any source reading): a query reads only its declared footprint iff its answer does
not depend on state outside that footprint. For each read action: build the base state, run the action (twice: the
answer must be stable); for each perturbation OUTSIDE the declared footprint build base + perturbation and run again.
A changed answer is a read outside the declared footprint. Where cheap, a perturbation INSIDE the footprint must change
the answer (the probe is sensitive). Every variant starts from lib.reset() on a fresh connection and calls the action
on a fresh engine (no client cache carries over; Graph.KG.Eraser.EraseAll kills ^IVG.AlgoCache and ^KG("__version")
only grows, so no server cache answers a variant from another).
Answers are compared canonically (lists sorted recursively, floats rounded to 10 digits); an order-only difference
is recorded separately (storage order, not a read outside).

Oracle B (table level, Python-issued SQL only): iris.dbapi.Cursor.execute/executemany are wrapped in this harness
process (not in the product) and every SQL text the product sends during the call is recorded; the tables named after
FROM/JOIN are compared with the action's declared reads in footprints/NN.json. It cannot see SQL or global reads that
run inside Graph.KG classes (Native API calls) and cannot see which rows a statement read.

Declared footprint per action: the stores of footprints/NN.json (correspondence.json reads for modules 11-14) and the
graph or target the call is scoped to by its signature/docstring (cited in each case's `declared`).
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "live"))
import lib  # noqa: E402

import iris.dbapi  # noqa: E402

G1, G2 = "stg1", "stg2"
T0 = 1_700_000_000
FOOT = lib.ROOT / "footprints"

# ------------------------------------------------------------------------------------------------ oracle B capture
_CAPTURE = {"on": False, "sql": []}
_orig_exec = iris.dbapi.Cursor.execute
_orig_many = iris.dbapi.Cursor.executemany


def _exec(self, operation, *a, **k):
    if _CAPTURE["on"]:
        _CAPTURE["sql"].append(str(operation))
    return _orig_exec(self, operation, *a, **k)


def _many(self, operation, *a, **k):
    if _CAPTURE["on"]:
        _CAPTURE["sql"].append(str(operation))
    return _orig_many(self, operation, *a, **k)


iris.dbapi.Cursor.execute = _exec
iris.dbapi.Cursor.executemany = _many


def hsql(c, q, *params):
    """Harness SQL, not recorded by oracle B."""
    was = _CAPTURE["on"]
    _CAPTURE["on"] = False
    try:
        return c.sql(q, *params)
    finally:
        _CAPTURE["on"] = was
TABLE = re.compile(r"\b(?:FROM|JOIN)\s+((?:[\w%]+|\"[^\"]+\")\.(?:[\w%]+|\"[^\"]+\")|[\w%]+)", re.I)


def tables_of(sqls):
    out = set()
    for s in sqls:
        for m in TABLE.finditer(s):
            t = m.group(1).replace('"', "")
            if "." in t and not t.upper().startswith(("INFORMATION_SCHEMA", "%")):
                out.add(t.split(".")[0] + "." + t.split(".")[1])
            elif "." in t:
                out.add(t)
    return sorted(out)


def declared_tables(module, entry):
    """sql: stores the footprint declares as reads (or writes) of entry ('IRISGraphEngine.<name>')."""
    if not entry:
        return None
    p = FOOT / f"{module}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    eps = d.get("entry_points") or d.get("entries") or []
    for e in eps:
        i = e.get("id") or e.get("entry") or ""
        if i in (f"py:{entry}", entry, f"eng:{entry}"):
            st = []
            for key in ("reads", "writes"):
                v = e.get(key)
                if isinstance(v, dict):
                    st += [("sql:" + t if not t.startswith("sql:") else t) for t in v.get("tables", [])]
                elif isinstance(v, list):
                    st += [x["store"] if isinstance(x, dict) else x for x in v]
            return sorted({s.split(" ")[0][4:] for s in st if s.startswith("sql:")})
    return None


# ------------------------------------------------------------------------------------------------ answers
def canon(x):
    if isinstance(x, float):
        return round(x, 10)
    if isinstance(x, dict):
        return {str(k): canon(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple, set, frozenset)):
        items = [canon(v) for v in x]
        try:
            return sorted(items, key=lambda v: json.dumps(v, sort_keys=True, default=str))
        except Exception:  # noqa: BLE001
            return items
    if hasattr(x, "__dict__") and not isinstance(x, type):
        return canon({k: v for k, v in vars(x).items() if not k.startswith("_")})
    try:
        json.dumps(x)
        return x
    except TypeError:
        return str(x)


def raw(x):
    if isinstance(x, float):
        return round(x, 10)
    if isinstance(x, dict):
        return {str(k): raw(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [raw(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted(str(v) for v in x)
    if hasattr(x, "__dict__") and not isinstance(x, type):
        return raw({k: v for k, v in vars(x).items() if not k.startswith("_")})
    try:
        json.dumps(x)
        return x
    except TypeError:
        return str(x)


VOLATILE_KEYS = {"revision_id", "parent_id", "verified_head", "committed_ms", "adoption_revision", "shape",
                 "committed_at", "elapsed_ms", "duration_ms"}
HEX32 = re.compile(r"^[0-9a-f]{32}$")


def mask(x):
    """Wall-clock and generated-id values replaced by placeholders (they differ between identical runs)."""
    if isinstance(x, dict):
        return {k: ("<volatile>" if k in VOLATILE_KEYS and v is not None else mask(v)) for k, v in x.items()}
    if isinstance(x, list):
        return [mask(v) for v in x]
    if isinstance(x, str) and HEX32.match(x):
        return "<hex32>"
    return x


def file_lines(path):
    p = Path(path)
    return sorted(p.read_text(errors="replace").splitlines()) if p.exists() else None


# ------------------------------------------------------------------------------------------------ data builders
BASE_NODES = {"a": (["L"], {"name": "A", "k": "v1", "j": '{"f":"x"}'}), "b": (["L", "M"], {"k": "v2"}),
              "c": (["M"], {"k": "v1"})}
BASE_EDGES = [("a", "R", "b"), ("b", "R", "c"), ("a", "S", "c")]
NOISE_NODES = {"a": (["N"], {"name": "A2", "k": "v9", "z": "1", "j": '{"f":"y"}'}), "b": (["L"], {"k": "v1"}),
               "c": (["L"], {"k": "v1"}), "d": (["L"], {"k": "v1", "name": "D"})}
NOISE_EDGES = [("a", "R", "c"), ("c", "R", "a"), ("a", "R", "d"), ("d", "R", "b"), ("b", "S", "a")]
KEY_NODES = {"a_x": (["LX"], {"k2": "v1", "kk": "v1"}), "ax": (["Lx"], {"k_": "v1", "name": "AX"})}


def put(e, g, nodes, edges):
    for n, (labels, props) in nodes.items():
        e.create_node(n, labels=list(labels), properties=dict(props), graph=g)
    for s, p, o in edges:
        e.create_edge(s, p, o, graph=g)


def base_in(g):
    return lambda e, c: put(e, g, BASE_NODES, BASE_EDGES)


def other_graphs(g):
    """The same ids (and one more) in every graph but g, with other labels/props/edges."""
    others = [x for x in (None, G1, G2) if x != g]
    return lambda e, c: [put(e, x, NOISE_NODES, NOISE_EDGES) for x in others]


def key_noise(g):
    return lambda e, c: put(e, g, KEY_NODES, [("ax", "T", "a_x")])


def inside_nodes(g):
    return lambda e, c: (e.store_node("a", properties={"name": "A", "k": "v7", "extra": "1"}, labels=["L", "Q"], graph=g),
                         e.create_node("e", labels=["L"], properties={"k": "v1"}, graph=g), e.create_edge("e", "R", "a", graph=g))


def temporal_base(g):
    def f(e, c):
        for n in ("a", "b", "c"):
            e.create_node(n, graph=g)
        e.create_edge_temporal("a", "T", "b", timestamp=T0 + 10, attrs={"w": "1"}, graph=g)
        e.create_edge_temporal("a", "T", "c", timestamp=T0 + 20, graph=g)
        e.create_edge_temporal("b", "T", "c", timestamp=T0 + 15, graph=g)
        e.create_edge_temporal("a", "U", "b", timestamp=T0 + 12, attrs={"w": "2"}, graph=g)
    return f


def temporal_other_graphs(g):
    def f(e, c):
        for x in [y for y in (None, G1, G2) if y != g]:
            for n in ("a", "b", "c", "d"):
                e.create_node(n, graph=x)
            e.create_edge_temporal("a", "T", "d", timestamp=T0 + 11, attrs={"w": "9"}, graph=x)
            e.create_edge_temporal("a", "T", "b", timestamp=T0 + 10, attrs={"w": "8"}, graph=x)
            e.create_edge_temporal("d", "T", "c", timestamp=T0 + 14, graph=x)
            e.create_edge_temporal("a", "U", "b", timestamp=T0 + 12, attrs={"w": "7"}, graph=x)
    return f


def temporal_other_source_other_predicate(g):
    def f(e, c):
        e.create_node("d", graph=g)
        for i in range(3):
            e.create_edge_temporal("d", "V", "a", timestamp=T0 + 13 + i, graph=g)
    return f


def temporal_same_source_other_predicate(g):
    return lambda e, c: e.create_edge_temporal("a", "V", "c", timestamp=T0 + 16, graph=g)


def temporal_inside(g):
    def f(e, c):
        e.create_node("e", graph=g)
        e.create_edge_temporal("a", "T", "e", timestamp=T0 + 18, graph=g)
        e.create_edge_temporal("e", "T", "a", timestamp=T0 + 19, graph=g)
        e.create_edge_temporal("a", "U", "b", timestamp=T0 + 12, attrs={"w": "5"}, graph=g, upsert=True)
    return f


def algo_base(e, c):
    put(e, None, BASE_NODES, BASE_EDGES + [("c", "R", "a")])


# ------------------------------------------------------------------------------------------------ ledger helpers
def ledger_tenant(prefix, actor, corr, key=None, source=None):
    from iris_vector_graph.ledger import Changeset

    def f(e, c):
        ch = Changeset(actor=actor, actor_type="ingest", message=f"tenant {prefix}", correlation_id=corr,
                       idempotency_key=key, source=source)
        ch.create_node(f"{prefix}|a", labels=["L"], properties={"k": "v1"})
        ch.create_node(f"{prefix}|b", properties={"k": "v2"})
        ch.create_relationship(f"{prefix}|a", "R", f"{prefix}|b")
        return e.ledger.commit(ch)
    return f


def ledger_base(e, c):
    e.ledger.enable()
    c.conn.commit()
    ledger_tenant("t1", "alice", "corrA", key="kA", source={"sys": "s1"})(e, c)


def ledger_noise_tenant(e, c):
    ledger_tenant("t2", "bob", "corrB", key="kB", source={"sys": "s2"})(e, c)
    ledger_tenant("t3", "carol", "corrA-x", key="kA-x", source={"sys": "s1x"})(e, c)


def ledger_noise_bypass_other_graph(e, c):
    """The tenant's ids written directly (not through the ledger) in a named graph."""
    put(e, G2, {"t1|a": (["N"], {"k": "v9"}), "t1|b": ([], {"k": "v8"})}, [("t1|a", "R", "t1|b")])


def ledger_inside(e, c):
    from iris_vector_graph.ledger import Changeset
    ch = Changeset(actor="alice", actor_type="ingest", message="tenant t1 more", correlation_id="corrA")
    ch.set_property("t1|a", "k", "v5")
    e.ledger.commit(ch)


def strip_rev(x):
    """Revision answers without wall-clock fields."""
    if isinstance(x, dict):
        return {k: strip_rev(v) for k, v in x.items() if k not in ("committed_ms", "committed_at", "ts", "timestamp",
                                                                  "elapsed_ms", "duration_ms")}
    if isinstance(x, list):
        return [strip_rev(v) for v in x]
    return x


def rev_answer(r):
    return strip_rev(raw(r))


def first_rev(e):
    page = e.ledger.history(actor="alice", limit=10)
    revs = getattr(page, "revisions", None) or getattr(page, "items", None) or list(page)
    return revs[0]


def rev_id(r):
    return getattr(r, "revision_id", None) or getattr(r, "id", None) or r["revision_id"]


def erase_then_redact_base(e, c):
    ledger_base(e, c)
    c.conn.commit()
    e.delete_nodes_by_prefix("t1|")


def receipt(r):
    """The receipt; the audit revision's own seq is head + 1 (the ledger head is a declared read of Final,
    correspondence.json redact-final), so it is masked."""
    d = raw(r)
    if isinstance(d, dict) and isinstance(d.get("redaction"), dict) and "seq" in d["redaction"]:
        d["redaction"]["seq"] = "<head+1>"
    return d


def redact_inside(e, c):
    from iris_vector_graph.ledger import Changeset
    ch = Changeset(actor="alice", actor_type="ingest", message="tenant t1 more", correlation_id="corrA")
    ch.create_node("t1|c", properties={"k": "v3"})
    e.ledger.commit(ch)
    c.conn.commit()
    e.delete_nodes_by_prefix("t1|")


# ------------------------------------------------------------------------------------------------ the cases
def E(name, *a, **k):
    return lambda e, c: getattr(e, name)(*a, **k)


def tmpfile(suffix):
    d = lib.OUT / "reads3" / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return str(d / f"out-{time.time_ns()}{suffix}")


def export_file(fn, suffix):
    def f(e, c):
        p = tmpfile(suffix)
        r = fn(e, p)
        lines = file_lines(p)
        Path(p).unlink(missing_ok=True)
        return {"lines": lines, "result_keys": sorted(raw(r).keys()) if isinstance(raw(r), dict) else None}
    return f


def _drop_ts(x):
    if isinstance(x, dict):
        return {k: _drop_ts(v) for k, v in x.items() if k not in ("created_at", "updated_at")}
    if isinstance(x, list):
        return [_drop_ts(v) for v in x]
    return x


def snapshot_answer(e, c):
    p = tmpfile(".zip")
    e.save_snapshot(p)
    out = {}
    with zipfile.ZipFile(p) as z:
        for n in sorted(z.namelist()):
            if n.endswith("metadata.json"):
                continue
            data = z.read(n)
            if n.endswith(".ndjson"):
                # row timestamps (nodes.created_at DEFAULT CURRENT_TIMESTAMP, schema.py:398) differ between identical
                # runs a second apart: masked before hashing
                lines = []
                for ln in data.decode("utf-8", "replace").splitlines():
                    try:
                        lines.append(json.dumps(mask(_drop_ts(json.loads(ln))), sort_keys=True))
                    except ValueError:
                        lines.append(ln)
                data = "\n".join(sorted(lines)).encode()
            out[n] = hashlib.sha256(data).hexdigest()[:16]
    Path(p).unlink(missing_ok=True)
    return out


def scratch_global(e, c):
    c.o.set("x", "^IVGAuditDRd3Snap", "k")
    c.o.set("y", "^IVGAuditDRd3Snap", "k2", 1)


def drop_scratch(c):
    c.o.kill("^IVGAuditDRd3Snap")


def reif_base(e, c):
    put(e, None, BASE_NODES, BASE_EDGES)
    eid = c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s='a' AND p='R' AND o_id='b' AND COALESCE(graph_id,'')=''")[0][0]
    e.reify_edge(int(eid), reifier_id="rf1", props={"p": "1"})


def reif_call(e, c):
    eid = hsql(c, "SELECT edge_id FROM Graph_KG.rdf_edges WHERE s='a' AND p='R' AND o_id='b' AND COALESCE(graph_id,'')=''")[0][0]
    return e.get_reifications(int(eid))


def reif_noise(e, c):
    put(e, G2, {"rf1": (["Reification"], {"p": "2", "q": "x"}), "a": ([], {}), "b": ([], {})}, [("a", "R", "b")])
    eid = c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s='b' AND p='R' AND o_id='c' AND COALESCE(graph_id,'')=''")[0][0]
    e.reify_edge(int(eid), reifier_id="rf2", props={"p": "3"})


def anchors_base(e, c):
    e.create_node("mesh:a", labels=["MeSH"], properties={"name": "A"})
    e.fhir_bridge_add("I10", "mesh:a")
    e.fhir_bridge_add("I11", "mesh:x")


def anchors_noise(e, c):
    e.create_node("mesh:x", labels=["MeSH"], properties={"name": "X"}, graph=G2)


def vec(x):
    return [float(v) for v in x]


def vec_base(g):
    def f(e, c):
        put(e, g, BASE_NODES, [])
        e.store_embedding("a", vec([1, 0, 0, 0]), graph=g)
        e.store_embedding("b", vec([0.9, 0.1, 0, 0]), graph=g)
        e.store_embedding("c", vec([0, 1, 0, 0]), graph=g)
    return f


def vec_noise(g):
    def f(e, c):
        for x in [y for y in (None, G1, G2) if y != g]:
            put(e, x, NOISE_NODES, [])
            e.store_embedding("a", vec([0, 0, 1, 0]), graph=x)
            e.store_embedding("d", vec([1, 0.01, 0, 0]), graph=x)
    return f


SHAPES = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <urn:ivg:> .
ex:S a sh:NodeShape ; sh:targetClass ex:L ; sh:property [ sh:path ex:k ; sh:minCount 1 ] ."""


def C(module, cid, call, base, declared, outside, inside=None, entry=None, note="", inside_declared=None, project=False):
    return {"module": module, "id": cid, "call": call, "base": base, "declared": declared, "outside": outside,
            "inside": inside, "entry": entry, "note": note, "inside_declared": inside_declared, "project": project}


def cases():
    L = []
    # ---- 01 (property keys of a label; F-0106)
    L.append(C("01", "get_property_keys(label=L) [not graph-scoped: keys of nodes with label L]",
               E("get_property_keys", label="L"), base_in(G1),
               "keys of the nodes that carry label L, in any graph (schema.py:500-512 'Not graph-scoped'); a key of a node row without L is outside",
               {"same ids without L in other graphs": lambda e, c: put(e, G2, {"a": (["N"], {"z": "1"})}, []),
                "other labels same graph": key_noise(G1)},
               inside=inside_nodes(G1), entry="IRISGraphEngine.get_property_keys"))
    # ---- 02
    L.append(C("02", "is_multigraph(G1)", E("is_multigraph", G1), lambda e, c: e.create_node("a", graph=G1),
               "^IVG.GraphMode(G1) (GraphMode.cls)", {"other graph's mode on": lambda e, c: e.set_multigraph(G2, True),
                                                     "default graph's mode on": lambda e, c: e.set_multigraph(None, True)},
               inside=lambda e, c: e.set_multigraph(G1, True), entry="IRISGraphEngine.is_multigraph"))
    # ---- 03 graph-scoped readers
    for g, gname in ((G1, "G1"), (None, "default")):
        L.append(C("03", f"get_node(a, graph={gname})", E("get_node", "a", graph=g), base_in(g),
                   f"rows of node a in graph {gname} (nodes_edges.py:563-619)",
                   {"same ids in other graphs": other_graphs(g), "other ids same graph": key_noise(g)},
                   inside=inside_nodes(g), entry="IRISGraphEngine.get_node"))
        L.append(C("03", f"count_nodes(graph={gname})", E("count_nodes", graph=g), base_in(g),
                   f"nodes of graph {gname} (nodes_edges.py:733-758)", {"same ids in other graphs": other_graphs(g)},
                   inside=inside_nodes(g), entry="IRISGraphEngine.count_nodes"))
        L.append(C("03", f"count_nodes(label=L, graph={gname})", E("count_nodes", label="L", graph=g), base_in(g),
                   f"nodes of graph {gname} with label L", {"same ids in other graphs": other_graphs(g),
                                                           "other labels same graph": key_noise(g)},
                   inside=inside_nodes(g), entry="IRISGraphEngine.count_nodes"))
        L.append(C("03", f"node_count(graph={gname})", E("node_count", graph=g), base_in(g),
                   f"nodes of graph {gname} (nodes_edges.py:2362-2373)", {"same ids in other graphs": other_graphs(g)},
                   inside=inside_nodes(g), entry="IRISGraphEngine.node_count"))
        L.append(C("03", f"edge_count(graph={gname})", E("edge_count", graph=g), base_in(g),
                   f"edges of graph {gname} (nodes_edges.py:2374-2392)", {"same ids in other graphs": other_graphs(g)},
                   inside=inside_nodes(g), entry="IRISGraphEngine.edge_count"))
    L.append(C("03", "get_nodes([a,b,c], graph=G1)", E("get_nodes", ["a", "b", "c"], graph=G1), base_in(G1),
               "rows of a, b, c in G1 (nodes_edges.py:621-731: 'Every statement below is scoped to it')",
               {"same ids in other graphs": other_graphs(G1), "other ids same graph": key_noise(G1)},
               inside=inside_nodes(G1), entry="IRISGraphEngine.get_nodes"))
    for name, args in (("get_nodes_by_ids", (["a", "b"],)), ("get_node_name", ("a",)), ("get_node_properties", ("a",))):
        ins = inside_nodes(None) if name != "get_node_name" else (lambda e, c: e.store_node("a", properties={"name": "A9"}))
        L.append(C("03", f"{name}{args} [default graph]", E(name, *args), base_in(None),
                   f"default-graph rows (nodes_edges.py:2341-2361 'the default-graph node')",
                   {"same ids in other graphs": other_graphs(None), "other ids same graph": key_noise(None)},
                   inside=ins, entry=f"IRISGraphEngine.{name}"))
    L.append(C("03", "get_label_distribution(graph=G1)", E("get_label_distribution", graph=G1), base_in(G1),
               "labels of G1 (schema.py:487-497)", {"same ids in other graphs": other_graphs(G1)},
               inside=inside_nodes(G1), entry="IRISGraphEngine.get_label_distribution"))
    # all-graphs readers: graph noise is inside; key noise is outside
    allg = [("get_node_ids_by_label", ("L",), "rdf_labels rows with label L, all graphs (nodes_edges.py:760-777)"),
            ("nodes_exist", (["a", "zz"],), "nodes rows of the given ids, any graph (nodes_edges.py:2590)"),
            ("get_property_pairs", ("k",), "rdf_props rows with key k, all graphs (nodes_edges.py:846)"),
            ("get_node_ids_by_property", ("k", "v1"), "rdf_props rows key=k val=v1 (nodes_edges.py:801)"),
            ("get_property_values", ("k",), "rdf_props rows with key k (nodes_edges.py:862)"),
            ("count_subjects_with_property", ("k", "v1"), "rdf_props rows key=k val=v1 (nodes_edges.py:946)"),
            ("get_node_ids_like", ("a%",), "nodes rows whose id is LIKE 'a%' (nodes_edges.py:932)"),
            ("get_json_field_values", ("j", "f"), "rdf_props rows with key j (nodes_edges.py:916)"),
            ("property_value_exists", ("k", "v2%"), "rdf_props rows key=k val LIKE v2% (nodes_edges.py:879)"),
            ("get_property_pairs_like", ("k", "v1%"), "rdf_props rows key=k val LIKE v1% (nodes_edges.py:892)"),
            ("get_nodes_by_property", ("k", "v1"), "rdf_props rows key=k val=v1, hydrated (nodes_edges.py:833)")]
    special_in = {"nodes_exist": lambda e, c: e.create_node("zz", graph=G1),
                  "count_subjects_with_property": lambda e, c: e.create_node("e2", properties={"k": "v1"}, graph=G1),
                  "get_node_ids_like": lambda e, c: e.create_node("ab", graph=G1),
                  "get_json_field_values": lambda e, c: e.create_node("e3", properties={"j": '{"f":"w"}'}, graph=G1),
                  "property_value_exists": lambda e, c: e.store_node("b", properties={"k": "v9"}, graph=G1)}
    for name, args, decl in allg:
        L.append(C("03", f"{name}{args} [all graphs]", E(name, *args), base_in(G1), decl,
                   {"other keys/labels/ids": key_noise(G1)} if name != "get_node_ids_like" else
                   {"ids not matching the pattern": lambda e, c: put(e, G1, {"ba": (["L"], {"k": "v1"}), "x_a": ([], {})}, [])},
                   inside=special_in.get(name, inside_nodes(G1)), entry=f"IRISGraphEngine.{name}"))
    # writers whose outcome depends on what they read (footprint role 'both'): the outcome must depend on G1 only
    def g1_counts(c):
        return {t: hsql(c, f"SELECT COUNT(*) FROM Graph_KG.{t} WHERE COALESCE(graph_id,'') = ?", G1)[0][0]
                for t in ("nodes", "rdf_edges", "rdf_labels", "rdf_props")}
    L.append(C("03", "create_node(a, graph=G1): outcome and G1 rows", lambda e, c: {"r": e.create_node("a", labels=["L"], properties={"k": "v1"}, graph=G1), "g1": g1_counts(c)},
               lambda e, c: None, "the existence probe of a in G1 (nodes_edges.py create_node; footprints/03.json create_node)",
               {"a in other graphs": other_graphs(G1)}, inside=lambda e, c: e.create_node("a", graph=G1), entry="IRISGraphEngine.create_node"))
    L.append(C("03", "create_edge(a,R,b, graph=G1): outcome and G1 rows", lambda e, c: {"r": e.create_edge("a", "R", "b", graph=G1), "g1": g1_counts(c)},
               lambda e, c: [e.create_node(n, graph=G1) for n in ("a", "b")], "G1's edge a-R-b and its endpoints in G1 (create_edge; footprints/03.json)",
               {"the same edge in other graphs": lambda e, c: [put(e, x, {"a": ([], {}), "b": ([], {})}, [("a", "R", "b")]) for x in (None, G2)]},
               inside=lambda e, c: e.create_edge("a", "R", "b", graph=G1), entry="IRISGraphEngine.create_edge"))
    L.append(C("05", "create_edge_temporal(a,T,b,ts, graph=G1): outcome and G1 window", lambda e, c: {"r": e.create_edge_temporal("a", "T", "b", timestamp=T0 + 10, graph=G1),
                                                                                                   "w": raw(e.get_edges_in_window("a", "T", T0, T0 + 100, graph=G1))},
               lambda e, c: [e.create_node(n, graph=G1) for n in ("a", "b")], "G1's temporal entries of (a,T,b,ts) (temporal.py create_edge_temporal)",
               {"the same temporal edge in other graphs": temporal_other_graphs(G1)},
               inside=lambda e, c: e.create_edge_temporal("a", "T", "b", timestamp=T0 + 11, graph=G1),
               entry="IRISGraphEngine.create_edge_temporal"))
    L.append(C("03", "list_graphs() [graphs holding edges]", E("list_graphs"), base_in(G1),
               "rdf_edges graph ids (footprints/03.json list_graphs reads sql:Graph_KG.rdf_edges)",
               {"a graph with nodes and no edges": lambda e, c: e.create_node("q", graph=G2)},
               inside=lambda e, c: put(e, G2, {"q": ([], {}), "r": ([], {})}, [("q", "R", "r")]), entry="IRISGraphEngine.list_graphs"))
    L.append(C("03", "get_nodes_by_label(L) [ids every graph, hydrated from the default graph]",
               E("get_nodes_by_label", "L"), base_in(None),
               "ids from rdf_labels of every graph, rows hydrated from the default graph (nodes_edges.py:779 docstring)",
               {"other labels any graph": lambda e, c: put(e, G2, {"q": (["LL"], {"k": "v1"})}, [])},
               inside=inside_nodes(None), entry="IRISGraphEngine.get_nodes_by_label"))
    # ---- 04
    for g, gname in ((G1, "G1"), (None, "default")):
        L.append(C("04", f"verify_graph(graph={gname})", E("verify_graph", graph=g), base_in(g),
                   f"one graph's ^KG adjacency and rdf_edges rows (admin.py:850)",
                   {"same ids in other graphs": other_graphs(g)},
                   inside=lambda e, c, g=g: e.create_edge("c", "S", "a", graph=g), entry="IRISGraphEngine.verify_graph"))
    L.append(C("04", "Edgeless.LonersJson(Graph_KG, G1)",
               lambda e, c: json.loads(str(c.call("Graph.KG.Edgeless", "LonersJson", "Graph_KG", G1, "", 1000))),
               lambda e, c: (base_in(G1)(e, c), e.create_node("z", graph=G1)),
               "G1 nodes rows and ^KG(out/in, G1) (Edgeless.cls:15-120)",
               {"same ids in other graphs": other_graphs(G1),
                "z with edges in other graphs": lambda e, c: [put(e, x, {"z": ([], {}), "y": ([], {})}, [("z", "R", "y")]) for x in (None, G2)]},
               inside=lambda e, c: e.create_edge("z", "R", "a", graph=G1)))
    L.append(C("04", "Adj.Degree(G1, a)", lambda e, c: int(c.call("Graph.KG.Adj", "Degree", G1, "a", "")), base_in(G1),
               "^KG(out, G1, a) (Adj.cls:52-89)", {"same ids in other graphs": other_graphs(G1)},
               inside=lambda e, c: e.create_edge("a", "R", "a", graph=G1)))
    # ---- 05
    TG = G1
    t_out = {"same ids/predicate in other graphs": temporal_other_graphs(TG),
             "another source's edges of another predicate, same graph": temporal_other_source_other_predicate(TG),
             "a's edge of another predicate, same graph": temporal_same_source_other_predicate(TG)}
    t_out_src = {k: v for k, v in t_out.items() if not k.startswith("a's")}
    t_in_src = {"a's edge of another predicate, same graph (velocity counts every predicate, temporal.py:860)": temporal_same_source_other_predicate(TG)}
    tcalls = [("get_edges_in_window", ("a", "T", T0, T0 + 100), "temporal.py:478"),
              ("get_edges_in_window", ("", "T", T0, T0 + 100), "temporal.py:478"),
              ("get_window_sources", ("T", T0, T0 + 100), "temporal.py:1049"),
              ("get_distinct_count", ("a", "T", T0, T0 + 100), "temporal.py:1088"),
              ("get_bucket_groups", ("T", T0, T0 + 100), "temporal.py:961"),
              ("get_bucket_group_targets", ("a", "T", T0, T0 + 100), "temporal.py"),
              ("get_edge_attrs", (T0 + 12, "a", "U", "b"), "temporal.py:911")]
    for name, args, cite in tcalls:
        L.append(C("05", f"{name}{args[:2]} graph=G1", E(name, *args, graph=TG), temporal_base(TG),
                   f"graph G1's temporal index entries for the given source/predicate/window ({cite})", t_out,
                   inside=temporal_inside(TG), entry=f"IRISGraphEngine.{name}"))
    L.append(C("05", "get_temporal_structural('T',) graph=G1", E("get_temporal_structural", "T", graph=TG), temporal_base(TG),
               "^IVG.TemporalStructural(G1, T)", {"other graph's setting": lambda e, c: e.set_temporal_structural("T", False, graph=G2),
                                                   "default graph's setting": lambda e, c: e.set_temporal_structural("T", False, graph=None)},
               inside=lambda e, c: e.set_temporal_structural("T", False, graph=TG), entry="IRISGraphEngine.get_temporal_structural"))
    L.append(C("05", "get_edge_velocity(a, window, now) graph=G1",
               E("get_edge_velocity", "a", window_seconds=1000, now_ts=T0 + 50, graph=TG), temporal_base(TG),
               "^KG(bucket, G1, a): edges a is the source of, every predicate, in the window (temporal.py:852-863)", t_out_src,
               inside=temporal_inside(TG), inside_declared=t_in_src, entry="IRISGraphEngine.get_edge_velocity"))
    L.append(C("05", "find_burst_nodes(T, window, threshold=1, now) graph=G1",
               E("find_burst_nodes", "T", window_seconds=1000, threshold=1, now_ts=T0 + 50, graph=TG), temporal_base(TG),
               "^KG(bucket, G1, *) for predicate T: Args 'predicate: Filter to edges with this predicate' (temporal.py:898); the docstring body says it filters nothing (F-0508)",
               t_out, inside=temporal_inside(TG), entry="IRISGraphEngine.find_burst_nodes"))
    L.append(C("05", "export_temporal_edges_ndjson(graph=G1)",
               export_file(lambda e, p: e.export_temporal_edges_ndjson(p, graph=TG), ".ndjson"), temporal_base(TG),
               "G1's ^KG(tout) and edgeprop, every predicate", {"same ids/predicate in other graphs": temporal_other_graphs(TG)},
               inside=temporal_inside(TG), inside_declared={"other predicates same graph": temporal_other_source_other_predicate(TG)},
               entry="IRISGraphEngine.export_temporal_edges_ndjson"))
    L.append(C("05", "export_temporal_edges_ndjson(predicate=T, graph=G1)",
               export_file(lambda e, p: e.export_temporal_edges_ndjson(p, predicate="T", graph=TG), ".ndjson"), temporal_base(TG),
               "G1's ^KG(tout) and edgeprop for predicate T", t_out, inside=temporal_inside(TG),
               entry="IRISGraphEngine.export_temporal_edges_ndjson"))
    # ---- 06
    L.append(C("06", "kg_KNN_VEC(q, k=3, graph=G1)", E("kg_KNN_VEC", "[1,0,0,0]", k=3, graph=G1), vec_base(G1),
               "G1's route of the embedding registry (vector.py:504 'Nearest neighbours inside one graph')",
               {"same ids and a closer vector in other graphs": vec_noise(G1)},
               inside=lambda e, c: (e.create_node("e", graph=G1), e.store_embedding("e", vec([1, 0, 0, 0.001]), graph=G1)),
               entry="IRISGraphEngine.kg_KNN_VEC"))
    # ---- 10 (default graph unless a graph argument)
    a_out = {"same ids and edges in a named graph": other_graphs(None)}
    a_in = lambda e, c: (e.create_node("e", graph=None), e.create_edge("a", "R", "e"), e.create_edge("e", "R", "c"))
    acalls = [("kg_PAGERANK", (), {}), ("ppr", ("a",), {}), ("khop", ("a",), {"hops": 2}), ("kg_WCC", (), {}),
              ("kg_CDLP", (), {}), ("kg_SUBGRAPH", (["a"],), {"k_hops": 1}), ("triangle_count", (), {}),
              ("kg_GRAPH_WALK", ("a",), {"max_depth": 2}),
              ("kg_PERSONALIZED_PAGERANK", (["a"],), {}), ("k_core", (), {}), ("strongly_connected_components", (), {}),
              ("closeness_centrality", (), {}), ("eigenvector_centrality", (), {}), ("betweenness_centrality", (), {}),
              ("leiden_communities", (), {"random_seed": 1}), ("degree_centrality", (), {})]
    for name, args, kw in acalls:
        L.append(C("10", f"{name}{args} [default graph]", E(name, *args, **kw), algo_base,
                   "the default graph's ^KG adjacency / nodes (algorithms.py docstrings: default graph)", a_out,
                   inside=a_in, entry=f"IRISGraphEngine.{name}"))
    L.append(C("10", "kg_NEIGHBORS([a]) [every graph, ALG-B9.10]", E("kg_NEIGHBORS", ["a"]), algo_base,
               "one hop from a through a Cypher query over every graph (10-algorithms.md:157 ALG-B9.10; algorithms.py:986-1023)",
               {"other sources' edges": lambda e, c: put(e, None, {"x": ([], {}), "y": ([], {})}, [("x", "R", "y"), ("b", "S", "x")])},
               inside=a_in, inside_declared={"same ids and edges in a named graph": other_graphs(None)}, entry="IRISGraphEngine.kg_NEIGHBORS"))
    L.append(C("10", "random_walk(a) [default graph]: nodes visited",
               lambda e, c: (lambda ws: {"walks_nonempty": any(ws), "outside_nodes": sorted({n for w in ws for n in (w if isinstance(w, list) else [w])} - {"a", "b", "c"})})(e.random_walk("a", length=6, num_walks=20)),
               algo_base, "the default graph's ^KG (algorithms.py:658); answer = visited nodes outside {a,b,c} (none in the default graph)",
               a_out, entry="IRISGraphEngine.random_walk"))
    L.append(C("10", "degree_centrality(graph=G1)", E("degree_centrality", graph=G1), base_in(G1),
               "G1's adjacency (algorithms.py:1051 'The one graph to count')", {"same ids in other graphs": other_graphs(G1)},
               inside=lambda e, c: e.create_edge("c", "S", "a", graph=G1), entry="IRISGraphEngine.degree_centrality"))
    L.append(C("10", "kg_PERSONALIZED_PAGERANK([a], graph=G1)", E("kg_PERSONALIZED_PAGERANK", ["a"], graph=G1), base_in(G1),
               "G1's adjacency", {"same ids in other graphs": other_graphs(G1)},
               inside=lambda e, c: e.create_edge("b", "S", "a", graph=G1), entry="IRISGraphEngine.kg_PERSONALIZED_PAGERANK"))
    # ---- 11 ledger core readers
    L.append(C("11", "ledger.history(actor=alice)", lambda e, c: rev_answer(e.ledger.history(actor="alice")), ledger_base,
               "ledger_revisions rows with actor=alice (replay.py:299-345, SQL pushed filters)",
               {"other tenants' commits": ledger_noise_tenant, "tenant ids written directly in a named graph": ledger_noise_bypass_other_graph},
               inside=ledger_inside, entry="IRISGraphEngine.ledger.history"))
    L.append(C("11", "ledger.history(correlation_id=corrA)", lambda e, c: rev_answer(e.ledger.history(correlation_id="corrA")),
               ledger_base, "ledger_revisions rows with correlation_id=corrA",
               {"other tenants' commits": ledger_noise_tenant}, inside=ledger_inside))
    L.append(C("11", "ledger.history(source='{\"sys\":\"s1\"}') [stored JSON text, F-1113]", lambda e, c: rev_answer(e.ledger.history(source='{"sys":"s1"}')),
               ledger_base, "ledger_revisions rows with that source (client.py:585-631)",
               {"other tenants' commits": ledger_noise_tenant},
               inside=lambda e, c: ledger_tenant("t4", "dave", "corrD", key="kD", source={"sys": "s1"})(e, c)))
    L.append(C("11", "ledger.commit replay of idempotency key kA",
               lambda e, c: rev_answer(ledger_tenant("t1", "alice", "corrA", key="kA", source={"sys": "s1"})(e, c)),
               ledger_base, "^IVG.Ledger(idem, kA) and its revision (correspondence.json replay reads)",
               {"other tenants' commits": ledger_noise_tenant}))
    # ---- 12 erasure (answer = count and what is left of the target graph)
    def left(g, ids):
        return lambda c: sorted(r[0] for r in hsql(c, "SELECT node_id FROM Graph_KG.nodes WHERE COALESCE(graph_id,'') = ?", g or "") if r[0] in ids)
    L.append(C("12", "erase_graph(G1): count and G1 left", lambda e, c: {"n": e.erase_graph(G1), "left": left(G1, set(BASE_NODES) | {"e"})(c)},
               base_in(G1), "graph G1's rows and derived stores (Eraser.cls EraseGraph; correspondence.json erase-graph reads)",
               {"same ids in other graphs": other_graphs(G1)}, inside=inside_nodes(G1), entry="IRISGraphEngine.erase_graph"))
    pre_base = lambda e, c: put(e, G1, {"t1|a": (["L"], {"k": "1"}), "t1|b": ([], {}), "u|c": ([], {})}, [("t1|a", "R", "t1|b"), ("u|c", "R", "t1|a")])
    L.append(C("12", "delete_nodes_by_prefix(t1|, graph=G1): count and G1 left",
               lambda e, c: {"n": e.delete_nodes_by_prefix("t1|", graph=G1), "left": left(G1, {"t1|a", "t1|b", "u|c", "t1|c"})(c)}, pre_base,
               "G1's nodes with prefix t1| and their edges (Eraser.cls EraseNodes)",
               {"same prefix in other graphs": lambda e, c: [put(e, x, {"t1|a": ([], {}), "t1|z": ([], {})}, [("t1|a", "R", "t1|z")]) for x in (None, G2)],
                "prefix-like ids same graph": lambda e, c: put(e, G1, {"t1x": ([], {}), "t1": ([], {})}, [])},
               inside=lambda e, c: put(e, G1, {"t1|c": ([], {})}, []), entry="IRISGraphEngine.delete_nodes_by_prefix"))
    # ---- 13 redaction receipt
    L.append(C("13", "ledger.redact(prefix=t1) receipt counts", lambda e, c: receipt(e.ledger.redact(prefix="t1")),
               erase_then_redact_base, "target (default graph, prefix t1): its records and statements (LedgerRedact.cls; correspondence.json redact-* reads)",
               {"other tenants' history": ledger_noise_tenant,
                "another tenant's ids live in a named graph (direct write)": lambda e, c: put(e, G2, {"t2|a": (["N"], {"k": "v9"})}, [])},
               inside=redact_inside,
               inside_declared={"tenant ids live in a named graph (LedgerRedact.cls:143-148: a default-graph prefix target counts node rows in every graph)": ledger_noise_bypass_other_graph},
               entry="IRISGraphEngine.ledger.redact"))
    # ---- 14 replay readers
    L.append(C("14", "ledger.get_revision(alice's revision)", lambda e, c: rev_answer(e.ledger.get_revision(rev_id(first_rev(e)))),
               ledger_base, "^IVG.Ledger(rec, seq) of that revision and its ledger_revisions row (client.py:695-704)",
               {"other tenants' commits": ledger_noise_tenant, "tenant ids written directly in a named graph": ledger_noise_bypass_other_graph}))
    L.append(C("14", "ledger.reconstruct(alice's revision)",
               lambda e, c: canon(raw(e.ledger.reconstruct(rev_id(first_rev(e))).as_comparable())), ledger_base,
               "records of seq 1..that revision (client.py:720-728)",
               {"later commits of other tenants": ledger_noise_tenant, "tenant ids written directly in a named graph": ledger_noise_bypass_other_graph}))
    L.append(C("14", "ledger.verify() result", lambda e, c: strip_rev(raw(e.ledger.verify())), lambda e, c: (put(e, None, {}, []), ledger_base(e, c)),
               "ledger records and the content tables, graph-blind (correspondence.json verify reads)",
               {"vectors and a BM25 index (stores verify does not declare)": lambda e, c: (
                   e.store_embedding("t1|a", vec([1, 0, 0, 0])), e.bm25_build("rdidx", ["k"]))},
               inside=lambda e, c: e.create_node("zz-unlogged")))
    # ---- 15
    L.append(C("15", "get_reifications(edge a-R-b)", reif_call, reif_base,
               "rdf_reifications rows of that edge and the reifier's rdf_props (schema.py:3335; footprints/15.json)",
               {"reifier id in another graph and another edge's reification": reif_noise},
               inside=lambda e, c: e.reify_edge(int(c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s='a' AND p='R' AND o_id='b' AND COALESCE(graph_id,'')=''")[0][0]), reifier_id="rf3", props={"p": "4"}),
               entry="IRISGraphEngine.get_reifications"))
    L.append(C("15", "get_kg_anchors([I10, I11])", E("get_kg_anchors", ["I10", "I11"]), anchors_base,
               "fhir_bridges rows of the codes and the existing default-graph nodes they map to (fhir.py:444)",
               {"mapped id exists only in a named graph": anchors_noise},
               inside=lambda e, c: e.create_node("mesh:x"), entry="IRISGraphEngine.get_kg_anchors"))
    L.append(C("15", "export_rdf(graph_id=G1)", export_file(lambda e, p: e.export_rdf(p, format="nt", graph_id=G1), ".nt"),
               base_in(G1), "G1's labels, props and edges (rdf_export.py:96 'any other value that named graph')",
               {"same ids in other graphs": other_graphs(G1)}, inside=inside_nodes(G1), entry="IRISGraphEngine.export_rdf"))
    L.append(C("15", "prov_export() [default graph temporal]",
               export_file(lambda e, p: e.prov_export(p, format="nt", ts_start=T0, ts_end=T0 + 100), ".nt"), temporal_base(None),
               "the default graph's temporal edges in the window (prov.py:107)", {"same temporal edges in other graphs": temporal_other_graphs(None)},
               inside=temporal_inside(None), entry="IRISGraphEngine.prov_export"))
    L.append(C("15", "validate_shacl(shapes, node_ids=[a,b])", lambda e, c: raw(e.validate_shacl(SHAPES, node_ids=["a", "b"])),
               base_in(G1), "labels/props/edges of a and b (shacl.py:203)", {"other ids": key_noise(G1)},
               entry="IRISGraphEngine.validate_shacl"))
    # ---- 18
    L.append(C("18", "save_snapshot(path): archive members", snapshot_answer, base_in(G1),
               "the store plan (snapshot.py:385-410 snapshot_globals, the graph tables and routes)",
               {"an undeclared global (^IVGAuditDRd3Snap scratch)": scratch_global},
               inside=lambda e, c: e.create_node("q", graph=G1), entry="IRISGraphEngine.save_snapshot", project=True,
               note="members whose content differs between two identical base runs are compared by name only"))
    return L


# ------------------------------------------------------------------------------------------------ the run
def variant(case, extra, tag):
    c = lib.conn()
    try:
        lib.reset(c)
        setup_err = None
        e = lib.engine(c)
        try:
            case["base"](e, c)
            c.conn.commit()
            if extra:
                extra(e, c)
                c.conn.commit()
        except Exception as ex:  # noqa: BLE001
            setup_err = f"{type(ex).__name__}: {str(ex)[:300]}"
            try:
                c.conn.rollback()
            except Exception:  # noqa: BLE001
                pass
        e2 = lib.engine(c)
        _CAPTURE.update(on=True, sql=[])
        try:
            ans = case["call"](e2, c)
            err = None
        except Exception as ex:  # noqa: BLE001
            ans, err = None, f"{type(ex).__name__}: {str(ex)[:300]}"
        finally:
            sql = list(_CAPTURE["sql"])
            _CAPTURE.update(on=False, sql=[])
        try:
            c.conn.commit()
        except Exception:  # noqa: BLE001
            pass
        ans = mask(raw(ans))
        with_ctx = {"tag": tag, "setup_error": setup_err, "error": err, "canon": canon(ans), "raw": ans,
                    "sql_tables": tables_of(sql), "sql_count": len(sql)}
        drop_scratch(c)
        return with_ctx
    finally:
        c.close()


def same(a, b):
    return a["canon"] == b["canon"] and (a["error"] or "").split(":")[0] == (b["error"] or "").split(":")[0]


def run_case(case):
    t = time.time()
    b0 = variant(case, None, "base")
    b1 = variant(case, None, "base-again")
    stable = same(b0, b1)
    projected = None
    if not stable and case.get("project") and isinstance(b0["canon"], dict) and isinstance(b1["canon"], dict):
        keep = sorted(k for k in b0["canon"] if b1["canon"].get(k) == b0["canon"][k])
        projected = {"stable_keys": keep, "unstable_keys": sorted(set(b0["canon"]) - set(keep))}

        def proj(v):
            if isinstance(v.get("canon"), dict):
                v = dict(v)
                v["canon"] = {"__keys__": sorted(v["canon"]), **{k: v["canon"].get(k) for k in keep}}
            return v
        b0, b1 = proj(b0), proj(b1)
        stable = same(b0, b1)
        _proj = proj
    else:
        _proj = lambda v: v  # noqa: E731
    res = {"module": case["module"], "id": case["id"], "declared": case["declared"], "note": case["note"],
           "base": b0, "stable": stable, "projected": projected, "outside": {}, "inside": None,
           "inside_declared": {}}
    viol = []
    for name, fn in case["outside"].items():
        v = _proj(variant(case, fn, "outside:" + name))
        ch = not same(b0, v)
        order_only = (not ch) and v["raw"] != b0["raw"]
        res["outside"][name] = {"changed": ch, "order_only_change": order_only, "answer": v["canon"], "error": v["error"],
                                "setup_error": v["setup_error"]}
        if ch and v["setup_error"] is None:
            viol.append(name)
    for name, fn in (case.get("inside_declared") or {}).items():
        v = _proj(variant(case, fn, "inside-declared:" + name))
        res["inside_declared"][name] = {"changed": not same(b0, v), "answer": v["canon"], "error": v["error"]}
    if case["inside"]:
        v = _proj(variant(case, case["inside"], "inside"))
        res["inside"] = {"changed": not same(b0, v), "answer": v["canon"], "error": v["error"], "setup_error": v["setup_error"]}
    # oracle B: Python-issued SQL tables vs the footprint's declared tables
    decl = declared_tables(case["module"], case["entry"]) if case["entry"] else None
    res["oracle_b"] = {"tables_read": b0["sql_tables"], "declared_tables": decl,
                       "undeclared": sorted(set(b0["sql_tables"]) - set(decl)) if decl is not None else None}
    base_err = b0["error"] or b0["setup_error"]
    if isinstance(b0["canon"], dict) and b0["canon"].get("walks_nonempty") is False:
        base_err = "vacuous: the walk returned no steps (random_walk without the Arno library, F-1002)"
    if base_err:
        verdict = "undecided-error" if not viol else "violation"
    elif not stable:
        verdict = "unstable"
    elif viol:
        verdict = "violation"
    else:
        verdict = "holds"
    res["violations"] = viol
    res["verdict"] = verdict
    res["insensitive"] = bool(case["inside"]) and res["inside"] is not None and not res["inside"]["changed"]
    res["seconds"] = round(time.time() - t, 1)
    print(f"[{res['module']}] {verdict:15} {case['id'][:70]}  viol={viol} inside_changed="
          f"{res['inside']['changed'] if res['inside'] else None} base_err={(base_err or '')[:80]} ({res['seconds']}s)", flush=True)
    return res


# ------------------------------------------------------------------------------------------------ self-test
def seeded_cases():
    def blind(e, c):
        return sorted(map(list, c.sql('SELECT "key", val FROM Graph_KG.rdf_props WHERE s = ?', "a")))

    def scoped(e, c):
        return sorted(map(list, c.sql('SELECT "key", val FROM Graph_KG.rdf_props WHERE s = ? AND graph_id = ?', "a", G1)))

    def blind_b(e, c):
        cur = e.conn.cursor()
        cur.execute('SELECT "key" FROM Graph_KG.rdf_props WHERE s = ?', ["a"])
        cur.execute("SELECT COUNT(*) FROM Graph_KG.docs")
        return sorted(r[0] for r in cur.fetchall())

    out = [C("selftest", "SEEDED graph-blind reader (must be flagged)", blind, base_in(G1),
             "rdf_props of a in G1", {"same ids in other graphs": other_graphs(G1)}, inside=inside_nodes(G1)),
           C("selftest", "SEEDED scoped reader (must hold)", scoped, base_in(G1),
             "rdf_props of a in G1", {"same ids in other graphs": other_graphs(G1)}, inside=inside_nodes(G1)),
           C("selftest", "SEEDED reader of an undeclared table (oracle B must flag docs)", blind_b, base_in(G1),
             "rdf_props", {})]
    return out


def main() -> int:
    out_p = Path(sys.argv[sys.argv.index("--out") + 1])
    c = lib.conn()
    info = {"engine": lib.version(c), "pid_example": c.pid, "namespace": lib.NS}
    c.close()
    if "--self-test" in sys.argv:
        rs = [run_case(x) for x in seeded_cases()]
        rs[2]["oracle_b"]["declared_tables"] = ["Graph_KG.rdf_props"]
        rs[2]["oracle_b"]["undeclared"] = sorted(set(rs[2]["oracle_b"]["tables_read"]) - {"Graph_KG.rdf_props"})
        ok_a = rs[0]["verdict"] == "violation" and rs[1]["verdict"] == "holds" and rs[0]["inside"]["changed"] and rs[1]["inside"]["changed"]
        rs[1]["oracle_b"]["declared_tables"] = ["Graph_KG.rdf_props"]
        rs[1]["oracle_b"]["undeclared"] = sorted(set(rs[1]["oracle_b"]["tables_read"]) - {"Graph_KG.rdf_props"})
        ok_b = rs[2]["oracle_b"]["undeclared"] == ["Graph_KG.docs"] and rs[1]["oracle_b"]["undeclared"] == [] and \
            rs[1]["oracle_b"]["tables_read"] == ["Graph_KG.rdf_props"]
        summary = {"self_test_oracle_a": "PASS" if ok_a else "FAIL", "self_test_oracle_b": "PASS" if ok_b else "FAIL"}
        lib.dump(out_p, {"info": info, "summary": summary, "cases": rs})
        print(json.dumps(summary))
        return 0 if ok_a and ok_b else 1
    mods = sys.argv[sys.argv.index("--modules") + 1].split(",")
    sel = [x for x in cases() if x["module"] in mods]
    if "--only" in sys.argv:
        pat = sys.argv[sys.argv.index("--only") + 1]
        sel = [x for x in sel if pat in x["id"]]
    rs = []
    for x in sel:
        try:
            rs.append(run_case(x))
        except Exception as ex:  # noqa: BLE001
            rs.append({"module": x["module"], "id": x["id"], "verdict": "harness-error",
                       "error": f"{type(ex).__name__}: {ex}", "trace": traceback.format_exc()[-1500:]})
            print(f"[{x['module']}] harness-error {x['id']}: {ex}", flush=True)
    summ = {}
    for r in rs:
        s = summ.setdefault(r["module"], {})
        s[r["verdict"]] = s.get(r["verdict"], 0) + 1
    lib.dump(out_p, {"info": info, "summary": summ, "cases": rs})
    print(json.dumps(summ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
