"""Breadth lane B explorer machines (models/breadth-b/src/m07.rs .. m10.rs at pin 3eaa79cf), transcribed as
executable machines for trace replay, with the trace side (`alpha`: replayed store and step replies -> observable
machine state; `actions`: which machine actions a captured step performs). The model crate is not modified.

Exploration bounds of the explorer (a run count, a write count, "one build", "two queries") bound the state space
of the explorer; they are not guards of a real step and are lifted here (each lifted bound is named in the class
docstring). Trace-side bookkeeping a class adds (e.g. the last answer a call gave) never feeds back into next().
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from trlib import Family, Store


def _int(v, default=None):
    if v is None or v == "":
        return default
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return default


# ================================================================================================ m07 bm25

ND = 3
MASK = [0b11, 0b10, 0b01]
LEN = [2, 1, 1]


def _idx(**kw):
    d = {"n": None, "total": None, "schema": None, "graph": False, "upgrading": False, "idf": False,
         "post": [0, 0, 0], "len": [0, 0, 0], "doc": [0, 0, 0], "df": [0, 0]}
    d.update(kw)
    return d


def _content(ix):
    d = json.loads(json.dumps(ix))
    d["upgrading"] = False
    return d


def _index_doc(ix, d):
    ix["post"][d] |= MASK[d]
    for t in range(2):
        if MASK[d] & (1 << t):
            ix["df"][t] += 1
    ix["doc"][d] = MASK[d]
    ix["len"][d] = LEN[d]


def _remove_doc(ix, d):
    if ix["len"][d] == 0 and ix["doc"][d] == 0:
        return
    old, rec = ix["len"][d], ix["doc"][d]
    for t in range(2):
        if rec & (1 << t):
            ix["post"][d] &= ~(1 << t)
            ix["df"][t] = max(ix["df"][t] - 1, 0)
    ix["doc"][d] = 0
    ix["len"][d] = 0
    ix["n"] = (ix["n"] or 0) - 1
    ix["total"] = (ix["total"] or 0) - old


def _exists(ix):
    return ix["n"] is not None


def _schema(ix):
    return 1 if ix["schema"] is None else ix["schema"]


def _writable(ix):
    return not (_exists(ix) and (ix["upgrading"] or _schema(ix) < 2))


class Bm25(Family):
    """models/breadth-b/src/m07.rs:62-391 machine `bm25` (module 07; TXT-I1, TXT-I2, TXT-I3, TXT-X2, TXT-I5;
    F-0701, F-0704). One index name; documents 0, 1 (the graph's corpus) and 2 (inserted); tokens t0, t1.
    Transcribed: BuildStart/BuildIndex/BuildFinish/BuildCrash, WBegin/WTimeout/WBody, DropAll/DropLock/DropBody
    (Upgrade not driven). Bounds lifted: `builds >= 1` (each Build call is a fresh run of the build process: Done or
    Crashed -> Idle at its start), `wops >= 2`, `drops >= 1`."""
    name = "bm25"
    I1 = "TXT-I1 each word's document frequency is the count of documents that hold it"
    I2 = "TXT-I2 the document count and total length match the stored documents"
    I3 = "TXT-I3 a schema 2 index holds no saved word weights"
    X2 = "TXT-X2 a refused build leaves the old index as it was"
    I5 = "TXT-I5 two writers never change one BM25 index at the same time"

    def __init__(self, index: str, docs: List[str], tokens: List[str], design: str = "as-built"):
        super().__init__()
        self.index, self.docs, self.tokens, self.design = index, docs, tokens, design
        self.name = f"bm25[{design}]"
        rv = design == "reviewed"
        self.build_locks = rv
        self.shadow = rv
        self.early_refusal = rv
        self.drop_locks = rv

    def init(self, store, trace):
        return {"vis": self._observe(store)[0], "shadow": None, "lock": None, "b": ["Idle"], "snap": None,
                "refused_changed": False, "w": None, "d": 0}

    @staticmethod
    def _busy(s):
        v = []
        if s["b"][0] == "Running":
            v.append("B")
        if s["lock"] is not None and s["lock"] not in v:
            v.append(s["lock"])
        return v

    def next(self, s, a):  # noqa: C901 - a transcription of one match
        t = json.loads(json.dumps(s))
        kind = a[0] if isinstance(a, tuple) else a
        if kind == "BuildStart":
            bk = a[1]
            if s["b"][0] == "Running":
                return None
            if bk == "Empty" and self.early_refusal:
                t["b"] = ["Done"]
                return t
            if self.build_locks:
                if s["lock"] is not None:
                    return None
                t["lock"] = "B"
            if bk == "Empty":
                t["snap"] = _content(s["vis"])
            if self.shadow:
                t["shadow"] = _idx()
            else:
                t["vis"] = _idx()
            t["b"] = ["Running", bk, 0, 0, 0]
        elif kind == "BuildIndex":
            if s["b"][0] != "Running":
                return None
            _, bk, nxt, n, total = s["b"]
            if nxt >= (2 if bk == "Corpus" else 0):
                return None
            _index_doc(t["shadow"] if self.shadow else t["vis"], nxt)
            t["b"] = ["Running", bk, nxt + 1, n + 1, total + LEN[nxt]]
        elif kind == "BuildFinish":
            if s["b"][0] != "Running":
                return None
            _, bk, nxt, n, total = s["b"]
            if nxt < (2 if bk == "Corpus" else 0):
                return None
            if self.shadow:
                g = t["shadow"]
                t["shadow"] = None
                g.update(n=n, total=total, graph=True, schema=2)
                t["vis"] = g
            else:
                t["vis"].update(n=n, total=total, graph=True, schema=2)
            if t["lock"] == "B":
                t["lock"] = None
            if bk == "Empty":
                if t["snap"] is not None and _content(t["vis"]) != t["snap"]:
                    t["refused_changed"] = True
                t["snap"] = None
            t["b"] = ["Done"]
        elif kind == "BuildCrash":
            if s["b"][0] != "Running":
                return None
            t["b"], t["shadow"], t["snap"] = ["Crashed"], None, None
            if t["lock"] == "B":
                t["lock"] = None
        elif kind == "WBegin":
            op = a[1]
            if s["w"] is not None:
                return None
            if op == "Del" and not _exists(s["vis"]):
                return t
            if not _writable(s["vis"]):
                return t
            if s["lock"] is not None:
                return None
            t["lock"], t["w"] = "W", op
        elif kind == "WBody":
            op = s["w"]
            if op is None:
                return None
            t["w"], t["lock"] = None, None
            if not _writable(s["vis"]):
                return t
            v = t["vis"]
            if op == "Ins":
                if not _exists(v):
                    v.update(n=0, total=0, schema=2)
                _remove_doc(v, 2)
                _index_doc(v, 2)
                v["n"] = v["n"] + 1
                v["total"] = (v["total"] or 0) + LEN[2]
            else:
                _remove_doc(v, 0)
        elif kind == "DropAll":
            if self.drop_locks:
                return None
            t["vis"] = _idx()
        elif kind == "DropLock":
            if not self.drop_locks or s["d"] != 0 or s["lock"] is not None:
                return None
            t["lock"], t["d"] = "D", 1
        elif kind == "DropBody":
            if s["d"] != 1:
                return None
            t["vis"], t["lock"], t["d"] = _idx(), None, 0
        else:
            return None
        return t

    def invariants(self):
        def i1(s):
            v = s["vis"]
            if not (_exists(v) and v["schema"] == 2):
                return True
            return all(v["df"][t] == sum(1 for d in range(ND) if v["post"][d] & (1 << t)) for t in range(2)) and \
                all(v["doc"][d] == v["post"][d] for d in range(ND))

        def i2(s):
            v = s["vis"]
            if not (_exists(v) and v["schema"] == 2):
                return True
            return v["n"] == sum(1 for d in range(ND) if v["len"][d] > 0) and v["total"] == sum(v["len"])
        return [(self.I1, i1), (self.I2, i2), (self.I3, lambda s: s["vis"]["schema"] != 2 or not s["vis"]["idf"]),
                (self.X2, lambda s: not s["refused_changed"])]

    def action_properties(self):
        def who(a):
            k = a[0] if isinstance(a, tuple) else a
            return "B" if k.startswith("Build") else ("W" if k.startswith("W") else "D")

        def i5(s, a, t):
            if _content(s["vis"]) == _content(t["vis"]):
                return True
            me = who(a)
            return all(q == me for q in self._busy(s))
        return [(self.I5, i5)]

    def obs(self, s):
        v = s["vis"]
        return (v["n"], v["total"], v["schema"], v["graph"], v["upgrading"], v["idf"], tuple(v["post"]),
                tuple(v["len"]), tuple(v["doc"]), tuple(v["df"]), ())

    def _observe(self, store: Store):
        nm = self.index
        cfg = lambda k: store.get("^BM25Idx", nm, "cfg", k)  # noqa: E731
        v = _idx(n=_int(cfg("N")), total=_int(cfg("totalLen")), schema=_int(cfg("schema")),
                 graph=store.has("^BM25Idx", nm, "cfg", "graph"), upgrading=bool(_int(cfg("upgrading"), 0)),
                 idf=store.subtree_defined("^BM25Idx", nm, "idf"))
        extra = []
        for k, val in store.under("^BM25Idx", nm).items():
            kind = k[2] if len(k) > 2 else ""
            if kind == "tf" and len(k) == 5:
                if k[3] in self.tokens and k[4] in self.docs:
                    v["post"][self.docs.index(k[4])] |= 1 << self.tokens.index(k[3])
                else:
                    extra.append(("tf", k[3], k[4]))
            elif kind == "df" and len(k) == 4:
                if k[3] in self.tokens:
                    v["df"][self.tokens.index(k[3])] = _int(val, 0)
                else:
                    extra.append(("df", k[3]))
            elif kind == "len" and len(k) == 4:
                if k[3] in self.docs:
                    v["len"][self.docs.index(k[3])] = _int(val, 0)
                else:
                    extra.append(("len", k[3]))
            elif kind == "doc" and len(k) == 4:
                if k[3] in self.docs:
                    toks = val if isinstance(val, tuple) else ((val,) if val else ())
                    m = 0
                    for tk in toks:
                        if tk in self.tokens:
                            m |= 1 << self.tokens.index(tk)
                        else:
                            extra.append(("doc-token", k[3], tk))
                    v["doc"][self.docs.index(k[3])] = m
                else:
                    extra.append(("doc", k[3]))
        return v, tuple(sorted(extra))

    def alpha(self, store, step):
        v, extra = self._observe(store)
        return (v["n"], v["total"], v["schema"], v["graph"], v["upgrading"], v["idf"], tuple(v["post"]),
                tuple(v["len"]), tuple(v["doc"]), tuple(v["df"]), extra)

    def actions(self, step, seg, pre, post):
        fam = step.get("family")
        if fam != "bm25":
            return []
        op = step["op"]
        S = self.S
        if op in ("bm25_build", "index.build"):
            bk = "Corpus" if op == "bm25_build" else "Empty"
            acts = [("BuildStart", bk)]
            s1 = self.next(S, acts[0])
            if s1 is None or s1["b"][0] != "Running":
                return acts
            for _ in range(2 if bk == "Corpus" else 0):
                acts.append("BuildIndex")
            acts.append("BuildFinish")
            return acts
        if op in ("bm25_insert", "bm25_delete"):
            o = "Ins" if op == "bm25_insert" else "Del"
            s1 = self.next(S, ("WBegin", o))
            return [("WBegin", o)] + (["WBody"] if s1 is not None and s1["w"] is not None else [])
        if op == "bm25_drop":
            return ["DropLock", "DropBody"] if self.drop_locks else ["DropAll"]
        return []

    def relevant(self, ref):
        return ref.startswith('^BM25Idx("' + self.index + '"')


# ================================================================================================ m08 txn

class Txn(Family):
    """models/breadth-b/src/m08.rs:37-196 machine `txn` (module 08; CYP-I6.4/CYP-X6.5 ATOMIC, CYP-I6.3 CALLER,
    F-0806 MSG, F-0805 DUP). Rows: W (the caller's earlier row), C (the query's node), E (its literal edge); row
    values 0 absent, 1 at IVG's open level, 2 committed, 3 pending in the caller's transaction. Bound lifted:
    `queries >= 2`. A query step is Reset (when the last query is done) + Start(v) + Step + Step."""
    name = "txn"
    ATOMIC = "a failed write query leaves none of its rows"
    MSG = "an error's text matches what stayed written"
    DUP = "creating an existing edge between literal endpoints adds nothing and fails nothing"
    CALLER = "a failed write query keeps the caller's earlier work"

    def __init__(self, tag: str, w: str, c: str, edge: Optional[Tuple[str, str, str]], variant: str,
                 design: str = "as-built"):
        super().__init__()
        self.tag, self.wn, self.cn, self.edge, self.variant, self.design = tag, w, c, edge, variant, design
        self.name = f"txn[{design}]{tag}"
        self.node_root = None

    def bind(self, trace):
        self.node_root = trace["layouts"]["Graph_KG.nodes"]["data"]
        self.edge_root = trace["layouts"]["Graph_KG.rdf_edges"]["data"]

    def _present(self, store):
        ids = {str(r.get("node_id")) for r in store.rows("Graph_KG.nodes")}
        e = False
        if self.edge:
            e = any((r.get("s"), r.get("p"), r.get("o_id")) == self.edge for r in store.rows("Graph_KG.rdf_edges"))
        return self.wn in ids, self.cn in ids, e

    def init(self, store, trace):
        w, c, e = self._present(store)
        return {"caller_open": False, "w": 2 if w else 0, "c": 2 if c else 0, "e": 2 if e else 0, "ivg_level": 0,
                "pc": ["Idle"], "q_rows": 0, "q_caller": False}

    def _fail(self, t, v, dup, claims):
        if self.design == "control-rollback-all":
            for r in ("w", "c", "e"):
                if t[r] in (1, 3):
                    t[r] = 0
            t["caller_open"] = False
        else:
            for r in ("c", "e"):
                if t[r] == 1:
                    t[r] = 0
        t["ivg_level"] -= 1
        t["pc"] = ["DoneErr", v, dup, claims]

    @staticmethod
    def _ok(t, v):
        to = 3 if t["caller_open"] else 2
        for r in ("c", "e"):
            if t[r] == 1:
                t[r] = to
        t["ivg_level"] -= 1
        t["pc"] = ["DoneOk", v]

    def next(self, s, a):
        t = json.loads(json.dumps(s))
        quiet = s["pc"][0] in ("Idle", "DoneOk", "DoneErr")
        kind = a[0] if isinstance(a, tuple) else a
        if kind == "CallerBegin":
            if s["caller_open"] or not quiet or s["w"] != 0:
                return None
            t["caller_open"], t["w"] = True, 3
        elif kind in ("CallerCommit", "CallerRollback"):
            if not s["caller_open"] or not quiet:
                return None
            t["caller_open"] = False
            for r in ("w", "c", "e"):
                if t[r] == 3:
                    t[r] = 2 if kind == "CallerCommit" else 0
        elif kind == "Reset":
            if s["pc"][0] not in ("DoneOk", "DoneErr"):
                return None
            t["pc"] = ["Idle"]
        elif kind == "Start":
            if s["pc"][0] != "Idle":
                return None
            t["ivg_level"] += 1
            t["q_rows"], t["q_caller"] = 0, s["caller_open"]
            t["pc"] = ["Running", a[1], 0]
        elif kind == "Step":
            fail = a[1]
            if s["pc"][0] != "Running":
                return None
            _, v, stp = s["pc"]
            landed = 1
            if stp == 0:
                if fail:
                    return None
                if t["c"] == 0:
                    t["c"] = landed
                    t["q_rows"] |= 1
                t["pc"] = ["Running", v, 1]
            elif v == "LiteralEdge" and stp == 1:
                if fail:
                    return None
                exists = t["e"] != 0
                if exists and self.design != "reviewed":
                    self._fail(t, v, True, False)
                else:
                    if not exists:
                        t["e"] = landed
                        t["q_rows"] |= 2
                    self._ok(t, v)
            elif v == "Stepped" and stp == 1:
                if fail:
                    self._fail(t, v, False, self.design != "reviewed")
                else:
                    self._ok(t, v)
            else:
                return None
        else:
            return None
        return t

    def invariants(self):
        def atomic(s):
            if s["pc"][0] == "DoneErr":
                return (s["q_rows"] & 1 == 0 or s["c"] == 0) and (s["q_rows"] & 2 == 0 or s["e"] == 0)
            return True

        def msg(s):
            if s["pc"][0] == "DoneErr" and s["pc"][3]:
                return (s["q_rows"] & 1 != 0 and s["c"] != 0) or (s["q_rows"] & 2 != 0 and s["e"] != 0)
            return True
        return [(self.ATOMIC, atomic), (self.MSG, msg),
                (self.DUP, lambda s: not (s["pc"][0] == "DoneErr" and s["pc"][2]))]

    def action_properties(self):
        def caller(s, a, t):
            fails = s["pc"][0] == "Running" and t["pc"][0] == "DoneErr"
            return not fails or (t["caller_open"] == s["caller_open"] and t["w"] == s["w"])
        return [(self.CALLER, caller)]

    def obs(self, s):
        pc = s["pc"]
        err = (pc[0] == "DoneErr", bool(pc[2]) if pc[0] == "DoneErr" else False,
               bool(pc[3]) if pc[0] == "DoneErr" else False)
        return (s["caller_open"], s["w"] != 0, s["c"] != 0, s["e"] != 0, s["ivg_level"],
                "Running" if pc[0] == "Running" else ("Done" if pc[0] != "Idle" else "Idle"), err)

    def alpha(self, store, step):
        w, c, e = self._present(store)
        if step is None or step.get("query_of") != self.tag:
            pc, err = (self.S and self.obs(self.S)[5:7]) or ("Idle", (False, False, False))
        else:
            msg = step.get("error") or ""
            dup = any(x in msg for x in ("-119", "UNIQUE", "unique", "duplicate", "Duplicate"))
            claims = "steps before it are written" in msg
            pc, err = "Done", ((not step["ok"]), dup and not step["ok"], claims and not step["ok"])
        open_ = bool(step.get("caller_open")) if step is not None else False
        return (open_, w, c, e, int(step.get("tlevel_above_caller", 0)) if step is not None else 0, pc, err)

    def actions(self, step, seg, pre, post):
        tags = step.get("txn_fams") or []
        if self.tag not in tags:
            return []
        op = step["op"]
        if op == "caller-begin":
            return ["CallerBegin"]
        if op == "caller-commit":
            return ["CallerCommit"]
        if op == "caller-rollback":
            return ["CallerRollback"]
        if op == "execute_cypher" and step.get("query_of") == self.tag:
            acts = ["Reset"] if self.S["pc"][0] in ("DoneOk", "DoneErr") else []
            acts += [("Start", self.variant), ("Step", False)]
            if self.variant == "Stepped":
                acts.append(("Step", bool(step.get("read_step_fails"))))
            else:
                acts.append(("Step", False))
            return acts
        return []

    def relevant(self, ref):
        return self.node_root is not None and (ref.startswith(self.node_root + "(") or
                                               ref.startswith(self.edge_root + "("))


# ================================================================================================ m09 gate

class Gate(Family):
    """models/breadth-b/src/m09.rs:460-516 machine `gate` (module 09; NAT-I1/NAT-B1, F-0906). Node n's label in its
    rdf_labels row and in ^KG("label"); the native gate opens on the edge index alone (as built). Bound lifted:
    `writes <= 3` (within_bounds). The indexes are declared on the namespace (EnsureFull already happened at
    deploy): the initial state takes edge_idx/label_idx from the capture's dictionary read."""
    name = "gate"
    G_I1 = "NAT-I1: a native read answers labels as the SQL path does"

    def __init__(self, node: str, label: str, gk: str, design: str = "as-built"):
        super().__init__()
        self.node, self.label, self.gk, self.design = node, label, gk, design
        self.name = f"gate[{design}]"

    def bind(self, trace):
        self.label_root = trace["layouts"]["Graph_KG.rdf_labels"]["data"]
        self.facts = trace["meta"]["index_facts"]

    def _observe(self, store):
        row = any((str(r.get("s")), str(r.get("label")), r.get("graph_id") or "") == (self.node, self.label, "")
                  for r in store.rows("Graph_KG.rdf_labels"))
        kg = store.has("^KG", "label", self.gk, self.label, self.node)
        return row, kg

    def init(self, store, trace):
        row, kg = self._observe(store)
        return {"edge_idx": bool(self.facts["edge_idx"]), "label_idx": bool(self.facts["label_idx"]), "row": row,
                "kg": kg, "last": None}

    def next(self, s, a):
        t = dict(s)
        t["last"] = None
        if a == "EnsurePartial":
            if s["edge_idx"]:
                return None
            t["edge_idx"] = True
        elif a == "EnsureFull":
            if s["edge_idx"] and s["label_idx"]:
                return None
            t["edge_idx"], t["label_idx"], t["kg"] = True, True, s["row"]
        elif a in ("AddLabel", "RemoveLabel"):
            v = a == "AddLabel"
            if s["row"] == v:
                return None
            t["row"] = v
            if s["label_idx"] or not s["edge_idx"]:
                t["kg"] = v
        elif a == "Read":
            if self.design == "as-built":
                op = s["edge_idx"]
            elif self.design == "reviewed":
                op = s["edge_idx"] and s["label_idx"]
            else:
                op = True
            native = s["kg"] if op else s["row"]
            t["last"] = [op, native, s["row"]]
        else:
            return None
        return t

    def action_properties(self):
        return [(self.G_I1, lambda s, a, t: not (t["last"] is not None and t["last"][1] != t["last"][2]))]

    def obs(self, s):
        return (s["row"], s["kg"], tuple(s["last"]) if s["last"] else None)

    def alpha(self, store, step):
        row, kg = self._observe(store)
        last = None
        if step is not None and step["op"] == "read" and step["ok"]:
            r = step["reply"]
            last = (bool(r["native_answered"]), int(r["native_count"]) > 0, int(r["sql_count"]) > 0)
        return (row, kg, last)

    def actions(self, step, seg, pre, post):
        if step.get("family") != "gate" or not step["ok"]:
            return []
        return {"add-label": ["AddLabel"], "remove-label": ["RemoveLabel"], "read": ["Read"]}.get(step["op"], [])

    def relevant(self, ref):
        return ref.startswith(self.label_root + "(") or ref.startswith('^KG("label"')


# ================================================================================================ m10 cache

class Cache(Family):
    """models/breadth-b/src/m10.rs:99-303 machine `cache` (module 10; ALG-I4/ALG-B16.11/ALG-B2.19 P_HIT; F-1004).
    Base nodes a, b with edge a->b; edgeless node x (the PPR seed); one caller running PPR from [x]
    (Start -> Lookup -> Compute -> Put). Bounds lifted: `calls < 3`, `edge_writes < 2`, `next_id <= max_id`.
    x's id (fresh per creation) is not observable as the model numbers it; the projection keeps whether x exists.
    Trace-side bookkeeping: `ans`, what the last PPR call answered (x scored or not), checked against its reply."""
    name = "cache"
    P_HIT = ("a cached answer served equals a fresh computation of a state the call overlapped "
             "(ALG-I4, ALG-B16.11, ALG-B2.19)")

    def __init__(self, a: str, rel: str, b: str, x: str, gk: str, design: str = "as-built"):
        super().__init__()
        self.a, self.rel, self.b, self.x, self.gk, self.design = a, rel, b, x, gk, design
        self.name = f"cache[{design}]"

    def bind(self, trace):
        self.node_root = trace["layouts"]["Graph_KG.nodes"]["data"]
        self.tokmap: Dict[int, int] = {}

    def _tok(self, real):
        """The token's abstraction: its rank among the distinct values seen, in order (the machine compares tokens
        for equality and moves its token by one per token-raising write; IRIS may raise it by more than one in one
        write, e.g. an edgeless delete moved it by 2, b-10-live-cache)."""
        if real is None:
            return None
        if real not in self.tokmap:
            self.tokmap[real] = len(self.tokmap) + 1
        return self.tokmap[real]

    def _observe(self, store):
        edge = store.has("^KG", "out", self.gk, self.a, self.rel, self.b)
        x = any(str(r.get("node_id")) == self.x and (r.get("graph_id") or "") == ""
                for r in store.rows("Graph_KG.nodes"))
        ver = self._tok(_int(store.get("^KG", "__version"), 0))
        cache = []
        for k, v in sorted(store.under("^IVG.AlgoCache", self.gk).items()):
            if len(k) == 4 and "ppr" in str(k[2]).lower() and isinstance(v, tuple):
                cache.append((self._tok(_int(v[0])), self.x in str(v[1])))
        return edge, x, ver, cache

    def init(self, store, trace):
        edge, x, ver, cache = self._observe(store)
        return {"edge": edge, "x": x, "ver": ver, "nver": 0, "cache": [[c[0], 0, c[1]] for c in cache],
                "caller": ["Idle"], "ans": None}

    def _hit(self, s):
        if not s["cache"]:
            return None
        tok, nv, ans = s["cache"][0]
        node_ok = True if self.design == "as-built" else nv == s["nver"]
        return ans if tok == s["ver"] and node_ok else None

    def _node_write(self, u, delete):
        if delete:
            u["ver"] += 1
            u["cache"] = []
        if self.design == "reviewed":
            u["nver"] += 1

    def next(self, s, a):
        u = json.loads(json.dumps(s))
        if a == "WriteEdge":
            u["edge"], u["ver"] = not s["edge"], s["ver"] + 1
        elif a == "CreateX":
            if s["x"]:
                return None
            u["x"] = True
            self._node_write(u, False)
        elif a == "DeleteX":
            if not s["x"]:
                return None
            u["x"] = False
            self._node_write(u, True)
        elif a == "Start":
            if s["caller"][0] != "Idle":
                return None
            u["caller"] = ["Started", 1 << int(s["x"])]
        elif a == "Lookup":
            if s["caller"][0] != "Started":
                return None
            h = self._hit(s)
            if h is not None:
                u["caller"], u["ans"] = ["Idle"], h
            else:
                u["caller"] = ["Missed", s["ver"], s["nver"]]
        elif a == "Compute":
            if s["caller"][0] != "Missed":
                return None
            u["caller"] = ["Computed", s["caller"][1], s["caller"][2], s["x"]]
        elif a == "Put":
            if s["caller"][0] != "Computed":
                return None
            _, ver, nver, ans = s["caller"]
            u["cache"] = [[ver, nver, ans]]
            u["caller"], u["ans"] = ["Idle"], ans
        else:
            return None
        if a in ("WriteEdge", "CreateX", "DeleteX") and u["caller"][0] == "Started":
            u["caller"][1] |= 1 << int(u["x"])
        return u

    def action_properties(self):
        def p_hit(s, a, t):
            if a == "Lookup" and s["caller"][0] == "Started":
                h = self._hit(s)
                if h is not None:
                    seen = s["caller"][1] | (1 << int(s["x"]))
                    return bool(seen & (1 << int(h)))
            return True
        return [(self.P_HIT, p_hit)]

    def obs(self, s):
        return (s["edge"], s["x"], s["ver"], tuple((c[0], c[2]) for c in s["cache"]), s["caller"][0], s["ans"])

    def alpha(self, store, step):
        edge, x, ver, cache = self._observe(store)
        ans = self.S["ans"] if (step is None or step["op"] != "ppr") else bool(step["reply"].get("x_scored"))
        return (edge, x, ver, tuple(cache), "Idle", ans)

    def actions(self, step, seg, pre, post):
        if step.get("family") != "cache" or not step["ok"]:
            return []
        op = step["op"]
        if op == "ppr":
            s1 = self.next(self.next(self.S, "Start"), "Lookup")
            return ["Start", "Lookup"] + (["Compute", "Put"] if s1 is not None and s1["caller"][0] == "Missed" else [])
        return {"create_node": ["CreateX"], "delete_node": ["DeleteX"], "delete_edge": ["WriteEdge"],
                "create_edge": ["WriteEdge"]}.get(op, [])

    def relevant(self, ref):
        return ref.startswith("^IVG.AlgoCache") or ref.startswith('^KG("__version"') or \
            (self.node_root is not None and ref.startswith(self.node_root + "("))


# ================================================================================================ m07 leg

class Leg(Family):
    """models/breadth-b/src/m07.rs:406-537 machine `leg` (module 07; TXT-I7/SYS-I2 L_SCOPE, TXT-B8.3 L_LABEL;
    F-0705, F-0707). Up to three BM25 indexes, each holding one graph's documents (D default, A named) with a
    recorded graph (Build) or none (an index a first Insert created). Queries driven: CypherScoped(g, k) (USE GRAPH g
    CALL ivg.bm25.search(index k)) and CypherAll(k) (the same CALL without USE GRAPH); Fusion and Retrieve are not
    driven (Retrieve needs an embedder; Fusion's registry order also lists the stopword pseudo-index, F-0706, which the
    machine does not have). Bound lifted: `ops >= 3`."""
    name = "leg"
    L_SCOPE = "TXT-I7 a scoped BM25 answer holds only that graph's nodes"
    L_LABEL = "TXT-B8.3 rows of an index are never labelled with a graph they do not belong to"

    def __init__(self, names: List[str], graph_of_doc: Dict[str, str], gname: Dict[str, str], design="as-built"):
        super().__init__()
        self.names, self.graph_of_doc, self.gname, self.design = names, graph_of_doc, gname, design
        self.name = f"leg[{design}]"
        self.g_of_name = {v: k for k, v in gname.items()}

    def _seen(self, i):
        if i[1] is not None:
            return i[1]
        return "D" if self.design == "as-built" else None

    def init(self, store, trace):
        return {"idx": self._observe(store), "last": None}

    def next(self, s, a):
        t = json.loads(json.dumps(s))
        t["last"] = None
        kind = a[0]
        if kind == "Build":
            t["idx"][a[1]] = [a[2], a[2]]
        elif kind == "InsertCreate":
            if s["idx"][a[1]] is not None:
                return None
            t["idx"][a[1]] = [a[2], None]
        elif kind == "Drop":
            if s["idx"][a[1]] is None:
                return None
            t["idx"][a[1]] = None
        elif kind == "Ask":
            q = a[1]
            ans = None
            if q[0] == "CypherScoped":
                i = s["idx"][q[2]]
                if i is not None and not (self.design == "reviewed" and self._seen(i) != q[1]):
                    ans = (i[0], q[1])
            elif q[0] == "CypherAll":
                i = s["idx"][q[1]]
                if i is not None and self._seen(i) is not None:
                    ans = (i[0], self._seen(i))
            t["last"] = None if ans is None else [list(q), ans[0], ans[1]]
        else:
            return None
        return t

    def action_properties(self):
        def scope(s, a, t):
            L = t["last"]
            if L and L[0][0] == "CypherScoped":
                return L[1] == L[0][1]
            return True

        def label(s, a, t):
            L = t["last"]
            return not L or L[1] == L[2]
        return [(self.L_SCOPE, scope), (self.L_LABEL, label)]

    def obs(self, s):
        return (tuple(tuple(i) if i else None for i in s["idx"]),
                None if s["last"] is None else (tuple(s["last"][0]), s["last"][1], s["last"][2]))

    def _observe(self, store):
        out = []
        for nm in self.names:
            if not store.has("^BM25Idx", nm, "cfg", "N"):
                out.append(None)
                continue
            docs = {k[3] for k in store.under("^BM25Idx", nm, "len") if len(k) == 4}
            gs = sorted({self.graph_of_doc.get(d, "?") for d in docs})
            holds = gs[0] if len(gs) == 1 else "/".join(gs)
            rec = store.get("^BM25Idx", nm, "cfg", "graph") if store.has("^BM25Idx", nm, "cfg", "graph") else None
            rec = None if rec is None else self.g_of_name.get(str(rec), "?" + str(rec))
            out.append([holds, rec])
        return out

    def alpha(self, store, step):
        idx = self._observe(store)
        last = None
        if step is not None and step["op"].startswith("ask-") and step["ok"]:
            r = step["reply"]
            q = tuple(step["query"])
            gs = sorted({self.graph_of_doc[d] for d in r["docs"]})
            h = gs[0] if len(gs) == 1 else ("/".join(gs) if gs else None)
            lbl = q[1] if q[0] == "CypherScoped" else r.get("label")
            last = None if h is None else (q, h, lbl)
        return (tuple(tuple(i) if i else None for i in idx), last)

    def actions(self, step, seg, pre, post):
        if step.get("family") != "leg":
            return []
        op = step["op"]
        if op == "bm25_build":
            return [("Build", step["slot"], step["g"])]
        if op == "bm25_insert":
            return [("InsertCreate", step["slot"], step["g"])]
        if op == "bm25_drop":
            return [("Drop", step["slot"])]
        if op.startswith("ask-"):
            return [("Ask", tuple(step["query"]))]
        return []

    def relevant(self, ref):
        return any(ref.startswith('^BM25Idx("' + n + '"') for n in self.names)


# ================================================================================================ m10 degree

class Degree(Family):
    """models/breadth-b/src/m10.rs:653-697 machine `degree` (module 10; I_HANDSHAKE; F-1007). k parallel a->b edges
    (multigraph mode) and one c->b; DegreeCentralityJson's out-degree from Adj.Degree's multiplicity, in-degree one
    per source (as built). Bound lifted: `ab >= 3`. Trace-side observation action `Read`: records the machine's own
    `sums(s)` (the invariant's computation) so a degree_centrality reply can be compared with it; it changes no
    machine state component."""
    name = "degree"
    I_HANDSHAKE = "out-degrees and in-degrees each sum to the number of edges (parallel edges count)"

    def __init__(self, g, a, rel, b, c, design="as-built"):
        super().__init__()
        self.g, self.a, self.rel, self.b, self.c, self.design = g, a, rel, b, c, design
        self.name = f"degree[{design}]"

    def bind(self, trace):
        self.edge_root = trace["layouts"]["Graph_KG.rdf_edges"]["data"]

    def sums(self, s):
        edges = s["ab"] + int(s["cb"])
        out = s["ab"] + int(s["cb"])
        in_b = (int(s["ab"] > 0) + int(s["cb"])) if self.design == "as-built" else s["ab"] + int(s["cb"])
        return (out, in_b, edges)

    def _observe(self, store):
        rows = [r for r in store.rows("Graph_KG.rdf_edges") if (r.get("graph_id") or "") == self.g]
        ab = sum(1 for r in rows if (r.get("s"), r.get("p"), r.get("o_id")) == (self.a, self.rel, self.b))
        cb = any((r.get("s"), r.get("p"), r.get("o_id")) == (self.c, self.rel, self.b) for r in rows)
        return ab, cb

    def init(self, store, trace):
        ab, cb = self._observe(store)
        return {"ab": ab, "cb": cb, "read": None}

    def next(self, s, a):
        u = dict(s)
        u["read"] = None
        if a == "AddAB":
            u["ab"] += 1
        elif a == "DelAB":
            if s["ab"] == 0:
                return None
            u["ab"] -= 1
        elif a == "AddCB":
            if s["cb"]:
                return None
            u["cb"] = True
        elif a == "Read":
            u["read"] = list(self.sums(s))
        else:
            return None
        return u

    def invariants(self):
        def hs(s):
            o, i, e = self.sums(s)
            return o == e and i == e
        return [(self.I_HANDSHAKE, hs)]

    def obs(self, s):
        return (s["ab"], s["cb"], tuple(s["read"]) if s["read"] else None)

    def alpha(self, store, step):
        ab, cb = self._observe(store)
        read = None
        if step is not None and step["op"] == "degree_centrality" and step["ok"]:
            r = step["reply"]
            read = (int(r["out_sum"]), int(r["in_sum"]), ab + int(cb))
        return (ab, cb, read)

    def actions(self, step, seg, pre, post):
        if step.get("family") != "degree" or not step["ok"]:
            return []
        return {"create-ab": ["AddAB"], "create-cb": ["AddCB"], "delete-ab": ["DelAB"],
                "degree_centrality": ["Read"]}.get(step["op"], [])

    def relevant(self, ref):
        return ref.startswith(self.edge_root + "(")


# ================================================================================================ m08 readonly

class ReadOnly(Family):
    """models/breadth-b/src/m08.rs:346-389 machine `readonly` (module 08; CYP-I8.6; F-0814, F-0815). Calls made in
    read-only mode: a read, a write clause (refused by writes_cypher's text check), a dotted function pasting
    Graph_KG.Txn_Begin into the SQL (opens a transaction level), an AQL query whose collection name carries a SET
    (execute_aql has no read_only). State: rows changed, $TLEVEL, answered, refused. Bound lifted: `calls >= 3`."""
    name = "readonly"
    RO = "a call in read-only mode changes no data and opens no transaction"

    def __init__(self, data_nodes, design="as-built"):
        super().__init__()
        self.data_nodes, self.design = data_nodes, design
        self.name = f"readonly[{design}]"
        self.seen = {"answered": 0, "refused": 0}

    def bind(self, trace):
        self.props_root = trace["layouts"]["Graph_KG.rdf_props"]["data"]
        self.nodes_root = trace["layouts"]["Graph_KG.nodes"]["data"]

    def _data(self, store):
        pwn = sum(1 for r in store.rows("Graph_KG.rdf_props") if str(r.get("key")).startswith("pwn"))
        made = sum(1 for r in store.rows("Graph_KG.nodes") if str(r.get("node_id")) in self.data_nodes)
        return pwn + made

    def init(self, store, trace):
        return {"data": self._data(store), "tlevel": 0, "answered": 0, "refused": 0}

    def next(self, s, a):
        t = dict(s)
        text_check = self.design != "reviewed-no-text-check"
        reviewed = self.design != "as-built"
        k = a[1]
        if k == "Read":
            t["answered"] += 1
        elif k == "WriteClause":
            if text_check:
                t["refused"] += 1
            else:
                t["data"] += 1
        elif k == "DottedTxnBegin":
            if reviewed:
                t["refused"] += 1
            else:
                t["tlevel"] += 1
                t["answered"] += 1
        elif k == "AqlWrite":
            if reviewed and text_check:
                t["refused"] += 1
            else:
                t["data"] += 1
        else:
            return None
        return t

    def invariants(self):
        return [(self.RO, lambda s: s["data"] == 0 and s["tlevel"] == 0)]

    def obs(self, s):
        # data projected to "some row changed": the machine counts writing calls, the store shows rows (one AQL
        # write may set several rows); the invariant reads only data == 0
        return (s["data"] > 0, s["tlevel"], s["answered"], s["refused"])

    def alpha(self, store, step):
        if step is not None and step.get("family") == "readonly":
            # the machine counts read answers and refusals; an AQL write that ran is counted in `data` only
            if not step["ok"]:
                self.seen["refused"] += 1
            elif step.get("kind") != "AqlWrite":
                self.seen["answered"] += 1
        tl = self.S["tlevel"] if step is None or step.get("tlevel") is None else int(step["tlevel"])
        return (self._data(store) > 0, tl, self.seen["answered"], self.seen["refused"])

    def actions(self, step, seg, pre, post):
        if step.get("family") != "readonly":
            return []
        return [("Call", step["kind"])]

    def relevant(self, ref):
        return ref.startswith(self.props_root + "(") or ref.startswith(self.nodes_root + "(")
