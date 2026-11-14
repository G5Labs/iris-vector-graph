#!/usr/bin/env python3
"""E-STOP gap found by the proofs-env lane (D-7): no recorded round stops a process with two OPEN levels (the one nested
case commits its inner level first). These cases do; built with cases.py's own helpers, observed by driver.py and
checked by the executable contract like every round. The contract (E-STOP) permits only 'every level rolled back'.

    python estop_gap_cases.py OUT_CASES_JSON
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cases import OP, X, case  # noqa: E402


def cases():
    a, b = X("a"), X("b")
    return [
        case("stop-two-open-levels", "a stop with two open levels rolls back both", 2,
             [(0, OP("t_start")), (0, OP("set", node=a, value="1")), (0, OP("t_start")), (0, OP("set", node=b, value="2")),
              (1, OP("terminate", target=0))], observe=[a, b]),
        case("stop-two-open-levels-outer-write-only", "a stop at level 2 rolls back the outer level's write", 2,
             [(0, OP("t_start")), (0, OP("set", node=a, value="1")), (0, OP("t_start")),
              (1, OP("terminate", target=0))], observe=[a]),
        case("stop-two-open-levels-table", "a stop at level 2 rolls back an outer-level row insert", 2,
             [(0, OP("t_start")), (0, OP("insert", table="T", k="1", v="a")), (0, OP("t_start")),
              (0, OP("set", node=b, value="2")), (1, OP("terminate", target=0))], observe=[b], tables=True),
    ]


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(cases(), indent=1))
    print(len(cases()), "cases")
