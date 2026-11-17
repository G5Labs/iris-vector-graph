"""Binding for install_lifecycle (iteration 56, Part B) on the run-isolated continuation fixture.

observe.py drops and re-creates the namespaces I56SA, I56SB and I56SC (from %SYS, container ivg-cont-20261117-iris only)
and drives the real engine at the pin through the install lifecycle. Every expected value below comes from a Python port
of install_lifecycle.rs (validate, resolve, first_access, how/setup/record_after, deploy/plan_compiles, col_action/
width_refused/width_after, conflicts/set_identity/adopt/enforce_ok, place/place_effect) applied to the history the
harness itself wrote (which namespace holds what, which marker or class it removed, which widths and rows it stored),
never from the product's answers. Mutations mirror the model's controls that this fixture can distinguish; one deciding
observation is tampered.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/install_lifecycle/binding.py)
"""
import hashlib, json, os, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO / ".g5/Verus_verification/tools"))
import observe  # noqa: E402
import runtime  # noqa: E402  (put on sys.path by observe)

MUTS = ["unknown-width-counted", "code-package-unchecked", "env-over-arg", "no-mismatch-check", "unrecorded-marker-refused", "traces-before-legacy",
        "dry-run-records", "explicit-refused", "clash-unchecked", "skip-on-marker-only", "populated-altered", "failed-deploy-keeps-marker",
        "rewidth-not-required", "adopt-overwrites", "width-only-with-models", "claim-known-model",
        "place-skips-node-check", "placement-creates-route", "delete-before-insert", "row-read-materialized"]
CODE_PACKAGES = ("Graph.KG", "IVG", "IVGC")
VT = ["kg_EdgeEmbeddings", "kg_NodeEmbeddings", "kg_NodeEmbeddings_optimized"]


# ------------------------------------------------------------------ port of install_lifecycle.rs
def validate(n, m):
    pkg = n.replace("_", ".").upper()
    if n == "": return ("err", "Empty")
    if n.startswith("%"): return ("err", "Percent")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", n): return ("err", "Pattern")
    if n.upper() == "SQLUSER": return ("err", "SqlUser")
    if n.upper() == "GRAPH_KG": return ("ok", "Graph_KG")
    if not m.get("code-package-unchecked") and any(pkg == c.upper() or pkg.startswith(c.upper() + ".") for c in CODE_PACKAGES):
        return ("err", "CodePackage")
    return ("ok", n)


def resolve(arg, env, m):
    if m.get("env-over-arg") and env: return env
    return arg if arg is not None else (env or "Graph_KG")


def first_access(ns, s, m):
    rec = ns.get("record")
    if rec is not None:
        return "ok" if (m.get("no-mismatch-check") or rec.upper() == s.upper()) else "mismatch"
    if s.upper() in ns.get("marker", set()) and not m.get("unrecorded-marker-refused"): return "ok"
    if m.get("traces-before-legacy"):
        if ns.get("traces"): return "unfinished"
        if ns.get("legacy"): return "not_upgraded"
    else:
        if ns.get("legacy"): return "not_upgraded"
        if ns.get("traces"): return "unfinished"
    return "never_set_up"


def how(i, m):
    if i["record"] is not None: return "existing"
    if not i["held_self"] and not i["held_other"]: return "new"
    if not i["held_other"]: return "inferred"
    if i["explicit"] and not m.get("explicit-refused"): return "explicit"
    return None


def setup(i, m):
    if i["record"] is not None and i["record"].upper() != i["s"].upper(): return ("err", "mismatch")
    h = how(i, m)
    if h is None: return ("err", "unrecorded_schemas")
    if i["clash"] and not m.get("clash-unchecked"): return ("err", "package_clash")
    return ("plan" if i["dry"] else "ran", h)


def record_after(i, m):
    k, h = setup(i, m)
    if k == "ran" and h != "existing": return i["s"]
    if k == "plan" and m.get("dry-run-records"): return i["s"]
    return i["record"]


def unchanged(d, m):
    return bool(d["marker_eq"] and (d["all_compiled"] or m.get("skip-on-marker-only")))


def col_action(db, dim, rows, rewidth, m):
    if db == dim: return "unchanged"
    if db is None: return "manual" if (m.get("unknown-width-counted") and rows != 0) else "alter"
    if rows != 0 and not m.get("populated-altered"): return "manual"
    if rewidth or m.get("rewidth-not-required"): return "alter"
    return "rewidth"


