#!/usr/bin/env python3
"""§3.4 declared reads, follow-up: the non-interference oracle (reads2/ni_base.py, a copy of structural/reads/
noninterference.py) over the read/both entry points structural/reads/cells.json left unchecked.

    locks.sh iris timeout 1500 python ni2.py --modules 12,13 --out FILE
    locks.sh iris timeout 600  python ni2.py --self-test --out FILE

Same oracle: base state, the action twice (stable), each perturbation OUTSIDE the declared footprint (answer must not
change), an INSIDE perturbation (should change). For writers whose read part is a guard, the answer is the call's
outcome and the target graph's state afterwards (rows of the four content tables in that graph, its ^KG out/label
leaves). Entry points that read no store are justified statically in static.json, not here.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "live"))
import lib  # noqa: E402
import ni_base as NI  # noqa: E402

G1, G2, T0 = NI.G1, NI.G2, NI.T0
C, E, put, hsql, raw, mask = NI.C, NI.E, NI.put, NI.hsql, NI.raw, NI.mask
TMP = lib.OUT / "reads2" / "tmp"
SERVER_A, SERVER_B = "/tmp/ivgauditd-rd2-a.txt", "/tmp/ivgauditd-rd2-b.txt"


def tmpfile(suffix):
    TMP.mkdir(parents=True, exist_ok=True)
    return str(TMP / f"out-{time.time_ns()}{suffix}")


NI.tmpfile = tmpfile          # the copied helpers write their scratch files under reads2, not reads


def gstate(c, g):
    """The target graph's state: its rows in the four content tables and its ^KG out / label leaves."""
    gg = g or ""
    out = {}
    for t, cols in (("nodes", "node_id"), ("rdf_edges", "s, p, o_id, ekey"), ("rdf_labels", "s, label"),
                    ("rdf_props", 's, "key", val')):
        # %IGNOREINDEX *: the master map, so rows a %NOINDEX load wrote are seen (premise P-0304)
        out[t] = sorted(list(map(str, r)) for r in hsql(c, f"SELECT {cols} FROM %IGNOREINDEX * Graph_KG.{t} WHERE COALESCE(graph_id,'') = ?", gg))
    key = 0 if not g else g
    leaves = []
    for d in ("out", "label"):
        if int(c.o.isDefined("^KG", d, key)):
            for a, _ in c.o.iterator("^KG", d, key).items():
                for b, _ in c.o.iterator("^KG", d, key, a).items():
                    if d == "out":
                        for o, _ in c.o.iterator("^KG", d, key, a, b).items():
                            leaves.append([d, str(a), str(b), str(o)])
                    else:
                        leaves.append([d, str(a), str(b)])
    out["kg"] = sorted(leaves)
    return out


TIMING = ("elapsed", "_seconds", "seconds", "_ms", "duration")


def untimed(x):
    if isinstance(x, dict):
        return {k: untimed(v) for k, v in x.items() if not any(s in str(k) for s in TIMING) and not str(k).endswith("_s")}
    if isinstance(x, list):
        return [untimed(v) for v in x]
    return x


def writer(fn, g=G1):
    """Answer of a writer: its outcome (timings dropped) and the target graph's state afterwards."""
    def f(e, c):
        try:
            r = untimed(raw(fn(e, c)))
            err = None
        except Exception as ex:  # noqa: BLE001
            r, err = None, f"{type(ex).__name__}"
        try:
            c.conn.commit()
        except Exception:  # noqa: BLE001
            pass
        return {"result": r, "error": err, "state": gstate(c, g)}
    return f


def other_graph_noise(g=G1):
    return NI.other_graphs(g)


# ------------------------------------------------------------------------------------------------ 12
def erase_edges_call(e, c):
    n = int(c.call("Graph.KG.Eraser", "EraseEdges", G1, json.dumps([{"s": "a", "p": "R", "o": "b"}])))
    c.conn.commit()
    return {"n": n, "state": gstate(c, G1)}


def scratch(e, c):
    c.o.set("x", "^IVGAuditDRd2X", "k")


SCRATCH_SEEN = []


def erase_all_call(e, c):
    present_before = bool(int(c.o.isDefined("^IVGAuditDRd2X")))
    n = int(c.call("Graph.KG.Eraser", "EraseAll"))
    c.conn.commit()
    if present_before:
        SCRATCH_SEEN.append(c.o.get("^IVGAuditDRd2X", "k"))
    c.o.kill("^IVGAuditDRd2X")
    return {"n": n}


# ------------------------------------------------------------------------------------------------ 13
def ledger_two_records_base(e, c):
    NI.ledger_base(e, c)
    c.conn.commit()
    e.delete_nodes_by_prefix("t1|")


def stop_resume_call(e, c):
    r1 = e.ledger.redact(prefix="t1", batch_size=1, max_batches=1)
    c.conn.commit()
    r2 = e.ledger.redact(prefix="t1")
    c.conn.commit()
    return {"first": {"complete": raw(r1).get("complete"), "batches": raw(r1).get("batches")}, "final": NI.receipt(r2)}


