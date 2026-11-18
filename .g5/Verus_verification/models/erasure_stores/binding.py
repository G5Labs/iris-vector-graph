#!/usr/bin/env python3
"""erasure_stores binding (iteration 65): every erase entry point through the real engine from the pin, on the run's own
IRIS fixture, against a hand transcription of erasure_stores.rs (keep_graph / erase_graph, keep_ids / erase_ids with
prefix_sel and list_sel, keep_edges / erase_edges, keep_all / erase_all, delete_edge, the counts, refused, call,
joined_then, dedicated_then, list_erase).

Run from the pin tree through run_binding.py (installs the fixture runtime as `runtime`). It drops and re-creates the
namespaces I65B (graph erase), I65C (prefix / ID / relationship erases and the bypass), I65D (erase-all) and I65E
(caller transactions, chunk commits, an injected failure) from %SYS in the run's container only (docker exec), and
creates the table I65App.Ref in I65E.

Model inputs are the observed store map before each call (an observer independent of the Eraser: SQL over every table
and an ObjectScript $Query walk of every global, run through `iris session`) and the call's own arguments. The
transcription derives the expected store map, return value and refusal; the observation is the store map after the
call, its return value or raised error. Fixture writers: the engine's public writers (create_node, create_edge,
create_edge_temporal, set_temporal_structural, set_multigraph, store_embedding, reify_edge, bm25_build, vec_create_index /
vec_insert, ledger.commit, execute_wcc for ^IVG.AlgoCache). Disclosed direct SQL (no public writer reaches it on this
fixture): NULL-spelled default-graph rows (the column default is ''), docs rows (no engine writer), kg_EdgeEmbeddings
rows, an embedding_quarantine row (written only by a migration), the FHIR side tables (product DDL
GraphSchema.get_fhir_graph_schema_sql, rows by INSERT: fhir_graph_register needs a FHIR repository), an orphan route
(the registry row of a real route deleted, the state a rolled-back route creation leaves), a property row with no node
row. Injected failures, both reachable in production: an over-long node ID in a caller's ID list (<SUBSCRIPT> in
EraseNodeIds) and an application table with a foreign key to Graph_KG.nodes (DELETE FROM nodes fails -124). A failed
post-commit DROP was not injected (not established).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import binding_common as bc  # noqa: E402

PIN_DIR = bc.import_pin()
import runtime  # noqa: E402  (installed by run_binding.py)
from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402
from iris_vector_graph.schema import GraphSchema  # noqa: E402

OK_TAIL = 'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!'
PRODUCT_FILES = ["iris_src/src/Graph/KG/Eraser.cls", "iris_src/src/Graph/KG/GraphStores.cls",
                 "iris_src/src/Graph/KG/Adjacency.cls", "iris_src/src/Graph/KG/TemporalIndex.cls",
                 "iris_src/src/Graph/KG/GraphKey.cls", "iris_vector_graph/_engine/nodes_edges.py",
                 "iris_vector_graph/stores/iris_sql_store.py", "iris_vector_graph/_write_txn.py",
                 "iris_vector_graph/_validate.py", "iris_vector_graph/engine.py"]
DIM = 8


# ====================================================================== the fixture
def iris(script, ns="%SYS"):
    return subprocess.run(["docker", "exec", "-i", runtime.NAME, "iris", "session", "IRIS", "-U", ns],
                          input=script + "\nHalt\n", capture_output=True, text=True, timeout=600).stdout


def recreate(ns):
    assert ns.startswith("I65")
    out = iris(f'Set ns="{ns}", dir="/usr/irissys/mgr/{ns.lower()}/"\n'
               'If ##class(Config.Namespaces).Exists(ns) { Set sc=##class(Config.Namespaces).Delete(ns) }\n'
               'If ##class(Config.Databases).Exists(ns) { Set sc=##class(Config.Databases).Delete(ns) }\n'
               'If ##class(%File).Exists(dir_"IRIS.DAT") { Set sc=##class(SYS.Database).DeleteDatabase(dir) }\n'
               'Set ok=##class(%File).CreateDirectoryChain(dir) Set sc=##class(SYS.Database).CreateDatabase(dir) '
               'If $System.Status.IsOK(sc) { Set pdb("Directory")=dir, sc=##class(Config.Databases).Create(ns,.pdb) } '
               'If $System.Status.IsOK(sc) { Set pns("Globals")=ns, pns("Routines")=ns, sc=##class(Config.Namespaces).Create(ns,.pns) } '
               + OK_TAIL)
    assert "RESULT OK" in out, out


def fresh(ns):
    recreate(ns)
    c = runtime.connect(ns)
    e = IRISGraphEngine(c, embedding_dimension=DIM, namespace=ns)
    e.initialize_schema()
    return c, e


# ====================================================================== the observer (independent of the Eraser)
# (global root, depth below the root, model kind). Entry-level walks emit each distinct subscript prefix of that depth.
WALKS = [('^KG("out")', 4, "out"), ('^KG("in")', 4, "in"), ('^KG("gen")', 2, "Gen"), ('^KG("degc")', 2, "Degc"),
         ('^KG("degw")', 1, "Degw"), ('^IVG.AdjNoLock', 1, "NoLock"), ('^KG("label")', 3, "KLabel"),
         ('^KG("prop")', 2, "KProp"), ('^KG("deg2p")', 1, "Deg2p"), ('^KG("deg2p_exact")', 1, "Deg2p"),
         ('^KG("tout")', 5, "tout"), ('^IVG.TemporalStructural', 2, "TStruct"), ('^IVG.GraphMode', 1, "GMode"),
         ('^IVG.AlgoCache', 3, "ACache"), ('^IVG.Ledger("tuple")', 4, "Tuple"), ('^NKG("$NI")', 1, "Nkg")]
# temporal subtrees other than tout, counted per graph key (TAgg); whole-store counts for the rest
PER_KEY = [('^KG("tin")', "tin"), ('^KG("bucket")', "bucket"), ('^KG("tagg")', "tagg"), ('^KG("edgeprop")', "edgeprop"),
           ('^KG("tlast")', "tlast")]
WHOLE = [('^KG("labelset")', "Labelset"), ('^KG("deg2p_exact_merged")', "Merged"), ('^ArnoKG', "Arno"),
         ('^IVG.Ledger("rec")', "Rec"), ('^BM25Idx', "Bm25"), ('^IVF', "Ivf"), ('^PLAID', "Plaid"), ('^VecIdx', "VecIdx"),
         ('^NKG', "NkgAll")]


def _walk(root, d, tag):
    return (f'Set r=$Name({root}),ql=$QLength(r),q=r,last="" For  Set q=$Query(@q) Quit:q=""  Quit:$Name(@q,ql)\'=r  '
            f'Set k=$Name(@q,ql+{d}) If k\'=last {{ Set last=k,a=[] For i=ql+1:1:$QLength(k) {{ Do a.%Push($QSubscript(k,i)) }} '
            f'Write "E",$C(9),"{tag}",$C(9),a.%ToJSON(),! }}')


def _perkey(root, tag):
    return (f'Set r=$Name({root}),ql=$QLength(r),q=r For  Set q=$Query(@q) Quit:q=""  Quit:$Name(@q,ql)\'=r  '
            f'Write "E",$C(9),"{tag}",$C(9),[($QSubscript(q,ql+1))].%ToJSON(),!')


def _count(root, tag):
    return (f'Set r=$Name({root}),ql=$QLength(r),q=r,n=0 For  Set q=$Query(@q) Quit:q=""  Quit:$Name(@q,ql)\'=r  '
            f'Set n=n+1\nWrite "C",$C(9),"{tag}",$C(9),n,!')


def global_entries(ns):
    lines = [_walk(r, d, t) for r, d, t in WALKS] + [_perkey(r, t) for r, t in PER_KEY]
    for r, t in WHOLE:
        lines += _count(r, t).split("\n")
    lines.append('Set i="" For  Set i=$Order(^IVG.Ledger("stmt",i)) Quit:i=""  Set v=$Get(^IVG.Ledger("stmt",i)) '
                 'Write "E",$C(9),"Stmt",$C(9),[(i),($LG(v,1)),($LG(v,2)),($LG(v,3)),($LG(v,4))].%ToJSON(),!')
    lines.append('Write "V",$C(9),"version",$C(9),+$Get(^KG("__version")),!')
    lines.append('Write "V",$C(9),"invalidated",$C(9),+$Get(^NKG("$meta","invalidated")),!')
    lines.append('Write "V",$C(9),"nkgstamp",$C(9),$Data(^NKG("$meta","version"))#2,!')
    out = iris("\n".join(lines), ns)
    ent, cnt, val = [], {}, {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        kind, tag, payload = parts
        if kind.endswith("E"):
            ent.append((tag, json.loads(payload)))
        elif kind.endswith("C"):
            cnt[tag] = int(payload)
        elif kind.endswith("V"):
            val[tag] = int(payload)
    if "version" not in val:
        raise RuntimeError("observer failed: " + out[-1500:])
    return ent, cnt, val


def nz(v):
    return "" if v is None else str(v).replace("\x00", "")


def key_name(k):
    """^KG key (0 for the default graph) -> canonical graph name."""
    return "" if str(k) in ("0", "") else str(k)


def ledger_name(g):
    return "" if g in ("\x01", "\x00", "", None) else g


class Snap:
    """The observed store map: entries (k, g, s, p, o, eid, tbl, wm), g being the raw SQL spelling (None = NULL)."""

    def __init__(self, entries, version, invalidated, routes):
        self.entries, self.version, self.invalidated, self.routes = entries, version, invalidated, routes

    def counter(self):
        return Counter(self.entries)


def E(k, g="", s="", p="", o="", eid="", tbl="", wm=""):
    return (k, g, s, p, o, eid, tbl, wm)


def sql_entries(c):
    cur = c.cursor()

    def rows(sql):
        try:
            cur.execute(sql)
            return cur.fetchall()
        except Exception:  # noqa: BLE001  (a table this namespace does not have)
            return None

    def gid(v):
        return None if v is None else nz(v)

    out = []
    for g, n in rows("SELECT graph_id, node_id FROM Graph_KG.nodes") or []:
        out.append(E("Node", gid(g), nz(n)))
    for g, s, lab in rows("SELECT graph_id, s, label FROM Graph_KG.rdf_labels") or []:
        out.append(E("Label", gid(g), nz(s), nz(lab)))
    for g, s, k in rows('SELECT graph_id, s, "key" FROM Graph_KG.rdf_props') or []:
        out.append(E("Prop", gid(g), nz(s), nz(k)))
    for g, s, p, o, eid in rows("SELECT graph_id, s, p, o_id, edge_id FROM Graph_KG.rdf_edges") or []:
        out.append(E("Edge", gid(g), nz(s), nz(p), nz(o), str(eid)))
    for g, i in rows("SELECT graph_id, id FROM Graph_KG.docs") or []:
        out.append(E("Doc", gid(g), nz(i)))
    for t, k in (("kg_NodeEmbeddings", "NEmb"), ("kg_NodeEmbeddings_optimized", "NEmbOpt")):
        for g, n in rows(f"SELECT graph_id, node_id FROM Graph_KG.{t}") or []:
            out.append(E(k, gid(g), nz(n)))
    for g, s, p, o in rows("SELECT graph_id, s, p, o_id FROM Graph_KG.kg_EdgeEmbeddings") or []:
        out.append(E("EEmb", gid(g), nz(s), nz(p), nz(o)))
    routes = [nz(r[0]) for r in rows("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'Graph_KG' "
                                     "AND ((TABLE_NAME %STARTSWITH 'kg_emb_') OR (TABLE_NAME %STARTSWITH 'kg_eemb_'))") or []]
    for t in routes:
        out.append(E("RouteTable", "", tbl=t))
        if t.startswith("kg_emb_"):
            for g, n in rows(f"SELECT graph_id, node_id FROM Graph_KG.{t}") or []:
                out.append(E("NRoute", gid(g), nz(n), tbl=t))
        else:
            for g, s, p, o in rows(f"SELECT graph_id, s, p, o_id FROM Graph_KG.{t}") or []:
                out.append(E("ERoute", gid(g), nz(s), nz(p), nz(o), tbl=t))
    for g, t in rows("SELECT graph_id, table_name FROM Graph_KG.embedding_registry") or []:
        out.append(E("Registry", gid(g), tbl=nz(t)))
    for eid, rid in rows("SELECT edge_id, reifier_id FROM Graph_KG.rdf_reifications") or []:
        out.append(E("Reif", "", nz(rid), eid=str(eid)))
    for (i,) in rows("SELECT %ID FROM Graph_KG.embedding_quarantine") or []:
        out.append(E("Quar", "", str(i)))
    for t, col in (("fhir_unresolved", "source"), ("fhir_canonical_refs", "source"), ("fhir_definitions", "rsrc_key")):
        for g, s in rows(f"SELECT graph_id, {col} FROM Graph_KG.{t}") or []:
            out.append(E("FhirSide", gid(g), nz(s), t))
    for g, a, b in rows("SELECT graph_id, wm_rsrc, wm_ver FROM Graph_KG.fhir_graphs") or []:
        out.append(E("FhirReg", gid(g), wm=f"{int(a or 0)}/{int(b or 0)}"))
    return out, routes


def snapshot(c, ns):
    sq, routes = sql_entries(c)
    ent, cnt, val = global_entries(ns)
    out = list(sq)
    for tag, a in ent:
        a = [nz(x) for x in a]
        if tag == "out":
            out.append(E("Adj", key_name(a[0]), a[1], a[2], a[3], "out"))
        elif tag == "in":
            out.append(E("Adj", key_name(a[0]), a[3], a[2], a[1], "in"))
        elif tag in ("Gen", "Degc", "KProp"):
            out.append(E(tag, key_name(a[0]), a[1] if len(a) > 1 else ""))
        elif tag in ("Degw", "NoLock", "GMode"):
            out.append(E(tag, key_name(a[0])))
        elif tag == "Deg2p":
            out.append(E("Deg2p", key_name(a[0])))
        elif tag == "KLabel":
            out.append(E("KLabel", key_name(a[0]), a[2] if len(a) > 2 else "", a[1] if len(a) > 1 else ""))
        elif tag == "tout":
            out.append(E("Temporal", key_name(a[0]), a[2], a[3], a[4], a[1]))
        elif tag in ("tin", "bucket", "tagg", "edgeprop", "tlast"):
            out.append(E("TAgg", key_name(a[0]), tag))
        elif tag == "TStruct":
            out.append(E("TStruct", key_name(a[0]), a[1] if len(a) > 1 else ""))
        elif tag == "ACache":
            out.append(E("ACache", key_name(a[0]), a[1] if len(a) > 1 else "", a[2] if len(a) > 2 else ""))
        elif tag == "Tuple":
            out.append(E("Tuple", ledger_name(a[3]), a[0], a[1], a[2]))
        elif tag == "Stmt":
            out.append(E("Stmt", ledger_name(a[4]), a[1], a[2], a[3], a[0]))
        elif tag == "Nkg":
            out.append(E("Nkg", "", a[0]))
    ni = sum(1 for t, _ in ent if t == "Nkg")
    for tag, n in cnt.items():
        if tag == "NkgAll":
            # ^NKG beyond its dictionary, the invalidation mark and DropNKG's version stamp (GraphIndex.cls:22-27)
            n = n - ni - (1 if val.get("invalidated") else 0) - (1 if val.get("nkgstamp") else 0)
            tag = "NkgOther"
        for i in range(max(n, 0)):
            out.append(E(tag, "", f"#{i}"))
    return Snap(sorted(out, key=repr), val["version"], val["invalidated"], routes)


# ====================================================================== transcription of erasure_stores.rs
GRAPH_KILL = {"Node", "Label", "Prop", "Edge", "Doc", "NEmb", "NEmbOpt", "EEmb", "NRoute", "ERoute", "FhirSide", "Adj",
              "Gen", "Degc", "Degw", "NoLock", "KLabel", "KProp", "Deg2p", "Temporal", "TAgg", "GMode", "ACache", "Stmt",
              "Tuple"}
NODE_KILL = {"Node", "Label", "Prop", "Doc", "NEmb", "NEmbOpt", "NRoute", "FhirSide", "KLabel", "KProp", "Gen", "Degc"}
NKG_KINDS = {"Nkg", "NkgOther"}   # GraphIndex.DropNKG takes ^NKG whole
ALL_KEEP = {"Quar", "Rec", "FhirReg", "Bm25", "Ivf", "Plaid", "VecIdx"}
# Not compared for list erases: the temporal aggregates TemporalIndex.EraseNodes rewrites per bucket (outside the model)
LIST_SKIP = {"TAgg"}


def canon(g):
    return "" if g is None else g


def in_g(e, c):
    return canon(e[1]) == c


def interned(r, i):
    return ("Nkg", "", i, "", "", "", "", "") in r


def valid(n):
    return n != "0" and not any(ord(ch) < 32 or ord(ch) == 127 for ch in n)


def route_named(t):
    import re
    return bool(re.fullmatch(r"(?i)kg_e?emb_[0-9a-f]{16}", t or ""))


def at_risk_graph(r, c):
    return any(in_g(e, c) and (((e[0] in ("Edge", "Adj")) and interned(r, e[2]) and interned(r, e[4]))
                               or (e[0] == "Node" and interned(r, e[2]))) for e in r)


def claimed(r, c, tbl):
    return route_named(tbl) and any(e[0] == "Registry" and in_g(e, c) and e[6] == tbl for e in r)


def reset_in(e, c):
    return e[:7] + ("0/0",) if e[0] == "FhirReg" and in_g(e, c) else e


def keep_graph(r, c, df, e):
    k = e[0]
    if k in GRAPH_KILL and in_g(e, c):
        return False
    if k == "ACache":
        return False
    if k in NKG_KINDS:
        return not at_risk_graph(r, c)
    if k == "Reif":
        return not any(x[0] == "Edge" and in_g(x, c) and x[5] == e[5] for x in r)
    if k == "RouteTable":
        return not (claimed(r, c, e[6]) and e[6] not in df)
    if k == "Registry" and in_g(e, c):
        return not (claimed(r, c, e[6]) and e[6] not in df)
    return True


def erase_graph(r, c, df=frozenset()):
    return [x for x in (reset_in(e, c) for e in r) if keep_graph(r, c, df, x)]


def count_graph(r, c):
    return sum(1 for e in r if e[0] in ("Node", "Edge") and in_g(e, c))


def incident(e, c, d):
    return e[0] == "Edge" and in_g(e, c) and (e[2] in d or e[4] in d)


def keep_ids(r, c, d, e):
    k = e[0]
    inc = [x for x in r if incident(x, c, d)]
    had = any(in_g(x, c) and x[0] in ("Edge", "Adj") and (x[2] in d or x[4] in d) for x in r)
    removed = any(x[0] == "Node" and in_g(x, c) and x[2] in d for x in r)
    risk = any(interned(r, x[2]) and interned(r, x[4]) for x in inc) or any(interned(r, i) for i in d)
    if in_g(e, c) and k in NODE_KILL and e[2] in d:
        return False
    if incident(e, c, d):
        return False
    if k == "Reif":
        return not any(x[5] == e[5] for x in inc)
    if k in ("EEmb", "ERoute", "Stmt", "Tuple") and in_g(e, c):
        return not any(x[2] == e[2] and x[3] == e[3] and x[4] == e[4] for x in inc)
    if k in ("Adj", "Temporal") and in_g(e, c):
        return not (e[2] in d or e[4] in d)
    if k == "Deg2p" and in_g(e, c):
        return not had
    if k == "ACache":
        return not (removed or had)
    if k in NKG_KINDS:
        return not ((removed or had) and risk)
    return True


def erase_ids(r, c, d):
    return [e for e in r if keep_ids(r, c, d, e)]


def count_ids(r, c, d):
    return sum(1 for e in r if e[0] == "Node" and in_g(e, c) and e[2] in d)


def prefix_sel(r, c, pfx):
    return {e[2] for e in r if e[0] == "Node" and in_g(e, c) and e[2].startswith(pfx)}


def list_sel(ids):
    return {i for i in ids if i}


def keep_edges(r, c, t, e):
    k = e[0]
    sel = [x for x in r if x[0] == "Edge" and in_g(x, c) and (x[2], x[3], x[4]) in t]
    any_removed = any(in_g(x, c) and x[0] in ("Edge", "Adj") and (x[2], x[3], x[4]) in t for x in r)
    if e in sel:
        return False
    if k == "Reif":
        return not any(x[5] == e[5] for x in sel)
    if k in ("EEmb", "ERoute", "Stmt", "Tuple") and in_g(e, c):
        return not any((x[2], x[3], x[4]) == (e[2], e[3], e[4]) for x in sel)
    if k == "Adj" and in_g(e, c):
        return (e[2], e[3], e[4]) not in t
    if (k == "Deg2p" and in_g(e, c)) or k == "ACache" or k in NKG_KINDS:
        return not any_removed
    return True


def erase_edges(r, c, t):
    return [e for e in r if keep_edges(r, c, t, e)]


def count_edges(r, c, t):
    return sum(1 for e in r if e[0] == "Edge" and in_g(e, c) and (e[2], e[3], e[4]) in t)


def keep_all(r, df, e):
    if e[0] in ALL_KEEP:
        return True
    if e[0] == "RouteTable":
        return not (route_named(e[6]) and any(x[0] == "Registry" and x[6] == e[6] for x in r) and e[6] not in df)
    return False


def erase_all(r, df=frozenset()):
    return [x for x in ((e[:7] + ("0/0",)) if e[0] == "FhirReg" else e for e in r) if keep_all(r, df, x)]


def delete_edge_t(r, c, x):
    return [e for e in r if not (e[0] in ("Edge", "Adj") and in_g(e, c) and (e[2], e[3], e[4]) == x)]


def expect(r, ep):
    """(outcome, expected entries) per the model's `call` with no failure and no failed drop."""
    kind = ep[0]
    if kind == "graph":
        c = ep[1] or ""
        if not valid(c):
            return ("refused", r)
        return (count_graph(r, c), erase_graph(r, c))
    if kind == "prefix":
        c, pfx = ep[1] or "", ep[2]
        if not pfx or not valid(c):
            return ("refused", r)
        d = prefix_sel(r, c, pfx)
        return (count_ids(r, c, d), erase_ids(r, c, d))
    if kind == "ids":
        c, d = ep[1] or "", list_sel(ep[2])
        return (count_ids(r, c, d), erase_ids(r, c, d))
    if kind == "edges":
        c, t = ep[1] or "", set(ep[2])
        return (count_edges(r, c, t), erase_edges(r, c, t))
    if kind == "all":
        return (sum(1 for e in r if e[0] in ("Node", "Edge")), erase_all(r))
    if kind == "delete_edge":
        return (True, delete_edge_t(r, ep[1] or "", ep[2]))
    raise ValueError(kind)


