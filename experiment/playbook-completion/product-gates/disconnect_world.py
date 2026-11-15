#!/usr/bin/env python3
"""Integration world: client DISCONNECT at controlled points (playbook §3.7, gate 3.7-integration-worlds).

    source experiment/playbook-completion/environment.sh
    bash experiment/playbook-completion/tools/locks.sh iris python \
        experiment/playbook-completion/product-gates/disconnect_world.py OUT_DIR \
        --group commit|redact|erase|stop|stop2|locktimeout [--trials 3] [--points A1,B1] [--no-baseline]
    python experiment/playbook-completion/product-gates/disconnect_world.py --reevaluate OUT_DIR     # re-judge all
    python experiment/playbook-completion/product-gates/disconnect_world.py --self-test-oracle OUT_DIR

A client OS process performs one product operation through the product's real entry point (IRISGraphEngine on a
DBAPI connection: ledger.commit, ledger.redact, erase_graph) against namespace AUDITIA. It connects through a TCP
proxy (wireproxy.py) that frames the IRIS wire protocol, so the disconnect lands at an exact message. At the point
the harness SIGKILLs the client and the proxy closes both sockets; the server process finds its client gone. Then
the harness waits until that server process has exited, reconnects directly and checks:

  O1 full step or nothing: the server state holds the whole operation or none of it (P-0001: IRIS rolls back the open
     transaction of a dead process), from SQL row counts and the ledger globals, against the point's expectation;
  O2 journal oracle (traces/journal.py, independent of the product): every transaction of the dead server process is
     committed or fully undone (only the documented non-transactional counters survive an undo), none is left open;
  O3 locks released: the ledger head lock ^IVG.Ledger("head") can be taken at once from another process;
  O4 retry: the same call again. A commit with the same idempotency key returns the first answer when the first
     committed (spec 213: "original outcome with replayed=True", contracts/ledger-api.md:26) and commits once when
     it did not; a redaction run again completes and leaves one redaction revision; an erasure again removes the rest;
  O5 replay equals the store: the product's own ledger.verify() is "equal" after the retry (after the erase-then-redact
     flow for erasures, as the product documents it);
  O6 exactly once: after the retry the content exists once (one revision for the key, rows once).

Points (the exact message at which the disconnect happens):
  commit  A1 caller transaction: ledger.commit applied at a nested level, the driver's COMMIT (TC) dropped
          A2 staged commit (payload > 1,000,000 chars): the StageChunk requests reach the server, Commit is dropped
          A3 Commit forwarded; client killed and sockets closed while the server executes it
          B1 Commit executed on the server; its reply held (ambiguous acknowledgement)
          B2 caller transaction: the driver's COMMIT executed; its reply held
  redact  C1 a whole redaction call (max_batches=0) executed on the server; its reply held
          C2 the redaction call forwarded; client killed while the server runs its batches
          C3 a bounded run (max_batches=1 per call): the third call dropped, two batches done
  erase   D1 EraseGraph executed on the server; its reply held
          D2 caller transaction: erase_graph applied, the driver's COMMIT dropped
          D3 EraseGraph forwarded; client killed while the server executes it
  stop    T1, T2, T3 (stop2: T2b) the client's IRIS server process terminated by pid while it executes the call
  locktimeout L1, L2 a second live process holds ^IVG.Ledger("head") for the whole call (O7: documented refusal)
A baseline per group runs the same operation through the proxy without a disconnect. Results: DISCONNECT.md.

Negative controls: --self-test-oracle seeds one defect at a time into recorded observations (partial content,
double application, held lock, a different retry answer, verify diverged, an open or half-undone journal unit, a
redaction left in progress, an erased graph with a surviving row) and requires the checker to flag each; every group
also runs live seeded controls through the product's own API (a second connection holding the head lock; the same
content committed twice under another key; a bounded redaction left open; a node written into an erased graph).

Durability is not tested here (no instance crash): the container runs SynchCommit=0 (env-synchcommit-setting).
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
TRACES = HERE.parent / "traces"
REPO = HERE.parents[2]
NS = "AUDITIA"
DB = "/usr/irissys/mgr/auditia/"
N_SMALL = 300          # relationships per commit (900 operations with auto-stubbed endpoints)
N_STAGED = 7000        # canonical JSON above CHUNK_CHARS (1,000,000): staged path
N_BIG = 6000           # long enough to be mid-execution when cut
REDACT_N = 600
REDACT_BATCH = 50
REDACT_N_BIG = 3000
REDACT_BATCH_SMALL = 1     # one tombstone per batch transaction (scan cap batch x SCANFACTOR = 20 records): a long run
CUT_DELAY = 0.3
OUT_DIR = Path(".")

# Non-transactional counters a rollback does not undo, documented by the product (docs/USER_GUIDE.md:252-258;
# iris_src/src/Graph/KG/Adjacency.cls:28) or by IRIS (an SQL row-id counter, the unsubscripted top node of a data
# global, is $Increment'ed). They may survive an undone unit; nothing else may.
COUNTER_RE = re.compile(r'^\^(KG\("gen",|KG\("__version"\)|IVG\.AdjNoLock\(|NKG\(-3,|NKG\("\$meta",)')


STATS_ROOTS = {"^Graph.KG.LedgerStatsD"}


def is_counter(node: str) -> bool:
    return bool(COUNTER_RE.match(node)) or "(" not in node


# ----------------------------------------------------------------------------------------------- the client process
def lb(s: str) -> bytes:
    """One $LIST string item as the Native API sends a class or method name."""
    return bytes([len(s) + 2, 1]) + s.encode()


def client_main(spec: dict) -> None:
    sys.path.insert(0, str(TOOLS))
    sys.path.insert(0, str(REPO))
    from iris_conn import Conn
    from iris_vector_graph.engine import IRISGraphEngine

    def emit(x):
        print(json.dumps(x), flush=True)

    c = Conn(NS)                 # IVG_PORT points at the proxy
    emit({"pid": c.pid})
    eng = IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4)
    if spec.get("caller_txn"):
        cur = c.conn.cursor()
        cur.execute("START TRANSACTION")
        cur.close()
    op = spec["op"]
    try:
        _client_op(eng, spec, emit)
    except Exception as ex:  # noqa: BLE001 - the answer the caller would see
        emit({"error": f"{type(ex).__name__}: {ex}"})
        return
    if spec.get("caller_txn"):
        c.conn.commit()
        emit({"caller_committed": True})
    emit({"done": True})


def _client_op(eng, spec: dict, emit) -> None:
    op = spec["op"]
    if op == "commit":
        r = eng.ledger.commit(make_changeset(spec))
        emit({"commit": {"seq": r.revision.seq, "revision_id": r.revision.revision_id, "replayed": bool(r.replayed)}})
    elif op == "redact":
        for i in range(int(spec.get("calls", 1))):
            rc = eng.ledger.redact(spec["graph"], batch_size=int(spec["batch"]), max_batches=int(spec.get("max_batches", 0)))
            emit({"redact_call": i + 1, "complete": rc.complete, "tombstoned": rc.records_tombstoned, "batches": rc.batches})
            if rc.complete:
                break
    elif op == "erase":
        emit({"erase": int(eng.erase_graph(spec["graph"]))})


def make_changeset(spec: dict):
    from iris_vector_graph.ledger import Changeset
    cs = Changeset(actor="audit:disconnect", actor_type="ingest", idempotency_key=spec["key"],
                   auto_stub_missing_nodes=True)
    t, g = spec["tag"], spec["graph"]
    for i in range(int(spec["n"])):
        cs.create_relationship(f"{t}a{i}", "R", f"{t}b{i}", graph=g)
    return cs


# ----------------------------------------------------------------------------------------------- harness helpers
def _imports():
    sys.path.insert(0, str(TOOLS))
    sys.path.insert(0, str(TRACES))
    sys.path.insert(0, str(HERE))


def engine(c):
    from iris_vector_graph.engine import IRISGraphEngine
    return IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4)


def head(c) -> int:
    return int(c.o.get("^IVG.Ledger", "head") or 0)


def lock_free(c) -> bool:
    """O3: the head lock can be taken at once by another process (then released)."""
    try:
        c.o.lock("", 0, "^IVG.Ledger", "head")
    except Exception:  # noqa: BLE001 - <TIMEOUT>: someone holds it
        return False
    c.o.unlock("", "^IVG.Ledger", "head")
    return True


def exists(c, pid: str) -> bool:
    return bool(int(c.call("%SYS.ProcessQuery", "%ExistsId", pid) or 0))


_COUNT = r'''
 set lo={lo}, hi={hi}, g="{g}", t="{t}", key="{key}", lv=0
 for q=lo:1:hi {{ set (n,cr,cg,tb,rd)=0, o="" for {{ set o=$order(^IVG.Ledger("rec",q,o),1,v) quit:o=""  set n=n+1, op=$listget(v,1) if op="redacted" {{ set tb=tb+1 }} elseif op="redact" {{ set rd=rd+1 }} elseif op="create_rel" {{ set cr=cr+1 if $listget(v,7)=g {{ set cg=cg+1 }} }} }} write $char(30),"SEQ|",q,"|",n,"|",cr,"|",cg,"|",tb,"|",rd,! }}
 set s=t for {{ set s=$order(^IVG.Ledger("tuple",s)) quit:s=""  quit:$extract(s,1,$length(t))'=t  set p="" for {{ set p=$order(^IVG.Ledger("tuple",s,p)) quit:p=""  set o="" for {{ set o=$order(^IVG.Ledger("tuple",s,p,o)) quit:o=""  if $data(^IVG.Ledger("tuple",s,p,o,key)) {{ set lv=lv+1 }} }} }} }}
'''


def srv_counts(lo: int, hi: int, g: str, t: str, key: str) -> dict:
    """Ledger counts read server-side in one terminal session (plain ObjectScript, nothing compiled; as journal.py):
    per revision seq in [lo, hi] its records, create_rel records (all, and in graph g), tombstones and redaction
    records; and the live tuple entries of tag t's relationships in graph key `key`."""
    body = _COUNT.format(lo=int(lo), hi=int(hi), g=g.replace('"', '""'), t=t.replace('"', '""'),
                         key=key.replace('"', '""'))
    line = " " + " ".join(x.strip() for x in body.strip().splitlines()) + ' write $char(30),"LIVE|",lv,! write $char(30),"END|",!\n halt\n'
    container = os.environ["IVG_TEST_CONTAINER"]
    r = subprocess.run(["docker", "exec", "-i", container, "iris", "session", "IRIS", "-U", NS], input=line,
                       capture_output=True, text=True, timeout=600)
    out = r.stdout.replace("\r", "")
    if "\x1eEND|" not in out:
        raise RuntimeError("server count did not finish: " + out[-800:])
    per, live = {}, None
    for ln in out.split("\n"):
        if ln.startswith("\x1eSEQ|"):
            _, q, n, cr, cg, tb, rd = ln[1:].split("|")
            per[int(q)] = {"records": int(n), "create_rel": int(cr), "create_rel_in_graph": int(cg),
                           "tombstones": int(tb), "redact": int(rd)}
        elif ln.startswith("\x1eLIVE|"):
            live = int(ln[1:].split("|")[1])
    return {"per_seq": per, "live_tuples": live}


