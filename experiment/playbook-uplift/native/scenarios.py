#!/usr/bin/env python3
"""Live scenarios for erasure -> redaction -> replay on IRIS Community (playbook §3.7).

    python experiment/playbook-uplift/native/scenarios.py [--only NAME ...] [--out DIR]

Each scenario resets the dedicated namespace, drives the product through its public API (and, for the races, through
a second IRIS process that holds a lock), observes the whole stored state after every step, checks the expectations
named in the scenario, and writes its trace to DIR/traces/<name>.json for the model's trace checker. A scenario that
demonstrates a defect states the defect as its expectation ("observed-as-predicted"), so its pass means the defect
was reproduced, and the finding id is in its record.

Exit status 0 when every check of every selected scenario held.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ivg_native import (Background, Changeset, Conn, load_probe, observe, reset, strings_in, terminate,  # noqa: E402
                        wait_until)
from iris_vector_graph.ledger.errors import (IdempotencyConflictError, IdempotencyRedactedError,  # noqa: E402
                                             LedgerDisabledError, RedactionInProgressError, RedactionTargetLiveError)

GA, GB = "gTenantA", "gTenantB"
NEEDLES_A = ("tenantA", "gTenantA", "TenantALabel", "alphaSecret")
NEEDLES_B = ("tenantB", "gTenantB", "TenantBLabel", "bravoSecret")
SCENARIOS: Dict[str, Callable] = {}


def scenario(fn):
    SCENARIOS[fn.__name__] = fn
    return fn


class Run:
    def __init__(self, name: str):
        self.name, self.checks, self.trace, self.notes = name, [], [], {}

    def check(self, desc: str, cond: bool, detail: Any = "") -> bool:
        self.checks.append({"check": desc, "ok": bool(cond), "detail": detail if not cond else ""})
        print(f"  [{'ok' if cond else 'FAIL'}] {desc}" + ("" if cond else f"  -- {str(detail)[:400]}"))
        return bool(cond)

    @property
    def ok(self) -> bool:
        return all(x["ok"] for x in self.checks)

    def step(self, c: Conn, label: str, **args) -> Dict[str, Any]:
        s = observe(c)
        self.trace.append({"label": label, "args": args, "state": s})
        v = l2_violations(s)
        self.check(f"L2 invariants hold after '{label}'", not v, v[:5])
        return s


FREE = ("message", "source", "correlation_id", "idempotency_key")


def l2_violations(s: Dict[str, Any]) -> List[str]:
    """The machine's invariants at a transaction boundary (the executable twin of proofs/src/l2.rs inv)."""
    v = []
    tomb: Dict[str, int] = {}
    for k, rec in s["rec"].items():
        if rec[0] == "redacted":
            tomb[k.split(":")[0]] = tomb.get(k.split(":")[0], 0) + 1
    rr = set(map(str, s["redactedRev"]))
    for q in tomb:
        if q not in rr:
            v.append(f"tombstone in revision {q} without redactedRev")
        if any(s["revisions"][q][x] for x in FREE):
            v.append(f"tombstone in revision {q} that keeps free text")
    v += [f"redactedRev {q} without a tombstone" for q in rr if q not in tomb]
    v += [f"retry key {k} bound to redacted revision {val[0]}" for k, val in s["idem"].items() if val[0] in tomb]
    count: Dict[str, int] = {}
    for k in s["rec"]:
        count[k.split(":")[0]] = count.get(k.split(":")[0], 0) + 1
    v += [f"revision {q} holds {count.get(q, 0)} records, op_count {rv['op_count']}" for q, rv in s["revisions"].items()
          if count.get(q, 0) != rv["op_count"]]
    if s["marker"] is None and (s["counters"] or s["redactingRevs"]):
        v.append("redaction counters without a marker")
    if s["marker"] is not None and int(s["counters"].get("records", 0)) != sum(int(x) for x in s["redactingRevs"].values()):
        v.append("records counter differs from the per-revision counts")
    edges = {(e[1], e[2], e[3], e[0]) for e in s["content"]["edges"]}
    v += [f"live statement {sid} without its row" for sid, row in s["stmt"].items()
          if row[5] == "" and (row[0], row[1], row[2], row[3].replace("\x00", "")) not in edges]
    return v


# ------------------------------------------------------------------------------------------- the two-tenant world


def _cs(message, corr, key, src):
    return Changeset(actor="ingest:etl", actor_type="ingest", message=message, correlation_id=corr,
                     idempotency_key=key, source={"feed": src})


def world_changesets() -> List[Tuple[str, Changeset]]:
    """The upstream fixture's world (tests/integration/test_256_ledger_redaction_e2e.py build_world), as changesets."""
    out = []
    cs = _cs("tenantA load", "tenantA|c1", "tenantA-k1", "tenantA-feed")
    cs.create_node("tenantA|n1", labels=["TenantALabel"], properties={"tenantAKey": "alphaSecret1"})
    cs.create_node("tenantA|n2", properties={"name": "alphaSecretName"})
    cs.create_relationship("tenantA|n1", "LINKS", "tenantA|n2", qualifiers={"weight": "2", "note": "alphaSecretNote"}, graph=GA)
    out.append(("a1", cs))
    cs = _cs("tenantB load", "tenantB|c1", "tenantB-k1", "tenantB-feed")
    cs.create_node("tenantB|n1", labels=["TenantBLabel"], properties={"tenantBKey": "bravoSecret1"})
    cs.create_node("tenantB|n2", properties={"name": "bravoSecretName"})
    cs.create_relationship("tenantB|n1", "LINKS", "tenantB|n2", qualifiers={"weight": "3", "note": "bravoSecretNote"}, graph=GB)
    out.append(("b1", cs))
    cs = _cs("sync tenantA and tenantB", "shared|c1", "shared-k1", "shared-feed")
    cs.set_property("tenantA|n1", "tenantAKey", "alphaSecret2")
    cs.set_property("tenantB|n1", "tenantBKey", "bravoSecret2")
    cs.create_relationship("tenantA|n2", "BACK", "tenantA|n1", graph=GA)
    cs.create_relationship("tenantB|n2", "BACK", "tenantB|n1", graph=GB)
    out.append(("span", cs))
    cs = _cs("tenantA extra", "tenantA|c2", "tenantA-k2", "tenantA-feed")
    cs.create_node("tenantA|n3", properties={"tmp": "alphaSecretTemp"})
    cs.create_relationship("tenantA|n3", "LINKS", "tenantA|n1", qualifiers={"weight": "1"}, graph=GA)
    out.append(("a2", cs))
    cs = _cs("tenantA cleanup", "tenantA|c3", None, "tenantA-feed")
    cs.set_qualifier(("tenantA|n1", "LINKS", "tenantA|n2", GA), "note", "alphaSecretNote2")
    cs.delete_node("tenantA|n3", mode="detach")
    out.append(("a3", cs))
    cs = _cs("tenantB more", "tenantB|c2", "tenantB-k2", "tenantB-feed")
    cs.set_property("tenantB|n2", "name", "bravoSecretName2")
    out.append(("b2", cs))
    return out