def diff(expected, observed, skip=()):
    ce = Counter(e for e in expected if e[0] not in skip)
    co = Counter(e for e in observed if e[0] not in skip)
    missing, extra = ce - co, co - ce
    kinds = sorted({e[0] for e in list(missing) + list(extra)})
    return {"agrees": not missing and not extra, "kinds": kinds,
            "expected_not_observed": [list(e) for e in list(missing.elements())[:8]],
            "observed_not_expected": [list(e) for e in list(extra.elements())[:8]]}


CASES = []


def record(name, ep, pre, post, ret, err, want_out, expected, skip=(), note=""):
    d = diff(expected, post.entries, skip)
    outcome_ok = (want_out == "refused" and err is not None and post.entries == pre.entries) or \
                 (want_out != "refused" and err is None and ret == want_out)
    case = {"case": name, "entry_point": list(ep[:2]) + ([repr(ep[2])[:80]] if len(ep) > 2 else []),
            "returned": ret, "error": err, "expected_return": want_out, "outcome_agrees": outcome_ok,
            "stores": d, "pre_entries": len(pre.entries), "post_entries": len(post.entries),
            "version": [pre.version, post.version], "nkg_invalidated": [pre.invalidated, post.invalidated],
            "pre_kinds": dict(sorted(Counter(x[0] for x in pre.entries).items())),
            "post_kinds": dict(sorted(Counter(x[0] for x in post.entries).items())),
            "skip_kinds": sorted(skip), "note": note}
    case["agrees"] = outcome_ok and d["agrees"]
    CASES.append(case)
    flag = "AGREES" if case["agrees"] else "DISAGREES"
    print(f"  {name}: {flag} returned={ret!r} expected={want_out!r} err={str(err)[:80]!r} {d['kinds']}", flush=True)
    return case


