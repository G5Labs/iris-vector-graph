"""Shared harness for the refusals lane's live probes (namespace AUDITE only; playbook gate 5c-refusals).

    from rxlib import Lane
    with Lane("11") as L:                       # identity-checked Conn("AUDITE") + engine on the same process
        L.reset()                               # product's own Eraser.EraseAll + Ledger.PurgeAll (outside windows)
        L.control()                             # oracle positive control: a scratch write must be seen
        L.refusal("LED-B4.5", "commit never enabled", lambda: L.eng.ledger.commit(cs),
                  expect=raises("LedgerNotEnabledError", code="not_enabled"))
        L.save()                                # $RUN_DIR/refusals/<module>/results.json

Oracle. Each refused call runs inside a journal window (traces/journal.py: the engine's own journal, read
server-side, nothing compiled). Every SET/KILL record of AUDITE's database in the window, from any process, is kept;
its net effect (journal.net_effect) is what the call changed. A case may name `allowed` store patterns (for example
the ledger stats counter a refusal is stated to bump); anything else with a net effect, or any raw record left in an
open transaction, makes the case "changed". After the call the connection's $TLEVEL is read; an IVG refusal that
leaves a transaction open is reported (the probe then rolls it back outside the window).

The lane runs every command under `tools/locks.sh iris` (one IRIS process per Conn; at most 6 at once). The only
non-product writes are this harness's own scratch global ^IVGAuditRX (control write) and resets through the
product's own EraseAll/PurgeAll.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
COMPLETION = HERE.parent
REPO = COMPLETION.parents[1]
for p in (str(COMPLETION / "tools"), str(COMPLETION / "traces"), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

from iris_conn import Conn  # noqa: E402
import journal  # noqa: E402

NS = "AUDITE"
DB = "/usr/irissys/mgr/audite/"
LANE = "refusals"
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"


def run_dir(sub: str) -> Path:
    p = Path(os.environ["RUN_DIR"]) / LANE / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def engine(c: Conn, **kw):
    from iris_vector_graph.engine import IRISGraphEngine
    kw.setdefault("embedding_dimension", 4)
    return IRISGraphEngine(c.conn, namespace=NS, **kw)


def tlevel(conn) -> Optional[int]:
    cur = conn.cursor()
    try:
        cur.execute("SELECT $TLEVEL")
        row = cur.fetchone()
        return int(row[0]) if row else None
    except Exception:  # noqa: BLE001
        return None
    finally:
        with contextlib.suppress(Exception):
            cur.close()


def rollback_all(conn) -> Optional[int]:
    """Roll back every open level on this connection (SQL ROLLBACK ends one level on 2026.1, iris-contract)."""
    for _ in range(12):
        lvl = tlevel(conn)
        if not lvl:
            break
        cur = conn.cursor()
        try:
            cur.execute("ROLLBACK")
        except Exception:  # noqa: BLE001
            with contextlib.suppress(Exception):
                conn.rollback()
        finally:
            with contextlib.suppress(Exception):
                cur.close()
    with contextlib.suppress(Exception):
        conn.rollback()
    return tlevel(conn)


def open_caller_txn(conn, write_sql: Optional[str] = None) -> Optional[int]:
    """A caller transaction as the product's own tests open one (START TRANSACTION, then a write)."""
    cur = conn.cursor()
    try:
        cur.execute("START TRANSACTION")
        if write_sql:
            cur.execute(write_sql)
    finally:
        with contextlib.suppress(Exception):
            cur.close()
    return tlevel(conn)


# ------------------------------------------------------------------------------------------------ expectations

class Expect:
    """What the statement says the refusal looks like. `check(exc, result) -> (ok, why)`."""

    def __init__(self, desc: str, fn: Callable[[Optional[BaseException], Any], Tuple[bool, str]]):
        self.desc = desc
        self.fn = fn

    def check(self, exc, result):
        try:
            return self.fn(exc, result)
        except Exception as e:  # noqa: BLE001
            return False, f"expectation raised {type(e).__name__}: {e}"


def _mro_names(exc: BaseException) -> List[str]:
    return [k.__name__ for k in type(exc).__mro__]


