"""Remove the %NOINDEX rows journal candidate J07 (BulkLoader.load_edges, default use_noindex=True) left in AUDITA:
erase_graph did not see them (indexed reads skip %NOINDEX rows, P-0304). Same pattern as the upstream test's cleanup."""
from probe_lib import conn
c = conn()
q = "SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE %NOINDEX graph_id %STARTSWITH 'baj07'"
print("J07 edge rows before (non-indexed scan):", c.sql(q))
print("J07 edge rows before (indexed read):", c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id %STARTSWITH 'baj07'"))
print("J07 node rows before:", c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE %NOINDEX graph_id %STARTSWITH 'baj07'"))
cur = c.conn.cursor()
cur.execute("DELETE %NOINDEX FROM Graph_KG.rdf_edges WHERE %NOINDEX graph_id %STARTSWITH 'baj07'")
cur.execute('BUILD INDEX FOR TABLE Graph_KG.rdf_edges INDEX "%%DDLBEIndex"')
cur.execute("DELETE FROM Graph_KG.nodes WHERE graph_id %STARTSWITH 'baj07'")
c.conn.commit()
cur.close()
print("J07 edge rows after:", c.sql(q), "nodes after:", c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE %NOINDEX graph_id %STARTSWITH 'baj07'"))
c.close()
