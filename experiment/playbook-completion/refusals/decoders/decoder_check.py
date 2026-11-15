#!/usr/bin/env python3
"""§3.5 decoder / status-map check for modules 07 (text search), 10 (algorithms) and 18 (snapshots) at the pin.

    python decoder_check.py [--json OUT]          # the static map; exit 1 when a decoder reads what no server emits
    python decoder_check.py --self-test           # seeded defects in copies must each be reported

Pattern: tools/decoder_map_check.py (the ledger's 15 wire codes). Everything is extracted from source text at the pin;
nothing runs. For each decoder in SPEC:

  wire keys     server side: the keys an ObjectScript producer method emits - `%Set("key"`, the JSON-literal form
                `""key"":` and the dynamic-object literal `{"key": (` - and whether it emits dynamic keys (a map);
  decoder keys  client side: the keys the Python decoder reads (`x["key"]`, `.get("key")`, `"key" in x`,
                `.pop("key")`, and `for k in NAME` over a module-level tuple of keys);
  reported      `dead_reads`  keys the decoder reads that no producer emits (a dead mapping: the decoder expects a
                              shape the server never sends);
                `dropped`     keys a projecting decoder never reads although the producer emits them;
                `undocumented` / `doc_not_emitted`: keys the decoder's docstring promises vs the wire.

Error-code / status maps (MAPS): the error-text tokens or codes each Python map keys on, the status codes an HTTP
route can answer, and ALG-I5's propagation map (every engine method that calls a store `execute_*` must raise the
store's error, by `_raise_store_error` or an `.error` test that falls back to the owner): `unmapped` lists a call
whose error is dropped. Number and text encodings the JSON-literal producers write by concatenation are listed with
their guard (`jsonNum`/`jsonEsc` or the leading-dot fix) so the live script can drive the unguarded ones.

Self-test: in copies, (1) the `score` key is removed from Graph.KG.PageRank's producer -> `dead_reads` of the
scored-node decoder; (2) a store call without `_raise_store_error` is injected into an engine method -> ALG-I5
`unmapped`; (3) the snapshot import decoder reads a key no producer emits -> `dead_reads`; (4) Graph.KG.Snapshot's
Encode emits a new value form -> `undecoded_forms`. Each must be reported, and the unmodified tree must not report
them.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parents[4]
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
KG = "iris_src/src/Graph/KG"

# ------------------------------------------------------------------------------------------------ source access

def cls_method(root: Path, cls_path: str, method: str) -> Tuple[str, int, int]:
    lines = (root / cls_path).read_text(encoding="utf-8", errors="replace").splitlines()
    start = next(i for i, l in enumerate(lines) if re.match(rf"^(Class)?Method {re.escape(method)}\(", l))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "}")
    return "\n".join(lines[start:end + 1]), start + 1, end + 1


def py_func(root: Path, py_path: str, name: str) -> Tuple[str, int, int, Optional[str], ast.AST]:
    src = (root / py_path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or "", node.lineno, node.end_lineno, ast.get_docstring(node), node
    raise KeyError(f"{py_path}: no function {name}")


def module_tuples(root: Path, py_path: str) -> Dict[str, Tuple[str, ...]]:
    tree = ast.parse((root / py_path).read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = node.value
            if isinstance(v, (ast.Tuple, ast.List)) and all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                                                             for e in v.elts):
                out[node.targets[0].id] = tuple(e.value for e in v.elts)
    return out


SERVER_KEY_RES = [re.compile(r'%Set\("(\w+)"'), re.compile(r'""(\w+)"":'), re.compile(r'\{"(\w+)":\s*\('),
                  re.compile(r',\s*"(\w+)":\s*\(')]
DYNAMIC_SET = re.compile(r'%Set\((?!")')


def server_keys(body: str) -> Tuple[Set[str], bool]:
    keys: Set[str] = set()
    for rx in SERVER_KEY_RES:
        keys |= set(rx.findall(body))
    return keys, bool(DYNAMIC_SET.search(body))


READ_RES = [re.compile(r'\[\s*"(\w+)"\s*\]'), re.compile(r'\.get\(\s*"(\w+)"'),
            re.compile(r'"(\w+)"\s+(?:not\s+)?in\s+(?!(?:str\()?(?:err|err_str|error|exc|e|msg)\b)[\w.\[\]"]+'),
            re.compile(r'\.pop\(\s*"(\w+)"')]
#: reads that are not of the wire: capability flags of the engine and the store
NOT_WIRE = re.compile(r'(?:_store_capabilities|capabilities\(\))\.get\(\s*"\w+"[^)]*\)')


def client_reads(src: str, tuples: Dict[str, Tuple[str, ...]]) -> Set[str]:
    # strip the docstring and comments so prose does not count as a read
    body = re.sub(r'"""[\s\S]*?"""', "", src)
    body = "\n".join(l.split("#", 1)[0] if '"#' not in l else l for l in body.splitlines())
    body = NOT_WIRE.sub("", body)
    keys: Set[str] = set()
    for rx in READ_RES:
        keys |= set(rx.findall(body))
    for name, vals in tuples.items():
        if re.search(rf"for \w+ in {name}\b", body):
            keys |= set(vals)
    return keys


def doc_keys(doc: Optional[str]) -> Set[str]:
    return set(re.findall(r'``"(\w+)"``|"(\w+)"', doc or "")[0:0]) | {a or b for a, b in re.findall(r'``"(\w+)"``|``(\w+)``', doc or "")}


# ------------------------------------------------------------------------------------------------ the spec

# kind: projecting (reads named keys into a fixed structure) or pass-through (returns the server's dict as it is)
SPEC: List[dict] = [
    # ---- 07 text search
    {"module": "07", "name": "bm25_build <- BM25Index.Build", "kind": "pass-through",
     "server": [(f"{KG}/BM25Index.cls", "Build")], "client": [("iris_vector_graph/_engine/vector.py", "bm25_build")],
     "doc": ["indexed", "avgdl", "vocab_size", "graph"]},
    {"module": "07", "name": "bm25_search <- BM25Index.Search/SearchCore", "kind": "projecting",
     "server": [(f"{KG}/BM25Index.cls", "SearchCore")], "client": [("iris_vector_graph/_engine/vector.py", "bm25_search")],
     "ignore_reads": ["results", "skipped", "fallback"]},
    {"module": "07", "name": "bm25_search(report=True) <- BM25Index.SearchReport", "kind": "projecting",
     "server": [(f"{KG}/BM25Index.cls", "SearchReport"), (f"{KG}/BM25Index.cls", "SearchCore")],
     "client": [("iris_vector_graph/_engine/vector.py", "bm25_search")]},
    {"module": "07", "name": "bm25_upgrade <- BM25Index.Upgrade", "kind": "pass-through",
     "server": [(f"{KG}/BM25Index.cls", "Upgrade")], "client": [("iris_vector_graph/_engine/vector.py", "bm25_upgrade")],
     "doc": ["upgraded", "docs", "vocab", "postings", "already"]},
    {"module": "07", "name": "bm25_info / _index_graph <- BM25Index.Info", "kind": "pass-through",
     "server": [(f"{KG}/BM25Index.cls", "Info")],
     "client": [("iris_vector_graph/_engine/vector.py", "bm25_info"), ("iris_vector_graph/_engine/vector.py", "_index_graph")],
     "doc": ["N", "avgdl", "vocab_size", "graph", "schema", "type"], "client_adds": ["type"]},
    # ---- 10 algorithms
    {"module": "10", "name": "_scored_node_rows <- PageRank.RunJson / PageRankGlobalJson", "kind": "projecting",
     "server": [(f"{KG}/PageRank.cls", "RunJson"), (f"{KG}/PageRank.cls", "PageRankGlobalJson"),
                (f"{KG}/PageRank.cls", "WithUnscored")],
     "client": [("iris_vector_graph/stores/iris_sql_store.py", "_scored_node_rows")],
     "tuples": "iris_vector_graph/stores/iris_sql_store.py", "accepts_either": [["id", "node"]]},
    {"module": "10", "name": "_kg_pagerank_global fallback <- PageRank.PageRankGlobalJson", "kind": "projecting",
     "server": [(f"{KG}/PageRank.cls", "PageRankGlobalJson")],
     "client": [("iris_vector_graph/_engine/algorithms.py", "_kg_pagerank_global")]},
    {"module": "10", "name": "_membership_rows <- Algorithms.WCCJson / CDLPJson", "kind": "map",
     "server": [(f"{KG}/Algorithms.cls", "WCCJson"), (f"{KG}/Algorithms.cls", "CDLPJson")],
     "client": [("iris_vector_graph/stores/iris_sql_store.py", "_membership_rows")],
     "tuples": "iris_vector_graph/stores/iris_sql_store.py",
     "summary_keys_tuple": "_SUMMARY_KEYS",
     "dead_ok": {"id": "the row-list form: no Owner producer at the pin emits it (both answer a map); the Native "
                       "Reader's row lists are blocked here (no x86_64 libarno_callout.so, F-1001)",
                 "node": "as 'id'"}},
    {"module": "10", "name": "_subgraph_payload / kg_SUBGRAPH <- Subgraph.SubgraphJson", "kind": "projecting",
     "server": [(f"{KG}/Subgraph.cls", "SubgraphJson")],
     "client": [("iris_vector_graph/stores/iris_sql_store.py", "_subgraph_payload"),
                ("iris_vector_graph/_engine/algorithms.py", "kg_SUBGRAPH")],
     "ignore_reads": ["src", "dst"], "accepts_either": [["o", "o_id"]]},
    {"module": "10", "name": "execute_degree_centrality <- Centrality.DegreeCentralityJson", "kind": "projecting",
     "server": [(f"{KG}/Centrality.cls", "DegreeCentralityJson")],
     "client": [("iris_vector_graph/stores/iris_sql_store.py", "execute_degree_centrality")]},
    {"module": "10", "name": "khop <- TraversalBFS.BFSFastJson", "kind": "projecting",
     "server": [(f"{KG}/TraversalBFS.cls", "BFSFastJson"), (f"{KG}/TraversalBFS.cls", "BFSFastJsonDirect")],
     "client": [("iris_vector_graph/_engine/algorithms.py", "_khop_fallback")]},
    # ---- 18 snapshots
    {"module": "18", "name": "global value line <- Snapshot.NodeValueJSON/Encode; import -> SetNodeJSON/Decode",
     "kind": "forms", "server": [(f"{KG}/Snapshot.cls", "Encode")],
     "client": [("iris_vector_graph/_engine/snapshot.py", "_import_global_from_ndjson")],
     "python_writes": [("iris_vector_graph/_engine/snapshot.py", "_export_global_to_ndjson")],
     "server_decoder": [(f"{KG}/Snapshot.cls", "Decode")]},
    {"module": "18", "name": "snapshot_info / restore_snapshot <- metadata.json (save_snapshot)", "kind": "metadata",
     "client": [("iris_vector_graph/_engine/snapshot.py", "snapshot_info"),
                ("iris_vector_graph/_engine/snapshot.py", "restore_snapshot")],
     "python_writes": [("iris_vector_graph/_engine/snapshot.py", "save_snapshot")]},
]

MAPS: List[dict] = [
    {"module": "07", "name": "kg_TXT iFind error-text -> LIKE fallback / warning / raise",
     "py": ("iris_vector_graph/_engine/vector.py", "kg_TXT"), "tokens_in": "err"},
    {"module": "10", "name": "_RUNJSON_MISSING (PPR fast path falls back only on a missing RunJson)",
     "py_regex": ("iris_vector_graph/_engine/algorithms.py", "_RUNJSON_MISSING")},
    {"module": "10", "name": "execute_degree_centrality: CLASS DOES NOT EXIST / DBSRV -> gref fallback",
     "py": ("iris_vector_graph/stores/iris_sql_store.py", "execute_degree_centrality"), "tokens_in": "err_str"},
    {"module": "10", "name": "_refused_work_area: <THROW>/<PROTECT> -> privilege message",
     "py": ("iris_vector_graph/_engine/algorithms.py", "_refused_work_area"), "tokens_in": "error"},
    {"module": "10", "name": "_runjson_failure: <PARAMETER>RunJson^ -> redeploy hint",
     "py": ("iris_vector_graph/_engine/algorithms.py", "_runjson_failure"), "tokens_in": "exc"},
    {"module": "18", "name": "_table_missing: SQLCODE -30 -> skip lazily created table, else SnapshotReadError",
     "py_regex": ("iris_vector_graph/_engine/snapshot.py", "_SQLCODE_MINUS_30")},
    {"module": "18", "name": "POST /admin/snapshot HTTP status map", "http_route": ("iris_vector_graph/cypher_api.py",
                                                                                     "admin_snapshot_save")},
]


# ------------------------------------------------------------------------------------------------ checks

def check_decoder(root: Path, d: dict) -> dict:
    srv: Set[str] = set()
    dynamic = False
    srv_refs = []
    for path, m in d.get("server", []):
        body, a, b = cls_method(root, path, m)
        k, dyn = server_keys(body)
        srv |= k
        dynamic |= dyn
        srv_refs.append(f"{path}:{a}-{b}")
    reads: Set[str] = set()
    cli_refs = []
    docs: Set[str] = set()
    tuples = module_tuples(root, d["tuples"]) if d.get("tuples") else {}
    for path, f in d.get("client", []):
        src, a, b, doc, _ = py_func(root, path, f)
        reads |= client_reads(src, tuples)
        cli_refs.append(f"{path}:{a}-{b}")
    out = {"module": d["module"], "name": d["name"], "kind": d["kind"], "server": srv_refs, "client": cli_refs}
    if d["kind"] == "forms":
        # value forms: server Encode's object keys vs Python import's reads and server Decode's reads
        dec_body, a, b = cls_method(root, *d["server_decoder"][0])
        dec_reads = set(re.findall(r'%IsDefined\("(\w+)"\)', dec_body)) | set(re.findall(r'pObj\.(\w+)', dec_body))
        pyw: Set[str] = set()
        for path, f in d["python_writes"]:
            src, a2, b2, _, _ = py_func(root, path, f)
            pyw |= set(re.findall(r'\{"(\w+)":', src)) | set(re.findall(r'"(\w+)":\s*str\(', src))
            out.setdefault("python_writer", []).append(f"{path}:{a2}-{b2}")
        out["server_decoder"] = f"{d['server_decoder'][0][0]}:{a}-{b}"
        out["server_forms"] = sorted(srv)
        out["python_forms"] = sorted(pyw)
        out["client_reads"] = sorted(reads)
        out["server_decoder_reads"] = sorted(dec_reads)
        emitted = srv | pyw
        out["dead_reads"] = sorted(reads - emitted)
        out["undecoded_forms"] = sorted(srv - (reads | dec_reads))
        out["notes"] = ("plain values travel as {'k','v': str(value)}: the value's type is not encoded "
                        "(F-1804); $vector and $List-of-$vector travel as 'vec'/'list' and are decoded server-side")
        return out
    if d["kind"] == "metadata":
        pyw = set()
        for path, f in d["python_writes"]:
            src, a2, b2, _, _ = py_func(root, path, f)
            m = re.search(r"metadata: Dict\[str, Any\] = \{([\s\S]*?)\n        \}", src)
            pyw |= set(re.findall(r'^\s*"(\w+)":', m.group(1), re.M)) if m else set()
            pyw |= set(re.findall(r'metadata\["(\w+)"\]\s*=', src))
            pyw |= {"routed_tables"} if "ROUTED_TABLES_KEY: {}" in src else set()
            out.setdefault("python_writer", []).append(f"{path}:{a2}-{b2}")
        meta_reads = set()
        for path, f in d["client"]:
            src, _, _, _, _ = py_func(root, path, f)
            meta_reads |= set(re.findall(r'metadata\.get\(\s*"(\w+)"', src)) | set(re.findall(r'metadata\["(\w+)"\]', src))
            meta_reads |= {"routed_tables"} if "metadata.get(ROUTED_TABLES_KEY" in src else set()
        out["written"] = sorted(pyw)
        out["read"] = sorted(meta_reads)
        out["dead_reads"] = sorted(meta_reads - pyw)
        out["written_not_read"] = sorted(pyw - meta_reads)
        return out
    reads -= set(d.get("ignore_reads", []))
    reads -= set(d.get("client_adds", []))
    out["wire_keys"] = sorted(srv)
    out["dynamic_keys"] = dynamic
    out["decoder_reads"] = sorted(reads)
    dead = reads - srv
    for group in d.get("accepts_either", []):
        if set(group) & srv:
            dead -= set(group)
    if d["kind"] == "map" and d.get("summary_keys_tuple"):
        sk = set(tuples.get(d["summary_keys_tuple"], ()))
        dead -= sk
        out["summary_keys"] = sorted(sk)
        out["notes"] = ("a node->group map whose keys are node ids; a map that holds a summary key is refused as an "
                        "accelerated summary, so a node named " + "/".join(sorted(sk)) + " is refused too")
    ok = d.get("dead_ok", {})
    out["dead_reads"] = sorted(dead - set(ok))
    if dead & set(ok):
        out["dead_reads_explained"] = {k: ok[k] for k in sorted(dead & set(ok))}
    if d["kind"] == "projecting":
        out["dropped"] = sorted(srv - reads)
    if d.get("doc"):
        doc = set(d["doc"])
        out["doc_keys"] = sorted(doc)
        out["doc_not_emitted"] = sorted(doc - srv - set(d.get("client_adds", [])))
        out["undocumented"] = sorted(srv - doc)
    return out


def check_map(root: Path, m: dict) -> dict:
    out = {"module": m["module"], "name": m["name"]}
    if "py" in m:
        path, f = m["py"]
        src, a, b, _, _ = py_func(root, path, f)
        var = m["tokens_in"]
        toks = re.findall(rf'"([^"]+)"\s+(?:not\s+)?in\s+(?:str\()?{var}\b', src)
        toks += re.findall(rf're\.(?:match|search)\(r"([^"]+)",\s*str\({var}\)', src)
        out.update({"ref": f"{path}:{a}-{b}", "tokens": toks})
    if "py_regex" in m:
        path, name = m["py_regex"]
        text = (root / path).read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in tree.body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
                pat = ast.literal_eval(node.value.args[0]) if isinstance(node.value, ast.Call) else None
                out.update({"ref": f"{path}:{node.lineno}-{node.end_lineno}", "pattern": pat})
    if "http_route" in m:
        path, f = m["http_route"]
        src, a, b, _, _ = py_func(root, path, f)
        codes = sorted({int(x) for x in re.findall(r"status_code=(\d+)", src)})
        auth = (root / "iris_vector_graph/api_auth.py").read_text(encoding="utf-8")
        mw = sorted({int(x) for x in re.findall(r"status_code=(\d+)", auth)})
        out.update({"ref": f"{path}:{a}-{b}", "route_codes": [200] + codes, "middleware_codes": mw})
    return out


def alg_i5(root: Path) -> dict:
    """Every `self._store.execute_*` call in the engine's algorithms: its error raised or tested."""
    path = "iris_vector_graph/_engine/algorithms.py"
    src = (root / path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    mapped, unmapped = [], []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        seg = ast.get_source_segment(src, fn) or ""
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr.startswith("execute_") and "_store" in (ast.get_source_segment(src, n.func) or "")]
        for c in calls:
            name = c.func.attr
            raises = "_raise_store_error(" in seg
            tests = re.search(r"result\.error", seg) is not None
            rec = {"engine_method": fn.name, "store_call": name, "line": c.lineno,
                   "propagation": "raise" if raises else ("error-test+owner-fallback" if tests else "none")}
            (mapped if (raises or tests) else unmapped).append(rec)
    return {"module": "10", "name": "ALG-I5 store error -> exception (algorithms.py)", "ref": path,
            "mapped": mapped, "unmapped": unmapped}


