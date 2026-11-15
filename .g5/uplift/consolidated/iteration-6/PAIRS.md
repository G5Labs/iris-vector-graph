# Source-frozen iteration 6 temporal questions

Product3eaa79cf; foundation47236c82. These builder cases were selected from actual
snapshot/TemporalIndex/TemporalWindow sources and tests before the new candidate.
No private draw or independent prevalence sample is claimed.

- T1: same (source,predicate,target) at timestamp0 in default and named graphs,
  weights1 and2. After save/erase/replace restore, each graph's inclusive[0,0]
  one-call and paged reader must see its own weight; omission of default graph or
  epoch keys by a zero-start walk loses a legitimate outcome.
- T2: named graph holds one ordinary event and a second event written with reverse
  index suppressed, plus typed attributes. Restore must preserve outgoing events,
  only the existing inbound event, attribute values and omitted-versus-empty source
  filter. Page size1 must continue through its final done page.
- T3: an archive declaring another layout refuses before erase; a live sentinel
  node and both temporal windows remain unchanged. Missing layout is admitted as
  built; this does not authorize claiming malformed old globals are compatible.
- T4: a temporal global line that cannot be written should stop/report failure by
  the intended snapshot-failure rule. Actual _import_global_from_ndjson catches
  per-line errors and can still report restored_globals KG with failed_rows empty.
  Retain both intended failure and as-built result; match inherited F-C1802 rather
  than count a new bug. Valid neighboring rows must survive.

Authority: tests/integration/test_snapshot_inventory.py::test_the_restored_temporal_edge_answers_a_window_query,
tests/unit/test_snapshot_inventory.py (zero graph/timestamp sentinel); snapshot.py
STORE_PLAN/export/import/restore; TemporalIndex.WriteStores/QueryWindow;
TemporalWindow.Open/Page/Row; temporal.py public one-call and paged consumers.
No proof currently derives restore to these readers; existing paging contracts
will be reused under stamped dependency inputs, with fresh native round trips.
