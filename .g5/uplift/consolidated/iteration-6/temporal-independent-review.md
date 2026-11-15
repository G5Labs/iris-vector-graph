# Independent temporal-restore review — iteration 6

Product pin `3eaa79cf77d3e0a879b2cced634cf2729d81499e`; foundation before `47236c829a48215db58c1677637b3fc41cc85310`. I read source-frozen `PAIRS.md` before the new candidate, then inspected the actual writer/export/import/readers and published builder receipts. No private evaluator evidence was used. I did not execute the native binding, connect to a target or change any runtime/container, product, model, shared tool, canonical owner or Git state. This report is the only repository file I write for this review; proof/control copies are isolated scratch files.

## Result and source correspondence

The new model distinguishes a real boundary missing from the earlier temporal reader alone: successfully written temporal coordinates -> scalar archive lines -> NativeAPI import -> graph/direction/window and attribute observations. The as-built scalar type loss and the intended requirement remain distinct. The latest inspected native receipt before review, `results/temporal_restore/20261115T171322Z-binding/receipt.json`, reports AGREES with the **as-built** oracle, while retaining `intended_scalar_types.preserved=false` and the original `20261115T170720Z-binding` DISAGREES receipt. This is not a repair or a newly counted bug: it strengthens inherited F-1804. The quiet native-invalid line strengthens inherited F-C1802; valid neighbors remain observable.

The actual deciding chain supports the represented projection:

1. Python `create_edge_temporal` passes the actual graph/timestamp/weight/attribute inputs to `TemporalIndex.InsertEdge` and `WriteStores`. A successful first write places a canonical numeric weight in graph-scoped `tout`, conditionally `tin`, and the parsed attribute values in `edgeprop`. The model's `insert`, raw reverse-index flag and attribute map supply those effects; collision stutters correspond to the default insert mode, not the update mode.
2. `snapshot_globals` and `kg_export_subscripts` derive temporal prefixes from STORE_PLAN. `_export_global_to_ndjson` recursively walks the real native subscripts from `START=""`; ordinary KG scalar values are written as **`str(val)`**. `encode_scalar(Number(n))=NumericText(n)` therefore records actual producer behavior rather than assuming a preserved type. The old zero-start exporter is an actual method-copy control, not an arbitrary result fixture.
3. `_import_global_from_ndjson` decodes each JSON line and calls NativeAPI `set(entry['v'],...)`; per-line exceptions are caught, counted as zero applied, and not propagated. `restore_snapshot` can still list KG among restored globals when other lines applied, with empty failed_rows. The model's rejected-key/Line::Malformed paths preserve this partial as-built result. The native receipt contains the actual `<SUBSCRIPT>` refusal for the edited empty-subscript line and surviving valid neighbors.
4. `TemporalIndex.QueryWindow/QueryWindowInbound` use graph-specific tout/tin and inclusive bounds. Their `jsonNum` weight output remains numeric after textual scalar restore. The paged `TemporalWindow.Row` tests storage type before emitting attribute JSON; restored numeric-looking text is quoted, so `temporal_window.event` returns string attribute n. The model's separate `weight_value` and `attrs` capture this meaningful difference. The binding's original native observation has n=1 before and n="1" after while w remains numeric.
5. Paged Open/Page/Next and the Python cursor were actually traversed in the builder fixture at page size1, including the final done-page round trips. Suppressed reverse-index input is absent from the inbound result while outgoing events survive. Omitted sources and explicit empty sources remain distinct. Layout mismatch is observed before erase using both preserved temporal observations and a SQL sentinel.

The normal/layout/bad-line worlds use the actual identity-checked disposable instance according to the builder receipt; this reviewer audited those receipts and source but did **not** independently replay native behavior. The receipt's seven comparisons are labeled scenario comparisons, not seven independent samples or a prevalence denominator.

## Exact scope and remaining formal boundaries

