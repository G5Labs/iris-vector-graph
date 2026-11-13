# Ontology, model and implementation review

Use when explicitly requested, or as a compact brief within an authorized uplift or
incremental review. Inherit its scope, permitted sources, repair permissions, assurance
level and review limits. This brief adds no extra review round or completion gate.

Read original accepted requirements and decisions, the relevant ontology including
children, actual models and configurations, implementation and existing evidence.
Independently derive expected behavior from accepted sources and inspect relevant
operations before reading claimed coverage or prior defenses. Keep unavailable sources
explicit; observed code behavior does not itself establish intended policy.

1. **Coverage:** What consequential source-supported behavior is missing or only partly
   represented? Check conditions and exceptions within linked features. A requirement
   omitted from ontology, models and code can only be recovered by looking beyond them.
2. **Meaning:** Could the model satisfy its assertions while violating the reviewed
   ontology? Inspect outcome-changing interpretations against parent statements and
   relevant children. Identify wrong behavior the checks must reject and legitimate
   behavior they must preserve.
3. **Implementation:** Could real code violate the commitment while modeled checks pass?
   Inspect relevant operations, competing writers, effects, failure boundaries and
   relied-on dependencies. Distinguish reviewed or tested correspondence from proof.

Use the [TLC model-checking mechanics](TLC/model-checking.md) or [Verus verification guidance](Verus/verification.md) for the selected foundation. Use [intent recovery](uplift-intent-recovery.md) for uplift. For PR scope and closure use [TLC re-verification](TLC/pr_incremental_TLA_reverification.md) or [Verus re-verification](Verus/incremental-reverification.md).
Record material discrepancies, sources, owning statements, affected models/code and
closure evidence in existing findings and coverage records. Resolve findings against
governing authority, repair within authorization and recheck affected results.

The same questions can inform an early review of draft ontology before substantial
modeling. Identify artifacts not yet available; early review does not establish their
fidelity or replace the existing final review. Report coverage and conclusions only at
the scope and assurance level supported by the evidence.
