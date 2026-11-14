"""Module 09 live checks on AUDITB (one lock hold; each part logs its own JSON under $RUN_DIR/breadth-b/live/).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 python \
        experiment/playbook-completion/live/breadth-b/09_live.py [part ...]

Parts (default: all, in this order):
  probe      gate facts; a hop read goes native in off and sync modes; $ZCRC(x,7) vs zlib.crc32 (P-0901)
  footprint  journal footprints of native reads (off/job/sync/parallel), Exec.Run plumbing, Gen.Mode, DropAll
  f0903      namespace compile mode "OFF" (not a mode) builds synchronously in the reader; control "off" builds nothing
  f0905      DropAll while a job build compiles: a broken entry $LB(class,,,"ok") and a surviving class
  f0901      two real plan shapes whose $ZCRC collide (birthday search over label names in IRIS), then a job-mode
             read pair: the entry of one shape marked ok for the class compiled from the other -> wrong answers
  f0902      two relationships whose $ZCRC($LB(src,p,dst,ekey),7) collide: the interpreter drops valid matches
  f0907      shadow mode on a tied ORDER BY (with and without LIMIT)
  f0909      native read inside an open caller transaction on an engine with a dedicated native connection
  f0904      P-0903 on Community 2026.1: after a failed sync build in a process, can it prepare new SQL?
  f0906      adjacency index facts of AUDITB (read only)
Everything is cleaned at the end: Gen.DropAll, ^IVG.CypherGen("mode"/"breaktest") killed, process mode cleared,
b09 rows deleted.
"""
import importlib.util
import json
import random
import subprocess
import sys
import time
import traceback
import zlib
from pathlib import Path

spec = importlib.util.spec_from_file_location("c09", Path(__file__).with_name("09_common.py"))
c09 = importlib.util.module_from_spec(spec); spec.loader.exec_module(c09)

PARTS = ["probe", "footprint", "f0903", "f0905", "f0901", "f0902", "f0907", "f0909", "f0904", "f0906"]
want = sys.argv[1:] or PARTS
RESULTS = {}


def mode(s, m):
    return str(s.c.call("Graph.KG.Cypher.Gen", "Mode", m))


def dropall(s):
    return str(s.c.call("Graph.KG.Cypher.Gen", "DropAll"))


def entry_status(s):
    return c09.plan_state(s.c)


def wait_settled(s, timeout=60.0):
    """Wait until no entry is pending (a job build finished) or the timeout passes."""
    t0 = time.time()
    st = entry_status(s)
    while time.time() - t0 < timeout:
        if not any(e["status"] == "pending" for e in st["entries"].values()):
            return st, round(time.time() - t0, 2)
        time.sleep(0.5)
        st = entry_status(s)
    return st, round(time.time() - t0, 2)


def walk1_label(s, cls, labels):
    """Which of `labels` the compiled class's Walk1 code names (from the class dictionary, a SQL read)."""
    try:
        rows = s.c.sql("SELECT Implementation FROM %Dictionary.MethodDefinition WHERE parent = ? AND Name = 'Walk1'", cls)
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}
    text = ""
    for (impl,) in rows:
        text = str(impl)
    return {lab: (lab in text) for lab in labels} | {"chars": len(text)}