- The target reports **29 verification units**, including **16 rechecked inherited units** from the byte-identical `temporal_window_reader.rs` import. The new file has **11 named proof functions plus two recursive specification termination units**, or 13 new units. Calling all29 new theorems would overstate the gain. Imported SHA-256 `4f14236f57a45c64e889f794b6d55f3fc823dccaba4a2759ed7cedc97fd3bd9d` equals the iteration-5 file.
- The per-key export/import/window theorem requires that the enumerated key sequence contains the needed key and that the store set includes its subtree. It does **not** prove native `nextSubscript` enumeration exhaustiveness from STORE_PLAN or build the whole key census. That producer relation is inspected and sampled natively, including zero graph/epoch and a decisive failing control.
- The new `weight` definition reuses imported `window_spec/server_admits`. It does not feed a restored row sequence into `paging::drain` or prove a new restore-to-page-concatenation theorem. The old cursor lifecycle proof remains inherited; restored paged content is newly **observed** within the native fixture. A full paged composition claim remains conditional.
- Scalar numbers are abstract integer payloads; the native fixture uses integer weights and integer/text attributes. No arbitrary float/Decimal/JSON object or nested-attribute codec theorem follows. Numeric-looking text and nonnumeric text need the stated abstraction relation; legal native global addresses and a completed admitted writer remain provider premises. This slice covers successful default-mode first writes/collisions, not every temporal update, structural-callback failure, partial write or competing writer.
- Layout `None` being admitted is as built; it proves no compatibility for malformed old globals. The restore model projects one admitted temporal KG scope, not every SQL table/global/cache or rollback of a replacing restore. Source inspection and the whole-product confinement gate conservatively protect product correspondence; the binding receipt itself stamps the model/helper/import plus selected pin checks rather than every temporal deciding source separately.
- No assume, admit or external_body occurs in the new file or imported reader. Native APIs, JSON/global scalar correspondence, provider behavior and the inspected transcription remain outside executable-body proof.

## Findings, failed proposal and review corrections

The initial numeric-attribute observation is a real intended mismatch, not an oracle error to erase. The candidate now models it and keeps the intended preservation requirement/finding open. The raw-value-only candidate replacing `"v": str(val)` with `"v": val` was tested on an actual method copy and failed while exporting another KG scalar: native Decimal was not JSON serializable. The raw failure is retained in `scalar_preserving_variant.error` as SnapshotReadError. That proposal is insufficient and retired; it has no product implementation or successful proposed-design Verus comparison. It supplies no excuse to weaken the type requirement or announce a repair.

Two concrete review issues were sent to root and corrected before integration:

1. The first new runner placed imported control dependencies outside the run's timestamp directory: `.../<name>/<stamp>/../temporal_window_reader`. A later control could overwrite an old run's dependency. Root moved the actual working directory under `.../<stamp>/models/<model-name>` and confined copied dependencies to that unique control root. Mathematical proof results from the first layout remained valid, but preserved replay inputs were not self-contained across changed imports.
2. The first binding sensitivity check used `changed != final`, which only established that a JSON edit occurred. Root changed it to run the actual oracle: `agreement(final,restored=True) and not agreement(changed,restored=True)`. Root also made the quiet-line interpretation require `native_error is not None`, so an invisible-but-accepted empty key cannot masquerade as an actual native refusal. The older receipt already contained an actual refusal, so its historical witness remains valid.

Canonical/NOTES integration should retain all boundaries above, keep F-1804/F-C1802 identities, and avoid promoting the imported paging proof or a scenario receipt into general implementation verification. The normal and failing controls distinguish meaningful neighbors; no new product defect or owner approval is inferred by this review.

## Independently reproduced proof, controls and dependency freshness

Only copied model/import/manifest/runner inputs were executed under scratch RUN_DIR. No native binding was imported or run. Raw logs, receipts and all control source copies remain in the scratch directory.

```json
{
  "scratch": "/Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-independent-3647hlwj",
  "runs": [
    {
      "action": "prove",
      "exit": 0,
      "wall_s": 1.069,
      "log": "/Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-independent-3647hlwj/prove.log"
    },
    {
      "action": "controls",
      "exit": 0,
      "wall_s": 9.901,
      "log": "/Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-independent-3647hlwj/controls.log"
    }
  ],
  "hashes": {
    ".g5/Verus_verification/run_verus.py": "33229fcee5e07aaa3b9daab300b491c9e7ab053685669e944248a14c3d47edfa",
    ".g5/Verus_verification/models/temporal_restore/temporal_restore.rs": "630f1bc4fdfd6c729b45a2e1d4d66a5cde20916fd6fa8445b9fdce2fd8f4a3c6",
    ".g5/Verus_verification/models/temporal_restore/model.json": "d250b2a8d9cb27c8cfe0c8fd2c3657399d30042813f746bf52dc6f28c40052f8",
    ".g5/Verus_verification/models/temporal_window_reader/temporal_window_reader.rs": "4f14236f57a45c64e889f794b6d55f3fc823dccaba4a2759ed7cedc97fd3bd9d"
  }
}
```

