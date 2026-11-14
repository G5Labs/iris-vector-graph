#!/usr/bin/env python3
"""The autocommit-off DML cases of cases.py's 'autocommit-off-failed-dml' without its INSERT ... SELECT steps, so a
model that leaves INSERT ... SELECT out (proofs-env's Verus subset) can be checked against them: with autocommit off a
failing single-row INSERT opens the transaction; a DELETE or UPDATE that finds no row does not.

    python dml_single_cases.py OUT_CASES_JSON
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cases import OP, TL, case  # noqa: E402

ins = lambda t, k, v: OP("insert", table=t, k=k, v=v)  # noqa: E731


def cases():
    return [
        case("autocommit-off-failed-dml-single-row", "with autocommit off a failing single-row INSERT opens the transaction; "
             "a DML that finds no row does not", 1,
             [(0, ins("T", "1", "a")), (0, OP("set_autocommit", on=False)), (0, TL),
              (0, OP("delete", table="T", k="9")), (0, TL), (0, OP("update", table="T", k="9", v="z")), (0, TL),
              (0, ins("T", "1", "b")), (0, TL), (0, OP("drv_rollback")), (0, TL), (0, OP("set_autocommit", on=True))],
             tables=True),
        case("autocommit-off-empty-dml-only", "with autocommit off a DELETE and an UPDATE that find no row open no transaction", 1,
             [(0, ins("T", "1", "a")), (0, OP("set_autocommit", on=False)), (0, OP("delete", table="T", k="9")), (0, TL),
              (0, OP("update", table="T", k="9", v="z")), (0, TL), (0, OP("set_autocommit", on=True))], tables=True),
    ]


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(cases(), indent=1))
    print(len(cases()), "cases")