def run(c, ns, name, ep, call, skip=(), note="", want=None):
    pre = snapshot(c, ns)
    want_out, expected = expect(pre.entries, ep) if want is None else want(pre)
    ret, err = None, None
    try:
        ret = call()
        if hasattr(ret, "rows"):
            ret = ret.rows[0][0]
        if hasattr(ret, "deleted"):
            ret = [ret.deleted, ret.failed]
    except Exception as x:  # noqa: BLE001
        err = f"{type(x).__name__}: {str(x)[:300]}"
    post = snapshot(c, ns)
    case = record(name, ep, pre, post, ret, err, want_out, expected, skip, note)
    return pre, post, case


# ====================================================================== scenario B: graph erase
def vec(x):
    return [x] * DIM


def ledger_rel(e, rels):
    e.ledger.enable()
    cs = Changeset(actor="i65", actor_type="system", auto_stub_missing_nodes=True)
    for s, p, o, g in rels:
        cs.create_relationship(s, p, o, graph=g)
    e.ledger.commit(cs)


def fhir_tables(c, rows_by_graph):
    cur = c.cursor()
    from iris_vector_graph.utils import _split_sql_statements
    for body in _split_sql_statements(GraphSchema.get_fhir_graph_schema_sql()):   # the product's own splitter
        if body.strip():
            try:
                cur.execute(body)
            except Exception as x:  # noqa: BLE001
                if "already exists" not in str(x).lower():
                    print("  fhir ddl:", str(x)[:120])
    for g in rows_by_graph:
        cur.execute("INSERT INTO Graph_KG.fhir_unresolved (graph_id, source, param, target, reason) VALUES (?, 'a', 'subject', "
                    "'Patient/p1', 'missing')", [g])
        cur.execute("INSERT INTO Graph_KG.fhir_graphs (graph_id, repo_id, rsrc_schema, search_schema, ver_schema, wm_rsrc, "
                    "wm_ver) VALUES (?, ?, 'R', 'S', 'V', 7, 9)", [g, f"repo-{g}"])


