# Ordered application and failure rollback

Product: `3eaa79cf77d3e0a879b2cced634cf2729d81499e`. Owner: `ledger.commit`.
As-built transcription, **9 verified / 5 controls**. Run `run_verus.py prove|controls` on this directory; receipts and copied logs are under `results/ledger_apply/`.

`apply_all` takes raw Create/Label/Set/Rel operations. `fails` reads node existence, reserved keys and existing relationships; `write` derives prior/new records and suppresses no-op sets. `commit` publishes the produced record list with the new head/binding only after the whole sequence succeeds. `revision` consumes that published list. This replaces the missing producer/failure boundary for the selected M03 pair, not the inherited admission protocol.

Named obligations: `theorem_two_writes_produce_priors` (fresh node, absent→1→2 and revision reader), `theorem_noop_has_no_property_record`, `theorem_same_value_records_nothing`, `theorem_real_endpoint_decides`, `theorem_valid_relationship_reachable`, `theorem_mid_failure_rolls_back_prefix` (create/label/property/relationship prefix, unknown endpoint at zero-based 4, no prefix, allocation or revision persists), `theorem_failure_publishes_nothing`, `theorem_reserved_key_refuses`.

Controls: discard prior, leak prefix, drop target-endpoint guard, record same value, report index zero. Each fails its named theorem; the successful relationship neighbor still proves in the baseline.

Exact source bindings:

- `LedgerApply.cls::{ApplyAll,NodeExists,IsReserved,OpSetProp,SetProp,OpCreateRel,Rec}`: dispatch, producer guards, prior/new encoding and first failure. `OpCreateNode` and `OpAddLabel` supply the selected prefix.
- `Ledger.cls::{Commit,CommitInTxn,WriteRevision}`: transaction boundary, refusal before publication, ordinal record storage and binding.
- `GraphLedger.get_revision`, `iter_records_sql`, `MutationRecord.from_row`: final Python revision reader; `GraphLedger._commit` and `from_commit_error` preserve the failing operation index. See exact ranges in `crosswalk/decision-links.tsv`.

`binding.py` executes the real builder/wire conversion and real Python revision paging, null decoding, graph replay and error mapping in **9** property scenarios. A reference writer and SQL provider supply rows. The reference is an **unverified hand translation**, not ObjectScript execution or evidence that the server generated those records/rolled back. Reversed reader order and changed prior observations are detected. No end-to-end IRIS result is claimed.

Premises: normal changeset already admitted; one default graph; SQL/global transactions roll back together; successful SQL writes are faithful; head serialized; new statement IDs are fresh. Provider exceptions beyond the represented missing/duplicate/reserved guards, other operation kinds, graph aliases/temporal adoption, redaction, post-commit properties, caller transactions, dirty flags, metrics and concurrent writers remain outside this model. This is a spec proof and inspected ObjectScript binding, with a Python consumer observation. Direct implementation proofs: **0**.

Trust inventory: bundled pinned `vstd`; no assume/admit/external_body or actors dependency. Same pinned Verus as inherited. Product/tests unchanged. Live M03 rollback test is inherited/upstream, not rerun here.
