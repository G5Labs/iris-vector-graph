#!/usr/bin/env python3
"""Module 10 IRIS-free probes of the pin's pure functions (no IRIS connection).

    python experiment/playbook-completion/live/breadth-b/10_probe_units.py

F-1012: _arno_gate.build_proof keeps an earlier entry for an algorithm absent from the run but names only the current
        run's library build.
F-1001: arno_readers.route answers "native" for a default-graph call whatever the namespace's named graphs hold (it
        takes no such input), unlike the BFS adapter's _only_default_graph probe.
F-1004: algo_cache.param_hash for PPR depends only on seeds and settings: the key cannot change when a start node is
        created without an edge.
"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from iris_vector_graph import _arno_gate, algo_cache, arno_readers  # noqa: E402

out = {}
prev = {"library": {"version": "1.2.0", "sha256": {"lib": "aaa"}}, "proven_at": "t0",
        "algorithms": {"pagerank": {"min_revision": 2, "fixtures": ["f1", "f2", "f3", "f4", "f5"], "repeats": 5}}}
doc = _arno_gate.build_proof(previous=prev, version="1.3.0", sha256={"lib": "bbb"},
                             results={"wcc": {"passed": True, "revision": 1, "fixtures": ["f1", "f2", "f3", "f4", "f5"], "repeats": 5}},
                             proven_at="t1")
out["F-1012"] = {"doc": doc, "pagerank_kept": "pagerank" in doc["algorithms"],
                 "library_named": doc["library"],
                 "per_entry_build": any(k in doc["algorithms"]["pagerank"] for k in ("version", "sha256", "library")),
                 "reproduced": "pagerank" in doc["algorithms"] and doc["library"]["version"] == "1.3.0"
                               and not any(k in doc["algorithms"]["pagerank"] for k in ("version", "sha256", "library"))}
_shipped = json.loads((REPO / "docs/dev/arno-reader-proof.json").read_text())
proof = arno_readers.Proof.from_dict({"library": _shipped["library"], "proven_at": _shipped["proven_at"],
                                      "algorithms": {"pagerank": {"min_revision": 2, "fixtures": ["a", "b", "c", "d", "e"], "repeats": 5}}})
r_default = arno_readers.route("pagerank", {"pagerank": 2}, proof, "")
r_named = arno_readers.route("pagerank", {"pagerank": 2}, proof, "g1")
import inspect  # noqa: E402
params = list(inspect.signature(arno_readers.route).parameters)
out["F-1001"] = {"route_default_graph": r_default, "route_named_graph": r_named, "route_parameters": params,
                 "named_edges_input": any("named" in p or "edges" in p for p in params),
                 "reproduced": r_default == arno_readers.NATIVE and not any("named" in p or "edges" in p for p in params)}
k1 = algo_cache.param_hash({"seeds": algo_cache.seed_key(["x"]), "damping": 0.85, "max_iterations": 100})
k2 = algo_cache.param_hash({"seeds": algo_cache.seed_key(["x"]), "damping": 0.85, "max_iterations": 100})
out["F-1004-key"] = {"key_before": k1, "key_after_node_create": k2, "same": k1 == k2, "cacheable": sorted(algo_cache.CACHEABLE)}
print(json.dumps(out, indent=1, default=str))
dst = Path(os.environ["RUN_DIR"]) / "breadth-b" / "live" / "10-probe-units.json"
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(out, indent=1, default=str) + "\n")
