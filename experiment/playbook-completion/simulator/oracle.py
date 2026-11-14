"""Independent oracle for the simulator (playbook §5c).

Input: a recorded trace (sim.py): the ledger and content-table state before the schedule, the IRIS journal records
since the mark (traces/journal.py), the workers' operation events and the quiescent observations. Nothing here calls
the product. The journal is replayed, outermost transaction by transaction in commit order, onto the recorded
initial state of ^IVG.Ledger, ^Graph.KG.LedgerRevisionD and the data globals of Graph_KG.nodes / rdf_edges /
rdf_labels / rdf_props; every unit is attributed to the operation that ran it by the worker's scratch markers
(^IVGAuditSim(w, i, attempt, "b"|"e") in the same process's journal stream). After every committed unit the global
invariants are checked on the replayed state; a violation is counted once, at the unit that introduced it.

Invariants (sources: spec 213 / 256, ADR-0013, the audit's ERS/RED/LED rules):
  I1 STMT-TUPLE   every ("tuple", s,p,o,gkey) names a live ("stmt") of that tuple, and every live statement has it
  I2 ERS-I3       every live edge row written by a ledger commit has a live statement entry for its tuple
  I2b STMT-ROW    every live statement has a live edge row (the converse; a direct delete breaks it, F-0303)
  I3 RED-B1.1     no tombstone written by a redaction batch is of content live when that batch commits
  I3b RED-I1      a tombstone belongs to the target of the redaction that wrote it (spec 256 FR-002 predicate)
  I4 MARKER       a batch that tombstones runs under its own target's marker; a Final removes only its own marker
  I5 AUDIT        the redaction revision's per-revision counts equal the tombstones its own target's run wrote
  I6 SC-001       once every target of a tenant has completed (erase + complete redaction), no string of the tenant
                  remains in ^IVG.Ledger or in Graph_KG.ledger_revisions (replayed ^Graph.KG.LedgerRevisionD)
  I7 VERIFY       at each quiescent point verify() equals the oracle's replay-vs-tables comparison
  I8 IDEM         an idempotency key binds one fingerprint and one revision; a replay returns that revision and
                  writes no content; a redacted key is never bound again
  I9 READER       a reconstruct() answer equals the oracle's reconstruction at some committed point of its interval
  ADJ             (quiescent) every live edge row has its ^KG("out") adjacency entry
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "traces"))
from conformance import parse_ref  # noqa: E402  (pure parser of journal global references)
import journal  # noqa: E402

import iris  # noqa: E402  (IRISList decoder only)

LEDGER = "^IVG.Ledger"
REVD = "^Graph.KG.LedgerRevisionD"
MARK = "^IVGAuditSim"
DATA = {"^t52S.XCFT.1": "nodes", "^t52S.BWr6.1": "edges", "^t52S.CLwA.1": "labels", "^t52S.DMCe.1": "props"}
TENANT_NAMES = ("acme", "beta", "gamma")
DEFAULT_KEY = "\x01"   # the ledger's subscript for the default graph (Graph.KG.GraphKey LEDGERDEFAULT)


def relevant_roots():
    return {LEDGER, REVD, MARK, *DATA}


# ------------------------------------------------------------------------------------------------ decoding

def _el(v):
    if v is None:
        return ""
    if isinstance(v, (bytes, bytearray)):
        return bytes(v).decode("utf-8", "replace")
    return v


def as_list(raw: Optional[bytes]) -> Optional[Tuple]:
    if raw is None:
        return None
    try:
        lst = iris.IRISList(raw)
        return tuple(_el(lst.get(i)) for i in range(1, lst.count() + 1))
    except Exception:  # noqa: BLE001
        return None


def ledger_value(subs: Tuple, b64: Optional[str]):
    raw = None if b64 is None else base64.b64decode(b64)
    if subs and ((subs[0] == "rec" and len(subs) == 3) or (subs[0] == "stmt" and len(subs) == 2)
                 or (subs[0] == "idem" and len(subs) == 2) or subs == ("redacting",)):
        v = as_list(raw)
        if v is not None:
            return v
    return "" if raw is None else raw.decode("utf-8", "replace")


def norm_graph(g) -> str:
    return "" if g in (None, "", "\x00") else str(g)


def gkey(g) -> str:
    g = norm_graph(g).replace("\x00", "")
    return DEFAULT_KEY if g == "" else g


def enc_val(e) -> Optional[str]:
    """A record's encoded value: "N" is null, "S"_text is a string."""
    e = "" if e is None else str(e)
    if e.startswith("N"):
        return None
    return e[1:] if e.startswith("S") else e


def tuple_of(enc) -> Optional[Tuple[str, str, str, str]]:
    v = enc_val(enc)
    if not v:
        return None
    try:
        d = json.loads(v)
    except Exception:  # noqa: BLE001
        return None
    return str(d.get("s", "")), str(d.get("p", "")), str(d.get("o", "")), norm_graph(d.get("graph"))


def target_digest(graph: Optional[str], prefix: Optional[str], sep: str = "|") -> Tuple[str, str, str]:
    """(digest, graph name, match string) of a redaction target, from spec 256's definition of the target."""
    name = ("" if graph is None else str(graph)).replace("\x00", "")
    match = ""
    if prefix:
        match = prefix if prefix.endswith(sep) else prefix + sep
    d = hashlib.sha256((name + "\x00" + match).encode("utf-8")).hexdigest()
    return d, name, match


# ------------------------------------------------------------------------------------------------ state

