"""typed_equality binding: actual Cypher WHERE equality and RETURN on the run-isolated IRIS fixture vs a port of the model.

Each value is written once as a node property (create_node) and once as an edge qualifier (create_edge), on fresh
nodes. Every (kind, value) world is read by `WHERE x.p = <literal> RETURN count(*)` for seven literals and by
`RETURN x.p`. The port mirrors typed_equality.rs; for stored doubles it uses the declared providers (IRIS canonical
number text; numeric equality). Four port mutations mirror the model controls and must each disagree with at least one
actual observation. Ordinary data on the identity-checked fixture only.
"""
import hashlib
import json
import os
import re
import sys
import time
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(Path(os.environ.get("IVG_RUNTIME_DIR", str(REPO / ".g5/uplift/consolidated/iteration-15")))))
import runtime  # noqa: E402

RUN = os.environ.get("TE_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
VALUES = [0, 1, 2, -1, 12, True, False, "1", "0", "True", "False", "true", "false", "12", "01", "x", "1.0", "12.0", 1.0, 0.0, 0.95, 12.0]
LITERALS = [("bool", True), ("bool", False), ("int", 0), ("int", 1), ("int", 2), ("int", 12), ("int", -1)]
TRUE_SP, FALSE_SP = ("true", "1", "True"), ("false", "0", "False")
INT_RE, FLOAT_RE = re.compile(r"^-?(0|[1-9]\d*)$"), re.compile(r"^-?(0|[1-9]\d*)\.\d+$")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canonical(x):
    """Provider: IRIS canonical number text (1.0 -> '1', 0.95 -> '.95')."""
    d = Decimal(repr(x)) if isinstance(x, float) else Decimal(x)
    t = "0" if d == 0 else format(d.normalize(), "f")
    return t[1:] if t.startswith("0.") else ("-" + t[2:] if t.startswith("-0.") else t)


def lit_text(kind, v):
    return ("true" if v else "false") if kind == "bool" else str(v)


# ---------------- port of typed_equality.rs ----------------
def node_stored(v):
    if isinstance(v, bool):
        return ("text", "true" if v else "false")
    if isinstance(v, int):
        return ("int", v)
    if isinstance(v, float):
        return ("double", v)
    return ("text", v)


def node_matches(st, t, rules):
    k, x = st
    if k == "text":
        return x == t
    if rules.get("stored_integer_not_a_spelling"):
        return False
    return (canonical(x) if k == "double" else str(x)) == t


def node_where(st, lit, rules):
    kind, v = lit
    if kind == "bool":
        sp = TRUE_SP if v else FALSE_SP
        if rules.get("legacy_one_not_true") and v:
            sp = ("true", "true", "True")
        return any(node_matches(st, t, rules) for t in sp)
    if rules.get("node_number_by_text"):
        return node_matches(st, str(v), rules)
    k, x = st
    return k in ("int", "double") and x == v


def node_return(st):
    k, x = st
    if k == "text":
        return True if x == "true" else False if x == "false" else x
    return x


def json_value(v, rules):
    if isinstance(v, bool):
        return ("true" if v else "false") if rules.get("json_boolean_reads_as_word") else ("1" if v else "0")
    if isinstance(v, float):
        # provider, observed in attempts 1-2: JSON_VALUE keeps a whole JSON float's spelling (1.0, 0.0, 12.0). A fraction's
        # spelling (.95 or 0.95) is not distinguishable by these boolean/integer literals; either gives the same cells.
        return repr(v)
    if isinstance(v, int):
        return canonical(v)
    return v


def rel_where(v, lit, rules):
    kind, x = lit
    t = json_value(v, rules)
    if kind == "bool":
        sp = TRUE_SP if x else FALSE_SP
        if rules.get("legacy_one_not_true") and x:
            sp = ("true", "true", "True")
        return t in sp
    return t == str(x) if rules.get("twin_spelling_dropped") else t in (str(x), str(x) + ".0")


def rel_return(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    t = v  # rel_prop_text as_built on ASCII text
    if t == "true":
        return True
    if t == "false":
        return False
    if INT_RE.match(t):
        return int(t)
    if FLOAT_RE.match(t):
        return float(t)
    return t


def predict(kind, v, rules=None):
    rules = rules or {}
    out = {}
    for lit in LITERALS:
        out[lit_text(*lit)] = node_where(node_stored(v), lit, rules) if kind == "node" else rel_where(v, lit, rules)
    out["return"] = node_return(node_stored(v)) if kind == "node" else rel_return(v)
    return out


def typed(x):
    return [type(x).__name__, x]


def main():
    start = time.monotonic()
    c = runtime.connect()
    e = runtime.engine(c)
    worlds = []
    for i, v in enumerate(VALUES):
        for kind in ("node", "rel"):
            a, b = f"te{RUN}{kind}{i}a", f"te{RUN}{kind}{i}b"
            if kind == "node":
                e.create_node(a, labels=["TE"], properties={"p": v})
                base = f"MATCH (x:TE) WHERE x.id = '{a}'"
            else:
                e.create_node(a, labels=["TE"])
                e.create_node(b, labels=["TE"])
                e.create_edge(a, "TER", b, qualifiers={"p": v})
                base = f"MATCH (s)-[x:TER]->(t) WHERE s.id = '{a}'"
            obs = {}
            for lit in LITERALS:
                rows = e.execute_cypher(f"{base} AND x.p = {lit_text(*lit)} RETURN count(*) AS n")["rows"]
                obs[lit_text(*lit)] = bool(rows[0][0])
            got = e.execute_cypher(f"{base} RETURN x.p AS p")["rows"]
            obs["return"] = got[0][0] if got else "NO ROW"
            want = predict(kind, v)
            same = all(obs[k] == want[k] for k in want if k != "return") and typed(obs["return"]) == typed(want["return"])
            worlds.append({"kind": kind, "value": typed(v), "observed": {k: (typed(x) if k == "return" else x) for k, x in obs.items()},
                           "expected": {k: (typed(x) if k == "return" else x) for k, x in want.items()}, "agrees": same,
                           "provider_dependent": isinstance(v, float)})
    c.close()
    mismatches = [w for w in worlds if not w["agrees"]]
    sens = {}
    for rule in ["legacy_one_not_true", "node_number_by_text", "json_boolean_reads_as_word", "stored_integer_not_a_spelling", "twin_spelling_dropped"]:
        n = 0
        for w in worlds:
            v = w["value"][1]
            alt = predict(w["kind"], v, {rule: True})
            if any(alt[k] != w["observed"][k] for k in alt if k != "return"):
                n += 1
        sens[rule] = n
    body = {
        "kind": "binding", "model": "typed_equality", "fixture": runtime.NAME, "port": runtime.PORT, "run": RUN,
        "product_baseline": runtime.PRODUCT, "verdict": "AGREES" if not mismatches else "DISAGREES",
        "worlds": len(worlds), "comparisons": len(worlds) * (len(LITERALS) + 1), "mismatches": mismatches,
        "sensitivities_detected_worlds": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
        "elapsed_s": time.monotonic() - start,
        "inputs": {str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "typed_equality.rs", HERE / "model.json"]},
        "scope": "SQL path (engine native_cypher=False) on IRIS 2026.1 Community; create_node/create_edge writers; WHERE x.p = <boolean or "
                 "integer literal> and RETURN x.p. Doubles use declared providers. No parameters, IN lists, MERGE patterns, native "
                 "executor, Cypher-written values or legacy rows.",
    }
    out = REPO / ".g5/Verus_verification/results/typed_equality" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True)
    (out / "worlds.json").write_text(json.dumps(worlds, indent=1, default=str) + "\n")
    body["worlds_sha256"] = sha(out / "worlds.json")
    (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "worlds", "comparisons", "all_sensitivities_detected", "sensitivities_detected_worlds", "elapsed_s")}, indent=1))
    for m in mismatches:
        print("MISMATCH", json.dumps({k: m[k] for k in ("kind", "value")}), {k: (m["observed"][k], m["expected"][k]) for k in m["expected"] if m["observed"][k] != m["expected"][k]})
    print(out / "receipt.json")


if __name__ == "__main__":
    main()
