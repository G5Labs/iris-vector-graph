#!/usr/bin/env python3
"""Generate the iris-contract differential cases.

    python cases.py out.json [--seed N] [--random-per-family K]

Two kinds of case:
- named clause cases: one per contract clause, each a sharpness case (the contract permits few outcomes and
  forbids the plausible alternative a mutant encodes);
- seeded random families: single-process transaction-controller sequences mixing Native API, SQL and driver verbs;
  two-process lock sequences over hierarchical names and modes; two-process visibility/rollback sequences; row-lock
  sequences with waits; process stops. The seed is recorded in the output so a run can be regenerated exactly.

Roots: ^X (globals, -> ^IVGAuditEnv), ^L (locks, -> ^IVGAuditLk), table T (-> IVGAudit.T).
"""
from __future__ import annotations

import json
import random
import sys
from typing import Dict, List


def N(root: str, *subs: str) -> Dict:
    return {"root": root, "subs": list(subs)}


X = lambda *s: N("^X", *s)  # noqa: E731
L = lambda *s: N("^L", *s)  # noqa: E731
OP = lambda name, **kw: {"op": name, **kw}  # noqa: E731
TL = OP("t_level")


def case(cid: str, clause: str, procs: int, steps: List, observe=(), tables=False, kinds=None) -> Dict:
    c = {"id": cid, "clause": clause, "procs": procs, "steps": [[p, o] for p, o in steps],
         "observe": list(observe), "observe_tables": ["T"] if tables else []}
    if kinds:
        c["kinds"] = kinds
    return c