class State:
    def __init__(self) -> None:
        self.L: Dict[Tuple, Any] = {}
        self.R: Dict[Tuple, Any] = {}
        self.T: Dict[str, Dict[Any, Tuple]] = {t: {} for t in DATA.values()}
        self.recorded_edges: set = set()           # rowids of edge rows a ledger commit wrote
        self.stmt_tuple: Dict[str, Tuple] = {}     # every statement id ever seen -> tuple (incl. tombstoned ones)

    def load(self, obs: Dict) -> None:
        for ref, b64 in obs["L"]:
            _, subs = parse_ref(ref)
            self.L[subs] = ledger_value(subs, b64)
        for ref, b64 in obs["R"]:
            _, subs = parse_ref(ref)
            self.R[subs] = as_list(base64.b64decode(b64)) if b64 else ""
        t = obs["tables"]
        for rid, nid, g in t["nodes"]:
            self.T["nodes"][int(rid)] = (str(nid), norm_graph(g))
        for rid, g, s, p, o, _q in t["edges"]:
            self.T["edges"][int(rid)] = (norm_graph(g), str(s), str(p), str(o))
        for rid, g, s, label in t["labels"]:
            self.T["labels"][int(rid)] = (norm_graph(g), str(s), str(label))
        for rid, g, s, k, v in t["props"]:
            self.T["props"][int(rid)] = (norm_graph(g), str(s), str(k), "" if v is None else str(v))
        self.learn_stmts()

    def learn_stmts(self, keys=None) -> None:
        for k in (keys if keys is not None else list(self.L)):
            v = self.L.get(k)
            if len(k) == 3 and k[0] == "rec" and isinstance(v, tuple) and len(v) >= 6:
                if v[0] == "create_rel":
                    t = tuple_of(v[5])
                elif v[0] == "delete_rel":
                    t = tuple_of(v[4])
                else:
                    t = None
                if t:
                    self.stmt_tuple[str(v[2])] = t
            if len(k) == 2 and k[0] == "stmt" and isinstance(v, tuple) and len(v) >= 4:
                self.stmt_tuple.setdefault(str(k[1]), (str(v[0]), str(v[1]), str(v[2]), norm_graph(v[3])))

    def apply(self, r: Dict) -> Optional[Tuple]:
        g = r["g"]
        if not g:
            return None
        root, subs = parse_ref(g)
        typ = r["t"]
        is_set = typ.startswith("SET") and not typ.startswith("SETbit")
        is_kill = typ.startswith("KILL") or typ.startswith("ZKILL")
        if root == LEDGER:
            if is_set:
                self.L[subs] = ledger_value(subs, r["n"])
            elif is_kill:
                if typ.startswith("ZKILL"):
                    self.L.pop(subs, None)
                else:
                    for k in [k for k in self.L if k[:len(subs)] == subs]:
                        del self.L[k]
            return ("L", subs, typ)
        if root == REVD:
            if is_set and len(subs) == 1:
                self.R[subs] = as_list(base64.b64decode(r["n"])) if r["n"] else ""
            elif is_kill and len(subs) == 1:
                self.R.pop(subs, None)
            return ("R", subs, typ)
        if root in DATA and len(subs) == 1:
            table = DATA[root]
            rid = subs[0]
            if is_set:
                row = as_list(base64.b64decode(r["n"])) if r["n"] else None
                if row is None:
                    return None
                if table == "nodes":
                    self.T[table][rid] = (str(row[0]), norm_graph(row[1] if len(row) > 1 else ""))
                elif table == "edges":
                    self.T[table][rid] = (norm_graph(row[0]), str(row[1]), str(row[2]), str(row[3]))
                elif table == "labels":
                    self.T[table][rid] = (norm_graph(row[0]), str(row[1]), str(row[2]))
                else:
                    self.T[table][rid] = (norm_graph(row[0]), str(row[1]), str(row[2]),
                                          "" if len(row) < 4 else str(row[3]))
            elif is_kill:
                self.T[table].pop(rid, None)
                if table == "edges":
                    self.recorded_edges.discard(rid)
            return ("T", table, rid, typ)
        if root in DATA and len(subs) == 2 and subs[1] == "qualifiers":
            return ("Q", DATA[root], subs[0], typ)
        return None

    # -- views
    def marker(self) -> Optional[Tuple]:
        v = self.L.get(("redacting",))
        return v if isinstance(v, tuple) else None

    def live_edges(self) -> Dict[Tuple, List]:
        out = defaultdict(list)
        for rid, row in self.T["edges"].items():
            out[row].append(rid)
        return out

    def node_live(self, nid: str) -> bool:
        return (any(r[0] == nid for r in self.T["nodes"].values()) or any(r[1] == nid for r in self.T["labels"].values())
                or any(r[1] == nid for r in self.T["props"].values()))


# ------------------------------------------------------------------------------------------------ predicates

def rec_tuple(rec: Tuple, st: State) -> Optional[Tuple]:
    op = rec[0]
    if op in ("create_rel", "create_temporal_edge"):
        return tuple_of(rec[5])
    if op == "delete_rel":
        return tuple_of(rec[4])
    return st.stmt_tuple.get(str(rec[2]))


def spec_member(rec: Tuple, name: str, match: str, st: State) -> Optional[bool]:
    """Spec 256 FR-002, written from the spec: the record's graph is the target graph and, for a prefix target,
    its node id (node records) or an endpoint of its statement (relationship records) starts with prefix|."""
    if not isinstance(rec, tuple) or not rec or rec[0] in ("redacted", "redact"):
        return False
    if norm_graph(rec[6] if len(rec) > 6 else "").replace("\x00", "") != name:
        return False
    if not match:
        return True
    if rec[1] == "node":
        return str(rec[2]).startswith(match)
    t = rec_tuple(rec, st)
    if t is None:
        return None
    return t[0].startswith(match) or t[2].startswith(match)


def content_live(rec: Tuple, st: State) -> Optional[str]:
    """What of the record's content is live in the replayed tables, or None."""
    if rec[1] == "node":
        return f"node {rec[2]}" if st.node_live(str(rec[2])) else None
    t = rec_tuple(rec, st)
    if t is None:
        return None
    g, s, p, o = t[3], t[0], t[1], t[2]
    for row in st.T["edges"].values():
        if row == (g, s, p, o):
            return f"edge {s}-[{p}]->{o} in '{g}'"
    return None


def tenant_of(text: str) -> List[str]:
    return [t for t in TENANT_NAMES if t in text]


def strings_of(v) -> List[str]:
    if isinstance(v, tuple):
        out = []
        for x in v:
            out += strings_of(x)
        return out
    return [str(v)] if v is not None else []


def residue(st: State, t: str) -> List[str]:
    out = []
    for k, v in st.L.items():
        texts = [str(x) for x in k] + strings_of(v)
        if any(t in x for x in texts):
            out.append(f"^IVG.Ledger{list(k)} = {str(v)[:120]}")
    for k, v in st.R.items():
        if any(t in x for x in strings_of(v)):
            out.append(f"ledger_revisions seq {k[0]}: {str(v)[:160]}")
    return out


# ------------------------------------------------------------------------------------------------ reconstruction

def reconstruct(L: Dict[Tuple, Any], upto: int) -> Dict:
    """Replay of the ledger's records 1..upto (spec 213 replay semantics, skipping tombstones and audit records)."""
    nodes: Dict[str, List] = {}
    rels: Dict[str, List] = {}
    keys = sorted((k for k in L if len(k) == 3 and k[0] == "rec"), key=lambda k: (int(k[1]), int(k[2])))
    for k in keys:
        if int(k[1]) > upto:
            break
        r = L[k]
        if not isinstance(r, tuple) or not r or r[0] in ("redacted",) or (len(r) > 1 and r[1] == "revision"):
            continue
        op, kind, eid, attr = r[0], r[1], str(r[2]), str(r[3])
        new = enc_val(r[5]) if len(r) > 5 else None
        if kind == "node":
            if op == "create_node":
                nodes[eid] = [set(), {}]
            elif op == "delete_node":
                nodes.pop(eid, None)
            elif eid in nodes:
                if op == "add_label":
                    nodes[eid][0].add(attr)
                elif op == "remove_label":
                    nodes[eid][0].discard(attr)
                elif op == "set_prop":
                    nodes[eid][1][attr] = new if new is not None else ""
                elif op == "remove_prop":
                    nodes[eid][1].pop(attr, None)
        elif kind == "rel":
            if op == "create_rel":
                t = tuple_of(r[5])
                if t:
                    rels[eid] = [t[0], t[1], t[2], t[3] or None, {}]
            elif op == "delete_rel":
                rels.pop(eid, None)
            elif eid in rels:
                if op == "set_qual":
                    rels[eid][4][attr] = new if new is not None else ""
                elif op == "remove_qual":
                    rels[eid][4].pop(attr, None)
    return {"nodes": {n: [sorted(v[0]), dict(sorted(v[1].items()))] for n, v in nodes.items()},
            "rels": {s: [v[0], v[1], v[2], v[3], dict(sorted(v[4].items()))] for s, v in rels.items()}}


