def get_nodes(
    self, node_ids: List[str], graph: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve multiple nodes by ID using optimized batch SQL.

    Eliminates N+1 query patterns by fetching all labels and properties
    for a set of nodes in two efficient queries.

    Args:
        node_ids: List of node identifiers
        graph: Named graph to read from; omitted means the default graph. Every
            statement below is scoped to it — spec 227 allows one node ID in several
            graphs, and an unscoped read merged their label lists and let one graph's
            property values overwrite another's.

    Returns:
        List of node dicts with 'id', 'labels', and properties
    """
    if not node_ids:
        return []

    graph_id = DEFAULT_GRAPH if graph is None else graph

    _IN_CHUNK = 499

    cursor = self.conn.cursor()
    node_map = {nid: {"id": nid, "labels": []} for nid in node_ids}

    for i in range(0, len(node_ids), _IN_CHUNK):
        chunk = node_ids[i : i + _IN_CHUNK]
        placeholders = ",".join(["?"] * len(chunk))

        cursor.execute(
            f"SELECT s, label FROM {self._t('rdf_labels')} "
            f"WHERE graph_id = ? AND s IN ({placeholders})",
            [graph_id] + list(chunk),
        )
        for s, label in cursor.fetchall():
            if s in node_map:
                node_map[s]["labels"] = [label]

        # R218: CY_TYPED reads a value stored as a number (a Cypher write's) as that number under
        # every driver version; 5.4.1 read it as IRIS text (.94999999999999995559)
        cursor.execute(
            f'SELECT s, "key", {self._ivg_schema}.CY_TYPED(val) FROM {self._t("rdf_props")} '
            f"WHERE graph_id = ? AND s IN ({placeholders})",
            [graph_id] + list(chunk),
        )
        _STRUCTURAL_KEYS = ("id", "labels")
        for s, key, val in cursor.fetchall():
            if s in node_map:
                store_key = f"p_{key}" if key in _STRUCTURAL_KEYS else key
                # a list or map by the rule every Cypher read uses (4.6.0 R307), else 'true' / 'false'
                node_map[s][store_key] = read_node_value(val)

    empty_nids = [
        nid for nid, data in node_map.items() if not data["labels"] and len(data) <= 2
    ]
    if empty_nids:
        existing_empty: set = set()
        for i in range(0, len(empty_nids), _IN_CHUNK):
            chunk = empty_nids[i : i + _IN_CHUNK]
            e_placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(
                f"SELECT node_id FROM {self._t('nodes')} "
                f"WHERE graph_id = ? AND node_id IN ({e_placeholders})",
                [graph_id] + list(chunk),
            )
            existing_empty.update(row[0] for row in cursor.fetchall())
        return [
            node_map[nid]
            for nid in node_ids
            if nid in existing_empty or nid not in empty_nids
        ]

    return [node_map[nid] for nid in node_ids if nid in node_map]
