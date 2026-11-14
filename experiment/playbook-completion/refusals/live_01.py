#!/usr/bin/env python3
"""Module 01 (install and schema): live probes of the stated refusals (INS kind X) in namespace AUDITE.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1200 \
        python experiment/playbook-completion/refusals/live_01.py [case ...]

AUDITE is deployed by the pin's own initialize_schema and records Graph_KG as its IVG Schema (^IVG.Deploy("schema")).
Every probe here triggers a refusal that must come before anything is written, so nothing the pin deployed is changed:
no class is compiled, no table or record is touched (the journal window of rxlib proves it per case). Refusals whose
trigger needs a namespace without a record, a least-privilege user, a v3.2.0 table or a failing DDL are not probed
here (see refusals/audit/01.json). Two kinds of case:
  entry point  - the refused call goes through the product's public entry point (IRISGraphEngine(...),
                 initialize_schema, deploy_packaged_classes, remove_legacy_objects, upgrade_to_4_0_0, an SQL function);
  function     - the implementing function is called directly (case name says "function:"); corroboration only.
Results: $RUN_DIR/refusals/01/results.json. Scratch ids prefixed rx01.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rxlib import (Lane, raises, returns, run_cases, engine, tlevel, open_caller_txn,  # noqa: E402
                   rollback_all, NS)

OTHER = "RXOTHER"   # a valid schema name that is not the one AUDITE records


def ivg_engine(L, **kw):
    from iris_vector_graph.engine import IRISGraphEngine
    return IRISGraphEngine(L.c.conn, namespace=NS, **kw)


# ---------------------------------------------------------------------------------------------- INS-X1 setup
def c_x1_2(L):
    """INS-X1.2: setup without a vector width refuses (ValueError naming embedding_dimension) before any write."""
    eng = ivg_engine(L, embedding_dimension=None)
    dim = getattr(eng, "embedding_dimension", "absent")
    L.note("INS-X1.2", "setup: engine built with embedding_dimension=None", embedding_dimension=dim)
    if dim is not None:
        L.note("INS-X1.2", "skipped: the engine inferred a width, so initialize_schema would run", dim=dim)
        return
    L.refusal("INS-X1.2", "initialize_schema() with no vector width -> ValueError naming embedding_dimension",
              lambda: eng.initialize_schema(), raises("ValueError", match="embedding_dimension"),
              entry="IRISGraphEngine.initialize_schema")


def c_x1_3(L):
    """INS-X1.3: setup and its preview refuse while the caller has an open transaction."""
    eng = ivg_engine(L, embedding_dimension=4)
    for dry in (False, True):
        lvl = open_caller_txn(L.c.conn)
        L.refusal("INS-X1.3", f"initialize_schema(dry_run={dry}) with a caller transaction open (TLEVEL {lvl}) "
                              "-> CallerTransactionOpenError",
                  lambda: eng.initialize_schema(dry_run=dry),
                  raises("CallerTransactionOpenError", match=r"initialize_schema"),
                  entry="IRISGraphEngine.initialize_schema",
                  after=lambda: {"tlevel_still": tlevel(L.c.conn)}, keep_txn=True)
        rollback_all(L.c.conn)


# ---------------------------------------------------------------------------------------------- INS-X2 schema names
BAD_NAMES = [("", "it is empty"), ("1bad", "must start with a letter"), ("bad-name", "must start with a letter"),
             ("%Bad", "reserved for InterSystems"), ("SQLUser", "SQLUser is the default schema"),
             ("sqluser", "SQLUser is the default schema")]
UNDER_CODE = ["IVG", "ivgc", "IVG_Sub", "Graph_KG_Sub", "IVGC_x"]


def c_x2_3(L):
    """INS-X2.3: a bad schema name is refused before any database call, naming the rule."""
    for name, rule in BAD_NAMES:
        L.refusal("INS-X2.3", f"IRISGraphEngine(schema_prefix={name!r}) -> ValueError ({rule})",
                  lambda: ivg_engine(L, embedding_dimension=4, schema_prefix=name),
                  raises("ValueError", match=r"not a valid IVG Schema name: .*" + rule.split()[0]),
                  entry="IRISGraphEngine.__init__ (resolve_schema_name)")


def c_x2_4(L):
    """INS-X2.4: a name whose class package is or lies under Graph.KG / IVG / IVGC is refused; Graph_KG allowed."""
    for name in UNDER_CODE:
        L.refusal("INS-X2.4", f"IRISGraphEngine(schema_prefix={name!r}) -> ValueError (under an IVG code package)",
                  lambda: ivg_engine(L, embedding_dimension=4, schema_prefix=name),
                  raises("ValueError", match=r"is, or is under, IVG's code package"),
                  entry="IRISGraphEngine.__init__ (resolve_schema_name)")
    from iris_vector_graph.schema_name import validate_schema_name
    L.note("INS-X2.4", "Graph_KG itself is allowed", graph_kg=validate_schema_name("graph_kg"))


def c_x2_6(L):
    """INS-X2.6 (function): refuse_package_clash on a package holding classes IVG did not make (read-only)."""
    from iris_vector_graph.schema_name import refuse_package_clash
    L.refusal("INS-X2.6", "function: refuse_package_clash(conn, 'INFORMATION_SCHEMA') -> IVGSchemaError",
              lambda: refuse_package_clash(L.c.conn, "INFORMATION_SCHEMA"),
              raises("IVGSchemaError", match=r"already holds classes IVG did not create.*Nothing was created"),
              entry="iris_vector_graph.schema_name.refuse_package_clash (called by setup at _engine/schema.py:2243)")
    # the setup entry point on AUDITE meets the record check first (FR-006), so it cannot reach the clash check here
    eng = ivg_engine(L, embedding_dimension=4, schema_prefix="INFORMATION_SCHEMA")
    L.refusal("INS-X2.6", "entry: initialize_schema(dry_run=True) on INFORMATION_SCHEMA meets the record check first",
              lambda: eng.initialize_schema(dry_run=True),
              raises("IVGSchemaError", match=r"records Graph_KG as its IVG Schema"),
              entry="IRISGraphEngine.initialize_schema")


# ---------------------------------------------------------------------------------------------- record mismatch
def c_x2_12(L):
    """INS-X2.12: setup (and its preview) and a deploy are refused when the record names another schema."""
    holder = {}
    L.refusal("INS-X3.2", f"construct IRISGraphEngine(schema_prefix={OTHER!r}) on a namespace recording Graph_KG: "
                          "no exception, nothing written",
              lambda: holder.setdefault("eng", ivg_engine(L, embedding_dimension=4, schema_prefix=OTHER)) and None,
              returns(lambda r: True, "construction returns (the refusal is pending)"),
              entry="IRISGraphEngine.__init__")
    eng = holder["eng"]
    for dry in (False, True):
        L.refusal("INS-X2.12", f"initialize_schema(dry_run={dry}) with schema_prefix={OTHER} -> IVGSchemaError naming both",
                  lambda: eng.initialize_schema(dry_run=dry),
                  raises("IVGSchemaError", match=rf"records Graph_KG as its IVG Schema, and this engine asks for {OTHER}"),
                  entry="IRISGraphEngine.initialize_schema")
    from iris_vector_graph._engine.class_deploy import deploy_packaged_classes
    L.refusal("INS-X2.12", f"deploy_packaged_classes(conn, schema={OTHER!r}) -> IVGSchemaError before loading",
              lambda: deploy_packaged_classes(L.c.conn, schema=OTHER),
              raises("IVGSchemaError", match=rf"records Graph_KG as its IVG Schema, and this engine asks for {OTHER}"),
              entry="iris_vector_graph._engine.class_deploy.deploy_packaged_classes")
    from iris_vector_graph.schema import GraphSchema

    def deploy_cls():
        cur = L.c.conn.cursor()
        try:
            return GraphSchema.deploy_objectscript_classes(cur, None, conn=L.c.conn, schema=OTHER)
        finally:
            cur.close()
    L.refusal("INS-X2.12", f"GraphSchema.deploy_objectscript_classes(schema={OTHER!r}) -> IVGSchemaError before "
                           "the rescue probe or any load",
              deploy_cls,
              raises("IVGSchemaError", match=rf"records Graph_KG as its IVG Schema, and this engine asks for {OTHER}"),
              entry="GraphSchema.deploy_objectscript_classes")


def _public_functions(obj, exempt):
    names, skipped = [], []
    for name in dir(type(obj)):
        if name.startswith("_") or name in exempt:
            continue
        raw = inspect.getattr_static(type(obj), name, None)
        if inspect.isfunction(raw):
            names.append(name)
        elif callable(raw) or isinstance(raw, (classmethod, staticmethod)):
            skipped.append(name)
    return names, skipped


def c_x3_2(L):
    """INS-X3.2: on a namespace recording another schema every public call of the engine is refused (both schemas
    named) and nothing is written. Mechanical: every public function of the engine class (the guard's own criterion,
    schema_name.py:332-347) and of its sub-engines and ledger client, each called with no arguments."""
    from iris_vector_graph.schema_name import EXEMPT_METHODS
    eng = ivg_engine(L, embedding_dimension=4, schema_prefix=OTHER)
    names, skipped = _public_functions(eng, EXEMPT_METHODS)

    def call_all(objs):
        out = {}
        for label, obj, meths in objs:
            for m in meths:
                try:
                    r = getattr(obj, m)()
                    out[f"{label}.{m}"] = {"refused": False, "returned": repr(r)[:200]}
                except Exception as e:  # noqa: BLE001
                    msg = str(e)
                    out[f"{label}.{m}"] = {"refused": type(e).__name__ == "IVGSchemaError"
                                           and "Graph_KG" in msg and OTHER in msg,
                                           "type": type(e).__name__, "message": msg[:160]}
        return out

    def ok(r):
        return bool(r) and all(v["refused"] for v in r.values())

    holder = {}
    L.refusal("INS-X3.2", f"every public engine method ({len(names)}) on schema_prefix={OTHER} -> IVGSchemaError "
                          "naming both schemas",
              lambda: holder.setdefault("eng", call_all([("engine", eng, names)])),
              returns(ok, "every call raised IVGSchemaError naming Graph_KG and RXOTHER"),
              entry="IRISGraphEngine public methods (guard_methods)",
              after=lambda: {"methods": len(names), "not_called_non_functions": skipped,
                             "not_refused": sorted(k for k, v in holder.get("eng", {}).items() if not v["refused"])})
    subs = []
    for label in ("graph", "cypher", "temporal", "algorithms"):
        sub = getattr(eng, label, None)
        if sub is not None:
            subs.append((label, sub, _public_functions(sub, ())[0]))
    led = eng.ledger
    subs.append(("ledger", led, [m for m in ("meta", "head", "stats", "history", "enable", "disable",
                                             "redaction_in_progress", "verify")]))
    holder2 = {}
    L.refusal("INS-X3.2", f"every public sub-engine and ledger method on schema_prefix={OTHER} (no arguments) -> "
                          "IVGSchemaError naming both schemas",
              lambda: holder2.setdefault("r", call_all(subs)),
              returns(ok, "every call raised IVGSchemaError naming Graph_KG and RXOTHER"),
              entry="engine.graph/cypher/temporal/algorithms/ledger",
              after=lambda: {"calls": len(holder2.get("r", {})),
                             "not_refused": {k: v for k, v in holder2.get("r", {}).items() if not v["refused"]}})


# ---------------------------------------------------------------------------------------------- grants, ledger copy
def c_x6_2(L):
    """INS-X6.2 (function): copy_grants refuses a grant whose grantee has an odd name before granting."""
    from iris_vector_graph._engine import legacy
    item = {"sql_name": "SQLUser.rx01_view", "replacement": "rx01_fn", "class_name": "User.rx01",
            "grants": [{"subject": "rx01 bad;name", "privilege": "EXECUTE", "with_grant": False}]}
    L.refusal("INS-X6.2", "function: legacy.copy_grants with grantee 'rx01 bad;name' -> ValueError",
              lambda: legacy.copy_grants(L.c.conn, [item], "Graph_KG", dry_run=False),
              raises("ValueError", match=r"refusing to copy a grant with an unexpected name"),
              entry="iris_vector_graph._engine.legacy.copy_grants")


def c_x6_13(L):
    """INS-X6.13 (function): a ledger table missing after setup raises and copies no rows (copy_ledger_history)."""
    from iris_vector_graph._engine import legacy
    L.reset(ledger=True)   # a genesis row in Graph_KG.ledger_revisions (outside the window)
    rows = int(L.c.sql("SELECT COUNT(*) FROM Graph_KG.ledger_revisions")[0][0])
    L.note("INS-X6.13", "setup: Graph_KG.ledger_revisions rows", rows=rows)
    L.refusal("INS-X6.13", "function: copy_ledger_history(conn, 'RXNOSCHEMA', dry_run=False) with no target table "
                           "-> RuntimeError, nothing copied",
              lambda: legacy.copy_ledger_history(L.c.conn, "RXNOSCHEMA", dry_run=False),
              raises("RuntimeError", match=r"does not exist after setup.*was not copied"),
              entry="iris_vector_graph._engine.legacy.copy_ledger_history (setup: _engine/schema.py)")
    L.reset()


# ---------------------------------------------------------------------------------------------- legacy removal
def c_x7_7(L):
    """INS-X7.7: legacy removal (dry_run=False) refuses a caller's open transaction; the listing is not refused."""
    eng = ivg_engine(L, embedding_dimension=4)
    lvl = open_caller_txn(L.c.conn)
    L.refusal("INS-X7.7", f"remove_legacy_objects(dry_run=False) with a caller transaction open (TLEVEL {lvl}) -> "
                          "CallerTransactionOpenError",
              lambda: eng.remove_legacy_objects(dry_run=False),
              raises("CallerTransactionOpenError", match=r"remove_legacy_objects"),
              entry="IRISGraphEngine.remove_legacy_objects", keep_txn=True)
    L.refusal("INS-X7.7", "remove_legacy_objects(dry_run=True) in the same caller transaction: listed, not refused",
              lambda: eng.remove_legacy_objects(dry_run=True),
              returns(lambda r: isinstance(r, list), "a list (the listing is not refused)"),
              entry="IRISGraphEngine.remove_legacy_objects", keep_txn=True)
    _not_refused(L)
    rollback_all(L.c.conn)