def named() -> List[Dict]:
    a, b = X("a"), X("b")
    out = [
        # --- transactions: nesting, commit, rollback
        case("txn-nest-commit-inner", "TCOMMIT inside another level only lowers the level", 1,
             [(0, OP("t_start")), (0, OP("t_start")), (0, OP("set", node=a, value="1")), (0, OP("t_commit")), (0, TL),
              (0, OP("t_rollback")), (0, TL)], observe=[a]),
        case("txn-rollback-one", "TROLLBACK 1 undoes only the top level", 1,
             [(0, OP("t_start")), (0, OP("set", node=a, value="o")), (0, OP("t_start")), (0, OP("set", node=b, value="i")),
              (0, OP("t_rollback_one")), (0, TL), (0, OP("t_commit")), (0, TL)], observe=[a, b]),
        case("txn-commit-at-zero", "TCOMMIT with no transaction is a <COMMAND> error", 1, [(0, OP("t_commit")), (0, TL)]),
        case("txn-incr-survives", "$INCREMENT is not rolled back", 1,
             [(0, OP("set", node=a, value="5")), (0, OP("t_start")), (0, OP("incr", node=a)), (0, OP("t_rollback"))],
             observe=[a]),
        case("txn-kill-subtree-rollback", "a rollback restores a killed subtree", 1,
             [(0, OP("set", node=X("t", "1"), value="1")), (0, OP("set", node=X("t", "2"), value="2")), (0, OP("t_start")),
              (0, OP("kill", node=X("t"))), (0, OP("data", node=X("t"))), (0, OP("t_rollback")), (0, OP("data", node=X("t")))],
             observe=[X("t", "1"), X("t", "2")]),
        case("txn-dirty-read", "another process sees an uncommitted global write", 2,
             [(0, OP("t_start")), (0, OP("set", node=a, value="d")), (1, OP("get", node=a)), (0, OP("t_rollback")),
              (1, OP("get", node=a))]),
        case("txn-physical-rollback", "a rollback restores the old value over another process's later write", 2,
             [(0, OP("t_start")), (0, OP("set", node=a, value="mine")), (1, OP("set", node=a, value="theirs")),
              (0, OP("t_rollback"))], observe=[a]),
        # --- SQL and driver verbs on the same process
        case("sql-commit-native-2", "SQL COMMIT at two Native levels", 1,
             [(0, OP("t_start")), (0, OP("t_start")), (0, OP("sql_commit")), (0, TL)]),
        case("sql-rollback-native-2", "SQL ROLLBACK at two Native levels", 1,
             [(0, OP("t_start")), (0, OP("t_start")), (0, OP("sql_rollback")), (0, TL)]),
        case("sql-start-inside-native", "SQL START TRANSACTION inside a Native level", 1,
             [(0, OP("t_start")), (0, OP("sql_start")), (0, TL), (0, OP("t_rollback")), (0, TL)]),
        case("sql-start-twice", "a second SQL START TRANSACTION while SQL owns it does nothing", 1,
             [(0, OP("sql_start")), (0, OP("sql_start")), (0, TL), (0, OP("sql_commit")), (0, TL)]),
        case("drv-rollback-native-2", "driver rollback() at two Native levels", 1,
             [(0, OP("t_start")), (0, OP("t_start")), (0, OP("drv_rollback")), (0, TL)]),
        case("drv-commit-native-2", "driver commit() at two Native levels", 1,
             [(0, OP("t_start")), (0, OP("t_start")), (0, OP("drv_commit")), (0, TL), (0, OP("t_rollback"))]),
        case("sql-row-in-native-level", "SQL rows written inside a Native level follow TROLLBACK 1", 1,
             [(0, OP("t_start")), (0, OP("insert", table="T", k="1", v="a")), (0, OP("t_start")),
              (0, OP("insert", table="T", k="2", v="b")), (0, OP("t_rollback_one")), (0, OP("select", table="T")),
              (0, OP("t_rollback")), (0, OP("select", table="T"))]),
        case("autocommit-off-first-write", "with autocommit off the first DML opens a transaction", 1,
             [(0, OP("set_autocommit", on=False)), (0, TL), (0, OP("insert", table="T", k="1", v="a")), (0, TL),
              (0, OP("drv_rollback")), (0, TL), (0, OP("set_autocommit", on=True))], tables=True),
        case("autocommit-on-commits-one-level", "turning the driver's autocommit on commits one open level", 1,
             [(0, OP("t_start")), (0, OP("set", node=a, value="1")), (0, OP("set_autocommit", on=True)), (0, TL),
              (0, OP("t_rollback")), (0, OP("get", node=a)), (0, OP("t_start")), (0, OP("t_start")),
              (0, OP("set", node=b, value="2")), (0, OP("set_autocommit", on=True)), (0, TL), (0, OP("t_rollback")),
              (0, OP("get", node=b)), (0, OP("set_autocommit", on=False)), (0, OP("insert", table="T", k="1", v="a")),
              (0, TL), (0, OP("set_autocommit", on=True)), (0, TL), (0, OP("t_rollback"))], tables=True),
        # --- locks
        case("lock-deferred-in-txn", "an unlock inside a transaction takes effect at its end", 2,
             [(0, OP("t_start")), (0, OP("lock", node=L("a"), mode="E", wait=False)),
              (0, OP("unlock", node=L("a"), mode="E", immediate=False)),
              (1, OP("lock", node=L("a"), mode="E", wait=False)), (0, OP("t_commit")),
              (1, OP("lock", node=L("a"), mode="E", wait=False))]),
        case("lock-deferred-pre-txn", "an unlock in a transaction defers a lock taken before it", 2,
             [(0, OP("lock", node=L("a"), mode="E", wait=False)), (0, OP("t_start")),
              (0, OP("unlock", node=L("a"), mode="E", immediate=False)), (1, OP("lock", node=L("a"), mode="E", wait=False)),
              (0, OP("t_rollback")), (1, OP("lock", node=L("a"), mode="E", wait=False))]),
        case("lock-immediate", "an immediate unlock releases at once inside a transaction", 2,
             [(0, OP("t_start")), (0, OP("lock", node=L("a"), mode="E", wait=False)),
              (0, OP("unlock", node=L("a"), mode="E", immediate=True)), (1, OP("lock", node=L("a"), mode="E", wait=False)),
              (0, OP("t_commit"))]),
        case("lock-survives-commit", "a lock not unlocked survives the commit", 2,
             [(0, OP("t_start")), (0, OP("lock", node=L("a"), mode="E", wait=False)), (0, OP("t_commit")),
              (1, OP("lock", node=L("a"), mode="E", wait=False))]),
        case("lock-hier-child", "a lock on a name conflicts with a lock on its descendant", 2,
             [(0, OP("lock", node=L("p"), mode="E", wait=False)), (1, OP("lock", node=L("p", "c"), mode="E", wait=False))]),
        case("lock-hier-parent", "a lock on a name conflicts with a lock on its ancestor", 2,
             [(0, OP("lock", node=L("p", "c"), mode="E", wait=False)), (1, OP("lock", node=L("p"), mode="E", wait=False))]),
        case("lock-siblings", "locks on sibling names do not conflict", 2,
             [(0, OP("lock", node=L("p", "c"), mode="E", wait=False)), (1, OP("lock", node=L("p", "d"), mode="E", wait=False))]),
        case("lock-shared", "shared locks are compatible; exclusive conflicts with shared", 2,
             [(0, OP("lock", node=L("s"), mode="S", wait=False)), (1, OP("lock", node=L("s"), mode="S", wait=False)),
              (1, OP("lock", node=L("s"), mode="E", wait=False))]),
        case("lock-shared-parent-excl", "a shared lock on a descendant blocks an exclusive lock on the ancestor", 2,
             [(0, OP("lock", node=L("s", "1"), mode="S", wait=False)), (1, OP("lock", node=L("s"), mode="E", wait=False)),
              (1, OP("lock", node=L("s"), mode="S", wait=False))]),
        case("lock-incremental", "lock counts are incremental", 2,
             [(0, OP("lock", node=L("c"), mode="E", wait=False)), (0, OP("lock", node=L("c"), mode="E", wait=False)),
              (0, OP("unlock", node=L("c"), mode="E", immediate=False)), (1, OP("lock", node=L("c"), mode="E", wait=False)),
              (0, OP("unlock", node=L("c"), mode="E", immediate=False)), (1, OP("lock", node=L("c"), mode="E", wait=False))]),
        case("lock-wait-then-get", "a waiting lock is granted when the holder releases", 2,
             [(0, OP("lock", node=L("w"), mode="E", wait=False)), (1, OP("lock", node=L("w"), mode="E", wait=True)),
              (1, OP("await")), (0, OP("release_all")), (1, OP("await"))]),
        case("lock-release-all-in-txn", "release-all inside a transaction", 2,
             [(0, OP("t_start")), (0, OP("lock", node=L("r"), mode="E", wait=False)), (0, OP("release_all")),
              (1, OP("lock", node=L("r"), mode="E", wait=False)), (0, OP("t_commit"))]),
        case("lock-only-releases-others", "a non-incremental LOCK releases every other lock first", 2,
             [(0, OP("lock", node=L("a"), mode="E", wait=False)), (0, OP("lock_only", node=L("b"), wait=False)),
              (1, OP("lock", node=L("a"), mode="E", wait=False)), (1, OP("lock", node=L("b"), mode="E", wait=False))],
             kinds=["term", "dbapi"]),
        case("lock-only-in-txn", "a non-incremental LOCK inside a transaction", 2,
             [(0, OP("t_start")), (0, OP("lock", node=L("a"), mode="E", wait=False)), (0, OP("lock_only", node=L("b"), wait=False)),
              (1, OP("lock", node=L("a"), mode="E", wait=False)), (0, OP("t_commit")),
              (1, OP("lock", node=L("a"), mode="E", wait=False))], kinds=["term", "dbapi"]),
        # --- process-private globals
        case("ppg-not-rolled-back", "process-private globals are not rolled back", 1,
             [(0, OP("ppg_set", node=X("p"), value="1")), (0, OP("t_start")), (0, OP("ppg_set", node=X("p"), value="2")),
              (0, OP("t_rollback")), (0, OP("ppg_get", node=X("p")))], kinds=["term"]),
        case("ppg-private", "another process does not see a process-private global", 2,
             [(0, OP("ppg_set", node=X("p"), value="1")), (1, OP("ppg_get", node=X("p")))], kinds=["term", "term"]),
        # --- SQL rows and row locks
        case("row-dirty-select", "SQL SELECT sees another process's uncommitted insert", 2,
             [(0, OP("t_start")), (0, OP("insert", table="T", k="1", v="a")), (1, OP("select", table="T")),
              (0, OP("t_rollback")), (1, OP("select", table="T"))]),
        case("row-delete-waits-insert", "a DELETE waits for a row another transaction inserted", 2,
             [(0, OP("t_start")), (0, OP("insert", table="T", k="1", v="a")), (1, OP("delete", table="T", k="1")),
              (1, OP("await")), (0, OP("t_commit")), (1, OP("await"))], tables=True),
        case("row-delete-waits-insert-rb", "the waiting DELETE affects nothing after the insert rolls back", 2,
             [(0, OP("t_start")), (0, OP("insert", table="T", k="1", v="a")), (1, OP("delete", table="T", k="1")),
              (0, OP("t_rollback")), (1, OP("await"))], tables=True),
        case("row-update-waits-update", "an UPDATE waits for a row another transaction updated", 2,
             [(0, OP("insert", table="T", k="1", v="a")), (0, OP("t_start")), (0, OP("update", table="T", k="1", v="b")),
              (1, OP("update", table="T", k="1", v="c")), (0, OP("t_commit")), (1, OP("await"))], tables=True),
        case("row-autocommit-no-hold", "an autocommit statement holds no row lock afterwards", 2,
             [(0, OP("insert", table="T", k="1", v="a")), (1, OP("delete", table="T", k="1"))], tables=True),
        case("row-insert-dup-uncommitted", "INSERT of a key another transaction inserted", 2,
             [(0, OP("t_start")), (0, OP("insert", table="T", k="1", v="a")), (1, OP("insert", table="T", k="1", v="b")),
              (0, OP("t_rollback"))], tables=True),
        case("row-insert-after-uncommitted-delete", "INSERT of a key another transaction deleted", 2,
             [(0, OP("insert", table="T", k="1", v="a")), (0, OP("t_start")), (0, OP("delete", table="T", k="1")),
              (1, OP("insert", table="T", k="1", v="b")), (0, OP("t_rollback")), (1, OP("await"))], tables=True),
        case("row-global-write-no-row-lock", "a global SET takes no lock: a DELETE of a row set by globals does not wait", 2,
             [(0, OP("insert", table="T", k="1", v="a")), (0, OP("t_start")), (0, OP("set", node=X("side"), value="1")),
              (1, OP("delete", table="T", k="1")), (0, OP("t_rollback"))], tables=True),
        # --- process stop
        case("stop-rolls-back", "a stopped process's open transaction is rolled back", 2,
             [(0, OP("t_start")), (0, OP("set", node=a, value="x")), (0, OP("insert", table="T", k="1", v="a")),
              (1, OP("terminate", target=0)), (1, OP("get", node=a))], observe=[a], tables=True),
        case("stop-releases-locks", "a stopped process's locks are released", 2,
             [(0, OP("lock", node=L("k"), mode="E", wait=False)), (1, OP("lock", node=L("k"), mode="E", wait=False)),
              (1, OP("terminate", target=0)), (1, OP("lock", node=L("k"), mode="E", wait=False))]),
        case("stop-releases-row-lock", "a stopped process's row locks are released and a waiter proceeds", 3,
             [(0, OP("t_start")), (0, OP("insert", table="T", k="1", v="a")), (1, OP("delete", table="T", k="1")),
              (2, OP("terminate", target=0)), (1, OP("await"))], tables=True),
        case("stop-nested-levels", "a stop rolls back every level", 2,
             [(0, OP("t_start")), (0, OP("set", node=a, value="1")), (0, OP("t_start")), (0, OP("set", node=b, value="2")),
              (0, OP("t_commit")), (1, OP("terminate", target=0))], observe=[a, b]),
    ]
    return out


