"""Shared helpers for the redaction probes (product baseline 3eaa79cf, read-only use of public APIs)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import RUN_DIR, canonical, connect, engine, ensure_schema, ledger_global, ledger_records, record, reset, sha256  # noqa: E402,F401

from iris_vector_graph.ledger import Changeset  # noqa: E402

TWIN = RUN_DIR / "verus" / "twin" / "twin"
OPS = {"create_node": 0, "delete_node": 1, "add_label": 2, "remove_label": 3, "set_prop": 4, "remove_prop": 5,
       "create_rel": 6, "delete_rel": 7, "set_qual": 8, "remove_qual": 9, "create_temporal_edge": 10, "redact": 11}


def h(s: str) -> str:
    return s.encode("utf-8").hex() if s else "-"


def tuple_ends(enc: str):
    """(s, o) from an encoded tuple value "S{...}", None when absent or unparsable (LedgerRedact.TupleEnds)."""
    if not enc or not str(enc).startswith("S"):
        return None
    try:
        t = json.loads(str(enc)[1:])
    except Exception:
        return None
    if not isinstance(t, dict):
        return None
    return (str(t.get("s") or ""), str(t.get("o") or ""))


def knowledge(recs: dict, stmt_map: dict, graph: str):
    """What LedgerRedact.Matches can know at the start of a run: PrePass over create_rel/delete_rel
    records of the target graph, then the live ^IVG.Ledger("stmt") map."""
    pre = {}
    for (_seq, _ord), f in sorted(recs.items()):
        if f[0] in ("create_rel", "delete_rel") and f[1] == "rel" and str(f[6] or "").replace("\x00", "") == graph and f[2]:
            e = tuple_ends(f[5] if f[0] == "create_rel" else f[4])
            if e:
                pre[str(f[2])] = e
    live = {sid: (row[0], row[2]) for sid, row in stmt_map.items()}
    return pre, live


def stmt_rows(native) -> dict:
    """{stmt_id: [s, p, o, graph, createdSeq, deletedSeq]} from ^IVG.Ledger("stmt")."""
    import iris

    out = {}
    for key, val in ledger_global(native, "stmt").items():
        if len(key) != 2:
            continue
        lst = iris.IRISList(val)
        out[str(key[1])] = [lst.get(i) for i in range(1, lst.count() + 1)]
    return out


def twin_classify(recs: dict, graph: str, prefix: str, sep: str, pre: dict, live: dict) -> dict:
    """Run the Verus-verified twin (proved equal to redaction.rs `matches`) over observed records."""
    lines = [f"T\t{h(graph)}\t{h(prefix)}\t{h(sep)}"]
    order = []
    for (seq, ordn), f in sorted(recs.items()):
        if f[0] == "redacted":
            continue
        op = OPS.get(f[0], 12)
        g = str(f[6] or "").replace("\x00", "")
        eid = str(f[2] or "")
        ends = None
        if f[0] in ("create_rel", "create_temporal_edge"):
            ends = tuple_ends(f[5])
        elif f[0] == "delete_rel":
            ends = tuple_ends(f[4])
        stmt = int(eid) if (f[1] == "rel" and eid.isdigit()) else 0
        known = (pre.get(eid) or live.get(eid)) if (f[1] == "rel" and f[0] in ("set_qual", "remove_qual")) else None
        lines.append("\t".join([
            "R", str(seq), str(ordn), str(op), h(g), h(eid), str(stmt),
            "1" if ends else "0", h(ends[0]) if ends else "-", h(ends[1]) if ends else "-",
            "0", "1" if known else "0", h(known[0]) if known else "-", h(known[1]) if known else "-",
        ]))
        order.append((seq, ordn))
    p = subprocess.run([str(TWIN)], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True)
    out = {}
    for line in p.stdout.splitlines():
        parts = line.split("\t")
        if parts[0] == "M":
            continue
        out[(int(parts[0]), int(parts[1]))] = parts[2]
    return out


def revision_rows(conn) -> dict:
    cur = conn.cursor()
    try:
        cur.execute("SELECT seq, revision_id, parent_id, kind, actor, actor_type, conn_user, committed_ms, message, source, "
                    "correlation_id, idempotency_key, op_count, stmt_first, stmt_last FROM Graph_KG.ledger_revisions ORDER BY seq")
        cols = [d[0] for d in cur.description]
        return {int(r[0]): dict(zip(cols, r)) for r in cur.fetchall()}
    finally:
        cur.close()


def marker(native):
    v = json.loads(str(native.classMethodValue("Graph.KG.LedgerRedact", "InProgress")))
    return v if v.get("in_progress") else None


def cs(message=None, corr=None, key=None, src=None, actor="probe:etl"):
    return Changeset(actor=actor, actor_type="ingest", message=message, correlation_id=corr, idempotency_key=key,
                     source={"feed": src} if src else None)


def verdict(name: str, ok_expected: bool, reason: str, data: dict) -> int:
    v = "OBSERVED_AS_EXPECTED" if ok_expected else "OBSERVED_DEFECT"
    data = {**data, "verdict": v, "reason": reason}
    path = record(name, data)
    print(f"{name}: {v} — {reason} [{path}]")
    return 0
