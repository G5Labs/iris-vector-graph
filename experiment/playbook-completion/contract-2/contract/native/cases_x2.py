#!/usr/bin/env python3
"""contract-2 round env2-r1 cases (X2-JSON, X2-LIST, X2-TOP, X2-BATCH, X2-IOU, X2-QUERY, X2-MERGE).

    python cases_x2.py out.json [--seed N] [--random K]

Named cases: one or more per clause, each sharp against the clause's mutants (the plausible alternative readings,
src/lib.rs `mutants()`). Seeded random families per clause. Roots: ^X (-> ^IVGAuditEnv), table T (-> IVGAudit.T).
"""
from __future__ import annotations

import json
import random
import sys
from typing import Dict, List

OP = lambda name, **kw: {"op": name, **kw}  # noqa: E731
TL = OP("t_level")
X = lambda *s: {"root": "^X", "subs": list(s)}  # noqa: E731


def U(s: str) -> List[int]:
    return [ord(c) for c in s]


def case(cid, clause, procs, steps, kinds=None, tables=False, observe=()):
    c = {"id": cid, "clause": clause, "procs": procs, "steps": [[p, o] for p, o in steps], "observe": list(observe),
         "observe_tables": ["T"] if tables else []}
    if kinds:
        c["kinds"] = kinds
    return c


def jb(*sets):
    return OP("json_build", sets=[[U(k), v, t] for k, v, t in sets])


def jr(text, remove=None):
    d = {"op": "json_roundtrip", "text": U(text)}
    if remove is not None:
        d["remove"] = U(remove)
    return d


def jg(text, key):
    return OP("json_get", text=U(text), key=U(key))


def el(k, t=None):
    return None if k == "u" else [k, t]


def le(elems, what):
    return OP("list_eval", elems=elems, what=what)


TERM = ["term"]
LST = [el("s", "a"), el("i", "1"), el("u"), el("d", "2.5"), el("s", "")]


def ins(k, v="v", t="T"):
    return OP("insert", table=t, k=k, v=v)


def top(n, order="asc", form="top", offset=0):
    return OP("select_top", table="T", n=n, order=order, form=form, offset=offset)


