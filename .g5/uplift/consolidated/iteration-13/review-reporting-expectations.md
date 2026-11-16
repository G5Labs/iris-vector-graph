# Independent routine-reporting review panel

Frozen from restored iteration12 owners and pinned primary docs/tests/production source before inspecting the new `routine_reporting` candidate. Product3eaa79cf77d3e0a879b2cced634cf2729d81499e; baseline198365a3e726bac66d5c67901a1b86e2238cbc47. Purposive ordinary workflow review, not population/private grading. Interrupted work and related inputs remain unpursued/unassessed and are not evidence here. No native/network execution.

| ID | Material neighbors and expected observation |
| --- | --- |
| R1 | Default versus named graph raw node rows: omitted/None/empty graph count only default; named counts only that graph. NULL structural graph cells coalesce to default in these SQL counters. |
| R2 | Same node ID across graphs versus repeated label/edge rows: graph-scoped counts are row counts under actual table/key frames; graph+ID identity and edge multiplicity must not be replaced by bare-ID sets. |
| R3 | No label filter versus label filter: node-table count differs from matching label-row count; orphan/duplicate child rows need an explicit physical-table correspondence frame. |
| R4 | No predicate versus predicate filter: edge count includes every parallel physical edge satisfying graph/predicate, not distinct triples or adjacency coordinates. |
| R5 | Two labels with unequal counts versus ties: label distribution derives GROUP BY counts and descending-count order; tie order is not promised beyond the provider's actual contract. |
| R6 | Valid graph versus invalid graph name: actual validator refuses before SQL; admitted graph-name codec is explicit, not a supplied valid flag or a proof of all normalization. |
| R7 | Empty table versus count query failure: ordinary count methods return0 only for actual empty counts; provider failures propagate instead of fabricated zero results. |
| R8 | Engine counters versus status: status table totals span every graph; its Graph line explicitly says 'in every graph'. Default-graph totals cannot be substituted for namespace census. |
| R9 | Legacy embedding table only versus legacy plus routed tables: status sums actual per-table row counts of the selected kind, deriving table inventory from raw registry cells. |
| R10 | Node/edge route kinds, absent kind and misleading names: kind defaults to node for old/null rows; recorded kind decides inclusion; allowed route-name fragment is still checked. An optimized mirror is excluded from node totals. |
| R11 | Duplicate/case-varied registry table names versus distinct routes: actual case-insensitive seen set avoids double counting; preserve the chosen raw spelling/provider relation. |
| R12 | Registry absent (-30) versus another registry read error: absence retains legacy totals without a missing-registry error; other failures retain legacy totals and append an explicit registry error. Do not supply the registry outcome as the final answer. |
| R13 | Listed route present versus its count query failing: failed table contributes no numeric count and remains visible in errors; the overall sum is partial rather than a claimed complete census. |
| R14 | Graph/node/edge probe success versus failure: failed graph probe marks graph unknown, so report Graph is unknown rather than a valid zero graph. Other component failures need their actual part-specific propagation, not blanket guessed unknown flags. |
| R15 | Node-vector count failure versus edge-vector count failure: actual node-vector wrapper marks vector_index unknown when errors grow; preserve error-list composition and do not assume every error sets the same status flag. |
| R16 | First-access schema refusal versus available schema: status reports refusal, recorded schema/legacy count and unknown parts without running remaining probes; it is an inspection API allowed by the schema-refusal owner. |
| R17 | No schema record/other probe problem versus refusal: report errors accurately and preserve which probes may proceed; do not turn every status error into the same short circuit. |
| R18 | Data producer → TableCounts/unknown/errors → report(): report Graph, index and probe-error text must read actual derived fields, not supplied labels/complete booleans or independently prepared counts. |
| R19 | Successful report versus failed/partial providers: actual Python/SQL adapters may establish bounded correspondence; native schema/global/index bodies, all status probes and arbitrary formatting/collation remain qualified. No direct native-body credit. |
| R20 | Shared counter/registry helpers and report readers: identify the actual deciding/filtering/deduplicating/adding/error writers and final reader. Existing scope/readiness/route models can be substantive partial hits without proving the raw census/report composition. |

Authority: API_REFERENCE get_node_count/get_edge_count/get_label_distribution/status; USER_GUIDE default-graph rule; tests/unit/test_460_r219_counts_default_graph.py, test_460_r249_counters_default_graph.py, test_230_status_counts.py, test_460_r050_status_counts_every_graph.py. Production source inspected: SchemaMixin counts/distribution; AdminMixin embedding-table inventory/counts/status/_status_schema/_status_probes; TableCounts/EngineStatus.report. Governing owners include graph.membership/default and install.schema.refusal/not_ready/setup.resume. A dedicated routine count/report commitment is not assumed to exist before inspection of the current foundation.
