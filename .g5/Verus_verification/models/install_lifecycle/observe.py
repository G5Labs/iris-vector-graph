"""Observation half of the install_lifecycle binding (iteration 56, Part B).

Drops and re-creates its own namespaces I56SA, I56SB, I56SC (from %SYS, in the container ivg-cont-20261117-iris only)
and drives the public install lifecycle through the real engine at the pin: first access on fresh, partial and legacy
namespaces; setup's record decision (new / existing / inferred / explicit / refusals), its dry run, the class deploy's
fingerprint skip and redeploy, the vector-width decision (refuse / rewidth / manual), the embedding identity
(adopt / claim / conflict / force / enforce) and quarantine placement. Each case is reduced to a small JSON value that
binding.py compares with the model's prediction; nothing here computes an expected value.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/install_lifecycle/observe.py)
"""
import json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

os.environ.pop("IVG_SCHEMA_PREFIX", None)
os.environ.pop("IVG_FORCE_CLASS_DEPLOY", None)
OK_TAIL = 'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!'


def iris_sys(script, ns="%SYS"):
    return subprocess.run(["docker", "exec", "-i", runtime.NAME, "iris", "session", "IRIS", "-U", ns],
                          input=script + "\nHalt\n", capture_output=True, text=True, timeout=600).stdout


def recreate_namespace(ns):
    out = iris_sys(f'Set ns="{ns}", dir="/usr/irissys/mgr/{ns.lower()}/"\n'
                   'If ##class(Config.Namespaces).Exists(ns) { Set sc=##class(Config.Namespaces).Delete(ns) }\n'
                   'If ##class(Config.Databases).Exists(ns) { Set sc=##class(Config.Databases).Delete(ns) }\n'
                   'If ##class(%File).Exists(dir_"IRIS.DAT") { Set sc=##class(SYS.Database).DeleteDatabase(dir) }\n'
                   'Set ok=##class(%File).CreateDirectoryChain(dir) Set sc=##class(SYS.Database).CreateDatabase(dir) '
                   'If $System.Status.IsOK(sc) { Set pdb("Directory")=dir, sc=##class(Config.Databases).Create(ns,.pdb) } '
                   'If $System.Status.IsOK(sc) { Set pns("Globals")=ns, pns("Routines")=ns, sc=##class(Config.Namespaces).Create(ns,.pns) } '
                   + OK_TAIL)
    assert "RESULT OK" in out, out


def drop_namespace(ns):
    iris_sys(f'Set ns="{ns}", dir="/usr/irissys/mgr/{ns.lower()}/"\n'
             'If ##class(Config.Namespaces).Exists(ns) { Set sc=##class(Config.Namespaces).Delete(ns) }\n'
             'If ##class(Config.Databases).Exists(ns) { Set sc=##class(Config.Databases).Delete(ns) }\n'
             'If ##class(%File).Exists(dir_"IRIS.DAT") { Set sc=##class(SYS.Database).DeleteDatabase(dir) }\n')


def connect(ns):
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=ns, username="_SYSTEM", password="SYS")
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c), fx.docker_container_hostname(runtime.NAME),
                                         fx.docker_container_id(runtime.NAME)):
        c.close(); raise RuntimeError("fixture identity mismatch")
    return c


def kind(exc):
    t = str(exc)
    name = type(exc).__name__
    if "has never been set up for IVG" in t: return "never_set_up"
    if "set up by an earlier IVG release" in t: return "not_upgraded"
    if "setup has not finished here" in t: return "unfinished"
    if "records" in t and "and this engine asks for" in t: return "mismatch"
    if "has no IVG Schema record, and holds IVG tables" in t: return "unrecorded_schemas"
    if "already holds classes IVG did not create" in t: return "package_clash"
    if name == "EmbeddingIdentityConflict":
        if "dimension mismatch" in t or "-wide and the route" in t: return "conflict_width"
        if "recorded model" in t: return "conflict_model"
        if "and the route holds" in t: return "conflict_dtype"
        return "conflict"
    if "has no embedding route" in t: return "no_route"
    if "does not exist in graph" in t: return "no_node"
    if "is not a quarantine reason" in t: return "bad_reason"
    if name == "ValueError": return "value_error"
    return f"other:{name}:{t[:200]}"


