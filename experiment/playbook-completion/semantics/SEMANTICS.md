# System semantics of IVG, system-wide (playbook 3.3a)

Product pin `3eaa79cf` (tree `b098a6f4`), unchanged. Semantics lane, steer 7 (queue item Q17b), revised after the fourth
independent review (R4-08, R4-09). Observation only: the product is not changed; every result below about a model is a
statement about that model, never about the product. The original submission's semantics covered the erase, redact and
replay slice only (`experiment/playbook-uplift/semantics/SEMANTICS.md`); this lane does steps 1-3 of 3.3a for all 19
modules, the requirement trace of the 3.3a gate, the module-00 model check (3.3 for the system axioms) and the model of
F-C0605. Step 5 (write-set obligations, 3.3a-writesets) belongs to the writesets lane and is not discharged here; step 4
(the domain contract, replay equals the store) is the existing 3.3a-domain-contract cell, used here as clause DC-REPLAY.

## What is here

| File | Content |
|---|---|
| `AXIOMS.md`, `axioms.json` | 14 universal axioms (SYS-I1..I10 repaired and extended), 11 named exceptions, the contract clauses a requirement may trace to |
| `MECHANISMS.md`, `mechanisms.json` | 13 shared mechanisms: state, operations, effect kinds, events, L1 laws, generic controls, the objects using each (canonical or hand-rolled), per-law departures with their findings or exceptions, model checks and their complements |
| `LIFECYCLES.md`, `lifecycles.json` | 8 canonical lifecycles; naming collisions in the ontology and how the mapping resolves them |
| `objects.json` | the 77 objects (every ontology `Entity` line, derived mechanically), each with lifecycle, state and command map, mechanisms, axioms, hand-rolled variants, findings |
| `trace.json` | 2,939 requirements traced (or listed open) |
| `src/` | hand-written sources: `axioms_src.json`, `mechanisms_src.json`, `objects_map.json`, `finding_classes.json` (every finding classed by axiom), `trace_rules.json`, `trace_explicit.json` |
| `data/trace_sample_review.json` | hand review of the rule-based trace classifier (precision) |
| `tools/build_semantics.py` | builds `axioms.json`, `mechanisms.json`, `objects.json` from `src/` and the model results (`--check`) |
| `tools/render_docs.py` | renders `AXIOMS.md` and `MECHANISMS.md` from the JSON (`--check`) |
| `tools/trace_requirements.py` | builds `trace.json` (`--check`) |
| `tools/check_semantics.py` | the gate checker, with `--self-test` |
| `../models/semantics/` | the explorer crate: one generic machine per mechanism, the module-00 composition, `RESULTS.json` |
| `../findings/audit/zz-semantics.json` | new finding F-C0670 |

Regenerate and check, from `experiment/playbook-completion/`: `python3 semantics/tools/trace_requirements.py && python3
semantics/tools/build_semantics.py && python3 semantics/tools/render_docs.py && python3 semantics/tools/check_semantics.py
&& python3 semantics/tools/check_semantics.py --self-test`; the models: `CARGO_TARGET_DIR=$RUN_DIR/target/semantics cargo
run --release -- --out RESULTS.json` in `models/semantics/` (a few seconds).

## 1. Axioms (step 1)

