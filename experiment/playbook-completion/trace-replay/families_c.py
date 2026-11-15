"""Breadth lane C explorer families (models/breadth-c/src/*.rs at pin 3eaa79cf), transcribed as executable machines
for trace replay (modules 15-18). Same conventions as families_a.py: the Rust file and lines are cited per class (the
model crate is not modified); `obs` is the part of the state the replayed store, the archive file or the step's
reply determines; ghost components evolve only through next() and are what the invariants read. Explorer
exploration bounds (array sizes, attempt counters) are lifted where a real trace is longer; each lift is named.
"""
from __future__ import annotations

import json
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from trlib import At, Family, Store, stores_at_units

# ================================================================================================ helpers


def zip_ndjson(path: str, member: str) -> List[Dict]:
    with zipfile.ZipFile(path) as z:
        if member not in z.namelist():
            return []
        return [json.loads(x) for x in z.read(member).decode().splitlines() if x.strip()]


def zip_names(path: str) -> List[str]:
    with zipfile.ZipFile(path) as z:
        return z.namelist()


# ================================================================================================ restore (M5)

R_NONE, R_LIVE, R_TOMB = "None", "Live", "Tomb"


class SnpRestore(Family):
    """models/breadth-c/src/restore.rs:28-150 (module 18; F-1801, HD-1801; SNP-I3.6, SNP-B3.7, SYS-I5). Revision
    sequence numbers 1..N: per seq the record content (None/Live/Tomb), the LedgerRevision row, head, redactedRev
    marks, one idempotency binding, at most one archive. Bound lifted: N = 3 in the crate, N = 6 here (the pin's
    genesis takes seq 1 and the redaction appends its own revision). The `restores >= 1` and
    `refused_commits >= 1` exploration bounds are kept: the scenario restores once and is refused once."""
    name = "snp_restore"
    source = "models/breadth-c/src/restore.rs:28-150"
    N = 6
    ONE = "one history"
    NOCONTENT = "a redacted record holds no content"
    GROWS = "the ledger only grows"

    def __init__(self, key: str, design: str = "as-built"):
        super().__init__()
        self.key, self.design = key, design
        self.name = f"snp_restore[{design}]"
        self._archive = None
        self._restores: set = set()
        self._refused: set = set()

    # --- machine
    def _empty(self):
        return {"recs": [R_NONE] * self.N, "revs": [False] * self.N, "head": 0, "marks": [False] * self.N, "idem": 0}

    def init(self, store, trace):
        return {"live": self._ledger(store), "archive": None, "restores": 0, "refused_commits": 0,
                "redacted_ever": [False] * self.N, "committed_after_restore": False}

    def next(self, s, a):
        t = json.loads(json.dumps(s))
        l = t["live"]
        kind = a[0]
        if kind == "Commit":
            keyed = a[1]
            seq = s["live"]["head"] + 1
            if seq > self.N:
                return None
            if keyed and s["live"]["idem"] != 0:
                return None
            i = seq - 1
            if s["live"]["revs"][i]:
                if s["refused_commits"] >= 1:
                    return None
                t["refused_commits"] += 1
                return t
            l["recs"][i] = R_LIVE
            l["revs"][i] = True
            l["head"] = seq
            if keyed:
                l["idem"] = seq
            if s["restores"] > 0:
                t["committed_after_restore"] = True
        elif kind == "Save":
            if s["archive"] is not None:
                return None
            t["archive"] = json.loads(json.dumps(s["live"]))
        elif kind == "Redact":
            i = a[1] - 1
            if s["live"]["recs"][i] != R_LIVE:
                return None
            l["recs"][i] = R_TOMB
            l["marks"][i] = True
            t["redacted_ever"][i] = True
        elif kind == "Restore":
            ar = s["archive"]
            if ar is None or s["restores"] >= 1:
                return None
            t["restores"] += 1
            l = t["live"]
            if self.design == "as-built":
                for i in range(self.N):
                    if ar["recs"][i] != R_NONE:
                        l["recs"][i] = ar["recs"][i]
                    if ar["revs"][i]:
                        l["revs"][i] = True
                    if ar["marks"][i]:
                        l["marks"][i] = True
                l["head"] = ar["head"]
                if ar["idem"] != 0:
                    l["idem"] = ar["idem"]
            else:
                live = s["live"]
                prefix = live["head"] <= ar["head"] and all(
                    live["revs"][i] == ar["revs"][i] and (live["recs"][i] == ar["recs"][i] or
                                                          (live["recs"][i] == R_TOMB and ar["recs"][i] == R_LIVE))
                    for i in range(live["head"]))
                if not prefix:
                    u = json.loads(json.dumps(s))
                    u["restores"] = s["restores"] + 1
                    return u
                keep = self.design == "reviewed"
                t["live"] = json.loads(json.dumps(ar))
                if keep:
                    for i in range(self.N):
                        if live["marks"][i]:
                            t["live"]["marks"][i] = True
                            t["live"]["recs"][i] = R_TOMB
        else:
            return None
        return t

    def invariants(self):
        def one(s):
            l = s["live"]
            return all(i < l["head"] or (l["recs"][i] == R_NONE and not l["revs"][i]) for i in range(self.N)) \
                and l["idem"] <= l["head"]

        def nocontent(s):
            return all(not (s["live"]["marks"][i] or s["redacted_ever"][i]) or s["live"]["recs"][i] != R_LIVE
                       for i in range(self.N))
        return [(self.ONE, one), (self.NOCONTENT, nocontent)]

    def action_properties(self):
        return [(self.GROWS, lambda a, _x, b: b["live"]["head"] >= a["live"]["head"])]

    @staticmethod
    def _lt(l):
        return (tuple(l["recs"]), tuple(l["revs"]), l["head"], tuple(l["marks"]), l["idem"])

    def obs(self, s):
        return (self._lt(s["live"]), None if s["archive"] is None else self._lt(s["archive"]), s["restores"],
                s["refused_commits"])

    # --- abstraction
    def _ledger(self, store: Store):
        l = self._empty()
        recs: Dict[int, List[Any]] = {}
        for k, v in store.under("^IVG.Ledger", "rec").items():
            if len(k) == 4 and k[2].lstrip("-").isdigit():
                recs.setdefault(int(k[2]), []).append(v)
        for seq, vs in recs.items():
            if 1 <= seq <= self.N:
                tomb = [isinstance(v, tuple) and v and v[0] == "redacted" for v in vs]
                l["recs"][seq - 1] = R_TOMB if all(tomb) else R_LIVE
        for k in store.under("^Graph.KG.LedgerRevisionD"):
            if len(k) == 2 and k[1].isdigit() and 1 <= int(k[1]) <= self.N:
                l["revs"][int(k[1]) - 1] = True
        h = store.get("^IVG.Ledger", "head")
        l["head"] = int(h) if h not in (None, "") else 0
        for k in store.under("^IVG.Ledger", "redactedRev"):
            if len(k) == 3 and k[2].isdigit() and 1 <= int(k[2]) <= self.N:
                l["marks"][int(k[2]) - 1] = True
        b = store.get("^IVG.Ledger", "idem", self.key)
        if b is not None:
            l["idem"] = int(b[0] if isinstance(b, tuple) else b)
        return l

    def _archive_ledger(self, path: str):
        """The archive's ledger, abstracted the same way from globals/IVG.Ledger.ndjson and the revision rows'
        global (snapshot.py:399-406, 1612-1652: {"k": subscripts, "v": str(value)})."""
        l = self._empty()
        recs: Dict[int, List[str]] = {}
        for x in zip_ndjson(path, "globals/IVG.Ledger.ndjson"):
            k, v = [str(y) for y in x["k"]], x.get("v")
            if k[:1] == ["rec"] and len(k) == 3 and k[1].isdigit():
                recs.setdefault(int(k[1]), []).append(str(v))
            elif k == ["head"]:
                l["head"] = int(v)
            elif k[:1] == ["redactedRev"] and len(k) == 2 and k[1].isdigit():
                l["marks"][int(k[1]) - 1] = True
            elif k == ["idem", self.key]:
                digits = "".join(ch for ch in str(v)[:12] if ch.isdigit())
                l["idem"] = int(self._lb_first_int(v) or digits or 0)
        for seq, vs in recs.items():
            if 1 <= seq <= self.N:
                l["recs"][seq - 1] = R_TOMB if all("redacted" in v[:24] for v in vs) else R_LIVE
        for x in zip_ndjson(path, "globals/Graph.KG.LedgerRevisionD.ndjson"):
            k = [str(y) for y in x["k"]]
            if len(k) == 1 and k[0].isdigit() and 1 <= int(k[0]) <= self.N:
                l["revs"][int(k[0]) - 1] = True
        return l

    @staticmethod
    def _lb_first_int(v) -> Optional[int]:
        """The first element of a $LB written by str(bytes) (the archive's text of a list value)."""
        try:
            import ast
            import iris
            raw = ast.literal_eval(v) if isinstance(v, str) and v.startswith(("b'", 'b"')) else None
            if raw is None:
                return None
            return int(iris.IRISList(raw).get(1))
        except Exception:  # noqa: BLE001
            return None

    def alpha(self, store, step):
        live = self._ledger(store)
        if step is not None:
            if step["op"] == "save_snapshot" and step["ok"]:
                self._archive = self._archive_ledger(step["path"])
            if step["op"] == "restore_snapshot":
                self._restores.add(step["i"])
            if step["op"] == "ledger-commit" and not step["ok"]:
                self._refused.add(step["i"])
        return (self._lt(live), None if self._archive is None else self._lt(self._archive), len(self._restores),
                len(self._refused))

    def actions(self, step, seg, pre, post):
        op = step["op"]
        if op == "ledger-commit":
            return [("Commit", bool(step.get("keyed")))]
        if op == "save_snapshot" and step["ok"]:
            return [("Save",)]
        if op == "redact" and step["ok"]:
            # restore.rs's Redact appends no revision; the pin's redaction commits its own (LedgerRedact Final):
            # mapped as an unkeyed Commit after the tombstoning (a model gap, stated in the report)
            return [("Redact", s) for s in step["redact_seqs"]] + [("Commit", False)]
        if op == "restore_snapshot" and step["ok"]:
            return [("Restore",)]
        return []

    def relevant(self, ref):
        return ref.startswith(('^IVG.Ledger("rec"', '^IVG.Ledger("head"', '^IVG.Ledger("redactedRev"',
                               '^IVG.Ledger("idem"', "^Graph.KG.LedgerRevisionD("))


