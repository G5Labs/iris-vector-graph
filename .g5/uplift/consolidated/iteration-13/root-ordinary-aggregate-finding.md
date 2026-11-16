<a id="bug-agg-001"></a>
### A leading grouped OPTIONAL MATCH with no matches returns NULL for SUM instead of zero

Severity: Low · Decision: Open

Run: Ordinary consolidated iteration13, 2026-11-15

Found by: the fresh aggregate source survey, actual local SQL caller contrasts, [prospective native neighbors](../uplift/consolidated/iteration-13/root-optional-aggregate-PAIRS.md), [four actual native caller observations](../uplift/consolidated/iteration-13/root-optional-aggregate-native.json), and [independent29-check fact audit](../uplift/consolidated/iteration-13/review-optional-aggregate-audit.json) with [authority/dedup triage](../uplift/consolidated/iteration-13/review-optional-aggregate-triage.md). This is a source-informed ordinary discovery, not private evaluation or an assessment of interrupted work.

Reproduced by: actual pinned SQL-path execute_cypher on the task-owned IRIS, using only a fresh graph, one new anchor and a never-created unique label. No namespace census, unrelated data, supplied result rows, injected provider error or product patch.

Expected: [query.aggregation](../ontology/features/cypher.g5.md#query.aggregation). The newer [R308 regression](../../tests/unit/test_460_r308_guards.py#L53) explicitly says openCypher SUM over no values is0 and requires zero for an all-null group. A synthetic optional row contributes to COUNT(*) but supplies no value to SUM.

Observed: leading `OPTIONAL MATCH (n:Missing) RETURN n.kind, count(*), count(n), sum(n.x), avg(n.x), collect(n.x)` in the fresh graph returns `[null,1,0,null,null,[]]`. The sum should be0. Ordinary empty global MATCH returns `[0,0,0,null,[]]`, leading global OPTIONAL returns `[1,0,0,null,[]]`, and an anchored missing OPTIONAL returns `[1,0,0,null,[]]`. All four source forecasts agree with the actual calls; only the grouped fallback differs from the prospectively recorded zero-sum reference. The fixture and anchor readback are retained in the raw receipt.

Cause and authority: `_null_row_aggregate` supplies SQL NULL for SUM, and a leading grouped OPTIONAL materializes that value in its synthetic UNION fallback rather than passing through the ordinary SUM zero-if-null expression. The older [R298 helper unit](../../tests/unit/test_460_r298_fixes46_leftovers.py#L28) explicitly tests that NULL as built. Root preserves this source tension and follows the newer, explicit all-null-group SUM requirement; the helper test does not justify different public SUM results by query shape. F-0823 concerns a different empty CALL result with max/avg/collect, not this grouped OPTIONAL SUM root.

Consequence: an ordinary report can receive a missing metric instead of a numeric zero when it adds a grouping key to an unmatched OPTIONAL query. Low reflects this narrow read-result consequence; no data loss or wider aggregation failure is claimed.

Repair proposal (not implemented): return a numeric zero for SUM in the synthetic no-value fallback and preserve its final type, while retaining COUNT(*)1, COUNT(value)0, AVG null and COLLECT[]. Keep ordinary/global/grouped/anchored neighbors separate. The ordinary aggregate model's SQL-fold domain remains qualified; this OPTIONAL caller boundary is observed and still partial in Verus, not a new active source binding or executable-body proof. No product repair or owner decision is recorded.