def raises(*names: str, code: Optional[str] = None, match: Optional[str] = None,
           attr: Optional[Dict[str, Any]] = None) -> Expect:
    """The call raises an exception whose class (or a base class) is one of `names`; optional wire `code`
    (exception .code / .error_code attribute or text), message regex `match`, attribute values `attr`."""
    desc = "raises " + "|".join(names) + (f" code={code}" if code else "") + (f" /{match}/" if match else "")

    def fn(exc, result):
        if exc is None:
            return False, f"no exception; returned {repr(result)[:300]}"
        mro = _mro_names(exc)
        if names and not any(n in mro for n in names):
            return False, f"raised {type(exc).__name__} (mro {mro[:4]}), want {names}"
        if code is not None:
            got = getattr(exc, "code", None) or getattr(exc, "error_code", None)
            if got != code and code not in str(exc):
                return False, f"code {got!r}, want {code!r}"
        if match is not None and not re.search(match, f"{exc}", re.S | re.I):
            return False, f"message {str(exc)[:300]!r} does not match /{match}/"
        for k, v in (attr or {}).items():
            got = getattr(exc, k, None)
            if callable(v):
                if not v(got):
                    return False, f"attribute {k}={got!r} fails its check"
            elif got != v:
                return False, f"attribute {k}={got!r}, want {v!r}"
        return True, f"raised {type(exc).__name__}: {str(exc)[:300]}"
    return Expect(desc, fn)


def returns(pred: Callable[[Any], bool], desc: str) -> Expect:
    """The refusal is an answer, not an exception (e.g. {'status':'error'} or a refused count)."""
    def fn(exc, result):
        if exc is not None:
            return False, f"raised {type(exc).__name__}: {str(exc)[:300]}"
        ok = bool(pred(result))
        return ok, f"returned {repr(result)[:400]}"
    return Expect("returns " + desc, fn)


def either(*exps: Expect) -> Expect:
    def fn(exc, result):
        whys = []
        for e in exps:
            ok, why = e.check(exc, result)
            if ok:
                return True, why
            whys.append(why)
        return False, " / ".join(whys)
    return Expect(" or ".join(e.desc for e in exps), fn)


# ------------------------------------------------------------------------------------------------ the lane

