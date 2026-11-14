#!/usr/bin/env python3
"""Binding probe: real ledger records before and after erase + redact, compared with the model.

World: two tenants (default-graph prefixes tenantA|/tenantB| plus their own graphs gA/gB), a revision
spanning both tenants with an idempotency key, qualifier updates by statement and by tuple, a detach
delete with cascade, a default-graph relationship of tenant A, and temporal edges in gA.

Expected outcomes are derived two ways, both independent of the product's implementation:
  L1   — from the probe's own knowledge of what each statement and node belongs to;
  twin — the Verus-verified executable twin of redaction.rs `matches` run on the observed records
         (the as-built rule; knowledge resolved by the trusted adapter in redaction_common.py).
Observed: every record after redaction must be byte-identical unless the twin classified it Yes for
one of the two targets, in which case it must be the tombstone ("redacted", sha256(canonical original),
flags, op, kind). Revision metadata, idempotency bindings, the audit revisions and verify() are checked
too. Two observation-mutation controls check that the comparison notices a changed decisive field.
"""
from __future__ import annotations

import copy
import json

from redaction_common import (canonical, connect, cs, engine, ensure_schema, h, knowledge, ledger_global,
                              ledger_records, marker, record, reset, revision_rows, sha256, stmt_rows,
                              twin_classify, verdict)

GA, GB = "gA", "gB"


def build(eng):
    led = eng.ledger
    led.enable()
    c = cs("tenantA load", "tenantA|c1", "tA-k1", "tenantA-feed")
    c.create_node("tenantA|n1", labels=["TA"], properties={"secret": "alpha1"})
    c.create_node("tenantA|n2", properties={"name": "alphaName"})
    c.create_relationship("tenantA|n1", "LINKS", "tenantA|n2", qualifiers={"weight": "2", "note": "alphaNote"}, graph=GA)
    c.create_relationship("tenantA|n1", "SELF", "tenantA|n2", qualifiers={"note": "alphaDefault"})  # default graph
    led.commit(c)
    c = cs("tenantB load", "tenantB|c1", "tB-k1", "tenantB-feed")
    c.create_node("tenantB|n1", labels=["TB"], properties={"secret": "bravo1"})
    c.create_node("tenantB|n2", properties={"name": "bravoName"})
    c.create_relationship("tenantB|n1", "LINKS", "tenantB|n2", qualifiers={"weight": "3"}, graph=GB)
    led.commit(c)
    c = cs("sync both", "shared|c1", "shared-k1", "shared-feed")
    c.set_property("tenantA|n1", "secret", "alpha2")
    c.set_property("tenantB|n1", "secret", "bravo2")
    c.create_relationship("tenantA|n2", "BACK", "tenantA|n1", graph=GA)
    c.create_relationship("tenantB|n2", "BACK", "tenantB|n1", graph=GB)
    led.commit(c)
    c = cs("tenantA extra", "tenantA|c2", "tA-k2", "tenantA-feed")
    c.create_node("tenantA|n3", properties={"tmp": "alphaTemp"})
    c.create_relationship("tenantA|n3", "LINKS", "tenantA|n1", qualifiers={"weight": "1"}, graph=GA)
    c.create_temporal_edge("tenantA|n1", "METRIC", "tenantA|n2", ts=1700000000, weight=5.0, graph=GA)
    led.commit(c)
    c = cs("tenantA cleanup", "tenantA|c3", None, "tenantA-feed")
    c.set_qualifier(("tenantA|n1", "LINKS", "tenantA|n2", GA), "note", "alphaNote2")
    c.set_qualifier(("tenantA|n1", "SELF", "tenantA|n2", None), "note", "alphaDefault2")
    c.delete_node("tenantA|n3", mode="detach")
    led.commit(c)
    c = cs("tenantB more", "tenantB|c2", "tB-k2", "tenantB-feed")
    c.set_property("tenantB|n2", "name", "bravoName2")
    c.create_temporal_edge("tenantB|n1", "METRIC", "tenantB|n2", ts=1700000001, weight=6.0, graph=GB)
    led.commit(c)


def l1_belongs(f, target_graph: str, prefix: str) -> bool:
    """The probe's own attribution (what it wrote), not the product's matcher."""
    op, kind, eid, g = f[0], f[1], str(f[2] or ""), str(f[6] or "").replace("\x00", "")
    if op in ("redacted", "redact"):
        return False
    if target_graph == GA:  # whole graph gA
        return g == GA
    # default graph, prefix tenantA|
    if g != "":
        return False
    if kind == "node":
        return eid.startswith("tenantA|")
    # the only default-graph relationship the probe made is tenantA|n1 -SELF-> tenantA|n2
    return kind in ("rel", "temporal_edge")


