"""Iteration 60 repair 2: native cases for the counter row held by a caller's transaction while the head is free
(validation case V3 and its neighbours), the in-process counter paths (strict guard, verify), and bug-led-013's
re-enable clause.

Local fixture only (local-runtime/runtime.py: ivg-uplift-next-20261115, 127.0.0.1:35975, identity-checked on every
connection; executable product files byte-checked against 3eaa79cf). Writes only in this repair's own namespace I60SA,
created additively from %SYS with SQL CREATE DATABASE, deployed with initialize_schema() from the unchanged pin, ledger
enabled with defaults; plus one application table SQLUser.i60s_app of its own there. IDs start with i60s_. The X lock is
a Native API lock on I60SA's own ^IVG.Ledger("head"), always released. No erase, reset, kill or drop; nothing written
to USER, I60L*, I60R*, R60* or V60L. Predictions: ../PREDICTIONS.md (committed before any run).

Connections: A = the caller under test, B = another writer (autocommit, hook events recorded), X = the head-lock
holder, R = a reader of the product's own GraphLedger.stats() (a separate server process).

Usage: python -B i60s_probe.py <section ...>   sections: setup s1 s2 s3 s3z s4 s6 s6n s5 s5r bindns
       -> observed-<stamp>-<sections>.json beside this file
"""
import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_STATE = Path("/Users/ziniuw/Desktop/projects/G5-benchmark/results/local/iris-test-obligations-20261117")
if (RUN_STATE / "STOP").exists():
    print("STOP file present; not running")
    sys.exit(3)
sys.path.insert(0, str(HERE.parents[2] / "local-runtime"))
import runtime as rt  # noqa: E402  local fixture runtime (identity-checked connect)

from iris_vector_graph.ledger import Changeset  # noqa: E402
from iris_vector_graph.ledger import errors as LE  # noqa: E402

NS = "I60SA"
OBS = {"fixture": rt.FIXTURE, "product": rt.PRODUCT, "runtime_file": rt.__file__, "namespace": NS, "identity": []}
CNT = ["commits_ok", "replays_idem", "rej_stale_head", "rej_unknown_head", "rej_idem_conflict", "rej_failed_op",
       "rej_strict_block", "rej_size_limit", "rej_disabled", "rej_lock_timeout"]


def stamp():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def exc(e):
    d = {"class": type(e).__name__, "module": type(e).__module__, "msg": str(e)[:300]}
    for a in ("op_index", "current_head", "limit"):
        if hasattr(e, a):
            d[a] = getattr(e, a)
    return d


def connect(ns=NS):
    c = rt.connect(ns)  # raises on identity mismatch
    ok, host = rt.identity(c)
    OBS["identity"].append({"ns": ns, "ok": ok, "host": host, "t": stamp()})
    assert ok
    return c


def open_ns(hook=None):
    c = connect()
    e = rt.engine(c, NS)
    if hook is not None:
        e.ledger.register_metrics_hook(lambda d: hook.append(d["outcome"]))
    return c, e


class Reader:
    """R: the product's own counter reader (GraphLedger.stats) on a connection of its own."""

    def __init__(self):
        self.c, self.e = open_ns()

    def counters(self):
        st = self.e.ledger.stats()
        rej = dict(st.rejections)
        out = {k: rej.get(k, 0) for k in CNT}
        out["commits_ok"], out["replays_idem"] = st.commits_ok, st.replays_idem
        out["last_verify_result"] = st.last_verify_result
        return out

    def close(self):
        self.c.close()


def delta(a, b):
    return {k: b[k] - a[k] for k in CNT if b[k] != a[k]}


def tlevel(c):
    cur = c.cursor()
    cur.execute("SELECT $TLEVEL")
    v = int(cur.fetchone()[0])
    cur.close()
    return v


def node_rows(c, nid):
    cur = c.cursor()
    cur.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", [nid])
    n = int(cur.fetchone()[0])
    cur.close()
    return n


