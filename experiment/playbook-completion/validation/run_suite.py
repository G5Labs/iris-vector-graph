#!/usr/bin/env python3
"""Run an upstream pytest set against the pin on the Community audit container (validation lane).

    python experiment/playbook-completion/validation/run_suite.py --meta OUT.json -- <pytest args...>

Run from the checkout root with experiment/playbook-completion/environment.sh sourced. Generalizes
$RUN_DIR/run-community-redaction.py (the original audit's harness) from one file to any path set.

What this harness replaces (and nothing else; collection, fixtures, resets, scenarios and assertions are the pin's):

1. `tests.conftest._deploy_objectscript` -> `deploy_dispatch`. The upstream session fixture (`iris_test_container`)
   calls `_deploy_objectscript(<container>)`, which loads every iris_src/src class, including Graph.KG.MCPService /
   MCPToolSet / MCPTools, which need %AI.* classes that IRIS Community 2026.1 does not have, so it fails and every
   test using `iris_connection` errors at setup. Exactly that call (container == $IVG_TEST_CONTAINER, namespace unset
   or $IVG_NAMESPACE, no Native handle, no port) goes to `deploy_community`, which checks the database identity with
   the upstream probe and then runs the pin's own `IRISGraphEngine.initialize_schema()` (it skips the %AI-dependent
   classes and reports them). Every other call (unit tests that exercise the function itself with a fake handle, an
   E2E file that loads a scratch namespace) goes to the pin's original function unchanged. The pin's conftest is
   verified byte-identical to the pin blob before the patch, and the replaced object is checked to be its function.

2. Namespace guard (audit policy, CONVENTIONS.md: lanes never create namespaces). `tcp_setup.make_namespace` and
   `tcp_setup.drop_namespace` (scripts/dev/tcp_setup.py, through which scripts/dev/make_scratch_namespace.py and the
   e2e gate make and drop scratch namespaces) raise AuditNamespacePolicy when given a real IRIS Native handle, and
   `tcp_setup.run` does when it would run on the real server (no handle, or a real one) lines that contain
   `Config.Namespaces/Databases ... Create` or `SYS.Database ... CreateDatabase`. Calls with a unit test's fake handle
   pass through to the pin's functions. A test that hits the guard is recorded as blocked by the audit policy, never
   as a product result. The e2e gate's own namespace plugin is switched off with IVG_GATE_NAMESPACES=0 by the caller
   (the documented switch, tests/e2e/gate.py).

The harness also records the IRIS namespace list (from iris.cpf, read-only) before and after the run, and the
number of times deploy_community ran, into the --meta JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path.cwd()
sys.path.insert(0, str(REPO))
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"

import pytest  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from tests import conftest as fixtures  # noqa: E402

DEPLOY_CALLS: list = []
DELEGATED: list = []
GUARD_HITS: list = []


class AuditNamespacePolicy(RuntimeError):
    """Raised instead of creating or dropping a namespace: the audit forbids it (CONVENTIONS.md)."""


def _blob(path: str) -> str:
    return subprocess.run(["git", "hash-object", path], capture_output=True, text=True, check=True).stdout.strip()


def _pin_blob(path: str) -> str:
    return subprocess.run(["git", "rev-parse", f"{PIN}:{path}"], capture_output=True, text=True,
                          check=True).stdout.strip()


def deploy_community(container_name, namespace=None, native=None, port=None):
    expected = os.environ["IVG_TEST_CONTAINER"]
    ns_expected = os.environ["IVG_NAMESPACE"]
    namespace = namespace or ns_expected
    scratch_ok = SCRATCH and namespace.upper() not in PREEXISTING  # a namespace this run's fixtures made
    if container_name != expected or native is not None or (namespace != ns_expected and not scratch_ok):
        raise RuntimeError(f"harness refuses deploy target {container_name}/{namespace} (native={native is not None})")
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
        t0 = time.time()
        engine = IRISGraphEngine(conn, namespace=namespace, embedding_dimension=fixtures.SESSION_EMBEDDING_DIM)
        status = engine.initialize_schema()
        summary = {key: status.get(key) for key in
                   ("schema", "objectscript_skipped", "objectscript_failed", "warnings")}
        DEPLOY_CALLS.append({"namespace": namespace, "identity": str(actual), "seconds": round(time.time() - t0, 2),
                             **summary})
        print("[run_suite] deploy_community " + json.dumps(summary, sort_keys=True), flush=True)
        if status.get("schema") != "Graph_KG" or status.get("objectscript_failed") or any(
            "failed" in warning.lower() for warning in status.get("warnings", [])
        ):
            raise RuntimeError("Community schema initialization failed")
    finally:
        conn.close()


_CREATE = re.compile(r"Config\.(Namespaces|Databases)\)?\s*\.\s*Create|Config\.(Namespaces|Databases)\"\s*,\s*\"Create"
                     r"|SYS\.Database\)?\s*\.\s*CreateDatabase", re.I)
ORIGINAL_DEPLOY = None


def deploy_dispatch(container_name, namespace=None, native=None, port=None):
    if (container_name == os.environ["IVG_TEST_CONTAINER"] and native is None and port is None
            and (namespace in (None, os.environ["IVG_NAMESPACE"])
                 or (SCRATCH and str(namespace).upper() not in PREEXISTING))):
        return deploy_community(container_name, namespace, native, port)
    DELEGATED.append({"container": str(container_name), "namespace": str(namespace), "native": type(native).__name__})
    return ORIGINAL_DEPLOY(container_name, namespace, native=native, port=port)


def _real(native) -> bool:
    import iris
    return isinstance(native, iris.IRIS)


SCRATCH = os.environ.get("VALIDATION_SCRATCH_NS") == "1"
PREEXISTING: set = set()
MADE: list = []


def install_namespace_guard() -> None:
    """Default: refuse every namespace make/drop on the real server. With VALIDATION_SCRATCH_NS=1 (the operator's
    2026-11-14 ruling: pinned fixtures that make isolated scratch namespaces may run under the iris lock), a make or drop
    of a namespace that did not exist when the run started is let through (and recorded); any namespace that existed
    before the run (%SYS, USER, AUDIT*, another lane's IVG460SNAP, ...) is still refused."""
    dev = str(REPO / "scripts" / "dev")
    if dev not in sys.path:
        sys.path.insert(0, dev)
    import tcp_setup  # the same module object make_scratch_namespace and tests/helpers/iris_lines import

    orig_make, orig_drop, orig_run = tcp_setup.make_namespace, tcp_setup.drop_namespace, tcp_setup.run

    def guarded(what, orig):
        def _g(native, ns, *args, **kwargs):
            if _real(native) and SCRATCH and str(ns).upper() not in PREEXISTING:
                MADE.append({"call": what, "namespace": str(ns)})
                return orig(native, ns, *args, **kwargs)
            if _real(native):
                GUARD_HITS.append({"call": what, "namespace": str(ns)})
                raise AuditNamespacePolicy(f"audit policy: {what}({ns}) refused (lanes never create or drop namespaces)")
            return orig(native, ns, *args, **kwargs)
        return _g

    def guarded_run(lines, namespace, *args, **kwargs):
        native = kwargs.get("native")
        text = lines if isinstance(lines, str) else "\n".join(lines)
        if (native is None or _real(native)) and _CREATE.search(text):
            GUARD_HITS.append({"call": "tcp_setup.run", "namespace": str(namespace),
                               "match": _CREATE.search(text).group(0)})
            raise AuditNamespacePolicy("audit policy: ObjectScript creating a namespace/database refused")
        return orig_run(lines, namespace, *args, **kwargs)

    tcp_setup.make_namespace = guarded("tcp_setup.make_namespace", orig_make)
    tcp_setup.drop_namespace = guarded("tcp_setup.drop_namespace", orig_drop)
    tcp_setup.run = guarded_run
    # `session` calls run through the module global, so it is guarded too.


def namespaces() -> list:
    out = subprocess.run(["docker", "exec", os.environ["IVG_TEST_CONTAINER"], "cat", "/usr/irissys/iris.cpf"],
                         capture_output=True, text=True, timeout=60).stdout
    sect = re.search(r"^\[Namespaces\]\n(.*?)(?:^\[|\Z)", out, re.S | re.M)
    return sorted(line.split("=", 1)[0] for line in (sect.group(1).splitlines() if sect else []) if "=" in line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", required=True)
    ap.add_argument("--no-guard", action="store_true")
    ap.add_argument("pytest_args", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    args = a.pytest_args[1:] if a.pytest_args[:1] == ["--"] else a.pytest_args

    if _blob("tests/conftest.py") != _pin_blob("tests/conftest.py"):
        raise SystemExit("tests/conftest.py differs from the pin")
    if not (getattr(fixtures._deploy_objectscript, "__module__", "") == "tests.conftest"
            and fixtures._deploy_objectscript.__name__ == "_deploy_objectscript"):
        raise SystemExit("tests.conftest._deploy_objectscript is not the pin's function")
    global ORIGINAL_DEPLOY
    ORIGINAL_DEPLOY = fixtures._deploy_objectscript
    fixtures._deploy_objectscript = deploy_dispatch
    before = namespaces()
    PREEXISTING.update(n.upper() for n in before)
    if not a.no_guard:
        install_namespace_guard()

    t0 = time.time()
    t0u = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    code = int(pytest.main(list(args)))
    dt = time.time() - t0
    after = namespaces()
    meta = {
        "argv": args, "exit_code": code, "seconds": round(dt, 1), "start_utc": t0u,
        "end_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "harness": {
            "replaces": ["tests.conftest._deploy_objectscript: the session call -> deploy_community (pin initialize_schema); other calls -> pin original"]
            + ([] if a.no_guard else ["scripts/dev/tcp_setup.make_namespace, drop_namespace: real IRIS handle -> AuditNamespacePolicy",
                                      "scripts/dev/tcp_setup.run: on the real server, refuses lines creating a namespace or database"]),
            "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "conftest_blob": _blob("tests/conftest.py"),
        },
        "deploy_calls": DEPLOY_CALLS, "deploy_delegated": DELEGATED, "guard_hits": GUARD_HITS,
        "scratch_mode": SCRATCH, "scratch_namespace_calls": MADE,
        "env": {k: os.environ.get(k) for k in ("IVG_TEST_CONTAINER", "IVG_PORT", "IVG_NAMESPACE", "SKIP_IRIS_TESTS",
                                               "IVG_GATE_NAMESPACES", "IVG_GATE", "PYTEST_ADDOPTS",
                                               "IVG_AUTO_START_CONTAINER")},
        "namespaces_before": before, "namespaces_after": after, "namespaces_unchanged": before == after,
    }
    Path(a.meta).write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n")
    print(f"[run_suite] exit={code} seconds={dt:.1f} namespaces_unchanged={before == after} "
          f"deploy_calls={len(DEPLOY_CALLS)} delegated={len(DELEGATED)} guard_hits={len(GUARD_HITS)}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
