"""ledger_client native binding: the actual product (Python client + ObjectScript server) on IRIS vs the model.

Run through the local runtime wrapper, which installs the fixture module as `runtime`:
    python -B .g5/uplift/consolidated/local-runtime/run_binding.py .g5/Verus_verification/models/ledger_client/binding.py
`runtime` must provide NAME, PORT, FIXTURE, connect(namespace) (identity-checked) and engine(c, namespace). Writes only in
task-owned namespaces, by default the iteration-60 repair's I60RA (enabled, max_ops 50000), I60RC (enabled, max_ops 2) and
I60RE (never enabled; never enabled here); override with LEDGER_CLIENT_NS_A / _C / _E (the iteration-60 run used I60LA,
I60LC, I60LE). IDs and keys carry a per-run stamp, so repeated runs do not collide. The repair cases add counter deltas
read from another connection while a caller's transaction is open (B8), an uncounted nested refusal (B8b), the strict
guard's count call (B8c), a redaction-blocked commit and the revision readers during an unfinished redaction of this
run's own prefix (B18, B19; redaction is otherwise an excluded area), and revision-row field limits (B20).

Expected outcomes come from `Ref`, an UNVERIFIED hand transcription of ledger_client.rs's spec functions (server,
client_commit, from_commit_error, bump, txn_commit/txn_rollback/txn_end, seq_read, diff_read, head_read, enable,
set_strict, update_allowed, chunks/join, stored_source), fed with the namespace state observed just before each case and
with the apply outcome each case is built to have (the ledger_apply premise). Observations are the real
CommitResult / exception class and attributes / ledger_stats counters / metrics-hook events / readers / SQL refusals.
Detection: each named mutation of the reference (the same edits as the model's controls) must disagree with at least
one observation, and a changed observation must be caught.
"""
import copy
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import binding_common as bc  # noqa: E402

PIN_DIR = bc.import_pin()
import runtime as rt  # noqa: E402  (installed by local-runtime/run_binding.py)
from iris_vector_graph.ledger import Changeset  # noqa: E402
from iris_vector_graph.ledger import errors as LE  # noqa: E402

CNT = {"ok": "commits_ok", "replays": "replays_idem", "stale": "rej_stale_head", "unknown": "rej_unknown_head",
       "conflict": "rej_idem_conflict", "failed": "rej_failed_op", "size": "rej_size_limit", "disabled": "rej_disabled",
       "lock": "rej_lock_timeout", "strict_block": "rej_strict_block"}
EXC = {"NotEnabled": "LedgerNotEnabledError", "Disabled": "LedgerDisabledError", "Empty": "EmptyChangesetError",
       "TooLarge": "ChangesetTooLargeError", "Stale": "StaleHeadError", "UnknownRev": "UnknownRevisionError",
       "Conflict": "IdempotencyConflictError", "IdemRedacted": "IdempotencyRedactedError", "OpError": "ChangesetOperationError",
       "NodeNotFound": "NodeNotFoundError", "LockTimeout": "LedgerLockTimeoutError", "Base": "LedgerError",
       "TxnOpen": "LedgerTransactionOpenError", "Inconsistent": "LedgerInconsistencyError",
       "RedactionInProgress": "RedactionInProgressError"}
WIRE = {"NotEnabled": "not_enabled", "Disabled": "disabled", "Empty": "empty", "TooLarge": "too_large", "StaleHead": "stale_head",
        "UnknownHead": "unknown_head", "Conflict": "idempotency_conflict", "IdemRedacted": "idempotency_redacted",
        "FailedOp": "failed_op", "LockTimeout": "lock_timeout", "Inconsistent": "inconsistent",
        "RedactionInProgress": "redaction_in_progress"}
LIMITS = {"message": 4000, "source": 4000, "actor": 256, "actor_type": 32, "correlation": 256, "key": 256}


