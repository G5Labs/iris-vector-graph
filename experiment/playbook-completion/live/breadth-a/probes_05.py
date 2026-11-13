"""Live checks of module 05 (temporal) findings in AUDITA that need no ledger. See probe_lib for the rules."""
from __future__ import annotations

import json
import sys
import time

from probe_lib import Result, engine, erase, gname, run

ROW = "SELECT qualifiers FROM Graph_KG.rdf_edges WHERE graph_id = ? AND s = ? AND p = ? AND o_id = ?"


def p0501_update_double_counts_bucket(r: Result):
    """F-0501: an update-mode write at the same coordinates adds the edge to the bucket aggregate again.
    Oracle: CONTEXT.md:173-177 (an upsert replaces the edge) and the docstring (aggregates keep the original value)."""
    c, eng = engine()
    g = gname("tb")
    try:
        eng.create_edge_temporal("s", "P", "o", timestamp=1000, weight=1.0, graph=g)
        eng.create_edge_temporal("s", "P", "o", timestamp=1000, weight=5.0, upsert=True, graph=g)
        r.obs("tout_weight", str(c.o.get("^KG", "tout", g, 1000, "s", "P", "o")))
        # bucket 3 is [900, 1199]: the window holds it whole, so the pre-aggregate answers
        cnt = r.obs("whole_bucket_count", eng.get_temporal_aggregate("s", "P", "count", 900, 1199, graph=g))
        sm = r.obs("whole_bucket_sum", eng.get_temporal_aggregate("s", "P", "sum", 900, 1199, graph=g))
        r.obs("cut_window_count", eng.get_temporal_aggregate("s", "P", "count", 950, 1100, graph=g))
        r.obs("tagg_count", str(c.o.get("^KG", "tagg", g, 3, "s", "P", "count")))
        eng.delete_edge_temporal("s", "P", "o", 1000, graph=g)
        r.obs("bucket_counter_after_delete", str(c.o.get("^KG", "bucket", g, 3, "s")))
        r["oracle"] = "whole-bucket count equals the edges at its coordinates (1) and sum their weights"
        r["reproduced"] = cnt == 2
        r["verdict"] = f"count {cnt}, sum {sm} for one edge" if r["reproduced"] else "aggregate correct"
    finally:
        erase(eng, g)
        c.close()


def p0502_missing_time_is_epoch_zero(r: Result):
    """F-0502: create_edge_temporal(timestamp=None) stores the edge at ts 0; the batch path turns an explicit ts 0
    into now. Oracle: InsertEdge's own rule (a missing time is now, TemporalIndex.cls:51)."""
    c, eng = engine()
    g = gname("t0")
    try:
        eng.create_edge_temporal("s", "P", "o", graph=g)
        r.obs("single_stored_at_0", int(c.o.isDefined("^KG", "tout", g, 0, "s", "P", "o")))
        eng.bulk_create_edges_temporal([{"s": "s2", "p": "P", "o": "o2", "ts": 0}], graph=g)
        r.obs("batch_stored_at_0", int(c.o.isDefined("^KG", "tout", g, 0, "s2", "P", "o2")))
        first = c.o.classMethodValue("%SYSTEM.SQL", "DATEDIFF", "ss", "1970-01-01 00:00:00", "2026-01-01 00:00:00")
        ts = c.sql(f"SELECT 1")  # noqa: F841 - keeps the connection's SQL process warm for the order below
        nxt = r.obs("batch_first_ts", str(c.o.nextSubscript(False, "^KG", "tout", g, 0)))
        r["oracle"] = "a missing time means now on every path; an explicit 0 means 0"
        r["reproduced"] = bool(r["observed"]["single_stored_at_0"]) and not r["observed"]["batch_stored_at_0"]
        r["verdict"] = (f"single write stored at 0; batch ts 0 stored at {nxt} (>{first})"
                        if r["reproduced"] else "consistent")
    finally:
        erase(eng, g)
        c.close()


