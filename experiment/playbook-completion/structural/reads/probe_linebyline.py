"""Feasibility probe 3: %Monitor.System.LineByLine (instance monitor, started and stopped inside this one lock hold, as
correspondence/tools/monitor.py does) around one product reader (Graph.KG.Edgeless.LonersJson in AUDITD): which INT
lines ran, and whether that tells which globals/rows were read. Stopped in a finally block."""
import json, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'live'))
import lib
RTN = "Graph.KG.Edgeless.1"
out = {}
c = lib.conn()
lib.reset(c)
e = lib.engine(c)
for n in ("a", "b", "z"):
    e.create_node(n, graph="g1")
e.create_edge("a", "R", "b", graph="g1")
for n in ("a", "q"):
    e.create_node(n, graph="g2")
c.conn.commit()
try:
    s = lib.session(' set sc=##class(%Monitor.System.LineByLine).Start($lb("' + RTN + '"),$lb("RtnLine","GloRef"),"")'
                    ' write $c(30),"START|",$system.Status.IsOK(sc),"|",$system.Status.GetErrorText(sc),!\n halt\n')
    out["start"] = lib.marked(s, "START")
    ans = str(c.call("Graph.KG.Edgeless", "LonersJson", "Graph_KG", "g1", "", 100))
    out["answer"] = ans
    r = lib.session(' set rs=##class(%ResultSet).%New("%Monitor.System.LineByLine:Result")'
                    ' set sc=rs.Execute("' + RTN + '") set n=0'
                    ' while rs.Next() { set n=n+1 set v=rs.GetData(1) if $listvalid(v),$lg(v,1) write $c(30),"L|",n,"|",$listtostring(v,","),! }'
                    ' write $c(30),"END|",n,!\n halt\n')
    out["executed_int_lines"] = lib.marked(r, "L")[:80]
    out["int_lines_total"] = lib.marked(r, "END")
finally:
    st = lib.session(' set sc=##class(%Monitor.System.LineByLine).Stop() write $c(30),"STOP|",$system.Status.IsOK(sc),"|",##class(%Monitor.System.LineByLine).IsActive(),!\n halt\n')
    out["stop"] = lib.marked(st, "STOP")
lib.reset(c)
c.close()
lib.dump(lib.OUT / "reads" / "probe-linebyline.json", out)
print(json.dumps(out, indent=1)[:4000])
