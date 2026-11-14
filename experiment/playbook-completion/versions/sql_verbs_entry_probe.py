#!/usr/bin/env python3
"""SQL COMMIT / ROLLBACK / START TRANSACTION levels through both client entry points of one driver build.

    python sql_verbs_entry_probe.py <namespace>

The contract's driver connects with `iris.dbapi.connect`; the product's tests and docs also hand the engine
`iris.connect(...)` connections. This asks, on the identity-checked target (IVG_TEST_CONTAINER / IVG_PORT), whether the
entry point changes E-SQL-END / E-SQL-START: two Native API levels, then the SQL statement, then `$TLEVEL`.
Nothing is written but $TLEVEL changes; every level is rolled back at the end.
"""
from __future__ import annotations

import importlib.metadata as md
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
import iris  # noqa: E402
import iris.dbapi  # noqa: E402

from tests import conftest as fx  # noqa: E402


def checked(conn):
    container = os.environ["IVG_TEST_CONTAINER"]
    actual = fx.probe_instance_hostname(conn)
    if not fx.container_hostname_matches(actual, fx.docker_container_hostname(container),
                                         fx.docker_container_id(container)):
        conn.close()
        raise RuntimeError(f"database identity does not match {container}")
    return conn


def main() -> int:
    ns = sys.argv[1]
    port = int(os.environ["IVG_PORT"])
    print("driver:", md.version("intersystems-irispython"))
    entries = {
        "iris.dbapi.connect": lambda: iris.dbapi.connect(hostname="127.0.0.1", port=port, namespace=ns,
                                                         username="_SYSTEM", password="SYS"),
        "iris.connect": lambda: iris.connect("127.0.0.1", port, ns, "_SYSTEM", "SYS"),
    }
    for name, make in entries.items():
        conn = checked(make())
        try:
            o = iris.createIRIS(conn)
            if name == "iris.dbapi.connect":
                print("engine:", o.classMethodValue("%SYSTEM.Version", "GetVersion"))
            res = {}
            for stmt in ("COMMIT", "ROLLBACK", "START TRANSACTION"):
                o.tStart()
                o.tStart()
                cur = conn.cursor()
                cur.execute(stmt)
                cur.close()
                res[stmt] = int(o.getTLevel())
                o.tRollback()
            print(f"{name} ({type(conn).__module__}.{type(conn).__name__}): $TLEVEL 2 -> SQL COMMIT -> {res['COMMIT']}; "
                  f"2 -> SQL ROLLBACK -> {res['ROLLBACK']}; 2 -> SQL START TRANSACTION -> {res['START TRANSACTION']}")
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
