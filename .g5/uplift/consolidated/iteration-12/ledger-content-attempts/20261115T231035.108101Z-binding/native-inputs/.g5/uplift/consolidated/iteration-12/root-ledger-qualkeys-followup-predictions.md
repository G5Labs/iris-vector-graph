# Follow-up after native empty-key forecast refutation

The original qualifier-key predictions and native.py/json/log remain unchanged.
Its first relationship call refused with LedgerInconsistencyError and <SUBSCRIPT>
at QualsJson's local tKeys("") assignment. Thus the skip-empty forecast is
refuted; it was a source-only native-provider assumption, not a product defect.

This follow-up is explicitly exposed to that outcome. New empty-key create should
refuse without a row/revision; existing upsert should likewise refuse at MergeQuals
before changing its old qualifier. Nonempty-key new/upsert neighbors should emit
the ordinary exact records and contents. Direct empty-key setter should retain
its separate Python ValueError, and node batch empty-property should fail through
SetProp with its transaction prefix rolled back. These are finite provider checks,
not a blind prediction score or a universal native-local-subscript proof.