def named() -> List[Dict]:
    keys = ["1", "10", "2", "3", "9", "a", "B", "c"]
    setup_t = [(0, ins(k, "v" + k)) for k in keys]
    q = [(0, OP("set", node=X("a", "1"), value="1")), (0, OP("set", node=X("a", "1", "x"), value="2")),
         (0, OP("set", node=X("a", "2"), value="3")), (0, OP("set", node=X("a", "10"), value="5")),
         (0, OP("set", node=X("a", "b"), value="6")), (0, OP("set", node=X("b"), value="4"))]
    return [
        # ---- X2-JSON
        case("x2-json-order", "X2-JSON: %ToJSON keeps insertion order", 1,
             [(0, jb(("b", "2", "number"), ("a", "1", "number"), ("c", "3", "number")))], TERM),
        case("x2-json-reset-keeps-place", "X2-JSON: a re-%Set keeps the key's place", 1,
             [(0, jb(("b", "2", "number"), ("a", "1", "number"), ("b", "5", "number")))], TERM),
        case("x2-json-number-form", "X2-JSON: numbers set from ObjectScript are canonical with a leading zero; booleans true/false", 1,
             [(0, jb(("temporal", "1", "boolean"), ("weight", ".5", "number"), ("x", "-.25", "number"),
                     ("y", "1E-7", "number"), ("z", "2.0", "number"), ("n", "007", "number"), ("f", "0", "boolean")))], TERM),
        case("x2-json-marker", "X2-JSON: AssertTemporalRow's qualifiers start with {\"temporal\":true (Adjacency.cls:585-590, 661)", 1,
             [(0, jb(("temporal", "1", "boolean"))), (0, jb(("temporal", "1", "boolean"), ("weight", "+.5", "number")))], TERM),
        case("x2-json-dup", "X2-JSON: a duplicate key in parsed text: last value at the first key's place", 1,
             [(0, jr('{"b":1,"a":2,"b":3}'))], TERM),
        case("x2-json-number-text", "X2-JSON: a parsed number keeps its JSON text", 1,
             [(0, jr('{"x":1.50,"y":1e2,"z":-0.0,"u":2.0,"w":12345678901234567}'))], TERM),
        case("x2-json-pydumps", "X2-JSON: Python json.dumps text (spaces, 2.0) re-serialised compactly, number text kept", 1,
             [(0, jr('{"temporal": true, "weight": 2.0}'))], TERM),
        case("x2-json-escapes", "X2-JSON: escapes for \", \\ and controls; / DEL and non-ASCII raw", 1,
             [(0, jb(("s", "\x01e/\n\"\\\t\x7fé€\x08\x0c\r\x1f", "string")))], TERM),
        case("x2-json-escapes-parse", "X2-JSON: \\/ and \\u escapes parsed, re-escaped by the rules", 1,
             [(0, jr('{"s":"a\\u0001b\\nc\\/d\\u00e9"}'))], TERM),
        case("x2-json-get", "X2-JSON: %Get / %GetTypeOf / %IsDefined of null, boolean, number, string, missing", 1,
             [(0, jg('{"n":null,"t":true,"s":"1","i":1.50}', k)) for k in ("n", "t", "s", "i", "missing")], TERM),
        case("x2-json-remove", "X2-JSON: %Remove keeps the other keys' order", 1,
             [(0, jr('{"z":1,"a":2,"m":3}', remove="a"))], TERM),
        case("x2-json-invalid", "X2-JSON: invalid text throws", 1, [(0, jr('{"a":1,')), (0, jg('[1,', "a"))], TERM),
        case("x2-json-null-set", "X2-JSON: %Set with type null; $Char(0) escaped", 1,
             [(0, jb(("k", "", "null"), ("j", "\x00", "string"), ("e", "", "string")))], TERM),
        # ---- X2-LIST
        case("x2-list-get", "X2-LIST: $LISTGET default only for undefined or missing elements; $LISTDATA", 1,
             [(0, le(LST, w)) for w in ("len", "data:3", "get:3:d", "get:5:d", "get:9", "data:5")], TERM),
        case("x2-list-item", "X2-LIST: $LIST of an undefined or missing element is <NULL VALUE>", 1,
             [(0, le(LST, "item:3")), (0, le(LST, "item:9")), (0, le(LST, "item:4"))], TERM),
        case("x2-list-walk", "X2-LIST: $LISTNEXT visits undefined elements", 1,
             [(0, le(LST, "walk")), (0, le([el("u")], "walk")), (0, le([el("u"), el("u")], "len"))], TERM),
        case("x2-list-find", "X2-LIST: $LISTFIND compares values as strings, from after `start`", 1,
             [(0, le([el("s", "a"), el("s", "b"), el("s", "a")], "find:a:1")), (0, le([el("i", "1")], "find:1:0")),
              (0, le([el("s", "a"), el("s", "b")], "find:z:0"))], TERM),
        case("x2-list-same", "X2-LIST: $LISTSAME compares values; = compares encodings", 1,
             [(0, OP("list_same", a=[el("i", "1")], b=[el("s", "1")])), (0, OP("list_same", a=[el("s", "01")], b=[el("i", "1")])),
              (0, OP("list_same", a=[el("u")], b=[el("s", "")]))], TERM),
        case("x2-list-tostring", "X2-LIST: $LISTTOSTRING of an undefined element is <NULL VALUE> unless flag 1", 1,
             [(0, le([el("s", "a"), el("u"), el("s", "c")], "tostring:,:0")),
              (0, le([el("s", "a"), el("u"), el("s", "c")], "tostring:,:1")),
              (0, le([el("s", "a"), el("s", "b,c")], "tostring:,:0"))], TERM),
        case("x2-list-fromstring", "X2-LIST: $LISTFROMSTRING keeps empty fields as defined empty strings", 1,
             [(0, OP("list_fromstring", s="a,b,,c", d=","))], TERM),
        case("x2-list-native", "X2-LIST: the driver's IRISList decodes integers as int, decimals as Decimal, strings as str", 2,
             [(0, OP("list_store", elems=[el("s", "a"), el("i", "1"), el("u"), el("d", "2.5"), el("s", ""),
                                         el("i", "-3"), el("d", "-.25"), el("s", "1"), el("i", "256")])),
              (1, OP("list_native"))], ["term", "dbapi"]),
        # ---- X2-TOP
        case("x2-top-asc", "X2-TOP: TOP n of ORDER BY k (default collation: SQLUPPER string order)", 1,
             setup_t + [(0, top(3)), (0, top(2, "desc")), (0, top(4, "exact"))]),
        case("x2-top-zero", "X2-TOP: TOP 0 returns no row", 1, setup_t + [(0, top(0))]),
        case("x2-limit", "X2-TOP: LIMIT n and LIMIT n OFFSET m", 1,
             setup_t + [(0, top(2, form="limit")), (0, top(2, form="limit_offset", offset=1)),
                        (0, top(3, form="limit_offset", offset=6))]),
        case("x2-top-dirty", "X2-TOP, E-VIS: TOP reads another process's uncommitted row", 2,
             setup_t[:3] + [(1, OP("t_start")), (1, ins("0")), (0, top(2)), (1, OP("t_rollback")), (0, top(2))]),
        case("x2-top-none", "X2-TOP: TOP without ORDER BY returns some n rows", 1,
             setup_t[:4] + [(0, top(2, "none"))]),
        # ---- X2-BATCH
        case("x2-batch-dup-skipped", "X2-BATCH: executemany skips a refused row of several without raising", 1,
             [(0, OP("insert_many", table="T", rows=[["1", "a"], ["2", "b"], ["1", "c"], ["3", "d"]])), (0, TL),
              (0, OP("select", table="T"))], tables=True),
        case("x2-batch-single-raises", "X2-BATCH: executemany of one refused row raises (-119)", 1,
             [(0, ins("1")), (0, OP("insert_many", table="T", rows=[["1", "x"]]))], tables=True),
        case("x2-batch-in-txn", "X2-BATCH: executemany rows are the transaction's; rollback undoes them", 1,
             [(0, OP("t_start")), (0, OP("insert_many", table="T", rows=[["1", "a"], ["2", "b"]])), (0, OP("t_rollback"))],
             tables=True),
        case("x2-batch-autocommit-off", "X2-BATCH, E-AUTOCOMMIT: with autocommit off executemany opens the level", 1,
             [(0, OP("set_autocommit", on=False)), (0, OP("insert_many", table="T", rows=[["1", "a"], ["1", "b"]])), (0, TL),
              (0, OP("drv_rollback")), (0, TL), (0, OP("set_autocommit", on=True))], tables=True),
        case("x2-batch-rowlock", "X2-BATCH, E-ROWLOCK: each executemany row holds its row lock", 2,
             [(0, OP("t_start")), (0, OP("insert_many", table="T", rows=[["1", "a"], ["2", "b"]])),
              (1, OP("delete", table="T", k="2")), (0, OP("t_rollback")), (1, OP("await"))], tables=True),
        # ---- X2-IOU
        case("x2-iou-insert-update", "X2-IOU: INSERT OR UPDATE inserts an absent key, updates a present one", 1,
             [(0, OP("upsert", table="T", k="1", v="a")), (0, OP("upsert", table="T", k="1", v="b"))], tables=True),
        case("x2-iou-waits-insert-rb", "X2-IOU: an upsert waits for a row another inserted; after its rollback fails -109", 2,
             [(0, OP("t_start")), (0, ins("2", "x")), (1, OP("upsert", table="T", k="2", v="y")), (0, OP("t_rollback")),
              (1, OP("await"))], tables=True),
        case("x2-iou-waits-update-commit", "X2-IOU: an upsert waits for an uncommitted update, then updates", 2,
             [(0, ins("1", "a")), (0, OP("t_start")), (0, OP("update", table="T", k="1", v="z")),
              (1, OP("upsert", table="T", k="1", v="w")), (0, OP("t_commit")), (1, OP("await"))], tables=True),
        case("x2-iou-rollback", "X2-IOU: upserts in a transaction are seen dirty and undone by rollback", 2,
             [(0, ins("1", "w")), (1, OP("t_start")), (1, OP("upsert", table="T", k="1", v="q")),
              (1, OP("upsert", table="T", k="5", v="q")), (0, OP("select", table="T")), (1, OP("t_rollback"))], tables=True),
        # ---- X2-QUERY / X2-MERGE
        case("x2-query-walk", "X2-QUERY: $QUERY walks data nodes depth-first in $ORDER collation", 1,
             q + [(0, OP("query_walk", node=X()))], TERM),
        case("x2-query-back", "X2-QUERY: $QUERY(ref, -1) is the previous data node", 1,
             q + [(0, OP("query_back", node=X("b"))), (0, OP("query_back", node=X("a", "10"))),
                  (0, OP("query_back", node=X("a", "1")))], TERM),
        case("x2-merge-rollback", "X2-MERGE: MERGE copies the subtree and a rollback undoes it", 1,
             q + [(0, OP("t_start")), (0, OP("merge", to=X("c"), **{"from": X("a")})), (0, OP("data", node=X("c", "1", "x"))),
                  (0, OP("t_rollback")), (0, OP("data", node=X("c")))], TERM),
        case("x2-merge-onto", "X2-MERGE: MERGE onto an existing subtree overwrites matching nodes and keeps the others", 1,
             q + [(0, OP("set", node=X("d", "1"), value="old")), (0, OP("set", node=X("d", "9"), value="keep")),
                  (0, OP("merge", to=X("d"), **{"from": X("a")})), (0, OP("get", node=X("d", "1"))),
                  (0, OP("get", node=X("d", "9"))), (0, OP("data", node=X("d", "1", "x")))], TERM),
        case("x2-zkill", "X2-MERGE: ZKILL removes the node's value only; a rollback restores it", 1,
             q + [(0, OP("t_start")), (0, OP("zkill", node=X("a", "1"))), (0, OP("data", node=X("a", "1"))),
                  (0, OP("t_rollback")), (0, OP("data", node=X("a", "1"))), (0, OP("get", node=X("a", "1")))], TERM),
    ]


