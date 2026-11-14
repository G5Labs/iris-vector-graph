#!/usr/bin/env python3
"""Premise E-1 cases: the pin's compiled embedded SQL against the contract's permitted sets (same clause ids).

    python cases_e1.py out.json [--seed N] [--random K]

Named cases: one or more per contract clause the pin's embedded statements use (E-NEST, E-PARTIAL, E-VIS,
E-ROWLOCK, E-UNIQUE, E-STOP, E-AUTOCOMMIT / E-DRV, E-SQL-END, X-STMT, X-NULL, SQLCODE -104 / -108), each sharp
against an E-1 mutant (an embedded statement that differs from the dynamic one in that clause). Random family
`rand-e1`: two processes mixing the pin's embedded statements with dynamic DML on the same rows, transaction
verbs and process stops. Tables N, R, R0, G: native/driver_e1.py.
"""
from __future__ import annotations

import json
import random
import sys
from typing import Dict, List

OP = lambda name, **kw: {"op": name, **kw}  # noqa: E731
TL = OP("t_level")


def n(i) -> str:
    return f"env2e1-n{i}"


def r(i) -> str:
    return f"env2e1-r{i}"


def case(cid: str, clause: str, procs: int, steps: List, tables=()) -> Dict:
    return {"id": cid, "clause": clause, "procs": procs, "steps": [[p, o] for p, o in steps], "observe": [],
            "observe_tables": list(tables)}


REG = lambda i: OP("emb_register", k=n(i))  # noqa: E731
RET = lambda i: OP("emb_retract", k=r(i))  # noqa: E731
CNT = OP("emb_count")
ROUTE = OP("emb_route")
SEL = lambda t: OP("select", table=t)  # noqa: E731


def ins(t, k, v=""):
    return OP("insert", table=t, k=k, v=v)