def parse_quals(q) -> Optional[Dict[str, str]]:
    if not q:
        return {}
    try:
        d = json.loads(q) if isinstance(q, str) else dict(q)
    except Exception:  # noqa: BLE001
        return {}
    if d.get("temporal") is True:
        return None
    out = {}
    for k, v in d.items():
        if v is None:
            continue
        out[str(k)] = ("true" if v else "false") if isinstance(v, bool) else (
            json.dumps(v) if isinstance(v, (dict, list)) else str(v))
    return out


def expected_verify(st: State, tables: Dict) -> Tuple[str, List[str]]:
    """What verify() must answer at a quiescent point: the replay of the records against the canonical tables."""
    if st.marker() is not None:
        return "redaction_in_progress", []
    head = int(st.L.get(("head",), 0) or 0)
    rep = reconstruct(st.L, head)
    a_nodes = {n: (set(v[0]), v[1]) for n, v in rep["nodes"].items()}
    a_rels = {}
    for sid, v in rep["rels"].items():
        a_rels[(v[0], v[1], v[2], norm_graph(v[3]))] = v[4]
    b_nodes: Dict[str, Tuple[set, Dict]] = {}
    for _rid, nid, _g in tables["nodes"]:
        b_nodes.setdefault(str(nid), (set(), {}))
    for _rid, _g, s, label in tables["labels"]:
        b_nodes.setdefault(str(s), (set(), {}))[0].add(str(label))
    for _rid, _g, s, k, v in tables["props"]:
        if k in ("id", "__graph"):
            continue
        b_nodes.setdefault(str(s), (set(), {}))[1][str(k)] = "" if v is None else str(v)
    b_rels = {}
    for _rid, g, s, p, o, q in tables["edges"]:
        pq = parse_quals(q)
        if pq is None:
            continue
        b_rels[(str(s), str(p), str(o), norm_graph(g))] = pq
    diff = []
    for n in sorted(set(a_nodes) | set(b_nodes)):
        if a_nodes.get(n) != b_nodes.get(n):
            diff.append(f"node {n}: ledger {a_nodes.get(n)} tables {b_nodes.get(n)}")
    for t in sorted(set(a_rels) | set(b_rels)):
        if a_rels.get(t) != b_rels.get(t):
            diff.append(f"rel {t}: ledger {a_rels.get(t)} tables {b_rels.get(t)}")
    return ("equal" if not diff else "diverges"), diff


# ------------------------------------------------------------------------------------------------ the check

KNOWN = {
    "I1": "stmt/tuple bijection", "I2": "ERS-I3", "I2b": "live statement without row", "I3": "RED-B1.1",
    "I3b": "RED-I1", "I4": "marker", "I5": "audit counts", "I6": "SC-001", "I7": "verify", "I8": "idempotency",
    "I9": "reader", "ADJ": "adjacency", "I10": "failed operation left committed writes",
    "I11": "statement assigned to a recorded edge",
}


def attribute_index(recs: List[Dict]):
    """pid -> sorted [(begin address, end address, key)] from the workers' scratch markers."""
    marks: Dict[str, Dict[Tuple, Dict]] = defaultdict(dict)
    for r in recs:
        if r["g"] and r["g"].startswith(MARK) and r["t"].startswith("SET"):
            _, subs = parse_ref(r["g"])
            if len(subs) == 4:
                key = (str(subs[0]), int(subs[1]), int(subs[2]))
                marks[r["p"]].setdefault(key, {})[subs[3]] = r["a"]
    idx = {}
    for pid, d in marks.items():
        idx[pid] = sorted((v.get("b", 0), v.get("e", 10 ** 18), k) for k, v in d.items())
    return idx


def find_op(idx, pid: str, addr: int):
    best = None
    for b, e, k in idx.get(pid, []):
        if b <= addr:
            best = (b, e, k)
        else:
            break
    if best and addr <= best[1]:
        return best[2]
    return best[2] if best else None


def plan_ops(plan: Dict) -> Dict[Tuple[str, int], Dict]:
    out = {}
    for ph in plan["phases"]:
        for w, spec in ph["workers"].items():
            for i, op in enumerate(spec["ops"]):
                out[(str(w), i)] = op
    return out


def classify(inv: str, ctx: Dict) -> Tuple[str, str]:
    """Known finding id (or NEW) for a violation, from its invariant and the operation context that caused it."""
    if ctx.get("inherit"):
        return ctx["inherit"][0], "consequence of an earlier " + ctx.get("consequence_of", "") + ": " + ctx["inherit"][1]
    kind = ctx.get("killer_kind") or ctx.get("op_kind")
    if inv == "I2":
        if kind == "erase":
            if ctx.get("killer_graph_erase"):
                return "F-1201", "graph erasure killed the statement of an edge a concurrent commit created"
            return "F-1114", "prefix erasure killed statement entries without the head lock"
        if kind == "redact":
            return "F-1302", "redaction Final dropped the statement of content live again"
        return "NEW", "ERS-I3 broken by " + str(kind)
    if inv == "I2b":
        if kind == "direct":
            return "F-0303", "direct edge delete left the statement live"
        if kind == "erase":
            return "F-1114", "erasure left a live statement whose row is gone"
        return "NEW", "live statement without row after " + str(kind)
    if inv == "I1":
        if kind == "erase":
            return "F-1114", "erasure changed the statement maps without the head lock"
        if kind == "direct":
            return "F-0303", "direct edge write against the statement maps"
        return "NEW", "stmt/tuple bijection broken by " + str(kind)
    if inv == "I3":
        w = ctx.get("live_writer_kind")
        if w == "commit":
            return "F-1302", "a commit made the target live in the redaction's unlocked window"
        if w == "direct":
            return "F-C1307", "a ledger-bypassing writer made the target live during the run"
        if w == "erase-rollback":
            return "F-C1201", "redaction against an erasure that rolled back"
        return "F-1302", "tombstone of live content (writer " + str(w) + ")"
    if inv in ("I4", "I5"):
        return "F-1303", "two targets' runs shared the marker or counters"
    if inv == "I3b":
        return "NEW", "tombstone outside the target"
    if inv == "I8":
        if ctx.get("replay_wrote_content"):
            return ("F-1306" if ctx.get("revived") else "F-1101"), "replayed commit re-applied post-commit properties"
        return "NEW", ctx.get("why", "idempotency")
    if inv == "I9":
        if ctx.get("redaction_during"):
            return "F-1402", "reader interval overlapped a redaction"
        return "NEW", "reader answer matches no committed point"
    if inv == "ADJ":
        return ("F-C1202" if ctx.get("graph_erase_seen") else "NEW"), "edge row without adjacency"
    if inv == "I11":
        return "NEW", "assigned_stmt for an edge with a live recorded statement"
    if inv == "I10":
        return "NEW", "a refused operation's writes stayed committed"
    if inv == "I6":
        return ctx.get("finding", "NEW"), ctx.get("why", "tenant string after complete redaction")
    if inv == "I7":
        return ctx.get("finding", "NEW"), ctx.get("why", "verify disagrees with the oracle")
    return "NEW", inv