# ------------------------------------------------------------------------------------------------ random families
JKEYS = ["a", "b", "c", "k", "é", "a b"]
JNUMS = [".5", "-.25", "2.0", "007", "1E-7", "123", "0", "-0", "1E3", "1.5E1", "-12.75"]
JCHARS = ["a", "b", "/", "\x01", "\n", "\"", "\\", "\t", "é", "€", "\x7f", " ", "\x00", "\x1f"]
JTEXTNUMS = ["1.50", "1e2", "-0.0", "2.0", "0.1", "7", "-3", "1E-2", "10"]


def rand_json(rng, i, seed):
    steps = []
    for _ in range(rng.randint(2, 4)):
        r = rng.random()
        if r < 0.45:
            sets = []
            for _ in range(rng.randint(1, 5)):
                t = rng.choice(["number", "number", "string", "boolean", "null"])
                v = {"number": lambda: rng.choice(JNUMS), "string": lambda: "".join(rng.choice(JCHARS) for _ in range(rng.randint(0, 4))),
                     "boolean": lambda: rng.choice(["1", "0", "2", ""]), "null": lambda: ""}[t]()
                sets.append((rng.choice(JKEYS), v, t))
            steps.append((0, jb(*sets)))
        else:
            parts = []
            ks = [rng.choice(JKEYS) for _ in range(rng.randint(1, 4))]
            for k in ks:
                vt = rng.random()
                if vt < 0.4:
                    v = rng.choice(JTEXTNUMS)
                elif vt < 0.6:
                    v = json.dumps("".join(rng.choice(JCHARS) for _ in range(rng.randint(0, 3))), ensure_ascii=rng.random() < 0.5)
                elif vt < 0.8:
                    v = rng.choice(["true", "false", "null", "[1,2.50,null]", "{}"])
                else:
                    v = '{"x":' + rng.choice(JTEXTNUMS) + "}"
                parts.append(json.dumps(k, ensure_ascii=rng.random() < 0.5) + rng.choice([":", ": "]) + v)
            text = "{" + rng.choice([",", ", "]).join(parts) + "}"
            if rng.random() < 0.1:
                text = text[:-1]  # invalid
            if rng.random() < 0.5:
                steps.append((0, jr(text, remove=rng.choice(ks) if rng.random() < 0.3 else None)))
            else:
                steps.append((0, jg(text, rng.choice(ks + ["missing"]))))
    return case(f"rand-json-{seed}-{i}", "X2-JSON (random)", 1, steps, TERM)


