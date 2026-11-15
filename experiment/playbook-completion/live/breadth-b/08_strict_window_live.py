#!/usr/bin/env python3
"""F-0801 / CYP-X7.2, two IRIS processes on AUDITB: a Cypher write inside the guard's 5 s cache after another process
turned ledger strict mode on.

    bash experiment/playbook-completion/tools/locks.sh iris python experiment/playbook-completion/live/breadth-b/08_strict_window_live.py

Process A (engine A, its own connection) writes once, so its LedgerGuard caches the ledger's state. Process B (a second
connection, a second IRIS server process) enables the ledger and sets strict mode. A then writes again within the TTL
(guard.TTL_SECONDS = 5.0): the oracle (CYP-X7.2; specs/213-graph-revision-ledger/contracts/ledger-api.md:82-92) says the
write is refused and changes nothing. After the TTL, A writes again (expected refused: the positive control showing
strict mode is effective once the cache expires). Ledger state is restored to what the script found (strict off; a
never-enabled or disabled ledger is left disabled, an enabled one enabled).
"""
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("c08", HERE / "08_common.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def main():
    R = {}
    with C.session08("08-strict-window", native_cypher=False) as s:
        found = C.ledger_meta(s)
        R["found_meta"] = found
        if found.get("strict"):
            R["skipped"] = "strict mode already on (another worker's state); not changed"
            print(C.write_log(s, R, name="08-strict-window"))
            return
        cB = C.conn_retry()
        s.extra_conns.append(cB)
        engB = s.engine_on(cB, native_cypher=False, embedding_dimension=4)
        R["pids"] = {"A": s.c.pid, "B": cB.pid}
        C.cleanup(s)
        # 1. A writes: its guard caches the current (not strict) state
        r0 = C.run(s, "CREATE (:B08G {id:'b08_g0'})")
        t_cache = time.monotonic()
        R["A_warm"] = {k: r0.get(k) for k in ("exc", "msg", "error")}
        head_before = None
        # 2. B turns strict mode on (enable + set_strict)
        try:
            if found.get("state") != "enabled":
                engB.ledger.enable()
            engB.ledger.set_strict(True)
            R["B_meta_after_strict"] = engB.ledger.meta()
            head_before = R["B_meta_after_strict"].get("head_seq")
        except Exception as e:  # noqa: BLE001
            R["B_error"] = f"{type(e).__name__}: {e}"
        # 3. A writes within the TTL
        within = time.monotonic() - t_cache
        cap = C.capture(s, lambda: s.eng.execute_cypher("CREATE (:B08G {id:'b08_g1'})"), pids={s.c.pid})
        g1 = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'b08_g1'")[0][0]
        meta_mid = engB.ledger.meta()
        R["A_within_ttl"] = {"seconds_since_cache": round(within, 3), "error": cap.error, "b08_g1_rows": g1,
                             "journal_stores": cap.stores(), "ledger_head_seq_after": meta_mid.get("head_seq"),
                             "ledger_head_seq_before": head_before}
        # 4. B's own (fresh) engine is refused at once
        rB = None
        try:
            engB.execute_cypher("CREATE (:B08G {id:'b08_gB'})")
            rB = "accepted"
        except Exception as e:  # noqa: BLE001
            rB = f"{type(e).__name__}: {str(e)[:200]}"
        R["B_fresh_engine_write"] = rB
        # 5. After the TTL, A is refused (positive control)
        time.sleep(max(0.0, 5.5 - (time.monotonic() - t_cache)))
        r2 = C.run(s, "CREATE (:B08G {id:'b08_g2'})")
        g2 = s.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'b08_g2'")[0][0]
        R["A_after_ttl"] = {"exc": r2.get("exc"), "msg": (r2.get("msg") or "")[:200], "b08_g2_rows": g2}
        # 6. restore the ledger, then clean up
        try:
            engB.ledger.set_strict(False)
            if found.get("state") != "enabled":
                engB.ledger.disable()
        except Exception as e:  # noqa: BLE001
            R["restore_error"] = f"{type(e).__name__}: {e}"
        if found.get("state") == "never-enabled":
            # Back to never-enabled with the pin's test/admin reset (Ledger.cls:241-248: kills ^IVG.Ledger and the
            # LedgerRevision / LedgerStats extents, nothing else).
            R["purge_all"] = str(s.c.call("Graph.KG.Ledger", "PurgeAll"))
        R["restored_meta"] = C.ledger_meta(s)
        R["restored_to_found"] = all(R["restored_meta"].get(k) == found.get(k) for k in ("state", "strict", "head_seq"))
        time.sleep(5.5)  # let A's guard forget strict mode before cleanup writes
        R["cleanup"] = C.cleanup(s)
        repro = (R["A_within_ttl"]["error"] is None and g1 == 1 and "Strict" in str(rB)
                 and "LedgerStrictModeError" == R["A_after_ttl"]["exc"])
        R["oracle"] = ("CYP-X7.2 / ledger-api.md:82-92: in strict mode a guarded write raises LedgerStrictModeError and "
                       "changes nothing")
        R["verdict"] = "reproduced" if repro else "inconclusive"
        p = C.write_log(s, R, name="08-strict-window")
    print(p)
    print(json.dumps({k: R[k] for k in ("A_within_ttl", "B_fresh_engine_write", "A_after_ttl", "restored_meta", "verdict")},
                     default=str, indent=1))


if __name__ == "__main__":
    main()
