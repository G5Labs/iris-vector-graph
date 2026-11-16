"""temporal_marker binding: actual writers on the run-isolated IRIS fixture vs a port of the model's rules.

Every history of length 1..3 over {temporal 1.5, temporal 1.0, create_edge, create_edge(weight=5.0),
bulk_create_edges} on its own fresh default-graph triple, plus single temporal writes at further weights.
Readers: the raw row, export_graph_ndjson (one export, lines selected by ID), export_rdf (filtered by node ID,
parsed back) and Cypher properties(r). The port mirrors temporal_marker.rs; the explicit writer's own qualifier
text is a provider observed on a separate fresh triple. Six port mutations mirror the model controls and must
each disagree with at least one actual observation.

Ordinary data on the identity-checked fixture only; no other database, socket or Git use beyond the fixture.
"""
import hashlib
import itertools
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(Path(os.environ.get("IVG_RUNTIME_DIR", str(REPO / ".g5/uplift/consolidated/iteration-15")))))
import runtime  # noqa: E402  (fixture identity guard, pin on sys.path)

RUN = os.environ.get("TM_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
OPS = {"T15": ("temporal", 1.5), "T1": ("temporal", 1.0), "E": ("explicit", None), "E5": ("explicit", 5.0), "B": ("bulk", None)}
EXTRA_WEIGHTS = [2.0, 0.5, 3.25, 10.0, 0.75]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------- port of temporal_marker.rs ----------------
def os_number(w):
    """Model premise: the provider's JSON spelling of +pWeight (canonical, leading zero kept)."""
    x = float(w)
    return str(int(x)) if x == int(x) else repr(x)


def marker(w):
    sp = os_number(w)
    return '{"temporal":true}' if sp == "1" else '{"temporal":true,"weight":' + sp + "}"


def decode(q):
    if not q:
        return {}
    try:
        d = json.loads(q)
    except ValueError:
        return None  # outside the model's recognizer
    return d if isinstance(d, dict) else None


def object_marked(q):
    d = decode(q)
    return isinstance(d, dict) and d.get("temporal") is True


def sql_marked(q):
    return q is not None and q.startswith('{"temporal"')


ABSENT = ("absent",)


def step(row, op, own, rules):
    kind, w = OPS[op] if isinstance(op, str) else op
    if kind == "temporal":
        if row == ABSENT or rules.get("temporal_overwrites"):
            return ("row", marker(w) if not rules.get("unit_weight_written") else '{"temporal":true,"weight":' + os_number(w) + "}")
        return row
    if kind == "explicit":
        mine = own[w]
        if row == ABSENT:
            return ("row", mine)
        if rules.get("adoption_ignores_marker") or object_marked(row[1]):
            return ("row", mine)
        return row
    if kind == "bulk":
        if row == ABSENT:
            return ("row", None)
        if sql_marked(row[1]) and not rules.get("bulk_keeps_marker"):
            return ("row", None)
        return row
    raise ValueError(op)


def readers(row, rules):
    q = row[1]
    d = decode(q) or {}
    keys = sorted(d)
    if rules.get("cypher_hides_marker"):
        keys = [k for k in keys if k != "temporal"]
    ndjson = (not sql_marked(q)) or bool(rules.get("ndjson_writes_marked"))
    quals = [k for k in d if k != "inferred"] if d else []
    rdf_edge = {"spo": 1, "envelope": 4 if d else 0, "qualifier_keys": sorted(quals)}
    return {"cypher_keys": keys, "ndjson_line": ndjson, "rdf": rdf_edge}


def predict(history, own, rules=None):
    rules = rules or {}
    row = ABSENT
    for op in history:
        row = step(row, op, own, rules)
    return {"row": row[1], **readers(row, rules)}


# ---------------- actual product ----------------
def apply(e, a, b, op):
    kind, w = OPS[op] if isinstance(op, str) else op
    if kind == "temporal":
        e.create_edge_temporal(a, "KNOWS", b, timestamp=1700000000, weight=w)
    elif kind == "explicit":
        e.create_edge(a, "KNOWS", b) if w is None else e.create_edge(a, "KNOWS", b, weight=w)
    else:
        e.bulk_create_edges([{"source_id": a, "predicate": "KNOWS", "target_id": b}])


def raw_rows(c, a):
    cur = c.cursor()
    try:
        cur.execute("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ? AND p = 'KNOWS'", [a])
        return [r[0] for r in cur.fetchall()]
    finally:
        cur.close()


def observe_rdf(e, a, b, d):
    from rdflib import ConjunctiveGraph, URIRef, BNode
    path = Path(d) / f"{a}.nq"
    rep = e.export_rdf(str(path), format="nquads", node_ids=[a, b])
    g = ConjunctiveGraph()
    g.parse(str(path), format="nquads")
    spo = sum(1 for s, p, o in g.triples((None, None, None)) if isinstance(s, URIRef) and str(p).endswith("KNOWS"))
    env = sum(1 for s, p, o in g.triples((None, None, None)) if isinstance(s, BNode) and "22-rdf-syntax-ns#" in str(p))
    qk = sorted(str(p).rsplit("/", 1)[1] for s, p, o in g.triples((None, None, None)) if "urn:ivg:qualifier/" in str(p))
    return {"spo": spo, "envelope": env, "qualifier_keys": qk}, {k: rep[k] for k in ("triples", "nodes", "edges")}, sha(path)


def main():
    start = time.monotonic()
    c = runtime.connect()
    e = runtime.engine(c)
    histories = [h for n in (1, 2, 3) for h in itertools.product(list(OPS), repeat=n)]
    histories += [(("temporal", w),) for w in EXTRA_WEIGHTS]
    # provider: the explicit writer's own qualifier text on a separate fresh triple
    own = {None: None}
    pa, pb = f"tm{RUN}prova", f"tm{RUN}provb"
    for x in (pa, pb):
        e.create_node(x, labels=["P"])
    e.create_edge(pa, "KNOWS", pb, weight=5.0)
    own[5.0] = raw_rows(c, pa)[0]
    worlds = []
    with tempfile.TemporaryDirectory() as d:
        for i, h in enumerate(histories):
            a, b = f"tm{RUN}w{i}a", f"tm{RUN}w{i}b"
            for x in (a, b):
                e.create_node(x, labels=["P"])
            errors = []
            for op in h:
                try:
                    apply(e, a, b, op)
                except Exception as x:  # recorded; a write error is an observation, not hidden
                    errors.append(f"{op}: {type(x).__name__}: {x}")
            rows = raw_rows(c, a)
            try:
                rdf, report, file_sha = observe_rdf(e, a, b, d)
            except Exception as x:
                rdf, report, file_sha = f"ERROR {type(x).__name__}: {x}", None, None
            try:
                got = e.execute_cypher(f"MATCH (x)-[r:KNOWS]->(y) WHERE x.id = '{a}' RETURN properties(r) AS p")["rows"]
                ckeys = sorted(got[0][0]) if got else None
            except Exception as x:
                ckeys = f"ERROR {type(x).__name__}: {x}"
            worlds.append({"history": [op if isinstance(op, str) else list(op) for op in h], "ids": [a, b], "rows": rows,
                           "write_errors": errors, "rdf": rdf, "rdf_report": report, "rdf_file_sha256": file_sha,
                           "cypher_keys": ckeys})
        nd = Path(d) / "all.ndjson"
        e.export_graph_ndjson(str(nd))
        lines = [json.loads(x) for x in nd.read_text().splitlines()]
        edges_by_source = {}
        for ln in lines:
            if ln["kind"] == "edge":
                edges_by_source.setdefault(ln["source"], []).append(ln)
        ndjson_sha = sha(nd)
    c.close()
    mismatches = []
    for wd, h in zip(worlds, histories):
        got = {"row": wd["rows"][0] if len(wd["rows"]) == 1 else ("MULTI", wd["rows"]),
               "cypher_keys": wd["cypher_keys"], "ndjson_line": bool(edges_by_source.get(wd["ids"][0])), "rdf": wd["rdf"]}
        wd["ndjson_edge_lines"] = edges_by_source.get(wd["ids"][0], [])
        want = predict(h, own)
        wd["expected"] = want
        wd["observed"] = got
        if got != want or wd["write_errors"]:
            mismatches.append({"history": wd["history"], "expected": want, "observed": got, "write_errors": wd["write_errors"]})
    sensitivities = {}
    for rule in ["temporal_overwrites", "unit_weight_written", "adoption_ignores_marker", "bulk_keeps_marker",
                 "ndjson_writes_marked", "cypher_hides_marker"]:
        detected = sum(1 for wd, h in zip(worlds, histories) if predict(h, own, {rule: True}) != wd["observed"])
        sensitivities[rule] = detected
    body = {
        "kind": "binding", "model": "temporal_marker", "fixture": runtime.NAME, "port": runtime.PORT, "run": RUN,
        "product_baseline": runtime.PRODUCT, "verdict": "AGREES" if not mismatches else "DISAGREES",
        "worlds": len(worlds), "comparisons": 4 * len(worlds), "mismatches": mismatches,
        "explicit_provider_text": {repr(k): v for k, v in own.items()}, "sensitivities_detected_worlds": sensitivities,
        "all_sensitivities_detected": all(v > 0 for v in sensitivities.values()),
        "ndjson_file_sha256": ndjson_sha, "elapsed_s": time.monotonic() - start,
        "inputs": {str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "temporal_marker.rs", HERE / "model.json"]},
        "scope": "Default-graph single-row triples; actual temporal, explicit and bulk writers on IRIS 2026.1 Community; "
                 "actual NDJSON/RDF/Cypher readers. Explicit qualifier text and ObjectScript number spelling are providers. "
                 "No named-graph, multigraph-key, purge, concurrency or failure paths.",
    }
    out = REPO / ".g5/Verus_verification/results/temporal_marker" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True)
    (out / "worlds.json").write_text(json.dumps(worlds, indent=1, default=str) + "\n")
    body["worlds_sha256"] = sha(out / "worlds.json")
    (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "worlds", "comparisons", "all_sensitivities_detected", "sensitivities_detected_worlds", "elapsed_s")}, indent=1))
    for m in mismatches[:12]:
        print("MISMATCH", json.dumps(m, default=str)[:600])
    print(out / "receipt.json")


if __name__ == "__main__":
    main()
