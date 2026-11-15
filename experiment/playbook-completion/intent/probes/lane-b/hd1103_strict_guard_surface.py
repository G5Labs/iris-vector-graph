"""HD-1103 probe: what strict mode refuses at the pin (client-side guard, its 5 s cache, unguarded Python paths).

Run under the EXCLUSIVE lane lock. Pin API only.
  1. guarded call (create_node) under strict -> LedgerStrictModeError (ledger-api.md:84-91)
  2. bulk_delete_adjacency under strict (not in the contract's list; F-1108) -> as built: deletes the edge row
  3. guard TTL: engine A caches "not strict"; engine B (another process) sets strict; A's guarded write inside 5 s passes
     (guard.py:3-6,38-41, TTL_SECONDS=5.0); after the TTL it is refused
  4. server-side writer under strict: raw SQL INSERT (documented unguarded, ledger-api.md:93)
Discriminates HD-1103's readings: (a) client-side fail-open guard on listed calls  vs  (b) server-side barrier
(would refuse 2, 3 and 4)  vs  (c) fail-closed client guard (changes only the unreadable-state case, not probed live).
Stated contracts: ledger-api.md:84-93 (list + "BulkLoader and raw SQL are not guarded"); USER_GUIDE.md:1107-1109
("create_node, create_edge and the other methods ... Strict mode refuses them").
"""
import time

from _ib3_common import Conn, engine_on, meta, out, purge_ledger, cleanup, foreign_rows

from iris_vector_graph.ledger import LedgerStrictModeError


def main():
    c1 = Conn("AUDITIB")
    c2 = Conn("AUDITIB")
    try:
        out("foreign rows at start", foreign_rows(c1))
        cleanup(c1)
        a = engine_on(c1)
        b = engine_on(c2)
        a.create_node("ib3_s_a")
        a.create_node("ib3_s_b")
        a.create_edge("ib3_s_a", "IB3REL", "ib3_s_b")
        a.ledger.enable(strict=True)
        out("meta", meta(c1))
        r = {}
        try:
            a.create_node("ib3_s_guarded")
            r["1 create_node under strict"] = "WRITTEN"
        except LedgerStrictModeError:
            r["1 create_node under strict"] = "refused LedgerStrictModeError"
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                n = a.bulk_delete_adjacency(["ib3_s_a"])
            left = c1.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = 'ib3_s_a'")[0][0]
            r["2 bulk_delete_adjacency under strict"] = f"accepted (returned {n}); edge rows left {left}"
        except LedgerStrictModeError:
            r["2 bulk_delete_adjacency under strict"] = "refused LedgerStrictModeError"
        v = a.ledger.verify()
        r["2b verify after it"] = (v.result, v.classification, [(d.entity_kind, d.attr, d.before, d.after) for d in v.differences][:4])

        # 3. TTL: A probes now (strict off), B sets strict, A writes within the TTL
        b.ledger.set_strict(False)
        a._ledger_guard.refresh()
        r["3a A guard is_strict (cached now)"] = a._ledger_guard.is_strict()
        b.ledger.set_strict(True)
        t0 = time.monotonic()
        try:
            ok = a.create_node("ib3_s_ttl")
            r["3b A create_node right after B set strict"] = f"WRITTEN={ok} at +{time.monotonic() - t0:.2f}s"
        except LedgerStrictModeError:
            r["3b A create_node right after B set strict"] = "refused"
        time.sleep(5.5)
        try:
            a.create_node("ib3_s_ttl2")
            r["3c A create_node after 5.5 s"] = "WRITTEN"
        except LedgerStrictModeError:
            r["3c A create_node after 5.5 s"] = "refused LedgerStrictModeError"

        # 4. raw SQL (documented unguarded)
        c1.sql("INSERT INTO Graph_KG.nodes (node_id, graph_id) VALUES ('ib3_s_rawsql', '')")
        r["4 raw SQL INSERT under strict"] = "written" if c1.sql(
            "SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'ib3_s_rawsql'")[0][0] else "not written"
        for k, val in r.items():
            out(k, val)
        out("VERDICT reading (a) client-side guard on listed calls with TTL",
            r["1 create_node under strict"].startswith("refused") and r["3b A create_node right after B set strict"].startswith("WRITTEN")
            and r["3c A create_node after 5.5 s"].startswith("refused"))
        out("VERDICT reading (b) server-side barrier", r["2 bulk_delete_adjacency under strict"].startswith("refused")
            and r["4 raw SQL INSERT under strict"] == "not written")
        out("VERDICT USER_GUIDE 'the other methods' refused (F-1108 bulk_delete_adjacency)",
            "holds" if r["2 bulk_delete_adjacency under strict"].startswith("refused") else "VIOLATED")
    finally:
        cleanup(c1)
        c1.close()
        c2.close()


if __name__ == "__main__":
    main()
