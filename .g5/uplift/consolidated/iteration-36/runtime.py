"""Run-isolated iteration-36 continuation fixture runtime (container ivg-cont-20261117-iris); no shared database use."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("IVG_REPO", str(HERE.parents[3])))
PIN = Path(os.environ.get("IVG_PIN_DIR", "/home/ziniu_wu_g5labs_ai/experiments/iris-uplift-continuation-20261117/runs/ivg-cont-20261117/pin"))
PRODUCT = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
NAME = "ivg-cont-20261117-iris"
PORT = 36317
sys.path.insert(0, str(PIN))
os.environ["IVG_TEST_CONTAINER"] = NAME
os.environ["IVG_PORT"] = str(PORT)
os.environ["IVG_NAMESPACE"] = "USER"
os.environ["IVG_AUTO_START_CONTAINER"] = "0"


def connect():
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=PORT, namespace="USER",
                          username="_SYSTEM", password="SYS")
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c),
            fx.docker_container_hostname(NAME), fx.docker_container_id(NAME)):
        c.close()
        raise RuntimeError("audit database identity mismatch")
    return c


def engine(c):
    from iris_vector_graph.engine import IRISGraphEngine
    return IRISGraphEngine(c, embedding_dimension=768, native_cypher=False)


def hashes():
    """Check executable product files against the requested Git product object."""
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


if __name__ == "__main__":
    source_hashes = hashes()
    c = connect()
    e = engine(c)
    status = e.initialize_schema()
    c.close()
    result = dict(container=NAME, port=PORT, product=PRODUCT, identity_checked=True,
                  source_hashes=source_hashes, status=status,
                  qualification="Community 2026.1; no Arno library or %AI MCP classes. "
                  "Fresh audit-only namespace. Python and ObjectScript deployed from unchanged product pin.")
    (Path(os.environ.get("IVG_RUNTIME_OUT", str(HERE))) / "runtime.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({k: status.get(k) for k in ["schema", "objectscript_failed", "objectscript_skipped", "warnings"]}))
