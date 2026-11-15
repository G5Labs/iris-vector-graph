"""Module 09 compiled-plan machines from models/breadth-b/src/m09.rs (pin 3eaa79cf), transcribed for trace replay:
`planc` (m09.rs:73-306) and `mode` (m09.rs:334-397). Driven in AUDITC (orchestrator scope decision: the native
executor compiling its own generated plan classes IVGC.P<h> at run time is the product's normal operation).

Abstraction: an entry ^IVG.CypherCompiled(h) = $LB(class, shape, stamp, status, began) and its lines (h, "src", i)
from the replayed store; the generated classes IVGC.* and each one's Walk1 text from the step's reply (a read-only
%Dictionary query in the step's own process, after the call). Exploration bounds (drops, readers' anchors) lifted.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

import base64

from trlib import BITMAP, OPAQUE, Family, Store

ST = {"ok": "Ok", "pending": "Pending"}


def _st(v) -> str:
    v = "" if v is None else str(v)
    return ST.get(v, "Refused" if v else "Pending")


def lines_digest(lines: List[str]) -> str:
    """Digest of Walk1's lines, whitespace-normalised (the class text and the entry's src lines are compared)."""
    norm = [" ".join(str(x).split()) for x in lines]
    norm = [x for x in norm if x]
    return hashlib.sha256("\n".join(norm).encode()).hexdigest()[:16]


class Planc(Family):
    """m09.rs:73-306 `planc`, design AsBuilt/Reviewed, shapes 2, no collision (each shape its own slot), DropAll
    unlocked (as built). Ghosts: reader walks (`wrong`, `raised`), jobs' digests, drop epoch. Observation per slot:
    the entry (shape index, status, named, lines present) and the class IVGC.P<h> (absent / compiled from the
    entry's own current lines / from other lines)."""
    name = "planc"
    source = "models/breadth-b/src/m09.rs:73-306"
    P_I3 = "NAT-I3: a read never runs code written for another plan shape"
    P_BIND = "NAT-T5.16: an ok entry runs the class compiled from its own shape"
    P_I5 = "NAT-I5: after a DropAll no plan written before it is left"
    P_SHAPE = "P-0907: no entry has an undefined element"

    def __init__(self, design="as-built"):
        super().__init__()
        self.design = design
        self.name = f"planc[{design}]"
        self.slots: Dict[int, str] = {}
        self.shape_text: Dict[int, str] = {}
        self.classes: Dict[str, str] = {}

    def bind(self, trace):
        self.slots = {int(k): str(v) for k, v in trace["meta"].get("slots", {}).items()}
        self.shape_text = {int(k): str(v) for k, v in trace["meta"].get("shape_text", {}).items()}
        self.classes = dict(trace["meta"].get("classes_before", {}))

    # --- machine (transcribed; slot r = shape r)
    def init(self, store, trace):
        return {"entry": [None, None], "class": [None, None], "lock": [None, None], "jobs": [None, None],
                "reader": [["Idle"], ["Idle"]], "wrong": [False, False], "raised": [False, False], "epoch": 0,
                "drop_pc": 0}

    def _reviewed(self):
        return self.design != "as-built"

    def next(self, s, a):
        t = json.loads(json.dumps(s))
        kind = a[0]
        if kind == "For":
            r = a[1]
            if s["reader"][r][0] != "Idle":
                return None
            slot = r
            gen = None
            e = s["entry"][slot]
            job_alive = any(j is not None and j["slot"] == slot for j in s["jobs"])
            write = True
            if e is not None:
                if e["shape"] is None and not self._reviewed():
                    t["raised"][r] = True
                    write = False
                elif e["shape"] == r:
                    if e["status"] == "Ok":
                        if e["named"]:
                            gen = slot
                        write = False
                    elif e["status"] == "Refused":
                        write = False
                    elif job_alive:
                        write = False
            if write:
                t["entry"][slot] = {"shape": r, "status": "Pending", "named": False, "src": [r, s["epoch"]]}
                for j in range(2):
                    if t["jobs"][j] is None:
                        t["jobs"][j] = {"slot": slot, "digest": r, "pc": ["Start"]}
                        break
            t["reader"][r] = ["Walking", gen, 2]
        elif kind == "Walk":
            r = a[1]
            rd = s["reader"][r]
            if rd[0] != "Walking":
                return None
            gen, left = rd[1], rd[2]
            if gen is not None:
                c = s["class"][gen]
                if c is None:
                    t["reader"][r] = ["Idle"]
                    return t
                if c[0] != r:
                    t["wrong"][r] = True
            t["reader"][r] = ["Walking", gen, left - 1] if left > 1 else ["Idle"]
        elif kind == "JobLock":
            j = a[1]
            job = s["jobs"][j]
            if job is None or job["pc"][0] != "Start":
                return None
            slot = job["slot"]
            if s["lock"][slot] is not None:
                t["jobs"][j] = None
                return t
            e = s["entry"][slot]
            if e is not None and e["status"] == "Pending" and e["src"] is not None:
                lines, ep = e["src"]
                if lines != job["digest"]:
                    t["entry"][slot]["status"] = "Refused"
                    t["jobs"][j] = None
                else:
                    t["lock"][slot] = j
                    t["jobs"][j]["pc"] = ["Compiling", lines, ep]
            else:
                t["jobs"][j] = None
        elif kind == "JobCompile":
            j = a[1]
            job = s["jobs"][j]
            if job is None or job["pc"][0] != "Compiling":
                return None
            _, lines, ep = job["pc"]
            t["class"][job["slot"]] = [lines, ep]
            t["jobs"][j]["pc"] = ["Written", lines, ep]
        elif kind == "JobWrite":
            j = a[1]
            job = s["jobs"][j]
            if job is None or job["pc"][0] != "Written":
                return None
            lines = job["pc"][1]
            slot = job["slot"]
            if self._reviewed():
                e = t["entry"][slot]
                if e is not None and e["shape"] == lines and e["status"] == "Pending":
                    e["named"], e["status"] = True, "Ok"
                else:
                    t["class"][slot] = None
            else:
                if t["entry"][slot] is not None:
                    t["entry"][slot]["named"], t["entry"][slot]["status"] = True, "Ok"
                else:
                    t["entry"][slot] = {"shape": None, "status": "Ok", "named": True, "src": None}
            t["lock"][slot] = None
            t["jobs"][j] = None
        elif kind == "DropDelete":
            if self._reviewed() or s["drop_pc"] != 0:
                return None
            t["class"] = [None, None]
            t["drop_pc"] = 1
        elif kind == "DropKill":
            if self._reviewed() or s["drop_pc"] != 1:
                return None
            t["entry"] = [None, None]
            t["drop_pc"] = 0
            t["epoch"] += 1
        elif kind == "DropLocked":
            if not self._reviewed() or any(x is not None for x in s["lock"]):
                return None
            t["class"], t["entry"] = [None, None], [None, None]
            t["epoch"] += 1
        else:
            return None
        return t

    def invariants(self):
        def bind(s):
            for k in range(2):
                e, c = s["entry"][k], s["class"][k]
                if e and e["shape"] is not None and e["status"] == "Ok" and e["named"] and c is not None and c[0] != e["shape"]:
                    return False
            return True
        return [(self.P_I3, lambda s: not any(s["wrong"])), (self.P_BIND, bind),
                (self.P_I5, lambda s: s["drop_pc"] != 0 or s["epoch"] == 0 or
                 all(c is None or c[1] == s["epoch"] for c in s["class"])),
                (self.P_SHAPE, lambda s: all(not (e is not None and e["shape"] is None) for e in s["entry"]))]

    def obs(self, s):
        out = []
        for k in range(2):
            e, c = s["entry"][k], s["class"][k]
            eo = None if e is None else (e["shape"], e["status"], e["named"], e["src"] is not None)
            if c is None:
                co = None
            else:
                co = "own" if (e is not None and e["src"] is not None and list(e["src"]) == list(c)) else "other"
            out.append((eo, co))
        return tuple(out)

    # --- trace side
    def alpha(self, store: Store, step):
        if step is not None and isinstance(step.get("reply"), dict) and "classes" in step["reply"]:
            self.classes = dict(step["reply"]["classes"])
        out = []
        for k in range(2):
            h = self.slots.get(k)
            if h is None:
                out.append((None, None))
                continue
            v = store.get("^IVG.CypherCompiled", h)
            eo = None
            # the lines are ObjectScript text: read them as text (a line such as "\t\tSet ..." can tile as a $LB and
            # would be decoded as a list by trlib.decode's heuristic)
            pre = ("^IVG.CypherCompiled", str(h), "src")
            src_lines = [base64.b64decode(v2).decode("utf-8", "replace") for kk, v2 in
                         sorted(((k, v) for k, v in store.d.items() if k[:3] == pre and len(k) == 4 and v not in (OPAQUE, BITMAP)),
                                key=lambda kv: int(kv[0][3]))]
            if isinstance(v, tuple):
                shape_txt = v[1] if len(v) > 1 else None
                shape = None if shape_txt in (None,) else next((r for r, txt in self.shape_text.items() if txt == shape_txt), -1)
                named = len(v) > 0 and str(v[0]) == f"IVGC.P{h}"
                eo = (shape, _st(v[3] if len(v) > 3 else None), named, bool(src_lines))
            cls = self.classes.get(f"IVGC.P{h}")
            if cls is None:
                co = None
            else:
                co = "own" if (src_lines and cls == lines_digest([str(x) for x in src_lines])) else "other"
            out.append((eo, co))
        return tuple(out)

    def actions(self, step, seg, pre, post):
        p = step.get("planc")
        if not p or not step["ok"]:
            return []
        if p == "DropAll":
            return [("DropDelete",), ("DropKill",)] if not self._reviewed() else [("DropLocked",)]
        r = step["shape_index"]
        acts: List[Any] = [("For", r)]
        s = self.next(self.S, ("For", r))
        if s is not None:
            for j in range(2):
                if s["jobs"][j] is not None and (self.S["jobs"][j] is None):
                    acts += [("JobLock", j), ("JobCompile", j), ("JobWrite", j)]
        acts += [("Walk", r), ("Walk", r)]
        return acts

    def relevant(self, ref):
        return ref.startswith("^IVG.CypherCompiled")


MV = {None: "Undef", "": "Undef", "job": "Job", "sync": "Sync", "off": "Off"}


def _mv(v):
    return MV.get(v if v is None else str(v), "Unknown")


class Mode(Family):
    """m09.rs:334-397 `mode` (F-0903; NAT-X12, NAT-X11, NAT-B5.2). State: namespace mode ^IVG.CypherGen("mode"), the
    process mode (process-private ^||IVG.CypherGenMode, not journaled: ghost), the last read's (effective mode, where
    it built). A read's build place is read from the journal: an entry turned "ok" by the reader's own process =
    InReader; written pending by the reader and turned "ok" by another process = Background; no entry = Nothing."""
    name = "mode"
    source = "models/breadth-b/src/m09.rs:334-397"
    M_X12 = "NAT-X12: a read under an unknown namespace mode builds nothing"
    M_X11 = "NAT-X11: set other leaves the process mode unchanged"
    M_B52 = "NAT-B5.2: the process mode wins over the namespace mode"

    def __init__(self, design="as-built"):
        super().__init__()
        self.design = design
        self.name = f"mode[{design}]"
        self._built = None

    def init(self, store, trace):
        return {"ns": _mv(store.get("^IVG.CypherGen", "mode")), "proc": "Undef", "last": None}

    def next(self, s, a):
        t = dict(s)
        t["last"] = None
        kind = a[0]
        if kind == "SetNs":
            t["ns"] = a[1]
        elif kind == "SetProc":
            if a[1] != "Unknown":
                t["proc"] = a[1]
        elif kind == "ClearProc":
            t["proc"] = "Undef"
        elif kind == "Read":
            eff = s["proc"] if s["proc"] != "Undef" else (s["ns"] if s["ns"] != "Undef" else "Job")
            if eff == "Off":
                built = "Nothing"
            elif eff == "Job":
                built = "Background"
            elif eff == "Sync":
                built = "InReader"
            elif self.design == "as-built":
                built = "InReader"
            elif self.design == "reviewed":
                built = "Nothing"
            else:
                built = "Background"
            t["last"] = [eff, built]
        else:
            return None
        return t

    def action_properties(self):
        return [(self.M_X12, lambda s, a, t: a[0] != "Read" or not (t["last"] and t["last"][0] == "Unknown"
                                                                      and t["last"][1] != "Nothing")),
                (self.M_X11, lambda s, a, t: not (a[0] == "SetProc" and a[1] == "Unknown") or s["proc"] == t["proc"]),
                (self.M_B52, lambda s, a, t: a[0] != "Read" or s["proc"] == "Undef" or (t["last"] and t["last"][0] == s["proc"]))]

    def obs(self, s):
        return (s["ns"], None if s["last"] is None else tuple(s["last"]))

    def alpha(self, store, step):
        ns = _mv(store.get("^IVG.CypherGen", "mode"))
        last = None
        if step is not None and step.get("mode_op") == "Read" and step["ok"]:
            eff = _mv(step["reply"].get("effective")) if isinstance(step.get("reply"), dict) else None
            last = (eff, self._built)
        return (ns, last)

    def actions(self, step, seg, pre, post):
        op = step.get("mode_op")
        if not op:
            return []
        if op == "Read":
            if not step["ok"]:
                return []
            reader = step["pid"]
            oks, pend = set(), set()
            for r in seg:
                if not r["g"].startswith("^IVG.CypherCompiled(") or ",\"src\"" in r["g"] or r["t"] != "SET":
                    continue
                from trlib import decode
                v = decode(r["n"])
                if isinstance(v, tuple) and len(v) > 3:
                    (oks if str(v[3]) == "ok" else pend).add(r["p"])
            if not oks and not pend:
                self._built = "Nothing"
            elif oks and oks <= {reader}:
                self._built = "InReader"
            elif oks:
                self._built = "Background"
            else:
                self._built = "Nothing"
            return [("Read",)]
        if op == "SetNs":
            return [("SetNs", _mv(step.get("value")))]
        if op == "SetProc":
            return [("SetProc", _mv(step.get("value")))]
        if op == "ClearProc":
            return [("ClearProc",)]
        return []

    def relevant(self, ref):
        return ref.startswith("^IVG.CypherGen(")
