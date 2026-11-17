# W1 open-question snippet (additive; parent integrates into open_questions.md)

No new question: the existing card [access.transactions](../../../../Verus_verification/open_questions.md#access.transactions)
("Must the Neo4j-compatible surfaces keep Neo4j's transaction meaning?") already lists the two answers. Do not change
its anchor, card fields, prompt, default_assumption or answer. Proposed **additive** evidence bullet, appended after its
existing "- A Neo4j HTTP batch keeps …" bullet:

- Iteration 56 (review 53-55 F1): reproduced end to end with the neo4j driver 6.4.1 and a raw Bolt client against the product's own listener ([bug-plt-127](bugs_issues.md#bug-plt-127), [bolt_tx binding](results/bolt_tx/20261117T065936Z-binding/receipt.json)): rollback, a failure then rollback, RESET, a closed connection and an aborted `execute_write` all keep the transaction's writes while every answer is SUCCESS. Both listed answers rule this out; the new owner [access.bolt.transactions](../ontology/concepts/access.g5.md#access.bolt.transactions) states that shared rule, and the model checks both repairs (`atomic-tx`, `begin-refused`). What remains open is only which repair.

Note for the parent: [access.bolt](../ontology/concepts/access.g5.md#access.bolt) no longer carries the bullet
"Working assumption: Assume per-statement commits on Bolt until an explicit transaction contract is established."; it
now says auto-commit statements commit on their own and points to `access.bolt.transactions`. The card's
"Disposition: open. Working assumption: …" line is left as is (append-only rule); if check_findings requires the
owner and card working assumptions to match, add to the card (append) "Iteration 56: the owner now states the shared
rule; auto-commit statements still commit on their own."