def build_world(c: Conn, extra_a: int = 0) -> Dict[str, Any]:
    led = c.eng.ledger
    led.enable()
    revs = {}
    for name, cs in world_changesets():
        revs[name] = led.commit(cs).revision
    for i in range(extra_a):  # more of tenant A, for multi-batch runs
        cs = _cs(f"tenantA bulk {i}", f"tenantA|bulk{i}", f"tenantA-bulk-{i}", "tenantA-feed")
        cs.create_node(f"tenantA|x{i}", properties={"v": f"alphaSecretBulk{i}"})
        cs.create_relationship(f"tenantA|x{i}", "LINKS", "tenantA|n1", qualifiers={"note": f"alphaSecretQ{i}"}, graph=GA)
        revs[f"x{i}"] = led.commit(cs).revision
    return revs


def erase_a(c: Conn) -> None:
    c.eng.erase_graph(GA)
    c.eng.delete_nodes_by_prefix("tenantA|")


def canonical_all(c: Conn, s: Dict[str, Any]) -> Dict[str, str]:
    out = {}
    for key in s["rec"]:
        seq, ordn = map(int, key.split(":"))
        out[key] = str(c.call("Graph.KG.Ledger", "CanonicalRecord", seq, ordn) or "")
    return out


def stmt_ends(s: Dict[str, Any]) -> Dict[str, Tuple[str, str, str]]:
    """Statement id -> (s, o, graph) from every create_rel / delete_rel record (the independent oracle's map)."""
    ends = {}
    for rec in s["rec"].values():
        if rec[0] in ("create_rel", "delete_rel") and rec[2]:
            enc = rec[5] if rec[0] == "create_rel" else rec[4]
            if enc[:1] == "S":
                t = json.loads(enc[1:])
                ends[rec[2]] = (t.get("s", ""), t.get("o", ""), rec[6].replace("\x00", ""))
    return ends


def in_target(rec: List[str], graph: str, match: str, ends) -> bool:
    """The documented target rule (ADR-0013, spec 256 FR-001), written independently of LedgerRedact.Matches."""
    if rec[0] in ("redacted", "redact"):
        return False
    if rec[6].replace("\x00", "") != graph:
        return False
    if not match:
        return True
    if rec[1] == "node":
        return rec[2].startswith(match)
    if rec[0] in ("create_rel", "create_temporal_edge", "delete_rel"):
        enc = rec[5] if rec[0] != "delete_rel" else rec[4]
        t = json.loads(enc[1:]) if enc[:1] == "S" else {}
        return str(t.get("s", "")).startswith(match) or str(t.get("o", "")).startswith(match)
    e = ends.get(rec[2])
    return bool(e) and (e[0].startswith(match) or e[1].startswith(match))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_redacted(r: Run, before: Dict[str, Any], canon: Dict[str, str], after: Dict[str, Any],
                   targets: List[Tuple[str, str]], content_before: Dict[str, Any]) -> None:
    """The business rules of a completed redaction, between a pre-redaction and a post-redaction observation."""
    ends = stmt_ends(before)
    hit = {k for k, rec in before["rec"].items() if any(in_target(rec, g, m, ends) for g, m in targets)}
    r.notes.setdefault("target_records", len(hit))
    r.check("the oracle finds target records before redaction", len(hit) > 0, len(hit))
    r.check("every record position survives (shape)", set(before["rec"]) <= set(after["rec"]),
            sorted(set(before["rec"]) - set(after["rec"]))[:5])
    new_keys = set(after["rec"]) - set(before["rec"])
    new_seqs = {k.split(":")[0] for k in new_keys}
    r.check("records added by the redaction belong to redaction revisions",
            all(after["revisions"][q]["kind"] == "redaction" for q in new_seqs), sorted(new_seqs))
    bad_tomb, bad_keep = [], []
    for k, rec in before["rec"].items():
        now = after["rec"][k]
        if k in hit:
            if not (now[0] == "redacted" and now[1] == sha(canon[k]) and now[3] == rec[0] and now[4] == rec[1]
                    and len(now) == 5):
                bad_tomb.append((k, now))
        elif now != rec:
            bad_keep.append((k, rec, now))
    r.check("each target record is a tombstone holding sha256(CanonicalRecord) and its op", not bad_tomb, bad_tomb[:3])
    r.check("every other record is byte-identical", not bad_keep, bad_keep[:3])
    tomb_seqs = {k.split(":")[0] for k in hit}
    bad_meta = []
    for q, rv in before["revisions"].items():
        now = after["revisions"][q]
        fixed = {x: rv[x] for x in ("revision_id", "parent_id", "kind", "actor", "op_count")}
        if {x: now[x] for x in fixed} != fixed:
            bad_meta.append((q, "fixed fields changed"))
        if q in tomb_seqs:
            if any(now[x] for x in ("message", "source", "correlation_id", "idempotency_key")):
                bad_meta.append((q, "free text kept", now))
        elif now != rv:
            bad_meta.append((q, "untouched revision changed"))
    r.check("a revision with any tombstone loses its four free-text fields; others are unchanged", not bad_meta, bad_meta[:3])
    r.check("redactedRev is exactly the revisions with a tombstone",
            set(map(str, after["redactedRev"])) >= tomb_seqs, (sorted(tomb_seqs), after["redactedRev"]))
    bad_idem = [k for k, v in after["idem"].items() if v[0] in tomb_seqs]
    moved = [k for k, v in before["idem"].items() if v[0] in tomb_seqs]
    r.check("no live retry key points at a redacted revision", not bad_idem, bad_idem)
    r.check("each retry key of a redacted revision is kept only as sha256(key)",
            all(sha(k) in after["idemRedacted"] for k in moved), moved)
    r.check("untouched retry keys are unchanged",
            {k: v for k, v in before["idem"].items() if k not in moved} == after["idem"])
    r.check("no marker or counters remain", after["marker"] is None and not after["counters"] and not after["redactingRevs"],
            (after["marker"], after["counters"]))
    r.check("redaction changes no content", after["content"] == content_before)
    red = [q for q, rv in after["revisions"].items() if rv["kind"] == "redaction"]
    named = set()
    for q in red:
        for k, rec in after["rec"].items():
            if k.split(":")[0] == q:
                named.add(rec[2])
    r.check("the redaction revisions name exactly the redacted revisions", named >= tomb_seqs, (sorted(named), sorted(tomb_seqs)))
    r.check("the redaction revisions hold none of the target's strings",
            not any(n in json.dumps([after["revisions"][q]] + [rec for k, rec in after["rec"].items() if k.split(":")[0] == q])
                    for q in red for n in NEEDLES_A))


