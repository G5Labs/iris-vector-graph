# G03-temporal fork report (saved by the integrator; verbatim content)

G03-temporal regrade is done: all 139 rows are in `scratch/iteration-64/forks/G03-temporal/rows.tsv`. That covers 92 full and 47 absent rows; the three erasure ids the brief reserves for the integrator were not touched. Nothing in the repo was edited and no Verus run was made.

**1. Counts**
- Full rows (92): 67 stay full, 25 drop to partial, none drop to absent.
- Absent rows (47): 42 stay absent, 4 rise to partial, 1 rises to full.
- check_scope full → narrowed: 18 in total. 13 are on rows that stay full: clock#o10, retry#o02–#o04, after-purge#o02, #o03, #o05, #o06, stats.window#o04, sources#o02, release#o04, release#o09 and ledger.atomic#o02. The other 5 are on rows that dropped to partial.
- Statements fixed: 1 (temporal.write.collision#o01).
- Overlay: exit 0. "rows reviewed: 139; problems naming them: 0; errors: 0 | absent->absent 42, absent->full 1, absent->partial 4, full->full 67, full->partial 25, scope full->narrowed 18, scope n/a->narrowed 3, statement changed 1".
- Rows that stay full: any gap left on them now starts with `outside-statement:` (6 rows); refutation text moved from `gap` to `premises` as "refutes: …"; every `check_scope full` row whose proofs have a `requires` carries a `requires-reviewed:` note; five rows got extra theorem locators documenting the composition. Generator: `make_rows.py`.

**2. Changed rows**

| id | old → new | checklist | reason |
|---|---|---|---|
| temporal.edge#o05 | full → partial | c, d | The bucket divisor is a parameter; that the engine uses only the seconds class is inspection only. |
| temporal.edge.clock#o10 | scope full → narrowed | e | The only proof is a point check; it decides exactly the two stated inputs. |
| temporal.write#o05 | full → partial | a, c | The theorem decides the fallback route; success on the single route holds by `write`'s definition; the public return value is not modelled. |
| temporal.write.collision#o01 | full → partial | b, f | Statement restored to the block's "changes nothing anywhere"; the newest-event index (tlast) is not modelled (native L7 observation only). |
| temporal.write.repeatable#o01 | full → partial | b | "Every store identical" is proved only for modelled stores; tin, min/max/sketch and tlast are missing. |
| temporal.write.retry#o02, #o03, #o04 | scope → narrowed | e | Proved on an empty store with a one-item batch. |
| temporal.stats#o01 | full → partial | e | Excludes update over an occupied coordinate, throwing writes and rollbacks, all of which "any serial history" includes. |
| after-purge#o02 | scope → narrowed | e | Raw-store equality is proved for a one-bucket range only. |
| after-purge#o03 | scope → narrowed | e | The cited purge covers the whole bucket; the cut-purge case is a documented composition. |
| after-purge#o04 | full → partial | a | The count for a k-bucket range holds by `purged_count`'s definition; only 0 and 1 are proved. |
| after-purge#o05, #o06 | scope → narrowed | e | One bucket that holds statistics; at least one surviving edge. |
| stats.window#o01 | full → partial | b | Windows spanning buckets are not proved. |
| stats.window#o03 | full → partial | a | The target window bounds hold by `is_target`'s definition; there is no hi vs hi+1 contrast. |
| stats.window#o04 | scope → narrowed | e | One-bucket windows only. |
| velocity#o05 | full → partial | b | The no-counter exclusion holds by definition only. |
| velocity#o06 | full → partial | a | Given vs default "now" holds by `now_of`'s definition only. |
| velocity#o07 | full → partial | b | The "unless the caller passes now" contrast is unproved for milliseconds. |
| velocity#o08 | full → partial | a | Definition only; no proof fn. |
| distinct#o01 | full → partial | a | The merge holds by `distinct`'s definition; the cited theorem is register idempotence. |
| distinct#o05 | full → partial | b | One event, one-bucket window; no untouched-bucket contrast. |
| distinct#o06 | full → partial | c | The point check stops at the estimator of an empty sketch; an empty window inside a non-empty bucket gives at least 11. |
| temporal.delete#o01 | full → partial | b | The inbound entry (^KG tin) named in the statement is not in the model. |
| optout.effect#o01 | full → partial | b | Only the ObjectScript writer is modelled; the Python mirror and engine-flag paths write rows (bug-tmp-006); tagged owner-contradicted. |
| optout.toggle#o04 | full → partial | a, b | The mark and the nodes hold by `backfill`'s definition only; the no-timestamp contrast is unproved. |
| optout.drop#o01 | full → partial | a, b | Unmarked rows kept is proved; removing all marked rows and the other-graph frame hold by definition only. |
| temporal.window#o04 | full → partial | c, d | Server pages are a scripted input, so covering the whole window is not modelled. |
| window.sources#o02 | scope → narrowed | e | Point check only. |
| window.sources#o03 | full → partial | b | The "only" half (case `['a']`, prefix) holds by `server_admits`' definition. |
| paging.release#o01 | full → partial | b | The with-block and garbage-collection ending paths are binding-only. |
| paging.release#o04 | scope → narrowed | e | Close mid-read is proved only right after the opening page. |
| paging.release#o09 | scope → narrowed | e | Requires page size ≥ 1 and size limit ≥ 1, which the product does not establish. |
| labelset#o01 | full → partial | c | The returned hash is not modelled (P-SHA1 premise); scalar sets only. |
| labelset#o03 | full → partial | a | Key sorting holds by `canon_v`'s definition; the theorem varies object references, not key order. |
| temporal.purge#o01 | full → partial | b | Survival outside the range and in other graphs holds by definition only. |
| ledger.atomic#o02 | scope → narrowed | g | Three point witnesses; the refutation itself stands. |
| edge.graph-scope#o02 | absent → partial | — | `temporal_clock::theorem_final_window_excludes_wrong_graph_and_time` covers the write case; the other steps hold by definition. |
| write.repeatable#o03 | absent → full (proved, narrowed) | — | `temporal_marker.rs::theorem_first_temporal_weight_wins` + `theorem_marker_decodes`, receipt `temporal_marker/20261116T163749Z-prove`. Filed under the marker block, which is why the search missed it. |
| temporal.delete#o02 | absent → partial | — | `temporal.rs::delete_temporal` returns false/true, but by definition only. |
| optout.effect#o04 | absent → partial | — | `temporal.rs::witness_optin_gap_closed_by_backfill` shows a temporal-only write still stores tout; no reader is composed with the registry. |
| temporal.ledger#o02 | absent → partial | — | `temporal.rs::LOp` takes the mode as an input (README rule 2). |

**3. Owner contradictions, duplicates and housekeeping**
- optout.effect#o01: the block's own metadata says the Python mirror and engine-flag paths write rows without reading the registry (F9 / bug-tmp-006).
- purge#o05: tagged owner-contradicted. `PurgeBefore` (`TemporalIndex.cls` 816–860) removes statistics only inside its raw-timestamp loop (§6.1 #25).
- collision#o01: the start statement had dropped the newest-event index from "nothing anywhere".
- No duplicates found.
- Housekeeping, report only: `temporal_stats` NOTES "Not represented" is consistent with the census. The `design-verified` tag on `temporal.labelset` and `temporal.stats.window` overstates coverage. `temporal.window.sources` is tagged design-verified, but its server half is inspection-only.

**4. Rows where I was unsure**
- temporal.stats#o01: a parent row; possibly harsh in counting update and rollback as in scope while update is still an open question.
- temporal.write.collision#o01 and repeatable#o01: downgraded only because tlast and tin are not modelled.
- delete#o01: downgraded because tin is not modelled.
- write#o07, collision#o02, toggle#o02: kept full and narrowed on point witnesses.
- repeatable#o03: an absent → full upgrade. The observation is the marker's weight qualifier, not a weight column.
- velocity#o06 and window.sources#o03: downgraded for definition-only halves.
- retry#o05: held full even though the reader-level proof covers only two-item pairs.
- latest.exact#o05: kept absent. `proofs-stmt` `eg_ti` kills the tlast cell, but the theorem's conclusion does not cover it and the crate has development runs only.
