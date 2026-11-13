# Follow-up evidence for the decision ledger

These checks ran on 13 November 2026 in the follow-up worktree, with IVG product at `3eaa79cf`, submission at `9c3719c1`, and the dedicated `ivg-playbook-20261113-iris` Community 2026.1 container. The prior submission's evidence is in its own run directory. These historical pre-repair logs are under `~/runs/iris-vector-graph-playbook-uplift-20261113/completion/preparation`. The current environment points to a separate clean audit run.

| Log | What ran | Result | SHA-256 |
| --- | --- | --- | --- |
| `selected-unit.log` | Entire test files for graph-scoped Python reads, RRF scope, iFind/fusion SQL and the ledger guard | 43 passed | `d13d6dffe48fc3bf0e4106ce8115a34f84f44e5593456c4a5c323bd4e9449bad` |
| `selected-live.log` | Four original redaction tests using the identity-checked Community fixture | 4 passed, 21 deselected | `03ee2307e590519f299b6dd4e1712884b0fe2e9fdd7a0e0d1963bbda4cbf78ed` |
| `row-lock.log` | New observation of P-1201 using two independent IRIS connections and a unique scratch SQL table, removed on exit | Uncontended delete about 13 ms. In two trials the concurrent same-row delete was pending after 0.5 s with the update transaction open. Each affected one row after that transaction rolled back. Final row count zero. | `c183454db71a1d3183811f4474f1c8186b944220848d2c7f583d3d449531d414` |

The row-lock probe samples one table shape, server build and synchronization window. The client signals just before issuing the statement, so the measurement is a client-side timing observation. It does not inspect the server lock queue or reproduce the IVG erasure race. Extend it with independent controls and engine-side traces before applying a universal locking claim.

Reproduce in the dedicated experiment environment from the checkout root. Use a fresh output location for reruns.

```bash
source experiment/playbook-completion/environment.sh
python -m pytest -o addopts= -p no:cacheprovider -q tests/unit/test_230_get_nodes_graph_scope.py tests/unit/test_230_rrf_fuse_scope.py tests/unit/test_ifind_and_fusion_sql.py tests/unit/test_ledger_guard.py
python "$RUN_DIR/run-community-redaction.py" -p no:cacheprovider -k 'spanning_revision_keeps or same_redaction_again or prefix_that_already_ends or receipt_counts'
PYTHONPATH="$WORK_DIR" python experiment/playbook-completion/observe_row_lock.py
```

On the VM, `gh api user` returned `ziniuwu-g5`. The GitHub API confirmed read access to `G5Labs/actors`, `G5Labs/bank-of-ziniu` and `G5Labs/omnisaas`. After configuring the Git credential helper, an authenticated HTTPS `git ls-remote --heads` on actors returned only `main` at `c03f9fa9be961610f2b274ffbb6a2c88d7d4d877`. GitHub returned 404 for `r8-models`. The uploaded PGspec proof/lemma source and the exact outstanding reference versions are recorded in [reference-upload.md](reference-upload.md).

The VM also has a bare mirror of the public IVG repository at `$IVG_REFERENCES/ivg-upstream.git`. Its 52 branches are available locally for blame, log and cross-branch comparisons. The fetched upstream main is the experiment's product pin. The branch/tag manifest at `$IVG_REFERENCES/ivg-upstream-refs.txt` has SHA-256 `a51c04385981871da9149dd14750aad4b19f349d4ac30acacb28c4317e993b49`.
