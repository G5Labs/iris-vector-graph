import json, os, sys, time
sys.path.insert(0, os.environ["IT36"]); import runtime
c = runtime.connect(); e = runtime.engine(c); TAG = time.strftime("%H%M%S", time.gmtime()); F = os.environ["F"]
pf, uri = f"exb{TAG}", f"http://example.org/b{TAG}/"
e.register_namespace(pf, uri)
e.create_node(uri + "n1", labels=["Thing"]); e.create_node(uri + "n2"); e.create_edge(uri + "n1", uri + "rel", uri + "n2")
e.export_rdf(F + f"/c9b-{TAG}.ttl", node_ids=[uri + "n1"])
e.export_rdf_from_cypher(f"MATCH (a {{node_id: '{uri}n1'}})-[r]->(b) RETURN a.node_id AS s, type(r) AS p, b.node_id AS o", F + f"/c9c-{TAG}.ttl")
t1 = open(F + f"/c9b-{TAG}.ttl").read(); t2 = open(F + f"/c9c-{TAG}.ttl").read()
print(json.dumps({"export_rdf_declares": f"@prefix {pf}:" in t1, "export_rdf_uses": f"{pf}:" in t1,
                  "from_cypher_declares": f"@prefix {pf}:" in t2, "from_cypher_uses": f"{pf}:" in t2}))
