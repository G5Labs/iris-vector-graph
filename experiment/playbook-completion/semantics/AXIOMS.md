# Universal axioms of IVG (playbook 3.3a step 1)

Product pin `3eaa79cf`. Semantics lane. Machine-readable: `axioms.json` (built by `tools/build_semantics.py` from
`src/axioms_src.json`; violating findings from the hand classification `src/finding_classes.json`; reliance from
`objects.json`; module-00 checks from `models/semantics/RESULTS.json`). Rendered by `tools/render_docs.py`. Checked by
`tools/check_semantics.py` (`sem-check-r2`, self-test `sem-check-selftest-r2`).

The original slice-only semantics (`experiment/playbook-uplift/semantics/SEMANTICS.md`) used the ten system statements
SYS-I1..SYS-I10 of `ontology/00-system.md`. Here they are repaired and extended to fourteen axioms for the whole product:
SYS-I3 and SYS-I9 merge into one (the playbook's "explicit, recorded refusals"); SYS-I1, I2, I4..I8 and I10 are kept with
the repairs stated per axiom; five are new (AX-10..AX-14: removal reach, serialization, truthful outcomes, capability,
progress), because 77 of the 309 findings in `findings/audit/` break one of them and 51 of those break
no rule a SYS statement stated. The ontology's SYS-I statements are not edited (ontology lane); the repair is proposed here.

Each finding was classified by hand against the axioms (`src/finding_classes.json`, 309 findings, every one exactly
once; the checker fails when a new finding appears unclassified). Classes outside the axioms: FUNC (a module's own
functional contract; 63), DOC (document against code; 23), ENV (10), TEST (3), PERF (performance or capacity; 3), NONE (refuted or not reproduced; 5).
208 of 309 findings break at least one axiom.

## The axioms

| Id | Axiom | Rule | Repairs | Mechanisms | Objects (modules) relying | Findings breaking it (S1/S2/S3/S4) | Exceptions |
|---|---|---|---|---|---|---|---|
| AX-01 | One writer per fact | Each kind of stored fact has one owning mechanism, and every write of that fact goes through it, with the owner's checks. | SYS-I1 | M-12 | 9 (6) | 23 (2/10/7/4) | - |
| AX-02 | Graph and tenant scope | A command scoped to a graph or tenant reads and changes only that graph's or tenant's content; an all-graphs read is the union of each graph's own answer; every predicate that names a tenant (erase, liveness, record match) names the same content. | SYS-I2 | M-05, M-09, M-12 | 35 (15) | 42 (18/16/6/2) | EXC-06 |
| AX-03 | Explicit, inert refusals | A refused or failed command leaves every store as it was (the caller's own earlier writes included) and says why, with a code of the product's error family; a failure is never reported as success, as no rows, or as another error. | SYS-I3, SYS-I9 | M-08, M-10, M-11 | 37 (13) | 36 (2/12/14/8) | - |
| AX-04 | All or none across stores | A command that writes several stores writes all of them or none: it is one transaction, or a sequence whose every intermediate state is named and recoverable. | SYS-I4 | M-01, M-05, M-10 | 36 (14) | 13 (2/7/3/1) | EXC-01, EXC-08 |
| AX-05 | History only grows | The ledger's records and revisions are only appended; a saved record changes only into its tombstone, and the head never moves back. | SYS-I5 | M-01, M-06 | 13 (6) | 3 (2/1/0/0) | EXC-02 |
| AX-06 | At most once per retry key | A request repeated with the same retry key (or the same business identity) takes effect at most once; a repeat gets the first answer without any further effect, or a clear refusal. | SYS-I6 | M-02 | 7 (6) | 6 (2/3/1/0) | - |
| AX-07 | A governed change is recorded with it | While the ledger governs a kind of content, every change of that content is saved in the same transaction as its record; a write that cannot be recorded is refused in strict mode. | SYS-I7 | M-01 | 12 (6) | 16 (2/9/4/1) | EXC-03, EXC-04 |
| AX-08 | Derived stores match or say they are stale | A store built from other stores either equals its derivation from their committed content or carries a staleness signal every reader checks; a rolled-back or interrupted source write never leaves a derived store current and wrong. | SYS-I8 | M-04, M-12 | 22 (12) | 22 (0/16/4/2) | EXC-05, EXC-11 |
| AX-09 | One install, one schema, one version per namespace | A namespace holds one install of the product under one recorded schema; setup is idempotent, reports every failure, never touches objects outside that schema, and code runs only against the version it expects. | SYS-I10 | M-08 | 13 (7) | 10 (1/4/4/1) | EXC-09 |
| AX-10 | Removal reaches every store and copy | Erasure followed by redaction removes a target's content from every store that holds it, every derived store and every copy the product makes (indexes, quarantine, snapshots, history text, retry keys), or the receipt names exactly what remains. | new | M-05, M-06 | 14 (7) | 19 (11/4/4/0) | EXC-07 |
| AX-11 | Conflicting commands serialize | Commands whose footprints overlap behave as if run one at a time: each takes the lock that guards what it reads and writes, a marker is set before the first effect it guards, and only its owner clears it. | new | M-03, M-07 | 13 (10) | 22 (6/9/7/0) | - |
| AX-12 | Truthful outcomes and committed observations | A command's reported outcome equals its effect: success means the whole effect happened and is kept, counts and receipts report what was done; a read changes no stored state except derived caches, and a read or an archive shows a state some serial order of committed commands produced. | new | M-02, M-03, M-06, M-07, M-10, M-13 | 38 (18) | 24 (4/13/6/1) | EXC-10 |
| AX-13 | Least capability | A caller can do only what its key and role allow: a read-only caller changes nothing, a missing or wrong key is refused before any effect, and no entry point hands a caller a capability beyond the product's API (server files, raw SQL or code text). | new | M-11 | 13 (5) | 10 (4/4/2/0) | - |
| AX-14 | Accepted work progresses | Work the product accepts (a queue entry, a run, a session) finishes or is reported failed under fair scheduling: no entry starves, no run restarts forever, no resource stays held after its holder ends. | new | M-07 | 5 (4) | 5 (0/3/1/1) | - |

## Repairs, sources and the findings that break each axiom

### AX-01 One writer per fact

- Rule: Each kind of stored fact has one owning mechanism, and every write of that fact goes through it, with the owner's checks.
- Formal reading: `for every store s and every write step w: writes(w) contains s => w is a method of owner(s), or w calls owner(s) with owner(s)'s guards`
- Repair: SYS-I1 named the owner but not the guards; a writer that writes the owned store directly, or calls the owner while skipping its checks (identity, mark, kind), is the same defect (F-0602, F-0603, F-1107).
- Sources at the pin: `docs/adr/0011-the-adjacency-index-has-one-writer-module.md:10-17`; `docs/adr/0002-temporal-globals-are-not-directly-accessible.md`; `docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md`; `CONTEXT.md:121-128`
- Implemented by: M-12; relied on by 9 objects in modules 06, 07, 09, 10, 15, 17
- Not in the module-00 composition; its laws are checked by the generic machines of M-12
- As-built findings breaking it, S1: F-0304, F-1114
- As-built findings breaking it, S2: F-0506, F-0601, F-0602, F-0603, F-1107, F-C0151, F-C0349, F-C0350, F-C0450, F-C1150
- As-built findings breaking it, S3: F-0404, F-0613, F-C0340, F-C0351, F-C0840, F-C1001, F-C1540
- As-built findings breaking it, S4: F-C0440, F-C0640, F-C1040, F-C1740

### AX-02 Graph and tenant scope

- Rule: A command scoped to a graph or tenant reads and changes only that graph's or tenant's content; an all-graphs read is the union of each graph's own answer; every predicate that names a tenant (erase, liveness, record match) names the same content.
- Formal reading: `answer(cmd, g) = answer(cmd, restrict(state, g)); effect(cmd, g) leaves restrict(state, h) unchanged for h != g; erase_pred(t) = live_pred(t) = match_pred(t)`
- Repair: SYS-I2 covered answers only. Extended to writes (F-1503, F-0507), to the all-graphs union rule (CONTEXT.md:38-43, F-0209) and to the three target predicates whose difference is the root of F-1304/F-1305 (P-1310 refuted, TRUST.md).
- Sources at the pin: `CONTEXT.md:27-59`; `docs/adr/0001-graph-key-as-first-subscript.md`; `docs/adr/0003-two-graph-key-derivations.md`; `specs/256-ledger-tenant-redaction/spec.md:142-148`
- Implemented by: M-05, M-09, M-12; relied on by 35 objects in modules 02, 03, 05, 06, 07, 08, 09, 10, 11, 12, 13, 15, 16, 17, 18
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-as-built-ax-02`, `sys00-control-ax02-tomb-both-tenants`
- As-built findings breaking it, S1: F-0705, F-0707, F-0711, F-0802, F-0816, F-0818, F-0820, F-1001, F-1002, F-1008, F-1304, F-1305, F-1502, F-1503, F-1603, F-1604, F-1701, F-C1351
- As-built findings breaking it, S2: F-0106, F-0202, F-0206, F-0507, F-0609, F-0616, F-0819, F-1006, F-1105, F-1401, F-1507, F-1803, F-C0150, F-C0701, F-C1307, F-C1547
- As-built findings breaking it, S3: F-0605, F-1009, F-1013, F-C0340, F-C0347, F-C1041
- As-built findings breaking it, S4: F-0203, F-0209

### AX-03 Explicit, inert refusals

- Rule: A refused or failed command leaves every store as it was (the caller's own earlier writes included) and says why, with a code of the product's error family; a failure is never reported as success, as no rows, or as another error.
- Formal reading: `outcome(cmd) = refused(code) => state' = state and code in ErrorFamily(cmd)`
- Repair: Merges SYS-I3 (changes nothing) and SYS-I9 (says why), as the playbook's 'explicit, recorded refusals'. Extended: the caller's earlier writes in its own transaction are part of 'every store' (F-C0702, F-0409), and a silent drop or a misreported error class is a refusal that does not say why (F-0307, F-0817, F-C1602).
- Sources at the pin: `docs/adr/0004-erasure-removes-content-not-history.md:19-21`; `iris_src/src/Graph/KG/Ledger.cls:61-70`; `iris_vector_graph/ledger/errors.py:1-40`; `docs/dev/TESTING_POLICY.md`
- Implemented by: M-08, M-10, M-11; relied on by 37 objects in modules 01, 03, 04, 05, 06, 07, 08, 09, 11, 15, 16, 17, 18
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-as-built-ax-03`, `sys00-control-ax03-refusal-writes`
- As-built findings breaking it, S1: F-0409, F-C0702
- As-built findings breaking it, S2: F-0307, F-0308, F-0601, F-0608, F-0615, F-0704, F-0803, F-1511, F-C0501, F-C0748, F-C0848, F-C1802
- As-built findings breaking it, S3: F-0513, F-0614, F-0804, F-0806, F-0807, F-0817, F-0903, F-1509, F-1704, F-1714, F-C0940, F-C1107, F-C1110, F-C1602
- As-built findings breaking it, S4: F-0306, F-0825, F-1111, F-1506, F-C0415, F-C0717, F-C0841, F-C1109

### AX-04 All or none across stores

- Rule: A command that writes several stores writes all of them or none: it is one transaction, or a sequence whose every intermediate state is named and recoverable.
- Formal reading: `for every execution of cmd ending at a quiescent point: delta(state) in {full_effect(cmd), empty}`
- Repair: Unchanged in substance; units sent to a server (Bolt explicit transactions, HTTP tx commit, FHIR event writes) are commands too (F-1601, F-1610, F-1609).
- Sources at the pin: `CONTEXT.md:198-208`; `docs/adr/0004-erasure-removes-content-not-history.md:8-21`; `iris_src/src/Graph/KG/Ledger.cls:397-415`
- Implemented by: M-01, M-05, M-10; relied on by 36 objects in modules 03, 04, 05, 06, 07, 08, 11, 12, 13, 14, 15, 16, 17, 18
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-as-built-ax-04`, `sys00-control-ax04-erase-split`
- As-built findings breaking it, S1: F-0409, F-C0702
- As-built findings breaking it, S2: F-0305, F-0701, F-1601, F-1609, F-1610, F-C0330, F-C0748
- As-built findings breaking it, S3: F-C1501, F-C1502, F-C1548
- As-built findings breaking it, S4: F-C0301

### AX-05 History only grows

- Rule: The ledger's records and revisions are only appended; a saved record changes only into its tombstone, and the head never moves back.
- Formal reading: `for every step: records'[k] in {records[k], tomb(records[k])} for k <= head, and head' >= head`
- Repair: Adds 'the head never moves back', which a replacing restore violates (F-1801).
- Sources at the pin: `CONTEXT.md:183-197`; `docs/adr/0013-redaction-removes-content-from-history.md:20-30`; `iris_src/src/Graph/KG/LedgerRevision.cls:77-123`
- Implemented by: M-01, M-06; relied on by 13 objects in modules 03, 05, 08, 11, 14, 18
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-as-built-ax-05`, `sys00-control-ax05-delete-records`
- As-built findings breaking it, S1: F-1801, F-C1850
- As-built findings breaking it, S2: F-C1150

### AX-06 At most once per retry key

- Rule: A request repeated with the same retry key (or the same business identity) takes effect at most once; a repeat gets the first answer without any further effect, or a clear refusal.
- Formal reading: `count(effects(key)) <= 1; replay(key) => delta(state) = empty (post-commit effects included)`
- Repair: Extended from the ledger key to every retry layer (HTTP client resend, server re-run) and to post-commit effects (F-1306, F-C1703, F-C1604).
- Sources at the pin: `iris_src/src/Graph/KG/Ledger.cls:454-473`; `docs/adr/0013-redaction-removes-content-from-history.md:10-19`; `specs/213-graph-revision-ledger/contracts/ledger-api.md`
- Implemented by: M-02; relied on by 7 objects in modules 01, 06, 11, 13, 16, 17
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-as-built-ax-06`, `sys00-control-ax06-post-on-replay`
- As-built findings breaking it, S1: F-1101, F-1306
- As-built findings breaking it, S2: F-C1604, F-C1703, F-CS01
- As-built findings breaking it, S3: F-1106

### AX-07 A governed change is recorded with it

- Rule: While the ledger governs a kind of content, every change of that content is saved in the same transaction as its record; a write that cannot be recorded is refused in strict mode.
- Formal reading: `ledger on and kind governed: delta(content) != empty <=> a record of exactly that delta commits in the same transaction`
- Repair: Adds both directions: no record without its change (F-0511, F-1105) and no unrecorded change while strict (F-0301, F-1108).
- Sources at the pin: `iris_src/src/Graph/KG/Ledger.cls:387-415`; `CONTEXT.md:193-197`
- Implemented by: M-01; relied on by 12 objects in modules 03, 05, 08, 11, 14, 18
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-as-built-ax-07`, `sys00-control-ax07-unrecorded-apply`
- As-built findings breaking it, S1: F-0505, F-C1350
- As-built findings breaking it, S2: F-0303, F-0503, F-0504, F-0801, F-1105, F-1108, F-C0150, F-C0151, F-C0450
- As-built findings breaking it, S3: F-0301, F-0302, F-0511, F-C0340
- As-built findings breaking it, S4: F-C1108

### AX-08 Derived stores match or say they are stale

- Rule: A store built from other stores either equals its derivation from their committed content or carries a staleness signal every reader checks; a rolled-back or interrupted source write never leaves a derived store current and wrong.
- Formal reading: `stamp(D) = token => D = f(committed(S)); every write of S moves token or updates D in S's transaction`
- Repair: Adds committed content (rollback, F-0402, F-C0401) and the reader's obligation to check the signal (F-0906).
- Sources at the pin: `CONTEXT.md:88-128`; `docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md:10-18`; `iris_src/src/Graph/KG/Adjacency.cls:20-35`
- Implemented by: M-04, M-12; relied on by 22 objects in modules 02, 03, 04, 05, 06, 07, 09, 10, 11, 15, 17, 18
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-as-built-ax-08`, `sys00-control-ax08-erase-skips-derived`
- As-built findings breaking it, S2: F-0204, F-0208, F-0303, F-0401, F-0402, F-0403, F-0406, F-0501, F-0703, F-0901, F-0906, F-1004, F-1805, F-C0401, F-C0901, F-C1202
- As-built findings breaking it, S3: F-0302, F-0407, F-1005, F-C1101
- As-built findings breaking it, S4: F-0405, F-C0801

### AX-09 One install, one schema, one version per namespace

- Rule: A namespace holds one install of the product under one recorded schema; setup is idempotent, reports every failure, never touches objects outside that schema, and code runs only against the version it expects.
- Formal reading: `recorded_schema(ns) fixed after first setup; setup;setup = setup; touched(setup) within schema(ns) union manifest(legacy)`
- Repair: Adds idempotence, the failure report and the version gate (F-0102, F-0103, F-0107).
- Sources at the pin: `CONTEXT.md:14-26`; `docs/adr/0016-one-ivg-schema-per-namespace.md:10-13`; `CONTEXT.md:286-291`
- Implemented by: M-08; relied on by 13 objects in modules 01, 03, 09, 11, 15, 16, 17
- Not in the module-00 composition; its laws are checked by the generic machines of M-08
- As-built findings breaking it, S1: F-C1306
- As-built findings breaking it, S2: F-0102, F-0309, F-1605, F-C0150
- As-built findings breaking it, S3: F-0103, F-0105, F-0107, F-0109
- As-built findings breaking it, S4: F-C0690

### AX-10 Removal reaches every store and copy

- Rule: Erasure followed by redaction removes a target's content from every store that holds it, every derived store and every copy the product makes (indexes, quarantine, snapshots, history text, retry keys), or the receipt names exactly what remains.
- Formal reading: `after erase(t); redact(t) succeeds: for every store s in Stores (inventory complete): content(s, t) = empty, or s in receipt.remaining`
- Repair: New. SYS-D26/D27 define erasure and redaction; no SYS axiom stated their reach. Spec 256 SC-001 and FR-008 (receipt) are its intent sources.
- Sources at the pin: `CONTEXT.md:198-220`; `docs/adr/0004-erasure-removes-content-not-history.md:8-17`; `specs/256-ledger-tenant-redaction/spec.md:114-148`
- Implemented by: M-05, M-06; relied on by 14 objects in modules 05, 06, 07, 12, 13, 15, 18
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-as-built-ax-10`, `sys00-control-ax10-binding-kept`
- As-built findings breaking it, S1: F-0606, F-0702, F-1305, F-1306, F-1502, F-C1203, F-C1250, F-C1306, F-C1308, F-C1351, F-C1850
- As-built findings breaking it, S2: F-0507, F-0618, F-C1304, F-CS01
- As-built findings breaking it, S3: F-C0840, F-C1305, F-C1309, F-C1548

### AX-11 Conflicting commands serialize

- Rule: Commands whose footprints overlap behave as if run one at a time: each takes the lock that guards what it reads and writes, a marker is set before the first effect it guards, and only its owner clears it.
- Formal reading: `every reachable history of overlapping commands is equivalent to some serial order of them`
- Repair: New. Implicit in ADR-0013 (head lock), ADR-0011/0012 (writer lock, generations) and spec 256 FR-006; every S1 race finding (F-1201, F-1302, F-1303, F-C1201) violates it.
- Sources at the pin: `docs/adr/0013-redaction-removes-content-from-history.md:10-19`; `specs/256-ledger-tenant-redaction/spec.md:125`; `iris_src/src/Graph/KG/Adjacency.cls:20-35`
- Implemented by: M-03, M-07; relied on by 13 objects in modules 02, 04, 06, 07, 09, 10, 11, 12, 13, 15
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-as-built-ax-11`, `sys00-as-built-ax-11-marker`, `sys00-control-ax11-check-before-lock`
- As-built findings breaking it, S1: F-1114, F-1302, F-1303, F-C1201, F-C1301, F-C1350
- As-built findings breaking it, S2: F-0207, F-0701, F-1103, F-1201, F-C0348, F-C0349, F-C0402, F-C1202, F-C1302
- As-built findings breaking it, S3: F-0407, F-0905, F-1102, F-1104, F-1807, F-C0601, F-C0670

### AX-12 Truthful outcomes and committed observations

- Rule: A command's reported outcome equals its effect: success means the whole effect happened and is kept, counts and receipts report what was done; a read changes no stored state except derived caches, and a read or an archive shows a state some serial order of committed commands produced.
- Formal reading: `outcome(cmd) = ok(r) => effect(cmd) complete and durable and r = report(effect); read: delta(primary state) = empty and answer from some committed serial state`
- Repair: New. The durability half is intent-undecided (F-C1102: no IVG document states a durability premise). Read purity (a read writes no primary state) is part of it (F-C1001).
- Sources at the pin: `docs/adr/0004-erasure-removes-content-not-history.md:19-21`; `specs/256-ledger-tenant-redaction/spec.md:127-129`; `CONTEXT.md:183-187`
- Implemented by: M-02, M-03, M-06, M-07, M-10, M-13; relied on by 38 objects in modules 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-as-built-ax-12`, `sys00-control-ax12-receipt-early`
- As-built findings breaking it, S1: F-1303, F-1305, F-1402, F-C1804
- As-built findings breaking it, S2: F-0102, F-0604, F-0709, F-1508, F-1601, F-1615, F-1802, F-1803, F-C0330, F-C0348, F-C1102, F-C1801, F-C1802
- As-built findings breaking it, S3: F-0101, F-0613, F-1611, F-1804, F-C0940, F-C1001
- As-built findings breaking it, S4: F-C1640

### AX-13 Least capability

- Rule: A caller can do only what its key and role allow: a read-only caller changes nothing, a missing or wrong key is refused before any effect, and no entry point hands a caller a capability beyond the product's API (server files, raw SQL or code text).
- Formal reading: `role(caller) = read_only => delta(state) = empty; keys_on and not key_ok => refused before effect`
- Repair: New. Intent: docs/ADMIN_GUIDE.md section 5, spec 253 FR-011.
- Sources at the pin: `docs/ADMIN_GUIDE.md:824-840`; `docs/ADMIN_API.md:32-45`; `specs/253-native-cypher-executor/spec.md:124`
- Implemented by: M-11; relied on by 13 objects in modules 08, 09, 16, 17, 18
- Not in the module-00 composition; its laws are checked by the generic machines of M-11
- As-built findings breaking it, S1: F-0814, F-0815, F-1709, F-C1803
- As-built findings breaking it, S2: F-1614, F-1806, F-C0341, F-C1603
- As-built findings breaking it, S3: F-0908, F-C1741

### AX-14 Accepted work progresses

- Rule: Work the product accepts (a queue entry, a run, a session) finishes or is reported failed under fair scheduling: no entry starves, no run restarts forever, no resource stays held after its holder ends.
- Formal reading: `under weak fairness of the worker: pending(e) leads-to done(e) or failed(e)`
- Repair: New. Progress premises are TRUST.md rows (fair scheduling, operator re-runs); the axiom states what the product must do under them.
- Sources at the pin: `docs/adr/0013-redaction-removes-content-from-history.md:10-19`; `iris_src/src/Graph/KG/EmbedQueue.cls:106-134`
- Implemented by: M-07; relied on by 5 objects in modules 06, 09, 13, 15
- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): `sys00-reviewed-progress`, `sys00-as-built-ax-14`, `sys00-control-ax14-marker-never-cleared`
- As-built findings breaking it, S2: F-C1303, F-C1307, F-C1601
- As-built findings breaking it, S3: F-C0347
- As-built findings breaking it, S4: F-C0605

## Named exceptions

| Id | Axiom | Exception | Source |
|---|---|---|---|
| EXC-01 | AX-04 | DDL after commit: EraseGraph drops routed vector tables after its transaction commits; a failure there leaves empty tables, not content. | `iris_src/src/Graph/KG/Eraser.cls:47-260`; `ontology/00-system.md SYS-I4 notes` |
| EXC-02 | AX-05 | PurgeAll reset: PurgeAll is a test and admin reset of the whole ledger, outside the growth rule. | `iris_src/src/Graph/KG/Ledger.cls:242-250` |
| EXC-03 | AX-07 | Post-commit properties: Post-commit properties are written by the client after the ledger commit, outside its transaction (by design; their replay is F-1306). | `iris_vector_graph/ledger/client.py:430-487` |
| EXC-04 | AX-07 | Vectors are not ledgered: Vector writes never pass through the ledger and no revision holds a vector (VEC-B1.2). | `docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md` |
| EXC-05 | AX-08 | Route cache window: An engine may reuse a route it read up to 30 s ago without asking the registry (VEC-T2.13); missing routes are never cached. | `iris_vector_graph/_engine/vector.py` |
| EXC-06 | AX-02 | Interned snapshot has no graph dimension: The interned snapshot gives the default graph's answer only while no named graph has an edge (documented). | `CONTEXT.md:97-102` |
| EXC-07 | AX-10 | Tombstone keeps shape and digest: A tombstone keeps seq, ordinal, op kind, entity kind and a SHA-256 digest of the replaced record (ADR-0013); the digest is not content. | `docs/adr/0013-redaction-removes-content-from-history.md:10-19` |
| EXC-08 | AX-04 | Monotone counters survive rollback: $Increment counters and version tokens are not undone by a rollback (E-INCR); they only mark staleness, so a rolled-back increment is safe. | `iris_src/src/Graph/KG/Adjacency.cls:26-33` |
| EXC-09 | AX-09 | Legacy objects kept until removed: 4.5.x objects outside the IVG Schema stay in place, frozen and unused, until an operator removes them from the fixed manifest. | `CONTEXT.md:286-291`; `docs/adr/0016-one-ivg-schema-per-namespace.md` |
| EXC-10 | AX-12 | Algorithm runs read without isolation: Algorithms read the edges with no lock; a write during a long run can give a mix of old and new edges (ALG-P6; the concurrency contract of Neo4j GDS, spec 162 FR-021). | `iris_src/src/Graph/KG/Centrality.cls:25-28` |
| EXC-11 | AX-08 | Undeclared adjacency or label index: Where the adjacency or label index is not declared on its table, only the engine's own writers and a rebuild keep it; any other write leaves it stale, and its declaration flag (Graph.KG.Adjacency.Indexed) is the signal readers must check (CONTEXT.md, Adjacency Index). | `CONTEXT.md:88-96`; `iris_src/src/Graph/KG/Adjacency.cls:20-35` |

## Contract clauses a requirement may trace to

Besides an axiom or a named exception, a requirement (`trace.json`) may trace to a clause of the IRIS environment contract
(`iris-contract/CONTRACT.md`, ids E-* and X-*), to the domain contract DC-REPLAY (replay of the ledger equals the governed
store; the 3.3a-domain-contract cell) or to a module's functional contract DC-FUNC-NN (what that module's commands compute,
formalised by its L1 model in the D-1 crate named in `axioms.json`). A DC-FUNC trace is the weakest kind: it says the
statement is a functional rule of its module, which no universal axiom governs; nothing checks that the L1 model encodes
each such statement.
