# Restartable work queue

Ordered by value. Status: `todo`, `doing`, `done` (with evidence id), `open` (stopped with a reason), `blocked`
(exact dependency). A successor resumes from the first non-done row of each lane. Lanes own disjoint paths
(see `CONVENTIONS.md`); the orchestrator commits.

| # | Lane | Item | Status |
|---|---|---|---|
| Q1 | orchestrator | Scaffolding: conventions, registry, locks, per-lane namespaces, journal oracle | done (c01a7ccd) |
| Q2 | orchestrator | IRIS environment contract: executable permitted-outcome model of the IRIS subset IVG uses; native differential harness on AUDITENV; sharpness cases; model mutants killed | doing |
| Q3 | orchestrator | Core erase/redact/replay models: three targeting predicates, graph-blind provenance, default/named graphs and overlapping ids, preexisting data, statement/tuple maps and cleanup, post-commit replay, mixed revisions and unattributed qualifiers, per-target counters, marker ownership/absence, concurrent erase/start, abort/recovery; as-built vs reviewed; controls | todo |
| Q4 | orchestrator | Participant contracts and `Protocol2` composition (eraser, ledger, redactor, readers) in Verus; safety + progress under named fairness; progress-only mutant | todo |
| Q5 | orchestrator | Trace conformance: product operations in AUDITCORE captured from the IRIS journal (independent oracle) and replayed through the L2 machine; lock observations; unchecked lines listed | todo |
| Q6 | orchestrator | §3.4–3.6 mapping: tables/globals/statements/update order/ownership/handlers/status/lock plans for modules 11–14; frame/key/order/capacity conditions; proof gate status | todo |
| Q7 | orchestrator | Obligation matrix (`matrix/`): gates × modules × entry points × readers/writers × properties × evidence; reconciled inventories | todo |
| Q8 | ontology | Literal §3.1 rule: strengthened checker, controls, repaired ontology copy | doing |
| Q9 | intent-a / intent-b | Independent intent recovery for 61 HD questions, discriminating probes | doing |
| Q10 | breadth-a / -b / -c | Modules 00–11, 15–18: entry points, footprints (journal-validated), small models + controls, findings audit, gate status | doing |
| Q11 | validation | Existing suites on the unchanged pin, triage, SC-002/003 and baselines, multi-process, editions | doing |
| Q12 | orchestrator | Findings audit for modules 12–14 (F-1201, F-1301..1306, F-1401, F-1402) | todo |
| Q13 | review | Independent intent review (§3.8): omitted writers, over-narrow domains, assumed fairness, model-to-code relation | todo |
| Q14 | orchestrator | Single clean entry point `verify.sh` against a candidate commit; trust inventory; phase verdict; STATUS | todo |