# ---------------------------------------------------------------------------------------------- migrations
def c_x9_4_91(L):
    """INS-X9.4.91: the re-key refuses an old key name that is not plain and hands back no statements."""
    from iris_vector_graph.schema import GraphSchema
    L.refusal("INS-X9.4.91", "GraphSchema.get_graph_scope_migration_sql(legacy_node_keys=['bad; DROP']) -> ValueError",
              lambda: GraphSchema.get_graph_scope_migration_sql(legacy_node_keys=["bad; DROP"]),
              raises("ValueError", match=r"not a constraint name this migration can drop"),
              entry="GraphSchema.get_graph_scope_migration_sql")


def c_x9_5(L):
    """INS-X9.5: a step name that is not one of the four is refused before any step runs."""
    from iris_vector_graph.migrations import upgrade_to_4_0_0
    L.refusal("INS-X9.5", "upgrade_to_4_0_0(steps=['rx01_bogus'], dry_run=False) -> ValueError naming the known steps",
              lambda: upgrade_to_4_0_0(L.c.conn, steps=["rx01_bogus"], dry_run=False),
              raises("ValueError", match=r"not upgrade steps: rx01_bogus\. Known steps"),
              entry="iris_vector_graph.migrations.upgrade_to_4_0_0")
    L.refusal("INS-X9.5", "upgrade_to_4_0_0(steps=['rx01_bogus', <a real step>], dry_run=True) -> ValueError before "
                          "the real step",
              lambda: upgrade_to_4_0_0(L.c.conn, steps=["rx01_bogus", _first_step()], dry_run=True),
              raises("ValueError", match=r"not upgrade steps: rx01_bogus"),
              entry="iris_vector_graph.migrations.upgrade_to_4_0_0")


