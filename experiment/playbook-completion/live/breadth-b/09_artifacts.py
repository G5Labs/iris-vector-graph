"""Write module 09's audit artifacts from the inventory, the live logs and the model results (no IRIS access).

    python experiment/playbook-completion/live/breadth-b/09_artifacts.py

Outputs: experiment/playbook-completion/footprints/09.json, findings/audit/09.json, modules/09.json.
Inputs: models/breadth-b/inventory/09.json, $RUN_DIR/breadth-b/live/09-*.json, models/breadth-b/results/m09-*.json,
evidence/runs/b-09-*.json, $RUN_DIR/checks/storage-order.json.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMP = HERE.parents[1]
RUN = Path(os.environ["RUN_DIR"])
LIVE = RUN / "breadth-b" / "live"
INV = json.loads((COMP / "models/breadth-b/inventory/09.json").read_text())


def live(name):
    """A part's log, only when the part completed (an exception log is not evidence of the product's behaviour)."""
    p = LIVE / f"09-{name}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    return d if d.get("status") == "done" else None


def mc(i):
    p = COMP / "models/breadth-b/results" / f"{i}.json"
    return json.loads(p.read_text()) if p.exists() else None


def reg(i):
    return (COMP / "evidence/runs" / f"{i}.json").exists()


L = {n: live(n) for n in ["probe", "footprint", "f0903", "f0905", "f0901", "f0902", "f0907", "f0909", "f0904", "f0906"]}
G = "iris_src/src/Graph/KG/Cypher/Gen.cls"
E = "iris_src/src/Graph/KG/Cypher/Exec.cls"
P = "iris_src/src/Graph/KG/Cypher/Props.cls"
Q = "iris_vector_graph/_engine/query.py"
NP = "iris_vector_graph/cypher/native_plan.py"

# ------------------------------------------------------------------------------------------------ footprints
PP = ["^||IVG.CypherOut", "^||IVG.CypherRun", "^||IVG.CypherProps", "^||IVG.CypherMemo", "^||IVG.CypherGenFailed",
      "^||IVG.CypherCompiledRuns", "^||IVG.CypherDegreeTally", "^||IVG.CypherNamedEnds", "%ivgCypherPropsStmt (process variable)"]
RUN_READS = {"tables": ["Graph_KG.nodes (Exec.Anchors :856-869)", "Graph_KG.rdf_props (Anchors :886-899, NamedEnds :1101-1109; Props.Get SQL fallback :64-70)",
                        "%Dictionary.CompiledStorage/CompiledStorageIndex/CompiledIndex/CompiledStorageDataValue/CompiledClass (Props.Resolve/Stamp :29-41, :106-110; NamedEnds :1103)"],
             "globals": ["^KG(\"label\", g, label, id) (RunA :241-266, NodeOK, Neighbours :1191-1197)", "^KG(\"out\"/\"in\", g, s, p, o[, ekey]) (Neighbours :1174-1250)",
                         "^KG(\"__version\") (Recall :817)", "rdf_props data/index storage globals by name (Props.Get :56-60; RunA tQ(\"pd\") :131-132)",
                         "degree cache via Graph.KG.Adj.Cached (module 04)", "^IVG.CypherCompiled(h) (Gen.For :70)", "^IVG.CypherGen(\"mode\"/\"breakfor\"/\"breakwrite\"/\"breaktest\") (Gen :43, :78, :267, :193)"]}


def fp(id_, role, source, reads, writes, txn, locks=(), nolock=(), notes="", jv=None):
    return {"id": id_, "role": role, "source": source, "reads": reads, "writes": writes, "transaction": txn,
            "locks": list(locks), "nolock": list(nolock), "journal_validation": jv, "notes": notes}


NOLOCK_READ = ["no LOCK, no snapshot: globals read with $Order/$Data at the moment of each read; SQL by %SQL.Statement at the "
               "process default isolation (read uncommitted, P-0002); NAT-T4.6"]
ENTRY_W = "^IVG.CypherCompiled(h) = $LB(class, shape, stamp, status, began) and (h, \"src\", i)"
fps = {}
fps["cls:Graph.KG.Cypher.Exec.PlanVersion"] = fp("cls:Graph.KG.Cypher.Exec.PlanVersion", "pure", f"{E}:19-22", {"tables": [], "globals": []}, {"tables": [], "globals": []}, "none")
fps["cls:Graph.KG.Cypher.Exec.BuiltAt"] = fp("cls:Graph.KG.Cypher.Exec.BuiltAt", "pure", f"{E}:25-29", {"tables": [], "globals": []}, {"tables": [], "globals": []}, "none", notes="objectgenerator: the compile time is a literal in the code")
fps["cls:Graph.KG.Cypher.Exec.Run"] = fp("cls:Graph.KG.Cypher.Exec.Run", "reader (writes a plan cache)", f"{E}:32-72 (RunA :110-285, Parallel :447-511, Gen.For {G}:61-105)",
    RUN_READS, {"tables": [], "globals": PP + ["^IRIS.Temp.IVG.Cypher(share, ...) (Parallel :451-505, Out :1889-1898; IRISTEMP, not journaled)",
                                              ENTRY_W + " (through Gen.For, a new or stale shape in job/sync mode; persistent, outside any transaction)",
                                              "IVGC.P<h> class (Gen.Build in sync mode, in this process)"]},
    "none: no TSTART; the entry writes of Gen.For are plain Sets (not rolled back with a caller's transaction); a caller's open transaction is not joined or ended",
    locks=["through Gen.Build (sync mode): Lock +^IVG.CypherCompiled(h):0, no wait"], nolock=NOLOCK_READ,
    notes="rows of a run live in ^||IVG.CypherOut(tag) (first 1000 returned inline and freed, Head :76-87)")
fps["cls:Graph.KG.Cypher.Exec.Part"] = fp("cls:Graph.KG.Cypher.Exec.Part", "reader (worker)", f"{E}:540-554", RUN_READS,
    {"tables": [], "globals": ["^IRIS.Temp.IVG.Cypher(share, \"rows\"/\"sort\"/\"k\"/\"c\"/\"d\"/\"seq\") (Export :560-589, Out :1882-1899)", "^||IVG.VLWorker", "^||IVG.CypherProps", "^||IVG.CypherRun"]},
    "none", nolock=NOLOCK_READ, notes="%SYSTEM.WorkMgr worker; runs in its coordinator's compile mode (pPlan genmode, :454)")
fps["cls:Graph.KG.Cypher.Exec.ReadPage"] = fp("cls:Graph.KG.Cypher.Exec.ReadPage", "reader", f"{E}:1902-1910", {"tables": [], "globals": ["^||IVG.CypherOut(tag, n)"]}, {"tables": [], "globals": []}, "none")
fps["cls:Graph.KG.Cypher.Exec.Drop"] = fp("cls:Graph.KG.Cypher.Exec.Drop", "writer (process-private)", f"{E}:1913-1916", {"tables": [], "globals": []}, {"tables": [], "globals": ["^||IVG.CypherOut(tag) (Kill)"]}, "none")
fps["cls:Graph.KG.Cypher.Gen.Mode"] = fp("cls:Graph.KG.Cypher.Gen.Mode", "writer (process-private)", f"{G}:28-39", {"tables": [], "globals": ["^IVG.CypherGen(\"mode\") (Effective)"]}, {"tables": [], "globals": ["^||IVG.CypherGenMode (Set or Kill)"]}, "none", notes="validates the value (NAT-X11); refuses others with an exception")
fps["cls:Graph.KG.Cypher.Gen.Effective"] = fp("cls:Graph.KG.Cypher.Gen.Effective", "reader", f"{G}:41-44", {"tables": [], "globals": ["^||IVG.CypherGenMode", "^IVG.CypherGen(\"mode\")"]}, {"tables": [], "globals": []}, "none", notes="namespace value unchecked (F-0903)")
fps["cls:Graph.KG.Cypher.Gen.ModeOf"] = fp("cls:Graph.KG.Cypher.Gen.ModeOf", "reader", f"{G}:47-50", {"tables": [], "globals": ["pQ(\"genmode\")", "^||IVG.CypherGenMode", "^IVG.CypherGen(\"mode\")"]}, {"tables": [], "globals": []}, "none")
fps["cls:Graph.KG.Cypher.Gen.BuiltAt"] = fp("cls:Graph.KG.Cypher.Gen.BuiltAt", "pure", f"{G}:53-57", {"tables": [], "globals": []}, {"tables": [], "globals": []}, "none")
fps["cls:Graph.KG.Cypher.Gen.For"] = fp("cls:Graph.KG.Cypher.Gen.For", "writer", f"{G}:61-105", {"tables": [], "globals": ["^IVG.CypherCompiled(h)", "^IVG.CypherGen(\"breakfor\"/\"breakwrite\") test hooks", "^||IVG.CypherProps(\"stamp\")"]},
    {"tables": [], "globals": [ENTRY_W + ": Set entry pending :80, Kill src :81, Merge src :89, Set $List(.,4) 'not written' :86", "JOB Gen.Build (job mode :96)", "Gen.Build inline (sync mode :101)", "^oddDEP (class-dependency dictionary global written by the class compiler, also from a system process; journal-observed)"]},
    "none: plain Sets/Kill/Merge outside any transaction, no lock between reading the entry (:70-71) and overwriting it (:80)",
    locks=[], nolock=["reads and overwrites the entry with no lock (F-0901: two colliding shapes overwrite each other)"],
    notes="key: tH = $ZCRC(shape, 7), 32 bits (:69, P-0901)")
fps["cls:Graph.KG.Cypher.Gen.Build"] = fp("cls:Graph.KG.Cypher.Gen.Build", "writer", f"{G}:163-222", {"tables": [], "globals": ["^IVG.CypherCompiled(h), (h, \"src\")", "^IVG.CypherGen(\"breaktest\")"]},
    {"tables": [], "globals": ["$List(^IVG.CypherCompiled(h), 1) = class and (.., 4) = \"ok\" (:207) or the error text (:210, :215) or \"refused...\" (:176)",
                               "class IVGC.P<h>: $System.OBJ.LoadStream + Compile (:204-205; class dictionary and routine globals, ^oddDEP journal-observed), $System.OBJ.Delete on failure (:213)",
                               "messages.log line on failure/refusal (:177, :212)"]},
    "none: no TSTART; class compile is not transactional",
    locks=[{"lock": "^IVG.CypherCompiled(h)", "mode": "+ exclusive", "timeout": "0 (Quit when not granted, :167)", "source": f"{G}:166-167, released :172, :180, :220"}],
    notes="writes elements 1 and 4 of whatever entry the hash holds at :207, without checking it still holds the shape compiled (F-C0901), and re-creates a killed entry as $LB(class,,,\"ok\") (F-0905)")
fps["cls:Graph.KG.Cypher.Gen.DropAll"] = fp("cls:Graph.KG.Cypher.Gen.DropAll", "writer", f"{G}:225-230", {"tables": [], "globals": []},
    {"tables": [], "globals": ["package IVGC: $System.OBJ.DeletePackage (:227; ^oddDEP and other class-dictionary globals)", "Kill ^IVG.CypherCompiled (:228)"]}, "none",
    locks=[], nolock=["takes no entry lock: a build compiling concurrently re-creates its entry and class after the drop (F-0905)"])
fps["cls:Graph.KG.Cypher.Gen.Source"] = fp("cls:Graph.KG.Cypher.Gen.Source", "reader", f"{G}:233-242", {"tables": [], "globals": ["^IVG.CypherCompiled(h, \"src\", i)"]}, {"tables": [], "globals": []}, "none", notes="NAT-T5.21: any caller of the generator reads entries' code")
fps["cls:Graph.KG.Cypher.Gen.Entries"] = fp("cls:Graph.KG.Cypher.Gen.Entries", "reader", f"{G}:245-254", {"tables": [], "globals": ["^IVG.CypherCompiled(h)"]}, {"tables": [], "globals": []}, "none", notes="$List(tE, 3) raises <NULL VALUE> on a broken entry (F-0905)")
fps["cls:Graph.KG.Cypher.Props.Layout"] = fp("cls:Graph.KG.Cypher.Props.Layout", "reader (process cache)", f"{P}:14-25 (Resolve :29-41, Stamp :106-110)", {"tables": ["%Dictionary.CompiledStorage", "%Dictionary.CompiledStorageIndex", "%Dictionary.CompiledIndex", "%Dictionary.CompiledStorageDataValue", "%Dictionary.CompiledClass"], "globals": []}, {"tables": [], "globals": ["^||IVG.CypherProps(\"stamp\"/\"data\"/\"index\"/\"slot\")"]}, "none")
fps["cls:Graph.KG.Cypher.Props.Get"] = fp("cls:Graph.KG.Cypher.Props.Get", "reader", f"{P}:44-72", {"tables": ["Graph_KG.rdf_props (SQL fallback, :64-70)"], "globals": ["rdf_props pkprops index and data globals by name (:57-60)"]}, {"tables": [], "globals": ["%ivgCypherPropsStmt (process public variable, :64-67)", "^||IVG.CypherProps (through Layout)"]}, "none", nolock=NOLOCK_READ)
fps["cls:Graph.KG.Cypher.Props.Begin"] = fp("cls:Graph.KG.Cypher.Props.Begin", "writer (process-private)", f"{P}:76-79", {"tables": ["%Dictionary (Layout)"], "globals": []}, {"tables": [], "globals": ["^||IVG.CypherProps(\"run\")"]}, "none")
fps["cls:Graph.KG.Cypher.Props.End"] = fp("cls:Graph.KG.Cypher.Props.End", "writer (process-private)", f"{P}:82-85", {"tables": [], "globals": []}, {"tables": [], "globals": ["^||IVG.CypherProps(\"run\") (Kill)"]}, "none")
fps["cls:Graph.KG.Cypher.Props.GetJson"] = fp("cls:Graph.KG.Cypher.Props.GetJson", "reader", f"{P}:88-97", {"tables": ["as Props.Get"], "globals": ["as Props.Get"]}, {"tables": [], "globals": ["as Props.Get"]}, "none")
fps["cls:Graph.KG.Cypher.Props.LayoutOK"] = fp("cls:Graph.KG.Cypher.Props.LayoutOK", "reader", f"{P}:100-103", {"tables": ["as Props.Layout"], "globals": []}, {"tables": [], "globals": ["^||IVG.CypherProps"]}, "none")
fps["cls:Graph.KG.Cypher.SortKey.Key"] = fp("cls:Graph.KG.Cypher.SortKey.Key", "pure", "iris_src/src/Graph/KG/Cypher/SortKey.cls:9-151", {"tables": [], "globals": []}, {"tables": [], "globals": []}, "none")
CE = "iris_src/src/IVG/CypherEngine.cls"
for m, span, role, rd, note in [
    ("Local", "27-33", "pure", [], "object constructor"),
    ("Remote", "35-53", "pure", [], "object constructor; default credentials _SYSTEM/SYS"),
    ("EnsureEngine", "56-94", "reader", [], "builds an IRISGraphEngine (remote mode: opens an IRIS connection)"),
    ("QueryJson", "97-132", "reader or writer", ["any Cypher: Graph_KG tables, ^KG (module 08's write footprint for writes)"], "execute_cypher without read_only: writes run too"),
    ("Query", "135-138", "reader or writer", ["as QueryJson"], ""),
    ("Scalar", "141-150", "reader or writer", ["as QueryJson"], "execute_cypher without read_only"),
    ("GetLabelsJson", "153-158", "reader", ["Graph_KG.rdf_labels (engine.get_labels)"], ""),
    ("GetLabels", "161-164", "reader", ["as GetLabelsJson"], ""),
    ("GetNodeCount", "167-171", "reader", ["Graph_KG.nodes / rdf_labels (engine.get_node_count)"], ""),
    ("GetEdgeCount", "174-178", "reader", ["Graph_KG.rdf_edges (engine.get_edge_count)"], ""),
    ("NodeExists", "181-185", "reader", ["Graph_KG.nodes"], ""),
    ("GetLabelCountsJson", "188-193", "reader", ["Graph_KG.rdf_labels"], ""),
    ("GetLabelCounts", "196-199", "reader", ["as GetLabelCountsJson"], ""),
    ("InitSchemaJson", "202-208", "writer", ["schema DDL, class deploy, Gen.DropAll (initialize_schema)"], "a lifecycle operation (module 01's footprint)"),
    ("InitSchema", "210-213", "writer", ["as InitSchemaJson"], ""),
    ("RebuildKG", "216-220", "writer", ["^KG rebuild (module 04's footprint)"], ""),
    ("IsReady", "223-230", "reader", ["Graph_KG tables"], ""),
    ("SmokeTest", "233-246", "writer", ["InitSchema when needed, then a node count"], ""),
]:
    w = rd if role.startswith("writer") or "writer" in role else []
    fps[f"cls:IVG.CypherEngine.{m}"] = fp(f"cls:IVG.CypherEngine.{m}", role, f"{CE}:{span}", {"tables": rd if "reader" in role else [], "globals": []},
                                          {"tables": w, "globals": []}, "the engine's (module 08 / 01 / 04)", notes=note)
for i, fn, span, role in [
    ("py:iris_vector_graph/cypher/native_plan.py:plan_query", "plan_query", "50-59", "pure"),
    ("py:iris_vector_graph/cypher/native_plan.py:native_gate", "native_gate", "524-536", "reader (cached gate facts)"),
    ("py:iris_vector_graph/cypher/native_route.py:NativeRoute.__init__", "NativeRoute.__init__", "33-55", "pure"),
    ("py:iris_vector_graph/cypher/native_route.py:NativeRoute.sql_failed", "NativeRoute.sql_failed", "71-74", "pure (in-memory route)"),
    ("py:iris_vector_graph/cypher/native_route.py:NativeRoute.next_path", "NativeRoute.next_path", "76-83", "pure (in-memory route)"),
    ("py:iris_vector_graph/cypher/native_route.py:NativeRoute.record", "NativeRoute.record", "85-107", "pure (in-memory route)"),
    ("py:iris_vector_graph/cypher/native_shadow.py:compare", "compare", "29-69", "pure"),
]:
    path = i.split(":")[1]
    fps[i] = fp(i, role, f"{path}:{span}", {"tables": [], "globals": []} if role.startswith("pure") else {"tables": ["first use: engine gate probes (engine.py:559-611, 703-724)"], "globals": []},
                {"tables": [], "globals": []}, "none")
fps["eng:IRISGraphEngine.execute_cypher[native]"] = fp("eng:IRISGraphEngine.execute_cypher[native]", "reader (native branch)", f"{Q}:2032-2082 (_try_native :2118-2160, _run_native_plan :2202-2224)",
    {"tables": ["Graph_KG.table_mappings (mapped-label check, :2162-2184)", "gate probes on first use"], "globals": ["as Exec.Run"]},
    {"tables": [], "globals": ["as Exec.Run (plan cache)"]}, "none of its own; a native read runs on the engine's native link (a separate process when from_connect knows the login, engine.py:1894-1942)",
    nolock=NOLOCK_READ)
for i, span, note in [("eng:IRISGraphEngine._routed_sql", "2084-2110", "SQL path of a routed shape (module 08's footprint); native retry on SQL failure"),
                      ("eng:IRISGraphEngine._try_native", "2118-2160", "plan, gate, translation cache, Exec.Run"),
                      ("eng:IRISGraphEngine._run_native_plan", "2202-2224", "Exec.Run, ReadPage, Drop"),
                      ("eng:IRISGraphEngine._shadow_compare", "2226-2249", "re-runs the SQL path without LIMIT for an unordered limited read"),
                      ("eng:IRISGraphEngine._names_mapped_label", "2162-2184", "reads the table mapping cache (Graph_KG.table_mappings)")]:
    fps[i] = fp(i, "reader", f"{Q}:{span}", {"tables": ["see notes"], "globals": []}, {"tables": [], "globals": []}, "none", notes=note)
fps["env:IVG_NATIVE_CYPHER"] = fp("env:IVG_NATIVE_CYPHER", "configuration", "iris_vector_graph/engine.py:302-306", {"tables": [], "globals": []}, {"tables": [], "globals": []}, "none")
fps["env:IVG_CYPHER_SHADOW"] = fp("env:IVG_CYPHER_SHADOW", "configuration", f"{Q}:2112-2116", {"tables": [], "globals": []}, {"tables": [], "globals": []}, "none")
fps["global:^IVG.CypherGen(\"mode\")"] = fp("global:^IVG.CypherGen(\"mode\")", "configuration (operator write)", f"{G}:41-44; docs/ADMIN_GUIDE.md:774-779",
    {"tables": [], "globals": []}, {"tables": [], "globals": ["^IVG.CypherGen(\"mode\") by a plain Set (any text)"]}, "none", notes="unvalidated (F-0903)")
fps["lifecycle:deploy-DropAll"] = fp("lifecycle:deploy-DropAll", "writer", "iris_vector_graph/schema.py:2934-2941", {"tables": [], "globals": []}, {"tables": [], "globals": ["as Gen.DropAll"]}, "none", notes="only when the deploy installed classes; a failure is logged at debug and ignored (NAT-T5.24)")
fps["job:Graph.KG.Cypher.Gen.Build[job]"] = dict(fps["cls:Graph.KG.Cypher.Gen.Build"], id="job:Graph.KG.Cypher.Gen.Build[job]", source=f"{G}:92-99 -> :163-222", notes="background JOB started by For in job mode, one attempt (:95-98)")
fps["job:Graph.KG.Cypher.Exec.Part[worker]"] = dict(fps["cls:Graph.KG.Cypher.Exec.Part"], id="job:Graph.KG.Cypher.Exec.Part[worker]", source=f"{E}:447-511 -> :540-554")
for i, span, note in [("gate:engine._native_privileges", "559-586", "SELECT TOP 1 1 FROM Graph_KG.<t> WHERE 1 = 0 on four tables (existence-only), cached per engine"),
                      ("gate:engine._native_executor_current", "588-611", "Native call Exec.PlanVersion, cached per engine"),
                      ("gate:engine._adjacency_indexed", "703-724", "GraphSchema.adjacency_index_kind on rdf_edges only (F-0906), cached per engine"),
                      ("gate:engine._iris_obj", "1894-1942", "opens a dedicated Native API connection when the login is known (from_connect)")]:
    fps[i] = fp(i, "reader (cited gate fact, not owned)", f"iris_vector_graph/engine.py:{span}", {"tables": ["%Dictionary / Graph_KG tables (see notes)"], "globals": []}, {"tables": [], "globals": []}, "none", notes=note)

# journal validations from the live footprint part
jv_rows = []
F = L.get("footprint") or {}
def jv(part, declared, entry_ids, note):
    d = F.get(part)
    if not d:
        return
    observed = sorted({x for v in (d.get("footprint") or {}).values() for x in v})
    undeclared = sorted(set(observed) - set(declared))
    outside = d.get("outside_txn") or []
    rec = {"log": f"$RUN_DIR/breadth-b/live/09-footprint.json#{part}", "run_id": "b-09-footprint", "declared_stores": declared,
           "observed_stores": observed, "match": not undeclared and set(observed) <= set(declared), "undeclared": undeclared,
           "records": d.get("records"), "outside_txn": len(outside), "transaction_units": sorted({t["kind"] for t in d.get("txns") or []}),
           "pids": sorted((d.get("footprint") or {}).keys()), "reader_pid": d.get("reader_pid"), "notes": note}
    jv_rows.append((entry_ids, rec))
    for e in entry_ids:
        if e in fps and fps[e]["journal_validation"] is None:
            fps[e]["journal_validation"] = rec
jv("read_off", [], ["cls:Graph.KG.Cypher.Exec.Run", "eng:IRISGraphEngine.execute_cypher[native]", "cls:Graph.KG.Cypher.Exec.ReadPage", "cls:Graph.KG.Cypher.Exec.Drop", "cls:Graph.KG.Cypher.Props.Begin", "cls:Graph.KG.Cypher.Props.Get"],
   "off mode: an interpreted native read writes nothing persistent in AUDITB (process-private globals are not journaled)")
jv("read_job_new_shape", ["global:^IVG.CypherCompiled", "global:^oddDEP"], ["cls:Graph.KG.Cypher.Gen.For", "job:Graph.KG.Cypher.Gen.Build[job]"],
   "job mode, new shape: the reader writes the pending entry and its lines; the background job (another pid) writes elements 1 and 4; class compilation writes system globals only (filtered); all outside a transaction")
jv("read_job_compiled", [], ["cls:Graph.KG.Cypher.Exec.Run"], "job mode, an ok entry: the compiled read writes nothing persistent")
jv("read_sync_new_shape", ["global:^IVG.CypherCompiled", "global:^oddDEP"], ["cls:Graph.KG.Cypher.Gen.Build"], "sync mode: entry, lines and Build's update all in the reader's pid, outside a transaction")
jv("mode_set", [], ["cls:Graph.KG.Cypher.Gen.Mode"], "Gen.Mode writes only the process-private mode")
jv("exec_run_plumbing", [], ["cls:Graph.KG.Cypher.Exec.Run"], "a plumbing plan (range) writes only ^||IVG.CypherOut")
jv("gen_entries_read", [], ["cls:Graph.KG.Cypher.Gen.Entries"], "Entries reads only")
jv("read_parallel", [], ["cls:Graph.KG.Cypher.Exec.Part", "job:Graph.KG.Cypher.Exec.Part[worker]"], "workers write ^IRIS.Temp.IVG.Cypher (IRISTEMP, not journaled): nothing persistent in AUDITB")
jv("dropall", ["global:^IVG.CypherCompiled", "global:^oddDEP"], ["cls:Graph.KG.Cypher.Gen.DropAll", "lifecycle:deploy-DropAll"], "DropAll kills the entries (and deletes IVGC classes: system globals, filtered); outside a transaction")

fp_list = []
for e in INV["entry_points"]:
    rec = fps.get(e["id"]) or fp(e["id"], "unclassified", f"{e['path']}:{e['start']}-{e['end']}", {"tables": [], "globals": []}, {"tables": [], "globals": []}, "see source")
    rec = dict(rec)
    rec["inventory_hint"] = {k: v for k, v in (e.get("hint") or {}).items() if v}
    fp_list.append(rec)
validated = [r for r in fp_list if r["journal_validation"]]
mism = [r["id"] for r in validated if not r["journal_validation"]["match"]]
footprints = {"module": "09", "pin": "3eaa79cf", "inventory": "experiment/playbook-completion/models/breadth-b/inventory/09.json",
              "oracle": "experiment/playbook-completion/traces/journal.py via live/breadth-b/blive.capture (AUDITB database records; transaction markers by pid)",
              "summary": {"entry_points": len(fp_list), "journal_validated_entry_points": len(validated),
                          "journal_validation_runs": len(jv_rows), "mismatches": mism,
                          "persistent_writers": sorted(r["id"] for r in fp_list if "writer" in r["role"] and "process-private" not in r["role"])},
              "entry_points": fp_list}
(COMP / "footprints/09.json").write_text(json.dumps(footprints, indent=1) + "\n")
print("footprints:", footprints["summary"]["entry_points"], "validated", len(validated), "mismatches", mism)

# ------------------------------------------------------------------------------------------------ findings audit
def ev(kind, ref):
    return {"kind": kind, "ref": ref}


def mcev(*ids):
    return [ev("mc", i) for i in ids if mc(i)]


def lv(i):
    return [ev("live", i)] if reg(i) else []


f1 = L.get("f0901") or {}
f2 = L.get("f0902") or {}
f3 = L.get("f0903") or {}
f4 = L.get("f0904") or {}
f5 = L.get("f0905") or {}
f6 = L.get("f0906") or {}
f7 = L.get("f0907") or {}
f9 = L.get("f0909") or {}
pr = L.get("probe") or {}

wrong_attempt = next((a for a in f1.get("attempts", []) if a.get("wrong_answer")), None)
F0901_live = bool(wrong_attempt)
col = f1.get("collision") or {}


def f0901_observed():
    s = []
    if col:
        s.append(f"Live (b-09-f0901-collision): a birthday search in IRIS over label names of one length found two labels "
                 f"{col.get('label_1')} / {col.get('label_2')} whose plan shapes share $ZCRC(shape,7) = {col.get('crc')} after "
                 f"{col.get('tries')} candidates ({f1.get('search_seconds')} s); hashes of the separately compiled shapes: {f1.get('hash_of')}.")
    if wrong_attempt:
        s.append(f"In job mode ({wrong_attempt.get('variant') or 'one process'}) a read of the {col.get('label_2')} shape (its build job compiling) then a read of the {col.get('label_1')} shape "
                 f"left one entry, status {[e.get('status') for e in (wrong_attempt.get('state') or {}).get('entries', {}).values()]}; the next "
                 f"{col.get('label_1')} read answered {wrong_attempt['reread_l1'].get('rows')} where the SQL path answers "
                 f"{f1.get('sql_answers', {}).get(col.get('label_1'), {}).get('rows')}; a shadow-mode engine raised "
                 f"{(wrong_attempt.get('shadow_l1') or {}).get('exc')}; another process's engine answered "
                 f"{(wrong_attempt.get('other_process_l1') or {}).get('rows')}: the {col.get('label_1')} entry runs the class compiled from the {col.get('label_2')} shape's lines (it counts {col.get('label_2')} nodes), in every process.")
    elif f1:
        s.append(f"Live attempts did not produce the wrong answer: {[{k: a.get(k) for k in ('delay', 'wrong_answer')} for a in f1.get('attempts', [])]}")
    s.append("Model: m09-planc-as-built-collide-I3 (a read mid-walk runs the rebuilt class of the other shape), -binding (the entry of "
             "one shape marked ok for the class compiled from the other), -progress (two colliding shapes never both run compiled); "
             "reviewed per-shape names pass (m09-planc-reviewed); control m09-planc-control-shared-name caught.")
    return " ".join(s)


findings = []
findings.append({
    "id": "F-0901", "module": "09", "title": "Two plan shapes with one 32-bit checksum share one compiled class",
    "intended": "ADR-0014 (docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md:19): 'A compiled class answers exactly as the interpreter does'; NAT-I3 (a read never runs code written for another plan shape); NAT-T5.16.",
    "observed": f0901_observed(),
    "disposition": "reproduced-live" if F0901_live else "reproduced-model",
    "outcome": "product-defect",
    "evidence": lv("b-09-f0901-collision") + mcev("m09-planc-as-built-collide-I3", "m09-planc-as-built-collide-binding", "m09-planc-as-built-collide-progress", "m09-planc-reviewed", "m09-planc-control-shared-name")
                + [ev("inspected", f"{G}:69"), ev("inspected", f"{G}:71-80"), ev("inspected", f"{G}:186-207"), ev("inspected", f"{E}:158"), ev("inspected", f"{E}:199"), ev("inspected", f"{E}:258")],
    "gates": ["3.3-model-check", "3.5-handlers", "3.6-keys", "3.4-statements"],
    "severity": "S2", "confidence": "high",
    "remedy": "Name the class by a digest wide enough to rule out collisions (the SHA-256 Digest already computes) or a counter, keep the shape check, and have Build verify under its lock that the entry still holds the shape it compiled before marking it ok.",
    "notes": "Labels, relationship types and property keys are caller-chosen, so a collision is constructible on demand (birthday search over ~10^5 names in seconds), not only the accident P-0901's odds describe; one caller's reads can thereby change the answers of another caller's queries of a colliding shape in the same namespace until a deploy, a DropAll or a stamp change.",
})
findings.append({
    "id": "F-0902", "module": "09", "title": "The interpreter tells relationships apart by a 32-bit checksum",
    "intended": "NAT-B1.11 (two different relationships in one match are never taken as the same one); ADR-0014:19 (compiled = interpreted); spec 253 FR-002 (same answer as the SQL path).",
    "observed": (f"Live (b-09-f0902-collision): relationships {f2.get('collision', {}).get('x1')}-[:B09T]->b09_hub and {f2.get('collision', {}).get('x2')}-[:B09T]->b09_hub share "
                 f"$ZCRC($LB(src,p,dst,\"\"),7) = {f2.get('collision', {}).get('crc')} (found after {f2.get('collision', {}).get('tries')} candidates). "
                 f"MATCH (a:B09P)-[:B09T]->(h:B09H)<-[:B09T]-(c:B09P) RETURN count(*): SQL path {f2.get('sql', {}).get('count', {}).get('rows')}, interpreter (off mode) "
                 f"{f2.get('interpreted', {}).get('count', {}).get('rows')}, compiled walk (sync) {f2.get('compiled', {}).get('count', {}).get('rows')}; a control pair without a collision: "
                 f"SQL {f2.get('sql', {}).get('control', {}).get('rows')}, interpreter {f2.get('interpreted', {}).get('control', {}).get('rows')}; shadow mode on the interpreted read: "
                 f"{f2.get('shadow_interpreted', {}).get('exc') or f2.get('shadow_interpreted', {}).get('rows')}. Model m09-used-as-built; reviewed exact identity passes.") if f2.get("collision") else "Model m09-used-as-built (a CRC collision drops valid matches); reviewed exact identity passes (m09-used-reviewed).",
    "disposition": "reproduced-live" if (f2.get("interpreted", {}).get("count", {}).get("rows") not in (None, f2.get("sql", {}).get("count", {}).get("rows"))) else "reproduced-model",
    "outcome": "product-defect",
    "evidence": lv("b-09-f0902-collision") + mcev("m09-used-as-built", "m09-used-reviewed", "m09-used-control-type-only") + [ev("inspected", f"{E}:1236-1250"), ev("inspected", f"{G}:410-433")],
    "gates": ["3.3-model-check", "3.5-handlers"],
    "severity": "S2", "confidence": "high",
    "remedy": "Keep used relationships as exact subscripts (a local array keyed by $LB(src, p, dst, ekey)) instead of checksums in a string.",
    "notes": "Node ids are caller-chosen, so the collision is constructible; the interpreter is also the shadow reference (off mode), so shadow runs then blame the compiled path's correct answer.",
})
# F-0903
nsv = (f3.get("by_namespace_value") or {})
def _st(v):
    d = nsv.get(v) or {}
    ents = (d.get("entries_right_after_read") or {}).get("entries") or {}
    return {"effective": d.get("effective"), "entry_status": [e.get("status") for e in ents.values()],
            "classes": (d.get("entries_right_after_read") or {}).get("class_definitions"), "ms": (d.get("read") or {}).get("ms")}
f0903_obs = {v: _st(v) for v in nsv}
OFF = f0903_obs.get("OFF") or {}
f0903_live = bool(OFF.get("entry_status")) and all(s == "ok" for s in OFF["entry_status"]) and bool(OFF.get("classes"))
findings.append({
    "id": "F-0903", "module": "09", "title": "The namespace compile mode is not checked: any value but job or off acts as sync",
    "intended": "NAT-X12 (a namespace mode other than job, sync or off is refused, never taken as sync); docs/ADMIN_GUIDE.md:774-779 tells operators to Set ^IVG.CypherGen(\"mode\") = \"off\" under change control.",
    "observed": f"Live (b-09-f0903-mode): namespace value -> (Effective, entry status right after the read returned, IVGC classes, read ms): {json.dumps(f0903_obs)}. Model m09-mode-as-built (violation of NAT-X12); reviewed (unknown taken as off) passes; control caught.",
    "disposition": "reproduced-live" if f0903_live else ("reproduced-model" if mc("m09-mode-as-built") else "confirmed-source"),
    "outcome": "product-defect",
    "evidence": lv("b-09-f0903-mode") + mcev("m09-mode-as-built", "m09-mode-reviewed", "m09-mode-control-unknown-job") + [ev("inspected", f"{G}:41-44"), ev("inspected", f"{G}:61-105")],
    "gates": ["3.3-model-check", "5c-refusals", "3.5-decoders"],
    "severity": "S3", "confidence": "high",
    "remedy": "Effective() (or For) treats an unknown namespace value as off and logs it once; a test that sets \"OFF\" and asserts no entry is written.",
    "notes": "The operator who meant to stop run-time compilation gets synchronous compilation in every reader's process (F-0904's exposure on top).",
})
# F-0904
fb = f4.get("read_with_failed_build") or {}
probes = f4.get("new_sql_in_same_process") or []
p0903 = bool(probes) and all("rows" in p for p in probes)
f4_ents = list(((f4.get("entries") or {}).get("entries") or {}).values())
findings.append({
    "id": "F-0904", "module": "09", "title": "In sync mode a failed build runs in the reader's own process",
    "intended": "specs/257-compiled-native-plans/spec.md:60-63 (User Story 3: compilation never costs a caller); NAT-B5.3 (a failed build never stops the reader's own process from running SQL).",
    "observed": (f"Live (b-09-f0904-sync-failed-build, Community 2026.1): with the product's test hook ^IVG.CypherGen(\"breaktest\") a sync-mode read compiled a broken class in the reader's process "
                 f"(entry status {[e.get('status')[:80] for e in f4_ents]}); the read answered {fb.get('rows')} ({fb.get('ms')} ms). The same process then prepared "
                 f"{len(probes)} statement texts it had never run: {['ok' if 'rows' in p else p.get('error') for p in probes]}; the SQL path in that process answered "
                 f"{(f4.get('sql_path_read_same_process') or {}).get('rows')}. Premise P-0903 (observed by the product on 2026.3) {'did not reproduce' if p0903 else 'reproduced'} here.") if f4 else "Source: Gen.cls:101 builds in the caller for sync; Build compiles there (:205).",
    "disposition": ("not-reproduced" if p0903 else "reproduced-live") if f4 else "confirmed-source",
    "outcome": "intent-undecided" if p0903 else "product-defect",
    "evidence": lv("b-09-f0904-sync-failed-build") + [ev("inspected", f"{G}:101"), ev("inspected", f"{G}:204-215"), ev("tested", "tests/e2e/test_257_compiled_plans_e2e.py::test_the_broken_builds_leave_the_session_process_able_to_compile_sql"), ev("assumed", "P-0903")],
    "gates": ["3.2-coverage", "3.7-failure-controls"],
    "severity": "S3", "confidence": "medium",
    "remedy": "Build in a job in every mode and let sync wait for the job, or document sync as a test-only mode with this hazard.",
    "notes": "The mechanism (sync compiles in the reader's process, costing it the compile time) is source-confirmed; the harsher effect (the process can no longer prepare SQL) is an IRIS 2026.3 premise that Community 2026.1 did not show. Whether sync is a supported production mode is not settled: ADMIN_GUIDE offers it (docs/ADMIN_GUIDE.md:746-752), spec 257 US3 promises compilation never costs a caller.",
})
# F-0905
fa = next((a for a in f5.get("attempts", []) if a.get("broken_entries")), None)
findings.append({
    "id": "F-0905", "module": "09", "title": "A deploy's drop does not wait for builds already running",
    "intended": "ADR-0014 and NAT-I5 (after a deploy, no compiled plan made before it is left); NAT-T5.22.",
    "observed": (f"Live (b-09-f0905-dropall-race): a job-mode read started a build; DropAll {fa.get('delay')} s later; after the job finished the namespace held entries "
                 f"{json.dumps((fa.get('after') or {}).get('entries'))} (elements defined '{'/'.join(e.get('elements_defined', '') for e in ((fa.get('after') or {}).get('entries') or {}).values())}') and classes "
                 f"{(fa.get('after') or {}).get('class_definitions')}; Gen.Entries(): {fa.get('entries_call_error') or fa.get('entries_call')}; two rereads answered {[(fa.get('reread_1') or {}).get('rows'), (fa.get('reread_2') or {}).get('rows')]} and left "
                 f"{json.dumps((fa.get('after_rereads') or {}).get('entries'))}.") if fa else
                (f"Live attempts did not hit the window: {[{k: a.get(k) for k in ('delay', 'broken_entries')} for a in f5.get('attempts', [])]}; model m09-planc-as-built-drop-* reproduce it." if f5 else "Model m09-planc-as-built-drop-shape / -I5 / -progress."),
    "disposition": "reproduced-live" if fa else "reproduced-model",
    "outcome": "product-defect",
    "evidence": lv("b-09-f0905-dropall-race") + mcev("m09-planc-as-built-drop-shape", "m09-planc-as-built-drop-I5", "m09-planc-as-built-drop-progress", "m09-planc-reviewed", "m09-planc-control-drop-nolock") + [ev("inspected", f"{G}:225-230"), ev("inspected", f"{G}:166"), ev("inspected", f"{G}:207"), ev("inspected", f"{G}:71"), ev("assumed", "P-0907")],
    "gates": ["3.5-lockplans", "3.3-model-check", "3.7-lock-log"],
    "severity": "S3", "confidence": "high",
    "remedy": "DropAll takes each entry's lock (or a namespace lock Build also takes); Build re-checks that its entry still exists before writing; For and Entries read with $ListGet.",
    "notes": "Answers stay right (the shape runs interpreted); the defect costs speed until the next DropAll and breaks the operator's Entries() listing.",
})
findings.append({
    "id": "F-0906", "module": "09", "title": "The native gate checks the edge index but not the label index",
    "intended": "NAT-I1 (labels are read from the adjacency index only where each label write keeps it up to date); CONTEXT.md:88-96 (the index is declared on the edge and label tables).",
    "observed": f"Model m09-gate-as-built: with the edge index declared and the label index not (the state ensure_adjacency_index leaves when it fails between its two declarations, iris_vector_graph/schema.py:863-899), a label write keeps only the row and the open gate answers from ^KG; reviewed gate (both indexes) passes; control caught. Live (b-09-f0906-index-facts, read only): AUDITB has {f6.get('indexes')}; engine._adjacency_indexed = {f6.get('engine_adjacency_indexed')}; the edge-only state was not created live (it needs dropping a product index).",
    "disposition": "reproduced-model",
    "outcome": "product-defect",
    "evidence": mcev("m09-gate-as-built", "m09-gate-reviewed", "m09-gate-control-always-open") + lv("b-09-f0906-index-facts") + [ev("inspected", f"{NP}:528-529"), ev("inspected", "iris_vector_graph/engine.py:703-724"), ev("inspected", "iris_vector_graph/schema.py:863-899")],
    "gates": ["3.3-model-check", "3.4-declared-reads"],
    "severity": "S2", "confidence": "medium",
    "remedy": "The gate (or Graph.KG.Adjacency.Indexed()) also requires idx_labels_adj as a functional index; a unit test with the label index absent.",
    "notes": "Reaching the edge-only state needs a partial index declaration; shadow mode would catch the drift, default mode would not.",
})
# F-0907
def _sh(k):
    d = f7.get(k) or {}
    return {"native": (d.get("native") or {}).get("rows"), "sql": (d.get("sql") or {}).get("rows"), "shadow": (d.get("shadow") or {}).get("exc") or "no mismatch"}
f7obs = {k: _sh(k) for k in ("limit", "nolimit", "control_unique_order")}
f7_live = any(v["shadow"] == "NativeMismatch" for k, v in f7obs.items() if k != "control_unique_order")
findings.append({
    "id": "F-0907", "module": "09", "title": "Shadow mode holds any ordered projection to a fixed row order, ties included",
    "intended": "spec 253 FR-013 and docs/dev/TCK.md: rows in the same order only where the query orders them completely; NAT-T8.4.",
    "observed": f"Live (b-09-f0907-shadow-ties): {json.dumps(f7obs)}.",
    "disposition": "reproduced-live" if f7_live else "not-reproduced",
    "outcome": "product-defect" if f7_live else "product-defect",
    "evidence": lv("b-09-f0907-shadow-ties") + [ev("inspected", f"{NP}:179-194"), ev("inspected", f"{Q}:2232-2238"), ev("inspected", "iris_vector_graph/cypher/native_shadow.py:55-63")],
    "gates": ["3.7-differential"],
    "severity": "S4", "confidence": "high" if f7_live else "medium",
    "remedy": "Compute 'ordered' for projections from whether the ORDER BY keys determine the returned row (or compare tied runs as bags); a unit test with a tied ORDER BY.",
    "notes": "False alarms in shadow runs, not wrong answers." + ("" if f7_live else " Both paths broke the ties the same way on this data, so no false alarm was observed; the code path (ordered = bool(order)) is source-confirmed."),
})
findings.append({
    "id": "F-0908", "module": "09", "title": "The privilege check spec 253 puts in the executor is in the engine only",
    "intended": "specs/253-native-cypher-executor/spec.md:124-127 (FR-011: the executor MUST check SELECT on the graph tables, cached per process and user); decisions.md HD-0901 working answer: authorization at use.",
    "observed": "Source: Graph.KG.Cypher.Exec.Run (iris_src/src/Graph/KG/Cypher/Exec.cls:32-72) checks no privilege; the check is the engine's (iris_vector_graph/engine.py:559-586, gate native_plan.py:532-533), cached per engine. docs/ADMIN_GUIDE.md:565-575 states the database resource is the boundary. A live demonstration needs a second IRIS user without SELECT on the tables but with %Native_ClassExecution: blocked (creating users or roles changes the container's security configuration, which the audit may not do).",
    "disposition": "confirmed-source",
    "outcome": "intent-undecided",
    "live": "blocked-access: needs a second IRIS user/role without SELECT but with %Native_ClassExecution (container security configuration, which the audit may not change); not created",
    "evidence": [ev("inspected", f"{E}:32-72"), ev("inspected", "iris_vector_graph/engine.py:559-586"), ev("inspected", f"{NP}:532-533"), ev("inspected", "docs/ADMIN_GUIDE.md:565-575"), ev("inspected", "experiment/playbook-completion/intent/HD-0901.md"), ev("open", "HD-0901")],
    "gates": ["3.5-handlers", "3.8-findings-disposed"],
    "severity": "S3", "confidence": "high",
    "remedy": "Amend FR-011 to the shipped design (engine-side check, database resource as the boundary), or add the check to Run.",
    "notes": "The code-vs-spec gap is confirmed in source. Which contract holds is undecided: FR-011 (decided 2026-10-20) puts the check in the executor; the later maintainer statement R280 (commit d3a86fcd, 2026-11-04) and docs/ADMIN_GUIDE.md:565-570 make the database resource the native boundary (intent/HD-0901.md: treat FR-011's executor check as an unimplemented spec requirement whose amendment is the maintainer's call).",
})
findings.append({
    "id": "F-0909", "module": "09", "title": "Spec 253's 'same process' reason for seeing one's own writes is not what the code does",
    "intended": "specs/253-native-cypher-executor/spec.md:91-92 (a native read inside an open transaction sees its own writes because it runs in the same process); NAT-B4.1, NAT-T4.7.",
    "observed": (f"Live (b-09-f0909-txn-visibility): an engine from from_connect ran SQL in pid {f9.get('sql_pid')} and native reads in pid {f9.get('native_pid')} "
                 f"(dedicated: {f9.get('dedicated_native_connection')}); with START TRANSACTION and an uncommitted node+edge in the SQL process (tlevel {f9.get('tlevel_sql_process')}), its native read answered "
                 f"{(f9.get('native_in_txn') or {}).get('rows')} (native: {f9.get('native_in_txn_was_native')}); another engine's process (pid {f9.get('other_process_pid')}) also answered "
                 f"{(f9.get('other_process_native') or {}).get('rows')} natively; after ROLLBACK {(f9.get('after_rollback_native') or {}).get('rows')}. The read sees the caller's writes by reading uncommitted data from another process (P-0002), as it sees any writer's.") if f9 else "Source: engine._iris_obj opens a dedicated native connection when the login is known (engine.py:1894-1942); _run_native_plan uses it (query.py:2202-2209).",
    "disposition": "reproduced-live" if f9.get("dedicated_native_connection") else "confirmed-source",
    "outcome": "product-defect",
    "evidence": lv("b-09-f0909-txn-visibility") + [ev("inspected", "iris_vector_graph/engine.py:1894-1942"), ev("inspected", f"{Q}:2202-2209"), ev("assumed", "P-0002")],
    "gates": ["3.7-e2e", "3.2-coverage"],
    "severity": "S3", "confidence": "high",
    "remedy": "Correct the spec's reason; add an e2e test that writes in an open transaction and reads natively on an engine built with from_connect.",
    "notes": "Behaviour (own writes visible) holds today only through read-uncommitted visibility across processes (HD-0903).",
})
new = []
if wrong_attempt or mc("m09-planc-as-built-collide-binding"):
    new.append({
        "id": "F-C0901", "module": "09", "title": "A build marks whatever entry its hash holds as ok, so one shape's entry can run another shape's class for good",
        "intended": "NAT-T5.16 (a ready entry runs only the class written for its own shape) and NAT-I3; ADR-0014:19.",
        "observed": f0901_observed() if wrong_attempt else "Model m09-planc-as-built-collide-binding: For of shape S2 overwrites the entry while S1's build compiles; S1's build then sets element 1 and status ok on S2's entry.",
        "disposition": "reproduced-live" if wrong_attempt else "reproduced-model",
        "outcome": "product-defect",
        "evidence": lv("b-09-f0901-collision") + mcev("m09-planc-as-built-collide-binding", "m09-planc-reviewed") + [ev("inspected", f"{G}:175-182"), ev("inspected", f"{G}:207")],
        "gates": ["3.5-lockplans", "3.3-model-check"],
        "severity": "S2", "confidence": "high" if wrong_attempt else "medium",
        "remedy": "Under its lock, Build writes the entry only if it still holds the shape (or digest) it compiled; otherwise it deletes the class and leaves the entry.",
        "notes": "Root cause shared with F-0901 (two shapes on one 32-bit name) but a distinct mechanism: F-0901 describes a transient mid-walk race and overwrite churn; here the wrong binding persists across reads and processes until a deploy, a DropAll or a stamp change. The R311 digest check (:175-182) compares only the lines it merged, before compiling, and does not prevent it.",
    })

summary = {"original_findings": len(findings), "by_disposition": {}, "by_outcome": {}, "new_findings": len(new), "new_by_outcome": {}}
for f in findings:
    summary["by_disposition"][f["disposition"]] = summary["by_disposition"].get(f["disposition"], 0) + 1
    summary["by_outcome"][f["outcome"]] = summary["by_outcome"].get(f["outcome"], 0) + 1
for f in new:
    summary["new_by_outcome"][f["outcome"]] = summary["new_by_outcome"].get(f["outcome"], 0) + 1
(COMP / "findings/audit/09.json").write_text(json.dumps({"module": "09", "lane": "breadth-b", "pin": "3eaa79cf", "summary": summary,
                                                          "findings": findings, "new_findings": new}, indent=1) + "\n")
print("findings:", summary)

# ------------------------------------------------------------------------------------------------ module gates
mc_ids = sorted(p.stem for p in (COMP / "models/breadth-b/results").glob("m09-*.json"))
mc_res = {i: mc(i) for i in mc_ids}
mc_met = sum(1 for r in mc_res.values() if r and r.get("met"))
by_design = {}
for r in mc_res.values():
    by_design.setdefault(r["design"], {"met": 0, "not_met": 0})
    by_design[r["design"]]["met" if r["met"] else "not_met"] += 1
runs = sorted(p.stem for p in (COMP / "evidence/runs").glob("b-09-*.json"))

so_sites = []
so_path = RUN / "checks" / "storage-order.json"
if so_path.exists():
    for x in json.loads(so_path.read_text()):
        if x["file"] == E:
            so_sites.append({"file": x["file"], "line": x["line"], "sql": x["sql"], "checker_kind": x["kind"],
                             "disposition": "existence-only",
                             "reason": "a cardinality cap, not a prefix of the answer: SELECT TOP 1001 reads the candidates of a named-end walk; the result is used only when it holds at most 1000 rows, i.e. the whole result (Exec.cls:1110-1117 `Quit:tN>1000 0` falls back to the full walk), and the start-node test `Return:tC=pS 0` bails out the same way whichever rows are scanned; no answer depends on scan order"})
        if x["file"] == Q and 2032 <= x["line"] <= 2250:
            so_sites.append({"file": x["file"], "line": x["line"], "sql": x["sql"], "checker_kind": x["kind"], "disposition": "module 09 span", "reason": "none expected"})
    cited = [x for x in json.loads(so_path.read_text()) if x["file"] == "iris_vector_graph/engine.py" and x["line"] == 576]
    for x in cited[:1]:
        so_sites.append({"file": x["file"], "line": x["line"], "sql": x["sql"], "checker_kind": x["kind"], "disposition": "existence-only",
                         "reason": "gate fact cited by module 09 (owned by the engine): SELECT TOP 1 1 ... WHERE 1 = 0 asks only whether the Prepare is allowed (engine.py:559-586)", "owned": False})
q_sites = sorted({x["line"] for x in json.loads(so_path.read_text()) if x["file"] == Q}) if so_path.exists() else []

ENV = [
    ("$ZCRC(string, 7) CRC-32 (equals zlib.crc32, b-09-probe)", "plan entry / class name key; interpreter's used-relationship set; memo and group hash buckets (exact subscripts there)", [f"{G}:69", f"{E}:1243", f"{E}:817", f"{E}:828", f"{E}:1294", f"{E}:1384"]),
    ("JOB command (background process, timeout 0, one attempt)", "job-mode plan builds", [f"{G}:92-99"]),
    ("Run-time class compilation: %SYSTEM.OBJ LoadStream/Compile/Delete/DeletePackage (not transactional; writes class dictionary and routine globals incl. ^oddDEP)", "compiled plans IVGC.P<h>, DropAll, deploy", [f"{G}:184-215", f"{G}:225-230", "iris_vector_graph/schema.py:2934-2941"]),
    ("A class (re)compiled or deleted takes effect at the next call in every process (P-0904)", "a running read meets a rebuilt or deleted class (NAT-T5.26; F-0901 mid-walk)", [f"{E}:199", f"{E}:258"]),
    ("A failed compile in a process may leave it unable to prepare new SQL (P-0903, 2026.3; not seen on 2026.1)", "sync mode builds in the reader", [f"{G}:101", f"{G}:205"]),
    ("LOCK +^G(sub):0 incremental exclusive lock with zero timeout and $TEST; released on process exit", "one build per entry", [f"{G}:166-167", f"{G}:172", f"{G}:180", f"{G}:220"]),
    ("Process-private globals ^|| (not journaled, freed at process exit)", "result rows, walk scratch, property layout cache, process compile mode, memo, counters", [f"{E}:35-36", f"{E}:176", f"{P}:16-21", f"{G}:30-34", f"{E}:817"]),
    ("%SYSTEM.WorkMgr work queues (worker processes with the caller's namespace and roles, WaitForComplete; P-0905)", "parallel native reads", [f"{E}:467-476"]),
    ("^IRIS.Temp globals (IRISTEMP database, not journaled, shared across processes) and $Increment on them", "worker result shares", [f"{E}:451-452", f"{E}:578", f"{E}:1889"]),
    ("$Increment on globals (atomic, not rolled back)", "result tags, share ids, sequence numbers", [f"{E}:35", f"{E}:451", f"{E}:1889"]),
    ("Read-uncommitted visibility across processes for globals and SQL at default isolation (P-0002)", "native reads take no lock and no snapshot; see a caller's and other writers' uncommitted data (b-09-f0909)", [f"{E}:999-1094", f"{Q}:2202-2224"]),
    ("Dynamic SQL from ObjectScript (%SQL.Statement %ExecDirect, %Prepare, %SQLCODE) inside a native run", "anchors, named ends, property fallback", [f"{E}:866-869", f"{E}:897-899", f"{E}:1109", f"{P}:64-70", f"{P}:112-118"]),
    ("Class dictionary SQL (%Dictionary.CompiledStorage/CompiledStorageIndex/CompiledIndex/CompiledStorageDataValue/CompiledClass.TimeChanged/CompiledProperty) readable by the role", "property reader layout and stamp; val_key presence", [f"{P}:29-41", f"{P}:106-110", f"{E}:888", f"{E}:1103"]),
    ("Direct global access to a SQL table's storage (rdf_props data/index globals, $List slot) and name indirection @", "property reads without SQL; generated code reads storage globals by name", [f"{P}:56-60", f"{E}:131-132"]),
    ("TimeChanged of a class moves on every recompile including DDL (P-0906)", "plan stamp invalidation", [f"{P}:106-110", f"{G}:136-139"]),
    ("$LIST semantics: SET $LIST pads undefined elements; $LIST of an undefined element raises <NULL VALUE>; $ListGet does not (P-0907)", "plan entries", [f"{G}:71", f"{G}:207", f"{G}:210", f"{G}:248-251"]),
    ("Functional indexes that maintain ^KG from rdf_edges/rdf_labels row writes in the row's transaction (P-0902)", "adjacency index the native path reads", ["iris_vector_graph/engine.py:703-724", "iris_vector_graph/schema.py:769-782"]),
    ("SQL privilege refusal at Prepare (SQLCODE -99) as the privilege probe", "native gate", ["iris_vector_graph/engine.py:559-586"]),
    ("objectgenerator methods (compile-time constants)", "BuiltAt stamps", [f"{E}:25-29", f"{G}:53-57"]),
    ("$ClassMethod dynamic dispatch", "calling the compiled Walk1", [f"{E}:199", f"{E}:258"]),
    ("%SYS.System.WriteToConsoleLog (messages.log)", "build failures, refusals, compile-off notices", [f"{G}:177", f"{G}:212", f"{E}:165"]),
    ("$System.Encryption.SHAHash(256) and Base64Encode", "digest of a plan's lines (R311)", [f"{G}:147-157"]),
    ("%Library.DynamicObject/DynamicArray JSON (%FromJSON/%ToJSON), long strings up to 3.6 MB", "plans in, rows out, paging (FR-015)", [f"{E}:34", f"{E}:76-87", f"{E}:1902-1910"]),
    ("$Horolog / $ZTimestamp / $ZDateTime", "pending-entry age (120 s), build stamps", [f"{G}:141-144", f"{G}:55"]),
    ("String collation and the sorts-after operator ]] for sort keys and key ranges", "ORDER BY trimming, scan chunks", [f"{E}:250", "iris_src/src/Graph/KG/Cypher/SortKey.cls:9-151"]),
    ("%Stream.GlobalCharacter", "class source stream for LoadStream", [f"{G}:184-203"]),
    ("Embedded Python methods ([Language = python]) importing the Python package inside IRIS", "IVG.CypherEngine", ["iris_src/src/IVG/CypherEngine.cls:56-230"]),
    ("Native API over DB-API connections (classMethodValue; a dedicated connection is another server process)", "engine's native link", ["iris_vector_graph/engine.py:1894-1942", f"{Q}:2206-2224"]),
    ("Number of CPUs (Graph.KG.VarLength.CPUs) and Community's connection/core limits", "worker count (at most 8)", [f"{E}:449-450"]),
]
env_features = [{"feature": f, "used_for": u, "source": "; ".join(src)} for f, u, src in ENV]

writesets = [
    {"invariant": "NAT-I3 (a read never runs code written for another plan shape)", "reads": ["^IVG.CypherCompiled(h)", "class IVGC.P<h>"],
     "plans": [{"plan": "cls:Graph.KG.Cypher.Gen.For", "writes": ["entry", "src"], "discharge": "finding F-0901 (shared 32-bit name); reviewed mc m09-planc-reviewed"},
               {"plan": "cls:Graph.KG.Cypher.Gen.Build", "writes": ["entry 1/4", "class"], "discharge": "finding F-0901, F-C0901; reviewed mc m09-planc-reviewed"},
               {"plan": "cls:Graph.KG.Cypher.Gen.DropAll", "writes": ["entry", "class"], "discharge": "mc m09-planc-reviewed (a deleted class fails the run over to SQL, NAT-T5.26)"},
               {"plan": "lifecycle:deploy-DropAll", "writes": ["entry", "class"], "discharge": "as DropAll"}]},
    {"invariant": "NAT-T5.16 (an ok entry runs only the class compiled from its own shape)", "reads": ["^IVG.CypherCompiled(h)", "class IVGC.P<h>"],
     "plans": [{"plan": "cls:Graph.KG.Cypher.Gen.Build", "writes": ["entry 1/4"], "discharge": "finding F-C0901 (as built); mc m09-planc-reviewed (re-check under the lock)"},
               {"plan": "cls:Graph.KG.Cypher.Gen.For", "writes": ["entry"], "discharge": "finding F-0901"}]},
    {"invariant": "NAT-I4 (a compiled plan whose stamp is not the running stamp never runs)", "reads": ["entry stamp", "rdf_props TimeChanged", "Exec/Gen BuiltAt"],
     "plans": [{"plan": "DDL on rdf_props (other modules)", "writes": ["class TimeChanged"], "discharge": "inspected: every For compares the stamp (Gen.cls:71) and every run recomputes it (NAT-T5.6); not model-checked"},
               {"plan": "lifecycle:deploy-DropAll", "writes": ["Exec/Gen BuiltAt"], "discharge": "inspected"}]},
    {"invariant": "NAT-I5 (after a deploy no compiled plan made before it is left) and P-0907 entry shape", "reads": ["entry", "class"],
     "plans": [{"plan": "cls:Graph.KG.Cypher.Gen.DropAll", "writes": ["entry", "class"], "discharge": "finding F-0905 (b-09-f0905-dropall-race; mc m09-planc-as-built-drop-*); reviewed mc m09-planc-reviewed"},
               {"plan": "cls:Graph.KG.Cypher.Gen.Build", "writes": ["entry 1/4", "class"], "discharge": "finding F-0905"}]},
    {"invariant": "NAT-X12 / NAT-B5.2 (compile mode)", "reads": ["^IVG.CypherGen(\"mode\")", "^||IVG.CypherGenMode"],
     "plans": [{"plan": "global:^IVG.CypherGen(\"mode\") (operator Set)", "writes": ["mode"], "discharge": "finding F-0903 (b-09-f0903-mode; mc m09-mode-as-built)"},
               {"plan": "cls:Graph.KG.Cypher.Gen.Mode", "writes": ["^||IVG.CypherGenMode"], "discharge": "guard: Mode validates (Gen.cls:28-39); mc m09-mode-as-built-X11-B52"}]},
    {"invariant": "NAT-I1 (labels read from the adjacency index only where label writes keep it)", "reads": ["^KG(\"label\")", "rdf_labels"],
     "plans": [{"plan": "label writers (module 02/03) with idx_labels_adj absent", "writes": ["rdf_labels rows only"], "discharge": "finding F-0906 (mc m09-gate-as-built)"}]},
    {"invariant": "NAT-I2 (a read's rows and scratch belong to its process and are cleared)", "reads": ["^||IVG.CypherOut", "^||IVG.CypherRun", "^IRIS.Temp.IVG.Cypher(share)"],
     "plans": [{"plan": "cls:Graph.KG.Cypher.Exec.Run / Part", "writes": ["process-private", "IRISTEMP share"], "discharge": "journal (b-09-footprint): no AUDITB write by reads; inspected kills Exec.cls:39, :176, :284, :474, :505, :1916"}]},
]


def g(status, reason, evidence=(), remaining=""):
    return {"status": status, "reason": reason, "evidence": list(evidence), "remaining": remaining}


inv = INV
gates_by_id = {
    "3.1-parent": g("closed", "ontology_index.py --check --only 09: 0 violations (parents, grade, lexical terms)", [f"run:$RUN_DIR/breadth-b/09-ontology-check.log"]),
    "3.1-grade": g("closed", "0 grade violations in NAT statements (ontology_index.py --check --only 09)", [f"run:$RUN_DIR/breadth-b/09-ontology-check.log"]),
    "3.1-terms": g("open", "decisions.md HD-0001 adopts the literal rule; check-literal-scope.py reports 116 NAT statement/term pairs in 68 statements using a term not defined by an ancestor or an earlier sibling (e.g. NAT-I3 'plan shape', NAT-T5.13 'compile mode')", [f"run:$RUN_DIR/breadth-b/09-literal-scope.tsv"], "reparent or add local definitions (ontology lane)"),
    "3.1-cells": g("closed", f"all {inv['counts']['cells']} cells defined (no open cell); every cell command maps to entry points (inventory cells_without_entry_point = 0). Cell correctness is audited separately: 'compiled shape|building|drop all' (NAT-I5) fails as built (F-0905)", ["inspected:experiment/playbook-completion/models/breadth-b/inventory/09.json"]),
    "3.1-coverage": g("open", f"{inv['counts']['entry_points']} entry points derived from source; {len(inv['omissions'])} have no covering statement: IVG.CypherEngine's helpers (Query, Scalar, GetLabels*, GetNodeCount, GetEdgeCount, NodeExists, GetLabelCounts*, InitSchema*, RebuildKG, IsReady; QueryJson/Query/Scalar run writes too, with no read_only) and Props.GetJson/LayoutOK. Background jobs (Gen.Build job, Exec.Part workers), the deploy DropAll and the namespace mode global are inventoried and covered.", ["inspected:experiment/playbook-completion/models/breadth-b/inventory/09.json"], "statements for IVG.CypherEngine's helper methods (incl. that Query runs writes and InitSchema/RebuildKG are lifecycle writers) and the property reader's JSON accessor"),
    "3.1-intent": g("closed", "HD-0901..HD-0904 have working dispositions (decisions.md) and intent-lane recovery files", ["inspected:experiment/playbook-completion/decisions.md", "inspected:experiment/playbook-completion/intent/HD-0901.md", "inspected:experiment/playbook-completion/intent/HD-0902.md", "inspected:experiment/playbook-completion/intent/HD-0903.md", "inspected:experiment/playbook-completion/intent/HD-0904.md"]),
    "3.2-coverage": g("open", f"{len(env_features)} IRIS engine features listed in env_features with source lines; whether each is inside the orchestrator's IRIS 2026.1 contract is not yet decided here. Two are checked live by this lane: $ZCRC(x,7) = CRC-32 (b-09-probe) and cross-process read-uncommitted visibility (b-09-f0909); P-0903 did not reproduce on 2026.1 (b-09-f0904-sync-failed-build)", ["live:b-09-probe", "live:b-09-f0909-txn-visibility"], "map env_features into the IRIS contract (AUDITENV, orchestrator)"),
    "3.3-L1": g("open", "explorer machines state the module's invariants (NAT-I3, T5.16, I5, X12, X11, B5.2, B1.11, I1) over abstract state; no Verus L1", [f"mc:{i}" for i in ("m09-planc-reviewed", "m09-mode-reviewed", "m09-used-reviewed", "m09-gate-reviewed")], "Verus L1 for the plan cache and the native gate"),
    "3.3-L2": g("open", "machine planc is over the real layout (entry $LB elements, src lines, per-entry lock, IVGC class, job builds, DropAll steps; Gen.cls cited per action) but explorer-only; the walk itself (Exec.RunA/Walk/Neighbours) is not modelled beyond the used-relationship set", ["mc:m09-planc-as-built-collide-binding", "mc:m09-planc-as-built-drop-shape"], "L2 of the walk and of answer parity with the SQL path"),
    "3.3-refinement": g("open", "no refinement audit (explorer::refinement::audit) or proof between an L2 and an L1 for module 09", [], "bind planc to an L1 cache contract"),
    "3.3-controls": g("open", f"explorer controls caught (m09-planc-control-shared-name, -drop-nolock, m09-mode-control-unknown-job, m09-used-control-type-only, m09-gate-control-always-open); the gate asks for proof-rejected controls", [f"mc:{i}" for i in mc_ids if "control" in i], "proof-level controls"),
    "3.3-model-check": g("closed", f"{mc_met} of {len(mc_ids)} checks met their expectation, exhaustive within bounds: as-built violations reproduce F-0901, F-C0901, F-0902, F-0903, F-0905, F-0906; reviewed designs pass incl. AG EF progress; controls caught; sharpness witnesses reachable", [f"mc:{i}" for i in mc_ids], "answer parity of the walk with the SQL path is not model-checked (shadow mode and the TCK are its evidence)"),
    "3.3a-writesets": g("failed", "every (invariant, writer plan) pair over the plan cache is listed in invariant_writesets; NAT-I3/T5.16 vs For/Build and NAT-I5 vs DropAll/Build are open by product defects (F-0901, F-C0901, F-0905), NAT-X12 vs the operator mode Set by F-0903", ["live:b-09-f0905-dropall-race", "live:b-09-f0903-mode", "mc:m09-planc-reviewed"], "fixes or decisions for F-0901/F-C0901/F-0905/F-0903"),
    "3.4-statements": g("open", "the module's storage statements (entry Sets/Kill/Merge, class compile, Anchors/NamedEnds/Props SQL) are not proved equal to a model's evaluation", [], ""),
    "3.4-ownership": g("closed", "single write owner: ^IVG.CypherCompiled and package IVGC are written only by Graph.KG.Cypher.Gen (For/Build/DropAll; grep of iris_src and iris_vector_graph at the pin finds no other writer; the deploy calls Gen.DropAll, schema.py:2939); ^IVG.CypherGen is configuration written by operators and tests (documented, docs/ADMIN_GUIDE.md:774-779); journal footprints show no other module's process writing them during module 09 runs", ["live:b-09-footprint", "inspected:iris_vector_graph/schema.py:2934-2941"], "a self-test for an ownership checker (none exists for this global)"),
    "3.4-storage-order": g("closed", f"{len([s for s in so_sites if s.get('owned', True)])} storage-order site(s) in module 09's own files dispositioned (Exec.cls:1101 cardinality cap: existence-only); query.py sites {q_sites} lie outside the native routing span (2032-2250) and are module 08's; engine.py:576 (gate fact, cited) existence-only", ["inspected:$RUN_DIR/checks/storage-order.json"]),
    "3.4-declared-reads": g("failed", "the native path reads ^KG(\"label\") while its gate checks only the edge index (F-0906): a read from a store the gate does not establish as maintained; no read oracle validates the rest", ["mc:m09-gate-as-built"], "gate on both indexes; a read-footprint oracle"),
    "3.5-handlers": g("open", "no handler proofs; Exec.Run's lack of the FR-011 privilege check is recorded (F-0908)", [], ""),
    "3.5-lockplans": g("failed", "lock plan: Build takes Lock +^IVG.CypherCompiled(h):0; For reads and overwrites entries without it; DropAll takes none. Live and model show the plan insufficient: F-0905 (b-09-f0905-dropall-race), F-C0901/F-0901 (m09-planc-as-built-collide-binding)", ["live:b-09-f0905-dropall-race", "mc:m09-planc-as-built-collide-binding", "mc:m09-planc-reviewed"], "DropAll under the entry locks; Build re-check under its lock"),
    "3.5-decoders": g("failed", "status maps: any native exception falls back to SQL with one warning per reason (query.py:2145-2152); NativeMismatch for shadow differences; plan JSON and row JSON decoded by the engine (unit tests b-09-unit). The namespace mode value is decoded unchecked (F-0903, b-09-f0903-mode); shadow's 'ordered' decision mis-classifies tied orders (F-0907, b-09-f0907-shadow-ties)", ["run:b-09-unit", "live:b-09-f0903-mode", "live:b-09-f0907-shadow-ties"], "fix F-0903, F-0907"),
    "3.6-frame": g("open", "frame obligations not stated", [], ""),
    "3.6-row-permutation": g("failed", "native and SQL answers agree as bags (unit tests), but shadow mode compares tied ordered rows positionally and raises on a row permutation the query allows (F-0907)", ["live:b-09-f0907-shadow-ties"], "fix F-0907"),
    "3.6-keys": g("failed", "the plan entry key is a 32-bit CRC of the shape: two shapes share a key (P-0901 confirmed CRC-32; F-0901)", ["live:b-09-probe", "mc:m09-planc-as-built-collide-I3"], "a collision-free key"),
    "3.6-fk": g("failed", "no SQL foreign keys in module 09's state; the entry -> class reference analogue breaks: an entry naming a class with no shape and a class left after DropAll (F-0905)", ["live:b-09-f0905-dropall-race"], ""),
    "3.6-capacity": g("open", "rows are paged (1000 per page, strings under 3.6 MB, Exec.cls:76-87, :1902-1910); workers at most 8 (Exec.cls:449-450); routes and translations at most 256 per engine (NAT-T7.9); compiled classes grow by one per new shape and nothing prunes them (NAT-T5.25) — no capacity bound or test", ["inspected:iris_src/src/Graph/KG/Cypher/Exec.cls:449-450"], "a bound or a measured limit for compiled classes"),
    "3.7-trace-replay": g("open", "journal traces captured for the cache writers (b-09-footprint, b-09-f0905-dropall-race) but not replayed through planc", ["live:b-09-footprint"], "replay the journaled entry writes through the planc machine"),
    "3.7-lock-log": g("open", "LOCK activity is not journaled; no lock log was captured", [], "capture ^$LOCK during a build"),
    "3.7-mutation": g("open", "only model mutants (controls); no mutation testing of the product code", [], ""),
    "3.8-findings-disposed": g("closed", "every original finding F-0901..F-0909 has an audit record with disposition and outcome; one new finding F-C0901", ["inspected:experiment/playbook-completion/findings/audit/09.json"]),
    "5c-refusals": g("failed", "X statements: NAT-X12 fails (F-0903, live); NAT-X11 holds (mc m09-mode-as-built-X11-B52; Gen.cls:28-39); NAT-X9 (plan version) and NAT-X13/X14 (shadow raises) and the planner's declines NAT-X1..X8 are covered by upstream unit tests run here (b-09-unit); NAT-X10 (unknown operator) inspected Exec.cls:66-69", ["live:b-09-f0903-mode", "run:b-09-unit", "mc:m09-mode-as-built-X11-B52"], "fix F-0903"),
    "3.7-explorers": g("closed", f"module 09 explorer checks ran: {mc_met}/{len(mc_ids)} met", [f"mc:{i}" for i in mc_ids[:3]]),
    "3.7-suites": g("closed", "module 09 upstream unit tests (22 files, 419 tests) passed with IRIS unreachable; IRIS-backed e2e (tests/e2e/test_253_*, test_257_*) not run by this lane (their fixture compiles classes)", ["run:b-09-unit"], "IRIS-backed suites in the validation lane"),
    "3.7-e2e": g("closed", "multi-process live checks: a dedicated native connection (separate pid) and a second process reading natively inside an open transaction (b-09-f0909); job builds in another pid (b-09-f0903-mode); worker split (b-09-footprint read_parallel)", ["live:b-09-f0909-txn-visibility", "live:b-09-f0903-mode", "live:b-09-footprint"]),
    "3.3-progress-controls": g("closed", "AG EF progress fails only in the as-built designs that block recompilation (m09-planc-as-built-collide-progress, -drop-progress) and holds in the reviewed design", ["mc:m09-planc-as-built-drop-progress", "mc:m09-planc-reviewed"]),
}
gates = [{"gate": k, **v} for k, v in gates_by_id.items()]
counts = {"entry_points": inv["counts"]["entry_points"], "omissions": len(inv["omissions"]), "cells": inv["counts"]["cells"],
          "cells_without_entry_point": inv["counts"]["cells_without_entry_point"],
          "footprints": len(fp_list), "footprints_journal_validated": len(validated), "footprint_mismatches": len(mism),
          "model_checks": len(mc_ids), "model_checks_met": mc_met, "model_checks_by_design": by_design,
          "findings_original": len(findings), "findings_new": len(new), "storage_order_sites": len(so_sites),
          "env_features": len(env_features), "registered_runs": runs}
module = {"module": "09", "lane": "breadth-b", "pin": "3eaa79cf", "gates": gates, "gates_by_id": gates_by_id,
          "storage_order": so_sites, "invariant_writesets": writesets, "env_features": env_features, "counts": counts,
          "registered_runs": runs}
(COMP / "modules/09.json").write_text(json.dumps(module, indent=1) + "\n")
print("module:", json.dumps(counts))