def check(trace: Dict) -> Dict:
    plan = trace["plan"]
    ops_by = plan_ops(plan)
    events = {(str(e["w"]), e["i"], e["attempt"]): e for e in trace["events"] if e.get("ev") == "op"}
    tenants = {t["name"]: t for t in plan["tenants"]}
    st = State()
    st.load(trace["init"])
    recs = trace["journal"]
    idx = attribute_index(recs)
    units = journal.transactions(recs)
    units.sort(key=lambda u: (u.get("end") or u.get("begin") or 0))
    viol: List[Dict] = []
    seen_keys = set()
    obs = Counter()
    pend: Dict[str, Counter] = defaultdict(Counter)        # digest -> seq -> tombstones of the open run
    fin: Dict[str, set] = defaultdict(set)                 # tenant -> completed target digests since last write
    bindings: Dict[str, List[Dict]] = defaultdict(list)    # key -> [{seq, fp, set_at, killed_at}]
    redacted_keys = set()
    killer: Dict[Tuple, Dict] = {}                         # ("stmt", sid) -> context of the unit that killed it
    graph_erase_seen = False
    live_writer: Dict[str, str] = {}                       # entity text -> kind of the last op that made it live
    finalized = set()                                      # redact op attempts whose Final unit was seen
    effective: Dict[Tuple, List[int]] = defaultdict(list)  # op attempt -> committed units with a net write
    erased_tenants = set()
    stmt_cause: Dict[str, Tuple[str, str]] = {}            # statement id -> (finding, why) of an earlier I2b

    def completion(op, digest, end, ctx):
        t_name = op.get("tenant")
        if not t_name:
            return
        fin[t_name].add(digest)
        need = {target_digest(x["graph"], x["prefix"])[0] for x in _targets(tenants[t_name])}
        if need <= fin[t_name]:
            res = residue(st, t_name)
            if res:
                add("I6", ("sc001", t_name, tuple(sorted(res))), f"tenant {t_name}: {len(res)} string(s) remain after "
                    f"complete redaction, e.g. {res[:3]}", {**ctx, **sc001_cause(res, st, t_name)})
    committed_units = 0
    unattributed = 0

    # readers: intervals [b, e] in journal addresses
    readers = []
    for key, ev in events.items():
        op = ops_by.get((key[0], key[1]), {})
        if op.get("kind") == "reconstruct" and ev.get("ok"):
            b = e = None
            for bb, ee, k in idx.get(ev["pid"], []):
                if k == key:
                    b, e = bb, ee
            if b is not None:
                readers.append({"key": key, "b": b, "e": e, "seq": ev["res"]["seq"], "state": ev["res"]["state"],
                                "matched": False, "evaluated": 0, "redaction_during": False})

    def add(inv: str, dedupe: Tuple, detail: str, ctx: Dict) -> None:
        if (inv, dedupe) in seen_keys:
            return
        seen_keys.add((inv, dedupe))
        fid, why = classify(inv, ctx)
        viol.append({"invariant": inv, "name": KNOWN.get(inv, inv), "finding": fid, "why": why, "detail": detail,
                     "context": {k: v for k, v in ctx.items() if k not in ("state",)}, "_key": (inv, dedupe)})

    def eval_readers(addr_lo: int, addr_hi: int) -> None:
        for rd in readers:
            if rd["matched"]:
                continue
            if rd["b"] <= addr_hi and addr_lo <= rd["e"]:
                rd["evaluated"] += 1
                if reconstruct(st.L, int(rd["seq"])) == rd["state"]:
                    rd["matched"] = True

    last_addr = 0
    for u in units:
        end = u.get("end") or u.get("begin") or 0
        # the state before this unit is a committed point for readers whose interval contains it
        eval_readers(last_addr, end)
        if u["kind"] == "txn" and not u["committed"]:
            obs["open_units_at_end"] += 1
            continue
        if not u["records"]:
            continue
        r0 = u["records"][0]
        if r0["g"].startswith(MARK):
            _, ms = parse_ref(r0["g"])
            if len(ms) == 4 and ms[3] == "e":
                mk = (str(ms[0]), int(ms[1]), int(ms[2]))
                mop = ops_by.get((mk[0], mk[1]), {})
                mev = events.get(mk)
                if (mop.get("kind") == "redact" and mev and mev.get("ok") and mev["res"].get("complete")
                        and mk not in finalized):
                    completion(mop, target_digest(mop.get("graph"), mop.get("prefix"))[0], end,
                               {"unit_end": end, "op": list(mk), "op_kind": "redact", "tenant": mop.get("tenant"),
                                "empty_run": True})
            last_addr = end
            continue
        key = find_op(idx, u["pid"], r0["a"])
        op = ops_by.get((key[0], key[1]), {}) if key else {}
        ev = events.get(key) if key else None
        kind = op.get("kind", "unattributed")
        if not key:
            unattributed += 1
        before_marker = st.marker()
        live_by_tuple = {}
        if kind == "commit":
            for k_, v_ in st.L.items():
                if len(k_) == 2 and k_[0] == "stmt" and isinstance(v_, tuple) and len(v_) >= 6 and str(v_[5]) == "":
                    live_by_tuple[(str(v_[0]), str(v_[1]), str(v_[2]), norm_graph(v_[3]))] = str(k_[1])
        before_L = {}
        touched = []
        for r in u["records"]:
            if r["g"] and r["g"].startswith(LEDGER):
                _, subs = parse_ref(r["g"])
                if subs not in before_L:
                    before_L[subs] = st.L.get(subs)
        for r in u["records"]:
            t = st.apply(r)
            if t:
                touched.append(t)
        st.learn_stmts([t[1] for t in touched if t[0] == "L"])
        if u["kind"] == "txn":
            committed_units += 1
        if key and touched and not u.get("rolled_back") and any(t[0] in ("L", "T", "R") for t in touched):
            effective[tuple(key)].append(end)
        ctx = {"unit_end": end, "pid": u["pid"], "op": list(key) if key else None, "op_kind": kind,
               "tenant": op.get("tenant")}
        content_rows = [t for t in touched if t[0] in ("T", "Q")]
        # provenance of edge rows and of live content
        for t in touched:
            if t[0] == "T" and t[1] == "edges" and t[3].startswith("SET"):
                if kind == "commit":
                    st.recorded_edges.add(t[2])
                row = st.T["edges"].get(t[2])
                if row:
                    live_writer[f"edge {row[1]}-[{row[2]}]->{row[3]} in '{row[0]}'"] = kind
            if t[0] == "T" and t[1] in ("nodes", "labels", "props") and t[3].startswith("SET"):
                row = st.T[t[1]].get(t[2])
                if row:
                    live_writer[f"node {row[0] if t[1] == 'nodes' else row[1]}"] = kind
        for subs, prior in before_L.items():
            if len(subs) == 2 and subs[0] == "stmt" and prior is not None and st.L.get(subs) is None:
                killer[("stmt", str(subs[1]))] = {"killer_kind": kind, "killer_op": list(key) if key else None,
                                                  "killer_graph_erase": bool(op.get("graph_erase"))}
        if kind == "erase" and op.get("graph_erase"):
            graph_erase_seen = True
        if kind == "erase" and content_rows:
            erased_tenants.add(op.get("tenant"))

        # ---- I11: a commit assigns a new statement id only to an edge the ledger has no live statement for
        if kind == "commit":
            for subs, prior in before_L.items():
                v_ = st.L.get(subs)
                if (len(subs) == 3 and subs[0] == "rec" and prior is None and isinstance(v_, tuple) and len(v_) >= 8
                        and "assigned_stmt" in str(v_[7])):
                    tup = rec_tuple(v_, st)
                    old = live_by_tuple.get(tup) if tup else None
                    if old and old != str(v_[2]):
                        add("I11", ("assigned", subs), f"commit {list(key)} recorded {v_[0]} of {tup} against a new "
                            f"statement {v_[2]} (assigned_stmt) while statement {old} of that tuple was live in the "
                            f"committed state", {**ctx, "old_stmt": old})
        # ---- redaction rules
        tomb_new = [(subs, prior) for subs, prior in before_L.items()
                    if len(subs) == 3 and subs[0] == "rec" and isinstance(st.L.get(subs), tuple)
                    and st.L[subs][0] == "redacted" and not (isinstance(prior, tuple) and prior[0] == "redacted")]
        audit_new = [(subs, st.L[subs]) for subs, prior in before_L.items()
                     if len(subs) == 3 and subs[0] == "rec" and prior is None and isinstance(st.L.get(subs), tuple)
                     and st.L[subs][0] == "redact"]
        if tomb_new:
            for r_ in readers:
                if r_["b"] <= end <= r_["e"]:
                    r_["redaction_during"] = True
        if tomb_new and kind != "redact":
            add("I4", ("tomb-by", kind, end), f"{len(tomb_new)} tombstone(s) written by a {kind} unit", ctx)
        if kind == "redact":
            digest, name, match = target_digest(op.get("graph"), op.get("prefix"))
            ctx["target"] = [name, match]
            m_after = st.marker()
            for subs, prior in tomb_new:
                if not isinstance(prior, tuple):
                    continue
                live = content_live(prior, st)
                if live:
                    w = live_writer.get(live, "unknown")
                    add("I3", ("tomb", subs), f"tombstone at {list(subs)} of {prior[:3]}: {live} at the batch's commit",
                        {**ctx, "live": live, "live_writer_kind": w})
                mem = spec_member(prior, name, match, st)
                if mem is False:
                    add("I3b", ("out", subs), f"tombstone at {list(subs)} of {prior[:3]} outside target {name!r}/{match!r}",
                        ctx)
                pend[digest][int(subs[1])] += 1
            if tomb_new and (m_after is None or str(m_after[0]) != digest):
                add("I4", ("marker", end), f"batch tombstoned {len(tomb_new)} under marker "
                    f"{(str(m_after[0])[:12] if m_after else None)} not its own {digest[:12]}", ctx)
            if audit_new:
                counts = Counter()
                for subs, v in audit_new:
                    counts[int(v[2])] += int(enc_val(v[5]) or 0)
                if before_marker is not None and str(before_marker[0]) != digest:
                    add("I4", ("final-foreign", end), f"Final of {digest[:12]} removed marker of "
                        f"{str(before_marker[0])[:12]}", ctx)
                if dict(counts) != dict(pend[digest]):
                    add("I5", ("counts", end), f"audit counts {dict(counts)} != this target's tombstones "
                        f"{dict(pend[digest])}", ctx)
                pend[digest] = Counter()
            completed = (before_marker is not None and st.marker() is None) or bool(audit_new)
            if completed:
                finalized.add(tuple(key))
                completion(op, digest, end, ctx)
        # a ledger write carrying a tenant's strings reopens its SC-001 obligation
        for t in touched:
            if t[0] == "L" and t[1][:1] == ("rec",) and t[2].startswith("SET"):
                v = st.L.get(t[1])
                if isinstance(v, tuple) and v[0] not in ("redacted", "redact"):
                    for tn in tenant_of(" ".join(strings_of(v))):
                        fin[tn] = set()
            if t[0] == "R" and t[2].startswith("SET") and kind == "commit":
                for tn in tenant_of(" ".join(strings_of(st.R.get(t[1])))):
                    fin[tn] = set()

        # ---- idempotency
        for subs, prior in before_L.items():
            if len(subs) == 2 and subs[0] == "idem":
                k = str(subs[1])
                now = st.L.get(subs)
                if isinstance(now, tuple) and prior != now:
                    live_b = [b for b in bindings[k] if b["killed_at"] is None]
                    if live_b:
                        add("I8", ("rebind", k), f"key {k} bound again (seq {now[0]}) while bound to seq {live_b[0]['seq']}",
                            {**ctx, "why": "a key bound twice"})
                    if k in redacted_keys:
                        add("I8", ("redacted-rebind", k), f"redacted key {k} bound again", {**ctx, "why": "redacted key rebound"})
                    fp = ((ev or {}).get("res") or {}).get("fingerprint") or (ev or {}).get("fingerprint")
                    if fp and str(now[1]) != fp:
                        add("I8", ("fp", k), f"key {k} bound to fingerprint {str(now[1])[:12]} of another changeset",
                            {**ctx, "why": "binding fingerprint"})
                    bindings[k].append({"seq": int(now[0]), "fp": str(now[1]), "set_at": end, "killed_at": None})
                elif now is None and prior is not None:
                    for b in bindings[k]:
                        if b["killed_at"] is None:
                            b["killed_at"] = end
                    if kind == "redact":
                        redacted_keys.add(k)
        if kind == "commit" and ev and ev.get("ok") and ev["res"].get("replayed") and content_rows:
            nids = sorted({st.T[t[1]].get(t[2], ("?",))[1] for t in content_rows
                           if t[0] == "T" and t[1] == "props" and t[2] in st.T["props"]})
            node_rows = {r[0] for r in st.T["nodes"].values()}
            revived = any(n.split("|")[0] in erased_tenants and n not in node_rows for n in nids)
            add("I8", ("replay-writes", tuple(key)), f"replayed commit {key} wrote {len(content_rows)} content row(s) "
                f"{nids[:3]}", {**ctx, "replay_wrote_content": True, "revived": revived})

        # ---- global invariants on the replayed state
        tuples = {k: v for k, v in st.L.items() if len(k) == 5 and k[0] == "tuple"}
        live_stmts = {}
        for k, v in st.L.items():
            if len(k) == 2 and k[0] == "stmt" and isinstance(v, tuple) and len(v) >= 6 and str(v[5]) == "":
                live_stmts[str(k[1])] = (str(v[0]), str(v[1]), str(v[2]), norm_graph(v[3]))
        for k, sid in tuples.items():
            row = live_stmts.get(str(sid))
            if row is None or (row[0], row[1], row[2], gkey(row[3])) != (str(k[1]), str(k[2]), str(k[3]), str(k[4])):
                add("I1", ("tuple", k, str(sid)), f"tuple {list(k[1:])} -> {sid} has no matching live statement",
                    {**ctx, **killer.get(("stmt", str(sid)), {})})
        for sid, t in live_stmts.items():
            if str(tuples.get(("tuple", t[0], t[1], t[2], gkey(t[3])), "")) != sid:
                c2 = dict(ctx)
                if sid in stmt_cause:
                    c2.update(inherit=stmt_cause[sid], consequence_of="I2b")
                add("I1", ("stmt", sid), f"live statement {sid} {t} has no tuple entry", c2)
        live = st.live_edges()
        for rid in list(st.recorded_edges):
            row = st.T["edges"].get(rid)
            if row is None:
                continue
            g, s, p, o = row
            sid = st.L.get(("tuple", s, p, o, gkey(g)))
            if sid is None or str(sid) not in live_stmts:
                kc = killer.get(("stmt", str(sid)), {}) if sid is not None else {}
                if not kc:
                    # the statement of this tuple that was killed most recently
                    for sid2, t2 in st.stmt_tuple.items():
                        if t2 == (s, p, o, g) and ("stmt", sid2) in killer:
                            kc = killer[("stmt", sid2)]
                add("I2", ("ers", rid, row), f"edge row {rid} {s}-[{p}]->{o} in '{g}' (written by a commit) has no live "
                    f"statement", {**ctx, **kc})
        for sid, t in live_stmts.items():
            if (t[3], t[0], t[1], t[2]) not in live:
                if ("I2b", ("stmtrow", sid)) not in seen_keys:
                    stmt_cause[sid] = classify("I2b", ctx)
                add("I2b", ("stmtrow", sid), f"live statement {sid} {t} has no edge row", ctx)
        last_addr = end

    eval_readers(last_addr, 10 ** 18)
    # I8 (replay answers): a replayed commit returns the revision its key is bound to, for the same fingerprint
    for k3, ev in events.items():
        res = ev.get("res") if isinstance(ev.get("res"), dict) else {}
        if not (ev.get("ok") and res.get("replayed")):
            continue
        key_ = res.get("key")
        ok_b = [b for b in bindings.get(str(key_), []) if b["seq"] == int(res.get("seq") or -1)
                and b["fp"] == res.get("fingerprint")]
        if not ok_b:
            add("I8", ("replay-answer", k3), f"replayed commit {list(k3)} with key {key_} answered seq {res.get('seq')}, "
                f"but the key's bindings were {[(b['seq'], b['fp'][:8]) for b in bindings.get(str(key_), [])]}",
                {"op": list(k3), "op_kind": "commit", "why": "replay answered a revision not bound to its key and "
                                                             "fingerprint"})
    # I10: an operation that reported failure (and whose process was not terminated) committed nothing
    for k3, ev in events.items():
        op = ops_by.get((k3[0], k3[1]), {})
        if ev.get("ok") or ev.get("killed") or op.get("kind") not in ("commit", "erase", "direct"):
            continue
        if effective.get(k3):
            add("I10", ("failed-wrote", k3), f"{op.get('kind')} {list(k3)} reported {ev.get('err')} "
                f"({str(ev.get('msg'))[:120]}) but {len(effective[k3])} of its unit(s) committed writes",
                {"op": list(k3), "op_kind": op.get("kind"), "err": ev.get("err")})
    for v in viol:
        if v["finding"] == "NEW" and v["invariant"] in ("I1", "I2b", "I11"):
            sid = v["context"].get("old_stmt") or _sid_of(v["detail"])
            kc = killer.get(("stmt", str(sid))) if sid else None
            if kc and kc.get("killer_kind") == "erase":
                v["finding"] = "F-1114"
                v["why"] = ("a commit read a concurrent erasure's uncommitted kill of the statement maps "
                            "(erasure takes no head lock); the statement was killed by erase " + str(kc.get("killer_op")))
    # structural violations still present in the final committed state are persistent; the others were healed by a
    # later committed unit (e.g. a concurrent transaction whose uncommitted write the violating one had read)
    now = state_violation_keys(st)
    for v in viol:
        if v["invariant"] in ("I1", "I2", "I2b"):
            v["persistent"] = v.get("_key") in now
    for rd in readers:
        if not rd["matched"]:
            add("I9", ("reader", tuple(rd["key"])), f"reconstruct {rd['key']} at seq {rd['seq']} matches none of "
                f"{rd['evaluated']} committed point(s) of its interval", {"op": list(rd["key"]),
                                                                          "redaction_during": rd["redaction_during"]})

    # ---- quiescent checks
    q_results = []
    for k, q in enumerate(trace["quiescent"]):
        qs = State()
        qs.load(q)
        exp, diff = expected_verify(qs, q["tables"])
        got = (q.get("verify") or {}).get("result") or (q.get("verify") or {}).get("error")
        q_results.append({"phase": k, "expected": exp, "product": got, "oracle_diff": diff[:8],
                          "product_diff": (q.get("verify") or {}).get("diff", [])[:8],
                          "stable": q.get("stable_during_verify")})
        if q.get("stable_during_verify") and got != exp:
            add("I7", ("verify", k), f"phase {k}: verify() said {got}, oracle expects {exp}; oracle diff {diff[:4]}; "
                f"product diff {(q.get('verify') or {}).get('diff', [])[:4]}", {"phase": k, **verify_cause(diff, q)})
        for g, s, p, o in q.get("adj_missing", []):
            add("ADJ", ("adj", g, s, p, o), f"phase {k}: edge {s}-[{p}]->{o} in '{g}' has no ^KG out entry",
                {"phase": k, "graph_erase_seen": graph_erase_seen})
        if qs.marker() is not None:
            obs["marker_left_at_phase_end"] += 1

    # ---- replay fidelity against the final observation
    fin_obs = State()
    fin_obs.load(trace["quiescent"][-1])
    l_diff = [k for k in set(st.L) | set(fin_obs.L) if st.L.get(k) != fin_obs.L.get(k)]
    t_diff = {t: len(set(st.T[t].items()) ^ set(fin_obs.T[t].items())) for t in st.T}
    for d, c in pend.items():
        if c:
            obs["redaction_runs_left_open"] += 1

    # ---- operation statistics
    op_events = [e for e in trace["events"] if e.get("ev") == "op"]
    by_kind = Counter(ops_by.get((str(e["w"]), e["i"]), {}).get("kind", "?") for e in op_events)
    ok_kind = Counter(ops_by.get((str(e["w"]), e["i"]), {}).get("kind", "?") for e in op_events if e.get("ok"))
    errs = Counter(f"{ops_by.get((str(e['w']), e['i']), {}).get('kind')}:{e.get('err')}" for e in op_events if not e.get("ok"))
    redact_complete = sum(1 for e in op_events if e.get("ok") and isinstance(e.get("res"), dict) and e["res"].get("complete"))
    replays = sum(1 for e in op_events if e.get("ok") and isinstance(e.get("res"), dict) and e["res"].get("replayed"))
    kills = [k for ph in trace["phases"] for k in ph["kills"] if k.get("pid")]
    obs.update({"unattributed_units": unattributed, "redactions_completed": redact_complete, "replays": replays,
                "kills": len(kills), "reader_checks": len(readers),
                "reader_points_evaluated": sum(r["evaluated"] for r in readers)})
    for v in viol:
        v.pop("_key", None)
    return {
        "persistent_by_invariant": dict(Counter(v["invariant"] for v in viol if v.get("persistent", True))),
        "ops": len(op_events), "ops_by_kind": dict(by_kind), "ok_by_kind": dict(ok_kind), "refusals": dict(errs),
        "committed_units": committed_units, "units": len(units),
        "violations": viol,
        "violations_by_invariant": dict(Counter(v["invariant"] for v in viol)),
        "violations_by_finding": dict(Counter(v["finding"] for v in viol)),
        "quiescent": q_results, "observations": dict(obs),
        "replay_matches_engine": not l_diff and not any(t_diff.values()),
        "replay_ledger_diff": [str(k) for k in l_diff[:8]], "replay_table_diff": t_diff,
        "kills": kills,
    }