def named() -> List[Dict]:
    return [
        # --- E-NEST / E-PARTIAL: the embedded INSERT is undone by the caller's rollback, level by level
        case("e1-reg-rollback", "E-NEST, E-VIS: an embedded INSERT inside TSTART is seen dirty and undone by TROLLBACK", 2,
             [(0, OP("t_start")), (0, REG(1)), (0, TL), (1, SEL("N")), (0, OP("t_rollback")), (0, TL), (1, SEL("N"))],
             tables=["N"]),
        case("e1-reg-rollback-one", "E-PARTIAL: TROLLBACK 1 undoes the embedded INSERT of the inner level only", 1,
             [(0, OP("t_start")), (0, ins("N", n(1))), (0, OP("t_start")), (0, REG(2)), (0, OP("t_rollback_one")), (0, TL),
              (0, SEL("N")), (0, OP("t_commit")), (0, TL)], tables=["N"]),
        case("e1-reg-nest-commit-inner", "E-NEST: an inner TCOMMIT keeps the embedded INSERT undoable by the outer rollback", 1,
             [(0, OP("t_start")), (0, OP("t_start")), (0, REG(1)), (0, OP("t_commit")), (0, TL), (0, OP("t_rollback")), (0, TL)],
             tables=["N"]),
        case("e1-reg-sql-rollback", "E-SQL-END: the SQL ROLLBACK statement ends one level, undoing the embedded INSERT", 1,
             [(0, OP("t_start")), (0, OP("t_start")), (0, REG(1)), (0, OP("sql_rollback")), (0, TL), (0, SEL("N")),
              (0, OP("t_commit")), (0, TL)], tables=["N"]),
        case("e1-reg-drv-rollback", "E-DRV: driver rollback() ends every level, undoing the embedded INSERT", 1,
             [(0, OP("t_start")), (0, OP("t_start")), (0, REG(1)), (0, OP("drv_rollback")), (0, TL)], tables=["N"]),
        # --- E-STOP
        case("e1-reg-stop", "E-STOP: a stopped process's embedded INSERT is rolled back", 2,
             [(0, OP("t_start")), (0, REG(1)), (1, SEL("N")), (1, OP("terminate", target=0)), (1, SEL("N"))], tables=["N"]),
        # --- E-ROWLOCK / E-UNIQUE: the embedded INSERT's row lock and unique entry, seen by dynamic SQL
        case("e1-reg-rowlock-rb", "E-ROWLOCK: a dynamic DELETE waits for the row an embedded INSERT holds; after its rollback deletes nothing", 2,
             [(0, OP("t_start")), (0, REG(1)), (1, OP("delete", table="N", k=n(1))), (0, OP("t_rollback")),
              (1, OP("await"))], tables=["N"]),
        case("e1-reg-rowlock-commit", "E-ROWLOCK: a dynamic UPDATE waits for the embedded INSERT's commit, then updates", 2,
             [(0, OP("t_start")), (0, REG(1)), (1, OP("update", table="N", k=n(1), v="")), (0, OP("t_commit")),
              (1, OP("await"))], tables=["N"]),
        case("e1-reg-unique", "E-UNIQUE: a dynamic INSERT of a key an open embedded INSERT wrote fails at once (-119)", 2,
             [(0, OP("t_start")), (0, REG(1)), (1, ins("N", n(1))), (0, OP("t_rollback")), (1, SEL("N"))], tables=["N"]),
        case("e1-reg-autocommit-no-hold", "E-ROWLOCK: an autocommit embedded INSERT holds no row lock afterwards", 2,
             [(0, REG(1)), (0, TL), (1, OP("delete", table="N", k=n(1)))], tables=["N"]),
        # --- E-VIS: the embedded SELECT INTO / cursor reads uncommitted rows
        case("e1-reg-sees-dirty", "E-VIS: the embedded SELECT INTO sees another's uncommitted row (no INSERT)", 2,
             [(1, OP("t_start")), (1, ins("N", n(1))), (0, REG(1)), (0, TL), (1, OP("t_rollback")), (0, SEL("N"))],
             tables=["N"]),
        case("e1-count-dirty", "E-VIS: the embedded cursor counts another's uncommitted row, then not after its rollback", 2,
             [(1, OP("t_start")), (1, ins("R", r(1), "t")), (0, CNT), (1, OP("t_rollback")), (0, CNT)], tables=["R"]),
        case("e1-count-dirty-delete", "E-VIS: the embedded cursor misses a row another deleted (uncommitted)", 2,
             [(1, ins("R", r(1), "t")), (1, ins("R", r(2), "t")), (1, OP("t_start")), (1, OP("delete", table="R", k=r(1))),
              (0, CNT), (1, OP("t_rollback")), (0, CNT)], tables=["R"]),
        case("e1-route-dirty", "E-VIS: the embedded SELECT TOP 1 INTO reads another's uncommitted registry row", 2,
             [(1, OP("t_start")), (1, ins("G", "kg_emb_env2e1a", "g")), (0, ROUTE), (1, OP("t_rollback")), (0, ROUTE)],
             tables=["G"]),
        # --- E-ROWLOCK for the embedded DELETE
        case("e1-retract-waits-rb", "E-ROWLOCK: the embedded DELETE waits for a row another inserted; after its rollback deletes nothing", 2,
             [(1, OP("t_start")), (1, ins("R", r(1), "t")), (0, RET(1)), (1, OP("t_rollback")), (0, OP("await")), (1, SEL("R"))],
             tables=["R"]),
        case("e1-retract-waits-commit", "E-ROWLOCK: the embedded DELETE waits for the inserter's commit, then deletes", 2,
             [(1, OP("t_start")), (1, ins("R", r(1), "t")), (0, RET(1)), (1, OP("t_commit")), (0, OP("await"))],
             tables=["R"]),
        case("e1-retract-update-waits", "E-VIS, E-NEST: an open embedded DELETE is seen dirty by a dynamic SELECT and undone by TROLLBACK", 2,
             [(1, ins("R", r(1), "t")), (0, OP("t_start")), (0, RET(1)), (1, SEL("R")), (0, OP("t_rollback")), (1, SEL("R"))],
             tables=["R"]),
        case("e1-retract-stop", "E-STOP: a stopped process's embedded DELETE is rolled back and its row lock released", 2,
             [(1, ins("R", r(1), "t")), (0, OP("t_start")), (0, RET(1)), (1, OP("terminate", target=0)), (1, SEL("R")),
              (1, OP("delete", table="R", k=r(1)))], tables=["R"]),
        # --- E-AUTOCOMMIT / E-DRV / X-STMT for embedded statements under the driver's autocommit off
        case("e1-reg-autocommit-off", "E-AUTOCOMMIT: with the driver's autocommit off, the embedded INSERT opens a level; rollback() undoes it", 2,
             [(0, OP("set_autocommit", on=False)), (0, REG(1)), (0, TL), (1, SEL("N")), (0, OP("drv_rollback")), (0, TL),
              (0, OP("set_autocommit", on=True))], tables=["N"]),
        case("e1-reg-autocommit-on-commits", "E-AUTOCOMMIT: turning autocommit on commits the level the embedded INSERT opened", 1,
             [(0, OP("set_autocommit", on=False)), (0, REG(1)), (0, TL), (0, OP("set_autocommit", on=True)), (0, TL)],
             tables=["N"]),
        case("e1-retract-autocommit-off", "E-AUTOCOMMIT: with autocommit off the embedded DELETE opens a level; rollback() restores the row", 1,
             [(0, ins("R", r(1), "t")), (0, OP("set_autocommit", on=False)), (0, RET(1)), (0, TL), (0, OP("drv_rollback")),
              (0, TL), (0, OP("set_autocommit", on=True))], tables=["R"]),
        case("e1-assert-autocommit-off-failed", "X-STMT: with autocommit off a failing embedded INSERT (-108) still opens the transaction", 1,
             [(0, OP("set_autocommit", on=False)), (0, OP("emb_assert", k=n(5), mode="empty")), (0, TL),
              (0, OP("drv_rollback")), (0, TL), (0, OP("set_autocommit", on=True))], tables=["N", "R0"]),
        # --- X-NULL for host variables and literals; SQLCODE mapping
        case("e1-null-empty-host", "X-NULL: an embedded host variable \"\" binds as NULL (NOT NULL graph_id: -108, nothing written)", 1,
             [(0, OP("emb_assert", k=n(5), mode="empty")), (0, TL)], tables=["N", "R0"]),
        case("e1-null-c0-host", "X-NULL: an embedded host variable $Char(0) binds as '' (default-graph rows written)", 1,
             [(0, OP("emb_assert", k=n(5), mode="zero")), (0, SEL("N"))], tables=["N", "R0"]),
        case("e1-null-literal", "X-NULL: an embedded literal '' is stored as the empty string (read as '' by the DB-API)", 1,
             [(0, REG(1)), (0, REG(2)), (0, REG(1))], tables=["N"]),
        case("e1-sqlcode-104", "SQLCODE -104: an over-long node id fails alike through embedded and dynamic SQL", 2,
             [(0, OP("emb_register", k="env2e1-n" + "x" * 260)), (1, ins("N", "env2e1-n" + "y" * 260)), (0, TL)],
             tables=["N"]),
        case("e1-assert-rollback", "E-NEST: the embedded INSERT ... SELECT rows of AssertTemporalRow are undone by TROLLBACK", 2,
             [(0, OP("t_start")), (0, OP("emb_assert", k=n(6), mode="zero")), (1, SEL("R0")), (0, OP("t_rollback")),
              (1, SEL("R0"))], tables=["N", "R0"]),
    ]


