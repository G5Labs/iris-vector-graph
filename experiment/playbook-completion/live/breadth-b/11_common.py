"""Module 11 (ledger core) live-check helpers on AUDITB (scratch ids b11_*, graphs b11g*).

Every script that imports this runs under `bash experiment/playbook-completion/tools/locks.sh iris python ...`;
blive.session then also takes the lane-B lock. Namespace-wide ledger state is restored by `finish()`: strict off and
the ledger reset to never-enabled with the pin's own test/admin reset Graph.KG.Ledger.PurgeAll
(iris_src/src/Graph/KG/Ledger.cls:241-248: Kill ^IVG.Ledger and %KillExtent of LedgerRevision and LedgerStats;
nothing else), so other lane-B workers' writes never meet the strict guard.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import *  # noqa: F401,F403,E402
import blive  # noqa: E402

L = "Graph.KG.Ledger"
S = "Graph_KG"


def meta(c):
    return json.loads(str(c.call(L, "Meta")))


def purge(c):
    """The pin's test/admin ledger reset (Ledger.cls:241-248)."""
    return str(c.call(L, "PurgeAll"))


def stats_row(c):
    rows = c.sql("SELECT commits_ok, replays_idem, rej_stale_head, rej_unknown_head, rej_idem_conflict, "
                 "rej_failed_op, rej_strict_block, rej_size_limit, rej_disabled, rej_lock_timeout, state, strict, "
                 "head_seq FROM Graph_KG.ledger_stats")
    if not rows:
        return None
    k = ["commits_ok", "replays_idem", "rej_stale_head", "rej_unknown_head", "rej_idem_conflict", "rej_failed_op",
         "rej_strict_block", "rej_size_limit", "rej_disabled", "rej_lock_timeout", "state", "strict", "head_seq"]
    return dict(zip(k, rows[0]))


def revisions(c):
    return [tuple(r) for r in c.sql("SELECT seq, kind, actor, op_count, source, idempotency_key "
                                    "FROM Graph_KG.ledger_revisions ORDER BY seq")]


def records(c, seq):
    out = []
    o = c.o
    i = ""
    while True:
        i = o.nextSubscript(False, "IVG.Ledger", "rec", seq, i)
        if i is None or i == "":
            break
        out.append(str(o.get("IVG.Ledger", "rec", seq, i)))
    return out


def scrub(c):
    """Remove every b11 row in every graph (edges first, FK order); SQL keeps ^KG in step (functional indexes)."""
    done = {}
    for t, col in (("rdf_edges", "s"), ("rdf_edges", "o_id"), ("rdf_labels", "s"), ("rdf_props", "s"),
                   ("kg_NodeEmbeddings", "node_id"), ("nodes", "node_id")):
        try:
            done[f"{t}.{col}"] = c.sql(f"DELETE FROM {S}.{t} WHERE {col} %STARTSWITH 'b11'")
        except Exception as e:  # noqa: BLE001
            done[f"{t}.{col}"] = f"error: {e}"[:200]
    return done


def counts(c):
    out = {}
    for t, col in (("nodes", "node_id"), ("rdf_labels", "s"), ("rdf_props", "s"), ("rdf_edges", "s")):
        out[t] = c.sql(f"SELECT COUNT(*) FROM {S}.{t} WHERE {col} %STARTSWITH 'b11'")[0][0]
    return out


def diffs(report, prefix="b11"):
    """Verification differences that concern b11 entities (other lanes' scratch rows are ignored)."""
    out = []
    for d in report.differences:
        if prefix in str(d.entity_id) or prefix in str(d.before) or prefix in str(d.after):
            out.append({"kind": d.entity_kind, "id": str(d.entity_id)[:200], "attr": d.attr,
                        "before": d.before, "after": d.after})
    return out


def net_effect_bits(records_):
    """Net effect per node handling SET/KILL/ZKILL and BitSET (journal.net_effect treats BitSET as a kill)."""
    first, last, bits = {}, {}, {}
    for r in records_:
        g = r["g"]
        if not g:
            continue
        if r["t"].lower() == "bitset":
            n = base64.b64decode(r["n"]).decode() if r["n"] else "0"
            o = base64.b64decode(r["o"]).decode() if r["o"] else "0"
            bits[g] = bits.get(g, 0) + (1 if (n, o) == ("1", "0") else -1 if (n, o) == ("0", "1") else 0)
            continue
        if g not in first:
            first[g] = r["o"]
        last[g] = r["n"] if r["t"] == "SET" else None
    out = {g: v for g, v in last.items() if v != first[g]}
    out.update({g + " [bits]": v for g, v in bits.items() if v})
    return out


def analyse(cap, smap, pid=None):
    """Stores written, transactions and non-transactional writes of one capture (per process when pid given)."""
    recs = [r for r in cap.records if pid is None or r["p"] == pid]
    tx = blive.J.transactions(recs)
    units = []
    for u in tx:
        st = sorted({blive.J.store_of(r["g"], smap) for r in u["records"] if r["g"]})
        if not st:
            continue
        units.append({"pid": u["pid"], "kind": u["kind"], "committed": u["committed"],
                      "net_empty": bool(u["records"]) and not net_effect_bits(u["records"]),
                      "nested_levels": u.get("nested_levels", 0), "n": len(u["records"]), "stores": st,
                      "nodes": sorted({r["g"].split("(")[0] + ("(" + r["g"].split("(")[1].split(",")[0] if "(" in r["g"] else "")
                                       for r in u["records"] if r["g"]})[:40]})
    outside = [{"pid": r["p"], "t": r["t"], "store": blive.J.store_of(r["g"], smap), "g": r["g"][:160]}
               for r in recs if r["g"] and not r["x"]]
    return {"stores": sorted({blive.J.store_of(r["g"], smap) for r in recs if r["g"]}), "units": units,
            "outside_txn": outside, "n_records": len(recs), "error": cap.error,
            "result": str(cap.result)[:600]}


def finish(s, note=""):
    """Leave the namespace-wide ledger as other workers expect: strict off, never-enabled; b11 rows removed."""
    out = {}
    try:
        m = meta(s.c)
        if m.get("state") != "never-enabled":
            try:
                s.c.call(L, "SetStrict", 0)
            except Exception as e:  # noqa: BLE001
                out["set_strict_off_error"] = str(e)[:200]
    except Exception as e:  # noqa: BLE001
        out["meta_error"] = str(e)[:200]
    out["scrub"] = scrub(s.c)
    out["purge"] = purge(s.c)
    out["meta_after"] = meta(s.c)
    out["b11_counts_after"] = counts(s.c)
    out["note"] = note
    return out