def _first_step():
    from iris_vector_graph.migrations.upgrade import UPGRADE_STEPS
    return UPGRADE_STEPS[0]


def c_x9_8(L):
    """INS-X9.8: the upgrade refuses a caller's open transaction; a preview does not refuse."""
    from iris_vector_graph.migrations import upgrade_to_4_0_0
    lvl = open_caller_txn(L.c.conn)
    L.refusal("INS-X9.8", f"upgrade_to_4_0_0(dry_run=False) with a caller transaction open (TLEVEL {lvl}) -> "
                          "CallerTransactionOpenError",
              lambda: upgrade_to_4_0_0(L.c.conn, dry_run=False),
              raises("CallerTransactionOpenError", match=r"upgrade_to_4_0_0"),
              entry="iris_vector_graph.migrations.upgrade_to_4_0_0", keep_txn=True)
    L.refusal("INS-X9.8", "upgrade_to_4_0_0(dry_run=True) in the same caller transaction: a preview, not refused",
              lambda: type(upgrade_to_4_0_0(L.c.conn, dry_run=True)).__name__,
              returns(lambda r: r == "UpgradeReport", "an UpgradeReport (the preview is not refused)"),
              entry="iris_vector_graph.migrations.upgrade_to_4_0_0", keep_txn=True,
              after=lambda: {"tlevel_still": tlevel(L.c.conn)})
    _not_refused(L)
    rollback_all(L.c.conn)


