#!/usr/bin/env python3
"""Iteration 66 native regrade (review-1 R1-N1..N8): column changes and new rows for the query.native*, query.shadow
and query.compiled.deploy-discards census rows, plus the changed blocks' hashes and counts. Run from the repository
root after the census worker's splits; idempotent (a row already at its new value is left alone; a NEWROW already
present is not added again). Prints the ledger lines (id, column, old, new, reason) it applied.

    python3 apply_native.py [--ledger OUT.tsv]
"""
import csv
import sys
from pathlib import Path

REPO = Path.cwd()
CEN = REPO / ".g5/Verus_verification/census"
sys.path.insert(0, str(REPO / ".g5/Verus_verification/tools"))
import census  # noqa: E402

NA = ".g5/Verus_verification/models/native_admission/native_admission.rs::"
RR = ".g5/Verus_verification/models/route_recheck/route_recheck.rs::"
PROVE = ".g5/Verus_verification/results/native_admission/LATEST-prove/receipt.json"
BIND = "binding AGREES .g5/Verus_verification/results/native_admission/LATEST-binding/receipt.json"
CTL = ".g5/Verus_verification/results/native_admission/LATEST-control-{}/receipt.json"
SRC = "changed: iteration 66 review-1 repair ({}); native_admission re-proved, binding replayed on the run-own fixture"


def L(*names):
    return "; ".join(NA + n for n in names)


def R(*controls):
    return "; ".join([PROVE] + [CTL.format(c) for c in controls])


