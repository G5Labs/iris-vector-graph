"""Module 11 (ledger core) machines from models/breadth-b/src/m11.rs (pin 3eaa79cf), transcribed for trace replay.

Machines replayed: enable (m11.rs:29-131), adopt (m11.rs:132-226), guard (m11.rs:345-421), retry (m11.rs:422-491),
commit (m11.rs:492-577). The explorer's exploration bounds (writes < 3, retries < 2, tries < 3) are not guards of a real
step and are not applied. Abstraction over ^IVG.Ledger, Graph_KG.ledger_revisions, the content tables and the replies.
"""
from __future__ import annotations

import json
from typing import Any, List, Optional

from trlib import Family, Store


def _state(store: Store) -> str:
    return str(store.get("^IVG.Ledger", "meta", "state") or "never-enabled")


def _head(store: Store) -> int:
    v = store.get("^IVG.Ledger", "head")
    return int(v) if v not in (None, "") else 0


def _revs(store: Store) -> List[int]:
    return sorted(int(r["_id"]) for r in store.rows("Graph_KG.ledger_revisions"))


def _cp(x):
    return json.loads(json.dumps(x))


# ================================================================================================ enable


class LedEnable(Family):
    """m11.rs:29-131. Two enables; state: enabled, head, rev1 (revision row seq 1), pc per process."""
    name = "m11-enable"
    source = "models/breadth-b/src/m11.rs:36-131"
    E_OK = "LED-B1.12 every concurrent enable answers the genesis"
    E_CONS = "LED-B1.7 between transactions: enabled iff revision 1 exists and is the head"

    def __init__(self, design="as-built"):
        super().__init__()
        self.design = design
        self.name = f"m11-enable[{design}]"

    def init(self, store, trace):
        return {"enabled": _state(store) == "enabled", "head": _head(store), "rev1": 1 in _revs(store),
                "lock": None, "pc": ["Idle", "Idle"], "pre": [[False, 0, False], [False, 0, False]]}

    def next(self, s, a):
        t = _cp(s)
        kind, i = a
        locked = self.design != "control-no-lock"
        if kind == "Start":
            if s["pc"][i] != "Idle":
                return None
            if self.design == "as-built" and s["enabled"]:
                t["pc"][i] = ["Done", s["head"] >= 1 and s["rev1"]]
            else:
                t["pc"][i] = "Ready"
        elif kind == "Lock":
            if s["pc"][i] != "Ready":
                return None
            if locked:
                if s["lock"] is not None:
                    return None
                t["lock"] = i
            t["pre"][i] = [s["enabled"], s["head"], s["rev1"]]
            if self.design != "as-built" and s["enabled"]:
                t["pc"][i] = ["Done", s["head"] >= 1 and s["rev1"]]
                if locked:
                    t["lock"] = None
            else:
                t["pc"][i] = "Locked"
        elif kind == "SetState":
            if s["pc"][i] != "Locked":
                return None
            t["enabled"], t["head"], t["pc"][i] = True, 0, "Head0"
        elif kind == "Save":
            if s["pc"][i] != "Head0":
                return None
            if s["rev1"]:
                e, h, r = s["pre"][i]
                t["enabled"], t["head"], t["rev1"], t["pc"][i] = e, h, r, ["Done", False]
            else:
                t["rev1"], t["head"], t["pc"][i] = True, 1, ["Done", True]
            if locked:
                t["lock"] = None
        else:
            return None
        return t

    def invariants(self):
        return [(self.E_OK, lambda s: ["Done", False] not in s["pc"]),
                (self.E_CONS, lambda s: any(p in ("Locked", "Head0") for p in s["pc"]) or
                 (s["enabled"] == s["rev1"] and (s["head"] == 1) == s["rev1"]))]

    def obs(self, s):
        return (s["enabled"], s["head"], s["rev1"], tuple(str(p) for p in s["pc"]))

    def alpha(self, store, step):
        pcs = list(self.S["pc"])
        if step is not None and step.get("enabler") is not None:
            ok = bool(step["ok"]) and isinstance(step["reply"], dict) and step["reply"].get("seq") == 1
            pcs[step["enabler"]] = ["Done", ok]
        return (_state(store) == "enabled", _head(store), 1 in _revs(store), tuple(str(p) for p in pcs))

    def actions(self, step, seg, pre, post):
        i = step.get("enabler")
        if i is None:
            return []
        if self.design == "as-built" and self.S["enabled"]:
            return [("Start", i)]
        if self.design != "as-built" and self.S["enabled"]:
            return [("Start", i), ("Lock", i)]
        return [("Start", i), ("Lock", i), ("SetState", i), ("Save", i)]

    def relevant(self, ref):
        return ref.startswith('^IVG.Ledger("meta","state")') or ref.startswith('^IVG.Ledger("head")')