def paused_redaction(e, c):
    e.delete_nodes_by_prefix("t1|")
    c.conn.commit()
    e.ledger.redact(prefix="t1", batch_size=1, max_batches=1)


def in_progress_call(e, c):
    r = e.ledger.redaction_in_progress()
    return None if r is None else {"in_progress": True, "keys": sorted(r)}


# ------------------------------------------------------------------------------------------------ 14
def two_alice_revs(e):
    page = e.ledger.history(actor="alice", limit=10)
    revs = getattr(page, "revisions", None) or getattr(page, "items", None) or list(page)
    return [NI.rev_id(r) for r in revs]


def l14_base(e, c):
    NI.ledger_base(e, c)
    c.conn.commit()
    NI.ledger_inside(e, c)


def diff_call(e, c):
    ids = two_alice_revs(e)
    d = e.ledger.diff(ids[0], ids[1])
    return NI.canon(NI.strip_rev(raw(d)))


def l14_later_noise(e, c):
    NI.ledger_noise_tenant(e, c)


def l14_inside(e, c):
    from iris_vector_graph.ledger import Changeset
    ch = Changeset(actor="alice", actor_type="ingest", message="alice third", correlation_id="corrA")
    ch.set_property("t1|b", "k", "v6")
    e.ledger.commit(ch)


def export_recon_call(e, c):
    ids = two_alice_revs(e)
    p = tmpfile(".ndjson")
    e.ledger.export_reconstruction(ids[0], p)
    lines = NI.file_lines(p)
    Path(p).unlink(missing_ok=True)
    return lines


def alice_seq(e):
    r = NI.first_rev(e)
    return int(getattr(r, "seq", None) or raw(r)["seq"])


def records_page_call(e, c):
    head1 = alice_seq(e)
    cur = e.conn.cursor()
    try:
        cur.execute("SELECT * FROM Graph_KG.ledger_records(?, ?, ?, ?)", [1, head1, 1, 100])
        rows = [list(map(str, r)) for r in cur.fetchall()]
    finally:
        cur.close()
    return NI.mask(rows)


def canonical_call(e, c):
    seq = alice_seq(e)
    return [str(c.call("Graph.KG.Ledger", "CanonicalRecord", seq, i)) for i in (1, 2, 3)]


def pcp_base(e, c):
    NI.ledger_base(e, c)


def pcp_call(e, c):
    from iris_vector_graph.ledger import Changeset
    ch = Changeset(actor="alice", actor_type="ingest", message="pcp", post_commit_properties={"t1|a": {"pc": "v1"}})
    ch.set_property("t1|a", "k", "v3")
    r = e.ledger.commit(ch)
    c.conn.commit()
    return {"applied": r.post_commit_applied, "error": r.post_commit_error,
            "default_rows": sorted(map(list, hsql(c, "SELECT \"key\", val FROM Graph_KG.rdf_props WHERE s = 't1|a' AND COALESCE(graph_id,'') = ''"))),
            "g2_row_untouched": [r[0] for r in hsql(c, "SELECT val FROM Graph_KG.rdf_props WHERE s = 't1|a' AND graph_id = ? AND \"key\" = 'pc'", G2)] in ([], ["g2value"])}


def pcp_outside(e, c):
    put(e, G2, {"t1|a": (["N"], {"pc": "g2value", "k": "v9"})}, [])


def pcp_outside_noise_only(e, c):
    NI.ledger_noise_tenant(e, c)


# ------------------------------------------------------------------------------------------------ 18
def archive_base(e, c):
    put(e, G1, NI.BASE_NODES, NI.BASE_EDGES)
    c.conn.commit()
    p = TMP / "fixed-archive.zip"
    TMP.mkdir(parents=True, exist_ok=True)
    p.unlink(missing_ok=True)
    e.save_snapshot(str(p))


def snapshot_info_call(e, c):
    from iris_vector_graph.engine import IRISGraphEngine
    d = raw(IRISGraphEngine.snapshot_info(str(TMP / "fixed-archive.zip")))
    d = NI.mask(d)
    def drop(x):
        if isinstance(x, dict):
            return {k: drop(v) for k, v in x.items() if k not in ("snapshot_ts", "created_ts")}
        if isinstance(x, list):
            return [drop(v) for v in x]
        return x
    return drop(d)


def admin_snapshot_call(e, c):
    import os
    import zipfile
    import hashlib
    from starlette.testclient import TestClient
    import iris_vector_graph.cypher_api as api
    d = TMP / f"admin-{time.time_ns()}"
    d.mkdir(parents=True, exist_ok=True)
    os.environ["IVG_SNAPSHOT_DIR"] = str(d)
    api._engine_cache = lib.engine(c)
    try:
        with TestClient(api.app) as tc:
            r = tc.post("/admin/snapshot")
        body = r.json()
    finally:
        api._engine_cache = None
    out = {"status": r.status_code, "keys": sorted(body)}
    p = body.get("path")
    if p and Path(p).exists():
        members = {}
        with zipfile.ZipFile(p) as z:
            for n in sorted(z.namelist()):
                if n.endswith("metadata.json"):
                    continue
                data = z.read(n)
                if n.endswith(".ndjson"):
                    lines = []
                    for ln in data.decode("utf-8", "replace").splitlines():
                        try:
                            lines.append(json.dumps(NI.mask(NI._drop_ts(json.loads(ln))), sort_keys=True))
                        except ValueError:
                            lines.append(ln)
                    data = "\n".join(sorted(lines)).encode()
                members[n] = hashlib.sha256(data).hexdigest()[:16]
        out.update({f"member:{k}": v for k, v in members.items()})
        Path(p).unlink(missing_ok=True)
    return out


