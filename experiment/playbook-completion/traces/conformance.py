#!/usr/bin/env python3
"""Trace conformance for the ledger, erasure and redaction (playbook §3.7 trace replay; §4.2 L3 option 1).

    python conformance.py OUT_DIR [--batch N]

Runs a two-tenant scenario through the pin's public API in namespace AUDITCORE, one IRIS process per operation so
the journal's process id names the operation. Then, independently of the product:
1. snapshots ^IVG.Ledger before the scenario and replays every journaled SET/KILL of the scenario onto it, outermost
   transaction by transaction (traces/journal.py);
2. after each committed transaction checks the L2 step rule of the operation that ran it (rules written from spec
   256 / ADR-0013 / spec 213, not from the code), the frame (every store the transaction wrote is in the operation's
   declared write footprint) and the ledger invariants;
3. checks the replayed final state equals the state read back from the engine (the replay is faithful).

The record match used by the rules is a fourth implementation of the target predicate, written from the spec text
(a record belongs to a target when its graph is the target graph and its node id, or an endpoint of its statement,
starts with the target's prefix-and-separator), so a disagreement with the product's Matches is visible.
"""
from __future__ import annotations

import base64
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
sys.path.insert(0, str(HERE))
import iris  # noqa: E402
from iris_conn import Conn, version  # noqa: E402
import journal  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402

NS = "AUDITCORE"
DB = "/usr/irissys/mgr/auditcore/"
SEP = "|"

# Declared write footprints per operation (from source reading; the journal validates them independently).
FOOTPRINT = {
    "commit": {"global:^IVG.Ledger", "global:^KG", "global:^Graph.KG.LedgerRevisionD", "global:^Graph.KG.LedgerRevisionI",
               "sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props",
               "sql:Graph_KG.ledger_revisions", "sql:Graph_KG.ledger_stats", "global:^IVG.AdjNoLock",
               "global:^IVG.GraphMode", "global:^NKG", "global:^IVG.ArnoVersion", "global:^IVG.AlgoCache"},
    "erase": {"global:^IVG.Ledger", "global:^KG", "global:^NKG", "global:^IVG.AlgoCache", "global:^IVG.GraphMode",
              "global:^IVG.AdjNoLock", "global:^IVG.ArnoVersion", "sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges",
              "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "sql:Graph_KG.docs", "sql:Graph_KG.kg_NodeEmbeddings",
              "sql:Graph_KG.kg_EdgeEmbeddings", "sql:Graph_KG.rdf_reifications", "sql:Graph_KG.kg_NodeEmbeddings_optimized"},
    "redact": {"global:^IVG.Ledger", "sql:Graph_KG.ledger_revisions", "sql:Graph_KG.ledger_stats",
               "global:^Graph.KG.LedgerRevisionD", "global:^Graph.KG.LedgerRevisionI"},
    "verify": {"global:^IVG.Ledger", "sql:Graph_KG.ledger_stats"},
}

# ------------------------------------------------------------------------------------------------ global references

_TOKEN = re.compile(r'"((?:[^"]|"")*)"|\$c(?:har)?\(([\d,]+)\)|(-?\d+(?:\.\d+)?(?:E-?\d+)?)|(_)|(,)', re.I)


def parse_ref(ref: str) -> Tuple[str, Tuple]:
    """'^IVG.Ledger("tuple","x",$c(1))' -> ('^IVG.Ledger', ('tuple', 'x', '\\x01')). Numbers stay numbers."""
    if ref.startswith('^["'):
        ref = "^" + ref[ref.index("]") + 1:]
    if "(" not in ref:
        return ref, ()
    root, body = ref.split("(", 1)
    body = body[:-1]
    subs: List[Any] = []
    cur: Optional[Any] = None
    pos = 0
    while pos < len(body):
        m = _TOKEN.match(body, pos)
        if not m:
            raise ValueError(f"cannot parse subscript in {ref!r} at {pos}")
        s, chars, num, cat, comma = m.groups()
        if s is not None:
            piece: Any = s.replace('""', '"')
        elif chars is not None:
            piece = "".join(chr(int(x)) for x in chars.split(","))
        elif num is not None:
            piece = int(num) if re.fullmatch(r"-?\d+", num) else float(num)
        elif cat:
            pos = m.end()
            continue
        else:
            subs.append(cur)
            cur = None
            pos = m.end()
            continue
        cur = piece if cur is None else str(cur) + str(piece)
        pos = m.end()
    subs.append(cur)
    return root, tuple(subs)