def _sid_of(detail: str) -> Optional[str]:
    import re
    m = re.match(r"live statement (\S+) ", detail)
    return m.group(1) if m else None


def state_violation_keys(st: State) -> set:
    """The I1 / I2 / I2b dedupe keys that hold in a state (as check() builds them)."""
    out = set()
    tuples = {k: v for k, v in st.L.items() if len(k) == 5 and k[0] == "tuple"}
    live_stmts = {}
    for k, v in st.L.items():
        if len(k) == 2 and k[0] == "stmt" and isinstance(v, tuple) and len(v) >= 6 and str(v[5]) == "":
            live_stmts[str(k[1])] = (str(v[0]), str(v[1]), str(v[2]), norm_graph(v[3]))
    for k, sid in tuples.items():
        row = live_stmts.get(str(sid))
        if row is None or (row[0], row[1], row[2], gkey(row[3])) != (str(k[1]), str(k[2]), str(k[3]), str(k[4])):
            out.add(("I1", ("tuple", k, str(sid))))
    for sid, t in live_stmts.items():
        if str(tuples.get(("tuple", t[0], t[1], t[2], gkey(t[3])), "")) != sid:
            out.add(("I1", ("stmt", sid)))
    live = st.live_edges()
    for rid in st.recorded_edges:
        row = st.T["edges"].get(rid)
        if row is None:
            continue
        g, s, p, o = row
        sid = st.L.get(("tuple", s, p, o, gkey(g)))
        if sid is None or str(sid) not in live_stmts:
            out.add(("I2", ("ers", rid, row)))
    for sid, t in live_stmts.items():
        if (t[3], t[0], t[1], t[2]) not in live:
            out.add(("I2b", ("stmtrow", sid)))
    return out


