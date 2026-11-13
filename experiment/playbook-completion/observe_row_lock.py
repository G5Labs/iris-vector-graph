"""Observe a conflicting SQL DELETE on a disposable table on the IVG experiment VM."""
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import iris.dbapi
from tests import conftest as fixtures


def connect():
    conn = iris.dbapi.connect(hostname="127.0.0.1", port=int(os.environ["IVG_PORT"]),
                              namespace=os.environ["IVG_NAMESPACE"], username="_SYSTEM", password="SYS")
    container = os.environ["IVG_TEST_CONTAINER"]
    if not fixtures.container_hostname_matches(fixtures.probe_instance_hostname(conn),
            fixtures.docker_container_hostname(container), fixtures.docker_container_id(container)):
        conn.close()
        raise RuntimeError("Unexpected IRIS instance")
    return conn


def observe(table, held_key):
    started = threading.Event()

    def delete(key, signal=False):
        conn = connect()
        try:
            cur = conn.cursor()
            if signal:
                started.set()
            cur.execute(f"DELETE FROM {table} WHERE k = ?", (key,))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    owner = connect()
    try:
        cursor = owner.cursor()
        cursor.execute("START TRANSACTION")
        with ThreadPoolExecutor(max_workers=1) as workers:
            try:
                cursor.execute(f"UPDATE {table} SET v = 2 WHERE k = ?", (held_key,))
                job = workers.submit(delete, held_key, True)
                if not started.wait(10):
                    raise RuntimeError("Delete worker failed to start")
                time.sleep(0.5)
                while_held = job.done()
            finally:
                owner.rollback()
            affected = job.result(timeout=15)
        return {"finished_while_update_open": while_held, "deleted_after_rollback": affected}
    finally:
        owner.close()


def main():
    table = "SQLUser.IVGAuditLock" + uuid.uuid4().hex[:12]
    admin = connect()
    try:
        cur = admin.cursor()
        cur.execute(f"CREATE TABLE {table} (k INTEGER PRIMARY KEY, v INTEGER)")
        try:
            for key in (1, 2, 3):
                cur.execute(f"INSERT INTO {table} (k, v) VALUES (?, 1)", (key,))
            admin.commit()
            baseline = time.monotonic()
            cur.execute(f"DELETE FROM {table} WHERE k = 3")
            admin.commit()
            control_elapsed = time.monotonic() - baseline
            observations = [observe(table, key) for key in (1, 2)]
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            remaining = cur.fetchone()[0]
            print(json.dumps({"uncontended_delete_seconds": control_elapsed, "observations": observations,
                              "remaining_rows": remaining}, sort_keys=True))
            assert remaining == 0 and all(not r["finished_while_update_open"] and
                                          r["deleted_after_rollback"] == 1 for r in observations)
        finally:
            cur.execute(f"DROP TABLE {table}")
            admin.commit()
    finally:
        admin.close()


if __name__ == "__main__":
    main()
