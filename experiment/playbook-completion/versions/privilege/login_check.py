#!/usr/bin/env python3
"""Whether IVGAUDIT_RO can log in to AUDITB now (the password is read from the secrets file, never printed)."""
import os
import sys
from pathlib import Path

import iris.dbapi

pw = (Path(os.environ["RUN_DIR"]) / "versions" / "secrets" / "ivgaudit_ro.pw").read_text().strip()
try:
    c = iris.dbapi.connect(hostname="127.0.0.1", port=int(os.environ["IVG_PORT"]), namespace="AUDITB",
                           username="IVGAUDIT_RO", password=pw)
    cur = c.cursor()
    cur.execute("SELECT $USERNAME")
    print("login: accepted as", cur.fetchone()[0])
    c.close()
except Exception as e:  # noqa: BLE001
    print("login: refused:", type(e).__name__, str(e)[:200])
sys.exit(0)
