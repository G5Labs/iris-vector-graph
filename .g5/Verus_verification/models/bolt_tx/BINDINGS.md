# bolt transactions

Bolt explicit transactions: BEGIN, COMMIT and ROLLBACK answer SUCCESS and keep no transaction, and every RUN commits at once, so a rolled-back, failed, reset or abandoned transaction keeps its writes (bug-plt-127, formerly F-1601); commit and auto-commit agree with the rule; refusing BEGIN is a checked repair

Evidence status: active. Variant: as-built bounded transcription.

Verified and errors count obligations reported by the verifier. A control is judged against its named expected failure. Native observations have their recorded scope.

[Formal source](bolt_tx.rs)

[Formal claims, product bindings and limitations](NOTES.md)

[Premises](NOTES.md)

[Product and declaration crosswalk](../../crosswalk/decision-links.tsv)
