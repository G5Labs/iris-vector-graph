# Iteration 61 — master integration

- Builder session 1fbd7561 committed `ec56aaf5` (census instrument + 119-block tranche). Master replayed `tools/census.py`: exit 0, deterministic `summary.md`.
- check_consolidated failed only at step 8: the iteration-60 correspondence stamp recorded the Mac Verus binaries
  (`verus-arm64-macos`), this host runs the Linux build of the same release 0.2026.10.04.426d8b0. Product inputs unchanged.
- Resolution (no relabelling): the four models whose latest proofs were produced on the Mac were re-proved and their
  controls rerun here with `run_verus.py`: adjacency_maint PASS 35 (16 EXPECTED_FAIL), bolt_tx PASS 35 (14), ledger_client
  PASS 34 (33), ledger_verify PASS 15 (12) — same verified counts as their iteration-60 receipts. After this all 87 latest
  prove receipts name `~/.local/share/g5-verification/verus-0.2026.10.04.426d8b0/verus-x86-linux/verus`.
- The census citations of those four models' prove receipts were repointed to the fresh receipts (111 cells); census PASS.
- New stamp `iteration-61/correspondence-inputs.json` captured on this host. Bindings (native correspondence) were not
  rerun: the product files and binding scripts are unchanged; only the proof toolchain binary differs, which bears on
  proof receipts, and those were refreshed.
- Factual errors the builder reported in grade sources (not yet repaired): erasure.atomic working assumption 2
  (Eraser never takes the ledger head lock); query.compiled.deploy-discards (Gen.cls:214 deletes a class that fails to
  compile); stale coverage.md rows (erasure.scope "Proved"; ledger rows "not modelled"). Queued.