def named_sqlproc() -> List[Dict]:
    """Round r2 (premise S-1): the pin's compiled SQL functions Txn_Begin / Txn_End / Txn_Undo act on the calling
    connection's own process and transaction (what _write_txn.py relies on, Txn.cls:1-11)."""
    B = lambda h=False: OP("sql_txn_begin", hold=h)  # noqa: E731
    E = lambda lv: OP("sql_txn_end", level=lv)  # noqa: E731
    U = lambda lv: OP("sql_txn_undo", level=lv)  # noqa: E731
    return [
        case("s1-begin-undo", "S-1: Txn_Begin opens a level that stays open after the SELECT; Txn_Undo takes back its rows only", 2,
             [(0, ins("N", n(1))), (0, B()), (0, TL), (0, ins("N", n(2))), (0, REG(3)), (1, SEL("N")), (0, U(1)), (0, TL)],
             tables=["N"]),
        case("s1-nested-in-caller", "S-1: under a caller's TSTART, Txn_Begin answers 2 and Txn_Undo(2) keeps the caller's row", 1,
             [(0, OP("t_start")), (0, ins("N", n(1))), (0, B()), (0, ins("N", n(2))), (0, U(2)), (0, SEL("N")), (0, TL),
              (0, OP("t_commit")), (0, TL)], tables=["N"]),
        case("s1-end-commits", "S-1: Txn_End(1) commits IVG's own level: the row lock is gone", 2,
             [(0, B()), (0, ins("N", n(1))), (0, E(1)), (0, TL), (1, OP("delete", table="N", k=n(1)))], tables=["N"]),
        case("s1-end-inner-rollback-outer", "S-1: Txn_End(2) only lowers the level; the caller's TROLLBACK undoes IVG's write", 1,
             [(0, OP("t_start")), (0, B()), (0, REG(1)), (0, E(2)), (0, TL), (0, OP("t_rollback")), (0, TL)], tables=["N"]),
        case("s1-hold-autocommit-off", "S-1, E-DRV: with autocommit off Txn_Begin(1) opens the caller's level first; rollback() undoes both", 2,
             [(0, OP("set_autocommit", on=False)), (0, B(True)), (0, ins("N", n(1))), (0, E(2)), (0, TL), (1, SEL("N")),
              (0, OP("drv_rollback")), (0, TL), (0, OP("set_autocommit", on=True))], tables=["N"]),
        case("s1-hold-autocommit-off-commit", "S-1, E-DRV: after Txn_End(2) the driver's commit() ends the caller's level", 2,
             [(0, OP("set_autocommit", on=False)), (0, B(True)), (0, REG(1)), (0, E(2)), (0, OP("drv_commit")), (0, TL),
              (1, OP("delete", table="N", k=n(1))), (0, OP("set_autocommit", on=True))], tables=["N"]),
        case("s1-rowlock", "S-1, E-ROWLOCK: a row written under Txn_Begin is locked until Txn_Undo; the waiter then deletes nothing", 2,
             [(0, B()), (0, ins("N", n(1))), (1, OP("delete", table="N", k=n(1))), (0, U(1)), (1, OP("await"))],
             tables=["N"]),
        case("s1-stop", "S-1, E-STOP: a process stopped inside Txn_Begin's level loses the level's rows", 2,
             [(0, B()), (0, REG(1)), (0, ins("R", r(1), "t")), (1, OP("terminate", target=0)), (1, SEL("N")), (1, CNT)],
             tables=["N", "R"]),
        case("s1-end-below", "S-1: Txn_End and Txn_Undo of a level already ended leave $TLEVEL as it is", 1,
             [(0, B()), (0, OP("t_commit")), (0, E(1)), (0, U(1)), (0, TL)], tables=["N"]),
    ]