def timed_commit(L, cs):
    t = time.time()
    try:
        r = L.commit(cs)
        out = {"seq": r.revision.seq, "parent": r.revision.parent_id}
    except Exception as ex:  # noqa: BLE001
        out = exc(ex)
    out["wait_s"] = round(time.time() - t, 1)
    return out


def node_cs(nid, actor):
    cs = Changeset(actor=actor, actor_type="agent")
    cs.upsert_node(nid)
    return cs


# ------------------------------------------------------------------------------------------------------- sections
def setup():
    o = OBS.setdefault("setup", {})
    c = connect("%SYS")
    cur = c.cursor()
    cur.execute("SELECT Name FROM Config.Namespaces WHERE Name = ?", [NS])
    existed = cur.fetchone() is not None
    o["existed"] = existed
    if not existed:
        cur.execute(f"CREATE DATABASE {NS}")
    c.close()
    cn, e = open_ns()
    st = e.initialize_schema()
    o["init"] = sorted(st.get("tables_created", [])) if isinstance(st, dict) else str(st)[:200]
    if e.ledger.meta().get("state") == "never-enabled":
        info = e.ledger.enable()
        o["enable"] = {"seq": info.seq, "kind": info.kind}
    o["meta"] = e.ledger.meta()
    cur = cn.cursor()
    try:
        cur.execute("CREATE TABLE SQLUser.i60s_app (k VARCHAR(64), v VARCHAR(64))")
        o["app_table"] = "created"
    except Exception as ex:  # noqa: BLE001
        o["app_table"] = exc(ex)
    cur.close()
    cn.close()


def held_row_case(label, caller_txn):
    """S1 (caller_txn=True: validation V3) and S2 (caller_txn=False: its neighbour)."""
    import iris
    o = OBS.setdefault(label, {})
    s = stamp().lower()
    R = Reader()
    evB = []
    cB, eB = open_ns(evB)
    LB = eB.ledger
    evA = []
    cA, eA = open_ns(evA)
    cX = connect()
    nat = iris.createIRIS(cX)
    o["t0"] = R.counters()
    h0 = LB.head()
    o["head0"] = h0.seq
    locked = False
    if caller_txn:
        cA.setAutoCommit(False)
    csB = node_cs(f"i60s_{label}b{s}", "i60sB")
    try:
        nat.lock("", 2, "^IVG.Ledger", "head")
        locked = True
        o["X_lock"] = "acquired"
        o["A"] = timed_commit(eA.ledger, node_cs(f"i60s_{label}a{s}", "i60sA"))
        o["A_events"] = list(evA)
        o["A_tlevel"] = tlevel(cA)
        o["t1_after_A_refused"] = R.counters()
        nat.unlock("", "^IVG.Ledger", "head")
        locked = False
        o["X_unlock"] = "released"
        o["B"] = timed_commit(LB, csB)
        o["B_events"] = list(evB)
        o["t2_after_B"] = R.counters()
        o["head_after_B"] = LB.head().seq
        o["B_node_rows"] = node_rows(cB, f"i60s_{label}b{s}")
    finally:
        if locked:
            try:
                nat.unlock("", "^IVG.Ledger", "head")
            except Exception as ex:  # noqa: BLE001
                o["X_unlock_finally"] = exc(ex)
        if caller_txn:
            cA.rollback()
            cA.setAutoCommit(True)
    o["t3_after_A_end"] = R.counters()
    if "seq" not in o.get("B", {}):
        o["B_retry"] = timed_commit(LB, csB)
        o["B_retry"]["seq_is_next"] = o["B_retry"].get("seq") == h0.seq + 1
        o["B_retry"]["parent_is_prior_head"] = o["B_retry"].get("parent") == h0.revision_id
        o["t4_after_B_retry"] = R.counters()
    o["delta_A_refused"] = delta(o["t0"], o["t1_after_A_refused"])
    o["delta_after_B"] = delta(o["t0"], o["t2_after_B"])
    o["delta_after_A_end"] = delta(o["t0"], o["t3_after_A_end"])
    if "t4_after_B_retry" in o:
        o["delta_after_B_retry"] = delta(o["t0"], o["t4_after_B_retry"])
    cX.close(); cA.close(); cB.close(); R.close()