def quarantine(cur):
    cur.execute("INSERT INTO Graph_KG.embedding_quarantine (node_id, source_table, dimension, dtype, reason) "
                "VALUES ('q1', 'kg_NodeEmbeddings', 8, 'double', 'ambiguous_graph')")


def _has_cols(c, table, cols):
    cur = c.cursor()
    cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='Graph_KG' AND TABLE_NAME=?", [table])
    have = {r[0].lower() for r in cur.fetchall()}
    return all(x in have for x in cols)


def scenario_b():
    ns = "I65B"
    print(f"[{ns}] graph erase", flush=True)
    c, e = fresh(ns)
    cur = c.cursor()
    for g in ("g1", "g2"):
        for n in ("a", "b"):
            e.create_node(n, ["P"], {"name": f"{n}-{g} text"}, graph=g)
        e.create_edge("a", "R", "b", graph=g)
        e.create_edge_temporal("a", "T", "b", timestamp=1700000000, graph=g)
        e.store_embedding("a", vec(0.1), graph=g)
        cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, 'a', 'alpha doc')", [g])
    e.set_temporal_structural("EV", False, graph="g1")
    e.create_edge_temporal("t1", "EV", "t2", timestamp=1700000100, graph="g1")
    e.set_multigraph("g1", True)
    e.set_multigraph("g2", True)
    for g in ("g1", "g2"):
        cur.execute("SELECT edge_id FROM Graph_KG.rdf_edges WHERE graph_id = ? AND s = 'a' AND p = 'R'", [g])
        e.reify_edge(cur.fetchone()[0], reifier_id=f"reif-{g}", props={"why": f"secret-{g}"})
    ledger_rel(e, [("l1", "R", "l2", "g1"), ("l1", "R", "l2", "g2"), ("l1", "R", "l2", None)])
    e.bm25_build("ix1", ["name"], graph="g1")
    # default graph: '' through the writers, NULL by an explicit INSERT (the column default is '')
    e.create_node("d1", ["P"], {"k": "v"})
    e.create_edge("d1", "R", "a")
    e.create_node("dn", ["P"], {})
    nulls = {}
    for tbl, sql in (("nodes", "INSERT INTO Graph_KG.nodes (graph_id, node_id) VALUES (NULL, 'dn0')"),
                     ("rdf_props", "INSERT INTO Graph_KG.rdf_props (graph_id, s, \"key\", val) VALUES (NULL, 'dn', 'k2', 'v')"),
                     ("rdf_labels", "INSERT INTO Graph_KG.rdf_labels (graph_id, s, label) VALUES (NULL, 'dn', 'Q')"),
                     ("rdf_edges", "INSERT INTO Graph_KG.rdf_edges (graph_id, s, p, o_id) VALUES (NULL, 'dn', 'R', 'd1')"),
                     ("docs", "INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (NULL, 'dn', 'null doc')")):
        try:
            cur.execute(sql)
            nulls[tbl] = "accepted"
        except Exception as x:  # noqa: BLE001
            nulls[tbl] = str(x).split("%msg:")[-1][:120]
    CASES.append({"case": "B0_null_spelling_reachability", "observed": nulls, "agrees": True,
                  "model": "Sp::Null is representable; which tables accept it is a schema fact recorded here"})
    print("  NULL graph_id:", nulls)
    # an orphan route holding g1's vectors: a second route for g1, its registry row removed
    e.store_embedding("a", vec(0.2), graph="g1", model_key="m2")
    cur.execute("SELECT table_name FROM Graph_KG.embedding_registry WHERE graph_id = 'g1' AND model_key = 'm2'")
    orphan = cur.fetchone()[0]
    cur.execute("DELETE FROM Graph_KG.embedding_registry WHERE table_name = ?", [orphan])
    quarantine(cur)
    fhir_tables(c, ["g1", "g2"])
    e.kg_WCC()   # ^IVG.AlgoCache for the default graph
    e.sync() if hasattr(e, "sync") else None   # ^NKG
    # the mark a writer leaves when the writer lock is not granted in 5 s (Adjacency.cls:57-67), set directly
    out = iris('Set x=$Increment(^IVG.AdjNoLock("g1")),x=$Increment(^IVG.AdjNoLock("g2"))\nWrite "RESULT OK",!', ns)
    assert "RESULT OK" in out, out
    run(c, ns, "B1_erase_graph_g1", ("graph", "g1"), lambda: e.erase_graph("g1"))
    reif = e.get_node("reif-g1") if hasattr(e, "get_node") else None
    CASES.append({"case": "B1_reader_reifier_node_after_erase", "observed": reif,
                  "model": "witness_named_erase_keeps_reifier_node: the reifier node (default graph) keeps the edge's properties",
                  "agrees": bool(reif) and "secret-g1" in json.dumps(reif, default=str)})
    mg = {g: e.is_multigraph(g) for g in ("g1", "g2")}
    CASES.append({"case": "B1_reader_is_multigraph_after_erase", "observed": mg,
                  "model": "graph_kill(GMode): g1's mode cleared, g2's kept", "agrees": mg == {"g1": False, "g2": True}})
    hits = e.bm25_search("ix1", "text", 5) if hasattr(e, "bm25_search") else None
    CASES.append({"case": "B1_reader_bm25_after_erase", "observed": [list(h) for h in (hits or [])],
                  "model": "witness_empty_digest_bm25_survives: the BM25 index recorded for g1 still answers",
                  "agrees": bool(hits) and all(h[0] in ("a", "b") for h in hits)})
    dg = json.loads(str(e._iris_obj().classMethodValue("Graph.KG.GraphStores", "Digest", "g1")))
    nonempty = {k: v["entries"] for k, v in dg["stores"].items() if v["entries"]}
    CASES.append({"case": "B1_reader_digest_after_erase", "observed": nonempty,
                  "model": "theorem_graph_erase_digest_empty + witness_digest_reports_kept_setting: only configuration",
                  "agrees": set(nonempty) <= {'^IVG.TemporalStructural', 'Graph_KG.embedding_registry'}})
    print("  digest after erase (non-empty):", nonempty)
    run(c, ns, "B2_drop_graph_g2", ("graph", "g2"), lambda: e.drop_graph("g2"),
        note="drop_graph is erase_graph (theorem_drop_graph_is_erase_graph)")
    run(c, ns, "B3_erase_default_none", ("graph", None), lambda: e.erase_graph(None),
        note="both spellings: rows with graph_id '' and NULL")
    run(c, ns, "B4_refuse_zero", ("graph", "0"), lambda: e.erase_graph("0"))
    run(c, ns, "B5_refuse_control", ("graph", "bad\x01"), lambda: e.erase_graph("bad\x01"))
    run(c, ns, "B6_eraser_refuses_zero_natively", ("graph", "0"),
        lambda: e._iris_obj().classMethodValue("Graph.KG.Eraser", "EraseGraph", "0"),
        note="the Eraser's own GraphKey refusal (Python refuses first on the engine path)")
    run(c, ns, "B7_erase_empty_graph", ("graph", "g9"), lambda: e.erase_graph("g9"))
    c.close()