def decode_value(b64: Optional[str]) -> Any:
    if b64 is None:
        return None
    raw = base64.b64decode(b64)
    try:
        lst = iris.IRISList(raw)
        if lst.count() >= 1 and raw[:1] not in (b"",):
            return tuple(_s(lst.get(i)) for i in range(1, lst.count() + 1))
    except Exception:  # noqa: BLE001
        pass
    return raw.decode("utf-8", "replace")


def _s(v):
    if isinstance(v, (bytes, bytearray)):
        try:
            inner = iris.IRISList(bytes(v))
            return tuple(_s(inner.get(i)) for i in range(1, inner.count() + 1))
        except Exception:  # noqa: BLE001
            return bytes(v).decode("utf-8", "replace")
    return "" if v is None else (v if isinstance(v, (int, float)) else str(v))


def snapshot(c: Conn, root: str = "^IVG.Ledger") -> Dict[Tuple, Any]:
    out: Dict[Tuple, Any] = {}

    def walk(subs: Tuple):
        d = int(c.o.isDefined(root, *subs))
        if d in (1, 11):
            raw = c.o.getBytes(root, *subs)
            out[subs] = decode_value(base64.b64encode(raw).decode()) if raw is not None else None
        if d >= 10:
            for sub, _ in c.o.iterator(root, *subs).items():
                walk(subs + (int(sub) if isinstance(sub, str) and re.fullmatch(r"-?\d+", sub) else sub,))
    walk(())
    return out


def apply(state: Dict[Tuple, Any], rec: Dict) -> None:
    _, subs = parse_ref(rec["g"])
    if rec["t"] == "SET":
        v = decode_value(rec["n"])
        state[subs] = "" if v is None else _deep(v)   # the journal reader reports an empty new value as None
    elif rec["t"] in ("KILL",):
        for k in [k for k in state if k[:len(subs)] == subs]:
            del state[k]
    elif rec["t"] == "ZKILL":
        state.pop(subs, None)


# ------------------------------------------------------------------------------------------------ the spec's predicate

def rec_graph(r: Tuple) -> str:
    return str(r[6]).replace("\x00", "") if len(r) > 6 else ""


def tuple_ends(enc: Any) -> Optional[Tuple[str, str]]:
    if not isinstance(enc, str) or not enc.startswith("S"):
        return None
    try:
        t = json.loads(enc[1:])
        return str(t.get("s", "")), str(t.get("o", ""))
    except Exception:  # noqa: BLE001
        return None


def spec_member(r: Tuple, target: Tuple[str, str], stmt_ends: Dict[str, Tuple[str, str]]) -> Optional[bool]:
    """Spec 256 FR-002: does the record belong to the target? None when its statement's ends are unknown."""
    graph, match = target
    if not r or r[0] in ("redacted", "redact") or rec_graph(r) != graph:
        return False
    if not match:
        return True
    kind, rid = str(r[1]), str(r[2])
    if kind == "node":
        return rid.startswith(match)
    ends = stmt_ends.get(rid)
    if ends is None:
        return None
    return ends[0].startswith(match) or ends[1].startswith(match)


def statement_ends(state: Dict[Tuple, Any], extra: Dict[str, Tuple[str, str]]) -> Dict[str, Tuple[str, str]]:
    ends = dict(extra)
    for k, v in state.items():
        if len(k) == 3 and k[0] == "rec" and isinstance(v, tuple) and v and v[0] in ("create_rel", "delete_rel"):
            e = tuple_ends(v[5] if v[0] == "create_rel" else v[4])
            if e:
                ends[str(v[2])] = e
    return ends


