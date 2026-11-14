#!/usr/bin/env python3
"""Resume of a PREFIX target with relationship and qualifier records (review R1-2).

World: tenant P (ids "tP|...") in the default graph: nodes with properties, a default-graph relationship
created with qualifiers, then qualified again by statement reference in a later revision; tenant Q alongside.
After erasing P by prefix, redact(None, prefix="tP", batch_size=1, max_batches=1) is called repeatedly until it
reports complete (each call is one batch and a fresh call: PrePass, the live statement map and the persistent
("redacting","stmt") set are what each call knows). Expected (lemma_serial_resume_keeps_attribution, spec 256
Decision 3 "the same target can resume"): the end state equals the uninterrupted run's prediction — every
record the probe attributes to P is a tombstone with sha256(canonical original), every other record is
byte-identical, unattributed_records is 0 on every receipt, and verify() is equal.
"""
from redaction_common import (canonical, connect, cs, engine, ensure_schema, knowledge, ledger_records, marker,
                              reset, sha256, stmt_rows, twin_classify, verdict)


def build(eng):
    led = eng.ledger
    led.enable()
    c = cs("P load", "tP|c1", "tP-k1", "tP-feed")
    c.create_node("tP|1", properties={"s": "pSecret1"})
    c.create_node("tP|2", properties={"s": "pSecret2"})
    c.create_relationship("tP|1", "KNOWS", "tP|2", qualifiers={"since": "pSince", "note": "pNote"})
    led.commit(c)
    c = cs("Q load", "tQ|c1", "tQ-k1", "tQ-feed")
    c.create_node("tQ|1", properties={"s": "qSecret"})
    led.commit(c)
    c = cs("P qualify", "tP|c2", None, "tP-feed")
    c.set_qualifier(("tP|1", "KNOWS", "tP|2", None), "note", "pNote2")
    c.set_property("tQ|1", "s", "qSecret2")
    led.commit(c)


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    reset(eng, native)
    build(eng)
    eng.delete_nodes_by_prefix("tP|")
    before = ledger_records(native)
    canon = {k: canonical(native, *k) for k in before}
    pre, live = knowledge(before, stmt_rows(native), "")
    cls = twin_classify(before, "", "tP", "|", pre, live)
    yes = {k for k, c in cls.items() if c == "Yes"}
    l1 = {k for k, f in before.items() if ("tP|" in str(f[2]) or "tP|" in str(f[4]) or "tP|" in str(f[5])
                                           or (f[0] in ("set_qual", "remove_qual")))}
    receipts, calls = [], 0
    while calls < 200:
        r = eng.ledger.redact(None, prefix="tP", batch_size=1, max_batches=1)
        calls += 1
        receipts.append({"complete": r.complete, "tombstoned": r.records_tombstoned, "unattributed": r.unattributed_records})
        if r.complete:
            break
    after = ledger_records(native)
    problems = []
    for k, f in before.items():
        a = after.get(k)
        if k in yes:
            exp = ["redacted", sha256(canon[k]), f[7] if len(f) > 7 else "", f[0], f[1]]
            if a is None or [str(x or "") for x in a[:5]] != [str(x or "") for x in exp]:
                problems.append({"pos": str(k), "expected_tombstone": exp, "observed": a})
        elif a != f:
            problems.append({"pos": str(k), "changed": True, "before": f, "after": a})
    ver = eng.ledger.verify().result
    data = {"calls": calls, "receipts": receipts, "twin_yes": sorted(map(str, yes)), "l1_p_records": sorted(map(str, l1)),
            "twin_vs_l1": sorted(map(str, yes ^ l1)), "unknown": sorted(str(k) for k, c in cls.items() if c == "Unknown"),
            "problems": problems, "verify": ver, "marker_after": marker(native)}
    ok = (receipts and receipts[-1]["complete"] and not problems and yes == l1 and not data["unknown"]
          and all(x["unattributed"] == 0 for x in receipts) and ver == "equal" and data["marker_after"] is None)
    reason = (f"{calls} one-batch calls; {len(yes)} P records tombstoned as predicted (L1 {len(l1)}); problems={len(problems)}; "
              f"unattributed={[x['unattributed'] for x in receipts if x['unattributed']]}; verify={ver}")
    return verdict("redaction_prefix_resume", ok, reason, data)


if __name__ == "__main__":
    raise SystemExit(main())
