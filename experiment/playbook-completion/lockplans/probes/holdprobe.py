"""A lock-hold probe in the style of correspondence/tools/lockplan.py, for namespace AUDITD (at most 4 connections).

A probe process P holds a lock (or nothing), product operations start in other connections in threads (each at its
own delay into the hold), an observer samples their process state (%SYS.ProcessQuery) and the lock table
(%SYS.LockQuery_List()), reads a `during` snapshot, takes a journal mark, and releases. After the operations end the
observer reads an `after` snapshot. The journal (traces/journal.py) gives each operation's records before and after
the release mark, by pid, as an independent oracle of what it wrote while P held.
"""
from __future__ import annotations

import threading
import time

import lpcommon as L
import journal  # noqa: E402  (PC/traces, on the path via lpcommon)


class Side:
    """One identity-checked connection with its engine and store."""

    def __init__(self, c=None):
        self.c = c or L.conn()
        self.e = L.engine(self.c)
        self._s = None

    @property
    def s(self):
        if self._s is None:
            self._s = L.store(self.c)
        return self._s

    @property
    def o(self):
        return self.c.o

    def close(self):
        self.c.close()


def roots(recs):
    return sorted({journal.global_root(r["g"]) for r in recs if r.get("g")})


def run(name, *, lock=None, mode="", hold=3.0, setup=None, ops=(), during=None, after=None, expect="",
        lock_needles=("IVG", "NKG", "Graph.KG", "Graph_KG", "KG("), release_when=None, max_hold=None):
    """ops: list of (tag, delay_s, fn(side) -> value, nested: bool). `nested` opens a caller transaction first (SQL
    START TRANSACTION) and leaves it open; `end_nested` in the result tells how it was ended (COMMIT after the op)."""
    obs = Side()
    res = {"probe": name, "lock": None if lock is None else [lock[0], list(lock[1])], "mode": mode, "hold_s": hold,
           "expect": expect}
    try:
        L.reset(obs.c)
        if setup:
            res["setup"] = setup(obs)
            obs.c.conn.commit()
        sides = {tag: Side() for tag, *_ in ops}
        P = Side() if lock is not None else None
        res["pids"] = {"obs": obs.c.pid, **({"P": P.c.pid} if P else {}), **{t: s.c.pid for t, s in sides.items()}}
        m0 = journal.mark()
        if P:
            g, subs = lock
            P.o.lock(mode, 1, g, *subs)
        done = {}
        t0 = time.time()

        def work(tag, delay, fn, nested):
            time.sleep(delay)
            sd = sides[tag]
            t = time.time()
            try:
                if nested:
                    sd.c.sql("START TRANSACTION")
                v = fn(sd)
                err = getattr(v, "error", None)
                done[tag] = {"ok": not (isinstance(err, str) and err), "answer": str(getattr(v, "rows", v))[:600]}
                if isinstance(err, str) and err:
                    done[tag]["error"] = err[:400]
            except Exception as ex:  # noqa: BLE001
                done[tag] = {"ok": False, "error": f"{type(ex).__name__}: {str(ex)[:400]}"}
            done[tag]["started_s"] = round(t - t0, 2)
            done[tag]["returned_s"] = round(time.time() - t0, 2)
        ths = [threading.Thread(target=work, args=(tag, d, fn, nested)) for tag, d, fn, nested in ops]
        for th in ths:
            th.start()
        samples = []
        while time.time() - t0 < (max_hold if release_when else hold):
            if release_when and time.time() - t0 >= hold and release_when(obs, sides, done):
                break
            time.sleep(0.5)
            samples.append({"t": round(time.time() - t0, 2),
                            **{tag: {"returned": tag in done, **L.proc_state(obs.c, sides[tag].c.pid)} for tag in sides}})
        res["state_while_held"] = samples
        pids = {s.c.pid for s in sides.values()} | ({P.c.pid} if P else set())
        res["locks_while_held"] = [r for r in L.lock_table(obs.c, pids=pids)] + \
            [r for r in L.lock_table(obs.c, needle="IVG") if r["owner"] not in pids][:10]
        res["returned_before_release"] = sorted(done)
        if during:
            res["during"] = during(obs)
        m_rel = journal.mark()
        res["released_at_s"] = round(time.time() - t0, 2)
        if P:
            P.o.releaseAllLocks()
        for th in ths:
            th.join(120)
        res["ops"] = done
        res["locks_after_ops"] = L.lock_table(obs.c, pids=pids)
        for tag, d, fn, nested in ops:
            if nested:
                try:
                    sides[tag].c.sql("COMMIT")
                    res.setdefault("nested_end", {})[tag] = "COMMIT"
                except Exception as ex:  # noqa: BLE001
                    res.setdefault("nested_end", {})[tag] = f"COMMIT failed: {str(ex)[:200]}"
        if after:
            res["after"] = after(obs)
        jr = {}
        for tag, s in sides.items():
            recs = journal.records_since(m0, dbs={L.DB}, pids={s.c.pid})
            before = [r for r in recs if r["a"] <= m_rel.address]
            jr[tag] = {"records": len(recs), "before_release": len(before), "roots_before_release": roots(before),
                       "roots_total": roots(recs),
                       "nodes_before_release": sorted({r["g"][:100] for r in before if r.get("g")})[:40]}
        res["journal"] = jr
        for s in list(sides.values()) + ([P] if P else []):
            s.close()
    finally:
        try:
            L.reset(obs.c)
        except Exception as ex:  # noqa: BLE001
            res["final_reset_error"] = str(ex)[:200]
        obs.close()
    return res


def gget(side, *node):
    """A global's value or None (Native API, read uncommitted)."""
    try:
        if int(side.o.isDefined(*node)) % 10 == 1:
            v = side.o.get(*node)
            return None if v is None else str(v)
    except Exception as ex:  # noqa: BLE001
        return f"<error {str(ex)[:80]}>"
    return None


def defined(side, *node) -> int:
    return int(side.o.isDefined(*node))