def width_refused(a, rewidth):
    return a == "rewidth" or (rewidth and a == "manual")


def conflicts(r, o, m):
    rm, om = r.get("model"), o.get("model")
    if rm is not None and om is not None and rm != om: return "conflict_model"
    if rm is not None and om is not None and r.get("mech") != o.get("mech"): return "conflict_mechanism"
    width_needs_models = m.get("width-only-with-models")
    if r.get("dim") is not None and o.get("dim") is not None and r["dim"] != o["dim"] and (not width_needs_models or (rm is not None and om is not None)):
        return "conflict_width"
    if r.get("dtype", "DOUBLE") != o.get("dtype", "DOUBLE"): return "conflict_dtype"
    return None


def set_identity(rec, o, force, m):
    if o.get("model") is None: return ("err", "value_error"), rec
    if force: return ("ok", o["model"]), {**o, "by": "forced"}
    if rec is None: return ("ok", o["model"]), {**o, "by": "claimed"}
    if (rec.get("model") is None or m.get("claim-known-model")) and (rec.get("dim") is None or rec["dim"] == o["dim"]):
        new = {**rec, "model": o["model"], "mech": o["mech"], "by": "claimed"}
        return ("ok", o["model"]), new
    c = conflicts(rec, o, m)
    if c: return ("err", c), rec
    return ("ok", rec["model"]), rec


def adopt(rec, declared, m):
    if rec is not None and not m.get("adopt-overwrites"): return rec, "already_recorded"
    return {"model": None, "mech": None, "dim": declared, "dtype": "DOUBLE", "by": "adopted"}, "adopted"


def place(row, row_read_ok, route, row_dim, row_dtype, node_in_graph, insert_ok, m):
    if not row: return "value_error"
    if not row_read_ok and not m.get("row-read-materialized"): return "row_read_failed"
    if route is None: return "placed_new_route" if m.get("placement-creates-route") else "no_route"
    if route["dim"] is None or route["dim"] != (row_dim or 0): return "conflict_width"
    if row_dtype != route["dtype"]: return "conflict_dtype"
    if not node_in_graph and not m.get("place-skips-node-check"): return "no_node"
    if not insert_ok: return "route_refused"
    return "placed"


def place_obs(out, m):
    """The observation a placement outcome gives: error kind (or ok True), quarantine and route row deltas, and whether g2 got a route."""
    if out == "placed": return {"ok": True, "dq": -1, "dr": 1, "routes_g2": False}
    if out == "placed_new_route": return {"ok": True, "dq": -1, "dr": 1, "routes_g2": True}
    if out == "route_refused" and m.get("delete-before-insert"): return {"err": out, "dq": -1, "dr": 0, "routes_g2": False}
    return {"err": out, "dq": 0, "dr": 0, "routes_g2": False}


def setup_view(k, h, schema, compiled, widths=None, manual=None, others=()):
    if k == "err": return {"err": h}
    return {"ok": {"how": h, "schema": schema, "compiled": compiled, "widths": widths, "manual": manual, "other_schemas": sorted(others)}}


def wl(**kw):
    out = {"alter": [], "needs_manual_migration": [], "needs_rewidth": [], "unchanged": []}
    for k, v in kw.items(): out[k] = sorted(v)
    return out


def widths_for(cols, dim, rewidth, m):
    """cols: table -> (declared width, rows). The dry run's lists and whether a run would refuse."""
    lists = {"alter": [], "needs_manual_migration": [], "needs_rewidth": [], "unchanged": []}
    bucket = {"unchanged": "unchanged", "alter": "alter", "manual": "needs_manual_migration", "rewidth": "needs_rewidth"}
    refused = False
    for t, (db, rows) in sorted(cols.items()):
        a = col_action(db, dim, rows, rewidth, m)
        lists[bucket[a]].append(t)
        refused |= width_refused(a, rewidth)
    return lists, refused