The final-runner pass reproduces all seven controls at their named functions. A dependency-only comment change then makes the old proof receipt STALE (exit1), and running the zero-start control against that changed import preserves the earlier control's original imported file while creating a distinct new copy. This is a formal-input stamp/control-copy check, not a changed product theorem or native observation:

```json
{
  "runs": [
    {
      "phase": "controls-final-runner",
      "exit": 0,
      "wall_s": 9.804
    },
    {
      "phase": "control-import-changed",
      "exit": 0,
      "wall_s": 1.5
    }
  ],
  "runner_sha256": "33229fcee5e07aaa3b9daab300b491c9e7ab053685669e944248a14c3d47edfa",
  "old_control_copy": "/Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-independent-3647hlwj/runtime-final/verus/temporal_restore/controls/zero-start-export/20261115T171754Z/models/temporal_window_reader/temporal_window_reader.rs",
  "old_copy_preserved": true,
  "copy_count": 2,
  "copied_hashes": [
    "4f14236f57a45c64e889f794b6d55f3fc823dccaba4a2759ed7cedc97fd3bd9d",
    "685a83b7e7f286ca7c6e6a701dd024c0f2a68532a97dee6742c277fe88c1162f"
  ],
  "stale_exit": 1,
  "stale_output": "STALE: /Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-independent-3647hlwj/.g5/Verus_verification/results/temporal_restore/20261115T171654Z-prove/receipt.json no longer applies; changed inputs: .g5/Verus_verification/models/temporal_window_reader/temporal_window_reader.rs"
}
```

Current model SHA-256 is `630f1bc4fdfd6c729b45a2e1d4d66a5cde20916fd6fa8445b9fdce2fd8f4a3c6`. The reviewed runner after correction is SHA-256 `33229fcee5e07aaa3b9daab300b491c9e7ab053685669e944248a14c3d47edfa`. The model file and import contain no admissions/trusted external bodies; whole-product source confinement is a separate correspondence gate. Independent wall times: proof1.069s, initial full controls9.901s, final-runner full controls9.804s, changed-import representative control1.5s. Tokens/cache/currency and solver-only time are unavailable. Repeated controls are disclosed reruns, not additional coverage.

I also executed only the current pure `expected`/`agreement` definitions extracted by AST from binding.py against the retained native receipt: the as-built data is accepted, altered n=99 is rejected, intended numeric-type preservation is still rejected, and the actual native refusal is present. No import or native call was needed. The corrected binding source hash differs from the latest inspected native receipt, so root still needs a fresh final native harness receipt before sealing; this reviewer does not manufacture a new native observation.

**Review verdict:** PASS for the represented per-key as-built model, dependency staleness and seven decisive controls, with the explicit enumeration/paging/codec/provider qualifications above. Native conclusions are audited builder evidence; final harness freshness and canonical/NOTES qualification remain root integration work. The retained intended violations and failed simplification must stay visible.

## Final strengthening addendum — 31 units and fresh native receipt

This addendum supersedes the earlier 29-unit count, the missing desired-key derivation in the weight contract, and the pending final native-harness freshness note. The earlier review remains preserved as the reason for strengthening.

`export_temporal(src)` now enumerates `src.dom().to_seq()` and fixes the three critical temporal store identities. `theorem_complete_source_reaches_window` derives the desired key's membership from the finite source map rather than accepting it from the query caller, and `theorem_actual_writer_restore_window` composes the successful writer with that export, replace-restore and the final window weight. The native provider must still establish that its local recursive walk enumerates the corresponding finite leaves completely; that NativeAPI correspondence remains inspected/sampled, not an executable-body proof. Full restored sequence -> paged drain composition is still not newly proved. Attribute-specific per-key theorems and scalar/legality/provider limits remain as previously qualified.

The final count is **31 verified units = 15 new units (13 named proof functions plus two recursive spec termination units) + 16 rechecked inherited paging units**. Independent final scratch proof and all seven controls reproduce:

