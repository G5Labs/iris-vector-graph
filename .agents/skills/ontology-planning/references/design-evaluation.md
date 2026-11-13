# Evaluate the minimal sufficient design

Planning's minimal-design principles govern. Initial downlift examines all sixteen
dimensions across the selected target and extension boundaries, taking the time needed
to resolve consequential risks. Incremental work considers only dimensions that affect
its design; it does not require this whole reference, a scorecard or unrelated audits.

Required outcomes and constraints are mandatory. Allocate further effort by impact and
uncertainty; reuse applicable evidence. Scores are optional and cannot compensate for
an unmet requirement. If comparing scores, fix scope, criteria and weights first and
keep raw evidence, unknowns and scope changes visible. Independence describes confidence
in the assessment, not a product quality to average into it; additional reviewers are
not automatically required.

For proof-maintenance comparisons, examine ownership, reuse of guarantees,
state-consistency obligations, boundary premises, and failure/progress reasoning.
Use a representative increment to compare which decisions and evidence must change.
Treat anticipated burden as an estimate; smaller proof or state counts alone do not
establish a better design. Numeric scoring remains optional under the rules above.

| Dimension | Decision-relevant evidence |
|---|---|
| 1. Intent fidelity | Retained outcomes and exceptions reach contracts and checks/tests; narrowing has human authority. |
| 2. Verification coverage | Actual checked obligations and gaps; sensitive negative controls and mechanism-removal comparisons. |
| 3. Failure-mode completeness | Material failure behavior, recovery and tests, including affected unchanged consumers. |
| 4. Performance and scalability | Required operating envelope, query cost, contention and growth; distinguish configured limits from measured capacity. |
| 5. Availability and recovery | Acceptable loss/recovery time, failure dependencies and restore behavior. |
| 6. Security | Entry-point threats, authorization, abuse and trusted boundaries. |
| 7. Privacy and data lifecycle | Sensitive copies, disclosure, retention, deletion and portability requirements. |
| 8. Observability and operability | Detecting, diagnosing and recovering consequential failures. |
| 9. Resource cost | Required services, bounded work, storage growth and cost at intended scale. |
| 10. Evolvability | Representative extensions through public operations, versioning and triggers for core design changes. |
| 11. Migration and compatibility | In-scope data/API compatibility, coexistence, cutover and rollback. |
| 12. Delivery feasibility | Consequential unknowns and effort; targeted prototypes or proof spikes where needed. |
| 13. Dependency and supply-chain risk | Maintenance, compatibility, licensing and exposure of necessary dependencies. |
| 14. API usability | Coherent operations, outcomes, pagination, retries/idempotency and errors. |
| 15. Specification quality | Sufficient, concise, consistent contracts with clear ownership and assumptions. |
| 16. Review independence | Self-review versus independent assessment, fixed comparison criteria and material scorer disagreement. |

Use these as design questions, not mandatory artifacts or universal metrics. Preserve
modularity, abstraction and encapsulation while challenging unnecessary state and
protocols. Narrowed features or operating bounds are explicit tradeoffs; a changed scale
requirement can justify mechanisms the earlier envelope did not need. Save consequential
choices, reasons and remaining uncertainty in the existing design; no separate report
or prescribed implementation process is required.