class Lane:
    def __init__(self, module: str, engine_kw: Optional[Dict[str, Any]] = None):
        self.module = module
        self.out = run_dir(module)
        self.c = Conn(NS)
        self.engine_kw = engine_kw or {}
        self.eng = engine(self.c, **self.engine_kw)
        self._smap = None
        self.cases: List[Dict[str, Any]] = []
        self.extra: List[Conn] = []
        self.control_ok: Optional[bool] = None
        self.started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # -- connections ------------------------------------------------------------------------------------------
    def conn(self) -> Conn:
        """Another identity-checked connection (its own IRIS process). The lane keeps at most 6 open."""
        if len(self.extra) >= 5:
            raise RuntimeError("connection cap: the lane opens at most 6 connections")
        c = Conn(NS)
        self.extra.append(c)
        return c

    def drop(self, c: Conn) -> None:
        with contextlib.suppress(Exception):
            rollback_all(c.conn)
        c.close()
        if c in self.extra:
            self.extra.remove(c)

    def fresh_engine(self, **kw):
        """A new engine on the lane's main connection (a fresh strict-mode guard cache)."""
        k = dict(self.engine_kw)
        k.update(kw)
        self.eng = engine(self.c, **k)
        return self.eng

    @property
    def smap(self):
        if self._smap is None:
            self._smap = journal.storage_map(self.c)
        return self._smap

    # -- state ---------------------------------------------------------------------------------------------------
    def reset(self, ledger: bool = False, strict: bool = False) -> None:
        """Empty AUDITE through the product's own erase paths (outside every window)."""
        rollback_all(self.c.conn)
        with contextlib.suppress(Exception):
            self.eng.ledger.disable()
            self.c.conn.commit()
        self.c.call("Graph.KG.Eraser", "EraseAll")
        self.c.call("Graph.KG.Ledger", "PurgeAll")
        self.c.conn.commit()
        self.c.o.kill("IVGAuditRX")
        self._smap = None
        self.fresh_engine()
        if ledger:
            self.eng.ledger.enable(strict=strict)
            self.c.conn.commit()
            self.fresh_engine()

    def counts(self) -> Dict[str, int]:
        out = {}
        for t in ("nodes", "rdf_edges", "rdf_labels", "rdf_props"):
            out[t] = int(self.c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t}")[0][0])
        return out

    # -- oracle ------------------------------------------------------------------------------------------------
    def _window(self, fn: Callable[[], Any]):
        m = journal.mark()
        exc = None
        res = None
        tb = None
        t0 = time.time()
        try:
            res = fn()
        except BaseException as e:  # noqa: BLE001  (the outcome is data)
            if isinstance(e, KeyboardInterrupt):
                raise
            exc = e
            tb = traceback.format_exc()[-2500:]
        secs = time.time() - t0
        lvl = tlevel(self.c.conn)
        recs = journal.records_since(m, dbs={DB})
        return res, exc, tb, secs, lvl, recs

    def control(self) -> bool:
        """Positive control of the oracle: a scratch SET in the window must be seen, with its net effect."""
        res, exc, tb, secs, lvl, recs = self._window(lambda: self.c.o.set("ctl", "IVGAuditRX", "ctl"))
        seen = [r for r in recs if r["g"].startswith("^IVGAuditRX")]
        net = journal.net_effect(recs)
        self.control_ok = bool(seen) and any(g.startswith("^IVGAuditRX") for g in net) and exc is None
        self.c.o.kill("IVGAuditRX")
        self.cases.append({"case": "oracle-control", "statement": None, "ok": self.control_ok,
                           "records": len(recs), "seen": len(seen)})
        if not self.control_ok:
            raise RuntimeError("journal oracle positive control failed: a scratch write was not observed")
        return True

    def refusal(self, statement: str, case: str, fn: Callable[[], Any], expect: Expect,
                allowed: Iterable[str] = (), entry: str = "", setup_note: str = "",
                after: Optional[Callable[[], Dict[str, Any]]] = None, keep_txn: bool = False,
                caller_txn_open: bool = False, allow_nontxn_increments: bool = False) -> Dict[str, Any]:
        """Run one refused call in a journal window and record whether it refused as stated and changed nothing.

        allowed: regexes over store names ('sql:Graph_KG.LedgerStats', 'global:^IVG.Ledger') or global nodes a
        stated refusal may change (e.g. a stated rejection counter). after(): extra observations (dict).
        """
        res, exc, tb, secs, lvl, recs = self._window(fn)
        ok, why = expect.check(exc, res)
        net = journal.net_effect(recs)
        smap = self.smap
        allowed_re = [re.compile(a) for a in allowed]

        def is_allowed(node: str) -> bool:
            st = journal.store_of(node, smap)
            return any(a.search(st) or a.search(node) for a in allowed_re)

        # A node every one of whose records in the window was journaled non-transactional while its process had a
        # transaction bracket open is an IRIS $INCREMENT-style write that a rollback does not undo by design (the
        # breadth-c jcheck "increment" class: extent ID counters, ^KG("__version"), index word counts). With
        # allow_nontxn_increments such nodes are reported separately and not counted as a change of the refusal.
        nontxn: Dict[str, bool] = {}
        open_by_pid: Dict[str, int] = {}
        for r in recs:
            t = r["t"]
            if t.startswith("BeginTrans"):
                open_by_pid[r["p"]] = open_by_pid.get(r["p"], 0) + 1
                continue
            if t.startswith("CommitTrans") or t.lower().startswith("rollback"):
                continue
            if not r["g"]:
                continue
            inc = (not r["x"]) and open_by_pid.get(r["p"], 0) > 0
            nontxn[r["g"]] = nontxn.get(r["g"], True) and inc
        increments = sorted(g for g in net if allow_nontxn_increments and nontxn.get(g) and not is_allowed(g))
        changed = {g: v for g, v in net.items() if not is_allowed(g) and g not in increments}
        changed_stores = sorted({journal.store_of(g, smap) for g in changed})
        allowed_changed = sorted({g for g in net if is_allowed(g)})
        open_txn_records = [r for r in recs if r["x"]]
        units = journal.transactions(recs)
        left_open = [u for u in units if u["kind"] == "txn" and not u["committed"]]
        extra = {}
        if after is not None:
            try:
                extra = after()
            except Exception as e:  # noqa: BLE001
                extra = {"after_error": f"{type(e).__name__}: {e}"}
        if lvl and not keep_txn:
            rollback_all(self.c.conn)
        # caller_txn_open: the case deliberately runs inside a caller's transaction opened before the window, so the
        # journal shows the call's nested level (BeginTrans with a level) with no matching outer CommitTrans; that
        # bracket is expected, and the case checks $TLEVEL and the caller's write itself (observations)
        unchanged = not changed and (not left_open or caller_txn_open)
        outcome = "holds-live" if ok and unchanged else ("refused-but-changed" if ok else "not-refused-as-stated")
        rec = {
            "statement": statement, "case": case, "entry": entry, "setup": setup_note,
            "expect": expect.desc, "refused_as_stated": ok, "why": why,
            "exception": None if exc is None else {"type": type(exc).__name__, "mro": _mro_names(exc)[:5],
                                                    "message": str(exc)[:1500],
                                                    "code": getattr(exc, "code", None)},
            "returned": _jsonable(res) if exc is None else None,
            "traceback": tb if (not ok and tb) else None,
            "seconds": round(secs, 3), "tlevel_after": lvl,
            "journal": {"records": len(recs), "net_changed_nodes": len(net),
                        "changed_outside_allowed": sorted(changed)[:60], "changed_stores": changed_stores,
                        "allowed_patterns": list(allowed), "allowed_changed": allowed_changed[:20],
                        "nontxn_increments_allowed": allow_nontxn_increments,
                        "nontxn_increment_nodes": increments[:40],
                        "nontxn_nodes_all": sorted(g for g, v in nontxn.items() if v)[:40],
                        "transactional_records": len(open_txn_records),
                        "transactions_left_open": len(left_open), "caller_txn_open_expected": caller_txn_open,
                        "record_types": [r["t"] for r in recs[:12]],
                        "pids": sorted({r["p"] for r in recs})},
            "observations": extra,
            "unchanged": unchanged, "outcome": outcome,
        }
        self.cases.append(rec)
        flag = "OK " if outcome == "holds-live" else "BAD"
        print(f"[{flag}] {statement:<14} {case[:60]:<60} {outcome} recs={len(recs)} changed={changed_stores} :: "
              f"{why[:160]}", flush=True)
        return rec

    def note(self, statement: str, case: str, **data) -> Dict[str, Any]:
        """A non-refusal observation the module audit relies on (e.g. a setup fact)."""
        rec = {"statement": statement, "case": case, "outcome": "observation", **data}
        self.cases.append(_jsonable(rec))
        print(f"[obs] {statement:<14} {case[:60]:<60} {json.dumps(_jsonable(data))[:200]}", flush=True)
        return rec

    def save(self, name: str = "results.json") -> Path:
        p = self.out / name
        summary: Dict[str, Dict[str, int]] = {}
        for c in self.cases:
            if not c.get("statement"):
                continue
            summary.setdefault(c["statement"], {}).setdefault(c["outcome"], 0)
            summary[c["statement"]][c["outcome"]] += 1
        doc = {"module": self.module, "namespace": NS, "pin": PIN, "started_utc": self.started,
               "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "oracle_control_ok": self.control_ok, "summary": summary, "cases": self.cases}
        p.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
        print(f"wrote {p} ({len(self.cases)} cases)")
        return p

    def close(self) -> None:
        for c in list(self.extra):
            self.drop(c)
        with contextlib.suppress(Exception):
            rollback_all(self.c.conn)
        self.c.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except TypeError:
        if isinstance(v, dict):
            return {str(k): _jsonable(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_jsonable(x) for x in v]
        return repr(v)[:2000]


def run_cases(L: Lane, cases: List[Tuple[str, Callable[[Lane], None]]], only: Optional[List[str]] = None) -> None:
    """Run each (name, fn) case; a harness error in one case is recorded and the rest still run."""
    for name, fn in cases:
        if only and name not in only:
            continue
        try:
            fn(L)
        except Exception as e:  # noqa: BLE001
            tb = traceback.format_exc()[-3000:]
            L.cases.append({"statement": None, "case": name, "outcome": "harness-error",
                            "error": f"{type(e).__name__}: {e}", "traceback": tb})
            print(f"[ERR] {name}: {type(e).__name__}: {e}", flush=True)
            with contextlib.suppress(Exception):
                rollback_all(L.c.conn)
