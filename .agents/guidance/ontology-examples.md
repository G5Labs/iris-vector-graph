# Ontology writing examples

Ontology must be human-readable, concise, minimal, consistent and deduplicated. These are writing examples, not product policies. Prefer one concise sentence per block. Bullets describe one commitment; children give a useful rule or decision its own identity. Neither requires a separate model for every property.

## Writing rules

- A block has at most three sentences outside its bullets, even across several paragraphs, and each bullet has at most three.
- A block has at most 10 bullets. Anything larger is worth a new concept, its definition and a collection of statements.
- Write for a typical reader, at about an 8th-grade reading level.
- Omit details a reasonable practitioner would infer from other statements. Keep confirmed or notable exceptions.
- Keep provenance, such as the issue, PR or bug behind a rule, in metadata. State a reason only when it is not obvious.
- Give each new level of a dotted ID its own block that defines its concept. The root page's overview defines the top-level name.
- Define a shared concept or abstraction when it makes many statements shorter or simpler.
- Keep each file under the platform's render size; split a large page into files aligned with its abstractions or sub-components, linked from a short parent page.

Write new and changed statements to these rules even where older ones do not yet follow them. The [checker](scripts/check_ontology.py) warns about long statements and bullets, more than ten bullets, issue references in statement prose, undefined ID levels and oversized files.

## Passwords — one block with bullets

<a id="example.passwords"></a>
[I · example.passwords]

Passwords must contain:

- At least 12 characters.
- An uppercase and a lowercase letter.
- A number and a special character.

## Layouts and Review — one block

<a id="example.layout-loading"></a>
[I · example.layout-loading]

A failed layout read must not erase the saved layout.

<a id="example.review-capacity"></a>
[I · example.review-capacity]

A reviewer can have at most ten active reviews, even when several reviews start at once.

## Retrying a request — parent and child

<a id="example.retry"></a>
[D · example.retry]

If a completed request’s reply is lost, another server can return the saved result when the request is retried.

<a id="example.retry.atomic-save"></a>
[D · example.retry.atomic-save]

Save the result and the changes in the same database transaction.

## Metadata

### example.passwords

- human-provided
- user-facing-behavior, security
- implementation-verified

### example.layout-loading

- agent
- user-facing-behavior
- manual-check-review

### example.review-capacity

- agent
- user-facing-behavior
- design-verified

State machines: [Review capacity](../TLA_verification/models/review-capacity/manifest.json)

### example.retry

