# System semantics of IVG, system-wide (playbook 3.3a)

Product pin `3eaa79cf` (tree `b098a6f4`), unchanged. Semantics lane, steer 7 (queue item Q17b). Observation only: the
product is not changed; every result below about a model is a statement about that model, never about the product.
The original submission's semantics covered the erase, redact and replay slice only
(`experiment/playbook-uplift/semantics/SEMANTICS.md`); this lane does steps 1-3 of 3.3a for all 19 modules, the
requirement trace of the 3.3a gate, the module-00 model check (3.3 for the system axioms) and the model of F-C0605. Step 5
(write-set obligations, 3.3a-writesets) belongs to the writesets lane and is not discharged here; step 4 (the domain
contract, replay equals the store) is the existing closed 3.3a-domain-contract cell, used here as clause DC-REPLAY.

## What is here

| File | Content |
|---|---|
| `AXIOMS.md`, `axioms.json` | 14 universal axioms (SYS-I1..I10 repaired and extended), 10 named exceptions, the contract clauses a requirement may trace to |
| `MECHANISMS.md`, `mechanisms.json` | 13 shared mechanisms: state, operations, effect kinds, events, L1 laws, generic controls, the objects using each (canonical or hand-rolled), departures with their findings, model checks |
| `LIFECYCLES.md`, `lifecycles.json` | 8 canonical lifecycles; naming collisions in the ontology and how the mapping resolves them |
| `objects.json` | the 62 objects (every ontology `Entity` line, derived mechanically), each with lifecycle, state and command map, mechanisms, axioms, hand-rolled variants, findings |
| `trace.json` | 2,600 requirements traced (or listed open) |
| `src/` | hand-written sources: `axioms_src.json`, `mechanisms_src.json`, `objects_map.json`, `finding_classes.json` (every finding classed by axiom), `trace_rules.json`, `trace_explicit.json` |
| `data/trace_sample_review.json` | hand review of the rule-based trace classifier (precision) |
| `tools/build_semantics.py` | builds `axioms.json`, `mechanisms.json`, `objects.json` from `src/` and the model results (`--check` for staleness) |
| `tools/trace_requirements.py` | builds `trace.json` (`--check`) |
| `tools/check_semantics.py` | the gate checker, with `--self-test` |
| `../models/semantics/` | the explorer crate: one generic machine per mechanism, the module-00 composition, `RESULTS.json` |
| `../findings/audit/zz-semantics.json` | new finding F-C0670 |

Regenerate and check: `python3 semantics/tools/build_semantics.py && python3 semantics/tools/trace_requirements.py &&
python3 semantics/tools/check_semantics.py && python3 semantics/tools/check_semantics.py --self-test` (from
`experiment/playbook-completion/`); the models: `CARGO_TARGET_DIR=$RUN_DIR/target/semantics cargo run --release -- --out
RESULTS.json` in `models/semantics/` (about 2 s).

## 1. Axioms (step 1)

