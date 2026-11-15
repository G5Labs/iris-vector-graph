#!/usr/bin/env python3
"""What the product's autocommit reading sees with each driver build (observation only, no product code changed).

    python autocommit_probe.py <namespace>

Connects through tools/iris_conn.Conn (identity-checked against IVG_TEST_CONTAINER / IVG_PORT), then reports:
- the connection's type and whether it exposes `autocommit`;
- `iris_vector_graph._write_txn._driver_autocommit_off(conn)` and `caller_transaction_level(conn)` (the pin's code,
  imported read-only) after `setAutoCommit(False)` and after `setAutoCommit(True)`;
- `$TLEVEL` around `setAutoCommit(True)` with a Native API level open, autocommit already on (E-AUTOCOMMIT's
  disputed half) and after switching it off then on with a level open.
Scratch: ^IVGAuditVer only, killed at the end.
"""
from __future__ import annotations

import importlib.metadata as md
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from iris_conn import Conn, version  # noqa: E402


def main() -> int:
    ns = sys.argv[1]
    from iris_vector_graph import _write_txn as wt

    print("driver:", md.version("intersystems-irispython"))
    c = Conn(ns)
    try:
        print("engine:", version(c))
        conn, o = c.conn, c.o
        print("type:", type(conn).__module__, type(conn).__name__, "| hasattr autocommit:", hasattr(conn, "autocommit"))
        print("initial autocommit attr:", getattr(conn, "autocommit", "<absent>"))
        conn.setAutoCommit(False)
        print("after setAutoCommit(False): attr", getattr(conn, "autocommit", "<absent>"),
              "| _driver_autocommit_off", wt._driver_autocommit_off(conn),
              "| caller_transaction_level", wt.caller_transaction_level(conn))
        conn.setAutoCommit(True)
        print("after setAutoCommit(True): attr", getattr(conn, "autocommit", "<absent>"),
              "| _driver_autocommit_off", wt._driver_autocommit_off(conn),
              "| caller_transaction_level", wt.caller_transaction_level(conn))
        # E-AUTOCOMMIT: autocommit already on, a Native level open, setAutoCommit(True)
        o.kill("^IVGAuditVer")
        o.tStart()
        o.set("1", "^IVGAuditVer", "a")
        before = o.getTLevel()
        conn.setAutoCommit(True)
        after = o.getTLevel()
        o.tRollback()
        print(f"already-on: $TLEVEL {before} -> setAutoCommit(True) -> {after}; after TROLLBACK ^IVGAuditVer(a) =",
              o.get("^IVGAuditVer", "a"))
        # off -> on with a level open
        o.kill("^IVGAuditVer")
        conn.setAutoCommit(False)
        o.tStart()
        o.set("2", "^IVGAuditVer", "b")
        before = o.getTLevel()
        conn.setAutoCommit(True)
        after = o.getTLevel()
        o.tRollback()
        print(f"off-then-on: $TLEVEL {before} -> setAutoCommit(True) -> {after}; after TROLLBACK ^IVGAuditVer(b) =",
              o.get("^IVGAuditVer", "b"))
        o.kill("^IVGAuditVer")
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
