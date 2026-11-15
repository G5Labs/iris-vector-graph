# Strongest remaining timestamp/fallback candidate, before native probe

Product3eaa79cf, iteration7 candidate frozen. Current temporal_clock deliberately
models Counts unavailability before any effect. Inherited temporal G models fixed
coordinates/partial structural writes (bug-tmp-001), and the new clock model makes
zero route-specific. Neither current composition derives a post-effect Counts
error followed by fallback at another coordinate. This is an inherited-root
composition question, not a new adjudicated bug or private holdout.

- R1 zero: actual Counts succeeds and writes a current-time event, then its port
  reply raises before caller receives it. Actual fallback should also write epoch0
  for that same raw input. Prediction from source/clock composition: two observable
  events for one input, though fallback reports count1. Formal composition partial.
- R2 positive100: same lost-reply event followed by fallback should collide at100,
  keep one event, yet report successful-call count1/collisions0. Existing fixed-
  coordinate and count theorems cover ingredients, not the actual composed call.
- R3 a mixed zero/100 batch: expected three final events for two input items, not
  an arbitrary repeated-count inflation claim. A prewrite failure neighbor should
  produce only the fallback coordinates. Retain successful provider return and
  actual persisted readers; the injected post-effect exception is not a real TCP
  failure, partial-prefix failure or a product patch.

Materiality test: do these current models/canonical qualifications answer the
ordinary retry consequence, or does an explicit prefix/ack outcome materially
change a caller decision? Keep the result either way before convergence assessment.
