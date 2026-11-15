#!/usr/bin/env python3
"""F-C1303 on the real engine: does a bounded redaction finish when it is run again and again?

    python fc1303_resume.py OUT_DIR

Graph.KG.LedgerRedact.Redact's documentation (LedgerRedact.cls:178-180): "pMaxBatches > 0 stops after that many
batches and leaves the run in progress; running the same target again resumes it." Each call starts its scan at the
first ledger record (:213) and a batch scans at most batch x SCANFACTOR (20) records (:306-310). World: 30 revisions
of another tenant, then 3 revisions of tenant acme, acme erased; then Redact("", "acme", batch=1, max_batches=1)
called 60 times. Oracle: some call reports complete and every acme record ends tombstoned. Control: the same world
with max_batches=0 (unbounded) must complete in one call, showing the world itself is redactable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from iris_conn import Conn, version  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402

NS = "AUDITCORE"


def world(c: Conn) -> None:
    c.call("Graph.KG.Eraser", "EraseAll")
    c.call("Graph.KG.Ledger", "PurgeAll")
    led = IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4).ledger
    led.enable()
    for i in range(30):
        cs = Changeset(actor="audit:fc1303", actor_type="ingest")
        cs.create_node(f"zeta|{i}", labels=["T"])
        led.commit(cs)
    for i in range(3):
        cs = Changeset(actor="audit:fc1303", actor_type="ingest")
        cs.create_node(f"acme|{i}", labels=["T"], properties={"secret": f"s{i}"})
        led.commit(cs)
    c.conn.commit()
    c.call("Graph.KG.Eraser", "EraseNodes", "", "acme|")
    c.conn.commit()


def redact(c: Conn, max_batches: int) -> dict:
    o = str(c.call("Graph.KG.LedgerRedact", "Redact", "", "acme", "|", "audit:fc1303", 1, max_batches, "Graph_KG"))
    if o.startswith("CHUNKED:"):
        _, tag, n = o.split(":")
        o = "".join(str(c.call("Graph.KG.Ledger", "ReadLargeOutChunk", tag, i)) for i in range(1, int(n) + 1))
    return json.loads(o)


def acme_left(c: Conn) -> int:
    n = 0
    for seq, _ in c.o.iterator("^IVG.Ledger", "rec").items():
        for ordn, _ in c.o.iterator("^IVG.Ledger", "rec", seq).items():
            lst = c.o.getIRISList("^IVG.Ledger", "rec", seq, ordn)
            if str(lst.get(1)) != "redacted" and str(lst.get(3) or "").startswith("acme|"):
                n += 1
    return n


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    c = Conn(NS)
    print("engine:", version(c), flush=True)
    world(c)
    before = acme_left(c)
    calls = []
    for i in range(60):
        r = redact(c, 1)
        calls.append({"call": i + 1, "complete": r.get("complete"), "tombstoned": r.get("records_tombstoned"),
                      "batches": r.get("batches"), "error": r.get("error")})
        if r.get("complete") or r.get("error"):
            break
    left = acme_left(c)
    bounded = {"acme_records_before": before, "calls": len(calls), "completed": any(x["complete"] for x in calls),
               "acme_records_left": left, "last": calls[-1], "first": calls[0]}
    world(c)
    r0 = redact(c, 0)
    control = {"complete": r0.get("complete"), "tombstoned": r0.get("records_tombstoned"), "batches": r0.get("batches"),
               "acme_records_left": acme_left(c)}
    c.close()
    res = {"bounded_resume": bounded, "control_unbounded": control,
           "verdict": {"bounded_resume_finishes": bounded["completed"] and bounded["acme_records_left"] == 0,
                       "control_finishes": bool(control["complete"]) and control["acme_records_left"] == 0}}
    (out / "result.json").write_text(json.dumps({**res, "calls": calls}, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