# ------------------------------------------------------------------------------------------------ scenarios


@scenario
def premises(r: Run, c: Conn) -> None:
    """P-0001..P-0004 on this IRIS build, with ObjectScript semantics where the product depends on them."""
    load_probe(c)
    c2 = Conn()
    try:
        c.o.kill("^IVGUplift")
        c.o.tStart()
        c.o.set(1, "^IVGUplift", "dirty")
        seen = c2.o.get("^IVGUplift", "dirty")
        c.o.tRollback()
        r.check("P-0002: another process reads a value set inside an open transaction", str(seen) == "1", seen)
        r.check("P-0002: the rollback takes it back", int(c2.o.isDefined("^IVGUplift", "dirty")) == 0)

        lvl = c.call("IVGUplift.Probe", "LockThenUnlockInTxn", "p3")
        held = c2.call("IVGUplift.Probe", "CanLock", "p3")
        c.o.tCommit()
        free = c2.call("IVGUplift.Probe", "CanLock", "p3")
        r.check("P-0003: a lock released by 'Lock -' inside a transaction is still held", str(lvl) == "1" and str(held) == "0",
                (lvl, held))
        r.check("P-0003: it is released when the transaction ends", str(free) == "1", free)

        victim = Conn()
        victim.o.tStart()
        victim.o.set(1, "^IVGUplift", "x")
        victim.o.lock("", 1, "^IVGUplift", "L2")
        terminate(c2, victim.pid)
        gone = wait_until(lambda: int(c2.o.isDefined("^IVGUplift", "x")) == 0, 10)
        r.check("P-0001: a stopped process's open transaction is rolled back", gone)
        try:
            c2.o.lock("", 2, "^IVGUplift", "L2")
            c2.o.unlock("", "^IVGUplift", "L2")
            got = True
        except Exception as e:
            got = str(e)
        r.check("P-0004: a stopped process's lock is freed", got is True, got)
        victim.close()
    finally:
        c2.close()


@scenario
def nested_commit_holds_head(r: Run, c: Conn) -> None:
    """4.7.0: a ledger commit inside the caller's transaction keeps the head lock until the caller ends it."""
    load_probe(c)
    c.eng.ledger.enable()
    c2 = Conn()
    try:
        head0 = c.eng.ledger.head().seq
        c.o.tStart()
        cs = _cs("nested", "n|1", None, "nested")
        cs.create_node("tenantB|nested1")
        err = None
        try:
            c.eng.ledger.commit(cs)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        held = c2.call("IVGUplift.Probe", "CanLockHead")
        c.o.tRollback()
        free = c2.call("IVGUplift.Probe", "CanLockHead")
        r.notes["commit_error"] = err
        r.check("a commit inside an open transaction is accepted", err is None, err)
        r.check("the head lock is held while the caller's transaction is open", str(held) == "0", held)
        r.check("the caller's rollback takes the revision back and frees the lock",
                c2.eng.ledger.head().seq == head0 and str(free) == "1", (c2.eng.ledger.head().seq, head0, free))
    finally:
        c2.close()


