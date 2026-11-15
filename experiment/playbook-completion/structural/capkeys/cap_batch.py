#!/usr/bin/env python3
"""§3.6 capacity: batch sizes, whole-window string readers and IRIS lock escalation (AUDITD, live).

    locks.sh iris python cap_batch.py OUT.json [case-prefix ...]

Cases (module):
  17 store adapter: get_nodes over 1,201 ids (its 500-id chunks, iris_sql_store.py:1112-1114) and write_nodes of
     1,201 nodes; every id exactly once.
  08 Cypher UNWIND of 3,000 rows: all created; and the same with one bad row last: all or nothing (USER_GUIDE.md:266-271).
  06 store_embeddings of 2,000 vectors: 2,000 rows.
  04 bulk_create_edges of 5,000 edges in a named graph: adjacency equals rows (verify_graph).
  15 40,000 temporal edges in the default graph: prov_export, prov_as_dict(one edge), prov_export_from_cypher; and
     get_edges_in_window (documented one-string cap) / iter_edges_in_window (paged) as the module-05 reference.
  03 lock escalation: a caller transaction holding 1,500 create_node inserts (> IRIS's default lock threshold of
     1,000 row locks per table) and, while it is open, a second process's create_node of another node: its
     answer, its wait, and whether its node exists after the first commits; control with 200 inserts. The lock
     table is read (^$LOCK, read only) while the transaction is open.
  13 redaction of 1,100 revisions in one batch while another tenant commits: the other tenant's commit latencies
     and errors during the redaction; control with batch_size 50.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from keys import call, keys_check  # noqa: E402

from iris_vector_graph.ledger import Changeset  # noqa: E402

TS0 = 1_700_000_000


def lock_table(pattern):
    out = lib.session(' set n="" for  { set n=$order(^$LOCK(n)) quit:n=""  if n[' + json.dumps(pattern) +
                      ' { write $c(30),"LK|",n,"|",$get(^$LOCK(n,"MODE")),"|",$get(^$LOCK(n,"OWNER")),! } }'
                      ' write $c(30),"LKEND|",! halt\n')
    return [x.split("|", 1)[1] for x in lib.marked(out, "LK")][:40], bool(lib.marked(out, "LKEND"))


def case(label, module, fn):
    c = lib.conn()
    t0 = time.time()
    r = {"case": label, "module": module}
    try:
        lib.reset(c)
        eng = lib.engine(c)
        r.update(fn(c, eng))
    except Exception:  # noqa: BLE001
        r["harness_error"] = traceback.format_exc()[-1500:]
    finally:
        try:
            c.conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        try:
            lib.reset(c)
        except Exception:  # noqa: BLE001
            pass
        c.close()
    r["secs"] = round(time.time() - t0, 2)
    print(json.dumps(r, default=str)[:2500], flush=True)
    return r


def b17_store(c, e):
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    st = IRISGraphStore(c.conn, namespace=lib.NS)
    ids = [f"sb:{i:05d}" for i in range(1201)]
    w = st.write_nodes([{"id": i, "labels": ["A"], "properties": {"k": i}} for i in ids])
    rows = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'sb:'")[0][0]
    g = st.get_nodes(ids)
    got = []
    for row in g.rows:
        d = row if isinstance(row, dict) else dict(zip(g.columns, row))
        got.append(str(d.get("id") or d.get("node_id")))
    return {"write_error": w.error, "rows": rows, "get_error": g.error, "returned": len(got), "distinct": len(set(got)),
            "missing": sorted(set(ids) - set(got))[:5], "holds": w.error is None and rows == 1201 and sorted(set(got)) == ids and len(got) == 1201}


def b08_unwind(c, e):
    rows = [{"id": f"uw:{i}"} for i in range(3000)]
    r1 = e.execute_cypher("UNWIND $rows AS r CREATE (n:U {id: r.id})", {"rows": rows})
    n1 = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'uw:'")[0][0]
    bad = [{"id": f"ub:{i}", "v": "x"} for i in range(2999)] + [{"id": "ub:last", "v": "y" * 64001}]
    try:
        r2 = e.execute_cypher("UNWIND $rows AS r CREATE (n:U {id: r.id, v: r.v})", {"rows": bad})
        err2 = str(r2.error)[:200] if r2.error else None
    except Exception as ex:  # noqa: BLE001
        err2 = f"raised {type(ex).__name__}: {str(ex)[:200]}"
    try:
        c.conn.rollback()
    except Exception:  # noqa: BLE001
        pass
    n2 = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'ub:'")[0][0]
    p2 = c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE s %STARTSWITH 'ub:'")[0][0]
    return {"unwind_3000_error": str(r1.error)[:200] if r1.error else None, "created": n1,
            "bad_last_row_error": err2, "created_with_bad_row": n2, "props_with_bad_row": p2,
            "holds": r1.error is None and n1 == 3000 and err2 is not None and n2 == 0 and p2 == 0}


def b06_vectors(c, e):
    ids = [f"vb:{i}" for i in range(2000)]
    e.bulk_create_nodes([{"id": i} for i in ids])
    ok = call(lambda: e.store_embeddings([{"node_id": i, "embedding": [float(k % 7), 1.0, 0.5, float(k % 3)]} for k, i in enumerate(ids)]))
    n = c.sql("SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings WHERE node_id %STARTSWITH 'vb:'")[0][0]
    return {"store_embeddings": ok, "rows": n, "holds": ok["ok"] and n == 2000}


def b04_bulk_edges(c, e):
    n = 5000
    nodes = [{"id": f"eb:{i}"} for i in range(n + 1)]
    e.bulk_create_nodes(nodes, graph="ebg")
    k = e.bulk_create_edges([{"source_id": f"eb:{i}", "predicate": "R", "target_id": f"eb:{i + 1}"} for i in range(n)], graph="ebg")
    v = e.verify_graph(graph="ebg")
    kc = keys_check(c)
    return {"bulk_create_edges": k, "verify_ok": v.get("ok"), "verify_counts": v.get("counts"),
            "key_violations": kc["violations"], "holds": k == n and bool(v.get("ok")) and not kc["violations"]}


def b15_prov(c, e, pad=""):
    n = 40_000
    nodes = [{"id": f"pv:{pad}{i}"} for i in range(200)]
    e.bulk_create_nodes(nodes)
    edges = [{"source": f"pv:{pad}{i % 200}", "predicate": "ACT", "target": f"pv:{pad}{(i * 7 + 1) % 200}", "timestamp": TS0 + i}
             for i in range(n)]
    t0 = time.time()
    w = call(lambda: e.bulk_create_edges_temporal(edges))
    out = {"temporal_written": w, "write_secs": round(time.time() - t0, 1)}
    out["05 get_edges_in_window (documented cap)"] = call(lambda: len(e.get_edges_in_window(start=TS0, end=TS0 + n)))
    out["05 iter_edges_in_window (paged)"] = call(lambda: sum(1 for _ in e.iter_edges_in_window(start=TS0, end=TS0 + n)))
    with tempfile.TemporaryDirectory() as d:
        out["15 prov_export whole window"] = call(lambda: e.prov_export(str(Path(d) / "a.ttl")))
        out["15 prov_export one-second window"] = call(lambda: e.prov_export(str(Path(d) / "b.ttl"), ts_start=TS0 + 5, ts_end=TS0 + 5))
        one = f"pv:{pad}5|ACT|pv:{pad}{(5 * 7 + 1) % 200}|{TS0 + 5}"
        out["15 prov_as_dict(one edge)"] = call(lambda: e.prov_as_dict(one))
        out["15 prov_export_from_cypher(one node)"] = call(lambda: e.prov_export_from_cypher(f"MATCH (n {{id: 'pv:{pad}5'}}) RETURN n.id", str(Path(d) / "c.ttl")))
    small = {k: v for k, v in out.items() if k.startswith("15")}
    out["holds"] = all(v.get("ok") for v in small.values())
    return out


def l03_escalation(n_rows):
    def f(c, e):
        out = {"rows_in_open_txn": n_rows}
        a = lib.conn()
        b = lib.conn()
        try:
            ea, eb = lib.engine(a), lib.engine(b)
            a.conn.setAutoCommit(False)
            t0 = time.time()
            for i in range(n_rows):
                ea.create_node(f"le:{i}")
            out["a_insert_secs"] = round(time.time() - t0, 1)
            out["a_tlevel"] = a.sql("SELECT $TLEVEL")[0][0]
            locks, complete = lock_table("t52S")
            out["lock_table_while_open"] = locks
            out["lock_table_read_complete"] = complete
            out["table_level_lock_on_nodes"] = any(x.split("|")[0] in ('^t52S.XCFT.1', '^["^^/usr/irissys/mgr/auditd/"]t52S.XCFT.1')
                                                   for x in locks)
            res = {}

            def bw():
                t1 = time.time()
                try:
                    res["answer"] = eb.create_node("le:b")
                except Exception as ex:  # noqa: BLE001
                    res["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
                res["wait_secs"] = round(time.time() - t1, 2)
            th = threading.Thread(target=bw)
            th.start()
            th.join(timeout=40)
            out["b_finished_while_a_open"] = not th.is_alive()
            a.conn.commit()
            th.join(timeout=60)
            out["b"] = res
            out["a_committed_rows"] = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'le:' AND node_id <> 'le:b'")[0][0]
            out["b_row_exists"] = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'le:b'")[0][0]
            ans = res.get("answer")
            out["b_answer_matches_store"] = (ans is True and out["b_row_exists"] == 1) or (ans is not True and out["b_row_exists"] == 0)
        finally:
            for x in (a, b):
                try:
                    x.conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
                x.close()
        out["holds"] = out.get("b_answer_matches_store") is True
        return out
    return f


def cs(msg, idem=None):
    return Changeset(actor="audit:structural", actor_type="ingest", message=msg, idempotency_key=idem)


def l13_redaction(batch):
    def f(c, e):
        led = e.ledger
        led.enable()
        c.conn.commit()
        n = 1100
        t0 = time.time()
        for i in range(n):
            ch = cs(f"ta {i}")
            ch.create_node(f"ta|{i}")
            led.commit(ch)
        c.conn.commit()
        out = {"revisions": n, "setup_secs": round(time.time() - t0, 1), "batch_size": batch}
        c.call("Graph.KG.Eraser", "EraseNodes", "", "ta|")
        c.conn.commit()
        red = {}
        stop = threading.Event()
        lat, errs = [], []

        def redactor():
            x = lib.conn()
            try:
                t1 = time.time()
                red["receipt"] = str(lib.engine(x).ledger.redact(prefix="ta", batch_size=batch))[:300]
                red["secs"] = round(time.time() - t1, 2)
            except Exception as ex:  # noqa: BLE001
                red["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
            finally:
                stop.set()
                x.close()

        def committer():
            y = lib.conn()
            try:
                ly = lib.engine(y).ledger
                k = 0
                while not stop.is_set() and k < 400:
                    t2 = time.time()
                    try:
                        ch = cs(f"tb {k}")
                        ch.create_node(f"tb|{k}")
                        ly.commit(ch)
                        y.conn.commit()
                        lat.append(round(time.time() - t2, 3))
                    except Exception as ex:  # noqa: BLE001
                        errs.append(f"{type(ex).__name__}: {str(ex)[:160]}")
                    k += 1
            finally:
                y.close()
        tc = threading.Thread(target=committer)
        tr = threading.Thread(target=redactor)
        tc.start()
        time.sleep(0.3)
        tr.start()
        tr.join(timeout=600)
        stop.set()
        tc.join(timeout=120)
        out["redaction"] = red
        out["other_tenant_commits"] = len(lat)
        out["other_tenant_max_latency_s"] = max(lat) if lat else None
        out["other_tenant_errors"] = errs[:5]
        out["other_tenant_error_count"] = len(errs)
        out["holds"] = "error" not in red and not errs
        return out
    return f


CASES = [
    ("17-store-1201-ids", "17", b17_store),
    ("08-unwind-3000", "08", b08_unwind),
    ("06-store_embeddings-2000", "06", b06_vectors),
    ("04-bulk_create_edges-5000", "04", b04_bulk_edges),
    ("15-prov-40000-temporal-edges", "15", b15_prov),
    ("15-prov-long-ids-40000-temporal-edges", "15", lambda c, e: b15_prov(c, e, pad="x" * 40)),
    ("03-lock-escalation-control-200", "03", l03_escalation(200)),
    ("03-lock-escalation-1500", "03", l03_escalation(1500)),
    ("13-redaction-batch-50-control", "13", l13_redaction(50)),
    ("13-redaction-one-batch-1100", "13", l13_redaction(100_000)),
]


def main() -> int:
    outp = Path(sys.argv[1])
    sel = sys.argv[2:]
    res = []
    for label, module, fn in CASES:
        if sel and not any(label.startswith(s) for s in sel):
            continue
        res.append(case(label, module, fn))
        lib.dump(outp, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
