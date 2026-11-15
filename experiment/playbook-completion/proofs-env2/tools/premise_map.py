#!/usr/bin/env python3
"""The link from the proof crates' environment premises to the contract's Verus specification (proof debt D-7).

    python experiment/playbook-completion/proofs-env2/tools/premise_map.py --results <RESULTS.json> --out <premise_map.json>
    python .../premise_map.py --self-test

Every proof-premise condition of reflection/closure.json (CLOSURE.md's 72 rows) and the PROOFS.md premises below that
the closure does not list get exactly one verdict:
  proved           a theorem of src/premises.rs states the premise and verifies (the lemmas named); the controls named
                   weaken the clause it needs and make it fail at its located line;
  proved-in-part   the parts named are theorems; the residual is stated (with its verdict);
  shown-false      a theorem proves the premise's negation from the contract (a witness);
  permitted-not-implied  a theorem proves the contract permits the premise's opposite (so it is a modelling restriction
                   or a sharpening the contract does not give);
  product-discipline     holds only under a discipline of the product (who takes which lock, who writes what); the
                   contract's part is proved under the discipline; a violation at the pin is the pin's, not a gap;
  outside-contract no clause of the contract (or of its Verus subset) speaks to it;
  progress         scheduling, fairness or operator behaviour: the contract has no liveness clause.
The checker fails if a closure condition is unmapped, a verdict is unknown, or a named lemma is not a verified function
of the baseline in --results.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPLETION = HERE.parent.parent
VERDICTS = {"proved", "proved-in-part", "shown-false", "permitted-not-implied", "product-discipline",
            "outside-contract", "progress"}

HL = ["premises::premise_proofs_p_c01"]
HL_CTL = ["ctl_unlock_immediate", "ctl_stop_commits", "ctl_stop_top_level_only", "ctl_kill_not_logged"]
PF3 = ("progress", ["premises::premise_proofs_pf_3", "premises::premise_proofs_pf_3_commit"], ["ctl_lock_wait_never_granted"],
       "that every erasure ENDS (and that a stopped holder is stopped) is scheduling: not implied. What the contract "
       "implies is proved: its commit or rollback releases the holds it deferred (premise_proofs_pf_3_commit) and a "
       "waiter on a stopped holder's lock is granted it (premise_proofs_pf_3)")
PROG = ("progress", [], [], "scheduling / operator / fairness: the contract has no liveness clause")
D92 = ("proved-in-part", ["premises::premise_d9_p_d9_2_wait", "premises::premise_d9_p_d9_2_insert_fails",
                          "premises::premise_d9_p_d9_2_freedom"],
       ["ctl_dml_ignores_row_locks", "ctl_row_lock_statement_only", "ctl_insert_dup_waits", "ctl_freedom_wait_only"],
       "proved: a commit's UPDATE / DELETE of a row an open bypass transaction wrote waits (premise_d9_p_d9_2_wait). "
       "Not as worded for an INSERT of a key the bypass inserted: the contract implies an immediate -119, not a wait "
       "(premise_d9_p_d9_2_insert_fails). Permitted-not-implied: a bypass INSERT over the open erasure's uncommitted "
       "DELETE may wait or proceed (premise_d9_p_d9_2_freedom); the crates' wait is a sharpening (the observed branch)")
D91 = ("product-discipline", ["premises::premise_d9_p_d9_1", "premises::premise_d9_p_d9_1_may_roll_back",
                              "premises::premise_d9_g_l_reader_under_lock", "premises::premise_head_lock_init"], HL_CTL,
       "proved under the discipline `disc` (every write to the ledger's globals by the exclusive head-lock holder inside "
       "its transaction, no immediate unlock of the head lock, no $INCREMENT on them): inv_h is inductive over every "
       "operation of every process and holds initially; the holder's step is atomic (all or none at its end, none after "
       "a stop); readers under the lock see committed values; erasures and bypass writes may roll back "
       "(premise_d9_p_d9_1_may_roll_back). A commit nested in a caller's transaction (Ledger.cls:390-396) stopped "
       "with both levels open leaves nothing: the clause's every-level reading is observed (env-estop-gap, "
       "proofs-env-mutants-r2). That the product's code follows `disc` is code correspondence (D-3/D-4): "
       "EraseGraph takes no head lock at the pin (F-1201) -- the pin's violation, not a contract gap")
A6 = ("proved-in-part", ["premises::premise_breadth_p_a6_kill", "premises::premise_breadth_p_a6_incr",
                         "premises::premise_core_ma_5_rollback_other", "gen::lemma_fresh_set_rollback"],
      ["ctl_kill_not_logged", "ctl_incr_rolled_back", "ctl_rollback_physical"],
      "proved: a rollback restores the before-image of a node the transaction set or killed when nobody wrote it since "
      "(lemma_fresh_set_rollback, premise_breadth_p_a6_kill); $INCREMENT is not undone (premise_breadth_p_a6_incr). "
      "Not as worded unconditionally: a node another process wrote since keeps that write (E-ROLLBACK-OTHER, "
      "premise_core_ma_5_rollback_other) -- the models' writers are serialized by the row lock (P-A2), so this does not "
      "arise there for rows; for globals written without a lock it does")
A2 = ("proved-in-part", ["premises::premise_breadth_p_a2", "premises::premise_d9_p_d9_2_insert_fails",
                         "premises::premise_d9_p_d9_2_freedom"],
      ["ctl_dml_ignores_row_locks", "ctl_row_lock_statement_only", "ctl_insert_dup_waits", "ctl_freedom_wait_only"],
      "proved for UPDATE / DELETE of an existing edge row: the second writer waits (premise_breadth_p_a2). An INSERT of "
      "a visible key fails at once (-119); an INSERT over another's uncommitted DELETE may proceed under a new row id "
      "(the Freedom) -- then the two writers hold different rows, so 'one edge row' still has one open writer")
L3 = ("product-discipline", ["premises::premise_breadth_p_l3", "premises::premise_head_lock_init"], HL_CTL,
      "proved under `disc` for the lock the code takes (inv_h inductive; the step atomic). That the code takes the "
      "locks the model assumes is D-3/D-4 (P-L4: Disable takes no head lock -- violated at the pin)")
L5 = ("proved", ["premises::premise_breadth_p_l5"], ["ctl_dml_ignores_row_locks", "ctl_row_lock_statement_only"], "")
GUID = ("outside-contract", [], [], "CreateGUID freshness: no contract clause (outside-premise family P2-RANDOM)")
MAP = {
    "proof-premise:TRUST:changed:P-0001 steps are transactions (rollback on stop)":
        ("proved", ["premises::premise_trust_p_0001"], ["ctl_stop_commits", "ctl_stop_top_level_only"],
         "the 'every level' reading now rests on an observation: round env-estop-gap (3 stops at $TLEVEL 2 without a "
         "commit) kills the Verus mutant stop-rolls-back-top-level-only (proofs-env-mutants-r2); before it, no recorded "
         "case discriminated it (stop-nested-levels commits its inner level before the stop)"),
    "proof-premise:TRUST:changed:P-0003 unlock inside a transaction is deferred":
        ("proved", ["premises::premise_trust_p_0003"], ["ctl_unlock_immediate"], ""),
    "proof-premise:TRUST:changed:P-1201 a SQL delete waits for a row another transaction holds":
        ("proved", ["premises::premise_trust_p_1201", "premises::premise_d9_p_d9_2_wait"],
         ["ctl_dml_ignores_row_locks", "ctl_row_lock_statement_only"],
         "for a row another open transaction inserted (premise_trust_p_1201) or updated (premise_d9_p_d9_2_wait); the "
         "INSERT over an uncommitted DELETE stays the contract's Freedom (premise_d9_p_d9_2_freedom)"),
    "proof-premise:TRUST:changed:Txn.cls:8 / _write_txn.py:15: SQL COMMIT and ROLLBACK end every level":
        ("shown-false", ["premises::premise_trust_txn_cls_8_false"], ["ctl_sql_commit_ends_all"],
         "SQL COMMIT at a nested level leaves a transaction open on this engine"),
    "proof-premise:TRUST:new:Durability of an acknowledged commit: a revision the ledger reports as committed survives an instance crash, which needs IRIS SynchCommit=1 or a journal flush before the acknowledgement":
        ("outside-contract", [], [], "journal restore and crash recovery are outside the contract's subset"),
    "proof-premise:TRUST:new:Embedded SQL (&sql) behaves as dynamic SQL for the clauses used":
        ("proved", ["premises::premise_trust_e1", "gen::gen_e1"],
         ["ctl_emb_own_txn", "ctl_emb_ignores_autocommit", "ctl_emb_select_committed_only", "ctl_emb_ignores_row_locks"],
         "proofs-env2: contract-2's E-1 is in the Verus specification. For the clauses the pin's embedded statements "
         "use, the embedded DML has the dynamic statement's effect and answer (same transaction, same driver "
         "autocommit), its SELECT INTO sees what a dynamic SELECT sees (uncommitted rows included), its DELETE waits "
         "exactly when the dynamic DELETE does, and its INSERT over another's uncommitted DELETE is the same Freedom "
         "(premise_trust_e1). The 121 E-1 cases (env2-e1-r1, env2-e1-r2) are in the subset and agree; the six E-1 "
         "mutants (incl. emb-empty-host-var-empty and maxlen-not-enforced, the -108 / -104 answers) are killed by "
         "observation (proofs-env2-mutants)"),
    "proof-premise:TRUST:new:Enabled steps are eventually scheduled; the operator re-runs after a stop; the ledger is (re-)enabled; every erasure releases its lock":
        ("progress", ["premises::premise_proofs_pf_3_commit"], [],
         "scheduling and operator: not implied; 'releases its lock' at its end is proved (premise_proofs_pf_3_commit)"),
    "proof-premise:TRUST:new:M07-L4 progress: the queue worker is weakly fair; a stopped run is resumed 3 - cursor more times": PROG,
    "proof-premise:TRUST:new:Writers go quiet, the operator resumes, nothing is stopped forever, erasure may be repeated": PROG,
    "proof-premise:TRUST:trusted:IRIS environment contract":
        ("proved-in-part", ["exec::e_run", "exec::e_step", "ext_exec::e_ext_step"], [],
         "the Verus subset is linked mechanically: the exec model is verified against the specification and agrees with "
         "the executable contract on every recorded in-subset case, every observation inside (differential). "
         "proofs-env2 adds X-TLEVEL-SQL, X-VEC's SQL functions, X-ZSTRIP, X-ORDER, X-NULL, X-STMT (INSERT ... SELECT), "
         "contract-2's E-1, maxlen, X2-BATCH and X2-IOU (2,430 of 2,943 recorded cases in the subset). Still outside, "
         "the executable contract trusted as before (exact obligations: PROOFS.md section 6): X-DDL, X-STAR, X-FX, "
         "X-NOINDEX, X-VEC's $VECTOR set/get, X2-JSON, X2-LIST, X2-TOP, X2-QUERY/MERGE/ZKILL"),
    "proof-premise:models-core:MA-1": PROG,
    "proof-premise:models-core:MA-2": PROG,
    "proof-premise:models-core:MA-3": PROG,
    "proof-premise:models-core:MA-4": PROG,
    "proof-premise:models-core:MA-5":
        ("proved", ["premises::premise_d1f_p_u2_false", "premises::premise_core_ma_5_rollback_other",
                    "premises::premise_trust_p_1201", "premises::premise_trust_p_0001", "premises::premise_proofs_pf_3"],
         ["ctl_no_dirty_reads", "ctl_rollback_physical", "ctl_dml_ignores_row_locks", "ctl_row_lock_statement_only",
          "ctl_stop_commits", "ctl_stop_top_level_only", "ctl_lock_wait_never_granted"],
         "dirty reads, value rollback, row-lock waits, stop rollback, lock release: each a theorem"),
    "proof-premise:models-core:MA-6": ("proved", ["premises::premise_core_ma_6"], ["ctl_select_committed_only"], ""),
    "proof-premise:models-core:P-1306": PROG,
    "proof-premise:proofs-breadth:P-A2": A2,
    "proof-premise:proofs-breadth:P-A6": A6,
    "proof-premise:proofs-breadth:P-L1": GUID,
    "proof-premise:proofs-breadth:P-L3": L3,
    "proof-premise:proofs-breadth:P-L5": L5,
    "proof-premise:proofs-d1b:P-S7": GUID,
    "proof-premise:proofs-d1c:P-B2": ("proved", ["premises::premise_d1c_p_b2"], [],
                                      "no control: the specification has no alternative reading of an inner TCOMMIT "
                                      "(the contract's nesting mutant concerns TROLLBACK 1, see premise_contract2_s1_partial)"),
    "proof-premise:proofs-d1c:P-L3":
        ("proved-in-part", ["premises::premise_d1c_p_l3_counter", "premises::premise_proofs_p_c01"],
         ["ctl_incr_rolled_back"] + HL_CTL,
         "a counter only $INCREMENT writes never goes back (premise_d1c_p_l3_counter); stmtNext is a SET inside the "
         "head-locked commit (LedgerApply.cls:162-163): committed values change only at the holder's commit "
         "(premise_proofs_p_c01, under `disc`); the SQL %ID counter is outside the contract"),
    "proof-premise:proofs-d1c:P-T3": ("proved", ["premises::premise_d1c_p_t3"], ["ctl_incr_rolled_back"], ""),
    "proof-premise:proofs-d1d:P-R3": ("outside-contract", [], [], "caller identity (E-CALLER) is outside the Verus subset"),
    "proof-premise:proofs-d1e:P-C5": ("shown-false", ["premises::premise_d1e_p_c5_false"], ["ctl_no_dirty_reads"], ""),
    "proof-premise:proofs-d1e:P-M2":
        ("proved-in-part", ["premises::premise_d1e_p_m2_stmt_atomic", "gen::gen_stmt_atomic"], ["ctl_statement_not_atomic"],
         "proofs-env2: the part the contract states (X-STMT) is proved -- a multi-row INSERT ... SELECT that fails on a "
         "row writes none of its rows and answers -119 (premise_d1e_p_m2_stmt_atomic; mutant statement-not-atomic "
         "killed by observation). That every SQL statement / global operation is one step stays the contract's own "
         "granularity (validated as observed), not a consequence; Cypher's single mode read is product code"),
    "proof-premise:proofs-d1f:P-F4":
        ("proved-in-part", ["premises::premise_d1f_p_f4", "headlock::theorem_inv_h"], ["ctl_lock_wait_never_granted"],
         "a killed holder's lock is freed and a waiter is granted it (premise_d1f_p_f4); mutual exclusion of the sync "
         "lock is the lock_ok part of the inductive invariant (theorem_inv_h); that the sync takes it is the product's"),
    "proof-premise:proofs-d1f:P-U2": ("shown-false", ["premises::premise_d1f_p_u2_false"], ["ctl_no_dirty_reads"], ""),
    "proof-premise:proofs-d1f:PF-1": PROG,
    "proof-premise:proofs-d1f:PF-2": PROG,
    "proof-premise:proofs-d1f:PF-3": PROG,
    "proof-premise:proofs-d1f:PF-4": PROG,
    "proof-premise:proofs-d9:P-D9-1": D91,
    "proof-premise:proofs-d9:P-D9-2": D92,
    "proof-premise:proofs-d9:PF-1": PROG,
    "proof-premise:proofs-d9:PF-2": PROG,
    "proof-premise:proofs-d9:PF-3": PF3,
    "proof-premise:proofs-d9:PF-4": PROG,
    "proof-premise:proofs-d9:PF-5": PROG,
    "proof-premise:proofs-d9:PF-6": ("progress", [], [], "shown false at the pin (F-C1307): product behaviour, not the contract"),
    "proof-premise:proofs-d9b:P-D9b-2": ("outside-contract", [], [], "sha256 collision freedom: outside (P2-HASH)"),
    "proof-premise:proofs-d9b:PF-1": PROG,
    "proof-premise:proofs-d9b:PF-2": PROG,
    "proof-premise:proofs-d9b:PF-3": PF3,
    "proof-premise:proofs-d9b:PF-4": PROG,
    "proof-premise:proofs-d9b:PF-5": PROG,
    "proof-premise:proofs-d9b:PF-6": ("progress", [], [], "shown false at the pin (F-C1307): product behaviour"),
    "proof-premise:proofs-d9c:P-D9-1": D91,
    "proof-premise:proofs-d9c:P-D9-2": D92,
    "proof-premise:proofs-d9c:P-D9b-2": ("outside-contract", [], [], "sha256 collision freedom: outside (P2-HASH)"),
    "proof-premise:proofs-d9c:PF-1": PROG,
    "proof-premise:proofs-d9c:PF-2": PROG,
    "proof-premise:proofs-d9c:PF-3": PF3,
    "proof-premise:proofs-d9c:PF-4": PROG,
    "proof-premise:proofs-d9c:PF-5": PROG,
    "proof-premise:proofs-d9c:PF-6": ("progress", [], [], "shown false at the pin (F-C1307): product behaviour"),
    "proof-premise:proofs-mech:PM-1": PROG,
    "proof-premise:proofs-mech:PM-2": PROG,
    "proof-premise:proofs-pa3:P-A2": A2,
    "proof-premise:proofs-pa3:P-A6": A6,
    "proof-premise:proofs-pa3:P-E2":
        ("proved-in-part", ["premises::premise_breadth_p_a2", "premises::premise_trust_p_1201",
                            "premises::premise_d9_p_d9_2_freedom"],
         ["ctl_dml_ignores_row_locks", "ctl_row_lock_statement_only", "ctl_freedom_wait_only"],
         "per row: a writer of an existing row and the DELETE serialize through its row lock; an INSERT after the "
         "DELETE of its key may wait or proceed (Freedom). A multi-row DELETE's scan order is outside the contract "
         "(DELETE by key only), so 'the DELETE is one step' is not implied"),
    "proof-premise:proofs-pa3:P-L1": GUID,
    "proof-premise:proofs-pa3:P-L3": L3,
    "proof-premise:proofs-pa3:P-L5": L5,
    "proof-premise:proofs:P-C01":
        ("product-discipline", HL + ["premises::premise_head_lock_init", "effects::lemma_step_eff"], HL_CTL,
         "proved under `disc`: each head-locked step is atomic, a stop leaves nothing (with nested levels open too: "
         "observed by env-estop-gap, proofs-env-mutants-r2), a stopped process loses only its "
         "own state (lemma_step_eff: every other process is unchanged). 'The erasure is one open transaction' holds for "
         "an erasure that takes the head lock (the reviewed HD-1201); at the pin EraseGraph does not (F-1201)"),
    "proof-premise:proofs-env:ENV-4": ("progress", [], [], "proofs-env's (and proofs-env2's) own premise: the contract "
                                       "has no liveness clause, so the progress premises are not implied (D-8)"),
    "proof-premise:proofs-sys:PS-2": ("progress", [], [], "operator action (ReErase, Resume): the contract has no "
                                      "liveness clause"),
    "proof-premise:proofs-sys:PS-3": ("progress", [], [], "fairness of the scheduler (AX-14 as AG EF): not implied by "
                                      "any clause"),
    "proof-premise:proofs:PF-1": PROG,
    "proof-premise:proofs:PF-2": PROG,
    "proof-premise:proofs:PF-3": PF3,
    "proof-premise:proofs:PF-4": PROG,
}
# PROOFS.md premises the closure does not list (linked here as well)
EXTRA = {
    "proofs:P-C04 (an erasure is not rolled back between its two steps)":
        ("permitted-not-implied", ["premises::premise_proofs_p_c04_not_implied"], [],
         "a stop of the erasure's process is permitted at any moment and ends its transaction: a modelling restriction "
         "(dropped by proofs-d9)"),
    "proofs-d1b:P-S1 (a ledger commit is one step)": ("product-discipline", ["premises::premise_d1b_p_s1"], HL_CTL,
                                                       "as P-C01, under `disc`"),
    "proofs-breadth:P-A4 (a rebuild overlaps no writer; violated at the pin)":
        ("product-discipline", ["premises::premise_breadth_p_a4_shared"], ["ctl_shared_conflicts_shared"],
         "the contract makes shared holds compatible (proved), so BeginRebuild's ^IVG.AdjW#\"S\" excludes no shared "
         "writer: P-A4 needs an exclusive lock the pin does not take (F-C0402) -- the pin's violation"),
    "proofs-pa3:R04-5 (reviewed guard: exclusive ^IVG.AdjW excludes the writers' ^IVG.AdjW(g))":
        ("proved", ["premises::premise_pa3_r04_5_names"], ["ctl_flat_lock_names"], "lock-name hierarchy"),
    "proofs-d9:G-L (the liveness check runs under the eraser's lock)":
        ("product-discipline", ["premises::premise_d9_g_l_reader_under_lock"], [],
         "a reader holding the lock sees committed protected values (from inv_h); that Start/Final take it is the "
         "reviewed design (not at the pin, F-C1201)"),
    "contract-2:S-1 / _write_txn (Txn_Undo, TROLLBACK 1)":
        ("proved", ["premises::premise_contract2_s1_partial"], ["ctl_rollback_one_undoes_all"], ""),
    "proofs-d9:EraseAbort (the erasure's value-based rollback; E-ROLLBACK-OTHER)":
        ("proved", ["premises::premise_d9_erasure_rollback"], ["ctl_rollback_physical", "ctl_freedom_wait_only"], ""),
}


def build(results: dict) -> tuple[dict, list[str]]:
    problems = []
    closure = json.loads((COMPLETION / "reflection" / "closure.json").read_text())
    pp = [c for c in closure["conditions"] if c["group"] == "proof-premise"]
    fns = set(results["baseline"]["functions"]) if results else set()
    ctls = set(results.get("controls", {})) if results else set()
    rows = []
    for c in pp:
        if c["id"] not in MAP:
            problems.append(f"unmapped closure condition {c['id']}")
            continue
        rows.append((c["id"], c["condition"], c["status"], MAP[c["id"]], "closure.json"))
    for k in MAP:
        if k not in {c["id"] for c in pp}:
            problems.append(f"map entry not in closure.json: {k}")
    for k, v in EXTRA.items():
        rows.append((k, k, None, v, "PROOFS.md"))
    out = []
    for cid, cond, status, (verdict, lemmas, controls, note), src in rows:
        if verdict not in VERDICTS:
            problems.append(f"{cid}: unknown verdict {verdict}")
        if results:
            for lm in lemmas:
                if lm not in fns:
                    problems.append(f"{cid}: lemma {lm} is not a verified function of the baseline")
            for ct in controls:
                if ct not in ctls:
                    problems.append(f"{cid}: control {ct} not in the results")
        out.append({"id": cid, "condition": cond, "closure_status": status, "source": src, "verdict": verdict,
                    "lemmas": lemmas, "controls": controls, "note": note})
    counts = {}
    for r in out:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    closure_counts = {}
    for r in out:
        if r["source"] == "closure.json":
            closure_counts[r["verdict"]] = closure_counts.get(r["verdict"], 0) + 1
    return {"generated_by": "proofs-env2/tools/premise_map.py", "closure_conditions": len(pp),
            "closure_verdicts": closure_counts, "all_verdicts": counts, "rows": out}, problems


def self_test() -> int:
    # seeded faults: an unmapped id, an unknown verdict, a missing lemma must each be reported
    bad = 0
    saved = dict(MAP)
    k0 = next(iter(MAP))
    del MAP[k0]
    _, p = build({})
    bad += not any("unmapped" in x for x in p)
    MAP[k0] = ("nonsense", [], [], "")
    _, p = build({})
    bad += not any("unknown verdict" in x for x in p)
    MAP[k0] = ("proved", ["premises::no_such_lemma"], [], "")
    _, p = build({"baseline": {"functions": []}, "controls": {}})
    bad += not any("no_such_lemma" in x for x in p)
    MAP.clear()
    MAP.update(saved)
    print("self-test", "pass" if not bad else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results")
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    res = json.loads(Path(a.results).read_text()) if a.results else {}
    m, problems = build(res)
    m["problems"] = problems
    if a.out:
        Path(a.out).write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    print(f"premise map: {m['closure_conditions']} closure conditions, verdicts {m['closure_verdicts']}; all rows "
          f"{len(m['rows'])} {m['all_verdicts']}; problems {len(problems)}")
    for p in problems:
        print("PROBLEM:", p)
    sys.exit(1 if problems else 0)