def p0505_marker_predicate(r: Result):
    """F-0505: an explicit create_edge with qualifiers {"temporal": 1} is deleted by the last temporal delete on its
    triple (IsTemporalMarked accepts 1); the ledger and create_edge's adopt treat only JSON true as the mark."""
    c, eng = engine()
    g = gname("mk")
    try:
        eng.create_node("a", graph=g)
        eng.create_node("b", graph=g)
        eng.create_edge("a", "R", "b", qualifiers={"temporal": 1}, graph=g)
        r.obs("explicit_row", c.sql(ROW, g, "a", "R", "b"))
        eng.create_edge_temporal("a", "R", "b", timestamp=100, graph=g)
        eng.delete_edge_temporal("a", "R", "b", 100, graph=g)
        left = r.obs("row_after_last_temporal_delete", c.sql(ROW, g, "a", "R", "b"))
        r["oracle"] = "an explicitly written edge (not JSON-true marked) survives the temporal side (ADR-0009)"
        r["reproduced"] = not left
        r["verdict"] = "explicit edge with temporal:1 deleted by the temporal delete" if not left else "kept"
    finally:
        erase(eng, g)
        c.close()


def p0304_store_edge_does_not_adopt(r: Result):
    """F-0304 with its discriminating control: over a temporal (marked) row, create_edge adopts (clears the mark) and
    the edge survives the last temporal delete; store_edge swallows the duplicate, keeps the mark, and the edge is
    deleted. Oracle: ADR-0009 (an explicit structural create takes the edge over)."""
    c, eng = engine()
    g = gname("ad")
    try:
        out = {}
        for writer in ("create_edge", "store_edge"):
            s, o = f"{writer}_s", f"{writer}_o"
            eng.create_edge_temporal(s, "R", o, timestamp=100, graph=g)
            before = c.sql(ROW, g, s, "R", o)
            getattr(eng, writer)(s, "R", o, graph=g)
            mid = c.sql(ROW, g, s, "R", o)
            eng.delete_edge_temporal(s, "R", o, 100, graph=g)
            out[writer] = {"marked_row": before, "after_explicit_write": mid,
                           "after_last_temporal_delete": c.sql(ROW, g, s, "R", o)}
        r.obs("paths", out)
        r["oracle"] = "an explicitly written edge survives the last temporal delete (ADR-0009, CONTEXT.md:66-73)"
        r["reproduced"] = bool(out["create_edge"]["after_last_temporal_delete"]) and \
            not out["store_edge"]["after_last_temporal_delete"]
        r["verdict"] = ("create_edge's edge survives (control), store_edge's edge is deleted"
                        if r["reproduced"] else "not reproduced")
    finally:
        erase(eng, g)
        c.close()


def p0507_purge_wipes_all_graphs(r: Result):
    """F-0507: Graph.KG.TemporalIndex.Purge() kills every graph's temporal stores and retracts no marked row; the
    rows then outlive every timestamp and purge_before cannot find them."""
    c, eng = engine()
    g1, g2 = gname("pa"), gname("pb")
    try:
        eng.create_edge_temporal("a", "R", "b", timestamp=100, graph=g1)
        eng.create_edge_temporal("c", "R", "d", timestamp=100, graph=g2)
        r.obs("rows_before", c.sql("SELECT graph_id, qualifiers FROM Graph_KG.rdf_edges WHERE graph_id IN (?, ?)", g1, g2))
        c.o.classMethodVoid("Graph.KG.TemporalIndex", "Purge")  # declared with no return type
        r.obs("tout_g1_after", int(c.o.isDefined("^KG", "tout", g1)))
        r.obs("tout_g2_after", int(c.o.isDefined("^KG", "tout", g2)))
        rows = r.obs("rows_after_purge", c.sql("SELECT graph_id, qualifiers FROM Graph_KG.rdf_edges WHERE graph_id IN (?, ?)", g1, g2))
        r.obs("purge_before_removed", eng.purge_before(10_000_000_000))
        rows2 = r.obs("rows_after_purge_before", c.sql("SELECT graph_id FROM Graph_KG.rdf_edges WHERE graph_id IN (?, ?)", g1, g2))
        r.obs("out_g1_after", int(c.o.isDefined("^KG", "out", g1, "a", "R", "b")))
        r["oracle"] = "ADR-0009 amendment: the marked row goes when the triple's last timestamp goes, in every graph"
        r["reproduced"] = len(rows) == 2 and len(rows2) == 2
        r["verdict"] = "both graphs' temporal stores wiped; marked rows and adjacency survive every purge" \
            if r["reproduced"] else "rows retracted"
    finally:
        erase(eng, g1, g2)
        c.close()


