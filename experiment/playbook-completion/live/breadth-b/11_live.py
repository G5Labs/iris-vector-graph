#!/usr/bin/env python3
"""Module 11 (ledger core) live checks on AUDITB, one process: journal footprints of the ledger writers and the cheap
finding reproductions (F-1101, F-1105..F-1113).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 900 python experiment/playbook-completion/live/breadth-b/11_live.py

Starts by resetting the AUDITB ledger to never-enabled with the pin's test/admin reset (Ledger.PurgeAll,
Ledger.cls:241-248) and ends the same way (strict off, never-enabled, b11 rows removed), so no other lane-B worker
meets strict mode. Writes $RUN_DIR/breadth-b/live/11-*.json, one log per check group.
"""
from __future__ import annotations

import importlib
import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
C = importlib.import_module("11_common")
from blive import session, capture, write_log  # noqa: E402

from iris_vector_graph.ledger.changeset import Changeset  # noqa: E402

warnings.simplefilter("ignore", DeprecationWarning)


def cs(**kw):
    kw.setdefault("actor", "b11-tester")
    kw.setdefault("actor_type", "service")
    return Changeset(**kw)


def exc(e):
    return {"type": type(e).__name__, "mro": [k.__name__ for k in type(e).__mro__][:5], "msg": str(e)[:400]}


def commit(eng, c, **kw):
    try:
        r = eng.ledger.commit(c, **kw)
        return {"ok": True, "seq": r.revision.seq, "kind": getattr(r.revision, "kind", None),
                "revision_id": r.revision.revision_id, "replayed": r.replayed,
                "stmt_ids": {str(k): v for k, v in r.stmt_ids.items()},
                "post_commit_applied": r.post_commit_applied, "post_commit_error": r.post_commit_error}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, **exc(e)}


def prop(c, nid, key, graph=""):
    rows = c.sql("SELECT val FROM Graph_KG.rdf_props WHERE s = ? AND \"key\" = ? AND graph_id = ?", nid, key, graph) \
        if graph else c.sql("SELECT val FROM Graph_KG.rdf_props WHERE s = ? AND \"key\" = ? AND (graph_id IS NULL OR graph_id = '')", nid, key)
    return [r[0] for r in rows]


def main() -> int:
    out = {}
    with session("11-live") as s:
        try:
            return body(s, out)
        except Exception:
            import traceback
            write_log(s, {"phase": "crash", "traceback": traceback.format_exc(), "partial": out,
                          "finish": C.finish(s, "11_live.py crash")}, name="11-live-crash")
            raise


