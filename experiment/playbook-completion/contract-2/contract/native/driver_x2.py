#!/usr/bin/env python3
"""contract-2 round env2-r1 (X2-* clauses) on AUDITENV: the r6 driver (driver.py) with the X2 operations added.

    python driver_x2.py cases.json observed.json [--only ID ...]

Terminal (`term`) operations build ObjectScript lines; values cross the terminal as code points (`$ASCII` lists), so
the terminal's character translation cannot change them. DB-API (`dbapi`) operations use the scratch table
IVGAudit.T and the Native API on ^IVGAuditEnv. Nothing is compiled.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import driver as base  # noqa: E402

_ORIG_TERM = base.TermProc  # the r6 classes, before this module patches the names run_case uses
_ORIG_DBAPI = base.DbapiProc

W = 'write $c(30),"R|",'


def cstr(codes) -> str:
    codes = [int(c) for c in codes]
    return "$c(" + ",".join(str(c) for c in codes) + ")" if codes else '""'


def tstr(text: str) -> str:
    return cstr([ord(c) for c in text])


def lb(elems) -> str:
    parts = []
    for e in elems:
        if e is None:
            parts.append("")
        else:
            k, t = e
            parts.append(tstr(t) if k == "s" else t)
    return "$lb(" + ",".join(parts) + ")"


CODES = 'set c="" for i=1:1:$length(j) { set c=c_$s(i>1:",",1:"")_$ascii(j,i) } '


class X2Term(_ORIG_TERM):
    def _translate(self, op):
        k = op["op"]
        if k == "json_build":
            sets = []
            for key, v, ty in op["sets"]:
                val = {"string": lambda: tstr(v), "number": lambda: f'+"{v}"', "boolean": lambda: f'+"{v}"',
                       "null": lambda: '""'}[ty]()
                sets.append(f'do o.%Set({cstr(key)},{val},"{ty}")')
            return 'set o={} ' + " ".join(sets) + ' set j=o.%ToJSON() ' + CODES + W + '"J",c,!'
        if k == "json_roundtrip":
            rm = f' do o.%Remove({cstr(op["remove"])})' if op.get("remove") is not None else ""
            return ('set j="" try { set o={}.%FromJSON(' + cstr(op["text"]) + ')' + rm + ' set j=o.%ToJSON() } '
                    'catch ex { set j="error" } ' + CODES + W + '"J",c,!')
            # note: "error" travels as code points too
        if k == "json_get":
            K = cstr(op["key"])
            return ('set o="" try { set o={}.%FromJSON(' + cstr(op["text"]) + ') } catch ex { set o="" } '
                    'if \'$isobject(o) { ' + W + '"X","error",! } else { set g=o.%Get(' + K + '),t=o.%GetTypeOf(' + K
                    + '),d=o.%IsDefined(' + K + '),gc="" if $isobject(g) { set gc="<obj>" } else { for i=1:1:$length(g) '
                    '{ set gc=gc_$s(i>1:",",1:"")_$ascii(g,i) } } ' + W + '"X",gc,"|",t,"|",d,! }')
        if k == "list_eval":
            what = op["what"].split(":")
            L = "set l=" + lb(op["elems"]) + " "
            if what[0] == "len":
                return L + W + '"X",$listlength(l),!'
            if what[0] == "data":
                return L + W + f'"X",$listdata(l,{int(what[1])}),!'
            if what[0] == "get":
                return L + W + f'"X",$listget(l,{int(what[1])},{tstr(what[2] if len(what) > 2 else "")}),!'
            if what[0] == "item":
                return L + f'try {{ set x=$list(l,{int(what[1])}) }} catch ex {{ set x=ex.Name }} ' + W + '"X",x,!'
            if what[0] == "walk":
                return (L + 'set p=0,s="" kill v while $listnext(l,p,v) { set s=s_$s(s="":"",1:";")_$s($d(v):"<"_v_">",1:"U") '
                        'kill v } ' + W + '"X",s,!')
            if what[0] == "find":
                st = int(what[2]) if len(what) > 2 else 0
                return L + W + f'"X",$listfind(l,{tstr(what[1])},{st}),!'
            if what[0] == "tostring":
                fl = int(what[2]) if len(what) > 2 else 0
                return (L + f'try {{ set x=$listtostring(l,{tstr(what[1])},{fl}) }} catch ex {{ set x=ex.Name }} '
                        + W + '"X",x,!')
            return None
        if k == "list_same":
            return f'set a={lb(op["a"])},b={lb(op["b"])} ' + W + '"X",$listsame(a,b),"|",(a=b),!'
        if k == "list_fromstring":
            return (f'set l=$listfromstring({tstr(op["s"])},{tstr(op["d"])}),p=0,s="" kill v while $listnext(l,p,v) '
                    '{ set s=s_$s(s="":"",1:";")_$s($d(v):"<"_v_">",1:"U") kill v } ' + W + '"X",$listlength(l),"|",s,!')
        if k == "list_store":
            return f'set ^IVGAuditEnv("lb")={lb(op["elems"])} ' + W + '"ok",!'
        if k == "query_walk":
            return ('set r="' + base.real_root(op["node"]["root"]) + '",out="" for { set r=$query(@r) quit:r=""  set s="" '
                    'for i=1:1:$qlength(r) { set s=s_$s(i>1:$c(31),1:"")_$qsubscript(r,i) } set out=out_s_$c(29) } '
                    + W + '"Q",out,!')
        if k == "query_back":
            return ('set r=$query(' + self.ref(op["node"]) + ',-1),s="" if r\'="" { for i=1:1:$qlength(r) '
                    '{ set s=s_$s(i>1:$c(31),1:"")_$qsubscript(r,i) } } ' + W + '"X",s,!')
        if k == "merge":
            return f'merge {self.ref(op["to"])}={self.ref(op["from"])} ' + W + '"ok",!'
        if k == "zkill":
            return f'zkill {self.ref(op["node"])} ' + W + '"ok",!'
        return super()._translate(op)

    @staticmethod
    def _decode(op, r):
        if r["ok"] and r["raw"][:1] in ("J", "X", "Q"):
            tag, body = r["raw"][0], r["raw"][1:]
            if tag == "J":
                return {"obs": "value", "value": "".join(chr(int(x)) for x in body.split(",") if x != "")}
            if tag == "X":
                return {"obs": "value", "value": body}
            if tag == "Q":
                return {"obs": "subs", "subs": [x for x in body.split("\x1d") if x != ""]}
        return _ORIG_TERM._decode(op, r)


class X2Dbapi(_ORIG_DBAPI):
    def _x2(self, op):
        k = op["op"]
        t = base.tname(op.get("table", "T"))
        if k == "list_native":
            import iris
            raw = self.o.getBytes(base.GROOT, "lb")
            if raw is None:
                return {"obs": "refused", "what": "list_native of a node that is not a stored $LB"}
            lst = iris.IRISList(raw)
            out = []
            for i in range(1, lst.count() + 1):
                v = lst.get(i)
                out.append("None" if v is None else f"{type(v).__name__}:{v}")
            return {"obs": "value", "value": ";".join(out)}
        if k == "select_top":
            n, order, form = int(op["n"]), op["order"], op["form"]
            ob = {"asc": "ORDER BY k", "desc": "ORDER BY k DESC", "exact": "ORDER BY %EXACT(k)", "none": ""}[order]
            if form == "top":
                q = f"SELECT TOP {n} k, v FROM {t} {ob}"
            elif form == "limit":
                q = f"SELECT k, v FROM {t} {ob} LIMIT {n}"
            else:
                q = f"SELECT k, v FROM {t} {ob} LIMIT {n} OFFSET {int(op.get('offset', 0))}"
            rows = [[str(a), str(b)] for a, b in self._q(q)]
            return {"obs": "rows", "rows": sorted(rows) if order == "none" else rows}
        if k == "insert_many":
            cur = self.c.conn.cursor()
            try:
                cur.executemany(f"INSERT INTO {t} (k, v) VALUES (?, ?)", [tuple(r) for r in op["rows"]])
                return {"obs": "count", "rowcount": max(cur.rowcount, 0)}
            except Exception as e:  # noqa: BLE001
                return base.norm_err(e)
            finally:
                cur.close()
        if k == "upsert":
            cur = self.c.conn.cursor()
            try:
                cur.execute(f"INSERT OR UPDATE {t} (k, v) VALUES (?, ?)", (op["k"], op["v"]))
                return {"obs": "count", "rowcount": max(cur.rowcount, 0)}
            except Exception as e:  # noqa: BLE001
                return base.norm_err(e)
            finally:
                cur.close()
        return None

    def run(self, op):
        k = op["op"]
        if k in ("list_native", "select_top", "insert_many", "upsert"):
            if self.pending is not None:
                return {"obs": "error", "error": "busy"}
            if k == "upsert":
                a = base.Async(lambda: self._x2(op))
                r = a.wait(base.ISSUE_WAIT)
                if r is None:
                    self.pending = a
                    return {"obs": "pending"}
                return r
            try:
                return self._x2(op)
            except Exception as e:  # noqa: BLE001
                return base.norm_err(e)
        return super().run(op)


base.TermProc = X2Term
base.DbapiProc = X2Dbapi

if __name__ == "__main__":
    raise SystemExit(base.main())
