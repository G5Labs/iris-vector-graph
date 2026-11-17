"""W55: Cypher expressions over values known only at run time (run-isolated continuation fixture; ordinary data).

Reads run on both of execute_cypher's entry points (native: engine._try_native, None when it declines; SQL:
engine._execute_parsed_sql). Writes run through execute_cypher and are read back with a later MATCH and get_node().
The frozen predictions are in cypherexpr-PAIRS.md."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W55_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def res(r):
    if r is None:
        return None
    err = getattr(r, "error", None)
    return {"rows": [list(x) for x in r.rows], "error": str(err)[:400] if err else None}


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.cypher.parser import parse_query
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    p, L = f"i48_{TAG}_", f"I48E{TAG}"
    out = {"run": RUN, "fixture": runtime.NAME, "prefix": p, "label": L, "cases": {}}

    def both(q, params=None):
        params = params or {}
        cell = {"query": q, "params": params}
        try:
            nat = e._try_native(parse_query(q), params)
            cell["native"] = res(nat[1]) if nat is not None else None
        except Exception as x:
            cell["native"] = {"exception": f"{type(x).__name__}: {str(x)[:300]}"}
        try:
            cell["sql"] = res(e._execute_parsed_sql(parse_query(q), params, None))
        except Exception as x:
            cell["sql"] = {"exception": f"{type(x).__name__}: {str(x)[:300]}"}
        return cell

    def case(k, q, params=None):
        try:
            out["cases"][k] = both(q, params)
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:300]

    def write(k, q, params=None, reads=(), node_ids=()):
        cell = {"query": q, "params": params or {}}
        try:
            r = e.execute_cypher(q, params or {})
            cell["write"] = {"rows": r.get("rows") if isinstance(r, dict) else None,
                             "error": (r.get("error") if isinstance(r, dict) else None)}
        except Exception as x:
            cell["write"] = {"exception": f"{type(x).__name__}: {str(x)[:400]}"}
        cell["reads"] = {}
        for rq in reads:
            try:
                rr = e.execute_cypher(rq)
                cell["reads"][rq] = rr.get("rows") if isinstance(rr, dict) else str(rr)
            except Exception as x:
                cell["reads"][rq] = f"EXC {type(x).__name__}: {str(x)[:300]}"
        cell["get_node"] = {}
        for nid in node_ids:
            try:
                cell["get_node"][nid] = e.get_node(nid)
            except Exception as x:
                cell["get_node"][nid] = f"EXC {type(x).__name__}: {str(x)[:300]}"
        out["cases"][k] = cell

    # Data (Cypher-written, typed storage)
    e.execute_cypher(f"CREATE (n:{L} {{id: '{p}c', s: 'hello', w: '  Ab c ', b: 'banana', f: 'an', t: 'AN', "
                     f"l: [1, 2, 3, 4, 5], e: [], n42: '42', n29: '2.9', foo: 'foo', i7: 7, f25: 2.5, v: 1, "
                     f"flag: true}})")
    for i, (v, s, flag) in enumerate([(1, 'a', True), (2, 'a', False), (3, 'b', None), (None, None, None)]):
        props = ", ".join(x for x in [f"id: '{p}v{i}'", f"v: {v}" if v is not None else "",
                                      f"s: '{s}'" if s else "", f"flag: {str(flag).lower()}" if flag is not None else ""] if x)
        e.execute_cypher(f"CREATE (n:{L}V {{{props}}})")
    e.execute_cypher(f"CREATE (:{L}M {{id: '{p}m1', v: 1}}), (:{L}M {{id: '{p}m2', v: 5}}), (:{L}M {{id: '{p}m3', v: 3}})")
    e.execute_cypher(f"CREATE (:{L}G {{id: '{p}g1', l: [1]}}), (:{L}G {{id: '{p}g2', l: [2, 3]}})")
    C = f"MATCH (n:{L} {{id: '{p}c'}})"
    V = f"MATCH (n:{L}V) WHERE n.id STARTS WITH '{p}v'"

    # S1
    case("S1_stored", f"{C} RETURN toUpper(n.w), toLower(n.w), trim(n.w), ltrim(n.w), rtrim(n.w), toUpper(n.missing)")
    case("S1_literal", "RETURN toUpper('  Ab c '), toLower('  Ab c '), trim('  Ab c '), ltrim('  Ab c '), rtrim('  Ab c ')")
    case("S1_unwind", "UNWIND ['  Ab c '] AS w RETURN toUpper(w), toLower(w), trim(w), ltrim(w), rtrim(w)")
    # S2
    case("S2_rows", f"{C} UNWIND [[1, 3], [2, 99], [5, 1]] AS ab RETURN ab, substring(n.s, ab[0], ab[1])")
    case("S2_rows_scalar", f"{C} UNWIND [1, 2, 5] AS a RETURN a, substring(n.s, a, 3), substring(n.s, a)")
    case("S2_literal", f"{C} RETURN substring('hello', 1, 3), substring(n.s, 1, 3), substring(n.s, 1), substring(n.s, 2, 99), substring(n.s, 5, 1)")
    case("S2_param", f"{C} RETURN substring(n.s, $a, $b)", {"a": 1, "b": 3})
    case("S2_neg_rows", f"{C} UNWIND [-1] AS a RETURN substring(n.s, a, 2)")
    case("S2_neg_literal", f"{C} RETURN substring(n.s, -1, 2)")
    # S3
    case("S3_rows", f"{C} UNWIND [2, 0, 99] AS k RETURN k, left(n.s, k), right(n.s, k)")
    case("S3_literal", f"{C} RETURN left('hello', 2), right('hello', 2), left(n.s, 2), right(n.s, 2), left(n.s, 0), right(n.s, 99)")
    case("S3_param", f"{C} RETURN left(n.s, $k), right(n.s, $k)", {"k": 2})
    # S4
    case("S4_stored", f"{C} RETURN replace(n.b, n.f, n.t), replace(n.b, 'zz', 'y'), replace(n.b, 'an', n.missing)")
    case("S4_literal", "RETURN replace('banana', 'an', 'AN')")
    case("S4_rows", "UNWIND [['banana', 'an', 'AN']] AS x RETURN replace(x[0], x[1], x[2])")
    # S5
    case("S5_stored", f"{C} RETURN size(n.s), size(n.l), size(n.e)")
    case("S5_literal", "RETURN size('hello'), size([1, 2, 3]), size([])")
    case("S5_unwind", "UNWIND ['hey'] AS x RETURN size(x)")
    case("S5_with_list", f"{C} WITH n.l AS l RETURN size(l)")
    # S6
    case("S6_stored", f"{C} RETURN toInteger(n.n42), toInteger(n.n29), toInteger(n.foo), toFloat(n.n42), toFloat(n.n29), toFloat(n.foo), toString(n.i7), toString(n.f25)")
    case("S6_literal", "RETURN toInteger('42'), toInteger('2.9'), toInteger('foo'), toFloat('42'), toFloat('2.9'), toFloat('foo'), toString(7), toString(2.5)")
    case("S6_unwind", "UNWIND ['42', '2.9', 'foo'] AS x RETURN x, toInteger(x), toFloat(x)")
    case("S6_bool", f"{C} RETURN toBoolean(n.flag), toString(n.flag)")
    # L1
    case("L1_rows", f"{C} UNWIND [[1, 3], [-3, -1], [3, 1], [-9, 9]] AS ab RETURN ab, n.l[ab[0]..ab[1]]")
    case("L1_rows_scalar", f"{C} UNWIND [1, -3, 3, -9] AS a RETURN a, n.l[a..3]")
    case("L1_literal", f"{C} RETURN n.l[1..3], n.l[-3..-1], n.l[3..1], n.l[-9..9]")
    case("L1_literal_list", "WITH [1, 2, 3, 4, 5] AS l RETURN l[1..3], l[-3..-1], l[3..1], l[-9..9]")
    case("L1_param", f"{C} RETURN n.l[$a..$b], n.l[$c..$d]", {"a": 1, "b": 3, "c": -3, "d": -1})
    # L2
    case("L2_stored", f"{C} RETURN n.l[2..], n.l[..-1]")
    case("L2_literal", "WITH [1, 2, 3, 4, 5] AS l RETURN l[2..], l[..-1]")
    # L3
    case("L3_stored", f"{C} RETURN 2 IN n.l, 9 IN n.l")
    case("L3_literal", "RETURN 2 IN [1, 2, 3, 4, 5], 9 IN [1, 2, 3, 4, 5]")
    # L4
    case("L4_stored", f"{C} RETURN [x IN n.l WHERE x > 2 | x * 10], [x IN n.e WHERE x > 2 | x * 10]")
    case("L4_literal", "WITH [1, 2, 3, 4, 5] AS l RETURN [x IN l WHERE x > 2 | x * 10]")
    # C1-C4
    case("C1_stored", f"{V} RETURN n.id, CASE n.v WHEN 1 THEN 'one' WHEN 2 THEN 'two' ELSE 'other' END ORDER BY n.id")
    case("C1_unwind", "UNWIND [1, 2, 3, null] AS v RETURN v, CASE v WHEN 1 THEN 'one' WHEN 2 THEN 'two' ELSE 'other' END")
    case("C2_stored", f"{V} RETURN n.id, CASE WHEN n.v > 1 THEN 'big' WHEN n.v IS NULL THEN 'none' ELSE 'small' END ORDER BY n.id")
    case("C2_unwind", "UNWIND [1, 2, 3, null] AS v RETURN v, CASE WHEN v > 1 THEN 'big' WHEN v IS NULL THEN 'none' ELSE 'small' END")
    case("C3_stored", f"{V} RETURN n.id, coalesce(n.missing, n.v, 'z') ORDER BY n.id")
    case("C3_literal", "RETURN coalesce(null, 1, 'z')")
    case("C4_stored", f"{V} WHERE n.flag IS NOT NULL RETURN n.id, CASE WHEN n.flag THEN 'y' ELSE 'n' END ORDER BY n.id")
    case("C4_unwind", "UNWIND [true, false] AS f RETURN f, CASE WHEN f THEN 'y' ELSE 'n' END")
    # A1-A3
    case("A1_stored", f"MATCH (n:{L}M) RETURN max(n.v), min(n.v)")
    case("A1_strings", f"{V} RETURN min(n.s), max(n.s)")
    case("A1_unwind", "UNWIND [1, 5, 3] AS v RETURN max(v), min(v)")
    case("A2_stored", f"{V} RETURN count(DISTINCT n.s)")
    case("A2_unwind", "UNWIND ['a', 'a', 'b', null] AS s RETURN count(DISTINCT s)")
    case("A3_stored", f"MATCH (n:{L}G) RETURN collect(n.l)")
    case("A3_unwind", "UNWIND [[1], [2, 3]] AS l RETURN collect(l)")

    # Writes W1-W5 (each on fresh nodes)
    e.execute_cypher(f"CREATE (:{L}W {{id: '{p}w1', s: 'ab', l: [1, 2, 3]}}), (:{L}W {{id: '{p}w1lit'}})")
    write("W1_runtime", f"MATCH (n:{L}W {{id: '{p}w1'}}) SET n.u = toUpper(n.s), n.c = size(n.l), n.h = n.l[0..2]",
          reads=[f"MATCH (n:{L}W {{id: '{p}w1'}}) RETURN n.u, n.c, n.h"], node_ids=[p + "w1"])
    write("W1_literal", f"MATCH (n:{L}W {{id: '{p}w1lit'}}) SET n.u = toUpper('ab'), n.c = size([1, 2, 3]), n.h = [1, 2, 3][0..2]",
          reads=[f"MATCH (n:{L}W {{id: '{p}w1lit'}}) RETURN n.u, n.c, n.h"], node_ids=[p + "w1lit"])
    write("W2_runtime", f"UNWIND ['{p}ab', '{p}cd'] AS s CREATE (:{L}X {{id: s, u: toUpper(s), k: size(s)}})",
          reads=[f"MATCH (n:{L}X) RETURN n.id, n.u, n.k ORDER BY n.id"], node_ids=[p + "ab"])
    write("W2_literal", f"CREATE (:{L}Y {{id: '{p}x', u: toUpper('ab'), k: size('ab')}})",
          reads=[f"MATCH (n:{L}Y) RETURN n.id, n.u, n.k"], node_ids=[p + "x"])
    write("W3_uuid", f"CREATE (:{L}R {{id: '{p}r', u: randomUUID()}})",
          reads=[f"MATCH (n:{L}R) RETURN n.id, n.u"], node_ids=[p + "r"])
    write("W3_rand", f"CREATE (:{L}R {{id: '{p}r1', f: rand()}})",
          reads=[f"MATCH (n:{L}R) RETURN n.id, n.f"], node_ids=[p + "r1"])
    write("W3_neighbor", f"CREATE (:{L}R {{id: '{p}r2', u: toString(1)}})",
          reads=[f"MATCH (n:{L}R) RETURN n.id, n.u"], node_ids=[p + "r2"])
    write("W3_set_uuid", f"MATCH (n:{L}R {{id: '{p}r2'}}) SET n.v = randomUUID()",
          reads=[f"MATCH (n:{L}R {{id: '{p}r2'}}) RETURN n.v"])
    e.execute_cypher(f"CREATE (:{L}A {{id: '{p}a1', age: '30'}}), (:{L}A {{id: '{p}a2', age: '30'}})")
    write("W4_runtime", f"MATCH (n:{L}A {{id: '{p}a1'}}) SET n.age = toInteger(n.age)",
          reads=[f"MATCH (n:{L}A {{id: '{p}a1'}}) RETURN n.age", f"MATCH (n:{L}A) WHERE n.age = 30 RETURN n.id ORDER BY n.id"],
          node_ids=[p + "a1"])
    write("W4_literal", f"MATCH (n:{L}A {{id: '{p}a2'}}) SET n.age = 30",
          reads=[f"MATCH (n:{L}A {{id: '{p}a2'}}) RETURN n.age", f"MATCH (n:{L}A) WHERE n.age = 30 RETURN n.id ORDER BY n.id"],
          node_ids=[p + "a2"])
    write("W5_runtime", f"UNWIND [1, 2] AS i CREATE (:{L}Z {{id: '{p}z' + toString(i), sq: i * i}})",
          reads=[f"MATCH (n:{L}Z) RETURN n.id, n.sq ORDER BY n.id"], node_ids=[p + "z1"])
    write("W5_literal", f"CREATE (:{L}Z {{id: '{p}w9', sq: 3 * 3}})",
          reads=[f"MATCH (n:{L}Z {{id: '{p}w9'}}) RETURN n.sq"], node_ids=[p + "w9"])
    c.close()
    dest = HERE / f"cypherexpr-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(dest)


if __name__ == "__main__":
    main()