def p0508_burst_predicate_ignored(r: Result):
    """F-0508: find_burst_nodes(predicate="B") counts edges of predicate A (the argument is not read)."""
    c, eng = engine()
    g = gname("bu")
    now = int(time.time())
    try:
        eng.bulk_create_edges_temporal([{"s": "hub", "p": "A", "o": f"t{i}", "ts": now - 10} for i in range(5)],
                                       graph=g)
        got = r.obs("bursts_for_B", eng.find_burst_nodes(predicate="B", window_seconds=300, threshold=3,
                                                           now_ts=now, graph=g))
        r["oracle"] = "Args: predicate filters to edges with this predicate (temporal.py docstring)"
        r["reproduced"] = any(x.get("id") == "hub" for x in got)
        r["verdict"] = "hub reported as a burst of predicate B with only A edges" if r["reproduced"] else "filtered"
    finally:
        erase(eng, g)
        c.close()


def p0509_label_set_json(r: Result):
    """F-0509: InternLabelSet writes keys and string values unescaped, so a value holding a quote resolves to text
    that is not JSON."""
    c, eng = engine()
    try:
        h = r.obs("hash", eng.intern_label_set({"k": 'a"b'}))
        txt = r.obs("resolved", eng.resolve_label_set(h))
        try:
            json.loads(txt)
            ok = True
        except Exception as e:
            ok = False
            r.obs("json_error", str(e))
        r["oracle"] = "the canonical form of a label set is JSON (spec 204 FR-012)"
        r["reproduced"] = not ok
        r["verdict"] = "resolved text is not JSON" if not ok else "valid JSON"
    finally:
        c.close()


def p0510_ms_index_now_in_seconds(r: Result):
    """F-0510: Graph.KG.TemporalIndexMS.InsertEdge with no time stores the edge at "now" in seconds, not ms."""
    c, eng = engine()
    g = gname("ms")
    try:
        c.call("Graph.KG.TemporalIndexMS", "InsertEdge", g, "s", "P", "o", "")
        ts = r.obs("stored_ts", int(str(c.o.nextSubscript(False, "^KG", "tout", g, ""))))
        now_ms = int(time.time() * 1000)
        r.obs("now_ms", now_ms)
        r["oracle"] = "TSUNIT=ms: a missing time is now in milliseconds"
        r["reproduced"] = ts < now_ms / 100
        r["verdict"] = f"stored at {ts} (seconds scale) instead of ~{now_ms}" if r["reproduced"] else "ms"
    finally:
        erase(eng, g)
        c.close()


def p0512_suppress_reverse_field(r: Result):
    """F-0512: BulkInsertCounts with the spec's field name suppress_reverse still writes the reverse index; only
    "sri" suppresses it."""
    c, eng = engine()
    g = gname("sr")
    try:
        batch = [{"s": "a", "p": "P", "o": "b", "ts": 100, "suppress_reverse": 1},
                 {"s": "c", "p": "P", "o": "d", "ts": 100, "sri": 1}]
        r.obs("result", str(c.call("Graph.KG.TemporalIndex", "BulkInsertCounts", g, json.dumps(batch))))
        tin_spec = r.obs("tin_written_with_suppress_reverse", int(c.o.isDefined("^KG", "tin", g, 100, "b", "P", "a")))
        r.obs("tin_written_with_sri", int(c.o.isDefined("^KG", "tin", g, 100, "d", "P", "c")))
        r["oracle"] = "spec 204 FR-009: suppress_reverse suppresses the reverse index"
        r["reproduced"] = bool(tin_spec)
        r["verdict"] = "suppress_reverse ignored; reverse index written" if tin_spec else "suppressed"
    finally:
        erase(eng, g)
        c.close()