# ================================================================================================ snapcut (M4)


class SnpCut(Family):
    """models/breadth-c/src/snapcut.rs:26-160 (module 18; HD-1802, F-C1801, SNP-Q1.17). Node a always present; node b
    and edge a->b; one writer transaction (node first, then the edge); the exporter reads the nodes table, then the
    edges table. The `writer_txns < 2` and `saves < 1` exploration bounds are kept (one writer transaction, one save)."""
    name = "snp_cut"
    source = "models/breadth-c/src/snapcut.rs:26-160"
    COMMITTED = "the archive is a committed state"
    DANGLING = "the archive has no dangling edge"

    def __init__(self, g: str, a: str, b: str, p: str, design: str = "as-built"):
        super().__init__()
        self.g, self.a, self.b, self.p, self.design = g, a, b, p, design
        self.name = f"snp_cut[{design}]"
        self._x = "Idle"
        self._arch = (False, False)
        self.node_root = self.edge_root = None

    def bind(self, trace):
        self.node_root = trace["layouts"]["Graph_KG.nodes"]["data"]
        self.edge_root = trace["layouts"]["Graph_KG.rdf_edges"]["data"]

    @staticmethod
    def _idx(d):
        return (int(d[0]) << 1) | int(d[1])

    def _cur(self, store):
        nb = any(str(r.get("node_id")) == self.b and (r.get("graph_id") or "") == self.g
                 for r in store.rows("Graph_KG.nodes"))
        ab = any((r.get("s"), r.get("p"), r.get("o_id"), r.get("graph_id") or "") == (self.a, self.p, self.b, self.g)
                 for r in store.rows("Graph_KG.rdf_edges"))
        return (nb, ab)

    def init(self, store, trace):
        d = self._cur(store)
        return {"cur": list(d), "committed": list(d), "w": "Idle", "x": "Idle", "arch_node_b": False,
                "arch_edge": False, "seen": 0, "gate_export": False, "gate_writer": False, "writer_txns": 0,
                "saves": 0, "created_committed": False}

    def _writer_gate(self):
        return self.design == "reviewed"

    def _export_gate(self):
        return self.design in ("reviewed", "control-writer-skips-gate")

    def next(self, s, a):
        t = json.loads(json.dumps(s))
        kind = a[0]
        if kind == "WriterFirst":
            create = a[1]
            if s["w"] != "Idle" or s["writer_txns"] >= 2:
                return None
            if self._writer_gate() and s["gate_export"]:
                return None
            if create:
                if s["cur"][0]:
                    return None
                t["cur"][0] = True
                t["w"] = "CreatedNode"
            else:
                if not s["cur"][1]:
                    return None
                t["cur"][1] = False
                t["w"] = "DeletedEdge"
            t["gate_writer"] = self._writer_gate()
            t["writer_txns"] += 1
        elif kind == "WriterSecond":
            if s["w"] == "CreatedNode":
                t["cur"][1], t["w"] = True, "CreatedEdge"
            elif s["w"] == "DeletedEdge":
                t["cur"][0], t["w"] = False, "DeletedNode"
            else:
                return None
        elif kind == "WriterEnd":
            commit = a[1]
            if s["w"] not in ("CreatedEdge", "DeletedNode", "CreatedNode", "DeletedEdge"):
                return None
            if commit:
                if s["w"] not in ("CreatedEdge", "DeletedNode"):
                    return None
                t["committed"] = list(s["cur"])
                if s["w"] == "CreatedEdge":
                    t["created_committed"] = True
            else:
                t["cur"] = list(s["committed"])
            t["w"], t["gate_writer"] = "Idle", False
            if s["x"] in ("Started", "NodesRead"):
                t["seen"] |= 1 << self._idx(t["committed"])
        elif kind == "SaveStart":
            if s["x"] != "Idle" or s["saves"] >= 1:
                return None
            if self._export_gate() and s["gate_writer"]:
                return None
            t["gate_export"] = self._export_gate()
            t["x"] = "Started"
            t["saves"] += 1
            t["seen"] = 1 << self._idx(s["committed"])
        elif kind == "SaveReadNodes":
            if s["x"] != "Started":
                return None
            t["arch_node_b"], t["x"] = s["cur"][0], "NodesRead"
        elif kind == "SaveReadEdges":
            if s["x"] != "NodesRead":
                return None
            t["arch_edge"], t["x"], t["gate_export"] = s["cur"][1], "Done", False
        else:
            return None
        return t

    def invariants(self):
        return [(self.COMMITTED, lambda s: s["x"] != "Done" or
                 bool(s["seen"] & (1 << self._idx((s["arch_node_b"], s["arch_edge"]))))),
                (self.DANGLING, lambda s: s["x"] != "Done" or not s["arch_edge"] or s["arch_node_b"])]

    def obs(self, s):
        return (tuple(s["cur"]), s["x"], s["arch_node_b"], s["arch_edge"])

    def alpha(self, store, step):
        if step is not None and step["op"] == "save_snapshot" and step["ok"]:
            nodes = zip_ndjson(step["path"], "sql/Graph_KG_nodes.ndjson")
            edges = zip_ndjson(step["path"], "sql/Graph_KG_rdf_edges.ndjson")
            nb = any(x.get("node_id") == self.b and (x.get("graph_id") or "") == self.g for x in nodes)
            ab = any((x.get("s"), x.get("p"), x.get("o_id"), x.get("graph_id") or "") == (self.a, self.p, self.b, self.g)
                     for x in edges)
            self._x, self._arch = "Done", (nb, ab)
        return (self._cur(store), self._x, self._arch[0], self._arch[1])

    OPS = {"writer-create-node": [("WriterFirst", True)], "writer-create-edge": [("WriterSecond",)],
           "writer-rollback": [("WriterEnd", False)], "writer-commit": [("WriterEnd", True)],
           "save_snapshot": [("SaveStart",), ("SaveReadNodes",), ("SaveReadEdges",)]}

    def actions(self, step, seg, pre, post):
        return self.OPS.get(step["op"], []) if step["ok"] else []

    def relevant(self, ref):
        return bool(self.node_root) and (ref.startswith(self.node_root + "(") or ref.startswith(self.edge_root + "("))