def rand_txn_controller(rng: random.Random, i: int, seed: int = 0) -> Dict:
    verbs = ["t_start", "t_start", "t_commit", "t_rollback_one", "t_rollback", "sql_start", "sql_commit", "sql_rollback",
             "drv_commit", "drv_rollback", "set", "insert"]
    steps = []
    k = 0
    for _ in range(rng.randint(5, 11)):
        v = rng.choice(verbs)
        if v == "set":
            steps.append((0, OP("set", node=X(str(rng.randint(1, 3))), value=str(k))))
        elif v == "insert":
            k += 1
            steps.append((0, OP("insert", table="T", k=str(k), v="r")))
        else:
            steps.append((0, OP(v)))
        steps.append((0, TL))
    return case(f"rand-txn-{seed}-{i}", "transaction controller (random)", 1, steps,
                observe=[X("1"), X("2"), X("3")], tables=True)


def rand_locks(rng: random.Random, i: int, seed: int = 0) -> Dict:
    names = [L("a"), L("a", "1"), L("a", "2"), L("b")]
    steps = []
    for _ in range(rng.randint(6, 12)):
        p = rng.randint(0, 1)
        r = rng.random()
        n = rng.choice(names)
        if r < 0.40:
            steps.append((p, OP("lock", node=n, mode=rng.choice(["E", "S"]), wait=False)))
        elif r < 0.65:
            steps.append((p, OP("unlock", node=n, mode=rng.choice(["E", "S"]), immediate=rng.random() < 0.3)))
        elif r < 0.75:
            steps.append((p, OP("t_start")))
        elif r < 0.83:
            steps.append((p, OP("t_commit")))
        elif r < 0.90:
            steps.append((p, OP("t_rollback")))
        else:
            steps.append((p, OP("release_all")))
    # probe every name from both sides at the end, with timeout 0
    for p in (0, 1):
        for n in names:
            steps.append((p, OP("lock", node=n, mode="E", wait=False)))
    return case(f"rand-lock-{seed}-{i}", "lock table (random)", 2, steps)


def rand_visibility(rng: random.Random, i: int, seed: int = 0) -> Dict:
    nodes = [X("a"), X("b"), X("a", "1")]
    steps = []
    for _ in range(rng.randint(6, 12)):
        p = rng.randint(0, 1)
        r = rng.random()
        n = rng.choice(nodes)
        if r < 0.30:
            steps.append((p, OP("set", node=n, value=f"{p}{len(steps)}")))
        elif r < 0.40:
            steps.append((p, OP("kill", node=n)))
        elif r < 0.55:
            steps.append((p, OP("get", node=n)))
        elif r < 0.62:
            steps.append((p, OP("incr", node=X("n"))))
        elif r < 0.75:
            steps.append((p, OP("t_start")))
        elif r < 0.83:
            steps.append((p, OP("t_commit")))
        elif r < 0.92:
            steps.append((p, OP("t_rollback_one")))
        else:
            steps.append((p, OP("t_rollback")))
    return case(f"rand-vis-{seed}-{i}", "visibility and rollback (random)", 2, steps,
                observe=[X("a"), X("b"), X("a", "1"), X("n")])


def rand_rows(rng: random.Random, i: int, seed: int = 0) -> Dict:
    """Two processes doing DML on two keys in and out of transactions. After a DML that may block, the other
    process ends its transaction and the first awaits, so no process is left pending; an `await` with nothing
    pending is itself an observation both sides must agree on ("nothing pending")."""
    steps = []
    open_ = {0: False, 1: False}
    for _ in range(rng.randint(4, 8)):
        p = rng.randint(0, 1)
        r = rng.random()
        k = str(rng.randint(1, 2))
        if r < 0.55:
            op = rng.choice([OP("insert", table="T", k=k, v=f"{p}"), OP("delete", table="T", k=k),
                             OP("update", table="T", k=k, v=f"u{p}")])
            steps.append((p, op))
            if open_[1 - p]:
                steps.append((1 - p, OP(rng.choice(["t_commit", "t_rollback"]))))
                open_[1 - p] = False
                steps.append((p, OP("await")))
        elif r < 0.80 and not open_[p]:
            steps.append((p, OP("t_start")))
            open_[p] = True
        elif open_[p]:
            steps.append((p, OP(rng.choice(["t_commit", "t_rollback"]))))
            open_[p] = False
    for p in (0, 1):
        if open_[p]:
            steps.append((p, OP("t_commit")))
    steps.append((0, OP("select", table="T")))
    return case(f"rand-row-{seed}-{i}", "row locks (random)", 2, steps, tables=True)


