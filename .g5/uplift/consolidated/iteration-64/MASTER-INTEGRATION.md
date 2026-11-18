# Iteration 64 — master integration

- Builder session df90c373 ($77.16; forks + a fresh non-fork blind reviewer of 50 rows) committed b0af31bd. No product
  file or governing ontology wording changed.
- Master replay: census PASS with the new lint (0 problems), deterministic; check_evidence FRESH; check_consolidated PASS.
- **Whole-foundation figure (published with its uncertainty):** 2097 obligations over 406 blocks; full 744 / partial 686
  / absent 667 / unassessed 0 → recorded 35.5%. Blind-sample agreement on kept-full rows 27/30 (Wilson 74–97%), so the
  builder's point estimate is ~32% (≈26–36%). Passing design checks over the full stated scope: 196; proved incl.
  narrowed 1105; bounded 1; refuted 145. Retained-obligation change: −222 full on the same 2097 rows (a correction,
  not a loss of coverage); no scope change.
- **Master decision on `design-verified` tags.** The builder kept the tag only where every obligation is full and none is
  refuted (7 kept, 103 removed). That is stricter than the frozen rule (guidance/ontology-format.md: "`design-verified`
  (… model checking machinery + code linking exist)… needs a linked state machine with recorded runs… A model
  association … does not by itself establish complete verification") and it stripped imported metadata. The master
  restored the tag on the 80 blocks that (a) had it at 3f18ba52, (b) have at least one obligation graded full under the
  strict lint and (c) have decision-link rows; 23 blocks with no fully decided obligation or no code link stay untagged.
  Completeness is reported by the census, not by the tag. `design-verified-tags.tsv` records each block's action.
- Owner contradictions: 48 obligations carry `owner-contradicted:` gaps for the area batches.
