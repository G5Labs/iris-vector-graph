def import_graph_ndjson(
    self,
    path: str,
    upsert_nodes: bool = True,
    batch_size: int = 10000,
    graph: str = None,
) -> dict:
    """Write the nodes, edges and temporal edges an NDJSON file describes, one JSON object a line.

    Lines are ``{"kind": "node"|"edge"|"temporal_edge", ...}``, or the ledger's reconstruction export
    form (``{"type": "node"|"rel", ...}``). Nodes and edges go into ``graph``, else an edge line's own
    ``graph``; temporal edges are written in batches of ``batch_size`` to the default graph, and with
    ``upsert_nodes`` their endpoints are created there first. An edge line names its endpoints ``source``
    and ``target`` (or ``source_id`` and ``target_id``). Malformed lines, lines of an unknown kind, and node or
    edge lines missing their id, source, predicate or target are logged with their line number and skipped.
    Returns ``nodes``, ``edges`` and ``temporal_edges``, the lines processed (not rows created), and
    ``skipped``, the lines skipped.
    """
    _ledger_check(self, "import_graph_ndjson")
    nodes = 0
    edges = 0
    temporal_edges = 0
    skipped = 0
    temporal_batch = []

    with open(path, "r") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("import_graph_ndjson: skipping malformed NDJSON line %d", lineno)
                skipped += 1
                continue
            if not isinstance(event, dict):
                logger.warning("import_graph_ndjson: skipping line %d, not a JSON object", lineno)
                skipped += 1
                continue

            kind = event.get("kind", "")
            # spec 213: reconstruction exports use {"type": "node"|"rel", ...}
            etype = event.get("type", "")
            if not kind and etype == "node":
                kind = "node"
                event = {
                    "kind": "node",
                    "id": event.get("id", ""),
                    "labels": event.get("labels", []),
                    "properties": event.get("props", event.get("properties", {})),
                }
            elif not kind and etype == "rel":
                kind = "edge"
                event = {
                    "kind": "edge",
                    "source": event.get("s", ""),
                    "predicate": event.get("p", ""),
                    "target": event.get("o", ""),
                    "graph": event.get("graph"),
                    "qualifiers": event.get("quals") or None,
                }

            if kind == "node":
                node_id = event.get("id", "")
                labels = event.get("labels", [])
                props = event.get("properties", {})
                if node_id:
                    # spec 214 FR-015: pass graph to scope import into a named graph
                    self.create_node(node_id, labels=labels, properties=props, graph=graph)
                    nodes += 1
                else:
                    logger.warning("import_graph_ndjson: skipping line %d, a node with no 'id'", lineno)
                    skipped += 1

            elif kind == "edge":
                src = event.get("source") or event.get("source_id", "")
                pred = event.get("predicate", "")
                tgt = event.get("target") or event.get("target_id", "")
                if not (src and pred and tgt):
                    # R213: this was skipped without a word, so a file keyed source_id/target_id loaded 0 edges
                    logger.warning(
                        "import_graph_ndjson: skipping line %d, an edge without source, predicate and target", lineno
                    )
                    skipped += 1
                else:
                    event_graph = event.get("graph")
                    quals = event.get("qualifiers")
                    # spec 214 FR-015: if graph= param supplied, it overrides per-line graph
                    effective_graph = graph if graph is not None else event_graph
                    if effective_graph is not None or (quals and any(quals.values())):
                        self.create_edge(
                            src, pred, tgt, qualifiers=quals or None, graph=effective_graph
                        )
                    else:
                        self.create_edge(src, pred, tgt)
                    edges += 1

            elif kind == "temporal_edge":
                src = event.get("source", "")
                pred = event.get("predicate", "")
                tgt = event.get("target", "")
                ts = event.get("timestamp", 0)
                w = event.get("weight", 1.0)
                attrs = event.get("attrs", {})
                src_labels = event.get("source_labels", [])
                tgt_labels = event.get("target_labels", [])
                if upsert_nodes:
                    if src:
                        self.create_node(src, labels=src_labels)
                    if tgt:
                        self.create_node(tgt, labels=tgt_labels)
                item = {"s": src, "p": pred, "o": tgt, "ts": ts, "w": w}
                if attrs:
                    item["attrs"] = {k: str(v) for k, v in attrs.items()}
                temporal_batch.append(item)
                if len(temporal_batch) >= batch_size:
                    self.bulk_create_edges_temporal(temporal_batch)
                    temporal_edges += len(temporal_batch)
                    temporal_batch = []
            else:
                logger.warning("import_graph_ndjson: skipping line %d, unknown NDJSON kind %r", lineno, kind)
                skipped += 1

    if temporal_batch:
        self.bulk_create_edges_temporal(temporal_batch)
        temporal_edges += len(temporal_batch)

    return {"nodes": nodes, "edges": edges, "temporal_edges": temporal_edges, "skipped": skipped}
