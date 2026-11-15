"""Shared harness for breadth lane A's live checks in namespace AUDITA (observation only).

Every probe uses the pin's public Python API, deployed Graph.KG class methods through the Native API, or SQL, on an
identity-checked connection (tools/iris_conn.Conn). Nothing is compiled into IRIS and no product file is touched.
Each probe works in graphs whose names start with "ba" plus a per-run suffix, and erases them at the end through the
product's own erase_graph, so probes do not see each other's data. Scratch globals are ^IVGAuditA* only.

    python experiment/playbook-completion/live/breadth-a/probes_NN.py [probe ...]

writes live/breadth-a/results/<probe>.json (the observation, the oracle and whether the finding reproduced) and
$RUN_DIR/breadth-a/live/<module>-<stamp>.log (everything printed, including product log lines).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Callable, Dict, List

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                      # experiment/playbook-completion
REPO = ROOT.parents[1]
for p in (ROOT / "tools", ROOT / "traces", REPO):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from iris_conn import Conn  # noqa: E402
import journal as J  # noqa: E402

NS = "AUDITA"
DB = "/usr/irissys/mgr/audita/"
RESULTS = HERE / "results"
LOGDIR = Path(os.environ["RUN_DIR"]) / "breadth-a" / "live"
RUN = dt.datetime.now().strftime("%H%M%S")


def conn() -> Conn:
    return Conn(NS)


def engine(c: Conn | None = None, **kw):
    from iris_vector_graph.engine import IRISGraphEngine
    c = c or conn()
    kw.setdefault("embedding_dimension", 4)
    return c, IRISGraphEngine(c.conn, namespace=NS, **kw)


def gname(tag: str) -> str:
    return f"ba{tag}{RUN}"


def erase(eng, *graphs):
    for g in graphs:
        with contextlib.suppress(Exception):
            eng.erase_graph(g)


def rows(c: Conn, q: str, *params):
    return c.sql(q, *params)


class Result(dict):
    """One probe's record: id, finding, oracle, observed, reproduced (True/False/None), notes."""

    def obs(self, key, value):
        self.setdefault("observed", {})[key] = value
        print(f"  observed {key} = {value!r}")
        return value


def run(module: str, probes: Dict[str, Callable[[Result], None]], argv: List[str]) -> int:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    want = argv or list(probes)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = LOGDIR / f"{module}-{'-'.join(want) if len(want) < 4 else 'all'}-{stamp}.log"
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    summary = []

    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s)
            buf.write(s)
            return len(s)

    with contextlib.redirect_stdout(Tee()):
        print(f"# breadth-a live probes, module {module}, namespace {NS}, run {RUN}, {stamp}")
        for name in want:
            fn = probes[name]
            r = Result(id=name, module=module, started=dt.datetime.now().isoformat(timespec="seconds"),
                       doc=(fn.__doc__ or "").strip())
            print(f"\n## {name}\n{r['doc']}")
            t = time.time()
            try:
                fn(r)
            except Exception as e:  # a probe that crashed is recorded as such, never as a pass
                r["error"] = f"{type(e).__name__}: {e}"
                r["traceback"] = traceback.format_exc()
                r.setdefault("reproduced", None)
                print(r["traceback"])
            r["seconds"] = round(time.time() - t, 2)
            r["log"] = "$RUN_DIR/" + str(log_path.relative_to(Path(os.environ["RUN_DIR"])))
            print(f"=> {name}: reproduced={r.get('reproduced')} {r.get('verdict', '')}")
            (RESULTS / f"{name}.json").write_text(json.dumps(r, indent=1, sort_keys=True, default=str) + "\n")
            summary.append((name, r.get("reproduced"), r.get("verdict", "")))
        print("\n# summary")
        for s in summary:
            print(f"{s[0]:<40} reproduced={s[1]!s:<6} {s[2]}")
    logging.getLogger().removeHandler(handler)
    log_path.write_text(buf.getvalue())
    print(f"log: {log_path}")
    return 0