def attempt(f):
    try:
        return {"ok": f()}
    except Exception as e:  # noqa: BLE001 - classified
        return {"err": kind(e)}


def engine(conn, dim, prefix=None):
    from iris_vector_graph.engine import IRISGraphEngine
    kw = {"embedding_dimension": dim, "native_cypher": False}
    if prefix is not None:
        kw["schema_prefix"] = prefix
    return IRISGraphEngine(conn, **kw)


def native(conn):
    import iris
    return iris.createIRIS(conn)


def gget(nat, *sub):
    v = nat.get("^IVG.Deploy", *sub)
    return None if v is None or str(v) == "" else str(v)


def scalar(conn, sql, args=()):
    cur = conn.cursor()
    try:
        cur.execute(sql, list(args)); r = cur.fetchone()
        return None if r is None else r[0]
    finally:
        cur.close()


def tables_in(conn, schema):
    return int(scalar(conn, "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ? AND TABLE_TYPE = 'BASE TABLE'", [schema]))


def setup_obs(st):
    return {"how": st.get("schema_recorded"), "schema": st.get("schema"), "tables": len(st.get("tables_created") or []),
            "routines_created": len((st.get("routines") or {}).get("created") or []),
            "compiled": len(st.get("objectscript_compiled") or []) > 0,
            "manual": sorted(t.rsplit(".", 1)[-1] for t in (st.get("needs_manual_migration") or [])) if not st.get("dry_run") else None,
            "widths": ({k: sorted(t.rsplit(".", 1)[-1] for t in v) for k, v in (st.get("embedding_dimension") or {}).items()
                        if k != "configured"} if st.get("dry_run") and isinstance(st.get("embedding_dimension"), dict) else None),
            "other_schemas": sorted((st.get("other_schemas") or {}).keys())}


def registry(conn, table):
    cur = conn.cursor()
    try:
        cur.execute("SELECT model_key, dimension, set_by, kind FROM Graph_KG.embedding_registry WHERE table_name = ? AND graph_id = ''", [table])
        r = cur.fetchone()
        return None if r is None else {"model": r[0] or None, "dim": None if r[1] in (None, "") else int(r[1]), "set_by": r[2], "kind": r[3]}
    finally:
        cur.close()


def colwidth(conn, table):
    from iris_vector_graph.schema import GraphSchema
    cur = conn.cursor()
    try:
        return GraphSchema.get_embedding_dimension(cur, f"Graph_KG.{table}")
    finally:
        cur.close()


