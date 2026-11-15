"""Identity-checked connections to the dedicated audit IRIS container.

Every connection is checked with the upstream fixtures' identity probe against $IVG_TEST_CONTAINER, so nothing in
the completion audit can run against another database. One connection is one IRIS server process: its SQL
(DBAPI cursor) and its Native API handle (globals, locks, class methods, transaction level) share that process and
therefore that process's transaction and lock ownership.
"""
from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import iris  # noqa: E402
import iris.dbapi  # noqa: E402

from tests import conftest as fixtures  # noqa: E402


class Conn:
    def __init__(self, namespace: str | None = None) -> None:
        container = os.environ["IVG_TEST_CONTAINER"]
        self.namespace = namespace or os.environ.get("IVG_NAMESPACE", "USER")
        self.conn = iris.dbapi.connect(hostname="127.0.0.1", port=int(os.environ["IVG_PORT"]),
                                       namespace=self.namespace, username="_SYSTEM", password="SYS")
        actual = fixtures.probe_instance_hostname(self.conn)
        if not fixtures.container_hostname_matches(actual, fixtures.docker_container_hostname(container),
                                                   fixtures.docker_container_id(container)):
            self.conn.close()
            raise RuntimeError(f"database identity does not match {container}")
        self.o = iris.createIRIS(self.conn)
        self.pid = str(self.o.classMethodValue("%SYSTEM.SYS", "ProcessID"))

    def call(self, cls: str, method: str, *args):
        return self.o.classMethodValue(cls, method, *args)

    def sql(self, q: str, *params):
        cur = self.conn.cursor()
        try:
            cur.execute(q, params) if params else cur.execute(q)
            return [tuple(r) for r in cur.fetchall()] if cur.description else cur.rowcount
        finally:
            cur.close()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def version(c: Conn) -> str:
    return str(c.call("%SYSTEM.Version", "GetVersion"))
