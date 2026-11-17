"""Iteration 57 (builder): what traversal readers answer while another connection runs engine.sync().

Fixture ivg-cont-20261117-iris, USER, fresh prefix i57c_<tag>_ in the default graph: s-R->a, a-Q->b, s-R->c.
Phase 1 (quiet): readers N times, no rebuild. Phase 2: a child process (own connection) runs sync() repeatedly
while the parent runs the same readers. Records each distinct answer with its count. Readers: store.execute_bfs
(rows and whether the SQL fallback ran), engine.khop, store.shortest_path_length(s, b), and a raw ^KG out-entry
count for s. Expected (frozen W61 R1 and the owners): every answer equals the quiet answer."""
import json, os, subprocess, sys, time
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

def child(n):
    c = runtime.connect(); e = runtime.engine(c)
    for _ in range(n):
        e.sync()
    c.close()

def main():
    import iris
    tag = time.strftime("%H%M%S", time.gmtime()); P = f"i57c_{tag}_"
    c = runtime.connect(); e = runtime.engine(c); nat = iris.createIRIS(c); st = e._store
    for a, t, b in [("s", "R", "a"), ("a", "Q", "b"), ("s", "R", "c")]:
        e.create_edge(P + a, t, P + b)
    calls = {"fb": 0}
    real_fb = st._sql_bfs_fallback
    def fb(*a, **k):
        calls["fb"] += 1
        return real_fb(*a, **k)
    st._sql_bfs_fallback = fb
    def read():
        calls["fb"] = 0
        out = {}
        try:
            rows = [tuple(r) for r in st.execute_bfs(P + "s", [], 2, "out", 0).rows]
            out["bfs"] = [(x[0][len(P):], x[1], x[2]) for x in rows]
        except Exception as ex:
            out["bfs"] = "ERR " + str(ex)[:80]
        out["bfs_fallback"] = calls["fb"]
        try:
            k = e.khop(P + "s", hops=2)
            out["khop"] = sorted(n[len(P):] for n in k["nodes"])
        except Exception as ex:
            out["khop"] = "ERR " + str(ex)[:80]
        try:
            out["spl"] = st.shortest_path_length(P + "s", P + "b", [], 5, "out")
        except Exception as ex:
            out["spl"] = "ERR " + str(ex)[:80]
        n = 0; k2 = ""
        while True:
            k2 = nat.nextSubscript(False, "^KG", "out", 0, P + "s", "R", k2)
            if not k2: break
            n += 1
        out["kg_out_s_R"] = n
        return json.dumps(out, sort_keys=True)
    N = int(os.environ.get("RACE_N", "60"))
    quiet = Counter(read() for _ in range(N))
    proc = subprocess.Popen([sys.executable, "-B", __file__, "--child", os.environ.get("RACE_SYNCS", "4")], env=os.environ)
    busy = Counter(); t0 = time.time()
    while proc.poll() is None:
        busy[read()] += 1
    after = Counter(read() for _ in range(5))
    expected = quiet.most_common(1)[0][0]
    body = {"kind": "probe", "probe": "rebuild_race", "fixture": runtime.NAME, "product": runtime.PRODUCT, "prefix": P,
            "quiet": dict(quiet), "during_sync": dict(busy), "after": dict(after), "sync_seconds": round(time.time() - t0, 1),
            "quiet_answer": json.loads(expected),
            "departures_during_sync": sum(v for k, v in busy.items() if k != expected),
            "reads_during_sync": sum(busy.values())}
    out = HERE / f"race-observed-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    out.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: body[k] for k in ("departures_during_sync", "reads_during_sync", "sync_seconds")}), out.name)
    for k, v in busy.items():
        print(v, k)
    c.close()

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--child":
        child(int(sys.argv[2]))
    else:
        main()