def part_probe(s):
    out = {}
    eng = s.eng
    from iris_vector_graph.cypher.native_plan import native_gate
    out["gate"] = {"native_cypher": eng.native_cypher, "adjacency_indexed": eng._adjacency_indexed,
                   "privileges": eng._native_privileges(), "executor_current": eng._native_executor_current(),
                   "reason": native_gate(eng)}
    out["before"] = entry_status(s)
    eng.create_node("b09_a", labels=["B09A"], properties={"name": "a"})
    eng.create_node("b09_b1", labels=["B09X"], properties={"name": "b1"})
    eng.create_node("b09_b2", labels=["B09Y"], properties={"name": "b2"})
    eng.create_edge("b09_a", "B09R", "b09_b1")
    eng.create_edge("b09_a", "B09R", "b09_b2")
    q = "MATCH (a:B09A {id: 'b09_a'})-[:B09R]->(b:B09X) RETURN count(b) AS c"
    out["mode_off"] = mode(s, "off")
    n0 = c09.native_count(eng)
    out["read_off"] = c09.run(eng, q)
    out["native_after_off"] = c09.native_count(eng) - n0
    out["state_after_off"] = entry_status(s)
    out["mode_sync"] = mode(s, "sync")
    out["read_sync"] = c09.run(eng, q)
    out["state_after_sync"] = entry_status(s)
    out["read_sync_2"] = c09.run(eng, q)
    out["native_total"] = c09.native_count(eng) - n0
    samples = ["", "a", "hello", "IVG native plan", "b09_hub|B09T", "\x01\x02abc\xff"]
    script = "\n".join(' write $char(30),"CRC|' + str(i) + '|",$zcrc(' +
                       ("$char(" + ",".join(str(ord(ch)) for ch in smp) + ")" if smp else '""') + ',7),!'
                       for i, smp in enumerate(samples))
    o = c09.osession(script)
    got = {int(v.split("|")[0]): int(v.split("|")[1]) for v in c09.marked(o, "CRC")}
    out["zcrc_vs_zlib"] = [{"sample": repr(smp), "zcrc7": got.get(i), "zlib_crc32": zlib.crc32(smp.encode("latin-1")),
                            "equal": got.get(i) == zlib.crc32(smp.encode("latin-1"))} for i, smp in enumerate(samples)]
    mode(s, "")
    dropall(s)
    return out


def part_footprint(s):
    out = {}
    eng = s.eng
    for nid, lab in (("b09_fa", "B09FA"), ("b09_fb", "B09FB"), ("b09_fc", "B09FB")):
        eng.create_node(nid, labels=[lab], properties={"name": nid})
    eng.create_edge("b09_fa", "B09FR", "b09_fb")
    eng.create_edge("b09_fa", "B09FR", "b09_fc")
    dropall(s)

    def summarize(cap):
        return {"result": None if cap.result is None else (cap.result.get("rows") if isinstance(cap.result, dict) else str(cap.result)[:300]),
                "error": cap.error, "footprint": cap.footprint_json(), "txns": cap.txn_summary(s.smap),
                "outside_txn": cap.writes_outside_txn(s.smap)[:40], "records": len(cap.records), "seconds": round(cap.seconds, 3),
                "reader_pid": s.c.pid}
    q1 = "MATCH (a:B09FA {id: 'b09_fa'})-[:B09FR]->(b:B09FB) RETURN count(b) AS c"
    q2 = "MATCH (a:B09FA {id: 'b09_fa'})-[:B09FR]->(b:B09FB) RETURN b.name AS n ORDER BY b.name"
    q3 = "MATCH (a:B09FA)-[:B09FR]->(b:B09FB) RETURN count(b) AS c"
    mode(s, "off")
    n0 = c09.native_count(eng)
    out["read_off"] = summarize(c09.capture(s, lambda: c09.run(eng, q1)))
    out["read_off"]["native"] = c09.native_count(eng) - n0
    mode(s, "job")
    n0 = c09.native_count(eng)
    out["read_job_new_shape"] = summarize(c09.capture(s, lambda: c09.run(eng, q2), settle=4.0))
    out["read_job_new_shape"]["native"] = c09.native_count(eng) - n0
    out["read_job_new_shape"]["entries_after"] = entry_status(s)
    n0 = c09.native_count(eng)
    out["read_job_compiled"] = summarize(c09.capture(s, lambda: c09.run(eng, q2)))
    out["read_job_compiled"]["native"] = c09.native_count(eng) - n0
    mode(s, "sync")
    out["read_sync_new_shape"] = summarize(c09.capture(s, lambda: c09.run(eng, q1)))
    out["read_sync_new_shape"]["entries_after"] = entry_status(s)
    out["mode_set"] = summarize(c09.capture(s, lambda: mode(s, "sync")))
    out["exec_run_plumbing"] = summarize(c09.capture(s, lambda: s.c.call("Graph.KG.Cypher.Exec", "Run", json.dumps({"ops": [{"op": "range", "n": 3}]}), "{}")))
    out["gen_entries_read"] = summarize(c09.capture(s, lambda: s.c.call("Graph.KG.Cypher.Gen", "Entries")))
    # a read split among workers (native_parallel_min=0: always split where more than one CPU)
    mode(s, "off")
    eng.native_parallel_min = 0
    n0 = getattr(eng, "_native_parallel_runs", 0)
    out["read_parallel"] = summarize(c09.capture(s, lambda: c09.run(eng, q3), settle=1.0))
    out["read_parallel"]["parallel_runs"] = getattr(eng, "_native_parallel_runs", 0) - n0
    eng.native_parallel_min = 1500
    out["dropall"] = summarize(c09.capture(s, lambda: dropall(s)))
    out["entries_after_dropall"] = entry_status(s)
    mode(s, "")
    return out