# ====================================================================== scenario C: prefix, ID and relationship erases
def scenario_c():
    ns = "I65C"
    print(f"[{ns}] prefix / ID / relationship erases and delete_edge", flush=True)
    c, e = fresh(ns)
    cur = c.cursor()
    for g in ("g1", "g2"):
        for n in ("acme|1", "acme|2", "acme-health|1", "x1", "x2", "x3", "k1", "k2", "k3", "k4", "m1", "m2"):
            e.create_node(n, ["P"], {"name": n}, graph=g)
        for s, o in (("acme|1", "acme|2"), ("acme|1", "x1"), ("acme-health|1", "acme|2"), ("x2", "x3"), ("m1", "m2")):
            e.create_edge(s, "R", o, graph=g)
        e.create_edge_temporal("acme|1", "T", "x1", timestamp=1700000000, graph=g)
        e.store_embedding("acme|1", vec(0.3), graph=g)
        cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, 'acme|1', 'doc')", [g])
    e.set_temporal_structural("EV", False, graph="g1")
    e.create_edge_temporal("acme|9", "EV", "acme|10", timestamp=1700000200, graph="g1")   # temporal-only, no node rows
    cur.execute("INSERT INTO Graph_KG.rdf_props (graph_id, s, \"key\", val) VALUES ('g1', 'acme|8', 'k', 'v')")  # no node
    ledger_rel(e, [("k1", "R", "k2", "g1"), ("k3", "R", "k4", "g1"), ("k1", "R", "k2", "g2"), ("acme|1", "L", "acme|2", "g1")])
    cur.execute("SELECT edge_id FROM Graph_KG.rdf_edges WHERE graph_id = 'g1' AND s = 'k3'")
    e.reify_edge(cur.fetchone()[0], reifier_id="reif-k3", props={"why": "x"})
    e.sync() if hasattr(e, "sync") else None
    run(c, ns, "C1_prefix_acme_bar", ("prefix", "g1", "acme|"), lambda: e.delete_nodes_by_prefix("acme|", graph="g1"),
        skip=LIST_SKIP)
    run(c, ns, "C2_refuse_empty_prefix", ("prefix", "g1", ""), lambda: e.delete_nodes_by_prefix("", graph="g1"))
    run(c, ns, "C3_ids_without_node_rows", ("ids", "g1", ["acme|9", "acme|8"]),
        lambda: e._store.delete_nodes(["acme|9", "acme|8"], graph="g1"), skip=LIST_SKIP,
        note="explicit IDs reach the temporal-only event and the orphan property row the prefix erase left")
    run(c, ns, "C4_delete_node", ("ids", "g1", ["x1"]), lambda: e.delete_node("x1", graph="g1"), skip=LIST_SKIP,
        want=lambda pre: ((lambda n, r: (n > 0, r))(*expect(pre.entries, ("ids", "g1", ["x1"])))))
    run(c, ns, "C5_bulk_delete_nodes", ("ids", "g1", ["x2", "x3"]),
        lambda: e.bulk_delete_nodes(["x2", "x3"], graph="g1"), skip=LIST_SKIP,
        want=lambda pre: ((lambda n, r: ([n, 0], r))(*expect(pre.entries, ("ids", "g1", ["x2", "x3"])))))
    run(c, ns, "C6_store_delete_edges", ("edges", "g1", [("k1", "R", "k2")]),
        lambda: e._store.delete_edges([("k1", "R", "k2")], graph="g1"), skip=LIST_SKIP)
    run(c, ns, "C7_delete_edge_bypass", ("delete_edge", "g1", ("k3", "R", "k4")),
        lambda: e.delete_edge("k3", "R", "k4", graph="g1"), skip=LIST_SKIP,
        note="bypass: the statement, tuple lookup and reification stay (bug-str-013)")

    def bda_want(pre):
        r = pre.entries
        for g in ("g1", "g2"):
            t = {(x[2], x[3], x[4]) for x in r if incident(x, g, {"m1"})}
            r = erase_edges(r, g, t)
        return (1, r)
    run(c, ns, "C8_bulk_delete_adjacency", ("bda", "*", ["m1"]), lambda: e.bulk_delete_adjacency(["m1"]),
        skip=LIST_SKIP, want=bda_want, note="EraseEdges per graph holding an incident edge; returns len(ids)")
    c.close()