def c_x9_13(L):
    """INS-X9.13: a statement declared with an unknown expected outcome is refused."""
    from iris_vector_graph.migrations.statements import Statement
    L.refusal("INS-X9.13", "Statement(expects='rx01-bogus') -> ValueError",
              lambda: Statement(name="rx01", sql="SELECT 1", params_doc=(), expects="rx01-bogus"),
              raises("ValueError", match=r"expects must be one of"),
              entry="iris_vector_graph.migrations.statements.Statement")


def _not_refused(L):
    """For a case whose statement says the call is NOT refused (a preview, a listing): it holds when the call answers
    and the journal shows no net change; a lone transaction marker in the caller's own open transaction (no SET/KILL
    with a net effect) is not a change. The rxlib verdict and journal counts stay in the record."""
    rec = L.cases[-1]
    j = rec["journal"]
    if rec["refused_as_stated"] and j["net_changed_nodes"] == 0 and not j["changed_outside_allowed"]:
        rec["rxlib_outcome"] = rec["outcome"]
        rec["outcome"] = "holds-live"
        rec["why"] += f" (not refused, as stated; journal {j['records']} record(s), 0 net changes)"


class _CursorSpy:
    """Delegates to a real connection and counts cursor() calls (a statement sent needs a cursor)."""

    def __init__(self, conn):
        self._conn = conn
        self.cursors = 0

    def cursor(self):
        self.cursors += 1
        return self._conn.cursor()

    def __getattr__(self, k):
        return getattr(self._conn, k)


