# Procedure result independent review

Product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`; foundation `709a497f`. This is source-only review plus isolated Verus/Python replay. No native connection, container operation, product edit, shared model edit, or owner policy decision was made by this reviewer. Parent-owned native receipts are inspected evidence only.

## Frozen expectations and review boundary

Read `procedure-predictions.md` before the candidate model. P1 expected aliased WHERE plus explicit RETURN to keep the wanted persisted label and result name; P2 expected passing WITH to filter and MATCH to refuse. P3 retained the earlier source-first miss that a bare alias keeps physical column `label`, so bare ORDER BY l refuses. P4 left empty-producer expression validation unanswered rather than assuming eager refusal. Existing label scoping finding F-0816 remains inherited.

The candidate follows persisted labels -> actual `_proc_db_labels` DISTINCT/ORDER SQL -> `_try_system_procedure` -> actual parser source/alias pair -> `handler_tail` -> `where_rows` -> optional `_project_onto_names` -> `_apply_handler_tail` -> public `execute_cypher`. The SQLite binding calls real create_node and bulk_create_nodes setup writers; their transaction correctness is not thereby proved. Other committed label writers are admitted through arbitrary finite record state. SQL provider relation, grammar, multi-column providers, general/composite expressions, Unicode/collation and concurrent isolation remain outside the theorem boundary.

## Independently discovered missed neighbor

The initial 18-unit/9-control transcription missed `_project_onto_names`'s first `if names == columns: return result`. On nonempty A, actual pinned public calls gave:

| Query | Actual result |
|---|---|
| `CALL db.labels() YIELD absent AS label RETURN label` | column label, row A |
| `CALL db.labels() YIELD absent AS l RETURN l` | refused: answers label, not absent |
| `CALL db.labels() YIELD absent AS label WHERE label = null RETURN label` | refused before projection |
| `CALL db.labels() YIELD absent AS label RETURN label ORDER BY label` | column label, row A |

The old `consume` refused the first and fourth cases, and old `theorem_wrong_source_empty_vs_nonempty` quantified every alias, including physical label. The binding's wrong-source panel used only alias l, so its 6540 comparisons missed this branch. This is an as-built model correspondence failure discovered by review, not a new product defect or evidence of an intended wrong-source policy. Parent accepted the miss and is extending the raw-name domain and dedicated control; no alias==physical input exclusion is appropriate.

## Original isolated replay retained

Scratch: `/Users/ziniuw/.cache/g5-verification/ivg-procedure-review-yt69jg7q`. Copied only runner, procedure model, inherited bulk adapter and binding_common; RUN_DIR is scratch/run, exported pin is `/Users/ziniuw/runs/ivg-consolidated-20261114/pin`, Git object lookup is the real repository read-only. At most four Verus threads. Original model SHA-256 `54a75b7b3bf74c2efce04b82f6d2bbdca3d07e59f900e4b8ff5d3ed2ce6b90a9`; manifest `48eea63daaba0e7ff6a93e3eafb2131e2d7c3b37c71b69bb4f5bc9a0e88ee84d`; binding `9c0281d0b867473c6f92273a719a74b6c6a799276ad0f863f9d0641d9d631988`.

Original replay: 18 verified, zero errors (0.738 s); all nine controls EXPECTED_FAIL in their named theorem (10.899 s). Binding: AGREES, 6540 comparisons, zero mismatches, three comparison controls detected, zero socket connect attempts (3.469 s subprocess; receipt 2.923 s). Logs `original-prove.log`, `original-controls.log`, `original-binding.log` and receipts are retained in scratch. These successful formal/finite baseline results do not cancel the concrete missed neighbor above.

## Policy and claims review

The alias-column and empty-WHERE differences should remain open questions q-iter-004 and q-iter-005. Existing broad refusal wording and ordinary alias conventions motivate the questions, but the reviewed evidence establishes as-built behavior rather than a metadata-specific intended policy. Neither supplies owner approval for a repair or a new bug count. The canonical result child clearly states bare physical columns, alias-aware filtering/RETURN, true-only filtering, cutting after filtering, and expression versus structural refusal. Its linked Formal/NOTES scope excludes grammar/general expression/multi-column/collation claims. F-0816 stays inherited, not new.

Formal controls alter deciding effects rather than adding arbitrary impossible premises: filtering, projection naming, physical retention, empty validation, tail refusal, result-column ordering, filter/cut order, provider graph scope and DISTINCT. The predicate-soundness theorem itself concerns filtered membership, while separate composition theorems and the actual public reader binding cover the provider/consumer chain. Do not describe these as whole-member body proofs. The initial capability assignment and AST module identity split failures are harness failures retained in NOTES/results, not product bugs.

## Final rereview

The frozen extension is accepted within the declared boundary. The model first preserves expression/source validation when conditions exist; projection then takes its actual physical-name shortcut. The old wrong-source theorem now keeps all aliases and derives successful rows exactly for alias==physical; other aliases refuse on nonempty data. New `theorem_physical_return_bypasses_source_check` proves this behavior, and new control `physical-return-validates-source` fails that named theorem when the shortcut is removed. No input narrowing or owner intent change was used.

Final scratch snapshot: `/Users/ziniuw/.cache/g5-verification/ivg-procedure-review-yt69jg7q/final`. Model SHA-256 `c1b5fd65835381087753328369b55ce89b2c7b04f9191a97736a5a98bef1b875`; manifest `6a39b16f5e69698e0a2c602aa11ebf654da8e13c82c1a0bcc9f9609fd70f03b8`; binding `d9d8c54ec729c4b6a29315cc7f19d19209566694a6c1268606132e87b400dde8`. The full final snapshot equals current builder source at review.

Final independent replay: 19 verified, zero errors (0.850 s); all ten controls EXPECTED_FAIL in their named theorem (12.216 s); binding AGREES on 6580 comparisons, zero mismatches, all three actual comparison controls detected, zero socket connect attempts (3.584 s subprocess). The 19 units include two helper lemmas and 17 behavioral proof declarations. Logs are final/prove.log, final/controls.log, final/binding.log, with all raw Verus output and receipts beside the copied model. Original prepatch snapshots/results remain untouched.

At 18:23 UTC inspected parent-owned `procedure-native.json`: AGREES, 24 comparisons, no mismatches, every recorded helper/binding/script hash current. Its new empty/nonempty wrong-source cases cover physical label and alias l. This corroborates concrete default single/named bulk writers, SQL and public result flow on the parent-owned IRIS; it is not an independent native rerun or a generic SQL/collation/writer-transition proof.

NOTES accurately records the first false correspondence and source retention under procedure-attempts; canonical result/alias/empty-validation child statements and linked open questions remain qualified. Crosswalk writer entries explicitly say observes, committed-state premise, no newly modeled writer transaction. Parser entry states parser/name relation observed and grammar excluded. At review, the generated crosswalk descriptions still carried old SQLite6540/IRIS20 counts; parent was notified to regenerate them, along with adding the tenth shortcut effect to the formal-control prose. No material model/contract gap remains in the reviewed single-label scoped fragment.

Replay (replace the scratch path only if moving its preserved snapshot):

```sh
RUN_DIR=/Users/ziniuw/.cache/g5-verification/ivg-procedure-review-yt69jg7q/final/run VERUS_RUN_THREADS=4 VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus python3 /Users/ziniuw/.cache/g5-verification/ivg-procedure-review-yt69jg7q/final/.g5/Verus_verification/run_verus.py prove /Users/ziniuw/.cache/g5-verification/ivg-procedure-review-yt69jg7q/final/.g5/Verus_verification/models/procedure_results
RUN_DIR=/Users/ziniuw/.cache/g5-verification/ivg-procedure-review-yt69jg7q/final/run VERUS_RUN_THREADS=4 VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus python3 /Users/ziniuw/.cache/g5-verification/ivg-procedure-review-yt69jg7q/final/.g5/Verus_verification/run_verus.py controls /Users/ziniuw/.cache/g5-verification/ivg-procedure-review-yt69jg7q/final/.g5/Verus_verification/models/procedure_results
RUN_DIR=/Users/ziniuw/.cache/g5-verification/ivg-procedure-review-yt69jg7q/final/run IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin GIT_DIR=/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph/.git /Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python /Users/ziniuw/.cache/g5-verification/ivg-procedure-review-yt69jg7q/final/.g5/Verus_verification/models/procedure_results/binding.py
```


Cost: review ran approximately 18:17–18:24 UTC on 2026-11-15; proof/binding timings above are measured, total wall includes reading/coordination. No token/cache/currency or solver-only CPU estimate is available.