Fourteen axioms (`AXIOMS.md`). AX-01..AX-09 repair SYS-I1..SYS-I10 (SYS-I3 and SYS-I9 merge into AX-03, "explicit, inert
refusals"); AX-10 removal reaches every store and copy, AX-11 conflicting commands serialize, AX-12 truthful outcomes and
committed observations (with read purity), AX-13 least capability and AX-14 accepted work progresses are new. Every
finding in `findings/audit/` (264 at this pass) is classed by hand against them (`src/finding_classes.json`): 180 break
at least one axiom, the rest are functional (53), documentation (23), environment (7), test (2), performance (1) or
refuted/not reproduced (4). The checker fails when a finding appears that is not classed, so a new finding from any lane
must be placed under an axiom (a ratchet; this pass classed six findings the writesets lane filed while it ran).
Exceptions are named (EXC-01..EXC-10: DDL after commit, PurgeAll, post-commit properties, unledgered vectors, the 30 s
route memory, the interned snapshot's missing graph dimension, tombstone digests, monotone counters, legacy objects, and
unlocked algorithm reads). The ontology's SYS-I statements are not edited (ontology lane); the repaired wording is proposed
in `axioms_src.json`.

## 2. Mechanisms (step 2) and their generic models

Thirteen mechanisms (`MECHANISMS.md`): M-01 ledger commit with record, M-02 retry and idempotency binding, M-03 exclusive
section (head lock and redaction marker, writer locks), M-04 derived store with staleness (adjacency, degree and result
caches, interned snapshot, BM25, IVF, statement maps, aggregates, engine caches), M-05 store inventory and removal, M-06
snapshot save and restore, M-07 background job and queue, M-08 install, settings and version gate, M-09 graph key and
tenant scope, M-10 unit of work (all or none, inert refusal), M-11 capability gate, M-12 catalog binding of artifacts to
graph and identity, M-13 read epoch. 45 laws in all.

Models (`models/semantics/`, explorer and actors at `c03f9fa`): each mechanism is one machine generic over a trait, with
one trait instance per object (or group of objects with one variant), declaring the as-built variant (policies, step
programs or paths, cited to the pin in the file comments) and the reviewed one (the mechanism's canonical policies). The
laws are written once per machine. 266 checks, all met, all exhaustive within declared bounds, none truncated
(`sem-mc-all`): 99 as-built and 2 exception checks, 106 reviewed (including sharpness witnesses), 59 negative controls
(at least one per law, each caught as a violation of exactly its law). The as-built checks reproduce, as violations of the
named law, the departures recorded by 114 findings from all 18 modules with operations (01-18; for example F-1302 and F-1303 as
M03-L3/L4/L5, F-0402 as M04-L1, F-0702 and F-0606 as M05-L1, F-1801 as M06-L2, F-1306 as M02-L2, F-1304 as M09-L4,
F-C0702 as M10-L2, F-C1803 as M11-L3, F-0901 as M12-L3, F-1402 as M13-L1). 52 of the 62 objects hand-roll at least one
mechanism; every hand-rolled variant that departs from a law names its finding(s) or a named exception, and has an as-built
check that shows the departure (checked by `check_semantics.py`). One departure had no finding: two embed-queue workers can
work one entry at once (M07-L2); it is recorded as **F-C0670** (S3, high confidence; evidence: source, the intent lane's
probe `intent-a-hd0604-queue-claim`, and `sem-mc-queue-as-built`).

Limits, stated: these are explorer checks of small abstract machines, exhaustive only within their bounds (two or three
processes, two to four writes); the playbook asks for generic lemmas *proved* once over a trait (Verus), which this lane
did not write. 63 findings that break an axiom are not attached to any mechanism instance (`MECHANISMS.md`, last section):
they are further variants of modelled instances or outside every machine's subset.

## 3. Lifecycles and objects (step 3)

Eight canonical lifecycles (`LIFECYCLES.md`): LC-1 content item, LC-2 derived entry, LC-3 setting or install, LC-4 history
item, LC-5 run, LC-6 scope, LC-7 session, request or claim, LC-8 copy. The object list is derived mechanically from the 62
`Entity` lines of the ontology (module 00 declares none). Every object maps each of its ontology states and commands onto
one canonical state (with facets) and one canonical command; 60 objects declare a lifecycle, 2 carry an explicit reason
(`02/graph-name`: its states are classes of an input value; `08/graph-scope`: a facet of the Cypher request). Every object
uses at least one mechanism and therefore relies on at least one axiom (`objects.json`). Canonical ids have one meaning
across the vocabulary (five colliding ids were renamed: four reported by the mapping, one found by the checker's vocabulary
rule; seven ids recur with one meaning seen from two levels). The mapping exposes gaps that are already findings: IVF and BM25 indexes have no stale state (F-0606, F-0703),
the queue entry has no running state (F-C0601, F-C0670), the reifier has an orphan state (F-1502).

## 4. Requirement trace (the 3.3a gate)

**Definition.** A requirement is every ontology statement (`ontology/[0-9]*.md`, Statements tables, all 19 modules) of kind
B (business rule), T (technical rule), I (invariant), X (refusal) or P (premise about IRIS, the driver or the operator).
R (roots), D (definitions, including restatements) and Q (open questions, which name a human decision rather than state a
rule) are not requirements. Why the ontology and not the specs' FR-/SC- ids: the ontology is the audit's one source-cited
statement of intent for every module under the literal 3.1 rule (3,877 statements); the specs cover only some modules
(none for vectors, interfaces or operations) and the ontology already cites the FR ids it restates. The set is
exhaustive by construction (the checker parses the ontology itself and requires every requirement exactly once).

**Bases**, in order, all recorded: `repairs` (SYS-I -> its AX), `finding:` (the statement cites a finding classed to an
axiom), `kind` (every X statement -> AX-03), `rule:` (regex rules, `src/trace_rules.json`), `explicit` (by hand,
`src/trace_explicit.json`), and `fallback:functional` (a B or T statement with no other target traces to its module's
functional contract DC-FUNC-NN). I, X and P statements have no fallback.

**Result** (`trace.json`): 2,600 requirements (B 1,160, T 822, X 364, I 149, P 105); 2,545 traced, **55 open** (53 P, 2 I),
each with its reason in `src/trace_explicit.json` (`open_reasons`). Of the traced: 1,441 to an axiom, 59 to an iris-contract
clause, 23 to a named exception, 13 to DC-REPLAY, and 1,041 only to a module's functional contract (the weakest trace: it
says the statement is a functional rule of its module, which no universal axiom governs). The open P statements are IRIS,
driver, edition or third-party facts outside the validated contract subset (catalog and grants, string and parameter
limits, HNSW, Task Manager, FHIR, %AI, Arno, networkx); the two open I statements are cost and memory bounds (TXT-B4.8,
INT-R1.13), which no axiom covers. Open by module: 01: 13, 17: 10, 15: 8, 06: 5, 10: 4, 05/07/08/09/11/16: 2 each,
02/03/04: 1 each.

**Precision of the rule classifier** (`data/trace_sample_review.json`, seed 20261114, 80 rule-traced requirements,
one reviewer, the lane itself, not independent): round 1 agree 67, partly 10, disagree 3; the systematic false positives
were fixed anyway and round 2 drawn: agree 68, partly 10, disagree 2 (2.5%). The broad AX-02 (graph scope) and AX-08
(derived store) rules produce most "partly" verdicts.

## 5. Module 00: the universal axioms over the composed mechanisms (3.3-model-check, module 00)

`models/semantics/src/sys00.rs` composes M-01, M-02, M-03, M-04, M-05 and M-10 over two tenants and four processes (a
client committing tenant A with a retry key and retrying once, a commit of tenant B, erasure of A, redaction of A with
park, operator re-erase and resume). The axioms AX-02..AX-08, AX-10..AX-12 are invariants or action properties over the
composed state, AX-14 is AG EF. Results (`sem-mc-sys00-reviewed`, `sem-mc-sys00-as-built`, `sem-control-sys00`, 29 checks,
exhaustive):
- the reviewed composition keeps every one of the 11 safety axioms and AX-14 (654 states);
- the as-built composition (eraser without head lock and without reaching the derived store, unlocked liveness check and
  late marker, Final clearing any marker, post-commit properties re-applied on a replay) violates AX-06 (F-1101, F-1306),
  AX-07 and AX-11 (F-1302), AX-08 (F-0702, F-0606 family), AX-10 (F-1306 revival, F-0702), and keeps AX-02, AX-03, AX-04,
  AX-05, AX-12 and AX-14 *within this composition* (the product breaks them elsewhere: see the generic machines);
- 11 controls, one mutant of the reviewed composition per axiom, each caught as a violation of exactly its axiom;
- 4 sharpness witnesses (a completed redaction while B is live, a retry refused after redaction, a replay, a writer
  refused by the marker).
AX-01, AX-09 and AX-13 are not in the composition; their laws are checked by the generic machines of M-12 and M-01 (AX-01),
M-08 (AX-09) and M-11 (AX-13). Progress premises (operator re-runs) are those of `TRUST.md`.

## 6. F-C0605 (module 06)

`models/semantics/src/queue.rs`, machine `Order`: node ids 0 and 1 (low-collating, re-enqueued without bound as node text
changes; the state stays finite) and 2 (high), served one at a time in collation order as ClaimPendingBatch and ProcessBatch
do (EmbedQueue.cls:112-133, 258-268). As built, law M07-L3 (bounded overtaking, at most N-1 = 2 others served while an entry
waits) is violated, and the fair-lasso check (`harness::fair_lasso`, added in this crate: Tarjan SCC over the whole
reachable graph, looking for a cycle of states in which id 2 stays pending that contains a worker step) finds an infinite
fair run on which id 2 is never served. AG EF "id 2 can still be served" holds as built, which is why the bounded breadth-a
`vec_queue` model drained and could not show the finding. Reviewed FIFO passes both; a LIFO control is caught by both
(`sem-mc-queue-as-built`, `sem-mc-queue-reviewed`, `sem-control-queue`). `fair_lasso` is unproved tooling; its controls are
the FIFO pass and the LIFO and as-built catches. F-C0605's disposition (confirmed-source) is the breadth lane's; this is a
model reproduction (model-level).

## 7. Registered evidence

`sem-mc-all` (266 checks); per family `sem-mc-<family>-as-built` (expected-violation), `sem-mc-<family>-reviewed` (pass),
`sem-control-<family>` (expected-violation) for ledger, retry, excl, derived, removal, snapshot, queue, install, scope, unit,
cap, catalog, epoch, sys00 (42 records); `sem-check` (0 violations) and `sem-check-selftest` (base clean, 18 of 18 seeded
mutations caught). Logs under `$RUN_DIR/semantics/r1/`.

**Erratum (proposed for `evidence/errata.json`, orchestrator's file):** the `sem-mc-all` record says "as-built 99
(including 2 exception checks for EXC-05, EXC-06), reviewed 106 (including sharpness), controls 61". Correct: as-built 99
plus 2 exception checks (101), reviewed 106, controls 59; total 266 (RESULTS.json is right; only the description is wrong).

## 8. Open obligations (exact)

1. **Trace:** 55 requirements open (53 P premises outside the validated IRIS-contract subset, 2 I cost/memory rules);
   1,041 traced only to a module's functional contract, whose L1 models are not checked statement by statement.
2. **Mechanisms:** generic lemmas are explorer checks over a trait, not Verus proofs over a trait; 63 axiom-breaking
   findings not attached to a mechanism instance.
3. **Axioms:** the repaired wording is not in `ontology/00-system.md` (ontology lane); AX-12's durability half rests on an
   intent-undecided premise (F-C1102).
4. **Write sets (step 5):** not discharged here (writesets lane, 3.3a-writesets).
5. No result here transfers to the product: the product obligation of every cell stays failed where an as-built check or a
   finding shows the departure.