def part_f0903(s):
    out = {}
    eng = s.eng
    for nid, lab in (("b09_ma", "B09MA"), ("b09_mb", "B09MB")):
        eng.create_node(nid, labels=[lab], properties={"name": nid})
    eng.create_edge("b09_ma", "B09MR", "b09_mb")
    dropall(s)
    mode(s, "")  # this process follows the namespace value
    out["namespace_mode_before"] = c09.gget(s.c, "mode", root="IVG.CypherGen")
    results = {}
    for i, val in enumerate(["off", "OFF", "none", "job"]):
        dropall(s)
        s.c.o.set(val, "IVG.CypherGen", "mode")
        eff = str(s.c.call("Graph.KG.Cypher.Gen", "Effective"))
        n0 = c09.native_count(eng)
        cap = c09.capture(s, lambda: c09.run(eng, f"MATCH (a:B09MA {{id: 'b09_ma'}})-[:B09MR]->(b:B09MB) RETURN b.name AS n{i}"))
        st = entry_status(s)
        results[val] = {"effective": eff, "read": cap.result, "native": c09.native_count(eng) - n0,
                        "entries_right_after_read": st, "footprint": cap.footprint_json(),
                        "reader_pid": s.c.pid}
        s.c.o.kill("IVG.CypherGen", "mode")
    out["by_namespace_value"] = results
    out["namespace_mode_after"] = c09.gget(s.c, "mode", root="IVG.CypherGen")
    dropall(s)
    return out


def part_f0905(s):
    out = {"attempts": []}
    eng = s.eng
    for nid, lab in (("b09_da", "B09DA"), ("b09_db", "B09DB")):
        eng.create_node(nid, labels=[lab], properties={"name": nid})
    eng.create_edge("b09_da", "B09DR", "b09_db")
    for attempt, delay in enumerate([0.0, 0.05, 0.15, 0.3, 0.6]):
        dropall(s)
        mode(s, "job")
        q = f"MATCH (a:B09DA {{id: 'b09_da'}})-[:B09DR]->(b:B09DB) RETURN b.name AS n{attempt}"
        r1 = c09.run(eng, q)
        time.sleep(delay)
        d = dropall(s)
        st, waited = wait_settled(s, 30)
        time.sleep(1.0)
        st = entry_status(s)
        broken = [h for h, e in st["entries"].items() if e["elements_defined"] != "11111"]
        rec = {"delay": delay, "read": r1, "dropall": d, "after": st, "broken_entries": broken}
        if broken or st["class_definitions"]:
            # the consequences: Entries() and the next reads of that shape
            try:
                rec["entries_call"] = str(s.c.call("Graph.KG.Cypher.Gen", "Entries"))
            except Exception as e:  # noqa: BLE001
                rec["entries_call_error"] = f"{type(e).__name__}: {str(e)[:300]}"
            n0 = c09.native_count(eng)
            rec["reread_1"] = c09.run(eng, q)
            rec["reread_2"] = c09.run(eng, q)
            rec["native_rereads"] = c09.native_count(eng) - n0
            rec["after_rereads"] = entry_status(s)
            out["attempts"].append(rec)
            if broken:
                break
        else:
            out["attempts"].append(rec)
    out["reproduced_broken_entry"] = any(a["broken_entries"] for a in out["attempts"])
    out["surviving_class_after_dropall"] = any(a["after"]["class_definitions"] for a in out["attempts"])
    mode(s, "")
    dropall(s)
    out["after_cleanup"] = entry_status(s)
    return out


