#!/usr/bin/env python3
"""reads3 core: the reads2 non-interference oracle (reads3/ni_base.py, a copy of reads2/ni_base.py) with three
extensions, used by ni3.py for modules 04 and 10.

1. prep: an optional step run after the perturbation and before the action (rebuilds of derived stores, e.g.
   engine.sync(), over base + perturbation), so a perturbation is applied to the rows a derived store is built from
   and never after a derived store was stamped.
2. keyed answers: a case may evaluate several entry points against the same base and perturbations; its answer is a
   dict {entry key: answer}, and the verdict is computed per key (stable / changed under each outside perturbation /
   changed under the inside one). A sub-call that raises answers {"__error__": text}; a key whose base answer is an
   error is undecided unless the case declares the error to be the entry point's answer (refusal_keys).
3. engines are built with native_cypher=False: a Cypher query never reaches the native executor, so nothing compiles a
   plan class.

Everything else is ni_base's: every variant starts from lib.reset() on a fresh connection and a fresh engine, the
answer is compared canonically (lists sorted, floats rounded to 10 digits), wall-clock and generated ids are masked.
"""
from __future__ import annotations

import json
import re
import time
import traceback
from pathlib import Path

import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "live"))
import lib  # noqa: E402
import ni_base as NI  # noqa: E402  (reads3 copy)

import iris  # noqa: E402

G1, G2, T0 = NI.G1, NI.G2, NI.T0
SCRATCH = "^IVGAuditDRd3X"
ROOTG = "^IVGAuditDRd3Root"
SCRATCH_GLOBALS = (SCRATCH, ROOTG, "^IVGAuditDRd3Snap")


def a_in(e, c):
    """ni_base's inside perturbation for default-graph algorithms: a new node e and edges a-R-e, e-R-c."""
    e.create_node("e", graph=None)
    e.create_edge("a", "R", "e")
    e.create_edge("e", "R", "c")


def engine(c, **kw):
    kw.setdefault("native_cypher", False)
    return lib.engine(c, **kw)


def kill_scratch(c):
    for g in SCRATCH_GLOBALS:
        try:
            c.o.kill(g)
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------------------------------------------ values
def vstr(v):
    """A global's value as text; a $ListBuild arrives as a str of control characters, escaped here (no IRISList
    decoding: the client crashed on some inputs)."""
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    s = str(v)
    if any(ord(ch) < 32 for ch in s):
        return s.encode("unicode_escape").decode("ascii")
    return s


def walk(c, *root, maxdepth=9):
    """Every defined node under root as [subscripts..., '=value'] (subscripts after the global name)."""
    out = []
    try:
        d0 = int(c.o.isDefined(*root))
    except Exception:  # noqa: BLE001
        return out
    if d0 == 0:
        return out
    if d0 in (1, 11):
        out.append([str(x) for x in root[1:]] + ["=" + vstr(c.o.get(*root))])

    def rec(node, depth):
        if depth > maxdepth:
            return
        for sub, _ in c.o.iterator(*node).items():
            n2 = list(node) + [sub]
            dd = int(c.o.isDefined(*n2))
            if dd in (1, 11):
                out.append([str(x) for x in n2[1:]] + ["=" + vstr(c.o.get(*n2))])
            if dd >= 10:
                rec(n2, depth + 1)
    if d0 >= 10:
        rec(list(root), 0)
    return sorted(out)


def gkey(g):
    return 0 if not g else g


KG_SUBS = ("out", "in", "label", "gen", "degc", "deg2p", "deg2p_exact")


def kgstate(c, g, subs=KG_SUBS):
    """Graph g's ^KG subtrees (out, in, label, gen, degc, deg2p, deg2p_exact); degw is reported as present or not
    (its value is the namespace token, which grows between variants)."""
    k = gkey(g)
    out = {s: walk(c, "^KG", s, k) for s in subs}
    out["degw_present"] = bool(int(c.o.isDefined("^KG", "degw", k)))
    return out