def body(s, out) -> int:
    if True:
        c, eng, smap = s.c, s.eng, s.smap
        pid = c.pid
        out["meta_at_start"] = C.meta(c)
        out["purge_at_start"] = C.purge(c)
        out["scrub_at_start"] = C.scrub(c)
        # content before the genesis (unrecorded, captured by the genesis)
        eng.create_node("b11_a", labels=["B11"], properties={"name": "a"})
        eng.create_node("b11_b", labels=["B11"], properties={"name": "b"})
        fp = {}

        # ---- enable (genesis), max_ops 3 so F-1107's size bypass is cheap
        cap = capture(s, lambda: eng.ledger.enable(max_ops=3))
        fp["enable_genesis"] = C.analyse(cap, smap, pid)
        genesis = eng.ledger.head()
        fp["enable_genesis"]["head"] = genesis.seq
        fp["enable_genesis"]["stats"] = C.stats_row(c)

        # ---- commit: node ops (3 ops)
        x = cs(message="b11 node ops")
        x.create_node("b11_c", labels=["B11"], properties={"name": "c"})
        x.add_label("b11_a", "B11X")
        x.set_property("b11_a", "k", "1")
        cap = capture(s, lambda: commit(eng, x))
        fp["commit_node_ops"] = C.analyse(cap, smap, pid)

        # ---- commit: create_rel (stmt maps)
        x = cs(message="b11 rel")
        x.create_relationship("b11_a", "B11R", "b11_b", {"w": "1"})
        cap = capture(s, lambda: commit(eng, x))
        fp["commit_create_rel"] = C.analyse(cap, smap, pid)
        sid = cap.result["stmt_ids"].get("0") if isinstance(cap.result, dict) else None
        fp["commit_create_rel"]["stmt_id"] = sid

        # ---- commit: set qualifier, then delete rel + detach delete node
        x = cs(message="b11 qual")
        x.set_qualifier(stmt_id=sid, key="w", value="2")
        cap = capture(s, lambda: commit(eng, x))
        fp["commit_set_qual"] = C.analyse(cap, smap, pid)
        x = cs(message="b11 deletes")
        x.delete_relationship(stmt_id=sid)
        x.delete_node("b11_c", mode="detach")
        cap = capture(s, lambda: commit(eng, x))
        fp["commit_delete_rel_node"] = C.analyse(cap, smap, pid)

        # ---- refused commit (stale head): rollback, then Bump in its own transaction after the unlock
        x = cs(message="b11 stale", expected_head=genesis.revision_id)
        x.set_property("b11_a", "k", "stale")
        cap = capture(s, lambda: commit(eng, x))
        fp["commit_refused_stale"] = C.analyse(cap, smap, pid)
        fp["commit_refused_stale"]["stats_after"] = C.stats_row(c)
        write_log(s, {"phase": "footprints-1", "fp": fp}, name="11-footprints-1")

        # ================= F-1101: a replayed commit writes its post-commit properties again
        f = {}
        x1 = cs(message="b11 pcp", idempotency_key="b11-k1")
        x1.create_node("b11_p1", labels=["B11"])
        x1.post_commit_properties = {"b11_p1": {"audit": "pcp-v1"}}
        f["first"] = commit(eng, x1)
        f["after_first"] = prop(c, "b11_p1", "audit")
        x2 = cs(message="b11 governed set")
        x2.set_property("b11_p1", "audit", "governed-v2")
        f["governed_set"] = commit(eng, x2)
        f["after_governed"] = prop(c, "b11_p1", "audit")
        x1b = cs(message="b11 pcp retry", idempotency_key="b11-k1")
        x1b.create_node("b11_p1", labels=["B11"])
        x1b.post_commit_properties = {"b11_p1": {"audit": "pcp-v1"}}
        cap = capture(s, lambda: commit(eng, x1b))
        f["retry"] = cap.result
        f["retry_footprint"] = C.analyse(cap, smap, pid)
        f["after_retry"] = prop(c, "b11_p1", "audit")
        # same key and ops, different post-commit properties: the fingerprint excludes them (changeset.py:365-385)
        x1c = cs(message="b11 pcp retry other", idempotency_key="b11-k1")
        x1c.create_node("b11_p1", labels=["B11"])
        x1c.post_commit_properties = {"b11_p1": {"audit": "pcp-OTHER"}}
        f["retry_other_pcp"] = commit(eng, x1c)
        f["after_retry_other"] = prop(c, "b11_p1", "audit")
        rep = eng.ledger.verify()
        f["verify"] = {"result": rep.result, "classification": rep.classification, "b11": C.diffs(rep, "b11_p1")}
        f["reproduced"] = (f["retry"].get("replayed") is True and f["after_governed"] == ["governed-v2"]
                           and f["after_retry"] == ["pcp-v1"] and rep.result == "diverges")
        out["F-1101"] = f
        fp["commit_replayed_with_pcp"] = f["retry_footprint"]

        # ================= F-1106: a replayed commit returns no statement ids
        f = {}
        x = cs(message="b11 rel keyed", idempotency_key="b11-k2")
        x.create_relationship("b11_a", "B11S", "b11_b")
        f["first"] = commit(eng, x)
        x = cs(message="b11 rel keyed retry", idempotency_key="b11-k2")
        x.create_relationship("b11_a", "B11S", "b11_b")
        f["retry"] = commit(eng, x)
        f["reproduced"] = bool(f["first"].get("stmt_ids")) and f["retry"].get("replayed") is True and f["retry"].get("stmt_ids") == {}
        out["F-1106"] = f

        # ================= F-1109: a retry without a retry key is not a replay
        f = {}
        x = cs(message="b11 nokey 1")
        x.set_property("b11_a", "nk", "v")
        f["first"] = commit(eng, x)
        x = cs(message="b11 nokey 2")
        x.set_property("b11_a", "nk", "v")
        f["second_same_ops"] = commit(eng, x)
        x = cs(message="b11 nokey create")
        x.create_node("b11_nk")
        f["create_1"] = commit(eng, x)
        x = cs(message="b11 nokey create again")
        x.create_node("b11_nk")
        f["create_2"] = commit(eng, x)
        f["reproduced"] = (f["second_same_ops"].get("ok") and not f["second_same_ops"].get("replayed")
                           and f["second_same_ops"].get("seq") != f["first"].get("seq") and not f["create_2"].get("ok"))
        out["F-1109"] = f

        # ================= F-1107: a commit accepts any revision kind
        f = {}
        for kind in ("genesis", "redaction", "b11-bogus"):
            x = cs(message=f"b11 kind {kind}")
            x.create_node(f"b11_k_{kind.replace('-', '_')}")
            f[f"kind_{kind}"] = commit(eng, x, kind=kind)
        big = cs(message="b11 4 ops changeset")
        for i in range(4):
            big.create_node(f"b11_big{i}")
        f["changeset_4_ops_max3"] = commit(eng, big)
        big2 = cs(message="b11 4 ops other kind")
        for i in range(4):
            big2.create_node(f"b11_bog{i}")
        f["other_kind_4_ops_max3"] = commit(eng, big2, kind="b11-bogus")
        ghost = cs(message="b11 adoption of nothing")
        ghost.ops = [{"op": "create_node", "entity_kind": "node", "entity_id": "b11_ghost", "attr": "",
                      "prior": None, "new": "{}", "graph": None}]
        f["adoption_ghost"] = commit(eng, ghost, kind="adoption")
        f["ghost_rows"] = C.counts(c)
        f["ghost_node_rows"] = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'b11_ghost'")[0][0]
        f["revisions"] = [r for r in C.revisions(c) if r[0] > 1]
        rep = eng.ledger.verify()
        f["verify"] = {"result": rep.result, "b11_ghost": C.diffs(rep, "b11_ghost")}
        f["reproduced"] = (f["kind_genesis"].get("ok") and f["kind_redaction"].get("ok")
                           and f["other_kind_4_ops_max3"].get("ok") and not f["changeset_4_ops_max3"].get("ok")
                           and f["adoption_ghost"].get("ok") and f["ghost_node_rows"] == 0)
        out["F-1107"] = f

        # ================= F-1105: a node change for an id only a named graph holds
        f = {}
        eng.create_node("b11_named", labels=["B11N"], properties={"name": "n"}, graph="b11g")
        f["rows_before"] = c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = 'b11_named'")
        x = cs(message="b11 delete named-only")
        x.delete_node("b11_named")
        f["delete_plain"] = commit(eng, x)
        f["rows_after"] = c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = 'b11_named'")
        if f["delete_plain"].get("ok"):
            f["records"] = C.records(c, f["delete_plain"]["seq"])
        x = cs(message="b11 set_prop named-only")
        x.set_property("b11_named", "z", "1")
        f["set_prop"] = commit(eng, x)
        f["orphan_default_prop"] = c.sql("SELECT graph_id, val FROM Graph_KG.rdf_props WHERE s = 'b11_named' AND \"key\" = 'z'")
        x = cs(message="b11 add_label named-only")
        x.add_label("b11_named", "B11Z")
        f["add_label"] = commit(eng, x)
        rep = eng.ledger.verify()
        f["verify"] = {"result": rep.result, "b11_named": C.diffs(rep, "b11_named")}
        f["reproduced"] = bool(f["delete_plain"].get("ok") and f["rows_after"] and rep.result == "diverges")
        out["F-1105"] = f

        # ================= F-1113: history's source filter vs stored JSON text
        f = {}
        x = cs(message="b11 sourced", source={"system": "cmms", "run": "b11"})
        f["commit"] = commit(eng, x)
        f["stored_source"] = c.sql("SELECT source FROM Graph_KG.ledger_revisions WHERE seq = ?", f["commit"].get("seq", -1))
        f["history_source_cmms"] = len(eng.ledger.history(source="cmms", limit=1000).revisions)
        stored = f["stored_source"][0][0] if f["stored_source"] else None
        f["history_source_exact_text"] = len(eng.ledger.history(source=stored, limit=1000).revisions) if stored else None
        f["history_source_python_json"] = len(eng.ledger.history(source=json.dumps({"system": "cmms", "run": "b11"}), limit=1000).revisions)
        f["reproduced"] = f["history_source_cmms"] == 0 and (f["history_source_exact_text"] or 0) >= 1
        out["F-1113"] = f

        # ================= F-1111: the metrics hook and Python-side refusals
        f = {"events": []}
        eng.ledger.register_metrics_hook(lambda ev: f["events"].append(ev))
        try:
            eng.ledger.commit(cs(message="b11 empty"))
            f["empty"] = "accepted?"
        except Exception as e:  # noqa: BLE001
            f["empty"] = exc(e)
        f["events_after_empty"] = len(f["events"])
        bad = cs(message="b11 bad op_ref")
        bad.ops = [{"op": "delete_rel", "ref": {"op_ref": 5}}]
        try:
            eng.ledger.commit(bad)
            f["bad_ref"] = "accepted?"
        except Exception as e:  # noqa: BLE001
            f["bad_ref"] = exc(e)
        f["events_after_bad_ref"] = len(f["events"])
        x = cs(message="b11 stale for hook", expected_head=genesis.revision_id)
        x.set_property("b11_a", "k", "z")
        f["stale"] = commit(eng, x)
        f["events_after_stale"] = len(f["events"])
        f["event_outcomes"] = [ev.get("outcome") for ev in f["events"]]
        f["reproduced"] = f["events_after_empty"] == 0 and f["events_after_bad_ref"] == 0 and f["events_after_stale"] == 1
        out["F-1111"] = f

        # ================= F-1112: meta has no "enabled" key
        m = eng.ledger.meta()
        out["F-1112"] = {"meta": m, "keys": sorted(m), "has_enabled": "enabled" in m,
                         "fixture_expr_value": bool(m.get("enabled")), "reproduced": "enabled" not in m and m.get("state") == "enabled"}
        write_log(s, {"phase": "findings-1", **{k: out[k] for k in out if k.startswith("F-")}}, name="11-findings-1")

        # ================= set_strict footprint, F-1108 (unguarded writer under strict), guard control
        f = {}
        cap = capture(s, lambda: eng.ledger.set_strict(True))
        fp["set_strict_on"] = C.analyse(cap, smap, pid)
        f["meta_strict"] = C.meta(c)
        f["edges_before"] = c.sql("SELECT s, p, o_id FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'b11'")
        try:
            eng.create_node("b11_guarded", labels=["B11"])
            f["guarded_create_node"] = "accepted"
        except Exception as e:  # noqa: BLE001
            f["guarded_create_node"] = exc(e)
        cap = capture(s, lambda: eng.bulk_delete_adjacency(["b11_a"]))
        f["bulk_delete_adjacency"] = {"result": cap.result, "error": cap.error, "fp": C.analyse(cap, smap, pid)}
        f["edges_after"] = c.sql("SELECT s, p, o_id FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'b11'")
        # GraphQL sample API mutation resolver, called directly (no server): api/gql/resolvers/mutation.py:23-230
        try:
            import asyncio
            from api.gql.resolvers.mutation import Mutation
            from api.gql.types import CreateProteinInput

            class _Info:
                context = {"db_connection": c.conn, "protein_loader": None}
            inp = CreateProteinInput(id="b11_gql", name="g")
            fn = Mutation.create_protein
            fn = getattr(fn, "base_resolver", None) and fn.base_resolver.wrapped_func or fn
            try:
                asyncio.run(fn(Mutation(), _Info(), inp))
                f["graphql_create_protein"] = "returned"
            except Exception as e:  # noqa: BLE001
                f["graphql_create_protein"] = exc(e)
            f["graphql_rows"] = c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = 'b11_gql'")
        except Exception as e:  # noqa: BLE001
            f["graphql_create_protein"] = {"import_or_call_error": exc(e)}
        rep = eng.ledger.verify()
        f["verify"] = {"result": rep.result, "b11_rel": [d for d in C.diffs(rep, "b11") if d["kind"] == "rel"][:10],
                       "b11_gql": C.diffs(rep, "b11_gql")}
        cap = capture(s, lambda: eng.ledger.set_strict(False))
        fp["set_strict_off"] = C.analyse(cap, smap, pid)
        f["reproduced"] = (isinstance(f["guarded_create_node"], dict) and "Strict" in f["guarded_create_node"]["type"]
                           and f["bulk_delete_adjacency"]["error"] is None and len(f["edges_after"]) < len(f["edges_before"]))
        out["F-1108"] = f

        # ================= disable, unrecorded write, re-enable with adoption (footprints)
        cap = capture(s, lambda: eng.ledger.disable())
        fp["disable"] = C.analyse(cap, smap, pid)
        eng.create_node("b11_u", labels=["B11"], properties={"name": "u"})  # unrecorded while disabled
        stats_before = C.stats_row(c)
        cap = capture(s, lambda: eng.ledger.enable())
        fp["reenable_with_adoption"] = C.analyse(cap, smap, pid)
        fp["reenable_with_adoption"]["result"] = str(cap.result)[:300]
        fp["reenable_with_adoption"]["revisions_tail"] = C.revisions(c)[-2:]
        fp["reenable_with_adoption"]["stats_before_after"] = [stats_before, C.stats_row(c)]
        write_log(s, {"phase": "footprints-2", "fp": fp, "F-1108": out["F-1108"]}, name="11-footprints-2")

        out["finish"] = C.finish(s, "11_live.py end")
        write_log(s, {"phase": "finish", "finish": out["finish"],
                      "reproduced": {k: v.get("reproduced") for k, v in out.items() if k.startswith("F-")}},
                  name="11-live-summary")
    print(json.dumps({k: (v.get("reproduced") if isinstance(v, dict) else None) for k, v in out.items()}, default=str))
    print(json.dumps(out["finish"], default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