def collide_labels(s, template_label, h):
    """Birthday search in IRIS: same-length labels whose shape (the stored shape with the label replaced) shares $ZCRC."""
    # Candidates differ in pseudo-random letters (6 from $ZCRC("k"_i) and 4 from i): CRC-32 is linear, so names that
    # differ only in a few digit positions span fewer than 32 GF(2) dimensions and never collide (the first run's
    # digit-only search found none in 900,000); letters from a pseudo-random value span enough for a birthday search.
    assert len(template_label) == 14 and template_label.startswith("B09Q")
    script = (' set S=$list(^IVG.CypherCompiled(' + str(h) + '),2), T="' + template_label + '" kill seen set found=0'
              ' for i=1:1:400000 { set v=$zcrc("k"_i,7), w=i, x="" for j=1:1:6 { set x=x_$char(65+(v#26)), v=v\\26 } for j=1:1:4 { set x=x_$char(65+(w#26)), w=w\\26 }'
              ' set cand="B09Q"_x, c=$zcrc($replace(S,T,cand),7)'
              ' if $data(seen(c),o) { write $char(30),"COL|",o,"|",cand,"|",c,"|",i,! set found=1 quit } set seen(c)=cand }'
              ' write $char(30),"DONE|",found,!')
    o = c09.osession(script, timeout=600)
    cols = c09.marked(o, "COL")
    if not cols:
        return None, o[-500:]
    a, b, c, i = cols[0].split("|")
    return {"label_1": a, "label_2": b, "crc": c, "tries": int(i)}, None