CHANGES = [
    # ---- privileges: lead restated as the FR-011 requirement, Today bullet added
    ("query.native.privileges#o01", "locator", "lead 'is to get the SQL path, never the native one'", "R1 privileges lead (census owner-contradicted note)"),
    ("query.native.privileges#o01", "statement", "Requirement (spec 253 FR-011): a caller lacking SELECT on any of the four graph tables is answered by the SQL path, never the native one", "lead restated as the requirement"),
    ("query.native.privileges#o01", "grade_source", SRC.format("privileges lead restated; refutation unchanged: a running engine keeps its cached answer"), ""),
    ("query.native.privileges#o01", "iteration", "66", ""),
    ("query.native.privileges#o02", "locator", "lead 'so that SQL table privileges keep deciding what a caller can read'", "lead reworded"),
    ("query.native.privileges#o02", "iteration", "66", ""),
    ("query.native.privileges#o03", "iteration", "66", "block rehashed; unchanged"),
    # ---- reads-only: bullet 1 repaired, bullet 2 added
    ("query.native.reads-only#o05", "locator", "bullet 1 'A read statement chained after a write in the same query may still run natively'", "R1-N4 owner repaired"),
    ("query.native.reads-only#o05", "statement", "A read statement chained after a write in the same query may run natively, inside the write's transaction, and then sees the write's own uncommitted changes", "R1-N4"),
    ("query.native.reads-only#o05", "model_locators", L("theorem_read_part_of_chained_write_runs_natively", "chain_part"), "R1-N4"),
    ("query.native.reads-only#o05", "premises", "routing: as built (execute_cypher's chained loop); visibility: the live observation in the same transaction and the reviewed-design crate (another connection's open transaction)", ""),
    ("query.native.reads-only#o05", "gap", "the write's uncommitted change being visible to the native read is a live observation (binding chained_write_then_read), not a model transition", "owner-contradicted gap resolved by the owner repair"),
    ("query.native.reads-only#o05", "design_receipts", R("chained-part-keeps-chain"), ""),
    ("query.native.reads-only#o05", "grade_source", SRC.format("R1-N4: bullet repaired; partial: visibility not modelled"), ""),
    ("query.native.reads-only#o05", "iteration", "66", ""),
    *[(f"query.native.reads-only#o0{i}", "iteration", "66", "block rehashed; unchanged") for i in (1, 2, 3, 4)],
    # ---- equal-answers: FR-002/FR-013
    ("query.native.equal-answers#o01", "iteration", "66", "block rehashed; unchanged"),
    ("query.native.equal-answers#o02", "iteration", "66", "block rehashed; unchanged"),
    ("query.native.equal-answers#o03", "locator", "bullet 2 'Where the query's ORDER BY puts every row it returns in one order'", "R1-N1 owner amended"),
    ("query.native.equal-answers#o03", "statement", "Where the ORDER BY puts every returned row in one order (no ties on the sort values), native returns the same rows in the same order as the SQL path", "R1-N1"),
    ("query.native.equal-answers#o03", "iteration", "66", ""),
    ("query.native.equal-answers#o04", "locator", "bullet 4 'Without ORDER BY, the same rows in any order'", "R1-N1: the partial-order case moved to #o06"),
    ("query.native.equal-answers#o04", "statement", "Without ORDER BY, native returns the same multiset of rows as the SQL path", "R1-N1"),
    ("query.native.equal-answers#o04", "iteration", "66", ""),
    ("query.native.equal-answers#o05", "locator", "bullet 5 'Where LIMIT or SKIP keeps rows the query does not fully order'", "R1-N1"),
    ("query.native.equal-answers#o05", "statement", "With LIMIT/SKIP over a not fully ordered result, native returns the same number of rows, each a row of the SQL answer without the limit, with their sort values in the SQL answer's order", "R1-N1: FR-013 plus FR-002's order"),
    ("query.native.equal-answers#o05", "model_locators", L("fr013_equal", "compare", "plan", "theorem_partial_order_compared_in_order", "theorem_limit_pass_means_rows_of_full_answer", "theorem_limit_other_rows_pass", "theorem_limit_outside_row_raises", "theorem_limit_count_names_no_row", "theorem_skip_never_compared", "witness_comparator_accepts_wrong_topk"), "R1-N1"),
    ("query.native.equal-answers#o05", "premises", "the owner rule as fr013_equal over the returned rows and the ORDER BY columns; the comparison as compare decides it with the planner's flags", ""),
    ("query.native.equal-answers#o05", "gap", "native rows are a model input (w.native_rows), so the native answer itself is not modelled; the rule is formalised (fr013_equal) and the comparator is proved to enforce it except for an aggregate ordered off its grouping keys (witness_comparator_accepts_wrong_topk, bug-cyp-162) and to compare ties in order (F-0907); SKIP is never planned", "R1-N1"),
    ("query.native.equal-answers#o05", "design_receipts", R("complete-order-flag", "limit-without-count", "limit-skips-spent-check", "owner-drops-order-keys"), ""),
    ("query.native.equal-answers#o05", "grade_source", SRC.format("R1-N1"), ""),
    ("query.native.equal-answers#o05", "iteration", "66", ""),
    # ---- fallback: R1-N3 narrowed premise (the Python steps are the new #o03)
    ("query.native.fallback#o01", "statement", "A failure of the native executor's run (raise, missing class, plan of another version, refused SQL anchor) yields the SQL path's answer instead of an error", "R1-N3 split: the Python steps are #o03"),
    ("query.native.fallback#o01", "premises", "failures inside Exec.Run only (the one call inside _try_native's try, query.py:2144-2152): a missing class, a plan of another version, a SQL-found anchor refused by privileges, any other raise; the SQL path's own answer (rows or error) is what the reader gets; the Python steps around it are #o03", "R1-N3"),
    ("query.native.fallback#o01", "grade_source", SRC.format("R1-N3: premise narrowed to Exec.Run failures"), ""),
    ("query.native.fallback#o01", "iteration", "66", ""),
    # ---- gates#o04: setup resets only after a deploy (R1-N7)
    ("query.native.gates#o04", "premises", "the answer is cached per engine until a setup whose deploy left the classes in place (objectscript_deployed); a transient probe error keeps only that call on SQL", "R1-N7"),
    ("query.native.gates#o04", "model_locators", "+" + NA + "theorem_setup_resets_only_after_deploy", "R1-N7"),
    ("query.native.gates#o04", "iteration", "66", ""),
    # ---- shadow
    ("query.shadow#o02", "model_locators", "+" + L("witness_comparator_accepts_wrong_topk", "witness_comparator_accepts_reversed_count_order"), "R1-N1: a difference under FR-013 is returned as the answer"),
    ("query.shadow#o02", "grade_source", SRC.format("R1-N1: a second refutation, a wrong top-1 or reversed order is returned (binding blind_spot_wrong_top1, blind_spot_reversed_order)"), ""),
    ("query.shadow#o02", "iteration", "66", ""),
    ("query.shadow#o03", "premises", "a SQL failure as an error result (live) or as a plain RuntimeError (modeled; not constructed live behind an admitted plan); reader covers the unchained path only: execute_cypher's chained loop (query.py:1904-1916) does not convert a RuntimeError", "R1-N5"),
    ("query.shadow#o03", "iteration", "66", ""),
    # ---- deploy-discards (R1-N6)
    ("query.compiled.deploy-discards#o01", "check_scope", "narrowed", "R1-N6"),
    ("query.compiled.deploy-discards#o01", "premises", "a successful deploy whose DropAll call succeeds: a DropAll failure is logged at debug level and swallowed (schema.py:2936-2941)", "R1-N6"),
    ("query.compiled.deploy-discards#o01", "grade_source", "it66 regrade (review-1 R1-N6): check_scope full -> narrowed", ""),
    ("query.compiled.deploy-discards#o01", "iteration", "66", ""),
    # ---- route
    ("query.native.route#o15", "locator", "working-assumption 1 'on whether the second HTTP app's Cypher endpoints should answer through the engine'", "R1-N8: question attached"),
    ("query.native.route#o15", "iteration", "66", ""),
    *[(f"query.native.route#o{i:02d}", "iteration", "66", "block rehashed; unchanged") for i in range(1, 15)],
]

