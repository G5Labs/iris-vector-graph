"""Feasibility probe 2: %SYS.PTools per-job SQL statistics (setSQLStatsFlagJob) in the harness connection's own
process: does it observe (a) a harness dynamic statement, (b) the product's Python-issued dynamic SQL, (c) the
product's embedded SQL (&sql in Graph.KG classes compiled before the flag was set)? Flag set for this job only and
reset to 0 at the end; the job's StatsSQL rows are listed (they are instrumentation, not product data)."""
import json, sys, uuid
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'live'))
import lib
out = {}
c = lib.conn()
lib.reset(c)
e = lib.engine(c)
e.create_node("rd:a", labels=["L"], properties={"k": "v"}); c.conn.commit()
cols = c.sql("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='%SYS_PTools' AND TABLE_NAME='StatsSQL'")
out["columns"] = [x[0] for x in cols]
out["flag_before"] = str(c.call("%SYSTEM.SQL.PTools", "getSQLStatsFlagByPID", c.pid))
out["set"] = str(c.call("%SYSTEM.SQL.PTools", "setSQLStatsFlagJob", 2))
try:
    nb = c.sql("SELECT COUNT(*) FROM %SYS_PTools.StatsSQL")[0][0]
    tag = "ivgauditdrd" + uuid.uuid4().hex[:8]
    c.sql(f"SELECT COUNT(*) AS {tag} FROM Graph_KG.nodes WHERE node_id = ?", "rd:a")
    e.get_node("rd:a")                                  # product Python SQL
    c.call("Graph.KG.Ledger", "State")                  # product ObjectScript (globals)
    c.call("Graph.KG.Eraser", "EraseAll")               # product embedded SQL cursor
    c.conn.commit()
    rows = c.sql("SELECT * FROM %SYS_PTools.StatsSQL")
    out["rows_before"] = nb
    out["rows_after"] = len(rows)
    out["rows"] = [[str(v)[:120] for v in r] for r in rows[-40:]]
finally:
    out["unset"] = str(c.call("%SYSTEM.SQL.PTools", "setSQLStatsFlagJob", 0))
lib.reset(c)
c.close()
lib.dump(lib.OUT / "reads" / "probe-ptools.json", out)
print(json.dumps(out, indent=1)[:5000])
