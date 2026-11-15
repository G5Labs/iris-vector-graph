# Global PageRank cache admission through its node producer

As-built transcription at 3eaa79cf, **9 verified / 6 controls**. Canonical owner:
algorithms.cache.pagerank. Results/raw logs: `../../results/pagerank_admission/`.

`token` distinguishes failed census from successful count0/max0. SQL row count
and MAX(%ID) are inspected provider results. `add_node` derives changed count/max
from insertion with a fresh non-reused row ID. `key/call` derive matching node
census, damping, iteration and adjacency-token admission; hit returns actual
stored rows with zero loner reads, miss consumes fresh rows with one census.
Damping is an opaque parameter-identity token here, not score arithmetic.
Legacy list key sorting and SHA256 injectivity are not proved: `key(None,...)`
represents the fallback list dependency only, not all permutation equivalences.

The independent producer review added `edgeless`: raw loners contain a has-loop
bit. A self-loop-only node is removed, a true isolate remains; only the latter
forces the Owner on a cache miss. `native_candidate` means the native eligibility
probe may be attempted; proof/routing/availability still decides whether it runs. This producer/consumer distinction has both
neighbors and an inverted-bit control. Other controls omit node key, eagerly
read loners, ignore adjacency, admit Native with isolates, or treat failed token
as known-empty. Each fails its named theorem; controls/baseline are replayable.

Native Python binding: **16 journeys**, three real engine calls each, plus cold
isolate/loop and empty-census checks. Token success/failure, 0..3 added isolates
and changed/unchanged adjacency vary independently. Real engine token query,
engine/store, cache key hashing, shared-cache protocol, JSON decoder and score
reader execute. Server SQL/census, cache storage, PageRank rows and native hook
are fixtures. Scores are normalized fixture rows and are forwarded correctly;
this is NOT an ObjectScript numerical or 10000-cap observation. A constant-node-
key product mutation and changed rows are detected.

Trust: bundled pinned vstd only, no unchecked declarations or actors. Stable
reads, monotone non-reused row IDs, faithful shared-cache token/key lookup and
successful small payload storage are premises. No snapshot/concurrency proof;
failed computations, front cache, legacy-list sorting and score arithmetic remain
open. F-1003's 10000-row cap and F-1004/bug-plt-017's PPR bug remain distinct.
Implementation-verified 0.