# ================================================================================================ unit (M2)


class Unit(Family):
    """models/breadth-c/src/unit.rs:20-140 (module 16; F-1601, F-1610). A two-statement unit of work: Bolt explicit
    transaction (BEGIN, RUN w1, RUN w2, COMMIT | ROLLBACK, the driver's managed retry) or the HTTP
    POST /db/neo4j/tx/commit with two statements. The `attempts < 2` bound is kept (one driver retry)."""
    name = "unit"
    source = "models/breadth-c/src/unit.rs:20-140"
    ATOMIC = "unit atomicity"
    ONCE = "at most once"

    def __init__(self, entry: str, w1_label: str, w2_label: str, design: str = "as-built"):
        super().__init__()
        self.entry, self.l1, self.l2, self.design = entry, w1_label, w2_label, design
        self.name = f"unit[{design}]{entry}"
        self.label_root = None

    def bind(self, trace):
        self.label_root = trace["layouts"]["Graph_KG.rdf_labels"]["data"]

    def init(self, store, trace):
        return {"phase": "Idle", "w1": 0, "w2": 0, "buf1": False, "buf2": False, "last_failed": False,
                "attempts": 0, "committed_units": 0}

    def _per_stmt(self):
        return self.design == "as-built"

    def _discard(self, s, t):
        if self.design == "control-rollback-keeps-first-write" and s["buf1"]:
            t["w1"] += 1
        t["buf1"] = t["buf2"] = False

    def next(self, s, a):
        t = dict(s)
        kind = a[0]
        http = self.entry == "http"
        if kind == "Begin":
            if s["phase"] != "Idle" or s["attempts"] > 0:
                return None
            t["phase"], t["attempts"] = "Open", 1
        elif kind == "Run1":
            if s["phase"] != "Open":
                return None
            if self._per_stmt():
                t["w1"] += 1
            else:
                t["buf1"] = True
            t["phase"] = "AfterW1"
        elif kind == "Run2":
            ok = a[1]
            if s["phase"] != "AfterW1":
                return None
            if ok:
                if self._per_stmt():
                    t["w2"] += 1
                else:
                    t["buf2"] = True
                t["phase"] = "Ready"
                if http:
                    if not self._per_stmt():
                        t["w1"] += int(s["buf1"])
                        t["w2"] += 1
                        t["buf1"] = t["buf2"] = False
                    t["committed_units"] += 1
                    t["phase"] = "Idle"
            elif http:
                self._discard(s, t)
                t["last_failed"], t["phase"] = True, "Idle"
            else:
                t["phase"] = "Failed"
        elif kind == "Commit":
            if s["phase"] != "Ready" or http:
                return None
            if not self._per_stmt():
                t["w1"] += int(s["buf1"])
                t["w2"] += int(s["buf2"])
                t["buf1"] = t["buf2"] = False
            t["committed_units"] += 1
            t["phase"] = "Idle"
        elif kind == "Rollback":
            if http or s["phase"] not in ("AfterW1", "Ready", "Failed"):
                return None
            self._discard(s, t)
            t["last_failed"] = s["phase"] == "Failed"
            t["phase"] = "Idle"
        elif kind == "DriverRetry":
            if s["phase"] != "Idle" or not s["last_failed"] or s["attempts"] >= 2:
                return None
            t["attempts"] += 1
            t["last_failed"], t["phase"] = False, "Open"
        else:
            return None
        return t

    def invariants(self):
        return [(self.ATOMIC, lambda s: not (s["phase"] == "Idle" and s["w1"] != s["w2"])),
                (self.ONCE, lambda s: s["w1"] <= 1 and s["w2"] <= 1)]

    def obs(self, s):
        return (s["w1"], s["w2"])

    def _count(self, store, label):
        return len({r.get("s") for r in store.rows("Graph_KG.rdf_labels") if r.get("label") == label})

    def alpha(self, store, step):
        return (self._count(store, self.l1), self._count(store, self.l2))

    def actions(self, step, seg, pre, post):
        if step.get("unit") != self.entry:
            return []
        acts = step.get("model") or []
        if self.entry == "http" and acts:
            # one request: checkpoint the first statement's own commit (unit.rs Run1 as built commits it)
            cps = [(u, st) for u, st in stores_at_units(pre, seg) if u["kind"] == "txn" and u["committed"]]
            out = []
            for a in acts:
                if tuple(a) == ("Run1",) and cps:
                    out.append(At(tuple(a), self.alpha(cps[0][1], None)))
                else:
                    out.append(tuple(a))
            return out
        return [tuple(a) for a in acts]

    def relevant(self, ref):
        return bool(self.label_root) and ref.startswith(self.label_root + "(")


