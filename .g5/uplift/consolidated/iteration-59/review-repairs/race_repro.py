"""Iteration 59 reproduction of the review-56-58 race probe (copied verbatim except prefix and output path): reads and writes in one connection while another process runs engine.sync().
Fixture ivg-cont-20261117-iris, USER, prefix i59r_<tag>_. Default graph: s-R->a, a-Q->b, s-R->c.
Reads: engine.khop(s,2), store.shortest_path_length(s,b), Cypher var-length count on a native_cypher=True engine.
Writes during sync: create_edge(w_i -W-> x_i); after the syncs each must be in ^KG out and answered by khop(w_i,1)."""
import json, os, subprocess, sys, time
from collections import Counter
REPO = os.environ["IVG_REPO"]
sys.path.insert(0, REPO + "/.g5/Verus_verification/tools"); sys.path.insert(0, REPO + "/.g5/uplift/consolidated/iteration-36")
import binding_common as bc
bc.import_pin()
import runtime

def child(n):
    c = runtime.connect(); e = runtime.engine(c)
    for _ in range(n):
        e.sync()
    c.close()

def main():
    import iris
    from iris_vector_graph.engine import IRISGraphEngine
    tag = time.strftime("%H%M%S", time.gmtime()); P = f"i59r_{tag}_"
    c = runtime.connect(); e = runtime.engine(c); nat = iris.createIRIS(c); st = e._store
    cn = runtime.connect(); en = IRISGraphEngine(cn, embedding_dimension=768, native_cypher=True)
    for a, t, b in [("s", "R", "a"), ("a", "Q", "b"), ("s", "R", "c")]:
        e.create_edge(P + a, t, P + b)
    def read():
        out = {}
        try: out["khop"] = sorted(n[len(P):] for n in e.khop(P + "s", hops=2)["nodes"])
        except Exception as ex: out["khop"] = "ERR " + str(ex)[:60]
        try: out["spl"] = st.shortest_path_length(P + "s", P + "b", [], 5, "out")
        except Exception as ex: out["spl"] = "ERR " + str(ex)[:60]
        try:
            r = en.execute_cypher(f"MATCH (s {{node_id: '{P}s'}})-[*1..2]->(b) RETURN count(DISTINCT b) AS c")
            out["cy"] = r.rows[0][0] if r.rows else ("ERR " + str(r.error)[:60])
        except Exception as ex: out["cy"] = "ERR " + str(ex)[:60]
        return json.dumps(out, sort_keys=True)
    N = int(os.environ.get("RACE_N", "30"))
    quiet = Counter(read() for _ in range(N))
    proc = subprocess.Popen([sys.executable, "-B", __file__, "--child", os.environ.get("RACE_SYNCS", "3")], env=os.environ)
    busy = Counter(); writes = []; i = 0; t0 = time.time()
    while proc.poll() is None:
        busy[read()] += 1
        if i < 40:
            try:
                e.create_edge(P + f"w{i}", "W", P + f"x{i}"); writes.append(i)
            except Exception as ex:
                writes.append(f"ERR {i} {str(ex)[:60]}")
            i += 1
    after = Counter(read() for _ in range(5))
    lost = []
    for w in writes:
        if not isinstance(w, int): continue
        k = nat.isDefined("^KG", "out", 0, P + f"w{w}", "W", P + f"x{w}")
        h = e.khop(P + f"w{w}", hops=1)["nodes"]
        if not k or (P + f"x{w}") not in h: lost.append({"i": w, "kg_defined": k, "khop": [n[len(P):] for n in h]})
    expected = quiet.most_common(1)[0][0]
    body = {"prefix": P, "quiet": dict(quiet), "during_sync": dict(busy), "after": dict(after),
            "sync_seconds": round(time.time() - t0, 1), "departures": sum(v for k, v in busy.items() if k != expected),
            "reads_during_sync": sum(busy.values()), "writes_during_sync": writes, "writes_lost_from_adjacency": lost}
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"race-observed-{tag}.json")
    json.dump(body, open(fn, "w"), indent=1)
    print(json.dumps({k: body[k] for k in ("departures", "reads_during_sync", "sync_seconds", "writes_lost_from_adjacency")}))
    for k, v in busy.most_common(): print(v, k)
    print("quiet", dict(quiet)); print("after", dict(after))

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--child": child(int(sys.argv[2]))
    else: main()