# ---------------------------------------------------------------------------------------------- reference (model)
class Ref:
    """Hand transcription of ledger_client.rs. `mut` names one control-equivalent mutation (or None)."""

    def __init__(self, mut=None):
        self.mut = mut

    def scope(self, c):
        ops = () if self.mut == "ops-not-fingerprinted" else tuple(c["ops"])
        return (c["actor"], c["actor_type"], ops)

    def fp(self, c):
        return (self.scope(c), c.get("message")) if self.mut == "message-fingerprinted" else self.scope(c)

    def bump(self, cnt, code):
        k = {"Disabled": "disabled", "Conflict": "conflict", "IdemRedacted": "conflict", "UnknownHead": "unknown",
             "StaleHead": "stale", "TooLarge": "size", "FailedOp": "failed", "LockTimeout": "lock"}.get(code)
        if self.mut == "never-counted-as-disabled" and code == "NotEnabled":
            k = "disabled"
        cnt = dict(cnt)
        if k:
            cnt[k] += 1
        return cnt

    def stats_free(self, s, p):
        return s.get("stats_holder") is None or s.get("stats_holder") == p or self.mut == "bump-ignores-held-row"

    def fits(self, c):
        if self.mut == "field-limits-unchecked":
            return True
        return all(c["lens"][k] <= LIMITS[k] for k in LIMITS)

    def server(self, s, c, p, a):
        s = copy.deepcopy(s)
        hid = s["id_of"].get(s["head"])

        def refuse(code, head=None, **kw):
            if self.stats_free(s, p):
                s["cnt"] = self.bump(s["cnt"], code)
            return s, dict(kind="Err", code=code, head=head, **kw)
        if s["holder"] is not None and s["holder"] != p:
            return refuse("LockTimeout")
        if s["state"] == "Never":
            if self.mut == "never-counted-as-disabled":
                return refuse("Disabled")
            return s, dict(kind="Err", code="NotEnabled", head=None)
        if s["state"] == "Disabled":
            return refuse("Disabled")
        k, e = c.get("key"), c.get("expected")
        stale = e is not None and e in s["seq_of"] and e != hid
        if self.mut == "expected-head-before-idempotency" and stale:
            return refuse("StaleHead", hid)
        if self.mut == "field-limits-before-key" and not self.fits(c):
            return s, dict(kind="Err", code="Inconsistent", head=hid)
        if k is not None and k in s["idem"]:
            if self.fp(s["idem"][k][1]) == self.fp(c):
                if not self.stats_free(s, p):
                    pass
                elif self.mut == "replay-counted-as-commit":
                    s["cnt"]["ok"] += 1
                else:
                    s["cnt"]["replays"] += 1
                return s, dict(kind="Ok", seq=s["idem"][k][0], replayed=True, stmts=False)
            return refuse("Conflict", hid)
        if e is not None and e not in s["seq_of"] and self.mut != "unknown-as-stale":
            return refuse("UnknownHead", hid)
        if e is not None and e != hid:
            if self.mut == "key-bound-on-refusal" and k is not None:
                s["idem"][k] = (s["head"], c)
            return refuse("StaleHead", e if self.mut == "stale-names-expected" else hid)
        if len(c["ops"]) == 0:
            return s, dict(kind="Err", code="Empty", head=hid)
        if (len(c["ops"]) >= s["max_ops"]) if self.mut == "size-limit-exclusive" else (len(c["ops"]) > s["max_ops"]):
            return refuse("TooLarge", limit=s["max_ops"])
        if not a["ok"]:
            return refuse("FailedOp", op_index=a["index"], missing=a.get("missing"))
        if s.get("redacting") and a.get("blocked"):
            if self.mut == "redaction-block-counted":
                return refuse("FailedOp")
            return s, dict(kind="Err", code="RedactionInProgress", head=None)
        if not self.fits(c):
            return s, dict(kind="Err", code="Inconsistent", head=hid)
        if not self.stats_free(s, p):
            return s, dict(kind="Err", code="Inconsistent", head=hid)
        n = s["head"] + 1
        s["head"] = n
        s["id_of"][n] = "<fresh>"
        s["seq_of"]["<fresh>"] = n
        s["parent"][n] = hid
        if k is not None:
            s["idem"][k] = (n, c)
        s["cnt"]["ok"] += 1
        return s, dict(kind="Ok", seq=n, replayed=False, stmts=True)

    def exc(self, w):
        code = w["code"]
        if code == "FailedOp":
            i = -1 if (w.get("op_index") is None or self.mut == "op-index-lost") else w["op_index"]
            if w.get("missing") is not None and self.mut != "no-node-narrowing":
                return ("NodeNotFound", {"op_index": i, "missing_node": w["missing"]})
            return ("OpError", {"op_index": i})
        if code == "StaleHead":
            return ("Stale", {"current_head": w["head"]})
        if code == "TooLarge":
            return ("TooLarge", {"limit": w.get("limit")})
        return ({"NotEnabled": "NotEnabled", "Disabled": "Disabled", "Empty": "Empty", "UnknownHead": "UnknownRev",
                 "Conflict": "Conflict", "IdemRedacted": "IdemRedacted", "LockTimeout": "LockTimeout",
                 "Inconsistent": "Inconsistent", "RedactionInProgress": "RedactionInProgress"}.get(code, "Base"), {})

    def client(self, s, c, p, a):
        if len(c["ops"]) == 0 and self.mut != "no-client-validate":
            return s, ("Raise", "Empty", {}), []
        if c.get("bad_ref") is not None:
            ev = ["failed_op"] if self.mut == "event-on-client-refusal" else []
            return s, ("Raise", "OpError", {"op_index": c["bad_ref"]}), ev
        s2, w = self.server(s, c, p, a)
        if w["kind"] == "Ok":
            return s2, ("Res", w["seq"], w["replayed"], w["stmts"]), ["replayed" if w["replayed"] else "success"]
        name, attrs = self.exc(w)
        return s2, ("Raise", name, attrs), [WIRE[w["code"]]]

    def txn_commit(self, s, c, p, a):
        s2, py, ev = self.client(s, c, p, a)
        calls = len(c["ops"]) > 0 and c.get("bad_ref") is None
        foreign = s["holder"] is not None and s["holder"] != p
        if calls and not foreign and self.mut != "lock-released-inside-transaction":
            s2 = dict(s2, holder=p)
        took_row = calls if self.mut == "uncounted-refusal-holds-row" else (s2["cnt"] != s["cnt"])
        if took_row and self.mut != "stats-row-not-held":
            if s.get("stats_holder") != p:
                s2 = dict(s2, stats_base=dict(s["cnt"]))
            s2 = dict(s2, stats_holder=p)
        return s2, py, ev

    def txn_rollback(self, before, cur, p):
        out = copy.deepcopy(before)
        out["holder"] = None
        out["stats_holder"] = None
        out["cnt"] = dict(cur["stats_base"]) if cur.get("stats_holder") == p else dict(cur["cnt"])
        if self.mut == "idem-not-journaled":
            out["idem"] = copy.deepcopy(cur["idem"])
        return out

    def count_strict(self, s, q):
        s = copy.deepcopy(s)
        if self.stats_free(s, q):
            s["cnt"]["strict_block"] += 1
        return s

    def seq_read(self, s, rid):
        if self.mut == "lookup-before-redaction-check" and rid not in s["seq_of"]:
            return ("Raise", "UnknownRev")
        if s.get("redacting"):
            return ("Raise", "RedactionInProgress")
        if rid in s["seq_of"]:
            return ("At", s["seq_of"][rid])
        return ("At", 0) if self.mut == "unknown-id-reads-genesis" else ("Raise", "UnknownRev")

    def head_read(self, s):
        bad = (s["state"] != "Enabled") if self.mut == "head-refused-while-disabled" else (s["state"] == "Never")
        return ("Raise", "NotEnabled") if bad else ("At", s["head"])

    def reenable_strict(self, s, strict):
        return strict if s["state"] == "Disabled" else s["strict"]

    def enable_on_enabled_strict(self, s, strict):
        return strict if self.mut == "enable-on-enabled-sets-strict" else s["strict"]

    def update_allowed(self, ctx, rr, other, emptied):
        return ctx and rr and not other and (True if self.mut == "update-without-emptying" else emptied)

    def chunks(self, p, n):
        out, i = [], 0
        while i < len(p):
            out.append(p[i:i + (n - 1 if self.mut == "chunk-off-by-one" else n)])
            i += n
        return out

    def stored_source(self, src):
        if isinstance(src, dict):
            return "object"
        return "text" if (self.mut == "text-source-kept" and isinstance(src, str)) else None