def _targets(t: Dict) -> List[Dict]:
    if t["shape"] == "graph":
        return [{"graph": t["graph"], "prefix": None}, {"graph": None, "prefix": t["name"]}]
    return [{"graph": None, "prefix": t["name"]}]


def sc001_cause(res: List[str], st: State, t: str) -> Dict:
    """Where the residue is: an untombstoned record, a revision's metadata, an idempotency binding, a statement.
    A residue made only of the metadata (and idempotency binding) of revisions that hold no record at all is the
    zero-record revision case (F-CS01): redaction clears metadata on a revision's first tombstone only."""
    seqs = set()
    for k, v in st.R.items():
        if any(t in x for x in strings_of(v)):
            seqs.add(int(k[0]))
    recs_of = Counter(int(k[1]) for k in st.L if len(k) == 3 and k[0] == "rec")
    idem_seqs = {int(v[0]) for k, v in st.L.items() if len(k) == 2 and k[0] == "idem" and t in str(k[1])
                 and isinstance(v, tuple)}
    only_meta = all(x.startswith(("ledger_revisions", "^IVG.Ledger['idem'")) for x in res)
    zero = bool(seqs | idem_seqs) and all(recs_of.get(q, 0) == 0 for q in seqs | idem_seqs)
    kinds = Counter()
    for x in res:
        if x.startswith("^IVG.Ledger['rec'"):
            kinds["record"] += 1
        elif x.startswith("^IVG.Ledger['idem'"):
            kinds["idem"] += 1
        elif x.startswith("^IVG.Ledger['stmt'") or x.startswith("^IVG.Ledger['tuple'"):
            kinds["stmt"] += 1
        elif x.startswith("ledger_revisions"):
            kinds["revision-metadata"] += 1
        else:
            kinds["other"] += 1
    out = {"residue_kinds": dict(kinds), "residue_revisions": sorted(seqs | idem_seqs)}
    if only_meta and zero:
        out.update(finding="F-CS01", why="a revision with no records keeps its message, source, correlation id and "
                                          "idempotency key (and binding) through a complete redaction")
    return out


