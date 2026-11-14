Review 4, semantics slice (scratch data; the review text is REVIEW-4.md).
- sem_logs.py: compares each sem-* record's observes with its family log (counts, max states, laws, control->law, passing names).
  Output sem_logs.out: 43 log-parsed records MATCH on those fields (sem-check, sem-check-selftest read by hand).
- Specificity test: a copy of models/semantics in $RUN_DIR/review-4/semantics/crate-complement with harness.rs Keep::only
  changed to keep every safety property EXCEPT the named ones (only change). Run: cargo run --release (exit 1 by design,
  123 of 266 met). specificity.txt: 19 of 59 controls and 38 of 84 as-built/exception violation checks also violate
  another law (exhaustive within bounds). undeclared.txt: 21 as-built checks whose instance violates a law for which the
  instance has no declared departure.
- Faithful rerun: $RUN_DIR/review-4/semantics/RESULTS.json, rerun-all.log: 266 of 266 met, identical to the registered run.
- Checker reruns: $RUN_DIR/review-4/semantics/*.log (working tree, HEAD 7b72fc52 export, e8a0d08a export).