def vecidx_base(e, c):
    e.vec_create_index("rd2a", 4)
    e.vec_insert("rd2a", "d1", [1.0, 0.0, 0.0, 0.0])


def vecidx_outside(e, c):
    e.vec_create_index("rd2b", 4)
    e.vec_insert("rd2b", "d1", [0.0, 1.0, 0.0, 0.0])
    e.vec_insert("rd2b", "d2", [0.0, 0.0, 1.0, 0.0])
    put(e, G1, NI.BASE_NODES, NI.BASE_EDGES)


def nodevalue_call(e, c):
    return [str(c.call("Graph.KG.Snapshot", "NodeValueJSON", "^VecIdx", json.dumps(s)))
            for s in (["rd2a", "meta", "count"], ["rd2a", "cfg", "dim"], ["rd2a", "vec", "d1"])]


def remove_server_files():
    import os
    import subprocess
    subprocess.run(["docker", "exec", os.environ["IVG_TEST_CONTAINER"], "rm", "-f", SERVER_A, SERVER_B],
                   capture_output=True, timeout=60)


def files_base(e, c):
    remove_server_files()
    c.o.classMethodVoid("Graph.KG.Snapshot", "WriteFileChunk", SERVER_A, "hello-a", 0)


def files_outside(e, c):
    c.o.classMethodVoid("Graph.KG.Snapshot", "WriteFileChunk", SERVER_B, "other-b-longer", 0)
    put(e, G1, NI.BASE_NODES, NI.BASE_EDGES)


def files_inside(e, c):
    c.o.classMethodVoid("Graph.KG.Snapshot", "WriteFileChunk", SERVER_A, "-more", 1)


def files_call(e, c):
    p = SERVER_A
    out = {"exists": int(c.call("Graph.KG.Snapshot", "FileExists", p)),
           "size": int(c.call("Graph.KG.Snapshot", "GetFileSize", p)),
           "chunk": str(c.call("Graph.KG.Snapshot", "ReadFileChunk", p, 0, 1000))}
    remove_server_files()
    return out


# ------------------------------------------------------------------------------------------------ 03
def g1_endpoints(e, c):
    for n in ("a", "b", "c"):
        e.create_node(n, labels=["L"], properties={"k": "v1"}, graph=G1)
    e.create_edge("a", "R", "b", graph=G1)


def bulkloader(c, graph=G1):
    from iris_vector_graph.bulk_loader import BulkLoader
    return BulkLoader(c.conn, graph=graph)


def load_then_rebuild(method, *args):
    """BulkLoader's documented use: load, then rebuild_all_indices (bulk_loader.py:393-395 'Call rebuild_all_indices()
    after loading'), so its %NOINDEX rows are visible to indexed reads and to the eraser of the next variant."""
    def f(e, c):
        bl = bulkloader(c)
        r = getattr(bl, method)(*args)
        bl.rebuild_all_indices()
        return r
    return f


def nx_graph():
    import networkx as nx
    G = nx.DiGraph()
    G.add_node("a", namespace="L", k="v1")
    G.add_node("n2", namespace="L")
    G.add_edge("a", "n2")
    return G


def bls_call(e, c):
    with e.bulk_load_session() as s:
        s.add_nodes([{"id": "n2", "labels": ["L"]}, {"id": "a", "labels": ["Q"]}])
        s.add_edges([("a", "n2")], predicate="R")
    return {k: v for k, v in raw(s.stats).items() if "time" not in k and "elapsed" not in k}


def missing_rows_call(e, c):
    from iris_vector_graph._batch_check import missing_rows
    cur = e.conn.cursor()
    try:
        return missing_rows(cur, "Graph_KG.nodes", ["graph_id", "node_id"], [(G1, "a"), (G1, "zz"), (G1, "c")], e.conn)
    finally:
        cur.close()


def dictionary_call(e, c):
    from iris_vector_graph._dictionary import compiled_class_exists, compiled_method_exists
    return {"cls": compiled_class_exists(e.conn, "Graph.KG.Eraser"), "nocls": compiled_class_exists(e.conn, "Graph.KG.NoSuchRd2"),
            "meth": compiled_method_exists(e.conn, "Graph.KG.Eraser", "EraseAll"),
            "nometh": compiled_method_exists(e.conn, "Graph.KG.Eraser", "NoSuchRd2")}