@scenario
def mixed_tenant_flow(r: Run, c: Conn) -> None:
    """Two tenants and a spanning revision: erase A, redact A by graph and by prefix, verify, replay."""
    revs = build_world(c)
    s0 = r.step(c, "world")
    canon = canonical_all(c, s0)
    r.check("the scan sees tenant A and tenant B before erasure",
            set(strings_in(s0, NEEDLES_A)) == set(NEEDLES_A) and set(strings_in(s0, NEEDLES_B)) == set(NEEDLES_B))
    v0 = c.eng.ledger.verify()
    r.notes["verify_on_built_world"] = [d.to_wire() for d in v0.differences]
    r.check("F-1401: verify on the built world already diverges, only on tenantA|n3 (detach delete kept its named-graph row)",
            v0.result == "diverges" and [(d.entity_kind, d.entity_id, d.before, d.after) for d in v0.differences]
            == [("node", "tenantA|n3", None, "")], r.notes["verify_on_built_world"])
    erase_a(c)
    s1 = r.step(c, "erase A", graph=GA, prefix="tenantA|")
    r.check("erasure leaves no tenant A content", not any(n in json.dumps(s1["content"]) for n in NEEDLES_A))
    r.check("erasure keeps every record", s1["rec"] == s0["rec"])
    v1 = c.eng.ledger.verify()
    r.check("verify diverges after the erase alone (replay rebuilds A)", v1.result == "diverges", v1.result)
    r.notes["differences_after_erase"] = len(v1.differences)
    rc1 = c.eng.ledger.redact(GA)
    s2 = r.step(c, "redact", graph=GA, prefix="")
    rc2 = c.eng.ledger.redact(None, prefix="tenantA")
    s3 = r.step(c, "redact", graph="", prefix="tenantA")
    r.notes["receipts"] = [rc1.__dict__ | {"redaction": None}, rc2.__dict__ | {"redaction": None}]
    check_redacted(r, s1, canon, s3, [(GA, ""), ("", "tenantA|")], s1["content"])
    r.check("receipts count the tombstones",
            rc1.records_tombstoned + rc2.records_tombstoned == r.notes["target_records"],
            (rc1.records_tombstoned, rc2.records_tombstoned, r.notes["target_records"]))
    r.check("nothing in the ledger holds tenant A", strings_in(s3, NEEDLES_A) == [], strings_in(s3, NEEDLES_A))
    r.check("tenant B's strings are all still in the ledger", set(strings_in(s3, NEEDLES_B)) == set(NEEDLES_B))
    v3 = c.eng.ledger.verify()
    r.check("verify is equal after erase and redaction", v3.result == "equal", [d.to_wire() for d in v3.differences][:5])
    head = c.eng.ledger.head()
    rec = json.dumps({k: sorted(v.items()) if isinstance(v, dict) else v
                      for k, v in c.eng.ledger.reconstruct(head.revision_id).as_comparable().items()}, default=str)
    r.check("replay to the head holds no tenant A", not any(n in rec for n in NEEDLES_A))
    span = revs["span"].seq
    kept = [v for k, v in s3["rec"].items() if k.split(":")[0] == str(span) and v[0] != "redacted"]
    r.check("the spanning revision keeps tenant B's records", any("tenantB" in json.dumps(x) for x in kept) and
            all("tenantA" not in json.dumps(x) for x in kept))
    again = c.eng.ledger.redact(GA)
    s4 = r.step(c, "redact", graph=GA, prefix="")
    r.check("running the same redaction again changes nothing and reports 0",
            again.records_tombstoned == 0 and again.redaction is None and
            {k: v for k, v in s4.items() if k != "revisions"} == {k: v for k, v in s3.items() if k != "revisions"},
            again.__dict__)


@scenario
def retries(r: Run, c: Conn) -> None:
    """Retry keys across tenants after a redaction."""
    revs = build_world(c)
    erase_a(c)
    c.eng.ledger.redact(GA)
    c.eng.ledger.redact(None, prefix="tenantA")
    s0 = r.step(c, "redacted world")
    css = dict(world_changesets())
    for name, exc, desc in [("a1", IdempotencyRedactedError, "tenant A's own retry key"),
                            ("span", IdempotencyRedactedError, "the spanning revision's key, retried by tenant B's writer")]:
        try:
            c.eng.ledger.commit(css[name])
            got = "committed"
        except Exception as e:
            got = type(e).__name__
        r.check(f"a retry with {desc} is refused as idempotency_redacted", got == exc.__name__, got)
    s1 = r.step(c, "refused retries")
    r.check("the refused retries change nothing outside the stats",
            {k: v for k, v in s1.items()} == {k: v for k, v in s0.items()})
    res = c.eng.ledger.commit(dict(world_changesets())["b1"])
    r.check("tenant B's unredacted key replays its first revision",
            res.replayed and res.revision.seq == revs["b1"].seq, (res.replayed, res.revision.seq, revs["b1"].seq))
    cs = _cs("tenantB other", "tenantB|c9", "tenantB-k1", "tenantB-feed")
    cs.set_property("tenantB|n1", "tenantBKey", "different")
    try:
        c.eng.ledger.commit(cs)
        got = "committed"
    except Exception as e:
        got = type(e).__name__
    r.check("tenant B's key with another changeset is a plain conflict", got == IdempotencyConflictError.__name__, got)
    cs = _cs("tenantA again", "tenantA|c9", "tenantA-new", "tenantA-feed")
    cs.create_node("tenantA|n1", properties={"name": "alphaSecretNew"})
    res = c.eng.ledger.commit(cs)
    r.step(c, "re-onboard A")
    r.check("after the redaction finishes, the same ids can be written again with a new key", not res.replayed)
    r.check("verify is equal after the re-onboarding", c.eng.ledger.verify().result == "equal")


