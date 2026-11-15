"""Module 09 probe: is the native path live in AUDITB (gate facts), do hop reads go native in off/sync modes, what the
plan cache holds afterwards, and is $ZCRC(x,7) the CRC-32 of zlib (P-0901)? Cleans up (DropAll, b09 rows).

    bash experiment/playbook-completion/tools/locks.sh iris python experiment/playbook-completion/live/breadth-b/09_probe.py
"""
import zlib
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("c09", Path(__file__).with_name("09_common.py"))
c09 = importlib.util.module_from_spec(spec); spec.loader.exec_module(c09)

out = {}
with c09.session("09-probe", native_route_ms=0) as s:
    eng = s.eng
    out["gate"] = {"native_cypher": eng.native_cypher, "adjacency_indexed": eng._adjacency_indexed,
                   "privileges": eng._native_privileges(), "executor_current": eng._native_executor_current()}
    from iris_vector_graph.cypher.native_plan import native_gate
    out["gate_reason"] = native_gate(eng)
    out["before"] = c09.plan_state(s.c)
    eng.create_node("b09_a", labels=["B09A"], properties={"name": "a"})
    eng.create_node("b09_b1", labels=["B09X"], properties={"name": "b1"})
    eng.create_node("b09_b2", labels=["B09Y"], properties={"name": "b2"})
    eng.create_edge("b09_a", "B09R", "b09_b1")
    eng.create_edge("b09_a", "B09R", "b09_b2")
    q = "MATCH (a:B09A {id: 'b09_a'})-[:B09R]->(b:B09X) RETURN count(b) AS c"
    out["mode_off"] = str(s.c.call("Graph.KG.Cypher.Gen", "Mode", "off"))
    n0 = c09.native_count(eng)
    out["read_off"] = c09.run(eng, q)
    out["native_after_off"] = c09.native_count(eng) - n0
    out["state_after_off"] = c09.plan_state(s.c)
    out["mode_sync"] = str(s.c.call("Graph.KG.Cypher.Gen", "Mode", "sync"))
    out["read_sync"] = c09.run(eng, q)
    out["state_after_sync"] = c09.plan_state(s.c)
    out["read_sync_2"] = c09.run(eng, q)
    out["native_total"] = c09.native_count(eng) - n0
    # P-0901: $ZCRC(x,7) vs zlib.crc32 on sample strings
    samples = ["", "a", "hello", "IVG native plan", "b09_hub|B09T", "\x01\x02abc\xff"]
    script = "\n".join(f' write $char(30),"CRC|",{i},"|",$zcrc({c09_lit},7),!'.replace("{c09_lit}", "$char(" + ",".join(str(ord(ch)) for ch in smp) + ")" if smp else '""')
                       for i, smp in enumerate(samples))
    o = c09.osession(script)
    got = {int(v.split("|")[0]): int(v.split("|")[1]) for v in c09.marked(o, "CRC")}
    out["zcrc_vs_zlib"] = [{"sample": repr(smp), "zcrc7": got.get(i), "zlib_crc32": zlib.crc32(smp.encode("latin-1")),
                            "equal": got.get(i) == zlib.crc32(smp.encode("latin-1"))} for i, smp in enumerate(samples)]
    out["cleanup"] = c09.cleanup(s)
    p = c09.write_log(s, out)
    print(p)
import json
print(json.dumps({k: out[k] for k in ("gate", "gate_reason", "read_off", "native_after_off", "read_sync", "native_total", "zcrc_vs_zlib")}, indent=1, default=str)[:4000])
print(json.dumps(out["state_after_sync"], indent=1)[:1500])
print(json.dumps(out["cleanup"], indent=1, default=str)[:1500])
