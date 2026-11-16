def export_graph_ndjson(self, path: str) -> dict:
    """Write the default graph to ``path`` as NDJSON: a ``{"kind": "node", ...}`` line per node, with its
    labels and properties, then a ``{"kind": "edge", ...}`` line per edge, with its ``qualifiers``.

    ``import_graph_ndjson`` reads the file back into the same graph. Named graphs are not written, nor are
    temporal edges (``export_temporal_edges_ndjson`` writes those). Returns ``{"nodes": n, "edges": m}``,
    the lines written.
    """
    from iris_vector_graph.constants import TEMPORAL_MARKED_ROW

    nodes_written = 0
    edges_written = 0

    cursor = self.conn.cursor()
    try:
        with open(path, "w") as f:
            cursor.execute(
                f"SELECT node_id FROM {self._t('nodes')} WHERE graph_id = '' ORDER BY node_id"
            )
            for (node_id,) in cursor.fetchall():
                node_data = self.get_node(node_id, graph="named")
                if node_data:
                    event = {
                        "kind": "node",
                        "id": node_id,
                        "labels": node_data.get("labels", []),
                        "properties": {
                            k: v for k, v in node_data.items() if k not in ("id", "labels")
                        },
                    }
                    f.write(json.dumps(event) + "\n")
                    nodes_written += 1

            # R088: the edges. A temporal edge's marked row (ADR-0009) belongs to the temporal export.
            cursor.execute(
                f"SELECT s, p, o_id, qualifiers FROM {self._t('rdf_edges')} WHERE graph_id = '' "
                f"AND (qualifiers IS NULL OR NOT ({TEMPORAL_MARKED_ROW})) ORDER BY edge_id"
            )
            for s, p, o, quals in cursor.fetchall():
                event = {"kind": "edge", "source": s, "predicate": p, "target": o}
                quals = json.loads(quals) if quals else None
                if quals:
                    event["qualifiers"] = quals
                f.write(json.dumps(event) + "\n")
                edges_written += 1
    finally:
        cursor.close()
    return {"nodes": nodes_written, "edges": edges_written}