# ------------------------------------------------------------------ prediction from the harness's own history
def predict(m):
    p = {}
    for n in ["1abc", "SQLUser", "sqluser", "%X", "", "Graph_KG_x", "IVG_A", "IVGC", "I56_OK", "graph_kg", "GRAPH_KG", "a-b"]:
        k, v = validate(n, m)
        p[f"name:{n}"] = {"ok": v} if k == "ok" else {"err": "value_error"}
    p["resolve:arg_env"] = {"ok": resolve("ARGS", "ENVS", m)}
    p["resolve:env"] = {"ok": resolve(None, "ENVS", m)}
    p["resolve:env_empty"] = {"ok": resolve(None, "", m)}
    p["resolve:iris_prefix"] = {"ok": resolve(None, None, m)}   # IRIS_SCHEMA_PREFIX is not an input
    p["resolve:bad_arg"] = {"err": "value_error"}
    acc = lambda ns, s, ok_value=0: ({"ok": ok_value} if first_access(ns, s, m) == "ok" else {"err": first_access(ns, s, m)})

    # NS C: nothing; then a global of IVG's; then also a class an earlier release made; then a foreign class in I56Z
    p["C:fresh"] = acc({"record": None}, "Graph_KG")
    p["C:fresh_status_schema"] = {"ok": None}                   # status is exempt and reports the record
    p["C:global_only"] = acc({"record": None, "traces": True}, "Graph_KG")
    p["C:legacy_class"] = acc({"record": None, "traces": True, "legacy": True}, "Graph_KG")
    ci = {"record": None, "s": "I56Z", "held_self": False, "held_other": False, "explicit": True, "clash": True}
    k, h = setup({**ci, "dry": True}, m)
    p["C:clash_dry"] = setup_view(k, h, "I56Z", True, wl(), None)
    k, h = setup({**ci, "dry": False}, m)
    p["C:clash_run"] = setup_view(k, h, "I56Z", True, None, [])
    p["C:clash_record"] = record_after({**ci, "dry": False}, m)

    # NS A
    nsA = {"record": None}
    p["A:fresh"] = acc(nsA, "Graph_KG")
    a1 = {"record": None, "s": "Graph_KG", "held_self": False, "held_other": False, "explicit": False, "clash": False}
    k, h = setup({**a1, "dry": True}, m)
    p["A:dry1"] = setup_view(k, h, "Graph_KG", True, wl(), None)        # no vector table exists yet
    p["A:dry1_record"] = record_after({**a1, "dry": True}, m)
    p["A:dry1_tables"] = 0 if setup({**a1, "dry": True}, m)[0] == "plan" else 18    # the dry run writes no DDL
    p["A:dry1_fingerprint"] = False                                                 # nor the deploy marker
    p["A:still_refused_after_dry"] = acc({"record": record_after({**a1, "dry": True}, m)}, "Graph_KG")
    k, h = setup({**a1, "dry": False}, m)
    p["A:setup1"] = setup_view(k, h, "Graph_KG", True, None, [])
    rec = record_after({**a1, "dry": False}, m)
    p["A:setup1_record"] = rec
    nsA = {"record": rec, "marker": {"GRAPH_KG"}, "traces": True}
    p["A:after_setup_call"] = acc(nsA, "Graph_KG")
    a2 = {**a1, "record": rec, "held_self": True}
    cols8 = {t: (8, 0) for t in VT}
    d_same = {"marker_eq": True, "all_compiled": True}
    k, h = setup({**a2, "dry": False}, m)
    p["A:setup2"] = setup_view(k, h, "Graph_KG", not unchanged(d_same, m), None, [])
    k, h = setup({**a2, "dry": True}, m)
    p["A:dry2"] = setup_view(k, h, "Graph_KG", not unchanged(d_same, m), widths_for(cols8, 8, False, m)[0], None)
    alt = {**a2, "s": "I56ALT", "explicit": True}
    p["A:alt_call"] = acc(nsA, "I56ALT")
    p["A:alt_setup"] = setup_view(*setup({**alt, "dry": False}, m), "I56ALT", True)
    p["A:alt_dry"] = setup_view(*setup({**alt, "dry": True}, m), "I56ALT", True)
    p["A:alt_deploy"] = {"ok": "deployed"} if first_access(nsA, "I56ALT", m) != "mismatch" else {"err": "mismatch"}
    p["A:alt_status_schema"] = {"ok": nsA["record"]}
    p["A:alt_record_after"] = nsA["record"]
    p["A:lower_call"] = acc(nsA, "graph_kg")
    p["A:plan_unchanged"] = {"ok": unchanged(d_same, m)}
    d_fp = {"marker_eq": False, "all_compiled": True}
    p["A:plan_fp_altered"] = {"ok": unchanged(d_fp, m)}
    p["A:setup_fp_altered"] = setup_view("ran", "existing", "Graph_KG", not unchanged(d_fp, m), None, [])
    p["A:fp_restored"] = True                                    # a clean compile writes the fingerprint
    d_miss = {"marker_eq": True, "all_compiled": False}
    p["A:plan_class_missing"] = {"ok": unchanged(d_miss, m)}
    p["A:setup_class_missing"] = setup_view("ran", "existing", "Graph_KG", not unchanged(d_miss, m), None, [])
    p["A:class_back"] = not unchanged(d_miss, m)
    # the record removed after a complete setup: the marker function is still there
    nsR = {"record": None, "marker": {"GRAPH_KG"}, "traces": True}
    p["A:norecord_marker_call"] = acc(nsR, "Graph_KG")
    a3 = {**a1, "held_self": True}
    p["A:norecord_dry"] = setup_view(*setup({**a3, "dry": True}, m), "Graph_KG", False, widths_for(cols8, 8, False, m)[0], None)
    p["A:norecord_setup"] = setup_view(*setup({**a3, "dry": False}, m), "Graph_KG", False, None, [])
    rec3 = record_after({**a3, "dry": False}, m)
    p["A:norecord_record_after"] = rec3
    p["A:record_nomarker_call"] = acc({"record": rec3, "marker": set(), "traces": True}, "Graph_KG")
    p["A:norecord_nomarker_call"] = acc({"record": None, "marker": set(), "traces": True}, "Graph_KG")
    p["A:repair_setup"] = setup_view(*setup({**a3, "dry": False}, m), "Graph_KG", False, None, [])
    p["A:repair_record"] = record_after({**a3, "dry": False}, m)
    p["A:repair_call"] = acc({"record": p["A:repair_record"], "marker": {"GRAPH_KG"}, "traces": True}, "Graph_KG")

    # widths: the three vector tables declared 8 and empty; an engine at 16
    p["W:col_before"] = 8
    reg = adopt(None, 8, m)[0]
    p["W:reg_before"] = {"dim": reg["dim"], "kind": "node", "model": reg["model"], "set_by": reg["by"]}
    lists, refused = widths_for(cols8, 16, False, m)
    p["W:e16_dry"] = setup_view("plan", "existing", "Graph_KG", False, lists, None)
    p["W:e16_setup"] = {"err": "conflict"} if refused else setup_view("ran", "existing", "Graph_KG", False, None, [])
    w16 = {t: (16 if col_action(8, 16, 0, False, m) == "alter" else 8) for t in VT}
    if refused: w16 = {t: 8 for t in VT}
    p["W:col_after_refusal"] = w16["kg_NodeEmbeddings"]
    lists_r, refused_r = widths_for(cols8, 16, True, m)
    p["W:e16_dry_rewidth"] = setup_view("plan", "existing", "Graph_KG", False, lists_r, None)
    p["W:e16_rewidth"] = {"err": "conflict"} if refused_r else setup_view("ran", "existing", "Graph_KG", False, None, [])
    cols = {t: (16, 0) for t in VT} if not refused_r else cols8
    p["W:col_after_rewidth"] = cols["kg_NodeEmbeddings"][0]
    reg = {**reg, "dim": cols["kg_NodeEmbeddings"][0]}           # reconcile copies the declared width
    p["W:reg_after_rewidth"] = {"dim": reg["dim"], "kind": "node", "model": reg["model"], "set_by": reg["by"]}
    undeclared = lambda d: {"model": None, "mech": None, "dim": d, "dtype": "DOUBLE"}
    p["W:store16"] = {"err": conflicts(reg, undeclared(16), m)} if conflicts(reg, undeclared(16), m) else {"ok": True}
    p["W:store8"] = {"err": conflicts(reg, undeclared(8), m)} if conflicts(reg, undeclared(8), m) else {"ok": True}
    stored = p["W:store16"] == {"ok": True}
    colsP = {**cols, "kg_NodeEmbeddings": (cols["kg_NodeEmbeddings"][0], 1 if stored else 0)}
    lists_p, refused_p = widths_for(colsP, 8, False, m)
    p["W:e8_dry_populated"] = setup_view("plan", "existing", "Graph_KG", False, lists_p, None)
    p["W:e8_setup_populated"] = {"err": "conflict"} if refused_p else setup_view(
        "ran", "existing", "Graph_KG", False, None, sorted(t for t in lists_p["needs_manual_migration"]))
    _, refused_pr = widths_for(colsP, 8, True, m)
    p["W:e8_rewidth_populated"] = {"err": "conflict"} if refused_pr else setup_view("ran", "existing", "Graph_KG", False, None, [])
    after = cols["kg_NodeEmbeddings"][0]
    if not refused_p and col_action(after, 8, colsP["kg_NodeEmbeddings"][1], False, m) == "alter": after = 8
    p["W:col_after_populated"] = after
    p["W:rows_after_populated"] = colsP["kg_NodeEmbeddings"][1]

    # identity
    view = lambda r, kind="node": {"dim": r["dim"], "kind": kind, "model": r["model"], "set_by": r["by"]}
    p["I:reg_adopted"] = view(reg)
    ident = lambda mk: {"model": mk, "mech": "external", "dim": 16, "dtype": "DOUBLE"}
    out, reg = set_identity(reg, ident("m-a"), False, m); p["I:claim"] = dict([out]); p["I:reg_claimed"] = view(reg)
    out, reg = set_identity(reg, ident("m-a"), False, m); p["I:same_normalized"] = dict([out])   # keys normalized (search.embedding.model_key)
    out, reg = set_identity(reg, ident("m-b"), False, m); p["I:other_model"] = dict([out]); p["I:reg_after_conflict"] = view(reg)
    out, reg = set_identity(reg, ident("m-b"), True, m); p["I:force"] = dict([out]); p["I:reg_forced"] = view(reg)
    out, _ = set_identity(reg, undeclared(16), False, m); p["I:undeclared_set"] = dict([out])
    enf = lambda o: {"err": conflicts(reg, o, m)} if conflicts(reg, o, m) else {"ok": reg["model"]}
    p["I:enforce_w8"] = enf(undeclared(8))
    p["I:enforce_w16"] = enf(undeclared(16))
    p["I:enforce_other_model"] = enf({"model": "m-c", "mech": "iris-embedding-config", "dim": 16, "dtype": "DOUBLE"})
    p["I:edge_col"] = cols["kg_EdgeEmbeddings"][0]
    regs = {"kg_EdgeEmbeddings": None, "kg_NodeEmbeddings": reg, "kg_NodeEmbeddings_optimized": {"model": None, "dim": 16, "by": "adopted"}}
    outs = {}
    for t in VT:
        regs[t], outs[t] = adopt(regs[t], cols[t][0], m)
    p["I:adopt"] = {"ok": outs}
    p["I:reg_edge_adopted"] = view(regs["kg_EdgeEmbeddings"], "edge")    # the legacy edge table is an edge route (R316)
    outs2 = {}
    for t in VT:
        regs[t], outs2[t] = adopt(regs[t], cols[t][0], m)
    p["I:adopt_again"] = {"ok": outs2}
    p["I:reg_node_after_adopt"] = view(regs["kg_NodeEmbeddings"])

    # quarantine: route (g1, qm) 4-wide DOUBLE; q1 in g1, q2 nowhere; six rows; no route for g2
    route = {"dim": 4, "dtype": "DOUBLE"}
    p["Q:route_dim"] = 4
    p["Q:listed_before"] = 6
    p["Q:route_rows_before"] = 0
    p["Q:bad_reason"] = {"err": "bad_reason"}
    p["Q:reason_filter"] = 0
    p["Q:missing_row"] = {"err": place(False, False, route, None, "DOUBLE", True, True, m)}
    cases = [("noroute", None, 4, "DOUBLE", True), ("width", route, 3, "DOUBLE", True), ("dtype", route, 4, "FLOAT", True),
             ("nonode", route, 4, "DOUBLE", False), ("ok", route, 4, "DOUBLE", True), ("dup", route, 4, "DOUBLE", True)]
    for prefix, readable in (("Q", False), ("QR", True)):
        held = 0                                                  # vectors of q1 the route holds
        q, r = 6, 0
        for name, rt, dim, dt, node in cases:
            out = place(True, readable, rt, dim, dt, node, held == 0, m)     # the route's key holds one vector per node
            ob = place_obs(out, m)
            p[f"{prefix}:place_{name}"] = ob
            q += ob["dq"]; r += ob["dr"]
            if ob.get("ok") and rt is not None: held += 1
        p[f"{prefix}:total_conserved"] = (q + r == 6)

    # NS B: setup in I56X; record removed; other engines ask
    b1 = {"record": None, "s": "I56X", "held_self": False, "held_other": False, "explicit": True, "clash": False}
    p["B:x_setup"] = setup_view(*setup({**b1, "dry": False}, m), "I56X", True, None, [])
    p["B:x_record"] = record_after({**b1, "dry": False}, m)
    nsB = {"record": None, "marker": {"I56X"}, "traces": True}
    p["B:default_call"] = acc(nsB, "Graph_KG")
    bd = {"record": None, "s": "Graph_KG", "held_self": False, "held_other": True, "explicit": False, "clash": False}
    p["B:default_dry"] = setup_view(*setup({**bd, "dry": True}, m), "Graph_KG", True, wl(), None, ["I56X"])
    p["B:default_setup"] = setup_view(*setup({**bd, "dry": False}, m), "Graph_KG", True, None, [], ["I56X"])
    p["B:record_after_dry"] = record_after({**bd, "dry": True}, m)
    by = {**bd, "s": "I56Y", "explicit": True}
    p["B:y_explicit_dry"] = setup_view(*setup({**by, "dry": True}, m), "I56Y", True, wl(), None, ["I56X"])
    p["B:y_env_dry"] = p["B:y_explicit_dry"]
    bx = {**b1, "held_self": True}
    k, h = setup({**bx, "dry": False}, m)
    p["B:x_inferred_setup"] = setup_view(k, h, "I56X", False, None, [])
    recB = record_after({**bx, "dry": False}, m)
    p["B:record_after"] = recB
    p["B:x_call"] = acc({"record": recB, "marker": {"I56X"}}, "I56X")
    p["B:record_after_lower"] = recB                              # existing: the stored text is kept
    # the other-case engine's deploy: its fingerprint differs (sources rewritten for "i56x"), so it loads; IRIS refuses the
    # three schema classes under the other-case package name (P-CASE-CLASS, ERROR #5092), so the compile is not clean
    dl = {"marker_eq": False, "all_compiled": True}
    marker_after_lower = None if not m.get("failed-deploy-keeps-marker") else "fp_i56x"
    p["B:fingerprint_after_lower"] = marker_after_lower is not None
    # the I56X engine's next setup: its own fingerprint is not the marker (none, or the i56x one) -> it compiles
    p["B:x_setup_after_lower"] = setup_view("ran", "existing", "I56X", not unchanged({"marker_eq": False, "all_compiled": True}, m), None, [])
    p["B:sqlproc_after_lower"] = {"ok": 2}                       # observation of the projected procedure still answering
    p["B:cypher_after_lower"] = {"ok": [[0]]}
    be = {**by, "dry": False}
    p["B:y_explicit_setup"] = setup_view(*setup(be, m), "I56Y", True, None, [], ["I56X"])
    recE = record_after(be, m)
    p["B:record_after_explicit"] = recE
    p["B:x_call_after_explicit"] = acc({"record": recE, "marker": {"I56X", "I56Y"}}, "I56X")
    p["B:x_lower_call"] = acc({"record": recB, "marker": {"I56X"}}, "i56x")
    # NS D: I56W set up at 8, one 8-wide vector stored; engines at 16 named I56W and i56w
    colsD = {"kg_NodeEmbeddings": (8, 1), "kg_EdgeEmbeddings": (8, 0), "kg_NodeEmbeddings_optimized": (8, 0)}
    p["D:store8"] = {"ok": True}
    _, refD = widths_for(colsD, 16, False, m)
    p["D:upper16_setup"] = {"err": "conflict"} if refD else setup_view("ran", "existing", "I56W", False, None, [])
    p["D:after_upper"] = {"col": {t: v[0] for t, v in colsD.items()}, "reg": {t: v[0] for t, v in colsD.items()}}
    # the other-case engine reads no declared width (P-CASE-LOOKUP): every existing column reads as db None
    lookup = {t: (None, rows) for t, (db, rows) in colsD.items()}
    listsL, refL = widths_for(lookup, 16, False, m)
    p["D:lower16_dry"] = setup_view("plan", "existing", "I56W", True, listsL, None)
    p["D:lower16_setup"] = {"err": "conflict"} if refL else setup_view("ran", "existing", "I56W", True, None,
                                                                      sorted(listsL["needs_manual_migration"]))
    col_after = {}
    for t, (db, rows) in colsD.items():
        a = col_action(None, 16, rows, False, m)
        # IRIS refuses to re-declare a populated vector column (P-ALTER-POPULATED); an empty one moves
        col_after[t] = 16 if (a == "alter" and rows == 0 and not refL) else db
    p["D:after_lower"] = {"col": col_after, "reg": {t: v[0] for t, v in colsD.items()}}   # reconcile reads no width either
    p["D:rows_after"] = 1
    return p


