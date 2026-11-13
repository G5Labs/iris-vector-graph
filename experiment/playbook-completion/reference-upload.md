# References staged after the IVG run

VM `g5-verus-c3-20261020`, project `g5-dev-1ccc`, zone `us-central1-a`. The following directory is a sibling of the IVG checkout. The original submission is still `9c3719c14891b92d15c26898959339e83ede1b8e`.

```text
~/experiments/iris-vector-graph-playbook-uplift-20261113/post-run-references/
```

| Location under that directory | Provenance and contents |
| --- | --- |
| `omnisaas/` | All 6,751 tracked files of omniSaaS at `76113f84e1e10f0664c76b8108c0a9ad45090133`. Includes the playbook, design, storage definitions and mappings, generators, CI, original recorded results, 50 L2 crates and seven model-checking crates. |
| `omnisaas/design/model/` | All 283 canonical spec shards. The VM ran `python3 design/model_io.py check` and reported 58 top-level keys, all valid. The full model can be assembled with `python3 design/model_io.py assemble` from a working copy. |
| `omnisaas/verification/r2r-l2/src/` and `omnisaas/design/storage/r2r/` | Worked SQL-to-model example. Read `stmt.rs` and `sql_gen.rs` with `MAPPING.md`, `schema.sql`, `queries.sql`, `sql_gen_stmt.rs` and `lemma-debt.txt`. The statement lemmas relate successful PGspec evaluation to a local model, with explicit conditions. |
| `lemma-bank/` | 119 tracked files at bank-of-ziniu `f1d1ca591b0c3f526edc64ea301cb6c04f0402a2`, the proof/lemma pin in omniSaaS CI. Includes PGspec evaluator, permitted outcomes, transaction model, statement lemmas, SQL generator and validation sources, plus actors, explorer, vecops, builtin macros, workspace manifests and `SQL_CLOSURE.md`. |
| `example-workspace/verification/` | Separate working copy with local vendor dependencies in the layout expected by the omniSaaS L2 manifests. Offline Cargo metadata read 52 workspace packages and resolved both local dependencies of `r2r-l2` (`actors` and `pgspec`). |
| `example-workspace/pgspec-smoke.log` | The VM built and ran the lemma-pin PGspec generator on its own example schema and queries. It generated four statements. Output SHA-256 is `afecb64f844f9c73133e4a2a495676165126d583c6f4ff49cb7dc8081ceb1bb1`. This exercises the reference tool on PostgreSQL inputs. No IVG proof was rerun on these inputs. |
| `incoming/` | Source archives, `SHA256SUMS` and `git-blobs.json`. Both archive hashes were checked on the VM. Every extracted file was independently matched to its Git blob, including symlink and executable mode checks. |

The omniSaaS archive SHA-256 is `8967d9dc3ecf970f33a5a89fcbd50fcf68de275b9a7cf9f3577bfc900fd3a062`. The lemma-bank archive SHA-256 is `d94b61c3e1494c159660155ffba53cd3f8e4ed40429243733d521c07e852e04a`. The staged omniSaaS playbook matches the submitted IVG playbook byte for byte. The Git trees for omniSaaS verification and design/model are `1370a522417ffb21a229490e512d95dcb8f005ce` and `1c3dfae384ddc6158532ec696d356bffe27893d2`.

## Two references still unavailable

- **The omniSaaS SQL-subset checker.** CI uses bank revision `3177c2f6`, source key `36153bf97cdc2e0a` and the digest in `omnisaas/ci/spec-pin.txt`. The exact registry manifest returned HTTP 403 for `artifactregistry.repositories.downloadArtifacts`. A retained regional Cloud Build at the same source revision was visible, but its generation-pinned source object returned HTTP 403 for `storage.objects.get`. The VM had no active registry credential. Access to the pinned image, or a source bundle including its pg-verify dependencies, would supply this checker. The available lemma-pin generator was tested separately.
- **The r8 collection named in §1a of the playbook.** The accessible `G5Labs/actors` repository advertises only `main` at `c03f9fa`. Its `r8-models` branch returned 404, and the named bank commits `1ecc0035` and `a8e5d2bf` did not resolve through the accessible bank repository. No provenance-matching r8 or full pg-verify tree was located. An authorized archive or reachable immutable revision with its `SOURCE.json` would settle this. The older lemma-pin PGspec has its own documented interface and coverage.

The original IVG experiment used the separately staged actors checkout at `c03f9fa`. The additional models, libraries and working example above became available after the submitted run. An IRIS-specific contract and its validation would still be needed to transfer database-level claims to IVG.