def compare(before, after, canon, yes) -> list:
    problems = []
    for key, f in before.items():
        a = after.get(key)
        if key in yes:
            exp = ["redacted", sha256(canon[key]), f[7] if len(f) > 7 else "", f[0], f[1]]
            if a is None or [str(x or "") for x in a[:5]] != [str(x or "") for x in exp]:
                problems.append({"pos": key, "kind": "tombstone mismatch", "expected": exp, "observed": a})
        else:
            if a != f:
                problems.append({"pos": key, "kind": "changed but should not", "before": f, "observed": a})
    return problems


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    schema = ensure_schema(eng)
    reset(eng, native)
    build(eng)
    eng.erase_graph(GA)
    eng.delete_nodes_by_prefix("tenantA|")
    verify_after_erase = eng.ledger.verify().result

    before = ledger_records(native)
    canon = {k: canonical(native, *k) for k in before}
    revs_before = revision_rows(conn)
    stmts = stmt_rows(native)
    # ADR-0004: no live statement outlives its content — after erase_graph(gA) and the prefix erase,
    # no ^IVG.Ledger("stmt") entry may name gA or a tenantA endpoint in the default graph
    stmt_leftovers = {sid: row for sid, row in stmts.items()
                      if str(row[3] or "").replace("\x00", "") == GA
                      or (str(row[3] or "").replace("\x00", "") == "" and (str(row[0]).startswith("tenantA|") or str(row[2]).startswith("tenantA|")))}
    idem_before = {str(k[1]): v for k, v in ledger_global(native, "idem").items() if len(k) == 2}

    yes, unknown, l1_diff = set(), set(), []
    for tg, pfx in ((GA, ""), ("", "tenantA")):
        pre, live = knowledge(before, stmts, tg)
        cls = twin_classify(before, tg, pfx, "|", pre, live)
        for key, c in cls.items():
            if c == "Yes":
                yes.add(key)
            elif c == "Unknown":
                unknown.add(key)
            if (c == "Yes") != l1_belongs(before[key], tg, pfx):
                l1_diff.append({"pos": key, "target": [tg, pfx], "twin": c, "record": before[key]})

    r1 = eng.ledger.redact(GA)
    r2 = eng.ledger.redact(None, prefix="tenantA")
    after = ledger_records(native)
    revs_after = revision_rows(conn)
    verify_after = eng.ledger.verify()
    idem_after = {str(k[1]): v for k, v in ledger_global(native, "idem").items() if len(k) == 2}
    idem_red = {str(k[1]) for k in ledger_global(native, "idemRedacted") if len(k) == 2}

    problems = compare(before, after, canon, yes)
    tomb_revs = {seq for (seq, _o) in yes}
    meta_problems = []
    for seq, row in revs_before.items():
        ra = revs_after.get(seq)
        if seq in tomb_revs:
            exp = dict(row, message=None, source=None, correlation_id=None, idempotency_key=None)
            norm = lambda d: {k: (None if v in ("", None) else v) for k, v in d.items()}
            if norm(ra) != norm(exp):
                meta_problems.append({"seq": seq, "expected": exp, "observed": ra})
            key = row.get("idempotency_key")
            if key and (key in idem_after or sha256(key) not in idem_red):
                meta_problems.append({"seq": seq, "idem": key, "still_bound": key in idem_after})
        elif ra != row:
            meta_problems.append({"seq": seq, "changed_but_untouched": True, "before": row, "after": ra})
    new_revs = [revs_after[s] for s in sorted(set(revs_after) - set(revs_before))]
    audit_text = json.dumps(new_revs, default=str) + json.dumps({str(k): v for k, v in after.items() if k[0] in {r["seq"] for r in new_revs}}, default=str)
    leaks = [n for n in ("tenantA", "gA", "alpha", "TA") if n in audit_text]
    exp_digests = [sha256(GA + "\x00"), sha256("" + "\x00" + "tenantA|")]

    # observation-mutation controls: a changed decisive field must be noticed by the comparison
    mut1 = copy.deepcopy(after)
    k_keep = next(k for k in sorted(before) if k not in yes)
    mut1[k_keep] = list(mut1[k_keep]); mut1[k_keep][5] = "Smutated"
    mut2 = copy.deepcopy(after)
    k_tomb = next(iter(sorted(yes)))
    mut2[k_tomb] = list(mut2[k_tomb]); mut2[k_tomb][1] = "0" * 64
    controls = {"value_change_detected": bool(compare(before, mut1, canon, yes)),
                "digest_change_detected": bool(compare(before, mut2, canon, yes))}

    data = {
        "schema": schema, "verify_after_erase": verify_after_erase, "verify_after_redaction": verify_after.result,
        "verify_differences": [vars(d) for d in verify_after.differences][:20],
        "records_before": len(before), "twin_yes": sorted(yes), "twin_unknown": sorted(unknown),
        "l1_vs_twin": l1_diff, "record_problems": problems, "metadata_problems": meta_problems,
        "receipts": [vars(r1), vars(r2)], "audit_revisions": new_revs, "audit_leaks": leaks,
        "audit_target_digests_expected": exp_digests, "idem_before": idem_before, "idem_after": idem_after,
        "observation_controls": controls, "marker_after": marker(native), "stmt_leftovers_after_erase": stmt_leftovers,
    }
    ok = (verify_after_erase == "diverges" and verify_after.result == "equal" and not problems and not meta_problems
          and not l1_diff and not unknown and not leaks and all(controls.values()) and data["marker_after"] is None
          and r1.complete and r2.complete and not stmt_leftovers)
    reason = (f"{len(before)} records, {len(yes)} tombstoned as the twin predicted; byte-identical otherwise; "
              f"verify diverges→equal; metadata/idem moved; controls={controls}" if ok else
              f"problems={len(problems)} meta={len(meta_problems)} l1_vs_twin={len(l1_diff)} unknown={len(unknown)} "
              f"leaks={leaks} verify={verify_after_erase}->{verify_after.result} controls={controls} stmt_leftovers={len(stmt_leftovers)}")
    return verdict("redaction_binding", ok, reason, data)


if __name__ == "__main__":
    raise SystemExit(main())
