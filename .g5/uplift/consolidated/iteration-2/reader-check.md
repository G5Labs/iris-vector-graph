# Canonical reader self-check, iteration 2

Self-check, not independent review. The answers below use the owning ontology body, including its stated departures and policy questions. Source and model text are not needed to derive these answers; this does not independently validate them.

| Situation A / B | Predicted observation | Canonical owner |
|---|---|---|
| Create node, set k=1, then 2 / append relationship to unknown endpoint after a prefix | First returns both prior/new records and final 2; second reports the failing zero-based position and leaves no revision/content prefix | ledger.commit |
| History always within bound / history exceeds it then shrinks | Ordinary reader returns first, refuses second even at equal final size | ledger.readers.bound |
| Same oversize history ordinary / stream or export | Ordinary raises; stream/export skip bound but fully materialize the requested graph | ledger.readers.bound |
| Read revision 1 / read revision 2 with an extra entity | Later records cannot affect the earlier read's content or bound refusal | ledger.readers.bound |
| One item first / repeated later at different provider score | First occurrence determines RRF contribution; changing magnitudes alone does not change rank-derived score | search.fusion.python |
| Successful empty vector leg / failed vector leg, with text succeeding | Empty leg is retained in mode details, failed leg is omitted; neither substitutes a failure for an empty success | search.fusion.failed_leg |
| Failed vector / failed text | Wrapper drops vector failure and may return incomplete ranking; text error raises, a stated departure from intended per-leg failure reporting | search.fusion.failed_leg |
| Two delete batches, first fails / both succeed | Failure is counted and later batch still runs; a true boolean can coexist with failures | structure.node.delete.bulk |
| Primary nodes removed then cleanup fails / primary call refused before removal | Both may count as failed, but only the second guarantees those nodes stayed. False/int-zero cannot establish no content change | structure.node.delete.bulk |
| Shared fusion policy / helper API support | Neither has owner acceptance; common zero versus distinct documented surfaces and continued compatibility versus deprecation remain proposals | search.fusion.absent, search.fusion.python.support |

Known limitations remain visible in canonical metadata: ledger model is a subset with inspected server bindings; reconstruction is a structural projection; fusion's general sort/details are observed; bulk providers are substituted. No implementation-verified claim or changed cache/restore claim is inferred.
