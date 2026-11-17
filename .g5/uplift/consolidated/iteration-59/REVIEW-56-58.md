# Independent review round 4 (review 56-58), copied verbatim

Reviewer: fresh session `86e7606a`. Reviewed commit: `fdc19d527268fe8673a44e9c5556c2cfe8e8c367` (`fdc19d52`, consolidated_uplift), product pin `3eaa79cf`. Source: `$G5_RUN_STATE/reviews/review-56-58/REVIEW.md`; the reviewer's full answer is `ANSWER.md` beside it (summarised in [DISPOSITIONS.md](DISPOSITIONS.md)). The text below the rule is unchanged.

---

# Review 56-58 (independent review round 4)

Commit reviewed: fdc19d527268fe8673a44e9c5556c2cfe8e8c367 (consolidated_uplift), product pin 3eaa79cf.
Scratch: /tmp/review-56-58 (tree/ = git archive copy; run/proofs.log; probes/; reach/, reach-base/; new-bound.json; dl-added.tsv).

Verdict: conditional sign-off. Not blocking. One material item: G1, an HTTP tx/commit batch that keeps partial writes, which is unowned and unregistered. One counting item: B1, OtherEdgeKeys is counted as active. The full text is the reviewer's final answer; the main items are listed below.

Reproduced:
- Proofs (copy): bolt_tx 20, install_lifecycle 32, traversal_strategy 30, adjacency_maint 35, rebuild_reads 5, clause_combos 28, result_decoders 12. All PASS.
- Controls: begin-refused, row-read-materialized, length-in-reversed, fresh-ignores-stamp, rebuild-swaps, group-by-kind-column, with-coalesce-typed. All EXPECTED_FAIL.
- member_reach: HEAD 706 vs fb1f806b 640. 70 members newly bound; 4 lost (the F5 relabels).
- Fixture probes (prefixes rv58_*):
  - bug-plt-127: driver rollback leaves count 1; commit gives 1.
  - bug-str-115: 467 of 6,413 reads during sync() departed, including the native Cypher var-length count (0); 40 writes made during sync() were all kept.
  - bug-srch-116: "Cursor closed", and the row is kept.
  - bug-cyp-155: WITH coalesce gives '3', RETURN coalesce gives 3.
  - bug-cyp-156: CASE boolean gives 'true'.
  - bug-cyp-146: fixed-length path length is 1 while `p IS NULL` is true.
- New observations:
  - HTTP tx/commit batch: statements 1 and 3 persist around a failing statement 2.
  - CALL {} that imports an UNWIND variable fails.
  - ORDER BY over a query-held list puts booleans among the numbers.
  - A UNION of literal lists answers JSON text.
  - A whole float (2.0) round-trips as a float, so that challenge is refuted.
