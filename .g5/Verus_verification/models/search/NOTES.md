# Model `search` — embeddings and search (worker B-search)

Product baseline `3eaa79cf` (worktree head `0e441f1c`; no product path differs). Root file `search.rs`,
controls in `model.json`. Stage-A leads: `.g5/uplift/ivg-verus-initial/intent/search.md` (O1–O6, F1–F13);
every premise below was re-read at its producer in the code. Nothing here verifies the ObjectScript or
Python bodies: the L2 functions are transcriptions bound line by line to the product (L3 column).

Run: `VERUS_RUN_THREADS=4 python3 .g5/Verus_verification/run_verus.py prove|controls .g5/Verus_verification/models/search`.
Result (review round 2): `prove` PASS, 56 verified, 0 errors (`results/search/20261114T035601Z-prove/receipt.json`);
27 controls, see "Controls". Superseded: round 0 (49 verified, 22 controls, `receipts/search/`) and round 1
(50 verified, 25 controls, `results/search/20261114T00*`).
Toolchain: Verus 0.2026.10.04.426d8b0, bundled vstd only (see `SOURCE.json`).

## O1 — BM25 counters under Insert / Delete / Build / Drop

**Governing sources.** spec 044 FR-015..FR-022 (accepted decisions, Clarifications 2026-10-08; the
opsreview request behind them is external, human requirement only secondhand); ADR-0007 (accepted:
"does every write under an index-level lock in a transaction with plain Set"); CONTEXT.md "Document
Frequency" (glossary, agent-written).

**L1** (`cons`, `cons_present`): at a committed point an index is absent (no N, nothing stored) or
df(t) = |{d : tf(t,d)}| and absent at zero; the token record of d is exactly the terms with a tf(t,d);
every posting's document has a record; N = |len|; totalLen = sum len; vocab_size = |df|;
len(d) = sum_t tf(t,d) > 0.

**L2 → L3 bindings** (`iris_src/src/Graph/KG/BM25Index.cls` at the pin):

| Model | Product |
|---|---|
| `Ix` fields | `^BM25Idx(x,"tf"/"df"/"doc"/"len"/"cfg")`, header l.6-18 |
| `tok_ok(bag, dlen)` (premise P_tok) | `Tokenize` l.56-87 drops empty tokens (l.80-85), so `$LISTLENGTH` = sum of tfMap (Insert l.447-454, IndexDoc l.180-188) |
| `writable` | `RequireWritable` l.385-394 (checked before the lock l.444 and under it l.459) |
| `remove_postings`, `remove_tail`, `remove_doc` | `RemoveDoc` l.416-437 (oldLen read l.419 before the loop; `+$Get` on N/totalLen l.434-435) |
| `add_postings`, `add_body`, `add_counters`, `add_doc` | Insert l.471-479 (add loop), l.480-481 (record, len), l.482-483 (N and totalLen read without `$Get`) |
| `init_ix`, `insert_body` | Insert l.460-485 (new-index cfg l.461-466) inside `LockWrite` l.456 / `Lock -` l.491 |
| `WAct::InsBegin` / `DelBegin` (`begin_run`) | Insert l.444-467 / Delete l.496-505: checks, lock, TStart, init, RemoveDoc's presence test, oldLen, record and loop (l.418-431). Delete returns 0 without locking when no N (l.498) |
| `WAct::WTail`, `WAdd`, `WCommit` | RemoveDoc l.432-435; Insert l.468-481; Insert l.482-485 / Delete l.506 and the unlock. One writer transaction in flight at a time (`WSys.run`: the lock) |
| `WAct::BuildKill/BuildDoc/BuildFinish`, `index_doc`, `publish` | `Build` l.97-175: `Kill` l.99, scan l.123-157, `IndexDoc` l.178-204 (locals N, totalLen, vocabSize), cfg writes l.160-170, schema last l.170. No lock, no TStart |
| `WAct::Drop`, `absent_ix` | `Drop` l.587-591, no lock |
| `undo` (premise P_undo) | Insert/Delete Catch `If $TLevel > 0 TRollback` l.486-490 / l.507-511 |

**Step relation (review R1-8).** Insert and Delete are split at their real interleaving points for an
unlocked writer: RemoveDoc's loop (inside TStart), RemoveDoc's tail, the add loop, and N/totalLen + TCommit.
Build (Kill, one IndexDoc per scanned document, publication) and Drop (Kill) are steps that take no lock, so
they can land between any two writer steps. A failure inside an in-flight transaction and its rollback are
not in the step relation (a split run always reaches TCommit; `WCommit` is not enabled when N is
undefined, which is where the product raises `<UNDEFINED>` and rolls back).

