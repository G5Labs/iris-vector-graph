#!/usr/bin/env python3
"""Check the lock logs ($RUN_DIR/trace-replay/locklog/NN.json, from lockrun.py) against each module's lock plan.

    python lockcheck.py NN [NN ...]     # offline; prints one verdict per plan item and exits 0 when all hold

Plan items (from footprints/NN.json `locks` and the source lines they cite) are predicates over the log. "held" means
the writer's own pid was seen owning the lock by the fast poller (or the scan); "waited" means a block probe saw the
writer in a LOCK wait state while the probe held that lock.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trlib  # noqa: E402


def load(nn):
    return json.loads((trlib.run_dir() / "locklog" / f"{nn}.json").read_text())


def held(w: Dict, name_prefix: str) -> List[Tuple[str, str]]:
    return [tuple(x) for x in w["summary"]["held"] if x[0].startswith(name_prefix)]


def ivg_scan(w: Dict) -> List[Tuple[str, str]]:
    return [tuple(x) for x in w["summary"]["scan_rows_of_owner"]]


def only_names(w: Dict, allowed: List[str]) -> List:
    """Polled or scanned IVG/^KG locks of the writer outside the allowed name prefixes."""
    out = [x for x in w["summary"]["held"] if not any(x[0].startswith(a) for a in allowed)]
    out += [x for x in w["summary"]["scan_rows_of_owner"]
            if ("IVG" in x[0] or "^KG" in x[0] or "NKG" in x[0]) and not any(a.strip("^") in x[0] for a in allowed)]
    return out


def W(log, key):
    return log["workloads"][key]


def P(log, key):
    return log["probes"][key]


def adjw(log):
    return log["plan_names"][0]


ITEMS: Dict[str, List[Tuple[str, Callable[[Dict], Tuple[bool, str]]]]] = {
    "01": [
        ("initialize_schema's locks are among the declared ones (footprints/01.json py:IRISGraphEngine.initialize_schema: "
         "^IVG.AdjW S:5, ^IVG.AdjW(g) E:0, ^IVG.NKGBuild X) and it never takes the ledger head lock",
         lambda L: (lambda w: (all((n == "^IVG.AdjW" and m.startswith("S")) or (n.startswith("^IVG.AdjW(") and not m.startswith("S"))
                                   or (n == "^IVG.NKGBuild" and not m.startswith("S")) for n, m in w["summary"]["held"])
                               and not any("Ledger" in r[0] for r in w["summary"]["scan_rows_of_owner"]),
                               f"held {w['summary']['held']}; scan rows with IVG/KG {[r for r in w['summary']['scan_rows_of_owner'] if 'IVG' in r[0] or 'KG' in r[0]][:8]}; "
                               f"work {str(w['work'])[:200]}"))(W(L, "initialize_schema"))),
    ],
    "02": [
        ("set_multigraph takes no IVG lock (GraphMode.cls:27-45 has no LOCK; F-0207's two unlocked steps)",
         lambda L: (not W(L, "set_multigraph on/off")["summary"]["held"] and not [x for x in ivg_scan(W(L, "set_multigraph on/off")) if "IVG" in x[0]],
                    f"held {W(L, 'set_multigraph on/off')['summary']['held']}, scan {ivg_scan(W(L, 'set_multigraph on/off'))}, "
                    f"{W(L, 'set_multigraph on/off')['work']['iterations']} calls")),
        ("set_multigraph(off) does not wait for the writers' lock ^IVG.AdjW(g) (no lock shared with writers)",
         lambda L: (not P(L, "set_multigraph(off) vs AdjW(g) held exclusively")["waited"],
                    str(P(L, "set_multigraph(off) vs AdjW(g) held exclusively")["x"]))),
    ],
    "03": [
        ("create_edge/delete_edge hold ^IVG.AdjW(g) shared (Adjacency.WriterLock, Adjacency.cls:60-64)",
         lambda L: (bool(held(W(L, "create_edge+delete_edge"), adjw(L))) and
                    all(m.startswith("S") for _, m in held(W(L, "create_edge+delete_edge"), adjw(L))),
                    str(W(L, "create_edge+delete_edge")["summary"]))),
        ("create_node takes no adjacency writer lock (no edge row) ",
         lambda L: (not held(W(L, "create_node"), "^IVG.AdjW"), str(W(L, "create_node")["summary"]))),
        ("no other IVG lock in the direct writers",
         lambda L: (not only_names(W(L, "create_edge+delete_edge"), [adjw(L)]), str(only_names(W(L, "create_edge+delete_edge"), [adjw(L)])))),
        ("with ^IVG.AdjW(g) held exclusively, create_edge waits at WriterLock (timeout 5 s) and then writes without it",
         lambda L: (P(L, "create_edge vs AdjW(g) held exclusively")["waited"] and "error" not in P(L, "create_edge vs AdjW(g) held exclusively")["x"],
                    f"wait at {P(L, 'create_edge vs AdjW(g) held exclusively')['wait_at']}, x {P(L, 'create_edge vs AdjW(g) held exclusively')['x']}")),
    ],
    "04": [
        ("the Degree workload holds no lock other than the interleaved writes' ^IVG.AdjW(g) S (Degree's own "
         "Lock +^IVG.AdjW(g)#\"E\":0 with immediate release, Adj.cls:66-70, is shorter than the poll interval: "
         "not observed by sampling; the probe below shows its zero timeout)",
         lambda L: (all(n == adjw(L) and m.startswith("S") for n, m in W(L, "Adj.Degree (+ a write every 5th call)")["summary"]["held"]),
                    str(W(L, "Adj.Degree (+ a write every 5th call)")["summary"]["held"]))),
        ("with ^IVG.AdjW(g) held shared, Adj.Degree does not wait (Lock ...#\"E\":0)",
         lambda L: (not P(L, "Adj.Degree vs AdjW(g) held shared")["waited"], str(P(L, "Adj.Degree vs AdjW(g) held shared")["x"]))),
        ("sync (BuildKG) holds the parent ^IVG.AdjW shared (Adjacency.BeginRebuild, Adjacency.cls:814-822)",
         lambda L: (any(n == "^IVG.AdjW" and m.startswith("S") for n, m in W(L, "sync (BuildKG)")["summary"]["held"]),
                    str(W(L, "sync (BuildKG)")["summary"]))),
        ("with ^IVG.AdjW held exclusively, sync waits for it",
         lambda L: (P(L, "sync vs ^IVG.AdjW held exclusively")["waited"],
                    f"wait at {P(L, 'sync vs ^IVG.AdjW held exclusively')['wait_at']}, x {P(L, 'sync vs ^IVG.AdjW held exclusively')['x']}")),
    ],
    "05": [
        ("create_edge_temporal/delete_edge_temporal hold ^IVG.AdjW(g) shared (AssertTemporalRow/RetractTemporalRow -> row hook)",
         lambda L: (bool(held(W(L, "create_edge_temporal+delete_edge_temporal"), adjw(L))) and
                    all(m.startswith("S") for _, m in held(W(L, "create_edge_temporal+delete_edge_temporal"), adjw(L))),
                    str(W(L, "create_edge_temporal+delete_edge_temporal")["summary"]))),
        ("with ^IVG.AdjW(g) held exclusively, create_edge_temporal waits at the writer lock",
         lambda L: (P(L, "create_edge_temporal vs AdjW(g) held exclusively")["waited"],
                    f"wait at {P(L, 'create_edge_temporal vs AdjW(g) held exclusively')['wait_at']}, x {P(L, 'create_edge_temporal vs AdjW(g) held exclusively')['x']}")),
    ],
    "06": [
        ("store_embedding and ivf_insert take no IVG lock (footprints/06.json: no locks)",
         lambda L: (not [x for x in W(L, "store_embedding+ivf_insert")["summary"]["held"]] and
                    not [x for x in ivg_scan(W(L, "store_embedding+ivf_insert")) if "IVG" in x[0] or "IVF" in x[0]],
                    str(W(L, "store_embedding+ivf_insert")["summary"]))),
        ("store_embedding does not wait for ^IVG.Ledger(\"head\")",
         lambda L: (not P(L, "store_embedding vs ^IVG.Ledger(head) held exclusively")["waited"],
                    str(P(L, "store_embedding vs ^IVG.Ledger(head) held exclusively")["x"]))),
        ("store_embedding does not wait for ^IVG.AdjW(g)",
         lambda L: (not P(L, "store_embedding vs AdjW(g) held exclusively")["waited"],
                    str(P(L, "store_embedding vs AdjW(g) held exclusively")["x"]))),
    ],
    "08": [
        ("Cypher CREATE/DELETE hold ^IVG.AdjW(g) shared through the row hook (footprints/08.json)",
         lambda L: (bool(held(W(L, "Cypher CREATE + DELETE"), adjw(L))) and
                    all(m.startswith("S") for _, m in held(W(L, "Cypher CREATE + DELETE"), adjw(L))),
                    str(W(L, "Cypher CREATE + DELETE")["summary"]))),
        ("with ^IVG.AdjW(g) held exclusively, a Cypher CREATE waits at the writer lock",
         lambda L: (P(L, "Cypher CREATE vs AdjW(g) held exclusively")["waited"],
                    f"wait at {P(L, 'Cypher CREATE vs AdjW(g) held exclusively')['wait_at']}, x {P(L, 'Cypher CREATE vs AdjW(g) held exclusively')['x']}")),
    ],
    "10": [
        ("rebuild_nkg holds ^IVG.NKGBuild exclusively and no other IVG lock (footprints/10.json: ^IVG.NKGBuild + exclusive)",
         lambda L: (all(n == "^IVG.NKGBuild" and not m.startswith("S") for n, m in W(L, "rebuild_nkg")["summary"]["held"])
                    and bool(W(L, "rebuild_nkg")["summary"]["held"]),
                    str(W(L, "rebuild_nkg")["summary"]))),
        ("with ^IVG.NKGBuild held, rebuild_nkg waits for it",
         lambda L: (P(L, "rebuild_nkg vs ^IVG.NKGBuild held exclusively")["waited"],
                    f"wait at {P(L, 'rebuild_nkg vs ^IVG.NKGBuild held exclusively')['wait_at']}, x {P(L, 'rebuild_nkg vs ^IVG.NKGBuild held exclusively')['x']}")),
    ],
    "09": [
        ("sync builds: the reader holds ^IVG.CypherCompiled(h) exclusively while it compiles (Gen.cls:166, released "
         ":172/:180/:220) and no other polled IVG lock",
         lambda L: (lambda w: (any(n.startswith("^IVG.CypherCompiled(") and m == "X" for n, m in w["summary"]["held"])
                               and all(n.startswith("^IVG.CypherCompiled(") for n, _ in w["summary"]["held"])
                               and w["work"]["builds_ok"] >= 1,
                               f"held {w['summary']['held']}, builds {w['work']['builds_ok']}/{w['work']['iterations']}, "
                               f"others {w['held_by_other_processes']}"))(W(L, "DropAll + read (sync)"))),
        ("job builds: the build lock is held by another process (the job), never by the reader",
         lambda L: (lambda w: (not any(n.startswith("^IVG.CypherCompiled") for n, _ in w["summary"]["held"])
                               and any(n.startswith("^IVG.CypherCompiled(") and m == "X" for n, m, _ in w["held_by_other_processes"])
                               and w["work"]["builds_ok"] >= 1,
                               f"reader held {w['summary']['held']}, held by others {w['held_by_other_processes']}, "
                               f"builds {w['work']['builds_ok']}/{w['work']['iterations']}"))(W(L, "DropAll + read (job)"))),
        ("with ^IVG.CypherCompiled(h) held by another process, a sync read does not wait (Lock :0), compiles nothing, "
         "leaves the entry pending and is answered",
         lambda L: (lambda p: (not p["waited"] and "error" not in p["x"] and "'status': 'pending'" in p["x"].get("result", "")
                               and "'classes': 0" in p["x"].get("result", ""),
                               f"waited {p['waited']}, x {p['x']}"))(P(L, "sync read vs ^IVG.CypherCompiled(h) held exclusively"))),
    ],
    "13": [
        ("the redaction holds ^IVG.Ledger(\"head\") exclusively and no other IVG lock (poll and scan)",
         lambda L: (all(n == '^IVG.Ledger("head")' and m == "X" for n, m in W(L, "Redact batch=1")["summary"]["held"])
                    and all(r[0] == '^IVG.Ledger("head")' for r in W(L, "Redact batch=1")["summary"]["scan_rows_of_owner"]),
                    f"{W(L, 'Redact batch=1')['summary']}; receipt batches {W(L, 'Redact batch=1')['work']['receipt'].get('batches')} "
                    "(releases between batches are shorter than the poll period: one episode)")),
    ],
    "13b": [
        ("with the head lock held from the start, the redaction waits at Batch's lock (LedgerRedact.cls:282) having "
         "written nothing",
         lambda L: (lambda p: (p["waited"] and not p["x_records_before_release"],
                               f"wait at {p['wait_at']}, records before release {len(p['x_records_before_release'])}"))(
             P(L, "Redact vs head held from the start (Batch, :282)"))),
        ("Final's own head lock (LedgerRedact.cls:390): with P queued for the head lock behind the only Batch, the "
         "redaction waits at a second, different line after its tombstones and before its redaction revision and head",
         lambda L: (lambda p, q: (p["waited"] and p["wait_at"] != q["wait_at"] and p["tombstones_before_mark"] > 0
                                  and not any(r.endswith("(6)") for r in p["revision_rows_before_mark"])
                                  and p["revision_rows_after_mark"] and p["head_after_mark"],
                                  f"wait at {p['wait_at']} (Batch's at {q['wait_at']}); tombstones before {p['tombstones_before_mark']}, "
                                  f"revision rows after {p['revision_rows_after_mark']}, head after {p['head_after_mark']}, "
                                  f"receipt {p['x'].get('receipt')}"))(
             P(L, "Redact vs head taken after the first Batch (Final, :390)"),
             P(L, "Redact vs head held from the start (Batch, :282)"))),
    ],
    "18": [
        ("restore_snapshot takes no IVG lock of its own and never the ledger head lock (footprints/18.json: 'none: the "
         "ledger head lock is not taken'); the only lock seen is the parent ^IVG.AdjW shared that its erase_all takes "
         "(Eraser.EraseAll -> Adjacency.RemoveAll, Adjacency.cls:452-462, module 12's plan), which the declared plan omits",
         lambda L: (all(n == "^IVG.AdjW" and m.startswith("S") for n, m in W(L, "restore_snapshot(merge=False)")["summary"]["held"])
                    and not any("Ledger" in r[0] for r in W(L, "restore_snapshot(merge=False)")["summary"]["scan_rows_of_owner"]),
                    str(W(L, "restore_snapshot(merge=False)")["summary"]))),
        ("restore_snapshot does not wait for ^IVG.Ledger(\"head\")",
         lambda L: (not P(L, "restore_snapshot vs ^IVG.Ledger(head) held exclusively")["waited"],
                    str(P(L, "restore_snapshot vs ^IVG.Ledger(head) held exclusively")["x"]))),
    ],
}


def main() -> int:
    ok_all = True
    out = {}
    for nn in sys.argv[1:]:
        L = load(nn)
        res = []
        for text, pred in ITEMS[nn]:
            try:
                ok, detail = pred(L)
            except KeyError as ex:
                ok, detail = False, f"missing in the log: {ex}"
            res.append({"item": text, "holds": bool(ok), "detail": detail[:600]})
            ok_all &= bool(ok)
            print(f"{nn} {'HOLDS' if ok else 'DOES NOT HOLD'}: {text}\n      {detail[:400]}")
        out[nn] = res
    (trlib.run_dir() / "locklog" / f"check-{'-'.join(sys.argv[1:])}.json").write_text(json.dumps(out, indent=1))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
