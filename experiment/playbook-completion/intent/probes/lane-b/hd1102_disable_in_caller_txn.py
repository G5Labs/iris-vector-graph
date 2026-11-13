"""HD-1102 probe: ledger.disable() / set_strict() inside a caller's open transaction, then ROLLBACK.

Run under the EXCLUSIVE lane lock. Two engine topologies on the same identity-checked endpoint:
  plain   - engine built on the caller's connection: Native API on the caller's own server process
  native2 - engine whose Native API connection is a second process (the from_connect topology, engine.py:1922-1942;
            emulated by giving the engine an identity-checked second Conn as its `_native_conn`)
The caller transaction is START TRANSACTION plus one INSERT of a scratch node row (ib3_txn), so $TLEVEL > 0.

Discriminates HD-1102's alternatives:
  (a) refuse inside a caller transaction (as enable/redact since 4.7.0)  -> LedgerTransactionOpenError, state unchanged
  (b) join the caller transaction                                       -> rollback restores enabled / strict on BOTH
  (c) as built: no refusal; plain engine joins (rollback undoes), native2 commits apart (rollback leaves it)
Maintainer principle (commit 0cf1524f, 4.7.0 row 3b; CHANGELOG.md:37): IVG calls "join the caller's transaction or
refuse it"; enable()/redact() refuse on every engine.
"""
import time

from _ib3_common import Conn, engine_on, engine_native_elsewhere, meta, out, purge_ledger, cleanup, foreign_rows

from iris_vector_graph._write_txn import caller_transaction_level


def caller_txn(e):
    cur = e.conn.cursor()
    cur.execute("START TRANSACTION")
    cur.execute("INSERT INTO Graph_KG.nodes (node_id, graph_id) VALUES ('ib3_txn', '')")
    cur.close()
    return caller_transaction_level(e.conn)


def rollback(e):
    cur = e.conn.cursor()
    cur.execute("ROLLBACK")
    cur.close()


def run(kind, e, observer):
    res = {}
    # --- disable() inside the caller transaction
    purge_ledger(observer)
    e.ledger.enable()
    lvl = caller_txn(e)
    try:
        e.ledger.enable()
        res["enable_in_txn"] = "no refusal (already enabled: idempotent branch)"
    except Exception as ex:  # noqa: BLE001
        res["enable_in_txn"] = f"{type(ex).__name__}"
    try:
        e.ledger.disable()
        res["disable_in_txn"] = "accepted"
    except Exception as ex:  # noqa: BLE001
        res["disable_in_txn"] = f"refused {type(ex).__name__}: {ex}"
    res["state_seen_by_other_process_inside_txn"] = meta(observer)["state"]
    rollback(e)
    res["caller_tlevel"] = lvl
    res["state_after_rollback"] = meta(observer)["state"]
    res["caller_row_after_rollback"] = observer.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'ib3_txn'")[0][0]

    # --- re-enable from a disabled ledger inside a caller transaction (control: the 4.7.0 refusal)
    if res["state_after_rollback"] == "disabled":
        lvl2 = caller_txn(e)
        try:
            e.ledger.enable()
            res["reenable_in_txn"] = "accepted"
        except Exception as ex:  # noqa: BLE001
            res["reenable_in_txn"] = f"refused {type(ex).__name__}"
        rollback(e)
        res["reenable_caller_tlevel"] = lvl2

    # --- set_strict(False) inside the caller transaction, strict was on
    purge_ledger(observer)
    e.ledger.enable(strict=True)
    caller_txn(e)
    try:
        e.ledger.set_strict(False)
        res["set_strict_in_txn"] = "accepted"
    except Exception as ex:  # noqa: BLE001
        res["set_strict_in_txn"] = f"refused {type(ex).__name__}: {ex}"
    res["guard_is_strict_inside_txn"] = e._ledger_guard.is_strict()  # caches the probe (TTL 5 s)
    rollback(e)
    res["strict_after_rollback"] = meta(observer)["strict"]
    # within the guard's 5 s TTL: does a guarded write pass on the cached (rolled-back) value?
    t0 = time.monotonic()
    try:
        ok = e.create_node("ib3_stale_guard")
        res["guarded_create_after_rollback"] = f"written={ok} after {time.monotonic() - t0:.2f}s (guard cache)"
    except Exception as ex:  # noqa: BLE001
        res["guarded_create_after_rollback"] = f"refused {type(ex).__name__}"
    for k, v in res.items():
        out(f"[{kind}] {k}", v)
    return res


def main():
    c1 = Conn("AUDITIB")
    c2 = Conn("AUDITIB")
    c3 = Conn("AUDITIB")
    try:
        out("pids caller/native2/observer", (c1.pid, c2.pid, c3.pid))
        out("foreign rows at start", foreign_rows(c3))
        cleanup(c3)
        plain = engine_on(c1)
        out("plain engine native pid", plain._iris_obj().classMethodValue("%SYSTEM.SYS", "ProcessID"))
        r_plain = run("plain", plain, c3)
        cleanup(c3)
        nat = engine_native_elsewhere(c1, c2)
        out("native2 engine native pid", nat._iris_obj().classMethodValue("%SYSTEM.SYS", "ProcessID"))
        r_nat = run("native2", nat, c3)

        a = all(str(r["disable_in_txn"]).startswith("refused") and str(r["set_strict_in_txn"]).startswith("refused")
                for r in (r_plain, r_nat))
        b = all(r["state_after_rollback"] == "enabled" and r["strict_after_rollback"] is True for r in (r_plain, r_nat))
        cc = (r_plain["state_after_rollback"] == "enabled" and r_nat["state_after_rollback"] == "disabled"
              and r_plain["strict_after_rollback"] is True and r_nat["strict_after_rollback"] is False)
        out("VERDICT alternative (a) refuse on every engine", a)
        out("VERDICT alternative (b) join on every engine", b)
        out("VERDICT alternative (c) as built: engine-dependent", cc)
        out("VERDICT 4.7.0 principle 'join or refuse' for native2 disable/set_strict",
            "holds" if (r_nat["state_after_rollback"] == "enabled" or str(r_nat["disable_in_txn"]).startswith("refused"))
            else "VIOLATED (committed outside the caller's transaction)")
    finally:
        try:
            cleanup(c3)
        finally:
            for c in (c1, c2, c3):
                c.close()


if __name__ == "__main__":
    main()