# ====================================================================== scenario D: erase-all
def scenario_d():
    ns = "I65D"
    print(f"[{ns}] erase-all", flush=True)
    c, e = fresh(ns)
    cur = c.cursor()
    for g in ("g1", None):
        e.create_node("a", ["P"], {"name": "alpha text"}, graph=g)
        e.create_node("b", ["P"], {"name": "beta text"}, graph=g)
        e.create_edge("a", "R", "b", graph=g)
        e.create_edge_temporal("a", "T", "b", timestamp=1700000000, graph=g)
        e.store_embedding("a", vec(0.4), graph=g)
    e.set_temporal_structural("EV", False, graph="g1")
    e.set_multigraph("g1", True)
    ledger_rel(e, [("l1", "R", "l2", "g1")])
    e.bm25_build("ixd", ["name"], graph="g1")
    try:
        e.vec_create_index("vx", DIM)
        e.vec_insert("vx", "a", vec(0.5))
    except Exception as x:  # noqa: BLE001
        print("  vec index:", str(x)[:120])
    quarantine(cur)
    fhir_tables(c, ["g1"])
    e.kg_WCC()
    e.sync() if hasattr(e, "sync") else None
    run(c, ns, "D1_erase_all", ("all",), lambda: e.erase_all())
    hits = e.bm25_search("ixd", "text", 5) if hasattr(e, "bm25_search") else None
    CASES.append({"case": "D1_reader_bm25_after_erase_all", "observed": [list(h) for h in (hits or [])],
                  "model": "witness_erase_all_keeps_named_indexes", "agrees": bool(hits)})
    c.close()


