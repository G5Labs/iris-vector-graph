#!/usr/bin/env python3
"""F-C1306 live probe: legacy Graph_KG.ledger_revisions rows after a 4.5.1 -> pin upgrade to a non-default schema.

    source experiment/playbook-completion/environment.sh
    bash experiment/playbook-completion/tools/locks.sh iris timeout 3000 \
        python experiment/playbook-completion/fc1306/probe.py

Builds the precondition with the pinned upstream fixture's own functions, imported unmodified from
scripts/fixtures/build_release_namespace.py (what tests/e2e/test_460_upgrade_ledger_history_e2e.py::upg calls):

  1. `build("v4.5.1", NS, schema_prefix="RAG")`: a new scratch namespace NS with its own database, v4.5.1's own
     initialize_schema (its classes compiled by v4.5.1's own code, as the fixture does), the seed copied to RAG.
  2. `run_ledger_commits("v4.5.1", NS, "RAG")`: v4.5.1's ledger enabled, the fixture's two r114 changesets.
  3. fc1306/ledger451_child.py, run the way `run_ledger_commits` runs its child (release worktree on PYTHONPATH):
     two more changesets for tenant T (r114) and two for tenant O (o114), each with a message, source, correlation
     id and idempotency key, through v4.5.1's public `engine.ledger.commit`.
  4. The pin's `IRISGraphEngine(..., schema_prefix="RAG").initialize_schema()` (dry run first), as the fixture does.
  5. The pin's public erase-then-redact for tenant T: `delete_nodes_by_prefix("r114:")`, then
     `ledger.redact(None, prefix="r114", separator=":")`.
  6. SC-001-style scans for T's and O's strings: every ^IVG.Ledger subscript and value, every row of every
     ledger_* table in the namespace (any schema), and the storage globals of those tables' classes.

NS must not exist beforehand (the probe refuses rather than let `build` drop it). NS is left in place afterwards.
Connections: one at a time from this process, plus the fixture's own children (one each). Nothing else is
compiled; no product file is touched. Output: $RUN_DIR/fc1306/probe.json.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from iris_conn import Conn, version  # noqa: E402

sys.path.append(str(REPO / "scripts" / "fixtures"))
import build_release_namespace as brn  # noqa: E402  (the pinned fixture, imported unmodified)

from iris_vector_graph import IRISGraphEngine  # noqa: E402  (the pin)

NS = os.environ.get("FC1306_NS", "IVG262FC1306")
SCHEMA = "RAG"
TAG = "v4.5.1"
OUT = Path(os.environ["RUN_DIR"]) / "fc1306"
OUT.mkdir(parents=True, exist_ok=True)
RESULT = OUT / "probe.json"

#: Tenant T (the redaction target): its ids, its label/type, the fixture's two messages, and every fc1306T- string
#: (messages, sources, correlation ids, idempotency keys, property values). Tenant O must stay.
T_TOKENS = ["r114:a", "r114:b", "r114:c", "R114", "fc1306T-", "two nodes and a relationship", "a property"]
O_TOKENS = ["o114:a", "o114:b", "O114", "fc1306O-"]
META = ("message", "source", "correlation_id", "idempotency_key")

res: dict = {"namespace": NS, "schema": SCHEMA, "tag": TAG, "phases": {}}


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save() -> None:
    RESULT.write_text(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")


def phase(name: str, fn):
    t0 = time.time()
    rec = {"start_utc": utc()}
    try:
        rec["value"] = fn()
        rec["ok"] = True
    except Exception as exc:  # the outcome is data
        rec["ok"] = False
        rec["error_type"] = type(exc).__name__
        rec["error"] = str(exc)[-4000:]
        rec["traceback"] = traceback.format_exc()[-4000:]
    rec["seconds"] = round(time.time() - t0, 2)
    res["phases"][name] = rec
    print(f"[{utc()}] {name}: {'ok' if rec['ok'] else 'FAILED ' + rec.get('error', '')[:300]}", flush=True)
    save()
    return rec


# ------------------------------------------------------------------------------------------------------------ helpers

def ledger_tables(c: Conn) -> list:
    rows = c.sql("SELECT TABLE_SCHEMA, TABLE_NAME, CLASSNAME FROM INFORMATION_SCHEMA.TABLES "
                 "WHERE LOWER(TABLE_NAME) LIKE 'ledger%'")
    return sorted([str(s), str(t), str(k)] for s, t, k in rows)


def storage_globals(c: Conn, classname: str) -> list:
    rows = c.sql("SELECT DataLocation, IndexLocation, StreamLocation FROM %Dictionary.CompiledStorage "
                 "WHERE parent = ?", classname)
    return sorted({str(g) for r in rows for g in r if g})


def rev_rows(c: Conn, schema: str) -> list:
    cols = "seq, kind, actor, op_count, message, source, correlation_id, idempotency_key"
    return [[None if v is None else str(v) for v in r]
            for r in c.sql(f"SELECT {cols} FROM {schema}.ledger_revisions ORDER BY seq")]


def content_counts(c: Conn, prefix: str) -> dict:
    p = prefix + "%"
    out = {}
    for schema in ("Graph_KG", SCHEMA):
        d = {}
        for table, where in (("nodes", "node_id LIKE ?"), ("rdf_labels", "s LIKE ?"), ("rdf_props", "s LIKE ?"),
                             ("rdf_edges", "s LIKE ? OR o_id LIKE ?")):
            try:
                args = (p, p) if "OR" in where else (p,)
                d[table] = c.sql(f"SELECT COUNT(*) FROM {schema}.{table} WHERE {where}", *args)[0][0]
            except Exception as exc:
                d[table] = f"error: {str(exc)[:160]}"
        out[schema] = d
    return out


def walk_global(o, gname: str, subs=(), out=None, limit=500000):
    """Every (subscripts, value bytes) node of a global, depth first (as followup/probes.py)."""
    out = [] if out is None else out
    d = o.isDefined(gname, *subs)
    if d in (1, 11):
        try:
            v = o.getBytes(gname, *subs)
        except Exception:
            v = str(o.get(gname, *subs)).encode()
        out.append((list(subs), v or b""))
    if d in (10, 11) or (not subs and d == 0):
        for k, _ in o.iterator(gname, *subs).items():
            if len(out) >= limit:
                break
            walk_global(o, gname, subs + (k,), out, limit)
    return out


def scan_global(c: Conn, gname: str, tokens) -> dict:
    hits = {t: [] for t in tokens}
    nodes = walk_global(c.o, gname)
    for subs, v in nodes:
        text = " ".join(str(s) for s in subs).encode(errors="replace") + b" " + v
        for t in tokens:
            if t.encode() in text:
                hits[t].append([str(s) for s in subs][:4])
    return {"nodes": len(nodes), "hits": {t: {"count": len(h), "first": h[:6]} for t, h in hits.items()}}


def scan_table(c: Conn, schema: str, table: str, tokens) -> dict:
    rows = c.sql(f'SELECT * FROM "{schema}"."{table}"')
    hits = {t: 0 for t in tokens}
    for row in rows:
        s = " ".join("" if x is None else str(x) for x in row)
        for t in tokens:
            if t in s:
                hits[t] += 1
    return {"rows": len(rows), "hits": hits}


def scan_all(c: Conn) -> dict:
    tokens = T_TOKENS + O_TOKENS
    out = {"^IVG.Ledger": scan_global(c, "^IVG.Ledger", tokens), "tables": {}, "storage_globals": {}}
    for schema, table, classname in ledger_tables(c):
        key = f"{schema}.{table}"
        try:
            out["tables"][key] = scan_table(c, schema, table, tokens)
        except Exception as exc:
            out["tables"][key] = {"error": str(exc)[:300]}
        try:
            for g in storage_globals(c, classname):
                gname = g if g.startswith("^") else "^" + g
                out["storage_globals"][f"{gname} ({classname})"] = scan_global(c, gname, tokens)
        except Exception as exc:
            out["storage_globals"][f"? ({classname})"] = {"error": str(exc)[:300]}
    # the 4.5.1 class's storage, by its documented name, even if no table projects it any more (migration step 4)
    for g in ("^Graph.KG.LedgerRevisionD", "^Graph.KG.LedgerStatsD"):
        if not any(k.startswith(g + " ") for k in out["storage_globals"]):
            out["storage_globals"][f"{g} (by name)"] = scan_global(c, g, tokens)
    return out


def t_hits(scan: dict) -> dict:
    """Where tenant T's strings are: {location: {token: count}} (non-zero only)."""
    where = {}

    def add(loc, hits):
        nz = {t: (h["count"] if isinstance(h, dict) else h) for t, h in hits.items() if t in T_TOKENS}
        nz = {t: n for t, n in nz.items() if n}
        if nz:
            where[loc] = nz

    add("^IVG.Ledger", scan["^IVG.Ledger"]["hits"])
    for k, v in scan["tables"].items():
        if "hits" in v:
            add(k, v["hits"])
    for k, v in scan["storage_globals"].items():
        if "hits" in v:
            add(k, v["hits"])
    return where


