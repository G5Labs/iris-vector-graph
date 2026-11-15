"""Trace replay through the breadth machines (playbook §3.7 "trace replay of real runs through the machines").

Capture (live, namespace AUDITE, under `tools/locks.sh iris`):
    a scenario is a sequence of *steps*; each step runs one product entry point on its own IRIS connection (a fresh
    one, or a named persistent one for multi-step transactions), and a journal mark is taken after every step, so the
    journal records between two marks are exactly what that step wrote (traces/journal.py; the journal is written by
    the engine, not by the product or this harness). Before the first step every non-system global of the namespace
    is snapshotted with the Native API; after the last step it is snapshotted again (the engine's own final state).

Replay (offline, from the saved trace.json):
    1. the store is the before-snapshot; every journal record of every step is applied in journal order (SET sets a
       node, KILL removes a node and its subtree, ZKILL a node), and each record's journaled old value is checked
       against the replayed value of its node (continuity: a dropped, reordered or foreign record breaks it);
    2. frame: every global a step wrote is in the step's declared write footprint, and every writing process is one
       of the step's own processes;
    3. model: after each step the module's families map the step (its records, its reply) to one or more actions of
       the copied explorer machine (`models/breadth-*/src/<family>.rs`, transcribed into `families/*.py`), check every
       action is enabled (next() is defined) and compare the machine's observable projection with the abstraction
       alpha(store) of the replayed store;
    4. faithfulness: the replayed final store equals the engine's final snapshot.

Controls (seeded trace defects, `mutate`): a dropped record, two steps' records swapped, and a foreign write; each must
be flagged by the named rule.

Nothing is compiled into IRIS; the only writes are the product's own (through its public API) and the harness's
resets of the lane's own namespace.
"""
from __future__ import annotations

