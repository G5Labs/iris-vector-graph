# iris-vector-graph uplift source index

This index records candidate product promises at [`3eaa79cf`](https://github.com/intersystems-community/iris-vector-graph/tree/3eaa79cf77d3e0a879b2cced634cf2729d81499e). The parent is the v4.7.0 release commit, `fabf4fae`. The first section maps the whole product. The worked example follows one operator request from its rationale to executable checks. Treat each seed as a claim to challenge at this pin.

## How large is the target?

The pin has 2,671 reachable commits from 2025-09-24 to 2026-11-12, 61 reachable tags and 16 architecture decision records (ADRs). All commits have the same Git author name. The change history often preserves design conversations or test findings, but a single author field cannot establish independent agreement. The [release](https://github.com/intersystems-community/iris-vector-graph/releases/tag/v4.7.0) and [published Python package](https://pypi.org/project/iris-vector-graph/4.7.0/) provide dated public cross-checks.

| Contents at the pin | Text files | Physical lines |
|---|---:|---:|
| Product Python | 161 | 101,109 |
| Product ObjectScript | 74 | 27,593 |
| Product SQL | 14 | 1,546 |
| Test code and harness | 1,897 | 357,411 |
| Test data | 43 | 331,488 |
| Documentation and specs | 272 | 70,977 |
| Configuration, CI and lockfile | 19 | 5,985 |
| Other, including tooling, demos and benchmarks outside the product roots | 437 | 62,073 |

Counts include comments and blank lines. The denominator is regular tracked text at the product pin, excluding symlinks, submodule contents and files containing a NUL byte. Classification in order: files under `tests/` are test data if in a `fixtures` directory or ending in `.json/.csv/.ttl/.xml/.ndjson`, otherwise test/harness. Product is Python, ObjectScript and SQL under `iris_vector_graph/`, `iris_src/`, `api/`, `src/` and `sql/`. Docs include all of `docs/`, `specs/` and root Markdown. Config includes `.github/`, `config/`, TOML, YAML, INI, CFG, root tool/environment settings and `uv.lock`. Other is the remainder.

The strongest design evidence is at boundaries where the team named an owner, documented a rejected alternative, and wrote a live regression. The ledger is a good example. The harder parts to infer are cross-module behavior and old feature promises. Transactions span Python, SQL and ObjectScript, some specs still say “draft” after a release, and an ADR may describe an alternative branch. Read later changes before treating an older design as shipped. This makes IVG a useful comparison target for intent recovery and implementation binding. A whole-product proof would cover substantially more than the focused trial.

## Where to look for intent

| Question | Start here | How to interpret it |
|---|---|---|
| What language does the product use for its own concepts? | [Product glossary](../../CONTEXT.md), [user guide](../../docs/USER_GUIDE.md), [API reference](../../docs/API_REFERENCE.md), [admin guide](../../docs/ADMIN_GUIDE.md) | Start with graph, statement, revision, graph key and tenant. Distinguish public guarantees from the deployment recipe used to demonstrate them. |
| Who needed the behavior, and why? | [OpsReview integration brief](../../docs/dev/notes/for-opsreview/IVG-OPSREVIEW-BRIEF.md), [spec 256 user stories and recorded decisions](../../specs/256-ledger-tenant-redaction/spec.md), [ADRs](../../docs/adr) | The brief distinguishes the consuming application's event store from its rebuildable IVG graph. Spec 256 preserves the consumer request secondhand. The ADR explains the accepted compromise. |
| Which interface and persistence layer own each decision? | [Python engine](../../iris_vector_graph/engine.py), [engine modules](../../iris_vector_graph/_engine), [ledger wire/API contracts](../../specs/213-graph-revision-ledger/contracts), [IRIS classes](../../iris_src/src/Graph/KG), [schema](../../iris_vector_graph/schema.py), [HTTP API](../../api) | Follow the public call to the writer and reader. Python is a façade over domain modules. ObjectScript owns several transactions spanning SQL and IRIS globals. Source comments explain choices at those boundaries. |
| Which failures tell us what mattered? | [Known issues](../../docs/KNOWN_ISSUES.md), [changelog](../../CHANGELOG.md), [test policy](../../docs/dev/TESTING_POLICY.md), [contract tests](../../tests/contract), [live integration tests](../../tests/integration) | Pair the original failure with a regression and check the release where behavior changed. Source-text assertions and database-backed assertions support different claims. |
| Which promises come from outside IVG? | [Dependencies and extras](../../pyproject.toml), [locked packages](../../uv.lock), [IRIS runtime](../../docker-compose.yml), [Cypher conformance record](../../docs/dev/TCK.md), [upstream openCypher resources](https://opencypher.org/resources/) | The core depends on the IRIS client and embedded wrapper, Pydantic, NumPy, requests and tzdata. RDF, graph analysis and API extras add their own premises. The TCK constrains query semantics. Its eligible cases, driver and IRIS edition matter when citing a historical run. |

## Seed contracts to investigate

| Subject | Candidate promise and evidence |
|---|---|
| Graph scope | Both adjacency and ledger keys derive from the public graph ID. They encode the default graph differently. A scoped operation must use the correct derivation. [ADR 0003](../../docs/adr/0003-two-graph-key-derivations.md) · [GraphKey](../../iris_src/src/Graph/KG/GraphKey.cls) |
| Edge identity | A deployment opts into parallel edges. With the mode off, existing single-edge storage and identity are meant to remain compatible. The spec separately tracks ledger/restore work, a reason to check each surface at this pin. [Spec 234](../../specs/234-multigraph-parallel-edges/spec.md) · [parallel-edge E2E](../../tests/e2e/test_460_one_hop_parallel_edges_e2e.py) |
| Adjacency and degree | One writer owns structural adjacency. A cached degree may be served only while its generation is current. Follow how mutation or rollback affects what the next reader sees. [ADR 0011](../../docs/adr/0011-the-adjacency-index-has-one-writer-module.md) · [ADR 0012](../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md) · [live degree tests](../../tests/e2e/test_degree_cache_live.py) |
| Temporal edges | A temporal assertion creates a structural edge by default. A graph can opt a predicate out. Time-window reads and an explicitly asserted structural edge have separate obligations. [ADR 0015](../../docs/adr/0015-temporal-structural-rows-opt-out.md) · [live opt-out tests](../../tests/e2e/test_temporal_structural_optout_e2e.py) |
| Embeddings | The embedding store's registry owns the declared model identity and width. Compatibility can be checked on write even when the ledger is disabled. [ADR 0006](../../docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md) · [registry integration tests](../../tests/integration/test_embedding_registry_e2e.py) |
| Text search | BM25 schema 2 updates token records and frequencies together under a write lock. Writes against the old schema require an upgrade. Query-time scoring uses current document frequencies. [ADR 0007](../../docs/adr/0007-bm25-df-and-doc-record-schema-2.md) · [BM25Index](../../iris_src/src/Graph/KG/BM25Index.cls) |
| Cypher execution | The compiled plan and interpreter owe the caller the same result. A stale plan must never run. The interpreter can answer when compilation is unavailable. [ADR 0014](../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md) · [plan generator](../../iris_src/src/Graph/KG/Cypher/Gen.cls) · [TCK harness](../../tests/tck) |
| Live erasure | Successful erasure removes content and live ledger references together. Failure rolls back. Historical operations may span graphs, so their ordinals survive. A returned zero means nothing matched. [ADR 0004](../../docs/adr/0004-erasure-removes-content-not-history.md) · [Eraser](../../iris_src/src/Graph/KG/Eraser.cls) · [failure cases](../../tests/integration/test_eraser_failures.py) |
| Redaction and isolation | Redaction refuses a live target. For an erased target it replaces matching records in place with tombstones. Other tenants' records in the same revision retain their bytes, while four free-text fields shared by that revision are cleared. Default-graph node targeting uses a separator-delimited prefix. [ADR 0013](../../docs/adr/0013-redaction-removes-content-from-history.md) · [LedgerRedact](../../iris_src/src/Graph/KG/LedgerRedact.cls) · [revision update guard](../../iris_src/src/Graph/KG/LedgerRevision.cls) |
| Retries and interruption | A previously used, redacted idempotency key cannot re-create content. During a batched redaction, the marker governs readers, targeted commits and competing redactions. The same target can resume. [Ledger writer](../../iris_src/src/Graph/KG/Ledger.cls) · [Python client](../../iris_vector_graph/ledger/client.py) · [pause and retry cases](../../tests/integration/test_256_ledger_redaction_e2e.py) |
| What verification means | Readers show tombstoned ordinals. Replay omits their content. In the two-tenant fixture, replay diverges after erasure alone and equals the live store after redaction. A tombstone digest can be recomputed from the original record. Earlier exports, IRIS journals and backups remain outside the guarantee. [ADR 0013](../../docs/adr/0013-redaction-removes-content-from-history.md) · [replay](../../iris_vector_graph/ledger/replay.py) · [before/after oracle](../../tests/integration/test_256_ledger_redaction_e2e.py) |

## How to trace the worked example

Read the commits in order with `git show <id>`. The names below resolve in the transferred history.

| Commit | What it adds |
|---|---|
| `a140ed78` | The consumer asks for targeted erasure that can still be audited. The draft contains assumptions awaiting tests. |
| `42907b21` | The maintainer records decisions on the audit record, shared revision metadata and batching. |
| `2b8ea46d` | Plan, tasks and ADR 0013 connect these decisions to changes in the writer and readers. |
| `e4b5eef5` | Implementation, Python API and tests land together. Compare each observable with the pre-change parent. |
| `9afe0822` | Version 4.3.0 publishes usage and release notes. Later defects and fixes still matter at the experiment pin. |

For later changes use `git log -p e4b5eef5..3eaa79cf -- iris_src/src/Graph/KG/LedgerRedact.cls iris_vector_graph/ledger`. For the introduction of the retry rule use `git log -S'idemRedacted' -- iris_src/src/Graph/KG`.

The [native two-tenant fixture](../../tests/integration/test_256_ledger_redaction_e2e.py) first shows it can find the target. It then checks mixed revisions, untouched bytes, a neighboring prefix, retry, interruption, and replay. The [unit suite](../../tests/unit/test_256_ledger_redaction.py) also inspects Python behavior and ObjectScript source shape. Open questions for the uplift include which guarantees need an engine transaction or lock, what holds between committed batches, and which parts of replay equality the test observes. A candidate who models one graph or one revision per tenant cannot exercise the shared-revision decision.
