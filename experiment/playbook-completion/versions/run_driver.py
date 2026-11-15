#!/usr/bin/env python3
"""Run a snapshot of the iris-contract driver with the client driver's identity and the engine recorded.

    python run_driver.py <snapshot native dir> cases.json observed.json [--only ID ...]

Environment: IVG_TEST_CONTAINER / IVG_PORT (the identity-checked target, as tools/iris_conn.Conn reads them),
IVG_CONTRACT_NS (namespace for the scratch globals and IVGAudit.* tables; default the driver's AUDITENV).
The driver itself is unchanged: only its module-level namespace NS is set before main() runs. Which
intersystems-irispython is used is decided by PYTHONPATH (the 5.4.0 site-packages first, or not); this script
prints what was actually imported so the log attributes every observation to one driver build.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as md
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    snap = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(TOOLS))
    sys.path.insert(0, str(snap))
    import iris  # noqa: E402

    pkg = Path(iris.__file__).parent
    so = sorted(pkg.glob(f"irissdk.cpython-{sys.version_info.major}{sys.version_info.minor}-*.so"))
    print("driver: intersystems-irispython", md.version("intersystems-irispython"),
          "| iris.__version__ =", getattr(iris, "__version__", None),
          "| iris from", iris.__file__,
          "| irissdk", so[0].name if so else None, "sha256", sha256(so[0]) if so else None, flush=True)
    print("python:", sys.version.split()[0], sys.executable, flush=True)
    print("target: container", os.environ["IVG_TEST_CONTAINER"], "port", os.environ["IVG_PORT"], flush=True)
    import driver  # noqa: E402  (the snapshot's native/driver.py)

    driver.NS = os.environ.get("IVG_CONTRACT_NS", driver.NS)
    print("namespace:", driver.NS, "| driver.py sha256", sha256(snap / "driver.py"), flush=True)
    sys.argv = [str(snap / "driver.py")] + sys.argv[2:]
    return driver.main()


if __name__ == "__main__":
    raise SystemExit(main())
