# Agent Prompt Authoring Guide

`agent_prompt` defines what the single `g5-agent-approval-review` skill should evaluate. It is review-policy data, not a second system prompt, a custom skill, or a way to grant tools, network access, mounts, or other capabilities.

The API accepts at most 20,000 Unicode characters after trimming; the database column is `TEXT`. Prefer a short prompt—usually under 2,000 characters—and link to an accessible, versioned policy rather than pasting a large policy. Never place secrets or credentials in the prompt.

## Minimal form

A short natural-language prompt is sufficient when the intent is clear:

```text
UX Review. Posture: customer_ready.
Check the changed user flow against our accessibility guidelines, including keyboard use, focus order, labels, error recovery, and contrast. Treat guideline violations as required failures. Report unrelated visual polish as advisory.
```

The skill also accepts existing free-form prompts without headings.

## Recommended form

Use only the fields that reduce ambiguity:

```text
Review name: <human-readable name>
Domains: <UX | Functional | Architectural | Security | Technical; one or more>
Posture: <prototype | demo | internal_test | customer_ready | organization-defined>
Focus: <the behavior, change, or question to evaluate>

Required:
- <observable pass/fail criterion>

Advisory:
- <important consideration that does not independently block approval>

Waived:
- <normally applicable criterion intentionally excluded, with reason>

Governing policies:
- <accessible document and version; say whether mandatory>

Evidence:
- <tests, scenarios, artifacts, or inspection expected>

Nonclaims:
- <certifications or broader conclusions this review must not imply>
```

Omit `Waived` rather than inventing waivers. The skill separately determines when a baseline dimension is genuinely not applicable.

## Built-in domains

- `UX`: flows, clarity, states, recovery, consistency, readability, accessibility, and responsive behavior.
- `Functional`: requirements, outcomes, boundaries, state transitions, errors, and regression risk.
- `Architectural`: boundaries, authority, contracts, trust, coupling, evolvability, and failure containment.
- `Security`: authentication, authorization, tenant isolation, trust boundaries, secrets and credentials, sensitive-data and privacy controls, attack surface and abuse resistance, dependency and supply-chain exposure, security observability, and fail-closed behavior.
- `Technical`: correctness, validation, reliability, maintainability, testing, and operability.

Multiple domains are allowed. The result is still one approval decision.

## Built-in postures

- `prototype`: prove the scoped concept and core path; explicitly state which hardening or verification is advisory or waived.
- `demo`: make the intended demonstration path coherent and reliable, with known limitations visible.
- `internal_test`: support safe, diagnosable exercise by the intended internal audience.
- `customer_ready`: require production-grade quality for all applicable dimensions.

If the organization uses another label, define it in the prompt or map it to a built-in posture:

```text
Posture: pilot
Posture definition: Treat as customer_ready for authorization, privacy, and data integrity; treat scale testing and 24x7 operational readiness as advisory for this review.
```

An undefined label adds no reliable grading rule.

## Examples

### Functional review

```text
Review name: Functional Review
Domains: Functional
Posture: internal_test
Focus: Verify that an authorized user can create, retry, cancel, and inspect an approval review without duplicate terminal decisions.
Required:
- Each stated state transition matches the accepted contract.
- Invalid or cross-tenant requests create no job or status.
- Retry and lost-ack paths converge on one decision.
Evidence:
- Relevant service, database, and API tests or equivalent executable proof.
Nonclaims:
- This is not a full UX or production-operations review.
```

### UX review

```text
Review name: UX Review
Domains: UX
Posture: customer_ready
Focus: Evaluate the changed approval-review experience against the accessible interaction guidelines.
Required:
- All actions are keyboard operable with visible, logical focus.
- Labels, instructions, loading, empty, error, and completion states are understandable.
- Error recovery preserves user input where safe.
Governing policies:
- Product Accessibility Standard v3 (mandatory; available in Project Docs).
Advisory:
- Minor visual polish that does not impair comprehension or access.
```

### Security review

```text
Review name: Security Review
Domains: Security
Posture: customer_ready
Focus: Evaluate authentication, authorization, tenant isolation, secret handling, sensitive-data exposure, abuse resistance, and fail-closed behavior for the changed scope.
Required:
- Every privileged action enforces the intended authorization and tenant boundary.
- Secrets and sensitive data are neither persisted nor emitted outside approved boundaries.
- Untrusted input and dependency boundaries fail closed with bounded, auditable errors.
Evidence:
- Relevant threat-boundary inspection plus authorization, cross-tenant, secret-redaction, and failure-path tests.
Nonclaims:
- This is a scoped engineering security review, not a penetration test or compliance certification.
```

### Architectural, security, and technical review

```text
Review name: Approval Review Architecture
Domains: Architectural, Security, Technical
Posture: customer_ready
Focus: Evaluate exact-cut authority, tenant isolation, replay safety, artifact confinement, and terminal status ordering.
Required:
- Git and PostgreSQL authority boundaries match the governing ontology.
- Authorization and tenant boundaries fail closed.
- A terminal job cannot exist without exactly one replay-safe status.
- Tests exercise success, failure, cancellation, and worker-loss paths.
```

### Novel topic: GDPR engineering-policy review

```text
Review name: GDPR Engineering Policy Review
Posture: customer_ready
Focus: Evaluate the changed data flow against the organization's GDPR engineering policy.
Governing policies:
- Privacy Engineering Standard v5.2, GDPR section (mandatory; available in Project Docs).
Required:
- Identify the personal-data fields, purposes, stores, processors, retention behavior, deletion path, and access controls affected by the change.
- No personal data is logged or exposed outside the policy's approved boundaries.
- The implementation supplies the policy-required deletion and data-subject-request behavior for the affected data.
Evidence:
- Data-flow inspection and relevant authorization, retention, deletion, and logging tests.
Nonclaims:
- This is an engineering-policy review, not legal advice or regulatory certification.
```

A novel review does not require a novel skill. It requires criteria concrete enough to judge, or an accessible governing policy concrete enough to supply them. If neither is available, the reviewer cannot produce a trustworthy decision.

## Writing criteria well

- State observable pass/fail outcomes, not broad aspirations such as “ensure quality.”
- Say what is required versus advisory.
- Name the reviewed scope and important exclusions.
- Identify expected evidence when absence of evidence must block approval.
- Version governing policies and make them available inside the review environment.
- State nonclaims for narrow, regulatory, security, or accessibility reviews to prevent overstatement.