def normalize(o):
    """The observation reduced to the predicted fields: setup replies keep how/schema/compiled/widths/manual/others."""
    out = {}
    for k, v in o.items():
        if isinstance(v, dict) and "err" in v and isinstance(v["err"], str):
            e = v["err"]
            if "Cursor closed" in e: e = "row_read_failed"
            elif e.startswith("other:IntegrityError") and "UNIQUE or PRIMARY KEY" in e: e = "route_refused"
            v = {**v, "err": e}
        if isinstance(v, dict) and isinstance(v.get("ok"), dict) and "how" in v["ok"]:
            s = v["ok"]
            v = {"ok": {"how": s["how"], "schema": s["schema"], "compiled": s["compiled"], "widths": s["widths"],
                        "manual": s["manual"], "other_schemas": s["other_schemas"]}}
        out[k] = v
    return out


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    t0 = time.time()
    raw = observe.observe()
    got = json.loads(json.dumps(normalize(raw), default=str))
    want = json.loads(json.dumps(predict({}), default=str))
    mism = [{"case": k, "observed": got.get(k), "expected": want[k]} for k in want if got.get(k) != want[k]]
    sens = {mm: sum(1 for k, v in json.loads(json.dumps(predict({mm: True}), default=str)).items() if v != got.get(k)) for mm in MUTS}
    tampered = dict(got); tampered["A:norecord_marker_call"] = {"err": "unfinished"}
    tamper_detected = any(tampered.get(k) != want[k] for k in want)
    import binding_common as bc
    body = {"fixture": runtime.NAME, "port": runtime.PORT, "namespaces": ["I56SA", "I56SB", "I56SC", "I56SD"],
            "run": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "verdict": "AGREES" if not mism else "DISAGREES",
            "cases": len(want), "mismatches": mism, "observed": raw, "observed_only": sorted(set(raw) - set(want)),
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "product_inputs": {f: sha(Path(runtime.PIN) / f) for f in [
                "iris_vector_graph/schema_name.py", "iris_vector_graph/schema.py", "iris_vector_graph/_engine/schema.py",
                "iris_vector_graph/_engine/class_deploy.py", "iris_vector_graph/embedding_identity.py",
                "iris_vector_graph/engine.py", "iris_vector_graph/_engine/embeddings.py"]},
            "harness_inputs": {str(q.relative_to(REPO)): sha(q) for q in [HERE / "observe.py", HERE / "model.json"]},
            "scope": "Real engine at pin 3eaa79cf on IRIS 2026.1, namespaces I56SA/B/C re-created: schema-name validation and resolution "
                     "(12 names, 5 resolutions); first access on never-set-up, IVG-global-only, earlier-release, recorded, record-removed and "
                     "marker-dropped namespaces; setup and dry run new/existing/inferred/explicit/mismatch/unrecorded/clash; class deploy "
                     "skip, fingerprint change, a class deleted; vector widths 8 -> 16 refused, rewidth, populated with empty siblings; "
                     "identity adopt/claim/normalized/conflict/force/enforce/re-adopt; quarantine placement as built (DB-API driver) and with "
                     "_quarantined_row materialized (the proposed repair, conditional)."}
    out = bc.write_receipt("install_lifecycle", HERE / "binding.py", body)
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "all_sensitivities_detected", "sensitivities_detected_cases",
                                           "observation_tamper_detected", "elapsed_s")}))
    print(out)
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