@scenario
def paused_and_resumed(r: Run, c: Conn) -> None:
    """Interruption between batches (max_batches), commits in the window, a competing target, resumption."""
    build_world(c, extra_a=6)
    erase_a(c)
    s0 = r.step(c, "erased")
    canon = canonical_all(c, s0)
    part = c.eng.ledger.redact(GA, batch_size=1, max_batches=1)
    s1 = r.step(c, "redact", graph=GA, prefix="", batch=1, max_batches=1)
    r.check("a paused run reports incomplete and one tombstone", not part.complete and part.records_tombstoned == 1,
            part.__dict__)
    r.check("the marker names the target's digest", s1["marker"] is not None and s1["marker"][0] == part.target_sha256)
    r.check("verify reports redaction_in_progress", c.eng.ledger.verify().result == "redaction_in_progress")
    try:
        c.eng.ledger.reconstruct(c.eng.ledger.head().revision_id)
        got = "answered"
    except RedactionInProgressError:
        got = "refused"
    r.check("record readers refuse while the marker exists", got == "refused", got)
    cs = Changeset(actor="ingest:etl", actor_type="ingest")
    cs.create_relationship("tenantB|n1", "LATE", "tenantB|n2", graph=GA)
    try:
        c.eng.ledger.commit(cs)
        got = "committed"
    except RedactionInProgressError:
        got = "refused"
    s2 = r.step(c, "commit refused", graph=GA)
    r.check("a commit with a record in the target is refused and changes nothing", got == "refused" and
            {k: v for k, v in s2.items()} == {k: v for k, v in s1.items()}, got)
    cs = Changeset(actor="ingest:etl", actor_type="ingest")
    cs.set_property("tenantB|n1", "tenantBKey", "bravoSecret3")
    c.eng.ledger.commit(cs)
    s3 = r.step(c, "commit B")
    try:
        c.eng.ledger.redact(None, prefix="tenantA")
        got = "ran"
    except RedactionInProgressError:
        got = "refused"
    s4 = r.step(c, "competing redaction refused")
    r.check("a redaction of another target is refused while the marker exists, and changes nothing",
            got == "refused" and s4 == s3, got)
    done = c.eng.ledger.redact(GA, batch_size=2)
    r.step(c, "redact", graph=GA, prefix="", batch=2)
    r.check("the same target resumes and completes", done.complete and done.redaction is not None and done.batches > 1,
            done.__dict__)
    c.eng.ledger.redact(None, prefix="tenantA")
    s5 = r.step(c, "redact", graph="", prefix="tenantA")
    # The reference "before" is the state after tenant B's commit with tenant A's records as they were before the
    # paused run: the one record the paused run tombstoned is compared against its original.
    before = {**s3, "rec": {**s3["rec"], **s0["rec"]}, "revisions": {**s3["revisions"], **s0["revisions"]},
              "idem": {**s3["idem"], **s0["idem"]}}
    for k in list(before["idem"]):
        if k not in s0["idem"] and k not in s3["idem"]:
            del before["idem"][k]
    canon_b = {**canonical_all(c, {"rec": {k: v for k, v in s3["rec"].items() if k not in s0["rec"]}}), **canon}
    check_redacted(r, before, canon_b, s5, [(GA, ""), ("", "tenantA|")], s3["content"])
    r.check("verify is equal", c.eng.ledger.verify().result == "equal")


def _block_revision_row(holder: Conn, seq: int) -> None:
    holder.o.lock("", 5, "^Graph.KG.LedgerRevisionD", seq)


def _unblock_revision_row(holder: Conn, seq: int) -> None:
    holder.o.unlock("I", "^Graph.KG.LedgerRevisionD", seq)


@scenario
def killed_mid_batch(r: Run, c: Conn) -> None:
    """Interruption inside a batch: stop the redacting process while its transaction is open, then resume."""
    load_probe(c)
    revs = build_world(c, extra_a=4)
    erase_a(c)
    s0 = r.step(c, "erased")
    canon = canonical_all(c, s0)
    block = revs["a2"].seq  # a revision of A after a1 and span: the batch tombstones earlier ones first
    _block_revision_row(c, block)
    bg = Background(lambda cc: cc.redact_raw(GA, "", 1000, 0), "redactor").start()
    progressed = wait_until(lambda: int(str(c.o.get("^IVG.Ledger", "redacting", "n", "records") or 0)) > 0, 10)
    time.sleep(0.5)
    dirty = observe(c)
    stuck = bg.t.is_alive()
    n_dirty = sum(1 for v in dirty["rec"].values() if v[0] == "redacted")
    r.notes["dirty_tombstones"] = n_dirty
    r.check("the redaction is inside its batch, blocked on the revision row", progressed and stuck and n_dirty > 0,
            (progressed, stuck, n_dirty))
    r.check("P-0002 again: the open batch's tombstones and marker are visible to another process",
            dirty["marker"] is not None and n_dirty > 0)
    r.trace.append({"label": "dirty (uncommitted) view", "args": {}, "state": dirty, "uncommitted": True})
    terminate(c, bg.c.pid)
    bg.join(15)
    _unblock_revision_row(c, block)
    r.notes["redactor_error"] = bg.error
    s1 = r.step(c, "process stopped")
    r.check("the stopped batch left no trace: the state equals the state before it",
            {k: v for k, v in s1.items()} == {k: v for k, v in s0.items()},
            [k for k in s0 if s0[k] != s1[k]])
    r.check("the head lock is free again", str(c.call("IVGUplift.Probe", "CanLockHead")) == "1")
    done = c.eng.ledger.redact(GA)
    r.step(c, "redact", graph=GA, prefix="")
    c.eng.ledger.redact(None, prefix="tenantA")
    s2 = r.step(c, "redact", graph="", prefix="tenantA")
    r.check("the same target then runs to completion", done.complete)
    check_redacted(r, s0, canon, s2, [(GA, ""), ("", "tenantA|")], s0["content"])
    r.check("verify is equal", c.eng.ledger.verify().result == "equal")


