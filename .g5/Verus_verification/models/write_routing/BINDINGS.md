# write routing

Whether an engine write joins the caller's transaction: WriteTxn nesting (Txn_Begin/End/Undo), routing of a call to the caller's or the engine's own server process (from_connect), direct ObjectScript calls' global-then-SQL order under driver autocommit off (temporal write, batch and delete, iteration 31), the caller-transaction refusal; failed-write undo not natively exercised

Evidence status: active. Variant: as-built bounded transcription.

Verified and errors count obligations reported by the verifier. A control is judged against its named expected failure. Native observations have their recorded scope.

[Formal source](write_routing.rs)

[Formal claims, product bindings and limitations](NOTES.md)

[Premises](NOTES.md)

[Product and declaration crosswalk](../../crosswalk/decision-links.tsv)