def layout_call(e, c):
    v = c.call("Graph.KG.PropWrite", "Layout", "Graph_KG.rdf_props")
    return str(v)


# ------------------------------------------------------------------------------------------------ 11
def l11_base(e, c):
    NI.ledger_base(e, c)


def l11_noise(e, c):
    NI.ledger_noise_tenant(e, c)
    NI.ledger_noise_bypass_other_graph(e, c)


def cm(cls, meth, *args):
    return lambda e, c: str(c.call(cls, meth, *args))


def masked_cm(cls, meth, *args):
    return lambda e, c: NI.mask(NI.strip_rev(json.loads(str(c.call(cls, meth, *args)))))


def seqof_call(e, c):
    rid = NI.rev_id(NI.first_rev(e))
    return json.loads(str(c.call("Graph.KG.Ledger", "SeqOf", rid)))


def stmt_call(e, c):
    return str(c.call("Graph.KG.Ledger", "StmtForTuple", "t1|a", "R", "t1|b", ""))


def _edge_id(c, g):
    r = hsql(c, "SELECT edge_id FROM Graph_KG.rdf_edges WHERE s = 't1|a' AND p = 'R' AND o_id = 't1|b' AND COALESCE(graph_id,'') = ?", g)
    return str(r[0][0]) if r else ""


def find_edge_call(e, c):
    got = str(c.call("Graph.KG.LedgerApply", "FindEdge", "Graph_KG", "t1|a", "R", "t1|b", "", ""))
    return {"found": got != "", "is_the_default_graph_row": got == _edge_id(c, "")}


def find_edge_g2_call(e, c):
    got = str(c.call("Graph.KG.LedgerApply", "FindEdge", "Graph_KG", "t1|a", "R", "t1|b", G2, ""))
    return {"found": got != "", "is_the_g2_row": got != "" and got == _edge_id(c, G2)}


def node_exists_call(e, c):
    return {"t1|a": int(c.call("Graph.KG.LedgerApply", "NodeExists", "Graph_KG", "t1|a")),
            "solo": int(c.call("Graph.KG.LedgerApply", "NodeExists", "Graph_KG", "solo"))}


def solo_named(e, c):
    put(e, G2, {"solo": ([], {})}, [])


def snapshot_json_call(e, c):
    return json.loads(str(c.call("Graph.KG.LedgerApply", "NodeSnapshotJson", "Graph_KG", "t1|a")))


def stats_call(e, c):
    s = raw(e.ledger.stats())
    return untimed(s) if isinstance(s, dict) else s


def guard_call(e, c):
    from iris_vector_graph.ledger.guard import LedgerGuard
    try:
        LedgerGuard(e).check_structural_write("create_node")
        return "allowed"
    except Exception as ex:  # noqa: BLE001
        return f"refused {type(ex).__name__}"


def status_call(e, c):
    st = e.status()
    led = getattr(st, "ledger", None)
    d = raw(led)
    return NI.mask(d) if isinstance(d, dict) else d


def revision_update_call(e, c):
    out = {}
    for name, q in (("update", "UPDATE Graph_KG.ledger_revisions SET message = 'x' WHERE seq = 2"),
                    ("delete", "DELETE FROM Graph_KG.ledger_revisions WHERE seq = 2")):
        try:
            c.sql(q)
            out[name] = "accepted"
        except Exception as ex:  # noqa: BLE001
            msg = str(ex)
            out[name] = "refused " + ("trigger" if "trigger" in msg.lower() or "immutable" in msg.lower() or "-415" in msg or "-131" in msg else msg[:60])
        try:
            c.conn.rollback()
        except Exception:  # noqa: BLE001
            pass
    out["row"] = [list(map(str, r)) for r in hsql(c, "SELECT seq, actor, message FROM Graph_KG.ledger_revisions WHERE seq = 2")]
    return out


def sql_surface_call(e, c):
    return {"revisions": NI.mask([[str(x) for x in r] for r in c.sql("SELECT seq, kind, actor, message, op_count FROM Graph_KG.ledger_revisions ORDER BY seq")]),
            "stats_rows": len(c.sql("SELECT * FROM Graph_KG.ledger_stats"))}


