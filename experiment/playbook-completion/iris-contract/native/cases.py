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


def main() -> int:
    out = sys.argv[1]
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 20261113
    k = int(sys.argv[sys.argv.index("--random-per-family") + 1]) if "--random-per-family" in sys.argv else 60
    rng = random.Random(seed)
    cases = named()
    cases += [rand_txn_controller(rng, i, seed) for i in range(k)]
    cases += [rand_locks(rng, i, seed) for i in range(k)]
    cases += [rand_visibility(rng, i, seed) for i in range(k)]
    cases += [rand_rows(rng, i, seed) for i in range(k)]
    with open(out, "w") as f:
        json.dump(cases, f, indent=1)
    print(f"{len(cases)} cases (seed {seed}, {k} per random family)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