Fourteen axioms (`AXIOMS.md`). AX-01..AX-09 repair SYS-I1..SYS-I10 (SYS-I3 and SYS-I9 merge into AX-03, "explicit, inert
refusals"); AX-10 removal reaches every store and copy, AX-11 conflicting commands serialize, AX-12 truthful outcomes and
committed observations (with read purity), AX-13 least capability and AX-14 accepted work progresses are new. Every
finding in `findings/audit/` (309 at this pass; a finding whose disposition is `duplicate`, such as F-C1720 of F-C1743,
is not counted) is classed by hand against them (`src/finding_classes.json`): 208 break at least one axiom, the rest are
functional (63), documentation (23), environment (10), test (3), performance or capacity (3), or refuted/not reproduced
(5, F-C1240 and F-1612 among them). The checker fails when a finding appears that is not classed,
so a new finding from any lane must be placed under an axiom (a ratchet). Exceptions are named (EXC-01..EXC-11: DDL after
commit, PurgeAll, post-commit properties, unledgered vectors, the 30 s route memory, the interned snapshot's missing graph
dimension, tombstone digests, monotone counters, legacy objects, unlocked algorithm reads, and an undeclared adjacency or
label index kept only by the engine's writers). The ontology's SYS-I statements are not edited (ontology lane); the
repaired wording is proposed in `axioms_src.json`.

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
laws are written once per machine. 272 checks, all met, all exhaustive within declared bounds, none truncated
(`sem-mc-all-r2`): 102 as-built and 2 exception checks, 109 reviewed (including sharpness witnesses), 59 negative controls
(at least one per law).

**What a check shows.** An as-built check or a control is attributed to one law with `Keep::only`: the explorer's
shortest counterexample violates that law. That does not mean no other law is violated. Since the review-4 rerun the
harness also runs the complement for every Keep check: each safety law of the underlying model explored alone, recorded
in `RESULTS.json` (`violates`, `also_violates`). Of the 140 violation checks, 58 also violate another law (as-built 38 of
82, exception 1 of 2, controls 19 of 56); no reviewed check violates any law. Most of the overlaps are one defect seen by
two laws of the same mechanism (an unmaintained write leaves a derived entry current and wrong, so M04-L2 and M04-L1 and
the gated read M04-L4 all fail; a store missing from the inventory fails M05-L1 and M05-L3).

**Departures.** 59 of the 77 objects hand-roll at least one mechanism. A departure is declared per law, with the
finding(s) that record it or a named exception, and a `why` where it is a consequence of the same defect. The checker
requires, for every modelled instance, that the laws its as-built model violates (the complement sets) equal its declared
departures (`departure-undeclared`, `departure-unshown`), so no departure stays undeclared: the 21 undeclared departures
the review found are declared (each a consequence of the finding already cited, except the native gate's M04-L1/L2 under
the new exception EXC-11), four instances were split so that an object's model shows only its own variants
(result-cache-04, adjacency-no-lock-mark, bm25- and ivf-index-graph-unchecked), declared departures that no check showed
were corrected (M10-L3 for the Bolt session and M10-L2 for the FHIR graph removed: F-1601's reply aspect and F-1511 are
attributed to M10-L1; 18/namespace and 08/cypher-call now name the second model that shows their other law), and
13/redaction-run, declared canonical while its model violated three laws, is hand-rolled with the target's departures. The as-built checks reproduce departures recorded by findings from all 18 modules
with operations (for example F-1302 and F-1303 under M03-L3/L4/L5, F-0402 under M04-L1, F-0702 and F-0606 under M05-L1,
F-1801 under M06-L2, F-1306 under M02-L2, F-1304 under M09-L4, F-C0702 under M10-L2, F-C1803 under M11-L3, F-0901 under
M12-L3, F-1402 under M13-L1). One departure had no finding: two embed-queue workers can work one entry at once (M07-L2);
it is recorded as **F-C0670** (S3, high confidence).

Limits, stated: these are explorer checks of small abstract machines, exhaustive only within their bounds (two or three
processes, two to four writes); the playbook asks for generic lemmas *proved* once over a trait (Verus), which this lane did
not write (PROOF-DEBT D-14; 3.3a-mechanisms is open for it). 75 findings that break an axiom are not attached to any
mechanism instance (`MECHANISMS.md`, last section): they are further variants of modelled instances or outside every
machine's subset.

## 3. Lifecycles and objects (step 3)

Eight canonical lifecycles (`LIFECYCLES.md`): LC-1 content item, LC-2 derived entry, LC-3 setting or install, LC-4 history
item, LC-5 run, LC-6 scope, LC-7 session, request or claim, LC-8 copy. The object list is derived mechanically from the 77
`Entity` lines of the ontology (module 00 declares none; the ontology-2 lane added 15, mapped in this revision). Every
object maps each of its ontology states and commands onto one canonical state (with facets) and one canonical command;
75 objects declare a lifecycle, 2 carry an explicit reason (`02/graph-name`: its states are classes of an input value;
`08/graph-scope`: a facet of the Cypher request). Every object uses at least one mechanism and therefore relies on at least
one axiom (`objects.json`). Canonical ids have one meaning across the vocabulary (five colliding ids were renamed: four
reported by the mapping, one found by the checker's vocabulary rule; seven ids recur with one meaning seen from two
levels). The mapping exposes gaps that are already findings: IVF and BM25 indexes have no stale state (F-0606, F-0703),
the queue entry has no running state (F-C0601, F-C0670), the reifier has an orphan state (F-1502).

## 4. Requirement trace (the 3.3a gate)

**Definition.** A requirement is every ontology statement (`ontology/[0-9]*.md`, Statements tables, all 19 modules) of kind
B (business rule), T (technical rule), I (invariant), X (refusal) or P (premise about IRIS, the driver or the operator).
R (roots), D (definitions, including restatements) and Q (open questions, which name a human decision rather than state a
rule) are not requirements. Why the ontology and not the specs' FR-/SC- ids: the ontology is the audit's one source-cited
statement of intent for every module under the literal 3.1 rule; the specs cover only some modules (none for vectors,
interfaces or operations) and the ontology already cites the FR ids it restates. The set is exhaustive by construction (the
checker parses the ontology itself and requires every requirement exactly once).

**Bases**, in order, all recorded: `repairs` (SYS-I -> its AX), `finding:` (the statement cites a finding classed to an
axiom), `kind` (every X statement -> AX-03), `rule:` (regex rules, `src/trace_rules.json`), `explicit` (by hand,
`src/trace_explicit.json`), and `fallback:functional` (a B or T statement with no other target traces to its module's
functional contract DC-FUNC-NN). I, X and P statements have no fallback.

**Result** (`trace.json`, regenerated on the ontology after the ontology-2 lane and against the contract extended by
the contract-2 lane): 2,939 requirements (B 1,333, T 971, X 381, I 149, P 105); 2,884 traced, **55 open** (53 P, 2 I),
each with its reason in `src/trace_explicit.json` (`open_reasons`). Of the traced: 1,627 to an axiom, 79 to an IRIS
contract clause (round r6 or contract-2), 23 to a named exception, 14 to DC-REPLAY, and 1,183 only to a module's
functional contract (the weakest trace: it says the statement is a functional rule of its module, which no universal
axiom governs). Open by module: 01: 13, 17: 10, 15: 8, 06: 5, 10: 4, 05/07/08/09/11/16: 2 each, 02/03/04: 1 each.

**Re-trace against the contract-2 extension** (clauses E-1, S-1, X2-JSON, X2-LIST, X2-TOP, X2-BATCH, X2-IOU, X2-QUERY,
X2-MERGE in `contract-2/VALIDATED.json`, all registered pass; the checker and the trace tool now read them as contract
clauses). None of the 55 open requirements is decided by a new clause: the clauses validate embedded SQL, SQL procedure
levels, JSON, $LIST, TOP/LIMIT, executemany, INSERT OR UPDATE, $QUERY and MERGE, and no open premise is about those.
17 already-traced statements whose IRIS behaviour a new clause decides gained it (S-1: CYP-P2, WRT-T2.4, CYP-T6.1,
OPS-B4.9, LED-B9.5, INS-B10.1.91; X2-TOP: WRT-B92, INS-B12.90, OPS-B3.4; X2-BATCH: VEC-B3.13; X2-IOU: INT-B1.2, SNP-B3.2;
X2-JSON: ADJ-T2.90, CYP-T11.98; X2-LIST: LED-B4.7, RED-B2.1, NAT-B1.5). All 55 stay outside. 42 of them are held by a named
contract-2 outside premise (assumed, not validated; `contract-2/coverage.json` families), recorded per statement as
`outside_premise`: P2-ABSENT 7 (%AI and FHIR server absent on Community), P2-SEC 5 (grants, revoke, privilege checks,
read-only databases, server SQL rights), P2-CATALOG 4, P2-DICT 4, P2-LIMITS 4 (string length, bound parameters, callout
heap), P2-SQLEXPR 2, P2-SQLTEXT 2, and one each of P2-CFG, P2-EPY, P2-FK, P2-HNSW, P2-IFIND, P2-JOB, P2-NATIVESUB, P2-OBJ,
P2-SQLCODE, P2-SQLROUTINE, P2-STATUS, P2-TASK, P2-TRIGGER, P2-WEB. 13 have no clause and no premise family, each with
its reason: TXT-B4.8 (cost) and INT-R1.13 (memory bound), the two I rules; the third-party library facts ALG-P1, ALG-P4
(Arno), ALG-P5 (networkx), INT-S1.12 (pySHACL); the driver and packaging facts OPS-P4, OPS-P6; the language fact OPS-P12;
OPS-P16 (image availability) and INS-P4.16 (an upstream test-session deploy fact), which are not engine behaviour; and
WRT-P5.12 (an equal-text SET is not written) and TMP-P4 (a global value keeps its number or text type), engine behaviour
that neither a clause nor a premise family covers.

**Precision of the rule classifier** (`data/trace_sample_review.json`, seed 20261114, 80 rule-traced requirements of the
2,600 before the ontology-2 additions, one reviewer, the lane itself, not independent): round 1 agree 67, partly 10,
disagree 3; after fixing the systematic false positives, round 2 agree 68, partly 10, disagree 2 (2.5%). The 339
statements the ontology-2 lane added were traced by the same rules and are not in the sample.

## 5. Module 00: the universal axioms over the composed mechanisms (3.3-model-check, module 00)

`models/semantics/src/sys00.rs` composes M-01, M-02, M-03, M-04, M-05 and M-10 over two tenants and four processes (a
client committing tenant A with a retry key and retrying once, a commit of tenant B, erasure of A, redaction of A with
park, operator re-erase and resume). The axioms AX-02..AX-08, AX-10..AX-12 are invariants or action properties over the
composed state, AX-14 is AG EF. Results (`sem-mc-sys00-reviewed-r2`, `sem-mc-sys00-as-built-r2`, `sem-control-sys00-r2`,
29 checks, exhaustive):
- the reviewed composition keeps every one of the 11 safety axioms and AX-14 (654 states; complement empty);
- the as-built composition (eraser without head lock and without reaching the derived store, unlocked liveness check and
  late marker, Final clearing any marker, post-commit properties re-applied on a replay) violates AX-06 (F-1101, F-1306),
  AX-07 and AX-11 (F-1302), AX-08 (F-0702, F-0606 family) and AX-10 (F-1306 revival, F-0702): each as-built check is
  attributed to one axiom, and the complement shows the composed model violates all of them together (six properties:
  AX-06, AX-07, AX-08, AX-10 and both AX-11 properties); the
  AX-02, AX-03, AX-04, AX-05, AX-12 and AX-14 checks pass for those axioms *within this composition* (the product breaks
  them elsewhere: see the generic machines);
- 11 controls, one mutant of the reviewed composition per axiom, each caught as a violation of its attributed axiom; 6 of
  them also violate other axioms (complement: for example `sys00-control-ax03-refusal-writes` also breaks AX-07, AX-08
  and AX-11, because the refusal writes ungoverned content);
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
(`sem-mc-queue-as-built-r2`, `sem-mc-queue-reviewed-r2`, `sem-control-queue-r2`). `fair_lasso` is unproved tooling; its
controls are the FIFO pass and the LIFO and as-built catches. F-C0605's disposition (confirmed-source) is the breadth
lane's; this is a model reproduction (model-level).

## 7. Registered evidence

Current: `sem-mc-all-r2` (272 checks with complements); per family `sem-mc-<family>-as-built-r2` (expected-violation),
`sem-mc-<family>-reviewed-r2` (pass), `sem-control-<family>-r2` (expected-violation) for ledger, retry, excl, derived,
removal, snapshot, queue, install, scope, unit, cap, catalog, epoch, sys00 (42 records); `sem-check-r2` (0 violations) and
`sem-check-selftest-r2` (base clean, 21 of 21 seeded mutations caught); after ten more findings arrived from the
structural follow-up and contract-2 lanes and were classed, `sem-check-r3` and `sem-check-selftest-r3` (same results);
after eleven more (refusals, writesets, product-gates) were classed, duplicates were left uncounted and the trace was
re-run against the contract-2 clauses, `sem-check-r4` and `sem-check-selftest-r4`. Logs under `$RUN_DIR/semantics/r2/`,
`r3/` and `r4/`. The first
pass's records (`sem-mc-all`, `sem-mc-<family>-*`, `sem-control-<family>`, `sem-check`, `sem-check-selftest`, logs under
`$RUN_DIR/semantics/r1/`) stay registered and are superseded.

**Errata (proposed for `evidence/errata.json`, the orchestrator's file; texts in `MATRIX-INPUT.json` `errata_proposed`):**
- `sem-mc-all`: the counts in its description are wrong ("as-built 99 (including 2 exception checks), controls 61"; correct:
  99 as-built plus 2 exception, 106 reviewed, 59 controls, 266 in all).
- the 15 records review 4 marked PARTIAL (`sem-mc-{retry,excl,derived,removal,queue,cap,catalog,sys00}-as-built`,
  `sem-control-{retry,excl,derived,removal,queue,catalog,sys00}`): "each a violation of exactly its law" overclaims;
  each check violates its attributed law, and the listed checks also violate another law.

## 8. Open obligations (exact)

1. **Trace:** 55 requirements open (53 P premises outside the validated IRIS contract, including contract-2's clauses, of
   which 42 are held by a named contract-2 premise and 11 by none; 2 I cost/memory rules); 1,183 traced only to a module's
   functional contract, whose L1 models are not checked statement by statement; the rule precision sample predates the
   339 ontology-2 statements.
2. **Mechanisms:** generic lemmas are explorer checks over a trait, not Verus proofs over a trait (D-14); 75 axiom-breaking
   findings not attached to a mechanism instance.
3. **Axioms:** the repaired wording is not in `ontology/00-system.md` (ontology lane); AX-12's durability half rests on an
   intent-undecided premise (F-C1102).
4. **Write sets (step 5):** not discharged here (writesets lane, 3.3a-writesets).
5. No result here transfers to the product: the product obligation of every cell stays failed where an as-built check or a
   finding shows the departure.
