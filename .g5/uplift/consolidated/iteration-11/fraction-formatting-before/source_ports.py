"""Mutable source transcription: actual DijkstraJson and DijkstraCost control steps.
Exact Fraction arithmetic is an explicit provider interpretation; this does not
execute ObjectScript or claim native Double/JSON equivalence.
"""
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


