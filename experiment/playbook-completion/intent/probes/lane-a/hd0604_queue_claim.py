"""HD-0604 probe: does the embed queue give two workers disjoint work?

Contracts cited:
- iris_src/src/Graph/KG/EmbedQueue.cls:22-25 (commit 5bb149ed, 2026-06-27, "Single-processor; persist-until-cleared"):
  "Single-processor: ClaimPendingBatch is a plain ordered scan (no atomic claim state)."
- docs/ADMIN_GUIDE.md:737-740: start_background_embedding creates "one per namespace" task; nothing documents that the
  Python process_embed_queue and the IRIS task must not run together.
- docs/API_REFERENCE.md:1387-1393: process_embed_queue "Process up to batch_size PENDING queue entries (spec 199)".

Deterministic two-connection check with the pin's own class methods (no model call, no task started):
enqueue 3 probe entries; worker A and worker B (two IRIS processes) each call Graph.KG.EmbedQueue.ClaimPendingBatch,
as process_embed_queue does (embeddings.py:1912-1915); then read the entries' status.
- Both claims return the same entries and status stays PENDING -> no claim/exclusion exists; two workers double-process
  (as-built; consistent with the code's single-processor premise, option (c) undocumented to users).
- Disjoint batches or a CLAIMED status -> an atomic claim exists (option (a)).
Precondition: AUDITIA's ^EmbedQueue is empty (else blocked). Cleanup: the probe's entries are set
DONE through SetResult and removed through ClearDone (which removes only DONE entries; the queue held none of its own
before, checked).
"""
from __future__ import annotations

import json

import _common as C

IDS = ["ia0604:n1", "ia0604:n2", "ia0604:n3"]


def main() -> None:
    a = C.conn()
    b = C.conn()
    try:
        pending0 = int(a.call("Graph.KG.EmbedQueue", "PendingCount"))
        done_before = a.o.isDefined("^EmbedQueue")
        C.obs(step="precondition", pending=pending0, queue_defined=done_before)
        if pending0 or done_before:
            C.verdict("blocked", "AUDITIA ^EmbedQueue is not empty; not touching other entries (ClearDone is queue-wide)")
            IDS.clear()
            return
        for i in IDS:
            st = a.call("Graph.KG.EmbedQueue", "Enqueue", i, "", f"text {i}", "ia-0604")
            C.obs(step="enqueue", id=i, status=str(st))
        ca = json.loads(str(a.call("Graph.KG.EmbedQueue", "ClaimPendingBatch", 10)))
        cb = json.loads(str(b.call("Graph.KG.EmbedQueue", "ClaimPendingBatch", 10)))
        ida, idb = [x["reqId"] for x in ca], [x["reqId"] for x in cb]
        status = {i: json.loads(str(a.call("Graph.KG.EmbedQueue", "GetEntry", i))).get("status") for i in IDS}
        C.obs(step="claims", worker_a=ida, worker_b=idb, overlap=sorted(set(ida) & set(idb)), status_after=status,
              pid_a=a.pid, pid_b=b.pid)
        overlap = set(ida) & set(idb)
        if overlap:
            C.verdict("pass", f"no claim state: both workers were handed the same {len(overlap)} entries and they stay "
                      "PENDING (matches the code's stated single-processor design; nothing enforces one worker)")
        else:
            C.verdict("fail", "claims were disjoint: the code comment 'plain ordered scan' is wrong")
    finally:
        try:
            for i in IDS:
                if a.o.isDefined("^EmbedQueue", i):
                    a.call("Graph.KG.EmbedQueue", "SetResult", i, "DONE", "0,0,0,0")
            if IDS:
                C.obs(step="cleanup", cleared=int(a.call("Graph.KG.EmbedQueue", "ClearDone")),
                      pending_after=int(a.call("Graph.KG.EmbedQueue", "PendingCount")),
                      queue_defined_after=a.o.isDefined("^EmbedQueue"))
        finally:
            a.close()
            b.close()


if __name__ == "__main__":
    main()