def observe():
    from iris_vector_graph.schema_name import resolve_schema_name, validate_schema_name
    from iris_vector_graph._engine.class_deploy import deploy_packaged_classes, plan_packaged_classes, fingerprint
    from iris_vector_graph.embedding_identity import EmbeddingIdentity
    o = {}
    t0 = time.time()
    # ---- names (pure) ----
    for n in ["1abc", "SQLUser", "sqluser", "%X", "", "Graph_KG_x", "IVG_A", "IVGC", "I56_OK", "graph_kg", "GRAPH_KG", "a-b"]:
        o[f"name:{n}"] = attempt(lambda n=n: validate_schema_name(n))
    o["resolve:arg_env"] = attempt(lambda: resolve_schema_name("ARGS", {"IVG_SCHEMA_PREFIX": "ENVS"}))
    o["resolve:env"] = attempt(lambda: resolve_schema_name(None, {"IVG_SCHEMA_PREFIX": "ENVS"}))
    o["resolve:env_empty"] = attempt(lambda: resolve_schema_name(None, {"IVG_SCHEMA_PREFIX": ""}))
    o["resolve:iris_prefix"] = attempt(lambda: resolve_schema_name(None, {"IRIS_SCHEMA_PREFIX": "RAG"}))
    o["resolve:bad_arg"] = attempt(lambda: resolve_schema_name("1x", {}))

    # ---- NS C: first access on fresh, partial, legacy namespaces; package clash ----
    recreate_namespace("I56SC")
    c = connect("I56SC")
    o["C:fresh"] = attempt(lambda: engine(c, 8).get_node_count())
    st = attempt(lambda: engine(c, 8).status().schema)
    o["C:fresh_status_schema"] = st
    c.close()
    iris_sys('Set ^IVG.Deploy("note")=1', ns="I56SC")
    c = connect("I56SC")
    o["C:global_only"] = attempt(lambda: engine(c, 8).get_node_count())
    c.close()
    iris_sys('Set d=##class(%Dictionary.ClassDefinition).%New() Set d.Name="Graph.KG.BenchFormat" Set sc=d.%Save() ' + OK_TAIL, ns="I56SC")
    c = connect("I56SC")
    o["C:legacy_class"] = attempt(lambda: engine(c, 8).get_node_count())
    cur = c.cursor(); cur.execute("CREATE TABLE I56Z.foo (x INT)"); cur.close(); c.commit()
    o["C:clash_dry"] = attempt(lambda: setup_obs(engine(c, 8, "I56Z").initialize_schema(dry_run=True)))
    o["C:clash_run"] = attempt(lambda: setup_obs(engine(c, 8, "I56Z").initialize_schema()))
    o["C:clash_record"] = gget(native(c), "schema")
    o["C:clash_tables_I56Z"] = tables_in(c, "I56Z")
    c.close()

    # ---- NS A: setup lifecycle, deploy, widths, identity, quarantine ----
    recreate_namespace("I56SA")
    c = connect("I56SA"); nat = native(c)
    e8 = engine(c, 8)
    o["A:fresh"] = attempt(lambda: e8.get_node_count())
    o["A:dry1"] = attempt(lambda: setup_obs(e8.initialize_schema(dry_run=True)))
    o["A:dry1_record"] = gget(nat, "schema")
    o["A:dry1_tables"] = tables_in(c, "Graph_KG")
    o["A:dry1_fingerprint"] = gget(nat, "fingerprint") is not None
    o["A:still_refused_after_dry"] = attempt(lambda: e8.get_node_count())
    s1 = time.time()
    o["A:setup1"] = attempt(lambda: setup_obs(e8.initialize_schema()))
    o["A:setup1_s"] = round(time.time() - s1, 1)
    o["A:setup1_record"] = gget(nat, "schema")
    o["A:setup1_tables"] = tables_in(c, "Graph_KG")
    o["A:after_setup_call"] = attempt(lambda: e8.get_node_count())
    o["A:setup2"] = attempt(lambda: setup_obs(e8.initialize_schema()))
    o["A:dry2"] = attempt(lambda: setup_obs(e8.initialize_schema(dry_run=True)))
    # mismatch
    o["A:alt_call"] = attempt(lambda: engine(c, 8, "I56ALT").get_node_count())
    o["A:alt_setup"] = attempt(lambda: setup_obs(engine(c, 8, "I56ALT").initialize_schema()))
    o["A:alt_dry"] = attempt(lambda: setup_obs(engine(c, 8, "I56ALT").initialize_schema(dry_run=True)))
    o["A:alt_deploy"] = attempt(lambda: deploy_packaged_classes(c, schema="I56ALT") and "deployed")
    o["A:alt_status_schema"] = attempt(lambda: engine(c, 8, "I56ALT").status().schema)
    o["A:alt_record_after"] = gget(nat, "schema")
    o["A:lower_call"] = attempt(lambda: engine(c, 8, "graph_kg").get_node_count())
    # fingerprint: unchanged -> skip; altered marker -> redeploy; a class removed -> redeploy
    o["A:plan_unchanged"] = attempt(lambda: plan_packaged_classes(nat).unchanged)
    nat.set("x", "^IVG.Deploy", "fingerprint")
    o["A:plan_fp_altered"] = attempt(lambda: plan_packaged_classes(nat).unchanged)
    o["A:setup_fp_altered"] = attempt(lambda: setup_obs(e8.initialize_schema()))
    o["A:fp_restored"] = gget(nat, "fingerprint") not in (None, "x")
    nat.classMethodValue("%SYSTEM.OBJ", "Delete", "IVG.Percentile", "-d")
    o["A:plan_class_missing"] = attempt(lambda: plan_packaged_classes(nat).unchanged)
    o["A:setup_class_missing"] = attempt(lambda: setup_obs(e8.initialize_schema()))
    from iris_vector_graph._engine.class_deploy import class_exists
    o["A:class_back"] = class_exists(nat, "IVG.Percentile")
    # record killed after a complete setup (marker present): first access, then setup
    nat.kill("^IVG.Deploy", "schema")
    o["A:norecord_marker_call"] = attempt(lambda: engine(c, 8).get_node_count())
    o["A:norecord_dry"] = attempt(lambda: setup_obs(engine(c, 8).initialize_schema(dry_run=True)))
    o["A:norecord_setup"] = attempt(lambda: setup_obs(engine(c, 8).initialize_schema()))
    o["A:norecord_record_after"] = gget(nat, "schema")
    # record present, this release's marker function dropped
    cur = c.cursor(); cur.execute("DROP FUNCTION Graph_KG.CY_CMP"); cur.close(); c.commit()
    o["A:record_nomarker_call"] = attempt(lambda: engine(c, 8).get_node_count())
    # record and marker both gone: IVG's classes and globals remain
    nat.kill("^IVG.Deploy", "schema")
    o["A:norecord_nomarker_call"] = attempt(lambda: engine(c, 8).get_node_count())
    o["A:repair_setup"] = attempt(lambda: setup_obs(engine(c, 8).initialize_schema()))
    o["A:repair_record"] = gget(nat, "schema")
    o["A:repair_call"] = attempt(lambda: engine(c, 8).get_node_count())

    # widths (all vector tables empty, declared 8)
    o["W:col_before"] = colwidth(c, "kg_NodeEmbeddings")
    o["W:reg_before"] = registry(c, "kg_NodeEmbeddings")
    e16 = engine(c, 16)
    o["W:e16_dry"] = attempt(lambda: setup_obs(e16.initialize_schema(dry_run=True)))
    o["W:e16_setup"] = attempt(lambda: setup_obs(e16.initialize_schema()))
    o["W:col_after_refusal"] = colwidth(c, "kg_NodeEmbeddings")
    o["W:e16_dry_rewidth"] = attempt(lambda: setup_obs(e16.initialize_schema(dry_run=True, rewidth=True)))
    o["W:e16_rewidth"] = attempt(lambda: setup_obs(e16.initialize_schema(rewidth=True)))
    o["W:col_after_rewidth"] = colwidth(c, "kg_NodeEmbeddings")
    o["W:reg_after_rewidth"] = registry(c, "kg_NodeEmbeddings")
    e16.create_node("n1", labels=["T"])
    o["W:store16"] = attempt(lambda: e16.store_embedding("n1", [0.1] * 16))
    o["W:store8"] = attempt(lambda: e16.store_embedding("n1", [0.1] * 8))
    e8b = engine(c, 8)
    o["W:e8_dry_populated"] = attempt(lambda: setup_obs(e8b.initialize_schema(dry_run=True)))
    o["W:e8_setup_populated"] = attempt(lambda: setup_obs(e8b.initialize_schema()))
    o["W:e8_rewidth_populated"] = attempt(lambda: setup_obs(e8b.initialize_schema(rewidth=True)))
    o["W:col_after_populated"] = colwidth(c, "kg_NodeEmbeddings")
    o["W:rows_after_populated"] = int(scalar(c, "SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings"))

    # identity: adopted -> claim -> no-op (normalized) -> conflict -> force; enforce; adopt on a legacy row
    ident = lambda m: EmbeddingIdentity(mechanism="external", model_key=m, dimension=16, dtype="DOUBLE")
    o["I:reg_adopted"] = registry(c, "kg_NodeEmbeddings")
    o["I:claim"] = attempt(lambda: e16.set_embedding_identity(ident("m-a")).model_key)
    o["I:reg_claimed"] = registry(c, "kg_NodeEmbeddings")
    o["I:same_normalized"] = attempt(lambda: e16.set_embedding_identity(ident("  M-A ")).model_key)
    o["I:other_model"] = attempt(lambda: e16.set_embedding_identity(ident("m-b")).model_key)
    o["I:reg_after_conflict"] = registry(c, "kg_NodeEmbeddings")
    o["I:force"] = attempt(lambda: e16.set_embedding_identity(ident("m-b"), force=True).model_key)
    o["I:reg_forced"] = registry(c, "kg_NodeEmbeddings")
    o["I:undeclared_set"] = attempt(lambda: e16.set_embedding_identity(EmbeddingIdentity(mechanism=None, model_key=None, dimension=16)).model_key)
    o["I:enforce_w8"] = attempt(lambda: (e16.enforce_embedding_identity("kg_NodeEmbeddings", dimension=8) or EmbeddingIdentity(None, None)).model_key)
    o["I:enforce_w16"] = attempt(lambda: (e16.enforce_embedding_identity("kg_NodeEmbeddings", dimension=16) or EmbeddingIdentity(None, None)).model_key)
    o["I:enforce_other_model"] = attempt(lambda: (e16.enforce_embedding_identity("kg_NodeEmbeddings", dimension=16, config="m-c") or EmbeddingIdentity(None, None)).model_key)
    cur = c.cursor(); cur.execute("DELETE FROM Graph_KG.embedding_registry WHERE table_name = 'kg_EdgeEmbeddings' AND graph_id = ''"); cur.close(); c.commit()
    o["I:edge_col"] = colwidth(c, "kg_EdgeEmbeddings")
    o["I:adopt"] = attempt(lambda: dict(sorted(e16.adopt_embedding_identities().items())))
    c.commit()
    o["I:reg_edge_adopted"] = registry(c, "kg_EdgeEmbeddings")
    o["I:adopt_again"] = attempt(lambda: dict(sorted(e16.adopt_embedding_identities().items())))
    o["I:reg_node_after_adopt"] = registry(c, "kg_NodeEmbeddings")

    # quarantine placement
    e16.create_node("q1", labels=["Q"], graph="g1")
    route = e16.resolve_route("g1", "qm", create=True, dimension=4)
    o["Q:route_dim"] = None if route is None else route.dimension
    q = lambda nid, dim, dtype, vec: (lambda cur: (cur.execute(
        "INSERT INTO Graph_KG.embedding_quarantine (node_id, source_table, emb, dimension, dtype, reason) "
        f"VALUES (?, 'kg_NodeEmbeddings', TO_VECTOR(?, DOUBLE, {len(vec.split(','))}), ?, ?, 'ambiguous_graph')",
        [nid, vec, dim, dtype]), cur.execute("SELECT MAX(q_rowid) FROM Graph_KG.embedding_quarantine"), cur.fetchone()[0]))(c.cursor())[2]
    rows = {"ok": q("q1", 4, "DOUBLE", "1,0,0,0"), "nonode": q("q2", 4, "DOUBLE", "0,1,0,0"),
            "width": q("q1", 3, "DOUBLE", "1,0,0"), "dtype": q("q1", 4, "FLOAT", "0,0,1,0"),
            "noroute": q("q1", 4, "DOUBLE", "0,0,0,1"), "dup": q("q1", 4, "DOUBLE", "1,1,0,0")}
    c.commit()
    qcount = lambda: len(e16.list_quarantine())
    rcount = lambda: int(scalar(c, f"SELECT COUNT(*) FROM Graph_KG.{route.table_name}"))
    o["Q:listed_before"] = qcount()
    o["Q:route_rows_before"] = rcount()
    o["Q:bad_reason"] = attempt(lambda: e16.list_quarantine(reason="bogus"))
    o["Q:reason_filter"] = len(e16.list_quarantine(reason="no_node"))
    o["Q:missing_row"] = attempt(lambda: e16.place_quarantined(999999, graph="g1", model_key="qm"))
    for name, graph in [("noroute", "g2"), ("width", "g1"), ("dtype", "g1"), ("nonode", "g1"), ("ok", "g1"), ("dup", "g1")]:
        before_q, before_r = qcount(), rcount()
        res = attempt(lambda: e16.place_quarantined(rows[name], graph=graph, model_key="qm"))
        o[f"Q:place_{name}"] = {**res, "dq": qcount() - before_q, "dr": rcount() - before_r,
                                "routes_g2": e16.resolve_route("g2", "qm") is not None}
    o["Q:total_conserved"] = qcount() + rcount() == o["Q:listed_before"] + o["Q:route_rows_before"]
    # The same placements with _quarantined_row materializing its row before the cursor closes (the proposed repair
    # for bug-srch-116, as get_embedding_identity already does): the checks after it, conditional on that repair.
    from iris_vector_graph._engine import schema as _sch
    orig = _sch.SchemaMixin._quarantined_row

    def materialized(self, q_rowid):
        cur = self.conn.cursor()
        try:
            cur.execute(f"SELECT node_id, dimension, dtype FROM {self._quarantine_table()} WHERE q_rowid = ?", [q_rowid])
            r = cur.fetchone()
            r = None if r is None else tuple(r)
        finally:
            cur.close()
        return None if r is None else (str(r[0]), r[1], r[2])
    _sch.SchemaMixin._quarantined_row = materialized
    try:
        for name, graph in [("noroute", "g2"), ("width", "g1"), ("dtype", "g1"), ("nonode", "g1"), ("ok", "g1"), ("dup", "g1")]:
            before_q, before_r = qcount(), rcount()
            res = attempt(lambda: e16.place_quarantined(rows[name], graph=graph, model_key="qm"))
            o[f"QR:place_{name}"] = {**res, "dq": qcount() - before_q, "dr": rcount() - before_r,
                                     "routes_g2": e16.resolve_route("g2", "qm") is not None}
        o["QR:total_conserved"] = qcount() + rcount() == o["Q:listed_before"] + o["Q:route_rows_before"]
    finally:
        _sch.SchemaMixin._quarantined_row = orig
    c.close()

    # ---- NS B: setup's choice of schema from where IVG's tables are ----
    recreate_namespace("I56SB")
    c = connect("I56SB"); nat = native(c)
    o["B:x_setup"] = attempt(lambda: setup_obs(engine(c, 8, "I56X").initialize_schema()))
    o["B:x_record"] = gget(nat, "schema")
    nat.kill("^IVG.Deploy", "schema")
    o["B:default_call"] = attempt(lambda: engine(c, 8).get_node_count())
    o["B:default_dry"] = attempt(lambda: setup_obs(engine(c, 8).initialize_schema(dry_run=True)))
    o["B:default_setup"] = attempt(lambda: setup_obs(engine(c, 8).initialize_schema()))
    o["B:y_explicit_dry"] = attempt(lambda: setup_obs(engine(c, 8, "I56Y").initialize_schema(dry_run=True)))
    os.environ["IVG_SCHEMA_PREFIX"] = "I56Y"
    o["B:y_env_dry"] = attempt(lambda: setup_obs(engine(c, 8).initialize_schema(dry_run=True)))
    os.environ.pop("IVG_SCHEMA_PREFIX", None)
    o["B:x_lower_dry"] = attempt(lambda: setup_obs(engine(c, 8, "i56x").initialize_schema(dry_run=True)))
    o["B:record_after_dry"] = gget(nat, "schema")
    o["B:x_inferred_setup"] = attempt(lambda: setup_obs(engine(c, 8, "I56X").initialize_schema()))
    o["B:record_after"] = gget(nat, "schema")
    o["B:x_call"] = attempt(lambda: engine(c, 8, "I56X").get_node_count())
    # the same schema named in another case: a real run (observation only; widths agree, 8)
    def lower_setup():
        st = engine(c, 8, "i56x").initialize_schema()
        return {**setup_obs(st), "failed_classes": sorted(st.get("objectscript_failed") or {}),
                "routines_failed": sorted((st.get("routines") or {}).get("failed") or {})}
    o["B:x_lower_setup"] = attempt(lower_setup)
    o["B:fingerprint_after_lower"] = gget(nat, "fingerprint") is not None
    o["B:sqlproc_after_lower"] = attempt(lambda: scalar(c, "SELECT I56X.Percentile_PDISC('[1,2,3]', 0.5)"))
    o["B:cypher_after_lower"] = attempt(lambda: engine(c, 8, "I56X").execute_cypher("MATCH (n) RETURN count(n) AS c").rows)
    o["B:x_setup_after_lower"] = attempt(lambda: setup_obs(engine(c, 8, "I56X").initialize_schema()))
    o["B:record_after_lower"] = gget(nat, "schema")
    o["B:x_lower_call"] = attempt(lambda: engine(c, 8, "i56x").get_node_count())
    # bug-plt-026 end to end: no record, IVG's tables in I56X only, an engine naming I56Y explicitly runs setup
    nat.kill("^IVG.Deploy", "schema")
    o["B:y_explicit_setup"] = attempt(lambda: setup_obs(engine(c, 8, "I56Y").initialize_schema()))
    o["B:record_after_explicit"] = gget(nat, "schema")
    o["B:x_call_after_explicit"] = attempt(lambda: engine(c, 8, "I56X").get_node_count())
    c.close()
    # ---- NS D: the recorded schema named in another letter case, over a populated table at another width ----
    from iris_vector_graph.schema import GraphSchema
    recreate_namespace("I56SD")
    c = connect("I56SD")
    eW = engine(c, 8, "I56W")
    eW.initialize_schema()
    eW.create_node("v1", labels=["T"])
    o["D:store8"] = attempt(lambda: eW.store_embedding("v1", [0.25] * 8))

    def widths_reg():
        cur = c.cursor()
        try:
            w = {t: GraphSchema.get_embedding_dimension(cur, f"I56W.{t}") for t in ("kg_NodeEmbeddings", "kg_EdgeEmbeddings", "kg_NodeEmbeddings_optimized")}
            cur.execute("SELECT table_name, dimension FROM I56W.embedding_registry WHERE graph_id = ''")
            reg = {str(r[0]): int(r[1]) for r in cur.fetchall() if r[1] not in (None, "")}
        finally:
            cur.close()
        return {"col": w, "reg": reg}
    o["D:upper16_setup"] = attempt(lambda: setup_obs(engine(c, 16, "I56W").initialize_schema()))
    o["D:after_upper"] = widths_reg()
    o["D:lower16_dry"] = attempt(lambda: setup_obs(engine(c, 16, "i56w").initialize_schema(dry_run=True)))
    o["D:lower16_setup"] = attempt(lambda: setup_obs(engine(c, 16, "i56w").initialize_schema()))
    o["D:after_lower"] = widths_reg()
    o["D:rows_after"] = int(scalar(c, "SELECT COUNT(*) FROM I56W.kg_NodeEmbeddings"))
    c.close()
    o["elapsed_s"] = round(time.time() - t0, 1)
    return o


if __name__ == "__main__":
    obs = observe()
    out = REPO / ".g5/uplift/consolidated/iteration-56/install" / ("observed-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ".json")
    out.write_text(json.dumps(obs, indent=1, sort_keys=True, default=str) + "\n")
    print(out)
    print(json.dumps(obs, indent=1, sort_keys=True, default=str))