def commit_state(c, spec: dict, start_head: int) -> dict:
    t, g, n = spec["tag"], spec["graph"], int(spec["n"])
    h = head(c)
    edges = int(c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ? AND s %STARTSWITH ?", g, t)[0][0])
    nodes = int(c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH ?", t)[0][0])
    key = str(c.call("Graph.KG.GraphKey", "ForLedger", g))
    sc = srv_counts(start_head + 1, h, g, t, key)
    revs = sc["per_seq"]
    with_content = sorted(q for q, r in revs.items() if r["create_rel"])
    rel_records = sum(r["create_rel"] for r in revs.values())
    live = sc["live_tuples"]
    idem = c.o.getIRISList("^IVG.Ledger", "idem", spec["key"]) if c.o.isDefined("^IVG.Ledger", "idem", spec["key"]) else None
    rows = int(c.sql("SELECT COUNT(*) FROM Graph_KG.ledger_revisions")[0][0])
    ids = [str(c.o.get("^IVG.Ledger", "idBySeq", q) or "") for q in with_content]
    return {"content_revision_ids": ids, "head": h, "revisions_after_start": h - start_head, "revisions_with_content": with_content,
            "create_rel_records": rel_records, "edge_rows": edges, "node_rows": nodes, "live_statements": live,
            "idem_seq": int(idem.get(1)) if idem is not None else None, "revision_rows": rows}


def commit_outcome(s: dict, n: int) -> str:
    # an auto-stubbed endpoint gets a row in the default graph (the ledger's node records are graph-blind) and one
    # in the relationship's graph: 4 node rows per relationship (the baseline shows the same)
    full = (s["edge_rows"] == n and s["node_rows"] == 4 * n and s["create_rel_records"] == n
            and len(s["revisions_with_content"]) == 1 and s["live_statements"] == n
            and s["idem_seq"] == s["revisions_with_content"][0])
    none = (s["edge_rows"] == 0 and s["node_rows"] == 0 and s["create_rel_records"] == 0
            and not s["revisions_with_content"] and s["live_statements"] == 0 and s["idem_seq"] is None)
    return "full" if full else "nothing" if none else "partial"


def graph_state(c, spec: dict, rec_lo: int, rec_hi: int, start_head: int) -> dict:
    """Erasure and redaction targets: the graph's rows, its live statements, its records (tombstoned or not)."""
    t, g, n = spec["tag"], spec["graph"], int(spec["n"])
    h = head(c)
    edges = int(c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ?", g)[0][0])
    gnodes = int(c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", g)[0][0])
    key = str(c.call("Graph.KG.GraphKey", "ForLedger", g))
    tgt = srv_counts(rec_lo, rec_hi, g, t, key)
    live = tgt["live_tuples"]
    content = sum(r["create_rel_in_graph"] for r in tgt["per_seq"].values())
    tomb = sum(r["tombstones"] for r in tgt["per_seq"].values())
    later = srv_counts(start_head + 1, h, g, t, key)["per_seq"] if h > start_head else {}
    redaction_revs = sorted(q for q, r in later.items() if r["redact"])
    return {"head": h, "revisions_after_start": h - start_head, "edge_rows": edges, "graph_node_rows": gnodes,
            "live_statements": live,
            "target_records_content": content, "target_records_tombstoned": tomb,
            "marker": bool(int(c.o.isDefined("^IVG.Ledger", "redacting") or 0)),
            "redaction_revisions_after_start": redaction_revs, "later_revisions": later}


def verify(c) -> str:
    v = engine(c).ledger.verify()
    return str(getattr(v, "result", v))


def journal_units(recs: list) -> dict:
    """O2 over the dead server process's journal records, in journal order.

    A span runs from an outermost BeginTrans to its CommitTrans; nested levels ("BeginTrans with level" / "CommitTrans
    Pending with level") stay inside it. IRIS journals a rollback, also the one a dying process performs, as
    compensating SET/KILL records with InTransaction=0 inside the span before its final CommitTrans (observed here),
    so a span's outcome is its net effect over ALL its records: "committed" when non-counter nodes changed, "undone"
    when only counters changed although it wrote non-counter nodes (compensated), "empty" otherwise, and "open" when no
    CommitTrans closes it. Data records outside every span are reported as "outside-transaction" writes.
    """
    import journal
    spans, cur, outside = [], None, []
    for r in recs:
        t = r["t"]
        if t == "BeginTrans" or (t.startswith("BeginTrans") and cur is None):
            cur = {"records": [], "begin": r["a"], "nested": 0}
            continue
        if t.startswith("BeginTrans"):
            cur["nested"] += 1
            continue
        if t == "CommitTrans":
            if cur is not None:
                cur["end"] = r["a"]
                spans.append(cur)
            cur = None
            continue
        if t.startswith("CommitTrans"):
            continue
        if not r["g"]:
            continue
        (cur["records"] if cur is not None else outside).append(r)
    if cur is not None:
        cur["end"] = None
        spans.append(cur)
    units = []
    for sp in spans:
        ne = journal.net_effect(sp["records"])
        ne_nc = {g: v for g, v in ne.items() if not is_counter(g)}
        wrote = [x for x in sp["records"] if x["x"] and not is_counter(x["g"])]
        comp = [x for x in sp["records"] if not x["x"] and not is_counter(x["g"])]
        roots = {journal.global_root(g) for g in ne_nc}
        if sp["end"] is None:
            cls = "open"
        elif ne_nc and roots <= STATS_ROOTS:
            cls = "stats-only"      # a rejection counter bumped after the rollback (LedgerStats.cls:1-3)
        elif ne_nc:
            cls = "committed"
        elif wrote:
            cls = "undone"
        else:
            cls = "empty"
        units.append({"class": cls, "records": len(sp["records"]), "writes_in_txn": len(wrote),
                      "compensations": len(comp), "net_nodes": len(ne_nc), "net_counters": len(ne) - len(ne_nc),
                      "ledger_rec_nodes": sum(1 for g in ne_nc if g.startswith('^IVG.Ledger("rec",')),
                      "begin": sp["begin"], "end": sp["end"], "nested_levels": sp["nested"],
                      "net_roots": sorted({journal.global_root(g) for g in ne_nc})[:12]})
    out_ne = journal.net_effect(outside)
    out_nc = {g: v for g, v in out_ne.items() if not is_counter(g)}
    if out_nc:
        units.append({"class": "outside-transaction", "records": len(outside), "net_nodes": len(out_nc),
                      "ledger_rec_nodes": 0, "net_roots": sorted({journal.global_root(g) for g in out_nc})[:12]})
    types: dict = {}
    for r in recs:
        types[r["t"]] = types.get(r["t"], 0) + 1
    tot: dict = {}
    for x in units:
        tot[x["class"]] = tot.get(x["class"], 0) + 1
    return {"units": units, "unit_classes": tot, "record_types": types, "records": len(recs),
            "outside_counter_records": len(outside) - sum(1 for x in outside if not is_counter(x["g"]))}


# ----------------------------------------------------------------------------------------------- the checker (O1-O6)
def check(point: str, cfg: dict, obs: dict) -> list:
    """Violations of O1-O6 for one trial observation. Pure function: the negative controls call it on seeded data."""
    bad = []
    group, expect = cfg["group"], cfg["expect"]
    j = obs.get("journal") or {}
    classes = j.get("unit_classes", {})
    if obs.get("server_exited") is not True:
        bad.append("O2 server process still alive after the disconnect")
    if classes.get("open"):
        bad.append(f"O2 {classes['open']} transaction(s) of the dead process left open")
    if classes.get("outside-transaction"):
        bad.append("O2 the dead process wrote non-counter nodes outside any transaction")
    if obs.get("lock_free_after_kill") is not True:
        bad.append("O3 ledger head lock not free after the dead process exited")
    if obs.get("lock_free_after_retry") is not True:
        bad.append("O3 ledger head lock not free after the retry")
    out1 = obs.get("outcome_after_kill")
    if out1 == "partial" or out1 is None:
        bad.append(f"O1 state after the disconnect is {out1}: neither the full step nor nothing")
    elif expect != "either" and out1 != expect:
        bad.append(f"O1 outcome {out1}, the point determines {expect}")
    committed_units = sum(1 for u in j.get("units", []) if u["class"] == "committed")
    if out1 in ("nothing", "in-progress-0") and committed_units and group != "redact":
        bad.append(f"O2 journal shows {committed_units} committed unit(s) of the dead process but the state shows nothing")
    if group == "commit":
        if out1 == "full" and not any(u["ledger_rec_nodes"] == 3 * cfg["n"] for u in j.get("units", [])
                                      if u["class"] == "committed"):
            bad.append("O2 no committed unit of the dead process carries the revision's records")
        r = obs.get("retry") or {}
        if "error" in r:
            bad.append(f"O4 retry raised {r['error'][:120]}")
        elif out1 == "full":
            # the first answer: the reply the client never read (held, or printed before its COMMIT was lost); when
            # no reply ever left the server (cut), the revision the state holds is the only first outcome there is
            s1 = obs.get("state_after_kill") or {}
            first = obs.get("first_answer") or (
                {"seq": s1["revisions_with_content"][0], "revision_id": (s1.get("content_revision_ids") or [None])[0]}
                if s1.get("revisions_with_content") else {})
            if not r.get("replayed") or r.get("revision_id") != first.get("revision_id") or r.get("seq") != first.get("seq"):
                bad.append(f"O4 same-key retry answered {r}, the first outcome was {first}")
        elif out1 == "nothing" and r.get("replayed"):
            bad.append("O4 retry replayed a revision the state does not hold")
        if obs.get("outcome_after_retry") != "full":
            bad.append(f"O6 after the retry the content is {obs.get('outcome_after_retry')}, not exactly once")
        s2 = obs.get("state_after_retry") or {}
        if s2.get("revision_rows") != s2.get("head"):
            bad.append("O6 revision rows differ from the head")
    if group == "redact":
        s1 = obs.get("state_after_kill") or {}
        tomb_units = [u for u in j.get("units", []) if u["class"] == "committed" and u["ledger_rec_nodes"]]
        if any(u["ledger_rec_nodes"] % cfg["batch"] and u is not tomb_units[-1] for u in tomb_units):
            bad.append("O2 a committed batch unit tombstoned a partial batch")
        if s1.get("target_records_content", 0) + s1.get("target_records_tombstoned", 0) != cfg["n"]:
            bad.append("O1 target records neither content nor tombstone")
        r = obs.get("retry") or {}
        if "error" in r or r.get("complete") is not True:
            bad.append(f"O4 the re-run did not complete: {r}")
        s2 = obs.get("state_after_retry") or {}
        if s2.get("marker") or s2.get("target_records_content") or s2.get("target_records_tombstoned") != cfg["n"]:
            bad.append(f"O6 after the re-run marker={s2.get('marker')} content={s2.get('target_records_content')}")
        if len(s2.get("redaction_revisions_after_start", [])) != 1:
            bad.append(f"O6 redaction revisions after start: {s2.get('redaction_revisions_after_start')} (want one)")
    if group == "erase":
        r = obs.get("retry") or {}
        if "error" in r:
            bad.append(f"O4 retry raised {r['error'][:120]}")
        elif out1 == "full" and r.get("removed") != 0:
            bad.append(f"O4 retry removed {r.get('removed')} rows after a full erasure")
        elif out1 == "nothing" and r.get("removed") != cfg["rows"]:
            bad.append(f"O4 retry removed {r.get('removed')} rows, want {cfg['rows']}")
        s2 = obs.get("state_after_retry") or {}
        if s2.get("edge_rows") or s2.get("live_statements") or s2.get("graph_node_rows"):
            bad.append("O6 rows or statements of the graph left after the retry")
        if s2.get("target_records_content", 0) + s2.get("target_records_tombstoned", 0) != cfg["n"]:
            bad.append("O6 the erasure changed the ledger's records")
    if cfg.get("mode") == "lockheld":
        errs = [x.get("error", "") for x in obs.get("client_lines", []) if "error" in x]
        if not any(("LockTimeout" in e) or ("lock_timeout" in e) or ("head lock" in e) for e in errs):
            bad.append("O7 the call under a held head lock was not refused with the documented lock-timeout error")
    if obs.get("verify_after_retry") != "equal":
        bad.append(f"O5 verify after the retry is {obs.get('verify_after_retry')}")
    return bad


def outcome_graph(s: dict, n: int, group: str) -> str:
    if group == "erase":
        if s["edge_rows"] == 0 and s["live_statements"] == 0 and s.get("graph_node_rows", 0) == 0:
            return "full"
        if s["edge_rows"] == n and s["live_statements"] == n and s.get("graph_node_rows") == 2 * n:
            return "nothing"
        return "partial"
    # redact
    if s["target_records_content"] + s["target_records_tombstoned"] != n:
        return "partial"
    if not s["marker"] and s["target_records_content"] == 0 and len(s["redaction_revisions_after_start"]) == 1:
        return "complete"
    if s["marker"] and not s["redaction_revisions_after_start"]:
        return f"in-progress-{s['target_records_tombstoned']}"
    if not s["marker"] and s["target_records_tombstoned"] == 0 and not s["redaction_revisions_after_start"]:
        return "in-progress-0"
    return "partial"


# ----------------------------------------------------------------------------------------------- points
def pred_call(cls: str, method: str, nth: int = 1):
    seen = {"n": 0}
    a, b = lb(cls), lb(method)

    def p(m) -> bool:
        if m.mtype != "K\xc2" or a not in m.payload or b not in m.payload:
            return False
        seen["n"] += 1
        return seen["n"] == nth
    return p


def pred_tc(m) -> bool:
    return m.mtype == "TC"


POINTS = {
    "A1": {"group": "commit", "mode": "drop", "pred": "TC", "caller_txn": True, "n": N_SMALL, "expect": "nothing",
           "desc": "caller transaction: ledger.commit applied at a nested level; the driver's COMMIT (TC) dropped"},
    "A2": {"group": "commit", "mode": "drop", "pred": "Commit", "n": N_STAGED, "expect": "nothing",
           "desc": "staged commit: every StageChunk request reached the server; the Commit request dropped"},
    "A3": {"group": "commit", "mode": "cut", "pred": "Commit", "n": N_BIG, "expect": "either",
           "desc": f"Commit forwarded; client killed and sockets closed {CUT_DELAY} s later, the server executing it"},
    "B1": {"group": "commit", "mode": "hold", "pred": "Commit", "n": N_SMALL, "expect": "full",
           "desc": "Commit executed on the server; its reply held: ambiguous acknowledgement"},
    "B2": {"group": "commit", "mode": "hold", "pred": "TC", "caller_txn": True, "n": N_SMALL, "expect": "full",
           "desc": "caller transaction: the driver's COMMIT executed on the server; its reply held"},
    "C1": {"group": "redact", "mode": "hold", "pred": "Redact", "n": REDACT_N, "batch": REDACT_BATCH,
           "max_batches": 0, "expect": "complete",
           "desc": "a whole redaction call (max_batches=0) executed on the server; its reply held"},
    "C2": {"group": "redact", "mode": "cut", "pred": "Redact", "n": REDACT_N_BIG, "batch": REDACT_BATCH_SMALL,
           "max_batches": 0, "expect": "either", "cut_delay": 0.02,
           "desc": "the redaction call forwarded; client killed 0.02 s later while the server runs its batches"},
    "C3": {"group": "redact", "mode": "drop", "pred": "Redact", "nth": 3, "n": REDACT_N, "batch": REDACT_BATCH,
           "max_batches": 1, "calls": 50, "expect": f"in-progress-{2 * REDACT_BATCH}", "fresh_ledger": True,
           "desc": "bounded run, one batch per call, on a fresh ledger (a bounded call rescans from the first record, "
                   "F-C1303): the third call dropped after two batches"},
    "D1": {"group": "erase", "mode": "hold", "pred": "EraseGraph", "n": N_SMALL, "expect": "full",
           "desc": "EraseGraph executed on the server; its reply held"},
    "D2": {"group": "erase", "mode": "drop", "pred": "TC", "caller_txn": True, "n": N_SMALL, "expect": "nothing",
           "desc": "caller transaction: erase_graph applied; the driver's COMMIT (TC) dropped"},
    "D3": {"group": "erase", "mode": "cut", "pred": "EraseGraph", "n": N_BIG, "expect": "either", "cut_delay": 0.05,
           "desc": "EraseGraph forwarded; client killed 0.05 s later, the server executing it"},
}
POINTS.update({
    # process stop: the client's IRIS server process is terminated (%SYSTEM.Process.Terminate, by its recorded pid)
    # while it executes the call; the only way to interrupt a batch, since a disconnect does not stop a running call
    "T1": {"group": "commit", "mode": "stop", "pred": "Commit", "n": N_BIG, "expect": "either", "cut_delay": 0.3,
           "desc": "Commit forwarded; the client's server process terminated 0.3 s later, inside the commit transaction"},
    "T2": {"group": "redact", "mode": "stop", "pred": "Redact", "n": REDACT_N_BIG, "batch": REDACT_BATCH_SMALL,
           "max_batches": 0, "expect": "either", "cut_delay": 0.02,
           "desc": "redaction call forwarded; the client's server process terminated 0.02 s later, mid-run"},
    "T2b": {"group": "redact", "mode": "stop", "pred": "Redact", "n": REDACT_N_BIG, "batch": REDACT_BATCH_SMALL,
            "max_batches": 0, "expect": "either", "cut_delay": 0.01, "after_marker": True,
            "desc": "redaction call forwarded; the client's server process terminated 0.01 s after its marker appeared, "
                    "i.e. while it runs its batch transactions"},
    "T3": {"group": "erase", "mode": "stop", "pred": "EraseGraph", "n": N_BIG, "expect": "either", "cut_delay": 0.05,
           "desc": "EraseGraph forwarded; the client's server process terminated 0.05 s later, inside the erase"},
    # lock timeout: another live process holds ^IVG.Ledger("head") for longer than LOCKTIMEOUT (30 s)
    "L1": {"group": "commit", "mode": "lockheld", "n": N_SMALL, "expect": "nothing",
           "desc": "the head lock held by another process for the whole call: the commit waits 30 s and is refused"},
    "L2": {"group": "redact", "mode": "lockheld", "n": REDACT_N, "batch": REDACT_BATCH, "max_batches": 0,
           "expect": "either", "fresh_ledger": True,
           "desc": "the head lock held by another process: the redaction's first batch waits 30 s and is refused"},
})
GROUPS = {"commit": ["A1", "A2", "A3", "B1", "B2"], "redact": ["C1", "C2", "C3"], "erase": ["D1", "D2", "D3"],
          "stop": ["T1", "T2", "T3"], "stop2": ["T2b"], "locktimeout": ["L1", "L2"]}


def predicate(cfg: dict):
    p = cfg.get("pred")
    if p == "TC":
        return pred_tc
    if p == "Commit":
        return pred_call("Graph.KG.Ledger", "Commit")
    if p == "Redact":
        return pred_call("Graph.KG.LedgerRedact", "Redact", cfg.get("nth", 1))
    if p == "EraseGraph":
        return pred_call("Graph.KG.Eraser", "EraseGraph")
    raise ValueError(p)


# ----------------------------------------------------------------------------------------------- one trial
def spawn(spec: dict, port: int) -> subprocess.Popen:
    env = dict(os.environ, IVG_PORT=str(port))
    return subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--client", json.dumps(spec)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)


def read_json_lines(text: str) -> list:
    out = []
    for ln in text.splitlines():
        if ln.startswith("{"):
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return out


def prepare(ctl, point: str, cfg: dict, trial: str) -> dict:
    """Per-trial spec and its preconditions (set up through the product's own API on a direct connection)."""
    g = cfg["group"]
    tag = f"{point.lower()}{trial}_"
    spec = {"op": {"commit": "commit", "redact": "redact", "erase": "erase"}[g], "tag": tag,
            "graph": f"DW_{point}_{trial}", "n": cfg["n"], "key": f"dw-{point}-{trial}-{int(time.time())}",
            "caller_txn": bool(cfg.get("caller_txn"))}
    if g in ("redact", "erase"):
        lo = head(ctl) + 1
        engine(ctl).ledger.commit(make_changeset(dict(spec, key=spec["key"] + "-setup")))
        spec["rec_lo"], spec["rec_hi"] = lo, head(ctl)
        # erase_graph returns the Graph_KG.nodes and Graph_KG.rdf_edges rows it removed (nodes_edges.py:1496-1498)
        spec["rows"] = int(ctl.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ?", spec["graph"])[0][0]) + \
            int(ctl.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", spec["graph"])[0][0])
        if g == "redact":
            engine(ctl).erase_graph(spec["graph"])
            spec.update(batch=cfg["batch"], max_batches=cfg["max_batches"], calls=cfg.get("calls", 1))
    return spec


def state(ctl, spec: dict, cfg: dict, start_head: int) -> dict:
    if cfg["group"] == "commit":
        return commit_state(ctl, spec, start_head)
    return graph_state(ctl, spec, spec["rec_lo"], spec["rec_hi"], start_head)


def outcome(s: dict, spec: dict, cfg: dict) -> str:
    if cfg["group"] == "commit":
        return commit_outcome(s, int(spec["n"]))
    return outcome_graph(s, int(spec["n"]), cfg["group"])


def reset(ctl) -> None:
    """A fresh namespace state through the product's own API (as traces/lost_ack.py and crash_world.py do)."""
    ctl.call("Graph.KG.Eraser", "EraseAll")
    ctl.call("Graph.KG.Ledger", "PurgeAll")
    engine(ctl).ledger.enable()
    ctl.conn.commit()


def trial(ctl, point: str, cfg: dict, idx: str, baseline: bool = False) -> dict:
    import journal
    from wireproxy import Proxy
    if cfg.get("fresh_ledger"):
        reset(ctl)
    spec = prepare(ctl, point, cfg, idx)
    start_head = head(ctl)
    s0 = state(ctl, spec, cfg, start_head)
    jm = journal.mark()
    px = Proxy(int(os.environ["IVG_PORT"]))
    if not baseline and cfg["mode"] in ("drop", "hold", "cut", "stop"):
        (px.drop_request if cfg["mode"] == "drop" else px.hold_reply)(predicate(cfg))
    holder = None
    if not baseline and cfg["mode"] == "lockheld":
        from iris_conn import Conn as _C
        holder = _C(NS)
        holder.o.lock("", 5, "^IVG.Ledger", "head")
    terminated = None
    t0 = time.time()
    p = spawn(spec, px.port)
    first = json.loads(p.stdout.readline() or "{}")
    pid = first.get("pid")
    event, killed = None, False
    deadline = time.time() + 600
    while time.time() < deadline:
        if baseline:
            if p.poll() is not None:
                event = "client-finished"
                break
        elif cfg["mode"] == "drop" and px.request_dropped.is_set():
            event = "request-dropped"
            break
        elif cfg["mode"] == "hold" and px.reply_held.is_set():
            event = "reply-held"
            break
        elif cfg["mode"] == "cut" and px.request_forwarded.is_set():
            time.sleep(cfg.get("cut_delay", CUT_DELAY))
            event = "cut-after-request" + ("-reply-already-held" if px.reply_held.is_set() else "-reply-pending")
            break
        elif cfg["mode"] == "stop" and px.request_forwarded.is_set():
            if cfg.get("after_marker"):
                # batches have started once the run's marker is visible (a dirty read of ^IVG.Ledger("redacting"))
                t_m = time.time()
                while time.time() - t_m < 30 and not int(ctl.o.isDefined("^IVG.Ledger", "redacting") or 0):
                    time.sleep(0.001)
            time.sleep(cfg.get("cut_delay", CUT_DELAY))
            pending = not px.reply_held.is_set()
            terminated = int(ctl.call("%SYSTEM.Process", "Terminate", pid) or 0)
            event = "server-terminated" + ("-reply-pending" if pending else "-reply-already-held")
            break
        elif cfg["mode"] == "lockheld":
            if p.poll() is not None:
                event = "client-finished-under-held-lock"
                break
            time.sleep(0.05)
            continue
        if p.poll() is not None:
            event = "client-finished-before-point"
            break
        time.sleep(0.005)
    t_event = time.time()
    if p.poll() is None:
        os.kill(p.pid, signal.SIGKILL)
        killed = True
    out, err = p.communicate(timeout=60)
    px.close()
    if holder is not None:
        holder.o.unlock("", "^IVG.Ledger", "head")
        holder.close()
    lines = read_json_lines(out)
    exited, t_exit = False, None
    end = time.time() + 600
    while pid and time.time() < end:
        if not exists(ctl, pid):
            exited, t_exit = True, time.time()
            break
        time.sleep(0.1)
    held = px.held.decode("latin-1", "replace") if px.held else ""
    m = re.search(r'"revision":\{"seq":(\d+),"revision_id":"(\w+)"', held)
    first_answer = {"seq": int(m.group(1)), "revision_id": m.group(2)} if m else None
    if cfg["group"] == "commit" and first_answer is None:
        prior = [x["commit"] for x in lines if "commit" in x]
        if prior:
            first_answer = {"seq": prior[-1]["seq"], "revision_id": prior[-1]["revision_id"]}
    recs = journal.records_since(jm, dbs={DB}, pids={str(pid)}) if pid else []
    import gzip
    with gzip.open(OUT_DIR / f"journal-{point}-{idx}.jsonl.gz", "wt") as fh:   # the raw oracle input, kept
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    with gzip.open(OUT_DIR / f"proxy-{point}-{idx}.jsonl.gz", "wt") as fh:      # every framed message, in order
        for x in px.log:
            fh.write(json.dumps(x) + "\n")
    jsum = journal_units(recs)
    lock1 = lock_free(ctl)
    s1 = state(ctl, spec, cfg, start_head)
    out1 = outcome(s1, spec, cfg)
    # O4: the same call again, on a fresh direct connection
    from iris_conn import Conn
    rc = Conn(NS)
    try:
        e2 = engine(rc)
        if cfg["group"] == "commit":
            r = e2.ledger.commit(make_changeset(spec))
            retry = {"seq": r.revision.seq, "revision_id": r.revision.revision_id, "replayed": bool(r.replayed)}
        elif cfg["group"] == "redact":
            r = e2.ledger.redact(spec["graph"], batch_size=int(spec["batch"]), max_batches=0)
            retry = {"complete": r.complete, "records_tombstoned": r.records_tombstoned, "batches": r.batches}
        else:
            retry = {"removed": int(e2.erase_graph(spec["graph"]))}
            r = e2.ledger.redact(spec["graph"], batch_size=500, max_batches=0)  # the documented erase-then-redact flow
            retry["redaction_complete"] = r.complete
    except Exception as ex:  # noqa: BLE001
        retry = {"error": f"{type(ex).__name__}: {ex}"}
    finally:
        rc.close()
    lock2 = lock_free(ctl)
    s2 = state(ctl, spec, cfg, start_head)
    v = verify(ctl)
    obs = {"point": point, "trial": idx, "baseline": baseline, "desc": cfg["desc"], "spec": spec,
           "server_pid": pid, "event": event, "client_killed": killed, "client_lines": lines,
           "client_stderr_tail": err[-400:] if err else "", "seconds_to_event": round(t_event - t0, 3),
           "server_exited": exited, "seconds_kill_to_exit": round(t_exit - t_event, 3) if t_exit else None,
           "proxy_trigger": px.trigger_msg.text()[:120] if px.trigger_msg else None,
           "held_reply_preview": held[:200], "first_answer": first_answer, "journal": jsum,
           "state_before": s0, "lock_free_after_kill": lock1, "state_after_kill": s1, "outcome_after_kill": out1,
           "retry": retry, "lock_free_after_retry": lock2, "state_after_retry": s2,
           "outcome_after_retry": outcome(s2, spec, cfg), "verify_after_retry": v,
           "proxy_messages": len(px.log), "terminate_rc": terminated,
           "server_call_seconds": round(px.t_reply - px.t_request, 4) if px.t_reply and px.t_request else None,
           "cut_seconds_after_request": round(t_event - px.t_request, 4) if px.t_request and cfg["mode"] == "cut" else None,
           "stagechunk_requests": sum(1 for x in px.log if x[1] == "c2s" and "StageChunk" in x[5])}
    if cfg["group"] == "commit":
        obs["outcome_after_retry"] = commit_outcome(s2, int(spec["n"]))
    if baseline:
        obs["violations"] = [] if out1 in ("full", "complete") and v == "equal" else [f"baseline {out1} {v}"]
    else:
        valid = event not in (None, "client-finished-before-point")
        obs["violations"] = check(point, dict(cfg, rows=spec.get("rows")), obs) if valid else [f"point not reached: {event}"]
    return obs


# ----------------------------------------------------------------------------------------------- live seeded controls
def live_controls(ctl, group: str) -> list:
    """Defects seeded through the product's own API; the checker must flag each."""
    from iris_conn import Conn
    res = []
    if group == "commit":
        cfg = POINTS["B1"]
        spec = prepare(ctl, "K1", cfg, "1")
        start = head(ctl)
        e = engine(ctl)
        first = e.ledger.commit(make_changeset(spec))
        # seeded defect 1: another live process holds the head lock while the checker looks
        holder = Conn(NS)
        holder.o.lock("", 5, "^IVG.Ledger", "head")
        lock = lock_free(ctl)
        holder.o.unlock("", "^IVG.Ledger", "head")
        holder.close()
        # seeded defect 2: the tag's content applied a second time under another key (a second revision of
        # relationships between the same endpoints, predicate R2: a duplicate R edge would be refused)
        from iris_vector_graph.ledger import Changeset
        dup = Changeset(actor="audit:disconnect", actor_type="ingest", idempotency_key=spec["key"] + "-dup",
                        auto_stub_missing_nodes=True)
        for i in range(cfg["n"]):
            dup.create_relationship(f"{spec['tag']}a{i}", "R2", f"{spec['tag']}b{i}", graph=spec["graph"])
        e.ledger.commit(dup)
        s = commit_state(ctl, spec, start)
        obs = {"server_exited": True, "journal": {"units": [{"class": "committed", "ledger_rec_nodes": 3 * cfg["n"],
                                                             "net_nodes": 1}], "unit_classes": {"committed": 1}},
               "lock_free_after_kill": lock, "lock_free_after_retry": True, "state_after_kill": s,
               "outcome_after_kill": commit_outcome(s, cfg["n"]),
               "first_answer": {"seq": first.revision.seq, "revision_id": first.revision.revision_id},
               "retry": {"seq": first.revision.seq, "revision_id": first.revision.revision_id, "replayed": True},
               "state_after_retry": s, "outcome_after_retry": commit_outcome(s, cfg["n"]), "verify_after_retry": verify(ctl)}
        v = check("B1", cfg, obs)
        res.append({"control": "live-commit-held-lock-and-double-application", "state": s, "lock_free_seen": lock,
                    "violations": v, "caught": any(x.startswith("O3") for x in v) and any(x.startswith(("O1", "O6")) for x in v)})
        # seeded defect 3: a retry under the same key with a different changeset (the product refuses it)
        try:
            e.ledger.commit(make_changeset(dict(spec, n=cfg["n"] - 1)))
            retry = {"seq": None, "error": "accepted"}
        except Exception as ex:  # noqa: BLE001
            retry = {"error": f"{type(ex).__name__}: {ex}"}
        obs3 = dict(obs, lock_free_after_kill=True, retry=retry)
        v3 = check("B1", cfg, obs3)
        res.append({"control": "live-commit-retry-other-changeset-same-key", "retry": retry, "violations": v3,
                    "caught": any(x.startswith("O4") for x in v3)})
    if group == "redact":
        cfg = POINTS["C1"]
        reset(ctl)   # the bounded call must reach the target (F-C1303)
        spec = prepare(ctl, "K2", cfg, "1")
        start = head(ctl)
        e = engine(ctl)
        r = e.ledger.redact(spec["graph"], batch_size=cfg["batch"], max_batches=1)  # leaves the run open
        s = graph_state(ctl, spec, spec["rec_lo"], spec["rec_hi"], start)
        obs = {"server_exited": True, "journal": {"units": [], "unit_classes": {}}, "lock_free_after_kill": True,
               "lock_free_after_retry": True, "state_after_kill": s, "outcome_after_kill": outcome_graph(s, cfg["n"], "redact"),
               "retry": {"complete": r.complete}, "state_after_retry": s, "verify_after_retry": verify(ctl)}
        v = check("C1", cfg, obs)
        res.append({"control": "live-redaction-left-in-progress-presented-as-final", "state": {k: s[k] for k in s if k != "later_revisions"},
                    "violations": v, "caught": any(x.startswith(("O4", "O5", "O6")) for x in v)})
        e.ledger.redact(spec["graph"], batch_size=500, max_batches=0)
    if group == "erase":
        cfg = POINTS["D1"]
        spec = prepare(ctl, "K3", cfg, "1")
        start = head(ctl)
        e = engine(ctl)
        e.erase_graph(spec["graph"])
        e.ledger.redact(spec["graph"], batch_size=500, max_batches=0)
        # seeded defect: writes into the erased graph outside the ledger (accepted on a non-strict ledger, F-C1307)
        e.create_node(spec["tag"] + "zombie", graph=spec["graph"])
        e.create_node(spec["tag"] + "zombie2", graph=spec["graph"])
        e.create_edge(spec["tag"] + "zombie", "R", spec["tag"] + "zombie2", graph=spec["graph"])
        ctl.conn.commit()
        s = graph_state(ctl, spec, spec["rec_lo"], spec["rec_hi"], start)
        obs = {"server_exited": True, "journal": {"units": [], "unit_classes": {}}, "lock_free_after_kill": True,
               "lock_free_after_retry": True, "state_after_kill": s, "outcome_after_kill": "full",
               "retry": {"removed": 0}, "state_after_retry": s, "verify_after_retry": verify(ctl)}
        v = check("D1", cfg, obs)
        res.append({"control": "live-erased-graph-with-a-bypass-write", "state": {k: s[k] for k in s if k != "later_revisions"},
                    "violations": v, "caught": any(x.startswith(("O5", "O6")) for x in v)})
        e.erase_graph(spec["graph"])
        ctl.conn.commit()
        res[-1]["verify_after_cleanup"] = verify(ctl)
    return res


# ----------------------------------------------------------------------------------------------- self-test of the oracle
def seeded(obs: dict, cfg: dict) -> dict:
    """Each seeded defect: (name, mutated observation). All must be flagged."""
    import copy
    out = {}

    def mut(name, f):
        o = copy.deepcopy(obs)
        f(o)
        out[name] = o
    g = cfg["group"]
    mut("server-alive", lambda o: o.update(server_exited=False))
    mut("journal-open-unit", lambda o: o["journal"]["unit_classes"].update(open=1))
    mut("journal-write-outside-transaction", lambda o: o["journal"]["unit_classes"].update({"outside-transaction": 1}))
    mut("lock-held", lambda o: o.update(lock_free_after_kill=False))
    mut("partial-after-kill", lambda o: o.update(outcome_after_kill="partial"))
    mut("verify-diverged", lambda o: o.update(verify_after_retry="diverged"))
    if cfg["expect"] != "either":
        other = {"nothing": "full", "full": "nothing", "complete": f"in-progress-{cfg.get('batch', 1)}"}.get(cfg["expect"], "complete")
        mut("outcome-contradicts-point", lambda o: o.update(outcome_after_kill=other))
    if g == "commit":
        mut("double-application", lambda o: o.update(outcome_after_retry="partial"))
        if obs.get("outcome_after_kill") == "full":
            mut("retry-other-answer", lambda o: o["retry"].update(revision_id="0" * 32, replayed=False))
        else:
            mut("retry-replayed-nothing", lambda o: o["retry"].update(replayed=True))
        mut("journal-committed-but-state-nothing", lambda o: (o.update(outcome_after_kill="nothing"), o["journal"]["units"].append(
            {"class": "committed", "net_nodes": 5, "ledger_rec_nodes": 0, "records": 5})))
    if g == "redact":
        mut("redaction-left-open", lambda o: o["state_after_retry"].update(marker=True))
        mut("two-redaction-revisions", lambda o: o["state_after_retry"].update(redaction_revisions_after_start=[1, 2]))
        mut("rerun-incomplete", lambda o: o["retry"].update(complete=False))
    if cfg.get("mode") == "lockheld":
        mut("refusal-missing", lambda o: o.update(client_lines=[x for x in o["client_lines"] if "error" not in x]))
    if g == "erase":
        mut("row-survives-erasure", lambda o: o["state_after_retry"].update(edge_rows=1))
        mut("records-changed", lambda o: o["state_after_retry"].update(target_records_content=0, target_records_tombstoned=0))
        mut("retry-count-wrong", lambda o: o["retry"].update(removed=12345))
    return out


def self_test(results: list) -> dict:
    """Negative controls over recorded observations: the checker must flag every seeded defect, and pass the real
    observation it was seeded from when that observation had no violation."""
    rep = {}
    for obs in results:
        if obs.get("baseline") or obs["point"] in rep:
            continue
        cfg = dict(POINTS[obs["point"]], rows=obs["spec"].get("rows"))
        base_ok = not check(obs["point"], cfg, obs)
        flagged, missed = [], []
        for name, o in seeded(obs, cfg).items():
            (flagged if check(obs["point"], cfg, o) else missed).append(name)
        rep[obs["point"]] = {"seeded": len(flagged) + len(missed), "flagged": flagged, "missed": missed,
                             "source_observation_passes": base_ok}
    return rep


def reevaluate(out: Path) -> int:
    """Re-judge every recorded trial with this file's checker: the journal classification is recomputed from the raw
    journal records kept per trial (journal-<point>-<trial>.jsonl.gz), then O1-O7 are applied. Observations are not
    changed; the verdicts are written to reevaluated.json."""
    import gzip
    rows, per = [], {}
    for f in sorted(out.glob("results-*.json")):
        doc = json.loads(f.read_text())
        for o in doc["trials"]:
            jf = out / f"journal-{o['point']}-{o['trial']}.jsonl.gz"
            if jf.exists():
                o["journal"] = journal_units([json.loads(x) for x in gzip.open(jf, "rt")])
            cfg = dict(POINTS[o["point"]], rows=o["spec"].get("rows"))
            if o["baseline"]:
                v = [] if o["outcome_after_kill"] in ("full", "complete") and o["verify_after_retry"] == "equal" else ["baseline"]
            elif o["event"] in (None, "client-finished-before-point"):
                v = [f"point not reached: {o['event']}"]
            else:
                v = check(o["point"], cfg, o)
            key = o["point"] + (" baseline" if o["baseline"] else "")
            s = per.setdefault(key, {"trials": 0, "violating": 0, "outcomes": {}, "events": {}, "journal": {}})
            s["trials"] += 1
            s["violating"] += bool(v)
            s["outcomes"][o["outcome_after_kill"]] = s["outcomes"].get(o["outcome_after_kill"], 0) + 1
            s["events"][o["event"]] = s["events"].get(o["event"], 0) + 1
            for k, n in o["journal"]["unit_classes"].items():
                s["journal"][k] = s["journal"].get(k, 0) + n
            rows.append({"point": o["point"], "trial": o["trial"], "baseline": o["baseline"], "event": o["event"],
                         "outcome_after_kill": o["outcome_after_kill"], "outcome_after_retry": o["outcome_after_retry"],
                         "retry": o["retry"], "verify_after_retry": o["verify_after_retry"],
                         "lock_free": [o["lock_free_after_kill"], o["lock_free_after_retry"]],
                         "seconds_kill_to_exit": o["seconds_kill_to_exit"], "journal": o["journal"]["unit_classes"],
                         "recorded_violations": o["violations"], "violations": v})
    controls = []
    for f in sorted(out.glob("results-*.json")):
        controls += [{k: c[k] for k in ("control", "caught", "violations")} for c in json.loads(f.read_text())["live_controls"]]
    doc = {"per_point": per, "live_controls": controls, "trials": rows}
    (out / "reevaluated.json").write_text(json.dumps(doc, indent=1, default=str))
    bad = [r for r in rows if r["violations"]]
    for k, s in sorted(per.items()):
        print(k, json.dumps(s))
    for c in controls:
        print("live control", c["control"], "caught" if c["caught"] else "MISSED")
    print(f"trials {len(rows)} (baselines {sum(r['baseline'] for r in rows)}); violating {len(bad)}: "
          f"{[(r['point'], r['trial'], r['violations']) for r in bad]}")
    return 0 if not bad and all(c["caught"] for c in controls) else 1


# ----------------------------------------------------------------------------------------------- main
def main() -> int:
    if "--client" in sys.argv:
        client_main(json.loads(sys.argv[sys.argv.index("--client") + 1]))
        return 0
    _imports()
    if "--reevaluate" in sys.argv:
        return reevaluate(Path(sys.argv[sys.argv.index("--reevaluate") + 1]))
    if "--self-test-oracle" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--self-test-oracle") + 1])
        results = []
        for f in sorted(out.glob("results-*.json")):
            results += json.loads(f.read_text())["trials"]
        rep = self_test(results)
        (out / "self-test.json").write_text(json.dumps(rep, indent=1))
        ok = all(not r["missed"] for r in rep.values()) and rep
        for p, r in sorted(rep.items()):
            print(p, f"seeded {r['seeded']} flagged {len(r['flagged'])} missed {r['missed']} source-passes {r['source_observation_passes']}")
        print("oracle self-test", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    global OUT_DIR
    OUT_DIR = out
    group = sys.argv[sys.argv.index("--group") + 1]
    trials = int(sys.argv[sys.argv.index("--trials") + 1]) if "--trials" in sys.argv else 3
    only = sys.argv[sys.argv.index("--points") + 1].split(",") if "--points" in sys.argv else GROUPS[group]
    from iris_conn import Conn, version
    ctl = Conn(NS)
    meta = {"engine": version(ctl), "namespace": NS, "group": group, "trials_per_point": trials,
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    print(json.dumps(meta), flush=True)
    reset(ctl)
    meta["verify_at_start"] = verify(ctl)
    res = []
    base_pt = GROUPS[group][0] if group != "commit" else "B1"
    if "--no-baseline" not in sys.argv:
        b = trial(ctl, base_pt, POINTS[base_pt], "base", baseline=True)
        res.append(b)
        print(json.dumps({k: b[k] for k in ("point", "baseline", "event", "outcome_after_kill", "verify_after_retry", "violations")}), flush=True)
    for pt in only:
        for i in range(trials):
            o = trial(ctl, pt, POINTS[pt], str(i + 1))
            res.append(o)
            print(json.dumps({k: o[k] for k in ("point", "trial", "event", "seconds_kill_to_exit", "outcome_after_kill",
                                                "retry", "outcome_after_retry", "verify_after_retry", "violations")}
                             | {"journal": o["journal"]["unit_classes"]}), flush=True)
    ctl_res = live_controls(ctl, group) if "--no-live-controls" not in sys.argv else []
    for x in ctl_res:
        print(json.dumps({k: x[k] for k in ("control", "caught", "violations")}), flush=True)
    meta["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    meta["verify_at_end"] = verify(ctl)
    summary = {}
    for o in res:
        k = o["point"] + (" baseline" if o["baseline"] else "")
        s = summary.setdefault(k, {"trials": 0, "violating": 0, "outcomes": {}, "events": {}})
        s["trials"] += 1
        s["violating"] += bool(o["violations"])
        s["outcomes"][o["outcome_after_kill"]] = s["outcomes"].get(o["outcome_after_kill"], 0) + 1
        s["events"][o["event"]] = s["events"].get(o["event"], 0) + 1
    doc = {"meta": meta, "summary": summary, "live_controls": ctl_res, "trials": res}
    (out / f"results-{group}.json").write_text(json.dumps(doc, indent=1, default=str))
    print(json.dumps({"summary": summary, "live_controls_caught": [x["caught"] for x in ctl_res]}), flush=True)
    ctl.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