MUTATIONS = ["message-fingerprinted", "ops-not-fingerprinted", "expected-head-before-idempotency", "replay-counted-as-commit",
             "key-bound-on-refusal", "stale-names-expected", "unknown-as-stale", "never-counted-as-disabled", "no-client-validate",
             "size-limit-exclusive", "no-node-narrowing", "op-index-lost", "lock-released-inside-transaction", "idem-not-journaled",
             "unknown-id-reads-genesis", "head-refused-while-disabled", "enable-on-enabled-sets-strict", "update-without-emptying",
             "chunk-off-by-one", "text-source-kept", "event-on-client-refusal", "stats-row-not-held", "bump-ignores-held-row",
             "uncounted-refusal-holds-row", "redaction-block-counted", "field-limits-unchecked", "field-limits-before-key",
             "lookup-before-redaction-check"]
# The redaction exception of RejectUpdate needs %IVGLedgerRedaction set in the SQL server process and a redactedRev entry;
# the binding does not forge redaction internals, so that branch is an inspected source binding only.
NOT_NATIVE = {"update-without-emptying": "redaction-context UPDATE not forged (inspected only)"}


# ---------------------------------------------------------------------------------------------- product observation
class NS:
    """One namespace's engine plus the observed model state used as the reference's pre-state."""

    def __init__(self, ns):
        self.ns = ns
        self.c = rt.connect(ns)
        self.e = rt.engine(self.c, ns)
        self.L = self.e.ledger
        self.events = []
        self.L.register_metrics_hook(lambda d: self.events.append(d["outcome"]))
        self.idem = {}   # key -> (seq, reference changeset) for keys this run bound (fresh keys only)

    def counters(self):
        st = self.L.stats()
        rej = dict(st.rejections)
        return {k: (st.commits_ok if col == "commits_ok" else st.replays_idem if col == "replays_idem" else rej.get(col, 0))
                for k, col in CNT.items()}

    def state(self):
        m = self.L.meta()
        state = {"never-enabled": "Never", "enabled": "Enabled", "disabled": "Disabled"}[m["state"]]
        head = int(m.get("head_seq") or 0)
        ids = {}
        if state != "Never":
            for r in self.L.history(limit=100000).revisions:
                ids[r.revision_id] = r.seq
        redacting = state != "Never" and self.L.redaction_in_progress() is not None
        return {"state": state, "strict": bool(m.get("strict")), "max_ops": int(m["max_ops"]), "head": head,
                "id_of": {v: k for k, v in ids.items()}, "seq_of": ids, "parent": {}, "idem": dict(self.idem),
                "holder": None, "stats_holder": None, "stats_base": None, "redacting": redacting, "cnt": self.counters()}

    def close(self):
        self.c.close()


def cs_of(spec, stamp):
    """Build the real Changeset and the reference changeset from one case spec."""
    c = Changeset(actor=spec.get("actor", "bind"), actor_type=spec.get("actor_type", "agent"), message=spec.get("message"),
                  correlation_id=spec.get("correlation"), idempotency_key=spec.get("key"), expected_head=spec.get("expected"),
                  source=spec.get("source"))
    for op in spec["ops"]:
        getattr(c, op[0])(*op[1:])
    if spec.get("bad_ref") is not None:
        c.ops.append({"op": "delete_rel", "ref": {"op_ref": spec["bad_ref"] + 5}})
    src = c.source if isinstance(c.source, dict) else None   # a text source is stored empty (bug-led-012)
    lens = {"message": len(c.message or ""), "source": len(json.dumps(src, sort_keys=True, separators=(",", ":"))) if src else 0,
            "actor": len(c.actor or ""), "actor_type": len(c.actor_type or ""), "correlation": len(c.correlation_id or ""),
            "key": len(c.idempotency_key or "")}
    ref = {"actor": c.actor, "actor_type": c.actor_type, "message": c.message, "key": c.idempotency_key,
           "expected": c.expected_head, "ops": [json.dumps(o, sort_keys=True) for o in c.ops],
           "bad_ref": (len(c.ops) - 1) if spec.get("bad_ref") is not None else None, "lens": lens}
    return c, ref