ENC_FIELD = re.compile(r'""(\w+)"":"\s*_\s*(\w+)\s*_')


def number_encodings(root: Path) -> List[dict]:
    """Numbers and strings JSON-literal producers write by concatenation, with their guard."""
    out = []
    for path, methods in ((f"{KG}/BM25Index.cls", ("Build", "Info", "Upgrade", "SearchCore", "SearchReport")),):
        for m in methods:
            body, a, b = cls_method(root, path, m)
            for key, var in ENC_FIELD.findall(body):
                guarded = bool(re.search(rf'\$Extract\({var}\)\s*=\s*"\."', body)) or f"jsonNum({var}" in body
                fractional = bool(re.search(rf"Set {var} = [^\n]*/", body))
                out.append({"producer": f"{path}:{a}-{b}", "method": m, "key": key, "var": var,
                            "leading_dot_guard": guarded, "may_be_fractional": fractional})
            for key in re.findall(r'""(\w+)"":"""_(\w+JSON)_"""', body):
                k, var = key
                esc = re.search(rf"Set {var} = ([^\n]+)", body)
                out.append({"producer": f"{path}:{a}-{b}", "method": m, "key": k, "var": var, "string": True,
                            "escaping": esc.group(1).strip() if esc else None,
                            "escapes_control_characters": bool(esc and "jsonEsc" in esc.group(1))})
    return out


