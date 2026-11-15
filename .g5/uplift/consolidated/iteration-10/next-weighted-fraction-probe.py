"""Source-only exact Fraction/grid-numerator trace sanity, not a Verus model.

No product/native imports, network, runtime or Git. Both executions retain the
actual source control structure; only numeric representation differs. No search
consumes an optimum or oracle answer. This checks scaling, not algorithm validity.
"""
import hashlib
import itertools
import json
import random
import socket
import time
from fractions import Fraction as F
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
GUARD = patch.object(socket.socket, "connect", side_effect=AssertionError("source-only fraction probe"))
CONNECT = GUARD.start()


def raw(rows):
    out = {}
    for g, u, p, v, n in rows:
        out[0, g, u, p, v] = n
        out[1, g, v, p, u] = n
    return out


def encode(r, d, mutant=None):
    return {a: ((None if mutant == "default-unit-one" else d) if n is None else
                ((1 if mutant == "nonpositive-unit-one" else d) if n <= 0 else
                 (n*d if mutant == "positive-scaled-twice" else n))) for a, n in r.items()}


def arcs(r, graph, direction, predicates, node, backward=False, wrong_order=False):
    primary = (1 if direction == "in" else 0) ^ int(backward)
    if wrong_order and backward and direction == "both":
        primary ^= 1
    tags = [primary, 1-primary] if direction == "both" else [primary]
    return [a for tag in tags for a in sorted(r)
            if a[0] == tag and a[1] == graph and a[2] == node
            and (not predicates or a[3] in predicates)]


def freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((k, freeze(v)) for k, v in value.items()))
    if isinstance(value, (set, frozenset)):
        return tuple(sorted(value))
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


def json_search(r, weight, src, dst, cap, bound, direction, predicates, graph, mutant=None):
    q = {(0, src, 0)}; dist = {(src, 0): 0}; seen = {}; parent = {}; trace = []
    if src == dst:
        return {"answer": 0, "path": [], "trace": [], "stop": "self"}
    while q:
        trace.append(freeze((q, dist, seen, parent)))
        cost, u, h = min(q); q.remove((cost, u, h))
        if u in seen and seen[u] <= h:
            continue
        seen[u] = h
        if u == dst:
            v, hh, path = dst, h, []
            while v != src:
                if (v, hh) not in parent:
                    break  # actual source break; inherited proof rules it out here
                before, ph, a, w = parent[v, hh]
                path.insert(0, (a, w)); v, hh = before, ph
            assert v == src and sum(w for a, w in path) == cost
            return {"answer": cost, "path": path, "trace": trace, "stop": "target"}
        if cost >= cap or (bound and h >= bound):
            continue
        nh = h + 1 if bound else 0
        for a in arcs(r, graph, direction, predicates, u):
            v = a[4]; n = cost + weight(r[a]); k = (v, nh)
            if (v in seen and seen[v] <= nh) or n > cap or (k in dist and dist[k] <= n):
                continue
            if mutant == "json-removes-old" and k in dist:
                q.discard((dist[k], v, nh))
            dist[k] = n; q.add((n, v, nh)); parent[k] = (u, h, a, weight(r[a]))
    trace.append(freeze((q, dist, seen, parent)))
    return {"answer": None, "path": [], "trace": trace, "stop": "empty"}


def cost_search(r, weight, src, dst, cap, bound, direction, predicates, graph, mutant=None):
    if src == dst:
        return {"answer": 0, "trace": [], "fallback": False, "best_hops": 0, "stop": "self"}
    q = [{(0, src)}, {(0, dst)}]; dist = [{src: 0}, {dst: 0}]
    hops = [{src: 0}, {dst: 0}]; done = [set(), set()]; best = None; bh = 0; trace = []
    while True:
        trace.append(freeze((q, dist, hops, done, best, bh)))
        if not q[0] or not q[1]:
            stop = "empty"; break
        top = [min(s)[0] for s in q]
        if best is not None and sum(top) >= best:
            stop = "frontsum"; break
        side = int(top[1] < top[0]); other = 1-side
        c, u = min(q[side]); q[side].remove((c, u)); done[side].add(u)
        if c >= cap:
            continue
        for a in arcs(r, graph, direction, predicates, u, bool(side), mutant == "cost-wrong-both-order"):
            v = a[4]; n = c + weight(r[a])
            if v in done[side] or n > cap:
                continue
            if v not in dist[side] or n < dist[side][v]:
                if v in dist[side] and mutant != "cost-keeps-old":
                    q[side].discard((dist[side][v], v))
                dist[side][v] = n; hops[side][v] = hops[side][u] + 1; q[side].add((n, v))
            if v in dist[other]:
                meeting = dist[side][v] + dist[other][v]
                if best is None or meeting < best:
                    best, bh = meeting, hops[side][v] + hops[other][v]
    fallback = best is not None and best <= cap and bound > 0 and bh > bound
    jr = json_search(r, weight, src, dst, cap, bound, direction, predicates, graph) if fallback else None
    answer = None if best is None or best > cap else (jr["answer"] if fallback else best)
    return {"answer": answer, "trace": trace, "fallback": fallback, "best_hops": bh,
            "stop": stop, "fallback_json": jr}


def decode_json(z, d):
    def state(t):
        q, dist, seen, parent = t
        return (tuple((F(c,d),u,h) for c,u,h in q),
                tuple((k,F(v,d)) for k,v in dist), seen,
                tuple((k,(u,h,a,F(w,d))) for k,(u,h,a,w) in parent))
    return {**z, "answer": None if z["answer"] is None else F(z["answer"],d),
            "path": [(a,F(w,d)) for a,w in z["path"]], "trace": [state(t) for t in z["trace"]]}