def verify_cause(diff: List[str], q: Dict) -> Dict:
    return {"oracle_diff_n": len(diff)}


# ------------------------------------------------------------------------------------------------ self-test

def _first(j, pred):
    for n, r in enumerate(j):
        if pred(r):
            return n, r
    raise StopIteration


def _unit_of(trace, kind):
    """(index in journal of the first record, pid) of the first committed unit run by an operation of `kind`."""
    ops_by = plan_ops(trace["plan"])
    idx = attribute_index(trace["journal"])
    for u in journal.transactions(trace["journal"]):
        if u["kind"] == "txn" and u["committed"] and u["records"]:
            key = find_op(idx, u["pid"], u["records"][0]["a"])
            if key and ops_by.get((key[0], key[1]), {}).get("kind") == kind:
                yield u, key


def _b64list(*items) -> str:
    lst = iris.IRISList()
    for x in items:
        lst.add(x)
    return base64.b64encode(lst.getBuffer()).decode()


def mutate(trace: Dict, kind: str) -> Dict:
    t = copy.deepcopy(trace)
    j = t["journal"]
    if kind == "drop-tuple":
        for u, _ in _unit_of(t, "commit"):
            r = next((r for r in u["records"] if r["g"].startswith('^IVG.Ledger("tuple"') and r["t"] == "SET"), None)
            if r:
                j[:] = [x for x in j if x["a"] != r["a"]]
                return t
    if kind == "kill-stmt":
        for u, _ in _unit_of(t, "commit"):
            r = next((r for r in u["records"] if r["g"].startswith('^IVG.Ledger("stmt"') and r["t"] == "SET"), None)
            tr = next((r for r in u["records"] if r["g"].startswith('^IVG.Ledger("tuple"') and r["t"] == "SET"), None)
            row = any(r2["g"].startswith("^t52S.BWr6.1(") and r2["t"] == "SET" and "," not in r2["g"] for r2 in u["records"])
            if r and tr and row:
                pos = max(n for n, x in enumerate(j) if x["a"] == u["end"])
                j.insert(pos + 1, {**r, "t": "KILL", "n": None, "x": False, "a": u["end"]})
                j.insert(pos + 2, {**tr, "t": "KILL", "n": None, "x": False, "a": u["end"]})
                return t
    if kind == "tombstone-live":
        for u, _ in _unit_of(t, "redact"):
            tomb = next((r for r in u["records"] if r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET"
                         and (ledger_value(parse_ref(r["g"])[1], r["n"]) or ("",))[0] == "redacted"), None)
            if tomb:
                _, subs = parse_ref(tomb["g"])
                # the original record's node id (or an endpoint) made live again inside the batch
                orig = _orig_record(t, subs)
                if orig is None or orig[1] != "node":
                    continue
                pos = next(n for n, x in enumerate(j) if x["a"] == tomb["a"])
                j.insert(pos, {**tomb, "g": "^t52S.XCFT.1(99999999)", "n": _b64list(str(orig[2]), "", 0)})
                return t
    if kind == "count-mismatch":
        for u, _ in _unit_of(t, "redact"):
            r = next((r for r in u["records"] if r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET"
                      and (ledger_value(parse_ref(r["g"])[1], r["n"]) or ("",))[0] == "redact"), None)
            if r:
                v = list(ledger_value(parse_ref(r["g"])[1], r["n"]))
                v[5] = "S" + str(int(enc_val(v[5])) + 1)
                r["n"] = _b64list(*v)
                return t
    if kind == "foreign-marker":
        for u, _ in _unit_of(t, "redact"):
            r = next((r for r in u["records"] if r["g"] == '^IVG.Ledger("redacting")' and r["t"] == "SET"), None)
            if r:
                v = list(ledger_value(("redacting",), r["n"]))
                v[0] = "0" * 64
                r["n"] = _b64list(*v)
                return t
    if kind == "residue":
        ops_by = plan_ops(t["plan"])
        shapes = {x["name"]: x["shape"] for x in t["plan"]["tenants"]}
        for u, key in _unit_of(t, "redact"):
            ten = ops_by[(key[0], key[1])].get("tenant")
            if shapes.get(ten) != "prefix":
                continue
            r = next((r for r in u["records"] if r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET"
                      and (ledger_value(parse_ref(r["g"])[1], r["n"]) or ("",))[0] == "redact"), None)
            if r:
                pos = next(n for n, x in enumerate(j) if x["a"] == r["a"])
                j.insert(pos, {**r, "g": '^IVG.Ledger("meta","note")',
                               "n": base64.b64encode(f"{ten}|n1 left behind".encode()).decode()})
                return t
    if kind == "verify-flip":
        q = t["quiescent"][-1]
        if q.get("verify", {}).get("result") in ("equal", "diverges"):
            q["verify"]["result"] = "diverges" if q["verify"]["result"] == "equal" else "equal"
            return t
    if kind == "idem-rebind":
        for u, _ in _unit_of(t, "commit"):
            r = next((r for r in u["records"] if r["g"].startswith('^IVG.Ledger("idem"') and r["t"] == "SET"), None)
            if r:
                v = list(ledger_value(parse_ref(r["g"])[1], r["n"]))
                v[0] = int(v[0]) + 1000
                j.append({**r, "n": _b64list(*v), "x": False, "a": j[-1]["a"] + 1})
                return t
    if kind == "failed-op-wrote":
        ops_by = plan_ops(t["plan"])
        idx = attribute_index(j)
        for u, key in _unit_of(t, "commit"):
            ev = next((e for e in t["events"] if e.get("ev") == "op" and (str(e["w"]), e["i"], e["attempt"]) == key
                       and e.get("ok") and not (e.get("res") or {}).get("replayed")), None)
            if ev:
                ev.update(ok=False, err="InjectedError", msg="injected: reported failure")
                return t
    if kind == "row-gone":
        for u, _ in _unit_of(t, "commit"):
            row = next((r for r in u["records"] if r["g"].startswith("^t52S.BWr6.1(") and r["t"] == "SET"
                        and "," not in r["g"]), None)
            if row:
                pos = max(n for n, x in enumerate(j) if x["a"] == u["end"])
                j.insert(pos + 1, {**row, "t": "KILL", "n": None, "x": False, "a": u["end"]})
                return t
    if kind == "assigned-over-live":
        units = list(_unit_of(t, "commit"))
        for n, (u1, _) in enumerate(units):
            cr = next((r for r in u1["records"] if r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET"
                       and (ledger_value(parse_ref(r["g"])[1], r["n"]) or ("",))[0] == "create_rel"), None)
            if not cr:
                continue
            v = ledger_value(parse_ref(cr["g"])[1], cr["n"])
            later = [u for u, _ in units[n + 1:n + 2]]
            if not later:
                continue
            u2 = later[0]
            r0 = u2["records"][0]
            fake = _b64list("delete_rel", "rel", 99999, "", v[5], "N", v[6], "assigned_stmt")
            pos = next(i for i, x in enumerate(j) if x["a"] == r0["a"])
            j.insert(pos, {**r0, "g": '^IVG.Ledger("rec",99999,1)', "t": "SET", "n": fake, "x": True})
            return t
    if kind == "adjacency-missing":
        t["quiescent"][-1].setdefault("adj_missing", []).append(["", "acme|n0", "KNOWS", "acme|n1"])
        return t
    if kind == "reader-wrong":
        for e in t["events"]:
            if e.get("ev") == "op" and e.get("ok") and isinstance(e.get("res"), dict) and "state" in e["res"]:
                e["res"]["state"]["nodes"]["acme|ghost"] = [[], {}]
                return t
    raise StopIteration(kind)