def text_patch(root: Path) -> dict:
    src, a, b, _, _ = py_func(root, "iris_vector_graph/_engine/vector.py", "bm25_search")
    m = re.search(r"_re\.sub\(r'([^']+)', r'([^']+)', str\(raw\)\)", src)
    return {"module": "07", "name": "bm25_search _parse: leading-dot patch over the raw JSON text",
            "ref": f"iris_vector_graph/_engine/vector.py:{a}-{b}", "pattern": m.group(1) if m else None,
            "token_aware": False if m else None,
            "notes": "applied to the whole answer, string values (document ids) included; the server already writes "
                     "a leading 0 (BM25Index.cls SearchCore scoreText)"}


def list_separator(root: Path) -> dict:
    body, a, b = cls_method(root, f"{KG}/BM25Index.cls", "List")
    _, ca, cb, _, _ = py_func(root, "iris_vector_graph/_engine/vector.py", "_build_index_registry")
    val = (root / "iris_vector_graph/_validate.py").read_text(encoding="utf-8")
    m = re.search(r"class BM25BuildInput[\s\S]*?(?=\nclass )", val)
    refuses_comma = bool(m and "','" in m.group(0)) or bool(m and '","' in m.group(0))
    return {"module": "07", "name": "BM25Index.List comma-joined names -> _build_index_registry split(',') + strip()",
            "server": f"{KG}/BM25Index.cls:{a}-{b}", "client": f"iris_vector_graph/_engine/vector.py:{ca}-{cb}",
            "separator": ",", "name_validator_refuses_separator": refuses_comma,
            "insert_validates_name": False}