def decode_cost(z, d):
    def state(t):
        q, dist, hops, done, best, bh = t
        return (tuple(tuple((F(c,d),u) for c,u in s) for s in q),
                tuple(tuple((k,F(v,d)) for k,v in s) for s in dist), hops, done,
                None if best is None else F(best,d), bh)
    result = {**z, "answer": None if z["answer"] is None else F(z["answer"],d),
              "trace": [state(t) for t in z["trace"]]}
    if z.get("fallback_json") is not None:
        result["fallback_json"] = decode_json(z["fallback_json"], d)
    return result


def case(r, d, cap, h, direction="out", predicates=(), graph="g", src="s", dst="t", mutant=None):
    qw = lambda n: F(n,d) if n is not None and n > 0 else F(1)
    iw = lambda n: n if n is not None and n > 0 else 1
    ir = encode(r,d,mutant); icap = cap if mutant != "cap-not-scaled" else cap//d
    jq = json_search(r,qw,src,dst,F(cap,d),h,direction,predicates,graph)
    ji = decode_json(json_search(ir,iw,src,dst,icap,h,direction,predicates,graph,mutant),d)
    cq = cost_search(r,qw,src,dst,F(cap,d),h,direction,predicates,graph)
    ci = decode_cost(cost_search(ir,iw,src,dst,icap,h,direction,predicates,graph,mutant),d)
    if mutant == "output-not-decoded" and ci["answer"] is not None:
        ci["answer"] *= d
    return {"agrees": jq == ji and cq == ci, "json": jq, "cost": cq, "scaled_json": ji, "scaled_cost": ci}


def main():
    started = time.monotonic(); rng = random.Random(210111); cases = 0; fallback = 0; failed = []
    for d in [1,2,3,4,8,10]:
        graphs = [raw([("g","s","R","a",2*d),("g","s","R","b",d//2 or 1),("g","b","R","a",d//2 or 1),("g","a","R","t",d//2 or 1)])]
        for _ in range(12):
            graphs.append(raw([("g",u,p,v,rng.choice([None,-d,0,1,2,d,5]))
                               for u,v,p in itertools.product("sabt","sabt",["R","S"]) if rng.randrange(8)==0]))
        for r, cap, h, di, ps, graph, endpoints in itertools.product(graphs,[0,d,3*d,6*d],[0,2,3],["out","in","both"],[(),("R",)],["g","other"],[("s","t"),("s","ghost"),("ghost","ghost")]):
            result = case(r,d,cap,h,di,ps,graph,*endpoints); cases += 1; fallback += result["cost"]["fallback"]
            if not result["agrees"]:failed.append((d,cap,h,di,ps,graph,endpoints))
    default = raw([("g","s","R","t",None),("g","s","R","a",1),("g","a","R","t",2)])
    nonpos = raw([("g","s","R","t",0),("g","s","R","a",1),("g","a","R","t",2)])
    fitting = raw([("g","s","R","a",2),("g","a","R","t",3)])
    a1 = raw([("g","s","R","a",8),("g","s","R","b",2),("g","b","R","a",2),("g","a","R","t",2)])
    both = raw([("g","s","R","a",2),("g","a","R","v",2),("g","v","R","u",2),("g","u","R","t",2),("g","u","R","w",3),("g","s","R","w",3)])
    controls = {}
    for name,r,d,cap,h,di in [("default-unit-one",default,4,12,0,"out"),("nonpositive-unit-one",nonpos,4,12,0,"out"),("positive-scaled-twice",fitting,4,5,0,"out"),("cap-not-scaled",fitting,4,5,0,"out"),("output-not-decoded",fitting,4,5,0,"out"),("json-removes-old",a1,4,40,0,"out"),("cost-keeps-old",a1,4,40,0,"out"),("cost-wrong-both-order",both,4,40,3,"both")]:
        baseline=case(r,d,cap,h,di); changed=case(r,d,cap,h,di,mutant=name)
        controls[name]={"detected":baseline["agrees"] and not changed["agrees"],"baseline":baseline,"changed":changed}
    laws = 0
    for d,n,m in itertools.product([1,2,3,4,8,10],range(15),range(15)):
        assert F(n+m,d)==F(n,d)+F(m,d) and ((n<m)==(F(n,d)<F(m,d))) and ((n<=m)==(F(n,d)<=F(m,d)))
        laws += 1
    inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ["iris_src/src/Graph/KG/TraversalPaths.cls",".g5/Verus_verification/models/weighted_paths/weighted_paths.rs",".g5/Verus_verification/models/weighted_cost/weighted_cost.rs",".g5/uplift/consolidated/iteration-10/next-weighted-fraction-PAIRS.md"]}
    out={"verdict":"AGREES" if not failed and all(v["detected"] for v in controls.values()) and CONNECT.call_count==0 else "DISAGREES","comparisons":cases,"fallbacks":fallback,"algebra_checks":laws,"failures":failed[:8],"controls":controls,"inputs":inputs,"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"elapsed_s":time.monotonic()-started,"socket_calls":CONNECT.call_count,"scope":"Source-only Fraction vs scaled-numerator full trace sanity; no formal proof, product/native execution, independent optimum input or new model credit. Same actual queue/relaxation skeleton; deciding searches receive only raw graph/cap/H."}
    Path(__file__).with_suffix(".json").write_text(json.dumps(out,indent=2,default=str)+"\n")
    print(json.dumps({k:out[k] for k in ["verdict","comparisons","fallbacks","algebra_checks","elapsed_s","socket_calls"]}));print(json.dumps({k:v["detected"] for k,v in controls.items()}));assert out["verdict"]=="AGREES"


if __name__ == "__main__":
    main()
