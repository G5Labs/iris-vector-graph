#!/usr/bin/env python3
"""Interrupted batches resume to the same end state as an uninterrupted run (theorem: batches compose,
rescanning is harmless; spec 256 Decision 3 "the same target can resume").

Reference: fresh world, erase tenant A's graph, redact(gA) in one call.
Interrupted: fresh identical world, erase, then
  1. redact(gA, batch_size=1, max_batches=1)  -> paused, marker set
  2. disable the ledger; redact(gA)            -> refused (LedgerDisabledError), nothing changes
  3. enable; write gA content outside the ledger (target live again)
  4. redact(gA, batch_size=2)                   -> batches run, final step refuses (target_live), marker stays
  5. verify() -> redaction_in_progress; erase gA again; redact(gA) -> complete
Expected: the final ^IVG.Ledger("rec") values (tombstones and digests) equal the reference; one redaction
revision naming the same revisions with the same totals; marker gone; verify equal.
"""
from redaction_binding import GA, build
from redaction_common import connect, engine, ensure_schema, ledger_records, marker, reset, revision_rows, verdict


def redaction_tail(conn, native):
    revs = revision_rows(conn)
    audits = [r for r in revs.values() if r["kind"] == "redaction"]
    recs = ledger_records(native)
    named = [sorted(int(f[2]) for (s, _o), f in recs.items() if s == a["seq"] and f[0] == "redact") for a in audits]
    return audits, named


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    # reference
    reset(eng, native); build(eng); eng.erase_graph(GA)
    ref_receipt = vars(eng.ledger.redact(GA))
    ref_recs = ledger_records(native)
    ref_audits, ref_named = redaction_tail(conn, native)
    # interrupted
    reset(eng, native); build(eng); eng.erase_graph(GA)
    steps = {}
    p1 = eng.ledger.redact(GA, batch_size=1, max_batches=1)
    steps["1_paused"] = {"complete": p1.complete, "tombstoned": p1.records_tombstoned, "marker": bool(marker(native))}
    eng.ledger.disable()
    snap = ledger_records(native)
    try:
        eng.ledger.redact(GA); steps["2_disabled"] = {"refused": False}
    except Exception as ex:
        steps["2_disabled"] = {"refused": True, "error": type(ex).__name__, "unchanged": ledger_records(native) == snap}
    eng.ledger.enable()
    eng.create_edge("late|1", "R", "late|2", graph=GA)
    try:
        r4 = eng.ledger.redact(GA, batch_size=2); steps["4_live_again"] = {"refused": False, "receipt": vars(r4)}
    except Exception as ex:
        steps["4_live_again"] = {"refused": True, "error": type(ex).__name__, "marker": bool(marker(native))}
    steps["5_verify_midway"] = eng.ledger.verify().result
    eng.erase_graph(GA)
    fin = eng.ledger.redact(GA)
    steps["5_final"] = vars(fin)
    recs = ledger_records(native)
    audits, named = redaction_tail(conn, native)
    diff = [str(k) for k in set(ref_recs) | set(recs) if ref_recs.get(k) != recs.get(k)]
    data = {"reference_receipt": ref_receipt, "steps": steps, "record_differences": diff,
            "reference_named": ref_named, "named": named, "verify_final": eng.ledger.verify().result,
            "marker_after": marker(native)}
    ok = (not diff and named == ref_named and fin.complete and steps["2_disabled"].get("refused")
          and steps["2_disabled"].get("unchanged") and steps["4_live_again"].get("error") == "RedactionTargetLiveError"
          and steps["5_verify_midway"] == "redaction_in_progress" and data["verify_final"] == "equal"
          and data["marker_after"] is None and fin.records_tombstoned == ref_receipt["records_tombstoned"])
    reason = (f"record diffs vs uninterrupted={len(diff)}; audit names {named} vs {ref_named}; final tombstoned "
              f"{fin.records_tombstoned} vs {ref_receipt['records_tombstoned']}; steps={ {k: (v if not isinstance(v, dict) else v.get('error', v.get('complete'))) for k, v in steps.items()} }")
    return verdict("redaction_interrupt_resume", ok, reason, data)


if __name__ == "__main__":
    raise SystemExit(main())