def cases():
    L = []
    og = other_graph_noise(G1)
    # 12
    L.append(C("12", "EraseEdges(G1, [a-R-b]) [erase-edges-all]: count and G1 left", erase_edges_call, NI.base_in(G1),
               "G1's rows of the named edges and their ^KG entries (Eraser.cls:395-463; correspondence.json erase-edges-all reads ^KG(out), rdf_edges)",
               {"same edges in other graphs": og}, inside=lambda e, c: e.create_edge("c", "S", "b", graph=G1)))
    L.append(C("12", "EraseAll() [erase-edges-all]: count, a non-product global untouched", erase_all_call, NI.base_in(G1),
               "every graph's content and routes (Eraser.cls:709-845); nothing else",
               {"a non-product scratch global ^IVGAuditDRd2X": scratch}, inside=og))
    # 13
    L.append(C("13", "redact(prefix=t1, batch 1, max_batches=1) then redact(prefix=t1) [redact-stop-resume]",
               stop_resume_call, ledger_two_records_base,
               "target t1: its records, statements and the marker (LedgerRedact.cls:186-239; correspondence.json redact-stop-resume)",
               {"other tenants' history": NI.ledger_noise_tenant,
                "another tenant's ids live in a named graph (direct write)": lambda e, c: put(e, G2, {"t2|a": (["N"], {"k": "v9"})}, [])},
               inside=NI.redact_inside))
    L.append(C("13", "ledger.redaction_in_progress()", in_progress_call, NI.ledger_base,
               "^IVG.Ledger(redacting) (LedgerRedact InProgress; client.py:682-685)",
               {"other tenants' history": NI.ledger_noise_tenant, "content written directly in a named graph": NI.ledger_noise_bypass_other_graph},
               inside=paused_redaction, entry="IRISGraphEngine.ledger.redaction_in_progress"))
    # 14
    L.append(C("14", "ledger.diff(alice rev 1, alice rev 2)", diff_call, l14_base,
               "records of seqs in (rev1, rev2] (client.py:706-718)",
               {"later commits of other tenants": l14_later_noise, "tenant ids written directly in a named graph": NI.ledger_noise_bypass_other_graph},
               inside=l14_inside, note="inside: a later alice commit does not enter (rev1, rev2]; it shows only that the call reads its own range"))
    L.append(C("14", "ledger.export_reconstruction(alice rev 1)", export_recon_call, l14_base,
               "records of seqs 1..rev1 (client.py:730-739)",
               {"later commits of other tenants": l14_later_noise, "tenant ids written directly in a named graph": NI.ledger_noise_bypass_other_graph}))
    L.append(C("14", "SQL Graph_KG.ledger_records(1, alice's first seq, 1, 100) [Records page reader]", records_page_call, NI.ledger_base,
               "^IVG.Ledger(rec, seq) for seq in the range (Ledger.cls:613-652)",
               {"later commits of other tenants": NI.ledger_noise_tenant, "tenant ids written directly in a named graph": NI.ledger_noise_bypass_other_graph}))
    L.append(C("14", "Ledger.CanonicalRecord(alice's seq, 1..3)", canonical_call, NI.ledger_base,
               "^IVG.Ledger(rec, seq, ordinal) (Ledger.cls:572-611)",
               {"later commits of other tenants": NI.ledger_noise_tenant, "tenant ids written directly in a named graph": NI.ledger_noise_bypass_other_graph}))
    L.append(C("14", "commit with post_commit_properties {t1|a: {pc}}: applied and default-graph rows",
               pcp_call, pcp_base, "the default graph's rdf_props rows of t1|a, key pc (client.py:445-487: 'scoped to the default graph')",
               {"t1|a with key pc in a named graph": pcp_outside, "other tenants' history": pcp_outside_noise_only},
               inside=lambda e, c: e.store_node("t1|a", properties={"pc": "old"})))
    # 18
    L.append(C("18", "snapshot_info(archive) [reads only the archive]", snapshot_info_call, archive_base,
               "the archive file's metadata.json (snapshot.py:1051-1057: 'without touching the database')",
               {"database content changed after the archive was written": og}, inside=None))
    L.append(C("18", "POST /admin/snapshot (cypher_api, in-process): archive members", admin_snapshot_call, NI.base_in(G1),
               "the store plan, as save_snapshot (cypher_api.py:668-678 -> snapshot.py:797-1048)",
               {"an undeclared global (^IVGAuditDRdSnap scratch)": NI.scratch_global},
               inside=lambda e, c: e.create_node("q", graph=G1), project=True))
    L.append(C("18", "Snapshot.NodeValueJSON(^VecIdx, rd2a nodes)", nodevalue_call, vecidx_base,
               "the one vector-index node named (Snapshot.cls:79-84, 94-110: ^IVF/^PLAID/^VecIdx only)",
               {"another index and graph content": vecidx_outside},
               inside=lambda e, c: e.vec_insert("rd2a", "d2", [0.0, 1.0, 0.0, 0.0])))
    L.append(C("18", "Snapshot.FileExists/GetFileSize/ReadFileChunk(server file a)", files_call, files_base,
               "the named server file only (Snapshot.cls:37-77)",
               {"another server file and graph content": files_outside}, inside=files_inside))
    # 03 writers with a guard read: outcome and G1 state
    L.append(C("03", "bulk_create_edges([a-R-c], graph=G1)", writer(lambda e, c: e.bulk_create_edges([{"source_id": "a", "predicate": "R", "target_id": "c"}], graph=G1)),
               g1_endpoints, "G1's rows of a, c and the edge (nodes_edges.py:1873-2017)", {"same ids in other graphs": og},
               inside=lambda e, c: e.create_edge("a", "R", "c", graph=G1), entry="IRISGraphEngine.bulk_create_edges"))
    L.append(C("03", "bulk_create_nodes([a, n2], graph=G1)", writer(lambda e, c: e.bulk_create_nodes([{"id": "a", "labels": ["Q"]}, {"id": "n2"}], graph=G1)),
               g1_endpoints, "G1's rows of a, n2 (nodes_edges.py:1648-1871)", {"same ids in other graphs": og},
               inside=lambda e, c: e.create_node("n2", graph=G1), entry="IRISGraphEngine.bulk_create_nodes"))
    L.append(C("03", "bulk_ingest_edges([a-R-c]) [default graph]", writer(lambda e, c: e.bulk_ingest_edges([{"source_id": "a", "target_id": "c"}], predicate="R"), g=None),
               lambda e, c: g1_endpoints_default(e, c), "the default graph's rows of a, c and the edge (nodes_edges.py:2019-2132)",
               {"same ids in named graphs": other_graph_noise(None)}, inside=lambda e, c: e.create_edge("a", "R", "c"),
               entry="IRISGraphEngine.bulk_ingest_edges"))
    L.append(C("03", "delete_edge(a, R, b, graph=G1)", writer(lambda e, c: e.delete_edge("a", "R", "b", graph=G1)), g1_endpoints,
               "G1's edge a-R-b (nodes_edges.py:1382-1456)", {"same ids in other graphs": og},
               inside=lambda e, c: e.create_edge("b", "R", "a", graph=G1), entry="IRISGraphEngine.delete_edge"))
    L.append(C("03", "delete_node(b, graph=G1)", writer(lambda e, c: e.delete_node("b", graph=G1)), g1_endpoints,
               "G1's node b and its edges (nodes_edges.py:2227-2268)", {"same ids in other graphs": og},
               inside=lambda e, c: e.create_edge("c", "R", "b", graph=G1), entry="IRISGraphEngine.delete_node"))
    L.append(C("03", "bulk_delete_nodes([b, c], graph=G1)", writer(lambda e, c: e.bulk_delete_nodes(["b", "c"], graph=G1)), g1_endpoints,
               "G1's nodes b, c and their edges (nodes_edges.py:2270-2299)", {"same ids in other graphs": og},
               inside=lambda e, c: e.create_edge("c", "R", "a", graph=G1), entry="IRISGraphEngine.bulk_delete_nodes"))
    L.append(C("03", "store_edge(a, R, c, graph=G1)", writer(lambda e, c: e.store_edge("a", "R", "c", qualifiers={"w": "1"}, graph=G1)), g1_endpoints,
               "G1's rows of a, c and the edge (nodes_edges.py:2532-2588)", {"same ids in other graphs": og},
               inside=lambda e, c: e.create_edge("a", "R", "c", qualifiers={"w": "0"}, graph=G1), entry="IRISGraphEngine.store_edge"))
    L.append(C("03", "store_node(a, graph=G1)", writer(lambda e, c: e.store_node("a", properties={"k": "v5"}, labels=["Q"], graph=G1)), g1_endpoints,
               "G1's rows of a (nodes_edges.py:2393-2530)", {"same ids in other graphs": og},
               inside=lambda e, c: e.store_node("a", properties={"z": "9"}, graph=G1), entry="IRISGraphEngine.store_node"))
    L.append(C("03", "set_edge_weight(a, R, b, 2.5) [default graph]", writer(lambda e, c: e.set_edge_weight("a", "R", "b", 2.5), g=None),
               lambda e, c: g1_endpoints_default(e, c), "the default graph's edge a-R-b (nodes_edges.py:1306-1380)",
               {"same ids in named graphs": other_graph_noise(None)}, inside=lambda e, c: e.delete_edge("a", "R", "b"),
               entry="IRISGraphEngine.set_edge_weight"))
    L.append(C("03", "BulkLoader(graph=G1).load_nodes", writer(load_then_rebuild("load_nodes", [("a", {"namespace": "Q"}), ("n2", {"namespace": "L"})])),
               g1_endpoints, "G1's nodes rows (bulk_loader.py:182-199 _known_nodes_sql, scoped to the loader's graph)",
               {"same ids in other graphs": og}, inside=lambda e, c: e.create_node("n2", graph=G1),
               entry="iris_vector_graph.bulk_loader.BulkLoader.load_nodes"))
    L.append(C("03", "BulkLoader(graph=G1).load_edges", writer(load_then_rebuild("load_edges", [("a", "R", "c", None), ("a", "R", "b", None)])),
               g1_endpoints, "G1's nodes and edges rows (bulk_loader.py:417-440, graph-scoped scans)",
               {"same ids in other graphs": og}, inside=lambda e, c: e.create_edge("a", "R", "c", graph=G1),
               entry="iris_vector_graph.bulk_loader.BulkLoader.load_edges"))
    L.append(C("03", "BulkLoader(graph=G1).load_networkx", writer(load_then_rebuild("load_networkx", nx_graph())),
               g1_endpoints, "G1's nodes and edges rows, then BuildKG (bulk_loader.py:540-629)",
               {"same ids in other graphs": og}, inside=lambda e, c: e.create_node("n2", graph=G1),
               entry="iris_vector_graph.bulk_loader.BulkLoader.load_networkx"))
    L.append(C("03", "BulkLoader(graph=G1).build_graph_globals", writer(lambda e, c: bulkloader(c).build_graph_globals()),
               g1_endpoints, "BuildKG over every graph's rows; the answer is G1's ^KG (bulk_loader.py:512-538)",
               {"same ids in other graphs": og}, inside=lambda e, c: e.create_edge("b", "R", "c", graph=G1),
               entry="iris_vector_graph.bulk_loader.BulkLoader.build_graph_globals"))
    L.append(C("03", "erase_all(): count, a non-product global untouched", erase_all_call_engine, NI.base_in(G1),
               "every graph's content (nodes_edges.py:1565-1586 -> Eraser.EraseAll)",
               {"a non-product scratch global ^IVGAuditDRd2X": scratch}, inside=og, entry="IRISGraphEngine.erase_all"))
    L.append(C("03", "bulk_load_session(): add_nodes + add_edges [default graph]", writer(bls_call, g=None),
               lambda e, c: g1_endpoints_default(e, c), "the default graph's rows of the loaded ids (nodes_edges.py:332-502)",
               {"same ids in named graphs": other_graph_noise(None)}, inside=lambda e, c: e.create_node("n2"),
               entry="IRISGraphEngine.bulk_load_session"))
    L.append(C("03", "PropWrite.Layout(Graph_KG.rdf_props)", layout_call, NI.base_in(G1),
               "the class dictionary of the table's class (PropWrite.cls:66-100)", {"graph content in every graph": og}))
    L.append(C("03", "_batch_check.missing_rows(nodes, (G1,a),(G1,zz),(G1,c))", missing_rows_call, NI.base_in(G1),
               "nodes rows of the given ids, compared as (graph, id) (_batch_check.py:48-65)",
               {"the missing id zz in other graphs": lambda e, c: [put(e, x, {"zz": ([], {})}, []) for x in (None, G2)],
                "same ids in other graphs": og},
               inside=lambda e, c: e.create_node("zz", graph=G1)))
    L.append(C("03", "_dictionary.compiled_class_exists / compiled_method_exists", dictionary_call, NI.base_in(G1),
               "%Dictionary.CompiledClass / CompiledMethod rows of the names (_dictionary.py:40-64)", {"graph content in every graph": og}))
    # 11
    led_out = {"other tenants' commits and the tenant's ids written directly in a named graph": l11_noise}
    L.append(C("11", "Ledger.State()", cm("Graph.KG.Ledger", "State"), l11_base, "^IVG.Ledger(meta, state) (Ledger.cls:40-43)", led_out,
               inside=lambda e, c: e.ledger.disable()))
    L.append(C("11", "Ledger.Meta()", masked_cm("Graph.KG.Ledger", "Meta"), l11_base, "^IVG.Ledger(meta), (head), (idBySeq, head) (Ledger.cls:143-156)",
               {"content written directly in a named graph": NI.ledger_noise_bypass_other_graph}, inside=NI.ledger_noise_tenant))
    L.append(C("11", "Ledger.Head() (RevisionResponse/RevisionObj of the head)", masked_cm("Graph.KG.Ledger", "Head"), l11_base,
               "^IVG.Ledger(head) and that ledger_revisions row (Ledger.cls:85-120, 158-164)",
               {"content written directly in a named graph": NI.ledger_noise_bypass_other_graph}, inside=NI.ledger_noise_tenant))
    L.append(C("11", "Ledger.RevisionResponse(2, 0, '') (RevisionObj)", masked_cm("Graph.KG.Ledger", "RevisionResponse", 2, 0, ""), l11_base,
               "the ledger_revisions row of seq 2 (Ledger.cls:85-120)", led_out))
    L.append(C("11", "Ledger.SeqOf(alice's revision id)", seqof_call, l11_base, "^IVG.Ledger(revById, id) (Ledger.cls:166-174)", led_out))
    L.append(C("11", "Ledger.StmtForTuple(t1|a, R, t1|b, '')", stmt_call, l11_base, "^IVG.Ledger(tuple, s, p, o, default-graph key) (Ledger.cls:176-179)",
               {"the same tuple written directly in a named graph": NI.ledger_noise_bypass_other_graph, "other tenants' commits": NI.ledger_noise_tenant}))
    L.append(C("11", "LedgerApply.FindEdge(Graph_KG, t1|a, R, t1|b, '')", find_edge_call, l11_base,
               "the default graph's rdf_edges row of the tuple (LedgerApply.cls:144-157)",
               {"the same tuple written directly in a named graph": NI.ledger_noise_bypass_other_graph}))
    L.append(C("11", "LedgerApply.FindEdge(Graph_KG, t1|a, R, t1|b, G2)", find_edge_g2_call, l11_base,
               "graph G2's rdf_edges row of the tuple (LedgerApply.cls:144-157)",
               {"the same tuple in the default graph (ledger commit)": NI.ledger_noise_tenant},
               inside=NI.ledger_noise_bypass_other_graph))
    L.append(C("11", "LedgerApply.NodeExists(Graph_KG, t1|a / solo)", node_exists_call, l11_base,
               "graph-blind by design (LedgerApply.cls:91-93: 'NodeExists stays graph-blind on purpose'): nodes rows of the id in any graph",
               {"other tenants' commits": NI.ledger_noise_tenant}, inside=solo_named,
               note="a named-graph-only id makes the ledger's default-graph node ops act on it (F-1105); here only the declared graph-blind read is checked"))
    L.append(C("11", "LedgerApply.NodeSnapshotJson(Graph_KG, t1|a)", snapshot_json_call, l11_base,
               "the default graph's rdf_labels/rdf_props rows of the id (LedgerApply.cls:337-351)",
               {"the tenant's ids written directly in a named graph": NI.ledger_noise_bypass_other_graph, "other tenants' commits": NI.ledger_noise_tenant},
               inside=NI.ledger_inside))
    L.append(C("11", "GraphLedger.stats()", stats_call, l11_base, "ledger_stats and ^IVG.Ledger(meta) (client.py:542-577)",
               {"content written directly in a named graph": NI.ledger_noise_bypass_other_graph}, inside=NI.ledger_noise_tenant))
    L.append(C("11", "LedgerGuard.check_structural_write (strict off)", guard_call, l11_base,
               "^IVG.Ledger(meta) via Meta, %Dictionary.CompiledClass (guard.py:38-86)", led_out,
               inside=lambda e, c: e.ledger.set_strict(True)))
    L.append(C("11", "IRISGraphEngine.status().ledger", status_call, l11_base, "Ledger Meta and stats (_engine/ledger.py:40-69)",
               {"content written directly in a named graph": NI.ledger_noise_bypass_other_graph}, inside=NI.ledger_noise_tenant))
    L.append(C("11", "SQL UPDATE / DELETE of a ledger_revisions row [%Save(existing) / %DeleteId triggers]", revision_update_call, l11_base,
               "the row named; the triggers refuse (LedgerRevision.cls:77-123)", led_out))
    L.append(C("11", "SQL SELECT Graph_KG.ledger_revisions / ledger_stats", sql_surface_call, l11_base,
               "the two tables (LedgerRevision.cls:1-60, LedgerStats.cls:4-48)",
               {"content written directly in a named graph": NI.ledger_noise_bypass_other_graph}, inside=NI.ledger_noise_tenant))
    return L