BASE = {"parent_entailment": "", "iteration": "66"}
NEW = [
    dict(BASE, id="query.native.privileges#o04", block="query.native.privileges",
         locator="bullet 1 'Today an engine checks those privileges once, at its first native read'",
         statement="Current behaviour: an engine checks the four SELECT privileges once, at its first native read, and keeps the answer (setup does not reset it); a new engine keeps a caller lacking one on SQL, a REVOKE after the check does not reach the engine's native reads that find their first nodes through the adjacency index, and its reads that look their first nodes up through SQL fail and fall back",
         cases="fresh engine without SELECT vs running engine after REVOKE: label scan vs property-lookup anchor; after setup; new engine",
         observation="which path answers; the fallback warning",
         model_locators=L("priv_probe", "theorem_missing_select_keeps_sql", "theorem_revoke_does_not_reach_running_engine", "theorem_revoke_reaches_sql_anchor_only"),
         premises="one engine; a REVOKE on one graph table; Exec's anchor kinds as transcribed",
         grade="full", design_check="proved", check_scope="narrowed",
         design_receipts=R("recheck-privileges", "setup-resets-privileges", "anchor-ignores-privileges"), as_built=BIND,
         gap="", grade_source="new: iteration 66 owner text (review-1, privileges lead)"),
    dict(BASE, id="query.native.reads-only#o06", block="query.native.reads-only",
         locator="bullet 2 'The read steps a write runs for itself ... always take the SQL path'",
         statement="The read steps a write runs for itself (the MATCH before a per-row MERGE, also after a WITH; the count before a CREATE) always take the SQL path",
         cases="per-row MERGE (prefix with __rm alias; after a WITH, with or without one) and count_create's count vs a plain read",
         observation="which path answers the read step (_native_answers)",
         model_locators=L("count_step", "merge_prefix", "merge_prefix_after_with", "theorem_write_read_steps"),
         premises="the steps as count_create/merge_rows build them (transcribed shapes); requires-reviewed: whole.mutation is the statement's 'a write'",
         grade="full", design_check="proved", check_scope="narrowed",
         design_receipts=R("show-internal-alias", "merge-after-with-planned"), as_built=BIND,
         gap="", grade_source="new: iteration 66 owner text (review-1 R1-N4)"),
    dict(BASE, id="query.native.equal-answers#o06", block="query.native.equal-answers",
         locator="bullet 3 'Where rows tie on the sort values, the same rows with their sort values in the same order'",
         statement="Where rows tie on the sort values, native returns the same rows with their sort values in the SQL answer's order; only tied rows may come in another order",
         cases="tied rows permuted (allowed) vs untied rows reordered or a wrong top group (refused)",
         observation="the rows and their order-key sequence",
         model_locators=L("fr013_equal", "order_agrees", "theorem_partial_order_compared_in_order", "witness_comparator_accepts_reversed_count_order"),
         premises="the rule over the returned rows and the ORDER BY columns",
         grade="partial", design_check="proved", check_scope="narrowed",
         design_receipts=R("owner-drops-order-keys", "complete-order-flag"), as_built=BIND,
         gap="native rows are a model input, so the native answer's order is not modelled; the rule is formalised and the comparator is shown to over-enforce it on ties (F-0907) and to under-enforce it for an aggregate ordered off its grouping keys (bug-cyp-162)",
         grade_source="new: iteration 66 owner text (review-1 R1-N1)"),
    dict(BASE, id="query.native.equal-answers#o07", block="query.native.equal-answers",
         locator="bullet 6 'Today the shadow check enforces less'",
         statement="Current behaviour: the shadow comparator compares an aggregate whose ORDER BY leaves out a grouping key as if it had no ORDER BY, accepting a wrong top row (LIMIT) or a reversed order (no LIMIT); off that shape a passing comparison implies the rule",
         cases="ORDER BY count (blind) vs ORDER BY the grouping key (ordered, raises) vs non-aggregate ORDER BY",
         observation="NativeMismatch raised or the native answer returned in shadow mode",
         model_locators=L("witness_comparator_accepts_wrong_topk", "witness_comparator_accepts_reversed_count_order", "theorem_blind_spot_is_partial_aggregate_order", "theorem_comparator_sound_off_partial_aggregate_order"),
         premises="the planner's ordered flag as transcribed (checked against the real plan_query); fits(sql, u): SQL's limited rows are rows of its unlimited answer",
         grade="full", design_check="proved", check_scope="narrowed",
         design_receipts=R("topk-plan-ordered", "owner-drops-order-keys", "ordered-compared-as-bag", "plan-drops-order"),
         as_built=BIND, gap="", grade_source="new: iteration 66 owner text (review-1 R1-N1, bug-cyp-162)"),
    dict(BASE, id="query.native.fallback#o03", block="query.native.fallback",
         locator="lead 'If the native executor fails for any reason, the SQL path answers the query instead'",
         statement="A failure in the native path's Python steps (planning other than a decline, the shared translation, the mapped-label check, decoding the native rows) yields the SQL path's answer instead of an error",
         cases="a raise in plan_query / _native_translation / _names_mapped_label / _finish_sql_result vs a raise in Exec.Run",
         observation="execute_cypher answer or exception",
         model_locators="", premises="", grade="absent", design_check="none", check_scope="n/a", design_receipts="",
         as_built="inspection read iris_vector_graph/_engine/query.py",
         gap="open obligation (review-1 R1-N3): these steps are outside the try, so a raise would propagate instead of falling back; no reachable trigger has been constructed; try_native lets only run fail",
         grade_source="new: iteration 66 split of #o01 (review-1 R1-N3)"),
    dict(BASE, id="query.native.route#o16", block="query.native.route",
         locator="bullet 5 'Today, while a trial runs, identical calls of a shape take native for the first three calls'",
         statement="Current behaviour: during a trial identical calls take native for the first three calls and then SQL and native in turn, so wherever the two paths answer differently the same query returns different answers from one call to the next",
         cases="bug-cyp-104's query (paths differ: two answers in turn) vs a query whose paths agree (one answer)",
         observation="the rows each identical call returns, and the path (_native_answers)",
         model_locators=L("call_routed", "next_rpath", "record_trial", "theorem_route_trial_alternates_answers", "theorem_successive_calls_differ_in_trial"),
         premises="a warm engine, an admissible read, the SQL path answers rows; the trial does not end within the calls (timing premise: native median under small_ms, no SQL timing over 4x native's slowest, fewer than `trials` timings), observed on the real route in the binding",
         grade="full", design_check="proved", check_scope="narrowed",
         design_receipts=R("trial-no-alternation"), as_built=BIND, gap="",
         grade_source="new: iteration 66 owner text (review-1 R1-N2)"),
    dict(BASE, id="query.native.route#o17", block="query.native.route",
         locator="bullet 5 'every recheck or drift trial starts this again'",
         statement="Current behaviour: every recheck or drift trial starts the alternation again",
         cases="held shape at the recheck threshold vs before it; drift trigger vs not",
         observation="the path of the calls after the threshold",
         model_locators=RR + "theorem_before_and_at_threshold; " + RR + "theorem_reset_derives_native_first",
         premises="drift disabled in route_recheck; the two route models are separate crates (composition by the shared next_path rule, not proved)",
         grade="partial", design_check="proved", check_scope="narrowed",
         design_receipts=".g5/Verus_verification/results/route_recheck/LATEST-prove/receipt.json", as_built="none",
         gap="the recheck reset to a native-first trial is proved in route_recheck and the alternation in native_admission, but the two are not composed in one model; drift is unmodelled",
         grade_source="new: iteration 66 owner text (review-1 R1-N2)"),
]
CHANGED_BLOCKS = ["query.native.privileges", "query.native.reads-only", "query.native.equal-answers",
                  "query.native.route", "query.native.fallback"]


