#!/usr/bin/env python3
"""E-1 journal oracle summary: what the pin's embedded statements wrote, and whether an embedded statement's
journal footprint equals the dynamic statement's on the same table.

    python e1_journal.py <round dir>      -> <round dir>/journal-summary.json (exit 1 if a check fails)

Input: <round dir>/cases.json and journal.json (driver_e1.py --journal: every record of the case's processes in
AUDITCORE's database, mapped to stores). A process's records are cut into statements at the engine's statement
markers ("BeginTrans with level" ... "CommitTrans Pending with level", inside a transaction) or, at level 0, at its
own "BeginTrans" ... "CommitTrans". A statement's signature is the ordered (record type, in-transaction, store,
global suffix) list, with row ids and keys abstracted.

Checks:
  footprint   each pin method's statements write only the stores of its tables (plus the AdjIndex ^KG entries the
              rdf_edges rows carry, and the non-transactional counters); the readers (VerifyGraph, VectorRouteGuard)
              write nothing.
  same-shape  the embedded INSERT of a nodes row (RegisterDefaultNode) inside a transaction has the signature of the
              dynamic INSERT of a nodes row inside a transaction; likewise the embedded DELETE of an rdf_edges row
              (RetractTemporalRows) and the dynamic DELETE of one.
  in-txn      every row write of an embedded statement issued inside an open transaction is journaled in-transaction.
"""
import json
import re
import sys
from pathlib import Path


def abstract(g: str) -> str:
    g = re.sub(r"\d{3,}", "#", g)
    g = re.sub(r'"env2e1-[a-z]\d+"', '"<k>"', g)
    return g.split("(")[0] + ("(" + g.split("(", 1)[1] if "(" in g else "")


def statements(recs):
    """Split one process's records into statement segments."""
    out, cur, depth = [], None, 0
    for r in recs:
        t = r["t"]
        if t == "BeginTrans with level" or (t == "BeginTrans" and cur is None):
            cur = {"open": t, "records": []}
            continue
        if t in ("CommitTrans Pending with level", "CommitTrans") and cur is not None:
            cur["close"] = t
            out.append(cur)
            cur = None
            continue
        if cur is not None and t not in ("BeginTrans",):
            cur["records"].append(r)
    if cur is not None:
        out.append(cur)
    return out


def sig(seg):
    return [(r["t"], r["x"], r["store"], abstract(r["g"]).split("(")[0]) for r in seg["records"]]


def main() -> int:
    d = Path(sys.argv[1])
    cases = {c["id"]: c for c in json.loads((d / "cases.json").read_text())}
    jr = json.loads((d / "journal.json").read_text())
    res = {"footprints": {}, "same_shape": {}, "in_txn": {}, "failures": []}
    # footprint per pin method: cases whose only writer process runs only that method
    method_cases = {
        "RegisterDefaultNode": ("e1-reg-autocommit-no-hold", 0),
        "AssertTemporalRow(gk 0)": ("e1-null-c0-host", 0),
        "AssertTemporalRow(gk \"\")": ("e1-null-empty-host", 0),
        "VerifyGraph": ("e1-count-dirty", 0),
        "VectorRouteGuard": ("e1-route-dirty", 0),
        "RetractTemporalRows": ("e1-retract-update-waits", 0),
    }
    allowed = {
        "RegisterDefaultNode": {"sql:Graph_KG.nodes"},
        "AssertTemporalRow(gk 0)": {"sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges", "global:^KG"},
        "AssertTemporalRow(gk \"\")": set(),
        "VerifyGraph": set(),
        "VectorRouteGuard": set(),
        "RetractTemporalRows": {"sql:Graph_KG.rdf_edges", "global:^KG"},
    }
    for m, (cid, p) in method_cases.items():
        if cid not in jr:
            res["failures"].append(f"no journal for {cid}")
            continue
        pid = jr[cid]["pids"][str(p)]
        recs = [r for r in jr[cid]["records"] if r["p"] == pid and r["store"]]
        stores = sorted({r["store"] for r in recs})
        nontxn = sorted({abstract(r["g"]) for r in recs if not r["x"]})
        ok = set(stores) <= allowed[m]
        res["footprints"][m] = {"case": cid, "stores": stores, "records": len(recs),
                                "non_transactional": nontxn, "ok": ok}
        if not ok:
            res["failures"].append(f"footprint {m}: {stores}")
    # same-shape: e1-reg-rollback-one has a dynamic nodes INSERT at level 1 and an embedded one at level 2
    def segs(cid, p):
        pid = jr[cid]["pids"][str(p)]
        return statements([r for r in jr[cid]["records"] if r["p"] == pid])
    pairs = {  # name: (dynamic statement, embedded statement) as (case, process, segment index)
        "nodes INSERT in a transaction": (("e1-reg-rollback-one", 0, 0), ("e1-reg-rollback-one", 0, 1)),
        "rdf_edges DELETE in a transaction": (("e1-count-dirty-delete", 1, 2), ("e1-retract-update-waits", 0, 0)),
    }
    for name, ((dc, dp, di), (ec, ep, ei)) in pairs.items():
        try:
            dyn = segs(dc, dp)[di]
            emb = segs(ec, ep)[ei]
        except (KeyError, IndexError) as e:
            res["failures"].append(f"same-shape {name}: segment missing ({e})")
            continue
        eq = sig(dyn) == sig(emb) and len(sig(dyn)) > 0
        res["same_shape"][name] = {"dynamic": f"{dc} p{dp} statement #{di}", "embedded": f"{ec} p{ep} statement #{ei}",
                                   "equal": eq, "dynamic_sig": sig(dyn), "embedded_sig": sig(emb)}
        if not eq:
            res["failures"].append(f"same-shape {name}")
    # in-txn: named cases where process 0 opens a transaction (t_start or autocommit off) before an emb op
    for cid, c in cases.items():
        if not cid.startswith("e1-") or cid not in jr:
            continue
        steps = c["steps"]
        opened = any(o["op"] in ("t_start",) or (o["op"] == "set_autocommit" and not o.get("on"))
                     for p, o in steps if p == 0)
        emb = any(o["op"].startswith("emb_") for p, o in steps if p == 0)
        if not (opened and emb) or cid in ("e1-retract-autocommit-off",):
            continue
        pid = jr[cid]["pids"]["0"]
        rows = [r for r in jr[cid]["records"] if r["p"] == pid and r["store"].startswith("sql:")
                and r["t"] in ("SET", "KILL", "ZKILL", "BitSET") and not re.search(r"\.1$", r["g"])]
        bad = [r for r in rows if not r["x"]]
        res["in_txn"][cid] = {"row_writes": len(rows), "outside_txn": len(bad)}
        if bad:
            res["failures"].append(f"in-txn {cid}: {len(bad)} row writes outside the transaction")
    (d / "journal-summary.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: (v if k == "failures" else {kk: (vv.get("ok", vv.get("equal", vv)) if isinstance(vv, dict) else vv)
                                                      for kk, vv in v.items()}) for k, v in res.items()}, indent=1))
    return 1 if res["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