def c_x9_14(L):
    """INS-X9.14: a run with the wrong number of inputs sends nothing (no cursor is opened)."""
    from iris_vector_graph.migrations.statements import Statement, run_statement
    spy = _CursorSpy(L.c.conn)
    st = Statement(name="rx01_count", sql="SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?",
                   params_doc=("node_id",), expects="rows-selected")
    L.refusal("INS-X9.14", "run_statement(1 placeholder, 2 values) -> ValueError, no cursor opened",
              lambda: run_statement(spy, st, ["rx01:a", "rx01:b"]),
              raises("ValueError", match=r"takes 1 parameter\(s\).*got 2"),
              entry="iris_vector_graph.migrations.statements.run_statement",
              after=lambda: {"cursors_opened": spy.cursors})
    if L.cases[-1].get("observations", {}).get("cursors_opened"):
        L.cases[-1]["outcome"] = "not-refused-as-stated"
        L.cases[-1]["why"] += " (but a cursor was opened)"


# ---------------------------------------------------------------------------------------------- SqlPrivilege
FAKE_TABLE = "Graph_KG.rx01_no_such_table"


def c_x10_8(L):
    """INS-X10.8: a failed read inside a routine raises; it does not come back as an empty answer (RaiseIfRefused).
    The failed read here is a table that does not exist (SQLCODE -30); the -99 refusal needs a user without SELECT."""
    calls = {
        "CY_PROPS_MAP": ("SELECT Graph_KG.CY_PROPS_MAP(?, ?, ?)", ["rx01:a", FAKE_TABLE, ""]),
        "CY_VLP_OPT": ("SELECT Graph_KG.CY_VLP_OPT(?, ?, ?, ?, ?)", ['[{"t":"rx01:a"}]', 0, "", '["RX01"]', FAKE_TABLE]),
        "CY_VLP_CHAIN": ("SELECT Graph_KG.CY_VLP_CHAIN(?, ?, ?)", ['["1"]', "out", FAKE_TABLE]),
    }
    for fn, (sql, params) in calls.items():
        L.refusal("INS-X10.8", f"SQL {fn} reading a missing table -> SQL error naming the table, not an empty answer",
                  lambda: L.c.sql(sql, *params),
                  raises(match=r"reading " + FAKE_TABLE.replace(".", r"\.")),
                  entry=f"SQL function Graph_KG.{fn} (deployed by the pin's initialize_schema)")
        rollback_all(L.c.conn)
    from iris_vector_graph.schema_name import missing_privilege  # noqa: F401  (import check only)


CASES = [("x1_2", c_x1_2), ("x1_3", c_x1_3), ("x2_3", c_x2_3), ("x2_4", c_x2_4), ("x2_6", c_x2_6),
         ("x2_12", c_x2_12), ("x3_2", c_x3_2), ("x6_2", c_x6_2), ("x6_13", c_x6_13), ("x7_7", c_x7_7),
         ("x9_4_91", c_x9_4_91), ("x9_5", c_x9_5), ("x9_8", c_x9_8), ("x9_13", c_x9_13), ("x9_14", c_x9_14),
         ("x10_8", c_x10_8)]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--out=")]
    out = next((a[6:] for a in sys.argv[1:] if a.startswith("--out=")), None)
    only = args or None
    with Lane("01") as L:
        L.reset()
        L.control()
        L.note("-", "AUDITE record", record=str(L.c.o.get("IVG.Deploy", "schema")))
        run_cases(L, CASES, only)
        L.reset()
        L.note("-", "AUDITE record after", record=str(L.c.o.get("IVG.Deploy", "schema")))
        L.save(out or ("results.json" if not only else "results-partial.json"))


if __name__ == "__main__":
    main()
