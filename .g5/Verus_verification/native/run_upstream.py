#!/usr/bin/env python3
"""Run upstream pytest targets on this arm's IRIS with IVG's Community deployment path.

A generalisation of experiment/g5-verus/run-community-redaction.py to any test paths. The upstream
session fixture compiles every class, including the three MCP classes that need %AI, which Community
Edition lacks; only that setup function is replaced by engine.initialize_schema(). Test collection,
connection identity checks, database resets, scenarios and assertions come from the pinned checkout.

    python3 .g5/Verus_verification/native/run_upstream.py <pytest args and paths...>
"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import pytest  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from tests import conftest as fixtures  # noqa: E402


def deploy_community(container_name, namespace=None, native=None, port=None):
    expected = os.environ["IVG_TEST_CONTAINER"]
    if container_name != expected or native is not None:
        raise RuntimeError(f"Unexpected deploy target or handle for {container_name}")
    namespace = namespace or os.environ["IVG_NAMESPACE"]
    port = int(port or os.environ["IVG_PORT"])
    import iris.dbapi

    conn = iris.dbapi.connect(hostname="127.0.0.1", port=port, namespace=namespace,
                              username="_SYSTEM", password="SYS")
    try:
        actual = fixtures.probe_instance_hostname(conn)
        if not fixtures.container_hostname_matches(
            actual, fixtures.docker_container_hostname(expected), fixtures.docker_container_id(expected)
        ):
            raise RuntimeError(f"Database identity does not match {expected}")
        engine = IRISGraphEngine(conn, namespace=namespace, embedding_dimension=fixtures.SESSION_EMBEDDING_DIM)
        status = engine.initialize_schema()
        print(json.dumps({key: status.get(key) for key in
                          ("schema", "objectscript_skipped", "objectscript_failed", "warnings")}, sort_keys=True))
        if status.get("schema") != "Graph_KG" or status.get("objectscript_failed") or any(
            "failed" in warning.lower() for warning in status.get("warnings", [])
        ):
            raise RuntimeError("Community schema initialization failed")
    finally:
        conn.close()


if __name__ == "__main__":
    if os.environ.get("IVG_TEST_CONTAINER") != "ivg-g5-verus-20261113-iris" or os.environ.get("IVG_PORT") != "35972":
        raise SystemExit("source experiment/g5-verus/environment.sh first (this arm's container and port)")
    fixtures._deploy_objectscript = deploy_community
    raise SystemExit(pytest.main(["-q", "-o", "addopts=", "-m", "not perf", "--tb=short", "-p", "no:cacheprovider",
                                  *sys.argv[1:]]))