def run(root: Path) -> dict:
    decs = [check_decoder(root, d) for d in SPEC]
    maps = [check_map(root, m) for m in MAPS]
    i5 = alg_i5(root)
    enc = number_encodings(root)
    problems = []
    for d in decs:
        for k in ("dead_reads", "undecoded_forms"):
            if d.get(k):
                problems.append(f"{d['name']}: {k} {d[k]}")
    for u in i5["unmapped"]:
        problems.append(f"ALG-I5 unmapped: {u['engine_method']} -> {u['store_call']} (line {u['line']})")
    risks = []
    for d in decs:
        if d.get("doc_not_emitted"):
            risks.append(f"{d['name']}: documented keys not emitted {d['doc_not_emitted']}")
        if d.get("undocumented"):
            risks.append(f"{d['name']}: emitted keys not documented {d['undocumented']}")
        if d.get("summary_keys"):
            risks.append(f"{d['name']}: {d['notes']}")
    for e in enc:
        if e.get("string") and not e["escapes_control_characters"]:
            risks.append(f"{e['method']}.{e['key']}: string written with {e['escaping']} (no control-character escaping)")
        if not e.get("string") and e["may_be_fractional"] and not e["leading_dot_guard"]:
            risks.append(f"{e['method']}.{e['key']}: fractional number {e['var']} written with no leading-dot guard")
    tp = text_patch(root)
    risks.append(f"{tp['name']}: pattern {tp['pattern']!r} not token-aware")
    ls = list_separator(root)
    if not ls["name_validator_refuses_separator"]:
        risks.append(f"{ls['name']}: the separator is allowed inside an index name")
    return {"pin": PIN, "decoders": decs, "maps": maps, "alg_i5": i5, "encodings": enc, "text_patch": tp,
            "list_separator": ls, "problems": problems, "risks_for_live": risks}


