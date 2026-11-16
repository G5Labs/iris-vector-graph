"""Pinned-product regression witnesses, with ordinary passing caller neighbors.

PASS means the recorded defect contrast reproduced, not that the product is fixed.
Run with the pinned venv: python -B regressions.py. No vulnerability cases run.
"""
import importlib.util
import json
import logging
import sys
import time
import traceback
import types
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt

logging.disable(logging.CRITICAL)
HERE = rt.HERE
PROBES = rt.ROOT / ".g5/Verus_verification/native/probes"
RESULTS = []


def reset(e, native):
    # This helper is authorized only after rt.connect's dedicated-instance guard.
    e.ledger.disable()
    e.erase_all()
    native.classMethodValue("Graph.KG.Ledger", "PurgeAll")
    e.ledger._refresh_guard()


def sql(c, text, args=()):
    cur = c.cursor()
    try:
        cur.execute(text, list(args))
        return [list(r) for r in cur.fetchall()]
    finally:
        cur.close()


def q(e, text, args=None):
    r = e.execute_cypher(text, args or {}, raise_on_error=True)
    assert not r.error, r.error
    return [list(row) for row in r.rows]


def load(name):
    spec = importlib.util.spec_from_file_location(name, PROBES / (name + ".py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def run(name, ids, fn):
    start = time.monotonic()
    row = dict(name=name, ids=ids, level="e2e reproduced", providers="actual pinned Python, DB-API, IRIS SQL/ObjectScript; no substituted dependency")
    c = None
    try:
        import iris
        c = rt.connect()
        e = rt.engine(c)
        native = iris.createIRIS(c)
        reset(e, native)
        row["observation"] = fn(e, native, c)
        row["verdict"] = "REPRODUCED_WITH_PASSING_NEIGHBOR"
    except Exception as ex:
        row.update(verdict="INCONCLUSIVE", level="not reproduced", error=dict(type=type(ex).__name__, text=str(ex), trace=traceback.format_exc()))
    finally:
        if c:
            try:
                c.close()
            except Exception:
                pass
        row["elapsed_s"] = time.monotonic() - start
        RESULTS.append(row)
        (HERE / "regressions.json").write_text(json.dumps(RESULTS, indent=2, default=str) + "\n")
        print(name, row["verdict"], row.get("error", {}).get("text", ""), flush=True)


def optional(e, n, c):
    tail = "count(*),count(x),sum(x.v),avg(x.v),collect(x.v)"
    neighbor = q(e, "MATCH (x:NeverCreated) RETURN " + tail)
    assert neighbor == [[0, 0, 0, None, []]], neighbor
    got = q(e, "OPTIONAL MATCH (x:NeverCreated) RETURN x.kind," + tail)
    expected = [[None, 1, 0, 0, None, []]]
    assert got == [[None, 1, 0, None, None, []]], got
    return dict(neighbor=neighbor, actual=got, expected=expected)


def aliases(e, n, c):
    assert e.create_node("alias", properties={"id": "stored-id", "p_id": "user-value"})
    stored = sql(c, "SELECT key,val FROM Graph_KG.rdf_props WHERE s=? ORDER BY key", ["alias"])
    assert {r[0] for r in stored} >= {"id", "p_id"}, stored
    got = e.get_node("alias")
    assert got["id"] == "alias" and got["p_id"] in ["stored-id", "user-value"], got
    assert e.create_node("neighbor", properties={"ordinary": "kept"})
    neighbor = e.get_node("neighbor")
    assert neighbor["ordinary"] == "kept", neighbor
    return dict(stored=stored, actual=got, expected="both accepted property values recoverable", neighbor=neighbor)


def rel_text(e, n, c):
    observations = []
    for i, value in enumerate(["12\n", "1\u0662", "12x"]):
        assert e.create_edge("s", "R" + str(i), "o", qualifiers={"v": value})
        got = q(e, "MATCH ()-[r:R" + str(i) + "]->() RETURN r.v")
        observations.append(dict(input=value, output=got))
    assert observations[0]["output"] == [[12]], observations
    assert observations[1]["output"] == [[12]], observations
    assert observations[2]["output"] == [["12x"]], observations
    return dict(actual=observations[:2], expected="noncanonical numeric text stays text", neighbor=observations[2])


def temporal_time(e, n, c):
    assert e.create_edge_temporal("s", "T", "o")
    assert e.create_edge_temporal("s", "N", "o", timestamp=100)
    missing = e.get_edges_in_window("s", "T", 0, 100)
    neighbor = e.get_edges_in_window("s", "N", 100, 100)
    assert len(missing) == 1 and missing[0]["ts"] == 0, missing
    assert len(neighbor) == 1 and neighbor[0]["ts"] == 100, neighbor
    return dict(actual=missing, expected="missing timestamp resolves current server time", neighbor=neighbor)


def temporal_empty(e, n, c):
    assert e.create_edge_temporal("s", "T", "o", timestamp=100, weight=2)
    neighbor = e.get_temporal_aggregate("s", "T", "min", 100, 100)
    assert neighbor == 2.0, neighbor
    try:
        got = e.get_temporal_aggregate("s", "T", "min", 200, 200)
    except ValueError as ex:
        return dict(actual=dict(type="ValueError", text=str(ex)), expected=0.0, neighbor=neighbor)
    raise AssertionError(f"empty min did not raise: {got!r}")


def legacy_temporal(kind):
    def case(e, n, c):
        m = load("temporal_write_modes")
        s = "neighbor"
        assert e.create_edge_temporal(s, m.P, "o", timestamp=m.T, weight=2)
        neighbor = m.raw_view(e, n, s, "o")
        assert m.agg_matches(neighbor, {"count": 1, "sum": 2, "velocity": 1}), neighbor
        out = {}
        if kind == "update":
            m.case_update(e, n, out)
        elif kind == "partial":
            m.case_partial_write(e, n, out)
        else:
            m.case_bulk_fallback(e, n, kind.removeprefix("bulk_"), out)
        assert out["verdict"].startswith("OBSERVED_DEFECT"), out
        return dict(actual=out, neighbor=neighbor)
    return case


def rollback(kind):
    def case(e, n, c):
        m = load("temporal_rollback_counters")
        m.seed(e)
        # A successful committed write establishes the same writer and readers.
        assert e.create_edge_temporal("neighbor", m.P, "end", timestamp=100, weight=2)
        neighbor = m.stats(e, n, "neighbor", 100)
        assert m.exact(neighbor), neighbor
        out = {}
        getattr(m, "case_" + kind)(e, n, out)
        assert out["verdict"].startswith("OBSERVED_DEFECT"), out
        return dict(actual=out, neighbor=neighbor)
    return case


def multigraph(e, n, c):
    m = load("graph_structure_parallel_delete_rel")
    e.ledger.enable()
    # Single-edge graph verification is the passing neighbor.
    assert e.create_edge("ns", "N", "no", graph="neighbor")
    neighbor = e.verify_graph("neighbor")
    assert neighbor.get("ok", neighbor.get("healthy", False)), neighbor
    out = m.run_case(e, n, c, "parallel", "parallel")
    assert out["verify_before"]["ok"] in (False, 0), out
    verdict, reason = m.judge(out)
    assert verdict == "OBSERVED_DEFECT", (verdict, reason, out)
    return dict(actual=out, reason=reason, neighbor=neighbor)


def ppr_node(e, n, c):
    missing = e.kg_PERSONALIZED_PAGERANK(["new-seed"])
    assert not missing, missing
    assert e.create_node("new-seed")
    cached = e.kg_PERSONALIZED_PAGERANK(["new-seed"])
    assert not cached, cached
    # A real unrelated edge invalidates the existing graph cache through its owner.
    assert e.create_edge("a", "R", "b")
    neighbor = e.kg_PERSONALIZED_PAGERANK(["new-seed"])
    assert neighbor.get("new-seed", 0) > 0, neighbor
    return dict(actual=cached, expected="positive seed after creation", neighbor=neighbor)


def where_return(e, n, c):
    assert e.create_node("node", labels=["Ordinary"])
    neighbor = q(e, "MATCH (n:Ordinary) WHERE false RETURN n.id")
    assert neighbor == [], neighbor
    got = q(e, "MATCH (n:Ordinary) RETURN n.id WHERE false")
    assert got == [["node"]], got
    return dict(actual=got, expected="syntax refusal", neighbor=neighbor)


def null_key(e, n, c):
    assert e.create_node("node", labels=["Ordinary"], properties={"z": 3, "neighbor": 4})
    q(e, "MATCH (n:Ordinary) SET n.z = null")
    got = q(e, "MATCH (n:Ordinary) RETURN keys(n)")
    assert "z" in got[0][0], got
    q(e, "MATCH (n:Ordinary) REMOVE n.neighbor")
    neighbor = q(e, "MATCH (n:Ordinary) RETURN keys(n)")
    assert "neighbor" not in neighbor[0][0], neighbor
    return dict(actual=got, expected="z absent", neighbor=neighbor)


def rel_param(e, n, c):
    q(e, "CREATE (a:L {id:'a'})-[:R {q:$v}]->(b:L {id:'b'})", {"v": "value"})
    got = q(e, "MATCH ()-[r:R]->() RETURN r.q")
    assert got == [[None]], got
    q(e, "CREATE (a:L {id:'c'})-[:N {q:'value'}]->(b:L {id:'d'})")
    neighbor = q(e, "MATCH ()-[r:N]->() RETURN r.q")
    assert neighbor == [["value"]], neighbor
    return dict(actual=got, expected=[["value"]], neighbor=neighbor)


def rel_with(e, n, c):
    q(e, "WITH $v AS v CREATE (a:L {id:'a'})-[:R {q:v}]->(b:L {id:'b'})", {"v": "value"})
    raw = sql(c, "SELECT qualifiers FROM Graph_KG.rdf_edges WHERE p='R'")
    try:
        json.loads(raw[0][0])
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError(raw)
    try:
        got = q(e, "MATCH ()-[r:R]->() RETURN r.q")
        assert got == [[None]], got
    except Exception as ex:
        assert "CY_REL_PROP" in str(ex), str(ex)
        got = dict(error=str(ex), type=type(ex).__name__)
    q(e, "CREATE (a:L {id:'c'})-[:N {q:'value'}]->(b:L {id:'d'})")
    neighbor = q(e, "MATCH ()-[r:N]->() RETURN r.q")
    assert neighbor == [["value"]], neighbor
    return dict(actual=got, raw=raw, expected=[["value"]], neighbor=neighbor)


def foreach(e, n, c):
    try:
        q(e, "FOREACH (x IN $items | CREATE (:L {v:x}))", {"items": [1, 2, 3]})
    except SyntaxError as ex:
        got = dict(type=type(ex).__name__, text=str(ex))
        assert "x" in str(ex), got
    else:
        raise AssertionError("parameter FOREACH succeeded")
    q(e, "FOREACH (x IN [1,2,3] | CREATE (:N {v:x}))")
    neighbor = q(e, "MATCH (n:N) RETURN count(n)")
    assert neighbor == [[3]], neighbor
    return dict(actual=got, expected="three nodes", neighbor=neighbor)


def unwind_with(e, n, c):
    params = {"p": [{"id": "a"}, {"id": "b"}]}
    try:
        q(e, "UNWIND $p AS e WITH e CREATE (:L {id:e.id})", params)
    except Exception as ex:
        got = dict(type=type(ex).__name__, text=str(ex))
        assert "PARAMETER" in str(ex).upper(), got
    else:
        raise AssertionError("WITH form succeeded")
    q(e, "UNWIND $p AS e CREATE (:N {id:e.id})", params)
    neighbor = q(e, "MATCH (n:N) RETURN count(n)")
    assert neighbor == [[2]], neighbor
    return dict(actual=got, expected="two nodes", neighbor=neighbor)


def aql_string(e, n, c):
    assert e.create_node("end", properties={"url": "http://x"})
    assert e.create_edge("start", "URL", "end")
    try:
        e.execute_aql("FOR v IN 1..1 OUTBOUND 'start' URL FILTER v.url == 'http://x' RETURN v")
    except Exception as ex:
        got = dict(type=type(ex).__name__, text=str(ex))
        assert "RETURN" in str(ex), got
    else:
        raise AssertionError("URL string accepted")
    neighbor = e.execute_aql("FOR v IN 1..1 OUTBOUND 'start' URL FILTER v.url == 'ordinary' RETURN v")
    assert not neighbor.error and not list(neighbor.rows), neighbor
    return dict(actual=got, expected="ordinary string parsed and query run", neighbor=[])


def snapshot_types(e, n, c):
    import tempfile
    assert e.create_edge_temporal("s", "T", "o", timestamp=100, attrs={"n": 1, "label": "kept"}, graph="snap")
    before = list(e.iter_edges_in_window(0, 200, attrs=True, graph="snap"))
    assert before[0]["attrs"] == {"n": 1, "label": "kept"}, before
    with tempfile.TemporaryDirectory(prefix="ivg-register-snapshot-") as work:
        archive = str(Path(work) / "ordinary.zip")
        e.save_snapshot(archive)
        e.erase_all()
        e.restore_snapshot(archive)
    after = list(e.iter_edges_in_window(0, 200, attrs=True, graph="snap"))
    assert after[0]["attrs"] == {"n": "1", "label": "kept"}, after
    assert after[0]["w"] == before[0]["w"], (before, after)
    return dict(actual=after, expected=before, neighbor="text label and numeric weight preserved")


def snapshot_merge(e, n, c):
    import tempfile
    assert e.create_node("shared", properties={"kept": "archive"}, graph="archive")
    assert e.create_node("second", properties={"kept": "second"}, graph="archive")
    with tempfile.TemporaryDirectory(prefix="ivg-register-merge-") as work:
        archive = str(Path(work) / "ordinary.zip")
        e.save_snapshot(archive)
        e.erase_all()
        assert e.create_node("shared", properties={"kept": "live"}, graph="live")
        report = e.restore_snapshot(archive, merge=True)
    got = sql(c, "SELECT node_id FROM Graph_KG.nodes WHERE graph_id='archive' ORDER BY node_id")
    neighbor = e.get_node("shared", graph="live")
    assert len(got) == 1, (got, report)
    assert neighbor["kept"] == "live", neighbor
    return dict(actual=got, expected=[["second"], ["shared"]], neighbor=neighbor, report=report,
                qualification="attempt3 refuted the one-parent-per-graph subcase on this schema; two parents in one graph trigger the actual first-column skip")


def marker_adoption(e, n, c):
    outcomes = {}
    for method in ["create_edge", "store_edge"]:
        assert e.create_edge_temporal(method, "T", "end", timestamp=100)
        getattr(e, method)(method, "T", "end")
        assert e.delete_edge_temporal(method, "T", "end", 100)
        outcomes[method] = q(e, f"MATCH (s {{id:'{method}'}})-[r:T]->(o) RETURN count(r)")
    assert outcomes["create_edge"] == [[1]], outcomes
    assert outcomes["store_edge"] == [[0]], outcomes
    return dict(actual=outcomes["store_edge"], expected=[[1]], neighbor=outcomes["create_edge"])


def label_json(e, n, c):
    good = e.resolve_label_set(e.intern_label_set({"k": "ordinary"}))
    assert json.loads(good) == {"k": "ordinary"}, good
    bad = e.resolve_label_set(e.intern_label_set({"k": 'a"b'}))
    try:
        json.loads(bad)
    except json.JSONDecodeError:
        return dict(actual=bad, expected='{"k":"a\\"b"}', neighbor=good)
    raise AssertionError(bad)


def burst_predicate(e, n, c):
    now = int(time.time())
    e.bulk_create_edges_temporal([dict(s="hub",p="A",o=f"o{i}",ts=now-10) for i in range(5)], graph="burst")
    got = e.find_burst_nodes(predicate="B", window_seconds=300, threshold=3, now_ts=now, graph="burst")
    neighbor = e.find_burst_nodes(predicate="A", window_seconds=300, threshold=3, now_ts=now, graph="burst")
    assert any(x.get("id") == "hub" for x in got), got
    assert any(x.get("id") == "hub" for x in neighbor), neighbor
    return dict(actual=got, expected=[], neighbor=neighbor)


def stale_multigraph(e, n, c):
    e.set_multigraph("multi", True)
    assert e.create_edge("a", "R", "b", graph="multi")
    assert e.is_multigraph("multi")
    c2 = rt.connect()
    try:
        other = rt.engine(c2)
        other.set_multigraph("multi", False)
        assert not other.is_multigraph("multi")
        assert e.is_multigraph("multi")
        q(e, "USE GRAPH 'multi' MATCH (a {id:'a'}),(b {id:'b'}) CREATE (a)-[:R]->(b)")
        got = q(e, "USE GRAPH 'multi' MATCH ()-[r:R]->() RETURN count(r)")
        assert got == [[2]], got
        assert e.create_edge("s", "N", "o", graph="single")
        assert e.create_edge("s", "N", "o", graph="single") is False
        neighbor = q(e, "USE GRAPH 'single' MATCH ()-[r:N]->() RETURN count(r)")
        assert neighbor == [[1]], neighbor
        return dict(actual=got, expected=[[1]], neighbor=neighbor)
    finally:
        c2.close()


def ivf_cosine(e, n, c):
    v = lambda a,b: [a,b] + [0.0]*766
    for ident in ["long", "aligned"]:
        assert e.create_node(ident, graph="vectors")
    e.store_embeddings([dict(node_id="long",embedding=v(10,0)), dict(node_id="aligned",embedding=v(.1,.1))], graph="vectors")
    e.ivf_build("audit_cosine", nlist=1, metric="cosine", graph="vectors")
    got = e.ivf_search("audit_cosine", v(1,1), k=2)
    assert got[0][0] == "long" and float(got[0][1]) > 1, got
    # Unit-length one-axis query/candidate is the scale-preserving native neighbor.
    e.ivf_build("audit_dot", nlist=1, metric="dot", graph="vectors")
    neighbor = e.ivf_search("audit_dot", v(1,0), k=2)
    assert neighbor[0][0] == "long" and abs(float(neighbor[0][1])-10)<1e-5, neighbor
    return dict(actual=got, expected="aligned precedes long under cosine; scores in [-1,1]", neighbor=neighbor)


def knn_labels(e, n, c):
    v = lambda a,b: [a,b] + [0.0]*766
    assert e.create_node("a", labels=["LA", "LB"])
    assert e.create_node("b", labels=["LA"])
    e.store_embedding("a", v(1,0))
    e.store_embedding("b", v(.9,.1))
    query = json.dumps(v(1,0))
    got = sql(c, "SELECT node_id,score FROM Graph_KG.kg_KNN_VEC(?,?,?,?)", [query,2,None,""])
    assert [r[0] for r in got] == ["a","a"], got
    neighbor = sql(c, "SELECT node_id,score FROM Graph_KG.kg_KNN_VEC(?,?,?,?)", [query,2,"LA",""])
    assert [r[0] for r in neighbor] == ["a","b"], neighbor
    return dict(actual=got, expected="two distinct nearest node IDs", neighbor=neighbor)


def declared_knn(e, n, c):
    vector = [1.0] + [0.0]*767
    assert e.create_node("v", graph="declared")
    e.store_embedding("v", vector, graph="declared", model_key="audit-model")
    got = sql(c, "SELECT node_id,score FROM Graph_KG.kg_KNN_VEC(?,?,?,?)", [json.dumps(vector),2,None,"declared"])
    assert got == [], got
    neighbor = e.search_nodes_by_vector(vector,k=2,graph="declared",model_key="audit-model")
    assert neighbor, neighbor
    return dict(actual=got, expected="held vectors or an explicit unsupported-route error", neighbor=neighbor)


def runtime_range(e, n, c):
    got = q(e, "RETURN range(1,4,$step)", {"step": 0})
    neighbor = q(e, "RETURN range(1,4,$step)", {"step": 1})
    assert got == [[[]]], got
    assert neighbor == [[[1,2,3,4]]], neighbor
    return dict(actual=got, expected="NumberOutOfRange refusal", neighbor=neighbor)


def empty_call(e, n, c):
    assert e.create_node("anchor", labels=["Anchor"])
    prefix = "MATCH (a:Anchor) CALL { WITH a MATCH (a)-[:MISSING]->(n) RETURN "
    got = q(e, prefix + "max(n.v) AS m } RETURN m")
    neighbor = q(e, prefix + "count(n) AS c } RETURN c")
    assert got in [[["0"]], [[0]]], got
    assert neighbor == [[0]], neighbor
    return dict(actual=got, expected=[[None]], neighbor=neighbor)


def unknown_procedure(e, n, c):
    assert e.create_node("a", labels=["Known"])
    neighbor = q(e, "CALL db.labels() YIELD label RETURN label")
    assert ["Known"] in neighbor, neighbor
    got = q(e, "CALL db.unknownOrdinaryProcedure()")
    assert got == [], got
    return dict(actual=got, expected="clear unknown-procedure refusal", neighbor=neighbor)


def null_rel_pattern(e, n, c):
    assert e.create_edge("s", "R", "o")
    neighbor = q(e, "MATCH ()-[r:R]->() RETURN count(r)")
    assert neighbor == [[1]], neighbor
    try:
        q(e, "MATCH ()-[r:R {k:0}]->() RETURN count(r)")
    except Exception as ex:
        assert "SQL" in str(ex), str(ex)
        return dict(actual=dict(type=type(ex).__name__,text=str(ex)), expected=[[0]], neighbor=neighbor)
    raise AssertionError("null qualifier pattern did not raise")


def bm25_id(e, n, c):
    assert e.create_node("part:.5", properties={"name": "ordinaryterm"}, graph="text")
    assert e.create_node("neighbor", properties={"name": "neighborterm"}, graph="text")
    e.bm25_build("audit_text", ["name"], graph="text")
    got = e.bm25_search("audit_text", "ordinaryterm", k=3)
    neighbor = e.bm25_search("audit_text", "neighborterm", k=3)
    assert got and got[0][0] == "part:0.5", got
    assert neighbor and neighbor[0][0] == "neighbor", neighbor
    return dict(actual=got, expected="stored ID part:.5 unchanged", neighbor=neighbor)


def membership_reserved(e, n, c):
    assert e.create_edge("components", "R", "b")
    result = e._store.execute_wcc()
    assert result.error, (result.error, list(result.rows))
    got = dict(error=result.error)
    fallback = e.kg_WCC()
    assert fallback["components"] == fallback["b"], fallback
    assert e.delete_node("components")
    assert e.create_edge("ordinary", "R", "b")
    neighbor = e.kg_WCC()
    assert neighbor["ordinary"] == neighbor["b"], neighbor
    return dict(actual=got, expected="membership for every accepted node ID", neighbor=neighbor,
                qualification="Public SQL GraphStore execute_wcc fails; public engine WCC successfully falls back. No claim that engine WCC fails.", engine_fallback=fallback)


def pagerank_cap(e, n, c):
    assert e.create_node("neighbor")
    neighbor = e.kg_PAGERANK(max_iterations=1)
    assert neighbor == [("neighbor", 1.0)], neighbor
    e.bulk_create_nodes([dict(id=f"node{i}") for i in range(10001)])
    assert e.get_node_count() == 10002
    got = e.kg_PAGERANK(max_iterations=1)
    assert len(got) == 10000, len(got)
    total = sum(score for _,score in got)
    assert total < .9999, total
    return dict(actual=dict(listed=len(got),score_sum=total), expected=dict(listed=10002,score_sum=1.0),
                neighbor=neighbor, qualification="Real public engine and ObjectScript Owner. No Arno reader is available, so native-versus-Owner route equivalence remains untested.")


def main():
    # Reuse selected reviewed scenario functions, replacing only their test-runtime locator.
    stub = types.ModuleType("harness")
    stub.connect = rt.connect
    stub.engine = rt.engine
    stub.ensure_schema = lambda e: {"reused": "runtime.json"}
    stub.reset = reset
    stub.record = lambda *a: None
    sys.modules["harness"] = stub
    sys.path.insert(0, str(PROBES))
    load("graph_structure_common")
    cases = [
        ("optional_grouped_sum", ["bug-agg-001"], optional),
        ("node_alias_collision", ["bug-str-101"], aliases),
        ("relationship_text", ["bug-cyp-101"], rel_text),
        ("missing_temporal_time", ["bug-tmp-007", "F-0502"], temporal_time),
        ("empty_temporal_min", ["bug-tmp-009"], temporal_empty),
        ("temporal_update_counts", ["bug-tmp-002"], legacy_temporal("update")),
        ("temporal_partial_retry", ["bug-tmp-001", "F-C0501"], legacy_temporal("partial")),
        ("temporal_bulk_insert", ["bug-tmp-001"], legacy_temporal("insert")),
        ("temporal_bulk_update", ["bug-tmp-001"], legacy_temporal("bulk_update")),
        *[("temporal_rollback_" + k, ["bug-tmp-003"] if k in ["r1", "r2", "r3", "r4"] else ["bug-tmp-010"], rollback(k))
          for k in ["r1", "r2", "r3", "r4", "r5", "r5b", "r6"]],
        ("parallel_ledger_delete", ["bug-str-001", "bug-str-004", "F-0204", "F-0403"], multigraph),
        ("ppr_edgeless_seed", ["bug-plt-017", "F-1004"], ppr_node),
        ("where_after_return", ["F-0803"], where_return),
        ("set_literal_null", ["F-0810"], null_key),
        ("relationship_parameter", ["F-C0848"], rel_param),
        ("relationship_with", ["F-C0849"], rel_with),
        ("foreach_parameter", ["F-0808"], foreach),
        ("unwind_with", ["F-0822"], unwind_with),
        ("aql_string_comment", ["F-0824"], aql_string),
        ("snapshot_temporal_types", ["F-1804"], snapshot_types),
        ("snapshot_merge_parent", ["bug-plt-004", "F-1802"], snapshot_merge),
        ("store_edge_marker_adoption", ["F-0304"], marker_adoption),
        ("label_set_json", ["F-0509"], label_json),
        ("burst_predicate", ["F-0508"], burst_predicate),
        ("stale_multigraph", ["F-0208", "bug-str-008"], stale_multigraph),
        ("ivf_cosine", ["F-0607"], ivf_cosine),
        ("knn_label_multiplicity", ["F-C0602"], knn_labels),
        ("declared_model_knn", ["F-0610"], declared_knn),
        ("runtime_range_zero", ["F-C0841"], runtime_range),
        ("empty_call_max", ["F-0823"], empty_call),
        ("unknown_procedure", ["F-0817"], unknown_procedure),
        ("null_relationship_pattern", ["F-C0101"], null_rel_pattern),
        ("bm25_result_id", ["F-C0715"], bm25_id),
        ("membership_reserved_id", ["F-C1018"], membership_reserved),
        ("pagerank_owner_cap", ["F-1003"], pagerank_cap),
    ]
    if sys.argv[1:]:
        names = set(sys.argv[1:])
        RESULTS.extend(r for r in json.loads((HERE / "regressions.json").read_text()) if r["name"] not in names)
        cases = [c for c in cases if c[0] in names]
    for name, ids, fn in cases:
        run(name, ids, fn)
    print(json.dumps(dict(total=len(RESULTS), reproduced=sum(r["verdict"].startswith("REPRODUCED") for r in RESULTS))))
    return 0 if all(r["verdict"] == "REPRODUCED_WITH_PASSING_NEIGHBOR" for r in RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