# ====================================================================== scenario E: caller transactions, chunks, failures
def seed_e(e, cur):
    for n in ("a", "b"):
        e.create_node(n, ["P"], {"name": n}, graph="g1")
    e.create_edge("a", "R", "b", graph="g1")
    e.store_embedding("a", vec(0.6), graph="g1")


def scenario_e():
    ns = "I65E"
    print(f"[{ns}] caller transactions, chunk commits, injected failures", flush=True)
    c, e = fresh(ns)
    cur = c.cursor()
    seed_e(e, cur)
    def caller(z, decision, call):
        base = snapshot(c, ns)
        c.setAutoCommit(False)
        e.create_node(z, ["P"], {}, graph="g9")
        ret, err = None, None
        try:
            ret = call()
            if hasattr(ret, "rows"):
                ret = ret.rows[0][0]
        except Exception as x:  # noqa: BLE001
            err = f"{type(x).__name__}: {str(x)[:300]}"
        (c.commit if decision == "commit" else c.rollback)()
        c.setAutoCommit(True)
        post = snapshot(c, ns)
        return base, post, ret, err

    def outside_g9(entries):
        return [x for x in entries if canon(x[1]) != "g9"]

    def caller_case(name, ep, base, post, ret, err, want_ret, want_entries, has_z, z, skip=(), note=""):
        """The caller's own write (graph g9) is checked as present or absent; every other entry against the model."""
        b = Snap(outside_g9(base.entries), base.version, base.invalidated, base.routes)
        p = Snap(outside_g9(post.entries), post.version, post.invalidated, post.routes)
        case = record(name, ep, b, p, ret, err, want_ret, outside_g9(want_entries), skip, note)
        seen = E("Node", "g9", z) in post.entries
        case["caller_write_after"] = seen
        case["caller_write_expected"] = has_z
        case["agrees"] = case["agrees"] and seen == has_z
        return case

    derived = {"Gen", "Degc", "Degw", "ACache", "Nkg", "NkgOther"}
    # E1 joined, caller rolls back: everything of g1 comes back, routed table and registry row included
    base, post, ret, err = caller("z1", "rollback", lambda: e.erase_graph("g1"))
    caller_case("E1_joined_erase_caller_rollback", ("graph", "g1"), base, post, ret, err, count_graph(base.entries, "g1"),
                base.entries, False, "z1", note="joined_then commit=false: rows == base.rows")
    # E2 joined, caller commits: the erase is final, the caller's own write kept
    base, post, ret, err = caller("z2", "commit", lambda: e.erase_graph("g1"))
    caller_case("E2_joined_erase_caller_commit", ("graph", "g1"), base, post, ret, err, count_graph(base.entries, "g1"),
                erase_graph(base.entries, "g1"), True, "z2", skip=derived,
                note="joined_then commit=true: rows == effect(base + w); ^NKG/caches of the caller's write not compared")
    seed_e(e, cur)
    # E3 joined, the erase fails (an over-long ID in the list), the caller commits: nothing erased, the caller's write kept
    long_id = "L" * 700
    base, post, ret, err = caller("z3", "commit", lambda: e._store.delete_nodes(["a", long_id], graph="g1"))
    c3 = caller_case("E3_joined_list_failure_caller_commit", ("ids", "g1", ["a", long_id]), base, post, ret, err, None,
                     base.entries, True, "z3", skip=derived,
                     note="joined_then fail=Some, commit=true: rows == base + w (the erase rolled back its own level)")
    c3["outcome_agrees"] = err is not None and ret is None
    c3["agrees"] = c3["outcome_agrees"] and c3["stores"]["agrees"] and c3["caller_write_after"]
    e.erase_graph("g9")
    # E4 not joined: 500 ids in chunk 1 commit, chunk 2 (an over-long ID) fails and raises
    ids = [f"n{i:04d}" for i in range(501)]
    e.bulk_create_nodes([{"id": i, "labels": ["P"]} for i in ids], graph="g1")
    pre = snapshot(c, ns)
    ret, err = None, None
    try:
        ret = e._store.delete_nodes(ids[:500] + [long_id, ids[500]], graph="g1")
    except Exception as x:  # noqa: BLE001
        err = f"{type(x).__name__}: {str(x)[:200]}"
    post = snapshot(c, ns)
    want = erase_ids(pre.entries, "g1", set(ids[:500]))   # list_erase: chunk 0 applied, chunk 1 failed
    c4 = record("E4_unjoined_chunk_commits", ("ids", "g1", "500 + [long, n0500]"), pre, post, None, err, None, want,
                skip=LIST_SKIP, note="list_erase fail_at=1: chunk 0 committed, chunk 1 rolled back, raised")
    c4["outcome_agrees"] = err is not None
    c4["agrees"] = c4["outcome_agrees"] and c4["stores"]["agrees"]
    # E5 the graph erase fails at the nodes DELETE (an application table's FK): every store as it was
    cur.execute("CREATE TABLE I65App.Ref (graph_id VARCHAR(256), node_id VARCHAR(256), "
                "CONSTRAINT fk_ref FOREIGN KEY (graph_id, node_id) REFERENCES Graph_KG.nodes (graph_id, node_id))")
    cur.execute("INSERT INTO I65App.Ref (graph_id, node_id) VALUES ('g1', 'a')")
    pre = snapshot(c, ns)
    ret, err = None, None
    try:
        ret = e.erase_graph("g1")
    except Exception as x:  # noqa: BLE001
        err = f"{type(x).__name__}: {str(x)[:300]}"
    post = snapshot(c, ns)
    c5 = record("E5_graph_erase_fails_fk", ("graph", "g1"), pre, post, ret, err, None, pre.entries,
                note="call fail=Some(late?): rows unchanged, raised after its own rollback")
    c5["outcome_agrees"] = err is not None and ret is None
    c5["agrees"] = c5["outcome_agrees"] and c5["stores"]["agrees"]
    cur.execute("DROP TABLE I65App.Ref")
    # E6 not joined: a from_connect engine's erase runs on its own Native API connection and survives the caller's rollback
    e2 = IRISGraphEngine.from_connect("127.0.0.1", runtime.PORT, ns, "_SYSTEM", "SYS", embedding_dimension=DIM)
    c2 = e2.conn
    base = snapshot(c, ns)
    c2.setAutoCommit(False)
    e2.create_node("z", ["P"], {}, graph="g9")
    ret, err = None, None
    try:
        ret = e2.erase_graph("g1")
    except Exception as x:  # noqa: BLE001
        err = f"{type(x).__name__}: {str(x)[:300]}"
    c2.rollback()
    c2.setAutoCommit(True)
    post = snapshot(c, ns)
    record("E6_dedicated_erase_survives_caller_rollback", ("graph", "g1"), base, post, ret, err,
           count_graph(base.entries, "g1"), erase_graph(base.entries, "g1"),
           note="dedicated_then commit=false: the erase stands, the caller's write is gone (q-plt-006)")
    c2.close()
    c.close()