def g1_endpoints_default(e, c):
    for n in ("a", "b", "c"):
        e.create_node(n, labels=["L"], properties={"k": "v1"})
    e.create_edge("a", "R", "b")


def erase_all_call_engine(e, c):
    present_before = bool(int(c.o.isDefined("^IVGAuditDRd2X")))
    n = e.erase_all()
    c.conn.commit()
    if present_before:
        SCRATCH_SEEN.append(c.o.get("^IVGAuditDRd2X", "k"))
    c.o.kill("^IVGAuditDRd2X")
    return {"n": n}


def main() -> int:
    out_p = Path(sys.argv[sys.argv.index("--out") + 1])
    c = lib.conn()
    info = {"engine": lib.version(c), "namespace": lib.NS}
    c.close()
    if "--self-test" in sys.argv:
        sys.argv = [sys.argv[0], "--self-test", "--out", str(out_p)]
        return NI.main()
    mods = sys.argv[sys.argv.index("--modules") + 1].split(",")
    sel = [x for x in cases() if x["module"] in mods]
    if "--only" in sys.argv:
        pat = sys.argv[sys.argv.index("--only") + 1]
        sel = [x for x in sel if pat in x["id"]]
    rs = []
    for x in sel:
        try:
            rs.append(NI.run_case(x))
        except Exception as ex:  # noqa: BLE001
            rs.append({"module": x["module"], "id": x["id"], "verdict": "harness-error",
                       "error": f"{type(ex).__name__}: {ex}", "trace": traceback.format_exc()[-1500:]})
            print(f"[{x['module']}] harness-error {x['id']}: {ex}", flush=True)
        finally:
            cc = lib.conn()
            try:
                cc.o.kill("^IVGAuditDRd2X")
                remove_server_files()
                try:
                    bulkloader(cc, None).rebuild_all_indices()   # %NOINDEX rows a failed variant left, made erasable
                except Exception:  # noqa: BLE001
                    pass
                ce = lib.engine(cc)
                for ix in ("rd2a", "rd2b"):
                    try:
                        ce.vec_drop(ix)
                    except Exception:  # noqa: BLE001
                        pass
                lib.reset(cc)
            finally:
                cc.close()
    summ = {}
    for r in rs:
        s = summ.setdefault(r["module"], {})
        s[r["verdict"]] = s.get(r["verdict"], 0) + 1
    lib.dump(out_p, {"info": info, "summary": summ, "cases": rs, "scratch_values_after_erase_all": SCRATCH_SEEN})
    print(json.dumps(summ), "scratch after EraseAll:", SCRATCH_SEEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