def part_f0901(s):
    out = {"attempts": []}
    eng = s.eng
    tpl = "B09QAAAAAAAAAA"
    eng.create_node("b09_ca", labels=["B09CA"], properties={"name": "ca"})
    eng.create_node("b09_cx", labels=[tpl], properties={"name": "cx"})
    eng.create_edge("b09_ca", "B09CR", "b09_cx")

    def q(lab):
        return f"MATCH (a:B09CA {{id: 'b09_ca'}})-[:B09CR]->(b:{lab}) RETURN count(b) AS c"
    dropall(s)
    mode(s, "sync")
    out["template_read"] = c09.run(eng, q(tpl))
    st = entry_status(s)
    out["template_state"] = st
    hs = [h for h, e in st["entries"].items() if e["status"] == "ok"]
    if not hs:
        out["error"] = "no compiled entry for the template shape"
        mode(s, "")
        return out
    h0 = hs[0]
    t0 = time.time()
    col, err = collide_labels(s, tpl, h0)
    out["search_seconds"] = round(time.time() - t0, 2)
    out["collision"] = col
    if col is None:
        out["error"] = "no collision found: " + str(err)
        mode(s, "")
        dropall(s)
        return out
    l1, l2 = col["label_1"], col["label_2"]
    # data: one L1 neighbour, two L2 neighbours of b09_ca
    eng.create_node("b09_c1", labels=[l1], properties={"name": "c1"})
    eng.create_node("b09_c2", labels=[l2], properties={"name": "c2"})
    eng.create_node("b09_c3", labels=[l2], properties={"name": "c3"})
    for t in ("b09_c1", "b09_c2", "b09_c3"):
        eng.create_edge("b09_ca", "B09CR", t)
    sql_eng = s.engine_on(s.c, native_cypher=False, embedding_dimension=4)
    out["sql_answers"] = {l1: c09.run(sql_eng, q(l1)), l2: c09.run(sql_eng, q(l2))}
    # the stored shapes really collide: sync-compile each alone and read its hash
    for lab in (l1, l2):
        dropall(s)
        mode(s, "sync")
        c09.run(eng, q(lab))
        out.setdefault("hash_of", {})[lab] = sorted(entry_status(s)["entries"].keys())
    for attempt, delay in enumerate([0.0, 0.0, 0.03, 0.1, 0.2, 0.0]):
        dropall(s)
        mode(s, "job")
        rec = {"delay": delay}
        n0 = c09.native_count(eng)
        rec["read_l2"] = c09.run(eng, q(l2))
        time.sleep(delay)
        rec["read_l1"] = c09.run(eng, q(l1))
        st, waited = wait_settled(s, 60)
        rec["settled_after_s"] = waited
        rec["state"] = st
        ents = list(st["entries"].values())
        cls = ents[0]["class"] if ents else ""
        rec["walk1_names"] = walk1_label(s, cls, [l1, l2]) if cls else None
        n1 = c09.native_count(eng)
        rec["reread_l1"] = c09.run(eng, q(l1))
        rec["reread_l1_native"] = c09.native_count(eng) - n1
        rec["natives"] = c09.native_count(eng) - n0
        wrong = (rec["reread_l1"].get("rows") not in (None, out["sql_answers"][l1].get("rows")))
        rec["wrong_answer"] = wrong
        if wrong:
            shadow = s.engine_on(s.c, embedding_dimension=4, native_route_ms=0)
            shadow.cypher_shadow = True
            rec["shadow_l1"] = c09.run(shadow, q(l1))
            rec["state_after_shadow"] = entry_status(s)
            # it persists: another reread in a fresh engine (any process using this namespace)
            other = s.engine_on(s.conn2(), embedding_dimension=4, native_route_ms=0)
            rec["other_process_l1"] = c09.run(other, q(l1))
        out["attempts"].append(rec)
        if wrong:
            break
    out["reproduced_wrong_answer"] = any(a.get("wrong_answer") for a in out["attempts"])
    if not out["reproduced_wrong_answer"]:
        # two processes: P2 reads the l2 shape in sync mode (For writes the entry, Build compiles in P2 under the
        # entry lock); as soon as the entry appears, this process reads the l1 shape in job mode (For overwrites the
        # entry with l1's shape; its job cannot take the lock). P2's Build then marks l1's entry ok for l2's class.
        hs2 = (out.get("hash_of") or {}).get(l2) or []
        for attempt in range(3):
            dropall(s)
            mode(s, "off")
            c09.run(eng, q(l1))  # warm the engine's translation cache so the timed read below is quick
            mode(s, "job")
            rec = {"variant": "two-process sync", "attempt": attempt}
            h = int(hs2[0]) if hs2 else None
            code = ("import json,sys; sys.path.insert(0, %r); from blive import open_conn, make_engine; c = open_conn(); "
                    "e = make_engine(c, native_route_ms=0); c.call('Graph.KG.Cypher.Gen', 'Mode', 'sync'); "
                    "r = e.execute_cypher(%r); print(json.dumps({'pid': c.pid, 'rows': [list(x) for x in r.rows]})); "
                    "c.call('Graph.KG.Cypher.Gen', 'Mode', ''); c.close()") % (str(Path(__file__).resolve().parent), q(l2))
            proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            t0 = time.time()
            seen = False
            while time.time() - t0 < 60 and h is not None:
                if s.c.o.isDefined("IVG.CypherCompiled", h) % 10 == 1:
                    seen = True
                    break
            rec["entry_seen_after_s"] = round(time.time() - t0, 3) if seen else None
            rec["read_l1"] = c09.run(eng, q(l1)) if seen else None
            try:
                o, e_ = proc.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                proc.kill(); o, e_ = proc.communicate()
            rec["p2"] = o.strip()[-500:]
            rec["p2_err"] = "\n".join(ln for ln in e_.splitlines() if "WARNING" not in ln)[-800:]
            st, waited = wait_settled(s, 60)
            rec["state"] = st
            ents = list(st["entries"].values())
            cls = ents[0]["class"] if ents else ""
            rec["walk1_names"] = walk1_label(s, cls, [l1, l2]) if cls else None
            n1 = c09.native_count(eng)
            rec["reread_l1"] = c09.run(eng, q(l1))
            rec["reread_l1_native"] = c09.native_count(eng) - n1
            rec["wrong_answer"] = rec["reread_l1"].get("rows") not in (None, out["sql_answers"][l1].get("rows"))
            if rec["wrong_answer"]:
                shadow = s.engine_on(s.c, embedding_dimension=4, native_route_ms=0)
                shadow.cypher_shadow = True
                rec["shadow_l1"] = c09.run(shadow, q(l1))
                other = s.engine_on(s.conn2(), embedding_dimension=4, native_route_ms=0)
                rec["other_process_l1"] = c09.run(other, q(l1))
            out["attempts"].append(rec)
            if rec["wrong_answer"]:
                break
        out["reproduced_wrong_answer"] = any(a.get("wrong_answer") for a in out["attempts"])
    mode(s, "")
    dropall(s)
    return out