# ================================================================================================ retry


class LedRetry(Family):
    """m11.rs:422-491 (F-1101). A commit with a post-commit property V1, a later governed set to V2, a retry of the
    first changeset (same key)."""
    name = "m11-retry"
    source = "models/breadth-b/src/m11.rs:431-491"
    R_NOOP = "LED-B10.5 a replayed commit changes nothing"
    R_STMT = "LED-B4.7.8 a replayed commit answers the first commit's statement ids"
    R_GOV = "a governed value is the store's value until the next governed change"

    def __init__(self, key, node, prop, design="as-built"):
        super().__init__()
        self.key, self.node, self.prop, self.design = key, node, prop, design
        self.name = f"m11-retry[{design}]"

    def init(self, store, trace):
        return {"bound": False, "node": False, "prop": 0, "rec_prop": 0, "governed": False, "retries": 0,
                "answer": None}

    def next(self, s, a):
        t = _cp(s)
        if a == "Commit":
            if s["bound"]:
                return None
            t.update(bound=True, node=True, prop=1, answer=[False, 1])
        elif a == "GovernedSet":
            if not s["node"] or s["governed"]:
                return None
            t.update(governed=True, prop=2, rec_prop=2, answer=None)
        elif a == "Retry":
            if not s["bound"]:
                return None
            t["retries"] += 1
            t["answer"] = [True, None if self.design == "as-built" else 1]
            if self.design != "reviewed":
                t["prop"] = 1
        else:
            return None
        return t

    def invariants(self):
        return [(self.R_GOV, lambda s: not s["governed"] or s["prop"] == s["rec_prop"])]

    def action_properties(self):
        return [(self.R_NOOP, lambda s, a, t: a != "Retry" or (s["node"] == t["node"] and s["prop"] == t["prop"]
                                                              and s["bound"] == t["bound"])),
                (self.R_STMT, lambda s, a, t: a != "Retry" or (t["answer"] is not None and t["answer"][1] == 1))]

    @staticmethod
    def _val(v):
        return {"V1": 1, "V2": 2}.get(str(v).strip('"'), 0) if v is not None else 0

    def obs(self, s):
        return (s["bound"], s["node"], s["prop"], s["rec_prop"],
                None if s["answer"] is None else tuple(s["answer"]))

    def alpha(self, store, step):
        bound = store.has("^IVG.Ledger", "idem", self.key)
        node = any(str(r.get("node_id")) == self.node for r in store.rows("Graph_KG.nodes"))
        prop = 0
        for r in store.rows("Graph_KG.rdf_props"):
            if str(r.get("s")) == self.node and str(r.get("key")) == self.prop:
                prop = self._val(r.get("val"))
        rec = 0
        for k, v in sorted(store.under("^IVG.Ledger", "rec").items(), key=lambda kv: (int(kv[0][2]), int(kv[0][3]))):
            if isinstance(v, tuple) and v[:4] == ("set_prop", "node", self.node, self.prop):
                rec = self._val(str(v[5])[1:] if str(v[5]).startswith("S") else None)
        ans = self.S["answer"]
        if step is not None and step.get("retry_op") in ("Commit", "Retry") and isinstance(step["reply"], dict):
            ids = step["reply"].get("stmt_ids") or {}
            ans = [bool(step["reply"].get("replayed")), 1 if (ids or step["retry_op"] == "Commit") else None]
            if step["retry_op"] == "Commit":
                ans = [False, 1]
        elif step is not None and step.get("retry_op") == "GovernedSet":
            ans = None
        return (bound, node, prop, rec, None if ans is None else tuple(ans))

    def actions(self, step, seg, pre, post):
        a = step.get("retry_op")
        return [a] if a and step["ok"] else []

    def relevant(self, ref):
        return ref.startswith('^IVG.Ledger("idem"')