@scenario
def killed_at_random(r: Run, c: Conn) -> None:
    """Twelve interruptions at spread-out moments of one long run; every stopped state must be a batch boundary."""
    build_world(c, extra_a=150)
    erase_a(c)
    s0 = r.step(c, "erased")
    canon = canonical_all(c, s0)
    kills = []
    for i in range(12):
        bg = Background(lambda cc: cc.redact_raw(GA, "", 2, 0), f"redactor{i}").start()
        time.sleep(0.001 + 0.002 * i)
        alive = bg.t.is_alive()
        if alive:
            terminate(c, bg.c.pid)
        bg.join(15)
        s = r.step(c, "process stopped" if alive else "redact", graph=GA, prefix="", batch=2, trial=i)
        kills.append({"trial": i, "stopped_while_running": alive, "tombstones": sum(1 for v in s["rec"].values() if v[0] == "redacted"),
                      "marker": s["marker"] is not None, "error": bg.error, "result": bg.result})
        if not alive:
            break
    r.notes["kills"] = kills
    r.check("at least five runs were stopped while running", sum(k["stopped_while_running"] for k in kills) >= 5, kills)
    done = c.eng.ledger.redact(GA)
    r.step(c, "redact", graph=GA, prefix="")
    c.eng.ledger.redact(None, prefix="tenantA")
    s2 = r.step(c, "redact", graph="", prefix="tenantA")
    r.check("the target completes after every interruption", done.complete or done.records_tombstoned == 0)
    check_redacted(r, s0, canon, s2, [(GA, ""), ("", "tenantA|")], s0["content"])
    r.check("verify is equal", c.eng.ledger.verify().result == "equal")


@scenario
def commit_in_unmarked_window(r: Run, c: Conn) -> None:
    """F-1302: a commit that lands after the liveness check and before the first tombstone is redacted while live."""
    load_probe(c)
    build_world(c)
    erase_a(c)
    s0 = r.step(c, "erased")
    c.o.lock("", 5, "^IVG.Ledger", "head")  # holds the redaction at its first batch, after its liveness check
    bg = Background(lambda cc: cc.redact_raw(GA, "", 2000, 0), "redactor").start()
    time.sleep(1.0)
    r.check("the redaction passed its liveness check and waits for the head lock", bg.t.is_alive())
    cs = _cs("tenantA returns", "tenantA|c9", "tenantA-k9", "tenantA-feed")
    cs.create_node("tenantA|n9", properties={"name": "alphaSecretLate"})
    cs.create_relationship("tenantA|n9", "LINKS", "tenantA|n9", qualifiers={"note": "alphaSecretLateNote"}, graph=GA)
    late = c.eng.ledger.commit(cs).revision  # this process holds the head lock, so its commit goes first
    s1 = r.step(c, "commit into the target", graph=GA)
    c.o.unlock("", "^IVG.Ledger", "head")
    bg.join(60)
    s2 = r.step(c, "redact", graph=GA, prefix="")
    r.notes["redact_result"] = bg.result
    late_recs = {k: v for k, v in s2["rec"].items() if k.split(":")[0] == str(late.seq)}
    live_ga = [e for e in s2["content"]["edges"] if e[0] == GA]
    r.check("the late commit's content is live in the target graph", len(live_ga) == 1, live_ga)
    r.check("the late commit's relationship record became a tombstone while its content is live",
            any(v[0] == "redacted" for v in late_recs.values()), late_recs)
    r.check("its metadata was cleared and its retry key moved to idemRedacted",
            s2["revisions"][str(late.seq)]["message"] == "" and "tenantA-k9" not in s2["idem"])
    r.check("the run then refuses at its final step and leaves the marker",
            bg.result and bg.result.get("error") == "target_live" and s2["marker"] is not None, bg.result)
    r.check("verify reports redaction_in_progress", c.eng.ledger.verify().result == "redaction_in_progress")
    again = c.redact_raw(GA, "", 2000, 0)
    r.check("a rerun is refused (target live) and the marker stays", again.get("error") == "target_live", again)
    cs = Changeset(actor="ingest:etl", actor_type="ingest")
    cs.set_qualifier(("tenantA|n9", "LINKS", "tenantA|n9", GA), "note", "x")
    try:
        c.eng.ledger.commit(cs)
        got = "committed"
    except RedactionInProgressError:
        got = "refused"
    r.check("the target's live content cannot be changed through the ledger until it is erased again", got == "refused", got)
    erase_a(c)
    r.step(c, "erase A again", graph=GA, prefix="tenantA|")
    fin = c.redact_raw(GA, "", 2000, 0)
    fin2 = c.redact_raw("", "tenantA", 2000, 0)
    s3 = r.step(c, "redact", graph=GA, prefix="")
    r.check("only a second erasure lets the redaction finish", fin.get("complete") is True and fin2.get("complete") is True,
            (fin, fin2))
    r.check("verify is then equal", c.eng.ledger.verify().result == "equal")


@scenario
def two_targets_at_once(r: Run, c: Conn) -> None:
    """F-1303: two redactions of different targets that start together both run; the audit mixes them."""
    build_world(c)
    erase_a(c)
    s0 = r.step(c, "erased")
    canon = canonical_all(c, s0)
    c.o.lock("", 5, "^IVG.Ledger", "head")
    g = Background(lambda cc: cc.redact_raw(GA, "", 1, 0), "graph").start()
    p = Background(lambda cc: cc.redact_raw("", "tenantA", 1, 0), "prefix").start()
    time.sleep(1.0)
    r.check("both runs passed their 'another redaction?' check and wait for the head lock", g.t.is_alive() and p.t.is_alive())
    c.o.unlock("", "^IVG.Ledger", "head")
    g.join(60)
    p.join(60)
    s1 = r.step(c, "two concurrent redactions")
    r.notes["graph_result"], r.notes["prefix_result"] = g.result, p.result
    both_ran = (g.result or {}).get("ok") and (p.result or {}).get("ok")
    r.check("neither run was refused as redaction_in_progress", bool(both_ran), (g.result, p.result))
    red = {q: rv for q, rv in s1["revisions"].items() if rv["kind"] == "redaction"}
    r.notes["redaction_revisions"] = red
    audit = {json.loads(rv["source"])["target_sha256"]: json.loads(rv["source"])["records"] for rv in red.values()}
    tg = str(c.call("Graph.KG.LedgerRedact", "TargetDigest", GA, ""))
    tp = str(c.call("Graph.KG.LedgerRedact", "TargetDigest", "", "tenantA|"))
    ends = stmt_ends(s0)
    truth = {tg: sum(1 for rec in s0["rec"].values() if in_target(rec, GA, "", ends)),
             tp: sum(1 for rec in s0["rec"].values() if in_target(rec, "", "tenantA|", ends))}
    r.notes["audit_records"], r.notes["true_records"] = audit, truth
    r.check("each target still gets one redaction revision", sorted(audit) == sorted(truth), (audit, truth))
    r.check("the audits' record counts are mixed between the two targets (shared counters)",
            audit != truth and sum(audit.values()) == sum(truth.values()), (audit, truth))
    check_redacted(r, s0, canon, s1, [(GA, ""), ("", "tenantA|")], s0["content"])
    r.check("verify is equal", c.eng.ledger.verify().result == "equal")


