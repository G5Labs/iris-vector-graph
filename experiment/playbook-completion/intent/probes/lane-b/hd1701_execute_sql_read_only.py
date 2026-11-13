"""HD-1701 probe: does IRISGraphStore.execute_sql(..., read_only=True) refuse a write?

Oracle (working assumption, not a stated contract): read_only=True is a requested guarantee, so a DML or DDL
statement passed with it must be refused before it runs. Alternatives: the flag is advisory (as built).
No document states what read_only means for execute_sql; the GraphStore protocol (store_protocol.py:18) only
declares it with default True.

Uses namespace AUDITIB, node ids prefixed ib2_ and the scratch table IVGAudit.ib2_ro; removes both at the end.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))
from iris_conn import Conn  # noqa: E402

from iris_vector_graph import IRISGraphStore  # noqa: E402

NODE = "ib2_ro_probe_1"
c = Conn("AUDITIB")
try:
    store = IRISGraphStore(c.conn, namespace="AUDITIB")
    c.sql("DELETE FROM Graph_KG.nodes WHERE node_id = ?", NODE)
    c.conn.commit()
    before = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", NODE)[0][0]

    r_dml = store.execute_sql("INSERT INTO Graph_KG.nodes (node_id, graph_id) VALUES (?, '')", [NODE], read_only=True)
    c.conn.commit()
    after = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", NODE)[0][0]
    print(f"DML  read_only=True: error={r_dml.error!r} rows_before={before} rows_after={after}")

    exists_q = "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'IVGAudit' AND TABLE_NAME = 'ib2_ro'"
    if c.sql(exists_q)[0][0]:
        c.sql("DROP TABLE IVGAudit.ib2_ro")
    r_ddl = store.execute_sql("CREATE TABLE IVGAudit.ib2_ro (x INT)", [], read_only=True)
    ddl_created = c.sql(exists_q)[0][0]
    print(f"DDL  read_only=True: error={r_ddl.error!r} table_created={ddl_created}")

    r_upd = store.execute_sql("UPDATE Graph_KG.nodes SET graph_id = '' WHERE node_id = ?", [NODE], read_only=True)
    print(f"UPD  read_only=True: error={r_upd.error!r}")

    dml_refused = bool(r_dml.error) and after == before
    ddl_refused = bool(r_ddl.error) and not ddl_created
    print(f"ORACLE (working assumption) refuse writes under read_only=True: dml_refused={dml_refused} ddl_refused={ddl_refused}")
    print("OUTCOME:", "pass" if (dml_refused and ddl_refused) else "expected-violation (flag ignored; writes ran)")
finally:
    try:
        c.sql("DELETE FROM Graph_KG.nodes WHERE node_id = ?", NODE)
        if c.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'IVGAudit' AND TABLE_NAME = 'ib2_ro'")[0][0]:
            c.sql("DROP TABLE IVGAudit.ib2_ro")
        c.conn.commit()
        left = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'ib2_ro'")[0][0]
        print(f"cleanup: ib2_ro nodes left={left}")
    finally:
        c.close()