def observe_commit(n, c, txn=False):
    ev0 = len(n.events)
    rel_ops = sum(op["op"] in ("create_rel", "upsert_rel") for op in c.ops)
    try:
        r = n.L.commit(c)
        # "stmts": the result carries a statement ID for every relationship operation (empty is complete without any)
        py = ("Res", r.revision.seq, r.replayed, len(r.stmt_ids) == rel_ops)
        rev = r.revision
    except LE.LedgerError as e:
        name = {v: k for k, v in EXC.items()}.get(type(e).__name__, type(e).__name__)
        attrs = {}
        if name in ("OpError", "NodeNotFound"):
            attrs["op_index"] = e.op_index
        if name == "NodeNotFound":
            attrs["missing_node"] = e.missing_node
        if name == "Stale":
            attrs["current_head"] = e.current_head
        if name == "TooLarge":
            attrs["limit"] = e.limit
        py, rev = ("Raise", name, attrs), None
    return py, n.events[ev0:], rev


def norm_ref(py, s_pre, s_post_obs_ids):
    """Reference Res seq is relative to observed state; fresh IDs are '<fresh>' in the reference."""
    return py


# ---------------------------------------------------------------------------------------------- cases
def run(ref, live, stamp, cases_out):
    """Evaluate every case for one reference (the live observations are taken once, by the caller)."""
    mism = []
    for case in live:
        exp = case["expect_fn"](ref)
        if exp != case["observed"]:
            mism.append({"case": case["name"], "expected": exp, "observed": case["observed"]})
    return mism


NS_A = os.environ.get("LEDGER_CLIENT_NS_A", "I60RA")
NS_C = os.environ.get("LEDGER_CLIENT_NS_C", "I60RC")
NS_E = os.environ.get("LEDGER_CLIENT_NS_E", "I60RE")


def cdelta(a, b):
    return {k: b[k] - a[k] for k in a if b[k] != a[k]}