def in_process_case(label, action, autocommit_off, earlier_write, strict):
    """S3/S3z/S4 (action 'direct_write': the strict guard refuses create_node) and S6/S6n (action 'verify')."""
    o = OBS.setdefault(label, {})
    s = stamp().lower()
    R = Reader()
    evB = []
    cB, eB = open_ns(evB)
    LB = eB.ledger
    LB.set_strict(strict)
    o["strict"] = LB.meta().get("strict")
    cA, eA = open_ns()  # opened after set_strict: its guard has no cached state
    o["t0"] = R.counters()
    h0 = LB.head()
    csB = node_cs(f"i60s_{label}b{s}", "i60sB")
    if autocommit_off:
        cA.setAutoCommit(False)
    try:
        if earlier_write:
            cur = cA.cursor()
            cur.execute("INSERT INTO SQLUser.i60s_app (k, v) VALUES (?, ?)", [f"i60s_{label}{s}", "app"])
            cur.close()
        o["A_tlevel_before"] = tlevel(cA)
        t = time.time()
        try:
            if action == "direct_write":
                o["A"] = {"returned": eA.create_node(f"i60s_{label}a{s}")}
            else:
                o["A"] = {"verify": eA.ledger.verify().result}
        except Exception as ex:  # noqa: BLE001
            o["A"] = exc(ex)
        o["A"]["wait_s"] = round(time.time() - t, 1)
        o["A_tlevel_after"] = tlevel(cA)
        o["t1_A_open"] = R.counters()
        o["B"] = timed_commit(LB, csB)
        o["B_events"] = list(evB)
        o["B_node_rows_A_open"] = node_rows(cB, f"i60s_{label}b{s}")
        o["t2_after_B"] = R.counters()
    finally:
        if autocommit_off:
            cA.rollback()
            cA.setAutoCommit(True)
    o["t3_after_A_end"] = R.counters()
    if "seq" not in o.get("B", {}):
        o["B_retry"] = timed_commit(LB, csB)
        o["B_retry"]["seq_is_next"] = o["B_retry"].get("seq") == h0.seq + 1
    o["t4"] = R.counters()
    o["delta_A_open"] = delta(o["t0"], o["t1_A_open"])
    o["delta_after_A_end"] = delta(o["t0"], o["t3_after_A_end"])
    if strict:
        LB.set_strict(False)
        o["strict_after"] = LB.meta().get("strict")
    cA.close(); cB.close(); R.close()


def s5():
    """bug-led-013's re-enable clause: disable()/enable() with a committed text-"true" temporal qualifier."""
    o = OBS.setdefault("s5", {})
    c, e = open_ns()
    L = e.ledger
    p = f"i60s_{stamp().lower()}_"
    o["prefix"] = p

    def vfy():
        r = L.verify()
        mine = [[d.entity_kind, d.entity_id, d.attr, d.before, d.after] for d in r.differences if p in str(d.entity_id)]
        return {"result": r.result, "classification": r.classification, "mine": mine, "all": len(r.differences)}
    cs = Changeset(actor="i60s", actor_type="agent")
    cs.upsert_node(p + "ta"); cs.upsert_node(p + "tb"); cs.upsert_node(p + "ya"); cs.upsert_node(p + "yb")
    cs.create_relationship(p + "ta", "I60SREL", p + "tb", qualifiers={"temporal": "true"})
    cs.create_relationship(p + "ya", "I60SREL", p + "yb", qualifiers={"temporal": "yes"})
    o["commit_seq"] = L.commit(cs).revision.seq
    o["verify_0"] = vfy()
    for i in (1, 2):
        h = L.head().seq
        L.disable()
        o[f"cycle{i}.state_disabled"] = L.meta().get("state")
        info = L.enable()
        o[f"cycle{i}.enable"] = {"seq": info.seq, "kind": info.kind, "head_moved": L.head().seq - h,
                                 "state": L.meta().get("state")}
        if info.kind == "adoption":
            recs = L.get_revision(info.revision_id).records
            o[f"cycle{i}.adoption_records_mine"] = [[x.op, x.entity_id, x.attr, x.new] for x in recs
                                                    if p in str(x.entity_id) or p in str(x.new)]
        o[f"cycle{i}.verify_after"] = vfy()
    c.close()