@scenario
def default_graph_without_prefix(r: Run, c: Conn) -> None:
    """F-1304: redacting the default graph with no prefix tombstones genesis records of nodes live in a named graph."""
    c.eng.create_node("tenantB|m1", labels=["TenantBLabel"], properties={"k": "bravoSecretM1"}, graph=GB)
    c.eng.create_node("tenantB|m2", properties={"k": "bravoSecretM2"}, graph=GB)
    c.eng.create_edge("tenantB|m1", "LINKS", "tenantB|m2", graph=GB)
    c.eng.ledger.enable()
    s0 = r.step(c, "genesis over a named graph")
    node_recs = {k: v for k, v in s0["rec"].items() if v[1] == "node"}
    r.check("genesis records the named graph's nodes with an empty graph", node_recs and all(v[6] in ("", "\x00") for v in node_recs.values()),
            node_recs)
    r.check("verify is equal before", c.eng.ledger.verify().result == "equal")
    res = c.redact_raw("", "", 2000, 0)
    s1 = r.step(c, "redact", graph="", prefix="")
    r.notes["result"] = res
    gone = [k for k in node_recs if s1["rec"][k][0] == "redacted"]
    r.check("redact(None) is accepted although tenant B's nodes are live", res.get("ok") is True, res)
    r.check("it tombstones the node records of nodes that are live in a named graph", len(gone) == len(node_recs), gone)
    v = c.eng.ledger.verify()
    r.check("verify then diverges on live content", v.result == "diverges", v.result)
    r.notes["differences"] = [d.to_wire() for d in v.differences][:6]


@scenario
def graph_per_tenant_unprefixed(r: Run, c: Conn) -> None:
    """F-1305: one graph per tenant with unprefixed ids: erase+redact(graph) cannot remove A's node ids or restore verify."""
    for g, ids in ((GA, ("n1", "n2")), (GB, ("m1", "m2"))):
        for i in ids:
            c.eng.create_node(i, properties={"secret": ("alphaSecret" if g == GA else "bravoSecret") + i}, graph=g)
        c.eng.create_edge(ids[0], "LINKS", ids[1], graph=g)
    c.eng.ledger.enable()
    s0 = r.step(c, "genesis")
    r.check("verify is equal before", c.eng.ledger.verify().result == "equal")
    c.eng.erase_graph(GA)
    s1 = r.step(c, "erase A", graph=GA, prefix="")
    res = c.eng.ledger.redact(GA)
    s2 = r.step(c, "redact", graph=GA, prefix="")
    left = [v for v in s2["rec"].values() if v[0] != "redacted" and ("n1" in v or "n2" in v)]
    r.check("redact(gTenantA) completes", res.complete, res.__dict__)
    r.check("tenant A's node ids and property values stay in the ledger", bool(left) and "alphaSecret" in json.dumps(s2["rec"]), left[:4])
    v = c.eng.ledger.verify()
    r.check("verify diverges: replay rebuilds tenant A's nodes", v.result == "diverges", v.result)
    r.notes["differences"] = [d.to_wire() for d in v.differences][:6]


@scenario
def retry_between_erase_and_redact(r: Run, c: Conn) -> None:
    """F-1306: a replayed retry re-applies post-commit properties, reviving an erased node's content and blocking redaction."""
    from iris_vector_graph.ledger.changeset import REVISION_ID_SENTINEL
    c.eng.ledger.enable()

    def changeset():
        cs = _cs("tenantA audit node", "tenantA|c7", "tenantA-pcp", "tenantA-feed")
        cs.create_node("tenantA|p1", properties={"name": "alphaSecretAudit"})
        cs.post_commit_properties = {"tenantA|p1": {"committed_rev": REVISION_ID_SENTINEL}}
        return cs
    first = c.eng.ledger.commit(changeset())
    r.check("the first commit applies its post-commit property", first.post_commit_applied, first.__dict__)
    s0 = r.step(c, "commit with a post-commit property")
    c.eng.delete_nodes_by_prefix("tenantA|")
    s1 = r.step(c, "erase A", graph="", prefix="tenantA|")
    r.check("the node erasure removes the node and all its properties",
            not any(p[1].startswith("tenantA|") for p in s1["content"]["props"]) and
            not any(n[1].startswith("tenantA|") for n in s1["content"]["nodes"]), s1["content"])
    again = c.eng.ledger.commit(changeset())
    s2 = r.step(c, "retry with the same key")
    revived = [p for p in s2["content"]["props"] if p[1].startswith("tenantA|")]
    r.notes["retry"] = {"replayed": again.replayed, "post_commit_applied": again.post_commit_applied, "revived": revived}
    r.check("the retry is a replay (no new revision)", again.replayed and s2["head"] == s1["head"], (again.replayed, s2["head"]))
    r.check("the replay re-applies the post-commit property: an erased node's property is live again",
            again.post_commit_applied and len(revived) == 1 and revived[0][2] == "committed_rev", revived)
    r.check("no node row came back: the property has no node", not any(n[1] == "tenantA|p1" for n in s2["content"]["nodes"]))
    try:
        c.eng.ledger.redact(None, prefix="tenantA")
        got = "ran"
    except RedactionTargetLiveError:
        got = "refused"
    s3 = r.step(c, "redact refused (target live)")
    r.check("the redaction of tenant A is then refused as live, and nothing changes", got == "refused" and s3 == s2, got)
    c.eng.delete_nodes_by_prefix("tenantA|")
    leftover = [p for p in r.step(c, "erase A again")["content"]["props"] if p[1].startswith("tenantA|")]
    r.notes["leftover_after_second_erase"] = leftover
    if leftover:
        c.sql("DELETE FROM Graph_KG.rdf_props WHERE s = ?", "tenantA|p1")
        c.conn.commit()
        r.step(c, "orphan property removed by hand")
    done = c.eng.ledger.redact(None, prefix="tenantA")
    r.step(c, "redact", graph="", prefix="tenantA")
    r.check("once the orphan property is gone, the redaction completes", done.complete)