# ---------------------------------------------------------------------------------------------- extension (r3)

F = "F"


def ins(table, k, v, **kw):
    return OP("insert", table=table, k=k, v=v, **kw)


def find(w):
    return OP("find", table=F, word=w)


def named_ext() -> List[Dict]:
    """Named sharpness cases of the extension clauses (round r3)."""
    a = X("a")
    out = [
        # --- functional index (iFind Basic on F.v): entries written by the row's statement, in its transaction
        case("fx-autocommit-visible", "a committed row's functional-index entry is listed", 2,
             [(0, ins(F, "1", "apple")), (1, find("apple")), (1, find("pear"))]),
        case("fx-dirty-then-rollback", "an uncommitted row's index entry is visible and is undone with the row", 2,
             [(0, OP("t_start")), (0, ins(F, "1", "apple")), (1, find("apple")), (0, OP("t_rollback")),
              (1, find("apple"))], tables=False),
        case("fx-rollback-one", "TROLLBACK 1 undoes only the inner level's index entries", 2,
             [(0, OP("t_start")), (0, ins(F, "1", "apple")), (0, OP("t_start")), (0, ins(F, "2", "apple")),
              (0, OP("t_rollback_one")), (1, find("apple")), (0, OP("t_commit")), (1, find("apple"))]),
        case("fx-update-rollback", "an UPDATE moves the entry; its rollback moves it back", 2,
             [(0, ins(F, "1", "pear")), (0, OP("t_start")), (0, OP("update", table=F, k="1", v="plum")),
              (1, find("plum")), (1, find("pear")), (0, OP("t_rollback")), (1, find("pear")), (1, find("plum"))]),
        case("fx-delete-rollback", "a DELETE removes the entry; its rollback restores it", 2,
             [(0, ins(F, "1", "pear")), (0, OP("t_start")), (0, OP("delete", table=F, k="1")), (1, find("pear")),
              (0, OP("t_rollback")), (1, find("pear"))]),
        case("fx-sql-rollback", "SQL ROLLBACK undoes the index entry with the row", 1,
             [(0, OP("sql_start")), (0, ins(F, "1", "fig")), (0, find("fig")), (0, OP("sql_rollback")), (0, find("fig"))]),
        case("fx-autocommit-off-rollback", "driver rollback() undoes the index entry with the row", 1,
             [(0, OP("set_autocommit", on=False)), (0, ins(F, "1", "fig")), (0, OP("drv_rollback")), (0, find("fig")),
              (0, OP("set_autocommit", on=True))]),
        case("fx-stop-rolls-back", "a stopped process's uncommitted index entries are undone", 2,
             [(0, OP("t_start")), (0, ins(F, "1", "fig")), (1, find("fig")), (1, OP("terminate", target=0)),
              (1, find("fig"))]),
        case("fx-term-path", "a row written by ObjectScript %ExecDirect maintains the index in its transaction", 2,
             [(0, OP("t_start")), (0, ins(F, "1", "plum")), (1, find("plum")), (0, OP("t_rollback")), (1, find("plum"))],
             kinds=["term", "dbapi"]),
        # --- %NOINDEX and BUILD INDEX
        case("noindex-insert-then-build", "%NOINDEX writes the row but no index entry; BUILD INDEX adds it", 2,
             [(0, ins(F, "1", "kiwi", noindex=True)), (1, find("kiwi")), (1, OP("select", table=F)),
              (0, OP("build_index", table=F)), (1, find("kiwi"))]),
        case("noindex-in-txn-rollback", "a %NOINDEX row in a transaction is undone by its rollback", 1,
             [(0, OP("t_start")), (0, ins(F, "1", "kiwi", noindex=True)), (0, OP("t_rollback")),
              (0, OP("select", table=F)), (0, OP("build_index", table=F)), (0, find("kiwi"))]),
        case("noindex-term", "%NOINDEX through ObjectScript %ExecDirect", 1,
             [(0, ins(F, "1", "date", noindex=True)), (0, find("date")), (0, OP("build_index", table=F)),
              (0, find("date"))], kinds=["term"]),
        case("build-index-not-in-txn", "BUILD INDEX inside a transaction is not undone by its rollback", 1,
             [(0, ins(F, "1", "kiwi", noindex=True)), (0, OP("t_start")), (0, OP("build_index", table=F)), (0, TL),
              (0, find("kiwi")), (0, OP("t_rollback")), (0, find("kiwi"))]),
        case("build-index-needs-extent", "BUILD INDEX fails (-400) while a transaction holds a row of the table", 2,
             [(0, OP("t_start")), (0, ins(F, "1", "fig")), (0, OP("build_index", table=F)), (1, OP("build_index", table=F)),
              (0, OP("t_rollback")), (1, OP("build_index", table=F)), (1, find("fig"))]),
        case("noindex-unique-not-maintained", "a %NOINDEX row is not in the unique index: a plain INSERT of its key "
             "writes a second row", 1,
             [(0, ins(F, "1", "kiwi", noindex=True)), (0, ins(F, "1", "lime")), (0, OP("select", table=F)),
              (0, find("lime")), (0, find("kiwi"))]),
        case("nocheck-second-row", "%NOCHECK skips the unique check: a second row with the key", 1,
             [(0, ins(F, "1", "apple")), (0, ins(F, "1", "pear", nocheck=True)), (0, OP("select", table=F)),
              (0, find("apple")), (0, find("pear")), (0, ins(F, "2", "pear", nocheck=True)), (0, find("pear"))]),
        case("noindex-insert-checks-unique", "%NOINDEX alone still checks the unique key", 1,
             [(0, ins(F, "1", "apple")), (0, ins(F, "1", "kiwi", noindex=True)), (0, OP("select", table=F))]),
        case("nocheck-noindex-term", "%NOINDEX %NOCHECK through ObjectScript (the bulk loader's hints)", 1,
             [(0, ins("T", "1", "a")), (0, ins("T", "1", "b", noindex=True, nocheck=True)), (0, OP("select", table="T"))],
             kinds=["term"]),
        case("build-index-dup-report", "after BUILD INDEX a duplicate INSERT reaches the DB-API as <LIST ERROR>, "
             "ObjectScript as -119; nothing is written", 2,
             [(0, ins(F, "1", "apple")), (0, ins("T", "5", "a")), (0, ins(F, "1", "pear")), (1, ins(F, "1", "pear")),
              (0, OP("build_index", table=F)), (0, OP("build_index", table="T")), (0, ins(F, "1", "plum")),
              (1, ins(F, "1", "plum")), (0, ins("T", "5", "b")), (1, ins("T", "5", "b")), (0, OP("delete", table=F, k="1")),
              (0, ins(F, "1", "fig")), (0, ins(F, "1", "kiwi")), (0, ins(F, "1", "date", noindex=True)),
              (0, OP("select", table=F)), (0, find("fig"))], tables=True, kinds=["dbapi", "term"]),
        case("build-index-rebuilds-all", "BUILD INDEX lists every row once, indexed or not", 1,
             [(0, ins(F, "1", "apple")), (0, ins(F, "2", "apple", noindex=True)), (0, find("apple")),
              (0, OP("build_index", table=F)), (0, find("apple"))]),
        # --- DDL
        case("ddl-create-in-txn", "CREATE TABLE in a transaction is undone by its rollback; the transaction stays open", 1,
             [(0, OP("t_start")), (0, OP("set", node=a, value="1")), (0, OP("create_table", table="D1")), (0, TL),
              (0, ins("D1", "1", "x")), (0, OP("t_rollback")), (0, TL), (0, OP("table_exists", table="D1")),
              (0, OP("get", node=a))]),
        case("ddl-create-commit", "CREATE TABLE in a committed transaction stays", 1,
             [(0, OP("t_start")), (0, OP("create_table", table="D1")), (0, ins("D1", "1", "x")), (0, OP("t_commit")),
              (0, OP("table_exists", table="D1")), (0, OP("select", table="D1"))]),
        case("ddl-drop-in-txn", "DROP TABLE in a transaction is undone by its rollback, rows included", 1,
             [(0, OP("create_table", table="D1")), (0, ins("D1", "1", "x")), (0, OP("t_start")),
              (0, OP("set", node=a, value="1")), (0, OP("drop_table", table="D1")), (0, TL),
              (0, OP("table_exists", table="D1")), (0, OP("select", table="D1")), (0, OP("t_rollback")), (0, TL),
              (0, OP("table_exists", table="D1")), (0, OP("get", node=a)), (0, OP("select", table="D1"))]),
        case("ddl-drop-waits-row-lock", "DROP TABLE cannot get the table lock while another transaction holds a row", 2,
             [(0, OP("create_table", table="D1")), (1, OP("t_start")), (1, ins("D1", "1", "x")),
              (0, OP("drop_table", table="D1")), (1, OP("t_rollback")), (0, OP("drop_table", table="D1")),
              (0, OP("table_exists", table="D1"))]),
        case("ddl-visible-at-once", "another process sees a table created in an open transaction", 2,
             [(0, OP("t_start")), (0, OP("create_table", table="D1")), (1, OP("table_exists", table="D1")),
              (0, OP("t_rollback")), (1, OP("table_exists", table="D1"))]),
        case("ddl-errors", "CREATE of an existing table, DROP / INSERT / SELECT of a missing one", 1,
             [(0, OP("create_table", table="D1")), (0, OP("create_table", table="D1")), (0, OP("drop_table", table="D2")),
              (0, ins("D2", "1", "x")), (0, OP("select", table="D2"))]),
        case("ddl-under-sql-txn", "DDL inside an SQL START TRANSACTION", 1,
             [(0, OP("sql_start")), (0, ins("T", "1", "a")), (0, OP("create_table", table="D1")), (0, TL),
              (0, OP("sql_rollback")), (0, TL), (0, OP("select", table="T")), (0, OP("table_exists", table="D1"))]),
        case("ddl-autocommit-off", "DDL with the driver's autocommit off", 1,
             [(0, OP("set_autocommit", on=False)), (0, OP("create_table", table="D1")), (0, TL),
              (0, ins("D1", "1", "x")), (0, TL), (0, OP("drv_rollback")), (0, TL),
              (0, OP("table_exists", table="D1")), (0, OP("select", table="D1")), (0, OP("set_autocommit", on=True))]),
        case("ddl-term-in-txn", "DDL through ObjectScript %ExecDirect inside TSTART", 1,
             [(0, OP("t_start")), (0, OP("create_table", table="D1")), (0, TL), (0, OP("t_rollback")),
              (0, OP("table_exists", table="D1"))], kinds=["term"]),
        # --- SELECT * column order and ALTER TABLE ADD COLUMN
        case("select-star-order", "SELECT * lists the declared columns in declaration order", 1,
             [(0, OP("select_star", table="C")), (0, OP("select_star", table="T"))]),
        case("alter-add-column-last", "ALTER TABLE ADD COLUMN appends the column", 1,
             [(0, OP("add_column", table="C", col="beta")), (0, OP("select_star", table="C"))]),
        case("alter-in-txn-rolled-back", "ALTER TABLE in a transaction is undone by its rollback", 1,
             [(0, OP("t_start")), (0, OP("add_column", table="C", col="beta")), (0, TL), (0, OP("t_rollback")),
              (0, OP("select_star", table="C"))]),
        case("alter-in-txn-other-process", "an uncommitted ALTER is visible to another process and undone for it", 2,
             [(0, OP("t_start")), (0, OP("add_column", table="C", col="beta")), (1, OP("select_star", table="C")),
              (0, OP("select_star", table="C")), (0, OP("t_rollback")), (1, OP("table_exists", table="C"))]),
        case("ddl-create-rollback-fresh-statement", "after a rolled-back CREATE, a process that compiled nothing "
             "against the table finds it gone", 2,
             [(0, OP("t_start")), (0, OP("create_table", table="D1")), (1, OP("table_exists", table="D1")),
              (0, OP("t_rollback")), (1, OP("select", table="D1")), (1, ins("D1", "1", "x"))]),
        # --- NULL and the empty string on the two client paths
        case("enc-dbapi-writes", "DB-API '' and None parameters and literals, read on both paths", 2,
             [(0, OP("put_e", k="1", v="")), (0, OP("put_e", k="2", v=None)), (0, OP("put_e", k="3", v="", literal=True)),
              (0, OP("put_e", k="4", v=None, literal=True)), (0, OP("put_e", k="5", v="x"))]
             + [(p, OP("get_e", k=k)) for k in "12345" for p in (0, 1)], kinds=["dbapi", "term"]),
        case("enc-term-writes", "ObjectScript \"\" and $Char(0) parameters and literals, read on both paths", 2,
             [(0, OP("put_e", k="1", v="")), (0, OP("put_e", k="2", v="\u0000")), (0, OP("put_e", k="3", v="", literal=True)),
              (0, OP("put_e", k="4", v=None, literal=True)), (0, OP("put_e", k="5", v="x"))]
             + [(p, OP("get_e", k=k)) for k in "12345" for p in (0, 1)], kinds=["term", "dbapi"]),
        case("enc-coalesce-guard", "COALESCE(v, '') = COALESCE(?, '') folds NULL and '' on both paths", 2,
             [(0, OP("put_e", k="1", v="")), (0, OP("put_e", k="2", v=None)), (0, OP("put_e", k="3", v="x"))]
             + [(p, OP("match_e", v=v)) for p in (0, 1) for v in (None, "", "\u0000", "x", "y")], kinds=["dbapi", "term"]),
        case("enc-dbapi-chr0", "a DB-API parameter $Char(0) is the SQL empty string", 2,
             [(0, OP("put_e", k="1", v="\u0000")), (0, OP("get_e", k="1")), (1, OP("get_e", k="1"))],
             kinds=["dbapi", "term"]),
        # --- statement-level atomicity
        case("stmt-atomic-in-txn", "a failing INSERT ... SELECT undoes its own rows; the transaction stays open", 1,
             [(0, ins("S", "1", "s1")), (0, ins("S", "2", "s2")), (0, ins("S", "3", "s3")), (0, ins("T", "3", "t3")),
              (0, OP("t_start")), (0, ins("T", "9", "t9")), (0, OP("insert_select", **{"from": "S", "to": "T"})), (0, TL),
              (0, OP("select", table="T")), (0, OP("t_commit"))], tables=True),
        case("stmt-atomic-autocommit", "a failing INSERT ... SELECT at level 0 leaves nothing", 1,
             [(0, ins("S", "1", "s1")), (0, ins("S", "2", "s2")), (0, ins("S", "3", "s3")), (0, ins("T", "3", "t3")),
              (0, OP("insert_select", **{"from": "S", "to": "T"})), (0, TL)], tables=True),
        case("stmt-ok-rolled-back", "a successful INSERT ... SELECT in a transaction is undone by its rollback", 1,
             [(0, ins("S", "1", "s1")), (0, ins("S", "2", "s2")), (0, OP("t_start")),
              (0, OP("insert_select", **{"from": "S", "to": "T"})), (0, OP("select", table="T")), (0, OP("t_rollback"))],
             tables=True),
        case("autocommit-off-failed-dml", "with autocommit off a failing DML opens the transaction; a DML that finds no "
             "row does not", 1,
             [(0, ins("T", "1", "a")), (0, ins("S", "1", "s1")), (0, OP("set_autocommit", on=False)), (0, TL),
              (0, OP("delete", table="T", k="9")), (0, TL), (0, OP("update", table="T", k="9", v="z")), (0, TL),
              (0, ins("T", "1", "b")), (0, TL), (0, OP("drv_rollback")), (0, TL),
              (0, OP("insert_select", **{"from": "S", "to": "T"})), (0, TL), (0, OP("drv_rollback")), (0, TL),
              (0, OP("set_autocommit", on=True))], tables=True),
        case("stmt-atomic-term", "statement atomicity through ObjectScript %ExecDirect", 1,
             [(0, ins("S", "1", "s1")), (0, ins("S", "2", "s2")), (0, ins("T", "2", "t2")), (0, OP("t_start")),
              (0, OP("insert_select", **{"from": "S", "to": "T"})), (0, TL), (0, OP("select", table="T")),
              (0, OP("t_commit"))], tables=True, kinds=["term"]),
        # --- SELECT $TLEVEL
        case("sql-tlevel", "SELECT $TLEVEL reports the level; a SELECT does not open one with autocommit off", 1,
             [(0, OP("sql_t_level")), (0, OP("t_start")), (0, OP("t_start")), (0, OP("sql_t_level")), (0, OP("t_rollback")),
              (0, OP("set_autocommit", on=False)), (0, OP("sql_t_level")), (0, OP("select", table="T")), (0, TL),
              (0, ins("T", "1", "a")), (0, OP("sql_t_level")), (0, OP("drv_rollback")), (0, OP("sql_t_level")),
              (0, OP("set_autocommit", on=True))]),
        case("sql-tlevel-term", "SELECT $TLEVEL through ObjectScript %ExecDirect", 1,
             [(0, OP("t_start")), (0, OP("sql_t_level")), (0, OP("t_rollback")), (0, OP("sql_t_level"))], kinds=["term"]),
        # --- vectors (availability) and $VECTOR in a global
        case("vec-sql-functions", "VECTOR_COSINE and VECTOR_DOT_PRODUCT exist; VECTOR_L2 does not (-359)", 2,
             [(0, {"op": "sql_fn", "name": "VECTOR_COSINE"}), (0, {"op": "sql_fn", "name": "VECTOR_DOT_PRODUCT"}),
              (0, {"op": "sql_fn", "name": "VECTOR_L2"}), (1, {"op": "sql_fn", "name": "VECTOR_L2"})], kinds=["dbapi", "term"]),
        case("vec-global", "a $VECTOR element SET in a global is read back and undone by a rollback", 1,
             [(0, OP("vec_set", node=X("v"), i=1, x=".5")), (0, OP("vec_set", node=X("v"), i=2, x=".25")),
              (0, OP("vec_get", node=X("v"), i=1)), (0, OP("vec_get", node=X("v"), i=3)), (0, OP("t_start")),
              (0, OP("vec_set", node=X("v"), i=1, x="9")), (0, OP("vec_get", node=X("v"), i=1)), (0, OP("t_rollback")),
              (0, OP("vec_get", node=X("v"), i=1))], kinds=["term"]),
        case("vec-native-get", "the Native API cannot read a $VECTOR value in a global", 2,
             [(0, OP("vec_set", node=X("v"), i=1, x=".5")), (1, OP("get", node=X("v"))), (1, OP("data", node=X("v"))),
              (0, OP("vec_get", node=X("v"), i=1))], kinds=["term", "dbapi"]),
        # --- $ZSTRIP character classes
        case("zstrip-class-c", "$ZSTRIP class C over 0..65535", 1, [(0, OP("z_class", **{"class": "C"}))], kinds=["term"]),
        case("zstrip-class-w", "$ZSTRIP class W over 0..65535", 1, [(0, OP("z_class", **{"class": "W"}))], kinds=["term"]),
        case("zstrip-product-masks", "the masks the product uses", 1,
             [(0, OP("z_strip", s=s, mask=m, rem=r)) for s, m, r in [
                 ([97, 1, 98, 127, 99, 133, 100, 160], "*C", ""),
                 ([32, 9, 97, 32, 32, 98, 10, 32], "<>W", ""),
                 ([32, 32, 97, 32, 32, 32, 98, 9, 9, 99, 32], "<=>W", ""),
                 ([32, 9, 97, 32], "<W", ""),
                 ([32, 97, 9, 98, 160, 99], "*W", ""),
                 ([48, 48, 49, 48, 50, 48], "<", "0"),
                 ([49, 48, 50, 48, 48], ">", "0")]], kinds=["term"]),
        # --- $ORDER collation
        case("order-collation", "$ORDER: canonical numbers first, numerically; then strings", 2,
             [(0, OP("set", node=X("c", s), value="v")) for s in
              ["10", "9", "-1", "-.5", ".5", "1.0", "01", "a", "B", " ", "1E2", "+1", "-0", "0", "1.50", "0.5", "Z", "2a",
               "123456789012345678", "-3.25", "1234567890123456789", "9223372036854775807", "9223372036854775808",
               "-9223372036854775808", "-9223372036854775809", "100000000000000000000", "12345678901234567890",
               "1" * 40, "9" * 39, "-" + "9" * 40, "." + "1" * 39]]
             + [(0, OP("order", node=X("c"))), (1, OP("order", node=X("c")))], kinds=["dbapi", "term"]),
    ]
    return out