def part_f0902(s):
    out = {}
    eng = s.eng
    script = (' set hub="b09_hub", T="B09T" kill seen set found=0'
              ' for i=1:1:400000 { set v=$zcrc("k"_i,7), w=i, y="" for j=1:1:6 { set y=y_$char(97+(v#26)), v=v\\26 } for j=1:1:4 { set y=y_$char(97+(w#26)), w=w\\26 }'
              ' set x="b09_x"_y, c=$zcrc($listbuild(x,T,hub,""),7)'
              ' if $data(seen(c),o) { write $char(30),"COL|",o,"|",x,"|",c,"|",i,! set found=1 quit } set seen(c)=x }'
              ' write $char(30),"DONE|",found,!')
    t0 = time.time()
    o = c09.osession(script, timeout=600)
    out["search_seconds"] = round(time.time() - t0, 2)
    cols = c09.marked(o, "COL")
    if not cols:
        out["error"] = "no collision: " + o[-400:]
        return out
    x1, x2, crc, tries = cols[0].split("|")
    out["collision"] = {"x1": x1, "x2": x2, "crc": crc, "tries": int(tries)}
    eng.create_node("b09_hub", labels=["B09H"], properties={"name": "hub"})
    for x in (x1, x2):
        eng.create_node(x, labels=["B09P"], properties={"name": x})
        eng.create_edge(x, "B09T", "b09_hub")
    # control pair without a collision
    eng.create_node("b09_hub2", labels=["B09H2"], properties={"name": "hub2"})
    for x in ("b09_y1", "b09_y2"):
        eng.create_node(x, labels=["B09P2"], properties={"name": x})
        eng.create_edge(x, "B09T", "b09_hub2")
    q = "MATCH (a:B09P)-[:B09T]->(h:B09H)<-[:B09T]-(c:B09P) RETURN count(*) AS n"
    qc = "MATCH (a:B09P2)-[:B09T]->(h:B09H2)<-[:B09T]-(c:B09P2) RETURN count(*) AS n"
    q_rows = "MATCH (a:B09P)-[:B09T]->(h:B09H)<-[:B09T]-(c:B09P) RETURN a.name AS a, c.name AS c ORDER BY a.name, c.name"
    sql_eng = s.engine_on(s.c, native_cypher=False, embedding_dimension=4)
    out["sql"] = {"count": c09.run(sql_eng, q), "control": c09.run(sql_eng, qc), "rows": c09.run(sql_eng, q_rows)}
    dropall(s)
    mode(s, "off")
    n0 = c09.native_count(eng)
    out["interpreted"] = {"count": c09.run(eng, q), "control": c09.run(eng, qc), "rows": c09.run(eng, q_rows)}
    out["interpreted_native_answers"] = c09.native_count(eng) - n0
    mode(s, "sync")
    n0 = c09.native_count(eng)
    out["compiled"] = {"count": c09.run(eng, q), "rows": c09.run(eng, q_rows)}
    out["compiled_native_answers"] = c09.native_count(eng) - n0
    out["compiled_entries"] = entry_status(s)
    mode(s, "off")
    shadow = s.engine_on(s.c, embedding_dimension=4, native_route_ms=0)
    shadow.cypher_shadow = True
    out["shadow_interpreted"] = c09.run(shadow, q)
    mode(s, "")
    dropall(s)
    return out


