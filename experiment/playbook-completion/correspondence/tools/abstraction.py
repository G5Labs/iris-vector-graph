#!/usr/bin/env python3
"""The abstraction function from stored state to the participant contracts, checked on real traces (§3.4/§3.5).

    python abstraction.py TRACE.json [--json OUT]

alpha maps a quiescent stored state (no transaction open) to the states of the participant contracts of
experiment/playbook-completion/proofs (src/ledger.rs, src/store.rs):

  LedgerS.hist[i][j]  <- ^IVG.Ledger("rec", i+1, j+1): a content record -> Live(content(rec)); $LB("redacted", ...)
                         -> Tomb; the records of a revision of kind "redaction" -> one Audit{t: target_sha256, n}
  LedgerS.idem        <- ^IVG.Ledger("idem", key) = $LB(seq, fingerprint)
  LedgerS.locked      <- false at every quiescent point (no process holds ^IVG.Ledger("head") across transactions
                         at the pin; the reviewed design's eraser would)
  LedgerS.enabled     <- ^IVG.Ledger("meta","state") = "enabled"
  LedgerS.marker      <- ^IVG.Ledger("redacting") (its target digest); count <- ("redacting","n","records");
                         tally <- ("redacting","revs",seq) per-revision counts
  StoreS.rows         <- governed content rows: Graph_KG.nodes/rdf_labels/rdf_props of the default graph (where the
                         ledger keeps nodes, R290; named-graph node rows written by EnsureEndpoint are unrecorded and
                         reported apart), rdf_edges of every graph and their qualifiers; reserved properties and
                         temporal-marked edge rows excluded (as replay.read_canonical)
  StoreS.stmts        <- ^IVG.Ledger("tuple", s, p, o, graphKey)
  StoreS.erasing      <- None at quiescent points

content(rec) is the key the record touches and its effect; replay folds records (delete_node also removes the
node's labels and properties, as DeleteNodeRows does). The record semantics are written here from spec 213's record
layout (Ledger.cls:7), independently of replay.py.

Per operation (ops are sequential in the conf/ext traces; their boundaries are quiescent) the check is that
alpha(before) -> alpha(after) is a step of the composed participant contracts with the operation's label:
commit = Ledger.Commit + Store.Apply(the new records); replay = Ledger.Replay (nothing changes); refused = stutter;
setenabled = Ledger.SetEnabled; erase = Store.EraseRows + EraseIndex (Ledger unchanged); redact = Ledger.Batch*
(each tombstone: Live(c) -> Tomb(c), c a record of the target and not live, digest = SHA-256 of the record's
canonical JSON, op/kind kept) then Ledger.Audit; verify/read = stutter; bypass = Store.Apply outside the ledger
(premise P-C02, reported, not a step of Biz). After every operation the checkable invariants of biz_inv are
evaluated (ledger_inv, stmts_ok, inv_stmts, inv_mark, inv_replay outside pending targets) plus stmt/tuple bijection.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import conformance, journal  # noqa: E402

RESERVED = {"id", "__graph"}
LEDGER_DEFAULT = "\x01"


# ------------------------------------------------------------------------------------------------ stored state

def ledger_state_at(before, recs, upto_addr):
    st = dict(before)
    for r in recs:
        if r["a"] > upto_addr:
            break
        if r["g"].startswith("^IVG.Ledger"):
            conformance.apply(st, r)
    return st


def gname(g):
    return "" if g in (None, "", "\x00") else str(g).replace("\x00", "")


def alpha_store(rows):
    """Governed content: key -> value. Also returns the unrecorded named-graph node rows."""
    out, named = {}, set()
    for nid, g in rows["nodes"]:
        if gname(g) == "":
            out[("node", nid)] = ""
        else:
            named.add((gname(g), nid))
    for s, label, g in rows["labels"]:
        if gname(g) == "":
            out[("label", s, label)] = ""
    for s, k, v, g in rows["props"]:
        if gname(g) == "" and k not in RESERVED:
            out[("prop", s, k)] = "" if v is None else v
    for _eid, s, p, o, g, q in rows["edges"]:
        quals = {}
        if q:
            try:
                quals = json.loads(q)
            except Exception:  # noqa: BLE001
                quals = {}
        if isinstance(quals, dict) and quals.get("temporal") is True:
            continue
        g = gname(g)
        out[("edge", g, s, p, o)] = ""
        for k, v in (quals or {}).items():
            if v is None:
                continue
            out[("qual", g, s, p, o, k)] = ("true" if v else "false") if isinstance(v, bool) else \
                (json.dumps(v) if isinstance(v, (dict, list)) else str(v))
    return out, named


def tuples_of(st):
    return {(gname(k[4]) if k[4] != LEDGER_DEFAULT else "", k[1], k[2], k[3]): str(v)
            for k, v in st.items() if len(k) == 5 and k[0] == "tuple"}


def stmts_of(st):
    return {str(k[1]): v for k, v in st.items() if len(k) == 2 and k[0] == "stmt"}


def hist_of(st):
    h = defaultdict(dict)
    for k, v in st.items():
        if len(k) == 3 and k[0] == "rec":
            h[int(k[1])][int(k[2])] = v
    return {s: [h[s][o] for o in sorted(h[s])] for s in sorted(h)}


def idem_of(st):
    return {str(k[1]): v for k, v in st.items() if len(k) == 2 and k[0] == "idem"}


def head_of(st):
    return int(st.get(("head",)) or 0)


def marker_of(st):
    m = st.get(("redacting",))
    return None if m is None else str(m[0] if isinstance(m, tuple) else m)


# ------------------------------------------------------------------------------------------------ records

def _tuple_of_enc(enc):
    if not isinstance(enc, str) or not enc.startswith("S"):
        return None
    try:
        t = json.loads(enc[1:])
    except Exception:  # noqa: BLE001
        return None
    return gname(t.get("graph")), str(t.get("s")), str(t.get("p")), str(t.get("o"))


def fold(state, recs, stmt_tuple):
    """Apply records (content tuples $LB(op, kind, id, attr, prior, new, graph, flags)) to a governed state."""
    st = dict(state)
    for r in recs:
        if not isinstance(r, tuple) or not r:
            continue
        op = str(r[0])
        if op in ("redacted", "redact"):
            continue
        kind, eid, attr = str(r[1]), str(r[2]), str(r[3])
        new = r[5] if len(r) > 5 else "N"
        if kind == "node":
            if op == "create_node":
                st[("node", eid)] = ""
            elif op == "delete_node":
                for k in [k for k in st if k[0] in ("node", "label", "prop") and k[1] == eid]:
                    del st[k]
            elif op == "add_label":
                st[("label", eid, attr)] = ""
            elif op == "remove_label":
                st.pop(("label", eid, attr), None)
            elif op == "set_prop":
                st[("prop", eid, attr)] = "" if str(new) == "N" else str(new)[1:]
            elif op == "remove_prop":
                st.pop(("prop", eid, attr), None)
            continue
        if kind != "rel":
            continue
        if op == "create_rel":
            t = _tuple_of_enc(new)
            if t:
                stmt_tuple[eid] = t
                st[("edge",) + t] = ""
        elif op == "delete_rel":
            t = stmt_tuple.get(eid) or _tuple_of_enc(r[4])
            if t:
                for k in [k for k in st if k[0] in ("edge", "qual") and k[1:5] == t]:
                    del st[k]
        elif op in ("set_qual", "remove_qual"):
            t = stmt_tuple.get(eid)
            if not t:
                continue
            if op == "set_qual":
                st[("qual",) + t + (attr,)] = "" if str(new) == "N" else str(new)[1:]
            else:
                st.pop(("qual",) + t + (attr,), None)
    return st


def replay_hist(hist, stmt_rows):
    stmt_tuple = {}
    for sid, row in stmt_rows.items():
        if isinstance(row, tuple) and len(row) >= 4:
            stmt_tuple[sid] = (gname(row[3]), str(row[0]), str(row[1]), str(row[2]))
    st = {}
    for seq in sorted(hist):
        st = fold(st, hist[seq], stmt_tuple)
    return st


def canonical_record(seq, ordn, r):
    """Ledger.CanonicalRecord (Ledger.cls:572-605) re-implemented: keys in alphabetical order, compact JSON."""
    def flags(f):
        return [p for p in str(f or "").split(",") if p != ""]
    new, prior = str(r[5]), str(r[4])
    def v(x):  # a $LB element keeps its type: an integer element is a JSON number in %ToJSON
        return x if isinstance(x, (int, float)) else str(x)
    obj = {"attr": v(r[3]), "entity_id": v(r[2]), "entity_kind": v(r[1]), "flags": flags(r[7] if len(r) > 7 else ""),
           "graph": None if str(r[6] if len(r) > 6 else "") == "" else str(r[6]),
           "new": None if new[:1] == "N" else new[1:], "op": str(r[0]), "ordinal": ordn,
           "prior": None if prior[:1] == "N" else prior[1:], "seq": seq}
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------ the check

def spans(recs):
    sp = {}
    for r in recs:
        b, e = sp.get(r["p"], (r["a"], r["a"]))
        sp[r["p"]] = (min(b, r["a"]), max(e, r["a"]))
    return sp


def check(trace):
    before0 = conformance._state(trace["before"])
    recs = sorted(trace["journal"], key=lambda r: r["a"])
    ops = trace["ops"]
    out = {"ops": [], "violations": [], "premise_instances": [], "invariant_notes": [], "protocol": []}
    if not all("rows_before" in o for o in ops):
        out["skipped"] = "trace has no per-operation row snapshots (ledger-side checks only)"
    sp = spans(recs)
    opsp = [sp.get(o["pid"]) for o in ops]
    overlap = any(a and b and a[0] < b[1] and b[0] < a[1] for i, a in enumerate(opsp) for b in opsp[i + 1:])
    if overlap:
        # concurrent operations: one contract step per committed outermost transaction, in journal order of its end
        out["mode"] = "per-transaction (operations overlap)"
        by_pid = {o["pid"]: o for o in ops}
        units = sorted(journal.transactions(recs), key=lambda u: u.get("end") or u.get("begin") or 0)
        st = dict(before0)
        for u in units:
            o = by_pid.get(u["pid"])
            prior = dict(st)
            for r in u["records"]:
                if r["g"].startswith("^IVG.Ledger"):
                    conformance.apply(st, r)
            if o is None or not u["committed"] or u.get("rolled_back"):
                continue
            ov = {k: v for k, v in o.items() if k not in ("rows_before", "rows_after")}
            notes = step(ov, prior, st)
            out["ops"].append({"op": o["op"], "label": o.get("label"), "ok": o["ok"], "unit": [u.get("begin"), u.get("end")],
                               "notes": notes, "invariants": []})
            out["violations"] += [f"{o.get('label')}@{u.get('end')}: {n}" for n in notes if not n.startswith("PREMISE")]
        erase_units = [(u, by_pid[u["pid"]]) for u in units if u["pid"] in by_pid and by_pid[u["pid"]]["op"] == "erase"
                       and u["kind"] == "txn"]
        commit_units = [(u, by_pid[u["pid"]]) for u in units if u["pid"] in by_pid and by_pid[u["pid"]]["op"] == "commit"
                        and u["kind"] == "txn" and u["committed"]]
        for eu, eo in erase_units:
            g = (eo.get("target") or [None])[0]
            for cu, co in commit_units:
                if eu.get("begin", 0) < cu.get("begin", 0) and (cu.get("end") or 0) < (eu.get("end") or 1 << 62):
                    touched = any(r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET" and
                                  isinstance(conformance.decode_value(r["n"]), tuple) and
                                  gname(conformance.decode_value(r["n"])[6]) == g for r in cu["records"])
                    out["protocol"].append(
                        f"commit {co.get('label')} [{cu.get('begin')},{cu.get('end')}] ran inside the open erasure "
                        f"{eo.get('label')} [{eu.get('begin')},{eu.get('end')}] of graph {g!r}"
                        f"{' and wrote records of that graph' if touched else ''}: not a step of the reviewed protocol "
                        f"(protocol_sys: EraseRows..EraseIndex hold the head lock, HD-1201)")
        fin = conformance._state(trace["final"])
        if trace.get("rows_final"):
            inv = invariants({"rows_after": trace["rows_final"]}, fin)
            out["invariant_notes"] += [f"final: {n}" for n in inv]
            # Serializability of an erasure and a commit into its graph. Alone, each preserves inv_stmts: a commit adds
            # the edge row and its statement entry; EraseGraph(g) removes g's rows and statement entries. In either serial
            # order a commit's edge of g ends with both (erase; commit) or with neither (commit; erase). A committed edge
            # of g that is live at the end without its statement entry matches neither order.
            S, _named = alpha_store(trace["rows_final"])
            tup = tuples_of(fin)
            for eu, eo in erase_units:
                g = (eo.get("target") or [None])[0]
                for cu, co in commit_units:
                    edges = set()
                    for r in cu["records"]:
                        if r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET":
                            v = conformance.decode_value(r["n"])
                            if isinstance(v, tuple) and len(v) > 6 and v[0] == "create_rel" and gname(v[6]) == g:
                                t = _tuple_of_enc(v[5])
                                if t:
                                    edges.add(t)
                    bad = [t for t in edges if ("edge",) + t in S and t not in tup]
                    if bad:
                        out["protocol"].append(
                            f"non-serializable: commit {co.get('label')} (journal [{cu.get('begin')},{cu.get('end')}]) and "
                            f"erasure {eo.get('label')} ([{eu.get('begin')},{eu.get('end')}]) both committed; edge(s) "
                            f"{bad} of graph {g!r} are live without a statement entry, which neither serial order "
                            f"produces: not an execution of the reviewed protocol (EraseRows..EraseIndex under the head "
                            f"lock, HD-1201); F-1201")
        return out
    pid_last = {}
    for r in recs:
        pid_last[r["p"]] = r["a"]
    prev_addr = recs[0]["a"] - 1 if recs else 0
    state_before = before0
    for i, o in enumerate(ops):
        last = pid_last.get(o["pid"], prev_addr)
        last = max(last, prev_addr)
        state_after = ledger_state_at(before0, recs, last)
        prev_addr = last
        notes = step(o, state_before, state_after)
        inv = invariants(o, state_after)
        out["ops"].append({"i": i, "op": o["op"], "label": o.get("label"), "ok": o["ok"], "notes": notes,
                           "invariants": inv})
        for n in notes:
            (out["premise_instances"] if n.startswith("PREMISE") else out["violations"]).append(f"{o.get('label')}: {n}")
        out["invariant_notes"] += [f"{o.get('label')}: {n}" for n in inv]
        state_before = state_after
    return out


def contract_view(st):
    return {"hist": hist_of(st), "idem": idem_of(st), "enabled": st.get(("meta", "state")) == "enabled",
            "marker": marker_of(st), "count": int(st.get(("redacting", "n", "records")) or 0),
            "tally": {k[2]: int(v) for k, v in st.items() if len(k) == 3 and k[:2] == ("redacting", "revs")},
            "tuples": tuples_of(st), "head": head_of(st)}


def step(o, sb, sa):
    notes = []
    L0, L1 = contract_view(sb), contract_view(sa)
    rb, ra = o.get("rows_before"), o.get("rows_after")
    S0 = alpha_store(rb)[0] if rb else None
    S1 = alpha_store(ra)[0] if ra else None
    res = o.get("result")
    label = o.get("label", o["op"])
    stutter_ledger = L0["hist"] == L1["hist"] and L0["idem"] == L1["idem"] and L0["marker"] == L1["marker"] \
        and L0["count"] == L1["count"] and L0["tuples"] == L1["tuples"]
    stutter_store = S0 == S1
    new_seqs = sorted(set(L1["hist"]) - set(L0["hist"]))
    changed_old = [s for s in L0["hist"] if L1["hist"].get(s) != L0["hist"][s]]
    if o["op"] == "commit":
        replayed = isinstance(res, dict) and res.get("replayed")
        killed = isinstance(res, dict) and res.get("killed")
        # a client killed before its answer (lost acknowledgement) is ambiguous: a Commit or nothing
        if (not o["ok"] and not (killed and new_seqs)) or replayed or not new_seqs:
            if not (stutter_ledger and (S0 is None or stutter_store)):
                kind = "Replay" if replayed else "refusal"
                notes.append(f"{kind} is not a stutter: ledger_same={stutter_ledger} store_same={stutter_store}")
            return notes
        if changed_old:
            notes.append(f"Ledger.Commit rewrote existing revisions {changed_old}")
        if len(new_seqs) != 1 or new_seqs[0] != L0["head"] + 1 or L1["head"] != L0["head"] + 1:
            notes.append(f"Ledger.Commit appended {new_seqs} with head {L0['head']}->{L1['head']}")
        if not L0["enabled"] and L0["head"] > 0:
            notes.append("Ledger.Commit pre: ledger not enabled")
        new = [r for s in new_seqs for r in L1["hist"][s]]
        kinds = {str(r[7]) if len(r) > 7 else "" for r in new}
        if L0["marker"] is not None:
            m = sb.get(("redacting",))
            tgt = (str(m[1]), str(m[2]))
            ends = conformance.statement_ends(sb, {})
            if any(conformance.spec_member(r, tgt, ends) for r in new):
                notes.append("Ledger.Commit pre: blocks_commit (a record in the marked target was committed)")
        added = set(L1["idem"]) - set(L0["idem"])
        rebound = [k for k in L0["idem"] if L1["idem"].get(k) != L0["idem"][k]]
        if rebound:
            notes.append(f"Ledger.Commit rebound idempotency keys {rebound}")
        for k in added:
            if int(L1["idem"][k][0]) != new_seqs[0]:
                notes.append(f"idem {k} bound to {L1['idem'][k][0]} not to the new revision")
        if S0 is not None:
            stmt_rows = stmts_of(sa)
            genesis = any("genesis" in k for k in kinds)
            adoption = any("adoption" in k for k in kinds)
            if genesis:
                rep = replay_hist(L1["hist"], stmt_rows)
                if rep != S1 or S0 != S1:
                    notes.append(f"genesis: replay(hist) == alpha(rows) {rep == S1}; rows unchanged {S0 == S1}; "
                                 f"diff {sorted(set(rep.items()) ^ set(S1.items()))[:4]}")
            elif adoption:
                if S0 != S1:
                    notes.append("adoption changed the store")
                rep = replay_hist(L1["hist"], stmt_rows)
                if rep != S1:
                    notes.append(f"adoption: replay(hist) != alpha(rows): {sorted(set(rep.items()) ^ set(S1.items()))[:4]}")
            else:
                stmt_tuple = {sid: (gname(r[3]), str(r[0]), str(r[1]), str(r[2])) for sid, r in stmt_rows.items()
                              if isinstance(r, tuple) and len(r) >= 4}
                exp = fold(S0, new, stmt_tuple)
                if o.get("pcp"):
                    # client.py:445-487: each post-commit property is a DELETE + INSERT of rdf_props in the default
                    # graph, in its own transaction after the commit, with no record
                    for nid, props in o["pcp"].items():
                        for k, v in props.items():
                            exp[("prop", nid, k)] = v
                    notes.append("PREMISE P-C02: post-commit properties written outside the ledger (no record; F-1101)")
                if exp != S1:
                    d = sorted(set(exp.items()) ^ set(S1.items()))
                    notes.append(f"Store.Apply(records) != rows after: {len(d)} key(s), e.g. {d[:4]}")
        return notes
    if o["op"] in ("verify", "read", "probe"):
        if not stutter_ledger or (S0 is not None and not stutter_store):
            notes.append(f"{label}: not a stutter (ledger_same={stutter_ledger}, store_same={stutter_store})")
        return notes
    if o["op"] == "setenabled":
        if L0["hist"] != L1["hist"] or L0["idem"] != L1["idem"] or L0["marker"] != L1["marker"]:
            notes.append("SetEnabled changed history, bindings or marker")
        if S0 is not None and not stutter_store:
            notes.append("SetEnabled changed the store")
        return notes
    if o["op"] == "bypass":
        if L0["hist"] != L1["hist"] or L0["tuples"] != L1["tuples"]:
            notes.append("ledger-bypassing write changed the ledger")
        if S0 is not None and not stutter_store:
            notes.append("PREMISE P-C02: a ledger-bypassing write changed the governed store (Store.Apply outside the ledger)")
        return notes
    if o["op"] == "erase":
        if L0["hist"] != L1["hist"] or L0["idem"] != L1["idem"] or L0["marker"] != L1["marker"]:
            notes.append("erasure changed history, bindings or marker")
        g, prefix = (o.get("target") or ("*", None))
        if S0 is not None:
            if o.get("edges") is not None:
                spo = {(e["s"], e["p"], e["o"]) for e in o.get("edges", [])}
                mem = lambda k: k[0] in ("edge", "qual") and k[1] == g and k[2:5] in spo  # noqa: E731
            elif g == "*":
                mem = lambda k: True  # noqa: E731
            elif prefix is None:
                mem = lambda k: (k[0] in ("edge", "qual") and k[1] == g) or (g == "" and k[0] in ("node", "label", "prop"))  # noqa: E731
            else:
                ids = {k[1] for k in S0 if k[0] == "node" and str(k[1]).startswith(prefix)} if g == "" else set()
                mem = lambda k: (k[0] in ("node", "label", "prop") and k[1] in ids) or \
                    (k[0] in ("edge", "qual") and k[1] == g and (k[2] in ids or k[4] in ids))  # noqa: E731
            exp = {k: v for k, v in S0.items() if not mem(k)}
            if exp != S1:
                d = sorted(set(exp.items()) ^ set(S1.items()))
                notes.append(f"Store.EraseRows: rows after != outside(rows, t): {len(d)} key(s), e.g. {d[:4]}")
            t0 = {k for k in L0["tuples"] if not mem(("edge",) + k)}
            if set(L1["tuples"]) != t0:
                notes.append(f"Store.EraseIndex: tuples after != filter(!t): extra {sorted(set(L1['tuples']) - t0)[:3]} "
                             f"missing {sorted(t0 - set(L1['tuples']))[:3]}")
        return notes
    if o["op"] == "redact":
        tgt = tuple(o["target"])
        ends = conformance.statement_ends(sb, {})
        ends.update(conformance.statement_ends(sa, {}))
        tombs, others = 0, []
        for s, rs0 in L0["hist"].items():
            rs1 = L1["hist"].get(s, [])
            for j, (r0, r1) in enumerate(zip(rs0, rs1)):
                if r0 == r1:
                    continue
                if isinstance(r1, tuple) and r1 and r1[0] == "redacted" and isinstance(r0, tuple) and r0[0] != "redacted":
                    tombs += 1
                    if str(r1[1]) != sha(canonical_record(s, j + 1, r0)):
                        notes.append(f"Batch: tombstone ({s},{j + 1}) digest != SHA-256(CanonicalRecord)")
                    if (str(r1[3]), str(r1[4])) != (str(r0[0]), str(r0[1])):
                        notes.append(f"Batch: tombstone ({s},{j + 1}) lost op/kind")
                    if conformance.spec_member(r0, tgt, ends) is False:
                        notes.append(f"Batch: tombstoned ({s},{j + 1}) outside the target {tgt}")
                    if S0 is not None:
                        live = fold({}, [r0], {sid: (gname(v[3]), str(v[0]), str(v[1]), str(v[2]))
                                               for sid, v in stmts_of(sb).items() if isinstance(v, tuple) and len(v) >= 4})
                        hit = [k for k in live if k in S0 and k[0] in ("node", "edge")]
                        if hit:
                            notes.append(f"Batch: tombstone of live content {hit[:2]} (theorem_no_tombstone_of_live)")
                else:
                    others.append((s, j + 1))
        if others:
            notes.append(f"redaction changed records other than by tombstoning: {others[:4]}")
        audit = [s for s in set(L1["hist"]) - set(L0["hist"])]
        if audit:
            rs = [r for s in audit for r in L1["hist"][s]]
            if not all(isinstance(r, tuple) and str(r[0]) == "redact" for r in rs):
                notes.append("Audit: the new revision holds records other than redact records")
            n = sum(int(str(r[5])[1:]) for r in rs if isinstance(r, tuple) and len(r) > 5 and str(r[0]) == "redact"
                    and str(r[5]).startswith("S") and str(r[5])[1:].isdigit())
            if n != L0["count"] + tombs:
                notes.append(f"Audit: counts {n} != count before {L0['count']} + this call's tombstones {tombs}")
            if L1["marker"] is not None:
                notes.append("Audit left a marker")
            src = [json.loads(r[5]) for r in (ra or {}).get("revisions", []) if str(r[0]) in map(str, audit) and r[5]]
            if src and src[0].get("target_sha256") != o.get("digest"):
                notes.append("Audit: target_sha256 of the redaction revision is not this target's")
        elif tombs:
            if L1["marker"] != o.get("digest"):
                notes.append(f"Batch: tombstones under marker {L1['marker']} (not this target's)")
            if L1["count"] != L0["count"] + tombs:
                notes.append(f"Batch: count {L0['count']} -> {L1['count']} with {tombs} tombstones")
        if not tombs and not audit and not stutter_ledger and L0["marker"] == L1["marker"]:
            if L0["tuples"] != L1["tuples"]:
                notes.append("redaction changed live tuple entries")
        if S0 is not None and not stutter_store:
            notes.append("redaction changed the store")
        if audit and L0["tuples"] != L1["tuples"]:
            notes.append(f"Final's DropStatements removed live tuple entries {sorted(set(L0['tuples']) - set(L1['tuples']))[:3]}")
        return notes
    return [f"no contract label for op {o['op']}"]


def invariants(o, st):
    notes = []
    L = contract_view(st)
    if L["count"] != sum(L["tally"].values()):
        notes.append(f"ledger_inv: count {L['count']} != tally {sum(L['tally'].values())}")
    if L["marker"] is None and (L["count"] or L["tally"]):
        notes.append("ledger_inv: no marker but counters left")
    for k, v in L["idem"].items():
        if not (isinstance(v, tuple) and int(v[0]) <= L["head"]):
            notes.append(f"ledger_inv: idem {k} names no revision")
    stm = stmts_of(st)
    for t, sid in L["tuples"].items():
        row = stm.get(sid)
        if not (isinstance(row, tuple) and str(row[5]) == "" and (gname(row[3]), str(row[0]), str(row[1]), str(row[2])) == t):
            notes.append(f"bijection: tuple {t} -> {sid} has no matching live stmt")
    for sid, row in stm.items():
        if isinstance(row, tuple) and len(row) >= 6 and str(row[5]) == "":
            t = (gname(row[3]), str(row[0]), str(row[1]), str(row[2]))
            if L["tuples"].get(t) != sid:
                notes.append(f"bijection: live stmt {sid} {t} has no tuple entry")
    ra = o.get("rows_after")
    if ra is not None:
        S, named = alpha_store(ra)
        edges = {k[1:] for k in S if k[0] == "edge"}
        for t in L["tuples"]:
            if t not in edges:
                notes.append(f"stmts_ok: tuple entry {t} names no live edge row")
        rep = replay_hist(L["hist"], stm)
        recorded = {k[1:] for k in rep if k[0] == "edge"}
        for e in edges & recorded:
            if e not in L["tuples"]:
                notes.append(f"inv_stmts (ERS-I3): recorded live edge {e} has no statement entry")
        diff = sorted(set(rep.items()) ^ set(S.items()))
        if diff:
            notes.append(f"inv_replay: replay(hist) and alpha(rows) differ on {len(diff)} key(s) (pending targets, "
                         f"unrecorded writes or divergence), e.g. {diff[:3]}")
        if L["marker"] is not None:
            m = st.get(("redacting",))
            tgt = (str(m[1]), str(m[2]))
            live = [k for k in S if (tgt[1] and k[0] in ("node",) and str(k[1]).startswith(tgt[1]) and tgt[0] == "")
                    or (not tgt[1] and k[0] == "edge" and k[1] == tgt[0])]
            if live:
                notes.append(f"inv_mark: marker of {tgt} while {len(live)} of its rows are live")
        if named:
            notes.append(f"abstraction: {len(named)} named-graph node row(s) without records (EnsureEndpoint), outside alpha")
    return notes


def main() -> int:
    p = Path(sys.argv[1])
    trace = json.loads(p.read_text())
    rep = check(trace)
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({"ops": len(rep["ops"]), "violations": rep["violations"], "premise_instances": rep["premise_instances"],
                      "invariant_notes": rep["invariant_notes"][:40], "skipped": rep.get("skipped")}, indent=1, default=str))
    return 0 if not rep["violations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