```json
{
  "scratch": "/Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-31-review-oyg2225y",
  "runs": [
    {
      "action": "prove",
      "exit_code": 0,
      "wall_s": 1.205,
      "log": "/Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-31-review-oyg2225y/prove.log"
    },
    {
      "action": "controls",
      "exit_code": 0,
      "wall_s": 9.907,
      "log": "/Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-31-review-oyg2225y/controls.log"
    }
  ],
  "hashes": {
    ".g5/Verus_verification/models/temporal_restore/temporal_restore.rs": "ba855930771f858e31c543ca268e465d80df35e21165c0baa2bf7b5b938c4141",
    ".g5/Verus_verification/models/temporal_restore/model.json": "6e7137843cae40f30a383cad43dee83f6733faac5bdff15cd9709921284cfb12",
    ".g5/Verus_verification/models/temporal_window_reader/temporal_window_reader.rs": "4f14236f57a45c64e889f794b6d55f3fc823dccaba4a2759ed7cedc97fd3bd9d",
    ".g5/Verus_verification/run_verus.py": "33229fcee5e07aaa3b9daab300b491c9e7ab053685669e944248a14c3d47edfa"
  },
  "native_executed": false
}
```

Audited fresh builder native receipt `.g5/Verus_verification/results/temporal_restore/20261115T172115Z-binding/receipt.json`: verdict AGREES, seven scenario comparisons, 0 mismatches against the as-built oracle; model and binding input hashes both equal the current source. Its actual oracle-based changed-attribute detection and exporter mutant detection are true. Intended scalar preservation remains false; native refusal evidence remains present; raw-value-only Decimal serialization failure remains the recorded retired proposal. This reviewer did not execute that native receipt. The earlier F-1804/F-C1802 disposition and original DISAGREES evidence are retained.

Related control correction audited without a native call: snapshot_routes receipt `.g5/Verus_verification/results/snapshot_routes/20261115T171758Z-binding/receipt.json` reports AGREES over 11 native scenario comparisons and matches the current binding hash. `changed_final_vector` now evaluates `complete_values(final) and not complete_values(changed)`. The old edit-only `changed != final` observation-control credit is **withdrawn** and replaced by this actual-oracle detection; no extra product fix, formal coverage or new issue follows from correcting the instrument. Historical observations remain intact.

**Final mathematical/native-evidence verdict:** PASS on this explicit as-built scope, with conditional NativeAPI enumeration/codec/provider correspondence and inherited paging lifecycle; no general restored-page sequence theorem or direct product-body verification is claimed. Canonical/NOTES text still needs to preserve these qualifications when root writes it.

## Final wording and raw-layout review before iteration-6 seal

Reviewed the now-written `models/temporal_restore/NOTES.md` and canonical `install.snapshot.temporal` body/metadata. They accurately retain the intended attribute-type and failure-report requirements alongside observed F-1804/F-C1802 violations, derived source-map keys under the explicit native enumeration contract, inherited paging-unit accounting, missing full page-sequence/global-loop composition and bounded scalar/provider scope. The three added store/reverse adapter roles were traced in actual source: explicit timestamp/weight/attrs/reverse flags reach `write_temporal_edge`/InsertEdge; `execute_temporal_window_query` selects QueryWindow versus QueryWindowInbound and maps actual JSON fields/error to the final consumer. These role claims remain limited to explicit integer timestamps and the observed projection, not clock resolution or general JSON behavior.

The final `restore` now consumes raw `Option<Seq<char>>` layout text and compares a present value with literal `graph-scoped`; it does not accept a pre-decided match boolean. Its generic refusal theorem takes an actual different declared string, and None remains admitted. This matches the deciding source branch. Independent scratch rerun:

```json
{
  "scratch": "/Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-layout-review-16fxmpjc",
  "runs": [
    {
      "action": "prove",
      "exit_code": 0,
      "wall_s": 0.936,
      "log": "/Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-layout-review-16fxmpjc/prove.log"
    },
    {
      "action": "controls",
      "exit_code": 0,
      "wall_s": 10.324,
      "log": "/Users/ziniuw/.cache/g5-verification/ivg-iter6-temporal-layout-review-16fxmpjc/controls.log"
    }
  ],
  "model_sha256": "0f72f0047d5a1faf6471e0cd7b2bc369fe2c4e334144bbc17b6264b961d584a6",
  "native_executed": false
}
```

Final native builder receipt audited: `.g5/Verus_verification/results/temporal_restore/20261115T175727Z-binding/receipt.json`, AGREES / seven scenario groups / 0 mismatches. Its binding/model input hashes equal current files; this reviewer executed no native operation. Mathematical and native evidence PASS on the declared domain. One minor NOTES locator paragraph was sent to root: the two `iris_sql_store.py` members live under `iris_vector_graph/stores`, while the engine modules live under `_engine`; crosswalk paths already resolve correctly. No remaining substantive wording objection or new issue count is introduced. All earlier review corrections and evidence remain historical, with this final raw-layout hash superseding the earlier model hashes.