def part_f0907(s):
    out = {}
    eng = s.eng
    # inserted in reverse id order: the rows' insertion order is not their id order
    for nid in ("b09_t4", "b09_t3", "b09_t2", "b09_t1"):
        eng.create_node(nid, labels=["B09TIE"], properties={"title": "same", "sid": nid})
    shadow = s.engine_on(s.c, embedding_dimension=4, native_route_ms=0)
    shadow.cypher_shadow = True
    sql_eng = s.engine_on(s.c, native_cypher=False, embedding_dimension=4)
    mode(s, "off")
    for name, q in (("limit", "MATCH (m:B09TIE) RETURN m.sid AS sid, m.title AS title ORDER BY m.title LIMIT 2"),
                    ("nolimit", "MATCH (m:B09TIE) RETURN m.sid AS sid, m.title AS title ORDER BY m.title"),
                    ("control_unique_order", "MATCH (m:B09TIE) RETURN m.sid AS sid, m.title AS title ORDER BY m.sid LIMIT 2")):
        n0 = c09.native_count(eng)
        out[name] = {"native": c09.run(eng, q), "sql": c09.run(sql_eng, q), "shadow": c09.run(shadow, q)}
        out[name]["native_answers"] = c09.native_count(eng) - n0
    mode(s, "")
    return out


def part_f0909(s):
    import iris
    out = {}
    from iris_vector_graph.engine import IRISGraphEngine
    eng = s.eng
    eng.create_node("b09_ta", labels=["B09TA"], properties={"name": "ta"})
    fc = IRISGraphEngine.from_connect("127.0.0.1", int(c09.os.environ["IVG_PORT"]), "AUDITB", "_SYSTEM", "SYS",
                                      embedding_dimension=4, native_route_ms=0)
    try:
        nat = fc._iris_obj()
        out["native_pid"] = str(nat.classMethodValue("%SYSTEM.SYS", "ProcessID"))
        cur = fc.conn.cursor()
        sqlnat = iris.createIRIS(fc.conn)
        out["sql_pid"] = str(sqlnat.classMethodValue("%SYSTEM.SYS", "ProcessID"))
        out["dedicated_native_connection"] = out["native_pid"] != out["sql_pid"]
        q = "MATCH (a:B09TA {id: 'b09_ta'})-[:B09TR]->(b:B09TX) RETURN count(b) AS c"
        out["before"] = c09.run(fc, q)
        cur.execute("START TRANSACTION")
        w = IRISGraphEngine(fc.conn, namespace="AUDITB", embedding_dimension=4, native_cypher=False)
        out["write_node_in_txn"] = w.create_node("b09_tx", labels=["B09TX"], properties={"name": "tx"})
        out["write_edge_in_txn"] = w.create_edge("b09_ta", "B09TR", "b09_tx")
        try:
            out["tlevel_sql_process"] = int(sqlnat.getTLevel())
        except Exception as e:  # noqa: BLE001
            out["tlevel_sql_process_error"] = repr(e)
        n0 = c09.native_count(fc)
        out["native_in_txn"] = c09.run(fc, q)
        out["native_in_txn_was_native"] = c09.native_count(fc) - n0
        sql_same_conn = IRISGraphEngine(fc.conn, namespace="AUDITB", embedding_dimension=4, native_cypher=False)
        out["sql_in_txn_same_process"] = c09.run(sql_same_conn, q)
        n0 = c09.native_count(eng)
        out["other_process_native"] = c09.run(eng, q)
        out["other_process_was_native"] = c09.native_count(eng) - n0
        out["other_process_pid"] = s.c.pid
        cur.execute("ROLLBACK")
        out["after_rollback_native"] = c09.run(fc, q)
        cur.close()
    finally:
        try:
            fc.conn.close()
        except Exception:
            pass
        try:
            if getattr(fc, "_native_conn", None) is not None:
                fc._native_conn.close()
        except Exception:
            pass
    return out


