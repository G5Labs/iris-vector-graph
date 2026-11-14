#!/usr/bin/env python3
"""Assemble module 10's footprints/10.json, findings/audit/10.json and modules/10.json (no IRIS).

    python3 experiment/playbook-completion/live/breadth-b/10_build_outputs.py

Inputs: models/breadth-b/inventory/10.json (mechanical inventory), $RUN_DIR/breadth-b/inventory/10-reconcile.json,
the live logs $RUN_DIR/breadth-b/live/10-*.json, the model results models/breadth-b/results/m10-*.json, the registry
evidence/runs/b-10-*.json and $RUN_DIR/checks/storage-order.json. Dispositions that depend on a live run are taken
from that run's verdict; a missing log leaves the record at its source/model disposition.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMP = HERE.parents[1]
REPO = COMP.parents[1]
RUN = Path(os.environ["RUN_DIR"])
LIVE = RUN / "breadth-b" / "live"


def load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:  # noqa: BLE001
        return None


INV = load(COMP / "models/breadth-b/inventory/10.json")
REC = load(RUN / "breadth-b/inventory/10-reconcile.json")
L = {k: load(LIVE / f"10-{k}.json") for k in ("live-cache", "live-nkg", "live-nkg-f1005", "live-scope", "live-cap",
                                              "live-fp", "live-refusals", "probe-units")}
RES = {p.stem: load(p) for p in sorted((COMP / "models/breadth-b/results").glob("m10-*.json"))}
RUNS = {p.stem: load(p) for p in sorted((COMP / "evidence/runs").glob("b-10-*.json"))}


def step(log, name):
    if not log:
        return None
    for s in log.get("steps", []):
        if s.get("step") == name:
            return s
    return None


def mc(*ids):
    return [{"kind": "mc", "ref": i} for i in ids if i in RES]


def live(rid):
    return [{"kind": "live", "ref": rid}] if rid in RUNS else []


def insp(*refs):
    return [{"kind": "inspected", "ref": r} for r in refs]


# ------------------------------------------------------------------------------------------------ live verdicts
cache = L["live-cache"] or {}
nkg = L["live-nkg"] or {}
nkg5 = L["live-nkg-f1005"] or {}
scope = L["live-scope"] or {}
cap = L["live-cap"] or {}
fp = L["live-fp"] or {}
ref = L["live-refusals"] or {}
pu = L["probe-units"] or {}
sv = {s["step"]: s for s in scope.get("steps", [])} if scope else {}
scope2 = load(LIVE / "10-live-scope2.json") or {}
sv2 = {s["step"]: s for s in scope2.get("steps", [])} if scope2 else {}


def verdict(log, key):
    return (log or {}).get("verdict", {}).get(key)


# ------------------------------------------------------------------------------------------------ findings
F = []


def rec(**kw):
    kw.setdefault("module", "10")
    kw.setdefault("original_ref", f"experiment/playbook-uplift/findings/10.md#{kw['id']}")
    kw.setdefault("notes", "")
    F.append(kw)


f1005_ok = verdict(nkg5, "F-1005") == "reproduced"
rec(id="F-1001", title="A native reader answers default-graph calls in a namespace where a named graph has edges",
    intended="spec 236 FR-014a: a native reader 'MUST be used only for the graph scope its proof covers' "
             "(specs/236-arno-callout-adoption/spec.md:268-272); ALG-I3 / SYS-I2 (a default-graph answer never mixes in a "
             "named graph's edges); the BFS route and the ^NKG tiers probe for named-graph edges "
             "(iris_vector_graph/stores/iris_sql_store.py:1842-1858, :3322).",
    observed="Source at the pin: arno_readers.route takes no named-graph input and answers native for graph '' "
             "(iris_vector_graph/arno_readers.py:257-280); _execute_pagerank routes with no named_graph_with_edges probe "
             "(iris_sql_store.py:2388-2400). Probe b-10-probe-units ran the pin's route(): 'native' for graph '' with no "
             "parameter that could carry named-graph edges. Model m10-routes-as-built-pagerank-scope finds the mixed answer "
             "only with a library whose reader is graph-blind; with a graph-0-only reader "
             "(m10-routes-as-built-pagerank-scope-default-only-lib) it passes: the outcome hinges on the open premise P-1004. "
             "Live observation is blocked: the arno-callout library is not loaded in this container (NKGAccel.Capabilities "
             "rust_callout false, b-10-live-nkg) and _arno_route answers owner outside the USER namespace "
             "(iris_sql_store.py:883-894), which the validation lane owns.",
    disposition="blocked-access", outcome="blocked-access",
    evidence=[{"kind": "probe", "ref": "b-10-probe-units"}] + mc("m10-routes-as-built-pagerank-scope",
             "m10-routes-as-built-pagerank-scope-default-only-lib", "m10-routes-reviewed", "m10-routes-control-no-probe")
             + insp("iris_vector_graph/arno_readers.py:257-280", "iris_vector_graph/stores/iris_sql_store.py:2388-2400",
                    "iris_vector_graph/stores/iris_sql_store.py:1842-1858", "iris_vector_graph/stores/iris_sql_store.py:883-894")
             + [{"kind": "assumed", "ref": "P-1004 (open: sources disagree on what the reader reads)"}],
    gates=["3.3-model-check", "3.5-handlers", "3.2-coverage"], severity="S1", confidence="medium",
    remedy="Route to a native reader only when named_graph_with_edges() is None (as BFS and the ^NKG tiers do), or add a "
           "named-graph fixture to the reader gate and record graph scope in the proof; then a live test in USER with "
           "arno-callout 1.2.1 loaded and a named graph's edges.",
    notes="Blocked dependency: arno-callout 1.2.1 library build loaded into the USER namespace of an IRIS instance "
          "(the proof record names arno-callout 1.2.1+844e5ff75f45, arm64). The missing probe itself is confirmed at the "
          "source; whether answers mix graphs depends on P-1004.")

f1002_empty = verdict(nkg, "F-1002-empty") == "reproduced"
f1002_cross = verdict(nkg, "F-1002-cross-graph") == "reproduced"
s_rw = step(nkg, "F-1002-random-walk-json-cross-graph") or {}
rec(id="F-1002", title="random_walk needs the Arno library for an ObjectScript walk, and walks every graph's edges",
    intended="ALG-I1 / CONTEXT.md:261-264 (IVG answers the same without the library, only slower); ALG-I3 and SYS-I2; "
             "decisions.md HD-1001 working answer (assumption): a declared graph scope and an observable unavailable "
             "result, never an empty graph inferred from missing acceleration.",
    observed=("Live (b-10-live-nkg): engine.random_walk('b10_a') answered [] while b10_a has out-edges and the Arno "
              "library is absent (engine._detect_arno() False). With named graph b10g1 holding b10_a -> b10_n beside the "
              "default graph's b10_a -> b10_b and ^NKG synced, the walk the engine would call, Graph.KG.NKGAccel."
              f"RandomWalkJson (pure ObjectScript), stepped first to {s_rw.get('first_steps')}: the named graph's node "
              "b10_n from a default-graph walk. The ^NKG procedure ivg.betweenness refused the same namespace (ALG-B7 "
              "holds live). Models: m10-routes-as-built-walk-empty and m10-nkg-as-built-scope reproduce both parts; "
              "reviewed designs pass.") if (f1002_empty and f1002_cross) else "Live run pending or not reproduced.",
    disposition="reproduced-live" if (f1002_empty and f1002_cross) else "confirmed-source",
    outcome="product-defect",
    evidence=live("b-10-live-nkg") + mc("m10-routes-as-built-walk-empty", "m10-nkg-as-built-scope", "m10-nkg-reviewed",
                                        "m10-nkg-control-walk-merged")
             + insp("iris_vector_graph/_engine/algorithms.py:658-678", "iris_src/src/Graph/KG/NKGAccelTraversal.cls:187-222",
                    "iris_src/src/Graph/KG/NKGAccel.cls:176-178")
             + [{"kind": "open", "ref": "HD-1001"}],
    gates=["3.3-model-check", "3.5-handlers", "3.8-findings-disposed"], severity="S1", confidence="high",
    remedy="Decide HD-1001; at minimum walk the default graph's ^KG in ObjectScript whatever the library state (or refuse "
           "with an explicit unavailable error), call EnsureNKG and refuse when a named graph has edges if ^NKG is "
           "kept; a live test with two graphs sharing a node id.",
    notes="Which graph a walk should cover is intent-undecided (HD-1001); the empty answer and the cross-graph step "
          "each violate a documented contract (ALG-I1 / CONTEXT.md:261-264; SYS-I2), hence product-defect. "
          "RandomWalkJson is a deployed public class method (callable directly over the Native API).")

cap_ok = bool(cap.get("reproduced"))
rec(id="F-1003", title="Global PageRank lists at most 10,000 nodes from its owner and every node from the native reader",
    intended="The method's docstring: every node takes part and the scores sum to 1 over node_count() nodes "
             "(iris_vector_graph/_engine/algorithms.py:741-760); decisions.md HD-1004 (assumption): the same result "
             "contract on every route, uncapped pending a documented limit, any truncation exposed.",
    observed=(f"Live (b-10-live-cap): with {cap.get('node_count')} default-graph nodes (hub b10_h -> 10,050 nodes, pin's "
              f"bulk API) kg_PAGERANK() on the owner route answered {cap.get('kg_PAGERANK_rows')} rows summing to "
              f"{cap.get('score_sum')}; {cap.get('unlisted_nodes')} nodes were silently not listed; "
              f"PageRank.PageRankGlobalJson itself answered {cap.get('PageRankGlobalJson_rows')} rows. The native route "
              "(every node, iris_sql_store.py:2396-2399) is blocked (arno-callout absent). Model "
              "m10-routes-as-built-pagerank-cap reproduces the route disagreement.") if cap else
             "Live run pending; source: PageRank.cls:506-520 stops at count >= 10000; _ranked_rows(..., 0) keeps every row.",
    disposition="reproduced-live" if cap_ok else "confirmed-source", outcome="product-defect",
    evidence=live("b-10-live-cap") + mc("m10-routes-as-built-pagerank-cap", "m10-routes-reviewed", "m10-routes-control-owner-cap")
             + insp("iris_src/src/Graph/KG/PageRank.cls:506-520", "iris_vector_graph/stores/iris_sql_store.py:2388-2400",
                    "iris_vector_graph/stores/iris_sql_store.py:124-129") + [{"kind": "open", "ref": "HD-1004"}],
    gates=["3.6-capacity", "3.5-handlers", "3.3-model-check"], severity="S2", confidence="high" if cap_ok else "medium",
    remedy="Decide HD-1004; make both routes cut (or not cut) the same way and say so in the answer (a truncation flag or "
           "a documented top_k).",
    notes="The native half is blocked-access (arno-callout library). The owner-side truncation contradicts the method's "
          "own docstring regardless of HD-1004.")

s_c = step(cache, "F-1004-create") or {}
s_d = step(cache, "F-1004-delete") or {}
tf = step(cache, "token-facts") or {}
rec(id="F-1004", title="A cached personalized PageRank answer misses a start node written or removed without an edge",
    intended="ALG-B2.19 (a cached answer changes when a start node is added to the graph or removed from it); ALG-B16.11 "
             "(after any write a cached answer equals a fresh computation); ALG-I4.",
    observed=(f"Live (b-10-live-cache): kg_PERSONALIZED_PAGERANK(['b10_x']) answered {s_c.get('before_x_exists')} before "
              "b10_x existed and the answer was cached (^IVG.AlgoCache(0,'ppr',...)); create_node('b10_x') with no edge "
              f"wrote only nodes/rdf_props and moved no token; the same call then answered {s_c.get('cached_answer_after_create')} "
              f"from the cache while a fresh run (after AlgoCache.InvalidateAll) answered {s_c.get('fresh_answer')}. "
              "Refuted part: deleting the edgeless start node moved ^KG('__version') "
              f"({tf.get('labelled_create')} -> {tf.get('labelled_delete')} for a labelled node; edgeless "
              f"{tf.get('after_edge_setup')} -> {tf.get('edgeless_delete')}) because delete_node runs Graph.KG.Eraser."
              "EraseNodeIds, whose InvalidateDerived bumps the token and kills ^IVG.AlgoCache (Eraser.cls:1038-1053); the "
              f"next call answered {s_d.get('cached_answer_after_delete')}, equal to a fresh run. Models: "
              "m10-cache-as-built-ppr (violation, linearizable property), m10-cache-reviewed-ppr (monotonic node token: "
              "pass), m10-cache-control-no-bump-on-create (caught).") if s_c else "Live run pending.",
    disposition="reproduced-live" if s_c.get("stale_served") else "confirmed-source", outcome="product-defect",
    evidence=live("b-10-live-cache") + [{"kind": "probe", "ref": "b-10-probe-units"}]
             + mc("m10-cache-as-built-ppr", "m10-cache-reviewed-ppr", "m10-cache-control-no-bump-on-create",
                  "m10-cache-as-built-pagerank")
             + insp("iris_vector_graph/stores/iris_sql_store.py:2231-2275", "iris_vector_graph/stores/iris_sql_store.py:921-983",
                    "iris_src/src/Graph/KG/AlgoCache.cls:17-50", "iris_src/src/Graph/KG/Eraser.cls:1038-1053"),
    gates=["3.6-keys", "3.3a-writesets", "3.3-model-check"], severity="S2", confidence="high",
    remedy="Put the node-set token in the PPR key (as global PageRank does since R313) or raise a node token on every node "
           "write and read it inside AlgoCache.Lookup; a live test that creates an edgeless start node after a cached call.",
    notes="Only the 'written' half reproduces at the pin; the 'removed' half is refuted live (a node delete always raises "
          "the token and clears the cache). The global PageRank key (R313, COUNT(*):MAX(%ID)) is sound within the model's "
          "bounds only because deletes raise the token: m10-cache-control-silent-delete-pagerank shows the ABA it would "
          "otherwise admit (COUNT:MAX returns to an earlier value when the newest node is deleted).")

b5 = step(nkg5, "F-1005-before-sync") or {}
a5 = step(nkg5, "F-1005-after-sync") or {}
rec(id="F-1005", title="The interned snapshot can lack edges with nothing saying it is out of date",
    intended="ALG-B12.7 (a snapshot reader sees the same edges as the adjacency index or learns the snapshot is out of "
             "date); SYS-I8 and CONTEXT.md:109-114 (a rebuilt store matches its sources or says it is stale).",
    observed=("Not reproduced live in the default configuration (b-10-live-nkg-f1005): with ^NKG built from b10_a -> b10_b, "
              "create_edge_temporal(b10_b, B10T, b10_c) wrote " + str(b5.get("temporal_write_stores")) + " (journal): the "
              "temporal edge asserted a structural rdf_edges row whose adjacency index wrote ^KG and interned b10_c into "
              "^NKG (interned: " + str(b5.get("nkg_interns_b10_c")) + ", edgeCount " +
              str((b5.get("nkg_meta_after_sync") or {}).get("edgeCount")) + " -> " +
              str((b5.get("nkg_meta_after_temporal") or {}).get("edgeCount")) + "); betweenness " + str(b5.get("betweenness")) +
              " and closeness answered the same before and after engine.sync() (differs: " + str(a5.get("differs")) + "). "
              "The source shows why: TemporalIndex.InsertEdge calls Adjacency.PutShadow (no interning, no stale mark) only "
              "when Graph.KG.Adjacency.Indexed() is false; with the index declared it calls AssertTemporalRow "
              "(TemporalIndex.cls:104-112). The finding therefore stands only for a namespace without the adjacency "
              "functional index (source + model m10-nkg-as-built-fresh, which models that branch). ^NKG('$meta','builtFrom') "
              "still lags the token with no reader comparing them (builtFrom_lags_token " + str(b5.get("builtFrom_lags_token")) +
              "), harmless here because the snapshot was current.") if b5 else
             "Live run pending; source: Adjacency.cls:111-140 (PutShadow), TraversalBuild.cls:399-424.",
    disposition="confirmed-source", outcome="product-defect", narrowed=True,
    evidence=live("b-10-live-nkg-f1005") + mc("m10-nkg-as-built-fresh", "m10-nkg-reviewed", "m10-nkg-control-ensure-ignores-stale")
             + insp("iris_src/src/Graph/KG/TemporalIndex.cls:104-112", "iris_src/src/Graph/KG/Adjacency.cls:111-140",
                    "iris_src/src/Graph/KG/TraversalBuild.cls:399-424", "iris_vector_graph/_engine/temporal.py:280-286"),
    gates=["3.3a-writesets", "3.3-model-check"], severity="S3", confidence="medium",
    remedy="Mark ^NKG stale in PutShadow when ^NKG is built (EnsureNKG then rebuilds), or compare builtFrom with the token "
           "in EnsureNKG; correct the ADJACENCY CONTRACT docstring (temporal.py:280-286), which still says temporal edges are "
           "never interned although the indexed path interns them.",
    notes="Narrowed: the original claim (temporal edges never reach ^NKG) is refuted live for the indexed configuration, the "
          "default after initialize_schema at the pin; it holds by source only where the adjacency index is not declared. "
          "The first live attempt (b-10-live-nkg) was void (^NKG unbuilt). The docstring at temporal.py:280-286 contradicts "
          "the observed indexed behaviour (a documentation defect of module 05).")

s6 = sv2.get("F-1006") or {}
rec(id="F-1006", title="Subgraph vectors are read by node id in every graph",
    intended="ALG-I3 (a default-graph call never mixes in a named graph's content); the table is keyed (graph_id, "
             "node_id) (iris_vector_graph/schema.py:429-437).",
    observed=(f"Live (b-10-live-scope2; the first run's fixture violated the (graph_id, node_id) foreign key): kg_NodeEmbeddings held rows {s6.get('rows')} for b10_s (in both graphs); "
              f"kg_SUBGRAPH(['b10_s'], include_embeddings=True) returned {s6.get('embedding_returned')} (default-graph "
              f"vector {s6.get('default_vector')}, named-graph vector {s6.get('named_vector')}).") if s6 else "Live run pending.",
    disposition="reproduced-live" if s6.get("reproduced") else ("not-reproduced" if s6 else "confirmed-source"),
    outcome="product-defect" if (s6.get("reproduced") or not s6) else "product-defect",
    evidence=live("b-10-live-scope2") + insp("iris_vector_graph/_engine/algorithms.py:850-880", "iris_vector_graph/schema.py:429-437",
                                            "iris_src/src/Graph/KG/Subgraph.cls:6-11"),
    gates=["3.5-handlers", "3.4-declared-reads"], severity="S2", confidence="medium",
    remedy="Add graph_id = '' to the read, correct the comment that the walk is namespace-wide, and test with two graphs.",
    notes="Needs a named graph's row in kg_NodeEmbeddings (named graphs normally use route tables, KNOWN_ISSUES 702-714); "
          "the row was written with SQL for the check. When both rows match, which vector wins depends on row order "
          "(the dict keeps the last row): an order-dependent answer.")

s7 = sv2.get("F-1007") or {}
rec(id="F-1007", title="Degree centrality counts parallel edges on out-edges but not on in-edges",
    intended="CONTEXT.md:103-108 (parallel edges each count towards degree); ALG-B5.4.",
    observed=(f"Live (b-10-live-scope2; the first run's engine.create_edge kept one edge per triple): named graph b10gm in multigraph mode "
              f"(engine.set_multigraph, restored after), three parallel b10_p -> b10_q edges by Cypher CREATE and one b10_r -> b10_q ({s7.get('edge_rows')} edge rows, "
              f"{s7.get('parallel_triples')} parallel triple): "
              f"degree_centrality out {s7.get('degree', {}).get('out')} (sum {s7.get('out_sum')}), in "
              f"{s7.get('degree', {}).get('in')} (sum {s7.get('in_sum')}). Model m10-degree-as-built violates the handshake "
              "invariant; m10-degree-reviewed passes; control caught.") if s7 else "Live run pending.",
    disposition="reproduced-live" if s7.get("reproduced") else ("not-reproduced" if s7 else "reproduced-model"),
    outcome="product-defect",
    evidence=live("b-10-live-scope2") + mc("m10-degree-as-built", "m10-degree-reviewed", "m10-degree-control-distinct-out")
             + insp("iris_src/src/Graph/KG/Centrality.cls:88-139", "iris_src/src/Graph/KG/Adjacency.cls:203-206"),
    gates=["3.5-handlers", "3.3-model-check"], severity="S2", confidence="high" if s7.get("reproduced") else "medium",
    remedy="Count in-degree from the out mirror's multiplicity; a multigraph test.", notes="")

s8 = sv.get("F-1008") or {}
rec(id="F-1008", title="Variable-length expansion's every-graph mode walks across graphs",
    intended="CONTEXT.md:38-43 (an edge meets only nodes of its own graph); ALG-I2.",
    observed=(f"Live (b-10-live-scope): default graph b10_s -> b10_k, named graph b10g1 b10_k -> b10_m (shared id b10_k). "
              f"Graph.KG.VarLength.Ends('b10_s', '', 'out', 2, 2, pAll=1) answered {s8.get('ends_every_graph_mode')}; with "
              f"pAll=0 (default graph) {s8.get('ends_default_graph')}. The translator side (Cypher with gall = 1) is module "
              "08's F-0818, reproduced live there (b-08-live-f0818). Model m10-walk-as-built-one-graph reproduces it; "
              "m10-walk-reviewed passes.") if s8 else "Live run pending.",
    disposition="reproduced-live" if s8.get("reproduced") else ("not-reproduced" if s8 else "reproduced-model"),
    outcome="product-defect",
    evidence=live("b-10-live-scope") + [{"kind": "live", "ref": "b-08-live-f0818"}]
             + mc("m10-walk-as-built-one-graph", "m10-walk-reviewed", "m10-walk-control-reset-at-shared")
             + insp("iris_src/src/Graph/KG/VarLength.cls:44-51", "iris_src/src/Graph/KG/VarLength.cls:126-148",
                    "iris_vector_graph/cypher/translator.py:15404-15431"),
    gates=["3.5-handlers", "3.3-model-check"], severity="S1", confidence="high" if s8.get("reproduced") else "medium",
    remedy="Walk each graph separately in the every-graph mode (fix the graph at the first hop); a live test with a "
           "parameter source in two graphs.", notes="")

s9 = sv.get("F-1009") or {}
rec(id="F-1009", title="khop answers a start node that exists only in a named graph",
    intended="The khop docstring: a missing seed answers two empty lists (_engine/algorithms.py:577-594); ALG-I3.",
    observed=(f"Live (b-10-live-scope): khop('b10_z') for b10_z held only by named graph b10g1 answered "
              f"{s9.get('khop_named_only')}; khop of an id in no graph answered {s9.get('khop_missing')}. Model "
              "m10-walk-as-built-khop reproduces it.") if s9 else "Live run pending.",
    disposition="reproduced-live" if s9.get("reproduced") else ("not-reproduced" if s9 else "confirmed-source"),
    outcome="product-defect",
    evidence=live("b-10-live-scope") + mc("m10-walk-as-built-khop", "m10-walk-reviewed")
             + insp("iris_vector_graph/_engine/algorithms.py:600-626"),
    gates=["3.5-handlers"], severity="S3", confidence="high" if s9.get("reproduced") else "medium",
    remedy="Add graph_id = '' to _khop_seed_exists.", notes="Leaks only the existence of the id, no edges.")

rec(id="F-1010", title="Leiden's server route ignores max_levels and tol",
    intended="leiden_communities documents max_levels and tol as arguments (_engine/algorithms.py:1527-1545).",
    observed="Confirmed at the source: _leiden_serverside calls Graph.KG.Communities.LeidenJsonAuto(10, gamma, 0.0001, "
             "top_k, 256, seed) whatever the caller passed (iris_vector_graph/stores/iris_sql_store.py:3765-3790); "
             "LeidenJsonPy takes neither (iris_src/src/Graph/KG/Communities.cls:615) and LeidenJson documents tol as unused "
             "(Communities.cls:433-443). Not driven live: which server path runs (leidenalg in IRIS Python or the greedy "
             "ObjectScript fallback) depends on the instance's Python packages, so an equal answer for two max_levels "
             "values would not by itself show the argument was dropped.",
    disposition="confirmed-source", outcome="product-defect",
    evidence=insp("iris_vector_graph/stores/iris_sql_store.py:3765-3790", "iris_src/src/Graph/KG/Communities.cls:615",
                  "iris_src/src/Graph/KG/Communities.cls:433-443", "iris_vector_graph/_engine/algorithms.py:1527-1545"),
    gates=["3.5-handlers"], severity="S3", confidence="high",
    remedy="Pass the caller's values, or document that this route ignores them.", notes="")

rec(id="F-1011", title="Documents describe snapshot behaviour the code no longer has",
    intended="docs/ADMIN_GUIDE.md and the method docstrings describe what the code does.",
    observed="Confirmed at the source: ADMIN_GUIDE.md:1271-1272 says algorithms answer [] for every node when ^NKG is not "
             "built, but the methods fall back to a Python walk with a warning (iris_sql_store.py:3322-3336; seen live in "
             "b-10-live-nkg: betweenness on an unbuilt ^NKG answered from the Python walk) or raise; the triangle_count / "
             "strongly_connected_components / k_core docstrings say they read ^NKG while only the default graph has edges "
             "(_engine/algorithms.py:1676-1684) but the store methods use the Arno upload of ^KG graph 0 or LazyKG "
             "(iris_sql_store.py:3977-4006).",
    disposition="confirmed-source", outcome="product-defect",
    evidence=insp("docs/ADMIN_GUIDE.md:1271-1272", "iris_vector_graph/stores/iris_sql_store.py:3322-3336",
                  "iris_vector_graph/_engine/algorithms.py:1676-1684", "iris_vector_graph/stores/iris_sql_store.py:3977-4006")
             + live("b-10-live-nkg"),
    gates=["3.8-findings-disposed"], severity="S3", confidence="high",
    remedy="Update the troubleshooting entry and the three docstrings.", notes="")

p12 = pu.get("F-1012", {}) if pu else {}
rec(id="F-1012", title="The proof record names one library build for entries proven on different builds",
    intended="CONTEXT.md:276-280: the proof record holds the build each reader was proven on.",
    observed=(f"Probe (b-10-probe-units) of the pin's _arno_gate.build_proof: with a previous record proving pagerank on "
              f"build 1.2.0 and a run that proved only wcc on build 1.3.0, the new record keeps pagerank "
              f"({p12.get('pagerank_kept')}) and names only {p12.get('library_named')} as its library, with no per-entry "
              f"build ({p12.get('per_entry_build')}). The upstream unit test that asserts the keeping "
              "(tests/unit/test_236_reader_gate.py) passed here (b-10-run-unit).") if p12 else "Probe pending.",
    disposition="reproduced-test" if p12.get("reproduced") else "confirmed-source", outcome="product-defect",
    evidence=[{"kind": "probe", "ref": "b-10-probe-units"}, {"kind": "run", "ref": "b-10-run-unit"}]
             + insp("iris_vector_graph/_arno_gate.py:138-177"),
    gates=["3.8-findings-disposed"], severity="S3", confidence="high", remedy="Keep the library identity per entry.",
    notes="The probe calls the product's pure function; no IRIS involved.")

s13 = sv.get("F-1013") or {}
a13 = json.dumps(s13.get("answer"))[:300] if s13 else ""
rec(id="F-1013", title="Graph.KG.PageRankEmbedded is deployed and reads every graph",
    intended="ALG-I2/ALG-I3 and the IVG schema boundary (spec 262: the IVG tables live in the IVG schema, Graph_KG here).",
    observed=(f"Live (b-10-live-scope): the deployed class method Graph.KG.PageRankEmbedded.ComputePageRank('b10_%', ...) "
              f"answered {a13}: its unqualified table names resolve to SQLUser, outside the namespace's IVG schema, so the "
              "deployed class cannot run against the IVG tables at all here; where a SQLUser.nodes/rdf_edges exists it reads "
              "that table instead. The every-graph part is confirmed at the source only: ComputePageRankCore selects nodes and "
              "rdf_edges by node_id LIKE ? with no graph_id predicate (PageRankEmbedded.cls:5-30).") if s13 else "Live run pending.",
    disposition="reproduced-live" if s13 else "confirmed-source", outcome="product-defect",
    evidence=live("b-10-live-scope") + insp("iris_src/src/Graph/KG/PageRankEmbedded.cls:5-30", "docs/ADMIN_GUIDE.md:346",
                                            "scripts/deploy_objectscript.py:129"),
    gates=["3.1-coverage", "3.5-handlers"], severity="S3", confidence="high" if s13 else "medium",
    remedy="Remove the class or scope it to one graph and the IVG schema (qualified table names).",
    notes="No engine method calls it (inventory: direct-surface-only); reproduced branch: 'a table outside the IVG schema'.")

# New findings (F-C10kk).
NEW = []
fpd = load(LIVE / "10-live-fp-detail.json") or {}
fp_tri = next((e for e in (fp or {}).get("entries", []) if e["id"] == "eng:IRISGraphEngine.triangle_count"), None)
if fp_tri:
    NEW.append(dict(
        id="F-C1001", module="10",
        title="triangle_count, a read, creates twelve SQL functions (DDL, class compile, commit) and rewrites the deploy record, with no Arno library",
        intended="ALG-I6: a read algorithm changes no content; it may write only its own work areas and caches "
                 "(experiment/playbook-uplift/ontology/10-algorithms.md ALG-I6). The routine record ^IVG.Deploy(\"routines\") is "
                 "setup's record of what it created (iris_vector_graph/routine_record.py:1-21).",
        observed=("Live, journal oracle (b-10-live-fp): the first engine.triangle_count() in AUDITB (Arno library absent) wrote "
                  + str(fp_tri["observed_stores"]) + " with no error, then answered from the LazyKG walk. The dictionary shows "
                  + str(len(fpd.get("arno_function_classes", []))) + " classes Graph.KG.funcivgarnozf* created at that moment "
                  "(b-10-live-fp-detail: TimeCreated $H 67888,3446-3447), i.e. the read path ran CREATE OR REPLACE FUNCTION for the "
                  "$ZF wrappers and committed. A later triangle_count on a new connection rewrote ^IVG.Deploy(\"routines\") again "
                  "(" + str(fpd.get("triangle_again_n")) + " journal record) although nothing was created. Source: "
                  "execute_triangle_count tries the Arno path unless IVG_DISABLE_ARNO is set (iris_sql_store.py:3977-3988); "
                  "build_kg_adjacency_chunked probes arno_available (arno_bridge.py:658-694), which runs _ensure_zf_call_function -> "
                  "_create_routines: DDL + class compile + conn.commit(), refused inside a caller transaction "
                  "(arno_bridge.py:106-136, :360-378), and RoutineRecord.save() writes the record on every probe "
                  "(routine_record.py:93-95).") ,
        disposition="reproduced-live", outcome="product-defect",
        evidence=[{"kind": "live", "ref": "b-10-live-fp"}, {"kind": "live", "ref": "b-10-live-fp-detail"}]
                 + insp("iris_vector_graph/stores/iris_sql_store.py:3977-3988", "iris_vector_graph/stores/arno_bridge.py:658-694",
                        "iris_vector_graph/stores/arno_bridge.py:106-136", "iris_vector_graph/stores/arno_bridge.py:360-378",
                        "iris_vector_graph/routine_record.py:93-95"),
        gates=["3.4-ownership", "3.5-handlers", "3.7-lock-log"], severity="S3", confidence="high",
        remedy="Create the $ZF wrappers in setup (initialize_schema) only, and have the read path probe availability without DDL "
               "(or check IsAvailable first); save the routine record only when something was created.",
        notes="Consequences: a read compiles classes in the reader's process (the compile-failure hazard F-0904 describes for "
              "module 09), commits, invalidates cached queries that call the wrappers, needs DDL privileges (a read-only login "
              "falls back silently), and inside a caller transaction is refused and falls back. The audit's own triangle_count "
              "call thereby compiled these twelve product SQL functions into AUDITB (product behavior, not an audit compile)."))
fp_entries = (fp or {}).get("entries", [])


# ------------------------------------------------------------------------------------------------ write findings
def summarize(recs):
    by_d, by_o = {}, {}
    for r in recs:
        by_d[r["disposition"]] = by_d.get(r["disposition"], 0) + 1
        by_o[r["outcome"]] = by_o.get(r["outcome"], 0) + 1
    return by_d, by_o


bd, bo = summarize(F)
nd, no = summarize(NEW)
audit = {"module": "10", "lane": "breadth-b", "pin": "3eaa79cf",
         "summary": {"original_findings": len(F), "by_disposition": bd, "by_outcome": bo, "new_findings": len(NEW),
                     "new_by_outcome": no},
         "findings": F, "new_findings": NEW}
(COMP / "findings/audit/10.json").write_text(json.dumps(audit, indent=1) + "\n")
print("findings", audit["summary"])


# ------------------------------------------------------------------------------------------------ footprints
def clean(gs):
    return sorted({g for g in gs if not g.startswith("^||") and not g.startswith("^IRIS.Temp")})


CACHED = {"kg_PAGERANK", "kg_PERSONALIZED_PAGERANK", "ppr", "kg_PPR", "kg_WCC", "kg_CDLP", "kg_PPR_GUIDED_SUBGRAPH"}
NKG_READERS = {"betweenness_centrality", "closeness_centrality", "eigenvector_centrality", "leiden_communities",
               "betweenness_centrality_neighborhood"}
MAN = {
    "eng:IRISGraphEngine.kg_PAGERANK": dict(
        reads={"tables": ["Graph_KG.nodes (COUNT(*), MAX(%ID) node token; edgeless nodes on a miss)"],
               "globals": ["^KG(\"__version\")", "^IVG.AlgoCache(0,\"pagerank\",hash)", "^KG(\"out\",0,...)"]},
        writes={"tables": [], "globals": ["^IVG.AlgoCache(0,\"pagerank\",hash) on a miss (AlgoCache.Put, AlgoCache.cls:45-50)"]},
        transaction="none: the cache entry is one Set; the token is read before compute (iris_sql_store.py:921-983)",
        locks=[], nolock=["^KG read lock-free (ALG-P6)"],
        source="iris_vector_graph/_engine/algorithms.py:741-804; iris_vector_graph/stores/iris_sql_store.py:2362-2418; iris_src/src/Graph/KG/PageRank.cls:400-521"),
    "eng:IRISGraphEngine.kg_PERSONALIZED_PAGERANK": dict(
        reads={"tables": ["Graph_KG.nodes (NodeSeeds; every node for zero scores)"], "globals": ["^KG(\"__version\")", "^IVG.AlgoCache(g,\"ppr\",hash)", "^KG(\"out\",g,...)"]},
        writes={"tables": [], "globals": ["^IVG.AlgoCache(g,\"ppr\",hash) on a miss"]},
        transaction="none (one Set)", locks=[], nolock=["lock-free reads (ALG-P6)"],
        source="iris_vector_graph/_engine/algorithms.py:216-390; iris_vector_graph/stores/iris_sql_store.py:2231-2360; iris_src/src/Graph/KG/PageRank.cls:87-116",
        notes="Cache key lacks a node token (F-1004)."),
    "eng:IRISGraphEngine.sync": dict(
        reads={"tables": ["Graph_KG.rdf_edges", "Graph_KG.nodes"], "globals": ["^KG"]},
        writes={"tables": [], "globals": ["^KG (BuildKG)", "^NKG (BuildNKG, in place)", "^IVG.BuiltFrom", "^KG(\"__version\")"]},
        transaction="none: rebuilt in place, readers see a mix of old and new rows (ALG-B12.2)",
        locks=[{"lock": "^IVG.NKGBuild", "mode": "+ exclusive", "timeout": "NKGBUILDWAIT", "source": "iris_src/src/Graph/KG/TraversalBuild.cls:288-298"}],
        source="iris_vector_graph/_engine/schema.py:2859-2922; iris_src/src/Graph/KG/TraversalBuild.cls:288-398",
        notes="Owned by module 04 (builder); in module 10's cells (interned snapshot | sync)."),
    "cls:Graph.KG.AlgoCache.Put": dict(writes={"tables": [], "globals": ["^IVG.AlgoCache(graphKey, algorithm, paramHash)"]},
                                       transaction="none (one Set)", source="iris_src/src/Graph/KG/AlgoCache.cls:45-50"),
    "cls:Graph.KG.AlgoCache.InvalidateAll": dict(writes={"tables": [], "globals": ["Kill ^IVG.AlgoCache"]}, transaction="none",
                                                 source="iris_src/src/Graph/KG/AlgoCache.cls:62-66"),
    "cls:Graph.KG.AlgoCache.InvalidateGraph": dict(writes={"tables": [], "globals": ["Kill ^IVG.AlgoCache(graphKey)"]}, transaction="none",
                                                   source="iris_src/src/Graph/KG/AlgoCache.cls:54-59"),
}
# Declared persistent write sets by source reading (the static closure does not follow the engine -> store calls).
WORK_BC = ["global:^bcParSrc", "global:^bcParScore", "global:^bcBitAdj"]  # NKGAccelCentrality.cls:325, :440, :470, :582
DECL = {
    "eng:IRISGraphEngine.sync": (["global:^KG", "global:^NKG", "global:^IVG.BuiltFrom", "sql:Graph_KG.rdf_edges", "sql:Graph_KG.rdf_labels"],
                                 "Traversal.BuildKG runs %BuildIndices of the functional adjacency indexes idxedgesadj / idxlabelsadj with "
                                 "worker jobs (TraversalBuild.cls:131-135: the tables' index storage ^t52S.*.2 in the journal, no data row), "
                                 "then BuildNKG / Build2HopStats (_engine/schema.py:2859-2922; TraversalBuild.cls:288-398, :949-1007)"),
    "eng:IRISGraphEngine.kg_PAGERANK": (["global:^IVG.AlgoCache"], "AlgoCache.Put on a miss (iris_sql_store.py:921-983)"),
    "eng:IRISGraphEngine.kg_PAGERANK#hit": ([], "a hit writes nothing (AlgoCache.Lookup reads only)"),
    "eng:IRISGraphEngine.kg_PERSONALIZED_PAGERANK": (["global:^IVG.AlgoCache", "global:^KG"], "AlgoCache.Put on a miss; the walk's "
                                                     "Adj.Degree fills the degree cache ^KG(\"degc\",g,node,key) (Adj.cls:64-79; journal: "
                                                     "^KG(\"degc\",0,\"b10_d\",$c(1)), b-10-live-fp-detail)"),
    "eng:IRISGraphEngine.kg_WCC": (["global:^IVG.AlgoCache"], "AlgoCache.Put on a miss (execute_wcc -> _cached_algorithm)"),
    "eng:IRISGraphEngine.kg_CDLP": (["global:^IVG.AlgoCache"], "AlgoCache.Put on a miss (execute_cdlp -> _cached_algorithm)"),
    "eng:IRISGraphEngine.degree_centrality": ([], "Centrality.DegreeCentralityJson reads ^KG only (Centrality.cls:88-139)"),
    "eng:IRISGraphEngine.betweenness_centrality": (WORK_BC + ["global:^NKG", "global:^IVG.BuiltFrom"],
                                                   "EnsureNKG may rebuild ^NKG (TraversalBuild.cls:399-424); parallel work areas killed after use"),
    "eng:IRISGraphEngine.closeness_centrality": (["global:^NKG", "global:^IVG.BuiltFrom"], "EnsureNKG may rebuild; NKGAccelCentrality.ClosenessGlobal reads ^NKG"),
    "eng:IRISGraphEngine.eigenvector_centrality": (["global:^NKG", "global:^IVG.BuiltFrom"], "EnsureNKG may rebuild"),
    "eng:IRISGraphEngine.khop": ([], "Traversal.BFSFastJson stages in process-private ^|| (not journaled)"),
    "eng:IRISGraphEngine.random_walk": ([], "returns [] without the library"),
    "eng:IRISGraphEngine.kg_SUBGRAPH": ([], "Subgraph.SubgraphJson reads ^KG"),
    "eng:IRISGraphEngine.kg_GRAPH_WALK": (["global:^ArnoKG"], "BFSFastJsonSorted stages rows in ^ArnoKG(\"bfs_r\") (TraversalBFS.cls:458; _engine/algorithms.py:93-95)"),
    "eng:IRISGraphEngine.triangle_count": ([], "a read: LazyKG walk of ^KG graph 0 without the library (ALG-I6: only work areas and caches); "
                                           "the observed ^IVG.Deploy / ^oddDEP / ^oddTSQL writes are F-C1001"),
    "eng:IRISGraphEngine.strongly_connected_components": ([], "LazyKG walk"),
    "eng:IRISGraphEngine.k_core": ([], "LazyKG walk"),
    "eng:IRISGraphEngine.leiden_communities": (["global:^NKG", "global:^IVG.BuiltFrom"], "LeidenJsonAuto reads ^NKG after EnsureNKG"),
}
fp_entries2 = []
for e in fp_entries:
    d = DECL.get(e["id"])
    if d is not None:
        dec = sorted(set(d[0]))
        e = {**e, "declared_stores_static": e["declared_stores"], "declared_stores": dec, "declared_by": d[1],
             "undeclared": sorted(set(e["observed_stores"]) - set(dec)),
             "declared_not_observed": sorted(set(dec) - set(e["observed_stores"])),
             "match": set(e["observed_stores"]) <= set(dec)}
    fp_entries2.append(e)
fp_entries = fp_entries2
fp_by = {}
for e in fp_entries:
    fp_by.setdefault(e["id"].split("#")[0], []).append(e)
nkg_fp = step(nkg, "fp-betweenness-stale-rebuild")
fps = []
for ep in (INV or {}).get("entry_points", []):
    h = ep.get("hint", {})
    w_g = clean(set(h.get("globals_written", [])) | set(h.get("globals_killed", [])))
    r_g = clean(h.get("globals_read", []) + h.get("globals_named", []))
    w_t = sorted(set(h.get("tables_written", [])))
    r_t = sorted(set(h.get("tables_read", [])))
    flags = h.get("flags", [])
    if ep["kind"] in ("external-writer", "external-maintainer"):
        role = "writer (other module)"
    elif w_g or w_t:
        role = "both" if (r_g or r_t) else "writer"
    elif r_g or r_t or h.get("classmethod_calls") or ep["kind"] in ("cls", "engine", "cypher-proc"):
        role = "reader"
    else:
        role = "pure"
    tx = ("own TSTART/TCOMMIT in the static closure" if "TSTART" in flags else
          ("caller's write transaction" if "write_txn" in flags else "none in the static closure"))
    r = {"id": ep["id"], "role": role, "source": f"{ep['path']}:{ep['start']}-{ep['end']}",
         "reads": {"tables": ["Graph_KG." + t for t in r_t], "globals": r_g},
         "writes": {"tables": ["Graph_KG." + t for t in w_t], "globals": w_g},
         "transaction": tx,
         "locks": [{"lock": l[1:], "mode": "+" if l.startswith("+") else "-", "timeout": "see source" if "LOCK-TIMEOUT" in flags else "none",
                    "source": f"{ep['path']}:{ep['start']}-{ep['end']}"} for l in h.get("locks", []) if l.startswith("+")],
         "nolock": ["%NOLOCK"] if "%NOLOCK" in flags else [],
         "derivation": "static source closure (inventory hint): ObjectScript ##class/..M/$ClassMethod calls and Python self.m / classMethodValue calls; process-private ^|| and IRISTEMP excluded",
         "journal_validation": None, "notes": ""}
    m = MAN.get(ep["id"])
    if m:
        r.update({k: v for k, v in m.items()})
        r["derivation"] = "source reading (path:lines in source)"
    for e in fp_by.get(ep["id"], []):
        jv = {"log": f"$RUN_DIR/breadth-b/live/10-live-fp.json#{e['id']}", "run_id": "b-10-live-fp",
              "declared_stores": e["declared_stores"], "observed_stores": e["observed_stores"], "match": e["match"],
              "undeclared": e["undeclared"], "outside_txn": e["outside_txn"], "outside_txn_stores": e["outside_txn_stores"],
              "error": e["error"], "notes": ""}
        if r["journal_validation"] is None:
            r["journal_validation"] = jv
        else:
            r.setdefault("journal_validation_more", []).append(jv)
    if ep["id"] == "eng:IRISGraphEngine.betweenness_centrality" and nkg_fp:
        r.setdefault("journal_validation_more", []).append(
            {"log": "$RUN_DIR/breadth-b/live/10-live-nkg.json#fp-betweenness-stale-rebuild", "run_id": "b-10-live-nkg",
             "condition": "^NKG marked stale (a named graph lost its last edge): EnsureNKG rebuilds before reading",
             "observed_stores": sorted({x for v in nkg_fp.get("footprint", {}).values() for x in v}),
             "per_process": nkg_fp.get("footprint"), "outside_txn": nkg_fp.get("outside_txn"), "error": nkg_fp.get("error")})
    fps.append(r)
validated = [r for r in fps if r["journal_validation"]]
mism = [r["id"] for r in validated if not r["journal_validation"]["match"]]
footprints = {"module": "10", "pin": "3eaa79cf", "inventory": "experiment/playbook-completion/models/breadth-b/inventory/10.json",
              "oracle": "experiment/playbook-completion/traces/journal.py via live/breadth-b/blive.capture (AUDITB journal)",
              "summary": {"entry_points": len(fps), "by_role": {k: sum(1 for r in fps if r["role"] == k) for k in sorted({r["role"] for r in fps})},
                          "journal_validated": len(validated), "mismatches": mism,
                          "note": "Readers are validated for 'writes only declared work areas and caches' (ALG-I6); process-private ^|| globals are not journaled and so not observable here."},
              "entry_points": fps}
(COMP / "footprints/10.json").write_text(json.dumps(footprints, indent=1) + "\n")
print("footprints", footprints["summary"])


# ------------------------------------------------------------------------------------------------ modules/10.json
def res_ids(prefix=""):
    return sorted(k for k in RES if k.startswith(prefix))


met = {k: v.get("met") for k, v in RES.items() if v}
by_design = {}
for k, v in RES.items():
    if not v:
        continue
    d = by_design.setdefault(v["design"], {"met": 0, "not_met": 0})
    d["met" if v["met"] else "not_met"] += 1
rec_sum = (REC or {}).get("summary", {})
ref_by = (ref or {}).get("by_statement", {})
xs_live_ok = sorted(k for k, v in ref_by.items() if v)
xs_live_bad = sorted(k for k, v in ref_by.items() if not v)
env = [
    {"feature": "$Increment on a global as a cross-process version token (^KG(\"__version\"), ^NKG(\"$meta\",\"version\")); atomic, never rolled back (P-1002)",
     "used_for": "result-cache token and snapshot version", "source": "iris_src/src/Graph/KG/ArnoAccel.cls:299-303; iris_src/src/Graph/KG/Adjacency.cls:131-136"},
    {"feature": "LOCK +name:timeout with $TEST (exclusive, incremental) on ^IVG.NKGBuild",
     "used_for": "one ^NKG rebuild at a time (ALG-B12.3)", "source": "iris_src/src/Graph/KG/TraversalBuild.cls:288-298, :410-424"},
    {"feature": "lock-free global reads concurrent with writers (read-uncommitted visibility of ^KG/^NKG; a long run may see a mix, ALG-P6)",
     "used_for": "every algorithm's reads", "source": "iris_src/src/Graph/KG/PageRank.cls:87-116; iris_src/src/Graph/KG/NKGAccelTraversal.cls:187-222"},
    {"feature": "$Order / $Data traversal in subscript collation order (canonical numbers first, then strings)",
     "used_for": "deterministic ranking and tie order; cut after ordering (PageRank 10,000 rows)", "source": "iris_src/src/Graph/KG/PageRank.cls:500-521; iris_vector_graph/_engine/algorithms.py:392-420"},
    {"feature": "process-private globals ^||name (not journaled, per process)",
     "used_for": "work areas (^||PPR, ^||walkNbrs, ^||LargeOut, ^||IVG.CPUs, ^||NKGAccel)", "source": "iris_src/src/Graph/KG/PageRank.cls:506-521; iris_src/src/Graph/KG/NKGAccelTraversal.cls:198-205; iris_src/src/Graph/KG/NKGAccelAdjacency.cls:217-228; iris_src/src/Graph/KG/VarLength.cls:263-270"},
    {"feature": "IRISTEMP globals ^IRIS.Temp.* shared across worker processes (not journaled)",
     "used_for": "variable-length walk partitions", "source": "iris_src/src/Graph/KG/VarLength.cls:342-404"},
    {"feature": "persistent per-pid work globals killed after use (^bcParSrc, ^bcParScore, ^bcBitAdj; ^ArnoKG(\"bfs_r\"/\"bfs_chunk\"))",
     "used_for": "parallel betweenness and BFS staging", "source": "iris_src/src/Graph/KG/NKGAccelCentrality.cls:325, :440, :470, :582; iris_src/src/Graph/KG/TraversalBFS.cls:312-318, :458"},
    {"feature": "JOB worker processes sized by $System.Util.NumberOfCPUs()",
     "used_for": "parallel betweenness, variable-length last level", "source": "iris_src/src/Graph/KG/NKGAccelCentrality.cls:381, :560; iris_src/src/Graph/KG/VarLength.cls:263-270"},
    {"feature": "embedded Python class methods [Language = python] with iris.sql.exec / iris.cls",
     "used_for": "PageRankEmbedded, ClosenessJsonPy, LeidenJsonPy (leidenalg/igraph when installed in mgr/python)", "source": "iris_src/src/Graph/KG/PageRankEmbedded.cls:5-30, :106-131; iris_src/src/Graph/KG/Communities.cls:543, :615"},
    {"feature": "unqualified SQL table names resolved in the namespace's default schema (SQLUser) from embedded Python",
     "used_for": "PageRankEmbedded (F-1013)", "source": "iris_src/src/Graph/KG/PageRankEmbedded.cls:19-25"},
    {"feature": "$ZF(-5) callout library loading and calls, with the $ZF heap limit (34,808 chars at default zfheap, P-1003)",
     "used_for": "Arno native readers; BFS size gate ZFMAXCHARS", "source": "iris_src/src/Graph/KG/NKGAccelTraversal.cls:17, :279-286; iris_vector_graph/stores/arno_bridge.py:137-350"},
    {"feature": "runtime CREATE FUNCTION DDL for $ZF wrapper functions", "used_for": "Arno SQL wrappers",
     "source": "iris_vector_graph/stores/arno_bridge.py:106-136, :360-378"},
    {"feature": "namespace switch of a process (Arno readers read USER's ^KG whatever namespace calls, P-1001)",
     "used_for": "native route only in USER", "source": "iris_vector_graph/stores/iris_sql_store.py:883-894; iris_src/src/Graph/KG/ArnoAccel.cls"},
    {"feature": "%DynamicArray / %DynamicObject JSON (%ToJSON, %FromJSON)", "used_for": "algorithm answers",
     "source": "iris_src/src/Graph/KG/PageRank.cls:502-521; iris_src/src/Graph/KG/VarLength.cls:14-25"},
    {"feature": "$ListBuild / $ListGet values", "used_for": "cache entries $LB(token, payload)", "source": "iris_src/src/Graph/KG/AlgoCache.cls:27-50"},
    {"feature": "long strings and the Native API string limit (answers chunked at 9,000 chars into ^||LargeOut; cache payloads up to 1,000,000 chars)",
     "used_for": "large algorithm answers", "source": "iris_src/src/Graph/KG/NKGAccelAdjacency.cls:217-228; iris_vector_graph/algo_cache.py:21-28"},
    {"feature": "$Random", "used_for": "random walk", "source": "iris_src/src/Graph/KG/NKGAccelTraversal.cls:206-208"},
    {"feature": "SQL COUNT(*) and MAX(%ID) with RowIDs never reused (monotonic row ids)",
     "used_for": "global PageRank's node-set cache token (R313); sound only with node deletes raising ^KG(\"__version\")", "source": "iris_vector_graph/_engine/algorithms.py:179-193"},
    {"feature": "Kill of a whole global outside any transaction", "used_for": "cache invalidation", "source": "iris_src/src/Graph/KG/AlgoCache.cls:54-66; iris_src/src/Graph/KG/Eraser.cls:1052"},
    {"feature": "embedded SQL / %SQL.Statement reads of Graph_KG.nodes at default isolation", "used_for": "seed checks, edgeless nodes",
     "source": "iris_src/src/Graph/KG/PageRank.cls:87-116; iris_vector_graph/_engine/algorithms.py:619-626"},
    {"feature": "$SYSTEM.Status / %Status error reporting through the Native API (<THROW>, <PROTECT>)", "used_for": "refused work-area writes (ALG-B9.3)",
     "source": "iris_vector_graph/_engine/algorithms.py:100-133"},
]
so = load(RUN / "checks/storage-order.json") or []
owned_files = {"iris_vector_graph/_engine/algorithms.py", "iris_vector_graph/arno_readers.py", "iris_vector_graph/_arno_gate.py",
               "iris_vector_graph/algo_cache.py", "iris_vector_graph/stores/arno_bridge.py"}
owned_cls = {"Algorithms", "PageRank", "PageRankEmbedded", "Centrality", "Communities", "Subgraph", "Traversal", "TraversalBFS",
             "TraversalKHop", "TraversalPaths", "VarLength", "NKGAccel", "NKGAccelAdjacency", "NKGAccelCentrality",
             "NKGAccelLoader", "NKGAccelTraversal", "ArnoAccel", "AlgoCache"}
store_alg_spans = [(e["start"], e["end"], e["id"]) for e in (INV or {}).get("entry_points", [])
                   if e["path"] == "iris_vector_graph/stores/iris_sql_store.py"]
gds_spans = [(1039, 1110, "engine gds.* procedure handlers")]
in_module, near = [], []
seen = set()
for x in so:
    key = (x["file"], x["line"])
    if key in seen:
        continue
    seen.add(key)
    f, ln = x["file"], x["line"]
    mine = (f in owned_files or (f.startswith("iris_src/src/Graph/KG/") and Path(f).stem in owned_cls)
            or (f == "iris_vector_graph/stores/iris_sql_store.py" and any(a <= ln <= b for a, b, _ in store_alg_spans))
            or (f == "iris_vector_graph/engine.py" and any(a <= ln <= b for a, b, _ in gds_spans)))
    (in_module if mine else near).append({"file": f, "line": ln, "kind": x["kind"], "sql": x["sql"][:120]})
near_mod = []
for x in near:
    if x["file"] in ("iris_vector_graph/stores/iris_sql_store.py",) or x["file"].startswith("iris_vector_graph/engine.py"):
        owner = {"iris_vector_graph/stores/iris_sql_store.py": "06 (execute_knn_vec, iris_sql_store.py:2568-2651)"}.get(x["file"], "08/02 (engine procedure handlers and graph probes)")
        near_mod.append({**x, "disposition": "not-module-10", "owner": owner})
storage_order = {
    "input": "$RUN_DIR/checks/storage-order.json (experiment/playbook-completion/tools/storage_order_check.py, self-tested)",
    "sites_in_module_10": in_module,
    "dispositions": [],
    "adjacent_sites_checked": near_mod,
    "non_sql_prefix_cuts_reviewed": [
        {"site": "iris_src/src/Graph/KG/PageRank.cls:500-521", "disposition": "unique-key",
         "why": "rows are emitted in ^||PPR(-score, node id) order and cut at 10,000: (score, node id) is unique; the cut itself is F-1003"},
        {"site": "iris_vector_graph/_engine/algorithms.py:392-420", "disposition": "unique-key",
         "why": "_ppr_every_node: SELECT TOP n node_id ... ORDER BY node_id (ordered); ties among scores by id (rank_key)"},
        {"site": "iris_vector_graph/_engine/algorithms.py:600-616", "disposition": "unique-key",
         "why": "khop keeps the first max_nodes ids in BFS reach order, which follows BFSFastJson's $Order walk (deterministic for a given ^KG)"},
    ],
    "result": "0 of the 109 flagged SQL texts lie in module 10's owned code; nothing to disposition there",
}
G = {}


def gate(gid, status, evidence, remaining="", reason=""):
    G[gid] = {"status": status, "reason": reason, "evidence": evidence, "remaining": remaining}


gate("3.1-parent", "closed", [{"kind": "check", "ref": "b-10-check-ontology-index"}],
     reason="ontology_index.py --check --only 10: every ALG parent id resolves (0 violations).")
gate("3.1-grade", "closed", [{"kind": "check", "ref": "b-10-check-ontology-index"}],
     reason="ontology_index.py --check --only 10: every ALG statement at Flesch-Kincaid grade <= 8.")
gate("3.1-terms", "open", [{"kind": "check", "ref": "b-10-check-literal-scope"}, {"kind": "check", "ref": "b-10-check-ontology-index"}],
     reason="Lexical-scope reading: 0 violations; literal rule adopted by decisions.md HD-0001: 36 statement/term pairs in 30 ALG statements fail.",
     remaining="Rewrite or reparent the 30 ALG statements (orchestrator's ontology lane).")
open_cells = [c for c in (INV or {}).get("cells", []) if c["outcome"] == "open"]
gate("3.1-cells", "closed", ["experiment/playbook-uplift/ontology/10-algorithms.md (Cells)", "experiment/playbook-completion/decisions.md (HD-1001)",
                             "models/breadth-b/inventory/10.json"],
     reason=f"All {len((INV or {}).get('cells', []))} cells have an outcome; {len(open_cells)} are 'open', each assigned to HD-1001 (random walk), which "
            "decisions.md gives a working assumption; every cell maps to at least one entry point (inventory cell_map).")
gate("3.1-coverage", "open", ["models/breadth-b/inventory/10.json", "$RUN_DIR/breadth-b/inventory/10-reconcile.json", "live/breadth-b/10_reconcile.py"],
     remaining=f"{(INV or {}).get('counts', {}).get('omissions')} of {(INV or {}).get('counts', {}).get('entry_points')} mechanically derived entry points are named by no ALG statement: "
               f"{rec_sum}. Genuine omissions are the direct-surface-only public class methods (PageRankEmbedded.ComputePageRank*, PageRank.WithUnscored, "
               "Communities.KCoreJson/SCCJson, Subgraph.PPRGuidedJson, ArnoAccel.*Json, legacy Traversal.BFS*/KHop2*, NKGAccel facades, "
               "VarLength.LastLevelPart, arno_bridge helpers) and the product-caller set (host.py, admin.py, query.py callers); "
               "statements or explicit internal/deprecated status are needed for each.",
     reason="Reconciled mechanically: other-module (cypher procs, builders, other modules' writers) and reached-from-covered entries are not omissions.")
gate("3.1-intent", "open", ["experiment/playbook-completion/decisions.md (HD-1001..HD-1004)"],
     remaining="Owned by the intent lanes: HD-1001..1004 carry working assumptions, not maintainer decisions.")
gate("3.2-coverage", "open", ["modules/10.json env_features"],
     remaining=f"{len(env)} IRIS features listed with source lines; the orchestrator's IRIS 2026.1 contract must cover or mark each outside its subset.")
gate("3.3-L1", "closed" if all(met.get(k) for k in res_ids("m10-")) and RES else "open",
     [{"kind": "mc", "ref": k} for k in res_ids("m10-")],
     reason="Five small explorer models (cache, nkg, routes, walk, degree) state ALG-I1, ALG-I2, ALG-I3, ALG-I4, ALG-B2.19, ALG-B12.7, ALG-B16.11 as invariants/action properties.",
     remaining="Explorer models are bounded executable L1s, not Verus specs.")
gate("3.3-L2", "open", [{"kind": "mc", "ref": "m10-cache-as-built-ppr"}, {"kind": "mc", "ref": "m10-nkg-as-built-fresh"}],
     remaining="The cache and nkg machines abstract ^IVG.AlgoCache / ^KG / ^NKG marks; no L2 over the full global layout.")
gate("3.3-refinement", "open", [], remaining="No refinement audit or proof of the module 10 operations against an L1.")
gate("3.3-controls", "open", [{"kind": "mc", "ref": k} for k in res_ids("m10-") if "control" in k],
     reason="Every explorer control is caught (mc), none by a proof.", remaining="Proof-level controls (Verus).")
gate("3.3-model-check", "closed" if RES and all(met.values()) else "open", [{"kind": "mc", "ref": k} for k in res_ids("m10-")],
     reason=f"{sum(1 for v in met.values() if v)} of {len(met)} checks met their expectation: {by_design}; as-built vs reviewed per modelable finding, controls caught, sharpness witnesses reached, AG EF goals in cache and nkg.")
gate("3.3a-writesets", "failed", ["modules/10.json invariant_writesets"],
     reason="Every (invariant, writer plan) pair is discharged by a guard, a model check, a live observation or a recorded finding; the pairs discharged only by product-defect findings (F-1004 edgeless node write vs ALG-I4; F-1005 PutShadow vs ALG-B12.7) are failed obligations.",
     remaining="Fixes or decisions for F-1004 and F-1005.")
gate("3.4-statements", "open", [], remaining="No storage-statement proofs for the cache Put / Lookup or ^NKG writes.")
gate("3.4-ownership", "open", ["footprints/10.json"],
     reason="^IVG.AlgoCache: written by AlgoCache.Put, killed by AlgoCache.Invalidate* and Eraser.InvalidateDerived (documented, ALG-B16.10). ^NKG: BuildNKG (spec 260 D-NKG-WRITER) plus Adjacency.Put interning, Eraser DropNKG and ArnoAccel.BumpVersion's $meta version: several writers. ^KG(\"degc\") (module 04's degree cache) is filled by module 10 reads (Adj.cls:64-79). ^IVG.Deploy(\"routines\") (setup's record) is written by a read path (F-C1001).",
     remaining="A mechanical single-owner check with a self-test over these globals.")
gate("3.4-storage-order", "closed", ["$RUN_DIR/checks/storage-order.json", "modules/10.json storage_order"],
     reason="0 of 109 flagged SQL texts lie in module 10's owned code; the non-SQL prefix cuts reviewed are ordered by a unique key (storage_order.non_sql_prefix_cuts_reviewed).")
gate("3.4-declared-reads", "open", ["footprints/10.json"], remaining="Reads are declared from the static closure; no read-footprint check with a self-test.")
gate("3.5-handlers", "failed", [{"kind": "finding", "ref": r["id"]} for r in F + NEW if r["outcome"] == "product-defect"],
     reason="Several handlers do not perform their stated step (F-1002, F-1003, F-1004, F-1005 narrowed, F-1006, F-1007, F-1008, F-1009, F-1010, F-1013) or write beyond a read's footprint (F-C1001).",
     remaining="No handler is proved; the listed defects stay failed.")
gate("3.5-lockplans", "open", ["footprints/10.json"],
     reason="Lock plan: ^IVG.NKGBuild with timeout for rebuilds; every algorithm read is lock-free (ALG-P6); cache freshness relies on the token protocol instead of locks (m10-cache-as-built-pagerank holds within bounds).",
     remaining="No lock-plan proof.")
gate("3.5-decoders", "open", [{"kind": "run", "ref": "b-10-run-unit"}],
     reason="JSON decoders (_scored_node_rows, UnreadableResultShape) and error maps (_raise_store_error, ALG-I5) are unit-tested (349 passed here).",
     remaining="Not verified.")
gate("3.6-row-permutation", "open", [{"kind": "run", "ref": "b-10-run-unit"}],
     reason="Rankings break ties by id (R050, unit-tested); F-1006 is an order-dependent answer when two embedding rows match.",
     remaining="No proof that answers are invariant under row permutation.")
gate("3.6-capacity", "failed", [{"kind": "finding", "ref": "F-1003"}] + live("b-10-live-cap"),
     reason="Capacity conditions: PageRank owner cut at 10,000 rows (silent; F-1003), Arno $ZF heap 34,808 chars (P-1003), answers chunked at 9,000 chars, cache payloads up to 1,000,000 chars (ALG-B16.5).",
     remaining="F-1003 (silent truncation) stays failed; the $ZF limit is a premise.")
gate("3.6-frame", "open", [], remaining="No frame obligations stated for the cache/^NKG writers.")
gate("3.6-keys", "failed", [{"kind": "finding", "ref": "F-1004"}, {"kind": "mc", "ref": "m10-cache-as-built-ppr"}],
     reason="The PPR cache key (graph, algorithm, param hash) omits the node set it reads (F-1004).")
gate("3.6-fk", "not-applicable", ["footprints/10.json", "$RUN_DIR/breadth-b/live/10-live-fp.json"],
     reason="Module 10 writes no SQL data row (journal b-10-live-fp: globals ^IVG.AlgoCache, ^NKG, ^KG, work areas; sync's %BuildIndices writes only index storage of rdf_edges/rdf_labels); no foreign key is involved.")
gate("3.7-trace-replay", "open", [], remaining="Live traces (b-10-live-cache, b-10-live-nkg-f1005) are not replayed through the machines.")
gate("3.7-lock-log", "open", [], remaining="No statement/lock log checked against the lock plan.")
gate("3.7-mutation", "open", [], remaining="No mutation testing of module 10's unverified layers.")
gate("3.8-findings-disposed", "closed", ["findings/audit/10.json"],
     reason=f"All {len(F)} original findings carry a disposition with evidence ({bd}); {len(NEW)} new.")
gate("5c-refusals", "open", live("b-10-live-refusals") + [{"kind": "run", "ref": "b-10-run-unit"}],
     reason=f"30 X statements: 17 upstream-tested, 13 inspected only at the uplift; live here: holds {xs_live_ok}, not holding {xs_live_bad}; ALG-B7 refusal seen live (b-10-live-nkg).",
     remaining="ALG-B5.5, B5.21 (store without a method), B9.3 (read-only login), B12.3 (concurrent rebuild wait), B12.8 (failing rebuild), B13.3, B15.x (gate) are not exercised live.")
gate("3.7-explorers", "closed" if RES else "open", [{"kind": "mc", "ref": k} for k in res_ids("m10-")], reason="Module 10's explorer checks ran (product-scope gate; module evidence).")
gate("3.7-suites", "open", [{"kind": "run", "ref": "b-10-run-unit"}],
     reason="349 IRIS-free module-10 unit tests passed; IRIS-backed upstream suites were not run (their fixture compiles classes).")
gate("3.3-progress-controls", "open", [{"kind": "mc", "ref": "m10-cache-reviewed-ppr"}, {"kind": "mc", "ref": "m10-nkg-reviewed"}],
     reason="AG EF goals hold in the reviewed cache and nkg machines; no progress-only control.")

inv_ws = [
    {"invariant": "ALG-I4 / ALG-B16.11 / ALG-B2.19 (a served cached answer equals a fresh computation)",
     "reads": ["^IVG.AlgoCache", "^KG(\"__version\")", "Graph_KG.nodes", "^KG(\"out\")"],
     "plans": [
         {"plan": "ext:IRISGraphEngine.create_edge (Adjacency.Put)", "writes": ["^KG(\"out\")", "^KG(\"__version\")"], "discharge": "guard: $Increment ^KG(\"__version\") (Adjacency.cls:131-136); mc m10-cache-reviewed-ppr"},
         {"plan": "ext:IRISGraphEngine.create_node (edgeless)", "writes": ["Graph_KG.nodes", "Graph_KG.rdf_props"], "discharge": "finding F-1004 (live b-10-live-cache; mc m10-cache-as-built-ppr); PageRank's R313 node-token key covers global PageRank (mc m10-cache-as-built-pagerank)"},
         {"plan": "ext:IRISGraphEngine.delete_node (Eraser.EraseNodeIds)", "writes": ["Graph_KG.nodes", "^KG", "^IVG.AlgoCache (Kill)"], "discharge": "guard: InvalidateDerived bumps the token and kills the cache (Eraser.cls:1038-1053; live b-10-live-cache)"},
         {"plan": "ext:Graph.KG.Eraser.EraseGraph", "writes": ["rows", "^KG", "^IVG.AlgoCache (Kill)"], "discharge": "guard: InvalidateDerived (Eraser.cls:1038-1053)"},
         {"plan": "ext:Graph.KG.Adjacency.PutShadow", "writes": ["^KG(\"out\")", "^KG(\"__version\")"], "discharge": "guard: $Increment token (Adjacency.cls:131-136)"},
         {"plan": "cls:Graph.KG.AlgoCache.Put", "writes": ["^IVG.AlgoCache"], "discharge": "token read before compute (AlgoCache.cls:1-13); mc m10-cache-as-built-pagerank, m10-cache-reviewed-*"},
     ]},
    {"invariant": "ALG-B12.7 / SYS-I8 (a snapshot reader sees the adjacency index's edges or learns it is stale)",
     "reads": ["^NKG", "^NKG(\"$meta\")", "^KG(\"out\")"],
     "plans": [
         {"plan": "ext:IRISGraphEngine.create_edge (Adjacency.Put)", "writes": ["^KG", "^NKG (interned when built)"], "discharge": "guard: Put interns (Adjacency.cls:94-105); mc m10-nkg-reviewed"},
         {"plan": "ext:Graph.KG.Adjacency.PutShadow", "writes": ["^KG", "^KG(\"__version\")"], "discharge": "finding F-1005 (live b-10-live-nkg-f1005; mc m10-nkg-as-built-fresh)"},
         {"plan": "Adjacency.Remove (last named edge)", "writes": ["^KG", "^NKG", "^NKG(\"$meta\",\"stale\")"], "discharge": "guard: stale mark (Adjacency.cls:169-180); live b-10-live-nkg (fp-betweenness-stale-rebuild)"},
         {"plan": "ext:Graph.KG.Eraser.EraseGraph", "writes": ["^NKG (DropNKG)", "^NKG(\"$meta\",\"invalidated\")"], "discharge": "guard: InvalidateDerived (Eraser.cls:1038-1046); mc m10-nkg-reviewed"},
         {"plan": "eng:IRISGraphEngine.sync / ext:Graph.KG.TraversalBuild.EnsureNKG", "writes": ["^NKG"], "discharge": "rebuild from ^KG under ^IVG.NKGBuild (TraversalBuild.cls:288-298, :399-424)"},
     ]},
    {"invariant": "ALG-I6 (a read algorithm changes no content; it writes only its work areas and caches)",
     "reads": ["Graph_KG tables", "^KG", "^NKG"],
     "plans": [{"plan": "17 journal-validated module-10 readers (footprints/10.json)", "writes": ["^IVG.AlgoCache", "^KG(\"degc\") degree cache", "^NKG (EnsureNKG rebuild)", "^IVG.BuiltFrom", "^bc*/^ArnoKG work areas"],
                "discharge": "live b-10-live-fp: caches and work areas only, no SQL data row"},
               {"plan": "eng:IRISGraphEngine.triangle_count (Arno probe path)", "writes": ["^IVG.Deploy(\"routines\")", "class dictionary (^oddDEP, ^oddTSQL): 12 SQL functions"],
                "discharge": "finding F-C1001 (live b-10-live-fp, b-10-live-fp-detail)"}]},
]
counts = {
    "entry_points": (INV or {}).get("counts", {}).get("entry_points"), "omissions": (INV or {}).get("counts", {}).get("omissions"),
    "omissions_reconciled": rec_sum, "cells": (INV or {}).get("counts", {}).get("cells"),
    "cells_without_entry_point": (INV or {}).get("counts", {}).get("cells_without_entry_point"),
    "footprints": len(fps), "footprints_journal_validated": len(validated), "footprint_store_mismatches": len(mism),
    "model_checks": len(met), "model_checks_met": sum(1 for v in met.values() if v), "model_checks_by_design": by_design,
    "original_findings": len(F), "findings_by_disposition": bd, "findings_by_outcome": bo, "new_findings": len(NEW),
    "env_features": len(env), "storage_order_sites_in_module": len(in_module),
}
module = {"module": "10", "lane": "breadth-b", "pin": "3eaa79cf",
          "gates": [{"gate": k, **v} for k, v in G.items()], "gates_by_id": G,
          "entry_point_omissions": {
              "method": "live/breadth-b/10_reconcile.py over models/breadth-b/inventory/10.json (statement covers an entry point when it cites its file with an overlapping line range or names it)",
              "summary": rec_sum,
              "genuine": sorted(k for k, v in ((REC or {}).get("classified", {})).items() if v["class"] in ("direct-surface-only", "product-caller")),
              "wrappers": sorted(k for k, v in ((REC or {}).get("classified", {})).items() if v["class"] == "objectscript-caller-only"),
              "cells_without_entry_point": (INV or {}).get("cells_without_entry_point", []),
              "entry_points_in_no_cell": len((INV or {}).get("entry_points_in_no_cell", [])),
          },
          "invariant_writesets": inv_ws, "env_features": env, "storage_order": storage_order, "counts": counts,
          "registered_runs": sorted(RUNS)}
(COMP / "modules/10.json").write_text(json.dumps(module, indent=1) + "\n")
print("module", counts)