def rows(c, g):
    gg = g or ""
    out = {}
    for t, cols in (("nodes", "node_id"), ("rdf_edges", "s, p, o_id, ekey, qualifiers"), ("rdf_labels", "s, label"),
                    ("rdf_props", 's, "key", val')):
        out[t] = sorted(list(map(str, r)) for r in NI.hsql(c, f"SELECT {cols} FROM %IGNOREINDEX * Graph_KG.{t} WHERE COALESCE(graph_id,'') = ?", gg))
    return out


def gstate(c, g):
    """Graph g's state: its rows in the four content tables and its ^KG subtrees."""
    return {"rows": rows(c, g), "kg": kgstate(c, g)}


def nkg_named(c):
    """^NKG as names: interned node names, edges (source, label, target) by name, and the meta counts."""
    nd = {}
    for i, v in (c.o.iterator("^NKG", "$ND").items() if int(c.o.isDefined("^NKG", "$ND")) else []):
        nd[str(i)] = str(v)
    ls = {}
    for i, v in (c.o.iterator("^NKG", "$LS").items() if int(c.o.isDefined("^NKG", "$LS")) else []):
        ls[str(i)] = str(v)
    edges = []
    if int(c.o.isDefined("^NKG", -1)):
        for s, _ in c.o.iterator("^NKG", -1).items():
            for p, _ in c.o.iterator("^NKG", -1, s).items():
                for o, w in c.o.iterator("^NKG", -1, s, p).items():
                    edges.append([nd.get(str(s), "#" + str(s)), ls.get(str(-int(p) - 1), "#" + str(p)), nd.get(str(o), "#" + str(o)), str(w)])
    meta = {}
    for k in ("nodeCount", "edgeCount", "liveNodes", "stale"):
        meta[k] = str(c.o.get("^NKG", "$meta", k)) if int(c.o.isDefined("^NKG", "$meta", k)) % 2 else None
    return {"nodes": sorted(nd.values()), "edges": sorted(edges), "meta": meta}


TAG = re.compile(r"\b(CHUNKED|SORTED):[0-9A-Za-z_]+:")
TOKEN = re.compile(r"^([HM])\d+")
DIGITS = re.compile(r"\d{5,}")


def mask3(x):
    if isinstance(x, dict):
        return {k: mask3(v) for k, v in x.items()}
    if isinstance(x, list):
        return [mask3(v) for v in x]
    if isinstance(x, str):
        x = TAG.sub(lambda m: m.group(1) + ":<tag>:", x)
        x = TOKEN.sub(lambda m: m.group(1) + "<token>", x)
        return x
    return x


def parse(v):
    if v is not None and hasattr(v, "invoke") and not isinstance(v, (str, bytes)):
        for m in ("%ToJSON", "_ToJSON"):  # a %DynamicArray / %DynamicObject handed back by reference (or wrapped in
            try:                          # %SYS.Python by an embedded-Python method): its JSON text
                v = v.invoke(m)
                break
            except Exception:  # noqa: BLE001
                continue
    if isinstance(v, (bytes, bytearray)):
        return vstr(v)
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in ("{", "["):
            try:
                return json.loads(s)
            except ValueError:
                return v
    return v


def errtext(ex):
    t = f"{type(ex).__name__}: {str(ex)}"
    t = DIGITS.sub("#", t)
    return t[:260]


def cm(cls, meth, *args):
    """A Native API class method call answering a value (JSON text parsed)."""
    def f(e, c):
        return parse(c.o.classMethodValue(cls, meth, *args))
    f.__name__ = f"{cls}.{meth}"
    return f


def cmv(cls, meth, *args):
    """A Native API call of a method that returns no value."""
    def f(e, c):
        c.o.classMethodVoid(cls, meth, *args)
        return "<void>"
    return f


def multi(spec):
    """spec: list of (key, fn(e, c)). Each sub-call runs in order on the same engine/connection; a raise answers
    {"__error__": ...} for that key and the next sub-call still runs."""
    def f(e, c):
        out = {}
        for key, fn in spec:
            try:
                v = fn(e, c)
            except Exception as ex:  # noqa: BLE001
                v = {"__error__": errtext(ex)}
                try:
                    c.conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
            try:
                c.conn.commit()
            except Exception:  # noqa: BLE001
                pass
            out[key] = v
        return out
    return f