import base64
import copy
import json
import os
import re
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
for p in (str(ROOT / "tools"), str(ROOT / "traces"), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

import journal  # noqa: E402

# the lane's namespace (AUDITE); a follow-up may name another one the orchestrator assigned (TR_NAMESPACE=AUDITC
# for module 09's compiled plans)
NS = os.environ.get("TR_NAMESPACE", "AUDITE")
DB = f"/usr/irissys/mgr/{NS.lower()}/"
OPAQUE = "<opaque>"
LANE = "trace-replay"


def run_dir() -> Path:
    return Path(os.environ["RUN_DIR"]) / LANE


# ------------------------------------------------------------------------------------------------ global references

_TOKEN = re.compile(r'"((?:[^"]|"")*)"|\$c(?:har)?\(([\d,]+)\)|(-?(?:\d+(?:\.\d*)?|\.\d+)(?:E-?\d+)?)|(_)|(,)', re.I)


def canon(x: Any) -> str:
    """A subscript in IRIS canonical string form (numbers as IRIS prints them, strings as they are)."""
    if isinstance(x, bool):
        return "1" if x else "0"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        if x == int(x):
            return str(int(x))
        s = repr(x)
        if s.startswith("0."):
            s = s[1:]
        elif s.startswith("-0."):
            s = "-" + s[2:]
        return s
    return str(x)


def _num_canon(tok: str) -> str:
    if re.fullmatch(r"-?\d+", tok):
        return str(int(tok))
    try:
        return canon(float(tok))
    except ValueError:
        return tok


def parse_ref(ref: str) -> Tuple[str, ...]:
    """'^IVG.Ledger("tuple","x",$c(1),2)' -> ('^IVG.Ledger', 'tuple', 'x', '\\x01', '2')."""
    if ref.startswith('^["') or ref.startswith('^|'):
        close = "]" if ref.startswith('^["') else "|"
        ref = "^" + ref[ref.index(close, 2) + 1:]
    if "(" not in ref:
        return (ref,)
    root, body = ref.split("(", 1)
    body = body[:-1]
    subs: List[str] = []
    cur: Optional[str] = None
    pos = 0
    while pos < len(body):
        m = _TOKEN.match(body, pos)
        if not m:
            raise ValueError(f"cannot parse subscript in {ref!r} at {pos}")
        s, chars, num, cat, comma = m.groups()
        pos = m.end()
        if s is not None:
            piece = s.replace('""', '"')
        elif chars is not None:
            piece = "".join(chr(int(x)) for x in chars.split(","))
        elif num is not None:
            piece = _num_canon(num)
        elif cat:
            continue
        else:
            subs.append("" if cur is None else cur)
            cur = None
            continue
        cur = piece if cur is None else cur + piece
    subs.append("" if cur is None else cur)
    return (root,) + tuple(subs)


def key_str(k: Tuple[str, ...]) -> str:
    return json.dumps(list(k), ensure_ascii=False)


def key_of(s: str) -> Tuple[str, ...]:
    return tuple(json.loads(s))


# ------------------------------------------------------------------------------------------------ values

def decode(v: Optional[str]) -> Any:
    """A stored value (base64 of its bytes) as Python: a $LB list as a tuple (recursively), else text."""
    if v is None:
        return None
    if v == OPAQUE:
        return OPAQUE
    raw = base64.b64decode(v)
    return _decode_raw(raw)


def _decode_raw(raw: bytes) -> Any:
    if raw and _looks_like_list(raw):
        try:
            import iris
            lst = iris.IRISList(raw)
            n = lst.count()
            out = []
            for i in range(1, n + 1):
                x = lst.get(i)
                if isinstance(x, (bytes, bytearray)):
                    x = _decode_raw(bytes(x)) if _looks_like_list(bytes(x)) else bytes(x).decode("utf-8", "replace")
                out.append(x)
            return tuple(out)
        except Exception:  # noqa: BLE001
            pass
    return raw.decode("utf-8", "replace")


def _looks_like_list(raw: bytes) -> bool:
    """Walk $LB element headers; True only when they tile the whole byte string exactly."""
    i, n = 0, len(raw)
    if n < 1:
        return False
    while i < n:
        ln = raw[i]
        if ln == 0:
            if i + 3 > n:
                return False
            ln = raw[i + 1] | (raw[i + 2] << 8)
            hdr = 3
            if ln == 0:
                if i + 7 > n:
                    return False
                ln = int.from_bytes(raw[i + 3:i + 7], "little")
                hdr = 7
        else:
            hdr = 1
        if ln == 1 and hdr == 1:   # undefined element
            i += 1
            continue
        if ln < hdr + 1 or i + ln > n:
            return False
        typ = raw[i + hdr]
        if typ not in (1, 2, 4, 5, 6, 7, 8, 9, 12, 13):
            return False
        i += ln
    return i == n


# ------------------------------------------------------------------------------------------------ live capture

CATALOG_ROOTS = ("^odd", "^rMAC", "^rINC", "^rOBJ", "^rMAP", "^rINDEX", "^ROUTINE", "^mtemp")


def roots_of(c) -> List[str]:
    rows = c.sql(f"SELECT Name FROM %SYS.GlobalQuery_NameSpaceList('{NS}','*',0)")
    out = []
    for (name,) in rows:
        g = "^" + str(name)
        if g.startswith(journal.SYSTEM_GLOBAL_PREFIXES) or g.startswith(CATALOG_ROOTS):
            continue
        out.append(g)
    return sorted(out)


def snapshot(c, roots: Iterable[str]) -> Dict[str, str]:
    """{key_str: base64 value or OPAQUE} for every defined node of the given roots."""
    out: Dict[str, str] = {}
    o = c.o

    def walk(root: str, subs: Tuple):
        d = int(o.isDefined(root, *subs))
        if d in (1, 11):
            try:
                raw = o.getBytes(root, *subs)
                out[key_str((root,) + tuple(canon(s) for s in subs))] = \
                    base64.b64encode(raw).decode() if raw is not None else base64.b64encode(b"").decode()
            except Exception:  # noqa: BLE001  ($vector values cannot be read as bytes)
                out[key_str((root,) + tuple(canon(s) for s in subs))] = OPAQUE
        if d >= 10:
            # nextSubscript, not iterator(): the iterator fetches each node's value and fails on a $vector
            sub = o.nextSubscript(False, root, *subs, None)
            while sub is not None:
                walk(root, subs + (sub,))
                sub = o.nextSubscript(False, root, *subs, sub)
    for r in roots:
        walk(r, ())
    return out


def workers(c) -> List[str]:
    """Pids of the IRIS Work Queue Manager's worker jobs (they run SQL filer work, e.g. bitmap extents and index
    builds, on behalf of the process that queued it)."""
    return sorted(str(p) for (p,) in c.sql("SELECT Pid FROM %SYS.ProcessQuery WHERE Routine = '%SYS.WorkQueueMgr'"))


def layouts(c) -> Dict[str, Dict]:
    """SQL table -> {data: global, nodes: [{sub, structure, fields: {pos: sqlname} | field}]} for Graph_KG tables."""
    out: Dict[str, Dict] = {}
    classes = c.sql("SELECT c.Name, c.SqlSchemaName, c.SqlTableName, s.DataLocation FROM %Dictionary.CompiledClass c "
                    "JOIN %Dictionary.CompiledStorage s ON s.parent = c.Name WHERE c.SqlSchemaName = 'Graph_KG' "
                    "AND c.SqlTableName IS NOT NULL")
    for cls, schema, table, data in classes:
        props = dict(c.sql("SELECT Name, SqlFieldName FROM %Dictionary.CompiledProperty WHERE parent = ?", cls))
        nodes = []
        for name, sub, structure, attr in c.sql("SELECT Name, Subscript, Structure, Attribute FROM "
                                                "%Dictionary.CompiledStorageData WHERE parent %STARTSWITH ?", cls + "||"):
            vals = c.sql("SELECT Name, Value FROM %Dictionary.CompiledStorageDataValue WHERE parent %STARTSWITH ?",
                         f"{cls}||Default||{name}")
            nodes.append({"sub": None if sub in (None, "") else str(sub).strip('"'), "structure": str(structure),
                          "fields": {str(p): props.get(str(v), str(v)) for p, v in vals},
                          "field": props.get(str(attr), str(attr)) if attr else None})
        out[f"{schema}.{table}"] = {"class": str(cls), "data": str(data), "nodes": nodes}
    return out


class Capture:
    """Runs a scenario's steps and records the journal between marks."""

    def __init__(self, name: str, conn_factory: Callable[[], Any]):
        self.name = name
        self.Conn = conn_factory
        self.steps: List[Dict] = []
        self.meta: Dict[str, Any] = {}
        self.persistent: Dict[str, Any] = {}
        self.marks: List[Dict] = []

    def begin(self, roots: Optional[List[str]] = None):
        c = self.Conn()
        self.roots_complete = roots is None
        self.roots = roots or roots_of(c)
        self.smap = journal.storage_map(c)
        self.layouts = layouts(c)
        self.before = snapshot(c, self.roots)
        self.workers = workers(c)
        c.close()
        m = journal.mark()
        self.m0 = {"file": m.file, "address": m.address}
        self.t0 = time.time()

    def conn(self, who: str):
        if who not in self.persistent:
            self.persistent[who] = self.Conn()
        return self.persistent[who]

    def step(self, op: str, fn: Callable, who: Optional[str] = None, helpers: Iterable[str] = (), **info) -> Any:
        """Run fn(conn) as one step. `who` names a persistent connection; else a fresh one is opened and closed.
        fn may return (reply, extra_pids) to name other server processes the step used."""
        c = self.conn(who) if who else self.Conn()
        t = time.time()
        extra: List[str] = []
        try:
            res = fn(c)
            if isinstance(res, tuple) and len(res) == 2 and isinstance(res[1], list) and res[1] and \
                    all(isinstance(p, str) and p.isdigit() for p in res[1]):
                res, extra = res
            ok, err = True, None
        except Exception as ex:  # noqa: BLE001
            res, ok, err = None, False, f"{type(ex).__name__}: {str(ex)[:400]}"
        if not who:
            c.close()
        m = journal.mark()
        rec = {"i": len(self.steps), "op": op, "who": who, "pid": c.pid, "pids": [c.pid] + extra,
               "helpers": list(helpers), "ok": ok, "error": err, "reply": _jsonable(res),
               "seconds": round(time.time() - t, 3), "mark": {"file": m.file, "address": m.address}, **info}
        self.steps.append(rec)
        print(f"  step {rec['i']:>2} {op:<28} pid {c.pid} ok={ok} {err or ''} {str(rec['reply'])[:120]}", flush=True)
        return res

    def end(self, out: Path) -> Dict:
        for c in self.persistent.values():
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        c = self.Conn()
        final = snapshot(c, sorted(set(self.roots) | set(roots_of(c))))
        self.workers = sorted(set(self.workers) | set(workers(c)))
        c.close()
        recs = journal.records_since(journal.Mark(self.m0["file"], self.m0["address"]), dbs={DB})
        files = {self.m0["file"]} | {s["mark"]["file"] for s in self.steps}
        if not self.roots_complete:
            final = {k: v for k, v in final.items() if key_of(k)[0] in set(self.roots)}
        trace = {"name": self.name, "namespace": NS, "db": DB, "roots": self.roots,
                 "roots_complete": self.roots_complete, "smap": self.smap,
                 "layouts": self.layouts, "before": self.before, "final": final, "m0": self.m0,
                 "steps": self.steps, "meta": self.meta, "journal": recs, "journal_files": sorted(files),
                 "workers": self.workers,
                 "seconds": round(time.time() - self.t0, 2)}
        out.mkdir(parents=True, exist_ok=True)
        (out / "trace.json").write_text(json.dumps(trace, default=str))
        return trace


def _jsonable(x):
    try:
        json.dumps(x)
        return x
    except TypeError:
        if isinstance(x, (list, tuple)):
            return [_jsonable(y) for y in x]
        if isinstance(x, dict):
            return {str(k): _jsonable(v) for k, v in x.items()}
        return str(x)


# ------------------------------------------------------------------------------------------------ store view

class Store:
    """The replayed store: {key tuple: base64 value | OPAQUE} with read helpers for globals and SQL rows."""

    def __init__(self, data: Dict[Tuple, str], layouts: Dict[str, Dict], smap: Dict[str, str]):
        self.d = data
        self.layouts = layouts
        self.smap = smap

    def copy(self) -> "Store":
        return Store(dict(self.d), self.layouts, self.smap)

    def get(self, *key) -> Any:
        k = tuple(canon(x) for x in key)
        return decode(self.d.get(k))

    def has(self, *key) -> bool:
        return tuple(canon(x) for x in key) in self.d

    def under(self, *prefix) -> Dict[Tuple, Any]:
        p = tuple(canon(x) for x in prefix)
        return {k: decode(v) for k, v in self.d.items() if k[:len(p)] == p}

    def subtree_defined(self, *prefix) -> bool:
        p = tuple(canon(x) for x in prefix)
        return any(k[:len(p)] == p for k in self.d)

    def rows(self, table: str) -> List[Dict]:
        lay = self.layouts[table]
        root = lay["data"]
        byid: Dict[str, Dict] = defaultdict(dict)
        for k, v in self.d.items():
            if k[0] != root or len(k) < 2:
                continue
            rid = k[1]
            for node in lay["nodes"]:
                if node["sub"] is None and len(k) == 2:
                    val = decode(v)
                    if isinstance(val, tuple):
                        for pos, f in node["fields"].items():
                            i = int(pos)
                            x = val[i - 1] if i - 1 < len(val) else None
                            byid[rid][f] = "" if x == "\x00" else x   # SQL '' is stored as $c(0)
                    byid[rid]["_id"] = rid
                elif node["sub"] is not None and len(k) == 3 and k[2] == node["sub"]:
                    byid[rid][node["field"] or node["sub"]] = decode(v)
        return [r for r in byid.values() if "_id" in r]


# ------------------------------------------------------------------------------------------------ replay

BITMAP = "<bitmap>"
# class-dictionary globals a product DDL statement writes (traces/journal.py's system list lacks ^oddTSQL): the SQL
# catalog, not data any machine reads; dropped from the replay like the other system globals
CATALOG = ("^odd", "^rMAC", "^rINC", "^rOBJ", "^rMAP", "^rINDEX", "^ROUTINE", "^mtemp")
# (the code globals were added for module 09: the native executor compiles its generated plan classes IVGC.P<h> at
# run time, which writes the class dictionary and the routine globals of the namespace)


def apply(d: Dict[Tuple, str], rec: Dict) -> None:
    k = parse_ref(rec["g"])
    t = rec["t"]
    if t.startswith("BitSET"):
        # a $BIT change: the journal reader (traces/journal.py) reports the bit's value, not its position, so the
        # node's whole value is not reconstructible; bitmap index chunks are derived data no machine reads
        d[k] = BITMAP
    elif t.startswith(("SET", "VecSET", "Vector")):
        d[k] = OPAQUE if rec.get("opaque") and rec["n"] is None else (rec["n"] if rec["n"] is not None else
                                                                        base64.b64encode(b"").decode())
    elif t == "ZKILL" or t.startswith("KillDes"):
        d.pop(k, None)
    elif t.startswith("KILL"):
        for kk in [kk for kk in d if kk[:len(k)] == k]:
            del d[kk]
    else:
        raise ValueError(f"unknown journal record type {t}")


def continuity(d: Dict[Tuple, str], rec: Dict) -> Optional[str]:
    """The record's journaled old value must be the replayed value of its node (when the journal carries it)."""
    if rec.get("opaque") or rec["t"].startswith("BitSET"):
        return None
    k = parse_ref(rec["g"])
    cur = d.get(k)
    if cur in (OPAQUE, BITMAP):
        return None
    o = rec["o"]
    if o is not None:
        if cur is None:
            return f"old value of {rec['g'][:90]} is journaled but the node is undefined in the replay"
        if cur != o and decode(cur) != decode(o):
            return f"old value of {rec['g'][:90]} differs from the replayed value"
    return None


_DDL_GLOBAL = re.compile(r"^\^t52S\.[A-Za-z0-9]+\.")


def _store(ref: str, smap: Dict[str, str]) -> str:
    """journal.store_of, plus: a hashed DDL table global absent from the storage map read at the capture's start
    belongs to a table the trace itself created (a routed vector table, kg_emb_<hash>)."""
    s = journal.store_of(ref, smap)
    if s.startswith("global:^t52S.") and _DDL_GLOBAL.match(journal.global_root(ref) + "."):
        return "sql:Graph_KG.<table created during the trace>"
    return s


def owned_by_step(trace: Dict) -> List[List[Dict]]:
    """Journal records per step, by the marks (records after mark i-1 and up to mark i belong to step i)."""
    marks = [trace["m0"]["address"]] + [s["mark"]["address"] for s in trace["steps"]]
    files = trace.get("journal_files") or []
    if len(files) > 1:
        raise RuntimeError(f"capture spans journal files {files}: segment by address is not defined")
    segs: List[List[Dict]] = [[] for _ in trace["steps"]]
    for r in trace["journal"]:
        for i in range(len(trace["steps"])):
            if marks[i] < r["a"] <= marks[i + 1]:
                segs[i].append(r)
                break
    return segs


class At:
    """An action with the abstraction expected right after it (a transaction boundary inside a step)."""

    def __init__(self, action, alpha):
        self.action, self.alpha = action, alpha

    def __repr__(self):
        return f"At({self.action!r})"


def stores_at_units(pre: "Store", seg: List[Dict]) -> List[Tuple[Dict, "Store"]]:
    """(unit, store right after the unit's last record or end marker) for every unit of a step, in journal order."""
    units = journal.transactions(seg)
    ends = sorted(units, key=lambda u: u.get("end") or u.get("begin") or 0)
    out = []
    st = pre.copy()
    pos = 0
    recs = [r for r in seg]
    for u in ends:
        end = u.get("end") or (u["records"][-1]["a"] if u["records"] else u.get("begin") or 0)
        while pos < len(recs) and recs[pos]["a"] <= end:
            if recs[pos]["g"]:
                apply(st.d, recs[pos])
            pos += 1
        out.append((u, st.copy()))
    return out


class Family:
    """One explorer family, transcribed. Subclasses define init/next/obs/alpha/invariants and the step mapping."""
    name = "?"
    source = "?"
    design = "as-built"

    def __init__(self):
        self.S = None

    def bind(self, trace: Dict) -> None:
        """Called before any other method with the whole trace (layouts, meta)."""

    def init(self, store: Store, trace: Dict) -> Any:
        raise NotImplementedError

    def actions(self, step: Dict, seg: List[Dict], pre: Store, post: Store) -> List[Any]:
        """Model actions this step performs (empty: the step is outside the family)."""
        return []

    def next(self, S, a) -> Optional[Any]:
        raise NotImplementedError

    def obs(self, S) -> Any:
        raise NotImplementedError

    def alpha(self, store: Store, step: Optional[Dict]) -> Any:
        raise NotImplementedError

    def invariants(self) -> List[Tuple[str, Callable[[Any], bool]]]:
        return []

    def action_properties(self) -> List[Tuple[str, Callable[[Any, Any, Any], bool]]]:
        return []

    def relevant(self, ref: str) -> bool:
        """Journal global refs whose records the family's abstraction reads (for the dropped-record control)."""
        return False


def check(trace: Dict, families: List[Family], footprint: Dict[str, set], quiet: bool = False) -> Dict:
    """Replay a captured trace through the families. Returns a report with violations by rule."""
    layouts_, smap = trace["layouts"], trace["smap"]
    d0 = {key_of(k): v for k, v in trace["before"].items()}
    store = Store(dict(d0), layouts_, smap)
    segs = trace.get("_segments") or owned_by_step(trace)
    rep: Dict[str, Any] = {"steps": [], "violations": [], "rules": Counter(), "model_steps": Counter(),
                           "invariant_violations": [], "unmapped_writes": []}

    def flag(rule: str, msg: str):
        rep["violations"].append({"rule": rule, "msg": msg})
        rep["rules"][rule] += 1

    for f in families:
        f.bind(trace)
    for f in families:
        f.S = f.init(store, trace)
        a = f.alpha(store, None)
        if f.obs(f.S) != a:
            flag("model-post-state", f"{f.name}: initial state {f.obs(f.S)} != alpha {a}")
    for i, step in enumerate(trace["steps"]):
        seg = segs[i]
        pre = store.copy()
        seg = [r for r in seg if not (r["g"] or "").startswith(CATALOG)]
        for r in seg:
            if not r["g"]:
                continue
            msg = continuity(store.d, r)
            if msg:
                flag("continuity", f"step {i} {step['op']}: {msg}")
            apply(store.d, r)
        # frame
        allowed = footprint.get(step["op"], footprint.get("*", set()))
        written = sorted({_store(r["g"], smap) for r in seg if r["g"]})
        outside = [s for s in written if s not in allowed and not any(s.startswith(a[:-1]) for a in allowed if a.endswith("*"))]
        if outside:
            flag("frame", f"step {i} {step['op']}: wrote outside its footprint: {outside}")
        pids = set(step.get("pids") or [step["pid"]]) | set(trace.get("workers") or [])
        foreign = sorted({r["p"] for r in seg if r["g"] and r["p"] not in pids and not step.get("helpers_any")})
        if foreign:
            flag("foreign-process", f"step {i} {step['op']}: records by processes {foreign} not of this step")
        units = journal.transactions(seg)
        srep = {"i": i, "op": step["op"], "ok": step["ok"], "records": len(seg),
                "txns": [{"pid": u["pid"], "kind": u["kind"], "committed": u["committed"],
                          "rolled_back": u.get("rolled_back"), "records": len(u["records"]),
                          "nested_levels": u.get("nested_levels")} for u in units if u["kind"] == "txn"],
                "auto_records": sum(1 for u in units if u["kind"] == "auto"), "stores": written, "families": {}}
        mapped_any = False
        for f in families:
            acts = f.actions(step, seg, pre, store)
            if not acts:
                continue
            mapped_any = True
            S = f.S
            trail = []
            for a in acts:
                checkpoint = None
                if isinstance(a, At):
                    a, checkpoint = a.action, a.alpha
                if isinstance(a, list):   # actions given in a step's info come back from JSON as lists
                    a = tuple(a)
                S2 = f.next(S, a)
                if S2 is None:
                    flag("model-not-enabled", f"step {i} {step['op']}: {f.name} action {a} not enabled in {f.obs(S)}")
                    break
                trail.append(str(a))
                for name, prop in f.action_properties():
                    if not prop(S, a, S2):
                        rep["invariant_violations"].append({"step": i, "op": step["op"], "family": f.name,
                                                            "property": name, "action": str(a),
                                                            "state": str(f.obs(S2))})
                S = S2
                rep["model_steps"][f.name] += 1
                if checkpoint is not None and f.obs(S) != checkpoint:
                    flag("model-post-state", f"step {i} {step['op']}: {f.name} after {a}: model {f.obs(S)} != "
                         f"alpha at the transaction's end {checkpoint}")
                for name, inv in f.invariants():
                    if not inv(S):
                        rep["invariant_violations"].append({"step": i, "op": step["op"], "family": f.name,
                                                            "invariant": name, "state": str(f.obs(S))})
            f.S = S
            a = f.alpha(store, step)
            match = f.obs(S) == a
            if not match:
                flag("model-post-state", f"step {i} {step['op']}: {f.name} model {f.obs(S)} != alpha {a}")
            srep["families"][f.name] = {"actions": trail, "obs": str(f.obs(S)), "alpha": str(a), "match": match}
        if not mapped_any and seg:
            rel = [r for r in seg if r["g"] and any(f.relevant(r["g"]) for f in families)]
            if rel and journal.net_effect(rel) and not step.get("harness"):
                flag("unmapped-transaction", f"step {i} {step['op']}: {len(rel)} model-relevant records but no model action")
            rep["unmapped_writes"].append({"step": i, "op": step["op"], "records": len(seg),
                                           "model_relevant": len(rel)})
        rep["steps"].append(srep)
    # faithfulness
    final = {key_of(k): v for k, v in trace["final"].items()}
    if trace.get("roots_complete", True):
        roots = set(trace["roots"]) | {k[0] for k in final} | {k[0] for k in store.d}
    else:
        roots = set(trace["roots"])
        outside = sorted({journal.global_root(r["g"]) for seg in segs for r in seg if r["g"]} - roots)
        if outside:
            flag("unsnapshotted-root", f"journal writes to roots outside the snapshot: {outside[:6]}")
    diff = []
    bitmaps = {k for k, v in store.d.items() if v == BITMAP}
    rep["bitmap_nodes_not_replayed"] = len(bitmaps)
    for k in set(store.d) | set(final):
        if k[0] not in roots or k in bitmaps or k[0].startswith(CATALOG):
            continue
        a, b = store.d.get(k), final.get(k)
        if a == b:
            continue
        if OPAQUE in (a, b) and a is not None and b is not None:
            continue
        if a is not None and b is not None and decode(a) == decode(b):
            continue
        diff.append(k)
    if diff:
        flag("faithfulness", f"replayed final store differs from the engine's at {len(diff)} nodes, e.g. "
             f"{[key_str(k)[:100] for k in sorted(diff)[:4]]}")
    rep["replay_matches_engine"] = not diff
    rep["rules"] = dict(rep["rules"])
    rep["model_steps"] = dict(rep["model_steps"])
    rep["records"] = sum(len(s) for s in segs)
    return rep


# ------------------------------------------------------------------------------------------------ controls

def mutate(trace: Dict, kind: str, families: List[Family], footprint: Dict[str, set],
           pair: Optional[Any] = None) -> Tuple[Dict, str]:
    """`pair`: for reordered-transaction the two steps to swap; for dropped-record a substring the dropped record's
    global reference must contain (both named by a scenario, CONTROL_PAIRS; default: the first candidate)."""
    """Seeded trace defects. Returns (mutated trace, description). Raises LookupError when not applicable."""
    t = copy.deepcopy(trace)
    for f in families:
        f.bind(t)
    segs = owned_by_step(t)
    rel = lambda r: r["g"] and any(f.relevant(r["g"]) for f in families)  # noqa: E731
    if kind == "dropped-record":
        for i, seg in enumerate(segs):
            for j, r in enumerate(seg):
                if rel(r) and r["t"].startswith("SET") and not r.get("opaque") and (pair is None or pair in r["g"]):
                    del seg[j]
                    t["_segments"] = segs
                    return t, f"dropped record {r['a']} {r['t']} {r['g'][:80]} of step {i} {t['steps'][i]['op']}"
    elif kind == "reordered-transaction" and pair is not None:
        # a scenario names the two steps to swap (used where the default choice would swap two steps the machine
        # cannot tell apart: two identical actions commute)
        x, y = pair
        segs[x], segs[y] = segs[y], segs[x]
        t["_segments"] = segs
        return t, (f"swapped the records of step {x} {t['steps'][x]['op']} and step {y} {t['steps'][y]['op']} "
                   f"(pair named by the scenario)")
    elif kind == "reordered-transaction":
        cand = [i for i, seg in enumerate(segs) if any(rel(r) for r in seg)]
        pairs = list(zip(cand, cand[1:]))
        # prefer two steps that write a common node (their order is then visible in the values)
        pairs.sort(key=lambda xy: not ({r["g"] for r in segs[xy[0]] if rel(r)} & {r["g"] for r in segs[xy[1]] if rel(r)}))
        for x, y in pairs:
            segs[x], segs[y] = segs[y], segs[x]
            t["_segments"] = segs
            return t, f"swapped the records of step {x} {t['steps'][x]['op']} and step {y} {t['steps'][y]['op']}"
        # one step with one transaction: swap two records of that step that write one node with different values
        for i, seg in enumerate(segs):
            byg: Dict[str, List[int]] = {}
            for j, r in enumerate(seg):
                if rel(r) and r["t"].startswith("SET") and not r.get("opaque"):
                    byg.setdefault(r["g"], []).append(j)
            for g, js in byg.items():
                if len(js) >= 2 and seg[js[0]]["n"] != seg[js[-1]]["n"] and len(
                        [u for u in journal.transactions(seg) if u["kind"] == "txn" and any(rel(r) for r in u["records"])]) < 2:
                    a, b = js[0], js[-1]
                    ra, rb = dict(seg[a]), dict(seg[b])
                    seg[a], seg[b] = dict(rb, a=ra["a"]), dict(ra, a=rb["a"])
                    t["_segments"] = segs
                    return t, f"swapped two writes of {g[:60]} in step {i} {t['steps'][i]['op']}"
        # one step only: swap two of its transactions (their whole blocks, markers included)
        for i, seg in enumerate(segs):
            units = [u for u in journal.transactions(seg) if u["kind"] == "txn" and any(rel(r) for r in u["records"])]
            if len(units) < 2:
                continue
            u1, u2 = units[0], units[1]

            def block(u):
                return [r for r in seg if r["p"] == u["pid"] and u["begin"] <= r["a"] <= (u.get("end") or 10 ** 18)]
            b1, b2 = block(u1), block(u2)
            ids1, ids2 = {id(r) for r in b1}, {id(r) for r in b2}
            out, done1, done2 = [], False, False
            for r in seg:
                if id(r) in ids1:
                    if not done1:
                        out.extend(b2)
                        done1 = True
                    continue
                if id(r) in ids2:
                    if not done2:
                        out.extend(b1)
                        done2 = True
                    continue
                out.append(r)
            addrs = sorted(r["a"] for r in seg)
            out = [dict(r, a=a) for r, a in zip(out, addrs)]
            segs[i] = out
            t["_segments"] = segs
            return t, (f"swapped two transactions of step {i} {t['steps'][i]['op']}: pid {u1['pid']} "
                       f"({len(b1)} records) and pid {u2['pid']} ({len(b2)} records)")
    elif kind == "foreign-write":
        for i, seg in enumerate(segs):
            for j, r in enumerate(seg):
                if rel(r):
                    allowed = footprint.get(t["steps"][i]["op"], footprint.get("*", set()))
                    fake = dict(r)
                    fake["p"] = "999999"
                    fake["a"] = r["a"]
                    seg.insert(j + 1, fake)
                    t["_segments"] = segs
                    return t, (f"inserted a copy of record {r['a']} ({r['g'][:60]}) written by process 999999 into step "
                               f"{i} {t['steps'][i]['op']}")
    raise LookupError(f"control {kind} not applicable")


CONTROLS = {"dropped-record": {"model-post-state", "continuity", "faithfulness"},
            "reordered-transaction": {"model-post-state", "model-not-enabled", "continuity"},
            "foreign-write": {"foreign-process"}}


def run_controls(trace: Dict, families_factory: Callable[[], List[Family]], footprint: Dict[str, set],
                 pairs: Optional[Dict[str, Tuple[int, int]]] = None) -> Dict:
    out = {}
    for kind, expected in CONTROLS.items():
        fams = families_factory()
        try:
            mt, desc = mutate(trace, kind, fams, footprint, (pairs or {}).get(kind))
        except LookupError as ex:
            out[kind] = {"applicable": False, "detail": str(ex), "caught": False}
            continue
        r = check(mt, families_factory(), footprint, quiet=True)
        fired = set(r["rules"])
        hit = sorted(fired & expected)
        out[kind] = {"applicable": True, "mutation": desc, "rules_fired": sorted(fired), "expected_any_of": sorted(expected),
                     "caught": bool(hit), "first": [v["msg"][:240] for v in r["violations"] if v["rule"] in expected][:2]}
    return out


# ------------------------------------------------------------------------------------------------ declared footprints

_ROOT_RE = re.compile(r"\^(?!\|\|)([A-Za-z%][A-Za-z0-9.]*)")
_TABLE_RE = re.compile(r"(Graph_KG\.[A-Za-z_]+|Graph_KG\.<dynamic[^>]*>|Graph_KG\.kg_emb_<route>|Graph_KG\.kg_eemb_<route>)")


def _norm_store(text: str) -> List[str]:
    out = []
    t = str(text)
    if "process-private" in t or t.startswith("global:^||") or "^IRIS.IF" in t:
        return out
    for m in _TABLE_RE.finditer(t):
        name = m.group(1)
        out.append("sql:Graph_KG.*" if "<" in name else "sql:" + name)
    if t.startswith("sql:") or t.startswith("Graph_KG."):
        return out
    for m in _ROOT_RE.finditer(t):
        out.append("global:^" + m.group(1).rstrip("."))
    return out


def declared(nn: str, entries: Iterable[str]) -> set:
    """Union of the declared write stores of the named entry points of footprints/NN.json (as journal.store_of
    names; table globals by table). Raises KeyError for an entry the file does not have."""
    d = json.loads((ROOT / "footprints" / f"{nn}.json").read_text())
    eps = d.get("entry_points") or d.get("entries") or []
    by = {}
    for e in eps:
        by[e.get("id") or e.get("entry")] = e
    out: set = set()
    for name in entries:
        e = by[name]
        w = e.get("writes")
        items: List[str] = []
        if isinstance(w, dict):
            items = []
            for x in w.get("tables", []):
                name = str(x).split()[0]
                items.append("sql:" + (name if name.startswith("Graph_KG.") else "Graph_KG." + name))
            items += list(w.get("globals", []))
        elif isinstance(w, list):
            items = [x["store"] if isinstance(x, dict) else x for x in w]
        for it in items:
            out.update(_norm_store(it))
    return out