def bindns():
    """The ledger_client binding's namespaces for this repair (clean, so earlier probe state cannot leak into it):
    I60SB enabled with defaults plus the application table SQLUser.i60s_app, I60SC enabled with max_ops 2, I60SE
    deployed and never enabled. Created additively from %SYS like I60SA."""
    o = OBS.setdefault("bindns", {})
    for ns, enable in (("I60SB", {}), ("I60SC", {"max_ops": 2}), ("I60SE", None)):
        r = o.setdefault(ns, {})
        c = connect("%SYS")
        cur = c.cursor()
        cur.execute("SELECT Name FROM Config.Namespaces WHERE Name = ?", [ns])
        r["existed"] = cur.fetchone() is not None
        if not r["existed"]:
            cur.execute(f"CREATE DATABASE {ns}")
        c.close()
        cn = connect(ns)
        e = rt.engine(cn, ns)
        st = e.initialize_schema()
        r["init_ok"] = isinstance(st, dict)
        if enable is not None and e.ledger.meta().get("state") == "never-enabled":
            info = e.ledger.enable(**enable)
            r["enable"] = {"seq": info.seq, "kind": info.kind}
        r["meta"] = e.ledger.meta()
        if ns == "I60SB":
            cur = cn.cursor()
            try:
                cur.execute("CREATE TABLE SQLUser.i60s_app (k VARCHAR(64), v VARCHAR(64))")
                r["app_table"] = "created"
            except Exception as ex:  # noqa: BLE001
                r["app_table"] = exc(ex)
            cur.close()
        cn.close()


def s5r():
    """Read-only follow-up to s5 (whose record filter matched only records naming the prefix): every record of every
    adoption revision in I60SA, so the set_qual record of the text-"true" relationship is visible."""
    o = OBS.setdefault("s5r", {})
    c, e = open_ns()
    L = e.ledger
    for r in L.history(limit=1000).revisions:
        if r.kind == "adoption":
            o[f"seq{r.seq}"] = [[x.op, x.entity_id, x.attr, x.new] for x in L.get_revision(r.revision_id).records]
    c.close()


SECTIONS = {
    "setup": setup,
    "s5r": s5r,
    "bindns": bindns,
    "s1": lambda: held_row_case("s1", True),
    "s2": lambda: held_row_case("s2", False),
    "s3": lambda: in_process_case("s3", "direct_write", True, True, True),
    "s3z": lambda: in_process_case("s3z", "direct_write", True, False, True),
    "s4": lambda: in_process_case("s4", "direct_write", False, False, True),
    "s6": lambda: in_process_case("s6", "verify", True, True, False),
    "s6n": lambda: in_process_case("s6n", "verify", True, False, False),
    "s5": s5,
}

if __name__ == "__main__":
    names = sys.argv[1:] or list(SECTIONS)
    OBS["started"] = stamp()
    OBS["ok"], OBS["errors"] = [], {}
    OBS["hashes_checked"] = len(rt.hashes())
    for n in names:
        if (RUN_STATE / "STOP").exists():
            OBS["errors"][n] = "STOP file present; section not run"
            continue
        try:
            SECTIONS[n]()
            OBS["ok"].append(n)
        except Exception:  # noqa: BLE001
            OBS["errors"][n] = traceback.format_exc()[-3000:]
    OBS["finished"] = stamp()
    out = HERE / f"observed-{OBS['started']}-{'-'.join(names)}.json"
    out.write_text(json.dumps(OBS, indent=1, default=str) + "\n")
    print(out)
    print(json.dumps({"ok": OBS["ok"], "errors": list(OBS["errors"])}))