# ====================================================================== detection
def detection():
    """(a) a changed decisive observed field; (b) transcription mutants against the live observations."""
    out = {}
    out["observed_field_changed"] = not diff(B1_STATE["expected"], B1_STATE["post"] + [E("Node", "g1", "a")])["agrees"]
    out["observed_other_graph_dropped"] = not diff(B1_STATE["expected"],
                                                   [x for x in B1_STATE["post"] if x != E("Node", "g2", "a")])["agrees"]
    # the frame-ignores-graph mutant: graph-scoped kinds of every graph go
    mutant = [x for x in B1_STATE["pre"] if x[0] not in GRAPH_KILL]
    out["mutant_frame_ignores_graph"] = not diff(mutant, B1_STATE["post"])["agrees"]
    c1 = next(x for x in CASES if x["case"] == "C1_prefix_acme_bar")
    out["mutant_count_ids_includes_edges"] = c1["returned"] != C1_STATE["mutant_count"]
    out["mutant_prefix_from_names"] = not diff(C1_STATE["mutant_expected"], C1_STATE["post"], LIST_SKIP)["agrees"]
    return out


B1_STATE, C1_STATE = {}, {}


def capture_states():
    """Re-derive the B1 and C1 inputs from the recorded cases (the snapshots are kept in memory by run())."""


_orig_run = run


def run(c, ns, name, ep, call, skip=(), note="", want=None):  # noqa: F811  (wrap to keep B1/C1 snapshots)
    pre, post, case = _orig_run(c, ns, name, ep, call, skip, note, want)
    if name == "B1_erase_graph_g1":
        B1_STATE.update(pre=pre.entries, post=post.entries, expected=expect(pre.entries, ep)[1])
    if name == "C1_prefix_acme_bar":
        d = prefix_sel(pre.entries, "g1", "acme|")
        names = {x[2] for x in pre.entries if x[2].startswith("acme|") and in_g(x, "g1")} | {x[4] for x in pre.entries
                                                                                              if x[4].startswith("acme|") and in_g(x, "g1")}
        C1_STATE.update(post=post.entries, mutant_expected=erase_ids(pre.entries, "g1", names),
                        mutant_count=count_ids(pre.entries, "g1", d) + sum(1 for x in pre.entries if incident(x, "g1", d)))
    return pre, post, case


# ====================================================================== main
def main():
    started = time.time()
    scenario_b()
    scenario_c()
    scenario_d()
    scenario_e()
    det = detection()
    mism = [x["case"] for x in CASES if not x.get("agrees")]
    pin = bc.pin_identity(PIN_DIR)
    for p in PRODUCT_FILES:
        want = subprocess.check_output(["git", "-C", str(bc.REPO), "rev-parse", f"{bc.PIN}:{p}"], text=True).strip()
        have = subprocess.check_output(["git", "hash-object", str(PIN_DIR / p)], text=True).strip()
        pin["files_equal_pin_blobs"][p] = want == have
        pin["all_equal"] &= want == have
    agrees = not mism and all(det.values()) and pin["all_equal"]
    verdict = "AGREES" if agrees else "DISAGREES"
    for x in CASES:
        print(f"  final {x['case']}: {'AGREES' if x.get('agrees') else 'DISAGREES'}")
    if os.environ.get("I65_DRY"):
        print(json.dumps({"verdict": verdict, "mism": mism, "det": det}, default=str))
        for x in CASES:
            if not x.get("agrees"):
                print(json.dumps(x, default=str)[:1500])
        return 0
    out = bc.write_receipt("erasure_stores", Path(__file__), {
        "verdict": verdict, "fixture": runtime.FIXTURE, "namespaces": ["I65B", "I65C", "I65D", "I65E"],
        "seconds": round(time.time() - started, 1), "live_cases": CASES, "live_mismatches": mism, "detection": det,
        "pin": pin,
        "real": "engine erase_graph/drop_graph/erase_all/delete_nodes_by_prefix/delete_node/bulk_delete_nodes/"
                "bulk_delete_adjacency/delete_edge, store delete_nodes/delete_edges, Graph.KG.Eraser.EraseGraph natively, "
                "GraphStores.Digest, bm25_search, from_connect engine, on IRIS",
        "scope": "one process per scenario; disclosed direct-SQL fixture rows (see module docstring); failed post-commit "
                 "DROP not injected; edge routes (kg_eemb_) not created; temporal aggregates not compared for list erases"})
    d = json.loads(out.read_text())
    for p in PRODUCT_FILES:
        d["inputs"][p] = bc.sha(bc.REPO / p)
    out.write_text(json.dumps(d, indent=2, sort_keys=True, default=str) + "\n")
    for x in CASES:
        print(f"  final {x['case']}: {'AGREES' if x.get('agrees') else 'DISAGREES'}")
    print(f"erasure_stores: {verdict}, {len(CASES)} cases ({len(mism)} disagree: {mism}), detection {det}; {out}")
    return 0 if verdict == "AGREES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
