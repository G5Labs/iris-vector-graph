#!/usr/bin/env python3
"""Exploratory probes for the contract-2 extension (AUDITENV, scratch ^IVGAuditEnv and IVGAudit.T only).
Prints one JSON line per probe. Not a validation: the clauses drafted from these are decided by a later round."""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "contract" / "native"))
import driver as d  # noqa: E402

out = []


def rec(k, v):
    out.append({"probe": k, "obs": v})
    print(json.dumps({"probe": k, "obs": v}, ensure_ascii=False), flush=True)


def T(t, cmd, secs=10):
    r = t._call('write $c(30),"R|",' + cmd + ",!" if not cmd.startswith("!") else cmd[1:], secs)
    return r["raw"] if r["ok"] else "ERR:" + r["raw"]


def Tx(t, stmts, expr, secs=10):
    """run statements, then write expr"""
    r = t._call(stmts + '  write $c(30),"R|",' + expr + ",!", secs)
    return r["raw"] if r["ok"] else "ERR:" + r["raw"]


ctl = d.Conn("AUDITENV")
d.reset(ctl)
t = d.TermProc()
try:
    # ---------------- JSON
    J = {
        "j1-bool": ('set o={} do o.%Set("temporal",1,"boolean")', "o.%ToJSON()"),
        "j2-weight-half": ('set o={} do o.%Set("temporal",1,"boolean") do o.%Set("weight",+".5","number")', "o.%ToJSON()"),
        "j2b-weight-2": ('set o={} do o.%Set("weight",+"2.0","number")', "o.%ToJSON()"),
        "j2c-neg-small": ('set o={} do o.%Set("x",-.25,"number") do o.%Set("y",1E-7,"number") do o.%Set("z",123456789012345678901234,"number")', "o.%ToJSON()"),
        "j3-order": ('set o={} do o.%Set("b",2) do o.%Set("a",1) do o.%Set("c",3)', "o.%ToJSON()"),
        "j3b-reset-existing": ('set o={} do o.%Set("b",2) do o.%Set("a",1) do o.%Set("b",5)', "o.%ToJSON()"),
        "j4-dup": ('set o={}.%FromJSON("{""b"":1,""a"":2,""b"":3}")', "o.%ToJSON()"),
        "j5-numbers": ('set o={}.%FromJSON("{""x"":1.50,""y"":1e2,""z"":-0.0,""w"":12345678901234567890,""v"":0.1,""u"":2.0}")', "o.%ToJSON()"),
        "j6-escapes": ('set o={} do o.%Set("s",$c(1)_"e"_$c(233)_"/"_$c(10)_$c(34)_"\\"_$c(9)_$c(8364))', "o.%ToJSON()"),
        "j7-types": ('set o={}.%FromJSON("{""n"":null,""t"":true,""f"":false,""s"":""1"",""i"":1}")',
                     'o.%Get("n"),"|",o.%GetTypeOf("n"),"|",o.%Get("t"),"|",o.%GetTypeOf("t"),"|",o.%Get("f"),"|",o.%GetTypeOf("s"),"|",o.%GetTypeOf("i"),"|",o.%Get("missing"),"|",o.%GetTypeOf("missing"),"|",o.%IsDefined("n"),"|",o.%IsDefined("missing"),"|",o.%Size()'),
        "j8-iter": ('set o={}.%FromJSON("{""z"":1,""a"":2,""m"":3}"),it=o.%GetIterator(),s="" while it.%GetNext(.k,.v) { set s=s_k_"="_v_";" }', "s"),
        "j9-remove": ('set o={}.%FromJSON("{""z"":1,""a"":2,""m"":3}") do o.%Remove("a")', "o.%ToJSON()"),
        "j10-invalid": ('set e="" try { set o={}.%FromJSON("{""a"":1,") } catch ex { set e=ex.Name }', "e"),
        "j11-pydumps": ('set o={}.%FromJSON("{""temporal"": true, ""weight"": 2.0}")', "o.%ToJSON()"),
        "j12-string-number": ('set o={} do o.%Set("k","007") do o.%Set("n",007) do o.%Set("e","")', "o.%ToJSON()"),
        "j13-third": ('set o={} do o.%Set("x",1/3)', "o.%ToJSON()"),
        "j14-array": ('set a=[].%FromJSON("[1,""a"",null,true,{""k"":[]}]") do a.%Push(2.50) do a.%Push("","null")', 'a.%ToJSON(),"|",a.%Size(),"|",a.%GetTypeOf(2)'),
        "j15-null-set": ('set o={} do o.%Set("k","","null") do o.%Set("j",$c(0))', "o.%ToJSON()"),
        "j16-get-number-type": ('set o={}.%FromJSON("{""x"":1.50,""y"":""1.50""}")', 'o.%Get("x"),"|",o.%Get("y"),"|",o.%GetTypeOf("x"),"|",(o.%Get("x")=1.5)'),
        "j17-nested-tojson": ('set o={"a":{"b":[1,2]},"c":"d"}', "o.%ToJSON()"),
        "j18-literal-bool": ('set o={"t":true,"n":null,"x":(1+1)}', "o.%ToJSON()"),
        "j19-bool-get": ('set o={} do o.%Set("t",1,"boolean") do o.%Set("f",0,"boolean")', 'o.%Get("t"),"|",o.%Get("f"),"|",o.%GetTypeOf("t")'),
        "j20-unicode-key": ('set o={} do o.%Set($c(233),1) do o.%Set("a b",2)', "o.%ToJSON()"),
        "j21-big-int-str": ('set o={}.%FromJSON("{""x"":9007199254740993,""y"":1.7976931348623157e308}")', 'o.%ToJSON(),"|",o.%Get("x")'),
        "j22-tojson-roundtrip-ctrl": ('set o={}.%FromJSON("{""s"":""a\\u0001b\\nc\\/d""}")', 'o.%ToJSON(),"|",$length(o.%Get("s"))'),
    }
    part2 = "--part2" in sys.argv or "--part3" in sys.argv
    for k, (st, ex) in ([] if part2 else J.items()):
        rec(k, Tx(t, st, ex))
    # ---------------- LIST
    L = {
        "l1-basic": ('set l=$lb("a",1,,2.5,"")', '$listlength(l),"|",$listdata(l,3),"|",$listget(l,3,"d"),"|",$listget(l,9),"|",$listdata(l,5),"|",$listget(l,5,"d")'),
        "l1b-list-missing": ('set l=$lb("a",,"c"),e="" try { set x=$list(l,2) } catch ex { set e=ex.Name }', 'e'),
        "l1c-list-beyond": ('set l=$lb("a"),e="" try { set x=$list(l,5) } catch ex { set e=ex.Name }', 'e'),
        "l2-next": ('set l=$lb("a",,3,""),p=0,s="" while $listnext(l,p,v) { set s=s_$s($d(v):"<"_v_">",1:"U")_";" }', 's'),
        "l3-valid": ('', '$listvalid("abc"),"|",$listvalid(""),"|",$listvalid($lb(1)),"|",$listvalid($c(3,1)_"ab"),"|",$listvalid($c(2,1))'),
        "l4-fromstring": ('set l=$listfromstring("a,b,,c",",")', '$listlength(l),"|",$listdata(l,3),"|",$listget(l,3,"d"),"|",$listtostring($lb("a","b,c"),","),"|",$listtostring($lb("a",,"c"),","),"|",$listtostring($lb("a",,"c"),",",1)'),
        "l5-same": ('', '$listsame($lb(1),$lb("1")),"|",($lb(1)=$lb("1")),"|",$listsame($lb(1.0),$lb(1)),"|",$listsame($lb("01"),$lb(1)),"|",($lb(1.5)=$lb(1.5))'),
        "l6-find": ('set l=$lb("a","b","a")', '$listfind(l,"a"),"|",$listfind(l,"a",1),"|",$listfind(l,"z"),"|",$listfind($lb(1),"1")'),
        "l7-empty": ('', '$listlength(""),"|",$listlength($lb()),"|",$listdata($lb(),1),"|",$listlength($lb(,))'),
        "l8-nested": ('set l=$lb($lb(1,2),"x")', '$listlength(l),"|",$listlength($list(l,1)),"|",$listvalid($list(l,1))'),
        "l9-concat": ('set l=$lb("a")_$lb("b",3)', '$listlength(l),"|",$list(l,3)'),
        "l10-setlist": ('set l=$lb("a","b") set $list(l,4)="d"', '$listlength(l),"|",$listdata(l,3),"|",$list(l,4)'),
        "l11-encodings": ('', '$length($lb("a")),"|",$length($lb(1)),"|",$length($lb(-1)),"|",$length($lb(2.5)),"|",$length($lb(256)),"|",$length($lb($c(233))),"|",$length($lb($c(8364))),"|",$length($lb()),"|",$length($lb(""))'),
        "l12-bytes": ('set s="" for x=$lb("a"),$lb(1),$lb(-1),$lb(2.5),$lb(""),$lb(),$lb($c(233)),$lb($c(8364)),$lb("1"),$lb(1E20),$lb(1.0) { set h="" for i=1:1:$length(x) { set h=h_$zhex($ascii(x,i))_"." } set s=s_h_";" }', 's'),
    }
    for k, (st, ex) in ([] if part2 else L.items()):
        rec(k, Tx(t, st or "set zz=1", ex))
    if part2 and "--part3" not in sys.argv:
        rec("l4b-tostring-undef", Tx(t, 'set e="" try { set x=$listtostring($lb("a",,"c"),",") } catch ex { set e=ex.Name }', 'e'))
        rec("l4c-tostring-undef-flag", Tx(t, 'set e="",x="" try { set x=$listtostring($lb("a",,"c"),",",1) } catch ex { set e=ex.Name }', 'e,"|",x'))
        rec("j6b-escapes-codes", Tx(t, 'set o={} do o.%Set("s",$c(233)_$c(8364)_$c(127)_$c(31)) set j=o.%ToJSON(),c="" for i=1:1:$length(j) { set c=c_$ascii(j,i)_"," }', 'c'))
        rec("j20b-key-codes", Tx(t, 'set o={} do o.%Set($c(233),1) set j=o.%ToJSON(),c="" for i=1:1:$length(j) { set c=c_$ascii(j,i)_"," }', 'c'))
    # Native API decode of $LB values
    if "--part3" not in sys.argv:
      rec("l13-set", Tx(t, 'set ^IVGAuditEnv("lb",1)=$lb("a",1,,2.5,"",-3,$c(233),$c(8364),1E20,"1",1.0)', '"ok"'))
    try:
        import iris
        if "--part3" in sys.argv:
            raise RuntimeError("skipped in part 3")
        raw = ctl.o.getBytes("^IVGAuditEnv", "lb", 1)
        lst = iris.IRISList(raw)
        vals = []
        for i in range(1, lst.count() + 1):
            v = lst.get(i)
            vals.append([type(v).__name__, None if v is None else str(v)])
        rec("l13-native-irislist", vals)
    except Exception as e:  # noqa: BLE001
        rec("l13-native-irislist", "EXC " + repr(e)[:300])
    try:
        rec("l13b-native-get", repr(ctl.o.get("^IVGAuditEnv", "lb", 1))[:300])
    except Exception as e:  # noqa: BLE001
        rec("l13b-native-get", "EXC " + repr(e)[:200])
    # ---------------- $QUERY, MERGE, ZKILL, $SEQUENCE
    p4 = "--part4" in sys.argv
    if not p4:
      rec("q0-setup", Tx(t, 'kill ^IVGAuditEnv  set ^IVGAuditEnv("a",1)=1,^IVGAuditEnv("a",1,"x")=2,^IVGAuditEnv("a",2)=3,^IVGAuditEnv("a","10")=5,^IVGAuditEnv("a","b")=6,^IVGAuditEnv("b")=4', '"ok"'))
    if not p4:
        rec("q1-walk", Tx(t, 'set r="^IVGAuditEnv",s="" for { set r=$query(@r) quit:r=""  set s=s_r_"#"_$qlength(r)_"#"_$qsubscript(r,$qlength(r))_";" }', "s"))
    if not p4:
        rec("q2-name", Tx(t, 'set n=$name(^IVGAuditEnv("a",1,"x")),m=$name(^IVGAuditEnv("a",1),1)', 'n,"|",m,"|",$qsubscript(n,0),"|",$qsubscript(n,2)'))
    if not p4:
        rec("q3-query-reverse", Tx(t, 'set r=$query(^IVGAuditEnv("b"),-1)', "r"))
    if not p4:
        rec("m1-merge-rollback", Tx(t, 'tstart  merge ^IVGAuditEnv("c")=^IVGAuditEnv("a") set d1=$data(^IVGAuditEnv("c",1,"x")) trollback', 'd1,"|",$data(^IVGAuditEnv("c"))'))
    if not p4:
        rec("m2-merge-onto-existing", Tx(t, 'set ^IVGAuditEnv("d",1)="old",^IVGAuditEnv("d",9)="keep" merge ^IVGAuditEnv("d")=^IVGAuditEnv("a")', '$get(^IVGAuditEnv("d",1)),"|",$get(^IVGAuditEnv("d",9)),"|",$data(^IVGAuditEnv("d",1,"x"))'))
    if not p4:
        rec("z1-zkill-rollback", Tx(t, 'tstart  zkill ^IVGAuditEnv("a",1) set d1=$data(^IVGAuditEnv("a",1)) trollback', 'd1,"|",$data(^IVGAuditEnv("a",1)),"|",$get(^IVGAuditEnv("a",1))'))
    if not p4:
        rec("s1-sequence", Tx(t, 'kill ^IVGAuditEnv("s") set a=$sequence(^IVGAuditEnv("s")),b=$sequence(^IVGAuditEnv("s")),g1=$get(^IVGAuditEnv("s")) tstart  set c=$sequence(^IVGAuditEnv("s")) trollback  set e=$sequence(^IVGAuditEnv("s")),g2=$get(^IVGAuditEnv("s"))', 'a,"|",b,"|",c,"|",e,"|",g1,"|",g2'))
    if not p4:
        t2 = d.TermProc()
    if not p4:
        rec("s2-sequence-other", Tx(t2, 'set x=$sequence(^IVGAuditEnv("s")),y=$sequence(^IVGAuditEnv("s"))', 'x,"|",y'))
    if not p4:
        rec("s3-sequence-again", Tx(t, 'set x=$sequence(^IVGAuditEnv("s"))', 'x,"|",$get(^IVGAuditEnv("s"))'))
    if not p4:
        rec("s4-incr-after-seq", Tx(t, 'set x=$increment(^IVGAuditEnv("s"))', 'x'))
    if not p4:
        t2.close()
    # ---------------- TOP / LIMIT / ORDER BY collation (DB-API)
    for k in ("1", "2", "3", "10", "9", "a", "B", "c"):
        ctl.sql("INSERT INTO IVGAudit.T (k, v) VALUES (?, ?)", k, "v" + k)
    for name, q, p in [("t1-top2", "SELECT TOP 2 k FROM IVGAudit.T ORDER BY k", ()),
                       ("t2-top-param", "SELECT TOP ? k FROM IVGAudit.T ORDER BY k", (3,)),
                       ("t3-top0", "SELECT TOP 0 k FROM IVGAudit.T ORDER BY k", ()),
                       ("t4-order-all", "SELECT k FROM IVGAudit.T ORDER BY k", ()),
                       ("t5-order-desc", "SELECT TOP 2 k FROM IVGAudit.T ORDER BY k DESC", ()),
                       ("t6-limit", "SELECT k FROM IVGAudit.T ORDER BY k LIMIT 2", ()),
                       ("t7-limit-offset", "SELECT k FROM IVGAudit.T ORDER BY k LIMIT 2 OFFSET 1", ()),

                       ("t10-order-exact", "SELECT k FROM IVGAudit.T ORDER BY %EXACT(k)", ()),
                       ("t11-top-noorder", "SELECT TOP 3 k FROM IVGAudit.T", ()),
                       ("t12-top-all", "SELECT TOP ALL k FROM IVGAudit.T ORDER BY k", ())]:
        try:
            rec(name, [r[0] for r in ctl.sql(q, *p)])
        except Exception as e:  # noqa: BLE001
            rec(name, "EXC " + str(e)[:200])
    # FETCH FIRST: in a child process (x2-explore-4: the client process dumped core on the first form)
    import subprocess, os as _os
    for name, q in [("t8-fetch-first-ordered", "SELECT k FROM IVGAudit.T ORDER BY k FETCH FIRST 2 ROWS ONLY"),
                    ("t8b-fetch-first-plain", "SELECT k FROM IVGAudit.T FETCH FIRST 2 ROWS ONLY"),
                    ("t8c-fetch-first-zero", "SELECT k FROM IVGAudit.T FETCH FIRST 0 ROWS ONLY"),
                    ("t9-offset-fetch", "SELECT k FROM IVGAudit.T ORDER BY k OFFSET 2 ROWS FETCH NEXT 2 ROWS ONLY")]:
        script = ("import sys; sys.path.insert(0, %r)\nfrom iris_conn import Conn\nc = Conn('AUDITENV')\n"
                  "print('ROWS', [r[0] for r in c.sql(%r)])\nc.close()\n") % (str(Path(__file__).resolve().parents[2] / "tools"), q)
        try:
            r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60, env=_os.environ)
            rec(name, {"returncode": r.returncode, "stdout": r.stdout.strip()[-200:], "stderr": r.stderr.strip()[-300:]})
        except subprocess.TimeoutExpired:
            rec(name, "timeout")
    # ---------------- executemany
    ctl.sql("DELETE FROM IVGAudit.T")
    c = d.DbapiProc()
    cur = c.c.conn.cursor()
    try:
        cur.executemany("INSERT INTO IVGAudit.T (k, v) VALUES (?, ?)", [("1", "a"), ("2", "b"), ("1", "c"), ("3", "d")])
        rec("b1-executemany-dup", {"ok": True, "rowcount": cur.rowcount})
    except Exception as e:  # noqa: BLE001
        rec("b1-executemany-dup", {"exc": str(e)[:300], "rowcount": cur.rowcount})
    rec("b1-rows", sorted(r[0] for r in ctl.sql("SELECT k FROM %IGNOREINDEX * IVGAudit.T")))
    rec("b1-tlevel", int(c.o.getTLevel()))
    ctl.sql("DELETE FROM IVGAudit.T")
    c.o.tStart()
    try:
        cur.executemany("INSERT INTO IVGAudit.T (k, v) VALUES (?, ?)", [("1", "a"), ("2", "b"), ("1", "c"), ("3", "d")])
        rec("b2-executemany-dup-txn", {"ok": True, "rowcount": cur.rowcount})
    except Exception as e:  # noqa: BLE001
        rec("b2-executemany-dup-txn", {"exc": str(e)[:300]})
    rec("b2-rows-open", sorted(r[0] for r in ctl.sql("SELECT k FROM %IGNOREINDEX * IVGAudit.T")))
    rec("b2-tlevel", int(c.o.getTLevel()))
    c.o.tRollback()
    rec("b2-rows-after-rollback", sorted(r[0] for r in ctl.sql("SELECT k FROM %IGNOREINDEX * IVGAudit.T")))
    try:
        cur.executemany("INSERT INTO IVGAudit.T (k, v) VALUES (?, ?)", [("4", "a"), ("5", "b")])
        rec("b3-executemany-ok", {"rowcount": cur.rowcount})
    except Exception as e:  # noqa: BLE001
        rec("b3-executemany-ok", {"exc": str(e)[:300]})
    cur.close()
    # autocommit off executemany with failure
    ctl.sql("DELETE FROM IVGAudit.T")
    c.c.conn.setAutoCommit(False)
    cur = c.c.conn.cursor()
    try:
        cur.executemany("INSERT INTO IVGAudit.T (k, v) VALUES (?, ?)", [("1", "a"), ("1", "c")])
        rec("b4-ac-off", {"ok": True})
    except Exception as e:  # noqa: BLE001
        rec("b4-ac-off", {"exc": str(e)[:200]})
    rec("b4-tlevel", int(c.o.getTLevel()))
    c.c.conn.rollback()
    rec("b4-rows-after-rollback", sorted(r[0] for r in ctl.sql("SELECT k FROM %IGNOREINDEX * IVGAudit.T")))
    c.c.conn.setAutoCommit(True)
    cur.close()
    # ---------------- INSERT OR UPDATE
    ctl.sql("DELETE FROM IVGAudit.T")
    cur = c.c.conn.cursor()
    cur.execute("INSERT OR UPDATE IVGAudit.T (k, v) VALUES ('1', 'a')")
    rec("u1-insert", cur.rowcount)
    cur.execute("INSERT OR UPDATE IVGAudit.T (k, v) VALUES ('1', 'b')")
    rec("u1-update", cur.rowcount)
    rec("u1-rows", [list(map(str, r)) for r in ctl.sql("SELECT k, v FROM IVGAudit.T")])
    cur.close()
    # concurrency: c holds an uncommitted insert of k=2; another process upserts k=2
    c.o.tStart()
    cur = c.c.conn.cursor()
    cur.execute("INSERT INTO IVGAudit.T (k, v) VALUES ('2', 'x')")
    p2 = d.DbapiProc()
    a = d.Async(lambda: p2._q("INSERT OR UPDATE IVGAudit.T (k, v) VALUES ('2', 'y')"))
    r1 = a.wait(1.0)
    rec("u2-upsert-vs-uncommitted-insert-issue", "pending" if r1 is None else r1)
    c.o.tRollback()
    r2 = a.wait(5.0) if r1 is None else r1
    rec("u2-after-holder-rollback", r2)
    rec("u2-rows", [list(map(str, r)) for r in ctl.sql("SELECT k, v FROM IVGAudit.T")])
    # c holds an uncommitted update of k=1; another process upserts k=1
    c.o.tStart()
    cur.execute("UPDATE IVGAudit.T SET v = 'z' WHERE k = '1'")
    a = d.Async(lambda: p2._q("INSERT OR UPDATE IVGAudit.T (k, v) VALUES ('1', 'w')"))
    r1 = a.wait(1.0)
    rec("u3-upsert-vs-uncommitted-update-issue", "pending" if r1 is None else r1)
    c.o.tCommit()
    r2 = a.wait(5.0) if r1 is None else r1
    rec("u3-after-holder-commit", r2)
    rec("u3-rows", [list(map(str, r)) for r in ctl.sql("SELECT k, v FROM IVGAudit.T ORDER BY k")])
    # upsert inside a txn then rollback
    p2.o.tStart()
    p2._q("INSERT OR UPDATE IVGAudit.T (k, v) VALUES ('1', 'q')")
    p2._q("INSERT OR UPDATE IVGAudit.T (k, v) VALUES ('5', 'q')")
    rec("u4-dirty", [list(map(str, r)) for r in ctl.sql("SELECT k, v FROM IVGAudit.T ORDER BY k")])
    p2.o.tRollback()
    rec("u4-after-rollback", [list(map(str, r)) for r in ctl.sql("SELECT k, v FROM IVGAudit.T ORDER BY k")])
    cur.close()
    p2.close()
    c.close()
finally:
    t.close()
    d.reset(ctl)
    ctl.close()
