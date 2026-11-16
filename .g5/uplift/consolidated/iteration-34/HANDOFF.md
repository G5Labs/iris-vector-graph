# Iteration 34: Python property readers (a Low finding and a known question)

Before image: seal 33 `f5d4805a`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-retest-20261116-iris`.

## W40

The strongest remaining candidate at the step-5 check: ten public property readers with no owner and no binding,
reading API-written typed values. Predictions frozen from the API reference ([property-readers-PAIRS.md](property-readers-PAIRS.md)).

- Held or resolved: text matching of `val` ("7" finds 7 and "7"; "true" finds true), `get_node_properties`,
  `get_nodes_by_label`, `nodes_exist` (every graph), `list_graphs` (graphs with edges).
- **Missed, known**: `get_node_ids_by_property`, `get_property_values`, `get_property_pairs` read every graph while
  `get_nodes_by_property` reads the default graph — already open question HD-0201; evidence added to its card.
- **Missed, new Low bug-str-102**: `get_property_values`/`get_property_pairs` return a stored boolean as `"true"`.
- New owner statement [structure.node.read.properties](../../../ontology/features/graph-structure.g5.md#structure.node.read.properties)
  (348 blocks). No formal contract: a probe-only claim, open in Verus.

## Cost correction

The pointers sealed with iterations 25-33 gave builder wall-clock estimates of "about 1 h" to "about 5 h 50 min";
those were wrong. From the session start (21:15:04Z) and the commit times, the seals of iterations 25-33 came at 20, 34,
42, 47, 51, 55, 64, 66 and 70 minutes. Tokens and currency are unavailable.