WORDS = ["apple", "pear", "fig"]


def rand_fx(rng: random.Random, i: int, seed: int = 0) -> Dict:
    """Two processes writing F (functional index on v) in and out of transactions, %NOINDEX inserts, finds from
    both sides, BUILD INDEX only when no transaction is open. Keys written %NOINDEX are not written again by key
    until a BUILD INDEX (by-key access to an unindexed row is outside the subset)."""
    steps = []
    open_ = {0: False, 1: False}
    unindexed = set()
    for _ in range(rng.randint(5, 10)):
        p = rng.randint(0, 1)
        r = rng.random()
        k = str(rng.randint(1, 3))
        w = rng.choice(WORDS)
        if r < 0.45 and k not in unindexed:
            noidx = rng.random() < 0.25
            op = rng.choice([ins(F, k, w, noindex=True) if noidx else ins(F, k, w), OP("delete", table=F, k=k),
                             OP("update", table=F, k=k, v=w)])
            if op["op"] == "insert" and op.get("noindex"):
                unindexed.add(k)
            steps.append((p, op))
            if open_[1 - p]:
                steps.append((1 - p, OP(rng.choice(["t_commit", "t_rollback"]))))
                open_[1 - p] = False
                steps.append((p, OP("await")))
        elif r < 0.65:
            steps.append((rng.randint(0, 1), find(rng.choice(WORDS))))
        elif r < 0.80 and not open_[p]:
            steps.append((p, OP("t_start")))
            open_[p] = True
        elif r < 0.88 and not open_[0] and not open_[1]:
            steps.append((p, OP("build_index", table=F)))
            unindexed.clear()
        elif open_[p]:
            steps.append((p, OP(rng.choice(["t_commit", "t_rollback", "t_rollback_one"]))))
            open_[p] = False
    for p in (0, 1):
        if open_[p]:
            steps.append((p, OP("t_commit")))
    for w in WORDS:
        steps.append((rng.randint(0, 1), find(w)))
    steps.append((0, OP("select", table=F)))
    kinds = rng.choice([["dbapi", "dbapi"], ["term", "dbapi"], ["dbapi", "term"]])
    return case(f"rand-fx-{seed}-{i}", "functional index in the row's transaction (random)", 2, steps, kinds=kinds)


