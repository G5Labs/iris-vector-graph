# Retained retry-replay questions before candidate

Product3eaa79cf; foundation9e6a876f. Iteration7 posteffect-PAIRS/native4 is a known
builder-visible input, not held-out evidence. Canonical temporal.write.partial-failure
and temporal.edge.clock describe the ingredients. Current temporal_clock derives
pre-effect fallback only; no formal composition derives a completed Counts prefix
plus whole-batch fallback with different clock interpretation.

- R1 complete native zero write then lost reply: now and epoch0 are both visible,
  while caller reports written1/collision0. Prewrite failure gives only epoch0.
- R2 explicit100: normal completion then lost reply/fallback keeps one coordinate;
  existing-coordinate input can return written1 although no fresh event is inserted.
- R3 mixed zero/100 or partial completed prefix: derive each completed prefix via
  the actual writer, then resend every normalized item. Do not supply a post-state
  or resume only the tail. Expected three events for the complete mixed native case.
- R4 normal success versus fault uses the same raw caller input. Normal zero has
  only now; a zero-valued clock is a legitimate overlap where fallback collides.
- R5 invalid later input prevents all port calls; empty batches never consult Counts,
  even if its supplied failure phase says an error would occur.

Only default insert/accepted fallback calls are modeled. Provider fault point is a
completed item boundary, including no completed items and after whole success;
partial effects inside WriteStores, genuine TCP failure, all modes/aggregates,
strict ledger and concurrent clocks/writers remain explicit residuals. No new
bug is inferred: bug-tmp-001 and F-0502 remain inherited roots.