@scenario
def reader_races_redaction(r: Run, c: Conn) -> None:
    """F-1402: a record reader checks for a redaction before it reads; a batch that commits in between is read half done.

    The interleaving is forced in this test process only: the reader's record fetch (replay.iter_records_sql) is wrapped
    so that, after the reader's marker check and before its first read, another IRIS process commits one redaction batch.
    No product code changes.
    """
    import iris_vector_graph.ledger.replay as rp
    build_world(c)
    erase_a(c)
    r.step(c, "erased")
    head = c.eng.ledger.head().revision_id
    full = c.eng.ledger.reconstruct(head).as_comparable()
    ga_full = sorted(k for k in full["rels"] if k[3] == GA)
    other = Conn()
    orig = rp.iter_records_sql
    fired = {}

    def racing(conn, schema, seq_from, seq_to):
        if not fired:
            fired["batch"] = other.redact_raw(GA, "", 1, 1)
        return orig(conn, schema, seq_from, seq_to)

    rp.iter_records_sql = racing
    err = None
    try:
        view = c.eng.ledger.reconstruct(head).as_comparable()
    except Exception as e:
        view, err = None, f"{type(e).__name__}: {e}"
    finally:
        rp.iter_records_sql = orig
        other.close()
    s1 = r.step(c, "reader raced one batch")
    ga_view = sorted(k for k in (view or {"rels": {}})["rels"] if k[3] == GA)
    r.notes["batch"] = fired.get("batch")
    r.notes["ga_statements_full"], r.notes["ga_statements_in_view"] = [list(map(str, k)) for k in ga_full], [list(map(str, k)) for k in ga_view]
    r.check("one redaction batch committed between the reader's check and its read",
            bool(fired.get("batch", {}).get("ok")) and fired["batch"].get("records_tombstoned") == 1, fired.get("batch"))
    r.check("the marker exists after the race", s1["marker"] is not None)
    r.check("the reader answered instead of refusing", err is None, err)
    r.check("its view shows tenant A's graph half redacted", 0 < len(ga_view) < len(ga_full), (len(ga_view), len(ga_full)))
    try:
        c.eng.ledger.reconstruct(head)
        again = "answered"
    except RedactionInProgressError:
        again = "refused"
    r.check("the same reader called now refuses (the marker is seen)", again == "refused", again)
    c.eng.ledger.redact(GA)
    c.eng.ledger.redact(None, prefix="tenantA")
    r.step(c, "redact", graph=GA, prefix="")
    r.check("the redaction then completes and verify is equal", c.eng.ledger.verify().result == "equal")


@scenario
def disabled_mid_run(r: Run, c: Conn) -> None:
    """The ledger disabled between batches: the run refuses, keeps its marker, and resumes once re-enabled."""
    build_world(c)
    erase_a(c)
    s0 = r.step(c, "erased")
    canon = canonical_all(c, s0)
    c.eng.ledger.redact(GA, batch_size=1, max_batches=1)
    r.step(c, "redact", graph=GA, prefix="", batch=1, max_batches=1)
    c.eng.ledger.disable()
    s1 = r.step(c, "disable")
    try:
        c.eng.ledger.redact(GA)
        got = "ran"
    except LedgerDisabledError:
        got = "refused"
    s2 = r.step(c, "redact refused (disabled)")
    r.check("a redaction is refused while the ledger is disabled and changes nothing", got == "refused" and s2 == s1, got)
    c.eng.ledger.enable()
    r.step(c, "enable")
    done = c.eng.ledger.redact(GA)
    c.eng.ledger.redact(None, prefix="tenantA")
    s3 = r.step(c, "redact", graph="", prefix="tenantA")
    r.check("after re-enabling, the same target resumes and completes", done.complete)
    check_redacted(r, s0, canon, s3, [(GA, ""), ("", "tenantA|")], s0["content"])


# ------------------------------------------------------------------------------------------------ driver


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out", default=os.path.join(os.environ["RUN_DIR"], "native"))
    a = ap.parse_args()
    out = Path(a.out)
    (out / "traces").mkdir(parents=True, exist_ok=True)
    names = a.only or list(SCENARIOS)
    summary = {}
    for name in names:
        print(f"== {name}")
        r = Run(name)
        c = Conn()
        try:
            reset(c)
            SCENARIOS[name](r, c)
        except Exception:
            r.check("scenario ran to the end", False, traceback.format_exc())
        finally:
            try:
                c.o.releaseAllLocks()
            except Exception:
                pass
            c.close()
        (out / "traces" / f"{name}.json").write_text(json.dumps(
            {"scenario": name, "doc": SCENARIOS[name].__doc__, "checks": r.checks, "notes": r.notes,
             "trace": r.trace}, indent=1, sort_keys=True, default=str))
        summary[name] = {"ok": r.ok, "checks": len(r.checks), "failed": [x["check"] for x in r.checks if not x["ok"]]}
        print(f"== {name}: {'PASS' if r.ok else 'FAIL'} ({len(r.checks)} checks)")
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0 if all(v["ok"] for v in summary.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
