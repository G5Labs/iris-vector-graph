#!/usr/bin/env python3
"""A qualifier record the redaction cannot attribute (model witness W4).

An edge written outside the ledger (engine.create_edge; LedgerGuard refuses it only in strict mode) is
later qualified through the ledger by tuple. LedgerApply.ResolveRef assigns it a statement
(flag assigned_stmt) and records only set_qual — no create_rel. Erasing the tenant removes the statement
entry; redaction then cannot find the statement's endpoints (Matches = -1).

Expected (spec 256 US1 / ADR-0013 / ledger.redact docstring: every record of the target becomes a
tombstone; nothing in the ledger holds the target's strings afterwards): the set_qual record is a
tombstone and the receipt reports no unattributed records.
"""
from redaction_common import connect, cs, engine, ensure_schema, ledger_records, reset, verdict


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    reset(eng, native)
    led = eng.ledger
    led.enable()
    c = cs("tU nodes", "tU|c", "tU-k", "tU-feed")
    c.create_node("tU|1"); c.create_node("tU|2")
    led.commit(c)
    eng.create_edge("tU|1", "R", "tU|2")
    c = cs("tU qualify", "tU|c2", None, "tU-feed")
    c.set_qualifier(("tU|1", "R", "tU|2", None), "note", "uSecretQualifier")
    led.commit(c)
    qual = {k: f for k, f in ledger_records(native).items() if f[0] == "set_qual"}
    eng.delete_nodes_by_prefix("tU|")
    r = led.redact(None, prefix="tU")
    after = ledger_records(native)
    leftover = {str(k): f for k, f in after.items() if f[0] != "redacted" and "uSecret" in str(f)}
    data = {"qualifier_records_before": {str(k): v for k, v in qual.items()}, "receipt": vars(r),
            "records_still_holding_target_text": leftover, "verify": led.verify().result}
    ok = not leftover and r.unattributed_records == 0
    reason = (f"receipt complete={r.complete} records_tombstoned={r.records_tombstoned} unattributed_records={r.unattributed_records}; "
              f"records still holding the qualifier value: {len(leftover)}")
    return verdict("redaction_unattributed_qualifier", ok, reason, data)


if __name__ == "__main__":
    raise SystemExit(main())
