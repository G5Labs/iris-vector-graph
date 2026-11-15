# Bulk delete counts after primary and cleanup failures

As-built orchestration `3eaa79cf`, **10 verified / 5 controls**. Owner `structure.node.delete.bulk`; receipts/logs `results/bulk_delete/`.

Raw input normalization removes None/empty IDs and repeated string IDs; the model represents these as Missing/Empty/Id. Batches have positive size and one explicit graph. External primary and cleanup failures are scripted by ID-trigger sets. The model derives order: successful primary deletion changes the node map before secondary cleanup can raise. A caught error adds the entire request count to failed, adds no deleted count and continues later batches. Int/bool conversion uses deleted only.

Named proof neighbors: normalize/filter/dedupe; successful deletion of both nodes; first batch refuses but second succeeds, returning (1,1), int 1, bool true, first node still live; failed count includes a requested nonexistent ID; cleanup failure after primary removal returns (0,2), int 0, bool false despite both nodes gone. `theorem_cleanup_failure_is_not_rollback` preserves the latter departure rather than assuming an atomic provider.

Five controls detect duplicates retained, stop after first refusal, hidden failed count, bool interpreted as no failures, and cleanup failure ignored. Initial proof left two concrete refusals unproved; replacing an existential helper with a recursive blocked predicate discharged them without changing allowed outcomes. Earlier receipt remains.

`binding.py` executes actual `NodesEdgesMixin.bulk_delete_nodes`, `_delete_in_scope` and DeleteResult over **1,872** cases (raw sequences length 0..3 over five values; size 1/2/3; primary rejection and cleanup failure choices). Store, reifier census and ledger guard are substituted. The actual Python primary/secondary producer order runs, including exception wrapping and partial live-node effects. Failed-count product mutant and changed live-content observation are detected. No live erasure service or security probe runs.

Sources: `nodes_edges.py::{DeleteResult,NodesEdgesMixin.bulk_delete_nodes,NodesEdgesMixin._delete_in_scope,NodesEdgesMixin._delete_scopes}` and `IRISGraphStore.delete_nodes/_eraser_txn`. Actual IRIS per-chunk behavior remains inspected/inherited as bug-led-011; this is not a new product finding. The reifier cleanup partial path is a related cause with the same catch/count consequence. Graph discovery, ambiguity refusal, invalid batch size, reifier effects on other stores, nested/cross-process transactions and full erasure semantics remain outside the proof. The canonical owner states the observed limitation.

Trust: pinned vstd, no assume/admit/external_body/actors. Scripted providers and expected count fold are unverified. Specification proof plus unit-level native Python correspondence, no implementation proof.