def _orig_record(trace, subs):
    st = State()
    st.load(trace["init"])
    for r in trace["journal"]:
        if r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET":
            _, s2 = parse_ref(r["g"])
            if s2 == subs:
                v = ledger_value(s2, r["n"])
                if isinstance(v, tuple) and v[0] not in ("redacted", "redact"):
                    return v
    v = st.L.get(subs)
    return v if isinstance(v, tuple) and v[0] not in ("redacted", "redact") else None


CONTROLS = {"drop-tuple": "I1", "kill-stmt": "I2", "tombstone-live": "I3", "count-mismatch": "I5",
            "foreign-marker": "I4", "residue": "I6", "verify-flip": "I7", "idem-rebind": "I8", "reader-wrong": "I9",
            "failed-op-wrote": "I10", "row-gone": "I2b", "adjacency-missing": "ADJ", "assigned-over-live": "I11"}


def self_test_traces(traces: List[Dict]) -> Dict:
    out = {"controls": {}, "unmutated": []}
    for tr in traces:
        rep = check(tr)
        out["unmutated"].append({"seed": tr["plan"]["seed"], "violations": rep["violations_by_invariant"]})
    for kind, inv in CONTROLS.items():
        res = {"caught": False, "applicable": False}
        for tr in traces:
            base = Counter(v["invariant"] for v in check(tr)["violations"])
            try:
                m = mutate(tr, kind)
            except StopIteration:
                continue
            res["applicable"] = True
            rep = check(m)
            got = Counter(v["invariant"] for v in rep["violations"])
            res.update(seed=tr["plan"]["seed"], baseline=base.get(inv, 0), mutated=got.get(inv, 0),
                       sample=[v["detail"] for v in rep["violations"] if v["invariant"] == inv][:1])
            if got.get(inv, 0) > base.get(inv, 0):
                res["caught"] = True
                break
        out["controls"][kind] = {"invariant": inv, **res}
    out["pass"] = all(v["caught"] for v in out["controls"].values())
    return out


def self_test(path: Path) -> int:
    import gzip
    files = sorted(path.glob("s*.trace.json.gz")) if path.is_dir() else [path]
    traces = []
    for f in files[:40]:
        with gzip.open(f, "rt") as fh:
            traces.append(json.load(fh))
    res = self_test_traces(traces)
    print(json.dumps(res, indent=1, default=str))
    return 0 if res["pass"] else 1
