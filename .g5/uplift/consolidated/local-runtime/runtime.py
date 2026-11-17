"""Local fixture runtime (iteration 60): container ivg-uplift-next-20261115 on 127.0.0.1:35975.

Same API as iteration-36/runtime.py (NAME, PORT, PRODUCT, connect(), engine(c), hashes()), pointed at the local shared
fixture. `connect(namespace)` checks the database identity against the container before returning. Bindings written for
the cloud runtime run here through `run_binding.py`, which installs this module as `sys.modules['runtime']`; every
receipt it writes records this fixture. Never relabel a cloud receipt as a local run.
"""
from pathlib import Path
import hashlib
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("IVG_REPO", str(HERE.parents[3])))
PIN = Path(os.environ.get("IVG_PIN_DIR", "/Users/ziniuw/runs/ivg-consolidated-20261114/pin"))
PRODUCT = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
NAME = "ivg-uplift-next-20261115"
PORT = 35975
FIXTURE = {"container": NAME, "host": "127.0.0.1", "port": PORT, "kind": "local-shared",
           "iris": "IRIS Community 2026.1 (Build 234U)"}
if str(PIN) not in sys.path:
    sys.path.insert(0, str(PIN))
os.environ["IVG_TEST_CONTAINER"] = NAME
os.environ["IVG_PORT"] = str(PORT)
os.environ.setdefault("IVG_NAMESPACE", "USER")
os.environ["IVG_AUTO_START_CONTAINER"] = "0"


def identity(c):
    from tests import conftest as fx
    host = fx.probe_instance_hostname(c)
    ok = fx.container_hostname_matches(host, fx.docker_container_hostname(NAME), fx.docker_container_id(NAME))
    return ok, host


def connect(namespace: str = "USER"):
    import iris.dbapi
    c = iris.dbapi.connect(hostname="127.0.0.1", port=PORT, namespace=namespace,
                           username="_SYSTEM", password="SYS")
    ok, host = identity(c)
    if not ok:
        c.close()
        raise RuntimeError(f"database identity mismatch (instance hostname {host!r} vs container {NAME})")
    return c


def engine(c, namespace: str | None = None):
    from iris_vector_graph.engine import IRISGraphEngine
    kw = {"namespace": namespace} if namespace else {}
    return IRISGraphEngine(c, embedding_dimension=768, native_cypher=False, **kw)


def hashes():
    """Check executable product files against the pinned Git product object."""
    files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", PRODUCT],
                                    cwd=ROOT, text=True).splitlines()
    out = {}
    for p in files:
        if p.startswith(("iris_vector_graph/", "iris_src/", "api/")) and (PIN / p).is_file():
            actual = (PIN / p).read_bytes()
            expected = subprocess.check_output(["git", "show", f"{PRODUCT}:{p}"], cwd=ROOT)
            assert actual == expected, p
            out[p] = hashlib.sha256(actual).hexdigest()
    return out