# ------------------------------------------------------------------------------------------------ step rules

def recs(state):
    return {(k[1], k[2]): v for k, v in state.items() if len(k) == 3 and k[0] == "rec"}


def stmts(state):
    return {str(k[1]): v for k, v in state.items() if len(k) == 2 and k[0] == "stmt"}


def check_invariants(state, notes: List[str]) -> None:
    # stmt/tuple: a live statement (empty deletedSeq) has its tuple entry pointing back at it
    tuples = {(k[1], k[2], k[3], k[4]): v for k, v in state.items() if len(k) == 5 and k[0] == "tuple"}
    for sid, row in stmts(state).items():
        if isinstance(row, tuple) and len(row) >= 6 and str(row[5]) == "":
            keys = [t for t, v in tuples.items() if str(v) == sid]
            if not keys:
                notes.append(f"INV stmt/tuple: live statement {sid} has no tuple entry")
    # tombstone shape
    for (seq, ordn), v in recs(state).items():
        if isinstance(v, tuple) and v and v[0] == "redacted":
            if len(v) != 5 or not re.fullmatch(r"[0-9a-f]{64}", str(v[1])):
                notes.append(f"INV tombstone shape at ({seq},{ordn}): {v!r}")
    # counters vs tombstones while a run is open
    revs = {k[2]: v for k, v in state.items() if len(k) == 3 and k[:2] == ("redacting", "revs")}
    n = state.get(("redacting", "n", "records"))
    if revs and n is not None and sum(int(x) for x in revs.values()) != int(n):
        notes.append(f"INV counters: per-revision sum {sum(int(x) for x in revs.values())} != records {n}")


def step_rule(op: str, info: Dict, before, after, notes: List[str]) -> None:
    rb, ra = recs(before), recs(after)
    changed = {k for k in set(rb) | set(ra) if rb.get(k) != ra.get(k)}
    hb, ha = before.get(("head",)), after.get(("head",))
    if op == "commit":
        new = {k for k in changed if k not in rb}
        if any(k in rb for k in changed):
            notes.append(f"commit changed an existing record: {sorted(k for k in changed if k in rb)}")
        if new and int(ha or 0) != int(hb or 0) + 1:
            notes.append(f"commit head {hb} -> {ha} with {len(new)} new records")
        if {k[0] for k in new} - {int(ha or 0)}:
            notes.append(f"commit wrote records outside its seq {ha}: {sorted(new)}")
    elif op == "erase":
        if changed:
            notes.append(f"erasure changed {len(changed)} ledger record(s) (ERS-B1.3)")
        sb, sa = stmts(before), stmts(after)
        if set(sa) - set(sb):
            notes.append("erasure created statement entries")
    elif op == "redact":
        target = info["target"]
        ends = statement_ends(before, info.get("prepass_ends", {}))
        tomb = [k for k in changed if isinstance(ra.get(k), tuple) and ra[k][0] == "redacted"]
        other = [k for k in changed if k not in tomb]
        new_rev = [k for k in other if k not in rb]
        if [k for k in other if k in rb]:
            notes.append(f"redaction changed records other than by tombstoning: {sorted(k for k in other if k in rb)}")
        for k in tomb:
            orig = rb.get(k)
            if not isinstance(orig, tuple) or orig[0] == "redacted":
                notes.append(f"tombstone over a non-record at {k}")
                continue
            if (ra[k][3], ra[k][4]) != (orig[0], orig[1]):
                notes.append(f"tombstone at {k} lost op/kind")
            m = spec_member(orig, target, ends)
            if m is False:
                notes.append(f"RED-I1: tombstoned a record outside the target at {k}: {orig[:3]}")
        marker_b, marker_a = before.get(("redacting",)), after.get(("redacting",))
        if tomb and marker_a is not None and str(marker_a[0]) != info["digest"]:
            notes.append(f"RED-B6: a batch tombstoned under another target's marker {str(marker_a[0])[:12]}")
        if new_rev:
            # the Final step: one redaction revision, counts equal to the run's tombstones of THIS target
            seqs = {k[0] for k in new_rev}
            if len(seqs) != 1:
                notes.append(f"final wrote records in several seqs {sorted(seqs)}")
            info.setdefault("finals", []).append({"seq": min(seqs), "records": len(new_rev),
                                                  "marker_before": marker_b and str(marker_b[0])[:12]})