def C3(module, cid, call, base, declared, outside, inside=None, prep=None, keyed=True, inside_declared=None,
       refusal_keys=(), note="", entries=None, insensitive_ok=(), vacuous=None):
    """vacuous: {key: fn(base answer) -> reason or None}; a key whose base answer is vacuous (the call answered
    without reading what it would read: a library or module absent) is undecided, never holding."""
    return {"module": module, "id": cid, "call": call, "base": base, "declared": declared, "outside": outside,
            "inside": inside, "prep": prep, "keyed": keyed, "inside_declared": inside_declared or {},
            "refusal_keys": set(refusal_keys), "note": note, "entries": entries, "insensitive_ok": set(insensitive_ok),
            "vacuous": vacuous or {}}


# ------------------------------------------------------------------------------------------------ the run
def variant3(case, extra, tag):
    c = lib.conn()
    try:
        lib.reset(c)
        kill_scratch(c)
        c.conn.commit()
        setup_err = None
        e = engine(c)
        try:
            case["base"](e, c)
            c.conn.commit()
            if extra:
                extra(e, c)
                c.conn.commit()
            if case.get("prep"):
                case["prep"](e, c)
                c.conn.commit()
        except Exception as ex:  # noqa: BLE001
            setup_err = errtext(ex)
            try:
                c.conn.rollback()
            except Exception:  # noqa: BLE001
                pass
        e2 = engine(c)
        NI._CAPTURE.update(on=True, sql=[])
        try:
            ans = case["call"](e2, c)
            err = None
        except Exception as ex:  # noqa: BLE001
            ans, err = None, errtext(ex)
        finally:
            sql = list(NI._CAPTURE["sql"])
            NI._CAPTURE.update(on=False, sql=[])
        try:
            c.conn.commit()
        except Exception:  # noqa: BLE001
            pass
        ans = mask3(NI.mask(NI.raw(ans)))
        return {"tag": tag, "setup_error": setup_err, "error": err, "canon": NI.canon(ans), "raw": ans,
                "sql_tables": NI.tables_of(sql), "sql_count": len(sql)}
    finally:
        try:
            kill_scratch(c)
            c.conn.commit()
        except Exception:  # noqa: BLE001
            pass
        c.close()


def is_err(v):
    return isinstance(v, dict) and "__error__" in v