# ------------------------------------------------------------------------------------------------ self-test

def _copy_tree(dst: Path) -> None:
    for rel in ("iris_src/src/Graph/KG", "iris_vector_graph"):
        shutil.copytree(REPO / rel, dst / rel, ignore=shutil.ignore_patterns("__pycache__", "browser_static"))


def self_test() -> int:
    base = run(REPO)
    ok = True

    def has(r, pred):
        return any(pred(p) for p in r["problems"])

    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        _copy_tree(t)
        # 1. the producers stop emitting score (every %Set("score" of Graph.KG.PageRank)
        p = t / KG / "PageRank.cls"
        p.write_text(p.read_text().replace('%Set("score"', '%Set("val"'))
        # 2. an engine method that drops a store error
        a = t / "iris_vector_graph/_engine/algorithms.py"
        a.write_text(a.read_text().replace(
            "    def kg_GRAPH_PATH(self,",
            "    def injected_drops_error(self):\n        result = self._store.execute_injected()\n"
            "        return result.rows\n\n    def kg_GRAPH_PATH(self,", 1))
        # 3. the import decoder reads a key nobody emits
        s = t / "iris_vector_graph/_engine/snapshot.py"
        s.write_text(s.read_text().replace('subs = entry.pop("k")', 'subs = entry.pop("k")\n                _x = entry.get("never_sent")', 1))
        # 4. Encode emits a new value form
        e = t / KG / "Snapshot.cls"
        e.write_text(e.read_text().replace('\tQuit {"v": (pVal_"")}', '\tQuit:0 {"blob": (pVal)}\n\tQuit {"v": (pVal_"")}', 1))
        bad = run(t)
    checks = {
        "unmodified tree: no dead reads, no unmapped, no undecoded forms": not base["problems"],
        "1 producer without score -> dead read 'score'": has(bad, lambda x: "_scored_node_rows" in x and "'score'" in x),
        "2 store error dropped -> ALG-I5 unmapped": has(bad, lambda x: "injected_drops_error" in x),
        "3 import reads an unsent key -> dead read": has(bad, lambda x: "global value line" in x and "never_sent" in x),
        "4 Encode emits an undecoded form -> undecoded_forms": has(bad, lambda x: "undecoded_forms" in x and "blob" in x),
    }
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
        ok &= v
    print("self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    r = run(REPO)
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1) + "\n")
    for d in r["decoders"]:
        keys = d.get("wire_keys", d.get("server_forms", d.get("written")))
        print(f"[{d['module']}] {d['name']}: wire {keys}; reads {d.get('decoder_reads', d.get('client_reads', d.get('read')))}; "
              f"dead {d.get('dead_reads')}")
    for m in r["maps"]:
        print(f"[{m['module']}] map {m['name']}: {m.get('tokens', m.get('pattern', m.get('route_codes')))}"
              + (f" + middleware {m['middleware_codes']}" if m.get('middleware_codes') else ""))
    print(f"[10] ALG-I5: {len(r['alg_i5']['mapped'])} store calls mapped, {len(r['alg_i5']['unmapped'])} unmapped")
    print(f"problems {len(r['problems'])}: {r['problems']}")
    print(f"risks for the live drive {len(r['risks_for_live'])}:")
    for x in r["risks_for_live"]:
        print("  - " + x)
    return 0 if not r["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