LPOOL = [("s", "a"), ("s", "b"), ("s", ""), ("s", "1"), ("i", "1"), ("i", "-3"), ("i", "256"), ("i", "0"),
         ("d", "2.5"), ("d", "-.25"), ("d", ".5"), ("u", None)]


def rand_list(rng, i, seed):
    steps = []
    for _ in range(rng.randint(2, 5)):
        elems = [el(*rng.choice(LPOOL)) if True else None for _ in range(rng.randint(1, 5))]
        n = len(elems)
        w = rng.choice(["len", f"data:{rng.randint(1, n + 1)}", f"get:{rng.randint(1, n + 1)}:d", f"item:{rng.randint(1, n + 1)}",
                        "walk", f"find:{rng.choice(['a', 'b', '1', '', '2.5'])}:{rng.randint(0, 2)}", "tostring:,:0", "tostring:,:1"])
        if w.startswith("find::"):
            w = "find:a:0"
        r = rng.random()
        if r < 0.75:
            steps.append((0, le(elems, w)))
        elif r < 0.9:
            steps.append((0, OP("list_same", a=elems, b=[el(*rng.choice(LPOOL)) for _ in range(n)])))
        else:
            steps.append((0, OP("list_fromstring", s=rng.choice(["a,b", "a,,b", ",", "x", "a,b,"]), d=",")))
    kinds = TERM
    if rng.random() < 0.4:
        elems = [el(*rng.choice(LPOOL)) for _ in range(rng.randint(1, 5))]
        steps += [(0, OP("list_store", elems=elems)), (1, OP("list_native"))]
        return case(f"rand-list-{seed}-{i}", "X2-LIST (random)", 2, steps, ["term", "dbapi"])
    return case(f"rand-list-{seed}-{i}", "X2-LIST (random)", 1, steps, kinds)


