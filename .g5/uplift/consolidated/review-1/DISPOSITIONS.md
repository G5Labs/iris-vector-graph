# Review-1 — master dispositions (review round 1 of this run)

Reviewer session 7e528c62 (fresh, read-only; $23.59) on bc85521e. Report: [REVIEW.md](REVIEW.md); evidence copied from
the reviewer's scratch into [scratch-evidence/](scratch-evidence/). Sign-off: Q1 native conditional, Q2 erasure not clean,
Q3 census conditional. The master adjudicated each finding against the governing sources named in the report; the
repairs are assigned to iteration 66 and must be validated before the next review.

| id | severity | category | disposition | repair owner |
|---|---|---|---|---|
| R1-N1 | material | incorrect intent (owner restates FR-013 too loosely) + product defect (comparator accepts wrong top-k/order under partial ORDER BY) | ACCEPT. Governing: spec 253 FR-002/FR-013. Register a finding (as-built comparator blind spot, not an observed wrong answer); amend query.native.equal-answers to FR-013's rule (exact where the rows kept are totally ordered; order-key agreement for the ordered prefix); extend native_admission with the complete-order direction and a control; regrade equal-answers rows. | it-66 |
| R1-N2 | material | missing intent | ACCEPT. Record in query.native.route (as built) that an identical query can return different answers on successive calls whenever the two paths differ (route trial alternation, recheck), linking bug-cyp-104/136; model the alternation consequence or keep it an open obligation with the live observation. | it-66 |
| R1-N3 | minor | model scope | ACCEPT. Narrow query.native.fallback#o01's premise to failures inside Exec.Run and record the uncaught planner/translation/decoding steps as an open obligation (no reachable trigger yet). | it-66 |
| R1-N4 | minor | owner not repaired | ACCEPT. Repair query.native.reads-only's MERGE example (as-built: declined); correct the `hidden_alias` premise for the WITH branch. | it-66 |
| R1-N5 | minor | conditional refutation | ACCEPT. Record the unconstructed RuntimeError branch as premise; keep shadow#o03's chained-loop limit explicit. | it-66 |
| R1-N6 | minor | scope | ACCEPT. deploy-discards#o01 check_scope → narrowed (DropAll failures swallowed). | it-66 |
| R1-N7 | minor | correspondence | ACCEPT. Model setup's conditional executor-version reset (objectscript_deployed); fix gates metadata. | it-66 |
| R1-N8 | minor | readability | ACCEPT. Attach or remove the stray working assumption in query.native.route. | it-66 |
| R1-ER-01 | material | product defect + correspondence error | ACCEPT. Register finding (delete_node of a reified edge's endpoint deletes the reifier node in every graph holding that id; reproduced live R1E); model `_delete_in_scope`'s reifier step for delete_node (and bulk_delete_nodes if the same path) instead of mapping delete_node straight to EraseNodeIds; replay live. | it-66 |
| R1-ER-02 | material | model error + grade error | ACCEPT. Theorems true by definition do not carry full: either model the failing step (fault before/after a store write, rollback to the found level) so the theorem is non-trivial, or regrade erasure.atomic#o02/#o03 partial. Controls must mutate a product step. | it-66 |
| R1-ER-03 | minor | model restates | ACCEPT. Derive the method→entry-point map from the real dispatch or regrade erasure.entry-points#o01 partial. | it-66 |
| R1-ER-04 | minor | model over-claims | ACCEPT. Distinguish live/closed statements per Eraser.cls:672-677 or narrow the claim. | it-66 |
| R1-ER-05 | material | missing intent / unresolved decision | ACCEPT. Relationship-list erase leaves temporal events (ADR-0009 says events are content). Add an owner statement or an open question beside q-tmp-006, a model claim that pins the as-built behaviour (M1 must fail), and a live observation if cheap. | it-66 |
| R1-ER-06 | minor | uncarried obligation | ACCEPT. Add the reifier-node residue (F-1502) as an obligation where its owner states it, or record why it is outside every statement. | it-66 |
| R1-ER-07 | minor | binding scope | ACCEPT. Observe ledger_revisions/record content in the binding (history survives), or narrow the history claim's correspondence. | it-66 |
| R1-ER-08 | minor | unresolved decision | ACCEPT as question: non-route registry rows kept by a graph erase — open question with the EraseAll comment as evidence. | it-66 |
| R1-ER-09 | minor | incorrect claim | ACCEPT. Correct "the store list is derived from GraphStores" in NOTES/BINDINGS. | it-66 |
| R1-CR-01 | minor | premise gap | ACCEPT. Record the bucket-counter $Increment surviving rollback as a premise/open obligation on erasure.atomic#o01/#o02 (reachability unestablished); fix #o01's witness citation (witness_list_erase_commits_earlier_chunk). | it-66 |
| R1-CB-07 | minor | correspondence | ACCEPT. Use GraphKey's character set (0-31, 127, 128-159) for the Eraser's name check; add the version bump to the graph-erase theorem or narrow it. | it-66 |
| R1-CB-04, R1-CB-01, R1-CR-02, R1-CR-03, R1-CR-04, R1-CB-02, R1-CB-03, R1-CB-06, R1-CB-08, R1-CR-07 | material/minor | census grade errors | ACCEPT. Regrade as listed; for R1-CR-02 decide obligation vs undecided alternative from the block text. Extend the lint: a partial row must carry a model locator (R1-CB-03). | it-66 |
| R1-CB-05 | material | census splitting (merged outcomes) | ACCEPT. Write one splitting rule in census/README (split when one outcome can fail while another holds, incl. Python-refusal vs native outcome), re-split the named rows (ledger.observability#o03, algorithms.op.paths.weighted#o06/#o08, fusion, capabilities) and sweep for other merged rows mechanically (rows naming several outcomes/entry points); report the denominator change as a scope change separately from retained-obligation change. | it-66 |
| re-search | material | stale grades | ACCEPT. Re-search rows graded before iteration 65 against the iteration-62 and -65 models (native_admission, erasure_stores). | it-66 |
| R1-T1 | minor | tooling/doc | ACCEPT. census.py needs a git checkout: say so in census/README and the runbook (or make the playbook-tree check fall back gracefully). | it-66 |

Reviewer's estimate of the true full share after review: ~36% (34–37%) of 2100, with the denominator probably
understated 10–20% by merged rows. Q4 cross-area leads (engine caches that never revalidate: privileges, index
declaration, another engine's bulk load q-cyp-003) are queued for the product-wide inventory.