def rand_ddl(rng: random.Random, i: int, seed: int = 0) -> Dict:
    """One process: DDL on D1/D2 mixed with row and global writes and every transaction verb. The generator follows
    the transaction levels (SQL START TRANSACTION opens one only at level 0; SQL COMMIT / ROLLBACK end one) so that a
    table whose CREATE a rollback undid is never used again (outside the subset): only TableExists asks about it."""
    steps = []
    n = 0
    stack: List[set] = []  # tables created at each open level
    ghosts: set = set()

    def end(commit: bool, levels: int) -> None:
        for _ in range(min(levels, len(stack))):
            top = stack.pop()
            if commit:
                if stack:
                    stack[-1] |= top
            else:
                ghosts.update(top)

    for _ in range(rng.randint(6, 12)):
        r = rng.random()
        live = [t for t in ("D1", "D2") if t not in ghosts]
        t = rng.choice(live) if live else None
        if r < 0.18 and t:
            steps.append((0, OP("create_table", table=t)))
            if stack:
                stack[-1].add(t)
        elif r < 0.28 and t:
            steps.append((0, OP("drop_table", table=t)))
        elif r < 0.43:
            n += 1
            steps.append((0, ins(rng.choice(live + ["T"]), str(n), "r")))
        elif r < 0.50:
            steps.append((0, OP("set", node=X(str(rng.randint(1, 2))), value=str(len(steps)))))
        elif r < 0.62:
            steps.append((0, OP("t_start")))
            stack.append(set())
        elif r < 0.70:
            v = rng.choice(["t_commit", "t_rollback", "t_rollback_one"])
            steps.append((0, OP(v)))
            end(v == "t_commit", len(stack) if v == "t_rollback" else 1)
        elif r < 0.78:
            v = rng.choice(["sql_start", "sql_commit", "sql_rollback"])
            steps.append((0, OP(v)))
            if v == "sql_start":
                if not stack:
                    stack.append(set())
            else:
                end(v == "sql_commit", 1)
        elif r < 0.88:
            steps.append((0, OP("table_exists", table=rng.choice(["D1", "D2"]))))
        elif t:
            steps.append((0, OP("select", table=t)))
        steps.append((0, TL))
    steps.append((0, OP("t_rollback")))
    end(False, len(stack))
    for t in ("D1", "D2"):
        steps.append((0, OP("table_exists", table=t)))
        if t not in ghosts:
            steps.append((0, OP("select", table=t)))
    kinds = [rng.choice(["dbapi", "dbapi", "term"])]
    return case(f"rand-ddl-{seed}-{i}", "DDL and transactions (random)", 1, steps,
                observe=[X("1"), X("2")], tables=True, kinds=kinds)