def rand_s1(rng: random.Random, i: int, seed: int) -> Dict:
    """One process: the write path's verbs (Txn_Begin / End / Undo with the level they answered), the caller's own
    transaction verbs and the driver's, embedded and dynamic writes; a second process observes."""
    steps, levels = [], []
    ac_off = rng.random() < 0.3
    if ac_off:
        steps.append((0, OP("set_autocommit", on=False)))
    for _ in range(rng.randint(5, 10)):
        x = rng.random()
        j = rng.randint(1, 3)
        if x < 0.2:
            steps.append((0, OP("sql_txn_begin", hold=ac_off)))
        elif x < 0.32:
            steps.append((0, OP("sql_txn_end", level=rng.randint(1, 3))))
        elif x < 0.44:
            steps.append((0, OP("sql_txn_undo", level=rng.randint(1, 3))))
        elif x < 0.54:
            steps.append((0, OP(rng.choice(["t_start", "t_commit", "t_rollback_one"]))))
        elif x < 0.70:
            steps.append((0, REG(j)))
        elif x < 0.85:
            steps.append((0, ins("N", n(j))))
        else:
            steps.append((1, SEL("N")))
        steps.append((0, TL))
    steps.append((0, OP("drv_commit") if rng.random() < 0.5 else OP("drv_rollback")))
    steps.append((0, TL))
    if ac_off:
        steps.append((0, OP("set_autocommit", on=True)))
    return case(f"rand-s1-{seed}-{i}", "the write path's SQL functions (random)", 2, steps, tables=["N"])


