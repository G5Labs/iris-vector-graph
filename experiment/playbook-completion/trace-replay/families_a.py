"""Breadth lane A explorer families (models/breadth-a/src/*.rs at pin 3eaa79cf), transcribed as executable machines
for trace replay. Each class copies the family's state, actions, next() and properties (the Rust file is cited per
class; the model crate itself is not modified) and adds the trace side: `alpha` (the abstraction of the replayed
store to the machine's observable state) and `actions` (which machine actions a captured step performs).

Observable projection `obs` = the state components the store or the step's reply determines; ghost components
(the model's own bookkeeping, e.g. "an explicit write established this row") evolve only through next() and are
what the invariants read.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401

from trlib import At, Family, Store, stores_at_units

# ================================================================================================ wrt_ledger_stmt


class WrtLedgerStmt(Family):
    """models/breadth-a/src/wrt_ledger_stmt.rs (module 03; F-0303; WRT-B1.9, INV-stmt). One triple of the default
    graph, ledger enabled. State: row lifetime, statements {id: (life, live, touched)}, tuple index, next ids."""
    name = "wrt_ledger_stmt"
    source = "models/breadth-a/src/wrt_ledger_stmt.rs:36-127"
    STMT = "INV-stmt: every live statement names the live edge row it was allocated for"
    IDENT = "WRT-B1.9: no statement is attached to a second edge lifetime"
    OPS = {"ledger-create-rel": "LedgerCreate", "ledger-update-rel": "LedgerUpdate", "ledger-delete-rel": "LedgerDelete",
           "delete_edge": "DirectDelete", "create_edge": "DirectCreate", "delete_node": "DeleteNode"}

    def __init__(self, triple: Tuple[str, str, str], gkey: str, design: str = "as-built"):
        super().__init__()
        self.triple, self.gkey, self.design = triple, gkey, design
        self.name = f"wrt_ledger_stmt[{design}]"
        self.lives: Dict[str, int] = {}
        self.sids: Dict[str, int] = {}

    # --- machine (transcribed)
    def init(self, store, trace):
        return {"row": None, "next_life": 0, "stmts": {}, "tuple": None, "next_stmt": 0}

    @staticmethod
    def _alloc(u, life):
        i = u["next_stmt"]
        u["next_stmt"] += 1
        u["stmts"][i] = {"life": life, "live": True, "touched": [life]}
        u["tuple"] = i

    @staticmethod
    def _erase_link(u, kill_stmt):
        if u["tuple"] is not None and kill_stmt:
            u["stmts"].pop(u["tuple"], None)
        u["tuple"] = None

    def next(self, s, a):
        u = json.loads(json.dumps(s))
        u["stmts"] = {int(k): v for k, v in u["stmts"].items()}
        if a == "LedgerCreate":
            if s["row"] is not None:
                return None
            life = s["next_life"]
            u["next_life"] += 1
            u["row"] = life
            self._alloc(u, life)
        elif a == "LedgerUpdate":
            life = s["row"]
            if life is None:
                return None
            if s["tuple"] is None:
                self._alloc(u, life)
            else:
                st = u["stmts"].get(s["tuple"])
                if st is None or not st["live"]:
                    return None
                if life not in st["touched"]:
                    st["touched"].append(life)
        elif a == "LedgerDelete":
            life = s["row"]
            if life is None or s["tuple"] is None:
                return None
            st = u["stmts"].get(s["tuple"])
            if st is None or not st["live"]:
                return None
            if life not in st["touched"]:
                st["touched"].append(life)
            st["live"] = False
            u["row"] = None
            u["tuple"] = None
        elif a == "DirectDelete":
            if s["row"] is None:
                return None
            u["row"] = None
            if self.design == "reviewed":
                self._erase_link(u, True)
            elif self.design == "control-tuple-only":
                self._erase_link(u, False)
        elif a == "DirectCreate":
            if s["row"] is not None:
                return None
            life = s["next_life"]
            u["next_life"] += 1
            u["row"] = life
        elif a == "DeleteNode":
            if s["row"] is None:
                return None
            u["row"] = None
            self._erase_link(u, True)
        else:
            return None
        return u

    def invariants(self):
        return [(self.STMT, lambda s: all(not st["live"] or s["row"] == st["life"] for st in s["stmts"].values())),
                (self.IDENT, lambda s: all(len(st["touched"]) <= 1 for st in s["stmts"].values()))]

    def obs(self, s):
        return (s["row"], tuple(sorted((i, st["live"]) for i, st in s["stmts"].items())), s["tuple"])

    # --- trace side
    def alpha(self, store: Store, step):
        a, p, b = self.triple
        rows = [r for r in store.rows("Graph_KG.rdf_edges")
                if (r.get("s"), r.get("p"), r.get("o_id"), r.get("graph_id") or "") == (a, p, b, "")]
        row = None
        if rows:
            rid = rows[0]["_id"]
            if rid not in self.lives:
                self.lives[rid] = len(self.lives)
            row = self.lives[rid]
        stmts = {}
        for k, v in store.under("^IVG.Ledger", "stmt").items():
            if len(k) == 3 and isinstance(v, tuple) and tuple(str(x) for x in v[:3]) == (a, p, b):
                if k[2] not in self.sids:
                    self.sids[k[2]] = len(self.sids)
                stmts[self.sids[k[2]]] = len(v) < 6 or str(v[5] if v[5] is not None else "") == ""
        t = store.get("^IVG.Ledger", "tuple", a, p, b, self.gkey)
        tid = None
        if t is not None:
            if str(t) not in self.sids:
                self.sids[str(t)] = len(self.sids)
            tid = self.sids[str(t)]
        return (row, tuple(sorted(stmts.items())), tid)

    def actions(self, step, seg, pre, post):
        if step.get("triple") != list(self.triple) and step.get("triple") != self.triple:
            return []
        a = self.OPS.get(step["op"])
        return [a] if a and step["ok"] else []

    def relevant(self, ref):
        return ref.startswith('^IVG.Ledger("stmt"') or ref.startswith('^IVG.Ledger("tuple"')


# ================================================================================================ wrt_bulk_atomic


class WrtBulkAtomic(Family):
    """models/breadth-a/src/wrt_bulk_atomic.rs (module 03; F-0305; WRT-B3.19). A batch of two chunks sent to
    EdgeScan.BulkIngestNodesSQL; state: committed[2], pending[2], txn_open, phase."""
    name = "wrt_bulk_atomic"
    source = "models/breadth-a/src/wrt_bulk_atomic.rs:31-82"
    INV = "WRT-B3.19: a bulk write commits all of its batch or none of it"

    def __init__(self, chunks: List[List[str]], design: str = "as-built"):
        super().__init__()
        self.chunks = chunks
        self.design = design
        self.name = f"wrt_bulk_atomic[{design}]"
        self.node_root = None

    def bind(self, trace):
        self.node_root = trace["layouts"]["Graph_KG.nodes"]["data"]

    def init(self, store, trace):
        return {"committed": [False, False], "pending": [False, False], "txn_open": False, "phase": "Start"}

    def next(self, s, a):
        u = json.loads(json.dumps(s))
        ph = s["phase"]
        if a == "Begin":
            if ph != "Start":
                return None
            u["txn_open"], u["phase"] = True, "Loading0"
        elif a == "ChunkOk":
            if not ph.startswith("Loading"):
                return None
            i = int(ph[-1])
            if self.design == "as-built":
                u["committed"][i] = True
            elif self.design == "reviewed":
                u["pending"][i] = True
            else:  # control: SqlCommit
                u["committed"][i] = True
                for j in range(2):
                    if s["pending"][j]:
                        u["committed"][j] = True
                u["pending"] = [False, False]
            u["phase"] = "Loaded" if i == 1 else "Loading1"
        elif a == "ChunkFail":
            if not ph.startswith("Loading"):
                return None
            u["pending"], u["txn_open"], u["phase"] = [False, False], False, "Fallback"
        elif a == "Commit":
            if ph != "Loaded":
                return None
            for j in range(2):
                if s["pending"][j]:
                    u["committed"][j] = True
            u["pending"], u["txn_open"], u["phase"] = [False, False], False, "Returned"
        elif a == "FallbackOk":
            if ph != "Fallback":
                return None
            u["committed"], u["phase"] = [True, True], "Returned"
        elif a == "FallbackFail":
            if ph != "Fallback":
                return None
            u["phase"] = "Raised"
        else:
            return None
        return u

    def invariants(self):
        return [(self.INV, lambda s: s["phase"] not in ("Returned", "Raised") or s["committed"][0] == s["committed"][1])]

    def obs(self, s):
        # what a reader in another process can see: the rows committed or pending in an open transaction are
        # told apart by the journal (a unit's commit); the phase by the call's reply
        return (tuple(s["committed"]), s["phase"] if s["phase"] in ("Returned", "Raised") else "running")

    def _committed(self, store: Store) -> Tuple[bool, bool]:
        ids = {str(r.get("node_id")) for r in store.rows("Graph_KG.nodes") if (r.get("graph_id") or "") == ""}
        return tuple(all(n in ids for n in ch) for ch in self.chunks)

    def alpha(self, store, step):
        phase = "running"
        if step is not None and step.get("op") == "bulk_create_nodes":
            phase = "Returned" if step["ok"] else "Raised"
        return (self._committed(store), phase)

    def actions(self, step, seg, pre, post):
        if step["op"] != "bulk_create_nodes":
            return []
        loader = set(step.get("loader_pids") or [])
        acts: List[Any] = ["Begin"]
        failed = False
        for u, st in stores_at_units(pre, seg):
            if u["kind"] != "txn":
                continue
            node_recs = [r for r in u["records"] if r["g"] and self._is_node_row(r["g"], post)]
            if not node_recs:
                continue
            if u["pid"] in loader and not failed:
                if u["committed"] and not u.get("rolled_back"):
                    acts.append(At("ChunkOk", (self._committed(st), "running")))
                else:
                    acts.append(At("ChunkFail", (self._committed(st), "running")))
                    failed = True
            elif u["pid"] not in loader:
                failed = True   # the SQL fallback on the cursor's process
                ok = u["committed"] and not u.get("rolled_back")
                acts.append("FallbackOk" if ok else "FallbackFail")
        if not failed and step["ok"]:
            acts.append("Commit")
        elif failed and not any(a in ("FallbackOk", "FallbackFail") for a in acts):
            acts.append("FallbackOk" if step["ok"] else "FallbackFail")
        return acts

    def _is_node_row(self, ref, store):
        if self.node_root is None:
            self.node_root = store.layouts["Graph_KG.nodes"]["data"]
        return ref.startswith(self.node_root + "(")

    def relevant(self, ref):
        return self.node_root is not None and ref.startswith(self.node_root + "(")


# ================================================================================================ tmp_mark

Q_MARKED, Q_PLAIN, Q_ONE = "Marked", "Plain", "TemporalOne"


class TmpMark(Family):
    """models/breadth-a/src/tmp_mark.rs (modules 03 and 05; F-0304, F-0505, F-0507; ADR-0009/HD-0302). One triple,
    adjacency index declared. State: row qualifier class, ghost `explicit`, timestamp count."""
    name = "tmp_mark"
    source = "models/breadth-a/src/tmp_mark.rs:46-128"
    EXPL = "ADR-0009/HD-0302: a temporal delete or purge never removes an explicitly written edge"
    MARK = "ADR-0009/TMP-B9.13: a marked row exists only while its triple has a timestamp"
    DESIGNS = {"as-built": dict(adopt_on_store=False, strict_marker=False, purge_retracts=False, adopt_clears=True),
               "reviewed": dict(adopt_on_store=True, strict_marker=True, purge_retracts=True, adopt_clears=True)}

    def __init__(self, g: str, gkey: str, triple: Tuple[str, str, str], design: str = "as-built"):
        super().__init__()
        self.g, self.gkey, self.triple, self.design = g, gkey, triple, design
        self.fix = self.DESIGNS[design]
        self.name = f"tmp_mark[{design}]{triple[0]}"

    def init(self, store, trace):
        row, ts = self._observe(store)
        return {"row": row, "explicit": False, "ts": ts}

    def _marked(self, q):
        return q == Q_MARKED or (q == Q_ONE and not self.fix["strict_marker"])

    def _retract(self, u):
        if u["row"] is not None and self._marked(u["row"]):
            u["row"], u["explicit"] = None, False

    def _adopt(self, u, q):
        if u["row"] == Q_MARKED:
            if self.fix["adopt_clears"]:
                u["row"] = q
            u["explicit"] = True

    def next(self, s, a):
        u = dict(s)
        kind, q = (a if isinstance(a, tuple) else (a, None))
        if kind == "CreateEdge":
            if s["row"] is None:
                u["row"], u["explicit"] = q, True
            else:
                self._adopt(u, q)
        elif kind == "StoreEdge":
            if s["row"] is None:
                u["row"], u["explicit"] = q, True
            elif self.fix["adopt_on_store"]:
                self._adopt(u, q)
            else:
                u["explicit"] = True
        elif kind == "TemporalInsert":
            if s["ts"] >= 2:
                return None
            u["ts"] += 1
            if s["row"] is None:
                u["row"], u["explicit"] = Q_MARKED, False
        elif kind == "TemporalDelete":
            if s["ts"] == 0:
                return None
            u["ts"] -= 1
            if u["ts"] == 0:
                self._retract(u)
        elif kind == "PurgeBefore":
            if s["ts"] == 0:
                return None
            u["ts"] = 0
            self._retract(u)
        elif kind == "Purge":
            u["ts"] = 0
            if self.fix["purge_retracts"]:
                self._retract(u)
        elif kind == "DirectDelete":
            if s["row"] is None:
                return None
            u["row"], u["explicit"] = None, False
        else:
            return None
        return u

    def invariants(self):
        return [(self.MARK, lambda s: s["row"] != Q_MARKED or s["ts"] > 0)]

    def action_properties(self):
        def expl(s, a, t):
            kind = a[0] if isinstance(a, tuple) else a
            if kind in ("TemporalDelete", "PurgeBefore", "Purge") and s["explicit"] and s["row"] is not None:
                return t["row"] is not None
            return True
        return [(self.EXPL, expl)]

    def obs(self, s):
        return (s["row"], s["ts"])

    def _observe(self, store: Store):
        a, p, b = self.triple
        rows = [r for r in store.rows("Graph_KG.rdf_edges")
                if (r.get("s"), r.get("p"), r.get("o_id"), r.get("graph_id") or "") == (a, p, b, self.g)]
        row = None
        if rows:
            q = rows[0].get("qualifiers")
            try:
                d = json.loads(q) if isinstance(q, str) and q else {}
            except ValueError:
                d = {}
            t = d.get("temporal") if isinstance(d, dict) else None
            row = Q_MARKED if t is True else (Q_ONE if t == 1 and t is not True else Q_PLAIN)
        ts = sum(1 for k in store.under("^KG", "tout", self.gkey)
                 if len(k) == 7 and tuple(k[4:7]) == (a, p, b))
        return row, ts

    def alpha(self, store, step):
        return self._observe(store)

    OPS = {"create_edge": "CreateEdge", "store_edge": "StoreEdge", "create_edge_temporal": "TemporalInsert",
           "delete_edge_temporal": "TemporalDelete", "purge_before": "PurgeBefore", "TemporalIndex.Purge": "Purge",
           "delete_edge": "DirectDelete"}

    def actions(self, step, seg, pre, post):
        kind = self.OPS.get(step["op"])
        if not kind or not step["ok"]:
            return []
        if kind not in ("Purge", "PurgeBefore") and tuple(step.get("triple") or ()) != tuple(self.triple):
            return []
        if kind == "PurgeBefore" and pre.under("^KG", "tout", self.gkey) == {}:
            return []
        if kind in ("CreateEdge", "StoreEdge"):
            q = step.get("qualifiers") or {}
            return [(kind, Q_ONE if q.get("temporal") == 1 and q.get("temporal") is not True else
                     (Q_MARKED if q.get("temporal") is True else Q_PLAIN))]
        return [kind]

    def relevant(self, ref):
        return ref.startswith('^KG("tout"')


# ================================================================================================ tmp_bucket


class TmpBucket(Family):
    """models/breadth-a/src/tmp_bucket.rs (module 05; F-0501; TMP-B1.7). One source/predicate/bucket, two
    coordinates. State: tout weights per coordinate, bucket counter, tagg count and sum."""
    name = "tmp_bucket"
    source = "models/breadth-a/src/tmp_bucket.rs:35-86"
    INV = "TMP-B1.7: the bucket aggregate and counter describe exactly the edges the bucket holds"

    def __init__(self, gkey: str, s: str, p: str, o: str, coords: List[int], bucket: int, design: str = "as-built"):
        super().__init__()
        self.gkey, self.s, self.p, self.o, self.coords, self.bucket = gkey, s, p, o, coords, bucket
        self.design = design
        self.name = f"tmp_bucket[{design}]"

    def init(self, store, trace):
        return self._observe_state(store)

    def next(self, st, a):
        u = {"tout": dict(st["tout"]), "bucket": st["bucket"], "count": st["count"], "sum": st["sum"]}
        if a[0] == "Insert":
            _, c, w, m = a
            old = st["tout"].get(c)
            if m != "update" and old is not None:
                return u
            if self.design == "reviewed" and old is not None:
                u["sum"] += w - old
            elif self.design == "control-bucket-counted" and old is not None:
                u["sum"] += w - old
                u["bucket"] += 1
            else:
                u["bucket"] += 1
                u["count"] += 1
                u["sum"] += w
            u["tout"][c] = w
        elif a[0] == "Delete":
            c = a[1]
            if c not in st["tout"]:
                return None
            del u["tout"][c]
            u["bucket"] -= 1
            if u["bucket"] <= 0:
                u["bucket"] = 0
            u["count"] = len(u["tout"])
            u["sum"] = sum(u["tout"].values())
        else:
            return None
        return u

    def invariants(self):
        def inv(st):
            n = len(st["tout"])
            return st["count"] == n and st["bucket"] == n and st["sum"] == sum(st["tout"].values())
        return [(self.INV, inv)]

    def obs(self, st):
        return (tuple(sorted(st["tout"].items())), st["bucket"], st["count"], st["sum"])

    def _num(self, v):
        if v is None or v == "":
            return 0
        f = float(v)
        return int(f) if f == int(f) else f

    def _observe_state(self, store):
        tout = {}
        for i, ts in enumerate(self.coords):
            v = store.get("^KG", "tout", self.gkey, ts, self.s, self.p, self.o)
            if v is not None:
                tout[i] = self._num(v)
        return {"tout": tout, "bucket": self._num(store.get("^KG", "bucket", self.gkey, self.bucket, self.s)),
                "count": self._num(store.get("^KG", "tagg", self.gkey, self.bucket, self.s, self.p, "count")),
                "sum": self._num(store.get("^KG", "tagg", self.gkey, self.bucket, self.s, self.p, "sum"))}

    def alpha(self, store, step):
        return self.obs(self._observe_state(store))

    def actions(self, step, seg, pre, post):
        if step.get("family") != "tmp_bucket" or not step["ok"]:
            return []
        c = self.coords.index(step["ts"])
        if step["op"] == "create_edge_temporal":
            return [("Insert", c, step["w"], step["mode"])]
        if step["op"] == "delete_edge_temporal":
            return [("Delete", c)]
        return []

    def relevant(self, ref):
        return ref.startswith('^KG("tout"') or ref.startswith('^KG("tagg"') or ref.startswith('^KG("bucket"')


# ================================================================================================ adj_degree


class AdjDegree(Family):
    """models/breadth-a/src/adj_degree.rs (module 04; F-0401, F-C0401; ADJ-I5.9). One graph, one source S with out
    entries {0, 1}. Transcribed: writer W (WLock, WOut, WGen, WCommit/WRollback), eraser E (ELock, E1, E2,
    EKillDegc, ECommit), reader R (RGen, RHit, RProbe, RCount, RStore, RRecheck). The explorer's run bounds
    (w_runs < 2, r_calls < 2) are exploration bounds, not guards of a real step, and are not applied to the replay.
    Trace-side bookkeeping added: `ans`, the value the last Degree call answered (checked against its reply)."""
    name = "adj_degree"
    source = "models/breadth-a/src/adj_degree.rs:80-260"
    INV = "ADJ-I5.9: a current degree-cache entry holds the committed out-degree"

    def __init__(self, gk, src, pred, dsts, design="as-built"):
        super().__init__()
        self.gk, self.src, self.pred, self.dsts, self.design = gk, src, pred, dsts, design
        self.name = f"adj_degree[{design}]"

    def init(self, store, trace):
        out, gen, degc = self._observe(store)
        return {"out": sorted(out), "gen": gen, "degc": degc, "committed": sorted(out), "w": ("Idle", None),
                "w_had": False, "w_undo": [], "e": "Idle", "e_undo": [], "r": "Idle", "r_gen": 0, "r_got": False,
                "r_count": 0, "ans": None}

    @staticmethod
    def _g(s):
        return s["gen"] or 0

    def _busy(self, s):
        return int(s["w"][0] != "Idle") + int(s["e"] not in ("Idle", "Done")) + int(s["r"] == "Stored")

    def next(self, s, a):  # noqa: C901 (a transcription of one match)
        u = json.loads(json.dumps(s))
        kind = a[0] if isinstance(a, tuple) else a
        e_open = s["e"] not in ("Idle", "Done")
        out = set(s["out"])

        def setout(x):
            u["out"] = sorted(x)
        if kind == "WLock":
            if s["w"][0] != "Idle" or e_open:
                return None
            u["w"] = ("Locked", a[1])
        elif kind == "WPre":
            if s["w"][0] != "Locked" or self.design != "reviewed":
                return None
            u["gen"] = self._g(s) + 1
            u["w"] = ("PreBumped", s["w"][1])
        elif kind == "WOut":
            pc, k = s["w"]
            if not ((pc == "Locked" and self.design in ("as-built", "hd0401")) or (pc == "PreBumped" and self.design == "reviewed")):
                return None
            if k == "Put":
                u["w_undo"].append(["Out", 1, 1 in out])
                setout(out | {1})
            else:
                u["w_had"] = 0 in out
                u["w_undo"].append(["Out", 0, 0 in out])
                setout(out - {0})
            u["w"] = ("Wrote", k)
        elif kind == "WGen":
            pc, k = s["w"]
            if pc != "Wrote":
                return None
            if k == "Put" or s["w_had"]:
                u["gen"] = self._g(s) + 1
            u["w"] = ("Bumped", k)
        elif kind == "WCommit":
            pc, k = s["w"]
            if pc != "Bumped":
                return None
            c = set(s["committed"])
            c = c | {1} if k == "Put" else c - {0}
            u["committed"] = sorted(c)
            u["w"], u["w_undo"], u["w_had"] = ("Idle", None), [], False
        elif kind == "WRollback":
            if s["w"][0] == "Idle":
                return None
            self._rollback(u, s["w_undo"])
            u["w"], u["w_undo"], u["w_had"] = ("Idle", None), [], False
        elif kind == "ELock":
            if s["e"] != "Idle" and s["e"] != "Done" or s["w"][0] != "Idle":
                return None
            u["e"] = "Locked"
        elif kind == "E1":
            if s["e"] != "Locked":
                return None
            if self.design in ("as-built", "hd0401"):
                for x in s["out"]:
                    u["e_undo"].append(["Out", x, True])
                u["out"] = []
            else:
                u["gen"] = self._g(s) + 1
            u["e"] = "Step1"
        elif kind == "E2":
            if s["e"] != "Step1":
                return None
            if self.design == "as-built":
                if s["gen"] is not None:
                    u["e_undo"].append(["Gen", s["gen"]])
                u["gen"] = None
            elif self.design == "hd0401":
                u["gen"] = self._g(s) + 1
            else:
                for x in s["out"]:
                    u["e_undo"].append(["Out", x, True])
                u["out"] = []
            u["e"] = "Step2"
        elif kind == "EKillDegc":
            if s["e"] != "Step2":
                return None
            if s["degc"] is not None:
                u["e_undo"].append(["Degc", s["degc"]])
            u["degc"] = None
            u["e"] = "DegcKilled"
        elif kind == "ECommit":
            if s["e"] != "DegcKilled":
                return None
            u["committed"], u["e_undo"], u["e"] = [], [], "Done"
        elif kind == "RGen":
            if s["r"] != "Idle":
                return None
            u["r_gen"], u["r"] = self._g(s), "GenRead"
        elif kind == "RHit":
            if s["r"] != "GenRead":
                return None
            if s["degc"] is not None and s["degc"][0] == s["r_gen"]:
                u["r"], u["ans"] = "Idle", s["degc"][1]
            else:
                u["r"] = "Hit"
        elif kind == "RProbe":
            if s["r"] != "Hit":
                return None
            held = s["w"][0] != "Idle" or e_open
            u["r_got"] = True if self.design == "control-no-probe" else not held
            u["r"] = "Probed"
        elif kind == "RCount":
            if s["r"] != "Probed":
                return None
            u["r_count"], u["r"] = len(s["out"]), "Counted"
        elif kind == "RStore":
            if s["r"] != "Counted":
                return None
            u["ans"] = s["r_count"]
            if s["r_got"] and self._g(s) == s["r_gen"]:
                u["degc"], u["r"] = [s["r_gen"], s["r_count"]], "Stored"
            else:
                u["r"] = "Idle"
        elif kind == "RRecheck":
            if s["r"] != "Stored":
                return None
            if self._g(s) != s["r_gen"]:
                u["degc"] = None
            u["r"] = "Idle"
        else:
            return None
        return u

    @staticmethod
    def _rollback(u, undo):
        for x in reversed(undo):
            if x[0] == "Out":
                o = set(u["out"])
                o = o | {x[1]} if x[2] else o - {x[1]}
                u["out"] = sorted(o)
            elif x[0] == "Gen":
                u["gen"] = x[1]
            elif x[0] == "Degc":
                u["degc"] = x[1]

    def invariants(self):
        def inv(s):
            if self._busy(s) > 0:
                return True
            if s["degc"] is not None and s["degc"][0] == self._g(s):
                return s["degc"][1] == len(s["committed"])
            return True
        return [(self.INV, inv)]

    def obs(self, s):
        return (tuple(s["out"]), s["gen"], tuple(s["degc"]) if s["degc"] else None, s["w"][0], s["ans"])

    def _observe(self, store):
        out = {i for i, d in enumerate(self.dsts) if store.has("^KG", "out", self.gk, self.src, self.pred, d)}
        gen = store.get("^KG", "gen", self.gk, self.src)
        gen = None if gen is None else int(gen)
        degc = store.get("^KG", "degc", self.gk, self.src, "\x01")
        degc = (int(degc[0]), int(degc[1])) if isinstance(degc, tuple) else None
        return out, gen, degc

    def alpha(self, store, step):
        out, gen, degc = self._observe(store)
        w = "Bumped" if step is not None and step.get("w_open") else "Idle"
        ans = self.S["ans"] if step is None else (int(step["reply"]) if step.get("op") == "Adj.Degree" else self.S["ans"])
        return (tuple(sorted(out)), gen, degc, w, ans)

    def actions(self, step, seg, pre, post):
        op = step["op"]
        if not step["ok"] or step.get("family") != "adj_degree":
            return []
        if op == "Adj.Degree":
            acts = ["RGen", "RHit"]
            s = self.next(self.next(self.S, "RGen"), "RHit")
            if s is not None and s["r"] == "Hit":
                acts += ["RProbe", "RCount", "RStore"]
                s = self.next(self.next(self.next(s, "RProbe"), "RCount"), "RStore")
                if s is not None and s["r"] == "Stored":
                    acts.append("RRecheck")
            return acts
        k = {"create_edge": "Put", "delete_edge": "Remove"}.get(op)
        if k and not step.get("w_open"):
            return [("WLock", k), "WOut", "WGen", "WCommit"]
        if k and step.get("w_open"):
            return [("WLock", k), "WOut", "WGen"]
        if op == "caller-rollback":
            return ["WRollback"]
        if op == "erase_graph":
            return ["ELock", "E1", "E2", "EKillDegc", "ECommit"]
        return []

    def relevant(self, ref):
        return ref.startswith('^KG("out"') or ref.startswith('^KG("gen"') or ref.startswith('^KG("degc"')


# ================================================================================================ adj_rebuild_txn (part 1)


class AdjRebuildCaller(Family):
    """models/breadth-a/src/adj_rebuild_txn.rs part 1 `Caller` (module 04; F-0409; ADJ-B8.9). A rebuild
    (engine.sync -> BuildKG) inside a caller's transaction on the caller's own server process."""
    name = "adj_rebuild_caller"
    source = "models/breadth-a/src/adj_rebuild_txn.rs:34-104"
    B89 = "ADJ-B8.9: a rebuild never ends or undoes a transaction its caller opened"

    def __init__(self, run, node, design="as-built"):
        super().__init__()
        self.run, self.node, self.design = run, node, design
        self.name = f"adj_rebuild_caller[{design}]{run}"
        self.node_root = None

    def bind(self, trace):
        self.node_root = trace["layouts"]["Graph_KG.nodes"]["data"]

    def init(self, store, trace):
        return {"tlevel": 0, "caller_open": False, "caller_pending": False, "caller_committed": False,
                "sync": ["NotYet", None], "ret": None}

    def next(self, s, a):
        u = json.loads(json.dumps(s))
        if a == "CBegin":
            if s["caller_open"] or s["tlevel"] != 0 or s["caller_committed"] or s["sync"][0] != "NotYet":
                return None
            u["caller_open"], u["tlevel"] = True, 1
        elif a == "CWrite":
            if not s["caller_open"] or s["caller_pending"] or s["tlevel"] == 0:
                return None
            u["caller_pending"] = True
        elif a == "SyncStart":
            if s["sync"][0] != "NotYet":
                return None
            u["sync"], u["tlevel"] = ["Running", s["tlevel"]], s["tlevel"] + 1
        elif a == "SyncOk":
            if s["sync"][0] != "Running":
                return None
            u["tlevel"] -= 1
            u["sync"], u["ret"] = ["Done", None], [s["sync"][1], u["tlevel"]]
        elif a == "SyncFail":
            if s["sync"][0] != "Running":
                return None
            found = s["sync"][1]
            if self.design == "as-built":
                u["tlevel"] = 0
                u["caller_pending"] = False
            elif self.design == "reviewed":
                u["tlevel"] = found
            else:
                while u["tlevel"] > found + 1:
                    u["tlevel"] -= 1
            u["sync"], u["ret"] = ["Done", None], [found, u["tlevel"]]
        elif a in ("CCommit", "CRollback"):
            if not s["caller_open"] or s["sync"][0] == "Running":
                return None
            if a == "CCommit" and s["tlevel"] >= 1 and s["caller_pending"]:
                u["caller_committed"] = True
            u["caller_open"], u["caller_pending"], u["tlevel"] = False, False, 0
        else:
            return None
        return u

    def action_properties(self):
        def b89(s, a, t):
            if a in ("SyncOk", "SyncFail") and s["sync"][0] == "Running":
                return t["tlevel"] == s["sync"][1] and t["caller_pending"] == s["caller_pending"]
            return True
        return [(self.B89, b89)]

    def obs(self, s):
        # what the store and the caller's $TLevel show: the caller's row present (pending or committed), $TLevel
        return (s["caller_pending"] or s["caller_committed"], s["tlevel"])

    def alpha(self, store, step):
        present = any(str(r.get("node_id")) == self.node for r in store.rows("Graph_KG.nodes"))
        tl = self.S["tlevel"] if step is None or step.get("tlevel") is None else int(step["tlevel"])
        return (present, tl)

    OPS = {"caller-begin": ["CBegin"], "caller-create_node": ["CWrite"], "sync": ["SyncStart", "SyncOk"],
           "caller-commit": ["CCommit"]}

    def actions(self, step, seg, pre, post):
        if step.get("run") != self.run:
            return []
        if step["op"] == "sync":
            return ["SyncStart", "SyncOk" if step["ok"] else "SyncFail"]
        return self.OPS.get(step["op"], [])

    def relevant(self, ref):
        return self.node_root is not None and ref.startswith(self.node_root + "(")


# ================================================================================================ gid_mode


class GidMode(Family):
    """models/breadth-a/src/gid_mode.rs (module 02; F-0201, F-0207, F-0208; GID-I4.10). One triple (s, p, o) of
    graph g: its rows' edge keys, the live mode ^IVG.GraphMode(g), each engine's cached mode (ghost: held in the
    engine object, not in the store), the two-step unlocked Set(g, 0). The explorer bound (ops < 6) is not applied."""
    name = "gid_mode"
    source = "models/breadth-a/src/gid_mode.rs:36-136"
    INV = "GID-I4.10: a graph whose mode is off holds no parallel edges"
    FLAWS = {"as-built": dict(ekey0_guard=True, set_unlocked=True, cache_forever=True, writer_lock=False),
             "reviewed": dict(ekey0_guard=False, set_unlocked=False, cache_forever=False, writer_lock=True)}

    def __init__(self, g, triple, design="as-built"):
        super().__init__()
        self.g, self.triple, self.design = g, triple, design
        self.f = self.FLAWS[design]
        self.name = f"gid_mode[{design}]"

    def init(self, store, trace):
        rows, mode = self._observe(store)
        return {"rows": rows, "mode": mode, "cache": [None, None], "set_counted": False, "cy": [None, None],
                "excl": False, "shared": 0}

    def _blocks(self, s):
        return (0 in s["rows"]) if self.f["ekey0_guard"] else bool(s["rows"])

    def next(self, s, a):
        u = json.loads(json.dumps(s))
        kind = a[0] if isinstance(a, tuple) else a
        locked = not self.f["set_unlocked"]
        if kind == "SetOn":
            u["mode"] = True
            u["cache"][a[1]] = None
        elif kind == "SetOffCount":
            if s["set_counted"] or not s["mode"]:
                return None
            if locked:
                if s["excl"] or s["shared"] > 0:
                    return None
                u["excl"] = True
            if len(s["rows"]) > 1:
                u["excl"] = False
            else:
                u["set_counted"] = True
                if locked:
                    u["mode"], u["cache"][0], u["set_counted"], u["excl"] = False, None, False, False
        elif kind == "SetOffKill":
            if not s["set_counted"]:
                return None
            u["mode"], u["cache"][0], u["set_counted"] = False, None, False
        elif kind == "CyMode":
            i = a[1]
            if s["cy"][i] is not None:
                return None
            if self.f["writer_lock"] and locked:
                if s["excl"]:
                    return None
                u["shared"] += 1
            if self.f["cache_forever"]:
                if s["cache"][i] is not None:
                    m = s["cache"][i]
                else:
                    u["cache"][i] = s["mode"]
                    m = s["mode"]
            else:
                m = s["mode"]
            u["cy"][i] = m
        elif kind == "CyInsert":
            i = a[1]
            m = s["cy"][i]
            if m is None:
                return None
            if m:
                k = max(s["rows"]) + 1 if s["rows"] else 0
                u["rows"] = sorted(set(s["rows"]) | {k})
            elif not self._blocks(s):
                u["rows"] = sorted(set(s["rows"]) | {0})
            u["cy"][i] = None
            if self.f["writer_lock"] and locked:
                u["shared"] -= 1
        elif kind in ("CreateEdge", "StoreEdge"):
            if not self._blocks(s):
                u["rows"] = sorted(set(s["rows"]) | {0})
        elif kind == "CyDelete":
            if a[1] not in s["rows"]:
                return None
            u["rows"] = sorted(set(s["rows"]) - {a[1]})
        else:
            return None
        return u

    def invariants(self):
        return [(self.INV, lambda s: s["mode"] or len(s["rows"]) <= 1)]

    def obs(self, s):
        return (tuple(s["rows"]), s["mode"])

    def _observe(self, store):
        a, p, b = self.triple
        rows = sorted(int(r.get("ekey") or 0) for r in store.rows("Graph_KG.rdf_edges")
                      if (r.get("s"), r.get("p"), r.get("o_id"), r.get("graph_id")) == (a, p, b, self.g))
        m = store.get("^IVG.GraphMode", self.g)   # GraphMode.cls:30-33: "multi" when on, killed when off
        return rows, (m is not None and str(m) == "multi")

    def alpha(self, store, step):
        rows, mode = self._observe(store)
        return (tuple(rows), mode)

    def actions(self, step, seg, pre, post):
        g = step.get("gid")
        if not g or not step["ok"]:
            return []
        e = step.get("engine", 0)
        if g == "SetOn":
            return [("SetOn", e)]
        if g == "SetOff":
            return ["SetOffCount", "SetOffKill"] if not step.get("refused") else ["SetOffCount"]
        if g == "CyCreate":
            return [("CyMode", e), ("CyInsert", e)]
        if g == "CyDelete":
            return [("CyDelete", step["ekey"])]
        if g in ("CreateEdge", "StoreEdge"):
            return [(g, e)]
        return []

    def relevant(self, ref):
        return ref.startswith("^IVG.GraphMode")


# ================================================================================================ vec_ivf


class VecIvf(Family):
    """models/breadth-a/src/vec_ivf.rs (module 06; F-0608, F-0606; VEC-B11.14, VEC-B11.4). One IVF index over graph
    g, two cells, node ids a, b. Insert = InsSet then InsCount (one process here, so back to back); Delete; EraseGraph.
    The explorer bound (ops < 4) is not applied."""
    name = "vec_ivf"
    source = "models/breadth-a/src/vec_ivf.rs:34-110"
    ONE = "VEC-B11.14: an id is listed in at most one cell"
    COUNT = "VEC-B11.14: indexed equals the number of distinct ids listed"
    LIVE = "VEC-B11.4/HD-0601: the index lists only ids with a live vector"

    def __init__(self, name_, g, ids, design="as-built"):
        super().__init__()
        self.idx, self.g, self.ids, self.design = name_, g, ids, design
        self.name = f"vec_ivf[{design}]"

    def init(self, store, trace):
        lists, indexed, live = self._observe(store)
        return {"lists": lists, "indexed": indexed, "live": live, "p": [None, None]}

    def next(self, s, a):
        u = json.loads(json.dumps(s))
        kind = a[0]
        if kind == "InsSet":
            _, p, i, c = a
            if s["p"][p] is not None or i not in s["live"]:
                return None
            if self.design == "as-built":
                u["lists"][str(i)] = sorted(set(s["lists"].get(str(i), [])) | {c})
                u["p"][p] = s["indexed"]
            else:
                was = bool(s["lists"].get(str(i)))
                u["lists"][str(i)] = [c]
                if not was:
                    u["indexed"] += 1
        elif kind == "InsCount":
            r = s["p"][a[1]]
            if r is None:
                return None
            u["indexed"], u["p"][a[1]] = r + 1, None
        elif kind == "Delete":
            cells = s["lists"].get(str(a[1]))
            if not cells:
                return None
            if self.design == "as-built":
                u["lists"][str(a[1])] = [x for x in cells if x != cells[0]]
            else:
                u["lists"].pop(str(a[1]))
            u["indexed"] -= 1
            if u["lists"].get(str(a[1])) == []:
                u["lists"].pop(str(a[1]))
        elif kind == "EraseGraph":
            if not s["live"]:
                return None
            u["live"] = []
            if self.design != "as-built":
                u["lists"], u["indexed"] = {}, 0
        else:
            return None
        return u

    def invariants(self):
        return [(self.ONE, lambda s: all(len(c) <= 1 for c in s["lists"].values())),
                (self.COUNT, lambda s: s["p"] != [None, None] or s["indexed"] == sum(1 for c in s["lists"].values() if c)),
                (self.LIVE, lambda s: all(int(i) in s["live"] for i, c in s["lists"].items() if c))]

    def obs(self, s):
        return (tuple(sorted((int(i), tuple(c)) for i, c in s["lists"].items() if c)), s["indexed"], tuple(sorted(s["live"])))

    def _observe(self, store):
        lists: Dict[str, List[int]] = {}
        for k in store.under("^IVF", self.idx, "list"):
            if len(k) == 5 and k[4] in self.ids:
                lists.setdefault(str(self.ids.index(k[4])), []).append(int(k[3]))
        lists = {i: sorted(c) for i, c in lists.items()}
        v = store.get("^IVF", self.idx, "cfg", "indexed")
        indexed = int(v) if v not in (None, "") else 0
        # a named graph's node vectors live in its routed table, named by its registry row (embeddings.py:470-558)
        tables = ["Graph_KG.kg_NodeEmbeddings"] + [
            "Graph_KG." + str(r.get("table_name")) for r in store.rows("Graph_KG.embedding_registry")
            if (r.get("graph_id") or "") == self.g and str(r.get("kind")) == "node"]
        have = set()
        for t in tables:
            if t in store.layouts:
                have |= {str(r.get("node_id")) for r in store.rows(t) if (r.get("graph_id") or "") == self.g}
        live = sorted(i for i, n in enumerate(self.ids) if n in have)
        return lists, indexed, live

    def alpha(self, store, step):
        lists, indexed, live = self._observe(store)
        return (tuple(sorted((int(i), tuple(c)) for i, c in lists.items() if c)), indexed, tuple(live))

    def actions(self, step, seg, pre, post):
        if step.get("ivf") == "Insert" and step["ok"]:
            i = self.ids.index(step["node"])
            acts = [("InsSet", 0, i, int(step["reply"]))]
            return acts + [("InsCount", 0)] if self.design == "as-built" else acts   # reviewed Insert is one step
        if step.get("ivf") == "Delete" and step["ok"]:
            return [("Delete", self.ids.index(step["node"]))]
        if step.get("ivf") == "EraseGraph" and step["ok"]:
            return [("EraseGraph",)]
        return []

    def relevant(self, ref):
        return ref.startswith('^IVF(')


# ================================================================================================ vec_route_batch


class VecRouteBatch(Family):
    """models/breadth-a/src/vec_route_batch.rs (module 06; F-0615; VEC-X3.9/SYS-I3). The pair (g, k) with no route;
    node a exists, m does not; Store(items, width). The explorer bound (calls < 3) is not applied."""
    name = "vec_route_batch"
    source = "models/breadth-a/src/vec_route_batch.rs:29-70"
    X39 = "VEC-X3.9/SYS-I3: a refused batch leaves no new route behind"

    def __init__(self, g, model_key, design="as-built"):
        super().__init__()
        self.g, self.mk, self.design = g, model_key, design
        self.name = f"vec_route_batch[{design}]"
        self.reg_root = None

    def bind(self, trace):
        self.reg_root = trace["layouts"]["Graph_KG.embedding_registry"]["data"]

    def init(self, store, trace):
        return {"route": self._route(store), "stored": 0, "last": "None"}

    def next(self, s, a):
        _, items, w = a
        u = dict(s)
        missing = items != 0
        pre = missing if self.design == "reviewed" else (items == 1 if self.design == "control-first-only" else False)
        if pre:
            u["last"] = "Refused"
            return u
        if s["route"] is None:
            u["route"] = w
        elif s["route"] != w:
            u["last"] = "Refused"
            return u
        if missing:
            u["last"] = "Refused"
            return u
        u["stored"] += 1
        u["last"] = "Stored"
        return u

    def action_properties(self):
        return [(self.X39, lambda s, a, t: t["last"] != "Refused" or t["route"] == s["route"])]

    def obs(self, s):
        return (s["route"], s["last"])

    def _route(self, store):
        for r in store.rows("Graph_KG.embedding_registry"):
            if (r.get("graph_id") or "") == self.g and str(r.get("model_key") or "") == self.mk:
                return int(r.get("dimension"))
        return None

    def alpha(self, store, step):
        last = self.S["last"]
        if step is not None and step.get("vrb_items") is not None:
            last = "Stored" if step["ok"] else "Refused"
        return (self._route(store), last)

    def actions(self, step, seg, pre, post):
        if step.get("vrb_items") is None:
            return []
        return [("Store", step["vrb_items"], step["vrb_width"])]

    def relevant(self, ref):
        return self.reg_root is not None and ref.startswith(self.reg_root + "(")


# ================================================================================================ ins_setup


class InsSetup(Family):
    """models/breadth-a/src/ins_setup.rs (module 01; F-0103, F-0102; INS-I3.4, INS-B1.12). Setup steps Tables,
    Marker, Classes, Kg, Record; first use. The lane's namespace was set up by the pin's own initialize_schema before
    the capture, so the machine starts at Replied with marker and record (reached by five Ok steps). The harness step
    that removes the record (as the breadth probe p0103 does, restored afterwards) stands for a setup stopped after its
    Marker step, a state the machine reaches by Ok, Ok, Stop, and the step that puts it back for a setup run to its
    end: the replay restarts the machine there (environment steps, not product actions)."""
    name = "ins_setup"
    source = "models/breadth-a/src/ins_setup.rs:42-109"
    I34 = "INS-I3.4: an engine is accepted only on a namespace whose record names its schema (or with a warning when unreadable)"
    B112 = "INS-B1.12: a reply with no warning means every setup step succeeded"

    def __init__(self, which, design="as-built"):
        super().__init__()
        self.which, self.design = which, design
        self.name = f"ins_setup[{design}]{which}"

    def init(self, store, trace):
        s = {"unreadable": False, "step": "Tables", "marker": False, "record": False, "failed": False, "warned": False,
             "deploy_failed": False, "engine": "NotChecked"}
        for a in ["Ok"] * 5:
            s = self.next(s, a)
        return s

    def next(self, s, a):
        u = dict(s)
        reviewed = self.design != "as-built"
        running = s["step"] not in ("Replied", "Stopped")
        if a in ("Ok", "Fail"):
            if not running:
                return None
            fail = a == "Fail"
            st = s["step"]
            if st == "Tables":
                if fail:
                    u["failed"] = True
                    u["warned"] = u["warned"] or reviewed
                u["step"] = "Marker"
            elif st == "Marker":
                if fail:
                    return None
                u["marker"], u["step"] = True, "Classes"
            elif st == "Classes":
                if fail:
                    u["failed"], u["deploy_failed"] = True, True
                u["step"] = "Kg"
            elif st == "Kg":
                if fail:
                    u["failed"] = True
                    u["warned"] = u["warned"] or reviewed
                u["step"] = "Record"
            elif st == "Record":
                if fail:
                    return None
                u["record"], u["step"] = True, "Replied"
        elif a == "Stop":
            if not running:
                return None
            u["step"] = "Stopped"
        elif a == "EngineFirstUse":
            if s["engine"] != "NotChecked":
                return None
            if s["unreadable"]:
                u["engine"] = "Accepted(warned)" if self.design != "control-silent-skip" else "Accepted"
            elif s["record"] or (s["marker"] and not reviewed):
                u["engine"] = "Accepted"
            else:
                u["engine"] = "Refused"
        elif a == "EnvRecordRemoved":
            # environment step: restart at the reachable state Ok, Ok, Stop (marker, no record)
            u = {"unreadable": False, "step": "Tables", "marker": False, "record": False, "failed": False,
                 "warned": False, "deploy_failed": False, "engine": s["engine"]}
            for b in ("Ok", "Ok", "Stop"):
                u = self.next(u, b)
        elif a == "EnvRecordRestored":
            # environment step: the record put back = a setup run to its end (five Ok steps)
            u = {"unreadable": False, "step": "Tables", "marker": False, "record": False, "failed": False,
                 "warned": False, "deploy_failed": False, "engine": s["engine"]}
            for b in ["Ok"] * 5:
                u = self.next(u, b)
        else:
            return None
        return u

    def invariants(self):
        return [(self.I34, lambda s: not s["engine"].startswith("Accepted") or s["record"] or
                 (s["unreadable"] and s["engine"] == "Accepted(warned)")),
                (self.B112, lambda s: s["step"] != "Replied" or s["warned"] or s["deploy_failed"] or not s["failed"])]

    def obs(self, s):
        return (s["record"], s["marker"], s["engine"])

    def alpha(self, store, step):
        record = store.get("^IVG.Deploy", "schema") not in (None, "")
        eng = self.S["engine"]
        if step is not None and step.get("first_use") == self.which:
            eng = "Accepted" if step["ok"] else "Refused"
        return (record, bool(self.S["marker"] if step is None or step.get("marker") is None else step["marker"]), eng)

    def actions(self, step, seg, pre, post):
        if step.get("env") == "record-removed":
            return ["EnvRecordRemoved"]
        if step.get("env") == "record-restored":
            return ["EnvRecordRestored"]
        if step.get("first_use") == self.which:
            return ["EngineFirstUse"]
        return []

    def relevant(self, ref):
        return ref.startswith('^IVG.Deploy("schema"')


# ================================================================================================ adj_token


class AdjToken(Family):
    """models/breadth-a/src/adj_token.rs (module 04; F-0402; ADJ-I11.2). The token ^KG("__version"), the shared result
    cache ^IVG.AlgoCache(g, algorithm, hash) = $LB(token, payload), one writer, one builder (kg_WCC through
    IRISSQLStore._cached_algorithm). Edges: 0 = x-R->z (committed before), 1 = x-R->y. A WCC payload holds edge 0
    when x and z share a component, edge 1 when x and y do. The explorer bounds (w_runs, b_runs < 2) are not applied."""
    name = "adj_token"
    source = "models/breadth-a/src/adj_token.rs:49-140"
    INV = "ADJ-I11.2: a cached answer stamped with the current token holds only committed edges"

    def __init__(self, gk, x, y, z, src, design="as-built"):
        super().__init__()
        self.gk, self.x, self.y, self.z, self.src, self.design = gk, x, y, z, src, design
        self.name = f"adj_token[{design}]"

    def _out(self, store):
        out = set()
        if store.has("^KG", "out", self.gk, self.x, "R", self.z):
            out.add(0)
        if store.has("^KG", "out", self.gk, self.x, "R", self.y):
            out.add(1)
        return sorted(out)

    def _token(self, store):
        v = store.get("^KG", "__version")
        return int(v) if v not in (None, "") else 0

    def _cache(self, store):
        ents = [v for k, v in store.under("^IVG.AlgoCache", self.gk).items() if len(k) == 4 and isinstance(v, tuple)]
        if not ents:
            return None
        tok, payload = ents[-1][0], ents[-1][1]
        try:
            rows = json.loads(payload)
            comp = {str(r[0]): str(r[1]) for r in rows}
        except Exception:  # noqa: BLE001
            return (int(tok), ("unreadable",))
        edges = []
        if self.x in comp and comp.get(self.x) == comp.get(self.z):
            edges.append(0)
        if self.x in comp and comp.get(self.x) == comp.get(self.y):
            edges.append(1)
        return (int(tok), tuple(edges))

    def init(self, store, trace):
        out = self._out(store)
        c = self._cache(store)
        return {"out": out, "committed": out, "token": self._token(store), "cache": list(c) if c else None,
                "w": ["Idle", None], "w_undo": None, "b": "Idle", "b_token": 0, "b_got": False, "b_payload": []}

    def next(self, s, a):
        u = json.loads(json.dumps(s))
        held = s["w"][0] != "Idle"
        kind = a[0] if isinstance(a, tuple) else a
        if kind == "WLock":
            if held:
                return None
            u["w"] = ["Locked", a[1]]
        elif kind == "WOut":
            if not (s["w"][0] == "Locked" and self.design in ("as-built", "probe")):
                return None
            k = s["w"][1]
            e = 1 if k == "Put" else 0
            u["w_undo"] = [e, e in s["out"]]
            o = set(s["out"])
            o = o | {1} if k == "Put" else o - {0}
            u["out"], u["w"] = sorted(o), ["Wrote", k]
        elif kind == "WBump":
            if s["w"][0] != "Wrote":
                return None
            u["token"] += 1
            u["w"] = ["Bumped", s["w"][1]]
        elif kind == "WCommit":
            if s["w"][0] != "Bumped":
                return None
            c = set(s["committed"])
            c = c | {1} if s["w"][1] == "Put" else c - {0}
            u["committed"], u["w"], u["w_undo"] = sorted(c), ["Idle", None], None
        elif kind == "WRollback":
            if not held:
                return None
            if s["w_undo"] is not None:
                e, present = s["w_undo"]
                o = set(s["out"])
                o = o | {e} if present else o - {e}
                u["out"] = sorted(o)
            u["w"], u["w_undo"] = ["Idle", None], None
        elif kind == "BToken":
            if s["b"] != "Idle":
                return None
            u["b_token"], u["b"] = s["token"], "Token"
        elif kind == "BProbe":
            if s["b"] != "Token" or self.design != "probe":
                return None
            u["b_got"], u["b"] = not held, "Probed"
        elif kind == "BCompute":
            ok = s["b"] == ("Probed" if self.design == "probe" else "Token")
            if not ok:
                return None
            u["b_payload"], u["b"] = list(s["out"]), "Computed"
        elif kind == "BStore":
            if s["b"] != "Computed":
                return None
            stores = True if self.design == "as-built" else (s["b_got"] and s["token"] == s["b_token"])
            if stores:
                u["cache"] = [s["b_token"], sorted(s["b_payload"])]
            u["b"], u["b_got"], u["b_payload"] = "Idle", False, []
        else:
            return None
        return u

    def invariants(self):
        def inv(s):
            if s["w"][0] != "Idle":
                return True
            if s["cache"] is not None and s["cache"][0] == s["token"]:
                return sorted(s["cache"][1]) == sorted(s["committed"])
            return True
        return [(self.INV, inv)]

    def obs(self, s):
        return (tuple(s["out"]), s["token"], None if s["cache"] is None else (s["cache"][0], tuple(sorted(s["cache"][1]))))

    def alpha(self, store, step):
        c = self._cache(store)
        return (tuple(self._out(store)), self._token(store), None if c is None else (c[0], tuple(sorted(c[1]))))

    def actions(self, step, seg, pre, post):
        t = step.get("token_op")
        if not t or not step["ok"]:
            return []
        if t == "WOpen":
            return [("WLock", "Put"), "WOut", "WBump"]
        if t == "WRollback":
            return ["WRollback"]
        if t == "Build":
            acts = ["BToken"] + (["BProbe"] if self.design == "probe" else []) + ["BCompute", "BStore"]
            return acts
        return []

    def relevant(self, ref):
        return ref.startswith('^IVG.AlgoCache') or ref.startswith('^KG("__version")') or ref.startswith('^KG("out"')