def rand_enc(rng: random.Random, i: int, seed: int = 0) -> Dict:
    """Writes of NULL / '' / $Char(0) / text to E on either client path, read on both."""
    steps = []
    kinds = [rng.choice(["dbapi", "term"]), rng.choice(["dbapi", "term"])]
    for j in range(rng.randint(3, 6)):
        p = rng.randint(0, 1)
        k = str(j + 1)
        v = rng.choice([None, "", "\u0000", "x", "ab"])
        literal = v != "\u0000" and rng.random() < 0.4
        steps.append((p, OP("put_e", k=k, v=v, literal=literal) if literal else OP("put_e", k=k, v=v)))
        if rng.random() < 0.5:
            steps.append((rng.randint(0, 1), OP("get_e", k=k)))
    for j in range(len([s for s in steps if s[1]["op"] == "put_e"])):
        for p in (0, 1):
            steps.append((p, OP("get_e", k=str(j + 1))))
    for p in (0, 1):
        steps.append((p, OP("match_e", v=rng.choice([None, "", "\u0000", "x"]))))
    return case(f"rand-enc-{seed}-{i}", "NULL and empty string encodings (random)", 2, steps, kinds=kinds)


def _rand_sub(rng: random.Random) -> str:
    r = rng.random()
    if r < 0.3:
        return str(rng.randint(-50, 200))
    if r < 0.5:  # canonical decimals: no leading 0, no trailing 0
        whole = "" if rng.random() < 0.5 else str(rng.randint(1, 30))
        return rng.choice(["", "-"]) + whole + "." + rng.choice(["5", "25", "75", "125"])
    if r < 0.6:
        return rng.choice(["01", "1.0", "+1", "-0", "1E2", "00", "0.5", "-0.5", "1.50", "2a", "1e3", " 1"])
    if r < 0.7:  # long canonical numbers, past the 64-bit range (explore-7)
        return rng.choice(["", "-"]) + str(rng.randint(1, 9)) + "".join(rng.choice("0123456789")
                                                                          for _ in range(rng.randint(15, 28)))
    return "".join(rng.choice("abAB z_") for _ in range(rng.randint(1, 3)))