- human-verified
- user-facing-behavior
- test-coverage
- Children: [Saving the result](#example.retry.atomic-save).

### example.retry.atomic-save

- agent
- architecture-decision
- design-verified
- Expands: [Retrying a request](#example.retry).

State machines: [Reply transaction](../TLA_verification/models/reply-transaction/manifest.json)

## Bad versus good prose

These illustrative comparisons show clearer wording and grouping; some bad wording is constructed. They explain the examples rather than add product requirements. The table explains the example format above.

| Bad | Good | Why |
|---|---|---|
| Commit replies with their changes so another node can replay a reply after a lost commit acknowledgement. | **Parent:** If a completed request’s reply is lost, another server can return the saved result when the request is retried.<br>**Child decision:** Save the result and the changes in the same database transaction. | The parent promises recovery; the child records a design choice. |
| Show each reviewer’s latest decision and authoritative time beside newer Waiting requests. Keep history. Unrequested types show Not requested; eligible reviewers aren’t pending requests. Distinguish failures and cancellations from rejection. A quorum leaves others’ pending requests open. | Show each reviewer’s latest decision and when they made it, alongside any newer unanswered requests.<br>• Keep earlier requests and decisions in history.<br>• Show “Not requested” until a request is sent. Eligible reviewers are not pending requests.<br>• Distinguish rejection, cancellation and technical failure.<br>• Receiving enough approvals does not close other pending requests. | Lead with the intent; group related rules as bullets. |
| Review-start admission must enforce the per-agent active-review cardinality constraint across concurrent invocations, preventing multiple independently admitted operations from collectively exceeding the configured maximum of ten. | A reviewer can have at most ten active reviews, even when several reviews start at once. | Keep the concurrency condition in plain English. |
| Password validation must enforce a minimum length threshold of twelve characters, with the measurement performed over character count rather than the byte length of the encoded representation. | Passwords must contain at least 12 characters. | State the requirement directly; characters already specify the unit. |
| Authorization for review initiation, note insertion and final decision submission is contingent upon the requesting actor matching the agent associated with the case’s current assignment. | Only the assigned reviewer may start the review, add notes or decide the case. | One actor and one authorization rule cover all three actions. |
| Vendor Receipt No is the one editable suggested receipt number, required, at most 20 characters and unique per vendor; deleting a draft does not release its stored number for reuse; a suggestion itself reserves nothing. | Every receipt needs a number unique to its vendor.<br>• The system suggests a number; the user can edit it.<br>• The number can contain at most 20 characters.<br>• Suggestions do not reserve numbers.<br>• Deleting a draft does not release its saved number. | One number rule, with its properties grouped underneath. |
| Once Create has returned an id/version, the editor retains that draft identity through Submit failure and retries the known draft rather than issuing another Create. | If submission fails after draft creation is confirmed, retry the same draft. | Keep the confirmation condition; omit command mechanics. |
| An unreadable saved layout is unknown rather than empty: disable layout saving until a successful late read can safely apply it, and never overwrite a user change or Reset that occurred while the read was pending. | A failed layout read must not erase the saved layout.<br>• Disable saving until the saved layout can be loaded and safely applied.<br>• A delayed response must not overwrite changes or a reset made while waiting. | State the protection first, then its two conditions. |
| Budget Sync Start Year must be an integer between 1000 and 9999. The browser imposes this bound, but the current API persists any integer and the value-object reader only defaults unparsable strings to 2025. | **Statement:** Budget Sync Start Year must be a whole number from 1000 to 9999.<br>**Metadata — linked issue:** The API accepts years outside this range.<br>**Metadata — supporting evidence:** The reader substitutes 2025 when a stored string cannot be parsed. | Keep the rule in the body; put findings and evidence in metadata. |
| After a correct phone number and password, the bank sends a six-digit code by SMS to the customer’s registered phone and the customer must enter it to finish signing in; the code is single use and expires five minutes after it is sent. | **Parent:** Customers sign in with their phone number, password and a code sent by SMS.<br>**Child — sending:** After a correct phone number and password, send a six-digit code to the customer’s registered phone.<br>**Child — accepting:** The code works once and expires five minutes after sending. | Sending and accepting codes are useful, separately named behaviors. |
| After bug #412 erased saved layouts, a failed layout read must not erase the saved layout. | **Statement:** A failed layout read must not erase the saved layout.<br>**Metadata — source:** Bug #412. | Keep provenance in metadata; the rule stands on its own. |
| Only the workspace owner may delete a workspace. Other members, administrators, viewers and signed-out users cannot delete it. | Only the workspace owner may delete a workspace. | “Only” already excludes everyone else. |
| `shop.cart.limit`: A cart holds at most 50 items, where a cart is the list of items a customer plans to buy. | **Parent `shop.cart`:** A cart lists the items a customer plans to buy.<br>**Child `shop.cart.limit`:** A cart holds at most 50 items. | Define each ID level once, then refine it. |
| While a queue still owns a turn, chain-end handover and the deactivated-approver skip before designee injection remove only document-wide System auto-acceptance. | When review reaches the end of the configured approval sequence but a queued reviewer still has a turn, do not record automatic approval of the whole document. | Replace compressed jargon with an understandable action. This is the main-statement excerpt: supporting bullets must retain the deactivated-approver case, genuine no-policy approval, policy-specific decisions and the unresolved timing question. Define necessary terms separately and link to automatic approval’s triggers. |
| Hydration owns one detail entry per grid line and is idempotent by line identity. | Loading a line's details must create one detail entry per grid line and give the same result when repeated for that line ID. | Explain the operation and the effect of repeating it instead of personifying a mechanism or relying on unexplained technical terms. |
| Save and Submit consists of two commands. Once Create returns an id/version, the editor must retain that draft identity through Submit failure and retry the known draft instead of creating another. | Save and Submit uses two commands; once Create returns an ID and version, a failed Submit must retry that same draft instead of creating another. | Put the recovery promise and its condition together. Keep the separate unresolved case where the Create response is lost; a confirmed draft and an uncertain creation outcome have different recovery guarantees. |
