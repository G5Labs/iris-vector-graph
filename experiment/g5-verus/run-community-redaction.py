#!/usr/bin/env python3
"""Run the upstream ledger redaction suite with IVG's Community deployment path.

The upstream session fixture unconditionally compiles classes that depend on
%AI. Only its setup function is replaced. Test collection, connection identity
checks, database reset, scenarios and assertions come from the pinned checkout.
Run from the IVG checkout with the experiment environment active.
"""
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path.cwd()))
from iris_vector_graph.engine import IRISGraphEngine
from tests import conftest as fixtures


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
    fixtures._deploy_objectscript = deploy_community
    raise SystemExit(pytest.main(["-q", "-s", "-o", "addopts=", "--tb=short",
                                  "tests/integration/test_256_ledger_redaction_e2e.py", *sys.argv[1:]]))