def rand_order(rng: random.Random, i: int, seed: int = 0) -> Dict:
    steps = []
    subs = [_rand_sub(rng) for _ in range(rng.randint(4, 10))]
    for s in subs:
        steps.append((0, OP("set", node=X("o", s), value="1")))
    if rng.random() < 0.5:
        steps.append((0, OP("kill", node=X("o", rng.choice(subs)))))
    steps.append((0, OP("order", node=X("o"))))
    kinds = [rng.choice(["dbapi", "term"])]
    return case(f"rand-order-{seed}-{i}", "$ORDER collation (random)", 1, steps, kinds=kinds)


ZPOOL = [0, 1, 9, 10, 11, 13, 31, 32, 48, 49, 65, 97, 127, 128, 133, 159, 160, 0x2000, 0x2028, 0x3000, 0xFEFF, 0x200B]
ZMASKS = [("*C", ""), ("*W", ""), ("<W", ""), (">W", ""), ("<>W", ""), ("<=>W", ""), ("<", "0"), (">", "0"),
          ("*", "0"), ("<>C", ""), ("=W", "")]


def rand_zstrip(rng: random.Random, i: int, seed: int = 0) -> Dict:
    steps = []
    for _ in range(rng.randint(3, 6)):
        s = [rng.choice(ZPOOL) for _ in range(rng.randint(1, 8))]
        m, r = rng.choice(ZMASKS)
        steps.append((0, OP("z_strip", s=s, mask=m, rem=r)))
    return case(f"rand-zstrip-{seed}-{i}", "$ZSTRIP (random)", 1, steps, kinds=["term"])


def rand_stmt(rng: random.Random, i: int, seed: int = 0) -> Dict:
    """One process: source rows in S (inserted in key order), rows in T, INSERT ... SELECT in and out of
    transactions."""
    steps = []
    kinds = [rng.choice(["dbapi", "dbapi", "term"])]
    src = sorted(rng.sample(["1", "2", "3", "4"], rng.randint(1, 3)))
    for k in src:
        steps.append((0, ins("S", k, "s" + k)))
    autocommit_off = kinds == ["dbapi"] and rng.random() < 0.4
    if autocommit_off:
        steps.append((0, OP("set_autocommit", on=False)))
    for _ in range(rng.randint(3, 7)):
        r = rng.random()
        if r < 0.25:
            k = rng.choice(["1", "2", "3", "4", "9"])
            steps.append((0, ins("T", k, "t" + k)))
        elif r < 0.45:
            steps.append((0, OP("insert_select", **{"from": "S", "to": "T"})))
        elif r < 0.60:
            steps.append((0, OP("t_start")))
        elif r < 0.75:
            steps.append((0, OP(rng.choice(["t_commit", "t_rollback", "t_rollback_one"]))))
        elif r < 0.85:
            steps.append((0, OP("delete", table="T", k=rng.choice(src + ["8"]))))
        else:
            steps.append((0, OP("select", table="T")))
        steps.append((0, TL))
    if autocommit_off:
        steps.append((0, OP("drv_commit")))
        steps.append((0, TL))
        steps.append((0, OP("set_autocommit", on=True)))
    steps.append((0, OP("t_commit")))
    return case(f"rand-stmt-{seed}-{i}", "statement atomicity (random)", 1, steps, tables=True, kinds=kinds)


def main() -> int:
    out = sys.argv[1]
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 20261113
    k = int(sys.argv[sys.argv.index("--random-per-family") + 1]) if "--random-per-family" in sys.argv else 60
    k2 = int(sys.argv[sys.argv.index("--ext-per-family") + 1]) if "--ext-per-family" in sys.argv else 30
    rng = random.Random(seed)
    cases = named()
    cases += [rand_txn_controller(rng, i, seed) for i in range(k)]
    cases += [rand_locks(rng, i, seed) for i in range(k)]
    cases += [rand_visibility(rng, i, seed) for i in range(k)]
    cases += [rand_rows(rng, i, seed) for i in range(k)]
    if "--no-ext" not in sys.argv:
        cases += named_ext()
        cases += [rand_fx(rng, i, seed) for i in range(k2)]
        cases += [rand_ddl(rng, i, seed) for i in range(k2)]
        cases += [rand_enc(rng, i, seed) for i in range(k2)]
        cases += [rand_order(rng, i, seed) for i in range(k2)]
        cases += [rand_zstrip(rng, i, seed) for i in range(k2)]
        cases += [rand_stmt(rng, i, seed) for i in range(k2)]
    with open(out, "w") as f:
        json.dump(cases, f, indent=1)
    print(f"{len(cases)} cases (seed {seed}, {k} per random family)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