# ================================================================================================ guard


class LedGuard(Family):
    """m11.rs:345-421 (F-0801 TTL cache, F-1108 unguarded writers). One engine E1's guard cache; E2 sets strict."""
    name = "m11-guard"
    source = "models/breadth-b/src/m11.rs:354-421"
    G_SG = "SG in strict mode every governed write is recorded or refused"

    def __init__(self, design="as-built", ttl=1):
        super().__init__()
        self.design, self.ttl = design, ttl
        self.name = f"m11-guard[{design}]"
        self.roots = ()

    def bind(self, trace):
        self.roots = tuple(trace["layouts"][t]["data"] + "(" for t in ("Graph_KG.nodes", "Graph_KG.rdf_edges"))

    def init(self, store, trace):
        return {"strict": str(store.get("^IVG.Ledger", "meta", "strict") or "0") == "1", "cache": None, "age": 0,
                "probe_fails": False, "bad": False, "refused": False, "writes": 0}

    def _check(self, s, t):
        fresh = self.design != "as-built"
        if not fresh and s["cache"] is not None and s["age"] < self.ttl:
            return s["cache"]
        v = (self.design == "reviewed") if s["probe_fails"] else s["strict"]
        if not fresh:
            t["cache"], t["age"] = (False if s["probe_fails"] else s["strict"]), 0
        return v

    def next(self, s, a):
        t = _cp(s)
        kind = a[0] if isinstance(a, tuple) else a
        if kind == "SetStrict":
            if s["strict"] == a[1]:
                return None
            t["strict"] = a[1]
        elif kind == "Tick":
            if s["age"] >= self.ttl:
                return None
            t["age"] += 1
        elif kind in ("GuardedWrite", "CypherWrite"):
            t["writes"] += 1
            if self._check(s, t):
                t["refused"] = True
            elif s["strict"]:
                t["bad"] = True
        elif kind == "UnguardedWrite":
            t["writes"] += 1
            if self.design != "as-built" and self._check(s, t):
                t["refused"] = True
            elif s["strict"]:
                t["bad"] = True
        elif kind == "LedgerCommit":
            t["writes"] += 1
        else:
            return None
        return t

    def invariants(self):
        return [(self.G_SG, lambda s: not s["bad"])]

    def obs(self, s):
        return (s["strict"], s["refused"], s["bad"])

    def alpha(self, store, step):
        strict = str(store.get("^IVG.Ledger", "meta", "strict") or "0") == "1"
        refused, writes, bad = self.S["refused"], self.S["writes"], self.S["bad"]
        if step is not None and step.get("guard_op") in ("GuardedWrite", "CypherWrite", "UnguardedWrite", "LedgerCommit"):
            writes = self.S["writes"]   # counted by the model; the trace shows the outcome below
            landed = step["ok"] and step.get("landed", True)
            refused = self.S["refused"] or (not step["ok"] and "strict" in str(step.get("error") or "").lower())
            bad = self.S["bad"] or (landed and strict and step["guard_op"] != "LedgerCommit")
        return (strict, refused, bad)

    def actions(self, step, seg, pre, post):
        g = step.get("guard_op")
        if not g:
            return []
        if g == "SetStrict":
            return [("SetStrict", bool(step["strict"]))] if step["ok"] else []
        if g == "Tick":
            return ["Tick"]
        return [g]

    def relevant(self, ref):
        # the strict flag, and the content rows a write that lands changes (whether a write landed is what SG reads)
        return ref.startswith('^IVG.Ledger("meta","strict")') or ref.startswith(self.roots)


# ================================================================================================ adopt