def latest(model, label, results):
    hits = sorted(d.name for d in results.glob(f"*-{label}") if (d / "receipt.json").exists()
                  and d.name.split("-", 1)[1] == label)
    return hits[-1] if hits else None


def resolve(text):
    res = REPO / ".g5/Verus_verification/results"
    out = []
    for part in text.split("; "):
        if "/LATEST-" in part:
            pre, rest = part.split("/LATEST-", 1)
            model = pre.rsplit("/", 1)[1]
            label = rest.split("/receipt.json")[0]
            stamp = latest(model, label, res / model)
            assert stamp, (model, label)
            part = f"{pre}/{stamp}/receipt.json" + rest.split("/receipt.json", 1)[1]
        out.append(part)
    return "; ".join(out)


def main():
    ledger = []
    cols = census.OBL_COLS
    rows = census.read_tsv(str(CEN / "obligations.tsv"), cols)
    byid = {r["id"]: r for r in rows}
    for oid, col, new, why in CHANGES:
        r = byid[oid]
        if new.startswith("+"):
            add = [x for x in resolve(new[1:]).split("; ") if x not in r[col].split("; ")]
            new = "; ".join([x for x in r[col].split("; ") if x] + add) if add else r[col]
        else:
            new = resolve(new)
        if r[col] != new:
            ledger.append((oid, col, r[col], new, why))
            r[col] = new
    for n in NEW:
        if n["id"] in byid:
            continue
        n = {c: resolve(n.get(c, "")) for c in cols}
        idx = max(i for i, r in enumerate(rows) if r["block"] == n["block"]) + 1
        rows.insert(idx, n)
        byid[n["id"]] = n
        ledger.append((n["id"], "NEWROW", "", n["statement"], n["grade_source"]))
    census.write_tsv(str(CEN / "obligations.tsv"), cols, rows)
    onto = census.parse_ontology()
    bcols = census.BLOCKS_COLS
    brows = census.read_tsv(str(CEN / "blocks.tsv"), bcols)
    for b in brows:
        if b["block"] in CHANGED_BLOCKS:
            n = str(sum(1 for r in rows if r["block"] == b["block"]))
            for col, new in (("sha256", onto[b["block"]]["sha256"]), ("obligations", n), ("iteration", "66")):
                if b[col] != new:
                    ledger.append((b["block"], "blocks." + col, b[col], new, "iteration 66 owner edit / split"))
                    b[col] = new
    census.write_tsv(str(CEN / "blocks.tsv"), bcols, brows)
    out = sys.argv[sys.argv.index("--ledger") + 1] if "--ledger" in sys.argv else None
    lines = ["\t".join(x.replace("\t", " ") for x in row) for row in ledger]
    if out:
        Path(out).write_text("id\tcolumn\told\tnew\treason\n" + "\n".join(lines) + "\n")
    print(f"applied {len(ledger)} changes")


if __name__ == "__main__":
    main()
