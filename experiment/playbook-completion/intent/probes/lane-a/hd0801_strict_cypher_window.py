"""HD-0801 probe: does a running engine refuse a Cypher write as soon as ledger strict mode is turned on?

Contract under test: specs/213-graph-revision-ledger/contracts/ledger-api.md:82-92 (pin 3eaa79cf): "When the ledger is
enabled with `strict=True`, these existing calls raise `LedgerStrictModeError` and change nothing: ... `execute_cypher`
with any updating clause". No window and no fail-open case is stated. As built, the Python LedgerGuard caches
Graph.KG.Ledger.Meta() for TTL_SECONDS = 5.0 per engine (iris_vector_graph/ledger/guard.py:20,38-59).

Steps (connection c1 = the long-lived application engine E1; c2 = the admin engine E2; c3 = a fresh engine E3):
  1. E2 enables the ledger (strict off). E1 runs a Cypher CREATE in graph ia-0801 (warms E1's guard cache).
  2. E2 set_strict(True); Meta() confirms strict=true.
  3. E1, inside its cache window, runs a Cypher CREATE and a create_node.
  4. E3 (fresh guard) runs a Cypher CREATE.
  5. after the TTL, E1 runs a Cypher CREATE again.
Oracle:
  step 3 refused and nothing written        -> contract holds (no window)              -> pass
  step 3 succeeds while Meta says strict     -> product violates the stated contract    -> fail (window reading, as built)
  step 4 and 5 refused                       -> the guard does enforce once the cache is fresh (expected either way)
Then ledger.verify() is asked whether the bypassing rows are reported as unrecorded writes (detection after the fact).
Restore (finally): strict off, probe graph erased, ledger disabled (AUDITIA was "never-enabled"; a genesis cannot be
undone through the public API, so the namespace is left "disabled", strict off).
"""
from __future__ import annotations

import time

import _common as C

from iris_vector_graph.ledger import LedgerStrictModeError

G = "ia-0801"


def cypher_create(e, nid):
    t = time.monotonic()
    try:
        r = e.execute_cypher(f"USE GRAPH '{G}' CREATE (:IaT0801 {{id: '{nid}'}})")
        return {"outcome": "accepted", "error": getattr(r, "error", None), "t": t}
    except LedgerStrictModeError as ex:
        return {"outcome": "refused", "error": str(ex)[:160], "t": t}


def rows(c, nid):
    return c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ? AND graph_id = ?", nid, G)[0][0]


def main():
    c1, c2, c3 = C.conn(), C.conn(), None
    e1, e2 = C.engine(c1), C.engine(c2)
    prior = e2.ledger.meta()
    C.obs(step="prior_meta", meta=prior)
    enabled_here = False
    verdict = ("incomplete", "did not finish")
    try:
        if prior.get("state") != "enabled":
            e2.ledger.enable(strict=False)
            enabled_here = True
        C.obs(step="enabled", meta=e2.ledger.meta())
        w0 = cypher_create(e1, "ia0801:w0")
        C.obs(step="warm_e1_cache", **w0, rows=rows(c1, "ia0801:w0"))
        e2.ledger.set_strict(True)
        t_strict = time.monotonic()
        meta = e2.ledger.meta()
        C.obs(step="strict_on", meta=meta, since_e1_probe_s=round(t_strict - w0["t"], 3))
        w1 = cypher_create(e1, "ia0801:w1")
        C.obs(step="e1_cypher_in_window", outcome=w1["outcome"], error=w1["error"],
              since_e1_probe_s=round(w1["t"] - w0["t"], 3), rows=rows(c1, "ia0801:w1"),
              meta_strict=e2.ledger.meta().get("strict"))
        try:
            e1.create_node("ia0801:n1", labels=["IaT0801"], graph=G)
            n1 = "accepted"
        except LedgerStrictModeError:
            n1 = "refused"
        C.obs(step="e1_create_node_in_window", outcome=n1, rows=rows(c1, "ia0801:n1"))
        c3 = C.conn()
        e3 = C.engine(c3)
        w3 = cypher_create(e3, "ia0801:w3")
        C.obs(step="fresh_engine_cypher", outcome=w3["outcome"], error=w3["error"], rows=rows(c1, "ia0801:w3"))
        wait = max(0.0, 5.0 - (time.monotonic() - w0["t"])) + 0.6
        time.sleep(wait)
        w5 = cypher_create(e1, "ia0801:w5")
        C.obs(step="e1_cypher_after_ttl", outcome=w5["outcome"], error=w5["error"],
              since_e1_probe_s=round(w5["t"] - w0["t"], 3), rows=rows(c1, "ia0801:w5"))
        bypass = c1.sql("SELECT node_id FROM Graph_KG.nodes WHERE graph_id = ? ORDER BY node_id", G)
        C.obs(step="rows_in_probe_graph_while_strict", rows=[r[0] for r in bypass])
        try:
            rep = e2.ledger.verify()
            C.obs(step="verify", report=repr(rep)[:1500])
        except Exception as ex:  # noqa: BLE001
            C.obs(step="verify", error=f"{type(ex).__name__}: {str(ex)[:300]}")
        window = w1["outcome"] == "accepted" and rows(c1, "ia0801:w1") == 1
        enforced_later = w3["outcome"] == "refused" and w5["outcome"] == "refused"
        if window:
            verdict = ("fail", f"a Cypher CREATE from an engine whose guard cache was {round(w1['t'] - w0['t'], 2)} s old "
                               f"was accepted and wrote a row while Meta() said strict=true (create_node: {n1}); fresh "
                               f"engine: {w3['outcome']}; same engine after TTL: {w5['outcome']} -> contract 'raise and "
                               "change nothing' violated inside the 5 s cache window")
        elif enforced_later:
            verdict = ("pass", "Cypher CREATE refused immediately after strict mode was turned on")
        else:
            verdict = ("incomplete", f"unexpected: in-window {w1['outcome']}, fresh {w3['outcome']}, after-ttl {w5['outcome']}")
    finally:
        try:
            if e2.ledger.meta().get("state") == "enabled":
                e2.ledger.set_strict(False)
        except Exception as ex:  # noqa: BLE001
            C.obs(step="restore_strict_error", error=str(ex)[:200])
        e2._ledger_guard.refresh()
        C.obs(step="erase_probe_graph", removed=e2.erase_graph(G))
        if enabled_here:
            e2.ledger.disable()
        C.obs(step="restored_meta", meta=e2.ledger.meta(),
              note="AUDITIA was never-enabled; after this probe it is 'disabled' with strict off (a genesis cannot be "
                   "removed through the public API)" if enabled_here else "ledger state left as found")
        for c in (c1, c2, c3):
            if c is not None:
                c.close()
    C.verdict(*verdict)


if __name__ == "__main__":
    main()
