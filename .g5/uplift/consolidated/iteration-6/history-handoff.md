# History paging package

Input seal `47236c829a48215db58c1677637b3fc41cc85310`, unchanged product3eaa79cf.
Edited only new model/receipts and history-prefixed iteration6 artifacts. No Git,
product, ontology, shared tool, imported tree or native runtime was mutated by
this builder. Source-first H1/H2 and the original384-case probe are retained in
iteration5's independent review; the new builder panel is not held-out evaluation.

## Result

The as-built producer derives filters, exclusive cursor, ordering and limit from
persisted revision fields; final page and RevisionInfo projection follow. Twenty
obligations pass and thirteen changed controls fail their named properties. The
source matcher now represents the native provider's ASCII case and trailing
space/TAB behavior, and source raw-text identity remains distinct from JSON decode.
Integer0 versus text"0" descending cursor behavior is represented and observed.
Zero/negative TOP and failed query/decode versus empty page are distinguished.

Binding executes **6080** real GraphLedger.history, fetch_history, _rev_from_row and
RevisionInfo.from_wire over SQLite with explicit TOP/collation adaptation. See
latest binding receipt for exact case count and all5 detections. Native TOP and
text-comparison evidence was run independently by root on its checked disposable
IRIS, not by this builder. The binding hashes its scripts and observations. Root
also observed the actual extra empty continuation page in both directions and
the distinct interior-JSON-spacing result, using public history and legitimately
committed native revisions; this is stronger than SQL fixture rows alone.

No new defect, simplification, owner decision or question is filed here. Case and
trailing-space matching are new source/provider challenges in this builder search,
not a repair to the product and not a new bug count. The API doc's word "exact"
for correlation_id should not be used to promise binary string comparison.

## Exact canonical recommendation (root owns integration)

Add child `ledger.readers.history` under `ledger.readers`, with a stable metadata
link to models/history_paging/history_paging.rs. Suggested body:

> History applies all requested filters before ordering and limiting a page. In
> oldest-first order the cursor excludes its sequence and everything older; in
> newest-first order it excludes its sequence and everything newer, while integer0
> starts at the newest revision.
>
> A nonempty page with exactly the requested number of revisions returns its last
> sequence as the next cursor, even if it is the final full page. A shorter or empty
> page returns no cursor, so a final full page needs one additional empty read.
>
> Time bounds include equality. A filter set to None is omitted; an empty string
> is still a supplied filter. Text filters use the database's comparison rules:
> this provider accepts ASCII case changes and trailing spaces/TABs, including in
> the stored JSON source text. Reading a source value decodes it separately.
>
> A zero limit returns an empty page. A negative limit is refused by IRIS, and a
> failed database read or required-field decode raises instead of becoming an empty
> page. An acquired cursor receives one close attempt. Each page reads the current
> rows; separate pages are not one fixed snapshot.

Detail either in the same body or supporting metadata: the raw descending-cursor
truthiness is tested before int conversion, so text"0" selects `seq<0` rather than
the initial page. Source serialization, general JSON/Unicode/SQLUPPER, other SQL
providers, migration index correctness and concurrent writers remain qualified
as NOTES states. Do not tag implementation-verified.

## Binding integration

NOTES contains four proposed specific-behavior role links: GraphLedger.history;
replay.fetch_history; replay._rev_from_row; RevisionInfo.from_wire. None was added
to shared crosswalk by this builder. The commit/genesis/redaction writers,
correlation-index setup and SQL provider are independently named residual roles;
do not count them as bound by this package. Full JSON reader behavior is observed
on twelve cases, not proved by the typed projection. Whole-method fidelity and
repository prevalence are unmeasured.

## Preserved attempts and residual queue

Kept initial12-proof version, generic-lemma failures (3/2/1), an ambiguous numeric
literal type error, expected-count corrections (17 and19 verified with zero errors)
and two control-anchor ERRORs where a text match was not unique. Later decisive
receipts supersede them; none is called a product defect or a successful control.
No oracle or supported input was silently deleted. The first384-case binary probe
had no case/space challenge; its scope is retained rather than being relabeled a
provider validation. Root's new native evidence caused the final comparison rule.

Remaining: full Unicode/provider collation contract; all source serialization and
JSON decoding; positive provider limits/failures beyond sampled boundaries;
stable multi-page snapshot policy under append/redaction; missing/unbuilt indexes;
general arbitrary Python input coercion; direct executable-body verification.
Another iteration can model an actual competing metadata writer or provider
comparison boundary if it changes a material prediction. Temporal restore-to-window
remains a separate consequential workflow and is being handled by root. This
package alone does not establish foundation convergence.