# ================================================================================================ retry (M1)


class Retry(Family):
    """models/breadth-c/src/retry.rs:22-170 (modules 16/17; HD-1603, HD-1702, F-C1703). One client call through
    IVGClient._post and the Cypher HTTP server's _run_cypher, with ambiguous acknowledgements. Bounds as the crate
    (client_max 3 = IVGClient max_retries, server_max 2 = _run_cypher's range(2))."""
    name = "retry"
    source = "models/breadth-c/src/retry.rs:22-170"
    ONCE = "at most once"
    DEFINITE = "a definite failure means nothing was applied"

    def __init__(self, op: str, marker: str, design: str = "as-built"):
        super().__init__()
        self.op, self.marker, self.design = op, marker, design
        self.name = f"retry[{design}]{marker}"
        self.client_max, self.server_max = 3, 2
        self.prop_root = None

    def bind(self, trace):
        self.prop_root = trace["layouts"]["Graph_KG.rdf_props"]["data"]

    def init(self, store, trace):
        return {"op": self.op, "client": "Ready", "client_attempts": 0, "server": "Idle", "server_attempts": 0,
                "applied": self._applied(store), "retried_after_timeout": False}

    def _client_retries_ambiguous(self, op):
        return True if self.design in ("as-built", "control-client-retries") else op == "Read"

    def _server_retries_after_send(self, op):
        return True if self.design in ("as-built", "control-server-retries") else op == "Read"

    def next(self, s, a):
        t = dict(s)
        kind = a[0]
        if kind == "Send":
            delivered = a[1]
            if s["client"] != "Ready" or s["client_attempts"] >= self.client_max:
                return None
            t["client_attempts"] += 1
            if delivered:
                t["client"], t["server"], t["server_attempts"] = "Waiting", "Executing", 0
            elif t["client_attempts"] >= self.client_max:
                t["client"] = "Done:Failed"
        elif kind == "Exec":
            pre_send, committed, ack = a[1], a[2], a[3]
            if s["server"] != "Executing" or s["server_attempts"] >= self.server_max:
                return None
            t["server_attempts"] += 1
            more = t["server_attempts"] < self.server_max
            if pre_send:
                t["server"] = "Executing" if more else "Replied:False"
                return t
            if committed and s["op"] == "Write":
                t["applied"] += 1
            if ack:
                t["server"] = f"Replied:{committed or s['op'] == 'Read'}"
            elif self._server_retries_after_send(s["op"]) and more:
                t["server"] = "Executing"
            elif self.design in ("as-built", "control-server-retries") or s["op"] == "Read":
                t["server"] = "Replied:False"
            else:
                t["server"] = "Lost"
        elif kind == "Reply":
            delivered = a[1]
            if s["server"].startswith("Replied:"):
                answer = s["server"].endswith("True")
            elif s["server"] == "Lost":
                answer = None
            else:
                return None
            if s["client"] != "Waiting":
                return None
            t["server"] = "Idle"
            if delivered:
                t["client"] = "Done:" + ({True: "Success", False: "Failed", None: "Unknown"}[answer])
            elif self._client_retries_ambiguous(s["op"]) and s["client_attempts"] < self.client_max:
                t["client"], t["retried_after_timeout"] = "Ready", True
            elif self._client_retries_ambiguous(s["op"]):
                t["client"] = "Done:Failed"
            else:
                t["client"] = "Done:Unknown"
        else:
            return None
        return t

    def invariants(self):
        return [(self.ONCE, lambda s: s["applied"] <= 1),
                (self.DEFINITE, lambda s: not (s["client"] == "Done:Failed" and s["applied"] > 0))]

    def obs(self, s):
        c = s["client"] if s["client"].startswith("Done") else "pending"
        return (s["applied"], c)

    def _applied(self, store):
        return sum(1 for r in store.rows("Graph_KG.rdf_props")
                   if r.get("key") == "marker" and str(r.get("val")) == self.marker)

    def alpha(self, store, step):
        client = self.S["client"] if self.S is not None and self.S["client"].startswith("Done") else "pending"
        if step is not None and step.get("op") == "IVGClient.execute_cypher" and step.get("marker") == self.marker:
            client = "Done:Success" if step["ok"] else ("Done:Failed" if "IVGClientError" in (step.get("error") or "")
                                                        else "Done:Unknown")
        return (self._applied(store), client)

    def actions(self, step, seg, pre, post):
        if step.get("op") != "IVGClient.execute_cypher" or step.get("marker") != self.marker:
            return []
        # the harness transport's log: per request, whether it reached the app and whether its reply was delivered;
        # each request's server attempt is matched to the committed transaction the journal shows for it
        cps = [(u, st) for u, st in stores_at_units(pre, seg) if u["kind"] == "txn" and u["committed"]]
        out = []
        k = 0
        for ev in step["transport"]:
            out.append(("Send", ev["delivered"]))
            if not ev["delivered"]:
                continue
            committed = ev.get("status") == 200
            if committed and k < len(cps):
                out.append(At(("Exec", False, True, True), (self.alpha(cps[k][1], None)[0], "pending")))
                k += 1
            else:
                out.append(("Exec", False, committed, True))
            out.append(("Reply", ev["reply_delivered"]))
        return out

    def relevant(self, ref):
        return bool(self.prop_root) and ref.startswith(self.prop_root + "(")