def p0513_validation_paths(r: Result):
    """F-0513: a negative weight is refused by create_edge_temporal (with a timestamp) and stored by the batch path
    and by create_edge_temporal without a timestamp."""
    c, eng = engine()
    g = gname("va")
    try:
        try:
            eng.create_edge_temporal("a", "P", "b", timestamp=100, weight=-1.0, graph=g)
            r.obs("single_with_ts", "stored")
        except Exception as e:
            r.obs("single_with_ts", f"{type(e).__name__}")
        try:
            eng.create_edge_temporal("a2", "P", "b2", weight=-1.0, graph=g)
            r.obs("single_without_ts", "stored")
        except Exception as e:
            r.obs("single_without_ts", f"{type(e).__name__}")
        try:
            r.obs("batch", str(eng.bulk_create_edges_temporal([{"s": "c", "p": "P", "o": "d", "ts": 100, "w": -1.0}],
                                                              graph=g)))
        except Exception as e:
            r.obs("batch", f"{type(e).__name__}: {e}")
        r.obs("batch_weight_stored", str(c.o.get("^KG", "tout", g, 100, "c", "P", "d")))
        r["oracle"] = "every temporal write path refuses weight < 0 (TemporalEdgeInput, _validate.py:207-227)"
        r["reproduced"] = r["observed"]["single_with_ts"] != "stored" and float(r["observed"]["batch_weight_stored"]) == -1.0
        r["verdict"] = ("refused with a timestamp; stored without one and on the batch path" if r["reproduced"]
                        else "consistent")
    finally:
        erase(eng, g)
        c.close()


def pC0501_refused_temporal_write_is_partial(r: Result):
    """New (static candidate from the footprint sub-lane): TemporalIndex.WriteStores writes tout/tin/bucket/latest
    before Adjacency.AssertTemporalRow, with no transaction of its own; when the structural row is refused (a predicate
    over rdf_edges.p's width) the call raises yet the temporal stores keep the edge. Oracle: create_edge_temporal's
    docstring "A write IRIS refuses raises GraphWriteError and writes nothing"."""
    c, eng = engine()
    g = gname("pt")
    p = "P" * 140
    try:
        try:
            eng.create_edge_temporal("s", p, "o", timestamp=100, graph=g)
            r.obs("call", "returned")
        except Exception as e:
            r.obs("call", f"raised {type(e).__name__}: {str(e)[:250]}")
        left = {k: int(c.o.isDefined("^KG", k, g)) for k in ("tout", "tin", "bucket", "tagg")}
        r.obs("temporal_stores_left", left)
        r.obs("tout_entry", int(c.o.isDefined("^KG", "tout", g, 100, "s", p, "o")))
        r.obs("rows", c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ?", g)[0][0])
        r["oracle"] = "a refused temporal write raises and writes nothing (temporal.py create_edge_temporal docstring)"
        r["reproduced"] = r["observed"]["call"].startswith("raised") and r["observed"]["tout_entry"] == 1
        r["verdict"] = "raised, yet the temporal index holds the edge" if r["reproduced"] else "nothing written"
    finally:
        erase(eng, g)
        c.close()


PROBES = {f.__name__: f for f in (pC0501_refused_temporal_write_is_partial, p0501_update_double_counts_bucket, p0502_missing_time_is_epoch_zero,
                                  p0505_marker_predicate, p0304_store_edge_does_not_adopt,
                                  p0507_purge_wipes_all_graphs, p0508_burst_predicate_ignored, p0509_label_set_json,
                                  p0510_ms_index_now_in_seconds, p0512_suppress_reverse_field,
                                  p0513_validation_paths)}

if __name__ == "__main__":
    sys.exit(run("05", PROBES, sys.argv[1:]))