def receipt_dict(r) -> dict:
    d = {k: getattr(r, k, None) for k in ("complete", "target_sha256", "revision_seqs", "records_tombstoned",
                                           "metadata_cleared", "idempotency_keys_removed", "statements_removed",
                                           "unattributed_records", "batches", "out_of_reach")}
    d["redaction_seq"] = r.redaction.seq if getattr(r, "redaction", None) else None
    return d


def verify(engine) -> dict:
    rep = engine.ledger.verify()
    return {"result": rep.result, "differences": [str(x)[:300] for x in (rep.differences or [])][:10]}


# --------------------------------------------------------------------------------------------------------------- main

def main() -> int:
    res["started_utc"] = utc()
    res["python"] = sys.executable

    # 0. NS must not exist: `build` drops an existing one first, and nothing here may drop anything.
    def precheck():
        c = Conn("%SYS")
        try:
            return {"exists": int(c.call("%SYS.Namespace", "Exists", NS)), "iris": version(c)}
        finally:
            c.close()

    pre = phase("0_precheck_namespace_absent", precheck)
    if not pre["ok"] or pre["value"]["exists"]:
        res["verdict"] = {"result": "incomplete", "why": "precheck failed or namespace exists; nothing done"}
        save()
        return 2

    # 1-3. the 4.5.1 namespace, through the fixture's functions and the release's own ledger
    res["namespace_created_utc_not_before"] = utc()
    b = phase("1_fixture_build_v451", lambda: brn.build(TAG, NS, schema_prefix=SCHEMA))
    if not b["ok"]:
        res["verdict"] = {"result": "blocked", "why": "fixture build failed", "error": b.get("error")}
        save()
        return 3
    lc = phase("2_fixture_run_ledger_commits", lambda: brn.run_ledger_commits(TAG, NS, SCHEMA))

    def two_tenants():
        tree = brn.release_worktree(TAG)
        env = dict(os.environ, PYTHONPATH=str(tree), IVG_BUILD_SCHEMA_PREFIX=SCHEMA)
        args = [sys.executable, str(HERE / "ledger451_child.py"), TAG, NS]
        out = subprocess.run(args, env=env, capture_output=True, text=True, timeout=600, cwd=str(tree))
        if out.returncode != 0:
            raise RuntimeError(f"child failed ({out.returncode}):\n{out.stderr[-3000:]}")
        return brn.parse_result(out.stdout)

    tt = phase("3_v451_two_tenant_commits", two_tenants)
    if not (lc["ok"] and tt["ok"]):
        res["verdict"] = {"result": "blocked", "why": "4.5.1 ledger commits failed"}
        save()
        return 3

    c = Conn(NS)
    try:
        def where_db():
            return {"global_dest": str(c.call("%SYS.Namespace", "GetGlobalDest", NS, "")),
                    "routine_dest": str(c.call("%SYS.Namespace", "GetRoutineDest", NS, ""))}

        phase("4a_namespace_database", where_db)
        phase("4b_before_upgrade", lambda: {
            "ledger_tables": ledger_tables(c),
            "graph_kg_ledger_revisions": rev_rows(c, "Graph_KG"),
            "content_r114": content_counts(c, "r114:"), "content_o114": content_counts(c, "o114:"),
            "scan": scan_all(c),
        })

        # 4. the pin's setup, as the fixture runs it
        engine = IRISGraphEngine(c.conn, embedding_dimension=8, namespace=NS, schema_prefix=SCHEMA,
                                 native_cypher=False)
        keep = ("schema", "ledger_history_copied", "objectscript_failed", "objectscript_skipped", "warnings")

        def setup(dry):
            st = engine.initialize_schema(dry_run=dry)
            return {k: st.get(k) for k in keep} | {"keys": sorted(st)}

        phase("5a_pin_setup_dry_run", lambda: setup(True))
        up = phase("5b_pin_setup", lambda: setup(False))
        if not up["ok"]:
            res["verdict"] = {"result": "blocked", "why": "pin initialize_schema failed", "error": up.get("error")}
            return 3

        phase("6_after_upgrade", lambda: {
            "ledger_tables": ledger_tables(c),
            "graph_kg_ledger_revisions": rev_rows(c, "Graph_KG"),
            "schema_ledger_revisions": rev_rows(c, SCHEMA),
            "head_seq": engine.ledger.head().seq,
            "verify": verify(engine),
            "content_r114": content_counts(c, "r114:"),
            "scan": scan_all(c),
        })

        # 5. erase then redact tenant T through the pin's public API
        er = phase("7_erase_delete_nodes_by_prefix", lambda: {
            "removed": engine.delete_nodes_by_prefix("r114:"),
            "content_r114_after": content_counts(c, "r114:"),
            "content_o114_after": content_counts(c, "o114:"),
        })
        rd = phase("8_redact", lambda: receipt_dict(engine.ledger.redact(None, prefix="r114", separator=":")))

        # 6. scans after
        after = phase("9_after_redaction", lambda: {
            "verify": verify(engine),
            "graph_kg_ledger_revisions": rev_rows(c, "Graph_KG"),
            "schema_ledger_revisions": rev_rows(c, SCHEMA),
            "history": [[r.seq, r.kind, r.message, r.correlation_id] for r in
                        engine.ledger.history(limit=50).revisions],
            "scan": scan_all(c),
        })
    finally:
        c.close()

    # verdict
    v: dict = {}
    if not (er["ok"] and rd["ok"] and after["ok"]):
        v = {"result": "incomplete", "why": "erase, redact or the after-scan failed"}
    else:
        rc = rd["value"]
        scan = after["value"]["scan"]
        where = t_hits(scan)
        seqs = set(rc.get("revision_seqs") or [])
        legacy = {int(r[0]): r for r in after["value"]["graph_kg_ledger_revisions"]}
        schema_rows = {int(r[0]): r for r in after["value"]["schema_ledger_revisions"]}
        per_seq = {s: {"Graph_KG": dict(zip(META, (legacy.get(s) or [None] * 8)[4:])),
                       SCHEMA: dict(zip(META, (schema_rows.get(s) or [None] * 8)[4:]))} for s in sorted(seqs)}
        sc001_literal = {k: n for k, n in where.items() if k == "^IVG.Ledger" or k.startswith("Graph_KG.ledger")}
        tables_any_schema = {k: n for k, n in where.items() if k == "^IVG.Ledger" or ".ledger" in k.split(" ")[0]}
        before_o = {int(r[0]): r for r in res["phases"]["6_after_upgrade"]["value"]["schema_ledger_revisions"]
                    if r[2] == "o114"}
        o_unchanged = all(schema_rows.get(s) == r for s, r in before_o.items())
        v = {
            "redaction_complete": rc.get("complete"),
            "receipt_revision_seqs": sorted(seqs),
            "receipt_metadata_cleared": rc.get("metadata_cleared"),
            "receipt_out_of_reach": rc.get("out_of_reach"),
            "verify_after": after["value"]["verify"],
            "t_strings_found": where,
            "sc001_literal_scope_hits": sc001_literal,
            "ledger_tables_and_ivg_ledger_hits": tables_any_schema,
            "redacted_seq_metadata_by_schema": per_seq,
            "o_tenant_rows_unchanged_in_schema": o_unchanged,
            "result": ("fail" if tables_any_schema else "pass") if rc.get("complete") else "incomplete",
        }
    res["verdict"] = v
    res["finished_utc"] = utc()
    save()
    print(json.dumps(v, indent=1, sort_keys=True, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
