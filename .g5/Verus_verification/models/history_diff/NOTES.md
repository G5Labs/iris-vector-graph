# Named diff, continuous endpoint values and lifecycle snapshots

As-built per-attribute transcription at 3eaa79cf, **12 verified / 6 controls**.
Owner: ledger.readers.diff and its order/snapshot question. Results and raw logs:
`../../results/history_diff/`.

`selected/read/diff` derives (lo,hi] selection, equal-empty and reverse field swap
from raw named sequences. `inverse` keeps entry identity/order and swaps values;
involution is proved for arbitrary entry sequences. Product stable sorting changes
no keys on inversion; global multi-entity sorting itself is inspected/observed,
not proved by this single-entity projection.

`writer` derives the selected attribute's prior/new and deletion snapshot from an
entity's actual state, not a supplied expected delta. It is a semantic record
projection, NOT ApplyAll: it overapproximates harmless same-value records, does not
prove admission, and does not execute SQL or a transaction. Native fixtures omit
same-value records and refuse invalid create/delete/remove histories as inspected
in LedgerApply. `theorem_raw_history_endpoints` proves for every nonempty sequence
of Set/Remove in a continuous life that output is empty iff endpoints match, else
its sole attribute entry carries the actual initial/final values. The relation to
full named graph reconstruction, labels/qualifier maps, arbitrary entities and
JSON parsing remains open.

Producer challenge corrected bug-led-101: actual DeleteNodeRows calls
NodeSnapshotJson, so the old empty-prior simple witness cannot establish missing
old content. `theorem_simple_delete_preserves_snapshot` proves the valid neighbor.
`theorem_change_then_delete_loses_range_prior` derives initial1 -> set2 -> delete
(snapshot2) -> recreate -> set3; the reverse keeps snapshot2 and loses prior1.
Whether lifecycle snapshots must be range-start values or deletion-moment values
needs maintainer ratification at ledger.readers.diff.order. This is stronger
corroboration and a withdrawal of an overbroad old inference, not a new bug count.

Six controls each fail a named theorem: include lower endpoint, skip reverse swap,
last prior wins, retain net zero, expose transient life, drop delete snapshot.
The native Python binding observes **9481 named pairs**, including **8113 continuous
endpoint comparisons**, over all admitted single-node histories of length0..4
from six operations and all named endpoints. Actual GraphLedger.diff/reconstruct,
SQL pagination/decoder, GraphState and inverse execute. SQL/meta/revision IDs,
redaction guard and server writes/snapshots are fixtures; no IRIS observations.
Rich label/property/qualifier/tuple neighbors are supplementary unit evidence,
not full-content formal proofs. Last-prior product mutation and a changed deciding
observation are detected. Fixture expectations are unverified Python.

Trust: bundled pinned vstd only; no assume/admit/external_body, no actors.
Provider premises: valid ordered records, stable history, admitted operations,
faithful SQL decoding and serialized writer/snapshot behavior. Implementation-
verified 0. Initial macro/type errors and later corrected inputs remain recorded;
only latest complete receipts support current claims.