TPOOL = ["1", "10", "2", "3", "9", "a", "B", "c", "D", "05"]


def rand_top(rng, i, seed):
    steps = [(0, ins(k, "v" + k)) for k in rng.sample(TPOOL, rng.randint(2, 7))]
    dirty = rng.random() < 0.4
    if dirty:
        steps += [(1, OP("t_start")), (1, ins(rng.choice(["0", "Z", "4"]), "d"))]
    for _ in range(rng.randint(1, 3)):
        form = rng.choice(["top", "top", "limit", "limit_offset"])
        order = rng.choice(["asc", "desc", "exact"]) if form == "top" else "asc"
        steps.append((0, top(rng.randint(0 if form == "top" else 1, 4), order, form, rng.randint(0, 3))))
    if dirty:
        steps += [(1, OP(rng.choice(["t_rollback", "t_commit"]))), (0, top(3))]
    return case(f"rand-top-{seed}-{i}", "X2-TOP (random)", 2, steps)


def rand_batch(rng, i, seed):
    steps = []
    if rng.random() < 0.5:
        steps.append((0, ins(rng.choice(["1", "2", "3"]))))
    txn = rng.random() < 0.4
    if txn:
        steps.append((0, OP("t_start")))
    for _ in range(rng.randint(1, 3)):
        rows = [[rng.choice(["1", "2", "3", "4"]), rng.choice(["a", "b"])] for _ in range(rng.randint(1, 4))]
        steps.append((0, OP("insert_many", table="T", rows=rows)))
    if txn:
        steps += [(0, TL), (0, OP(rng.choice(["t_commit", "t_rollback"])))]
    steps.append((0, OP("select", table="T")))
    return case(f"rand-batch-{seed}-{i}", "X2-BATCH (random)", 1, steps, tables=True)