def run_case3(case):
    t = time.time()
    b0 = variant3(case, None, "base")
    b1 = variant3(case, None, "base-again")
    outs = {name: variant3(case, fn, "outside:" + name) for name, fn in case["outside"].items()}
    ins = variant3(case, case["inside"], "inside") if case["inside"] else None
    insd = {name: variant3(case, fn, "inside-declared:" + name) for name, fn in case["inside_declared"].items()}
    res = {"module": case["module"], "id": case["id"], "declared": case["declared"], "note": case["note"],
           "base": b0, "base_again": {"canon": b1["canon"], "error": b1["error"], "setup_error": b1["setup_error"]},
           "outside": {n: {"answer": v["canon"], "error": v["error"], "setup_error": v["setup_error"]} for n, v in outs.items()},
           "inside": None if ins is None else {"answer": ins["canon"], "error": ins["error"], "setup_error": ins["setup_error"]},
           "inside_declared": {n: {"answer": v["canon"], "error": v["error"], "setup_error": v["setup_error"]} for n, v in insd.items()}}
    whole_err = b0["error"] or b0["setup_error"]
    keys = []
    if case["keyed"] and isinstance(b0["canon"], dict) and not whole_err:
        keys = list(b0["raw"].keys()) if isinstance(b0["raw"], dict) else sorted(b0["canon"])
    per = {}
    if keys:
        for k in keys:
            bv = b0["canon"].get(k)
            stable = (b1["canon"] or {}).get(k) == bv if isinstance(b1["canon"], dict) else False
            changed = sorted(n for n, v in outs.items() if v["setup_error"] is None and isinstance(v["canon"], dict) and v["canon"].get(k) != bv)
            not_applied = sorted(n for n, v in outs.items() if v["setup_error"] is not None)
            ich = None if ins is None or ins["setup_error"] else (not isinstance(ins["canon"], dict) or ins["canon"].get(k) != bv)
            idch = {n: (v["canon"].get(k) != bv if isinstance(v["canon"], dict) else True) for n, v in insd.items()}
            vac = case["vacuous"].get(k)
            vac_reason = vac(bv) if vac else None
            if is_err(bv) and k not in case["refusal_keys"]:
                verdict = "violation" if changed else "undecided-error"
            elif vac_reason:
                verdict = "violation" if changed else "undecided-vacuous"
            elif not stable:
                verdict = "unstable"
            elif changed:
                verdict = "violation"
            else:
                verdict = "holds"
            per[k] = {"verdict": verdict, "stable": stable, "changed_under": changed, "perturbations_not_applied": not_applied,
                      "inside_changed": ich, "inside_declared_changed": idch,
                      "base_answer_is_error": is_err(bv), "vacuous": vac_reason,
                      "refusal_is_the_answer": k in case["refusal_keys"],
                      "base_answer_excerpt": json.dumps(bv, default=str)[:300]}
        verdicts = {v["verdict"] for v in per.values()}
        verdict = "violation" if "violation" in verdicts else ("holds" if verdicts == {"holds"} else "mixed")
    else:
        stable = NI.same(b0, b1)
        changed = sorted(n for n, v in outs.items() if v["setup_error"] is None and not NI.same(b0, v))
        if whole_err:
            verdict = "violation" if changed else "undecided-error"
        elif not stable:
            verdict = "unstable"
        elif changed:
            verdict = "violation"
        else:
            verdict = "holds"
        per["__whole__"] = {"verdict": verdict, "stable": stable, "changed_under": changed,
                            "inside_changed": None if ins is None else not NI.same(b0, ins),
                            "inside_declared_changed": {n: not NI.same(b0, v) for n, v in insd.items()},
                            "base_error": whole_err}
    res["per_key"] = per
    res["verdict"] = verdict
    res["setup_errors"] = {n: v["setup_error"] for n, v in list(outs.items()) + [("base", b0), ("inside", ins or {})] + list(insd.items()) if v and v.get("setup_error")}
    res["seconds"] = round(time.time() - t, 1)
    viol = sorted(k for k, v in per.items() if v["verdict"] == "violation")
    und = sorted(k for k, v in per.items() if v["verdict"] not in ("holds", "violation"))
    print(f"[{case['module']}] {verdict:9} {case['id'][:64]}  keys={len(per)} viol={viol} other={und} "
          f"setup_err={list(res['setup_errors'])} ({res['seconds']}s)", flush=True)
    return res


def run_all(sel, out_p, info):
    rs = []
    for x in sel:
        try:
            rs.append(run_case3(x))
        except Exception as ex:  # noqa: BLE001
            rs.append({"module": x["module"], "id": x["id"], "verdict": "harness-error",
                       "error": f"{type(ex).__name__}: {ex}", "trace": traceback.format_exc()[-2000:]})
            print(f"[{x['module']}] harness-error {x['id']}: {ex}", flush=True)
        finally:
            cc = lib.conn()
            try:
                kill_scratch(cc)
                lib.reset(cc)
                cc.conn.commit()
            finally:
                cc.close()
    summ = {}
    for r in rs:
        for k, v in (r.get("per_key") or {"__case__": {"verdict": r["verdict"]}}).items():
            s = summ.setdefault(r["module"], {})
            s[v["verdict"]] = s.get(v["verdict"], 0) + 1
    lib.dump(out_p, {"info": info, "summary_per_key": summ, "cases": rs})
    print(json.dumps(summ))
    return rs
