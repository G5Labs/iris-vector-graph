# proofs-stmt: partial state (lane stopped by the coordinator, steer 14)

Crate `ivg-proofs-stmt` (path deps `../proofs-env2`, `../proofs`, both unchanged). Every result is about the
**hand-translated** program in the contract model (proofs-env2's Verus spec of IRIS 2026.1). Nothing transfers to the
product: the translation is a trusted premise (ST-TR) and its mechanical check was **not run**.

## Proved (development runs, not the gate runner, no independent recheck)

Registered: `proofs-stmt-dev-baseline` (110 verified, 0 errors, `--no-cheating`, trust scan of src/*.rs empty;
sources sha256 `01432ffc…13c9` over lay/prog/oplem/runs/stmts/eg/cx/lib.rs + Cargo.toml).

Handler A1, **EraseGraph** (Eraser.cls:47-262 plus RemoveGraph Adjacency.cls:431-445, TemporalIndex.cls:370-375,
InvalidateDerived 1040-1052, EraseLedgerFor 1117-1144), program `prog.rs` (`eg_prog_m`), every element tagged with
its file:line:
- `stmts.rs`: statement lemmas (3.4) for the scoped DELETE, derived Kill/$Increment/Set, DropNKG, EraseLedgerFor.
- `eg.rs::theorem_erase_graph`: from any state meeting `eg_pre` (solo run), the program performs core Store
  `EraseRows{tg(g)}` after its row DELETEs and `EraseIndex{tg(g)}` after EraseLedgerFor, before TCOMMIT; as built and
  reviewed. Abstraction `lay.rs::alpha` to `proofs/src/store.rs::StoreS`.
- `eg.rs::theorem_eg_disc`: the reviewed program (head lock R11-7) meets proofs-env2 `disc` on its solo trace.
- Controls, each rejected only at its LOCATE lines, counterexample in `cx.rs`:
  `proofs-stmt-dev-ctl-f1201-erase-no-head-lock` (eg.rs:805; `cx_f1201_interleaving`: commit lands between DELETE
  and EraseLedgerFor, committed edge live without statement entry, `!disc`), `-mut-drop-edges-delete` (eg.rs:261),
  `-mut-drop-ledger-cleanup` (eg.rs:276), `-mut-ledger-first` (eg.rs:269, 276), `-mut-cleanup-after-commit`
  (eg.rs:276, 283, 808).

## Not done

- `src/exec.rs` written, **never verified** (not in lib.rs); no harness, no journal replay: translation check and
  coverage = none.
- EraseNodeIds (EraseIdSet/EraseEdgeRow): no program, no proof. Module 11 ledger commit (B): nothing.
- No runner (tools/run_proofs.py), PROOFS.md, RESULTS.json, MATRIX-INPUT.json, recheck, abort/rollback theorem,
  interleaved theorem (disc only on the solo trace; composition with proofs-env2 `theorem_inv_h` not done).

## Exact open obligations (EraseGraph)

ST-TR translation unchecked; ST-SCAN (WHERE-DELETE = keyed DELETEs in cell order); ST-WALK ($Order walk = defined
stmt cells); ST-LIST (`dec`, X2-LIST: Eraser.cls:1129, 1139); routed tables 82-113, 167-178, 282-299 and FHIR 183,
1151-1180 (X-DDL); rdf_edges functional-index effect on ^KG (X-FX, 217); 215 NKG reads (free `nkg`); FK -124; lock
timeouts; catch path 259-261 unproved.

## Resume

    source experiment/playbook-completion/environment.sh
    bash $RUN_DIR/proofs-stmt/dev/devrun.sh <tag> [feature]     # dev Verus run under locks.sh heavy
    # next: add `pub mod exec;` to src/lib.rs, verify, then write harness/ and tools/run_proofs.py