def rand_e1(rng: random.Random, i: int, seed: int) -> Dict:
    """Two processes: the pin's embedded register / retract / count next to dynamic DML on the same rows. As in
    rand-row, a statement that may block is followed by the other process ending its transaction and an await."""
    steps = []
    open_ = {0: False, 1: False}
    pre = rng.random() < 0.5
    if pre:
        steps.append((1, ins("R", r(1), "t")))
    for _ in range(rng.randint(5, 9)):
        p = rng.randint(0, 1)
        x = rng.random()
        j = rng.randint(1, 2)
        if x < 0.55:
            op = rng.choice([REG(j), RET(j), ins("N", n(j)), OP("delete", table="N", k=n(j)), ins("R", r(j), "t"),
                             OP("delete", table="R", k=r(j)), CNT])
            steps.append((p, op))
            if op["op"] != "emb_count" and open_[1 - p]:
                steps.append((1 - p, OP(rng.choice(["t_commit", "t_rollback", "t_rollback_one"]))))
                open_[1 - p] = False
                steps.append((p, OP("await")))
        elif x < 0.75 and not open_[p]:
            steps.append((p, OP("t_start")))
            open_[p] = True
        elif x < 0.82 and open_[p] and rng.random() < 0.5:
            steps.append((1 - p, OP("terminate", target=p)))
            break
        elif open_[p]:
            steps.append((p, OP(rng.choice(["t_commit", "t_rollback", "t_rollback_one"]))))
            open_[p] = False
        else:
            steps.append((p, TL))
    alive = [q for q in (0, 1) if not any(o.get("op") == "terminate" and o.get("target") == q for _, o in steps)]
    for p in alive:
        if open_[p]:
            steps.append((p, OP("t_commit")))
    steps.append((alive[0], CNT))
    return case(f"rand-e1-{seed}-{i}", "embedded and dynamic DML on the same rows (random)", 2, steps,
                tables=["N", "R"])


def main() -> int:
    out = sys.argv[1]
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 1
    k = int(sys.argv[sys.argv.index("--random") + 1]) if "--random" in sys.argv else 40
    rng = random.Random(seed)
    if "--s1" in sys.argv:  # round r2: the SQL-function family, a fresh random e1 family
        cases = named_sqlproc() + [rand_s1(rng, i, seed) for i in range(k)] + [rand_e1(rng, i, seed) for i in range(k // 2)]
    else:
        cases = named() + [rand_e1(rng, i, seed) for i in range(k)]
    with open(out, "w") as f:
        json.dump(cases, f, indent=1)
    print(len(cases), "cases", "seed", seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