def classify(pid_ops: Dict[str, Dict], u: Dict) -> Optional[Dict]:
    return pid_ops.get(u["pid"])


# ------------------------------------------------------------------------------------------------ scenario

def run(out: Path, batch: int) -> Dict:
    ctl = Conn(NS)
    ctl.call("Graph.KG.Eraser", "EraseAll")
    ctl.call("Graph.KG.Ledger", "PurgeAll")
    ctl.conn.commit()
    eng = IRISGraphEngine(ctl.conn, namespace=NS, embedding_dimension=4)
    eng.ledger.enable()
    ctl.conn.commit()
    smap = journal.storage_map(ctl)
    before0 = snapshot(ctl)
    ctl.close()
    m = journal.mark()
    ops: List[Dict] = []

    def op(name: str, fn, **info):
        c = Conn(NS)
        t = time.time()
        try:
            res = fn(c)
            ok = True
        except Exception as ex:  # noqa: BLE001
            res, ok = str(ex)[:300], False
        ops.append({"op": name, "pid": c.pid, "ok": ok, "result": res if isinstance(res, (str, int, float, dict, list)) else str(res),
                    "seconds": round(time.time() - t, 3), **info})
        c.close()

    def commit(cs):
        def f(c):
            r = IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4).ledger.commit(cs)
            c.conn.commit()
            return {"seq": r.revision.seq}
        return f

    def cs(msg, key):
        return Changeset(actor="audit:trace", actor_type="ingest", message=msg, idempotency_key=key, source={"feed": msg})

    a = cs("acme nodes", "k1")
    a.create_node("acme|1", labels=["Person"], properties={"name": "alpha-secret"})
    a.create_node("acme|2", labels=["Person"])
    a.create_relationship("acme|1", "KNOWS", "acme|2", qualifiers={"note": "alpha-q"})
    op("commit", commit(a))
    b = cs("beta nodes", "k2")
    b.create_node("beta|1", labels=["Person"], properties={"name": "bravo"})
    op("commit", commit(b))
    span = cs("spanning", "k3")
    span.create_relationship("beta|1", "KNOWS", "acme|1", qualifiers={"note": "span-q"})
    span.set_property("beta|1", "city", "B-town")
    op("commit", commit(span))
    q = cs("qualifier on the spanning edge", "k4")
    q.set_qualifier(("beta|1", "KNOWS", "acme|1"), "weight", "2")
    op("commit", commit(q))
    op("erase", lambda c: int(c.call("Graph.KG.Eraser", "EraseNodes", "", "acme|")), graph="", prefix="acme|")
    digest = None

    def redact(max_batches):
        def f(c):
            o = str(c.call("Graph.KG.LedgerRedact", "Redact", "", "acme", SEP, "audit:trace", batch, max_batches, "Graph_KG"))
            if o.startswith("CHUNKED:"):
                _, tag, n = o.split(":")
                o = "".join(str(c.call("Graph.KG.Ledger", "ReadLargeOutChunk", tag, i)) for i in range(1, int(n) + 1))
            return json.loads(o)
        return f
    c = Conn(NS)
    digest = str(c.call("Graph.KG.LedgerRedact", "TargetDigest", "", "acme|"))
    c.close()
    op("redact", redact(1), target=("", "acme|"), digest=digest)
    op("redact", redact(0), target=("", "acme|"), digest=digest)
    op("verify", lambda c: json.loads(json.dumps(IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4).ledger.verify(),
                                                 default=str)))
    ctl = Conn(NS)
    final_engine = snapshot(ctl)
    ctl.close()
    recs_j = journal.records_since(m, dbs={DB})
    trace = {"before": [[list(k), v] for k, v in before0.items()], "final": [[list(k), v] for k, v in final_engine.items()],
             "ops": ops, "journal": recs_j, "smap": smap}
    out.mkdir(parents=True, exist_ok=True)
    (out / "trace.json").write_text(json.dumps(trace, default=list))
    return check_trace(trace, out)