def rand_iou(rng, i, seed):
    steps = []
    open_ = {0: False, 1: False}
    for _ in range(rng.randint(4, 8)):
        p = rng.randint(0, 1)
        r = rng.random()
        k = rng.choice(["1", "2"])
        if r < 0.55:
            op = rng.choice([OP("upsert", table="T", k=k, v=f"u{p}"), OP("upsert", table="T", k=k, v=f"w{p}"), ins(k, f"i{p}"),
                             OP("update", table="T", k=k, v=f"x{p}")])
            steps.append((p, op))
            if open_[1 - p]:
                steps.append((1 - p, OP(rng.choice(["t_commit", "t_rollback"]))))
                open_[1 - p] = False
                steps.append((p, OP("await")))
        elif r < 0.8 and not open_[p]:
            steps.append((p, OP("t_start")))
            open_[p] = True
        elif open_[p]:
            steps.append((p, OP(rng.choice(["t_commit", "t_rollback"]))))
            open_[p] = False
    for p in (0, 1):
        if open_[p]:
            steps.append((p, OP("t_commit")))
    return case(f"rand-iou-{seed}-{i}", "X2-IOU (random)", 2, steps, tables=True)


GSUBS = [("a",), ("a", "1"), ("a", "2"), ("a", "10"), ("a", "1", "x"), ("b",), ("a", "b"), ("c", "1"), ("-1",), ("1.5",)]


def rand_glob(rng, i, seed):
    steps = []
    for j, s in enumerate(rng.sample(GSUBS, rng.randint(3, 7))):
        steps.append((0, OP("set", node=X(*s), value=str(j))))
    txn = rng.random() < 0.6
    if txn:
        steps.append((0, OP("t_start")))
    for _ in range(rng.randint(1, 3)):
        r = rng.random()
        if r < 0.4:
            steps.append((0, OP("merge", to=X(rng.choice(["d", "e"])), **{"from": X(rng.choice(["a", "b", "c"]))})))
        elif r < 0.7:
            steps.append((0, OP("zkill", node=X(*rng.choice(GSUBS)))))
        else:
            steps.append((0, OP("query_back", node=X(*rng.choice(GSUBS)))))
    steps.append((0, OP("query_walk", node=X())))
    if txn:
        steps += [(0, OP(rng.choice(["t_rollback", "t_commit"]))), (0, OP("query_walk", node=X()))]
    return case(f"rand-glob-{seed}-{i}", "X2-QUERY / X2-MERGE (random)", 1, steps, TERM)


def main() -> int:
    out = sys.argv[1]
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 1
    k = int(sys.argv[sys.argv.index("--random") + 1]) if "--random" in sys.argv else 20
    rng = random.Random(seed)
    cases = named()
    for fam in (rand_json, rand_list, rand_top, rand_batch, rand_iou, rand_glob):
        cases += [fam(rng, i, seed) for i in range(k)]
    with open(out, "w") as f:
        json.dump(cases, f, indent=1)
    print(len(cases), "cases", "seed", seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