class LedAdopt(Family):
    """m11.rs:132-226 (F-1103; LED-B1.20). One adopter, no concurrent committer (committed_e true at start): an
    unrecorded write U made while disabled; verify(adopt=True) = ReadRecords, ReadStore, CommitAdoption."""
    name = "m11-adopt"
    source = "models/breadth-b/src/m11.rs:140-216"
    A_ONCE = "LED-B1.20 every fact is recorded at most once"
    A_REPLAY = "when no adoption runs the history replays to the store"
    U, EB = 1, 2

    def __init__(self, unode, edge=None, design="as-built"):
        super().__init__()
        self.unode, self.edge, self.design = unode, edge, design   # edge = (s, p, o) the committer records
        self.name = f"m11-adopt[{design}]"

    def _store_bits(self, store):
        b = self.U if any(str(r.get("node_id")) == self.unode for r in store.rows("Graph_KG.nodes")) else 0
        if self.edge and any((r.get("s"), r.get("p"), r.get("o_id")) == tuple(self.edge)
                             for r in store.rows("Graph_KG.rdf_edges")):
            b |= self.EB
        return b

    def _recs(self, store):
        n = sum(1 for v in store.under("^IVG.Ledger", "rec").values()
                if isinstance(v, tuple) and v[:3] == ("create_node", "node", self.unode))
        e = 0
        if self.edge:
            s, p, o = self.edge
            for v in store.under("^IVG.Ledger", "rec").values():
                if isinstance(v, tuple) and v[:2] == ("create_rel", "rel") and isinstance(v[5], str) and v[5][:1] == "S":
                    try:
                        t = json.loads(v[5][1:])
                    except ValueError:
                        continue
                    if (t.get("s"), t.get("p"), t.get("o")) == (s, p, o):
                        e += 1
        return [n, e]

    def init(self, store, trace):
        return {"store": self._store_bits(store), "rec": self._recs(store), "head": _head(store), "ad": ["Idle"],
                "tries": [0], "committed_e": self.edge is None}

    def next(self, s, a):
        t = _cp(s)
        replayed = (self.U if s["rec"][0] > 0 else 0) | (self.EB if s["rec"][1] > 0 else 0)
        if a == "ReadRecords":
            if s["ad"][0] != "Idle":
                return None
            t["ad"][0] = ["Recs", s["head"], replayed]
        elif a == "ReadStore":
            if not (isinstance(s["ad"][0], list) and s["ad"][0][0] == "Recs"):
                return None
            _, h, rep = s["ad"][0]
            t["ad"][0] = ["Diff", h, s["store"] & ~rep]
        elif a == "CommitEdge":
            if s["committed_e"]:
                return None
            t["committed_e"] = True
            t["store"] |= self.EB
            t["rec"][1] = min(t["rec"][1] + 1, 3)
            t["head"] += 1
        elif a == "CommitAdoption":
            if not (isinstance(s["ad"][0], list) and s["ad"][0][0] == "Diff"):
                return None
            _, h, diff = s["ad"][0]
            if diff == 0:
                t["ad"][0] = "Done"
                return t
            if self.design == "reviewed" and h != s["head"]:
                t["tries"][0] += 1
                t["ad"][0] = "Idle"
                return t
            for k, bit in ((0, self.U), (1, self.EB)):
                if diff & bit:
                    t["rec"][k] = min(t["rec"][k] + 1, 3)
            t["head"] += 1
            t["ad"][0] = "Done"
        else:
            return None
        return t

    def invariants(self):
        return [(self.A_ONCE, lambda s: all(c <= 1 for c in s["rec"])),
                (self.A_REPLAY, lambda s: not (all(p == "Done" for p in s["ad"]) and s["committed_e"]) or
                 ((s["rec"][0] > 0) == bool(s["store"] & self.U) and (s["rec"][1] > 0) == bool(s["store"] & self.EB)))]

    def obs(self, s):
        return (s["store"], tuple(s["rec"]), s["head"], s["ad"][0] if isinstance(s["ad"][0], str) else s["ad"][0][0])

    def alpha(self, store, step):
        ad = self.S["ad"][0]
        ad = ad if isinstance(ad, str) else ad[0]
        if step is not None and step.get("adopt"):
            ad = "Done"
        return (self._store_bits(store), tuple(self._recs(store)), _head(store), ad)

    def actions(self, step, seg, pre, post):
        if step.get("adopt") and step["ok"]:
            return ["ReadRecords", "ReadStore", "CommitAdoption"]
        if step.get("commit_edge") and step["ok"]:
            return ["CommitEdge"]
        return []

    def relevant(self, ref):
        return ref.startswith('^IVG.Ledger("rec"') or ref.startswith('^IVG.Ledger("head")')