def _deep(v):
    return tuple(_deep(x) for x in v) if isinstance(v, (list, tuple)) else v


def _state(pairs):
    return {tuple(k): _deep(v) for k, v in pairs}


def check_trace(trace: Dict, out: Optional[Path] = None) -> Dict:
    before0, final_engine = _state(trace["before"]), _state(trace["final"])
    ops, recs_j, smap = trace["ops"], trace["journal"], trace["smap"]
    for o in ops:
        if "target" in o:
            o["target"] = tuple(o["target"])
    pid_ops: Dict[str, List[Dict]] = defaultdict(list)
    for o in ops:
        pid_ops[o["pid"]].append(o)
    units = journal.transactions(recs_j)
    state = dict(before0)
    report = {"ops": ops, "transactions": [], "violations": [], "frame": [], "unclassified": [],
              "checked": Counter()}
    for u in sorted(units, key=lambda u: u.get("end") or u.get("begin") or 0):
        olist = pid_ops.get(u["pid"])
        prior = dict(state)
        for r in u["records"]:
            if r["g"].startswith("^IVG.Ledger"):
                apply(state, r)
        if not olist:
            report["unclassified"].append({"pid": u["pid"], "n": len(u["records"])})
            continue
        o = olist[0]
        stores = {journal.store_of(r["g"], smap) for r in u["records"] if r["g"]}
        outside = sorted(stores - FOOTPRINT[o["op"]])
        notes: List[str] = []
        if outside:
            report["frame"].append({"op": o["op"], "pid": u["pid"], "outside": outside})
        if u["kind"] == "txn" and u["committed"] and not u.get("rolled_back"):
            step_rule(o["op"], o, prior, state, notes)
            report["checked"][o["op"]] += 1
            report["checked"]["tombstones"] += sum(1 for k, v in recs(state).items()
                                                   if isinstance(v, tuple) and v and v[0] == "redacted"
                                                   and recs(prior).get(k) != v)
        check_invariants(state, notes)
        report["transactions"].append({"op": o["op"], "pid": u["pid"], "kind": u["kind"], "committed": u["committed"],
                                       "rolled_back": u.get("rolled_back"), "records": len(u["records"]),
                                       "nested_levels": u.get("nested_levels"), "stores": sorted(stores),
                                       "notes": notes})
        report["violations"] += [f"{o['op']}@{u['pid']}: {n}" for n in notes]
    # faithful replay
    diff = [k for k in set(state) | set(final_engine) if state.get(k) != final_engine.get(k)]
    report["replay_matches_engine"] = not diff
    report["replay_diff_sample"] = [str(k) for k in diff[:10]]
    # transactions per operation
    per_op = Counter((o["op"], o["pid"]) for o in ops)
    report["txn_count_per_op"] = {f"{k[0]}@{k[1]}": sum(1 for t in report["transactions"]
                                                         if t["pid"] == k[1] and t["kind"] == "txn") for k in per_op}
    report["checked"] = dict(report["checked"])
    if out is not None:
        (out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    return report


def mutate(trace: Dict, kind: str) -> Dict:
    """Negative controls: a trace the product never produced, each of which a rule must reject."""
    t = json.loads(json.dumps(trace, default=list))
    j = t["journal"]
    redact_pid = next(o["pid"] for o in t["ops"] if o["op"] == "redact")
    commit_pids = [o["pid"] for o in t["ops"] if o["op"] == "commit"]
    erase_pid = next(o["pid"] for o in t["ops"] if o["op"] == "erase")
    if kind == "tombstone-outside-target":
        # retarget one of the redaction's tombstones onto a beta record of the same revision layout
        # a node record of tenant beta, written by a commit, becomes the target of one of the redaction's tombstones
        beta = next(r for r in j if r["p"] in commit_pids and r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET"
                    and isinstance(decode_value(r["n"]), tuple) and decode_value(r["n"])[1:3] == ("node", "beta|1"))
        r = next(r for r in j if r["p"] == redact_pid and r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET")
        r["g"] = beta["g"]
    elif kind == "commit-rewrites-history":
        r = next(r for r in j if r["p"] == commit_pids[-1] and r["g"].startswith('^IVG.Ledger("rec"'))
        r["g"] = '^IVG.Ledger("rec",1,1)'
    elif kind == "erase-touches-records":
        victim = next(r["g"] for r in j if r["p"] in commit_pids and r["g"].startswith('^IVG.Ledger("rec"'))
        r = next(r for r in j if r["p"] == erase_pid and r["g"].startswith('^IVG.Ledger("stmt"'))
        j.insert(j.index(r) + 1, {**r, "g": victim, "t": "ZKILL", "n": None})
    elif kind == "frame-violation":
        r = next(r for r in j if r["p"] == redact_pid and r["g"].startswith("^IVG.Ledger"))
        j.insert(j.index(r) + 1, {**r, "g": '^KG("out",0,"acme|1")', "t": "SET"})
    elif kind == "live-stmt-without-tuple":
        r = next(r for r in j if r["p"] == commit_pids[0] and r["g"].startswith('^IVG.Ledger("tuple"'))
        j.remove(r)
    return t


CONTROLS = {"tombstone-outside-target": "RED-I1", "commit-rewrites-history": "commit wrote records outside",
            "erase-touches-records": "erasure changed", "frame-violation": "global:^KG",
            "live-stmt-without-tuple": "INV stmt/tuple"}


def self_test(path: Path) -> int:
    trace = json.loads(path.read_text())
    base = check_trace(trace)
    ok = not base["violations"] and not base["frame"]
    print("unmutated:", "clean" if ok else base["violations"][:3], base["checked"])
    for k, expected in CONTROLS.items():
        try:
            r = check_trace(mutate(trace, k))
            found = r["violations"] + [str(x) for x in r["frame"]]
            hits = [v for v in found if expected in v]
            caught = bool(hits)
            detail = hits[:1] or found[:1]
        except (StopIteration, IndexError) as ex:
            caught, detail = False, [f"control not applicable to this trace: {ex!r}"]
        ok = ok and caught
        print(f"control {k}: {'REJECTED' if caught else 'NOT CAUGHT'} {detail}")
    print("self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test(Path(sys.argv[sys.argv.index("--self-test") + 1]))
    if "--check" in sys.argv:
        rep = check_trace(json.loads(Path(sys.argv[sys.argv.index("--check") + 1]).read_text()))
        print(json.dumps({k: rep[k] for k in ("violations", "frame", "checked", "replay_matches_engine",
                                               "replay_diff_sample", "txn_count_per_op")}, indent=1, default=str))
        return 0 if not rep["violations"] and not rep["frame"] and rep["replay_matches_engine"] else 1
    out = Path(sys.argv[1])
    batch = int(sys.argv[sys.argv.index("--batch") + 1]) if "--batch" in sys.argv else 1
    c = Conn(NS)
    print("engine:", version(c), flush=True)
    c.close()
    rep = run(out, batch)
    print(json.dumps({"ops": [(o["op"], o["ok"], o["seconds"]) for o in rep["ops"]], "checked": rep["checked"],
                      "transactions": len(rep["transactions"]), "violations": rep["violations"],
                      "frame_outside": rep["frame"], "unclassified": rep["unclassified"],
                      "replay_matches_engine": rep["replay_matches_engine"],
                      "replay_diff_sample": rep["replay_diff_sample"], "txn_count_per_op": rep["txn_count_per_op"]},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