def part_f0904(s):
    out = {}
    eng = s.eng
    eng.create_node("b09_ka", labels=["B09KA"], properties={"name": "ka"})
    eng.create_node("b09_kb", labels=["B09KB"], properties={"name": "kb"})
    eng.create_edge("b09_ka", "B09KR", "b09_kb")
    dropall(s)
    mode(s, "sync")
    tag = "%06d" % random.randint(0, 999999)
    try:
        s.c.o.set(1, "IVG.CypherGen", "breaktest")
        n0 = c09.native_count(eng)
        out["read_with_failed_build"] = c09.run(eng, f"MATCH (a:B09KA {{id: 'b09_ka'}})-[:B09KR]->(b:B09KB) RETURN b.name AS k{tag}")
        out["native"] = c09.native_count(eng) - n0
        out["entries"] = entry_status(s)
    finally:
        s.c.o.kill("IVG.CypherGen", "breaktest")
    # the same process prepares statement texts it has never run (P-0903)
    probes = []
    for i in range(3):
        sql = f"SELECT COUNT(*) AS b09p{tag}{i} FROM Graph_KG.nodes WHERE node_id = 'b09_nope_{tag}_{i}'"
        try:
            probes.append({"sql": sql, "rows": s.c.sql(sql)})
        except Exception as e:  # noqa: BLE001
            probes.append({"sql": sql, "error": f"{type(e).__name__}: {str(e)[:300]}"})
    out["new_sql_in_same_process"] = probes
    out["sql_path_read_same_process"] = c09.run(s.engine_on(s.c, native_cypher=False, embedding_dimension=4),
                                                f"MATCH (a:B09KA {{id: 'b09_ka'}})-[:B09KR]->(b:B09KB) RETURN b.name AS z{tag}")
    out["process_pid"] = s.c.pid
    mode(s, "")
    dropall(s)
    return out


def part_f0906(s):
    out = {}
    rows = s.c.sql("SELECT parent, Name, Type, SqlName FROM %Dictionary.CompiledIndex WHERE parent %STARTSWITH 'Graph.KG.rdf' AND Name %STARTSWITH 'idx'")
    out["indexes"] = [list(r) for r in rows]
    from iris_vector_graph.schema import GraphSchema
    try:
        out["adjacency_index_kind"] = GraphSchema.adjacency_index_kind(s.c.conn.cursor(), schema="Graph_KG", native=s.c.o)
    except Exception as e:  # noqa: BLE001
        out["adjacency_index_kind_error"] = repr(e)
    out["engine_adjacency_indexed"] = s.eng._adjacency_indexed
    for m in ("Indexed", "IndexKind"):
        try:
            out[f"Adjacency.{m}"] = str(s.c.call("Graph.KG.Adjacency", m))
        except Exception as e:  # noqa: BLE001
            out[f"Adjacency.{m}_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return out


FUNCS = {"probe": part_probe, "footprint": part_footprint, "f0903": part_f0903, "f0905": part_f0905,
         "f0901": part_f0901, "f0902": part_f0902, "f0907": part_f0907, "f0909": part_f0909, "f0904": part_f0904,
         "f0906": part_f0906}

with c09.session("09-live", native_route_ms=0) as s:
    s.eng.native_route_ms = 0
    for name in [p for p in PARTS if p in want]:
        t0 = time.time()
        try:
            res = FUNCS[name](s)
            status = "done"
        except Exception as e:  # noqa: BLE001
            res = {"exception": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
            status = "exception"
        res["seconds"] = round(time.time() - t0, 2)
        res["status"] = status
        p = c09.write_log(s, res, name=f"09-{name}")
        RESULTS[name] = (status, str(p), res["seconds"])
        print(name, status, res["seconds"], p, flush=True)
        try:
            cl = c09.cleanup(s)
        except Exception as e:  # noqa: BLE001
            cl = {"cleanup_error": repr(e)}
        c09.write_log(s, cl, name=f"09-{name}-cleanup")
    final = c09.cleanup(s)
    c09.write_log(s, {"parts": RESULTS, "final_cleanup": final}, name="09-live-summary")
print(json.dumps(RESULTS, indent=1))
