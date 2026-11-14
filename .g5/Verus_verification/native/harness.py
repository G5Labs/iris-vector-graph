"""Native observation harness for the IVG Verus uplift (product baseline 3eaa79cf).

Probes drive the unmodified product through its public entry points against this arm's IRIS
instance only, and record what they observe. Nothing here changes product code; the harness only
connects, resets graph and ledger content, reads raw ledger state and writes observation JSON.

Environment (experiment/g5-verus/environment.sh): IVG_TEST_CONTAINER, IVG_PORT, IVG_NAMESPACE, RUN_DIR.
Every connection is checked against the container's hostname before anything is written, with the
same helpers the upstream test suite uses (tests/conftest.py).

Interface used by probes:
    conn, native = connect()
    eng = engine(conn)            # IRISGraphEngine on that connection
    reset(eng, native)            # every graph's content (Eraser.EraseAll) and all ledger state
    record(name, dict)            # observation JSON under $RUN_DIR/native/<name>-<stamp>.json
    ledger_records(native)        # {(seq, ordinal): $LB fields as a list} from ^IVG.Ledger("rec")
    canonical(native, seq, ord)   # Graph.KG.Ledger.CanonicalRecord(seq, ordinal)
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

RUN_DIR = Path(os.environ.get("RUN_DIR", str(Path.home() / "runs/iris-vector-graph-g5-verus-20261113")))
CONTAINER = os.environ.get("IVG_TEST_CONTAINER", "")
PORT = int(os.environ.get("IVG_PORT", "0") or 0)
NAMESPACE = os.environ.get("IVG_NAMESPACE", "USER")
EXPECTED_CONTAINER = "ivg-g5-verus-20261113-iris"
EXPECTED_PORT = 35972


def _guard():
    if CONTAINER != EXPECTED_CONTAINER or PORT != EXPECTED_PORT:
        raise SystemExit(f"refusing to run: IVG_TEST_CONTAINER={CONTAINER!r} IVG_PORT={PORT}; "
                         f"expected {EXPECTED_CONTAINER} on {EXPECTED_PORT} (source experiment/g5-verus/environment.sh)")


def connect():
    """(dbapi connection, native IRIS handle) on this arm's instance, identity-checked."""
    _guard()
    import iris
    import iris.dbapi
    from tests import conftest as fx

    conn = iris.dbapi.connect(hostname="127.0.0.1", port=PORT, namespace=NAMESPACE,
                              username="_SYSTEM", password="SYS")
    actual = fx.probe_instance_hostname(conn)
    if not fx.container_hostname_matches(actual, fx.docker_container_hostname(CONTAINER),
                                         fx.docker_container_id(CONTAINER)):
        conn.close()
        raise SystemExit(f"database identity {actual!r} does not match container {CONTAINER}")
    return conn, iris.createIRIS(conn)


def engine(conn, **kw):
    """IRISGraphEngine at the namespace's recorded embedding width (768: the width the upstream session deploy
    recorded on this arm). Setup refuses to change a recorded width without rewidth=True (4.7.0), and probes must
    not re-declare product columns."""
    from iris_vector_graph.engine import IRISGraphEngine

    kw.setdefault("embedding_dimension", 768)
    return IRISGraphEngine(conn, **kw)


def ensure_schema(eng) -> dict:
    """The Community deployment path (engine.initialize_schema), as experiment/g5-verus/run-community-redaction.py."""
    status = eng.initialize_schema()
    return {k: status.get(k) for k in ("schema", "objectscript_skipped", "objectscript_failed", "warnings")}


def reset(eng, native) -> None:
    """Remove every graph's content and all ledger state (the upstream ledger_reset fixture's steps)."""
    try:
        eng.ledger.enable()  # a disabled ledger leaves erase_all permitted either way; strict is off after PurgeAll
    except Exception:
        pass
    try:
        eng.ledger.set_strict(False)
    except Exception:
        pass
    eng.erase_all()
    cur = eng.conn.cursor()
    try:
        for table in ("Graph_KG.ledger_revisions", "Graph_KG.ledger_stats"):
            try:
                cur.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        try:
            eng.conn.commit()
        except Exception:
            pass
    finally:
        cur.close()
    native.classMethodValue("Graph.KG.Ledger", "PurgeAll")
    try:
        eng.ledger._refresh_guard()
    except Exception:
        pass


def _walk(native, gname, subs):
    out = {}
    sub = ""
    while True:
        sub = native.nextSubscript(False, gname, *subs, sub)
        if sub is None or sub == "":
            break
        key = subs + (sub,)
        if native.isDefined(gname, *key) % 10:
            out[key] = native.getBytes(gname, *key)  # raw bytes: $LB values decode with iris.IRISList
        out.update(_walk(native, gname, key))
    return out


def ledger_records(native) -> dict:
    """{(seq, ordinal): list of $LB fields} for ^IVG.Ledger("rec")."""
    import iris

    out = {}
    for key, val in _walk(native, "^IVG.Ledger", ("rec",)).items():
        if len(key) != 3:
            continue
        lst = iris.IRISList(val)
        fields = [lst.get(i) for i in range(1, lst.count() + 1)]
        out[(int(key[1]), int(key[2]))] = [f.decode() if isinstance(f, bytes) else f for f in fields]
    return out


def ledger_global(native, *subs) -> dict:
    return _walk(native, "^IVG.Ledger", tuple(subs))


def canonical(native, seq: int, ordinal: int) -> str:
    return str(native.classMethodValue("Graph.KG.Ledger", "CanonicalRecord", seq, ordinal))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _probe_inputs() -> dict:
    """SHA-256 of the running probe, its helpers and the harness, so a later edit makes this observation stale."""
    here = Path(__file__).resolve().parent
    files = {Path(sys.argv[0]).resolve()} | set((here / "probes").glob("*_common.py")) | {here / "harness.py"}
    return {str(f.relative_to(REPO)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files) if f.exists()}


def record(name: str, data: dict) -> Path:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RUN_DIR / "native" / f"{name}-{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {**data, "_probe_inputs": _probe_inputs(), "_product_baseline": "3eaa79cf77d3e0a879b2cced634cf2729d81499e"}
    out.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")
    return out