def main():
    stamp = time.strftime("%H%M%S", time.gmtime())
    A, C, E = NS(NS_A), NS(NS_C), NS(NS_E)
    live = []
    waits = {}

    def add(name, observed, expect_fn):
        live.append({"name": name, "observed": observed, "expect_fn": expect_fn})

    def commit_case(name, n, spec, apply, p=1, pre=None):
        c, rc = cs_of(spec, stamp)
        s0 = pre if pre is not None else n.state()
        c0 = n.counters()
        py, ev, rev = observe_commit(n, c)
        c1 = n.counters()
        delta = {k: c1[k] - c0[k] for k in c0}
        if py[0] == "Res" and not py[2] and spec.get("key"):
            n.idem[spec["key"]] = (py[1], rc)

        def expect(ref, s0=s0, rc=rc, apply=apply, p=p):
            s1, epy, eev = ref.client(s0, rc, p, apply)
            if epy[0] == "Raise" and epy[1] == "Stale":
                epy = ("Raise", "Stale", {"current_head": epy[2]["current_head"]})
            return {"py": epy, "events": eev, "delta": {k: s1["cnt"][k] - s0["cnt"][k] for k in s0["cnt"]},
                    "head_moved": s1["head"] - s0["head"]}
        h1 = n.L.head().seq if n.L.meta()["state"] != "never-enabled" else 0
        obs = {"py": py, "events": ev, "delta": delta, "head_moved": h1 - s0["head"]}
        add(name, obs, expect)
        return py, rev, s0, rc, obs

    ok = {"ok": True, "index": 0}
    # B1 retry with new metadata replays (first commit returns statement IDs, the replay none)
    k1 = f"i60b-{stamp}-k1"
    base = {"key": k1, "ops": [("create_node", f"i60b_{stamp}_a"), ("create_node", f"i60b_{stamp}_b")]}
    first_ops = base["ops"] + [("create_relationship", f"i60b_{stamp}_a", "R", f"i60b_{stamp}_b")]
    commit_case("B1.first", A, dict(base, ops=first_ops, message="m1", correlation="c1"), ok)
    stale_id = A.L.history(limit=1).revisions[0].revision_id  # genesis: a known, non-head revision
    commit_case("B1.retry_new_metadata_stale_head", A, dict(base, ops=first_ops, message="m2", correlation="c2", expected=stale_id), ok)
    # B2 reordered operations under the same key conflict
    k2 = f"i60b-{stamp}-k2"
    o2 = [("set_property", f"i60b_{stamp}_a", "x", "1"), ("set_property", f"i60b_{stamp}_a", "y", "2")]
    commit_case("B2.first", A, {"key": k2, "ops": o2}, ok)
    commit_case("B2.reordered", A, {"key": k2, "ops": list(reversed(o2))}, ok)
    # B3 a key used only by a refused (stale) commit stays free
    k3 = f"i60b-{stamp}-k3"
    _, _, s3a, r3a, o3a = commit_case("B3.stale", A, {"key": k3, "expected": stale_id, "ops": [("create_node", f"i60b_{stamp}_c")]}, ok)
    _, _, _, r3b, o3b = commit_case("B3.reuse", A, {"key": k3, "ops": [("create_node", f"i60b_{stamp}_d")]}, ok)

    def exp3(ref, s=s3a, ra=r3a, rb=r3b):
        s1, p1, _ = ref.client(s, ra, 1, ok)
        _, p2, _ = ref.client(s1, rb, 1, ok)
        return [p1, p2]
    add("B3.chain_refused_key_then_reuse", [o3a["py"], o3b["py"]], exp3)
    # B4 unknown expected head
    commit_case("B4.unknown_head", A, {"expected": "0123456789abcdef0123456789abcdef", "ops": [("create_node", f"i60b_{stamp}_u")]}, ok)
    # B5 empty and bad op_ref refused before the server, in every state
    for n, label in ((A, "enabled"), (E, "never")):
        commit_case(f"B5.empty_{label}", n, {"ops": []}, ok)
    commit_case("B5.empty_stale", A, {"expected": stale_id, "ops": []}, ok)
    commit_case("B5.bad_op_ref", A, {"ops": [("create_node", f"i60b_{stamp}_r")], "bad_ref": 0}, ok)
    # B6 size boundary on I60LC (max_ops 2)
    commit_case("B6.at_limit", C, {"ops": [("create_node", f"i60b_{stamp}_s1"), ("create_node", f"i60b_{stamp}_s2")]}, ok)
    commit_case("B6.over_limit", C, {"ops": [("create_node", f"i60b_{stamp}_s3"), ("create_node", f"i60b_{stamp}_s4"),
                                             ("create_node", f"i60b_{stamp}_s5")]}, ok)
    # B7 failed operations: missing endpoint (narrowed) and an existing relationship (plain)
    commit_case("B7.missing_node", A, {"ops": [("create_node", f"i60b_{stamp}_m1"), ("create_relationship", f"i60b_{stamp}_m1", "R", f"i60b_{stamp}_nope")]},
                {"ok": False, "index": 1, "missing": f"i60b_{stamp}_nope"})
    commit_case("B7.relationship_exists", A, {"ops": [("set_property", f"i60b_{stamp}_a", "z", "1"),
                                                      ("create_relationship", f"i60b_{stamp}_a", "R", f"i60b_{stamp}_b")]},
                {"ok": False, "index": 1})
    # B13 never enabled vs disabled (I60LA toggled; the re-enable writes an adoption revision when needed)
    commit_case("B13.never_enabled", E, {"ops": [("create_node", f"i60b_{stamp}_ne")]}, ok)
    A.L.disable()
    commit_case("B13.disabled", A, {"ops": [("create_node", f"i60b_{stamp}_dis")]}, ok)
    sd = A.state()
    head_dis = A.L.head().seq
    add("B11.head_while_disabled", ("At", head_dis), lambda ref, s=sd: ref.head_read(s))
    # B12 set_strict while disabled is reset by the next enable(); enable(strict=True) on an enabled ledger keeps strict
    A.L.set_strict(True)
    A.L.enable()
    add("B12.strict_after_reenable", A.L.meta()["strict"], lambda ref, s=sd: ref.reenable_strict(dict(s, strict=True), False))
    s_en = A.state()
    A.L.enable(strict=True)
    add("B12.enable_strict_on_enabled", A.L.meta()["strict"], lambda ref, s=s_en: ref.enable_on_enabled_strict(s, True))
    try:
        E.L.head(); hd = ("At", None)
    except LE.LedgerNotEnabledError:
        hd = ("Raise", "NotEnabled")
    se = E.state()
    add("B11.head_never_enabled", hd, lambda ref, s=se: ref.head_read(s))
    # B10 readers on revision IDs
    sa = A.state()
    tmp = Path(tempfile.mkdtemp(prefix="i60-bind-")) / "x.ndjson"
    unknown = "f" * 32
    for label, fn in (("get_revision", lambda: A.L.get_revision(unknown)), ("reconstruct", lambda: A.L.reconstruct(unknown)),
                      ("export", lambda: A.L.export_reconstruction(unknown, str(tmp))), ("diff", lambda: A.L.diff(stale_id, unknown))):
        try:
            fn(); got = ("At", "?")
        except LE.UnknownRevisionError:
            got = ("Raise", "UnknownRev")
        add(f"B10.{label}_unknown", got, lambda ref, s=sa: ref.seq_read(s, unknown))
    add("B10.export_wrote_nothing", tmp.exists(), lambda ref: False)
    hid = A.L.head().revision_id
    add("B10.head_id_resolves", ("At", A.L.get_revision(hid).info.seq), lambda ref, s=sa, h=hid: ref.seq_read(s, h))
    # B9 caller rollback frees the key and the seq
    k9 = f"i60b-{stamp}-k9"
    s9 = A.state()
    A.c.setAutoCommit(False)
    try:
        c9, r9 = cs_of({"key": k9, "ops": [("create_node", f"i60b_{stamp}_t1")]}, stamp)
        py9, _, _ = observe_commit(A, c9)
    finally:
        A.c.rollback(); A.c.setAutoCommit(True)
    c9b, r9b = cs_of({"key": k9, "ops": [("create_node", f"i60b_{stamp}_t2")]}, stamp)
    py9b, _, _ = observe_commit(A, c9b)
    if py9b[0] == "Res" and not py9b[2]:
        A.idem[k9] = (py9b[1], r9b)

    def exp9(ref, s=s9, r9=r9, r9b=r9b):
        s1, p1, _ = ref.txn_commit(s, r9, 1, ok)
        s2 = ref.txn_rollback(s, s1, 1)
        _, p2, _ = ref.client(s2, r9b, 2, ok)
        return [p1, p2]
    add("B9.rollback_frees_key_and_seq", [py9, py9b], exp9)
    # B8 caller transaction holds the head and the counter row: another process times out (about 40 s) and its refusal
    # is NOT counted (counters read from a third connection while A is open and after A's rollback); after the
    # rollback the same commit succeeds with the kept parent (review 60 FE-3: B8 had no counter delta before)
    s8 = A.state()
    B, R = NS(NS_A), NS(NS_A)
    A.c.setAutoCommit(False)
    try:
        c8, r8 = cs_of({"ops": [("create_node", f"i60b_{stamp}_la")]}, stamp)
        py8a, _, _ = observe_commit(A, c8)
        k8_open0 = R.counters()
        d8, rd8 = cs_of({"ops": [("create_node", f"i60b_{stamp}_lb")]}, stamp)
        t0 = time.time()
        py8b, ev8b, _ = observe_commit(B, d8)
        waits["B8"] = round(time.time() - t0, 1)
        k8_open1 = R.counters()
    finally:
        A.c.rollback(); A.c.setAutoCommit(True)
    k8_rb = R.counters()
    py8c, _, rev8c = observe_commit(B, d8)
    k8_c = R.counters()
    parent_ok = rev8c is not None and rev8c.parent_id == s8["id_of"][s8["head"]]

    def exp8(ref, s=s8, r8=r8, rd8=rd8):
        s1, p1, _ = ref.txn_commit(s, r8, 1, ok)
        s2, p2, e2 = ref.client(s1, rd8, 2, ok)
        s3 = ref.txn_rollback(s, s2, 1)
        s4, p3, _ = ref.client(s3, rd8, 2, ok)
        return [p1, p2, e2, cdelta(s1["cnt"], s2["cnt"]), cdelta(s["cnt"], s3["cnt"]), p3, cdelta(s["cnt"], s4["cnt"]),
                s4["parent"].get(s["head"] + 1) == s["id_of"][s["head"]]]
    add("B8.caller_transaction_holds_head", [py8a, py8b, ev8b, cdelta(k8_open0, k8_open1), cdelta(s8["cnt"], k8_rb), py8c,
                                             cdelta(s8["cnt"], k8_c), parent_ok], exp8)
    # B8b a nested commit refused without a count (revision row too long) holds the head but not the counter row:
    # the other process times out after about 30 s and its lock-timeout IS counted, and the count survives the rollback
    s8b = A.state()
    A.c.setAutoCommit(False)
    try:
        c8b, r8b = cs_of({"message": "m" * 5000, "ops": [("create_node", f"i60b_{stamp}_lc")]}, stamp)
        py8b_a, ev8b_a, _ = observe_commit(A, c8b)
        d8b, rd8b = cs_of({"ops": [("create_node", f"i60b_{stamp}_ld")]}, stamp)
        t0 = time.time()
        py8b_b, ev8b_b, _ = observe_commit(B, d8b)
        waits["B8b"] = round(time.time() - t0, 1)
        k8b_open = R.counters()
    finally:
        A.c.rollback(); A.c.setAutoCommit(True)
    k8b_rb = R.counters()

    def exp8b(ref, s=s8b, r8b=r8b, rd8b=rd8b):
        s1, p1, e1 = ref.txn_commit(s, r8b, 1, ok)
        s2, p2, e2 = ref.client(s1, rd8b, 2, ok)
        s3 = ref.txn_rollback(s, s2, 1)
        return [p1, e1, p2, e2, cdelta(s["cnt"], s2["cnt"]), cdelta(s["cnt"], s3["cnt"])]
    add("B8b.uncounted_nested_refusal_leaves_counter_row", [py8b_a, ev8b_a, py8b_b, ev8b_b, cdelta(s8b["cnt"], k8b_open),
                                                           cdelta(s8b["cnt"], k8b_rb)], exp8b)
    # B8c the strict guard's counter call (Ledger.Count) from another process is lost while A's transaction holds the row
    s8c = A.state()
    A.c.setAutoCommit(False)
    try:
        c8c, r8c = cs_of({"ops": [("create_node", f"i60b_{stamp}_le")]}, stamp)
        observe_commit(A, c8c)
        k8c_0 = R.counters()
        t0 = time.time()
        R.e._iris_obj().classMethodValue("Graph.KG.Ledger", "Count", "rej_strict_block")
        waits["B8c"] = round(time.time() - t0, 1)
        k8c_1 = R.counters()
    finally:
        A.c.rollback(); A.c.setAutoCommit(True)
    k8c_2 = R.counters()
    R.e._iris_obj().classMethodValue("Graph.KG.Ledger", "Count", "rej_strict_block")
    k8c_3 = R.counters()

    def exp8c(ref, s=s8c, r8c=r8c):
        s1, _, _ = ref.txn_commit(s, r8c, 1, ok)
        s2 = ref.count_strict(s1, 3)
        s3 = ref.txn_rollback(s, s2, 1)
        s4 = ref.count_strict(s3, 3)
        return [cdelta(s1["cnt"], s2["cnt"]), cdelta(s3["cnt"], s4["cnt"])]
    add("B8c.strict_count_lost_while_row_held", [cdelta(k8c_0, k8c_1), cdelta(k8c_2, k8c_3)], exp8c)
    B.close(); R.close()
    # B18 a commit into the target of an unfinished redaction of this run's own prefix: RedactionInProgressError, one
    # event, no counter, nothing written; a neighbour outside the target commits. B19: while it is unfinished, every
    # revision-ID reader refuses with RedactionInProgressError before looking the ID up (review 60 FE-4, FE-6)
    pfx = f"i60b{stamp}red"
    # One redaction batch scans at most batch_size x 20 records from the start of the history and sets the marker at its
    # first tombstone (LedgerRedact.BatchInLock). Size the batch to reach this run's target and give the target more
    # records than one batch tombstones, so exactly one unfinished redaction exists (run 1 of this repair used
    # batch_size=1, scanned no target record and left no marker: probes/ledger_client-binding-run1-crashed.log).
    prior = sum(int(r.op_count or 0) for r in A.L.history(limit=100000).revisions)
    batch18 = prior // 20 + 2
    rids = [f"{pfx}|{i}" for i in range(batch18 + 3)]
    cs18 = Changeset(actor="bind", actor_type="agent")
    for i in rids:
        cs18.upsert_node(i, properties={"p": "x"})
    A.L.commit(cs18)
    cs18 = Changeset(actor="bind", actor_type="agent")
    for i in rids:
        cs18.delete_node(i)
    A.L.commit(cs18)
    red1 = A.L.redact(None, prefix=pfx, batch_size=batch18, max_batches=1)
    if A.L.redaction_in_progress() is None:
        raise RuntimeError(f"setup: no unfinished redaction after one batch of {batch18} (prior records {prior})")
    commit_case("B18.redaction_blocked", A, {"ops": [("upsert_node", f"{pfx}|9")]}, {"ok": True, "index": 0, "blocked": True})
    commit_case("B18.neighbour_outside_target", A, {"ops": [("create_node", f"i60b_{stamp}_out")]}, {"ok": True, "index": 0, "blocked": False})
    s19 = A.state()
    tmp19 = Path(tempfile.mkdtemp(prefix="i60r-bind-")) / "x.ndjson"
    for label, fn in (("get_revision", lambda: A.L.get_revision(unknown)), ("reconstruct", lambda: A.L.reconstruct(unknown)),
                      ("export", lambda: A.L.export_reconstruction(unknown, str(tmp19))), ("diff", lambda: A.L.diff(stale_id, unknown))):
        try:
            fn(); got = ("At", "?")
        except LE.RedactionInProgressError:
            got = ("Raise", "RedactionInProgress")
        except LE.UnknownRevisionError:
            got = ("Raise", "UnknownRev")
        add(f"B19.{label}_unknown_during_redaction", got, lambda ref, s=s19: ref.seq_read(s, unknown))
    red2 = A.L.redact(None, prefix=pfx)
    waits["B18.redaction"] = {"first_complete": red1.complete, "second_complete": red2.complete, "batch_size": batch18,
                              "prior_records": prior, "target_nodes": len(rids)}
    s19b = A.state()
    try:
        A.L.get_revision(unknown); got = ("At", "?")
    except LE.UnknownRevisionError:
        got = ("Raise", "UnknownRev")
    add("B19.get_revision_unknown_after_redaction", got, lambda ref, s=s19b: ref.seq_read(s, unknown))
    # B20 revision-row field limits: refused as `inconsistent` after apply, uncounted, nothing written; a keyed retry
    # with an over-long message replays because the key is decided first (review 60 FE-5)
    commit_case("B20.message_4000", A, {"message": "m" * 4000, "ops": [("create_node", f"i60b_{stamp}_f1")]}, ok)
    commit_case("B20.message_5000", A, {"message": "m" * 5000, "ops": [("create_node", f"i60b_{stamp}_f2")]}, ok)
    commit_case("B20.key_300", A, {"key": f"i60b-{stamp}-" + "k" * 290, "ops": [("create_node", f"i60b_{stamp}_f3")]}, ok)
    commit_case("B20.correlation_300", A, {"correlation": "c" * 300, "ops": [("create_node", f"i60b_{stamp}_f4")]}, ok)
    commit_case("B20.actor_300", A, {"actor": "a" * 300, "ops": [("create_node", f"i60b_{stamp}_f5")]}, ok)
    commit_case("B20.source_object_4100", A, {"source": {"blob": "s" * 4100}, "ops": [("create_node", f"i60b_{stamp}_f6")]}, ok)
    k20 = f"i60b-{stamp}-k20"
    # a relationship op makes the result's statement IDs observable (a node-only changeset has none either way; run 2 of
    # this repair compared a node-only replay and disagreed only on that vacuous flag)
    o20 = [("create_node", f"i60b_{stamp}_f7"), ("create_node", f"i60b_{stamp}_f8"),
           ("create_relationship", f"i60b_{stamp}_f7", "R", f"i60b_{stamp}_f8")]
    commit_case("B20.keyed_first", A, {"key": k20, "message": "first", "ops": o20}, ok)
    commit_case("B20.keyed_retry_long_message", A, {"key": k20, "message": "m" * 5000, "ops": o20}, ok)
    # B14 revision rows are immutable through SQL
    cur = A.c.cursor()
    for label, sql in (("update", "UPDATE Graph_KG.ledger_revisions SET message='x' WHERE seq=1"),
                       ("delete", "DELETE FROM Graph_KG.ledger_revisions WHERE seq=1")):
        try:
            cur.execute(sql); got = "allowed"
        except Exception as ex:
            got = "refused" if "immutable" in str(ex) else f"other: {str(ex)[:80]}"
        expect = (lambda ref: "allowed" if ref.update_allowed(False, False, False, False) else "refused") if label == "update" else (lambda ref: "refused")
        add(f"B14.sql_{label}", got, expect)
    cur.close()
    # B15 chunked transport: a staged changeset and a staged answer join back exactly
    big = Changeset(actor="bind", actor_type="agent")
    big.create_node(f"i60b_{stamp}_big")
    for i in range(45):
        big.set_property(f"i60b_{stamp}_big", f"k{i:02d}", f"{i:02d}" + "x" * 29998)
    payload = big.canonical_json()
    rb = A.L.commit(big)
    vals = {r.attr: r.new for r in A.L.get_revision(rb.revision.revision_id).records if r.op == "set_prop"}
    add("B15.staged_changeset_values", [len(payload) > 1_000_000, len(vals), sorted({len(v) for v in vals.values()})],
        lambda ref, p=payload: [len(ref.chunks(p, 1_000_000)) > 1, 45, [30000]] if "".join(ref.chunks(p, 1_000_000)) == p else ["joined differs"])
    text = "".join(chr(97 + (i % 26)) for i in range(2_500_000))
    raw = str(A.e._iris_obj().classMethodValue("Graph.KG.Ledger", "LargeOut", text))
    parts = raw.split(":")
    back = "".join(str(A.e._iris_obj().classMethodValue("Graph.KG.Ledger", "ReadLargeOutChunk", parts[1], i)) for i in range(1, int(parts[2]) + 1))
    add("B15.large_answer", [parts[0], int(parts[2]), back == text],
        lambda ref, t=text: ["CHUNKED", len(ref.chunks(t, 1_000_000)), "".join(ref.chunks(t, 1_000_000)) == t])
    # B17 a text source is dropped; an object source is stored and found by its exact JSON text only
    st_obj, st_txt = {"system": "cmms", "run": stamp}, "auto-ingest"
    co = Changeset(actor="bind", actor_type="ingest", source=st_obj); co.create_node(f"i60b_{stamp}_so")
    ct = Changeset(actor="bind", actor_type="ingest", source=st_txt); ct.create_node(f"i60b_{stamp}_st")
    ro, rtx = A.L.commit(co), A.L.commit(ct)
    info_o, info_t = A.L.get_revision(ro.revision.revision_id).info.source, A.L.get_revision(rtx.revision.revision_id).info.source
    compact = json.dumps(st_obj, sort_keys=True, separators=(",", ":"))
    found = [r.seq for r in A.L.history(limit=100000, source=compact).revisions]
    found_txt = [r.seq for r in A.L.history(limit=100000, source=st_txt).revisions]
    add("B17.source", ["object" if isinstance(info_o, dict) else info_o, info_t, found == [ro.revision.seq], found_txt],
        lambda ref: [ref.stored_source(st_obj), ref.stored_source(st_txt), True, [] if ref.stored_source(st_txt) is None else [rtx.revision.seq]])
    for n in (A, C, E):
        n.close()

    # ------------------------------------------------------------------ compare
    mism = run(Ref(), live, stamp, None)
    detected = {}
    for m in MUTATIONS:
        detected[m] = bool(run(Ref(m), live, stamp, None))
    # a changed observation must be caught
    changed = copy.deepcopy(live)
    for case in changed:
        if case["name"] == "B4.unknown_head":
            case["observed"]["py"] = ("Raise", "Stale", {"current_head": "x"})
    changed_caught = bool(run(Ref(), changed, stamp, None))
    native_scope = [m for m in MUTATIONS if m not in NOT_NATIVE]
    verdict = "AGREES" if not mism and all(detected[m] for m in native_scope) and changed_caught else "DISAGREES"
    body = {
        "verdict": verdict, "comparisons": len(live), "mismatch_count": len(mism), "mismatches": mism,
        "mutations_detected": detected, "mutations_not_natively_exercisable": NOT_NATIVE, "changed_observation_caught": changed_caught,
        "cases": [{"name": c["name"], "observed": c["observed"]} for c in live],
        "fixture": rt.FIXTURE, "namespaces": [NS_A, NS_C, NS_E], "run_stamp": stamp, "wall_seconds_not_compared": waits,
        "pin": bc.pin_identity(PIN_DIR),
        "observed": "actual GraphLedger.commit/_commit/_send_changeset/_call/_emit/head/get_revision/diff/reconstruct/"
                    "export_reconstruction/history/stats/enable/disable/set_strict, Changeset builder/validate/fingerprint, "
                    "errors.from_commit_error, and the deployed Graph.KG.Ledger/LedgerApply/LedgerStats/LedgerRevision on IRIS",
        "substituted": "none for the product; the expected side is an unverified hand transcription of ledger_client.rs",
        "not_observed": "IdempotencyRedactedError; the redaction marker only as a neighbour (one blocked commit and the "
                        "readers during one unfinished redaction of this run's own prefix; whether records touch the target "
                        "is the ledger_redaction input `blocked`); object-path re-save/delete of a revision row; Inconsistent "
                        "transport failures; a write whose counter row another transaction holds while the head is free; "
                        "the ObjectScript bodies are executed, not proved",
    }
    out = bc.write_receipt("ledger_client", Path(__file__), body)
    d = json.loads(out.read_text())
    for p in ["iris_vector_graph/ledger/changeset.py", "iris_vector_graph/ledger/client.py", "iris_vector_graph/ledger/errors.py",
              "iris_src/src/Graph/KG/Ledger.cls", "iris_src/src/Graph/KG/LedgerStats.cls", "iris_src/src/Graph/KG/LedgerRevision.cls"]:
        d["inputs"][p] = bc.sha(PIN_DIR / p)
        assert d["inputs"][p] == bc.sha(bc.REPO / p), p
    d["inputs"][".g5/uplift/consolidated/local-runtime/runtime.py"] = bc.sha(Path(rt.__file__))
    out.write_text(json.dumps(d, indent=2, sort_keys=True, default=str) + "\n")
    print(f"ledger_client binding: {verdict}; {len(live)} cases; mismatches {len(mism)}; "
          f"mutations detected {sum(detected.values())}/{len(detected)} (not native: {list(NOT_NATIVE)}); changed caught {changed_caught}; {out}")
    return int(verdict != "AGREES")


if __name__ == "__main__":
    raise SystemExit(main())
