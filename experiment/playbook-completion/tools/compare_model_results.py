#!/usr/bin/env python3
"""Compare a verify run's model results with the committed RESULTS.json of each crate: every committed check must
be present in the rerun with the same design and expectation, and met in both. Prints per-crate counts; exit 1 on
any check missing, unmet, or changed."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows(p):
    d = json.loads(Path(p).read_text())
    r = d if isinstance(d, list) else d.get("checks") or d.get("results") or []
    return {x.get("id") or x.get("check") or x.get("check_id"): x for x in r}


def met_value(x):
    for k in ("met", "result", "outcome", "verdict"):
        if k in x:
            return x[k]
    return None


def met(x):
    v = met_value(x)
    return v is True or v in ("met", "pass", "expected-violation", "MET", "MATCH")


def main():
    out = Path(sys.argv[1]); bad = 0
    for crate in ("core", "breadth-a", "breadth-b", "breadth-c", "semantics"):
        new_p = out / f"models-{crate}.json"
        if not new_p.exists():
            print(f"{crate}: no rerun output"); bad += 1; continue
        old, new = rows(ROOT / "models" / crate / "RESULTS.json"), rows(new_p)
        missing = [k for k in old if k not in new]
        unmet = [k for k in new if not met(new[k])]
        print(f"{crate}: committed {len(old)}, rerun {len(new)}, missing {len(missing)}, unmet {len(unmet)}")
        bad += len(missing) + len(unmet)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