**Theorems.** `theorem_insert_preserves_counters` (replace, replace with empty text — which is also what a
Delete of a present document does — and the first insert into an absent index),
`theorem_delete_preserves_counters`, building on `lemma_remove_doc_preserves` and
`lemma_add_doc_preserves`; `theorem_locked_build_preserves` + `lemma_init_winv` (invariant `winv`: nothing
in flight → consistent; a Build in flight → what it will publish is consistent; a writer transaction in
flight → the global is exactly that transaction's partial state `stage(r)` from its TStart state): with the
proposed repair, in which Build and Drop take the index write lock (and so wait for an in-flight writer
transaction, and writers wait for them), every state with nothing in flight is consistent. This covers
Build and Drop inside an Insert or Delete **for counter consistency only**: it says nothing about whether
a returned Delete takes effect (review R2-1, below).

**A returned Delete takes effect (review R2-1).** L1 `gone_ok` (ghost `WSys.gone`: documents whose Delete
or empty-text replace has returned and that no later write put back — an Insert of the document, or a
Build that scans it after the delete): no such document is in the index, except during an Insert of it
between its add loop and TCommit. Sources: FR-019/FR-021 (Delete atomic and exclusive like Insert; accepted)
and `bm25_delete`'s contract ("False if it was not or the index does not exist", `_engine/vector.py:1849-1855`).
Verified against the code: `Delete` returns 0 before `LockWrite` when cfg N is absent (l.498-500), and
`Build` sets N only after its scan (l.160). `theorem_repair_delete_takes_effect` (+ `lemma_init_gone_ok`)
proves `gone_ok` is kept under the full repair `locked_build()`: Build and Drop take the lock **and** Delete
takes the lock before it tests N (`delete_under_lock`), so a Delete waits for a running Build.

**Witnesses (as-built; W-O1a/b/c are traces of `wstep` under `as_built_writers()`).**
- `witness_build_insert_breaks_n` (W-O1a): Build's Kill → an Insert of a document Build will not scan →
  Build indexes its document and publishes its local counts → committed index, no Build in flight, has
  N = 1 and two documents (also totalLen and vocab_size wrong).
- `witness_build_insert_double_df` (W-O1b): an Insert of the same document between Kill and IndexDoc →
  df(7) = 2 with one posting; a later (admitted, locked) Delete leaves df(7) = 1 with no posting.
- `witness_drop_inside_insert` (W-O1c): two Inserts build {1: 7, 2: 8}; an Insert replacing document 1
  runs `InsBegin` (RemoveDoc's loop); `Drop` lands; `WTail`, `WAdd`, `WCommit` all succeed (RemoveDoc uses
  `+$Get`, so N = -1 exists again for l.482) and the Insert commits: the dropped index exists again with
  N = 0, one document and no schema (writers then refused as "schema 1"). Needs no rollback premise.
  Round 0 composed this from the model's functions by hand and it still verified with Drop disabled
  (review Adv-3a); it is now a trace, and control `as-built-no-drop` (Drop disabled) makes it fail.
  Not probed natively (microsecond window).
- `witness_delete_during_build_lost` (W-O1e, R2-1): an index holds document 1; a Build's Kill; the Build's
  scan flushes document 1; a Delete of document 1 finds no N and returns 0 without the lock; BuildFinish
  publishes document 1. With nothing in flight the deleted document is in the index.
  `witness_round1_repair_loses_delete`: the same history under the round-1 repair alone (`round1_repair()`:
  Build and Drop locked, Delete still tests N first) still loses the delete, while `winv` holds at every
  step and the published index is consistent (proved by chaining `theorem_locked_build_preserves`).
  `witness_repair_delete_after_build` (valid outcome): under the full repair the Delete is not enabled
  while the Build runs, then removes the published document. W-O1e is not probed natively (source
  reading + model only); the review's scratch witness is `agents/R2-domains/adv/` (S-a).
- `witness_caller_txn_rollback` (W-O1d): **not a trace** — the step relation has no caller
  transactions. The model's functions composed as: Insert inside a caller's transaction, the inner
  `Lock -` releasing the lock (premise **P_unlock_in_txn**), a second writer committing on top, the
  caller's rollback (P_undo) → a posting for term 7 with no df(7). **P_unlock_in_txn is false on IRIS:**
  probe `search_bm25_caller_txn_lock` observed the second writer wait 3.0 s until the caller's rollback
  (IRIS keeps the lock to the end of the transaction), and the counters were consistent. This branch is
  not reachable; it is kept only as the record of the refuted premise.

**Premises and who establishes them.** P_tok (Tokenize, shown above). P_distinct: a token record lists
each term once (Insert builds it from `$Order(tfMap)`, IndexDoc likewise, Upgrade appends once per term),
so the per-term set-level effect equals the loop's. P_lock: one writer transaction at a time
(`WSys.run`), because Insert and Delete both hold `^BM25Idx(x,"lock")` (product, l.403-410); the lock binds
only the writers that take it, so Build and Drop interleave with the split writer steps. In the O2
subsystem (no Build or Drop) Insert and Delete stay one atomic step each. P_undo: IRIS TROLLBACK restores
each node the transaction wrote to its before-image (IRIS journal semantics; external). One Build of a
name at a time (modelling bound; two concurrent Builds race the same way, not modelled). Build's scan
flushes each node once (`ORDER BY node_id`, node ids unique per graph).

**Not represented.** Search reading mid-transaction state (Search takes no lock, FR-019; open question
Q4); a failure inside an in-flight writer transaction and its rollback (split runs always reach TCommit;
`WriteFails` covers refusals before TStart); `<UNDEFINED>` on l.482 when N is killed between RemoveDoc's
tail and l.482 (`WCommit` is then not enabled; W-O1c takes the interleaving that commits); Search during Build answers `[]` (no N) — an empty answer indistinguishable from
"no match"; Build's Kill also clears an Upgrade's `upgrading` flag (Build during Upgrade).

### O1 — common-term cutoff (pure function)

**Source.** spec 044 FR-044-C1..C5 (accepted, Clarification 2026-10-09); CONTEXT.md "Common-term cutoff".
**L1** (`theorem_cutoff_contract`): off (fraction ≤ 0 or schema 1) → nothing skipped, no fallback;
otherwise exactly the known terms (df > 0) with df/N > fraction are skipped, except that when every known
term is over the bound the rarest (first in query order on a tie, `rarest_upto`) is kept and `fallback`
is set; a df = 0 term is never skipped; a query with a known term always scores one.
**L2 → L3.** `cut_scan` = SearchCore l.268-276; `cutoff` = l.265-293 (`tAllSkipped` l.277-282, fallback
l.283-286, report l.287-292, schema/fraction gate l.266). **Premises.** N > 0 (l.241 returns earlier);
fraction den > 0; df(t) ≥ 0 (stored counts; the code tests `tD = 0`, the rule says df > 0 — they agree
only for non-negative df, which RemoveDoc's kill-at-≤0 keeps). **Not represented.** ObjectScript
collation order of `skipped` (Q6); df re-read for scoring at l.300 (a separate read, no isolation).

## O2 — schema-1 → schema-2 Upgrade

**Source.** spec 044 FR-022, FR-023, SC-012 (accepted); CONTEXT.md "Index Schema".
**L1.** Search reading schema 2 reads a consistent index (`schema_of ≥ 2 ⇒ cons`); writers are refused from
flag-set to flag-clear; one pass converts from tf/len; re-running after an interruption converges.
**L2 → L3** (`UAct`, `ustep`): `Start` = Upgrade l.528-533 (missing / already checked **only before the
lock** / flag set before the lock); `LockKill` = l.534-542; `Timeout` = l.536-538; `Rebuild` (`rebuilt`) =
l.543-558; `Count` (`counted`) = l.559-568; `Flip` = l.570; `Clean` = l.571-572; `Done` = l.578-579;
`Fail` = Catch l.573-576; `Crash` = process death (IRIS frees the lock, no Catch, flag stays). No TStart
anywhere in Upgrade. Writers: `Insert`/`Delete` as in O1 (atomic, lock-free required).
**Theorems.** `theorem_upgrade_step_preserves` (as-built, invariant `uinv`), `theorem_writers_refused_while_upgrading`,
`theorem_upgrade_completes` (one uninterrupted call leaves `canonical(ix)`, a function of tf and len only,
`lemma_canonical_depends_on_tf_len`), `lemma_upgrade_steps_keep_tf_len`, `theorem_rerun_converges`,
`lemma_schema1_init`. Premises of the as-built proof (variant `upgrade_as_built`): **serial** — an Upgrade
starts only when no other Upgrade of the index is in flight (the product does not establish this; the
pre-lock `already` test does not); **no death between the flip and the flag's clear** (l.570-578, which
includes `Kill ^BM25Idx(x,"idf")`, a walk of the whole schema-1 idf subtree); P_s1 (`s1ok`: tf and len
agree — what 3.x Build/Insert left; established by the old writers, checked by SC-012 tests).
**Repair.** `theorem_repaired_upgrade_preserves` (variant `upgrade_repaired`: re-read `schema` under the
lock and skip the rebuild of a schema-2 index): reader guarantee and rebuild exclusivity hold with
concurrent Upgrades and with a death anywhere, without the two premises.
**Witnesses.** `witness_concurrent_upgrades` (W-O2a): two calls pass the pre-lock check; the first
finishes and clears the flag while the second is in flight, a writer is admitted, and the second kills
df on a schema-2 index (Search reads df(7) = 0 for a term with a posting). `witness_crash_after_flip_rerun`
(W-O2b): death after the flip leaves the flag; the re-run's pre-check proceeds because of the flag and
kills df on a schema-2 index. `witness_repair_rerun_keeps_index`: the same history under the repair stays
consistent and clears the flag (valid outcome survives).
**Not represented.** The tf walk's partial states (atomic `Rebuild`; readers of schema 1 do not read df
except through the l.305-311 fallback, which needs schema 2); `cfg avgdl`/`k1`/`b`; Build or Drop during
Upgrade (both ignore the flag and the lock: O1's F2).

## O3 — embedding identity and routing

**Sources and the decision current at the pin.** ADR-0006 (accepted 2026-09-19: identity in
`embedding_registry`, refusable before the write, on installs with no ledger; "a write that disagrees is
refused"). It is **amended in effect, not in text**, by the 4.0.0 decision (CHANGELOG "routed tables, one
per (graph_id, model_key)", "never derive a name to find a route"): a different declared model is
**routed** to its own pair; refusal remains for width, dtype and mechanism disagreement on the same pair
(`embedding_identity.conflicts`, schema.py:1354-1396), and for `set_embedding_identity` / an
`initialize_schema` that would re-claim a recorded table for another model (schema.py:1211-1215,
1485-1515). CONTEXT.md "Embedding Registry" ("A write at another width or model is refused rather than mixed in
(ADR-0006)") was added on 2026-11-04 (commit 267aaff1, R039), after the 4.0.0 routing release of
2026-09-22 (e0438914): a later restatement of ADR-0006 that was not reconciled with routing, not an older
superseded text (corrected per review R1-9; round 0 said it "predates routing"). Routing still governs
writes that name a `model_key` (CHANGELOG 4.0.0, migration guide "Routed tables", USER_GUIDE §7 "Several
models"); refusal still governs a declared different model on one recorded table. The newer glossary
text strengthens the "refuse" side of open question Q1.
**L1** (`l1_must_refuse`, `read_table`, `one_row`): a write is refused iff the pair's recorded identity
disagrees on width, dtype, or (both naming a model) model or mechanism; otherwise the vector is stored
where every reader of its (graph, model) pair reads it; one registry row answers each pair.
**L2 → L3.** `read_route` = `_read_route` embeddings.py:377-468 with `_route_preference` l.107-118;
`read_table` = `_route_for_read` l.652-679; `is_default_pair` l.743-753; `store` = `store_embedding`
l.942-1025 (`_route_for_write` l.755-791, `resolve_route(create=True)` l.237-300 with the per-process lock
and PK arbitration modelled as one atomic creation, `enforce_embedding_identity` schema.py:1354-1396 with
`graph_id = route.graph_id or ""` l.981-987, `get_embedding_identity` schema.py:1033-1084 swallowing every
exception l.1054-1056, `_route_width` length check l.991-995); `conflicts` = embedding_identity.py:180-241;
`enqueue_admits` = embeddings.py:1838-1842; `process_entry` = EmbedQueue.cls `ProcessBatch` l.258-337
(target l.282-283, `RouteTable` l.220-235); `claim` = set_embedding_identity's conditional UPDATE
schema.py:1177-1209 (also run by `_record_configured_embedding_identity` from `initialize_schema` l.2568).
**Theorems.** `theorem_store_routes_and_refuses` (fresh reads: refusal ⇔ `l1_must_refuse` of the pair's
recorded row; on success the vector is read back by its pair; `one_row` and `routed_rows_ok` kept);
`theorem_identity_check_ignores_ledger` (the outcome is the same with the ledger on or off — the
transcription reads no ledger state; grep finds no ledger reference in `_engine/embeddings.py`).
Premises: P_hash (`names_ok`: route names distinct from the legacy table and each other — sha256-16, not
proved); P_routed_rows (no `force=True` re-claim of a routed table); `one_row` on entry; P_col (a table's
column width equals its row's recorded width — `reconcile_recorded_dimensions` schema.py:1688-1710 and
route creation at the vector's width).
**Witnesses.**
- `witness_queue_default_graph_misroutes` (W-O3a, F8): with kg_NodeEmbeddings adopted-unknown, a
  default-graph entry for model B passes the enqueue check; the IRIS worker writes it into kg_NodeEmbeddings;
  readers of ('', B) miss it, the undeclared default pair reads a B vector; `store_embedding` would have
  routed it to B's own table.
- `witness_queue_writes_into_claimed_table` (W-O3b, F8): queued while unclaimed, kg_NodeEmbeddings then
  claimed for A, the worker writes B's vector into A's table (time of check ≠ time of use; the worker
  checks nothing).
- `witness_claim_after_route_splits_pair` (W-O3c, F9): A writes to the default graph while
  kg_NodeEmbeddings is unknown (A's own route is created); claiming kg_NodeEmbeddings for A gives two rows
  for ('', A); the preference picks kg_NodeEmbeddings and A's stored vector is no longer read by A.
- `witness_identity_fail_open` (W-O3d, F11): a cached route plus a failed identity SELECT admits a writer
  whose mechanism disagrees with the row; refused with a fresh read and under the fail-closed repair.
- `witness_undeclared_default_vs_named` (W-O3e, open question Q1): an undeclared writer is width-checked
  only and lands in model A's kg_NodeEmbeddings on the default graph; on a named graph it gets its own route.
**Skipped checks, as the sources decide.** Registry absent (SQLCODE -30): unrouted, nothing recorded,
write passes (documented: "a pre-3.2.0 schema … nothing recorded to conflict with"). Registry read error:
`_read_route` raises (4.6.0 R161) but `get_embedding_identity` returns None (fail-open, W-O3d). Queue
worker, default graph: no identity check at all (W-O3a/b). Python worker: checks only that the entry's
model is the worker's own (`_assert_entry_is_this_workers_work` l.1987-2016).
**Not represented.** Edge routes (`kind`; symmetric code), `kg_NodeEmbeddings_optimized`, the 30 s cache
TTL as time (a cache entry is any earlier read), quarantine (O4, not in scope), the SQL `kg_KNN_VEC`
procedure, IVF/PLAID/VecIdx.

## O5 — erasure over search stores

**Sources.** ADR-0004 (accepted: "removes graph content from every store that holds it"; "every deletion
path funnels through the Eraser"); `GraphStores.cls` l.1-16 ("the one declared inventory", including the
stores it cannot scope) and l.113-116 (AlgoCache: "no answer outlives erased content"); Eraser.cls
l.138-144 (the BM25 corpus rationale).
**L1** (`no_erased_answer`): after EraseGraph(g), a search of an index that answers for g returns no
erased node of g. **L2 → L3.** `erase_graph(_, _, false)` = `Eraser.EraseGraph` l.47-313 via
`engine.erase_graph` nodes_edges.py:1473-1520; `^BM25Idx` is in neither list of `GraphStores.Inventory`
l.25-123 and no erase path references it (grep: no `BM25`/`IVF`/`PLAID`/`VecIdx` in Eraser.cls); `build`
= BM25Index.Build l.97-175 with `cfg graph` l.168; `hit` = SearchCore's posting walk.
**Theorem.** `theorem_repaired_erase_removes_answers`: the repair (drop indexes whose recorded graph is g)
satisfies L1 and leaves every other graph's index unchanged. **Witness.** `witness_erase_leaves_bm25`
(W-O5): build for graph 1 over node 5, erase graph 1, Search still answers node 5; re-create node 5 with
other text and the erased text still scores it. **Not represented.** IVF (`^IVF` records a route table,
no graph), PLAID and VecIdx (no graph at all): they cannot be attributed by recorded graph and would need
an "unscoped, rebuild after erase" inventory entry; a pre-230 BM25 index reports graph "" for all graphs
(Info l.608-612), so erasing the default graph under the repair would also drop it.

## Trust inventory

- `uninterp spec fn route_name(g, m)` — the sha256-16 route table name; used only under `names_ok()`
  (P_hash), stated as a `requires` wherever it matters.
- No `assume`, `admit`, `external_body`, `assume_specification`. vstd only.
- Abstractions: loop bodies of RemoveDoc / the add loop / IndexDoc as set-level effects (P_distinct);
  Upgrade's counting walks by their closed forms; Insert/Delete split at RemoveDoc's loop, its tail, the add
  loop and TCommit in the O1 writer system (atomic in O2); `undo` encodes P_undo; W-O1d additionally needs
  P_unlock_in_txn, which the native probe refuted (the branch is unreachable).

## Controls (`model.json`)

25 controls (each must make the named functions fail when verified alone): one or more per proved
property (a decisive guard or effect removed: `removedoc-keeps-df`, `insert-without-removedoc`,
`vocab-not-counted`, `cutoff-ties-to-last`, `cutoff-no-fallback`, `cutoff-counts-unknown-terms`,
`upgrade-no-flag`, `upgrade-flip-before-count`, `upgrade-rebuild-wrong-df`, `upgrade-writer-ignores-flag`,
`upgrade-keeps-idf`, `identity-no-width`, `route-created-without-lookup`, `identity-reads-ledger`);
repair-off controls showing each repair theorem depends on its repair (`repair-insert-ignores-build`,
`repair-drop-ignores-writer`, `repair-build-ignores-writer`, `repair-delete-checks-n-first` (R2-1),
`repair-recheck-off`, `repair-fail-closed-off`, `repair-erase-keeps-bm25`); premise/mechanism controls showing each witness depends on the as-built
mechanism (`as-built-build-locked`, `as-built-no-drop` — W-O1c fails with Drop disabled, review R1-8 /
Adv-3a —, `as-built-delete-without-early-return` — W-O1e comes from Delete's early return, R2-1 —,
`as-built-upgrade-serial`, `queue-routes-default-graph`); and one valid-outcome control
(`repair-erase-drops-every-index`: an erase that drops every index satisfies "no erased answer" but breaks
the frame clause). Round 0: 22/22 EXPECTED_FAIL (`receipts/search/`, superseded). Round 1: 25/25
EXPECTED_FAIL (superseded by round 2). Round 2: all 27 re-run one at a time (`CONTROL=<name>`) against the
current `search.rs` and `model.json`
(`~/runs/iris-vector-graph-g5-verus-20261113/agents/B-search/controls-round2.txt`). Round-1 run notes: The full `controls` run
was stopped by the shell's 10-minute background limit after its first 22 controls (all EXPECTED_FAIL); the
3 new controls were then run one at a time with `CONTROL=<name>`
(`~/runs/iris-vector-graph-g5-verus-20261113/agents/B-search/controls-round1-tail.txt`); round-1 receipts
`results/search/20261114T00*`. Round-2 receipts: `results/search/20261114T03*`/`T04*-control-<name>/receipt.json`,
prove `results/search/20261114T035601Z-prove/receipt.json`.

## Native probes and observations

All in `.g5/Verus_verification/native/probes/`, using `harness` through `search_common.py` (verdict
printer and a read-only brute-force recount of `^BM25Idx`). Expected outcomes come from the L1 rules, not
from the implementation. Observations: `.g5/Verus_verification/receipts/native/search_*.json` (run by the
orchestrator on this arm). Probe-run premises: IRIS Community Edition on this arm (container
ivg-g5-verus-20261113-iris, port 35972), its connection/license limit (the run log shows "Unable to allocate
a license" warnings from the conftest hostname read; they decided no verdict), and kg_NodeEmbeddings declared
at width 768.

| Probe | Case | Observed |
|---|---|---|
| `search_bm25_erase.py` | F1 / W-O5 | **OBSERVED_DEFECT**: after `erase_graph` the erased node is still answered, and still scored by its erased text after re-creation with other text |
| `search_bm25_build_insert_race.py` | F2 / W-O1a,b | **OBSERVED_DEFECT**: 99 L1 violations with nothing in flight (df off by one against postings, …); 167 Inserts committed inside Build's 0.38 s window |
| `search_bm25_caller_txn.py` Part A | F3 | **OBSERVED_DEFECT** (`search_bm25_caller_txn_rollback`): a failed `bm25_insert` (`<SUBSCRIPT>` on a long id) took the caller's `$TLEVEL` from 1 to 0; the node the caller created earlier in its transaction is gone after its error-free commit |
| `search_bm25_caller_txn.py` Part B | P_unlock_in_txn (W-O1d) | **OBSERVED_AS_EXPECTED** (`search_bm25_caller_txn_lock`): the second writer waited 3.0 s for the caller's rollback; counters consistent. W-O1d's premise is false; that branch is unreachable |
| `search_bm25_cutoff.py` | cutoff binding | **OBSERVED_AS_EXPECTED**: 6/6 cases match FR-044-C1..C5 |
| `search_bm25_upgrade_concurrent.py` | F4 / W-O2a | **OBSERVED_DEFECT** (transient): both calls converted (`upgraded: 1` twice); 18 of 22 Searches for a term in every document answered `[]` during the upgrades; the final state is consistent |
| `search_route_split.py` | F9 / W-O3c | **OBSERVED_DEFECT** (re-run at width 768): two registry rows answer ('', g5probe-model-a) and `get_embedding` returns nothing although the vector is in its `kg_emb_` route. The probe now takes the width from kg_NodeEmbeddings' recorded row instead of a constant (R1-12) |
| `search_queue_default_graph.py` | F8 / W-O3a | **INCONCLUSIVE**: no `%Embedding.Config` (Community ships the table empty). A 768-wide config needs an embedding class whose model IRIS's embedded Python can load (e.g. `%Embedding.SentenceTransformers` with sentence-transformers and the model files); this arm was not provisioned with them, so Community here cannot provide one. The probe now has an opt-in fixture (`G5_EMBED_MODEL`, `G5_EMBED_CACHE`, or `G5_EMBED_CONFIG`) for an arm that is |

## Candidate findings

Status key: CONFIRMED-BY-PROOF-OF-MODEL = a proved trace of the transcription; OBSERVED = the native probe
saw the violating outcome at the product's public entry points on this arm.

**Bugs**
1. **F1 / W-O5 — BM25 answers outlive `erase_graph`.** High (review R1-7: erasure governs here — CONTEXT
   "Erasure", ADR-0004 "a write path that touches one store without the others is a bug", ADR-0013 —
   while node deletes keep the caller-upkeep decision). Observed (code): no erase path touches `^BM25Idx`;
   the index records its graph. CONFIRMED-BY-PROOF-OF-MODEL; **OBSERVED** (`search_bm25_erase`). `^IVF`,
   `^PLAID`, `^VecIdx` hold copies of erased vectors by the same code reading (not probed).
2. **F2 / W-O1a, W-O1b, W-O1c, W-O1e — Build and Drop write without the lock or a transaction, and a
   Delete issued during a Build is lost.** Medium. Expected:
   ADR-0007 "every write under an index-level lock", FR-016/FR-018 "at every committed point". Committed
   inconsistent states (N vs len, df vs postings, a resurrected schema-less index). CONFIRMED-BY-PROOF-OF-MODEL
   (all are traces); **OBSERVED** for Build (`search_bm25_build_insert_race`); W-O1c (Drop inside an
   Insert) not probed (microsecond window). W-O1e (R2-1): `bm25_delete` during a Build answers False and the
   Build republishes the document; the round-1 repair (lock Build and Drop) does not close it — Delete must
   also test N under the lock. CONFIRMED-BY-PROOF-OF-MODEL; SUSPECTED (not probed).
3. **F3 — Insert/Delete Catch rolls back every level of a caller's transaction** (`If $TLevel > 0 TRollback`,
   l.487/508). High: a failed `bm25_insert`/`bm25_delete` silently aborts the caller's transaction, and the
   caller's later commit reports success. Expected: IVG's undo takes back its own level (`_write_txn.py`
   4.6.4; Eraser's `TROLLBACK 1` loop). Reachable from Python whenever the engine is built on a plain DB-API
   connection (native calls share the caller's process). Inspection, not modelled; **OBSERVED**
   (`search_bm25_caller_txn_rollback`). The lost-update variant W-O1d is **not reachable** (lock kept to
   the end of the caller's transaction, `search_bm25_caller_txn_lock`).
4. **F4 / W-O2a, W-O2b — Upgrade does not re-check under the lock.** Medium-low (two operators, or a death
   during `Kill idf`). Expected: FR-023. CONFIRMED-BY-PROOF-OF-MODEL; **OBSERVED** for W-O2a, transiently
   (`search_bm25_upgrade_concurrent`: 18/22 Searches empty while the second call rebuilt df on a schema-2
   index; the end state is consistent). W-O2b needs a process killed after the flip: not probed.
5. **F8 / W-O3a, W-O3b — the IRIS queue worker writes every default-graph entry into kg_NodeEmbeddings with
   no identity check.** Medium. Expected: 4.0.0 routing; ClaimPendingBatch's own rationale (EmbedQueue.cls
   l.108-111). CONFIRMED-BY-PROOF-OF-MODEL; SUSPECTED (probe INCONCLUSIVE: no embedding model on this
   Community arm).
6. **F9 / W-O3c — claiming kg_NodeEmbeddings after a model's default-graph route exists splits the pair.**
   Medium. Expected: one route per pair (FR-011 as quoted). Observed: no uniqueness on (graph, model, kind)
   in the registry; `_route_preference` picks the legacy table. CONFIRMED-BY-PROOF-OF-MODEL; **OBSERVED**
   (`search_route_split`, width 768).
7. **F11 / W-O3d — identity enforcement fails open on a registry read error after a cached route.** Low.
   Width is still checked from the cached route; mechanism, dtype and model are not. CONFIRMED-BY-PROOF-OF-MODEL;
   reachability needs a failing SELECT after a successful one within 30 s (permission change, transient
   error): not inducible through public entry points, no probe.

**Simplifications (proposals, each proved or distinguished in the model)**
- S-a: Build and Drop take the index write lock for their whole run (or Build builds under a temporary name
  and swaps under it), **and** Delete takes the lock before it tests cfg N — `theorem_locked_build_preserves`
  (counters, including Build and Drop inside an Insert or Delete) and `theorem_repair_delete_takes_effect`
  (a returned Delete stays in effect); distinguishing cases W-O1a, W-O1c and W-O1e
  (`witness_round1_repair_loses_delete` shows the lock alone is not enough). A build-and-swap variant must
  likewise make a Delete during the build apply to the new index. Preserve: Search keeps working; a Build
  still replaces the index.
- S-b: Upgrade re-reads `schema` under the lock and skips the rebuild of a schema-2 index —
  `theorem_repaired_upgrade_preserves`; distinguishing cases W-O2a/b; `witness_repair_rerun_keeps_index`
  shows the re-run still clears the flag.
- S-c: the Catch uses `TROLLBACK 1` down to the entry level (as the Eraser does). Distinguishing case:
  probe Part A.
- S-d: `get_embedding_identity` raises on a read failure other than SQLCODE -30 (the R161 policy of
  `_read_route`), or enforcement reuses the row `_read_route` read — `witness_identity_fail_open` shows the
  refusal comes back.
- S-e: the IRIS worker resolves default-graph entries through the registry like named ones (control
  `queue-routes-default-graph`), or refuses them unless the entry's model owns kg_NodeEmbeddings.
- S-f: EraseGraph drops (or empties) the BM25 indexes whose `cfg graph` is the erased graph, and the
  inventory lists `^IVF`/`^PLAID`/`^VecIdx` as unscoped derived stores — `theorem_repaired_erase_removes_answers`
  with the frame clause; distinguishing case W-O5.

**Open questions (human decision needed)**
- Q1 (W-O3e): may an undeclared writer add same-width vectors to a model-claimed default table? FR-010 (as
  quoted in code) supports today's "yes"; CONTEXT.md, in a restatement added 2026-11-04 after routing, says
  "refused rather than mixed in"; named graphs isolate it.
- Q2: record the 4.0.0 "route a write that names another model_key" decision as a "Later" note on ADR-0006
  and reconcile CONTEXT.md "Embedding Registry" (its 2026-11-04 wording restates ADR-0006 without routing).
- Q4: Search reads `^BM25Idx` without isolation during a write transaction (FR-019 "Search takes no lock");
  is reading uncommitted or mixed N/df/len acceptable?
- Stale-flag message: after a death during Upgrade, writers are refused with "is being upgraded", not
  "re-run Upgrade" (l.388-389).

## Proof development log (failed attempts)

Scratch copies of each stage are in `~/runs/iris-vector-graph-g5-verus-20261113/agents/B-search/` (`a.rs` …
`k.rs`, `*_dbg.rs`). Failures met and how each was resolved (no property was weakened):
- RemoveDoc lemma: the record-term facts needed explicit instantiation of the doc/tf trigger (1 error → 0).
- Build theorem: `publish(..) == add_doc(..)` needed map extensionality of the two `add_postings` results.
- Cutoff scan: failed until the premise df ≥ 0 was added. This is a real distinction, not a proof aid: the
  code's test is `tD = 0` while the rule says "df > 0"; they coincide only for non-negative df (kept by
  RemoveDoc's kill at ≤ 0). Recorded as a premise.
- Upgrade invariant: a first draft used `assume(false)` for "an index with no N" in the Insert case; it was
  replaced by the invariant clause `n is None ⇒ is_absent ∧ ¬upgrading` (no assume remains). Further
  failures were missing frame lemmas (`lemma_s1ok_frame`, `lemma_cons_frame`, `lemma_rebuilt_frame`) and
  explicit existential witnesses.
- Repaired-upgrade theorem: `lemma_rebuilt_frame` was first called for Insert/Delete, where tf changes
  (precondition failure); moved under the non-writer cases.
- O5: `Set::map` membership needed a named projection (`node_of`) and an explicit witness.
- Review round 1 (R1-8): W-O1c was a hand composition and verified with Drop disabled (Adv-3a). Insert and
  Delete were split into `InsBegin`/`DelBegin`, `WTail`, `WAdd`, `WCommit`; the repaired Drop and Build wait
  for an in-flight writer; `winv` gained the in-flight clause `s.ix == stage(r)`. The refactor of
  `add_doc` into `add_body` + `add_counters` and of `insert_body` through `init_ix` left every earlier proof
  intact (49 → 50 verified with `lemma_tok_empty`). With Drop disabled, W-O1c now fails
  (scratch `search_nodrop_r1.rs`: 49 verified, 1 error in `witness_drop_inside_insert`).
- Review round 2 (R2-1): ghost `WSys.gone`, variant flag `delete_under_lock` (as-built false; `locked_build()`
  true; `round1_repair()` = the round-1 repair), `gone_ok`, `theorem_repair_delete_takes_effect`, witnesses
  W-O1e, `witness_round1_repair_loses_delete` (its counter-consistency claim proved by chaining the
  round-1 theorem over each step, after showing each step is the same under both variants),
  `witness_repair_delete_after_build`. Two first-attempt errors: `!gone_ok(s4)` needed the explicit witness
  (document 1 in `gone`, nothing in flight). 50 → 56 verified.