# ================================================================================================ commit


class LedCommit(Family):
    """m11.rs:492-577 (LED-B4.3, LED-B4.11.2, LED-B4.7.5; P-1102). P1 commits inside a caller transaction, then the
    caller commits or rolls back; P2 commits plainly afterwards (same_key false)."""
    name = "m11-commit"
    source = "models/breadth-b/src/m11.rs:501-566"
    C_CHAIN = "LED-B4.11.2 revisions form one chain 1..head with no gaps"
    C_OPEN = "LED-B4.3 no commit builds on a head whose transaction has not ended"
    C_KEY = "LED-B4.7.5 a bound retry key names a kept revision"

    def __init__(self, base, design="as-built"):
        super().__init__()
        self.base, self.design = base, design     # seqs at or below base exist before the scenario
        self.name = f"m11-commit[{design}]"

    def init(self, store, trace):
        return {"head": _head(store) - self.base, "revs": 0, "key": None, "lock": None, "p1": ["Idle"],
                "p2": "Idle", "built_on_open": False, "same_key": False}

    def next(self, s, a):
        t = _cp(s)
        p1 = s["p1"][0]
        if a == "P1Lock":
            if p1 != "Idle" or s["lock"] is not None:
                return None
            t["lock"], t["p1"] = 1, ["Locked"]
        elif a == "P1Write":
            if p1 != "Locked":
                return None
            if s["key"] is not None:
                t["p1"], t["lock"] = ["Done"], None
                return t
            seq = s["head"] + 1
            t["p1"] = ["Written", s["head"], s["key"]]
            t["head"], t["revs"], t["key"] = seq, s["revs"] | (1 << (seq - 1)), seq
        elif a == "P1Inner":
            if p1 != "Written":
                return None
            t["p1"] = ["InnerDone", s["p1"][1], s["p1"][2]]
            if self.design == "control-immediate-unlock":
                t["lock"] = None
        elif isinstance(a, tuple) and a[0] == "P1Caller":
            if p1 != "InnerDone":
                return None
            pre_head, pre_key = s["p1"][1], s["p1"][2]
            if not a[1]:
                seq = pre_head + 1
                t["revs"] = s["revs"] & ~(1 << (seq - 1))
                t["head"] = pre_head
                if s["key"] == seq:
                    t["key"] = pre_key
            if t["lock"] == 1:
                t["lock"] = None
            t["p1"] = ["Done"]
        elif a == "P2Lock":
            if s["p2"] != "Idle" or s["lock"] is not None:
                return None
            t["lock"], t["p2"] = 2, "Locked"
        elif a == "P2Commit":
            if s["p2"] != "Locked":
                return None
            if not (s["same_key"] and s["key"] is not None):
                if p1 in ("Written", "InnerDone"):
                    t["built_on_open"] = True
                seq = s["head"] + 1
                t["head"], t["revs"] = seq, s["revs"] | (1 << (seq - 1))
            t["lock"], t["p2"] = None, "Done"
        else:
            return None
        return t

    def invariants(self):
        return [(self.C_CHAIN, lambda s: s["revs"] == (1 << s["head"]) - 1),
                (self.C_OPEN, lambda s: not s["built_on_open"]),
                (self.C_KEY, lambda s: s["key"] is None or bool(s["revs"] & (1 << (s["key"] - 1))))]

    def obs(self, s):
        return (s["head"], s["revs"])

    def alpha(self, store, step):
        head = _head(store) - self.base
        revs = 0
        for q in _revs(store):
            if q > self.base:
                revs |= 1 << (q - self.base - 1)
        return (head, revs)

    def actions(self, step, seg, pre, post):
        return list(step.get("commit_ops") or [])

    def relevant(self, ref):
        return ref.startswith('^IVG.Ledger("head")') or ref.startswith("^Graph.KG.LedgerRevisionD")
